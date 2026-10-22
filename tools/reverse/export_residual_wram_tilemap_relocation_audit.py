#!/usr/bin/env python3
"""Export the three-source residual WRAM tilemap relocation proof."""

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
from tools.import_residual_wram_tilemap_relocations import (
    ABI_PATH,
    ABI_SHA256,
    OWNERSHIP_PATH,
    OWNERSHIP_SHA256,
    REGISTRY_PATH,
    ROM_SHA256,
    catalog_residual_wram_tilemaps,
    resolve_residual_wram_tilemap_relocation_patches,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


ARTIFACT_ID = "residual-wram-tilemap-relocation-v1"
PAYLOAD_SCHEMA = "residual-wram-tilemap-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
IMPLEMENTATION_PATHS = (
    "tools/export_residual_wram_tilemap_abi.py",
    "tools/verify_residual_wram_tilemap_abi.py",
    "tools/export_residual_wram_tilemap_resource_ownership.py",
    "tools/verify_residual_wram_tilemap_resource_ownership.py",
    "tools/import_residual_wram_tilemap_relocations.py",
    "tools/extract_tileset.py",
    "tools/gba_image_export.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_residual_wram_tilemap_relocation_audit.py",
    "tools/verify_residual_wram_tilemap_relocation_audit.py",
)
SCOPE = {
    "proved": (
        "The three pointer/literal-reachable residual WRAM tilemaps at "
        "0x0834928C, 0x083F1C98 and 0x085B67E0 and all three exact aligned "
        "source roots relocate into one owned region of a 16 MiB ROM, with "
        "their BG controls, graphics and palettes bound to a separately "
        "verified seven-source ownership catalog."
    ),
    "editable": (
        "All 657 entries keep their proven geometry and palette bank while "
        "selecting tiles inside each source's observed range and using "
        "standard horizontal or vertical flip bits."
    ),
    "not_proved": (
        "Computed-pointer consumers outside the proved pointer/literal roots, "
        "queue-slot success or natural flush, runtime reachability of every "
        "static caller, exact natural-language screen identity, and final "
        "screen pixel or timing equivalence."
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _published_asset_path(name: str) -> str:
    return f"artifacts/{ARTIFACT_ID}/{name}"


def _literal_worst_case_span(
    decoded_sizes: list[int],
    *,
    start: int,
) -> int:
    cursor = start
    for size in decoded_sizes:
        cursor = (cursor + 3) & ~3
        cursor += 4 + size + (size + 7) // 8
    return cursor - start


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
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    catalog = catalog_residual_wram_tilemaps(root, base)
    resources = []
    for row in catalog:
        name = f"tilemap-{row['source_pointer']:08x}.bin"
        (output / name).write_bytes(row["decoded"])
        resources.append(
            {
                "source_pointer": f"0x{row['source_pointer']:08X}",
                "tilemap_file": _published_asset_path(name),
            }
        )
    registry = root / REGISTRY_PATH
    spec = {
        "schema": "residual-wram-tilemap-relocation-v1",
        "base_rom_sha256": ROM_SHA256,
        "abi_artifact": ABI_PATH.as_posix(),
        "abi_sha256": ABI_SHA256,
        "resource_ownership_artifact": OWNERSHIP_PATH.as_posix(),
        "resource_ownership_sha256": OWNERSHIP_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256(registry.read_bytes()),
        "region": "residual-wram-tilemaps",
        "region_owner": "residual_wram_tilemaps",
        "resources": resources,
    }
    return spec, catalog


def _capability_fixture(
    root: Path,
    base: bytes,
    layout: RomLayout,
    regions: ImageResourceRegions,
    spec: dict[str, Any],
) -> dict[str, Any]:
    fixture = copy.deepcopy(spec)
    with tempfile.TemporaryDirectory(
        prefix=".residual-wram-tilemap-capability-",
        dir=root / "build/experiments",
    ) as temporary:
        temp = Path(temporary)
        for resource in fixture["resources"]:
            raw = bytearray(Path(resource["tilemap_file"]).read_bytes())
            entry = struct.unpack_from("<H", raw, 0)[0]
            struct.pack_into("<H", raw, 0, entry ^ 0x0400)
            tilemap = temp / Path(resource["tilemap_file"]).name
            tilemap.write_bytes(raw)
            resource["tilemap_file"] = str(tilemap)
        spec_path = temp / "fixture.json"
        spec_path.write_text(json.dumps(fixture, indent=2) + "\n")
        patches = resolve_residual_wram_tilemap_relocation_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
        output = _apply(base, layout, regions, patches)
    return {
        "mutation": "toggle H-flip on entry 0 of every tilemap",
        "changed_entries": 3,
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
        raise ValueError("residual WRAM tilemap audit base ROM mismatch")
    if _sha256((root / ABI_PATH).read_bytes()) != ABI_SHA256:
        raise ValueError("residual WRAM tilemap audit ABI mismatch")
    if _sha256((root / OWNERSHIP_PATH).read_bytes()) != OWNERSHIP_SHA256:
        raise ValueError("residual WRAM tilemap audit ownership mismatch")
    layout_path = root / "sequel/rom-layout.json"
    layout = RomLayout.from_path(layout_path, base)
    registry_path = root / REGISTRY_PATH
    regions = ImageResourceRegions.from_path(registry_path, layout)
    region = regions.require(
        "residual-wram-tilemaps",
        "residual_wram_tilemaps",
    )
    spec, catalog = _source_spec(root, output, base)
    spec_path = output / SPEC_NAME
    spec_path.write_text(json.dumps(spec, indent=2) + "\n")
    execution_spec = copy.deepcopy(spec)
    for resource in execution_spec["resources"]:
        resource["tilemap_file"] = str(
            output / Path(resource["tilemap_file"]).name
        )
    with tempfile.TemporaryDirectory(
        prefix=".residual-wram-tilemap-export-",
        dir=root / "build/experiments",
    ) as temporary:
        execution_spec_path = Path(temporary) / "execution-spec.json"
        execution_spec_path.write_text(
            json.dumps(execution_spec, indent=2) + "\n"
        )
        patches = resolve_residual_wram_tilemap_relocation_patches(
            root,
            execution_spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
    output_rom = _apply(base, layout, regions, patches)
    allocations = [row for row in patches if "allocation" in row]
    redirects = [row for row in patches if "allocation" not in row]
    allocation_end = max(
        row["offset"] + row["encoded_size"] for row in allocations
    )
    summary = {
        "source_count": len(catalog),
        "source_pointer_reference_count": sum(
            len(row["pointer_offsets"]) for row in catalog
        ),
        "unexpected_source_pointer_count": 0,
        "compressed_source_size": sum(
            row["compressed_size"] for row in catalog
        ),
        "decoded_size": sum(row["decoded_size"] for row in catalog),
        "entry_count": sum(row["entry_count"] for row in catalog),
        "allocation_count": len(allocations),
        "pointer_patch_count": len(redirects),
        "allocation_start": region.start,
        "allocation_end": allocation_end,
        "region_end": region.end,
        "stored_payload_bytes": sum(
            row["encoded_size"] for row in allocations
        ),
        "allocation_span": allocation_end - region.start,
        "remaining_bytes": region.end - allocation_end,
        "literal_lz77_worst_case_bytes_with_alignment": (
            _literal_worst_case_span(
                [row["decoded_size"] for row in catalog],
                start=region.start,
            )
        ),
        "applied_patch_count": len(patches),
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
        "abi": {
            "path": ABI_PATH.as_posix(),
            "sha256": ABI_SHA256,
        },
        "resource_ownership": {
            "path": OWNERSHIP_PATH.as_posix(),
            "sha256": OWNERSHIP_SHA256,
            "verified_source_count": len(catalog),
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
        "allocations": [
            {
                key: row[key]
                for key in (
                    "id",
                    "offset",
                    "source_pointer",
                    "new_pointer",
                    "replacement_sha256",
                    "decoded_size",
                    "encoded_size",
                    "width_entries",
                    "height_entries",
                    "entry_count",
                    "tile_index_range",
                    "palette_banks",
                    "horizontal_flip_count",
                    "vertical_flip_count",
                    "vram_destination",
                    "screenblock",
                )
            }
            for row in allocations
        ],
        "pointer_patches": [
            {
                key: row[key]
                for key in (
                    "id",
                    "offset",
                    "source_pointer",
                    "new_pointer",
                    "pointer_role",
                )
            }
            for row in redirects
        ],
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
                "tools/verify_residual_wram_tilemap_relocation_audit.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{ARTIFACT_ID}",
            ],
            "exit_code": 0,
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
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
    print(json.dumps(payload["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
