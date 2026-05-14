"""Keyboard → semantic actions (WASD / arrows / Enter / Esc / F3)."""

from __future__ import annotations

from collections.abc import Iterator

import pygame

from src.services.input.actions import InputAction


class KeyboardAdapter:
    @staticmethod
    def actions_from_keydown(key: int) -> Iterator[InputAction]:
        if key in (pygame.K_UP, pygame.K_w):
            yield InputAction.MENU_UP
        elif key in (pygame.K_DOWN, pygame.K_s):
            yield InputAction.MENU_DOWN
        elif key in (pygame.K_LEFT, pygame.K_a):
            yield InputAction.MENU_LEFT
        elif key in (pygame.K_RIGHT, pygame.K_d):
            yield InputAction.MENU_RIGHT
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            yield InputAction.CONFIRM
        elif key == pygame.K_ESCAPE:
            yield InputAction.BACK
        elif key == pygame.K_F3:
            yield InputAction.TOGGLE_DEBUG
