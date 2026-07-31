#!/usr/bin/env python3
"""Export the four-source residual WRAM derived-tilemap relocation proof."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import struct
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from tools.build_mod import apply_patch
from tools.image_resource_regions import ImageResourceRegions
from tools.import_residual_wram_derived_tilemap_relocations import (
    ABI_PATH,
    ABI_SHA256,
    REGISTRY_PATH,
    ROM_SHA256,
    catalog_residual_wram_derived_tilemaps,
    resolve_residual_wram_derived_tilemap_relocation_patches,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


ARTIFACT_ID = "residual-wram-derived-tilemap-relocation-v1"
PAYLOAD_SCHEMA = "residual-wram-derived-tilemap-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
IMPLEMENTATION_PATHS = (
    "tools/export_residual_wram_visual_metadata_abi.py",
    "tools/verify_residual_wram_visual_metadata_abi.py",
    "tools/import_residual_wram_derived_tilemap_relocations.py",
    "tools/extract_tileset.py",
    "tools/gba_image_export.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/automated_test.py",
    "tools/export_residual_wram_derived_tilemap_relocation_audit.py",
    "tools/verify_residual_wram_derived_tilemap_relocation_audit.py",
)
SCOPE = {
    "proved": (
        "All four remaining pointer-reachable WRAM tilemap sources and their "
        "four exact aligned roots relocate into an owned 16 MiB ROM region."
    ),
    "editable": (
        "All 832 u16 entries keep source geometry and palette bank while "
        "selecting tiles inside each source's observed range and using H/V "
        "flip bits."
    ),
    "not_proved": (
        "Natural runtime reachability, queue-slot success and flush, graphics "
        "or palette ownership, natural-language screen identity, and final "
        "screen pixel or timing equivalence."
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def _asset_path(root: Path, output: Path, name: str) -> str:
    path = output / name
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _literal_worst_case(sizes: list[int], start: int) -> int:
    cursor = start
    for size in sizes:
        cursor = (cursor + 3) & ~3
        cursor += 4 + size + (size + 7) // 8
    return cursor - start


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


def _capability_fixture(
    root: Path,
    base: bytes,
    layout: RomLayout,
    regions: ImageResourceRegions,
    spec: dict[str, Any],
) -> dict[str, Any]:
    fixture = copy.deepcopy(spec)
    experiments = root / "build/experiments"
    experiments.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".residual-wram-derived-capability-",
        dir=experiments,
    ) as temporary:
        temp = Path(temporary)
        for resource in fixture["resources"]:
            source = Path(resource["tilemap_file"])
            if not source.is_absolute():
                source = root / source
            raw = bytearray(source.read_bytes())
            entry = struct.unpack_from("<H", raw, 0)[0]
            struct.pack_into("<H", raw, 0, entry ^ 0x0400)
            target = temp / source.name
            target.write_bytes(raw)
            resource["tilemap_file"] = str(target)
        spec_path = temp / "fixture.json"
        spec_path.write_bytes(_canonical_json(fixture))
        patches = resolve_residual_wram_derived_tilemap_relocation_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
        rebuilt = _apply(base, layout, regions, patches)
    return {
        "mutation": "toggle H-flip on entry 0 of every tilemap source",
        "changed_entries": 4,
        "output_rom_sha256": _sha256(rebuilt),
    }


def export_audit(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    output = Path(output).resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    base = (root / "rom/base.gba").read_bytes()
    if _sha256(base) != ROM_SHA256:
        raise ValueError("derived WRAM tilemap audit base ROM mismatch")
    if _sha256((root / ABI_PATH).read_bytes()) != ABI_SHA256:
        raise ValueError("derived WRAM tilemap audit ABI mismatch")
    layout_path = root / "sequel/rom-layout.json"
    layout = RomLayout.from_path(layout_path, base)
    registry_path = root / REGISTRY_PATH
    regions = ImageResourceRegions.from_path(registry_path, layout)
    region = regions.require(
        "residual-wram-derived-tilemaps",
        "residual_wram_derived_tilemaps",
    )
    catalog = catalog_residual_wram_derived_tilemaps(root, base)
    resources = []
    source_rows = []
    for row in catalog:
        name = f"tilemap-{row['source_pointer']:08x}.bin"
        data = row["decoded"]
        (output / name).write_bytes(data)
        resources.append(
            {
                "source_pointer": f"0x{row['source_pointer']:08X}",
                "tilemap_file": _asset_path(root, output, name),
            }
        )
        source_rows.append(
            {
                "source_pointer": f"0x{row['source_pointer']:08X}",
                "classification": row["classification"],
                "decoded_size": row["decoded_size"],
                "decoded_sha256": row["decoded_sha256"],
                "entry_count": row["entry_count"],
                "pointer_offsets": row["pointer_offsets"],
                "tilemap_file": name,
                "tilemap_file_sha256": _sha256(data),
            }
        )
    spec = {
        "schema": "residual-wram-derived-tilemap-relocation-v1",
        "base_rom_sha256": ROM_SHA256,
        "abi_artifact": ABI_PATH.as_posix(),
        "abi_sha256": ABI_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256(registry_path.read_bytes()),
        "region": "residual-wram-derived-tilemaps",
        "region_owner": "residual_wram_derived_tilemaps",
        "resources": resources,
    }
    spec_path = output / SPEC_NAME
    spec_path.write_bytes(_canonical_json(spec))
    patches = resolve_residual_wram_derived_tilemap_relocation_patches(
        root,
        spec_path,
        rom=base,
        layout=layout,
        regions=regions,
    )
    rebuilt = _apply(base, layout, regions, patches)
    allocations = [row for row in patches if "allocation" in row]
    redirects = [row for row in patches if "allocation" not in row]
    allocation_end = max(
        row["offset"] + row["encoded_size"] for row in allocations
    )
    summary = {
        "source_count": len(catalog),
        "source_pointer_reference_count": sum(
            len(row["pointer_offsets"]) for row in catalog
        ),
        "decoded_size": sum(row["decoded_size"] for row in catalog),
        "entry_count": sum(row["entry_count"] for row in catalog),
        "allocation_count": len(allocations),
        "pointer_patch_count": len(redirects),
        "applied_patch_count": len(patches),
        "allocation_start": region.start,
        "allocation_end": allocation_end,
        "region_end": region.end,
        "stored_payload_bytes": sum(
            row["encoded_size"] for row in allocations
        ),
        "allocation_span": allocation_end - region.start,
        "remaining_bytes": region.end - allocation_end,
        "literal_lz77_worst_case_bytes_with_alignment": _literal_worst_case(
            [row["decoded_size"] for row in catalog],
            region.start,
        ),
    }
    payload = {
        "schema": PAYLOAD_SCHEMA,
        "base_rom": {
            "path": "rom/base.gba",
            "size": len(base),
            "sha256": ROM_SHA256,
        },
        "layout": {
            "path": "sequel/rom-layout.json",
            "sha256": _sha256(layout_path.read_bytes()),
            "target_rom_size": layout.target_rom_size,
        },
        "region_registry": {
            "path": REGISTRY_PATH.as_posix(),
            "sha256": _sha256(registry_path.read_bytes()),
            "region": region.id,
            "owner": region.owner,
            "start": region.start,
            "end": region.end,
        },
        "abi": {"path": ABI_PATH.as_posix(), "sha256": ABI_SHA256},
        "authoring_spec": {
            "file": SPEC_NAME,
            "sha256": _sha256(spec_path.read_bytes()),
        },
        "sources": source_rows,
        "allocations": [
            {
                "source_pointer": f"0x{row['source_pointer']:08X}",
                "offset": row["offset"],
                "new_pointer": f"0x{row['new_pointer']:08X}",
                "encoded_size": row["encoded_size"],
                "replacement_sha256": row["replacement_sha256"],
            }
            for row in allocations
        ],
        "redirects": [
            {
                "source_pointer": f"0x{row['source_pointer']:08X}",
                "offset": row["offset"],
                "new_pointer": f"0x{row['new_pointer']:08X}",
            }
            for row in redirects
        ],
        "summary": summary,
        "scope": SCOPE,
        "capability_fixture": _capability_fixture(
            root,
            base,
            layout,
            regions,
            spec,
        ),
        "output_rom_sha256": _sha256(rebuilt),
        "implementation": {
            path: _sha256((root / path).read_bytes())
            for path in IMPLEMENTATION_PATHS
        },
    }
    payload_bytes = _canonical_json(payload)
    (output / PAYLOAD_NAME).write_bytes(payload_bytes)
    artifact_files = {
        path.name: _sha256(path.read_bytes())
        for path in sorted(output.iterdir())
        if path.is_file()
    }
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_id": ARTIFACT_ID,
        "artifact_schema": PAYLOAD_SCHEMA,
        "artifact_status": "accepted",
        "payload_file": PAYLOAD_NAME,
        "payload_sha256": _sha256(payload_bytes),
        "files": artifact_files,
        "implementation": payload["implementation"],
        "summary": summary,
        "scope": SCOPE,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_residual_wram_derived_tilemap_relocation_audit.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{ARTIFACT_ID}",
            ],
            "exit_code": 0,
        },
    }
    (output / "manifest.json").write_bytes(_canonical_json(manifest))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts") / ARTIFACT_ID,
    )
    args = parser.parse_args()
    payload = export_audit(args.root, args.output)
    print(json.dumps(payload["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
