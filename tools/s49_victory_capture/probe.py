#!/usr/bin/env python3
"""Interactive client for the headless mGBA probe used by stream K.

``tools/mgba_probe/probe_client.py`` runs a whole batch of commands and then
exits.  Stream K needs to *interleave* commands with game-state inspection
(the route is chosen from the live roster), so this client keeps the probe
process alive and exposes one method per probe verb.

Recording rules for this stream (fixed by the wave-2 brief):

* HLE BIOS -- do **not** pass ``--bios``; the baseline captures were taken
  with mGBA's built-in HLE BIOS.
* Reading I/O registers perturbs the emulation (VCOUNT has read side
  effects), so VRAM and I/O must never be dumped in the same run.

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
from typing import TextIO

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"

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
KEY_NAMES = {value: name for name, value in KEYS.items()}


class ProbeError(RuntimeError):
    """The probe reported an error for a command."""


class Probe:
    """A live probe process driven over its stdin/stdout command channel."""

    def __init__(self, rom: str | pathlib.Path,
                 exe: str | pathlib.Path = DEFAULT_EXE,
                 timeout: float = 600.0) -> None:
        self.rom = str(rom)
        self.exe = str(exe)
        self.timeout = timeout
        self._counter = 0
        self._proc: subprocess.Popen | None = None
        self._stderr: list[str] = []
        self._history: list[str] = []
        self._stdout_queue: queue.Queue[str | Exception | None] = queue.Queue(
            maxsize=1024)
        self._reader_stop = threading.Event()
        self._stdout_reader: threading.Thread | None = None
        self._stderr_reader: threading.Thread | None = None
        self._stdout_eof = False

    # ---------------------------------------------------------------- setup
    def start(self) -> None:
        if self._proc is not None:
            return
        if any(reader is not None and reader.is_alive()
               for reader in (self._stdout_reader, self._stderr_reader)):
            raise ProbeError("previous probe reader is still shutting down")
        exe = pathlib.Path(self.exe)
        if not exe.exists():
            raise ProbeError(f"{exe} missing; run: python tools/mgba_probe/build.py")
        self._proc = subprocess.Popen(
            [self.exe, self.rom],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
        )
        self._stdout_queue = queue.Queue(maxsize=1024)
        self._reader_stop = threading.Event()
        self._stdout_eof = False
        assert self._proc.stdout is not None and self._proc.stderr is not None
        self._stdout_reader = threading.Thread(
            target=self._drain_stdout,
            args=(self._proc.stdout, self._stdout_queue, self._reader_stop),
            name="mgba-probe-stdout", daemon=True)
        self._stderr_reader = threading.Thread(
            target=self._drain_stderr, args=(self._proc.stderr,),
            name="mgba-probe-stderr", daemon=True)
        try:
            self._stdout_reader.start()
            self._stderr_reader.start()
            banner = self._read_line()
            if banner is None or banner.strip() != "READY":
                self._stderr.append(f"banner: {banner!r}")
        except Exception:
            self.close()
            raise

    @staticmethod
    def _publish(result: queue.Queue[str | Exception | None],
                 stop: threading.Event, item: str | Exception | None) -> bool:
        while not stop.is_set():
            try:
                result.put(item, timeout=0.05)
                return True
            except queue.Full:
                continue
        return False

    @staticmethod
    def _drain_stdout(stream: TextIO,
                      result: queue.Queue[str | Exception | None],
                      stop: threading.Event) -> None:
        # Bind this process's stream/queue: a later start must not redirect an
        # old reader. Only the reader closes its stream, avoiding cross-thread
        # TextIOWrapper.close() blocking behind a pending readline().
        try:
            with stream:
                while not stop.is_set():
                    line = stream.readline()
                    if not line:
                        break
                    if not Probe._publish(result, stop, line):
                        return
        except Exception as error:
            Probe._publish(result, stop, error)
        finally:
            Probe._publish(result, stop, None)

    def _drain_stderr(self, stream: TextIO) -> None:
        try:
            with stream:
                for line in stream:
                    self._stderr.append(line.rstrip("\r\n"))
        except Exception as error:
            self._stderr.append(f"stderr reader failed: {error}")
            self._publish(self._stdout_queue, self._reader_stop, error)

    def _read_line(self) -> str | None:
        assert self._proc is not None and self._proc.stdout is not None
        if self._stdout_eof:
            return None
        try:
            line = self._stdout_queue.get(timeout=self.timeout)
        except queue.Empty as error:
            raise ProbeError("probe timed out") from error
        if isinstance(line, Exception):
            raise ProbeError(f"probe output reader failed: {line}") from line
        if line is None:
            self._stdout_eof = True
        return line

    def close(self) -> None:
        if self._proc is None:
            return
        proc = self._proc
        # Release a producer waiting on a full queue before waiting for the
        # child. Never close a pipe underneath a blocked reader from here.
        self._reader_stop.set()
        try:
            if self._proc.stdin is not None:
                self._proc.stdin.write("quit\n")
                self._proc.stdin.flush()
                self._proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        finally:
            if proc.stdin is not None and not proc.stdin.closed:
                try:
                    proc.stdin.close()
                except (BrokenPipeError, OSError):
                    pass
        try:
            self._proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait(timeout=10)
        self._proc = None
        for reader, stream in ((self._stdout_reader, proc.stdout),
                               (self._stderr_reader, proc.stderr)):
            if reader is not None and reader.ident is not None:
                reader.join(timeout=1)
            elif stream is not None:
                stream.close()

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
        sentinel = f"___K_PROBE_END_{self._counter}___"
        self._history.append(command)
        if len(self._history) > 40:
            del self._history[0]
        if self._proc.stdin is not None:
            try:
                self._proc.stdin.write(f"{command}\n")
                self._proc.stdin.write(f"echo {sentinel}\n")
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError) as error:
                raise ProbeError(
                    f"{command} -> pipe broken ({error}); "
                    f"probe exit={self._proc.poll()}; "
                    f"last commands: {self._history[-6:]}; "
                    f"probe stderr: {self._stderr[-6:]}") from error
        output: list[str] = []
        while True:
            line = self._read_line()
            if line is None:
                break
            line = line.rstrip("\r\n")
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

    def keyseq(self, hold: int, gap: int, count: int, addr: int, length: int,
               mask: int, prefix: str) -> list[str]:
        return self.run(
            f"keyseq {hold} {gap} {count} 0x{addr:08X} {length} "
            f"0x{mask:08X} {prefix}")

    def framedump(self, count: int, addr: int, length: int, mask: int,
                  prefix: str) -> list[str]:
        return self.run(
            f"framedump {count} 0x{addr:08X} {length} 0x{mask:08X} {prefix}")

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
