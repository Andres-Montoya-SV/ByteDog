"""Optional on-device debug HUD (F3) for handheld input tuning."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from src.ui.theme import Theme, load_ui_font


@dataclass(frozen=True, slots=True)
class InputDebugSnapshot:
    """Bundle HUD fields so ``ByteDogApp`` stays thin."""

    fps_ema: float
    joystick_count: int
    controller_names: str
    axes_summary: str
    menu_label: str
    menu_index: int
    last_raw_button: str
    last_raw_axis: str
    last_raw_hat: str
    last_semantic_action: str
    raw_input_lines: tuple[str, ...]


def build_input_debug_overlay_lines(snap: InputDebugSnapshot) -> list[str]:
    lines = [
        f"FPS ~{snap.fps_ema:.0f}",
        f"joysticks: {snap.joystick_count}",
    ]
    if snap.joystick_count <= 0:
        lines.append("names: (none)")
        lines.append("axes: —")
    else:
        lines.append(f"names: {snap.controller_names}")
        lines.append(f"axes: {snap.axes_summary}")
    lines.append(f"menu selection: {snap.menu_label} (#{snap.menu_index})")
    lines.append(f"last raw button: {snap.last_raw_button}")
    lines.append(f"last raw axis (event): {snap.last_raw_axis}")
    lines.append(f"last raw hat (event): {snap.last_raw_hat}")
    lines.append(f"last semantic action: {snap.last_semantic_action}")
    lines.extend(snap.raw_input_lines)
    lines.append("F3 = toggle overlay | input.debug = terminal")
    return lines


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
