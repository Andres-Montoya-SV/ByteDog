"""Pygame application shell for ByteDog OS Phase 1."""

from __future__ import annotations

import json
import random
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional

import pygame

from src.pet.animations import ChichaAnimator, ChichaVisuals, scale_surface
from src.pet.state import PetState
from src.services import battery as battery_service
from src.services import emulator as emulator_service
from src.services import system as system_service
from src.services import wifi as wifi_service
from src.services.audio import AudioService
from src.services.input_service import InputAction, InputService
from src.startup.health_checks import BootContext, run_all_checks
from src.startup.splash import run_startup_splash
from src.storage.database import ensure_database
from src.storage.ui_prefs import load_ui_prefs, save_ui_prefs
from src.ui.menu import LauncherMenu, MenuAction
from src.ui.handheld_shell import compute_handheld_main_layout, draw_handheld_launcher
from src.ui.icon_cache import MenuIconCache
from src.ui.ambient_motes import AmbientMotes
from src.ui.screens import (
    LayoutMetrics,
    compute_layout,
    draw_confirm_action_dialog,
    draw_launcher_background,
    draw_overlay_message,
    draw_quit_confirm_dialog,
    draw_status_bar_lines,
    finalize_frame_effects,
    measure_wrapped_status_bar,
)
from src.ui.debug_overlay import draw_input_debug_overlay
from src.ui.settings_screen import SettingsDisplayInfo, SettingsRow, draw_settings_screen
from src.ui.shutdown_screen import draw_shutdown_screen
from src.ui.theme import ScanlineOverlay, default_theme


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_config(root: Path) -> dict[str, Any]:
    cfg_path = root / "config" / "app.json"
    defaults: dict[str, Any] = {
        "window": {"width": 800, "height": 480, "fullscreen": False, "title": "ByteDog OS"},
        "fps": 60,
        "paths": {"assets": "assets", "data": "data"},
        "chicha": {
            "sleep_after_idle_ms": 120_000.0,
            "nav_happy_ms": 650.0,
            "low_battery_threshold_pct": 15,
            "reactive_to_navigation": True,
            "clip_names": (
                "idle",
                "sleep",
                "happy",
                "alert",
                "booting",
                "curious",
                "gaming",
                "low_battery",
            ),
            "clips": {},
        },
        "audio": {
            "master_volume": 1.0,
        },
        "performance": {
            "display_vsync": True,
            "chicha_fast_scale": False,
            "system_poll_sec": 1.0,
            "ambient_mote_count": 10,
        },
        "startup": {
            "show_splash": True,
            "minimum_splash_ms": 1500,
            "fail_on_critical": True,
            "startup_sound_sync_ms": 520.0,
        },
        "shutdown": {
            "minimum_display_ms": 2800,
        },
        "input": {
            "debug": False,
            "deadzone": 0.55,
            "stick_center_deadzone": 0.12,
            "repeat_cooldown_ms": 180.0,
            "repeat_cooldown_min_ms": 92.0,
            "repeat_accel_step_ms": 16.0,
            "stick_smooth_alpha": 0.22,
            "hat_repeat_ms": 140.0,
            "left_stick_horizontal_axis": 0,
            "left_stick_vertical_axis": 1,
            "dpad_horizontal_axis": -1,
            "dpad_vertical_axis": -1,
            "mappings": {
                "confirm_buttons": [0],
                "back_buttons": [1],
                "exit_buttons": [],
                "menu_up_buttons": [11],
                "menu_down_buttons": [12],
                "menu_left_buttons": [13],
                "menu_right_buttons": [14],
            },
        },
    }
    try:
        with cfg_path.open(encoding="utf-8") as handle:
            data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("config root must be an object")
            merged = defaults | data
            if isinstance(data.get("window"), dict):
                merged["window"] = defaults["window"] | data["window"]
            if isinstance(data.get("paths"), dict):
                merged["paths"] = defaults["paths"] | data["paths"]
            if isinstance(data.get("chicha"), dict):
                chicha_merged = dict(defaults["chicha"])
                chicha_merged.update(data["chicha"])
                user_clips = data["chicha"].get("clips")
                if isinstance(user_clips, dict):
                    base_clips = dict(defaults["chicha"]["clips"])
                    base_clips.update(user_clips)
                    chicha_merged["clips"] = base_clips
                merged["chicha"] = chicha_merged
            if isinstance(data.get("audio"), dict):
                merged["audio"] = dict(defaults.get("audio", {})) | data["audio"]
            if isinstance(data.get("performance"), dict):
                merged["performance"] = defaults["performance"] | data["performance"]
            if isinstance(data.get("startup"), dict):
                merged["startup"] = defaults["startup"] | data["startup"]
            if isinstance(data.get("shutdown"), dict):
                merged["shutdown"] = defaults["shutdown"] | data["shutdown"]
            if isinstance(data.get("input"), dict):
                im = dict(defaults["input"])
                im.update(data["input"])
                um = data["input"].get("mappings")
                if isinstance(um, dict):
                    base_m = dict(defaults["input"]["mappings"])
                    base_m.update(um)
                    for mk, mv in list(base_m.items()):
                        if isinstance(mv, list):
                            base_m[mk] = [int(x) for x in mv]
                    im["mappings"] = base_m
                merged["input"] = im
                for axis_key in ("dpad_horizontal_axis", "dpad_vertical_axis"):
                    if axis_key in im:
                        try:
                            merged["input"][axis_key] = int(im[axis_key])
                        except (TypeError, ValueError):
                            pass
            return merged
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"[ByteDog] Using defaults (config issue: {exc})", file=sys.stderr)
        return defaults


def ensure_runtime_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


class ByteDogApp:
    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        self._root = root
        self._config = config
        window = config.get("window", {}) or {}
        self._width = int(window.get("width", 800))
        self._height = int(window.get("height", 480))
        self._fullscreen = bool(window.get("fullscreen", False))
        self._title = str(window.get("title", "ByteDog OS"))
        self._fps = int(config.get("fps", 60))
        self._chicha_cfg: dict[str, Any] = config.get("chicha", {}) or {}
        self._performance: dict[str, Any] = config.get("performance", {}) or {}

        paths = config.get("paths", {}) or {}
        self._assets = root / str(paths.get("assets", "assets"))
        self._data = root / str(paths.get("data", "data"))
        chicha_root = self._assets / "chicha"
        ensure_runtime_dirs(
            self._assets,
            self._assets / "fonts",
            self._assets / "sounds",
            self._assets / "sounds" / "navigation",
            self._assets / "sounds" / "system",
            self._assets / "sounds" / "actions",
            self._assets / "sounds" / "chicha",
            self._assets / "sounds" / "ambient",
            self._assets / "images",
            chicha_root,
            chicha_root / "idle",
            chicha_root / "happy",
            chicha_root / "sleep",
            chicha_root / "alert",
            chicha_root / "booting",
            chicha_root / "curious",
            chicha_root / "gaming",
            chicha_root / "low_battery",
            self._data,
        )

        self._db_path = self._data / "bytedog.db"
        ensure_database(self._db_path)
        self._pet = PetState.from_db_path(self._db_path)

        self._prefs_path = self._data / "ui_prefs.json"
        self._ui_prefs = load_ui_prefs(self._prefs_path)

        self._theme = default_theme()
        self._menu = LauncherMenu()
        self._audio = AudioService(self._assets / "sounds")
        self._chicha_visuals = ChichaVisuals(images={})
        self._chicha_animator = ChichaAnimator(self._chicha_visuals)
        self._chicha_animator.configure_ambient(self._chicha_cfg)

        self._ambient_motes = AmbientMotes(count=int(self._performance.get("ambient_mote_count", 10)))
        self._settings_row = SettingsRow.SFX
        self._gaming_until_mono = 0.0
        self._launcher_entered_mono = 0.0
        self._battery_warned = False
        self._overlay_message: Optional[str] = None
        self._last_frame_dt_ms: float = 16.7
        self._clock = pygame.time.Clock()
        self._screen: Optional[pygame.Surface] = None
        self._scanlines = ScanlineOverlay()
        poll_sec = float(self._performance.get("system_poll_sec", 1.0))
        self._system_cache = system_service.SystemStatusCache(interval_sec=poll_sec)
        self._input_cfg: dict[str, Any] = config.get("input") or {}
        self._input_debug = bool(self._input_cfg.get("debug", False))
        self._joysticks: dict[int, pygame.joystick.Joystick] = {}
        self._input = InputService(self._input_cfg, self._joysticks)

        self._show_input_debug_overlay = False
        self._fps_ema = 60.0
        self._debug_last_button = "—"
        self._debug_last_action = "—"
        self._debug_last_axis = "—"
        self._debug_last_hat = "—"

        self._screen_mode = "launcher"
        self._menu_icons: Optional[MenuIconCache] = None
        self._settings_chicha_loaded: bool = False
        self._settings_chicha_source: Optional[pygame.Surface] = None
        self._settings_chicha_scaled: Optional[pygame.Surface] = None
        self._settings_chicha_scale_key: Optional[tuple[int, int, bool]] = None
        self._shutdown_started_at: float = 0.0
        self._shutdown_wait_ms: int = 0
        self._quit_confirm_active: bool = False
        self._shutdown_confirm_active: bool = False
        self._wire_menu()

    def _wire_menu(self) -> None:
        self._menu.bind_actions(
            {
                MenuAction.RETRO_GAMES: self._on_retro,
                MenuAction.CYBERDECK: lambda: self._set_overlay("Cyberdeck shell is not available in Phase 1."),
                MenuAction.CHICHA: lambda: self._set_overlay("Chicha care screen is coming soon."),
                MenuAction.TERMINAL: lambda: self._set_overlay("Terminal bridge is not wired in Phase 1."),
                MenuAction.SETTINGS: self._open_settings,
                MenuAction.SHUTDOWN: lambda: None,
            }
        )

    def _open_settings(self) -> None:
        self._settings_row = SettingsRow.SFX
        self._screen_mode = "settings"

    def _close_settings(self) -> None:
        self._screen_mode = "launcher"

    def _save_prefs(self) -> None:
        try:
            save_ui_prefs(self._prefs_path, self._ui_prefs)
        except OSError:
            pass

    def _maybe_low_battery_warning(self, batt: int | None) -> None:
        if batt is None:
            return
        if batt <= 15 and not self._battery_warned:
            self._battery_warned = True
            self._audio.play_warning()
        if batt >= 22:
            self._battery_warned = False

    def _maybe_nav_chicha_sound(self) -> None:
        if not self._ui_prefs.chicha_reactive_nav:
            return
        if random.random() < 0.055:
            self._audio.play_chicha_ack()

    def _set_overlay(self, message: str) -> None:
        self._overlay_message = message

    def _on_retro(self) -> None:
        self._gaming_until_mono = time.monotonic() + 2.75
        self._set_overlay(emulator_service.launch_retro_menu())

    def _shutdown(self) -> None:
        self._screen_mode = "shutdown"
        self._overlay_message = None
        self._shutdown_started_at = time.monotonic()
        sound_ms = self._audio.play_shutdown()
        sd_cfg = self._config.get("shutdown") or {}
        min_ms = float(sd_cfg.get("minimum_display_ms", 2800))
        self._shutdown_wait_ms = int(max(min_ms, float(sound_ms)))

    def _build_flags(self) -> int:
        flags = pygame.SCALED
        if self._fullscreen:
            flags |= pygame.FULLSCREEN
        return flags

    def _open_display(self) -> None:
        use_vsync = bool(self._performance.get("display_vsync", True))
        try:
            self._screen = pygame.display.set_mode(
                (self._width, self._height),
                flags=self._build_flags(),
                vsync=1 if use_vsync else 0,
            )
        except TypeError:
            self._screen = pygame.display.set_mode((self._width, self._height), flags=self._build_flags())

    def _enumerate_joysticks_at_startup(self) -> None:
        """Open already-connected devices once. Never call joystick.quit() here."""
        try:
            count = pygame.joystick.get_count()
        except pygame.error:
            return
        if self._input_debug:
            print(f"[input] startup joystick count: {count}")
        for idx in range(count):
            self._open_joystick_device_index(idx)

    def _open_joystick_device_index(self, device_index: int) -> None:
        """Open a single device by SDL device_index (hotplug or startup)."""
        try:
            j = pygame.joystick.Joystick(device_index)
            j.init()
            iid = j.get_instance_id()
        except pygame.error as exc:
            if self._input_debug:
                print(f"[input] open device_index={device_index} failed: {exc}")
            return
        existing = self._joysticks.get(iid)
        if existing is not None:
            if existing is not j:
                try:
                    j.quit()
                except pygame.error:
                    pass
            if self._input_debug:
                print(f"[input] skip duplicate instance_id={iid} (already tracked)")
            return
        self._joysticks[iid] = j
        if self._input_debug:
            print(
                f"[input] opened instance_id={iid} name={j.get_name()!r} "
                f"axes={j.get_numaxes()} buttons={j.get_numbuttons()} hats={j.get_numhats()}"
            )

    def _remove_joystick_instance_id(self, instance_id: int) -> None:
        j = self._joysticks.pop(instance_id, None)
        if j is None:
            return
        try:
            j.quit()
        except pygame.error:
            pass

    def run(self) -> None:
        pygame.init()
        try:
            pygame.joystick.init()
            self._enumerate_joysticks_at_startup()

            pygame.display.set_caption(self._title)
            self._audio.initialize()
            self._open_display()
        except pygame.error as exc:
            print(f"[ByteDog] Failed to open display: {exc}", file=sys.stderr)
            return

        if self._screen is None:
            return

        startup_cfg = self._config.get("startup") or {}
        ctx = BootContext(
            root=self._root,
            assets=self._assets,
            data=self._data,
            db_path=self._db_path,
            config=self._config,
            window_width=self._width,
            window_height=self._height,
        )
        health = run_all_checks(ctx, mixer_ready=self._audio.mixer_ready)

        try:
            self._chicha_visuals = ChichaVisuals.load(self._assets / "chicha", self._chicha_cfg)
            self._chicha_animator = ChichaAnimator(self._chicha_visuals)
        except (pygame.error, OSError, ValueError) as exc:
            print(f"[ByteDog] Chicha assets: {exc}", file=sys.stderr)
        self._chicha_animator.configure_ambient(self._chicha_cfg)
        self._chicha_animator.set_reactive_navigation(self._ui_prefs.chicha_reactive_nav)
        self._chicha_animator.set_booting(True)

        audio_cfg = self._config.get("audio") or {}
        self._audio.set_master_volume(float(audio_cfg.get("master_volume", 1.0)))
        self._audio.set_sfx_enabled(self._ui_prefs.sfx_enabled)
        if self._ui_prefs.ambient_menu_enabled:
            self._audio.start_ambient_menu()

        if bool(startup_cfg.get("show_splash", True)):
            min_ms = float(startup_cfg.get("minimum_splash_ms", 1500))
            fail_crit = bool(startup_cfg.get("fail_on_critical", True))
            sync_ms = float(startup_cfg.get("startup_sound_sync_ms", 520.0))
            if not run_startup_splash(
                self._screen,
                self._theme,
                health,
                minimum_ms=min_ms,
                fail_on_critical=fail_crit,
                clock=self._clock,
                target_fps=self._fps,
                audio=self._audio,
                chicha_animator=self._chicha_animator,
                chicha_pet=self._pet,
                chicha_fast_scale=bool(self._performance.get("chicha_fast_scale", False)),
                sync_startup_sound_ms=sync_ms,
            ):
                self._audio.shutdown()
                pygame.quit()
                return

        self._chicha_animator.set_booting(False)

        icon_px = max(36, min(44, self._height // 11))
        self._menu_icons = MenuIconCache(self._assets / "images", pixel_size=icon_px)
        self._menu_icons.preload(self._theme.accent_purple)

        self._launcher_entered_mono = time.monotonic()

        running = True
        while running:
            dt_ms = float(self._clock.tick(self._fps))
            self._last_frame_dt_ms = dt_ms
            self._fps_ema = 0.9 * self._fps_ema + 0.1 * (1000.0 / max(dt_ms, 0.001))
            self._input.step_cooldowns(dt_ms)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    if self._screen_mode == "shutdown":
                        running = False
                    elif not self._quit_confirm_active:
                        self._shutdown_confirm_active = False
                        self._quit_confirm_active = True
                    # While the quit dialog is open, ignore further close events until
                    # the user chooses stay (Esc/B) or quit (Enter/A).
                    break
                if self._screen_mode == "shutdown":
                    continue
                if event.type == pygame.JOYDEVICEADDED:
                    self._input.debug_log_event(event)
                    self._open_joystick_device_index(event.device_index)
                    continue
                if event.type == pygame.JOYDEVICEREMOVED:
                    self._input.debug_log_event(event)
                    self._remove_joystick_instance_id(event.instance_id)
                    continue
                if event.type == pygame.JOYAXISMOTION:
                    self._debug_last_axis = f"a{event.axis}={event.value:+.3f}"
                    if self._input_debug:
                        self._input.debug_log_event(event)
                elif event.type == pygame.JOYHATMOTION:
                    self._debug_last_hat = str(event.value)
                    if self._input_debug:
                        self._input.debug_log_event(event)
                elif self._input_debug and event.type in (
                    pygame.JOYBUTTONDOWN,
                ):
                    self._input.debug_log_event(event)
                if event.type == pygame.JOYBUTTONDOWN:
                    self._debug_last_button = str(event.button)
                if event.type in (
                    pygame.KEYDOWN,
                    pygame.JOYBUTTONDOWN,
                    pygame.JOYHATMOTION,
                    pygame.JOYAXISMOTION,
                ):
                    if not self._dispatch_input(event):
                        running = False
                        break

            if running and self._screen_mode != "shutdown":
                if not self._handle_intents(self._input.poll_navigation()):
                    running = False

            if self._screen_mode != "shutdown":
                batt = battery_service.read_battery_percent()
                self._chicha_animator.set_battery_percent(batt)
                self._chicha_animator.set_gaming_mode(time.monotonic() < self._gaming_until_mono)
                self._chicha_animator.update(dt_ms, self._pet)
                self._maybe_low_battery_warning(batt)
            self._render_frame()
            pygame.display.flip()

            if running and self._screen_mode == "shutdown":
                if (time.monotonic() - self._shutdown_started_at) * 1000.0 >= self._shutdown_wait_ms:
                    running = False

        self._audio.shutdown()
        pygame.quit()

    def _dispatch_input(self, event: pygame.event.Event) -> bool:
        """Return False to stop the main loop."""
        return self._handle_intents(self._input.actions_from_event(event))

    def _handle_intents(self, intents: Iterable[InputAction]) -> bool:
        """Return False to stop the main loop."""
        if self._screen_mode == "shutdown":
            return True
        if self._quit_confirm_active:
            for intent in intents:
                self._debug_last_action = intent.name
                if intent is InputAction.TOGGLE_DEBUG:
                    self._show_input_debug_overlay = not self._show_input_debug_overlay
                    continue
                if intent in (InputAction.CONFIRM, InputAction.EXIT):
                    if self._screen_mode == "settings":
                        self._save_prefs()
                    self._audio.play_confirm()
                    return False
                if intent is InputAction.BACK:
                    self._audio.play_back()
                    self._quit_confirm_active = False
                    self._shutdown_confirm_active = False
            return True

        if self._shutdown_confirm_active:
            for intent in intents:
                self._debug_last_action = intent.name
                if intent is InputAction.TOGGLE_DEBUG:
                    self._show_input_debug_overlay = not self._show_input_debug_overlay
                    continue
                if intent is InputAction.CONFIRM:
                    self._audio.play_confirm()
                    self._shutdown_confirm_active = False
                    self._shutdown()
                    return True
                if intent in (
                    InputAction.BACK,
                    InputAction.EXIT,
                    InputAction.MENU_UP,
                    InputAction.MENU_DOWN,
                    InputAction.MENU_LEFT,
                    InputAction.MENU_RIGHT,
                ):
                    self._audio.play_back()
                    self._shutdown_confirm_active = False
            return True

        for intent in intents:
            self._debug_last_action = intent.name
            if intent is InputAction.TOGGLE_DEBUG:
                self._show_input_debug_overlay = not self._show_input_debug_overlay
                continue

            if self._screen_mode == "settings":
                rows = list(SettingsRow)
                if intent is InputAction.EXIT:
                    self._shutdown_confirm_active = False
                    self._quit_confirm_active = True
                    continue
                if intent is InputAction.BACK:
                    self._audio.play_back()
                    self._chicha_animator.notify_activity()
                    self._save_prefs()
                    self._close_settings()
                    continue
                if intent is InputAction.MENU_UP:
                    i = rows.index(self._settings_row)
                    self._settings_row = rows[(i - 1) % len(rows)]
                    self._audio.play_menu_move()
                    self._chicha_animator.notify_menu_navigated()
                elif intent is InputAction.MENU_DOWN:
                    i = rows.index(self._settings_row)
                    self._settings_row = rows[(i + 1) % len(rows)]
                    self._audio.play_menu_move()
                    self._chicha_animator.notify_menu_navigated()
                elif intent is InputAction.CONFIRM:
                    self._audio.play_confirm()
                    row = self._settings_row
                    if row is SettingsRow.SFX:
                        self._ui_prefs.sfx_enabled = not self._ui_prefs.sfx_enabled
                        self._audio.set_sfx_enabled(self._ui_prefs.sfx_enabled)
                    elif row is SettingsRow.AMBIENT:
                        self._ui_prefs.ambient_menu_enabled = not self._ui_prefs.ambient_menu_enabled
                        if self._ui_prefs.ambient_menu_enabled:
                            self._audio.start_ambient_menu()
                        else:
                            self._audio.stop_ambient_menu()
                    elif row is SettingsRow.CHICHA_REACTIVE:
                        self._ui_prefs.chicha_reactive_nav = not self._ui_prefs.chicha_reactive_nav
                        self._chicha_animator.set_reactive_navigation(self._ui_prefs.chicha_reactive_nav)
                    elif row is SettingsRow.BACK:
                        self._save_prefs()
                        self._close_settings()
                continue

            if intent is InputAction.EXIT:
                self._shutdown_confirm_active = False
                self._quit_confirm_active = True
                continue
            if intent is InputAction.BACK:
                self._audio.play_back()
                self._chicha_animator.notify_activity()
                if self._overlay_message:
                    self._overlay_message = None
                    continue
                self._shutdown_confirm_active = False
                self._quit_confirm_active = True
                continue

            if self._overlay_message:
                if intent is InputAction.CONFIRM:
                    self._audio.play_confirm()
                    self._chicha_animator.notify_activity()
                    self._overlay_message = None
                continue

            if intent is InputAction.MENU_UP:
                if self._menu.move_up():
                    self._audio.play_menu_move()
                    self._chicha_animator.notify_menu_navigated()
                    self._maybe_nav_chicha_sound()
            elif intent is InputAction.MENU_DOWN:
                if self._menu.move_down():
                    self._audio.play_menu_move()
                    self._chicha_animator.notify_menu_navigated()
                    self._maybe_nav_chicha_sound()
            elif intent is InputAction.MENU_LEFT:
                if self._menu.move_left():
                    self._audio.play_menu_move()
                    self._chicha_animator.notify_menu_navigated()
                    self._maybe_nav_chicha_sound()
            elif intent is InputAction.MENU_RIGHT:
                if self._menu.move_right():
                    self._audio.play_menu_move()
                    self._chicha_animator.notify_menu_navigated()
                    self._maybe_nav_chicha_sound()
            elif intent is InputAction.CONFIRM:
                self._audio.play_confirm()
                self._chicha_animator.notify_activity()
                if self._menu.selected.action is MenuAction.SHUTDOWN:
                    self._quit_confirm_active = False
                    self._shutdown_confirm_active = True
                else:
                    self._menu.activate()
        return True

    def _controller_names_summary(self) -> str:
        parts: list[str] = []
        for joy in self._joysticks.values():
            try:
                if joy.get_init():
                    parts.append(joy.get_name())
            except pygame.error:
                continue
        joined = ", ".join(parts)
        return joined[:80] if joined else "(none)"

    def _scaled_settings_chicha_corner(self, w: int, h: int, fast: bool) -> Optional[pygame.Surface]:
        """Static Chicha art for the settings header (`assets/images` PNGs)."""
        if w <= 0 or h <= 0:
            return None
        if not self._settings_chicha_loaded:
            self._settings_chicha_loaded = True
            images = self._assets / "images"
            for name in ("chicha-settings.png", "chicha.png"):
                path = images / name
                if not path.is_file():
                    continue
                try:
                    img = pygame.image.load(str(path))
                    try:
                        img = img.convert_alpha()
                    except pygame.error:
                        pass
                    self._settings_chicha_source = img
                    break
                except (pygame.error, OSError, ValueError):
                    continue
        if self._settings_chicha_source is None:
            return None
        key = (w, h, fast)
        if self._settings_chicha_scale_key == key and self._settings_chicha_scaled is not None:
            return self._settings_chicha_scaled
        self._settings_chicha_scaled = scale_surface(self._settings_chicha_source, (w, h), fast)
        self._settings_chicha_scale_key = key
        return self._settings_chicha_scaled

    def _prepare_status_bar(
        self, layout: LayoutMetrics, sw: int, sh: int
    ) -> tuple[list[str], pygame.Rect, int]:
        wifi = wifi_service.get_wifi_status()
        sysinfo = self._system_cache.get()
        status_lines = [
            f"{wifi.state.upper()} · {wifi.ssid} · {wifi.strength_percent}%",
            f"{sysinfo.get('hostname')} · {sysinfo.get('system')} {sysinfo.get('release')}",
        ]
        if "memory_linux_percent_used" in sysinfo:
            status_lines.append(
                f"MEM ~{sysinfo['memory_linux_percent_used']}% of {sysinfo.get('memory_linux_mb_total')} MB"
            )
        font_size = max(14, layout.stat_size - 2)
        bar_w = sw - 2 * layout.margin
        wrapped, status_h = measure_wrapped_status_bar(status_lines, font_size, bar_w)
        status_rect = pygame.Rect(layout.margin, sh - layout.margin - status_h, bar_w, status_h)
        return wrapped, status_rect, font_size

    def _draw_status_overlay_scanlines_debug(
        self,
        surface: pygame.Surface,
        layout: LayoutMetrics,
        sw: int,
        sh: int,
        *,
        status_prepared: tuple[list[str], pygame.Rect, int] | None = None,
    ) -> None:
        if status_prepared is not None:
            wrapped_status, status_rect, font_size = status_prepared
        else:
            wrapped_status, status_rect, font_size = self._prepare_status_bar(layout, sw, sh)
        draw_status_bar_lines(surface, self._theme, wrapped_status, font_size, status_rect)

        if self._overlay_message:
            draw_overlay_message(surface, self._theme, self._overlay_message, layout.menu_size)

        finalize_frame_effects(surface, self._scanlines, self._theme)

        if self._show_input_debug_overlay:
            lines = self._build_input_debug_overlay_lines()
            draw_input_debug_overlay(surface, self._theme, lines, font_size=max(13, layout.stat_size - 2))

    def _render_frame(self) -> None:
        if self._screen is None:
            return
        surface = self._screen
        draw_launcher_background(surface, self._theme)

        sw, sh = surface.get_size()
        layout = compute_layout(sw, sh)

        if self._screen_mode == "shutdown":
            draw_shutdown_screen(surface, self._theme, started_monotonic=self._shutdown_started_at)
            finalize_frame_effects(surface, self._scanlines, self._theme)
            return

        if self._screen_mode == "settings":
            status_prepared = self._prepare_status_bar(layout, sw, sh)
            _, status_rect, _ = status_prepared
            fast_scale = bool(self._performance.get("chicha_fast_scale", False))
            draw_settings_screen(
                surface,
                self._theme,
                SettingsDisplayInfo(
                    controller_summary=self._controller_names_summary(),
                    resolution=f"{sw}x{sh}",
                    fullscreen=self._fullscreen,
                    fps_target=self._fps,
                    audio_ready=self._audio.mixer_ready,
                    input_debug=self._input_debug,
                ),
                self._ui_prefs,
                self._settings_row,
                time.monotonic(),
                content_bottom_y=status_rect.top,
            )
            margin = max(20, min(sw, sh) // 28)
            mini = pygame.Rect(sw - margin - 138, margin + 56, 118, 92)
            corner = self._scaled_settings_chicha_corner(mini.w, mini.h, fast_scale)
            if corner is not None:
                surface.blit(corner, corner.get_rect(center=mini.center))
            self._draw_status_overlay_scanlines_debug(
                surface, layout, sw, sh, status_prepared=status_prepared
            )
            if self._quit_confirm_active:
                draw_quit_confirm_dialog(
                    surface,
                    self._theme,
                    title_font_size=max(20, layout.menu_size),
                    hint_font_size=max(15, layout.menu_size - 4),
                )
            return

        hl = compute_handheld_main_layout(sw, sh, len(self._menu.items))
        assert self._menu_icons is not None
        icon_surfaces = {action: self._menu_icons.get(action) for action in MenuAction}
        fast_scale = bool(self._performance.get("chicha_fast_scale", False))
        inner = hl.chicha_rect.inflate(-10, -10)
        intro_elapsed = max(0.0, time.monotonic() - self._launcher_entered_mono)
        intro_t = min(1.0, intro_elapsed / 0.42)
        intro_ease = intro_t * intro_t * (3.0 - 2.0 * intro_t)
        intro_slide = int((1.0 - intro_ease) * 36)
        draw_handheld_launcher(
            surface,
            self._theme,
            hl,
            self._menu,
            icon_surfaces,
            wifi_service.get_wifi_status(),
            battery_service.read_battery_percent(),
            selection_pulse_s=time.monotonic(),
            intro_slide_px=intro_slide,
            chicha_life=self._chicha_animator.life_state,
        )

        self._ambient_motes.resize(inner.w, inner.h)
        self._ambient_motes.update(self._last_frame_dt_ms)
        self._chicha_animator.draw(surface, inner, fast_scale=fast_scale, now_s=time.monotonic())
        self._ambient_motes.draw(surface, inner, self._theme.accent_purple)

        if self._overlay_message:
            draw_overlay_message(surface, self._theme, self._overlay_message, layout.menu_size)

        finalize_frame_effects(surface, self._scanlines, self._theme)

        if self._shutdown_confirm_active:
            draw_confirm_action_dialog(
                surface,
                self._theme,
                title="¿Apagar el sistema?",
                confirm_hint="Enter o botón A · apagar",
                cancel_hint="Esc o botón B · cancelar",
                title_font_size=max(20, layout.menu_size),
                hint_font_size=max(15, layout.menu_size - 4),
                border_color=self._theme.danger,
            )

        if self._quit_confirm_active:
            draw_quit_confirm_dialog(
                surface,
                self._theme,
                title_font_size=max(20, layout.menu_size),
                hint_font_size=max(15, layout.menu_size - 4),
            )

        if self._show_input_debug_overlay:
            lines = self._build_input_debug_overlay_lines()
            draw_input_debug_overlay(surface, self._theme, lines, font_size=max(13, layout.stat_size - 2))

    def _build_input_debug_overlay_lines(self) -> list[str]:
        lines = [
            f"FPS ~{self._fps_ema:.0f}",
            f"joysticks: {len(self._joysticks)}",
        ]
        if not self._joysticks:
            lines.append("names: (none)")
            lines.append("axes: —")
        else:
            names = ", ".join(j.get_name() for j in self._joysticks.values())
            lines.append(f"names: {names[:70]}")
            axis_parts: list[str] = []
            for iid, joy in self._joysticks.items():
                try:
                    if not joy.get_init():
                        continue
                    vals = [f"{joy.get_axis(a):+.2f}" for a in range(joy.get_numaxes())]
                    axis_parts.append(f"id{iid}:[{','.join(vals)}]")
                except pygame.error:
                    axis_parts.append(f"id{iid}:?")
            lines.append("axes: " + (" | ".join(axis_parts))[:100])
        lines.append(f"menu selection: {self._menu.selected.label} (#{self._menu.selected_index})")
        lines.append(f"last raw button: {self._debug_last_button}")
        lines.append(f"last raw axis (event): {self._debug_last_axis}")
        lines.append(f"last raw hat (event): {self._debug_last_hat}")
        lines.append(f"last semantic action: {self._debug_last_action}")
        lines.extend(self._input.raw_input_debug_lines())
        lines.append("F3 = toggle overlay | input.debug = terminal")
        return lines


def run_app() -> None:
    root = project_root()
    config = load_config(root)
    ByteDogApp(root, config).run()


if __name__ == "__main__":
    run_app()
