"""Settings panel: navigable rows, toggles, placeholders (Phase 2 polish)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto

import pygame

from src.storage.ui_prefs import UiPreferences
from src.ui.screens import wrap_text_to_width
from src.ui.theme import Theme, load_ui_font


class SettingsRow(Enum):
    SFX = auto()
    AMBIENT = auto()
    CHICHA_REACTIVE = auto()
    BRIGHTNESS = auto()
    THEME_PREVIEW = auto()
    BACK = auto()


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
    prefs: UiPreferences,
    selected: SettingsRow,
    anim_phase_s: float,
    *,
    title_size: int = 36,
    body_size: int = 22,
    content_bottom_y: int | None = None,
) -> None:
    sw, sh = surface.get_size()
    margin = max(20, min(sw, sh) // 28)
    title_font = load_ui_font(title_size)
    body_font = load_ui_font(body_size)
    small = load_ui_font(max(16, body_size - 4))

    bottom_limit = content_bottom_y if content_bottom_y is not None else sh - margin
    gap_above_status = 14
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
    y += title_font.get_linesize() + 18

    rows: list[tuple[SettingsRow, str, str]] = [
        (SettingsRow.SFX, "Sound effects", "ON" if prefs.sfx_enabled else "OFF"),
        (SettingsRow.AMBIENT, "Ambient menu hum", "ON" if prefs.ambient_menu_enabled else "OFF"),
        (SettingsRow.CHICHA_REACTIVE, "Chicha reacts to navigation", "ON" if prefs.chicha_reactive_nav else "OFF"),
        (
            SettingsRow.BRIGHTNESS,
            "Brightness (backlight)",
            f"{prefs.brightness_placeholder}% · GPIO hook later",
        ),
        (SettingsRow.THEME_PREVIEW, "Theme preview", "Cozy cyberdeck · more palettes later"),
        (SettingsRow.BACK, "Back to launcher", "Esc / Circle"),
    ]

    pulse = 0.5 + 0.5 * math.sin(anim_phase_s * math.tau * 0.9)

    # Keep rows strictly inside the panel; diagnostics/meta clip below with their own checks.
    panel_inner_bottom = panel.bottom - 8
    body_ls = body_font.get_linesize()
    small_ls = small.get_linesize()
    core_h = body_ls + 2 + small_ls
    pad_h = body_ls + small_ls + 10
    pad_top_slack = 4
    base_gap = 14
    n_rows = len(rows)
    row0_y = y
    available_for_rows = panel_inner_bottom - row0_y
    for gap_try in range(base_gap, 3, -1):
        if n_rows * (core_h + gap_try) <= available_for_rows:
            row_gap = gap_try
            break
    else:
        row_gap = 4

    for row_id, label, value in rows:
        # Full row includes highlight pad extending `pad_top_slack` above the label.
        row_bottom = y + core_h + row_gap
        pad_bottom = y - pad_top_slack + pad_h
        if max(row_bottom, pad_bottom) > panel_inner_bottom:
            break

        sel = row_id == selected
        row_top = y
        if sel:
            pad = pygame.Rect(
                x - 10,
                row_top - pad_top_slack,
                panel.right - x - 14,
                pad_h,
            )
            glow = pygame.Surface((pad.w, pad.h), pygame.SRCALPHA)
            glow.fill((theme.accent_purple.r, theme.accent_purple.g, theme.accent_purple.b, int(40 + 50 * pulse)))
            surface.blit(glow, pad.topleft)
            pygame.draw.rect(surface, theme.accent_orange, pad, width=2, border_radius=8)

        lab = body_font.render(label, True, theme.text_primary if sel else theme.text_dim)
        surface.blit(lab, (x, y))
        y += body_ls + 2
        val_color = (
            theme.accent_orange
            if row_id in (SettingsRow.SFX, SettingsRow.AMBIENT, SettingsRow.CHICHA_REACTIVE)
            else theme.text_dim
        )
        val = small.render(value, True, val_color)
        surface.blit(val, (x + 22, y))
        y += small_ls + row_gap

    y += 6
    for part in wrap_text_to_width(
        small,
        f"Diagnostics · {info.controller_summary[:72]}",
        max_text_w,
    ):
        if y > panel.bottom - 10:
            break
        surface.blit(small.render(part, True, theme.text_dim), (x, y))
        y += small.get_linesize() + 2

    y += 4
    meta = (
        f"{info.resolution} · {'fullscreen' if info.fullscreen else 'windowed'} · "
        f"{info.fps_target} FPS · audio {'ready' if info.audio_ready else 'off'}"
    )
    for part in wrap_text_to_width(small, meta, max_text_w):
        if y > panel.bottom - 10:
            break
        surface.blit(small.render(part, True, theme.text_dim), (x, y))
        y += small.get_linesize() + 2
