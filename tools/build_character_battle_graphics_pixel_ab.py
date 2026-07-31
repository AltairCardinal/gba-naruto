#!/usr/bin/env python3
"""Build topology-identical resource-0 character graphics pixel A/B ROMs."""

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
from tools.import_character_battle_bundles import (
    CATALOG_PATH,
    CATALOG_SHA256,
    ROM_BASE,
    ROM_SHA256,
    SPEC_SCHEMA,
    resolve_character_battle_bundle_patches,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


SCHEMA = "character-battle-graphics-pixel-ab-build-v1"
RESOURCE_ID = 0
SLOT_ROWS = [0]
SOURCE_GRAPHICS_POINTER = "0x0813E090"
SOURCE_GRAPHICS_SHA256 = (
    "00604b6d454b23f73413ec7d65cebead033c7a6177f3e8da9861fb32f44db3ec"
)
GRAPHICS_BYTE_OFFSET = 0xD26
BEFORE = 0x12
AFTER = 0x42
SOURCE_PIXEL = [13, 17]
EXPECTED_SCREEN_PIXEL = [117, 25]
SOURCE_FRAME_ID = 3
SOURCE_COMPONENT_INDEX = 0
SOURCE_TILE_OFFSET = 96
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
        return [-1]
    return [
        index
        for index, pair in enumerate(zip(left, right))
        if pair[0] != pair[1]
    ]


def _spec(
    resource: dict[str, Any],
    graphics_path: Path,
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
                "id": "resource-000-natural-pixel-ab",
                "resource_id": RESOURCE_ID,
                "expected_descriptor": resource["descriptor"],
                "expected_slot_rows": resource["slot_rows"],
                "graphics_file": str(graphics_path),
                "graphics_sha256": _sha256(graphics_path.read_bytes()),
            }
        ],
    }


def _apply(
    base: bytes,
    layout: RomLayout,
    patches: list[dict[str, Any]],
) -> bytes:
    output = bytearray(layout.expanded_base())
    gate = PatchSafetyGate(base, layout=layout)
    for patch in patches:
        apply_patch(output, patch, gate=gate)
    return bytes(output)


def _ledger(patches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for patch in patches:
        allocation = patch.get("allocation")
        kind = "allocation" if allocation is not None else "descriptor"
        rows.append(
            {
                "id": patch["id"],
                "kind": kind,
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


def build_pixel_ab_roms(
    root: Path,
    output: Path,
    *,
    after: int = AFTER,
) -> dict[str, Any]:
    """Build an unchanged relocated baseline and one source-pixel candidate."""

    if after != AFTER:
        raise ValueError("character graphics fixed pixel contract mismatch")
    root = Path(root).resolve()
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("character graphics pixel A/B output directory must be empty")

    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("character graphics pixel A/B base ROM identity mismatch")
    catalog_path = root / CATALOG_PATH
    catalog_bytes = catalog_path.read_bytes()
    if _sha256(catalog_bytes) != CATALOG_SHA256:
        raise ValueError("character graphics pixel A/B catalog identity mismatch")
    catalog = json.loads(catalog_bytes)
    resource = catalog["resources"][RESOURCE_ID]
    source_path = root / "artifacts/character-battle-visuals-v1" / resource["graphics"]["file"]
    source = source_path.read_bytes()
    frame = resource["frames"][SOURCE_FRAME_ID]
    component = frame["components"][SOURCE_COMPONENT_INDEX]
    if (
        resource["resource_id"] != RESOURCE_ID
        or resource["slot_rows"] != SLOT_ROWS
        or resource["descriptor"]["graphics"] != SOURCE_GRAPHICS_POINTER
        or resource["graphics"]["sha256"] != SOURCE_GRAPHICS_SHA256
        or _sha256(source) != SOURCE_GRAPHICS_SHA256
        or frame["frame_id"] != SOURCE_FRAME_ID
        or component["component_index"] != SOURCE_COMPONENT_INDEX
        or component["tile_offset"] != SOURCE_TILE_OFFSET
        or component["width"] != 32
        or component["height"] != 64
        or component["horizontal_flip"]
        or component["vertical_flip"]
    ):
        raise ValueError("character graphics source runtime contract mismatch")
    if source[GRAPHICS_BYTE_OFFSET] != BEFORE:
        raise ValueError("character graphics source pixel byte mismatch")

    output.mkdir(parents=True, exist_ok=True)
    variants: dict[str, dict[str, Any]] = {}
    topologies = []
    roms: dict[str, bytes] = {}
    for variant in VARIANTS:
        variant_dir = output / variant
        variant_dir.mkdir()
        graphics = bytearray(source)
        if variant == "candidate":
            graphics[GRAPHICS_BYTE_OFFSET] = after
        graphics_path = variant_dir / "resource-000-graphics-4bpp.bin"
        graphics_path.write_bytes(graphics)
        spec_path = variant_dir / "spec.json"
        _write_json(spec_path, _spec(resource, graphics_path))
        layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
        patches = resolve_character_battle_bundle_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
        )
        if len(patches) != 2:
            raise ValueError("character graphics pixel A/B patch denominator mismatch")
        rom = _apply(base, layout, patches)
        rom_path = variant_dir / f"{variant}.gba"
        rom_path.write_bytes(rom)
        ledger = _ledger(patches)
        topologies.append(_topology(ledger))
        roms[variant] = rom
        variants[variant] = {
            "rom_path": rom_path.relative_to(output).as_posix(),
            "rom_sha256": _sha256(rom),
            "rom_size": len(rom),
            "graphics_path": graphics_path.relative_to(output).as_posix(),
            "graphics_sha256": _sha256(graphics),
            "spec_path": spec_path.relative_to(output).as_posix(),
            "patch_ledger": ledger,
        }

    shared_patch_topology = topologies[0] == topologies[1]
    changed = _changed_offsets(roms["baseline"], roms["candidate"])
    graphics_pointer = int(
        variants["baseline"]["patch_ledger"][0]["new_pointers"]["graphics"],
        16,
    )
    expected_changed = graphics_pointer - ROM_BASE + GRAPHICS_BYTE_OFFSET
    single_graphics_byte_difference = changed == [expected_changed]
    if not shared_patch_topology or not single_graphics_byte_difference:
        raise ValueError("character graphics pixel A/B isolation mismatch")

    manifest = {
        "schema": SCHEMA,
        "base_rom_sha256": ROM_SHA256,
        "resource": {
            "resource_id": RESOURCE_ID,
            "slot_rows": SLOT_ROWS,
            "source_graphics": SOURCE_GRAPHICS_POINTER,
            "source_graphics_sha256": SOURCE_GRAPHICS_SHA256,
            "source_frame_id": SOURCE_FRAME_ID,
            "source_component_index": SOURCE_COMPONENT_INDEX,
            "source_tile_offset": SOURCE_TILE_OFFSET,
        },
        "edit": {
            "graphics_byte_offset": GRAPHICS_BYTE_OFFSET,
            "before_hex": bytes([BEFORE]).hex(),
            "after_hex": bytes([AFTER]).hex(),
            "source_pixel": SOURCE_PIXEL,
            "expected_screen_pixel": EXPECTED_SCREEN_PIXEL,
            "before_palette_index": 1,
            "after_palette_index": 4,
        },
        "runtime_contract": {
            "input_checkpoint": (
                "artifacts/runtime-checkpoints/scenario-41-start-row.ss9"
            ),
            "input": {
                "key": "A",
                "down_frame": 5,
                "up_frame": 13,
                "hold_frames": 8,
            },
            "capture_frame": 80,
            "expected_oam": {
                "index": 0,
                "screen_x": 104,
                "screen_y": 8,
                "width": 32,
                "height": 64,
                "tile_index": 0,
                "palette_bank": 0,
                "priority": 2,
            },
        },
        "variants": variants,
        "isolation": {
            "shared_patch_topology": shared_patch_topology,
            "single_graphics_byte_difference": single_graphics_byte_difference,
            "rom_difference_offsets": changed,
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
    manifest = build_pixel_ab_roms(args.root, args.output)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
