"""
Pure Python data representation for the Layer Manager.

Contains data transfer objects used to exchange information between the
Model, Presenter, and View layers. No Blender imports.
"""

from dataclasses import dataclass


@dataclass
class CollectionRowState:
    """
    Represents a single visible collection row in the Layer Manager panel.

    Attributes:
        path:  Slash-separated path of the collection (e.g. "Props/Gun").
        name:  Blender collection name.
        depth: Nesting depth below the scene root collection.
        has_children: Whether the collection contains child collections.
        expanded: Whether the row's children are currently shown.
        flags: Per-view-layer flag states keyed by
            ``{view_layer_name: {flag_name: bool}}``. A view layer key is
            only present when the collection exists in that view layer.
    """

    path: str
    name: str
    depth: int
    has_children: bool
    expanded: bool
    flags: dict[str, dict[str, bool]]
