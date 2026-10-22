#!/usr/bin/env python3
"""Independently verify the world-map background relocation artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from collections import deque
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.image_resource_regions import ImageResourceRegions
from tools.rom_layout import RomLayout
from tools.verify_world_map_backgrounds import _lz77_record_and_data


ARTIFACT_ID = "world-map-background-relocation-v1"
PAYLOAD_SCHEMA = "world-map-background-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/world-map-backgrounds-v1/manifest.json")
CATALOG_SHA256 = (
    "b9b879841b7605af80e143a9f2f9bbe2e64754d6390b708033f92cc831bd4dd3"
)
REGISTRY_PATH = Path("sequel/image-resource-regions.json")
TABLE_OFFSET = 0x5A8014
TABLE_HASH = (
    "9ccd6d722b87a8bf910fb45072ad682d89b9cf3432979b163f57283902396f35"
)
ROLE_ORDER = {"graphics": 0, "tilemap": 1, "palette": 2}
ROLE_FIELDS = {
    "graphics": ("graphics_pointer", "graphics_file", "graphics_sha256"),
    "tilemap": ("tilemap_pointer", "tilemap_file", "tilemap_sha256"),
    "palette": ("palette_pointer", "palette_file", "palette_sha256"),
}
IMPLEMENTATION_PATHS = (
    "tools/import_world_map_background_relocations.py",
    "tools/export_world_map_backgrounds.py",
    "tools/verify_world_map_backgrounds.py",
    "tools/gba_image_export.py",
    "tools/extract_tileset.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_world_map_background_relocation_audit.py",
    "tools/verify_world_map_background_relocation_audit.py",
)
EXPECTED_SCOPE = {
    "proved": (
        "All three world-map pages, seven content resources, nine physical "
        "payloads and all nine exact descriptor pointer fields relocate into "
        "the registered world-map-backgrounds image region."
    ),
    "editable": (
        "Each page may use 1..512 complete 8bpp tiles; its fixed 30x20 "
        "tilemap and 160-color palette remain validated together. "
        "Catalog-approved aliases may split without original slot limits."
    ),
    "not_proved": (
        "Location-label text edits, unlock rules, page 1/2 natural runtime "
        "selection, cursor behavior, transition timing or final composed "
        "pixel equivalence after modification."
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def _encode(data: bytes) -> bytes:
    if not data or len(data) >= 1 << 24:
        raise ValueError("independent LZ77 input length is invalid")
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
                for previous in reversed(positions.get(key, ())):
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
            if best_length >= 3:
                flags |= 1 << (7 - token_index)
                encoded = ((best_length - 3) << 12) | (best_distance - 1)
                output.extend((encoded >> 8, encoded & 0xFF))
                advance = best_length
            else:
                output.append(data[cursor])
                advance = 1
            for position in range(cursor, cursor + advance):
                if position + 3 > len(data):
                    continue
                key = data[position : position + 3]
                bucket = positions.setdefault(key, deque())
                bucket.append(position)
                while bucket and position - bucket[0] > 0x1000:
                    bucket.popleft()
            cursor += advance
        output[flags_offset] = flags
    return bytes(output)


def _catalog(
    root: Path,
    base: bytes,
) -> dict[tuple[str, str], dict[str, Any]]:
    catalog_path = root / CATALOG_PATH
    if _sha256_file(catalog_path) != CATALOG_SHA256:
        raise ValueError("world-map independent catalog hash mismatch")
    catalog = _json(catalog_path)
    if (
        catalog.get("schema") != "world-map-backgrounds-v1"
        or catalog.get("rom", {}).get("sha256") != ROM_SHA256
        or len(catalog.get("pages", [])) != 3
    ):
        raise ValueError("world-map independent catalog identity mismatch")
    if _sha256(base[TABLE_OFFSET : TABLE_OFFSET + 36]) != TABLE_HASH:
        raise ValueError("world-map independent descriptor table mismatch")

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    expected_by_pointer: dict[int, set[int]] = {}
    for page_id, page in enumerate(catalog["pages"]):
        if page.get("page_id") != page_id:
            raise ValueError("world-map independent page order mismatch")
        background = page["background"]
        values = struct.unpack_from("<III", base, TABLE_OFFSET + page_id * 12)
        for role, pointer, delta in zip(
            ("graphics", "tilemap", "palette"),
            values,
            (0, 4, 8),
        ):
            pointer_field, file_field, hash_field = ROLE_FIELDS[role]
            if background.get(pointer_field) != f"0x{pointer:08X}":
                raise ValueError("world-map independent pointer mismatch")
            if role == "graphics":
                stored, content = _lz77_record_and_data(base, pointer, 32768)
                storage_kind = "lz77"
            elif role == "tilemap":
                stored, content = _lz77_record_and_data(base, pointer, 1200)
                storage_kind = "lz77"
            else:
                offset = pointer - ROM_BASE
                content = base[offset : offset + 320]
                stored = content
                storage_kind = "raw"
            digest = _sha256(content)
            source_file = background[file_field]
            if (
                background.get(hash_field) != digest
                or (catalog_path.parent / source_file).read_bytes() != content
            ):
                raise ValueError("world-map independent source content mismatch")
            pointer_offset = TABLE_OFFSET + page_id * 12 + delta
            alias = {
                "page_id": page_id,
                "resource_type": role,
                "table_pointer_offset": pointer_offset,
                "source_pointer": pointer,
                "physical_offset": pointer - ROM_BASE,
            }
            key = (role, digest)
            resource = grouped.setdefault(
                key,
                {
                    "resource_type": role,
                    "resource_sha256": digest,
                    "decompressed_size": len(content),
                    "storage_kind": storage_kind,
                    "source_files": [],
                    "physical_offsets": [],
                    "pointer_aliases": [],
                },
            )
            resource["source_files"].append(source_file)
            resource["physical_offsets"].append(pointer - ROM_BASE)
            resource["pointer_aliases"].append(alias)
            expected_by_pointer.setdefault(pointer, set()).add(pointer_offset)

    actual_by_pointer = {pointer: set() for pointer in expected_by_pointer}
    for offset in range(0, len(base) - 3, 4):
        value = int.from_bytes(base[offset : offset + 4], "little")
        if value in actual_by_pointer:
            actual_by_pointer[value].add(offset)
    if any(
        actual_by_pointer[pointer] != expected
        for pointer, expected in expected_by_pointer.items()
    ):
        raise ValueError("world-map independent exact pointer mismatch")
    for resource in grouped.values():
        resource["source_files"] = sorted(set(resource["source_files"]))
        resource["physical_offsets"] = sorted(set(resource["physical_offsets"]))
        resource["pointer_aliases"].sort(
            key=lambda alias: alias["table_pointer_offset"]
        )
    if (
        len(grouped) != 7
        or sum(len(row["physical_offsets"]) for row in grouped.values()) != 9
        or sum(len(row["pointer_aliases"]) for row in grouped.values()) != 9
    ):
        raise ValueError("world-map independent denominator mismatch")
    return grouped


def _expected_spec(
    root: Path,
    base: bytes,
    grouped: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    edits = []
    for resource in sorted(
        grouped.values(),
        key=lambda row: (
            ROLE_ORDER[row["resource_type"]],
            min(
                alias["table_pointer_offset"]
                for alias in row["pointer_aliases"]
            ),
        ),
    ):
        edits.append(
            {
                "id": (
                    f"{resource['resource_type']}-"
                    f"{resource['resource_sha256'][:12]}"
                ),
                "resource_type": resource["resource_type"],
                "resource_sha256": resource["resource_sha256"],
                "source_file": (
                    CATALOG_PATH.parent / resource["source_files"][0]
                ).as_posix(),
                "expected": {
                    "decompressed_size": resource["decompressed_size"],
                    "physical_offsets": resource["physical_offsets"],
                    "pointer_offsets": sorted(
                        alias["table_pointer_offset"]
                        for alias in resource["pointer_aliases"]
                    ),
                },
            }
        )
    return {
        "schema": "world-map-background-relocation-v1",
        "base_rom_sha256": _sha256(base),
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": _sha256_file(root / CATALOG_PATH),
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256_file(root / REGISTRY_PATH),
        "region": "world-map-backgrounds",
        "region_owner": "world_map_background_resources",
        "edits": edits,
    }


def _rebuild(
    root: Path,
    artifact: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    base = (root / "rom/base.gba").read_bytes()
    if _sha256(base) != ROM_SHA256:
        raise ValueError("world-map independent base ROM mismatch")
    grouped = _catalog(root, base)
    spec = _json(artifact / SPEC_NAME)
    if spec != _expected_spec(root, base, grouped):
        raise ValueError("world-map relocation authoring spec mismatch")
    layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    regions = ImageResourceRegions.from_path(root / REGISTRY_PATH, layout)
    region = regions.require(
        "world-map-backgrounds",
        "world_map_background_resources",
    )
    data = bytearray(layout.expanded_base())
    edits_by_key = {
        (edit["resource_type"], edit["resource_sha256"]): edit
        for edit in spec["edits"]
    }
    ordered = sorted(
        grouped.items(),
        key=lambda item: (
            ROLE_ORDER[item[1]["resource_type"]],
            min(
                alias["table_pointer_offset"]
                for alias in item[1]["pointer_aliases"]
            ),
        ),
    )
    if len(edits_by_key) != 7 or len(ordered) != 7:
        raise ValueError("world-map independent content denominator mismatch")

    cursor = region.start
    resources = []
    stored_payload_bytes = 0
    pointer_count = 0
    for index, (key, resource) in enumerate(ordered):
        edit = edits_by_key.get(key)
        if edit is None:
            raise ValueError("world-map independent edit identity mismatch")
        content = (root / edit["source_file"]).read_bytes()
        if (
            _sha256(content) != resource["resource_sha256"]
            or len(content) != resource["decompressed_size"]
        ):
            raise ValueError("world-map independent source payload mismatch")
        encoded = (
            content
            if resource["storage_kind"] == "raw"
            else _encode(content)
        )
        cursor = (cursor + 3) & ~3
        end = cursor + len(encoded)
        if end > region.end:
            raise ValueError("world-map independent allocation exceeds region")
        data[cursor:end] = encoded
        new_pointer = ROM_BASE + cursor
        aliases = resource["pointer_aliases"]
        pointer_offsets = sorted(
            alias["table_pointer_offset"] for alias in aliases
        )
        for alias in aliases:
            pointer_offset = alias["table_pointer_offset"]
            source_pointer = alias["source_pointer"]
            if (
                int.from_bytes(
                    data[pointer_offset : pointer_offset + 4],
                    "little",
                )
                != source_pointer
            ):
                raise ValueError(
                    "world-map independent pointer before-byte mismatch"
                )
            data[pointer_offset : pointer_offset + 4] = new_pointer.to_bytes(
                4,
                "little",
            )
            pointer_count += 1
        role = resource["resource_type"]
        resources.append(
            {
                "id": f"world-map-{role}-{index:02d}",
                "resource_type": role,
                "resource_sha256": resource["resource_sha256"],
                "replacement_sha256": _sha256(content),
                "decompressed_size": len(content),
                "encoded_size": len(encoded),
                "storage_kind": resource["storage_kind"],
                "new_pointer": new_pointer,
                "offset": cursor,
                "physical_offsets": resource["physical_offsets"],
                "all_pointer_offsets": pointer_offsets,
                "target_pointer_offsets": pointer_offsets,
                "logical_aliases": aliases,
                "source_file": edit["source_file"],
            }
        )
        stored_payload_bytes += len(encoded)
        cursor = end
    summary = {
        "page_count": 3,
        "content_resource_count": len(resources),
        "physical_payload_count": 9,
        "logical_pointer_count": pointer_count,
        "unexpected_pointer_count": 0,
        "allocation_count": len(resources),
        "pointer_patch_count": pointer_count,
        "allocation_start": region.start,
        "allocation_end": cursor,
        "region_end": region.end,
        "stored_payload_bytes": stored_payload_bytes,
        "allocation_span": cursor - region.start,
        "remaining_bytes": region.end - cursor,
        "applied_patch_count": len(resources) + pointer_count,
    }
    return summary, resources, _sha256(bytes(data))


def _verify(root: Path, artifact: Path) -> dict[str, Any]:
    manifest = _json(artifact / "manifest.json")
    payload_path = artifact / PAYLOAD_NAME
    spec_path = artifact / SPEC_NAME
    payload = _json(payload_path)
    expected_files = {
        PAYLOAD_NAME: _sha256_file(payload_path),
        SPEC_NAME: _sha256_file(spec_path),
    }
    actual_files = {
        path.relative_to(artifact).as_posix()
        for path in artifact.rglob("*")
        if path.is_file()
    }
    expected_verifier = {
        "command": [
            "python3",
            "tools/verify_world_map_background_relocation_audit.py",
            "--root",
            ".",
            "--artifact",
            f"artifacts/{ARTIFACT_ID}",
        ],
        "exit_code": 0,
    }
    if (
        actual_files != {"manifest.json", PAYLOAD_NAME, SPEC_NAME}
        or manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_id") != ARTIFACT_ID
        or manifest.get("artifact_schema") != PAYLOAD_SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("payload_file") != PAYLOAD_NAME
        or manifest.get("payload_sha256") != expected_files[PAYLOAD_NAME]
        or manifest.get("files") != expected_files
        or manifest.get("scope") != EXPECTED_SCOPE
        or manifest.get("summary") != payload.get("summary")
        or manifest.get("verifier") != expected_verifier
    ):
        raise ValueError("world-map relocation promotion manifest mismatch")
    if (
        payload.get("schema") != PAYLOAD_SCHEMA
        or payload.get("scope") != EXPECTED_SCOPE
        or payload.get("base_rom")
        != {
            "path": "rom/base.gba",
            "size": 0x600000,
            "sha256": ROM_SHA256,
        }
        or payload.get("catalog")
        != {
            "path": CATALOG_PATH.as_posix(),
            "sha256": CATALOG_SHA256,
        }
        or payload.get("authoring_spec")
        != {
            "file": SPEC_NAME,
            "sha256": expected_files[SPEC_NAME],
        }
    ):
        raise ValueError("world-map relocation payload provenance mismatch")
    layout_path = root / "sequel/rom-layout.json"
    registry_path = root / REGISTRY_PATH
    if (
        payload.get("layout")
        != {
            "path": "sequel/rom-layout.json",
            "sha256": _sha256_file(layout_path),
            "target_rom_size": 0x1000000,
            "partition": "sequel-image-assets",
            "owner": "sequel_image_assets",
        }
        or payload.get("region_registry")
        != {
            "path": REGISTRY_PATH.as_posix(),
            "sha256": _sha256_file(registry_path),
            "region": "world-map-backgrounds",
            "owner": "world_map_background_resources",
            "start": 0xB71000,
            "end": 0xB90000,
        }
    ):
        raise ValueError("world-map relocation layout/region mismatch")
    expected_implementation = {
        path: _sha256_file(root / path) for path in IMPLEMENTATION_PATHS
    }
    if payload.get("implementation") != expected_implementation:
        raise ValueError("world-map relocation implementation hashes mismatch")
    summary, resources, output_sha256 = _rebuild(root, artifact)
    if (
        payload.get("summary") != summary
        or payload.get("resources") != resources
        or payload.get("output_rom_sha256") != output_sha256
    ):
        raise ValueError("world-map relocation independent rebuild mismatch")
    return {
        "schema": "world-map-background-relocation-verification-v1",
        "artifact_id": ARTIFACT_ID,
        "verified_payloads": len(resources),
        "verified_pointers": summary["logical_pointer_count"],
        "rebuilt_output_rom_sha256": output_sha256,
        "errors": [],
    }


def verify_audit(root: Path, artifact: Path) -> dict[str, Any]:
    try:
        return _verify(Path(root).resolve(), Path(artifact).resolve())
    except Exception as error:
        return {
            "schema": "world-map-background-relocation-verification-v1",
            "artifact_id": ARTIFACT_ID,
            "verified_payloads": 0,
            "verified_pointers": 0,
            "rebuilt_output_rom_sha256": None,
            "errors": [str(error)],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts") / ARTIFACT_ID,
    )
    args = parser.parse_args()
    artifact = args.artifact
    if not artifact.is_absolute():
        artifact = args.root / artifact
    verification = verify_audit(args.root, artifact)
    print(json.dumps(verification, ensure_ascii=False, indent=2))
    return 0 if not verification["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
