#!/usr/bin/env python3
"""Look at one jutsu entry's target mode in the original battle.

The driver needs to know what the screen looks like after a jutsu is picked
(the cross shuriken's aim mode is the reference).  This script opens the
jutsu list of the acting unit, picks one entry and captures the following
frames, so the target mode can be recognised by its pixels.

Usage::

    python tools/s49_victory_capture/probe_jutsu_mode.py \
        --out build/s49-victory-capture/jutsu-mode --slot 2 --index 0
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
                        default=REPO / "build" / "s49-victory-capture" / "jutsu-mode")
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    parser.add_argument("--slot", type=int, default=1,
                        help="the pool slot of the acting unit (1 = Naruto)")
    parser.add_argument("--index", type=int, default=3,
                        help="the jutsu list index to pick")
    parser.add_argument("--skip", type=int, default=0,
                        help="how many units to let act before the probe")
    parser.add_argument("--frames", type=int, default=240,
                        help="frames to capture after the jutsu was picked")
    args = parser.parse_args(argv)

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.load(args.state)
        observer = battle_obs.BattleObserver(probe, raw_path=out / "frame.raw")

        def capture(label: str) -> battle_obs.Observation:
            observation = observer.observe()
            name = f"{len(rows):03d}-{label}.png"
            observation.image.save(out / name)
            sig = observation.sig
            rows.append({"label": label, "png": name, "level": observation.level,
                         "menu": observation.menu, "cursor": list(observation.cursor),
                         "menu_cursor": observation.menu_cursor, "sig": sig})
            print(f"[{len(rows) - 1:03d}] {label:<16} level={observation.level} "
                  f"menu={observation.menu:<8} cursor={observation.cursor} "
                  f"mcursor={observation.menu_cursor} "
                  f"border={sig['border_rows']} dark={sig['menu_dark']} "
                  f"panel={sig['panel_light']} dlg={sig['dialogue_light']} "
                  f"err={sig['error_light']} cfm={sig['confirm_light']} "
                  f"hatch={sig['hatch']} path={sig['path']}")
            return observation

        # entry performance -> the action menu
        for _ in range(40):
            observation = observer.observe()
            if observation.sig["border_rows"] >= 70:
                break
            observer.press("A", settle=90)
        capture("action5")

        # let the wanted unit act: end the actions of the other units
        for _ in range(12):
            observation = observer.observe()
            unit = observation.acting_ally()
            if unit is not None and unit["slot"] == args.slot:
                break
            if observation.menu in ("action5", "action2"):
                index = battle_obs.MENU_ITEM_END if observation.menu == "action5" else 1
                observer.select_menu_item(observation, index)
                observer.press("A", settle=60)
                for _ in range(4):
                    observation = observer.observe()
                    if observation.sig["confirm_light"] > 1000:
                        observer.press("A", settle=60)
                        continue
                    break
                continue
            observer.press("A", settle=90)
        capture(f"slot{args.slot}-action")

        # open the jutsu list
        observation = observer.observe()
        if observation.menu == "action5":
            observer.select_menu_item(observation, battle_obs.MENU_ITEM_JUTSU)
            observer.press("A", settle=60)
        for _ in range(20):
            observation = observer.observe()
            if observation.menu == "jutsu":
                break
            observer.run(30)
        capture("jutsu-list")

        observer.select_menu_item(observer.observe(), args.index)
        capture(f"jutsu-index{args.index}")
        observer.press("A", settle=30)
        for step in range(args.frames // 30):
            observer.run(30)
            capture(f"after-{step * 30:04d}")

        # fire at the closest bee and watch the forecast / confirmation
        observation = observer.observe()
        bees = observation.bees()
        if bees:
            target = min(bees, key=lambda unit: (abs(unit["x"] - observation.cursor[0])
                                                  + abs(unit["y"] - observation.cursor[1])))
            observer.move_cursor_to(observation, (target["x"], target["y"]))
            capture("aim-target")
            observer.press("A", settle=1)
            for step in range(args.frames // 5):
                observer.run(5)
                capture(f"fire-{step * 5:04d}")

    (out / "probe.json").write_text(
        json.dumps({"schema": "konoha.s49-victory-jutsu-mode.v1",
                    "slot": args.slot, "index": args.index, "rows": rows},
                   indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print("->", out / "probe.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
