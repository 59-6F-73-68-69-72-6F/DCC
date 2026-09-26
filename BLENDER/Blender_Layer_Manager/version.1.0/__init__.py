"""
Entry point and add-on bootstrap for the Blender Layer Manager.

This module defines the Blender add-on metadata (bl_info) and wires up the
MVP architecture on registration. It creates the Model (LayerManagerLogic)
and Controller (LayerManagerController), then delegates UI registration to
the View layer (layer_manager_ui).
"""

bl_info = {
    "name": "Layer Manager",
    "author": "Rudy Leti",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Layer Manager",
    "description": "Native MVP tool to manage Layers.",
    "category": "Lighting",
}

import os
import sys

import bpy

directory = os.path.dirname(os.path.abspath(__file__))
if directory not in sys.path:
    sys.path.append(directory)

from . import layer_manager_ui as lmui
from . import layer_manager_controller as lmc
from . import layer_manager_logic as lml


controller_instance: lmc.LayerManagerController | None = None


def _on_invalidation(*args):
    """Invalidate the cache whenever the depsgraph updates."""
    if controller_instance:
        controller_instance.mark_dirty()


def _on_undo_redo(*args):
    """Invalidate the cache after undo, redo, or file-load events."""
    if controller_instance:
        controller_instance.mark_dirty()


def register():
    """
    Register the Layer Manager add-on with Blender.

    Creates the Model and Controller instances, registers all UI classes and
    custom properties, and stores the Controller as a module-level singleton.
    """
    global controller_instance
    lmui.register()
    logic = lml.LayerManagerLogic()
    controller_instance = lmc.LayerManagerController(logic)
    if _on_invalidation not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_invalidation)
    if _on_undo_redo not in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.append(_on_undo_redo)
    if _on_undo_redo not in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.append(_on_undo_redo)
    if _on_undo_redo not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_undo_redo)


def unregister():
    """
    Unregister the Layer Manager add-on from Blender.

    Cleans up the Controller and unregisters all UI classes and custom
    properties.
    """
    global controller_instance
    for handler_list, handler in (
        (bpy.app.handlers.load_post, _on_undo_redo),
        (bpy.app.handlers.redo_post, _on_undo_redo),
        (bpy.app.handlers.undo_post, _on_undo_redo),
        (bpy.app.handlers.depsgraph_update_post, _on_invalidation),
    ):
        try:
            handler_list.remove(handler)
        except ValueError:
            pass
    if controller_instance:
        controller_instance.cleanup()
        controller_instance = None
    lmui.unregister()


if __name__ == "__main__":
    register()
