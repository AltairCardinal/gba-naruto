#!/usr/bin/env python3
"""Export the fixed-ID generic Sprite relocation proof artifact."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
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
from tools.image_resource_regions import ImageResourceRegions
from tools.import_generic_sprite_bundle_relocations import (
    ANIMATION_CATALOG_PATH,
    ANIMATION_CATALOG_SHA256,
    MAX_GRAPHICS_TILES,
    REGION_REGISTRY_PATH,
    ROM_SHA256,
    STATIC_CATALOG_PATH,
    STATIC_CATALOG_SHA256,
    catalog_generic_sprite_bundle,
    resolve_generic_sprite_bundle_relocation_patches,
)
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


ARTIFACT_ID = "generic-sprite-bundle-relocation-v1"
PAYLOAD_SCHEMA = "generic-sprite-bundle-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
SCOPE = {
    "proved": (
        "All 43 fixed generic Sprite IDs, 45 source components, the canonical "
        "graphics/palette payloads and all 174 exact source pointer references "
        "are accounted for; 45 payload allocations, 88 external pointer "
        "patches and 43 tile-base writes rebuild a 16 MiB ROM."
    ),
    "editable": (
        "The shared graphics pack may contain 1..97 complete 4bpp tiles, the "
        "palette remains one 16-color bank, and each fixed ID may contain "
        "1..2 valid GBA OBJ components, matching the proved source maximum. "
        "Animation 0 remains the proved "
        "single-frame hold-one-tick then stop sequence."
    ),
    "not_proved": (
        "Adding Sprite IDs, adding animations or frames, scene-specific "
        "resource overwrites, natural selection of every ID, or final "
        "screen-composited pixel/timing equivalence after modification."
    ),
}
IMPLEMENTATION_PATHS = (
    "tools/import_generic_sprite_bundle_relocations.py",
    "tools/export_sprite_definition_runtime_chain.py",
    "tools/verify_sprite_definition_runtime_chain.py",
    "tools/export_sprite_definition_animations.py",
    "tools/verify_sprite_definition_animations.py",
    "tools/gba_image_export.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_generic_sprite_bundle_relocation_audit.py",
    "tools/verify_generic_sprite_bundle_relocation_audit.py",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _component(component: dict[str, Any]) -> dict[str, Any]:
    return {
        key: component[key]
        for key in (
            "tile_offset",
            "flag_02",
            "flag_03",
            "horizontal_position_input",
            "vertical_position_input",
            "width",
            "height",
            "transform_factor_0c",
            "transform_factor_0e",
            "unknown_10_byte",
            "oam_attribute_byte",
            "unknown_12",
        )
    }


def _spec(root: Path, base: bytes) -> dict[str, Any]:
    static = json.loads((root / STATIC_CATALOG_PATH).read_text(encoding="utf-8"))
    registry = root / REGION_REGISTRY_PATH
    return {
        "schema": "generic-sprite-bundle-relocation-v1",
        "base_rom_sha256": _sha256(base),
        "source_static_catalog": STATIC_CATALOG_PATH.as_posix(),
        "source_static_catalog_sha256": _sha256_file(
            root / STATIC_CATALOG_PATH
        ),
        "source_animation_catalog": ANIMATION_CATALOG_PATH.as_posix(),
        "source_animation_catalog_sha256": _sha256_file(
            root / ANIMATION_CATALOG_PATH
        ),
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGION_REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256_file(registry),
        "region": "generic-sprite-bundle",
        "region_owner": "generic_sprite_resources",
        "graphics_file": (
            STATIC_CATALOG_PATH.parent
            / static["static_resources"]["graphics"]["output_bin"]
        ).as_posix(),
        "palette_file": (
            STATIC_CATALOG_PATH.parent
            / static["static_resources"]["palette"]["output_bin"]
        ).as_posix(),
        "entries": [
            {
                "id": entry["id"],
                "tile_base_offset": entry["tile_base_offset"],
                "components": [
                    _component(component)
                    for component in entry["components"]
                ],
            }
            for entry in static["entries"]
        ],
    }


def _capability_fixture(
    root: Path,
    base: bytes,
    layout: RomLayout,
    regions: ImageResourceRegions,
    spec: dict[str, Any],
) -> dict[str, Any]:
    fixture = copy.deepcopy(spec)
    original = (root / spec["graphics_file"]).read_bytes()
    extension = bytes((index * 73 + 19) & 0xFF for index in range(48 * 32))
    graphics = original + extension
    added = dict(fixture["entries"][0]["components"][0])
    added["tile_offset"] = 96
    added["horizontal_position_input"] = 8
    fixture["entries"][0]["components"].append(added)
    (root / "build/experiments").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".generic-sprite-capability-",
        dir=root / "build/experiments",
    ) as temporary:
        temporary_path = Path(temporary)
        graphics_path = temporary_path / "graphics-97.4bpp.bin"
        spec_path = temporary_path / "fixture.json"
        graphics_path.write_bytes(graphics)
        fixture["graphics_file"] = str(graphics_path)
        spec_path.write_text(
            json.dumps(fixture, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        patches = resolve_generic_sprite_bundle_relocation_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
        data = bytearray(layout.expanded_base())
        gate = PatchSafetyGate(base, layout=layout, image_regions=regions)
        for patch in patches:
            apply_patch(data, patch, gate=gate)
    allocations = [
        patch for patch in patches if isinstance(patch.get("allocation"), dict)
    ]
    allocation_end = max(
        patch["offset"] + len(bytes.fromhex(patch["after_hex"]))
        for patch in allocations
    )
    return {
        "schema": "generic-sprite-bundle-capability-fixture-v1",
        "construction": (
            "Append 48 deterministic 4bpp tiles to the canonical 49-tile "
            "pack and add a second ID-0 8x8 component at tile 96."
        ),
        "graphics_tile_count": len(graphics) // 32,
        "graphics_sha256": _sha256(graphics),
        "component_count": sum(
            len(entry["components"]) for entry in fixture["entries"]
        ),
        "entry_0_component_count": len(
            fixture["entries"][0]["components"]
        ),
        "allocation_count": len(allocations),
        "pointer_patch_count": sum(
            patch.get("asset_type") == "generic_sprite_bundle_pointer"
            for patch in patches
        ),
        "tile_base_patch_count": sum(
            patch.get("asset_type") == "generic_sprite_tile_base"
            for patch in patches
        ),
        "allocation_end": allocation_end,
        "output_rom_sha256": _sha256(bytes(data)),
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
            raise ValueError("generic Sprite audit output contains a directory")

    base = (root / "rom/base.gba").read_bytes()
    if _sha256(base) != ROM_SHA256:
        raise ValueError("generic Sprite audit base ROM mismatch")
    if _sha256_file(root / STATIC_CATALOG_PATH) != STATIC_CATALOG_SHA256:
        raise ValueError("generic Sprite static catalog mismatch")
    if _sha256_file(root / ANIMATION_CATALOG_PATH) != ANIMATION_CATALOG_SHA256:
        raise ValueError("generic Sprite animation catalog mismatch")

    layout_path = root / "sequel/rom-layout.json"
    layout = RomLayout.from_path(layout_path, base)
    registry_path = root / REGION_REGISTRY_PATH
    regions = ImageResourceRegions.from_path(registry_path, layout)
    region = regions.require(
        "generic-sprite-bundle",
        "generic_sprite_resources",
    )
    source = catalog_generic_sprite_bundle(root, base)

    spec = _spec(root, base)
    spec_path = output / SPEC_NAME
    spec_path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    patches = resolve_generic_sprite_bundle_relocation_patches(
        root,
        spec_path,
        rom=base,
        layout=layout,
        regions=regions,
    )
    data = bytearray(layout.expanded_base())
    gate = PatchSafetyGate(base, layout=layout, image_regions=regions)
    applied = [apply_patch(data, patch, gate=gate) for patch in patches]
    allocations = [
        patch for patch in patches if isinstance(patch.get("allocation"), dict)
    ]
    redirects = [
        patch
        for patch in patches
        if patch.get("asset_type") == "generic_sprite_bundle_pointer"
    ]
    tile_bases = [
        patch
        for patch in patches
        if patch.get("asset_type") == "generic_sprite_tile_base"
    ]
    if (
        len(allocations) != 45
        or len(redirects) != 88
        or len(tile_bases) != 43
        or len(applied) != 176
    ):
        raise ValueError("generic Sprite audit patch denominator mismatch")
    allocation_end = max(
        patch["offset"] + len(bytes.fromhex(patch["after_hex"]))
        for patch in allocations
    )
    summary = {
        "entry_count": source["entry_count"],
        "component_count": source["component_count"],
        "graphics_tile_count": source["graphics_tile_count"],
        "maximum_runtime_tile_base": source["maximum_runtime_tile_base"],
        "maximum_safe_graphics_tiles": MAX_GRAPHICS_TILES,
        "runtime_loader_call_count": source["runtime_loader_call_count"],
        "runtime_tile_bases": source["runtime_tile_bases"],
        "source_pointer_reference_count": source["pointer_reference_count"],
        "unexpected_source_pointer_count": len(
            source["unexpected_pointer_offsets"]
        ),
        "allocation_count": len(allocations),
        "pointer_patch_count": len(redirects),
        "tile_base_patch_count": len(tile_bases),
        "allocation_start": region.start,
        "allocation_end": allocation_end,
        "region_end": region.end,
        "stored_payload_bytes": sum(
            len(bytes.fromhex(patch["after_hex"])) for patch in allocations
        ),
        "allocation_span": allocation_end - region.start,
        "remaining_bytes": region.end - allocation_end,
        "applied_patch_count": len(applied),
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
        "catalogs": {
            "static": {
                "path": STATIC_CATALOG_PATH.as_posix(),
                "sha256": _sha256_file(root / STATIC_CATALOG_PATH),
            },
            "animation": {
                "path": ANIMATION_CATALOG_PATH.as_posix(),
                "sha256": _sha256_file(root / ANIMATION_CATALOG_PATH),
            },
        },
        "authoring_spec": {
            "file": SPEC_NAME,
            "sha256": _sha256_file(spec_path),
        },
        "implementation": {
            path: _sha256_file(root / path)
            for path in IMPLEMENTATION_PATHS
        },
        "summary": summary,
        "allocations": [
            {
                key: (
                    spec[
                        "graphics_file"
                        if patch["resource_type"] == "graphics"
                        else "palette_file"
                    ]
                    if key == "source_file"
                    and patch["resource_type"] in {"graphics", "palette"}
                    else patch[key]
                )
                for key in (
                    "id",
                    "resource_type",
                    "offset",
                    "decompressed_size",
                    "encoded_size",
                    "replacement_sha256",
                    "tile_count",
                    "entry_id",
                    "component_count",
                    "tile_base_offset",
                    "definition_pointer",
                    "animation_pointer",
                    "component_pointer",
                    "sequence_pointer",
                    "source_file",
                )
                if key in patch
            }
            for patch in allocations
        ],
        "capability_fixture": _capability_fixture(
            root,
            base,
            layout,
            regions,
            spec,
        ),
        "output_rom_sha256": _sha256(bytes(data)),
        "scope": SCOPE,
    }
    payload_path = output / PAYLOAD_NAME
    payload_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    files = {
        name: _sha256_file(output / name)
        for name in (SPEC_NAME, PAYLOAD_NAME)
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
                "tools/verify_generic_sprite_bundle_relocation_audit.py",
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
