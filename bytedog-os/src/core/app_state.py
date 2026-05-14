"""Shared runtime constants (screen ids, modes)."""

from __future__ import annotations

from typing import Literal

# Modes used by ``ByteDogApp`` today (SQLite + scenes unchanged).
ScreenMode = Literal["launcher", "settings", "shutdown"]
