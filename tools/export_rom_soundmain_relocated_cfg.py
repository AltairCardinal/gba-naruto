#!/usr/bin/env python3
"""Build the frozen preflight for the relocated mixed-ISA SoundMain source.

The first stage deliberately proves only the CpuSet copy operation and the
target-limited direct-call denominators.  CFG, literal and alignment claims are
added only after this preflight is locked by tests.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import heapq
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from capstone import CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, Cs


SCHEMA = "rom-soundmain-relocated-cfg-preflight-v1"
ARTIFACT_SCHEMA = "rom-soundmain-relocated-cfg-v1"
VERIFY_SCHEMA = "rom-soundmain-relocated-cfg-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
PAYLOAD_NAME = "rom-soundmain-relocated-cfg.json"
BUNDLE_NAME = "rom-soundmain-relocated-cfg.bin"
MANIFEST_NAME = "manifest.json"
ARTIFACT_RELATIVE = Path("artifacts/rom-soundmain-relocated-cfg-v1")
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 0x600000
BASE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
# Mutation tests patch this public raw-input guard.  Frozen range identities
# remain unchanged and therefore prove fail-closed behavior independently.
ROM_SHA256 = BASE_ROM_SHA256

INITIALIZER_CODE_RANGE = [0x09AA3C, 0x09AA90]
INITIALIZER_LITERAL_RANGE = [0x09AA90, 0x09AAB4]
INITIALIZER_CODE_SHA256 = "c782ff96fc49708def45c12c5ba3c4170449390bf0ea4aa389561e09f359013b"
INITIALIZER_LITERAL_SHA256 = "7f208987daf90cface78da36557a0773839b56b2bf1fe174358f1a56cfebbc6f"
INITIALIZER_OFFSET = 0x09AA3C
INITIALIZER_CALLSITE = 0x09AA4A
INITIALIZER_DIRECT_BL_PRODUCERS = [0x061E28]

CPUFASTSET_OFFSET = 0x09C0DC
CPUSET_OFFSET = 0x09C0E0
CPUSET_WRAPPER_RANGE = [0x09C0E0, 0x09C0E4]
CPUSET_WRAPPER_SHA256 = "07967ebdc3979cd4fd4de37fd22b3e6de8965b00dae4ac5585577c9709839652"

SOURCE_POINTER_LITERAL = 0x09AA90
DESTINATION_LITERAL = 0x09AA94
CONTROL_LITERAL = 0x09AA98
SOURCE_POINTER = 0x08099E11
SOURCE_START = 0x099E10
RUNTIME_START = 0x030077C8
CONTROL = 0x04000100
COPY_RANGE = [0x099E10, 0x09A210]
COPY_SHA256 = "7b4fef2cb8e0e87ce8e8aaf244970f121851095a6d6260a423eda20791d5b238"
SOURCE_ENVELOPE = [0x099E10, 0x09A1AE]
SOURCE_ENVELOPE_SHA256 = "1099dd6414c3f8a052a9e0e19c7ef9497661c4c15b4e8d1dd056f791bb115df8"

COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
COVERAGE_SHA256 = "2b93df18a7815cb966dad707dfa2ad606049911ae1772a341b57cf2347b58e3b"
COVERAGE_SUMMARY = {
    "classified_bytes": 6_122_489,
    "unknown_bytes": 168_967,
    "claim_count": 14_484,
    "segment_count": 16_593,
}

CODE_RANGES = [
    [0x099E10, 0x099E1A],
    [0x099E1C, 0x099EC2],
    [0x099EC8, 0x099FA6],
    [0x099FA8, 0x09A1AE],
]
LITERAL_RANGES = [[0x099EC4, 0x099EC8], [0x09A1B0, 0x09A1B4]]
ALIGNMENT_GAP_RANGES = [
    [0x099E1A, 0x099E1C],
    [0x099EC2, 0x099EC4],
    [0x099FA6, 0x099FA8],
]
OWNED_PROVENANCE_RANGES = [[0x09A1AE, 0x09A1B0]]
OWNED_RETURN_CLAIM_ID = "boot-thumb-handoff-code-22-09a1ae"
OWNED_RETURN_SHA256 = "477db9ac7ca5efc12e37f882656b8fe5a363ffeb99b2e565a953d10c3c91ab21"
SEMANTIC_UNION_RANGES = [
    [0x099E10, 0x099E1A],
    [0x099E1C, 0x099EC2],
    [0x099EC4, 0x099FA6],
    [0x099FA8, 0x09A1AE],
    [0x09A1B0, 0x09A1B4],
]

CODE_PACKED_SHA256 = "e9a33c0d5d90a69fd9c6906523dc48043eb59c31ddf7d47403409dbde18604d2"
CODE_RANGE_VECTOR_SHA256 = "17a5eb6c86a18b7aae3c5537a184d4ee355f244eae5a96b7c5d60ee6f1f5a95f"
LITERAL_PACKED_SHA256 = "73532471c9748faea0e2abc00e4c17dde622220884d2521f4e58cf3fab9be7e0"
LITERAL_RANGE_VECTOR_SHA256 = "ce75959fb7681a95b5a4bbf9371bdaf97d18afa44168107fc33d957c18d6bb71"
GAP_PACKED_SHA256 = "b0f66adc83641586656866813fd9dd0b8ebb63796075661ba45d1aa8089e1d44"
GAP_RANGE_VECTOR_SHA256 = "80e7409ef3fd737361faa6a08ae8e2efbedd9891c31e4f4b98392a3ad91da3af"
INSTRUCTION_VECTOR_SHA256 = "7f18b67eb2b9d93eb09d01c73e31cd89ca639464c888aa5e7b01ecc5d404fc88"
INSTRUCTION_EDGE_VECTOR_SHA256 = "0a14df5c71dac205501ed6daa636cb4d414e5c55acd8c3eb319ab5e9cdf6b6fc"
SEMANTIC_PACKED_SHA256 = "2e94dbb5f876de3420d1317db7ad646991b9778e15a3699659d7786d65de8331"
SEMANTIC_UNION_VECTOR_SHA256 = "edd9da8aad815cf4aea5ca9c02360c3903d523588f0a7a6d7a1fa214e57d8a94"

SEMANTIC_RANGE_ROWS = [
    {
        "id": "soundmain-code-00-099e10",
        "kind": "code",
        "range": [0x099E10, 0x099E1A],
        "size": 10,
        "sha256": "24afedc6cdbff9b7b4321f2e09ef10e899779307190eb09ceeaede96534e68ae",
        "semantic_class": "armv4t_soundmain_relocated_mixed_isa_code",
        "claim_kind": "soundmain_relocated_reachable_instruction_bytes",
        "baseline_unknown_only": True,
    },
    {
        "id": "soundmain-code-01-099e1c",
        "kind": "code",
        "range": [0x099E1C, 0x099EC2],
        "size": 166,
        "sha256": "28ceffde8c9efededde19ed0651c4dd7fd191443f26a1c24ceaadf2361a5f620",
        "semantic_class": "armv4t_soundmain_relocated_mixed_isa_code",
        "claim_kind": "soundmain_relocated_reachable_instruction_bytes",
        "baseline_unknown_only": True,
    },
    {
        "id": "soundmain-literal-00-099ec4",
        "kind": "literal",
        "range": [0x099EC4, 0x099EC8],
        "size": 4,
        "sha256": "2d04e57c5e80a3ae7f289b8ac025839a5b75d659b747ccd7e446f77e711a6663",
        "semantic_class": "soundmain_relocated_consumed_literal_bytes",
        "claim_kind": "soundmain_relocated_consumed_literal_bytes",
        "baseline_unknown_only": True,
    },
    {
        "id": "soundmain-code-02-099ec8",
        "kind": "code",
        "range": [0x099EC8, 0x099FA6],
        "size": 222,
        "sha256": "c804dcedcd92c3a0ec788ecb255aa1637ecdc838b9f1029c08ccb5cfb9fdea5e",
        "semantic_class": "armv4t_soundmain_relocated_mixed_isa_code",
        "claim_kind": "soundmain_relocated_reachable_instruction_bytes",
        "baseline_unknown_only": True,
    },
    {
        "id": "soundmain-code-03-099fa8",
        "kind": "code",
        "range": [0x099FA8, 0x09A1AE],
        "size": 518,
        "sha256": "34a9c442a64856a9eb8636a5d249a146260af74fe828dbbd338fe263eea90427",
        "semantic_class": "armv4t_soundmain_relocated_mixed_isa_code",
        "claim_kind": "soundmain_relocated_reachable_instruction_bytes",
        "baseline_unknown_only": True,
    },
    {
        "id": "soundmain-literal-01-09a1b0",
        "kind": "literal",
        "range": [0x09A1B0, 0x09A1B4],
        "size": 4,
        "sha256": "ee88b5a804fd87fa74b205951cfcc811ef5cdb452c4ad7f7cd1456fc90d71b90",
        "semantic_class": "soundmain_relocated_consumed_literal_bytes",
        "claim_kind": "soundmain_relocated_consumed_literal_bytes",
        "baseline_unknown_only": True,
    },
]

LIMITATIONS = [
    "This artifact classifies exactly 916 bounded relocated ARMv4T instruction bytes and 8 directly consumed literal bytes; the three two-byte alignment gaps remain unknown until this artifact has an accepted immutable verification receipt.",
    "The frozen CpuSet consumer and target-limited raw direct-producer scans bind the copied source, but computed or indirect producers and dynamic IWRAM state are not exhaustively resolved.",
    "The mixed Thumb/ARM CFG proves only the bounded relocated source closure and its opaque fallthrough into the already-owned return veneer; natural runtime reachability and broader audio semantics remain unproven.",
    "Editing, relocation, writeback, and allocatable free-space safety are outside scope.",
]

MODE_SWITCHES = [
    {
        "precursor_offset": 0x099E16,
        "producer_offset": 0x099E18,
        "producer_mode": "thumb",
        "register": "r1",
        "register_value": "0x030077D4",
        "target_runtime_address": "0x030077D4",
        "target_offset": 0x099E1C,
        "target_mode": "arm",
        "raw_hex": "01a10847",
    },
    {
        "precursor_offset": 0x099E68,
        "producer_offset": 0x099E6C,
        "producer_mode": "arm",
        "register": "r0",
        "register_value": "0x03007857",
        "target_runtime_address": "0x03007856",
        "target_offset": 0x099E9E,
        "target_mode": "thumb",
        "raw_hex": "2f008fe210ff2fe1",
    },
    {
        "precursor_offset": 0x099FA2,
        "producer_offset": 0x099FA4,
        "producer_mode": "thumb",
        "register": "r0",
        "register_value": "0x03007960",
        "target_runtime_address": "0x03007960",
        "target_offset": 0x099FA8,
        "target_mode": "arm",
        "raw_hex": "01a00047",
    },
    {
        "precursor_offset": 0x09A188,
        "producer_offset": 0x09A18C,
        "producer_mode": "arm",
        "register": "r0",
        "register_value": "0x03007B49",
        "target_runtime_address": "0x03007B48",
        "target_offset": 0x09A190,
        "target_mode": "thumb",
        "raw_hex": "01008fe210ff2fe1",
    },
]
EXPECTED_LITERAL_BINDINGS = [
    (0x099EB2, "thumb", 0x099EC4, 0x04000006),
    (0x09A19C, "thumb", 0x09A1B0, 0x68736D53),
]
EXPECTED_SUMMARY = {
    "instruction_count": 315,
    "instruction_bytes": 916,
    "thumb_instruction_count": 172,
    "thumb_instruction_bytes": 344,
    "arm_instruction_count": 143,
    "arm_instruction_bytes": 572,
    "code_bytes": 916,
    "block_count": 73,
    "internal_block_edge_count": 112,
    "external_block_edge_count": 1,
    "mode_switch_count": 4,
    "literal_ref_count": 2,
    "literal_word_count": 2,
    "literal_bytes": 8,
    "alignment_gap_count": 3,
    "alignment_gap_bytes": 6,
    "owned_return_veneer_count": 1,
    "owned_provenance_bytes": 2,
    "internal_return_count": 0,
    "opaque_return_count": 1,
    "unresolved_frontier_count": 0,
}

_ENGINES: dict[str, Cs] = {}

DIRECT_CPUSET_MANIFEST = Path("artifacts/rom-direct-cpuset-gpu-inventory-v1/manifest.json")
DIRECT_CPUSET_PAYLOAD = Path(
    "artifacts/rom-direct-cpuset-gpu-inventory-v1/rom-direct-cpuset-gpu-inventory.json"
)
DIRECT_CPUSET_VERIFIER = Path("tools/verify_rom_direct_cpuset_gpu_inventory.py")
DIRECT_CPUSET_MANIFEST_SHA256 = "ed886e717b54b0ec78af5eb4941d677095286290a5ad2ed2a01b033f4520d246"
DIRECT_CPUSET_PAYLOAD_SHA256 = "724f47ddced0ff9271d74c81395df6d0939b86642e1c40ffe1d9951fd49891e3"
DIRECT_CPUSET_VERIFIER_SHA256 = "4e8f394803873a96db2dfb2d7b5b7ec6750a2ead33cdc1bb8e08676c203f678b"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _compact_canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _bounded(rom: bytes, start: int, end: int) -> bytes:
    if start < 0 or end < start or end > len(rom):
        raise ValueError(f"ROM range outside image: 0x{start:06X}..0x{end:06X}")
    return rom[start:end]


def _u16(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 2), "little")


def _u32(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 4), "little")


def _sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _thumb_bl_target(rom: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 4 > len(rom) or offset % 2:
        return None
    first = _u16(rom, offset)
    second = _u16(rom, offset + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    encoded = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
    return offset + 4 + _sign_extend(encoded, 23)


def _direct_bl_callsites(rom: bytes, target: int) -> list[int]:
    return [
        offset
        for offset in range(0, len(rom) - 3, 2)
        if _thumb_bl_target(rom, offset) == target
    ]


def _thumb_branch_target(rom: bytes, offset: int) -> tuple[str, int] | None:
    if offset < 0 or offset + 2 > len(rom) or offset % 2:
        return None
    halfword = _u16(rom, offset)
    condition = (halfword >> 8) & 0xF
    if halfword & 0xF000 == 0xD000 and condition <= 0xD:
        target = offset + 4 + _sign_extend((halfword & 0xFF) << 1, 9)
        return "thumb_b_conditional", target
    if halfword & 0xF800 == 0xE000:
        target = offset + 4 + _sign_extend((halfword & 0x07FF) << 1, 12)
        return "thumb_b", target
    return None


def _arm_branch_target(rom: bytes, offset: int) -> tuple[str, int] | None:
    if offset < 0 or offset + 4 > len(rom) or offset % 4:
        return None
    word = _u32(rom, offset)
    if word & 0x0E000000 != 0x0A000000:
        return None
    target = offset + 8 + _sign_extend((word & 0x00FFFFFF) << 2, 26)
    return ("arm_bl" if word & (1 << 24) else "arm_b"), target


def _pointer_occurrences(rom: bytes, value: int) -> list[int]:
    needle = struct.pack("<I", value)
    found: list[int] = []
    cursor = 0
    while True:
        cursor = rom.find(needle, cursor)
        if cursor < 0:
            return found
        found.append(cursor)
        cursor += 1


def _target_producer_forms(rom: bytes, target: int) -> dict[str, list[int]]:
    forms = {
        "thumb_bl": _direct_bl_callsites(rom, target),
        "thumb_b": [],
        "thumb_b_conditional": [],
        "arm_b": [],
        "arm_bl": [],
        "bytewise_u32_entry": _pointer_occurrences(rom, ROM_BASE + target),
        "bytewise_u32_thumb_pointer": _pointer_occurrences(rom, ROM_BASE + target + 1),
    }
    for offset in range(0, len(rom) - 1, 2):
        decoded = _thumb_branch_target(rom, offset)
        if decoded is not None and decoded[1] == target:
            forms[decoded[0]].append(offset)
    for offset in range(0, len(rom) - 3, 4):
        decoded = _arm_branch_target(rom, offset)
        if decoded is not None and decoded[1] == target:
            forms[decoded[0]].append(offset)
    return forms


def _validate_root(root: Path | str) -> Path:
    value = Path(root).resolve()
    if not value.is_dir():
        raise ValueError(f"repository root is not a directory: {value}")
    return value


def _safe_file(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository path: {relative}")
    candidate = root / relative
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository path uses a symlink: {cursor}")
    if not candidate.is_file():
        raise ValueError(f"required file missing: {relative}")
    return candidate


def _read_hash_bound(root: Path, relative: Path, expected_sha256: str) -> bytes:
    raw = _safe_file(root, relative).read_bytes()
    if _sha(raw) != expected_sha256:
        raise ValueError(f"upstream identity changed: {relative}")
    return raw


def _validate_rom(rom: bytes) -> None:
    if len(rom) != ROM_SIZE:
        raise ValueError(f"ROM size changed: {len(rom)}")
    if _sha(rom) != ROM_SHA256:
        raise ValueError("ROM SHA-256 changed")


def _copy_operation(rom: bytes) -> dict[str, Any]:
    if _u32(rom, SOURCE_POINTER_LITERAL) != SOURCE_POINTER:
        raise ValueError("SoundMain source literal changed")
    if _u32(rom, DESTINATION_LITERAL) != RUNTIME_START:
        raise ValueError("SoundMain destination literal changed")
    if _u32(rom, CONTROL_LITERAL) != CONTROL:
        raise ValueError("SoundMain control literal changed")
    if _thumb_bl_target(rom, INITIALIZER_CALLSITE) != CPUSET_OFFSET:
        raise ValueError("CpuSet callsite changed")
    if _sha(_bounded(rom, *CPUSET_WRAPPER_RANGE)) != CPUSET_WRAPPER_SHA256:
        raise ValueError("CpuSet wrapper changed")
    if _sha(_bounded(rom, *INITIALIZER_CODE_RANGE)) != INITIALIZER_CODE_SHA256:
        raise ValueError("m4aSoundInit code window changed")
    if _sha(_bounded(rom, *INITIALIZER_LITERAL_RANGE)) != INITIALIZER_LITERAL_SHA256:
        raise ValueError("m4aSoundInit literal pool changed")

    unit_bytes = 4 if CONTROL & (1 << 26) else 2
    unit_count = CONTROL & 0x001FFFFF
    fixed_source = bool(CONTROL & (1 << 24))
    copy_bytes = unit_bytes * unit_count
    source_start = (SOURCE_POINTER & ~1) - ROM_BASE
    source_range = [source_start, source_start + copy_bytes]
    destination_range = [RUNTIME_START, RUNTIME_START + copy_bytes]
    if source_range != COPY_RANGE or fixed_source or copy_bytes != 0x400:
        raise ValueError("SoundMain CpuSet copy contract changed")
    if _sha(_bounded(rom, *source_range)) != COPY_SHA256:
        raise ValueError("SoundMain CpuSet copy window changed")

    return {
        "initializer_code_range": INITIALIZER_CODE_RANGE,
        "initializer_code_sha256": INITIALIZER_CODE_SHA256,
        "initializer_literal_range": INITIALIZER_LITERAL_RANGE,
        "initializer_literal_sha256": INITIALIZER_LITERAL_SHA256,
        "source_pointer": f"0x{SOURCE_POINTER:08X}",
        "source_pointer_literal_offset": SOURCE_POINTER_LITERAL,
        "source_range": source_range,
        "destination_literal_offset": DESTINATION_LITERAL,
        "destination_range": destination_range,
        "control_literal_offset": CONTROL_LITERAL,
        "control": f"0x{CONTROL:08X}",
        "unit_bytes": unit_bytes,
        "unit_count": unit_count,
        "copy_bytes": copy_bytes,
        "fixed_source": fixed_source,
        "callsite_offset": INITIALIZER_CALLSITE,
        "callsite_gba_address": f"0x{ROM_BASE + INITIALIZER_CALLSITE:08X}",
        "bios_wrapper_range": CPUSET_WRAPPER_RANGE,
        "bios_wrapper_sha256": CPUSET_WRAPPER_SHA256,
        "bios_swi": "0x0B",
        "copy_window_sha256": COPY_SHA256,
    }


def _producer_denominator(root: Path, rom: bytes) -> dict[str, Any]:
    manifest_raw = _read_hash_bound(
        root, DIRECT_CPUSET_MANIFEST, DIRECT_CPUSET_MANIFEST_SHA256
    )
    payload_raw = _read_hash_bound(
        root, DIRECT_CPUSET_PAYLOAD, DIRECT_CPUSET_PAYLOAD_SHA256
    )
    _read_hash_bound(root, DIRECT_CPUSET_VERIFIER, DIRECT_CPUSET_VERIFIER_SHA256)
    manifest = json.loads(manifest_raw.decode("utf-8"))
    payload = json.loads(payload_raw.decode("utf-8"))
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("direct CpuSet upstream artifact is not accepted")

    cpuset_forms = _target_producer_forms(rom, CPUSET_OFFSET)
    cpuset = cpuset_forms["thumb_bl"]
    cpufastset = _direct_bl_callsites(rom, CPUFASTSET_OFFSET)
    direct = sorted(
        [(offset, "CpuSet") for offset in cpuset]
        + [(offset, "CpuFastSet") for offset in cpufastset]
    )
    upstream = sorted(
        (
            int(item["callsite"], 16) - ROM_BASE,
            item["loader"],
        )
        for item in payload.get("direct_calls", [])
    )
    if cpuset != sorted(cpuset) or len(cpuset) != 126 or INITIALIZER_CALLSITE not in cpuset:
        raise ValueError("direct CpuSet denominator changed")
    if len(cpufastset) != 20:
        raise ValueError("direct CpuFastSet denominator changed")
    if direct != upstream or len(direct) != 146:
        raise ValueError("direct CpuSet artifact denominator changed")

    initializer_forms = _target_producer_forms(rom, INITIALIZER_OFFSET)
    initializer = initializer_forms["thumb_bl"]
    empty_forms = (
        "thumb_b",
        "thumb_b_conditional",
        "arm_b",
        "arm_bl",
        "bytewise_u32_entry",
        "bytewise_u32_thumb_pointer",
    )
    if initializer != INITIALIZER_DIRECT_BL_PRODUCERS or any(
        initializer_forms[kind] for kind in empty_forms
    ):
        raise ValueError("m4aSoundInit direct-BL producer denominator changed")
    if any(cpuset_forms[kind] for kind in empty_forms):
        raise ValueError("direct CpuSet non-BL producer denominator changed")

    vector = [
        {"callsite_offset": offset, "loader": loader}
        for offset, loader in direct
    ]
    return {
        "cpuset_target": f"0x{ROM_BASE + CPUSET_OFFSET:08X}",
        "cpuset_callsites": cpuset,
        "cpuset_call_count": len(cpuset),
        "cpufastset_target": f"0x{ROM_BASE + CPUFASTSET_OFFSET:08X}",
        "cpufastset_callsites": cpufastset,
        "cpufastset_call_count": len(cpufastset),
        "direct_call_count": len(direct),
        "direct_call_vector_sha256": _sha(_canonical(vector)),
        "soundmain_copy_callsites": [INITIALIZER_CALLSITE],
        "initializer_target": f"0x{ROM_BASE + INITIALIZER_OFFSET:08X}",
        "initializer_direct_bl_producers": initializer,
        "initializer_forms": initializer_forms,
        "cpuset_forms": cpuset_forms,
        "matches_direct_cpuset_artifact": True,
        "target_limited_direct_bl_denominator_complete": True,
        "target_limited_raw_producer_denominator_complete": True,
        "computed_or_indirect_producer_denominator_complete": False,
        "upstream": {
            "manifest_path": DIRECT_CPUSET_MANIFEST.as_posix(),
            "manifest_sha256": DIRECT_CPUSET_MANIFEST_SHA256,
            "payload_path": DIRECT_CPUSET_PAYLOAD.as_posix(),
            "payload_sha256": DIRECT_CPUSET_PAYLOAD_SHA256,
            "verifier_path": DIRECT_CPUSET_VERIFIER.as_posix(),
            "verifier_sha256": DIRECT_CPUSET_VERIFIER_SHA256,
        },
    }


def _engine(mode: str) -> Cs:
    if mode not in _ENGINES:
        capstone_mode = CS_MODE_THUMB if mode == "thumb" else CS_MODE_ARM
        engine = Cs(CS_ARCH_ARM, capstone_mode)
        engine.detail = True
        _ENGINES[mode] = engine
    return _ENGINES[mode]


def _runtime_address(offset: int) -> int:
    return RUNTIME_START + (offset - SOURCE_START)


def _source_offset(runtime_address: int) -> int:
    return SOURCE_START + (runtime_address - RUNTIME_START)


def _ranges_from_intervals(intervals: list[tuple[int, int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for start, end in sorted(set(intervals)):
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def _validate_relocated_boundaries(rom: bytes) -> None:
    for switch in MODE_SWITCHES:
        start = switch["precursor_offset"]
        producer_size = 2 if switch["producer_mode"] == "thumb" else 4
        end = switch["producer_offset"] + producer_size
        if _bounded(rom, start, end).hex() != switch["raw_hex"]:
            raise ValueError("mode-switch producer changed")
    for start, end in ALIGNMENT_GAP_RANGES:
        if _bounded(rom, start, end) != b"\x00\x00":
            raise ValueError("alignment gap changed")
    if _sha(_bounded(rom, *OWNED_PROVENANCE_RANGES[0])) != OWNED_RETURN_SHA256:
        raise ValueError("preowned SoundMain return veneer changed")


def _mixed_flow(
    rom: bytes, offset: int, mode: str, size: int
) -> tuple[str, bool, list[tuple[str, int, str]], list[str]]:
    switch = next(
        (
            item
            for item in MODE_SWITCHES
            if item["producer_offset"] == offset and item["producer_mode"] == mode
        ),
        None,
    )
    if switch is not None:
        return (
            "mode_switch",
            False,
            [("branch_target", switch["target_offset"], switch["target_mode"])],
            [],
        )

    end = offset + size
    if mode == "thumb":
        halfword = _u16(rom, offset)
        branch = _thumb_branch_target(rom, offset)
        if branch is not None:
            kind, target = branch
            if kind == "thumb_b_conditional":
                return (
                    "conditional_branch",
                    True,
                    [("branch_target", target, mode), ("fallthrough", end, mode)],
                    [],
                )
            return (
                "unconditional_branch",
                False,
                [("branch_target", target, mode)],
                [],
            )
        if halfword & 0xFF87 == 0x4700:
            register = (halfword >> 3) & 0xF
            if register == 14:
                return "return", False, [], []
            return "indirect_branch", False, [], [f"unresolved_bx_r{register}"]
        if halfword & 0xFF00 == 0xBD00:
            return "return", False, [], []
        return "linear", False, [("fallthrough", end, mode)], []

    word = _u32(rom, offset)
    branch = _arm_branch_target(rom, offset)
    if branch is not None:
        kind, target = branch
        condition = (word >> 28) & 0xF
        if kind == "arm_bl":
            successors = [("call_target", target, mode)]
            if condition != 0xE:
                successors.append(("fallthrough", end, mode))
            else:
                # ARM BL returns to the following instruction.
                successors.append(("fallthrough", end, mode))
            return "call", condition != 0xE, successors, []
        if condition == 0xE:
            return (
                "unconditional_branch",
                False,
                [("branch_target", target, mode)],
                [],
            )
        return (
            "conditional_branch",
            True,
            [("branch_target", target, mode), ("fallthrough", end, mode)],
            [],
        )
    if word & 0x0FFFFFF0 == 0x012FFF10:
        register = word & 0xF
        if register == 14:
            return "return", False, [], []
        return "indirect_branch", False, [], [f"unresolved_bx_r{register}"]
    return "linear", False, [("fallthrough", end, mode)], []


def _decode_relocated(rom: bytes, offset: int, mode: str) -> dict[str, Any]:
    if offset < SOURCE_ENVELOPE[0] or offset >= SOURCE_ENVELOPE[1]:
        raise ValueError(f"relocated decode outside source envelope: 0x{offset:06X}")
    alignment = 2 if mode == "thumb" else 4
    if _runtime_address(offset) % alignment:
        raise ValueError(f"misaligned relocated {mode} decode: 0x{offset:06X}")
    runtime_address = _runtime_address(offset)
    decoded = tuple(
        _engine(mode).disasm(rom[offset : offset + 4], runtime_address, count=1)
    )
    if len(decoded) != 1 or decoded[0].address != runtime_address:
        raise ValueError(f"relocated {mode} decode failed: 0x{offset:06X}")
    instruction = decoded[0]
    if instruction.size not in (2, 4):
        raise ValueError(f"relocated instruction size changed: 0x{offset:06X}")
    raw = _bounded(rom, offset, offset + instruction.size)
    flow_kind, conditional, successors, frontiers = _mixed_flow(
        rom, offset, mode, instruction.size
    )
    order = {"branch_target": 0, "call_target": 1, "fallthrough": 2}
    successors.sort(key=lambda item: (order[item[0]], item[1], item[2]))
    return {
        "source_offset": offset,
        "gba_address": f"0x{ROM_BASE + offset:08X}",
        "runtime_address": f"0x{runtime_address:08X}",
        "mode": mode,
        "size": instruction.size,
        "raw_hex": raw.hex(),
        "bytes_sha256": _sha(raw),
        "mnemonic": instruction.mnemonic,
        "op_str": instruction.op_str,
        "flow_kind": flow_kind,
        "conditional": conditional,
        "successors": [
            {"kind": kind, "target_offset": target, "target_mode": target_mode}
            for kind, target, target_mode in successors
        ],
        "frontiers": frontiers,
    }


def _walk_relocated_cfg(
    rom: bytes,
) -> tuple[dict[tuple[int, str], dict[str, Any]], list[dict[str, Any]]]:
    root_key = (SOURCE_START, "thumb")
    pending = [root_key]
    scheduled = {root_key}
    nodes: dict[tuple[int, str], dict[str, Any]] = {}
    external: list[dict[str, Any]] = []
    while pending:
        offset, mode = heapq.heappop(pending)
        node = _decode_relocated(rom, offset, mode)
        nodes[(offset, mode)] = node
        for successor in node["successors"]:
            target = successor["target_offset"]
            target_mode = successor["target_mode"]
            key = (target, target_mode)
            if key == (OWNED_PROVENANCE_RANGES[0][0], "thumb"):
                external.append({
                    "source_instruction_offset": offset,
                    "source_mode": mode,
                    "kind": successor["kind"],
                    "target_offset": target,
                    "target_mode": target_mode,
                    "resolution": "opaque_existing_soundmain_return_veneer",
                    "owner_claim_id": OWNED_RETURN_CLAIM_ID,
                })
                continue
            if not SOURCE_ENVELOPE[0] <= target < SOURCE_ENVELOPE[1]:
                raise ValueError(
                    f"relocated CFG escaped source envelope from 0x{offset:06X} "
                    f"to 0x{target:06X}"
                )
            if key not in scheduled:
                scheduled.add(key)
                heapq.heappush(pending, key)

    byte_owner: dict[int, tuple[int, str]] = {}
    for key, node in nodes.items():
        for byte_offset in range(key[0], key[0] + node["size"]):
            if byte_offset in byte_owner:
                raise ValueError("relocated mixed-ISA instruction overlap changed")
            byte_owner[byte_offset] = key
    code_ranges = _ranges_from_intervals(
        [(offset, offset + node["size"]) for (offset, _), node in nodes.items()]
    )
    if code_ranges != CODE_RANGES:
        raise ValueError("relocated code range denominator changed")
    if external != [{
        "source_instruction_offset": 0x09A1AC,
        "source_mode": "thumb",
        "kind": "fallthrough",
        "target_offset": 0x09A1AE,
        "target_mode": "thumb",
        "resolution": "opaque_existing_soundmain_return_veneer",
        "owner_claim_id": OWNED_RETURN_CLAIM_ID,
    }]:
        raise ValueError("preowned SoundMain return edge changed")
    return nodes, external


def _build_mixed_blocks(
    rom: bytes,
    nodes: dict[tuple[int, str], dict[str, Any]],
    external: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    predecessors: dict[tuple[int, str], list[tuple[tuple[int, str], str]]] = {
        key: [] for key in nodes
    }
    for source, node in nodes.items():
        for successor in node["successors"]:
            target = (successor["target_offset"], successor["target_mode"])
            if target in nodes:
                predecessors[target].append((source, successor["kind"]))

    root_key = (SOURCE_START, "thumb")
    starts = {root_key}
    for key, incoming in predecessors.items():
        if key == root_key:
            continue
        if len(incoming) != 1:
            starts.add(key)
            continue
        source, _ = incoming[0]
        predecessor = nodes[source]
        if (
            len(predecessor["successors"]) != 1
            or predecessor["flow_kind"] != "linear"
            or source[1] != key[1]
            or source[0] + predecessor["size"] != key[0]
        ):
            starts.add(key)

    blocks: list[dict[str, Any]] = []
    block_by_node: dict[tuple[int, str], str] = {}
    for start in sorted(starts):
        members: list[tuple[int, str]] = []
        key = start
        while key in nodes and key not in block_by_node:
            members.append(key)
            block_id = f"block-{start[1]}-{start[0]:06x}"
            block_by_node[key] = block_id
            node = nodes[key]
            if len(node["successors"]) != 1 or node["flow_kind"] != "linear":
                break
            successor = node["successors"][0]
            target = (successor["target_offset"], successor["target_mode"])
            if (
                target in starts
                or target[1] != key[1]
                or target[0] != key[0] + node["size"]
            ):
                break
            key = target
        if not members:
            continue
        last_key = members[-1]
        last = nodes[last_key]
        end = last_key[0] + last["size"]
        blocks.append({
            "id": block_by_node[start],
            "mode": start[1],
            "range": [start[0], end],
            "runtime_range": [_runtime_address(start[0]), _runtime_address(end)],
            "instruction_count": len(members),
            "bytes_sha256": _sha(_bounded(rom, start[0], end)),
            "terminator": {
                "source_offset": last_key[0],
                "mode": last_key[1],
                "mnemonic": last["mnemonic"],
                "op_str": last["op_str"],
                "flow_kind": last["flow_kind"],
                "conditional": last["conditional"],
            },
            "successors": [],
        })
    if len(block_by_node) != len(nodes):
        raise ValueError("relocated block partition omitted instructions")

    external_by_source = {
        (item["source_instruction_offset"], item["source_mode"]): item
        for item in external
    }
    edges: list[dict[str, Any]] = []
    for block in blocks:
        source_key = (
            block["terminator"]["source_offset"],
            block["terminator"]["mode"],
        )
        for successor in nodes[source_key]["successors"]:
            target_key = (successor["target_offset"], successor["target_mode"])
            if target_key in nodes:
                edge = {
                    "source_block_id": block["id"],
                    "source_instruction_offset": source_key[0],
                    "source_mode": source_key[1],
                    "kind": successor["kind"],
                    "target_offset": target_key[0],
                    "target_mode": target_key[1],
                    "target_block_id": block_by_node[target_key],
                    "resolution": "internal",
                }
            else:
                ext = external_by_source.get(source_key)
                if (
                    ext is None
                    or ext["kind"] != successor["kind"]
                    or ext["target_offset"] != successor["target_offset"]
                    or ext["target_mode"] != successor["target_mode"]
                ):
                    raise ValueError("relocated external block edge binding changed")
                edge = {**ext, "source_block_id": block["id"]}
            block["successors"].append(edge)
            edges.append(edge)
    internal_count = sum(edge["resolution"] == "internal" for edge in edges)
    if (
        len(blocks) != EXPECTED_SUMMARY["block_count"]
        or internal_count != EXPECTED_SUMMARY["internal_block_edge_count"]
        or len(edges) - internal_count != EXPECTED_SUMMARY["external_block_edge_count"]
    ):
        raise ValueError("relocated block or edge denominator changed")
    return blocks, edges


def _relocated_literal_bindings(
    rom: bytes, nodes: dict[tuple[int, str], dict[str, Any]]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for (offset, mode), node in sorted(nodes.items()):
        literal_runtime: int | None = None
        if mode == "thumb" and node["size"] == 2:
            halfword = _u16(rom, offset)
            if halfword & 0xF800 == 0x4800:
                literal_runtime = (
                    (_runtime_address(offset) + 4) & ~3
                ) + (halfword & 0xFF) * 4
        elif mode == "arm":
            word = _u32(rom, offset)
            if (
                word & 0x0C100000 == 0x04100000
                and (word >> 16) & 0xF == 15
                and word & (1 << 24)
            ):
                displacement = word & 0xFFF
                literal_runtime = _runtime_address(offset) + 8 + (
                    displacement if word & (1 << 23) else -displacement
                )
        if literal_runtime is None:
            continue
        literal_offset = _source_offset(literal_runtime)
        value = _u32(rom, literal_offset)
        records.append({
            "instruction_offset": offset,
            "instruction_mode": mode,
            "instruction_runtime_address": f"0x{_runtime_address(offset):08X}",
            "literal_offset": literal_offset,
            "literal_runtime_address": f"0x{literal_runtime:08X}",
            "value": f"0x{value:08X}",
            "raw_hex": _bounded(rom, literal_offset, literal_offset + 4).hex(),
        })
    actual = [
        (
            item["instruction_offset"],
            item["instruction_mode"],
            item["literal_offset"],
            int(item["value"], 16),
        )
        for item in records
    ]
    if actual != EXPECTED_LITERAL_BINDINGS:
        raise ValueError("literal binding changed")
    return records


def analyze_relocated_cfg(rom: bytes) -> dict[str, Any]:
    """Decode SoundMain at its IWRAM runtime addresses and close the raw CFG."""

    _validate_relocated_boundaries(rom)
    nodes, external = _walk_relocated_cfg(rom)
    literal_bindings = _relocated_literal_bindings(rom, nodes)
    blocks, block_edges = _build_mixed_blocks(rom, nodes, external)

    instruction_vector = [
        {
            "offset": offset,
            "mode": mode,
            "size": node["size"],
            "raw": node["raw_hex"],
            "flow": node["flow_kind"],
        }
        for (offset, mode), node in sorted(nodes.items())
    ]
    instruction_vector_sha = _sha(_compact_canonical(instruction_vector))
    if instruction_vector_sha != INSTRUCTION_VECTOR_SHA256:
        raise ValueError("relocated instruction denominator changed")

    internal_instruction_edges: list[
        tuple[tuple[int, str], str, tuple[int, str]]
    ] = []
    for source, node in nodes.items():
        for successor in node["successors"]:
            target = (successor["target_offset"], successor["target_mode"])
            if target in nodes:
                internal_instruction_edges.append((source, successor["kind"], target))
    edge_vector = [
        {
            "source_offset": source[0],
            "source_mode": source[1],
            "kind": kind,
            "target_offset": target[0],
            "target_mode": target[1],
        }
        for source, kind, target in sorted(internal_instruction_edges)
    ]
    instruction_edge_sha = _sha(_compact_canonical(edge_vector))
    if instruction_edge_sha != INSTRUCTION_EDGE_VECTOR_SHA256:
        raise ValueError("relocated instruction edge denominator changed")

    code_packed = b"".join(_bounded(rom, start, end) for start, end in CODE_RANGES)
    literal_packed = b"".join(
        _bounded(rom, start, end) for start, end in LITERAL_RANGES
    )
    gap_packed = b"".join(
        _bounded(rom, start, end) for start, end in ALIGNMENT_GAP_RANGES
    )
    identities = {
        "code_packed_sha256": _sha(code_packed),
        "code_range_vector_sha256": _sha(_compact_canonical(CODE_RANGES)),
        "literal_packed_sha256": _sha(literal_packed),
        "literal_range_vector_sha256": _sha(_compact_canonical(LITERAL_RANGES)),
        "gap_packed_sha256": _sha(gap_packed),
        "gap_range_vector_sha256": _sha(_compact_canonical(ALIGNMENT_GAP_RANGES)),
        "instruction_vector_sha256": instruction_vector_sha,
        "instruction_edge_vector_sha256": instruction_edge_sha,
    }
    expected_identities = {
        "code_packed_sha256": CODE_PACKED_SHA256,
        "code_range_vector_sha256": CODE_RANGE_VECTOR_SHA256,
        "literal_packed_sha256": LITERAL_PACKED_SHA256,
        "literal_range_vector_sha256": LITERAL_RANGE_VECTOR_SHA256,
        "gap_packed_sha256": GAP_PACKED_SHA256,
        "gap_range_vector_sha256": GAP_RANGE_VECTOR_SHA256,
        "instruction_vector_sha256": INSTRUCTION_VECTOR_SHA256,
        "instruction_edge_vector_sha256": INSTRUCTION_EDGE_VECTOR_SHA256,
    }
    if identities != expected_identities:
        raise ValueError("relocated code/literal/gap identity changed")

    thumb_nodes = [node for (_, mode), node in nodes.items() if mode == "thumb"]
    arm_nodes = [node for (_, mode), node in nodes.items() if mode == "arm"]
    internal_block_edges = sum(
        edge["resolution"] == "internal" for edge in block_edges
    )
    summary = {
        "instruction_count": len(nodes),
        "instruction_bytes": sum(node["size"] for node in nodes.values()),
        "thumb_instruction_count": len(thumb_nodes),
        "thumb_instruction_bytes": sum(node["size"] for node in thumb_nodes),
        "arm_instruction_count": len(arm_nodes),
        "arm_instruction_bytes": sum(node["size"] for node in arm_nodes),
        "code_bytes": len(code_packed),
        "block_count": len(blocks),
        "internal_block_edge_count": internal_block_edges,
        "external_block_edge_count": len(block_edges) - internal_block_edges,
        "mode_switch_count": len(MODE_SWITCHES),
        "literal_ref_count": len(literal_bindings),
        "literal_word_count": len({item["literal_offset"] for item in literal_bindings}),
        "literal_bytes": len(literal_packed),
        "alignment_gap_count": len(ALIGNMENT_GAP_RANGES),
        "alignment_gap_bytes": len(gap_packed),
        "owned_return_veneer_count": 1,
        "owned_provenance_bytes": OWNED_PROVENANCE_RANGES[0][1]
        - OWNED_PROVENANCE_RANGES[0][0],
        "internal_return_count": sum(
            node["flow_kind"] == "return" for node in nodes.values()
        ),
        "opaque_return_count": 1,
        "unresolved_frontier_count": sum(
            len(node["frontiers"]) for node in nodes.values()
        ),
    }
    if summary != EXPECTED_SUMMARY:
        raise ValueError("relocated CFG summary changed")

    return {
        "root": {
            "source_offset": SOURCE_START,
            "gba_address": f"0x{ROM_BASE + SOURCE_START:08X}",
            "runtime_address": f"0x{RUNTIME_START:08X}",
            "mode": "thumb",
        },
        "runtime_mapping": {
            "source_range": SOURCE_ENVELOPE,
            "runtime_range": [
                RUNTIME_START,
                RUNTIME_START + SOURCE_ENVELOPE[1] - SOURCE_ENVELOPE[0],
            ],
            "formula": "runtime=0x030077C8+(source_offset-0x099E10)",
        },
        "code_ranges": CODE_RANGES,
        "literal_ranges": LITERAL_RANGES,
        "alignment_gap_ranges": ALIGNMENT_GAP_RANGES,
        "owned_provenance_ranges": OWNED_PROVENANCE_RANGES,
        "mode_switches": MODE_SWITCHES,
        "literal_bindings": literal_bindings,
        "instructions": [node for _, node in sorted(nodes.items())],
        "blocks": blocks,
        "block_edges": block_edges,
        "external_edges": external,
        "identities": identities,
        "summary": summary,
    }


def _coverage_baseline(root: Path) -> dict[str, Any]:
    raw = _safe_file(root, COVERAGE_PATH).read_bytes()
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline SHA-256 changed")
    coverage = json.loads(raw.decode("utf-8"))
    summary = coverage.get("summary", {})
    actual_summary = {key: summary.get(key) for key in COVERAGE_SUMMARY}
    if actual_summary != COVERAGE_SUMMARY:
        raise ValueError("coverage baseline summary changed")
    by_range = {
        tuple(segment.get("range", [])): segment
        for segment in coverage.get("segments", [])
    }
    source = by_range.get(tuple(SOURCE_ENVELOPE))
    owner = by_range.get(tuple(OWNED_PROVENANCE_RANGES[0]))
    external_literal = by_range.get(tuple(LITERAL_RANGES[1]))
    if source is None or source.get("primary_class") != "unknown":
        raise ValueError("SoundMain source envelope is not current unknown")
    if (
        owner is None
        or owner.get("primary_claim_ids") != [OWNED_RETURN_CLAIM_ID]
    ):
        raise ValueError("preowned SoundMain return owner changed")
    if external_literal is None or external_literal.get("primary_class") != "unknown":
        raise ValueError("external SoundMain literal is not current unknown")
    return {
        "path": COVERAGE_PATH.as_posix(),
        "schema": coverage.get("schema"),
        "sha256": COVERAGE_SHA256,
        "summary": COVERAGE_SUMMARY,
        "target_segments": [
            {"range": SOURCE_ENVELOPE, "primary_class": "unknown"},
            {
                "range": OWNED_PROVENANCE_RANGES[0],
                "claim_id": OWNED_RETURN_CLAIM_ID,
            },
            {"range": LITERAL_RANGES[1], "primary_class": "unknown"},
        ],
    }


def _semantic_promotion(rom: bytes) -> dict[str, Any]:
    packed = b"".join(
        _bounded(rom, start, end) for start, end in SEMANTIC_UNION_RANGES
    )
    if len(packed) != 924 or _sha(packed) != SEMANTIC_PACKED_SHA256:
        raise ValueError("SoundMain semantic promotion bytes changed")
    union_vector_sha = _sha(_compact_canonical(SEMANTIC_UNION_RANGES))
    if union_vector_sha != SEMANTIC_UNION_VECTOR_SHA256:
        raise ValueError("SoundMain semantic promotion range vector changed")
    return {
        "code_ranges": CODE_RANGES,
        "literal_ranges": LITERAL_RANGES,
        "semantic_union_ranges": SEMANTIC_UNION_RANGES,
        "semantic_bytes": len(packed),
        "semantic_claim_count": len(CODE_RANGES) + len(LITERAL_RANGES),
        "semantic_packed_sha256": SEMANTIC_PACKED_SHA256,
        "semantic_union_range_vector_sha256": SEMANTIC_UNION_VECTOR_SHA256,
        "deferred_alignment_gap_ranges": ALIGNMENT_GAP_RANGES,
        "deferred_alignment_gap_bytes": sum(
            end - start for start, end in ALIGNMENT_GAP_RANGES
        ),
        "alignment_gap_requires_accepted_immutable_artifact": True,
        "projected_totals": {
            "classified_bytes": 6_123_413,
            "unknown_bytes": 168_043,
            "claim_count": 14_490,
            "segment_count": 16_600,
        },
        "post_gap_projected_totals": {
            "classified_bytes": 6_123_419,
            "unknown_bytes": 168_037,
            "claim_count": 14_493,
            "segment_count": 16_600,
        },
    }


def build_preflight_from_rom(root: Path | str, rom: bytes) -> dict[str, Any]:
    root_path = _validate_root(root)
    _validate_rom(rom)
    operation = _copy_operation(rom)
    denominator = _producer_denominator(root_path, rom)
    cfg = analyze_relocated_cfg(rom)
    envelope_bytes = SOURCE_ENVELOPE[1] - SOURCE_ENVELOPE[0]
    if _sha(_bounded(rom, *SOURCE_ENVELOPE)) != SOURCE_ENVELOPE_SHA256:
        raise ValueError("SoundMain source envelope changed")
    runtime_end = RUNTIME_START + envelope_bytes
    return {
        "schema": SCHEMA,
        "rom": {
            "path": ROM_PATH.as_posix(),
            "size": len(rom),
            "sha256": BASE_ROM_SHA256,
        },
        "copy_operation": operation,
        "producer_denominator": denominator,
        "cfg": cfg,
        "coverage_baseline": _coverage_baseline(root_path),
        "promotion": _semantic_promotion(rom),
        "source": {
            "rom_envelope": SOURCE_ENVELOPE,
            "gba_envelope": [
                f"0x{ROM_BASE + SOURCE_ENVELOPE[0]:08X}",
                f"0x{ROM_BASE + SOURCE_ENVELOPE[1]:08X}",
            ],
            "runtime_envelope": [RUNTIME_START, runtime_end],
            "gba_to_runtime_delta": RUNTIME_START - (ROM_BASE + SOURCE_START),
            "envelope_bytes": envelope_bytes,
            "envelope_sha256": SOURCE_ENVELOPE_SHA256,
            "copied_but_outside_envelope_range": [SOURCE_ENVELOPE[1], COPY_RANGE[1]],
            "copied_but_outside_envelope_bytes": COPY_RANGE[1] - SOURCE_ENVELOPE[1],
        },
        "scope": {
            "cpuset_copy_operation_complete": True,
            "target_limited_direct_bl_denominator_complete": True,
            "computed_or_indirect_producer_denominator_complete": False,
            "copied_window_is_all_code": False,
            "relocated_cfg_complete": True,
            "relocated_runtime_mapping_bound": True,
            "alignment_gaps_classified_by_semantic_packet": False,
            "alignment_gaps_require_post_acceptance_receipt": True,
            "natural_runtime_reachability_complete": False,
            "editing_relocation_writeback_safe": False,
            "allocatable_free_space_proven": False,
        },
    }


def build_preflight(root: Path | str) -> dict[str, Any]:
    root_path = _validate_root(root)
    rom = _safe_file(root_path, ROM_PATH).read_bytes()
    return build_preflight_from_rom(root_path, rom)


def _implementation(root: Path) -> dict[str, Any]:
    paths = {
        "exporter": Path("tools/export_rom_soundmain_relocated_cfg.py"),
        "verifier": Path("tools/verify_rom_soundmain_relocated_cfg.py"),
        "exporter_test": Path("tests/test_export_rom_soundmain_relocated_cfg.py"),
        "verifier_test": Path("tests/test_verify_rom_soundmain_relocated_cfg.py"),
    }
    return {
        role: {
            "path": path.as_posix(),
            "sha256": _sha(_safe_file(root, path).read_bytes()),
        }
        for role, path in paths.items()
    }


def _artifact_packet(
    root: Path, rom: bytes, preflight: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], bytes]:
    rows: list[dict[str, Any]] = []
    layout: list[dict[str, Any]] = []
    parts: list[bytes] = []
    bundle_offset = 0
    for frozen in SEMANTIC_RANGE_ROWS:
        row = {**frozen, "range": list(frozen["range"])}
        start, end = row["range"]
        raw = _bounded(rom, start, end)
        if len(raw) != row["size"] or _sha(raw) != row["sha256"]:
            raise ValueError(f"semantic promotion range changed: {row['id']}")
        rows.append(row)
        layout.append({
            "kind": row["kind"],
            "range": list(row["range"]),
            "source_offset": start,
            "bundle_offset": bundle_offset,
            "size": row["size"],
            "sha256": row["sha256"],
        })
        parts.append(raw)
        bundle_offset += len(raw)

    bundle = b"".join(parts)
    if len(bundle) != 924 or _sha(bundle) != SEMANTIC_PACKED_SHA256:
        raise ValueError("semantic packed binary changed")
    scope = preflight["scope"]
    claims = [
        {
            **row,
            "role": "primary",
            "promotion_batch": ARTIFACT_SCHEMA,
            "promoted_from_primary_class": "unknown",
            "promotion_union_range_count": len(SEMANTIC_UNION_RANGES),
            "promotion_union_bytes": len(bundle),
            "promotion_union_range_vector_sha256": SEMANTIC_UNION_VECTOR_SHA256,
            "non_claims": scope,
            "limitations": LIMITATIONS,
        }
        for row in rows
    ]
    return rows, claims, layout, bundle


def build_payload_from_rom(
    root: Path | str, rom: bytes
) -> tuple[dict[str, Any], bytes]:
    root_path = _validate_root(root)
    preflight = build_preflight_from_rom(root_path, bytes(rom))
    rows, claims, layout, bundle = _artifact_packet(
        root_path, bytes(rom), preflight
    )
    summary = {
        **preflight["cfg"]["summary"],
        "promoted_bytes": len(bundle),
        "promotion_claim_count": len(claims),
        "promotion_range_count": len(rows),
        "promotion_union_range_count": len(SEMANTIC_UNION_RANGES),
        "deferred_alignment_gap_bytes": preflight["promotion"][
            "deferred_alignment_gap_bytes"
        ],
    }
    payload = {
        **preflight,
        "schema": ARTIFACT_SCHEMA,
        "promotion_ranges": rows,
        "coverage_claims": claims,
        "packed_layout": layout,
        "packed_binary": {
            "file": BUNDLE_NAME,
            "size": len(bundle),
            "sha256": _sha(bundle),
            "layout": layout,
        },
        "summary": summary,
        "limitations": LIMITATIONS,
        "implementation": _implementation(root_path),
    }
    return payload, bundle


def build_payload(root: Path | str) -> tuple[dict[str, Any], bytes]:
    root_path = _validate_root(root)
    rom = _safe_file(root_path, ROM_PATH).read_bytes()
    return build_payload_from_rom(root_path, rom)


def _reject_symlink_components(path: Path) -> None:
    absolute = path.absolute()
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"output path uses a symlink: {cursor}")


def _validate_output(root: Path, output: Path | str) -> Path:
    target = Path(output).expanduser()
    if not target.is_absolute():
        target = root / target
    _reject_symlink_components(target)
    target = target.resolve(strict=False)
    parent = target.parent.resolve()
    if root != parent and root not in parent.parents:
        raise ValueError("output must stay inside repository root")
    if target.exists():
        if target.is_symlink() or not target.is_dir():
            raise ValueError("output must be a new directory")
        if any(target.iterdir()):
            raise ValueError("output directory must be empty")
    return target


def _candidate_manifest(
    payload: dict[str, Any],
    payload_raw: bytes,
    bundle: bytes,
    output_artifact: str,
) -> dict[str, Any]:
    return {
        "schema": PROMOTION_SCHEMA,
        "artifact_schema": ARTIFACT_SCHEMA,
        "artifact_status": "candidate",
        "rom": payload["rom"],
        "coverage_baseline": payload["coverage_baseline"],
        "copy_operation": payload["copy_operation"],
        "producer_denominator": payload["producer_denominator"],
        "source": payload["source"],
        "files": {
            PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)},
            BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bundle)},
        },
        "implementation": payload["implementation"],
        "producer": {
            "kind": "artifact-candidate-construction",
            "output_artifact": output_artifact,
            "command": [
                "python3",
                "tools/export_rom_soundmain_relocated_cfg.py",
                "--output",
                output_artifact,
            ]
        },
        "verification": {"status": "pending", "report": None},
        "promotion": payload["promotion"],
        "scope": payload["scope"],
        "summary": payload["summary"],
        "limitations": payload["limitations"],
    }


def write_candidate(root: Path | str, output: Path | str) -> dict[str, Any]:
    repository = _validate_root(root)
    target = _validate_output(repository, output)
    payload, bundle = build_payload(repository)
    payload_raw = _canonical(payload)
    output_artifact = target.relative_to(repository).as_posix()
    manifest_raw = _canonical(
        _candidate_manifest(payload, payload_raw, bundle, output_artifact)
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    try:
        (staging / PAYLOAD_NAME).write_bytes(payload_raw)
        (staging / BUNDLE_NAME).write_bytes(bundle)
        (staging / MANIFEST_NAME).write_bytes(manifest_raw)
        if target.exists():
            target.rmdir()
        os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        "artifact": str(target),
        "payload_sha256": _sha(payload_raw),
        "bundle_sha256": _sha(bundle),
        "manifest_sha256": _sha(manifest_raw),
    }


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path, default=ARTIFACT_RELATIVE)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = (
            build_preflight(args.root)
            if args.preflight
            else write_candidate(args.root, args.output)
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema": SCHEMA, "verified": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
