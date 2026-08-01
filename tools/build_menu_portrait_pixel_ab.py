#!/usr/bin/env python3
"""Build production-relocated one-pixel menu portrait A/B ROMs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from tools.build_mod import apply_patch
from tools.image_resource_regions import ImageResourceRegions
from tools.import_menu_portrait_relocations import (
    REGION_REGISTRY_PATH,
    SPEC_SCHEMA,
    resolve_menu_portrait_relocation_patches,
)
from tools.import_menu_portraits import (
    CATALOG_PATH,
    CATALOG_SHA256,
    ROM_SHA256,
    portrait_canvas_to_stream,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


SCHEMA = "menu-portrait-pixel-ab-build-v1"
PORTRAIT_ID = 1
VARIANT_ID = 0
RESOURCE_ID = 0
PAIR_POINTER_OFFSET = 0x5A4E14
CANVAS_XY = (40, 40)
CANVAS_BYTE_OFFSET = CANVAS_XY[1] * 80 + CANVAS_XY[0]
STREAM_BYTE_OFFSET = 5184
BEFORE_INDEX = 52
AFTER_INDEX = 55
GRAPHICS_ALLOCATION_OFFSET = 0xA80000
PALETTE_ALLOCATION_OFFSET = 0xA80CD8
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
    aliases: list[dict[str, Any]],
    png_path: Path,
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
        "region": "menu-portraits",
        "region_owner": "menu_portrait_resources",
        "edits": [
            {
                "id": f"portrait-01-variant-0-pixel-ab-{variant}",
                "resource_id": RESOURCE_ID,
                "png": str(png_path),
                "expected": {
                    "gfx_pointer": resource["gfx_pointer"],
                    "palette_pointer": resource["palette_pointer"],
                    "compressed_sha256": resource["compressed_sha256"],
                    "palette_sha256": resource["palette_sha256"],
                    "pair_pointer_offsets": sorted(
                        alias["pair_file_offset"] for alias in aliases
                    ),
                },
                "target_pair_pointer_offsets": [PAIR_POINTER_OFFSET],
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
        raise ValueError("menu portrait A/B ROM sizes differ")
    return [
        index
        for index, pair in enumerate(zip(left, right))
        if pair[0] != pair[1]
    ]


def build_pair(root: Path, output: Path) -> dict[str, Any]:
    """Build one preservation baseline and one indexed-pixel candidate."""

    root = Path(root).resolve()
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("menu portrait A/B output directory must be empty")

    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("menu portrait A/B base ROM identity mismatch")
    catalog_path = root / CATALOG_PATH
    catalog_bytes = catalog_path.read_bytes()
    if _sha256(catalog_bytes) != CATALOG_SHA256:
        raise ValueError("menu portrait A/B catalog identity mismatch")
    catalog = json.loads(catalog_bytes)
    resources = {
        row["resource_id"]: row for row in catalog["unique_resources"]
    }
    resource = resources.get(RESOURCE_ID)
    aliases = [
        row
        for row in catalog["portraits"]
        if row["resource_id"] == RESOURCE_ID
    ]
    target = next(
        (
            row
            for row in aliases
            if row["portrait_id"] == PORTRAIT_ID
            and row["variant"] == VARIANT_ID
            and row["pair_file_offset"] == PAIR_POINTER_OFFSET
        ),
        None,
    )
    if resource is None or target is None or len(aliases) != 36:
        raise ValueError("menu portrait row-1 resource contract mismatch")
    source_path = catalog_path.parent / target["png"]
    with Image.open(source_path) as image:
        image.load()
        if (
            image.mode != "P"
            or image.size != (80, 80)
            or image.info.get("transparency") != 0
            or image.getpixel(CANVAS_XY) != BEFORE_INDEX
        ):
            raise ValueError("menu portrait source PNG contract mismatch")
        baseline_pixels = image.tobytes()
        candidate_image = image.copy()
        candidate_image.putpalette(image.getpalette())
        candidate_image.info["transparency"] = 0
        candidate_image.putpixel(CANVAS_XY, AFTER_INDEX)
        candidate_pixels = candidate_image.tobytes()
    baseline_stream = portrait_canvas_to_stream(baseline_pixels)
    candidate_stream = portrait_canvas_to_stream(candidate_pixels)
    decoded_differences = _changed_offsets(baseline_stream, candidate_stream)
    if (
        decoded_differences != [STREAM_BYTE_OFFSET]
        or baseline_stream[STREAM_BYTE_OFFSET] != BEFORE_INDEX
        or candidate_stream[STREAM_BYTE_OFFSET] != AFTER_INDEX
    ):
        raise ValueError("menu portrait single-pixel stream isolation mismatch")

    output.mkdir(parents=True, exist_ok=True)
    layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    regions = ImageResourceRegions.from_path(
        root / REGION_REGISTRY_PATH,
        layout,
    )
    variants: dict[str, dict[str, Any]] = {}
    roms: dict[str, bytes] = {}
    for variant in VARIANTS:
        variant_dir = output / variant
        variant_dir.mkdir()
        png_path = variant_dir / "portrait.png"
        if variant == "baseline":
            shutil.copyfile(source_path, png_path)
        else:
            candidate_image.save(png_path, transparency=0)
        spec_path = variant_dir / "spec.json"
        _write_json(spec_path, _spec(root, resource, aliases, png_path, variant))
        patches = resolve_menu_portrait_relocation_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
        expected_sizes = (3287 if variant == "baseline" else 3288, 128, 4, 4)
        if (
            len(patches) != 4
            or tuple(len(bytes.fromhex(row["after_hex"])) for row in patches)
            != expected_sizes
            or tuple(row["offset"] for row in patches)
            != (
                GRAPHICS_ALLOCATION_OFFSET,
                PALETTE_ALLOCATION_OFFSET,
                PAIR_POINTER_OFFSET,
                PAIR_POINTER_OFFSET + 4,
            )
        ):
            raise ValueError("menu portrait A/B patch topology mismatch")
        rom = _apply(base, layout, regions, patches)
        rom_path = variant_dir / f"{variant}.gba"
        rom_path.write_bytes(rom)
        graphics = baseline_stream if variant == "baseline" else candidate_stream
        roms[variant] = rom
        variants[variant] = {
            "rom_path": rom_path.relative_to(output).as_posix(),
            "rom_sha256": _sha256(rom),
            "rom_size": len(rom),
            "spec_path": spec_path.relative_to(output).as_posix(),
            "png_path": png_path.relative_to(output).as_posix(),
            "png_sha256": _sha256(png_path.read_bytes()),
            "graphics_sha256": _sha256(graphics),
            "palette_sha256": resource["palette_sha256"],
            "patch_ledger": _ledger(patches),
        }

    changed = _changed_offsets(roms["baseline"], roms["candidate"])
    if (
        not changed
        or min(changed) < GRAPHICS_ALLOCATION_OFFSET
        or max(changed) >= PALETTE_ALLOCATION_OFFSET
        or roms["baseline"][PAIR_POINTER_OFFSET : PAIR_POINTER_OFFSET + 8]
        != roms["candidate"][PAIR_POINTER_OFFSET : PAIR_POINTER_OFFSET + 8]
        or roms["baseline"][
            PALETTE_ALLOCATION_OFFSET : PALETTE_ALLOCATION_OFFSET + 128
        ]
        != roms["candidate"][
            PALETTE_ALLOCATION_OFFSET : PALETTE_ALLOCATION_OFFSET + 128
        ]
    ):
        raise ValueError("menu portrait A/B ROM isolation mismatch")

    input_state = root / "artifacts/runtime-checkpoints/scenario-41-postbattle-dialogue-9.ss9"
    manifest = {
        "schema": SCHEMA,
        "base_rom_sha256": ROM_SHA256,
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": CATALOG_SHA256,
        "input_state": input_state.relative_to(root).as_posix(),
        "input_state_sha256": _sha256(input_state.read_bytes()),
        "input": {
            "key": "A",
            "down_frame": 5,
            "up_frame": 13,
            "capture_frame": 80,
        },
        "edit": {
            "portrait_id": PORTRAIT_ID,
            "variant": VARIANT_ID,
            "resource_id": RESOURCE_ID,
            "pair_pointer_offset": PAIR_POINTER_OFFSET,
            "canvas_xy": list(CANVAS_XY),
            "canvas_byte_offset": CANVAS_BYTE_OFFSET,
            "stream_byte_offset": STREAM_BYTE_OFFSET,
            "before_index": BEFORE_INDEX,
            "after_index": AFTER_INDEX,
        },
        "variants": variants,
        "isolation": {
            "same_allocation_addresses": True,
            "same_redirect_pointers": True,
            "single_decoded_graphics_byte": True,
            "rom_changed_offset_count": len(changed),
            "rom_changed_offsets": changed,
            "changed_span": [min(changed), max(changed) + 1],
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
