#!/usr/bin/env python3
"""Explore the original S49 battle-14 overlay and the battle cursor.

Stream K could not move its second unit because it guessed the landing cells
from coordinates.  This script reads the game's own overlay (BG2) instead, so
the legal cells can be read off the screen instead of guessed, and it records
how the overlay's logical cells relate to the game's battle coordinates.

For every key press it records

* the menu classification (pixel signature),
* the battle cursor (EWRAM 0x02026A78/79),
* the unit pool (EWRAM 0x020240C0),
* the HP array (EWRAM 0x020242A0),
* the BG2 overlay tilemap (VRAM 0x06001000) and its 16x16 logical family grid,
* a PNG frame.

Usage::

    python tools/s49_victory_capture/explore_overlay.py --out build/s49-victory-capture/explore1 \
        --walk "A*21"
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import battle as battle_module  # noqa: E402
import overlay as overlay_module  # noqa: E402
import probe as probe_module  # noqa: E402
import s49_state  # noqa: E402

_BUILD = pathlib.Path(__file__).resolve().parents[2] / "build"
DEFAULT_EXE = _BUILD / "mgba-probe-m" / "mgba-probe.exe"
if not DEFAULT_EXE.exists():
    DEFAULT_EXE = _BUILD / "mgba-probe" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")


def parse_walk(text: str) -> list[str]:
    """``"A*21,Right"`` -> ``["A", "A", ..., "Right"]``."""
    keys: list[str] = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "*" in chunk:
            name, count = chunk.split("*", 1)
            keys.extend([name.strip()] * int(count))
        else:
            keys.append(chunk)
    return keys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--exe", default=str(DEFAULT_EXE))
    parser.add_argument("--out", required=True)
    parser.add_argument("--walk", default="A*21")
    parser.add_argument("--settle", type=int, default=60)
    parser.add_argument("--shot", action="store_true",
                        help="write a PNG frame after every press")
    args = parser.parse_args(argv)

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    steps: list[dict] = []
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.load(args.state)
        battle = battle_module.Battle(probe, settle=args.settle,
                                      shot_dir=frames_dir,
                                      screen_path=out_dir / "screen.png")
        battle.capture_each = args.shot
        for index, key in enumerate(parse_walk(args.walk)):
            battle.press(key)
            over = overlay_module.read_overlay(probe)
            row = {
                "step": index,
                "key": key,
                "menu": battle.menu(),
                "cursor": list(battle.cursor()),
                "units": [(u["slot"], u["x"], u["y"], u["acting"], u["side"])
                          for u in battle.pool()],
                "hp": battle.hp(),
                "overlay": over.grid(),
                "lit": len(over.lit()),
                "hatch": over.cells_of("hatch"),
                "line_alt": over.cells_of("line_alt"),
                "band": over.cells_of("band"),
                "solid": over.cells_of("solid"),
                "hatch_shift": over.cells_of("hatch_shift"),
            }
            steps.append(row)
            print(f"[{index:02d}] {key:5s} menu={row['menu']:8s} "
                  f"cursor={row['cursor']} lit={row['lit']:3d} "
                  f"hatch={len(row['hatch']):3d} band={row['band']} "
                  f"units={[(u[0], u[1], u[2]) for u in row['units']]}")
        if args.shot:
            probe.shot(frames_dir / "final.png")

    (out_dir / "steps.json").write_text(
        json.dumps({"walk": args.walk, "steps": steps}, indent=1,
                   ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
