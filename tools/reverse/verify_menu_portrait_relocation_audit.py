#!/usr/bin/env python3
"""Independently verify the full menu-portrait relocation artifact."""

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

from tools.image_resource_regions import ImageResourceRegions
from tools.rom_layout import RomLayout
from tools.verify_menu_portrait_writeback_audit import (
    _decompress_lz77,
    _encode_lz77,
)


ARTIFACT_ID = "menu-portrait-relocation-v1"
PAYLOAD_SCHEMA = "menu-portrait-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/menu-portraits-v1/manifest.json")
CATALOG_SHA256 = "cd54c20d774a2aa69c7a41db396ca344157320882602b03a00ccd83851a791b3"
REGISTRY_PATH = Path("sequel/image-resource-regions.json")
IMPLEMENTATION_PATHS = (
    "tools/import_menu_portrait_relocations.py",
    "tools/import_menu_portraits.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_menu_portrait_relocation_audit.py",
    "tools/verify_menu_portrait_relocation_audit.py",
    "tools/verify_menu_portrait_writeback_audit.py",
    "tools/gba_image_export.py",
    "tools/extract_tileset.py",
    "tools/export_menu_portraits.py",
)
EXPECTED_SCOPE = {
    "proved": (
        "All 70 graphics and 70 palette payloads, representing 74 logical "
        "portrait pairs and 311 portraits, relocate through all 622 exact "
        "pair-table pointer fields into the registered menu-portraits region."
    ),
    "editable": (
        "Indexed 80x80 portraits may replace their compressed 6400-byte OBJ "
        "stream and 128-byte BGR555 palette, including explicit pair-alias "
        "splits, without the original compressed-slot capacity limit."
    ),
    "not_proved": (
        "Arbitrary portrait dimensions, modified-resource runtime pixel "
        "equivalence, menu color transforms, transitions or final composition."
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def _pointer(value: object) -> int:
    if not isinstance(value, str):
        raise ValueError("portrait pointer is not hexadecimal")
    pointer = int(value, 0)
    if pointer < 0x08000000:
        raise ValueError("portrait pointer is outside GBA ROM")
    return pointer


def _catalog_resources(
    root: Path,
    base: bytes,
    catalog: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    source_table = catalog.get("source_table")
    if (
        catalog.get("schema") != "menu-portrait-export-v1"
        or catalog.get("portrait_count") != 311
        or catalog.get("unique_resource_count") != 74
        or catalog.get("unique_graphics_count") != 70
        or len(catalog.get("portraits", [])) != 311
        or len(catalog.get("unique_resources", [])) != 74
        or not isinstance(source_table, dict)
        or source_table.get("entry_count") != 63
        or source_table.get("entry_size") != 40
        or source_table.get("variants_per_entry") != 5
    ):
        raise ValueError("portrait catalog denominator mismatch")
    table_offset = source_table["file_offset"]
    table_size = source_table["entry_count"] * source_table["entry_size"]
    if _sha256(base[table_offset : table_offset + table_size]) != source_table.get(
        "sha256"
    ):
        raise ValueError("portrait table bytes mismatch")
    unique_by_id = {
        resource["resource_id"]: resource
        for resource in catalog["unique_resources"]
    }
    if set(unique_by_id) != set(range(74)):
        raise ValueError("portrait resource IDs are not canonical")
    aliases_by_resource = {resource_id: [] for resource_id in unique_by_id}
    grouped: dict[tuple[str, int], dict[str, Any]] = {}
    for alias in catalog["portraits"]:
        resource_id = alias["resource_id"]
        resource = unique_by_id[resource_id]
        pair_offset = alias["pair_file_offset"]
        aliases_by_resource[resource_id].append(alias)
        for resource_type, delta, pointer_field, offset_field, hash_field in (
            (
                "graphics",
                0,
                "gfx_pointer",
                "gfx_file_offset",
                "decompressed_sha256",
            ),
            (
                "palette",
                4,
                "palette_pointer",
                "palette_file_offset",
                "palette_sha256",
            ),
        ):
            if alias[pointer_field] != resource[pointer_field]:
                raise ValueError("portrait alias pointer mismatch")
            pointer = _pointer(resource[pointer_field])
            source_offset = resource[offset_field]
            pointer_offset = pair_offset + delta
            if (
                pointer != 0x08000000 + source_offset
                or int.from_bytes(
                    base[pointer_offset : pointer_offset + 4],
                    "little",
                )
                != pointer
            ):
                raise ValueError("portrait pointer provenance mismatch")
            if resource_type == "graphics":
                content = _decompress_lz77(base, source_offset)
                if (
                    len(content) != 6400
                    or _sha256(content) != resource[hash_field]
                ):
                    raise ValueError("portrait graphics provenance mismatch")
            else:
                content = base[source_offset : source_offset + 128]
                if (
                    len(content) != 128
                    or _sha256(content) != resource[hash_field]
                ):
                    raise ValueError("portrait palette provenance mismatch")
            row = grouped.setdefault(
                (resource_type, pointer),
                {
                    "resource_type": resource_type,
                    "source_pointer": pointer,
                    "source_offset": source_offset,
                    "source_sha256": _sha256(content),
                    "source_size": len(content),
                    "content": content,
                    "logical_aliases": [],
                },
            )
            if row["content"] != content:
                raise ValueError("portrait physical payload identity mismatch")
            row["logical_aliases"].append(
                {
                    "resource_id": resource_id,
                    "portrait_id": alias.get("portrait_id"),
                    "variant": alias.get("variant"),
                    "kind": alias.get("kind"),
                    "pair_file_offset": pair_offset,
                    "pair_pointer_offset": pointer_offset,
                }
            )

    expected_by_pointer = {
        row["source_pointer"]: {
            alias["pair_pointer_offset"] for alias in row["logical_aliases"]
        }
        for row in grouped.values()
    }
    actual_by_pointer = {pointer: set() for pointer in expected_by_pointer}
    for offset in range(0, len(base) - 3, 4):
        value = int.from_bytes(base[offset : offset + 4], "little")
        if value in actual_by_pointer:
            actual_by_pointer[value].add(offset)
    for pointer, expected in expected_by_pointer.items():
        if actual_by_pointer[pointer] != expected:
            raise ValueError(
                f"portrait exact reference mismatch for 0x{pointer:08X}"
            )
    resources = sorted(
        grouped.values(),
        key=lambda row: (row["source_pointer"], row["resource_type"]),
    )
    if (
        len(resources) != 140
        or sum(row["resource_type"] == "graphics" for row in resources) != 70
        or sum(row["resource_type"] == "palette" for row in resources) != 70
        or sum(len(row["logical_aliases"]) for row in resources) != 622
    ):
        raise ValueError("portrait physical denominator mismatch")
    return resources, aliases_by_resource


def _rebuild(
    root: Path,
    artifact: Path,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    base = (root / "rom/base.gba").read_bytes()
    if _sha256(base) != ROM_SHA256:
        raise ValueError("portrait base ROM mismatch")
    layout_path = root / "sequel/rom-layout.json"
    layout = RomLayout.from_path(layout_path, base)
    regions = ImageResourceRegions.from_path(root / REGISTRY_PATH, layout)
    region = regions.require("menu-portraits", "menu_portrait_resources")
    if (
        layout.target_rom_size != 0x1000000
        or region.start != 0xA80000
        or region.end != 0xB00000
    ):
        raise ValueError("portrait expansion region mismatch")
    catalog = _json(root / CATALOG_PATH)
    resources, aliases_by_resource = _catalog_resources(root, base, catalog)
    unique_by_id = {
        resource["resource_id"]: resource
        for resource in catalog["unique_resources"]
    }
    spec = _json(artifact / SPEC_NAME)
    if (
        spec.get("schema") != "menu-portrait-relocation-v1"
        or spec.get("base_rom_sha256") != ROM_SHA256
        or spec.get("source_catalog") != CATALOG_PATH.as_posix()
        or spec.get("source_catalog_sha256") != CATALOG_SHA256
        or spec.get("region_registry") != REGISTRY_PATH.as_posix()
        or spec.get("region_registry_sha256")
        != _sha256_file(root / REGISTRY_PATH)
        or spec.get("partition") != "sequel-image-assets"
        or spec.get("owner") != "sequel_image_assets"
        or spec.get("region") != "menu-portraits"
        or spec.get("region_owner") != "menu_portrait_resources"
        or len(spec.get("edits", [])) != 74
    ):
        raise ValueError("portrait preservation spec contract mismatch")
    for expected_id, edit in enumerate(spec["edits"]):
        resource = unique_by_id[expected_id]
        aliases = aliases_by_resource[expected_id]
        expected_png = (
            CATALOG_PATH.parent / aliases[0]["png"]
        ).as_posix()
        if (
            edit.get("id") != f"portrait-{expected_id:03d}"
            or edit.get("resource_id") != expected_id
            or edit.get("png") != expected_png
            or edit.get("expected")
            != {
                "gfx_pointer": resource["gfx_pointer"],
                "palette_pointer": resource["palette_pointer"],
                "compressed_sha256": resource["compressed_sha256"],
                "palette_sha256": resource["palette_sha256"],
                "pair_pointer_offsets": sorted(
                    alias["pair_file_offset"] for alias in aliases
                ),
            }
            or _sha256_file(root / expected_png)
            != aliases[0]["png_sha256"]
        ):
            raise ValueError("portrait preservation edit mismatch")

    data = bytearray(layout.expanded_base())
    cursor = region.start
    resource_rows = []
    for index, resource in enumerate(resources):
        cursor = (cursor + 3) & ~3
        content = resource["content"]
        payload_bytes = (
            _encode_lz77(content)
            if resource["resource_type"] == "graphics"
            else content
        )
        if (
            resource["resource_type"] == "graphics"
            and _decompress_lz77(payload_bytes, 0) != content
        ):
            raise ValueError("portrait independent LZ77 round-trip mismatch")
        end = cursor + len(payload_bytes)
        if end > region.end:
            raise ValueError("portrait preservation exceeds region")
        if data[cursor:end] != bytes([layout.fill_byte]) * len(payload_bytes):
            raise ValueError("portrait allocation precondition mismatch")
        data[cursor:end] = payload_bytes
        new_pointer = 0x08000000 + cursor
        aliases = sorted(
            resource["logical_aliases"],
            key=lambda alias: alias["pair_pointer_offset"],
        )
        pointer_offsets = [
            alias["pair_pointer_offset"] for alias in aliases
        ]
        for pointer_offset in pointer_offsets:
            if int.from_bytes(
                data[pointer_offset : pointer_offset + 4],
                "little",
            ) != resource["source_pointer"]:
                raise ValueError("portrait redirect precondition mismatch")
            data[pointer_offset : pointer_offset + 4] = new_pointer.to_bytes(
                4,
                "little",
            )
        resource_type = resource["resource_type"]
        resource_rows.append(
            {
                "id": f"menu-portrait-{resource_type}-{index:03d}",
                "resource_type": resource_type,
                "resource_ids": sorted(
                    {alias["resource_id"] for alias in aliases}
                ),
                "source_pointer": resource["source_pointer"],
                "source_sha256": resource["source_sha256"],
                "source_size": resource["source_size"],
                "replacement_sha256": _sha256(payload_bytes),
                "replacement_size": len(payload_bytes),
                "new_pointer": new_pointer,
                "offset": cursor,
                "all_pointer_offsets": pointer_offsets,
                "target_pointer_offsets": pointer_offsets,
                "logical_aliases": aliases,
            }
        )
        cursor = end
    summary = {
        "logical_portrait_count": 311,
        "logical_pair_count": 74,
        "physical_payload_count": 140,
        "graphics_payload_count": 70,
        "palette_payload_count": 70,
        "logical_pointer_count": 622,
        "unexpected_pointer_count": 0,
        "allocation_count": 140,
        "pointer_patch_count": 622,
        "allocation_start": region.start,
        "allocation_end": cursor,
        "region_end": region.end,
        "stored_payload_bytes": sum(
            row["replacement_size"] for row in resource_rows
        ),
        "allocation_span": cursor - region.start,
        "remaining_bytes": region.end - cursor,
        "applied_patch_count": 762,
    }
    return summary, resource_rows, _sha256(bytes(data))


def _verify(root: Path, artifact: Path) -> dict[str, Any]:
    payload_path = artifact / PAYLOAD_NAME
    promotion_path = artifact / "manifest.json"
    spec_path = artifact / SPEC_NAME
    payload = _json(payload_path)
    promotion = _json(promotion_path)
    expected_files = {
        PAYLOAD_NAME: _sha256_file(payload_path),
        SPEC_NAME: _sha256_file(spec_path),
    }
    actual_files = {
        path.relative_to(artifact).as_posix(): _sha256_file(path)
        for path in artifact.rglob("*")
        if path.is_file() and path != promotion_path
    }
    command = [
        "python3",
        "tools/verify_menu_portrait_relocation_audit.py",
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
        or promotion.get("payload_sha256") != expected_files[PAYLOAD_NAME]
        or promotion.get("files") != expected_files
        or actual_files != expected_files
        or promotion.get("verifier")
        != {"command": command, "exit_code": 0}
    ):
        raise ValueError("portrait promotion manifest contract mismatch")
    if (
        payload.get("schema") != PAYLOAD_SCHEMA
        or payload.get("scope") != EXPECTED_SCOPE
        or promotion.get("scope") != EXPECTED_SCOPE
        or promotion.get("summary") != payload.get("summary")
    ):
        raise ValueError("portrait payload scope/summary contract mismatch")
    if (
        payload.get("base_rom")
        != {
            "path": "rom/base.gba",
            "size": len((root / "rom/base.gba").read_bytes()),
            "sha256": ROM_SHA256,
        }
        or payload.get("catalog", {}).get("path")
        != CATALOG_PATH.as_posix()
        or payload.get("catalog", {}).get("sha256") != CATALOG_SHA256
        or payload.get("authoring_spec", {}).get("file") != SPEC_NAME
        or payload.get("authoring_spec", {}).get("sha256")
        != expected_files[SPEC_NAME]
    ):
        raise ValueError("portrait payload provenance mismatch")
    layout_path = root / payload["layout"]["path"]
    registry_path = root / payload["region_registry"]["path"]
    if (
        payload["layout"]["path"] != "sequel/rom-layout.json"
        or payload["layout"]["sha256"] != _sha256_file(layout_path)
        or payload["layout"]["target_rom_size"] != 0x1000000
        or payload["layout"]["partition"] != "sequel-image-assets"
        or payload["layout"]["owner"] != "sequel_image_assets"
        or payload["region_registry"]
        != {
            "path": REGISTRY_PATH.as_posix(),
            "sha256": _sha256_file(registry_path),
            "region": "menu-portraits",
            "owner": "menu_portrait_resources",
            "start": 0xA80000,
            "end": 0xB00000,
        }
    ):
        raise ValueError("portrait layout/region provenance mismatch")
    expected_implementation = {
        path: _sha256_file(root / path) for path in IMPLEMENTATION_PATHS
    }
    if payload.get("implementation") != expected_implementation:
        raise ValueError("portrait implementation hashes mismatch")

    summary, resources, output_sha256 = _rebuild(root, artifact, payload)
    if (
        payload.get("summary") != summary
        or payload.get("resources") != resources
        or payload.get("output_rom_sha256") != output_sha256
    ):
        raise ValueError("portrait independent rebuild mismatch")
    return {
        "schema": "menu-portrait-relocation-verification-v1",
        "artifact_id": ARTIFACT_ID,
        "verified_payloads": len(resources),
        "verified_pointers": summary["logical_pointer_count"],
        "rebuilt_output_rom_sha256": output_sha256,
        "errors": [],
    }


def verify_audit(root: Path, artifact: Path) -> dict[str, Any]:
    try:
        return _verify(Path(root).resolve(), Path(artifact).resolve())
    except Exception as error:
        return {
            "schema": "menu-portrait-relocation-verification-v1",
            "artifact_id": ARTIFACT_ID,
            "verified_payloads": 0,
            "verified_pointers": 0,
            "rebuilt_output_rom_sha256": None,
            "errors": [str(error)],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts") / ARTIFACT_ID,
    )
    args = parser.parse_args()
    artifact = args.artifact
    if not artifact.is_absolute():
        artifact = args.root / artifact
    verification = verify_audit(args.root, artifact)
    print(json.dumps(verification, ensure_ascii=False, indent=2))
    return 0 if not verification["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
