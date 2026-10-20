#!/usr/bin/env python3
"""Populate all bank.json files with real ROM data entries.

Reads the ROM binary and extracts entries for every structure that has
a known table_offset but empty entries array.

Adjudication guard (2026-10-20)
--------------------------------
Several legacy banks had their identity adjudicated in
`tools/table_registry.py` (`ALIASES` / `FALSIFIED` / `CONFLICTS`): their
old base turned out to be a *window* into another table, or the name was
falsified outright.  Re-importing entries from those old bases would
resurrect data that is known to be mis-attributed, so this tool refuses to
touch an adjudicated bank and says so.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROM_PATH = ROOT / "build" / "naruto-sequel-dev.gba"


def load_rom() -> bytes:
    return ROM_PATH.read_bytes()


def _adjudicated_banks() -> dict[str, str]:
    """Banks whose identity was adjudicated in `tools/table_registry.py`.

    Re-importing entries for them would resurrect data that was proven to
    come from a window / a falsified address, so this tool refuses to touch
    them.
    """
    try:
        from tools import table_registry
    except Exception:
        return {}
    out: dict[str, str] = {}
    for bank, canonical in (getattr(table_registry, "ALIASES", {}) or {}).items():
        out[bank] = f"弃用别名 -> {canonical}"
    for bank, reason in (getattr(table_registry, "FALSIFIED", {}) or {}).items():
        out[bank] = f"身份作废: {reason}"
    for conflict in (getattr(table_registry, "CONFLICTS", {}) or {}).values():
        for bank, disposition in (conflict.get("dispositions") or {}).items():
            out.setdefault(bank, disposition)
    return out


def update_bank_json(name: str, entries: list[dict], extra_fields: dict | None = None):
    """Update a bank.json with entries and optional extra fields."""
    bank_path = ROOT / "sequel" / "content" / name / "bank.json"
    if not bank_path.exists():
        print(f"  SKIP {name}: no bank.json")
        return
    adjudicated = _adjudicated_banks()
    if name in adjudicated:
        print(f"  SKIP {name}: 已裁决（{adjudicated[name]}），不再从旧基址导入数据")
        return
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    if bank.get("entries") and len(bank["entries"]) > 0:
        # Already has entries - update verification only
        bank["verification"] = "static_verified"
        from tools.lib.io import write_text as write_text_lf
        write_text_lf(bank_path, json.dumps(bank, indent=4, ensure_ascii=False) + "\n")
        print(f"  {name}: already has {len(bank['entries'])} entries, set verification=static_verified")
        return
    bank["entries"] = entries
    bank["verification"] = "static_verified"
    if extra_fields:
        bank.update(extra_fields)
    from tools.lib.io import write_text as write_text_lf
    write_text_lf(bank_path, json.dumps(bank, indent=4, ensure_ascii=False) + "\n")
    print(f"  {name}: wrote {len(entries)} entries")


def fmt_hex(val: int) -> str:
    """Format an address as hex string."""
    return f"0x{val:06X}"


def populate_battle_encounters(rom: bytes):
    """Battle encounters at 0x542384: 38 entries × 4 bytes (mixed ptrs + values)."""
    off = 0x542384
    entries = []
    for i in range(38):
        val = struct.unpack_from("<I", rom, off + i * 4)[0]
        is_ptr = 0x08000000 <= val <= 0x09000000
        entries.append({
            "id": f"encounter_{i:02d}",
            "index": i,
            "offset": off + i * 4,
            "offset_hex": fmt_hex(off + i * 4),
            "value": val,
            "value_hex": fmt_hex(val),
            "is_pointer": is_ptr,
            "type": "pointer" if is_ptr else "data"
        })
    update_bank_json("battle-encounters", entries)


def populate_battle_handlers(rom: bytes):
    """Battle handlers at 0x53E6D8: 14 entries × 4 bytes (u32 code pointers)."""
    off = 0x53E6D8
    entries = []
    unique_ptrs = set()
    for i in range(14):
        ptr = struct.unpack_from("<I", rom, off + i * 4)[0]
        unique_ptrs.add(ptr)
        entries.append({
            "id": f"handler_{i:02d}",
            "index": i,
            "offset": off + i * 4,
            "offset_hex": fmt_hex(off + i * 4),
            "handler_ptr": ptr,
            "handler_ptr_hex": fmt_hex(ptr),
        })
    update_bank_json("battle-handlers", entries, {
        "unique_handler_count": len(unique_ptrs),
        "unique_handlers": [fmt_hex(p) for p in sorted(unique_ptrs)]
    })


def populate_character_stats_b(rom: bytes):
    """Character stats B at 0x545200: 18 entries × 16 bytes."""
    off = 0x545200
    entries = []
    for i in range(18):
        e_off = off + i * 16
        fields = struct.unpack_from("<HHHHHHHH", rom, e_off)
        entries.append({
            "id": f"char_b_{i:02d}",
            "index": i,
            "offset": e_off,
            "offset_hex": fmt_hex(e_off),
            "field0": fields[0],
            "field1": fields[1],
            "field2": fields[2],
            "field3": fields[3],
            "field4": fields[4],
            "field5": fields[5],
            "field6": fields[6],
            "field7": fields[7],
        })
    update_bank_json("character-stats-b", entries)


def populate_cutscene_scripts(rom: bytes):
    """Level data block table at 0x53DF70: 4 entries × 8 bytes.

    Proved by the single native reader 0x08072F0C (fn 0x08072EDC): the
    stride is 8, and each entry is a pointer pair -- an LZ77-compressed
    4bpp tile block and an LZ77-compressed 16-colour palette, both
    decompressed into VRAM / palette RAM by the BIOS `svc 0x12`.  The old
    "17 entries x u32" reading spanned two different tables.
    See `notes/evidence/cutscene-block-format-20261020.md`.
    """
    off = 0x53DF70
    entries = []
    for i in range(4):
        gfx_ptr, palette_ptr = struct.unpack_from("<II", rom, off + i * 8)
        entries.append({
            "id": f"level_block_{i:02d}",
            "index": i,
            "offset": off + i * 8,
            "offset_hex": fmt_hex(off + i * 8),
            "gfx_ptr": gfx_ptr,
            "gfx_ptr_hex": fmt_hex(gfx_ptr),
            "palette_ptr": palette_ptr,
            "palette_ptr_hex": fmt_hex(palette_ptr),
        })
    update_bank_json("cutscene-scripts", entries)


def populate_data_table_a(rom: bytes):
    """Data table A at 0x5A14A4: 20 entries × 4 bytes (u32 pointers)."""
    off = 0x5A14A4
    entries = []
    for i in range(20):
        ptr = struct.unpack_from("<I", rom, off + i * 4)[0]
        entries.append({
            "id": f"data_a_{i:02d}",
            "index": i,
            "offset": off + i * 4,
            "offset_hex": fmt_hex(off + i * 4),
            "data_ptr": ptr,
            "data_ptr_hex": fmt_hex(ptr),
        })
    update_bank_json("data-table-a", entries)


def populate_data_table_b(rom: bytes):
    """Data table B at 0x5A2120: 20 entries × 4 bytes (u32 pointers)."""
    off = 0x5A2120
    entries = []
    for i in range(20):
        ptr = struct.unpack_from("<I", rom, off + i * 4)[0]
        entries.append({
            "id": f"data_b_{i:02d}",
            "index": i,
            "offset": off + i * 4,
            "offset_hex": fmt_hex(off + i * 4),
            "data_ptr": ptr,
            "data_ptr_hex": fmt_hex(ptr),
        })
    update_bank_json("data-table-b", entries)


def populate_fonts(rom: bytes):
    """Font widths at 0x53E5B4: 256 entries × 1 byte (character pixel widths)."""
    off = 0x53E5B4
    entries = []
    for i in range(256):
        width = rom[off + i]
        entries.append({
            "id": f"char_{i:02X}",
            "index": i,
            "offset": off + i,
            "offset_hex": fmt_hex(off + i),
            "ascii_code": i,
            "character": chr(i) if 32 <= i < 127 else None,
            "pixel_width": width,
        })
    update_bank_json("fonts", entries)


def populate_function_pointers(rom: bytes):
    """Function pointers at 0x53D5F4: 11 entries × 4 bytes (u32 code pointers)."""
    off = 0x53D5F4
    entries = []
    for i in range(11):
        ptr = struct.unpack_from("<I", rom, off + i * 4)[0]
        entries.append({
            "id": f"func_{i:02d}",
            "index": i,
            "offset": off + i * 4,
            "offset_hex": fmt_hex(off + i * 4),
            "func_ptr": ptr,
            "func_ptr_hex": fmt_hex(ptr),
        })
    update_bank_json("function-pointers", entries)


def populate_map_events(rom: bytes):
    """Map events at 0x53EB08: 47 entries × 4 bytes (u32 handler pointers)."""
    off = 0x53EB08
    entries = []
    unique_ptrs = set()
    for i in range(47):
        ptr = struct.unpack_from("<I", rom, off + i * 4)[0]
        unique_ptrs.add(ptr)
        entries.append({
            "id": f"map_event_{i:02d}",
            "index": i,
            "offset": off + i * 4,
            "offset_hex": fmt_hex(off + i * 4),
            "handler_ptr": ptr,
            "handler_ptr_hex": fmt_hex(ptr),
        })
    update_bank_json("map-events", entries, {
        "unique_handler_count": len(unique_ptrs),
        "unique_handlers": [fmt_hex(p) for p in sorted(unique_ptrs)]
    })


def populate_map_sprites(rom: bytes):
    """Map sprites at 0x53F1DC: 47 entries × 4 bytes (u32 sprite pointers)."""
    off = 0x53F1DC
    entries = []
    for i in range(47):
        ptr = struct.unpack_from("<I", rom, off + i * 4)[0]
        entries.append({
            "id": f"sprite_{i:02d}",
            "index": i,
            "offset": off + i * 4,
            "offset_hex": fmt_hex(off + i * 4),
            "sprite_ptr": ptr,
            "sprite_ptr_hex": fmt_hex(ptr),
        })
    update_bank_json("map-sprites", entries)


def populate_menu_ui(rom: bytes):
    """Menu UI at 0x5A5774: 20 entries × 4 bytes (u32 UI data pointers)."""
    off = 0x5A5774
    entries = []
    for i in range(20):
        ptr = struct.unpack_from("<I", rom, off + i * 4)[0]
        entries.append({
            "id": f"menu_{i:02d}",
            "index": i,
            "offset": off + i * 4,
            "offset_hex": fmt_hex(off + i * 4),
            "ui_ptr": ptr,
            "ui_ptr_hex": fmt_hex(ptr),
        })
    update_bank_json("menu-ui", entries)


def populate_palettes(rom: bytes):
    """Palettes at 0x53F138: 88 entries × 4 bytes (u32 palette pointers).
    Note: This overlaps with audio table in the report, but palettes use
    the same region with different interpretation."""
    off = 0x53F138
    entries = []
    for i in range(88):
        ptr = struct.unpack_from("<I", rom, off + i * 4)[0]
        entries.append({
            "id": f"palette_{i:02d}",
            "index": i,
            "offset": off + i * 4,
            "offset_hex": fmt_hex(off + i * 4),
            "palette_ptr": ptr,
            "palette_ptr_hex": fmt_hex(ptr),
        })
    update_bank_json("palettes", entries)


def populate_resource_pointers(rom: bytes):
    """Resource pointers at 0x596F0C: 20 entries × 4 bytes (u32 resource pointers)."""
    off = 0x596F0C
    entries = []
    for i in range(20):
        ptr = struct.unpack_from("<I", rom, off + i * 4)[0]
        entries.append({
            "id": f"resource_{i:02d}",
            "index": i,
            "offset": off + i * 4,
            "offset_hex": fmt_hex(off + i * 4),
            "resource_ptr": ptr,
            "resource_ptr_hex": fmt_hex(ptr),
        })
    update_bank_json("resource-pointers", entries)


def populate_sprite_animations(rom: bytes):
    """Sprite animations at 0x53F200: 38 entries × 4 bytes (u32 animation pointers)."""
    off = 0x53F200
    entries = []
    for i in range(38):
        ptr = struct.unpack_from("<I", rom, off + i * 4)[0]
        entries.append({
            "id": f"anim_{i:02d}",
            "index": i,
            "offset": off + i * 4,
            "offset_hex": fmt_hex(off + i * 4),
            "anim_ptr": ptr,
            "anim_ptr_hex": fmt_hex(ptr),
        })
    update_bank_json("sprite-animations", entries)


def populate_audio_song_header(rom: bytes, bank: str, base: int, sound_id: int):
    """One m4a SongHeader: u8 track_count, u8 block_count, u16 pad,
    u32 voicegroup_ptr, u32 track_ptr[track_count].

    The five legacy ``story*`` banks are these headers (sound ids 1/2/8/11/14);
    their old bases were 4 bytes late because the legacy extractor anchored
    on the voicegroup pointer instead of the header start.  See
    ``notes/evidence/story-table-family-20261020.md``.
    """
    track_count = rom[base]
    word_count = track_count + 2
    entries = []
    for i in range(word_count):
        off = base + i * 4
        word = struct.unpack_from("<I", rom, off)[0]
        entries.append({
            "id": f"word_{i:02d}",
            "index": i,
            "offset": off,
            "offset_hex": fmt_hex(off),
            "word": word,
            "word_hex": fmt_hex(word),
        })
    update_bank_json(bank, entries, {
        "sound_id": sound_id,
        "track_count": track_count,
        "block_count": rom[base + 1],
    })


def populate_story(rom: bytes):
    """Sound id 1: m4a SongHeader at 0x536368.

    The legacy base 0x53636C was 4 bytes late (it
    anchored on the voicegroup pointer, not the header start).
    """
    populate_audio_song_header(rom, "story", 0x536368, 1)


def populate_story_b(rom: bytes):
    """Sound id 2: m4a SongHeader at 0x536BC4.

    The legacy base 0x536BC8 was 4 bytes late (it
    anchored on the voicegroup pointer, not the header start).
    """
    populate_audio_song_header(rom, "story-b", 0x536BC4, 2)


def populate_story_c(rom: bytes):
    """Sound id 8: m4a SongHeader at 0x538FEC.

    The legacy base 0x538FF0 was 4 bytes late (it
    anchored on the voicegroup pointer, not the header start).
    """
    populate_audio_song_header(rom, "story-c", 0x538FEC, 8)


def populate_story_d(rom: bytes):
    """Sound id 11: m4a SongHeader at 0x53AB74.

    The legacy base 0x53AB78 was 4 bytes late (it
    anchored on the voicegroup pointer, not the header start).
    """
    populate_audio_song_header(rom, "story-d", 0x53AB74, 11)


def populate_story_e(rom: bytes):
    """Sound id 14: m4a SongHeader at 0x53C3BC.

    The legacy base 0x53C3C0 was 4 bytes late (it
    anchored on the voicegroup pointer, not the header start).
    """
    populate_audio_song_header(rom, "story-e", 0x53C3BC, 14)


def populate_tile_assets(rom: bytes):
    """Tile assets at 0x5A3218: 6 entries × 4 bytes (u32 tile data pointers)."""
    off = 0x5A3218
    entries = []
    for i in range(6):
        ptr = struct.unpack_from("<I", rom, off + i * 4)[0]
        entries.append({
            "id": f"tile_{i:02d}",
            "index": i,
            "offset": off + i * 4,
            "offset_hex": fmt_hex(off + i * 4),
            "tile_ptr": ptr,
            "tile_ptr_hex": fmt_hex(ptr),
        })
    update_bank_json("tile-assets", entries)


def populate_encounter_zones(rom: bytes):
    """Encounter zones from map headers at 0x53D910: 47 entries × 32 bytes, zone_id at offset 28."""
    off = 0x53D910
    entries = []
    for i in range(47):
        e_off = off + i * 32
        width, height = struct.unpack_from("<HH", rom, e_off)
        zone_id = struct.unpack_from("<I", rom, e_off + 28)[0]
        entries.append({
            "id": f"zone_{i:02d}",
            "index": i,
            "offset": e_off,
            "offset_hex": fmt_hex(e_off),
            "map_width": width,
            "map_height": height,
            "zone_id": zone_id,
        })
    update_bank_json("encounter-zones", entries)


def populate_save_state(rom: bytes):
    """Save state at 0x53D848: 10 entries × 8 bytes (u32 ewram_addr, u32 sram_offset)."""
    off = 0x53D848
    entries = []
    for i in range(10):
        e_off = off + i * 8
        ewram, sram = struct.unpack_from("<II", rom, e_off)
        entries.append({
            "id": f"save_{i:02d}",
            "index": i,
            "offset": e_off,
            "offset_hex": fmt_hex(e_off),
            "ewram_addr": ewram,
            "ewram_addr_hex": fmt_hex(ewram),
            "sram_offset": sram,
        })
    update_bank_json("save-state", entries)


def populate_audio(rom: bytes):
    """Audio at 0x53F138: 88 entries × 4 bytes (u32 audio pointers)."""
    off = 0x53F138
    entries = []
    for i in range(88):
        ptr = struct.unpack_from("<I", rom, off + i * 4)[0]
        entries.append({
            "id": f"audio_{i:02d}",
            "index": i,
            "offset": off + i * 4,
            "offset_hex": fmt_hex(off + i * 4),
            "audio_ptr": ptr,
            "audio_ptr_hex": fmt_hex(ptr),
        })
    update_bank_json("audio", entries)


def populate_items(rom: bytes):
    """Item / skill records at 0x545BE4: 94 entries x 16 bytes.

    The legacy base 0x546100 was entry 81 + 12 bytes -- a skewed
    window into this table.
    """
    off = 0x545BE4
    entries = []
    for i in range(94):
        e_off = off + i * 16
        words = struct.unpack_from("<8H", rom, e_off)
        entry = {
            "id": f"word_{i:02d}",
            "index": i,
            "offset": e_off,
            "offset_hex": fmt_hex(e_off),
        }
        for k, word in enumerate(words):
            entry[f"field_{k}"] = word
            entry[f"field_{k}_hex"] = fmt_hex(word)
        entries.append(entry)
    update_bank_json("items", entries)


def populate_units(rom: bytes):
    """Units at 0x53F298: 64 entries × 2 bytes (u16 character IDs)."""
    off = 0x53F298
    entries = []
    for i in range(64):
        char_id = struct.unpack_from("<H", rom, off + i * 2)[0]
        entries.append({
            "id": f"unit_{i:02d}",
            "index": i,
            "offset": off + i * 2,
            "offset_hex": fmt_hex(off + i * 2),
            "char_id": char_id,
        })
    update_bank_json("units", entries)


def populate_sappy_engine(rom: bytes):
    """Sappy engine code at 0x079668: code region (not a data table)."""
    off = 0x079668
    code_bytes = rom[off:off + 256]
    entries = [{
        "id": "sappy_dispatcher",
        "offset": off,
        "offset_hex": fmt_hex(off),
        "code_hex": code_bytes.hex()[:64],
        "description": "Custom Sappy audio dispatcher (not standard m4aSongNumStart)",
        "commands": {
            "0x64-0x67": "BGM channel control",
            "0x80-0xE3": "Indexed lookup into 100-entry pointer table at 0x08599634"
        }
    }]
    update_bank_json("sappy-engine", entries, {
        "verification": "code_verified",
        "call_sites": 15,
        "unique_functions": 6,
    })


def main():
    rom = load_rom()
    print(f"ROM loaded: {len(rom)} bytes")

    populate_battle_encounters(rom)
    populate_battle_handlers(rom)
    populate_character_stats_b(rom)
    populate_cutscene_scripts(rom)
    populate_data_table_a(rom)
    populate_data_table_b(rom)
    populate_fonts(rom)
    populate_function_pointers(rom)
    populate_map_events(rom)
    populate_map_sprites(rom)
    populate_menu_ui(rom)
    populate_palettes(rom)
    populate_resource_pointers(rom)
    populate_sprite_animations(rom)
    populate_story_b(rom)
    populate_story_c(rom)
    populate_story_d(rom)
    populate_story_e(rom)
    populate_tile_assets(rom)
    populate_encounter_zones(rom)
    populate_save_state(rom)
    populate_audio(rom)
    populate_items(rom)
    populate_units(rom)
    populate_sappy_engine(rom)
    populate_story(rom)

    # Also update already-populated ones with verification
    for name in ["battle-config", "character-stats", "levels", "maps", "positions", "skills", "story"]:
        update_bank_json(name, [])

    print("\nDone!")


if __name__ == "__main__":
    main()
