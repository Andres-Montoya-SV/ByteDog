"""Main launcher chrome: card shell, top bar, icon menu, Chicha hero, flavor footer."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

import pygame

from src.pet.chicha_life import ChichaLifeState
from src.services.wifi import WifiStatus
from src.ui.menu import LauncherMenu, MenuAction
from src.ui.screens import wrap_text_to_width
from src.ui.theme import Theme, load_sans_ui_font


@dataclass(slots=True)
class HandheldMainLayout:
    outer_margin: int
    card: pygame.Rect
    top_bar: pygame.Rect
    content: pygame.Rect
    menu_area: pygame.Rect
    chicha_rect: pygame.Rect
    flavor: pygame.Rect
    icon_size: int
    row_height: int
    text_left_x: int


def compute_handheld_main_layout(sw: int, sh: int, num_menu_items: int) -> HandheldMainLayout:
    outer = max(12, min(sw, sh) // 36)
    card = pygame.Rect(outer, outer, sw - 2 * outer, sh - 2 * outer)
    top_h = max(34, min(44, sh // 11))
    flavor_h = max(38, min(48, sh // 10))
    pad = 10
    content_top = card.y + top_h + pad
    content_bottom = card.bottom - flavor_h - pad
    content = pygame.Rect(card.x + pad, content_top, card.w - 2 * pad, max(80, content_bottom - content_top))

    menu_w = max(200, min(int(content.w * 0.45), content.w - 140))
    menu_area = pygame.Rect(content.x, content.y, menu_w, content.h)
    chicha_rect = pygame.Rect(
        menu_area.right + 12,
        content.y,
        max(100, content.right - menu_area.right - 16),
        content.h,
    )

    icon_size = max(32, min(44, sh // 12))
    usable_h = content.h - 8
    row_height = max(52, min(76, usable_h // max(num_menu_items, 1)))

    text_left_x = menu_area.x + 8 + icon_size + 12
    top_bar = pygame.Rect(card.x + pad, card.y + 6, card.w - 2 * pad, top_h - 6)
    flavor = pygame.Rect(card.x + pad, content_bottom + 4, card.w - 2 * pad, flavor_h - 4)

    return HandheldMainLayout(
        outer_margin=outer,
        card=card,
        top_bar=top_bar,
        content=content,
        menu_area=menu_area,
        chicha_rect=chicha_rect,
        flavor=flavor,
        icon_size=icon_size,
        row_height=row_height,
        text_left_x=text_left_x,
    )


def _draw_wifi_glyphs(surface: pygame.Surface, cx: int, cy: int, strength: int, color: pygame.Color) -> None:
    strength = max(0, min(100, strength))
    for i, scale in enumerate((0.45, 0.7, 1.0)):
        arc_h = int(8 * scale)
        threshold = (i + 1) * 33
        c = color if strength >= threshold else pygame.Color(color.r // 3, color.g // 3, color.b // 3)
        rect = pygame.Rect(cx - 14 + i * 5, cy - arc_h, 10, arc_h + 2)
        pygame.draw.arc(surface, c, rect, 3.7, 5.9, 2)


def _draw_battery(surface: pygame.Surface, right_x: int, cy: int, pct: int | None, theme: Theme) -> int:
    """Draw battery glyph left of right_x; return new right_x for further widgets."""
    font = load_sans_ui_font(14, bold=False)
    label = f"{pct}%" if pct is not None else "—"
    bw, bh = 24, 11
    bx = right_x - bw - 4 - font.size(label)[0] - 6
    by = cy - bh // 2
    pygame.draw.rect(surface, theme.text_dim, pygame.Rect(bx, by, bw, bh), width=1, border_radius=2)
    pygame.draw.rect(surface, theme.text_dim, pygame.Rect(bx + bw, by + 3, 2, 5))
    fill_w = max(0, int((bw - 2) * ((pct or 0) / 100.0))) if pct is not None else 0
    if fill_w > 0:
        low = (pct or 0) <= 15
        fill_color = theme.accent_orange if low else pygame.Color(72, 200, 120)
        pygame.draw.rect(surface, fill_color, pygame.Rect(bx + 1, by + 1, fill_w, bh - 2), border_radius=1)
    surface.blit(font.render(label, True, theme.text_dim), (bx + bw + 6, cy - font.get_height() // 2))
    return bx - 8


def _draw_paw_mark(surface: pygame.Surface, cx: int, cy: int, color: pygame.Color) -> None:
    for ox, oy, r in ((-5, -2, 3), (5, -2, 3), (-7, 4, 2), (0, 5, 3), (7, 4, 2)):
        pygame.draw.circle(surface, color, (cx + ox, cy + oy), r)


def draw_handheld_launcher(
    surface: pygame.Surface,
    theme: Theme,
    layout: HandheldMainLayout,
    menu: LauncherMenu,
    menu_icons: Mapping[MenuAction, pygame.Surface],
    wifi: WifiStatus,
    battery_pct: int | None,
    *,
    selection_pulse_s: float = 0.0,
    intro_slide_px: int = 0,
    chicha_life: ChichaLifeState = ChichaLifeState.IDLE,
) -> None:
    slide = max(-24, min(48, intro_slide_px))

    pygame.draw.rect(surface, theme.bg_panel, layout.card, border_radius=14)
    pygame.draw.rect(surface, theme.border, layout.card, width=2, border_radius=14)

    title_font = load_sans_ui_font(max(16, layout.top_bar.h - 10))
    menu_title = title_font.render("MENÚ PRINCIPAL", True, theme.accent_purple)
    surface.blit(menu_title, (layout.top_bar.x + slide, layout.top_bar.centery - menu_title.get_height() // 2))

    time_font = load_sans_ui_font(max(15, layout.top_bar.h - 12), bold=True)
    clock_s = datetime.now().strftime("%H:%M")
    clock_img = time_font.render(clock_s, True, theme.text_primary)
    right = layout.top_bar.right - 8
    surface.blit(clock_img, (right - clock_img.get_width(), layout.top_bar.centery - clock_img.get_height() // 2))
    right -= clock_img.get_width() + 12
    right = _draw_battery(surface, right, layout.top_bar.centery, battery_pct, theme)

    wifi_center_x = right - 4
    _draw_wifi_glyphs(
        surface,
        wifi_center_x,
        layout.top_bar.centery,
        wifi.strength_percent,
        theme.accent_purple,
    )

    neon = theme.accent_purple
    title_sz = max(17, min(22, layout.row_height // 3))
    sub_sz = max(12, title_sz - 5)
    font_title = load_sans_ui_font(title_sz, bold=True)
    font_sub = load_sans_ui_font(sub_sz, bold=False)

    for i, item in enumerate(menu.items):
        y = layout.menu_area.y + i * layout.row_height + slide
        x0 = layout.menu_area.x + slide
        if y + layout.row_height > layout.menu_area.bottom:
            break
        row_rect = pygame.Rect(
            x0,
            y,
            layout.menu_area.w,
            min(layout.row_height, layout.menu_area.bottom - y),
        )
        selected = i == menu.selected_index
        if selected:
            pulse = 0.5 + 0.5 * math.sin(selection_pulse_s * math.tau * 0.85)
            pygame.draw.rect(surface, theme.selection_bg, row_rect, border_radius=10)
            pygame.draw.rect(surface, theme.accent_orange, row_rect, width=2, border_radius=10)
            bar_h = max(12, row_rect.h - 14)
            bar_w = 3 + int(2 * pulse)
            pygame.draw.rect(
                surface,
                neon,
                pygame.Rect(row_rect.x + 4, row_rect.centery - bar_h // 2, bar_w, bar_h),
                border_radius=2,
            )

        icon = menu_icons.get(item.action)
        if icon is not None:
            iw, ih = icon.get_size()
            ix = x0 + 8 + (layout.icon_size - iw) // 2
            iy = row_rect.centery - ih // 2
            surface.blit(icon, (ix, iy))

        title_color = theme.text_primary if selected else theme.text_dim
        sub_color = theme.text_dim if selected else pygame.Color(
            max(0, theme.text_dim.r - 15),
            max(0, theme.text_dim.g - 15),
            max(0, theme.text_dim.b - 15),
        )
        label_upper = item.label.upper()
        t1 = font_title.render(label_upper, True, title_color)
        surface.blit(t1, (layout.text_left_x + slide, row_rect.y + 6))
        t2 = font_sub.render(item.subtitle, True, sub_color)
        max_sub_w = layout.menu_area.right - layout.text_left_x - 8
        if t2.get_width() > max_sub_w:
            sub_lines = _ellipsis_lines(font_sub, item.subtitle, max_sub_w)
            sy = row_rect.y + 6 + t1.get_height() + 2
            for sl in sub_lines[:2]:
                s2 = font_sub.render(sl, True, sub_color)
                surface.blit(s2, (layout.text_left_x + slide, sy))
                sy += font_sub.get_linesize()
        else:
            surface.blit(t2, (layout.text_left_x + slide, row_rect.y + 6 + t1.get_height() + 2))

        if i < len(menu.items) - 1:
            sep_y = row_rect.bottom - 1
            pygame.draw.line(
                surface,
                pygame.Color(35, 30, 55),
                (layout.menu_area.x + slide + 6, sep_y),
                (layout.menu_area.right - 6 + slide, sep_y),
                1,
            )

    # Chicha pose is drawn in the hero rect by the app (no separate deck PNG underneath).

    pygame.draw.rect(surface, theme.bg_panel, layout.flavor, border_radius=8)
    pygame.draw.rect(surface, theme.border, layout.flavor, width=1, border_radius=8)
    flavor_font = load_sans_ui_font(max(14, layout.flavor.h // 2), bold=False)
    msg, heart_txt = _flavor_for_life(chicha_life)
    heart = flavor_font.render(heart_txt, True, theme.accent_purple)
    fimg = flavor_font.render(msg, True, theme.text_dim)
    fx = layout.flavor.x + 14
    cy = layout.flavor.centery
    _draw_paw_mark(surface, fx + 10, cy, theme.accent_purple)
    surface.blit(fimg, (fx + 26, cy - fimg.get_height() // 2))
    surface.blit(heart, (fx + 26 + fimg.get_width(), cy - heart.get_height() // 2))


def _flavor_for_life(state: ChichaLifeState) -> tuple[str, str]:
    hearts = {
        ChichaLifeState.IDLE: " ♥",
        ChichaLifeState.HAPPY: " ✦",
        ChichaLifeState.SLEEPY: " zZ",
        ChichaLifeState.CURIOUS: " ?",
        ChichaLifeState.ALERT: " !",
        ChichaLifeState.LOW_BATTERY: " …",
        ChichaLifeState.GAMING: " ▶",
        ChichaLifeState.BOOTING: " ◎",
    }
    lines = {
        ChichaLifeState.IDLE: "Chicha te está esperando",
        ChichaLifeState.HAPPY: "Chicha se alegra contigo",
        ChichaLifeState.SLEEPY: "Chicha sueña contigo el sistema",
        ChichaLifeState.CURIOUS: "Chicha olfatea el menú",
        ChichaLifeState.ALERT: "Chicha está atenta",
        ChichaLifeState.LOW_BATTERY: "Chicha nota poca energía",
        ChichaLifeState.GAMING: "Chicha lista para jugar",
        ChichaLifeState.BOOTING: "Chicha arranca el deck",
    }
    return lines.get(state, lines[ChichaLifeState.IDLE]), hearts.get(state, " ♥")


def _ellipsis_lines(font: pygame.font.Font, text: str, max_w: int) -> list[str]:
    lines = wrap_text_to_width(font, text, max_w)
    return lines if lines else [text[:20] + "…"]
