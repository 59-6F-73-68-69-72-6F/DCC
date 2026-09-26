###################################
# This script contains functions for transferring light AOVs data's between Nuke and Maya.
###################################

import json

from maya import cmds

LIGHT_TYPES = [
    "aiPhotometricLight",
    "aiSkyDomeLight",
    "aiAreaLight",
    "spotLight",
    "pointLight",
    "directionalLight",
    "aiLightPortal"
]


def lights_data_tranfert(path: str):
    """ Transfers light data from a json file from Nuke light AOV Mixer to Maya lights. """

    with open(path, "r") as file:
        data = json.load(file)

        all_light = [cmds.ls(type=Ltype) for Ltype in LIGHT_TYPES if Ltype]  # All Maya Lights
        for light in all_light:
            if light:
                for lightshape in light:
                    light_transform = cmds.listRelatives(lightshape, parent=True)[0]
                    aov_attribute = f"{light_transform}.aiAov"
                    current_aov = cmds.getAttr(aov_attribute)
                    color = f"{light_transform}.color"
                    current_color = cmds.getAttr(color)[0]
                    exposure = f"{light_transform}.aiExposure"
                    current_exposure = cmds.getAttr(exposure)

                    if data[current_aov]:
                        if data[current_aov]["Mute"] == False:
                            cmds.setAttr(f"{light_transform}.visibility", True)
                        else:
                            cmds.setAttr(f"{light_transform}.visibility", False)

                        # color transfert -------
                        if data[current_aov]["Color"]:
                            color_data = data[current_aov]["Color"]
                            r = current_color[0] * color_data[0]
                            g = current_color[1] * color_data[1]
                            b = current_color[2] * color_data[2]
                            cmds.setAttr(f"{light_transform}.color", r, g, b, type="double3")

                        # exposure transfert -------
                        if data[current_aov]["Exposure"]:
                            cmds.setAttr(f"{light_transform}.aiExposure",
                                         current_exposure + (data[current_aov]["Exposure"]))
                        print(f"{light_transform} : Transfert complet")
