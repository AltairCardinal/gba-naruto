#!/usr/bin/env python3
"""Probe which cells the original accepts as a move destination.

Stream K guessed the landing cells and every guess was rejected.  This script
asks the game instead: it walks the battle cursor onto a candidate cell,
presses A and then reads the unit pool.  A cell is *legal* when the acting
unit actually stands on it afterwards.

It also dumps the BG2 overlay before and after every probe, so the legal set
can be correlated with the overlay families (cyan = reachable range, orange =
path preview, grey = blocked) and the coordinate mapping can be derived.

Usage::

    python tools/s49_victory_capture/probe_move.py --out build/s49-victory-capture/moveprobe \
        --candidates "9,6 8,6 7,6 11,7 12,6"
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

# The error boxes are wide and start at y >= 71; the 「可以嗎？」 dialog is a
# narrow light box at (87..152, 31..80).
FILL = (231, 247, 214)


def parse_candidates(text: str) -> list[tuple[int, int]]:
    out = []
    for chunk in text.replace(";", " ").split():
        x, y = chunk.split(",")
        out.append((int(x), int(y)))
    return out


def error_box_visible(image) -> bool:
    """A wide message box (the game's own rejection notice)."""
    region = image.crop((8, 71, 232, 120))
    light = sum(1 for pixel in region.get_flattened_data() if pixel == FILL)
    return light > 300


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--exe", default=str(DEFAULT_EXE))
    parser.add_argument("--out", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--walk", default="A*30",
                        help="key walk used to reach the move phase")
    parser.add_argument("--settle", type=int, default=60)
    parser.add_argument("--shot", action="store_true")
    parser.add_argument("--wait", type=int, default=360,
                        help="extra frames to wait for the walk animation")
    args = parser.parse_args(argv)

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    log: list[dict] = []
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.load(args.state)
        battle = battle_module.Battle(probe, settle=args.settle,
                                      shot_dir=frames_dir,
                                      screen_path=out_dir / "screen.png")
        battle.capture_each = args.shot

        # ---- 1. reach the move phase -----------------------------------
        from explore_overlay import parse_walk
        for key in parse_walk(args.walk):
            battle.press(key)
            over = overlay_module.read_overlay(probe)
            hatch = len(over.cells_of("hatch"))
            if hatch > 20:
                log.append({"event": "move-phase", "key": key, "hatch": hatch})
                break
        else:
            log.append({"event": "no-move-phase"})
            print("!! never reached the move phase")
        unit = battle.acting_ally() or {"slot": 1, "x": battle.cursor()[0],
                                        "y": battle.cursor()[1]}
        origin = (battle.cursor()[0], battle.cursor()[1])
        over0 = overlay_module.read_overlay(probe)
        log.append({"event": "origin", "unit": unit, "cursor": list(origin),
                    "hatch": len(over0.cells_of("hatch")),
                    "line_alt": len(over0.cells_of("line_alt"))})
        print("origin cursor", origin, "unit", unit,
              "hatch", len(over0.cells_of("hatch")))

        # ---- 2. probe every candidate ----------------------------------
        for cell in parse_candidates(args.candidates):
            if battle.cursor() != cell:
                battle.set_cursor(*cell)
            actual = tuple(battle.cursor())
            before = battle.position(unit["slot"])
            battle.press("A", settle=140, tag="move-dest")
            # the walk animation needs a while before the unit is on its
            # destination cell (the teleport needs ~400 frames)
            probe.frames(args.wait, 0)
            after = battle.position(unit["slot"])
            menu = battle.menu()
            image = battle.screen()
            err = error_box_visible(image)
            row = {
                "cell": list(cell),
                "cursor": list(actual),
                "menu": menu,
                "error_box": err,
                "moved": after != before,
                "from": list(before) if before else None,
                "to": list(after) if after else None,
                "hatch": len(overlay_module.read_overlay(probe).cells_of("hatch")),
            }
            log.append(row)
            print(f"cell={cell} cursor={actual} menu={menu} error={err} "
                  f"moved={row['moved']} {before}->{after}")
            if row["moved"]:
                break
            if menu in ("action2", "action5"):
                log.append({"event": "phase-ended", "cell": list(cell)})
                break
            if err:
                battle.press("B", settle=120, tag="dismiss")

    (out_dir / "moveprobe.json").write_text(
        json.dumps(log, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
