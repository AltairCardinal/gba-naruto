#!/usr/bin/env python3
"""Bind runtime BG tile content to the verified dialogue-font source corpus."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.export_dialogue_font_atlases import expand_2bpp_to_4bpp
from tools.export_runtime_bg_composites import _decode_checkpoint, _map_offset


SCHEMA = "runtime-font-tile-provenance-v1"
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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_record_sha256(record: dict) -> str:
    encoded = (
        json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    return _sha256(encoded)


def _compact_ranges(values: list[int]) -> list[list[int]]:
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


def _load_font_sources(
    root: Path,
) -> tuple[dict, dict[bytes, list[dict]], dict[int, dict]]:
    manifest_path = root / FONT_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rom = (root / ROM_PATH).read_bytes()
    if _sha256(rom) != manifest["rom"]["sha256"]:
        raise ValueError("base ROM hash differs from dialogue-font-v2")

    sjis_by_logical = {
        int(record["logical_index"]): record
        for record in manifest["sjis_glyphs"]
    }
    expanded: dict[bytes, list[dict]] = defaultdict(list)
    physical = manifest["physical_half_tiles"]
    for expected_index, record in enumerate(physical):
        if int(record["index"]) != expected_index:
            raise ValueError("font physical half indices are not contiguous")
        offset = int(record["file_offset"])
        source = rom[offset : offset + 16]
        if len(source) != 16 or _sha256(source) != record["sha256"]:
            raise ValueError(
                f"font physical half {expected_index} differs from the ROM"
            )
        for palette_group in EXPANSION_PALETTE_GROUPS:
            runtime_tile = expand_2bpp_to_4bpp(
                source,
                palette_group=palette_group,
            )
            expanded[runtime_tile].append(
                {
                    "physical_half_index": expected_index,
                    "source_half_sha256": record["sha256"],
                    "palette_group": palette_group,
                    "lookup_branch": record["lookup_branch"],
                    "logical_index": int(record["logical_index"]),
                    "half_index": int(record["half_index"]),
                    "is_all_zero": bool(record["is_all_zero"]),
                }
            )
    return manifest, expanded, sjis_by_logical


def _font_tile_group(
    tile_id: int,
    tile: bytes,
    positions: list[int],
    candidates: list[dict],
    char_base: int,
) -> dict:
    candidate_rows = [
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
    candidate_rows.sort(
        key=lambda item: (
            item["physical_half_index"],
            item["expansion_palette_group"],
        )
    )
    return {
        "runtime_tile_id": tile_id,
        "runtime_tile_address": f"0x{0x06000000 + char_base + tile_id * 32:08X}",
        "runtime_tile_sha256": _sha256(tile),
        "cell_count": len(positions),
        "linear_cell_ranges": _compact_ranges(positions),
        "candidate_count": len(candidate_rows),
        "candidates": candidate_rows,
    }


def _build_layer(
    root: Path,
    parent: dict,
    expanded: dict[bytes, list[dict]],
    sjis_by_logical: dict[int, dict],
    cache: dict[str, tuple[dict, dict[str, bytes]]],
) -> dict:
    relative = parent["checkpoint_paths"][0]
    if relative not in cache:
        cache[relative] = _decode_checkpoint(root / relative)
    checkpoint, domains = cache[relative]
    if checkpoint["state_id"] != parent["state_id"]:
        raise ValueError(f"{relative}: parent/runtime state ID mismatch")
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
            raise ValueError(f"{relative}: parent BG field {field} mismatch")
    if background["color_depth_bpp"] != 4:
        raise ValueError(f"{relative}: font provenance expects a 4bpp BG")

    bg_vram = domains["bg_vram"]
    char_base = int(background["char_base_block"]) * 0x4000
    screen_base = int(background["screen_base_block"]) * 0x800
    size_code = int(background["size_code"])
    width, height = ((32, 32), (64, 32), (32, 64), (64, 64))[size_code]
    cells: list[list[dict]] = []
    tilemap = bytearray()
    font_positions_by_tile: dict[int, list[int]] = defaultdict(list)
    font_tile_content: dict[int, tuple[bytes, list[dict]]] = {}
    ambiguous_blank_cells = []

    for y in range(height):
        row = []
        for x in range(width):
            offset = _map_offset(screen_base, size_code, x, y)
            entry_bytes = bg_vram[offset : offset + 2]
            if len(entry_bytes) != 2:
                raise ValueError(f"{relative}: BG tilemap exceeds VRAM")
            tilemap.extend(entry_bytes)
            entry = int.from_bytes(entry_bytes, "little")
            tile_id = entry & 0x3FF
            tile_offset = char_base + tile_id * 32
            tile = bg_vram[tile_offset : tile_offset + 32]
            if len(tile) != 32:
                raise ValueError(f"{relative}: BG graphics exceeds VRAM")
            candidates = list(expanded.get(tile, ()))
            nonblank = [
                item for item in candidates if not item["is_all_zero"]
            ]
            linear = y * width + x
            if nonblank:
                font_positions_by_tile[tile_id].append(linear)
                previous = font_tile_content.setdefault(
                    tile_id,
                    (tile, nonblank),
                )
                if previous != (tile, nonblank):
                    raise ValueError(f"{relative}: reused tile ID changed content")
            elif candidates:
                ambiguous_blank_cells.append(
                    {
                        "classification": "ambiguous_blank_font_content",
                        "position_tiles": [x, y],
                        "linear_cell_index": linear,
                        "runtime_tile_id": tile_id,
                        "runtime_tile_address": (
                            f"0x{0x06000000 + tile_offset:08X}"
                        ),
                        "runtime_tile_sha256": _sha256(tile),
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

    ordered_pairs = []
    ordered_pair_cells: set[tuple[int, int]] = set()
    for y in range(height - 1):
        for x in range(width):
            top = cells[y][x]
            bottom = cells[y + 1][x]
            if (top["entry"] | bottom["entry"]) & 0x0C00:
                continue
            top_palette = (top["entry"] >> 12) & 0xF
            bottom_palette = (bottom["entry"] >> 12) & 0xF
            if top_palette != bottom_palette:
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
            ordered_pair_cells.update(((x, y), (x, y + 1)))
            selected = next(iter(candidates.values()))
            glyph = sjis_by_logical[selected[0]["logical_index"]]
            ordered_pairs.append(
                {
                    "position_tiles": [x, y],
                    "runtime_positions_tiles": [[x, y], [x, y + 1]],
                    "runtime_tile_ids": [
                        top["tile_id"],
                        bottom["tile_id"],
                    ],
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
                    "runtime_top_tile_sha256": _sha256(top["tile"]),
                    "runtime_bottom_tile_sha256": _sha256(bottom["tile"]),
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

    exact_font_tiles = [
        _font_tile_group(
            tile_id,
            font_tile_content[tile_id][0],
            font_positions_by_tile[tile_id],
            font_tile_content[tile_id][1],
            char_base,
        )
        for tile_id in sorted(font_positions_by_tile)
    ]
    exact_count = sum(
        item["cell_count"] for item in exact_font_tiles
    )
    blank_count = len(ambiguous_blank_cells)
    parent_key = f"{parent['state_id']}:bg{parent['bg_index']}"
    return {
        "parent_layer_key": parent_key,
        "parent_layer_sha256": _canonical_record_sha256(parent),
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
        "tilemap_sha256": _sha256(bytes(tilemap)),
        "cell_count": width * height,
        "exact_nonblank_font_content_cell_count": exact_count,
        "ambiguous_blank_font_content_cell_count": blank_count,
        "no_font_content_cell_count": width * height - exact_count - blank_count,
        "ordered_sjis_pair_count": len(ordered_pairs),
        "ordered_sjis_pair_cell_count": len(ordered_pair_cells),
        "exact_nonblank_font_tiles": exact_font_tiles,
        "ambiguous_blank_font_cells": ambiguous_blank_cells,
        "ordered_sjis_pairs": ordered_pairs,
    }


def build_payload(root: Path) -> dict:
    root = Path(root).resolve()
    parent_path = root / PARENT_PAYLOAD
    parent_manifest_path = root / PARENT_MANIFEST
    font_manifest_path = root / FONT_MANIFEST
    parent_payload = json.loads(parent_path.read_text(encoding="utf-8"))
    parent_promotion = json.loads(
        parent_manifest_path.read_text(encoding="utf-8")
    )
    expected_parent_hash = parent_promotion["files"][PARENT_PAYLOAD.name]
    if _sha256(parent_path.read_bytes()) != expected_parent_hash:
        raise ValueError("parent provenance payload differs from its manifest")
    font_manifest, expanded, sjis_by_logical = _load_font_sources(root)

    parents = [
        item
        for item in parent_payload["layers"]
        if item["classification"] == "unidentified_runtime_payload"
    ]
    parents.sort(key=lambda item: (item["state_id"], item["bg_index"]))
    cache: dict[str, tuple[dict, dict[str, bytes]]] = {}
    layers = [
        _build_layer(root, item, expanded, sjis_by_logical, cache)
        for item in parents
    ]

    palette_groups = Counter(
        pair["expansion_palette_group"]
        for layer in layers
        for pair in layer["ordered_sjis_pairs"]
    )
    bg_indices = Counter(layer["bg_index"] for layer in layers)
    all_pairs = [
        pair
        for layer in layers
        for pair in layer["ordered_sjis_pairs"]
    ]
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
        "ordered_sjis_pair_count": len(all_pairs),
        "ordered_sjis_pair_cell_count": sum(
            layer["ordered_sjis_pair_cell_count"] for layer in layers
        ),
        "layers_with_ordered_sjis_pairs": sum(
            bool(layer["ordered_sjis_pairs"]) for layer in layers
        ),
        "distinct_sjis_code_count": len(
            {pair["sjis_hex"] for pair in all_pairs}
        ),
        "unique_source_pair_count": sum(
            pair["candidate_count"] == 1 for pair in all_pairs
        ),
        "layer_counts_by_bg_index": {
            str(key): value for key, value in sorted(bg_indices.items())
        },
        "ordered_pair_counts_by_palette_group": {
            str(key): value for key, value in sorted(palette_groups.items())
        },
        "layers_without_ordered_sjis_pairs": no_pair,
    }
    return {
        "schema": SCHEMA,
        "implementation": {
            "exporter_sha256": _sha256(Path(__file__).read_bytes()),
            "verifier_sha256": _sha256(
                (
                    root
                    / "tools/verify_runtime_font_tile_provenance.py"
                ).read_bytes()
            ),
            "test_sha256": _sha256(
                (
                    root
                    / "tests/test_export_runtime_font_tile_provenance.py"
                ).read_bytes()
            ),
        },
        "source": {
            "rom": ROM_PATH.as_posix(),
            "rom_sha256": _sha256((root / ROM_PATH).read_bytes()),
            "parent_provenance_payload": PARENT_PAYLOAD.as_posix(),
            "parent_provenance_payload_sha256": _sha256(
                parent_path.read_bytes()
            ),
            "parent_provenance_manifest": PARENT_MANIFEST.as_posix(),
            "parent_provenance_manifest_sha256": _sha256(
                parent_manifest_path.read_bytes()
            ),
            "dialogue_font_manifest": FONT_MANIFEST.as_posix(),
            "dialogue_font_manifest_sha256": _sha256(
                font_manifest_path.read_bytes()
            ),
            "dialogue_font_schema": font_manifest["schema"],
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


def _promotion(payload: dict, payload_bytes: bytes) -> dict:
    summary = payload["summary"]
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {PAYLOAD_NAME: _sha256(payload_bytes)},
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
                "schema": "runtime-font-tile-provenance-verification-v1",
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


def export_artifact(root: Path, output: Path) -> dict:
    root = Path(root).resolve()
    output = Path(output).resolve()
    payload = build_payload(root)
    payload_bytes = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{output.name}.",
        dir=output.parent,
    ) as temporary:
        staged = Path(temporary) / output.name
        staged.mkdir()
        (staged / PAYLOAD_NAME).write_bytes(payload_bytes)
        (staged / "manifest.json").write_text(
            json.dumps(
                _promotion(payload, payload_bytes),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if output.exists():
            shutil.rmtree(output)
        os.replace(staged, output)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/runtime-font-tile-provenance-v1"),
    )
    args = parser.parse_args()
    payload = export_artifact(args.root, args.output_dir)
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
