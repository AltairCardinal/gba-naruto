#!/usr/bin/env python3
"""Export both localized base-ROM dialogue glyph lookup branches losslessly."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.gba_image_export import indexed_png_from_bgr555


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

# Numeric source-index visualization only; no runtime RGB meaning is claimed.
SOURCE_PALETTE_BGR555 = bytes.fromhex("00004a29b556ff7f")
SOURCE_PALETTE_RGB888 = [
    [0, 0, 0],
    [82, 82, 82],
    [173, 173, 173],
    [255, 255, 255],
]

CODE_SLICES = (
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
        "name": "sjis_expansion_core",
        "file_offset": 0x065EB8,
        "gba_address": "0x08065EB8",
        "size": 0xCC,
        "sha256": "0c5faad64f303f95a978dc8e8aad3a45753923ebbb7df8674c0fe8cf24cf7712",
    },
    {
        "name": "byte_lookup_and_expansion",
        "file_offset": 0x06606C,
        "gba_address": "0x0806606C",
        "size": 0xD6,
        "sha256": "44442bbfae35bd6e11814fca10a3de9bf3fa9cfcb816a74fa4750cba9b4de168",
    },
    {
        "name": "cache_expansion_path",
        "file_offset": 0x08942C,
        "gba_address": "0x0808942C",
        "size": 0xB8,
        "sha256": "399a65ef6891c7c81acf42a52a8da2ee824bb80c77dcbd73f7a536845489e391",
    },
    {
        "name": "text_parser_vertical_layout",
        "file_offset": 0x066302,
        "gba_address": "0x08066302",
        "size": 0xA4,
        "sha256": "66b825738fc35608b0a2eeb6641dd1d4a354b8716510e35cdb8d675f69e8fb03",
    },
    {
        "name": "text_consumer_a_vertical_layout",
        "file_offset": 0x08CE8C,
        "gba_address": "0x0808CE8C",
        "size": 0x7C,
        "sha256": "d63541506eba58dc15f19989ef72cdbce3f4ccce748d48a7212fcfb333cb8ba7",
    },
    {
        "name": "text_consumer_b_vertical_layout",
        "file_offset": 0x08CF08,
        "gba_address": "0x0808CF08",
        "size": 0xA2,
        "sha256": "c61ec8fb439575c53b0d0a1b46d6fd935501155fe6a46a5a76b5f0e426dfae7a",
    },
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pointer(value: int) -> str:
    return f"0x{value:08X}"


def _source_raw(
    rom: bytes,
    pointer: int,
    size: int,
) -> bytes:
    offset = pointer - ROM_BASE
    if not 0 <= offset <= len(rom) - size:
        raise ValueError(f"source pointer {_pointer(pointer)} is outside the ROM")
    return rom[offset : offset + size]


def _source_histogram(raw: bytes) -> list[int]:
    histogram = [0] * 4
    for packed in raw:
        for shift in (0, 2, 4, 6):
            histogram[(packed >> shift) & 3] += 1
    return histogram


def _indices_used(histogram: list[int]) -> list[int]:
    return [index for index, count in enumerate(histogram) if count]


def expand_2bpp_to_4bpp(
    source: bytes,
    *,
    palette_group: int,
) -> bytes:
    """Reproduce the ROM's four-2bpp-pixels to four-4bpp-pixels expansion."""
    if not 0 <= palette_group <= 3:
        raise ValueError("palette group must fit two bits")
    base_index = palette_group << 2
    output = bytearray()
    for packed in source:
        values = [
            base_index | ((packed >> shift) & 3)
            for shift in (0, 2, 4, 6)
        ]
        output.extend(
            (
                values[0] | (values[1] << 4),
                values[2] | (values[3] << 4),
            )
        )
    return bytes(output)


def _decode_2bpp_record(source: bytes, *, width: int, height: int) -> bytes:
    if len(source) * 4 != width * height:
        raise ValueError("2bpp record size does not match its geometry")
    if width != 8 or height % 8:
        raise ValueError("dialogue atlas items must stack 8x8 tiles vertically")
    tile_count = height // 8
    if len(source) != tile_count * HALF_TILE_SOURCE_BYTES:
        raise ValueError("dialogue source tile count is inconsistent")
    pixels = bytearray()
    for tile_index in range(tile_count):
        tile_source = source[tile_index * 16 : (tile_index + 1) * 16]
        for packed in tile_source:
            pixels.extend((packed >> shift) & 3 for shift in (0, 2, 4, 6))
    return bytes(pixels)


def _render_source_atlas(
    source: bytes,
    *,
    item_count: int,
    item_width: int,
    item_height: int,
    source_bytes_per_item: int,
) -> tuple[bytes, int, int]:
    if len(source) != item_count * source_bytes_per_item:
        raise ValueError("source atlas item count is inconsistent")
    items_per_row = max(1, ATLAS_WIDTH_LIMIT // item_width)
    columns = min(item_count, items_per_row)
    rows = (item_count + items_per_row - 1) // items_per_row
    width = columns * item_width
    height = rows * item_height
    pixels = bytearray(width * height)
    for item_index in range(item_count):
        item_x = (item_index % items_per_row) * item_width
        item_y = (item_index // items_per_row) * item_height
        start = item_index * source_bytes_per_item
        item_pixels = _decode_2bpp_record(
            source[start : start + source_bytes_per_item],
            width=item_width,
            height=item_height,
        )
        for row in range(item_height):
            destination = (item_y + row) * width + item_x
            source_row = row * item_width
            pixels[destination : destination + item_width] = item_pixels[
                source_row : source_row + item_width
            ]
    return bytes(pixels), width, height


def _parse_sjis_entries(rom: bytes) -> list[dict[str, Any]]:
    entries = []
    previous_upper: int | None = None
    for index in range(SJIS_ENTRY_COUNT):
        table_offset = SJIS_TABLE_OFFSET + index * SJIS_ENTRY_SIZE
        lower, range_size, aux_byte, source_pointer = struct.unpack_from(
            "<HBBI",
            rom,
            table_offset,
        )
        if not range_size:
            raise ValueError(f"SJIS entry {index} has an empty range")
        if previous_upper is not None and lower < previous_upper:
            raise ValueError(f"SJIS entry {index} overlaps the previous range")
        previous_upper = lower + range_size
        source_end_pointer = source_pointer + range_size * SJIS_SOURCE_BYTES
        raw = _source_raw(
            rom,
            source_pointer,
            range_size * SJIS_SOURCE_BYTES,
        )
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
                "source_pointer": _pointer(source_pointer),
                "source_end_pointer": _pointer(source_end_pointer),
                "source_data_size": len(raw),
                "source_data_sha256": _sha256(raw),
                "raw_hex": rom[
                    table_offset : table_offset + SJIS_ENTRY_SIZE
                ].hex(),
            }
        )
    return entries


def _parse_byte_entries(rom: bytes) -> list[dict[str, Any]]:
    entries = []
    for index in range(BYTE_ENTRY_COUNT):
        table_offset = BYTE_TABLE_OFFSET + index * BYTE_ENTRY_SIZE
        lower, range_size, aux_halfword, source_pointer = struct.unpack_from(
            "<BBHI",
            rom,
            table_offset,
        )
        if not range_size:
            raise ValueError(f"byte entry {index} has an empty range")
        source_end_pointer = source_pointer + range_size * BYTE_SOURCE_BYTES
        raw = _source_raw(
            rom,
            source_pointer,
            range_size * BYTE_SOURCE_BYTES,
        )
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
                "source_pointer": _pointer(source_pointer),
                "source_end_pointer": _pointer(source_end_pointer),
                "source_data_size": len(raw),
                "source_data_sha256": _sha256(raw),
                "raw_hex": rom[
                    table_offset : table_offset + BYTE_ENTRY_SIZE
                ].hex(),
            }
        )
    return entries


def _logical_records(
    entries: list[dict[str, Any]],
    *,
    source_bytes: int,
) -> list[tuple[int, int, int]]:
    records = []
    for entry in entries:
        pointer = int(entry["source_pointer"], 16)
        for relative in range(entry["range_size"]):
            records.append(
                (
                    entry["index"],
                    entry["lower"] + relative,
                    pointer + relative * source_bytes,
                )
            )
    return records


def _mapping_evidence(
    root: Path,
    sjis_entries: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = root / MAPPING_PATH
    raw = path.read_bytes()
    source_sha256 = _sha256(raw)
    if source_sha256 != MAPPING_SHA256:
        raise ValueError("chapter-intro mapping SHA-256 mismatch")
    document = json.loads(raw)
    mappings = document.get("mappings")
    if not isinstance(mappings, dict):
        raise ValueError("chapter-intro mapping has no mappings object")
    errors = []
    used = []
    for key, value in sorted(mappings.items(), key=lambda item: int(item[0], 16)):
        sjis = int(key, 16)
        hits = [
            entry
            for entry in sjis_entries
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
        used.append(
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
            "sha256": source_sha256,
            "mapping_count": len(mappings),
            "verified_mapping_count": len(mappings) - len(errors),
            "errors": errors,
        },
        used,
    )


def _group0_stream_evidence(rom: bytes) -> dict[str, Any]:
    raw = rom[
        GROUP0_STREAM_OFFSET : GROUP0_STREAM_OFFSET + GROUP0_STREAM_SIZE
    ]
    if len(raw) != GROUP0_STREAM_SIZE:
        raise ValueError("group0 stream is truncated")
    if _sha256(raw) != GROUP0_STREAM_SHA256:
        raise ValueError("group0 stream SHA-256 mismatch")
    sjis_codes = []
    controls = []
    cursor = 0
    while cursor < len(raw):
        lead = raw[cursor]
        if lead == 0x0A:
            controls.append(
                {
                    "relative_offset": cursor,
                    "file_offset": GROUP0_STREAM_OFFSET + cursor,
                    "value": "0x0A",
                }
            )
            cursor += 1
            continue
        if not 0x81 <= lead <= 0xFC or cursor + 1 >= len(raw):
            raise ValueError(
                f"group0 invalid lead byte 0x{lead:02X} at +0x{cursor:X}"
            )
        trail = raw[cursor + 1]
        if not 0x40 <= trail <= 0xFC:
            raise ValueError(
                f"group0 invalid trail byte 0x{trail:02X} at +0x{cursor + 1:X}"
            )
        sjis_codes.append(f"0x{lead:02X}{trail:02X}")
        cursor += 2
    return {
        "file_offset": GROUP0_STREAM_OFFSET,
        "size": len(raw),
        "sha256": _sha256(raw),
        "raw_hex": raw.hex(),
        "sjis_token_count": len(sjis_codes),
        "sjis_codes": sjis_codes,
        "control_bytes": controls,
    }


def _localized_mapping_evidence(
    root: Path,
    rom: bytes,
    sjis_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    raw = (root / LOCALIZED_MAPPING_PATH).read_bytes()
    if _sha256(raw) != LOCALIZED_MAPPING_SHA256:
        raise ValueError("localized glyph mapping SHA-256 mismatch")
    document = json.loads(raw)
    mapping = document.get("mapping")
    if not isinstance(mapping, dict):
        raise ValueError("localized glyph mapping has no mapping object")
    unresolved = document.get("_unresolved_codes", {})
    if not isinstance(unresolved, dict):
        raise ValueError("localized glyph unresolved-code metadata is not an object")
    group0_stream = _group0_stream_evidence(rom)
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
    code_rows = [
        (key, display_character, "historical_ocr_label", None)
        for key, display_character in mapping.items()
    ]
    code_rows.extend(
        (
            key,
            None,
            "unresolved",
            metadata.get("reason") if isinstance(metadata, dict) else str(metadata),
        )
        for key, metadata in unresolved.items()
    )
    stream_codes = {code.removeprefix("0x") for code in group0_stream["sjis_codes"]}
    documented_codes = set(mapping) | set(unresolved)
    if stream_codes != documented_codes:
        errors.append(
            "group0 documented codes differ from parsed SJIS tokens: "
            f"missing={sorted(stream_codes - documented_codes)}, "
            f"extra={sorted(documented_codes - stream_codes)}"
        )
    for key, display_character, semantic_status, unresolved_reason in code_rows:
        sjis = int(key, 16)
        hits = [
            entry
            for entry in sjis_entries
            if entry["lower"]
            <= sjis
            < entry["lower"] + entry["range_size"]
        ]
        if len(hits) != 1:
            errors.append(f"0x{key}: expected one table hit, got {len(hits)}")
            continue
        entry = hits[0]
        pointer = (
            int(entry["source_pointer"], 16)
            + (sjis - entry["lower"]) * SJIS_SOURCE_BYTES
        )
        source = _source_raw(rom, pointer, SJIS_SOURCE_BYTES)
        verified.append(
            {
                "sjis": sjis,
                "sjis_hex": f"0x{sjis:04X}",
                "display_character": display_character,
                "semantic_status": semantic_status,
                "unresolved_reason": unresolved_reason,
                "entry_index": entry["index"],
                "source_pointer": _pointer(pointer),
                "source_sha256": _sha256(source),
                "source_indices_used": _indices_used(
                    _source_histogram(source)
                ),
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
        "group0_stream": group0_stream,
        "errors": errors,
        "mappings": verified,
    }


def _raw_for_records(
    rom: bytes,
    records: Iterable[tuple[int, int, int]],
    *,
    source_bytes: int,
) -> bytes:
    return b"".join(
        _source_raw(rom, pointer, source_bytes)
        for _, _, pointer in records
    )


def _write_dataset(
    output_dir: Path,
    *,
    name: str,
    source: bytes,
    item_count: int,
    item_width: int,
    item_height: int,
    source_bytes_per_item: int,
    item_layout: str,
    palette_group: int | None,
    expansion_context: str | None,
) -> dict[str, Any]:
    source_name = f"{name}-source-2bpp.bin"
    png_name = f"{name}-atlas.png"
    (output_dir / source_name).write_bytes(source)
    pixels, width, height = _render_source_atlas(
        source,
        item_count=item_count,
        item_width=item_width,
        item_height=item_height,
        source_bytes_per_item=source_bytes_per_item,
    )
    png = indexed_png_from_bgr555(
        pixels,
        SOURCE_PALETTE_BGR555,
        width=width,
        height=height,
        transparent_index=None,
    )
    (output_dir / png_name).write_bytes(png)
    histogram = _source_histogram(source)
    result = {
        "item_count": item_count,
        "item_width": item_width,
        "item_height": item_height,
        "item_layout": item_layout,
        "source_bytes_per_item": source_bytes_per_item,
        "source_bin": source_name,
        "source_size": len(source),
        "source_sha256": _sha256(source),
        "source_indices_used": _indices_used(histogram),
        "source_index_histogram": histogram,
        "all_zero_records": sum(
            not any(source[offset : offset + source_bytes_per_item])
            for offset in range(0, len(source), source_bytes_per_item)
        ),
        "atlas_png": png_name,
        "atlas_png_sha256": _sha256(png),
        "atlas_width": width,
        "atlas_height": height,
    }
    if palette_group is not None:
        if expansion_context is None:
            raise ValueError("expanded dataset requires a consumer context")
        expanded = expand_2bpp_to_4bpp(
            source,
            palette_group=palette_group,
        )
        expanded_name = f"{name}-expanded-4bpp.bin"
        (output_dir / expanded_name).write_bytes(expanded)
        result.update(
            {
                "expansion_palette_group": palette_group,
                "expansion_context": expansion_context,
                "expanded_4bpp_bin": expanded_name,
                "expanded_4bpp_size": len(expanded),
                "expanded_4bpp_sha256": _sha256(expanded),
            }
        )
    return result


def build_manifest(
    root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    rom = (root / "rom/base.gba").read_bytes()
    rom_sha256 = _sha256(rom)
    if rom_sha256 != ROM_SHA256:
        raise ValueError(
            f"unexpected ROM SHA-256 {rom_sha256}; expected {ROM_SHA256}"
        )
    sjis_table = rom[
        SJIS_TABLE_OFFSET : SJIS_TABLE_OFFSET
        + SJIS_ENTRY_COUNT * SJIS_ENTRY_SIZE
    ]
    byte_table = rom[
        BYTE_TABLE_OFFSET : BYTE_TABLE_OFFSET
        + BYTE_ENTRY_COUNT * BYTE_ENTRY_SIZE
    ]
    if _sha256(sjis_table) != SJIS_TABLE_SHA256:
        raise ValueError("SJIS table SHA-256 mismatch")
    if _sha256(byte_table) != BYTE_TABLE_SHA256:
        raise ValueError("byte table SHA-256 mismatch")

    sjis_entries = _parse_sjis_entries(rom)
    byte_entries = _parse_byte_entries(rom)
    sjis_records = _logical_records(
        sjis_entries,
        source_bytes=SJIS_SOURCE_BYTES,
    )
    byte_records = _logical_records(
        byte_entries,
        source_bytes=BYTE_SOURCE_BYTES,
    )
    if len(sjis_records) != 4410 or len(byte_records) != 192:
        raise ValueError("font table logical record counts are unexpected")
    mapping, intro_glyphs = _mapping_evidence(root, sjis_entries)
    if mapping["errors"]:
        raise ValueError("chapter-intro mapping no longer matches the ROM")
    localized_mapping = _localized_mapping_evidence(
        root,
        rom,
        sjis_entries,
    )
    if localized_mapping["errors"]:
        raise ValueError("localized glyph mapping no longer matches the ROM")

    half_references: dict[int, dict[str, Any]] = {}
    for logical_index, (entry_index, sjis, pointer) in enumerate(sjis_records):
        for half_index in (0, 1):
            half_pointer = pointer + half_index * HALF_TILE_SOURCE_BYTES
            if half_pointer in half_references:
                raise ValueError("SJIS source half unexpectedly aliases")
            half_references[half_pointer] = {
                "lookup_branch": "sjis",
                "logical_index": logical_index,
                "entry_index": entry_index,
                "code": sjis,
                "half_index": half_index,
            }
    for logical_index, (entry_index, byte_value, pointer) in enumerate(
        byte_records
    ):
        if pointer in half_references:
            raise ValueError("byte source unexpectedly aliases another half")
        half_references[pointer] = {
            "lookup_branch": "byte",
            "logical_index": logical_index,
            "entry_index": entry_index,
            "code": byte_value,
            "half_index": 0,
        }
    half_addresses = sorted(half_references)
    half_index_by_pointer = {
        pointer: index for index, pointer in enumerate(half_addresses)
    }

    intro_count_by_sjis = {
        glyph["sjis"]: glyph["chapter_intro_count"] for glyph in intro_glyphs
    }
    sjis_glyphs = [
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
                half_index_by_pointer[pointer],
                half_index_by_pointer[pointer + HALF_TILE_SOURCE_BYTES],
            ],
            "chapter_intro_count": intro_count_by_sjis.get(sjis, 0),
        }
        for logical_index, (entry_index, sjis, pointer) in enumerate(
            sjis_records
        )
    ]
    byte_glyphs = [
        {
            "logical_index": logical_index,
            "entry_index": entry_index,
            "byte_value": byte_value,
            "byte_hex": f"0x{byte_value:02X}",
            "source_pointer": _pointer(pointer),
            "source_sha256": _sha256(
                _source_raw(rom, pointer, BYTE_SOURCE_BYTES)
            ),
            "physical_half_tile_index": half_index_by_pointer[pointer],
        }
        for logical_index, (entry_index, byte_value, pointer) in enumerate(
            byte_records
        )
    ]
    for glyph in intro_glyphs:
        pointer = int(glyph["source_pointer"], 16)
        glyph["physical_half_tile_indices"] = [
            half_index_by_pointer[pointer],
            half_index_by_pointer[pointer + HALF_TILE_SOURCE_BYTES],
        ]

    physical_half_tiles = []
    for index, pointer in enumerate(half_addresses):
        raw = _source_raw(rom, pointer, HALF_TILE_SOURCE_BYTES)
        histogram = _source_histogram(raw)
        physical_half_tiles.append(
            {
                "index": index,
                "source_pointer": _pointer(pointer),
                "file_offset": pointer - ROM_BASE,
                "sha256": _sha256(raw),
                "source_indices_used": _indices_used(histogram),
                "source_index_histogram": histogram,
                "is_all_zero": not any(raw),
                **half_references[pointer],
            }
        )

    sjis_source = _raw_for_records(
        rom,
        sjis_records,
        source_bytes=SJIS_SOURCE_BYTES,
    )
    byte_source = _raw_for_records(
        rom,
        byte_records,
        source_bytes=BYTE_SOURCE_BYTES,
    )
    intro_records = [
        (
            glyph["entry_index"],
            glyph["sjis"],
            int(glyph["source_pointer"], 16),
        )
        for glyph in intro_glyphs
    ]
    intro_source = _raw_for_records(
        rom,
        intro_records,
        source_bytes=SJIS_SOURCE_BYTES,
    )
    half_source = b"".join(
        _source_raw(rom, pointer, HALF_TILE_SOURCE_BYTES)
        for pointer in half_addresses
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    datasets = {
        "sjis_full": _write_dataset(
            output_dir,
            name="sjis-full",
            source=sjis_source,
            item_count=len(sjis_records),
            item_width=8,
            item_height=16,
            source_bytes_per_item=SJIS_SOURCE_BYTES,
            item_layout="vertical-proven-consumer-layout",
            palette_group=3,
            expansion_context="0x080894DE callsite in 0x08089310 function; arg1=1",
        ),
        "byte_full": _write_dataset(
            output_dir,
            name="byte-full",
            source=byte_source,
            item_count=len(byte_records),
            item_width=8,
            item_height=8,
            source_bytes_per_item=BYTE_SOURCE_BYTES,
            item_layout="single-tile",
            palette_group=2,
            expansion_context="0x080894A8 callsite in 0x08089310 function; arg1=0",
        ),
        "all_unique_halves": _write_dataset(
            output_dir,
            name="all-unique-halves",
            source=half_source,
            item_count=len(half_addresses),
            item_width=8,
            item_height=8,
            source_bytes_per_item=HALF_TILE_SOURCE_BYTES,
            item_layout="single-tile",
            palette_group=None,
            expansion_context=None,
        ),
        "chapter_intro_used": _write_dataset(
            output_dir,
            name="chapter-intro-used",
            source=intro_source,
            item_count=len(intro_records),
            item_width=8,
            item_height=16,
            source_bytes_per_item=SJIS_SOURCE_BYTES,
            item_layout="vertical-proven-consumer-layout",
            palette_group=3,
            expansion_context="0x080894DE callsite in 0x08089310 function; arg1=1",
        ),
    }

    code_slices = []
    for expected in CODE_SLICES:
        raw = rom[
            expected["file_offset"] : expected["file_offset"] + expected["size"]
        ]
        if _sha256(raw) != expected["sha256"]:
            raise ValueError(f"{expected['name']} code slice SHA-256 mismatch")
        code_slices.append(dict(expected))

    logical_count = len(sjis_records) + len(byte_records)
    unique_source_pointers = {
        pointer for _, _, pointer in sjis_records + byte_records
    }
    return {
        "schema": "dialogue-font-atlas-v2",
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": rom_sha256,
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
        "logical_glyph_count": logical_count,
        "unique_source_record_count": len(unique_source_pointers),
        "physical_half_tile_count": len(half_addresses),
        "logical_alias_count": logical_count - len(unique_source_pointers),
        "storage_relationships": {
            "byte_entry_boundary": byte_entries[0]["source_end_pointer"],
            "byte_to_sjis_boundary": byte_entries[1]["source_end_pointer"],
            "sjis_first_source_pointer": sjis_entries[0]["source_pointer"],
            "overlap_bytes": 0,
            "all_source_records_unique": True,
        },
        "sjis_entries": sjis_entries,
        "byte_entries": byte_entries,
        "sjis_glyphs": sjis_glyphs,
        "byte_glyphs": byte_glyphs,
        "physical_half_tiles": physical_half_tiles,
        "chapter_intro_mapping": mapping,
        "chapter_intro_glyphs": intro_glyphs,
        "localized_mapping_evidence": localized_mapping,
        "datasets": datasets,
        "source_format": {
            "bits_per_pixel": 2,
            "pixels_per_byte": 4,
            "pixel_order_within_byte": "bits 1:0, 3:2, 5:4, 7:6",
            "sjis_record": {
                "bytes": SJIS_SOURCE_BYTES,
                "half_tile_count": 2,
                "half_tile_dimensions": [8, 8],
                "half_tile_order": [0, 1],
                "intrinsic_layout": "none",
            },
            "byte_record": {
                "bytes": BYTE_SOURCE_BYTES,
                "tile_count": 1,
                "tile_dimensions": [8, 8],
                "intrinsic_layout": "single-tile",
            },
        },
        "runtime_expansion": {
            "formula": (
                "output_index = source_2bpp + (((arg1 & 1) + 2) << 2)"
            ),
            "sjis_expander": "0x08065EB8",
            "byte_expander": "0x080660A4",
            "sjis_cache_arg1": 1,
            "sjis_cache_indices": [12, 13, 14, 15],
            "byte_cache_arg1": 0,
            "byte_cache_indices": [8, 9, 10, 11],
            "cache_enclosing_function": "0x08089310",
            "cache_path_anchor": "0x0808942C",
            "byte_cache_callsite": "0x080894A8",
            "sjis_cache_callsite": "0x080894DE",
            "cache_path_final_layout": "undetermined",
            "sjis_output": (
                "two ordered 8x8 4bpp tiles; final layout is consumer-defined"
            ),
            "byte_output": "one 8x8 4bpp tile",
            "runtime_rgb_palette_verified": False,
        },
        "runtime_layouts": [
            {
                "consumer": "0x0806626C",
                "role": "tilemap-layout",
                "glyph_dimensions": [8, 16],
                "half_tile_layout": "vertical",
                "half_tile_order": ["top", "bottom"],
                "horizontal_advance_tiles": 1,
                "code_slice": "text_parser_vertical_layout",
                "expander_callsite": "0x08066306",
                "half_0_store": "0x08066388",
                "half_1_store": "0x08066394",
                "row_stride_evidence": "context width * 2 bytes",
                "column_advance_evidence": "0x08066396..0x0806639A",
            },
            {
                "consumer": "0x0808CE8C",
                "role": "tilemap-layout",
                "glyph_dimensions": [8, 16],
                "half_tile_layout": "vertical",
                "half_tile_order": ["top", "bottom"],
                "horizontal_advance_tiles": 1,
                "code_slice": "text_consumer_a_vertical_layout",
                "expander_callsite": "0x0808CED2",
                "half_0_store": "0x0808CEEA",
                "half_1_store": "0x0808CEEE",
                "row_stride_evidence": "width * 2 bytes",
                "column_advance_evidence": "0x0808CEF2",
            },
            {
                "consumer": "0x0808CF08",
                "role": "tilemap-layout",
                "glyph_dimensions": [8, 16],
                "half_tile_layout": "vertical",
                "half_tile_order": ["top", "bottom"],
                "horizontal_advance_tiles": 1,
                "code_slice": "text_consumer_b_vertical_layout",
                "expander_callsite": "0x0808CF5E",
                "half_0_store": "0x0808CF82",
                "half_1_store": "0x0808CF86",
                "row_stride_evidence": "width * 2 bytes",
                "column_advance_evidence": "0x0808CF8A..0x0808CF92",
            },
        ],
        "visualization_palette": {
            "id": "diagnostic-source-2bpp-grayscale-v1",
            "bgr555_hex": SOURCE_PALETTE_BGR555.hex(),
            "rgb888": SOURCE_PALETTE_RGB888,
            "runtime_verified": False,
            "transparent_index": None,
            "meaning": (
                "source values 0..3 only; grayscale is not runtime RGB"
            ),
        },
        "consumer_chain": {
            "sjis_lookup": "0x08065E80",
            "sjis_outer": "0x08065F84",
            "byte_lookup": "0x0806606C",
            "cache_enclosing_function": "0x08089310",
            "cache_path_anchor": "0x0808942C",
            "cache_byte_callsite": "0x080894A8",
            "cache_sjis_callsite": "0x080894DE",
            "vertical_layout_consumers": [
                "0x0806626C",
                "0x0808CE8C",
                "0x0808CF08",
            ],
            "code_slices": code_slices,
        },
        "scope": {
            "kind": (
                "localized base-ROM 2bpp dialogue glyph sources plus "
                "context-bound diagnostic 4bpp expansions"
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


def export_dialogue_font_atlases(
    root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    manifest = build_manifest(root, output_dir)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export both localized-ROM dialogue font lookup branches",
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/dialogue-font-v2"),
    )
    args = parser.parse_args()
    manifest = export_dialogue_font_atlases(
        args.root.resolve(),
        args.output_dir,
    )
    print(
        json.dumps(
            {
                "schema": manifest["schema"],
                "logical_glyphs": manifest["logical_glyph_count"],
                "half_tiles": manifest["physical_half_tile_count"],
                "atlases": len(manifest["datasets"]),
                "output": str(args.output_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
