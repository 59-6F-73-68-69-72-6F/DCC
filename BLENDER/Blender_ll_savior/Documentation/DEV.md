# Light Link Savior — Developer Documentation

Save and restore the **light linking** state of scene lights from a temporary JSON stash.

- **Version:** 1.0.1
- **Blender requirement:** ≥ 4.0 (light linking feature)
- **Python:** 3.10+ (type-hint syntax `tuple[...]`, `set[str]`)

---

## 1. Overview

`Light Link Savior` lets a user capture the current light linking setup of all scene
lights, then re-apply it later. The state is persisted as a JSON file inside the
addon's own `temp/` folder, next to where the addon is installed.

The flow follows a small layered design with a single direction of dependency:

```
User clicks button
        │
        ▼
ll_savior_ui ──► ll_savior_controller ──► ll_savior_logic
 (operators)        (2 thin functions)      (core / Blender & FS)
        ▲
        └────────────── __init__.py (addon registration entry point)
```

## 2. File map

| File                    | Role                                                        | Public API                                   |
| ----------------------- | ----------------------------------------------------------- | -------------------------------------------- |
| `__init__.py`           | Addon entry point, `bl_info`, enable/disable lifecycle      | `register()`, `unregister()`                 |
| `ll_savior_ui.py`       | Operators + sidebar panel, Blender class registration       | `register()`, `unregister()`, operators/panel|
| `ll_savior_controller.py` | Controller layer: thin delegation to the logic               | `save_light_links()`, `restore_light_links()`|
| `ll_savior_logic.py`    | Core: scan scene, stash/save to JSON, re-establish links    | `stash_light_links()`, `load_stash()`, `delete_stash()`, `re_establish_light_links()` |

## 3. Installation & activation (dev)

1. Place the `light_link_savior` folder in your Blender addons directory.
2. Enable it in **Edit > Preferences > Add-ons** (category **Lighting**).
3. UI appears in `3D Viewport > Sidebar (N) > Lighting > LIGHT LINK SAVIOR`.

## 4. Architecture & data flow

### 4.1 Save

```
LM_OT_SaveLightLink.execute()
 └─ ll_savior_controller.save_light_links()
     └─ ll_savior_logic.stash_light_links()          # no return value; writes JSON
         ├─ iterate bpy.context.scene.objects (type == 'LIGHT')
         ├─ per light: stash receiver links then blocker links
         └─ write JSON via _stash_file_path()
```

### 4.2 Restore

```
LM_OT_RestoreLightLink.execute()
 ├─ guard: os.path.exists(stash_file_path)  # path duplicated in UI (see §8)
 │    if missing → report ERROR, return COMBINED {"CANCELLED"}
 └─ ll_savior_controller.restore_light_links()
     ├─ ll_savior_logic.load_stash()                    # {} on missing/corrupt file
     ├─ ll_savior_logic.re_establish_light_links(receiver, blocker)
     │    per light, only for sides present in the stash:
     │      clear that side's collection → view_layer.update() → idempotent re-link
     └─ ll_savior_logic.delete_stash()                  # "consume-once" behaviour
```

## 5. Stash format (JSON)

File: `<addon_dir>/temp/light_linking_stash.json`

```json
{
  "receiver": {
    "<light name>": [
      ["collections", "<child collection name>", "INCLUDE"],
      ["objects", "<object name>", "EXCLUDE"]
    ]
  },
  "blocker": { ... }
}
```

- Top level has two maps keyed by **light object name**: `receiver` and `blocker`.
- Each value is a list of `[kind, name, state]` triplets where `kind` is
  `"collections"` or `"objects"` and `state` is `"INCLUDE"` / `"EXCLUDE"`.
- Objects/collections are referenced by **name** only (see §8 limitations).

## 6. Blender light linking API used

- `Object.light_linking` → `Lightlink`:
  - `.receiver_collection`, `.blocker_collection` → `Collection`.
- Linking an object/collection into one of those collections creates a wrapper in
  the collection's `objects` / `children`, with a parallel entry in
  `collection_objects` / `collection_children` that carries the per-member
  `.light_linking.link_state` (`INCLUDE` / `EXCLUDE`).

Helpers (`ll_savior_logic.py`):

| Helper                    | Purpose                                                  |
| ------------------------- | -------------------------------------------------------- |
| `_link_state_of(wrapper)` | Read `INCLUDE`/`EXCLUDE` from a parallel wrapper (default `INCLUDE`) |
| `_set_link_state(wrapper, state)` | Write the state back onto a wrapper               |
| `_clear_members(col)`     | Unlink all objects and child collections                 |
| `_restore_members(col, linked)` | Relink from `[kind, name, state]` triplets, dropping unresolved names |
| `_ensure_link_collection(light, suffix)` | Return the receiver/blocker collection, creating it if missing |
| `_stash_file_path()`      | Resolve `<addon_dir>/temp/light_linking_stash.json` (creates folder) |

## 7. Stash lifecycle

1. **Save** → overwrite the JSON with the current scene state.
2. **Restore** → read JSON (missing/corrupt file degrades to empty maps),
   re-establish the links, then **delete** the file.
3. Consequence: after a successful restore the stash is gone; a second Restore
   without a prior Save reports *“No saved light links to restore”*.

## 8. Known limitations

- **Name-based persistence:** links are stored by object/collection name. Renaming
  or deleting a target silently drops that rule (`_restore_members` does `continue`).
  Duplicate names across collections can also resolve to the wrong target via `find()`.
- **Duplicated stash path:** `stash_file_path` is computed in the UI
  (`ll_savior_ui.py:14-15`) **and** in the logic (`_stash_file_path` in
  `ll_savior_logic.py:86-90`). If one changes, the Restore guard in the UI can diverge
  from the real file location.
- **Consume-once restore:** `delete_stash()` removes the stash after use.
- **Stale annotation:** *(fixed in 1.0.1)* `stash_light_links()` no longer carries the wrong
  `-> tuple[dict, dict]` annotation.
- **No undo/redo:** operator mutations are not undoable.
- **Debug prints:** the logic layer prints to the console (`_ensure_link_collection`,
  `re_establish_light_links`, `delete_stash`).
- **Duplicated stash blocks:** the receiver and blocker branches in
  `stash_light_links()` are near-identical and could be factored into one helper.

## 8.1 Changes in 1.0.1

- **Idempotent restore:** `_restore_members()` now checks membership before linking
  (`find() < 0` → link), then always asserts the saved state, and skips duplicate
  triplets. Fixes `RuntimeError: ... already in collection` for scene setups where
  multiple lights share the same linking collection (or duplicated lights).
- **Per-side restore:** `re_establish_light_links()` clears/rebuilds each light
  linking side (receiver/blocker) independently and only when that side exists in
  the stash (`is not None`), so blocker links added after Save are no longer wiped
  when only a receiver side was stashed.
- **Depsgraph flush:** a `bpy.context.view_layer.update()` runs after each clear so
  membership lists are fresh before re-linking (Blender 5.x robustness).

## 9. Conventions

- Docstrings in **English**; module-level docstring + one per public function/operator.
- Blender class naming: `LM_*` operator prefix, `LIGHTLINKING_PT_*` panel prefix.
- Each module owns its `register()` / `unregister()`; unregister in reverse order.
- Keep the dependency direction `ui → controller → logic` (no cycles, no global
  mutable state shared across modules).

## 10. Extending

To add a new action:

1. Add the operator in `ll_savior_ui.py` with a `bl_idname = "lm.<action>"`.
2. Delegate its `execute()` to a new function in `ll_savior_controller.py`.
3. Implement the actual work (Blender data / FS) in `ll_savior_logic.py`.
4. Register/unregister the class in the UI module's `classes` tuple.

---

© 2026 Rudy Leti. All rights reserved.