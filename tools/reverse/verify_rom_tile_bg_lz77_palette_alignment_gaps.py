#!/usr/bin/env python3
"""Verify the frozen tile-BG LZ77-to-palette short zero gaps.

This helper derives both sides of every boundary from the raw ROM.  The
accepted pointer inventory and tile-BG manifest are identity-bound source
contracts only; no runtime database or exporter implementation is imported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


VERIFY_SCHEMA = "rom-tile-bg-lz77-palette-alignment-gaps-verification-v1"
PROMOTION_BATCH = "rom-tile-bg-lz77-palette-alignment-gaps-v1"
PRIMARY_CLASS = "tile_bg_lz77_palette_alignment_bytes"
CLAIM_KIND = "tile_bg_lz77_palette_alignment_gap_bytes"

ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

POINTER_MANIFEST_PATH = Path(
    "artifacts/rom-pointer-lz77-inventory-v1/manifest.json"
)
POINTER_PAYLOAD_PATH = Path(
    "artifacts/rom-pointer-lz77-inventory-v1/rom-pointer-lz77-inventory.json"
)
POINTER_MANIFEST_SHA256 = "d4afca9d19c3b764ce40f460d9c73d7c19f908bf25c197d4b082bd6bc5c4bb33"
POINTER_PAYLOAD_SHA256 = "0c4aed52328b0506e8e41afebe5e5c0ef3dccb830cf8af6c092eb1d0566581c5"

TILE_MANIFEST_PATH = Path("artifacts/tile-assets-bg-v2/manifest.json")
TILE_MANIFEST_SHA256 = "1df63cf6cf49079115e997c6f0f33c57578e517dbe22dc16c15f64c4d218a749"
TILE_EXPORTER_PATH = Path("tools/verify_tile_asset_bg_export.py")
TILE_EXPORTER_SHA256 = "4273c6d0cada4e7d018a805e5c96fca9654c19aabeff9a1a7b26e5aa8380d57c"

TABLE_OFFSET = 0x5A320C
TABLE_ENTRY_COUNT = 79
TABLE_ENTRY_SIZE = 68
TABLE_END = TABLE_OFFSET + TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
TABLE_SHA256 = "0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73"
ALIGNMENT_UNIT_BYTES = 4
TILE_PALETTE_WORDS = {"A": 5, "B": 8, "C": 12, "D": 16}
TILE_LAYER_SPECS = {
    "A": {"gfx": 3, "tilemap": 4, "palette": 5, "bits_per_pixel": 4, "size": 32},
    "B": {"gfx": 6, "tilemap": 7, "palette": 8, "bits_per_pixel": 4, "size": 32},
    "C": {"gfx": 10, "tilemap": 11, "palette": 12, "bits_per_pixel": 8, "size": 128},
    "D": {"gfx": 14, "tilemap": 15, "palette": 16, "bits_per_pixel": 4, "size": 32},
}
EXPECTED_SENTINEL_DESCRIPTOR_IDS = (13, 31, 32, 46)

EXPECTED_POINTER_LZ77_COUNT = 896
EXPECTED_TILE_DESCRIPTOR_COUNT = 79
EXPECTED_TILE_PALETTE_ENTRY_COUNT = 236
EXPECTED_TILE_RAW_PALETTE_RANGE_COUNT = 108
EXPECTED_TILE_MERGED_PALETTE_CLAIM_COUNT = 107
EXPECTED_TILE_MERGED_PALETTE_BYTES = 9984
EXPECTED_GAP_COUNT = 84
EXPECTED_GAP_BYTES = 165
EXPECTED_SIZE_COUNTS = {"1": 31, "2": 25, "3": 28}
EXPECTED_RANGE_VECTOR_SHA256 = "684c4ad2fa1256261de50ed01f8a781bde09b7514f4cab0c5ec5dec9a0b472e2"
EXPECTED_BOUNDARY_VECTOR_SHA256 = "b96f496cb68ed87905d62c39a148f67b2fef4e10bfa9e2b6b004f2d1644fe448"
EXPECTED_PACKED_BYTES_SHA256 = "2aa1fd6b1e4d7e4352751c0a8b7acb6fd9aa3a3a4c994f52b0a214c6f346277d"

EXPECTED_BOUNDARIES = (
    (3452872, 3453477, 3453480, 3453512),
    (3457484, 3458071, 3458072, 3458104),
    (3461164, 3461659, 3461660, 3461692),
    (3464908, 3465386, 3465388, 3465420),
    (3472960, 3473502, 3473504, 3473536),
    (3481268, 3481802, 3481804, 3481836),
    (3485096, 3485605, 3485608, 3485640),
    (3488544, 3489075, 3489076, 3489108),
    (3495304, 3495799, 3495800, 3495832),
    (3502960, 3503486, 3503488, 3503520),
    (3506776, 3507346, 3507348, 3507380),
    (3511964, 3512547, 3512548, 3512580),
    (3516328, 3516889, 3516892, 3516924),
    (3521016, 3521645, 3521648, 3521680),
    (3524704, 3525174, 3525176, 3525208),
    (3529404, 3529967, 3529968, 3530000),
    (3532356, 3532789, 3532792, 3532824),
    (3538932, 3539458, 3539460, 3539492),
    (3541556, 3541979, 3541980, 3542012),
    (3545380, 3545954, 3545956, 3545988),
    (3549324, 3549837, 3549840, 3549872),
    (3552780, 3553249, 3553252, 3553284),
    (3557472, 3558087, 3558088, 3558120),
    (3561152, 3561633, 3561636, 3561668),
    (3569484, 3570015, 3570016, 3570144),
    (3578160, 3578774, 3578776, 3578904),
    (3583916, 3584443, 3584444, 3584476),
    (3598564, 3599241, 3599244, 3599372),
    (3605764, 3606470, 3606472, 3606504),
    (3611784, 3612203, 3612204, 3612332),
    (3631628, 3632194, 3632196, 3632324),
    (3638888, 3639329, 3639332, 3639460),
    (3646116, 3646749, 3646752, 3646880),
    (3649088, 3649429, 3649432, 3649464),
    (3653700, 3653986, 3653988, 3654116),
    (3659280, 3659725, 3659728, 3659760),
    (3662744, 3663119, 3663120, 3663152),
    (3668244, 3668609, 3668612, 3668740),
    (3682096, 3682521, 3682524, 3682652),
    (3693212, 3693538, 3693540, 3693668),
    (3708352, 3708823, 3708824, 3708952),
    (3715264, 3715755, 3715756, 3715884),
    (3724628, 3725098, 3725100, 3725228),
    (3734132, 3734621, 3734624, 3734752),
    (3740064, 3740519, 3740520, 3740648),
    (3768036, 3768635, 3768636, 3768764),
    (3775316, 3775802, 3775804, 3775932),
    (3783820, 3784367, 3784368, 3784496),
    (3788856, 3789227, 3789228, 3789356),
    (3804656, 3805105, 3805108, 3805236),
    (3808624, 3808941, 3808944, 3809072),
    (3813040, 3813375, 3813376, 3813504),
    (3818180, 3818562, 3818564, 3818692),
    (3823532, 3823917, 3823920, 3824048),
    (3828268, 3828634, 3828636, 3828764),
    (3832964, 3833387, 3833388, 3833516),
    (3838028, 3838467, 3838468, 3838596),
    (3845244, 3845715, 3845716, 3845844),
    (3854576, 3855155, 3855156, 3855284),
    (3862376, 3862891, 3862892, 3863020),
    (3872208, 3872841, 3872844, 3872972),
    (3881028, 3881633, 3881636, 3881764),
    (3889460, 3890067, 3890068, 3890196),
    (3898848, 3899447, 3899448, 3899576),
    (3909280, 3909941, 3909944, 3910072),
    (3919272, 3919599, 3919600, 3919728),
    (3924724, 3925101, 3925104, 3925232),
    (3933448, 3934030, 3934032, 3934160),
    (3941132, 3941663, 3941664, 3941792),
    (3954556, 3955235, 3955236, 3955364),
    (3972860, 3973306, 3973308, 3973436),
    (3976012, 3976215, 3976216, 3976344),
    (3982712, 3983337, 3983340, 3983372),
    (3987228, 3987494, 3987496, 3987624),
    (3993280, 3993838, 3993840, 3993872),
    (3998648, 3999010, 3999012, 3999140),
    (4006368, 4006922, 4006924, 4007052),
    (4011784, 4012134, 4012136, 4012264),
    (4022928, 4023245, 4023248, 4023376),
    (4041100, 4041713, 4041716, 4041844),
    (4052244, 4052819, 4052820, 4052948),
    (4058060, 4058413, 4058416, 4058544),
    (4063424, 4063773, 4063776, 4063904),
    (4069216, 4069678, 4069680, 4069808),
)

EXPECTED_LONG_GAPS = ((1302573, 1302640), (3448401, 3448436))
EXPECTED_HETEROGENEOUS_GAPS = (
    (3443681, 3443684),
    (3445786, 3445788),
    (3446445, 3446448),
    (4136542, 4136544),
    (4218861, 4218864),
    (4554406, 4554408),
    (4602066, 4602068),
)

NON_CLAIMS = (
    "padding",
    "reserved_space",
    "free_space",
    "allocatable_space",
    "natural_runtime_reachability",
    "global_unreachability",
    "fixed_consumer_exhaustiveness",
    "final_pixel_equivalence",
    "editing_safety",
    "relocation_safety",
)

LIMITATIONS = [
    "Only the frozen 84 short ranges between independently parsed pointer-reachable LZ77 endpoints and fixed tile-BG palette source ranges are classified.",
    "The bytes are not claimed to be padding, reserved space, free space, or allocatable space.",
    "The helper does not claim natural runtime reachability, global unreachability, fixed-consumer exhaustiveness, final pixel equivalence, editing safety, or relocation safety.",
    "The parent integration performs current-unknown and adjacent-owner checks after this independent helper is accepted.",
    "The two nonzero long gaps and seven heterogeneous direct-CpuSet/reuse gaps remain outside this contract.",
]

EXPECTED_TILE_SUMMARY = {
    "descriptor_count": 79,
    "sentinel_descriptor_ids": [13, 31, 32, 46],
    "complete_layer_counts": {"A": 75, "B": 75, "C": 75, "D": 11},
    "complete_layer_count": 236,
    "partial_layer_count": 1,
    "unique_graphics_count": 107,
    "unique_tilemap_count": 108,
    "unique_palette_count": 107,
    "unique_atlas_count": 108,
    "unique_complete_layer_count": 108,
}
EXPECTED_POINTER_SUMMARY = {
    "aligned_pointer_reachable_record_count": 896,
    "newly_exported_record_count": 31,
    "previously_bound_record_count": 865,
    "remaining_unbound_record_count": 0,
    "strict_lz77_record_count": 1099,
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
    """Return the exact compressed-stream end, or None for an invalid stream."""

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


def _pointer_lz77_denominator(rom: bytes) -> dict[int, int]:
    """Rebuild every aligned ROM pointer whose target is a valid Type-0x10 stream."""

    if not isinstance(rom, bytes):
        raise ValueError("ROM input is not bytes")
    candidates: set[int] = set()
    mapped_end = ROM_BASE + len(rom)
    for offset in range(0, len(rom) - 3, ALIGNMENT_UNIT_BYTES):
        pointer = struct.unpack_from("<I", rom, offset)[0]
        if ROM_BASE <= pointer < mapped_end:
            target = pointer - ROM_BASE
            if target % ALIGNMENT_UNIT_BYTES == 0:
                candidates.add(target)
    parsed = {
        target: end
        for target in candidates
        if (end := _parse_type10(rom, target)) is not None
    }
    if len(parsed) != EXPECTED_POINTER_LZ77_COUNT:
        raise ValueError("aligned pointer-reachable LZ77 denominator changed")
    return parsed


def _validate_pointer_sources(
    manifest: dict[str, Any], payload: dict[str, Any]
) -> None:
    if manifest.get("schema") != "git-artifact-promotion-v1":
        raise ValueError("pointer inventory manifest schema changed")
    if manifest.get("artifact_schema") != "rom-pointer-lz77-inventory-v1":
        raise ValueError("pointer inventory artifact schema changed")
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("pointer inventory artifact status changed")
    files = manifest.get("files")
    if (
        not isinstance(files, dict)
        or files.get(POINTER_PAYLOAD_PATH.name) != POINTER_PAYLOAD_SHA256
    ):
        raise ValueError("pointer inventory manifest payload binding changed")
    if payload.get("schema") != "rom-pointer-lz77-inventory-v1":
        raise ValueError("pointer inventory payload schema changed")
    if payload.get("rom") != {
        "path": ROM_PATH.as_posix(),
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


def _pointer_string(pointer: int) -> str:
    return f"0x{pointer:08X}"


def _tile_manifest_static_checks(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != "tile-assets-bg-export-v2":
        raise ValueError("tile manifest schema changed")
    if manifest.get("rom") != {
        "path": ROM_PATH.as_posix(),
        "size": ROM_SIZE,
        "sha256": ROM_SHA256,
    }:
        raise ValueError("tile manifest ROM binding changed")
    if manifest.get("source_bank") != "sequel/content/tile-assets/bank.json":
        raise ValueError("tile manifest source bank changed")
    if manifest.get("supersedes") != {
        "artifact": "artifacts/tile-assets-bg-v1",
        "reason": "v1 decoded consumer-proven 8bpp C layers as 4bpp",
    }:
        raise ValueError("tile manifest supersedes binding changed")
    expected_scope = {
        "kind": "native static BG layers and complete mixed-depth atlases",
        "final_composite": False,
        "layer_color_depths": {
            "A": "4bpp",
            "B": "4bpp",
            "C": "8bpp",
            "D": "4bpp",
        },
        "runtime_tile_base_and_palette_bank_preserved_as_unknowns": True,
    }
    if manifest.get("scope") != expected_scope:
        raise ValueError("tile manifest scope changed")
    for key, expected in EXPECTED_TILE_SUMMARY.items():
        if manifest.get(key) != expected:
            raise ValueError("tile manifest denominator changed")


def _validate_tile_sources(
    rom: bytes, manifest: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int], int, int]:
    """Validate the accepted manifest and independently rebuild palette ranges."""

    _tile_manifest_static_checks(manifest)
    table = manifest.get("source_table")
    expected_table = {
        "file_offset": TABLE_OFFSET,
        "gba_address": _pointer_string(ROM_BASE + TABLE_OFFSET),
        "entry_count": TABLE_ENTRY_COUNT,
        "entry_size": TABLE_ENTRY_SIZE,
        "sha256": TABLE_SHA256,
        "verification": "code_verified",
    }
    if table != expected_table:
        raise ValueError("tile descriptor table metadata changed")
    if _sha(rom[TABLE_OFFSET:TABLE_END]) != TABLE_SHA256:
        raise ValueError("tile descriptor table changed")

    descriptors = manifest.get("descriptors")
    if not isinstance(descriptors, list) or len(descriptors) != TABLE_ENTRY_COUNT:
        raise ValueError("tile descriptor list changed")

    ranges: dict[tuple[int, int], dict[str, Any]] = {}
    complete_layer_counts = {name: 0 for name in TILE_LAYER_SPECS}
    entry_count = 0
    partial_layer_count = 0
    for descriptor_id, descriptor in enumerate(descriptors):
        if not isinstance(descriptor, dict):
            raise ValueError(f"descriptor {descriptor_id} is not an object")
        row_offset = TABLE_OFFSET + descriptor_id * TABLE_ENTRY_SIZE
        words = struct.unpack_from("<17I", rom, row_offset)
        expected_words = [_pointer_string(word) for word in words]
        if descriptor.get("descriptor_id") != descriptor_id:
            raise ValueError(f"descriptor {descriptor_id} identity changed")
        if descriptor.get("consumer_id") != descriptor_id + 1:
            raise ValueError(f"descriptor {descriptor_id} consumer identity changed")
        if descriptor.get("descriptor_file_offset") != row_offset:
            raise ValueError(f"descriptor {descriptor_id} file offset changed")
        if descriptor.get("descriptor_gba_address") != _pointer_string(ROM_BASE + row_offset):
            raise ValueError(f"descriptor {descriptor_id} GBA address changed")
        if descriptor.get("raw_words") != expected_words:
            raise ValueError(f"descriptor {descriptor_id} raw words differ from ROM")

        words_are_zero = not any(words)
        layers = descriptor.get("layers")
        if not isinstance(layers, list):
            raise ValueError(f"descriptor {descriptor_id} layers changed")
        if words_are_zero:
            if descriptor_id not in EXPECTED_SENTINEL_DESCRIPTOR_IDS:
                raise ValueError("unexpected all-zero tile descriptor")
            if descriptor.get("status") != "sentinel" or layers != []:
                raise ValueError(f"descriptor {descriptor_id} sentinel changed")
            continue

        if descriptor_id in EXPECTED_SENTINEL_DESCRIPTOR_IDS:
            raise ValueError("expected all-zero tile descriptor changed")
        expected_status = "partial" if descriptor_id == 0 else "complete"
        if descriptor.get("status") != expected_status:
            raise ValueError(f"descriptor {descriptor_id} status changed")
        if len(layers) != len(TILE_LAYER_SPECS):
            raise ValueError(f"descriptor {descriptor_id} layer denominator changed")
        by_name: dict[str, dict[str, Any]] = {}
        for layer in layers:
            if not isinstance(layer, dict):
                raise ValueError(f"descriptor {descriptor_id} layer is not an object")
            name = layer.get("name")
            if name not in TILE_LAYER_SPECS or name in by_name:
                raise ValueError(f"descriptor {descriptor_id} layer names changed")
            by_name[name] = layer
        if set(by_name) != set(TILE_LAYER_SPECS):
            raise ValueError(f"descriptor {descriptor_id} layer names changed")

        for name, spec in TILE_LAYER_SPECS.items():
            layer = by_name[name]
            pointers = (words[spec["gfx"]], words[spec["tilemap"]], words[spec["palette"]])
            present_count = sum(bool(pointer) for pointer in pointers)
            if layer.get("bits_per_pixel") != spec["bits_per_pixel"]:
                raise ValueError(f"descriptor {descriptor_id} {name} color depth changed")
            if layer.get("palette_pointer") != (
                _pointer_string(pointers[2]) if pointers[2] else None
            ):
                raise ValueError(f"descriptor {descriptor_id} {name} palette pointer changed")

            if present_count == 0:
                if name != "D" or layer.get("status") != "absent":
                    raise ValueError(f"descriptor {descriptor_id} {name} absence changed")
                if layer.get("palette") is not None:
                    raise ValueError(f"descriptor {descriptor_id} {name} palette absence changed")
                continue
            if present_count == 1 and (
                descriptor_id == 0
                and name == "D"
                and pointers[0] == 0
                and pointers[1] != 0
                and pointers[2] == 0
            ):
                partial_layer_count += 1
                if layer.get("status") != "partial" or layer.get("palette") is not None:
                    raise ValueError(f"descriptor {descriptor_id} partial D changed")
                continue
            if present_count != 3:
                raise ValueError(f"descriptor {descriptor_id} {name} completeness changed")
            if layer.get("status") != "complete":
                raise ValueError(f"descriptor {descriptor_id} {name} status changed")

            pointer = pointers[2]
            start = pointer - ROM_BASE
            size = spec["size"]
            if not (0 <= start <= len(rom) - size):
                raise ValueError(f"descriptor {descriptor_id} {name} palette range changed")
            palette = layer.get("palette")
            if not isinstance(palette, dict):
                raise ValueError(f"descriptor {descriptor_id} {name} palette row changed")
            expected_palette = {
                "file_offset": start,
                "gba_address": _pointer_string(pointer),
                "size": size,
                "sha256": _sha(rom[start : start + size]),
            }
            if palette.get("sha256") != expected_palette["sha256"]:
                raise ValueError("tile palette bytes changed")
            if palette != expected_palette:
                raise ValueError(f"descriptor {descriptor_id} {name} palette binding changed")
            key = (start, start + size)
            item = ranges.setdefault(
                key,
                {"bits_per_pixel": spec["bits_per_pixel"], "bindings": []},
            )
            if item["bits_per_pixel"] != spec["bits_per_pixel"]:
                raise ValueError("tile palette format conflict")
            item["bindings"].append([descriptor_id, name])
            complete_layer_counts[name] += 1
            entry_count += 1

    if tuple(
        complete_layer_counts[name] for name in ("A", "B", "C", "D")
    ) != (75, 75, 75, 11):
        raise ValueError("tile palette per-layer denominator changed")
    if entry_count != EXPECTED_TILE_PALETTE_ENTRY_COUNT:
        raise ValueError("tile palette entry denominator changed")
    if len(ranges) != EXPECTED_TILE_RAW_PALETTE_RANGE_COUNT:
        raise ValueError("tile raw palette range denominator changed")

    merged: list[dict[str, Any]] = []
    for start, end in sorted(ranges):
        source = ranges[(start, end)]
        if merged and merged[-1]["range"][1] == start:
            if merged[-1]["bits_per_pixel"] != source["bits_per_pixel"]:
                raise ValueError("adjacent tile palette formats disagree")
            merged[-1]["range"][1] = end
            merged[-1]["bindings"].extend(source["bindings"])
        else:
            merged.append(
                {
                    "range": [start, end],
                    "bits_per_pixel": source["bits_per_pixel"],
                    "bindings": list(source["bindings"]),
                }
            )
    if len(merged) != EXPECTED_TILE_MERGED_PALETTE_CLAIM_COUNT:
        raise ValueError("tile merged palette claim denominator changed")
    merged_bytes = sum(item["range"][1] - item["range"][0] for item in merged)
    if merged_bytes != EXPECTED_TILE_MERGED_PALETTE_BYTES:
        raise ValueError("tile merged palette byte denominator changed")
    return merged, complete_layer_counts, entry_count, len(ranges)


def _frozen_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for left_start, left_end, palette_start, palette_end in EXPECTED_BOUNDARIES:
        size = palette_start - left_end
        left = [left_start, left_end]
        right = [palette_start, palette_end]
        gap = [left_end, palette_start]
        rows.append(
            {
                "alignment_unit_bytes": ALIGNMENT_UNIT_BYTES,
                "bytes_sha256": _sha(b"\x00" * size),
                "gfx_stream_range": left,
                "id": f"tile-bg-lz77-palette-gap-{left_start:06x}",
                "left": left,
                "left_id": f"lz77-{left_start:06x}",
                "left_primary_class": "lz77_resource",
                "palette_range": right,
                "range": gap,
                "raw_hex": "00" * size,
                "right": right,
                "right_claim_kind": "tile_bg_palette_source_range",
                "right_id": f"tile-bg-palette-{palette_start:06x}",
                "right_primary_class": "palette_bgr555",
                "size": size,
            }
        )
    return rows


def _boundary_projection(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            key: row[key]
            for key in ("range", "left", "right", "left_id", "right_id")
        }
        for row in rows
    ]


def _right_end_align4(rows: list[dict[str, Any]]) -> bool:
    """Return whether every gap's right endpoint is four-byte aligned."""

    return all(
        row["range"][1] % ALIGNMENT_UNIT_BYTES == 0
        for row in rows
    )


def _validate_static_contract() -> None:
    frozen_rows = _frozen_rows()
    ranges = [row["range"] for row in frozen_rows]
    if _vector_sha(ranges) != EXPECTED_RANGE_VECTOR_SHA256:
        raise ValueError("range vector contract constant changed")
    if _vector_sha(_boundary_projection(frozen_rows)) != EXPECTED_BOUNDARY_VECTOR_SHA256:
        raise ValueError("boundary vector contract constant changed")
    if len(frozen_rows) != EXPECTED_GAP_COUNT:
        raise ValueError("gap count contract constant changed")
    if sum(row["size"] for row in frozen_rows) != EXPECTED_GAP_BYTES:
        raise ValueError("gap byte contract constant changed")
    counts: dict[str, int] = {}
    for row in frozen_rows:
        key = str(row["size"])
        counts[key] = counts.get(key, 0) + 1
    if counts != EXPECTED_SIZE_COUNTS:
        raise ValueError("gap size contract constant changed")


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
        "size_counts": dict(EXPECTED_SIZE_COUNTS),
        "range_vector_sha256": EXPECTED_RANGE_VECTOR_SHA256,
        "boundary_vector_sha256": EXPECTED_BOUNDARY_VECTOR_SHA256,
        "packed_bytes_sha256": None,
        "aligned_pointer_reachable_lz77_count": 0,
        "tile_descriptor_count": 0,
        "tile_palette_entry_count": 0,
        "tile_raw_palette_range_count": 0,
        "tile_merged_palette_claim_count": 0,
        "tile_merged_palette_bytes": 0,
        "all_zero": False,
        "right_end_align4": False,
        "rows": [],
        "excluded_long_gaps": [],
        "excluded_heterogeneous_gaps": [],
        "non_claims": list(NON_CLAIMS),
        "limitations": list(LIMITATIONS),
        "bound_inputs": {},
    }


def _row_for_boundary(
    left_start: int,
    left_end: int,
    palette_start: int,
    palette_end: int,
    raw: bytes,
) -> dict[str, Any]:
    return {
        "alignment_unit_bytes": ALIGNMENT_UNIT_BYTES,
        "bytes_sha256": _sha(raw),
        "gfx_stream_range": [left_start, left_end],
        "id": f"tile-bg-lz77-palette-gap-{left_start:06x}",
        "left": [left_start, left_end],
        "left_id": f"lz77-{left_start:06x}",
        "left_primary_class": "lz77_resource",
        "palette_range": [palette_start, palette_end],
        "range": [left_end, palette_start],
        "raw_hex": raw.hex(),
        "right": [palette_start, palette_end],
        "right_claim_kind": "tile_bg_palette_source_range",
        "right_id": f"tile-bg-palette-{palette_start:06x}",
        "right_primary_class": "palette_bgr555",
        "size": len(raw),
    }


def _verify_bound_inputs(
    rom: bytes,
    *,
    pointer_manifest_raw: bytes,
    pointer_payload_raw: bytes,
    tile_manifest_raw: bytes,
    exporter_source: bytes,
) -> dict[str, Any]:
    _validate_static_contract()
    _check_identity(rom, ROM_SHA256, "ROM")
    if len(rom) != ROM_SIZE:
        raise ValueError("ROM size changed")
    _check_identity(
        pointer_manifest_raw,
        POINTER_MANIFEST_SHA256,
        "pointer inventory manifest",
    )
    _check_identity(
        pointer_payload_raw,
        POINTER_PAYLOAD_SHA256,
        "pointer inventory payload",
    )
    _check_identity(tile_manifest_raw, TILE_MANIFEST_SHA256, "tile asset manifest")
    _check_identity(exporter_source, TILE_EXPORTER_SHA256, "tile asset verifier")

    pointer_manifest = _parse_json(pointer_manifest_raw, "pointer inventory manifest")
    pointer_payload = _parse_json(pointer_payload_raw, "pointer inventory payload")
    tile_manifest = _parse_json(tile_manifest_raw, "tile asset manifest")
    _validate_pointer_sources(pointer_manifest, pointer_payload)
    pointer_lz77 = _pointer_lz77_denominator(rom)
    merged, complete_counts, palette_entry_count, raw_range_count = _validate_tile_sources(
        rom, tile_manifest
    )

    palette_by_start = {item["range"][0]: item for item in merged}
    rows: list[dict[str, Any]] = []
    for stream_start, stream_end in sorted(
        pointer_lz77.items(), key=lambda item: (item[1], item[0])
    ):
        aligned_end = (
            stream_end + ALIGNMENT_UNIT_BYTES - 1
        ) & ~(ALIGNMENT_UNIT_BYTES - 1)
        if aligned_end == stream_end:
            continue
        palette = palette_by_start.get(aligned_end)
        if palette is None:
            continue
        gap_size = aligned_end - stream_end
        if gap_size not in (1, 2, 3):
            continue
        raw = rom[stream_end:aligned_end]
        row = _row_for_boundary(
            stream_start,
            stream_end,
            aligned_end,
            palette["range"][1],
            raw,
        )
        if any(raw):
            raise ValueError(f"{row['id']} alignment bytes changed")
        rows.append(row)
    rows.sort(key=lambda row: row["range"])

    expected_rows = _frozen_rows()
    if len(rows) != EXPECTED_GAP_COUNT or sum(row["size"] for row in rows) != EXPECTED_GAP_BYTES:
        raise ValueError("alignment gap denominator changed")
    if rows != expected_rows:
        raise ValueError("alignment boundary rows changed")
    ranges = [row["range"] for row in rows]
    if _vector_sha(ranges) != EXPECTED_RANGE_VECTOR_SHA256:
        raise ValueError("alignment range vector hash changed")
    boundary_vector = _boundary_projection(rows)
    if _vector_sha(boundary_vector) != EXPECTED_BOUNDARY_VECTOR_SHA256:
        raise ValueError("alignment boundary vector hash changed")
    packed = b"".join(rom[start:end] for start, end in ranges)
    if _sha(packed) != EXPECTED_PACKED_BYTES_SHA256:
        raise ValueError("packed alignment bytes changed")
    for row in rows:
        start, end = row["range"]
        left_start, left_end = row["left"]
        right_start, right_end = row["right"]
        if (
            left_end != start
            or end != right_start
            or not left_start < left_end <= start < end <= right_start < right_end
            or end % ALIGNMENT_UNIT_BYTES != 0
            or end - start not in (1, 2, 3)
            or any(rom[start:end])
        ):
            raise ValueError(f"{row['id']} adjacency or alignment changed")
    size_counts: dict[str, int] = {}
    for row in rows:
        key = str(row["size"])
        size_counts[key] = size_counts.get(key, 0) + 1
    if size_counts != EXPECTED_SIZE_COUNTS:
        raise ValueError("alignment gap size counts changed")

    excluded_long_gaps = []
    for start, end in EXPECTED_LONG_GAPS:
        raw = rom[start:end]
        evidence = {
            "range": [start, end],
            "size": end - start,
            "contains_nonzero": any(raw),
            "bytes_sha256": _sha(raw),
        }
        if not evidence["contains_nonzero"]:
            raise ValueError("excluded long-gap evidence changed")
        excluded_long_gaps.append(evidence)
    excluded_heterogeneous_gaps = [
        {
            "range": [start, end],
            "size": end - start,
            "reason": "heterogeneous direct-CpuSet/reuse short gap",
        }
        for start, end in EXPECTED_HETEROGENEOUS_GAPS
    ]
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
        "range_vector_sha256": _vector_sha(ranges),
        "boundary_vector_sha256": _vector_sha(boundary_vector),
        "packed_bytes_sha256": _sha(packed),
        "aligned_pointer_reachable_lz77_count": len(pointer_lz77),
        "tile_descriptor_count": TABLE_ENTRY_COUNT,
        "tile_palette_entry_count": palette_entry_count,
        "tile_raw_palette_range_count": raw_range_count,
        "tile_merged_palette_claim_count": len(merged),
        "tile_merged_palette_bytes": sum(
            item["range"][1] - item["range"][0] for item in merged
        ),
        "tile_complete_layer_counts": complete_counts,
        "all_zero": not any(packed),
        "right_end_align4": _right_end_align4(rows),
        "rows": rows,
        "excluded_long_gaps": excluded_long_gaps,
        "excluded_heterogeneous_gaps": excluded_heterogeneous_gaps,
        "non_claims": list(NON_CLAIMS),
        "limitations": list(LIMITATIONS),
    }


def verify_inputs(
    rom: bytes,
    *,
    pointer_manifest: bytes,
    pointer_payload: bytes,
    tile_manifest: bytes,
    exporter_source: bytes,
) -> dict[str, Any]:
    """Verify already-loaded bound inputs without opening repository paths."""

    report = _empty_report()
    try:
        report = _verify_bound_inputs(
            rom,
            pointer_manifest_raw=pointer_manifest,
            pointer_payload_raw=pointer_payload,
            tile_manifest_raw=tile_manifest,
            exporter_source=exporter_source,
        )
    except (
        OSError,
        TypeError,
        ValueError,
        KeyError,
        IndexError,
        UnicodeError,
        json.JSONDecodeError,
        struct.error,
    ) as error:
        report["errors"].append(str(error))
    return report


def verify_root_from_bytes(
    rom: bytes,
    *,
    pointer_manifest: bytes,
    pointer_payload: bytes,
    tile_manifest: bytes,
    exporter_source: bytes,
) -> dict[str, Any]:
    """Test seam for mutated ROM bytes; no filesystem reads or writes occur."""

    return verify_inputs(
        rom,
        pointer_manifest=pointer_manifest,
        pointer_payload=pointer_payload,
        tile_manifest=tile_manifest,
        exporter_source=exporter_source,
    )


def verify_root(raw_root: Path) -> dict[str, Any]:
    """Safely load the five frozen inputs from a repository root and verify them."""

    report = _empty_report()
    try:
        root = _safe_root(raw_root)
        bound_paths = (
            (ROM_PATH, ROM_SHA256),
            (POINTER_MANIFEST_PATH, POINTER_MANIFEST_SHA256),
            (POINTER_PAYLOAD_PATH, POINTER_PAYLOAD_SHA256),
            (TILE_MANIFEST_PATH, TILE_MANIFEST_SHA256),
            (TILE_EXPORTER_PATH, TILE_EXPORTER_SHA256),
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
            tile_manifest=loaded[TILE_MANIFEST_PATH],
            exporter_source=loaded[TILE_EXPORTER_PATH],
        )
        report["bound_inputs"] = bound_inputs
    except (
        OSError,
        TypeError,
        ValueError,
        KeyError,
        IndexError,
        UnicodeError,
        json.JSONDecodeError,
        struct.error,
    ) as error:
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
