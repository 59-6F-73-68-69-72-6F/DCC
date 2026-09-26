"""
Defines all Blender UI components: custom properties on WindowManager,
Blender Operators for user actions, and the main UI panel displayed in the
3D View sidebar. UI behaviour is delegated to the Controller through the
``UI_HOOKS`` callback dictionary.
"""

import bpy

UI_HOOKS = {
    "get_rows_data": None,
    "get_pending_count": None,
    "on_toggle_expand": None,
    "on_toggle_flag": None,
    "on_apply": None,
    "on_cancel": None,
    "on_refresh": None,
}
"""
Callback hooks populated by ``LayerManagerController``.
Keys:
    get_rows_data: Called with ``(context, props)`` to retrieve visible
        collection rows with their staged/effective flag states.
    get_pending_count: Called with no arguments; returns the number of
        staged flag changes awaiting apply.
    on_toggle_expand: Called with ``(props, path)`` to expand/collapse a
        collection row.
    on_toggle_flag: Called with ``(context, view_layer_name, path, flag)``
        to stage a flag change. Toggling a parent collection also stages
        the same change for all of its descendants.
    on_apply: Called with ``(context)`` to apply all staged changes.
    on_cancel: Called with no arguments to discard all staged changes.
    on_refresh: Called with ``(context)`` to force a live-state cache refresh.
"""


class LM_ExpandItem(bpy.types.PropertyGroup):
    """Stores a single expanded collection path in the panel's UI state."""

    path: bpy.props.StringProperty(name="Path")


class LM_Props(bpy.types.PropertyGroup):
    """Window-manager state tracking which collection rows are expanded."""

    expanded: bpy.props.CollectionProperty(type=LM_ExpandItem)

    def toggle(self, path: str):
        """Toggle the expanded state of the row for ``path``."""
        for index, item in enumerate(self.expanded):
            if item.path == path:
                self.expanded.remove(index)
                return
        item = self.expanded.add()
        item.path = path


def split_n(layout: bpy.types.UILayout, count: int):
    """Split ``layout`` into ``count`` aligned columns and return them."""
    parts = []
    current = layout
    for i in range(count):
        if i == count - 1:
            parts.append(current)
        else:
            split = current.split(factor=1.0 / (count - i), align=True)
            first = split.column()
            current = split.column()
            parts.append(first)
    return parts


class LM_OT_toggle_expand(bpy.types.Operator):
    """Expand or collapse a collection's children in the panel."""
    bl_idname = "lm.toggle_expand"
    bl_label = "Expand / Collapse"
    bl_description = "Expand or collapse the collection's children"

    path: bpy.props.StringProperty()

    def execute(self, context) -> set[str]:
        """Forward the toggle to the Controller via ``UI_HOOKS``."""
        props = getattr(context.window_manager, "lm_props", None)
        if props is not None and UI_HOOKS["on_toggle_expand"]:
            UI_HOOKS["on_toggle_expand"](props, self.path)
        return {"FINISHED"}


class LM_OT_toggle_flag(bpy.types.Operator):
    """Stage a flag change for a collection row."""
    bl_idname = "lm.toggle_flag"
    bl_label = "Toggle Layer Flag"
    bl_description = "Stage a collection change; press OK to apply"

    view_layer_name: bpy.props.StringProperty()
    path: bpy.props.StringProperty()
    flag: bpy.props.EnumProperty(
        items=[
            ("EXCLUDE", "Exclude", "Exclude from view layer"),
            ("HOLDOUT", "Holdout", "Holdout from view layer"),
            ("INDIRECT", "Indirect Only", "Render indirect contributions only"),
        ]
    )

    def execute(self, context) -> set[str]:
        """Forward the flag toggle to the Controller via ``UI_HOOKS``."""
        if UI_HOOKS["on_toggle_flag"]:
            UI_HOOKS["on_toggle_flag"](
                context, self.view_layer_name, self.path, self.flag
            )
        return {"FINISHED"}


class LM_OT_refresh(bpy.types.Operator):
    """Force a refresh of the live view layer state cache."""
    bl_idname = "lm.refresh"
    bl_label = "Refresh"
    bl_description = "Force a refresh of the live view layer state"

    def execute(self, context) -> set[str]:
        """Forward the refresh request to the Controller via ``UI_HOOKS``."""
        if UI_HOOKS["on_refresh"]:
            UI_HOOKS["on_refresh"](context)
        return {"FINISHED"}


class LM_OT_apply_flags(bpy.types.Operator):
    """Apply all currently staged flag changes."""
    bl_idname = "lm.apply_flags"
    bl_label = "Apply"
    bl_description = "Apply all pending layer flag changes"

    def execute(self, context) -> set[str]:
        """Forward the apply request to the Controller via ``UI_HOOKS``."""
        if UI_HOOKS["on_apply"]:
            UI_HOOKS["on_apply"](context)
        return {"FINISHED"}


class LM_OT_cancel_flags(bpy.types.Operator):
    """Discard all currently staged flag changes."""
    bl_idname = "lm.cancel_flags"
    bl_label = "Cancel"
    bl_description = "Discard all pending layer flag changes"

    def execute(self, context) -> set[str]:
        """Forward the cancel request to the Controller via ``UI_HOOKS``."""
        if UI_HOOKS["on_cancel"]:
            UI_HOOKS["on_cancel"]()
        return {"FINISHED"}


class LM_OT_view_layer_header(bpy.types.Operator):
    """Show an info tooltip for a view layer column header."""
    bl_idname = "lm.view_layer_header"
    bl_label = "View Layer Header"

    tooltip: bpy.props.StringProperty()

    @classmethod
    def description(cls, context, operator) -> str:
        return operator.tooltip

    def execute(self, context) -> set[str]:
        return {"FINISHED"}


FLAG_ICONS = {
    "EXCLUDE": ("CHECKBOX_DEHLT", "CHECKBOX_HLT"),
    "HOLDOUT": ("HOLDOUT_ON", "HOLDOUT_OFF"),
    "INDIRECT": ("INDIRECT_ONLY_ON", "INDIRECT_ONLY_OFF"),
}


class LAYERMAN_PT_MainPanel(bpy.types.Panel):
    """Main Layer Manager panel shown in the 3D View sidebar."""

    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Layer Manager"
    bl_label = "BLENDER LAYER MANAGER"

    @staticmethod
    def _flag_operator(layout: bpy.types.UILayout, flag: str, state: bool) -> bpy.types.Operator:
        """Build a toggle button for one flag; return its operator for props."""
        on_icon, off_icon = FLAG_ICONS[flag]
        op = layout.operator(
            "lm.toggle_flag",
            text="",
            depress=state,
            icon=on_icon if state else off_icon,
        )
        op.flag = flag
        return op

    def draw(self, context: bpy.types.Context):
        """Render the collection table, flag cells, and action buttons."""
        layout = self.layout
        table_box = layout.box()
        row = table_box.row(align=True)
        props = getattr(context.window_manager, "lm_props", None)
        scene = context.scene
        view_layers = list(scene.view_layers)

        if props is None or UI_HOOKS["get_rows_data"] is None:
            layout.label(text="Layer Manager is not registered.")
            layout.label(text="Disable any duplicate add-on and re-enable.")
            return

        if not view_layers:
            layout.label(text="No view layers.")
            return

        rows = UI_HOOKS["get_rows_data"](context, props)
        pending_count = UI_HOOKS["get_pending_count"]()

        header = row.row(align=True)
        header.scale_y = 0.5
        header.operator("lm.refresh", text="", icon="FILE_REFRESH")
        split = header.split(factor=0.42, align=True)
        left = split.column()
        right = split.column()
        left.label(text="COLLECTIONS", icon="GROUP")

        # -- Head --
        for vl, column in zip(view_layers, split_n(right, len(view_layers))):
            op = column.operator("lm.view_layer_header",
                                 text=vl.name, icon="RENDERLAYERS", emboss=False)
            op.tooltip = (vl.name)

        # -- Table --
        table_middle = layout.box()
        for row in rows:
            section = table_middle.row(align=True)
            line = section.row(align=True)
            split = line.split(factor=0.42, align=True)
            left = split.column()
            right = split.column()
            name_row = left.row(align=True)
            for _ in range(row.depth):
                name_row.label(icon="BLANK1")
            if row.has_children:
                op = name_row.operator(
                    "lm.toggle_expand",
                    text="",
                    icon="DISCLOSURE_TRI_DOWN" if row.expanded else "DISCLOSURE_TRI_RIGHT",
                )
                op.path = row.path
            else:
                name_row.label(text="", icon="BLANK1")
            name_row.label(text=row.name, icon="GROUP")

            for vl, column in zip(view_layers, split_n(right, len(view_layers))):
                if vl.name not in row.flags:
                    continue
                cell = column.row(align=True)
                for flag in ("EXCLUDE", "HOLDOUT", "INDIRECT"):
                    state = row.flags[vl.name].get(flag, False)
                    op = self._flag_operator(cell, flag, state)
                    op.view_layer_name = vl.name
                    op.path = row.path

        # -- Pending approval --
        table_box_bottom = layout.box()
        bottom = table_box_bottom.row(align=True)
        bottom.label(text=f"Pending changes: {pending_count}")

        # -- Validator --
        actions = layout.row(align=True)
        actions.enabled = pending_count > 0
        actions.operator("lm.apply_flags", text="OK", icon="CHECKMARK")
        actions.operator("lm.cancel_flags", text="CANCEL", icon="PANEL_CLOSE")

        layout.separator()

        # -- Tail --
        table_tail = layout.box()
        tail_row = table_tail.row(align=True)
        tail_row.scale_y = 0.3
        tail_row.label(text="© 2026 Rudy Leti. All Rights Reserved.")


classes = (
    LM_ExpandItem,
    LM_Props,
    LM_OT_toggle_expand,
    LM_OT_toggle_flag,
    LM_OT_apply_flags,
    LM_OT_cancel_flags,
    LM_OT_refresh,
    LM_OT_view_layer_header,
    LAYERMAN_PT_MainPanel,
)


def register_properties():
    """Register the ``lm_props`` pointer property on the WindowManager."""
    bpy.types.WindowManager.lm_props = bpy.props.PointerProperty(type=LM_Props)


def unregister_properties():
    """Remove the ``lm_props`` pointer property from the WindowManager."""
    try:
        del bpy.types.WindowManager.lm_props
    except Exception:
        pass


def register():
    """Register all UI classes and custom properties for the add-on."""
    unregister()
    for cls in classes:
        bpy.utils.register_class(cls)
    register_properties()


def unregister():
    """Unregister all UI classes and custom properties for the add-on."""
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    unregister_properties()
