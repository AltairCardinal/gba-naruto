#!/usr/bin/env python3
"""Independently verify the generated battle status-bar artifact."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import struct
from typing import Any
import zlib

from PIL import Image


SCHEMA = "battle-status-bars-v1"
VERIFY_SCHEMA = "battle-status-bars-verification-v1"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PARENT_SHA256 = "c096e70c033f804548446272c47d43bfefa72eed173841e152c630c5436efba8"
PARENT_MANIFEST_SHA256 = (
    "8fc7c3ea449b480c5065a97e70d0f6c5c0fa30a0dc3f942931f6be86264337a4"
)
OVERVIEW_SHA256 = "b4ac97c3bc534d6932b9d189d58a31fe7986c5c9f3557f590fba0fdd839a8b6d"
OVERVIEW_MANIFEST_SHA256 = (
    "cd7c16abcd865827ea35fc7014e13b1681b69a7e17ecf45daa0a1f9a82be931e"
)
EXPECTED_FILES = {
    "source-templates.4bpp.bin",
    "generated-family.4bpp.bin",
    "runtime-palette-bank13.bgr555.bin",
    "battle-status-bars.png",
    "battle-status-bars.json",
}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
STATE_SIZE = 0x61000
DIRECT_CALLS = (0x0806F0D6, 0x0806F0EC, 0x0807A83C, 0x0807A8A6)
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


def _png_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("checkpoint is not a PNG")
    chunks = []
    cursor = 8
    while cursor < len(data):
        if cursor + 12 > len(data):
            raise ValueError("truncated PNG chunk")
        size = struct.unpack_from(">I", data, cursor)[0]
        tag = data[cursor + 4 : cursor + 8]
        start = cursor + 8
        end = start + size
        if end + 4 > len(data):
            raise ValueError("truncated PNG payload")
        payload = data[start:end]
        stored = struct.unpack_from(">I", data, end)[0]
        if zlib.crc32(tag + payload) & 0xFFFFFFFF != stored:
            raise ValueError("PNG CRC mismatch")
        chunks.append((tag, payload))
        cursor = end + 4
        if tag == b"IEND":
            if cursor != len(data):
                raise ValueError("data after PNG IEND")
            break
    if not chunks or chunks[-1][0] != b"IEND":
        raise ValueError("PNG lacks IEND")
    return chunks


def _state(path: Path) -> bytes:
    payloads = [
        payload for tag, payload in _png_chunks(path.read_bytes()) if tag == b"gbAs"
    ]
    if len(payloads) != 1:
        raise ValueError("checkpoint must contain one gbAs chunk")
    decoder = zlib.decompressobj()
    data = decoder.decompress(payloads[0], STATE_SIZE + 1)
    data += decoder.flush()
    if (
        not decoder.eof
        or decoder.unused_data
        or decoder.unconsumed_tail
        or len(data) != STATE_SIZE
    ):
        raise ValueError("invalid checkpoint state payload")
    version = struct.unpack_from("<I", data, 0)[0]
    if not 0x01000000 <= version <= 0x0100000B:
        raise ValueError("unsupported checkpoint version")
    return data


def _read_memory(state: bytes, address: int, size: int) -> bytes:
    regions = (
        (0x04000000, 0x00400, 0x00400),
        (0x05000000, 0x00400, 0x00800),
        (0x07000000, 0x00400, 0x00C00),
        (0x06000000, 0x18000, 0x01000),
        (0x03000000, 0x08000, 0x19000),
        (0x02000000, 0x40000, 0x21000),
    )
    for base, length, offset in regions:
        relative = address - base
        if 0 <= relative and relative + size <= length:
            return state[offset + relative : offset + relative + size]
    raise ValueError(f"memory read outside checkpoint: 0x{address:08X}+0x{size:X}")


def _u32(state: bytes, address: int) -> int:
    return struct.unpack("<I", _read_memory(state, address, 4))[0]


def _decode_bl(rom: bytes, address: int) -> int | None:
    offset = address - 0x08000000
    first, second = struct.unpack_from("<HH", rom, offset)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    high = first & 0x07FF
    if high & 0x0400:
        high -= 0x0800
    return (address + 4 + (high << 12) + ((second & 0x07FF) << 1)) & 0xFFFFFFFF


def _bar(template: bytes, style: int, level: int) -> bytes:
    if len(template) != 160 or style not in (0, 1) or level not in range(39):
        raise ValueError("invalid independent generator input")
    data = bytearray(template)
    pointer = 4
    for column in range(1, 39):
        values = None
        if column < level:
            if column == 1:
                values = (
                    (0x32, 0xA3, 0x93)
                    if style == 0
                    else (0x32, 0x63, 0x53)
                )
            elif column % 2 == 0:
                values = (
                    (0xAA, 0x99, 0x88)
                    if style == 0
                    else (0x66, 0x55, 0x44)
                )
        elif column == level:
            if column == 1:
                values = (
                    (0x32, 0xA3, 0x93)
                    if style == 0
                    else (0x32, 0x63, 0x53)
                )
            elif column == 38:
                values = (
                    (0x12, 0x1A, 0x19)
                    if style == 0
                    else (0x12, 0x16, 0x15)
                )
            elif column % 2:
                values = (
                    (0xBA, 0xA9, 0x98)
                    if style == 0
                    else (0x76, 0x65, 0x54)
                )
            else:
                values = (
                    (0xBB, 0xBA, 0xB9)
                    if style == 0
                    else (0x77, 0x76, 0x75)
                )
        else:
            if column == 1:
                values = (0x32, 0xB3, 0xB3)
            elif column == 38:
                values = (0x12, 0x1B, 0x1B)
            elif column % 2 == 0:
                fill = 0xBB if style == 0 else 0x77
                values = (fill, fill, fill)
            elif column - 1 == level:
                values = (
                    (0xBB, 0xBA, 0xB9)
                    if style == 0
                    else (0xBB, 0xB6, 0xB5)
                )
        if values is not None:
            first, second, third = values
            data[pointer] = data[pointer + 20] = first
            data[pointer + 4] = data[pointer + 16] = second
            data[pointer + 8] = data[pointer + 12] = third
        if column % 2:
            pointer += 1
            if column % 8 == 7:
                pointer += 28
    return bytes(data)


def _family(templates: bytes) -> tuple[list[list[bytes]], bytes]:
    if len(templates) != 320:
        raise ValueError("source template size mismatch")
    split = (templates[:160], templates[160:])
    generated = [
        [_bar(split[style], style, level) for level in range(39)]
        for style in range(2)
    ]
    flat = b"".join(bar for style in generated for bar in style)
    if len({_sha256(bar) for style in generated for bar in style}) != 78:
        raise ValueError("generated full-bar family is not unique")
    return generated, flat


def _preview(path: Path, family: list[list[bytes]], palette: bytes) -> None:
    expected = bytearray(80 * 312)
    for style in range(2):
        for level in range(39):
            bar = family[style][level]
            for tile_index in range(5):
                tile = bar[tile_index * 32 : (tile_index + 1) * 32]
                for y in range(8):
                    for x in range(8):
                        packed = tile[y * 4 + x // 2]
                        expected[
                            (level * 8 + y) * 80
                            + style * 40
                            + tile_index * 8
                            + x
                        ] = (packed >> (4 * (x & 1))) & 0x0F
    with Image.open(path) as image:
        image.load()
        if image.mode != "P" or image.size != (80, 312):
            raise ValueError("contact sheet must be indexed 80x312")
        if image.info.get("transparency") != 0:
            raise ValueError("contact sheet transparency index mismatch")
        if image.tobytes() != bytes(expected):
            raise ValueError("contact sheet pixels differ from generated family")
        rgb = []
        for color in struct.unpack("<16H", palette):
            for shift in (0, 5, 10):
                value = (color >> shift) & 0x1F
                rgb.append((value << 3) | (value >> 2))
        if image.getpalette()[:48] != rgb:
            raise ValueError("contact sheet palette differs from runtime palette")


def _artifact_inventory(artifact: Path) -> dict[str, Any]:
    if artifact.is_symlink() or not artifact.is_dir():
        raise ValueError("artifact is not a normal directory")
    paths = [
        path for path in artifact.rglob("*") if path.is_file() or path.is_symlink()
    ]
    if any(path.is_symlink() for path in paths):
        raise ValueError("artifact contains symbolic links")
    relatives = {path.relative_to(artifact).as_posix() for path in paths}
    if relatives != EXPECTED_FILES | {"manifest.json"}:
        raise ValueError(f"unexpected artifact files: {sorted(relatives)}")
    manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != SCHEMA
        or manifest.get("artifact_status") != "accepted"
    ):
        raise ValueError("promotion metadata mismatch")
    if set(manifest.get("files", {})) != EXPECTED_FILES:
        raise ValueError("promotion file inventory mismatch")
    for relative, expected in manifest["files"].items():
        if _sha256((artifact / relative).read_bytes()) != expected:
            raise ValueError(f"promotion hash mismatch: {relative}")
    return manifest


def _code_record(rom: bytes, start: int, end: int) -> dict[str, Any]:
    data = rom[start:end]
    return {
        "gba_start": f"0x{0x08000000 + start:08X}",
        "gba_end_exclusive": f"0x{0x08000000 + end:08X}",
        "size": len(data),
        "sha256": _sha256(data),
    }


def _runtime_expected(
    root: Path,
    layers: list[dict[str, Any]],
    family: list[list[bytes]],
) -> dict[str, Any]:
    bars = []
    cells: dict[tuple[str, int], dict[str, Any]] = {}
    for layer in layers:
        name = layer["checkpoint"]
        relative = Path("artifacts/runtime-checkpoints") / name
        raw = (root / relative).read_bytes()
        state = _state(root / relative)
        if (
            _u32(state, 0x0201BD48),
            _u32(state, 0x0201BD50),
            _u32(state, 0x0201BD54),
        ) != (0x0600C000, 0x06001800, 0x0600F800):
            raise ValueError(f"{name} runtime graphics globals changed")
        starts = [
            start
            for content in layer["unmatched_nonfont_contents"]
            for start, _ in content["linear_cell_ranges"]
        ]
        first = 501 if min(starts) < 544 else 565
        tilemap = struct.unpack("<1024H", _read_memory(state, 0x06001800, 2048))
        for style, linear in ((0, first), (1, first + 32)):
            entries = list(tilemap[linear : linear + 5])
            if any(entry >> 12 != 13 or entry & 0x0C00 for entry in entries):
                raise ValueError(f"{name} bar tilemap attributes changed")
            ids = [entry & 0x03FF for entry in entries]
            tile_data = [
                _read_memory(state, 0x0600C000 + tile_id * 32, 32)
                for tile_id in ids
            ]
            whole = b"".join(tile_data)
            matches = [
                level for level in range(39) if family[style][level] == whole
            ]
            if len(matches) != 1:
                raise ValueError(f"{name} bar match is not unique")
            bar_index = len(bars)
            for tile_index, tile in enumerate(tile_data):
                cells[(name, linear + tile_index)] = {
                    "bar_index": bar_index,
                    "style": style,
                    "fill_level": matches[0],
                    "tile_index": tile_index,
                    "sha256": _sha256(tile),
                }
            bars.append(
                {
                    "checkpoint": relative.as_posix(),
                    "checkpoint_sha256": _sha256(raw),
                    "parent_layer_key": layer["parent_layer_key"],
                    "parent_layer_sha256": layer["parent_layer_sha256"],
                    "style": style,
                    "fill_level_matches": matches,
                    "first_linear_cell": linear,
                    "screen_xy": [linear % 32, linear // 32],
                    "tilemap_entries": [f"0x{entry:04X}" for entry in entries],
                    "runtime_tile_ids": ids,
                    "runtime_tile_sha256": [_sha256(tile) for tile in tile_data],
                    "full_bar_sha256": _sha256(whole),
                }
            )
    records = []
    counts: Counter[str] = Counter()
    for layer in layers:
        name = layer["checkpoint"]
        for content in layer["unmatched_nonfont_contents"]:
            positions = [
                linear
                for start, end in content["linear_cell_ranges"]
                for linear in range(start, end)
            ]
            if len(positions) != content["cell_count"]:
                raise ValueError("parent content count mismatch")
            for linear in positions:
                match = cells.get((name, linear))
                if match is None or match["sha256"] != content["runtime_tile_sha256"]:
                    raise ValueError("parent unknown record is not generated content")
                records.append((name, linear, match))
                counts[match["sha256"]] += 1
    candidates: defaultdict[str, set[tuple[int, int, int]]] = defaultdict(set)
    for style in range(2):
        for level in range(39):
            for tile_index in range(5):
                tile = family[style][level][
                    tile_index * 32 : (tile_index + 1) * 32
                ]
                candidates[_sha256(tile)].add((style, level, tile_index))
    coverage = [
        {
            "runtime_tile_sha256": tile_hash,
            "parent_cell_count": count,
            "generated_candidates": [
                {
                    "style": style,
                    "fill_level": level,
                    "tile_index": tile_index,
                }
                for style, level, tile_index in sorted(candidates[tile_hash])
            ],
        }
        for tile_hash, count in sorted(counts.items())
    ]
    return {
        "checkpoint_count": len(layers),
        "bar_count": len(bars),
        "full_bar_tile_count": len(bars) * 5,
        "parent_unknown_record_count": len(records),
        "parent_unknown_cell_count": len(records),
        "parent_unknown_distinct_hash_count": len(counts),
        "exact_generated_unknown_cell_count": len(records),
        "exact_generated_unknown_distinct_hash_count": len(counts),
        "unmatched_unknown_cell_count": 0,
        "fill_level_distribution": [
            {"style": style, "fill_level": level, "bar_count": count}
            for (style, level), count in sorted(
                Counter(
                    (bar["style"], bar["fill_level_matches"][0]) for bar in bars
                ).items()
            )
        ],
        "hash_coverage": coverage,
        "bars": bars,
    }


def _verify(root: Path, artifact: Path) -> dict[str, Any]:
    manifest = _artifact_inventory(artifact)
    payload = json.loads(
        (artifact / "battle-status-bars.json").read_text(encoding="utf-8")
    )
    if payload.get("schema") != SCHEMA:
        raise ValueError("payload schema mismatch")
    if set(payload) != {
        "schema",
        "implementation",
        "rom",
        "generator",
        "generated",
        "runtime_binding",
        "parent_visible_resource_resolution",
        "scope",
    }:
        raise ValueError("payload field inventory mismatch")
    implementations = {
        "exporter_sha256": _sha256(
            (root / "tools/export_battle_status_bars.py").read_bytes()
        ),
        "verifier_sha256": _sha256(Path(__file__).read_bytes()),
        "test_sha256": _sha256(
            (root / "tests/test_export_battle_status_bars.py").read_bytes()
        ),
    }
    if payload.get("implementation") != implementations:
        raise ValueError("implementation hashes mismatch")
    if any(
        manifest.get("producer", {}).get(key) != value
        for key, value in implementations.items()
    ):
        raise ValueError("promotion producer hash mismatch")
    expected_manifest_semantics = {
        "source": {
            "rom_sha256": ROM_SHA256,
            "checkpoint_count": 30,
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
            **implementations,
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
            "verifier_sha256": implementations["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                "exact_generated_unknown_cell_count": 181,
                "errors": [],
            },
        },
    }
    for key, expected in expected_manifest_semantics.items():
        if manifest.get(key) != expected:
            raise ValueError(f"promotion {key} semantics mismatch")

    rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256 or payload.get("rom") != {
        "file": "rom/base.gba",
        "sha256": ROM_SHA256,
    }:
        raise ValueError("ROM binding mismatch")
    generator = payload.get("generator", {})
    if generator.get("code") != _code_record(rom, 0x068370, 0x068642):
        raise ValueError("generator code binding mismatch")
    if generator.get("full_object") != _code_record(rom, 0x068370, 0x068660):
        raise ValueError("generator object binding mismatch")
    if generator.get("tail_literal_pool") != _code_record(
        rom, 0x068644, 0x068660
    ):
        raise ValueError("generator literal-pool binding mismatch")
    if [_decode_bl(rom, address) for address in DIRECT_CALLS] != [
        0x08068370
    ] * 4:
        raise ValueError("generator direct-call target mismatch")
    if generator.get("direct_calls") != [
        f"0x{address:08X}" for address in DIRECT_CALLS
    ]:
        raise ValueError("generator direct-call inventory mismatch")
    if generator.get("callers") != [
        _code_record(rom, 0x06ED88, 0x06F0FC),
        _code_record(rom, 0x07A34C, 0x07AA8C),
    ]:
        raise ValueError("generator caller bindings mismatch")
    if generator.get("runtime_globals") != {
        "graphics_base_pointer": "0x0201BD48",
        "screenblock_pointer": "0x0201BD50",
        "template_base_pointer": "0x0201BD54",
        "work_tiles": "0x0201BD84",
    }:
        raise ValueError("generator runtime-global metadata mismatch")
    if generator.get("formula") != {
        "fill_level": "floor(38 * numerator / denominator)",
        "fill_level_storage": "unsigned 8-bit result",
        "domain": "style in {0,1}; fill_level in [0,38]",
        "output": "five consecutive 8x8 4bpp tiles",
        "interior_width_pixels": 38,
    }:
        raise ValueError("generator formula mismatch")
    if generator.get("literals") != {
        "palette_lz77": "0x0809C8B0",
        "palette_work": "0x02002880",
        "palette_selector": "0x0201BD5C",
        "template_base_pointer": "0x0201BD54",
        "work_tiles": "0x0201BD84",
        "graphics_base_pointer": "0x0201BD48",
    }:
        raise ValueError("generator literal metadata mismatch")
    if generator.get("copy_route") != {
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
        "hardware_screenblock": "0x06001800",
    }:
        raise ValueError("generator copy-route metadata mismatch")
    if set(generator) != {
        "code",
        "full_object",
        "tail_literal_pool",
        "direct_calls",
        "callers",
        "runtime_globals",
        "literals",
        "formula",
        "copy_route",
    }:
        raise ValueError("generator field inventory mismatch")
    if payload.get("scope") != SCOPE:
        raise ValueError("scope mismatch")

    templates = (artifact / "source-templates.4bpp.bin").read_bytes()
    palette = (artifact / "runtime-palette-bank13.bgr555.bin").read_bytes()
    if (
        _sha256(templates[:160]),
        _sha256(templates[160:]),
        _sha256(palette),
    ) != (
        "cacf8c0f71ff964ddd962a02ad4f5a2713dd0dc9e43f1adc5d3f690f72f5b21f",
        "d0eda4d1836693671205f7c9cfb82abed04167600ecf498fdcbf2b98608791cd",
        "82f1c93a86b077a17e05e44c28d7f6522ff69542a6356487ce25a45b61a8a9d2",
    ):
        raise ValueError("source template or palette hash mismatch")
    family, flat = _family(templates)
    if (artifact / "generated-family.4bpp.bin").read_bytes() != flat:
        raise ValueError("generated family differs from independent reconstruction")
    generated = payload.get("generated", {})
    expected_records = {
        "templates": ("source-templates.4bpp.bin", templates),
        "family": ("generated-family.4bpp.bin", flat),
        "palette": ("runtime-palette-bank13.bgr555.bin", palette),
        "contact_sheet": (
            "battle-status-bars.png",
            (artifact / "battle-status-bars.png").read_bytes(),
        ),
    }
    if (
        generated.get("style_count"),
        generated.get("fill_level_count"),
        generated.get("tiles_per_bar"),
        generated.get("bytes_per_bar"),
    ) != (2, 39, 5, 160):
        raise ValueError("generated-family dimensions mismatch")
    for key, (relative, data) in expected_records.items():
        record = generated.get(key, {})
        if (
            record.get("file"),
            record.get("size"),
            record.get("sha256"),
        ) != (relative, len(data), _sha256(data)):
            raise ValueError(f"generated {key} metadata mismatch")
    expected_generated = {
        "style_count": 2,
        "fill_level_count": 39,
        "tiles_per_bar": 5,
        "bytes_per_bar": 160,
        "templates": {
            "file": "source-templates.4bpp.bin",
            "size": 320,
            "sha256": _sha256(templates),
            "style_sha256": [
                _sha256(templates[:160]),
                _sha256(templates[160:]),
            ],
            "initializer_tile_ranges": [[24, 29], [29, 34]],
        },
        "family": {
            "file": "generated-family.4bpp.bin",
            "size": 12480,
            "sha256": _sha256(flat),
            "order": "style 0 levels 0..38, then style 1 levels 0..38",
        },
        "palette": {
            "file": "runtime-palette-bank13.bgr555.bin",
            "size": 32,
            "sha256": _sha256(palette),
            "runtime_address": "0x050001A0",
            "palette_bank": 13,
        },
        "contact_sheet": {
            "file": "battle-status-bars.png",
            "size": len(expected_records["contact_sheet"][1]),
            "sha256": _sha256(expected_records["contact_sheet"][1]),
            "dimensions_pixels": [80, 312],
            "layout": "style columns, fill-level rows",
            "transparent_palette_index": 0,
            "encoder": "canonical-indexed-png-stored-deflate-v1",
        },
    }
    if generated != expected_generated:
        raise ValueError("generated artifact metadata mismatch")
    _preview(artifact / "battle-status-bars.png", family, palette)

    parent_path = (
        root / "artifacts/initializer-resource-pack-v1/initializer-resource-pack.json"
    )
    parent_manifest = root / "artifacts/initializer-resource-pack-v1/manifest.json"
    overview_path = (
        root / "artifacts/overview-gradient-overlay-v1/overview-gradient-overlay.json"
    )
    overview_manifest = root / "artifacts/overview-gradient-overlay-v1/manifest.json"
    if (
        _sha256(parent_path.read_bytes()),
        _sha256(parent_manifest.read_bytes()),
        _sha256(overview_path.read_bytes()),
        _sha256(overview_manifest.read_bytes()),
    ) != (
        PARENT_SHA256,
        PARENT_MANIFEST_SHA256,
        OVERVIEW_SHA256,
        OVERVIEW_MANIFEST_SHA256,
    ):
        raise ValueError("parent artifact hash mismatch")
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    overview = json.loads(overview_path.read_text(encoding="utf-8"))
    layers = sorted(
        [
            layer
            for layer in parent["runtime_binding"]["layers"]
            if layer.get("unmatched_nonfont_contents")
            and layer.get("checkpoint") != "alternate-character-overview.ss9"
        ],
        key=lambda item: item["checkpoint"],
    )
    if len(layers) != 30 or any(layer["bg_index"] != 3 for layer in layers):
        raise ValueError("battle BG3 parent-layer inventory mismatch")
    for layer in layers:
        state = _state(
            root / "artifacts/runtime-checkpoints" / layer["checkpoint"]
        )
        if (
            _read_memory(state, 0x0600FB00, 160) != templates[:160]
            or _read_memory(state, 0x0600FBA0, 160) != templates[160:]
            or _read_memory(state, 0x050001A0, 32) != palette
        ):
            raise ValueError("checkpoint source resources mismatch")
    runtime = _runtime_expected(root, layers, family)
    if payload.get("runtime_binding") != runtime:
        raise ValueError("runtime bar binding mismatch")
    baseline = overview["parent_unmatched_resolution"]["visible_resource_domain"][
        "effective_remaining"
    ]
    expected_resolution = {
        "parents": {
            "initializer_artifact": (
                "artifacts/initializer-resource-pack-v1/initializer-resource-pack.json"
            ),
            "initializer_artifact_sha256": PARENT_SHA256,
            "initializer_manifest": (
                "artifacts/initializer-resource-pack-v1/manifest.json"
            ),
            "initializer_manifest_sha256": PARENT_MANIFEST_SHA256,
            "overview_artifact": (
                "artifacts/overview-gradient-overlay-v1/"
                "overview-gradient-overlay.json"
            ),
            "overview_artifact_sha256": OVERVIEW_SHA256,
            "overview_manifest": (
                "artifacts/overview-gradient-overlay-v1/manifest.json"
            ),
            "overview_manifest_sha256": OVERVIEW_MANIFEST_SHA256,
        },
        "baseline": {
            "global_visible_resource_unmatched_cell_count": 181,
            "global_visible_resource_unmatched_distinct_hash_count": 22,
        },
        "resolved": {
            "cell_count": 181,
            "distinct_hash_count": 22,
            "classification": "generated_battle_status_bar_content",
        },
        "remaining": {
            "global_visible_resource_unmatched_cell_count": 0,
            "global_visible_resource_unmatched_distinct_hash_count": 0,
        },
    }
    if {
        key: baseline[key] for key in expected_resolution["baseline"]
    } != expected_resolution["baseline"]:
        raise ValueError("overview baseline denominator mismatch")
    if payload.get("parent_visible_resource_resolution") != expected_resolution:
        raise ValueError("parent visible-resource resolution mismatch")
    return {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        "exact_generated_unknown_cell_count": 181,
        "errors": [],
    }


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    try:
        artifact = Path(artifact_dir)
        if artifact.is_symlink():
            raise ValueError("artifact path is a symbolic link")
        return _verify(Path(root).resolve(), artifact.resolve())
    except Exception as error:
        return {
            "schema": VERIFY_SCHEMA,
            "verified": False,
            "exact_generated_unknown_cell_count": 0,
            "errors": [str(error)],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/battle-status-bars-v1"),
    )
    args = parser.parse_args()
    artifact = args.artifact_dir
    if not artifact.is_absolute():
        artifact = args.root / artifact
    report = verify_artifact(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
