#!/usr/bin/env python3
"""Export the process-generated five-tile battle status-bar family."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
from typing import Any
import uuid
import zlib

try:
    from tools.inspect_mgba_savestate import load_gba_state
    from tools.thumb_branch import decode_thumb_bl
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from inspect_mgba_savestate import load_gba_state
    from thumb_branch import decode_thumb_bl


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "battle-status-bars-v1"
VERIFY_SCHEMA = "battle-status-bars-verification-v1"
PAYLOAD_NAME = "battle-status-bars.json"
EXPECTED_FILES = {
    "source-templates.4bpp.bin",
    "generated-family.4bpp.bin",
    "runtime-palette-bank13.bgr555.bin",
    "battle-status-bars.png",
    PAYLOAD_NAME,
}
ROM_RELATIVE = Path("rom/base.gba")
PARENT_RELATIVE = Path(
    "artifacts/initializer-resource-pack-v1/initializer-resource-pack.json"
)
PARENT_MANIFEST_RELATIVE = Path("artifacts/initializer-resource-pack-v1/manifest.json")
OVERVIEW_RELATIVE = Path(
    "artifacts/overview-gradient-overlay-v1/overview-gradient-overlay.json"
)
OVERVIEW_MANIFEST_RELATIVE = Path(
    "artifacts/overview-gradient-overlay-v1/manifest.json"
)
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PARENT_SHA256 = "c096e70c033f804548446272c47d43bfefa72eed173841e152c630c5436efba8"
PARENT_MANIFEST_SHA256 = (
    "8fc7c3ea449b480c5065a97e70d0f6c5c0fa30a0dc3f942931f6be86264337a4"
)
OVERVIEW_SHA256 = "b4ac97c3bc534d6932b9d189d58a31fe7986c5c9f3557f590fba0fdd839a8b6d"
OVERVIEW_MANIFEST_SHA256 = (
    "cd7c16abcd865827ea35fc7014e13b1681b69a7e17ecf45daa0a1f9a82be931e"
)

GENERATOR_RANGE = (0x068370, 0x068642)
GENERATOR_SHA256 = (
    "13ef2ceedfe889bee6b7a6666d268246f43daa3fe5ad0be83a37f275e4ff4b20"
)
FULL_OBJECT_RANGE = (0x068370, 0x068660)
FULL_OBJECT_SHA256 = (
    "9ed2404ba8cae02b834b691ef5f7b9df8db76eca6cc52f280a4e3737dd8e0b3e"
)
LITERAL_POOL_RANGE = (0x068644, 0x068660)
LITERAL_POOL_SHA256 = (
    "b39034f0d29df6c4c8f3c26eaad80f406ec9e105f0f7b1bb1c8729ae159c926f"
)
CALLER_RANGES = (
    (
        0x06ED88,
        0x06F0FC,
        "35c52ecf13a5ce848d9077b47f96d2d04c3134e5ebe28444b61fa90a4c1d9964",
    ),
    (
        0x07A34C,
        0x07AA8C,
        "f400ef9501381b6e005e7d9c51add8ac5fe3dc4217a3fa6397e1ccdf3dc64c51",
    ),
)
DIRECT_CALLS = (0x0806F0D6, 0x0806F0EC, 0x0807A83C, 0x0807A8A6)
WORK_TILES = 0x0201BD84
GRAPHICS_BASE_POINTER = 0x0201BD48
TEMPLATE_BASE_POINTER = 0x0201BD54
PALETTE_ADDRESS = 0x050001A0
SCREEN_BASE = 0x06001800
BAR_BYTES = 160

SCOPE = {
    "generator_algorithm_code_verified": True,
    "source_templates_losslessly_exported": True,
    "all_fill_levels_losslessly_generated": True,
    "tracked_battle_bg3_unknown_content_fully_resolved": True,
    "tracked_visible_resource_denominator_complete": True,
    "all_game_visual_states_complete": False,
    "all_generator_callers_runtime_bound": False,
    "bar_input_field_semantics_complete": False,
    "generic_image_writeback_complete": False,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _code_record(
    rom: bytes, start: int, end: int, expected_sha256: str
) -> dict[str, Any]:
    data = rom[start:end]
    actual = _sha256(data)
    if actual != expected_sha256:
        raise ValueError(f"ROM code hash changed at {_address(0x08000000 + start)}")
    return {
        "gba_start": _address(0x08000000 + start),
        "gba_end_exclusive": _address(0x08000000 + end),
        "size": len(data),
        "sha256": actual,
    }


def _require_hash(path: Path, expected: str, label: str) -> bytes:
    data = path.read_bytes()
    if _sha256(data) != expected:
        raise ValueError(f"{label} SHA-256 changed")
    return data


def generate_bar(template: bytes, style: int, fill_level: int) -> bytes:
    """Reproduce the nibble-aware loop at 0x080683F6..0x0806859E."""

    if len(template) != BAR_BYTES:
        raise ValueError("bar template must contain five 4bpp tiles")
    if style not in (0, 1) or not 0 <= fill_level <= 38:
        raise ValueError("style/fill level outside generator domain")
    result = bytearray(template)
    cursor = 4

    def write_triplet(first: int, second: int, third: int) -> None:
        for offset in (0, 20):
            result[cursor + offset] = first
        for offset in (4, 16):
            result[cursor + offset] = second
        for offset in (8, 12):
            result[cursor + offset] = third

    for position in range(1, 39):
        triplet: tuple[int, int, int] | None
        if position < fill_level:
            if position == 1:
                triplet = (
                    (0x32, 0xA3, 0x93)
                    if style == 0
                    else (0x32, 0x63, 0x53)
                )
            elif position & 1:
                triplet = None
            else:
                triplet = (
                    (0xAA, 0x99, 0x88)
                    if style == 0
                    else (0x66, 0x55, 0x44)
                )
        elif position == fill_level:
            if position == 1:
                triplet = (
                    (0x32, 0xA3, 0x93)
                    if style == 0
                    else (0x32, 0x63, 0x53)
                )
            elif position <= 37:
                if position & 1:
                    triplet = (
                        (0xBA, 0xA9, 0x98)
                        if style == 0
                        else (0x76, 0x65, 0x54)
                    )
                else:
                    triplet = (
                        (0xBB, 0xBA, 0xB9)
                        if style == 0
                        else (0x77, 0x76, 0x75)
                    )
            else:
                triplet = (
                    (0x12, 0x1A, 0x19)
                    if style == 0
                    else (0x12, 0x16, 0x15)
                )
        else:
            if position == 1:
                triplet = (0x32, 0xB3, 0xB3)
            elif position <= 37:
                if not position & 1:
                    triplet = (
                        (0xBB, 0xBB, 0xBB)
                        if style == 0
                        else (0x77, 0x77, 0x77)
                    )
                elif position - 1 == fill_level:
                    triplet = (
                        (0xBB, 0xBA, 0xB9)
                        if style == 0
                        else (0xBB, 0xB6, 0xB5)
                    )
                else:
                    triplet = None
            else:
                triplet = (0x12, 0x1B, 0x1B)
        if triplet is not None:
            write_triplet(*triplet)
        if position & 1:
            cursor += 1
            if position & 7 == 7:
                cursor += 28
    return bytes(result)


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def _stored_zlib(data: bytes) -> bytes:
    """Encode deterministic RFC 1950 data with uncompressed DEFLATE blocks."""

    output = bytearray(b"\x78\x01")
    cursor = 0
    while cursor < len(data):
        block = data[cursor : cursor + 0xFFFF]
        cursor += len(block)
        output.append(1 if cursor == len(data) else 0)
        output.extend(struct.pack("<HH", len(block), len(block) ^ 0xFFFF))
        output.extend(block)
    output.extend(struct.pack(">I", zlib.adler32(data) & 0xFFFFFFFF))
    return bytes(output)


def _render_family(family: list[list[bytes]], palette: bytes) -> bytes:
    pixels = bytearray(80 * 312)
    for style in range(2):
        for fill_level in range(39):
            bar = family[style][fill_level]
            for tile_index in range(5):
                tile = bar[tile_index * 32 : (tile_index + 1) * 32]
                for y in range(8):
                    for x in range(8):
                        packed = tile[y * 4 + x // 2]
                        color = (packed >> (4 * (x & 1))) & 0x0F
                        px = style * 40 + tile_index * 8 + x
                        py = fill_level * 8 + y
                        pixels[py * 80 + px] = color
    colors = struct.unpack("<16H", palette)
    rgb = bytearray()
    for color in colors:
        for shift in (0, 5, 10):
            channel = (color >> shift) & 0x1F
            rgb.append((channel << 3) | (channel >> 2))
    rgb.extend(bytes(768 - len(rgb)))
    scanlines = b"".join(
        b"\x00" + pixels[row * 80 : (row + 1) * 80] for row in range(312)
    )
    ihdr = struct.pack(">IIBBBBB", 80, 312, 8, 3, 0, 0, 0)
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(b"IHDR", ihdr),
            _png_chunk(b"PLTE", bytes(rgb)),
            _png_chunk(b"tRNS", b"\x00"),
            _png_chunk(b"IDAT", _stored_zlib(scanlines)),
            _png_chunk(b"IEND", b""),
        )
    )


def _battle_layers(parent: dict[str, Any]) -> list[dict[str, Any]]:
    layers = [
        layer
        for layer in parent["runtime_binding"]["layers"]
        if layer.get("unmatched_nonfont_contents")
        and layer.get("checkpoint") != "alternate-character-overview.ss9"
    ]
    if len(layers) != 30 or any(layer.get("bg_index") != 3 for layer in layers):
        raise ValueError("parent battle BG3 layer inventory changed")
    return sorted(layers, key=lambda item: item["checkpoint"])


def _load_sources(
    root: Path, layers: list[dict[str, Any]]
) -> tuple[tuple[bytes, bytes], bytes, dict[str, Any], list[Any]]:
    states = []
    checkpoint_records = []
    reference_templates: tuple[bytes, bytes] | None = None
    reference_palette: bytes | None = None
    for layer in layers:
        relative = Path("artifacts/runtime-checkpoints") / layer["checkpoint"]
        path = root / relative
        raw = path.read_bytes()
        state = load_gba_state(path)
        if state.read_u32(GRAPHICS_BASE_POINTER) != 0x0600C000:
            raise ValueError("battle dynamic graphics base changed")
        if state.read_u32(TEMPLATE_BASE_POINTER) != 0x0600F800:
            raise ValueError("battle template graphics base changed")
        if state.read_u32(0x0201BD50) != SCREEN_BASE:
            raise ValueError("battle BG3 screen base changed")
        templates = (
            state.read_memory(0x0600FB00, BAR_BYTES),
            state.read_memory(0x0600FBA0, BAR_BYTES),
        )
        palette = state.read_memory(PALETTE_ADDRESS, 32)
        if reference_templates is None:
            reference_templates = templates
            reference_palette = palette
        if templates != reference_templates or palette != reference_palette:
            raise ValueError("battle checkpoints disagree on bar source resources")
        states.append(state)
        checkpoint_records.append(
            {
                "checkpoint": relative.as_posix(),
                "sha256": _sha256(raw),
                "parent_layer_key": layer["parent_layer_key"],
                "parent_layer_sha256": layer["parent_layer_sha256"],
            }
        )
    assert reference_templates is not None and reference_palette is not None
    expected = (
        "cacf8c0f71ff964ddd962a02ad4f5a2713dd0dc9e43f1adc5d3f690f72f5b21f",
        "d0eda4d1836693671205f7c9cfb82abed04167600ecf498fdcbf2b98608791cd",
    )
    if tuple(_sha256(item) for item in reference_templates) != expected:
        raise ValueError("battle bar template hashes changed")
    if _sha256(reference_palette) != (
        "82f1c93a86b077a17e05e44c28d7f6522ff69542a6356487ce25a45b61a8a9d2"
    ):
        raise ValueError("battle bar runtime palette changed")
    return reference_templates, reference_palette, {
        item["checkpoint"]: item for item in checkpoint_records
    }, states


def _runtime_binding(
    layers: list[dict[str, Any]],
    states: list[Any],
    family: list[list[bytes]],
    checkpoints: dict[str, Any],
) -> dict[str, Any]:
    bars = []
    cells: dict[tuple[str, int], dict[str, Any]] = {}
    for layer, state in zip(layers, states):
        checkpoint = layer["checkpoint"]
        starts = [
            start
            for content in layer["unmatched_nonfont_contents"]
            for start, _ in content["linear_cell_ranges"]
        ]
        row_start = 501 if min(starts) < 544 else 565
        tilemap = struct.unpack("<1024H", state.read_memory(SCREEN_BASE, 2048))
        for style, first_linear in ((0, row_start), (1, row_start + 32)):
            entries = list(tilemap[first_linear : first_linear + 5])
            if any(
                entry >> 12 != 13 or entry & 0x0C00 for entry in entries
            ):
                raise ValueError(f"{checkpoint} bar tilemap attributes changed")
            tile_ids = [entry & 0x03FF for entry in entries]
            tile_data = [
                state.read_memory(0x0600C000 + tile_id * 32, 32)
                for tile_id in tile_ids
            ]
            full_bar = b"".join(tile_data)
            matches = [
                fill_level
                for fill_level in range(39)
                if family[style][fill_level] == full_bar
            ]
            if len(matches) != 1:
                raise ValueError(f"{checkpoint} bar does not resolve uniquely")
            bar_index = len(bars)
            for tile_index, tile in enumerate(tile_data):
                cells[(checkpoint, first_linear + tile_index)] = {
                    "bar_index": bar_index,
                    "style": style,
                    "fill_level": matches[0],
                    "tile_index": tile_index,
                    "sha256": _sha256(tile),
                }
            bars.append(
                {
                    "checkpoint": checkpoints[
                        f"artifacts/runtime-checkpoints/{checkpoint}"
                    ]["checkpoint"],
                    "checkpoint_sha256": checkpoints[
                        f"artifacts/runtime-checkpoints/{checkpoint}"
                    ]["sha256"],
                    "parent_layer_key": layer["parent_layer_key"],
                    "parent_layer_sha256": layer["parent_layer_sha256"],
                    "style": style,
                    "fill_level_matches": matches,
                    "first_linear_cell": first_linear,
                    "screen_xy": [first_linear % 32, first_linear // 32],
                    "tilemap_entries": [f"0x{entry:04X}" for entry in entries],
                    "runtime_tile_ids": tile_ids,
                    "runtime_tile_sha256": [_sha256(tile) for tile in tile_data],
                    "full_bar_sha256": _sha256(full_bar),
                }
            )

    parent_records = []
    parent_hash_counts: Counter[str] = Counter()
    for layer in layers:
        checkpoint = layer["checkpoint"]
        for content in layer["unmatched_nonfont_contents"]:
            ranges = content["linear_cell_ranges"]
            positions = [
                linear
                for start, end in ranges
                for linear in range(start, end)
            ]
            if content["cell_count"] != len(positions):
                raise ValueError("parent unknown record cell count mismatch")
            for linear in positions:
                match = cells.get((checkpoint, linear))
                if match is None or match["sha256"] != content["runtime_tile_sha256"]:
                    raise ValueError("parent unknown tile is not generated bar content")
                parent_hash_counts[match["sha256"]] += 1
                parent_records.append(
                    {
                        "checkpoint": checkpoint,
                        "linear_cell": linear,
                        **match,
                    }
                )
    if (
        len(parent_records),
        len(parent_hash_counts),
        sum(parent_hash_counts.values()),
    ) != (181, 22, 181):
        raise ValueError("parent battle BG3 unknown denominator changed")

    generated_candidates: defaultdict[str, set[tuple[int, int, int]]] = defaultdict(set)
    for style in range(2):
        for fill_level in range(39):
            for tile_index in range(5):
                tile = family[style][fill_level][
                    tile_index * 32 : (tile_index + 1) * 32
                ]
                generated_candidates[_sha256(tile)].add(
                    (style, fill_level, tile_index)
                )
    coverage = []
    for tile_hash, count in sorted(parent_hash_counts.items()):
        coverage.append(
            {
                "runtime_tile_sha256": tile_hash,
                "parent_cell_count": count,
                "generated_candidates": [
                    {
                        "style": style,
                        "fill_level": fill_level,
                        "tile_index": tile_index,
                    }
                    for style, fill_level, tile_index in sorted(
                        generated_candidates[tile_hash]
                    )
                ],
            }
        )
    return {
        "checkpoint_count": len(layers),
        "bar_count": len(bars),
        "full_bar_tile_count": len(bars) * 5,
        "parent_unknown_record_count": len(parent_records),
        "parent_unknown_cell_count": len(parent_records),
        "parent_unknown_distinct_hash_count": len(parent_hash_counts),
        "exact_generated_unknown_cell_count": len(parent_records),
        "exact_generated_unknown_distinct_hash_count": len(parent_hash_counts),
        "unmatched_unknown_cell_count": 0,
        "fill_level_distribution": [
            {
                "style": style,
                "fill_level": fill_level,
                "bar_count": count,
            }
            for (style, fill_level), count in sorted(
                Counter(
                    (bar["style"], bar["fill_level_matches"][0]) for bar in bars
                ).items()
            )
        ],
        "hash_coverage": coverage,
        "bars": bars,
    }


def _build_payload(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    rom = _require_hash(root / ROM_RELATIVE, ROM_SHA256, "base ROM")
    parent_bytes = _require_hash(root / PARENT_RELATIVE, PARENT_SHA256, "initializer")
    _require_hash(
        root / PARENT_MANIFEST_RELATIVE,
        PARENT_MANIFEST_SHA256,
        "initializer manifest",
    )
    overview_bytes = _require_hash(
        root / OVERVIEW_RELATIVE, OVERVIEW_SHA256, "overview artifact"
    )
    _require_hash(
        root / OVERVIEW_MANIFEST_RELATIVE,
        OVERVIEW_MANIFEST_SHA256,
        "overview manifest",
    )
    parent = json.loads(parent_bytes)
    overview = json.loads(overview_bytes)
    layers = _battle_layers(parent)
    templates, palette, checkpoints, states = _load_sources(root, layers)
    family = [
        [generate_bar(templates[style], style, level) for level in range(39)]
        for style in range(2)
    ]
    all_bars = b"".join(bar for style in family for bar in style)
    source_templates = b"".join(templates)
    preview = _render_family(family, palette)
    runtime = _runtime_binding(layers, states, family, checkpoints)

    for address in DIRECT_CALLS:
        offset = address - 0x08000000
        first, second = struct.unpack_from("<HH", rom, offset)
        if decode_thumb_bl(address, first, second) != 0x08068370:
            raise ValueError(f"direct call target changed at {_address(address)}")

    baseline = overview["parent_unmatched_resolution"]["visible_resource_domain"][
        "effective_remaining"
    ]
    expected_baseline = {
        "global_visible_resource_unmatched_cell_count": 181,
        "global_visible_resource_unmatched_distinct_hash_count": 22,
    }
    if {
        key: baseline[key] for key in expected_baseline
    } != expected_baseline:
        raise ValueError("overview visible-resource denominator changed")

    files = {
        "source-templates.4bpp.bin": source_templates,
        "generated-family.4bpp.bin": all_bars,
        "runtime-palette-bank13.bgr555.bin": palette,
        "battle-status-bars.png": preview,
    }
    implementation = {
        "exporter_sha256": _sha256(Path(__file__).read_bytes()),
        "verifier_sha256": _sha256(
            (root / "tools/verify_battle_status_bars.py").read_bytes()
        ),
        "test_sha256": _sha256(
            (root / "tests/test_export_battle_status_bars.py").read_bytes()
        ),
    }
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "implementation": implementation,
        "rom": {"file": ROM_RELATIVE.as_posix(), "sha256": ROM_SHA256},
        "generator": {
            "code": _code_record(
                rom, *GENERATOR_RANGE, GENERATOR_SHA256
            ),
            "full_object": _code_record(
                rom, *FULL_OBJECT_RANGE, FULL_OBJECT_SHA256
            ),
            "tail_literal_pool": _code_record(
                rom, *LITERAL_POOL_RANGE, LITERAL_POOL_SHA256
            ),
            "direct_calls": [_address(address) for address in DIRECT_CALLS],
            "callers": [
                _code_record(rom, start, end, sha)
                for start, end, sha in CALLER_RANGES
            ],
            "runtime_globals": {
                "graphics_base_pointer": _address(GRAPHICS_BASE_POINTER),
                "screenblock_pointer": "0x0201BD50",
                "template_base_pointer": _address(TEMPLATE_BASE_POINTER),
                "work_tiles": _address(WORK_TILES),
            },
            "literals": {
                "palette_lz77": "0x0809C8B0",
                "palette_work": "0x02002880",
                "palette_selector": "0x0201BD5C",
                "template_base_pointer": _address(TEMPLATE_BASE_POINTER),
                "work_tiles": _address(WORK_TILES),
                "graphics_base_pointer": _address(GRAPHICS_BASE_POINTER),
            },
            "formula": {
                "fill_level": "floor(38 * numerator / denominator)",
                "fill_level_storage": "unsigned 8-bit result",
                "domain": "style in {0,1}; fill_level in [0,38]",
                "output": "five consecutive 8x8 4bpp tiles",
                "interior_width_pixels": 38,
            },
            "copy_route": {
                "template_to_work": (
                    "*0x0201BD54 + (24 + style * 5) * 32 -> "
                    "0x0201BD84, 160 bytes"
                ),
                "work_to_vram": (
                    "0x0201BD84 + tile_index * 32 -> "
                    "*0x0201BD48 + dynamic_tile_id * 32"
                ),
                "tilemap_entry": "dynamic_tile_id | 0xD000",
                "tilemap_destination": (
                    "record+0x1E+2*((y+1)*record.width+(x+1+tile_index))"
                ),
                "hardware_screenblock": _address(SCREEN_BASE),
            },
        },
        "generated": {
            "style_count": 2,
            "fill_level_count": 39,
            "tiles_per_bar": 5,
            "bytes_per_bar": BAR_BYTES,
            "templates": {
                "file": "source-templates.4bpp.bin",
                "size": len(source_templates),
                "sha256": _sha256(source_templates),
                "style_sha256": [_sha256(item) for item in templates],
                "initializer_tile_ranges": [[24, 29], [29, 34]],
            },
            "family": {
                "file": "generated-family.4bpp.bin",
                "size": len(all_bars),
                "sha256": _sha256(all_bars),
                "order": "style 0 levels 0..38, then style 1 levels 0..38",
            },
            "palette": {
                "file": "runtime-palette-bank13.bgr555.bin",
                "size": len(palette),
                "sha256": _sha256(palette),
                "runtime_address": _address(PALETTE_ADDRESS),
                "palette_bank": 13,
            },
            "contact_sheet": {
                "file": "battle-status-bars.png",
                "size": len(preview),
                "sha256": _sha256(preview),
                "dimensions_pixels": [80, 312],
                "layout": "style columns, fill-level rows",
                "transparent_palette_index": 0,
                "encoder": "canonical-indexed-png-stored-deflate-v1",
            },
        },
        "runtime_binding": runtime,
        "parent_visible_resource_resolution": {
            "parents": {
                "initializer_artifact": PARENT_RELATIVE.as_posix(),
                "initializer_artifact_sha256": PARENT_SHA256,
                "initializer_manifest": PARENT_MANIFEST_RELATIVE.as_posix(),
                "initializer_manifest_sha256": PARENT_MANIFEST_SHA256,
                "overview_artifact": OVERVIEW_RELATIVE.as_posix(),
                "overview_artifact_sha256": OVERVIEW_SHA256,
                "overview_manifest": OVERVIEW_MANIFEST_RELATIVE.as_posix(),
                "overview_manifest_sha256": OVERVIEW_MANIFEST_SHA256,
            },
            "baseline": expected_baseline,
            "resolved": {
                "cell_count": 181,
                "distinct_hash_count": 22,
                "classification": "generated_battle_status_bar_content",
            },
            "remaining": {
                "global_visible_resource_unmatched_cell_count": 0,
                "global_visible_resource_unmatched_distinct_hash_count": 0,
            },
        },
        "scope": SCOPE,
    }
    payload_bytes = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    files[PAYLOAD_NAME] = payload_bytes
    return payload, files


def _promotion(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {
            relative: _sha256(data) for relative, data in sorted(files.items())
        },
        "source": {
            "rom_sha256": ROM_SHA256,
            "checkpoint_count": payload["runtime_binding"]["checkpoint_count"],
            "generator_gba_address": "0x08068370",
        },
        "producer": {
            "command": [
                "python3",
                "tools/export_battle_status_bars.py",
                "--root",
                ".",
                "--output-dir",
                "artifacts/battle-status-bars-v1",
            ],
            **payload["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_battle_status_bars.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/battle-status-bars-v1",
            ],
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                "exact_generated_unknown_cell_count": 181,
                "errors": [],
            },
        },
    }


def validate_output_target(root: Path, output: Path) -> Path:
    root = root.resolve()
    requested = output.expanduser()
    if requested.is_symlink():
        raise ValueError("output directory must not be a symbolic link")
    target = requested.resolve()
    if target == root or target in root.parents:
        raise ValueError("output directory must not be the repository or its ancestor")
    if target.exists():
        if not target.is_dir():
            raise ValueError("existing output target is not a directory")
        try:
            children = list(target.iterdir())
            if any(path.is_symlink() or not path.is_file() for path in children):
                raise ValueError("existing artifact contains non-file entries")
            if {path.name for path in children} != EXPECTED_FILES | {
                "manifest.json"
            }:
                raise ValueError("existing artifact file inventory mismatch")
            existing = json.loads(
                (target / "manifest.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as error:
            raise ValueError("refusing to replace output not owned by this artifact") from error
        if (
            existing.get("schema") != "git-artifact-promotion-v1"
            or existing.get("artifact_schema") != SCHEMA
            or existing.get("artifact_status") != "accepted"
            or set(existing.get("files", {})) != EXPECTED_FILES
        ):
            raise ValueError("refusing to replace output not owned by this artifact")
        for relative, expected in existing["files"].items():
            if _sha256((target / relative).read_bytes()) != expected:
                raise ValueError("refusing to replace artifact with invalid file hashes")
    return target


def _replace_output(
    output: Path, files: dict[str, bytes], manifest: dict[str, Any]
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent)
    )
    backup: Path | None = None
    try:
        for relative, data in sorted(files.items()):
            path = temporary / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if output.exists():
            backup = output.parent / f".{output.name}.backup-{uuid.uuid4().hex}"
            output.rename(backup)
        try:
            os.replace(temporary, output)
        except BaseException:
            if backup is not None and backup.exists() and not output.exists():
                backup.rename(output)
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists() and output.exists():
            shutil.rmtree(backup)


def export_artifact(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    payload, files = _build_payload(root)
    output = validate_output_target(root, Path(output_dir))
    _replace_output(output, files, _promotion(payload, files))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/battle-status-bars-v1"),
    )
    args = parser.parse_args()
    output = args.output_dir
    if not output.is_absolute():
        output = args.root / output
    payload = export_artifact(args.root, output)
    print(
        json.dumps(
            {
                "checkpoint_count": payload["runtime_binding"]["checkpoint_count"],
                "bar_count": payload["runtime_binding"]["bar_count"],
                "exact_generated_unknown_cell_count": payload["runtime_binding"][
                    "exact_generated_unknown_cell_count"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
