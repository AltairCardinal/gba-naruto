#!/usr/bin/env python3
"""Export the full tile-assets variable-length relocation audit."""

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
from import_tile_asset_resources import (
    CATALOG_PATH,
    catalog_tile_asset_resources,
    resolve_tile_asset_resource_patches,
)
from patch_safety import PatchSafetyGate
from rom_layout import RomLayout


ARTIFACT_ID = "tile-asset-resource-relocation-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
PAYLOAD_SCHEMA = "tile-asset-resource-relocation-audit-v1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _spec(
    base: bytes,
    catalog_sha256: str,
    resources: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": "tile-asset-resource-import-v1",
        "description": (
            "Capacity/fidelity audit: relocate all 323 tile-assets payloads "
            "and all 709 exact descriptor pointer aliases without editing."
        ),
        "base_rom_sha256": _sha256(base),
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": catalog_sha256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "edits": [
            {
                "id": (
                    f"{resource['resource_type']}-"
                    f"{resource['source_offset']:06x}-relocation"
                ),
                "resource_type": resource["resource_type"],
                "source_pointer": resource["source_pointer"],
                "source_sha256": resource["source_sha256"],
                "expected_pointer_offsets": [
                    alias["pointer_offset"]
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
    catalog_path = root / CATALOG_PATH
    base = base_path.read_bytes()
    layout = RomLayout.from_path(layout_path, base)
    catalog_bytes = catalog_path.read_bytes()
    catalog = json.loads(catalog_bytes)
    resources = catalog_tile_asset_resources(root, base)

    spec_path = output / SPEC_NAME
    spec = _spec(base, _sha256(catalog_bytes), resources)
    spec_path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    patches = resolve_tile_asset_resource_patches(
        root,
        spec_path,
        rom=base,
        layout=layout,
    )
    data = bytearray(layout.expanded_base())
    gate = PatchSafetyGate(base, layout=layout)
    applied = [apply_patch(data, patch, gate=gate) for patch in patches]
    allocations = [
        patch
        for patch in patches
        if patch.get("asset_type") == "tile_asset_resource"
    ]
    redirects = [
        patch
        for patch in patches
        if patch.get("asset_type") == "tile_asset_resource_pointer"
    ]
    if len(allocations) != 323 or len(redirects) != 709:
        raise ValueError("tile-assets relocation patch denominator mismatch")
    if (
        sum(row["patch_class"] == "allocation" for row in applied) != 323
        or sum(row["patch_class"] == "game_effective" for row in applied) != 709
    ):
        raise ValueError("tile-assets relocation safety classes mismatch")

    partition = next(
        row for row in layout.partitions if row.id == "sequel-image-assets"
    )
    allocation_end = max(
        patch["offset"] + len(bytes.fromhex(patch["after_hex"]))
        for patch in allocations
    )
    allocations_by_pointer = {
        patch["source_pointer"]: patch for patch in allocations
    }
    resource_rows = []
    for pointer, resource in resources.items():
        allocation = allocations_by_pointer[resource["source_pointer"]]
        encoded = bytes.fromhex(allocation["after_hex"])
        resource_rows.append(
            {
                "resource_type": resource["resource_type"],
                "source_pointer": resource["source_pointer"],
                "source_offset": resource["source_offset"],
                "source_sha256": resource["source_sha256"],
                "source_size": resource["source_size"],
                "source_stored_size": len(resource["source_stored"]),
                "storage_kind": resource["storage_kind"],
                "bits_per_pixel": resource["bits_per_pixel"],
                "allocation_offset": allocation["offset"],
                "relocated_stored_size": len(encoded),
                "relocated_stored_sha256": _sha256(encoded),
                "new_pointer": allocation["new_pointer"],
                "logical_pointer_count": len(resource["logical_aliases"]),
                "pointer_offsets": [
                    alias["pointer_offset"]
                    for alias in resource["logical_aliases"]
                ],
                "unexpected_pointer_offsets": (
                    resource["unexpected_pointer_offsets"]
                ),
            }
        )
    resource_rows.sort(key=lambda row: row["source_offset"])
    type_counts = {
        kind: sum(row["resource_type"] == kind for row in resource_rows)
        for kind in ("graphics", "tilemap", "palette")
    }
    summary = {
        "descriptor_count": int(catalog["descriptor_count"]),
        "complete_layer_count": int(catalog["complete_layer_count"]),
        "partial_layer_count": int(catalog["partial_layer_count"]),
        "resource_count": len(resource_rows),
        "resource_type_counts": type_counts,
        "logical_pointer_count": len(redirects),
        "unexpected_pointer_count": sum(
            len(row["unexpected_pointer_offsets"]) for row in resource_rows
        ),
        "allocation_start": partition.start,
        "allocation_end": allocation_end,
        "allocated_span_bytes": allocation_end - partition.start,
        "relocated_stored_bytes": sum(
            row["relocated_stored_size"] for row in resource_rows
        ),
        "source_stored_bytes": sum(
            row["source_stored_size"] for row in resource_rows
        ),
        "source_content_bytes": sum(
            row["source_size"] for row in resource_rows
        ),
        "partition_end": partition.end,
        "remaining_bytes": partition.end - allocation_end,
    }
    expected = {
        "descriptor_count": 79,
        "complete_layer_count": 236,
        "partial_layer_count": 1,
        "resource_count": 323,
        "resource_type_counts": {
            "graphics": 107,
            "tilemap": 108,
            "palette": 108,
        },
        "logical_pointer_count": 709,
        "unexpected_pointer_count": 0,
    }
    for key, value in expected.items():
        if summary[key] != value:
            raise ValueError(
                f"tile-assets relocation {key} mismatch: "
                f"expected {value!r} got {summary[key]!r}"
            )

    implementation_paths = (
        "tools/import_tile_asset_resources.py",
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
            "partition": partition.id,
            "owner": partition.owner,
        },
        "catalog": {
            "path": CATALOG_PATH.as_posix(),
            "sha256": _sha256(catalog_bytes),
            "table_sha256": catalog["source_table"]["sha256"],
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
        "scope": {
            "proved": (
                "All 323 graphics/tilemap/palette payloads and all 709 exact "
                "descriptor pointers relocate into the registered 4 MiB image "
                "partition with no unknown aligned exact references."
            ),
            "editable": (
                "Raw 4bpp/8bpp graphics, u16 tilemaps and BGR555 palettes may "
                "change size where their layer geometry remains valid."
            ),
            "not_proved": (
                "Modified-resource runtime pixel equivalence, final window/"
                "blend/timing composition, or the missing graphics/palette "
                "producers for descriptor 0 partial D."
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
                "tools/verify_tile_asset_resource_relocation_audit.py",
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
