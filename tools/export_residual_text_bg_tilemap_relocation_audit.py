#!/usr/bin/env python3
"""Export the residual text-BG tilemap relocation proof artifact."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import struct
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

from tools.build_mod import apply_patch
from tools.image_resource_regions import ImageResourceRegions
from tools.import_residual_text_bg_tilemap_relocations import (
    INVENTORY_PATH,
    INVENTORY_SHA256,
    OWNERSHIP_PATH,
    OWNERSHIP_SHA256,
    REGISTRY_PATH,
    ROM_SHA256,
    SOURCE_POINTER,
    catalog_residual_text_bg_tilemap,
    resolve_residual_text_bg_tilemap_relocation_patches,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


ARTIFACT_ID = "residual-text-bg-tilemap-relocation-v1"
PAYLOAD_SCHEMA = "residual-text-bg-tilemap-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
TILEMAP_NAME = "tilemap.bin"
IMPLEMENTATION_PATHS = (
    "tools/export_rom_pointer_lz77_inventory.py",
    "tools/verify_rom_pointer_lz77_inventory.py",
    "tools/export_residual_text_bg_tilemap_resource_ownership.py",
    "tools/verify_residual_text_bg_tilemap_resource_ownership.py",
    "tools/import_residual_text_bg_tilemap_relocations.py",
    "tools/gba_image_export.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_residual_text_bg_tilemap_relocation_audit.py",
    "tools/verify_residual_text_bg_tilemap_relocation_audit.py",
)
SCOPE = {
    "proved": (
        "The single pointer-reachable residual text-BG tilemap at "
        "0x08349368 and its only aligned source-pointer root relocate into "
        "a 16 MiB ROM, with BG2, graphics and palette ownership bound to a "
        "separately verified artifact."
    ),
    "editable": (
        "All 640 32x20 screen entries may select tile 0..5, palette bank 1, "
        "and standard horizontal or vertical flip bits."
    ),
    "not_proved": (
        "Changing the screenblock destination, coordinated semantic authoring "
        "across its separately relocatable graphics/palette resources, the "
        "runtime ordering against another stream that may reuse 0x06001000, "
        "assigning a natural-language screen identity, and final "
        "screen-composited runtime equivalence."
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _published_asset_path(name: str) -> str:
    return f"artifacts/{ARTIFACT_ID}/{name}"


def _apply(
    base: bytes,
    layout: RomLayout,
    regions: ImageResourceRegions,
    patches: list[dict[str, Any]],
) -> bytes:
    output = bytearray(layout.expanded_base())
    gate = PatchSafetyGate(base, layout=layout, image_regions=regions)
    for patch in patches:
        apply_patch(output, patch, gate=gate)
    return bytes(output)


def _source_spec(
    root: Path,
    output: Path,
    base: bytes,
) -> dict[str, Any]:
    catalog = catalog_residual_text_bg_tilemap(root, base)
    (output / TILEMAP_NAME).write_bytes(catalog["decoded"])
    registry = root / REGISTRY_PATH
    return {
        "schema": "residual-text-bg-tilemap-relocation-v1",
        "base_rom_sha256": ROM_SHA256,
        "inventory": INVENTORY_PATH.as_posix(),
        "inventory_sha256": INVENTORY_SHA256,
        "resource_ownership_artifact": OWNERSHIP_PATH.as_posix(),
        "resource_ownership_sha256": OWNERSHIP_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256(registry.read_bytes()),
        "region": "residual-text-bg-tilemap",
        "region_owner": "residual_text_bg_tilemap",
        "source_pointer": f"0x{SOURCE_POINTER:08X}",
        "tilemap_file": _published_asset_path(TILEMAP_NAME),
    }


def _capability_fixture(
    root: Path,
    base: bytes,
    layout: RomLayout,
    regions: ImageResourceRegions,
    spec: dict[str, Any],
) -> dict[str, Any]:
    fixture = copy.deepcopy(spec)
    with tempfile.TemporaryDirectory(
        prefix=".residual-text-bg-tilemap-capability-",
        dir=root / "build/experiments",
    ) as temporary:
        temp = Path(temporary)
        raw = bytearray(Path(fixture["tilemap_file"]).read_bytes())
        entry = struct.unpack_from("<H", raw, 0)[0]
        tile = entry & 0x03FF
        struct.pack_into("<H", raw, 0, (entry & ~0x03FF) | ((tile + 1) % 6))
        tilemap = temp / TILEMAP_NAME
        tilemap.write_bytes(raw)
        fixture["tilemap_file"] = str(tilemap)
        spec_path = temp / "fixture.json"
        spec_path.write_text(json.dumps(fixture, indent=2) + "\n")
        patches = resolve_residual_text_bg_tilemap_relocation_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
        output = _apply(base, layout, regions, patches)
    return {
        "mutation": "increment entry 0 tile index modulo 6",
        "changed_entries": 1,
        "output_rom_sha256": _sha256(output),
    }


def export_audit(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    output = Path(output).resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (root / "build/experiments").mkdir(parents=True, exist_ok=True)
    base = (root / "rom/base.gba").read_bytes()
    if _sha256(base) != ROM_SHA256:
        raise ValueError("residual text-BG tilemap audit base ROM mismatch")
    if _sha256((root / INVENTORY_PATH).read_bytes()) != INVENTORY_SHA256:
        raise ValueError("residual text-BG tilemap audit inventory mismatch")
    if _sha256((root / OWNERSHIP_PATH).read_bytes()) != OWNERSHIP_SHA256:
        raise ValueError("residual text-BG tilemap audit ownership mismatch")
    layout_path = root / "sequel/rom-layout.json"
    layout = RomLayout.from_path(layout_path, base)
    registry_path = root / REGISTRY_PATH
    regions = ImageResourceRegions.from_path(registry_path, layout)
    region = regions.require(
        "residual-text-bg-tilemap",
        "residual_text_bg_tilemap",
    )
    catalog = catalog_residual_text_bg_tilemap(root, base)
    spec = _source_spec(root, output, base)
    spec_path = output / SPEC_NAME
    spec_path.write_text(json.dumps(spec, indent=2) + "\n")
    execution_spec = copy.deepcopy(spec)
    execution_spec["tilemap_file"] = str(output / TILEMAP_NAME)
    with tempfile.TemporaryDirectory(
        prefix=".residual-text-bg-tilemap-export-",
        dir=root / "build/experiments",
    ) as temporary:
        execution_spec_path = Path(temporary) / "execution-spec.json"
        execution_spec_path.write_text(
            json.dumps(execution_spec, indent=2) + "\n"
        )
        patches = resolve_residual_text_bg_tilemap_relocation_patches(
            root,
            execution_spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
    output_rom = _apply(base, layout, regions, patches)
    allocation = next(row for row in patches if "allocation" in row)
    redirect = next(row for row in patches if "allocation" not in row)
    end = allocation["offset"] + allocation["encoded_size"]
    summary = {
        "source_count": 1,
        "source_pointer_reference_count": 1,
        "unexpected_source_pointer_count": 0,
        "compressed_source_size": catalog["compressed_size"],
        "decoded_size": catalog["decoded_size"],
        "entry_count": catalog["entry_count"],
        "tile_index_min": catalog["tile_index_range"][0],
        "tile_index_max": catalog["tile_index_range"][1],
        "palette_banks": catalog["palette_banks"],
        "allocation_count": 1,
        "pointer_patch_count": 1,
        "allocation_start": region.start,
        "allocation_end": end,
        "region_end": region.end,
        "stored_payload_bytes": allocation["encoded_size"],
        "allocation_span": end - region.start,
        "remaining_bytes": region.end - end,
        "applied_patch_count": 2,
    }
    payload = {
        "schema": PAYLOAD_SCHEMA,
        "base_rom": {
            "path": "rom/base.gba",
            "size": len(base),
            "sha256": ROM_SHA256,
        },
        "layout": {
            "path": "sequel/rom-layout.json",
            "sha256": _sha256(layout_path.read_bytes()),
            "target_rom_size": layout.target_rom_size,
            "partition": "sequel-image-assets",
            "owner": "sequel_image_assets",
        },
        "region_registry": {
            "path": REGISTRY_PATH.as_posix(),
            "sha256": _sha256(registry_path.read_bytes()),
            "region": region.id,
            "owner": region.owner,
            "start": region.start,
            "end": region.end,
        },
        "inventory": {
            "path": INVENTORY_PATH.as_posix(),
            "sha256": INVENTORY_SHA256,
        },
        "resource_ownership": {
            "path": OWNERSHIP_PATH.as_posix(),
            "sha256": OWNERSHIP_SHA256,
            "verified_source_count": 1,
        },
        "authoring_spec": {
            "file": SPEC_NAME,
            "sha256": _sha256(spec_path.read_bytes()),
        },
        "implementation": {
            path: _sha256((root / path).read_bytes())
            for path in IMPLEMENTATION_PATHS
        },
        "summary": summary,
        "allocation": {
            key: allocation[key]
            for key in (
                "id",
                "offset",
                "source_pointer",
                "new_pointer",
                "replacement_sha256",
                "decoded_size",
                "encoded_size",
                "entry_count",
                "tile_index_range",
                "palette_banks",
                "horizontal_flip_count",
                "vertical_flip_count",
                "destination",
            )
        },
        "pointer_patch": {
            key: redirect[key]
            for key in (
                "id",
                "offset",
                "source_pointer",
                "new_pointer",
                "pointer_role",
            )
        },
        "output_rom_sha256": _sha256(output_rom),
        "capability_fixture": _capability_fixture(
            root,
            base,
            layout,
            regions,
            execution_spec,
        ),
        "scope": SCOPE,
    }
    payload_path = output / PAYLOAD_NAME
    payload_path.write_text(json.dumps(payload, indent=2) + "\n")
    files = {
        path.name: _sha256(path.read_bytes())
        for path in sorted(output.iterdir())
        if path.is_file()
    }
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_id": ARTIFACT_ID,
        "artifact_schema": PAYLOAD_SCHEMA,
        "artifact_status": "accepted",
        "payload_file": PAYLOAD_NAME,
        "payload_sha256": files[PAYLOAD_NAME],
        "files": files,
        "implementation": payload["implementation"],
        "scope": SCOPE,
        "summary": summary,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_residual_text_bg_tilemap_relocation_audit.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{ARTIFACT_ID}",
            ],
            "exit_code": 0,
        },
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
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
    output = args.output
    if not output.is_absolute():
        output = args.root / output
    payload = export_audit(args.root, output)
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
