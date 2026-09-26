###################################
# This script contains custom utility functions for Nuke.
###################################

import nuke


def is_selected(output: str = None) -> nuke.Node | str | None:
    """Check if a node is selected and return its name, type, or the node itself."""
    node = None
    try:
        node = nuke.selectedNode()
        if output == "name":
            return node.name()
        elif output == "type":
            return node.Class()
        elif output == None:
            return node
    except ValueError:
        nuke.message("No node is selected.")
        return node


def select_node(node_name: str) -> nuke.Node:
    """Select a node by its name."""
    if node_name:
        node = nuke.toNode(node_name)
        node.setSelected(True)
        return node
    else:
        print("Node name is empty.")
        return None


def node_builder(node_type: str,) -> nuke.Node:
    """build a new node"""
    return nuke.createNode(node_type, inpanel=False)


def node_renamer(node: nuke.Node, name: str) -> None:
    """Rename a node."""
    node_type = node.Class()
    if not node_type.isalpha():
        node_type = node_type[:-1]
    node.setName(node_type + "_" + name)


def node_validator(node: nuke.Node) -> nuke.Node | None:
    """Validate the node type, "Read", "Shuffle", or "Grade" and check for EXR format in Read nodes."""
    assert node.Class() == "Read", "Please select a Read Node."
    if node.Class() == "Read":
        for knob_name, knob in node.knobs().items():
            if knob.value() == "exr":
                print(f"--- Node validated : {node.name()}, src : {knob.value()} ---")
                return node
        return None


def layer_checker(node: nuke.Node) -> list:
    """Check for layers in a Read node."""
    if node.Class() == "Read":
        layers = node.channels()
    return layers


def get_all_nodes() -> list:
    """Get all nodes in the Nuke script."""
    return nuke.allNodes()


def unselect_all_nodes() -> None:
    """Unselect all nodes in the Nuke script."""
    for node in nuke.allNodes():
        node.setSelected(False)


def get_connection(source_node, destination_node, input_number: int):
    """Get the node connected to the specified input of the destination node.
        For Merge nodes,the 'A' input (index 1),the 'B' input (index 0).
    """
    destination_node.setInput(input_number, source_node)


def rgb_to_nuke_int(r: int, g: int, b: int, a: int = 255) -> int:
    """Converts 8-bit RGB (0-255) to the Nuke tile_color integer."""
    # The string format builds the AARRGGBB hex string (with A always 255/FF)
    hex_string = f"0x{a:02x}{r:02x}{g:02x}{b:02x}".upper()
    # int(hex_string, 16) converts the hex string to a base-10 integer
    return int(hex_string, 16)
