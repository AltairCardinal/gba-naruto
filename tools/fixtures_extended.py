"""Additional synthetic fixtures: more table formats proven by round-trip.

These extend `tools/synthetic_fixture.py` (which owns the registry and the
runner).  Each fixture lives in its own module so the fixture set can grow
without one file becoming a monolith, and so several people can add fixtures
in parallel without touching the same file.

The technique is the same everywhere:
    write content of known meaning -> point the game at it -> read it back
    with the production reader -> the read must equal the write

This proves the table's *format*.  It does not prove the game uses the field
the way we think; that stays a dynamic-verification question.
"""
from __future__ import annotations

import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import extract_battle_tables as ebt  # noqa: E402
import object_tables  # noqa: E402
import portrait_assets as pa  # noqa: E402
from tools import text_codec  # noqa: E402
from tools.lib import lz77  # noqa: E402

BASE = 0x08000000
FREE_SPACE = 0x5DFBEC


def _free(rom: bytearray, size: int) -> int:
    if rom[FREE_SPACE:FREE_SPACE + size] != b"\xFF" * size:
        raise AssertionError(f"0x{FREE_SPACE:X} is not free space any more")
    return FREE_SPACE


def _put_u32(rom: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", rom, offset, value)


def _write_text(rom: bytearray, offset: int, text: str, mapping) -> int:
    raw = text_codec.encode(text, "font", mapping) + b"\x00"
    rom[offset:offset + len(raw)] = raw
    return len(raw)


def _check(label: str, expected, actual) -> dict:
    return {"check": label, "expected": expected, "actual": actual,
            "pass": expected == actual}


# --------------------------------------------------------------- missions

def fixture_mission_text(rom: bytearray, mapping) -> list[dict]:
    """Mission title / description / hint: a three-level pointer chain.

    index = rom[0x348DAC + stage] + sub  ->  table[index*4] -> ROM pointer -> text

    A synthetic mission text is written into free space, the three text
    tables are pointed at it, and the index byte is set.  The production
    extractor must read all three back.
    """
    stage, sub = 40, 1
    texts = {
        "title": "合成夹具：任务标题",
        "description": "合成夹具：任务说明",
        "hint": "合成夹具：任务提示",
    }
    offsets = {}
    cursor = _free(rom, 256)
    for label, text in texts.items():
        offsets[label] = cursor
        cursor += _write_text(rom, cursor, text, mapping)

    index = ebt.MISSION_INDEX + stage
    for label, table in ebt.MISSION_TABLES:
        # the index table gives the base index; sub selects within the group
        base_index = 0x40
        rom[index] = base_index
        _put_u32(rom, table + (base_index + sub) * 4, BASE + offsets[label])

    missions = ebt.extract_missions(rom, mapping)
    entry = next((m for m in missions if m["stage"] == stage and m["sub"] == sub),
                 None)
    checks = [_check("mission entry is present", "found",
                      "found" if entry else "missing")]
    if entry is None:
        return checks
    for label, text in texts.items():
        checks.append(_check(f"{label} text round-trips", text,
                             entry[label]["text"]))
    checks.append(_check("index arithmetic", 0x40 + sub, entry["index"]))
    return checks


# --------------------------------------------------------------- portraits

def fixture_portrait_table(rom: bytearray, mapping) -> list[dict]:
    """Portrait table `0x5A4DEC`: (gfx ptr, palette ptr) per id/expression.

    The gfx is LZ77-compressed 4bpp (80x80 -> 6400 bytes) and the palette is
    *raw* 128 bytes (64 BGR555 colours).  This fixture also exercises the
    LZ77 encoder we added for exactly this purpose.
    """
    pid, expr = 7, 2
    gfx = bytearray(6400)
    for i in range(0, 6400, 2):
        gfx[i] = 0x21
        gfx[i + 1] = 0x43
    packed = lz77.compress_literal(bytes(gfx))
    palette = bytes((i * 7) & 0xFF for i in range(128))

    cursor = _free(rom, len(packed) + len(palette) + 16)
    gfx_off = cursor
    rom[gfx_off:gfx_off + len(packed)] = packed
    pal_off = gfx_off + len(packed)
    rom[pal_off:pal_off + len(palette)] = palette

    slot = pa.PORTRAIT_TABLE + pid * pa.PORTRAIT_STRIDE + expr * pa.EXPR_STRIDE
    _put_u32(rom, slot, BASE + gfx_off)
    _put_u32(rom, slot + 4, BASE + pal_off)

    portraits = pa.read_portraits(rom)
    row = next((r for r in portraits if r["id"] == pid), None)
    checks = [_check("portrait id is present", "found",
                      "found" if row else "missing")]
    if row is None:
        return checks
    entry = next((e for e in row["expressions"] if e["expression"] == expr), None)
    checks.append(_check("expression slot is present", "found",
                          "found" if entry else "missing"))
    if entry is None:
        return checks
    checks.append(_check("gfx points at our synthetic block", BASE + gfx_off,
                          entry["gfx"]))
    checks.append(_check("gfx decompresses to 6400 bytes", 6400,
                          entry["gfx_lz_size"]))
    checks.append(_check("palette is a raw 128-byte block", True,
                          entry["palette_is_raw_128"]))
    decoded = lz77.decompress(bytes(rom), gfx_off)
    checks.append(_check("gfx round-trips through our LZ77 encoder",
                          bytes(gfx), decoded))
    return checks


# ------------------------------------------------------------- background

def fixture_background_table(rom: bytearray, mapping) -> list[dict]:
    """Story background table `0x59903C + id*16`:
    gfx / palette / tilemap / 8bpp flag.
    """
    bg_id = 12
    gfx = bytes(3072)
    palette = bytes(384)
    tilemap = bytes(640)
    cursor = _free(rom, len(gfx) + len(palette) + len(tilemap) + 16)
    gfx_off = cursor
    rom[gfx_off:gfx_off + len(gfx)] = gfx
    pal_off = gfx_off + len(gfx)
    rom[pal_off:pal_off + len(palette)] = palette
    map_off = pal_off + len(palette)
    rom[map_off:map_off + len(tilemap)] = tilemap

    slot = object_tables.BACKGROUND_TABLE + bg_id * 16
    _put_u32(rom, slot, BASE + gfx_off)
    _put_u32(rom, slot + 4, BASE + pal_off)
    _put_u32(rom, slot + 8, BASE + map_off)
    _put_u32(rom, slot + 12, 1)

    backgrounds = object_tables.read_backgrounds(rom)
    row = next((b for b in backgrounds if b["id"] == bg_id), None)
    checks = [_check("background id is present", "found",
                      "found" if row else "missing")]
    if row is None:
        return checks
    checks.append(_check("gfx pointer", BASE + gfx_off, row["gfx"]))
    checks.append(_check("palette pointer", BASE + pal_off, row["palette"]))
    checks.append(_check("tilemap pointer", BASE + map_off, row["tilemap"]))
    checks.append(_check("8bpp flag", 1, row["flag_8bpp"]))
    return checks


# ------------------------------------------------------------------ names

def fixture_ninjutsu_names(rom: bytearray, mapping) -> list[dict]:
    """Ninjutsu name table `0x599634`: u32 pointer per entry, text in font codes."""
    import extract_rewards as er

    slot_id = 90
    text = "合成夹具：忍具名"
    off = _free(rom, 64)
    _write_text(rom, off, text, mapping)
    _put_u32(rom, er.NINJUTSU_TABLE + slot_id * 4, BASE + off)

    names = er.read_name_table(rom, er.NINJUTSU_TABLE, er.NINJUTSU_COUNT, mapping)
    checks = [_check("ninjutsu name round-trips", text, names[slot_id - 1])]
    return checks


def fixture_skill_table(rom: bytearray, mapping) -> list[dict]:
    """Skill table `0x545458`: u32 pointer per entry, text in font codes."""
    slot_id = 300
    text = "合成夹具：技能名"
    off = _free(rom, 64)
    _write_text(rom, off, text, mapping)
    _put_u32(rom, 0x545458 + slot_id * 4, BASE + off)

    ptr = struct.unpack_from("<I", rom, 0x545458 + slot_id * 4)[0] - BASE
    decoded, _ = text_codec.decode_tokens(rom, ptr, mapping)
    checks = [_check("skill name round-trips", text, decoded)]
    return checks


EXTRA_FIXTURES = {
    "mission_text": fixture_mission_text,
    "portrait_table": fixture_portrait_table,
    "background_table": fixture_background_table,
    "ninjutsu_names": fixture_ninjutsu_names,
    "skill_table": fixture_skill_table,
}
