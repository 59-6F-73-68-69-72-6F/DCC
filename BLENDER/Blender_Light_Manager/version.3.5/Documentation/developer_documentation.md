# Blender Light Manager v3.0 — Developer Documentation

## Architecture Overview

The add-on follows the **Model-View-Controller (MVC)** architectural pattern.

```
light_manager_main.py          (Bootstrap / Entry Point)
       │
       ├──► light_manager_controller.py   (Controller)
       │         │
       │         ├──► light_manager_logic.py   (Model)
       │         │         │
       │         │         └──► models/light_state.py   (DTO)
       │         │
       │         └──► light_manager_ui.py   (View)
       │
       └──► light_manager_ui.py   (View registration)
```

### Layer Responsibilities

| Layer | File | Role |
|---|---|---|
| **Model** | `light_manager_logic.py` + `models/light_state.py` | Pure data/logic. Performs all direct Blender `bpy` operations (CRUD, visibility, solo, attribute editing). Has **zero imports** from View or Controller. |
| **View** | `light_manager_ui.py` | Blender UI components: custom properties, Operators, Panel. Delegates logic to the Controller via the `UI_HOOKS` callback dictionary. |
| **Controller** | `light_manager_controller.py` | Mediates Model ↔ View. Registers callbacks into `UI_HOOKS`, manages a depsgraph update handler for auto-refresh, pushes status/stats messages to the UI. |
| **Bootstrap** | `light_manager_main.py` | `bl_info` metadata, `register()` / `unregister()` add-on lifecycle. Creates the Model and Controller instances. |

---

## File Breakdown

### `light_manager_main.py` — Entry Point

- Defines `bl_info` (add-on metadata for Blender).
- `register()`: Instantiates `LightManagerLogic` and `LightManagerController`, registers UI classes via `lmui.register()`.
- `unregister()`: Cleans up the controller (removes Blender handlers, nullifies hooks), then unregisters UI classes.
- Module-level `controller_instance` holds the singleton `LightManagerController`.

### `light_manager_logic.py` — Model Layer

**Class: `LightManagerLogic`**

| Method | Description |
|---|---|
| `get_active_view_layer()` | Returns the name of the currently active view layer (checks 3 fallback sources). |
| `get_lights(view_layer_name)` | Returns a sorted `list[LightState]` of all managed lights. Auto-detects solo mode if exactly one light is visible. |
| `create_light(name, type)` | Creates a new light with dedicated collection (`C_`) and locator (`World_`). Returns the final naming convention string. |
| `rename_light(old_name, new_name)` | Renames collection, locator, light object, and data block atomically. |
| `delete_light(light_name)` | Removes collection (with `do_unlink`), locator, and light object. |
| `set_light_visibility(light_name, is_visible, view_layer_name)` | Shows/hides via collection exclusion. |
| `set_light_solo(light_name, is_soloed, view_layer_name, all_light_names)` | Snapshots visibility states when soloing, restores on unsolo. |
| `set_light_attribute(light_name, attr_name, value)` | Sets attributes on the object or its data block. Special handling for `lightgroup`. |

**Naming Prefixes (constants):**

| Constant | Value | Purpose |
|---|---|---|
| `PREFIX_lgt` | `"Lgt_"` | Light object names in Blender |
| `PREFIX_col` | `"C_"` | Collection names containing a light + locator |
| `PREFIX_loc` | `"World_"` | Locator (empty transform) object names |

### `models/light_state.py` — Data Transfer Object

**Dataclass: `LightState`**

Contains all relevant properties of a managed light: `name`, `obj`, `is_visible`, `is_soloed`, `type`, `color`, `exposure`, `use_temperature`, `temperature`, `radius`, `use_shadow`, `lightgroup`.

### `light_manager_controller.py` — Controller Layer

**Class: `LightManagerController`**

- Owns a reference to the `LightManagerLogic` model.
- Populates the `lmui.UI_HOOKS` dictionary with callback methods.
- Manages a `_depsgraph_handlers` list for Blender event handler lifecycle.
- `register_handlers()` / `unregister_handlers()`: Add/remove depsgraph update post handler that auto-refreshes viewports when light data changes.
- `force_ui_redraw()`: Tags all `VIEW_3D` areas for redraw.
- `set_status(msg)`: Pushes a status string to `wm.lm_status_info`.
- `get_ui_lights(view_layer_name)`: Enriches `LightState` data with Blender objects and calculates stats (total/visible/soloed), stored in `wm.lm_stats_info`.
- `cleanup()`: Tears down handlers and nullifies all `UI_HOOKS` callbacks.

### `light_manager_ui.py` — View Layer

**Hook System — `UI_HOOKS` dict**

A global dictionary of callbacks populated by the Controller. View code calls these hooks without importing the Controller directly.

| Hook Key | Signature | Purpose |
|---|---|---|
| `on_create` | `(name, light_type)` | Create a light |
| `on_rename` | `(old_name, new_name)` | Rename a light |
| `on_delete` | `(light_name)` | Delete a light |
| `on_visibility_toggle` | `(light_name, state)` | Toggle visibility |
| `on_solo_toggle` | `(light_name, state)` | Toggle solo mode |
| `on_attribute_changed` | `(light_name, attr_name, value)` | Change an attribute |
| `get_lights_data` | `(view_layer_name)` | Retrieve light data |

**Operators (Blender `bpy.types.Operator` subclasses)**

| Class | `bl_idname` | Action |
|---|---|---|
| `LM_OT_CreateLight` | `lm.create_light` | Creates a new light |
| `LM_OT_RenameLight` | `lm.rename_light` | Renames the active light |
| `LM_OT_DeleteLight` | `lm.delete_light` | Deletes a light |
| `LM_OT_ToggleVisibility` | `lm.toggle_visibility` | Toggles light visibility |
| `LM_OT_ToggleSolo` | `lm.toggle_solo` | Toggles solo mode |
| `LM_OT_SelectLight` | `lm.select_light` | Selects and activates a light |

**Panel**

| Class | Location |
|---|---|
| `LIGHTMAN_PT_MainPanel` | `VIEW_3D` → Sidebar → Light Manager tab |

**Custom Properties**

Registered on `bpy.types.WindowManager`:
- `lm_entry_name` — String property for light name input
- `lm_entry_type` — Enum property (POINT, SUN, SPOT, AREA)
- `lm_search_filter` — String property for search/filter
- `lm_stats_info` — Read-only stats string
- `lm_status_info` — Read-only status string

Registered on `bpy.types.Object`:
- `lm_lightgroup` — Enum property synced to Blender's native `lightgroup`

---

## Data Flow

```
User clicks button in UI
       │
       ▼
Operator.execute() ──► UI_HOOKS["on_*"](...)
                               │
                               ▼
               LightManagerController.on_*(...)
                               │
                               ├──► model.create_light(...)
                               ├──► set_status(msg)
                               └──► force_ui_redraw()
```

## Event-Driven Auto-Refresh

The controller registers a `depsgraph_update_post` handler. When any `bpy.types.Light` data block or `bpy.types.Object` with `type == 'LIGHT'` is updated externally (e.g., user modifies a light in the viewport), all 3D View areas are tagged for redraw.

---

## Naming Conventions

- **Files:** `light_manager_*.py` prefix for consistency.
- **Classes:** PascalCase — `LightManagerLogic`, `LightManagerController`.
- **Methods/Functions:** snake_case — `get_active_view_layer`, `force_ui_redraw`.
- **Constants:** UPPER_CASE — `PREFIX_lgt`, `PREFIX_col`, `UI_HOOKS`.
- **Operators:** `LM_OT_*` (Blender standard: `{Addon}_{Type}_{Name}`).
- **Panel:** `LIGHTMAN_PT_*` (Blender standard: `{Addon}_PT_{Name}`).
- **Custom Properties:** `lm_*` prefix (lowercase, namespaced with add-on initials).

---

## How to Extend

### Add a new UI control

1. Add a callback key to `UI_HOOKS` in `light_manager_ui.py`.
2. Add the handler method in `LightManagerController.__init__()`.
3. Add the UI element in `LIGHTMAN_PT_MainPanel.draw()`.

### Add a new Blender operator

1. Create a new class inheriting `bpy.types.Operator` in `light_manager_ui.py`.
2. Add it to the `classes` tuple.
3. Use `UI_HOOKS` to delegate logic to the Controller.

### Add a new light property

1. Add the field to `LightState` dataclass in `models/light_state.py`.
2. Read the value in `LightManagerLogic.get_lights()`.
3. Write the value in `LightManagerLogic.set_light_attribute()`.
4. Display it in `LIGHTMAN_PT_MainPanel.draw()`.
