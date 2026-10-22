#!/usr/bin/env python3
"""Build an alias-isolated map-41 primary-layout pixel A/B ROM pair."""

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


SCHEMA = "map41-primary-layout-pixel-ab-build-v1"
RESOURCE_TYPE = "primary_layout"
SOURCE_SHA256 = "950f9555a8b12c73b3c3fdabb50209917b849972ff1ee6c3e5b80ead5d472f6f"
MAP_ID = 41
MAP41_SOURCE_POINTER = 0x0811DCC0
TARGET_HEADER_POINTER_OFFSET = 0x53DE3C
EXPECTED_PHYSICAL_OFFSETS = [
    0x117F40,
    0x11AE00,
    0x11DCC0,
    0x120B80,
    0x123A40,
    0x126900,
    0x1297C0,
]
EXPECTED_HEADER_POINTER_OFFSETS = [
    0x53DDFC,
    0x53DE1C,
    0x53DE3C,
    0x53DE5C,
    0x53DE7C,
    0x53DE9C,
    0x53DEBC,
]
COARSE_WIDTH = 9
COARSE_X = 1
COARSE_Y = 6
DECODED_BYTE_OFFSET = 0xDC
BEFORE_WORD = 0x00350022
AFTER_WORD = 0x00220035
RUNTIME_EWRAM_BASE = 0x0201BE2C


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex32(value: int) -> str:
    return f"0x{value:08X}"


def _spec(root: Path, resource: dict[str, Any], content: Path) -> dict[str, Any]:
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
                "id": "map41-primary-layout-pixel-ab",
                "resource_type": RESOURCE_TYPE,
                "source_sha256": SOURCE_SHA256,
                "expected_physical_offsets": resource["physical_offsets"],
                "expected_header_pointer_offsets": [
                    alias["header_pointer_offset"]
                    for alias in resource["logical_aliases"]
                ],
                "target_header_pointer_offsets": [
                    TARGET_HEADER_POINTER_OFFSET
                ],
                "content_file": str(content),
                "content_sha256": _sha256(content.read_bytes()),
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
            "new_pointer": patch["new_pointer"],
            "target_header_pointer_offsets": patch[
                "target_header_pointer_offsets"
            ],
        }
        for patch in patches
    ]


def build_ab_roms(
    root: Path,
    output: Path,
    *,
    coarse_x: int = COARSE_X,
    coarse_y: int = COARSE_Y,
    replacement_word: int = AFTER_WORD,
) -> dict[str, Any]:
    root = Path(root).resolve()
    output = Path(output).resolve()
    if (coarse_x, coarse_y, replacement_word) != (
        COARSE_X,
        COARSE_Y,
        AFTER_WORD,
    ):
        raise ValueError(
            "map41 layout fixed A/B contract requires coarse cell (1,6) "
            "and replacement 0x00220035"
        )
    if output.exists() and any(output.iterdir()):
        raise ValueError("map41 layout output directory must be empty")

    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("map41 layout base ROM identity mismatch")
    layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    regions = ImageResourceRegions.from_path(
        root / REGION_REGISTRY_PATH,
        layout,
    )
    resources = catalog_map_resource_relocations(root, base)
    resource = resources[(RESOURCE_TYPE, SOURCE_SHA256)]
    expected_headers = [
        alias["header_pointer_offset"] for alias in resource["logical_aliases"]
    ]
    if (
        resource["physical_offsets"] != EXPECTED_PHYSICAL_OFFSETS
        or expected_headers != EXPECTED_HEADER_POINTER_OFFSETS
        or [
            alias["map_id"]
            for alias in resource["logical_aliases"]
            if alias["header_pointer_offset"] == TARGET_HEADER_POINTER_OFFSET
        ]
        != [MAP_ID]
    ):
        raise ValueError("map41 layout catalog alias contract mismatch")

    source = resource["source_content"]
    calculated_offset = (COARSE_Y * COARSE_WIDTH + COARSE_X) * 4
    if calculated_offset != DECODED_BYTE_OFFSET:
        raise ValueError("map41 layout coarse-cell offset contract mismatch")
    if struct.unpack_from("<I", source, DECODED_BYTE_OFFSET)[0] != BEFORE_WORD:
        raise ValueError("map41 layout source word contract mismatch")

    output.mkdir(parents=True, exist_ok=True)
    variants = {
        "baseline": bytearray(source),
        "candidate": bytearray(source),
    }
    struct.pack_into(
        "<I",
        variants["candidate"],
        DECODED_BYTE_OFFSET,
        AFTER_WORD,
    )

    patch_sets: dict[str, list[dict[str, Any]]] = {}
    roms: dict[str, bytes] = {}
    specs: dict[str, str] = {}
    for variant, content in variants.items():
        content_path = output / f"{variant}-primary-layout.bin"
        content_path.write_bytes(content)
        spec_path = output / f"{variant}-spec.json"
        spec_path.write_text(
            json.dumps(
                _spec(root, resource, content_path),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        patches = resolve_map_resource_relocation_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
        if (
            len(patches) != 2
            or "allocation" not in patches[0]
            or patches[1]["offset"] != TARGET_HEADER_POINTER_OFFSET
        ):
            raise ValueError("map41 layout patch isolation contract mismatch")
        rom = _apply(base, layout, regions, patches)
        (output / f"{variant}.gba").write_bytes(rom)
        patch_sets[variant] = patches
        roms[variant] = rom
        specs[variant] = spec_path.name

    baseline_pointer = int(patch_sets["baseline"][0]["new_pointer"], 16)
    candidate_pointer = int(patch_sets["candidate"][0]["new_pointer"], 16)
    if baseline_pointer != candidate_pointer:
        raise ValueError("map41 layout runtime source pointers diverged")
    baseline_raw = lz77_decompress(
        roms["baseline"], baseline_pointer - ROM_BASE
    )
    candidate_raw = lz77_decompress(
        roms["candidate"], candidate_pointer - ROM_BASE
    )
    differing_source_bytes = [
        index
        for index, pair in enumerate(zip(baseline_raw, candidate_raw))
        if pair[0] != pair[1]
    ]
    if differing_source_bytes != [0xDC, 0xDE]:
        raise ValueError("map41 layout decoded source isolation mismatch")

    preserved_headers = [
        offset
        for offset in EXPECTED_HEADER_POINTER_OFFSETS
        if offset != TARGET_HEADER_POINTER_OFFSET
    ]
    only_map41_header_redirected = all(
        roms[variant][offset : offset + 4] == base[offset : offset + 4]
        for variant in ("baseline", "candidate")
        for offset in preserved_headers
    )
    manifest = {
        "schema": SCHEMA,
        "base_rom_sha256": ROM_SHA256,
        "runtime_source_pointer": _hex32(baseline_pointer),
        "edit": {
            "map_id": MAP_ID,
            "resource_type": RESOURCE_TYPE,
            "resource_sha256": SOURCE_SHA256,
            "map41_source_pointer": _hex32(MAP41_SOURCE_POINTER),
            "target_header_pointer_offset": _hex32(
                TARGET_HEADER_POINTER_OFFSET
            ),
            "coarse_x": COARSE_X,
            "coarse_y": COARSE_Y,
            "decoded_byte_offset": DECODED_BYTE_OFFSET,
            "before_word": _hex32(BEFORE_WORD),
            "after_word": _hex32(AFTER_WORD),
            "decoded_differing_byte_offsets": differing_source_bytes,
            "expected_runtime_ewram_word_address": _hex32(
                RUNTIME_EWRAM_BASE + DECODED_BYTE_OFFSET
            ),
        },
        "alias_split": {
            "all_header_pointer_offsets": EXPECTED_HEADER_POINTER_OFFSETS,
            "redirected_header_pointer_offsets": [
                TARGET_HEADER_POINTER_OFFSET
            ],
            "preserved_header_pointer_offsets": preserved_headers,
            "preserved_map_ids": [39, 40, 42, 43, 44, 45],
        },
        "roms": {
            variant: {
                "path": f"{variant}.gba",
                "sha256": _sha256(roms[variant]),
                "size": len(roms[variant]),
                "decoded_sha256": _sha256(bytes(variants[variant])),
                "spec": specs[variant],
            }
            for variant in ("baseline", "candidate")
        },
        "patch_ledgers": {
            variant: _patch_ledger(patch_sets[variant])
            for variant in ("baseline", "candidate")
        },
        "isolation": {
            "same_runtime_source_pointer": baseline_pointer
            == candidate_pointer,
            "same_pointer_redirect": patch_sets["baseline"][1]["after_hex"]
            == patch_sets["candidate"][1]["after_hex"],
            "only_map41_header_redirected": only_map41_header_redirected,
            "decoded_source_diff_count": len(differing_source_bytes),
        },
    }
    if (
        not manifest["isolation"]["same_runtime_source_pointer"]
        or not manifest["isolation"]["same_pointer_redirect"]
        or not manifest["isolation"]["only_map41_header_redirected"]
    ):
        raise ValueError("map41 layout A/B isolation contract failed")
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
