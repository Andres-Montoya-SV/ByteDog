#!/usr/bin/env python3
"""Offline checks for Phase 2 foundation (no hardware, no long-running app).

Requires project dependencies (``pip install -r requirements.txt``), especially pygame.

Sets ``SDL_VIDEODRIVER=dummy`` (and dummy audio) **before** importing pygame-dependent
modules so this can run on machines without a display.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _fail(msg: str) -> None:
    print("FAIL:", msg, file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))

    cfg = ROOT / "config"
    for name in ("app.json", "input.json", "pet.json", "ui.json"):
        if not (cfg / name).is_file():
            _fail(f"missing {cfg / name}")

    for rel in ("assets", "assets/chicha", "assets/images", "data"):
        if not (ROOT / rel).is_dir():
            _fail(f"missing directory {ROOT / rel}")

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    importlib.import_module("src.app")

    from src.config.loader import load_merged_config

    merged = load_merged_config(ROOT)
    if not isinstance(merged, dict) or "fps" not in merged:
        _fail("merged config invalid")

    from src.services.input import InputAction, InputService

    assert InputAction.CONFIRM is not None
    svc = InputService(merged.get("input") or {}, {})
    list(svc.poll_navigation())

    from src.storage.database import ensure_database

    db = ROOT / "data" / "_validate_phase2.db"
    ensure_database(db)
    if not db.is_file():
        _fail("database init did not create file")
    try:
        db.unlink()
    except OSError:
        pass

    import pygame

    pygame.init()
    try:
        from src.pet.animations import ChichaAnimator, ChichaVisuals

        anim = ChichaAnimator(ChichaVisuals(images={}))
        surf = pygame.Surface((64, 48))
        anim.draw(surf, surf.get_rect(), fast_scale=True, now_s=0.0)
    finally:
        pygame.quit()

    print("OK: Phase 2 foundation validation passed.")


if __name__ == "__main__":
    main()
