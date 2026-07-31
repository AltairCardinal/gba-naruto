#!/usr/bin/env python3
"""Build an isolated relocated-ROM pixel A/B pair for one WRAM tilemap entry."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
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
from tools.extract_tileset import lz77_decompress
from tools.image_resource_regions import ImageResourceRegions
from tools.import_residual_wram_derived_tilemap_relocations import (
    ABI_PATH,
    ABI_SHA256,
    OWNERSHIP_PATH,
    OWNERSHIP_SHA256,
    REGION_ID,
    REGION_OWNER,
    ROM_BASE,
    ROM_SHA256,
    SPEC_SCHEMA,
    catalog_residual_wram_derived_tilemaps,
    resolve_residual_wram_derived_tilemap_relocation_patches,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


SCHEMA = "residual-wram-tilemap-pixel-ab-build-v1"
SOURCE_POINTER = 0x084635D8
ROW = 8
COLUMN = 8
BEFORE_ENTRY = 0xD80C
AFTER_ENTRY = 0xD80B
TILE_ADD = 0x02BC
DESTINATION = 0x06000806
ROW_STRIDE = 0x40
SCREEN_BASE = 0x06000800
GRAPHICS_POINTER = 0x08463688
GRAPHICS_TILE_BASE = 700
GRAPHICS_TILE_BYTES = 32
GRAPHICS_DECODED_SIZE = 3072
PALETTE_POINTER = 0x084638F4
PALETTE_BANK = 13
REGISTRY_PATH = Path("sequel/image-resource-regions.json")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex16(value: int) -> str:
    return f"0x{value:04X}"


def _hex32(value: int) -> str:
    return f"0x{value:08X}"


def _decode_tile(graphics: bytes, tile: int, *, vertical_flip: bool) -> list[int]:
    relative = tile - GRAPHICS_TILE_BASE
    if not 0 <= relative < GRAPHICS_DECODED_SIZE // GRAPHICS_TILE_BYTES:
        raise ValueError("pixel A/B tile is outside the owned graphics range")
    raw = graphics[
        relative * GRAPHICS_TILE_BYTES : (relative + 1) * GRAPHICS_TILE_BYTES
    ]
    pixels: list[int] = []
    for value in raw:
        pixels.extend((value & 0x0F, value >> 4))
    rows = [pixels[index : index + 8] for index in range(0, 64, 8)]
    if vertical_flip:
        rows.reverse()
    return [pixel for row in rows for pixel in row]


def _pixel_oracle(rom: bytes) -> dict[str, Any]:
    graphics = lz77_decompress(rom, GRAPHICS_POINTER - ROM_BASE)
    if len(graphics) != GRAPHICS_DECODED_SIZE:
        raise ValueError("pixel A/B graphics size mismatch")
    before_effective = (BEFORE_ENTRY + TILE_ADD) & 0xFFFF
    after_effective = (AFTER_ENTRY + TILE_ADD) & 0xFFFF
    before_tile = before_effective & 0x03FF
    after_tile = after_effective & 0x03FF
    vertical_flip = bool(before_effective & 0x0800)
    if vertical_flip != bool(after_effective & 0x0800):
        raise ValueError("pixel A/B unexpectedly changes vertical flip")
    before = _decode_tile(graphics, before_tile, vertical_flip=vertical_flip)
    after = _decode_tile(graphics, after_tile, vertical_flip=vertical_flip)
    screen_x = ((DESTINATION - SCREEN_BASE) // 2 % 32 + COLUMN) * 8
    screen_y = (((DESTINATION - SCREEN_BASE) // 2) // 32 + ROW) * 8
    changed = []
    for index, (left, right) in enumerate(zip(before, after)):
        if left != right:
            changed.append(
                {
                    "x": screen_x + index % 8,
                    "y": screen_y + index // 8,
                    "before_palette_index": left,
                    "after_palette_index": right,
                }
            )
    return {
        "graphics_pointer": _hex32(GRAPHICS_POINTER),
        "graphics_tile_base": GRAPHICS_TILE_BASE,
        "before_tile_index": before_tile,
        "after_tile_index": after_tile,
        "palette_pointer": _hex32(PALETTE_POINTER),
        "palette_bank": PALETTE_BANK,
        "vertical_flip": vertical_flip,
        "screen_bbox": [screen_x, screen_y, screen_x + 7, screen_y + 7],
        "source_tile_differing_pixel_count": len(changed),
        "expected_screen_pixels": changed,
    }


def _spec(root: Path, resources: dict[int, Path]) -> dict[str, Any]:
    registry = root / REGISTRY_PATH
    return {
        "schema": SPEC_SCHEMA,
        "base_rom_sha256": ROM_SHA256,
        "abi_artifact": ABI_PATH.as_posix(),
        "abi_sha256": ABI_SHA256,
        "resource_ownership_artifact": OWNERSHIP_PATH.as_posix(),
        "resource_ownership_sha256": OWNERSHIP_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256(registry.read_bytes()),
        "region": REGION_ID,
        "region_owner": REGION_OWNER,
        "resources": [
            {
                "source_pointer": _hex32(pointer),
                "tilemap_file": str(resources[pointer]),
            }
            for pointer in sorted(resources)
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


def _patch_ledger(patches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": patch["id"],
            "kind": "allocation" if "allocation" in patch else "pointer_redirect",
            "offset": patch["offset"],
            "before_hex": patch["before_hex"],
            "after_hex": patch["after_hex"],
            "source_pointer": _hex32(patch["source_pointer"]),
            "new_pointer": _hex32(patch["new_pointer"]),
            "replacement_sha256": patch.get("replacement_sha256"),
        }
        for patch in patches
    ]


def build_ab_roms(
    root: Path,
    output: Path,
    *,
    row: int = ROW,
    column: int = COLUMN,
    replacement_entry: int = AFTER_ENTRY,
) -> dict[str, Any]:
    root = Path(root).resolve()
    output = Path(output).resolve()
    if (row, column, replacement_entry) != (ROW, COLUMN, AFTER_ENTRY):
        raise ValueError(
            "pixel A/B fixed A/B contract requires row 8, column 8, "
            "replacement 0xD80B"
        )
    base = (root / "rom/base.gba").read_bytes()
    if _sha256(base) != ROM_SHA256:
        raise ValueError("pixel A/B base ROM SHA-256 mismatch")
    layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    regions = ImageResourceRegions.from_path(root / REGISTRY_PATH, layout)
    catalog = catalog_residual_wram_derived_tilemaps(root, base)
    by_pointer = {record["source_pointer"]: record for record in catalog}
    source = by_pointer[SOURCE_POINTER]
    values = list(struct.unpack("<144H", source["decoded"]))
    entry_index = ROW * 12 + COLUMN
    if values[entry_index] != BEFORE_ENTRY:
        raise ValueError("pixel A/B source entry contract mismatch")

    if output.exists() and any(output.iterdir()):
        raise ValueError("pixel A/B output directory must be empty")
    output.mkdir(parents=True, exist_ok=True)
    specs: dict[str, Path] = {}
    patch_sets: dict[str, list[dict[str, Any]]] = {}
    roms: dict[str, bytes] = {}
    decoded_hashes: dict[str, str] = {}
    for variant in ("baseline", "candidate"):
        resource_dir = output / "resources" / variant
        resource_dir.mkdir(parents=True)
        resources: dict[int, Path] = {}
        for record in catalog:
            decoded = bytearray(record["decoded"])
            if variant == "candidate" and record["source_pointer"] == SOURCE_POINTER:
                struct.pack_into("<H", decoded, entry_index * 2, AFTER_ENTRY)
            path = resource_dir / f"{record['source_pointer']:08X}.bin"
            path.write_bytes(decoded)
            resources[record["source_pointer"]] = path
        spec_path = output / f"{variant}-spec.json"
        spec_path.write_text(
            json.dumps(_spec(root, resources), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        specs[variant] = spec_path
        patches = resolve_residual_wram_derived_tilemap_relocation_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
        patch_sets[variant] = patches
        rom = _apply(base, layout, regions, patches)
        rom_path = output / f"{variant}.gba"
        rom_path.write_bytes(rom)
        roms[variant] = rom
        target_patch = next(
            patch
            for patch in patches
            if patch.get("source_pointer") == SOURCE_POINTER
            and "allocation" in patch
        )
        decoded_hashes[variant] = target_patch["replacement_sha256"]

    baseline_target = next(
        patch
        for patch in patch_sets["baseline"]
        if patch.get("source_pointer") == SOURCE_POINTER and "allocation" in patch
    )
    candidate_target = next(
        patch
        for patch in patch_sets["candidate"]
        if patch.get("source_pointer") == SOURCE_POINTER and "allocation" in patch
    )
    if baseline_target["new_pointer"] != candidate_target["new_pointer"]:
        raise ValueError("pixel A/B runtime source pointers diverged")
    runtime_pointer = baseline_target["new_pointer"]
    baseline_raw = lz77_decompress(roms["baseline"], runtime_pointer - ROM_BASE)
    candidate_raw = lz77_decompress(roms["candidate"], runtime_pointer - ROM_BASE)
    differing_source_bytes = [
        index
        for index, (left, right) in enumerate(zip(baseline_raw, candidate_raw))
        if left != right
    ]
    if differing_source_bytes != [entry_index * 2]:
        raise ValueError("pixel A/B decoded source is not a single-byte edit")

    manifest = {
        "schema": SCHEMA,
        "base_rom_sha256": ROM_SHA256,
        "runtime_source_pointer": _hex32(runtime_pointer),
        "edit": {
            "source_pointer": _hex32(SOURCE_POINTER),
            "row": ROW,
            "column": COLUMN,
            "entry_index": entry_index,
            "before_entry": _hex16(BEFORE_ENTRY),
            "after_entry": _hex16(AFTER_ENTRY),
            "effective_before_entry": _hex16((BEFORE_ENTRY + TILE_ADD) & 0xFFFF),
            "effective_after_entry": _hex16((AFTER_ENTRY + TILE_ADD) & 0xFFFF),
            "tile_add": _hex16(TILE_ADD),
            "vram_entry_address": _hex32(
                DESTINATION + ROW * ROW_STRIDE + COLUMN * 2
            ),
            "decoded_differing_byte_offsets": differing_source_bytes,
        },
        "pixel_oracle": _pixel_oracle(base),
        "roms": {
            variant: {
                "path": f"{variant}.gba",
                "sha256": _sha256(roms[variant]),
                "size": len(roms[variant]),
                "target_decoded_sha256": decoded_hashes[variant],
                "spec": specs[variant].name,
            }
            for variant in ("baseline", "candidate")
        },
        "patch_ledgers": {
            variant: _patch_ledger(patch_sets[variant])
            for variant in ("baseline", "candidate")
        },
        "isolation": {
            "same_runtime_source_pointer": True,
            "same_pointer_redirects": [
                patch["after_hex"]
                for patch in patch_sets["baseline"]
                if "allocation" not in patch
            ]
            == [
                patch["after_hex"]
                for patch in patch_sets["candidate"]
                if "allocation" not in patch
            ],
            "decoded_source_diff_count": len(differing_source_bytes),
        },
    }
    if manifest["pixel_oracle"]["source_tile_differing_pixel_count"] != 50:
        raise ValueError("pixel A/B source tile oracle no longer has 50 pixels")
    if not all(manifest["isolation"].values()):
        raise ValueError("pixel A/B isolation contract failed")
    (output / "build-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_ab_roms(args.root, args.output)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
