# Blender Layer Manager v1.0 — Developer Documentation

## Architecture Overview

The add-on follows the **Model-View-Controller (MVC)** architectural pattern.

```
__init__.py                             (Bootstrap / Entry Point)
    │
    ├──► layer_manager_controller.py    (Controller)
    │         │
    │         ├──► layer_manager_logic.py       (Model)
    │         │         │
    │         │         └──► models/collection_state.py   (DTO)
    │         │
    │         └──► layer_manager_ui.py   (View)
    │
    └──► layer_manager_ui.py   (View registration)
```

### Layer Responsibilities

| Layer | File | Role |
|---|---|---|
| **Model** | `layer_manager_logic.py` + `models/collection_state.py` | Pure data/logic. Performs all direct Blender `bpy` operations (collection tree traversal, view-layer flag reading/writing) and owns the live-state caches. Has **zero imports** from View or Controller. |
| **View** | `layer_manager_ui.py` | Blender UI components: custom properties, Operators, Panel. Delegates all behaviour to the Controller via the `UI_HOOKS` callback dictionary. |
| **Controller** | `layer_manager_controller.py` | Mediates Model ↔ View. Owns the staging transaction (`pending`), registers callbacks into `UI_HOOKS`, triggers UI redraws, and resolves flag writes through the model's caches. |
| **Bootstrap** | `__init__.py` | `bl_info` metadata, `register()` / `unregister()` add-on lifecycle, and the auto-invalidation handlers (depsgraph / undo / redo / load). |

---

## File Breakdown

### `__init__.py` — Entry Point

- Defines `bl_info` (add-on metadata: name "Layer Manager", author "Rudy Leti", version `(1, 0, 0)`, Blender `5.0+`, category "Lighting").
- Module-level `controller_instance` holds the singleton `LayerManagerController`.
- `register()`: Instantiates `LayerManagerLogic` and `LayerManagerController`, registers UI classes via `lmui.register()`, then appends the invalidation handlers. Appends are **idempotent** (guarded by `if handler not in list`) because Blender auto-registers enabled add-ons at startup.
- `unregister()`: Removes the handlers with a defensive `try/except ValueError` (Blender may already have dropped a handler that raised), cleans up the controller (nullifies hooks), then unregisters UI classes.
- Handlers:
  - `_on_invalidation(*args)` → appended to `depsgraph_update_post`.
  - `_on_undo_redo(*args)` → appended to `undo_post`, `redo_post`, `load_post`.
  - Both simply call `controller_instance.mark_dirty()`.

### `layer_manager_logic.py` — Model Layer

**Class: `LayerManagerLogic`**

Owns two parallel caches and a dirty flag:

| Attribute | Structure | Purpose |
|---|---|---|
| `cache` | `{scene.name: {view_layer.name: {path: {flag: bool}}}}` | Live flag states for every collection in every view layer. |
| `layer_collections` | `{scene.name: {view_layer.name: {path: LayerCollection}}}` | O(1) path → `LayerCollection` resolution for writing flags. |
| `cache_dirty` | `bool` | Global staleness flag for both caches. |

| Method | Description | Cost |
|---|---|---|
| `mark_dirty()` | Flags both caches as stale. | O(1) |
| `refresh_cache(scene)` | **Merged single DFS walk** per view layer of `scene` that rebuilds both `cache` and `layer_collections` at once. Preserves other scenes' entries. | O(V·N) |
| `ensure_fresh(scene)` | Rebuilds via `refresh_cache` only when `cache_dirty` is `True`. | O(1) |
| `get_collection_by_path(scene, path)` | Resolves a slash-separated path to a `Collection`. | O(depth) |
| `find_layer_collection(lc, collection)` | Recursive DFS to find the `LayerCollection` for a `Collection`. | O(N) |
| `get_flag_state(lc)` | Reads EXCLUDE/HOLDOUT/INDIRECT from a `LayerCollection`. | O(1) |
| `_set_flag(lc, flag, state)` | Writes one flag onto a `LayerCollection`. | O(1) |
| `get_live_flag_state(scene, vl, path)` | Cache lookup; `None` if unknown. | O(1) |
| `get_descendant_paths(scene, vl, path)` | Prefix-filter over cache keys (non-recursive). | O(N) |
| `apply_flags(scene, vl, path, flag_states)` | Live DFS write (fallback path). Does **not** call `view_layer.update()`. | O(N) |
| `apply_flag_states(scene, vl, path, flag_states)` | Map-based write; returns `False` if the path is missing from the map (stale structure). Guards against use-after-free by verifying the cached `LayerCollection` is still reachable in the live view-layer tree (`_is_in_tree`) before writing. | O(N) |
| `build_rows(scene, expanded_paths)` | Builds visible `CollectionRowState` rows honouring expansion, reading flags from the cache. Stores **copies** of flag dicts (`dict(state)`) so the pending overlay can never mutate the cache. | O(R·V) |

### `models/collection_state.py` — Data Transfer Object

**Dataclass: `CollectionRowState`**

Pure Python (no `bpy`). Fields: `path`, `name`, `depth`, `has_children`, `expanded`, `flags` (`{view_layer_name: {flag: bool}}`).

### `layer_manager_controller.py` — Controller Layer

**Class: `LayerManagerController`**

| Method | Description |
|---|---|
| `__init__(model)` | Stores the model and wires all callbacks into `lmui.UI_HOOKS`. |
| `refresh(context)` | Forces a full cache rebuild (the Refresh button) and redraw. |
| `mark_dirty()` | Delegates to `model.mark_dirty()` (called by the invalidation handlers). |
| `get_rows_data(context, props)` | `build_rows` + overlays `pending` changes on top of live state (on copies). |
| `get_pending_count()` | Total number of staged flag changes. |
| `on_toggle_expand(props, path)` | Expands/collapses a row in `lm_props`. |
| `on_toggle_flag(context, vl, path, flag)` | Computes the effective (staged-or-live) state, inverts it, and stages it for the path **and all descendants**. |
| `_stage_flag(...)` | Stages one change, dropping no-op entries that equal live state. |
| `_prune_pending(vl, path)` | Removes empty staging entries so `pending` holds no dead keys. |
| `on_apply(context)` | Commits all staged changes via the map; on a stale-map miss it rebuilds once, retries, then falls back to DFS `apply_flags`. Updates each touched view layer **once** (batched), then clears `pending` and marks the cache dirty. |
| `on_cancel()` | Discards all staged changes and redraws. |
| `force_ui_redraw()` | Tags all `VIEW_3D` areas for redraw. |
| `cleanup()` | Nullifies every `UI_HOOKS` callback. |

### `layer_manager_ui.py` — View Layer

**Hook System — `UI_HOOKS` dict**

A global dictionary of callbacks populated by the Controller. View code calls these hooks without importing the Controller.

| Hook Key | Signature | Purpose |
|---|---|---|
| `get_rows_data` | `(context, props)` | Retrieve visible rows with effective flag states. |
| `get_pending_count` | `()` | Number of staged changes. |
| `on_toggle_expand` | `(props, path)` | Expand/collapse a row. |
| `on_toggle_flag` | `(context, vl, path, flag)` | Stage a flag change (parent + descendants). |
| `on_apply` | `(context)` | Apply all staged changes. |
| `on_cancel` | `()` | Discard all staged changes. |
| `on_refresh` | `(context)` | Force a live-state cache refresh. |

**Operators (Blender `bpy.types.Operator` subclasses)**

| Class | `bl_idname` | Action |
|---|---|---|
| `LM_OT_toggle_expand` | `lm.toggle_expand` | Expand/collapse a collection row. |
| `LM_OT_toggle_flag` | `lm.toggle_flag` | Stage a flag toggle for a row. |
| `LM_OT_refresh` | `lm.refresh` | Force a cache refresh (header button). |
| `LM_OT_apply_flags` | `lm.apply_flags` | Commit pending changes ("OK"). |
| `LM_OT_cancel_flags` | `lm.cancel_flags` | Discard pending changes ("CANCEL"). |

**Panel**

| Class | Location |
|---|---|
| `LAYERMAN_PT_MainPanel` | `VIEW_3D` → Sidebar → Layer Manager tab ("BLENDER LAYER MANAGER"). |

**Custom Properties**

Registered on `bpy.types.WindowManager`:
- `lm_props` → `LM_Props`, whose `expanded` collection of `LM_ExpandItem` tracks which collection paths are expanded.

**Helpers**

- `split_n(layout, count)` — splits a row into `count` aligned columns (one per view layer).
- `FLAG_ICONS` — icon pairs per flag (`EXCLUDE`, `HOLDOUT`, `INDIRECT`).

---

## Data Flow

```
Draw path:
Panel.draw() ──► UI_HOOKS["get_rows_data"](context, props)
                       │
                       ├──► model.build_rows(scene, expanded)   (from cache, O(R·V))
                       └──► overlay pending onto row flag copies
                       ▼
                 render header / rows / flag cells / footer

Toggle path:
LM_OT_toggle_flag.execute() ──► UI_HOOKS["on_toggle_flag"](...)
                                       │
                                       ├──► compute effective state (live or staged)
                                       ├──► stage parent + all descendants
                                       └──► force_ui_redraw()

Apply path:
LM_OT_apply_flags.execute() ──► UI_HOOKS["on_apply"](context)
                                       │
                                       ├──► model.apply_flag_states() per path (map, O(1))
                                       ├──► on stale miss: refresh_cache() → retry → DFS fallback
                                       ├──► view_layer.update() once per touched view layer
                                       └──► pending.clear() + model.mark_dirty() + redraw
```

---

## Caching Strategy

Two structures are built together in a **single DFS walk** per view layer (`refresh_cache`):

1. `cache` — live flag states (`{path: {flag: bool}}`).
2. `layer_collections` — `{path: LayerCollection}` for O(1) writes.

Both are invalidated together via `cache_dirty`. Any invalidation trigger marks the cache dirty, and the **next read** (draw or toggle) lazily rebuilds both caches:

- `depsgraph_update_post` — fires on scene/view-layer/collection changes (including external edits in the Outliner).
- `undo_post` / `redo_post` — undo/redo of any operation.
- `load_post` — file load.
- `LM_OT_refresh` (Refresh button) — forces an immediate rebuild, covering any residual staleness.

The Refresh button exists as a manual override because the depsgraph handler only *marks dirty*; it cannot know whether the change affected collections. Flag toggles staged by the add-on do **not** invalidate the map (they only affect flag values), so the map is purely structure-driven and stays valid across staging.

Key safety property: `build_rows` copies flag dicts, so the pending overlay in `get_rows_data` can never write staged values back into the live cache (regression-tested).

---

## Staging Transaction Model

Toggles are staged, not applied:

- `pending` is `{view_layer_name: {path: {flag: new_state}}}`.
- Toggling a parent also stages the same change for **every descendant** (get_descendant_paths).
- `_stage_flag` drops entries whose target equals live state (no-op), and `_prune_pending` removes empty path/view-layer keys.
- **OK** (`on_apply`) commits everything; **CANCEL** (`on_cancel`) discards everything.
- While changes are pending, the panel shows the *effective* (overlaid) state and the "Pending changes: N" counter; the action buttons are enabled only when `N > 0`.

---

## Performance Model

`N` = total collections, `V` = view layers, `R` = visible rows, `D` = applied paths.

| Path | Big-O | Measured @ 210 collections |
|---|---|---|
| `refresh_cache` (full rebuild) | O(V·N) | ~1 ms (1 VL) / ~3 ms (3 VL) |
| `build_rows` (draw) | O(R·V), O(1)/cell | ~1 ms (1 VL) / ~1.7 ms (3 VL) |
| `get_live_flag_state` | O(1) | < 0.01 ms |
| toggle recursion (`on_toggle_flag`) | O(N) | ~0.1 ms |
| `on_apply` (all pending, batched) | O(D + N) | ~6 ms (210 flags) |
| cache memory | O(V·N) | 3 booleans per cell |

The pipeline is **linear end-to-end**; the previous O(N²) apply hotspot (a recursive DFS per path) was eliminated by the `layer_collections` map plus a single batched `view_layer.update()`.

---

## Naming Conventions

- **Files:** `layer_manager_*.py` prefix for consistency.
- **Classes:** PascalCase — `LayerManagerLogic`, `LayerManagerController`.
- **Methods/Functions:** snake_case — `get_descendant_paths`, `force_ui_redraw`.
- **Operators:** `LM_OT_*` (Blender standard: `{Addon}_{Type}_{Name}`).
- **Panel:** `LAYERMAN_PT_*` (Blender standard: `{Addon}_PT_{Name}`).
- **Custom Properties:** `lm_*` prefix (lowercase, namespaced with add-on initials).
- **Flags:** UPPER_CASE — `EXCLUDE`, `HOLDOUT`, `INDIRECT`.
- **Hook keys:** snake_case — `on_toggle_flag`, `get_rows_data`.

---

## How to Extend

### Add a new UI control / hook

1. Add a callback key to `UI_HOOKS` in `layer_manager_ui.py`.
2. Add the handler method in `LayerManagerController.__init__()`.
3. Add the UI element in `LAYERMAN_PT_MainPanel.draw()`.

### Add a new Blender operator

1. Create a class inheriting `bpy.types.Operator` in `layer_manager_ui.py`.
2. Add it to the `classes` tuple.
3. Delegate logic through `UI_HOOKS`.

### Add or change a flag

1. Add the property branch to `LayerManagerLogic.get_flag_state()` and `_set_flag()`.
2. Add an icon pair to `FLAG_ICONS` in `layer_manager_ui.py`.
3. Add an item to the `flag` EnumProperty of `LM_OT_toggle_flag`.
4. Add the flag to the per-cell loop in `LAYERMAN_PT_MainPanel.draw()`.

### Change recursion behaviour

- The descendant propagation in `on_toggle_flag` is driven by `get_descendant_paths`. To restrict propagation (e.g. to children only, not all descendants), change the filter in that method.

---

## Testing

Headless regression suites (run against the addon package with a system Blender):

- Cache build / lazy refresh / staleness + handler add/remove symmetry — `test_cache`.
- 130-collection correctness, batched apply, cancel-revert (cache un-pollution), and **self-heal** scenarios (rename/remove a collection, then apply) — `test_bigscene`.
- Micro-benchmarks at 210 collections (1 and 3 view layers) — `bench_200`.

The add-on registers cleanly headless: `register()` / `unregister()` add and remove the invalidation handlers symmetrically and idempotently.
