#!/usr/bin/env python3
"""Relocate menu/story portrait payloads into an expanded image region."""

from __future__ import annotations

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
from tools.image_resource_regions import ImageResourceRegions
from tools.import_menu_portraits import (
    CATALOG_PATH,
    CATALOG_SHA256,
    PORTRAIT_BYTES,
    PORTRAIT_COLORS,
    ROM_SHA256,
    _load_png,
    _preserve_palette_reserved_bits,
)
from tools.rom_layout import RomLayout


RESOURCE_FIELDS = {
    "graphics": {
        "pointer": "gfx_pointer",
        "offset": "gfx_file_offset",
        "size": "decompressed_size",
        "sha256": "decompressed_sha256",
        "stored_size": "compressed_size",
        "stored_sha256": "compressed_sha256",
        "pointer_delta": 0,
    },
    "palette": {
        "pointer": "palette_pointer",
        "offset": "palette_file_offset",
        "size": "palette_size",
        "sha256": "palette_sha256",
        "pointer_delta": 4,
    },
}
SPEC_SCHEMA = "menu-portrait-relocation-v1"
REGION_REGISTRY_PATH = Path("sequel/image-resource-regions.json")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pointer(value: object, label: str) -> int:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a hexadecimal pointer")
    try:
        pointer = int(value, 0)
    except ValueError as error:
        raise ValueError(f"{label} is not a hexadecimal pointer") from error
    if pointer < 0x08000000:
        raise ValueError(f"{label} is outside GBA ROM")
    return pointer


def _catalog(root: Path, rom: bytes) -> dict[str, Any]:
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("menu portrait relocation base ROM SHA-256 mismatch")
    catalog_path = root / CATALOG_PATH
    catalog_bytes = catalog_path.read_bytes()
    if _sha256(catalog_bytes) != CATALOG_SHA256:
        raise ValueError("menu portrait relocation catalog SHA-256 mismatch")
    catalog = json.loads(catalog_bytes)
    source_table = catalog.get("source_table")
    if (
        catalog.get("schema") != "menu-portrait-export-v1"
        or catalog.get("portrait_count") != 311
        or catalog.get("unique_resource_count") != 74
        or catalog.get("unique_graphics_count") != 70
        or not isinstance(source_table, dict)
        or source_table.get("entry_count") != 63
        or source_table.get("entry_size") != 40
        or source_table.get("variants_per_entry") != 5
    ):
        raise ValueError("menu portrait relocation catalog denominator mismatch")
    table_offset = source_table.get("file_offset")
    if not isinstance(table_offset, int):
        raise ValueError("menu portrait source table offset is invalid")
    table_size = source_table["entry_count"] * source_table["entry_size"]
    if _sha256(rom[table_offset : table_offset + table_size]) != source_table.get(
        "sha256"
    ):
        raise ValueError("menu portrait source table bytes mismatch")
    if len(catalog.get("portraits", [])) != 311:
        raise ValueError("menu portrait logical alias denominator mismatch")
    if len(catalog.get("unique_resources", [])) != 74:
        raise ValueError("menu portrait resource-pair denominator mismatch")
    return catalog


def catalog_menu_portrait_payloads(
    root: Path,
    rom: bytes | None = None,
) -> dict[tuple[str, int], dict[str, Any]]:
    """Rebuild the 140 physical payloads and all 622 exact pointer aliases."""
    root = Path(root).resolve()
    base = (
        (root / "rom/base.gba").read_bytes()
        if rom is None
        else bytes(rom)
    )
    catalog = _catalog(root, base)
    unique_by_id = {
        row["resource_id"]: row for row in catalog["unique_resources"]
    }
    if set(unique_by_id) != set(range(74)):
        raise ValueError("menu portrait resource IDs are not canonical")

    resources: dict[tuple[str, int], dict[str, Any]] = {}
    expected_offsets_by_pointer: dict[int, set[int]] = {}
    for portrait in catalog["portraits"]:
        resource_id = portrait.get("resource_id")
        resource = unique_by_id.get(resource_id)
        pair_offset = portrait.get("pair_file_offset")
        if (
            resource is None
            or not isinstance(pair_offset, int)
            or pair_offset % 4
        ):
            raise ValueError("menu portrait logical alias is invalid")
        for field in (
            "gfx_pointer",
            "palette_pointer",
            "gfx_file_offset",
            "palette_file_offset",
            "decompressed_size",
            "decompressed_sha256",
            "palette_size",
            "palette_sha256",
        ):
            if portrait.get(field) != resource.get(field):
                raise ValueError(
                    f"menu portrait resource {resource_id} alias {field} mismatch"
                )

        for resource_type, fields in RESOURCE_FIELDS.items():
            pointer = _pointer(
                resource[fields["pointer"]],
                f"resource {resource_id} {resource_type}",
            )
            source_offset = resource[fields["offset"]]
            content_size = resource[fields["size"]]
            content_sha256 = resource[fields["sha256"]]
            pointer_offset = pair_offset + fields["pointer_delta"]
            if (
                not isinstance(source_offset, int)
                or pointer != 0x08000000 + source_offset
                or not isinstance(content_size, int)
                or content_size <= 0
                or int.from_bytes(
                    base[pointer_offset : pointer_offset + 4],
                    "little",
                )
                != pointer
            ):
                raise ValueError(
                    f"menu portrait resource {resource_id} "
                    f"{resource_type} provenance mismatch"
                )

            if resource_type == "graphics":
                stored = read_lz77_record(base, source_offset)
                content = lz77_decompress(base, source_offset)
                if (
                    len(stored) != resource[fields["stored_size"]]
                    or _sha256(stored) != resource[fields["stored_sha256"]]
                    or len(content) != PORTRAIT_BYTES
                ):
                    raise ValueError(
                        f"menu portrait resource {resource_id} graphics mismatch"
                    )
            else:
                content = base[source_offset : source_offset + content_size]
                if len(content) != PORTRAIT_COLORS * 2:
                    raise ValueError(
                        f"menu portrait resource {resource_id} palette mismatch"
                    )
            if len(content) != content_size or _sha256(content) != content_sha256:
                raise ValueError(
                    f"menu portrait resource {resource_id} "
                    f"{resource_type} content mismatch"
                )

            key = (resource_type, pointer)
            row = resources.setdefault(
                key,
                {
                    "resource_type": resource_type,
                    "source_pointer": pointer,
                    "source_offset": source_offset,
                    "source_sha256": content_sha256,
                    "source_size": content_size,
                    "logical_aliases": [],
                },
            )
            if (
                row["source_offset"] != source_offset
                or row["source_sha256"] != content_sha256
                or row["source_size"] != content_size
            ):
                raise ValueError(
                    f"menu portrait physical {resource_type} identity mismatch"
                )
            row["logical_aliases"].append(
                {
                    "resource_id": resource_id,
                    "portrait_id": portrait.get("portrait_id"),
                    "variant": portrait.get("variant"),
                    "kind": portrait.get("kind"),
                    "pair_file_offset": pair_offset,
                    "pair_pointer_offset": pointer_offset,
                }
            )
            expected_offsets_by_pointer.setdefault(pointer, set()).add(
                pointer_offset
            )

    actual_offsets_by_pointer = {
        pointer: set() for pointer in expected_offsets_by_pointer
    }
    for offset in range(0, len(base) - 3, 4):
        value = int.from_bytes(base[offset : offset + 4], "little")
        if value in actual_offsets_by_pointer:
            actual_offsets_by_pointer[value].add(offset)

    for row in resources.values():
        pointer = row["source_pointer"]
        expected = expected_offsets_by_pointer[pointer]
        actual = actual_offsets_by_pointer[pointer]
        missing = sorted(expected - actual)
        if missing:
            raise ValueError(
                f"menu portrait pointer 0x{pointer:08X} is missing aliases"
            )
        row["logical_aliases"] = sorted(
            row["logical_aliases"],
            key=lambda alias: alias["pair_pointer_offset"],
        )
        row["unexpected_pointer_offsets"] = sorted(actual - expected)

    if (
        len(resources) != 140
        or sum(
            row["resource_type"] == "graphics" for row in resources.values()
        )
        != 70
        or sum(
            row["resource_type"] == "palette" for row in resources.values()
        )
        != 70
        or sum(len(row["logical_aliases"]) for row in resources.values())
        != 622
    ):
        raise ValueError("menu portrait relocation denominator mismatch")
    return resources


def _resolve_path(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty path")
    path = Path(value)
    return path if path.is_absolute() else root / path


def _canonical_offsets(value: object, label: str) -> list[int]:
    if (
        not isinstance(value, list)
        or not value
        or any(isinstance(item, bool) or not isinstance(item, int) for item in value)
    ):
        raise ValueError(f"{label} must be a non-empty integer array")
    offsets = sorted(value)
    if len(offsets) != len(set(offsets)) or any(offset % 4 for offset in offsets):
        raise ValueError(f"{label} must be unique and four-byte aligned")
    return offsets


def resolve_menu_portrait_relocation_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes | None = None,
    layout: RomLayout | None = None,
    regions: ImageResourceRegions | None = None,
) -> list[dict[str, Any]]:
    """Build one atomic allocation-and-pointer plan for edited portraits."""
    root = Path(root).resolve()
    spec_path = _resolve_path(root, str(spec_path), "portrait relocation spec")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or spec.get("schema") != SPEC_SCHEMA:
        raise ValueError(f"expected schema {SPEC_SCHEMA}")
    base = (
        (root / "rom/base.gba").read_bytes()
        if rom is None
        else bytes(rom)
    )
    if (
        spec.get("base_rom_sha256") != ROM_SHA256
        or _sha256(base) != ROM_SHA256
    ):
        raise ValueError("menu portrait relocation base ROM mismatch")
    if (
        spec.get("source_catalog") != CATALOG_PATH.as_posix()
        or spec.get("source_catalog_sha256") != CATALOG_SHA256
    ):
        raise ValueError("menu portrait relocation catalog contract mismatch")

    if layout is None:
        layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    partition_id = spec.get("partition")
    owner = spec.get("owner")
    try:
        partition = next(
            row for row in layout.partitions if row.id == partition_id
        )
    except StopIteration as error:
        raise ValueError(
            "menu portrait relocation parent partition is missing"
        ) from error
    if (
        partition.id != "sequel-image-assets"
        or partition.owner != "sequel_image_assets"
        or owner != partition.owner
    ):
        raise ValueError("menu portrait relocation parent contract mismatch")

    if (
        spec.get("region_registry") != REGION_REGISTRY_PATH.as_posix()
        or spec.get("region_registry_sha256")
        != _sha256((root / REGION_REGISTRY_PATH).read_bytes())
    ):
        raise ValueError("menu portrait region registry contract mismatch")
    if regions is None:
        regions = ImageResourceRegions.from_path(
            root / REGION_REGISTRY_PATH,
            layout,
        )
    region = regions.require(
        str(spec.get("region", "")),
        str(spec.get("region_owner", "")),
    )
    if (
        regions.parent != partition
        or region.id != "menu-portraits"
        or region.owner != "menu_portrait_resources"
    ):
        raise ValueError("menu portrait relocation region contract mismatch")

    catalog = _catalog(root, base)
    physical = catalog_menu_portrait_payloads(root, base)
    if any(row["unexpected_pointer_offsets"] for row in physical.values()):
        raise ValueError("menu portrait relocation has unknown exact references")
    resource_pairs = {
        row["resource_id"]: row for row in catalog["unique_resources"]
    }
    aliases_by_resource: dict[int, list[dict[str, Any]]] = {
        resource_id: [] for resource_id in resource_pairs
    }
    for alias in catalog["portraits"]:
        aliases_by_resource[alias["resource_id"]].append(alias)

    edits = spec.get("edits")
    if not isinstance(edits, list):
        raise ValueError("menu portrait relocation edits must be an array")
    seen_ids: set[str] = set()
    seen_resources: set[int] = set()
    claimed_pointer_offsets: set[int] = set()
    prepared: list[dict[str, Any]] = []
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("menu portrait relocation edit must be an object")
        edit_id = edit.get("id")
        resource_id = edit.get("resource_id")
        if not isinstance(edit_id, str) or not edit_id or edit_id in seen_ids:
            raise ValueError("menu portrait relocation edit ID is invalid")
        if resource_id not in resource_pairs or resource_id in seen_resources:
            raise ValueError("menu portrait relocation resource ID is invalid")
        seen_ids.add(edit_id)
        seen_resources.add(resource_id)
        resource = resource_pairs[resource_id]
        expected = edit.get("expected")
        if not isinstance(expected, dict):
            raise ValueError("menu portrait relocation expected data is missing")
        if (
            expected.get("gfx_pointer") != resource["gfx_pointer"]
            or expected.get("palette_pointer") != resource["palette_pointer"]
            or expected.get("compressed_sha256")
            != resource["compressed_sha256"]
            or expected.get("palette_sha256") != resource["palette_sha256"]
        ):
            raise ValueError("menu portrait relocation provenance mismatch")
        aliases = aliases_by_resource[resource_id]
        all_pair_offsets = sorted(
            alias["pair_file_offset"] for alias in aliases
        )
        if _canonical_offsets(
            expected.get("pair_pointer_offsets"),
            "expected pair pointer offsets",
        ) != all_pair_offsets:
            raise ValueError("menu portrait relocation alias contract mismatch")
        target_pair_offsets = (
            all_pair_offsets
            if "target_pair_pointer_offsets" not in edit
            else _canonical_offsets(
                edit["target_pair_pointer_offsets"],
                "target pair pointer offsets",
            )
        )
        if not set(target_pair_offsets).issubset(all_pair_offsets):
            raise ValueError(
                "menu portrait relocation target aliases are not canonical"
            )
        target_pointer_offsets = {
            offset + delta
            for offset in target_pair_offsets
            for delta in (0, 4)
        }
        overlap = claimed_pointer_offsets & target_pointer_offsets
        if overlap:
            raise ValueError(
                "menu portrait relocation aliases are claimed twice"
            )
        claimed_pointer_offsets.update(target_pointer_offsets)

        graphics, palette = _load_png(
            _resolve_path(root, edit.get("png"), "portrait PNG")
        )
        palette_offset = int(resource["palette_file_offset"])
        original_palette = base[
            palette_offset : palette_offset + PORTRAIT_COLORS * 2
        ]
        palette = _preserve_palette_reserved_bits(
            palette,
            original_palette,
        )
        payloads = {
            "graphics": encode_gba_lz77(graphics),
            "palette": palette,
        }
        for resource_type, payload in payloads.items():
            fields = RESOURCE_FIELDS[resource_type]
            source_pointer = _pointer(
                resource[fields["pointer"]],
                f"resource {resource_id} {resource_type}",
            )
            physical_row = physical[(resource_type, source_pointer)]
            pointer_offsets = [
                offset + fields["pointer_delta"]
                for offset in target_pair_offsets
            ]
            selected_aliases = [
                alias
                for alias in physical_row["logical_aliases"]
                if alias["pair_pointer_offset"] in pointer_offsets
            ]
            if len(selected_aliases) != len(pointer_offsets):
                raise ValueError(
                    "menu portrait relocation selected alias mismatch"
                )
            prepared.append(
                {
                    "edit_id": edit_id,
                    "resource_id": resource_id,
                    "resource_type": resource_type,
                    "source_pointer": source_pointer,
                    "source_sha256": physical_row["source_sha256"],
                    "source_size": physical_row["source_size"],
                    "payload": payload,
                    "all_pointer_offsets": [
                        alias["pair_pointer_offset"]
                        for alias in physical_row["logical_aliases"]
                    ],
                    "target_pointer_offsets": pointer_offsets,
                    "logical_aliases": selected_aliases,
                }
            )

    grouped: dict[tuple[str, int, str], dict[str, Any]] = {}
    for row in prepared:
        replacement_sha256 = _sha256(row["payload"])
        key = (
            row["resource_type"],
            row["source_pointer"],
            replacement_sha256,
        )
        group = grouped.setdefault(
            key,
            {
                **row,
                "replacement_sha256": replacement_sha256,
                "resource_ids": set(),
                "edit_ids": set(),
                "target_pointer_offsets": [],
                "logical_aliases": [],
            },
        )
        if group["payload"] != row["payload"]:
            raise AssertionError("portrait replacement hash collision")
        group["resource_ids"].add(row["resource_id"])
        group["edit_ids"].add(row["edit_id"])
        group["target_pointer_offsets"].extend(row["target_pointer_offsets"])
        group["logical_aliases"].extend(row["logical_aliases"])

    cursor = region.start
    allocations: list[dict[str, Any]] = []
    redirects: list[dict[str, Any]] = []
    type_order = {"graphics": 0, "palette": 1}
    for index, group in enumerate(
        sorted(
            grouped.values(),
            key=lambda row: (
                row["source_pointer"],
                type_order[row["resource_type"]],
                row["replacement_sha256"],
            ),
        )
    ):
        cursor = (cursor + 3) & ~3
        payload = group["payload"]
        end = cursor + len(payload)
        if end > region.end:
            raise ValueError(
                "menu portrait relocation exceeds its registered region"
            )
        target_pointer_offsets = sorted(group["target_pointer_offsets"])
        if len(target_pointer_offsets) != len(set(target_pointer_offsets)):
            raise ValueError(
                "menu portrait relocation grouped aliases overlap"
            )
        new_pointer = 0x08000000 + cursor
        resource_type = group["resource_type"]
        allocation_id = f"menu-portrait-{resource_type}-{index:03d}"
        allocation = {
            "id": allocation_id,
            "type": "bytes",
            "asset_type": f"menu_portrait_{resource_type}_relocation",
            "resource_type": resource_type,
            "resource_ids": sorted(group["resource_ids"]),
            "source_pointer": group["source_pointer"],
            "source_sha256": group["source_sha256"],
            "source_size": group["source_size"],
            "replacement_sha256": group["replacement_sha256"],
            "replacement_size": len(payload),
            "new_pointer": new_pointer,
            "offset": cursor,
            "before_hex": bytes([layout.fill_byte]) * len(payload),
            "after_hex": payload.hex(),
            "allocation": {
                "partition": partition.id,
                "owner": partition.owner,
                "region": region.id,
                "region_owner": region.owner,
            },
            "all_pointer_offsets": sorted(
                set(group["all_pointer_offsets"])
            ),
            "target_pointer_offsets": target_pointer_offsets,
            "logical_aliases": sorted(
                group["logical_aliases"],
                key=lambda alias: alias["pair_pointer_offset"],
            ),
        }
        allocation["before_hex"] = allocation["before_hex"].hex()
        allocations.append(allocation)
        for pointer_offset in target_pointer_offsets:
            redirects.append(
                {
                    "id": f"{allocation_id}.pointer-{pointer_offset:06x}",
                    "type": "bytes",
                    "asset_type": "menu_portrait_pointer",
                    "resource_type": resource_type,
                    "resource_ids": sorted(group["resource_ids"]),
                    "source_pointer": group["source_pointer"],
                    "new_pointer": new_pointer,
                    "offset": pointer_offset,
                    "before_hex": group["source_pointer"].to_bytes(
                        4,
                        "little",
                    ).hex(),
                    "after_hex": new_pointer.to_bytes(4, "little").hex(),
                    "target_pointer_offsets": target_pointer_offsets,
                }
            )
        cursor = end
    return allocations + sorted(redirects, key=lambda patch: patch["offset"])
