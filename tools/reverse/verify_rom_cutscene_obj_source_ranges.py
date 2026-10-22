#!/usr/bin/env python3
"""Independently verify the fixed Cutscene OBJ source-range artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


SCHEMA = "rom-cutscene-obj-source-ranges-v1"
VERIFY_SCHEMA = "rom-cutscene-obj-source-ranges-verification-v1"
ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

RESOURCE_TABLE_OFFSET = 0x53DF70
SPRITE_TABLE_OFFSET = 0x53DF90
ENTRY_COUNT = 4
ENTRY_SIZE = 8
RESOURCE_TABLE_SHA256 = "16b13c432f37ba159697cd9d9d6d5d5147adc41c44c8cc0cc44ce7f2935f1401"
SPRITE_TABLE_SHA256 = "1c76f2100b2067e78abd713e312bd845d7c874b030f51ef08f968961862e198a"
COMBINED_TABLE_SHA256 = "1e6d5016b58d0e565c5a40791a7f2684d6129e0a1c4e85e79317af4d2b1a7f62"

FRAME_COUNTS = (2, 2, 2, 4)
DEFINITION_COMPONENT_SIZE = 20
DEFINITION_RECORD_SIZE = 24
ANIMATION_RECORD_SIZE = 8
TERMINATOR = bytes.fromhex("ffff0000")
RESOURCE_ENVELOPES = (
    (0x12DEFC, 0x12DF4C),
    (0x12E444, 0x12E494),
    (0x12E960, 0x12E9B0),
    (0x12ED70, 0x12EE10),
)
EXPECTED_POINTERS = (
    (0x0812D9E4, 0x0812DEE4, 0x0812DF2C, 0x0812DF44),
    (0x0812DF4C, 0x0812E42C, 0x0812E474, 0x0812E48C),
    (0x0812E494, 0x0812E948, 0x0812E990, 0x0812E9A8),
    (0x0812E9B0, 0x0812ED58, 0x0812EDD0, 0x0812EE00),
)
EXPECTED_COMPONENTS = (
    ((0, 0, 0, -32, -32, 64, 64, 0x100, 0x100, 0xFF, 0, 0), (64, 0, 0, -32, -32, 64, 64, 0x100, 0x100, 0xFF, 0, 0)),
    ((0, 0, 0, -32, -32, 64, 64, 0x100, 0x100, 0xFF, 0, 0), (64, 0, 0, -32, -32, 64, 64, 0x100, 0x100, 0xFF, 0, 0)),
    ((0, 0, 0, -32, -32, 64, 64, 0x100, 0x100, 0xFF, 0, 0), (64, 0, 0, -32, -32, 64, 64, 0x100, 0x100, 0xFF, 0, 0)),
    ((0, 0, 0, -16, -16, 32, 32, 0x100, 0x100, 0xFF, 0, 0), (16, 0, 0, -16, -16, 32, 32, 0x100, 0x100, 0xFF, 0, 0), (32, 0, 0, -16, -16, 32, 32, 0x100, 0x100, 0xFF, 0, 0), (48, 0, 0, -16, -16, 32, 32, 0x100, 0x100, 0xFF, 0, 0)),
)
EXPECTED_DURATIONS = (1, 0)

CONSUMER_SLICES = (
    ("sprite_task_allocator", 0x080625A4, 0x080626B0, "e238cd1ee159265fb8b718766f336f8d5462596954f93c7805d1bf33dd6b3c54"),
    ("animation_frame_selector", 0x0806298C, 0x080629A0, "62718fbb246078256e2c3344773d0ab9a0b2c10aee2fb3890d16e134b331e1ab"),
    ("animation_timing_consumer", 0x08063256, 0x080632D8, "1ec4801f36351e56d511caaa6cc5fdf31d52142292e64d3c9cf6567eed468be0"),
)
COMPONENT_PARSER_SLICE = (
    "component_stride_and_terminator",
    0x080631F6,
    0x08063210,
    "71906dd2a83fd26e1065d14aecb07a05190a96d46ff95ca1cd12a05fa8c93fe4",
)
COMPONENT_PARSER_HALFWORDS = (
    0x2514,
    0x44A8,
    0x4640,
    0x2200,
    0x5E81,
    0x2001,
    0x4240,
    0x4281,
    0xD00B,
)
CONSUMER_KEY_BYTES = {
    0x080625A4: bytes.fromhex("f0b557464e464546e0b482b0"),
    0x08062668: bytes.fromhex("f800009940180168e16140682062"),
    0x0806298C: bytes.fromhex("b98a386a89000918f88a80000968091800910025"),
    0x08063256: bytes.fromhex("388b01303883009a0223d05e3a8b904237d1009b0422985e404508d0f88a0130f8821fe0"),
}

UPSTREAM_MANIFEST = Path("artifacts/cutscene-obj-v1/manifest.json")
UPSTREAM_VERIFIER = Path("tools/verify_cutscene_obj_export.py")
UPSTREAM_MANIFEST_SHA256 = "b8e1341172decef9f07080879cd8369bc5308274d84383d5c706de72a0b781e7"
UPSTREAM_VERIFIER_SHA256 = "8f8dee83cdbf8da910cd7165fce167a9840394b1a079dd7526531218f99d32d3"
RELOCATION_DIR = Path("artifacts/cutscene-obj-bundle-relocation-v1")
RELOCATION_MANIFEST = RELOCATION_DIR / "manifest.json"
RELOCATION_MANIFEST_SHA256 = "5438878f03972989ca20c302cce4a526b594208b8458399a2b0d2d2455b1868b"

PAYLOAD_NAME = "rom-cutscene-obj-source-ranges.json"
BUNDLE_NAME = "rom-cutscene-obj-source-ranges.bin"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME}
PRODUCER_COMMAND = [
    "python3", "tools/export_rom_cutscene_obj_source_ranges.py", "--root", ".",
    "--output-dir", "build/experiments/active/cutscene-obj-source-ranges/r5/final",
]
VERIFIER_COMMAND = [
    "python3", "tools/verify_rom_cutscene_obj_source_ranges.py", "--root", ".",
    "--artifact-dir", "build/experiments/active/cutscene-obj-source-ranges/r5/final",
]
MANIFEST_KEYS = {
    "schema", "artifact_schema", "artifact_status", "files", "producer", "verifier",
    "rom", "source_identity", "scope", "limitations",
}

SCOPE = {
    "fixed_resource_ids": [0, 1, 2, 3],
    "fixed_frame_counts": [2, 2, 2, 4],
    "source_records_and_pointer_tables_only": True,
    "natural_all_id_or_frame_reachability": False,
    "all_scene_or_cutscene_sources": False,
    "final_pixels": False,
    "definition_unknown_field_semantics": False,
    "graphics_or_palette_expansion": False,
    "editing_writeback_or_relocation_safety": False,
    "free_space": False,
}
LIMITATIONS = [
    "Only the four fixed resource IDs and their fixed definition/animation source records and pointer tables are classified.",
    "This does not claim natural reachability of every ID or frame, all scene/cutscene sources, or final screen-composited pixels.",
    "Definition fields unknown_10_byte and unknown_12 remain unknown; graphics, palette expansion, and other resource envelopes are outside scope.",
    "No editing, write-back, relocation, free-space, allocatability, or post-modification runtime equivalence is claimed.",
]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _vector_sha(value: Any) -> str:
    return _sha(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _offset(address: int) -> int:
    if address < ROM_BASE:
        raise ValueError("GBA address precedes ROM base")
    return address - ROM_BASE


def _slice(rom: bytes, start: int, end: int) -> bytes:
    if start < 0 or end < start or end > len(rom):
        raise ValueError("ROM range is outside the input")
    return rom[start:end]


def _safe_file(root: Path, relative: Path) -> Path:
    root = root.resolve(strict=True)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative path: {relative}")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {relative}")
    resolved = (root / relative).resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"repository input escapes root: {relative}") from error
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _safe_dir(root: Path, relative: Path) -> Path:
    root = root.resolve(strict=True)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative path: {relative}")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {relative}")
    resolved = (root / relative).resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"repository input escapes root: {relative}") from error
    if not resolved.is_dir():
        raise ValueError(f"repository input is not a directory: {relative}")
    return resolved


def _read_bound(root: Path, relative: Path, expected_sha256: str) -> bytes:
    path = _safe_file(root, relative)
    raw = path.read_bytes()
    if _sha(raw) != expected_sha256:
        raise ValueError(f"bound source changed: {relative}")
    return raw


def _read_root_pairs(rom: bytes) -> tuple[tuple[int, int, int, int], ...]:
    combined = _slice(
        rom,
        RESOURCE_TABLE_OFFSET,
        SPRITE_TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE,
    )
    split = ENTRY_COUNT * ENTRY_SIZE
    resource_half, sprite_half = combined[:split], combined[split:]
    if _sha(resource_half) != RESOURCE_TABLE_SHA256:
        raise ValueError("resource root table hash changed")
    if _sha(sprite_half) != SPRITE_TABLE_SHA256:
        raise ValueError("sprite root table hash changed")
    if _sha(combined) != COMBINED_TABLE_SHA256:
        raise ValueError("combined root table hash changed")

    roots: list[tuple[int, int, int, int]] = []
    for resource_id in range(ENTRY_COUNT):
        slot = resource_id * ENTRY_SIZE
        values = tuple(
            int.from_bytes(raw[start : start + 4], "little")
            for raw in (resource_half, sprite_half)
            for start in (slot, slot + 4)
        )
        if values != EXPECTED_POINTERS[resource_id]:
            raise ValueError(f"resource {resource_id} root pointer vector changed")
        roots.append(values)
    return tuple(roots)


def _decode_component_abi(
    raw: bytes, resource_id: int, frame_id: int
) -> dict[str, Any]:
    if len(raw) != DEFINITION_RECORD_SIZE:
        raise ValueError("definition record size changed")
    if raw[-len(TERMINATOR) :] != TERMINATOR:
        raise ValueError(
            f"resource {resource_id} frame {frame_id} definition terminator changed"
        )
    values = struct.Struct("<HBBhhhhhhBBH").unpack_from(raw)
    if values != EXPECTED_COMPONENTS[resource_id][frame_id]:
        raise ValueError(
            f"resource {resource_id} frame {frame_id} definition component semantics changed"
        )
    names = (
        "tile_offset",
        "flag_02",
        "flag_03",
        "horizontal_position_input",
        "vertical_position_input",
        "width",
        "height",
        "transform_factor_0c",
        "transform_factor_0e",
        "unknown_10_byte",
        "oam_attribute_byte",
        "unknown_12",
    )
    decoded = dict(zip(names, values, strict=True))
    if (
        decoded["width"] not in (32, 64)
        or decoded["height"] != decoded["width"]
        or decoded["horizontal_position_input"] != -decoded["width"] // 2
        or decoded["vertical_position_input"] != -decoded["height"] // 2
        or (decoded["transform_factor_0c"], decoded["transform_factor_0e"])
        != (0x100, 0x100)
    ):
        raise ValueError("definition component geometry changed")
    return decoded


def _decode_animation_claim(
    raw: bytes, resource_id: int, frame_id: int
) -> tuple[int, int]:
    if len(raw) != ANIMATION_RECORD_SIZE:
        raise ValueError("animation record size changed")
    frame_value, duration, terminator, zero = struct.unpack("<HHHH", raw)
    expected_duration = 1 if frame_id == 0 else 0
    if (frame_value, duration, terminator, zero) != (
        frame_id,
        expected_duration,
        0xFFFF,
        0,
    ):
        raise ValueError(
            f"resource {resource_id} frame {frame_id} animation semantics changed"
        )
    return frame_value, duration


def _assert_record_common(
    record: Any,
    rom: bytes,
    *,
    resource_id: int,
    kind: str,
    start: int,
    end: int,
    selector: dict[str, Any],
    extra_keys: set[str],
) -> bytes:
    base_keys = {
        "resource_id",
        "kind",
        "range",
        "gba_range",
        "size",
        "raw_hex",
        "raw_sha256",
        "selector",
    }
    if not isinstance(record, dict) or set(record) != base_keys | extra_keys:
        raise ValueError(f"{kind} record key set changed")
    raw = _slice(rom, start, end)
    if (
        record["resource_id"] != resource_id
        or record["kind"] != kind
        or record["range"] != [start, end]
        or record["gba_range"] != [_gba(start), _gba(end)]
        or record["size"] != end - start
        or record["raw_hex"] != raw.hex()
        or record["raw_sha256"] != _sha(raw)
        or record["selector"] != selector
    ):
        raise ValueError(f"{kind} record bytes or selector changed")
    return raw


def _consumer_evidence(rom: bytes) -> dict[str, Any]:
    evidence = []
    for name, start_gba, end_gba, expected in CONSUMER_SLICES:
        start, end = _offset(start_gba), _offset(end_gba)
        raw = _slice(rom, start, end)
        if _sha(raw) != expected:
            raise ValueError(f"consumer slice changed: {name}")
        evidence.append({"name": name, "gba_range": [f"0x{start_gba:08X}", f"0x{end_gba:08X}"], "range": [start, end], "size": len(raw), "sha256": _sha(raw)})
    for address, expected in CONSUMER_KEY_BYTES.items():
        if _slice(rom, _offset(address), _offset(address) + len(expected)) != expected:
            raise ValueError(f"consumer semantic bytes changed at 0x{address:08X}")
    if _slice(rom, _offset(0x08062668), _offset(0x08062668) + 14).hex() != "f800009940180168e16140682062":
        raise ValueError("sprite pair-install consumer semantics changed")
    parser_name, parser_start_gba, parser_end_gba, parser_sha256 = (
        COMPONENT_PARSER_SLICE
    )
    parser_raw = _slice(
        rom, _offset(parser_start_gba), _offset(parser_end_gba)
    )
    if _sha(parser_raw) != parser_sha256:
        raise ValueError("component parser slice changed")
    parser_halfwords = tuple(
        int.from_bytes(parser_raw[offset : offset + 2], "little")
        for offset in range(0, 18, 2)
    )
    if parser_halfwords != COMPONENT_PARSER_HALFWORDS:
        raise ValueError("component parser stride or terminator semantics changed")
    return {
        "addresses": [
            "0x080625A4",
            "0x08062668",
            "0x0806298C",
            "0x080631F6",
            "0x08063256",
        ],
        "slices": evidence,
        "key_windows": {f"0x{address:08X}": {"size": len(expected), "raw_hex": expected.hex(), "sha256": _sha(expected)} for address, expected in sorted(CONSUMER_KEY_BYTES.items())},
        "pair_install": {"gba_address": "0x08062668", "raw_hex": "f800009940180168e16140682062", "semantic": "id_times_8_installs_definition_and_animation_pointers"},
        "component_parser": {
            "name": parser_name,
            "gba_range": [
                f"0x{parser_start_gba:08X}",
                f"0x{parser_end_gba:08X}",
            ],
            "range": [_offset(parser_start_gba), _offset(parser_end_gba)],
            "size": len(parser_raw),
            "raw_hex": parser_raw.hex(),
            "sha256": parser_sha256,
            "semantic_halfwords": [
                f"0x{word:04X}" for word in parser_halfwords
            ],
            "record_stride_bytes": 20,
            "terminator_field_offset": 0,
            "terminator_s16": -1,
        },
    }


def _validate_upstream(
    root: Path,
    rom: bytes,
    roots: tuple[tuple[int, int, int, int], ...],
) -> dict[str, Any]:
    manifest_raw = _read_bound(root, UPSTREAM_MANIFEST, UPSTREAM_MANIFEST_SHA256)
    verifier_raw = _read_bound(root, UPSTREAM_VERIFIER, UPSTREAM_VERIFIER_SHA256)
    manifest = json.loads(manifest_raw.decode("utf-8"))
    if manifest.get("schema") != "cutscene-obj-export-v1" or manifest.get("rom") != {"path": "rom/base.gba", "size": len(rom), "sha256": ROM_SHA256}:
        raise ValueError("upstream Cutscene OBJ export identity changed")
    if manifest.get("resource_table", {}).get("sha256") != RESOURCE_TABLE_SHA256 or manifest.get("sprite_table", {}).get("sha256") != SPRITE_TABLE_SHA256 or manifest.get("combined_table_sha256") != COMBINED_TABLE_SHA256:
        raise ValueError("upstream root table identity changed")
    if manifest.get("resource_count") != ENTRY_COUNT or manifest.get("frame_counts") != list(FRAME_COUNTS):
        raise ValueError("upstream resource denominator changed")
    resources = manifest.get("resources")
    if not isinstance(resources, list) or len(resources) != ENTRY_COUNT:
        raise ValueError("upstream resource records are incomplete")
    for resource_id, pointers in enumerate(roots):
        source = resources[resource_id]
        expected = EXPECTED_POINTERS[resource_id]
        if pointers != expected or source.get("resource_id") != resource_id or source.get("gfx_pointer") != f"0x{expected[0]:08X}" or source.get("palette_pointer") != f"0x{expected[1]:08X}" or source.get("definition_table_pointer") != f"0x{expected[2]:08X}" or source.get("animation_table_pointer") != f"0x{expected[3]:08X}" or source.get("frame_count") != FRAME_COUNTS[resource_id]:
            raise ValueError(f"upstream resource {resource_id} pointers changed")
        frames = source.get("frames")
        if not isinstance(frames, list) or len(frames) != FRAME_COUNTS[resource_id]:
            raise ValueError(f"upstream resource {resource_id} frame denominator changed")
        for frame_id, frame in enumerate(frames):
            definition_pointer = ROM_BASE + RESOURCE_ENVELOPES[resource_id][0] + frame_id * DEFINITION_RECORD_SIZE
            animation_pointer = expected[2] + FRAME_COUNTS[resource_id] * 4 + frame_id * ANIMATION_RECORD_SIZE
            definition_raw = _slice(rom, _offset(definition_pointer), _offset(definition_pointer) + DEFINITION_RECORD_SIZE)
            animation_raw = _slice(rom, _offset(animation_pointer), _offset(animation_pointer) + ANIMATION_RECORD_SIZE)
            if frame.get("frame_id") != frame_id or frame.get("definition_pointer") != f"0x{definition_pointer:08X}" or frame.get("definition_raw_hex") != definition_raw.hex() or frame.get("animation_pointer") != f"0x{animation_pointer:08X}" or frame.get("animation_raw_hex") != animation_raw.hex():
                raise ValueError(f"upstream resource {resource_id} frame {frame_id} source mismatch")
    relocation_raw = _read_bound(root, RELOCATION_MANIFEST, RELOCATION_MANIFEST_SHA256)
    relocation = json.loads(relocation_raw.decode("utf-8"))
    if relocation.get("schema") != "git-artifact-promotion-v1" or relocation.get("artifact_status") != "accepted":
        raise ValueError("upstream relocation artifact identity changed")
    _safe_dir(root, RELOCATION_DIR)
    files = relocation.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("upstream relocation file inventory missing")
    for name, expected in files.items():
        if not isinstance(name, str) or name == "manifest.json" or _sha(_safe_file(root, RELOCATION_DIR / name).read_bytes()) != expected:
            raise ValueError(f"upstream relocation member changed: {name}")
    expected_summary = {"resource_count": 4, "frame_count": 10, "component_count": 10, "animation_count": 10, "keyframe_count": 10}
    if {key: relocation.get("summary", {}).get(key) for key in expected_summary} != expected_summary:
        raise ValueError("upstream relocation summary changed")
    return {
        "cutscene_obj_export_manifest": {"path": UPSTREAM_MANIFEST.as_posix(), "schema": manifest.get("schema"), "sha256": UPSTREAM_MANIFEST_SHA256, "resource_count": manifest.get("resource_count"), "frame_counts": manifest.get("frame_counts")},
        "cutscene_obj_export_verifier": {"path": UPSTREAM_VERIFIER.as_posix(), "sha256": UPSTREAM_VERIFIER_SHA256, "size": len(verifier_raw)},
        "bundle_relocation": {"artifact_path": RELOCATION_DIR.as_posix(), "manifest_path": RELOCATION_MANIFEST.as_posix(), "manifest_sha256": RELOCATION_MANIFEST_SHA256, "files": dict(sorted(files.items())), "summary": relocation["summary"]},
    }


def _implementation(root: Path) -> dict[str, dict[str, str]]:
    paths = {
        "exporter": Path("tools/export_rom_cutscene_obj_source_ranges.py"),
        "test": Path("tests/test_export_rom_cutscene_obj_source_ranges.py"),
        "verifier": Path("tools/verify_rom_cutscene_obj_source_ranges.py"),
    }
    return {label: {"path": path.as_posix(), "sha256": _sha(_safe_file(root, path).read_bytes())} for label, path in paths.items()}


def _verify_payload_claims(
    root: Path,
    rom: bytes,
    payload: dict[str, Any],
    bundle: bytes,
) -> dict[str, Any]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("fixed ROM identity changed")

    payload_keys = {
        "files",
        "frame_counts",
        "implementation",
        "limitations",
        "records",
        "resource_count",
        "resources",
        "rom",
        "root_tables",
        "schema",
        "scope",
        "source_identity",
        "summary",
    }
    if set(payload) != payload_keys or payload.get("schema") != SCHEMA:
        raise ValueError("payload key set or schema changed")

    roots = _read_root_pairs(rom)
    upstream = _validate_upstream(root, rom, roots)
    consumer = _consumer_evidence(rom)
    expected_rom = {
        "path": ROM_PATH.as_posix(),
        "size": len(rom),
        "sha256": ROM_SHA256,
    }
    expected_root_tables = {
        "resource_table": {
            "file_offset": RESOURCE_TABLE_OFFSET,
            "gba_address": _gba(RESOURCE_TABLE_OFFSET),
            "entry_count": ENTRY_COUNT,
            "entry_size": ENTRY_SIZE,
            "sha256": RESOURCE_TABLE_SHA256,
        },
        "sprite_table": {
            "file_offset": SPRITE_TABLE_OFFSET,
            "gba_address": _gba(SPRITE_TABLE_OFFSET),
            "entry_count": ENTRY_COUNT,
            "entry_size": ENTRY_SIZE,
            "sha256": SPRITE_TABLE_SHA256,
        },
        "combined_sha256": COMBINED_TABLE_SHA256,
    }
    expected_source_identity = {
        **upstream,
        "roots": ["0x0853DF70", "0x0853DF90"],
        "consumers": consumer["addresses"],
        "consumer_evidence": consumer,
    }
    if (
        payload.get("rom") != expected_rom
        or payload.get("root_tables") != expected_root_tables
        or payload.get("source_identity") != expected_source_identity
        or payload.get("resource_count") != ENTRY_COUNT
        or payload.get("frame_counts") != list(FRAME_COUNTS)
        or payload.get("scope") != SCOPE
        or payload.get("limitations") != LIMITATIONS
        or payload.get("implementation") != _implementation(root)
    ):
        raise ValueError("payload fixed provenance changed")

    resources = payload.get("resources")
    records = payload.get("records")
    if (
        not isinstance(resources, list)
        or len(resources) != ENTRY_COUNT
        or not isinstance(records, list)
        or len(records) != 28
    ):
        raise ValueError("payload resource or record denominator changed")

    record_index = 0
    verified_ranges: list[list[int]] = []
    packed_parts: list[bytes] = []
    kind_counts = {
        "definition_record": {"range_count": 0, "byte_count": 0},
        "definition_pointer_table": {"range_count": 0, "byte_count": 0},
        "animation_timeline": {"range_count": 0, "byte_count": 0},
        "animation_pointer_table": {"range_count": 0, "byte_count": 0},
    }

    def account(record: dict[str, Any], raw: bytes) -> None:
        verified_ranges.append(record["range"])
        packed_parts.append(raw)
        counter = kind_counts[record["kind"]]
        counter["range_count"] += 1
        counter["byte_count"] += len(raw)

    for resource_id, root_pointers in enumerate(roots):
        gfx_pointer, palette_pointer, definition_table, animation_table = (
            root_pointers
        )
        frame_count = FRAME_COUNTS[resource_id]
        envelope_start, envelope_end = RESOURCE_ENVELOPES[resource_id]
        definition_offset = _offset(definition_table)
        animation_offset = _offset(animation_table)
        if animation_offset - definition_offset != frame_count * 12:
            raise ValueError(f"resource {resource_id} frame-count delta changed")

        definition_table_raw = _slice(
            rom, definition_offset, definition_offset + frame_count * 4
        )
        animation_table_raw = _slice(
            rom, animation_offset, animation_offset + frame_count * 4
        )
        definition_pointers = [
            int.from_bytes(
                definition_table_raw[index : index + 4], "little"
            )
            for index in range(0, len(definition_table_raw), 4)
        ]
        animation_pointers = [
            int.from_bytes(animation_table_raw[index : index + 4], "little")
            for index in range(0, len(animation_table_raw), 4)
        ]
        expected_definition_pointers = [
            ROM_BASE + envelope_start + frame_id * DEFINITION_RECORD_SIZE
            for frame_id in range(frame_count)
        ]
        expected_animation_pointers = [
            ROM_BASE
            + definition_offset
            + frame_count * 4
            + frame_id * ANIMATION_RECORD_SIZE
            for frame_id in range(frame_count)
        ]
        if definition_pointers != expected_definition_pointers:
            raise ValueError(
                f"resource {resource_id} definition pointer vector changed"
            )
        if animation_pointers != expected_animation_pointers:
            raise ValueError(
                f"resource {resource_id} animation pointer vector changed"
            )
        if (
            definition_pointers[0] - ROM_BASE != envelope_start
            or animation_offset + frame_count * 4 != envelope_end
        ):
            raise ValueError(f"resource {resource_id} envelope changed")

        definition_table_gba = f"0x{definition_table:08X}"
        animation_table_gba = f"0x{animation_table:08X}"
        for frame_id, pointer in enumerate(definition_pointers):
            start = _offset(pointer)
            selector = {
                "root_table": "sprite_table",
                "root_table_gba": "0x0853DF90",
                "root_entry_index": resource_id,
                "pointer_table_role": "definition",
                "pointer_table_gba": definition_table_gba,
                "pointer_slot": frame_id,
                "frame_id": frame_id,
            }
            record = records[record_index]
            raw = _assert_record_common(
                record,
                rom,
                resource_id=resource_id,
                kind="definition_record",
                start=start,
                end=start + DEFINITION_RECORD_SIZE,
                selector=selector,
                extra_keys={
                    "pointer_gba",
                    "pointer_table_gba",
                    "frame_id",
                    "component",
                    "terminator_hex",
                },
            )
            expected_extra = {
                "pointer_gba": f"0x{pointer:08X}",
                "pointer_table_gba": definition_table_gba,
                "frame_id": frame_id,
                "component": _decode_component_abi(raw, resource_id, frame_id),
                "terminator_hex": TERMINATOR.hex(),
            }
            if any(record[key] != value for key, value in expected_extra.items()):
                raise ValueError("definition record semantic fields changed")
            account(record, raw)
            record_index += 1

        definition_record = records[record_index]
        definition_selector = {
            "root_table": "sprite_table",
            "root_table_gba": "0x0853DF90",
            "root_entry_index": resource_id,
            "pointer_table_role": "definition",
            "pointer_slot_count": frame_count,
        }
        raw = _assert_record_common(
            definition_record,
            rom,
            resource_id=resource_id,
            kind="definition_pointer_table",
            start=definition_offset,
            end=definition_offset + frame_count * 4,
            selector=definition_selector,
            extra_keys={
                "pointer_gba",
                "pointer_vector",
                "pointer_vector_sha256",
                "entry_size",
            },
        )
        definition_extra = {
            "pointer_gba": definition_table_gba,
            "pointer_vector": [
                f"0x{pointer:08X}" for pointer in definition_pointers
            ],
            "pointer_vector_sha256": _vector_sha(definition_pointers),
            "entry_size": 4,
        }
        if any(
            definition_record[key] != value
            for key, value in definition_extra.items()
        ):
            raise ValueError("definition pointer-table claim changed")
        account(definition_record, raw)
        record_index += 1

        for frame_id, pointer in enumerate(animation_pointers):
            start = _offset(pointer)
            selector = {
                "root_table": "sprite_table",
                "root_table_gba": "0x0853DF90",
                "root_entry_index": resource_id,
                "pointer_table_role": "animation",
                "pointer_table_gba": animation_table_gba,
                "pointer_slot": frame_id,
                "frame_id": frame_id,
            }
            record = records[record_index]
            raw = _assert_record_common(
                record,
                rom,
                resource_id=resource_id,
                kind="animation_timeline",
                start=start,
                end=start + ANIMATION_RECORD_SIZE,
                selector=selector,
                extra_keys={
                    "pointer_gba",
                    "pointer_table_gba",
                    "frame_id",
                    "duration",
                    "terminator_hex",
                },
            )
            frame_value, duration = _decode_animation_claim(
                raw, resource_id, frame_id
            )
            animation_extra = {
                "pointer_gba": f"0x{pointer:08X}",
                "pointer_table_gba": animation_table_gba,
                "frame_id": frame_value,
                "duration": duration,
                "terminator_hex": TERMINATOR.hex(),
            }
            if any(
                record[key] != value for key, value in animation_extra.items()
            ):
                raise ValueError("animation record semantic fields changed")
            account(record, raw)
            record_index += 1

        animation_record = records[record_index]
        animation_selector = {
            "root_table": "sprite_table",
            "root_table_gba": "0x0853DF90",
            "root_entry_index": resource_id,
            "pointer_table_role": "animation",
            "pointer_slot_count": frame_count,
        }
        raw = _assert_record_common(
            animation_record,
            rom,
            resource_id=resource_id,
            kind="animation_pointer_table",
            start=animation_offset,
            end=animation_offset + frame_count * 4,
            selector=animation_selector,
            extra_keys={
                "pointer_gba",
                "pointer_vector",
                "pointer_vector_sha256",
                "entry_size",
            },
        )
        animation_extra = {
            "pointer_gba": animation_table_gba,
            "pointer_vector": [
                f"0x{pointer:08X}" for pointer in animation_pointers
            ],
            "pointer_vector_sha256": _vector_sha(animation_pointers),
            "entry_size": 4,
        }
        if any(
            animation_record[key] != value
            for key, value in animation_extra.items()
        ):
            raise ValueError("animation pointer-table claim changed")
        account(animation_record, raw)
        record_index += 1

        expected_resource = {
            "resource_id": resource_id,
            "resource_pair_file_offset": RESOURCE_TABLE_OFFSET
            + resource_id * ENTRY_SIZE,
            "sprite_pair_file_offset": SPRITE_TABLE_OFFSET
            + resource_id * ENTRY_SIZE,
            "gfx_pointer": f"0x{gfx_pointer:08X}",
            "palette_pointer": f"0x{palette_pointer:08X}",
            "definition_table_pointer": definition_table_gba,
            "animation_table_pointer": animation_table_gba,
            "frame_count": frame_count,
            "envelope": {
                "range": [envelope_start, envelope_end],
                "gba_range": [_gba(envelope_start), _gba(envelope_end)],
                "size": envelope_end - envelope_start,
                "sha256": _sha(_slice(rom, envelope_start, envelope_end)),
            },
            "definition_pointer_vector": [
                f"0x{pointer:08X}" for pointer in definition_pointers
            ],
            "animation_pointer_vector": [
                f"0x{pointer:08X}" for pointer in animation_pointers
            ],
            "definition_pointer_table_raw_hex": definition_table_raw.hex(),
            "animation_pointer_table_raw_hex": animation_table_raw.hex(),
            "definition_pointer_table_sha256": _sha(definition_table_raw),
            "animation_pointer_table_sha256": _sha(animation_table_raw),
            "source_selector": {
                "resource_id": resource_id,
                "resource_table_root": "0x0853DF70",
                "sprite_table_root": "0x0853DF90",
                "resource_pair_file_offset": RESOURCE_TABLE_OFFSET
                + resource_id * ENTRY_SIZE,
                "sprite_pair_file_offset": SPRITE_TABLE_OFFSET
                + resource_id * ENTRY_SIZE,
            },
        }
        if resources[resource_id] != expected_resource:
            raise ValueError(f"resource {resource_id} payload record changed")

    if record_index != len(records):
        raise ValueError("unverified source records remain")
    if verified_ranges != sorted(verified_ranges):
        raise ValueError("source range order changed")
    if any(
        previous[1] > current[0]
        for previous, current in zip(verified_ranges, verified_ranges[1:])
    ):
        raise ValueError("source ranges overlap")
    rebuilt_bundle = b"".join(packed_parts)
    if bundle != rebuilt_bundle:
        raise ValueError("bundle does not match independently verified ROM slices")

    expected_summary = {
        "range_count": 28,
        "byte_count": 400,
        "kind_counts": kind_counts,
        "resource_envelope_count": len(RESOURCE_ENVELOPES),
        "resource_envelope_bytes": sum(
            end - start for start, end in RESOURCE_ENVELOPES
        ),
        "resource_envelopes": [
            [start, end] for start, end in RESOURCE_ENVELOPES
        ],
        "range_vector_sha256": _vector_sha(verified_ranges),
        "bundle_sha256": _sha(bundle),
    }
    if payload.get("summary") != expected_summary:
        raise ValueError("payload summary changed")
    if payload.get("files") != {
        BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bundle)}
    }:
        raise ValueError("payload bundle identity changed")
    return _expected_report(payload, bundle)


def verify_payload_from_rom(
    root: Path | str,
    rom: bytes,
    payload: dict[str, Any],
    bundle: bytes,
) -> dict[str, Any]:
    return _verify_payload_claims(
        Path(root).resolve(strict=True), rom, payload, bundle
    )


def _expected_report(payload: dict[str, Any], bundle: bytes) -> dict[str, Any]:
    return {"schema": VERIFY_SCHEMA, "artifact_schema": SCHEMA, "verified": True, "errors": [], "range_count": payload["summary"]["range_count"], "byte_count": payload["summary"]["byte_count"], "bundle_sha256": _sha(bundle), "range_vector_sha256": payload["summary"]["range_vector_sha256"]}


def _manifest_expected(payload: dict[str, Any], files: dict[str, bytes], report: dict[str, Any] | None, status: str) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA, "artifact_status": status,
        "files": {name: _sha(content) for name, content in sorted(files.items())},
        "producer": {"command": PRODUCER_COMMAND, **payload["implementation"]},
        "verifier": {"schema": VERIFY_SCHEMA, "command": VERIFIER_COMMAND, "exit_code": 0 if report is not None else None, "report": report, "verifier_sha256": payload["implementation"]["verifier"]["sha256"]},
        "rom": payload["rom"], "source_identity": payload["source_identity"], "scope": payload["scope"], "limitations": payload["limitations"],
    }


def _artifact_path(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("artifact path uses a symlink")
        if not cursor.exists():
            break
    return requested.resolve(strict=True)


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
    if _canonical(manifest) != manifest_raw or set(manifest) != MANIFEST_KEYS:
        raise ValueError("manifest is not canonical or key set changed")
    if manifest.get("schema") != "git-artifact-promotion-v1" or manifest.get("artifact_schema") != SCHEMA or manifest.get("artifact_status") not in {"candidate", "accepted"}:
        raise ValueError("artifact manifest identity mismatch")
    payload_path = artifact / PAYLOAD_NAME
    payload_raw = payload_path.read_bytes()
    payload = json.loads(payload_raw.decode("utf-8"))
    if _canonical(payload) != payload_raw or payload.get("schema") != SCHEMA:
        raise ValueError("payload is not canonical or schema changed")
    bundle = (artifact / BUNDLE_NAME).read_bytes()
    if manifest.get("files") != {PAYLOAD_NAME: _sha(payload_raw), BUNDLE_NAME: _sha(bundle)}:
        raise ValueError("artifact file hashes mismatch")
    report = _verify_payload_claims(
        root, _safe_file(root, ROM_PATH).read_bytes(), payload, bundle
    )
    implementation = payload["implementation"]
    if manifest.get("producer") != {"command": PRODUCER_COMMAND, **implementation}:
        raise ValueError("manifest producer identity mismatch")
    if manifest.get("rom") != payload["rom"] or manifest.get("source_identity") != payload["source_identity"] or manifest.get("scope") != payload["scope"] or manifest.get("limitations") != payload["limitations"]:
        raise ValueError("manifest provenance mismatch")
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
        report = _verify(root, _artifact_path(artifact))
        return report
    except (KeyError, OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError, struct.error) as error:
        return {"schema": VERIFY_SCHEMA, "artifact_schema": SCHEMA, "verified": False, "errors": [str(error)], "range_count": 0, "byte_count": 0, "bundle_sha256": None, "range_vector_sha256": None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report.get("verified") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
