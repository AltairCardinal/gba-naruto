#!/usr/bin/env python3
"""Build production-relocated one-pixel world-map page 0 A/B ROMs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from tools.build_mod import apply_patch
from tools.image_resource_regions import ImageResourceRegions
from tools.import_world_map_background_relocations import (
    CATALOG_PATH,
    CATALOG_SHA256,
    REGION_REGISTRY_PATH,
    ROM_SHA256,
    SPEC_SCHEMA,
    catalog_world_map_background_relocation_payloads,
    resolve_world_map_background_relocation_patches,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


SCHEMA = "world-map-page0-pixel-ab-build-v1"
PAGE_ID = 0
RESOURCE_TYPE = "graphics"
TABLE_POINTER_OFFSET = 0x5A8014
SOURCE_POINTER = 0x084414E4
GRAPHICS_BYTE_OFFSET = 15588
TILE_ID = 243
CANVAS_XY = (116, 76)
BEFORE_INDEX = 112
AFTER_INDEX = 137
GRAPHICS_ALLOCATION_OFFSET = 0xB71000
INPUT_STATE = Path(
    "artifacts/runtime-checkpoints/scenario-41-postbattle-dialogue-11.ss9"
)
INPUT_STATE_SHA256 = (
    "bf821ecdd9945c123576ff7f26717c4d2018f07e623c36cb83dc2bb0fa569555"
)
VARIANTS = ("baseline", "candidate")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _spec(
    root: Path,
    resource: dict[str, Any],
    source_file: Path,
    variant: str,
) -> dict[str, Any]:
    registry_path = root / REGION_REGISTRY_PATH
    return {
        "schema": SPEC_SCHEMA,
        "base_rom_sha256": ROM_SHA256,
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": CATALOG_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGION_REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256(registry_path.read_bytes()),
        "region": "world-map-backgrounds",
        "region_owner": "world_map_background_resources",
        "edits": [
            {
                "id": f"world-map-page0-graphics-pixel-ab-{variant}",
                "resource_type": RESOURCE_TYPE,
                "resource_sha256": resource["resource_sha256"],
                "source_file": str(source_file),
                "expected": {
                    "decompressed_size": resource["decompressed_size"],
                    "physical_offsets": resource["physical_offsets"],
                    "pointer_offsets": sorted(
                        alias["table_pointer_offset"]
                        for alias in resource["pointer_aliases"]
                    ),
                },
                "target_pointer_offsets": [TABLE_POINTER_OFFSET],
            }
        ],
    }


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


def _ledger(patches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for patch in patches:
        allocation = patch.get("allocation")
        rows.append(
            {
                "id": patch["id"],
                "kind": "allocation" if allocation is not None else "redirect",
                "asset_type": patch["asset_type"],
                "resource_type": patch["resource_type"],
                "offset": patch["offset"],
                "size": len(bytes.fromhex(patch["after_hex"])),
                "before_sha256": _sha256(bytes.fromhex(patch["before_hex"])),
                "after_sha256": _sha256(bytes.fromhex(patch["after_hex"])),
                "before_hex": patch["before_hex"] if allocation is None else None,
                "after_hex": patch["after_hex"] if allocation is None else None,
                "new_pointer": patch["new_pointer"],
                "target_pointer_offsets": patch["target_pointer_offsets"],
                "allocation": allocation,
            }
        )
    return rows


def _changed_offsets(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("world-map page0 A/B payload sizes differ")
    return [
        index
        for index, (before, after) in enumerate(zip(left, right))
        if before != after
    ]


def build_pair(root: Path, output: Path) -> dict[str, Any]:
    """Build one preservation baseline and one page-0 graphics candidate."""

    root = Path(root).resolve()
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("world-map page0 A/B output directory must be empty")

    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("world-map page0 A/B base ROM identity mismatch")
    catalog_path = root / CATALOG_PATH
    if _sha256(catalog_path.read_bytes()) != CATALOG_SHA256:
        raise ValueError("world-map page0 A/B catalog identity mismatch")

    resources = catalog_world_map_background_relocation_payloads(root, base)
    resource = next(
        (
            row
            for row in resources.values()
            if row["resource_type"] == RESOURCE_TYPE
            and any(
                alias["page_id"] == PAGE_ID
                and alias["table_pointer_offset"] == TABLE_POINTER_OFFSET
                and alias["source_pointer"] == SOURCE_POINTER
                for alias in row["pointer_aliases"]
            )
        ),
        None,
    )
    if (
        resource is None
        or resource["decompressed_size"] != 32768
        or resource["physical_offsets"] != [SOURCE_POINTER - 0x08000000]
        or [
            alias["table_pointer_offset"] for alias in resource["pointer_aliases"]
        ]
        != [TABLE_POINTER_OFFSET]
    ):
        raise ValueError("world-map page0 graphics resource contract mismatch")

    original_path = catalog_path.parent / resource["source_files"][0]
    baseline_graphics = original_path.read_bytes()
    candidate_graphics = bytearray(baseline_graphics)
    if baseline_graphics[GRAPHICS_BYTE_OFFSET] != BEFORE_INDEX:
        raise ValueError("world-map page0 source pixel contract mismatch")
    candidate_graphics[GRAPHICS_BYTE_OFFSET] = AFTER_INDEX
    candidate_graphics = bytes(candidate_graphics)
    decoded_offsets = _changed_offsets(baseline_graphics, candidate_graphics)
    if decoded_offsets != [GRAPHICS_BYTE_OFFSET]:
        raise ValueError("world-map page0 decoded graphics isolation mismatch")

    output.mkdir(parents=True, exist_ok=True)
    layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    regions = ImageResourceRegions.from_path(root / REGION_REGISTRY_PATH, layout)
    variants: dict[str, dict[str, Any]] = {}
    roms: dict[str, bytes] = {}
    for variant in VARIANTS:
        variant_dir = output / variant
        variant_dir.mkdir()
        graphics_path = variant_dir / "background.8bpp.bin"
        if variant == "baseline":
            shutil.copyfile(original_path, graphics_path)
            graphics = baseline_graphics
        else:
            graphics_path.write_bytes(candidate_graphics)
            graphics = candidate_graphics
        spec_path = variant_dir / "spec.json"
        _write_json(spec_path, _spec(root, resource, graphics_path, variant))
        patches = resolve_world_map_background_relocation_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
        if (
            len(patches) != 2
            or [patch["offset"] for patch in patches]
            != [GRAPHICS_ALLOCATION_OFFSET, TABLE_POINTER_OFFSET]
            or patches[0].get("target_pointer_offsets")
            != [TABLE_POINTER_OFFSET]
            or patches[1].get("new_pointer") != 0x08000000 + GRAPHICS_ALLOCATION_OFFSET
        ):
            raise ValueError("world-map page0 A/B patch topology mismatch")
        rom = _apply(base, layout, regions, patches)
        rom_path = variant_dir / f"{variant}.gba"
        rom_path.write_bytes(rom)
        roms[variant] = rom
        variants[variant] = {
            "rom_path": rom_path.relative_to(output).as_posix(),
            "rom_sha256": _sha256(rom),
            "rom_size": len(rom),
            "spec_path": spec_path.relative_to(output).as_posix(),
            "graphics_path": graphics_path.relative_to(output).as_posix(),
            "graphics_sha256": _sha256(graphics),
            "patch_ledger": _ledger(patches),
        }

    changed_rom_offsets = _changed_offsets(roms["baseline"], roms["candidate"])
    baseline_ledger = variants["baseline"]["patch_ledger"]
    candidate_ledger = variants["candidate"]["patch_ledger"]
    allocation_end = max(
        GRAPHICS_ALLOCATION_OFFSET + baseline_ledger[0]["size"],
        GRAPHICS_ALLOCATION_OFFSET + candidate_ledger[0]["size"],
    )
    if (
        not changed_rom_offsets
        or min(changed_rom_offsets) < GRAPHICS_ALLOCATION_OFFSET
        or max(changed_rom_offsets) >= allocation_end
        or baseline_ledger[1]["after_hex"] != candidate_ledger[1]["after_hex"]
        or roms["baseline"][0x5A8020 : 0x5A8038]
        != roms["candidate"][0x5A8020 : 0x5A8038]
    ):
        raise ValueError("world-map page0 A/B ROM isolation mismatch")

    input_state = root / INPUT_STATE
    if _sha256(input_state.read_bytes()) != INPUT_STATE_SHA256:
        raise ValueError("world-map page0 input checkpoint identity mismatch")
    manifest = {
        "schema": SCHEMA,
        "base_rom_sha256": ROM_SHA256,
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": CATALOG_SHA256,
        "input_state": INPUT_STATE.as_posix(),
        "input_state_sha256": INPUT_STATE_SHA256,
        "input": {
            "key": "A",
            "down_frame": 5,
            "up_frame": 13,
            "capture_frame": 80,
        },
        "edit": {
            "page_id": PAGE_ID,
            "resource_type": RESOURCE_TYPE,
            "table_pointer_offset": TABLE_POINTER_OFFSET,
            "canvas_xy": list(CANVAS_XY),
            "tile_id": TILE_ID,
            "graphics_byte_offset": GRAPHICS_BYTE_OFFSET,
            "before_index": BEFORE_INDEX,
            "after_index": AFTER_INDEX,
        },
        "variants": variants,
        "isolation": {
            "decoded_graphics_offsets": decoded_offsets,
            "same_allocation_address": True,
            "same_redirect_pointer": True,
            "page_1_and_2_descriptors_unchanged": True,
            "rom_changed_offset_count": len(changed_rom_offsets),
            "rom_changed_offsets": changed_rom_offsets,
            "changed_span": [
                min(changed_rom_offsets),
                max(changed_rom_offsets) + 1,
            ],
        },
    }
    _write_json(output / "build-manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_pair(args.root, args.output)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
