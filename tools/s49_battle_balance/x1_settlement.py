#!/usr/bin/env python3
"""X1 (wave 12): record the remake's settlement chain on the ROM.

How the chain is reached
------------------------
The battle cannot be won on the current ROM (the action confirm crashes the
ROM -- see notes/s49-fidelity/X1-input-regression-and-settlement.md), so the
chain is entered by **forcing the controller's phase** to ``outcome``
(``battle_scene_phase::outcome`` = 13) with the probe's ``poke`` command.

The controller is a ``BN_DATA_EWRAM_BSS static`` in the battle runtime scene;
its address comes from the ELF's symbol table and ``_phase`` is its first
member, so the phase byte sits at the symbol's address.  Every frame in the
capture is a **real runtime frame** (the product code renders it), but the
battle was **not** won by playing, so the settlement numbers are the empty
result, not a finished fight's.

Usage::

    python tools/s49_battle_balance/x1_settlement.py \\
        --rom build/x1/rom.gba --out build/x1/settlement
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import w1_boot  # noqa: E402
import w1_probe as probe_module  # noqa: E402
import x1_play  # noqa: E402
import x1_telemetry  # noqa: E402

PHASE_OUTCOME = 13
SETTLEMENT_PHASES = (13, 14, 15, 19, 24, 25)
PHASE_COMPLETE = 16

# The controller's static in the battle runtime scene
# (BN_DATA_EWRAM_BSS static battle_runtime_controller controller;) and the
# offset of its ``_phase`` member (the DWARF's data_member_location of
# ``battle_scene_controller<12, 23, 32>::_phase``).
CONTROLLER_PHASE_ADDRESS = 0x0200C444
CONTROLLER_PHASE_OFFSET = 0x177FC
CONTROLLER_PHASE_ADDRESS_DECIMAL = 0x02023C40  # 33 700 928
CONTROLLER_OUTCOME_OFFSET = 0x17A24
CONTROLLER_OUTCOME_ADDRESS_DECIMAL = 0x02023E68  # 33 701 480
OUTCOME_WIN = 1


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path,
                        default=HERE.parents[1] / "build" / "mgba-probe-x1" /
                        "mgba-probe.exe")
    parser.add_argument("--controller-phase-address", type=lambda value: int(value, 0),
                        default=CONTROLLER_PHASE_ADDRESS_DECIMAL)
    parser.add_argument("--controller-base", type=lambda value: int(value, 0),
                        default=CONTROLLER_PHASE_ADDRESS)
    parser.add_argument("--controller-outcome-address",
                        type=lambda value: int(value, 0),
                        default=CONTROLLER_OUTCOME_ADDRESS_DECIMAL)
    parser.add_argument("--settle-frames", type=int, default=70)
    parser.add_argument("--press-hold", type=int, default=4)
    parser.add_argument("--max-pages", type=int, default=40)
    parser.add_argument("--route", type=pathlib.Path, default=None,
                        help="route to replay before the phase is forced")
    parser.add_argument("--route-steps", type=int, default=0,
                        help="how many route steps to replay first")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    shots = args.out / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    receipt: dict[str, object] = {
        "schema": "konoha.s49-x1-settlement-capture.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "out": str(args.out),
        "controller_phase_address":
            f"0x{args.controller_phase_address:08X}",
        "note": "the chain is entered by forcing the controller's phase to "
                "outcome; every frame is a real runtime frame but the battle "
                "was not won by playing (the action confirm crashes the ROM)",
        "pages": [],
    }
    started = time.time()
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        boot = w1_boot.Boot(probe, args.out / "boot")
        receipt["boot"] = boot.run()
        telemetry = x1_telemetry.Telemetry(probe)
        telemetry.locate()
        receipt["telemetry_address"] = f"0x{telemetry.address:08X}"
        if args.route and args.route_steps:
            route = json.loads(args.route.read_text(encoding="utf-8"))
            driver = x1_play.Driver(probe, telemetry, args.out, verbose=False)
            driver.telemetry.locate()
            driver.play_route(route, args.route_steps)
            receipt["route"] = str(args.route)
            receipt["route_steps"] = args.route_steps
            receipt["phase_before_poke"] = telemetry.read()["phase"]
        # Force the controller into the victory phase.  The probe parses the
        # poke address as a **decimal** integer, so it is converted here.
        # The phase byte is verified by reading it back before the poke.
        raw = telemetry._dump(args.controller_phase_address, 1)
        current = telemetry.read()["phase"]
        receipt["phase_byte_before_poke"] = raw[0]
        receipt["phase_from_telemetry"] = current
        if raw[0] != current:
            raise RuntimeError(
                f"the byte at 0x{args.controller_phase_address:08X} is "
                f"{raw[0]}, not the phase {current}")
        probe.run(f"poke {args.controller_phase_address} {PHASE_OUTCOME}")
        # The victory screen is only drawn for a won battle, so the
        # controller's outcome is set to win as well.
        probe.run(f"poke {args.controller_outcome_address} {OUTCOME_WIN}")
        probe.run(f"frames {args.settle_frames} 0x00000000")
        for index in range(args.max_pages):
            values = telemetry.read()
            phase = values["phase"]
            if phase == PHASE_COMPLETE:
                break
            if phase not in SETTLEMENT_PHASES:
                break
            path = shots / f"page-{index:03d}-{x1_telemetry.phase_name(phase)}.png"
            probe.run(f"shot {path}")
            receipt["pages"].append({
                "index": index,
                "phase": phase,
                "phase_name": x1_telemetry.phase_name(phase),
                "settlement_page": values["training_detail_page"],
                "outcome": values["condition_outcome"],
                "result_participant_count": values["result_participant_count"],
                "file": path.name,
                "sha256": sha256_file(path),
            })
            print(f"page {index}: {x1_telemetry.phase_name(phase)} -> {path.name}",
                  flush=True)
            # Advance the chain with A.
            probe.run(f"frames {args.press_hold} 0x00000001")
            probe.run(f"frames {args.settle_frames} 0x00000000")
            after = telemetry.read()
            receipt["pages"][-1]["phase_after"] = after["phase"]
            receipt["pages"][-1]["presentation_busy"] = after["presentation_busy"]
            receipt["pages"][-1]["map_movement_active"] = after["map_movement_active"]
        values = telemetry.read()
        receipt["final_phase"] = values["phase"]
        receipt["final_phase_name"] = x1_telemetry.phase_name(values["phase"])
        stderr = probe.stderr
        (args.out / "stderr.txt").write_text("\n".join(stderr) + "\n",
                                              encoding="utf-8", newline="\n")
    receipt["wall_seconds"] = round(time.time() - started, 1)
    (args.out / "settlement.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in receipt.items()
                      if key != "pages"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
