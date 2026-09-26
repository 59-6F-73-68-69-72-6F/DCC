"""
Playblast add-on entry point.

Provides a viewport playblast tool that renders PNG image sequences to a
user-specified folder. UI lives in the 3D Viewport sidebar under the
"Animation" tab. Delegates registration to playblast_ui.
"""

import sys
import os

import bpy


bl_info = {
    "name": "Playblast",
    "author": "Rudy Leti",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Animation",
    "description": "Quick viewport playblast renderer — saves PNG image sequences.",
    "category": "Animation",
}


directory = os.path.dirname(os.path.abspath(__file__))
if directory not in sys.path:
    sys.path.append(directory)


def register():
    """Register the Playblast add-on with Blender."""
    from . import playblast_ui
    playblast_ui.register()


def unregister():
    """Unregister the Playblast add-on and clean up its sys.path entry."""
    from . import playblast_ui
    playblast_ui.unregister()
    if directory in sys.path:
        sys.path.remove(directory)
