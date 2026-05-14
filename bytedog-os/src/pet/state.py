"""In-memory pet state loaded from SQLite."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sqlite3

from src.storage.database import ensure_database, fetch_pet_row


@dataclass(slots=True)
class PetState:
    name: str
    mood: str
    level: int
    xp: int
    hunger: int
    energy: int

    @classmethod
    def default_chicha(cls) -> PetState:
        return cls(
            name="Chicha",
            mood="happy",
            level=1,
            xp=0,
            hunger=50,
            energy=80,
        )

    @classmethod
    def from_db_path(cls, db_path: Path) -> PetState:
        try:
            ensure_database(db_path)
            row = fetch_pet_row(db_path)
            if row is None:
                return cls.default_chicha()
            return cls(
                name=str(row["name"]),
                mood=str(row["mood"]),
                level=int(row["level"]),
                xp=int(row["xp"]),
                hunger=int(row["hunger"]),
                energy=int(row["energy"]),
            )
        except (sqlite3.Error, OSError, ValueError, TypeError):
            return cls.default_chicha()

    def mood_key(self) -> str:
        """Normalize mood for asset lookup."""
        return self.mood.strip().lower()
