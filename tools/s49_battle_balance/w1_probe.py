#!/usr/bin/env python3
"""W1 (wave 11): a line-safe client for the headless mGBA probe.

Why not ``tools/s49_victory_capture/probe.py``
---------------------------------------------
That client spawns **one reader thread per line** and joins it with a long
timeout.  When a long ``frames`` command is followed by more commands, the
per-line threads can consume the sentinel out of order; the client then waits
for output that never comes and the run stalls for the whole timeout.  The
symptom is a probe that burns almost no CPU and stops making progress.

This client uses **one** background reader thread that pushes every line into
a queue.  Nothing is ever lost, nothing is read out of order, and a stalled
probe surfaces as a timeout instead of a silent hang.

Key masks (GBA / mGBA ``C.GBA_KEY.*``)::

    A=0x001 B=0x002 SELECT=0x004 START=0x008
    RIGHT=0x010 LEFT=0x020 UP=0x040 DOWN=0x080
    R=0x100 L=0x200
"""

from __future__ import annotations

import pathlib
import queue
import subprocess
import threading
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_EXE = REPO / "build" / "mgba-probe-w1" / "mgba-probe.exe"

KEYS = {
    "A": 0x001,
    "B": 0x002,
    "Select": 0x004,
    "Start": 0x008,
    "Right": 0x010,
    "Left": 0x020,
    "Up": 0x040,
    "Down": 0x080,
    "R": 0x100,
    "L": 0x200,
}


class ProbeError(RuntimeError):
    """The probe reported an error or stopped answering."""


class Probe:
    """A live probe process driven over its stdin/stdout command channel."""

    def __init__(self, rom: str | pathlib.Path,
                 exe: str | pathlib.Path = DEFAULT_EXE,
                 timeout: float = 900.0) -> None:
        self.rom = str(rom)
        self.exe = str(exe)
        self.timeout = timeout
        self._counter = 0
        self._proc: subprocess.Popen | None = None
        self._stderr: list[str] = []
        self._lines: queue.Queue[str | None] = queue.Queue()
        self._reader: threading.Thread | None = None
        # Every command that was sent to the probe.  The battle driver writes
        # the count of the ``poke`` commands into its receipt, so the receipt
        # can prove that the outcome was **not** poked into the ROM.
        self.commands: list[str] = []

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        if self._proc is not None:
            return
        exe = pathlib.Path(self.exe)
        if not exe.exists():
            raise ProbeError(f"{exe} missing; run: python tools/mgba_probe/build.py")
        self._proc = subprocess.Popen(
            [self.exe, self.rom],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        self._reader = threading.Thread(target=self._drain, daemon=True)
        self._reader.start()
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        banner = self._read_line()
        if banner is None or banner.strip() != "READY":
            self._stderr.append(f"banner: {banner!r}")

    def _drain(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        for line in self._proc.stdout:
            self._lines.put(line.rstrip("\r\n"))
        self._lines.put(None)

    def _drain_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        for line in self._proc.stderr:
            self._stderr.append(line.rstrip("\r\n"))

    def _read_line(self) -> str | None:
        try:
            return self._lines.get(timeout=self.timeout)
        except queue.Empty as error:
            raise ProbeError("probe timed out waiting for output") from error

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.stdin is not None:
                self._proc.stdin.write("quit\n")
                self._proc.stdin.flush()
                self._proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        try:
            self._proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait(timeout=10)
        self._proc = None

    def __enter__(self) -> "Probe":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def stderr(self) -> list[str]:
        return list(self._stderr)

    # --------------------------------------------------------------- verbs
    def run(self, command: str) -> list[str]:
        """Run one probe command and return its output lines."""
        if self._proc is None:
            raise ProbeError("probe is not running")
        self._counter += 1
        sentinel = f"___W1_PROBE_END_{self._counter}___"
        stdin = self._proc.stdin
        if stdin is None:
            raise ProbeError("probe stdin is gone")
        self.commands.append(command)
        try:
            stdin.write(f"{command}\n")
            stdin.write(f"echo {sentinel}\n")
            stdin.flush()
        except (BrokenPipeError, OSError) as error:
            raise ProbeError(f"{command} -> pipe broken ({error})") from error
        output: list[str] = []
        while True:
            line = self._read_line()
            if line is None:
                raise ProbeError(f"{command} -> probe closed its stdout")
            if line == sentinel:
                break
            output.append(line)
        if any(line.startswith("ERR") for line in output):
            raise ProbeError(f"{command} -> {output}")
        return output

    def load(self, state_path: str | pathlib.Path) -> list[str]:
        return self.run(f"load {state_path}")

    def save(self, state_path: str | pathlib.Path) -> list[str]:
        return self.run(f"save {state_path}")

    def shot(self, image_path: str | pathlib.Path) -> list[str]:
        return self.run(f"shot {image_path}")

    def frames(self, count: int, mask: int = 0) -> list[str]:
        return self.run(f"frames {count} 0x{mask:08X}")

    def dump(self, addr: int, length: int) -> bytes:
        lines = self.run(f"dump 0x{addr:08X} {length}")
        hex_text = "".join(line for line in lines
                           if not line.startswith("DUMP") and line != "ENDDUMP")
        return bytes.fromhex(hex_text)


def key_mask(names: list[str]) -> int:
    """Translate key names into a GBA key mask."""
    mask = 0
    for name in names:
        if name not in KEYS:
            raise KeyError(f"unknown key {name!r}")
        mask |= KEYS[name]
    return mask
