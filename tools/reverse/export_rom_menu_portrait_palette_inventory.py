#!/usr/bin/env python3
"""Export the fixed physical menu/story portrait GBA BGR555 palettes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Any


SCHEMA = "rom-menu-portrait-palette-inventory-v1"
VERIFY_SCHEMA = "rom-menu-portrait-palette-inventory-verification-v1"
ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

CATALOG_MANIFEST = Path("artifacts/menu-portraits-v1/manifest.json")
CATALOG_SHA256 = "cd54c20d774a2aa69c7a41db396ca344157320882602b03a00ccd83851a791b3"
CATALOG_SCHEMA = "menu-portrait-export-v1"
CATALOG_RESOURCE_VECTOR_SHA256 = (
    "aacf1dd777711ffddd46d268b419da0887002557004064c38d51e5b299521c3b"
)

TABLE_OFFSET = 0x5A4DEC
TABLE_GBA_ADDRESS = ROM_BASE + TABLE_OFFSET
TABLE_ENTRY_COUNT = 63
TABLE_ENTRY_SIZE = 0x28
VARIANTS_PER_ENTRY = 5
TABLE_SIZE = TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
TABLE_SHA256 = "bfc995240519eca9035e140a45e506a5c1f6f561e05827a589b5ac03543bba7e"
SPECIAL_PAIR_OFFSET = TABLE_OFFSET - 8
SPECIAL_PAIR_GBA_ADDRESS = ROM_BASE + SPECIAL_PAIR_OFFSET
SPECIAL_PAIR_RAW_SHA256 = (
    "878734508bacadb5190d10484f55a6958ffecc6119841dbe08dad145a4ad9049"
)

SELECTOR_START = 0x096138
SELECTOR_END = 0x096162
SELECTOR_GBA_START = ROM_BASE + SELECTOR_START
SELECTOR_GBA_END = ROM_BASE + SELECTOR_END
SELECTOR_SHA256 = "6a981ff31b2c8dbf979d0ffab751ccfa395e70e2a6e85380f549535295fee96e"
SELECTOR_RAW_HEX = (
    "00b50006020e0906090e052904d1014809e00000e44d5a0890008018c000c900024a"
    "8918401802bc0847"
)

PALETTE_STARTS = (
    0x4098C4,
    0x40A6A4,
    0x40B4F8,
    0x40C260,
    0x40D128,
    0x40DE80,
    0x40E9D8,
    0x40F59C,
    0x41029C,
    0x410F60,
    0x411C54,
    0x412984,
    0x413738,
    0x4146B0,
    0x415594,
    0x4163B8,
    0x417178,
    0x417BB4,
    0x418A08,
    0x4196C8,
    0x41A35C,
    0x41B1D8,
    0x41BF8C,
    0x41CCE8,
    0x41D904,
    0x41E44C,
    0x41EFB4,
    0x41F980,
    0x420604,
    0x42126C,
    0x421DE8,
    0x422D4C,
    0x4239A8,
    0x42491C,
    0x425478,
    0x4261D0,
    0x426EB4,
    0x427B94,
    0x4287A4,
    0x4291E4,
    0x429DEC,
    0x42A9E4,
    0x42B4F4,
    0x42C1E4,
    0x42CEB4,
    0x42DDA8,
    0x42E800,
    0x42F288,
    0x42FE44,
    0x430D04,
    0x431CC4,
    0x432C60,
    0x433C88,
    0x434618,
    0x435278,
    0x4361F8,
    0x43704C,
    0x437E2C,
    0x438B64,
    0x439838,
    0x43A4E4,
    0x43B0F8,
    0x43BFB0,
    0x43CCE4,
    0x43D938,
    0x43E4D0,
    0x43EF4C,
    0x43FBF8,
    0x440738,
    0x441324,
)
PALETTE_SIZE = 128
RANGE_VECTOR = [[start, start + PALETTE_SIZE] for start in PALETTE_STARTS]
RANGE_VECTOR_SHA256 = (
    "84e8b9f99a51f94e1b9e0b972d6458c883428443aa173a9f739beaf601b4e338"
)
BUNDLE_SHA256 = "d5d80e37d88000ec81501d9549b4c6038c42e6ec172614127821213d9dbcdccc"

WRITEBACK_MANIFEST = Path("artifacts/menu-portrait-writeback-v1/manifest.json")
WRITEBACK_MANIFEST_SHA256 = "dbae133169f8ced45eb0893535084c5488345cfe2d3be6c6fef1611e3352278a"
WRITEBACK_PAYLOAD = Path("artifacts/menu-portrait-writeback-v1/menu-portrait-writeback.json")
WRITEBACK_PAYLOAD_SHA256 = "4d85be165101f35e53b2cf682d6db21a68a3010e7c8bcc0e8a8f9b5f05e00679"
WRITEBACK_VERIFIER = Path("tools/verify_menu_portrait_writeback_audit.py")
WRITEBACK_VERIFIER_SHA256 = "6df2c2b1c9b2495d882a01111da9894da9adab894161b3126f28d0cb97324734"
WRITEBACK_REPORT = {
    "schema": "menu-portrait-writeback-verification-v1",
    "verified": True,
    "resource_count": 74,
    "errors": [],
}

QUEUE_DIR = Path("artifacts/rom-gpu-copy-queue-inventory-v1")
QUEUE_MANIFEST = QUEUE_DIR / "manifest.json"
QUEUE_MANIFEST_SHA256 = "3a3f4d06f27560dfcf2674c13802e2fbcc551246e5de121b1f62747a09f32a95"
QUEUE_PAYLOAD = QUEUE_DIR / "rom-gpu-copy-queue-inventory.json"
QUEUE_PAYLOAD_SHA256 = "798b72cbeb69cae522f77f586794cd0bf9d1775d57d590479daf89e808ca23bf"
QUEUE_VERIFIER = Path("tools/verify_rom_gpu_copy_queue_inventory.py")
QUEUE_VERIFIER_SHA256 = "7314eef6758b055a9a30dc5778e1d001b1328a9c65a1435306f44759b52f2ce0"
QUEUE_REPORT = {
    "schema": "rom-gpu-copy-queue-inventory-verification-v1",
    "verified": True,
    "direct_caller_count": 14,
    "new_rom_source_count": 0,
    "errors": [],
}
QUEUE_PALETTE_CALLS = (
    0x080962FE,
    0x0809655C,
    0x080965A4,
    0x08096DBA,
    0x08096E00,
)

PAYLOAD_NAME = "rom-menu-portrait-palette-inventory.json"
BUNDLE_NAME = "rom-menu-portrait-palettes.bin"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME}
IMPLEMENTATION_PATHS = {
    "exporter": Path("tools/export_rom_menu_portrait_palette_inventory.py"),
    "verifier": Path("tools/verify_rom_menu_portrait_palette_inventory.py"),
    "test": Path("tests/test_export_rom_menu_portrait_palette_inventory.py"),
}

SCOPE = {
    "fixed_palette_byte_inventory_complete": True,
    "source_resource_aliases_complete": True,
    "fixed_length_palette_writeback_verified": True,
    "natural_gameplay_all_logical_outputs_proven": False,
    "dynamic_caller_input_domain_complete": False,
    "graphics_bytes_classified_here": False,
    "adjacent_gaps_classified": False,
    "runtime_pixel_equivalence": False,
    "arbitrary_image_writeback": False,
    "relocation_complete": False,
    "pointer_rewrite_complete": False,
    "safe_free_space_claimed": False,
}
LIMITATIONS = [
    "The complete denominator is the 70 fixed, non-overlapping 128-byte physical palette ranges referenced by the accepted 74-resource catalog.",
    "The 311 logical denominator is exactly (63 - 1) * 5 + 1: record 0's five zero pairs are physical sentinels, not logical outputs; the catalog domain is records 1..62, variants 0..4, plus the special variant 5 pair.",
    "The selector truncates record and variant inputs to u8 and has no bounds check; this artifact does not claim arbitrary dynamic caller inputs or natural gameplay reachability.",
    "Physical deduplication is by palette pointer/range, not by byte-content hash; distinct physical ranges may have identical bytes.",
    "Palette writeback is fixed-length 128-byte evidence only. An in-place edit of the shared 0x084098C4 palette affects all five aliased resources and independent splitting requires relocation.",
    "Graphics bytes, adjacent gaps, arbitrary image fit, pointer rewriting, relocation, safe free space, runtime pixel equivalence, and natural gameplay coverage are not claimed.",
]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _vector_hash(value: Any) -> str:
    return _sha(json.dumps(value, separators=(",", ":")).encode())


def _pointer(value: int) -> str:
    return f"0x{value:08X}"


def _safe_file(root: Path, relative: Path, expected_sha: str | None = None) -> Path:
    root = root.resolve(strict=True)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative path: {relative}")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {relative}")
    path = (root / relative).resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"repository input escapes root: {relative}") from error
    if not path.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    if expected_sha is not None and _sha(path.read_bytes()) != expected_sha:
        raise ValueError(f"bound source identity changed: {relative}")
    return path


def _read_bound(root: Path, relative: Path, expected_sha: str) -> bytes:
    return _safe_file(root, relative, expected_sha).read_bytes()


def _json_bound(root: Path, relative: Path, expected_sha: str) -> dict[str, Any]:
    value = json.loads(_read_bound(root, relative, expected_sha))
    if not isinstance(value, dict):
        raise ValueError(f"bound JSON is not an object: {relative}")
    return value


def _u16(rom: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(rom):
        raise ValueError("u16 read is outside ROM")
    return struct.unpack_from("<H", rom, offset)[0]


def _u32(rom: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(rom):
        raise ValueError("u32 read is outside ROM")
    return struct.unpack_from("<I", rom, offset)[0]


def _selector_branch_target(address: int, instruction: int) -> int:
    if instruction & 0xF800 != 0xD000:
        raise ValueError("selector conditional branch encoding changed")
    imm8 = instruction & 0xFF
    if imm8 & 0x80:
        imm8 -= 0x100
    return address + 4 + imm8 * 2


def _selector_unconditional_target(address: int, instruction: int) -> int:
    if instruction & 0xF800 != 0xE000:
        raise ValueError("selector unconditional branch encoding changed")
    imm11 = instruction & 0x7FF
    if imm11 & 0x400:
        imm11 -= 0x800
    return address + 4 + imm11 * 2


def selector_pair(rom: bytes, record: int, variant: int) -> dict[str, Any]:
    record_u8 = record & 0xFF
    variant_u8 = variant & 0xFF
    if variant_u8 == 5:
        pair_offset = SPECIAL_PAIR_OFFSET
    else:
        pair_offset = TABLE_OFFSET + record_u8 * TABLE_ENTRY_SIZE + variant_u8 * 8
    if pair_offset < 0 or pair_offset + 8 > len(rom):
        raise ValueError("selector pair escapes ROM")
    gfx = _u32(rom, pair_offset)
    palette = _u32(rom, pair_offset + 4)
    return {
        "record_input": record,
        "variant_input": variant,
        "record_u8": record_u8,
        "variant_u8": variant_u8,
        "pair_file_offset": pair_offset,
        "pair_gba_address": _pointer(ROM_BASE + pair_offset),
        "gfx_pointer": _pointer(gfx),
        "palette_pointer": _pointer(palette),
    }


def validate_selector(rom: bytes) -> dict[str, Any]:
    raw = rom[SELECTOR_START:SELECTOR_END]
    if len(raw) != SELECTOR_END - SELECTOR_START:
        raise ValueError("selector function range is outside ROM")
    if _sha(raw) != SELECTOR_SHA256:
        raise ValueError("selector function raw identity changed")
    expected_words = {
        0x096138: 0xB500,
        0x09613A: 0x0600,
        0x09613C: 0x0E02,
        0x09613E: 0x0609,
        0x096140: 0x0E09,
        0x096142: 0x2905,
        0x096146: 0x4801,
        0x096148: 0xE009,
        0x096150: 0x0090,
        0x096152: 0x1880,
        0x096154: 0x00C0,
        0x096156: 0x00C9,
        0x096158: 0x4A02,
        0x09615A: 0x1889,
        0x09615C: 0x1840,
        0x09615E: 0xBC02,
        0x096160: 0x4708,
    }
    for offset, expected in expected_words.items():
        if _u16(rom, offset) != expected:
            raise ValueError(f"selector Thumb instruction changed at 0x{offset:06X}")
    if _u16(rom, 0x096144) != 0xD104:
        raise ValueError("selector BNE condition changed")
    if _selector_branch_target(0x096144, _u16(rom, 0x096144)) != 0x096150:
        raise ValueError("selector BNE branch target changed")
    if _selector_unconditional_target(0x096148, _u16(rom, 0x096148)) != 0x09615E:
        raise ValueError("selector special branch target changed")
    if _u32(rom, 0x09614C) != 0x085A4DE4:
        raise ValueError("selector special pair literal changed")
    if _u32(rom, 0x096160 + 4) != 0x085A4DEC:
        raise ValueError("selector table-base literal changed")

    normal = selector_pair(rom, 1, 4)
    special = selector_pair(rom, 62, 5)
    truncated = selector_pair(rom, 0x101, 0x104)
    if normal["pair_file_offset"] != TABLE_OFFSET + 40 + 32:
        raise ValueError("selector normal pair formula changed")
    if special["pair_file_offset"] != SPECIAL_PAIR_OFFSET:
        raise ValueError("selector special pair formula changed")
    if truncated["record_u8"] != 1 or truncated["variant_u8"] != 4:
        raise ValueError("selector u8 truncation changed")
    return {
        "function": {
            "range": [SELECTOR_START, SELECTOR_END],
            "file_range": [SELECTOR_START, SELECTOR_END],
            "gba_range": [_pointer(SELECTOR_GBA_START), _pointer(SELECTOR_GBA_END)],
            "size": len(raw),
            "sha256": _sha(raw),
            "raw_hex": raw.hex(),
        },
        "formula": {
            "record_input": "u8(record)",
            "variant_input": "u8(variant)",
            "special_condition": "variant_u8 == 5",
            "normal_condition": "otherwise; no variant<5 bounds check is claimed",
            "normal_pair": "0x085A4DEC + record_u8*40 + variant_u8*8",
            "special_pair": "0x085A4DE4",
            "record_stride": 40,
            "variant_stride": 8,
            "pair_fields": {"gfx_pointer_offset": 0, "palette_pointer_offset": 4},
            "has_bounds_check": False,
            "catalog_domain": "record 1..62 × variant 0..4 plus special variant 5",
            "dynamic_caller_input_domain_complete": False,
        },
        "sample_pairs": {
            "normal": normal,
            "special": special,
            "u8_truncation": truncated,
        },
    }


def _run_upstream_verifiers(root: Path) -> dict[str, dict[str, Any]]:
    commands = (
        (
            "writeback",
            WRITEBACK_VERIFIER,
            ["--root", str(root), "--artifact", str(root / WRITEBACK_MANIFEST.parent)],
            WRITEBACK_REPORT,
        ),
        (
            "queue",
            QUEUE_VERIFIER,
            ["--root", str(root), "--artifact-dir", str(root / QUEUE_DIR)],
            QUEUE_REPORT,
        ),
    )
    reports: dict[str, dict[str, Any]] = {}
    for name, script, arguments, expected in commands:
        script_path = _safe_file(root, script)
        completed = subprocess.run(
            [sys.executable, str(script_path), *arguments],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        try:
            report = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"{name} verifier returned invalid JSON") from error
        if completed.returncode != 0 or report != expected:
            raise ValueError(
                f"{name} verifier report changed: exit={completed.returncode}, report={report}, "
                f"stderr={completed.stderr.decode('utf-8', 'replace')}"
            )
        reports[name] = report
    return reports


def _source_identity(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    catalog = _json_bound(root, CATALOG_MANIFEST, CATALOG_SHA256)
    if catalog.get("schema") != CATALOG_SCHEMA:
        raise ValueError("menu portrait catalog schema changed")
    writeback_manifest = _json_bound(root, WRITEBACK_MANIFEST, WRITEBACK_MANIFEST_SHA256)
    writeback_payload = _read_bound(root, WRITEBACK_PAYLOAD, WRITEBACK_PAYLOAD_SHA256)
    _read_bound(root, WRITEBACK_VERIFIER, WRITEBACK_VERIFIER_SHA256)
    if writeback_manifest.get("files", {}).get(WRITEBACK_PAYLOAD.name) != WRITEBACK_PAYLOAD_SHA256:
        raise ValueError("writeback source payload identity changed")
    queue_manifest = _json_bound(root, QUEUE_MANIFEST, QUEUE_MANIFEST_SHA256)
    queue_payload = _json_bound(root, QUEUE_PAYLOAD, QUEUE_PAYLOAD_SHA256)
    _read_bound(root, QUEUE_VERIFIER, QUEUE_VERIFIER_SHA256)
    if queue_manifest.get("files", {}).get(QUEUE_PAYLOAD.name) != QUEUE_PAYLOAD_SHA256:
        raise ValueError("queue source payload identity changed")
    if not writeback_payload or not queue_payload:
        raise ValueError("upstream source payload is empty")
    routes = queue_payload.get("instruction_evidence", {}).get("menu_palette_routes")
    if routes != [
        {
            "destination_base": "0x05000200",
            "enqueue_callsite": _pointer(address),
            "palette_load": _pointer(load),
            "palette_load_offset": 4,
            "selector_callsite": _pointer(selector),
            "selector_target": "0x08096138",
            "size_bytes": 128,
        }
        for address, load, selector in (
            (0x080962FE, 0x080962F8, 0x08096298),
            (0x0809655C, 0x08096550, 0x0809654C),
            (0x080965A4, 0x08096598, 0x08096594),
            (0x08096DBA, 0x08096DB4, 0x08096DB0),
            (0x08096E00, 0x08096DFA, 0x08096DF6),
        )
    ]:
        raise ValueError("queue menu palette route evidence changed")
    source = {
        "catalog": {
            "path": CATALOG_MANIFEST.as_posix(),
            "sha256": CATALOG_SHA256,
            "schema": CATALOG_SCHEMA,
            "resource_vector_sha256": CATALOG_RESOURCE_VECTOR_SHA256,
        },
        "writeback": {
            "manifest": {"path": WRITEBACK_MANIFEST.as_posix(), "sha256": WRITEBACK_MANIFEST_SHA256},
            "payload": {"path": WRITEBACK_PAYLOAD.as_posix(), "sha256": WRITEBACK_PAYLOAD_SHA256},
            "verifier": {"path": WRITEBACK_VERIFIER.as_posix(), "sha256": WRITEBACK_VERIFIER_SHA256},
        },
        "queue": {
            "manifest": {"path": QUEUE_MANIFEST.as_posix(), "sha256": QUEUE_MANIFEST_SHA256},
            "payload": {"path": QUEUE_PAYLOAD.as_posix(), "sha256": QUEUE_PAYLOAD_SHA256},
            "verifier": {"path": QUEUE_VERIFIER.as_posix(), "sha256": QUEUE_VERIFIER_SHA256},
        },
    }
    return catalog, queue_payload, source


def _logical_outputs(rom: bytes, catalog: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[tuple[int, int], int]]:
    resources = catalog.get("unique_resources")
    if not isinstance(resources, list) or len(resources) != 74:
        raise ValueError("catalog resource denominator changed")
    by_pair: dict[tuple[int, int], int] = {}
    vector = []
    for expected_id, row in enumerate(resources):
        if row.get("resource_id") != expected_id:
            raise ValueError("catalog resource IDs are not canonical")
        palette_offset = row.get("palette_file_offset")
        palette_sha = row.get("palette_sha256")
        vector.append([expected_id, palette_offset, palette_sha])
        pair = (int(row["gfx_pointer"], 16), int(row["palette_pointer"], 16))
        if pair in by_pair:
            raise ValueError("catalog resource pair identity is not unique")
        by_pair[pair] = expected_id
    if _vector_hash(vector) != CATALOG_RESOURCE_VECTOR_SHA256:
        raise ValueError("catalog resource vector changed")

    outputs: list[dict[str, Any]] = []
    logical_id = 0
    for record_id in range(1, TABLE_ENTRY_COUNT):
        for variant in range(VARIANTS_PER_ENTRY):
            selected = selector_pair(rom, record_id, variant)
            pair = (int(selected["gfx_pointer"], 16), int(selected["palette_pointer"], 16))
            if pair not in by_pair:
                raise ValueError("catalog is missing a nonzero table pair")
            outputs.append(
                {
                    "logical_id": logical_id,
                    "record_id": record_id,
                    "variant": variant,
                    "kind": "matrix",
                    "pair_file_offset": selected["pair_file_offset"],
                    "pair_gba_address": selected["pair_gba_address"],
                    "gfx_pointer": selected["gfx_pointer"],
                    "palette_pointer": selected["palette_pointer"],
                    "resource_id": by_pair[pair],
                }
            )
            logical_id += 1
    special = selector_pair(rom, 0, 5)
    pair = (int(special["gfx_pointer"], 16), int(special["palette_pointer"], 16))
    if pair not in by_pair:
        raise ValueError("catalog is missing special pair")
    outputs.append(
        {
            "logical_id": logical_id,
            "record_id": None,
            "variant": 5,
            "kind": "global_special",
            "pair_file_offset": SPECIAL_PAIR_OFFSET,
            "pair_gba_address": _pointer(SPECIAL_PAIR_GBA_ADDRESS),
            "gfx_pointer": special["gfx_pointer"],
            "palette_pointer": special["palette_pointer"],
            "resource_id": by_pair[pair],
        }
    )
    if len(outputs) != 311:
        raise ValueError("logical output denominator changed")
    portraits = catalog.get("portraits")
    if not isinstance(portraits, list) or len(portraits) != 311:
        raise ValueError("catalog logical portrait denominator changed")
    for expected, portrait in zip(outputs, portraits, strict=True):
        if (
            portrait.get("resource_id") != expected["resource_id"]
            or portrait.get("variant") != expected["variant"]
            or portrait.get("kind") != expected["kind"]
            or portrait.get("pair_file_offset") != expected["pair_file_offset"]
            or portrait.get("gfx_pointer") != expected["gfx_pointer"]
            or portrait.get("palette_pointer") != expected["palette_pointer"]
        ):
            raise ValueError("catalog logical portrait mapping changed")
    return outputs, by_pair


def _table_evidence(rom: bytes) -> dict[str, Any]:
    table = rom[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE]
    if len(table) != TABLE_SIZE or _sha(table) != TABLE_SHA256:
        raise ValueError("portrait pointer table identity changed")
    sentinel = table[:TABLE_ENTRY_SIZE]
    if sentinel != bytes(TABLE_ENTRY_SIZE):
        raise ValueError("record 0 sentinel row changed")
    special = rom[SPECIAL_PAIR_OFFSET : SPECIAL_PAIR_OFFSET + 8]
    if len(special) != 8 or _sha(special) != SPECIAL_PAIR_RAW_SHA256:
        raise ValueError("special variant pair identity changed")
    return {
        "file_offset": TABLE_OFFSET,
        "gba_address": _pointer(TABLE_GBA_ADDRESS),
        "entry_count": TABLE_ENTRY_COUNT,
        "entry_size": TABLE_ENTRY_SIZE,
        "variants_per_entry": VARIANTS_PER_ENTRY,
        "total_table_slots": TABLE_ENTRY_COUNT * VARIANTS_PER_ENTRY,
        "zero_sentinel_slots": VARIANTS_PER_ENTRY,
        "matrix_nonzero_outputs": (TABLE_ENTRY_COUNT - 1) * VARIANTS_PER_ENTRY,
        "table_size": TABLE_SIZE,
        "sha256": _sha(table),
        "record0_range": [TABLE_OFFSET, TABLE_OFFSET + TABLE_ENTRY_SIZE],
        "record0_raw_sha256": _sha(sentinel),
        "special_pair_range": [SPECIAL_PAIR_OFFSET, SPECIAL_PAIR_OFFSET + 8],
        "special_pair_gba_address": _pointer(SPECIAL_PAIR_GBA_ADDRESS),
        "special_pair_raw_sha256": _sha(special),
    }


def _physical_palettes(rom: bytes, catalog: dict[str, Any], logical: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bytes]:
    resources = catalog["unique_resources"]
    by_offset: dict[int, list[dict[str, Any]]] = {}
    logical_by_resource: dict[int, list[dict[str, Any]]] = {index: [] for index in range(74)}
    for item in logical:
        logical_by_resource[item["resource_id"]].append(item)
    for row in resources:
        offset = int(row["palette_file_offset"])
        if int(row["palette_size"]) != PALETTE_SIZE:
            raise ValueError("catalog palette size changed")
        pointer = int(row["palette_pointer"], 16)
        if pointer != ROM_BASE + offset:
            raise ValueError("catalog palette pointer/file offset mismatch")
        raw = rom[offset : offset + PALETTE_SIZE]
        if len(raw) != PALETTE_SIZE or _sha(raw) != row["palette_sha256"]:
            raise ValueError(f"catalog palette bytes changed for resource {row['resource_id']}")
        if int(row["reuse_count"]) != len(logical_by_resource[row["resource_id"]]):
            raise ValueError("catalog resource logical alias count changed")
        by_offset.setdefault(offset, []).append(row)

    derived_ranges = [[offset, offset + PALETTE_SIZE] for offset in sorted(by_offset)]
    if derived_ranges != RANGE_VECTOR or _vector_hash(derived_ranges) != RANGE_VECTOR_SHA256:
        raise ValueError("physical palette range denominator changed")
    records: list[dict[str, Any]] = []
    bundle = bytearray()
    for physical_id, (start, end) in enumerate(derived_ranges):
        rows = sorted(by_offset[start], key=lambda row: row["resource_id"])
        raw = rom[start:end]
        packed = [len(bundle), len(bundle) + len(raw)]
        bundle.extend(raw)
        aliases = []
        pointer_identities = []
        resource_ids = []
        for row in rows:
            resource_id = row["resource_id"]
            resource_ids.append(resource_id)
            pointer_identities.append(
                {
                    "resource_id": resource_id,
                    "gfx_pointer": row["gfx_pointer"],
                    "palette_pointer": row["palette_pointer"],
                    "palette_file_offset": row["palette_file_offset"],
                    "palette_sha256": row["palette_sha256"],
                }
            )
            for item in logical_by_resource[resource_id]:
                aliases.append(
                    {
                        "logical_id": item["logical_id"],
                        "record_id": item["record_id"],
                        "variant": item["variant"],
                        "kind": item["kind"],
                        "pair_file_offset": item["pair_file_offset"],
                        "resource_id": resource_id,
                    }
                )
        if resource_ids != sorted(resource_ids):
            raise ValueError("physical resource IDs are not canonical")
        records.append(
            {
                "physical_id": physical_id,
                "range": [start, end],
                "gba_range": [_pointer(ROM_BASE + start), _pointer(ROM_BASE + end)],
                "size": len(raw),
                "raw_sha256": _sha(raw),
                "palette_sha256": _sha(raw),
                "resource_ids": resource_ids,
                "alias_count": len(resource_ids),
                "logical_alias_count": len(aliases),
                "palette_pointer_identities": pointer_identities,
                "resource_aliases": resource_ids,
                "logical_aliases": aliases,
                "packed_range": packed,
            }
        )
    if len(records) != 70 or len(bundle) != 8_960 or _sha(bytes(bundle)) != BUNDLE_SHA256:
        raise ValueError("physical palette bundle denominator changed")
    if sum(len(row["logical_aliases"]) for row in records) != 311:
        raise ValueError("physical logical alias denominator changed")
    return records, bytes(bundle)


def _implementation(root: Path) -> dict[str, dict[str, str]]:
    root = root.resolve(strict=True)
    loaded_root = Path(__file__).resolve().parents[1]
    result: dict[str, dict[str, str]] = {}
    for label, path in IMPLEMENTATION_PATHS.items():
        passed_bytes = _safe_file(root, path).read_bytes()
        loaded_bytes = _safe_file(loaded_root, path).read_bytes()
        if passed_bytes != loaded_bytes:
            raise ValueError(
                f"loaded implementation does not match passed root: {path}"
            )
        result[label] = {"path": path.as_posix(), "sha256": _sha(passed_bytes)}
    return result


def _source_payload(
    root: Path,
    catalog: dict[str, Any],
    queue_payload: dict[str, Any],
    source: dict[str, Any],
    reports: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], bytes]:
    rom = _read_bound(root, ROM_PATH, ROM_SHA256)
    if len(rom) != ROM_SIZE:
        raise ValueError("fixed ROM size changed")
    selector = validate_selector(rom)
    table = _table_evidence(rom)
    logical, by_pair = _logical_outputs(rom, catalog)
    records, bundle = _physical_palettes(rom, catalog, logical)
    content_hash_count = len({row["raw_sha256"] for row in records})
    alias_groups = [row for row in records if row["alias_count"] > 1]
    if len(alias_groups) != 1 or alias_groups[0]["range"][0] != 0x4098C4:
        raise ValueError("physical alias group denominator changed")
    if alias_groups[0]["resource_ids"] != [0, 67, 68, 69, 70]:
        raise ValueError("physical alias resource IDs changed")
    if alias_groups[0]["logical_alias_count"] != 56:
        raise ValueError("physical alias logical count changed")
    queue_routes = queue_payload["instruction_evidence"]["menu_palette_routes"]
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "source": {
            **source,
            "resource_vector_sha256": CATALOG_RESOURCE_VECTOR_SHA256,
            "resource_vector": [
                [row["resource_id"], row["palette_file_offset"], row["palette_sha256"]]
                for row in catalog["unique_resources"]
            ],
            "range_vector": RANGE_VECTOR,
            "table": table,
            "special_pair_raw_hex": rom[SPECIAL_PAIR_OFFSET : SPECIAL_PAIR_OFFSET + 8].hex(),
        },
        "selector": selector,
        "queue": {
            "verifier_report": reports["queue"],
            "menu_palette_callers": [
                {
                    "enqueue_callsite": route["enqueue_callsite"],
                    "selector_callsite": route["selector_callsite"],
                    "palette_load": route["palette_load"],
                    "palette_load_offset": route["palette_load_offset"],
                    "destination_base": route["destination_base"],
                    "size_bytes": route["size_bytes"],
                }
                for route in queue_routes
            ],
            "menu_palette_caller_file_offsets": [
                route["enqueue_callsite"] - ROM_BASE for route in (
                    {"enqueue_callsite": 0x080962FE},
                    {"enqueue_callsite": 0x0809655C},
                    {"enqueue_callsite": 0x080965A4},
                    {"enqueue_callsite": 0x08096DBA},
                    {"enqueue_callsite": 0x08096E00},
                )
            ],
            "palette_source_formula": "u32[Pair(u8(record),u8(variant))+4]",
            "runtime_upload_claimed": False,
        },
        "writeback": {
            "verifier_report": reports["writeback"],
            "palette_fixed_length_writeback_count": 74,
            "palette_fixed_length_writeback_complete": True,
            "shared_alias_in_place_effect": "one physical write affects all five aliased resources",
            "independent_alias_split_requires_relocation": True,
        },
        "logical_denominator": {
            "total_table_slots": 315,
            "zero_sentinel_slots": 5,
            "matrix_nonzero_outputs": 310,
            "special_outputs": 1,
            "logical_outputs": 311,
            "formula": "(63 - 1) * 5 + 1",
            "catalog_domain": "record 1..62 × variant 0..4 plus special variant 5",
            "natural_gameplay_all_logical_outputs_proven": False,
            "dynamic_caller_input_domain_complete": False,
        },
        "resource_provenance": [
            {
                "resource_id": row["resource_id"],
                "gfx_pointer": row["gfx_pointer"],
                "palette_pointer": row["palette_pointer"],
                "gfx_file_offset": row["gfx_file_offset"],
                "palette_file_offset": row["palette_file_offset"],
                "palette_size": row["palette_size"],
                "palette_sha256": row["palette_sha256"],
                "logical_output_count": row["reuse_count"],
            }
            for row in catalog["unique_resources"]
        ],
        "logical_outputs": logical,
        "physical_palettes": records,
        "summary": {
            "logical_output_count": 311,
            "source_resource_count": 74,
            "unique_palette_count": 70,
            "unique_palette_content_hash_count": content_hash_count,
            "alias_group_count": 1,
            "aliased_resource_count": 5,
            "aliased_logical_output_count": 56,
            "logical_alias_count": 311,
            "palette_bytes": 8_960,
            "packed_bytes": 8_960,
            "range_overlap_bytes": 0,
            "range_vector_sha256": RANGE_VECTOR_SHA256,
            "bundle_sha256": BUNDLE_SHA256,
        },
        "files": {BUNDLE_NAME: {"size": len(bundle), "sha256": BUNDLE_SHA256}},
        "scope": SCOPE,
        "limitations": LIMITATIONS,
        "implementation": _implementation(root),
        "implementation_binding": {
            "kind": "passed-root-files-equal-loaded-script-root",
            "loaded_root_derived_from": "__file__",
            "paths": sorted(path.as_posix() for path in IMPLEMENTATION_PATHS.values()),
        },
    }
    if len(by_pair) != 74:
        raise ValueError("resource pair denominator changed")
    return payload, bundle


def build_payload(root: Path | str) -> tuple[dict[str, Any], bytes]:
    root = Path(root).resolve(strict=True)
    catalog, queue_payload, source = _source_identity(root)
    reports = _run_upstream_verifiers(root)
    return _source_payload(root, catalog, queue_payload, source, reports)


def _expected_report(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload["summary"]
    return {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        "logical_output_count": summary["logical_output_count"],
        "source_resource_count": summary["source_resource_count"],
        "unique_palette_count": summary["unique_palette_count"],
        "alias_group_count": summary["alias_group_count"],
        "aliased_resource_count": summary["aliased_resource_count"],
        "palette_bytes": summary["palette_bytes"],
        "packed_bytes": summary["packed_bytes"],
        "range_overlap_bytes": summary["range_overlap_bytes"],
        "range_vector_sha256": summary["range_vector_sha256"],
        "bundle_sha256": summary["bundle_sha256"],
        "errors": [],
    }


def _promotion_manifest(payload: dict[str, Any], files: dict[str, bytes], report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {name: _sha(raw) for name, raw in sorted(files.items())},
        "scope": SCOPE,
        "source": payload["source"],
        "producer": {
            "command": [
                "python3",
                "tools/export_rom_menu_portrait_palette_inventory.py",
                "--root",
                ".",
                "--output-dir",
                f"artifacts/{SCHEMA}",
            ],
            **payload["implementation"],
            "implementation_binding": payload["implementation_binding"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_rom_menu_portrait_palette_inventory.py",
                "--root",
                ".",
                "--artifact-dir",
                f"artifacts/{SCHEMA}",
            ],
            "verifier_sha256": payload["implementation"]["verifier"]["sha256"],
            "exit_code": 0,
            "report": report,
        },
    }


def _reject_symlink_components(path: Path) -> Path:
    requested = path.expanduser().absolute()
    temp_lexical = Path(tempfile.gettempdir()).expanduser().absolute()
    allowed_platform_aliases: set[tuple[Path, Path]] = set()
    alias_cursor = Path(temp_lexical.anchor)
    for part in temp_lexical.parts[1:]:
        alias_cursor /= part
        if alias_cursor.is_symlink():
            allowed_platform_aliases.add((alias_cursor, alias_cursor.resolve()))
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            if (cursor, cursor.resolve()) not in allowed_platform_aliases:
                raise ValueError("artifact output path uses a symlink") from None
        if not cursor.exists():
            break
    return requested


def _validate_output(root: Path, output: Path) -> Path:
    requested = output.expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested)
    target = requested.resolve(strict=False)
    if target == root or target in root.parents:
        raise ValueError("artifact output must not be the repository root or an ancestor")
    if target.exists():
        if not target.is_dir():
            raise ValueError("artifact output is not replaceable")
        if any(target.iterdir()):
            raise ValueError("artifact output is not replaceable")
    return target


def _install_new(root: Path, target: Path, files: dict[str, bytes], manifest: dict[str, Any], expected_report: dict[str, Any]) -> None:
    _reject_symlink_components(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(target.parent)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        for name, raw in files.items():
            (temporary / name).write_bytes(raw)
        (temporary / "manifest.json").write_bytes(_canonical(manifest))
        completed = subprocess.run(
            [
                sys.executable,
                str(_safe_file(root, IMPLEMENTATION_PATHS["verifier"])),
                "--root",
                str(root),
                "--artifact-dir",
                str(temporary),
            ],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        try:
            report = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise ValueError("independent verifier returned invalid JSON") from error
        if completed.returncode != 0 or report != expected_report:
            raise ValueError(
                "independent verifier rejected candidate artifact: "
                f"exit={completed.returncode}, report={report}, "
                f"stderr={completed.stderr.decode('utf-8', 'replace')}"
            )
        _reject_symlink_components(target)
        if target.exists():
            target.rmdir()
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def export_artifact(root: Path | str, output_dir: Path | str) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    target = _validate_output(root, Path(output_dir))
    payload, bundle = build_payload(root)
    files = {PAYLOAD_NAME: _canonical(payload), BUNDLE_NAME: bundle}
    report = _expected_report(payload)
    _install_new(root, target, files, _promotion_manifest(payload, files, report), report)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    payload = export_artifact(args.root, args.output_dir)
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
