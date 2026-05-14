"""Lightweight system information using the standard library."""

from __future__ import annotations

import os
import platform
import time
from pathlib import Path
from typing import Any


def _read_linux_meminfo() -> dict[str, int]:
    data: dict[str, int] = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if ":" not in line:
                    continue
                key, rest = line.split(":", 1)
                parts = rest.strip().split()
                if parts and parts[0].isdigit():
                    data[key.strip()] = int(parts[0])  # kB
    except (OSError, ValueError):
        pass
    return data


def get_system_status() -> dict[str, Any]:
    """Return a fresh snapshot (uncached). Prefer SystemStatusCache on the hot path."""
    status: dict[str, Any] = {
        "hostname": platform.node() or "unknown",
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count() or 0,
    }

    if platform.system() == "Linux":
        mem = _read_linux_meminfo()
        total = mem.get("MemTotal", 0)
        avail = mem.get("MemAvailable", mem.get("MemFree", 0))
        if total > 0 and avail >= 0:
            used_pct = int(100 * (1 - (avail / total)))
            status["memory_linux_percent_used"] = max(0, min(100, used_pct))
            status["memory_linux_mb_total"] = total // 1024

    status["cwd"] = str(Path.cwd())
    return status


class SystemStatusCache:
    """Recompute `/proc` + platform info at most once per interval (default 1s)."""

    def __init__(self, interval_sec: float = 1.0) -> None:
        self._interval = max(0.25, float(interval_sec))
        self._snapshot: dict[str, Any] = {}
        self._last_refresh: float = 0.0

    def get(self) -> dict[str, Any]:
        now = time.monotonic()
        if not self._snapshot or (now - self._last_refresh) >= self._interval:
            self._snapshot = get_system_status()
            self._last_refresh = now
        return self._snapshot

    def force_refresh(self) -> dict[str, Any]:
        self._snapshot = get_system_status()
        self._last_refresh = time.monotonic()
        return self._snapshot
