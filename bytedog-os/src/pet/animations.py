"""Chicha: folder-based frame clips, legacy single PNGs, and vector fallback."""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pygame

from src.pet.state import PetState


@dataclass(slots=True)
class FrameClip:
    frames: list[pygame.Surface]
    fps: float


@dataclass(slots=True)
class ChichaVisuals:
    """Loaded clips keyed by mood folder name: idle, sleep, happy, alert."""

    clips: dict[str, FrameClip]

    @classmethod
    def load(cls, chicha_dir: Path, chicha_cfg: dict[str, Any]) -> ChichaVisuals:
        default_fps = float(chicha_cfg.get("default_fps", 8.0))
        clips_cfg: dict[str, Any] = chicha_cfg.get("clips", {}) or {}
        clips: dict[str, FrameClip] = {}
        for name in ("idle", "sleep", "happy", "alert"):
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
    """Advances frame clips based on dt while staying independent of render FPS spikes."""

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
    )

    def __init__(self, visuals: ChichaVisuals) -> None:
        self._visuals = visuals
        self._clip_name = "idle"
        self._frame_index = 0
        self._accum_ms = 0.0
        self._idle_hold_ms = 0.0
        self._rng = random.Random()
        self._scale_key: tuple[int, int, bool, str, int] | None = None
        self._scale_surf: pygame.Surface | None = None
        self._launcher_idle_ms = 0.0
        self._nav_boost_ms = 0.0
        self._sleep_after_ms = 120_000.0
        self._nav_happy_ms = 650.0
        self._blink_phase_ms = 0.0
        self._blink_overlay_ms = 0.0
        self._next_blink_in_ms = self._rng.uniform(2200.0, 4800.0)

    def configure_ambient(self, chicha_cfg: dict[str, Any]) -> None:
        """Idle sleep delay and menu-reaction timing from config (Phase 1 polish)."""
        self._sleep_after_ms = max(30_000.0, float(chicha_cfg.get("sleep_after_idle_ms", 120_000.0)))
        self._nav_happy_ms = max(200.0, float(chicha_cfg.get("nav_happy_ms", 650.0)))

    def notify_activity(self) -> None:
        """User did something meaningful — reset idle timer toward sleep clip."""
        self._launcher_idle_ms = 0.0

    def notify_menu_navigated(self) -> None:
        """Menu highlight moved — brief happy bias + idle timing variation."""
        self._launcher_idle_ms = 0.0
        self._nav_boost_ms = self._nav_happy_ms
        if self._clip_name == "idle" and self._rng.random() < 0.38:
            self._idle_hold_ms = max(self._idle_hold_ms, self._rng.uniform(35.0, 120.0))

    def _desired_clip(self, pet: PetState) -> str:
        avail = set(self._visuals.clips.keys())
        if self._nav_boost_ms > 0.0 and "happy" in avail:
            return "happy"
        if self._launcher_idle_ms >= self._sleep_after_ms and "sleep" in avail:
            return "sleep"
        return resolve_clip_name(pet, avail)

    def update(self, dt_ms: float, pet: PetState) -> None:
        self._launcher_idle_ms += max(0.0, dt_ms)
        self._nav_boost_ms = max(0.0, self._nav_boost_ms - dt_ms)

        desired = self._desired_clip(pet)
        if desired != self._clip_name:
            self._clip_name = desired
            self._frame_index = 0
            self._accum_ms = 0.0
            self._idle_hold_ms = 0.0
            self._scale_key = None
            self._scale_surf = None

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

        self._accum_ms += max(0.0, dt_ms)
        step_ms = 1000.0 / clip.fps
        while self._accum_ms >= step_ms:
            self._accum_ms -= step_ms
            self._frame_index = (self._frame_index + 1) % len(clip.frames)
            if self._clip_name == "idle" and self._rng.random() < 0.07:
                self._idle_hold_ms = self._rng.uniform(70.0, 220.0)

    def draw(
        self,
        target: pygame.Surface,
        rect: pygame.Rect,
        *,
        fast_scale: bool,
    ) -> None:
        clip = self._visuals.clips.get(self._clip_name)
        if not clip or not clip.frames:
            self._scale_key = None
            self._scale_surf = None
            _draw_placeholder_dachshund(target, rect)
            return
        n = len(clip.frames)
        idx = self._frame_index % n
        key = (rect.width, rect.height, fast_scale, self._clip_name, idx)
        if self._scale_surf is None or self._scale_key != key:
            surf = clip.frames[idx]
            self._scale_surf = scale_surface(surf, (rect.width, rect.height), fast_scale)
            self._scale_key = key
        target.blit(self._scale_surf, rect.topleft)
        if self._clip_name == "idle" and self._blink_overlay_ms > 0.0:
            h = max(6, rect.height // 5)
            veil = pygame.Surface((rect.width, h), pygame.SRCALPHA)
            veil.fill((8, 4, 18, min(140, int(90 + 50 * math.sin(self._blink_overlay_ms * 0.45)))))
            target.blit(veil, (rect.x, rect.y + rect.height // 5))


def _draw_placeholder_dachshund(target: pygame.Surface, rect: pygame.Rect) -> None:
    """Simple elongated 'pixel' dachshund using primitives."""
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
