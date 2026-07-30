#!/usr/bin/env python3
"""Independently rebuild and verify the story BG3 relocation artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import encode_gba_lz77
from tools.image_resource_regions import ImageResourceRegions
from tools.rom_layout import RomLayout


ARTIFACT_ID = "story-visual-resource-relocation-v1"
PAYLOAD_SCHEMA = "story-visual-resource-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/story-visual-layers-v1/manifest.json")
CATALOG_SHA256 = "556a7319ce57699e2542c578ce0bd1331b93efda58fde1f364271f12f5052fd8"
SOURCE_ARTIFACT = Path("artifacts/story-visual-resource-sources-v1")
SOURCE_MANIFEST = SOURCE_ARTIFACT / "manifest.json"
SOURCE_PAYLOAD = SOURCE_ARTIFACT / "source-catalog.json"
REGISTRY_PATH = Path("sequel/image-resource-regions.json")
TABLE_OFFSET = 0x54229C
TABLE_ENTRY_COUNT = 24
TABLE_ENTRY_SIZE = 0x10
ROLE_OFFSETS = {"graphics": 0, "palette": 4, "tilemap": 8}
TYPE_ORDER = {"graphics": 0, "palette": 1, "tilemap": 2}
IMPLEMENTATION_PATHS = (
    "tools/import_story_visual_resource_relocations.py",
    "tools/export_story_visual_resource_sources.py",
    "tools/gba_image_export.py",
    "tools/extract_tileset.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_story_visual_resource_relocation_audit.py",
    "tools/verify_story_visual_resource_relocation_audit.py",
    "tools/export_story_visual_layers.py",
    "tools/verify_story_visual_layer_export.py",
)
EXPECTED_SCOPE = {
    "proved": (
        "All 49 story-layer content resources, representing 72 physical LZ77 "
        "payloads and all 72 exact descriptor pointer fields across 24 rows, "
        "relocate into the registered story-visual-layers image region."
    ),
    "editable": (
        "Each layer may replace its 4bpp graphics and 32x32 tilemap together, "
        "including changing the graphics tile count from 1 through 192; the "
        "palette remains 16 colors, tile IDs remain the exact contiguous "
        "0x140-based range and every descriptor alias may split safely, "
        "subject to the aggregate registered-region capacity."
    ),
    "not_proved": (
        "A different BG3 tilemap geometry, more than 192 tiles, another "
        "palette bank, changes to linked tile-assets config descriptors, "
        "scroll/window/blend timing, final screen equivalence or physical "
        "cartridge behavior."
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _validate_view(layer_id: int, view: dict[str, bytes]) -> None:
    graphics = view["graphics"]
    palette = view["palette"]
    tilemap = view["tilemap"]
    if not graphics or len(graphics) % 32 or len(graphics) > 0x1800:
        raise ValueError(f"layer {layer_id} independent graphics shape mismatch")
    if len(palette) != 32 or len(tilemap) != 0x800:
        raise ValueError(f"layer {layer_id} independent fixed payload mismatch")
    entries = struct.unpack("<1024H", tilemap)
    if {entry >> 12 for entry in entries} != {15}:
        raise ValueError(f"layer {layer_id} independent palette bank mismatch")
    tile_count = len(graphics) // 32
    if {entry & 0x03FF for entry in entries} != set(
        range(0x140, 0x140 + tile_count)
    ):
        raise ValueError(f"layer {layer_id} independent tile coverage mismatch")


def _resources(base: bytes) -> dict[tuple[str, str], dict[str, Any]]:
    resources: dict[tuple[str, str], dict[str, Any]] = {}
    expected_by_pointer: dict[int, set[int]] = {}
    for layer_id in range(TABLE_ENTRY_COUNT):
        descriptor = TABLE_OFFSET + layer_id * TABLE_ENTRY_SIZE
        gfx, palette, tilemap, config_id = struct.unpack_from(
            "<IIII",
            base,
            descriptor,
        )
        if not 0 <= config_id < 79:
            raise ValueError("independent story config ID is outside tile-assets")
        view = {}
        for role, field_offset, pointer in (
            ("graphics", 0, gfx),
            ("palette", 4, palette),
            ("tilemap", 8, tilemap),
        ):
            physical_offset = pointer - ROM_BASE
            if not 0 <= physical_offset < len(base):
                raise ValueError("independent story pointer is outside ROM")
            content = lz77_decompress(base, physical_offset)
            digest = _sha256(content)
            key = (role, digest)
            resource = resources.setdefault(
                key,
                {
                    "resource_type": role,
                    "resource_sha256": digest,
                    "decompressed_size": len(content),
                    "content": content,
                    "physical_offsets": [],
                    "pointer_aliases": [],
                },
            )
            if resource["content"] != content:
                raise ValueError("independent story content hash collision")
            pointer_offset = descriptor + field_offset
            alias = {
                "layer_id": layer_id,
                "config_id": config_id,
                "descriptor_file_offset": descriptor,
                "table_pointer_offset": pointer_offset,
                "physical_offset": physical_offset,
                "source_pointer": pointer,
            }
            resource["physical_offsets"].append(physical_offset)
            resource["pointer_aliases"].append(alias)
            expected_by_pointer.setdefault(pointer, set()).add(pointer_offset)
            view[role] = content
        _validate_view(layer_id, view)
    actual_by_pointer = {pointer: set() for pointer in expected_by_pointer}
    for offset in range(0, len(base) - 3, 4):
        value = int.from_bytes(base[offset : offset + 4], "little")
        if value in actual_by_pointer:
            actual_by_pointer[value].add(offset)
    if any(
        actual_by_pointer[pointer] != expected
        for pointer, expected in expected_by_pointer.items()
    ):
        raise ValueError("independent story exact pointer denominator mismatch")
    for resource in resources.values():
        resource["physical_offsets"].sort()
        resource["pointer_aliases"].sort(
            key=lambda row: row["table_pointer_offset"]
        )
    if (
        len(resources) != 49
        or sum(len(row["physical_offsets"]) for row in resources.values()) != 72
        or sum(len(row["pointer_aliases"]) for row in resources.values()) != 72
    ):
        raise ValueError("independent story resource denominator mismatch")
    return resources


def _source_rows(
    root: Path,
    resources: dict[tuple[str, str], dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    manifest_path = root / SOURCE_MANIFEST
    manifest = _json(manifest_path)
    catalog = _json(root / SOURCE_PAYLOAD)
    promotion_files = {
        path.relative_to(root / SOURCE_ARTIFACT).as_posix(): _sha256_file(path)
        for path in (root / SOURCE_ARTIFACT).rglob("*")
        if path.is_file() and path != manifest_path
    }
    rows = catalog.get("resources")
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_id") != SOURCE_ARTIFACT.name
        or manifest.get("artifact_schema")
        != "story-visual-resource-source-export-v1"
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("payload_file") != SOURCE_PAYLOAD.name
        or manifest.get("payload_sha256")
        != promotion_files.get(SOURCE_PAYLOAD.name)
        or manifest.get("files") != promotion_files
        or catalog.get("schema") != "story-visual-resource-source-export-v1"
        or catalog.get("artifact_id") != SOURCE_ARTIFACT.name
        or catalog.get("source_catalog") != CATALOG_PATH.as_posix()
        or catalog.get("source_catalog_sha256") != CATALOG_SHA256
        or catalog.get("summary")
        != {
            "content_resource_count": 49,
            "physical_payload_count": 72,
            "logical_pointer_count": 72,
            "resource_type_counts": {
                "graphics": 24,
                "palette": 1,
                "tilemap": 24,
            },
        }
        or not isinstance(rows, list)
        or len(rows) != 49
    ):
        raise ValueError("independent story source manifest mismatch")
    expected_files = {"manifest.json", SOURCE_PAYLOAD.name}
    by_key = {}
    for row in rows:
        relative = row.get("source_file")
        if (
            not isinstance(relative, str)
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            raise ValueError("independent story source path is unsafe")
        key = (row.get("resource_type"), row.get("resource_sha256"))
        resource = resources.get(key)
        if resource is None or key in by_key:
            raise ValueError("independent story source identity mismatch")
        source_path = root / SOURCE_ARTIFACT / relative
        content = source_path.read_bytes()
        expected_files.add(relative)
        if (
            content != resource["content"]
            or row.get("decompressed_size") != len(content)
            or row.get("physical_offsets") != resource["physical_offsets"]
            or row.get("pointer_offsets")
            != [
                alias["table_pointer_offset"]
                for alias in resource["pointer_aliases"]
            ]
        ):
            raise ValueError("independent story source payload mismatch")
        by_key[key] = row
    actual_files = {
        path.relative_to(root / SOURCE_ARTIFACT).as_posix()
        for path in (root / SOURCE_ARTIFACT).rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        raise ValueError("independent story source file set mismatch")
    return by_key


def _expected_spec(
    root: Path,
    base: bytes,
    resources: dict[tuple[str, str], dict[str, Any]],
    source_rows: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    edits = []
    for key, resource in sorted(
        resources.items(),
        key=lambda item: (
            min(item[1]["physical_offsets"]),
            item[1]["resource_type"],
        ),
    ):
        source = SOURCE_ARTIFACT / source_rows[key]["source_file"]
        edits.append(
            {
                "id": (
                    f"{resource['resource_type']}-"
                    f"{resource['resource_sha256'][:12]}"
                ),
                "resource_type": resource["resource_type"],
                "resource_sha256": resource["resource_sha256"],
                "source_file": source.as_posix(),
                "expected": {
                    "decompressed_size": resource["decompressed_size"],
                    "physical_offsets": resource["physical_offsets"],
                    "pointer_offsets": [
                        alias["table_pointer_offset"]
                        for alias in resource["pointer_aliases"]
                    ],
                },
            }
        )
    return {
        "schema": "story-visual-resource-relocation-v1",
        "base_rom_sha256": _sha256(base),
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": CATALOG_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256_file(root / REGISTRY_PATH),
        "region": "story-visual-layers",
        "region_owner": "story_visual_resources",
        "edits": edits,
    }


def _rebuild(
    root: Path,
    artifact: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    base = (root / "rom/base.gba").read_bytes()
    resources = _resources(base)
    source_rows = _source_rows(root, resources)
    spec = _json(artifact / SPEC_NAME)
    if spec != _expected_spec(root, base, resources, source_rows):
        raise ValueError("independent story authoring spec mismatch")
    layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    regions = ImageResourceRegions.from_path(root / REGISTRY_PATH, layout)
    region = regions.require(
        "story-visual-layers",
        "story_visual_resources",
    )
    data = bytearray(layout.expanded_base())
    cursor = region.start
    resource_rows = []
    stored_payload_bytes = 0
    pointer_patch_count = 0
    for index, (key, resource) in enumerate(
        sorted(
            resources.items(),
            key=lambda item: (
                min(item[1]["physical_offsets"]),
                TYPE_ORDER[item[1]["resource_type"]],
            ),
        )
    ):
        edit = spec["edits"][index]
        content = (root / edit["source_file"]).read_bytes()
        if content != resource["content"]:
            raise ValueError("independent story replacement payload mismatch")
        encoded = encode_gba_lz77(content)
        cursor = (cursor + region.alignment - 1) & -region.alignment
        end = cursor + len(encoded)
        if end > region.end:
            raise ValueError("independent story allocation exceeds region")
        data[cursor:end] = encoded
        new_pointer = ROM_BASE + cursor
        aliases = resource["pointer_aliases"]
        pointer_offsets = [
            alias["table_pointer_offset"] for alias in aliases
        ]
        for alias in aliases:
            pointer_offset = alias["table_pointer_offset"]
            source_pointer = alias["source_pointer"]
            if int.from_bytes(
                data[pointer_offset : pointer_offset + 4],
                "little",
            ) != source_pointer:
                raise ValueError("independent story pointer precondition mismatch")
            data[pointer_offset : pointer_offset + 4] = new_pointer.to_bytes(
                4,
                "little",
            )
            pointer_patch_count += 1
        role = resource["resource_type"]
        resource_rows.append(
            {
                "id": f"story-visual-{role}-{index:03d}",
                "resource_type": role,
                "resource_sha256": resource["resource_sha256"],
                "replacement_sha256": _sha256(content),
                "decompressed_size": len(content),
                "encoded_size": len(encoded),
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
        "layer_count": 24,
        "content_resource_count": len(resource_rows),
        "physical_payload_count": 72,
        "logical_pointer_count": pointer_patch_count,
        "unexpected_pointer_count": 0,
        "allocation_count": len(resource_rows),
        "pointer_patch_count": pointer_patch_count,
        "allocation_start": region.start,
        "allocation_end": cursor,
        "region_end": region.end,
        "stored_payload_bytes": stored_payload_bytes,
        "allocation_span": cursor - region.start,
        "remaining_bytes": region.end - cursor,
        "applied_patch_count": len(resource_rows) + pointer_patch_count,
    }
    return summary, resource_rows, _sha256(bytes(data))


def _verify(root: Path, artifact: Path) -> dict[str, Any]:
    if _sha256_file(root / CATALOG_PATH) != CATALOG_SHA256:
        raise ValueError("story visual relocation current catalog hash mismatch")
    manifest_path = artifact / "manifest.json"
    payload_path = artifact / PAYLOAD_NAME
    spec_path = artifact / SPEC_NAME
    manifest = _json(manifest_path)
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
            "tools/verify_story_visual_resource_relocation_audit.py",
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
        raise ValueError("story visual relocation promotion manifest mismatch")
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
        raise ValueError("story visual relocation payload provenance mismatch")
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
            "region": "story-visual-layers",
            "owner": "story_visual_resources",
            "start": 0xB50000,
            "end": 0xB71000,
        }
        or payload.get("source_artifact")
        != {
            "path": SOURCE_ARTIFACT.as_posix(),
            "manifest_sha256": _sha256_file(root / SOURCE_MANIFEST),
            "payload_sha256": _sha256_file(root / SOURCE_PAYLOAD),
        }
    ):
        raise ValueError("story visual relocation layout/source mismatch")
    linked = (root / "rom/base.gba").read_bytes()[
        0x5A320C : 0x5A320C + 79 * 0x44
    ]
    if payload.get("linked_tile_assets") != {
        "table_offset": 0x5A320C,
        "entry_count": 79,
        "entry_size": 0x44,
        "table_sha256": _sha256(linked),
        "relationship": "config_id only; no linked descriptor is patched",
    }:
        raise ValueError("story visual linked tile-assets provenance mismatch")
    expected_implementation = {
        path: _sha256_file(root / path) for path in IMPLEMENTATION_PATHS
    }
    if payload.get("implementation") != expected_implementation:
        raise ValueError("story visual implementation hashes mismatch")
    summary, resources, output_sha256 = _rebuild(root, artifact)
    if (
        payload.get("summary") != summary
        or payload.get("resources") != resources
        or payload.get("output_rom_sha256") != output_sha256
    ):
        raise ValueError("story visual independent rebuild mismatch")
    return {
        "schema": "story-visual-resource-relocation-verification-v1",
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
            "schema": "story-visual-resource-relocation-verification-v1",
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
    report = verify_audit(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
