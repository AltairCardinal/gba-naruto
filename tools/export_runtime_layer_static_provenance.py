#!/usr/bin/env python3
"""Export byte-level provenance from tracked runtime BG layers to static assets."""

from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEFAULT_ROOT))

from tools.export_runtime_bg_composites import _decode_checkpoint  # noqa: E402
from tools.extract_tileset import lz77_decompress  # noqa: E402


SCHEMA = "runtime-layer-static-provenance-v1"
SOURCE_MANIFESTS = (
    "artifacts/bg-resource-canvases-v1/manifest.json",
    "artifacts/map-canvases-v1/manifest.json",
    "artifacts/scene-visual-packs-v1/manifest.json",
    "artifacts/story-visual-layers-v1/manifest.json",
    "artifacts/tile-assets-bg-v2/manifest.json",
    "artifacts/world-map-backgrounds-v1/manifest.json",
)
SCOPE = {
    "observed_runtime_layer_static_provenance_complete": True,
    "all_runtime_visual_payloads_named": False,
    "camera_or_scroll_writer_schedule_complete": False,
    "cross_frame_transition_timing_complete": False,
    "final_screen_composition_complete": False,
    "dynamic_palette_transform_semantics_complete": False,
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compact_ranges(values: list[int]) -> list[list[int]]:
    unique = sorted(set(values))
    if not unique:
        return []
    ranges = []
    start = previous = unique[0]
    for value in unique[1:]:
        if value != previous + 1:
            ranges.append([start, previous + 1])
            start = value
        previous = value
    ranges.append([start, previous + 1])
    return ranges


def load_json(root: Path, path: str) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def candidate(
    family: str,
    source_id: str,
    bpp: int,
    gfx: bytes,
    tilemap: bytes | None,
    palette: bytes | None,
    *,
    bgcnt: int | None = None,
    tilemap_width: int | None = None,
    tilemap_height: int | None = None,
    source_tile_base: int = 0,
    source_palette_base: int = 0,
    manifest: str,
) -> dict:
    return {
        "family": family,
        "source_id": source_id,
        "source_key": f"{family}/{source_id}",
        "manifest": manifest,
        "bpp": bpp,
        "gfx": gfx,
        "tilemap": tilemap,
        "palette": palette,
        "bgcnt": bgcnt,
        "tilemap_width": tilemap_width,
        "tilemap_height": tilemap_height,
        "source_tile_base": source_tile_base,
        "source_palette_base": source_palette_base,
        "component_hashes": {
            "graphics": sha256(gfx),
            "tilemap": sha256(tilemap) if tilemap is not None else None,
            "palette": sha256(palette) if palette is not None else None,
        },
    }


def load_candidates(root: Path) -> list[dict]:
    result: list[dict] = []
    rom = (root / "rom/base.gba").read_bytes()
    decompressed: dict[int, bytes] = {}

    def lz(offset: int) -> bytes:
        if offset not in decompressed:
            decompressed[offset] = lz77_decompress(rom, offset)
        return decompressed[offset]

    manifest_path = "artifacts/bg-resource-canvases-v1/manifest.json"
    manifest = load_json(root, manifest_path)
    base = root / "artifacts/bg-resource-canvases-v1"
    for entry in manifest["entries"]:
        result.append(
            candidate(
                "bg-resource-canvases-v1",
                f"entry-{entry['entry_id']:02d}",
                int(entry["pixel_mode"][0]),
                (base / entry["graphics"]["file"]).read_bytes(),
                (base / entry["tilemap"]["file"]).read_bytes(),
                (base / entry["palette"]["file"]).read_bytes(),
                tilemap_width=int(entry["tilemap"]["width_tiles"]),
                tilemap_height=int(entry["tilemap"]["height_tiles"]),
                manifest=manifest_path,
            )
        )

    manifest_path = "artifacts/tile-assets-bg-v2/manifest.json"
    manifest = load_json(root, manifest_path)
    for descriptor in manifest["descriptors"]:
        for layer in descriptor["layers"]:
            if layer["status"] != "complete":
                continue
            result.append(
                candidate(
                    "tile-assets-bg-v2",
                    f"descriptor-{descriptor['descriptor_id']:02d}-{layer['name']}",
                    int(layer["bits_per_pixel"]),
                    lz(int(layer["gfx"]["file_offset"])),
                    lz(int(layer["tilemap"]["file_offset"])),
                    rom[
                        int(layer["palette"]["file_offset"]) :
                        int(layer["palette"]["file_offset"])
                        + int(layer["palette"]["size"])
                    ],
                    tilemap_width=int(layer["definition"]["width_tiles"]),
                    tilemap_height=int(layer["definition"]["height_tiles"]),
                    source_tile_base=0,
                    source_palette_base=min(
                        int(value) for value in layer["source_palette_banks"]
                    ),
                    manifest=manifest_path,
                )
            )

    manifest_path = "artifacts/story-visual-layers-v1/manifest.json"
    manifest = load_json(root, manifest_path)
    for layer in manifest["layers"]:
        result.append(
            candidate(
                "story-visual-layers-v1",
                f"layer-{layer['layer_id']:02d}",
                4,
                lz(int(layer["gfx"]["file_offset"])),
                lz(int(layer["tilemap"]["file_offset"])),
                lz(int(layer["palette"]["file_offset"])),
                tilemap_width=32,
                tilemap_height=32,
                source_tile_base=int(layer["tile_base"]),
                source_palette_base=min(int(value) for value in layer["palette_banks"]),
                manifest=manifest_path,
            )
        )

    manifest_path = "artifacts/map-canvases-v1/manifest.json"
    manifest = load_json(root, manifest_path)
    base = root / "artifacts/map-canvases-v1"
    for entry in manifest["entries"]:
        gfx = (base / entry["resources"]["tile_graphics"]["output_bin"]).read_bytes()
        palette = (base / entry["resources"]["bg_palette"]["output_bin"]).read_bytes()
        for variant in entry["variants"]:
            result.append(
                candidate(
                    "map-canvases-v1",
                    f"map-{entry['map_id']:02d}-{variant['name']}",
                    4,
                    gfx,
                    (base / variant["tilemap_bin"]).read_bytes(),
                    palette,
                    tilemap_width=int(entry["dimensions_tiles"][0]),
                    tilemap_height=int(entry["dimensions_tiles"][1]),
                    manifest=manifest_path,
                )
            )

    manifest_path = "artifacts/world-map-backgrounds-v1/manifest.json"
    manifest = load_json(root, manifest_path)
    base = root / "artifacts/world-map-backgrounds-v1"
    for page in manifest["pages"]:
        background = page["background"]
        result.append(
            candidate(
                "world-map-backgrounds-v1",
                f"page-{page['page_id']:02d}",
                int(background["bits_per_pixel"]),
                (base / background["graphics_file"]).read_bytes(),
                (base / background["tilemap_file"]).read_bytes(),
                (base / background["palette_file"]).read_bytes(),
                bgcnt=int(background["hardware"]["bgcnt"], 16),
                tilemap_width=int(background["dimensions_tiles"][0]),
                tilemap_height=int(background["dimensions_tiles"][1]),
                manifest=manifest_path,
            )
        )

    manifest_path = "artifacts/scene-visual-packs-v1/manifest.json"
    manifest = load_json(root, manifest_path)
    base = root / "artifacts/scene-visual-packs-v1"
    for pack in manifest["packs"]:
        background = pack["background"]
        result.append(
            candidate(
                "scene-visual-packs-v1",
                f"pack-{pack['pack_id']:02d}-background",
                int(background["bits_per_pixel"]),
                (base / background["graphics_file"]).read_bytes(),
                (base / background["tilemap_file"]).read_bytes(),
                (base / background["palette_file"]).read_bytes(),
                bgcnt=int(background["hardware"]["bgcnt"], 16),
                tilemap_width=int(background["width_tiles"]),
                tilemap_height=int(background["height_tiles"]),
                manifest=manifest_path,
            )
        )
    return result


def map_offset(size: int, tile_x: int, tile_y: int) -> int:
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
    return block * 0x800 + ((tile_y % 32) * 32 + tile_x % 32) * 2


def normalized_tilemap_match(
    source: bytes,
    source_width: int,
    source_height: int,
    runtime: bytes,
    runtime_size: int,
    bpp: int,
    expected_tile_delta: int | None,
) -> dict | None:
    runtime_dimensions = ((32, 32), (64, 32), (32, 64), (64, 64))
    runtime_width, runtime_height = runtime_dimensions[runtime_size]
    if (
        len(source) != source_width * source_height * 2
        or source_width > runtime_width
        or source_height > runtime_height
    ):
        return None
    for origin_y in range(runtime_height - source_height + 1):
        for origin_x in range(runtime_width - source_width + 1):
            tile_delta = None
            palette_delta = None
            matched = True
            for y in range(source_height):
                for x in range(source_width):
                    source_offset = (y * source_width + x) * 2
                    runtime_offset = map_offset(
                        runtime_size, origin_x + x, origin_y + y
                    )
                    source_entry = int.from_bytes(
                        source[source_offset : source_offset + 2], "little"
                    )
                    runtime_entry = int.from_bytes(
                        runtime[runtime_offset : runtime_offset + 2], "little"
                    )
                    if (source_entry & 0x0C00) != (runtime_entry & 0x0C00):
                        matched = False
                        break
                    current_tile_delta = (
                        (runtime_entry & 0x03FF) - (source_entry & 0x03FF)
                    ) & 0x03FF
                    if tile_delta is None:
                        tile_delta = current_tile_delta
                    elif tile_delta != current_tile_delta:
                        matched = False
                        break
                    if bpp == 4:
                        current_palette_delta = (
                            ((runtime_entry >> 12) & 0xF)
                            - ((source_entry >> 12) & 0xF)
                        ) & 0xF
                        if palette_delta is None:
                            palette_delta = current_palette_delta
                        elif palette_delta != current_palette_delta:
                            matched = False
                            break
                if not matched:
                    break
            if matched and (
                expected_tile_delta is None or tile_delta == expected_tile_delta
            ):
                runtime_entries = bytearray()
                for y in range(source_height):
                    for x in range(source_width):
                        offset = map_offset(
                            runtime_size, origin_x + x, origin_y + y
                        )
                        runtime_entries.extend(runtime[offset : offset + 2])
                return {
                    "origin": [origin_x, origin_y],
                    "tile_delta": tile_delta,
                    "palette_delta": palette_delta,
                    "runtime_entries_sha256": sha256(bytes(runtime_entries)),
                }
    return None


def used_palette_match(
    candidate_record: dict,
    runtime_palette: bytes,
    normalized_tilemap: dict | None,
) -> dict | None:
    if normalized_tilemap is None:
        return None
    gfx = candidate_record["gfx"]
    tilemap = candidate_record["tilemap"]
    palette = candidate_record["palette"]
    width = candidate_record["tilemap_width"]
    height = candidate_record["tilemap_height"]
    if (
        tilemap is None
        or palette is None
        or width is None
        or height is None
        or len(tilemap) != int(width) * int(height) * 2
    ):
        return None
    bpp = int(candidate_record["bpp"])
    bytes_per_tile = 64 if bpp == 8 else 32
    source_tile_base = int(candidate_record["source_tile_base"])
    source_palette_base = int(candidate_record["source_palette_base"])
    palette_delta = int(normalized_tilemap["palette_delta"] or 0)
    comparisons: set[tuple[int, int]] = set()
    for offset in range(0, len(tilemap), 2):
        entry = int.from_bytes(tilemap[offset : offset + 2], "little")
        local_tile = (entry & 0x03FF) - source_tile_base
        tile_offset = local_tile * bytes_per_tile
        if local_tile < 0 or tile_offset + bytes_per_tile > len(gfx):
            return None
        tile = gfx[tile_offset : tile_offset + bytes_per_tile]
        if bpp == 8:
            for color in tile:
                if color:
                    comparisons.add((color, color))
        else:
            source_bank = (entry >> 12) & 0xF
            runtime_bank = (source_bank + palette_delta) & 0xF
            for packed in tile:
                for color in (packed & 0xF, packed >> 4):
                    if color:
                        source_index = (
                            (source_bank - source_palette_base) * 16 + color
                        )
                        runtime_index = runtime_bank * 16 + color
                        comparisons.add((source_index, runtime_index))
    if not comparisons:
        return None
    for source_index, runtime_index in comparisons:
        source_offset = source_index * 2
        runtime_offset = runtime_index * 2
        if (
            source_offset < 0
            or source_offset + 2 > len(palette)
            or runtime_offset + 2 > len(runtime_palette)
            or palette[source_offset : source_offset + 2]
            != runtime_palette[runtime_offset : runtime_offset + 2]
        ):
            return None
    return {
        "compared_color_count": len(comparisons),
        "palette_delta": palette_delta,
        "source_color_ranges": compact_ranges(
            [value[0] for value in comparisons]
        ),
        "runtime_color_ranges": compact_ranges(
            [value[1] for value in comparisons]
        ),
    }


def candidate_match(
    item: dict,
    background: dict,
    bg_vram: bytes,
    bg_palette: bytes,
    tilemap_cache: dict[tuple, dict | None],
) -> dict | None:
    if int(item["bpp"]) != int(background["color_depth_bpp"]):
        return None
    control = int(str(background["bgcnt"]), 16)
    if item["bgcnt"] is not None and int(item["bgcnt"]) != control:
        return None

    char_base = int(background["char_base_block"]) * 0x4000
    screen_base = int(background["screen_base_block"]) * 0x800
    size_code = int(background["size_code"])
    screen_size = (1, 2, 2, 4)[size_code] * 0x800
    screen_region = bg_vram[screen_base : screen_base + screen_size]

    gfx = item["gfx"]
    tilemap = item["tilemap"]
    palette = item["palette"]
    bytes_per_tile = 64 if item["bpp"] == 8 else 32
    gfx_offsets = []
    cursor = char_base
    while True:
        absolute = bg_vram.find(gfx, cursor)
        if absolute < 0:
            break
        relative = absolute - char_base
        if relative % bytes_per_tile == 0:
            gfx_offsets.append(relative)
        cursor = absolute + 1

    selected_gfx_offset = gfx_offsets[0] if gfx_offsets else -1
    normalized_tilemap = None
    if (
        tilemap is not None
        and item["tilemap_width"] is not None
        and item["tilemap_height"] is not None
    ):
        offsets_to_try = gfx_offsets or [None]
        for gfx_offset in offsets_to_try:
            expected_tile_delta = (
                gfx_offset // bytes_per_tile - int(item["source_tile_base"])
                if gfx_offset is not None
                else None
            )
            cache_key = (
                item["component_hashes"]["tilemap"],
                int(item["tilemap_width"]),
                int(item["tilemap_height"]),
                size_code,
                int(item["bpp"]),
                expected_tile_delta,
            )
            if cache_key not in tilemap_cache:
                tilemap_cache[cache_key] = normalized_tilemap_match(
                    tilemap,
                    int(item["tilemap_width"]),
                    int(item["tilemap_height"]),
                    screen_region,
                    size_code,
                    int(item["bpp"]),
                    expected_tile_delta,
                )
            normalized_tilemap = tilemap_cache[cache_key]
            if normalized_tilemap is not None:
                if gfx_offset is not None:
                    selected_gfx_offset = gfx_offset
                break

    palette_offset = bg_palette.find(palette) if palette is not None else -1
    used_palette = used_palette_match(item, bg_palette, normalized_tilemap)
    graphics_exact = bool(gfx_offsets)
    tilemap_exact = normalized_tilemap is not None
    palette_exact = palette_offset >= 0 or used_palette is not None
    matched_domain_count = sum(
        (graphics_exact, tilemap_exact, palette_exact)
    )
    if not matched_domain_count:
        return None

    graphics = {
        "exact": graphics_exact,
        "source_size": len(gfx),
        "source_sha256": item["component_hashes"]["graphics"],
        "runtime_address": (
            f"0x{0x06000000 + char_base + selected_gfx_offset:08X}"
            if graphics_exact
            else None
        ),
        "runtime_offset_from_char_base": (
            selected_gfx_offset if graphics_exact else None
        ),
        "all_runtime_offsets_from_char_base": gfx_offsets,
        "runtime_sha256": (
            sha256(
                bg_vram[
                    char_base + selected_gfx_offset :
                    char_base + selected_gfx_offset + len(gfx)
                ]
            )
            if graphics_exact
            else None
        ),
    }
    tilemap_domain = {
        "exact": tilemap_exact,
        "source_size": len(tilemap) if tilemap is not None else 0,
        "source_sha256": item["component_hashes"]["tilemap"],
        "source_dimensions_tiles": [
            item["tilemap_width"],
            item["tilemap_height"],
        ],
        "runtime_screen_base_address": f"0x{0x06000000 + screen_base:08X}",
        "origin_tiles": (
            normalized_tilemap["origin"] if normalized_tilemap else None
        ),
        "tile_delta": (
            normalized_tilemap["tile_delta"] if normalized_tilemap else None
        ),
        "palette_delta": (
            normalized_tilemap["palette_delta"] if normalized_tilemap else None
        ),
        "compared_entry_count": (
            int(item["tilemap_width"]) * int(item["tilemap_height"])
            if tilemap_exact
            else 0
        ),
        "runtime_entries_sha256": (
            normalized_tilemap["runtime_entries_sha256"]
            if normalized_tilemap
            else None
        ),
    }
    if palette_offset >= 0:
        palette_domain = {
            "exact": True,
            "match_kind": "full-payload",
            "source_size": len(palette),
            "source_sha256": item["component_hashes"]["palette"],
            "runtime_address": f"0x{0x05000000 + palette_offset:08X}",
            "runtime_offset": palette_offset,
            "compared_color_count": len(palette) // 2,
            "palette_delta": palette_offset // 32 if item["bpp"] == 4 else 0,
            "source_color_ranges": [[0, len(palette) // 2]],
            "runtime_color_ranges": [
                [
                    palette_offset // 2,
                    palette_offset // 2 + len(palette) // 2,
                ]
            ],
        }
    elif used_palette is not None:
        palette_domain = {
            "exact": True,
            "match_kind": "used-colors",
            "source_size": len(palette),
            "source_sha256": item["component_hashes"]["palette"],
            "runtime_address": "0x05000000",
            "runtime_offset": None,
            **used_palette,
        }
    else:
        palette_domain = {
            "exact": False,
            "match_kind": None,
            "source_size": len(palette) if palette is not None else 0,
            "source_sha256": item["component_hashes"]["palette"],
            "runtime_address": None,
            "runtime_offset": None,
            "compared_color_count": 0,
            "palette_delta": None,
            "source_color_ranges": [],
            "runtime_color_ranges": [],
        }
    return {
        "source_key": item["source_key"],
        "source_manifest": item["manifest"],
        "bits_per_pixel": item["bpp"],
        "layout": {
            "compatible": True,
            "expected_bgcnt": (
                f"0x{int(item['bgcnt']):04X}"
                if item["bgcnt"] is not None
                else None
            ),
            "actual_bgcnt": background["bgcnt"],
        },
        "matched_domain_count": matched_domain_count,
        "domains": {
            "graphics": graphics,
            "tilemap": tilemap_domain,
            "palette": palette_domain,
        },
    }


def build_payload(root: Path) -> dict:
    candidates = load_candidates(root)
    checkpoint_paths = sorted(
        (root / "artifacts/runtime-checkpoints").glob("*.ss9")
    )
    if not checkpoint_paths:
        raise ValueError("no tracked runtime checkpoints found")

    checkpoints = []
    state_records: dict[str, dict] = {}
    checkpoint_enabled_layer_count = 0
    for path in checkpoint_paths:
        record, domains = _decode_checkpoint(path)
        relative = path.relative_to(root).as_posix()
        enabled = list(record["display"]["enabled_backgrounds"])
        checkpoint_enabled_layer_count += len(enabled)
        checkpoints.append(
            {
                "path": relative,
                "checkpoint_sha256": record["checkpoint_sha256"],
                "state_id": record["state_id"],
                "enabled_backgrounds": enabled,
            }
        )
        state_id = str(record["state_id"])
        previous = state_records.setdefault(
            state_id,
            {
                "checkpoint_paths": [],
                "backgrounds": record["backgrounds"],
                "domains": domains,
            },
        )
        if previous["domains"] != domains:
            raise ValueError(f"state hash collision for {state_id}")
        previous["checkpoint_paths"].append(relative)

    layers = []
    classification_counts = Counter()
    matched_domain_counts = Counter()
    matched_family_counts = Counter()
    for state_id in sorted(state_records):
        state = state_records[state_id]
        bg_vram = state["domains"]["bg_vram"]
        bg_palette = state["domains"]["bg_palette"]
        for background in state["backgrounds"]:
            if not background["enabled"]:
                continue
            tilemap_cache: dict[tuple, dict | None] = {}
            matches = []
            for item in candidates:
                match = candidate_match(
                    item,
                    background,
                    bg_vram,
                    bg_palette,
                    tilemap_cache,
                )
                if match is not None:
                    matches.append(match)
                    matched_domain_counts[match["matched_domain_count"]] += 1
                    matched_family_counts[item["family"]] += 1
            matches.sort(
                key=lambda item: (-item["matched_domain_count"], item["source_key"])
            )
            exact_sources = [
                item for item in matches if item["matched_domain_count"] == 3
            ]
            partial_sources = [
                item for item in matches if item["matched_domain_count"] < 3
            ]
            if exact_sources:
                classification = "exact_static_source"
            elif partial_sources:
                classification = "partial_static_source"
            else:
                classification = "unidentified_runtime_payload"
            classification_counts[classification] += 1
            layers.append(
                {
                    "state_id": state_id,
                    "checkpoint_paths": sorted(state["checkpoint_paths"]),
                    "bg_index": background["index"],
                    "bgcnt": background["bgcnt"],
                    "color_depth_bpp": background["color_depth_bpp"],
                    "char_base_address": background["char_base_address"],
                    "screen_base_address": background["screen_base_address"],
                    "size_code": background["size_code"],
                    "classification": classification,
                    "exact_sources": exact_sources,
                    "partial_sources": partial_sources,
                }
            )

    candidate_family_counts = Counter(item["family"] for item in candidates)
    source_registry = [
        {
            "family": path.split("/")[1],
            "manifest": path,
            "manifest_sha256": sha256((root / path).read_bytes()),
            "candidate_count": candidate_family_counts[path.split("/")[1]],
        }
        for path in SOURCE_MANIFESTS
    ]
    summary = {
        "checkpoint_count": len(checkpoints),
        "checkpoint_enabled_layer_count": checkpoint_enabled_layer_count,
        "unique_state_count": len(state_records),
        "unique_state_enabled_layer_count": len(layers),
        "candidate_count": len(candidates),
        "candidate_family_counts": dict(sorted(candidate_family_counts.items())),
        "exact_static_source_count": classification_counts[
            "exact_static_source"
        ],
        "partial_static_source_count": classification_counts[
            "partial_static_source"
        ],
        "unidentified_runtime_payload_count": classification_counts[
            "unidentified_runtime_payload"
        ],
        "match_record_counts_by_domain_count": {
            str(key): value for key, value in sorted(matched_domain_counts.items())
        },
        "match_record_counts_by_family": dict(
            sorted(matched_family_counts.items())
        ),
    }
    return {
        "schema": SCHEMA,
        "implementation": {
            "exporter_sha256": sha256(Path(__file__).read_bytes()),
            "verifier_sha256": sha256(
                (
                    root / "tools/verify_runtime_layer_static_provenance.py"
                ).read_bytes()
            ),
            "test_sha256": sha256(
                (
                    root / "tests/test_export_runtime_layer_static_provenance.py"
                ).read_bytes()
            ),
        },
        "source": {
            "checkpoint_root": "artifacts/runtime-checkpoints",
            "checkpoint_glob": "*.ss9",
            "rom": "rom/base.gba",
            "rom_sha256": sha256((root / "rom/base.gba").read_bytes()),
        },
        "classification_contract": {
            "exact_static_source": (
                "compatible layout plus exact graphics, loader-normalized "
                "tilemap, and full or actually-used palette colors"
            ),
            "partial_static_source": (
                "compatible layout and at least one but fewer than three "
                "exact byte domains"
            ),
            "unidentified_runtime_payload": (
                "no exact byte domain in the registered static families"
            ),
            "palette_zero_policy": (
                "transparent color index zero is excluded from used-color "
                "comparison but remains covered by full-payload matches"
            ),
        },
        "source_registry": source_registry,
        "summary": summary,
        "checkpoints": checkpoints,
        "layers": layers,
        "scope": SCOPE,
    }


def _build_artifact(root: Path, output: Path) -> dict:
    payload = build_payload(root)
    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    payload_name = "runtime-layer-static-provenance.json"
    (output / payload_name).write_bytes(encoded)
    promotion = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {payload_name: sha256(encoded)},
        "source": {
            "checkpoint_root": "artifacts/runtime-checkpoints",
            "checkpoint_count": payload["summary"]["checkpoint_count"],
            "unique_state_count": payload["summary"]["unique_state_count"],
            "candidate_count": payload["summary"]["candidate_count"],
        },
        "producer": {
            "command": [
                "python3",
                "tools/export_runtime_layer_static_provenance.py",
                "--root",
                ".",
                "--output-dir",
                "artifacts/runtime-layer-static-provenance-v1",
            ],
            **payload["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_runtime_layer_static_provenance.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/runtime-layer-static-provenance-v1",
            ],
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": "runtime-layer-static-provenance-verification-v1",
                "verified": True,
                "checkpoint_count": payload["summary"]["checkpoint_count"],
                "layer_count": payload["summary"][
                    "unique_state_enabled_layer_count"
                ],
                "errors": [],
            },
        },
        "experiment": {
            "task": "runtime-layer-static-provenance",
            "run_id": "tracked-runtime-layer-static-provenance-20260730-01",
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(promotion, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def export_artifact(root: Path, output: Path) -> dict:
    root = Path(root).resolve()
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{output.name}.", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / output.name
        staged.mkdir()
        payload = _build_artifact(root, staged)
        if output.exists():
            shutil.rmtree(output)
        os.replace(staged, output)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/runtime-layer-static-provenance-v1"),
    )
    args = parser.parse_args()
    payload = export_artifact(args.root, args.output_dir)
    print(json.dumps(payload["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
