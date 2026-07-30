#!/usr/bin/env python3
"""Relocate regular BG resources into an expanded ROM image region."""

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

from tools.gba_image_export import encode_gba_lz77
from tools.image_resource_regions import ImageResourceRegions
from tools.import_bg_resources import (
    CATALOG_PATH,
    CATALOG_SHA256,
    ROLE_POINTER_OFFSETS,
    ROM_BASE,
    ROM_SHA256,
    _catalog_resources,
    _validate_entry_view,
    _validate_resource_payload,
)
from tools.rom_layout import RomLayout


SPEC_SCHEMA = "bg-resource-relocation-v1"
REGION_REGISTRY_PATH = Path("sequel/image-resource-regions.json")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def _load_catalog(
    root: Path,
    base: bytes,
) -> tuple[
    dict[tuple[str, str], dict[str, Any]],
    dict[int, dict[str, Any]],
]:
    if _sha256(base) != ROM_SHA256:
        raise ValueError("BG relocation base ROM SHA-256 mismatch")
    catalog_path = root / CATALOG_PATH
    catalog_bytes = catalog_path.read_bytes()
    if _sha256(catalog_bytes) != CATALOG_SHA256:
        raise ValueError("BG relocation catalog SHA-256 mismatch")
    catalog = json.loads(catalog_bytes)
    return _catalog_resources(catalog, base)


def catalog_bg_relocation_payloads(
    root: Path,
    rom: bytes | None = None,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Rebuild 31 content groups, 36 physical payloads and 36 exact refs."""
    root = Path(root).resolve()
    base = (
        (root / "rom/base.gba").read_bytes()
        if rom is None
        else bytes(rom)
    )
    grouped, _ = _load_catalog(root, base)
    resources: dict[tuple[str, str], dict[str, Any]] = {}
    expected_by_pointer: dict[int, set[int]] = {}
    for key, source in grouped.items():
        aliases = []
        for alias in source["logical_aliases"]:
            pointer_offset = alias["table_pointer_offset"]
            physical_offset = alias["physical_offset"]
            source_pointer = ROM_BASE + physical_offset
            if (
                int.from_bytes(
                    base[pointer_offset : pointer_offset + 4],
                    "little",
                )
                != source_pointer
            ):
                raise ValueError("BG relocation pointer provenance mismatch")
            aliases.append(
                {
                    **alias,
                    "source_pointer": source_pointer,
                }
            )
            expected_by_pointer.setdefault(source_pointer, set()).add(
                pointer_offset
            )
        resources[key] = {
            "resource_type": source["resource_type"],
            "resource_sha256": source["resource_sha256"],
            "decompressed_size": source["decompressed_size"],
            "source_files": list(source["source_files"]),
            "physical_offsets": list(source["physical_offsets"]),
            "pointer_aliases": sorted(
                aliases,
                key=lambda alias: alias["table_pointer_offset"],
            ),
            "logical_aliases": list(source["logical_aliases"]),
        }

    actual_by_pointer = {pointer: set() for pointer in expected_by_pointer}
    for offset in range(0, len(base) - 3, 4):
        value = int.from_bytes(base[offset : offset + 4], "little")
        if value in actual_by_pointer:
            actual_by_pointer[value].add(offset)
    for resource in resources.values():
        unexpected = set()
        for alias in resource["pointer_aliases"]:
            pointer = alias["source_pointer"]
            expected = expected_by_pointer[pointer]
            actual = actual_by_pointer[pointer]
            if expected - actual:
                raise ValueError("BG relocation exact pointer reference missing")
            unexpected.update(actual - expected)
        resource["unexpected_pointer_offsets"] = sorted(unexpected)

    if (
        len(resources) != 31
        or sum(
            len(resource["physical_offsets"])
            for resource in resources.values()
        )
        != 36
        or sum(
            len(resource["pointer_aliases"])
            for resource in resources.values()
        )
        != 36
    ):
        raise ValueError("BG relocation denominator mismatch")
    return resources


def resolve_bg_resource_relocation_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes | None = None,
    layout: RomLayout | None = None,
    regions: ImageResourceRegions | None = None,
) -> list[dict[str, Any]]:
    """Build one atomic BG allocation and descriptor-pointer plan."""
    root = Path(root).resolve()
    spec_path = _resolve_path(root, str(spec_path), "BG relocation spec")
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
        raise ValueError("BG relocation base ROM mismatch")
    if (
        spec.get("source_catalog") != CATALOG_PATH.as_posix()
        or spec.get("source_catalog_sha256") != CATALOG_SHA256
    ):
        raise ValueError("BG relocation catalog contract mismatch")

    if layout is None:
        layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    try:
        partition = next(
            row for row in layout.partitions if row.id == spec.get("partition")
        )
    except StopIteration as error:
        raise ValueError("BG relocation parent partition is missing") from error
    if (
        partition.id != "sequel-image-assets"
        or partition.owner != "sequel_image_assets"
        or spec.get("owner") != partition.owner
    ):
        raise ValueError("BG relocation parent contract mismatch")
    registry_path = root / REGION_REGISTRY_PATH
    if (
        spec.get("region_registry") != REGION_REGISTRY_PATH.as_posix()
        or spec.get("region_registry_sha256")
        != _sha256(registry_path.read_bytes())
    ):
        raise ValueError("BG relocation region registry contract mismatch")
    if regions is None:
        regions = ImageResourceRegions.from_path(registry_path, layout)
    region = regions.require(
        str(spec.get("region", "")),
        str(spec.get("region_owner", "")),
    )
    if (
        regions.parent != partition
        or region.id != "regular-bg"
        or region.owner != "regular_bg_resources"
    ):
        raise ValueError("BG relocation region contract mismatch")

    resources = catalog_bg_relocation_payloads(root, base)
    if any(
        resource["unexpected_pointer_offsets"]
        for resource in resources.values()
    ):
        raise ValueError("BG relocation has unknown exact references")
    _, entry_slots = _load_catalog(root, base)

    edits = spec.get("edits")
    if not isinstance(edits, list):
        raise ValueError("BG relocation edits must be an array")
    seen_ids: set[str] = set()
    claimed_pointer_offsets: set[int] = set()
    prepared: list[dict[str, Any]] = []
    replacement_by_pointer_offset: dict[int, bytes] = {}
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("BG relocation edit must be an object")
        edit_id = edit.get("id")
        if not isinstance(edit_id, str) or not edit_id or edit_id in seen_ids:
            raise ValueError("BG relocation edit ID is invalid")
        seen_ids.add(edit_id)
        key = (edit.get("resource_type"), edit.get("resource_sha256"))
        resource = resources.get(key)
        if resource is None:
            raise ValueError("BG relocation resource identity is invalid")
        expected = edit.get("expected")
        if not isinstance(expected, dict):
            raise ValueError("BG relocation expected data is missing")
        all_pointer_offsets = sorted(
            alias["table_pointer_offset"]
            for alias in resource["pointer_aliases"]
        )
        if (
            expected.get("decompressed_size")
            != resource["decompressed_size"]
            or expected.get("physical_offsets")
            != resource["physical_offsets"]
            or _canonical_offsets(
                expected.get("pointer_offsets"),
                "expected BG pointer offsets",
            )
            != all_pointer_offsets
        ):
            raise ValueError("BG relocation provenance contract mismatch")
        target_pointer_offsets = (
            all_pointer_offsets
            if "target_pointer_offsets" not in edit
            else _canonical_offsets(
                edit["target_pointer_offsets"],
                "target BG pointer offsets",
            )
        )
        if not set(target_pointer_offsets).issubset(all_pointer_offsets):
            raise ValueError(
                "BG relocation target pointer offsets are not canonical"
            )
        if claimed_pointer_offsets.intersection(target_pointer_offsets):
            raise ValueError("BG relocation pointer aliases are claimed twice")
        claimed_pointer_offsets.update(target_pointer_offsets)
        content = _resolve_path(
            root,
            edit.get("source_file"),
            "BG relocation source file",
        ).read_bytes()
        _validate_resource_payload(
            resource["resource_type"],
            content,
            resource["logical_aliases"],
        )
        if len(content) != resource["decompressed_size"]:
            raise ValueError("BG relocation replacement size mismatch")
        selected_aliases = [
            alias
            for alias in resource["pointer_aliases"]
            if alias["table_pointer_offset"] in target_pointer_offsets
        ]
        if len(selected_aliases) != len(target_pointer_offsets):
            raise ValueError("BG relocation selected alias mismatch")
        for pointer_offset in target_pointer_offsets:
            replacement_by_pointer_offset[pointer_offset] = content
        prepared.append(
            {
                "edit_id": edit_id,
                "resource": resource,
                "content": content,
                "encoded": encode_gba_lz77(content),
                "replacement_sha256": _sha256(content),
                "target_pointer_offsets": target_pointer_offsets,
                "selected_aliases": selected_aliases,
                "source_file": edit["source_file"],
            }
        )

    for entry_id, row in entry_slots.items():
        view = {}
        for role, delta in ROLE_POINTER_OFFSETS.items():
            pointer_offset = row["descriptor_file_offset"] + delta
            view[role] = replacement_by_pointer_offset.get(
                pointer_offset,
                row[role]["content"],
            )
        _validate_entry_view(
            entry_id,
            row["mode_flag"],
            view["graphics"],
            view["palette"],
            view["tilemap"],
        )

    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in prepared:
        resource = item["resource"]
        key = (
            resource["resource_type"],
            resource["resource_sha256"],
            item["replacement_sha256"],
        )
        group = grouped.setdefault(
            key,
            {
                **item,
                "edit_ids": set(),
                "target_pointer_offsets": [],
                "selected_aliases": [],
            },
        )
        if group["encoded"] != item["encoded"]:
            raise AssertionError("BG relocation replacement hash collision")
        group["edit_ids"].add(item["edit_id"])
        group["target_pointer_offsets"].extend(
            item["target_pointer_offsets"]
        )
        group["selected_aliases"].extend(item["selected_aliases"])

    type_order = {"graphics": 0, "palette": 1, "tilemap": 2}
    cursor = region.start
    allocations: list[dict[str, Any]] = []
    redirects: list[dict[str, Any]] = []
    for index, group in enumerate(
        sorted(
            grouped.values(),
            key=lambda item: (
                min(item["resource"]["physical_offsets"]),
                type_order[item["resource"]["resource_type"]],
                item["replacement_sha256"],
            ),
        )
    ):
        cursor = (cursor + 3) & ~3
        encoded = group["encoded"]
        end = cursor + len(encoded)
        if end > region.end:
            raise ValueError("BG relocation exceeds its registered region")
        target_pointer_offsets = sorted(group["target_pointer_offsets"])
        if len(target_pointer_offsets) != len(set(target_pointer_offsets)):
            raise ValueError("BG relocation grouped aliases overlap")
        resource = group["resource"]
        resource_type = resource["resource_type"]
        new_pointer = ROM_BASE + cursor
        allocation_id = f"regular-bg-{resource_type}-{index:03d}"
        allocations.append(
            {
                "id": allocation_id,
                "type": "bytes",
                "asset_type": "bg_resource_relocation",
                "resource_type": resource_type,
                "resource_sha256": resource["resource_sha256"],
                "replacement_sha256": group["replacement_sha256"],
                "decompressed_size": len(group["content"]),
                "encoded_size": len(encoded),
                "new_pointer": new_pointer,
                "offset": cursor,
                "before_hex": bytes([layout.fill_byte] * len(encoded)).hex(),
                "after_hex": encoded.hex(),
                "allocation": {
                    "partition": partition.id,
                    "owner": partition.owner,
                    "region": region.id,
                    "region_owner": region.owner,
                },
                "physical_offsets": resource["physical_offsets"],
                "all_pointer_offsets": sorted(
                    alias["table_pointer_offset"]
                    for alias in resource["pointer_aliases"]
                ),
                "target_pointer_offsets": target_pointer_offsets,
                "logical_aliases": sorted(
                    group["selected_aliases"],
                    key=lambda alias: alias["table_pointer_offset"],
                ),
                "source_file": group["source_file"],
            }
        )
        for alias in sorted(
            group["selected_aliases"],
            key=lambda item: item["table_pointer_offset"],
        ):
            pointer_offset = alias["table_pointer_offset"]
            source_pointer = alias["source_pointer"]
            redirects.append(
                {
                    "id": f"{allocation_id}.pointer-{pointer_offset:06x}",
                    "type": "bytes",
                    "asset_type": "bg_resource_pointer",
                    "resource_type": resource_type,
                    "resource_sha256": resource["resource_sha256"],
                    "source_pointer": source_pointer,
                    "new_pointer": new_pointer,
                    "offset": pointer_offset,
                    "before_hex": source_pointer.to_bytes(4, "little").hex(),
                    "after_hex": new_pointer.to_bytes(4, "little").hex(),
                    "target_pointer_offsets": target_pointer_offsets,
                }
            )
        cursor = end
    return allocations + sorted(redirects, key=lambda patch: patch["offset"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    patches = resolve_bg_resource_relocation_patches(args.root, args.spec)
    payload = {
        "schema": "bg-resource-relocation-patches-v1",
        "patches": patches,
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
