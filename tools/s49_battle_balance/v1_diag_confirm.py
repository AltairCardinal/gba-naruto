#!/usr/bin/env python3
"""U4 (wave 17): where exactly does the attack freeze now?

After U1's fix the action confirmation no longer corrupts the battle state,
but the scene still stops advancing.  The chain reaches ``target_confirmation``
and stays there.  This tool answers the question that decides whether the
remaining blocker is the **product** or the **driver**:

* drive the turn to the attack,
* confirm the attack and the target,
* **wait without pressing anything** and watch the phase and the scene frame,
* then press A once and watch again.

If the scene freezes on its own, the blocker is the product's.  If it only
freezes after the A press, the driver is pressing the wrong thing.

Usage::

    python tools/s49_battle_balance/v1_diag_confirm.py \\
        --rom build/v1-u4/rom-pinned.gba --out build/v1-u4/diag-confirm
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import w1_boot  # noqa: E402
import w1_probe as probe_module  # noqa: E402
import x1_telemetry  # noqa: E402
import v1_battle  # noqa: E402
import v1_truth  # noqa: E402

REPO = HERE.parents[1]

PHASE_ACTION_SELECTION = 6
PHASE_TARGET_SELECTION = 8


def snapshot(driver) -> dict:
    values = driver.state()
    return {"frame": driver.frames, "phase": values["phase"],
            "phase_name": x1_telemetry.phase_name(values["phase"]),
            "scene_frame": values["scene_frame"],
            "busy": values["presentation_busy"],
            "combat_stage": values["presentation_combat_stage"],
            "combat_frame": values["presentation_combat_stage_frame"],
            "combat_impact": values["presentation_combat_impact_index"],
            "action_error": values["selected_action_error"],
            "control_error": values["last_control_error"],
            "player_error": values["last_player_error"],
            "cursor": [values["cursor_x"], values["cursor_y"]]}


def watch(driver, polls: int, gap: int, label: str, press: str | None
          ) -> list[dict]:
    out = []
    for index in range(polls):
        if index == 2 and press:
            driver.press(press, 4)
            driver.wait(30)
        driver.wait(gap)
        record = snapshot(driver)
        record["label"] = label
        out.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
    return out


def try_inputs(driver, trials: list[tuple[str, list[str]]], gap: int
               ) -> list[dict]:
    """Try one candidate input after another at the current phase.

    Each trial presses the candidate's keys, waits, and records whether the
    phase moved on.  The first candidate that moves the phase on is the one
    the player has to use.
    """
    out = []
    for label, keys in trials:
        before = snapshot(driver)
        for key in keys:
            driver.press(key, 4)
            driver.wait(12)
        driver.wait(gap)
        after = snapshot(driver)
        record = {"trial": label, "keys": keys, "before": before,
                  "after": after,
                  "phase_moved": after["phase"] != before["phase"],
                  "scene_advanced": after["scene_frame"] > before["scene_frame"]}
        out.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
        if not record["scene_advanced"]:
            break
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path,
                        default=REPO / "build" / "mgba-probe-u4" /
                        "mgba-probe.exe")
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "v1-u4" / "diag-confirm")
    parser.add_argument("--truth", type=pathlib.Path,
                        default=REPO / "build" / "v1" / "battle-truth.json")
    parser.add_argument("--move-cell", type=str, default="9,6")
    parser.add_argument("--action-index", type=int, default=3)
    parser.add_argument("--target", type=str, default="6,6")
    parser.add_argument("--polls", type=int, default=12)
    parser.add_argument("--gap", type=int, default=30)
    parser.add_argument("--trials", type=str,
                        default="Up+A,A,Down+A,B",
                        help="the candidate inputs at the 「可以嗎?」 prompt, "
                             "comma separated; the first one that moves the "
                             "phase on is the answer")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    truth = v1_truth.load(args.truth)
    move_cell = tuple(int(part) for part in args.move_cell.split(","))
    target = tuple(int(part) for part in args.target.split(","))
    record: dict[str, object] = {"rom": str(args.rom),
                                  "rom_sha256": v1_battle.y1_play.sha256_file(
                                      args.rom),
                                  "move_cell": list(move_cell),
                                  "action_index": args.action_index,
                                  "target": list(target)}
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        boot = w1_boot.Boot(probe, args.out / "boot")
        boot.run()
        telemetry = x1_telemetry.Telemetry(probe)
        driver = v1_battle.Battle(probe, telemetry, args.out, verbose=False,
                                  truth=truth, allow_tools=True)
        for _ in range(300):
            values = telemetry.read()
            if values["phase"] == PHASE_ACTION_SELECTION:
                break
            if values["phase"] == 18:
                driver.advance_dialogue()
            elif values["phase"] == 23:
                driver.press("A", 4)
                driver.wait(30)
                driver.settle()
            elif values["phase"] == 1:
                driver.select_actor()
            elif values["phase"] == 3:
                driver.do_command()
            elif values["phase"] == 2:
                driver.plan = {"path": [(values["cursor_x"], values["cursor_y"]),
                                        move_cell], "cell": move_cell}
                driver.do_move()
            else:
                driver.wait(30)
        record["at_action"] = snapshot(driver)
        for _ in range(args.action_index):
            driver.press("Down", 2)
            driver.wait(8)
        record["on_entry"] = snapshot(driver)
        driver.press("A", 4)
        driver.wait(30)
        record["after_action"] = snapshot(driver)
        # the target selection: put the cursor on the bee and confirm it
        for _ in range(60):
            values = telemetry.read()
            if values["phase"] == PHASE_TARGET_SELECTION:
                break
            driver.wait(30)
        driver.place_cursor(target)
        record["cursor_on_target"] = snapshot(driver)
        driver.press("A", 4)
        driver.wait(30)
        record["after_target"] = snapshot(driver)
        # ---- the 「可以嗎?」 prompt: reach it, then look at it ---------
        for _ in range(60):
            values = telemetry.read()
            if values["phase"] == 20:
                break
            if values["phase"] == 22:
                # the preview waits for an A press before the dialog shows
                driver.press("A", 4)
                driver.wait(30)
            else:
                driver.wait(30)
        record["at_confirm"] = snapshot(driver)
        probe.run(f"shot {args.out / 'confirm-00.png'}")
        # ---- watch WITHOUT any input -----------------------------------
        record["watch_no_input"] = watch(driver, args.polls, args.gap,
                                          "no-input", None)
        probe.run(f"shot {args.out / 'confirm-01.png'}")
        # ---- which input moves the target confirmation on? --------------
        record["input_trials"] = try_inputs(driver, [
            (item, item.split("+")) for item in args.trials.split(",") if item
        ], args.gap)
        probe.run(f"shot {args.out / 'after-trials.png'}")
        record["roster"] = driver.roster_snapshot(driver.state())
    (args.out / "diag-confirm.json").write_text(
        json.dumps(record, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
