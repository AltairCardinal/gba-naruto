#!/usr/bin/env python3
"""Headless smoke test: run the remake ROM for N frames and report a crash.

The probe is mGBA without a window.  It prints a line for every illegal
instruction or invalid jump it sees, so a crash is visible in its stderr even
when the process itself keeps running.

The test does two runs:

* **boot** -- 4096 frames with no input.  This is the title screen (the
  Chinese title has to render), and it is the run that has to survive.
* **walk** -- the same input sequence the fidelity report uses
  (``Down,Down,A x32``), so the battle scene, the overlay and the unit
  sprites are actually executed.

Usage::

    python tools/s49_w1/smoke_4096.py --out build/s49-w1/smoke
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROBE_CLIENT = REPO / "tools" / "mgba_probe" / "probe_client.py"

DEFAULT_EXE = REPO / "build" / "mgba-probe-w1" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba")

CRASH_MARKERS = ("Jumped to invalid address", "Illegal opcode",
                 "Assertion failed", "BN_ERROR")

KEY_A = 0x001
KEY_DOWN = 0x010


def run_probe(exe: pathlib.Path, rom: pathlib.Path, commands: list[str],
              out: pathlib.Path) -> dict:
    argv = [sys.executable, str(PROBE_CLIENT), "--exe", str(exe),
            "--rom", str(rom)]
    for command in commands:
        argv += ["--cmd", command]
    argv += ["--out", str(out)]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=1800)
    document = json.loads(out.read_text(encoding="utf-8"))
    document["client_exit_code"] = proc.returncode
    return document


def crash_lines(document: dict) -> list[str]:
    return [line for line in document.get("stderr", [])
            if any(marker in line for marker in CRASH_MARKERS)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=pathlib.Path,
                    default=REPO / "build" / "s49-w1" / "smoke")
    ap.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    ap.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    ap.add_argument("--frames", type=int, default=4096)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    summary: dict = {"rom": str(args.rom), "runs": {}}
    failed = False

    boot = [f"frames {args.frames} 0x000",
            f"shot {args.out / 'boot-title.png'}"]
    document = run_probe(args.exe, args.rom, boot, args.out / "boot.json")
    crashes = crash_lines(document)
    summary["runs"]["boot"] = {
        "frames": args.frames,
        "probe_exit_code": document.get("exit_code"),
        "client_exit_code": document.get("client_exit_code"),
        "crash_lines": crashes,
        "stderr_lines": len(document.get("stderr", [])),
    }
    print(f"boot: {args.frames} frames, probe exit "
          f"{document.get('exit_code')}, {len(crashes)} crash lines")
    if crashes:
        failed = True

    # The walk the fidelity report uses: Down, Down, then A x32.
    commands = ["frames 240 0x000"]
    for mask in (KEY_DOWN, KEY_DOWN):
        commands.append(f"frames 4 0x{mask:03X}")
        commands.append("frames 90 0x000")
    for _ in range(32):
        commands.append(f"frames 4 0x{KEY_A:03X}")
        commands.append("frames 90 0x000")
    commands.append(f"shot {args.out / 'walk-last.png'}")
    document = run_probe(args.exe, args.rom, commands, args.out / "walk.json")
    crashes = crash_lines(document)
    summary["runs"]["walk"] = {
        "commands": len(commands),
        "probe_exit_code": document.get("exit_code"),
        "client_exit_code": document.get("client_exit_code"),
        "crash_lines": crashes,
        "stderr_lines": len(document.get("stderr", [])),
    }
    print(f"walk: probe exit {document.get('exit_code')}, "
          f"{len(crashes)} crash lines")
    if crashes:
        failed = True

    (args.out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    print(f"wrote {args.out / 'summary.json'}")
    if failed:
        print("FAIL: the probe reported a crash")
        return 1
    print("OK: no crash markers in either run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
