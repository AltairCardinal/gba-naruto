#!/usr/bin/env python3
"""Independently verify the full battle-effect relocation artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.image_resource_regions import ImageResourceRegions
from tools.rom_layout import RomLayout
from tools.verify_battle_effect_resource_writeback_audit import (
    CATALOG_PATH,
    CATALOG_SHA256,
    _decompress,
    _encode,
    _group_resources,
)


ARTIFACT_ID = "battle-effect-resource-relocation-v1"
PAYLOAD_SCHEMA = "battle-effect-resource-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
REGISTRY_PATH = Path("sequel/image-resource-regions.json")
IMPLEMENTATION_PATHS = (
    "tools/import_battle_effect_resource_relocations.py",
    "tools/import_battle_effect_resources.py",
    "tools/gba_image_export.py",
    "tools/extract_tileset.py",
    "tools/verify_battle_effect_resource_writeback_audit.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_battle_effect_resource_relocation_audit.py",
    "tools/verify_battle_effect_resource_relocation_audit.py",
)
EXPECTED_SCOPE = {
    "proved": (
        "All 34 battle-effect content resources, representing 35 physical "
        "LZ77 payloads and all 36 exact pair-table pointer fields, relocate "
        "into the registered battle-effects image region."
    ),
    "editable": (
        "Complete 4bpp graphics tiles and 32-byte palettes may change without "
        "original compressed-slot limits; catalog-approved aliases may split "
        "while every selected graphics/palette pair remains explicit."
    ),
    "not_proved": (
        "Different graphics geometry, OAM placement, affine parameters, "
        "animation timing, blend/window behavior, audio coupling or final "
        "runtime pixel equivalence."
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


def _exact_pointer_aliases(
    base: bytes,
    grouped: dict[tuple[str, str], dict[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    expected_by_pointer: dict[int, set[int]] = {}
    aliases_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for key, resource in grouped.items():
        aliases = []
        for alias in resource["logical_aliases"]:
            source_pointer = 0x08000000 + alias["physical_offset"]
            pointer_offset = alias["table_pointer_offset"]
            if (
                int.from_bytes(
                    base[pointer_offset : pointer_offset + 4],
                    "little",
                )
                != source_pointer
            ):
                raise ValueError(
                    "battle-effect independent pointer provenance mismatch"
                )
            aliases.append({**alias, "source_pointer": source_pointer})
            expected_by_pointer.setdefault(source_pointer, set()).add(
                pointer_offset
            )
        aliases_by_key[key] = sorted(
            aliases,
            key=lambda alias: alias["table_pointer_offset"],
        )
    actual_by_pointer = {pointer: set() for pointer in expected_by_pointer}
    for offset in range(0, len(base) - 3, 4):
        value = int.from_bytes(base[offset : offset + 4], "little")
        if value in actual_by_pointer:
            actual_by_pointer[value].add(offset)
    if any(
        actual_by_pointer[pointer] != expected
        for pointer, expected in expected_by_pointer.items()
    ):
        raise ValueError(
            "battle-effect independent exact pointer denominator mismatch"
        )
    if (
        len(expected_by_pointer) != 35
        or sum(len(offsets) for offsets in expected_by_pointer.values()) != 36
    ):
        raise ValueError(
            "battle-effect independent physical/reference count mismatch"
        )
    return aliases_by_key


def _expected_spec(
    root: Path,
    base: bytes,
    grouped: dict[tuple[str, str], dict[str, Any]],
    aliases_by_key: dict[tuple[str, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    edits = []
    for key, resource in sorted(
        grouped.items(),
        key=lambda item: (
            min(item[1]["physical_offsets"]),
            item[1]["resource_type"],
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
                        for alias in aliases_by_key[key]
                    ),
                },
            }
        )
    return {
        "schema": "battle-effect-resource-relocation-v1",
        "base_rom_sha256": _sha256(base),
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": _sha256_file(root / CATALOG_PATH),
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256_file(root / REGISTRY_PATH),
        "region": "battle-effects",
        "region_owner": "battle_effect_resources",
        "edits": edits,
    }


def _rebuild(
    root: Path,
    artifact: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    base = (root / "rom/base.gba").read_bytes()
    catalog = _json(root / CATALOG_PATH)
    grouped = _group_resources(base, catalog)
    aliases_by_key = _exact_pointer_aliases(base, grouped)
    spec = _json(artifact / SPEC_NAME)
    if spec != _expected_spec(root, base, grouped, aliases_by_key):
        raise ValueError("battle-effect relocation authoring spec mismatch")
    layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    regions = ImageResourceRegions.from_path(root / REGISTRY_PATH, layout)
    region = regions.require("battle-effects", "battle_effect_resources")
    data = bytearray(layout.expanded_base())

    edits_by_key = {
        (edit["resource_type"], edit["resource_sha256"]): edit
        for edit in spec["edits"]
    }
    ordered = sorted(
        grouped.items(),
        key=lambda item: (
            min(item[1]["physical_offsets"]),
            item[1]["resource_type"],
        ),
    )
    if len(edits_by_key) != 34 or len(ordered) != 34:
        raise ValueError("battle-effect independent content denominator mismatch")

    resources = []
    stored_payload_bytes = 0
    pointer_patch_count = 0
    cursor = region.start
    for index, (key, resource) in enumerate(ordered):
        edit = edits_by_key.get(key)
        if edit is None:
            raise ValueError("battle-effect independent edit identity mismatch")
        content = (root / edit["source_file"]).read_bytes()
        if (
            len(content) != resource["decompressed_size"]
            or _sha256(content) != resource["resource_sha256"]
            or content != _decompress(base, resource["physical_offsets"][0])
        ):
            raise ValueError("battle-effect independent source payload mismatch")
        if (
            resource["resource_type"] == "graphics"
            and (not content or len(content) % 32)
        ):
            raise ValueError("battle-effect independent graphics format mismatch")
        if resource["resource_type"] == "palette" and len(content) != 32:
            raise ValueError("battle-effect independent palette format mismatch")

        encoded = _encode(content)
        cursor = (cursor + 3) & ~3
        end = cursor + len(encoded)
        if end > region.end:
            raise ValueError("battle-effect independent allocation exceeds region")
        data[cursor:end] = encoded
        new_pointer = 0x08000000 + cursor
        aliases = aliases_by_key[key]
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
                    "battle-effect independent pointer before-byte mismatch"
                )
            data[pointer_offset : pointer_offset + 4] = new_pointer.to_bytes(
                4,
                "little",
            )
            pointer_patch_count += 1
        resource_type = resource["resource_type"]
        resources.append(
            {
                "id": f"battle-effect-{resource_type}-{index:03d}",
                "resource_type": resource_type,
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
        "group_count": 18,
        "content_resource_count": len(resources),
        "physical_payload_count": 35,
        "logical_pointer_count": pointer_patch_count,
        "unexpected_pointer_count": 0,
        "allocation_count": len(resources),
        "pointer_patch_count": pointer_patch_count,
        "allocation_start": region.start,
        "allocation_end": cursor,
        "region_end": region.end,
        "stored_payload_bytes": stored_payload_bytes,
        "allocation_span": cursor - region.start,
        "remaining_bytes": region.end - cursor,
        "applied_patch_count": len(resources) + pointer_patch_count,
    }
    return summary, resources, _sha256(bytes(data))


def _verify(root: Path, artifact: Path) -> dict[str, Any]:
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
            "tools/verify_battle_effect_resource_relocation_audit.py",
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
        raise ValueError("battle-effect relocation promotion manifest mismatch")
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
        raise ValueError("battle-effect relocation payload provenance mismatch")
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
            "region": "battle-effects",
            "owner": "battle_effect_resources",
            "start": 0xB40000,
            "end": 0xB50000,
        }
    ):
        raise ValueError("battle-effect relocation layout/region mismatch")
    expected_implementation = {
        path: _sha256_file(root / path) for path in IMPLEMENTATION_PATHS
    }
    if payload.get("implementation") != expected_implementation:
        raise ValueError("battle-effect relocation implementation hashes mismatch")
    summary, resources, output_sha256 = _rebuild(root, artifact)
    if (
        payload.get("summary") != summary
        or payload.get("resources") != resources
        or payload.get("output_rom_sha256") != output_sha256
    ):
        raise ValueError("battle-effect relocation independent rebuild mismatch")
    return {
        "schema": "battle-effect-resource-relocation-verification-v1",
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
            "schema": "battle-effect-resource-relocation-verification-v1",
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
