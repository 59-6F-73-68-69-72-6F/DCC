"""
Controller layer for the Blender Light Manager.

Mediates communication between the Model (LightManagerLogic) and the View
(light_manager_ui). Registers callback hooks into the UI's UI_HOOKS dictionary
and listens for depsgraph updates to auto-refresh the interface when lights
change externally.
"""

import bpy

import light_manager_ui as lmui


class LightManagerController:
    """
    Mediates between the Blender Light Manager Model and View.

    The Controller owns the application logic that responds to UI events.
    It registers callbacks in ``lmui.UI_HOOKS``, manages a depsgraph update
    handler for auto-refresh, and pushes status/stats messages to the UI.
    """

    def __init__(self, model):
        """Initialise the controller and wire up all UI hooks.
        Args:
            model: An instance of ``blender_light_logic.LightManagerLogic``.
        """
        self.model = model
        self._depsgraph_handlers = []

        lmui.UI_HOOKS["on_create"] = self.on_light_created
        lmui.UI_HOOKS["on_rename"] = self.on_light_renamed
        lmui.UI_HOOKS["on_delete"] = self.on_light_deleted
        lmui.UI_HOOKS["on_visibility_toggle"] = self.on_visibility_toggle
        lmui.UI_HOOKS["on_solo_toggle"] = self.on_solo_toggle
        lmui.UI_HOOKS["on_attribute_changed"] = self.on_attribute_changed
        lmui.UI_HOOKS["get_lights_data"] = self.get_ui_lights

        self.register_handlers()

    def set_status(self, msg: str):
        """
        Update the status message displayed in the UI panel.
        Args:
            msg: The status text to display.
        """
        if bpy.context and hasattr(bpy.context, "window_manager"):
            bpy.context.window_manager.lm_status_info = msg

    def force_ui_redraw(self):
        """
        Force all 3D Viewport areas to redraw.
        Iterates all windows and screens to tag every ``VIEW_3D`` area
        for a refresh.
        """
        if not bpy.context:
            return
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

    def get_ui_lights(self, view_layer_name: str) -> list[dict]:
        """
        Retrieve light data enriched with Blender objects and stats.
        
        Wraps each ``LightState`` with its corresponding ``bpy.types.Object``
        and calculates summary statistics (total, visible, soloed).

        Args:
            view_layer_name: Name of the view layer to query.

        Returns:
            A list of dictionaries, each containing:
                - ``"obj"``: The ``bpy.types.Object`` for the light.
                - ``"state"``: The corresponding ``LightState`` dataclass.
        """
        states = self.model.get_lights(view_layer_name)
        data_list = []
        visible_count = 0
        solo_count = 0

        for state in states:
            data_list.append({"obj": state.obj, "state": state})
            if state.is_visible:
                visible_count += 1
            if state.is_soloed:
                solo_count += 1

        if bpy.context and hasattr(bpy.context, "window_manager"):
            wm = bpy.context.window_manager
            wm.lm_stats_info = f"Total: {len(data_list)} | Visible: {visible_count} | Solo: {solo_count}"

        return data_list

    def register_handlers(self):
        """Register a depsgraph update handler to auto-refresh the UI.

        The handler checks whether any ``Light`` data block or ``LIGHT``
        object was updated and triggers a viewport redraw if so.
        Previously registered handlers are removed first to prevent leaks.
        """
        self.unregister_handlers()

        def on_depsgraph_update(scene, depsgraph):
            is_light_updated = False
            for update in depsgraph.updates:
                try:
                    uid = update.id
                    if isinstance(uid, bpy.types.Light) or (
                        isinstance(uid, bpy.types.Object) and uid.type == 'LIGHT'
                    ):
                        is_light_updated = True
                        break
                except Exception:
                    pass
            if is_light_updated:
                self.force_ui_redraw()

        bpy.app.handlers.depsgraph_update_post.append(on_depsgraph_update)
        self._depsgraph_handlers.append(on_depsgraph_update)

    def unregister_handlers(self):
        """Remove all previously registered Blender event handlers."""
        for job in self._depsgraph_handlers:
            if job in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.remove(job)
        self._depsgraph_handlers.clear()

    def on_light_created(self, name: str, light_type: str):
        """
        Handle a light creation request from the UI.
        Args:
            name: Base name for the new light.
            light_type: One of ``"POINT"``, ``"SUN"``, ``"SPOT"``, ``"AREA"``.
        """
        try:
            new_name = self.model.create_light(name, light_type)
            self.set_status(f"Light '{new_name}' created.")
            self.force_ui_redraw()
        except Exception as e:
            self.set_status(f"Error: {e}")

    def on_light_renamed(self, old_name: str, new_name: str):
        """
        Handle a light rename request from the UI.
        Args:
            old_name: Current light object name.
            new_name: Desired base name for the light.
        """
        try:
            renamed_name = self.model.rename_light(old_name, new_name)
            self.set_status(f"Light '{old_name}' renamed to '{renamed_name}'.")
            self.force_ui_redraw()
        except Exception as e:
            self.set_status(f"Error: {e}")

    def on_light_deleted(self, name: str):
        """
        Handle a light deletion request from the UI.
        Args:
            name: Light object name to delete.
        """
        try:
            self.model.delete_light(name)
            self.set_status(f"Light '{name}' deleted.")
            self.force_ui_redraw()
        except Exception as e:
            self.set_status(f"Error: {e}")

    def on_visibility_toggle(self, light_name: str, state: bool):
        """
        Handle a visibility toggle request from the UI.
        Args:
            light_name: Light object name.
            state: ``True`` to show the light, ``False`` to hide it.
        """
        try:
            vl = self.model.get_active_view_layer()
            self.model.set_light_visibility(light_name, state, vl)
            self.force_ui_redraw()
        except Exception as e:
            self.set_status(f"Error: {e}")

    def on_solo_toggle(self, light_name: str, state: bool):
        """
        Handle a solo toggle request from the UI.
        Args:
            light_name: Light object name to solo or unsolo.
            state: ``True`` to activate solo, ``False`` to deactivate.
        """
        try:
            vl = self.model.get_active_view_layer()
            all_names = [s.name for s in self.model.get_lights(vl)]
            self.model.set_light_solo(light_name, state, vl, all_names)
            self.set_status(f"Light '{light_name}' is solo.")
            self.force_ui_redraw()
        except Exception as e:
            self.set_status(f"Error: {e}")

    def on_attribute_changed(self, light_name: str, attr_name: str, value):
        """
        Handle an attribute change request from the UI.
        Args:
            light_name: Light object name.
            attr_name: Attribute name to modify.
            value: The new value to assign.
        """
        try:
            self.model.set_light_attribute(light_name, attr_name, value)
            if attr_name == "lightgroup":
                group_label = f"'{value}'" if value else "<none>"
                self.set_status(f"Light '{light_name}' assigned to lightgroup {group_label}.")
            else:
                self.set_status(f"Light '{light_name}': {attr_name} updated.")
            self.force_ui_redraw()
        except Exception as e:
            self.set_status(f"Error updating attribute: {e}")

    def cleanup(self):
        """
        Tear down the controller.
        Unregisters Blender event handlers and nullifies all UI hook
        callbacks to break references.
        """
        self.unregister_handlers()
        for key in lmui.UI_HOOKS:
            lmui.UI_HOOKS[key] = None