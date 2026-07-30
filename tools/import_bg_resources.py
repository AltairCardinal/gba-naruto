#!/usr/bin/env python3
"""Build guarded in-place patches for fullscreen BG resources."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import encode_gba_lz77, read_lz77_record


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/bg-resource-canvases-v1/manifest.json")
CATALOG_SHA256 = "27096c9129823cc7d4f98aeb1fde304419a1c6abfadaf1cff6e13b80bf2fa99e"
SPEC_SCHEMA = "bg-resource-import-v1"
TABLE_OFFSET = 0x59903C
TABLE_ENTRY_COUNT = 14
TABLE_ENTRY_SIZE = 16
TABLE_SHA256 = "57e9b8b6b7c3003615c39539f80934f142efeb1e6674114fbaca98bc629f7da2"
VALID_ENTRY_IDS = tuple(range(1, 8)) + tuple(range(9, 14))
ROLE_POINTER_OFFSETS = {"graphics": 0, "palette": 4, "tilemap": 8}
PALETTE_SIZE = 384
TILEMAP_SIZE = 32 * 10 * 2


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
) -> tuple[
    dict[tuple[str, str], dict[str, Any]],
    dict[int, dict[str, Any]],
]:
    if catalog.get("schema") != "bg-resource-canvases-v1":
        raise ValueError("BG resource catalog schema mismatch")
    table = catalog.get("table")
    if (
        not isinstance(table, dict)
        or table.get("file_offset") != TABLE_OFFSET
        or table.get("entry_count") != TABLE_ENTRY_COUNT
        or table.get("entry_size") != TABLE_ENTRY_SIZE
        or table.get("empty_entry_ids") != [0, 8]
        or table.get("sha256") != TABLE_SHA256
    ):
        raise ValueError("BG resource table provenance mismatch")
    table_bytes = rom[
        TABLE_OFFSET : TABLE_OFFSET + TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
    ]
    if _sha256(table_bytes) != TABLE_SHA256:
        raise ValueError("BG resource table bytes mismatch")
    for empty_id in (0, 8):
        start = empty_id * TABLE_ENTRY_SIZE
        if table_bytes[start : start + TABLE_ENTRY_SIZE] != bytes(TABLE_ENTRY_SIZE):
            raise ValueError(f"BG resource entry {empty_id} is not a sentinel")

    entries = catalog.get("entries")
    if not isinstance(entries, list) or len(entries) != len(VALID_ENTRY_IDS):
        raise ValueError("BG resource catalog must contain 12 entries")
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    entry_slots: dict[int, dict[str, Any]] = {}
    physical_spans: dict[int, tuple[int, str]] = {}
    logical_count = 0
    for expected_entry_id, entry in zip(VALID_ENTRY_IDS, entries, strict=True):
        if not isinstance(entry, dict):
            raise ValueError("BG resource entry must be an object")
        entry_id = entry.get("entry_id")
        entry_offset = entry.get("descriptor_file_offset")
        mode_flag = entry.get("mode_flag")
        if (
            entry_id != expected_entry_id
            or entry_offset != TABLE_OFFSET + entry_id * TABLE_ENTRY_SIZE
            or mode_flag not in (0, 1)
            or entry.get("pixel_mode") != ("8bpp" if mode_flag else "4bpp")
        ):
            raise ValueError("BG resource entry identity mismatch")
        descriptor = table_bytes[
            entry_id * TABLE_ENTRY_SIZE : (entry_id + 1) * TABLE_ENTRY_SIZE
        ]
        if int.from_bytes(descriptor[12:16], "little") != mode_flag:
            raise ValueError(f"BG resource entry {entry_id} mode mismatch")
        slot_row: dict[str, Any] = {
            "entry_id": entry_id,
            "mode_flag": mode_flag,
            "descriptor_file_offset": entry_offset,
        }
        for role, pointer_delta in ROLE_POINTER_OFFSETS.items():
            logical_count += 1
            resource = entry.get(role)
            if not isinstance(resource, dict):
                raise ValueError(
                    f"BG resource entry {entry_id} {role} is missing"
                )
            digest = resource.get("decompressed_sha256")
            offset = resource.get("file_offset")
            size = resource.get("decompressed_size")
            source_file = resource.get("file")
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or not isinstance(offset, int)
                or not isinstance(size, int)
                or size <= 0
                or not isinstance(source_file, str)
            ):
                raise ValueError(
                    f"BG resource entry {entry_id} {role} record is invalid"
                )
            pointer = int.from_bytes(
                descriptor[pointer_delta : pointer_delta + 4],
                "little",
            )
            if pointer != ROM_BASE + offset:
                raise ValueError(
                    f"BG resource entry {entry_id} {role} pointer mismatch"
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
                    f"BG resource entry {entry_id} {role} "
                    "does not match base ROM"
                )
            existing_span = physical_spans.get(offset)
            span = (offset + len(record), role)
            if existing_span is not None and existing_span != span:
                raise ValueError("conflicting BG physical slot provenance")
            physical_spans[offset] = span
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
                raise ValueError(f"conflicting BG resource identity: {key}")
            row["source_files"].add(source_file)
            row["physical_offsets"].add(offset)
            row["logical_aliases"].append(
                {
                    "entry_id": entry_id,
                    "mode_flag": mode_flag,
                    "resource_type": role,
                    "table_pointer_offset": entry_offset + pointer_delta,
                    "physical_offset": offset,
                    "source_file": source_file,
                }
            )
            slot_row[role] = {
                "offset": offset,
                "content": content,
                "digest": digest,
            }
        entry_slots[entry_id] = slot_row

    ordered_spans = sorted(
        (start, end, role) for start, (end, role) in physical_spans.items()
    )
    for (_, previous_end, _), (start, _, _) in zip(
        ordered_spans,
        ordered_spans[1:],
    ):
        if start < previous_end:
            raise ValueError("BG physical slots overlap")
    physical_count = sum(
        len(row["physical_offsets"]) for row in grouped.values()
    )
    if len(grouped) != 31 or physical_count != 36 or logical_count != 36:
        raise ValueError(
            "BG resource denominator mismatch: "
            f"{len(grouped)}/31 content, {physical_count}/36 physical, "
            f"{logical_count}/36 logical"
        )
    for row in grouped.values():
        row["source_files"] = sorted(row["source_files"])
        row["physical_offsets"] = sorted(row["physical_offsets"])
        row["logical_aliases"] = sorted(
            row["logical_aliases"],
            key=lambda item: (
                item["entry_id"],
                item["table_pointer_offset"],
            ),
        )
    return grouped, entry_slots


def _validate_resource_payload(
    role: str,
    content: bytes,
    aliases: list[dict[str, Any]],
) -> None:
    if role == "graphics":
        modes = {item["mode_flag"] for item in aliases}
        for mode_flag in modes:
            tile_size = 64 if mode_flag else 32
            if not content or len(content) % tile_size:
                raise ValueError(
                    f"graphics must contain complete {tile_size}-byte "
                    f"{'8bpp' if mode_flag else '4bpp'} tiles"
                )
    elif role == "palette":
        if len(content) != PALETTE_SIZE:
            raise ValueError("palette must contain exactly 384 bytes")
    elif role == "tilemap":
        if len(content) != TILEMAP_SIZE:
            raise ValueError("tilemap must contain exactly 640 bytes")
    else:
        raise ValueError(f"unsupported BG resource type: {role}")


def _validate_entry_view(
    entry_id: int,
    mode_flag: int,
    graphics: bytes,
    palette: bytes,
    tilemap: bytes,
) -> None:
    if len(palette) != PALETTE_SIZE:
        raise ValueError(
            f"BG entry {entry_id} palette must contain exactly 384 bytes"
        )
    if len(tilemap) != TILEMAP_SIZE:
        raise ValueError(
            f"BG entry {entry_id} tilemap must contain exactly 640 bytes"
        )
    tile_size = 64 if mode_flag else 32
    if not graphics or len(graphics) % tile_size:
        raise ValueError(
            f"BG entry {entry_id} graphics must contain complete "
            f"{tile_size}-byte {'8bpp' if mode_flag else '4bpp'} tiles"
        )
    tile_count = len(graphics) // tile_size
    if mode_flag and graphics and max(graphics) >= PALETTE_SIZE // 2:
        raise ValueError(
            f"BG entry {entry_id} 8bpp color index exceeds "
            f"{PALETTE_SIZE // 2} palette colors"
        )
    entries = struct.unpack(f"<{TILEMAP_SIZE // 2}H", tilemap)
    for index, value in enumerate(entries):
        tile_index = value & 0x03FF
        if tile_index >= tile_count:
            raise ValueError(
                f"BG entry {entry_id} tile index {tile_index} at {index} "
                f"exceeds {tile_count} tiles"
            )
        if not mode_flag:
            palette_bank = (value >> 12) & 0x0F
            maximum_palette_index = palette_bank * 16 + 15
            if maximum_palette_index >= PALETTE_SIZE // 2:
                raise ValueError(
                    f"BG entry {entry_id} palette index "
                    f"{maximum_palette_index} at {index} exceeds "
                    f"{PALETTE_SIZE // 2} colors"
                )


def resolve_bg_resource_patches(
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
        raise ValueError("BG source catalog path mismatch")

    catalog_path = root / CATALOG_PATH
    catalog_bytes = catalog_path.read_bytes()
    if _sha256(catalog_bytes) != CATALOG_SHA256:
        raise ValueError("BG resource catalog hash mismatch")
    catalog = json.loads(catalog_bytes)
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("BG resource base ROM hash mismatch")
    resources, entry_slots = _catalog_resources(catalog, base)

    edits = spec.get("edits")
    if not isinstance(edits, list):
        raise ValueError("BG resource edits must be a list")
    seen_slots: set[tuple[str, str, int]] = set()
    prepared: list[dict[str, Any]] = []
    replacements: dict[int, bytes] = {}
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("BG resource edit must be an object")
        role = edit.get("resource_type")
        digest = edit.get("resource_sha256")
        resource = resources.get((role, digest))
        if resource is None:
            raise ValueError(f"unknown BG resource: {role}/{digest}")
        expected = edit.get("expected")
        if not isinstance(expected, dict):
            raise ValueError("BG resource edit is missing expected provenance")
        if expected.get("decompressed_size") != resource["decompressed_size"]:
            raise ValueError("BG resource decompressed size provenance mismatch")
        if expected.get("physical_offsets") != resource["physical_offsets"]:
            raise ValueError("BG resource physical offset provenance mismatch")
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
                "BG target physical offsets must be a canonical non-empty "
                "subset of catalog provenance"
            )
        slot_keys = {(role, digest, offset) for offset in target_offsets}
        if seen_slots.intersection(slot_keys):
            raise ValueError(f"duplicate BG resource edit: {role}/{digest}")
        seen_slots.update(slot_keys)
        source_value = edit.get("source_file")
        if not isinstance(source_value, str):
            raise ValueError("BG resource source_file must be a path")
        content = _resolve_path(root, source_value).read_bytes()
        _validate_resource_payload(role, content, resource["logical_aliases"])
        if len(content) != resource["decompressed_size"]:
            raise ValueError(
                f"{role} replacement size {len(content)} does not match "
                f"{resource['decompressed_size']}"
            )
        if _sha256(content) == digest:
            continue
        for offset in target_offsets:
            replacements[offset] = content
        prepared.append(
            {
                "edit": edit,
                "resource": resource,
                "target_offsets": target_offsets,
                "content": content,
                "encoded": encode_gba_lz77(content),
                "source_value": source_value,
            }
        )

    for entry_id, row in entry_slots.items():
        view = {
            role: replacements.get(row[role]["offset"], row[role]["content"])
            for role in ROLE_POINTER_OFFSETS
        }
        _validate_entry_view(
            entry_id,
            row["mode_flag"],
            view["graphics"],
            view["palette"],
            view["tilemap"],
        )

    planned: list[dict[str, Any]] = []
    for item in prepared:
        resource = item["resource"]
        role = resource["resource_type"]
        digest = resource["resource_sha256"]
        encoded = item["encoded"]
        physical_plans: list[dict[str, Any]] = []
        overflow: list[tuple[int, int]] = []
        for offset in item["target_offsets"]:
            original_record = read_lz77_record(base, offset)
            slot_content = lz77_decompress(base, offset)
            if (
                len(slot_content) != resource["decompressed_size"]
                or _sha256(slot_content) != digest
            ):
                raise ValueError(
                    f"BG physical slot 0x{offset:06X} "
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
            alias
            for alias in resource["logical_aliases"]
            if alias["physical_offset"] in item["target_offsets"]
        ]
        affected_entries = sorted(
            {alias["entry_id"] for alias in logical_aliases}
        )
        for physical in physical_plans:
            planned.append(
                {
                    "id": (
                        f"{item['edit'].get('id', 'bg-resource')}-"
                        f"{physical['offset']:06x}"
                    ),
                    "type": "bytes",
                    "asset_type": "bg_resource",
                    "resource_type": role,
                    "resource_sha256": digest,
                    "replacement_sha256": _sha256(item["content"]),
                    "offset": physical["offset"],
                    "before_hex": physical["before"].hex(),
                    "after_hex": physical["after"].hex(),
                    "encoded_size": len(encoded),
                    "slot_size": physical["slot_size"],
                    "padding_bytes": physical["slot_size"] - len(encoded),
                    "affected_entries": affected_entries,
                    "logical_aliases": logical_aliases,
                    "content_physical_offsets": resource["physical_offsets"],
                    "target_physical_offsets": item["target_offsets"],
                    "source_file": item["source_value"],
                }
            )
    return sorted(planned, key=lambda row: row["offset"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build guarded in-place patches for fullscreen BG resources."
    )
    parser.add_argument("spec", type=Path)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    patches = resolve_bg_resource_patches(args.root, args.spec)
    payload = {"schema": "bg-resource-patches-v1", "patches": patches}
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
