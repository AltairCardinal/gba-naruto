#!/usr/bin/env python3
"""V1 (wave 16): which action entry freezes the remake?

For every index of Naruto's action list the tool boots the battle, walks the
action cursor onto that entry, confirms it and reports whether the scene keeps
advancing (``scene_frame``).
"""
from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import w1_boot
import w1_probe as probe_module
import x1_telemetry
import v1_battle
import v1_truth

REPO = HERE.parents[1]

DEFAULT_ROM = REPO / "build" / "v1" / "rom-pinned.gba"
DEFAULT_EXE = REPO / "build" / "mgba-probe-v1" / "mgba-probe.exe"
DEFAULT_OUT = REPO / "build" / "v1" / "diag"


def try_index(index: int, move: bool, truth: dict,
              cell: tuple[int, int] | None = None,
              rom: pathlib.Path = DEFAULT_ROM,
              exe: pathlib.Path = DEFAULT_EXE,
              out_root: pathlib.Path = DEFAULT_OUT) -> dict:
    out = out_root / \
        (f"idx{index}" + ("-move" if move else "") +
         ("" if cell is None else f"-{cell[0]}_{cell[1]}"))
    out.mkdir(parents=True, exist_ok=True)
    result = {"index": index, "move": move}
    with probe_module.Probe(rom, exe=exe) as probe:
        boot = w1_boot.Boot(probe, out / "boot")
        boot.run()
        telemetry = x1_telemetry.Telemetry(probe)
        driver = v1_battle.Battle(probe, telemetry, out, verbose=False,
                                  truth=truth)
        for _ in range(60):
            values = telemetry.read()
            if values["phase"] == 6:
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
                if move:
                    if cell is not None:
                        driver.plan = {"path": [driver.state()["cursor_x"],
                                                driver.state()["cursor_y"]],
                                       }
                        driver.plan["path"] = [
                            (values["cursor_x"], values["cursor_y"]), cell]
                        driver.plan["cell"] = cell
                    driver.do_move()
                else:
                    driver.press("A", 4)
                    driver.wait(30)
                    driver.settle()
            else:
                driver.wait(30)
        values = telemetry.read()
        result["at_action"] = {"phase": values["phase"],
                               "action_id": values["selected_action_id"],
                               "cursor": [values["cursor_x"],
                                          values["cursor_y"]]}
        count = max(1, values["action_count"])
        for _ in range(index):
            driver.press("Down", 2)
            driver.wait(8)
        values = telemetry.read()
        result["selected"] = {"index": values["action_index"],
                              "action_id": values["selected_action_id"],
                              "source": values["selected_action_kind"],
                              "target_kind": values["selected_action_target_kind"]}
        before = telemetry.read()["scene_frame"]
        driver.press("A", 4)
        driver.wait(60)
        after = telemetry.read()
        result["after"] = {"phase": after["phase"],
                           "scene_frame_before": before,
                           "scene_frame_after": after["scene_frame"],
                           "advanced": after["scene_frame"] > before + 1,
                           "control_error": after["last_control_error"],
                           "player_error": after["last_player_error"]}
        probe.run(f"shot {out / 'after.png'}")
        result["stderr"] = [line for line in probe.stderr
                            if "error" in line.lower() or "ERROR" in line]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument("--truth", type=pathlib.Path,
                        default=REPO / "build" / "v1" / "battle-truth.json")
    parser.add_argument("--index", type=int, default=3,
                        help="the action list index to hover and confirm")
    parser.add_argument("--cells", type=str, default="11,4;13,6;12,6;9,5",
                        help="the landing cells to try, 'x,y;x,y'")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    truth = v1_truth.load(args.truth)
    cells = []
    for item in args.cells.split(";"):
        item = item.strip()
        if not item:
            continue
        x, _, y = item.partition(",")
        cells.append((int(x), int(y)))
    results = []
    for cell in cells:
        result = try_index(args.index, True, truth, cell,
                           rom=args.rom, exe=args.exe, out_root=args.out)
        results.append(result)
        print(result, flush=True)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        import json
        (args.out / "freeze-report.json").write_text(
            json.dumps({"rom": str(args.rom),
                        "rom_sha256": v1_battle.y1_play.sha256_file(args.rom),
                        "index": args.index,
                        "results": results}, indent=1, ensure_ascii=False)
            + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
