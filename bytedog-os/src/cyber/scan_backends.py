"""Platform WiFi scan backends (read-only, no extra dependencies)."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.cyber import scope as scope_mod

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_CHANNEL_RE = re.compile(r"Channel:\s*(\d+)")
_SIGNAL_RE = re.compile(r"Signal / Noise:\s*(-?\d+)\s*dBm")


@dataclass(frozen=True, slots=True)
class ScanResult:
    ssid: str
    bssid: str
    channel: int
    rssi: int
    source: str
    synthetic_bssid: bool = False


def run_scan() -> tuple[list[ScanResult], str]:
    """Try real scanners in platform order; fall back to empty (caller may simulate)."""
    system = platform.system()
    if system == "Linux":
        if nets := _scan_nmcli():
            return nets, "nmcli"
        if nets := _scan_iw():
            return nets, "iw"
    if system == "Darwin":
        if nets := _scan_macos_corewlan():
            return nets, "corewlan"
        if nets := _scan_macos_system_profiler():
            return nets, "system_profiler"
    return [], "none"


def _scan_macos_corewlan() -> list[ScanResult]:
    """Active scan with real SSID names (macOS CoreWLAN). BSSID may be hidden by macOS."""
    script = _PROJECT_ROOT / "tools" / "macos_wifi_scan.swift"
    if not script.is_file():
        return []
    try:
        proc = subprocess.run(
            ["swift", str(script)],
            capture_output=True,
            text=True,
            timeout=25.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        rows = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    if not isinstance(rows, list):
        return []
    out: list[ScanResult] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ssid = str(row.get("ssid", "")) or "(hidden)"
        raw_bssid = str(row.get("bssid", "")).strip()
        bssid = scope_mod.normalize_bssid(raw_bssid) if raw_bssid else ""
        try:
            channel = int(row.get("channel", 0))
        except (TypeError, ValueError):
            channel = 0
        try:
            rssi = int(row.get("rssi", -80))
        except (TypeError, ValueError):
            rssi = -80
        if bssid and scope_mod.is_valid_bssid(bssid):
            out.append(
                ScanResult(ssid, bssid, channel, rssi, "corewlan", synthetic_bssid=False)
            )
        else:
            out.append(_macos_network(ssid, channel, rssi, source="corewlan"))
    return out


def _scan_nmcli() -> list[ScanResult]:
    try:
        proc = subprocess.run(
            ["nmcli", "-t", "-f", "SSID,BSSID,CHAN,SIGNAL", "device", "wifi", "list"],
            capture_output=True,
            text=True,
            timeout=15.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    out: list[ScanResult] = []
    for line in proc.stdout.splitlines():
        parts = _split_nmcli_terse(line)
        if len(parts) < 4:
            continue
        ssid = parts[0] or "(hidden)"
        bssid = scope_mod.normalize_bssid(parts[1])
        try:
            channel = int(parts[2]) if parts[2] else 0
        except ValueError:
            channel = 0
        try:
            rssi = int(parts[3])
        except ValueError:
            rssi = -100
        if scope_mod.is_valid_bssid(bssid):
            out.append(ScanResult(ssid, bssid, channel, rssi, "nmcli"))
    return out


def _split_nmcli_terse(line: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            buf.append(line[i + 1])
            i += 2
            continue
        if ch == ":":
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return parts


def _scan_iw() -> list[ScanResult]:
    iface = _linux_wifi_iface()
    if not iface:
        return []
    try:
        subprocess.run(
            ["iw", "dev", iface, "scan", "trigger"],
            capture_output=True,
            timeout=4.0,
            check=False,
        )
        proc = subprocess.run(
            ["iw", "dev", iface, "scan", "dump"],
            capture_output=True,
            text=True,
            timeout=14.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    return _parse_iw_scan(proc.stdout)


def _linux_wifi_iface() -> str | None:
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


def _parse_iw_scan(text: str) -> list[ScanResult]:
    out: list[ScanResult] = []
    ssid = ""
    bssid = ""
    channel = 0
    rssi = -100
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("BSS "):
            if bssid and scope_mod.is_valid_bssid(bssid):
                out.append(ScanResult(ssid or "(hidden)", bssid, channel, rssi, "iw"))
            parts = line.split()
            bssid = scope_mod.normalize_bssid(parts[1].rstrip(")"))
            ssid = ""
            channel = 0
            rssi = -100
        elif line.startswith("SSID:"):
            ssid = line.split("SSID:", 1)[1].strip()
        elif "signal:" in line:
            try:
                rssi = int(float(line.split("signal:")[1].split()[0]))
            except (ValueError, IndexError):
                pass
        elif "DS Parameter set: channel" in line:
            try:
                channel = int(line.split("channel")[-1].strip())
            except ValueError:
                pass
        elif "freq:" in line and channel == 0:
            m = re.search(r"freq:\s*(\d+)", line)
            if m:
                channel = _freq_to_channel(int(m.group(1)))
    if bssid and scope_mod.is_valid_bssid(bssid):
        out.append(ScanResult(ssid or "(hidden)", bssid, channel, rssi, "iw"))
    return out


def _freq_to_channel(freq_mhz: int) -> int:
    if 2412 <= freq_mhz <= 2484:
        return (freq_mhz - 2407) // 5
    if 5170 <= freq_mhz <= 5825:
        return (freq_mhz - 5000) // 5
    return 0


def _scan_macos_system_profiler() -> list[ScanResult]:
    try:
        proc = subprocess.run(
            ["system_profiler", "SPAirPortDataType"],
            capture_output=True,
            text=True,
            timeout=18.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0 or not proc.stdout:
        return []
    return _parse_macos_profiler(proc.stdout)


def _parse_macos_profiler(text: str) -> list[ScanResult]:
    out: list[ScanResult] = []
    in_other = False
    ssid: str | None = None
    channel = 0
    rssi = -75

    def flush() -> None:
        nonlocal ssid, channel, rssi
        if ssid and ssid.strip():
            name = ssid.strip()
            if name.startswith("<") and name.endswith(">"):
                name = f"NET_{len(out) + 1}"
            out.append(_macos_network(name, channel, rssi))
        ssid = None
        channel = 0
        rssi = -75

    for raw in text.splitlines():
        if "Other Local Wi-Fi Networks:" in raw:
            in_other = True
            continue
        if not in_other:
            continue
        if re.match(r"^ {8}\S[\w.-]*:$", raw) and not raw.startswith("            "):
            flush()
            in_other = False
            continue
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.endswith(":") and not any(
            key in stripped
            for key in ("PHY", "Channel", "Network Type", "Security", "Signal", "Country")
        ):
            flush()
            ssid = stripped[:-1]
            continue
        if ssid is None:
            continue
        m = _CHANNEL_RE.search(stripped)
        if m:
            channel = int(m.group(1))
        m = _SIGNAL_RE.search(stripped)
        if m:
            rssi = int(m.group(1))
    flush()
    return out


def _macos_network(ssid: str, channel: int, rssi: int, *, source: str = "system_profiler") -> ScanResult:
    digest = hashlib.sha256(ssid.encode("utf-8")).digest()
    bssid = "02:" + ":".join(f"{b:02X}" for b in digest[:5])
    return ScanResult(
        ssid=ssid,
        bssid=bssid,
        channel=channel,
        rssi=rssi,
        source=source,
        synthetic_bssid=True,
    )
