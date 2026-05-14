"""Lightweight fades/slides: delta-time driven, cached surfaces (Pi: avoid per-frame alloc)."""

from __future__ import annotations

from dataclasses import dataclass, field

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


@dataclass
class BlackVeilCache:
    """Reusable full-screen RGBA sheet for intro/outro fades (one alloc per resolution)."""

    _surfaces: dict[tuple[int, int], pygame.Surface] = field(default_factory=dict)

    def blit_fade(
        self,
        target: pygame.Surface,
        *,
        alpha: int,
        rgb: tuple[int, int, int] = (6, 4, 14),
    ) -> None:
        """Alpha 0 = invisible, 255 = opaque overlay."""
        a = max(0, min(255, int(alpha)))
        if a <= 0:
            return
        sw, sh = target.get_size()
        key = (sw, sh)
        surf = self._surfaces.get(key)
        if surf is None:
            # Performance: allocate once per resolution; reuse for all fade frames.
            surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
            surf.fill((*rgb, 255))
            self._surfaces[key] = surf
        surf.set_alpha(a)
        target.blit(surf, (0, 0))


@dataclass
class FadeTimer:
    """Non-blocking fade 1→0 over ``duration_ms`` while ``active``."""

    duration_ms: float
    elapsed_ms: float = 0.0

    def reset(self) -> None:
        self.elapsed_ms = 0.0

    def update(self, dt_ms: float, *, active: bool) -> float:
        """Returns overlay alpha 0..255 (fade out black)."""
        if not active or self.duration_ms <= 0:
            self.elapsed_ms = 0.0
            return 0.0
        self.elapsed_ms = min(self.duration_ms, self.elapsed_ms + max(0.0, dt_ms))
        u = self.elapsed_ms / self.duration_ms
        ease = u * u * (3.0 - 2.0 * u)
        return 255.0 * (1.0 - ease)


@dataclass
class SlideProgress:
    """Placeholder slide-in: maps elapsed time to [0,1]."""

    duration_ms: float
    elapsed_ms: float = 0.0

    def update(self, dt_ms: float, *, active: bool) -> float:
        if not active or self.duration_ms <= 0:
            self.elapsed_ms = 0.0
            return 1.0
        self.elapsed_ms = min(self.duration_ms, self.elapsed_ms + max(0.0, dt_ms))
        u = self.elapsed_ms / self.duration_ms
        return u * u * (3.0 - 2.0 * u)
