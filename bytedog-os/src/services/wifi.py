"""Wi-Fi status (Phase 1 placeholder)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class WifiStatus:
    ssid: str
    strength_percent: int
    state: Literal["connected", "disconnected", "scanning"]


def get_wifi_status() -> WifiStatus:
    """Fake connectivity snapshot for UI polish."""
    return WifiStatus(ssid="NEON_DOG_NET", strength_percent=78, state="connected")
