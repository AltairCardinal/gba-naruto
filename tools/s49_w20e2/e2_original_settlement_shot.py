#!/usr/bin/env python3
"""Replay the **original** ROM from the reverse line's savestates and capture
the settlement screen.

Why this tool exists
--------------------
The wave-20 E2 task asks for the original's 「戰鬥分」 values (the settlement
screen's second row).  The reverse line keeps mGBA savestates (``.ss9``) that
sit **on** the original's settlement screen, and the original ROM is in the
repo (``rom/base.gba``).  The headless probe can load a savestate and take a
screenshot, so the original's own settlement screen is directly observable
instead of being guessed.

This tool answers one question per checkpoint:

    *What does the original's settlement screen show at this checkpoint?*

Usage::

    python tools/s49_w20e2/e2_original_settlement_shot.py \
        --probe build/w20-e2/probe/mgba-probe.exe \
        --rom rom/base.gba \
        --out build/w20-e2/original-shots \
        scenario-41-result.ss9 scenario-46-victory-reward.ss9
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "s49_battle_balance"))

import w1_probe  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=pathlib.Path, required=True)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("states", nargs="+")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    checkpoints = pathlib.Path(
        r"D:\Shell\Github\gba-naruto-reverse\artifacts\runtime-checkpoints")

    with w1_probe.Probe(args.rom, exe=args.probe) as probe:
        for state in args.states:
            path = pathlib.Path(state)
            if not path.is_absolute():
                path = checkpoints / state
            if not path.exists():
                print(f"SKIP  {state}: missing")
                continue
            try:
                probe.load(path)
                probe.frames(args.frames, 0)
                shot = args.out / (path.stem + ".png")
                probe.shot(shot)
                print(f"OK    {state} -> {shot}")
            except Exception as error:  # noqa: BLE001
                print(f"FAIL  {state}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
