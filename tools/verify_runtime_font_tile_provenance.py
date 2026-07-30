#!/usr/bin/env python3
"""Independently rebuild and verify runtime-font-tile-provenance-v1."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import struct
import zlib


SCHEMA = "runtime-font-tile-provenance-v1"
VERIFY_SCHEMA = "runtime-font-tile-provenance-verification-v1"
PARENT_PAYLOAD = Path(
    "artifacts/runtime-layer-static-provenance-v1/"
    "runtime-layer-static-provenance.json"
)
PARENT_MANIFEST = Path(
    "artifacts/runtime-layer-static-provenance-v1/manifest.json"
)
FONT_MANIFEST = Path("artifacts/dialogue-font-v2/manifest.json")
ROM_PATH = Path("rom/base.gba")
PAYLOAD_NAME = "runtime-font-tile-provenance.json"
EXPANSION_PALETTE_GROUPS = (2, 3)
STATE_SIZE = 0x61000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SCOPE = {
    "all_parent_unidentified_layers_classified_for_font_content": True,
    "exact_nonblank_expanded_font_tile_content_complete": True,
    "ordered_sjis_vertical_pair_content_complete": True,
    "runtime_writer_identity_per_checkpoint_complete": False,
    "whole_bg_source_identity_complete": False,
    "nonfont_tile_source_identity_complete": False,
    "unicode_or_localized_character_semantics_complete": False,
    "all_game_visual_states_complete": False,
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_record_sha(record: dict) -> str:
    encoded = (
        json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    return _sha(encoded)


def _ranges(values: list[int]) -> list[list[int]]:
    unique = sorted(set(values))
    if not unique:
        return []
    result = []
    start = previous = unique[0]
    for value in unique[1:]:
        if value != previous + 1:
            result.append([start, previous + 1])
            start = value
        previous = value
    result.append([start, previous + 1])
    return result


def _state(path: Path) -> bytes:
    raw = path.read_bytes()
    if not raw.startswith(PNG_SIGNATURE):
        raise ValueError(f"{path.name}: invalid PNG signature")
    cursor = len(PNG_SIGNATURE)
    payloads = []
    while cursor < len(raw):
        if cursor + 12 > len(raw):
            raise ValueError(f"{path.name}: truncated PNG chunk")
        size = struct.unpack_from(">I", raw, cursor)[0]
        tag = raw[cursor + 4 : cursor + 8]
        start, end = cursor + 8, cursor + 8 + size
        if end + 4 > len(raw):
            raise ValueError(f"{path.name}: truncated PNG payload")
        payload = raw[start:end]
        stored_crc = struct.unpack_from(">I", raw, end)[0]
        if stored_crc != zlib.crc32(tag + payload) & 0xFFFFFFFF:
            raise ValueError(f"{path.name}: PNG CRC mismatch")
        if tag == b"gbAs":
            payloads.append(payload)
        cursor = end + 4
        if tag == b"IEND":
            break
    if cursor != len(raw) or len(payloads) != 1:
        raise ValueError(f"{path.name}: invalid savestate container")
    decoder = zlib.decompressobj()
    state = decoder.decompress(payloads[0], STATE_SIZE + 1) + decoder.flush()
    if (
        len(state) != STATE_SIZE
        or not decoder.eof
        or decoder.unused_data
        or decoder.unconsumed_tail
    ):
        raise ValueError(f"{path.name}: invalid gbAs payload")
    version = struct.unpack_from("<I", state, 0)[0]
    if not 0x01000000 <= version <= 0x0100000B:
        raise ValueError(f"{path.name}: unsupported state version")
    return state


def _memory(state: bytes, address: int, size: int) -> bytes:
    regions = (
        (0x04000000, 0x400, 0x400),
        (0x05000000, 0x400, 0x800),
        (0x06000000, 0x18000, 0x1000),
    )
    for base, length, offset in regions:
        relative = address - base
        if 0 <= relative and relative + size <= length:
            return state[offset + relative : offset + relative + size]
    raise ValueError(f"unsupported memory range 0x{address:08X}+0x{size:X}")


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _checkpoint(path: Path) -> tuple[dict, dict[str, bytes]]:
    state = _state(path)
    io = _memory(state, 0x04000000, 0x400)
    pram = _memory(state, 0x05000000, 0x400)
    vram = _memory(state, 0x06000000, 0x18000)
    dispcnt = _u16(io, 0)
    if dispcnt & 7 or dispcnt & 0x80:
        raise ValueError(f"{path.name}: expected visible Mode 0")
    if _u16(io, 0x4C):
        raise ValueError(f"{path.name}: unsupported nonzero MOSAIC")
    enabled = [index for index in range(4) if dispcnt & (1 << (8 + index))]
    backgrounds = []
    for index in range(4):
        control = _u16(io, 8 + index * 2)
        char_block = (control >> 2) & 3
        screen_block = (control >> 8) & 31
        size_code = (control >> 14) & 3
        width, height = ((32, 32), (64, 32), (32, 64), (64, 64))[
            size_code
        ]
        backgrounds.append(
            {
                "index": index,
                "enabled": index in enabled,
                "bgcnt": f"0x{control:04X}",
                "priority": control & 3,
                "char_base_block": char_block,
                "char_base_address": (
                    f"0x{0x06000000 + char_block * 0x4000:08X}"
                ),
                "mosaic": bool(control & (1 << 6)),
                "color_depth_bpp": 8 if control & 0x80 else 4,
                "screen_base_block": screen_block,
                "screen_base_address": (
                    f"0x{0x06000000 + screen_block * 0x800:08X}"
                ),
                "affine_wrap_bit": bool(control & (1 << 13)),
                "size_code": size_code,
                "width_pixels": width * 8,
                "height_pixels": height * 8,
                "hofs": _u16(io, 0x10 + index * 4) & 0x1FF,
                "vofs": _u16(io, 0x12 + index * 4) & 0x1FF,
            }
        )
    bg_palette = pram[:0x200]
    bg_vram = vram[:0x10000]
    state_id = _sha(io[:0x58] + bg_palette + bg_vram)
    return (
        {"state_id": state_id, "backgrounds": backgrounds},
        {"bg_vram": bg_vram},
    )


def _map_offset(
    screen_base: int,
    size: int,
    tile_x: int,
    tile_y: int,
) -> int:
    block_x = tile_x // 32
    block_y = tile_y // 32
    if size == 0:
        block = 0
    elif size == 1:
        block = block_x
    elif size == 2:
        block = block_y
    else:
        block = block_x + block_y * 2
    index = (tile_y % 32) * 32 + tile_x % 32
    return screen_base + block * 0x800 + index * 2


def _expand(source: bytes, palette_group: int) -> bytes:
    if not 0 <= palette_group <= 3:
        raise ValueError("palette group must fit two bits")
    base = palette_group << 2
    output = bytearray()
    for packed in source:
        values = [
            base | ((packed >> shift) & 3)
            for shift in (0, 2, 4, 6)
        ]
        output.extend(
            (
                values[0] | (values[1] << 4),
                values[2] | (values[3] << 4),
            )
        )
    return bytes(output)


def _font_sources(
    root: Path,
) -> tuple[dict, dict[bytes, list[dict]], dict[int, dict]]:
    manifest = json.loads((root / FONT_MANIFEST).read_text(encoding="utf-8"))
    rom = (root / ROM_PATH).read_bytes()
    if _sha(rom) != manifest["rom"]["sha256"]:
        raise ValueError("base ROM hash differs from dialogue-font-v2")
    sjis = {
        int(record["logical_index"]): record
        for record in manifest["sjis_glyphs"]
    }
    expanded: dict[bytes, list[dict]] = defaultdict(list)
    for expected_index, record in enumerate(manifest["physical_half_tiles"]):
        if int(record["index"]) != expected_index:
            raise ValueError("font physical half indices are not contiguous")
        offset = int(record["file_offset"])
        source = rom[offset : offset + 16]
        if len(source) != 16 or _sha(source) != record["sha256"]:
            raise ValueError(f"font half {expected_index} differs from ROM")
        for group in EXPANSION_PALETTE_GROUPS:
            expanded[_expand(source, group)].append(
                {
                    "physical_half_index": expected_index,
                    "source_half_sha256": record["sha256"],
                    "palette_group": group,
                    "lookup_branch": record["lookup_branch"],
                    "logical_index": int(record["logical_index"]),
                    "half_index": int(record["half_index"]),
                    "is_all_zero": bool(record["is_all_zero"]),
                }
            )
    return manifest, expanded, sjis


def _font_tile_group(
    tile_id: int,
    tile: bytes,
    positions: list[int],
    candidates: list[dict],
    char_base: int,
) -> dict:
    rows = [
        {
            "physical_half_index": item["physical_half_index"],
            "source_half_sha256": item["source_half_sha256"],
            "lookup_branch": item["lookup_branch"],
            "logical_index": item["logical_index"],
            "half_index": item["half_index"],
            "expansion_palette_group": item["palette_group"],
        }
        for item in candidates
        if not item["is_all_zero"]
    ]
    rows.sort(
        key=lambda item: (
            item["physical_half_index"],
            item["expansion_palette_group"],
        )
    )
    return {
        "runtime_tile_id": tile_id,
        "runtime_tile_address": f"0x{0x06000000 + char_base + tile_id * 32:08X}",
        "runtime_tile_sha256": _sha(tile),
        "cell_count": len(positions),
        "linear_cell_ranges": _ranges(positions),
        "candidate_count": len(rows),
        "candidates": rows,
    }


def _layer(
    root: Path,
    parent: dict,
    expanded: dict[bytes, list[dict]],
    sjis_by_logical: dict[int, dict],
    cache: dict[str, tuple[dict, dict[str, bytes]]],
) -> dict:
    relative = parent["checkpoint_paths"][0]
    if relative not in cache:
        cache[relative] = _checkpoint(root / relative)
    checkpoint, domains = cache[relative]
    if checkpoint["state_id"] != parent["state_id"]:
        raise ValueError(f"{relative}: state ID mismatch")
    background = next(
        item
        for item in checkpoint["backgrounds"]
        if item["index"] == parent["bg_index"]
    )
    for field in (
        "bgcnt",
        "color_depth_bpp",
        "char_base_address",
        "screen_base_address",
        "size_code",
    ):
        if background[field] != parent[field]:
            raise ValueError(f"{relative}: BG field {field} mismatch")
    if background["color_depth_bpp"] != 4:
        raise ValueError(f"{relative}: expected 4bpp")

    bg_vram = domains["bg_vram"]
    char_base = int(background["char_base_block"]) * 0x4000
    screen_base = int(background["screen_base_block"]) * 0x800
    size_code = int(background["size_code"])
    width, height = ((32, 32), (64, 32), (32, 64), (64, 64))[size_code]
    cells = []
    tilemap = bytearray()
    positions_by_tile: dict[int, list[int]] = defaultdict(list)
    tile_content: dict[int, tuple[bytes, list[dict]]] = {}
    blank_cells = []
    for y in range(height):
        row = []
        for x in range(width):
            offset = _map_offset(screen_base, size_code, x, y)
            entry_bytes = bg_vram[offset : offset + 2]
            if len(entry_bytes) != 2:
                raise ValueError(f"{relative}: tilemap outside VRAM")
            tilemap.extend(entry_bytes)
            entry = int.from_bytes(entry_bytes, "little")
            tile_id = entry & 0x3FF
            tile_offset = char_base + tile_id * 32
            tile = bg_vram[tile_offset : tile_offset + 32]
            if len(tile) != 32:
                raise ValueError(f"{relative}: graphics outside VRAM")
            candidates = list(expanded.get(tile, ()))
            nonblank = [item for item in candidates if not item["is_all_zero"]]
            linear = y * width + x
            if nonblank:
                positions_by_tile[tile_id].append(linear)
                previous = tile_content.setdefault(tile_id, (tile, nonblank))
                if previous != (tile, nonblank):
                    raise ValueError(f"{relative}: tile ID changed content")
            elif candidates:
                blank_cells.append(
                    {
                        "classification": "ambiguous_blank_font_content",
                        "position_tiles": [x, y],
                        "linear_cell_index": linear,
                        "runtime_tile_id": tile_id,
                        "runtime_tile_address": (
                            f"0x{0x06000000 + tile_offset:08X}"
                        ),
                        "runtime_tile_sha256": _sha(tile),
                        "tilemap_entry": f"0x{entry:04X}",
                        "candidate_count": len(candidates),
                        "expansion_palette_groups": sorted(
                            {item["palette_group"] for item in candidates}
                        ),
                    }
                )
            row.append(
                {
                    "entry": entry,
                    "tile_id": tile_id,
                    "tile": tile,
                    "candidates": candidates,
                    "nonblank_candidates": nonblank,
                }
            )
        cells.append(row)

    pairs = []
    pair_cells = set()
    for y in range(height - 1):
        for x in range(width):
            top = cells[y][x]
            bottom = cells[y + 1][x]
            if (top["entry"] | bottom["entry"]) & 0x0C00:
                continue
            top_palette = (top["entry"] >> 12) & 15
            if top_palette != ((bottom["entry"] >> 12) & 15):
                continue
            candidates = {}
            for top_candidate in top["nonblank_candidates"]:
                if (
                    top_candidate["lookup_branch"] != "sjis"
                    or top_candidate["half_index"] != 0
                ):
                    continue
                for bottom_candidate in bottom["candidates"]:
                    key = (
                        top_candidate["logical_index"],
                        top_candidate["palette_group"],
                        top_candidate["physical_half_index"],
                        bottom_candidate["physical_half_index"],
                    )
                    if (
                        bottom_candidate["lookup_branch"] == "sjis"
                        and bottom_candidate["half_index"] == 1
                        and bottom_candidate["logical_index"]
                        == top_candidate["logical_index"]
                        and bottom_candidate["palette_group"]
                        == top_candidate["palette_group"]
                    ):
                        candidates[key] = (top_candidate, bottom_candidate)
            if not candidates:
                continue
            pair_cells.update(((x, y), (x, y + 1)))
            selected = next(iter(candidates.values()))
            glyph = sjis_by_logical[selected[0]["logical_index"]]
            pairs.append(
                {
                    "position_tiles": [x, y],
                    "runtime_positions_tiles": [[x, y], [x, y + 1]],
                    "runtime_tile_ids": [top["tile_id"], bottom["tile_id"]],
                    "runtime_tile_id_delta": (
                        bottom["tile_id"] - top["tile_id"]
                    ),
                    "runtime_tilemap_entries": [
                        f"0x{top['entry']:04X}",
                        f"0x{bottom['entry']:04X}",
                    ],
                    "runtime_palette_bank": top_palette,
                    "runtime_top_tile_address": (
                        f"0x{0x06000000 + char_base + top['tile_id'] * 32:08X}"
                    ),
                    "runtime_bottom_tile_address": (
                        f"0x{0x06000000 + char_base + bottom['tile_id'] * 32:08X}"
                    ),
                    "runtime_top_tile_sha256": _sha(top["tile"]),
                    "runtime_bottom_tile_sha256": _sha(bottom["tile"]),
                    "flip_hv": [False, False],
                    "runtime_tilemap_flips": [
                        [False, False],
                        [False, False],
                    ],
                    "lookup_branch": "sjis",
                    "logical_index": int(glyph["logical_index"]),
                    "sjis_hex": glyph["sjis_hex"],
                    "source_pointer": glyph["source_pointer"],
                    "source_record_sha256": glyph["source_sha256"],
                    "source_physical_half_indices": [
                        selected[0]["physical_half_index"],
                        selected[1]["physical_half_index"],
                    ],
                    "source_half_indices": [0, 1],
                    "source_half_sha256s": [
                        selected[0]["source_half_sha256"],
                        selected[1]["source_half_sha256"],
                    ],
                    "expansion_palette_group": selected[0][
                        "palette_group"
                    ],
                    "candidate_count": len(candidates),
                }
            )
    exact_tiles = [
        _font_tile_group(
            tile_id,
            tile_content[tile_id][0],
            positions_by_tile[tile_id],
            tile_content[tile_id][1],
            char_base,
        )
        for tile_id in sorted(positions_by_tile)
    ]
    exact_count = sum(item["cell_count"] for item in exact_tiles)
    blank_count = len(blank_cells)
    return {
        "parent_layer_key": f"{parent['state_id']}:bg{parent['bg_index']}",
        "parent_layer_sha256": _canonical_record_sha(parent),
        "parent_classification": parent["classification"],
        "state_id": parent["state_id"],
        "checkpoint_paths": sorted(parent["checkpoint_paths"]),
        "bg_index": parent["bg_index"],
        "bgcnt": parent["bgcnt"],
        "color_depth_bpp": parent["color_depth_bpp"],
        "char_base_address": parent["char_base_address"],
        "screen_base_address": parent["screen_base_address"],
        "size_code": size_code,
        "dimensions_tiles": [width, height],
        "tilemap_sha256": _sha(bytes(tilemap)),
        "cell_count": width * height,
        "exact_nonblank_font_content_cell_count": exact_count,
        "ambiguous_blank_font_content_cell_count": blank_count,
        "no_font_content_cell_count": width * height - exact_count - blank_count,
        "ordered_sjis_pair_count": len(pairs),
        "ordered_sjis_pair_cell_count": len(pair_cells),
        "exact_nonblank_font_tiles": exact_tiles,
        "ambiguous_blank_font_cells": blank_cells,
        "ordered_sjis_pairs": pairs,
    }


def _payload(root: Path) -> dict:
    parent_path = root / PARENT_PAYLOAD
    parent_manifest_path = root / PARENT_MANIFEST
    font_path = root / FONT_MANIFEST
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    promotion = json.loads(parent_manifest_path.read_text(encoding="utf-8"))
    if _sha(parent_path.read_bytes()) != promotion["files"][PARENT_PAYLOAD.name]:
        raise ValueError("parent payload differs from manifest")
    font, expanded, sjis = _font_sources(root)
    parents = [
        item
        for item in parent["layers"]
        if item["classification"] == "unidentified_runtime_payload"
    ]
    parents.sort(key=lambda item: (item["state_id"], item["bg_index"]))
    cache = {}
    layers = [_layer(root, item, expanded, sjis, cache) for item in parents]
    pairs = [
        pair for layer in layers for pair in layer["ordered_sjis_pairs"]
    ]
    bg_counts = Counter(layer["bg_index"] for layer in layers)
    group_counts = Counter(
        pair["expansion_palette_group"] for pair in pairs
    )
    no_pair = [
        {
            "checkpoint": Path(layer["checkpoint_paths"][0]).name,
            "bg_index": layer["bg_index"],
        }
        for layer in layers
        if not layer["ordered_sjis_pairs"]
    ]
    no_pair.sort(key=lambda item: (item["checkpoint"], item["bg_index"]))
    summary = {
        "layer_count": len(layers),
        "cell_count": sum(layer["cell_count"] for layer in layers),
        "exact_nonblank_font_content_cell_count": sum(
            layer["exact_nonblank_font_content_cell_count"]
            for layer in layers
        ),
        "ambiguous_blank_font_content_cell_count": sum(
            layer["ambiguous_blank_font_content_cell_count"]
            for layer in layers
        ),
        "no_font_content_cell_count": sum(
            layer["no_font_content_cell_count"] for layer in layers
        ),
        "ordered_sjis_pair_count": len(pairs),
        "ordered_sjis_pair_cell_count": sum(
            layer["ordered_sjis_pair_cell_count"] for layer in layers
        ),
        "layers_with_ordered_sjis_pairs": sum(
            bool(layer["ordered_sjis_pairs"]) for layer in layers
        ),
        "distinct_sjis_code_count": len(
            {pair["sjis_hex"] for pair in pairs}
        ),
        "unique_source_pair_count": sum(
            pair["candidate_count"] == 1 for pair in pairs
        ),
        "layer_counts_by_bg_index": {
            str(key): value for key, value in sorted(bg_counts.items())
        },
        "ordered_pair_counts_by_palette_group": {
            str(key): value for key, value in sorted(group_counts.items())
        },
        "layers_without_ordered_sjis_pairs": no_pair,
    }
    return {
        "schema": SCHEMA,
        "implementation": {
            "exporter_sha256": _sha(
                (
                    root
                    / "tools/export_runtime_font_tile_provenance.py"
                ).read_bytes()
            ),
            "verifier_sha256": _sha(Path(__file__).read_bytes()),
            "test_sha256": _sha(
                (
                    root
                    / "tests/test_export_runtime_font_tile_provenance.py"
                ).read_bytes()
            ),
        },
        "source": {
            "rom": ROM_PATH.as_posix(),
            "rom_sha256": _sha((root / ROM_PATH).read_bytes()),
            "parent_provenance_payload": PARENT_PAYLOAD.as_posix(),
            "parent_provenance_payload_sha256": _sha(
                parent_path.read_bytes()
            ),
            "parent_provenance_manifest": PARENT_MANIFEST.as_posix(),
            "parent_provenance_manifest_sha256": _sha(
                parent_manifest_path.read_bytes()
            ),
            "dialogue_font_manifest": FONT_MANIFEST.as_posix(),
            "dialogue_font_manifest_sha256": _sha(font_path.read_bytes()),
            "dialogue_font_schema": font["schema"],
            "expansion_palette_groups": list(EXPANSION_PALETTE_GROUPS),
        },
        "classification_contract": {
            "exact_nonblank_font_content": (
                "runtime 4bpp tile bytes exactly equal a nonblank ROM "
                "dialogue-font half expanded with the proven groups 2 or 3"
            ),
            "ambiguous_blank_font_content": (
                "runtime tile bytes match only all-zero font sources and "
                "therefore do not identify a glyph"
            ),
            "ordered_sjis_vertical_pair": (
                "same-palette, unflipped vertical cells match half 0 then "
                "half 1 of one SJIS logical glyph"
            ),
            "whole_bg_identity_policy": (
                "component matches never replace the parent layer's "
                "unidentified_runtime_payload classification"
            ),
        },
        "summary": summary,
        "layers": layers,
        "scope": SCOPE,
    }


def _promotion(payload: dict, encoded: bytes) -> dict:
    summary = payload["summary"]
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {PAYLOAD_NAME: _sha(encoded)},
        "source": {
            "parent_layer_count": summary["layer_count"],
            "cell_count": summary["cell_count"],
            "dialogue_font_manifest": FONT_MANIFEST.as_posix(),
        },
        "producer": {
            "command": [
                "python3",
                "tools/export_runtime_font_tile_provenance.py",
                "--root",
                ".",
                "--output-dir",
                "artifacts/runtime-font-tile-provenance-v1",
            ],
            **payload["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_runtime_font_tile_provenance.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/runtime-font-tile-provenance-v1",
            ],
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                "layer_count": summary["layer_count"],
                "ordered_sjis_pair_count": summary[
                    "ordered_sjis_pair_count"
                ],
                "errors": [],
            },
        },
        "experiment": {
            "task": "runtime-unknown-bg-mechanism",
            "run_id": "20260730-01",
        },
    }


def verify_artifact(root: Path, artifact: Path) -> dict:
    root = Path(root).resolve()
    artifact = Path(artifact).resolve()
    errors = []
    try:
        expected = _payload(root)
        encoded = (
            json.dumps(
                expected,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        expected_manifest = _promotion(expected, encoded)
    except Exception as error:
        return {
            "schema": VERIFY_SCHEMA,
            "verified": False,
            "layer_count": 0,
            "ordered_sjis_pair_count": 0,
            "errors": [f"independent reconstruction failed: {error}"],
        }
    try:
        actual = json.loads(
            (artifact / PAYLOAD_NAME).read_text(encoding="utf-8")
        )
        if actual != expected:
            errors.append(
                "runtime font provenance differs from independent reconstruction"
            )
    except Exception as error:
        errors.append(f"payload read failed: {error}")
    try:
        manifest = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )
        if manifest != expected_manifest:
            errors.append("promotion manifest differs from reconstruction")
    except Exception as error:
        errors.append(f"promotion manifest read failed: {error}")
    files = sorted(
        path.relative_to(artifact).as_posix()
        for path in artifact.rglob("*")
        if path.is_file()
    )
    if files != ["manifest.json", PAYLOAD_NAME]:
        errors.append(f"unexpected artifact files: {files}")
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "layer_count": expected["summary"]["layer_count"],
        "ordered_sjis_pair_count": expected["summary"][
            "ordered_sjis_pair_count"
        ],
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts/runtime-font-tile-provenance-v1"),
    )
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
