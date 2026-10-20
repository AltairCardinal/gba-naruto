#!/usr/bin/env python3
"""Battle character sprite animation format (action table at 0x596CCC).

Derived and re-verified against `rom/base.gba` (Konoha Senki).  The
derivation, the verification commands and the measured numbers live in
`notes/sprite-frame-format-20261020.md`.

Layout
------
action table   0x596CCC + id*144 + action*16 -> 4 x u32 ROM pointers
               (frames, animations, gfx, palette)

frames ptr     u32[] of frame-descriptor pointers.  The array has *no*
               terminator of its own: it ends where the first word that is
               not a ROM pointer appears, and in this ROM that word is the
               first animation descriptor, which follows immediately.
frame descr    list of 20-byte parts, terminated by a part whose tile index
               is 0xFFFF.
part           u16 tile, u16 flags, s16 x, s16 y, u16 w, u16 h, u16 256,
               u16 256
gfx            raw 4bpp tile data, 32 bytes per 8x8 tile.  A part's `tile`
               is a tile index into that blob, so a part needs
               `tile*32 + w*h/2` bytes.
palette        16 x u16 BGR555 (32 bytes), stored at its own pointer.

The tool never guesses: every pointer, terminator and size is checked
against the ROM, and anything that does not add up is reported as an
anomaly instead of being silently dropped.

Usage
-----
    python tools/sprite_frames.py rom/base.gba --stats
    python tools/sprite_frames.py rom/base.gba --id 3 --action 0
    python tools/sprite_frames.py rom/base.gba --json build/sprites.json
    python tools/sprite_frames.py rom/base.gba --check
    python tools/sprite_frames.py rom/base.gba --id 3 --png-dir build/png
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools import text_codec  # noqa: E402
from tools.lib.io import write_text  # noqa: E402

ROM_BASE = 0x08000000
SPRITE_TABLE = 0x596CCC
ID_STRIDE = 144
ACTION_STRIDE = 16
ACTIONS_PER_ID = ID_STRIDE // ACTION_STRIDE
MAX_FRAMES = 256
MAX_PARTS = 32
PART_STRIDE = 20
TILE_BYTES = 32
PALETTE_COLORS = 16
PALETTE_STRIDE = 2
TEMPLATE_W = 128
TEMPLATE_H = 128
ANCHOR_X = 64
ANCHOR_Y = 96
ALLOWED_SIZES = (8, 16, 32, 64)
MAX_ANIM_ENTRIES = 1024
MAX_ANIM_PTRS = 256
DEFAULT_MIN_ID = 1
DEFAULT_MAX_ID = 62
INDEX_USAGE_PIXEL_BUDGET = 2_000_000

# A single byte in the shipped ROM is corrupt: the piece-list terminator of
# character 26 / action 2 / frame 2 is `0xFBFF` where it should be `0xFFFF`
# (ROM offset 0x25A8E5 holds 0xFB instead of 0xFF).  The original ROM in the
# repository root is byte-identical to rom/base.gba, so the defect ships with
# the ROM and is not caused by our tooling.  See
# notes/sprite-frame-format-20261020.md section 5.1.
#
# `--check` tolerates violations that are attributable to a known defect so it
# can be used as a gate; the violations are still printed.  `--strict-rom`
# puts them back into the failure decision.
KNOWN_ROM_DEFECTS = {
    (26, 2): "ROM offset 0x25A8E5 is 0xFB, should be 0xFF (ROM-native defect)",
}


# --------------------------------------------------------------------------
# ROM access
# --------------------------------------------------------------------------
def u16(rom: bytes, off: int) -> int:
    return int.from_bytes(rom[off:off + 2], "little")


def u32(rom: bytes, off: int) -> int:
    return int.from_bytes(rom[off:off + 4], "little")


def s16(rom: bytes, off: int) -> int:
    v = u16(rom, off)
    return v - 0x10000 if v >= 0x8000 else v


def ptr_offset(value: int) -> int:
    """ROM offset of a GBA pointer, or -1 when the word is not a pointer."""
    off = value - ROM_BASE
    return off if off >= 0 else -1


def hexoff(value: int | None) -> str | None:
    return None if value is None else f"0x{value:08X}"


def word_kind(value: int, rom_len: int) -> str:
    """Classify a word that ended a pointer table."""
    off = ptr_offset(value)
    if value == 0:
        return "zero"
    if off < 0:
        return "not_a_pointer"
    if off >= rom_len:
        return "out_of_rom"
    return "pointer"


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
def template_overflow(part: dict) -> dict:
    """How far a part sticks out of the 128x128 sprite-sheet cell."""
    left = ANCHOR_X + part["x"]
    top = ANCHOR_Y + part["y"]
    right = left + part["w"]
    bottom = top + part["h"]
    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "overflow_left": max(0, -left),
        "overflow_top": max(0, -top),
        "overflow_right": max(0, right - TEMPLATE_W),
        "overflow_bottom": max(0, bottom - TEMPLATE_H),
        "ok": (left >= 0 and top >= 0 and right <= TEMPLATE_W
               and bottom <= TEMPLATE_H),
    }


def part_is_valid(part: dict) -> bool:
    return (part["w"] in ALLOWED_SIZES and part["h"] in ALLOWED_SIZES
            and part["scale_x"] == 256 and part["scale_y"] == 256)


def read_parts(rom: bytes, off: int, anomalies: list) -> tuple[list, bool, int]:
    """Read one frame's part list.

    Returns (parts, terminated, terminator_word).  `terminator_word` is the
    raw u16 that ended the list, or -1 when the list ran out.
    """
    parts: list[dict] = []
    for j in range(MAX_PARTS):
        q = off + j * PART_STRIDE
        if q + PART_STRIDE > len(rom):
            anomalies.append({
                "code": "parts_out_of_rom",
                "detail": f"part {j} at {hexoff(q)} runs past the ROM",
            })
            return parts, False, -1
        tile, flags, x, y, w, h, scale_x, scale_y = struct.unpack_from(
            "<HHhhHHHH", rom, q)
        if tile == 0xFFFF:
            return parts, True, tile
        part = {
            "index": j,
            "offset": q,
            "tile": tile,
            "flags": flags,
            "flip_x": bool(flags & 1),
            "flip_y": bool(flags & 2),
            "flags_unknown": flags & ~0x3,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "scale_x": scale_x,
            "scale_y": scale_y,
            "tiles": (w // 8) * (h // 8) if w % 8 == 0 and h % 8 == 0 else 0,
            "bytes": (w * h) // 2,
        }
        part["template"] = template_overflow(part)
        parts.append(part)
        if not part_is_valid(part):
            # A part whose size/scale fields are nonsense cannot be a real
            # part.  In this ROM exactly one such word exists: a corrupted
            # list terminator.  Stop here and report it.
            anomalies.append({
                "code": "parts_terminator_corrupted",
                "detail": f"part {j} at {hexoff(q)} has tile=0x{tile:04X} "
                          f"{w}x{h} scale {scale_x}x{scale_y}; expected a "
                          f"0xFFFF terminator here",
            })
            return parts, False, tile
    anomalies.append({
        "code": "parts_unterminated",
        "detail": f"no 0xFFFF tile terminator within {MAX_PARTS} parts at "
                  f"{hexoff(off)}",
    })
    return parts, False, -1


def read_animations(rom: bytes, off: int, anomalies: list) -> tuple[list, dict]:
    """Read the animation pointer table and the descriptors it points at."""
    animations: list[dict] = []
    terminator = {"word": None, "kind": None}
    for i in range(MAX_ANIM_PTRS):
        p = off + i * 4
        if p + 4 > len(rom):
            anomalies.append({
                "code": "anim_ptr_table_out_of_rom",
                "detail": f"pointer slot {i} at {hexoff(p)} runs past the ROM",
            })
            break
        raw = u32(rom, p)
        target = ptr_offset(raw)
        if raw == 0:
            terminator = {"word": hexoff(raw), "kind": "zero"}
            break
        if target < 0 or target >= len(rom):
            terminator = {"word": hexoff(raw),
                          "kind": word_kind(raw, len(rom))}
            break
        entries: list[dict] = []
        terminated = False
        for j in range(MAX_ANIM_ENTRIES):
            q = target + j * 4
            if q + 4 > len(rom):
                anomalies.append({
                    "code": "anim_desc_out_of_rom",
                    "detail": f"animation {i} entry {j} at {hexoff(q)} "
                              f"runs past the ROM",
                })
                break
            frame = u16(rom, q)
            b2 = rom[q + 2]
            b3 = rom[q + 3]
            if frame == 0xFFFF:
                terminated = True
                break
            entries.append({"frame": frame, "b2": b2, "b3": b3})
        if not terminated:
            anomalies.append({
                "code": "anim_desc_unterminated",
                "detail": f"animation {i} at {hexoff(target)} has no 0xFFFF "
                          f"terminator within {MAX_ANIM_ENTRIES} entries",
            })
        animations.append({
            "index": i,
            "pointer": hexoff(raw),
            "offset": target,
            "entries": entries,
            "entry_count": len(entries),
            "bytes": (len(entries) + 1) * 4,
        })
    else:
        anomalies.append({
            "code": "anim_ptr_table_unterminated",
            "detail": f"animation pointer table at {hexoff(off)} has no zero "
                      f"slot within {MAX_ANIM_PTRS} entries",
        })
    return animations, terminator


def read_action(rom: bytes, sid: int, action: int) -> dict:
    """Parse one (id, action) entry of the sprite action table."""
    entry = SPRITE_TABLE + sid * ID_STRIDE + action * ACTION_STRIDE
    rec: dict = {
        "id": sid,
        "action": action,
        "entry_offset": entry,
        "frames_ptr": None,
        "animations_ptr": None,
        "gfx_ptr": None,
        "palette_ptr": None,
        "frames_ptr_off": None,
        "animations_ptr_off": None,
        "gfx_off": None,
        "palette_off": None,
        "frames": [],
        "frame_count": 0,
        "part_count": 0,
        "gfx_bytes": 0,
        "gfx_bytes_8bpp": 0,
        "gfx_span_end": None,
        "gfx_tiles": 0,
        "gfx_next_resource": None,
        "gfx_contiguous": None,
        "gfx_contiguous_8bpp": None,
        "tiles_contiguous": None,
        "palette": [],
        "animations": [],
        "frames_terminator": None,
        "anim_ptr_terminator": None,
        "unused": False,
        "anomalies": [],
    }
    anomalies: list = rec["anomalies"]

    if entry + ACTION_STRIDE > len(rom):
        anomalies.append({
            "code": "action_entry_out_of_rom",
            "detail": f"entry at {hexoff(entry)} runs past the ROM",
        })
        return rec

    raw = [u32(rom, entry + i * 4) for i in range(4)]
    rec["frames_ptr"] = hexoff(raw[0])
    rec["animations_ptr"] = hexoff(raw[1])
    rec["gfx_ptr"] = hexoff(raw[2])
    rec["palette_ptr"] = hexoff(raw[3])
    offsets = [ptr_offset(v) for v in raw]

    if all(v == 0 for v in raw):
        # A completely empty slot is an unused (id, action) pair, not a
        # broken entry.
        rec["unused"] = True
        return rec

    for name, value, off in zip(
            ("frames", "animations", "gfx", "palette"), raw, offsets):
        if value == 0:
            anomalies.append({
                "code": "null_pointer",
                "detail": f"{name} pointer is 0 at {hexoff(entry)}",
            })
        elif off < 0:
            anomalies.append({
                "code": "pointer_not_a_rom_pointer",
                "detail": f"{name} pointer {hexoff(value)} at {hexoff(entry)}",
            })
        elif off >= len(rom):
            anomalies.append({
                "code": "pointer_out_of_rom",
                "detail": f"{name} pointer {hexoff(value)} at {hexoff(entry)}",
            })

    frames_off, anim_off, gfx_off, pal_off = offsets
    rec["frames_ptr_off"] = frames_off if frames_off >= 0 else None
    rec["animations_ptr_off"] = anim_off if anim_off >= 0 else None
    rec["gfx_off"] = gfx_off if gfx_off >= 0 else None
    rec["palette_off"] = pal_off if pal_off >= 0 else None

    # ---- frame pointer table -------------------------------------------
    if frames_off >= 0 and frames_off < len(rom):
        terminator = None
        for i in range(MAX_FRAMES):
            p = frames_off + i * 4
            if p + 4 > len(rom):
                anomalies.append({
                    "code": "frames_table_out_of_rom",
                    "detail": f"frame pointer slot {i} at {hexoff(p)} runs "
                              f"past the ROM",
                })
                terminator = {"word": None, "kind": "out_of_rom"}
                break
            value = u32(rom, p)
            target = ptr_offset(value)
            if target < 0 or target >= len(rom):
                terminator = {"word": hexoff(value),
                              "kind": word_kind(value, len(rom))}
                break
            parts, terminated, term_word = read_parts(rom, target, anomalies)
            if not parts:
                terminator = {"word": hexoff(value), "kind": "empty_frame"}
                break
            rec["frames"].append({
                "index": i,
                "descriptor_ptr": hexoff(value),
                "descriptor_offset": target,
                "parts": parts,
                "part_count": len(parts),
                "terminated": terminated,
                "terminator_word": (hexoff(term_word)
                                     if term_word >= 0 else None),
            })
        else:
            anomalies.append({
                "code": "frames_table_unterminated",
                "detail": f"no non-pointer word within {MAX_FRAMES} slots "
                          f"at {hexoff(frames_off)}",
            })
            terminator = {"word": None, "kind": "limit_reached"}
        rec["frames_terminator"] = terminator
    else:
        rec["frames_terminator"] = None

    rec["frame_count"] = len(rec["frames"])
    rec["part_count"] = sum(f["part_count"] for f in rec["frames"])

    # ---- gfx span -------------------------------------------------------
    gfx_bytes = 0
    gfx_bytes_8bpp = 0
    max_tile = 0
    for frame in rec["frames"]:
        for part in frame["parts"]:
            gfx_bytes = max(gfx_bytes,
                             part["tile"] * TILE_BYTES + part["bytes"])
            gfx_bytes_8bpp = max(gfx_bytes_8bpp,
                                 part["tile"] * TILE_BYTES * 2 + part["bytes"] * 2)
            max_tile = max(max_tile, part["tile"])
    rec["gfx_bytes"] = gfx_bytes
    rec["gfx_bytes_8bpp"] = gfx_bytes_8bpp
    rec["gfx_tiles"] = (max_tile + 1) if max_tile else 0
    if gfx_off >= 0:
        rec["gfx_span_end"] = gfx_off + gfx_bytes
        if gfx_off + gfx_bytes > len(rom):
            anomalies.append({
                "code": "gfx_out_of_rom",
                "detail": f"gfx at {hexoff(gfx_off)} needs {gfx_bytes} bytes "
                          f"but the ROM ends at {hexoff(len(rom))}",
            })

    # ---- palette --------------------------------------------------------
    if pal_off >= 0:
        if pal_off + PALETTE_COLORS * PALETTE_STRIDE > len(rom):
            anomalies.append({
                "code": "palette_out_of_rom",
                "detail": f"palette at {hexoff(pal_off)} runs past the ROM",
            })
        else:
            rec["palette"] = [
                u16(rom, pal_off + i * PALETTE_STRIDE)
                for i in range(PALETTE_COLORS)
            ]

    # ---- animations -----------------------------------------------------
    if anim_off >= 0 and anim_off < len(rom):
        rec["animations"], rec["anim_ptr_terminator"] = read_animations(
            rom, anim_off, anomalies)

    # ---- per-part consistency -------------------------------------------
    for frame in rec["frames"]:
        for part in frame["parts"]:
            if part["w"] not in ALLOWED_SIZES or part["h"] not in ALLOWED_SIZES:
                anomalies.append({
                    "code": "part_size_invalid",
                    "detail": f"id {sid} action {action} frame "
                              f"{frame['index']} part {part['index']}: "
                              f"{part['w']}x{part['h']}",
                })
            if part["scale_x"] != 256 or part["scale_y"] != 256:
                anomalies.append({
                    "code": "part_scale_invalid",
                    "detail": f"id {sid} action {action} frame "
                              f"{frame['index']} part {part['index']}: "
                              f"scale {part['scale_x']}x{part['scale_y']}",
                })
            if not part["template"]["ok"]:
                anomalies.append({
                    "code": "part_out_of_template",
                    "detail": f"id {sid} action {action} frame "
                              f"{frame['index']} part {part['index']}: "
                              f"x={part['x']} y={part['y']} "
                              f"{part['w']}x{part['h']} overflows "
                              f"L{part['template']['overflow_left']} "
                              f"T{part['template']['overflow_top']} "
                              f"R{part['template']['overflow_right']} "
                              f"B{part['template']['overflow_bottom']}",
                })
            if gfx_off >= 0 and gfx_off + part["tile"] * TILE_BYTES \
                    + part["bytes"] > len(rom):
                anomalies.append({
                    "code": "part_gfx_out_of_rom",
                    "detail": f"id {sid} action {action} frame "
                              f"{frame['index']} part {part['index']}: tile "
                              f"{part['tile']} runs past the ROM",
                })

    # ---- metadata / gfx adjacency ---------------------------------------
    meta = [f["descriptor_offset"] for f in rec["frames"]]
    if frames_off is not None and frames_off >= 0:
        meta.append(frames_off)
    if anim_off is not None and anim_off >= 0:
        meta.append(anim_off)
    if gfx_off is not None and gfx_off >= 0 and meta:
        after = [m for m in meta if m > gfx_off]
        if after:
            boundary = min(after)
            rec["gfx_next_resource"] = hexoff(boundary)
            rec["gfx_contiguous"] = (gfx_off + gfx_bytes == boundary)
            rec["gfx_contiguous_8bpp"] = (gfx_off + gfx_bytes_8bpp == boundary)
            if gfx_off < boundary < gfx_off + gfx_bytes:
                anomalies.append({
                    "code": "gfx_overlaps_metadata",
                    "detail": f"gfx span {hexoff(gfx_off)}.."
                              f"{hexoff(gfx_off + gfx_bytes)} overlaps "
                              f"{hexoff(boundary)}",
                })

    # ---- tile index contiguity ------------------------------------------
    if rec["frames"]:
        used = set()
        for frame in rec["frames"]:
            for part in frame["parts"]:
                if not part_is_valid(part):
                    continue
                start = part["tile"]
                used.update(range(start, start + part["tiles"]))
        rec["tiles_contiguous"] = bool(used) and min(used) == 0 and \
            max(used) + 1 == len(used)
    return rec


def collect(rom: bytes, ids: range, actions: range) -> list:
    return [read_action(rom, sid, act) for sid in ids for act in actions]


# --------------------------------------------------------------------------
# Rendering (verification aid)
# --------------------------------------------------------------------------
def part_pixel(rom: bytes, gfx_off: int, part: dict, px: int, py: int) -> int:
    """4bpp palette index of pixel (px, py) inside a part."""
    if part["flip_x"]:
        px = part["w"] - 1 - px
    if part["flip_y"]:
        py = part["h"] - 1 - py
    src = (gfx_off + part["tile"] * TILE_BYTES
           + ((py >> 3) * (part["w"] >> 3) + (px >> 3)) * TILE_BYTES
           + (py & 7) * 4 + ((px & 7) >> 1))
    return (rom[src] >> ((px & 1) * 4)) & 0xF


def bgr555_to_rgb(value: int) -> tuple:
    r = (value >> 10) & 31
    g = (value >> 5) & 31
    b = value & 31
    return (r * 255 // 31, g * 255 // 31, b * 255 // 31)


def render_action(rom: bytes, rec: dict):
    """Render one action into a PIL image (5 frames per row, 128px cells)."""
    from PIL import Image

    frames = rec["frames"]
    if not frames:
        return None
    cols = 5
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * TEMPLATE_W, rows * TEMPLATE_H),
                      (0, 0, 0, 0))
    gfx_off = rec["gfx_off"]
    if gfx_off is None or gfx_off < 0:
        return sheet
    palette = rec["palette"]
    for frame in frames:
        cell_x = (frame["index"] % cols) * TEMPLATE_W
        cell_y = (frame["index"] // cols) * TEMPLATE_H
        for part in frame["parts"]:
            if not part_is_valid(part):
                continue
            for py in range(part["h"]):
                for px in range(part["w"]):
                    idx = part_pixel(rom, gfx_off, part, px, py)
                    if idx == 0 or idx >= len(palette):
                        continue
                    dx = cell_x + ANCHOR_X + part["x"] + px
                    dy = cell_y + ANCHOR_Y + part["y"] + py
                    if 0 <= dx < sheet.width and 0 <= dy < sheet.height:
                        sheet.putpixel((dx, dy),
                                       bgr555_to_rgb(palette[idx]) + (255,))
    return sheet


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------
def build_stats(records: list, rom: bytes) -> dict:
    anomaly_codes = Counter()
    frame_counts = Counter()
    parts_per_frame = Counter()
    sizes = Counter()
    flags = Counter()
    flip_x = flip_y = 0
    total_parts = 0
    total_gfx = 0
    total_gfx_valid = 0
    actions_with_data = 0
    ids_with_data = set()
    palette_index_use = Counter()
    template_ok = 0
    template_bad = 0
    contiguous = 0
    contiguous_8bpp = 0
    tiles_contiguous = 0
    action_usage: dict = {}
    palettes: dict = {}
    anim_b2 = Counter()
    anim_b3 = Counter()
    anim_entries = Counter()
    anim_descriptors = 0
    frames_term_kind = Counter()
    anim_term_kind = Counter()
    for rec in records:
        for a in rec["anomalies"]:
            anomaly_codes[a["code"]] += 1
        if rec["frame_count"]:
            actions_with_data += 1
            ids_with_data.add(rec["id"])
            frame_counts[rec["frame_count"]] += 1
            total_gfx += rec["gfx_bytes"]
            if rec["gfx_contiguous"]:
                total_gfx_valid += rec["gfx_bytes"]
            action_usage.setdefault(str(rec["action"]), {})[str(rec["id"])] = \
                rec["frame_count"]
            if rec["palette"]:
                palettes.setdefault(tuple(rec["palette"]), []).append(
                    (rec["id"], rec["action"]))
            if rec["gfx_contiguous"]:
                contiguous += 1
            if rec["gfx_contiguous_8bpp"]:
                contiguous_8bpp += 1
            if rec["tiles_contiguous"]:
                tiles_contiguous += 1
        if rec["frames_terminator"]:
            frames_term_kind[rec["frames_terminator"]["kind"]] += 1
        if rec["anim_ptr_terminator"]:
            anim_term_kind[rec["anim_ptr_terminator"]["kind"]] += 1
        anim_descriptors += len(rec["animations"])
        for anim in rec["animations"]:
            anim_entries[anim["entry_count"]] += 1
            for e in anim["entries"]:
                anim_b2[e["b2"]] += 1
                anim_b3[e["b3"]] += 1
        for frame in rec["frames"]:
            parts_per_frame[frame["part_count"]] += 1
            for part in frame["parts"]:
                total_parts += 1
                sizes[f"{part['w']}x{part['h']}"] += 1
                flags[part["flags"]] += 1
                if part["flip_x"]:
                    flip_x += 1
                if part["flip_y"]:
                    flip_y += 1
                if part["template"]["ok"]:
                    template_ok += 1
                else:
                    template_bad += 1
    # Palette index histogram over the real pixel data.  Bounded so the
    # overview stays fast on a full sweep.
    budget = INDEX_USAGE_PIXEL_BUDGET
    for rec in records:
        if budget <= 0:
            break
        gfx_off = rec["gfx_off"]
        if not rec["frames"] or gfx_off is None or gfx_off < 0:
            continue
        for frame in rec["frames"]:
            for part in frame["parts"]:
                if budget <= 0:
                    break
                if not part_is_valid(part):
                    continue
                for py in range(part["h"]):
                    for px in range(part["w"]):
                        budget -= 1
                        palette_index_use[
                            part_pixel(rom, gfx_off, part, px, py)
                        ] += 1
    return {
        "actions_scanned": len(records),
        "actions_with_frames": actions_with_data,
        "ids_with_frames": sorted(ids_with_data),
        "ids_with_frames_count": len(ids_with_data),
        "action_usage": action_usage,
        "total_frames": sum(r["frame_count"] for r in records),
        "total_parts": total_parts,
        "total_gfx_bytes": total_gfx,
        "total_gfx_bytes_valid_actions": total_gfx_valid,
        "distinct_palettes": len(palettes),
        "gfx_contiguous_4bpp": contiguous,
        "gfx_contiguous_8bpp": contiguous_8bpp,
        "tile_index_contiguous": tiles_contiguous,
        "frame_count_histogram": {str(k): v for k, v in sorted(frame_counts.items())},
        "parts_per_frame_histogram": {str(k): v
                                      for k, v in sorted(parts_per_frame.items())},
        "part_size_histogram": dict(sorted(sizes.items())),
        "flags_histogram": {str(k): v for k, v in sorted(flags.items())},
        "flip_x_parts": flip_x,
        "flip_y_parts": flip_y,
        "parts_inside_template": template_ok,
        "parts_outside_template": template_bad,
        "palette_index_usage": {str(k): v for k, v in
                                 sorted(palette_index_use.items())},
        "frames_terminator_kinds": dict(sorted(frames_term_kind.items())),
        "anim_ptr_terminator_kinds": dict(sorted(anim_term_kind.items())),
        "anim_descriptors": anim_descriptors,
        "anim_entries_per_descriptor": {str(k): v
                                        for k, v in sorted(anim_entries.items())},
        "anim_entry_b2": {str(k): v for k, v in sorted(anim_b2.items())},
        "anim_entry_b3": {str(k): v for k, v in sorted(anim_b3.items())},
        "anomaly_counts": dict(sorted(anomaly_codes.items())),
        "anomaly_total": sum(anomaly_codes.values()),
    }


def print_stats(records: list, stats: dict, rom_path: pathlib.Path) -> None:
    print(f"ROM                : {rom_path}")
    print(f"action table       : {hexoff(SPRITE_TABLE)} "
          f"(id*{ID_STRIDE} + action*{ACTION_STRIDE})")
    print(f"actions scanned    : {stats['actions_scanned']}")
    print(f"actions with frames: {stats['actions_with_frames']}")
    print(f"ids with frames    : {stats['ids_with_frames_count']} "
          f"{stats['ids_with_frames']}")
    print(f"total frames       : {stats['total_frames']}")
    print(f"total parts        : {stats['total_parts']}")
    print(f"total gfx bytes    : {stats['total_gfx_bytes']} "
          f"(valid actions only: {stats['total_gfx_bytes_valid_actions']})")
    print(f"distinct palettes  : {stats['distinct_palettes']}")
    print()
    print("action usage (action -> #ids, frame counts):")
    for act in sorted(stats["action_usage"], key=int):
        ids = stats["action_usage"][act]
        counts = sorted(set(ids.values()))
        print(f"  action {act}: {len(ids)} ids, frames {counts}")
    print()
    print("frame count histogram (frames -> actions):")
    for k, v in stats["frame_count_histogram"].items():
        print(f"  {k:>4} frames : {v} actions")
    print("parts per frame histogram:")
    for k, v in stats["parts_per_frame_histogram"].items():
        print(f"  {k:>4} parts  : {v} frames")
    print("part size histogram:")
    for k, v in stats["part_size_histogram"].items():
        print(f"  {k:>9} : {v} parts")
    print("flags histogram:")
    for k, v in stats["flags_histogram"].items():
        print(f"  flags={k} : {v} parts")
    print(f"flip_x parts: {stats['flip_x_parts']}   "
          f"flip_y parts: {stats['flip_y_parts']}")
    print()
    print(f"parts inside 128x128 template : {stats['parts_inside_template']}")
    print(f"parts outside 128x128 template: {stats['parts_outside_template']}")
    print(f"gfx span contiguous (4bpp hyp) : {stats['gfx_contiguous_4bpp']} "
          f"of {stats['actions_with_frames']}")
    print(f"gfx span contiguous (8bpp hyp) : {stats['gfx_contiguous_8bpp']} "
          f"of {stats['actions_with_frames']}")
    print(f"tile index contiguous from 0   : {stats['tile_index_contiguous']} "
          f"of {stats['actions_with_frames']}")
    print(f"palette index usage            : {stats['palette_index_usage']}")
    print()
    print(f"frames-table terminator kinds  : {stats['frames_terminator_kinds']}")
    print(f"anim-table terminator kinds    : {stats['anim_ptr_terminator_kinds']}")
    print(f"animation descriptors          : {stats['anim_descriptors']}")
    print(f"entries per descriptor         : "
          f"{stats['anim_entries_per_descriptor']}")
    print(f"animation entry byte 2 (b2)    : {stats['anim_entry_b2']}")
    print(f"animation entry byte 3 (b3)    : {stats['anim_entry_b3']}")
    print()
    print("anomalies:")
    if not stats["anomaly_counts"]:
        print("  (none)")
    for code, v in stats["anomaly_counts"].items():
        print(f"  {code:<32} {v}")
    print(f"  {'TOTAL':<32} {stats['anomaly_total']}")


def print_action(rec: dict) -> None:
    print(f"id {rec['id']} action {rec['action']} @ {hexoff(rec['entry_offset'])}")
    print(f"  frames ptr      : {rec['frames_ptr']} "
          f"(off {hexoff(rec['frames_ptr_off'])})")
    print(f"  animations ptr  : {rec['animations_ptr']} "
          f"(off {hexoff(rec['animations_ptr_off'])})")
    print(f"  gfx ptr         : {rec['gfx_ptr']} (off {hexoff(rec['gfx_off'])})")
    print(f"  palette ptr     : {rec['palette_ptr']} "
          f"(off {hexoff(rec['palette_off'])})")
    print(f"  frames          : {rec['frame_count']}  "
          f"parts: {rec['part_count']}  "
          f"terminator: {rec.get('frames_terminator')}")
    print(f"  gfx bytes       : {rec['gfx_bytes']} "
          f"(span {hexoff(rec['gfx_off'])}..{hexoff(rec['gfx_span_end'])}, "
          f"next={rec.get('gfx_next_resource')}, "
          f"contiguous={rec.get('gfx_contiguous')})")
    print(f"  animations      : {len(rec['animations'])} "
          f"(table terminator {rec.get('anim_ptr_terminator')})")
    if rec["palette"]:
        print(f"  palette (BGR555): "
              f"{' '.join(f'{v:04X}' for v in rec['palette'])}")
    for frame in rec["frames"]:
        for part in frame["parts"]:
            t = part["template"]
            flag = "" if t["ok"] else "  <-- OUT OF TEMPLATE"
            print(f"    f{frame['index']:<3} tile={part['tile']:<6} "
                  f"flags={part['flags']} "
                  f"x={part['x']:<5} y={part['y']:<5} "
                  f"{part['w']}x{part['h']} "
                  f"tiles={part['tiles']} bytes={part['bytes']}"
                  f"{flag}")
    for a in rec["anomalies"]:
        print(f"    !! {a['code']}: {a['detail']}")


def run_checks(records: list, strict_rom: bool = False) -> int:
    """Run the format invariants that the derivation rests on.

    Violations that are attributable to a documented ROM-native defect are
    reported but do not fail the run, unless `strict_rom` is set.
    """
    live = [r for r in records if r["frame_count"]]
    print("format invariants")
    print("-" * 72)

    c1 = [r for r in live if r["gfx_contiguous"]]
    c1b = [r for r in live if r["gfx_contiguous_8bpp"]]
    print(f"C1 gfx span ends exactly at the next resource (4bpp): "
          f"{len(c1)}/{len(live)} PASS"
          if len(c1) == len(live) else
          f"C1 gfx span ends exactly at the next resource (4bpp): "
          f"{len(c1)}/{len(live)} FAIL "
          f"{[(r['id'], r['action']) for r in live if not r['gfx_contiguous']]}")
    print(f"C1' same test under the 8bpp hypothesis (64 B/tile): "
          f"{len(c1b)}/{len(live)} "
          f"{'PASS' if len(c1b) < len(live) else 'FAIL'} "
          f"(must FAIL for the 4bpp reading to be the right one)")

    bad_size = [(r, p) for r in live for f in r["frames"]
                for p in f["parts"]
                if p["w"] not in ALLOWED_SIZES or p["h"] not in ALLOWED_SIZES]
    print(f"C2 every part size is 8/16/32/64: "
          f"{len(live) and len(bad_size) == 0} "
          f"({len(bad_size)} violations)")

    bad_scale = [(r, p) for r in live for f in r["frames"]
                 for p in f["parts"]
                 if p["scale_x"] != 256 or p["scale_y"] != 256]
    print(f"C3 every part scale field is 256/256: "
          f"{len(bad_scale) == 0} ({len(bad_scale)} violations)")

    bad_tpl = [(r, p) for r in live for f in r["frames"]
               for p in f["parts"] if not p["template"]["ok"]]
    print(f"C4 every part fits the 128x128 cell: "
          f"{len(bad_tpl) == 0} ({len(bad_tpl)} violations)")

    unterm = [r for r in live for f in r["frames"] if not f["terminated"]]
    print(f"C5 every part list ends with a 0xFFFF terminator: "
          f"{len(unterm) == 0} ({len(unterm)} violations)")

    bad_ptr = [r for r in records
               if r["frames_ptr_off"] is None and r["frames_ptr"] not in
               (None, "0x00000000")]
    print(f"C6 every frame/animation pointer resolves inside the ROM: "
          f"{len(bad_ptr) == 0} ({len(bad_ptr)} violations)")

    tiles_ok = [r for r in live if r["tiles_contiguous"]]
    print(f"C7 tile indices cover 0..N with no gap: "
          f"{len(tiles_ok)}/{len(live)} PASS"
          if len(tiles_ok) == len(live) else
          f"C7 tile indices cover 0..N with no gap: "
          f"{len(tiles_ok)}/{len(live)} FAIL "
          f"{[(r['id'], r['action']) for r in live if not r['tiles_contiguous']]}")

    # The frame pointer table has no terminator: the animation descriptor
    # blob starts right behind its last entry.
    c8_ok = 0
    c8_bad = []
    for r in live:
        if not r["animations"] or r["frames_ptr_off"] is None:
            continue
        want = r["frames_ptr_off"] + r["frame_count"] * 4
        if r["animations"][0]["offset"] == want:
            c8_ok += 1
        else:
            c8_bad.append((r["id"], r["action"]))
    print(f"C8 first animation descriptor starts right after the frame "
          f"pointer table: {c8_ok}/{len(live)} PASS"
          if not c8_bad else
          f"C8 first animation descriptor starts right after the frame "
          f"pointer table: {c8_ok}/{len(live)} FAIL {c8_bad}")

    bad_idx = []
    for r in live:
        for anim in r["animations"]:
            for e in anim["entries"]:
                if e["frame"] >= r["frame_count"]:
                    bad_idx.append((r["id"], r["action"], e["frame"],
                                    r["frame_count"]))
    print(f"C9 every animation entry points at an existing frame: "
          f"{len(bad_idx) == 0} ({len(bad_idx)} violations "
          f"{bad_idx[:5]})")

    pal_bad = []
    for r in live:
        if r["palette_off"] is None or r["gfx_off"] is None:
            continue
        p0, p1 = r["palette_off"], r["palette_off"] + PALETTE_COLORS * 2
        g0, g1 = r["gfx_off"], r["gfx_off"] + r["gfx_bytes"]
        if p0 < g1 and g0 < p1:
            pal_bad.append((r["id"], r["action"]))
    print(f"C10 palette (16 colours) does not overlap the gfx blob: "
          f"{len(pal_bad) == 0} ({len(pal_bad)} violations)")

    def _ia(r):
        return (r["id"], r["action"])

    def _is_known(item):
        if isinstance(item, dict):
            key = (item.get("id"), item.get("action"))
        elif isinstance(item, tuple) and len(item) >= 2:
            head = item[0]
            if isinstance(head, dict):
                key = (head.get("id"), head.get("action"))
            elif isinstance(head, int):
                key = (head, item[1])
            else:
                return False
        else:
            return False
        return key in KNOWN_ROM_DEFECTS

    def _known_only(items):
        return [i for i in items if _is_known(i)]

    attributed = {
        "C1 gfx span": _known_only([r for r in live if not r["gfx_contiguous"]]),
        "C2 part size": _known_only(bad_size),
        "C3 part scale": _known_only(bad_scale),
        "C4 part template": _known_only(bad_tpl),
        "C5 piece terminator": _known_only(unterm),
    }
    for label, items in attributed.items():
        for item in items:
            head = item[0] if isinstance(item, tuple) else item
            key = ((head.get("id"), head.get("action")) if isinstance(head, dict)
                   else (head, item[1]))
            reason = KNOWN_ROM_DEFECTS.get(key, "known ROM defect")
            print(f"    ({label}: attributed to known ROM defect {key} - {reason})")

    def _drop(items):
        return [i for i in items if not _is_known(i)] if not strict_rom else items

    c1_bad = _drop([r for r in live if not r["gfx_contiguous"]])
    bad_size = _drop(bad_size)
    bad_scale = _drop(bad_scale)
    bad_tpl = _drop(bad_tpl)
    unterm = _drop(unterm)
    c1_ok = len(live) - len(c1_bad)
    tiles_bad = _drop([r for r in live if not r["tiles_contiguous"]])
    tiles_ok = len(live) - len(tiles_bad)
    c8_bad = _drop(c8_bad)
    bad_idx = _drop(bad_idx)
    pal_bad = _drop(pal_bad)

    ok = (c1_ok == len(live) and len(c1b) < len(live) and not bad_size
          and not bad_scale and not bad_tpl and not unterm and not bad_ptr
          and tiles_ok == len(live) and not c8_bad and not bad_idx
          and not pal_bad)
    print("-" * 72)
    print("RESULT:", "all invariants hold" if ok
          else "one or more invariants are violated (see above)")
    return 0 if ok else 1

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Parse the battle sprite animation tables of the ROM.")
    ap.add_argument("rom", nargs="?", default=None,
                    help="ROM path (default rom/base.gba)")
    ap.add_argument("--id", type=int, default=None,
                    help="only this character id")
    ap.add_argument("--action", type=int, default=None,
                    help="only this action (0..8)")
    ap.add_argument("--min-id", type=int, default=DEFAULT_MIN_ID)
    ap.add_argument("--max-id", type=int, default=DEFAULT_MAX_ID)
    ap.add_argument("--json", default=None,
                    help="write the structured result to this file "
                         "('-' for stdout)")
    ap.add_argument("--stats", action="store_true",
                    help="print the global overview")
    ap.add_argument("--strict-rom", action="store_true",
                    help="treat documented ROM-native defects as failures")
    ap.add_argument("--check", action="store_true",
                    help="run the format invariants and report PASS/FAIL")
    ap.add_argument("--verbose", action="store_true",
                    help="with --stats, also print every action")
    ap.add_argument("--omit-frames", action="store_true",
                    help="in --json, drop the per-frame part detail")
    ap.add_argument("--png-dir", default=None,
                    help="render each action to a PNG sheet in this directory")
    args = ap.parse_args()

    rom_path = text_codec.resolve_rom(args.rom)
    rom = rom_path.read_bytes()

    ids = range(args.min_id, args.max_id + 1)
    if args.id is not None:
        ids = range(args.id, args.id + 1)
    actions = range(ACTIONS_PER_ID)
    if args.action is not None:
        actions = range(args.action, args.action + 1)

    records = collect(rom, ids, actions)
    stats = build_stats(records, rom)

    payload = {
        "rom": str(rom_path),
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "sprite_table": hexoff(SPRITE_TABLE),
        "id_stride": ID_STRIDE,
        "action_stride": ACTION_STRIDE,
        "actions_per_id": ACTIONS_PER_ID,
        "max_frames": MAX_FRAMES,
        "max_parts": MAX_PARTS,
        "part_stride": PART_STRIDE,
        "tile_bytes": TILE_BYTES,
        "palette_colors": PALETTE_COLORS,
        "template": {
            "width": TEMPLATE_W,
            "height": TEMPLATE_H,
            "anchor_x": ANCHOR_X,
            "anchor_y": ANCHOR_Y,
        },
        "stats": stats,
        "actions": [],
    }
    for rec in records:
        item = {k: v for k, v in rec.items() if not k.startswith("_")}
        if args.omit_frames:
            item.pop("frames", None)
        payload["actions"].append(item)

    if args.json:
        blob = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if args.json == "-":
            sys.stdout.write(blob)
        else:
            out = pathlib.Path(args.json)
            write_text(out, blob)
            print(f"wrote {out}")

    if args.png_dir:
        out_dir = pathlib.Path(args.png_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for rec in records:
            if not rec["frames"]:
                continue
            image = render_action(rom, rec)
            if image is None:
                continue
            image.save(out_dir / f"sprite_{rec['id']:02d}_{rec['action']}.png")
        print(f"rendered PNG sheets to {out_dir}")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.stats:
        print_stats(records, stats, rom_path)
        if args.verbose:
            print()
            for rec in records:
                print_action(rec)
    elif not args.check:
        for rec in records:
            print_action(rec)

    if args.check:
        return run_checks(records, strict_rom=args.strict_rom)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
