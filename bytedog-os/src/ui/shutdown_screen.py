"""Full-screen shutdown farewell (handheld / cyberpunk)."""

from __future__ import annotations

import time

import pygame

from src.ui.theme import Theme, load_sans_ui_font


def draw_shutdown_screen(
    surface: pygame.Surface,
    theme: Theme,
    *,
    started_monotonic: float,
) -> None:
    sw, sh = surface.get_size()
    surface.fill(theme.bg)

    elapsed_ms = (time.monotonic() - started_monotonic) * 1000.0
    phase = int(elapsed_ms / 380) % 4
    dots = "." * phase + " " * (3 - phase)

    title_f = load_sans_ui_font(max(36, min(48, sw // 16)), bold=True)
    main_f = load_sans_ui_font(max(20, min(28, sw // 28)), bold=True)
    sub_f = load_sans_ui_font(max(15, min(20, sw // 40)), bold=False)

    title = title_f.render("ByteDog OS", True, theme.text_primary)
    glow = title_f.render("ByteDog OS", True, theme.accent_purple)
    line1 = main_f.render(f"Apagando sistema{dots}", True, theme.accent_purple)
    line2 = sub_f.render("Gracias por jugar con Chicha", True, theme.text_dim)
    hint = sub_f.render("Hasta pronto", True, theme.text_dim)

    cx, cy = sw // 2, sh // 2
    surface.blit(glow, (cx - title.get_width() // 2 + 2, cy - 88 + 2))
    surface.blit(title, (cx - title.get_width() // 2, cy - 90))
    surface.blit(line1, (cx - line1.get_width() // 2, cy - 18))
    surface.blit(line2, (cx - line2.get_width() // 2, cy + 22))
    surface.blit(hint, (cx - hint.get_width() // 2, cy + 52))

    bar_w = min(420, sw - 80)
    progress = min(1.0, elapsed_ms / 4000.0)
    bx = cx - bar_w // 2
    by = cy + 96
    pygame.draw.rect(surface, theme.bg_panel, pygame.Rect(bx, by, bar_w, 8), border_radius=4)
    pygame.draw.rect(surface, theme.border, pygame.Rect(bx, by, bar_w, 8), width=1, border_radius=4)
    if progress > 0:
        pygame.draw.rect(
            surface,
            theme.accent_purple,
            pygame.Rect(bx + 2, by + 2, max(0, int((bar_w - 4) * progress)), 4),
            border_radius=2,
        )
