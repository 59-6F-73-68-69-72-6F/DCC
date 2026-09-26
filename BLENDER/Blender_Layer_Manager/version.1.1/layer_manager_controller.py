"""
Controller layer for the Blender Layer Manager.

Mediates between the Model (LayerManagerLogic) and the View
(layer_manager_ui). Owns the pending staging state: flag toggles from the UI
are staged here and only committed to Blender when the user confirms (OK),
or discarded (CANCEL).
"""

import bpy

from . import layer_manager_ui as lmui


class LayerManagerController:
    """
    Coordinates the Model and the View for the Layer Manager.

    Attributes:
        model: An instance of ``LayerManagerLogic``.
        pending: Staged flag changes keyed by
            ``{view_layer_name: {path: {flag: state}}}``.
    """

    def __init__(self, model):
        """Wire the controller's callbacks into the View's ``UI_HOOKS``."""
        self.model = model
        self.pending: dict = {}

        lmui.UI_HOOKS["get_rows_data"] = self.get_rows_data
        lmui.UI_HOOKS["get_pending_count"] = self.get_pending_count
        lmui.UI_HOOKS["on_toggle_expand"] = self.on_toggle_expand
        lmui.UI_HOOKS["on_toggle_flag"] = self.on_toggle_flag
        lmui.UI_HOOKS["on_apply"] = self.on_apply
        lmui.UI_HOOKS["on_cancel"] = self.on_cancel
        lmui.UI_HOOKS["on_refresh"] = self.refresh
        lmui.UI_HOOKS["on_override"] = self.on_override

    def refresh(self, context: bpy.types.Context):
        """Force a rebuild of the live-state cache and redraw the UI."""
        self.model.refresh_cache(context.scene)
        self.force_ui_redraw()

    def mark_dirty(self):
        """Mark the live-state cache as stale for the next draw or toggle."""
        self.model.mark_dirty()

    def get_rows_data(self, context: bpy.types.Context, props: type):
        """Return visible rows with pending flag changes overlaid on live state."""
        expanded = {item.path for item in props.expanded}
        rows = self.model.build_rows(context.scene, expanded)
        for row in rows:
            for view_layer_name, paths in self.pending.items():
                if view_layer_name in row.flags and row.path in paths:
                    row.flags[view_layer_name].update(paths[row.path])
        return rows

    def get_pending_count(self):
        """Return the total number of staged flag changes awaiting apply."""
        return sum(
            len(flag_states)
            for view_layer_pending in self.pending.values()
            for flag_states in view_layer_pending.values()
        )

    def on_toggle_expand(self, props, path):
        """Expand or collapse a collection row via the stored UI state."""
        props.toggle(path)

    def on_toggle_flag(self, context: bpy.types.Context, view_layer_name: str, path: str, flag: str):
        """Stage ``flag`` for ``path`` and all its descendants (inverted live state)."""
        live = self.model.get_live_flag_state(
            context.scene, view_layer_name, path)
        if live is None:
            return
        path_pending = self.pending.setdefault(
            view_layer_name, {}).setdefault(path, {})
        effective = path_pending.get(flag, live[flag])
        new_state = not effective
        self._stage_flag(context.scene, view_layer_name, path, flag, new_state)
        for child_path in self.model.get_descendant_paths(
            context.scene, view_layer_name, path
        ):
            self._stage_flag(context.scene, view_layer_name,
                             child_path, flag, new_state)
        self.force_ui_redraw()

    def _stage_flag(self, scene: bpy.types.Scene, view_layer_name: str, path: str, flag: str, new_state: bool):
        """Stage ``new_state`` for ``flag`` on ``path``, dropping no-op entries."""
        live = self.model.get_live_flag_state(scene, view_layer_name, path)
        if live is None:
            return
        path_pending = self.pending.setdefault(
            view_layer_name, {}).setdefault(path, {})
        if new_state == live[flag]:
            path_pending.pop(flag, None)
            self._prune_pending(view_layer_name, path)
        else:
            path_pending[flag] = new_state

    def _prune_pending(self, view_layer_name: str, path: str):
        """Remove empty staging entries so ``pending`` holds no dead keys."""
        view_layer_pending = self.pending.get(view_layer_name)
        if view_layer_pending is None:
            return
        path_pending = view_layer_pending.get(path)
        if path_pending is not None and not path_pending:
            view_layer_pending.pop(path, None)
        if not view_layer_pending:
            self.pending.pop(view_layer_name, None)

    def on_apply(self, context: bpy.types.Context):
        """
        Commit all staged flag changes, then update each view layer once.

        Rebuilds the model's layer-collection map from the live tree first
        (defence against stale caches), then writes through the map; paths
        that still cannot be resolved (deleted collection / removed view
        layer) fall back to a live DFS lookup and are otherwise skipped.
        """
        self.model.refresh_cache(context.scene)
        updated_view_layers = set()

        """Apply all staged changes via the layer-collection map first, then
        fall back to a live DFS lookup for any paths that cannot be resolved."""
        for view_layer_name, paths in self.pending.items():
            failures = [
                (path, flag_states)
                for path, flag_states in paths.items()
                if not self.model.apply_flag_states(
                    context.scene, view_layer_name, path, flag_states
                )
            ]
            if failures:
                self.model.refresh_cache(context.scene)
                failures = [
                    (path, flag_states)
                    for path, flag_states in failures
                    if not self.model.apply_flag_states(
                        context.scene, view_layer_name, path, flag_states
                    )
                ]
            # Final fallback: DFS lookup for any remaining failures.
            for path, flag_states in failures:
                self.model.apply_flags(
                    context.scene, view_layer_name, path, flag_states
                )
            updated_view_layers.add(view_layer_name)

        # Update each view layer once after all writes are complete.
        for view_layer_name in updated_view_layers:
            view_layer = context.scene.view_layers.get(view_layer_name)
            if view_layer is not None:
                view_layer.update()
        self.pending.clear()
        self.model.mark_dirty()
        self.force_ui_redraw()

    def on_cancel(self):
        """Discard all staged flag changes and redraw the UI."""
        self.pending.clear()
        self.force_ui_redraw()

    def on_override(self, context: bpy.types.Context, source_view_layer_name: str) -> int:
        """
        Copy one view layer's flag map onto every other view layer now.

        The source map is the live flag state overlaid with any staged
        changes still pending on the source view layer. Only writes that
        actually differ from a target's current state are made. Any pending
        staging is cleared afterwards because the override supersedes it.
        Returns the number of flags written.
        """
        scene = context.scene
        if source_view_layer_name not in [vl.name for vl in scene.view_layers]:
            return 0
        if len(scene.view_layers) < 2:
            return 0
        self.model.refresh_cache(scene)

        # Build a map of the source view layer's flag states, including any pending changes.
        source_map = {
            path: dict(states)
            for path, states in self.model.cache.get(
                scene.name, {}).get(source_view_layer_name, {}).items()
        }

        # Overlay any pending changes for the source view layer onto the source map.
        for path, states in self.pending.get(source_view_layer_name, {}).items():
            source_map.setdefault(path, {}).update(states)

        written = 0
        updated = set()

        # Iterate over all other view layers and apply the source map to them.
        for view_layer in scene.view_layers:
            if view_layer.name == source_view_layer_name:
                continue
            # map of path -> {flag: state} for the target view layer
            target_map = self.model.cache.get(scene.name, {}).get(view_layer.name, {})
            touched = False  # flag to track if any changes were made to this view layer
            for path, states in source_map.items():
                target_states = target_map.get(path)
                if target_states is None:
                    continue
                for flag, state in states.items():
                    if target_states.get(flag) == state:
                        continue
                    if self.model.apply_flag_states(
                        scene, view_layer.name, path, {flag: state}
                    ):
                        written += 1
                        touched = True
            if touched:
                updated.add(view_layer.name)

        for view_layer_name in updated:
            view_layer = scene.view_layers.get(view_layer_name)
            if view_layer is not None:
                view_layer.update()
        self.pending.clear()
        self.model.mark_dirty()
        self.force_ui_redraw()
        return written

    def force_ui_redraw(self):
        """Request a redraw of all 3D View areas."""
        if bpy.context.screen is None:
            return
        for area in bpy.context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

    def cleanup(self):
        """Detach all controller callbacks from the View's ``UI_HOOKS``."""
        for key in lmui.UI_HOOKS:
            lmui.UI_HOOKS[key] = None
