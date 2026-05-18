"""In-app terminal screen (embedded shell output + input)."""

from __future__ import annotations

import pygame

from src.services.terminal_shell import EmbeddedTerminal
from src.ui.theme import Theme, load_sans_ui_font, load_ui_font
from src.ui.widgets import draw_panel


def draw_terminal_screen(
    surface: pygame.Surface,
    theme: Theme,
    term: EmbeddedTerminal,
    *,
    cursor_phase_s: float,
    content_bottom_y: int | None = None,
) -> pygame.Rect:
    sw, sh = surface.get_size()
    margin = max(16, min(sw, sh) // 30)
    font = load_ui_font(15)
    title_font = load_ui_font(26)
    hint_font = load_sans_ui_font(13)

    bottom_limit = content_bottom_y if content_bottom_y is not None else sh - margin
    panel_h = max(120, bottom_limit - margin)
    panel = pygame.Rect(margin, margin, sw - 2 * margin, panel_h)
    draw_panel(surface, theme, panel)

    pad = 14
    header_h = title_font.get_linesize() + hint_font.get_linesize() + 20
    footer_h = 28
    inner = pygame.Rect(
        panel.x + pad,
        panel.y + pad,
        panel.width - 2 * pad,
        panel.height - 2 * pad,
    )
    term_rect = pygame.Rect(
        inner.x,
        inner.y + header_h,
        inner.w,
        max(40, inner.h - header_h - footer_h),
    )

    x = inner.x
    y = inner.y
    surface.blit(title_font.render("Terminal", True, theme.text_primary), (x, y))
    y += title_font.get_linesize() + 2
    status = f"{term.shell_name} · {term.cwd.name}/ · {'live' if term.alive else 'stopped'}"
    surface.blit(hint_font.render(status, True, theme.accent_purple), (x, y))

    pygame.draw.rect(surface, (12, 10, 22), term_rect, border_radius=8)
    pygame.draw.rect(surface, theme.border, term_rect, width=1, border_radius=8)

    line_h = font.get_linesize()
    max_lines = max(1, term_rect.height // line_h)
    cols = max(20, term_rect.width // max(8, font.size("M")[0]))
    term.resize(cols, max_lines)

    ty = term_rect.y + 6
    visible = term.visible_text(max_lines, wrap_cols=cols)
    prev_clip = surface.get_clip()
    surface.set_clip(term_rect)
    for idx, line in enumerate(visible):
        if ty + line_h > term_rect.bottom - 4:
            break
        is_prompt = idx == len(visible) - 1 and line.rstrip().endswith(("%", "#", "$"))
        color = theme.accent_orange if is_prompt else theme.text_primary
        surface.blit(font.render(line, True, color), (term_rect.x + 8, ty))
        ty += line_h
    surface.set_clip(prev_clip)

    foot_y = panel.bottom - footer_h
    hints = "Type here · Enter run · Esc exit · PgUp/PgDn scroll"
    if term.scroll_back_lines > 0:
        hints += f" · scrollback −{term.scroll_back_lines}"
    surface.blit(hint_font.render(hints, True, theme.text_dim), (x, foot_y))

    return term_rect
