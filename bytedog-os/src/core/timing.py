"""Frame clock helpers (Pi: stable dt for animation + HUD)."""

from __future__ import annotations

import pygame


def update_frame_timing(clock: pygame.time.Clock, fps: int, fps_ema: float) -> tuple[float, float]:
    """Single ``tick`` per frame — avoid extra clock calls (60 FPS target)."""
    dt_ms = float(clock.tick(fps))
    ema = 0.9 * fps_ema + 0.1 * (1000.0 / max(dt_ms, 0.001))
    return dt_ms, ema
