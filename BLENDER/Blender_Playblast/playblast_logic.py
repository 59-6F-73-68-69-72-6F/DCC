"""Core playblast rendering logic, decoupled from the UI layer."""

import os
import datetime

import bpy


class PlayblastLogic:
    """Orchestrates an OpenGL viewport playblast, restoring scene state afterward."""

    def __init__(self):
        """Initialize placeholders for the scene state that will be saved and restored."""
        self._original_filepath: str
        self._original_file_format: str
        self._original_start: int
        self._original_end: int

    def make_playblast(self, output_dir: str, start: int, end: int):
        """
        Render a viewport playblast and save PNG frames into a timestamped folder.

        Temporarily sets the scene's frame range and render settings for the
        duration of the render, then restores their original values.

        Args:
            output_dir: Directory where the timestamped playblast subfolder is created.
            start: First frame of the playblast range.
            end: Last frame of the playblast range.

        """
        if start > end:
            raise ValueError("First Frame Higher than Last Frame")

        scene = bpy.context.scene
        render = scene.render
        stamped_time_folder = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Store Original Frame Range and Path
        self._original_filepath = render.filepath
        self._original_file_format = render.image_settings.file_format
        self._original_start = scene.frame_start
        self._original_end = scene.frame_end

        # Updated Frame Range and Path
        scene.frame_start = start
        scene.frame_end = end
        render.image_settings.file_format = 'PNG'
        render.filepath = os.path.join(output_dir + "/" + stamped_time_folder, "playblast_")

        try:
            # Playblast
            bpy.ops.render.opengl(animation=True, view_context=True)

        finally:
            # Restore Original Frame Range and Path
            scene.frame_start = self._original_start
            scene.frame_end = self._original_end
            render.filepath = self._original_filepath
            render.image_settings.file_format = self._original_file_format
