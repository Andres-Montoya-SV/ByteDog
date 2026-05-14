"""Lightweight behavior placeholder for Phase 2 Chicha life (no simulation yet)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.pet.animations import ChichaAnimator
    from src.pet.state import PetState


class ChichaBehaviorEngine:
    """
    Future hooks: inactivity → sleep, nav reactions, low-battery nudge.
    Intentionally empty: preserves Phase 1 visuals and input latency.
    """

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def tick(self, _dt_ms: float, _pet: "PetState", _animator: "ChichaAnimator") -> None:
        """Call from main loop when wiring life logic; no-op today."""
        return
