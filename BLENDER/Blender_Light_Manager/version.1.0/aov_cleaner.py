import bpy


def garbage_oav():
    """
    Removes unused light groups from the current view layer
    """
    actual_view_layer = bpy.context.view_layer
    all_lights = [obj for obj in actual_view_layer.objects if obj.type == "LIGHT"]
    light_groups_in_view_layer = actual_view_layer.lightgroups

    blender_lightgroups = []
    active_lightgroups = []

    # Collect all lightgroups currently in the view layer
    for lg in light_groups_in_view_layer:
        blender_lightgroups.append(lg.name)

    # Collect all lightgroups assigned to lights
    for light in all_lights:
        light_group_per_lgt = bpy.data.objects[light.name].lightgroup
        if light_group_per_lgt != "":
            active_lightgroups.append(light_group_per_lgt)

    # Identify and remove lightgroups that are not assigned to any light
    for lg in blender_lightgroups:
        if lg not in active_lightgroups:
            print(f"Removing: {lg}")
            aov_to_remove = bpy.context.view_layer.lightgroups.get(lg)
            bpy.context.view_layer.lightgroups.remove(aov_to_remove)
