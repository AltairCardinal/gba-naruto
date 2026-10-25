#!/usr/bin/env python3
"""Drive the headless mGBA probe for the S49 audio-event probe.

The probe (tools/mgba_probe/host_main.c) is a stdin/stdout REPL.  This module
wraps it with the same sentinel discipline probe_client.py uses, but keeps the
per-frame binary dumps on disk so that a capture can be replayed and diffed
later without re-running the emulator.

Everything here is deterministic: same ROM + same savestate + same command
list => byte-identical dump files.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import queue
import subprocess
import threading
import time

REPO = pathlib.Path(__file__).resolve().parents[2]

# GBA KEYINPUT bit layout (host_main.c documents the same mapping).
KEY_A = 0x001
KEY_B = 0x002
KEY_SELECT = 0x004
KEY_START = 0x008
KEY_RIGHT = 0x010
KEY_LEFT = 0x020
KEY_UP = 0x040
KEY_DOWN = 0x080
KEY_R = 0x100
KEY_L = 0x200

KEY_NAMES = {
    "A": KEY_A,
    "B": KEY_B,
    "Select": KEY_SELECT,
    "Start": KEY_START,
    "Right": KEY_RIGHT,
    "Left": KEY_LEFT,
    "Up": KEY_UP,
    "Down": KEY_DOWN,
    "R": KEY_R,
    "L": KEY_L,
}


def probe_exe() -> pathlib.Path:
    """Isolated probe build, falling back to the shared one.

    The shared build/mgba-probe/mgba-probe.exe may be held open by another
    worker, so stream J builds its own copy via KONOHA_PROBE_OUT.
    """
    out = os.environ.get("KONOHA_PROBE_OUT")
    candidates = []
    if out:
        candidates.append(pathlib.Path(out) / "mgba-probe.exe")
    candidates.append(REPO / "build" / "mgba-probe-j" / "mgba-probe.exe")
    candidates.append(REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit(
        "ERR mgba-probe.exe not found; build it with:\n"
        "  $env:KONOHA_PROBE_OUT='%s'; python tools/mgba_probe/build.py"
        % (REPO / "build" / "mgba-probe-j")
    )


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Probe:
    """One probe process; commands are issued one at a time."""

    def __init__(self, rom: pathlib.Path, *, bios: pathlib.Path | None = None,
                 exe: pathlib.Path | None = None, timeout: float = 1800.0,
                 cwd: pathlib.Path | None = None):
        self.rom = pathlib.Path(rom)
        self.bios = pathlib.Path(bios) if bios else None
        self.exe = pathlib.Path(exe) if exe else probe_exe()
        self.timeout = timeout
        # The probe writes its per-frame dumps relative to its own working
        # directory, so the caller decides where the capture lands.
        self.cwd = pathlib.Path(cwd) if cwd else None
        self.command = [str(self.exe), str(self.rom)]
        if self.bios:
            self.command += ["--bios", str(self.bios)]
        self.proc: subprocess.Popen | None = None
        self._stderr: list[str] = []
        self._steps: list[dict] = []
        self._deadline = time.monotonic() + timeout

    def __enter__(self) -> "Probe":
        self.proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            cwd=str(self.cwd) if self.cwd else None,
        )
        thread = threading.Thread(target=self._drain_stderr, daemon=True)
        thread.start()
        self._read_line()  # banner
        return self

    def __exit__(self, *exc) -> None:
        if self.proc is None:
            return
        try:
            self.proc.stdin.write("quit\n")
            self.proc.stdin.flush()
        except Exception:
            pass
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=20)

    def _drain_stderr(self) -> None:
        assert self.proc is not None and self.proc.stderr is not None
        for line in self.proc.stderr:
            self._stderr.append(line.rstrip("\r\n"))

    def _read_line(self) -> str | None:
        assert self.proc is not None and self.proc.stdout is not None
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("probe timed out")
        result: queue.Queue = queue.Queue()
        reader = threading.Thread(
            target=lambda: result.put(self.proc.stdout.readline()), daemon=True)
        reader.start()
        reader.join(remaining)
        if reader.is_alive():
            raise TimeoutError("probe timed out")
        line = result.get()
        return line if line else None

    def run(self, command: str) -> list[str]:
        assert self.proc is not None
        sentinel = f"___PROBE_END_{len(self._steps)}___"
        self.proc.stdin.write(f"{command}\n")
        self.proc.stdin.write(f"echo {sentinel}\n")
        self.proc.stdin.flush()
        output: list[str] = []
        while True:
            line = self._read_line()
            if line is None:
                break
            line = line.rstrip("\r\n")
            if line == sentinel:
                break
            output.append(line)
        status = "error" if any(line.startswith("ERR") for line in output) else "ok"
        self._steps.append({"command": command, "status": status, "output": output})
        if status == "error":
            raise RuntimeError(f"probe command failed: {command}\n" + "\n".join(output))
        return output

    @property
    def steps(self) -> list[dict]:
        return self._steps

    @property
    def stderr(self) -> list[str]:
        return self._stderr


def keyseq_command(hold: int, gap: int, count: int, addr: int, length: int,
                   keymask: int, prefix: str) -> str:
    """`keyseq` dumps `length` bytes after every frame of the press/release run."""
    return (f"keyseq {hold} {gap} {count} 0x{addr:08X} {length} "
            f"0x{keymask:08X} {prefix}")


def framedump_command(count: int, addr: int, length: int, keymask: int,
                      prefix: str) -> str:
    return (f"framedump {count} 0x{addr:08X} {length} "
            f"0x{keymask:08X} {prefix}")


def read_dump_series(directory: pathlib.Path, prefix: str) -> list[bytes]:
    """Read <prefix>-NNNN.bin files in index order."""
    files = sorted(directory.glob(f"{prefix}-*.bin"))
    series = []
    for path in files:
        series.append(path.read_bytes())
    # sanity: indices must be dense
    expected = [f"{prefix}-{index:04d}.bin" for index in range(len(files))]
    actual = [path.name for path in files]
    if expected != actual:
        raise RuntimeError(f"dump series {prefix} is not dense: {actual[:4]}...")
    return series


def write_json(path: pathlib.Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
