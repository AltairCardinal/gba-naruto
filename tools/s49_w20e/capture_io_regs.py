#!/usr/bin/env python3
"""Capture the *whole* IO register block of a walk's savestates.

Why this tool exists
--------------------
`tools/s49_w1/capture_original_state.py` decodes only three of the four BG
scroll registers:  it reports `bg_hofs` as `[BG0, BG1, BG2]` and stops there.
That is enough for the original (whose map layers sit on BG0..BG2) but it is
**wrong for the remake**, whose BG1 and BG2 have `BGCNT == 0` (unused) and
whose map lives on **BG3**.  Comparing the original's `bg_hofs[2]` with the
remake's `bg_hofs[2]` therefore compares two unrelated registers.

This tool dumps the raw IO block (0x04000000 .. 0x040003FF) of every savestate
of a walk and decodes *all four* BG layers, so the camera can be read off the
layer that actually carries the map on each side.

The convention is the repository's own: `load <state>` then
`framedump 1 0x04000000 0x400 0x000 <prefix>`, so every reading describes the
same frame as `tools/s49_w1/capture_original_state.py`.

Usage
-----
    python tools/s49_w20e/capture_io_regs.py \
        --capture-dir build/w20-e3/capture-remake \
        --rom build/w20-e3/butano-sequel/butano-sequel.gba \
        --exe build/mgba-probe-w20e3/mgba-probe.exe \
        --out build/w20-e3/io-remake.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROBE_CLIENT = REPO / "tools" / "mgba_probe" / "probe_client.py"

IO_ADDR = 0x04000000
IO_LEN = 0x400

SCREEN_SIZES = {
    0: (256, 256),
    1: (512, 256),
    2: (256, 512),
    3: (512, 512),
}


def decode_io(raw: bytes) -> dict:
    def u16(offset: int) -> int:
        return raw[offset] | (raw[offset + 1] << 8)

    dispcnt = u16(0x00)
    backgrounds = []
    for index in range(4):
        cnt = u16(0x08 + index * 2)
        hofs = u16(0x10 + index * 4)
        vofs = u16(0x12 + index * 4)
        size_code = (cnt >> 14) & 0x3
        width, height = SCREEN_SIZES[size_code]
        backgrounds.append({
            "index": index,
            "cnt": cnt,
            "cnt_hex": f"0x{cnt:04X}",
            "enabled": bool(dispcnt & (1 << index)),
            "priority": (cnt >> 7) & 0x3,
            "color_mode_256": bool(cnt & (1 << 3)),
            "mosaic": bool(cnt & (1 << 2)),
            "char_base_block": cnt & 0x3,
            "screen_base_block": (cnt >> 9) & 0x1F,
            "screen_size_px": f"{width}x{height}",
            "hofs_raw": hofs,
            "hofs": hofs & (0x3FF if width == 512 else 0x1FF),
            "vofs_raw": vofs,
            "vofs": vofs & (0x3FF if height == 512 else 0x1FF),
        })
    return {
        "dispcnt": dispcnt,
        "dispcnt_hex": f"0x{dispcnt:04X}",
        "dispcnt_flags": {
            "forced_blank": bool(dispcnt & (1 << 12)),
            "bg0": bool(dispcnt & 0x1),
            "bg1": bool(dispcnt & 0x2),
            "bg2": bool(dispcnt & 0x4),
            "bg3": bool(dispcnt & 0x8),
            "obj_enable": bool(dispcnt & 0x10),
            "win0": bool(dispcnt & 0x20),
            "win1": bool(dispcnt & 0x40),
            "obj_window": bool(dispcnt & 0x80),
            "obj_1d": bool(dispcnt & 0x100),
            "bg2_1d": bool(dispcnt & 0x400),
            "bg3_1d": bool(dispcnt & 0x800),
        },
        "backgrounds": backgrounds,
        "bg_hofs_all4": [b["hofs"] for b in backgrounds],
        "bg_vofs_all4": [b["vofs"] for b in backgrounds],
        "raw_hex": raw[:0x30].hex(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--capture-dir", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path, required=True)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    args = parser.parse_args()

    states = sorted(args.capture_dir.glob("step-*.ss9"))
    if not states:
        print(f"ERR no savestates under {args.capture_dir}")
        return 2

    dump_dir = args.out.parent / (args.out.stem + "-raw")
    dump_dir.mkdir(parents=True, exist_ok=True)

    commands: list[str] = []
    prefixes: list[pathlib.Path] = []
    for state in states:
        prefix = dump_dir / state.stem
        prefixes.append(prefix)
        commands.append(f"load {state}")
        commands.append(f"framedump 1 0x{IO_ADDR:08X} {IO_LEN} 0x000 {prefix}")

    argv = [sys.executable, str(PROBE_CLIENT), "--exe", str(args.exe),
            "--rom", str(args.rom)]
    for command in commands:
        argv += ["--cmd", command]
    argv += ["--out", str(dump_dir / "probe.json")]
    print(f"dumping IO for {len(states)} states ...")
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=1800)
    document = json.loads((dump_dir / "probe.json").read_text(encoding="utf-8"))
    bad = [step for step in document["steps"] if step["status"] != "ok"]
    if bad:
        print(f"ERR probe step failed: {bad[0]['command']}: {bad[0]['output']}")
        return 1

    states_out = {}
    for state, prefix in zip(states, prefixes):
        blob = (dump_dir / f"{prefix.name}-0000.bin").read_bytes()
        states_out[state.stem] = decode_io(blob)
        print(f"  {state.stem}: dispcnt={states_out[state.stem]['dispcnt_hex']} "
              f"hofs={states_out[state.stem]['bg_hofs_all4']} "
              f"vofs={states_out[state.stem]['bg_vofs_all4']}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({
            "rom": str(args.rom),
            "capture_dir": str(args.capture_dir),
            "states": states_out,
        }, handle, ensure_ascii=False, indent=1)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
