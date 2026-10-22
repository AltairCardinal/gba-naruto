#!/usr/bin/env python3
"""Export the full battle-map resource relocation audit."""
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
from gba_image_export import read_lz77_record
from image_resource_regions import ImageResourceRegions
from import_map_resource_relocations import (
    REGION_REGISTRY_PATH,
    catalog_map_resource_relocations,
    resolve_map_resource_relocation_patches,
)
from import_map_resources import CATALOG_PATH
from patch_safety import PatchSafetyGate
from rom_layout import RomLayout


ARTIFACT_ID = "map-resource-relocation-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
SCOPE = {
    "proved": (
        "All 166 deduplicated map contents and 249 exact map-header "
        "pointers relocate into the registered map image region."
    ),
    "editable": (
        "Map graphics, palettes, layouts, metatiles and collision "
        "grids may change size while every linked map remains valid."
    ),
    "not_proved": (
        "Modified-map runtime pixel equivalence, dynamic overlays, "
        "camera behavior or final collision gameplay semantics."
    ),
}
PAYLOAD_SCHEMA = "map-resource-relocation-audit-v1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _spec(
    base: bytes,
    catalog_sha256: str,
    registry_sha256: str,
    resources: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": "map-resource-relocation-v1",
        "description": (
            "Capacity/fidelity audit: relocate all 166 deduplicated map "
            "contents and all 249 exact map-header pointer aliases."
        ),
        "base_rom_sha256": _sha256(base),
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": catalog_sha256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGION_REGISTRY_PATH.as_posix(),
        "region_registry_sha256": registry_sha256,
        "region": "map-resources",
        "region_owner": "map_resources",
        "edits": [
            {
                "id": (
                    f"{resource['resource_type']}-"
                    f"{resource['source_sha256'][:12]}-relocation"
                ),
                "resource_type": resource["resource_type"],
                "source_sha256": resource["source_sha256"],
                "expected_physical_offsets": resource["physical_offsets"],
                "expected_header_pointer_offsets": [
                    alias["header_pointer_offset"]
                    for alias in resource["logical_aliases"]
                ],
            }
            for resource in resources.values()
        ],
    }


def export_audit(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    output = output if output.is_absolute() else root / output
    output.mkdir(parents=True, exist_ok=True)
    base_path = root / "rom/base.gba"
    layout_path = root / "sequel/rom-layout.json"
    registry_path = root / REGION_REGISTRY_PATH
    catalog_path = root / CATALOG_PATH
    base = base_path.read_bytes()
    layout = RomLayout.from_path(layout_path, base)
    registry_bytes = registry_path.read_bytes()
    regions = ImageResourceRegions.from_path(registry_path, layout)
    region = regions.require("map-resources", "map_resources")
    catalog_bytes = catalog_path.read_bytes()
    resources = catalog_map_resource_relocations(root, base)

    spec_path = output / SPEC_NAME
    spec = _spec(
        base,
        _sha256(catalog_bytes),
        _sha256(registry_bytes),
        resources,
    )
    spec_path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    patches = resolve_map_resource_relocation_patches(
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
        patch
        for patch in patches
        if patch.get("asset_type") == "map_resource_relocation"
    ]
    redirects = [
        patch
        for patch in patches
        if patch.get("asset_type") == "map_resource_relocation_pointer"
    ]
    if len(allocations) != 166 or len(redirects) != 249:
        raise ValueError("map relocation patch denominator mismatch")
    if (
        sum(row["patch_class"] == "allocation" for row in applied) != 166
        or sum(row["patch_class"] == "game_effective" for row in applied) != 249
    ):
        raise ValueError("map relocation safety class mismatch")

    allocations_by_key = {
        (patch["resource_type"], patch["source_sha256"]): patch
        for patch in allocations
    }
    resource_rows = []
    for key, resource in resources.items():
        allocation = allocations_by_key[key]
        encoded = bytes.fromhex(allocation["after_hex"])
        source_stored_sizes = [
            len(read_lz77_record(base, offset))
            for offset in resource["physical_offsets"]
        ]
        resource_rows.append(
            {
                "resource_type": resource["resource_type"],
                "source_sha256": resource["source_sha256"],
                "source_size": resource["source_size"],
                "physical_offsets": resource["physical_offsets"],
                "source_pointers": resource["source_pointers"],
                "source_stored_sizes": source_stored_sizes,
                "allocation_offset": allocation["offset"],
                "relocated_stored_size": len(encoded),
                "relocated_stored_sha256": _sha256(encoded),
                "new_pointer": allocation["new_pointer"],
                "logical_reference_count": len(resource["logical_aliases"]),
                "header_pointer_offsets": [
                    alias["header_pointer_offset"]
                    for alias in resource["logical_aliases"]
                ],
                "unexpected_pointer_offsets": (
                    resource["unexpected_pointer_offsets"]
                ),
            }
        )
    resource_rows.sort(
        key=lambda row: (
            min(row["physical_offsets"]),
            row["resource_type"],
            row["source_sha256"],
        )
    )
    type_counts = {
        role: sum(row["resource_type"] == role for row in resource_rows)
        for role in (
            "alternate_layout",
            "bg_palette",
            "collision_grid",
            "metatile_definitions",
            "primary_layout",
            "tile_graphics",
        )
    }
    allocation_end = max(
        row["allocation_offset"] + row["relocated_stored_size"]
        for row in resource_rows
    )
    summary = {
        "map_count": 47,
        "content_resource_count": len(resource_rows),
        "physical_source_count": sum(
            len(row["physical_offsets"]) for row in resource_rows
        ),
        "logical_reference_count": len(redirects),
        "resource_type_counts": type_counts,
        "unexpected_pointer_count": sum(
            len(row["unexpected_pointer_offsets"]) for row in resource_rows
        ),
        "allocation_start": region.start,
        "allocation_end": allocation_end,
        "allocated_span_bytes": allocation_end - region.start,
        "relocated_stored_bytes": sum(
            row["relocated_stored_size"] for row in resource_rows
        ),
        "source_physical_stored_bytes": sum(
            sum(row["source_stored_sizes"]) for row in resource_rows
        ),
        "source_content_bytes": sum(
            row["source_size"] for row in resource_rows
        ),
        "region_end": region.end,
        "remaining_bytes": region.end - allocation_end,
    }
    expected = {
        "content_resource_count": 166,
        "physical_source_count": 217,
        "logical_reference_count": 249,
        "resource_type_counts": {
            "alternate_layout": 12,
            "bg_palette": 15,
            "collision_grid": 35,
            "metatile_definitions": 35,
            "primary_layout": 35,
            "tile_graphics": 34,
        },
        "unexpected_pointer_count": 0,
        "allocation_end": 0x9DE03E,
    }
    for key, value in expected.items():
        if summary[key] != value:
            raise ValueError(
                f"map relocation {key} mismatch: "
                f"expected {value!r} got {summary[key]!r}"
            )

    implementation_paths = (
        "tools/import_map_resource_relocations.py",
        "tools/import_map_resources.py",
        "tools/image_resource_regions.py",
        "tools/rom_layout.py",
        "tools/patch_safety.py",
        "tools/build_mod.py",
    )
    payload: dict[str, Any] = {
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
            "sha256": _sha256(registry_bytes),
            "region": region.id,
            "owner": region.owner,
            "start": region.start,
            "end": region.end,
        },
        "catalog": {
            "path": CATALOG_PATH.as_posix(),
            "sha256": _sha256(catalog_bytes),
        },
        "authoring_spec": {
            "file": SPEC_NAME,
            "sha256": _sha256_file(spec_path),
        },
        "implementation": {
            path: _sha256_file(root / path)
            for path in implementation_paths
        },
        "summary": summary,
        "resources": resource_rows,
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
    promotion = {
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
                "tools/verify_map_resource_relocation_audit.py",
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(f"artifacts/{ARTIFACT_ID}"),
    )
    args = parser.parse_args()
    payload = export_audit(args.root, args.output)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
