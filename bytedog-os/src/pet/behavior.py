"""Deterministic Chicha companion hooks: timers + edges, no AI."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Optional

from src.pet.chicha_life import ChichaLifeState

if TYPE_CHECKING:
    from src.pet.animations import ChichaAnimator
    from src.pet.state import PetState
    from src.services.audio import AudioService


class ChichaBehaviorEngine:
    """
    Tracks interaction edges for future audio/personality hooks.
    Life-state computation stays in ``ChichaAnimator``; this layer is for orchestration.
    """

    def __init__(self, chicha_cfg: dict[str, Any], *, audio: Optional["AudioService"] = None) -> None:
        self._cfg = chicha_cfg
        self._audio = audio
        self._was_sleepy = False
        self._wake_ack_chance = float(chicha_cfg.get("wake_ack_chance", 0.12))

    def set_audio(self, audio: Optional["AudioService"]) -> None:
        self._audio = audio

    def tick(self, dt_ms: float, pet: "PetState", animator: "ChichaAnimator") -> None:
        _ = dt_ms
        _ = pet
        ls = animator.life_state
        now_sleepy = ls is ChichaLifeState.SLEEPY
        if self._was_sleepy and not now_sleepy:
            if self._audio is not None and self._wake_ack_chance > 0.0:
                if random.random() < self._wake_ack_chance:
                    self._audio.play_chicha_react()
        self._was_sleepy = now_sleepy

    def on_confirm(self, animator: "ChichaAnimator") -> None:
        animator.apply_confirm_boost()
