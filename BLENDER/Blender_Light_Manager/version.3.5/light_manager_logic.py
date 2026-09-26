"""
Model layer for the Blender Light Manager.

Provides the LightManagerLogic class which performs all direct Blender bpy
operations (CRUD, visibility, solo, attribute editing) without any knowledge
of the UI or Controller layers.
"""

import bpy

from .models.light_state import LightState


# Prefix for light object names in Blender.
PREFIX_lgt: str = "Lgt_"
# Prefix for collection names that contain a light and its locator.
PREFIX_col: str = "C_"
#Prefix for locator (empty transform) object names.
PREFIX_loc: str = "World_"


class LightManagerLogic:
    """
    Performs all direct Blender operations for the Light Manager.

    This is the pure data/logic layer (Model) in the MVC architecture.
    It has no imports from the View or Controller modules and can be tested
    independently.
    """

    def __init__(self):
        """
        Initialise the logic layer.
        
        Attributes:
            lightTypes: List of valid Blender light type strings.
            solo_visibility_state: Per-view-layer dictionary storing snapshots
                of visibility states before a solo operation is applied.
                Structure: {view_layer_name: {light_name: exclude_bool}}.
        """
        self.lightTypes = ["POINT", "SUN", "SPOT", "AREA"]
        self.solo_visibility_state = {}

    def get_active_view_layer(self) -> str:
        """
        Return the name of the currently active view layer.

        Checks, in order:
        1. ``bpy.context.window.view_layer``
        2. ``bpy.context.scene.view_layers.active``
        3. ``bpy.context.view_layer``

        Returns:
            The active view layer name, or an empty string if none is found.
        """
        window = getattr(bpy.context, 'window', None)
        if window is not None and getattr(window, 'view_layer', None) is not None:
            return window.view_layer.name
        
        active_scene_vl = getattr(bpy.context.scene.view_layers, 'active', None)
        if active_scene_vl is not None:
            return active_scene_vl.name
        
        ctx_vl = getattr(bpy.context, 'view_layer', None)
        return ctx_vl.name if ctx_vl is not None else ""

    def _build_collection_map(self, layer_collection, map: dict):
        """Recursively build {name: LayerCollection} flat dict."""
        map[layer_collection.name] = layer_collection
        for child in layer_collection.children:
            self._build_collection_map(child, map)

    def get_lights(self, view_layer_name: str) -> list[LightState]:
        """
        Retrieve all managed lights in the scene for a given view layer.

        Only lights whose collection name starts with *PREFIX_c* are
        considered managed lights. The method also auto-detects solo mode:
        if exactly one light is visible among many, it is marked as soloed.

        Args:
            view_layer_name: Name of the view layer to query.

        Returns:
            A list of LightState objects, sorted alphabetically by name.
        """
        scene = bpy.context.scene
        view_layer = scene.view_layers.get(view_layer_name) or bpy.context.view_layer

        coll_map = {}
        self._build_collection_map(view_layer.layer_collection, coll_map)

        managed_colls = {c.name for c in bpy.data.collections if c.name.startswith(PREFIX_col)}

        all_objects = []
        for coll_name in managed_colls:
            coll = bpy.data.collections.get(coll_name)
            if coll:
                for obj in coll.objects:
                    if obj.type == 'LIGHT':
                        all_objects.append(obj)
                        break

        all_objects.sort(key=lambda obj: obj.name)
        lights_data = []

        for light in all_objects:
            light_type = light.data.type
            lc = coll_map.get(PREFIX_col + light.name.split(PREFIX_lgt)[1])
            is_visible = not lc.exclude if lc else True

            color = (light.data.color[0], light.data.color[1], light.data.color[2])
            exposure = light.data.exposure
            use_temp = light.data.use_temperature
            temp = light.data.temperature
            radius = 0.0 if light_type in ("SUN", "AREA") else light.data.shadow_soft_size
            use_shadow = light.data.use_shadow
            lightgroup = getattr(light, "lightgroup", "")

            lights_data.append(LightState(
                name=light.name, obj=light, is_visible=is_visible, is_soloed=False, type=light_type,
                color=color, exposure=exposure, use_temperature=use_temp, temperature=temp,
                radius=radius, use_shadow=use_shadow, lightgroup=lightgroup
                ))

        visible_lights = [l for l in lights_data if l.is_visible]
        if len(visible_lights) == 1 and len(lights_data) > 1:
            visible_lights[0].is_soloed = True

        return lights_data

    def create_light(self, light_name: str, light_type: str) -> str:
        """Create a new light with a dedicated collection and locator.

        The created hierarchy is:
            Collection ``C_<name>``
            └── Locator ``World_<name>`` (PLAIN_AXES empty)
                └── Light object ``Lgt_<name>``

        A unique numbered suffix (``.000``, ``.001``, …) is appended to
        avoid name collisions.

        Args:
            light_name: Base name for the light. If empty, the light type
                string is used instead.
            light_type: One of ``"POINT"``, ``"SUN"``, ``"SPOT"``,
                ``"AREA"``.

        Returns:
            The final naming convention string (e.g. ``"Point.000"``).

        Raises:
            ValueError: If *light_type* is not a valid light type.
        """
        if light_type not in self.lightTypes:
            raise ValueError(f"Invalid light type '{light_type}'")
        if not light_name.strip():
            light_name = light_type

        num = 0
        naming_convention = f"{light_name}.{num:03d}"
        
        while naming_convention in bpy.data.objects:
            num += 1
            naming_convention = f"{light_name}.{num:03d}"

        light_data = bpy.data.lights.new(name=naming_convention, type=light_type)
        light_object = bpy.data.objects.new(name=PREFIX_lgt + naming_convention, object_data=light_data)

        new_collection = bpy.data.collections.new(PREFIX_col + naming_convention)
        new_collection.color_tag = "COLOR_03"
        locator_object = bpy.data.objects.new(name=PREFIX_loc + naming_convention, object_data=None)
        locator_object.empty_display_type = "PLAIN_AXES"

        bpy.context.scene.collection.children.link(new_collection)
        
        new_collection.objects.link(locator_object)
        new_collection.objects.link(light_object)
        
        light_object.parent = locator_object

        return naming_convention

    def rename_light(self, old_name: str, new_name: str) -> str:
        """
        Rename a light and all its associated Blender data blocks.

        Renames the collection (``C_``), locator (``World_``), light object
        (``Lgt_``), and the underlying light data block to the new name.
        A unique numbered suffix is generated to avoid collisions.

        Args:
            old_name: Current light object name (e.g. ``"Lgt_Point.000"``).
            new_name: Desired base name (prefixes are added automatically).

        Returns:
            The final naming convention string.

        Raises:
            ValueError: If *new_name* is empty.
            KeyError: If *old_name* does not exist in the scene.
        """
        if not new_name.strip():
            raise ValueError("New name cannot be empty.")

        num = 0
        naming_convention = f"{new_name}.{num:03d}"
        while naming_convention in bpy.data.objects:
            num += 1
            naming_convention = f"{new_name}.{num:03d}"

        if old_name in bpy.data.objects:
            coll_name = PREFIX_col + old_name.split(PREFIX_lgt)[1]
            if coll_name in bpy.data.collections:
                bpy.data.collections[coll_name].name = PREFIX_col + naming_convention
                bpy.data.objects[PREFIX_loc + old_name.split(PREFIX_lgt)[1]].name = PREFIX_loc + naming_convention
                light_object = bpy.data.objects[old_name]
                light_object.name = PREFIX_lgt + naming_convention
                light_object.data.name = naming_convention
            return naming_convention
        raise KeyError(f"Could not find light '{old_name}'.")

    def delete_light(self, light_name: str):
        """
        Delete a light and its dedicated collection from the scene.
        
        Args:
            light_name: Light object name to delete (e.g. ``"Lgt_Point.000"``).
        """
        light_obj = bpy.data.objects.get(light_name)
        collection = bpy.data.collections.get(PREFIX_col + light_name.split(PREFIX_lgt)[1])
        locator = bpy.data.objects.get(PREFIX_loc + light_name.split(PREFIX_lgt)[1])
        
        if collection:
            bpy.data.collections.remove(collection, do_unlink=True)
        if locator:
            bpy.data.objects.remove(locator, do_unlink=True)
        if light_obj:
            bpy.data.objects.remove(light_obj, do_unlink=True)

    def set_light_visibility(self, light_name: str, is_visible: bool, view_layer_name: str):
        """
        Show or hide a light in the given view layer via collection exclusion.

        Args:
            light_name: Light object name.
            is_visible: ``True`` to make the light visible, ``False`` to hide it.
            view_layer_name: View layer to apply the change to.
        """
        scene = bpy.context.scene
        view_layer = scene.view_layers.get(view_layer_name) or bpy.context.view_layer
        coll_map = {}
        self._build_collection_map(view_layer.layer_collection, coll_map)
        collection = coll_map.get(PREFIX_col + light_name.split(PREFIX_lgt)[1])
        if collection:
            collection.exclude = not is_visible

    def set_light_solo(self, light_name: str, is_soloed: bool, view_layer_name: str, all_light_names: list[str]):
        """
        Toggle solo mode for a light in the given view layer.

        When soloing, the current visibility state of all lights is snapshotted
        so that unsoloing can restore the previous state. Only one light can be
        soloed at a time per view layer.

        Args:
            light_name: Light object name to solo or unsolo.
            is_soloed: ``True`` to activate solo, ``False`` to deactivate.
            view_layer_name: View layer to apply solo in.
            all_light_names: Complete list of managed light names in the scene.
        """
        scene = bpy.context.scene
        view_layer = scene.view_layers.get(view_layer_name) or bpy.context.view_layer
        vl_key = view_layer_name

        coll_map = {}
        self._build_collection_map(view_layer.layer_collection, coll_map)

        currently_soloed = None
        for name in all_light_names:
            col = coll_map.get(PREFIX_col + name.split(PREFIX_lgt)[1])
            if col and not col.exclude:
                currently_soloed = name
                break

        if is_soloed:
            if vl_key not in self.solo_visibility_state:
                self.solo_visibility_state[vl_key] = {}
                for name in all_light_names:
                    col = coll_map.get(PREFIX_col + name.split(PREFIX_lgt)[1])
                    if col:
                        self.solo_visibility_state[vl_key][name] = col.exclude

            for name in all_light_names:
                col = coll_map.get(PREFIX_col + name.split(PREFIX_lgt)[1])
                if col:
                    col.exclude = (name != light_name)
        else:
            if currently_soloed == light_name and vl_key in self.solo_visibility_state:
                for name in all_light_names:
                    col = coll_map.get(PREFIX_col + name.split(PREFIX_lgt)[1])
                    if col and name in self.solo_visibility_state[vl_key]:
                        col.exclude = self.solo_visibility_state[vl_key][name]
                del self.solo_visibility_state[vl_key]


    def set_light_attribute(self, light_name: str, attr_name: str, value):
        """
        Set a single attribute on a light object or its data block.

        Special handling is provided for the ``"lightgroup"`` attribute:
        if the specified light group does not exist in any view layer, it
        is automatically created.

        Args:
            light_name: Light object name.
            attr_name: Attribute name. Checked on the object first, then
                on ``obj.data``.
            value: The new value to assign.

        Raises:
            KeyError: If *light_name* does not exist or is not a LIGHT type.
            AttributeError: If *attr_name* is not found on the object or
                its data block.
        """
        obj = bpy.data.objects.get(light_name)
        if obj is None or obj.type != 'LIGHT':
            raise KeyError(f"Light '{light_name}' not found.")

        if attr_name == "lightgroup":
            obj.lightgroup = str(value).strip()
        else:
            if hasattr(obj, attr_name):
                setattr(obj, attr_name, value)
            elif hasattr(obj.data, attr_name):
                setattr(obj.data, attr_name, value)
            else:
                raise AttributeError(f"Missing attribute '{attr_name}'.")
