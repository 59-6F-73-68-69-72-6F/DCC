from dataclasses import dataclass

@dataclass
class LightState:
    name: str
    is_visible: bool
    is_soloed: bool
    type: str  # POINT, SUN, SPOT, AREA
    color: tuple[float, float, float]
    exposure: float
    use_temperature: bool
    temperature: float
    radius: float
    use_shadow: bool
    lightgroup: str