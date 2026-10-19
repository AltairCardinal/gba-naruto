#!/usr/bin/env python3
"""Export the frozen story-state scheduler callback CFG packet."""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
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
ROOT_POINTER = ROM_BASE + ROOT + 1
PAYLOAD_NAME = "rom-story-state-callback-cfg.json"
MANIFEST_NAME = "manifest.json"
OFFICIAL = Path("artifacts/rom-story-state-callback-cfg-v1")
EXPERIMENT_ROOT = Path("build/experiments/active/story-state-callback-cfg-20260902/luna-r1")

CODE_RANGES = (
    (0x08F73C, 0x08F77A),
    (0x08F784, 0x08F8EE),
    (0x08F8F4, 0x08F974),
    (0x08F978, 0x08F99A),
    (0x08F9A0, 0x08FA00),
    (0x08FA04, 0x08FA32),
)
PROMOTION_CODE_RANGES = (
    (0x08F73C, 0x08F77A),
    (0x08F784, 0x08F844),
    (0x08F848, 0x08F866),
    (0x08F872, 0x08F8EE),
    (0x08F8F4, 0x08F974),
    (0x08F978, 0x08F99A),
    (0x08F9A0, 0x08F9E2),
    (0x08FA08, 0x08FA32),
)
LITERAL_RANGES = (
    (0x08F77C, 0x08F784),
    (0x08F8F0, 0x08F8F4),
    (0x08F974, 0x08F978),
    (0x08F99C, 0x08F9A0),
    (0x08FA00, 0x08FA04),
)
EXCLUDED_GAPS = (
    (0x08F77A, 0x08F77C),
    (0x08F8EE, 0x08F8F0),
    (0x08F99A, 0x08F99C),
    (0x08FA32, 0x08FA34),
)
EXPECTED_BINDINGS = (
    (0x08F746, 0x08F77C, 0x03000075),
    (0x08F74E, 0x08F780, 0x020311D4),
    (0x08F8E4, 0x08F8F0, 0x000003E7),
    (0x08F93A, 0x08F974, 0x02026804),
    (0x08F962, 0x08F974, 0x02026804),
    (0x08F98A, 0x08F99C, 0x020311D4),
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


def _branch_target(rom: bytes, offset: int) -> tuple[str, int] | None:
    first = struct.unpack_from("<H", rom, offset)[0]
    if offset + 4 <= len(rom):
        second = struct.unpack_from("<H", rom, offset + 2)[0]
        target = decode_thumb_bl(offset, first, second)
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


def _target_matches(rom: bytes, target: int) -> list[list[Any]]:
    matches: list[list[Any]] = []
    for offset in range(0, len(rom) - 3, 2):
        decoded = _branch_target(rom, offset)
        if decoded is not None and decoded[1] == target:
            matches.append([offset, target, decoded[0]])
    return matches


def _u32_occurrences(rom: bytes, value: int) -> list[int]:
    raw = struct.pack("<I", value)
    return [offset for offset in range(0, len(rom) - 3) if rom[offset : offset + 4] == raw]


def _in_ranges(offset: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= offset < end for start, end in ranges)


def _decode_cfg(rom: bytes) -> dict[str, Any]:
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    instructions: list[dict[str, Any]] = []
    opaque_calls: list[list[int]] = []
    local_edges: list[list[Any]] = []
    bindings: list[tuple[int, int, int]] = []
    for start, end in CODE_RANGES:
        rows = list(engine.disasm(rom[start:end], ROM_BASE + start))
        if not rows or sum(row.size for row in rows) != end - start:
            raise ValueError("callback code range no longer decodes exactly")
        for row in rows:
            offset = row.address - ROM_BASE
            raw = rom[offset : offset + row.size]
            instructions.append(
                {
                    "file_offset": offset,
                    "size": row.size,
                    "raw_hex": raw.hex(),
                    "mnemonic": row.mnemonic,
                    "op_str": row.op_str,
                    "bytes_sha256": _sha(raw),
                }
            )
            branch = _branch_target(rom, offset)
            if branch is not None:
                kind, target = branch
                if kind == "bl":
                    opaque_calls.append([offset, target])
                else:
                    if not _in_ranges(target, CODE_RANGES):
                        raise ValueError("callback local branch escaped frozen envelope")
                    local_edges.append([offset, target, kind])
            if row.size == 2:
                halfword = struct.unpack_from("<H", rom, offset)[0]
                if halfword & 0xF800 == 0x4800:
                    target = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
                    if _in_ranges(target, LITERAL_RANGES):
                        bindings.append((offset, target, struct.unpack_from("<I", rom, target)[0]))
    if len(instructions) != 336 or sum(row["size"] for row in instructions) != 728:
        raise ValueError("callback instruction denominator changed")
    if len(opaque_calls) != 28:
        raise ValueError("callback opaque call denominator changed")
    if tuple(bindings) != EXPECTED_BINDINGS:
        raise ValueError("callback literal binding denominator changed")
    if rom[0x08FA32:0x08FA34] != b"\x00\x00":
        raise ValueError("excluded callback tail changed")
    return {
        "instruction_count": len(instructions),
        "code_bytes": 728,
        "code_range_count": len(CODE_RANGES),
        "opaque_external_call_count": len(opaque_calls),
        "frontier_count": 0,
        "code_ranges": [list(row) for row in CODE_RANGES],
        "literal_ranges": [list(row) for row in LITERAL_RANGES],
        "literal_bindings": [[source, target, f"0x{value:08X}"] for source, target, value in bindings],
        "opaque_external_calls": opaque_calls,
        "local_edges": local_edges,
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


def _segment(segments: list[dict[str, Any]], starts: list[int], offset: int) -> dict[str, Any]:
    row = segments[bisect.bisect_right(starts, offset) - 1]
    if not row["range"][0] <= offset < row["range"][1]:
        raise ValueError("coverage segment lookup failed")
    return row


def _assert_unknown(segments: list[dict[str, Any]], starts: list[int], ranges: tuple[tuple[int, int], ...]) -> None:
    for start, end in ranges:
        cursor = start
        while cursor < end:
            row = _segment(segments, starts, cursor)
            if row.get("primary_class") != "unknown":
                raise ValueError("promotion escaped baseline unknown bytes")
            cursor = min(end, row["range"][1])


def build_payload(root: Path, rom_override: bytes | None = None) -> dict[str, Any]:
    root = root.resolve(strict=True)
    rom = _safe_file(root, ROM_PATH).read_bytes() if rom_override is None else rom_override
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("fixed ROM identity changed")
    gate = verify_scheduler_callback_lifecycle_gate(root, rom=rom)
    callback = gate.get("callbacks", {}).get("0x0808F73C", {})
    if not gate.get("verified") or callback.get("lifecycle_status") != "registration_dispatch_return_closed":
        raise ValueError("scheduler callback provenance changed")
    if callback.get("pointer_occurrences") != [0x6107C, 0x859B4]:
        raise ValueError("callback pointer denominator changed")
    if _target_matches(rom, ROOT):
        raise ValueError("callback root direct producer denominator changed")
    internal = _target_matches(rom, 0x08FA26) + _target_matches(rom, 0x08FA2C)
    if internal != [[0x08F7F4, 0x08FA26, "b"], [0x08F80A, 0x08FA2C, "b"]]:
        raise ValueError("internal handler branch denominator changed")
    consumer = _target_matches(rom, 0x08C4CC)
    if consumer != [[0x08FA26, 0x08C4CC, "bl"]]:
        raise ValueError("0x0808C4CC producer denominator changed")
    coverage, segments, starts = _coverage(root)
    _assert_unknown(segments, starts, PROMOTION_CODE_RANGES + LITERAL_RANGES)
    denominator = _decode_cfg(rom)
    claims = []
    for kind, ranges in (("reachable_thumb_code", PROMOTION_CODE_RANGES), ("consumed_literal_words", LITERAL_RANGES)):
        for index, (start, end) in enumerate(ranges, 1):
            claims.append(
                {
                    "id": f"story-callback-{kind}-{index:02d}-{start:06x}",
                    "kind": kind,
                    "range": [start, end],
                    "bytes_sha256": _sha(rom[start:end]),
                    "baseline_unknown_only": True,
                }
            )
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": _sha(rom)},
        "coverage_baseline": {
            "identity": {"path": COVERAGE_PATH.as_posix(), "sha256": COVERAGE_SHA256},
            "state": "baseline_unknown",
            "replay_mode": "historical_build_receipt_replay",
            "classified_bytes": coverage["summary"]["classified_bytes"],
            "unknown_bytes": coverage["summary"]["unknown_bytes"],
        },
        "root": {
            "file_offset": ROOT,
            "gba_address": f"0x{ROM_BASE + ROOT:08X}",
            "thumb_pointer": ROOT_POINTER,
            "pointer_occurrences": callback["pointer_occurrences"],
            "scheduler_lifecycle_status": callback["lifecycle_status"],
        },
        "producer_denominator": {
            "callback_root_direct_branches": [],
            "internal_handler_direct_branches": internal,
            "consumer_direct_bl": consumer,
            "target_pointer_occurrences": {
                "0x0808FA26": _u32_occurrences(rom, 0x0808FA27),
                "0x0808FA2C": _u32_occurrences(rom, 0x0808FA2D),
                "0x0808C4CC": _u32_occurrences(rom, 0x0808C4CD),
            },
            "target_even_u32_occurrences": {
                "0x0808FA26": _u32_occurrences(rom, 0x0808FA26),
                "0x0808FA2C": _u32_occurrences(rom, 0x0808FA2C),
                "0x0808C4CC": _u32_occurrences(rom, 0x0808C4CC),
            },
        },
        "target_local_denominator": denominator,
        "promotion": {
            "primary_class": "armv4t_story_state_callback_cfg",
            "claim_kind": "story_state_callback_cfg_exact_bytes",
            "code_ranges": [list(row) for row in PROMOTION_CODE_RANGES],
            "literal_ranges": [list(row) for row in LITERAL_RANGES],
            "preserved_unknown_gaps": [list(row) for row in EXCLUDED_GAPS],
            "code_bytes": 678,
            "literal_bytes": 24,
            "promotion_bytes": 702,
            "preserved_unknown_bytes": 8,
            "claims": claims,
        },
        "coverage_projection": {"post_promotion_gate": "exact_owner_required"},
        "scope": {
            "post_promotion_owner_verification_supported": True,
            "natural_runtime_reachability": False,
            "external_callee_classification": False,
            "business_semantics": False,
            "alignment_zero_classification": False,
            "editing_relocation_or_free_space": False,
        },
    }


def _output_path(root: Path, output: Path) -> Path:
    lexical = (output if output.is_absolute() else root / output).absolute()
    resolved = lexical.resolve(strict=False)
    allowed = (root / EXPERIMENT_ROOT).resolve(strict=True)
    official = (root / OFFICIAL).resolve(strict=False)
    if resolved != lexical or lexical.is_symlink() or not (resolved.is_relative_to(allowed) or resolved == official):
        raise ValueError("output outside packet scope or uses symlink traversal")
    return resolved


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    output = _output_path(root, output)
    if output.exists():
        raise ValueError("output must not already exist")
    payload = build_payload(root)
    payload_raw = _canonical(payload)
    manifest: dict[str, Any] = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "candidate",
        "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}},
        "promotion": payload["promotion"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".story-callback-") as raw:
        stage = Path(raw) / output.name
        stage.mkdir()
        (stage / PAYLOAD_NAME).write_bytes(payload_raw)
        (stage / MANIFEST_NAME).write_bytes(_canonical(manifest))
        from tools.verify_rom_story_state_callback_cfg import verify_artifact

        report = verify_artifact(root, stage, expected_receipt_path=output)
        if not report.get("verified"):
            raise ValueError(f"candidate verification failed: {report.get('errors')}")
        manifest["artifact_status"] = "accepted"
        manifest["verifier_report"] = report
        (stage / MANIFEST_NAME).write_bytes(_canonical(manifest))
        shutil.move(stage, output)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export_artifact(args.root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
