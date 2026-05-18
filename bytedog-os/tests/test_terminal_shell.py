"""Terminal line-buffer tests (PTY output quirks)."""

from __future__ import annotations

from pathlib import Path

from src.services.terminal_shell import EmbeddedTerminal


def test_crlf_ls_output_not_wiped() -> None:
    term = EmbeddedTerminal(cwd=Path("."))
    term._append("total 64\r\n")
    term._append("drwxr-xr-x  1 user  staff  64 May 18 12:00 .\r\n")
    lines = term._all_lines()
    assert lines == ["total 64", "drwxr-xr-x  1 user  staff  64 May 18 12:00 ."]


def test_bare_cr_redraws_line() -> None:
    term = EmbeddedTerminal(cwd=Path("."))
    term._append("old\rnew\n")
    assert term._all_lines() == ["new"]


def test_split_crlf_across_chunks() -> None:
    term = EmbeddedTerminal(cwd=Path("."))
    term._append("line\r")
    term._append("\n")
    assert term._all_lines() == ["line"]
