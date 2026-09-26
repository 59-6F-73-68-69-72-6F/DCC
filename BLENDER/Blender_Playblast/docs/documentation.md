# Playblast — Developer Manual

---

## Index

- [1. Project Overview](#1-project-overview)
- [2. Project Structure](#2-project-structure)
- [3. Architecture](#3-architecture)
- [4. Modules / Function Reference](#4-modules--function-reference)
  - [4.1 `__init__.py`](#41-__init__py)
  - [4.2 `playblast_logic.py`](#42-playblast_logicpy)
  - [4.3 `playblast_ui.py`](#43-playblast_uipy)
- [5. Data Model (WindowManager Properties)](#5-data-model-windowmanager-properties)
- [6. Registration Lifecycle](#6-registration-lifecycle)
- [7. Rendering Workflow](#7-rendering-workflow)
- [8. Error Handling & Edge Cases](#8-error-handling--edge-cases)
- [9. Extension Points](#9-extension-points)
- [10. Known Limitations](#10-known-limitations)
- [11. Author & Attribution](#11-author--attribution)

---

## 1. Project Overview

**Playblast** is a Blender 5.0+ add-on that renders an OpenGL viewport
playblast and saves the resulting PNG image sequence to a user-specified
folder. The UI lives in the **3D Viewport Sidebar → "Animation"** tab.

This manual is a **developer reference**. It documents the internal
architecture, every function and method, the data model, and how to extend
the add-on. For end-user installation and usage, see the concise usage notes
in this file under [Section 1.1](#11-quickstart).

### 1.1 Quickstart

1. Install the add-on via `Edit > Preferences > Add-ons > Install`.
2. In the 3D Viewport press `N` to open the Sidebar, select the **Animation** tab.
3. Type an **output Folder** path.
4. Set **Start** and **End** frames (auto-synced from the scene on first load).
5. Click **Create Playblast**.

---

## 2. Project Structure

```
Blender_Playblast/
├── __init__.py          # Add-on entry point: bl_info + register/unregister
├── playblast_logic.py   # Core rendering logic (PlayblastLogic)
├── playblast_ui.py      # UI layer: properties, operator, panel
└── docs/
    └── documentation.md # This developer manual
```

| File | Responsibility |
|---|---|
| `__init__.py` | Blender entry point; declares `bl_info`; delegates registration to the UI layer. |
| `playblast_logic.py` | Business logic: orchestrates the render and restores scene state. |
| `playblast_ui.py` | Presentation: window-manager properties, the create operator, and the sidebar panel. |

---

## 3. Architecture

The add-on follows a **three-layer separation of concerns**:

```
┌─────────────────────────────┐
│  __init__.py                │  Entry / registration
│  register() / unregister()  │
└──────────────┬──────────────┘
               │ delegates
┌──────────────▼──────────────┐
│  playblast_ui.py            │  Presentation
│  Properties / Operator /    │
│  Panel                      │
└──────────────┬──────────────┘
               │ instantiates & calls
┌──────────────▼──────────────┐
│  playblast_logic.py         │  Business logic
│  PlayblastLogic             │
└─────────────────────────────┘
```

- **Entry → UI**: `__init__.register()` imports and calls `playblast_ui.register()`.
- **UI → Logic**: `PLAYBLAST_OT_Create.execute()` instantiates `PlayblastLogic`
  and calls `make_playblast()`.
- **UI state** lives on `bpy.types.WindowManager` (registered properties),
  keeping the decoupled layers in sync without cross-imports of scene state.

Data flow is single-direction and dependency flows downward (UI depends on
Logic; Entry depends on UI; Logic depends only on `bpy`).

---

## 4. Modules / Function Reference

### 4.1 `__init__.py`

**Module docstring:** *Playblast add-on entry point.*

| Symbol | Type | Description |
|---|---|---|
| `bl_info` | `dict` | Add-on metadata: name, author, version, blender, location, description, category. |
| `directory` | `str` | Absolute path to the add-on folder; appended to `sys.path` at import. |
| `register()` | `function` | Import `playblast_ui` and invoke `playblast_ui.register()`. |
| `unregister()` | `function` | Invoke `playblast_ui.unregister()` and remove the add-on dir from `sys.path`. |

**`register()`**

```python
def register():
    """Register the Playblast add-on with Blender."""
    from . import playblast_ui
    playblast_ui.register()
```

- No arguments, no return value.
- A **local import** (`from . import playblast_ui`) is used to defer importing
  the UI module until registration time.

**`unregister()`**

```python
def unregister():
    """Unregister the Playblast add-on and clean up its sys.path entry."""
    from . import playblast_ui
    playblast_ui.unregister()
    if directory in sys.path:
        sys.path.remove(directory)
```

- Reverses registration and cleans up the module path so re-enabling the
  add-on does not accumulate stale path entries.

---

### 4.2 `playblast_logic.py`

**Module docstring:** *Core playblast rendering logic, decoupled from the UI layer.*

#### `class PlayblastLogic`

**Class docstring:** *Orchestrates an OpenGL viewport playblast, restoring scene state afterward.*

Encapsulates the save/restore of Blender scene state around a viewport render.
The class is intentionally thin — it manages the state bookkeeping while
delegating the actual render to Blender's `bpy.ops.render.opengl`.

#### `PlayblastLogic.__init__(self)`

```python
def __init__(self):
    """Initialize placeholders for the scene state that will be saved and restored."""
    self._original_filepath: str
    self._original_file_format: str
    self._original_start: int
    self._original_end: int
```

- No arguments.
- Declares the four instance attributes that will hold the original scene
  values before the render mutates them.

#### `PlayblastLogic.make_playblast(self, output_dir, start, end)`

```python
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
    ...
```

**Parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `output_dir` | `str` | Yes | Root directory; a timestamped subfolder is created inside it. |
| `start` | `int` | Yes | First frame of the playblast range. |
| `end` | `int` | Yes | Last frame of the playblast range (must be ≥ `start`). |

**Behavior**

1. **Guard:** raises `ValueError` if `start > end`.
2. **Snapshot:** stores `render.filepath`, `render.image_settings.file_format`,
   `scene.frame_start`, and `scene.frame_end` in the `_original_*` fields.
3. **Mutate:** sets `scene.frame_start = start`, `scene.frame_end = end`,
   `render.image_settings.file_format = 'PNG'`, and writes the output path to
   a timestamped subfolder: `f"{output_dir}/{timestamp}/playblast_"` where the
   timestamp is `datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")`.
4. **Render:** calls `bpy.ops.render.opengl(animation=True, view_context=True)`.
5. **Restore:** in a `finally` block, restores all four original values.
   Guarantees scene state is restored even if the render raises.

**Raises**

- `ValueError` — if `start` is greater than `end`.

**Notes**

- The timestamp uses `%Y-%m-%d_%H-%M-%S` (colon- and space-free) so the
  subfolder name is valid on Windows, Linux, and macOS.
- Blender appends the zero-padded frame number to the file name, producing
  files like `playblast_0001.png`.

---

### 4.3 `playblast_ui.py`

**Module docstring:** *Blender UI layer: properties, operators, and the sidebar panel for Playblast.*

#### `register_properties()`

```python
def register_properties():
    """Register all window-manager properties used by the Playblast UI."""
```

- No arguments, no return value.
- Registers four `WindowManager` properties (see [Section 5](#5-data-model-windowmanager-properties)).

#### `unregister_properties()`

```python
def unregister_properties():
    """Delete all window-manager properties registered by the playblast UI."""
```

- No arguments, no return value.
- Deletes the same four properties via `del bpy.types.WindowManager.<prop>`.

#### `class PLAYBLAST_OT_Create(bpy.types.Operator)`

**Class docstring:** *Render a viewport playblast and save PNG frames to the chosen folder.*

| Attribute | Value |
|---|---|
| `bl_idname` | `"playblast.create"` |
| `bl_label` | `"Create Playblast"` |

#### `PLAYBLAST_OT_Create.execute(self, context)`

```python
def execute(self, context):
    """
    Validate selection, then render the playblast to the chosen folder.

    Args:

    context: The current Blender context.

    Returns: {'FINISHED'} on success, {'CANCELLED'} on invalid input.
    """
```

**Parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `context` | `bpy.types.Context` | Yes | Current Blender context; used to reach the window manager. |

**Returns**

| Value | Condition |
|---|---|
| `{'CANCELLED'}` | The output path is empty or is not an existing directory. |
| `{'FINISHED'}` | The playblast render completed; reports an `INFO` message. |

**Behavior**

1. Reads `wm.playblast_output_path`, `wm.frame_start`, `wm.frame_end`.
2. Validates the output path exists (uses `os.path.isdir`). On failure,
   reports `ERROR` and returns `{'CANCELLED'}`.
3. Instantiates `PlayblastLogic` and calls
   `make_playblast(output_path, wm.frame_start, wm.frame_end)`.
4. Reports `INFO` with the output path and returns `{'FINISHED'}`.

#### `class PLAYBLAST_PT_Panel(bpy.types.Panel)`

**Class docstring:** *Sidebar panel for the Playblast tool.*

| Attribute | Value |
|---|---|
| `bl_label` | `"Playblast"` |
| `bl_idname` | `"PLAYBLAST_PT_playblast"` |
| `bl_space_type` | `"VIEW_3D"` |
| `bl_region_type` | `"UI"` |
| `bl_category` | `"Animation"` |

#### `PLAYBLAST_PT_Panel.draw(self, context)`

```python
def draw(self, context):
    """
    Draw the playblast sidebar panel, syncing the frame range from the scene.

    Args:
        context: The current Blender context used to access the scene and window manager.
    """
```

**Parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `context` | `bpy.types.Context` | Yes | Accessed for `context.scene` and `context.window_manager`. |

**Behavior**

1. **One-time sync:** if `wm.playblast_range_synced` is `False`, copies
   `scene.frame_start` / `scene.frame_end` into the window-manager properties
   and sets the flag to `True`. This seeds the Start/End fields from the scene
   on first draw, then lets the user override.
2. **Range guard:** if `wm.frame_start >= wm.frame_end`, forces
   `wm.frame_end = wm.frame_start + 1` so the display is never inverted.
3. **Layout:** draws a box with the output Folder field, Start/End fields,
   the **Create Playblast** button, and a copyright footer.

#### `register()` / `unregister()`

```python
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
```

- `classes` is a tuple: `(PLAYBLAST_OT_Create, PLAYBLAST_PT_Panel)`.
- `register()` registers properties first, then classes.
- `unregister()` unregisters classes in reverse order, then properties.

---

## 5. Data Model (WindowManager Properties)

All add-on state is stored on `bpy.types.WindowManager`. These are the
registered properties that thread state between the panel, the operator, and
the logic layer.

| Property | Type | Default | Range | Purpose |
|---|---|---|---|---|
| `playblast_output_path` | `StringProperty` | `""` | — | Output folder (`subtype='DIR_PATH'`). |
| `frame_start` | `IntProperty` | `1` | `min=-100` | First frame of the playblast range. |
| `frame_end` | `IntProperty` | `250` | `min=-100` | Last frame of the playblast range. |
| `playblast_range_synced` | `BoolProperty` | `False` | — | Guards the one-time scene→UI range sync. |

**Why `WindowManager`?** These values are UI/session state that must be
reachable from both the panel `draw()` and the operator `execute()`. Storing
them on the `WindowManager` keeps them global to the session and independent
of any particular scene.

---

## 6. Registration Lifecycle

```
Blender enables add-on
        │
        ▼
__init__.register()
        │  local import + delegate
        ▼
playblast_ui.register()
        │
        ├── register_properties()   → adds 4 WindowManager props
        └── for cls in classes      → register_class(PLAYBLAST_OT_Create)
                                      register_class(PLAYBLAST_PT_Panel)
```

Disabling reverses the process in `playblast_ui.unregister()` (classes
first, reverse order, then properties) and `__init__.unregister()` (also
removes the add-on directory from `sys.path`).

---

## 7. Rendering Workflow

```
User clicks "Create Playblast"
        │
        ▼
PLAYBLAST_OT_Create.execute()
        │  validate output_path (os.path.isdir)
        ▼
PlayblastLogic().make_playblast(output_path, frame_start, frame_end)
        │
        ├── guard: start > end → ValueError
        ├── snapshot: filepath, format, frame_start, frame_end
        ├── mutate:  PNG + timestamped folder + new range
        ├── render:  bpy.ops.render.opengl(animation=True, view_context=True)
        └── finally: restore filepath, format, frame range
```

**Key guarantee:** even if the OpenGL render raises, the `finally` block
restores the scene's original render settings and frame range.

---

## 8. Error Handling & Edge Cases

| Scenario | Handling |
|---|---|
| Output folder missing / not a directory | `PLAYBLAST_OT_Create` reports `ERROR` and returns `{'CANCELLED'}`. |
| `start > end` | `make_playblast` raises `ValueError`. |
| Inverted range in UI | `PLAYBLAST_PT_Panel.draw()` clamps `frame_end = frame_start + 1`. |
| Render raises (e.g. GL error) | `finally` restores original scene state; exception propagates. |
| Re-enable add-on repeatedly | `unregister()` removes `sys.path` entry and all properties to avoid duplication. |

---

## 9. Extension Points

The clean layer separation makes extension straightforward:

- **Add a new operator** — define a `bpy.types.Operator` subclass in
  `playblast_ui.py` and add it to the `classes` tuple.
- **Change output naming** — modify the file-prefix / timestamp logic in
  `PlayblastLogic.make_playblast()`.
- **Support other formats** — replace the `'PNG'` assignment in
  `make_playblast()` with a configurable format read from a new property.
- **Alternate folder picking** — a new browse operator can write to
  `wm.playblast_output_path`; the create operator reads the same property.

---

## 10. Known Limitations

- **File-browser dialog requires GPU/EGL context.** The `DIR_PATH` field's
  built-in browser draws a GPU-backed window. In headless or GPU-limited
  environments this may emit `EGL_BAD_ALLOC`. This is **environmental**, not
  an add-on bug; use the typed Folder field instead.
- **Single active scene.** The logic operates on `bpy.context.scene`; it does
  not support multi-scene selections.
- **Synchronous render.** `make_playblast` blocks until the playblast finishes.
- **No progress reporting.** Long playblasts show only Blender's native render
  progress.

---

## 11. Author & Attribution

**Author:** Rudy Leti

**Version:** 1.0.0

**Requires:** Blender 5.0 or newer

**Category:** Animation

**© 2026 Rudy Leti. All Rights Reserved.**
