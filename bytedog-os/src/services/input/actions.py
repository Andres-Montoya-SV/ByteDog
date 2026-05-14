"""Semantic input actions for the launcher (keyboard + gamepad map here, not raw SDL)."""

from __future__ import annotations

from enum import Enum, auto


class InputAction(Enum):
    MENU_UP = auto()
    MENU_DOWN = auto()
    MENU_LEFT = auto()
    MENU_RIGHT = auto()
    CONFIRM = auto()
    BACK = auto()
    EXIT = auto()
    TOGGLE_DEBUG = auto()


# Back-compat aliases used elsewhere in the codebase.
InputIntent = InputAction
MENU_CONFIRM = InputAction.CONFIRM
