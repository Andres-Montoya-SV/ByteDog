"""Minimal read-only settings panel for handheld diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from src.ui.screens import wrap_text_to_width
from src.ui.theme import Theme, load_ui_font


@dataclass(frozen=True, slots=True)
class SettingsDisplayInfo:
    controller_summary: str
    resolution: str
    fullscreen: bool
    fps_target: int
    audio_ready: bool
    input_debug: bool


def draw_settings_screen(
    surface: pygame.Surface,
    theme: Theme,
    info: SettingsDisplayInfo,
    *,
    title_size: int = 36,
    body_size: int = 22,
    content_bottom_y: int | None = None,
) -> None:
    """
    Draw settings panel. If content_bottom_y is set, the panel stops above that Y
    so status bar / footer can sit below without overlap.
    """
    sw, sh = surface.get_size()
    margin = max(20, min(sw, sh) // 28)
    title_font = load_ui_font(title_size)
    body_font = load_ui_font(body_size)
    small = load_ui_font(max(16, body_size - 4))

    bottom_limit = content_bottom_y if content_bottom_y is not None else sh - margin
    gap_above_status = 8
    panel_h = max(80, bottom_limit - margin - gap_above_status)
    panel = pygame.Rect(margin, margin, sw - 2 * margin, panel_h)
    pygame.draw.rect(surface, theme.bg_panel, panel, border_radius=12)
    pygame.draw.rect(surface, theme.accent_purple, panel, width=2, border_radius=12)

    inner_pad_x = 24
    inner_pad_right = 20
    max_text_w = max(80, panel.width - inner_pad_x - inner_pad_right)

    x = panel.x + inner_pad_x
    y = panel.y + 20
    title = title_font.render("Settings", True, theme.text_primary)
    surface.blit(title, (x, y))
    y += title_font.get_linesize() + 16

    raw_lines: list[tuple[str, bool]] = [
        (f"Controller · {info.controller_summary}", False),
        (
            f"Display · {info.resolution}  {'fullscreen' if info.fullscreen else 'windowed'}",
            False,
        ),
        (f"FPS target · {info.fps_target}", False),
        (f"Audio · {'ready' if info.audio_ready else 'unavailable'}", False),
        (f"Input debug (config) · {'on' if info.input_debug else 'off'}", False),
        ("", False),
        ("Back · Esc / Circle", True),
        ("F3 toggles debug overlay in launcher", True),
    ]

    line_gap = 6
    for text, is_hint in raw_lines:
        font = small if is_hint else body_font
        if not text:
            y += 6
            continue
        color = theme.text_dim if is_hint else theme.text_primary
        for part in wrap_text_to_width(font, text, max_text_w):
            if y + font.get_linesize() > panel.bottom - 8:
                break
            surf = font.render(part, True, color)
            surface.blit(surf, (x, y))
            y += font.get_linesize() + line_gap
