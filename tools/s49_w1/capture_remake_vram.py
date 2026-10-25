#!/usr/bin/env python3
"""Dump the remake's VRAM at every step of a battle walk.

The per-cell family comparison (``tools/s49_overlay_align/compare_overlay_families.py``)
needs the remake's overlay BG map.  That map lives in VRAM, and the walk
capture only produces PNG screenshots and savestates, so this script replays
each saved state in the headless mGBA probe and reads VRAM out of the bus.

It is the remake-side twin of ``tools/s49_rule_probe/capture_original.py``:
same shape (``load <state>`` then ``framedump 1``), same region, same
one-frame-advance convention, so the two sides stay comparable.

Usage::

    python tools/s49_w1/capture_remake_vram.py \
        --capture-dir build/s49-report/w1-after/capture-remake \
        --out-dir build/s49-w1/vram-after

The walk capture itself comes from ``tools/s49_fidelity_report.py``:

    python tools/s49_fidelity_report.py \
        --out build/s49-report/report-w1-after.json \
        --work-dir build/s49-report/w1-after
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

# The whole of VRAM.  The probe's `dump` command takes a decimal address,
# `framedump` takes a hex literal.
VRAM_ADDR = 0x06000000
VRAM_LEN = 0x18000


def run_probe(exe: pathlib.Path, rom: pathlib.Path, commands: list[str],
              out: pathlib.Path, timeout: float = 900.0) -> dict:
    argv = [sys.executable, str(PROBE_CLIENT), "--exe", str(exe),
            "--rom", str(rom)]
    for command in commands:
        argv += ["--cmd", command]
    argv += ["--out", str(out)]
    proc = subprocess.run(argv, capture_output=True, text=True,
                          timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"probe failed: {proc.stderr[:2000]}")
    return json.loads(out.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--capture-dir", type=pathlib.Path, required=True,
                    help="the walk capture directory (it holds the .ss9 files)")
    ap.add_argument("--out-dir", type=pathlib.Path, required=True)
    ap.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    ap.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    args = ap.parse_args()

    states = sorted(args.capture_dir.glob("step-*.ss9"))
    if not states:
        print(f"ERR no savestates under {args.capture_dir}")
        return 2
    args.out_dir.mkdir(parents=True, exist_ok=True)

    commands: list[str] = []
    prefixes: list[str] = []
    for state in states:
        prefix = args.out_dir / (state.stem + ".vram")
        prefixes.append(prefix.name)
        commands.append(f"load {state}")
        commands.append(
            f"framedump 1 0x{VRAM_ADDR:08X} {VRAM_LEN} 0x000 {prefix}")

    print(f"dumping VRAM for {len(states)} states ...")
    document = run_probe(args.exe, args.rom, commands,
                         args.out_dir / "probe.json")
    bad = [step for step in document["steps"] if step["status"] != "ok"]
    if bad:
        print(f"ERR probe step failed: {bad[0]['command']}: {bad[0]['output']}")
        return 1

    dumps = sorted(args.out_dir.glob("*.vram-*.bin"))
    print(f"wrote {len(dumps)} VRAM dumps to {args.out_dir}")
    if len(dumps) != len(states):
        print(f"ERR expected {len(states)} dumps, got {len(dumps)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
