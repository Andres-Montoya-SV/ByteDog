"""Chicha: mood folders under ``assets/chicha/<name>/`` — static hero PNGs and/or ``frame_*.png`` strips."""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Optional

import pygame

from src.pet.chicha_life import ChichaLifeState, clip_for_life_state
from src.pet.state import PetState

_ALERT_MOODS = frozenset({"alert", "warn", "danger", "scared"})
_HAPPY_MOODS = frozenset({"happy", "joy", "excited", "playful"})
_FRAME_RE = re.compile(r"frame_(\d+)", re.IGNORECASE)


@dataclass(slots=True)
class ChichaVisuals:
    """Preloaded surfaces per clip: one (static) or many (strip). FPS lives in ``clip_fps``."""

    frames: dict[str, list[pygame.Surface]]
    clip_fps: dict[str, float]

    @classmethod
    def empty(cls) -> ChichaVisuals:
        return cls(frames={}, clip_fps={})

    @classmethod
    def load(cls, chicha_dir: Path, chicha_cfg: dict[str, Any]) -> ChichaVisuals:
        clips_cfg: dict[str, Any] = chicha_cfg.get("clips", {}) or {}
        raw_names = chicha_cfg.get("clip_names")
        if isinstance(raw_names, (list, tuple)) and raw_names:
            clip_names = tuple(str(x) for x in raw_names)
        else:
            clip_names = cls.default_clip_names()
        default_fps = float(chicha_cfg.get("default_fps", 6.0))
        clip_fps: dict[str, float] = {}
        frames: dict[str, list[pygame.Surface]] = {}
        for name in clip_names:
            per = clips_cfg.get(name)
            cfg_entry = per if isinstance(per, dict) else {}
            folder = chicha_dir / name
            seq = _load_clip_surfaces(folder, name, cfg_entry)
            if not seq:
                continue
            frames[name] = seq
            try:
                clip_fps[name] = float(cfg_entry.get("fps", default_fps))
            except (TypeError, ValueError):
                clip_fps[name] = default_fps
        return cls(frames=frames, clip_fps=clip_fps)

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

    def clip_keys(self) -> frozenset[str]:
        return frozenset(self.frames.keys())


def _load_clip_surfaces(folder: Path, clip_name: str, cfg_entry: dict[str, Any]) -> list[pygame.Surface]:
    """Load all frames once at startup (no per-frame disk I/O)."""
    explicit = cfg_entry.get("file")
    if isinstance(explicit, str) and explicit.strip():
        p = folder / explicit.strip()
        if p.is_file():
            surf = _try_load_surface(p)
            return [surf] if surf is not None else []
    frame_paths = sorted(
        (p for p in folder.glob("frame_*.png") if p.is_file()),
        key=lambda p: _frame_sort_key(p.stem),
    )
    if frame_paths:
        out: list[pygame.Surface] = []
        for p in frame_paths:
            s = _try_load_surface(p)
            if s is not None:
                out.append(s)
        return out
    picked = _pick_png_in_folder(folder, clip_name)
    if picked is not None:
        surf = _try_load_surface(picked)
        return [surf] if surf is not None else []
    flat = folder.parent / f"{clip_name}.png" if folder.parent else None
    if flat is not None and flat.is_file():
        surf = _try_load_surface(flat)
        return [surf] if surf is not None else []
    return []


def _try_load_surface(path: Path) -> pygame.Surface | None:
    try:
        return pygame.image.load(str(path)).convert_alpha()
    except (pygame.error, OSError, ValueError):
        return None


def _frame_sort_key(stem: str) -> tuple[int, str]:
    m = _FRAME_RE.match(stem)
    if m:
        return (int(m.group(1)), stem.lower())
    return (10_000, stem.lower())


def _pick_png_in_folder(folder: Path, clip_name: str) -> Optional[Path]:
    if not folder.is_dir():
        return None
    pngs = [p for p in folder.glob("*.png") if p.is_file()]
    if not pngs:
        return None
    hint = clip_name.lower().replace("_", "-")
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


_PLACEHOLDER_COLORS: Final[tuple[tuple[int, int, int], ...]] = (
    (120, 72, 48),
    (92, 58, 40),
    (72, 48, 120),
)


def draw_chicha_vector_placeholder(target: pygame.Surface, rect: pygame.Rect) -> None:
    """Cheap silhouette when no PNGs loaded (Pi-safe: only primitives)."""
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    body = pygame.Rect(x + w // 6, y + h // 3, w * 2 // 3, h * 5 // 12)
    pygame.draw.ellipse(target, _PLACEHOLDER_COLORS[0], body)
    snout = pygame.Rect(x + w * 5 // 6 - w // 10, y + h // 2 - h // 14, w // 5, h // 7)
    pygame.draw.ellipse(target, _PLACEHOLDER_COLORS[1], snout)
    ear = pygame.Rect(x + w // 5, y + h // 5, w // 6, h // 5)
    pygame.draw.ellipse(target, _PLACEHOLDER_COLORS[2], ear)
    pygame.draw.circle(target, (40, 36, 52), (x + w * 5 // 6, y + h // 2 - h // 20), max(2, w // 28))


class ChichaAnimator:
    """Life-state driven pose + optional strip timing; cached scale per (clip, frame, size)."""

    __slots__ = (
        "_visuals",
        "_clip_name",
        "_frame_index",
        "_frame_ms_accum",
        "_rng",
        "_scale_key",
        "_scale_surf",
        "_launcher_idle_ms",
        "_nav_boost_ms",
        "_confirm_boost_ms",
        "_sleep_after_ms",
        "_nav_happy_ms",
        "_booting",
        "_gaming_mode",
        "_battery_pct",
        "_low_battery_threshold",
        "_burst_times",
        "_curious_boost_ms",
        "_reactive_nav",
        "_external_life",
        "_life_state",
        "_default_fps",
        "_blink_hold_ms",
        "_blink_cooldown_ms",
        "_blink_duration_ms",
        "_idle_blink_enabled",
        "_blink_min_ms",
        "_blink_max_ms",
    )

    def __init__(self, visuals: ChichaVisuals) -> None:
        self._visuals = visuals
        self._clip_name = "idle"
        self._frame_index = 0
        self._frame_ms_accum = 0.0
        self._rng = random.Random()
        self._scale_key: tuple[int, int, bool, str, int, int] | None = None
        self._scale_surf: pygame.Surface | None = None
        self._launcher_idle_ms = 0.0
        self._nav_boost_ms = 0.0
        self._confirm_boost_ms = 0.0
        self._sleep_after_ms = 120_000.0
        self._nav_happy_ms = 650.0
        self._booting = False
        self._gaming_mode = False
        self._battery_pct: int | None = None
        self._low_battery_threshold = 15
        self._burst_times: list[float] = []
        self._curious_boost_ms = 0.0
        self._reactive_nav = True
        self._external_life: ChichaLifeState | None = None
        self._life_state = ChichaLifeState.IDLE
        self._default_fps = 6.0
        self._blink_hold_ms = 0.0
        self._blink_cooldown_ms = 4000.0
        self._blink_duration_ms = 120.0
        self._idle_blink_enabled = True
        self._blink_min_ms = 3200.0
        self._blink_max_ms = 9000.0

    def configure_ambient(self, chicha_cfg: dict[str, Any]) -> None:
        self._sleep_after_ms = max(30_000.0, float(chicha_cfg.get("sleep_after_idle_ms", 120_000.0)))
        self._nav_happy_ms = max(200.0, float(chicha_cfg.get("nav_happy_ms", 650.0)))
        self._low_battery_threshold = max(1, min(50, int(chicha_cfg.get("low_battery_threshold_pct", 15))))
        self._reactive_nav = bool(chicha_cfg.get("reactive_to_navigation", True))
        self._default_fps = max(0.25, float(chicha_cfg.get("default_fps", 6.0)))
        blink = chicha_cfg.get("blink") if isinstance(chicha_cfg.get("blink"), dict) else {}
        try:
            self._blink_min_ms = float(blink.get("idle_min_interval_ms", 3200.0))
            self._blink_max_ms = float(blink.get("idle_max_interval_ms", 9000.0))
            self._blink_min_ms = max(800.0, self._blink_min_ms)
            self._blink_max_ms = max(self._blink_min_ms, self._blink_max_ms)
            self._blink_cooldown_ms = self._rng.uniform(self._blink_min_ms, self._blink_max_ms)
        except (TypeError, ValueError):
            self._blink_min_ms = 3200.0
            self._blink_max_ms = 9000.0
            self._blink_cooldown_ms = 4000.0
        try:
            self._blink_duration_ms = max(40.0, float(blink.get("blink_duration_ms", 120.0)))
        except (TypeError, ValueError):
            self._blink_duration_ms = 120.0
        self._idle_blink_enabled = bool(blink.get("enabled", True))

    def set_booting(self, active: bool) -> None:
        self._booting = bool(active)

    def set_gaming_mode(self, active: bool) -> None:
        self._gaming_mode = bool(active)

    def set_battery_percent(self, pct: int | None) -> None:
        self._battery_pct = int(pct) if pct is not None else None

    def set_reactive_navigation(self, enabled: bool) -> None:
        self._reactive_nav = bool(enabled)

    def set_external_life_state(self, state: ChichaLifeState | None) -> None:
        """Temporary override (e.g. WiFi Lab moods); cleared with ``None``."""
        self._external_life = state

    @property
    def life_state(self) -> ChichaLifeState:
        return self._life_state

    @property
    def current_clip_name(self) -> str:
        return self._clip_name

    def current_frame_count(self) -> int:
        return len(self._visuals.frames.get(self._clip_name, ()))

    def uses_placeholder_draw(self) -> bool:
        return len(self._visuals.frames) == 0

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

    def apply_confirm_boost(self) -> None:
        """Brief happy pose after menu confirm (deterministic, no AI)."""
        self._confirm_boost_ms = max(self._confirm_boost_ms, 480.0)
        self._launcher_idle_ms = 0.0

    def _compute_life_state(self, pet: PetState) -> ChichaLifeState:
        if self._booting:
            return ChichaLifeState.BOOTING
        if self._gaming_mode:
            return ChichaLifeState.GAMING
        if self._battery_pct is not None and self._battery_pct <= self._low_battery_threshold:
            return ChichaLifeState.LOW_BATTERY
        if self._external_life is not None:
            return self._external_life
        if self._confirm_boost_ms > 0.0:
            return ChichaLifeState.HAPPY
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
        avail = self._visuals.clip_keys()
        if not avail:
            return "idle"
        life = self._compute_life_state(pet)
        self._life_state = life
        primary = clip_for_life_state(life, avail)
        if life is ChichaLifeState.IDLE:
            return resolve_clip_name(pet, set(avail))
        return primary

    def _advance_strip(self, dt_ms: float) -> None:
        seq = self._visuals.frames.get(self._clip_name) or []
        n = len(seq)
        if n <= 1:
            self._frame_index = 0
            self._frame_ms_accum = 0.0
            return
        fps = self._visuals.clip_fps.get(self._clip_name, self._default_fps)
        fps = max(0.25, float(fps))
        step_ms = 1000.0 / fps
        self._frame_ms_accum += max(0.0, dt_ms)
        changed = False
        while self._frame_ms_accum >= step_ms and n > 0:
            self._frame_ms_accum -= step_ms
            self._frame_index = (self._frame_index + 1) % n
            changed = True
        if changed:
            self._scale_key = None

    def _tick_idle_blink(self, dt_ms: float) -> None:
        if not self._idle_blink_enabled:
            return
        seq = self._visuals.frames.get(self._clip_name) or []
        if self._life_state is not ChichaLifeState.IDLE or len(seq) != 1:
            self._blink_hold_ms = 0.0
            return
        if self._blink_hold_ms > 0.0:
            self._blink_hold_ms = max(0.0, self._blink_hold_ms - dt_ms)
            if self._blink_hold_ms <= 0.0:
                self._scale_key = None
            return
        self._blink_cooldown_ms -= dt_ms
        if self._blink_cooldown_ms <= 0.0:
            self._blink_hold_ms = self._blink_duration_ms
            self._scale_key = None
            self._blink_cooldown_ms = self._rng.uniform(self._blink_min_ms, self._blink_max_ms)

    def update(self, dt_ms: float, pet: PetState) -> None:
        self._launcher_idle_ms += max(0.0, dt_ms)
        self._nav_boost_ms = max(0.0, self._nav_boost_ms - dt_ms)
        self._confirm_boost_ms = max(0.0, self._confirm_boost_ms - dt_ms)
        self._curious_boost_ms = max(0.0, self._curious_boost_ms - dt_ms)

        desired = self._desired_clip(pet)
        if desired != self._clip_name:
            self._clip_name = desired
            self._frame_index = 0
            self._frame_ms_accum = 0.0
            self._scale_key = None

        self._advance_strip(dt_ms)
        self._tick_idle_blink(dt_ms)

    def draw(
        self,
        target: pygame.Surface,
        rect: pygame.Rect,
        *,
        fast_scale: bool,
        now_s: float = 0.0,
    ) -> None:
        _ = now_s
        seq = self._visuals.frames.get(self._clip_name) or []
        if not seq:
            for key in (self._clip_name, "idle", "happy", "sleep"):
                seq = self._visuals.frames.get(key) or []
                if seq:
                    break
            if not seq:
                for lst in self._visuals.frames.values():
                    seq = lst
                    break
        if not seq:
            draw_chicha_vector_placeholder(target, rect)
            return
        idx = self._frame_index % len(seq)
        src = seq[idx]
        squint = self._blink_hold_ms > 0.0 and len(seq) == 1
        dest_h = rect.height if not squint else max(4, int(rect.height * 0.92))
        dest_size = (rect.width, dest_h)
        cache_frame = idx if not squint else -1
        key = (rect.width, rect.height, fast_scale, self._clip_name, cache_frame, dest_h)
        if self._scale_key == key and self._scale_surf is not None:
            scaled = self._scale_surf
        else:
            scaled = scale_surface(src, dest_size, fast_scale)
            self._scale_surf = scaled
            self._scale_key = key
        y_off = rect.bottom - scaled.get_height()
        target.blit(scaled, (rect.x, y_off))
