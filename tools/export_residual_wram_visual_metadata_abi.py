#!/usr/bin/env python3
"""Export the complete seven-source residual WRAM visual-metadata ABI."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import read_lz77_record


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
ARTIFACT_ID = SCHEMA
PAYLOAD_NAME = "residual-wram-visual-metadata-abi.json"
BUNDLE_NAME = "tilemap-sources.bin"
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
    "tools/export_residual_wram_visual_metadata_abi.py",
    "tools/verify_residual_wram_visual_metadata_abi.py",
)


DIRECT_QUEUE_SPECS = (
    {
        "source": 0x0834928C,
        "root": 0x0808AEE0,
        "source_load": 0x0808AD30,
        "load_call": 0x0808AD3A,
        "queue_call": 0x0808AD46,
        "code_window": (0x0808AD30, 0x0808AD4A),
        "code_hash": (
            "68c39e771d5f2b706e8889786ae89552"
            "a2d395d75802fb7ca3395300b4661f9a"
        ),
        "destination": 0x0600001E,
        "width": 15,
        "height": 20,
        "wram": "task_base+0x2C8",
    },
    {
        "source": 0x083F1C98,
        "root": 0x0808BD38,
        "source_load": 0x0808BBD4,
        "load_call": 0x0808BBD8,
        "queue_call": 0x0808BBEE,
        "code_window": (0x0808BBD4, 0x0808BBF2),
        "code_hash": (
            "82a4cb13a693742e83c7684e1cde8cfe"
            "69ec331bd24a73875eabc0d3d801531e"
        ),
        "destination": 0x0600F810,
        "width": 24,
        "height": 12,
        "wram": "scene_work_buffer",
    },
    {
        "source": 0x085B67E0,
        "root": 0x0808BD48,
        "source_load": 0x0808BBF8,
        "load_call": 0x0808BBFC,
        "queue_call": 0x0808BC12,
        "code_window": (0x0808BBF8, 0x0808BC16),
        "code_hash": (
            "5474c996f3d743429ecfa77da743f6d8"
            "4271bfa6d43c9b2c943e404de3ba4ee0"
        ),
        "destination": 0x0600FC4E,
        "width": 23,
        "height": 3,
        "wram": "scene_work_buffer+0x240",
    },
)

CROP_SPEC = {
    "source": 0x083F2108,
    "root": 0x0808BD60,
    "source_load": 0x0808BC2A,
    "load_call": 0x0808BC2E,
    "submit_call": 0x0808BC36,
    "load_window": (0x0808BC2A, 0x0808BC3A),
    "load_hash": (
        "1a5332253ac2b0ccf8eead861567be8c9b8243109f8375a22007a6e238bf0dad"
    ),
    "consumer": 0x0808B79C,
    "consumer_window": (0x0808B79C, 0x0808B834),
    "consumer_hash": (
        "09f7ab1f2b47b1e2f80d2c4175fb0c7e74afb1817f4a2375488f07a8b60fefab"
    ),
    "destination": 0x06001100,
    "source_width": 40,
    "source_height": 10,
    "submitted_width": 32,
    "submitted_height": 10,
    "wram": "0x02002880",
}

TRANSFORM_SPECS = (
    {
        "source": 0x084634B8,
        "root": 0x08090BDC,
        "source_load": 0x08090B58,
        "load_call": 0x08090B5C,
        "load_window": (0x08090B58, 0x08090B60),
        "load_hash": (
            "e9522d47a95e15ee2674174dd80480b53ef3075dc6c9e56b357d65688f746578"
        ),
        "consumer": 0x08090AEC,
        "consumer_window": (0x08090AEC, 0x08090CC4),
        "consumer_hash": (
            "553ca1f9ea0141844c5134f28749c240bb91e39650ebc607b8f0a7e944954d7d"
        ),
        "source_read": 0x08090C68,
        "output_write": 0x08090C6C,
        "queue_call": 0x08090CB0,
        "phase": "single_phase",
    },
    {
        "source": 0x0846356C,
        "root": 0x08090DDC,
        "source_load": 0x08090D52,
        "load_call": 0x08090D56,
        "load_window": (0x08090D52, 0x08090D62),
        "load_hash": (
            "e656aa94cf38596f0858d4b4a04fcca621f511c88f11561dfcf697de083cb7bc"
        ),
        "consumer": 0x08090CC8,
        "consumer_window": (0x08090CC8, 0x08090F50),
        "consumer_hash": (
            "dc2e4d819841744681ad8cc9ff9cc42e82a80890db666ded41f3fbc17cacb31f"
        ),
        "source_read": 0x08090EF4,
        "output_write": 0x08090EF8,
        "queue_call": 0x08090F3C,
        "phase": "initial_phase",
    },
    {
        "source": 0x084635D8,
        "root": 0x08090DE8,
        "source_load": 0x08090DC0,
        "load_call": 0x08090DC4,
        "load_window": (0x08090DC0, 0x08090DD0),
        "load_hash": (
            "dd0af6d7de652fe55a124371cf91a8cd64eaeec5953734e8feb0cd71d7b1e1fb"
        ),
        "consumer": 0x08090CC8,
        "consumer_window": (0x08090CC8, 0x08090F50),
        "consumer_hash": (
            "dc2e4d819841744681ad8cc9ff9cc42e82a80890db666ded41f3fbc17cacb31f"
        ),
        "source_read": 0x08090EF4,
        "output_write": 0x08090EF8,
        "queue_call": 0x08090F3C,
        "phase": "second_phase",
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
    start, end = bounds
    return rom[start - ROM_BASE : end - ROM_BASE]


def _code_window(
    rom: bytes,
    bounds: tuple[int, int],
    expected_hash: str,
) -> dict[str, str]:
    if _sha256(_slice(rom, bounds)) != expected_hash:
        raise ValueError(
            f"code window {_address(bounds[0])}..{_address(bounds[1])} changed"
        )
    return {
        "start": _address(bounds[0]),
        "end_exclusive": _address(bounds[1]),
        "sha256": expected_hash,
    }


def _tilemap(data: bytes, width: int, height: int) -> dict[str, Any]:
    count = width * height
    if len(data) != count * 2:
        raise ValueError("tilemap dimensions do not match payload")
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
        raise ValueError("invalid BG screenblock rectangle")
    return {"index": offset // 0x800, "row": row, "column": column}


def _inventory_records(inventory: dict[str, Any]) -> dict[int, dict[str, Any]]:
    records = {}
    for row in inventory.get("new_records", []):
        classification = row.get("classification", {})
        if (
            classification.get("kind") == "visual_metadata"
            and classification.get("destination_domain") == "WRAM_dynamic"
        ):
            records[int(row["gba_address"], 16)] = row
    expected = {
        spec["source"]
        for spec in DIRECT_QUEUE_SPECS + TRANSFORM_SPECS
    } | {CROP_SPEC["source"]}
    if set(records) != expected:
        raise ValueError("WRAM visual metadata denominator changed")
    return records


def _source_data(
    rom: bytes,
    inventory_row: dict[str, Any],
    source: int,
    root: int,
    source_load: int,
) -> tuple[bytes, bytes]:
    compressed = read_lz77_record(
        rom,
        source - ROM_BASE,
        expected_size=inventory_row["decompressed_size"],
    )
    decoded = lz77_decompress(rom, source - ROM_BASE)
    if (
        len(compressed) != inventory_row["compressed_size"]
        or len(decoded) != inventory_row["decompressed_size"]
        or _sha256(compressed) != inventory_row["compressed_sha256"]
        or _sha256(decoded) != inventory_row["decompressed_sha256"]
        or inventory_row["aligned_pointer_references"] != [_address(root)]
        or inventory_row["literal_load_users"] != [_address(source_load)]
    ):
        raise ValueError(f"source contract changed for {_address(source)}")
    return compressed, decoded


def _source_base(
    spec: dict[str, Any],
    compressed: bytes,
    decoded: bytes,
    bundle_offset: int,
) -> dict[str, Any]:
    return {
        "source_pointer": _address(spec["source"]),
        "compressed_size": len(compressed),
        "compressed_sha256": _sha256(compressed),
        "decompressed_size": len(decoded),
        "decompressed_sha256": _sha256(decoded),
        "aligned_pointer_roots": [_address(spec["root"])],
        "source_load": _address(spec["source_load"]),
        "load_call": _address(spec["load_call"]),
        "load_route": "LZ77UnCompWram_wrapper",
        "bundle_offset": bundle_offset,
    }


def _build_payload(root: Path) -> tuple[dict[str, Any], bytes]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 changed")
    inventory_bytes = (root / INVENTORY_PATH).read_bytes()
    if _sha256(inventory_bytes) != INVENTORY_SHA256:
        raise ValueError("LZ77 inventory SHA-256 changed")
    records = _inventory_records(json.loads(inventory_bytes))
    queue_code = _code_window(rom, QUEUE_WINDOW, QUEUE_WINDOW_SHA256)

    bundle = bytearray()
    sources: list[dict[str, Any]] = []
    for spec in DIRECT_QUEUE_SPECS:
        compressed, decoded = _source_data(
            rom,
            records[spec["source"]],
            spec["source"],
            spec["root"],
            spec["source_load"],
        )
        record = _source_base(spec, compressed, decoded, len(bundle))
        record.update(
            {
                "classification": "direct_strided_queue_tilemap",
                "wram_buffer": spec["wram"],
                "submit_route": "strided_gpu_copy_queue",
                "submit_call": _address(spec["queue_call"]),
                "submit_consumer": "0x0806365C",
                "vram_destination": _address(spec["destination"]),
                "screenblock": _screenblock(
                    spec["destination"],
                    spec["width"],
                    spec["height"],
                ),
                "transfer_geometry": {
                    "source_width_entries": spec["width"],
                    "source_height_entries": spec["height"],
                    "submitted_width_entries": spec["width"],
                    "submitted_height_entries": spec["height"],
                    "source_row_stride_bytes": spec["width"] * 2,
                    "destination_row_stride_bytes": 64,
                },
                "route_code": _code_window(
                    rom,
                    spec["code_window"],
                    spec["code_hash"],
                ),
                "tilemap": _tilemap(
                    decoded,
                    spec["width"],
                    spec["height"],
                ),
            }
        )
        sources.append(record)
        bundle.extend(decoded)

    spec = CROP_SPEC
    compressed, decoded = _source_data(
        rom,
        records[spec["source"]],
        spec["source"],
        spec["root"],
        spec["source_load"],
    )
    crop = _source_base(spec, compressed, decoded, len(bundle))
    crop.update(
        {
            "classification": "direct_cpu_crop_tilemap",
            "wram_buffer": spec["wram"],
            "submit_route": "direct_cpu_halfword_crop",
            "submit_call": _address(spec["submit_call"]),
            "submit_consumer": _address(spec["consumer"]),
            "vram_destination": _address(spec["destination"]),
            "screenblock": _screenblock(
                spec["destination"],
                spec["submitted_width"],
                spec["submitted_height"],
            ),
            "transfer_geometry": {
                "source_width_entries": spec["source_width"],
                "source_height_entries": spec["source_height"],
                "submitted_width_entries": spec["submitted_width"],
                "submitted_height_entries": spec["submitted_height"],
                "source_row_stride_bytes": spec["source_width"] * 2,
                "destination_row_stride_bytes": spec["submitted_width"] * 2,
                "discarded_right_entries_per_row": (
                    spec["source_width"] - spec["submitted_width"]
                ),
            },
            "load_route_code": _code_window(
                rom,
                spec["load_window"],
                spec["load_hash"],
            ),
            "consumer_code": _code_window(
                rom,
                spec["consumer_window"],
                spec["consumer_hash"],
            ),
            "tilemap": _tilemap(
                decoded,
                spec["source_width"],
                spec["source_height"],
            ),
        }
    )
    sources.append(crop)
    bundle.extend(decoded)

    for spec in TRANSFORM_SPECS:
        compressed, decoded = _source_data(
            rom,
            records[spec["source"]],
            spec["source"],
            spec["root"],
            spec["source_load"],
        )
        record = _source_base(spec, compressed, decoded, len(bundle))
        record.update(
            {
                "classification": "transformed_strided_queue_tilemap",
                "wram_buffer": "0x0200A640",
                "output_buffer": "0x0200A760",
                "submit_route": (
                    "coordinate_clipped_tile_bias_then_strided_queue"
                ),
                "submit_call": _address(spec["queue_call"]),
                "submit_consumer": "0x0806365C",
                "source_read": _address(spec["source_read"]),
                "output_write": _address(spec["output_write"]),
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
                    "coordinate_keyframes_pointer": "0x085A8A7F"
                    if spec["source"] == 0x084634B8
                    else "0x085A8A8F",
                },
                "load_route_code": _code_window(
                    rom,
                    spec["load_window"],
                    spec["load_hash"],
                ),
                "consumer_code": _code_window(
                    rom,
                    spec["consumer_window"],
                    spec["consumer_hash"],
                ),
                "tilemap": _tilemap(decoded, 12, 12),
            }
        )
        if record["tilemap"]["tile_index_range"][1] + 0x02BC > 0x03FF:
            raise ValueError("transformed tile index exceeds BG tile field")
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
        "wram_visual_metadata_denominator": len(sources),
        "tilemap_source_count": len(sources),
        "direct_strided_queue_count": len(DIRECT_QUEUE_SPECS),
        "direct_cpu_crop_count": 1,
        "transformed_strided_queue_count": len(TRANSFORM_SPECS),
        "remaining_unresolved_count": 0,
        "tilemap_entry_count": sum(
            row["tilemap"]["entry_count"] for row in sources
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
            "code_window": queue_code,
        },
        "tilemap_sources": sources,
        "remaining_unresolved": [],
        "scope": scope,
    }
    return payload, bytes(bundle)


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    output = output.resolve()
    if output.exists():
        existing = {
            path.relative_to(output).as_posix()
            for path in output.rglob("*")
            if path.is_file()
        }
        foreign = existing - EXPECTED_FILES
        if foreign:
            raise ValueError(f"output contains foreign files: {sorted(foreign)}")
    output.mkdir(parents=True, exist_ok=True)
    payload, bundle = _build_payload(root)
    payload_bytes = _canonical_json(payload)
    files = {PAYLOAD_NAME: payload_bytes, BUNDLE_NAME: bundle}
    for name, data in files.items():
        (output / name).write_bytes(data)
    implementation = {
        relative: _sha256((root / relative).read_bytes())
        for relative in IMPLEMENTATION_PATHS
    }
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_id": ARTIFACT_ID,
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "payload_file": PAYLOAD_NAME,
        "payload_sha256": _sha256(payload_bytes),
        "files": {
            name: _sha256(data) for name, data in sorted(files.items())
        },
        "implementation": implementation,
        "summary": payload["summary"],
        "scope": payload["scope"],
        "verifier": {
            "command": [
                "python3",
                "tools/verify_residual_wram_visual_metadata_abi.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{ARTIFACT_ID}",
            ],
            "exit_code": 0,
        },
    }
    (output / "manifest.json").write_bytes(_canonical_json(manifest))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts") / ARTIFACT_ID,
    )
    args = parser.parse_args()
    payload = export_artifact(args.root, args.output)
    print(json.dumps(payload["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
