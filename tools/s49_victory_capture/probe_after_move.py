#!/usr/bin/env python3
"""Watch the game right after a confirmed move.

The driver stalls after Sakura's move to (7,13): the action menu never comes
back.  This script replays the situation and dumps the screen, the menu
classification and the unit pool every few frames so the state can be seen.

Usage::

    python tools/s49_victory_capture/probe_after_move.py \
        --out build/s49-victory-capture/after-move --cell 7,13
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

FILL = (231, 247, 214)


def error_box_visible(image) -> bool:
    region = image.crop((40, 45, 200, 100))
    light = sum(1 for pixel in region.get_flattened_data() if pixel == FILL)
    confirm = image.crop((86, 30, 154, 72))
    confirm_light = sum(1 for pixel in confirm.get_flattened_data() if pixel == FILL)
    return 1000 < light < 3000 and confirm_light < 500


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--exe", default=str(DEFAULT_EXE))
    parser.add_argument("--out", required=True)
    parser.add_argument("--cell", default="7,13")
    parser.add_argument("--walk", default="A*30")
    parser.add_argument("--settle", type=int, default=60)
    parser.add_argument("--watch", type=int, default=40)
    parser.add_argument("--step", type=int, default=45)
    parser.add_argument("--press", action="store_true",
                        help="press A between the samples instead of waiting")
    args = parser.parse_args(argv)

    out_dir = pathlib.Path(args.out)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    cell = tuple(int(v) for v in args.cell.split(","))

    rows: list[dict] = []
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.load(args.state)
        battle = battle_module.Battle(probe, settle=args.settle,
                                      screen_path=out_dir / "screen.png")
        from explore_overlay import parse_walk
        # 1. reach the first unit's move phase
        for key in parse_walk(args.walk):
            battle.press(key)
            if len(overlay_module.read_overlay(probe).cells_of("hatch")) > 20:
                break
        print("cursor", battle.cursor(), "menu", battle.menu())
        # 2. walk the cursor onto the requested cell and confirm the move
        battle.set_cursor(*cell)
        print("cursor now", battle.cursor())
        battle.press("A", settle=140, tag="move-dest")
        for index in range(args.watch):
            if args.press:
                battle.press("A", settle=args.settle)
            else:
                probe.frames(args.step, 0)
            image = battle.screen()
            row = {
                "index": index,
                "menu": battle.menu(),
                "level": battle.menu_level(),
                "panel_fill": sum(1 for y in range(20, 130) for x in range(170, 240)
                                  if image.getpixel((x, y)) == (231, 247, 214)),
                "cursor": list(battle.cursor()),
                "units": [(u["slot"], u["x"], u["y"]) for u in battle.pool_current()],
                "hp": battle.hp(),
                "error": error_box_visible(image),
                "hatch": len(overlay_module.read_overlay(probe).cells_of("hatch")),
            }
            rows.append(row)
            probe.shot(frames_dir / f"watch-{index:03d}.png")
            print(index, row["menu"], row["cursor"], row["error"],
                  row["hatch"], row["units"])
    (out_dir / "watch.json").write_text(
        json.dumps(rows, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
