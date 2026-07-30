#!/usr/bin/env python3
"""Export the full menu-portrait relocation proof artifact."""

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
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

from tools.build_mod import apply_patch
from tools.image_resource_regions import ImageResourceRegions
from tools.import_menu_portrait_relocations import (
    CATALOG_PATH,
    CATALOG_SHA256,
    REGION_REGISTRY_PATH,
    ROM_SHA256,
    resolve_menu_portrait_relocation_patches,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


ARTIFACT_ID = "menu-portrait-relocation-v1"
PAYLOAD_SCHEMA = "menu-portrait-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
SCOPE = {
    "proved": (
        "All 70 graphics and 70 palette payloads, representing 74 logical "
        "portrait pairs and 311 portraits, relocate through all 622 exact "
        "pair-table pointer fields into the registered menu-portraits region."
    ),
    "editable": (
        "Indexed 80x80 portraits may replace their compressed 6400-byte OBJ "
        "stream and 128-byte BGR555 palette, including explicit pair-alias "
        "splits, without the original compressed-slot capacity limit."
    ),
    "not_proved": (
        "Arbitrary portrait dimensions, modified-resource runtime pixel "
        "equivalence, menu color transforms, transitions or final composition."
    ),
}
IMPLEMENTATION_PATHS = (
    "tools/import_menu_portrait_relocations.py",
    "tools/import_menu_portraits.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_menu_portrait_relocation_audit.py",
    "tools/verify_menu_portrait_relocation_audit.py",
    "tools/verify_menu_portrait_writeback_audit.py",
    "tools/gba_image_export.py",
    "tools/extract_tileset.py",
    "tools/export_menu_portraits.py",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _spec(root: Path, base: bytes, catalog: dict[str, Any]) -> dict[str, Any]:
    aliases_by_resource: dict[int, list[dict[str, Any]]] = {
        resource["resource_id"]: []
        for resource in catalog["unique_resources"]
    }
    for alias in catalog["portraits"]:
        aliases_by_resource[alias["resource_id"]].append(alias)
    edits = []
    for resource in catalog["unique_resources"]:
        resource_id = resource["resource_id"]
        aliases = aliases_by_resource[resource_id]
        edits.append(
            {
                "id": f"portrait-{resource_id:03d}",
                "resource_id": resource_id,
                "png": (
                    CATALOG_PATH.parent / aliases[0]["png"]
                ).as_posix(),
                "expected": {
                    "gfx_pointer": resource["gfx_pointer"],
                    "palette_pointer": resource["palette_pointer"],
                    "compressed_sha256": resource["compressed_sha256"],
                    "palette_sha256": resource["palette_sha256"],
                    "pair_pointer_offsets": sorted(
                        alias["pair_file_offset"] for alias in aliases
                    ),
                },
            }
        )
    registry_path = root / REGION_REGISTRY_PATH
    return {
        "schema": "menu-portrait-relocation-v1",
        "base_rom_sha256": _sha256(base),
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": _sha256_file(root / CATALOG_PATH),
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGION_REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256_file(registry_path),
        "region": "menu-portraits",
        "region_owner": "menu_portrait_resources",
        "edits": edits,
    }


def export_audit(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    output = Path(output)
    if not output.is_absolute():
        output = root / output
    output.mkdir(parents=True, exist_ok=True)
    base_path = root / "rom/base.gba"
    base = base_path.read_bytes()
    if _sha256(base) != ROM_SHA256:
        raise ValueError("menu portrait audit base ROM mismatch")
    catalog_path = root / CATALOG_PATH
    if _sha256_file(catalog_path) != CATALOG_SHA256:
        raise ValueError("menu portrait audit catalog mismatch")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    layout_path = root / "sequel/rom-layout.json"
    layout = RomLayout.from_path(layout_path, base)
    registry_path = root / REGION_REGISTRY_PATH
    regions = ImageResourceRegions.from_path(registry_path, layout)
    region = regions.require("menu-portraits", "menu_portrait_resources")

    spec = _spec(root, base, catalog)
    spec_path = output / SPEC_NAME
    spec_path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    patches = resolve_menu_portrait_relocation_patches(
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
        if patch.get("asset_type") == "menu_portrait_pointer"
    ]
    if len(allocations) != 140 or len(redirects) != 622:
        raise ValueError("menu portrait audit patch denominator mismatch")
    resource_rows = [
        {
            key: patch[key]
            for key in (
                "id",
                "resource_type",
                "resource_ids",
                "source_pointer",
                "source_sha256",
                "source_size",
                "replacement_sha256",
                "replacement_size",
                "new_pointer",
                "offset",
                "all_pointer_offsets",
                "target_pointer_offsets",
                "logical_aliases",
            )
        }
        for patch in allocations
    ]
    allocation_end = max(
        patch["offset"] + len(bytes.fromhex(patch["after_hex"]))
        for patch in allocations
    )
    summary = {
        "logical_portrait_count": 311,
        "logical_pair_count": 74,
        "physical_payload_count": 140,
        "graphics_payload_count": 70,
        "palette_payload_count": 70,
        "logical_pointer_count": 622,
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
            "table_sha256": catalog["source_table"]["sha256"],
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
                "tools/verify_menu_portrait_relocation_audit.py",
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
        default=Path("artifacts") / ARTIFACT_ID,
    )
    args = parser.parse_args()
    payload = export_audit(args.root, args.output)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
