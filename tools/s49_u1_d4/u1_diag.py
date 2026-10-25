#!/usr/bin/env python3
"""U1 (wave 17): where exactly does the player's in-range attack die?

The driver walks one turn, lands on one action-list entry, confirms it and
then polls the remake's own telemetry every 30 frames.  Every poll prints the
phase, the scene frame counter and the combat presentation's internal state
(stage / stage frame / resource / impact index), so a frozen ROM and a dead
input gate are told apart by data instead of by impression.

Usage::

    python tools/s49_u1_d4/u1_diag.py \\
        --rom build/u1/rom.gba \\
        --move-cell 9,6 --action-index 3 --target 6,6
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
BALANCE = REPO / "tools" / "s49_battle_balance"
if str(BALANCE) not in sys.path:
    sys.path.insert(0, str(BALANCE))

import w1_boot  # noqa: E402
import w1_probe as probe_module  # noqa: E402
import x1_telemetry  # noqa: E402
import v1_battle  # noqa: E402
import v1_truth  # noqa: E402

PHASE_ACTION_SELECTION = 6
PHASE_TARGET_SELECTION = 8


def line(values: dict[str, int]) -> str:
    return (f"phase={values['phase']:3d} "
            f"{x1_telemetry.phase_name(values['phase']):20s} "
            f"scene_frame={values['scene_frame']:7d} "
            f"busy={values['presentation_busy']} "
            f"c_stage={values['presentation_combat_stage']:2d} "
            f"c_frame={values['presentation_combat_stage_frame']:5d} "
            f"c_res={values['presentation_combat_resource']:2d} "
            f"c_impact={values['presentation_combat_impact_index']} "
            f"act_idx={values['action_index']:2d} "
            f"act_id={values['selected_action_id']:3d} "
            f"act_err={values['selected_action_error']} "
            f"ctrl={values['last_control_error']} "
            f"player={values['last_player_error']}")


def parse_cell(text: str) -> tuple[int, int]:
    x, _, y = text.partition(",")
    return int(x), int(y)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path,
                        default=REPO / "build" / "mgba-probe-u1" /
                        "mgba-probe.exe")
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "u1" / "diag")
    parser.add_argument("--truth", type=pathlib.Path,
                        default=REPO / "build" / "v1" / "battle-truth.json")
    parser.add_argument("--move-cell", type=str, default="")
    parser.add_argument("--action-index", type=int, default=2)
    parser.add_argument("--target", type=str, default="")
    parser.add_argument("--observe", type=int, default=1200)
    parser.add_argument("--poll", type=int, default=30)
    parser.add_argument("--crash-dump", action="store_true",
                        help="ask mGBA's debugger for the register state and "
                             "the backtrace once the scene stopped advancing")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    truth = v1_truth.load(args.truth)
    record: dict[str, object] = {
        "rom": str(args.rom),
        "rom_sha256": v1_battle.y1_play.sha256_file(args.rom),
        "action_index": args.action_index,
        "move_cell": args.move_cell,
        "target": args.target,
        "polls": [],
    }
    move_cell = parse_cell(args.move_cell) if args.move_cell else None
    target = parse_cell(args.target) if args.target else None

    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        boot = w1_boot.Boot(probe, args.out / "boot")
        boot.run()
        telemetry = x1_telemetry.Telemetry(probe)
        driver = v1_battle.Battle(probe, telemetry, args.out, verbose=False,
                                  truth=truth)

        # ---- drive the turn up to the action list ----------------------
        for _ in range(200):
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
                if move_cell is not None:
                    driver.plan = {
                        "path": [(values["cursor_x"], values["cursor_y"]),
                                 move_cell],
                        "cell": move_cell,
                    }
                    driver.do_move()
                else:
                    driver.press("A", 4)
                    driver.wait(30)
                    driver.settle()
            else:
                driver.wait(30)

        values = telemetry.read()
        print("at-action  " + line(values), flush=True)
        record["at_action"] = dict(values)

        # ---- land on the wanted entry -----------------------------------
        for _ in range(args.action_index):
            driver.press("Down", 2)
            driver.wait(8)
        values = telemetry.read()
        print("on-entry   " + line(values), flush=True)
        record["on_entry"] = dict(values)

        # ---- confirm and observe ----------------------------------------
        # Snapshot the devkitARM IRQ vector table before the attack, so the
        # crash-time copy can be compared against it.
        before_table = telemetry._dump(0x03002800, 0x100).hex()
        driver.press("A", 4)
        driver.wait(args.poll)
        reached_target = False
        for step in range(args.observe // args.poll):
            values = telemetry.read()
            text = line(values)
            print(f"[{step * args.poll:5d}] {text}", flush=True)
            record["polls"].append(dict(values))
            if values["phase"] == PHASE_TARGET_SELECTION and not reached_target:
                reached_target = True
                if target is not None:
                    driver.place_cursor(target)
                    print("cursor-on-target " + line(telemetry.read()),
                          flush=True)
                    driver.press("A", 4)
                    driver.wait(args.poll)
                    continue
            if values["phase"] in (22, 20):
                # target_preview / target_confirmation: confirm with A.
                driver.press("A", 4)
                driver.wait(args.poll)
                print(f"confirm@{values['phase']} " + line(telemetry.read()),
                      flush=True)
                continue
            if reached_target and values["phase"] == PHASE_TARGET_SELECTION:
                # the target confirmation was refused: keep polling
                pass
            driver.wait(args.poll)

        values = telemetry.read()
        print("final      " + line(values), flush=True)
        record["final"] = dict(values)
        record["roster"] = driver.roster_snapshot(values)
        probe.run(f"shot {args.out / 'after.png'}")

        if args.crash_dump:
            dump = []
            # The IWRAM top holds the devkitARM IRQ vector at 0x03007FFC and
            # the user stack grows down from 0x03007F00, so a stack that
            # reaches this window has overwritten the interrupt vector.
            for label, address, length in (
                    ("irq-vector-table", 0x03002800, 0x100),
                    ("iwram-top", 0x03007000, 0x1000),
                    ("io-registers", 0x04000200, 0x10),
                    ("ewram-top", 0x0203FFF0, 0x10),
            ):
                try:
                    blob = telemetry._dump(address, length)
                except Exception as error:  # noqa: BLE001
                    blob = b""
                    dump.append(f"---- {label} -> <{error}>")
                if blob:
                    words = []
                    for offset in range(0, len(blob) - 3, 4):
                        word = int.from_bytes(blob[offset:offset + 4], "little")
                        words.append(f"{address + offset:08X}:{word:08X}")
                    dump.append(f"---- {label} ----")
                    dump.extend("    " + item for item in words)
            for command in ("status",
                            "print/x r13", "print/x r14", "print/x r15",
                            "print/x r0", "print/x r1", "print/x r2",
                            "print/x r3", "print/x r12",
                            "backtrace 30",
                            "listb", "listw"):
                try:
                    lines = probe.run(command)
                except Exception as error:  # noqa: BLE001
                    lines = [f"<{error}>"]
                dump.append(f"---- {command} ----")
                dump.extend(f"    {item}" for item in lines)
                print(f"---- {command} ----", flush=True)
                for item in lines:
                    print(f"    {item}", flush=True)
            # Disassemble around whatever the program counter points at.
            try:
                pc_line = [item for item in dump
                           if "r15" in item and "0x" in item]
                pc_text = pc_line[-1] if pc_line else ""
                pc = int(pc_text.split("0x")[-1].split()[0], 16)
            except (IndexError, ValueError):
                pc = 0
            if pc:
                for command in (f"disassemble 0x{pc:08X} 24",
                                f"x/4 0x{pc:08X} 32"):
                    try:
                        lines = probe.run(command)
                    except Exception as error:  # noqa: BLE001
                        lines = [f"<{error}>"]
                    dump.append(f"---- {command} ----")
                    dump.extend(f"    {item}" for item in lines)
                    print(f"---- {command} ----", flush=True)
                    for item in lines:
                        print(f"    {item}", flush=True)
            record["crash_dump"] = dump
            record["irq_table_before"] = before_table
            (args.out / "crash-dump.txt").write_text(
                "\n".join(dump) + "\n", encoding="utf-8", newline="\n")
            stderr = list(probe.stderr)
            print(f"---- probe stderr ({len(stderr)} lines) ----", flush=True)
            for item in stderr[-40:]:
                print(f"    {item}", flush=True)
            (args.out / "stderr.txt").write_text(
                "\n".join(stderr) + "\n", encoding="utf-8", newline="\n")

    (args.out / "u1-diag.json").write_text(
        json.dumps(record, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
