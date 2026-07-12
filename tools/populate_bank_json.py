#!/usr/bin/env python3
"""Populate all bank.json files with real ROM data entries.

Reads the ROM binary and extracts entries for every structure that has
a known table_offset but empty entries array.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

try:
    from extract_character_definitions import extract_character_definitions, write_json_atomic
except ImportError:  # pragma: no cover - used when imported as tools.populate_bank_json
    from tools.extract_character_definitions import extract_character_definitions, write_json_atomic

ROOT = Path(__file__).resolve().parent.parent
ROM_PATH = ROOT / "build" / "naruto-sequel-dev.gba"


def load_rom() -> bytes:
    return ROM_PATH.read_bytes()


def update_bank_json(
    name: str,
    entries: list[dict],
    extra_fields: dict | None = None,
    *,
    force: bool = False,
    verification: str = "static_verified",
):
    """Update a bank.json with entries and optional extra fields."""
    bank_path = ROOT / "sequel" / "content" / name / "bank.json"
    if not bank_path.exists():
        print(f"  SKIP {name}: no bank.json")
        return
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    if not force and bank.get("entries") and len(bank["entries"]) > 0:
        # Already has entries - update verification only
        bank["verification"] = verification
        bank_path.write_text(json.dumps(bank, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  {name}: already has {len(bank['entries'])} entries, set verification=static_verified")
        return
    bank["entries"] = entries
    bank["verification"] = verification
    if extra_fields:
        bank.update(extra_fields)
    bank_path.write_text(json.dumps(bank, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  {name}: wrote {len(entries)} entries")


def fmt_hex(val: int) -> str:
    """Format an address as hex string."""
    return f"0x{val:06X}"


def populate_battle_encounters(rom: bytes):
    """Story visual descriptors at 0x54229C: 24 entries × 16 bytes."""
    off = 0x54229C
    entries = []
    for i in range(24):
        gfx, palette, tilemap, config_id = struct.unpack_from(
            "<IIII", rom, off + i * 16
        )
        entries.append({
            "_index": i,
            "_raw_offset": off + i * 16,
            "gfx_lz_ptr": gfx,
            "gfx_lz_ptr_hex": gfx.to_bytes(4, "little").hex(),
            "palette_lz_ptr": palette,
            "palette_lz_ptr_hex": palette.to_bytes(4, "little").hex(),
            "tilemap_lz_ptr": tilemap,
            "tilemap_lz_ptr_hex": tilemap.to_bytes(4, "little").hex(),
            "config_id": config_id,
            "config_id_hex": config_id.to_bytes(4, "little").hex(),
        })
    update_bank_json(
        "battle-encounters", entries, force=True, verification="code_verified"
    )


def populate_battle_handlers(rom: bytes):
    """Preserve the disproved battle-handler alias tombstone."""
    return None


def populate_character_stats_b(rom: bytes):
    """Preserve the disproved B-bank tombstone; never recreate the false table."""
    return None


def populate_cutscene_scripts(rom: bytes):
    """Visual resource tables at 0x53DF70: 8 pointer pairs."""
    off = 0x53DF70
    entries = []
    for i in range(8):
        primary, secondary = struct.unpack_from("<II", rom, off + i * 8)
        entries.append({
            "_index": i,
            "_raw_offset": off + i * 8,
            "pair_kind": (
                "compressed_gfx_palette"
                if i < 4 else "sprite_definition_animation"
            ),
            "resource_id": i % 4,
            "primary_ptr": primary,
            "primary_ptr_hex": primary.to_bytes(4, "little").hex(),
            "secondary_ptr": secondary,
            "secondary_ptr_hex": secondary.to_bytes(4, "little").hex(),
        })
    update_bank_json(
        "cutscene-scripts", entries, force=True, verification="code_verified"
    )


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
    """Runtime-indexed handlers at 0x53E698: 256 primary/secondary pairs."""
    off = 0x53E698
    entries = []
    unique_ptrs = set()
    for i in range(256):
        primary, secondary = struct.unpack_from("<II", rom, off + i * 8)
        unique_ptrs.update((primary, secondary))
        entries.append({
            "_index": i,
            "_raw_offset": off + i * 8,
            "primary_handler_ptr": primary,
            "primary_handler_ptr_hex": primary.to_bytes(4, "little").hex(),
            "secondary_handler_ptr": secondary,
            "secondary_handler_ptr_hex": secondary.to_bytes(4, "little").hex(),
        })
    update_bank_json("map-events", entries, {
        "unique_handler_count": len(unique_ptrs),
        "unique_handlers": [fmt_hex(p) for p in sorted(unique_ptrs)]
    }, force=True, verification="code_verified")


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


def populate_story_b(rom: bytes):
    """Preserve disproved tombstone; this slice belongs to a resource set."""
    return None


def populate_story_c(rom: bytes):
    """Preserve disproved tombstone; this slice belongs to a resource set."""
    return None


def populate_story_d(rom: bytes):
    """Preserve disproved tombstone; this slice belongs to a resource set."""
    return None


def populate_story_e(rom: bytes):
    """Preserve disproved tombstone; this slice belongs to a resource set."""
    return None


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
    """Regenerate variable-length save descriptors from the proven consumer."""
    from tools.extract_save_descriptors import build_bank
    write_json_atomic(ROOT / "sequel/content/save-state/bank.json", build_bank(rom))


def populate_audio(rom: bytes):
    """Regenerate the real sound-ID/descriptor table, not the message table."""
    from tools.extract_audio_resource_sets import extract
    write_json_atomic(ROOT / "sequel/content/audio/bank.json", extract(rom))


def populate_items(rom: bytes):
    """Preserve the disproved item-bank tombstone; never clone skills into it."""
    return None


def populate_units(rom: bytes):
    """Units/characters at 0x54241C: 63 entries × 0xB4 bytes."""
    bank_path = ROOT / "sequel" / "content" / "units" / "bank.json"
    bank = extract_character_definitions(rom)
    write_json_atomic(bank_path, bank)
    print(f"  units: wrote {len(bank['entries'])} character definition records")


def populate_sappy_engine(rom: bytes):
    """Message dispatcher at 0x079668 under the legacy sappy-engine slug."""
    off = 0x079668
    code_bytes = rom[off:off + 256]
    entries = [{
        "id": "sappy_dispatcher",
        "offset": off,
        "offset_hex": fmt_hex(off),
        "code_hex": code_bytes.hex()[:64],
        "description": "Message-selection dispatcher; legacy sappy-engine slug",
        "commands": {
            "0x64-0x67": "Select pointer fields from caller state",
            "0x80-0xE3": "Select message pointer from table at 0x08599634"
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

    # Also update already-populated ones with verification
    for name in ["battle-config", "character-stats", "levels", "maps", "positions", "skills"]:
        update_bank_json(name, [])

    print("\nDone!")


if __name__ == "__main__":
    main()
