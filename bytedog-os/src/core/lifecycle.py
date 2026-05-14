"""Display / pygame teardown helpers (Phase 2: centralize safe shutdown)."""

from __future__ import annotations

from typing import Any

import pygame


def shutdown_mixer_if_any(audio: Any) -> None:
    """Stop UI audio without raising (mixer may never have init'd on headless CI)."""
    shutdown = getattr(audio, "shutdown", None)
    if callable(shutdown):
        try:
            shutdown()
        except (pygame.error, RuntimeError, OSError):
            pass


def quit_pygame_display() -> None:
    try:
        pygame.quit()
    except pygame.error:
        pass
