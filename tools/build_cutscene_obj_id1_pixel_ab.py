#!/usr/bin/env python3
"""Build production-relocated Cutscene OBJ ID 1 one-pixel A/B ROMs."""

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
from tools.import_cutscene_obj_bundle_relocations import (
    CATALOG_PATH,
    CATALOG_SHA256,
    REGION_REGISTRY_PATH,
    ROM_SHA256,
    SPEC_SCHEMA,
    resolve_cutscene_obj_bundle_relocation_patches,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


SCHEMA = "cutscene-obj-id1-pixel-ab-build-v1"
RESOURCE_ID = 1
FRAME_ID = 0
GRAPHICS_BYTE_OFFSET = 82
TILE_ID = 2
TILE_PIXEL_XY = (4, 4)
FRAME_PIXEL_XY = (20, 4)
SCREEN_XY = (60, 52)
BEFORE_BYTE = 0x11
AFTER_BYTE = 0x12
BEFORE_INDEX = 1
AFTER_INDEX = 2
INPUT_STATE = Path("artifacts/runtime-checkpoints/scenario-41-combat-popup.ss9")
INPUT_STATE_SHA256 = (
    "01f478cfafa2796cbe1652007c16e54480d2a289d1e6f54068ace8adc970300a"
)
REFERENCE_POST_STATE = Path(
    "artifacts/runtime-checkpoints/scenario-41-victory.ss9"
)
REFERENCE_POST_STATE_SHA256 = (
    "7a24a7a628c301493418d93e88ab239c0fbb6b77de139a67b91e8e0bcadf6200"
)
FULL_SPEC = Path(
    "artifacts/cutscene-obj-bundle-relocation-v1/full-relocation-spec.json"
)
SOURCE_GRAPHICS = Path(
    "artifacts/cutscene-obj-bundle-relocation-v1/resource_1.4bpp.bin"
)
EXPECTED_SOURCE_SHA256 = (
    "1494d4db49423aaf026f3a1d45df4a63c70db9a0c6c7bae72621f7f7688bae0d"
)
VARIANTS = ("baseline", "candidate")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _changed_offsets(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("Cutscene OBJ ID 1 A/B payload sizes differ")
    return [
        index
        for index, (before, after) in enumerate(zip(left, right))
        if before != after
    ]


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
        after = bytes.fromhex(patch["after_hex"])
        allocation = patch.get("allocation")
        rows.append(
            {
                "id": patch["id"],
                "kind": "allocation" if allocation is not None else "redirect",
                "offset": patch["offset"],
                "size": len(after),
                "after_sha256": _sha256(after),
                "after_hex": None if allocation is not None else patch["after_hex"],
                "allocation": allocation,
                "resource_type": patch.get("resource_type"),
                "resource_id": patch.get("resource_id"),
                "pointer_role": patch.get("pointer_role"),
                "new_pointer": patch.get("new_pointer"),
                "replacement_sha256": patch.get("replacement_sha256"),
                "decompressed_size": patch.get("decompressed_size"),
            }
        )
    return rows


def _topology(ledger: list[dict[str, Any]]) -> list[tuple[object, ...]]:
    return [
        (
            row["id"],
            row["kind"],
            row["offset"],
            row["size"],
            row["resource_type"],
            row["resource_id"],
            row["pointer_role"],
            row["new_pointer"],
        )
        for row in ledger
    ]


def build_pair(root: Path, output: Path) -> dict[str, Any]:
    """Build one preservation baseline and one ID-1 graphics candidate."""

    root = Path(root).resolve()
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Cutscene OBJ ID 1 A/B output directory must be empty")

    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("Cutscene OBJ ID 1 A/B base ROM identity mismatch")
    if _sha256((root / CATALOG_PATH).read_bytes()) != CATALOG_SHA256:
        raise ValueError("Cutscene OBJ ID 1 A/B catalog identity mismatch")
    if _sha256((root / INPUT_STATE).read_bytes()) != INPUT_STATE_SHA256:
        raise ValueError("Cutscene OBJ ID 1 A/B input checkpoint mismatch")
    if (
        _sha256((root / REFERENCE_POST_STATE).read_bytes())
        != REFERENCE_POST_STATE_SHA256
    ):
        raise ValueError("Cutscene OBJ ID 1 A/B reference post-state mismatch")

    baseline_graphics = (root / SOURCE_GRAPHICS).read_bytes()
    if (
        len(baseline_graphics) != 4096
        or _sha256(baseline_graphics) != EXPECTED_SOURCE_SHA256
        or baseline_graphics[GRAPHICS_BYTE_OFFSET] != BEFORE_BYTE
    ):
        raise ValueError("Cutscene OBJ ID 1 source graphics contract mismatch")
    candidate_graphics = bytearray(baseline_graphics)
    candidate_graphics[GRAPHICS_BYTE_OFFSET] = AFTER_BYTE
    candidate_graphics = bytes(candidate_graphics)
    if _changed_offsets(baseline_graphics, candidate_graphics) != [
        GRAPHICS_BYTE_OFFSET
    ]:
        raise ValueError("Cutscene OBJ ID 1 decoded graphics isolation mismatch")

    authored_spec = json.loads((root / FULL_SPEC).read_text(encoding="utf-8"))
    if (
        authored_spec.get("schema") != SPEC_SCHEMA
        or [row.get("id") for row in authored_spec.get("resources", [])]
        != [0, 1, 2, 3]
    ):
        raise ValueError("Cutscene OBJ ID 1 parent spec contract mismatch")

    output.mkdir(parents=True, exist_ok=True)
    layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    regions = ImageResourceRegions.from_path(
        root / REGION_REGISTRY_PATH, layout
    )
    variants: dict[str, dict[str, Any]] = {}
    roms: dict[str, bytes] = {}
    for variant in VARIANTS:
        variant_dir = output / variant
        variant_dir.mkdir()
        graphics_path = variant_dir / "resource_1.4bpp.bin"
        graphics = (
            baseline_graphics if variant == "baseline" else candidate_graphics
        )
        graphics_path.write_bytes(graphics)

        spec = json.loads(json.dumps(authored_spec))
        spec["resources"][RESOURCE_ID]["graphics_file"] = str(graphics_path)
        spec_path = variant_dir / "spec.json"
        _write_json(spec_path, spec)
        patches = resolve_cutscene_obj_bundle_relocation_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
        ledger = _ledger(patches)
        graphics_patch = next(
            row
            for row in ledger
            if row["kind"] == "allocation"
            and row["resource_id"] == RESOURCE_ID
            and row["resource_type"] == "graphics"
        )
        if (
            len(patches) != 28
            or graphics_patch["decompressed_size"] != len(graphics)
            or graphics_patch["replacement_sha256"] != _sha256(graphics)
        ):
            raise ValueError("Cutscene OBJ ID 1 patch topology mismatch")
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
            "encoded_graphics_size": graphics_patch["size"],
            "graphics_allocation_offset": graphics_patch["offset"],
            "patch_ledger": ledger,
        }

    baseline_ledger = variants["baseline"]["patch_ledger"]
    candidate_ledger = variants["candidate"]["patch_ledger"]
    same_topology = _topology(baseline_ledger) == _topology(candidate_ledger)
    same_allocations = [
        row["offset"] for row in baseline_ledger if row["kind"] == "allocation"
    ] == [
        row["offset"] for row in candidate_ledger if row["kind"] == "allocation"
    ]
    same_redirects = [
        (row["offset"], row["after_hex"], row["new_pointer"])
        for row in baseline_ledger
        if row["kind"] == "redirect"
    ] == [
        (row["offset"], row["after_hex"], row["new_pointer"])
        for row in candidate_ledger
        if row["kind"] == "redirect"
    ]
    if not (same_topology and same_allocations and same_redirects):
        raise ValueError("Cutscene OBJ ID 1 A/B bundle topology changed")

    allocation_offset = variants["baseline"]["graphics_allocation_offset"]
    allocation_size = variants["baseline"]["encoded_graphics_size"]
    rom_differences = _changed_offsets(roms["baseline"], roms["candidate"])
    if not rom_differences or any(
        not allocation_offset <= offset < allocation_offset + allocation_size
        for offset in rom_differences
    ):
        raise ValueError("Cutscene OBJ ID 1 encoded ROM isolation mismatch")

    manifest = {
        "schema": SCHEMA,
        "base_rom_sha256": ROM_SHA256,
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": CATALOG_SHA256,
        "input_state": INPUT_STATE.as_posix(),
        "input_state_sha256": INPUT_STATE_SHA256,
        "reference_post_state": REFERENCE_POST_STATE.as_posix(),
        "reference_post_state_sha256": REFERENCE_POST_STATE_SHA256,
        "input": {
            "key": "A",
            "down_frame": 5,
            "up_frame": 13,
            "capture_frame": 512,
        },
        "edit": {
            "resource_id": RESOURCE_ID,
            "frame_id": FRAME_ID,
            "graphics_byte_offset": GRAPHICS_BYTE_OFFSET,
            "tile_id": TILE_ID,
            "tile_pixel_xy": list(TILE_PIXEL_XY),
            "frame_pixel_xy": list(FRAME_PIXEL_XY),
            "before_byte": BEFORE_BYTE,
            "after_byte": AFTER_BYTE,
            "before_index": BEFORE_INDEX,
            "after_index": AFTER_INDEX,
            "screen_xy": list(SCREEN_XY),
        },
        "isolation": {
            "decoded_graphics_offsets": [GRAPHICS_BYTE_OFFSET],
            "same_patch_topology": same_topology,
            "same_allocation_offsets": same_allocations,
            "same_redirect_pointers": same_redirects,
            "rom_changed_offsets": rom_differences,
            "rom_changed_offset_count": len(rom_differences),
            "changed_rom_span": [
                min(rom_differences),
                max(rom_differences) + 1,
            ],
        },
        "variants": variants,
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
