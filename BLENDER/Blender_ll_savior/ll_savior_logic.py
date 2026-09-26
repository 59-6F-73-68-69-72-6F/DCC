"""
Core functionality for managing light linking states,
 saving light linking state  in a temporary stash file,
 and re-establishing light links in the scene from the stash.
 """


import os
import json

import bpy


def _link_state_of(wrapper) -> str:
    """ Return the light linking state ('INCLUDE' or 'EXCLUDE') of a collection member. """
    ll = getattr(wrapper, "light_linking", None)
    state = getattr(ll, "link_state", None) if ll else None
    return state if state in ("INCLUDE", "EXCLUDE") else "INCLUDE"


def _set_link_state(wrapper, state):
    """ Write the light linking state (INCLUDE/EXCLUDE) back onto a collection member wrapper."""
    ll = getattr(wrapper, "light_linking", None)
    if ll is not None and state in ("INCLUDE", "EXCLUDE"):
        ll.link_state = state


def stash_light_links():
    """
    Scans scene lights and creates a mapping of each light to
    the receiving and blocking collections and objects linked to it, with their link state.
    """
    receiver_stash: dict[str, list[list]] = {}
    blocker_stash: dict[str, list[list]] = {}

    for obj in bpy.context.scene.objects:
        if obj.type != 'LIGHT':
            continue

        ll = getattr(obj, "light_linking", None)
        if ll is None:
            continue
        rec_col = ll.receiver_collection
        block_col = ll.blocker_collection

        # 1. --- Stash Receiver Links ---
        if rec_col is not None:
            receiver_value: list[list] = []

            # Stash collections in the receiver
            for i, child in enumerate(rec_col.children):
                receiver_value.append(["collections",
                                       child.name,
                                       _link_state_of(rec_col.collection_children[i])])

            # Stash objects in the receiver
            for i, member in enumerate(rec_col.objects):
                receiver_value.append(["objects",
                                       member.name,
                                       _link_state_of(rec_col.collection_objects[i])])
            receiver_stash[obj.name] = receiver_value

        # 2. --- Stash Blocker Links ---
        if block_col is not None:
            blocker_value: list[list] = []

            # Stash collections in the blocker
            for i, child in enumerate(block_col.children):
                blocker_value.append(["collections",
                                      child.name,
                                      _link_state_of(block_col.collection_children[i])])

            # Stash objects in the blocker
            for i, member in enumerate(block_col.objects):
                blocker_value.append(["objects",
                                      member.name,
                                      _link_state_of(block_col.collection_objects[i])])
            blocker_stash[obj.name] = blocker_value

    # Save the mapping to a temporary JSON file for persistence
    temp_file = _stash_file_path()
    with open(temp_file, 'w') as f:
        json.dump({"receiver": receiver_stash, "blocker": blocker_stash}, f, indent=2)


def _stash_file_path() -> str:
    """ Return the path to the stash JSON file inside the addon's own temp folder. """
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    return os.path.join(temp_dir, "light_linking_stash.json")


def load_stash() -> tuple[dict, dict]:
    """
    Load the JSON file.
    Returns empty dicts when the file is missing or unreadable.
    """
    temp_file = _stash_file_path()
    try:
        with open(temp_file, 'r') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}, {}

    receiver = data.get("receiver") if isinstance(data, dict) else None
    blocker = data.get("blocker") if isinstance(data, dict) else None
    return receiver if isinstance(receiver, dict) else {}, blocker if isinstance(blocker, dict) else {}


def delete_stash():
    """Delete the temporary stash file if it exists."""
    temp_file = _stash_file_path()
    if os.path.exists(temp_file):
        os.remove(temp_file)
        print(f"Temp File Deleted : {temp_file}")


def _clear_members(col):
    """ Remove every object and child collection from a light linking collection. """
    if col is None:
        return

    # Remove all members from the collection
    for member in list(col.objects):
        col.objects.unlink(member)

    # Remove all child collections from the collection
    for child in list(col.children):
        col.children.unlink(child)


def _restore_members(col, linked: list[list]):
    """Relink members described by [kind, name, state] triplets, dropping unresolved rules."""
    seen: set[tuple[str, str]] = set()
    for kind, name, state in linked:
        key = (kind, name)
        if key in seen:
            continue
        seen.add(key)

        if kind == "objects":
            target = bpy.data.objects.get(name)
            if target is None:
                continue
            idx = col.objects.find(name)
            if idx < 0:
                col.objects.link(target)
                idx = col.objects.find(name)
            if idx >= 0:
                _set_link_state(col.collection_objects[idx], state)
        elif kind == "collections":
            target = bpy.data.collections.get(name)
            if target is None:
                continue
            idx = col.children.find(name)
            if idx < 0:
                col.children.link(target)
                idx = col.children.find(name)
            if idx >= 0:
                _set_link_state(col.collection_children[idx], state)


def _ensure_link_collection(light, name_suffix: str = "") -> bpy.types.Collection:
    """Return the light's receiver/blocker collection, creating and assigning it if missing."""
    ll = light.light_linking
    attr = "blocker_collection" if name_suffix else "receiver_collection"
    col = getattr(ll, attr)
    if col is None:
        col = bpy.data.collections.new(f"Light Linking for {light.name}{name_suffix}")
        setattr(ll, attr, col)
    print(f"Ensured light linking collection for {light.name}{name_suffix}: {col.name}")
    return col


def re_establish_light_links(receiver_stash: dict[str, list[list]], blocker_stash: dict[str, list[list]]):
    """
    Remove existing light links and re-establish them from the stash mappings.
    Lights absent from both stashes are left untouched.
    """
    for obj in bpy.context.scene.objects:
        if obj.type != 'LIGHT':
            continue

        ll = getattr(obj, "light_linking", None)
        if ll is None:
            continue

        receivers_map = receiver_stash.get(obj.name)
        blockers_map = blocker_stash.get(obj.name)
        if receivers_map is None and blockers_map is None:
            continue

        # Re-establish receiver links
        if receivers_map is not None:
            rec_col = _ensure_link_collection(obj)
            _clear_members(rec_col)
            bpy.context.view_layer.update()
            _restore_members(rec_col, receivers_map)

        # Re-establish blocker links
        if blockers_map is not None:
            block_col = _ensure_link_collection(obj, " (blocked)")
            _clear_members(block_col)
            bpy.context.view_layer.update()
            _restore_members(block_col, blockers_map)
    print("Light linking restoration complete.")
