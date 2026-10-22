#!/usr/bin/env python3
"""Check the audio exporter's pitch model against the engine's own values.

The m4a engine computes a note's pitch in the ROM (``0x0809A998``) and
stores the resulting DirectSound register in the voice structure
(``0x0809A658``).  This tool reads the **engine's** own readings -- taken
with ``tools/closure_pitch_probe.py`` -- and checks that
``tools/audio_song_export.py``'s model produces exactly the same numbers:

* ``bend_pitch_offset`` must reproduce the channel's semitone offset
  (``channel+0x08``) and fraction (``channel+0x09``);
* ``engine_pitch_base`` must reproduce the pitch register the engine
  stored, i.e. ``(base * wave[4]) >> 32``.

Usage:
    python tools/closure_pitch_check.py build/closure-pitch-b60-r8.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools.audio_song_export import (  # noqa: E402
    bend_pitch_offset, engine_pitch_base, load_tables,
)

ROM_BASE = 0x08000000


def check(rom: bytes, tables: dict, record: dict) -> tuple[int, list[str]]:
    problems: list[str] = []
    checked = 0
    for hit in record.get("hits", []):
        if hit.get("address") != "0x0809A8E0":
            continue
        key = hit.get("key")
        wave = hit.get("wave")
        if key is None or wave is None:
            continue
        wave = int(wave, 16)
        offset = hit.get("bend_offset") or 0
        if offset > 127:
            offset -= 256
        fraction = hit.get("fraction") or 0
        got = int(hit["pitch"], 16)

        # 1. the bend accumulator the engine ran must match the tool's
        bend_cmd = hit.get("bend_cmd")
        bend_range = hit.get("bend_range")
        if bend_cmd is not None and bend_range is not None:
            if bend_cmd > 127:
                bend_cmd -= 256
            model_offset, model_fraction = bend_pitch_offset(bend_cmd, bend_range)
            if (model_offset, model_fraction) != (offset, fraction):
                problems.append(
                    "bend(%d, %d): tool says (%d, %d), engine has (%d, %d)"
                    % (bend_cmd, bend_range, model_offset, model_fraction,
                       offset, fraction))
                continue

        # 2. the pitch register must match the tool's interpolated base
        base = engine_pitch_base(tables, key + offset, fraction)
        w4 = struct.unpack_from("<I", rom, wave - ROM_BASE + 4)[0]
        want = (base * w4) >> 32
        checked += 1
        if want != got:
            problems.append(
                "key=%d offset=%d fraction=%d wave=0x%08X: engine 0x%08X, "
                "tool 0x%08X" % (key, offset, fraction, wave, got, want))
    return checked, problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("json", nargs="+", help="probe output files")
    args = ap.parse_args(argv)

    rom = (REPO / args.rom).read_bytes()
    tables = load_tables(rom)
    total = 0
    bad = 0
    for name in args.json:
        path = pathlib.Path(name)
        if not path.is_absolute():
            path = REPO / path
        record = json.loads(path.read_text(encoding="utf-8"))
        checked, problems = check(rom, tables, record)
        total += checked
        bad += len(problems)
        print(f"{path.name}: {checked} engine pitch readings checked, "
              f"{len(problems)} mismatch(es)")
        for line in problems[:10]:
            print("   " + line)
    print(f"TOTAL: {total} readings, {bad} mismatch(es)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
