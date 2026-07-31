#!/usr/bin/env python3
"""Independently verify the residual WRAM tilemap relocation artifact."""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ABI_PATH = Path(
    "artifacts/residual-wram-tilemap-abi-v1/"
    "residual-wram-tilemap-abi.json"
)
ABI_SHA256 = "07e1f89b5aaff938184d5d31bea4174e995f96d10b8ffbee56bff0f609a27dfc"
OWNERSHIP_PATH = Path(
    "artifacts/residual-wram-tilemap-resource-ownership-v1/"
    "resource-ownership.json"
)
OWNERSHIP_SHA256 = (
    "1eea02442ad5ad7e717d450433404c3e9cac2fe21214c79be83a37aa90b5ced7"
)
REGISTRY_PATH = Path("sequel/image-resource-regions.json")
LAYOUT_PATH = Path("sequel/rom-layout.json")
ARTIFACT_ID = "residual-wram-tilemap-relocation-v1"
PAYLOAD_SCHEMA = "residual-wram-tilemap-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
REGION_START = 0xBC0C00
REGION_END = 0xBC1400
TARGET_ROM_SIZE = 0x1000000
SOURCE_ROOTS = {
    0x0834928C: 0x08AEE0,
    0x083F1C98: 0x08BD38,
    0x085B67E0: 0x08BD48,
}
IMPLEMENTATION_PATHS = (
    "tools/export_residual_wram_tilemap_abi.py",
    "tools/verify_residual_wram_tilemap_abi.py",
    "tools/export_residual_wram_tilemap_resource_ownership.py",
    "tools/verify_residual_wram_tilemap_resource_ownership.py",
    "tools/import_residual_wram_tilemap_relocations.py",
    "tools/extract_tileset.py",
    "tools/gba_image_export.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_residual_wram_tilemap_relocation_audit.py",
    "tools/verify_residual_wram_tilemap_relocation_audit.py",
)
SCOPE = {
    "proved": (
        "The three pointer/literal-reachable residual WRAM tilemaps at "
        "0x0834928C, 0x083F1C98 and 0x085B67E0 and all three exact aligned "
        "source roots relocate into one owned region of a 16 MiB ROM, with "
        "their BG controls, graphics and palettes bound to a separately "
        "verified seven-source ownership catalog."
    ),
    "editable": (
        "All 657 entries keep their proven geometry and palette bank while "
        "selecting tiles inside each source's observed range and using "
        "standard horizontal or vertical flip bits."
    ),
    "not_proved": (
        "Computed-pointer consumers outside the proved pointer/literal roots, "
        "queue-slot success or natural flush, runtime reachability of every "
        "static caller, exact natural-language screen identity, and final "
        "screen pixel or timing equivalence."
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise ValueError(f"{label} must be an integer")


def _power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


def _align(value: int, alignment: int = 4) -> int:
    return (value + alignment - 1) & -alignment


def _literal_worst_case_span(
    decoded_sizes: list[int],
    *,
    start: int,
) -> int:
    cursor = start
    for size in decoded_sizes:
        cursor = _align(cursor)
        cursor += 4 + size + (size + 7) // 8
    return cursor - start


def _decode_lz77(data: bytes, offset: int) -> tuple[bytes, int]:
    if offset < 0 or offset + 4 > len(data) or data[offset] != 0x10:
        raise ValueError("invalid LZ77 header")
    size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    cursor = offset + 4
    output = bytearray()
    while len(output) < size:
        if cursor >= len(data):
            raise ValueError("truncated LZ77 flags")
        flags = data[cursor]
        cursor += 1
        for bit in range(8):
            if len(output) >= size:
                break
            if flags & (0x80 >> bit):
                if cursor + 2 > len(data):
                    raise ValueError("truncated LZ77 token")
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
                if cursor >= len(data):
                    raise ValueError("truncated LZ77 literal")
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
        flag_offset = len(output)
        output.append(0)
        flags = 0
        for token_index in range(8):
            if cursor >= len(data):
                break
            best_length = 0
            best_distance = 0
            if cursor + 3 <= len(data):
                key = data[cursor : cursor + 3]
                for previous in reversed(positions.get(key, ())):
                    distance = cursor - previous
                    if distance > 0x1000:
                        break
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
            if best_length >= 3:
                flags |= 1 << (7 - token_index)
                token = ((best_length - 3) << 12) | (best_distance - 1)
                output.extend((token >> 8, token & 0xFF))
                advance = best_length
            else:
                output.append(data[cursor])
                advance = 1
            for position in range(cursor, cursor + advance):
                if position + 3 <= len(data):
                    key = data[position : position + 3]
                    bucket = positions.setdefault(key, deque())
                    bucket.append(position)
                    while bucket and position - bucket[0] > 0x1000:
                        bucket.popleft()
            cursor += advance
        output[flag_offset] = flags
    return bytes(output)


def _aligned_offsets(data: bytes, pointer: int) -> list[int]:
    raw = struct.pack("<I", pointer)
    return [
        offset
        for offset in range(0, len(data) - 3, 4)
        if data[offset : offset + 4] == raw
    ]


def _metadata(data: bytes, record: dict[str, Any]) -> dict[str, Any]:
    tilemap = record["tilemap"]
    expected_size = tilemap["entry_count"] * 2
    if (
        len(data) != expected_size
        or tilemap["width_entries"] * tilemap["height_entries"]
        != tilemap["entry_count"]
    ):
        raise ValueError("tilemap geometry mismatch")
    entries = struct.unpack(f"<{tilemap['entry_count']}H", data)
    tiles = [entry & 0x03FF for entry in entries]
    banks = sorted({entry >> 12 for entry in entries})
    minimum, maximum = tilemap["tile_index_range"]
    if min(tiles) < minimum or max(tiles) > maximum:
        raise ValueError("tilemap index range mismatch")
    if banks != tilemap["palette_banks"]:
        raise ValueError("tilemap palette bank mismatch")
    return {
        "entry_count": len(entries),
        "tile_index_range": [min(tiles), max(tiles)],
        "palette_banks": banks,
        "horizontal_flip_count": sum(bool(entry & 0x0400) for entry in entries),
        "vertical_flip_count": sum(bool(entry & 0x0800) for entry in entries),
    }


def _validate_layout_and_regions(
    base: bytes,
    layout: dict[str, Any],
    registry: dict[str, Any],
) -> None:
    if layout.get("version") != 1:
        raise ValueError("ROM layout version mismatch")
    base_spec = layout.get("base_rom")
    if (
        not isinstance(base_spec, dict)
        or _integer(base_spec.get("size"), "base size") != len(base)
        or str(base_spec.get("sha1", "")).lower()
        != hashlib.sha1(base).hexdigest()
        or _integer(layout.get("target_rom_size"), "target size")
        != TARGET_ROM_SIZE
        or _integer(layout.get("fill_byte"), "fill byte") != 0xFF
    ):
        raise ValueError("ROM layout base contract mismatch")
    partitions = layout.get("partitions")
    if not isinstance(partitions, list) or not partitions:
        raise ValueError("ROM layout partitions are invalid")
    normalized = []
    seen = set()
    for row in partitions:
        if not isinstance(row, dict):
            raise ValueError("ROM layout partition is invalid")
        identifier = str(row.get("id", "")).strip()
        owner = str(row.get("owner", "")).strip()
        origin = str(row.get("origin", "")).strip()
        start = _integer(row.get("start"), "partition start")
        end = _integer(row.get("end"), "partition end")
        alignment = _integer(row.get("alignment", 1), "alignment")
        if (
            not identifier
            or identifier in seen
            or not owner
            or origin not in {"base_ff", "expanded_ff"}
            or start < 0
            or end <= start
            or end > TARGET_ROM_SIZE
            or not _power_of_two(alignment)
            or start % alignment
            or end % alignment
        ):
            raise ValueError("ROM layout partition contract mismatch")
        seen.add(identifier)
        normalized.append(
            (start, end, identifier, owner, origin, alignment)
        )
    normalized.sort()
    if any(
        left[1] > right[0]
        for left, right in zip(normalized, normalized[1:])
    ):
        raise ValueError("ROM layout partitions overlap")
    parent = [row for row in normalized if row[2] == "sequel-image-assets"]
    if parent != [
        (
            0x800000,
            0xC00000,
            "sequel-image-assets",
            "sequel_image_assets",
            "expanded_ff",
            4,
        )
    ]:
        raise ValueError("image resource parent partition mismatch")
    if (
        registry.get("version") != 1
        or registry.get("parent_partition") != "sequel-image-assets"
        or registry.get("parent_owner") != "sequel_image_assets"
    ):
        raise ValueError("image region parent mismatch")
    raw_regions = registry.get("regions")
    if not isinstance(raw_regions, list) or not raw_regions:
        raise ValueError("image regions are invalid")
    regions = []
    seen = set()
    for row in raw_regions:
        if not isinstance(row, dict):
            raise ValueError("image region is invalid")
        identifier = str(row.get("id", "")).strip()
        owner = str(row.get("owner", "")).strip()
        start = _integer(row.get("start"), "region start")
        end = _integer(row.get("end"), "region end")
        alignment = _integer(row.get("alignment"), "alignment")
        if (
            not identifier
            or identifier in seen
            or not owner
            or start < 0x800000
            or end <= start
            or end > 0xC00000
            or not _power_of_two(alignment)
            or start % alignment
            or end % alignment
        ):
            raise ValueError("image region contract mismatch")
        seen.add(identifier)
        regions.append((start, end, identifier, owner, alignment))
    regions.sort()
    cursor = 0x800000
    for row in regions:
        if row[0] != cursor:
            raise ValueError("image regions have a gap or overlap")
        cursor = row[1]
    if cursor != 0xC00000:
        raise ValueError("image regions do not cover parent")
    target = [row for row in regions if row[2] == "residual-wram-tilemaps"]
    if target != [
        (
            REGION_START,
            REGION_END,
            "residual-wram-tilemaps",
            "residual_wram_tilemaps",
            4,
        )
    ]:
        raise ValueError("residual WRAM tilemap region mismatch")


def _published_asset_path(name: str) -> str:
    return f"artifacts/{ARTIFACT_ID}/{name}"


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


def _source_records(
    base: bytes,
    abi: dict[str, Any],
    ownership: dict[int, dict[str, Any]],
) -> list[tuple[int, dict[str, Any], bytes]]:
    if (
        abi.get("schema") != "residual-wram-tilemap-abi-v1"
        or abi.get("summary")
        != {
            "wram_visual_metadata_denominator": 7,
            "direct_tilemap_queue_abi_count": 3,
            "remaining_unresolved_count": 4,
            "tilemap_entry_count": 657,
            "tilemap_payload_bytes": 1314,
        }
        or abi.get("remaining_unresolved")
        != ["0x083F2108", "0x084634B8", "0x0846356C", "0x084635D8"]
    ):
        raise ValueError("ABI contract mismatch")
    records = abi.get("tilemaps")
    if not isinstance(records, list) or len(records) != 3:
        raise ValueError("ABI source denominator mismatch")
    result = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("ABI source row mismatch")
        pointer = int(record.get("source_pointer", "0"), 16)
        if pointer not in SOURCE_ROOTS:
            raise ValueError("ABI source pointer mismatch")
        owner = ownership.get(pointer)
        if (
            not isinstance(owner, dict)
            or owner.get("vram_destination") != record["vram_destination"]
            or owner.get("source_tile_index_range")
            != record["tilemap"]["tile_index_range"]
            or owner.get("effective_tile_index_range")
            != record["tilemap"]["tile_index_range"]
            or [row.get("bank") for row in owner.get("palettes", [])]
            != record["tilemap"]["palette_banks"]
        ):
            raise ValueError("resource ownership source mismatch")
        decoded, consumed = _decode_lz77(base, pointer - ROM_BASE)
        compressed = base[
            pointer - ROM_BASE :
            pointer - ROM_BASE + record.get("compressed_size", 0)
        ]
        metadata = _metadata(decoded, record)
        if (
            consumed != record.get("compressed_size")
            or _sha256(compressed) != record.get("compressed_sha256")
            or len(decoded) != record.get("decompressed_size")
            or _sha256(decoded) != record.get("decompressed_sha256")
            or _aligned_offsets(base, pointer) != [SOURCE_ROOTS[pointer]]
            or metadata
            != {
                "entry_count": record["tilemap"]["entry_count"],
                "tile_index_range": record["tilemap"]["tile_index_range"],
                "palette_banks": record["tilemap"]["palette_banks"],
                "horizontal_flip_count": record["tilemap"][
                    "horizontal_flip_count"
                ],
                "vertical_flip_count": record["tilemap"][
                    "vertical_flip_count"
                ],
            }
        ):
            raise ValueError("ABI source bytes or root mismatch")
        result.append((pointer, record, decoded))
    result.sort()
    if [pointer for pointer, _, _ in result] != sorted(SOURCE_ROOTS):
        raise ValueError("ABI source set mismatch")
    return result


def _build_rom(
    base: bytes,
    sources: list[tuple[int, dict[str, Any], bytes]],
) -> tuple[bytes, list[dict[str, Any]], list[dict[str, Any]]]:
    output = bytearray(base)
    output.extend(bytes([0xFF]) * (TARGET_ROM_SIZE - len(output)))
    cursor = REGION_START
    allocations = []
    redirects = []
    for pointer, record, decoded in sources:
        metadata = _metadata(decoded, record)
        encoded = _encode_lz77(decoded)
        offset = _align(cursor)
        end = offset + len(encoded)
        if end > REGION_END:
            raise ValueError("encoded batch exceeds region")
        if any(value != 0xFF for value in output[offset:end]):
            raise ValueError("allocation target is not erased")
        output[offset:end] = encoded
        new_pointer = ROM_BASE + offset
        root = SOURCE_ROOTS[pointer]
        if output[root : root + 4] != struct.pack("<I", pointer):
            raise ValueError("source pointer precondition mismatch")
        output[root : root + 4] = struct.pack("<I", new_pointer)
        allocations.append(
            {
                "id": f"residual-wram-tilemap-{pointer:08x}",
                "offset": offset,
                "source_pointer": pointer,
                "new_pointer": new_pointer,
                "replacement_sha256": _sha256(decoded),
                "decoded_size": len(decoded),
                "encoded_size": len(encoded),
                "width_entries": record["tilemap"]["width_entries"],
                "height_entries": record["tilemap"]["height_entries"],
                **metadata,
                "vram_destination": record["vram_destination"],
                "screenblock": record["screenblock"],
            }
        )
        redirects.append(
            {
                "id": (
                    f"residual-wram-tilemap-{pointer:08x}."
                    f"pointer-{root:06x}"
                ),
                "offset": root,
                "source_pointer": pointer,
                "new_pointer": new_pointer,
                "pointer_role": "tilemap_source",
            }
        )
        cursor = end
    return bytes(output), allocations, redirects


def verify_audit(root: Path, artifact: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    artifact = Path(artifact).resolve()
    errors: list[str] = []
    rebuilt_sha = None
    try:
        expected_names = {
            "manifest.json",
            PAYLOAD_NAME,
            SPEC_NAME,
            "tilemap-0834928c.bin",
            "tilemap-083f1c98.bin",
            "tilemap-085b67e0.bin",
        }
        actual_names = {
            path.relative_to(artifact).as_posix()
            for path in artifact.rglob("*")
            if path.is_file()
        }
        if actual_names != expected_names:
            raise ValueError("artifact file inventory mismatch")
        if any(path.is_symlink() for path in artifact.rglob("*")):
            raise ValueError("artifact contains symbolic links")
        manifest = json.loads((artifact / "manifest.json").read_bytes())
        payload = json.loads((artifact / PAYLOAD_NAME).read_bytes())
        spec = json.loads((artifact / SPEC_NAME).read_bytes())
        files = {
            name: _sha256((artifact / name).read_bytes())
            for name in sorted(expected_names - {"manifest.json"})
        }
        if (
            manifest.get("schema") != "git-artifact-promotion-v1"
            or manifest.get("artifact_id") != ARTIFACT_ID
            or manifest.get("artifact_schema") != PAYLOAD_SCHEMA
            or manifest.get("artifact_status") != "accepted"
            or manifest.get("payload_file") != PAYLOAD_NAME
            or manifest.get("payload_sha256") != files[PAYLOAD_NAME]
            or manifest.get("files") != files
            or manifest.get("implementation") != payload.get("implementation")
            or manifest.get("scope") != SCOPE
            or manifest.get("verifier")
            != {
                "command": [
                    "python3",
                    "tools/verify_residual_wram_tilemap_relocation_audit.py",
                    "--root",
                    ".",
                    "--artifact",
                    f"artifacts/{ARTIFACT_ID}",
                ],
                "exit_code": 0,
            }
        ):
            raise ValueError("promotion manifest contract mismatch")
        base = (root / "rom/base.gba").read_bytes()
        if _sha256(base) != ROM_SHA256:
            raise ValueError("base ROM mismatch")
        abi_bytes = (root / ABI_PATH).read_bytes()
        if _sha256(abi_bytes) != ABI_SHA256:
            raise ValueError("ABI hash mismatch")
        abi = json.loads(abi_bytes)
        ownership = _ownership_records(root)
        layout_bytes = (root / LAYOUT_PATH).read_bytes()
        registry_bytes = (root / REGISTRY_PATH).read_bytes()
        layout = json.loads(layout_bytes)
        registry = json.loads(registry_bytes)
        _validate_layout_and_regions(base, layout, registry)
        source_rows = _source_records(base, abi, ownership)
        expected_resources = []
        artifact_sources = []
        for pointer, record, source_decoded in source_rows:
            name = f"tilemap-{pointer:08x}.bin"
            decoded = (artifact / name).read_bytes()
            if decoded != source_decoded:
                raise ValueError("preservation tilemap bytes mismatch")
            _metadata(decoded, record)
            expected_resources.append(
                {
                    "source_pointer": f"0x{pointer:08X}",
                    "tilemap_file": _published_asset_path(name),
                }
            )
            artifact_sources.append((pointer, record, decoded))
        expected_spec = {
            "schema": "residual-wram-tilemap-relocation-v1",
            "base_rom_sha256": ROM_SHA256,
            "abi_artifact": ABI_PATH.as_posix(),
            "abi_sha256": ABI_SHA256,
            "resource_ownership_artifact": OWNERSHIP_PATH.as_posix(),
            "resource_ownership_sha256": OWNERSHIP_SHA256,
            "partition": "sequel-image-assets",
            "owner": "sequel_image_assets",
            "region_registry": REGISTRY_PATH.as_posix(),
            "region_registry_sha256": _sha256(registry_bytes),
            "region": "residual-wram-tilemaps",
            "region_owner": "residual_wram_tilemaps",
            "resources": expected_resources,
        }
        if spec != expected_spec:
            raise ValueError("authoring spec mismatch")
        output, allocations, redirects = _build_rom(base, artifact_sources)
        rebuilt_sha = _sha256(output)
        allocation_end = max(
            row["offset"] + row["encoded_size"] for row in allocations
        )
        summary = {
            "source_count": 3,
            "source_pointer_reference_count": 3,
            "unexpected_source_pointer_count": 0,
            "compressed_source_size": sum(
                record["compressed_size"] for _, record, _ in source_rows
            ),
            "decoded_size": sum(len(data) for _, _, data in source_rows),
            "entry_count": sum(
                record["tilemap"]["entry_count"]
                for _, record, _ in source_rows
            ),
            "allocation_count": 3,
            "pointer_patch_count": 3,
            "allocation_start": REGION_START,
            "allocation_end": allocation_end,
            "region_end": REGION_END,
            "stored_payload_bytes": sum(
                row["encoded_size"] for row in allocations
            ),
            "allocation_span": allocation_end - REGION_START,
            "remaining_bytes": REGION_END - allocation_end,
            "literal_lz77_worst_case_bytes_with_alignment": (
                _literal_worst_case_span(
                    [len(data) for _, _, data in source_rows],
                    start=REGION_START,
                )
            ),
            "applied_patch_count": 6,
        }
        mutated = []
        for pointer, record, decoded in artifact_sources:
            changed = bytearray(decoded)
            struct.pack_into(
                "<H",
                changed,
                0,
                struct.unpack_from("<H", changed, 0)[0] ^ 0x0400,
            )
            mutated.append((pointer, record, bytes(changed)))
        fixture_output, _, _ = _build_rom(base, mutated)
        implementation = {
            path: _sha256((root / path).read_bytes())
            for path in IMPLEMENTATION_PATHS
        }
        expected_payload = {
            "schema": PAYLOAD_SCHEMA,
            "base_rom": {
                "path": "rom/base.gba",
                "size": len(base),
                "sha256": ROM_SHA256,
            },
            "layout": {
                "path": LAYOUT_PATH.as_posix(),
                "sha256": _sha256(layout_bytes),
                "target_rom_size": TARGET_ROM_SIZE,
                "partition": "sequel-image-assets",
                "owner": "sequel_image_assets",
            },
            "region_registry": {
                "path": REGISTRY_PATH.as_posix(),
                "sha256": _sha256(registry_bytes),
                "region": "residual-wram-tilemaps",
                "owner": "residual_wram_tilemaps",
                "start": REGION_START,
                "end": REGION_END,
            },
            "abi": {
                "path": ABI_PATH.as_posix(),
                "sha256": ABI_SHA256,
            },
            "resource_ownership": {
                "path": OWNERSHIP_PATH.as_posix(),
                "sha256": OWNERSHIP_SHA256,
                "verified_source_count": 3,
            },
            "authoring_spec": {
                "file": SPEC_NAME,
                "sha256": _sha256((artifact / SPEC_NAME).read_bytes()),
            },
            "implementation": implementation,
            "summary": summary,
            "allocations": allocations,
            "pointer_patches": redirects,
            "output_rom_sha256": rebuilt_sha,
            "capability_fixture": {
                "mutation": "toggle H-flip on entry 0 of every tilemap",
                "changed_entries": 3,
                "output_rom_sha256": _sha256(fixture_output),
            },
            "scope": SCOPE,
        }
        if payload != expected_payload:
            raise ValueError("audit payload reconstruction mismatch")
        if manifest.get("summary") != summary:
            raise ValueError("manifest summary mismatch")
    except Exception as error:
        errors.append(str(error))
    return {
        "schema": (
            "residual-wram-tilemap-relocation-audit-verification-v1"
        ),
        "verified_sources": 0 if errors else 3,
        "verified_source_pointers": 0 if errors else 3,
        "rebuilt_output_rom_sha256": rebuilt_sha,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts") / ARTIFACT_ID,
    )
    args = parser.parse_args()
    report = verify_audit(args.root, args.artifact)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
