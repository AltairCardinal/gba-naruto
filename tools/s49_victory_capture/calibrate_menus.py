#!/usr/bin/env python3
"""Measure the screen signatures of the original's battle menus.

The driver's classifier needs numbers that were measured on this machine, so
this script walks the original into every menu state and records the pixel
signature of each one:

* the five entry action menu (移動 / 术・忍具 / 查克拉 / 休息 / 行動終了),
* the jutsu list (with its light info panel),
* the aim mode,
* the compact menu (術·忍具 / 行動終了) that replaces the action menu after a
  move,
* the damage forecast and the 「可以嗎？」 dialog.

Every step is a *frame exact* observation (see ``battle_obs``): the picture
and the registers belong to the same frame.

Usage::

    python tools/s49_victory_capture/calibrate_menus.py \
        --out build/s49-victory-capture/calibrate
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import battle_obs  # noqa: E402
import probe as probe_module  # noqa: E402

REPO = HERE.parents[1]
DEFAULT_EXE = REPO / "build" / "mgba-probe-w3" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "s49-victory-capture" / "calibrate")
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    args = parser.parse_args(argv)

    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []

    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.load(args.state)
        observer = battle_obs.BattleObserver(probe, raw_path=out / "frame.raw")

        def capture(label: str, note: str = "") -> battle_obs.Observation:
            observation = observer.observe()
            name = f"{len(rows):02d}-{label}.png"
            observation.image.save(out / name)
            row = {
                "index": len(rows),
                "label": label,
                "note": note,
                "png": name,
                "level": observation.level,
                "menu_cursor": observation.menu_cursor,
                "cursor": list(observation.cursor),
                "menu": observation.menu,
                "signature": observation.sig,
                "units": observation.units,
            }
            rows.append(row)
            sig = observation.sig
            print(f"[{row['index']:02d}] {label:<16} level={observation.level} "
                  f"menu={observation.menu:<8} "
                  f"border={sig['border_rows']:>3} dark={sig['menu_dark']:>4} "
                  f"panel={sig['panel_light']:>5} dlg={sig['dialogue_light']:>5} "
                  f"err={sig['error_light']:>5} cfm={sig['confirm_light']:>5} "
                  f"cursor={observation.cursor[:2]} "
                  f"mcursor={observation.menu_cursor}")
            return observation

        # --- the entry performance: press A until the action menu shows up
        for _ in range(40):
            observation = observer.observe()
            if observation.sig["border_rows"] >= 70:
                break
            observer.press("A", settle=90)
        capture("action5", "five entry action menu")

        # --- move: 移動 -> walk the cursor -> confirm -> compact menu
        observer.select_menu_item(observer.observe(), battle_obs.MENU_ITEM_MOVE)
        observer.press("A", settle=90)
        capture("move-phase", "move phase, cursor on the unit")
        for _ in range(3):
            observer.press("Left", settle=20)
        capture("move-cursor", "cursor walked three cells to the left")
        observer.press("A", settle=200)
        capture("action2", "compact menu right after the move")
        observer.run(180)
        capture("action2b", "compact menu after the walk animation")

        # --- open the jutsu list from the compact menu
        observer.press("A", settle=90)
        capture("jutsu", "jutsu list with the info panel")

        # --- pick the cross shuriken -> aim mode
        observer.select_menu_item(observer.observe(), battle_obs.JUTSU_SHURIKEN)
        observer.press("A", settle=90)
        capture("aim", "aim / target cursor")

        # --- aim at the bee next to the unit and fire
        observation = observer.observe()
        bees = observation.bees()
        if bees:
            target = min(bees, key=lambda unit: (abs(unit["x"] - observation.cursor[0])
                                                  + abs(unit["y"] - observation.cursor[1])))
            observer.move_cursor_to(observation, (target["x"], target["y"]))
            capture("aim-target", "aim cursor on the bee")
            observer.press("A", settle=90)
            capture("forecast", "damage forecast / 可以嗎?")
            observer.press("A", settle=90)
            capture("confirm", "after the confirmation")

    (out / "calibrate.json").write_text(
        json.dumps({"schema": "konoha.s49-victory-calibrate.v1",
                    "rows": rows}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print("->", out / "calibrate.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
