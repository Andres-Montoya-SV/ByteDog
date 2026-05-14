"""Persisted lightweight UI preferences (Phase 2; JSON, no schema migration yet)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class UiPreferences:
    sfx_enabled: bool = True
    ambient_menu_enabled: bool = False
    chicha_reactive_nav: bool = True
    brightness_placeholder: int = 80  # 0–100, display only until backlight hook exists

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json_dict(cls, raw: dict[str, Any]) -> UiPreferences:
        return cls(
            sfx_enabled=bool(raw.get("sfx_enabled", True)),
            ambient_menu_enabled=bool(raw.get("ambient_menu_enabled", False)),
            chicha_reactive_nav=bool(raw.get("chicha_reactive_nav", True)),
            brightness_placeholder=max(0, min(100, int(raw.get("brightness_placeholder", 80)))),
        )


def load_ui_prefs(path: Path) -> UiPreferences:
    if not path.is_file():
        return UiPreferences()
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return UiPreferences.from_json_dict(data)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return UiPreferences()


def save_ui_prefs(path: Path, prefs: UiPreferences) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(prefs.to_json_dict(), handle, indent=2)
    tmp.replace(path)
