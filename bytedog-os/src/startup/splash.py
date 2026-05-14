"""Boot splash: health summary, Chicha init line, loader, fades (Pi-friendly)."""

from __future__ import annotations

import math
import time

import pygame

from src.startup.health_checks import HealthResult
from src.ui.theme import Theme, load_ui_font


def run_startup_splash(
    surface: pygame.Surface,
    theme: Theme,
    results: list[HealthResult],
    *,
    minimum_ms: float,
    fail_on_critical: bool,
    clock: pygame.time.Clock,
    target_fps: int,
) -> bool:
    """
    Draw splash until minimum_ms + exit fade. Return False on quit / critical block.
    """
    start = time.monotonic()
    has_fail = any(r.status == "FAIL" for r in results)
    blocked = has_fail and fail_on_critical
    out_fade_ms = 380.0
    total_ok_ms = minimum_ms + (0.0 if blocked else out_fade_ms)

    title_font = load_ui_font(44)
    sub_font = load_ui_font(24)
    row_font = load_ui_font(18)
    small_font = load_ui_font(15)
    brand_font = load_ui_font(20)

    while True:
        elapsed_ms = (time.monotonic() - start) * 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if blocked and event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False

        _draw_splash_frame(
            surface,
            theme,
            results,
            elapsed_ms,
            minimum_ms,
            blocked,
            total_ok_ms,
            title_font,
            sub_font,
            row_font,
            small_font,
            brand_font,
        )
        pygame.display.flip()
        clock.tick(target_fps)

        if blocked:
            if elapsed_ms >= minimum_ms:
                continue
        else:
            if elapsed_ms >= total_ok_ms:
                return True


def _splash_cover_alpha(elapsed_ms: float, minimum_ms: float, blocked: bool) -> int:
    """Vignette fade in at boot, fade out before handing off to launcher."""
    if blocked:
        return 0
    fade_in_ms = 480.0
    fade_out_ms = 380.0
    if elapsed_ms < fade_in_ms:
        return int(245 * (1.0 - elapsed_ms / fade_in_ms))
    fo_start = minimum_ms - fade_out_ms
    if fo_start < fade_in_ms:
        fo_start = fade_in_ms
    if elapsed_ms > fo_start:
        u = (elapsed_ms - fo_start) / fade_out_ms
        return int(245 * min(1.0, max(0.0, u)))
    return 0


def _draw_splash_frame(
    surface: pygame.Surface,
    theme: Theme,
    results: list[HealthResult],
    elapsed_ms: float,
    minimum_ms: float,
    blocked: bool,
    total_ok_ms: float,
    title_font: pygame.font.Font,
    sub_font: pygame.font.Font,
    row_font: pygame.font.Font,
    small_font: pygame.font.Font,
    brand_font: pygame.font.Font,
) -> None:
    sw, sh = surface.get_size()
    surface.fill(theme.bg)

    # Subtle vertical scan bands
    for x in range(0, sw, 6):
        pygame.draw.line(surface, (18, 14, 34), (x, 0), (x, sh), 1)

    glow = title_font.render("ByteDog OS", True, theme.accent_purple)
    title = title_font.render("ByteDog OS", True, theme.text_primary)
    surface.blit(glow, (28, 26))
    surface.blit(title, (26, 24))

    tag = brand_font.render("handheld launcher", True, theme.accent_orange)
    surface.blit(tag, (26, 74))

    sub = sub_font.render("Initializing Chicha…", True, theme.accent_purple)
    surface.blit(sub, (26, 108))

    y = 148
    for r in results:
        color = theme.text_primary
        if r.status == "WARN":
            color = theme.accent_orange
        elif r.status == "FAIL":
            color = theme.danger
        line = f"[{r.status:4}] {r.name}: {r.message}"
        surf = row_font.render(line[:96], True, color)
        surface.blit(surf, (26, y))
        y += row_font.get_linesize() + 4

    y += 10
    cx, cy = 56, y + 28
    angle = (elapsed_ms / 220.0) * math.tau
    pygame.draw.circle(surface, theme.border, (cx, cy), 22, width=2)
    arc_rect = pygame.Rect(cx - 18, cy - 18, 36, 36)
    pygame.draw.arc(surface, theme.accent_orange, arc_rect, angle, angle + math.pi * 1.25, width=4)

    pct = 100.0 * min(1.0, elapsed_ms / max(minimum_ms, 1.0))
    if not blocked:
        pct = min(100.0, 100.0 * min(1.0, elapsed_ms / max(total_ok_ms, 1.0)))
    prog = small_font.render(f"boot {pct:.0f}%", True, theme.text_dim)
    surface.blit(prog, (92, y + 12))

    y += 56
    eta = max(0.0, (minimum_ms - elapsed_ms) / 1000.0)
    hint = small_font.render(
        f"minimum {minimum_ms / 1000:.1f}s  ·  {eta:.1f}s left",
        True,
        theme.text_dim,
    )
    surface.blit(hint, (26, y))

    if blocked:
        y += 32
        warn = small_font.render("Critical failure — press Escape to exit", True, theme.danger)
        surface.blit(warn, (26, y))

    cover = _splash_cover_alpha(elapsed_ms, minimum_ms, blocked)
    if cover > 0:
        veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
        veil.fill((6, 4, 14, min(250, cover)))
        surface.blit(veil, (0, 0))
