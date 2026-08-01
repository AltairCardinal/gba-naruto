#!/usr/bin/env python3
"""Build production-relocated battle-effect group 5 one-pixel A/B ROMs."""

from __future__ import annotations

import argparse
import hashlib
import json
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
from tools.import_battle_effect_resource_relocations import (
    REGION_REGISTRY_PATH,
    SPEC_SCHEMA,
    resolve_battle_effect_resource_relocation_patches,
)
from tools.import_battle_effect_resources import (
    CATALOG_PATH,
    CATALOG_SHA256,
    ROM_SHA256,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


SCHEMA = "battle-effect-group5-pixel-ab-build-v1"
GROUP_ID = 5
SEQUENCE_ID = 6
FRAME_ID = 1
GRAPHICS_BYTE_OFFSET = 0x200
TILE_ID = 16
TILE_PIXEL_XY = (0, 0)
FRAME_PIXEL_XY = (0, 0)
SCREEN_XY = (160, 48)
BEFORE_BYTE = 0x02
AFTER_BYTE = 0x04
BEFORE_INDEX = 2
AFTER_INDEX = 4
PAIR_POINTER_OFFSET = 0x599144
GRAPHICS_ALLOCATION_OFFSET = 0xB40000
SOURCE_GRAPHICS = Path(
    "artifacts/battle-effect-resource-pairs-v1/group-05-graphics-4bpp.bin"
)
SOURCE_GRAPHICS_SHA256 = (
    "6628fdc3365f8d6f16b134797be5f9a1c7cb48662ffeeea634ace058c659bb32"
)
FULL_SPEC = Path(
    "artifacts/battle-effect-resource-relocation-v1/full-relocation-spec.json"
)
INPUT_STATE = Path(
    "artifacts/runtime-checkpoints/scenario-41-attack-confirmation.ss9"
)
INPUT_STATE_SHA256 = (
    "544cffbaea182a55d1963447965d95750984a915cae9877d66d6bc3aebbd560f"
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
        raise ValueError("battle-effect group 5 A/B payload sizes differ")
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
        allocation = patch.get("allocation")
        after = bytes.fromhex(patch["after_hex"])
        rows.append(
            {
                "id": patch["id"],
                "kind": "allocation" if allocation is not None else "redirect",
                "asset_type": patch["asset_type"],
                "resource_type": patch["resource_type"],
                "resource_sha256": patch["resource_sha256"],
                "replacement_sha256": patch.get("replacement_sha256"),
                "offset": patch["offset"],
                "size": len(after),
                "after_sha256": _sha256(after),
                "after_hex": None if allocation is not None else patch["after_hex"],
                "new_pointer": patch["new_pointer"],
                "target_pointer_offsets": patch["target_pointer_offsets"],
                "allocation": allocation,
                "decompressed_size": patch.get("decompressed_size"),
            }
        )
    return rows


def _topology(ledger: list[dict[str, Any]]) -> list[tuple[object, ...]]:
    return [
        (
            row["id"],
            row["kind"],
            row["asset_type"],
            row["resource_type"],
            row["offset"],
            row["size"],
            row["new_pointer"],
            tuple(row["target_pointer_offsets"]),
        )
        for row in ledger
    ]


def build_pair(root: Path, output: Path) -> dict[str, Any]:
    """Build one preservation baseline and one group-5 graphics candidate."""

    root = Path(root).resolve()
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("battle-effect group 5 A/B output directory must be empty")

    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("battle-effect group 5 A/B base ROM identity mismatch")
    if _sha256((root / CATALOG_PATH).read_bytes()) != CATALOG_SHA256:
        raise ValueError("battle-effect group 5 A/B catalog identity mismatch")
    if _sha256((root / INPUT_STATE).read_bytes()) != INPUT_STATE_SHA256:
        raise ValueError("battle-effect group 5 A/B input checkpoint mismatch")

    baseline_graphics = (root / SOURCE_GRAPHICS).read_bytes()
    if (
        len(baseline_graphics) != 3840
        or _sha256(baseline_graphics) != SOURCE_GRAPHICS_SHA256
        or baseline_graphics[GRAPHICS_BYTE_OFFSET] != BEFORE_BYTE
    ):
        raise ValueError("battle-effect group 5 source graphics contract mismatch")
    candidate_graphics = bytearray(baseline_graphics)
    candidate_graphics[GRAPHICS_BYTE_OFFSET] = AFTER_BYTE
    candidate_graphics = bytes(candidate_graphics)
    if _changed_offsets(baseline_graphics, candidate_graphics) != [
        GRAPHICS_BYTE_OFFSET
    ]:
        raise ValueError("battle-effect group 5 decoded graphics isolation mismatch")

    parent_spec = json.loads((root / FULL_SPEC).read_text(encoding="utf-8"))
    source_edit = next(
        (
            row
            for row in parent_spec.get("edits", [])
            if row.get("resource_type") == "graphics"
            and row.get("resource_sha256") == SOURCE_GRAPHICS_SHA256
        ),
        None,
    )
    if parent_spec.get("schema") != SPEC_SCHEMA or source_edit is None:
        raise ValueError("battle-effect group 5 parent spec contract mismatch")

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
        graphics = (
            baseline_graphics if variant == "baseline" else candidate_graphics
        )
        graphics_path = variant_dir / "group-05-graphics-4bpp.bin"
        graphics_path.write_bytes(graphics)

        spec = {key: value for key, value in parent_spec.items() if key != "edits"}
        edit = json.loads(json.dumps(source_edit))
        edit["id"] = f"group-05-graphics-pixel-ab-{variant}"
        edit["source_file"] = str(graphics_path)
        spec["edits"] = [edit]
        spec_path = variant_dir / "spec.json"
        _write_json(spec_path, spec)

        patches = resolve_battle_effect_resource_relocation_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
        ledger = _ledger(patches)
        if (
            len(ledger) != 2
            or ledger[0]["kind"] != "allocation"
            or ledger[0]["offset"] != GRAPHICS_ALLOCATION_OFFSET
            or ledger[0]["size"] != 1165
            or ledger[0]["decompressed_size"] != 3840
            or ledger[0]["replacement_sha256"] != _sha256(graphics)
            or ledger[1]["kind"] != "redirect"
            or ledger[1]["offset"] != PAIR_POINTER_OFFSET
        ):
            raise ValueError("battle-effect group 5 patch topology mismatch")

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
            "encoded_graphics_size": ledger[0]["size"],
            "graphics_allocation_offset": ledger[0]["offset"],
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
        raise ValueError("battle-effect group 5 A/B relocation topology changed")

    rom_differences = _changed_offsets(roms["baseline"], roms["candidate"])
    encoded_size = variants["baseline"]["encoded_graphics_size"]
    if not rom_differences or any(
        not GRAPHICS_ALLOCATION_OFFSET
        <= offset
        < GRAPHICS_ALLOCATION_OFFSET + encoded_size
        for offset in rom_differences
    ):
        raise ValueError("battle-effect group 5 encoded ROM isolation mismatch")

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
            "capture_frame": 150,
        },
        "edit": {
            "group_id": GROUP_ID,
            "sequence_id": SEQUENCE_ID,
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
        "runtime_contract": {
            "obj_vram_address": "0x06012400",
            "obj_tile_base": 288,
            "palette_bank": 5,
            "oam_index": 1,
            "oam_attributes": ["0x0030", "0x80A0", "0x5930"],
            "before_rgb": [255, 222, 198],
            "after_rgb": [189, 123, 115],
        },
        "isolation": {
            "decoded_offsets": [GRAPHICS_BYTE_OFFSET],
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
