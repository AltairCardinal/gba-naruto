#!/usr/bin/env python3
"""Independently replay the ten fixed disproved-bank negative proofs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


SCHEMA = "disproved-bank-candidate-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_BASE = 0x08000000

DISPROVED_SPECS: dict[str, dict[str, Any]] = {
    "battle-handlers": {
        "candidate_range": (0x53E6D8, 0x53E710),
        "candidate_sha256": "aa94c4fc093dbe84a36a2c4db406fc7b26e7f71bba5d95763ee6a61b41a51528",
        "bank_sha256": "1d3b1ed2da0b7581f09cc7fbf40db5169f7e6c3659bf47def544a9d6ef4886bd",
        "proof_kind": "canonical_table_alias",
        "evidence": (
            "notes/dynamic-verification-audit.md",
            "sequel/content/map-events/bank.json",
        ),
    },
    "character-stats-b": {
        "candidate_range": (0x545200, 0x545320),
        "candidate_sha256": "4ef1e6fda824c63b2c220190247a7082c80840968377bd5b5e8999b9dc7ea0e4",
        "bank_sha256": "9655ae046ead20234259aa342c01e393604d95120febce8acafa454c72c44184",
        "proof_kind": "misaligned_canonical_table_slice",
        "evidence": (
            "sequel/content/character-stats-b/bank.json",
            "sequel/content/character-stats/bank.json",
        ),
    },
    "encounter-zones": {
        "candidate_range": (0x53D910, 0x53DEF0),
        "candidate_sha256": "977b4393a2c5d37124d09e772de42f11d2d9abff9ec832d1160aeeb194a6566c",
        "bank_sha256": "656e77b14b8faf5dd0d5665836965d05272b6f7752ad50e6bb9944e9e6671bc1",
        "proof_kind": "canonical_table_alias",
        "evidence": (
            "artifacts/runtime-checkpoints/maps-resource-runtime-evidence.json",
            "sequel/content/maps/bank.json",
        ),
    },
    "fonts": {
        "candidate_range": (0x53E5B4, 0x53E6B4),
        "candidate_sha256": "e79d55ca75ab5929216ea85572bcd3fc60fa17232be4293d34aef55a02a5f9b2",
        "bank_sha256": "206cdb5470c09505195eeff6b6c4d288fa2442f4ca772913d0fb47a3dcad38d4",
        "proof_kind": "mixed_font_and_handler_extent",
        "evidence": (
            "artifacts/dialogue-font-v2/manifest.json",
            "sequel/content/map-events/bank.json",
        ),
    },
    "items": {
        "candidate_range": (0x546100, 0x5461C0),
        "candidate_sha256": "eefb58986440ef412931a024b4b2e25aacb909ac76beb3016187ad9d3d2ec4b6",
        "bank_sha256": "8dd9458f2c15ac6db09fd534970bbccc0d01500744e65d84561d2b89c718fca1",
        "proof_kind": "misaligned_canonical_table_slice",
        "evidence": (
            "notes/skill-template-identity-20260711.md",
            "sequel/content/skills/bank.json",
        ),
    },
    "resource-pointers": {
        "candidate_range": (0x596F0C, 0x596F5C),
        "candidate_sha256": "10c456c9fde36afba9d4815a0da4829a0396077b1a9f52a235d3848ee9309f23",
        "bank_sha256": "0d595c1dfeb9b71a25007e5aef11232553b3aecc9bc29321e185346dbfe5aa2d",
        "proof_kind": "canonical_visual_matrix_slice",
        "evidence": (
            "docs/structure-field-semantics.md",
            "artifacts/character-battle-visuals-v1/manifest.json",
        ),
    },
    "sprite-animations": {
        "candidate_range": (0x53F200, 0x53F298),
        "candidate_sha256": "b51a89c13daee6cfb6bbdd934ed98c3b1f4875b4b36c399ebf2527f94af550b2",
        "bank_sha256": "5148a8a367861e011ec59d75ee8cbf19feb25b2ea511fa56bde390d5f1cee4ee",
        "proof_kind": "canonical_table_alias",
        "evidence": ("sequel/content/map-sprites/bank.json",),
    },
    "story-c": {
        "candidate_range": (0x538FF0, 0x538FF4),
        "candidate_sha256": "f865fdd834e2d67ae7ade5044406f0858b75841a07e30fcb74b38c09257c3032",
        "bank_sha256": "e0f22540e759975a557182612f764fde415490eaec1d9d9f0585e5a411d087c4",
        "proof_kind": "m4a_song_header_subfield",
        "sound_id": 8,
        "evidence": (
            "sequel/content/audio/bank.json",
            "artifacts/rom-m4a-byte-inventory-v1/manifest.json",
        ),
    },
    "story-d": {
        "candidate_range": (0x53AB78, 0x53AB7C),
        "candidate_sha256": "b22596ff1a00f87e145807a28f5110b616dd7c9f23d5dac0df42bd34ea1a284a",
        "bank_sha256": "e3aa6bf2b1ae6c7a109a3082c0d0a53055f459aedfd1b9ab9dc2e293f3b17474",
        "proof_kind": "m4a_song_header_subfield",
        "sound_id": 11,
        "evidence": (
            "sequel/content/audio/bank.json",
            "artifacts/rom-m4a-byte-inventory-v1/manifest.json",
        ),
    },
    "story-e": {
        "candidate_range": (0x53C3C0, 0x53C3C4),
        "candidate_sha256": "3b1eec63ad0987f46bfb7ae362e9cef20c637f8fe0a60e123ddd6c000665d72a",
        "bank_sha256": "c9d4bdb125965e372f0069a981c758e036ffd7c039a57e7c5ca3ea571c1c4608",
        "proof_kind": "m4a_song_header_subfield",
        "sound_id": 14,
        "evidence": (
            "sequel/content/audio/bank.json",
            "artifacts/rom-m4a-byte-inventory-v1/manifest.json",
        ),
    },
}

PHYSICAL_ALIAS_SPECS: dict[str, dict[str, Any]] = {
    "battle-handlers": {
        "canonical_start": 0x53E698,
        "candidate_base_pointer_offsets": (),
        "canonical_base_pointer_offsets": (0x7FA38, 0x7FD88),
        "consumer_code_range": (0x7F934, 0x7F968),
        "consumer_code_sha256": (
            "a1dc1b497f2aebb8e2b865adbc7c7a9abb42f13e7f456130f648b619343cb4f9"
        ),
    },
    "character-stats-b": {
        "canonical_start": 0x545068,
        "candidate_base_pointer_offsets": (),
        "canonical_base_pointer_offsets": (0x6D998,),
        "consumer_code_range": (0x6D964, 0x6D994),
        "consumer_code_sha256": (
            "ac928b1d93209cb34f43a226919b6eda783df982550fd7a4a8267f477511a1e5"
        ),
    },
    "encounter-zones": {
        "canonical_start": 0x53D910,
        "candidate_base_pointer_offsets": (
            0x68FE0,
            0x690DC,
            0x6924C,
            0x6927C,
            0x7AB00,
            0x80734,
            0x809C4,
            0x8F508,
        ),
        "canonical_base_pointer_offsets": (
            0x68FE0,
            0x690DC,
            0x6924C,
            0x6927C,
            0x7AB00,
            0x80734,
            0x809C4,
            0x8F508,
        ),
        "consumer_code_range": (0x6921C, 0x6922C),
        "consumer_code_sha256": (
            "c1f028a5df8ef0b14f6644af0097ab9bde1694e7526726cbce36def5aa16384a"
        ),
    },
    "items": {
        "canonical_start": 0x545BE4,
        "candidate_base_pointer_offsets": (),
        "canonical_base_pointer_offsets": (
            0x6D960,
            0x78F04,
            0x78FC0,
            0x8FC38,
            0x8FFC4,
            0x953A0,
            0x9545C,
        ),
        "consumer_code_range": None,
        "consumer_code_sha256": None,
    },
    "resource-pointers": {
        "canonical_start": 0x596D5C,
        "candidate_base_pointer_offsets": (0x7B278,),
        "canonical_base_pointer_offsets": (),
        "consumer_code_range": (0x7B220, 0x7B25A),
        "consumer_code_sha256": (
            "2c023ed722d90bb1194e81655c606215029b74fb5013a9b81916a03c7950fcc4"
        ),
    },
    "sprite-animations": {
        "canonical_start": 0x53F140,
        "candidate_base_pointer_offsets": (),
        "canonical_base_pointer_offsets": (0x80B54,),
        "consumer_code_range": (0x80B08, 0x80B52),
        "consumer_code_sha256": (
            "5d9073b849f98b8bf9153df047b3afe0f65f64aca749b74df306836b250e3e77"
        ),
    },
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_file(root: Path, relative: str | Path) -> Path:
    root = Path(root).resolve(strict=True)
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"repository path escapes root: {relative}")
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"repository path uses a symlink: {relative}")
    resolved = (root / relative).resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"repository file is invalid: {relative}")
    return resolved


def _load_json(root: Path, relative: str | Path) -> dict[str, Any]:
    value = json.loads(_safe_file(root, relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {relative}")
    return value


def _require_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise ValueError(message)


def _pointer_offsets(rom: bytes, file_offset: int) -> list[int]:
    """Return the complete byte-aligned occurrence denominator for one ROM pointer."""

    needle = (ROM_BASE + file_offset).to_bytes(4, "little")
    offsets: list[int] = []
    cursor = 0
    while True:
        cursor = rom.find(needle, cursor)
        if cursor < 0:
            return offsets
        offsets.append(cursor)
        cursor += 1


def _physical_alias_binding(rom: bytes, slug: str) -> dict[str, Any]:
    spec = PHYSICAL_ALIAS_SPECS[slug]
    candidate_start = DISPROVED_SPECS[slug]["candidate_range"][0]
    candidate_offsets = _pointer_offsets(rom, candidate_start)
    canonical_offsets = _pointer_offsets(rom, spec["canonical_start"])
    if tuple(candidate_offsets) != spec["candidate_base_pointer_offsets"]:
        raise ValueError(f"{slug} candidate-base pointer denominator changed")
    if tuple(canonical_offsets) != spec["canonical_base_pointer_offsets"]:
        raise ValueError(f"{slug} canonical-base pointer denominator changed")

    code_range = spec["consumer_code_range"]
    if code_range is not None:
        start, end = code_range
        if _sha(rom[start:end]) != spec["consumer_code_sha256"]:
            raise ValueError(f"{slug} canonical consumer code changed")
    return {
        "candidate_base_pointer_offsets": candidate_offsets,
        "canonical_base_pointer_offsets": canonical_offsets,
        "consumer_code_range": list(code_range) if code_range is not None else None,
        "consumer_code_sha256": spec["consumer_code_sha256"],
    }


def _entry_index(entry: dict[str, Any], index: int, offset: int) -> None:
    if entry.get("_index") != index or entry.get("_raw_offset") != offset:
        raise ValueError(f"canonical entry denominator changed at index {index}")


def _map_event_table(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    bank = _load_json(root, "sequel/content/map-events/bank.json")
    start, count, size = 0x53E698, 256, 8
    _require_equal(
        (bank.get("table_offset"), bank.get("entry_count"), bank.get("entry_size")),
        (start, count, size),
        "map-events table denominator changed",
    )
    entries = bank.get("entries")
    if not isinstance(entries, list) or len(entries) != count:
        raise ValueError("map-events entry denominator changed")
    chunks = []
    for index, entry in enumerate(entries):
        _entry_index(entry, index, start + index * size)
        chunks.append(
            struct.pack(
                "<II",
                entry["primary_handler_ptr"],
                entry["secondary_handler_ptr"],
            )
        )
    raw = b"".join(chunks)
    if rom[start : start + len(raw)] != raw:
        raise ValueError("map-events canonical table differs from ROM")
    return bank, raw


def _raw_hex_table(
    root: Path,
    rom: bytes,
    relative: str,
    *,
    start: int,
    count: int,
    size: int,
) -> tuple[dict[str, Any], bytes]:
    bank = _load_json(root, relative)
    _require_equal(
        (bank.get("table_offset"), bank.get("entry_count"), bank.get("entry_size")),
        (start, count, size),
        f"{relative} table denominator changed",
    )
    entries = bank.get("entries")
    if not isinstance(entries, list) or len(entries) != count:
        raise ValueError(f"{relative} entry denominator changed")
    chunks = []
    for index, entry in enumerate(entries):
        _entry_index(entry, index, start + index * size)
        raw = bytes.fromhex(entry.get("raw_hex", ""))
        if len(raw) != size:
            raise ValueError(f"{relative} raw entry size changed at {index}")
        chunks.append(raw)
    table = b"".join(chunks)
    if rom[start : start + len(table)] != table:
        raise ValueError(f"{relative} canonical table differs from ROM")
    return bank, table


def _maps_table(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    bank = _load_json(root, "sequel/content/maps/bank.json")
    start, count, size = 0x53D910, 47, 32
    _require_equal(
        (bank.get("table_offset"), bank.get("entry_count"), bank.get("entry_size")),
        (start, count, size),
        "maps table denominator changed",
    )
    entries = bank.get("entries")
    if not isinstance(entries, list) or len(entries) != count:
        raise ValueError("maps entry denominator changed")
    chunks = []
    pointer_fields = (
        "tileset_ptr",
        "tilemap_ptr",
        "tilemap_alt_ptr",
        "extra_ptr",
        "palette_ptr",
        "palette2_ptr",
        "flags",
    )
    for index, entry in enumerate(entries):
        _entry_index(entry, index, start + index * size)
        chunks.append(
            struct.pack(
                "<HH7I",
                entry["width"],
                entry["height"],
                *(entry[field] for field in pointer_fields),
            )
        )
    raw = b"".join(chunks)
    if rom[start : start + len(raw)] != raw:
        raise ValueError("maps canonical table differs from ROM")
    return bank, raw


def _map_sprite_table(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    bank = _load_json(root, "sequel/content/map-sprites/bank.json")
    start, count, size = 0x53F140, 43, 8
    _require_equal(
        (bank.get("table_offset"), bank.get("entry_count"), bank.get("entry_size")),
        (start, count, size),
        "map-sprites table denominator changed",
    )
    entries = bank.get("entries")
    if not isinstance(entries, list) or len(entries) != count:
        raise ValueError("map-sprites entry denominator changed")
    chunks = []
    for index, entry in enumerate(entries):
        _entry_index(entry, index, start + index * size)
        chunks.append(struct.pack("<II", entry["definition_ptr"], entry["animation_ptr"]))
    raw = b"".join(chunks)
    if rom[start : start + len(raw)] != raw:
        raise ValueError("map-sprites canonical table differs from ROM")
    return bank, raw


def _visual_matrix(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    manifest = _load_json(root, "artifacts/character-battle-visuals-v1/manifest.json")
    table = manifest.get("table")
    slots = manifest.get("slots")
    if not isinstance(table, dict) or not isinstance(slots, list):
        raise ValueError("character visual matrix payload is incomplete")
    start, count, size = 0x596D5C, 558, 16
    _require_equal(
        (table.get("file_offset"), table.get("entry_count"), table.get("entry_size")),
        (start, count, size),
        "character visual matrix denominator changed",
    )
    if len(slots) != count:
        raise ValueError("character visual matrix slot count changed")
    chunks = []
    for index, slot in enumerate(slots):
        if slot.get("row") != index:
            raise ValueError(f"character visual matrix row changed at {index}")
        raw = bytes.fromhex(slot.get("descriptor_raw_hex", ""))
        if len(raw) != size:
            raise ValueError(f"character visual descriptor size changed at {index}")
        chunks.append(raw)
    raw = b"".join(chunks)
    if _sha(raw) != table.get("sha256") or rom[start : start + len(raw)] != raw:
        raise ValueError("character visual matrix differs from ROM")
    return manifest, raw


def _verify_font_extent(root: Path, rom: bytes, candidate: bytes) -> dict[str, Any]:
    _, handlers = _map_event_table(root, rom)
    manifest = _load_json(root, "artifacts/dialogue-font-v2/manifest.json")
    if manifest.get("schema") != "dialogue-font-atlas-v2" or manifest.get("rom") != {
        "path": ROM_PATH.as_posix(),
        "size": ROM_SIZE,
        "sha256": ROM_SHA256,
    }:
        raise ValueError("dialogue font manifest identity changed")
    font_ranges = []
    for name in ("sjis_table", "byte_table"):
        record = manifest.get(name)
        if not isinstance(record, dict):
            raise ValueError(f"dialogue font manifest lacks {name}")
        start = record.get("file_offset")
        size = record.get("entry_count", 0) * record.get("entry_size", 0)
        if not isinstance(start, int) or size <= 0:
            raise ValueError(f"dialogue font {name} range changed")
        if _sha(rom[start : start + size]) != record.get("sha256"):
            raise ValueError(f"dialogue font {name} table changed")
        font_ranges.append([start, start + size])
    candidate_start, candidate_end = DISPROVED_SPECS["fonts"]["candidate_range"]
    handler_start = 0x53E698
    if not candidate_start < handler_start < candidate_end:
        raise ValueError("historical font candidate no longer crosses handler table")
    overlap = candidate_end - handler_start
    if candidate[-overlap:] != handlers[:overlap]:
        raise ValueError("historical font candidate suffix is not canonical handlers")
    pointer = (ROM_BASE + candidate_start).to_bytes(4, "little")
    if rom.find(pointer) != -1:
        raise ValueError("historical font candidate unexpectedly gained a literal pointer")
    return {
        "verified_font_table_ranges": font_ranges,
        "handler_table_start": handler_start,
        "handler_overlap_bytes": overlap,
        "candidate_literal_pointer_occurrences": 0,
    }


def _audio_table(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    bank = _load_json(root, "sequel/content/audio/bank.json")
    start, count, size = 0x465B70, 80, 8
    _require_equal(
        (bank.get("table_offset"), bank.get("entry_count"), bank.get("entry_size")),
        (start, count, size),
        "audio master table denominator changed",
    )
    entries = bank.get("entries")
    if not isinstance(entries, list) or len(entries) != count:
        raise ValueError("audio master entry denominator changed")
    chunks = []
    seen_sound_ids: set[int] = set()
    for entry in entries:
        sound_id = entry.get("sound_id")
        if (
            not isinstance(sound_id, int)
            or entry.get("_index") != sound_id
            or entry.get("_raw_offset") != start + sound_id * size
            or sound_id in seen_sound_ids
            or not 0 <= sound_id <= 158
        ):
            raise ValueError("audio active sound-id denominator changed")
        seen_sound_ids.add(sound_id)
        raw = bytes.fromhex(entry.get("raw_hex", ""))
        if len(raw) != size:
            raise ValueError(f"audio master entry size changed at sound ID {sound_id}")
        if rom[entry["_raw_offset"] : entry["_raw_offset"] + size] != raw:
            raise ValueError(f"audio master entry differs from ROM at sound ID {sound_id}")
        chunks.append(raw)
    return bank, b"".join(chunks)


def _verify_story_subfield(
    root: Path, rom: bytes, slug: str, sound_id: int, candidate: bytes
) -> dict[str, Any]:
    audio, _ = _audio_table(root, rom)
    entries = [entry for entry in audio["entries"] if entry.get("sound_id") == sound_id]
    if len(entries) != 1:
        raise ValueError("audio sound-id denominator changed")
    entry = entries[0]
    descriptor_offset = entry.get("descriptor_offset")
    descriptor = bytes.fromhex(entry.get("descriptor_raw_hex", ""))
    if not isinstance(descriptor_offset, int) or len(descriptor) < 8:
        raise ValueError("audio descriptor denominator changed")
    if rom[descriptor_offset : descriptor_offset + len(descriptor)] != descriptor:
        raise ValueError("audio descriptor differs from ROM")
    descriptor_pointer = int.from_bytes(
        rom[entry["_raw_offset"] : entry["_raw_offset"] + 4], "little"
    )
    if descriptor_pointer != ROM_BASE + descriptor_offset:
        raise ValueError("audio master pointer no longer selects the descriptor")
    start, end = DISPROVED_SPECS[slug]["candidate_range"]
    if (start, end) != (descriptor_offset + 4, descriptor_offset + 8):
        raise ValueError("story candidate is not descriptor +4 voicegroup field")
    voicegroup_pointer = int.from_bytes(descriptor[4:8], "little")
    if candidate != descriptor[4:8] or voicegroup_pointer != entry.get("voicegroup_ptr"):
        raise ValueError("story candidate no longer equals the voicegroup pointer")

    m4a = _load_json(root, "artifacts/rom-m4a-byte-inventory-v1/manifest.json")
    if m4a.get("base_rom") != {
        "path": ROM_PATH.as_posix(),
        "size": ROM_SIZE,
        "sha256": ROM_SHA256,
    }:
        raise ValueError("m4a inventory ROM identity changed")
    claim_id = f"m4a-song-header-{sound_id:03d}"
    claims = [item for item in m4a.get("claims", []) if item.get("id") == claim_id]
    if len(claims) != 1:
        raise ValueError("m4a SongHeader claim denominator changed")
    claim = claims[0]
    claim_range = claim.get("range")
    if (
        claim.get("semantic_class") != "m4a_song_header"
        or not isinstance(claim_range, list)
        or claim_range[0] != descriptor_offset
        or claim_range[1] != descriptor_offset + len(descriptor)
        or _sha(descriptor) != claim.get("bytes_sha256")
        or claim.get("subject", {}).get("sound_ids") != [sound_id]
        or claim.get("subject", {}).get("voicegroup_pointer")
        != f"0x{voicegroup_pointer:08X}"
    ):
        raise ValueError("m4a SongHeader semantic claim changed")
    return {
        "sound_id": sound_id,
        "master_entry_offset": entry["_raw_offset"],
        "descriptor_offset": descriptor_offset,
        "voicegroup_pointer": voicegroup_pointer,
        "m4a_claim_id": claim_id,
    }


def _proof_details(root: Path, rom: bytes, slug: str, candidate: bytes) -> dict[str, Any]:
    start, end = DISPROVED_SPECS[slug]["candidate_range"]
    if slug == "battle-handlers":
        _, raw = _map_event_table(root, rom)
        source_start = 0x53E698 + 8 * 8
        if (start, end) != (source_start, source_start + 7 * 8) or candidate != raw[8 * 8 : 15 * 8]:
            raise ValueError("battle-handlers is not map-events records 8 through 14")
        return {
            "source_bank": "map-events",
            "source_record_range": [8, 15],
            **_physical_alias_binding(rom, slug),
        }
    if slug == "character-stats-b":
        _, raw = _raw_hex_table(
            root,
            rom,
            "sequel/content/character-stats/bank.json",
            start=0x545068,
            count=63,
            size=16,
        )
        byte_start = 25 * 16 + 8
        if start != 0x545068 + byte_start or candidate != raw[byte_start : byte_start + 0x120]:
            raise ValueError("character-stats-b is not the fixed misaligned canonical slice")
        return {
            "source_bank": "character-stats",
            "source_byte_range": [byte_start, byte_start + 0x120],
            "alignment_remainder": byte_start % 16,
            **_physical_alias_binding(rom, slug),
        }
    if slug == "encounter-zones":
        _, raw = _maps_table(root, rom)
        if candidate != raw or (start, end) != (0x53D910, 0x53D910 + len(raw)):
            raise ValueError("encounter-zones is not the complete canonical maps table")
        runtime = _load_json(
            root, "artifacts/runtime-checkpoints/maps-resource-runtime-evidence.json"
        )
        expected_checks = {
            "alternate_layout_null_and_skipped",
            "bg_palette_after_transparent_color_zero_normalization",
            "collision_low_byte_passability_exact",
            "metatile_attributes_exact",
            "primary_layout_exact",
            "tile_gfx_exact",
        }
        checks = runtime.get("resource_checks")
        if (
            runtime.get("schema_version") != 1
            or runtime.get("outcome") != "matched"
            or runtime.get("map_id") != 41
            or runtime.get("row_file_offset") != "0x53DE30"
            or runtime.get("map_runtime") != [36, 44, 9, 22]
            or not isinstance(checks, dict)
            or set(checks) != expected_checks
            or not all(checks.values())
        ):
            raise ValueError("encounter-zones runtime map-row evidence changed")
        return {
            "source_bank": "maps",
            "source_record_range": [0, 47],
            "runtime_map_binding": {
                "map_id": 41,
                "row_file_offset": 0x53DE30,
                "row_stride": 32,
                "flag_byte_offset": 0x1D,
                "resource_checks_all_passed": True,
            },
            **_physical_alias_binding(rom, slug),
        }
    if slug == "fonts":
        return _verify_font_extent(root, rom, candidate)
    if slug == "items":
        _, raw = _raw_hex_table(
            root,
            rom,
            "sequel/content/skills/bank.json",
            start=0x545BE4,
            count=94,
            size=16,
        )
        byte_start = 0x546100 - 0x545BE4
        if candidate != raw[byte_start : byte_start + 0xC0]:
            raise ValueError("items is not the fixed misaligned skills slice")
        return {
            "source_bank": "skills",
            "source_byte_range": [byte_start, byte_start + 0xC0],
            "alignment_remainder": byte_start % 16,
            **_physical_alias_binding(rom, slug),
        }
    if slug == "resource-pointers":
        _, raw = _visual_matrix(root, rom)
        if candidate != raw[27 * 16 : 32 * 16]:
            raise ValueError("resource-pointers is not visual matrix rows 27 through 31")
        return {
            "source_artifact": "character-battle-visuals-v1",
            "source_record_range": [27, 32],
            **_physical_alias_binding(rom, slug),
        }
    if slug == "sprite-animations":
        _, raw = _map_sprite_table(root, rom)
        if candidate != raw[24 * 8 : 43 * 8]:
            raise ValueError("sprite-animations is not map-sprites records 24 through 42")
        return {
            "source_bank": "map-sprites",
            "source_record_range": [24, 43],
            **_physical_alias_binding(rom, slug),
        }
    return _verify_story_subfield(
        root, rom, slug, DISPROVED_SPECS[slug]["sound_id"], candidate
    )


def verify_disproved_bank_candidate(
    root: Path, slug: str, *, rom: bytes | None = None
) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    if slug not in DISPROVED_SPECS:
        return {
            "schema": SCHEMA,
            "verified": False,
            "bank": slug,
            "errors": [f"unsupported disproved bank: {slug}"],
        }
    spec = DISPROVED_SPECS[slug]
    try:
        if rom is None:
            rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM identity changed")
        bank_path = _safe_file(root, f"sequel/content/{slug}/bank.json")
        bank = json.loads(bank_path.read_text(encoding="utf-8"))
        if (
            _sha(bank_path.read_bytes()) != spec["bank_sha256"]
            or bank.get("verification") != "disproved"
            or bank.get("entry_count") != 0
            or bank.get("entries") != []
        ):
            raise ValueError("disproved bank denominator changed")
        start, end = spec["candidate_range"]
        candidate = rom[start:end]
        if _sha(candidate) != spec["candidate_sha256"]:
            raise ValueError("candidate ROM bytes changed")
        details = _proof_details(root, rom, slug, candidate)
        evidence = {
            relative: _sha(_safe_file(root, relative).read_bytes())
            for relative in spec["evidence"]
        }
        return {
            "schema": SCHEMA,
            "verified": True,
            "errors": [],
            "bank": slug,
            "rejected": True,
            "rejection_scope": "independent_physical_bank_candidate",
            "alternative_logical_consumers_exhaustively_excluded": False,
            "proof_kind": spec["proof_kind"],
            "candidate_range": [start, end],
            "candidate_sha256": spec["candidate_sha256"],
            "bank_sha256": spec["bank_sha256"],
            "evidence_sha256": evidence,
            "details": details,
        }
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        return {
            "schema": SCHEMA,
            "verified": False,
            "errors": [str(error)],
            "bank": slug,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--bank", required=True)
    args = parser.parse_args()
    report = verify_disproved_bank_candidate(args.root, args.bank)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
