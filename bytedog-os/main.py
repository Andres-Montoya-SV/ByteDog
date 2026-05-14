#!/usr/bin/env python3
"""ByteDog OS entry point."""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_path() -> Path:
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def main() -> None:
    _bootstrap_path()
    from src.app import run_app

    run_app()


if __name__ == "__main__":
    main()
