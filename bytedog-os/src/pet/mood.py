"""Pet mood vocabulary (aligns with ``assets/chicha/<mood>/`` folders)."""

from __future__ import annotations

from enum import Enum


class ChichaMood(str, Enum):
    """Static pose / life keys (not an AI mood model)."""

    IDLE = "idle"
    HAPPY = "happy"
    SLEEPY = "sleepy"
    CURIOUS = "curious"
    ALERT = "alert"
    LOW_BATTERY = "low_battery"
    GAMING = "gaming"
    BOOTING = "booting"
    SLEEP = "sleep"
