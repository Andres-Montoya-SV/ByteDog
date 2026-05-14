"""Best-effort battery percent for status chrome (Linux / Pi)."""

from __future__ import annotations

from pathlib import Path


def read_battery_percent() -> int | None:
    """Return 0–100 if a power supply reports capacity, else None (e.g. desktop)."""
    base = Path("/sys/class/power_supply")
    if not base.is_dir():
        return None
    for supply in sorted(base.iterdir()):
        t = supply / "type"
        if t.is_file() and t.read_text().strip().lower() != "battery":
            continue
        cap = supply / "capacity"
        if not cap.is_file():
            continue
        try:
            return max(0, min(100, int(cap.read_text().strip())))
        except ValueError:
            continue
    return None
