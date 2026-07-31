#!/usr/bin/env python3
"""Export the full world-map background relocation proof artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

from tools.build_mod import apply_patch
from tools.image_resource_regions import ImageResourceRegions
from tools.import_world_map_background_relocations import (
    CATALOG_PATH,
    CATALOG_SHA256,
    REGION_REGISTRY_PATH,
    ROM_SHA256,
    catalog_world_map_background_relocation_payloads,
    resolve_world_map_background_relocation_patches,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


ARTIFACT_ID = "world-map-background-relocation-v1"
PAYLOAD_SCHEMA = "world-map-background-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
SCOPE = {
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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _spec(root: Path, base: bytes) -> dict[str, Any]:
    resources = catalog_world_map_background_relocation_payloads(root, base)
    order = {"graphics": 0, "tilemap": 1, "palette": 2}
    edits = []
    for resource in sorted(
        resources.values(),
        key=lambda row: (
            order[row["resource_type"]],
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
    registry_path = root / REGION_REGISTRY_PATH
    return {
        "schema": "world-map-background-relocation-v1",
        "base_rom_sha256": _sha256(base),
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": _sha256_file(root / CATALOG_PATH),
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGION_REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256_file(registry_path),
        "region": "world-map-backgrounds",
        "region_owner": "world_map_background_resources",
        "edits": edits,
    }


def export_audit(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    output = Path(output)
    if not output.is_absolute():
        output = root / output
    output.mkdir(parents=True, exist_ok=True)
    base = (root / "rom/base.gba").read_bytes()
    if _sha256(base) != ROM_SHA256:
        raise ValueError("world-map relocation audit base ROM mismatch")
    catalog_path = root / CATALOG_PATH
    if _sha256_file(catalog_path) != CATALOG_SHA256:
        raise ValueError("world-map relocation audit catalog mismatch")
    layout_path = root / "sequel/rom-layout.json"
    layout = RomLayout.from_path(layout_path, base)
    registry_path = root / REGION_REGISTRY_PATH
    regions = ImageResourceRegions.from_path(registry_path, layout)
    region = regions.require(
        "world-map-backgrounds",
        "world_map_background_resources",
    )

    spec = _spec(root, base)
    spec_path = output / SPEC_NAME
    spec_path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    patches = resolve_world_map_background_relocation_patches(
        root,
        spec_path,
        rom=base,
        layout=layout,
        regions=regions,
    )
    data = bytearray(layout.expanded_base())
    gate = PatchSafetyGate(base, layout=layout, image_regions=regions)
    applied = [apply_patch(data, patch, gate=gate) for patch in patches]
    allocations = [
        patch for patch in patches if isinstance(patch.get("allocation"), dict)
    ]
    redirects = [
        patch
        for patch in patches
        if patch.get("asset_type") == "world_map_background_pointer"
    ]
    if len(allocations) != 7 or len(redirects) != 9:
        raise ValueError("world-map relocation audit patch denominator mismatch")
    allocation_end = max(
        patch["offset"] + len(bytes.fromhex(patch["after_hex"]))
        for patch in allocations
    )
    summary = {
        "page_count": 3,
        "content_resource_count": 7,
        "physical_payload_count": 9,
        "logical_pointer_count": 9,
        "unexpected_pointer_count": 0,
        "allocation_count": len(allocations),
        "pointer_patch_count": len(redirects),
        "allocation_start": region.start,
        "allocation_end": allocation_end,
        "region_end": region.end,
        "stored_payload_bytes": sum(
            len(bytes.fromhex(patch["after_hex"])) for patch in allocations
        ),
        "allocation_span": allocation_end - region.start,
        "remaining_bytes": region.end - allocation_end,
        "applied_patch_count": len(applied),
    }
    resources = [
        {
            key: patch[key]
            for key in (
                "id",
                "resource_type",
                "resource_sha256",
                "replacement_sha256",
                "decompressed_size",
                "encoded_size",
                "storage_kind",
                "new_pointer",
                "offset",
                "physical_offsets",
                "all_pointer_offsets",
                "target_pointer_offsets",
                "logical_aliases",
                "source_file",
            )
        }
        for patch in allocations
    ]
    payload = {
        "schema": PAYLOAD_SCHEMA,
        "base_rom": {
            "path": "rom/base.gba",
            "size": len(base),
            "sha256": _sha256(base),
        },
        "layout": {
            "path": "sequel/rom-layout.json",
            "sha256": _sha256_file(layout_path),
            "target_rom_size": layout.target_rom_size,
            "partition": regions.parent.id,
            "owner": regions.parent.owner,
        },
        "region_registry": {
            "path": REGION_REGISTRY_PATH.as_posix(),
            "sha256": _sha256_file(registry_path),
            "region": region.id,
            "owner": region.owner,
            "start": region.start,
            "end": region.end,
        },
        "catalog": {
            "path": CATALOG_PATH.as_posix(),
            "sha256": _sha256_file(catalog_path),
        },
        "authoring_spec": {
            "file": SPEC_NAME,
            "sha256": _sha256_file(spec_path),
        },
        "implementation": {
            path: _sha256_file(root / path)
            for path in IMPLEMENTATION_PATHS
        },
        "summary": summary,
        "resources": resources,
        "output_rom_sha256": _sha256(bytes(data)),
        "scope": SCOPE,
    }
    payload_path = output / PAYLOAD_NAME
    payload_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    files = {
        PAYLOAD_NAME: _sha256_file(payload_path),
        SPEC_NAME: _sha256_file(spec_path),
    }
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_id": ARTIFACT_ID,
        "artifact_schema": PAYLOAD_SCHEMA,
        "artifact_status": "accepted",
        "payload_file": PAYLOAD_NAME,
        "payload_sha256": files[PAYLOAD_NAME],
        "files": files,
        "scope": payload["scope"],
        "summary": summary,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_world_map_background_relocation_audit.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{ARTIFACT_ID}",
            ],
            "exit_code": 0,
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts") / ARTIFACT_ID,
    )
    args = parser.parse_args()
    payload = export_audit(args.root, args.output)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
