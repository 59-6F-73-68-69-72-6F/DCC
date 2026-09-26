###############################
# Blender Light Manager UI (v2.0)
# This module defines the LightManagerUI class, a QWidget that provides a user interface
# for managing lights in Blender. It includes a table for displaying light attributes,
# controls for creating, renaming, and deleting lights, and signals for communicating
# with the Presenter.
###############################

import os
from PySide6.QtCore import Qt, QSize, Signal, QTimer
from PySide6.QtGui import QFont, QWheelEvent, QPixmap, QColor
from PySide6.QtWidgets import (QWidget, QTableWidget, QComboBox, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout, QHBoxLayout, QAbstractItemView, QGroupBox, QApplication, 
                               QMessageBox, QScrollArea, QTableWidgetItem, QCheckBox, QColorDialog)
from models.light_state import LightState

TABLE_HEADER = ["Name", "V", "S", "Type", "Color", "Exposure",
                "Use Temp.", "Temperature", "Radius", "Shadow", "LightGroup"]
HEADER_SIZE = [150, 15, 15, 40, 55, 65, 60, 80, 60, 20, 60]
FONT = "Nimbus Sans, Bold"
COLOR = "#c7c7c5"
FONT_WEIGHT = 400
FONT_SIZE = 9


class LightManagerUI(QWidget):
    """
    QWidget class that provides a pure user interface for managing lights.
    This class handles the creation, layout, and display of light-related data
    within a QTableWidget, communicating via Signals and Dataclasses.
    """

    # Abstract interface signals
    signal_light_created = Signal(str, str)         # (light_name, light_type)
    signal_light_renamed = Signal(str, str)         # (old_name, new_name)
    signal_light_deleted = Signal(str)              # (light_name)
    signal_refresh_requested = Signal()
    signal_view_layer_changed = Signal(str)         # (layer_name)
    signal_table_selection_changed = Signal(str)    # (light_name)
    signal_attribute_changed = Signal(str, str, object)  # (light_name, attr_name, new_value)
    signal_color_changed = Signal(str, tuple)       # (light_name, (r, g, b))

    LIGHT_TYPES = ["POINT", "SUN", "SPOT", "AREA"]

    def __init__(self):
        super().__init__()
        self.build_ui()
        self.connect_signals()

    # SET WINDOW --------------------------------------------
    def build_ui(self):
        """Constructs and lays out all the UI widgets."""
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowTitle("Blender Light Manager")
        self.setMinimumSize(800, 600)
        self.setMaximumSize(800, 690)

        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignCenter)

        self.scroll_area = QScrollArea()

        title_light_name = self.label_text("Light Name:")
        self.entry_light_name = self.bar_text("Name your light", 160)

        self.info_text = self.label_text("Light Manager initialized")
        self.info_text.setFont(QFont(FONT, 9))

        title_ligh_search = self.label_text("Search by name:")
        self.entry_ligh_search = self.bar_text("Type light name to search", 685)

        title_light_type = self.label_text("Light Type:")
        self.combo_light_type = self.combo_list(self.LIGHT_TYPES)

        self.button_create_light = self.push_button("Create Light")
        self.button_create_light.setStyleSheet("background-color: #2a9d8f; color: black;")

        self.button_refresh = self.push_button("Refresh")
        self.button_refresh.setStyleSheet("background-color: #8ecae6; color: black;")

        title_view_layer = self.label_text("View Layer:")
        self.combo_view_layer = self.combo_list([])

        self.button_rename = self.push_button("Rename Light")
        self.button_rename.setStyleSheet("background-color: #D17D98; color: white;")

        self.button_delete = self.push_button("Delete")
        self.button_delete.setStyleSheet("background-color: #c1121f; color: white;")

        self.light_table = QTableWidget()
        self.light_table.setFont(QFont(FONT, FONT_SIZE))
        self.light_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.light_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.light_table.setStyleSheet("QTableWidget { background-color: #222b33; color: white; }")
        
        for y in range(len(TABLE_HEADER)):
            self.light_table.setColumnCount(y + 1)
            self.light_table.setHorizontalHeaderLabels(TABLE_HEADER)
            header = self.light_table.horizontalHeader()
            header.resizeSection(y, HEADER_SIZE[y])
            header.setStyleSheet(f"QHeaderView::section {{font-family: {FONT}; font-size: {10}px}}")

        group_box_01 = QGroupBox()
        group_box_02 = QGroupBox()
        group_box_01.setStyleSheet(
            "QGroupBox { border: 1px solid grey; border-radius: 3px; padding: 20px; padding-top: 1px; padding-bottom: 2px; }")
        group_box_02.setStyleSheet(
            "QGroupBox { border: 1px solid grey; border-radius: 3px; padding: 3px; }")
        
        layoutV_01 = QVBoxLayout()
        layoutV_02 = QVBoxLayout()
        layoutV_01_01 = QVBoxLayout()
        layoutH_02 = QHBoxLayout()
        layoutH_03 = QHBoxLayout()
        layoutH_04 = QHBoxLayout()

        layoutH_02.addWidget(title_light_name)
        layoutH_02.addWidget(self.entry_light_name)
        layoutH_02.addWidget(title_light_type)
        layoutH_02.addWidget(self.combo_light_type)
        layoutH_03.addWidget(self.button_create_light)
        layoutH_03.addWidget(self.button_rename)
        layoutH_04.addWidget(title_view_layer)
        layoutH_04.addWidget(self.combo_view_layer)
        
        layoutV_02.addWidget(title_ligh_search)
        layoutV_02.addWidget(self.entry_ligh_search)
        layoutV_02.addWidget(self.light_table)
        layoutV_02.addWidget(self.button_refresh)
        layoutV_02.addWidget(self.button_delete)

        layoutV_01.addLayout(layoutV_01_01)
        layoutV_01.addLayout(layoutH_02)
        layoutV_01.addLayout(layoutH_03)
        layoutV_02.addLayout(layoutH_04)

        group_box_01.setLayout(layoutV_01)
        group_box_02.setLayout(layoutV_02)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.addWidget(self.logo)
        self.main_layout.addWidget(group_box_01)
        self.main_layout.addWidget(group_box_02)
        self.main_layout.addWidget(self.info_text)

        self.main_layout.setAlignment(Qt.AlignCenter)
        self.setLayout(self.main_layout)

    # GENERIC WIDGETS --------------------------------------------
    def label_text(self, text: str) -> QLabel:
        """Creates a QLabel with consistent styling."""
        label = QLabel(text=text)
        label.setFont(QFont(FONT, FONT_SIZE))
        label.setStyleSheet(f"color:{COLOR}")
        return label

    def bar_text(self, text: str = "", length=20) -> QLineEdit:
        """Creates a QLineEdit with consistent styling."""
        line_edit = QLineEdit(placeholderText=text)
        line_edit.setFixedSize(QSize(length, 25))
        line_edit.setFont(QFont(FONT, FONT_SIZE))
        return line_edit

    def combo_list(self, light_list: list) -> QComboBox:
        """Creates a QComboBox with consistent styling and populates it with sorted items."""
        combo_box = QComboBox()
        for light in sorted(light_list):
            combo_box.addItem(light)
            combo_box.setFont(QFont(FONT, FONT_SIZE))
        return combo_box

    def push_button(self, text: str) -> QPushButton:
        """Creates a QPushButton with consistent styling."""
        button = QPushButton(text)
        button.setFont(QFont(FONT, FONT_SIZE))
        return button

    # SIGNALS --------------------------------------------
    def connect_signals(self):
        """Connects UI events to their corresponding emitter methods."""
        self.button_create_light.clicked.connect(self.emit_light_created)
        self.button_rename.clicked.connect(self.emit_light_renamed)
        self.button_refresh.clicked.connect(self.emit_refresh)
        self.button_delete.clicked.connect(self.emit_light_deleted)
        self.light_table.itemSelectionChanged.connect(self.emit_table_selection)
        self.entry_ligh_search.textChanged.connect(self.on_search_text_changed)
        self.combo_view_layer.currentTextChanged.connect(self.emit_view_layers)

    # EMITTERS & EVENT HANDLERS -------------------------
    def emit_light_created(self):
        """Emits a signal to create a new light with the specified name and type."""
        light_name = self.entry_light_name.text()
        light_type = self.combo_light_type.currentText()
        self.signal_light_created.emit(light_name, light_type)
        self.entry_light_name.clear()

    def emit_light_renamed(self):
        """Emits a signal to rename an existing light."""
        if self.light_table.selectedItems():
            old_name = self.light_table.currentItem().text()
            new_name = self.entry_light_name.text()
            self.signal_light_renamed.emit(old_name, new_name)
            self.entry_light_name.clear()

    def emit_light_deleted(self):
        """Emits a signal to delete an existing light."""
        if self.light_table.selectedItems():
            selection = self.light_table.currentItem().text()
            btn_question = QMessageBox.question(self, "Question", f"Are you sure you want to delete {selection} ?")
            if btn_question == QMessageBox.Yes:
                self.signal_light_deleted.emit(selection)

    def on_search_text_changed(self, search_text: str):
        """Filter rows locally in the UI without querying the logic database."""
        search_text = search_text.lower().strip()
        for row in range(self.light_table.rowCount()):
            item = self.light_table.item(row, 0)
            if item:
                light_name = item.text().lower()
                self.light_table.setRowHidden(row, search_text not in light_name)

    def emit_table_selection(self):
        """Emits a signal with the name of the currently selected light, or an empty string if no selection."""
        selected_items = self.light_table.selectedItems()
        if selected_items:
            # First item in row is the light name
            row = selected_items[0].row()
            name_item = self.light_table.item(row, 0)
            if name_item:
                self.signal_table_selection_changed.emit(name_item.text())
        else:
            self.signal_table_selection_changed.emit("")

    def emit_refresh(self):
        """Emits a signal to refresh the UI, typically after changes in the Model."""
        self.signal_refresh_requested.emit()

    def emit_view_layers(self, layer_name: str):
        """Emits a signal when the active view layer is changed via the combo box."""
        if layer_name:
            self.signal_view_layer_changed.emit(layer_name)

    def show_info_message(self, message: str, duration_ms: int = 3500):
        """Displays a temporary informational message in the UI."""
        self.info_text.setText(message)
        QTimer.singleShot(duration_ms, lambda: self.info_text.setText(""))

    # POPULATING DATA -----------------------------------
    def update_view_layers(self, layers: list[str], active_layer: str):
        """Updates the view layers dropdown with the current layers and sets the active layer."""
        self.combo_view_layer.blockSignals(True)
        self.combo_view_layer.clear()
        self.combo_view_layer.addItems(layers)
        if active_layer in layers:
            self.combo_view_layer.setCurrentText(active_layer)
        self.combo_view_layer.blockSignals(False)

    def populate_table(self, lights: list[LightState], icons_dir: str):
        """Populate the table using clean LightState models."""
        
        # Preserve scroll position before clearing the table to prevent jumpiness during refreshes
        v_scroll_bar = self.light_table.verticalScrollBar()
        h_scroll_bar = self.light_table.horizontalScrollBar()
        current_vpos = v_scroll_bar.value()
        current_hpos = h_scroll_bar.value()
        max_v_range = v_scroll_bar.maximum()

        self.light_table.setRowCount(0)

        for row, light in enumerate(lights):
            self.light_table.insertRow(row)

            # 0. Name
            name_item = QTableWidgetItem(light.name)
            name_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.light_table.setItem(row, 0, name_item)

            # 1. V (Mute Checkbox)
            mute_widget = QWidget()
            mute_checkbox = QCheckBox()
            mute_checkbox.setStyleSheet("QCheckBox::indicator:unchecked { background-color: #f94144 }")
            mute_checkbox.setChecked(light.is_visible)
            mute_checkbox.setProperty("light_name", light.name)
            mute_checkbox.setProperty("attribute_name", "visibility")
            mute_checkbox.stateChanged.connect(self._on_checkbox_changed)
            mute_layout = QHBoxLayout(mute_widget)
            mute_layout.addWidget(mute_checkbox)
            mute_layout.setAlignment(Qt.AlignCenter)
            mute_layout.setContentsMargins(0, 0, 0, 0)
            self.light_table.setCellWidget(row, 1, mute_widget)

            # 2. S (Solo Checkbox)
            solo_widget = QWidget()
            solo_checkbox = QCheckBox()
            solo_checkbox.setStyleSheet("QCheckBox::indicator:checked { background-color: #adb5bd }")
            solo_checkbox.setChecked(light.is_soloed)
            solo_checkbox.setProperty("light_name", light.name)
            solo_checkbox.setProperty("attribute_name", "solo")
            solo_checkbox.stateChanged.connect(self._on_checkbox_changed)
            solo_layout = QHBoxLayout(solo_widget)
            solo_layout.addWidget(solo_checkbox)
            solo_layout.setAlignment(Qt.AlignCenter)
            solo_layout.setContentsMargins(0, 0, 0, 0)
            self.light_table.setCellWidget(row, 2, solo_widget)

            # 3. Type Icon
            icon_label = QLabel()
            icon_path = os.path.join(icons_dir, f"{light.type}.png")
            if os.path.exists(icon_path):
                icon_label.setPixmap(QPixmap(icon_path))
            icon_label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.light_table.setCellWidget(row, 3, icon_label)

            # 4. Color Swatch
            color_widget = QWidget()
            color_button = QPushButton()
            color_button.setFixedSize(56, 26)
            r, g, b = int(light.color[0]*255), int(light.color[1]*255), int(light.color[2]*255)
            color_button.setStyleSheet(f"background-color: rgba({r},{g},{b},1)")
            color_button.setProperty("light_name", light.name)
            color_button.setProperty("current_color", light.color)
            color_button.clicked.connect(self._on_color_button_clicked)
            color_layout = QHBoxLayout(color_widget)
            color_layout.addWidget(color_button)
            color_layout.setAlignment(Qt.AlignCenter)
            color_layout.setContentsMargins(0, 0, 0, 0)
            self.light_table.setCellWidget(row, 4, color_widget)

            # 5. Exposure
            exp_widget = QWidget()
            exp_input = CustomLineEditNum()
            exp_input.setFixedSize(65, 29)
            exp_input.setAlignment(Qt.AlignCenter)
            exp_input.setText(f"{light.exposure:.3f}")
            exp_input.setProperty("light_name", light.name)
            exp_input.setProperty("attribute_name", "exposure")
            exp_input.editingFinished.connect(self._on_numeric_edited)
            exp_layout = QHBoxLayout(exp_widget)
            exp_layout.addWidget(exp_input)
            exp_layout.setAlignment(Qt.AlignCenter)
            exp_layout.setContentsMargins(0, 0, 0, 0)
            self.light_table.setCellWidget(row, 5, exp_widget)

            # 6. Use Temp Checkbox
            use_temp_widget = QWidget()
            use_temp_checkbox = QCheckBox()
            use_temp_checkbox.setChecked(light.use_temperature)
            use_temp_checkbox.setProperty("light_name", light.name)
            use_temp_checkbox.setProperty("attribute_name", "use_temperature")
            use_temp_checkbox.stateChanged.connect(self._on_checkbox_changed)
            use_temp_layout = QHBoxLayout(use_temp_widget)
            use_temp_layout.addWidget(use_temp_checkbox)
            use_temp_layout.setAlignment(Qt.AlignCenter)
            use_temp_layout.setContentsMargins(0, 0, 0, 0)
            self.light_table.setCellWidget(row, 6, use_temp_widget)

            # 7. Temperature
            if light.use_temperature:
                temp_widget = QWidget()
                temp_input = CustomLineEditNum()
                temp_input.setFixedSize(65, 29)
                temp_input.setAlignment(Qt.AlignCenter)
                temp_input.setText(f"{light.temperature:.3f}")
                temp_input.setProperty("light_name", light.name)
                temp_input.setProperty("attribute_name", "temperature")
                temp_input.editingFinished.connect(self._on_numeric_edited)
                temp_layout = QHBoxLayout(temp_widget)
                temp_layout.addWidget(temp_input)
                temp_layout.setAlignment(Qt.AlignCenter)
                temp_layout.setContentsMargins(0, 0, 0, 0)
                self.light_table.setCellWidget(row, 7, temp_widget)
            else:
                na_label = QLabel("N/A")
                na_label.setAlignment(Qt.AlignCenter)
                self.light_table.setCellWidget(row, 7, na_label)

            # 8. Radius
            if light.type in ("SUN", "AREA"):
                na_label = QLabel("N/A")
                na_label.setAlignment(Qt.AlignCenter)
                self.light_table.setCellWidget(row, 8, na_label)
            else:
                rad_widget = QWidget()
                rad_input = CustomLineEditNum()
                rad_input.setFixedSize(65, 29)
                rad_input.setAlignment(Qt.AlignCenter)
                rad_input.setText(f"{light.radius:.3f}")
                rad_input.setProperty("light_name", light.name)
                rad_input.setProperty("attribute_name", "shadow_soft_size")
                rad_input.editingFinished.connect(self._on_numeric_edited)
                rad_layout = QHBoxLayout(rad_widget)
                rad_layout.addWidget(rad_input)
                rad_layout.setAlignment(Qt.AlignCenter)
                rad_layout.setContentsMargins(0, 0, 0, 0)
                self.light_table.setCellWidget(row, 8, rad_widget)

            # 9. Shadow
            shadow_widget = QWidget()
            shadow_checkbox = QCheckBox()
            shadow_checkbox.setChecked(light.use_shadow)
            shadow_checkbox.setProperty("light_name", light.name)
            shadow_checkbox.setProperty("attribute_name", "use_shadow")
            shadow_checkbox.stateChanged.connect(self._on_checkbox_changed)
            shadow_layout = QHBoxLayout(shadow_widget)
            shadow_layout.addWidget(shadow_checkbox)
            shadow_layout.setAlignment(Qt.AlignCenter)
            shadow_layout.setContentsMargins(0, 0, 0, 0)
            self.light_table.setCellWidget(row, 9, shadow_widget)

            # 10. LightGroup
            lg_widget = QWidget()
            lg_input = QLineEdit()
            lg_input.setFixedSize(59, 29)
            lg_input.setAlignment(Qt.AlignCenter)
            lg_input.setPlaceholderText("AOV")
            lg_input.setText(light.lightgroup)
            lg_input.setProperty("light_name", light.name)
            lg_input.setProperty("attribute_name", "lightgroup")
            lg_input.returnPressed.connect(self._on_text_edited)
            lg_layout = QHBoxLayout(lg_widget)
            lg_layout.addWidget(lg_input)
            lg_layout.setAlignment(Qt.AlignCenter)
            lg_layout.setContentsMargins(0, 0, 0, 0)
            self.light_table.setCellWidget(row, 10, lg_widget)

        # Restore scroll position after repopulating the table, adjusting for any changes in maximum range
        new_vmax_range = v_scroll_bar.maximum()
        if max_v_range - current_vpos <= 1:
            v_scroll_bar.setValue(new_vmax_range)
        else:
            v_scroll_bar.setValue(current_vpos)
        h_scroll_bar.setValue(current_hpos)

    # VIEW CALLBACKS ------------------------------------
    def _on_checkbox_changed(self, state):
        """
        Generic handler for all checkboxes in the table,
        using properties to identify which light and attribute changed.
        """
        sender = self.sender()
        light_name = sender.property("light_name")
        attr_name = sender.property("attribute_name")
        checked = bool(state)
        self.signal_attribute_changed.emit(light_name, attr_name, checked)

    def _on_numeric_edited(self):
        """
        Generic handler for all numeric QLineEdits in the table,
        using properties to identify which light and attribute changed.
        """
        sender = self.sender()
        light_name = sender.property("light_name")
        attr_name = sender.property("attribute_name")
        try:
            val = float(sender.text())
            self.signal_attribute_changed.emit(light_name, attr_name, val)
        except ValueError:
            pass

    def _on_text_edited(self):
        """
        Generic handler for all text QLineEdits in the table,
        using properties to identify which light and attribute changed.
        """
        sender = self.sender()
        light_name = sender.property("light_name")
        attr_name = sender.property("attribute_name")
        val = sender.text().strip()
        self.signal_attribute_changed.emit(light_name, attr_name, val)

    def _on_color_button_clicked(self):
        """
        Handler for when a color swatch button is clicked.
        Opens a QColorDialog and emits the new color if changed.
        """
        sender = self.sender()
        light_name = sender.property("light_name")
        current_color = sender.property("current_color")

        qcolor = QColor(int(current_color[0]*255), int(current_color[1]*255), int(current_color[2]*255))
        color_dialog = QColorDialog(currentColor=qcolor, parent=self)
        if color_dialog.exec() == QColorDialog.Accepted:
            new_color = color_dialog.selectedColor()
            r, g, b = new_color.redF(), new_color.greenF(), new_color.blueF()
            self.signal_color_changed.emit(light_name, (r, g, b))


class CustomLineEditNum(QLineEdit):
    """
    A custom QLineEdit that allows numerical values to be adjusted using the mouse wheel.
    Supports Ctrl/Shift modifiers for fine or coarse scrubbing.
    """

    def __init__(self):
        super().__init__()
        self.setText("0.000")

    def wheelEvent(self, event: QWheelEvent):
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier:
            step = 0.01
        elif modifiers == Qt.ShiftModifier:
            step = 0.001
        else:
            super().wheelEvent(event)
            return

        try:
            current_value = float(self.text())
            delta = event.angleDelta().y() / 120
            new_value = current_value + delta * step
            self.setText(f"{new_value:.3f}")
            self.editingFinished.emit()
        except ValueError:
            pass
