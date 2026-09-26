"""
Delegate  to``ll_savior_logic`` to handle the core functionality of saving and restoring light linking states,
and provide a simple interface for the UI layer to call into.
"""

from . import ll_savior_logic as logic


def save_light_links():
    """ Stash the current light linking state of all lights into the temporary JSON file. """
    logic.stash_light_links()


def restore_light_links():
    """ Restore the light linking state from the stash, then delete the stash file. """
    receiver, blocker = logic.load_stash()
    logic.re_establish_light_links(receiver, blocker)
    logic.delete_stash()
