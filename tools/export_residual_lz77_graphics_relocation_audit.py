#!/usr/bin/env python3
"""Export the residual LZ77 graphics relocation proof artifact."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

from tools.build_mod import apply_patch
from tools.extract_tileset import lz77_decompress
from tools.image_resource_regions import ImageResourceRegions
from tools.import_residual_lz77_graphics_relocations import (
    CATALOG_PATH,
    CATALOG_SHA256,
    INVENTORY_PATH,
    INVENTORY_SHA256,
    REGION_REGISTRY_PATH,
    ROM_BASE,
    ROM_SHA256,
    catalog_residual_lz77_graphics,
    resolve_residual_lz77_graphics_relocation_patches,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


ARTIFACT_ID = "residual-lz77-graphics-relocation-v1"
PAYLOAD_SCHEMA = "residual-lz77-graphics-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
SCOPE = {
    "proved": (
        "All 20 residual aligned-pointer-reachable 4bpp LZ77 graphics and "
        "all 34 exact source-pointer literals are accounted for. A full "
        "preservation relocation rebuilds a 16 MiB ROM."
    ),
    "editable": (
        "Every resource may replace all of its complete 4bpp tiles while "
        "preserving that resource's decoded tile count. Recompression may "
        "use the entire registered 64 KiB region instead of the old slot."
    ),
    "not_proved": (
        "Changing decoded tile counts or VRAM destinations, editing raw or "
        "LZ77 palettes, the two unresolved palette identities, natural "
        "business names, and final screen-composited runtime equivalence."
    ),
}
IMPLEMENTATION_PATHS = (
    "tools/export_rom_pointer_lz77_inventory.py",
    "tools/verify_rom_pointer_lz77_inventory.py",
    "tools/export_rom_pointer_lz77_graphics.py",
    "tools/verify_rom_pointer_lz77_graphics.py",
    "tools/import_residual_lz77_graphics_relocations.py",
    "tools/gba_image_export.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_residual_lz77_graphics_relocation_audit.py",
    "tools/verify_residual_lz77_graphics_relocation_audit.py",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _asset_path(root: Path, output: Path, name: str) -> str:
    path = output / name
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _apply(
    base: bytes,
    layout: RomLayout,
    regions: ImageResourceRegions,
    patches: list[dict[str, Any]],
) -> bytes:
    data = bytearray(layout.expanded_base())
    gate = PatchSafetyGate(base, layout=layout, image_regions=regions)
    for patch in patches:
        apply_patch(data, patch, gate=gate)
    return bytes(data)


def _source_spec(
    root: Path,
    output: Path,
    base: bytes,
) -> dict[str, Any]:
    catalog = catalog_residual_lz77_graphics(root, base)
    resources = []
    for row in catalog["resources"]:
        pointer = row["source_pointer"]
        name = f"graphics_{pointer:08x}.4bpp.bin"
        raw = lz77_decompress(base, pointer - ROM_BASE)
        (output / name).write_bytes(raw)
        resources.append(
            {
                "source_pointer": f"0x{pointer:08X}",
                "graphics_file": _asset_path(root, output, name),
            }
        )
    registry = root / REGION_REGISTRY_PATH
    return {
        "schema": "residual-lz77-graphics-relocation-v1",
        "base_rom_sha256": _sha256(base),
        "source_inventory": INVENTORY_PATH.as_posix(),
        "source_inventory_sha256": _sha256(
            (root / INVENTORY_PATH).read_bytes()
        ),
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": _sha256(
            (root / CATALOG_PATH).read_bytes()
        ),
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGION_REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256(registry.read_bytes()),
        "region": "residual-lz77-graphics",
        "region_owner": "residual_lz77_graphics",
        "resources": resources,
    }


def _mutate_first_tile(raw: bytes, index: int) -> bytes:
    result = bytearray(raw)
    for offset in range(32):
        result[offset] ^= (index * 29 + offset * 7 + 1) & 0xFF
    return bytes(result)


def _capability_fixture(
    root: Path,
    base: bytes,
    layout: RomLayout,
    regions: ImageResourceRegions,
    spec: dict[str, Any],
) -> dict[str, Any]:
    fixture = copy.deepcopy(spec)
    with tempfile.TemporaryDirectory(
        prefix=".residual-lz77-capability-",
        dir=root / "build/experiments",
    ) as temporary:
        temp = Path(temporary)
        for index, row in enumerate(fixture["resources"]):
            source = Path(row["graphics_file"])
            raw = _mutate_first_tile(source.read_bytes(), index)
            path = temp / f"fixture-{index:02d}.4bpp.bin"
            path.write_bytes(raw)
            row["graphics_file"] = str(path)
        spec_path = temp / "fixture.json"
        spec_path.write_text(
            json.dumps(fixture, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        patches = resolve_residual_lz77_graphics_relocation_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
        output = _apply(base, layout, regions, patches)
    return {
        "mutation": (
            "xor each resource first 32-byte tile with "
            "(resource_index*29 + byte_offset*7 + 1) & 0xff"
        ),
        "changed_resources": len(spec["resources"]),
        "output_rom_sha256": _sha256(output),
    }


def export_audit(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    output = Path(output).resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (root / "build/experiments").mkdir(parents=True, exist_ok=True)
    base = (root / "rom/base.gba").read_bytes()
    if _sha256(base) != ROM_SHA256:
        raise ValueError("residual LZ77 audit base ROM SHA-256 mismatch")
    if _sha256((root / INVENTORY_PATH).read_bytes()) != INVENTORY_SHA256:
        raise ValueError("residual LZ77 audit inventory SHA-256 mismatch")
    if _sha256((root / CATALOG_PATH).read_bytes()) != CATALOG_SHA256:
        raise ValueError("residual LZ77 audit catalog SHA-256 mismatch")
    layout_path = root / "sequel/rom-layout.json"
    layout = RomLayout.from_path(layout_path, base)
    regions = ImageResourceRegions.from_path(
        root / REGION_REGISTRY_PATH,
        layout,
    )
    region = regions.require(
        "residual-lz77-graphics",
        "residual_lz77_graphics",
    )
    spec = _source_spec(root, output, base)
    spec_path = output / SPEC_NAME
    spec_path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    patches = resolve_residual_lz77_graphics_relocation_patches(
        root,
        spec_path,
        rom=base,
        layout=layout,
        regions=regions,
    )
    output_rom = _apply(base, layout, regions, patches)
    allocations = [row for row in patches if "allocation" in row]
    redirects = [
        row
        for row in patches
        if row.get("asset_type") == "residual_lz77_graphics_pointer"
    ]
    allocation_end = max(
        row["offset"] + row["encoded_size"] for row in allocations
    )
    stored = sum(row["encoded_size"] for row in allocations)
    source_catalog = catalog_residual_lz77_graphics(root, base)
    summary = {
        "resource_count": source_catalog["resource_count"],
        "source_pointer_reference_count": source_catalog[
            "pointer_reference_count"
        ],
        "unexpected_source_pointer_count": len(
            source_catalog["unexpected_pointer_offsets"]
        ),
        "decompressed_size": source_catalog["decompressed_size"],
        "source_compressed_size": source_catalog["compressed_size"],
        "unresolved_palette_count": source_catalog[
            "unresolved_palette_count"
        ],
        "allocation_count": len(allocations),
        "pointer_patch_count": len(redirects),
        "allocation_start": region.start,
        "allocation_end": allocation_end,
        "region_end": region.end,
        "stored_payload_bytes": stored,
        "allocation_span": allocation_end - region.start,
        "remaining_bytes": region.end - allocation_end,
        "applied_patch_count": len(patches),
    }
    payload = {
        "schema": PAYLOAD_SCHEMA,
        "base_rom": {
            "path": "rom/base.gba",
            "size": len(base),
            "sha256": _sha256(base),
        },
        "layout": {
            "path": "sequel/rom-layout.json",
            "sha256": _sha256(layout_path.read_bytes()),
            "target_rom_size": layout.target_rom_size,
            "partition": "sequel-image-assets",
            "owner": "sequel_image_assets",
        },
        "region_registry": {
            "path": REGION_REGISTRY_PATH.as_posix(),
            "sha256": _sha256(
                (root / REGION_REGISTRY_PATH).read_bytes()
            ),
            "region": region.id,
            "owner": region.owner,
            "start": region.start,
            "end": region.end,
        },
        "inventory": {
            "path": INVENTORY_PATH.as_posix(),
            "sha256": INVENTORY_SHA256,
        },
        "catalog": {
            "path": CATALOG_PATH.as_posix(),
            "sha256": CATALOG_SHA256,
        },
        "authoring_spec": {
            "file": SPEC_NAME,
            "sha256": _sha256(spec_path.read_bytes()),
        },
        "implementation": {
            path: _sha256((root / path).read_bytes())
            for path in IMPLEMENTATION_PATHS
        },
        "summary": summary,
        "allocations": [
            {
                key: row[key]
                for key in (
                    "id",
                    "offset",
                    "source_pointer",
                    "new_pointer",
                    "decompressed_size",
                    "encoded_size",
                    "tile_count",
                    "replacement_sha256",
                    "destination_addresses",
                    "palette_binding_kind",
                    "palette_source_addresses",
                    "pointer_offsets",
                )
            }
            for row in allocations
        ],
        "pointer_patches": [
            {
                key: row[key]
                for key in (
                    "id",
                    "offset",
                    "source_pointer",
                    "new_pointer",
                    "pointer_role",
                )
            }
            for row in redirects
        ],
        "output_rom_sha256": _sha256(output_rom),
        "capability_fixture": _capability_fixture(
            root,
            base,
            layout,
            regions,
            spec,
        ),
        "scope": SCOPE,
    }
    payload_path = output / PAYLOAD_NAME
    payload_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    files = {
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
        "payload_sha256": files[PAYLOAD_NAME],
        "files": files,
        "scope": SCOPE,
        "summary": summary,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_residual_lz77_graphics_relocation_audit.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{ARTIFACT_ID}",
            ],
            "exit_code": 0,
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(f"artifacts/{ARTIFACT_ID}"),
    )
    args = parser.parse_args()
    output = args.output
    if not output.is_absolute():
        output = args.root / output
    payload = export_audit(args.root, output)
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
