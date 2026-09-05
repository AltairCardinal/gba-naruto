#!/usr/bin/env python3
"""Independently verify the frozen scene-visual source-range promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


SCHEMA = "rom-scene-visual-source-ranges-v1"
VERIFY_SCHEMA = "rom-scene-visual-source-ranges-verification-v1"
PRODUCER_COMMAND = [
    "python3",
    "tools/export_rom_scene_visual_source_ranges.py",
    "--root",
    ".",
    "--output-dir",
    "build/experiments/active/luna-scene-visual-source-ranges-20260820/r2/final",
]
VERIFIER_COMMAND = [
    "python3",
    "tools/verify_rom_scene_visual_source_ranges.py",
    "--root",
    ".",
    "--artifact-dir",
    "build/experiments/active/luna-scene-visual-source-ranges-20260820/r2/final",
]
MANIFEST_KEYS = {
    "schema",
    "artifact_schema",
    "artifact_status",
    "files",
    "producer",
    "verifier",
    "rom",
    "source_identity",
    "coverage_baseline",
    "scope",
    "limitations",
}
ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SOURCE_ARTIFACT = Path("artifacts/scene-visual-packs-v1")
SOURCE_MANIFEST = SOURCE_ARTIFACT / "manifest.json"
SOURCE_VERIFIER = Path("tools/verify_scene_visual_packs.py")
SOURCE_SCHEMA = "scene-visual-packs-v1"
SOURCE_MANIFEST_SHA256 = "4bb40dff9ac2e5641b5e13f46b1dc90bdaa28b9b5615deab7e2a914ae002d5f4"
SOURCE_VERIFIER_SHA256 = "477d27ac7d8b1c11ecfaf3fe23d70bab9087349df5b36c041bb94911bca2293d"
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
COVERAGE_SCHEMA = "rom-byte-coverage-v1"
COVERAGE_SHA256 = "b95e1239420e416fe03244d8e3584adc5dd93470dfa8bfe8e501addb78c3f2cd"
COVERAGE_SUMMARY = {
    "classified_bytes": 6_102_121,
    "unknown_bytes": 189_335,
    "claim_count": 13_872,
    "segment_count": 16_119,
}
TABLE_GBA = 0x085A4CE8
TABLE_OFFSET = TABLE_GBA - ROM_BASE
TABLE_COUNT = 9
TABLE_ENTRY_SIZE = 0x1C
TABLE_SIZE = TABLE_COUNT * TABLE_ENTRY_SIZE
TABLE_SHA256 = "b562062061a088aac2e5ce2f2d9f8bbfd34f0cb53a794a7ea5b0f270ecf909b3"
SHARED_PALETTES = ((0, 0x083F2794, 0x20), (1, 0x083F2CB0, 0x20))
BACKGROUND_PALETTE_SIZE = 0x100
COMPONENT_SIZE = 0x14
ANIMATION_SIZE = 8
TERMINATOR = b"\xFF\xFF\x00\x00"
PAYLOAD_NAME = "rom-scene-visual-source-ranges.json"
BUNDLE_NAME = "rom-scene-visual-source-ranges.bin"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME}
FULL_RANGE_SHA256 = "6140246af1cf1a3c23e32ecf8d2e5b059a209f2d0a33131499a2bdb82c12743c"
CANDIDATE_RANGE_SHA256 = "6e8715e8eb59ad0a4912f5c714401c65b7911f4ec58b95d8d9d4fd7ae5e4e755"
PROMOTION_RANGE_SHA256 = "13dc504bebbff131700bb77869afb29e98a2f032d60bab4165eba90bcb2be7df"
OVERLAP_RANGE_SHA256 = "1434caee691420c22ad48a6c198507e5df8fb55b9ce25514fb91ebedc3d92b80"
PROMOTION_BUNDLE_SHA256 = "2eec5a820e1f79cc817e5976dc710e889adbee1038a4247652812a695832bc95"
LIMITATIONS = [
    "This is a fixed consumer/parser source extent inventory, not a claim over all scene sources.",
    "The existing LZ77 primary ranges are provenance only; this promotion does not assign new LZ77 semantics.",
    "The pack-05 definition overlap records the old primary claim and does not correct or replace that claim.",
    "No gap, padding, free-space, natural reachability, final-pixel, editing, relocation, or real-GBA claim is made.",
    "Consumer code is evidence only; pure consumer-code ownership is outside this source-range promotion.",
]
SCOPE = {
    "fixed_source_table_extent_complete": True,
    "fixed_lz77_extent_complete": True,
    "fixed_palette_extent_complete": True,
    "fixed_definition_parser_extent_complete": True,
    "fixed_animation_parser_extent_complete": True,
    "full_source_denominator_complete": True,
    "candidate_logic_denominator_complete": True,
    "promotion_current_unknown_only": True,
    "all_scene_sources": False,
    "natural_reachability": False,
    "final_pixels": False,
    "editing_or_relocation_safety": False,
    "real_gba_equivalence": False,
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _range_hash(ranges: list[list[int]]) -> str:
    return _sha(json.dumps(ranges, separators=(",", ":")).encode("ascii"))


def _address(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _safe_path(root: Path, relative: Path, *, directory: bool = False) -> Path:
    requested = root / relative
    cursor = Path(requested.anchor)
    for part in requested.absolute().parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository input path uses a symlink: {relative}")
        if not cursor.exists():
            break
    resolved = requested.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repository input escapes root: {relative}")
    if directory:
        if not resolved.is_dir():
            raise ValueError(f"repository input is not a directory: {relative}")
    elif not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _slice(rom: bytes, start: int, end: int) -> bytes:
    if start < 0 or end < start or end > len(rom):
        raise ValueError("ROM range is outside the input")
    return rom[start:end]


def _lz_extent(rom: bytes, pointer: int) -> tuple[int, int, int]:
    offset = pointer - ROM_BASE
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        raise ValueError("invalid LZ77 source")
    output_size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    cursor = offset + 4
    output = bytearray()
    while len(output) < output_size:
        if cursor >= len(rom):
            raise ValueError("truncated LZ77 flags")
        flags = rom[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(output) >= output_size:
                break
            if flags & (1 << bit):
                if cursor + 2 > len(rom):
                    raise ValueError("truncated LZ77 back-reference")
                first, second = rom[cursor : cursor + 2]
                cursor += 2
                length = (first >> 4) + 3
                distance = ((first & 0x0F) << 8 | second) + 1
                if distance > len(output) or len(output) + length > output_size:
                    raise ValueError("invalid LZ77 back-reference")
                for _ in range(length):
                    output.append(output[-distance])
            else:
                if cursor >= len(rom):
                    raise ValueError("truncated LZ77 literal")
                output.append(rom[cursor])
                cursor += 1
    return offset, cursor, output_size


def _parse_definition_extent(rom: bytes, pointer: int, frame_count: int) -> tuple[int, int, int]:
    pointer_offset = pointer - ROM_BASE
    table_end = pointer_offset + frame_count * 4
    if pointer_offset < 0 or table_end > len(rom):
        raise ValueError("definition pointer table is outside ROM")
    pointers = [
        int.from_bytes(rom[pointer_offset + index * 4 : pointer_offset + index * 4 + 4], "little")
        for index in range(frame_count)
    ]
    if not pointers or any(not ROM_BASE <= value < pointer for value in pointers):
        raise ValueError("definition pointer count or range changed")
    if pointers != sorted(set(pointers)):
        raise ValueError("definition pointers are not increasing")
    for start_address, end_address in zip(pointers, pointers[1:] + [pointer]):
        cursor = start_address - ROM_BASE
        end = end_address - ROM_BASE
        while cursor < end and rom[cursor : cursor + 4] != TERMINATOR:
            if cursor + COMPONENT_SIZE > len(rom):
                raise ValueError("definition component is truncated")
            raw = rom[cursor : cursor + COMPONENT_SIZE]
            tile_index = int.from_bytes(raw[0:2], "little")
            tile_flags = int.from_bytes(raw[2:4], "little")
            width = int.from_bytes(raw[8:10], "little")
            height = int.from_bytes(raw[10:12], "little")
            control = raw[16]
            affine_mode = raw[17]
            reserved = raw[18:20]
            if tile_index == 0xFFFF or tile_flags & ~3 or width not in (8, 16, 32, 64) or height not in (8, 16, 32, 64):
                raise ValueError("definition component dimensions changed")
            if control not in (0, 0xFF) or affine_mode not in (0, 1) or reserved != b"\x00\x00":
                raise ValueError("definition component parser fields changed")
            cursor += COMPONENT_SIZE
        if cursor + 4 > len(rom) or rom[cursor : cursor + 4] != TERMINATOR:
            raise ValueError("definition terminator is missing")
        cursor += 4
        if cursor != end:
            raise ValueError("definition parser extent changed")
    return pointers[0] - ROM_BASE, table_end, frame_count


def _parse_animation_extent(rom: bytes, timeline_start: int, pointer: int, frame_count: int) -> tuple[int, int, int]:
    pointer_offset = pointer - ROM_BASE
    table_end = pointer_offset + frame_count * 4
    if pointer_offset < 0 or table_end > len(rom):
        raise ValueError("animation pointer table is outside ROM")
    pointers = [
        int.from_bytes(rom[pointer_offset + index * 4 : pointer_offset + index * 4 + 4], "little")
        for index in range(frame_count)
    ]
    if not pointers or any(not timeline_start <= value < pointer for value in pointers):
        raise ValueError("animation pointer count or range changed")
    if pointers != sorted(set(pointers)):
        raise ValueError("animation pointers are not increasing")
    for start_address, end_address in zip(pointers, pointers[1:] + [pointer]):
        if end_address - start_address != ANIMATION_SIZE:
            raise ValueError("animation parser extent changed")
        frame_id, _timing, terminator, zero = struct.unpack("<HHHH", _slice(rom, start_address - ROM_BASE, end_address - ROM_BASE))
        if frame_id >= frame_count or terminator != 0xFFFF or zero:
            raise ValueError("animation terminator or frame selection changed")
    return pointers[0] - ROM_BASE, table_end, frame_count


def _record(source_id: str, kind: str, start: int, end: int, rom: bytes, **extra: Any) -> dict[str, Any]:
    raw = _slice(rom, start, end)
    result: dict[str, Any] = {
        "source_id": source_id,
        "kind": kind,
        "range": [start, end],
        "gba_range": [_address(start), _address(end)],
        "size": end - start,
        "raw_sha256": _sha(raw),
    }
    result.update(extra)
    return result


def _records_from_rom(rom: bytes) -> list[dict[str, Any]]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity mismatch")
    table = _slice(rom, TABLE_OFFSET, TABLE_OFFSET + TABLE_SIZE)
    if _sha(table) != TABLE_SHA256:
        raise ValueError("scene visual source table changed")
    rows = [
        struct.unpack("<IIIIIIBBBB", table[index * TABLE_ENTRY_SIZE : (index + 1) * TABLE_ENTRY_SIZE])
        for index in range(TABLE_COUNT)
    ]
    records = [_record("scene-source-table", "source_table", TABLE_OFFSET, TABLE_OFFSET + TABLE_SIZE, rom, gba_address=_address(TABLE_OFFSET), entry_count=TABLE_COUNT, entry_size=TABLE_ENTRY_SIZE, table_sha256=TABLE_SHA256)]
    for pack_id, row in enumerate(rows):
        bg_gfx, bg_map, bg_palette, obj_gfx, definition, animation, _width, _height, _presentation, spawn_count = row
        for label, pointer in (("background-gfx", bg_gfx), ("background-tilemap", bg_map), ("obj-gfx", obj_gfx)):
            start, end, output_size = _lz_extent(rom, pointer)
            records.append(_record(f"pack-{pack_id:02d}-{label}", "lz77", start, end, rom, pack_id=pack_id, pointer_gba=f"0x{pointer:08X}", decompressed_size=output_size))
        records.append(_record(f"pack-{pack_id:02d}-background-palette", "background_palette", bg_palette - ROM_BASE, bg_palette - ROM_BASE + BACKGROUND_PALETTE_SIZE, rom, pack_id=pack_id, pointer_gba=f"0x{bg_palette:08X}"))
        definition_start, definition_table_end, _ = _parse_definition_extent(rom, definition, spawn_count)
        records.append(_record(f"pack-{pack_id:02d}-definition", "definition", definition_start, definition_table_end, rom, pack_id=pack_id, pointer_gba=f"0x{definition:08X}", frame_count=spawn_count))
        animation_start, animation_table_end, _ = _parse_animation_extent(rom, ROM_BASE + definition_table_end, animation, spawn_count)
        records.append(_record(f"pack-{pack_id:02d}-animation", "animation", animation_start, animation_table_end, rom, pack_id=pack_id, pointer_gba=f"0x{animation:08X}", frame_count=spawn_count))
    for bank, pointer, size in SHARED_PALETTES:
        records.append(_record(f"shared-obj-palette-{bank}", "shared_obj_palette", pointer - ROM_BASE, pointer - ROM_BASE + size, rom, bank=bank, pointer_gba=f"0x{pointer:08X}"))
    records.sort(key=lambda item: (item["range"][0], item["range"][1], item["source_id"]))
    previous_end = -1
    for item in records:
        start, end = item["range"]
        if start < previous_end:
            raise ValueError("scene visual source ranges overlap")
        previous_end = end
    return records


def _identity(root: Path) -> dict[str, Any]:
    manifest_path = _safe_path(root, SOURCE_MANIFEST)
    source_dir = _safe_path(root, SOURCE_ARTIFACT, directory=True)
    for member in source_dir.rglob("*"):
        if member.is_symlink():
            raise ValueError("scene visual source artifact uses a symlink")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SOURCE_SCHEMA or _sha(manifest_path.read_bytes()) != SOURCE_MANIFEST_SHA256:
        raise ValueError("scene visual source manifest identity changed")
    verifier_path = _safe_path(root, SOURCE_VERIFIER)
    if _sha(verifier_path.read_bytes()) != SOURCE_VERIFIER_SHA256:
        raise ValueError("scene visual source verifier identity changed")
    try:
        from tools.verify_scene_visual_packs import verify_artifact
    except ModuleNotFoundError:  # pragma: no cover
        from verify_scene_visual_packs import verify_artifact
    report = verify_artifact(root, source_dir)
    expected_report = {"verified": True, "errors": [], "pack_count": 9, "obj_frame_count": 16, "obj_animation_count": 16}
    if report != expected_report:
        raise ValueError("scene visual source verifier report changed")
    return {
        "artifact_path": SOURCE_ARTIFACT.as_posix(),
        "artifact_schema": SOURCE_SCHEMA,
        "manifest_path": SOURCE_MANIFEST.as_posix(),
        "manifest_sha256": SOURCE_MANIFEST_SHA256,
        "verifier_path": SOURCE_VERIFIER.as_posix(),
        "verifier_sha256": SOURCE_VERIFIER_SHA256,
        "verifier_report": report,
    }


def _coverage(root: Path) -> dict[str, Any]:
    path = _safe_path(root, COVERAGE_PATH)
    if _sha(path.read_bytes()) != COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    value = json.loads(path.read_text(encoding="utf-8"))
    _validate_coverage_identity(value)
    return value


def _validate_coverage_identity(coverage: dict[str, Any]) -> None:
    if _sha(_canonical(coverage)) != COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    if coverage.get("schema") != COVERAGE_SCHEMA or coverage.get("base_rom") != {
        "path": ROM_PATH.as_posix(),
        "sha256": ROM_SHA256,
        "size": ROM_SIZE,
    }:
        raise ValueError("coverage baseline identity changed")
    if coverage.get("domain") != [0, ROM_SIZE] or coverage.get("policy") != {
        "one_primary_claim_per_byte": True,
        "padding_is_not_automatically_free_space": True,
        "ranges_are_half_open": True,
        "secondary_claims_are_explicit": True,
        "unknown_is_required_not_implicit": True,
    }:
        raise ValueError("coverage baseline domain or policy changed")
    summary = coverage.get("summary")
    if not isinstance(summary, dict) or {
        key: summary.get(key) for key in COVERAGE_SUMMARY
    } != COVERAGE_SUMMARY:
        raise ValueError("coverage baseline summary changed")


def _span_map(coverage: dict[str, Any]) -> list[dict[str, Any]]:
    segments = coverage.get("segments")
    if not isinstance(segments, list) or len(segments) != COVERAGE_SUMMARY["segment_count"]:
        raise ValueError("coverage baseline segments changed")
    previous = 0
    for segment in segments:
        if not isinstance(segment, dict) or not isinstance(segment.get("range"), list) or len(segment["range"]) != 2:
            raise ValueError("coverage baseline segment shape changed")
        start, end = segment["range"]
        if not isinstance(start, int) or not isinstance(end, int) or start != previous or end <= start or end > ROM_SIZE:
            raise ValueError("coverage baseline range partition changed")
        previous = end
    if previous != ROM_SIZE:
        raise ValueError("coverage baseline range partition is incomplete")
    return segments


def _segment_covering(segments: list[dict[str, Any]], start: int, end: int) -> list[dict[str, Any]]:
    result = [segment for segment in segments if segment["range"][0] < end and segment["range"][1] > start]
    if not result or result[0]["range"][0] > start or result[-1]["range"][1] < end:
        raise ValueError("coverage baseline does not cover source range")
    return result


def _validate_baseline_records(rom: bytes, records: list[dict[str, Any]], coverage: dict[str, Any]) -> None:
    segments = _span_map(coverage)
    claims = coverage.get("claims")
    if not isinstance(claims, list):
        raise ValueError("coverage baseline claims changed")
    claim_map = {item.get("id"): item for item in claims if isinstance(item, dict)}
    expected_primary = {
        (TABLE_OFFSET, TABLE_OFFSET + TABLE_SIZE): ("scene_visual_pack_source_table", ["verified-reuse-scene-visual-pack-source-table-5a4ce8"])
    }
    for item in records:
        start, end = item["range"]
        if item["kind"] == "lz77":
            expected_primary[(start, end)] = ("lz77_resource", [f"lz77-{start:x}"])
    for (start, end), (primary_class, owner_ids) in expected_primary.items():
        covered = _segment_covering(segments, start, end)
        if len(covered) != 1 or covered[0]["range"] != [start, end] or covered[0].get("primary_class") != primary_class or covered[0].get("primary_claim_ids") != owner_ids or covered[0].get("secondary_claim_ids") != []:
            raise ValueError("coverage baseline source owner changed")
        for owner_id in owner_ids:
            claim = claim_map.get(owner_id)
            if not isinstance(claim, dict) or claim.get("range") != [start, end] or claim.get("primary_class") != primary_class or claim.get("role") != "primary" or claim.get("bytes_sha256") != _sha(_slice(rom, start, end)):
                raise ValueError("coverage baseline source claim changed")
    candidate = [item for item in records if item["kind"] in {"shared_obj_palette", "background_palette", "definition", "animation"}]
    for item in candidate:
        start, end = item["range"]
        covered = _segment_covering(segments, start, end)
        if [start, end] == [0x407BF0, 0x407C50]:
            expected = [([0x407BF0, 0x407C0F], "lz77_syntax_unbound", ["unbound-lz77-35-407bec"]), ([0x407C0F, 0x407C50], "unknown", [])]
        else:
            expected = [([start, end], "unknown", [])]
        if len(covered) != len(expected):
            raise ValueError("coverage baseline candidate overlap changed")
        intersections = [[max(start, segment["range"][0]), min(end, segment["range"][1])] for segment in covered]
        expected_intersections = [[max(start, expected_range[0]), min(end, expected_range[1])] for expected_range, _primary_class, _owner_ids in expected]
        if intersections != expected_intersections:
            raise ValueError("coverage baseline candidate range changed")
        for segment, (_expected_range, primary_class, owner_ids) in zip(covered, expected):
            if segment.get("primary_class") != primary_class or segment.get("primary_claim_ids") != owner_ids or segment.get("secondary_claim_ids") != []:
                raise ValueError("coverage baseline candidate owner changed")
            for owner_id in owner_ids:
                claim = claim_map.get(owner_id)
                if not isinstance(claim, dict) or claim.get("range") != segment["range"] or claim.get("primary_class") != primary_class or claim.get("role") != "primary" or claim.get("bytes_sha256") != _sha(_slice(rom, *segment["range"])):
                    raise ValueError("coverage baseline overlap claim changed")


def _validate_frozen_baseline_records(rom: bytes, records: list[dict[str, Any]]) -> None:
    """Validate the compact ownership facts frozen into this packet.

    Artifact verification deliberately does not read the repository's live
    coverage file.  The source table/LZ77 ownership and the sole candidate
    overlap are fixed contract facts, rebuilt from the ROM and compared here.
    """
    source_table = [item for item in records if item["kind"] == "source_table"]
    if [item["range"] for item in source_table] != [[TABLE_OFFSET, TABLE_OFFSET + TABLE_SIZE]]:
        raise ValueError("frozen baseline source table ownership changed")
    lz_records = [item for item in records if item["kind"] == "lz77"]
    if len(lz_records) != 27:
        raise ValueError("frozen baseline LZ77 ownership count changed")
    candidate_records = [
        item
        for item in records
        if item["kind"] in {"shared_obj_palette", "background_palette", "definition", "animation"}
    ]
    if len(candidate_records) != 29:
        raise ValueError("frozen baseline candidate ownership count changed")
    for item in candidate_records:
        start, end = item["range"]
        if [start, end] == [0x407BF0, 0x407C50]:
            known = _slice(rom, 0x407BF0, 0x407C0F)
            unknown = _slice(rom, 0x407C0F, 0x407C50)
            if not known or not unknown:
                raise ValueError("frozen baseline candidate overlap is empty")
        elif start >= end:
            raise ValueError("frozen baseline candidate range changed")


def validate_baseline(root: Path | str, payload: dict[str, Any], coverage: dict[str, Any]) -> None:
    root = Path(root).resolve(strict=True)
    rom = _safe_path(root, ROM_PATH).read_bytes()
    if payload.get("rom", {}).get("sha256") != ROM_SHA256:
        raise ValueError("payload ROM identity changed")
    records = _records_from_rom(rom)
    _validate_coverage_identity(coverage)
    _validate_baseline_records(rom, records, coverage)


def _denominator(records: list[dict[str, Any]]) -> dict[str, Any]:
    chosen = sorted(records, key=lambda item: (item["range"][0], item["range"][1], item["source_id"]))
    vector = [item["range"] for item in chosen]
    return {"range_count": len(chosen), "byte_count": sum(item["size"] for item in chosen), "range_vector": vector, "range_vector_sha256": _range_hash(vector), "records": chosen}


def _implementation(root: Path) -> dict[str, Any]:
    paths = {"exporter": Path("tools/export_rom_scene_visual_source_ranges.py"), "verifier": Path("tools/verify_rom_scene_visual_source_ranges.py"), "test": Path("tests/test_export_rom_scene_visual_source_ranges.py")}
    return {label: {"path": path.as_posix(), "sha256": _sha(_safe_path(root, path).read_bytes())} for label, path in paths.items()}


def _build_payload(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    records = _records_from_rom(rom)
    source_identity = _identity(root)
    _validate_frozen_baseline_records(rom, records)
    candidate_records = []
    for record in records:
        if record["kind"] not in {"shared_obj_palette", "background_palette", "definition", "animation"}:
            continue
        if record["range"] == [0x407BF0, 0x407C50]:
            candidate_records.append(
                {
                    **record,
                    "promotion_state": "mixed",
                    "baseline_state": "mixed",
                    "known_slices": [[0x407BF0, 0x407C0F]],
                    "unknown_slices": [[0x407C0F, 0x407C50]],
                }
            )
        else:
            candidate_records.append(
                {
                    **record,
                    "promotion_state": "current_unknown",
                    "baseline_state": "current_unknown",
                }
            )
    candidate_records.sort(key=lambda item: (item["range"][0], item["range"][1], item["source_id"]))
    overlap_records = [{"source_id": "pack-05-definition", "range": [0x407BF0, 0x407C0F], "size": 31, "primary_class": "lz77_syntax_unbound", "primary_claim_ids": ["unbound-lz77-35-407bec"]}]
    promotion_records = []
    for row in candidate_records:
        if row["range"] == [0x407BF0, 0x407C50]:
            start, end = 0x407C0F, 0x407C50
            promotion_record = {
                **row,
                "range": [start, end],
                "gba_range": [_address(start), _address(end)],
                "size": end - start,
                "raw_sha256": _sha(_slice(rom, start, end)),
                "promotion_state": "current_unknown",
                "baseline_state": "current_unknown",
            }
            promotion_record.pop("known_slices", None)
            promotion_record.pop("unknown_slices", None)
            promotion_records.append(promotion_record)
        else:
            promotion_records.append({**row, "promotion_state": "current_unknown", "baseline_state": "current_unknown"})
    full = _denominator(records)
    candidate = _denominator(candidate_records)
    promotion = _denominator(promotion_records)
    overlap = {"range_count": 1, "byte_count": 31, "range_vector": [[0x407BF0, 0x407C0F]], "range_vector_sha256": OVERLAP_RANGE_SHA256, "records": overlap_records}
    if (full["range_count"], full["byte_count"], full["range_vector_sha256"]) != (57, 88756, FULL_RANGE_SHA256):
        raise ValueError("full scene visual source denominator changed")
    if (candidate["range_count"], candidate["byte_count"], candidate["range_vector_sha256"]) != (29, 3288, CANDIDATE_RANGE_SHA256):
        raise ValueError("candidate scene visual source denominator changed")
    if (promotion["range_count"], promotion["byte_count"], promotion["range_vector_sha256"]) != (29, 3257, PROMOTION_RANGE_SHA256):
        raise ValueError("promotion scene visual source denominator changed")
    bundle = b"".join(_slice(rom, start, end) for start, end in promotion["range_vector"])
    if _sha(bundle) != PROMOTION_BUNDLE_SHA256:
        raise ValueError("scene visual source promotion bundle changed")
    class_counts = {}
    for kind, name in (("shared_obj_palette", "shared_obj_palette"), ("background_palette", "background_palette"), ("definition", "definition"), ("animation", "animation")):
        chosen = [row for row in candidate_records if row["kind"] == kind]
        class_counts[name] = {"range_count": len(chosen), "byte_count": sum(row["size"] for row in chosen)}
    coverage_identity = {"path": COVERAGE_PATH.as_posix(), "schema": COVERAGE_SCHEMA, "sha256": COVERAGE_SHA256, "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256}, "summary": COVERAGE_SUMMARY}
    implementation = _implementation(root)
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "source_identity": source_identity,
        "coverage_baseline": coverage_identity,
        "source_denominator": full,
        "candidate_denominator": candidate,
        "overlap_denominator": overlap,
        "promotion_denominator": {**promotion, "bundle": {"path": BUNDLE_NAME, "size": len(bundle), "sha256": _sha(bundle)}},
        "summary": {"source_record_count": 57, "source_bytes": 88756, "candidate_range_count": 29, "candidate_bytes": 3288, "overlap_range_count": 1, "overlap_bytes": 31, "promotion_range_count": 29, "promotion_bytes": 3257, "candidate_class_counts": class_counts, "promotion_bundle_sha256": _sha(bundle)},
        "scope": SCOPE,
        "limitations": LIMITATIONS,
        "implementation": implementation,
        "files": {BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bundle)}},
    }
    return payload, bundle


def build_payload(root: Path | str) -> tuple[dict[str, Any], bytes]:
    root = Path(root).resolve(strict=True)
    return _build_payload(root, _safe_path(root, ROM_PATH).read_bytes())


def rebuild_from_rom(root: Path | str, rom: bytes) -> tuple[dict[str, Any], bytes]:
    root = Path(root).resolve(strict=True)
    return _build_payload(root, rom)


def rebuild_payload(root: Path | str) -> tuple[dict[str, Any], bytes]:
    return build_payload(root)


def _expected_report(payload: dict[str, Any], bundle: bytes) -> dict[str, Any]:
    return {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        "errors": [],
        "summary": payload["summary"],
        "bundle_sha256": _sha(bundle),
        "artifact_schema": SCHEMA,
    }


def _verify(root: Path, artifact: Path) -> dict[str, Any]:
    if artifact.is_symlink() or not artifact.is_dir():
        raise ValueError("artifact directory is invalid")
    members = list(artifact.rglob("*"))
    if any(member.is_symlink() for member in members):
        raise ValueError("artifact contains a symlink")
    actual = {member.relative_to(artifact).as_posix() for member in members if member.is_file()}
    if actual != EXPECTED_FILES:
        raise ValueError("artifact file set mismatch")
    manifest_path = artifact / "manifest.json"
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw.decode("utf-8"))
    if _canonical(manifest) != manifest_raw:
        raise ValueError("manifest is not canonical JSON")
    if set(manifest) != MANIFEST_KEYS:
        raise ValueError("manifest key set mismatch")
    if manifest.get("schema") != "git-artifact-promotion-v1" or manifest.get("artifact_schema") != SCHEMA or manifest.get("artifact_status") not in {"candidate", "accepted"}:
        raise ValueError("artifact manifest identity mismatch")
    payload_path = artifact / PAYLOAD_NAME
    payload_raw = payload_path.read_bytes()
    payload = json.loads(payload_raw.decode("utf-8"))
    if _canonical(payload) != payload_raw or payload.get("schema") != SCHEMA:
        raise ValueError("payload is not canonical or schema changed")
    bundle = (artifact / BUNDLE_NAME).read_bytes()
    expected_files = {PAYLOAD_NAME: _sha(payload_raw), BUNDLE_NAME: _sha(bundle)}
    if manifest.get("files") != expected_files:
        raise ValueError("artifact file hashes mismatch")
    root = root.resolve(strict=True)
    rom = _safe_path(root, ROM_PATH).read_bytes()
    rebuilt, rebuilt_bundle = _build_payload(root, rom)
    if payload != rebuilt:
        raise ValueError("payload does not match raw ROM/source/baseline rebuild")
    if bundle != rebuilt_bundle:
        raise ValueError("promotion bundle does not match raw ROM range order")
    if payload.get("promotion_denominator", {}).get("bundle", {}).get("sha256") != _sha(bundle):
        raise ValueError("payload bundle identity mismatch")
    implementation = payload["implementation"]
    expected_producer = {"command": PRODUCER_COMMAND, **implementation}
    if manifest.get("producer") != expected_producer:
        raise ValueError("manifest implementation identity mismatch")
    if manifest.get("rom") != payload["rom"] or manifest.get("source_identity") != payload["source_identity"] or manifest.get("coverage_baseline") != payload["coverage_baseline"] or manifest.get("scope") != payload["scope"] or manifest.get("limitations") != payload["limitations"]:
        raise ValueError("manifest provenance mismatch")
    report = _expected_report(payload, bundle)
    verifier = manifest.get("verifier")
    if not isinstance(verifier, dict) or set(verifier) != {"schema", "command", "exit_code", "report", "verifier_sha256"}:
        raise ValueError("verifier receipt is missing")
    if verifier.get("schema") != VERIFY_SCHEMA or verifier.get("command") != VERIFIER_COMMAND or verifier.get("verifier_sha256") != implementation["verifier"]["sha256"]:
        raise ValueError("manifest verifier identity mismatch")
    if manifest.get("artifact_status") == "accepted":
        if verifier.get("exit_code") != 0 or verifier.get("report") != report:
            raise ValueError("verifier receipt does not match exact rebuild")
    elif verifier.get("exit_code") is not None or verifier.get("report") is not None:
        raise ValueError("candidate verifier receipt is malformed")
    return report


def verify_artifact(root: Path | str, artifact_dir: Path | str) -> dict[str, Any]:
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact_dir).expanduser()
        if not artifact.is_absolute():
            artifact = root / artifact
        artifact = artifact.absolute()
        # Reject lexical symlinks in the artifact path before resolving it.
        cursor = Path(artifact.anchor)
        for part in artifact.parts[1:]:
            cursor /= part
            if cursor.is_symlink():
                raise ValueError("artifact path uses a symlink")
            if not cursor.exists():
                break
        artifact = artifact.resolve(strict=True)
        report = _verify(root, artifact)
        return report
    except (KeyError, OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
        return {"schema": VERIFY_SCHEMA, "verified": False, "errors": [str(error)], "summary": {}, "bundle_sha256": None, "artifact_schema": SCHEMA}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, default=Path(f"artifacts/{SCHEMA}"))
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
