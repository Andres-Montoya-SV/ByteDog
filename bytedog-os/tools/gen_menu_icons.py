#!/usr/bin/env python3
"""One-shot: write 64×64 PNG menu icons (no Cairo). Run: python tools/gen_menu_icons.py"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "images"


def retro(s: pygame.Surface) -> None:
    """Handheld outline + simple screen grid (no face-like shapes)."""
    c = (220, 220, 235)
    pygame.draw.rect(s, c, pygame.Rect(12, 22, 40, 22), border_radius=4, width=2)
    # Pixel grid on the "display"
    px, py = 18, 28
    for dx in (0, 8, 16, 24):
        for dy in (0, 6):
            pygame.draw.rect(s, c, pygame.Rect(px + dx, py + dy, 4, 4))
    pygame.draw.rect(s, c, pygame.Rect(28, 38, 8, 4), border_radius=1)


def cyber(s: pygame.Surface) -> None:
    c = (180, 100, 255)
    pygame.draw.rect(s, c, pygame.Rect(14, 16, 36, 34), width=2, border_radius=3)
    pygame.draw.line(s, c, (18, 24), (46, 24), 2)
    pygame.draw.rect(s, c, pygame.Rect(22, 30, 20, 12), border_radius=2, width=2)


def chicha(s: pygame.Surface) -> None:
    body = (120, 75, 45)
    ear = (90, 55, 35)
    pygame.draw.ellipse(s, body, pygame.Rect(18, 28, 28, 24))
    pygame.draw.circle(s, body, (44, 36), 14)
    pygame.draw.polygon(s, ear, [(22, 30), (28, 14), (34, 28)])
    pygame.draw.polygon(s, ear, [(38, 28), (46, 14), (50, 30)])
    pygame.draw.rect(s, (200, 160, 255), pygame.Rect(30, 44, 8, 4))


def terminal(s: pygame.Surface) -> None:
    c = (160, 140, 220)
    pygame.draw.rect(s, c, pygame.Rect(12, 14, 40, 36), width=2, border_radius=3)
    pygame.draw.rect(s, c, pygame.Rect(16, 20, 32, 3))
    font = pygame.font.Font(None, 22)
    s.blit(font.render(">_", True, c), (18, 32))


def settings(s: pygame.Surface) -> None:
    c = (170, 120, 240)
    cx, cy = 32, 32
    for i in range(8):
        a = i * (math.tau / 8)
        x1 = cx + int(10 * math.cos(a))
        y1 = cy + int(10 * math.sin(a))
        x2 = cx + int(22 * math.cos(a))
        y2 = cy + int(22 * math.sin(a))
        pygame.draw.line(s, c, (x1, y1), (x2, y2), 3)
    pygame.draw.circle(s, (12, 10, 22), (cx, cy), 8)


def shutdown(s: pygame.Surface) -> None:
    c = (240, 90, 110)
    pygame.draw.circle(s, c, (32, 32), 18, width=3)
    pygame.draw.line(s, c, (24, 24), (40, 40), 3)
    pygame.draw.line(s, c, (40, 24), (24, 40), 3)


def main() -> None:
    pygame.init()
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = (
        ("retro-games", retro),
        ("cyberdeck", cyber),
        ("chicha", chicha),
        ("terminal", terminal),
        ("settings", settings),
        ("shutdown", shutdown),
    )
    for name, fn in pairs:
        surf = pygame.Surface((64, 64), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        fn(surf)
        path = OUT / f"{name}.png"
        pygame.image.save(surf, str(path))
        print("wrote", path)
    pygame.quit()


if __name__ == "__main__":
    main()
    sys.exit(0)
