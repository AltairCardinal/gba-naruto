#!/usr/bin/env python3
"""Independently verify the frozen story-state scheduler callback CFG packet."""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _path in (PROJECT_ROOT, PROJECT_ROOT / "tools/_vendor"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs  # type: ignore

from tools.thumb_branch import decode_thumb_b, decode_thumb_bl
from tools.verify_rom_scheduler_callback_lifecycle_gate import (
    verify_scheduler_callback_lifecycle_gate,
)


SCHEMA = "rom-story-state-callback-cfg-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "b71a91d1e3c469a884f6d434a82ce23e751e201e83728e6ffc040a6226bfed52"
ROM_BASE = 0x08000000
ROOT = 0x08F73C
PAYLOAD_NAME = "rom-story-state-callback-cfg.json"
MANIFEST_NAME = "manifest.json"
CODE_RANGES = (
    (0x08F73C, 0x08F77A), (0x08F784, 0x08F8EE), (0x08F8F4, 0x08F974),
    (0x08F978, 0x08F99A), (0x08F9A0, 0x08FA00), (0x08FA04, 0x08FA32),
)
PROMOTION_CODE_RANGES = (
    (0x08F73C, 0x08F77A), (0x08F784, 0x08F844), (0x08F848, 0x08F866),
    (0x08F872, 0x08F8EE), (0x08F8F4, 0x08F974), (0x08F978, 0x08F99A),
    (0x08F9A0, 0x08F9E2), (0x08FA08, 0x08FA32),
)
LITERAL_RANGES = (
    (0x08F77C, 0x08F784), (0x08F8F0, 0x08F8F4), (0x08F974, 0x08F978),
    (0x08F99C, 0x08F9A0), (0x08FA00, 0x08FA04),
)
EXCLUDED_GAPS = (
    (0x08F77A, 0x08F77C), (0x08F8EE, 0x08F8F0),
    (0x08F99A, 0x08F99C), (0x08FA32, 0x08FA34),
)
EXPECTED_BINDINGS = (
    (0x08F746, 0x08F77C, 0x03000075), (0x08F74E, 0x08F780, 0x020311D4),
    (0x08F8E4, 0x08F8F0, 0x000003E7), (0x08F93A, 0x08F974, 0x02026804),
    (0x08F962, 0x08F974, 0x02026804), (0x08F98A, 0x08F99C, 0x020311D4),
    (0x08F9F8, 0x08FA00, 0x020240AC),
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _safe_file(root: Path, relative: Path) -> Path:
    root = root.resolve(strict=True)
    path = root / relative
    resolved = path.resolve(strict=True)
    if path.is_symlink() or not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"unsafe input path: {relative}")
    return resolved


def _branch(rom: bytes, offset: int) -> tuple[str, int] | None:
    first = struct.unpack_from("<H", rom, offset)[0]
    if offset + 4 <= len(rom):
        target = decode_thumb_bl(offset, first, struct.unpack_from("<H", rom, offset + 2)[0])
        if target is not None:
            return "bl", target
    target = decode_thumb_b(offset, first)
    if target is not None:
        return "b", target
    if first & 0xF000 == 0xD000 and ((first >> 8) & 0xF) < 0xE:
        displacement = (first & 0xFF) << 1
        if displacement & 0x100:
            displacement -= 0x200
        return "bcond", offset + 4 + displacement
    return None


def _matches(rom: bytes, target: int) -> list[list[Any]]:
    rows = []
    for offset in range(0, len(rom) - 3, 2):
        decoded = _branch(rom, offset)
        if decoded is not None and decoded[1] == target:
            rows.append([offset, target, decoded[0]])
    return rows


def _u32(rom: bytes, value: int) -> list[int]:
    raw = struct.pack("<I", value)
    return [offset for offset in range(len(rom) - 3) if rom[offset : offset + 4] == raw]


def _inside(offset: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= offset < end for start, end in ranges)


def _cfg(rom: bytes) -> dict[str, Any]:
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    instructions: list[dict[str, Any]] = []
    opaque: list[list[int]] = []
    edges: list[list[Any]] = []
    bindings: list[tuple[int, int, int]] = []
    for start, end in CODE_RANGES:
        decoded = list(engine.disasm(rom[start:end], ROM_BASE + start))
        if sum(row.size for row in decoded) != end - start:
            raise ValueError("independent callback decode changed")
        for row in decoded:
            offset = row.address - ROM_BASE
            raw = rom[offset : offset + row.size]
            instructions.append({
                "file_offset": offset, "size": row.size, "raw_hex": raw.hex(),
                "mnemonic": row.mnemonic, "op_str": row.op_str, "bytes_sha256": _sha(raw),
            })
            flow = _branch(rom, offset)
            if flow is not None:
                kind, target = flow
                if kind == "bl":
                    opaque.append([offset, target])
                else:
                    if not _inside(target, CODE_RANGES):
                        raise ValueError("independent local edge escaped callback")
                    edges.append([offset, target, kind])
            if row.size == 2:
                halfword = struct.unpack_from("<H", rom, offset)[0]
                if halfword & 0xF800 == 0x4800:
                    target = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
                    if _inside(target, LITERAL_RANGES):
                        bindings.append((offset, target, struct.unpack_from("<I", rom, target)[0]))
    if (len(instructions), sum(row["size"] for row in instructions), len(opaque)) != (336, 728, 28):
        raise ValueError("independent callback denominator changed")
    if tuple(bindings) != EXPECTED_BINDINGS:
        raise ValueError("independent literal bindings changed")
    if rom[0x08FA32:0x08FA34] != b"\x00\x00":
        raise ValueError("excluded callback tail changed")
    return {
        "instruction_count": 336, "code_bytes": 728, "code_range_count": 6,
        "opaque_external_call_count": 28, "frontier_count": 0,
        "code_ranges": [list(row) for row in CODE_RANGES],
        "literal_ranges": [list(row) for row in LITERAL_RANGES],
        "literal_bindings": [[source, target, f"0x{value:08X}"] for source, target, value in bindings],
        "opaque_external_calls": opaque, "local_edges": edges,
        "instruction_vector_sha256": _sha(_canonical(instructions)),
    }


def _coverage(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[int]]:
    raw = _safe_file(root, COVERAGE_PATH).read_bytes()
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    value = json.loads(raw)
    segments = value.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("coverage segments missing")
    return value, segments, [row["range"][0] for row in segments]


def _assert_unknown(segments: list[dict[str, Any]], starts: list[int]) -> None:
    for start, end in PROMOTION_CODE_RANGES + LITERAL_RANGES:
        cursor = start
        while cursor < end:
            row = segments[bisect.bisect_right(starts, cursor) - 1]
            if not row["range"][0] <= cursor < row["range"][1] or row.get("primary_class") != "unknown":
                raise ValueError("independent promotion escaped baseline unknown")
            cursor = min(end, row["range"][1])


def rebuild_payload(
    root: Path,
    rom_override: bytes | None = None,
    *,
    validate_live_coverage: bool = True,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    rom = _safe_file(root, ROM_PATH).read_bytes() if rom_override is None else rom_override
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("fixed ROM identity changed")
    gate = verify_scheduler_callback_lifecycle_gate(root, rom=rom)
    callback = gate.get("callbacks", {}).get("0x0808F73C", {})
    if not gate.get("verified") or callback.get("lifecycle_status") != "registration_dispatch_return_closed" or callback.get("pointer_occurrences") != [0x6107C, 0x859B4]:
        raise ValueError("independent scheduler callback provenance changed")
    if _matches(rom, ROOT):
        raise ValueError("independent callback root direct denominator changed")
    internal = _matches(rom, 0x08FA26) + _matches(rom, 0x08FA2C)
    if internal != [[0x08F7F4, 0x08FA26, "b"], [0x08F80A, 0x08FA2C, "b"]]:
        raise ValueError("independent handler branch denominator changed")
    consumer = _matches(rom, 0x08C4CC)
    if consumer != [[0x08FA26, 0x08C4CC, "bl"]]:
        raise ValueError("independent consumer producer denominator changed")
    if validate_live_coverage:
        coverage, segments, starts = _coverage(root)
        _assert_unknown(segments, starts)
        classified_bytes = coverage["summary"]["classified_bytes"]
        unknown_bytes = coverage["summary"]["unknown_bytes"]
    else:
        classified_bytes = 6_176_433
        unknown_bytes = 115_023
    claims = []
    for kind, ranges in (("reachable_thumb_code", PROMOTION_CODE_RANGES), ("consumed_literal_words", LITERAL_RANGES)):
        for index, (start, end) in enumerate(ranges, 1):
            claims.append({
                "id": f"story-callback-{kind}-{index:02d}-{start:06x}", "kind": kind,
                "range": [start, end], "bytes_sha256": _sha(rom[start:end]),
                "baseline_unknown_only": True,
            })
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": _sha(rom)},
        "coverage_baseline": {
            "identity": {"path": COVERAGE_PATH.as_posix(), "sha256": COVERAGE_SHA256},
            "state": "baseline_unknown", "replay_mode": "historical_build_receipt_replay",
            "classified_bytes": classified_bytes, "unknown_bytes": unknown_bytes,
        },
        "root": {
            "file_offset": ROOT, "gba_address": f"0x{ROM_BASE + ROOT:08X}",
            "thumb_pointer": ROM_BASE + ROOT + 1, "pointer_occurrences": callback["pointer_occurrences"],
            "scheduler_lifecycle_status": callback["lifecycle_status"],
        },
        "producer_denominator": {
            "callback_root_direct_branches": [], "internal_handler_direct_branches": internal,
            "consumer_direct_bl": consumer,
            "target_pointer_occurrences": {
                "0x0808FA26": _u32(rom, 0x0808FA27), "0x0808FA2C": _u32(rom, 0x0808FA2D),
                "0x0808C4CC": _u32(rom, 0x0808C4CD),
            },
            "target_even_u32_occurrences": {
                "0x0808FA26": _u32(rom, 0x0808FA26), "0x0808FA2C": _u32(rom, 0x0808FA2C),
                "0x0808C4CC": _u32(rom, 0x0808C4CC),
            },
        },
        "target_local_denominator": _cfg(rom),
        "promotion": {
            "primary_class": "armv4t_story_state_callback_cfg",
            "claim_kind": "story_state_callback_cfg_exact_bytes",
            "code_ranges": [list(row) for row in PROMOTION_CODE_RANGES],
            "literal_ranges": [list(row) for row in LITERAL_RANGES],
            "preserved_unknown_gaps": [list(row) for row in EXCLUDED_GAPS],
            "code_bytes": 678, "literal_bytes": 24, "promotion_bytes": 702,
            "preserved_unknown_bytes": 8, "claims": claims,
        },
        "coverage_projection": {"post_promotion_gate": "exact_owner_required"},
        "scope": {
            "post_promotion_owner_verification_supported": True,
            "natural_runtime_reachability": False, "external_callee_classification": False,
            "business_semantics": False, "alignment_zero_classification": False,
            "editing_relocation_or_free_space": False,
        },
    }


def verify_artifact(root: Path, artifact: Path, expected_receipt_path: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    try:
        root = root.resolve(strict=True)
        artifact = artifact.resolve(strict=True)
        if not artifact.is_dir() or artifact.is_symlink() or not artifact.is_relative_to(root):
            raise ValueError("unsafe artifact directory")
        members = list(artifact.iterdir())
        if {row.name for row in members} != {MANIFEST_NAME, PAYLOAD_NAME} or any(not row.is_file() or row.is_symlink() for row in members):
            raise ValueError("artifact members changed or include nested/symlink entries")
        manifest_raw = (artifact / MANIFEST_NAME).read_bytes()
        payload_raw = (artifact / PAYLOAD_NAME).read_bytes()
        manifest = json.loads(manifest_raw)
        payload = json.loads(payload_raw)
        if _canonical(manifest) != manifest_raw or _canonical(payload) != payload_raw:
            raise ValueError("artifact JSON is not canonical")
        expected = rebuild_payload(root, validate_live_coverage=False)
        if payload != expected:
            raise ValueError("artifact payload differs from independent rebuild")
        if manifest.get("artifact_schema") != SCHEMA or manifest.get("artifact_status") not in {"candidate", "accepted"}:
            raise ValueError("artifact manifest contract changed")
        if manifest.get("files") != {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}}:
            raise ValueError("artifact payload receipt changed")
        if manifest.get("promotion") != payload["promotion"]:
            raise ValueError("artifact promotion contract changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    receipt = expected_receipt_path or artifact
    return {
        "schema": "rom-story-state-callback-cfg-verifier-report-v1",
        "verified": not errors,
        "errors": errors,
        "artifact": receipt.as_posix(),
        "promotion_bytes": 702 if not errors else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
