#!/usr/bin/env python3
"""Build four topology-identical ROMs for map-41 visual resource A/B."""

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
from tools.extract_tileset import lz77_decompress
from tools.image_resource_regions import ImageResourceRegions
from tools.import_map_resource_relocations import (
    REGION_REGISTRY_PATH,
    ROM_BASE,
    SPEC_SCHEMA,
    catalog_map_resource_relocations,
    resolve_map_resource_relocation_patches,
)
from tools.import_map_resources import CATALOG_PATH, ROM_SHA256
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


SCHEMA = "map41-visual-resource-matrix-build-v1"
MAP_ID = 41
VARIANT_NAMES = (
    "baseline",
    "tile_graphics",
    "bg_palette",
    "metatile_definitions",
)
RESOURCE_TYPES = VARIANT_NAMES[1:]
RESOURCE_CONTRACTS: dict[str, dict[str, Any]] = {
    "tile_graphics": {
        "source_sha256": (
            "f7d4ac8b041bfcd7d5f1a2103e3402185fd57a35651a0f1d75e47e48d47a44c2"
        ),
        "source_pointer": 0x0811B4E0,
        "source_size": 12288,
        "physical_offsets": [
            0x115760,
            0x118620,
            0x11B4E0,
            0x11E3A0,
            0x121260,
            0x124120,
            0x126FE0,
        ],
        "header_pointer_offsets": [
            0x53DDF4,
            0x53DE14,
            0x53DE34,
            0x53DE54,
            0x53DE74,
            0x53DE94,
            0x53DEB4,
        ],
        "target_header_pointer_offset": 0x53DE34,
        "decoded_byte_offset": 0x2A20,
        "before": 0x34,
        "after": 0x35,
    },
    "bg_palette": {
        "source_sha256": (
            "3c86d041724735cc717fedffe8cca91ac9d717b7878c2296672e295eb12923e4"
        ),
        "source_pointer": 0x0811DC1C,
        "source_size": 384,
        "physical_offsets": [
            0x0C166C,
            0x0C416C,
            0x0C5F24,
            0x0C8454,
            0x0EA0F4,
            0x0EF448,
            0x0F584C,
            0x117E9C,
            0x11AD5C,
            0x11DC1C,
            0x120ADC,
            0x12399C,
            0x12685C,
            0x12971C,
        ],
        "header_pointer_offsets": [
            0x53D938,
            0x53D958,
            0x53D978,
            0x53D998,
            0x53DAD8,
            0x53DB18,
            0x53DB58,
            0x53DD38,
            0x53DDF8,
            0x53DE18,
            0x53DE38,
            0x53DE58,
            0x53DE78,
            0x53DE98,
            0x53DEB8,
        ],
        "target_header_pointer_offset": 0x53DE38,
        "decoded_byte_offset": 0x4A,
        "before": 0x0D,
        "after": 0x0C,
    },
    "metatile_definitions": {
        "source_sha256": (
            "f557bf169836e7b1abdf2e6fac94887f0f50b9293a9976eb8e7c93d64e3bb3db"
        ),
        "source_pointer": 0x0811DEB4,
        "source_size": 1376,
        "physical_offsets": [
            0x118134,
            0x11AFF4,
            0x11DEB4,
            0x120D74,
            0x123C34,
            0x126AF4,
            0x1299B4,
        ],
        "header_pointer_offsets": [
            0x53DE04,
            0x53DE24,
            0x53DE44,
            0x53DE64,
            0x53DE84,
            0x53DEA4,
            0x53DEC4,
        ],
        "target_header_pointer_offset": 0x53DE44,
        "decoded_byte_offset": 0x230,
        "before": 0x19,
        "after": 0x1A,
    },
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex32(value: int) -> str:
    return f"0x{value:08X}"


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
    root: Path,
    resources: dict[str, dict[str, Any]],
    contents: dict[str, Path],
) -> dict[str, Any]:
    catalog = root / CATALOG_PATH
    registry = root / REGION_REGISTRY_PATH
    return {
        "schema": SPEC_SCHEMA,
        "base_rom_sha256": ROM_SHA256,
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": _sha256(catalog.read_bytes()),
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGION_REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256(registry.read_bytes()),
        "region": "map-resources",
        "region_owner": "map_resources",
        "edits": [
            {
                "id": f"map41-visual-matrix-{resource_type}",
                "resource_type": resource_type,
                "source_sha256": RESOURCE_CONTRACTS[resource_type][
                    "source_sha256"
                ],
                "expected_physical_offsets": resource["physical_offsets"],
                "expected_header_pointer_offsets": [
                    alias["header_pointer_offset"]
                    for alias in resource["logical_aliases"]
                ],
                "target_header_pointer_offsets": [
                    RESOURCE_CONTRACTS[resource_type][
                        "target_header_pointer_offset"
                    ]
                ],
                "content_file": str(contents[resource_type]),
                "content_sha256": _sha256(
                    contents[resource_type].read_bytes()
                ),
            }
            for resource_type, resource in resources.items()
        ],
    }


def _apply_patches(
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
            "resource_type": patch["resource_type"],
            "source_sha256": patch["source_sha256"],
            "replacement_sha256": patch["replacement_sha256"],
            "source_size": patch["source_size"],
            "replacement_size": patch["replacement_size"],
            "new_pointer": patch["new_pointer"],
            "all_header_pointer_offsets": patch[
                "all_header_pointer_offsets"
            ],
            "target_header_pointer_offsets": patch[
                "target_header_pointer_offsets"
            ],
        }
        for patch in patches
    ]


def _topology(ledger: list[dict[str, Any]]) -> list[tuple[object, ...]]:
    return [
        (
            patch["kind"],
            patch["offset"],
            patch["resource_type"],
            tuple(patch["target_header_pointer_offsets"]),
            patch["new_pointer"],
            len(patch["after_hex"]),
        )
        for patch in ledger
    ]


def build_matrix_roms(
    root: Path,
    output: Path,
    *,
    tile_graphics_after: int = 0x35,
    bg_palette_after: int = 0x0C,
    metatile_definitions_after: int = 0x1A,
) -> dict[str, Any]:
    """Build one preservation baseline and three single-factor candidates."""

    requested_after = {
        "tile_graphics": tile_graphics_after,
        "bg_palette": bg_palette_after,
        "metatile_definitions": metatile_definitions_after,
    }
    if any(
        requested_after[resource_type] != contract["after"]
        for resource_type, contract in RESOURCE_CONTRACTS.items()
    ):
        raise ValueError("map41 visual fixed matrix contract mismatch")

    root = Path(root).resolve()
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("map41 visual matrix output directory must be empty")
    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("map41 visual matrix base ROM identity mismatch")
    layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    regions = ImageResourceRegions.from_path(
        root / REGION_REGISTRY_PATH,
        layout,
    )
    catalog = catalog_map_resource_relocations(root, base)
    resources: dict[str, dict[str, Any]] = {}
    for resource_type, contract in RESOURCE_CONTRACTS.items():
        resource = catalog[(resource_type, contract["source_sha256"])]
        headers = [
            alias["header_pointer_offset"]
            for alias in resource["logical_aliases"]
        ]
        target_aliases = [
            alias
            for alias in resource["logical_aliases"]
            if alias["header_pointer_offset"]
            == contract["target_header_pointer_offset"]
        ]
        if (
            resource["physical_offsets"] != contract["physical_offsets"]
            or headers != contract["header_pointer_offsets"]
            or len(resource["source_content"]) != contract["source_size"]
            or target_aliases != [
                {
                    "map_id": MAP_ID,
                    "resource_type": resource_type,
                    "header_pointer_offset": contract[
                        "target_header_pointer_offset"
                    ],
                    "physical_offset": contract["source_pointer"] - ROM_BASE,
                }
            ]
        ):
            raise ValueError(
                f"map41 {resource_type} catalog alias contract mismatch"
            )
        source = resource["source_content"]
        if source[contract["decoded_byte_offset"]] != contract["before"]:
            raise ValueError(
                f"map41 {resource_type} source edit contract mismatch"
            )
        resources[resource_type] = resource

    output.mkdir(parents=True, exist_ok=True)
    variants: dict[str, dict[str, Any]] = {}
    topologies: list[list[tuple[object, ...]]] = []
    pointer_sets: list[tuple[str, ...]] = []
    only_map41_headers_redirected = True
    for variant_name in VARIANT_NAMES:
        variant_dir = output / variant_name
        variant_dir.mkdir()
        content_paths: dict[str, Path] = {}
        expected_contents: dict[str, bytes] = {}
        for resource_type, resource in resources.items():
            content = bytearray(resource["source_content"])
            contract = RESOURCE_CONTRACTS[resource_type]
            if variant_name == resource_type:
                content[contract["decoded_byte_offset"]] = contract["after"]
            content_path = variant_dir / f"{resource_type}.bin"
            content_path.write_bytes(content)
            content_paths[resource_type] = content_path
            expected_contents[resource_type] = bytes(content)

        spec_path = variant_dir / "spec.json"
        _write_json(spec_path, _spec(root, resources, content_paths))
        patches = resolve_map_resource_relocation_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
        if len(patches) != 6:
            raise ValueError("map41 visual matrix patch denominator mismatch")
        rom = _apply_patches(base, layout, regions, patches)
        rom_path = variant_dir / f"{variant_name}.gba"
        rom_path.write_bytes(rom)
        ledger = _patch_ledger(patches)
        topologies.append(_topology(ledger))
        pointer_sets.append(
            tuple(
                next(
                    patch["new_pointer"]
                    for patch in ledger
                    if patch["kind"] == "allocation"
                    and patch["resource_type"] == resource_type
                )
                for resource_type in RESOURCE_TYPES
            )
        )

        decoded_sha256: dict[str, str] = {}
        for resource_type, expected in expected_contents.items():
            pointer = int(pointer_sets[-1][RESOURCE_TYPES.index(resource_type)], 16)
            decoded = lz77_decompress(rom, pointer - ROM_BASE)
            if decoded != expected:
                raise ValueError(
                    f"{variant_name} relocated {resource_type} content mismatch"
                )
            decoded_sha256[resource_type] = _sha256(decoded)
            contract = RESOURCE_CONTRACTS[resource_type]
            preserved = [
                offset
                for offset in contract["header_pointer_offsets"]
                if offset != contract["target_header_pointer_offset"]
            ]
            if any(
                rom[offset : offset + 4] != base[offset : offset + 4]
                for offset in preserved
            ):
                only_map41_headers_redirected = False

        variants[variant_name] = {
            "rom_path": rom_path.relative_to(output).as_posix(),
            "rom_sha256": _sha256(rom),
            "rom_size": len(rom),
            "spec_path": spec_path.relative_to(output).as_posix(),
            "decoded_sha256": decoded_sha256,
            "patch_ledger": ledger,
        }

    shared_patch_topology = all(
        topology == topologies[0] for topology in topologies
    ) and all(pointers == pointer_sets[0] for pointers in pointer_sets)
    if not shared_patch_topology:
        raise ValueError(
            "map41 visual matrix candidates do not share patch topology; "
            "build independent A/B pairs instead"
        )
    baseline_contents = {
        resource_type: (
            output / "baseline" / f"{resource_type}.bin"
        ).read_bytes()
        for resource_type in RESOURCE_TYPES
    }
    expected_variant_diffs = {
        "baseline": {},
        **{
            resource_type: {
                resource_type: [
                    RESOURCE_CONTRACTS[resource_type]["decoded_byte_offset"]
                ]
            }
            for resource_type in RESOURCE_TYPES
        },
    }
    for variant_name in VARIANT_NAMES:
        for resource_type in RESOURCE_TYPES:
            actual = _changed_offsets(
                baseline_contents[resource_type],
                (output / variant_name / f"{resource_type}.bin").read_bytes(),
            )
            if actual != expected_variant_diffs[variant_name].get(
                resource_type, []
            ):
                raise ValueError(
                    f"{variant_name} {resource_type} single-factor isolation mismatch"
                )

    manifest = {
        "schema": SCHEMA,
        "base_rom_sha256": ROM_SHA256,
        "map_id": MAP_ID,
        "resources": {
            resource_type: {
                "source_sha256": contract["source_sha256"],
                "source_pointer": _hex32(contract["source_pointer"]),
                "source_size": contract["source_size"],
                "physical_offsets": contract["physical_offsets"],
                "all_header_pointer_offsets": contract[
                    "header_pointer_offsets"
                ],
                "target_header_pointer_offset": contract[
                    "target_header_pointer_offset"
                ],
                "preserved_header_pointer_offsets": [
                    offset
                    for offset in contract["header_pointer_offsets"]
                    if offset != contract["target_header_pointer_offset"]
                ],
            }
            for resource_type, contract in RESOURCE_CONTRACTS.items()
        },
        "edits": {
            resource_type: {
                "source_pointer": _hex32(contract["source_pointer"]),
                "target_header_pointer_offset": _hex32(
                    contract["target_header_pointer_offset"]
                ),
                "decoded_byte_offsets": [contract["decoded_byte_offset"]],
                "before_hex": bytes([contract["before"]]).hex(),
                "after_hex": bytes([contract["after"]]).hex(),
            }
            for resource_type, contract in RESOURCE_CONTRACTS.items()
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
            "tile_graphics_vram_base": "0x06004000",
            "bg_palette_pram_base": "0x05000000",
            "metatile_ewram_base": "0x0201DE2C",
        },
        "variants": variants,
        "isolation": {
            "shared_patch_topology": shared_patch_topology,
            "only_map41_headers_redirected": only_map41_headers_redirected,
            "independent_runtime_required": True,
        },
    }
    if not only_map41_headers_redirected:
        raise ValueError("map41 visual matrix changed a preserved header")
    _write_json(output / "build-manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_matrix_roms(args.root, args.output)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
