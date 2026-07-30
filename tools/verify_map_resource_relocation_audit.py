#!/usr/bin/env python3
"""Independently verify the full battle-map resource relocation artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import encode_gba_lz77, read_lz77_record
from tools.image_resource_regions import ImageResourceRegions
from tools.rom_layout import RomLayout


ROM_BASE = 0x08000000
CATALOG_PATH = "artifacts/map-canvases-v1/manifest.json"
CATALOG_SHA256 = "12a231a570a1cb9e56bec7e2f87cb6de4ac48d673765b1ba536bbc5b0137e19c"
REGISTRY_PATH = "sequel/image-resource-regions.json"
ARTIFACT_ID = "map-resource-relocation-v1"
PAYLOAD_NAME = "relocation-audit.json"
EXPECTED_SCOPE = {
    "proved": (
        "All 166 deduplicated map contents and 249 exact map-header "
        "pointers relocate into the registered map image region."
    ),
    "editable": (
        "Map graphics, palettes, layouts, metatiles and collision "
        "grids may change size while every linked map remains valid."
    ),
    "not_proved": (
        "Modified-map runtime pixel equivalence, dynamic overlays, "
        "camera behavior or final collision gameplay semantics."
    ),
}
SPEC_NAME = "full-relocation-spec.json"
PAYLOAD_SCHEMA = "map-resource-relocation-audit-v1"
ROLE_POINTER_OFFSETS = {
    "tile_graphics": 4,
    "bg_palette": 8,
    "primary_layout": 12,
    "alternate_layout": 16,
    "metatile_definitions": 20,
    "collision_grid": 24,
}
ROLES = tuple(ROLE_POINTER_OFFSETS)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _read_resources(
    rom: bytes,
    catalog: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    if catalog.get("schema") != "map-canvases-v1":
        raise ValueError("independent map catalog schema mismatch")
    entries = catalog.get("entries")
    if not isinstance(entries, list) or len(entries) != 47:
        raise ValueError("independent map denominator mismatch")
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in entries:
        map_id = entry.get("map_id")
        header_offset = entry.get("header", {}).get("file_offset")
        sources = entry.get("resources")
        if (
            not isinstance(map_id, int)
            or not isinstance(header_offset, int)
            or not isinstance(sources, dict)
        ):
            raise ValueError("independent map entry identity mismatch")
        for role, pointer_delta in ROLE_POINTER_OFFSETS.items():
            source = sources.get(role)
            if source is None:
                continue
            offset = source.get("file_offset")
            size = source.get("decompressed_size")
            digest = source.get("sha256")
            if (
                not isinstance(offset, int)
                or not isinstance(size, int)
                or not isinstance(digest, str)
            ):
                raise ValueError("independent map resource record mismatch")
            content = lz77_decompress(rom, offset)
            if len(content) != size or _sha256(content) != digest:
                raise ValueError("independent map resource content mismatch")
            key = (role, digest)
            row = grouped.setdefault(
                key,
                {
                    "resource_type": role,
                    "source_sha256": digest,
                    "source_size": size,
                    "physical_offsets": set(),
                    "logical_aliases": [],
                    "source_content": content,
                },
            )
            if row["source_size"] != size or row["source_content"] != content:
                raise ValueError("independent map dedup identity mismatch")
            row["physical_offsets"].add(offset)
            row["logical_aliases"].append(
                {
                    "map_id": map_id,
                    "header_pointer_offset": header_offset + pointer_delta,
                    "physical_offset": offset,
                }
            )

    targets: dict[int, set[int]] = {}
    for row in grouped.values():
        for offset in row["physical_offsets"]:
            targets[offset] = set()
        for alias in row["logical_aliases"]:
            targets[alias["physical_offset"]].add(
                alias["header_pointer_offset"]
            )
    actual = {offset: set() for offset in targets}
    pointers = {ROM_BASE + offset: offset for offset in targets}
    for pointer_offset in range(0, len(rom) - 3, 4):
        pointer = struct.unpack_from("<I", rom, pointer_offset)[0]
        source_offset = pointers.get(pointer)
        if source_offset is not None:
            actual[source_offset].add(pointer_offset)
    for source_offset, expected in targets.items():
        if actual[source_offset] != expected:
            raise ValueError(
                f"map source 0x{source_offset:06X} exact reference mismatch"
            )

    result = {}
    for key, row in grouped.items():
        row["physical_offsets"] = sorted(row["physical_offsets"])
        row["logical_aliases"].sort(
            key=lambda alias: alias["header_pointer_offset"]
        )
        row["source_pointers"] = [
            f"0x{ROM_BASE + offset:08X}"
            for offset in row["physical_offsets"]
        ]
        row["unexpected_pointer_offsets"] = []
        result[key] = row
    if (
        len(result) != 166
        or sum(len(row["physical_offsets"]) for row in result.values()) != 217
        or sum(len(row["logical_aliases"]) for row in result.values()) != 249
    ):
        raise ValueError("independent map resource denominator mismatch")
    return dict(
        sorted(
            result.items(),
            key=lambda item: (
                min(item[1]["physical_offsets"]),
                item[0][0],
                item[0][1],
            ),
        )
    )


def _validate_payload(role: str, content: bytes) -> None:
    valid = {
        "tile_graphics": bool(content) and len(content) % 32 == 0,
        "bg_palette": (
            bool(content) and len(content) <= 512 and len(content) % 32 == 0
        ),
        "primary_layout": bool(content) and len(content) % 4 == 0,
        "alternate_layout": bool(content) and len(content) % 4 == 0,
        "metatile_definitions": bool(content) and len(content) % 8 == 0,
        "collision_grid": bool(content) and len(content) % 2 == 0,
    }
    if role not in valid or not valid[role]:
        raise ValueError("independent map resource geometry mismatch")


def _validate_maps(
    catalog: dict[str, Any],
    resources: dict[tuple[str, str], dict[str, Any]],
) -> None:
    for entry in catalog["entries"]:
        map_id = int(entry["map_id"])
        width, height = (int(value) for value in entry["dimensions_tiles"])
        coarse_width = width // 4
        coarse_height = height // 2
        sources = entry["resources"]

        def content(role: str) -> bytes:
            source = sources[role]
            return resources[(role, source["sha256"])]["source_content"]

        graphics = content("tile_graphics")
        palette = content("bg_palette")
        metatiles = content("metatile_definitions")
        collision = content("collision_grid")
        layouts = {"primary_layout": content("primary_layout")}
        if sources["alternate_layout"] is not None:
            layouts["alternate_layout"] = content("alternate_layout")
        for role, value in (
            ("tile_graphics", graphics),
            ("bg_palette", palette),
            ("metatile_definitions", metatiles),
            ("collision_grid", collision),
            *layouts.items(),
        ):
            _validate_payload(role, value)
        if len(collision) != coarse_width * coarse_height * 2:
            raise ValueError("independent collision size mismatch")
        metatile_count = len(metatiles) // 8
        tile_count = len(graphics) // 32
        palette_count = len(palette) // 32
        for layout in layouts.values():
            if len(layout) != coarse_width * coarse_height * 4:
                raise ValueError("independent layout size mismatch")
            for offset in range(0, len(layout), 4):
                packed = int.from_bytes(layout[offset : offset + 4], "little")
                if (
                    packed & 0xFFFF >= metatile_count
                    or packed >> 16 >= metatile_count
                ):
                    raise ValueError("independent metatile index mismatch")
        for offset in range(0, len(metatiles), 2):
            cell = int.from_bytes(metatiles[offset : offset + 2], "little")
            if cell & 0x03FF >= tile_count:
                raise ValueError(
                    f"independent map {map_id} tile index mismatch"
                )
            if (cell >> 12) & 0x0F >= palette_count:
                raise ValueError(
                    f"independent map {map_id} palette bank mismatch"
                )


def verify_audit(root: Path, artifact: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        root = root.resolve()
        artifact = artifact.resolve()
        promotion_path = artifact / "manifest.json"
        payload_path = artifact / PAYLOAD_NAME
        spec_path = artifact / SPEC_NAME
        promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload_digest = _sha256_file(payload_path)
        expected_files = {
            PAYLOAD_NAME: payload_digest,
            SPEC_NAME: _sha256_file(spec_path),
        }
        actual_files = {
            path.relative_to(artifact).as_posix(): _sha256_file(path)
            for path in artifact.rglob("*")
            if path.is_file() and path != promotion_path
        }
        command = [
            "python3",
            "tools/verify_map_resource_relocation_audit.py",
            "--root",
            ".",
            "--artifact",
            f"artifacts/{ARTIFACT_ID}",
        ]
        if (
            promotion.get("schema") != "git-artifact-promotion-v1"
            or promotion.get("artifact_id") != ARTIFACT_ID
            or promotion.get("artifact_schema") != PAYLOAD_SCHEMA
            or promotion.get("artifact_status") != "accepted"
            or promotion.get("payload_file") != PAYLOAD_NAME
            or promotion.get("payload_sha256") != payload_digest
            or promotion.get("files") != expected_files
            or actual_files != expected_files
            or promotion.get("verifier")
            != {"command": command, "exit_code": 0}
        ):
            raise ValueError("map promotion manifest contract mismatch")
        if payload.get("schema") != PAYLOAD_SCHEMA:
            raise ValueError("map relocation payload schema mismatch")
        if (
            payload.get("scope") != EXPECTED_SCOPE
            or promotion.get("scope") != EXPECTED_SCOPE
            or promotion.get("summary") != payload.get("summary")
        ):
            raise ValueError("map promotion scope/summary mismatch")

        base_spec = payload["base_rom"]
        base = (root / base_spec["path"]).read_bytes()
        if (
            len(base) != base_spec["size"]
            or _sha256(base) != base_spec["sha256"]
        ):
            raise ValueError("map base ROM provenance mismatch")
        layout_path = root / payload["layout"]["path"]
        if _sha256_file(layout_path) != payload["layout"]["sha256"]:
            raise ValueError("map layout SHA-256 mismatch")
        layout = RomLayout.from_path(layout_path, base)
        if (
            layout.target_rom_size != 0x1000000
            or layout.target_rom_size != payload["layout"]["target_rom_size"]
        ):
            raise ValueError("map target ROM size mismatch")
        partition = next(
            row
            for row in layout.partitions
            if row.id == payload["layout"]["partition"]
        )
        if (
            partition.id != "sequel-image-assets"
            or partition.owner != "sequel_image_assets"
            or payload["layout"]["owner"] != partition.owner
        ):
            raise ValueError("map parent partition contract mismatch")
        registry_spec = payload["region_registry"]
        if registry_spec["path"] != REGISTRY_PATH:
            raise ValueError("map region registry path mismatch")
        registry_path = root / registry_spec["path"]
        if _sha256_file(registry_path) != registry_spec["sha256"]:
            raise ValueError("map region registry SHA-256 mismatch")
        regions = ImageResourceRegions.from_path(registry_path, layout)
        region = regions.require(
            str(registry_spec["region"]),
            str(registry_spec["owner"]),
        )
        if (
            regions.parent != partition
            or region.id != "map-resources"
            or region.owner != "map_resources"
            or region.start != 0x980000
            or region.end != 0xA80000
            or registry_spec["start"] != region.start
            or registry_spec["end"] != region.end
        ):
            raise ValueError("map region contract mismatch")

        catalog_path = root / payload["catalog"]["path"]
        catalog_bytes = catalog_path.read_bytes()
        if (
            payload["catalog"]["path"] != CATALOG_PATH
            or _sha256(catalog_bytes) != CATALOG_SHA256
            or payload["catalog"]["sha256"] != CATALOG_SHA256
        ):
            raise ValueError("map catalog provenance mismatch")
        catalog = json.loads(catalog_bytes)
        resources = _read_resources(base, catalog)
        _validate_maps(catalog, resources)

        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        if _sha256_file(spec_path) != payload["authoring_spec"]["sha256"]:
            raise ValueError("map authoring spec SHA-256 mismatch")
        expected_spec_keys = {
            "schema",
            "description",
            "base_rom_sha256",
            "source_catalog",
            "source_catalog_sha256",
            "partition",
            "owner",
            "region_registry",
            "region_registry_sha256",
            "region",
            "region_owner",
            "edits",
        }
        if (
            set(spec) != expected_spec_keys
            or spec["schema"] != "map-resource-relocation-v1"
            or spec["base_rom_sha256"] != _sha256(base)
            or spec["source_catalog"] != CATALOG_PATH
            or spec["source_catalog_sha256"] != CATALOG_SHA256
            or spec["partition"] != partition.id
            or spec["owner"] != partition.owner
            or spec["region_registry"] != REGISTRY_PATH
            or spec["region_registry_sha256"] != registry_spec["sha256"]
            or spec["region"] != region.id
            or spec["region_owner"] != region.owner
            or len(spec["edits"]) != 166
        ):
            raise ValueError("map preservation spec contract mismatch")
        expected_edit_keys = {
            "id",
            "resource_type",
            "source_sha256",
            "expected_physical_offsets",
            "expected_header_pointer_offsets",
        }
        for edit, resource in zip(spec["edits"], resources.values()):
            expected_id = (
                f"{resource['resource_type']}-"
                f"{resource['source_sha256'][:12]}-relocation"
            )
            if (
                set(edit) != expected_edit_keys
                or edit["id"] != expected_id
                or edit["resource_type"] != resource["resource_type"]
                or edit["source_sha256"] != resource["source_sha256"]
                or edit["expected_physical_offsets"]
                != resource["physical_offsets"]
                or edit["expected_header_pointer_offsets"]
                != [
                    alias["header_pointer_offset"]
                    for alias in resource["logical_aliases"]
                ]
            ):
                raise ValueError("map preservation edit contract mismatch")

        implementation_paths = {
            "tools/import_map_resource_relocations.py",
            "tools/import_map_resources.py",
            "tools/image_resource_regions.py",
            "tools/rom_layout.py",
            "tools/patch_safety.py",
            "tools/build_mod.py",
        }
        if set(payload["implementation"]) != implementation_paths:
            raise ValueError("map implementation hash path set mismatch")
        for relative, digest in payload["implementation"].items():
            if _sha256_file(root / relative) != digest:
                raise ValueError(f"map implementation hash mismatch: {relative}")

        output = bytearray(layout.expanded_base())
        cursor = region.start
        rows = []
        for resource in resources.values():
            cursor = (cursor + 3) & ~3
            encoded = encode_gba_lz77(resource["source_content"])
            end = cursor + len(encoded)
            if end > region.end:
                raise ValueError("independent map relocation exceeds region")
            output[cursor:end] = encoded
            new_pointer = ROM_BASE + cursor
            for alias in resource["logical_aliases"]:
                pointer_offset = alias["header_pointer_offset"]
                expected_pointer = ROM_BASE + alias["physical_offset"]
                if struct.unpack_from("<I", base, pointer_offset)[0] != expected_pointer:
                    raise ValueError("independent map pointer precondition mismatch")
                struct.pack_into("<I", output, pointer_offset, new_pointer)
            source_stored_sizes = [
                len(read_lz77_record(base, offset))
                for offset in resource["physical_offsets"]
            ]
            rows.append(
                {
                    "resource_type": resource["resource_type"],
                    "source_sha256": resource["source_sha256"],
                    "source_size": resource["source_size"],
                    "physical_offsets": resource["physical_offsets"],
                    "source_pointers": resource["source_pointers"],
                    "source_stored_sizes": source_stored_sizes,
                    "allocation_offset": cursor,
                    "relocated_stored_size": len(encoded),
                    "relocated_stored_sha256": _sha256(encoded),
                    "new_pointer": f"0x{new_pointer:08X}",
                    "logical_reference_count": len(
                        resource["logical_aliases"]
                    ),
                    "header_pointer_offsets": [
                        alias["header_pointer_offset"]
                        for alias in resource["logical_aliases"]
                    ],
                    "unexpected_pointer_offsets": [],
                }
            )
            cursor = end
        if payload["resources"] != rows:
            raise ValueError("map resource audit rows mismatch")
        type_counts = {
            role: sum(row["resource_type"] == role for row in rows)
            for role in (
                "alternate_layout",
                "bg_palette",
                "collision_grid",
                "metatile_definitions",
                "primary_layout",
                "tile_graphics",
            )
        }
        summary = {
            "map_count": 47,
            "content_resource_count": 166,
            "physical_source_count": 217,
            "logical_reference_count": 249,
            "resource_type_counts": type_counts,
            "unexpected_pointer_count": 0,
            "allocation_start": region.start,
            "allocation_end": cursor,
            "allocated_span_bytes": cursor - region.start,
            "relocated_stored_bytes": sum(
                row["relocated_stored_size"] for row in rows
            ),
            "source_physical_stored_bytes": sum(
                sum(row["source_stored_sizes"]) for row in rows
            ),
            "source_content_bytes": sum(row["source_size"] for row in rows),
            "region_end": region.end,
            "remaining_bytes": region.end - cursor,
        }
        if payload["summary"] != summary:
            raise ValueError("map relocation summary mismatch")
        rebuilt_hash = _sha256(bytes(output))
        if rebuilt_hash != payload["output_rom_sha256"]:
            raise ValueError("map rebuilt output ROM SHA-256 mismatch")
        verified_resources = 166
        verified_pointers = 249
    except (
        KeyError,
        IndexError,
        OSError,
        StopIteration,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        struct.error,
    ) as error:
        errors.append(str(error))
        rebuilt_hash = ""
        verified_resources = 0
        verified_pointers = 0
    return {
        "schema": "map-resource-relocation-verification-v1",
        "errors": errors,
        "verified_resources": verified_resources,
        "verified_pointers": verified_pointers,
        "rebuilt_output_rom_sha256": rebuilt_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path(f"artifacts/{ARTIFACT_ID}"),
    )
    args = parser.parse_args()
    artifact = (
        args.artifact
        if args.artifact.is_absolute()
        else args.root / args.artifact
    )
    result = verify_audit(args.root, artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
