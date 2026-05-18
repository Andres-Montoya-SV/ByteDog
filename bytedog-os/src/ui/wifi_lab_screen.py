"""Cyberdeck WiFi Lab screen (university lab education)."""

from __future__ import annotations

import math
import time

import pygame

from src.cyber import reports as reports_mod
from src.cyber.wifi_lab import WifiLabController, WifiLabPanel
from src.ui.screens import wrap_text_to_width
from src.ui.theme import Theme, load_sans_ui_font, load_ui_font
from src.ui.widgets import draw_panel, draw_progress_bar

_CHICHA_RESERVE_W = 132
_PANEL_PAD = 20
_FOOTER_H = 58

_WPA_GUIDE_LINES: tuple[str, ...] = (
    "WPA/WPA2 uses a 4-way handshake between client and AP.",
    "The PSK is never sent over the air — only key material derived from it.",
    "Capture traffic only on networks you are authorized to test in class.",
    "Deauth demos explain 802.11 management frames on isolated lab VLANs.",
    "On Raspberry Pi: sudo apt install aircrack-ng, then airmon-ng start wlan0.",
    "On Mac (dev): scans are real; attacks simulate until you use the Pi lab.",
)


def _panel_subtitle(panel: WifiLabPanel) -> str:
    return {
        WifiLabPanel.HOME: "Main menu",
        WifiLabPanel.LAB: "Lab Mode · passive scan (read-only)",
        WifiLabPanel.RED_WARNING: "Red Team · safety briefing",
        WifiLabPanel.RED_TEAM: "Red Team · live scan & offensive lab",
        WifiLabPanel.REPORTS: "Saved lab reports (JSON logs)",
        WifiLabPanel.GUIDE: "WPA / WPA2 educational guide",
    }.get(panel, "")


def draw_wifi_lab_screen(
    surface: pygame.Surface,
    theme: Theme,
    lab: WifiLabController,
    *,
    anim_phase_s: float,
    content_bottom_y: int | None = None,
    chicha_rect: pygame.Rect | None = None,
) -> pygame.Rect:
    """Draw the lab panel; returns the Chicha draw rect (reserved top-right)."""
    sw, sh = surface.get_size()
    margin = max(16, min(sw, sh) // 30)
    title_font = load_ui_font(28)
    body_font = load_ui_font(19)
    small = load_ui_font(15)
    hint_font = load_sans_ui_font(13)

    bottom_limit = content_bottom_y if content_bottom_y is not None else sh - margin
    panel_h = max(120, bottom_limit - margin)
    panel = pygame.Rect(margin, margin, sw - 2 * margin, panel_h)
    draw_panel(surface, theme, panel)

    reserve = _CHICHA_RESERVE_W + 8
    content_right = panel.right - reserve
    x = panel.x + _PANEL_PAD
    y = panel.y + 14
    max_w = max(120, content_right - x)
    pulse = 0.5 + 0.5 * math.sin(anim_phase_s * math.tau * 0.85)

    surface.blit(title_font.render("WiFi Lab", True, theme.text_primary), (x, y))
    y += title_font.get_linesize() + 2
    surface.blit(small.render(_panel_subtitle(lab.panel), True, theme.accent_purple), (x, y))
    y += small.get_linesize() + 6

    mood_txt = f"Chicha · {lab.mood.value}"
    if lab.scanning:
        mood_txt += " · scanning…"
    surface.blit(small.render(mood_txt, True, theme.accent_orange), (x, y))
    y += small.get_linesize() + 6

    for line in lab.ui_banner_lines():
        col = theme.accent_orange if "simulate" in line.lower() or "blocked" in line.lower() else theme.text_dim
        if "Real AP" in line or "Live attacks" in line:
            col = theme.accent_purple
        for part in wrap_text_to_width(hint_font, line, max_w):
            surface.blit(hint_font.render(part, True, col), (x, y))
            y += hint_font.get_linesize() + 1
    y += 8

    footer_top = panel.bottom - _FOOTER_H
    body_bottom = footer_top - 10

    if lab.panel is WifiLabPanel.HOME:
        _draw_home(surface, theme, lab, x, y, max_w, body_bottom, body_font, small, pulse)
    elif lab.panel is WifiLabPanel.LAB:
        _draw_lab_mode(surface, theme, lab, x, y, max_w, body_bottom, body_font, small, pulse)
    elif lab.panel is WifiLabPanel.RED_WARNING:
        _draw_red_warning(surface, theme, lab, x, y, max_w, body_bottom, body_font, small)
    elif lab.panel is WifiLabPanel.RED_TEAM:
        _draw_red_team(surface, theme, lab, x, y, max_w, body_bottom, body_font, small, pulse)
    elif lab.panel is WifiLabPanel.REPORTS:
        _draw_reports(surface, theme, lab, x, y, max_w, body_bottom, small)
    elif lab.panel is WifiLabPanel.GUIDE:
        _draw_guide(surface, theme, x, y, max_w, body_bottom, small)

    _draw_wifi_lab_footer(surface, theme, lab, panel, x, max_w, footer_top, hint_font, small)

    if chicha_rect is not None:
        return chicha_rect
    return pygame.Rect(
        panel.right - _CHICHA_RESERVE_W - 6,
        panel.y + 10,
        _CHICHA_RESERVE_W,
        min(108, panel.height // 3),
    )


def _draw_wifi_lab_footer(
    surface: pygame.Surface,
    theme: Theme,
    lab: WifiLabController,
    panel: pygame.Rect,
    x: int,
    max_w: int,
    footer_top: int,
    hint_font: pygame.font.Font,
    small: pygame.font.Font,
) -> None:
    foot = pygame.Rect(panel.x + 2, footer_top, panel.width - 4, panel.bottom - footer_top - 2)
    pygame.draw.rect(surface, theme.bg_panel, foot, border_radius=8)
    pygame.draw.line(surface, theme.border, (foot.x, foot.y), (foot.right, foot.y), 1)

    y = foot.y + 5
    if lab.status_message:
        for part in wrap_text_to_width(small, lab.status_message[:100], max_w):
            surface.blit(small.render(part, True, theme.accent_purple), (x, y))
            y += small.get_linesize()

    hint_y = foot.bottom - hint_font.get_linesize() - 5
    hints = {
        WifiLabPanel.HOME: "↑↓ menu · Enter open · Esc launcher",
        WifiLabPanel.LAB: "↑↓ row · Enter scan · Esc home",
        WifiLabPanel.RED_TEAM: "↑↓ action · Enter run · ←→ AP · Esc home",
        WifiLabPanel.REPORTS: "↑↓ log · Esc home",
        WifiLabPanel.RED_WARNING: "Enter confirm (×2) · Esc cancel",
        WifiLabPanel.GUIDE: "Esc home",
    }.get(lab.panel, "↑↓ · Enter · Esc")
    surface.blit(hint_font.render(hints, True, theme.text_dim), (x, hint_y))


def _sel_glow(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color: pygame.Color,
    pulse: float,
    alpha: int = 40,
) -> None:
    glow = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    glow.fill((color.r, color.g, color.b, int(alpha + 45 * pulse)))
    surface.blit(glow, rect.topleft)


def _draw_home(
    surface: pygame.Surface,
    theme: Theme,
    lab: WifiLabController,
    x: int,
    y: int,
    max_w: int,
    body_bottom: int,
    body_font: pygame.font.Font,
    small: pygame.font.Font,
    pulse: float,
) -> None:
    for i, label in enumerate(lab.home_items()):
        if y + body_font.get_linesize() > body_bottom:
            break
        sel = i == lab.home_index
        if sel:
            pad = pygame.Rect(x - 8, y - 3, max_w, body_font.get_linesize() + 8)
            _sel_glow(surface, pad, theme.accent_purple, pulse)
        surface.blit(
            body_font.render(label, True, theme.text_primary if sel else theme.text_dim),
            (x, y),
        )
        y += body_font.get_linesize() + 10


def _draw_lab_mode(
    surface: pygame.Surface,
    theme: Theme,
    lab: WifiLabController,
    x: int,
    y: int,
    max_w: int,
    body_bottom: int,
    body_font: pygame.font.Font,
    small: pygame.font.Font,
    pulse: float,
) -> None:
    scan_sel = lab.lab_focus_scan
    if scan_sel:
        pad = pygame.Rect(x - 8, y - 2, max_w, body_font.get_linesize() + 6)
        _sel_glow(surface, pad, theme.accent_orange, pulse)
    label = "[ Run passive scan ]" if not lab.scanning else "[ Scanning… ]"
    surface.blit(
        body_font.render(label, True, theme.accent_orange if scan_sel else theme.text_primary),
        (x, y),
    )
    y += body_font.get_linesize() + 8

    if lab.scanning:
        bar = pygame.Rect(x, y, min(240, max_w), 10)
        draw_progress_bar(surface, theme, bar, (time.monotonic() % 1.2) / 1.2, fill=theme.accent_purple)
        y += 18

    if lab.networks:
        hdr = small.render("SSID · BSSID · CH · RSSI · SRC", True, theme.text_dim)
        surface.blit(hdr, (x, y))
        y += small.get_linesize() + 4
        for i, net in enumerate(lab.networks[:6]):
            if y + small.get_linesize() > body_bottom:
                break
            sel = i == lab.lab_network_index and not lab.lab_focus_scan
            src_tag = "sim" if net.source == "simulation" else net.source[:4]
            bssid_show = f"{net.bssid[:17]}*" if net.synthetic_bssid else net.bssid[:18]
            line = f"{net.ssid[:12]:12} {bssid_show} ch{net.channel:>2} {net.rssi:>4} {src_tag}"
            if sel:
                pygame.draw.rect(
                    surface,
                    (*theme.accent_orange[:3], 30),
                    pygame.Rect(x - 4, y - 1, max_w, small.get_linesize() + 2),
                    border_radius=4,
                )
            surface.blit(small.render(line, True, theme.text_primary if sel else theme.text_dim), (x, y))
            y += small.get_linesize() + 3
    elif not lab.scanning:
        surface.blit(small.render("Press Enter on scan row to discover APs.", True, theme.text_dim), (x, y))


def _draw_red_warning(
    surface: pygame.Surface,
    theme: Theme,
    lab: WifiLabController,
    x: int,
    y: int,
    max_w: int,
    body_bottom: int,
    body_font: pygame.font.Font,
    small: pygame.font.Font,
) -> None:
    _ = body_bottom
    surface.blit(body_font.render("AUTHORIZED UNIVERSITY LAB ONLY", True, theme.danger), (x, y))
    y += body_font.get_linesize() + 10
    for line in (
        "Sends real 802.11 frames only on the Raspberry Pi with aircrack-ng.",
        "May disconnect clients from the lab AP — never use on public WiFi.",
        lab.attack_status_line(),
        "Confirm twice below to unlock Red Team actions.",
    ):
        for part in wrap_text_to_width(small, line, max_w):
            surface.blit(small.render(part, True, theme.text_primary), (x, y))
            y += small.get_linesize() + 3
    y += 8
    step = 2 if lab.red_confirm_hold else (1 if lab.red_warning_ack else 0)
    steps = (
        "Step 1/2 · Press Enter — I understand",
        "Step 2/2 · Press Enter again to continue",
        "Opening Red Team panel…",
    )
    surface.blit(small.render(steps[min(step, 2)], True, theme.accent_orange), (x, y))


def _draw_red_team(
    surface: pygame.Surface,
    theme: Theme,
    lab: WifiLabController,
    x: int,
    y: int,
    max_w: int,
    body_bottom: int,
    body_font: pygame.font.Font,
    small: pygame.font.Font,
    pulse: float,
) -> None:
    for i, label in enumerate(lab.red_team_actions()):
        if y + body_font.get_linesize() > body_bottom - 8:
            break
        sel = i == lab.red_action_index
        if sel:
            pad = pygame.Rect(x - 8, y - 2, max_w, body_font.get_linesize() + 6)
            _sel_glow(surface, pad, theme.danger, pulse, alpha=28)
        prefix = "▸ " if sel else "  "
        surface.blit(
            body_font.render(prefix + label, True, theme.text_primary if sel else theme.text_dim),
            (x, y),
        )
        y += body_font.get_linesize() + 6


def _draw_reports(
    surface: pygame.Surface,
    theme: Theme,
    lab: WifiLabController,
    x: int,
    y: int,
    max_w: int,
    body_bottom: int,
    small: pygame.font.Font,
) -> None:
    reps = lab.reports
    if not reps:
        surface.blit(small.render("No logs yet. Run Lab or Red Team scan.", True, theme.text_dim), (x, y))
        return

    list_bottom = y + int((body_bottom - y) * 0.42)
    for i, meta in enumerate(reps[:5]):
        if y + small.get_linesize() > list_bottom:
            break
        sel = i == lab.report_index
        kind = {"scan": "SCAN", "red_team": "RED", "log": "LOG"}.get(meta.kind, meta.kind.upper())
        line = f"{meta.created_iso}  {kind}  {meta.path.name}"
        for part in wrap_text_to_width(small, line, max_w):
            if sel:
                pygame.draw.rect(
                    surface,
                    (*theme.accent_purple[:3], 35),
                    pygame.Rect(x - 4, y - 1, max_w, small.get_linesize() + 2),
                    border_radius=4,
                )
            surface.blit(
                small.render(part, True, theme.text_primary if sel else theme.text_dim),
                (x, y),
            )
            y += small.get_linesize() + 1
        y += 3

    preview = pygame.Rect(x, list_bottom + 6, max_w, max(44, body_bottom - list_bottom - 8))
    pygame.draw.rect(surface, theme.bg_panel, preview, border_radius=8)
    pygame.draw.rect(surface, theme.border, preview, width=1, border_radius=8)
    py = preview.y + 8
    px = preview.x + 10
    pw = preview.width - 20
    idx = max(0, min(lab.report_index, len(reps) - 1))
    surface.blit(small.render("Report preview", True, theme.accent_purple), (px, py))
    py += small.get_linesize() + 4
    for part in reports_mod.report_preview_lines(reps[idx].path, max_lines=6):
        for wrapped in wrap_text_to_width(small, part, pw):
            if py > preview.bottom - 8:
                return
            surface.blit(small.render(wrapped, True, theme.text_dim), (px, py))
            py += small.get_linesize() + 2


def _draw_guide(
    surface: pygame.Surface,
    theme: Theme,
    x: int,
    y: int,
    max_w: int,
    body_bottom: int,
    small: pygame.font.Font,
) -> None:
    for line in _WPA_GUIDE_LINES:
        for part in wrap_text_to_width(small, line, max_w):
            if y > body_bottom:
                return
            surface.blit(small.render(part, True, theme.text_primary), (x, y))
            y += small.get_linesize() + 4
