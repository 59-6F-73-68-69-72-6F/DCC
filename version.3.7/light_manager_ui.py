"""
Defines all Blender UI components: custom properties on WindowManager and
Object, Blender Operators for user actions, and the main UI panel displayed
in the 3D View sidebar. UI behaviour is delegated to the Controller through
the ``UI_HOOKS`` callback dictionary.
"""

import bpy

UI_HOOKS = {
    "on_create": None,
    "on_rename": None,
    "on_delete": None,
    "on_visibility_toggle": None,
    "on_solo_toggle": None,
    "on_attribute_changed": None,
    "get_lights_data": None,
    "on_refresh": None,
}
"""
Callback hooks populated by ``LightManagerController``.
Keys:
    on_create: Called with ``(name, light_type)`` when the user creates a light.
    on_rename: Called with ``(old_name, new_name)`` when the user renames a light.
    on_delete: Called with ``(light_name)`` when the user deletes a light.
    on_visibility_toggle: Called with ``(light_name, state)`` on visibility toggle.
    on_solo_toggle: Called with ``(light_name, state)`` on solo toggle.
    on_attribute_changed: Called with ``(light_name, attr_name, value)``.
    get_lights_data: Called with ``(view_layer_name)`` to retrieve light data.
    on_refresh: Called with no arguments to force a full data refresh.
"""


def get_lm_lightgroup_items(self, context):
    items = [("__NONE__", "None", "No light group assigned")]
    seen = set()
    for vl in context.scene.view_layers:
        for lg in vl.lightgroups:
            if lg.name not in seen:
                seen.add(lg.name)
                items.append((lg.name, lg.name, ""))
    if self.lightgroup and self.lightgroup not in seen:
        items.append((self.lightgroup, self.lightgroup, ""))
    return items


def sync_lm_lightgroup(self, context):
    group = "" if self.lm_lightgroup == "__NONE__" else self.lm_lightgroup
    if self.lightgroup != group:
        self.lightgroup = group
        if UI_HOOKS["on_attribute_changed"]:
            UI_HOOKS["on_attribute_changed"](self.name, "lightgroup", group)


def register_properties():
    """
    Register all custom Blender properties used by the Light Manager.
    Registers on ``bpy.types.WindowManager``:
        - ``lm_entry_name`` — light name text field.
        - ``lm_entry_type`` — light type enum (POINT, SUN, SPOT, AREA).
        - ``lm_search_filter`` — search/filter text field.
        - ``lm_stats_info`` — read-only stats label.
        - ``lm_status_info`` — read-only status label.

    Registers on ``bpy.types.Object``:
        - ``lm_lightgroup`` — enum property showing all view-layer lightgroups,
          synced to the Blender-native ``lightgroup`` attribute.
    """
    wm = bpy.types.WindowManager
    wm.lm_entry_name = bpy.props.StringProperty(name="Light Name", default="")
    wm.lm_search_filter = bpy.props.StringProperty(name="", default="", description="Filter by light name")
    wm.lm_stats_info = bpy.props.StringProperty(name="Stats", default="0 Lights")
    wm.lm_status_info = bpy.props.StringProperty(
        name="Status", default="Blender Light Manager - version 3.7"
    )
    wm.lm_entry_type = bpy.props.EnumProperty(
        name="Type",
        items=[('POINT', 'Point', ''), ('SUN', 'Sun', ''), ('SPOT', 'Spot', ''), ('AREA', 'Area', '')],
        default='POINT',
    )
    wm.lm_ll_active_light = bpy.props.StringProperty(name="", default="")
    wm.lm_page_index = bpy.props.IntProperty(name="Page", default=0, min=0)

    bpy.types.Object.lm_lightgroup = bpy.props.EnumProperty(
        name="Light Group",
        items=get_lm_lightgroup_items,
        update=sync_lm_lightgroup,
    )


def unregister_properties():
    """Remove all custom Blender properties registered by the Light Manager."""
    wm = bpy.types.WindowManager
    for prop in ["lm_entry_name", "lm_entry_type", "lm_status_info", "lm_search_filter", "lm_stats_info", "lm_ll_active_light", "lm_page_index"]:
        if hasattr(wm, prop):
            delattr(wm, prop)
    if hasattr(bpy.types.Object, "lm_lightgroup"):
        del bpy.types.Object.lm_lightgroup


# -- OPERATORS --


class LM_OT_CreateLight(bpy.types.Operator):
    """
    Create a new light in the scene.

    Reads the light name and type from the WindowManager properties and
    delegates creation to the Controller via ``UI_HOOKS["on_create"]``.
    """
    bl_idname = "lm.create_light"
    bl_label = "Create Light"
    bl_options = {"UNDO"}

    def execute(self, context):
        if UI_HOOKS["on_create"]:
            UI_HOOKS["on_create"](
                context.window_manager.lm_entry_name,
                context.window_manager.lm_entry_type,
            )
        return {'FINISHED'}


class LM_OT_RenameLight(bpy.types.Operator):
    """
    Rename the currently selected light.

    Reads the new name from the WindowManager property and delegates to
    the Controller via ``UI_HOOKS["on_rename"]``. Only acts when a LIGHT
    object is active.
    """
    bl_idname = "lm.rename_light"
    bl_label = "Rename Selected"
    bl_options = {"UNDO"}

    def execute(self, context):
        active = context.active_object
        if UI_HOOKS["on_rename"] and active and active.type == 'LIGHT':
            UI_HOOKS["on_rename"](active.name, context.window_manager.lm_entry_name)
        return {'FINISHED'}


class LM_OT_DeleteLight(bpy.types.Operator):
    """
    Delete a light from the scene.

    The target light name is passed as a ``StringProperty`` from the UI
    table row. Delegates to the Controller via ``UI_HOOKS["on_delete"]``.
    """
    bl_idname = "lm.delete_light"
    bl_label = "Delete"
    bl_options = {"UNDO"}
    light_name: bpy.props.StringProperty()

    def execute(self, context):
        if UI_HOOKS["on_delete"]:
            UI_HOOKS["on_delete"](self.light_name)
        return {'FINISHED'}


class LM_OT_ToggleVisibility(bpy.types.Operator):
    """
    Toggle the visibility (mute) of a light in the current view layer.

    The target light name and current state are passed as properties from
    the UI table row. Delegates to ``UI_HOOKS["on_visibility_toggle"]``.
    """
    bl_idname = "lm.toggle_visibility"
    bl_label = "Toggle Vis"
    bl_options = {"UNDO"}
    light_name: bpy.props.StringProperty()
    current_state: bpy.props.BoolProperty()

    def execute(self, context):
        if UI_HOOKS["on_visibility_toggle"]:
            UI_HOOKS["on_visibility_toggle"](self.light_name, not self.current_state)
        return {'FINISHED'}


class LM_OT_ToggleSolo(bpy.types.Operator):
    """
    Toggle solo mode for a light.

    When soloed, all other lights in the scene are hidden. The target
    light name and current solo state are passed from the UI table row.
    Delegates to ``UI_HOOKS["on_solo_toggle"]``.
    """
    bl_idname = "lm.toggle_solo"
    bl_label = "Toggle Solo"
    light_name: bpy.props.StringProperty()
    current_state: bpy.props.BoolProperty()

    def execute(self, context):
        if UI_HOOKS["on_solo_toggle"]:
            UI_HOOKS["on_solo_toggle"](self.light_name, not self.current_state)
        return {'FINISHED'}


class LM_OT_SelectLight(bpy.types.Operator):
    """
    Select a light in the Blender viewport.

    Deselects all other objects, then selects and activates the target
    light. The light name is passed as a ``StringProperty`` from the UI
    table row.
    """
    bl_idname = "lm.select_light"
    bl_label = "Select Light"
    light_name: bpy.props.StringProperty()

    def execute(self, context):
        try:
            obj = bpy.data.objects.get(self.light_name)
            if obj:
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                context.view_layer.objects.active = obj
            else:
                pass
        except RuntimeError:
            pass

        return {'FINISHED'}


class LM_OT_ToggleLightLinking(bpy.types.Operator):
    """
    Toggle the Light Linking editor for a specific light.

    When checked, the Light Linking section at the bottom of the panel
    shows the native Blender light linking widgets for that light.
    Only one light can be selected at a time.
    """
    bl_idname = "lm.toggle_light_linking"
    bl_label = "Show Light Linking"
    light_name: bpy.props.StringProperty()

    def execute(self, context):
        wm = context.window_manager
        if wm.lm_ll_active_light == self.light_name:
            wm.lm_ll_active_light = ""
        else:
            wm.lm_ll_active_light = self.light_name
        return {'FINISHED'}


class LM_OT_RefreshLights(bpy.types.Operator):
    """
    Force a full refresh of the light data table.

    Sets the dirty flag on the controller so the next panel draw
    rebuilds the entire light list from scratch.
    """
    bl_idname = "lm.refresh_lights"
    bl_label = "Refresh Lights"
    bl_description = "Force a full refresh of the light list"

    def execute(self, context):
        if UI_HOOKS["on_refresh"]:
            UI_HOOKS["on_refresh"]()
        return {'FINISHED'}


class LM_OT_PageLights(bpy.types.Operator):
    """Navigate light list pages."""
    bl_idname = "lm.page_lights"
    bl_label = "Page"
    direction: bpy.props.IntProperty(default=1)

    def execute(self, context):
        context.window_manager.lm_page_index = max(0, context.window_manager.lm_page_index + self.direction)
        return {'FINISHED'}


class LIGHTMAN_PT_MainPanel(bpy.types.Panel):
    """
    Main Blender Light Manager panel displayed in the 3D View sidebar.
    Provides:
        - Status and stats information.
        - Light creation (name, type, create/rename buttons).
        - Search/filter field.
        - Scrollable data table with per-light controls (select, visibility,
          solo, colour, exposure, temperature, radius, shadow, lightgroup,
          delete).
        - Footer credit line.
    """
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Light Manager'
    bl_label = 'BLENDER LIGHT MANAGER'

    def draw(self, context):
        """
        Render the panel UI.
        Args:
            context: The current Blender context.
        """
        layout = self.layout
        wm = context.window_manager

        # --- Stats & Status Info Box ---
        info_box = layout.box()
        info_box.label(text=wm.lm_status_info, icon='INFO')
        info_box.label(text=wm.lm_stats_info, icon='LIGHT_DATA')

        # --- Creation Controls ---
        box = layout.box()
        row_in = box.row(align=True)
        row_in.prop(wm, "lm_entry_name", text="Name")
        row_in.prop(wm, "lm_entry_type", text="Type")
        row_btns = box.row(align=True)
        row_btns.operator("lm.create_light", text="Create", icon='ADD')
        row_btns.operator("lm.rename_light", text="Rename", icon='LINE_DATA')

        # --- Search Bar ---
        layout.separator()
        row = layout.row(align=True)
        row.prop(wm, "lm_search_filter", text="", icon='VIEWZOOM')
        row.operator("lm.refresh_lights", text="", icon='FILE_REFRESH')

        if not UI_HOOKS["get_lights_data"]:
            return
        data_list = UI_HOOKS["get_lights_data"](context.window.view_layer.name)

        # Apply Search Filter
        search_term = wm.lm_search_filter.lower()
        if search_term:
            data_list = [
                item for item in data_list
                if search_term in item["obj"].name.lower()
            ]

        # --- Pagination ---
        page_size = 20
        total = len(data_list)
        max_page = max(0, (total - 1) // page_size)
        page_idx = min(wm.lm_page_index, max_page)
        wm.lm_page_index = page_idx
        start = page_idx * page_size
        page_data = data_list[start:start + page_size]

        # --- Data Table ---
        table_box = layout.box()
        for item in page_data:
            try:
                obj = item["obj"]
                state = item["state"]
                data = obj.data
                row = table_box.row(align=True)

                link_col = row.column(align=True)
                op_link = link_col.operator("lm.toggle_light_linking", text="",
                                            icon="CHECKBOX_HLT" if wm.lm_ll_active_light == obj.name else "CHECKBOX_DEHLT")
                op_link.light_name = obj.name

                name_col = row.column(align=True)
                name_col.scale_x = 0.7
                op_sel = name_col.operator("lm.select_light", text=obj.name, emboss=False)
                op_sel.light_name = obj.name

                op_v = row.operator(
                    "lm.toggle_visibility", text="",
                    icon='HIDE_OFF' if state.is_visible else 'HIDE_ON',
                )
                op_v.light_name = obj.name
                op_v.current_state = state.is_visible

                solo_col = row.column(align=True)
                solo_col.scale_x = 0.4
                op_s = solo_col.operator("lm.toggle_solo", text="S", depress=state.is_soloed)
                op_s.light_name = obj.name
                op_s.current_state = state.is_soloed

                row.label(text="", icon=f'LIGHT_{data.type}')

                color_col = row.column(align=True)
                color_col.scale_x = 0.5
                color_col.prop(data, "color", text="")

                expo_col = row.column(align=True)
                expo_col.scale_x = 0.5
                expo_col.prop(data, "exposure", text="")

                if hasattr(data, "use_temperature"):
                    row.prop(data, "use_temperature", text="")
                else:
                    row.label(text="-")

                temp_col = row.column(align=True)
                temp_col.scale_x = 0.5
                if hasattr(data, "temperature"):
                    temp_col.prop(data, "temperature", text="")
                else:
                    temp_col.label(text="-")

                sdh_col = row.column(align=True)
                sdh_col.scale_x = 0.5
                if hasattr(data, "shadow_soft_size"):
                    sdh_col.prop(data, "shadow_soft_size", text="")
                else:
                    sdh_col.label(text="-")
                row.prop(data, "use_shadow", text="")

                lgtgrp_col = row.column(align=True)
                lgtgrp_col.scale_x = 0.5
                if hasattr(obj, "lightgroup"):
                    lgtgrp_col.prop(obj, "lm_lightgroup", text="")
                else:
                    lgtgrp_col.label(text="Pass")

                op_del = row.operator("lm.delete_light", text="", icon='TRASH')
                op_del.light_name = obj.name
                row.separator(factor=2.5)
            except ReferenceError:
                pass

        # --- Pagination Controls ---
        if total > page_size:
            row = layout.row(align=True)
            prev = row.operator("lm.page_lights", text="", icon='TRIA_LEFT')
            prev.direction = -1
            row.label(text=f"{page_idx + 1} / {max_page + 1}")
            nxt = row.operator("lm.page_lights", text="", icon='TRIA_RIGHT')
            nxt.direction = 1

        layout_ll = self.layout
        layout_lgtlink = box = layout_ll.box()

        light_name = context.window_manager.lm_ll_active_light
        if light_name:
            obj = bpy.data.objects.get(light_name)
            if obj and obj.type == "LIGHT" and hasattr(obj, "light_linking"):
                ll = obj.light_linking

                # ── Light Linking (Receiver) ──
                col = layout_lgtlink.column()
                col.label(text="Light Linking")
                col.template_ID(
                    ll,
                    "receiver_collection",
                    new="object.light_linking_receiver_collection_new",
                )
                if ll.receiver_collection:
                    row = layout_lgtlink.row()
                    inner = row.column()
                    inner.template_light_linking_collection(row, ll, "receiver_collection")
                    inner = row.column()
                    sub = inner.column(align=True)
                    prop = sub.operator("object.light_linking_receivers_link", icon='ADD', text="")
                    prop.link_state = 'INCLUDE'
                    sub.operator("object.light_linking_unlink_from_collection", icon='REMOVE', text="")
                    sub = inner.column()
                    sub.menu("OBJECT_MT_light_linking_context_menu", icon='DOWNARROW_HLT', text="")

                layout_lgtlink.separator()

                # ── Shadow Linking (Blocker) ──
                col = layout_lgtlink.column()
                col.label(text="Shadow Linking")
                col.template_ID(
                    ll,
                    "blocker_collection",
                    new="object.light_linking_blocker_collection_new",
                )
                if ll.blocker_collection:
                    row = layout_lgtlink.row()
                    inner = row.column()
                    inner.template_light_linking_collection(row, ll, "blocker_collection")
                    inner = row.column()
                    sub = inner.column(align=True)
                    prop = sub.operator("object.light_linking_blockers_link", icon='ADD', text="")
                    prop.link_state = 'INCLUDE'
                    sub.operator("object.light_linking_unlink_from_collection", icon='REMOVE', text="")
                    sub = inner.column()
                    sub.menu("OBJECT_MT_shadow_linking_context_menu", icon='DOWNARROW_HLT', text="")
            else:
                layout_lgtlink.label(text="Light not found", icon='ERROR')
        else:
            row_ll = layout_lgtlink.row(align=True)
            row_ll.label(text="Light Linking Section:")
            layout_lgtlink.label(text="Check the box next to a light name", icon="INFO")

        # Tail --------------
        layout_tail = box = layout.box()
        row_tail = layout_tail.row(align=True)
        row_tail.scale_y = 0.3
        row_tail.label(text="© 2026 Rudy Leti. All Rights Reserved.")


# Tuple of all Blender UI classes to register/unregister.
classes = (
    LM_OT_CreateLight,
    LM_OT_RenameLight,
    LM_OT_DeleteLight,
    LM_OT_ToggleVisibility,
    LM_OT_ToggleSolo,
    LIGHTMAN_PT_MainPanel,
    LM_OT_SelectLight,
    LM_OT_ToggleLightLinking,
    LM_OT_RefreshLights,
    LM_OT_PageLights,
)


def register():
    """Register all Light Manager UI classes and custom properties with Blender."""
    register_properties()
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """Unregister all Light Manager UI classes and custom properties from Blender."""
    unregister_properties()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
