"""Strip / interpret terminal escape sequences for pygame text display."""

from __future__ import annotations

import re

# CSI … final byte (colors, cursor, erase, bracketed paste, etc.)
_CSI_RE = re.compile(r"\x1b\[[0-9:;<=>?]*[ -/]*[@-~]")
# OSC … BEL or ST
_OSC_RE = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)")
# Other single-char ESC sequences
_ESC_OTHER_RE = re.compile(r"\x1b[(@-Z\\=_]")
# Leftover stray CSI fragments (no ESC) — rare but cleans [?2004h leaks
_STRAY_CSI_RE = re.compile(r"\[[0-9:;<=>?]*[ -/]*[@-~]")


def strip_ansi(text: str) -> str:
    text = _OSC_RE.sub("", text)
    text = _CSI_RE.sub("", text)
    text = _ESC_OTHER_RE.sub("", text)
    text = _STRAY_CSI_RE.sub("", text)
    # Control chars except tab/newline/carriage return
    return "".join(
        ch for ch in text if ch in "\n\r\t" or (ord(ch) >= 32 and ord(ch) != 127)
    )


def apply_carriage_returns(text: str) -> str:
    """Turn \\r into \"overwrite current line\" (shell prompts)."""
    if "\r" not in text:
        return text
    out: list[str] = []
    for ch in text:
        if ch == "\r":
            if out and out[-1] == "\n":
                continue
            while out and out[-1] != "\n":
                out.pop()
            continue
        if ch == "\x08":  # backspace
            if out and out[-1] != "\n":
                out.pop()
            continue
        out.append(ch)
    return "".join(out)
