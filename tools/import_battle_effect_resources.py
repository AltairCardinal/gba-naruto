#!/usr/bin/env python3
"""Build guarded in-place patches for battle-effect graphics and palettes."""

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
CATALOG_PATH = Path(
    "artifacts/battle-effect-resource-pairs-v1/manifest.json"
)
CATALOG_SHA256 = "716ac580326077127797c634d1f19bbc0aadcfd4db9c577730728b112f002963"
SPEC_SCHEMA = "battle-effect-resource-import-v1"
TABLE_OFFSET = 0x59911C
TABLE_ENTRY_COUNT = 19
TABLE_ENTRY_SIZE = 8
ROLE_POINTER_OFFSETS = {"graphics": 0, "palette": 4}


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
    catalog: dict[str, Any],
    rom: bytes,
) -> dict[tuple[str, str], dict[str, Any]]:
    if catalog.get("schema") != "battle-effect-resource-pairs-v1":
        raise ValueError("battle-effect resource catalog schema mismatch")
    entries = catalog.get("entries")
    if not isinstance(entries, list) or len(entries) != 18:
        raise ValueError("battle-effect resource catalog must contain 18 groups")
    table = catalog.get("resource_pair_table")
    if (
        not isinstance(table, dict)
        or table.get("file_offset") != TABLE_OFFSET
        or table.get("entry_count") != TABLE_ENTRY_COUNT
        or table.get("entry_size") != TABLE_ENTRY_SIZE
        or table.get("valid_group_ids") != list(range(1, TABLE_ENTRY_COUNT))
    ):
        raise ValueError("battle-effect resource table provenance mismatch")
    table_bytes = rom[
        TABLE_OFFSET : TABLE_OFFSET + TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
    ]
    if _sha256(table_bytes) != table.get("sha256"):
        raise ValueError("battle-effect resource table bytes mismatch")
    if table_bytes[:TABLE_ENTRY_SIZE] != bytes(TABLE_ENTRY_SIZE):
        raise ValueError("battle-effect resource group zero is not a sentinel")

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    logical_reference_count = 0
    for expected_group_id, entry in enumerate(entries, 1):
        group_id = entry.get("group_id")
        entry_offset = entry.get("table_entry_file_offset")
        if (
            group_id != expected_group_id
            or entry_offset != TABLE_OFFSET + group_id * TABLE_ENTRY_SIZE
        ):
            raise ValueError("battle-effect group identity mismatch")
        pair = table_bytes[
            group_id * TABLE_ENTRY_SIZE :
            (group_id + 1) * TABLE_ENTRY_SIZE
        ]
        if entry.get("pair_raw_hex") != pair.hex():
            raise ValueError(f"battle-effect group {group_id} pair mismatch")

        for role, pointer_delta in ROLE_POINTER_OFFSETS.items():
            resource = entry.get(role)
            if not isinstance(resource, dict):
                raise ValueError(
                    f"battle-effect group {group_id} {role} is missing"
                )
            logical_reference_count += 1
            digest = resource.get("decompressed_sha256")
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
                raise ValueError(
                    f"battle-effect group {group_id} {role} record is invalid"
                )
            pointer = int.from_bytes(
                rom[
                    entry_offset + pointer_delta :
                    entry_offset + pointer_delta + 4
                ],
                "little",
            )
            if pointer != 0x08000000 + offset:
                raise ValueError(
                    f"battle-effect group {group_id} {role} pointer mismatch"
                )
            record = read_lz77_record(rom, offset)
            content = lz77_decompress(rom, offset)
            if (
                len(record) != resource.get("compressed_size")
                or _sha256(record) != resource.get("compressed_sha256")
                or len(content) != size
                or _sha256(content) != digest
            ):
                raise ValueError(
                    f"battle-effect group {group_id} {role} "
                    "does not match base ROM"
                )
            key = (role, digest)
            row = grouped.setdefault(
                key,
                {
                    "resource_type": role,
                    "resource_sha256": digest,
                    "decompressed_size": size,
                    "source_files": set(),
                    "physical_offsets": set(),
                    "logical_aliases": [],
                },
            )
            if row["decompressed_size"] != size:
                raise ValueError(
                    f"conflicting battle-effect resource identity: {key}"
                )
            row["source_files"].add(output_bin)
            row["physical_offsets"].add(offset)
            row["logical_aliases"].append(
                {
                    "group_id": group_id,
                    "resource_type": role,
                    "table_pointer_offset": entry_offset + pointer_delta,
                    "physical_offset": offset,
                    "source_file": output_bin,
                }
            )

    physical_count = sum(
        len(row["physical_offsets"]) for row in grouped.values()
    )
    if (
        len(grouped) != 34
        or physical_count != 35
        or logical_reference_count != 36
    ):
        raise ValueError(
            "battle-effect resource denominator mismatch: "
            f"{len(grouped)}/34 content, {physical_count}/35 physical, "
            f"{logical_reference_count}/36 logical"
        )
    for row in grouped.values():
        row["source_files"] = sorted(row["source_files"])
        row["physical_offsets"] = sorted(row["physical_offsets"])
        row["logical_aliases"] = sorted(
            row["logical_aliases"],
            key=lambda item: (
                item["group_id"],
                item["table_pointer_offset"],
            ),
        )
    return grouped


def _validate_resource_payload(role: str, content: bytes) -> None:
    if role == "graphics":
        if not content or len(content) % 32:
            raise ValueError(
                "graphics must contain complete 32-byte 4bpp tiles"
            )
    elif role == "palette":
        if len(content) != 32:
            raise ValueError("palette must contain exactly 32 bytes")
    else:
        raise ValueError(f"unsupported battle-effect resource type: {role}")


def resolve_battle_effect_resource_patches(
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
        raise ValueError("battle-effect source catalog path mismatch")

    catalog_path = root / CATALOG_PATH
    catalog_bytes = catalog_path.read_bytes()
    if _sha256(catalog_bytes) != CATALOG_SHA256:
        raise ValueError("battle-effect resource catalog hash mismatch")
    catalog = json.loads(catalog_bytes)

    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("battle-effect resource base ROM hash mismatch")
    resources = _catalog_resources(catalog, base)

    edits = spec.get("edits")
    if not isinstance(edits, list):
        raise ValueError("battle-effect resource edits must be a list")
    seen_slots: set[tuple[str, str, int]] = set()
    prepared: list[
        tuple[
            dict[str, Any],
            dict[str, Any],
            list[int],
            bytes,
            bytes,
            str,
        ]
    ] = []
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("battle-effect resource edit must be an object")
        role = edit.get("resource_type")
        digest = edit.get("resource_sha256")
        key = (role, digest)
        resource = resources.get(key)
        if resource is None:
            raise ValueError(f"unknown battle-effect resource: {role}/{digest}")

        expected = edit.get("expected")
        if not isinstance(expected, dict):
            raise ValueError(
                "battle-effect resource edit is missing expected provenance"
            )
        if expected.get("decompressed_size") != resource["decompressed_size"]:
            raise ValueError(
                "battle-effect resource decompressed size provenance mismatch"
            )
        if expected.get("physical_offsets") != resource["physical_offsets"]:
            raise ValueError(
                "battle-effect resource physical offset provenance mismatch"
            )
        target_offsets = edit.get(
            "target_physical_offsets",
            resource["physical_offsets"],
        )
        if (
            not isinstance(target_offsets, list)
            or not target_offsets
            or any(not isinstance(value, int) for value in target_offsets)
            or target_offsets != sorted(set(target_offsets))
            or not set(target_offsets).issubset(resource["physical_offsets"])
        ):
            raise ValueError(
                "battle-effect target physical offsets must be a canonical "
                "non-empty subset of catalog provenance"
            )
        slot_keys = {
            (role, digest, offset)
            for offset in target_offsets
        }
        if seen_slots.intersection(slot_keys):
            raise ValueError(
                f"duplicate battle-effect resource edit: {role}/{digest}"
            )
        seen_slots.update(slot_keys)

        source_value = edit.get("source_file")
        if not isinstance(source_value, str):
            raise ValueError(
                "battle-effect resource source_file must be a path"
            )
        content = _resolve_path(root, source_value).read_bytes()
        _validate_resource_payload(role, content)
        if len(content) != resource["decompressed_size"]:
            raise ValueError(
                f"{role} replacement size {len(content)} does not match "
                f"{resource['decompressed_size']}"
            )
        if _sha256(content) == digest:
            continue
        prepared.append(
            (
                edit,
                resource,
                target_offsets,
                content,
                encode_gba_lz77(content),
                source_value,
            )
        )

    planned: list[dict[str, Any]] = []
    for (
        edit,
        resource,
        target_offsets,
        content,
        encoded,
        source_value,
    ) in prepared:
        role = resource["resource_type"]
        digest = resource["resource_sha256"]
        physical_plans: list[dict[str, Any]] = []
        overflow: list[tuple[int, int]] = []
        for offset in target_offsets:
            original_record = read_lz77_record(base, offset)
            slot_content = lz77_decompress(base, offset)
            if (
                len(slot_content) != resource["decompressed_size"]
                or _sha256(slot_content) != digest
            ):
                raise ValueError(
                    f"battle-effect physical slot 0x{offset:06X} "
                    "does not match catalog provenance"
                )
            if len(encoded) > len(original_record):
                overflow.append((offset, len(original_record)))
                continue
            physical_plans.append(
                {
                    "offset": offset,
                    "before": original_record,
                    "after": encoded + original_record[len(encoded) :],
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

        logical_aliases = [
            item
            for item in resource["logical_aliases"]
            if item["physical_offset"] in target_offsets
        ]
        affected_groups = sorted(
            {item["group_id"] for item in logical_aliases}
        )
        for item in physical_plans:
            planned.append(
                {
                    "id": (
                        f"{edit.get('id', 'battle-effect-resource')}-"
                        f"{item['offset']:06x}"
                    ),
                    "type": "bytes",
                    "asset_type": "battle_effect_resource",
                    "resource_type": role,
                    "resource_sha256": digest,
                    "replacement_sha256": _sha256(content),
                    "offset": item["offset"],
                    "before_hex": item["before"].hex(),
                    "after_hex": item["after"].hex(),
                    "encoded_size": len(encoded),
                    "slot_size": item["slot_size"],
                    "padding_bytes": item["slot_size"] - len(encoded),
                    "affected_groups": affected_groups,
                    "logical_aliases": logical_aliases,
                    "content_physical_offsets": resource["physical_offsets"],
                    "target_physical_offsets": target_offsets,
                    "source_file": source_value,
                }
            )
    return sorted(planned, key=lambda item: item["offset"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build guarded in-place patches for battle-effect resources."
        )
    )
    parser.add_argument("spec", type=Path)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    patches = resolve_battle_effect_resource_patches(args.root, args.spec)
    payload = {
        "schema": "battle-effect-resource-patches-v1",
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
