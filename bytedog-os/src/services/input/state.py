"""Mapping tables, axis math, and per-device navigation edge state (Pi / SDL2 friendly)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

_DEFAULT_MAPPINGS: Final[dict[str, list[int]]] = {
    "confirm_buttons": [0],
    "back_buttons": [1],
    "exit_buttons": [],
    "menu_up_buttons": [11],
    "menu_down_buttons": [12],
    "menu_left_buttons": [13],
    "menu_right_buttons": [14],
}


def int_list(raw: Any) -> list[int]:
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for x in raw:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def mapping_sets(cfg: dict[str, Any]) -> dict[str, frozenset[int]]:
    m = dict(_DEFAULT_MAPPINGS)
    user = cfg.get("mappings")
    if isinstance(user, dict):
        for key in _DEFAULT_MAPPINGS:
            if key in user and isinstance(user[key], list):
                m[key] = int_list(user[key])
    return {k: frozenset(v) for k, v in m.items()}


def axis_sign(value: float, threshold: float) -> int:
    """-1 = negative deflection, 0 = neutral, 1 = positive deflection."""
    if value > threshold:
        return 1
    if value < -threshold:
        return -1
    return 0


@dataclass(slots=True)
class NavAxisState:
    """Per-source axis sign memory for edge detection (-1 / 0 / +1)."""

    h: int = 0
    v: int = 0
