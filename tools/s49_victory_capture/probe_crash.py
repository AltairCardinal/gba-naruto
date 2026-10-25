#!/usr/bin/env python3
"""Isolate the probe crash that happens right after Sakura's move.

The driver dies with a broken pipe after the second unit walks to (7,13).
This script replays the first action with the real driver, then performs
Sakura's move by hand and then reads the state -- with the screenshots and
the dumps switchable, so the trigger can be told apart.

Usage::

    python tools/s49_victory_capture/probe_crash.py --out build/s49-victory-capture/crash
"""

from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import battle as battle_module  # noqa: E402
import play_battle_v2  # noqa: E402
import probe as probe_module  # noqa: E402

_BUILD = pathlib.Path(__file__).resolve().parents[2] / "build"
DEFAULT_EXE = _BUILD / "mgba-probe-m" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--exe", default=str(DEFAULT_EXE))
    parser.add_argument("--out", required=True)
    parser.add_argument("--cell", default="7,13")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--no-shot", action="store_true")
    parser.add_argument("--no-dump", action="store_true")
    args = parser.parse_args(argv)

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cell = tuple(int(v) for v in args.cell.split(","))
    log: list = []

    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.load(args.state)
        battle = battle_module.Battle(probe, settle=45,
                                      screen_path=out_dir / "screen.png")
        driver = play_battle_v2.Driver(battle, log,
                                       debug_shots=out_dir / "debug")
        # ---- one full action (Naruto) --------------------------------
        for _ in range(80):
            if battle.menu() in ("action5", "action2"):
                break
            battle.press("A", settle=90)
        driver.act()
        print("after Naruto:", battle.menu(),
              [(u["slot"], u["x"], u["y"]) for u in battle.pool_current()])

        # ---- advance to the next unit ---------------------------------
        for _ in range(40):
            if battle.menu() in ("action5", "action2"):
                break
            battle.press("A", settle=90)
        print("next actor:", battle.acting_ally(), "menu", battle.menu())

        # ---- the move that crashes the probe -------------------------
        if args.full:
            driver.act()
            print("after Sakura's action:", battle.menu())
            for row in log:
                print("   log:", row)
            for index in range(12):
                probe.frames(60, 0)
                print(index, "menu", battle.menu(),
                      [(u["slot"], u["x"], u["y"]) for u in battle.pool_current()])
                probe.shot(out_dir / f"after-{index:02d}.png")
            print("survived")
            return 0
        # open the move phase of the acting unit (menu item 0 = 移動)
        battle.select_menu_item(0)
        battle.press("A", settle=140, tag="open-move")
        print("after open-move: menu", battle.menu(), "cursor", battle.cursor())
        battle.set_cursor(*cell)
        print("cursor", battle.cursor())
        battle.press("A", settle=140, tag="move")
        if not args.no_dump:
            print("pool", battle.pool_current())
        for index in range(12):
            probe.frames(60, 0)
            if not args.no_dump:
                print(index, "pool", [(u["slot"], u["x"], u["y"]) for u in battle.pool_current()],
                      "hp", battle.hp())
            if not args.no_shot:
                probe.shot(out_dir / f"after-{index:02d}.png")
            else:
                battle.menu()
    print("survived")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
