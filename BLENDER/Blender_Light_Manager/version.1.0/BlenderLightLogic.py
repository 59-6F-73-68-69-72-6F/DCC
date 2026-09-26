import os
import weakref
from functools import partial

from PySide6.QtWidgets import QWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QCheckBox, QLabel, QLineEdit, QColorDialog
from PySide6.QtCore import Qt, QTimer, QObject
from PySide6.QtGui import QPixmap, QColor
import bpy

from LightManagerUI import CustomLineEditNum


SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
PREFIX = "Lgt_"


class BlenderLightLogic(QObject):
    """
    A class that handles the logic and interaction between the UI and Blender.
    
    It manages light creation, renaming, deletion, and attribute modification,
    synchronizes Blender data-block changes with the UI using depsgraph handlers,
    
    And provides layer selection functionality.
    """

    def __init__(self, ui):
        """
        Initializes the logic for the Light Manager.
        
        Args: ui (LightManagerUI): An instance of the UI class to which this logic will connect.
        """
        super().__init__()
        self.ui = ui
        self.script_jobs = []  # JOB ID COLLECTOR
        self.lightTypes = ["POINT", "SUN", "SPOT", "AREA"]

    def rename_light(self, old_name: str, new_name: str, light_table: object):
        """
        Renames a light in the Blender scene and updates the UI accordingly.
        """
        num = 0
        naming_convention = f"{PREFIX}{new_name}.{num:03d}"

        if not new_name.strip():
            self.info_timer("Error: New name cannot be empty.")
            return

        if old_name in bpy.data.objects:
            bpy.data.objects[old_name].name = naming_convention
            bpy.data.collections["C" + old_name].name = "C" + naming_convention
            self.refresh(light_table)
            self.info_timer(f"Light: '{old_name}' renamed to '{new_name}'")
        else:
            self.info_timer(f"Error: Could not find actor '{old_name}' to rename.")

    def refresh(self, light_table: object):
        """
        Refreshes UI to reflect the current state of lights in the Blender scene.
        
        This function schedules the actual refresh on Blender's main thread via bpy.app.timers
        to avoid using bpy.context from a non-main (UI) thread.
        """
        def _do_refresh():
            try:
                # REMOVE ALL EXISTING HANDLERS TO AVOID DUPLICATES
                for job_id in self.script_jobs:
                    if job_id in bpy.app.handlers.depsgraph_update_post:
                        bpy.app.handlers.depsgraph_update_post.remove(job_id)
                self.script_jobs.clear()

                # SAVE CURRENT SCROLL POSITION
                v_scroll_bar = light_table.verticalScrollBar()
                h_scroll_bar = light_table.horizontalScrollBar()
                current_vpos = v_scroll_bar.value()
                current_hpos = h_scroll_bar.value()
                max_v_range = v_scroll_bar.maximum()
                max_h_range = h_scroll_bar.maximum()

                light_table.setRowCount(0)  # CLEAR THE TABLE

                # REPOPULATE THE TABLE
                # Prevent triggering view-layer change callbacks while updating the combo
                self.ui.combo_view_layer.blockSignals(True)  # BLOCKING SIGNAL

                scene = bpy.context.scene
                actual_view_layer = bpy.context.view_layer
                self.list_layers = sorted([vl.name for vl in scene.view_layers])

                # Determine Blender's authoritative active view layer (DCC)
                window = getattr(bpy.context, 'window', None)
                blender_active = None
                if window is not None and getattr(window, 'view_layer', None) is not None:
                    blender_active = window.view_layer.name
                else:
                    active_scene_vl = getattr(scene.view_layers, 'active', None)
                    if active_scene_vl is not None:
                        blender_active = active_scene_vl.name
                    else:
                        ctx_vl = getattr(bpy.context, 'view_layer', None)
                        blender_active = ctx_vl.name if ctx_vl is not None else None

                # Preserve previous UI selection as fallback
                previous_layer = self.ui.combo_view_layer.currentText() if hasattr(self.ui, 'combo_view_layer') else None

                self.ui.combo_view_layer.clear()
                self.ui.combo_view_layer.addItems(self.list_layers)

                # Align UI to Blender's active view layer when possible; otherwise restore previous selection
                if blender_active and blender_active in self.list_layers:
                    self.ui.combo_view_layer.setCurrentText(blender_active)
                elif previous_layer and previous_layer in self.list_layers:
                    self.ui.combo_view_layer.setCurrentText(previous_layer)

                self.ui.combo_view_layer.blockSignals(False)  # STOP BLOCKING SIGNAL

                bpy.ops.object.select_all(action='DESELECT')
                # Lights in the active view layer
                all_lights = [obj for obj in actual_view_layer.objects if obj.type == "LIGHT"]
                # Include lights that belong to CLgt_* collections so they remain visible in the UI
                try:
                    for obj in scene.objects:
                        if obj.type == 'LIGHT':
                            for coll in getattr(obj, 'users_collection', []):
                                if coll and isinstance(coll.name, str) and coll.name.startswith("C" + PREFIX):
                                    if obj not in all_lights:
                                        all_lights.append(obj)
                                    break
                except Exception:
                    pass

                for light in all_lights:
                    light_type = light.data.type

                    self.light_name_to_list(light, light_type, light_table)
                    self.mute_solo_to_list(light, light_table, light_type)
                    self.color_button_to_list(light, light_table)
                    self.entry_attr_num_to_list(light, "exposure", 5, light_table)
                    use_temp = self.checkbox_attr_to_list(light, "use_temperature", 6, light_table)
                    if use_temp == True:
                        self.entry_attr_num_to_list(light, "temperature", 7, light_table)
                        self.info_timer("Temperature enabled for this light")
                    else:
                        widget = QLabel("N/A")
                        widget.setAlignment(Qt.AlignCenter)
                        light_table.setCellWidget(self.row_position, 7, widget)
                    if light_type == "SUN" or light_type == "AREA":
                        widget = QLabel("N/A")
                        widget.setAlignment(Qt.AlignCenter)
                        light_table.setCellWidget(self.row_position, 8, widget)
                    else:
                        self.entry_attr_num_to_list(light, "shadow_soft_size", 8, light_table)
                    self.checkbox_attr_to_list(light, "use_shadow", 9, light_table)
                    self.entry_attr_text_to_list(light, "lightgroup", 10, light_table)

                    #  add more attributes here based on your UI

                # RESTORE SCROLL POSITION (Moved outside the loop)
                new_vmax_range = v_scroll_bar.maximum()

                if max_v_range - current_vpos <= 1:
                    v_scroll_bar.setValue(new_vmax_range)
                else:
                    v_scroll_bar.setValue(current_vpos)

                self.info_timer("Light Manager refreshed successfully.")

            except Exception:
                # Swallow exceptions so timer unregisters cleanly
                pass
            return

        try:
            bpy.app.timers.register(_do_refresh, first_interval=0.01)
        except Exception:
            # Fallback: run immediately (best-effort)
            _do_refresh()

    def delete(self, light_table: object):
        """
        Deletes the selected light from the Blender scene and updates the UI.
        """
        selected_items = light_table.selectedItems()
        if not selected_items:
            return

        light_name = selected_items[0].text()  # Get the name of the selected light
        light_obj_to_remove = bpy.data.objects.get(light_name)  # Get light by name
        collection_to_remove = bpy.data.collections.get("C" + light_name)  # Get collection by name

        if light_obj_to_remove and collection_to_remove or light_obj_to_remove:
            if collection_to_remove:
                bpy.data.collections.remove(collection_to_remove, do_unlink=True)
            if light_obj_to_remove:
                bpy.data.objects.remove(light_obj_to_remove, do_unlink=True)
            self.info_timer(f"Light '{light_name}' deleted successfully.")
            self.refresh(light_table)
        else:
            self.info_timer(f"Error: Could not find actor '{light_name}' to delete.")

    def light_table_selection(self, lightTable: object):
        """
        Selects the corresponding light in Blender when a row is selected in the UI table.
        The operation is scheduled on Blender's main thread via bpy.app.timers.register to
        avoid modifying bpy.context from the UI thread.
        """
        selected_items = lightTable.selectedItems()
        if not selected_items:
            def _clear_selection():
                bpy.ops.object.select_all(action='DESELECT')

            try:
                bpy.app.timers.register(_clear_selection, first_interval=0.01)
            except Exception:
                _clear_selection()
            return

        row = selected_items[0].row()
        light_name_item = lightTable.item(row, 0)
        if not light_name_item:
            return
        light_name = light_name_item.text()

        def _apply_selection():
            try:
                obj = bpy.data.objects.get(light_name)
                if obj is None:
                    return

                scene = bpy.context.scene
                # Determine the view layer referenced by the UI combo (where the object is listed)
                vl_name = None
                try:
                    vl_name = self.ui.combo_view_layer.currentText() if hasattr(self.ui, 'combo_view_layer') else None
                except Exception:
                    vl_name = None

                target_vl = None
                if vl_name:
                    target_vl = scene.view_layers.get(vl_name)

                # Prefer setting active/select on the target view layer object if present there
                target_obj = None
                if target_vl is not None:
                    try:
                        bpy.ops.object.select_all(action='DESELECT')
                        target_obj = target_vl.objects.get(obj.name)
                    except Exception:
                        target_obj = None

                # Fallback to the object from bpy.data
                if target_obj is None:
                    target_obj = obj

                try:
                    if target_vl is not None and target_obj is not None:
                        target_vl.objects.active = target_obj
                    else:
                        # Use context view layer as fallback
                        bpy.context.view_layer.objects.active = target_obj
                except Exception:
                    pass

                try:
                    # Select the object instance (works across layers)
                    target_obj.select_set(True)
                except Exception:
                    pass

            except Exception:
                pass
            return

        try:
            bpy.app.timers.register(_apply_selection, first_interval=0.0)
        except Exception:
            _apply_selection()

    def create_light(self, light_name: str, light_type: str, light_table: object):
        """
        Creates a new light of the specified type and name in the Blender scene and updates the UI.
        """
        if light_type not in self.lightTypes:
            self.info_timer(f"Error: Light type '{light_type}' is invalid.")
            return

        if not light_name.strip():
            light_name = light_type

        # INCREMENTAL NAMING CONVENTION
        num = 0
        naming_convention = f"{PREFIX}{light_name}.{num:03d}"

        # Create a new light data-block
        light_data = bpy.data.lights.new(name=naming_convention, type=light_type)
        # Create a new object with the light data-block
        light_object = bpy.data.objects.new(name=naming_convention, object_data=light_data)

        # Create a new collection
        new_collection = bpy.data.collections.new("C" + naming_convention)
        bpy.context.scene.collection.children.link(new_collection)
        new_collection.objects.link(light_object)

        # POPULATE THE TABLE LIST
        self.refresh(light_table)  # REFRESH THE ENTIRE TABLE
        self.info_timer(f" '{naming_convention}' has been created successfully.")

    def light_name_to_list(self, light: bpy.types.Object, light_type: str, light_table: object):
        """
        Adds a new row to the light table with the light's name and type icon.
        """
        self.row_position = light_table.rowCount()
        light_table.insertRow(self.row_position)

        # POPULATE THE "Name" COLUMN
        name_item = QTableWidgetItem(light.name)
        name_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        light_table.setItem(self.row_position, 0, name_item)

        # POPULATE THE "Light Type" COLUMN
        icon_light_type = QLabel()
        icon_path = os.path.join(SCRIPT_PATH, "img", "icons", f"{light_type}.png")

        img = QPixmap(icon_path)
        icon_light_type.setPixmap(img)
        icon_light_type.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        light_table.setCellWidget(self.row_position, 3, icon_light_type)

    def mute_solo_to_list(self, light: bpy.types.Object, light_table: object, light_type: str):
        """
        Adds Mute and Solo checkboxes to the current row in the table.
        """
        mute_widget = QWidget()
        mute_checkbox = QCheckBox()
        mute_checkbox.setStyleSheet("QCheckBox::indicator:unchecked { background-color: #f94144 }")
        actual_visibility = light.visible_get()
        mute_checkbox.setChecked(actual_visibility)
        mute_checkbox.stateChanged.connect(partial(self.update_all_lights_visibility, light_table, light))
        mute_layout = QHBoxLayout(mute_widget)
        mute_layout.addWidget(mute_checkbox)
        mute_layout.setAlignment(Qt.AlignCenter)
        mute_layout.setContentsMargins(0, 0, 0, 0)

        solo_widget = QWidget()
        solo_checkbox = QCheckBox()
        solo_checkbox.setStyleSheet("QCheckBox::indicator:checked { background-color: #adb5bd }")
        solo_checkbox.stateChanged.connect(partial(self.on_solo_toggled, self.row_position, light_table, light))
        solo_layout = QHBoxLayout(solo_widget)
        solo_layout.addWidget(solo_checkbox)
        solo_layout.setAlignment(Qt.AlignCenter)
        solo_layout.setContentsMargins(0, 0, 0, 0)

        light_table.setCellWidget(self.row_position, 1, mute_widget)
        light_table.setCellWidget(self.row_position, 2, solo_widget)

    def color_button_to_list(self, light: bpy.types.Object, light_table: object):
        """
        Adds a color button to the current row in the table that reflects the light's color.
        Clicking the button opens a color picker to change the light's color.
        """
        colorBtn_widget = QWidget()
        colorBtn = QPushButton()
        colorBtn.setFixedSize(56, 26)
        self.set_button_color(light, colorBtn)
        colorBtn.clicked.connect(partial(self.set_color, light, colorBtn))

        colorBtn_layout = QHBoxLayout(colorBtn_widget)
        colorBtn_layout.addWidget(colorBtn)
        colorBtn_layout.setAlignment(Qt.AlignCenter)
        colorBtn_layout.setContentsMargins(0, 0, 0, 0)
        light_table.setCellWidget(self.row_position, 4, colorBtn_widget)

    def entry_attr_text_to_list(self, light: bpy.types.Object, attribute_name: str, column: int, light_table: object):
        """
        Adds a string input field to a cell for a specific string attribute (e.g., light group).
        """
        attribute_value = getattr(light, attribute_name, None)

        bar_text = QLineEdit(placeholderText="AOV")
        bar_text.setFixedSize(59, 29)
        bar_text.setAlignment(Qt.AlignCenter)
        bar_text.setContentsMargins(0, 0, 0, 0)
        # Initialize UI with current Blender value
        bar_text.setText("") if attribute_value is None else bar_text.setText(str(attribute_value))

        def _update_blender_from_ui():
            light_group_name = bar_text.text().strip()
            try:
                if light_group_name:
                    bpy.ops.scene.view_layer_add_lightgroup(name=light_group_name)
                    setattr(light, attribute_name, light_group_name)
                    bar_text.setText(light_group_name)
                    self.info_timer(text=f"{light.name} set Light Group: '{light_group_name}'")
                else:
                    setattr(light, attribute_name, "")
                    self.info_timer(text=f"{light.name} cleared Light Group")
            except (ValueError, RuntimeError) as e:
                self.info_timer(f"Invalid input : {e}")
                # ON ERROR, Reset the text to the current value in BLENDER
                current_blender_val = getattr(light, attribute_name, None)
                bar_text.setText("") if current_blender_val is None else bar_text.setText(str(current_blender_val))
        bar_text.returnPressed.connect(_update_blender_from_ui)

        """
        Use a weak reference to the widget to prevent dangling pointers.
        The handler can check if the widget still exists before accessing it.
        """
        bar_text_weak_ref = weakref.ref(bar_text)

        def _update_ui_from_blender(scene, depsgraph):
            widget = bar_text_weak_ref()
            try:
                if widget is None or light.name not in bpy.data.objects:
                    return
            except ReferenceError:
                # The light object has been deleted.
                return

            # Check if the specific light object or its data-block was updated
            for update in depsgraph.updates:
                try:
                    update_name = getattr(getattr(update, 'id', None), 'name', None)
                except Exception:
                    update_name = None

                if update_name in (getattr(light, 'name', None), getattr(getattr(light, 'data', None), 'name', None)):
                    widget.blockSignals(True)
                    new_value = getattr(light, attribute_name, None)
                    try:
                        widget.setText("") if new_value is None else widget.setText(str(new_value))
                    finally:
                        widget.blockSignals(False)
                    break

        # CREATE A HANDLER TO LISTEN FOR CHANGES AND STORE CALLBACK FOR CLEANUP
        callback = _update_ui_from_blender
        bpy.app.handlers.depsgraph_update_post.append(callback)
        self.script_jobs.append(callback)

        widget = QWidget()
        bar_text_layout = QHBoxLayout(widget)
        bar_text_layout.addWidget(bar_text)
        bar_text_layout.setAlignment(Qt.AlignCenter)
        bar_text_layout.setContentsMargins(0, 0, 0, 0)
        light_table.setCellWidget(self.row_position, column, widget)

    def entry_attr_num_to_list(self, light: bpy.types.Object, attribute_name: str, column: int, light_table: object):
        """
        Adds a numeric input field to a cell for a specific float or int attribute.
        """
        self.atttribute_value = getattr(light.data, attribute_name)
        if self.atttribute_value is None:
            widget = QLabel("N/A")
            widget.setAlignment(Qt.AlignCenter)
            light_table.setCellWidget(self.row_position, column, widget)
            return

        # Create the numeric input field
        bar_text = CustomLineEditNum()
        bar_text.setFixedSize(65, 29)
        bar_text.setAlignment(Qt.AlignCenter)

        # SETTING THE CURRENT VALUE IN THE UI
        if isinstance(self.atttribute_value, (float)):
            bar_text.setText(f"{self.atttribute_value:.3f}")
        elif isinstance(self.atttribute_value, (int)):
            bar_text.setText(f"{self.atttribute_value}")

        def _update_blender_from_ui():
            """
            Gets called when the user finishes editing the text field.
            """
            try:
                # SET VALUE IN BLENDER
                new_value = float(bar_text.text())
                setattr(light.data, attribute_name, new_value)
            except ValueError:
                self.info_timer(f"Wrong input:  Please enter a number")
                # ON ERROR, Reset the text to the current value in BLENDER
                current_blender_val = self.atttribute_value
                if isinstance(current_blender_val, (float)):
                    bar_text.setText(f"{current_blender_val:.3f}")
                elif isinstance(current_blender_val, (int)):
                    bar_text.setText(f"{current_blender_val}")
            except ReferenceError:
                self.info_timer(f"Error: Could not update '{attribute_name}',light deleted")

        bar_text.editingFinished.connect(_update_blender_from_ui)

        """
        Use a weak reference to the widget to prevent dangling pointers.
        The handler can check if the widget still exists before accessing it.
        """
        bar_text_weak_ref = weakref.ref(bar_text)

        def _update_ui_from_blender(scene, depsgraph):
            widget = bar_text_weak_ref()
            try:
                if widget is None or light.name not in bpy.data.objects:
                    return
            except ReferenceError:
                # The light object has been deleted.
                return
            # Check if the specific light data-block was updated
            for update in depsgraph.updates:
                if update.id.name == light.data.name:
                    widget.blockSignals(True)
                    new_value = getattr(light.data, attribute_name)
                    try:
                        if isinstance(new_value, (float)):
                            widget.setText(f"{new_value:.3f}")
                        elif isinstance(new_value, (int)):
                            widget.setText(f"{new_value}")
                    finally:
                        # RE-ESTABLISH THE SIGNAL
                        widget.blockSignals(False)

        # # CREATE A HANDLER TO LISTEN FOR CHANGES AND STORE ID FOR CLEANUP
        callback = _update_ui_from_blender
        bpy.app.handlers.depsgraph_update_post.append(callback)
        self.script_jobs.append(callback)

        widget = QWidget()
        bar_text_layout = QHBoxLayout(widget)
        bar_text_layout.addWidget(bar_text)
        bar_text_layout.setAlignment(Qt.AlignCenter.AlignCenter)
        bar_text_layout.setContentsMargins(0, 0, 0, 0)
        light_table.setCellWidget(self.row_position, column, widget)

    def checkbox_attr_to_list(self, light: bpy, attribute_name: str, column: int, light_table: object):
        """
        Adds a checkbox to a cell for a specific boolean attribute.
        """
        if not light:
            return

        try:
            current_value = getattr(light.data, attribute_name)

        except (Exception, ValueError):
            self.info_timer(f"No Parameter {attribute_name} for this light")
            widget = QLabel("N/A")
            widget.setAlignment(Qt.AlignCenter)
            light_table.setCellWidget(self.row_position, column, widget)
            return
        # SETTING THE CURRENT VALUE IN THE UI
        if current_value is True or current_value is False:
            widget = QWidget()
            checkbox = QCheckBox()
            checkbox.setChecked(bool(current_value))

        def _update_blender_from_ui(checked):
            try:
                setattr(light.data, attribute_name, bool(checked))
                self.refresh(light_table)
            except (ReferenceError, RuntimeError):
                self.info_timer(f"Error: Could not update '{attribute_name}' for light deleted")

        checkbox.clicked.connect(_update_blender_from_ui)

        # Use a weak reference to the widget to prevent dangling pointers.
        # The handler can check if the widget still exists before accessing it.
        checkbox_weak_ref = weakref.ref(checkbox)

        def _update_ui_from_blender(scene, depsgraph):
            widget = checkbox_weak_ref()
            try:
                if widget is None or light.name not in bpy.data.objects:
                    return
            except ReferenceError:
                # The light object has been deleted.
                return
            # Check if the specific light data-block was updated
            for update in depsgraph.updates:
                if update.id.name == light.data.name:
                    current_value = getattr(light.data, attribute_name)
                    widget.blockSignals(True)
                    widget.setChecked(bool(current_value))
                    widget.blockSignals(False)
                    break

        job_id = bpy.app.handlers.depsgraph_update_post.append(_update_ui_from_blender)
        self.script_jobs.append(job_id)

        layout = QHBoxLayout(widget)
        layout.addWidget(checkbox)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        light_table.setCellWidget(self.row_position, column, widget)
        return current_value

    def on_solo_toggled(self, toggled_row: int, light_table: object, state: bool, light: bpy.types.Object, *args: str):
        """
        Ensures that only one 'Solo' checkbox can be active at a time.
        When a 'Solo' checkbox is checked, all other 'Solo' checkboxes are unchecked.
        """
        if state:
            # SKIP the ROW OF THE CHECKBOX THAT WAS JUST TOGGLED
            for i in range(light_table.rowCount()):
                if i != toggled_row:
                    solo_widget = light_table.cellWidget(i, 2)
                    if solo_widget:
                        # RETRIEVE THE CUSTOM WIDGET IN THE  'Solo' COLUMN
                        solo_checkbox = solo_widget.findChild(QCheckBox)
                        if solo_checkbox and solo_checkbox.isChecked():     # PREVENT RECURSIVE CALLS OF THIS FUNCTION
                            solo_checkbox.blockSignals(True)
                            solo_checkbox.setChecked(False)
                            solo_checkbox.blockSignals(False)
        self.update_all_lights_visibility(light_table)

    def get_layer_collection_recursive(self, layer_collection, name):
        """
        Recursively find a layer collection by name within the view layer hierarchy
        """
        if layer_collection.name == name:
            return layer_collection
        for child in layer_collection.children:
            found = self.get_layer_collection_recursive(child, name)
            if found:
                return found
        return

    def update_all_lights_visibility(self, light_table: object, *args):
        """
        Updates the visibility of all collections's lights based (per collection exclusion),
        on the states of the 'Mute' and 'Solo' checkboxes.
        """
        # Capture UI states immediately on the UI thread before switching to the Blender thread
        target_vl_name = self.ui.combo_view_layer.currentText()
        visibility_data = []
        soloed_row = -1

        for i in range(light_table.rowCount()):
            name_item = light_table.item(i, 0)
            mute_widget = light_table.cellWidget(i, 1)
            solo_widget = light_table.cellWidget(i, 2)

            if name_item and mute_widget and solo_widget:
                light_name = name_item.text()
                mute_cb = mute_widget.findChild(QCheckBox)
                solo_cb = solo_widget.findChild(QCheckBox)

                # Store visibility and solo states
                is_checked = mute_cb.isChecked() if mute_cb else True
                is_soloed = solo_cb.isChecked() if solo_cb else False

                if is_soloed:
                    soloed_row = i

                visibility_data.append((i, light_name, is_checked))

        def _do_update():
            try:
                scene = bpy.context.scene
                # Find the view layer object corresponding to the UI selection
                view_layer = scene.view_layers.get(target_vl_name)
                if not view_layer:
                    view_layer = bpy.context.view_layer  # Fallback

                for i, light_name, is_checked in visibility_data:
                    # Recursively find the specific collection in the target view layer
                    collection = self.get_layer_collection_recursive(view_layer.layer_collection, "C" + light_name)
                    if not collection:
                        continue

                    # Visibility priority: Solo > Mute
                    should_be_visible = (i == soloed_row) if soloed_row != -1 else is_checked

                    try:
                        # Exclude collection in the targeted view layer
                        collection.exclude = not should_be_visible
                    except Exception:
                        pass

                # Redraw viewports to show the update
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
            except Exception:
                pass
            return

        # Execute the update on Blender's main thread
        try:
            bpy.app.timers.register(_do_update, first_interval=0.01)
        except Exception:
            _do_update()

    def set_color(self, light: bpy, color_button: QPushButton):
        """
        Opens a color picker dialog to set the light's color and updates the button's background color
        """
        if not light.data.color:
            return
        # GET THE ACTUAL LIGHT COLOR
        linear_color = light.data.color
        try:
            # OPEN COLOR PICKER DIALOG
            color_dialog = QColorDialog(currentColor=QColor(
                linear_color[0]*255, linear_color[1]*255, linear_color[2]*255), parent=self.ui)
        except ReferenceError:
            self.info_timer("Cannot change color. The light may have been deleted.")

        if color_dialog.exec() == QColorDialog.Accepted:
            new_color = color_dialog.selectedColor()
            r, g, b = new_color.redF(), new_color.greenF(), new_color.blueF()
            light.data.color = (r, g, b)  # SET THE NEW COLOR TO THE LIGHT
            self.set_button_color(light, color_button)

    def set_button_color(self, light: bpy.types.Object, color_button: QPushButton, color: tuple = None):
        """
        Sets the background color of a QPushButton to match the light's color.
        """
        if not light:
            return

        linear_color = light.data.color
        r = int(linear_color[0] * 255)
        g = int(linear_color[1] * 255)
        b = int(linear_color[2] * 255)
        color_button.setStyleSheet(f"background-color: rgba({r},{g},{b},1)")

    def search_light(self, *args: str | object):
        """
        Filters the visibility of rows in the table based on a search string.

        Args:
            args[0] (str): The text to search for in the light names.
            args[1] (QTableWidget): The table whose rows will be filtered.
        """
        search_text = args[0]
        if not search_text:
            self.refresh(args[1])
            return
        if search_text:
            for row in range(args[1].rowCount()):
                researsh_light = args[1].item(row, 0).text()
                if search_text in researsh_light.lower():
                    args[1].showRow(row)
                else:
                    args[1].hideRow(row)

    def view_layers_change(self, combo_box: object):
        """
        Updates the active View Layer in Blender based on the UI selection
        and refreshes the light table.
        """
        if not combo_box:
            return

        layer_name = combo_box.currentText()
        scene = getattr(bpy.context, 'scene', None)
        if scene is None:
            return

        # Schedule the view-layer change on Blender's main thread to avoid context issues
        def _apply_view_layer():
            try:
                layer = scene.view_layers.get(layer_name)
                if layer is None:
                    return

                window = getattr(bpy.context, 'window', None)
                try:
                    if window is not None:
                        window.view_layer = layer
                    else:
                        scene.view_layers.active = layer
                except Exception:
                    # Try the scene assignment as a fallback
                    try:
                        scene.view_layers.active = layer
                    except Exception:
                        pass

                # Force UI redraw if possible
                window = getattr(bpy.context, 'window', None)
                if window is not None and getattr(window, 'screen', None) is not None:
                    for area in window.screen.areas:
                        try:
                            area.tag_redraw()
                        except Exception:
                            pass

                # Refresh the UI (runs in Blender main thread via timer)
                try:
                    self.refresh(self.ui.light_table)
                except Exception:
                    pass

            except Exception:
                pass
            return None  # unregister the timer after running once

        try:
            bpy.app.timers.register(_apply_view_layer, first_interval=0.0)
        except Exception:
            # If timers aren't available, try immediate application (best-effort)
            _apply_view_layer()

    def info_timer(self, text: str, duration_ms: int = 3500):
        """
        Displays a message in the UI's info label for a specified duration.

        Args:
            text (str): The message to display.
            duration_ms (int, optional): How long to display the message in milliseconds. Defaults to 3500.
        """
        self.ui.info_text.setText(text)
        QTimer.singleShot(duration_ms, lambda: self.ui.info_text.setText(""))
