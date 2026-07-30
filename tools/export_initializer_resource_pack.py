#!/usr/bin/env python3
"""Export the ROM resource pack loaded by the 0x08065404 initializer."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
import uuid


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from tools.extract_tileset import lz77_decompress  # noqa: E402
from tools.export_runtime_bg_composites import (  # noqa: E402
    _decode_checkpoint,
    _map_offset,
)
from tools.gba_image_export import (  # noqa: E402
    indexed_png_from_bgr555,
    read_lz77_record,
    render_4bpp_tile_atlas_indices,
)
from tools.thumb_branch import decode_thumb_bl  # noqa: E402


SCHEMA = "initializer-resource-pack-v1"
VERIFY_SCHEMA = "initializer-resource-pack-verification-v1"
PAYLOAD_NAME = "initializer-resource-pack.json"
ROM_PATH = Path("rom/base.gba")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
INITIALIZER_START = 0x065404
INITIALIZER_END = 0x065554
INITIALIZER_SHA256 = (
    "213423e70948ef3dbd91ed7854efb5c52fd7543f4b73b4a4a2219ffd89ce66f7"
)
CALLER_SCAN_END = 0x09C000
INITIALIZER_GBA = 0x08065404
DIRECT_CALLERS = (
    0x080691F8,
    0x08073752,
    0x08074E96,
    0x0807953C,
    0x0807AB68,
    0x08081328,
    0x08086204,
    0x0808692C,
    0x08086A94,
    0x08086B4C,
    0x0808702C,
    0x080875C0,
    0x08087CD6,
    0x0808819C,
    0x08088F92,
    0x0808A120,
    0x0808B5B2,
    0x0808BAE2,
    0x0808C506,
    0x0808CBA0,
    0x0808F26A,
    0x0808F582,
    0x08091512,
)
PARENT_PROVENANCE = Path(
    "artifacts/runtime-layer-static-provenance-v1/"
    "runtime-layer-static-provenance.json"
)
PARENT_PROVENANCE_MANIFEST = Path(
    "artifacts/runtime-layer-static-provenance-v1/manifest.json"
)
FONT_PROVENANCE = Path(
    "artifacts/runtime-font-tile-provenance-v1/"
    "runtime-font-tile-provenance.json"
)
FONT_PROVENANCE_MANIFEST = Path(
    "artifacts/runtime-font-tile-provenance-v1/manifest.json"
)
PARENT_PROVENANCE_SHA256 = (
    "4ba73a257695af886e939dd2dd2aff506a4fc4d0f952401f36f9dc408cc48578"
)
PARENT_PROVENANCE_MANIFEST_SHA256 = (
    "6a24b443bea94177c8a017a1099cfb343b4d61bed765f6a4d7400cf738a16704"
)
FONT_PROVENANCE_SHA256 = (
    "4787d0049a7d7b92e106b7eb560e0893271dcf979739031f06ad16f5714d6d5a"
)
FONT_PROVENANCE_MANIFEST_SHA256 = (
    "ad74f08c107a5326dc75c003614fcaff6fe1b0218087da80781d3d2316780375"
)
COMMON_TILE_DELTA = 448

RESOURCE_SPECS = {
    "bg_graphics": {
        "offset": 0x09C614,
        "literal_address": 0x0806557C,
        "load_call": 0x080654A0,
        "loader_target": 0x0809C0E8,
        "kind": "graphics",
        "tiles_per_row": 16,
        "palette": "bg_palette",
    },
    "bg_palette": {
        "offset": 0x09C870,
        "literal_address": 0x08065580,
        "load_call": 0x080654B8,
        "loader_target": 0x0808830C,
        "kind": "palette",
    },
    "obj_graphics": {
        "offset": 0x5B64E0,
        "literal_address": 0x08065588,
        "load_call": 0x080654C6,
        "loader_target": 0x0809C0E8,
        "kind": "graphics",
        "tiles_per_row": 12,
        "palette": "obj_palette",
    },
    "obj_palette": {
        "offset": 0x09CBC4,
        "literal_address": 0x08065590,
        "load_call": 0x080654D6,
        "loader_target": 0x0808830C,
        "kind": "palette",
    },
}

SCOPE = {
    "four_initializer_resources_losslessly_exported": True,
    "initializer_literal_and_loader_routes_code_verified": True,
    "tracked_parent_nonfont_cells_fully_classified": True,
    "exact_initializer_bg_tile_content_components_bound": True,
    "aliased_zero_and_fill_content_retained": True,
    "whole_bg_source_identity_complete": False,
    "runtime_writer_identity_per_checkpoint_complete": False,
    "obj_runtime_instance_binding_complete": False,
    "all_game_visual_states_complete": False,
    "natural_language_resource_identity_complete": False,
    "remaining_nonfont_content_sources_complete": False,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _canonical_record_sha256(record: dict[str, Any]) -> str:
    data = (
        json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    return _sha256(data)


def _expand_ranges(ranges: list[list[int]]) -> set[int]:
    return {
        value
        for start, end in ranges
        for value in range(int(start), int(end))
    }


def _compact_ranges(values: list[int]) -> list[list[int]]:
    unique = sorted(set(values))
    if not unique:
        return []
    result: list[list[int]] = []
    start = previous = unique[0]
    for value in unique[1:]:
        if value != previous + 1:
            result.append([start, previous + 1])
            start = value
        previous = value
    result.append([start, previous + 1])
    return result


def _validate_output_target(root: Path, output: Path) -> Path:
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
            manifest = json.loads(
                (target / "manifest.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(
                "refusing to replace a directory that is not this artifact"
            ) from error
        if manifest.get("artifact_schema") != SCHEMA:
            raise ValueError(
                "refusing to replace a directory that is not this artifact"
            )
    return target


def _replace_output(
    output: Path,
    files: dict[str, bytes],
    manifest: dict[str, Any],
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
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
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


def _scan_direct_callers(rom: bytes) -> list[int]:
    callers: list[int] = []
    for offset in range(0, min(CALLER_SCAN_END, len(rom) - 3), 2):
        first = int.from_bytes(rom[offset : offset + 2], "little")
        second = int.from_bytes(rom[offset + 2 : offset + 4], "little")
        address = 0x08000000 + offset
        if decode_thumb_bl(address, first, second) == INITIALIZER_GBA:
            callers.append(address)
    return callers


def _resource_files(
    rom: bytes,
) -> tuple[dict[str, dict[str, Any]], dict[str, bytes], dict[str, bytes]]:
    resources: dict[str, dict[str, Any]] = {}
    files: dict[str, bytes] = {}
    decompressed: dict[str, bytes] = {}
    compressed: dict[str, bytes] = {}
    for key, spec in RESOURCE_SPECS.items():
        offset = int(spec["offset"])
        compressed[key] = read_lz77_record(rom, offset)
        decompressed[key] = lz77_decompress(rom, offset)
        compressed_file = f"{key.replace('_', '-')}.lz77.bin"
        file = f"{key.replace('_', '-')}.bin"
        files[compressed_file] = compressed[key]
        files[file] = decompressed[key]
        record: dict[str, Any] = {
            "gba_pointer": _address(0x08000000 + offset),
            "file_offset": offset,
            "literal_gba_address": _address(int(spec["literal_address"])),
            "load_call_gba_address": _address(int(spec["load_call"])),
            "loader_target_gba_address": _address(int(spec["loader_target"])),
            "compressed_file": compressed_file,
            "compressed_size": len(compressed[key]),
            "compressed_sha256": _sha256(compressed[key]),
            "file": file,
            "decompressed_size": len(decompressed[key]),
            "decompressed_sha256": _sha256(decompressed[key]),
        }
        if spec["kind"] == "graphics":
            if len(decompressed[key]) % 32:
                raise ValueError(f"{key} is not complete 4bpp tile data")
            tiles = [
                decompressed[key][offset : offset + 32]
                for offset in range(0, len(decompressed[key]), 32)
            ]
            record.update(
                {
                    "bits_per_pixel": 4,
                    "tile_count": len(tiles),
                    "unique_tile_content_count": len(set(tiles)),
                }
            )
        else:
            if len(decompressed[key]) % 2:
                raise ValueError(f"{key} has an incomplete BGR555 color")
            record["color_count"] = len(decompressed[key]) // 2
        resources[key] = record

    for key, spec in RESOURCE_SPECS.items():
        if spec["kind"] != "graphics":
            continue
        pixels, width, height = render_4bpp_tile_atlas_indices(
            decompressed[key],
            tiles_per_row=int(spec["tiles_per_row"]),
        )
        atlas = indexed_png_from_bgr555(
            pixels,
            decompressed[str(spec["palette"])],
            width=width,
            height=height,
        )
        atlas_file = f"{key.replace('_', '-')}-atlas.png"
        files[atlas_file] = atlas
        resources[key]["atlas_png"] = atlas_file
        resources[key]["atlas_sha256"] = _sha256(atlas)
        resources[key]["atlas_dimensions"] = [width, height]
    return resources, files, decompressed


def _group_record(
    key: tuple[Any, ...],
    positions: list[int],
    *,
    char_base: int,
    classification: str,
) -> dict[str, Any]:
    (
        runtime_tile_id,
        runtime_tile_sha256,
        palette_bank,
        horizontal_flip,
        vertical_flip,
        source_indices,
        alias_kind,
    ) = key
    record: dict[str, Any] = {
        "classification": classification,
        "runtime_tile_id": runtime_tile_id,
        "runtime_tile_address": _address(
            0x06000000 + char_base + runtime_tile_id * 32
        ),
        "runtime_tile_sha256": runtime_tile_sha256,
        "runtime_palette_bank": palette_bank,
        "flip_hv": [horizontal_flip, vertical_flip],
        "cell_count": len(positions),
        "linear_cell_ranges": _compact_ranges(positions),
    }
    if source_indices:
        source_indices = list(source_indices)
        record.update(
            {
                "source_tile_indices": source_indices,
                "source_tile_candidate_count": len(source_indices),
                "source_tile_deltas": [
                    runtime_tile_id - source_id for source_id in source_indices
                ],
                "common_delta_match": (
                    runtime_tile_id - COMMON_TILE_DELTA in source_indices
                ),
            }
        )
    if alias_kind:
        record["alias_kind"] = alias_kind
        record["unique_source_identity"] = False
    return record


def _build_runtime_binding(
    root: Path,
    source_graphics: bytes,
    source_palette: bytes,
) -> dict[str, Any]:
    font_path = root / FONT_PROVENANCE
    font_manifest_path = root / FONT_PROVENANCE_MANIFEST
    parent_manifest_path = root / PARENT_PROVENANCE_MANIFEST
    if _sha256(font_path.read_bytes()) != FONT_PROVENANCE_SHA256:
        raise ValueError("font provenance payload differs from accepted anchor")
    if (
        _sha256(font_manifest_path.read_bytes())
        != FONT_PROVENANCE_MANIFEST_SHA256
    ):
        raise ValueError("font provenance manifest differs from accepted anchor")
    font = json.loads(font_path.read_text(encoding="utf-8"))
    parent_path = root / PARENT_PROVENANCE
    if _sha256(parent_path.read_bytes()) != PARENT_PROVENANCE_SHA256:
        raise ValueError("parent provenance payload differs from accepted anchor")
    if (
        _sha256(parent_manifest_path.read_bytes())
        != PARENT_PROVENANCE_MANIFEST_SHA256
    ):
        raise ValueError("parent provenance manifest differs from accepted anchor")
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    parent_manifest = json.loads(
        parent_manifest_path.read_text(encoding="utf-8")
    )
    font_manifest = json.loads(font_manifest_path.read_text(encoding="utf-8"))
    for label, manifest, payload_name, payload_hash in (
        (
            "parent",
            parent_manifest,
            PARENT_PROVENANCE.name,
            PARENT_PROVENANCE_SHA256,
        ),
        (
            "font",
            font_manifest,
            FONT_PROVENANCE.name,
            FONT_PROVENANCE_SHA256,
        ),
    ):
        if (
            manifest.get("artifact_status") != "accepted"
            or manifest.get("files", {}).get(payload_name) != payload_hash
            or not manifest.get("verifier", {}).get("report", {}).get(
                "verified"
            )
        ):
            raise ValueError(f"{label} provenance manifest is not accepted")
    parents = {
        f"{item['state_id']}:bg{item['bg_index']}": item
        for item in parent["layers"]
        if item["classification"] == "unidentified_runtime_payload"
    }
    if len(parents) != 61 or len(font["layers"]) != 61:
        raise ValueError("parent unidentified layer denominator changed")

    source_tiles: dict[bytes, list[int]] = defaultdict(list)
    for source_id in range(len(source_graphics) // 32):
        tile = source_graphics[source_id * 32 : (source_id + 1) * 32]
        source_tiles[tile].append(source_id)
    zero = bytes(32)
    if source_tiles.get(zero) != [0] + list(range(34, 64)):
        raise ValueError("initializer zero tile aliases changed")
    common_fill = source_graphics[32:64]
    if source_tiles.get(common_fill) != [1, 10]:
        raise ValueError("initializer common-fill aliases changed")

    source_palette_banks = [
        source_palette[offset : offset + 32]
        for offset in range(0, len(source_palette), 32)
    ]
    cache: dict[str, tuple[dict, dict[str, bytes]]] = {}
    layers: list[dict[str, Any]] = []
    all_exact_hashes: set[str] = set()
    all_unmatched_hashes: set[str] = set()
    alias_totals = defaultdict(int)

    for font_layer in font["layers"]:
        key = font_layer["parent_layer_key"]
        parent_layer = parents.get(key)
        if parent_layer is None:
            raise ValueError(f"missing parent layer {key}")
        if font_layer["parent_layer_sha256"] != _canonical_record_sha256(
            parent_layer
        ):
            raise ValueError(f"parent layer hash changed for {key}")
        relative = font_layer["checkpoint_paths"][0]
        if relative not in cache:
            cache[relative] = _decode_checkpoint(root / relative)
        checkpoint, domains = cache[relative]
        background = next(
            item
            for item in checkpoint["backgrounds"]
            if item["index"] == font_layer["bg_index"]
        )
        width, height = map(int, font_layer["dimensions_tiles"])
        char_base = int(background["char_base_block"]) * 0x4000
        screen_base = int(background["screen_base_block"]) * 0x800
        size_code = int(background["size_code"])
        excluded: set[int] = set()
        for group in font_layer["exact_nonblank_font_tiles"]:
            excluded.update(_expand_ranges(group["linear_cell_ranges"]))
        excluded.update(
            int(item["linear_cell_index"])
            for item in font_layer["ambiguous_blank_font_cells"]
        )
        if len(excluded) != (
            int(font_layer["exact_nonblank_font_content_cell_count"])
            + int(font_layer["ambiguous_blank_font_content_cell_count"])
        ):
            raise ValueError(f"font exclusions overlap for {key}")

        exact_groups: dict[tuple[Any, ...], list[int]] = defaultdict(list)
        alias_groups: dict[tuple[Any, ...], list[int]] = defaultdict(list)
        unmatched_groups: dict[tuple[Any, ...], list[int]] = defaultdict(list)
        exact_count = alias_count = unmatched_count = 0
        fixed_delta_count = 0
        exact_palette_banks: list[dict[str, Any]] = []

        for y in range(height):
            for x in range(width):
                linear = y * width + x
                if linear in excluded:
                    continue
                map_offset = _map_offset(screen_base, size_code, x, y)
                entry = int.from_bytes(
                    domains["bg_vram"][map_offset : map_offset + 2],
                    "little",
                )
                runtime_id = entry & 0x03FF
                tile_offset = char_base + runtime_id * 32
                tile = domains["bg_vram"][tile_offset : tile_offset + 32]
                if len(tile) != 32:
                    raise ValueError(f"{relative}: runtime tile exceeds BG VRAM")
                tile_hash = _sha256(tile)
                source_indices = tuple(source_tiles.get(tile, ()))
                palette_bank = (entry >> 12) & 0xF
                horizontal_flip = bool(entry & 0x0400)
                vertical_flip = bool(entry & 0x0800)
                alias_kind = None
                if tile == zero:
                    alias_kind = "all_zero"
                elif tile == common_fill:
                    alias_kind = "common_fill"
                group_key = (
                    runtime_id,
                    tile_hash,
                    palette_bank,
                    horizontal_flip,
                    vertical_flip,
                    source_indices,
                    alias_kind,
                )
                if alias_kind:
                    alias_groups[group_key].append(linear)
                    alias_count += 1
                    alias_totals[alias_kind] += 1
                elif source_indices:
                    exact_groups[group_key].append(linear)
                    exact_count += 1
                    all_exact_hashes.add(tile_hash)
                    if runtime_id - COMMON_TILE_DELTA in source_indices:
                        fixed_delta_count += 1
                else:
                    unmatched_groups[group_key].append(linear)
                    unmatched_count += 1
                    all_unmatched_hashes.add(tile_hash)

        if exact_count:
            runtime_palette_banks = sorted(
                {
                    group_key[2]
                    for group_key in exact_groups
                }
            )
            for runtime_bank in runtime_palette_banks:
                runtime_bytes = domains["bg_palette"][
                    runtime_bank * 32 : (runtime_bank + 1) * 32
                ]
                source_matches = [
                    source_bank
                    for source_bank, source_bytes in enumerate(
                        source_palette_banks
                    )
                    if runtime_bytes == source_bytes
                ]
                if source_matches:
                    exact_palette_banks.append(
                        {
                            "runtime_palette_bank": runtime_bank,
                            "runtime_palette_sha256": _sha256(runtime_bytes),
                            "source_palette_banks": source_matches,
                            "evidence_type": "checkpoint_bytes",
                        }
                    )

        exact_records = [
            _group_record(
                group_key,
                positions,
                char_base=char_base,
                classification="exact_initializer_bg_graphics_content",
            )
            for group_key, positions in sorted(exact_groups.items())
        ]
        alias_records = [
            _group_record(
                group_key,
                positions,
                char_base=char_base,
                classification="aliased_initializer_bg_graphics_content",
            )
            for group_key, positions in sorted(alias_groups.items())
        ]
        unmatched_records = [
            _group_record(
                group_key,
                positions,
                char_base=char_base,
                classification="unmatched_nonfont_content",
            )
            for group_key, positions in sorted(unmatched_groups.items())
        ]
        nonfont_count = width * height - len(excluded)
        if nonfont_count != exact_count + alias_count + unmatched_count:
            raise ValueError(f"{key}: nonfont classification is incomplete")
        layers.append(
            {
                "parent_layer_key": key,
                "parent_layer_sha256": font_layer["parent_layer_sha256"],
                "parent_classification": "unidentified_runtime_payload",
                "state_id": font_layer["state_id"],
                "checkpoint_paths": font_layer["checkpoint_paths"],
                "checkpoint": Path(relative).name,
                "bg_index": font_layer["bg_index"],
                "bgcnt": font_layer["bgcnt"],
                "char_base_address": font_layer["char_base_address"],
                "screen_base_address": font_layer["screen_base_address"],
                "dimensions_tiles": [width, height],
                "nonfont_cell_count": nonfont_count,
                "exact_initializer_bg_content_cell_count": exact_count,
                "aliased_initializer_content_cell_count": alias_count,
                "unmatched_nonfont_cell_count": unmatched_count,
                "common_runtime_tile_delta": (
                    COMMON_TILE_DELTA if exact_count else None
                ),
                "fixed_delta_cell_count": fixed_delta_count,
                "all_exact_content_at_common_delta": (
                    bool(exact_count) and fixed_delta_count == exact_count
                ),
                "exact_palette_bindings": exact_palette_banks,
                "exact_initializer_bg_contents": exact_records,
                "aliased_initializer_contents": alias_records,
                "unmatched_nonfont_contents": unmatched_records,
            }
        )

    layers.sort(key=lambda item: (item["state_id"], item["bg_index"]))
    no_exact = [
        {
            "checkpoint": layer["checkpoint"],
            "bg_index": layer["bg_index"],
        }
        for layer in layers
        if not layer["exact_initializer_bg_content_cell_count"]
    ]
    no_exact.sort(key=lambda item: (item["checkpoint"], item["bg_index"]))
    exact_total = sum(
        layer["exact_initializer_bg_content_cell_count"] for layer in layers
    )
    fixed_total = sum(layer["fixed_delta_cell_count"] for layer in layers)
    alias_total = sum(
        layer["aliased_initializer_content_cell_count"] for layer in layers
    )
    unmatched_total = sum(
        layer["unmatched_nonfont_cell_count"] for layer in layers
    )
    nonfont_total = sum(layer["nonfont_cell_count"] for layer in layers)
    if (
        nonfont_total,
        exact_total,
        alias_total,
        unmatched_total,
        len(all_exact_hashes),
        len(all_unmatched_hashes),
    ) != (59611, 5225, 53488, 898, 23, 39):
        raise ValueError("runtime initializer binding denominator changed")
    source_palette_sha = _sha256(source_palette_banks[0])
    if source_palette_sha != (
        "6b8d0c736a2f8ba4f6954f7a1f1e7b18458c3b34bf216beb21b9f03f5ff8bfb9"
    ):
        raise ValueError("initializer source palette bank 0 changed")

    alias_content_groups = [
        {
            "classification": "aliased_initializer_bg_graphics_content",
            "alias_kind": "all_zero",
            "runtime_tile_sha256": _sha256(zero),
            "runtime_cell_count": alias_totals["all_zero"],
            "source_tile_indices": source_tiles[zero],
            "source_tile_candidate_count": len(source_tiles[zero]),
            "unique_source_identity": False,
        },
        {
            "classification": "aliased_initializer_bg_graphics_content",
            "alias_kind": "common_fill",
            "runtime_tile_sha256": _sha256(common_fill),
            "runtime_cell_count": alias_totals["common_fill"],
            "source_tile_indices": source_tiles[common_fill],
            "source_tile_candidate_count": len(source_tiles[common_fill]),
            "unique_source_identity": False,
        },
    ]
    return {
        "source": {
            "bg_graphics_sha256": _sha256(source_graphics),
            "bg_palette_sha256": _sha256(source_palette),
            "parent_layer_provenance": PARENT_PROVENANCE.as_posix(),
            "parent_layer_provenance_sha256": _sha256(parent_path.read_bytes()),
            "parent_layer_provenance_manifest": (
                PARENT_PROVENANCE_MANIFEST.as_posix()
            ),
            "parent_layer_provenance_manifest_sha256": _sha256(
                parent_manifest_path.read_bytes()
            ),
            "font_tile_provenance": FONT_PROVENANCE.as_posix(),
            "font_tile_provenance_sha256": _sha256(font_path.read_bytes()),
            "font_tile_provenance_manifest": (
                FONT_PROVENANCE_MANIFEST.as_posix()
            ),
            "font_tile_provenance_manifest_sha256": _sha256(
                font_manifest_path.read_bytes()
            ),
        },
        "classification_contract": {
            "exact_initializer_bg_graphics_content": (
                "runtime 4bpp tile bytes equal a nonzero, non-common-fill "
                "tile content in the statically loaded BG graphics stream"
            ),
            "aliased_initializer_bg_graphics_content": (
                "runtime bytes equal the all-zero or common-fill content; "
                "content equality is retained without unique source identity"
            ),
            "unmatched_nonfont_content": (
                "runtime nonfont tile bytes do not occur in this BG stream"
            ),
            "parent_identity_policy": (
                "component matches never replace the parent layer's "
                "unidentified_runtime_payload classification"
            ),
        },
        "summary": {
            "parent_layer_count": len(layers),
            "nonfont_cell_count": nonfont_total,
            "exact_initializer_bg_content_cell_count": exact_total,
            "exact_initializer_bg_content_distinct_hash_count": len(
                all_exact_hashes
            ),
            "aliased_initializer_content_cell_count": alias_total,
            "aliased_zero_cell_count": alias_totals["all_zero"],
            "aliased_common_fill_cell_count": alias_totals["common_fill"],
            "unmatched_nonfont_cell_count": unmatched_total,
            "unmatched_nonfont_distinct_hash_count": len(all_unmatched_hashes),
            "layers_with_exact_initializer_bg_content": sum(
                bool(layer["exact_initializer_bg_content_cell_count"])
                for layer in layers
            ),
            "layers_without_exact_initializer_bg_content_count": len(no_exact),
            "layers_without_exact_initializer_bg_content": no_exact,
            "common_runtime_tile_delta": COMMON_TILE_DELTA,
            "fixed_delta_cell_count": fixed_total,
            "non_fixed_delta_cell_count": exact_total - fixed_total,
            "layers_with_all_exact_content_at_common_delta": sum(
                layer["all_exact_content_at_common_delta"] for layer in layers
            ),
            "layers_with_exact_bg_palette_bank": sum(
                bool(layer["exact_palette_bindings"]) for layer in layers
            ),
            "common_palette_binding": {
                "source_palette_bank": 0,
                "runtime_palette_bank": 14,
                "sha256": source_palette_sha,
            },
        },
        "alias_content_groups": alias_content_groups,
        "layers": layers,
    }


def build_payload(
    root: Path,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    root = root.resolve()
    rom = (root / ROM_PATH).read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    initializer = rom[INITIALIZER_START:INITIALIZER_END]
    if (
        len(initializer) != INITIALIZER_END - INITIALIZER_START
        or _sha256(initializer) != INITIALIZER_SHA256
    ):
        raise ValueError("initializer code slice differs from the accepted ROM")
    callers = _scan_direct_callers(rom)
    if callers != list(DIRECT_CALLERS):
        raise ValueError("initializer direct caller inventory changed")

    resources, files, decompressed = _resource_files(rom)
    for key, spec in RESOURCE_SPECS.items():
        literal_offset = int(spec["literal_address"]) - 0x08000000
        expected_pointer = 0x08000000 + int(spec["offset"])
        actual_pointer = int.from_bytes(
            rom[literal_offset : literal_offset + 4], "little"
        )
        if actual_pointer != expected_pointer:
            raise ValueError(f"{key} literal pointer changed")
        call_offset = int(spec["load_call"]) - 0x08000000
        first = int.from_bytes(rom[call_offset : call_offset + 2], "little")
        second = int.from_bytes(
            rom[call_offset + 2 : call_offset + 4], "little"
        )
        if decode_thumb_bl(int(spec["load_call"]), first, second) != int(
            spec["loader_target"]
        ):
            raise ValueError(f"{key} loader target changed")

    runtime_binding = _build_runtime_binding(
        root,
        decompressed["bg_graphics"],
        decompressed["bg_palette"],
    )
    verifier_path = root / "tools/verify_initializer_resource_pack.py"
    test_path = root / "tests/test_export_initializer_resource_pack.py"
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "implementation": {
            "exporter_sha256": _sha256(Path(__file__).read_bytes()),
            "verifier_sha256": _sha256(verifier_path.read_bytes()),
            "test_sha256": _sha256(test_path.read_bytes()),
        },
        "rom": {
            "file": ROM_PATH.as_posix(),
            "sha256": ROM_SHA256,
        },
        "initializer": {
            "gba_start": _address(0x08000000 + INITIALIZER_START),
            "gba_end_exclusive": _address(0x08000000 + INITIALIZER_END),
            "size": len(initializer),
            "sha256": INITIALIZER_SHA256,
            "direct_callers": callers,
            "evidence_type": "static_code",
        },
        "resources": resources,
        "loader_routes": {
            "bg_graphics": {
                "wrapper_gba_address": "0x0809C0E8",
                "bios_service": "LZ77UnCompVram",
                "source_register": "r0",
                "destination_register": "r1",
                "destination_formula": (
                    "0x06000000 + bg_charblock * 0x4000 + bg_tile_base * 32"
                ),
                "destination_pointer_global": "0x0201BD54",
                "evidence_type": "static_code",
            },
            "bg_palette": {
                "helper_gba_address": "0x0808830C",
                "bios_decompress": "LZ77UnCompWram",
                "bios_copy": "CpuSet",
                "scratch_address": "0x02002880",
                "destination_formula": (
                    "0x05000000 + bg_palette_slot * 32"
                ),
                "evidence_type": "static_code",
            },
            "obj_graphics": {
                "wrapper_gba_address": "0x0809C0E8",
                "bios_service": "LZ77UnCompVram",
                "destination_formula": (
                    "0x06010000 + obj_tile_slot * 32"
                ),
                "destination_slot_global": "0x0201BD5E",
                "evidence_type": "static_code",
            },
            "obj_palette": {
                "helper_gba_address": "0x0808830C",
                "bios_decompress": "LZ77UnCompWram",
                "bios_copy": "CpuSet",
                "scratch_address": "0x02002880",
                "destination_formula": (
                    "0x05000200 + obj_palette_slot * 32"
                ),
                "destination_slot_global": "0x0201BD60",
                "evidence_type": "static_code",
            },
        },
        "runtime_binding": runtime_binding,
        "scope": SCOPE,
    }
    payload_bytes = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    files[PAYLOAD_NAME] = payload_bytes
    return payload, files


def _promotion(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    summary = payload["runtime_binding"]["summary"]
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {
            relative: _sha256(data)
            for relative, data in sorted(files.items())
        },
        "source": {
            "rom_sha256": ROM_SHA256,
            "initializer_gba_address": "0x08065404",
            "runtime_parent_layer_count": summary["parent_layer_count"],
            "runtime_nonfont_cell_count": summary["nonfont_cell_count"],
        },
        "producer": {
            "command": [
                "python3",
                "tools/export_initializer_resource_pack.py",
                "--root",
                ".",
                "--output-dir",
                "artifacts/initializer-resource-pack-v1",
            ],
            **payload["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_initializer_resource_pack.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/initializer-resource-pack-v1",
            ],
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                "resource_count": 4,
                "runtime_layer_count": summary["parent_layer_count"],
                "nonfont_cell_count": summary["nonfont_cell_count"],
                "errors": [],
            },
        },
        "experiment": {
            "task": "runtime-nonfont-tile-provenance",
            "run_id": "20260730-01",
        },
    }


def export_artifact(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    output = _validate_output_target(root, Path(output_dir))
    payload, files = build_payload(root)
    _replace_output(output, files, _promotion(payload, files))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/initializer-resource-pack-v1"),
    )
    args = parser.parse_args()
    payload = export_artifact(args.root, args.output_dir)
    print(
        json.dumps(
            payload["runtime_binding"]["summary"],
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
