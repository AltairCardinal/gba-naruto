#!/usr/bin/env python3
"""Independently verify both localized base-ROM dialogue glyph branches."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any, Iterable

from PIL import Image


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SJIS_TABLE_OFFSET = 0x53D644
SJIS_ENTRY_COUNT = 26
SJIS_ENTRY_SIZE = 8
SJIS_SOURCE_BYTES = 32
SJIS_TABLE_SHA256 = (
    "6c396ab55b0cbeacb4d2d2d8df55666ab79fcfa426377ef91d03ab7743a7b18d"
)
BYTE_TABLE_OFFSET = 0x53D73C
BYTE_ENTRY_COUNT = 2
BYTE_ENTRY_SIZE = 8
BYTE_SOURCE_BYTES = 16
BYTE_TABLE_SHA256 = (
    "f6d1d6950f29cf0cb2e03e3d365ac5cc8faaafd2336c12c8ab28673602873b90"
)
MAPPING_PATH = Path("sequel/content/text/sjis-to-tile-addr-20260703.json")
MAPPING_SHA256 = (
    "3a8b8bb998028d93cdbd0905dd929efb96e1d9643720cbd36b817daf31db7e6f"
)
LOCALIZED_MAPPING_PATH = Path(
    "sequel/content/text/sjis-to-tile-mapping.json"
)
LOCALIZED_MAPPING_SHA256 = (
    "174dcb43915385fe0eab3e63a0671bc07edfd984c5d31f78c390f617c004a43d"
)
GROUP0_STREAM_OFFSET = 0x459414
GROUP0_STREAM_SIZE = 41
GROUP0_STREAM_SHA256 = (
    "dc998ad097f02104c488a3d380a17b37ad02b89cba5491b49ed444d55dab2370"
)
HALF_TILE_SOURCE_BYTES = 16
ATLAS_WIDTH_LIMIT = 256
EXPECTED_BGR555_HEX = "00004a29b556ff7f"
EXPECTED_RGB_PALETTE = [
    [0, 0, 0],
    [82, 82, 82],
    [173, 173, 173],
    [255, 255, 255],
]
EXPECTED_CODE_SLICES = (
    {
        "name": "sjis_lookup_and_expansion",
        "file_offset": 0x065E80,
        "gba_address": "0x08065E80",
        "size": 0x104,
        "sha256": "34af9f508d11604b363881ce01ec4dd29cedd6a545ad075481ab5f854f555626",
    },
    {
        "name": "sjis_two_tile_outer",
        "file_offset": 0x065F84,
        "gba_address": "0x08065F84",
        "size": 0xB0,
        "sha256": "7e4316e63cbb44d09b26c7cc6592c580b83af0b328098c67669db1b05d1c784c",
    },
    {
        "name": "byte_lookup_and_expansion",
        "file_offset": 0x06606C,
        "gba_address": "0x0806606C",
        "size": 0xD6,
        "sha256": "44442bbfae35bd6e11814fca10a3de9bf3fa9cfcb816a74fa4750cba9b4de168",
    },
    {
        "name": "renderer_dual_branch",
        "file_offset": 0x08942C,
        "gba_address": "0x0808942C",
        "size": 0xB8,
        "sha256": "399a65ef6891c7c81acf42a52a8da2ee824bb80c77dcbd73f7a536845489e391",
    },
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pointer(value: int) -> str:
    return f"0x{value:08X}"


def _source_raw(rom: bytes, pointer: int, size: int) -> bytes:
    offset = pointer - ROM_BASE
    if not 0 <= offset <= len(rom) - size:
        raise ValueError(f"source pointer {_pointer(pointer)} is outside the ROM")
    return rom[offset : offset + size]


def _histogram(source: bytes) -> list[int]:
    histogram = [0] * 4
    for packed in source:
        for shift in (0, 2, 4, 6):
            histogram[(packed >> shift) & 3] += 1
    return histogram


def _used(histogram: list[int]) -> list[int]:
    return [index for index, count in enumerate(histogram) if count]


def _expand(source: bytes, palette_group: int) -> bytes:
    base = palette_group << 2
    output = bytearray()
    for packed in source:
        values = [base | ((packed >> shift) & 3) for shift in (0, 2, 4, 6)]
        output.extend(
            (
                values[0] | (values[1] << 4),
                values[2] | (values[3] << 4),
            )
        )
    return bytes(output)


def _decode_record(source: bytes, width: int, height: int) -> bytes:
    if len(source) * 4 != width * height:
        raise ValueError("source record geometry is inconsistent")
    if height != 8 or width % 8:
        raise ValueError("source geometry is not a horizontal 8x8 tile row")
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            tile_index = x // 8
            pixel_in_tile = y * 8 + x % 8
            packed = source[tile_index * 16 + pixel_in_tile // 4]
            pixels.append((packed >> ((pixel_in_tile % 4) * 2)) & 3)
    return bytes(pixels)


def _decode_atlas(
    source: bytes,
    *,
    item_count: int,
    item_width: int,
    item_height: int,
    source_bytes_per_item: int,
) -> tuple[bytes, int, int]:
    if len(source) != item_count * source_bytes_per_item:
        raise ValueError("source atlas item count is inconsistent")
    per_row = max(1, ATLAS_WIDTH_LIMIT // item_width)
    columns = min(item_count, per_row)
    rows = (item_count + per_row - 1) // per_row
    width = columns * item_width
    height = rows * item_height
    pixels = bytearray(width * height)
    for item_index in range(item_count):
        item_x = (item_index % per_row) * item_width
        item_y = (item_index // per_row) * item_height
        start = item_index * source_bytes_per_item
        item = _decode_record(
            source[start : start + source_bytes_per_item],
            item_width,
            item_height,
        )
        for row in range(item_height):
            destination = (item_y + row) * width + item_x
            source_row = row * item_width
            pixels[destination : destination + item_width] = item[
                source_row : source_row + item_width
            ]
    return bytes(pixels), width, height


def _parse_sjis(
    rom: bytes,
) -> tuple[list[dict[str, Any]], list[tuple[int, int, int]]]:
    entries = []
    records = []
    for index in range(SJIS_ENTRY_COUNT):
        table_offset = SJIS_TABLE_OFFSET + index * SJIS_ENTRY_SIZE
        lower, range_size, aux_byte, pointer = struct.unpack_from(
            "<HBBI",
            rom,
            table_offset,
        )
        end = pointer + range_size * SJIS_SOURCE_BYTES
        raw = _source_raw(rom, pointer, range_size * SJIS_SOURCE_BYTES)
        entries.append(
            {
                "index": index,
                "table_file_offset": table_offset,
                "lower": lower,
                "lower_hex": f"0x{lower:04X}",
                "range_size": range_size,
                "exclusive_upper": lower + range_size,
                "exclusive_upper_hex": f"0x{lower + range_size:04X}",
                "aux_byte": aux_byte,
                "source_pointer": _pointer(pointer),
                "source_end_pointer": _pointer(end),
                "source_data_size": len(raw),
                "source_data_sha256": _sha256(raw),
                "raw_hex": rom[
                    table_offset : table_offset + SJIS_ENTRY_SIZE
                ].hex(),
            }
        )
        records.extend(
            (
                index,
                lower + relative,
                pointer + relative * SJIS_SOURCE_BYTES,
            )
            for relative in range(range_size)
        )
    return entries, records


def _parse_byte(
    rom: bytes,
) -> tuple[list[dict[str, Any]], list[tuple[int, int, int]]]:
    entries = []
    records = []
    for index in range(BYTE_ENTRY_COUNT):
        table_offset = BYTE_TABLE_OFFSET + index * BYTE_ENTRY_SIZE
        lower, range_size, aux_halfword, pointer = struct.unpack_from(
            "<BBHI",
            rom,
            table_offset,
        )
        end = pointer + range_size * BYTE_SOURCE_BYTES
        raw = _source_raw(rom, pointer, range_size * BYTE_SOURCE_BYTES)
        entries.append(
            {
                "index": index,
                "table_file_offset": table_offset,
                "lower": lower,
                "lower_hex": f"0x{lower:02X}",
                "range_size": range_size,
                "exclusive_upper": lower + range_size,
                "exclusive_upper_hex": f"0x{lower + range_size:03X}",
                "aux_halfword": aux_halfword,
                "source_pointer": _pointer(pointer),
                "source_end_pointer": _pointer(end),
                "source_data_size": len(raw),
                "source_data_sha256": _sha256(raw),
                "raw_hex": rom[
                    table_offset : table_offset + BYTE_ENTRY_SIZE
                ].hex(),
            }
        )
        records.extend(
            (
                index,
                lower + relative,
                pointer + relative * BYTE_SOURCE_BYTES,
            )
            for relative in range(range_size)
        )
    return entries, records


def _mapping(
    root: Path,
    entries: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw = (root / MAPPING_PATH).read_bytes()
    document = json.loads(raw)
    mappings = document["mappings"]
    errors = []
    glyphs = []
    for key, value in sorted(mappings.items(), key=lambda item: int(item[0], 16)):
        sjis = int(key, 16)
        hits = [
            entry
            for entry in entries
            if entry["lower"]
            <= sjis
            < entry["lower"] + entry["range_size"]
        ]
        if len(hits) != 1:
            errors.append(f"{key}: expected one table hit, got {len(hits)}")
            continue
        entry = hits[0]
        pointer = (
            int(entry["source_pointer"], 16)
            + (sjis - entry["lower"]) * SJIS_SOURCE_BYTES
        )
        if value.get("entry") != entry["index"]:
            errors.append(
                f"{key}: entry {value.get('entry')} != {entry['index']}"
            )
        try:
            actual_pointer = int(value.get("tile_addr", ""), 16)
        except (TypeError, ValueError):
            actual_pointer = -1
        if actual_pointer != pointer:
            errors.append(
                f"{key}: source {value.get('tile_addr')} != {_pointer(pointer)}"
            )
        count = value.get("count")
        if not isinstance(count, int) or count <= 0:
            errors.append(f"{key}: invalid occurrence count {count!r}")
            count = 0
        glyphs.append(
            {
                "sjis": sjis,
                "sjis_hex": f"0x{sjis:04X}",
                "entry_index": entry["index"],
                "source_pointer": _pointer(pointer),
                "chapter_intro_count": count,
            }
        )
    return (
        {
            "path": str(MAPPING_PATH),
            "sha256": _sha256(raw),
            "mapping_count": len(mappings),
            "verified_mapping_count": len(mappings) - len(errors),
            "errors": errors,
        },
        glyphs,
    )


def _group0_stream(rom: bytes) -> dict[str, Any]:
    raw = rom[
        GROUP0_STREAM_OFFSET : GROUP0_STREAM_OFFSET + GROUP0_STREAM_SIZE
    ]
    if len(raw) != GROUP0_STREAM_SIZE:
        raise ValueError("group0 stream is truncated")
    if _sha256(raw) != GROUP0_STREAM_SHA256:
        raise ValueError("group0 stream SHA-256 mismatch")
    codes = []
    controls = []
    offset = 0
    while offset < len(raw):
        first = raw[offset]
        if first == 0x0A:
            controls.append(
                {
                    "relative_offset": offset,
                    "file_offset": GROUP0_STREAM_OFFSET + offset,
                    "value": "0x0A",
                }
            )
            offset += 1
            continue
        if not 0x81 <= first <= 0xFC or offset + 1 >= len(raw):
            raise ValueError(
                f"group0 invalid lead byte 0x{first:02X} at +0x{offset:X}"
            )
        second = raw[offset + 1]
        if not 0x40 <= second <= 0xFC:
            raise ValueError(
                f"group0 invalid trail byte 0x{second:02X} at +0x{offset + 1:X}"
            )
        codes.append(f"0x{first:02X}{second:02X}")
        offset += 2
    return {
        "file_offset": GROUP0_STREAM_OFFSET,
        "size": len(raw),
        "sha256": _sha256(raw),
        "raw_hex": raw.hex(),
        "sjis_token_count": len(codes),
        "sjis_codes": codes,
        "control_bytes": controls,
    }


def _localized_mapping(
    root: Path,
    rom: bytes,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    raw = (root / LOCALIZED_MAPPING_PATH).read_bytes()
    document = json.loads(raw)
    mapping = document["mapping"]
    unresolved = document.get("_unresolved_codes", {})
    if not isinstance(unresolved, dict):
        raise ValueError("localized glyph unresolved-code metadata is not an object")
    stream = _group0_stream(rom)
    errors = []
    verified = []
    overlap = sorted(set(mapping) & set(unresolved))
    if overlap:
        errors.append(f"codes both named and unresolved: {overlap}")
    for key, display_character in mapping.items():
        if not isinstance(display_character, str) or not display_character:
            errors.append(f"0x{key}: invalid display-character label")
        elif any(character in "\r\n" for character in display_character):
            errors.append(f"0x{key}: control character used as glyph label")
    rows = [
        (key, display_character, "historical_ocr_label", None)
        for key, display_character in mapping.items()
    ]
    rows.extend(
        (
            key,
            None,
            "unresolved",
            metadata.get("reason") if isinstance(metadata, dict) else str(metadata),
        )
        for key, metadata in unresolved.items()
    )
    stream_codes = {code.removeprefix("0x") for code in stream["sjis_codes"]}
    documented_codes = set(mapping) | set(unresolved)
    if stream_codes != documented_codes:
        errors.append(
            "group0 documented codes differ from parsed SJIS tokens: "
            f"missing={sorted(stream_codes - documented_codes)}, "
            f"extra={sorted(documented_codes - stream_codes)}"
        )
    for key, display_character, semantic_status, unresolved_reason in rows:
        sjis = int(key, 16)
        hit = None
        for entry in entries:
            if entry["lower"] <= sjis < entry["lower"] + entry["range_size"]:
                if hit is not None:
                    errors.append(f"0x{key}: multiple table hits")
                hit = entry
        if hit is None:
            errors.append(f"0x{key}: no table hit")
            continue
        pointer = (
            int(hit["source_pointer"], 16)
            + (sjis - hit["lower"]) * SJIS_SOURCE_BYTES
        )
        source = _source_raw(rom, pointer, SJIS_SOURCE_BYTES)
        verified.append(
            {
                "sjis": sjis,
                "sjis_hex": f"0x{sjis:04X}",
                "display_character": display_character,
                "semantic_status": semantic_status,
                "unresolved_reason": unresolved_reason,
                "entry_index": hit["index"],
                "source_pointer": _pointer(pointer),
                "source_sha256": _sha256(source),
                "source_indices_used": _used(_histogram(source)),
            }
        )
    return {
        "path": str(LOCALIZED_MAPPING_PATH),
        "sha256": _sha256(raw),
        "basis": document.get("_mapping_method"),
        "source_offsets": document.get("_source_offsets"),
        "semantic_mapping_count": len(mapping),
        "unresolved_code_count": len(unresolved),
        "source_resolved_count": len(verified),
        "source_binding_claim": (
            "ROM lookup verifies code, source pointer, and source bytes; "
            "historical OCR labels remain semantic metadata"
        ),
        "group0_stream": stream,
        "errors": errors,
        "mappings": verified,
    }


def _raw_for(
    rom: bytes,
    records: Iterable[tuple[int, int, int]],
    size: int,
) -> bytes:
    return b"".join(_source_raw(rom, pointer, size) for _, _, pointer in records)


def _compare(
    expected: Any,
    actual: Any,
    path: str,
    errors: list[str],
) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            errors.append(f"{path}: expected object, got {type(actual).__name__}")
            return
        for key in expected:
            child = f"{path}.{key}" if path else key
            if key not in actual:
                errors.append(f"{child}: missing")
            else:
                _compare(expected[key], actual[key], child, errors)
        for key in actual.keys() - expected.keys():
            child = f"{path}.{key}" if path else key
            errors.append(f"{child}: unexpected")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list):
            errors.append(f"{path}: expected list, got {type(actual).__name__}")
            return
        if len(expected) != len(actual):
            errors.append(
                f"{path}: expected length {len(expected)}, got {len(actual)}"
            )
        for index, (expected_item, actual_item) in enumerate(
            zip(expected, actual)
        ):
            _compare(expected_item, actual_item, f"{path}[{index}]", errors)
        return
    if expected != actual:
        errors.append(f"{path}: expected {expected!r}, got {actual!r}")


def _verify_dataset(
    artifact_dir: Path,
    *,
    name: str,
    source: bytes,
    item_count: int,
    item_width: int,
    item_height: int,
    source_bytes_per_item: int,
    palette_group: int | None,
    actual: Any,
    errors: list[str],
) -> set[str]:
    source_name = f"{name}-source-2bpp.bin"
    png_name = f"{name}-atlas.png"
    files = {source_name, png_name}
    try:
        actual_source = (artifact_dir / source_name).read_bytes()
    except OSError as exc:
        errors.append(f"{source_name}: {exc}")
        return files
    if actual_source != source:
        errors.append(f"{source_name}: bytes differ from ROM source")
    try:
        png_bytes = (artifact_dir / png_name).read_bytes()
        with Image.open(artifact_dir / png_name) as image:
            image.load()
            mode = image.mode
            size = image.size
            pixels = image.tobytes()
            palette = image.getpalette()
            has_transparency = "transparency" in image.info
    except (OSError, ValueError) as exc:
        errors.append(f"{png_name}: {exc}")
        return files
    expected_pixels, width, height = _decode_atlas(
        source,
        item_count=item_count,
        item_width=item_width,
        item_height=item_height,
        source_bytes_per_item=source_bytes_per_item,
    )
    if mode != "P":
        errors.append(f"{png_name}: expected mode P, got {mode}")
    if size != (width, height):
        errors.append(f"{png_name}: expected size {(width, height)}, got {size}")
    if pixels != expected_pixels:
        errors.append(f"{png_name}: pixels differ from decoded 2bpp source")
    expected_flat_palette = [
        channel for color in EXPECTED_RGB_PALETTE for channel in color
    ]
    if palette is None or palette[:12] != expected_flat_palette:
        errors.append(f"{png_name}: diagnostic palette differs")
    if has_transparency:
        errors.append(f"{png_name}: unexpected transparency metadata")

    histogram = _histogram(source)
    expected = {
        "item_count": item_count,
        "item_width": item_width,
        "item_height": item_height,
        "source_bytes_per_item": source_bytes_per_item,
        "source_bin": source_name,
        "source_size": len(source),
        "source_sha256": _sha256(source),
        "source_indices_used": _used(histogram),
        "source_index_histogram": histogram,
        "all_zero_records": sum(
            not any(source[offset : offset + source_bytes_per_item])
            for offset in range(0, len(source), source_bytes_per_item)
        ),
        "atlas_png": png_name,
        "atlas_png_sha256": _sha256(png_bytes),
        "atlas_width": width,
        "atlas_height": height,
    }
    if palette_group is not None:
        expanded = _expand(source, palette_group)
        expanded_name = f"{name}-expanded-4bpp.bin"
        files.add(expanded_name)
        try:
            actual_expanded = (artifact_dir / expanded_name).read_bytes()
            if actual_expanded != expanded:
                errors.append(
                    f"{expanded_name}: bytes differ from independent expansion"
                )
        except OSError as exc:
            errors.append(f"{expanded_name}: {exc}")
        expected.update(
            {
                "canonical_palette_group": palette_group,
                "expanded_4bpp_bin": expanded_name,
                "expanded_4bpp_size": len(expanded),
                "expanded_4bpp_sha256": _sha256(expanded),
            }
        )
    _compare(expected, actual, f"datasets.{name.replace('-', '_')}", errors)
    return files


def verify_dialogue_font_atlases(
    root: Path,
    artifact_dir: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        rom = (root / "rom/base.gba").read_bytes()
        manifest = json.loads(
            (artifact_dir / "manifest.json").read_text(encoding="utf-8")
        )
        sjis_entries, sjis_records = _parse_sjis(rom)
        byte_entries, byte_records = _parse_byte(rom)
        mapping, intro_glyphs = _mapping(root, sjis_entries)
        localized_mapping = _localized_mapping(root, rom, sjis_entries)
    except (
        OSError,
        ValueError,
        KeyError,
        struct.error,
        json.JSONDecodeError,
    ) as exc:
        return {
            "schema": "dialogue-font-verification-v2",
            "verified_logical_glyphs": 0,
            "verified_half_tiles": 0,
            "verified_atlases": 0,
            "errors": [f"input: {exc}"],
        }
    if _sha256(rom) != ROM_SHA256:
        errors.append("rom.sha256: source ROM mismatch")
    sjis_table = rom[
        SJIS_TABLE_OFFSET : SJIS_TABLE_OFFSET
        + SJIS_ENTRY_COUNT * SJIS_ENTRY_SIZE
    ]
    byte_table = rom[
        BYTE_TABLE_OFFSET : BYTE_TABLE_OFFSET
        + BYTE_ENTRY_COUNT * BYTE_ENTRY_SIZE
    ]
    if _sha256(sjis_table) != SJIS_TABLE_SHA256:
        errors.append("sjis_table.sha256: source table mismatch")
    if _sha256(byte_table) != BYTE_TABLE_SHA256:
        errors.append("byte_table.sha256: source table mismatch")
    if mapping["sha256"] != MAPPING_SHA256:
        errors.append("chapter_intro_mapping.sha256: source mapping mismatch")
    if localized_mapping["sha256"] != LOCALIZED_MAPPING_SHA256:
        errors.append("localized_mapping_evidence.sha256: source mapping mismatch")
    errors.extend(
        f"localized_mapping_evidence: {error}"
        for error in localized_mapping["errors"]
    )

    half_refs = {}
    for logical_index, (entry_index, sjis, pointer) in enumerate(sjis_records):
        for half_index in (0, 1):
            half_refs[pointer + half_index * 16] = {
                "lookup_branch": "sjis",
                "logical_index": logical_index,
                "entry_index": entry_index,
                "code": sjis,
                "half_index": half_index,
            }
    for logical_index, (entry_index, value, pointer) in enumerate(byte_records):
        half_refs[pointer] = {
            "lookup_branch": "byte",
            "logical_index": logical_index,
            "entry_index": entry_index,
            "code": value,
            "half_index": 0,
        }
    half_addresses = sorted(half_refs)
    half_index = {
        pointer: index for index, pointer in enumerate(half_addresses)
    }
    intro_counts = {
        glyph["sjis"]: glyph["chapter_intro_count"] for glyph in intro_glyphs
    }
    expected_sjis_glyphs = [
        {
            "logical_index": logical_index,
            "entry_index": entry_index,
            "sjis": sjis,
            "sjis_hex": f"0x{sjis:04X}",
            "source_pointer": _pointer(pointer),
            "source_sha256": _sha256(
                _source_raw(rom, pointer, SJIS_SOURCE_BYTES)
            ),
            "physical_half_tile_indices": [
                half_index[pointer],
                half_index[pointer + HALF_TILE_SOURCE_BYTES],
            ],
            "chapter_intro_count": intro_counts.get(sjis, 0),
        }
        for logical_index, (entry_index, sjis, pointer) in enumerate(
            sjis_records
        )
    ]
    expected_byte_glyphs = [
        {
            "logical_index": logical_index,
            "entry_index": entry_index,
            "byte_value": value,
            "byte_hex": f"0x{value:02X}",
            "source_pointer": _pointer(pointer),
            "source_sha256": _sha256(
                _source_raw(rom, pointer, BYTE_SOURCE_BYTES)
            ),
            "physical_half_tile_index": half_index[pointer],
        }
        for logical_index, (entry_index, value, pointer) in enumerate(
            byte_records
        )
    ]
    for glyph in intro_glyphs:
        pointer = int(glyph["source_pointer"], 16)
        glyph["physical_half_tile_indices"] = [
            half_index[pointer],
            half_index[pointer + HALF_TILE_SOURCE_BYTES],
        ]
    expected_halves = []
    for index, pointer in enumerate(half_addresses):
        raw = _source_raw(rom, pointer, HALF_TILE_SOURCE_BYTES)
        histogram = _histogram(raw)
        expected_halves.append(
            {
                "index": index,
                "source_pointer": _pointer(pointer),
                "file_offset": pointer - ROM_BASE,
                "sha256": _sha256(raw),
                "source_indices_used": _used(histogram),
                "source_index_histogram": histogram,
                "is_all_zero": not any(raw),
                **half_refs[pointer],
            }
        )

    unique_sources = {
        pointer for _, _, pointer in sjis_records + byte_records
    }
    expected_sections = {
        "schema": "dialogue-font-atlas-v2",
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": _sha256(rom),
        },
        "sjis_table": {
            "file_offset": SJIS_TABLE_OFFSET,
            "gba_address": _pointer(ROM_BASE + SJIS_TABLE_OFFSET),
            "entry_count": SJIS_ENTRY_COUNT,
            "entry_size": SJIS_ENTRY_SIZE,
            "sha256": _sha256(sjis_table),
            "logical_glyph_count": len(sjis_records),
            "source_bytes_per_glyph": SJIS_SOURCE_BYTES,
        },
        "byte_table": {
            "file_offset": BYTE_TABLE_OFFSET,
            "gba_address": _pointer(ROM_BASE + BYTE_TABLE_OFFSET),
            "entry_count": BYTE_ENTRY_COUNT,
            "entry_size": BYTE_ENTRY_SIZE,
            "sha256": _sha256(byte_table),
            "logical_glyph_count": len(byte_records),
            "source_bytes_per_glyph": BYTE_SOURCE_BYTES,
        },
        "logical_glyph_count": len(sjis_records) + len(byte_records),
        "unique_source_record_count": len(unique_sources),
        "physical_half_tile_count": len(half_addresses),
        "logical_alias_count": (
            len(sjis_records) + len(byte_records) - len(unique_sources)
        ),
        "storage_relationships": {
            "byte_entry_boundary": byte_entries[0]["source_end_pointer"],
            "byte_to_sjis_boundary": byte_entries[1]["source_end_pointer"],
            "sjis_first_source_pointer": sjis_entries[0]["source_pointer"],
            "overlap_bytes": 0,
            "all_source_records_unique": True,
        },
        "sjis_entries": sjis_entries,
        "byte_entries": byte_entries,
        "sjis_glyphs": expected_sjis_glyphs,
        "byte_glyphs": expected_byte_glyphs,
        "physical_half_tiles": expected_halves,
        "chapter_intro_mapping": mapping,
        "chapter_intro_glyphs": intro_glyphs,
        "localized_mapping_evidence": localized_mapping,
        "source_format": {
            "bits_per_pixel": 2,
            "pixels_per_byte": 4,
            "pixel_order_within_byte": "bits 1:0, 3:2, 5:4, 7:6",
            "sjis_record": {
                "width": 16,
                "height": 8,
                "half_tiles": 2,
                "bytes": SJIS_SOURCE_BYTES,
            },
            "byte_record": {
                "width": 8,
                "height": 8,
                "half_tiles": 1,
                "bytes": BYTE_SOURCE_BYTES,
            },
        },
        "runtime_expansion": {
            "formula": (
                "output_index = source_2bpp + (((arg1 & 1) + 2) << 2)"
            ),
            "sjis_expander": "0x08065EB8",
            "byte_expander": "0x080660A4",
            "sjis_renderer_arg1": 1,
            "sjis_renderer_indices": [12, 13, 14, 15],
            "byte_renderer_arg1": 0,
            "byte_renderer_indices": [8, 9, 10, 11],
            "sjis_output": (
                "two adjacent horizontal 8x8 4bpp tiles (16x8 glyph)"
            ),
            "byte_output": "one 8x8 4bpp tile",
            "runtime_rgb_palette_verified": False,
        },
        "visualization_palette": {
            "id": "diagnostic-source-2bpp-grayscale-v1",
            "bgr555_hex": EXPECTED_BGR555_HEX,
            "rgb888": EXPECTED_RGB_PALETTE,
            "runtime_verified": False,
            "transparent_index": None,
            "meaning": "source values 0..3 only; grayscale is not runtime RGB",
        },
        "consumer_chain": {
            "sjis_lookup": "0x08065E80",
            "sjis_outer": "0x08065F84",
            "byte_lookup": "0x0806606C",
            "renderer": "0x0808942C",
            "renderer_byte_call": "0x080894A8",
            "renderer_sjis_call": "0x080894DE",
            "code_slices": [dict(item) for item in EXPECTED_CODE_SLICES],
        },
        "scope": {
            "kind": (
                "localized base-ROM 2bpp dialogue glyph sources plus "
                "code-derived canonical 4bpp expansion"
            ),
            "runtime_rgb_palette_verified": False,
            "localized_base_rom_glyph_sources_exported": True,
            "group0_known_codes_use_sjis_table": True,
            "runtime_replacement_layer_proven": False,
            "full_unicode_naming_complete": False,
            "full_glyph_character_names_asserted": False,
            "both_lookup_branches_exported": True,
        },
    }
    for key, expected in expected_sections.items():
        if key not in manifest:
            errors.append(f"{key}: missing")
        else:
            _compare(expected, manifest[key], key, errors)

    for item in EXPECTED_CODE_SLICES:
        raw = rom[item["file_offset"] : item["file_offset"] + item["size"]]
        if _sha256(raw) != item["sha256"]:
            errors.append(f"consumer_chain.{item['name']}: code slice mismatch")

    sjis_source = _raw_for(rom, sjis_records, SJIS_SOURCE_BYTES)
    byte_source = _raw_for(rom, byte_records, BYTE_SOURCE_BYTES)
    intro_records = [
        (
            glyph["entry_index"],
            glyph["sjis"],
            int(glyph["source_pointer"], 16),
        )
        for glyph in intro_glyphs
    ]
    intro_source = _raw_for(rom, intro_records, SJIS_SOURCE_BYTES)
    half_source = b"".join(
        _source_raw(rom, pointer, HALF_TILE_SOURCE_BYTES)
        for pointer in half_addresses
    )
    dataset_specs = {
        "sjis_full": (
            "sjis-full",
            sjis_source,
            len(sjis_records),
            16,
            8,
            SJIS_SOURCE_BYTES,
            3,
        ),
        "byte_full": (
            "byte-full",
            byte_source,
            len(byte_records),
            8,
            8,
            BYTE_SOURCE_BYTES,
            2,
        ),
        "all_unique_halves": (
            "all-unique-halves",
            half_source,
            len(half_addresses),
            8,
            8,
            HALF_TILE_SOURCE_BYTES,
            None,
        ),
        "chapter_intro_used": (
            "chapter-intro-used",
            intro_source,
            len(intro_records),
            16,
            8,
            SJIS_SOURCE_BYTES,
            3,
        ),
    }
    actual_datasets = manifest.get("datasets")
    if not isinstance(actual_datasets, dict):
        errors.append("datasets: expected object")
        actual_datasets = {}
    expected_files = {"manifest.json"}
    for key, spec in dataset_specs.items():
        if key not in actual_datasets:
            errors.append(f"datasets.{key}: missing")
            continue
        expected_files.update(
            _verify_dataset(
                artifact_dir,
                name=spec[0],
                source=spec[1],
                item_count=spec[2],
                item_width=spec[3],
                item_height=spec[4],
                source_bytes_per_item=spec[5],
                palette_group=spec[6],
                actual=actual_datasets[key],
                errors=errors,
            )
        )
    for key in actual_datasets.keys() - dataset_specs.keys():
        errors.append(f"datasets.{key}: unexpected")
    try:
        actual_files = {
            path.name for path in artifact_dir.iterdir() if path.is_file()
        }
        if actual_files != expected_files:
            errors.append(
                f"artifact files: expected {sorted(expected_files)}, "
                f"got {sorted(actual_files)}"
            )
    except OSError as exc:
        errors.append(f"artifact files: {exc}")

    verified = not errors
    return {
        "schema": "dialogue-font-verification-v2",
        "verified_logical_glyphs": (
            len(sjis_records) + len(byte_records) if verified else 0
        ),
        "verified_half_tiles": len(half_addresses) if verified else 0,
        "verified_atlases": len(dataset_specs) if verified else 0,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify both localized-ROM dialogue font atlas branches",
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/dialogue-font-v2"),
    )
    args = parser.parse_args()
    report = verify_dialogue_font_atlases(
        args.root.resolve(),
        args.artifact_dir,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
