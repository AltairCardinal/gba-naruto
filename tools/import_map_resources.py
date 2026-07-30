#!/usr/bin/env python3
"""Build guarded in-place patches for all deduplicated battle-map resources."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import encode_gba_lz77, read_lz77_record


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/map-canvases-v1/manifest.json")
CATALOG_SHA256 = "12a231a570a1cb9e56bec7e2f87cb6de4ac48d673765b1ba536bbc5b0137e19c"
SPEC_SCHEMA = "map-resource-import-v1"
ROLE_POINTER_OFFSETS = {
    "tile_graphics": 4,
    "bg_palette": 8,
    "primary_layout": 12,
    "alternate_layout": 16,
    "metatile_definitions": 20,
    "collision_grid": 24,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _catalog_resources(
    root: Path,
    catalog: dict[str, Any],
    rom: bytes,
) -> dict[tuple[str, str], dict[str, Any]]:
    if catalog.get("schema") != "map-canvases-v1":
        raise ValueError("map resource catalog schema mismatch")
    entries = catalog.get("entries")
    if not isinstance(entries, list) or len(entries) != 47:
        raise ValueError("map resource catalog must contain 47 entries")

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    logical_reference_count = 0
    for entry in entries:
        map_id = entry.get("map_id")
        header = entry.get("header", {})
        resources = entry.get("resources")
        if not isinstance(map_id, int) or not isinstance(resources, dict):
            raise ValueError("invalid map resource catalog entry")
        header_offset = header.get("file_offset")
        if not isinstance(header_offset, int):
            raise ValueError(f"map {map_id} header offset is invalid")
        for role, pointer_delta in ROLE_POINTER_OFFSETS.items():
            resource = resources.get(role)
            if resource is None:
                continue
            logical_reference_count += 1
            digest = resource.get("sha256")
            offset = resource.get("file_offset")
            size = resource.get("decompressed_size")
            output_bin = resource.get("output_bin")
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or not isinstance(offset, int)
                or not isinstance(size, int)
                or size <= 0
                or not isinstance(output_bin, str)
            ):
                raise ValueError(f"map {map_id} {role} catalog record is invalid")
            content = lz77_decompress(rom, offset)
            if len(content) != size or _sha256(content) != digest:
                raise ValueError(
                    f"map {map_id} {role} does not match base ROM"
                )
            key = (role, digest)
            row = grouped.setdefault(
                key,
                {
                    "resource_type": role,
                    "resource_sha256": digest,
                    "decompressed_size": size,
                    "source_file": output_bin,
                    "physical_offsets": set(),
                    "logical_aliases": [],
                },
            )
            if (
                row["decompressed_size"] != size
                or row["source_file"] != output_bin
            ):
                raise ValueError(f"conflicting map resource identity: {key}")
            row["physical_offsets"].add(offset)
            row["logical_aliases"].append(
                {
                    "map_id": map_id,
                    "resource_type": role,
                    "header_pointer_offset": header_offset + pointer_delta,
                    "physical_offset": offset,
                }
            )

    physical_count = sum(
        len(row["physical_offsets"]) for row in grouped.values()
    )
    if (
        len(grouped) != 166
        or physical_count != 217
        or logical_reference_count != 249
    ):
        raise ValueError(
            "map resource denominator mismatch: "
            f"{len(grouped)}/166 content, {physical_count}/217 physical, "
            f"{logical_reference_count}/249 logical"
        )
    for row in grouped.values():
        row["physical_offsets"] = sorted(row["physical_offsets"])
        row["logical_aliases"] = sorted(
            row["logical_aliases"],
            key=lambda item: (
                item["map_id"],
                item["header_pointer_offset"],
            ),
        )
    return grouped


def _validate_resource_payload(role: str, content: bytes) -> None:
    if role == "tile_graphics":
        valid = len(content) % 32 == 0
        message = "complete 32-byte 4bpp tiles"
    elif role == "bg_palette":
        valid = len(content) <= 512 and len(content) % 32 == 0
        message = "complete 32-byte BGR555 palette banks"
    elif role in {"primary_layout", "alternate_layout"}:
        valid = len(content) % 4 == 0
        message = "complete little-endian u32 layout cells"
    elif role == "metatile_definitions":
        valid = len(content) % 8 == 0
        message = "complete 8-byte metatile definitions"
    elif role == "collision_grid":
        valid = len(content) % 2 == 0
        message = "complete little-endian u16 collision cells"
    else:
        raise ValueError(f"unsupported map resource type: {role}")
    if not content or not valid:
        raise ValueError(f"{role} must contain {message}")


def _validate_linked_map_view(
    catalog: dict[str, Any],
    replacements: dict[tuple[str, str], bytes],
    rom: bytes,
) -> None:
    def content(role: str, source: dict[str, Any]) -> bytes:
        key = (role, source["sha256"])
        return replacements.get(
            key,
            lz77_decompress(rom, int(source["file_offset"])),
        )

    for entry in catalog["entries"]:
        map_id = int(entry["map_id"])
        width_tiles, height_tiles = (
            int(value) for value in entry["dimensions_tiles"]
        )
        coarse_width = width_tiles // 4
        coarse_height = height_tiles // 2
        sources = entry["resources"]
        graphics = content("tile_graphics", sources["tile_graphics"])
        palette = content("bg_palette", sources["bg_palette"])
        metatiles = content(
            "metatile_definitions",
            sources["metatile_definitions"],
        )
        collision = content("collision_grid", sources["collision_grid"])
        layouts = {
            "primary_layout": content(
                "primary_layout",
                sources["primary_layout"],
            )
        }
        if sources["alternate_layout"] is not None:
            layouts["alternate_layout"] = content(
                "alternate_layout",
                sources["alternate_layout"],
            )

        expected_layout_size = coarse_width * coarse_height * 4
        expected_collision_size = coarse_width * coarse_height * 2
        if len(collision) != expected_collision_size:
            raise ValueError(
                f"map {map_id} collision grid size {len(collision)} "
                f"does not match {expected_collision_size}"
            )
        metatile_count = len(metatiles) // 8
        tile_count = len(graphics) // 32
        palette_bank_count = len(palette) // 32
        for role, layout in layouts.items():
            if len(layout) != expected_layout_size:
                raise ValueError(
                    f"map {map_id} {role} size {len(layout)} "
                    f"does not match {expected_layout_size}"
                )
            for offset in range(0, len(layout), 4):
                packed = int.from_bytes(layout[offset : offset + 4], "little")
                for metatile_index in (packed & 0xFFFF, packed >> 16):
                    if metatile_index >= metatile_count:
                        raise ValueError(
                            f"map {map_id} {role} metatile index "
                            f"{metatile_index} exceeds {metatile_count}"
                        )
        for offset in range(0, len(metatiles), 2):
            value = int.from_bytes(
                metatiles[offset : offset + 2],
                "little",
            )
            tile_index = value & 0x03FF
            palette_bank = (value >> 12) & 0x0F
            if tile_index >= tile_count:
                raise ValueError(
                    f"map {map_id} metatile tile index {tile_index} "
                    f"exceeds {tile_count}"
                )
            if palette_bank >= palette_bank_count:
                raise ValueError(
                    f"map {map_id} metatile palette bank {palette_bank} "
                    f"exceeds {palette_bank_count}"
                )


def resolve_map_resource_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes | None = None,
) -> list[dict[str, Any]]:
    root = root.resolve()
    spec_path = _resolve_path(root, str(spec_path))
    spec = _load_json(spec_path)
    if spec.get("schema") != SPEC_SCHEMA:
        raise ValueError(f"expected schema {SPEC_SCHEMA}")
    if spec.get("source_catalog") != CATALOG_PATH.as_posix():
        raise ValueError("map resource source catalog path mismatch")

    catalog_path = root / CATALOG_PATH
    catalog_bytes = catalog_path.read_bytes()
    if _sha256(catalog_bytes) != CATALOG_SHA256:
        raise ValueError("map resource catalog hash mismatch")
    catalog = json.loads(catalog_bytes)

    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("map resource base ROM hash mismatch")
    resources = _catalog_resources(root, catalog, base)

    edits = spec.get("edits")
    if not isinstance(edits, list):
        raise ValueError("map resource edits must be a list")
    seen: set[tuple[str, str]] = set()
    replacements: dict[tuple[str, str], bytes] = {}
    prepared: list[
        tuple[dict[str, Any], dict[str, Any], bytes, bytes, str]
    ] = []
    planned: list[dict[str, Any]] = []
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("map resource edit must be an object")
        role = edit.get("resource_type")
        digest = edit.get("resource_sha256")
        key = (role, digest)
        if key in seen:
            raise ValueError(f"duplicate map resource edit: {role}/{digest}")
        seen.add(key)
        resource = resources.get(key)
        if resource is None:
            raise ValueError(f"unknown map resource: {role}/{digest}")

        expected = edit.get("expected")
        if not isinstance(expected, dict):
            raise ValueError("map resource edit is missing expected provenance")
        if expected.get("decompressed_size") != resource["decompressed_size"]:
            raise ValueError("map resource decompressed size provenance mismatch")
        if expected.get("physical_offsets") != resource["physical_offsets"]:
            raise ValueError("map resource physical offset provenance mismatch")

        source_value = edit.get("source_file")
        if not isinstance(source_value, str):
            raise ValueError("map resource source_file must be a path")
        content = _resolve_path(root, source_value).read_bytes()
        if len(content) != resource["decompressed_size"]:
            raise ValueError(
                f"{role} replacement size {len(content)} does not match "
                f"{resource['decompressed_size']}"
            )
        _validate_resource_payload(role, content)
        if _sha256(content) == digest:
            continue

        encoded = encode_gba_lz77(content)
        replacements[key] = content
        prepared.append((edit, resource, content, encoded, source_value))

    if replacements:
        _validate_linked_map_view(catalog, replacements, base)

    for edit, resource, content, encoded, source_value in prepared:
        role = resource["resource_type"]
        digest = resource["resource_sha256"]
        physical_plans: list[dict[str, Any]] = []
        overflow: list[tuple[int, int]] = []
        for offset in resource["physical_offsets"]:
            original_record = read_lz77_record(base, offset)
            slot_content = lz77_decompress(base, offset)
            if (
                len(slot_content) != resource["decompressed_size"]
                or _sha256(slot_content) != digest
            ):
                raise ValueError(
                    f"map resource physical slot 0x{offset:06X} "
                    "does not match catalog provenance"
                )
            if len(encoded) > len(original_record):
                overflow.append((offset, len(original_record)))
                continue
            after = encoded + original_record[len(encoded) :]
            physical_plans.append(
                {
                    "offset": offset,
                    "before": original_record,
                    "after": after,
                    "slot_size": len(original_record),
                }
            )
        if overflow:
            detail = ", ".join(
                f"0x{offset:06X}:{size}" for offset, size in overflow
            )
            raise ValueError(
                f"{role}/{digest} encoded size {len(encoded)} does not fit "
                f"every physical slot ({detail})"
            )

        affected_maps = sorted(
            {item["map_id"] for item in resource["logical_aliases"]}
        )
        for item in physical_plans:
            planned.append(
                {
                    "id": (
                        f"{edit.get('id', 'map-resource')}-"
                        f"{item['offset']:06x}"
                    ),
                    "type": "bytes",
                    "asset_type": "map_resource",
                    "resource_type": role,
                    "resource_sha256": digest,
                    "replacement_sha256": _sha256(content),
                    "offset": item["offset"],
                    "before_hex": item["before"].hex(),
                    "after_hex": item["after"].hex(),
                    "encoded_size": len(encoded),
                    "slot_size": item["slot_size"],
                    "padding_bytes": item["slot_size"] - len(encoded),
                    "affected_maps": affected_maps,
                    "logical_aliases": resource["logical_aliases"],
                    "source_file": source_value,
                }
            )

    return sorted(planned, key=lambda item: item["offset"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build guarded in-place patches for battle-map resources."
    )
    parser.add_argument("spec", type=Path)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    patches = resolve_map_resource_patches(args.root, args.spec)
    payload = {"schema": "map-resource-patches-v1", "patches": patches}
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
