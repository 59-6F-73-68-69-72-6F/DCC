"""
Light Link Savior Add-on entry point for Blender.
It registers the UI elements and operators.
"""

bl_info = {
    "name": "Light Link Savior",
    "author": "Rudy Leti",
    "version": (1, 0, 1),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Lighting",
    "description": "Save and restore the light linking state of scene lights",
    "category": "Lighting",
}


from . import ll_savior_ui


def register():
    ll_savior_ui.register()

def unregister():
    ll_savior_ui.unregister()
