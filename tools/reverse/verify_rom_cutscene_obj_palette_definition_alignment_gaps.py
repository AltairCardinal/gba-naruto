#!/usr/bin/env python3
"""Verify four fixed Cutscene OBJ palette-to-definition alignment gaps."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


VERIFY_SCHEMA = "rom-cutscene-obj-palette-definition-alignment-gaps-verification-v1"
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

RANGE_VECTOR = (
    (0x12DEFA, 0x12DEFC),
    (0x12E442, 0x12E444),
    (0x12E95E, 0x12E960),
    (0x12ED6E, 0x12ED70),
)
RANGE_VECTOR_SHA256 = "374c247199713cc2e172ebff551ae7a5e40df4289437f45cf76c814e84bed5e6"
BOUNDARY_VECTOR_SHA256 = "779dae0d0811b3cde7817d9de9c0c61c35e7d9c54e5d2f9ecfd99eb0a80b211d"
PACKED_BYTES_SHA256 = "af5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc"

EXPECTED_ROOT_ROWS = (
    (0x0812D9E4, 0x0812DEE4, 0x0812DF2C, 0x0812DF44),
    (0x0812DF4C, 0x0812E42C, 0x0812E474, 0x0812E48C),
    (0x0812E494, 0x0812E948, 0x0812E990, 0x0812E9A8),
    (0x0812E9B0, 0x0812ED58, 0x0812EDD0, 0x0812EE00),
)
ROOT_ROW_VECTOR_SHA256 = "8a0ab99bbb46e1fa58a0413ffae366bd67a3660e5f947b043228858688899e2d"
EXPECTED_FIRST_DEFINITION_POINTERS = (0x0812DEFC, 0x0812E444, 0x0812E960, 0x0812ED70)

PALETTE_COMPRESSED_SIZE = 22
PALETTE_DECODED_SIZE = 32
COMPRESSED_STREAM_SHA256 = "6bdf4b41b3d1b6240499cb68ceddb82a6e98267709f05d075bc64389956681c2"
DECODED_STREAM_SHA256 = "99d45ddc5929d60c150146f1292cd55f56d89afbff70ffd0f377128fe75352af"
ZERO_GAP_SHA256 = "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7"

COMPONENT_STRIDE_BYTES = 20
DEFINITION_RECORD_SIZE = 24
TERMINATOR = bytes.fromhex("ffff0000")
DEFINITION_RECORD_SHA256 = (
    "eb8f1ba7cc2d225bf3a2adefd015873a9bf311e4d1b1e080328f3c9187852ed1",
    "eb8f1ba7cc2d225bf3a2adefd015873a9bf311e4d1b1e080328f3c9187852ed1",
    "eb8f1ba7cc2d225bf3a2adefd015873a9bf311e4d1b1e080328f3c9187852ed1",
    "a3f6935912109790d1ddaa4b1496984c0eba79325a6b250057dfe5bb2eeb05ce",
)
EXPECTED_FIRST_DEFINITION_RAW = (
    bytes.fromhex("00000000e0ffe0ff4000400000010001ff000000ffff0000"),
    bytes.fromhex("00000000e0ffe0ff4000400000010001ff000000ffff0000"),
    bytes.fromhex("00000000e0ffe0ff4000400000010001ff000000ffff0000"),
    bytes.fromhex("00000000f0fff0ff2000200000010001ff000000ffff0000"),
)

NON_CLAIM_KEYS = (
    "allocatable_space_claimed",
    "free_space_claimed",
    "editing_safety_claimed",
    "writeback_or_relocation_safety_claimed",
    "runtime_consumes_padding_claimed",
    "natural_runtime_reachability_claimed",
    "final_pixel_equivalence_claimed",
    "definition_unknown_field_semantics_claimed",
    "graphics_or_palette_expansion_claimed",
    "all_cutscene_gaps_exhaustive_claimed",
    "generic_lz_alignment_rule_claimed",
    "lz_trailing_bytes_claimed",
    "compiler_authorship_claimed",
)
NON_CLAIMS = {key: False for key in NON_CLAIM_KEYS}
LIMITATIONS = [
    "Only four fixed palette-to-first-definition ranges are classified.",
    "The result does not claim free, allocatable, reserved, editable, or relocatable space.",
    "The result does not claim natural runtime reachability, final pixel equivalence, or complete Cutscene coverage.",
    "The LZ parser proves these four stream endpoints only; no generic alignment rule or trailing-byte meaning is claimed.",
    "Definition component field semantics and compiler authorship remain outside scope.",
]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _vector_sha(value: Any) -> str:
    return _sha(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _slice(rom: bytes, start: int, end: int, label: str) -> bytes:
    if start < 0 or end < start or end > len(rom):
        raise ValueError(f"{label} range is outside the ROM")
    return rom[start:end]


def _safe_root(root: Path) -> Path:
    path = Path(root)
    if path.is_symlink():
        raise ValueError("repository root is a symlink")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ValueError("repository root is missing") from error
    if not resolved.is_dir():
        raise ValueError("repository root is not a directory")
    for marker in (Path("tools"), Path("tests"), Path("rom")):
        candidate = resolved / marker
        if not candidate.is_dir() or candidate.is_symlink():
            raise ValueError("repository root is outside the expected project tree")
    return resolved


def _safe_rom_path(root: Path) -> Path:
    cursor = root
    for part in ROM_PATH.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("ROM input uses a symlink")
    try:
        resolved = cursor.resolve(strict=True)
    except OSError as error:
        raise ValueError("ROM input is missing") from error
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("ROM input escapes repository root") from error
    if not resolved.is_file():
        raise ValueError("ROM input is not a file")
    return resolved


def _pointer_offset(pointer: int, label: str, rom: bytes) -> int:
    if pointer < ROM_BASE or pointer >= ROM_BASE + len(rom):
        raise ValueError(f"{label} pointer is outside the ROM")
    if pointer & 3:
        raise ValueError(f"{label} pointer is not 4-byte aligned")
    return pointer - ROM_BASE


def _read_u32(rom: bytes, offset: int, label: str) -> int:
    raw = _slice(rom, offset, offset + 4, label)
    return int.from_bytes(raw, "little")


def _parse_type10(rom: bytes, start: int) -> tuple[bytes, int]:
    """Parse one strict GBA type-0x10 stream and return bytes plus endpoint."""

    header = _slice(rom, start, start + 4, "LZ header")
    if header[0] != 0x10:
        raise ValueError("LZ stream has the wrong type-0x10 header")
    declared_size = int.from_bytes(header[1:4], "little")
    if declared_size <= 0:
        raise ValueError("LZ stream declares an empty output")

    cursor = start + 4
    output = bytearray()
    flags = 0
    flags_left = 0
    while len(output) < declared_size:
        if flags_left == 0:
            if cursor >= len(rom):
                raise ValueError("LZ stream flags are truncated")
            flags = rom[cursor]
            cursor += 1
            flags_left = 8
        compressed = bool(flags & 0x80)
        flags = (flags << 1) & 0xFF
        flags_left -= 1
        if compressed:
            token = _slice(rom, cursor, cursor + 2, "LZ back-reference token")
            cursor += 2
            length = (token[0] >> 4) + 3
            distance = (((token[0] & 0x0F) << 8) | token[1]) + 1
            if distance > len(output):
                raise ValueError("LZ stream contains an illegal back-reference")
            if len(output) + length > declared_size:
                raise ValueError("LZ stream output overruns its declared size")
            for _ in range(length):
                output.append(output[-distance])
        else:
            literal = _slice(rom, cursor, cursor + 1, "LZ literal")
            cursor += 1
            output.extend(literal)
    if len(output) != declared_size:
        raise ValueError("LZ stream did not produce its declared size")
    return bytes(output), cursor


def _validate_fixed_constants() -> None:
    if len(RANGE_VECTOR) != ENTRY_COUNT or any(len(pair) != 2 for pair in RANGE_VECTOR):
        raise ValueError("gap denominator changed")
    if _vector_sha([list(pair) for pair in RANGE_VECTOR]) != RANGE_VECTOR_SHA256:
        raise ValueError("range vector hash changed")
    if set(NON_CLAIMS) != set(NON_CLAIM_KEYS) or any(
        value is not False for value in NON_CLAIMS.values()
    ):
        raise ValueError("non-claim contract changed")
    if COMPONENT_STRIDE_BYTES != 20 or DEFINITION_RECORD_SIZE != 24:
        raise ValueError("definition component stride or record size changed")
    if len(EXPECTED_ROOT_ROWS) != ENTRY_COUNT or len(EXPECTED_FIRST_DEFINITION_POINTERS) != ENTRY_COUNT:
        raise ValueError("root pointer denominator changed")
    if len(DEFINITION_RECORD_SHA256) != ENTRY_COUNT or len(EXPECTED_FIRST_DEFINITION_RAW) != ENTRY_COUNT:
        raise ValueError("definition record denominator changed")


def _read_root_tables(rom: bytes) -> tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...], str, str, str]:
    resource_raw = _slice(
        rom, RESOURCE_TABLE_OFFSET, RESOURCE_TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE, "resource root table"
    )
    sprite_raw = _slice(
        rom, SPRITE_TABLE_OFFSET, SPRITE_TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE, "sprite root table"
    )
    resource_sha = _sha(resource_raw)
    sprite_sha = _sha(sprite_raw)
    combined_sha = _sha(resource_raw + sprite_raw)
    if resource_sha != RESOURCE_TABLE_SHA256:
        raise ValueError("resource root table hash changed")
    if sprite_sha != SPRITE_TABLE_SHA256:
        raise ValueError("sprite root table hash changed")
    if combined_sha != COMBINED_TABLE_SHA256:
        raise ValueError("combined root table hash changed")
    resources = tuple(
        (
            int.from_bytes(resource_raw[index : index + 4], "little"),
            int.from_bytes(resource_raw[index + 4 : index + 8], "little"),
        )
        for index in range(0, len(resource_raw), ENTRY_SIZE)
    )
    sprites = tuple(
        (
            int.from_bytes(sprite_raw[index : index + 4], "little"),
            int.from_bytes(sprite_raw[index + 4 : index + 8], "little"),
        )
        for index in range(0, len(sprite_raw), ENTRY_SIZE)
    )
    return resources, sprites, resource_sha, sprite_sha, combined_sha


def _verify_bytes(rom: bytes) -> dict[str, Any]:
    _validate_fixed_constants()
    if len(rom) != ROM_SIZE:
        raise ValueError("ROM size changed")
    if _sha(rom) != ROM_SHA256:
        raise ValueError("ROM SHA-256 changed")

    resource_rows, sprite_rows, resource_sha, sprite_sha, combined_sha = _read_root_tables(rom)
    if len(resource_rows) != ENTRY_COUNT or len(sprite_rows) != ENTRY_COUNT:
        raise ValueError("root table denominator changed")

    resources: list[dict[str, Any]] = []
    root_row_vector: list[list[int]] = []
    boundary_vector: list[list[int]] = []
    packed_gaps: list[bytes] = []

    for resource_id, (resource_row, sprite_row) in enumerate(zip(resource_rows, sprite_rows, strict=True)):
        root_values = resource_row + sprite_row
        if root_values != EXPECTED_ROOT_ROWS[resource_id]:
            raise ValueError(f"resource {resource_id} root pointer vector changed")
        gfx_pointer, palette_pointer = resource_row
        definition_table_pointer, animation_table_pointer = sprite_row
        gfx_offset = _pointer_offset(gfx_pointer, f"resource {resource_id} graphics", rom)
        palette_offset = _pointer_offset(palette_pointer, f"resource {resource_id} palette", rom)
        definition_table_offset = _pointer_offset(
            definition_table_pointer, f"resource {resource_id} definition table", rom
        )
        animation_table_offset = _pointer_offset(
            animation_table_pointer, f"resource {resource_id} animation table", rom
        )
        del gfx_offset

        decoded, parser_end = _parse_type10(rom, palette_offset)
        compressed_raw = _slice(rom, palette_offset, parser_end, f"resource {resource_id} compressed palette")
        if len(compressed_raw) != PALETTE_COMPRESSED_SIZE:
            raise ValueError(f"resource {resource_id} LZ parser endpoint is not exact")
        if _sha(compressed_raw) != COMPRESSED_STREAM_SHA256:
            raise ValueError(f"resource {resource_id} compressed palette bytes changed")
        if len(decoded) != PALETTE_DECODED_SIZE:
            raise ValueError(f"resource {resource_id} decoded palette size changed")
        if _sha(decoded) != DECODED_STREAM_SHA256:
            raise ValueError(f"resource {resource_id} decoded palette bytes changed")

        expected_gap_start, expected_gap_end = RANGE_VECTOR[resource_id]
        if parser_end != expected_gap_start:
            raise ValueError(f"resource {resource_id} LZ parser endpoint changed")
        gap_start = parser_end
        gap_end = (parser_end + 3) & ~3
        if (gap_start, gap_end) != (expected_gap_start, expected_gap_end):
            raise ValueError(f"resource {resource_id} alignment equation changed")
        gap_raw = _slice(rom, gap_start, gap_end, f"resource {resource_id} alignment gap")
        if gap_raw != b"\x00\x00":
            raise ValueError(f"resource {resource_id} alignment gap is not two zero bytes")
        if _sha(gap_raw) != ZERO_GAP_SHA256:
            raise ValueError(f"resource {resource_id} alignment gap hash changed")
        packed_gaps.append(gap_raw)

        first_definition_pointer = _read_u32(
            rom, definition_table_offset, f"resource {resource_id} definition slot 0"
        )
        first_definition_offset = _pointer_offset(
            first_definition_pointer, f"resource {resource_id} definition slot 0", rom
        )
        if first_definition_offset != gap_end:
            raise ValueError(
                f"resource {resource_id} definition slot 0 is not the aligned LZ endpoint"
            )
        first_definition_raw = _slice(
            rom,
            first_definition_offset,
            first_definition_offset + DEFINITION_RECORD_SIZE,
            f"resource {resource_id} first definition record",
        )
        if len(first_definition_raw) != DEFINITION_RECORD_SIZE:
            raise ValueError(f"resource {resource_id} definition record size changed")
        if COMPONENT_STRIDE_BYTES != 20:
            raise ValueError(f"resource {resource_id} definition component stride changed")
        terminator = first_definition_raw[COMPONENT_STRIDE_BYTES:]
        if terminator != TERMINATOR:
            raise ValueError(f"resource {resource_id} definition terminator changed")
        if _sha(first_definition_raw) != DEFINITION_RECORD_SHA256[resource_id]:
            raise ValueError(f"resource {resource_id} first definition record bytes changed")
        if first_definition_raw != EXPECTED_FIRST_DEFINITION_RAW[resource_id]:
            raise ValueError(f"resource {resource_id} first definition record identity changed")

        if (animation_table_offset - definition_table_offset) % 12:
            raise ValueError(f"resource {resource_id} frame-count corroboration changed")
        frame_count = (animation_table_offset - definition_table_offset) // 12
        root_row = list(root_values) + [first_definition_pointer]
        root_row_vector.append([resource_id, *root_row])
        boundary_vector.append(
            [
                resource_id,
                palette_offset,
                parser_end,
                gap_start,
                gap_end,
                first_definition_offset,
                first_definition_offset + DEFINITION_RECORD_SIZE,
            ]
        )

        record: dict[str, Any] = {
            "resource_id": resource_id,
            "root": {
                "resource_row": list(resource_row),
                "sprite_row": list(sprite_row),
                "graphics_pointer": gfx_pointer,
                "palette_pointer": palette_pointer,
                "definition_table_pointer": definition_table_pointer,
                "animation_table_pointer": animation_table_pointer,
                "first_definition_pointer": first_definition_pointer,
            },
            "graphics_pointer": _gba(gfx_pointer - ROM_BASE),
            "palette_pointer": _gba(palette_offset),
            "definition_table_pointer": _gba(definition_table_offset),
            "animation_table_pointer": _gba(animation_table_offset),
            "first_definition_pointer": _gba(first_definition_offset),
            "frame_count_corroboration": frame_count,
            "palette_compressed_range": [palette_offset, parser_end],
            "palette_compressed_gba_range": [_gba(palette_offset), _gba(parser_end)],
            "palette_compressed_size": len(compressed_raw),
            "palette_compressed_sha256": _sha(compressed_raw),
            "palette_decoded_size": len(decoded),
            "palette_decoded_sha256": _sha(decoded),
            "parser_end": parser_end,
            "parser_end_gba": _gba(parser_end),
            "gap_start": gap_start,
            "gap_end": gap_end,
            "gap_range": [gap_start, gap_end],
            "gap_gba_range": [_gba(gap_start), _gba(gap_end)],
            "gap_size": len(gap_raw),
            "gap_raw_hex": gap_raw.hex(),
            "gap_sha256": _sha(gap_raw),
            "gap_start_equals_parser_end": gap_start == parser_end,
            "gap_end_equals_aligned_parser_end": gap_end == ((parser_end + 3) & ~3),
            "first_definition_range": [first_definition_offset, first_definition_offset + DEFINITION_RECORD_SIZE],
            "first_definition_gba_range": [
                _gba(first_definition_offset),
                _gba(first_definition_offset + DEFINITION_RECORD_SIZE),
            ],
            "first_definition_size": len(first_definition_raw),
            "first_definition_raw_hex": first_definition_raw.hex(),
            "first_definition_sha256": _sha(first_definition_raw),
            "first_definition_component_size": COMPONENT_STRIDE_BYTES,
            "component_stride_bytes": COMPONENT_STRIDE_BYTES,
            "first_definition_terminator_hex": terminator.hex(),
            "first_definition_terminator_exact": terminator == TERMINATOR,
            "slot_0_equals_aligned_parser_end": first_definition_offset == gap_end,
        }
        record.update(NON_CLAIMS)
        resources.append(record)

    if _vector_sha(root_row_vector) != ROOT_ROW_VECTOR_SHA256:
        raise ValueError("root-row vector hash changed")
    if _vector_sha(boundary_vector) != BOUNDARY_VECTOR_SHA256:
        raise ValueError("boundary vector hash changed")
    packed = b"".join(packed_gaps)
    if len(packed) != 8 or packed.count(0) != 8 or _sha(packed) != PACKED_BYTES_SHA256:
        raise ValueError("packed gap denominator or hash changed")

    report: dict[str, Any] = {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        "errors": [],
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": _sha(rom)},
        "gap_count": len(RANGE_VECTOR),
        "byte_count": len(packed),
        "zero_byte_count": packed.count(0),
        "left_lz_count": len(resources),
        "right_definition_count": len(resources),
        "ranges": [list(pair) for pair in RANGE_VECTOR],
        "range_vector_sha256": _vector_sha([list(pair) for pair in RANGE_VECTOR]),
        "boundary_vector": boundary_vector,
        "boundary_vector_sha256": _vector_sha(boundary_vector),
        "root_row_vector": root_row_vector,
        "root_row_vector_sha256": _vector_sha(root_row_vector),
        "packed_bytes_hex": packed.hex(),
        "packed_bytes_sha256": _sha(packed),
        "resource_table_sha256": resource_sha,
        "sprite_table_sha256": sprite_sha,
        "combined_table_sha256": combined_sha,
        "compressed_stream_sha256": COMPRESSED_STREAM_SHA256,
        "decoded_stream_sha256": DECODED_STREAM_SHA256,
        "all_parser_endpoints_exact": all(
            row["parser_end"] == row["gap_range"][0] and row["palette_compressed_size"] == PALETTE_COMPRESSED_SIZE
            for row in resources
        ),
        "all_alignment_equations_hold": all(
            row["gap_start_equals_parser_end"]
            and row["gap_end_equals_aligned_parser_end"]
            and row["slot_0_equals_aligned_parser_end"]
            for row in resources
        ),
        "resources": resources,
        "limitations": list(LIMITATIONS),
        "non_claims": dict(NON_CLAIMS),
    }
    report.update(NON_CLAIMS)
    return report


def _failure(errors: list[str]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": VERIFY_SCHEMA,
        "verified": False,
        "errors": [error or "verification failed" for error in errors],
        "limitations": list(LIMITATIONS),
        "non_claims": dict(NON_CLAIMS),
    }
    report.update(NON_CLAIMS)
    return report


def verify_rom_bytes(rom: bytes) -> dict[str, Any]:
    """Verify already-loaded ROM bytes and always return a JSON-compatible report."""

    try:
        return _verify_bytes(bytes(rom))
    except (TypeError, ValueError, IndexError, OSError) as error:
        return _failure([str(error)])


def verify_root(root: Path | str) -> dict[str, Any]:
    """Safely load ``rom/base.gba`` under *root* and verify it."""

    try:
        resolved_root = _safe_root(Path(root))
        rom_path = _safe_rom_path(resolved_root)
        return verify_rom_bytes(rom_path.read_bytes())
    except (TypeError, ValueError, OSError) as error:
        return _failure([str(error)])


def verify(root: Path | str) -> dict[str, Any]:
    """Public alias for repository-root verification."""

    return verify_root(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args(argv)
    report = verify_root(args.root)
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
