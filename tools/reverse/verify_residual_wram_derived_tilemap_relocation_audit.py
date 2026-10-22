#!/usr/bin/env python3
"""Independently rebuild the residual WRAM derived-tilemap relocation."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import deque
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ABI_PATH = Path(
    "artifacts/residual-wram-visual-metadata-abi-v2/"
    "residual-wram-visual-metadata-abi.json"
)
ABI_SHA256 = "4cee47ab097986d50ed0d3b3017fc4fd429037405ee247876022dfd08beac260"
OWNERSHIP_PATH = Path(
    "artifacts/residual-wram-tilemap-resource-ownership-v1/"
    "resource-ownership.json"
)
OWNERSHIP_SHA256 = (
    "1eea02442ad5ad7e717d450433404c3e9cac2fe21214c79be83a37aa90b5ced7"
)
REGISTRY_PATH = Path("sequel/image-resource-regions.json")
ARTIFACT_ID = "residual-wram-derived-tilemap-relocation-v1"
PAYLOAD_SCHEMA = "residual-wram-derived-tilemap-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
IMPLEMENTATION_PATHS = (
    "tools/export_residual_wram_visual_metadata_abi.py",
    "tools/verify_residual_wram_visual_metadata_abi.py",
    "tools/export_residual_wram_tilemap_resource_ownership.py",
    "tools/verify_residual_wram_tilemap_resource_ownership.py",
    "tools/import_residual_wram_derived_tilemap_relocations.py",
    "tools/extract_tileset.py",
    "tools/gba_image_export.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/automated_test.py",
    "tools/export_residual_wram_derived_tilemap_relocation_audit.py",
    "tools/verify_residual_wram_derived_tilemap_relocation_audit.py",
)
SCOPE = {
    "proved": (
        "All four remaining pointer-reachable WRAM tilemap sources and their "
        "four exact aligned roots relocate into an owned 16 MiB ROM region, "
        "with their BG controls, graphics and palettes bound to a separately "
        "verified seven-source ownership catalog."
    ),
    "editable": (
        "All 832 u16 entries keep source geometry and palette bank while "
        "selecting tiles inside each source's observed range and using H/V "
        "flip bits."
    ),
    "not_proved": (
        "Natural runtime reachability, queue-slot success and flush, exact "
        "natural-language screen identity, and final screen pixel or timing "
        "equivalence."
    ),
}
SOURCES = (
    (0x083F2108, 0x08BD60, 800, 40, 10, 10, (1, 16), "direct_cpu_crop_tilemap"),
    (
        0x084634B8,
        0x090BDC,
        288,
        12,
        12,
        12,
        (0, 54),
        "transformed_strided_queue_tilemap",
    ),
    (
        0x0846356C,
        0x090DDC,
        288,
        12,
        12,
        13,
        (0, 75),
        "transformed_strided_queue_tilemap",
    ),
    (
        0x084635D8,
        0x090DE8,
        288,
        12,
        12,
        13,
        (0, 95),
        "transformed_strided_queue_tilemap",
    ),
)
DESTINATIONS = {
    0x083F2108: 0x06001100,
    0x084634B8: 0x06000806,
    0x0846356C: 0x06000806,
    0x084635D8: 0x06000806,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def _align(value: int) -> int:
    return (value + 3) & ~3


def _decode_lz77(data: bytes, offset: int) -> tuple[bytes, int]:
    if data[offset] != 0x10:
        raise ValueError("invalid LZ77 header")
    size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    cursor = offset + 4
    output = bytearray()
    while len(output) < size:
        flags = data[cursor]
        cursor += 1
        for bit in range(8):
            if len(output) >= size:
                break
            if flags & (0x80 >> bit):
                token = (data[cursor] << 8) | data[cursor + 1]
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
                output.append(data[cursor])
                cursor += 1
    return bytes(output), cursor - offset


def _encode_lz77(data: bytes) -> bytes:
    output = bytearray(
        (0x10, len(data) & 0xFF, (len(data) >> 8) & 0xFF, len(data) >> 16)
    )
    positions: dict[bytes, deque[int]] = {}
    cursor = 0
    while cursor < len(data):
        flags_offset = len(output)
        output.append(0)
        flags = 0
        for token_index in range(8):
            if cursor >= len(data):
                break
            best_length = 0
            best_distance = 0
            if cursor + 3 <= len(data):
                key = data[cursor : cursor + 3]
                candidates = positions.get(key, ())
                for previous in reversed(candidates):
                    distance = cursor - previous
                    if distance > 0x1000:
                        break
                    if distance == 1:
                        continue
                    length = 3
                    while (
                        length < 18
                        and cursor + length < len(data)
                        and data[previous + length] == data[cursor + length]
                    ):
                        length += 1
                    if length > best_length:
                        best_length = length
                        best_distance = distance
                        if length == 18:
                            break
            consumed = best_length if best_length >= 3 else 1
            for index in range(consumed):
                position = cursor + index
                if position + 3 <= len(data):
                    key = data[position : position + 3]
                    queue = positions.setdefault(key, deque())
                    queue.append(position)
                    while queue and position - queue[0] > 0x1000:
                        queue.popleft()
            if best_length >= 3:
                flags |= 0x80 >> token_index
                displacement = best_distance - 1
                output.extend(
                    (
                        ((best_length - 3) << 4) | (displacement >> 8),
                        displacement & 0xFF,
                    )
                )
                cursor += best_length
            else:
                output.append(data[cursor])
                cursor += 1
        output[flags_offset] = flags
    return bytes(output)


def _source_metadata(
    data: bytes,
    width: int,
    height: int,
    bank: int,
    tile_range: tuple[int, int],
) -> tuple[int, str]:
    if len(data) != width * height * 2:
        raise ValueError("tilemap geometry mismatch")
    values = struct.unpack(f"<{width * height}H", data)
    tiles = [value & 0x03FF for value in values]
    if sorted({value >> 12 for value in values}) != [bank]:
        raise ValueError("tilemap palette mismatch")
    if min(tiles) < tile_range[0] or max(tiles) > tile_range[1]:
        raise ValueError("tilemap tile range mismatch")
    return len(values), _sha256(data)


def _literal_worst_case(sizes: list[int], start: int) -> int:
    cursor = start
    for size in sizes:
        cursor = _align(cursor)
        cursor += 4 + size + (size + 7) // 8
    return cursor - start


def _registry_region(root: Path) -> tuple[int, int, str]:
    path = root / REGISTRY_PATH
    registry = json.loads(path.read_text(encoding="utf-8"))
    regions = registry.get("regions", [])
    previous = 0x800000
    target = None
    for row in regions:
        start = int(row["start"], 16)
        end = int(row["end"], 16)
        if start != previous or end <= start or start % 4 or end % 4:
            raise ValueError("image region registry continuity mismatch")
        previous = end
        if row["id"] == "residual-wram-derived-tilemaps":
            target = row
    if previous != 0xC00000 or target is None:
        raise ValueError("image region registry coverage mismatch")
    if target["owner"] != "residual_wram_derived_tilemaps":
        raise ValueError("derived tilemap region owner mismatch")
    return int(target["start"], 16), int(target["end"], 16), _sha256(
        path.read_bytes()
    )


def _expected_spec(
    artifact: Path,
    registry_hash: str,
) -> tuple[dict[str, Any], dict[int, Path]]:
    spec = json.loads((artifact / SPEC_NAME).read_text(encoding="utf-8"))
    required = {
        "schema": "residual-wram-derived-tilemap-relocation-v1",
        "base_rom_sha256": ROM_SHA256,
        "abi_artifact": ABI_PATH.as_posix(),
        "abi_sha256": ABI_SHA256,
        "resource_ownership_artifact": OWNERSHIP_PATH.as_posix(),
        "resource_ownership_sha256": OWNERSHIP_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGISTRY_PATH.as_posix(),
        "region_registry_sha256": registry_hash,
        "region": "residual-wram-derived-tilemaps",
        "region_owner": "residual_wram_derived_tilemaps",
    }
    for key, value in required.items():
        if spec.get(key) != value:
            raise ValueError(f"authoring spec {key} mismatch")
    rows = spec.get("resources")
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError("authoring spec resource denominator mismatch")
    files = {}
    for row in rows:
        pointer = int(row["source_pointer"], 16)
        name = Path(row["tilemap_file"]).name
        path = artifact / name
        if pointer in files or pointer not in {source[0] for source in SOURCES}:
            raise ValueError("authoring spec source mismatch")
        files[pointer] = path
    if set(files) != {source[0] for source in SOURCES}:
        raise ValueError("authoring spec source set mismatch")
    return spec, files


def _ownership_records(root: Path) -> dict[int, dict[str, Any]]:
    raw = (root / OWNERSHIP_PATH).read_bytes()
    if _sha256(raw) != OWNERSHIP_SHA256:
        raise ValueError("resource ownership hash mismatch")
    ownership = json.loads(raw)
    if (
        ownership.get("schema")
        != "residual-wram-tilemap-resource-ownership-v1"
        or ownership.get("summary")
        != {
            "bg_control_complete_count": 7,
            "graphics_ownership_complete_count": 7,
            "palette_ownership_complete_count": 7,
            "remaining_unresolved_count": 0,
            "tilemap_source_count": 7,
        }
        or ownership.get("remaining_unresolved") != []
        or not ownership.get("scope", {}).get(
            "graphics_and_palette_ownership_complete"
        )
    ):
        raise ValueError("resource ownership contract mismatch")
    rows = ownership.get("ownership_records")
    if not isinstance(rows, list) or len(rows) != 7:
        raise ValueError("resource ownership denominator mismatch")
    records = {
        int(row.get("tilemap_source_pointer", "0"), 16): row
        for row in rows
        if isinstance(row, dict)
    }
    if len(records) != 7:
        raise ValueError("resource ownership source set mismatch")
    return records


def _validate_ownership_source(
    owner: object,
    *,
    destination: int,
    tile_range: tuple[int, int],
    tile_add: int,
    palette_bank: int,
) -> None:
    if (
        not isinstance(owner, dict)
        or owner.get("vram_destination") != f"0x{destination:08X}"
        or owner.get("source_tile_index_range") != list(tile_range)
        or owner.get("effective_tile_index_range")
        != [tile_range[0] + tile_add, tile_range[1] + tile_add]
        or owner.get("tile_index_add") != tile_add
        or [row.get("bank") for row in owner.get("palettes", [])]
        != [palette_bank]
    ):
        raise ValueError("resource ownership source mismatch")


def _rebuild(root: Path, artifact: Path) -> tuple[dict[str, Any], str]:
    base = (root / "rom/base.gba").read_bytes()
    if _sha256(base) != ROM_SHA256 or len(base) != 0x600000:
        raise ValueError("base ROM mismatch")
    if _sha256((root / ABI_PATH).read_bytes()) != ABI_SHA256:
        raise ValueError("ABI mismatch")
    ownership = _ownership_records(root)
    layout_path = root / "sequel/rom-layout.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    if (
        int(layout["target_rom_size"], 16) != 0x1000000
        or int(layout["fill_byte"], 16) != 0xFF
    ):
        raise ValueError("ROM layout mismatch")
    region_start, region_end, registry_hash = _registry_region(root)
    if (region_start, region_end) != (0xBC1400, 0xBC1C00):
        raise ValueError("derived tilemap region bounds mismatch")
    spec, files = _expected_spec(artifact, registry_hash)

    output = bytearray(base)
    output.extend(bytes([0xFF]) * (0x1000000 - len(output)))
    cursor = region_start
    allocations = []
    redirects = []
    source_rows = []
    for (
        pointer,
        root_offset,
        size,
        width,
        height,
        bank,
        tile_range,
        classification,
    ) in SOURCES:
        owner = ownership.get(pointer)
        tile_add = 0x02BC if classification == (
            "transformed_strided_queue_tilemap"
        ) else 0
        _validate_ownership_source(
            owner,
            destination=DESTINATIONS[pointer],
            tile_range=tile_range,
            tile_add=tile_add,
            palette_bank=bank,
        )
        original, _ = _decode_lz77(base, pointer - ROM_BASE)
        data = files[pointer].read_bytes()
        if data != original or len(data) != size:
            raise ValueError("preservation tilemap differs from ROM")
        count, digest = _source_metadata(
            data, width, height, bank, tile_range
        )
        needle = struct.pack("<I", pointer)
        roots = [
            offset
            for offset in range(0, len(base) - 3, 4)
            if base[offset : offset + 4] == needle
        ]
        if roots != [root_offset]:
            raise ValueError("source pointer denominator mismatch")
        encoded = _encode_lz77(data)
        cursor = _align(cursor)
        end = cursor + len(encoded)
        if end > region_end or output[cursor:end] != bytes([0xFF]) * len(encoded):
            raise ValueError("allocation exceeds or collides with region")
        output[cursor:end] = encoded
        new_pointer = ROM_BASE + cursor
        if output[root_offset : root_offset + 4] != needle:
            raise ValueError("pointer redirect precondition mismatch")
        output[root_offset : root_offset + 4] = struct.pack("<I", new_pointer)
        allocations.append(
            {
                "source_pointer": f"0x{pointer:08X}",
                "offset": cursor,
                "new_pointer": f"0x{new_pointer:08X}",
                "encoded_size": len(encoded),
                "replacement_sha256": digest,
            }
        )
        redirects.append(
            {
                "source_pointer": f"0x{pointer:08X}",
                "offset": root_offset,
                "new_pointer": f"0x{new_pointer:08X}",
            }
        )
        name = files[pointer].name
        source_rows.append(
            {
                "source_pointer": f"0x{pointer:08X}",
                "classification": classification,
                "decoded_size": size,
                "decoded_sha256": digest,
                "entry_count": count,
                "pointer_offsets": roots,
                "tilemap_file": name,
                "tilemap_file_sha256": _sha256(data),
            }
        )
        cursor = end
    summary = {
        "source_count": 4,
        "source_pointer_reference_count": 4,
        "decoded_size": 1664,
        "entry_count": 832,
        "allocation_count": 4,
        "pointer_patch_count": 4,
        "applied_patch_count": 8,
        "allocation_start": region_start,
        "allocation_end": cursor,
        "region_end": region_end,
        "stored_payload_bytes": sum(
            row["encoded_size"] for row in allocations
        ),
        "allocation_span": cursor - region_start,
        "remaining_bytes": region_end - cursor,
        "literal_lz77_worst_case_bytes_with_alignment": _literal_worst_case(
            [800, 288, 288, 288], region_start
        ),
    }
    mutated_output = bytearray(base)
    mutated_output.extend(bytes([0xFF]) * (0x1000000 - len(mutated_output)))
    mutated_cursor = region_start
    for (
        pointer,
        root_offset,
        _size,
        width,
        height,
        bank,
        tile_range,
        _classification,
    ) in SOURCES:
        mutated = bytearray(files[pointer].read_bytes())
        entry = struct.unpack_from("<H", mutated, 0)[0]
        struct.pack_into("<H", mutated, 0, entry ^ 0x0400)
        _source_metadata(bytes(mutated), width, height, bank, tile_range)
        encoded = _encode_lz77(bytes(mutated))
        mutated_cursor = _align(mutated_cursor)
        end = mutated_cursor + len(encoded)
        if (
            end > region_end
            or mutated_output[mutated_cursor:end]
            != bytes([0xFF]) * len(encoded)
        ):
            raise ValueError("capability allocation exceeds its region")
        mutated_output[mutated_cursor:end] = encoded
        new_pointer = ROM_BASE + mutated_cursor
        needle = struct.pack("<I", pointer)
        if mutated_output[root_offset : root_offset + 4] != needle:
            raise ValueError("capability pointer precondition mismatch")
        mutated_output[root_offset : root_offset + 4] = struct.pack(
            "<I", new_pointer
        )
        mutated_cursor = end
    capability_fixture = {
        "mutation": "toggle H-flip on entry 0 of every tilemap source",
        "changed_entries": 4,
        "output_rom_sha256": _sha256(mutated_output),
    }
    expected = {
        "schema": PAYLOAD_SCHEMA,
        "base_rom": {
            "path": "rom/base.gba",
            "size": len(base),
            "sha256": ROM_SHA256,
        },
        "layout": {
            "path": "sequel/rom-layout.json",
            "sha256": _sha256(layout_path.read_bytes()),
            "target_rom_size": 0x1000000,
        },
        "region_registry": {
            "path": REGISTRY_PATH.as_posix(),
            "sha256": registry_hash,
            "region": "residual-wram-derived-tilemaps",
            "owner": "residual_wram_derived_tilemaps",
            "start": region_start,
            "end": region_end,
        },
        "abi": {"path": ABI_PATH.as_posix(), "sha256": ABI_SHA256},
        "resource_ownership": {
            "path": OWNERSHIP_PATH.as_posix(),
            "sha256": OWNERSHIP_SHA256,
            "verified_source_count": 4,
        },
        "authoring_spec": {
            "file": SPEC_NAME,
            "sha256": _sha256((artifact / SPEC_NAME).read_bytes()),
        },
        "sources": source_rows,
        "allocations": allocations,
        "redirects": redirects,
        "summary": summary,
        "scope": SCOPE,
        "capability_fixture": capability_fixture,
        "output_rom_sha256": _sha256(output),
        "implementation": {
            path: _sha256((root / path).read_bytes())
            for path in IMPLEMENTATION_PATHS
        },
    }
    return expected, _sha256(output)


def verify_audit(root: Path, artifact: Path) -> dict[str, Any]:
    errors = []
    rebuilt_hash = None
    try:
        root = Path(root).resolve()
        artifact = Path(artifact).resolve()
        expected_files = {
            PAYLOAD_NAME,
            SPEC_NAME,
            "manifest.json",
            *(f"tilemap-{source[0]:08x}.bin" for source in SOURCES),
        }
        actual_files = {
            path.relative_to(artifact).as_posix()
            for path in artifact.rglob("*")
            if path.is_file()
        }
        if actual_files != expected_files:
            raise ValueError("artifact file inventory mismatch")
        if any(path.is_symlink() for path in artifact.rglob("*")):
            raise ValueError("artifact contains symbolic links")
        payload_bytes = (artifact / PAYLOAD_NAME).read_bytes()
        payload = json.loads(payload_bytes)
        expected, rebuilt_hash = _rebuild(root, artifact)
        if payload != expected:
            raise ValueError("relocation audit semantic reconstruction mismatch")
        if payload_bytes != _canonical_json(expected):
            raise ValueError("relocation audit canonical serialization mismatch")
        manifest = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )
        file_hashes = {
            name: _sha256((artifact / name).read_bytes())
            for name in sorted(expected_files - {"manifest.json"})
        }
        expected_verifier = {
            "command": [
                "python3",
                "tools/verify_residual_wram_derived_tilemap_relocation_audit.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{ARTIFACT_ID}",
            ],
            "exit_code": 0,
        }
        if (
            manifest.get("schema") != "git-artifact-promotion-v1"
            or manifest.get("artifact_id") != ARTIFACT_ID
            or manifest.get("artifact_schema") != PAYLOAD_SCHEMA
            or manifest.get("artifact_status") != "accepted"
            or manifest.get("payload_file") != PAYLOAD_NAME
            or manifest.get("payload_sha256") != _sha256(payload_bytes)
            or manifest.get("files") != file_hashes
            or manifest.get("implementation") != expected["implementation"]
            or manifest.get("summary") != expected["summary"]
            or manifest.get("scope") != SCOPE
            or manifest.get("verifier") != expected_verifier
        ):
            raise ValueError("manifest contract mismatch")
    except Exception as error:
        errors.append(str(error))
    return {
        "schema": (
            "residual-wram-derived-tilemap-relocation-audit-verification-v1"
        ),
        "verified_sources": 0 if errors else 4,
        "verified_source_pointers": 0 if errors else 4,
        "rebuilt_output_rom_sha256": rebuilt_hash,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path(
            "artifacts/residual-wram-derived-tilemap-relocation-v1"
        ),
    )
    args = parser.parse_args()
    report = verify_audit(args.root, args.artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
