##########################
# - AOV LIGHT MIXER / BRIDGE TO DCC -
# AUTHOR : RUDY LETI
# DATE : 2025/11/03
# DESIGNED TO TRANSFER LIGHT AOVS DATA BETWEEN NUKE AND MAYA
# This script contains the main logic for creating the LightMixer setup in Nuke.
##########################

import os

import nuke

import src.utils as utils
import light_mixer_node as lmn

JSON_PATH = r"Put Your Path Here, where your json files will be exported !"


def create_light_mixer_setup():
    """ Creates a Relight node setup from a selected Read node. """

    read_node = utils.is_selected()  # Pick the selected node
    if not read_node:
        nuke.message("Please select a Read node.")
        return

    light_mixer_node = lmn.LightMixer(read_node)
    group = light_mixer_node.build_group()

    if not group:
        return

    tree = light_mixer_node.build_tree(group)
    light_mixer_node.build_ui(tree)
    light_mixer_node.build_light_knobs(tree)

    if not os.path.exists(JSON_PATH):
        os.makedirs(JSON_PATH)

    light_mixer_node.exporter(tree, repr(os.path.join(JSON_PATH, '')))
