"""Lightweight full-screen fades/slides (Phase 2 polish; keep O(1) per frame)."""

from __future__ import annotations

import pygame


def fade_surface_alpha(surface: pygame.Surface, alpha: int) -> pygame.Surface:
    """Return a copy with ``set_alpha`` applied (caller should cache if used every frame)."""
    a = max(0, min(255, int(alpha)))
    out = surface.copy()
    out.set_alpha(a)
    return out


def slide_offset_x(progress: float, width_px: int) -> int:
    """progress in [0,1] → horizontal slide offset for intro placeholders."""
    u = max(0.0, min(1.0, float(progress)))
    return int((1.0 - u) * float(width_px))
