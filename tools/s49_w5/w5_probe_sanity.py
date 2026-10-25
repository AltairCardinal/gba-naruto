#!/usr/bin/env python3
"""W5 -- sanity-check that the probe's savestate `load` really changes memory.

The remake's captured savestates were reloaded to look for the battle
telemetry struct by its magic, and no hit was found anywhere in EWRAM.  That
is only meaningful if the reload actually works, so this script checks the
IO register block against a reading the judgement bench already published
(``report.json``'s ``dispcnt_hex`` anchor) and dumps the raw words around the
telemetry address the wave-12 notes name (``0x02025EF0``).

Usage
-----
    python tools/s49_w5/w5_probe_sanity.py \
        --rom build/s49-package-u3-final/work/pinned-rom/measured.gba \
        --capture build/s49-package-u3-final/work/s49-report/capture-remake \
        --exe build/s49-wave18/w5/probe/mgba-probe.exe
"""

from __future__ import annotations

import argparse
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from s49_fidelity_report.probe import Probe  # noqa: E402

IO_BASE = 0x04000000
TELEMETRY_GUESS = 0x02025EF0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", required=True)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--exe", required=True)
    args = parser.parse_args()

    capture = pathlib.Path(args.capture)
    for name in ("step-13-A.ss9", "step-14-A.ss9", "step-21-A.ss9", "step-34-A.ss9"):
        state = capture / name
        if not state.exists():
            print(name, "missing")
            continue
        with Probe(pathlib.Path(args.rom), exe=pathlib.Path(args.exe)) as probe:
            probe.command(f"load {state}")
            io = probe.dump(IO_BASE, 0x40)
            dispcnt = struct.unpack_from("<I", io, 0)[0]
            blob = probe.dump(TELEMETRY_GUESS, 32)
            words = struct.unpack("<8I", blob)
            print(f"{name}: DISPCNT=0x{dispcnt:04X}")
            print("   0x02025EF0 words:", " ".join("0x%08X" % w for w in words))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
