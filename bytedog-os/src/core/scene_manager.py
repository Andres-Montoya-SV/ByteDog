"""Scene identifiers for Phase 2 routing (launcher shell only today)."""

from __future__ import annotations

from enum import Enum


class SceneId(str, Enum):
    """Logical scenes; values match ``ByteDogApp`` ``_screen_mode`` strings."""

    LAUNCHER = "launcher"
    SETTINGS = "settings"
    SHUTDOWN = "shutdown"
