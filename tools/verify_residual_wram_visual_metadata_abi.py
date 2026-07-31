#!/usr/bin/env python3
"""Independently verify the complete residual WRAM visual-metadata ABI."""

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
SCHEMA = "residual-wram-visual-metadata-abi-v2"
PAYLOAD_NAME = "residual-wram-visual-metadata-abi.json"
BUNDLE_NAME = "tilemap-sources.bin"
EXPECTED_FILES = {PAYLOAD_NAME, BUNDLE_NAME, "manifest.json"}
QUEUE_WINDOW = (0x08063604, 0x080636C0)
QUEUE_HASH = (
    "844be072d9572bd9a657357e745977ed9435c647d0ec0e811f66c953c84a1bd6"
)
IMPLEMENTATION_PATHS = (
    "tools/export_rom_pointer_lz77_inventory.py",
    "tools/verify_rom_pointer_lz77_inventory.py",
    "tools/extract_tileset.py",
    "tools/gba_image_export.py",
    "tools/export_residual_wram_visual_metadata_abi.py",
    "tools/verify_residual_wram_visual_metadata_abi.py",
)
SPECS = (
    {
        "kind": "direct",
        "source": 0x0834928C,
        "root": 0x0808AEE0,
        "load": 0x0808AD30,
        "load_call": 0x0808AD3A,
        "submit": 0x0808AD46,
        "window": (0x0808AD30, 0x0808AD4A),
        "hash": (
            "68c39e771d5f2b706e8889786ae89552"
            "a2d395d75802fb7ca3395300b4661f9a"
        ),
        "destination": 0x0600001E,
        "width": 15,
        "height": 20,
        "wram": "task_base+0x2C8",
    },
    {
        "kind": "direct",
        "source": 0x083F1C98,
        "root": 0x0808BD38,
        "load": 0x0808BBD4,
        "load_call": 0x0808BBD8,
        "submit": 0x0808BBEE,
        "window": (0x0808BBD4, 0x0808BBF2),
        "hash": (
            "82a4cb13a693742e83c7684e1cde8cfe"
            "69ec331bd24a73875eabc0d3d801531e"
        ),
        "destination": 0x0600F810,
        "width": 24,
        "height": 12,
        "wram": "scene_work_buffer",
    },
    {
        "kind": "direct",
        "source": 0x085B67E0,
        "root": 0x0808BD48,
        "load": 0x0808BBF8,
        "load_call": 0x0808BBFC,
        "submit": 0x0808BC12,
        "window": (0x0808BBF8, 0x0808BC16),
        "hash": (
            "5474c996f3d743429ecfa77da743f6d8"
            "4271bfa6d43c9b2c943e404de3ba4ee0"
        ),
        "destination": 0x0600FC4E,
        "width": 23,
        "height": 3,
        "wram": "scene_work_buffer+0x240",
    },
    {
        "kind": "crop",
        "source": 0x083F2108,
        "root": 0x0808BD60,
        "load": 0x0808BC2A,
        "load_call": 0x0808BC2E,
        "submit": 0x0808BC36,
        "load_window": (0x0808BC2A, 0x0808BC3A),
        "load_hash": (
            "1a5332253ac2b0ccf8eead861567be8c9b8243109f8375a22007a6e238bf0dad"
        ),
        "consumer": 0x0808B79C,
        "consumer_window": (0x0808B79C, 0x0808B834),
        "consumer_hash": (
            "09f7ab1f2b47b1e2f80d2c4175fb0c"
            "7e74afb1817f4a2375488f07a8b60fefab"
        ),
        "destination": 0x06001100,
        "width": 40,
        "height": 10,
        "submitted_width": 32,
        "wram": "0x02002880",
    },
    {
        "kind": "transform",
        "source": 0x084634B8,
        "root": 0x08090BDC,
        "load": 0x08090B58,
        "load_call": 0x08090B5C,
        "submit": 0x08090CB0,
        "load_window": (0x08090B58, 0x08090B60),
        "load_hash": (
            "e9522d47a95e15ee2674174dd80480b53ef3075dc6c9e56b357d65688f746578"
        ),
        "consumer": 0x08090AEC,
        "consumer_window": (0x08090AEC, 0x08090CC4),
        "consumer_hash": (
            "553ca1f9ea0141844c5134f28749c240bb91e39650ebc607b8f0a7e944954d7d"
        ),
        "read": 0x08090C68,
        "write": 0x08090C6C,
        "phase": "single_phase",
        "keyframes": "0x085A8A7F",
    },
    {
        "kind": "transform",
        "source": 0x0846356C,
        "root": 0x08090DDC,
        "load": 0x08090D52,
        "load_call": 0x08090D56,
        "submit": 0x08090F3C,
        "load_window": (0x08090D52, 0x08090D62),
        "load_hash": (
            "e656aa94cf38596f0858d4b4a04fcca621f511c88f11561dfcf697de083cb7bc"
        ),
        "consumer": 0x08090CC8,
        "consumer_window": (0x08090CC8, 0x08090F50),
        "consumer_hash": (
            "dc2e4d819841744681ad8cc9ff9cc42e82a80890db666ded41f3fbc17cacb31f"
        ),
        "read": 0x08090EF4,
        "write": 0x08090EF8,
        "phase": "initial_phase",
        "keyframes": "0x085A8A8F",
    },
    {
        "kind": "transform",
        "source": 0x084635D8,
        "root": 0x08090DE8,
        "load": 0x08090DC0,
        "load_call": 0x08090DC4,
        "submit": 0x08090F3C,
        "load_window": (0x08090DC0, 0x08090DD0),
        "load_hash": (
            "dd0af6d7de652fe55a124371cf91a8cd64eaeec5953734e8feb0cd71d7b1e1fb"
        ),
        "consumer": 0x08090CC8,
        "consumer_window": (0x08090CC8, 0x08090F50),
        "consumer_hash": (
            "dc2e4d819841744681ad8cc9ff9cc42e82a80890db666ded41f3fbc17cacb31f"
        ),
        "read": 0x08090EF4,
        "write": 0x08090EF8,
        "phase": "second_phase",
        "keyframes": "0x085A8A8F",
    },
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def _slice(rom: bytes, bounds: tuple[int, int]) -> bytes:
    return rom[bounds[0] - ROM_BASE : bounds[1] - ROM_BASE]


def _window(
    rom: bytes,
    bounds: tuple[int, int],
    digest: str,
) -> dict[str, str]:
    if _sha256(_slice(rom, bounds)) != digest:
        raise ValueError(f"code window changed at {_address(bounds[0])}")
    return {
        "start": _address(bounds[0]),
        "end_exclusive": _address(bounds[1]),
        "sha256": digest,
    }


def _decode_lz77(rom: bytes, offset: int) -> tuple[bytes, int]:
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        raise ValueError("invalid LZ77 header")
    size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
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


def _screenblock(
    destination: int,
    width: int,
    height: int,
) -> dict[str, int]:
    offset = destination - 0x06000000
    within = offset % 0x800
    row = within // 64
    column = (within % 64) // 2
    if (
        offset < 0
        or offset >= 0x10000
        or offset % 2
        or column + width > 32
        or row + height > 32
    ):
        raise ValueError("invalid screenblock rectangle")
    return {"index": offset // 0x800, "row": row, "column": column}


def _records(inventory: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = {}
    for row in inventory.get("new_records", []):
        classification = row.get("classification", {})
        if (
            classification.get("kind") == "visual_metadata"
            and classification.get("destination_domain") == "WRAM_dynamic"
        ):
            rows[int(row["gba_address"], 16)] = row
    if set(rows) != {spec["source"] for spec in SPECS}:
        raise ValueError("WRAM visual metadata denominator changed")
    return rows


def _expected(root: Path) -> tuple[dict[str, Any], bytes]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 changed")
    inventory_bytes = (root / INVENTORY_PATH).read_bytes()
    if _sha256(inventory_bytes) != INVENTORY_SHA256:
        raise ValueError("inventory SHA-256 changed")
    inventory = _records(json.loads(inventory_bytes))

    sources = []
    bundle = bytearray()
    for spec in SPECS:
        source = spec["source"]
        row = inventory[source]
        decoded, consumed = _decode_lz77(rom, source - ROM_BASE)
        compressed = rom[source - ROM_BASE : source - ROM_BASE + consumed]
        if (
            consumed != row["compressed_size"]
            or len(decoded) != row["decompressed_size"]
            or _sha256(compressed) != row["compressed_sha256"]
            or _sha256(decoded) != row["decompressed_sha256"]
            or row["aligned_pointer_references"]
            != [_address(spec["root"])]
            or row["literal_load_users"] != [_address(spec["load"])]
        ):
            raise ValueError(f"source contract changed at {_address(source)}")
        record = {
            "source_pointer": _address(source),
            "compressed_size": consumed,
            "compressed_sha256": _sha256(compressed),
            "decompressed_size": len(decoded),
            "decompressed_sha256": _sha256(decoded),
            "aligned_pointer_roots": [_address(spec["root"])],
            "source_load": _address(spec["load"]),
            "load_call": _address(spec["load_call"]),
            "load_route": "LZ77UnCompWram_wrapper",
            "bundle_offset": len(bundle),
        }
        if spec["kind"] == "direct":
            width = spec["width"]
            height = spec["height"]
            record.update(
                {
                    "classification": "direct_strided_queue_tilemap",
                    "wram_buffer": spec["wram"],
                    "submit_route": "strided_gpu_copy_queue",
                    "submit_call": _address(spec["submit"]),
                    "submit_consumer": "0x0806365C",
                    "vram_destination": _address(spec["destination"]),
                    "screenblock": _screenblock(
                        spec["destination"], width, height
                    ),
                    "transfer_geometry": {
                        "source_width_entries": width,
                        "source_height_entries": height,
                        "submitted_width_entries": width,
                        "submitted_height_entries": height,
                        "source_row_stride_bytes": width * 2,
                        "destination_row_stride_bytes": 64,
                    },
                    "route_code": _window(
                        rom, spec["window"], spec["hash"]
                    ),
                    "tilemap": _tilemap(decoded, width, height),
                }
            )
        elif spec["kind"] == "crop":
            record.update(
                {
                    "classification": "direct_cpu_crop_tilemap",
                    "wram_buffer": spec["wram"],
                    "submit_route": "direct_cpu_halfword_crop",
                    "submit_call": _address(spec["submit"]),
                    "submit_consumer": _address(spec["consumer"]),
                    "vram_destination": _address(spec["destination"]),
                    "screenblock": _screenblock(
                        spec["destination"], spec["submitted_width"], 10
                    ),
                    "transfer_geometry": {
                        "source_width_entries": spec["width"],
                        "source_height_entries": spec["height"],
                        "submitted_width_entries": spec["submitted_width"],
                        "submitted_height_entries": spec["height"],
                        "source_row_stride_bytes": spec["width"] * 2,
                        "destination_row_stride_bytes": (
                            spec["submitted_width"] * 2
                        ),
                        "discarded_right_entries_per_row": (
                            spec["width"] - spec["submitted_width"]
                        ),
                    },
                    "load_route_code": _window(
                        rom, spec["load_window"], spec["load_hash"]
                    ),
                    "consumer_code": _window(
                        rom,
                        spec["consumer_window"],
                        spec["consumer_hash"],
                    ),
                    "tilemap": _tilemap(
                        decoded, spec["width"], spec["height"]
                    ),
                }
            )
        else:
            tilemap = _tilemap(decoded, 12, 12)
            if tilemap["tile_index_range"][1] + 0x02BC > 0x03FF:
                raise ValueError("transformed tile index overflow")
            record.update(
                {
                    "classification": "transformed_strided_queue_tilemap",
                    "wram_buffer": "0x0200A640",
                    "output_buffer": "0x0200A760",
                    "submit_route": (
                        "coordinate_clipped_tile_bias_then_strided_queue"
                    ),
                    "submit_call": _address(spec["submit"]),
                    "submit_consumer": "0x0806365C",
                    "source_read": _address(spec["read"]),
                    "output_write": _address(spec["write"]),
                    "phase": spec["phase"],
                    "vram_destination": "0x06000806",
                    "screenblock": _screenblock(0x06000806, 12, 12),
                    "transfer_geometry": {
                        "source_width_entries": 12,
                        "source_height_entries": 12,
                        "submitted_width_entries": 12,
                        "submitted_height_entries": 12,
                        "source_row_stride_bytes": 24,
                        "destination_row_stride_bytes": 64,
                    },
                    "transform": {
                        "coordinate_bounds": [12, 12],
                        "tile_index_add": 0x02BC,
                        "default_entry": "0x02BC",
                        "out_of_bounds_behavior": "retain_default_entry",
                        "coordinate_keyframes_pointer": spec["keyframes"],
                    },
                    "load_route_code": _window(
                        rom, spec["load_window"], spec["load_hash"]
                    ),
                    "consumer_code": _window(
                        rom,
                        spec["consumer_window"],
                        spec["consumer_hash"],
                    ),
                    "tilemap": tilemap,
                }
            )
        sources.append(record)
        bundle.extend(decoded)

    scope = {
        "all_pointer_reachable_wram_visual_metadata_enumerated": True,
        "all_seven_source_abis_complete": True,
        "remaining_unresolved_source_abis": False,
        "natural_language_screen_identity_complete": False,
        "runtime_reachability_complete": False,
        "queue_slot_and_natural_flush_complete": False,
        "graphics_and_palette_ownership_complete": False,
        "final_screen_pixel_and_timing_equivalence_complete": False,
        "generic_wram_visual_metadata_writeback_complete": False,
    }
    summary = {
        "wram_visual_metadata_denominator": 7,
        "tilemap_source_count": 7,
        "direct_strided_queue_count": 3,
        "direct_cpu_crop_count": 1,
        "transformed_strided_queue_count": 3,
        "remaining_unresolved_count": 0,
        "tilemap_entry_count": sum(
            record["tilemap"]["entry_count"] for record in sources
        ),
        "tilemap_payload_bytes": len(bundle),
    }
    payload = {
        "schema": SCHEMA,
        "supersedes": "residual-wram-tilemap-abi-v1",
        "rom": {"path": "rom/base.gba", "sha256": ROM_SHA256},
        "source_inventory": {
            "path": INVENTORY_PATH.as_posix(),
            "sha256": INVENTORY_SHA256,
        },
        "summary": summary,
        "queue_contract": {
            "enqueue": "0x08063604",
            "consumer": "0x0806365C",
            "status": 3,
            "destination_row_stride_bytes": 64,
            "code_window": _window(rom, QUEUE_WINDOW, QUEUE_HASH),
        },
        "tilemap_sources": sources,
        "remaining_unresolved": [],
        "scope": scope,
    }
    return payload, bytes(bundle)


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    errors = []
    try:
        root = root.resolve()
        artifact = artifact.resolve()
        actual_files = {
            path.relative_to(artifact).as_posix()
            for path in artifact.rglob("*")
            if path.is_file()
        }
        if actual_files != EXPECTED_FILES:
            raise ValueError("artifact file inventory mismatch")
        if any(path.is_symlink() for path in artifact.rglob("*")):
            raise ValueError("artifact contains symbolic links")

        payload_bytes = (artifact / PAYLOAD_NAME).read_bytes()
        bundle = (artifact / BUNDLE_NAME).read_bytes()
        manifest = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )
        payload = json.loads(payload_bytes)
        expected_payload, expected_bundle = _expected(root)
        if payload != expected_payload:
            raise ValueError("payload semantic reconstruction mismatch")
        if payload_bytes != _canonical_json(expected_payload):
            raise ValueError("payload canonical serialization mismatch")
        if bundle != expected_bundle:
            raise ValueError("tilemap source bundle mismatch")
        expected_hashes = {
            PAYLOAD_NAME: _sha256(payload_bytes),
            BUNDLE_NAME: _sha256(bundle),
        }
        if manifest.get("files") != expected_hashes:
            raise ValueError("manifest file hashes mismatch")
        expected_verifier = {
            "command": [
                "python3",
                "tools/verify_residual_wram_visual_metadata_abi.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/residual-wram-visual-metadata-abi-v2",
            ],
            "exit_code": 0,
        }
        if (
            manifest.get("schema") != "git-artifact-promotion-v1"
            or manifest.get("artifact_id") != SCHEMA
            or manifest.get("artifact_schema") != SCHEMA
            or manifest.get("artifact_status") != "accepted"
            or manifest.get("payload_file") != PAYLOAD_NAME
            or manifest.get("payload_sha256") != _sha256(payload_bytes)
            or manifest.get("summary") != expected_payload["summary"]
            or manifest.get("scope") != expected_payload["scope"]
            or manifest.get("verifier") != expected_verifier
        ):
            raise ValueError("manifest contract mismatch")
        implementation = {
            relative: _sha256((root / relative).read_bytes())
            for relative in IMPLEMENTATION_PATHS
        }
        if manifest.get("implementation") != implementation:
            raise ValueError("implementation hashes mismatch")
    except Exception as error:
        errors.append(str(error))
    return {
        "schema": "residual-wram-visual-metadata-abi-verification-v2",
        "verified": not errors,
        "verified_tilemap_sources": 0 if errors else 7,
        "remaining_unresolved": 7 if errors else 0,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts/residual-wram-visual-metadata-abi-v2"),
    )
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
