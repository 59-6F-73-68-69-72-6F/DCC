"""
Model layer for the Blender Layer Manager.

Provides the LayerManagerLogic class which performs all direct Blender bpy
operations (collection tree traversal, view-layer flag reading and writing)
without any knowledge of the View or Controller layers.
"""

import bpy

from .models.collection_state import CollectionRowState


class LayerManagerLogic:
    """
    Performs all direct Blender operations for the Layer Manager.

    This is the pure data/logic layer (Model) in the MVP architecture.
    It has no imports from the View or Controller modules and can be tested
    independently.
    """

    def __init__(self):
        """Initialise empty live-state and layer-collection caches, both dirty."""
        self.cache: dict = {}
        self.layer_collections: dict = {}
        self.cache_dirty: bool = True

    def mark_dirty(self):
        """Flag both caches as stale so they rebuild on next read."""
        self.cache_dirty = True

    def refresh_cache(self, scene: bpy.types.Scene):
        """Rebuild both caches for every view layer of ``scene`` in one walk."""
        cache = dict(self.cache)
        layer_collections = dict(self.layer_collections)

        def walk(lc: bpy.types.LayerCollection, path: str, by_path: dict, by_lc: dict):
            by_path[path] = self.get_flag_state(lc)
            by_lc[path] = lc
            for child in lc.children:
                child_path = child.collection.name if not path else f"{path}/{child.collection.name}"
                walk(child, child_path, by_path, by_lc)

        scene_cache = {}
        scene_lc = {}
        for vl in scene.view_layers:
            by_path = {}
            by_lc = {}
            walk(vl.layer_collection, "", by_path, by_lc)
            scene_cache[vl.name] = by_path
            scene_lc[vl.name] = by_lc
        cache[scene.name] = scene_cache
        layer_collections[scene.name] = scene_lc
        self.cache = cache
        self.layer_collections = layer_collections
        self.cache_dirty = False

    def ensure_fresh(self, scene: bpy.types.Scene):
        """Rebuild the cache for ``scene`` if it is currently dirty."""
        if self.cache_dirty:
            self.refresh_cache(scene)

    def get_collection_by_path(self, scene: bpy.types.Scene, path: str) -> None | type:
        """Resolve a ``path`` string to a Collection, or ``None`` if missing."""
        current = scene.collection
        for name in path.split("/"):
            child = current.children.get(name)
            if child is None:
                return None
            current = child
        return current

    def find_layer_collection(self, layer_collection: bpy.types.LayerCollection, collection: bpy.types.Collection) -> bpy.types.LayerCollection | None:
        """Find the LayerCollection matching ``collection`` via depth-first search."""
        if layer_collection.collection == collection:
            return layer_collection
        for child in layer_collection.children:
            result = self.find_layer_collection(child, collection)
            if result is not None:
                return result
        return None

    def get_flag_state(self, layer_collection: bpy.types.LayerCollection) -> dict:
        """Return the EXCLUDE/HOLDOUT/INDIRECT states of a LayerCollection."""
        return {
            "EXCLUDE": layer_collection.exclude,
            "HOLDOUT": layer_collection.holdout,
            "INDIRECT": layer_collection.indirect_only,
        }

    def _set_flag(self, layer_collection: bpy.types.LayerCollection, flag: str, state: bool):
        """Write ``state`` for ``flag`` onto a LayerCollection."""
        if flag == "EXCLUDE":
            layer_collection.exclude = state
        elif flag == "HOLDOUT":
            layer_collection.holdout = state
        elif flag == "INDIRECT":
            layer_collection.indirect_only = state

    @staticmethod
    def _is_in_tree(root: bpy.types.LayerCollection, target: bpy.types.LayerCollection) -> bool:
        """Return whether ``target`` is reachable from the live ``root`` tree.

        Uses pointer-identity comparison (``==`` on bpy objects), which is
        safe even when ``target`` references a freed LayerCollection; only the
        live ``root`` subtree is dereferenced.
        """
        if root == target:
            return True
        return any(
            LayerManagerLogic._is_in_tree(child, target) for child in root.children
        )

    def get_live_flag_state(self, scene: bpy.types.Scene, view_layer_name: str, path: str) -> dict:
        """Return cached flag states for ``path``, or ``None`` if unknown."""
        self.ensure_fresh(scene)
        return self.cache.get(scene.name, {}).get(view_layer_name, {}).get(path)

    def get_descendant_paths(self, scene: bpy.types.Scene, view_layer_name: str, path: str) -> list:
        """Return all cached descendant paths strictly below ``path``."""
        self.ensure_fresh(scene)
        prefix = f"{path}/"
        return [
            candidate
            for candidate in self.cache.get(scene.name, {}).get(view_layer_name, {})
            if candidate.startswith(prefix)
        ]

    def apply_flags(self, scene: bpy.types.Scene, view_layer_name: str, path: str, flag_states: dict) -> bool:
        """
        Write ``flag_states`` to a collection; return ``True`` on success.

        Does not call ``view_layer.update()``; callers should update each
        touched view layer once after a batch of flag writes.
        """
        view_layer = scene.view_layers.get(view_layer_name)
        collection = self.get_collection_by_path(scene, path)
        if view_layer is None or collection is None:
            return False
        layer_collection = self.find_layer_collection(
            view_layer.layer_collection, collection
        )
        if layer_collection is None:
            return False
        for flag, state in flag_states.items():
            self._set_flag(layer_collection, flag, state)
        return True

    def apply_flag_states(self, scene: bpy.types.Scene, view_layer_name: str, path: str, flag_states: dict) -> bool:
        """Write ``flag_states`` via the layer-collection map; return ``True`` on success.

        Unlike :meth:`apply_flags` this is O(1) per path. A ``False`` return
        means the path is absent from the map (stale structure); callers should
        rebuild via :meth:`refresh_cache` and retry, then fall back to
        :meth:`apply_flags` if it still cannot be resolved.
        """
        self.ensure_fresh(scene)
        layer_collection = (
            self.layer_collections.get(scene.name, {})
            .get(view_layer_name, {})
            .get(path)
        )
        if layer_collection is None:
            return False
        view_layer = scene.view_layers.get(view_layer_name)
        if view_layer is None or not self._is_in_tree(
            view_layer.layer_collection, layer_collection
        ):
            return False
        for flag, state in flag_states.items():
            self._set_flag(layer_collection, flag, state)
        return True

    def build_rows(self, scene: bpy.types.Scene, expanded_paths: set) -> list:
        """Build visible CollectionRowState rows for ``scene``, honouring expansion."""
        self.ensure_fresh(scene)
        rows = []
        view_layers = list(scene.view_layers)

        def walk(collection: bpy.types.Collection, path: str, depth: int):
            for child in collection.children:
                child_path = child.name if not path else f"{path}/{child.name}"
                flags = {}
                for vl in view_layers:
                    state = self.cache.get(scene.name, {}).get(
                        vl.name, {}).get(child_path)
                    if state is not None:
                        flags[vl.name] = dict(state)
                rows.append(
                    CollectionRowState(
                        path=child_path,
                        name=child.name,
                        depth=depth,
                        has_children=bool(child.children),
                        expanded=child_path in expanded_paths,
                        flags=flags,
                    )
                )
                if child_path in expanded_paths:
                    walk(child, child_path, depth + 1)

        walk(scene.collection, "", 0)
        return rows
