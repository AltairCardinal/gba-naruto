#!/usr/bin/env python3
"""Verify the frozen short zero gaps from menu portrait LZ77 to palettes.

The verifier intentionally derives the LZ77 stream endpoints from the raw ROM
and uses the accepted pointer/menu inventories only as identity-bound source
contracts.  It does not read the live coverage database; current-unknown and
adjacent-owner checks are performed by the parent promotion workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


VERIFY_SCHEMA = "rom-menu-portrait-lz77-palette-alignment-gaps-verification-v1"
PROMOTION_BATCH = "rom-menu-portrait-lz77-palette-alignment-gaps-v1"
PRIMARY_CLASS = "menu_portrait_lz77_palette_alignment_bytes"
CLAIM_KIND = "menu_portrait_lz77_palette_alignment_gap_bytes"

ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

POINTER_ARTIFACT = Path("artifacts/rom-pointer-lz77-inventory-v1")
POINTER_MANIFEST_PATH = POINTER_ARTIFACT / "manifest.json"
POINTER_PAYLOAD_PATH = POINTER_ARTIFACT / "rom-pointer-lz77-inventory.json"
POINTER_MANIFEST_SHA256 = "d4afca9d19c3b764ce40f460d9c73d7c19f908bf25c197d4b082bd6bc5c4bb33"
POINTER_PAYLOAD_SHA256 = "0c4aed52328b0506e8e41afebe5e5c0ef3dccb830cf8af6c092eb1d0566581c5"

MENU_ARTIFACT = Path("artifacts/rom-menu-portrait-palette-inventory-v1")
MENU_MANIFEST_PATH = MENU_ARTIFACT / "manifest.json"
MENU_PAYLOAD_PATH = MENU_ARTIFACT / "rom-menu-portrait-palette-inventory.json"
MENU_MANIFEST_SHA256 = "8a8675c2724131a6caa9b956825d74280fa26fe99447470b3cc3810688e6f88b"
MENU_PAYLOAD_SHA256 = "ac263fc071b6c6ad4b94b649df38560c180f2b2fd350212cc3875055146d908d"

EXPECTED_POINTER_LZ77_COUNT = 896
EXPECTED_RESOURCE_COUNT = 74
EXPECTED_PALETTE_COUNT = 70
EXPECTED_GAP_COUNT = 52
EXPECTED_GAP_BYTES = 110
ALIGNMENT_UNIT_BYTES = 4

EXPECTED_RANGE_VECTOR_SHA256 = "e88d3a42d6e3144919668ade6db9f9caa21e8aab1502d8b3d9c84a148875bbf7"
EXPECTED_BOUNDARY_VECTOR_SHA256 = "13ab975a67b42528abeef6075ff1f71b9440a7e53806f4f07f345d2e30900ddb"
EXPECTED_PACKED_BYTES_SHA256 = "f23391587f1c9fc48eabd1e95f4caf16f585ef09941b7bc24f023d228e81ccd5"

# The ranges and resource order are frozen by the preflight report.  Keeping
# them here makes a report-vector drift fail closed instead of accepting a
# newly discovered but out-of-contract boundary.
EXPECTED_RANGES = (
    (4233410, 4233412),
    (4236963, 4236964),
    (4240629, 4240632),
    (4244062, 4244064),
    (4251263, 4251264),
    (4257177, 4257180),
    (4260505, 4260508),
    (4263773, 4263776),
    (4267091, 4267092),
    (4270467, 4270468),
    (4273973, 4273976),
    (4285367, 4285368),
    (4288887, 4288888),
    (4291506, 4291508),
    (4295174, 4295176),
    (4298437, 4298440),
    (4301659, 4301660),
    (4305365, 4305368),
    (4308873, 4308876),
    (4312293, 4312296),
    (4315393, 4315396),
    (4321202, 4321204),
    (4330091, 4330092),
    (4333031, 4333032),
    (4336969, 4336972),
    (4344091, 4344092),
    (4350414, 4350416),
    (4353713, 4353716),
    (4357009, 4357012),
    (4360097, 4360100),
    (4365801, 4365804),
    (4368866, 4368868),
    (4371699, 4371700),
    (4378290, 4378292),
    (4382119, 4382120),
    (4384767, 4384768),
    (4390465, 4390468),
    (4398274, 4398276),
    (4412021, 4412024),
    (4415989, 4415992),
    (4419657, 4419660),
    (4423211, 4423212),
    (4426593, 4426596),
    (4429877, 4429880),
    (4433122, 4433124),
    (4436215, 4436216),
    (4439982, 4439984),
    (4443362, 4443364),
    (4449485, 4449488),
    (4452170, 4452172),
    (4455414, 4455416),
    (4461347, 4461348),
)
EXPECTED_RESOURCE_IDS = (
    0,
    1,
    2,
    3,
    73,
    6,
    7,
    8,
    9,
    10,
    11,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    25,
    28,
    29,
    30,
    32,
    34,
    35,
    36,
    37,
    39,
    40,
    41,
    43,
    44,
    45,
    47,
    49,
    53,
    54,
    55,
    56,
    57,
    58,
    59,
    60,
    61,
    62,
    64,
    65,
    66,
    72,
)
EXPECTED_GFX_STREAM_STARTS = (
    4230104,
    4233540,
    4237092,
    4240760,
    4247976,
    4254296,
    4257308,
    4260636,
    4263904,
    4267220,
    4270596,
    4281876,
    4285496,
    4289016,
    4291636,
    4295304,
    4298568,
    4301788,
    4305496,
    4309004,
    4312424,
    4318412,
    4327044,
    4330220,
    4333160,
    4340264,
    4347128,
    4350544,
    4353844,
    4357140,
    4362852,
    4365932,
    4368996,
    4375140,
    4378420,
    4382248,
    4387592,
    4394372,
    4408984,
    4412152,
    4416120,
    4419788,
    4423340,
    4426724,
    4430008,
    4433252,
    4436344,
    4440112,
    4446648,
    4449616,
    4452300,
    4458424,
)

MENU_RESOURCE_VECTOR_SHA256 = "aacf1dd777711ffddd46d268b419da0887002557004064c38d51e5b299521c3b"
MENU_PALETTE_RANGE_VECTOR_SHA256 = "84e8b9f99a51f94e1b9e0b972d6458c883428443aa173a9f739beaf601b4e338"
ZERO_HASHES = {
    1: "6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d",
    2: "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
    3: "709e80c88487a2411e1ee4dfb9f22a861492d20c4765150c0c794abd70f8147c",
}

NON_CLAIMS = {
    "padding_intent_claimed": False,
    "reserved_space_claimed": False,
    "free_space_claimed": False,
    "allocatable_space_claimed": False,
    "runtime_consumption_claimed": False,
    "natural_runtime_reachability_claimed": False,
    "generic_lz77_alignment_rule_claimed": False,
    "all_menu_gaps_exhaustive_claimed": False,
    "graphics_or_palette_semantics_expanded": False,
    "editing_safety_claimed": False,
    "writeback_or_relocation_safety_claimed": False,
}
LIMITATIONS = [
    "Only the frozen 52 short ranges between independently parsed pointer-reachable LZ77 endpoints and fixed menu portrait palette starts are classified.",
    "The bytes are not claimed to be padding, reserved space, free space, allocatable space, or runtime-consumed data.",
    "The helper does not claim natural runtime reachability, a generic LZ77 alignment rule, graphics or palette semantics beyond the bound source classes, editing safety, writeback safety, relocation safety, or an exhaustive menu-gap inventory.",
    "The parent workflow performs current-unknown and adjacent-owner checks after this helper is accepted.",
]

EXPECTED_POINTER_SUMMARY = {
    "aligned_pointer_reachable_record_count": 896,
    "newly_exported_record_count": 31,
    "previously_bound_record_count": 865,
    "remaining_unbound_record_count": 0,
    "strict_lz77_record_count": 1099,
}
EXPECTED_MENU_SUMMARY = {
    "alias_group_count": 1,
    "aliased_logical_output_count": 56,
    "aliased_resource_count": 5,
    "bundle_sha256": "d5d80e37d88000ec81501d9549b4c6038c42e6ec172614127821213d9dbcdccc",
    "logical_alias_count": 311,
    "logical_output_count": 311,
    "packed_bytes": 8960,
    "palette_bytes": 8960,
    "range_overlap_bytes": 0,
    "range_vector_sha256": MENU_PALETTE_RANGE_VECTOR_SHA256,
    "source_resource_count": 74,
    "unique_palette_content_hash_count": 54,
    "unique_palette_count": 70,
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _vector_sha(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return _sha(raw)


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _safe_root(raw_root: Path) -> Path:
    candidate = Path(raw_root)
    if candidate.is_symlink():
        raise ValueError("repository root must not be a symlink")
    root = candidate.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("repository root is not a directory")
    return root


def _safe_file(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative path: {relative}")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"bound input must not use a symlink: {relative}")
    path = cursor.resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"bound input escapes repository root: {relative}") from error
    if not path.is_file():
        raise ValueError(f"bound input is not a file: {relative}")
    return path


def _parse_json(raw: bytes, label: str) -> dict[str, Any]:
    if not isinstance(raw, bytes):
        raise ValueError(f"{label} is not bytes")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not a JSON object")
    return value


def _check_identity(raw: bytes, expected: str, label: str) -> None:
    if not isinstance(raw, bytes):
        raise ValueError(f"{label} is not bytes")
    if _sha(raw) != expected:
        raise ValueError(f"{label} identity changed")


def _parse_type10(rom: bytes, start: int) -> int | None:
    """Return the exact compressed-stream end, or None for invalid type-0x10."""

    if not isinstance(rom, bytes) or start < 0 or start + 4 > len(rom):
        return None
    if rom[start] != 0x10:
        return None
    declared = int.from_bytes(rom[start + 1 : start + 4], "little")
    if declared <= 0:
        return None
    cursor = start + 4
    produced = 0
    while produced < declared:
        if cursor >= len(rom):
            return None
        flags = rom[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if produced >= declared:
                break
            if flags & (1 << bit):
                if cursor + 2 > len(rom):
                    return None
                first, second = rom[cursor], rom[cursor + 1]
                cursor += 2
                length = (first >> 4) + 3
                distance = (((first & 0x0F) << 8) | second) + 1
                if distance > produced or produced + length > declared:
                    return None
                produced += length
            else:
                if cursor >= len(rom):
                    return None
                cursor += 1
                produced += 1
    return cursor


def _pointer_lz77_denominator(rom: bytes) -> set[int]:
    candidates: set[int] = set()
    mapped_end = ROM_BASE + len(rom)
    for offset in range(0, len(rom) - 3, ALIGNMENT_UNIT_BYTES):
        pointer = struct.unpack_from("<I", rom, offset)[0]
        if ROM_BASE <= pointer < mapped_end:
            target = pointer - ROM_BASE
            if target % ALIGNMENT_UNIT_BYTES == 0:
                candidates.add(target)
    result = {
        target
        for target in candidates
        if _parse_type10(rom, target) is not None
    }
    if len(result) != EXPECTED_POINTER_LZ77_COUNT:
        raise ValueError("aligned pointer-reachable LZ77 denominator changed")
    return result


def _validate_pointer_sources(manifest: dict[str, Any], payload: dict[str, Any]) -> None:
    if manifest.get("schema") != "git-artifact-promotion-v1":
        raise ValueError("pointer inventory manifest schema changed")
    if manifest.get("artifact_schema") != "rom-pointer-lz77-inventory-v1":
        raise ValueError("pointer inventory artifact schema changed")
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("pointer inventory artifact status changed")
    files = manifest.get("files")
    if not isinstance(files, dict) or files.get(POINTER_PAYLOAD_PATH.name) != POINTER_PAYLOAD_SHA256:
        raise ValueError("pointer inventory manifest payload binding changed")
    if payload.get("schema") != "rom-pointer-lz77-inventory-v1":
        raise ValueError("pointer inventory payload schema changed")
    if payload.get("rom") != {
        "path": "rom/base.gba",
        "sha256": ROM_SHA256,
        "size": ROM_SIZE,
    }:
        raise ValueError("pointer inventory ROM binding changed")
    if payload.get("summary") != EXPECTED_POINTER_SUMMARY:
        raise ValueError("pointer inventory denominator summary changed")
    selection = payload.get("selection_rule")
    if not isinstance(selection, dict):
        raise ValueError("pointer inventory selection rule is missing")
    if selection.get("pointer_reference_alignment") != ALIGNMENT_UNIT_BYTES:
        raise ValueError("pointer inventory alignment changed")
    if selection.get("source_alignment") != ALIGNMENT_UNIT_BYTES:
        raise ValueError("pointer inventory source alignment changed")
    if selection.get("syntax") != (
        "valid GBA type-0x10 stream with exact declared-size termination, "
        "in-range back-references, and no output overrun"
    ):
        raise ValueError("pointer inventory parser contract changed")


def _validate_menu_sources(
    rom: bytes, manifest: dict[str, Any], payload: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if manifest.get("schema") != "git-artifact-promotion-v1":
        raise ValueError("menu inventory manifest schema changed")
    if manifest.get("artifact_schema") != "rom-menu-portrait-palette-inventory-v1":
        raise ValueError("menu inventory artifact schema changed")
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("menu inventory artifact status changed")
    files = manifest.get("files")
    if not isinstance(files, dict) or files.get(MENU_PAYLOAD_PATH.name) != MENU_PAYLOAD_SHA256:
        raise ValueError("menu inventory manifest payload binding changed")
    if payload.get("schema") != "rom-menu-portrait-palette-inventory-v1":
        raise ValueError("menu inventory payload schema changed")
    if payload.get("rom") != {
        "path": "rom/base.gba",
        "sha256": ROM_SHA256,
        "size": ROM_SIZE,
    }:
        raise ValueError("menu inventory ROM binding changed")
    if payload.get("summary") != EXPECTED_MENU_SUMMARY:
        raise ValueError("menu inventory denominator summary changed")

    resources = payload.get("resource_provenance")
    palettes = payload.get("physical_palettes")
    if not isinstance(resources, list) or len(resources) != EXPECTED_RESOURCE_COUNT:
        raise ValueError("menu resource denominator changed")
    if [item.get("resource_id") for item in resources] != list(range(EXPECTED_RESOURCE_COUNT)):
        raise ValueError("menu resource ID denominator changed")
    if not isinstance(palettes, list) or len(palettes) != EXPECTED_PALETTE_COUNT:
        raise ValueError("physical palette denominator changed")

    source = payload.get("source")
    if not isinstance(source, dict):
        raise ValueError("menu source binding is missing")
    if source.get("resource_vector_sha256") != MENU_RESOURCE_VECTOR_SHA256:
        raise ValueError("menu resource vector binding changed")
    palette_ranges: list[list[int]] = []
    palette_by_start: dict[int, dict[str, Any]] = {}
    palette_resource_ids: dict[int, list[int]] = {}
    for index, palette in enumerate(palettes):
        if not isinstance(palette, dict) or palette.get("physical_id") != index:
            raise ValueError("physical palette IDs changed")
        interval = palette.get("range")
        if (
            not isinstance(interval, list)
            or len(interval) != 2
            or not all(isinstance(value, int) for value in interval)
            or interval[1] - interval[0] != 128
            or palette.get("size") != 128
            or palette.get("packed_range") != [index * 128, (index + 1) * 128]
        ):
            raise ValueError("physical palette range denominator changed")
        start, end = interval
        if not (0 <= start < end <= len(rom)) or start in palette_by_start:
            raise ValueError("physical palette ranges are not unique")
        raw = rom[start:end]
        if palette.get("raw_sha256") != _sha(raw):
            raise ValueError("physical palette bytes changed")
        if palette.get("palette_sha256") != _sha(raw):
            raise ValueError("physical palette hash changed")
        palette_ranges.append([start, end])
        palette_by_start[start] = palette
        resource_ids = palette.get("resource_ids")
        if (
            not isinstance(resource_ids, list)
            or palette.get("resource_aliases") != resource_ids
            or any(not isinstance(value, int) for value in resource_ids)
            or len(set(resource_ids)) != len(resource_ids)
            or palette.get("alias_count") != len(resource_ids)
        ):
            raise ValueError("physical palette resource aliases changed")
        palette_resource_ids[start] = list(resource_ids)

    all_palette_resource_ids = [
        resource_id
        for resource_ids in palette_resource_ids.values()
        for resource_id in resource_ids
    ]
    if sorted(all_palette_resource_ids) != list(range(EXPECTED_RESOURCE_COUNT)):
        raise ValueError("physical palette resource ID denominator changed")

    if palette_ranges != source.get("range_vector"):
        raise ValueError("menu palette range vector changed")
    if _vector_sha(palette_ranges) != MENU_PALETTE_RANGE_VECTOR_SHA256:
        raise ValueError("menu palette range vector hash changed")
    if palette_ranges != sorted(palette_ranges):
        raise ValueError("physical palette ranges are not ordered")

    resource_vector: list[list[Any]] = []
    for resource in resources:
        if not isinstance(resource, dict):
            raise ValueError("menu resource row is not an object")
        resource_id = resource.get("resource_id")
        gfx_start = resource.get("gfx_file_offset")
        palette_start = resource.get("palette_file_offset")
        if (
            not isinstance(resource_id, int)
            or not isinstance(gfx_start, int)
            or not isinstance(palette_start, int)
            or resource.get("gfx_pointer") != f"0x{ROM_BASE + gfx_start:08X}"
            or resource.get("palette_pointer") != f"0x{ROM_BASE + palette_start:08X}"
            or resource.get("palette_size") != 128
            or palette_start not in palette_by_start
            or resource.get("palette_sha256") != palette_by_start[palette_start].get("palette_sha256")
        ):
            raise ValueError(f"menu resource {resource_id} binding changed")
        resource_vector.append(
            [resource_id, palette_start, resource.get("palette_sha256")]
        )
    for palette_start, resource_ids in palette_resource_ids.items():
        expected_ids = [
            resource["resource_id"]
            for resource in resources
            if resource["palette_file_offset"] == palette_start
        ]
        if resource_ids != expected_ids:
            raise ValueError("physical palette resource aliases do not match resources")
    if resource_vector != source.get("resource_vector"):
        raise ValueError("menu resource vector changed")
    if _vector_sha(resource_vector) != MENU_RESOURCE_VECTOR_SHA256:
        raise ValueError("menu resource vector hash changed")
    return resources, palettes


def _frozen_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for resource_id, gfx_start, (start, end) in zip(
        EXPECTED_RESOURCE_IDS, EXPECTED_GFX_STREAM_STARTS, EXPECTED_RANGES
    ):
        size = end - start
        rows.append(
            {
                "alignment_unit_bytes": ALIGNMENT_UNIT_BYTES,
                "bytes_sha256": ZERO_HASHES[size],
                "gfx_stream_range": [gfx_start, start],
                "id": f"menu-portrait-lz77-palette-gap-{resource_id:02d}-{start:06x}",
                "left_primary_class": "lz77_resource",
                "palette_range": [end, end + 128],
                "range": [start, end],
                "raw_hex": "00" * size,
                "resource_id": resource_id,
                "right_primary_class": "menu_portrait_palette_bgr555",
                "size": size,
            }
        )
    return rows


def _validate_static_contract() -> None:
    expected_ranges = [list(pair) for pair in EXPECTED_RANGES]
    if _vector_sha(expected_ranges) != EXPECTED_RANGE_VECTOR_SHA256:
        raise ValueError("range vector contract constant changed")
    frozen_rows = _frozen_rows()
    if _vector_sha(frozen_rows) != EXPECTED_BOUNDARY_VECTOR_SHA256:
        raise ValueError("boundary vector contract constant changed")
    if len(frozen_rows) != EXPECTED_GAP_COUNT:
        raise ValueError("gap count contract constant changed")
    if sum(row["size"] for row in frozen_rows) != EXPECTED_GAP_BYTES:
        raise ValueError("gap byte contract constant changed")


def _empty_report(errors: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema": VERIFY_SCHEMA,
        "verified": False,
        "errors": list(errors or []),
        "promotion_batch": PROMOTION_BATCH,
        "primary_class": PRIMARY_CLASS,
        "claim_kind": CLAIM_KIND,
        "gap_count": EXPECTED_GAP_COUNT,
        "gap_bytes": EXPECTED_GAP_BYTES,
        "size_counts": {"1": 16, "2": 14, "3": 22},
        "resource_ids": [],
        "range_vector_sha256": EXPECTED_RANGE_VECTOR_SHA256,
        "boundary_vector_sha256": EXPECTED_BOUNDARY_VECTOR_SHA256,
        "packed_bytes_sha256": None,
        "aligned_pointer_reachable_lz77_count": 0,
        "menu_resource_count": 0,
        "physical_palette_count": 0,
        "rows": [],
        "non_claims": dict(NON_CLAIMS),
        "limitations": list(LIMITATIONS),
        "bound_inputs": {},
    }


def _verify_bound_inputs(
    rom: bytes,
    pointer_manifest_raw: bytes,
    pointer_payload_raw: bytes,
    menu_manifest_raw: bytes,
    menu_payload_raw: bytes,
) -> dict[str, Any]:
    _validate_static_contract()
    _check_identity(rom, ROM_SHA256, "ROM")
    if len(rom) != ROM_SIZE:
        raise ValueError("ROM size changed")
    _check_identity(pointer_manifest_raw, POINTER_MANIFEST_SHA256, "pointer inventory manifest")
    _check_identity(pointer_payload_raw, POINTER_PAYLOAD_SHA256, "pointer inventory payload")
    _check_identity(menu_manifest_raw, MENU_MANIFEST_SHA256, "menu inventory manifest")
    _check_identity(menu_payload_raw, MENU_PAYLOAD_SHA256, "menu inventory payload")

    pointer_manifest = _parse_json(pointer_manifest_raw, "pointer inventory manifest")
    pointer_payload = _parse_json(pointer_payload_raw, "pointer inventory payload")
    menu_manifest = _parse_json(menu_manifest_raw, "menu inventory manifest")
    menu_payload = _parse_json(menu_payload_raw, "menu inventory payload")
    _validate_pointer_sources(pointer_manifest, pointer_payload)
    resources, palettes = _validate_menu_sources(rom, menu_manifest, menu_payload)

    pointer_lz77 = _pointer_lz77_denominator(rom)
    boundaries: dict[tuple[int, int], dict[str, Any]] = {}
    for resource in resources:
        resource_id = resource["resource_id"]
        gfx_start = resource["gfx_file_offset"]
        palette_start = resource["palette_file_offset"]
        if gfx_start not in pointer_lz77:
            raise ValueError(f"resource {resource_id} graphics stream left denominator")
        stream_end = _parse_type10(rom, gfx_start)
        if stream_end is None:
            raise ValueError(f"resource {resource_id} graphics stream stopped parsing")
        if not (
            stream_end < palette_start <= stream_end + 3
            and ((stream_end + 3) & ~3) == palette_start
        ):
            continue
        raw = rom[stream_end:palette_start]
        if len(raw) == 0 or any(raw):
            raise ValueError(f"resource {resource_id} alignment bytes changed")
        key = (stream_end, palette_start)
        if key in boundaries:
            raise ValueError("two menu resources produced the same alignment boundary")
        boundaries[key] = {
            "alignment_unit_bytes": ALIGNMENT_UNIT_BYTES,
            "bytes_sha256": _sha(raw),
            "gfx_stream_range": [gfx_start, stream_end],
            "id": f"menu-portrait-lz77-palette-gap-{resource_id:02d}-{stream_end:06x}",
            "left_primary_class": "lz77_resource",
            "palette_range": [palette_start, palette_start + 128],
            "range": [stream_end, palette_start],
            "raw_hex": raw.hex(),
            "resource_id": resource_id,
            "right_primary_class": "menu_portrait_palette_bgr555",
            "size": len(raw),
        }
    rows = [boundaries[key] for key in sorted(boundaries)]
    ranges = [row["range"] for row in rows]
    packed = b"".join(rom[start:end] for start, end in ranges)
    if len(rows) != EXPECTED_GAP_COUNT or len(packed) != EXPECTED_GAP_BYTES:
        raise ValueError("alignment gap denominator changed")
    if ranges != [list(pair) for pair in EXPECTED_RANGES]:
        raise ValueError("alignment range vector changed")
    if _vector_sha(ranges) != EXPECTED_RANGE_VECTOR_SHA256:
        raise ValueError("alignment range vector hash changed")
    if _sha(packed) != EXPECTED_PACKED_BYTES_SHA256:
        raise ValueError("packed alignment bytes changed")
    if rows != _frozen_rows():
        raise ValueError("alignment boundary rows changed")

    size_counts: dict[str, int] = {}
    for row in rows:
        key = str(row["size"])
        size_counts[key] = size_counts.get(key, 0) + 1
    if size_counts != {"1": 16, "2": 14, "3": 22}:
        raise ValueError("alignment gap size counts changed")
    return {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        "errors": [],
        "promotion_batch": PROMOTION_BATCH,
        "primary_class": PRIMARY_CLASS,
        "claim_kind": CLAIM_KIND,
        "gap_count": len(rows),
        "gap_bytes": len(packed),
        "size_counts": size_counts,
        "resource_ids": [row["resource_id"] for row in rows],
        "range_vector_sha256": _vector_sha(ranges),
        "boundary_vector_sha256": _vector_sha(rows),
        "packed_bytes_sha256": _sha(packed),
        "aligned_pointer_reachable_lz77_count": len(pointer_lz77),
        "menu_resource_count": len(resources),
        "physical_palette_count": len(palettes),
        "rows": rows,
        "non_claims": dict(NON_CLAIMS),
        "limitations": list(LIMITATIONS),
    }


def verify_inputs(
    rom: bytes,
    *,
    pointer_manifest: bytes,
    pointer_payload: bytes,
    menu_manifest: bytes,
    menu_payload: bytes,
) -> dict[str, Any]:
    """Verify already-loaded bound inputs without opening any repository path."""

    report = _empty_report()
    try:
        report = _verify_bound_inputs(
            rom,
            pointer_manifest,
            pointer_payload,
            menu_manifest,
            menu_payload,
        )
    except (OSError, TypeError, ValueError, KeyError, IndexError, UnicodeError, json.JSONDecodeError) as error:
        report["errors"].append(str(error))
    return report


def verify_root_from_bytes(
    rom: bytes,
    *,
    pointer_manifest: bytes,
    pointer_payload: bytes,
    menu_manifest: bytes,
    menu_payload: bytes,
) -> dict[str, Any]:
    """Test seam for mutated ROM bytes; no filesystem writes or reads occur."""

    return verify_inputs(
        rom,
        pointer_manifest=pointer_manifest,
        pointer_payload=pointer_payload,
        menu_manifest=menu_manifest,
        menu_payload=menu_payload,
    )


def verify_root(raw_root: Path) -> dict[str, Any]:
    report = _empty_report()
    try:
        root = _safe_root(raw_root)
        bound_paths = (
            (ROM_PATH, ROM_SHA256),
            (POINTER_MANIFEST_PATH, POINTER_MANIFEST_SHA256),
            (POINTER_PAYLOAD_PATH, POINTER_PAYLOAD_SHA256),
            (MENU_MANIFEST_PATH, MENU_MANIFEST_SHA256),
            (MENU_PAYLOAD_PATH, MENU_PAYLOAD_SHA256),
        )
        loaded: dict[Path, bytes] = {}
        bound_inputs: dict[str, dict[str, Any]] = {}
        for relative, expected in bound_paths:
            path = _safe_file(root, relative)
            raw = path.read_bytes()
            _check_identity(raw, expected, relative.as_posix())
            loaded[relative] = raw
            bound_inputs[relative.as_posix()] = {
                "sha256": _sha(raw),
                "size": len(raw),
            }
        report = verify_inputs(
            loaded[ROM_PATH],
            pointer_manifest=loaded[POINTER_MANIFEST_PATH],
            pointer_payload=loaded[POINTER_PAYLOAD_PATH],
            menu_manifest=loaded[MENU_MANIFEST_PATH],
            menu_payload=loaded[MENU_PAYLOAD_PATH],
        )
        report["bound_inputs"] = bound_inputs
    except (OSError, TypeError, ValueError, KeyError, IndexError, UnicodeError, json.JSONDecodeError) as error:
        report["errors"].append(str(error))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = verify_root(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] and not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
