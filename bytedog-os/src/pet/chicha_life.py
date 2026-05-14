"""Chicha companion life states (Phase 2): timers and context, no AI.

Extension points for later: GPIO tactile input, rumble on ``low_battery``,
dock presence, emulator foreground — consume ``ChichaLifeState`` from UI/audio hooks.
"""

from __future__ import annotations

from enum import Enum
from typing import Final


class ChichaLifeState(str, Enum):
    """Logical companion state (clips may map 1:1 or fall back)."""

    IDLE = "idle"
    HAPPY = "happy"
    SLEEPY = "sleepy"
    CURIOUS = "curious"
    ALERT = "alert"
    LOW_BATTERY = "low_battery"
    GAMING = "gaming"
    BOOTING = "booting"


# Priority order: first clip name in ``available`` wins.
_STATE_TO_CLIPS: Final[dict[ChichaLifeState, tuple[str, ...]]] = {
    ChichaLifeState.BOOTING: ("booting", "alert", "idle"),
    ChichaLifeState.LOW_BATTERY: ("low_battery", "alert", "idle"),
    ChichaLifeState.GAMING: ("gaming", "happy", "idle"),
    ChichaLifeState.SLEEPY: ("sleep", "idle"),
    ChichaLifeState.HAPPY: ("happy", "idle"),
    ChichaLifeState.CURIOUS: ("curious", "happy", "idle"),
    ChichaLifeState.ALERT: ("alert", "idle"),
    ChichaLifeState.IDLE: ("idle",),
}


def clip_for_life_state(state: ChichaLifeState, available: frozenset[str]) -> str:
    """Pick best asset clip for a life state; always returns a member of ``available`` or ``idle``."""
    for name in _STATE_TO_CLIPS.get(state, ("idle",)):
        if name in available:
            return name
    if "idle" in available:
        return "idle"
    if available:
        return sorted(available)[0]
    return "idle"
