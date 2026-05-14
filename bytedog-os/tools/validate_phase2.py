#!/usr/bin/env python3
"""Phase 2 validation: configs, imports, pygame, audio, DB, Chicha modules (no Pi hardware)."""

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

    for rel in ("assets", "assets/chicha", "assets/images", "assets/sounds", "data"):
        if not (ROOT / rel).is_dir():
            _fail(f"missing directory {ROOT / rel}")

    cfg = ROOT / "config"
    for name in ("app.json", "input.json", "pet.json", "ui.json"):
        if not (cfg / name).is_file():
            _fail(f"missing {cfg / name}")

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

        anim = ChichaAnimator(ChichaVisuals.empty())
        surf = pygame.Surface((64, 48))
        anim.draw(surf, surf.get_rect(), fast_scale=True, now_s=0.0)

        from src.services.audio import AudioService

        audio = AudioService(ROOT / "assets" / "sounds")
        audio.initialize()
        _ = audio.mixer_ready
        audio.play_move()
        audio.play_chicha_react()
    finally:
        try:
            pygame.mixer.quit()
        except pygame.error:
            pass
        pygame.quit()

    print("OK: Phase 2 validation passed.")


if __name__ == "__main__":
    main()
