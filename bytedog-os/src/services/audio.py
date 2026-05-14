"""Pygame mixer–based UI audio: files grouped under assets/sounds by action."""

from __future__ import annotations

from pathlib import Path
from typing import Final, Optional

import pygame

# Relative to assets/sounds/ — ordered: preferred layout first, then legacy flat names.
_NAVIGATION_MENU_CHANGE: Final[tuple[str, ...]] = (
    "navigation/menu-change.mp3",
    "navigation/menu-change.wav",
    "menu-change.mp3",
    "select.wav",
    "menu_move.wav",
)
_SYSTEM_STARTUP: Final[tuple[str, ...]] = (
    "system/startup.mp3",
    "system/startup.wav",
    "startup.mp3",
    "startup.wav",
)
_SYSTEM_SHUTDOWN: Final[tuple[str, ...]] = (
    "system/shutdown.mp3",
    "system/shutdown.wav",
    "actions/shutdown.mp3",
    "actions/shutdown.wav",
    "shutdown.mp3",
    "shutdown.wav",
)
_ACTION_CONFIRM: Final[tuple[str, ...]] = (
    "actions/selected-item.mp3",
    "actions/selected-item.wav",
    "selected-item.mp3",
    "selected-item.wav",
    "actions/confirm.wav",
    "actions/confirm.mp3",
    "confirm.wav",
    "confirm.mp3",
)
_ACTION_BACK: Final[tuple[str, ...]] = (
    "actions/back.wav",
    "actions/back.mp3",
    "back.wav",
    "back.mp3",
)


class AudioService:
    def __init__(self, sounds_dir: Path) -> None:
        self._sounds_dir = sounds_dir
        self._navigation_menu_change: Optional[pygame.mixer.Sound] = None
        self._action_confirm: Optional[pygame.mixer.Sound] = None
        self._action_back: Optional[pygame.mixer.Sound] = None
        self._system_startup: Optional[pygame.mixer.Sound] = None
        self._system_shutdown: Optional[pygame.mixer.Sound] = None

    def initialize(self) -> None:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        except pygame.error:
            return
        self._load_optional_sounds()

    @property
    def mixer_ready(self) -> bool:
        try:
            return bool(pygame.mixer.get_init())
        except pygame.error:
            return False

    def shutdown(self) -> None:
        try:
            pygame.mixer.quit()
        except pygame.error:
            pass

    def _try_load(self, relative_path: str) -> Optional[pygame.mixer.Sound]:
        path = self._sounds_dir / relative_path
        if not path.is_file():
            return None
        try:
            return pygame.mixer.Sound(str(path))
        except (pygame.error, OSError, ValueError):
            return None

    def _load_first(self, candidates: tuple[str, ...]) -> Optional[pygame.mixer.Sound]:
        for rel in candidates:
            sound = self._try_load(rel)
            if sound is not None:
                return sound
        return None

    def _load_optional_sounds(self) -> None:
        self._navigation_menu_change = self._load_first(_NAVIGATION_MENU_CHANGE)
        self._system_startup = self._load_first(_SYSTEM_STARTUP)
        self._system_shutdown = self._load_first(_SYSTEM_SHUTDOWN)
        self._action_confirm = self._load_first(_ACTION_CONFIRM)
        self._action_back = self._load_first(_ACTION_BACK)

    def _play(self, sound: Optional[pygame.mixer.Sound]) -> None:
        if sound is None:
            return
        try:
            sound.play()
        except pygame.error:
            pass

    def play_menu_move(self) -> None:
        """Highlight moved to another menu item (navigation)."""
        self._play(self._navigation_menu_change)

    def play_confirm(self) -> None:
        """Menu item activated (Enter / Cross) or overlay confirm."""
        self._play(self._action_confirm)

    def play_back(self) -> None:
        self._play(self._action_back)

    def play_startup(self) -> None:
        self._play(self._system_startup)

    def play_shutdown(self) -> int:
        """
        Play shutdown sound. Returns a suggested hold time in ms (from clip length),
        or 0 if no clip; caller should still enforce a minimum on-screen time.
        """
        if self._system_shutdown is None:
            return 0
        try:
            self._system_shutdown.play()
            ms = int(self._system_shutdown.get_length() * 1000)
            return max(ms, 400)
        except pygame.error:
            return 0
