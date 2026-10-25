#!/usr/bin/env python3
"""Smoke test: read the remake telemetry out of one captured savestate.

Usage::

    python tools/s49_w21c2/_smoke.py --rom <rom> --state <ss9>
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "s49_battle_balance"))

import w1_probe as probe_module  # noqa: E402
import x1_telemetry as telemetry_module  # noqa: E402


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--state", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path, required=True)
    args = parser.parse_args()
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        print(probe.load(args.state))
        telemetry = telemetry_module.Telemetry(probe)
        values = telemetry.read()
        print(f"address 0x{telemetry.address:08X}")
        for name in ("magic", "battle_id", "phase", "round", "current_side",
                     "selected_unit", "unit_count", "active_unit_count",
                     "selected_command", "cursor_x", "cursor_y",
                     "presentation_busy", "map_movement_active",
                     "condition_outcome", "script_phase", "scene_frame",
                     "selected_action_id", "selected_action_error"):
            print(f"{name:28s} {values[name]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
