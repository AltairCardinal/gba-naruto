#!/usr/bin/env python3
"""Build an isolated Cutscene OBJ ID 1 secondary-pointer A/B input pair."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_cutscene_obj_id1_pixel_ab import build_pair as build_relocated_pair
from tools.build_cutscene_obj_primary_ptr_ab import EXPECTED_BASELINE_SHA256
from tools.build_mod import apply_patch
from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import encode_gba_lz77
from tools.image_resource_regions import ImageResourceRegions
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout

SCHEMA = "cutscene-obj-id1-secondary-ptr-ab-build-v1"
POINTER_OFFSET = 0x53DF7C
ROM_BASE = 0x08000000
PARENT_MANIFEST_SHA256 = "34e8cf88ed9d57ff6a6e5c4148d3a3af8f055c50923b7e62f0e369e3dc356e3f"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _fresh_output(output: Path) -> Path:
    output = Path(output).absolute()
    if output.resolve(strict=False) != output:
        raise ValueError("output must not use symlinks")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("output directory must be empty")
    return output


def build_pair(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output = _fresh_output(output)
    base = (root / "rom/base.gba").read_bytes()
    with tempfile.TemporaryDirectory() as directory:
        parent_dir = Path(directory) / "parent"
        parent = build_relocated_pair(root, parent_dir)
        original = (parent_dir / "baseline/baseline.gba").read_bytes()
        if (
            _sha(original) != EXPECTED_BASELINE_SHA256
            or _sha((parent_dir / "build-manifest.json").read_bytes())
            != PARENT_MANIFEST_SHA256
        ):
            raise ValueError("relocated parent identity mismatch")

    layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    regions = ImageResourceRegions.from_path(
        root / "sequel/image-resource-regions.json", layout
    )
    region = regions.require("cutscene-obj-bundle", "cutscene_obj_resources")
    allocations = [
        row for row in parent["variants"]["baseline"]["patch_ledger"]
        if row["kind"] == "allocation"
    ]
    gate = PatchSafetyGate(base, layout=layout, image_regions=regions)
    for row in allocations:
        offset, size = row["offset"], row["size"]
        gate.register({
            "id": row["id"], "offset": offset,
            "before_hex": (b"\xFF" * size).hex(),
            "after_hex": original[offset:offset + size].hex(),
            "allocation": row["allocation"],
        }, patch_class="allocation")
    last_end = max(row["offset"] + row["size"] for row in allocations)
    allocation_offset = (last_end + region.alignment - 1) & -region.alignment
    before_pointer = struct.unpack_from("<I", original, POINTER_OFFSET)[0]
    palette = lz77_decompress(original, before_pointer - ROM_BASE)
    if len(palette) != 32:
        raise ValueError("ID 1 palette size mismatch")
    authored_palette = bytearray(palette)
    before_color = struct.unpack_from("<H", palette, 2)[0]
    struct.pack_into("<H", authored_palette, 2, before_color ^ 0x1F)
    encoded = encode_gba_lz77(bytes(authored_palette))
    allocation = {
        "id": "cutscene-obj-id1-secondary-ptr-palette",
        "type": "bytes", "offset": allocation_offset,
        "before_hex": (b"\xFF" * len(encoded)).hex(),
        "after_hex": encoded.hex(),
        "allocation": {
            "partition": "sequel-image-assets", "owner": "sequel_image_assets",
            "region": region.id, "region_owner": region.owner,
        },
    }
    shared = bytearray(original)
    # Register against the immutable expanded origin and all parent allocations.
    apply_patch(shared, allocation, gate=gate)
    baseline = bytes(shared)
    after_pointer = ROM_BASE + allocation_offset
    redirect = {
        "id": "cutscene-obj-id1-secondary-ptr-redirect", "type": "bytes",
        "offset": POINTER_OFFSET,
        "before_hex": baseline[POINTER_OFFSET:POINTER_OFFSET + 4].hex(),
        "after_hex": struct.pack("<I", after_pointer).hex(),
    }
    candidate_buffer = bytearray(baseline)
    apply_patch(candidate_buffer, redirect, gate=PatchSafetyGate(baseline))
    candidate = bytes(candidate_buffer)
    differences = [
        index for index, (left, right) in enumerate(zip(baseline, candidate, strict=True))
        if left != right
    ]
    if not differences or any(not POINTER_OFFSET <= i < POINTER_OFFSET + 4 for i in differences):
        raise ValueError("secondary pointer edit is not isolated")
    output.mkdir(parents=True, exist_ok=True)
    variants = {}
    for name, payload in (("baseline", baseline), ("candidate", candidate)):
        variant_dir = output / name
        variant_dir.mkdir()
        path = variant_dir / f"{name}.gba"
        path.write_bytes(payload)
        variants[name] = {
            "rom_path": path.relative_to(output).as_posix(),
            "rom_sha256": _sha(payload), "rom_size": len(payload),
        }
    manifest = {
        "schema": SCHEMA,
        "source_rom_sha256": _sha(base),
        "parent_baseline_sha256": EXPECTED_BASELINE_SHA256,
        "parent_manifest_sha256": PARENT_MANIFEST_SHA256,
        "edit": {
            "record_id": "1", "resource_id": 1, "field": "secondary_ptr",
            "offset": POINTER_OFFSET, "before_pointer": before_pointer,
            "after_pointer": after_pointer,
        },
        "allocation": {
            "offset": allocation_offset, "size": len(encoded),
            "region": region.id, "region_owner": region.owner,
            "encoded_sha256": _sha(encoded),
            "decompressed_sha256": _sha(bytes(authored_palette)),
            "shared_by_both_variants": True,
            "palette_color_index": 1, "before_color": before_color,
            "after_color": before_color ^ 0x1F,
        },
        "isolation": {"changed_rom_offsets": differences, "other_bytes_equal": True},
        "variants": variants,
        "runtime_verified": False,
    }
    _write_json(output / "build-manifest.json", manifest)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(build_pair(args.root, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
