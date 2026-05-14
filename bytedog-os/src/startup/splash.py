"""Boot splash: health summary, logo reveal, Chicha boot clip, synced startup chime."""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING, Optional

import pygame

from src.startup.health_checks import HealthResult
from src.ui.theme import Theme, load_ui_font

if TYPE_CHECKING:
    from src.pet.animations import ChichaAnimator
    from src.pet.state import PetState
    from src.services.audio import AudioService


def run_startup_splash(
    surface: pygame.Surface,
    theme: Theme,
    results: list[HealthResult],
    *,
    minimum_ms: float,
    fail_on_critical: bool,
    clock: pygame.time.Clock,
    target_fps: int,
    audio: Optional["AudioService"] = None,
    chicha_animator: Optional["ChichaAnimator"] = None,
    chicha_pet: Optional["PetState"] = None,
    chicha_fast_scale: bool = False,
    sync_startup_sound_ms: float = 520.0,
) -> bool:
    """
    Draw splash until minimum_ms + exit fade. Return False on quit / critical block.
    Optionally updates/draws Chicha in ``booting`` state and fires startup audio once
    after ``sync_startup_sound_ms`` (aligned with logo reveal).
    """
    start = time.monotonic()
    last = start
    has_fail = any(r.status == "FAIL" for r in results)
    blocked = has_fail and fail_on_critical
    out_fade_ms = 520.0
    total_ok_ms = minimum_ms + (0.0 if blocked else out_fade_ms)

    title_font = load_ui_font(44)
    sub_font = load_ui_font(24)
    row_font = load_ui_font(18)
    small_font = load_ui_font(15)
    brand_font = load_ui_font(20)

    startup_sound_fired = False
    sw, sh = surface.get_size()
    chicha_rect = pygame.Rect(max(24, sw - 168), 92, 140, 104)

    while True:
        now = time.monotonic()
        elapsed_ms = (now - start) * 1000.0
        dt_ms = max(0.0, (now - last) * 1000.0)
        last = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if blocked and event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False

        if (
            audio is not None
            and not startup_sound_fired
            and not blocked
            and elapsed_ms >= sync_startup_sound_ms
        ):
            audio.play_startup()
            startup_sound_fired = True

        if chicha_animator is not None and chicha_pet is not None:
            chicha_animator.update(dt_ms, chicha_pet)

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
            chicha_animator=chicha_animator,
            chicha_rect=chicha_rect,
            chicha_fast_scale=chicha_fast_scale,
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
    """Fade in from black, hold clear, ease out to launcher."""
    if blocked:
        return 0
    fade_in_ms = 560.0
    fade_out_ms = 520.0
    if elapsed_ms < fade_in_ms:
        t = elapsed_ms / fade_in_ms
        ease = t * t * (3.0 - 2.0 * t)
        return int(250 * (1.0 - ease))
    fo_start = minimum_ms - fade_out_ms
    if fo_start < fade_in_ms:
        fo_start = fade_in_ms
    if elapsed_ms > fo_start:
        u = (elapsed_ms - fo_start) / fade_out_ms
        ease = u * u * (3.0 - 2.0 * min(1.0, max(0.0, u)))
        return int(255 * ease)
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
    *,
    chicha_animator: Optional["ChichaAnimator"] = None,
    chicha_rect: pygame.Rect | None = None,
    chicha_fast_scale: bool = False,
) -> None:
    sw, sh = surface.get_size()
    surface.fill(theme.bg)

    drift = int(4.0 * math.sin(elapsed_ms / 1400.0))
    for x in range(-6 + drift, sw + 6, 6):
        pygame.draw.line(surface, (18, 14, 34), (x, 0), (x, sh), 1)

    reveal = min(1.0, elapsed_ms / 520.0)
    ease = reveal * reveal * (3.0 - 2.0 * reveal)
    title_y = 24 + int((1.0 - ease) * 22)

    title_s = title_font.render("ByteDog OS", True, theme.text_primary)
    glow_s = title_font.render("ByteDog OS", True, theme.accent_purple)
    surface.blit(glow_s, (28, title_y + 2))
    surface.blit(title_s, (26, title_y))

    tag = brand_font.render("handheld launcher", True, theme.accent_orange)
    tag_x = 26 + int((1.0 - ease) * 40)
    surface.blit(tag, (tag_x, title_y + 50))

    sub = sub_font.render("Initializing Chicha…", True, theme.accent_purple)
    surface.blit(sub, (26, title_y + 86))

    y = title_y + 124
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
    angle = (elapsed_ms / 240.0) * math.tau
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

    if chicha_animator is not None and chicha_rect is not None:
        chicha_animator.draw(surface, chicha_rect, fast_scale=chicha_fast_scale, now_s=elapsed_ms * 0.001)

    if blocked:
        y += 32
        warn = small_font.render("Critical failure — press Escape to exit", True, theme.danger)
        surface.blit(warn, (26, y))

    cover = _splash_cover_alpha(elapsed_ms, minimum_ms, blocked)
    if cover > 0:
        veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
        veil.fill((6, 4, 14, min(250, cover)))
        surface.blit(veil, (0, 0))
