"""Educational placeholders when hardware tools or dangerous actions are unavailable."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SimulatedNetwork:
    ssid: str
    bssid: str
    channel: int
    rssi: int


_LAB_SSIDS = (
    ("BYTE_DOG_LAB", "AA:BB:CC:DD:EE:01", 6, -42),
    ("UNI_GUEST", "AA:BB:CC:DD:EE:02", 6, -58),
    ("IOT_DEMO", "AA:BB:CC:DD:EE:03", 11, -67),
    ("CAFE_FREE", "AA:BB:CC:DD:EE:04", 1, -71),
    ("HOME_TEST", "AA:BB:CC:DD:EE:05", 6, -55),
)


def simulated_scan_networks() -> list[SimulatedNetwork]:
    rng = random.Random(int(time.time()) // 30)
    count = rng.randint(3, len(_LAB_SSIDS))
    picked = rng.sample(_LAB_SSIDS, k=count)
    out: list[SimulatedNetwork] = []
    for ssid, bssid, ch, rssi in picked:
        jitter = rng.randint(-6, 4)
        out.append(
            SimulatedNetwork(
                ssid=ssid,
                bssid=bssid,
                channel=ch,
                rssi=rssi + jitter,
            )
        )
    return out


def simulate_deauth(
    target_bssid: str,
    *,
    ssid: str = "",
    count: int = 5,
    command: str | None = None,
) -> dict[str, str]:
    label = ssid or target_bssid
    cmd = command or f"aireplay-ng --deauth {count} -a {target_bssid} wlan0mon"
    return {
        "name": "deauthentication",
        "status": "simulated",
        "detail": f"No live tool on this host · would deauth {label} on Pi lab.",
        "command": cmd,
    }


def simulate_roaming_collect(
    target_bssid: str,
    *,
    ssid: str = "",
    command: str | None = None,
) -> dict[str, str]:
    label = ssid or target_bssid
    cmd = command or f"airodump-ng --bssid {target_bssid} -w lab_roam wlan0mon"
    return {
        "name": "roaming_collection",
        "status": "simulated",
        "detail": f"Would capture roaming frames near {label} (Pi + airodump-ng).",
        "command": cmd,
    }


def simulate_handshake_capture(
    target_bssid: str,
    *,
    ssid: str = "",
    command: str | None = None,
) -> dict[str, str]:
    label = ssid or target_bssid
    cmd = command or f"airodump-ng --bssid {target_bssid} -w lab_hs wlan0mon"
    return {
        "name": "handshake_capture",
        "status": "simulated",
        "detail": f"Would capture WPA handshake for {label} (Pi + monitor iface).",
        "command": cmd,
    }


def simulate_offensive_shell(cmd: str) -> dict[str, str]:
    return {
        "name": "offensive_command",
        "status": "simulated",
        "detail": "Command blocked — set dangerous_actions_enabled in config.",
        "command": cmd,
    }
