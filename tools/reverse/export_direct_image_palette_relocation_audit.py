#!/usr/bin/env python3
"""Export the direct image palette relocation proof artifact."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
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
from tools.extract_tileset import lz77_decompress
from tools.image_resource_regions import ImageResourceRegions
from tools.import_direct_image_palette_relocations import (
    DIRECT_INVENTORY_PATH,
    DIRECT_INVENTORY_SHA256,
    GRAPHICS_CATALOG_PATH,
    GRAPHICS_CATALOG_SHA256,
    LZ_INVENTORY_PATH,
    LZ_INVENTORY_SHA256,
    REGION_REGISTRY_PATH,
    ROM_BASE,
    ROM_SHA256,
    catalog_direct_image_palettes,
    resolve_direct_image_palette_relocation_patches,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


ARTIFACT_ID = "direct-image-palette-relocation-v1"
PAYLOAD_SCHEMA = "direct-image-palette-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
SCOPE = {
    "proved": (
        "All 18 strictly proven direct ROM-to-PRAM palette source addresses "
        "and all 29 exact aligned source-pointer roots are accounted for as "
        "17 physical allocations. A preservation relocation rebuilds a "
        "16 MiB ROM."
    ),
    "editable": (
        "All three 16-color LZ77 palettes and every non-overlap-locked raw "
        "BGR555 byte may be replaced at fixed decoded size. The nested "
        "0x08406010 source remains an alias of 0x08405FF0+0x20."
    ),
    "not_proved": (
        "Editing the 72 bytes shared with the scene LZ77 stream, assigning "
        "palettes to the two unresolved graphics, changing PRAM destinations "
        "or copy lengths, and final screen-composited runtime equivalence."
    ),
}
IMPLEMENTATION_PATHS = (
    "tools/export_rom_pointer_lz77_inventory.py",
    "tools/verify_rom_pointer_lz77_inventory.py",
    "tools/export_rom_pointer_lz77_graphics.py",
    "tools/verify_rom_pointer_lz77_graphics.py",
    "tools/export_rom_direct_cpuset_gpu_inventory.py",
    "tools/verify_rom_direct_cpuset_gpu_inventory.py",
    "tools/import_direct_image_palette_relocations.py",
    "tools/gba_image_export.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_direct_image_palette_relocation_audit.py",
    "tools/verify_direct_image_palette_relocation_audit.py",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _asset_path(root: Path, output: Path, name: str) -> str:
    path = output / name
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _apply(
    base: bytes,
    layout: RomLayout,
    regions: ImageResourceRegions,
    patches: list[dict[str, Any]],
) -> bytes:
    data = bytearray(layout.expanded_base())
    gate = PatchSafetyGate(base, layout=layout, image_regions=regions)
    for patch in patches:
        apply_patch(data, patch, gate=gate)
    return bytes(data)


def _source_bytes(base: bytes, row: dict[str, Any]) -> bytes:
    pointer = row["source_pointer"]
    if row["storage_kind"] == "lz77":
        return lz77_decompress(base, pointer - ROM_BASE)
    start = pointer - ROM_BASE
    return base[start : start + row["decoded_size"]]


def _source_spec(
    root: Path,
    output: Path,
    base: bytes,
) -> dict[str, Any]:
    catalog = catalog_direct_image_palettes(root, base)
    resources = []
    for row in catalog["resources"]:
        pointer = row["source_pointer"]
        name = f"palette_{pointer:08x}.bgr555.bin"
        (output / name).write_bytes(_source_bytes(base, row))
        resources.append(
            {
                "source_pointer": f"0x{pointer:08X}",
                "palette_file": _asset_path(root, output, name),
            }
        )
    registry = root / REGION_REGISTRY_PATH
    return {
        "schema": "direct-image-palette-relocation-v1",
        "base_rom_sha256": _sha256(base),
        "lz77_inventory": LZ_INVENTORY_PATH.as_posix(),
        "lz77_inventory_sha256": LZ_INVENTORY_SHA256,
        "graphics_catalog": GRAPHICS_CATALOG_PATH.as_posix(),
        "graphics_catalog_sha256": GRAPHICS_CATALOG_SHA256,
        "direct_inventory": DIRECT_INVENTORY_PATH.as_posix(),
        "direct_inventory_sha256": DIRECT_INVENTORY_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGION_REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256(registry.read_bytes()),
        "region": "direct-image-palettes",
        "region_owner": "direct_image_palettes",
        "resources": resources,
    }


def _mutate_palette(
    raw: bytes,
    source_pointer: int,
    index: int,
) -> bytes:
    result = bytearray(raw)
    result[2] ^= (index * 17 + 1) & 0xFF
    if source_pointer == 0x08405FF0:
        result[0x22] ^= 0x5A
    return bytes(result)


def _capability_fixture(
    root: Path,
    base: bytes,
    layout: RomLayout,
    regions: ImageResourceRegions,
    spec: dict[str, Any],
) -> dict[str, Any]:
    fixture = copy.deepcopy(spec)
    with tempfile.TemporaryDirectory(
        prefix=".direct-image-palette-capability-",
        dir=root / "build/experiments",
    ) as temporary:
        temp = Path(temporary)
        for index, row in enumerate(fixture["resources"]):
            source_pointer = int(row["source_pointer"], 0)
            source = Path(row["palette_file"])
            raw = _mutate_palette(
                source.read_bytes(),
                source_pointer,
                index,
            )
            path = temp / f"fixture-{index:02d}.bgr555.bin"
            path.write_bytes(raw)
            row["palette_file"] = str(path)
        spec_path = temp / "fixture.json"
        spec_path.write_text(
            json.dumps(fixture, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        patches = resolve_direct_image_palette_relocation_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
        output = _apply(base, layout, regions, patches)
    return {
        "mutation": (
            "xor byte 2 in every physical palette and byte 0x22 in "
            "0x08405FF0 to cover its nested logical alias"
        ),
        "changed_resources": len(spec["resources"]),
        "changed_logical_sources": len(spec["resources"]) + 1,
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
        raise ValueError("direct image palette audit base ROM mismatch")
    pinned = (
        (LZ_INVENTORY_PATH, LZ_INVENTORY_SHA256),
        (GRAPHICS_CATALOG_PATH, GRAPHICS_CATALOG_SHA256),
        (DIRECT_INVENTORY_PATH, DIRECT_INVENTORY_SHA256),
    )
    for path, expected in pinned:
        if _sha256((root / path).read_bytes()) != expected:
            raise ValueError(f"direct image palette audit input mismatch: {path}")
    layout_path = root / "sequel/rom-layout.json"
    layout = RomLayout.from_path(layout_path, base)
    regions = ImageResourceRegions.from_path(
        root / REGION_REGISTRY_PATH,
        layout,
    )
    region = regions.require(
        "direct-image-palettes",
        "direct_image_palettes",
    )
    spec = _source_spec(root, output, base)
    spec_path = output / SPEC_NAME
    spec_path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    patches = resolve_direct_image_palette_relocation_patches(
        root,
        spec_path,
        rom=base,
        layout=layout,
        regions=regions,
    )
    output_rom = _apply(base, layout, regions, patches)
    allocations = [row for row in patches if "allocation" in row]
    redirects = [
        row
        for row in patches
        if row.get("asset_type") == "direct_image_palette_pointer"
    ]
    allocation_end = max(
        row["offset"] + row["encoded_size"] for row in allocations
    )
    stored = sum(row["encoded_size"] for row in allocations)
    source_catalog = catalog_direct_image_palettes(root, base)
    summary = {
        "logical_source_count": source_catalog["logical_source_count"],
        "physical_resource_count": source_catalog[
            "physical_resource_count"
        ],
        "source_pointer_reference_count": source_catalog[
            "pointer_reference_count"
        ],
        "unexpected_source_pointer_count": len(
            source_catalog["unexpected_pointer_offsets"]
        ),
        "lz77_resource_count": source_catalog["lz77_resource_count"],
        "raw_resource_count": source_catalog["raw_resource_count"],
        "lz77_decoded_size": source_catalog["lz77_decoded_size"],
        "raw_physical_size": source_catalog["raw_physical_size"],
        "overlap_locked_size": source_catalog["overlap_locked_size"],
        "unresolved_graphics_palette_count": source_catalog[
            "unresolved_graphics_palette_count"
        ],
        "allocation_count": len(allocations),
        "pointer_patch_count": len(redirects),
        "allocation_start": region.start,
        "allocation_end": allocation_end,
        "region_end": region.end,
        "stored_payload_bytes": stored,
        "allocation_span": allocation_end - region.start,
        "remaining_bytes": region.end - allocation_end,
        "applied_patch_count": len(patches),
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
            "sha256": _sha256(layout_path.read_bytes()),
            "target_rom_size": layout.target_rom_size,
            "partition": "sequel-image-assets",
            "owner": "sequel_image_assets",
        },
        "region_registry": {
            "path": REGION_REGISTRY_PATH.as_posix(),
            "sha256": _sha256(
                (root / REGION_REGISTRY_PATH).read_bytes()
            ),
            "region": region.id,
            "owner": region.owner,
            "start": region.start,
            "end": region.end,
        },
        "lz77_inventory": {
            "path": LZ_INVENTORY_PATH.as_posix(),
            "sha256": LZ_INVENTORY_SHA256,
        },
        "graphics_catalog": {
            "path": GRAPHICS_CATALOG_PATH.as_posix(),
            "sha256": GRAPHICS_CATALOG_SHA256,
        },
        "direct_inventory": {
            "path": DIRECT_INVENTORY_PATH.as_posix(),
            "sha256": DIRECT_INVENTORY_SHA256,
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
                    "logical_source_pointers",
                    "new_pointer",
                    "storage_kind",
                    "decoded_size",
                    "encoded_size",
                    "color_count",
                    "replacement_sha256",
                    "pointer_offsets",
                    "range_aliases",
                    "locked_ranges",
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
                    "alias_offset",
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
            spec,
        ),
        "scope": SCOPE,
    }
    payload_path = output / PAYLOAD_NAME
    payload_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
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
        "scope": SCOPE,
        "summary": summary,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_direct_image_palette_relocation_audit.py",
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
