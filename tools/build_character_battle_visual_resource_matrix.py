#!/usr/bin/env python3
"""Build topology-identical character palette/component/timeline A/B ROMs."""

from __future__ import annotations

import argparse
import copy
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
from tools.import_character_battle_bundles import (
    CATALOG_PATH,
    CATALOG_SHA256,
    ROM_SHA256,
    SPEC_SCHEMA,
    resolve_character_battle_bundle_patches,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


SCHEMA = "character-battle-visual-resource-matrix-build-v1"
RESOURCE_ID = 0
VARIANTS = ("baseline", "palette", "component", "timeline")
BUNDLE_OFFSET = 0x600000
BUNDLE_SIZE = 0x4B60
DESCRIPTOR_OFFSET = 0x596D5C
EXPECTED_EDITS = {
    "palette": {
        "bundle_local_offset": 0x2,
        "before_hex": "84",
        "after_hex": "85",
        "palette_index": 1,
    },
    "component": {
        "bundle_local_offset": 0x486C,
        "before_hex": "f0",
        "after_hex": "f1",
        "frame_id": 3,
        "component_index": 0,
        "field": "x",
        "before": -16,
        "after": -15,
    },
    "timeline": {
        "bundle_local_offset": 0x4A64,
        "before_hex": "03",
        "after_hex": "04",
        "animation_id": 1,
        "keyframe_index": 0,
        "field": "frame_id",
        "before": 3,
        "after": 4,
    },
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _changed_offsets(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        return [-1]
    return [
        index
        for index, pair in enumerate(zip(left, right))
        if pair[0] != pair[1]
    ]


def _frames(resource: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "components": [
                {
                    key: component[key]
                    for key in (
                        "tile_offset",
                        "orientation",
                        "x",
                        "y",
                        "width",
                        "height",
                    )
                }
                for component in frame["components"]
            ]
        }
        for frame in resource["frames"]
    ]


def _animations(resource: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "keyframes": [
                {
                    "frame_id": keyframe["frame_id"],
                    "hold_frames": keyframe["hold_frames"],
                }
                for keyframe in animation["keyframes"]
            ]
        }
        for animation in resource["animations"]
    ]


def _spec(
    resource: dict[str, Any],
    graphics_path: Path,
    palette_path: Path,
    frames: list[dict[str, Any]],
    animations: list[dict[str, Any]],
    variant: str,
) -> dict[str, Any]:
    return {
        "schema": SPEC_SCHEMA,
        "base_rom_sha256": ROM_SHA256,
        "catalog": CATALOG_PATH.as_posix(),
        "catalog_sha256": CATALOG_SHA256,
        "partition": "character-battle-visual-bundles",
        "owner": "character_battle_visuals",
        "edits": [
            {
                "id": f"resource-000-visual-matrix-{variant}",
                "resource_id": RESOURCE_ID,
                "expected_descriptor": resource["descriptor"],
                "expected_slot_rows": resource["slot_rows"],
                "graphics_file": str(graphics_path),
                "graphics_sha256": _sha256(graphics_path.read_bytes()),
                "palette_file": str(palette_path),
                "palette_sha256": _sha256(palette_path.read_bytes()),
                "frames": frames,
                "animations": animations,
            }
        ],
    }


def _apply(base: bytes, layout: RomLayout, patches: list[dict[str, Any]]) -> bytes:
    output = bytearray(layout.expanded_base())
    gate = PatchSafetyGate(base, layout=layout)
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
                "kind": "allocation" if allocation is not None else "descriptor",
                "offset": patch["offset"],
                "size": len(bytes.fromhex(patch["after_hex"])),
                "before_sha256": _sha256(bytes.fromhex(patch["before_hex"])),
                "after_sha256": _sha256(bytes.fromhex(patch["after_hex"])),
                "resource_id": patch["resource_id"],
                "slot_row": patch.get("slot_row"),
                "new_pointers": patch["new_pointers"],
                "allocation": allocation,
            }
        )
    return rows


def _topology(ledger: list[dict[str, Any]]) -> list[tuple[object, ...]]:
    return [
        (
            row["kind"],
            row["offset"],
            row["size"],
            row["resource_id"],
            row["slot_row"],
            tuple(sorted(row["new_pointers"].items())),
        )
        for row in ledger
    ]


def build_matrix(
    root: Path,
    output: Path,
    *,
    variants: tuple[str, ...] = VARIANTS,
) -> dict[str, Any]:
    """Build one preservation baseline and three single-factor candidates."""

    if variants != VARIANTS:
        raise ValueError("character visual matrix variant contract mismatch")
    root = Path(root).resolve()
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("character visual matrix output directory must be empty")

    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("character visual matrix base ROM identity mismatch")
    catalog_path = root / CATALOG_PATH
    catalog_bytes = catalog_path.read_bytes()
    if _sha256(catalog_bytes) != CATALOG_SHA256:
        raise ValueError("character visual matrix catalog identity mismatch")
    resource = json.loads(catalog_bytes)["resources"][RESOURCE_ID]
    if (
        resource["resource_id"] != 0
        or resource["slot_rows"] != [0]
        or resource["descriptor"]["graphics"] != "0x0813E090"
        or resource["frames"][3]["components"][0]["x"] != -16
        or resource["frames"][3]["components"][0]["tile_offset"] != 96
        or resource["animations"][1]["keyframes"][0]
        != {"frame_id": 3, "hold_frames": 8}
    ):
        raise ValueError("character visual matrix source contract mismatch")

    source_root = root / "artifacts/character-battle-visuals-v1"
    source_graphics = (source_root / resource["graphics"]["file"]).read_bytes()
    source_palette = (source_root / resource["palette"]["file"]).read_bytes()
    if (
        _sha256(source_graphics) != resource["graphics"]["sha256"]
        or _sha256(source_palette) != resource["palette"]["sha256"]
        or source_palette[2] != 0x84
    ):
        raise ValueError("character visual matrix source payload mismatch")

    output.mkdir(parents=True, exist_ok=True)
    roms: dict[str, bytes] = {}
    result_variants: dict[str, dict[str, Any]] = {}
    topologies = []
    for variant in VARIANTS:
        variant_dir = output / variant
        variant_dir.mkdir()
        graphics_path = variant_dir / "graphics-4bpp.bin"
        graphics_path.write_bytes(source_graphics)
        palette = bytearray(source_palette)
        frames = _frames(resource)
        animations = _animations(resource)
        if variant == "palette":
            palette[2] = 0x85
        elif variant == "component":
            frames[3]["components"][0]["x"] = -15
        elif variant == "timeline":
            animations[1]["keyframes"][0]["frame_id"] = 4
        palette_path = variant_dir / "palette-bgr555.bin"
        palette_path.write_bytes(palette)
        spec_path = variant_dir / "spec.json"
        _write_json(
            spec_path,
            _spec(
                resource,
                graphics_path,
                palette_path,
                frames,
                animations,
                variant,
            ),
        )
        layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
        patches = resolve_character_battle_bundle_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
        )
        if len(patches) != 2:
            raise ValueError("character visual matrix patch denominator mismatch")
        rom = _apply(base, layout, patches)
        rom_path = variant_dir / f"{variant}.gba"
        rom_path.write_bytes(rom)
        ledger = _ledger(patches)
        topologies.append(_topology(ledger))
        roms[variant] = rom
        result_variants[variant] = {
            "rom_path": rom_path.relative_to(output).as_posix(),
            "rom_sha256": _sha256(rom),
            "rom_size": len(rom),
            "spec_path": spec_path.relative_to(output).as_posix(),
            "graphics_sha256": _sha256(source_graphics),
            "palette_sha256": _sha256(palette),
            "patch_ledger": ledger,
        }

    shared_patch_topology = all(row == topologies[0] for row in topologies[1:])
    differences = {
        variant: _changed_offsets(roms["baseline"], roms[variant])
        for variant in VARIANTS[1:]
    }
    expected_differences = {
        variant: [BUNDLE_OFFSET + EXPECTED_EDITS[variant]["bundle_local_offset"]]
        for variant in VARIANTS[1:]
    }
    single_byte_candidates = differences == expected_differences
    if not shared_patch_topology or not single_byte_candidates:
        raise ValueError("character visual matrix isolation mismatch")
    if any(
        len(rom[BUNDLE_OFFSET : BUNDLE_OFFSET + BUNDLE_SIZE]) != BUNDLE_SIZE
        or rom[DESCRIPTOR_OFFSET : DESCRIPTOR_OFFSET + 16]
        != roms["baseline"][DESCRIPTOR_OFFSET : DESCRIPTOR_OFFSET + 16]
        for rom in roms.values()
    ):
        raise ValueError("character visual matrix bundle topology mismatch")

    manifest = {
        "schema": SCHEMA,
        "base_rom_sha256": ROM_SHA256,
        "resource": {
            "resource_id": 0,
            "character_id": 1,
            "visual_slot": 0,
            "slot_rows": [0],
            "frame_id": 3,
            "component_index": 0,
            "animation_id": 1,
            "keyframe_index": 0,
        },
        "edits": EXPECTED_EDITS,
        "runtime_contract": {
            "input_checkpoint": "artifacts/runtime-checkpoints/scenario-41-start-row.ss9",
            "input": {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8},
            "capture_frame": 80,
            "baseline_active_task": {
                "task_address": "0x0300597C",
                "animation_id": 1,
                "keyframe_index": 0,
                "frame_id": 3,
            },
        },
        "variants": result_variants,
        "isolation": {
            "shared_patch_topology": shared_patch_topology,
            "single_byte_candidates": single_byte_candidates,
            "rom_difference_offsets": differences,
            "independent_runtime_required": True,
        },
    }
    _write_json(output / "build-manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_matrix(args.root, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
