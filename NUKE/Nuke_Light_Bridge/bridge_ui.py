###################################
# This script contains the UI for the Light Bridge tool.
###################################

import os

from Qt.QtCore import Qt, Signal
from Qt.QtGui import QFont
from Qt.QtWidgets import QWidget, QLabel, QFileDialog, QPushButton, QVBoxLayout, QMessageBox


FONT = "Nimbus Sans, Bold"
FONT_WEIGHT = 600
FONT_SIZE = 11


class BridgeUI(QWidget):
    """ Build the UI for the Light Bridge tool. """

    signal_path = Signal(str)  # (path)

    def __init__(self):
        """ Sets up the UI elements and connects signals to slots. """

        super().__init__()
        self.build_ui()
        self.connect_signals()

    # SET WINDOW --------------------------------------------
    def build_ui(self):
        """ Setup the UI elements."""

        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)  # KEEP WINDOW ON TOP
        self.setWindowTitle("Light Bridge")
        self.setMinimumSize(300, 100)
        self.setMaximumSize(300, 100)

        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignCenter)

        self.open_file_button = self.push_button("Open File")

        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.logo)
        self.main_layout.addWidget(self.open_file_button)

        self.setLayout(self.main_layout)

    # GENERIC WIDGETS --------------------------------------------
    def push_button(self, text: str) -> QPushButton:
        """Creates a QPushButton with a standardized font.
        Args:
            text (str): The text to display on the button.
        """
        button = QPushButton(text)
        button.setFont(QFont(FONT, FONT_SIZE))
        return button

    def open_file_dialog(self) -> str | None:
        """ Opens a file dialog and handles the selected file. """

        try:
            # QFileDialog.getOpenFileName returns a tuple (filename, selected_filter)
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select a file to open", os.path.expanduser("~"), "JSON Files (*.json)")

            if file_path:
                return file_path
            else:
                pass

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred:\n{str(e)}")

    # SIGNALS --------------------------------------------
    def connect_signals(self):
        """ connect all signals to their respective slots."""
        self.open_file_button.clicked.connect(self.emit_path)

    # EMITTERS --------------------------------------
    def emit_path(self):
        """ Emits the selected file path through the signal_path signal. """
        path = self.open_file_dialog()
        self.signal_path.emit(path)
