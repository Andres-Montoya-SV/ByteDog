"""Fast, non-blocking boot health checks (handheld-friendly)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pygame

Status = Literal["PASS", "WARN", "FAIL"]


@dataclass(frozen=True, slots=True)
class HealthResult:
    name: str
    status: Status
    message: str


@dataclass(frozen=True, slots=True)
class BootContext:
    root: Path
    assets: Path
    data: Path
    db_path: Path
    config: dict[str, Any]
    window_width: int
    window_height: int


def run_all_checks(ctx: BootContext, *, mixer_ready: bool) -> list[HealthResult]:
    """Ordered lightweight checks; no network, no long I/O."""
    results: list[HealthResult] = []
    results.append(_check_config(ctx))
    results.append(_check_paths(ctx))
    results.append(_check_sqlite(ctx))
    results.append(_check_pygame())
    results.append(_check_audio_module(mixer_ready))
    results.append(_check_mixer(mixer_ready))
    results.append(_check_joystick_subsystem())
    results.append(_check_input_module())
    results.append(_check_display(ctx))
    results.append(_check_asset_tree(ctx))
    results.append(_check_sound_assets(ctx))
    return results


def any_fail(results: list[HealthResult]) -> bool:
    return any(r.status == "FAIL" for r in results)


def _check_config(ctx: BootContext) -> HealthResult:
    if ctx.config and isinstance(ctx.config.get("window"), dict):
        return HealthResult("config", "PASS", "app.json merged")
    return HealthResult("config", "WARN", "using sparse defaults")


def _check_paths(ctx: BootContext) -> HealthResult:
    missing: list[str] = []
    for label, path in (
        ("assets", ctx.assets),
        ("data", ctx.data),
    ):
        if not path.is_dir():
            missing.append(label)
    if missing:
        return HealthResult("folders", "FAIL", f"missing: {', '.join(missing)}")
    return HealthResult("folders", "PASS", "assets / data present")


def _check_sqlite(ctx: BootContext) -> HealthResult:
    try:
        uri = ctx.db_path.expanduser().resolve().as_uri()
        conn = sqlite3.connect(f"{uri}?mode=ro", uri=True, timeout=0.2)
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as exc:
        return HealthResult("database", "FAIL", str(exc)[:80])
    return HealthResult("database", "PASS", "SQLite readable")


def _check_pygame() -> HealthResult:
    if pygame.get_init():
        return HealthResult("pygame", "PASS", "initialized")
    return HealthResult("pygame", "FAIL", "not initialized")


def _check_audio_module(mixer_ready: bool) -> HealthResult:
    """pygame.mixer module present (distinct from buffer init)."""
    if mixer_ready:
        return HealthResult("audio", "PASS", "mixer initialized")
    return HealthResult("audio", "WARN", "mixer unavailable (silent UI)")


def _check_mixer(mixer_ready: bool) -> HealthResult:
    if mixer_ready:
        return HealthResult("audio_mixer", "PASS", "mixer active")
    return HealthResult("audio_mixer", "WARN", "mixer not active (optional)")


def _check_input_module() -> HealthResult:
    """SDL input / event queue readiness (post pygame.init)."""
    try:
        if pygame.get_init():
            return HealthResult("input", "PASS", "pygame event/input ready")
    except (pygame.error, AttributeError):
        pass
    return HealthResult("input", "WARN", "pygame not fully initialized")


def _check_joystick_subsystem() -> HealthResult:
    try:
        getter = getattr(pygame.joystick, "get_init", None)
        if callable(getter) and getter():
            return HealthResult("joysticks", "PASS", "subsystem ready")
    except (pygame.error, AttributeError):
        pass
    return HealthResult("joysticks", "WARN", "joystick subsystem not ready")


def _check_display(ctx: BootContext) -> HealthResult:
    if ctx.window_width <= 0 or ctx.window_height <= 0:
        return HealthResult("display", "FAIL", "invalid window size")
    return HealthResult("display", "PASS", f"{ctx.window_width}x{ctx.window_height}")


def _check_asset_tree(ctx: BootContext) -> HealthResult:
    chicha = ctx.assets / "chicha"
    fonts = ctx.assets / "fonts"
    sounds = ctx.assets / "sounds"
    images = ctx.assets / "images"
    missing: list[str] = []
    if not chicha.is_dir():
        missing.append("chicha/")
    if not fonts.is_dir():
        missing.append("fonts/")
    if not sounds.is_dir():
        missing.append("sounds/")
    if not images.is_dir():
        missing.append("images/")
    if missing:
        return HealthResult("assets", "WARN", f"missing: {', '.join(missing)}")
    return HealthResult("assets", "PASS", "chicha / fonts / sounds / images")


def _check_sound_assets(ctx: BootContext) -> HealthResult:
    sounds = ctx.assets / "sounds"
    if not sounds.is_dir():
        return HealthResult("sound_files", "WARN", "sounds/ missing")
    return HealthResult("sound_files", "PASS", "sounds directory present")
