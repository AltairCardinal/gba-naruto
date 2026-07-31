#!/usr/bin/env python3
"""Export the Cutscene OBJ relocation proof artifact."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
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
from tools.import_cutscene_obj_bundle_relocations import (
    CATALOG_PATH,
    CATALOG_SHA256,
    FRAME_COUNTS,
    MAX_GRAPHICS_TILES,
    REGION_REGISTRY_PATH,
    ROM_BASE,
    ROM_SHA256,
    catalog_cutscene_obj_bundle,
    resolve_cutscene_obj_bundle_relocation_patches,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


ARTIFACT_ID = "cutscene-obj-bundle-relocation-v1"
PAYLOAD_SCHEMA = "cutscene-obj-bundle-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
RAW_NAMES = tuple(
    name
    for resource_id in range(4)
    for name in (
        f"resource_{resource_id}.4bpp.bin",
        f"resource_{resource_id}.bgr555.bin",
    )
)
SCOPE = {
    "proved": (
        "All four fixed Cutscene OBJ IDs, 10 source frames/components, "
        "10 source animations/keyframes and all 36 exact source pointer "
        "references are accounted for; 12 allocations and 16 root pointer "
        "patches rebuild a 16 MiB ROM."
    ),
    "editable": (
        "Each fixed ID may use 1..256 complete 4bpp tiles and one 16-color "
        "palette. The fixed 2/2/2/4 frame and animation slots each support "
        "1..2 valid GBA OBJ components and a non-empty variable keyframe "
        "timeline with u16 durations."
    ),
    "not_proved": (
        "Adding a fifth ID, changing the fixed frame/animation slot counts, "
        "more than two simultaneous components per frame, caller-level scene "
        "cleanup, or final screen-composited pixel/timing equivalence after "
        "modification."
    ),
}
IMPLEMENTATION_PATHS = (
    "tools/export_cutscene_obj_assets.py",
    "tools/verify_cutscene_obj_export.py",
    "tools/import_cutscene_obj_bundle_relocations.py",
    "tools/gba_image_export.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_cutscene_obj_bundle_relocation_audit.py",
    "tools/verify_cutscene_obj_bundle_relocation_audit.py",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _asset_path(root: Path, output: Path, name: str) -> str:
    path = output / name
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _source_spec(
    root: Path,
    output: Path,
    base: bytes,
) -> dict[str, Any]:
    source = json.loads((root / CATALOG_PATH).read_text(encoding="utf-8"))
    resources = []
    for row in source["resources"]:
        resource_id = row["resource_id"]
        graphics = lz77_decompress(
            base,
            int(row["gfx_pointer"], 16) - ROM_BASE,
        )
        palette = lz77_decompress(
            base,
            int(row["palette_pointer"], 16) - ROM_BASE,
        )
        graphics_name = f"resource_{resource_id}.4bpp.bin"
        palette_name = f"resource_{resource_id}.bgr555.bin"
        (output / graphics_name).write_bytes(graphics)
        (output / palette_name).write_bytes(palette)
        frames = []
        animations = []
        for frame in row["frames"]:
            raw = bytes.fromhex(frame["definition_raw_hex"])
            (
                tile_offset,
                x_offset,
                y_offset,
                width,
                height,
                transform_x,
                transform_y,
                unknown_10,
                unknown_12,
            ) = struct.unpack("<IhhHHHHHH", raw[:20])
            if (
                (transform_x, transform_y, unknown_10, unknown_12)
                != (0x100, 0x100, 0xFF, 0)
                or raw[20:] != bytes.fromhex("ffff0000")
            ):
                raise ValueError(
                    f"Cutscene OBJ resource {resource_id} definition changed"
                )
            animation = struct.unpack(
                "<4H",
                bytes.fromhex(frame["animation_raw_hex"]),
            )
            if animation[2:] != (0xFFFF, 0):
                raise ValueError(
                    f"Cutscene OBJ resource {resource_id} animation changed"
                )
            frames.append(
                {
                    "id": frame["frame_id"],
                    "components": [
                        {
                            "tile_offset": tile_offset,
                            "x_offset": x_offset,
                            "y_offset": y_offset,
                            "width": width,
                            "height": height,
                        }
                    ],
                }
            )
            animations.append(
                {
                    "id": frame["frame_id"],
                    "keyframes": [
                        {
                            "frame_id": animation[0],
                            "duration_ticks": animation[1],
                        }
                    ],
                }
            )
        resources.append(
            {
                "id": resource_id,
                "graphics_file": _asset_path(root, output, graphics_name),
                "palette_file": _asset_path(root, output, palette_name),
                "frames": frames,
                "animations": animations,
            }
        )
    registry = root / REGION_REGISTRY_PATH
    return {
        "schema": "cutscene-obj-bundle-relocation-v1",
        "base_rom_sha256": _sha256(base),
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": _sha256_file(root / CATALOG_PATH),
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGION_REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256_file(registry),
        "region": "cutscene-obj-bundle",
        "region_owner": "cutscene_obj_resources",
        "resources": resources,
    }


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


def _capability_fixture(
    root: Path,
    base: bytes,
    layout: RomLayout,
    regions: ImageResourceRegions,
    spec: dict[str, Any],
) -> dict[str, Any]:
    fixture = copy.deepcopy(spec)
    original = (root / fixture["resources"][0]["graphics_file"]).read_bytes()
    extension = bytes(
        (index * 73 + 19) & 0xFF
        for index in range((MAX_GRAPHICS_TILES - len(original) // 32) * 32)
    )
    graphics = original + extension
    added = dict(fixture["resources"][0]["frames"][0]["components"][0])
    added["tile_offset"] = 192
    added["x_offset"] = 32
    fixture["resources"][0]["frames"][0]["components"].append(added)
    fixture["resources"][0]["animations"][0]["keyframes"].append(
        {"frame_id": 1, "duration_ticks": 3}
    )
    (root / "build/experiments").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".cutscene-obj-capability-",
        dir=root / "build/experiments",
    ) as temporary:
        temporary_path = Path(temporary)
        graphics_path = temporary_path / "resource-0-256.4bpp.bin"
        spec_path = temporary_path / "fixture.json"
        graphics_path.write_bytes(graphics)
        fixture["resources"][0]["graphics_file"] = str(graphics_path)
        spec_path.write_text(
            json.dumps(fixture, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        patches = resolve_cutscene_obj_bundle_relocation_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
        data = _apply(base, layout, regions, patches)
    allocations = [
        patch for patch in patches if isinstance(patch.get("allocation"), dict)
    ]
    allocation_end = max(
        patch["offset"] + len(bytes.fromhex(patch["after_hex"]))
        for patch in allocations
    )
    return {
        "schema": "cutscene-obj-bundle-capability-fixture-v1",
        "construction": (
            "Extend resource 0 deterministically from 128 to 256 tiles, add "
            "a second 64x64 component at tile 192, and append a second "
            "keyframe to animation 0."
        ),
        "graphics_tile_count": len(graphics) // 32,
        "graphics_sha256": _sha256(graphics),
        "component_count": sum(
            len(frame["components"])
            for resource in fixture["resources"]
            for frame in resource["frames"]
        ),
        "keyframe_count": sum(
            len(animation["keyframes"])
            for resource in fixture["resources"]
            for animation in resource["animations"]
        ),
        "allocation_count": len(allocations),
        "pointer_patch_count": sum(
            patch.get("asset_type") == "cutscene_obj_bundle_pointer"
            for patch in patches
        ),
        "allocation_end": allocation_end,
        "output_rom_sha256": _sha256(data),
    }


def export_audit(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    output = Path(output)
    if not output.is_absolute():
        output = root / output
    output.mkdir(parents=True, exist_ok=True)
    for child in output.iterdir():
        if child.is_file():
            child.unlink()
        else:
            raise ValueError("Cutscene OBJ audit output contains a directory")

    base = (root / "rom/base.gba").read_bytes()
    if _sha256(base) != ROM_SHA256:
        raise ValueError("Cutscene OBJ audit base ROM mismatch")
    if _sha256_file(root / CATALOG_PATH) != CATALOG_SHA256:
        raise ValueError("Cutscene OBJ audit source catalog mismatch")
    layout_path = root / "sequel/rom-layout.json"
    layout = RomLayout.from_path(layout_path, base)
    registry_path = root / REGION_REGISTRY_PATH
    regions = ImageResourceRegions.from_path(registry_path, layout)
    region = regions.require(
        "cutscene-obj-bundle",
        "cutscene_obj_resources",
    )
    source = catalog_cutscene_obj_bundle(root, base)

    spec = _source_spec(root, output, base)
    spec_path = output / SPEC_NAME
    spec_path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    patches = resolve_cutscene_obj_bundle_relocation_patches(
        root,
        spec_path,
        rom=base,
        layout=layout,
        regions=regions,
    )
    data = _apply(base, layout, regions, patches)
    allocations = [
        patch for patch in patches if isinstance(patch.get("allocation"), dict)
    ]
    redirects = [
        patch
        for patch in patches
        if patch.get("asset_type") == "cutscene_obj_bundle_pointer"
    ]
    if len(allocations) != 12 or len(redirects) != 16 or len(patches) != 28:
        raise ValueError("Cutscene OBJ audit patch denominator mismatch")
    allocation_end = max(
        patch["offset"] + len(bytes.fromhex(patch["after_hex"]))
        for patch in allocations
    )
    summary = {
        "resource_count": source["resource_count"],
        "frame_count": source["frame_count"],
        "component_count": source["frame_count"],
        "animation_count": source["animation_count"],
        "keyframe_count": source["animation_count"],
        "frame_counts": source["frame_counts"],
        "runtime_tile_base": source["runtime_tile_base"],
        "maximum_safe_graphics_tiles": MAX_GRAPHICS_TILES,
        "runtime_loader_call_count": source["runtime_loader_call_count"],
        "source_pointer_reference_count": source[
            "pointer_reference_count"
        ],
        "unexpected_source_pointer_count": len(
            source["unexpected_pointer_offsets"]
        ),
        "allocation_count": len(allocations),
        "pointer_patch_count": len(redirects),
        "allocation_start": region.start,
        "allocation_end": allocation_end,
        "region_end": region.end,
        "stored_payload_bytes": sum(
            len(bytes.fromhex(patch["after_hex"])) for patch in allocations
        ),
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
            "sha256": _sha256_file(layout_path),
            "target_rom_size": layout.target_rom_size,
            "partition": regions.parent.id,
            "owner": regions.parent.owner,
        },
        "region_registry": {
            "path": REGION_REGISTRY_PATH.as_posix(),
            "sha256": _sha256_file(registry_path),
            "region": region.id,
            "owner": region.owner,
            "start": region.start,
            "end": region.end,
        },
        "catalog": {
            "path": CATALOG_PATH.as_posix(),
            "sha256": _sha256_file(root / CATALOG_PATH),
        },
        "authoring_spec": {
            "file": SPEC_NAME,
            "sha256": _sha256_file(spec_path),
        },
        "implementation": {
            path: _sha256_file(root / path) for path in IMPLEMENTATION_PATHS
        },
        "summary": summary,
        "allocations": [
            {
                key: patch[key]
                for key in (
                    "id",
                    "resource_type",
                    "offset",
                    "resource_id",
                    "decompressed_size",
                    "encoded_size",
                    "replacement_sha256",
                    "tile_count",
                    "frame_count",
                    "animation_count",
                    "component_counts",
                    "keyframe_counts",
                    "definition_table_pointer",
                    "animation_table_pointer",
                    "component_pointers",
                    "sequence_pointers",
                )
                if key in patch
            }
            for patch in allocations
        ],
        "raw_assets": {
            name: _sha256_file(output / name) for name in RAW_NAMES
        },
        "capability_fixture": _capability_fixture(
            root,
            base,
            layout,
            regions,
            spec,
        ),
        "output_rom_sha256": _sha256(data),
        "scope": SCOPE,
    }
    payload_path = output / PAYLOAD_NAME
    payload_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    promoted_names = (SPEC_NAME, PAYLOAD_NAME, *RAW_NAMES)
    files = {
        name: _sha256_file(output / name) for name in promoted_names
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
                "tools/verify_cutscene_obj_bundle_relocation_audit.py",
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
        default=Path("artifacts") / ARTIFACT_ID,
    )
    args = parser.parse_args()
    payload = export_audit(args.root, args.output)
    print(json.dumps(payload["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
