"""
Entry point and add-on bootstrap for the Blender Light Manager.

This module defines the Blender add-on metadata (bl_info) and wires up the
MVC architecture on registration. It creates the Model (LightManagerLogic)
and Controller (LightManagerController), then delegates UI registration to
the View layer (light_manager_ui).
"""


bl_info = {
    "name": "Light Manager",
    "author": "Rudy Leti",
    "version": (3, 7, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Light Manager",
    "description": "Native MVP tool to manage scene lights.",
    "category": "Lighting",
}

import sys
import os

directory = os.path.dirname(os.path.abspath(__file__))
if directory not in sys.path:
    sys.path.append(directory)



from . import light_manager_ui as lmui
from . import light_manager_controller as lmc
from . import light_manager_logic as lml


controller_instance: lmc.LightManagerController | None = None


def register():
    """
    Register the Light Manager add-on with Blender.

    Creates the Model and Controller instances, registers all UI classes and
    custom properties, and stores the presenter as a module-level singleton.
    """
    global controller_instance
    lmui.register()
    logic = lml.LightManagerLogic()
    controller_instance = lmc.LightManagerController(logic)


def unregister():
    """
    Unregister the Light Manager add-on from Blender.

    Cleans up the presenter (removes Blender event handlers, nullifies UI
    hooks) and unregisters all UI classes and custom properties.
    """
    global controller_instance
    if controller_instance:
        controller_instance.cleanup()
        controller_instance = None
    lmui.unregister()


if __name__ == "__main__":
    register()