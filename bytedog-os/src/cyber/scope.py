"""Lab scope checks for red-team exercises (university lab, user-confirmed)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_BSSID_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def normalize_bssid(value: str) -> str:
    raw = (value or "").strip().upper().replace("-", ":")
    if len(raw) == 12 and ":" not in raw:
        raw = ":".join(raw[i : i + 2] for i in range(0, 12, 2))
    return raw


def is_valid_bssid(value: str) -> bool:
    return bool(_BSSID_RE.match(normalize_bssid(value)))


@dataclass(frozen=True, slots=True)
class ScopeDecision:
    allowed: bool
    reason: str
    simulated: bool = False


def check_red_team_scope(
    cfg: dict[str, Any],
    *,
    target_bssid: str,
    dangerous_enabled: bool,
) -> ScopeDecision:
    if not bool(cfg.get("enabled", True)):
        return ScopeDecision(False, "WiFi Lab is disabled in config.", simulated=True)
    if not bool(cfg.get("red_team_mode", True)):
        return ScopeDecision(False, "Red Team mode is disabled in config.", simulated=True)
    norm = normalize_bssid(target_bssid)
    if not is_valid_bssid(norm):
        return ScopeDecision(
            False,
            "Select a valid target from a live scan.",
            simulated=True,
        )
    if not dangerous_enabled:
        return ScopeDecision(
            False,
            "dangerous_actions_enabled is false — simulation only.",
            simulated=True,
        )
    return ScopeDecision(
        True,
        f"University lab scope · target {norm} · live tools enabled.",
        simulated=False,
    )
