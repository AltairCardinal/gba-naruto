#!/usr/bin/env python3
"""Independently verify the overview BG0 gradient artifact."""

from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
from pathlib import Path
import struct
from typing import Any
import zlib

from PIL import Image


SCHEMA = "overview-gradient-overlay-v1"
VERIFY_SCHEMA = "overview-gradient-overlay-verification-v1"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CHECKPOINT_SHA256 = (
    "209bf3c7321fedc93a6c957fb2c7b46f0d48aa56ea5c4bb3858fce93d0a336f6"
)
PARENT_PAYLOAD_RELATIVE = Path(
    "artifacts/initializer-resource-pack-v1/initializer-resource-pack.json"
)
PARENT_MANIFEST_RELATIVE = Path(
    "artifacts/initializer-resource-pack-v1/manifest.json"
)
PARENT_PAYLOAD_SHA256 = (
    "c096e70c033f804548446272c47d43bfefa72eed173841e152c630c5436efba8"
)
PARENT_MANIFEST_SHA256 = (
    "8fc7c3ea449b480c5065a97e70d0f6c5c0fa30a0dc3f942931f6be86264337a4"
)
EXPECTED_FILES = {
    "generated-palette.bgr555.bin",
    "generated-tilemap-30x20.bin",
    "generated-tiles.4bpp.bin",
    "overview-gradient-overlay.json",
    "overview-gradient-overlay.png",
}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
STATE_SIZE = 0x61000


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
    decompressor = zlib.decompressobj()
    data = decompressor.decompress(payloads[0], STATE_SIZE + 1)
    data += decompressor.flush()
    if (
        not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
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
    raise ValueError(f"memory read outside state: 0x{address:08X}+0x{size:X}")


def _generated() -> tuple[bytes, bytes, bytes]:
    tiles = bytearray(0x160)
    for y in range(80):
        color = y * 15 // 80 + 1
        packed = color | color << 4
        offset = (1 + y // 8) * 32 + (y % 8) * 4
        tiles[offset : offset + 4] = bytes((packed,)) * 4
    palette = bytearray()
    for index in range(16):
        component = 0 if index == 0 else 20 - index
        palette.extend(
            struct.pack("<H", component | component << 5 | component << 10)
        )
    entries = []
    for row in range(20):
        value = 0x0100 if not 4 <= row <= 13 else 0xD101 + row - 4
        entries.extend((value,) * 30)
    return bytes(tiles), bytes(palette), struct.pack("<600H", *entries)


def _parent_resolution(root: Path, tiles: bytes) -> dict[str, Any]:
    payload_path = root / PARENT_PAYLOAD_RELATIVE
    manifest_path = root / PARENT_MANIFEST_RELATIVE
    payload_bytes = payload_path.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    if _sha256(payload_bytes) != PARENT_PAYLOAD_SHA256:
        raise ValueError("initializer parent payload hash mismatch")
    if _sha256(manifest_bytes) != PARENT_MANIFEST_SHA256:
        raise ValueError("initializer parent manifest hash mismatch")
    parent = json.loads(payload_bytes)
    summary = parent["runtime_binding"]["summary"]
    candidates = [
        layer
        for layer in parent["runtime_binding"]["layers"]
        if layer.get("checkpoint") == "alternate-character-overview.ss9"
        and layer.get("bg_index") == 0
    ]
    if len(candidates) != 1:
        raise ValueError("initializer parent overview BG0 identity mismatch")
    layer = candidates[0]
    tile_hashes = {
        0x100 + index: _sha256(tiles[index * 32 : (index + 1) * 32])
        for index in range(1, 11)
    }
    generated_hashes = set(tile_hashes.values())
    resolved = [
        item
        for item in layer["unmatched_nonfont_contents"]
        if item["runtime_tile_sha256"] in generated_hashes
    ]
    resolved_ids = sorted(item["runtime_tile_id"] for item in resolved)
    resolved_hashes = {item["runtime_tile_sha256"] for item in resolved}
    resolved_cells = sum(item["cell_count"] for item in resolved)
    layer_hashes = {
        item["runtime_tile_sha256"]
        for item in layer["unmatched_nonfont_contents"]
    }
    all_unmatched = [
        content
        for parent_layer in parent["runtime_binding"]["layers"]
        for content in parent_layer.get("unmatched_nonfont_contents", [])
    ]
    global_hashes = {item["runtime_tile_sha256"] for item in all_unmatched}
    if (
        summary.get("unmatched_nonfont_cell_count"),
        summary.get("unmatched_nonfont_distinct_hash_count"),
        layer.get("unmatched_nonfont_cell_count"),
        len(layer_hashes),
        resolved_cells,
        len(resolved_hashes),
        resolved_ids,
    ) != (898, 39, 717, 17, 300, 10, list(range(257, 267))):
        raise ValueError("initializer parent denominator mismatch")
    if any(
        tile_hashes[item["runtime_tile_id"]] != item["runtime_tile_sha256"]
        for item in resolved
    ):
        raise ValueError("initializer parent generated hash mismatch")
    return {
        "parent": {
            "artifact": PARENT_PAYLOAD_RELATIVE.as_posix(),
            "artifact_sha256": PARENT_PAYLOAD_SHA256,
            "manifest": PARENT_MANIFEST_RELATIVE.as_posix(),
            "manifest_sha256": PARENT_MANIFEST_SHA256,
        },
        "target_layer": {
            "parent_layer_key": layer["parent_layer_key"],
            "parent_layer_sha256": layer["parent_layer_sha256"],
            "checkpoint": layer["checkpoint"],
            "bg_index": layer["bg_index"],
        },
        "baseline": {
            "global_unmatched_cell_count": 898,
            "global_unmatched_distinct_hash_count": len(global_hashes),
            "target_layer_unmatched_cell_count": 717,
            "target_layer_unmatched_distinct_hash_count": len(layer_hashes),
        },
        "resolved": {
            "classification": "generated_overview_gradient_content",
            "cell_count": resolved_cells,
            "distinct_hash_count": len(resolved_hashes),
            "runtime_tile_ids": resolved_ids,
            "runtime_tile_sha256": [
                tile_hashes[tile_id] for tile_id in resolved_ids
            ],
            "parent_records": resolved,
        },
        "remaining": {
            "global_unmatched_cell_count": 898 - resolved_cells,
            "global_unmatched_distinct_hash_count": len(
                global_hashes - resolved_hashes
            ),
            "target_layer_unmatched_cell_count": 717 - resolved_cells,
            "target_layer_unmatched_distinct_hash_count": len(
                layer_hashes - resolved_hashes
            ),
        },
        "scope": (
            "This subtracts only exact generated tile-content matches from the "
            "hash-bound initializer unknown denominator; it does not reclassify "
            "the remaining target layer or any untracked visual state."
        ),
    }


def _visible_map(state: bytes) -> bytes:
    return b"".join(
        _read_memory(state, 0x06000000 + row * 64, 60) for row in range(20)
    )


def _decode_bl(rom: bytes, address: int) -> int | None:
    offset = address - 0x08000000
    first, second = struct.unpack_from("<HH", rom, offset)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    high = first & 0x07FF
    if high & 0x0400:
        high -= 0x0800
    displacement = (high << 12) | ((second & 0x07FF) << 1)
    return (address + 4 + displacement) & 0xFFFFFFFF


def _preview_semantics(path: Path, tiles: bytes, palette: bytes, tilemap: bytes) -> None:
    entries = struct.unpack("<600H", tilemap)
    expected = bytearray(240 * 160)
    for tile_y in range(20):
        for tile_x in range(30):
            source_tile = (entries[tile_y * 30 + tile_x] & 0x03FF) - 0x0100
            tile = tiles[source_tile * 32 : source_tile * 32 + 32]
            for py in range(8):
                for px in range(8):
                    value = tile[py * 4 + px // 2]
                    expected[(tile_y * 8 + py) * 240 + tile_x * 8 + px] = (
                        value >> (4 * (px & 1))
                    ) & 0x0F
    with Image.open(path) as image:
        image.load()
        if image.mode != "P" or image.size != (240, 160):
            raise ValueError("preview must be indexed 240x160")
        if image.info.get("transparency") != 0:
            raise ValueError("preview transparency index is not zero")
        if image.tobytes() != bytes(expected):
            raise ValueError("preview pixels differ from independent rendering")
        expected_palette = []
        for color in struct.unpack("<16H", palette):
            for shift in (0, 5, 10):
                channel = (color >> shift) & 0x1F
                expected_palette.append((channel << 3) | (channel >> 2))
        if image.getpalette()[:48] != expected_palette:
            raise ValueError("preview palette differs from generated BGR555")


def _verify(root: Path, artifact: Path) -> dict[str, Any]:
    if artifact.is_symlink() or not artifact.is_dir():
        raise ValueError("artifact is not a normal directory")
    paths = [path for path in artifact.rglob("*") if path.is_file() or path.is_symlink()]
    if any(path.is_symlink() for path in paths):
        raise ValueError("artifact contains symbolic links")
    relatives = {path.relative_to(artifact).as_posix() for path in paths}
    if relatives != EXPECTED_FILES | {"manifest.json"}:
        raise ValueError(f"unexpected artifact files: {sorted(relatives)}")

    manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "git-artifact-promotion-v1":
        raise ValueError("promotion schema mismatch")
    if manifest.get("artifact_schema") != SCHEMA:
        raise ValueError("artifact schema mismatch")
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("artifact is not accepted")
    if set(manifest.get("files", {})) != EXPECTED_FILES:
        raise ValueError("promotion file inventory mismatch")
    for relative, expected in manifest["files"].items():
        if _sha256((artifact / relative).read_bytes()) != expected:
            raise ValueError(f"promotion hash mismatch: {relative}")

    payload = json.loads(
        (artifact / "overview-gradient-overlay.json").read_text(encoding="utf-8")
    )
    if payload.get("schema") != SCHEMA:
        raise ValueError("payload schema mismatch")
    expected_implementations = {
        "exporter_sha256": _sha256(
            (root / "tools/export_overview_gradient_overlay.py").read_bytes()
        ),
        "verifier_sha256": _sha256(Path(__file__).read_bytes()),
        "test_sha256": _sha256(
            (root / "tests/test_export_overview_gradient_overlay.py").read_bytes()
        ),
    }
    if payload.get("implementation") != expected_implementations:
        raise ValueError("implementation hashes mismatch")
    producer = manifest.get("producer", {})
    for key, expected in expected_implementations.items():
        if producer.get(key) != expected:
            raise ValueError(f"producer {key} mismatch")

    rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256 or payload.get("rom", {}).get("sha256") != ROM_SHA256:
        raise ValueError("ROM hash mismatch")
    code_specs = (
        ("generator", 0x08D934, 0x08DA80),
        ("caller", 0x08DA90, 0x08DBB0),
        ("controller", 0x08DCE0, 0x08E08E),
    )
    for key, start, end in code_specs:
        expected = payload[key]["code"]
        code = rom[start:end]
        if expected != {
            "gba_start": f"0x{0x08000000 + start:08X}",
            "gba_end_exclusive": f"0x{0x08000000 + end:08X}",
            "size": end - start,
            "sha256": _sha256(code),
        }:
            raise ValueError(f"{key} code binding mismatch")
    if _decode_bl(rom, 0x0808DAB8) != 0x0808D934:
        raise ValueError("generator call target mismatch")
    if _decode_bl(rom, 0x0808DCFC) != 0x0808DA90:
        raise ValueError("controller call target mismatch")

    tiles, palette, tilemap = _generated()
    generator = payload.get("generator", {})
    if generator.get("formulas") != {
        "pixel_index": "floor(y * 15 / 80) + 1",
        "tile_scanline": "pixel_index repeated across all 8 pixels of scanline y",
        "palette_component": "0 if index == 0 else 20 - index",
        "palette_bgr555": "component | component << 5 | component << 10",
    }:
        raise ValueError("generator formulas mismatch")
    if generator.get("destinations") != {
        "work_tiles": "0x02002AB0",
        "work_palette": "0x02002C10",
        "work_tilemap": "0x02002C30",
        "vram_tiles": "0x06002000",
        "pram_palette": "0x050001A0",
        "vram_tilemap": "0x06000000",
    }:
        raise ValueError("generator destinations mismatch")
    if generator.get("copy_routes") != [
        {
            "call": "0x0808D9C6",
            "source": "0x02002AB0",
            "destination": "0x06002000",
            "size": 0x160,
        },
        {
            "call": "0x0808DA0E",
            "source": "0x02002C10",
            "destination": "0x050001A0",
            "size": 0x20,
        },
        {
            "call": "0x0808DA6E",
            "source": "0x02002C30",
            "destination": "0x06000000",
            "dimensions": [30, 20],
            "destination_stride_cells": 32,
        },
    ]:
        raise ValueError("generator copy routes mismatch")
    caller = payload.get("caller", {})
    if {
        key: caller.get(key)
        for key in (
            "gba_address",
            "generator_call",
            "generator_parameters",
            "bg0cnt_write",
            "bg0cnt_value",
        )
    } != {
        "gba_address": "0x0808DA90",
        "generator_call": "0x0808DAB8",
        "generator_parameters": {
            "work_buffer": "0x02002AB0",
            "charblock": 0,
            "tile_base": 0x100,
            "palette_bank": 13,
        },
        "bg0cnt_write": "0x0808DABC",
        "bg0cnt_value": "0x0002",
    }:
        raise ValueError("caller metadata mismatch")
    controller = payload.get("controller", {})
    if {
        key: controller.get(key)
        for key in ("gba_address", "caller_call", "resume_after_yield")
    } != {
        "gba_address": "0x0808DCE0",
        "caller_call": "0x0808DCFC",
        "resume_after_yield": "0x0808DF1A",
    }:
        raise ValueError("controller metadata mismatch")
    if payload.get("parent_unmatched_resolution") != _parent_resolution(root, tiles):
        raise ValueError("parent unmatched-resolution mismatch")
    generated_files = {
        "tiles": ("generated-tiles.4bpp.bin", tiles),
        "palette": ("generated-palette.bgr555.bin", palette),
        "tilemap": ("generated-tilemap-30x20.bin", tilemap),
    }
    for key, (relative, expected) in generated_files.items():
        actual = (artifact / relative).read_bytes()
        if actual != expected:
            raise ValueError(f"{key} differs from independent generation")
        record = payload["generated"][key]
        if (
            record.get("file") != relative
            or record.get("size") != len(expected)
            or record.get("sha256") != _sha256(expected)
        ):
            raise ValueError(f"{key} metadata mismatch")
    _preview_semantics(
        artifact / "overview-gradient-overlay.png", tiles, palette, tilemap
    )
    preview = payload["generated"]["preview"]
    if preview.get("sha256") != _sha256(
        (artifact / "overview-gradient-overlay.png").read_bytes()
    ):
        raise ValueError("preview hash mismatch")

    checkpoint = root / "artifacts/runtime-checkpoints/alternate-character-overview.ss9"
    if _sha256(checkpoint.read_bytes()) != CHECKPOINT_SHA256:
        raise ValueError("checkpoint hash mismatch")
    state = _state(checkpoint)
    domains = {
        "work_tiles": _read_memory(state, 0x02002AB0, 0x160),
        "work_palette": _read_memory(state, 0x02002C10, 0x20),
        "work_tilemap": _read_memory(state, 0x02002C30, 0x4B0),
        "vram_tiles": _read_memory(state, 0x06002000, 0x160),
        "pram_palette": _read_memory(state, 0x050001A0, 0x20),
        "vram_tilemap_visible_30x20": _visible_map(state),
    }
    expected_domains = {
        "work_tiles": tiles,
        "work_palette": palette,
        "work_tilemap": tilemap,
        "vram_tiles": tiles,
        "pram_palette": palette,
        "vram_tilemap_visible_30x20": tilemap,
    }
    if any(domains[key] != expected_domains[key] for key in domains):
        raise ValueError("checkpoint generated domains mismatch")
    runtime = payload["runtime_binding"]
    if struct.unpack("<H", _read_memory(state, 0x04000008, 2))[0] != 2:
        raise ValueError("checkpoint BG0CNT mismatch")
    task = _read_memory(state, 0x03000A88 + 0x4C, 0x4C)
    sp = struct.unpack_from("<I", task, 4)[0]
    lr = struct.unpack_from("<I", task, 8)[0]
    if (task[0], sp, lr) != (2, 0x030011D4, 0x0808DF1B):
        raise ValueError("active overview task mismatch")
    expected_runtime = {
        "checkpoint": (
            "artifacts/runtime-checkpoints/alternate-character-overview.ss9"
        ),
        "checkpoint_sha256": CHECKPOINT_SHA256,
        "active_task": {
            "slot": 2,
            "type": 2,
            "sp": "0x030011D4",
            "lr": "0x0808DF1B",
            "resume_pc": "0x0808DF1A",
            "controller_range": ["0x0808DCE0", "0x0808E08E"],
        },
        "bg0cnt": "0x0002",
        "exact_matches": {key: True for key in domains},
        "runtime_sha256": {
            key: _sha256(value) for key, value in domains.items()
        },
        "tilemap_exact_cell_count": 600,
        "tilemap_cell_count": 600,
        "identity_status": "checkpoint_writer_proven",
        "evidence_contract": (
            "hash-bound generator and caller code, active overview controller "
            "task, and exact generated EWRAM/VRAM/PRAM domains jointly bind "
            "this checkpoint; no claim is made for unobserved callers"
        ),
    }
    if runtime != expected_runtime:
        raise ValueError("runtime binding metadata mismatch")

    expected_scope = {
        "generator_algorithm_code_verified": True,
        "generated_tiles_palette_tilemap_losslessly_exported": True,
        "overview_checkpoint_work_buffers_exact": True,
        "overview_checkpoint_hardware_destinations_exact": True,
        "overview_checkpoint_writer_identity_complete": True,
        "whole_overview_screen_source_identity_complete": False,
        "all_callers_runtime_bound": False,
        "all_game_visual_states_complete": False,
        "generic_image_writeback_complete": False,
    }
    if payload.get("scope") != expected_scope:
        raise ValueError("scope mismatch")
    return {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        "tilemap_exact_cell_count": 600,
        "errors": [],
    }


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    try:
        artifact = Path(artifact_dir)
        if artifact.is_symlink():
            raise ValueError("artifact path is a symbolic link")
        return _verify(Path(root).resolve(), artifact.resolve())
    except Exception as error:  # verifier reports all artifact rejection uniformly
        return {
            "schema": VERIFY_SCHEMA,
            "verified": False,
            "tilemap_exact_cell_count": 0,
            "errors": [str(error)],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/overview-gradient-overlay-v1"),
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
