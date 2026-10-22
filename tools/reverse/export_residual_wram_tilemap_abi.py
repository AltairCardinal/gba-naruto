#!/usr/bin/env python3
"""Export code-proven WRAM-to-strided-VRAM tilemap ABI records."""

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
SCHEMA = "residual-wram-tilemap-abi-v1"
PAYLOAD_NAME = "residual-wram-tilemap-abi.json"
BUNDLE_NAME = "tilemaps.bin"
ARTIFACT_ID = "residual-wram-tilemap-abi-v1"
QUEUE_CONSUMER = 0x0806365C
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
EXPECTED_FILES = {PAYLOAD_NAME, BUNDLE_NAME, "manifest.json"}
ROUTES = (
    {
        "source_pointer": 0x0834928C,
        "root": 0x0808AEE0,
        "source_load": 0x0808AD30,
        "load_call": 0x0808AD3A,
        "queue_call": 0x0808AD46,
        "route_window": (0x0808AD30, 0x0808AD4A),
        "route_window_sha256": (
            "68c39e771d5f2b706e8889786ae89552"
            "a2d395d75802fb7ca3395300b4661f9a"
        ),
        "vram_destination": 0x0600001E,
        "width": 15,
        "height": 20,
        "wram_buffer": "task_base+0x2C8",
    },
    {
        "source_pointer": 0x083F1C98,
        "root": 0x0808BD38,
        "source_load": 0x0808BBD4,
        "load_call": 0x0808BBD8,
        "queue_call": 0x0808BBEE,
        "route_window": (0x0808BBD4, 0x0808BBF2),
        "route_window_sha256": (
            "82a4cb13a693742e83c7684e1cde8cfe"
            "69ec331bd24a73875eabc0d3d801531e"
        ),
        "vram_destination": 0x0600F810,
        "width": 24,
        "height": 12,
        "wram_buffer": "scene_work_buffer",
    },
    {
        "source_pointer": 0x085B67E0,
        "root": 0x0808BD48,
        "source_load": 0x0808BBF8,
        "load_call": 0x0808BBFC,
        "queue_call": 0x0808BC12,
        "route_window": (0x0808BBF8, 0x0808BC16),
        "route_window_sha256": (
            "5474c996f3d743429ecfa77da743f6d8"
            "4271bfa6d43c9b2c943e404de3ba4ee0"
        ),
        "vram_destination": 0x0600FC4E,
        "width": 23,
        "height": 3,
        "wram_buffer": "scene_work_buffer+0x240",
    },
)
UNRESOLVED = (
    0x083F2108,
    0x084634B8,
    0x0846356C,
    0x084635D8,
)


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


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _slice(rom: bytes, start: int, end: int) -> bytes:
    begin = start - ROM_BASE
    finish = end - ROM_BASE
    if begin < 0 or finish > len(rom) or begin >= finish:
        raise ValueError(f"invalid ROM range {_address(start)}..{_address(end)}")
    return rom[begin:finish]


def _tilemap_metadata(data: bytes, width: int, height: int) -> dict[str, Any]:
    entry_count = width * height
    if len(data) != entry_count * 2:
        raise ValueError("tilemap dimensions do not match decompressed payload")
    entries = struct.unpack(f"<{entry_count}H", data)
    tiles = [entry & 0x03FF for entry in entries]
    return {
        "width_entries": width,
        "height_entries": height,
        "entry_count": entry_count,
        "entry_size": 2,
        "tile_index_range": [min(tiles), max(tiles)],
        "palette_banks": sorted({entry >> 12 for entry in entries}),
        "horizontal_flip_count": sum(bool(entry & 0x0400) for entry in entries),
        "vertical_flip_count": sum(bool(entry & 0x0800) for entry in entries),
    }


def _screenblock(destination: int, width: int, height: int) -> dict[str, int]:
    offset = destination - 0x06000000
    if offset < 0 or offset >= 0x10000 or offset % 2:
        raise ValueError("tilemap destination is not aligned BG VRAM")
    within = offset % 0x800
    row = within // 64
    column = (within % 64) // 2
    if column + width > 32 or row + height > 32:
        raise ValueError("tilemap rectangle crosses a screenblock boundary")
    return {
        "index": offset // 0x800,
        "row": row,
        "column": column,
    }


def _inventory_records(inventory: dict[str, Any]) -> dict[int, dict[str, Any]]:
    records = {}
    for row in inventory.get("new_records", []):
        classification = row.get("classification", {})
        if (
            classification.get("kind") == "visual_metadata"
            and classification.get("destination_domain") == "WRAM_dynamic"
        ):
            records[int(row["gba_address"], 16)] = row
    expected = {route["source_pointer"] for route in ROUTES} | set(UNRESOLVED)
    if set(records) != expected:
        raise ValueError("WRAM visual metadata denominator changed")
    return records


def _build_payload(root: Path) -> tuple[dict[str, Any], bytes]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 changed")
    inventory_bytes = (root / INVENTORY_PATH).read_bytes()
    if _sha256(inventory_bytes) != INVENTORY_SHA256:
        raise ValueError("LZ77 inventory SHA-256 changed")
    inventory = json.loads(inventory_bytes)
    records = _inventory_records(inventory)
    queue_window = _slice(rom, *QUEUE_WINDOW)
    if _sha256(queue_window) != QUEUE_WINDOW_SHA256:
        raise ValueError("strided GPU queue consumer changed")

    bundle = bytearray()
    tilemaps = []
    for route in ROUTES:
        source = route["source_pointer"]
        row = records[source]
        compressed = read_lz77_record(
            rom,
            source - ROM_BASE,
            expected_size=row["decompressed_size"],
        )
        decompressed = lz77_decompress(rom, source - ROM_BASE)
        route_window = _slice(rom, *route["route_window"])
        if (
            _sha256(compressed) != row["compressed_sha256"]
            or _sha256(decompressed) != row["decompressed_sha256"]
            or len(compressed) != row["compressed_size"]
            or len(decompressed) != row["decompressed_size"]
            or row["aligned_pointer_references"] != [_address(route["root"])]
            or row["literal_load_users"] != [_address(route["source_load"])]
            or _sha256(route_window) != route["route_window_sha256"]
        ):
            raise ValueError(f"source contract changed for {_address(source)}")
        metadata = _tilemap_metadata(
            decompressed,
            route["width"],
            route["height"],
        )
        tilemaps.append(
            {
                "source_pointer": _address(source),
                "compressed_size": len(compressed),
                "compressed_sha256": _sha256(compressed),
                "decompressed_size": len(decompressed),
                "decompressed_sha256": _sha256(decompressed),
                "aligned_pointer_roots": [_address(route["root"])],
                "source_load": _address(route["source_load"]),
                "load_call": _address(route["load_call"]),
                "load_route": "LZ77UnCompWram_wrapper",
                "wram_buffer": route["wram_buffer"],
                "queue_call": _address(route["queue_call"]),
                "submit_route": "strided_gpu_copy_queue",
                "queue_consumer": _address(QUEUE_CONSUMER),
                "vram_destination": _address(route["vram_destination"]),
                "screenblock": _screenblock(
                    route["vram_destination"],
                    route["width"],
                    route["height"],
                ),
                "source_row_stride_bytes": route["width"] * 2,
                "destination_row_stride_bytes": 64,
                "bundle_offset": len(bundle),
                "route_code": {
                    "start": _address(route["route_window"][0]),
                    "end_exclusive": _address(route["route_window"][1]),
                    "sha256": route["route_window_sha256"],
                },
                "tilemap": metadata,
            }
        )
        bundle.extend(decompressed)

    payload = {
        "schema": SCHEMA,
        "rom": {
            "path": "rom/base.gba",
            "sha256": ROM_SHA256,
        },
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
            "consumer": _address(QUEUE_CONSUMER),
            "status": 3,
            "destination_row_stride_bytes": 64,
            "code_window": {
                "start": _address(QUEUE_WINDOW[0]),
                "end_exclusive": _address(QUEUE_WINDOW[1]),
                "sha256": QUEUE_WINDOW_SHA256,
            },
        },
        "tilemaps": tilemaps,
        "remaining_unresolved": [_address(value) for value in UNRESOLVED],
        "scope": {
            "all_pointer_reachable_wram_visual_metadata_enumerated": True,
            "direct_local_lz77_to_strided_queue_routes_complete": True,
            "three_tilemap_payload_shapes_and_gpu_destinations_proved": True,
            "remaining_four_wram_payload_abis_complete": False,
            "natural_language_screen_identity_complete": False,
            "runtime_reachability_complete": False,
            "final_screen_pixel_and_timing_equivalence_complete": False,
            "generic_wram_visual_metadata_writeback_complete": False,
        },
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
    files = {
        PAYLOAD_NAME: payload_bytes,
        BUNDLE_NAME: bundle,
    }
    for name, data in files.items():
        (output / name).write_bytes(data)
    implementation = {}
    for relative in IMPLEMENTATION_PATHS:
        data = (root / relative).read_bytes()
        implementation[relative] = _sha256(data)
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_id": ARTIFACT_ID,
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "payload_file": PAYLOAD_NAME,
        "payload_sha256": _sha256(payload_bytes),
        "files": {name: _sha256(data) for name, data in sorted(files.items())},
        "implementation": implementation,
        "summary": payload["summary"],
        "scope": payload["scope"],
        "verifier": {
            "command": [
                "python3",
                "tools/verify_residual_wram_tilemap_abi.py",
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
