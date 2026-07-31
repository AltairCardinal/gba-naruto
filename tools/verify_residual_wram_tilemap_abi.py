#!/usr/bin/env python3
"""Independently verify the residual WRAM tilemap ABI artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
INVENTORY_PATH = Path(
    "artifacts/rom-pointer-lz77-inventory-v1/"
    "rom-pointer-lz77-inventory.json"
)
INVENTORY_SHA256 = (
    "0c4aed52328b0506e8e41afebe5e5c0ef3dccb830cf8af6c092eb1d0566581c5"
)
PAYLOAD_NAME = "residual-wram-tilemap-abi.json"
BUNDLE_NAME = "tilemaps.bin"
EXPECTED_FILES = {PAYLOAD_NAME, BUNDLE_NAME, "manifest.json"}
QUEUE_WINDOW = (0x08063604, 0x080636C0)
QUEUE_WINDOW_SHA256 = (
    "844be072d9572bd9a657357e745977ed9435c647d0ec0e811f66c953c84a1bd6"
)
IMPLEMENTATION_PATHS = (
    "tools/export_rom_pointer_lz77_inventory.py",
    "tools/verify_rom_pointer_lz77_inventory.py",
    "tools/extract_tileset.py",
    "tools/gba_image_export.py",
    "tools/export_residual_wram_tilemap_abi.py",
    "tools/verify_residual_wram_tilemap_abi.py",
)
ROUTES = (
    (
        0x0834928C,
        0x0808AEE0,
        0x0808AD30,
        0x0808AD3A,
        0x0808AD46,
        0x0808AD30,
        0x0808AD4A,
        "68c39e771d5f2b706e8889786ae89552a2d395d75802fb7ca3395300b4661f9a",
        0x0600001E,
        15,
        20,
        "task_base+0x2C8",
    ),
    (
        0x083F1C98,
        0x0808BD38,
        0x0808BBD4,
        0x0808BBD8,
        0x0808BBEE,
        0x0808BBD4,
        0x0808BBF2,
        "82a4cb13a693742e83c7684e1cde8cfe69ec331bd24a73875eabc0d3d801531e",
        0x0600F810,
        24,
        12,
        "scene_work_buffer",
    ),
    (
        0x085B67E0,
        0x0808BD48,
        0x0808BBF8,
        0x0808BBFC,
        0x0808BC12,
        0x0808BBF8,
        0x0808BC16,
        "5474c996f3d743429ecfa77da743f6d84271bfa6d43c9b2c943e404de3ba4ee0",
        0x0600FC4E,
        23,
        3,
        "scene_work_buffer+0x240",
    ),
)
UNRESOLVED = (0x083F2108, 0x084634B8, 0x0846356C, 0x084635D8)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _decode_lz77(rom: bytes, offset: int) -> tuple[bytes, int]:
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        raise ValueError("invalid LZ77 header")
    size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    if size <= 0:
        raise ValueError("invalid LZ77 size")
    cursor = offset + 4
    output = bytearray()
    while len(output) < size:
        if cursor >= len(rom):
            raise ValueError("truncated LZ77 flags")
        flags = rom[cursor]
        cursor += 1
        for bit in range(8):
            if len(output) >= size:
                break
            if flags & (0x80 >> bit):
                if cursor + 2 > len(rom):
                    raise ValueError("truncated LZ77 token")
                token = (rom[cursor] << 8) | rom[cursor + 1]
                cursor += 2
                length = (token >> 12) + 3
                distance = (token & 0x0FFF) + 1
                if distance > len(output):
                    raise ValueError("invalid LZ77 distance")
                for _ in range(length):
                    if len(output) >= size:
                        break
                    output.append(output[-distance])
            else:
                if cursor >= len(rom):
                    raise ValueError("truncated LZ77 literal")
                output.append(rom[cursor])
                cursor += 1
    return bytes(output), cursor - offset


def _tilemap(data: bytes, width: int, height: int) -> dict[str, Any]:
    count = width * height
    if len(data) != count * 2:
        raise ValueError("tilemap size mismatch")
    entries = struct.unpack(f"<{count}H", data)
    tiles = [entry & 0x03FF for entry in entries]
    return {
        "width_entries": width,
        "height_entries": height,
        "entry_count": count,
        "entry_size": 2,
        "tile_index_range": [min(tiles), max(tiles)],
        "palette_banks": sorted({entry >> 12 for entry in entries}),
        "horizontal_flip_count": sum(bool(entry & 0x0400) for entry in entries),
        "vertical_flip_count": sum(bool(entry & 0x0800) for entry in entries),
    }


def _screenblock(destination: int, width: int, height: int) -> dict[str, int]:
    offset = destination - 0x06000000
    if offset < 0 or offset >= 0x10000 or offset % 2:
        raise ValueError("invalid BG VRAM destination")
    within = offset % 0x800
    row = within // 64
    column = (within % 64) // 2
    if column + width > 32 or row + height > 32:
        raise ValueError("tilemap crosses a screenblock boundary")
    return {
        "index": offset // 0x800,
        "row": row,
        "column": column,
    }


def _slice(rom: bytes, start: int, end: int) -> bytes:
    return rom[start - ROM_BASE : end - ROM_BASE]


def _expected(root: Path) -> tuple[dict[str, Any], bytes]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 changed")
    inventory_bytes = (root / INVENTORY_PATH).read_bytes()
    if _sha256(inventory_bytes) != INVENTORY_SHA256:
        raise ValueError("inventory SHA-256 changed")
    inventory = json.loads(inventory_bytes)
    records = {}
    for row in inventory.get("new_records", []):
        classification = row.get("classification", {})
        if (
            classification.get("kind") == "visual_metadata"
            and classification.get("destination_domain") == "WRAM_dynamic"
        ):
            records[int(row["gba_address"], 16)] = row
    if set(records) != {route[0] for route in ROUTES} | set(UNRESOLVED):
        raise ValueError("WRAM visual metadata denominator changed")
    if _sha256(_slice(rom, *QUEUE_WINDOW)) != QUEUE_WINDOW_SHA256:
        raise ValueError("queue consumer changed")

    bundle = bytearray()
    tilemaps = []
    for (
        source,
        root_pointer,
        source_load,
        load_call,
        queue_call,
        code_start,
        code_end,
        code_hash,
        destination,
        width,
        height,
        wram_buffer,
    ) in ROUTES:
        row = records[source]
        decoded, consumed = _decode_lz77(rom, source - ROM_BASE)
        compressed = rom[source - ROM_BASE : source - ROM_BASE + consumed]
        if (
            consumed != row.get("compressed_size")
            or len(decoded) != row.get("decompressed_size")
            or _sha256(compressed) != row.get("compressed_sha256")
            or _sha256(decoded) != row.get("decompressed_sha256")
            or row.get("aligned_pointer_references") != [_address(root_pointer)]
            or row.get("literal_load_users") != [_address(source_load)]
            or _sha256(_slice(rom, code_start, code_end)) != code_hash
        ):
            raise ValueError(f"source contract changed at {_address(source)}")
        tilemaps.append(
            {
                "source_pointer": _address(source),
                "compressed_size": consumed,
                "compressed_sha256": _sha256(compressed),
                "decompressed_size": len(decoded),
                "decompressed_sha256": _sha256(decoded),
                "aligned_pointer_roots": [_address(root_pointer)],
                "source_load": _address(source_load),
                "load_call": _address(load_call),
                "load_route": "LZ77UnCompWram_wrapper",
                "wram_buffer": wram_buffer,
                "queue_call": _address(queue_call),
                "submit_route": "strided_gpu_copy_queue",
                "queue_consumer": "0x0806365C",
                "vram_destination": _address(destination),
                "screenblock": _screenblock(
                    destination,
                    width,
                    height,
                ),
                "source_row_stride_bytes": width * 2,
                "destination_row_stride_bytes": 64,
                "bundle_offset": len(bundle),
                "route_code": {
                    "start": _address(code_start),
                    "end_exclusive": _address(code_end),
                    "sha256": code_hash,
                },
                "tilemap": _tilemap(decoded, width, height),
            }
        )
        bundle.extend(decoded)
    scope = {
        "all_pointer_reachable_wram_visual_metadata_enumerated": True,
        "direct_local_lz77_to_strided_queue_routes_complete": True,
        "three_tilemap_payload_shapes_and_gpu_destinations_proved": True,
        "remaining_four_wram_payload_abis_complete": False,
        "natural_language_screen_identity_complete": False,
        "runtime_reachability_complete": False,
        "final_screen_pixel_and_timing_equivalence_complete": False,
        "generic_wram_visual_metadata_writeback_complete": False,
    }
    payload = {
        "schema": "residual-wram-tilemap-abi-v1",
        "rom": {"path": "rom/base.gba", "sha256": ROM_SHA256},
        "source_inventory": {
            "path": INVENTORY_PATH.as_posix(),
            "sha256": INVENTORY_SHA256,
        },
        "summary": {
            "wram_visual_metadata_denominator": len(records),
            "direct_tilemap_queue_abi_count": len(tilemaps),
            "remaining_unresolved_count": len(UNRESOLVED),
            "tilemap_entry_count": sum(
                record["tilemap"]["entry_count"] for record in tilemaps
            ),
            "tilemap_payload_bytes": len(bundle),
        },
        "queue_contract": {
            "enqueue": "0x08063604",
            "consumer": "0x0806365C",
            "status": 3,
            "destination_row_stride_bytes": 64,
            "code_window": {
                "start": "0x08063604",
                "end_exclusive": "0x080636C0",
                "sha256": QUEUE_WINDOW_SHA256,
            },
        },
        "tilemaps": tilemaps,
        "remaining_unresolved": [_address(value) for value in UNRESOLVED],
        "scope": scope,
    }
    return payload, bytes(bundle)


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    errors = []
    root = root.resolve()
    artifact = artifact.resolve()
    try:
        actual_files = {
            path.relative_to(artifact).as_posix()
            for path in artifact.rglob("*")
            if path.is_file()
        }
        if actual_files != EXPECTED_FILES:
            raise ValueError("artifact file inventory mismatch")
        if any(path.is_symlink() for path in artifact.rglob("*")):
            raise ValueError("artifact contains symbolic links")
        manifest_bytes = (artifact / "manifest.json").read_bytes()
        payload_bytes = (artifact / PAYLOAD_NAME).read_bytes()
        bundle = (artifact / BUNDLE_NAME).read_bytes()
        manifest = json.loads(manifest_bytes)
        payload = json.loads(payload_bytes)
        expected_payload, expected_bundle = _expected(root)
        if payload != expected_payload:
            raise ValueError("payload semantic reconstruction mismatch")
        if payload_bytes != _canonical_json(expected_payload):
            raise ValueError("payload canonical serialization mismatch")
        if bundle != expected_bundle:
            raise ValueError("tilemap bundle mismatch")
        expected_hashes = {
            PAYLOAD_NAME: _sha256(payload_bytes),
            BUNDLE_NAME: _sha256(bundle),
        }
        if manifest.get("files") != expected_hashes:
            raise ValueError("manifest file hashes mismatch")
        if (
            manifest.get("schema") != "git-artifact-promotion-v1"
            or manifest.get("artifact_id") != "residual-wram-tilemap-abi-v1"
            or manifest.get("artifact_schema")
            != "residual-wram-tilemap-abi-v1"
            or manifest.get("artifact_status") != "accepted"
            or manifest.get("payload_file") != PAYLOAD_NAME
            or manifest.get("payload_sha256") != _sha256(payload_bytes)
            or manifest.get("summary") != expected_payload["summary"]
            or manifest.get("scope") != expected_payload["scope"]
            or manifest.get("verifier")
            != {
                "command": [
                    "python3",
                    "tools/verify_residual_wram_tilemap_abi.py",
                    "--root",
                    ".",
                    "--artifact",
                    "artifacts/residual-wram-tilemap-abi-v1",
                ],
                "exit_code": 0,
            }
        ):
            raise ValueError("manifest contract mismatch")
        implementation = {
            relative: _sha256((root / relative).read_bytes())
            for relative in IMPLEMENTATION_PATHS
        }
        if manifest.get("implementation") != implementation:
            raise ValueError("implementation hashes mismatch")
    except Exception as error:  # verifier must return structured rejection
        errors.append(str(error))
    return {
        "schema": "residual-wram-tilemap-abi-verification-v1",
        "verified": not errors,
        "verified_tilemaps": 0 if errors else 3,
        "remaining_unresolved": 7 if errors else 4,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts/residual-wram-tilemap-abi-v1"),
    )
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
