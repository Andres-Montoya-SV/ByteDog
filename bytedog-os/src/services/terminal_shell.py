"""Embedded interactive shell (PTY) for the in-app Terminal screen."""

from __future__ import annotations

import errno
import fcntl
import os
import platform
import pty
import struct
import subprocess
import termios
from dataclasses import dataclass, field
from pathlib import Path

from src.services.ansi_filter import strip_ansi


_MAX_BUFFER_CHARS = 120_000


@dataclass(slots=True)
class EmbeddedTerminal:
    """Runs the user's shell inside a pseudo-terminal (Unix/macOS/Pi)."""

    cwd: Path
    buffer: str = ""
    scroll_back_lines: int = 0
    alive: bool = True
    shell_name: str = ""
    _lines: list[str] = field(default_factory=list)
    _current_line: str = ""
    _deferred_cr: bool = False
    _master_fd: int = -1
    _proc: subprocess.Popen[bytes] | None = None
    _cols: int = 80
    _rows: int = 24
    _resize_cols: int = 0
    _resize_rows: int = 0

    @classmethod
    def start(cls, cwd: Path, *, cols: int = 80, rows: int = 24) -> EmbeddedTerminal:
        term = cls(cwd=cwd.resolve())
        term._cols = max(20, cols)
        term._rows = max(8, rows)
        shell = os.environ.get("SHELL") or ("/bin/bash" if platform.system() != "Windows" else "cmd.exe")
        term.shell_name = Path(shell).name
        if platform.system() == "Windows":
            term._start_windows(cwd, shell)
        else:
            term._start_unix_pty(cwd, shell)
        term._push_line(f"[ByteDog Terminal] {term.cwd} · {term.shell_name}")
        term._push_line("Type commands below. Esc or gamepad Back = exit.")
        term._push_line("")
        return term

    def _start_unix_pty(self, cwd: Path, shell: str) -> None:
        master_fd, slave_fd = pty.openpty()
        winsize = struct.pack("HHHH", self._rows, self._cols, 0, 0)
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)
        env = os.environ.copy()
        # Plain TERM keeps zsh/bash from emitting heavy color / bracketed-paste codes.
        env["TERM"] = "dumb"
        env["NO_COLOR"] = "1"
        env["CLICOLOR"] = "0"
        env["PWD"] = str(cwd)
        self._proc = subprocess.Popen(
            [shell, "-l"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=str(cwd),
            env=env,
            preexec_fn=os.setsid,
            close_fds=True,
        )
        os.close(slave_fd)
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self._master_fd = master_fd

    def _start_windows(self, cwd: Path, shell: str) -> None:
        self._proc = subprocess.Popen(
            [shell],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(cwd),
            text=False,
            bufsize=0,
        )
        self._master_fd = -1

    def resize(self, cols: int, rows: int) -> None:
        cols = max(20, cols)
        rows = max(8, rows)
        if cols == self._resize_cols and rows == self._resize_rows:
            return
        self._cols = cols
        self._rows = rows
        self._resize_cols = cols
        self._resize_rows = rows
        if self._master_fd < 0:
            return
        try:
            winsize = struct.pack("HHHH", self._rows, self._cols, 0, 0)
            fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)
        except OSError:
            pass

    def poll(self) -> None:
        """Read any pending shell output (non-blocking)."""
        if self._proc is None:
            return
        if self._proc.poll() is not None:
            self.alive = False
            code = self._proc.returncode
            self._append(f"\n[process exited {code}]\n")
            return
        if self._master_fd >= 0:
            self._read_master_fd()
        elif self._proc.stdout is not None:
            self._read_pipes()

    def _read_master_fd(self) -> None:
        while True:
            try:
                chunk = os.read(self._master_fd, 4096)
            except OSError as exc:
                if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    break
                self._append(f"\n[read error: {exc}]\n")
                break
            if not chunk:
                break
            self._append(chunk.decode("utf-8", errors="replace"))

    def _read_pipes(self) -> None:
        assert self._proc and self._proc.stdout
        try:
            chunk = self._proc.stdout.read(4096)
        except (OSError, ValueError):
            return
        if chunk:
            self._append(chunk.decode("utf-8", errors="replace"))

    def send_bytes(self, data: bytes) -> None:
        if not self.alive:
            return
        if self._master_fd >= 0:
            try:
                os.write(self._master_fd, data)
            except OSError as exc:
                self._append(f"\n[write error: {exc}]\n")
        elif self._proc and self._proc.stdin:
            try:
                self._proc.stdin.write(data)
                self._proc.stdin.flush()
            except (OSError, ValueError) as exc:
                self._append(f"\n[write error: {exc}]\n")

    def send_text(self, text: str) -> None:
        if text:
            self.send_bytes(text.encode("utf-8", errors="replace"))

    def send_key(self, key: int, *, mod: int = 0) -> bool:
        """Map pygame keys to terminal bytes. Return True if handled."""
        if key == 13:  # enter
            self.send_bytes(b"\n")
            return True
        if key == 8 or key == 127:  # backspace
            self.send_bytes(b"\x7f")
            return True
        if key == 9:  # tab
            self.send_bytes(b"\t")
            return True
        if key == 27:  # escape — let shell handle arrows if prefixed
            return False
        if key == 1073741906:  # up
            self.send_bytes(b"\x1b[A")
            return True
        if key == 1073741905:  # down
            self.send_bytes(b"\x1b[B")
            return True
        if key == 1073741903:  # right
            self.send_bytes(b"\x1b[C")
            return True
        if key == 1073741904:  # left
            self.send_bytes(b"\x1b[D")
            return True
        if key == 99 and (mod & 192):  # ctrl+c
            self.send_bytes(b"\x03")
            return True
        if key == 108 and (mod & 192):  # ctrl+l
            self.send_bytes(b"\x0c")
            return True
        if key == 100 and (mod & 192):  # ctrl+d
            self.send_bytes(b"\x04")
            return True
        return False

    def scroll_up(self, lines: int = 1) -> None:
        self.scroll_back_lines = min(
            self.scroll_back_lines + max(1, lines),
            max(0, self._line_count() - 1),
        )

    def scroll_down(self, lines: int = 1) -> None:
        self.scroll_back_lines = max(0, self.scroll_back_lines - max(1, lines))

    def scroll_page_up(self, page_lines: int) -> None:
        self.scroll_up(page_lines)

    def scroll_page_down(self, page_lines: int) -> None:
        self.scroll_down(page_lines)

    def visible_text(self, max_lines: int, *, wrap_cols: int | None = None) -> list[str]:
        all_lines = self._all_lines()
        if wrap_cols and wrap_cols > 0:
            all_lines = self._wrap_lines(all_lines, wrap_cols)
        if not all_lines:
            return [""]
        end = max(1, len(all_lines) - self.scroll_back_lines)
        start = max(0, end - max_lines)
        return all_lines[start:end]

    @staticmethod
    def _wrap_lines(lines: list[str], cols: int) -> list[str]:
        wrapped: list[str] = []
        for line in lines:
            if not line:
                wrapped.append("")
                continue
            for i in range(0, len(line), cols):
                wrapped.append(line[i : i + cols])
        return wrapped

    def _all_lines(self) -> list[str]:
        if self._current_line:
            return self._lines + [self._current_line]
        return list(self._lines)

    def _line_count(self) -> int:
        return max(1, len(self._all_lines()))

    def _push_line(self, line: str) -> None:
        self._lines.append(line)
        self._sync_buffer()

    def _sync_buffer(self) -> None:
        self.buffer = "\n".join(self._all_lines())
        if len(self.buffer) > _MAX_BUFFER_CHARS:
            while len(self.buffer) > _MAX_BUFFER_CHARS and self._lines:
                self._lines.pop(0)
            self.buffer = "\n".join(self._all_lines())

    def _append(self, text: str) -> None:
        cleaned = strip_ansi(text)
        had_output = bool(cleaned)
        i = 0
        while i < len(cleaned):
            if self._deferred_cr:
                self._deferred_cr = False
                ch = cleaned[i]
                if ch == "\n":
                    self._lines.append(self._current_line)
                    self._current_line = ""
                else:
                    self._current_line = ""
                    self._feed_char(ch)
                i += 1
                continue
            ch = cleaned[i]
            if ch == "\r":
                if i + 1 < len(cleaned) and cleaned[i + 1] == "\n":
                    self._lines.append(self._current_line)
                    self._current_line = ""
                    i += 2
                    continue
                if i + 1 >= len(cleaned):
                    self._deferred_cr = True
                    i += 1
                    continue
                self._current_line = ""
            else:
                self._feed_char(ch)
            i += 1
        if had_output:
            self.scroll_back_lines = 0
        self._sync_buffer()

    def _feed_char(self, ch: str) -> None:
        if ch == "\r":
            return
        if ch == "\n":
            self._lines.append(self._current_line.replace("\r", ""))
            self._current_line = ""
        elif ch == "\x08":
            self._current_line = self._current_line[:-1]
        elif ch == "\t":
            self._current_line += " " * (8 - len(self._current_line) % 8)
        else:
            self._current_line += ch

    def close(self) -> None:
        if self._proc is not None:
            try:
                if self._proc.poll() is None:
                    self._proc.terminate()
                    self._proc.wait(timeout=0.5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    self._proc.kill()
                except OSError:
                    pass
            self._proc = None
        if self._master_fd >= 0:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = -1
        self.alive = False
