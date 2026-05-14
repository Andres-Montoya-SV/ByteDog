"""Load menu icons from PNG files in assets/images (Pi-friendly, no SVG stack)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pygame

from src.ui.menu import MenuAction
from src.ui.theme import load_sans_ui_font


MENU_ICON_FILES: dict[MenuAction, str] = {
    MenuAction.RETRO_GAMES: "retro-games.png",
    MenuAction.CYBERDECK: "cyberdeck.png",
    MenuAction.CHICHA: "chicha.png",
    MenuAction.TERMINAL: "terminal.png",
    MenuAction.SETTINGS: "settings.png",
    MenuAction.SHUTDOWN: "shutdown.png",
}


def load_png_icon(path: Path, size: int) -> Optional[pygame.Surface]:
    if not path.is_file():
        return None
    try:
        img = pygame.image.load(str(path))
        try:
            img = img.convert_alpha()
        except pygame.error:
            pass
        if img.get_size() != (size, size):
            img = pygame.transform.smoothscale(img, (size, size))
        return img
    except (pygame.error, OSError, ValueError):
        return None


def _placeholder_icon(letter: str, size: int, accent: pygame.Color) -> pygame.Surface:
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    pygame.draw.rect(
        surf, (accent.r, accent.g, accent.b, 55), surf.get_rect(), border_radius=8
    )
    pygame.draw.rect(surf, accent, surf.get_rect(), width=2, border_radius=8)
    font = load_sans_ui_font(max(size // 2, 10))
    ch = letter[:1].upper() or "?"
    t = font.render(ch, True, (240, 235, 255))
    surf.blit(t, ((size - t.get_width()) // 2, (size - t.get_height()) // 2))
    return surf


class MenuIconCache:
    """Per-action icons from PNG; letter tile if file missing."""

    def __init__(self, images_dir: Path, pixel_size: int = 40) -> None:
        self._images_dir = images_dir
        self._pixel_size = pixel_size
        self._cache: dict[MenuAction, pygame.Surface] = {}
        self._fallback_accent = pygame.Color(160, 60, 255)

    def preload(self, accent: pygame.Color) -> None:
        self._fallback_accent = accent
        for action, filename in MENU_ICON_FILES.items():
            path = self._images_dir / filename
            surf = load_png_icon(path, self._pixel_size)
            if surf is None:
                letter = action.name.split("_")[0][:1] or "?"
                surf = _placeholder_icon(letter, self._pixel_size, accent)
            self._cache[action] = surf

    def get(self, action: MenuAction) -> pygame.Surface:
        return self._cache.get(action) or _placeholder_icon(
            "?", self._pixel_size, self._fallback_accent
        )
