###################################
# This script contains functions for navigating nodes in Nuke.
###################################

import nuke


def move_node_in_x(node: nuke.Node, xdist: int) -> None:
    """ Moves a node horizontally by a given distance. """
    x0 = node.xpos()
    node.setXpos(x0 + xdist)


def move_node_in_y(node: nuke.Node, ydist: int) -> None:
    """ Moves a node vertically by a given distance. """
    y0 = node.ypos()
    node.setYpos(y0 + ydist)


def place_node_below(node: nuke.Node, node_origin: nuke.Node, ydist: int) -> None:
    """ Places a node below another node. """
    x0 = node_origin.xpos()
    y0 = node_origin.ypos()
    node.setXpos(x0)
    node.setYpos(y0 + ydist)


def place_node_above(node: nuke.Node, node_origin: nuke.Node, ydist: int) -> None:
    """ Places a node above another node. """
    x0 = node_origin.xpos()
    y0 = node_origin.ypos()
    node.setXpos(x0)
    node.setYpos(y0 - ydist)


def place_node_to_right(node: nuke.Node, origin: nuke.Node, xdist: int) -> None:
    """ Places a node to the right of another node. """
    x0 = origin.xpos()
    y0 = origin.ypos()
    node.setXpos(x0 + xdist)
    node.setYpos(y0)


def place_node_to_left(node: nuke.Node, origin: nuke.Node, xdist: int) -> None:
    """ Places a node to the left of another node. """
    x0 = origin.xpos()
    y0 = origin.ypos()
    node.setXpos(x0 - xdist)
    node.setYpos(y0)
