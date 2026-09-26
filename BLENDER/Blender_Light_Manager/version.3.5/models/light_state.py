from dataclasses import dataclass
import bpy


@dataclass
class LightState:
    """
    Represents the state of a single light in the scene.

    This dataclass is used as a data transfer object between the Model
    (BlenderLightLogic) and the Controler/View layers. It encapsulates
    all relevant properties of a Blender light object.

    Attributes:
        obj:  The Blender object reference for this light.
        name:  Blender object name of the light (e.g. "Lgt_Point.000").
        is_visible:  Whether the light's collection is not excluded in the view layer.
        is_soloed:  Whether this light is the sole visible light (solo mode).
        type:  Light type string — one of "POINT", "SUN", "SPOT", "AREA".
        color:  RGB color as a tuple of three floats in range [0.0, 1.0].
        exposure:  Exposure value of the light data.
        use_temperature:  Whether color temperature is enabled.
        temperature:  Color temperature in Kelvin.
        radius:  Shadow soft size (shadow_soft_size). Always 0.0 for SUN and AREA types.
        use_shadow:  Whether shadow casting is enabled.
        lightgroup:  Name of the assigned light group (AOV), or empty string.
    """
    name: str
    obj: bpy.types.Object
    is_visible: bool
    is_soloed: bool
    type: str
    color: tuple[float, float, float]
    exposure: float
    use_temperature: bool
    temperature: float
    radius: float
    use_shadow: bool
    lightgroup: str