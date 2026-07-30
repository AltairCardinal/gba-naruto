#!/usr/bin/env python3
"""Independently verify the full tile-assets relocation artifact."""

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
from tools.rom_layout import RomLayout


ROM_BASE = 0x08000000
TABLE_OFFSET = 0x5A320C
TABLE_ENTRY_COUNT = 79
TABLE_ENTRY_SIZE = 0x44
TABLE_SHA256 = "0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73"
ARTIFACT_ID = "tile-asset-resource-relocation-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
PAYLOAD_SCHEMA = "tile-asset-resource-relocation-audit-v1"
SENTINELS = {13, 31, 32, 46}
ROLE_WORDS = {
    "A": {"graphics": 3, "tilemap": 4, "palette": 5},
    "B": {"graphics": 6, "tilemap": 7, "palette": 8},
    "C": {"graphics": 10, "tilemap": 11, "palette": 12},
    "D": {"graphics": 14, "tilemap": 15, "palette": 16},
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _pointer(value: object) -> int:
    return value if isinstance(value, int) else int(str(value), 0)


def _read_sources(
    rom: bytes,
    catalog: dict[str, Any],
) -> dict[int, dict[str, Any]]:
    table = rom[
        TABLE_OFFSET : TABLE_OFFSET + TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
    ]
    if _sha256(table) != TABLE_SHA256:
        raise ValueError("tile-assets table SHA-256 mismatch")
    descriptors = catalog.get("descriptors")
    if not isinstance(descriptors, list) or len(descriptors) != 79:
        raise ValueError("tile-assets descriptor denominator mismatch")
    resources: dict[int, dict[str, Any]] = {}
    for descriptor_id, descriptor in enumerate(descriptors):
        descriptor_offset = TABLE_OFFSET + descriptor_id * TABLE_ENTRY_SIZE
        raw = table[
            descriptor_id * TABLE_ENTRY_SIZE :
            (descriptor_id + 1) * TABLE_ENTRY_SIZE
        ]
        words = list(struct.unpack("<17I", raw))
        if (
            descriptor.get("descriptor_id") != descriptor_id
            or descriptor.get("descriptor_file_offset") != descriptor_offset
            or descriptor.get("raw_words")
            != [f"0x{word:08X}" for word in words]
        ):
            raise ValueError(f"descriptor {descriptor_id} provenance mismatch")
        layers = descriptor.get("layers")
        if descriptor_id in SENTINELS:
            if any(words) or descriptor.get("status") != "sentinel" or layers:
                raise ValueError(f"descriptor {descriptor_id} sentinel mismatch")
            continue
        if not isinstance(layers, list) or len(layers) != 4:
            raise ValueError(f"descriptor {descriptor_id} layer mismatch")
        for layer in layers:
            name = layer["name"]
            if name not in ROLE_WORDS:
                raise ValueError("unknown tile-assets layer")
            expected_map_size = (
                int(layer["definition"]["width_tiles"])
                * int(layer["definition"]["height_tiles"])
                * 2
            )
            for resource_type, word_index in ROLE_WORDS[name].items():
                pointer = words[word_index]
                pointer_text = layer.get(
                    {
                        "graphics": "gfx_pointer",
                        "tilemap": "tilemap_pointer",
                        "palette": "palette_pointer",
                    }[resource_type]
                )
                if not pointer:
                    if pointer_text is not None:
                        raise ValueError("zero pointer catalog mismatch")
                    continue
                if pointer != _pointer(pointer_text):
                    raise ValueError("descriptor pointer catalog mismatch")
                record = layer[
                    "gfx" if resource_type == "graphics" else resource_type
                ]
                offset = pointer - ROM_BASE
                if resource_type == "palette":
                    content = stored = rom[
                        offset : offset + int(record["size"])
                    ]
                    if (
                        len(content) != int(record["size"])
                        or _sha256(content) != record["sha256"]
                    ):
                        raise ValueError("palette source mismatch")
                else:
                    stored = read_lz77_record(rom, offset)
                    content = lz77_decompress(rom, offset)
                    if (
                        len(stored) != int(record["compressed_size"])
                        or _sha256(stored) != record["compressed_sha256"]
                        or len(content) != int(record["decompressed_size"])
                        or _sha256(content) != record["decompressed_sha256"]
                    ):
                        raise ValueError(
                            f"{resource_type} source mismatch"
                        )
                row = resources.setdefault(
                    pointer,
                    {
                        "resource_type": resource_type,
                        "source_pointer": f"0x{pointer:08X}",
                        "source_offset": offset,
                        "source_sha256": _sha256(content),
                        "source_size": len(content),
                        "source_content": content,
                        "source_stored": stored,
                        "storage_kind": (
                            "raw" if resource_type == "palette" else "gba-lz77"
                        ),
                        "bits_per_pixel": set(),
                        "aliases": [],
                    },
                )
                if (
                    row["resource_type"] != resource_type
                    or row["source_content"] != content
                ):
                    raise ValueError("source pointer identity conflict")
                row["bits_per_pixel"].add(int(layer["bits_per_pixel"]))
                row["aliases"].append(
                    {
                        "descriptor_id": descriptor_id,
                        "layer": name,
                        "layer_status": layer["status"],
                        "resource_type": resource_type,
                        "pointer_offset": descriptor_offset + word_index * 4,
                        "expected_size": (
                            expected_map_size
                            if resource_type == "tilemap"
                            else (
                                int(layer["palette_color_count"]) * 2
                                if resource_type == "palette"
                                else len(content)
                            )
                        ),
                    }
                )

    counts = {
        kind: sum(row["resource_type"] == kind for row in resources.values())
        for kind in ("graphics", "tilemap", "palette")
    }
    if (
        len(resources) != 323
        or counts != {"graphics": 107, "tilemap": 108, "palette": 108}
        or sum(len(row["aliases"]) for row in resources.values()) != 709
    ):
        raise ValueError("independent tile-assets denominator mismatch")
    targets = set(resources)
    actual: dict[int, set[int]] = {pointer: set() for pointer in targets}
    for offset in range(0, len(rom) - 3, 4):
        value = struct.unpack_from("<I", rom, offset)[0]
        if value in actual:
            actual[value].add(offset)
    for pointer, row in resources.items():
        row["bits_per_pixel"] = sorted(row["bits_per_pixel"])
        row["aliases"].sort(key=lambda item: item["pointer_offset"])
        expected = {alias["pointer_offset"] for alias in row["aliases"]}
        if actual[pointer] != expected:
            raise ValueError(
                f"pointer 0x{pointer:08X} exact reference mismatch"
            )
    return dict(sorted(resources.items()))


def _validate_source_layers(
    catalog: dict[str, Any],
    resources: dict[int, dict[str, Any]],
) -> None:
    for descriptor in catalog["descriptors"]:
        if descriptor["descriptor_id"] in SENTINELS:
            continue
        for layer in descriptor["layers"]:
            if layer["status"] != "complete":
                continue
            graphics = resources[_pointer(layer["gfx_pointer"])]["source_content"]
            tilemap = resources[
                _pointer(layer["tilemap_pointer"])
            ]["source_content"]
            palette = resources[
                _pointer(layer["palette_pointer"])
            ]["source_content"]
            bpp = int(layer["bits_per_pixel"])
            bytes_per_tile = bpp * 8
            expected_map_size = (
                int(layer["definition"]["width_tiles"])
                * int(layer["definition"]["height_tiles"])
                * 2
            )
            expected_palette_size = int(layer["palette_color_count"]) * 2
            if (
                not graphics
                or len(graphics) % bytes_per_tile
                or len(graphics) // bytes_per_tile > 1024
                or len(tilemap) != expected_map_size
                or len(palette) != expected_palette_size
            ):
                raise ValueError("independent linked layer geometry mismatch")
            if (
                bpp == 8
                and max(graphics, default=0)
                >= int(layer["palette_color_count"])
            ):
                raise ValueError("independent graphics pixel index mismatch")
            tile_count = len(graphics) // bytes_per_tile
            for offset in range(0, len(tilemap), 2):
                cell = int.from_bytes(tilemap[offset : offset + 2], "little")
                if cell & 0x03FF >= tile_count:
                    raise ValueError("independent tile index mismatch")
                if cell >> 12:
                    raise ValueError("independent source palette bank mismatch")


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
        expected_command = [
            "python3",
            "tools/verify_tile_asset_resource_relocation_audit.py",
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
            != {"command": expected_command, "exit_code": 0}
        ):
            raise ValueError("promotion manifest contract mismatch")
        if payload.get("schema") != PAYLOAD_SCHEMA:
            raise ValueError("audit payload schema mismatch")
        if (
            promotion.get("scope") != payload.get("scope")
            or promotion.get("summary") != payload.get("summary")
        ):
            raise ValueError("promotion scope/summary mismatch")

        base_spec = payload["base_rom"]
        base = (root / base_spec["path"]).read_bytes()
        if (
            len(base) != int(base_spec["size"])
            or _sha256(base) != base_spec["sha256"]
        ):
            raise ValueError("base ROM provenance mismatch")
        layout_path = root / payload["layout"]["path"]
        if _sha256_file(layout_path) != payload["layout"]["sha256"]:
            raise ValueError("layout SHA-256 mismatch")
        layout = RomLayout.from_path(layout_path, base)
        target_size = layout.target_rom_size
        fill_byte = layout.fill_byte
        partition = next(
            row
            for row in layout.partitions
            if row.id == payload["layout"]["partition"]
        )
        partition_start = partition.start
        partition_end = partition.end
        if (
            payload["layout"]["partition"] != "sequel-image-assets"
            or payload["layout"]["owner"] != "sequel_image_assets"
            or partition.id != "sequel-image-assets"
            or partition.owner != "sequel_image_assets"
            or partition.origin != "expanded_ff"
            or partition.start != 0x800000
            or partition.end != 0xC00000
            or target_size != 0x1000000
            or target_size != payload["layout"]["target_rom_size"]
        ):
            raise ValueError("image partition contract mismatch")

        catalog_path = root / payload["catalog"]["path"]
        catalog_bytes = catalog_path.read_bytes()
        catalog = json.loads(catalog_bytes)
        if (
            _sha256(catalog_bytes) != payload["catalog"]["sha256"]
            or catalog.get("schema") != "tile-assets-bg-export-v2"
            or catalog["source_table"]["sha256"]
            != payload["catalog"]["table_sha256"]
        ):
            raise ValueError("tile-assets catalog provenance mismatch")
        resources = _read_sources(base, catalog)
        _validate_source_layers(catalog, resources)

        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        if _sha256_file(spec_path) != payload["authoring_spec"]["sha256"]:
            raise ValueError("authoring spec SHA-256 mismatch")
        expected_spec_keys = {
            "schema",
            "description",
            "base_rom_sha256",
            "source_catalog",
            "source_catalog_sha256",
            "partition",
            "owner",
            "edits",
        }
        if (
            set(spec) != expected_spec_keys
            or spec["schema"] != "tile-asset-resource-import-v1"
            or spec["base_rom_sha256"] != _sha256(base)
            or spec["source_catalog"] != payload["catalog"]["path"]
            or spec["source_catalog_sha256"] != _sha256(catalog_bytes)
            or spec["partition"] != partition.id
            or spec["owner"] != partition.owner
            or len(spec["edits"]) != 323
        ):
            raise ValueError("authoring preservation spec contract mismatch")
        expected_edit_keys = {
            "id",
            "resource_type",
            "source_pointer",
            "source_sha256",
            "expected_pointer_offsets",
        }
        for edit, resource in zip(spec["edits"], resources.values()):
            if (
                set(edit) != expected_edit_keys
                or edit["id"]
                != (
                    f"{resource['resource_type']}-"
                    f"{resource['source_offset']:06x}-relocation"
                )
                or edit["resource_type"] != resource["resource_type"]
                or edit["source_pointer"] != resource["source_pointer"]
                or edit["source_sha256"] != resource["source_sha256"]
                or edit["expected_pointer_offsets"]
                != [
                    alias["pointer_offset"]
                    for alias in resource["aliases"]
                ]
            ):
                raise ValueError("authoring preservation edit contract mismatch")

        expected_implementation_paths = {
            "tools/import_tile_asset_resources.py",
            "tools/rom_layout.py",
            "tools/patch_safety.py",
            "tools/build_mod.py",
        }
        if set(payload["implementation"]) != expected_implementation_paths:
            raise ValueError("implementation hash path set mismatch")
        for relative, expected in payload["implementation"].items():
            if _sha256_file(root / relative) != expected:
                raise ValueError(f"implementation hash mismatch: {relative}")

        output = bytearray(
            base + bytes([fill_byte]) * (target_size - len(base))
        )
        cursor = partition_start
        expected_rows = []
        for pointer, resource in resources.items():
            cursor = (cursor + 3) & ~3
            encoded = (
                resource["source_content"]
                if resource["storage_kind"] == "raw"
                else encode_gba_lz77(resource["source_content"])
            )
            end = cursor + len(encoded)
            if end > partition_end:
                raise ValueError("independent relocation exceeds partition")
            output[cursor:end] = encoded
            new_pointer = ROM_BASE + cursor
            for alias in resource["aliases"]:
                offset = alias["pointer_offset"]
                if struct.unpack_from("<I", base, offset)[0] != pointer:
                    raise ValueError("descriptor pointer precondition mismatch")
                struct.pack_into("<I", output, offset, new_pointer)
            expected_rows.append(
                {
                    "resource_type": resource["resource_type"],
                    "source_pointer": resource["source_pointer"],
                    "source_offset": resource["source_offset"],
                    "source_sha256": resource["source_sha256"],
                    "source_size": resource["source_size"],
                    "source_stored_size": len(resource["source_stored"]),
                    "storage_kind": resource["storage_kind"],
                    "bits_per_pixel": resource["bits_per_pixel"],
                    "allocation_offset": cursor,
                    "relocated_stored_size": len(encoded),
                    "relocated_stored_sha256": _sha256(encoded),
                    "new_pointer": f"0x{new_pointer:08X}",
                    "logical_pointer_count": len(resource["aliases"]),
                    "pointer_offsets": [
                        alias["pointer_offset"] for alias in resource["aliases"]
                    ],
                    "unexpected_pointer_offsets": [],
                }
            )
            cursor = end
        if payload["resources"] != expected_rows:
            raise ValueError("resource relocation records mismatch")
        type_counts = {
            kind: sum(row["resource_type"] == kind for row in expected_rows)
            for kind in ("graphics", "tilemap", "palette")
        }
        expected_summary = {
            "descriptor_count": 79,
            "complete_layer_count": 236,
            "partial_layer_count": 1,
            "resource_count": 323,
            "resource_type_counts": type_counts,
            "logical_pointer_count": 709,
            "unexpected_pointer_count": 0,
            "allocation_start": partition_start,
            "allocation_end": cursor,
            "allocated_span_bytes": cursor - partition_start,
            "relocated_stored_bytes": sum(
                row["relocated_stored_size"] for row in expected_rows
            ),
            "source_stored_bytes": sum(
                row["source_stored_size"] for row in expected_rows
            ),
            "source_content_bytes": sum(
                row["source_size"] for row in expected_rows
            ),
            "partition_end": partition_end,
            "remaining_bytes": partition_end - cursor,
        }
        if payload["summary"] != expected_summary:
            raise ValueError("relocation summary mismatch")
        rebuilt_output_rom_sha256 = _sha256(bytes(output))
        if rebuilt_output_rom_sha256 != payload["output_rom_sha256"]:
            raise ValueError("rebuilt output ROM SHA-256 mismatch")
        verified_resources = len(expected_rows)
        verified_pointers = 709
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
        rebuilt_output_rom_sha256 = ""
        verified_resources = 0
        verified_pointers = 0
    return {
        "schema": "tile-asset-resource-relocation-verification-v1",
        "errors": errors,
        "verified_resources": verified_resources,
        "verified_pointers": verified_pointers,
        "rebuilt_output_rom_sha256": rebuilt_output_rom_sha256,
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
