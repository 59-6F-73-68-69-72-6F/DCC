import bpy
import os

class LightManagerPresenter:
    """
    Presenter class that coordinates the LightManagerUI (View) and
    BlenderLightLogic (Model). It acts as the event glue layer and
    manages depsgraph post-update timers safely.
    """

    def __init__(self, view, model, icons_dir):
        self.view = view
        self.model = model
        self.icons_dir = icons_dir
        self.script_jobs = []

        # Connect view signals to coordinator actions
        self.view.signal_light_created.connect(self.on_light_created)
        self.view.signal_light_renamed.connect(self.on_light_renamed)
        self.view.signal_light_deleted.connect(self.on_light_deleted)
        self.view.signal_refresh_requested.connect(self.refresh)
        self.view.signal_view_layer_changed.connect(self.on_view_layer_changed)
        self.view.signal_table_selection_changed.connect(self.on_selection_changed)
        self.view.signal_attribute_changed.connect(self.on_attribute_changed)
        self.view.signal_color_changed.connect(self.on_color_changed)

        # Register a single post-update depsgraph handler
        self.register_handlers()
        
        # Initial refresh to populate UI
        self.refresh()

    def register_handlers(self):
        self.unregister_handlers()
        
        def on_depsgraph_update(scene, depsgraph):
            # Check if any light object or light data properties were modified
            # Ignore collection visibility changes to prevent table reordering
            is_light_updated = False
            for update in depsgraph.updates:
                try:
                    update_id = update.id
                    # Only refresh for Light data and Object changes, NOT for Collection changes
                    if isinstance(update_id, bpy.types.Light):
                        is_light_updated = True
                        break
                    elif isinstance(update_id, bpy.types.Object) and update_id.type == 'LIGHT':
                        is_light_updated = True
                        break
                    # Ignore collection updates (visibility changes)
                    elif isinstance(update_id, bpy.types.Collection):
                        continue
                except Exception:
                    pass
            
            if is_light_updated:
                # Schedule refresh on Blender's main thread via timer to ensure thread safety
                try:
                    bpy.app.timers.register(self.refresh, first_interval=0.0)
                except Exception:
                    pass

        bpy.app.handlers.depsgraph_update_post.append(on_depsgraph_update)
        self.script_jobs.append(on_depsgraph_update)

    def unregister_handlers(self):
        for job in self.script_jobs:
            if job in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.remove(job)
        self.script_jobs.clear()

    def refresh(self):
        """Refreshes the view layers and table population from Blender data."""
        # 1. Fetch layers and active layer from Model
        layers = self.model.get_view_layers()
        active_layer = self.model.get_active_view_layer()
        
        # 2. Update view layers dropdown in UI (View)
        self.view.update_view_layers(layers, active_layer)
        
        # 3. Fetch lights status from Model
        lights = self.model.get_lights(active_layer)
        
        # 4. Populate UI Table (View)
        self.view.populate_table(lights, self.icons_dir)
        return None  # Return None if run by a timer to prevent rescheduling

    def on_light_created(self, name, light_type):
        """Handles the creation of a new light based on user input from the UI."""
        try:
            new_name = self.model.create_light(name, light_type)
            self.view.show_info_message(f"Light '{new_name}' created successfully.")
            self.refresh()
        except Exception as e:
            self.view.show_info_message(f"Error: {e}")

    def on_light_renamed(self, old_name, new_name):
        """Handles the renaming of a light based on user input from the UI."""
        try:
            renamed_name = self.model.rename_light(old_name, new_name)
            self.view.show_info_message(f"Light '{old_name}' renamed to '{renamed_name}'.")
            self.refresh()
        except Exception as e:
            self.view.show_info_message(f"Error: {e}")

    def on_light_deleted(self, name):
        """Handles the deletion of a light based on user input from the UI."""
        try:
            self.model.delete_light(name)
            self.view.show_info_message(f"Light '{name}' deleted.")
            self.refresh()
        except Exception as e:
            self.view.show_info_message(f"Error: {e}")

    def on_view_layer_changed(self, layer_name):
        """Handles the change of active view layer based on user selection from the UI."""
        try:
            self.model.set_active_view_layer(layer_name)
            self.refresh()
        except Exception as e:
            self.view.show_info_message(f"Error changing layer: {e}")

    def on_selection_changed(self, light_name):
        """Handles the change of selected light based on user interaction in the UI."""
        if light_name:
            active_layer = self.model.get_active_view_layer()
            self.model.select_light(light_name, active_layer)

    def on_attribute_changed(self, light_name, attr_name, value):
        """Handles the change of a light attribute (visibility, solo, or other) based on user interaction in the UI."""
        try:
            active_layer = self.model.get_active_view_layer()
            
            if attr_name == "visibility":
                self.model.set_light_visibility(light_name, value, active_layer)
            elif attr_name == "solo":
                lights = self.model.get_lights(active_layer)
                all_names = [l.name for l in lights]
                self.model.set_light_solo(light_name, value, active_layer, all_names)
            else:
                self.model.set_light_attribute(light_name, attr_name, value)
                # For attributes that may affect the light's presence in the current layer (like type changes), we can choose to refresh immediately.
                # self.refresh()
        except Exception as e:
            self.view.show_info_message(f"Error updating attribute: {e}")

    def on_color_changed(self, light_name, color_tuple):
        try:
            self.model.set_light_color(light_name, color_tuple)
            self.refresh()
        except Exception as e:
            self.view.show_info_message(f"Error updating color: {e}")

    def cleanup(self):
        """Cleans up unregistered handlers to prevent memory leaks."""
        self.unregister_handlers()
