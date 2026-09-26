# Layer Manager — Developer Documentation (v1.1)

Developer reference for the **Layer Manager** Blender add-on by Rudy Leti.
Targets Blender 5.0+. This document explains the architecture, module
responsibilities, data flow, caching strategy, and extension points.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture (MVP)](#architecture-mvp)
3. [Module Reference](#module-reference)
4. [Data Flow](#data-flow)
5. [Caching & Invalidation](#caching--invalidation)
6. [Core Concepts](#core-concepts)
7. [Extension Guide](#extension-guide)
8. [Testing](#testing)
9. [Conventions](#conventions)

---

## Overview

Layer Manager is a Blender add-on that lets artists control collection-level
render flags — **EXCLUDE**, **HOLDOUT**, and **INDIRECT** — per **view layer**,
from a single side-bar panel. Key behaviours:

- A **staging / commit** workflow: flag toggles are *staged* in memory and only
  written to Blender when the user presses **OK** (or discarded with
  **CANCEL**).
- **Descendant propagation**: toggling a parent collection stages the same
  change for all of its child collections.
- **Override**: copy one view layer's whole flag map onto every other view layer.
- **Cache invalidation** driven by Blender events (depsgraph updates, undo,
  redo, file load and save).

---

## Architecture (MVP)

The add-on follows a **Model – View – Controller** (MVP) split. There is no
frame-time coupling between layers; the View calls the Controller through a
**hook dictionary** (`UI_HOOKS`) instead of importing it directly.

```
                +--------------------------+
                |      __init__.py          |  Bootstrap: wires model + controller,
                |  (add-on entry point)     |  registers handlers, owns singleton.
                +------------+-------------+
                             |
              registers handlers / delegates UI registration
                             |
                             v
+---------------+     +-----------------+     +----------------------+
| UI  (View)    |     |  Controller     |     |  Model  (Logic)      |
| layer_        | --> | layer_manager_  | --> |  layer_manager_      |
| manager_ui.py |     | controller.py   |     |  logic.py            |
+---------------+     +-----------------+     +----------------------+
       |                    |                          |
       |  UI_HOOKS (dict)   |  calls Model methods     |  owns bpy access
       |  callbacks         |  owns `pending` state    |  + caches
       v                    v                          v
   Panel + Operators    staging / apply / cancel /   collection tree walk,
   + WindowManager      override / refresh           flag read & write
   props
```

### Layer roles

| Layer | Module | Responsibility | Import rules |
|-------|--------|----------------|--------------|
| Model | `layer_manager_logic.py` | All direct `bpy` operations: tree traversal, flag read/write, caching. Owns `cache` and `layer_collections`. | Must **not** import View or Controller modules. |
| View | `layer_manager_ui.py` | UI classes: panel, operators, WindowManager property groups. Pure presentation. | Exposes `UI_HOOKS`; never calls Model directly. |
| Controller | `layer_manager_controller.py` | Mediates Model ↔ View. Owns `pending` (staged changes). Implements apply/cancel/override/refresh logic. | Imports View (for `UI_HOOKS`); never imports Model statically. |
| Bootstrap | `__init__.py` | Add-on metadata, singleton, Blender event handlers, `sys.path` setup. | Imports all three layers. |
| Data | `models/collection_state.py` | Pure-Python dataclasses (no `bpy`). Shared DTOs. | No Blender imports. |

---

## Module Reference

### `__init__.py` — Entry point

Add-on metadata (`bl_info`, lines 10–18):

| Field | Value |
|-------|-------|
| `name` | `Layer Manager` |
| `author` | `Rudy Leti` |
| `version` | `(1, 1, 0)` |
| `blender` | `(5, 0, 0)` |
| `location` | `View3D > Sidebar > Layer Manager` |
| `category` | `Lighting` |

Module-level symbols:

- `controller_instance` — the singleton `LayerManagerController | None`.
- `_on_invalidation(handler)` — marks the cache dirty on
  `depsgraph_update_post`.
- `_on_undo_redo(handler)` — marks the cache dirty on `undo_post`,
  `redo_post`, and `load_post`.

Lifecycle:

- `register()` — 1) registers UI (View), 2) constructs the Model and
  Controller, 3) stores the controller singleton, 4) appends event handlers.
- `unregister()` — removes event handlers, calls `Controller.cleanup()`,
  clears the singleton, unregisters UI.

> Order matters: the View must be registered **before** the Controller is
> constructed, because the Controller writes its callbacks into
> `layer_manager_ui.UI_HOOKS`.

### `layer_manager_logic.py` — Model

Class `LayerManagerLogic`:

| Member | Kind | Purpose |
|--------|------|---------|
| `cache: dict` | attr | `{scene_name: {view_layer_name: {path: {flag: state}}}}` — **flag states**. |
| `layer_collections: dict` | attr | `{scene_name: {view_layer_name: {path: LayerCollection}}}` — **resolved LayerCollection objects** for O(1) writes. |
| `cache_dirty: bool` | attr | Both caches are stale when `True`. |
| `mark_dirty()` | method | Marks `cache_dirty = True`. |
| `refresh_cache(scene)` | method | Rebuilds **both** caches for every view layer in one tree walk. |
| `ensure_fresh(scene)` | method | Calls `refresh_cache` only when dirty. |
| `get_collection_by_path(scene, path)` | method | Resolves a path to a `Collection` by walking `scene.collection.children`. |
| `find_layer_collection(lc, collection)` | method | DFS search for the `LayerCollection` matching a `Collection`. |
| `get_flag_state(lc)` | method | Returns `{"EXCLUDE":…, "HOLDOUT":…, "INDIRECT":…}` for a LayerCollection. |
| `_set_flag(lc, flag, state)` | method | Writes one flag onto a LayerCollection. |
| `_is_in_tree(root, target)` | static | Pointer-identity check whether `target` is reachable from live `root`. Safe on freed objects. |
| `get_live_flag_state(scene, vl_name, path)` | method | Cached flag-state lookup; `None` when path is unknown. |
| `get_descendant_paths(scene, vl_name, path)` | method | All cached paths strictly below `path` (prefix `"{path}/"`). |
| `apply_flags(scene, vl_name, path, flag_states)` | method | Fallback writer using `get_collection_by_path` + DFS. Returns `bool`. **No `view_layer.update()`**. |
| `apply_flag_states(scene, vl_name, path, flag_states)` | method | O(1) writer via `layer_collections` map; validates membership with `_is_in_tree`. Returns `bool`. |
| `build_rows(scene, expanded_paths)` | method | Builds visible `CollectionRowState` rows honouring expansion. |

Important detail: **paths are slash-separated names** (`"Props/Gun"`), rooted at
the scene's root collection. The root itself is stored under path `""`.

### `layer_manager_controller.py` — Controller

Class `LayerManagerController`:

| Member | Kind | Purpose |
|--------|------|---------|
| `model` | attr | The `LayerManagerLogic` instance. |
| `pending: dict` | attr | Staged changes: `{view_layer_name: {path: {flag: state}}}`. |
| `refresh(context)` | method | Rebuild cache and force redraw (`on_refresh` hook). |
| `mark_dirty()` | method | Delegates to `model.mark_dirty()` (cache-invalidation entry). |
| `get_rows_data(context, props)` | method | Live rows **overlaid with pending changes**. |
| `get_pending_count()` | method | Total number of staged flag changes. |
| `on_toggle_expand(props, path)` | method | Delegate expand/collapse to `props.toggle(path)`. |
| `on_toggle_flag(context, vl_name, path, flag)` | method | Stage a flag for a path and all descendants (live state inverted). |
| `_stage_flag(scene, vl_name, path, flag, new_state)` | method | Stage / un-stage a single flag, pruning no-op entries. |
| `_prune_pending(vl_name, path)` | method | Remove dead keys from `pending`. |
| `on_apply(context)` | method | Commit staging: refresh → write via map → retry → DFS fallback → one `view_layer.update()` per touched layer. |
| `on_cancel()` | method | Clear `pending`, redraw. |
| `on_override(context, source_vl_name)` | method | Copies source map (live + pending) to all other view layers. Returns count written. |
| `force_ui_redraw()` | method | Tags every `VIEW_3D` area for redraw. |
| `cleanup()` | method | Detaches all `UI_HOOKS` callbacks (sets them to `None`). |

#### Apply (`on_apply`) battle plan

1. `refresh_cache` — guards against stale structure.
2. For each pending view layer, try `apply_flag_states` (map path).
3. Failures → `refresh_cache` again → retry `apply_flag_states`.
4. Still failing → DFS fallback `apply_flags` (handles collections removed
   after the last cache build).
5. Call `view_layer.update()` **once** per touched view layer.
6. Clear `pending`, mark the cache dirty, redraw.

#### Override (`on_override`) logic

1. Guard: source view layer must exist; at least 2 view layers required.
2. Build `source_map` from the **live cache** for the source view layer.
3. Overlay any **pending** changes that target the source view layer.
4. For every other view layer, for every path present in both maps, write each
   flag that differs from the target's current state.
5. `view_layer.update()` once per touched layer.
6. Clear pending + mark dirty + redraw. Returns written count.

### `layer_manager_ui.py` — View

Module constants:

- `UI_HOOKS` — the callback dictionary (see [Hooks](#ui_hooks)).
- `FLAGS = ("EXCLUDE", "HOLDOUT", "INDIRECT")` — display/write order.
- `FLAG_ICONS` — icon pairs `(off, on)` per flag.
- `FLAG_BLOCK_W = 6.5` — fixed width in `ui_units_x` for the three flag cells.

Helper functions:

- `_view_layer_items(self, context)` — enum items for every view layer.
- `_resolve_view_layer(context, props, view_layers)` — returns the chosen /
  active / first view layer, repairing stale selections.

Blender classes:

| Class | Type | Purpose |
|-------|------|---------|
| `LM_ExpandItem` | `PropertyGroup` | One expanded collection path. |
| `LM_Props` | `PropertyGroup` | WindowManager state: `expanded` (collection of `LM_ExpandItem`) + `view_layer_choice` (EnumProperty). Has `toggle(path)`. |
| `LM_OT_toggle_expand` | Operator | Expand/collapse a row. |
| `LM_OT_toggle_flag` | Operator | Stage a flag change (holds `view_layer_name`, `path`, `flag`). |
| `LM_OT_refresh` | Operator | Force cache refresh + redraw. |
| `LM_OT_apply_flags` | Operator | Commit staging ("OK"). |
| `LM_OT_cancel_flags` | Operator | Discard staging ("CANCEL"). |
| `LM_OT_override_flags` | Operator | Run override; reports written count. |
| `LAYERMAN_PT_MainPanel` | Panel | Main sidebar UI. |

Registration:

- `classes` tuple — canonical registration order (register) / reverse order
  (unregister).
- `register_properties()` / `unregister_properties()` — add / remove
  `WindowManager.lm_props`.
- `register()` / `unregister()` — safe, exception-tolerant bulk registration.

### `models/collection_state.py` — Data transfer objects

- `CollectionRowState` (dataclass) fields:
  - `path: str` — slash-separated path (`"Props/Gun"`).
  - `name: str` — collection name.
  - `depth: int` — nesting depth.
  - `has_children: bool`
  - `expanded: bool`
  - `flags: dict[str, dict[str, bool]]` — `{view_layer_name: {flag: state}}`.

---

## Data Flow

### Draw cycle

```
Panel.draw(context)
   │  UI_HOOKS["get_rows_data"](context, props)
   │        Controller.get_rows_data()
   │          ├─ model.build_rows(scene, expanded_paths)  (live state)
   │          └─ overlay pending changes onto rows
   │  UI_HOOKS["get_pending_count"]()  → pending_count label + button enablement
   ▼
render rows: disclosure triangle + name + 3 flag toggle buttons (fixed width)
```

### Staging a flag change

```
User clicks flag button
   │  LM_OT_toggle_flag.execute()
   │     UI_HOOKS["on_toggle_flag"](context, vl_name, path, flag)
   ▼
Controller.on_toggle_flag()
   ├─ live = model.get_live_flag_state(...)      (ensure_fresh builds cache on demand)
   ├─ effective = pending.get(flag, live[flag]); new_state = not effective
   ├─ _stage_flag(parent)                        (prunes if == live)
   └─ for each descendant path: _stage_flag(child, flag, new_state)
   └─ force_ui_redraw()
```

### Committing

```
OK button → LM_OT_apply_flags → UI_HOOKS["on_apply"](context)
   → Controller.on_apply() → [see Apply battle plan] → pending cleared
```

---

## Caching & Invalidation

Two parallel caches inside `LayerManagerLogic`:

1. `cache` — flag states for instant reads (`get_live_flag_state`,
   `get_descendant_paths`, `build_rows`, `on_override`).
2. `layer_collections` — resolved `LayerCollection` objects for O(1) writes
   without searching the tree (`apply_flag_states`).

Both are rebuilt together by `refresh_cache()` in a single post-order walk of
every view layer's `layer_collection` root.

`cache_dirty` starts `True`. It is set to `True` (invalidated) by:

- `Controller.mark_dirty()` — called from `__init__._on_invalidation`
  (`depsgraph_update_post`) and `_on_undo_redo` (`undo_post`, `redo_post`,
  `load_post`).
- `Controller.on_apply` and `Controller.on_override` after commits.
- Model construction.

`ensure_fresh()` performs a lazy rebuild on the next read; `refresh()`
(UI refresh button) rebuilds eagerly. `on_apply` additionally forces a
`refresh_cache` **before** writing, in case the cached structure is stale
(e.g. a collection was deleted since the last draw).

---

## Core Concepts

### Paths

Collections are addressed by slash-separated names from the scene root, e.g.
`"Props/Gun/Barrel"`. The root collection itself has the path `""`.

### Flags

Three boolean flags per LayerCollection, matching Blender's render settings:

| Flag | Blender property |
|------|------------------|
| `EXCLUDE` | `layer_collection.exclude` |
| `HOLDOUT` | `layer_collection.holdout` |
| `INDIRECT` | `layer_collection.indirect_only` |

### Staging semantics

- `pending` is keyed by `{view_layer_name: {path: {flag: state}}}`.
- A staged flag equal to the live state is **removed** (no-op pruning) — so
  toggling back and forth returns to zero pending changes.
- Toggling a parent sets the **same state** on every descendant path.
- Toggling again while pending inverts **the pending value** (not the live
  value), so behaviour is consistent even if the live state changed meanwhile.

### `UI_HOOKS`

The Controller writes its bound methods into `layer_manager_ui.UI_HOOKS` in
its constructor and clears them in `cleanup()`. The View reads these hooks; if
a hook is `None`, the corresponding button is inert. Draw-time hooks
(`get_rows_data`, `get_pending_count`) and a missing `props` / `lm_props`
cause the drawn "not registered" fallback label.

| Key | Signature | Owner |
|-----|-----------|-------|
| `get_rows_data` | `(context, props) -> list[CollectionRowState]` | Controller |
| `get_pending_count` | `() -> int` | Controller |
| `on_toggle_expand` | `(props, path)` | Controller |
| `on_toggle_flag` | `(context, view_layer_name, path, flag)` | Controller |
| `on_apply` | `(context)` | Controller |
| `on_cancel` | `()` | Controller |
| `on_refresh` | `(context)` | Controller |
| `on_override` | `(context, source_view_layer_name) -> int` | Controller |

---

## Extension Guide

### Add a new collection flag

1. **Model** (`layer_manager_logic.py`): add the property read in
   `get_flag_state()` and a branch in `_set_flag()`.
2. **View** (`layer_manager_ui.py`): add the flag name to `FLAGS`
   (controls column order), and an `(off, on)` entry in `FLAG_ICONS`.
3. **Operator**: extend `LM_OT_toggle_flag.flag` EnumProperty items so the
   new flag can be passed through.

No Controller or Model logic changes are required for reads/writes — both
iterate `FLAGS`-agnostic dictionaries.

### Add a new UI hook

1. Add the key to `UI_HOOKS` in `layer_manager_ui.py`.
2. Bind a bound method in `LayerManagerController.__init__`.
3. Add a menu button / operator that invokes `UI_HOOKS["your_key"]`.

### Add a new operator action

Add `LM_OT_*` operator that calls into the relevant `UI_HOOKS` entry, then
register it by appending to the `classes` tuple in `layer_manager_ui.py`.

### Add a new DTO

Extend `models/collection_state.py` with a `@dataclass`. Keep it free of
`bpy` imports so it stays unit-testable outside Blender.

---

## Testing

The Model layer (`LayerManagerLogic`) and the DTOs (`CollectionRowState`) have
**no View or Controller imports**, so they are the natural unit-test targets.
The `__pycache__` bytecode in `models/` indicates the add-on has been imported
under CPython 3.13/3.14. There is currently no committed test suite.

Suggested approach without a Blender runtime:

- Unit-test path building/parsing helpers and `_is_in_tree` with mock
  objects (duck-typed `collection.children`, `layer_collection.children`).
- Test `CollectionRowState` construction directly.

For integration tests, run the add-on inside a Blender 5.0+ Python environment
(`blender --background --python …`) and exercise the operators via
`bpy.ops.*`.

---

## Conventions

- **Python 3** type hints are used throughout (e.g. `dict[str, dict[str, bool]]`,
  `list[CollectionRowState]`). Note `None | type` is used for "collection or
  None" in `get_collection_by_path`.
- **No comments are added to source** beyond the existing module/class
  docstrings, unless explicitly requested.
- Modules own their `bpy` usage: only `layer_manager_logic.py` talks to
  `LayerCollection`/`Collection`/`Scene` internals; `layer_manager_ui.py`
  handles registration and aliasing to hooks.
- Registration order must follow the `classes` tuple and the
  View-then-Controller sequence in `__init__.py`.
- Each module has a module-level docstring describing its MVP role.
- Bump `bl_info["version"]` and `bl_info["blender"]` with feature changes.

---

## Version History

| Version | Notes |
|---------|-------|
| 1.0 | Initial release. |
| 1.1 | Reworked UI (fixed-width flag cells, per-view-layer selector) and Controller (staged apply with map + DFS fallback, override feature, cache invalidation via Blender handlers). |