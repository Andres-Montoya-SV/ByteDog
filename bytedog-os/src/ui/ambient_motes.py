"""Lightweight drifting particles for launcher hero panel (Phase 2)."""

from __future__ import annotations

import random
from dataclasses import dataclass

import pygame


@dataclass(slots=True)
class _Mote:
    x: float
    y: float
    vx: float
    vy: float
    r: int
    a: int


class AmbientMotes:
    """Tiny dust motes; bounded count, no allocations per frame after init."""

    __slots__ = ("_motes", "_rng", "_w", "_h", "_count")

    def __init__(self, count: int = 10) -> None:
        self._motes: list[_Mote] = []
        self._rng = random.Random(42)
        self._w = 0
        self._h = 0
        self._count = max(4, min(24, count))

    def resize(self, w: int, h: int) -> None:
        if w == self._w and h == self._h and len(self._motes) == self._count:
            return
        self._w = w
        self._h = h
        self._motes.clear()
        for _ in range(self._count):
            self._motes.append(
                _Mote(
                    x=self._rng.uniform(0, max(1, w)),
                    y=self._rng.uniform(0, max(1, h)),
                    vx=self._rng.uniform(-8, 8),
                    vy=self._rng.uniform(-5, 5),
                    r=self._rng.randint(1, 2),
                    a=self._rng.randint(18, 55),
                )
            )

    def update(self, dt_ms: float) -> None:
        if not self._motes or self._w <= 0 or self._h <= 0:
            return
        t = dt_ms * 0.001
        for m in self._motes:
            m.x += m.vx * t
            m.y += m.vy * t
            if m.x < -4 or m.x > self._w + 4:
                m.x = self._rng.uniform(0, self._w)
                m.y = self._rng.uniform(0, self._h)
            if m.y < -4 or m.y > self._h + 4:
                m.y = self._rng.uniform(0, self._h)
                m.x = self._rng.uniform(0, self._w)

    def draw(self, target: pygame.Surface, rect: pygame.Rect, color: pygame.Color) -> None:
        for m in self._motes:
            px = int(rect.x + m.x * rect.w / max(1, self._w))
            py = int(rect.y + m.y * rect.h / max(1, self._h))
            c = pygame.Color(color.r, color.g, color.b, m.a)
            pygame.draw.circle(target, c, (px, py), m.r)
