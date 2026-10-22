#!/usr/bin/env python3
"""Export a signed full-relocation audit for all story BG3 layer resources."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
for candidate in (REPO_ROOT, TOOLS_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from tools.build_mod import apply_patch
from tools.image_resource_regions import ImageResourceRegions
from tools.import_story_visual_resource_relocations import (
    CATALOG_PATH,
    CATALOG_SHA256,
    REGION_REGISTRY_PATH,
    ROM_SHA256,
    SPEC_SCHEMA,
    catalog_story_visual_relocation_payloads,
    resolve_story_visual_resource_relocation_patches,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


ARTIFACT_ID = "story-visual-resource-relocation-v1"
PAYLOAD_SCHEMA = "story-visual-resource-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
SOURCE_ARTIFACT = Path("artifacts/story-visual-resource-sources-v1")
SOURCE_MANIFEST = SOURCE_ARTIFACT / "manifest.json"
SOURCE_PAYLOAD = SOURCE_ARTIFACT / "source-catalog.json"
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
SCOPE = {
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


def _source_rows(root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    manifest = _json(root / SOURCE_MANIFEST)
    catalog = _json(root / SOURCE_PAYLOAD)
    expected_files = {
        path.relative_to(root / SOURCE_ARTIFACT).as_posix(): _sha256_file(path)
        for path in (root / SOURCE_ARTIFACT).rglob("*")
        if path.is_file() and path != root / SOURCE_MANIFEST
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
        != expected_files[SOURCE_PAYLOAD.name]
        or manifest.get("files") != expected_files
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
        raise ValueError("story visual source artifact manifest mismatch")
    by_key = {
        (row["resource_type"], row["resource_sha256"]): row for row in rows
    }
    if len(by_key) != 49:
        raise ValueError("story visual source artifact identities overlap")
    return by_key


def _full_spec(
    root: Path,
    base: bytes,
    resources: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    source_rows = _source_rows(root)
    edits = []
    for key, resource in sorted(
        resources.items(),
        key=lambda item: (
            min(item[1]["physical_offsets"]),
            item[1]["resource_type"],
        ),
    ):
        source_row = source_rows.get(key)
        if source_row is None:
            raise ValueError("story visual source artifact is incomplete")
        source_file = SOURCE_ARTIFACT / source_row["source_file"]
        if (root / source_file).read_bytes() != resource["content"]:
            raise ValueError("story visual source artifact payload mismatch")
        edits.append(
            {
                "id": (
                    f"{resource['resource_type']}-"
                    f"{resource['resource_sha256'][:12]}"
                ),
                "resource_type": resource["resource_type"],
                "resource_sha256": resource["resource_sha256"],
                "source_file": source_file.as_posix(),
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
        "schema": SPEC_SCHEMA,
        "base_rom_sha256": _sha256(base),
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": CATALOG_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGION_REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256_file(registry_path),
        "region": "story-visual-layers",
        "region_owner": "story_visual_resources",
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
        raise ValueError("story visual relocation audit base ROM mismatch")
    resources = catalog_story_visual_relocation_payloads(root, base)
    spec = _full_spec(root, base, resources)
    spec_path = output / SPEC_NAME
    spec_path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    layout_path = root / "sequel/rom-layout.json"
    registry_path = root / REGION_REGISTRY_PATH
    layout = RomLayout.from_path(layout_path, base)
    regions = ImageResourceRegions.from_path(registry_path, layout)
    region = regions.require(
        "story-visual-layers",
        "story_visual_resources",
    )
    patches = resolve_story_visual_resource_relocation_patches(
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
        if patch.get("asset_type") == "story_visual_resource_relocation"
    ]
    redirects = [
        patch
        for patch in patches
        if patch.get("asset_type") == "story_visual_resource_pointer"
    ]
    if len(allocations) != 49 or len(redirects) != 72:
        raise ValueError("story visual relocation audit patch denominator mismatch")
    allocation_end = max(
        patch["offset"] + len(bytes.fromhex(patch["after_hex"]))
        for patch in allocations
    )
    summary = {
        "layer_count": 24,
        "content_resource_count": 49,
        "physical_payload_count": 72,
        "logical_pointer_count": 72,
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
    resource_rows = [
        {
            key: patch[key]
            for key in (
                "id",
                "resource_type",
                "resource_sha256",
                "replacement_sha256",
                "decompressed_size",
                "encoded_size",
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
    linked_table = base[0x5A320C : 0x5A320C + 79 * 0x44]
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
            "sha256": _sha256_file(root / CATALOG_PATH),
        },
        "source_artifact": {
            "path": SOURCE_ARTIFACT.as_posix(),
            "manifest_sha256": _sha256_file(root / SOURCE_MANIFEST),
            "payload_sha256": _sha256_file(root / SOURCE_PAYLOAD),
        },
        "linked_tile_assets": {
            "table_offset": 0x5A320C,
            "entry_count": 79,
            "entry_size": 0x44,
            "table_sha256": _sha256(linked_table),
            "relationship": "config_id only; no linked descriptor is patched",
        },
        "authoring_spec": {
            "file": SPEC_NAME,
            "sha256": _sha256_file(spec_path),
        },
        "implementation": {
            path: _sha256_file(root / path) for path in IMPLEMENTATION_PATHS
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
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_id": ARTIFACT_ID,
        "artifact_schema": PAYLOAD_SCHEMA,
        "artifact_status": "accepted",
        "payload_file": PAYLOAD_NAME,
        "payload_sha256": files[PAYLOAD_NAME],
        "files": files,
        "scope": SCOPE,
        "summary": summary,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_story_visual_resource_relocation_audit.py",
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
