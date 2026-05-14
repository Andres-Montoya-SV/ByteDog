"""Chicha: one static PNG per mood folder under assets/chicha/<name>/."""

from __future__ import annotations

import random
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
class ChichaVisuals:
    """One surface per mood key (folder name under ``assets/chicha``)."""

    images: dict[str, pygame.Surface]

    @classmethod
    def load(cls, chicha_dir: Path, chicha_cfg: dict[str, Any]) -> ChichaVisuals:
        clips_cfg: dict[str, Any] = chicha_cfg.get("clips", {}) or {}
        raw_names = chicha_cfg.get("clip_names")
        if isinstance(raw_names, (list, tuple)) and raw_names:
            clip_names = tuple(str(x) for x in raw_names)
        else:
            clip_names = cls.default_clip_names()
        images: dict[str, pygame.Surface] = {}
        for name in clip_names:
            per = clips_cfg.get(name)
            cfg_entry = per if isinstance(per, dict) else {}
            folder = chicha_dir / name
            path = _resolve_png_path(folder, name, cfg_entry)
            if path is None:
                continue
            try:
                img = pygame.image.load(str(path)).convert_alpha()
            except (pygame.error, OSError, ValueError):
                continue
            images[name] = img
        return cls(images=images)

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


def _resolve_png_path(folder: Path, clip_name: str, cfg_entry: dict[str, Any]) -> Optional[Path]:
    """Pick a single PNG: optional ``clips.<name>.file``, else best match in folder."""
    explicit = cfg_entry.get("file")
    if isinstance(explicit, str) and explicit.strip():
        p = folder / explicit.strip()
        if p.is_file():
            return p
    picked = _pick_png_in_folder(folder, clip_name)
    if picked is not None:
        return picked
    flat = folder.parent / f"{clip_name}.png" if folder.parent else None
    if flat is not None and flat.is_file():
        return flat
    return None


def _pick_png_in_folder(folder: Path, clip_name: str) -> Optional[Path]:
    if not folder.is_dir():
        return None
    pngs = [p for p in folder.glob("*.png") if p.is_file()]
    if not pngs:
        return None
    hint = clip_name.lower().replace("_", "-")
    # Prefer non frame_*.png spritesheets when both exist.
    non_frame = [p for p in pngs if not p.stem.lower().startswith("frame_")]
    pool = non_frame if non_frame else pngs
    pool.sort(key=lambda p: p.name.lower())
    for p in pool:
        stem_l = p.stem.lower()
        if hint in stem_l or "chicha" in stem_l:
            return p
    return pool[0]


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
    """Life-state driven pose selection; draws one scaled static image per state."""

    __slots__ = (
        "_visuals",
        "_clip_name",
        "_rng",
        "_scale_key",
        "_scale_surf",
        "_launcher_idle_ms",
        "_nav_boost_ms",
        "_sleep_after_ms",
        "_nav_happy_ms",
        "_booting",
        "_gaming_mode",
        "_battery_pct",
        "_low_battery_threshold",
        "_burst_times",
        "_curious_boost_ms",
        "_reactive_nav",
        "_life_state",
    )

    def __init__(self, visuals: ChichaVisuals) -> None:
        self._visuals = visuals
        self._clip_name = "idle"
        self._rng = random.Random()
        self._scale_key: tuple[int, int, bool, str] | None = None
        self._scale_surf: pygame.Surface | None = None
        self._launcher_idle_ms = 0.0
        self._nav_boost_ms = 0.0
        self._sleep_after_ms = 120_000.0
        self._nav_happy_ms = 650.0
        self._booting = False
        self._gaming_mode = False
        self._battery_pct: int | None = None
        self._low_battery_threshold = 15
        self._burst_times: list[float] = []
        self._curious_boost_ms = 0.0
        self._reactive_nav = True
        self._life_state = ChichaLifeState.IDLE

    def configure_ambient(self, chicha_cfg: dict[str, Any]) -> None:
        self._sleep_after_ms = max(30_000.0, float(chicha_cfg.get("sleep_after_idle_ms", 120_000.0)))
        self._nav_happy_ms = max(200.0, float(chicha_cfg.get("nav_happy_ms", 650.0)))
        self._low_battery_threshold = max(1, min(50, int(chicha_cfg.get("low_battery_threshold_pct", 15))))
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
        avail = frozenset(self._visuals.images.keys())
        if not avail:
            return "idle"
        life = self._compute_life_state(pet)
        self._life_state = life
        primary = clip_for_life_state(life, avail)
        if life is ChichaLifeState.IDLE:
            return resolve_clip_name(pet, set(avail))
        return primary

    def update(self, dt_ms: float, pet: PetState) -> None:
        self._launcher_idle_ms += max(0.0, dt_ms)
        self._nav_boost_ms = max(0.0, self._nav_boost_ms - dt_ms)
        self._curious_boost_ms = max(0.0, self._curious_boost_ms - dt_ms)

        desired = self._desired_clip(pet)
        if desired != self._clip_name:
            self._clip_name = desired
            self._scale_key = None
            self._scale_surf = None

    def draw(
        self,
        target: pygame.Surface,
        rect: pygame.Rect,
        *,
        fast_scale: bool,
        now_s: float = 0.0,
    ) -> None:
        _ = now_s
        src = self._visuals.images.get(self._clip_name)
        if src is None:
            self._scale_key = None
            self._scale_surf = None
            return
        key = (rect.width, rect.height, fast_scale, self._clip_name)
        if self._scale_key == key and self._scale_surf is not None:
            scaled = self._scale_surf
        else:
            scaled = scale_surface(src, (rect.width, rect.height), fast_scale)
            self._scale_surf = scaled
            self._scale_key = key
        target.blit(scaled, rect.topleft)
