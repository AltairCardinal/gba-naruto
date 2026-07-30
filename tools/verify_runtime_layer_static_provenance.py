#!/usr/bin/env python3
"""Independently verify runtime-layer-static-provenance-v1."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import zlib


SCHEMA = "runtime-layer-static-provenance-v1"
VERIFY_SCHEMA = "runtime-layer-static-provenance-verification-v1"
STATE_SIZE = 0x61000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
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


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


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


def _checkpoint(path: Path) -> tuple[dict, dict[str, bytes]]:
    state = _state(path)
    io = _memory(state, 0x04000000, 0x400)
    pram = _memory(state, 0x05000000, 0x400)
    vram = _memory(state, 0x06000000, 0x18000)
    dispcnt = _u16(io, 0)
    if dispcnt & 7 or dispcnt & 0x80:
        raise ValueError(f"{path.name}: expected visible Mode 0")
    enabled = [index for index in range(4) if dispcnt & (1 << (8 + index))]
    backgrounds = []
    for index in range(4):
        control = _u16(io, 8 + index * 2)
        char_block = (control >> 2) & 3
        screen_block = (control >> 8) & 31
        backgrounds.append(
            {
                "index": index,
                "enabled": index in enabled,
                "bgcnt": f"0x{control:04X}",
                "color_depth_bpp": 8 if control & 0x80 else 4,
                "char_base_block": char_block,
                "char_base_address": f"0x{0x06000000 + char_block * 0x4000:08X}",
                "screen_base_block": screen_block,
                "screen_base_address": (
                    f"0x{0x06000000 + screen_block * 0x800:08X}"
                ),
                "size_code": (control >> 14) & 3,
            }
        )
    bg_palette, bg_vram = pram[:0x200], vram[:0x10000]
    state_id = _sha(io[:0x58] + bg_palette + bg_vram)
    return (
        {
            "checkpoint_sha256": _sha(path.read_bytes()),
            "state_id": state_id,
            "enabled_backgrounds": enabled,
            "backgrounds": backgrounds,
        },
        {"bg_palette": bg_palette, "bg_vram": bg_vram},
    )


def _lz(data: bytes, offset: int) -> bytes:
    if offset < 0 or offset + 4 > len(data) or data[offset] != 0x10:
        raise ValueError(f"not LZ77 at 0x{offset:06X}")
    expected = int.from_bytes(data[offset + 1 : offset + 4], "little")
    output = bytearray()
    cursor = offset + 4
    while len(output) < expected:
        if cursor >= len(data):
            raise ValueError("truncated LZ77 flags")
        flags = data[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(output) >= expected:
                break
            if flags & (1 << bit):
                if cursor + 2 > len(data):
                    raise ValueError("truncated LZ77 reference")
                length = (data[cursor] >> 4) + 3
                distance = (
                    ((data[cursor] & 15) << 8) | data[cursor + 1]
                ) + 1
                cursor += 2
                if distance > len(output) or len(output) + length > expected:
                    raise ValueError("invalid LZ77 reference")
                for _ in range(length):
                    output.append(output[-distance])
            else:
                if cursor >= len(data):
                    raise ValueError("truncated LZ77 literal")
                output.append(data[cursor])
                cursor += 1
    return bytes(output)


def _json(root: Path, path: str) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def _candidate(
    family: str,
    source_id: str,
    bpp: int,
    gfx: bytes,
    tilemap: bytes | None,
    palette: bytes | None,
    *,
    manifest: str,
    bgcnt: int | None = None,
    tilemap_width: int | None = None,
    tilemap_height: int | None = None,
    source_tile_base: int = 0,
    source_palette_base: int = 0,
) -> dict:
    return {
        "family": family,
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
        "hashes": {
            "graphics": _sha(gfx),
            "tilemap": _sha(tilemap) if tilemap is not None else None,
            "palette": _sha(palette) if palette is not None else None,
        },
    }


def _candidates(root: Path) -> list[dict]:
    result = []
    rom = (root / "rom/base.gba").read_bytes()
    cache: dict[int, bytes] = {}

    def lz(offset: int) -> bytes:
        if offset not in cache:
            cache[offset] = _lz(rom, offset)
        return cache[offset]

    manifest_path = "artifacts/bg-resource-canvases-v1/manifest.json"
    manifest = _json(root, manifest_path)
    base = root / "artifacts/bg-resource-canvases-v1"
    for entry in manifest["entries"]:
        result.append(
            _candidate(
                "bg-resource-canvases-v1",
                f"entry-{entry['entry_id']:02d}",
                int(entry["pixel_mode"][0]),
                (base / entry["graphics"]["file"]).read_bytes(),
                (base / entry["tilemap"]["file"]).read_bytes(),
                (base / entry["palette"]["file"]).read_bytes(),
                manifest=manifest_path,
                tilemap_width=int(entry["tilemap"]["width_tiles"]),
                tilemap_height=int(entry["tilemap"]["height_tiles"]),
            )
        )

    manifest_path = "artifacts/tile-assets-bg-v2/manifest.json"
    manifest = _json(root, manifest_path)
    for descriptor in manifest["descriptors"]:
        for layer in descriptor["layers"]:
            if layer["status"] != "complete":
                continue
            palette_offset = int(layer["palette"]["file_offset"])
            palette_size = int(layer["palette"]["size"])
            result.append(
                _candidate(
                    "tile-assets-bg-v2",
                    f"descriptor-{descriptor['descriptor_id']:02d}-{layer['name']}",
                    int(layer["bits_per_pixel"]),
                    lz(int(layer["gfx"]["file_offset"])),
                    lz(int(layer["tilemap"]["file_offset"])),
                    rom[palette_offset : palette_offset + palette_size],
                    manifest=manifest_path,
                    tilemap_width=int(layer["definition"]["width_tiles"]),
                    tilemap_height=int(layer["definition"]["height_tiles"]),
                    source_palette_base=min(
                        int(value) for value in layer["source_palette_banks"]
                    ),
                )
            )

    manifest_path = "artifacts/story-visual-layers-v1/manifest.json"
    manifest = _json(root, manifest_path)
    for layer in manifest["layers"]:
        result.append(
            _candidate(
                "story-visual-layers-v1",
                f"layer-{layer['layer_id']:02d}",
                4,
                lz(int(layer["gfx"]["file_offset"])),
                lz(int(layer["tilemap"]["file_offset"])),
                lz(int(layer["palette"]["file_offset"])),
                manifest=manifest_path,
                tilemap_width=32,
                tilemap_height=32,
                source_tile_base=int(layer["tile_base"]),
                source_palette_base=min(
                    int(value) for value in layer["palette_banks"]
                ),
            )
        )

    manifest_path = "artifacts/map-canvases-v1/manifest.json"
    manifest = _json(root, manifest_path)
    base = root / "artifacts/map-canvases-v1"
    for entry in manifest["entries"]:
        gfx = (base / entry["resources"]["tile_graphics"]["output_bin"]).read_bytes()
        palette = (base / entry["resources"]["bg_palette"]["output_bin"]).read_bytes()
        for variant in entry["variants"]:
            result.append(
                _candidate(
                    "map-canvases-v1",
                    f"map-{entry['map_id']:02d}-{variant['name']}",
                    4,
                    gfx,
                    (base / variant["tilemap_bin"]).read_bytes(),
                    palette,
                    manifest=manifest_path,
                    tilemap_width=int(entry["dimensions_tiles"][0]),
                    tilemap_height=int(entry["dimensions_tiles"][1]),
                )
            )

    manifest_path = "artifacts/world-map-backgrounds-v1/manifest.json"
    manifest = _json(root, manifest_path)
    base = root / "artifacts/world-map-backgrounds-v1"
    for page in manifest["pages"]:
        background = page["background"]
        result.append(
            _candidate(
                "world-map-backgrounds-v1",
                f"page-{page['page_id']:02d}",
                int(background["bits_per_pixel"]),
                (base / background["graphics_file"]).read_bytes(),
                (base / background["tilemap_file"]).read_bytes(),
                (base / background["palette_file"]).read_bytes(),
                manifest=manifest_path,
                bgcnt=int(background["hardware"]["bgcnt"], 16),
                tilemap_width=int(background["dimensions_tiles"][0]),
                tilemap_height=int(background["dimensions_tiles"][1]),
            )
        )

    manifest_path = "artifacts/scene-visual-packs-v1/manifest.json"
    manifest = _json(root, manifest_path)
    base = root / "artifacts/scene-visual-packs-v1"
    for pack in manifest["packs"]:
        background = pack["background"]
        result.append(
            _candidate(
                "scene-visual-packs-v1",
                f"pack-{pack['pack_id']:02d}-background",
                int(background["bits_per_pixel"]),
                (base / background["graphics_file"]).read_bytes(),
                (base / background["tilemap_file"]).read_bytes(),
                (base / background["palette_file"]).read_bytes(),
                manifest=manifest_path,
                bgcnt=int(background["hardware"]["bgcnt"], 16),
                tilemap_width=int(background["width_tiles"]),
                tilemap_height=int(background["height_tiles"]),
            )
        )
    return result


def _map_offset(size: int, x: int, y: int) -> int:
    if size == 0:
        block = 0
    elif size == 1:
        block = x // 32
    elif size == 2:
        block = y // 32
    else:
        block = x // 32 + (y // 32) * 2
    return block * 0x800 + ((y % 32) * 32 + x % 32) * 2


def _tilemap_match(
    source: bytes,
    width: int,
    height: int,
    runtime: bytes,
    size_code: int,
    bpp: int,
    expected_tile_delta: int | None,
) -> dict | None:
    runtime_width, runtime_height = (
        (32, 32),
        (64, 32),
        (32, 64),
        (64, 64),
    )[size_code]
    if (
        len(source) != width * height * 2
        or width > runtime_width
        or height > runtime_height
    ):
        return None
    for origin_y in range(runtime_height - height + 1):
        for origin_x in range(runtime_width - width + 1):
            tile_delta = None
            palette_delta = None
            valid = True
            for y in range(height):
                for x in range(width):
                    source_offset = (y * width + x) * 2
                    runtime_offset = _map_offset(
                        size_code, origin_x + x, origin_y + y
                    )
                    source_entry = _u16(source, source_offset)
                    runtime_entry = _u16(runtime, runtime_offset)
                    if source_entry & 0x0C00 != runtime_entry & 0x0C00:
                        valid = False
                        break
                    current_tile_delta = (
                        (runtime_entry & 0x03FF) - (source_entry & 0x03FF)
                    ) & 0x03FF
                    if tile_delta is None:
                        tile_delta = current_tile_delta
                    elif tile_delta != current_tile_delta:
                        valid = False
                        break
                    if bpp == 4:
                        current_palette_delta = (
                            ((runtime_entry >> 12) & 15)
                            - ((source_entry >> 12) & 15)
                        ) & 15
                        if palette_delta is None:
                            palette_delta = current_palette_delta
                        elif palette_delta != current_palette_delta:
                            valid = False
                            break
                if not valid:
                    break
            if valid and (
                expected_tile_delta is None
                or tile_delta == expected_tile_delta
            ):
                runtime_entries = bytearray()
                for y in range(height):
                    for x in range(width):
                        offset = _map_offset(
                            size_code, origin_x + x, origin_y + y
                        )
                        runtime_entries.extend(runtime[offset : offset + 2])
                return {
                    "origin": [origin_x, origin_y],
                    "tile_delta": tile_delta,
                    "palette_delta": palette_delta,
                    "runtime_entries_sha256": _sha(bytes(runtime_entries)),
                }
    return None


def _used_palette(
    item: dict,
    runtime_palette: bytes,
    tilemap_match: dict | None,
) -> dict | None:
    if tilemap_match is None:
        return None
    gfx, tilemap, palette = item["gfx"], item["tilemap"], item["palette"]
    width, height = item["tilemap_width"], item["tilemap_height"]
    if (
        tilemap is None
        or palette is None
        or width is None
        or height is None
        or len(tilemap) != int(width) * int(height) * 2
    ):
        return None
    bpp = int(item["bpp"])
    tile_size = 64 if bpp == 8 else 32
    palette_delta = int(tilemap_match["palette_delta"] or 0)
    comparisons: set[tuple[int, int]] = set()
    for offset in range(0, len(tilemap), 2):
        entry = _u16(tilemap, offset)
        local_tile = (entry & 0x03FF) - int(item["source_tile_base"])
        gfx_offset = local_tile * tile_size
        if local_tile < 0 or gfx_offset + tile_size > len(gfx):
            return None
        tile = gfx[gfx_offset : gfx_offset + tile_size]
        if bpp == 8:
            for color in tile:
                if color:
                    comparisons.add((color, color))
        else:
            source_bank = (entry >> 12) & 15
            runtime_bank = (source_bank + palette_delta) & 15
            for packed in tile:
                for color in (packed & 15, packed >> 4):
                    if color:
                        source_index = (
                            source_bank - int(item["source_palette_base"])
                        ) * 16 + color
                        runtime_index = runtime_bank * 16 + color
                        comparisons.add((source_index, runtime_index))
    if not comparisons:
        return None
    for source_index, runtime_index in comparisons:
        source_offset, runtime_offset = source_index * 2, runtime_index * 2
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
        "source_color_ranges": _ranges([value[0] for value in comparisons]),
        "runtime_color_ranges": _ranges([value[1] for value in comparisons]),
    }


def _match(
    item: dict,
    background: dict,
    bg_vram: bytes,
    bg_palette: bytes,
    cache: dict[tuple, dict | None],
) -> dict | None:
    if int(item["bpp"]) != int(background["color_depth_bpp"]):
        return None
    control = int(background["bgcnt"], 16)
    if item["bgcnt"] is not None and int(item["bgcnt"]) != control:
        return None
    char_base = int(background["char_base_block"]) * 0x4000
    screen_base = int(background["screen_base_block"]) * 0x800
    size_code = int(background["size_code"])
    screen_size = (1, 2, 2, 4)[size_code] * 0x800
    screen = bg_vram[screen_base : screen_base + screen_size]

    gfx, tilemap, palette = item["gfx"], item["tilemap"], item["palette"]
    tile_size = 64 if item["bpp"] == 8 else 32
    gfx_offsets = []
    cursor = char_base
    while True:
        absolute = bg_vram.find(gfx, cursor)
        if absolute < 0:
            break
        relative = absolute - char_base
        if relative % tile_size == 0:
            gfx_offsets.append(relative)
        cursor = absolute + 1
    selected_gfx_offset = gfx_offsets[0] if gfx_offsets else -1
    tilemap_match = None
    if (
        tilemap is not None
        and item["tilemap_width"] is not None
        and item["tilemap_height"] is not None
    ):
        for gfx_offset in gfx_offsets or [None]:
            expected_delta = (
                gfx_offset // tile_size - int(item["source_tile_base"])
                if gfx_offset is not None
                else None
            )
            key = (
                item["hashes"]["tilemap"],
                int(item["tilemap_width"]),
                int(item["tilemap_height"]),
                size_code,
                int(item["bpp"]),
                expected_delta,
            )
            if key not in cache:
                cache[key] = _tilemap_match(
                    tilemap,
                    int(item["tilemap_width"]),
                    int(item["tilemap_height"]),
                    screen,
                    size_code,
                    int(item["bpp"]),
                    expected_delta,
                )
            tilemap_match = cache[key]
            if tilemap_match is not None:
                if gfx_offset is not None:
                    selected_gfx_offset = gfx_offset
                break
    palette_offset = bg_palette.find(palette) if palette is not None else -1
    used_palette = _used_palette(item, bg_palette, tilemap_match)
    flags = (
        bool(gfx_offsets),
        tilemap_match is not None,
        palette_offset >= 0 or used_palette is not None,
    )
    count = sum(flags)
    if not count:
        return None

    graphics_domain = {
        "exact": flags[0],
        "source_size": len(gfx),
        "source_sha256": item["hashes"]["graphics"],
        "runtime_address": (
            f"0x{0x06000000 + char_base + selected_gfx_offset:08X}"
            if flags[0]
            else None
        ),
        "runtime_offset_from_char_base": (
            selected_gfx_offset if flags[0] else None
        ),
        "all_runtime_offsets_from_char_base": gfx_offsets,
        "runtime_sha256": (
            _sha(
                bg_vram[
                    char_base + selected_gfx_offset :
                    char_base + selected_gfx_offset + len(gfx)
                ]
            )
            if flags[0]
            else None
        ),
    }
    tilemap_domain = {
        "exact": flags[1],
        "source_size": len(tilemap) if tilemap is not None else 0,
        "source_sha256": item["hashes"]["tilemap"],
        "source_dimensions_tiles": [
            item["tilemap_width"],
            item["tilemap_height"],
        ],
        "runtime_screen_base_address": f"0x{0x06000000 + screen_base:08X}",
        "origin_tiles": tilemap_match["origin"] if tilemap_match else None,
        "tile_delta": tilemap_match["tile_delta"] if tilemap_match else None,
        "palette_delta": (
            tilemap_match["palette_delta"] if tilemap_match else None
        ),
        "compared_entry_count": (
            int(item["tilemap_width"]) * int(item["tilemap_height"])
            if flags[1]
            else 0
        ),
        "runtime_entries_sha256": (
            tilemap_match["runtime_entries_sha256"] if tilemap_match else None
        ),
    }
    if palette_offset >= 0:
        color_count = len(palette) // 2
        palette_domain = {
            "exact": True,
            "match_kind": "full-payload",
            "source_size": len(palette),
            "source_sha256": item["hashes"]["palette"],
            "runtime_address": f"0x{0x05000000 + palette_offset:08X}",
            "runtime_offset": palette_offset,
            "compared_color_count": color_count,
            "palette_delta": palette_offset // 32 if item["bpp"] == 4 else 0,
            "source_color_ranges": [[0, color_count]],
            "runtime_color_ranges": [
                [
                    palette_offset // 2,
                    palette_offset // 2 + color_count,
                ]
            ],
        }
    elif used_palette is not None:
        palette_domain = {
            "exact": True,
            "match_kind": "used-colors",
            "source_size": len(palette),
            "source_sha256": item["hashes"]["palette"],
            "runtime_address": "0x05000000",
            "runtime_offset": None,
            **used_palette,
        }
    else:
        palette_domain = {
            "exact": False,
            "match_kind": None,
            "source_size": len(palette) if palette is not None else 0,
            "source_sha256": item["hashes"]["palette"],
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
        "matched_domain_count": count,
        "domains": {
            "graphics": graphics_domain,
            "tilemap": tilemap_domain,
            "palette": palette_domain,
        },
    }


def _expected(root: Path) -> tuple[dict, dict]:
    candidates = _candidates(root)
    checkpoint_paths = sorted(
        (root / "artifacts/runtime-checkpoints").glob("*.ss9")
    )
    checkpoints = []
    states: dict[str, dict] = {}
    checkpoint_enabled_count = 0
    for path in checkpoint_paths:
        record, domains = _checkpoint(path)
        relative = path.relative_to(root).as_posix()
        enabled = record["enabled_backgrounds"]
        checkpoint_enabled_count += len(enabled)
        checkpoints.append(
            {
                "path": relative,
                "checkpoint_sha256": record["checkpoint_sha256"],
                "state_id": record["state_id"],
                "enabled_backgrounds": enabled,
            }
        )
        previous = states.setdefault(
            record["state_id"],
            {
                "checkpoint_paths": [],
                "backgrounds": record["backgrounds"],
                "domains": domains,
            },
        )
        if previous["domains"] != domains:
            raise ValueError(f"state collision {record['state_id']}")
        previous["checkpoint_paths"].append(relative)

    layers = []
    classifications = Counter()
    domain_counts = Counter()
    family_counts = Counter()
    for state_id in sorted(states):
        state = states[state_id]
        for background in state["backgrounds"]:
            if not background["enabled"]:
                continue
            cache: dict[tuple, dict | None] = {}
            matches = []
            for item in candidates:
                match = _match(
                    item,
                    background,
                    state["domains"]["bg_vram"],
                    state["domains"]["bg_palette"],
                    cache,
                )
                if match is not None:
                    matches.append(match)
                    domain_counts[match["matched_domain_count"]] += 1
                    family_counts[item["family"]] += 1
            matches.sort(
                key=lambda item: (-item["matched_domain_count"], item["source_key"])
            )
            exact = [
                item for item in matches if item["matched_domain_count"] == 3
            ]
            partial = [
                item for item in matches if item["matched_domain_count"] < 3
            ]
            if exact:
                classification = "exact_static_source"
            elif partial:
                classification = "partial_static_source"
            else:
                classification = "unidentified_runtime_payload"
            classifications[classification] += 1
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
                    "exact_sources": exact,
                    "partial_sources": partial,
                }
            )

    candidate_family_counts = Counter(item["family"] for item in candidates)
    registry = [
        {
            "family": path.split("/")[1],
            "manifest": path,
            "manifest_sha256": _sha((root / path).read_bytes()),
            "candidate_count": candidate_family_counts[path.split("/")[1]],
        }
        for path in SOURCE_MANIFESTS
    ]
    summary = {
        "checkpoint_count": len(checkpoints),
        "checkpoint_enabled_layer_count": checkpoint_enabled_count,
        "unique_state_count": len(states),
        "unique_state_enabled_layer_count": len(layers),
        "candidate_count": len(candidates),
        "candidate_family_counts": dict(sorted(candidate_family_counts.items())),
        "exact_static_source_count": classifications["exact_static_source"],
        "partial_static_source_count": classifications["partial_static_source"],
        "unidentified_runtime_payload_count": classifications[
            "unidentified_runtime_payload"
        ],
        "match_record_counts_by_domain_count": {
            str(key): value for key, value in sorted(domain_counts.items())
        },
        "match_record_counts_by_family": dict(sorted(family_counts.items())),
    }
    payload = {
        "schema": SCHEMA,
        "implementation": {
            "exporter_sha256": _sha(
                (
                    root / "tools/export_runtime_layer_static_provenance.py"
                ).read_bytes()
            ),
            "verifier_sha256": _sha(Path(__file__).read_bytes()),
            "test_sha256": _sha(
                (
                    root / "tests/test_export_runtime_layer_static_provenance.py"
                ).read_bytes()
            ),
        },
        "source": {
            "checkpoint_root": "artifacts/runtime-checkpoints",
            "checkpoint_glob": "*.ss9",
            "rom": "rom/base.gba",
            "rom_sha256": _sha((root / "rom/base.gba").read_bytes()),
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
        "source_registry": registry,
        "summary": summary,
        "checkpoints": checkpoints,
        "layers": layers,
        "scope": SCOPE,
    }
    payload_bytes = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    promotion = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {
            "runtime-layer-static-provenance.json": _sha(payload_bytes)
        },
        "source": {
            "checkpoint_root": "artifacts/runtime-checkpoints",
            "checkpoint_count": summary["checkpoint_count"],
            "unique_state_count": summary["unique_state_count"],
            "candidate_count": summary["candidate_count"],
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
                "schema": VERIFY_SCHEMA,
                "verified": True,
                "checkpoint_count": summary["checkpoint_count"],
                "layer_count": summary["unique_state_enabled_layer_count"],
                "errors": [],
            },
        },
        "experiment": {
            "task": "runtime-layer-static-provenance",
            "run_id": "tracked-runtime-layer-static-provenance-20260730-01",
        },
    }
    return payload, promotion


def verify_artifact(root: Path, artifact: Path) -> dict:
    root, artifact = Path(root).resolve(), Path(artifact).resolve()
    errors = []
    try:
        expected, expected_promotion = _expected(root)
    except Exception as error:
        return {
            "schema": VERIFY_SCHEMA,
            "verified": False,
            "checkpoint_count": 0,
            "layer_count": 0,
            "errors": [f"independent reconstruction failed: {error}"],
        }
    try:
        actual = json.loads(
            (
                artifact / "runtime-layer-static-provenance.json"
            ).read_text(encoding="utf-8")
        )
        if actual != expected:
            errors.append(
                "runtime provenance does not match independent reconstruction"
            )
    except Exception as error:
        errors.append(f"payload read failed: {error}")
    try:
        promotion = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )
        if promotion != expected_promotion:
            errors.append("promotion manifest does not match reconstruction")
    except Exception as error:
        errors.append(f"promotion manifest read failed: {error}")
    files = sorted(
        path.relative_to(artifact).as_posix()
        for path in artifact.rglob("*")
        if path.is_file()
    )
    if files != ["manifest.json", "runtime-layer-static-provenance.json"]:
        errors.append(f"unexpected artifact files: {files}")
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "checkpoint_count": len(expected["checkpoints"]),
        "layer_count": len(expected["layers"]),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts/runtime-layer-static-provenance-v1"),
    )
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
