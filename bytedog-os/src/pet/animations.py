"""Chicha: folder-based frame clips, life-state mapping, blend, ambient motion."""

from __future__ import annotations

import math
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pygame

from src.pet.chicha_life import ChichaLifeState, clip_for_life_state
from src.pet.state import PetState

_ALERT_MOODS = frozenset({"alert", "warn", "danger", "scared"})
_HAPPY_MOODS = frozenset({"happy", "joy", "excited", "playful"})


@dataclass(slots=True)
class FrameClip:
    frames: list[pygame.Surface]
    fps: float


@dataclass(slots=True)
class ChichaVisuals:
    """Loaded clips keyed by mood folder name."""

    clips: dict[str, FrameClip]

    @classmethod
    def load(cls, chicha_dir: Path, chicha_cfg: dict[str, Any]) -> ChichaVisuals:
        default_fps = float(chicha_cfg.get("default_fps", 8.0))
        clips_cfg: dict[str, Any] = chicha_cfg.get("clips", {}) or {}
        raw_names = chicha_cfg.get("clip_names")
        if isinstance(raw_names, (list, tuple)) and raw_names:
            clip_names = tuple(str(x) for x in raw_names)
        else:
            clip_names = cls.default_clip_names()
        clips: dict[str, FrameClip] = {}
        for name in clip_names:
            raw = clips_cfg.get(name)
            per = raw if isinstance(raw, dict) else {}
            fps = float(per.get("fps", default_fps))
            folder = chicha_dir / name
            frames = _load_frames_from_folder(folder)
            if not frames:
                single = _try_load_single_png(chicha_dir / f"{name}.png")
                if single is not None:
                    frames = [single]
            if frames:
                clips[name] = FrameClip(frames=frames, fps=max(1.0, min(60.0, fps)))
        return cls(clips=clips)

    @staticmethod
    def default_clip_names() -> tuple[str, ...]:
        return (
            "idle",
            "sleep",
            "happy",
            "alert",
            "booting",
            "curious",
            "gaming",
            "low_battery",
        )


def _try_load_single_png(path: Path) -> Optional[pygame.Surface]:
    if not path.is_file():
        return None
    try:
        return pygame.image.load(path).convert_alpha()
    except (pygame.error, OSError, ValueError):
        return None


def _frame_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"(\d+)", path.stem)
    if match:
        return (int(match.group(1)), path.name.lower())
    return (10**9, path.name.lower())


def _load_frames_from_folder(folder: Path) -> list[pygame.Surface]:
    if not folder.is_dir():
        return []
    paths = [p for p in folder.glob("frame_*.png") if p.is_file()]
    if not paths:
        paths = [p for p in folder.glob("*.png") if p.is_file()]
    paths.sort(key=_frame_sort_key)
    frames: list[pygame.Surface] = []
    for path in paths:
        try:
            frames.append(pygame.image.load(path).convert_alpha())
        except (pygame.error, OSError, ValueError):
            continue
    return frames


def resolve_clip_name(pet: PetState, available: set[str]) -> str:
    """Legacy mood-based clip (used when life system picks IDLE and clips exist)."""
    mood = pet.mood_key()
    sleep_moods = {"sleep", "sleepy", "tired", "nap"}
    alert_moods = {"alert", "warn", "danger", "scared"}
    happy_moods = {"happy", "joy", "excited", "playful"}

    if mood in sleep_moods and "sleep" in available:
        return "sleep"
    if mood in alert_moods and "alert" in available:
        return "alert"
    if mood in happy_moods and "happy" in available:
        return "happy"
    if mood == "idle" and "idle" in available:
        return "idle"
    if "idle" in available:
        return "idle"
    if "happy" in available:
        return "happy"
    if available:
        return sorted(available)[0]
    return "idle"


def scale_surface(
    source: pygame.Surface,
    size: tuple[int, int],
    fast: bool,
) -> pygame.Surface:
    if fast:
        return pygame.transform.scale(source, size)
    return pygame.transform.smoothscale(source, size)


class ChichaAnimator:
    """Frame clips + life states + lightweight ambient (blink, tail, look)."""

    __slots__ = (
        "_visuals",
        "_clip_name",
        "_frame_index",
        "_accum_ms",
        "_idle_hold_ms",
        "_rng",
        "_scale_key",
        "_scale_surf",
        "_launcher_idle_ms",
        "_nav_boost_ms",
        "_sleep_after_ms",
        "_nav_happy_ms",
        "_blink_phase_ms",
        "_blink_overlay_ms",
        "_next_blink_in_ms",
        "_booting",
        "_gaming_mode",
        "_battery_pct",
        "_low_battery_threshold",
        "_burst_times",
        "_curious_boost_ms",
        "_reactive_nav",
        "_blend_ms_remaining",
        "_blend_from_clip",
        "_blend_from_index",
        "_tail_phase",
        "_look_x",
        "_look_until_mono",
        "_life_state",
        "_blink_veil_size",
        "_blink_veil",
        "_blend_duration_ms",
        "_blend_scale_key",
        "_blend_scale_surf",
    )

    def __init__(self, visuals: ChichaVisuals) -> None:
        self._visuals = visuals
        self._clip_name = "idle"
        self._frame_index = 0
        self._accum_ms = 0.0
        self._idle_hold_ms = 0.0
        self._rng = random.Random()
        self._scale_key: tuple[int, int, bool, str, int, int] | None = None
        self._scale_surf: pygame.Surface | None = None
        self._launcher_idle_ms = 0.0
        self._nav_boost_ms = 0.0
        self._sleep_after_ms = 120_000.0
        self._nav_happy_ms = 650.0
        self._blink_phase_ms = 0.0
        self._blink_overlay_ms = 0.0
        self._next_blink_in_ms = self._rng.uniform(2200.0, 4800.0)
        self._booting = False
        self._gaming_mode = False
        self._battery_pct: int | None = None
        self._low_battery_threshold = 15
        self._burst_times: list[float] = []
        self._curious_boost_ms = 0.0
        self._reactive_nav = True
        self._blend_ms_remaining = 0.0
        self._blend_from_clip = "idle"
        self._blend_from_index = 0
        self._blend_scale_key: tuple[int, int, bool, str, int, int] | None = None
        self._blend_scale_surf: pygame.Surface | None = None
        self._blend_duration_ms = 160.0
        self._tail_phase = 0.0
        self._look_x = 0
        self._look_until_mono = 0.0
        self._life_state = ChichaLifeState.IDLE
        self._blink_veil_size: tuple[int, int] | None = None
        self._blink_veil: pygame.Surface | None = None

    def configure_ambient(self, chicha_cfg: dict[str, Any]) -> None:
        self._sleep_after_ms = max(30_000.0, float(chicha_cfg.get("sleep_after_idle_ms", 120_000.0)))
        self._nav_happy_ms = max(200.0, float(chicha_cfg.get("nav_happy_ms", 650.0)))
        self._low_battery_threshold = max(1, min(50, int(chicha_cfg.get("low_battery_threshold_pct", 15))))
        self._blend_duration_ms = max(0.0, min(400.0, float(chicha_cfg.get("clip_blend_ms", 160.0))))
        self._reactive_nav = bool(chicha_cfg.get("reactive_to_navigation", True))

    def set_booting(self, active: bool) -> None:
        self._booting = bool(active)

    def set_gaming_mode(self, active: bool) -> None:
        self._gaming_mode = bool(active)

    def set_battery_percent(self, pct: int | None) -> None:
        self._battery_pct = int(pct) if pct is not None else None

    def set_reactive_navigation(self, enabled: bool) -> None:
        self._reactive_nav = bool(enabled)

    @property
    def life_state(self) -> ChichaLifeState:
        return self._life_state

    def notify_activity(self) -> None:
        self._launcher_idle_ms = 0.0

    def notify_menu_navigated(self) -> None:
        self._launcher_idle_ms = 0.0
        if self._reactive_nav:
            self._nav_boost_ms = self._nav_happy_ms
            now = time.monotonic()
            self._burst_times.append(now)
            cutoff = now - 0.55
            self._burst_times = [t for t in self._burst_times if t >= cutoff]
            if len(self._burst_times) >= 4:
                self._curious_boost_ms = max(self._curious_boost_ms, 900.0)
        if self._clip_name == "idle" and self._rng.random() < 0.38:
            self._idle_hold_ms = max(self._idle_hold_ms, self._rng.uniform(35.0, 120.0))

    def _compute_life_state(self, pet: PetState) -> ChichaLifeState:
        if self._booting:
            return ChichaLifeState.BOOTING
        if self._gaming_mode:
            return ChichaLifeState.GAMING
        if self._battery_pct is not None and self._battery_pct <= self._low_battery_threshold:
            return ChichaLifeState.LOW_BATTERY
        if self._reactive_nav and self._nav_boost_ms > 0.0:
            return ChichaLifeState.HAPPY
        if self._reactive_nav and self._curious_boost_ms > 0.0:
            return ChichaLifeState.CURIOUS
        if self._launcher_idle_ms >= self._sleep_after_ms:
            return ChichaLifeState.SLEEPY
        mk = pet.mood_key()
        if mk in _ALERT_MOODS:
            return ChichaLifeState.ALERT
        if mk in _HAPPY_MOODS:
            return ChichaLifeState.HAPPY
        return ChichaLifeState.IDLE

    def _desired_clip(self, pet: PetState) -> str:
        avail = frozenset(self._visuals.clips.keys())
        if not avail:
            return "idle"
        life = self._compute_life_state(pet)
        self._life_state = life
        primary = clip_for_life_state(life, avail)
        if life is ChichaLifeState.IDLE:
            return resolve_clip_name(pet, set(avail))
        return primary

    def _begin_blend_if_needed(self, old_clip: str, old_index: int) -> None:
        if self._blend_duration_ms <= 0.0:
            return
        if old_clip not in self._visuals.clips:
            return
        self._blend_from_clip = old_clip
        self._blend_from_index = old_index
        self._blend_ms_remaining = self._blend_duration_ms
        self._blend_scale_key = None
        self._blend_scale_surf = None

    def update(self, dt_ms: float, pet: PetState) -> None:
        self._launcher_idle_ms += max(0.0, dt_ms)
        self._nav_boost_ms = max(0.0, self._nav_boost_ms - dt_ms)
        self._curious_boost_ms = max(0.0, self._curious_boost_ms - dt_ms)
        if self._blend_ms_remaining > 0.0:
            self._blend_ms_remaining = max(0.0, self._blend_ms_remaining - dt_ms)

        now = time.monotonic()
        if now >= self._look_until_mono:
            self._look_until_mono = now + self._rng.uniform(4.0, 9.0)
            self._look_x = int(self._rng.choice((-3, -2, -1, 0, 1, 2, 3)))

        desired = self._desired_clip(pet)
        if desired != self._clip_name:
            old_clip = self._clip_name
            old_idx = self._frame_index
            self._clip_name = desired
            self._frame_index = 0
            self._accum_ms = 0.0
            self._idle_hold_ms = 0.0
            self._scale_key = None
            self._scale_surf = None
            self._begin_blend_if_needed(old_clip, old_idx)

        self._idle_hold_ms = max(0.0, self._idle_hold_ms - dt_ms)
        if self._idle_hold_ms > 0:
            return

        clip = self._visuals.clips.get(self._clip_name)
        if not clip or len(clip.frames) <= 1:
            return

        if self._clip_name == "idle":
            if self._blink_overlay_ms > 0.0:
                self._blink_overlay_ms = max(0.0, self._blink_overlay_ms - dt_ms)
            else:
                self._blink_phase_ms += dt_ms
                if self._blink_phase_ms >= self._next_blink_in_ms:
                    self._blink_overlay_ms = self._rng.uniform(70.0, 130.0)
                    self._blink_phase_ms = 0.0
                    self._next_blink_in_ms = self._rng.uniform(2200.0, 4800.0)

        if self._clip_name in ("idle", "happy", "curious"):
            self._tail_phase += dt_ms * 0.011

        self._accum_ms += max(0.0, dt_ms)
        step_ms = 1000.0 / clip.fps
        while self._accum_ms >= step_ms:
            self._accum_ms -= step_ms
            self._frame_index = (self._frame_index + 1) % len(clip.frames)
            if self._clip_name == "idle" and self._rng.random() < 0.07:
                self._idle_hold_ms = self._rng.uniform(70.0, 220.0)

    def _scaled_frame(
        self,
        clip_name: str,
        frame_index: int,
        rect: pygame.Rect,
        fast_scale: bool,
        *,
        for_blend: bool,
    ) -> pygame.Surface | None:
        clip = self._visuals.clips.get(clip_name)
        if not clip or not clip.frames:
            return None
        n = len(clip.frames)
        idx = frame_index % n
        key = (rect.width, rect.height, fast_scale, clip_name, idx, self._look_x)
        if for_blend:
            if self._blend_scale_surf is not None and self._blend_scale_key == key:
                return self._blend_scale_surf
        elif self._scale_surf is not None and self._scale_key == key:
            return self._scale_surf
        surf = clip.frames[idx]
        scaled = scale_surface(surf, (rect.width, rect.height), fast_scale)
        if for_blend:
            self._blend_scale_surf = scaled
            self._blend_scale_key = key
        else:
            self._scale_surf = scaled
            self._scale_key = key
        return scaled

    def draw(
        self,
        target: pygame.Surface,
        rect: pygame.Rect,
        *,
        fast_scale: bool,
        now_s: float = 0.0,
    ) -> None:
        _ = now_s
        wag = 0.0
        if self._clip_name in ("idle", "happy", "curious", "gaming"):
            wag = math.sin(self._tail_phase) * 2.5

        draw_rect = rect.move(int(self._look_x + wag), 0)

        clip = self._visuals.clips.get(self._clip_name)
        if not clip or not clip.frames:
            self._scale_key = None
            self._scale_surf = None
            _draw_placeholder_dachshund(target, draw_rect)
            return

        main = self._scaled_frame(self._clip_name, self._frame_index, draw_rect, fast_scale, for_blend=False)
        if main is None:
            _draw_placeholder_dachshund(target, draw_rect)
            return

        blend_t = (
            self._blend_ms_remaining / self._blend_duration_ms
            if self._blend_duration_ms > 0.0 and self._blend_ms_remaining > 0.0
            else 0.0
        )
        if blend_t > 0.0 and self._blend_from_clip != self._clip_name:
            old_surf = self._scaled_frame(
                self._blend_from_clip, self._blend_from_index, draw_rect, fast_scale, for_blend=True
            )
            if old_surf is not None and old_surf.get_size() == main.get_size():
                target.blit(old_surf, draw_rect.topleft)
                alpha_new = int(255 * max(0.0, min(1.0, 1.0 - blend_t)))
                if alpha_new > 0:
                    layer = main.copy()
                    layer.set_alpha(alpha_new)
                    target.blit(layer, draw_rect.topleft)
            else:
                target.blit(main, draw_rect.topleft)
        else:
            target.blit(main, draw_rect.topleft)

        if self._clip_name == "idle" and self._blink_overlay_ms > 0.0:
            w, h = draw_rect.width, max(6, draw_rect.height // 5)
            if self._blink_veil is None or self._blink_veil_size != (w, h):
                self._blink_veil = pygame.Surface((w, h), pygame.SRCALPHA)
                self._blink_veil_size = (w, h)
            alpha = min(140, int(90 + 50 * math.sin(self._blink_overlay_ms * 0.45)))
            self._blink_veil.fill((0, 0, 0, 0))
            self._blink_veil.fill((8, 4, 18, alpha))
            target.blit(self._blink_veil, (draw_rect.x, draw_rect.y + draw_rect.height // 5))


def _draw_placeholder_dachshund(target: pygame.Surface, rect: pygame.Rect) -> None:
    x, y, w, h = rect.x, rect.y, rect.width, rect.height
    body_color = (120, 70, 40)
    ear_color = (90, 50, 30)
    snout = (200, 160, 120)
    collar = (184, 41, 255)

    pygame.draw.rect(target, body_color, pygame.Rect(x + w // 6, y + h // 3, int(w * 0.65), h // 3))
    pygame.draw.rect(target, body_color, pygame.Rect(x + int(w * 0.55), y + h // 4, w // 4, h // 4))
    pygame.draw.rect(target, snout, pygame.Rect(x + int(w * 0.72), y + h // 4 + 4, w // 7, h // 10))
    pygame.draw.rect(target, ear_color, pygame.Rect(x + int(w * 0.58), y + h // 5, w // 14, h // 6))
    pygame.draw.rect(target, ear_color, pygame.Rect(x + int(w * 0.66), y + h // 5, w // 14, h // 6))
    pygame.draw.rect(target, collar, pygame.Rect(x + int(w * 0.52), y + h // 3 + 2, w // 10, 6))
    leg_w, leg_h = max(4, w // 18), max(6, h // 5)
    for lx in (x + w // 5, x + int(w * 0.35), x + int(w * 0.55), x + int(w * 0.7)):
        pygame.draw.rect(target, ear_color, pygame.Rect(lx, y + int(h * 0.62), leg_w, leg_h))
