"""Backward-compatible import path; prefer ``from src.services.input import …``."""

from src.services.input import (
    MENU_CONFIRM,
    InputAction,
    InputIntent,
    InputService,
)

__all__ = ("InputAction", "InputIntent", "InputService", "MENU_CONFIRM")
