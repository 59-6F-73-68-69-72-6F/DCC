##########################
# This script creates a menu for the LightBridge tool in Nuke.
##########################

import nuke
import os

# Get the directory where this menu.py file is located.
tool_root = os.path.dirname(__file__)

# Add the tool's root directory to Nuke's plugin path.
nuke.pluginAddPath(tool_root)

import init

# Create a toolbar menu instance.
toolbar = nuke.menu("Nuke")
lb_menu = toolbar.addMenu("Light Bridge")
lb_menu.addCommand("Create LightMixer Node", "init.create_light_mixer_setup()")