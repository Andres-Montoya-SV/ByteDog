#!/usr/bin/env python3
"""Backward-compatible entry: runs ``validate_phase2`` checks."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
phase2 = ROOT / "tools" / "validate_phase2.py"
spec = importlib.util.spec_from_file_location("validate_phase2", phase2)
if spec is None or spec.loader is None:
    print("FAIL: could not load validate_phase2.py", file=sys.stderr)
    raise SystemExit(1)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.main()
