#!/usr/bin/env python3
"""Independently rebuild and verify initializer-resource-pack-v1."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import struct
from typing import Any
import zlib

from PIL import Image


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
INITIALIZER_GBA = 0x08065404
CALLER_SCAN_END = 0x09C000
DIRECT_CALLERS = [
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
]
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
STATE_SIZE = 0x61000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

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

LOADER_ROUTES = {
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
        "destination_formula": "0x05000000 + bg_palette_slot * 32",
        "evidence_type": "static_code",
    },
    "obj_graphics": {
        "wrapper_gba_address": "0x0809C0E8",
        "bios_service": "LZ77UnCompVram",
        "destination_formula": "0x06010000 + obj_tile_slot * 32",
        "destination_slot_global": "0x0201BD5E",
        "evidence_type": "static_code",
    },
    "obj_palette": {
        "helper_gba_address": "0x0808830C",
        "bios_decompress": "LZ77UnCompWram",
        "bios_copy": "CpuSet",
        "scratch_address": "0x02002880",
        "destination_formula": "0x05000200 + obj_palette_slot * 32",
        "destination_slot_global": "0x0201BD60",
        "evidence_type": "static_code",
    },
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _canonical_record_sha(record: dict[str, Any]) -> str:
    data = (
        json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    return _sha(data)


def _ranges(values: list[int]) -> list[list[int]]:
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


def _expand_ranges(ranges: list[list[int]]) -> set[int]:
    return {
        value
        for start, end in ranges
        for value in range(int(start), int(end))
    }


def _decode_bl(address: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    high = first & 0x07FF
    if high & 0x0400:
        high -= 0x0800
    displacement = (high << 12) | ((second & 0x07FF) << 1)
    return (address + 4 + displacement) & 0xFFFFFFFF


def _direct_callers(rom: bytes) -> list[int]:
    result = []
    for offset in range(0, min(CALLER_SCAN_END, len(rom) - 3), 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        address = 0x08000000 + offset
        if _decode_bl(address, first, second) == INITIALIZER_GBA:
            result.append(address)
    return result


def _lz77(rom: bytes, offset: int) -> tuple[bytes, bytes]:
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        raise ValueError(f"invalid LZ77 stream at 0x{offset:06X}")
    declared = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    output = bytearray()
    cursor = offset + 4
    while len(output) < declared:
        if cursor >= len(rom):
            raise ValueError("truncated LZ77 flags")
        flags = rom[cursor]
        cursor += 1
        for bit in range(8):
            if len(output) >= declared:
                break
            if flags & (0x80 >> bit):
                if cursor + 2 > len(rom):
                    raise ValueError("truncated LZ77 reference")
                token = (rom[cursor] << 8) | rom[cursor + 1]
                cursor += 2
                length = (token >> 12) + 3
                distance = (token & 0x0FFF) + 1
                if distance > len(output):
                    raise ValueError("invalid LZ77 distance")
                if len(output) + length > declared:
                    raise ValueError("LZ77 reference exceeds declared size")
                for _ in range(length):
                    output.append(output[-distance])
            else:
                if cursor >= len(rom):
                    raise ValueError("truncated LZ77 literal")
                output.append(rom[cursor])
                cursor += 1
    return rom[offset:cursor], bytes(output)


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
    if not 0x01000000 <= struct.unpack_from("<I", state, 0)[0] <= 0x0100000B:
        raise ValueError(f"{path.name}: unsupported state version")
    return state


def _memory(state: bytes, address: int, size: int) -> bytes:
    for base, length, offset in (
        (0x04000000, 0x400, 0x400),
        (0x05000000, 0x400, 0x800),
        (0x06000000, 0x18000, 0x1000),
    ):
        relative = address - base
        if 0 <= relative and relative + size <= length:
            return state[offset + relative : offset + relative + size]
    raise ValueError(f"unsupported memory range 0x{address:08X}+0x{size:X}")


def _checkpoint(path: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    state = _state(path)
    io = _memory(state, 0x04000000, 0x400)
    pram = _memory(state, 0x05000000, 0x400)
    vram = _memory(state, 0x06000000, 0x18000)
    dispcnt = struct.unpack_from("<H", io, 0)[0]
    backgrounds = []
    for index in range(4):
        control = struct.unpack_from("<H", io, 8 + index * 2)[0]
        char_block = (control >> 2) & 3
        screen_block = (control >> 8) & 31
        size_code = (control >> 14) & 3
        backgrounds.append(
            {
                "index": index,
                "bgcnt": f"0x{control:04X}",
                "char_base_block": char_block,
                "char_base_address": (
                    f"0x{0x06000000 + char_block * 0x4000:08X}"
                ),
                "color_depth_bpp": 8 if control & 0x80 else 4,
                "screen_base_block": screen_block,
                "screen_base_address": (
                    f"0x{0x06000000 + screen_block * 0x800:08X}"
                ),
                "size_code": size_code,
            }
        )
    bg_palette = pram[:0x200]
    bg_vram = vram[:0x10000]
    return (
        {
            "state_id": _sha(io[:0x58] + bg_palette + bg_vram),
            "backgrounds": backgrounds,
            "display_mode": dispcnt & 7,
        },
        {"bg_palette": bg_palette, "bg_vram": bg_vram},
    )


def _map_offset(
    screen_base: int,
    size: int,
    tile_x: int,
    tile_y: int,
) -> int:
    block_x, block_y = tile_x // 32, tile_y // 32
    block = (
        0
        if size == 0
        else block_x
        if size == 1
        else block_y
        if size == 2
        else block_x + block_y * 2
    )
    return (
        screen_base
        + block * 0x800
        + ((tile_y % 32) * 32 + tile_x % 32) * 2
    )


def _group(
    key: tuple[Any, ...],
    positions: list[int],
    char_base: int,
    classification: str,
) -> dict[str, Any]:
    (
        tile_id,
        tile_hash,
        palette_bank,
        flip_h,
        flip_v,
        source_indices,
        alias_kind,
    ) = key
    record: dict[str, Any] = {
        "classification": classification,
        "runtime_tile_id": tile_id,
        "runtime_tile_address": _address(
            0x06000000 + char_base + tile_id * 32
        ),
        "runtime_tile_sha256": tile_hash,
        "runtime_palette_bank": palette_bank,
        "flip_hv": [flip_h, flip_v],
        "cell_count": len(positions),
        "linear_cell_ranges": _ranges(positions),
    }
    if source_indices:
        source_indices = list(source_indices)
        record.update(
            {
                "source_tile_indices": source_indices,
                "source_tile_candidate_count": len(source_indices),
                "source_tile_deltas": [
                    tile_id - source_id for source_id in source_indices
                ],
                "common_delta_match": (
                    tile_id - COMMON_TILE_DELTA in source_indices
                ),
            }
        )
    if alias_kind:
        record["alias_kind"] = alias_kind
        record["unique_source_identity"] = False
    return record


def _runtime_binding(
    root: Path,
    source_graphics: bytes,
    source_palette: bytes,
) -> dict[str, Any]:
    font_path = root / FONT_PROVENANCE
    font_manifest_path = root / FONT_PROVENANCE_MANIFEST
    font = json.loads(font_path.read_text(encoding="utf-8"))
    parent_path = root / PARENT_PROVENANCE
    parent_manifest_path = root / PARENT_PROVENANCE_MANIFEST
    if _sha(parent_path.read_bytes()) != PARENT_PROVENANCE_SHA256:
        raise ValueError("parent provenance payload differs from accepted anchor")
    if (
        _sha(parent_manifest_path.read_bytes())
        != PARENT_PROVENANCE_MANIFEST_SHA256
    ):
        raise ValueError("parent provenance manifest differs from accepted anchor")
    if _sha(font_path.read_bytes()) != FONT_PROVENANCE_SHA256:
        raise ValueError("font provenance payload differs from accepted anchor")
    if (
        _sha(font_manifest_path.read_bytes())
        != FONT_PROVENANCE_MANIFEST_SHA256
    ):
        raise ValueError("font provenance manifest differs from accepted anchor")
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    parent_manifest = json.loads(
        parent_manifest_path.read_text(encoding="utf-8")
    )
    if (
        parent_manifest["files"][PARENT_PROVENANCE.name]
        != _sha(parent_path.read_bytes())
    ):
        raise ValueError("parent provenance payload differs from manifest")
    font_manifest = json.loads(
        font_manifest_path.read_text(encoding="utf-8")
    )
    if (
        font_manifest["files"][FONT_PROVENANCE.name]
        != _sha(font_path.read_bytes())
    ):
        raise ValueError("font provenance payload differs from manifest")
    for label, manifest in (
        ("parent", parent_manifest),
        ("font", font_manifest),
    ):
        if (
            manifest.get("artifact_status") != "accepted"
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
        raise ValueError("runtime parent denominator changed")

    source_tiles: dict[bytes, list[int]] = defaultdict(list)
    for source_id in range(len(source_graphics) // 32):
        source_tiles[
            source_graphics[source_id * 32 : (source_id + 1) * 32]
        ].append(source_id)
    zero = bytes(32)
    common_fill = source_graphics[32:64]
    if source_tiles[zero] != [0] + list(range(34, 64)):
        raise ValueError("zero tile aliases changed")
    if source_tiles[common_fill] != [1, 10]:
        raise ValueError("common-fill aliases changed")
    palette_banks = [
        source_palette[offset : offset + 32]
        for offset in range(0, len(source_palette), 32)
    ]

    layers = []
    cache: dict[str, tuple[dict[str, Any], dict[str, bytes]]] = {}
    exact_hashes, unmatched_hashes = set(), set()
    alias_totals = defaultdict(int)
    for font_layer in font["layers"]:
        parent_key = font_layer["parent_layer_key"]
        parent_layer = parents[parent_key]
        parent_hash = _canonical_record_sha(parent_layer)
        if parent_hash != font_layer["parent_layer_sha256"]:
            raise ValueError(f"{parent_key}: parent hash changed")
        relative = font_layer["checkpoint_paths"][0]
        if relative not in cache:
            cache[relative] = _checkpoint(root / relative)
        checkpoint, domains = cache[relative]
        if checkpoint["state_id"] != font_layer["state_id"]:
            raise ValueError(f"{relative}: state ID changed")
        background = next(
            item
            for item in checkpoint["backgrounds"]
            if item["index"] == font_layer["bg_index"]
        )
        for field in (
            "bgcnt",
            "char_base_address",
            "screen_base_address",
            "color_depth_bpp",
            "size_code",
        ):
            if background[field] != font_layer[field]:
                raise ValueError(f"{relative}: {field} changed")
        width, height = map(int, font_layer["dimensions_tiles"])
        char_base = int(background["char_base_block"]) * 0x4000
        screen_base = int(background["screen_base_block"]) * 0x800
        size_code = int(background["size_code"])
        excluded = set()
        for item in font_layer["exact_nonblank_font_tiles"]:
            excluded.update(_expand_ranges(item["linear_cell_ranges"]))
        excluded.update(
            int(item["linear_cell_index"])
            for item in font_layer["ambiguous_blank_font_cells"]
        )
        exact_groups: dict[tuple[Any, ...], list[int]] = defaultdict(list)
        alias_groups: dict[tuple[Any, ...], list[int]] = defaultdict(list)
        unmatched_groups: dict[tuple[Any, ...], list[int]] = defaultdict(list)
        fixed_count = 0
        for y in range(height):
            for x in range(width):
                linear = y * width + x
                if linear in excluded:
                    continue
                offset = _map_offset(screen_base, size_code, x, y)
                entry = int.from_bytes(
                    domains["bg_vram"][offset : offset + 2], "little"
                )
                tile_id = entry & 0x03FF
                tile = domains["bg_vram"][
                    char_base + tile_id * 32 :
                    char_base + (tile_id + 1) * 32
                ]
                source_indices = tuple(source_tiles.get(tile, ()))
                alias_kind = (
                    "all_zero"
                    if tile == zero
                    else "common_fill"
                    if tile == common_fill
                    else None
                )
                key = (
                    tile_id,
                    _sha(tile),
                    (entry >> 12) & 0xF,
                    bool(entry & 0x0400),
                    bool(entry & 0x0800),
                    source_indices,
                    alias_kind,
                )
                if alias_kind:
                    alias_groups[key].append(linear)
                    alias_totals[alias_kind] += 1
                elif source_indices:
                    exact_groups[key].append(linear)
                    exact_hashes.add(key[1])
                    if tile_id - COMMON_TILE_DELTA in source_indices:
                        fixed_count += 1
                else:
                    unmatched_groups[key].append(linear)
                    unmatched_hashes.add(key[1])
        exact_count = sum(map(len, exact_groups.values()))
        alias_count = sum(map(len, alias_groups.values()))
        unmatched_count = sum(map(len, unmatched_groups.values()))
        palette_bindings = []
        if exact_count:
            for runtime_bank in sorted({key[2] for key in exact_groups}):
                runtime_bytes = domains["bg_palette"][
                    runtime_bank * 32 : (runtime_bank + 1) * 32
                ]
                matches = [
                    source_bank
                    for source_bank, source_bytes in enumerate(palette_banks)
                    if runtime_bytes == source_bytes
                ]
                if matches:
                    palette_bindings.append(
                        {
                            "runtime_palette_bank": runtime_bank,
                            "runtime_palette_sha256": _sha(runtime_bytes),
                            "source_palette_banks": matches,
                            "evidence_type": "checkpoint_bytes",
                        }
                    )
        layers.append(
            {
                "parent_layer_key": parent_key,
                "parent_layer_sha256": parent_hash,
                "parent_classification": "unidentified_runtime_payload",
                "state_id": font_layer["state_id"],
                "checkpoint_paths": font_layer["checkpoint_paths"],
                "checkpoint": Path(relative).name,
                "bg_index": font_layer["bg_index"],
                "bgcnt": font_layer["bgcnt"],
                "char_base_address": font_layer["char_base_address"],
                "screen_base_address": font_layer["screen_base_address"],
                "dimensions_tiles": [width, height],
                "nonfont_cell_count": exact_count + alias_count + unmatched_count,
                "exact_initializer_bg_content_cell_count": exact_count,
                "aliased_initializer_content_cell_count": alias_count,
                "unmatched_nonfont_cell_count": unmatched_count,
                "common_runtime_tile_delta": (
                    COMMON_TILE_DELTA if exact_count else None
                ),
                "fixed_delta_cell_count": fixed_count,
                "all_exact_content_at_common_delta": (
                    bool(exact_count) and fixed_count == exact_count
                ),
                "exact_palette_bindings": palette_bindings,
                "exact_initializer_bg_contents": [
                    _group(
                        key,
                        positions,
                        char_base,
                        "exact_initializer_bg_graphics_content",
                    )
                    for key, positions in sorted(exact_groups.items())
                ],
                "aliased_initializer_contents": [
                    _group(
                        key,
                        positions,
                        char_base,
                        "aliased_initializer_bg_graphics_content",
                    )
                    for key, positions in sorted(alias_groups.items())
                ],
                "unmatched_nonfont_contents": [
                    _group(
                        key,
                        positions,
                        char_base,
                        "unmatched_nonfont_content",
                    )
                    for key, positions in sorted(unmatched_groups.items())
                ],
            }
        )
    layers.sort(key=lambda item: (item["state_id"], item["bg_index"]))
    no_exact = sorted(
        (
            {
                "checkpoint": item["checkpoint"],
                "bg_index": item["bg_index"],
            }
            for item in layers
            if not item["exact_initializer_bg_content_cell_count"]
        ),
        key=lambda item: (item["checkpoint"], item["bg_index"]),
    )
    exact_total = sum(
        item["exact_initializer_bg_content_cell_count"] for item in layers
    )
    fixed_total = sum(item["fixed_delta_cell_count"] for item in layers)
    source_palette_sha = _sha(palette_banks[0])
    return {
        "source": {
            "bg_graphics_sha256": _sha(source_graphics),
            "bg_palette_sha256": _sha(source_palette),
            "parent_layer_provenance": PARENT_PROVENANCE.as_posix(),
            "parent_layer_provenance_sha256": _sha(parent_path.read_bytes()),
            "parent_layer_provenance_manifest": (
                PARENT_PROVENANCE_MANIFEST.as_posix()
            ),
            "parent_layer_provenance_manifest_sha256": _sha(
                parent_manifest_path.read_bytes()
            ),
            "font_tile_provenance": FONT_PROVENANCE.as_posix(),
            "font_tile_provenance_sha256": _sha(font_path.read_bytes()),
            "font_tile_provenance_manifest": (
                FONT_PROVENANCE_MANIFEST.as_posix()
            ),
            "font_tile_provenance_manifest_sha256": _sha(
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
            "nonfont_cell_count": sum(
                item["nonfont_cell_count"] for item in layers
            ),
            "exact_initializer_bg_content_cell_count": exact_total,
            "exact_initializer_bg_content_distinct_hash_count": len(
                exact_hashes
            ),
            "aliased_initializer_content_cell_count": sum(
                item["aliased_initializer_content_cell_count"]
                for item in layers
            ),
            "aliased_zero_cell_count": alias_totals["all_zero"],
            "aliased_common_fill_cell_count": alias_totals["common_fill"],
            "unmatched_nonfont_cell_count": sum(
                item["unmatched_nonfont_cell_count"] for item in layers
            ),
            "unmatched_nonfont_distinct_hash_count": len(unmatched_hashes),
            "layers_with_exact_initializer_bg_content": sum(
                bool(item["exact_initializer_bg_content_cell_count"])
                for item in layers
            ),
            "layers_without_exact_initializer_bg_content_count": len(no_exact),
            "layers_without_exact_initializer_bg_content": no_exact,
            "common_runtime_tile_delta": COMMON_TILE_DELTA,
            "fixed_delta_cell_count": fixed_total,
            "non_fixed_delta_cell_count": exact_total - fixed_total,
            "layers_with_all_exact_content_at_common_delta": sum(
                item["all_exact_content_at_common_delta"] for item in layers
            ),
            "layers_with_exact_bg_palette_bank": sum(
                bool(item["exact_palette_bindings"]) for item in layers
            ),
            "common_palette_binding": {
                "source_palette_bank": 0,
                "runtime_palette_bank": 14,
                "sha256": source_palette_sha,
            },
        },
        "alias_content_groups": [
            {
                "classification": "aliased_initializer_bg_graphics_content",
                "alias_kind": "all_zero",
                "runtime_tile_sha256": _sha(zero),
                "runtime_cell_count": alias_totals["all_zero"],
                "source_tile_indices": source_tiles[zero],
                "source_tile_candidate_count": len(source_tiles[zero]),
                "unique_source_identity": False,
            },
            {
                "classification": "aliased_initializer_bg_graphics_content",
                "alias_kind": "common_fill",
                "runtime_tile_sha256": _sha(common_fill),
                "runtime_cell_count": alias_totals["common_fill"],
                "source_tile_indices": source_tiles[common_fill],
                "source_tile_candidate_count": len(source_tiles[common_fill]),
                "unique_source_identity": False,
            },
        ],
        "layers": layers,
    }


def _bgr555_to_rgb(color: int) -> tuple[int, int, int]:
    channels = [(color >> shift) & 31 for shift in (0, 5, 10)]
    return tuple((value << 3) | (value >> 2) for value in channels)


def _atlas_pixels(graphics: bytes, tiles_per_row: int) -> tuple[bytes, int, int]:
    tile_count = len(graphics) // 32
    rows = (tile_count + tiles_per_row - 1) // tiles_per_row
    width, height = tiles_per_row * 8, rows * 8
    pixels = bytearray(width * height)
    for tile_index in range(tile_count):
        tile_x = (tile_index % tiles_per_row) * 8
        tile_y = (tile_index // tiles_per_row) * 8
        tile = graphics[tile_index * 32 : (tile_index + 1) * 32]
        for y in range(8):
            for x in range(8):
                packed = tile[y * 4 + x // 2]
                pixels[(tile_y + y) * width + tile_x + x] = (
                    packed >> (4 if x & 1 else 0)
                ) & 15
    return bytes(pixels), width, height


def _resources(
    root: Path,
    artifact: Path,
) -> tuple[dict[str, Any], dict[str, bytes], dict[str, str]]:
    rom = (root / ROM_PATH).read_bytes()
    resources: dict[str, Any] = {}
    decoded: dict[str, bytes] = {}
    file_hashes: dict[str, str] = {}
    compressed_by_key = {}
    for key, spec in RESOURCE_SPECS.items():
        compressed, decoded[key] = _lz77(rom, int(spec["offset"]))
        compressed_by_key[key] = compressed
    for key, spec in RESOURCE_SPECS.items():
        compressed = compressed_by_key[key]
        stem = key.replace("_", "-")
        compressed_file, file = f"{stem}.lz77.bin", f"{stem}.bin"
        if (artifact / compressed_file).read_bytes() != compressed:
            raise ValueError(f"{key} compressed file differs from ROM")
        if (artifact / file).read_bytes() != decoded[key]:
            raise ValueError(f"{key} decompressed file differs from ROM")
        file_hashes[compressed_file] = _sha(compressed)
        file_hashes[file] = _sha(decoded[key])
        literal_offset = int(spec["literal_address"]) - 0x08000000
        if int.from_bytes(rom[literal_offset : literal_offset + 4], "little") != (
            0x08000000 + int(spec["offset"])
        ):
            raise ValueError(f"{key} literal pointer changed")
        call_offset = int(spec["load_call"]) - 0x08000000
        first, second = struct.unpack_from("<HH", rom, call_offset)
        if _decode_bl(int(spec["load_call"]), first, second) != int(
            spec["loader_target"]
        ):
            raise ValueError(f"{key} loader call changed")
        record: dict[str, Any] = {
            "gba_pointer": _address(0x08000000 + int(spec["offset"])),
            "file_offset": int(spec["offset"]),
            "literal_gba_address": _address(int(spec["literal_address"])),
            "load_call_gba_address": _address(int(spec["load_call"])),
            "loader_target_gba_address": _address(int(spec["loader_target"])),
            "compressed_file": compressed_file,
            "compressed_size": len(compressed),
            "compressed_sha256": _sha(compressed),
            "file": file,
            "decompressed_size": len(decoded[key]),
            "decompressed_sha256": _sha(decoded[key]),
        }
        if spec["kind"] == "graphics":
            tiles = [
                decoded[key][offset : offset + 32]
                for offset in range(0, len(decoded[key]), 32)
            ]
            atlas_file = f"{stem}-atlas.png"
            pixels, width, height = _atlas_pixels(
                decoded[key], int(spec["tiles_per_row"])
            )
            with Image.open(artifact / atlas_file) as image:
                image.load()
                if image.mode != "P" or image.size != (width, height):
                    raise ValueError(f"{key} atlas geometry changed")
                if image.tobytes() != pixels:
                    raise ValueError(f"{key} atlas pixels differ")
                expected_palette = []
                palette = decoded[str(spec["palette"])]
                for offset in range(0, len(palette), 2):
                    expected_palette.extend(
                        _bgr555_to_rgb(
                            int.from_bytes(palette[offset : offset + 2], "little")
                        )
                    )
                actual_palette = image.getpalette()[: len(expected_palette)]
                if actual_palette != expected_palette:
                    raise ValueError(f"{key} atlas palette differs")
                if "transparency" in image.info:
                    raise ValueError(f"{key} atlas unexpectedly transparent")
            atlas_bytes = (artifact / atlas_file).read_bytes()
            file_hashes[atlas_file] = _sha(atlas_bytes)
            record.update(
                {
                    "bits_per_pixel": 4,
                    "tile_count": len(tiles),
                    "unique_tile_content_count": len(set(tiles)),
                    "atlas_png": atlas_file,
                    "atlas_sha256": _sha(atlas_bytes),
                    "atlas_dimensions": [width, height],
                }
            )
        else:
            record["color_count"] = len(decoded[key]) // 2
        resources[key] = record
    return resources, decoded, file_hashes


def _expected_payload(
    root: Path,
    artifact: Path,
) -> tuple[dict[str, Any], dict[str, str]]:
    rom = (root / ROM_PATH).read_bytes()
    if _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    initializer = rom[INITIALIZER_START:INITIALIZER_END]
    if _sha(initializer) != INITIALIZER_SHA256:
        raise ValueError("initializer code slice changed")
    callers = _direct_callers(rom)
    if callers != DIRECT_CALLERS:
        raise ValueError("initializer caller inventory changed")
    resources, decoded, file_hashes = _resources(root, artifact)
    runtime_binding = _runtime_binding(
        root, decoded["bg_graphics"], decoded["bg_palette"]
    )
    payload = {
        "schema": SCHEMA,
        "implementation": {
            "exporter_sha256": _sha(
                (root / "tools/export_initializer_resource_pack.py").read_bytes()
            ),
            "verifier_sha256": _sha(Path(__file__).read_bytes()),
            "test_sha256": _sha(
                (root / "tests/test_export_initializer_resource_pack.py").read_bytes()
            ),
        },
        "rom": {"file": ROM_PATH.as_posix(), "sha256": ROM_SHA256},
        "initializer": {
            "gba_start": "0x08065404",
            "gba_end_exclusive": "0x08065554",
            "size": len(initializer),
            "sha256": INITIALIZER_SHA256,
            "direct_callers": callers,
            "evidence_type": "static_code",
        },
        "resources": resources,
        "loader_routes": LOADER_ROUTES,
        "runtime_binding": runtime_binding,
        "scope": SCOPE,
    }
    payload_bytes = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    if (artifact / PAYLOAD_NAME).read_bytes() != payload_bytes:
        raise ValueError("payload differs from independent reconstruction")
    file_hashes[PAYLOAD_NAME] = _sha(payload_bytes)
    return payload, file_hashes


def _expected_manifest(
    payload: dict[str, Any],
    file_hashes: dict[str, str],
) -> dict[str, Any]:
    summary = payload["runtime_binding"]["summary"]
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": dict(sorted(file_hashes.items())),
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


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    root, artifact = Path(root).resolve(), Path(artifact_dir).resolve()
    errors: list[str] = []
    resource_count = runtime_layer_count = nonfont_cell_count = 0
    try:
        if Path(artifact_dir).is_symlink():
            raise ValueError("artifact directory must not be a symbolic link")
        if any(path.is_symlink() for path in artifact.rglob("*")):
            raise ValueError("artifact files must not be symbolic links")
        payload, file_hashes = _expected_payload(root, artifact)
        resource_count = len(payload["resources"])
        runtime_layer_count = payload["runtime_binding"]["summary"][
            "parent_layer_count"
        ]
        nonfont_cell_count = payload["runtime_binding"]["summary"][
            "nonfont_cell_count"
        ]
        manifest = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )
        expected_manifest = _expected_manifest(payload, file_hashes)
        if manifest != expected_manifest:
            errors.append("manifest differs from independent reconstruction")
        actual_files = sorted(
            path.relative_to(artifact).as_posix()
            for path in artifact.rglob("*")
            if path.is_file()
        )
        expected_files = sorted(["manifest.json", *file_hashes])
        if actual_files != expected_files:
            errors.append(f"unexpected artifact files: {actual_files}")
    except Exception as error:
        errors.append(str(error))
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "resource_count": resource_count,
        "runtime_layer_count": runtime_layer_count,
        "nonfont_cell_count": nonfont_cell_count,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/initializer-resource-pack-v1"),
    )
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
