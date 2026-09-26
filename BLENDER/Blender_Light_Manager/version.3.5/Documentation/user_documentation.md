# Blender Light Manager v3.0 — User Documentation

## Overview

The **Blender Light Manager** is a native Blender add-on for managing scene lights from a single panel. It provides a streamlined interface for creating, selecting, renaming, deleting, and editing light properties, as well as visibility and solo controls — all from the 3D View sidebar.

**Author:** Rudy Leti  
**Version:** 3.0.0  
**Blender:** 4.0+  
**Category:** Lighting

---

## Installation

1. Download the add-on folder.
2. In Blender, go to **Edit → Preferences → Add-ons**.
3. Click **Install…** and select the add-on zip, or copy the folder to Blender's `scripts/addons/` directory.
4. Search for **"Light Manager"** in the add-on list and enable it.
5. The panel appears in the **3D View → Sidebar → Light Manager** tab.

---

## Interface Overview

The panel is located in the 3D Viewport sidebar (`N` key to toggle) under the **Light Manager** tab.

### 1. Status & Stats Bar

Displays current status messages and a summary line:
```
Total: 5 | Visible: 3 | Solo: 1
```

### 2. Creation Controls

- **Name** — Enter a base name for the new light.
- **Type** — Choose light type: `Point`, `Sun`, `Spot`, or `Area`.
- **Create** — Creates a new light with the chosen name and type.
- **Rename** — Renames the currently selected light to the entered name.

> **Note:** If no name is entered, the light type string is used as the default name (e.g., `"Point.000"`).

### 3. Search/Filter Bar

Type to filter the light list by name. The list updates in real time as you type.

### 4. Light Data Table

Each row represents a managed light with the following controls:

| Control | Description |
|---|---|
| **Name** (clickable) | Selects and activates the light in the viewport. |
| **Visibility** (eye icon) | Toggles the light on/off in the current view layer. Hidden lights are marked with a crossed-out eye. |
| **Solo** (`S` button) | Isolates the light — hides all others. Press again to restore previous visibility state. Only one light can be soloed at a time. |
| **Light type icon** | Visual indicator of the light type (Point, Sun, Spot, Area). |
| **Color** | RGB color picker for the light. |
| **Exposure** | Exposure value slider. |
| **Use Temperature** (checkbox) | Enables/disables color temperature control. |
| **Temperature** | Color temperature in Kelvin (visible when temperature is enabled). |
| **Shadow Softness** | Radius/softness of the shadow (not available for Sun and Area types — shows `-`). |
| **Use Shadow** (checkbox) | Enables/disables shadow casting. |
| **Light Group** (dropdown) | Assigns the light to a view-layer light group (AOV). Shows all existing groups across all view layers. |
| **Delete** (trash icon) | Permanently removes the light and its collection from the scene. |

---

## Features

### Light Hierarchy

Each managed light follows a consistent hierarchy in the Outliner:

```
Collection "C_<name>"
└── Locator "World_<name>" (PLAIN_AXES empty)
    └── Light "Lgt_<name>"
```

This structure ensures clean organisation and easy transform manipulation via the locator.

### View Layer Awareness

All visibility and solo operations are per-view-layer. You can have a light visible in one view layer and hidden in another.

### Solo Mode

- Click the **S** button to solo a light: all other lights are hidden.
- The pre-solo visibility state is snapshotted, so clicking **S** again restores exactly how things were before.
- If only one light is visible among many, it is automatically marked as soloed.

### Auto-Refresh

The panel automatically refreshes when you modify a light externally (e.g., in the Properties panel or Outliner). No manual refresh is needed.

### Light Groups (AOV)

The **Light Group** dropdown lists all existing light groups from every view layer. Selecting a group assigns the light to it for AOV/Light Link workflows. Selecting **"None"** removes the assignment.

---

## Tips

- **Quick select:** Click any light name in the table to select and activate it in the viewport.
- **Batch rename:** Select a light, type a new name in the **Name** field, and click **Rename**. The collection, locator, and data block are all renamed automatically.
- **Collision-safe names:** If a name already exists, Blender appends a numeric suffix (`.000`, `.001`, etc.).
- **Delete is permanent:** Deleting a light removes its collection, locator, and data block entirely with full cleanup.

---

## Troubleshooting

| Issue | Solution |
|---|---|
| Panel not showing | Ensure the add-on is enabled in Preferences. Press `N` to open the sidebar in the 3D View. |
| Light not visible after creation | Check the view layer exclusion (visibility toggle). The light may be hidden in the current view layer. |
| Solo mode not restoring | Solo mode restores the state from when solo was **first** activated. If you manually change visibility while soloed, unsoloing reverts to the pre-solo snapshot. |
| Light group not appearing | Light groups must exist in at least one view layer. Create them in the **View Layer** properties first. |

---

## Uninstallation

Disable or remove the add-on via **Edit → Preferences → Add-ons** → search for **"Light Manager"** → uncheck or remove.
