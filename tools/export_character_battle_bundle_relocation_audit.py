#!/usr/bin/env python3
"""Prove that all 250 character visual bundles fit the expansion partition."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for candidate in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from build_mod import apply_patch
from import_character_battle_bundles import (
    CATALOG_PATH,
    resolve_character_battle_bundle_patches,
)
from patch_safety import PatchSafetyGate
from rom_layout import RomLayout

ARTIFACT_ID = "character-battle-bundle-relocation-v1"
PAYLOAD_NAME = "relocation-audit.json"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _authoring_spec(
    root: Path,
    catalog: dict[str, Any],
    catalog_sha256: str,
    base_sha256: str,
) -> dict[str, Any]:
    return {
        "schema": "character-battle-bundle-import-v1",
        "description": (
            "Capacity/fidelity audit: relocate every existing resource while "
            "preserving graphics, palette, frame records, timelines and aliases."
        ),
        "base_rom_sha256": base_sha256,
        "catalog": str(CATALOG_PATH),
        "catalog_sha256": catalog_sha256,
        "partition": "character-battle-visual-bundles",
        "owner": "character_battle_visuals",
        "edits": [
            {
                "id": f"resource-{resource['resource_id']:03d}-relocation",
                "resource_id": resource["resource_id"],
                "expected_descriptor": resource["descriptor"],
                "expected_slot_rows": resource["slot_rows"],
                "graphics_file": str(
                    CATALOG_PATH.parent / resource["graphics"]["file"]
                ),
                "graphics_sha256": resource["graphics"]["sha256"],
            }
            for resource in catalog["resources"]
        ],
    }


def export_audit(root: Path, output: Path) -> dict[str, Any]:
    base_path = root / "rom/base.gba"
    layout_path = root / "sequel/rom-layout.json"
    catalog_path = root / CATALOG_PATH
    base = base_path.read_bytes()
    layout = RomLayout.from_path(layout_path, base)
    catalog_bytes = catalog_path.read_bytes()
    catalog = json.loads(catalog_bytes)
    base_sha256 = _sha256(base)
    catalog_sha256 = _sha256(catalog_bytes)

    output.mkdir(parents=True, exist_ok=True)
    spec_path = output / "full-relocation-spec.json"
    spec = _authoring_spec(root, catalog, catalog_sha256, base_sha256)
    spec_path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    patches = resolve_character_battle_bundle_patches(
        root,
        spec_path,
        rom=base,
        layout=layout,
    )
    data = bytearray(layout.expanded_base())
    gate = PatchSafetyGate(base, layout=layout)
    applied = [apply_patch(data, patch, gate=gate) for patch in patches]

    bundles = [
        patch
        for patch in patches
        if patch.get("asset_type") == "character_battle_bundle"
    ]
    descriptors = [
        patch
        for patch in patches
        if patch.get("asset_type") == "character_battle_bundle_descriptor"
    ]
    if len(bundles) != 250 or len(descriptors) != 342:
        raise ValueError("full relocation patch denominator mismatch")
    descriptor_rows = [patch["slot_row"] for patch in descriptors]
    if len(descriptor_rows) != len(set(descriptor_rows)):
        raise ValueError("full relocation descriptor rows overlap")
    by_id = {result["id"]: result for result in applied}
    for patch in bundles:
        if by_id[patch["id"]]["patch_class"] != "allocation":
            raise ValueError("bundle payload did not pass allocation gate")
    for patch in descriptors:
        if by_id[patch["id"]]["patch_class"] != "game_effective":
            raise ValueError("descriptor redirect did not pass base gate")

    allocation_start = min(patch["offset"] for patch in bundles)
    allocation_end = max(
        patch["offset"] + len(bytes.fromhex(patch["after_hex"]))
        for patch in bundles
    )
    partition = next(
        item
        for item in layout.partitions
        if item.id == "character-battle-visual-bundles"
    )
    resources = []
    for patch in bundles:
        resources.append(
            {
                "resource_id": patch["resource_id"],
                "slot_rows": patch["affected_slot_rows"],
                "offset": patch["offset"],
                "bundle_size": patch["bundle_size"],
                "bundle_sha256": _sha256(bytes.fromhex(patch["after_hex"])),
                "new_pointers": patch["new_pointers"],
                "graphics_size": patch["graphics_size"],
                "tile_count": patch["tile_count"],
                "frame_count": patch["frame_count"],
                "component_count": patch["component_count"],
                "animation_count": patch["animation_count"],
                "keyframe_count": patch["keyframe_count"],
                "target_pointer_count": patch["target_pointer_count"],
                "reference_count": patch["reference_count"],
                "compressed_payload_coincidences": patch[
                    "compressed_payload_coincidences"
                ],
                "unexpected_external_references": patch[
                    "unexpected_external_references"
                ],
            }
        )
    resources.sort(key=lambda item: item["resource_id"])
    if [item["resource_id"] for item in resources] != list(range(250)):
        raise ValueError("full relocation resource identities are not contiguous")

    summary = {
        "resource_count": len(resources),
        "descriptor_slot_count": len(descriptors),
        "allocation_patch_count": len(bundles),
        "descriptor_patch_count": len(descriptors),
        "allocation_start": allocation_start,
        "allocation_end": allocation_end,
        "allocated_bytes": allocation_end - allocation_start,
        "partition_end": partition.end,
        "remaining_bytes": partition.end - allocation_end,
        "frame_count": sum(item["frame_count"] for item in resources),
        "component_count": sum(item["component_count"] for item in resources),
        "animation_count": sum(item["animation_count"] for item in resources),
        "keyframe_count": sum(item["keyframe_count"] for item in resources),
        "tile_count": sum(item["tile_count"] for item in resources),
        "reference_target_count": sum(
            item["target_pointer_count"] for item in resources
        ),
        "reference_count": sum(item["reference_count"] for item in resources),
        "compressed_payload_coincidence_count": sum(
            len(item["compressed_payload_coincidences"]) for item in resources
        ),
        "unexpected_external_reference_count": sum(
            len(item["unexpected_external_references"]) for item in resources
        ),
    }
    expected_summary = {
        "resource_count": 250,
        "descriptor_slot_count": 342,
        "frame_count": 2004,
        "component_count": 2190,
        "animation_count": 784,
        "keyframe_count": 3187,
        "tile_count": 60430,
        "compressed_payload_coincidence_count": 1,
        "unexpected_external_reference_count": 0,
    }
    for key, expected in expected_summary.items():
        if summary[key] != expected:
            raise ValueError(
                f"full relocation summary {key} mismatch: "
                f"expected {expected} got {summary[key]}"
            )

    implementation_paths = (
        "tools/import_character_battle_bundles.py",
        "tools/rom_layout.py",
        "tools/patch_safety.py",
        "tools/build_mod.py",
    )
    payload: dict[str, Any] = {
        "schema": "character-battle-bundle-relocation-audit-v1",
        "base_rom": {
            "path": "rom/base.gba",
            "size": len(base),
            "sha256": base_sha256,
        },
        "layout": {
            "path": "sequel/rom-layout.json",
            "sha256": _sha256_file(layout_path),
            "target_rom_size": layout.target_rom_size,
            "partition": partition.id,
            "owner": partition.owner,
        },
        "catalog": {
            "path": str(CATALOG_PATH),
            "sha256": catalog_sha256,
        },
        "authoring_spec": {
            "file": "full-relocation-spec.json",
            "sha256": _sha256_file(spec_path),
        },
        "summary": summary,
        "output_rom_sha256": _sha256(bytes(data)),
        "implementation": {
            path: _sha256_file(root / path)
            for path in implementation_paths
        },
        "resources": resources,
        "scope": {
            "preserved": (
                "All 250 source graphics, copied 32-byte palettes, frame "
                "records including the single FBFF trailer, timelines and "
                "342 logical descriptor aliases."
            ),
            "proved": (
                "Every resource can be relocated together into the declared "
                "2 MiB partition with rewritten internal and descriptor "
                "pointers. The sole additional aligned exact value is recorded "
                "as data inside a separately pointed strict LZ77 payload; no "
                "unknown aligned exact-pointer references remain."
            ),
            "not_proved": (
                "Modified-resource runtime pixel equivalence, arbitrary flash "
                "cartridge behavior, or references encoded in a non-pointer form."
            ),
        },
    }
    payload_path = output / PAYLOAD_NAME
    payload_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    files = {
        PAYLOAD_NAME: _sha256_file(payload_path),
        spec_path.name: _sha256_file(spec_path),
    }
    promotion = {
        "schema": "git-artifact-promotion-v1",
        "artifact_id": ARTIFACT_ID,
        "artifact_schema": payload["schema"],
        "artifact_status": "accepted",
        "payload_file": PAYLOAD_NAME,
        "payload_sha256": files[PAYLOAD_NAME],
        "files": files,
        "scope": payload["scope"],
        "summary": payload["summary"],
        "verifier": {
            "command": [
                "python3",
                "tools/verify_character_battle_bundle_relocation_audit.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{ARTIFACT_ID}",
            ],
            "exit_code": 0,
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(promotion, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export full character bundle relocation capacity audit."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = export_audit(args.root, args.output)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
