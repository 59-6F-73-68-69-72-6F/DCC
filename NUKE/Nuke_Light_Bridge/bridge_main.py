###################################
# This script contains the main logic for the Maya Light Bridge tool.
###################################

import os

from Qt.QtGui import QPixmap

import bridge_ui as bui
import bridge_maya_logic as bml

ui = None


def getMayaMainWindow():
    """ Initializes and launches the Light Manager UI. """
    global ui
    ui = bui.BridgeUI()

    # LOAD LOGO IMAGE
    # GET THE PATH OF THE CURRENT SCRIPT
    script_path = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(script_path, "img", "logo.png")
    img = QPixmap(logo_path)
    ui.logo.setPixmap(img)

    # SET SIGNALS
    ui.signal_path.connect(bml.lights_data_tranfert)

    ui.show()


getMayaMainWindow()
