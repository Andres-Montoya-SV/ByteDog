"""SQLite persistence for ByteDog OS."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    db_path: Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_database(db_path: Path) -> None:
    """Create parent folders, database file, schema, and default row if empty."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pet_state (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                mood TEXT NOT NULL,
                level INTEGER NOT NULL,
                xp INTEGER NOT NULL,
                hunger INTEGER NOT NULL,
                energy INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur = conn.execute("SELECT COUNT(*) FROM pet_state")
        count = int(cur.fetchone()[0])
        if count == 0:
            conn.execute(
                """
                INSERT INTO pet_state (id, name, mood, level, xp, hunger, energy, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("Chicha", "happy", 1, 0, 50, 80, utc_now_iso()),
            )
        conn.commit()


@contextmanager
def connect(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def fetch_pet_row(db_path: Path) -> Optional[sqlite3.Row]:
    ensure_database(db_path)
    with connect(db_path) as conn:
        cur = conn.execute(
            "SELECT id, name, mood, level, xp, hunger, energy, updated_at FROM pet_state WHERE id = 1"
        )
        return cur.fetchone()
