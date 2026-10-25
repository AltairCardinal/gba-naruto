#!/usr/bin/env python3
"""W5 -- read the remake's battle telemetry out of the *already captured* walk.

Why this tool exists
--------------------
The two A-key walks diverge between original step 9 and step 10, and the
pictures say the divergence happens **inside the 开战 (battle start) title
card**.  To name the remake's side of that moment in the same vocabulary as
the original, the remake's own ``battle_runtime_scene_telemetry`` is needed:
it publishes the scene's phase, the round, the selected unit and the cursor.

The remake's capture already saved a savestate next to every PNG, so **no new
recording is needed**: the headless probe loads each savestate and dumps the
telemetry struct out of EWRAM.  The struct is located by its magic
(``0x4B42544C`` = "KBTL") because its address moves between builds.

Usage
-----
    python tools/s49_w5/w5_phase_telemetry.py \
        --rom build/s49-package-u3-final/work/pinned-rom/measured.gba \
        --capture build/s49-package-u3-final/work/s49-report/capture-remake \
        --exe build/s49-wave18/w5/probe/mgba-probe.exe \
        --out build/s49-wave18/w5/phase-remake.json
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from s49_battle_balance.x1_telemetry import (  # noqa: E402
    FIELDS, MAGIC, PHASES, WORD_COUNT, BYTE_COUNT,
)
from s49_fidelity_report.probe import Probe  # noqa: E402

EWRAM_BASE = 0x02000000
EWRAM_SIZE = 0x00040000


def phase_name(value: int) -> str:
    if 0 <= value < len(PHASES):
        return PHASES[value]
    return f"phase_{value}"


def find_telemetry(probe: Probe) -> int:
    """Scan EWRAM for the telemetry magic."""
    magic_bytes = struct.pack("<I", MAGIC)
    chunk = 0x8000
    for base in range(EWRAM_BASE, EWRAM_BASE + EWRAM_SIZE, chunk):
        blob = probe.dump(base, chunk)
        offset = blob.find(magic_bytes)
        while offset >= 0:
            if offset % 4 == 0:
                return base + offset
            offset = blob.find(magic_bytes, offset + 1)
    raise RuntimeError("the battle telemetry struct was not found in EWRAM")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", required=True)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    states = sorted(pathlib.Path(args.capture).glob("step-*.ss9"))
    print("savestates:", len(states))

    rows = []
    address = None
    with Probe(pathlib.Path(args.rom), exe=pathlib.Path(args.exe)) as probe:
        for state in states:
            probe.command(f"load {state}")
            if address is None:
                try:
                    address = find_telemetry(probe)
                except RuntimeError:
                    address = False
            if address is False:
                rows.append({"state": state.name, "telemetry": None})
                print(f"{state.name:<20} no telemetry struct in EWRAM")
                continue
            blob = probe.dump(address, BYTE_COUNT)
            words = struct.unpack(f"<{WORD_COUNT}I", blob)
            values = dict(zip(FIELDS, words))
            rows.append({"state": state.name, "telemetry": values})
            print(
                "{:<20} addr=0x{:08X} magic=0x{:08X} phase={:<20} "
                "battle_id={} round={} side={} sel_unit={} units={}/{} "
                "cmd={} cursor=({},{}) scene_frame={} render_stage={} "
                "busy={}".format(
                    state.name, address, values["magic"],
                    phase_name(values["phase"]), values["battle_id"],
                    values["round"], values["current_side"],
                    values["selected_unit"], values["active_unit_count"],
                    values["unit_count"], values["selected_command"],
                    values["cursor_x"], values["cursor_y"],
                    values["scene_frame"], values["render_stage"],
                    values["presentation_busy"],
                )
            )

    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                {
                    "rom": args.rom,
                    "capture": args.capture,
                    "telemetry_address": address,
                    "rows": rows,
                },
                handle, ensure_ascii=False, indent=1,
            )
        print("\nwrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
