"""Pygame mixer UI audio: preload, low latency, volume, graceful missing files."""

from __future__ import annotations

from pathlib import Path
from typing import Final, Optional

import pygame

# Relative to assets/sounds/ — preferred first.
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
_SYSTEM_WARNING: Final[tuple[str, ...]] = (
    "system/warning.mp3",
    "system/warning.wav",
    "actions/warning.wav",
    "actions/warning.mp3",
)
_CHICHA_ACK: Final[tuple[str, ...]] = (
    "chicha/ack.wav",
    "chicha/ack.mp3",
    "chicha/yip.wav",
    "actions/chicha.wav",
)
_AMBIENT_MENU: Final[tuple[str, ...]] = (
    "ambient/menu-hum.wav",
    "ambient/menu-hum.mp3",
    "ambient/menu_loop.wav",
)


class AudioService:
    def __init__(self, sounds_dir: Path) -> None:
        self._sounds_dir = sounds_dir
        self._navigation_menu_change: Optional[pygame.mixer.Sound] = None
        self._action_confirm: Optional[pygame.mixer.Sound] = None
        self._action_back: Optional[pygame.mixer.Sound] = None
        self._system_startup: Optional[pygame.mixer.Sound] = None
        self._system_shutdown: Optional[pygame.mixer.Sound] = None
        self._system_warning: Optional[pygame.mixer.Sound] = None
        self._chicha_ack: Optional[pygame.mixer.Sound] = None
        self._ambient_menu: Optional[pygame.mixer.Sound] = None
        self._ambient_channel: Optional[pygame.mixer.Channel] = None
        self._master_volume = 1.0
        self._sfx_enabled = True

    def initialize(self) -> None:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=256)
        except pygame.error:
            return
        self._load_optional_sounds()
        self._apply_loaded_volumes()

    @property
    def mixer_ready(self) -> bool:
        try:
            return bool(pygame.mixer.get_init())
        except pygame.error:
            return False

    def shutdown(self) -> None:
        self.stop_ambient_menu()
        try:
            pygame.mixer.quit()
        except pygame.error:
            pass

    def set_master_volume(self, v: float) -> None:
        self._master_volume = max(0.0, min(1.0, float(v)))
        self._apply_loaded_volumes()

    def set_sfx_enabled(self, enabled: bool) -> None:
        self._sfx_enabled = bool(enabled)

    def _apply_loaded_volumes(self) -> None:
        m = self._master_volume
        for s in (
            self._navigation_menu_change,
            self._action_confirm,
            self._action_back,
            self._system_startup,
            self._system_shutdown,
            self._system_warning,
            self._chicha_ack,
        ):
            if s is not None:
                try:
                    s.set_volume(m)
                except pygame.error:
                    pass
        if self._ambient_menu is not None:
            try:
                self._ambient_menu.set_volume(m * 0.22)
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
        self._system_warning = self._load_first(_SYSTEM_WARNING)
        self._chicha_ack = self._load_first(_CHICHA_ACK)
        self._ambient_menu = self._load_first(_AMBIENT_MENU)
        self._apply_loaded_volumes()

    def _play(self, sound: Optional[pygame.mixer.Sound]) -> None:
        if not self._sfx_enabled or sound is None:
            return
        try:
            sound.play()
        except pygame.error:
            pass

    def play_menu_move(self) -> None:
        self._play(self._navigation_menu_change)

    def play_confirm(self) -> None:
        self._play(self._action_confirm)

    def play_back(self) -> None:
        self._play(self._action_back)

    def play_warning(self) -> None:
        self._play(self._system_warning)

    def play_chicha_ack(self) -> None:
        self._play(self._chicha_ack)

    def play_startup(self) -> int:
        """
        Play startup chime. Returns suggested minimum ms to let the clip breathe, or 0.
        """
        if not self._sfx_enabled or self._system_startup is None:
            return 0
        try:
            self._system_startup.play()
            return max(400, int(self._system_startup.get_length() * 1000))
        except pygame.error:
            return 0

    def play_shutdown(self) -> int:
        if self._system_shutdown is None:
            return 0
        try:
            self._system_shutdown.play()
            ms = int(self._system_shutdown.get_length() * 1000)
            return max(ms, 400)
        except pygame.error:
            return 0

    def start_ambient_menu(self) -> None:
        if not self.mixer_ready or self._ambient_menu is None:
            return
        try:
            if self._ambient_channel is None:
                self._ambient_channel = pygame.mixer.Channel(7)
            if self._ambient_channel.get_busy():
                return
            self._ambient_channel.play(self._ambient_menu, loops=-1)
        except pygame.error:
            pass

    def stop_ambient_menu(self) -> None:
        if self._ambient_channel is None:
            return
        try:
            self._ambient_channel.stop()
        except pygame.error:
            pass
