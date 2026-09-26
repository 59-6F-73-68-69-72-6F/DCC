"""
This module defines the UI elements for the Light Link Savior
It includes operators for saving and restoring light linking states,
as well as a sidebar panel to expose these actions to the user.
"""

import os

import bpy

from . import ll_savior_controller


temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
stash_file_path = os.path.join(temp_dir, "light_linking_stash.json")


class LM_OT_SaveLightLink(bpy.types.Operator):
    """Save the current light linking state to a temporary file, via the controller."""

    bl_idname = "lm.save_light_link"
    bl_label = "Save Light Link"
    bl_description = "Save the current light linking state to a temporary file"

    def execute(self, context) -> set[str]:
        ll_savior_controller.save_light_links()
        return {"FINISHED"}


class LM_OT_RestoreLightLink(bpy.types.Operator):
    """Restore the light linking state from the temporary file, via the controller."""

    bl_idname = "lm.restore_light_link"
    bl_label = "Restore Light Link"
    bl_description = "Restore the light linking state from the temporary file"

    def execute(self, context) -> set[str]:
        if not os.path.exists(stash_file_path):
            self.report({"ERROR"}, "No saved light links to restore")
            return {"CANCELLED"}
        ll_savior_controller.restore_light_links()
        return {"FINISHED"}


class LIGHTLINKING_PT_MainPanel(bpy.types.Panel):
    """Sidebar panel exposing the Save/Restore actions."""

    bl_label = "LIGHT LINK SAVIOR"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lighting"

    def draw(self, context):
        """Draw the UI elements in the sidebar panel."""
        layout = self.layout
        col = layout.column(align=True)
        col.operator("lm.save_light_link", text="Save", icon="FILE_TICK")
        col.operator("lm.restore_light_link", text="Restore", icon="RECOVER_LAST")

        layout.separator()
        # -- Tail --
        table_tail = layout.box()
        tail_row = table_tail.row(align=True)
        tail_row.scale_y = 0.3
        tail_row.label(text="© 2026 Rudy Leti. All Rights Reserved.")


classes = (LM_OT_SaveLightLink,
           LM_OT_RestoreLightLink,
           LIGHTLINKING_PT_MainPanel)


def register():
    """Register the UI classes with Blender."""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """Unregister the UI classes from Blender."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
