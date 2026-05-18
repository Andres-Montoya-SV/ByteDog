"""Detect WiFi lab toolchain (scan backends + aircrack suite) for this host."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.cyber import scope as scope_mod

# Homebrew (Apple Silicon / Intel) sbin is often missing from GUI app PATH.
_EXTRA_BIN_DIRS: tuple[str, ...] = (
    "/opt/homebrew/sbin",
    "/opt/homebrew/bin",
    "/usr/local/sbin",
    "/usr/local/bin",
)


@dataclass(frozen=True, slots=True)
class LabToolchain:
    os_name: str
    wifi_iface: str
    monitor_iface: str
    has_nmcli: bool
    has_iw: bool
    has_airmon: bool
    aireplay: str | None
    airodump: str | None

    @property
    def has_aircrack(self) -> bool:
        return bool(self.aireplay) and bool(self.airodump)

    @property
    def can_live_deauth(self) -> bool:
        return bool(self.aireplay)

    @property
    def can_live_capture(self) -> bool:
        return bool(self.airodump)

    @property
    def can_live_attack(self) -> bool:
        return self.can_live_deauth and self.can_live_capture

    def summary(self) -> str:
        parts = [self.os_name]
        if self.can_live_attack:
            parts.append(f"live · {self.monitor_iface}")
        elif self.can_live_deauth:
            parts.append("deauth ready · capture needs airodump-ng")
        elif self.can_live_capture:
            parts.append("capture ready · deauth needs aireplay-ng")
        else:
            parts.append("scan-only · install aircrack-ng")
        return " · ".join(parts)

    def tools_line(self) -> str:
        bits: list[str] = []
        if self.aireplay:
            bits.append(f"aireplay-ng OK ({Path(self.aireplay).parent.name})")
        else:
            bits.append("aireplay-ng missing")
        if self.airodump:
            bits.append(f"airodump-ng OK")
        else:
            bits.append("airodump-ng missing")
        return " · ".join(bits)


def find_executable(name: str, cfg: dict[str, Any]) -> str | None:
    """Resolve tool binary: PATH, config override, then Homebrew sbin."""
    found = shutil.which(name)
    if found:
        return found
    cfg_key = name.replace("-", "_")
    if p := _path_from_cfg(cfg, cfg_key):
        return p
    for directory in _EXTRA_BIN_DIRS:
        candidate = Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def build_toolchain(cfg: dict[str, Any]) -> LabToolchain:
    os_name = platform.system()
    wifi_iface = str(cfg.get("wifi_interface", "wlan0"))
    monitor_iface = str(cfg.get("monitor_interface", "wlan0mon"))
    if os_name == "Darwin" and wifi_iface == "wlan0":
        wifi_iface = str(cfg.get("wifi_interface", "en0"))
        monitor_iface = str(cfg.get("monitor_interface", wifi_iface))
    aireplay = find_executable("aireplay-ng", cfg)
    airodump = find_executable("airodump-ng", cfg)
    if not wifi_iface or wifi_iface == "wlan0":
        wifi_iface = _detect_linux_wifi_iface() or wifi_iface
    return LabToolchain(
        os_name=os_name,
        wifi_iface=wifi_iface,
        monitor_iface=monitor_iface,
        has_nmcli=shutil.which("nmcli") is not None,
        has_iw=shutil.which("iw") is not None,
        has_airmon=find_executable("airmon-ng", cfg) is not None,
        aireplay=aireplay,
        airodump=airodump,
    )


def _path_from_cfg(cfg: dict[str, Any], key: str) -> str | None:
    paths = cfg.get("tool_paths")
    if not isinstance(paths, dict):
        return None
    raw = paths.get(key)
    if not isinstance(raw, str) or not raw.strip():
        return None
    p = Path(raw.strip())
    if p.is_file() and os.access(p, os.X_OK):
        return str(p)
    return None


def _detect_linux_wifi_iface() -> str | None:
    if platform.system() != "Linux":
        return None
    try:
        proc = subprocess.run(
            ["iw", "dev"],
            capture_output=True,
            text=True,
            timeout=4.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("Interface "):
            return line.split()[1]
    return None


def ensure_monitor_mode(tc: LabToolchain) -> tuple[bool, str]:
    """Best-effort monitor mode for lab exercises (Pi / Linux)."""
    if platform.system() != "Linux":
        return False, (
            f"macOS uses {tc.monitor_iface} — monitor mode not auto-configured; "
            "use Pi lab AP for live frame injection."
        )
    if tc.has_airmon:
        airmon = find_executable("airmon-ng", {})
        if not airmon:
            return False, "airmon-ng not found"
        try:
            proc = subprocess.run(
                [airmon, "start", tc.wifi_iface],
                capture_output=True,
                text=True,
                timeout=20.0,
                check=False,
            )
            detail = (proc.stdout or proc.stderr or "").strip()[:180]
            return proc.returncode == 0, detail or "airmon-ng started"
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, str(exc)
    if not tc.has_iw:
        return False, "iw not available for monitor setup."
    try:
        subprocess.run(
            ["ip", "link", "set", tc.wifi_iface, "down"],
            timeout=5.0,
            check=False,
        )
        proc = subprocess.run(
            ["iw", "dev", tc.wifi_iface, "set", "type", "monitor"],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
        if proc.returncode != 0:
            return False, (proc.stderr or "iw monitor failed").strip()[:180]
        subprocess.run(
            ["ip", "link", "set", tc.wifi_iface, "up"],
            timeout=5.0,
            check=False,
        )
        return True, f"{tc.wifi_iface} set to monitor mode"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)


def preview_deauth_command(
    tc: LabToolchain,
    *,
    ssid: str,
    bssid: str,
    synthetic_bssid: bool,
    count: int = 5,
) -> str:
    """Human-readable command (no binaries required)."""
    exe = tc.aireplay or "aireplay-ng"
    iface = tc.monitor_iface
    if scope_mod.is_valid_bssid(bssid) and not synthetic_bssid:
        return f"{exe} --deauth {count} -a {bssid} {iface}"
    if ssid and ssid != "(hidden)":
        return f"{exe} --deauth {count} -e {ssid!r} {iface}"
    return f"{exe} --deauth {count} -a {bssid} {iface}"


def deauth_command(
    tc: LabToolchain,
    *,
    ssid: str,
    bssid: str,
    synthetic_bssid: bool,
    count: int = 5,
) -> list[str] | None:
    if not tc.aireplay:
        return None
    iface = tc.monitor_iface
    if scope_mod.is_valid_bssid(bssid) and not synthetic_bssid:
        return [tc.aireplay, "--deauth", str(count), "-a", bssid, iface]
    if ssid and ssid != "(hidden)":
        return [tc.aireplay, "--deauth", str(count), "-e", ssid, iface]
    return [tc.aireplay, "--deauth", str(count), "-a", bssid, iface]


def roaming_capture_command(
    tc: LabToolchain,
    *,
    ssid: str,
    bssid: str,
    synthetic_bssid: bool,
    out_prefix: str,
) -> list[str] | None:
    if not tc.airodump:
        return None
    iface = tc.monitor_iface
    cmd = [tc.airodump, "--write", out_prefix, "--output-format", "pcap,csv", iface]
    if scope_mod.is_valid_bssid(bssid) and not synthetic_bssid:
        cmd[1:1] = ["--bssid", bssid]
    elif ssid and ssid != "(hidden)":
        cmd[1:1] = ["--essid", ssid]
    return cmd


def preview_roaming_command(
    tc: LabToolchain,
    *,
    ssid: str,
    bssid: str,
    synthetic_bssid: bool,
    out_prefix: str = "lab_roam",
) -> str:
    exe = tc.airodump or "airodump-ng"
    iface = tc.monitor_iface
    if scope_mod.is_valid_bssid(bssid) and not synthetic_bssid:
        return f"{exe} --bssid {bssid} --write {out_prefix} {iface}"
    if ssid and ssid != "(hidden)":
        return f"{exe} --essid {ssid!r} --write {out_prefix} {iface}"
    return f"{exe} --write {out_prefix} {iface}"


def handshake_capture_command(
    tc: LabToolchain,
    *,
    ssid: str,
    bssid: str,
    synthetic_bssid: bool,
    out_prefix: str,
) -> list[str] | None:
    return roaming_capture_command(
        tc, ssid=ssid, bssid=bssid, synthetic_bssid=synthetic_bssid, out_prefix=out_prefix
    )
