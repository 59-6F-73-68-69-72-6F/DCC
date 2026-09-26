from dataclasses import dataclass
import bpy


@dataclass
class LightState:
    """
    Represents the state of a single light in the scene.

    This dataclass is used as a data transfer object between the Model
    (BlenderLightLogic) and the Controler/View layers. It encapsulates
    only the dynamic visibility/solo state that cannot be read live from
    Blender data blocks during UI drawing.

    Attributes:
        obj:  The Blender object reference for this light.
        name:  Blender object name of the light (e.g. "Lgt_Point.000").
        is_visible:  Whether the light's collection is not excluded in the view layer.
        is_soloed:  Whether this light is the sole visible light (solo mode).
        type:  Light type string — one of "POINT", "SUN", "SPOT", "AREA".
        lightgroup:  Name of the assigned light group (AOV), or empty string.
    """
    obj: bpy.types.Object
    name: str
    is_visible: bool
    is_soloed: bool
    type: str
    lightgroup: str