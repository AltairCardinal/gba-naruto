#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read the remake's battle telemetry from captured save states.

`tools/s49_w24g1/script_telemetry.py` locates the telemetry struct right
after loading the *first* state, which is `step-00-base` -- before the battle
has started, so the struct does not exist yet and the tool dies with
"the battle telemetry struct was not found in EWRAM".

This version keeps loading states until the struct is found and then prints
the fields of every state.

Usage:
    python tools/s49_w25h1/remake_telemetry.py --remake-dir <dir> --rom <rom> \
        --exe <probe.exe> [--steps 0,1,2,...]
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "s49_battle_balance"))

import w1_probe as probe_module  # noqa: E402
import x1_telemetry as telemetry_module  # noqa: E402

FIELDS = (
    "phase",
    "scene_frame",
    "render_stage",
    "presentation_busy",
    "script_phase",
    "script_selector",
    "script_command_index",
    "script_message_window_visible",
    "script_portrait_0_visible",
    "script_portrait_1_visible",
    "round",
    "current_side",
    "selected_unit",
    "active_unit_count",
    "unit_count",
    "selected_unit_x",
    "selected_unit_y",
    "cursor_x",
    "cursor_y",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--remake-dir", type=pathlib.Path, required=True)
    ap.add_argument("--rom", type=pathlib.Path, required=True)
    ap.add_argument("--exe", type=pathlib.Path, required=True)
    ap.add_argument("--steps", default="")
    args = ap.parse_args()

    states = sorted(args.remake_dir.glob("step-*.ss9"))
    if args.steps:
        wanted = {int(v) for v in args.steps.split(",")}
        states = [
            s for s in states if int(s.name.split("-")[1]) in wanted
        ]
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        telemetry = telemetry_module.Telemetry(probe)
        address = None
        for state in states:
            probe.load(state)
            if address is None:
                try:
                    address = telemetry.locate()
                    print(f"telemetry at 0x{address:08X}")
                except RuntimeError:
                    print(f"{state.name}: no telemetry yet (before the battle)")
                    continue
            blob = probe.dump(address, telemetry_module.BYTE_COUNT)
            words = struct.unpack(
                f"<{telemetry_module.WORD_COUNT}I", blob)
            values = dict(zip(telemetry_module.FIELDS, words))
            row = {k: values.get(k) for k in FIELDS}
            row["phase_name"] = telemetry_module.phase_name(values["phase"])
            print(f"{state.name:<18} " + " ".join(f"{k}={v}" for k, v in row.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
