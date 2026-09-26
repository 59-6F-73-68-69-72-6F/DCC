###################################
# This script contains the core logic for building and managing the LightMixer node in Nuke.
###################################

import nuke

import src.navigation as nav
from src.utils import (get_connection, node_builder, node_validator, layer_checker, node_renamer, unselect_all_nodes,
                       rgb_to_nuke_int)


PREFIX = "RGBA_"  # light AOV prefix
GREEN = rgb_to_nuke_int(255, 120, 30, 20)


class LightMixer:
    """
    A class to build LightAOV Group Mixers for Nuke.
    Args:
        read_node (nuke.Node): The Nuke Read node containing the AOV passes.
    """

    def __init__(self, read_node: nuke.Node):
        self.read_node = read_node

    def build_group(self) -> nuke.Node:
        """ Builds a Nuke group name as 'AOVLight_Mixer'. """

        if node_validator(self.read_node):
            # Create group and open it
            group = node_builder("Group")
            group.setName("AOVLight_Mixer")
            group["tile_color"].setValue(GREEN)
            group["note_font_size"].setValue(15)
            group["note_font"].setValue("BOLD STYLE SIMULATION")
            group["disable_group_view"].setValue(True)
            get_connection(self.read_node, group, 0)
            unselect_all_nodes()
            return group

    def build_tree(self, group: nuke.Node) -> nuke.Node:
        """ Builds the node tree inside the Nuke 'LightMixer' group. """

        # Get aovs from read node
        all_aovs = layer_checker(self.read_node)

        # Filter AOVs to include only those starting with "RGBA_" and remove duplicates
        self.light_aovs = sorted(set([aov.split('.')[0] for aov in all_aovs if aov.startswith(PREFIX)]))

        # Create nodes inside group
        group.begin()
        input_node = node_builder("Input")
        dot_node = node_builder("Dot")
        get_connection(input_node, dot_node, 0)
        nav.place_node_below(dot_node, input_node, 150)

        last_merge_node = None
        for i, aov in enumerate(self.light_aovs):
            aov_base_name = aov.split(".")[0]
            light_name = aov_base_name[5:]  # Remove "RGBA_"

            # Map for Shuffle
            aov_to_rgb_map = [
                (0, aov_base_name + ".red", "rgba.red"),
                (0, aov_base_name + ".green", "rgba.green"),
                (0, aov_base_name + ".blue", "rgba.blue"),
                (0, aov_base_name + ".alpha", "rgba.alpha"),
            ]
            # Create Shuffle
            shuffle_node = node_builder("Shuffle2")
            node_renamer(shuffle_node, f"Shuffle_{light_name}")
            shuffle_node["in1"].setValue(aov_base_name)
            shuffle_node["mappings"].setValue(aov_to_rgb_map)
            get_connection(dot_node, shuffle_node, 0)
            nav.place_node_below(shuffle_node, dot_node, 80)
            nav.place_node_to_right(shuffle_node, dot_node, i * 200)

            # Create Grade for  Color
            color_node = node_builder("Grade")
            node_renamer(color_node, f"{light_name}_Color")
            nav.place_node_below(color_node, shuffle_node, 50)

            # Create Exposure
            exposure_node = node_builder("EXPTool")
            node_renamer(exposure_node, f"Exposure_{light_name}")
            exposure_node["mode"].setValue("Stops")
            nav.move_node_in_x(exposure_node, 0)
            nav.move_node_in_y(exposure_node, 1)
            get_connection(color_node, exposure_node, 0)
            nav.place_node_below(exposure_node, color_node, 50)

            # Create Grade for Mute
            mute_node = node_builder("Grade")
            node_renamer(mute_node, f"{light_name}_Mute")
            mute_node["multiply"].setValue(0)
            mute_node.knob("disable").setValue(True)  # Desactivate node
            nav.place_node_below(mute_node, exposure_node, 50)

            # Create Merge to add the light pass
            merge_node = node_builder("Merge2")
            merge_node['operation'].setValue('plus')
            node_renamer(merge_node, f"Merge_{light_name}")
            get_connection(mute_node, merge_node, 1)  # Connect light to A input
            nav.place_node_below(merge_node, mute_node, 200)

            if last_merge_node:
                get_connection(last_merge_node, merge_node, 0)  # Connect previous merge to B input
            last_merge_node = merge_node

        output_node = node_builder("Output")
        if last_merge_node:
            get_connection(last_merge_node, output_node, 0)
            nav.place_node_below(output_node, last_merge_node, 50)
        group.end()
        nav.place_node_above(dot_node, input_node, -40)
        nav.place_node_to_right(dot_node, dot_node, 33)
        nav.place_node_to_right(group, self.read_node, 100)
        return group

    def build_ui(self, group: nuke.Node):
        """ Builds the UI for the LightMixer group. """

        if not self.read_node:
            nuke.message("No Read node selected.")
            return

        # Create a tab for the UI
        tab_knob = nuke.Tab_Knob("AOVLight_Mixer")
        group.addKnob(tab_knob)

        # Mute all Button / UnMute Button ---------------
        all_mute_knobs = []
        for aov in self.light_aovs:
            light_name = aov.split(".")[0][5:]  # Remove "RGBA_"
            all_mute_knobs.append(f"Mute_{light_name}")

        mute_all_script = f"""
n = nuke.thisNode()
for name in {all_mute_knobs}:
    if n.knob(name):
        n.knob(name).setValue(True)
"""

        unmute_all_script = f"""
n = nuke.thisNode()
for name in {all_mute_knobs}:
    if n.knob(name):
        n.knob(name).setValue(False)
"""

        mute_all_button = nuke.PyScript_Knob("mute_all", "Mute All", mute_all_script)
        group.addKnob(mute_all_button)

        unmute_all_button = nuke.PyScript_Knob("unmute_all", "Unmute All", unmute_all_script)
        group.addKnob(unmute_all_button)

        # Hidden knob to store mute states before soloing
        pre_solo_mute_states_knob = nuke.String_Knob("_pre_solo_mute_states", "Pre-Solo Mute States", "")
        pre_solo_mute_states_knob.setFlag(nuke.INVISIBLE)
        group.addKnob(pre_solo_mute_states_knob)

    def build_light_knobs(self, group: nuke.Node):
        """Builds the light knobs for the LightMixer group."""

        # Create knobs for each light
        for aov in self.light_aovs:
            light_name = aov.split(".")[0][5:]  # Remove "RGBA_"

            # Text knob ---------------
            title_knob = nuke.Text_Knob("", f"<font color='light green'><b>{light_name}</b></font>", "")
            title_knob.setFlag(nuke.STARTLINE)
            group.addKnob(title_knob)

            # Solo logic ---------------
            @staticmethod
            def _solo_logic() -> str:
                """
                Handles the soloing logic for a light.
                When a light is soloed:
                - All other lights are muted.
                - If no lights are soloed, all lights are unmuted.
                - Stores the mute states before soloing to restore them later.
                """
                return f"""
import json

n = nuke.thisNode()
current_light_name = "{light_name}"
all_aovs = {self.light_aovs!r}
light_names = [aov.split(".")[0][5:] for aov in all_aovs]

solo_state_knob = n.knob("SoloState_" + current_light_name)
is_solo = not solo_state_knob.value() # Invert the value of the knob
solo_state_knob.setValue(is_solo)

any_solo_active = any(n.knob("SoloState_" + name).value() for name in light_names)

if is_solo:
    # If this is the first light being soloed, store the current mute states
    is_first_solo = len([name for name in light_names if n.knob("SoloState_" + name).value()]) == 1
    if is_first_solo:
        mute_states = {{name: n.knob("Mute_" + name).value() for name in light_names}}
        n.knob("_pre_solo_mute_states").setValue(json.dumps(mute_states))

    # Un-solo all other lights
    for name in light_names:
        if name != current_light_name:
            n.knob("SoloState_" + name).setValue(False)

if any_solo_active:
    # If any light is soloed, apply solo logic
    for name in light_names:
        is_this_light_soloed = n.knob("SoloState_" + name).value()
        n.knob("Mute_" + name).setValue(not is_this_light_soloed)
else:
    # If no lights are soloed, restore the previous mute states
    stored_states_json = n.knob("_pre_solo_mute_states").value()
    if stored_states_json:
        try:
            previous_states = json.loads(stored_states_json)
            for name, mute_value in previous_states.items():
                n.knob("Mute_" + name).setValue(mute_value)
            # Clear the stored states
            n.knob("_pre_solo_mute_states").setValue("")
        except json.JSONDecodeError:
            # Fallback in case of corrupted data: unmute all
            for name in light_names:
                n.knob("Mute_" + name).setValue(False)
"""

            # Solo knob ---------------
            # Hidden boolean knob to store solo state
            solo_state_knob = nuke.Boolean_Knob(f"SoloState_{light_name}", "Solo State")
            solo_state_knob.setFlag(nuke.INVISIBLE)
            group.addKnob(solo_state_knob)

            solo_script = _solo_logic()
            solo_button = nuke.PyScript_Knob(
                f"Solo_{light_name}", "<font color='black'>Solo</font>", solo_script)  # Solo python button
            group.addKnob(solo_button)

            # Mute knob ---------------
            mute_knob = nuke.Boolean_Knob(f"Mute_{light_name}", "<font color='orange'>&nbsp;&nbsp;Mute</font>")
            group.addKnob(mute_knob)
            # Link to the actual mute node
            internal_mute_node = group.node(f"Grade_{light_name}_Mute")  # Get the internal node
            reverse_tcl_expression = f"![value {mute_knob.name()}]"
            internal_mute_node['disable'].setExpression(reverse_tcl_expression)

            # Disable modification ---------------
            disable_knob = nuke.Boolean_Knob(f"Disable_Mod_{light_name}", "Disable Modifications")
            disable_knob.clearFlag(nuke.STARTLINE)
            group.addKnob(disable_knob)
            # Link to the actual grade node's disable knob
            internal_color_intensity_node = group.node(f"Grade_{light_name}_Color")
            internal_color_intensity_node['disable'].setExpression(f"parent.{disable_knob.name()}")
            internal_exposure_node = group.node(f"EXPTool_Exposure_{light_name}")
            internal_exposure_node['disable'].setExpression(f"parent.{disable_knob.name()}")

            # Exposure/Color knobs ---------------
            # Color ----
            color_knob = nuke.Color_Knob(f"{light_name}_Color", "Color")
            color_knob.setValue([1.0, 1.0, 1.0])
            color_knob.setFlag(nuke.STARTLINE)
            group.addKnob(color_knob)
            # Link to the actual grade node's gain knob
            internal_color_intensity_node = group.node(f"Grade_{light_name}_Color")
            internal_color_intensity_node['white'].setSingleValue(False)
            tcl_color_expression = f"parent.{color_knob.name()}"
            internal_color_intensity_node['white'].setExpression(tcl_color_expression)

            # Exposure ----
            exposure_knob = nuke.Double_Knob(f"{light_name}_Exposure", "Exposure")
            exposure_knob.setRange(-6.0, 6.0)
            exposure_knob.setValue(0.0)
            exposure_knob.setFlag(nuke.STARTLINE)
            group.addKnob(exposure_knob)
            # Link to the actual grade node's gain knob
            internal_exposure_node = group.node(f"EXPTool_Exposure_{light_name}")
            tcl_exposure_expression = f"parent.{exposure_knob.name()}"
            internal_exposure_node["red"].setExpression(tcl_exposure_expression)
            internal_exposure_node["green"].setExpression(tcl_exposure_expression)
            internal_exposure_node["blue"].setExpression(tcl_exposure_expression)

    def data_collector(self) -> str:
        """Generates a Python script 'string' to collect knob data dynamically."""

        light_names = [aov.split(".")[0][5:] for aov in self.light_aovs]

        return f"""   
def collect_data():
    node = nuke.thisNode()
    all_knobs = {{}}
    light_names = {light_names}
    for light_name in light_names:
        all_knobs[light_name] = {{
            "Mute": node.knob(f"Mute_{{light_name}}").value(),
            "Color": list(node.knob(f"{{light_name}}_Color").value()),
            "Exposure": node.knob(f"{{light_name}}_Exposure").value()
        }}

    return all_knobs
"""

    def exporter(self, group: nuke.Node, file_path: str):
        """ Exports the knob's data to a JSON file. """
        node_name = self.read_node['file'].value().split('/')[-1]
        layer_name = node_name.split('.')[0]

        export_script = f"""
import json
import datetime as dt

t = str(dt.datetime.strptime(str(dt.datetime.now()), '%Y-%m-%d %H:%M:%S.%f'))
datetime = t[:-7]
datetime = datetime.replace(" ", "__")
datetime = datetime.replace(":", "h",1)
datetime = datetime.replace(":", "m",1)+"s" 

{self.data_collector()}
data = collect_data()
with open(file={file_path}+f"{layer_name}_{{datetime}}.json", mode="w") as file:
    json.dump(data,file, ensure_ascii=False, indent=4)
    nuke.message("Export Complete")
"""

        # Export ---------------
        divider = nuke.Text_Knob("divider1", "", "")
        divider.setFlag(nuke.STARTLINE)
        group.addKnob(divider)

        bridge = nuke.PyScript_Knob("export", "Export", export_script)
        bridge.setFlag(nuke.STARTLINE)
        group.addKnob(bridge)

        # My infos ---------------
        my_infos_knob = nuke.Text_Knob(
            "Credit", "", "<font><br/><b><a href='https://rudyleti.artstation.com/' style='color:grey'>Rudy Leti</a></b></font>")
        group.addKnob(my_infos_knob)
