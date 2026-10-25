#!/usr/bin/env python3
"""Trace the remake's boot window frame by frame.

Why this exists
---------------
The remake's boot shows 26 pure white frames (the GBA's forced blank) before
the first picture, while the original shows 2.  W18-W3 located the *symptom*
inside Butano's ``bn::core::init()`` but could not tell **where the 26 frames
are spent**: before the ROM reaches ``main()`` (ROM/BIOS start up), inside
``bn::core::init()``, or after it (the game's own boot work).

This instrument answers that with three cheap observations per frame, all
taken with the read-only probe's ``dump`` command (which does **not** advance
the frame, so a dump always belongs to the frame that was just run):

===========================  ==========  ===================================
watch address                size        what it tells
===========================  ==========  ===================================
0x04000000 (DISPCNT)         2 bytes     bit 15 = GBA forced blank (white)
0x05000000 (BG palette 0)     4 bytes     Butano's palette init has run
0x03002324 (handover slot)    4 bytes     main() has emplaced the boot
                                          background
0x06000000 (BG tile VRAM)     8 bytes     the background's tiles are on VRAM
===========================  ==========  ===================================

The frame numbers at which those four watch points move bracket the 26
frames, which is the "is/does" question the wave needs answered.

Usage::

    python tools/s49_w19c/boot_trace.py \
        --rom build/w19-c/butano-sequel/butano-sequel.gba \
        --out build/w19-c/boot-trace.json --frames 60
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys

HERE = pathlib.Path(os.path.abspath(__file__)).parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_victory_capture"))

from probe import Probe, ProbeError  # noqa: E402  (read-only reuse)

DEFAULT_PROBE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"

# address -> (label, size in bytes)
WATCHES: dict[int, tuple[str, int]] = {
    0x04000000: ("DISPCNT", 2),
    0x05000000: ("BG_PALETTE_0", 4),
    0x03002324: ("HANDOVER_SLOT", 4),
    0x0300231C: ("HANDOVER_DRAWN", 1),
    0x06000000: ("BG_TILE_VRAM", 8),
}


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--probe", type=pathlib.Path, default=DEFAULT_PROBE)
    args = parser.parse_args()

    if not args.rom.is_file():
        print(f"ERR rom missing: {args.rom}", file=sys.stderr)
        return 2
    if not args.probe.is_file():
        print(f"ERR probe missing: {args.probe}", file=sys.stderr)
        return 2

    rows: list[dict[str, object]] = []
    try:
        with Probe(args.rom, exe=args.probe, timeout=300.0) as device:
            for _ in range(args.frames):
                device.frames(1, 0)
                row: dict[str, object] = {"frame": len(rows) + 1}
                for address, (label, size) in WATCHES.items():
                    row[label] = device.dump(address, size).hex()
                rows.append(row)
    except ProbeError as error:
        print(f"ERR the probe failed: {error}", file=sys.stderr)
        return 1

    def first_change(label: str) -> int | None:
        previous = None
        for row in rows:
            value = row[label]
            if previous is not None and value != previous:
                return int(row["frame"])
            previous = value
        return None

    summary = {
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "frames": len(rows),
        "first_change": {
            label: first_change(label) for label, _ in WATCHES.values()
        },
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(summary, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({"rom_sha256": summary["rom_sha256"],
                      "frames": summary["frames"],
                      "first_change": summary["first_change"]},
                     ensure_ascii=False))
    print("->", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
