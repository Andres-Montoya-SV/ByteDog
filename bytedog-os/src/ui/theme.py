"""Cyberpunk / retro visual tokens and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Optional

import pygame


@dataclass(frozen=True, slots=True)
class Theme:
    """Palette and typography hints for the launcher."""

    bg: pygame.Color
    bg_panel: pygame.Color
    grid: pygame.Color
    accent_purple: pygame.Color
    accent_orange: pygame.Color
    text_primary: pygame.Color
    text_dim: pygame.Color
    selection_bg: pygame.Color
    border: pygame.Color
    danger: pygame.Color


def default_theme() -> Theme:
    """Handheld / cyberpunk palette aligned with ByteDog OS reference UI."""
    return Theme(
        bg=pygame.Color(5, 5, 8),
        bg_panel=pygame.Color(12, 10, 22),
        grid=pygame.Color(26, 20, 42),
        accent_purple=pygame.Color(168, 72, 255),
        accent_orange=pygame.Color(255, 120, 72),
        text_primary=pygame.Color(242, 238, 252),
        text_dim=pygame.Color(132, 118, 168),
        selection_bg=pygame.Color(72, 38, 118),
        border=pygame.Color(150, 80, 230),
        danger=pygame.Color(255, 80, 80),
    )


_FONT_CACHE: dict[int, pygame.font.Font] = {}
_SANS_FONT_CACHE: dict[tuple[int, bool], pygame.font.Font] = {}


def load_ui_font(size: int) -> pygame.font.Font:
    """Prefer monospace system fonts for a terminal / deck feel."""
    cached = _FONT_CACHE.get(size)
    if cached is not None:
        return cached
    candidates: Final[tuple[str, ...]] = (
        "dejavusansmono",
        "consolas",
        "menlo",
        "monaco",
        "couriernew",
        "freemono",
    )
    for name in candidates:
        try:
            font = pygame.font.SysFont(name, size, bold=True)
            if font:
                _FONT_CACHE[size] = font
                return font
        except (pygame.error, OSError, ValueError):
            continue
    font = pygame.font.Font(None, max(size, 12))
    _FONT_CACHE[size] = font
    return font


def load_sans_ui_font(size: int, *, bold: bool = True) -> pygame.font.Font:
    """Clean sans for launcher chrome (reference UI); falls back to monospace."""
    key = (size, bold)
    cached = _SANS_FONT_CACHE.get(key)
    if cached is not None:
        return cached
    candidates: Final[tuple[str, ...]] = (
        "helveticaneue",
        "helvetica",
        "sf pro display",
        "sfprotext",
        "segoe ui",
        "arial",
        "liberation sans",
        "noto sans",
    )
    for name in candidates:
        try:
            font = pygame.font.SysFont(name, size, bold=bold)
            if font:
                _SANS_FONT_CACHE[key] = font
                return font
        except (pygame.error, OSError, ValueError):
            continue
    fallback = load_ui_font(size)
    _SANS_FONT_CACHE[key] = fallback
    return fallback


class ScanlineOverlay:
    """CRT-style scanlines built once per resolution (Pi-friendly)."""

    __slots__ = ("_key", "_surface")

    def __init__(self) -> None:
        self._surface: Optional[pygame.Surface] = None
        self._key: Optional[tuple[int, int, int, int]] = None

    def blit(self, target: pygame.Surface, step: int = 4, alpha: int = 28) -> None:
        w, h = target.get_size()
        key = (w, h, step, alpha)
        if self._surface is None or self._key != key:
            overlay = pygame.Surface((w, h), pygame.SRCALPHA)
            for y in range(0, h, step):
                pygame.draw.line(overlay, (0, 0, 0, alpha), (0, y), (w, y))
            self._surface = overlay
            self._key = key
        target.blit(self._surface, (0, 0))


def draw_grid(
    surface: pygame.Surface,
    color: pygame.Color,
    cell: int = 48,
    line_width: int = 1,
) -> None:
    w, h = surface.get_size()
    for x in range(0, w, cell):
        pygame.draw.line(surface, color, (x, 0), (x, h), line_width)
    for y in range(0, h, cell):
        pygame.draw.line(surface, color, (0, y), (w, y), line_width)
