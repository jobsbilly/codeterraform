# user_stubs.py - your space. The game NEVER overwrites this file.
# 
# This module holds type declarations that the in-game editor, the VS Code extension and other editors all read. The game accepts imports from user_stubs as no-ops, so put executable helpers in an in-game Library. Add type aliases, type-only declarations, and re-exported library types here. Import each name explicitly in player scripts. They survive every game update and every "Regenerate Stubs". The generated API stubs are produced by the game; do not edit those directly. Edit this file instead.
#
# user_stubs.py:
#     from typing import Literal
#     MineralId = Literal["iron_ore", "copper_ore"]
#     type SiteScore = tuple[str, float]
#
# script.py:
#     from user_stubs import MineralId, SiteScore
