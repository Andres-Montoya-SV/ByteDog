"""Optional on-device debug HUD (F3) for handheld input tuning."""

from __future__ import annotations

import pygame

from src.ui.theme import Theme, load_ui_font


def draw_input_debug_overlay(
    surface: pygame.Surface,
    theme: Theme,
    lines: list[str],
    font_size: int = 15,
) -> None:
    if not lines:
        return
    font = load_ui_font(font_size)
    line_h = font.get_linesize() + 2
    text_w = max(font.size(line)[0] for line in lines)
    pad_x, pad_y = 12, 10
    box_w = min(surface.get_width() - 16, text_w + pad_x * 2)
    box_h = min(surface.get_height() - 16, len(lines) * line_h + pad_y * 2)
    panel = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    panel.fill((12, 10, 22, 235))
    pygame.draw.rect(panel, theme.accent_orange, panel.get_rect(), width=2, border_radius=4)
    y = pad_y
    for line in lines:
        surf = font.render(line[:120], True, theme.text_primary)
        panel.blit(surf, (pad_x, y))
        y += line_h
    surface.blit(panel, (8, 8))
