"""Blender UI layer: properties, operators, and the sidebar panel for Playblast."""


import os

import bpy

from .playblast_logic import PlayblastLogic


def register_properties():
    """Register all window-manager properties used by the Playblast UI."""
    wm = bpy.types.WindowManager

    wm.playblast_range_synced = bpy.props.BoolProperty(default=False)
    wm.frame_start = bpy.props.IntProperty(name="First Frame", default=1, min=-100)
    wm.frame_end = bpy.props.IntProperty(name="Last Frame", default=250, min=-100)

    wm.playblast_output_path = bpy.props.StringProperty(
        name="Output Path",
        description="Directory where playblast images will be saved",
        default="",
        subtype='DIR_PATH',
    )


def unregister_properties():
    """Delete all window-manager properties registered by the playblast UI."""
    del bpy.types.WindowManager.playblast_output_path
    del bpy.types.WindowManager.frame_start
    del bpy.types.WindowManager.frame_end
    del bpy.types.WindowManager.playblast_range_synced


class PLAYBLAST_OT_Create(bpy.types.Operator):
    """Render a viewport playblast and save PNG frames to the chosen folder."""
    bl_idname = "playblast.create"
    bl_label = "Create Playblast"

    def execute(self, context):
        """
        Validate selection, then render the playblast to the chosen folder.

        Args:

        context: The current Blender context.

        Returns: {'FINISHED'} on success, {'CANCELLED'} on invalid input.
        """
        wm = context.window_manager
        output_path = wm.playblast_output_path

        if not output_path or not os.path.isdir(output_path):
            self.report({'ERROR'}, "Please select a valid output folder first.")
            return {'CANCELLED'}

        logic = PlayblastLogic()
        logic.make_playblast(output_path, wm.frame_start, wm.frame_end)

        self.report({'INFO'}, f"Playblast saved to {output_path}")
        return {'FINISHED'}


class PLAYBLAST_PT_Panel(bpy.types.Panel):
    """Sidebar panel for the Playblast tool."""
    bl_label = "Playblast"
    bl_idname = "PLAYBLAST_PT_playblast"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Animation"

    def draw(self, context):
        """
        Draw the playblast sidebar panel, syncing the frame range from the scene.

        Args:
            context: The current Blender context used to access the scene and window manager.
        """
        layout = self.layout
        wm = context.window_manager

        scene = context.scene
        if not wm.playblast_range_synced:
            wm.frame_start = scene.frame_start
            wm.frame_end = scene.frame_end
            wm.playblast_range_synced = True

        if wm.frame_start >= wm.frame_end:
            wm.frame_end = wm.frame_start + 1

        box = layout.box()
        row = box.row(align=True)
        row.prop(wm, "playblast_output_path", text="Folder")

        row_in = box.row(align=True)
        row_in.prop(wm, "frame_start", text="Start")
        row_in.prop(wm, "frame_end", text="End")

        box.operator("playblast.create", text="Create Playblast", icon='RENDER_ANIMATION')

        layout.separator()

        # -- Tail --
        table_tail = layout.box()
        tail_row = table_tail.row(align=True)
        tail_row.scale_y = 0.3
        tail_row.label(text="© 2026 Rudy Leti. All Rights Reserved.")


classes = (
    PLAYBLAST_OT_Create,
    PLAYBLAST_PT_Panel,
)


def register():
    """Register all Playblast UI classes and window-manager properties."""
    register_properties()
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """Unregister all Playblast UI classes and window-manager properties."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    unregister_properties()
