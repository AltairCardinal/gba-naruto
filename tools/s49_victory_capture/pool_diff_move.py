#!/usr/bin/env python3
"""Diff the unit pool around a move so the live position field is found.

The battle cursor moves and the unit visibly walks, but the pool's x/y at
+0xC4/+0xC5 does not change.  This script dumps the whole pool record of
every slot before and after a confirmed move and prints the changed byte
offsets, so the field that actually carries the position can be identified.

Usage::

    python tools/s49_victory_capture/pool_diff_move.py --out build/s49-victory-capture/pooldiff
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


def pool_bytes(probe) -> bytes:
    return probe.dump(s49_state.POOL_ADDRESS,
                      s49_state.POOL_STRIDE * 16)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--exe", default=str(DEFAULT_EXE))
    parser.add_argument("--out", required=True)
    parser.add_argument("--cell", default="9,6")
    parser.add_argument("--settle", type=int, default=60)
    args = parser.parse_args(argv)

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cell = tuple(int(v) for v in args.cell.split(","))

    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.load(args.state)
        battle = battle_module.Battle(probe, settle=args.settle,
                                      screen_path=out_dir / "screen.png")
        from explore_overlay import parse_walk
        for key in parse_walk("A*30"):
            battle.press(key)
            if len(overlay_module.read_overlay(probe).cells_of("hatch")) > 20:
                break
        print("cursor", battle.cursor(), "menu", battle.menu())
        before = pool_bytes(probe)
        (out_dir / "pool-before.bin").write_bytes(before)
        battle.set_cursor(*cell)
        print("cursor after move", battle.cursor())
        battle.press("A", settle=140, tag="move")
        probe.frames(400, 0)
        after = pool_bytes(probe)
        (out_dir / "pool-after.bin").write_bytes(after)
        battle.probe.shot(out_dir / "after.png")

    stride = s49_state.POOL_STRIDE
    changes: dict[str, list] = {}
    for slot in range(1, 16):
        start = slot * stride
        for offset in range(stride):
            if before[start + offset] != after[start + offset]:
                changes.setdefault(f"slot{slot}", []).append(
                    (offset, before[start + offset], after[start + offset]))
    for name, rows in changes.items():
        pretty = ", ".join(f"+0x{off:02X}:{b:02X}->{a:02X}" for off, b, a in rows)
        print(f"{name}: {pretty}")
    (out_dir / "changes.json").write_text(
        json.dumps(changes, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
