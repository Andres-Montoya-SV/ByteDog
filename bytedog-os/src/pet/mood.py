"""Pet mood vocabulary (aligns with ``assets/chicha/<mood>/`` folders)."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.pet.chicha_life import ChichaLifeState


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

    @classmethod
    def from_life_state(cls, life: ChichaLifeState) -> ChichaMood:
        from src.pet.chicha_life import ChichaLifeState as LS

        mapping: dict[LS, ChichaMood] = {
            LS.IDLE: cls.IDLE,
            LS.HAPPY: cls.HAPPY,
            LS.SLEEPY: cls.SLEEPY,
            LS.CURIOUS: cls.CURIOUS,
            LS.ALERT: cls.ALERT,
            LS.LOW_BATTERY: cls.LOW_BATTERY,
            LS.GAMING: cls.GAMING,
            LS.BOOTING: cls.BOOTING,
        }
        return mapping.get(life, cls.IDLE)
