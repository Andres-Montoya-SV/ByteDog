"""Load ``config/*.json`` into one merged dict (Phase 2: split files, safe defaults)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _defaults() -> dict[str, Any]:
    """Single source of truth for defaults (embedded for offline Pi boot)."""
    return {
        "window": {"width": 800, "height": 480, "fullscreen": False, "title": "ByteDog OS"},
        "fps": 60,
        "paths": {"assets": "assets", "data": "data"},
        "chicha": {
            "sleep_after_idle_ms": 120_000.0,
            "nav_happy_ms": 650.0,
            "low_battery_threshold_pct": 15,
            "reactive_to_navigation": True,
            "default_fps": 6.0,
            "wake_ack_chance": 0.12,
            "blink": {
                "enabled": True,
                "idle_min_interval_ms": 3200.0,
                "idle_max_interval_ms": 9000.0,
                "blink_duration_ms": 120.0,
            },
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
        "audio": {"master_volume": 1.0},
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
        "shutdown": {"minimum_display_ms": 2800},
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
        "ui": {},
        "cyber_lab": {
            "enabled": True,
            "red_team_mode": True,
            "log_dir": "data/lab_logs",
            "dangerous_actions_enabled": True,
            "wifi_interface": "wlan0",
            "monitor_interface": "wlan0mon",
            "auto_monitor_mode": True,
            "tool_paths": {},
        },
    }


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _normalize_input_mappings(im: dict[str, Any]) -> None:
    m = im.get("mappings")
    if not isinstance(m, dict):
        return
    for mk, mv in list(m.items()):
        if isinstance(mv, list):
            m[mk] = [int(x) for x in mv]


def load_merged_config(root: Path) -> dict[str, Any]:
    """
    Merge ``config/app.json`` with optional ``input.json``, ``ui.json``, ``pet.json``.
    Missing optional files are ignored. Invalid ``app.json`` falls back to defaults.
    """
    cfg_dir = root / "config"
    defaults = _defaults()
    app_path = cfg_dir / "app.json"
    try:
        with app_path.open(encoding="utf-8") as handle:
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
                im["mappings"] = base_m
            merged["input"] = im
            for axis_key in ("dpad_horizontal_axis", "dpad_vertical_axis"):
                if axis_key in im:
                    try:
                        merged["input"][axis_key] = int(im[axis_key])
                    except (TypeError, ValueError):
                        pass
        if isinstance(data.get("ui"), dict):
            merged["ui"] = dict(defaults.get("ui", {})) | data["ui"]
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"[ByteDog] Using defaults (config issue: {exc})", file=sys.stderr)
        merged = dict(defaults)

    # Optional split files (override same keys as monolithic app.json would).
    if extra := _load_json(cfg_dir / "input.json"):
        merged["input"] = _deep_merge(merged.get("input") or {}, extra)
        _normalize_input_mappings(merged["input"])
    if extra := _load_json(cfg_dir / "pet.json"):
        merged["chicha"] = _deep_merge(merged.get("chicha") or {}, extra)
    if extra := _load_json(cfg_dir / "ui.json"):
        merged["ui"] = _deep_merge(merged.get("ui") or {}, extra)
        if isinstance(extra.get("performance"), dict):
            merged["performance"] = _deep_merge(merged.get("performance") or {}, extra["performance"])
    if extra := _load_json(cfg_dir / "cyber_lab.json"):
        merged["cyber_lab"] = _deep_merge(merged.get("cyber_lab") or {}, extra)

    return merged
