#!/usr/bin/env python3
"""Read the battle scene's background registers out of a captured savestate.

The judgement bench reports ``bg_hofs`` as the three horizontal scroll
registers (BG0HOFS, BG1HOFS, BG2HOFS) masked to the register's nine bits.
This tool prints the *whole* IO register block plus the background control
registers and a digest of every background's tilemap, so the semantic meaning
of each scroll register can be established from the machine state instead of
guessed from the numbers.

Usage:
    python tools/s49_w20e3/bg_registers.py --rom <rom> --state <savestate> \
        [--state <savestate> ...] [--out <json>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO))

from s49_fidelity_report.probe import Probe  # noqa: E402

IO_BASE = 0x04000000
IO_LENGTH = 0x40
VRAM_BASE = 0x06000000
VRAM_LENGTH = 0x18000
EWRAM_BASE = 0x02000000
EWRAM_LENGTH = 0x40000

# The remake's battle scene telemetry (battle_runtime_scene.h).
TELEMETRY_MAGIC = 0x4B42544C
TELEMETRY_FIELDS = (
    "magic", "battle_id", "phase", "round", "current_side",
    "selected_unit", "active_unit_count", "unit_count", "selected_command",
    "player_completed", "enemy_completed", "scene_frame", "cursor_x",
    "cursor_y", "last_control_error", "last_player_error", "render_stage",
)

# GBA DISPCNT bits.
DISPCNT_BG = (0x0001, 0x0002, 0x0004, 0x0008)
DISPCNT_OBJ_1D = 0x0010
DISPCNT_OBJ_ENABLE = 0x0020
DISPCNT_WIN = (0x0040, 0x0080, 0x0100)
DISPCNT_OBJ_EXTENDED = 0x0800
DISPCNT_FORCED_BLANK = 0x8000

SCROLL_MASK = 0x1FF


def _word(blob: bytes, offset: int) -> int:
    return blob[offset] | (blob[offset + 1] << 8)


def decode_io(blob: bytes) -> dict:
    result = {
        "raw_hex": blob[:0x20].hex(),
        "dispcnt": _word(blob, 0x00),
        "bg_cnt": [_word(blob, 0x04 + 4 * index) for index in range(4)],
        "bg_hofs": [_word(blob, 0x06 + 4 * index) & SCROLL_MASK
                    for index in range(3)],
        "bg_hofs_raw": [_word(blob, 0x06 + 4 * index) for index in range(3)],
        "bg_vofs": [_word(blob, 0x14 + 4 * index) & SCROLL_MASK
                    for index in range(4)],
        "bg_vofs_raw": [_word(blob, 0x14 + 4 * index) for index in range(4)],
    }
    dispcnt = result["dispcnt"]
    result["dispcnt_flags"] = {
        "bg0": bool(dispcnt & DISPCNT_BG[0]),
        "bg1": bool(dispcnt & DISPCNT_BG[1]),
        "bg2": bool(dispcnt & DISPCNT_BG[2]),
        "bg3": bool(dispcnt & DISPCNT_BG[3]),
        "obj_1d": bool(dispcnt & DISPCNT_OBJ_1D),
        "obj_enable": bool(dispcnt & DISPCNT_OBJ_ENABLE),
        "win0": bool(dispcnt & DISPCNT_WIN[0]),
        "win1": bool(dispcnt & DISPCNT_WIN[1]),
        "obj_window": bool(dispcnt & DISPCNT_WIN[2]),
        "obj_extended": bool(dispcnt & DISPCNT_OBJ_EXTENDED),
        "forced_blank": bool(dispcnt & DISPCNT_FORCED_BLANK),
    }
    return result


def decode_bg(cnt: int) -> dict:
    size = (cnt >> 14) & 0x3
    return {
        "cnt": cnt,
        "cnt_hex": f"0x{cnt:04X}",
        "char_base_block": (cnt >> 2) & 0x3,
        "mosaic": bool(cnt & 0x40),
        "color_mode_256": bool(cnt & 0x80),
        "screen_base_block": (cnt >> 8) & 0x1F,
        "overflow": bool(cnt & 0x4000),
        "screen_size": ["256x256", "512x256", "256x512", "512x512"][size],
        "width_tiles": [32, 64, 32, 64][size],
        "height_tiles": [32, 32, 64, 64][size],
    }


def tilemap(vram: bytes, bg: dict) -> dict:
    base = bg["screen_base_block"] * 0x800
    width = bg["width_tiles"]
    height = bg["height_tiles"]
    size = width * height
    raw = vram[base:base + size * 2]
    indices = [raw[index] | (raw[index + 1] << 8) for index in range(0, len(raw), 2)]
    tiles = [value & 0x3FF for value in indices]
    return {
        "vram_base": base,
        "entries": size,
        "tile_index_sha256": hashlib.sha256(
            bytes(tiles)).hexdigest(),
        "first_row": tiles[:min(width, 64)],
        "unique_tile_indices": len(set(tiles)),
        "min_tile": min(tiles) if tiles else None,
        "max_tile": max(tiles) if tiles else None,
    }


def find_telemetry(ewram: bytes) -> dict | None:
    """The remake's battle scene telemetry, found by its magic value."""
    needle = TELEMETRY_MAGIC.to_bytes(4, "little")
    index = ewram.find(needle)
    if index < 0:
        return None
    values = {}
    for offset, name in enumerate(TELEMETRY_FIELDS):
        values[name] = int.from_bytes(
            ewram[index + 4 * offset:index + 4 * offset + 4], "little")
    values["ewram_address"] = f"0x{EWRAM_BASE + index:08X}"
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", required=True)
    parser.add_argument("--state", action="append", required=True)
    parser.add_argument("--probe", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    rom = pathlib.Path(args.rom)
    probe = pathlib.Path(args.probe) if args.probe else (
        REPO / "build" / "w20-e3" / "probe" / "mgba-probe.exe")

    report = {"rom": str(rom), "states": {}}
    with Probe(rom, probe) as device:
        for state in args.state:
            path = pathlib.Path(state)
            device.command(f"load {path}")
            io_blob = device.dump(IO_BASE, IO_LENGTH)
            vram = device.dump(VRAM_BASE, VRAM_LENGTH)
            record = decode_io(io_blob)
            record["backgrounds"] = []
            for index in range(4):
                bg = decode_bg(record["bg_cnt"][index])
                bg["index"] = index
                bg["enabled"] = bool(record["dispcnt"] & DISPCNT_BG[index])
                if bg["enabled"]:
                    bg["tilemap"] = tilemap(vram, bg)
                record["backgrounds"].append(bg)
            ewram = device.dump(EWRAM_BASE, EWRAM_LENGTH)
            record["telemetry"] = find_telemetry(ewram)
            report["states"][path.name] = record

    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        pathlib.Path(args.out).write_text(
            text + "\n", encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
