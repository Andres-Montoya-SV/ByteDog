"""Screen composition for the Phase 1 launcher."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pygame

from src.ui.menu import LauncherMenu
from src.ui.theme import ScanlineOverlay, Theme, draw_grid, load_ui_font

if TYPE_CHECKING:
    from src.pet.state import PetState


_bg_grid_key: tuple[Any, ...] | None = None
_bg_grid_surface: pygame.Surface | None = None


def _color_key(c: pygame.Color) -> tuple[int, int, int, int]:
    return (c.r, c.g, c.b, c.a)


def draw_launcher_background(surface: pygame.Surface, theme: Theme) -> None:
    """Fill + grid; raster cached per resolution and palette (Pi-friendly)."""
    global _bg_grid_key, _bg_grid_surface
    w, h = surface.get_size()
    key = (w, h, _color_key(theme.bg), _color_key(theme.grid))
    if _bg_grid_surface is None or _bg_grid_key != key:
        buf = pygame.Surface((w, h))
        buf.fill(theme.bg)
        draw_grid(buf, theme.grid, cell=56, line_width=1)
        _bg_grid_surface = buf
        _bg_grid_key = key
    surface.blit(_bg_grid_surface, (0, 0))


@dataclass(slots=True)
class LayoutMetrics:
    margin: int
    title_size: int
    menu_size: int
    stat_size: int
    pet_panel_width: int
    menu_highlight_width: int
    stat_line_spacing: int
    menu_x: int


def compute_layout(screen_w: int, screen_h: int) -> LayoutMetrics:
    """Tuned for ~800×480 handheld-class panels (5\" landscape)."""
    short = min(screen_w, screen_h)
    margin = max(14, short // 32)
    title_size = max(30, min(56, short // 8))
    menu_size = max(22, min(40, short // 12))
    stat_size = max(18, min(30, short // 18))
    pet_panel_width = max(
        200,
        min(int(screen_h * 0.58), int(screen_w * 0.46), screen_w - margin * 2 - 200),
    )
    menu_highlight_width = min(440, max(260, int(screen_w * 0.48)))
    stat_line_spacing = 4 if short < 520 else 3
    menu_x = max(24, margin + 4)
    return LayoutMetrics(
        margin=margin,
        title_size=title_size,
        menu_size=menu_size,
        stat_size=stat_size,
        pet_panel_width=pet_panel_width,
        menu_highlight_width=menu_highlight_width,
        stat_line_spacing=stat_line_spacing,
        menu_x=menu_x,
    )


def draw_title(surface: pygame.Surface, theme: Theme, text: str, y: int, size: int, x: int) -> None:
    font = load_ui_font(size)
    shadow = font.render(text, True, (0, 0, 0))
    glow = font.render(text, True, theme.accent_purple)
    main = font.render(text, True, theme.text_primary)
    surface.blit(shadow, (x + 3, y + 3))
    surface.blit(glow, (x + 1, y + 1))
    surface.blit(main, (x, y))


def draw_menu(
    surface: pygame.Surface,
    theme: Theme,
    menu: LauncherMenu,
    top: int,
    item_height: int,
    font_size: int,
    menu_x: int,
    highlight_width: int,
) -> None:
    font = load_ui_font(font_size)
    for i, item in enumerate(menu.items):
        y = top + i * item_height
        selected = i == menu.selected_index
        label = f"{'> ' if selected else '  '}{item.label}"
        color = theme.accent_orange if selected else theme.text_dim
        if selected:
            pad = pygame.Rect(menu_x - 10, y - 4, highlight_width, item_height)
            pygame.draw.rect(surface, theme.selection_bg, pad, border_radius=6)
            pygame.draw.rect(surface, theme.border, pad, width=2, border_radius=6)
        surf = font.render(label, True, color)
        surface.blit(surf, (menu_x, y))


def draw_pet_panel_frame(surface: pygame.Surface, theme: Theme, rect: pygame.Rect) -> None:
    pygame.draw.rect(surface, theme.bg_panel, rect, border_radius=10)
    pygame.draw.rect(surface, theme.border, rect, width=2, border_radius=10)
    glow = rect.inflate(6, 6)
    pygame.draw.rect(surface, theme.accent_purple, glow, width=1, border_radius=12)


def draw_stats(
    surface: pygame.Surface,
    theme: Theme,
    pet: PetState,
    top_left: tuple[int, int],
    font_size: int,
    line_spacing: int,
) -> None:
    font = load_ui_font(font_size)
    lines = [
        f"MOOD   {pet.mood}",
        f"LEVEL  {pet.level}",
        f"XP     {pet.xp}",
        f"HUNGER {pet.hunger}",
        f"ENERGY {pet.energy}",
    ]
    x, y = top_left
    step = font.get_linesize() + line_spacing
    for line in lines:
        surf = font.render(line, True, theme.text_primary)
        surface.blit(surf, (x, y))
        y += step


def measure_wrapped_status_bar(
    lines: list[str], font_size: int, bar_width: int
) -> tuple[list[str], int]:
    """
    Word-wrap status strings to the bar width; return wrapped lines and total height
    (padding + lines), for positioning before draw.
    """
    font = load_ui_font(font_size)
    max_w = max(40, bar_width - 16)
    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(wrap_text_to_width(font, line, max_w))
    # Keep in sync with draw_status_bar_lines (top inset 6, same line step).
    top_pad = 6
    bottom_pad = 6
    line_step = font.get_linesize() + 1
    height = top_pad + len(wrapped) * line_step + bottom_pad
    return wrapped, height


def draw_status_bar_lines(
    surface: pygame.Surface,
    theme: Theme,
    wrapped_lines: list[str],
    font_size: int,
    area: pygame.Rect,
) -> None:
    font = load_ui_font(font_size)
    x, y = area.x + 8, area.y + 6
    for line in wrapped_lines:
        surf = font.render(line, True, theme.text_dim)
        surface.blit(surf, (x, y))
        y += font.get_linesize() + 1


def draw_status_bar(
    surface: pygame.Surface,
    theme: Theme,
    lines: list[str],
    font_size: int,
    area: pygame.Rect,
) -> None:
    """Legacy helper: wraps to area.width; caller should size area.height using measure_wrapped_status_bar."""
    wrapped, _ = measure_wrapped_status_bar(lines, font_size, area.width)
    draw_status_bar_lines(surface, theme, wrapped, font_size, area)


def draw_overlay_message(
    surface: pygame.Surface,
    theme: Theme,
    message: str,
    font_size: int,
) -> None:
    sw, sh = surface.get_size()
    font = load_ui_font(font_size)
    line_gap = 4
    pad_x, pad_y = 28, 22
    max_inner = max(160, min(480, sw - 48))
    lines = wrap_text_to_width(font, message, max_inner)
    line_surfs = [font.render(line, True, theme.text_primary) for line in lines]
    line_h = font.get_linesize()
    content_w = max((s.get_width() for s in line_surfs), default=0)
    content_h = len(line_surfs) * line_h + max(0, len(line_surfs) - 1) * line_gap
    box_w = min(sw - 32, content_w + pad_x * 2)
    box_h = min(sh - 32, content_h + pad_y * 2)
    box = pygame.Rect(0, 0, box_w, box_h)
    box.center = (sw // 2, sh // 2)
    pygame.draw.rect(surface, theme.bg_panel, box, border_radius=12)
    pygame.draw.rect(surface, theme.accent_orange, box, width=2, border_radius=12)
    inner_top = box.y + pad_y
    for i, surf in enumerate(line_surfs):
        x = box.centerx - surf.get_width() // 2
        y = inner_top + i * (line_h + line_gap)
        surface.blit(surf, (x, y))


def draw_confirm_action_dialog(
    surface: pygame.Surface,
    theme: Theme,
    *,
    title: str,
    confirm_hint: str,
    cancel_hint: str,
    title_font_size: int,
    hint_font_size: int,
    border_color: pygame.Color | None = None,
) -> None:
    """Dim the frame and show a two-choice modal (drawn after gameplay UI, before scanlines)."""
    sw, sh = surface.get_size()
    veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
    veil.fill((8, 6, 18, 188))
    surface.blit(veil, (0, 0))

    border = border_color if border_color is not None else theme.accent_orange
    title_font = load_ui_font(title_font_size)
    hint_font = load_ui_font(hint_font_size)
    title_s = title_font.render(title, True, theme.text_primary)
    hints = (
        hint_font.render(confirm_hint, True, theme.text_dim),
        hint_font.render(cancel_hint, True, theme.text_dim),
    )
    line_gap = 6
    pad_x, pad_y = 32, 26
    hints_h = sum(h.get_height() for h in hints) + line_gap * max(0, len(hints) - 1)
    inner_w = max(title_s.get_width(), max(h.get_width() for h in hints))
    inner_h = title_s.get_height() + line_gap + 4 + hints_h
    box_w = min(sw - 36, inner_w + pad_x * 2)
    box_h = min(sh - 36, inner_h + pad_y * 2)
    box = pygame.Rect(0, 0, box_w, box_h)
    box.center = (sw // 2, sh // 2)
    pygame.draw.rect(surface, theme.bg_panel, box, border_radius=12)
    pygame.draw.rect(surface, border, box, width=2, border_radius=12)

    y = box.y + pad_y
    surface.blit(title_s, (box.centerx - title_s.get_width() // 2, y))
    y += title_s.get_height() + line_gap + 4
    for i, h in enumerate(hints):
        surface.blit(h, (box.centerx - h.get_width() // 2, y))
        y += h.get_height()
        if i < len(hints) - 1:
            y += line_gap


def draw_quit_confirm_dialog(
    surface: pygame.Surface,
    theme: Theme,
    *,
    title_font_size: int,
    hint_font_size: int,
) -> None:
    draw_confirm_action_dialog(
        surface,
        theme,
        title="Quit ByteDog OS?",
        confirm_hint="Enter or A button · quit",
        cancel_hint="Esc or B button · stay",
        title_font_size=title_font_size,
        hint_font_size=hint_font_size,
    )


def wrap_text_to_width(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    """Word-wrap using glyph width so lines fit inside the dialog inner width."""
    stripped = text.strip()
    if not stripped:
        return [""]
    words = stripped.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip() if current else word
        if font.size(trial)[0] <= max_width:
            current = trial
            continue
        if current:
            lines.append(current)
        if font.size(word)[0] <= max_width:
            current = word
        else:
            lines.extend(_break_long_token(font, word, max_width))
            current = ""
    if current:
        lines.append(current)
    return lines or [stripped]


def _break_long_token(font: pygame.font.Font, word: str, max_width: int) -> list[str]:
    chunks: list[str] = []
    buf = ""
    for ch in word:
        trial = buf + ch
        if font.size(trial)[0] <= max_width:
            buf = trial
        else:
            if buf:
                chunks.append(buf)
            buf = ch
    if buf:
        chunks.append(buf)
    return chunks


_vignette_key: tuple[int, int, int, int, int] | None = None
_vignette_surf: pygame.Surface | None = None


def blit_edge_vignette(surface: pygame.Surface, theme: Theme) -> None:
    """Subtle corner darkening; cached per resolution (cheap multiply on composite)."""
    global _vignette_key, _vignette_surf
    w, h = surface.get_size()
    key = (w, h, theme.bg.r, theme.bg.g, theme.bg.b)
    if _vignette_surf is None or _vignette_key != key:
        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(0, max(w, h) // 2, 3):
            a = max(0, 55 - i // 5)
            if a <= 0:
                break
            pygame.draw.rect(
                ov,
                (theme.bg.r, theme.bg.g, theme.bg.b, min(90, a)),
                pygame.Rect(i, i, w - 2 * i, h - 2 * i),
                width=2,
                border_radius=max(8, 24 - i // 4),
            )
        _vignette_surf = ov
        _vignette_key = key
    surface.blit(_vignette_surf, (0, 0))


def finalize_frame_effects(surface: pygame.Surface, scanlines: ScanlineOverlay, theme: Theme | None = None) -> None:
    if theme is not None:
        blit_edge_vignette(surface, theme)
    scanlines.blit(surface)
