import os
import bpy
from models.light_state import LightState

PREFIX : str = "Lgt_"


class BlenderLightLogic:
    """
    A class that handles pure Blender operations for the Light Manager.
    It performs scene database changes (creation, deletion, updates) and returns
    pure data structures (LightState) without any dependencies on PySide6/Qt.
    """

    def __init__(self):
        self.lightTypes : list[str] = ["POINT", "SUN", "SPOT", "AREA"]
        self.solo_visibility_state = {}  # Stores visibility state before solo activation

    def get_view_layers(self) -> list[str]:
        """Returns sorted list of all view layer names in the current scene."""
        return sorted([vl.name for vl in bpy.context.scene.view_layers])

    def get_active_view_layer(self) -> str:
        """Determines Blender's currently active view layer name."""
        window = getattr(bpy.context, 'window', None)
        if window is not None and getattr(window, 'view_layer', None) is not None:
            return window.view_layer.name
        
        active_scene_vl = getattr(bpy.context.scene.view_layers, 'active', None)
        if active_scene_vl is not None:
            return active_scene_vl.name
            
        ctx_vl = getattr(bpy.context, 'view_layer', None)
        return ctx_vl.name if ctx_vl is not None else ""

    def set_active_view_layer(self, layer_name: str):
        """Sets the active view layer in Blender."""
        scene = bpy.context.scene
        layer = scene.view_layers.get(layer_name)
        if layer is None:
            return
            
        window = getattr(bpy.context, 'window', None)
        if window is not None:
            window.view_layer = layer
        else:
            scene.view_layers.active = layer

    def get_lights(self, view_layer_name: str) -> list[LightState]:
        """Queries lights in the specified view layer and returns their state in consistent order."""
        scene = bpy.context.scene
        view_layer = scene.view_layers.get(view_layer_name)
        if not view_layer:
            view_layer = bpy.context.view_layer

        # Collect all lights that belong to CLgt_* collections for consistent ordering
        all_lights = []
        try:
            for obj in scene.objects:
                if obj.type == 'LIGHT':
                    for coll in getattr(obj, 'users_collection', []):
                        if coll and isinstance(coll.name, str) and coll.name.startswith("C" + PREFIX):
                            all_lights.append(obj)
                            break
        except Exception:
            pass

        # Sort lights by name to ensure consistent ordering regardless of visibility
        all_lights.sort(key=lambda obj: obj.name)

        lights_data = []
        for light in all_lights:
            light_type = light.data.type
            
            # Determine visibility (collection exclude status)
            collection = self.get_layer_collection_recursive(view_layer.layer_collection, "C" + light.name)
            is_visible = not collection.exclude if collection else True

            color = (light.data.color[0], light.data.color[1], light.data.color[2])
            exposure = getattr(light.data, "exposure", 0.0)
            use_temp = getattr(light.data, "use_temperature", False)
            temp = getattr(light.data, "temperature", 6500.0)
            
            if light_type in ("SUN", "AREA"):
                radius = 0.0
            else:
                radius = getattr(light.data, "shadow_soft_size", 0.0)
                
            use_shadow = getattr(light.data, "use_shadow", True)
            lightgroup = getattr(light, "lightgroup", "")

            lights_data.append(LightState(
                name=light.name,
                is_visible=is_visible,
                is_soloed=False,  # Evaluated below
                type=light_type,
                color=color,
                exposure=exposure,
                use_temperature=use_temp,
                temperature=temp,
                radius=radius,
                use_shadow=use_shadow,
                lightgroup=lightgroup
            ))

        # Evaluate solo states: Solo is True if ONLY this light collection is visible
        visible_lights = [l for l in lights_data if l.is_visible]
        if len(visible_lights) == 1 and len(lights_data) > 1:
            visible_lights[0].is_soloed = True

        return lights_data

    def get_layer_collection_recursive(self, layer_collection, name):
        """Recursively searches for a layer collection by name within the view layer's collection hierarchy."""
        if layer_collection.name == name:
            return layer_collection
        for child in layer_collection.children:
            found = self.get_layer_collection_recursive(child, name)
            if found:
                return found
        return None

    def select_light(self, light_name: str, view_layer_name: str):
        """Deselects all objects and selects the target light in the specified view layer."""
        obj = bpy.data.objects.get(light_name)
        if obj is None:
            return

        bpy.ops.object.select_all(action='DESELECT')
        
        scene = bpy.context.scene
        target_vl = scene.view_layers.get(view_layer_name)
        target_obj = None
        
        if target_vl is not None:
            try:
                target_obj = target_vl.objects.get(obj.name)
            except Exception:
                pass
                
        if target_obj is None:
            target_obj = obj

        try:
            if target_vl is not None and target_obj is not None:
                target_vl.objects.active = target_obj
            else:
                bpy.context.view_layer.objects.active = target_obj
        except Exception:
            pass

        try:
            target_obj.select_set(True)
        except Exception:
            pass

    def create_light(self, light_name: str, light_type: str) -> str:
        """Creates a new light and its associated collection in Blender."""
        if light_type not in self.lightTypes:
            raise ValueError(f"Invalid light type '{light_type}'")
        
        if not light_name.strip():
            light_name = light_type

        num = 0
        naming_convention = f"{PREFIX}{light_name}.{num:03d}"
        while naming_convention in bpy.data.objects:
            num += 1
            naming_convention = f"{PREFIX}{light_name}.{num:03d}"

        # Create light data and object
        light_data = bpy.data.lights.new(name=naming_convention, type=light_type)
        light_object = bpy.data.objects.new(name=naming_convention, object_data=light_data)

        # Link to collection
        new_collection = bpy.data.collections.new("C" + naming_convention)
        bpy.context.scene.collection.children.link(new_collection)
        new_collection.objects.link(light_object)

        return naming_convention

    def rename_light(self, old_name: str, new_name: str) -> str:
        """Renames a light object and its corresponding collection in Blender."""
        if not new_name.strip():
            raise ValueError("New name cannot be empty.")

        num = 0
        naming_convention = f"{PREFIX}{new_name}.{num:03d}"
        while naming_convention in bpy.data.objects:
            num += 1
            naming_convention = f"{PREFIX}{new_name}.{num:03d}"

        if old_name in bpy.data.objects:
            bpy.data.objects[old_name].name = naming_convention
            coll_name = "C" + old_name
            if coll_name in bpy.data.collections:
                bpy.data.collections[coll_name].name = "C" + naming_convention
            return naming_convention
        else:
            raise KeyError(f"Could not find light object '{old_name}' to rename.")

    def delete_light(self, light_name: str):
        """Removes a light object and its collection from Blender."""
        light_obj_to_remove = bpy.data.objects.get(light_name)
        collection_to_remove = bpy.data.collections.get("C" + light_name)

        if collection_to_remove:
            bpy.data.collections.remove(collection_to_remove, do_unlink=True)
        if light_obj_to_remove:
            bpy.data.objects.remove(light_obj_to_remove, do_unlink=True)

    def set_light_visibility(self, light_name: str, is_visible: bool, view_layer_name: str):
        """Sets the collection exclusion state in the view layer."""
        scene = bpy.context.scene
        view_layer = scene.view_layers.get(view_layer_name)
        if not view_layer:
            view_layer = bpy.context.view_layer

        collection = self.get_layer_collection_recursive(view_layer.layer_collection, "C" + light_name)
        if collection:
            collection.exclude = not is_visible
            self.redraw_viewports()

    def set_light_solo(self, light_name: str, is_soloed: bool, view_layer_name: str, all_light_names: list[str]):
        """Isolates the target light's visibility or restores all lights to their previous state.
        
        When solo is activated:
        - Saves the current visibility state of all lights (only on first solo)
        - Hides all lights except the target light
        
        When solo is deactivated:
        - Checks if another light is currently being soloed
        - Only restores state when NO lights are soloed (exiting solo mode completely)
        - If switching between solos, preserves the saved state for the next solo
        """
        scene = bpy.context.scene
        view_layer = scene.view_layers.get(view_layer_name)
        if not view_layer:
            view_layer = bpy.context.view_layer

        vl_key = view_layer_name
        
        # Find which light is currently visible (soloed)
        currently_soloed = None
        for name in all_light_names:
            collection = self.get_layer_collection_recursive(view_layer.layer_collection, "C" + name)
            if collection and not collection.exclude:  # Not excluded = visible
                currently_soloed = name
                break
        
        if is_soloed:
            # Save state only on first solo activation
            if vl_key not in self.solo_visibility_state:
                self.solo_visibility_state[vl_key] = {}
                for name in all_light_names:
                    collection = self.get_layer_collection_recursive(view_layer.layer_collection, "C" + name)
                    if collection:
                        self.solo_visibility_state[vl_key][name] = collection.exclude
            
            # Apply solo: hide all except target light
            for name in all_light_names:
                collection = self.get_layer_collection_recursive(view_layer.layer_collection, "C" + name)
                if collection:
                    collection.exclude = (name != light_name)
        else:
            # When unsoloing, only restore if this was the soloed light AND no other light is visible
            if currently_soloed == light_name and vl_key in self.solo_visibility_state:
                # This was the only visible light, so we're exiting solo mode
                for name in all_light_names:
                    collection = self.get_layer_collection_recursive(view_layer.layer_collection, "C" + name)
                    if collection and name in self.solo_visibility_state[vl_key]:
                        collection.exclude = self.solo_visibility_state[vl_key][name]
                del self.solo_visibility_state[vl_key]

        self.redraw_viewports()

    def set_light_color(self, light_name: str, color: tuple[float, float, float]):
        """Sets the color tuple of the light's data block."""
        light = bpy.data.objects.get(light_name)
        if light and light.type == 'LIGHT':
            light.data.color = color

    def set_light_attribute(self, light_name: str, attribute_name: str, value: any):
        """Sets a float/bool/string property of the light's data block."""
        light = bpy.data.objects.get(light_name)
        if not light or light.type != 'LIGHT':
            return

        if attribute_name == "lightgroup":
            if value:
                try:
                    bpy.ops.scene.view_layer_add_lightgroup(name=str(value))
                except Exception:
                    pass
            setattr(light, "lightgroup", str(value))
        else:
            setattr(light.data, attribute_name, value)

    def redraw_viewports(self):
        """Triggers screen redraws to display updates in real-time."""
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
