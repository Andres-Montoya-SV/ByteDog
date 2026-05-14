"""Small reusable draw helpers (Pi: avoid per-frame font allocation in hot paths)."""

from __future__ import annotations

import pygame

from src.ui.theme import Theme, load_sans_ui_font


def draw_panel(
    surface: pygame.Surface,
    theme: Theme,
    rect: pygame.Rect,
    *,
    border_width: int = 2,
    radius: int = 12,
) -> None:
    pygame.draw.rect(surface, theme.bg_panel, rect, border_radius=radius)
    pygame.draw.rect(surface, theme.border, rect, width=border_width, border_radius=radius)


def draw_label(
    surface: pygame.Surface,
    theme: Theme,
    text: str,
    pos: tuple[int, int],
    *,
    size: int = 18,
    bold: bool = False,
    color: pygame.Color | None = None,
) -> None:
    # Font cache could live here in Phase 2; one lookup per call is OK for menus.
    font = load_sans_ui_font(size, bold=bold)
    c = color if color is not None else theme.text_primary
    surface.blit(font.render(text, True, c), pos)


def draw_status_chip(
    surface: pygame.Surface,
    theme: Theme,
    text: str,
    center: tuple[int, int],
    *,
    font_size: int = 14,
) -> None:
    font = load_sans_ui_font(font_size, bold=True)
    t = font.render(text, True, theme.text_dim)
    r = t.get_rect(center=center)
    pad = pygame.Rect(r.x - 6, r.y - 3, r.w + 12, r.h + 6)
    pygame.draw.rect(surface, theme.bg_panel, pad, border_radius=6)
    pygame.draw.rect(surface, theme.accent_purple, pad, width=1, border_radius=6)
    surface.blit(t, r.topleft)


def draw_progress_bar(
    surface: pygame.Surface,
    theme: Theme,
    rect: pygame.Rect,
    progress: float,
    *,
    fill: pygame.Color | None = None,
) -> None:
    """progress in [0,1]."""
    pygame.draw.rect(surface, theme.bg_panel, rect, border_radius=4)
    pygame.draw.rect(surface, theme.border, rect, width=1, border_radius=4)
    p = max(0.0, min(1.0, float(progress)))
    inner = rect.inflate(-4, -4)
    inner.width = max(0, int(inner.width * p))
    col = fill if fill is not None else theme.accent_purple
    pygame.draw.rect(surface, col, inner, border_radius=3)


def draw_icon_button_placeholder(
    surface: pygame.Surface,
    theme: Theme,
    rect: pygame.Rect,
    letter: str,
) -> None:
    draw_panel(surface, theme, rect, border_width=1, radius=8)
    font = load_sans_ui_font(max(rect.h // 2, 10), bold=True)
    ch = letter[:1].upper() or "?"
    t = font.render(ch, True, theme.accent_orange)
    surface.blit(t, (rect.centerx - t.get_width() // 2, rect.centery - t.get_height() // 2))
