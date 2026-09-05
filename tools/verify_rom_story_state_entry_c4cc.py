#!/usr/bin/env python3
"""Independently verify the target-local CFG rooted at story-state entry C4CC."""

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
from tools.verify_rom_story_state_callback_cfg import verify_artifact as verify_callback_artifact


SCHEMA = "rom-story-state-entry-c4cc-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
DEPENDENCY_PATH = Path("artifacts/rom-story-state-callback-cfg-v1")
DEPENDENCY_PAYLOAD = "rom-story-state-callback-cfg.json"
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "b71a91d1e3c469a884f6d434a82ce23e751e201e83728e6ffc040a6226bfed52"
HISTORICAL_CLASSIFIED_BYTES = 6_176_433
HISTORICAL_UNKNOWN_BYTES = 115_023
TARGET = 0x08C4CC
SOURCE_START = 0x08FA26
SOURCE_END = 0x08FA2A
CODE_START = 0x08C4CC
CODE_END = 0x08C584
LITERALS_START = 0x08C584
LITERALS_END = 0x08C5A8
UNKNOWN_TAIL_START = 0x08C5A8
UNKNOWN_TAIL_END = 0x08CBB4
PAYLOAD_NAME = "rom-story-state-entry-c4cc.json"
MANIFEST_NAME = "manifest.json"
LITERAL_EXPECTATIONS = (
    (0x08C4D6, 0x08C584, 0x0300004C),
    (0x08C50E, 0x08C588, 0x08405EA4),
    (0x08C510, 0x08C58C, 0x06006800),
    (0x08C516, 0x08C590, 0x08405F10),
    (0x08C520, 0x08C594, 0x08405FF0),
    (0x08C522, 0x08C598, 0x05000100),
    (0x08C52A, 0x08C59C, 0x04000008),
    (0x08C530, 0x08C5A0, 0x03000054),
    (0x08C548, 0x08C5A4, 0x08408BC4),
)
_DEPENDENCY_CACHE: tuple[tuple[str, str], dict[str, Any]] | None = None


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _checked_file(root: Path, relative: Path) -> Path:
    root = root.resolve(strict=True)
    lexical = root / relative
    resolved = lexical.resolve(strict=True)
    if lexical.is_symlink() or not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"unsafe file: {relative}")
    return resolved


def _checked_directory(root: Path, relative: Path) -> Path:
    root = root.resolve(strict=True)
    lexical = root / relative
    resolved = lexical.resolve(strict=True)
    if lexical.is_symlink() or not resolved.is_relative_to(root) or not resolved.is_dir():
        raise ValueError(f"unsafe directory: {relative}")
    return resolved


def _decode_control(rom: bytes, offset: int) -> tuple[str, int] | None:
    halfword = struct.unpack_from("<H", rom, offset)[0]
    if offset + 4 <= len(rom):
        second = struct.unpack_from("<H", rom, offset + 2)[0]
        destination = decode_thumb_bl(offset, halfword, second)
        if destination is not None:
            return "bl", destination
    destination = decode_thumb_b(offset, halfword)
    if destination is not None:
        return "b", destination
    condition = (halfword >> 8) & 0xF
    if halfword & 0xF000 == 0xD000 and condition < 0xE:
        delta = (halfword & 0xFF) * 2
        if delta & 0x100:
            delta -= 0x200
        return "bcond", offset + 4 + delta
    return None


def _direct_denominator(rom: bytes, destination: int) -> list[list[Any]]:
    result: list[list[Any]] = []
    for source in range(0, len(rom) - 3, 2):
        decoded = _decode_control(rom, source)
        if decoded is not None and decoded[1] == destination:
            result.append([source, destination, decoded[0]])
    return result


def _find_words(rom: bytes, word: int) -> list[int]:
    needle = word.to_bytes(4, "little")
    result: list[int] = []
    cursor = 0
    while True:
        cursor = rom.find(needle, cursor)
        if cursor == -1:
            return result
        result.append(cursor)
        cursor += 1


def _verify_dependency(root: Path) -> dict[str, Any]:
    global _DEPENDENCY_CACHE
    directory = _checked_directory(root, DEPENDENCY_PATH)
    manifest_file = _checked_file(root, DEPENDENCY_PATH / MANIFEST_NAME)
    payload_file = _checked_file(root, DEPENDENCY_PATH / DEPENDENCY_PAYLOAD)
    manifest_raw = manifest_file.read_bytes()
    payload_raw = payload_file.read_bytes()
    cache_key = (_hash(manifest_raw), _hash(payload_raw))
    if _DEPENDENCY_CACHE is not None and _DEPENDENCY_CACHE[0] == cache_key:
        return dict(_DEPENDENCY_CACHE[1])
    report = verify_callback_artifact(root, directory)
    if report.get("verified") is not True:
        raise ValueError(f"callback dependency failed independent replay: {report.get('errors')}")
    manifest = json.loads(manifest_raw)
    payload = json.loads(payload_raw)
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("callback dependency is not accepted")
    promotion = payload.get("promotion")
    if not isinstance(promotion, dict) or promotion.get("primary_class") != "armv4t_story_state_callback_cfg":
        raise ValueError("callback dependency class changed")
    byte_owners = {offset: [] for offset in range(SOURCE_START, SOURCE_END)}
    claims = promotion.get("claims")
    if not isinstance(claims, list):
        raise ValueError("callback dependency claims missing")
    for claim in claims:
        bounds = claim.get("range") if isinstance(claim, dict) else None
        if claim.get("kind") != "reachable_thumb_code" or not isinstance(bounds, list) or len(bounds) != 2:
            continue
        for offset in range(max(bounds[0], SOURCE_START), min(bounds[1], SOURCE_END)):
            byte_owners[offset].append(claim.get("id"))
    if any(len(owners) != 1 for owners in byte_owners.values()):
        raise ValueError("callback dependency does not uniquely cover producer instruction")
    result = {
        "artifact": DEPENDENCY_PATH.as_posix(),
        "artifact_schema": manifest.get("artifact_schema"),
        "manifest_sha256": _hash(manifest_raw),
        "payload_sha256": _hash(payload_raw),
        "verifier": "tools/verify_rom_story_state_callback_cfg.py",
        "verifier_report_schema": report.get("schema"),
        "verified": True,
        "required_source_range": [SOURCE_START, SOURCE_END],
        "required_primary_class": promotion["primary_class"],
        "covering_claim_ids": sorted({owners[0] for owners in byte_owners.values()}),
    }
    _DEPENDENCY_CACHE = (cache_key, result)
    return dict(result)


def _independent_cfg(rom: bytes) -> dict[str, Any]:
    disassembler = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    decoded = list(disassembler.disasm(rom[CODE_START:CODE_END], ROM_BASE + CODE_START))
    if sum(instruction.size for instruction in decoded) != CODE_END - CODE_START:
        raise ValueError("independent code extent decode failed")
    vector: list[dict[str, Any]] = []
    calls: list[list[int]] = []
    local_edges: list[list[Any]] = []
    literal_rows: list[tuple[int, int, int]] = []
    for instruction in decoded:
        offset = instruction.address - ROM_BASE
        raw = rom[offset : offset + instruction.size]
        vector.append(
            {
                "file_offset": offset,
                "size": instruction.size,
                "raw_hex": raw.hex(),
                "mnemonic": instruction.mnemonic,
                "op_str": instruction.op_str,
                "bytes_sha256": _hash(raw),
            }
        )
        control = _decode_control(rom, offset)
        if control is not None:
            if control[0] == "bl":
                calls.append([offset, control[1]])
            else:
                local_edges.append([offset, control[1], control[0]])
        if instruction.size == 2:
            encoding = struct.unpack_from("<H", rom, offset)[0]
            if encoding & 0xF800 == 0x4800:
                literal = ((offset + 4) & ~3) + (encoding & 0xFF) * 4
                if not LITERALS_START <= literal <= LITERALS_END - 4:
                    raise ValueError("PC-relative load escaped literal pool")
                literal_rows.append((offset, literal, struct.unpack_from("<I", rom, literal)[0]))
    if len(decoded) != 78 or sum(row.size for row in decoded) != 184:
        raise ValueError("independent instruction denominator changed")
    if len(calls) != 14 or local_edges:
        raise ValueError("independent call/branch denominator changed")
    if tuple(literal_rows) != LITERAL_EXPECTATIONS:
        raise ValueError("independent literal denominator changed")
    epilogue = rom[0x08C57C:0x08C584]
    if epilogue != b"\x06\xb0\x10\xbc\x01\xbc\x00\x47":
        raise ValueError("strict return epilogue changed")
    if rom[UNKNOWN_TAIL_START : UNKNOWN_TAIL_START + 2] != b"\x10\xb5":
        raise ValueError("excluded next entry changed")
    return {
        "root": TARGET,
        "code_range": [CODE_START, CODE_END],
        "code_sha256": _hash(rom[CODE_START:CODE_END]),
        "instruction_count": len(decoded),
        "instruction_bytes": 184,
        "basic_block_count": len(calls) + 1,
        "opaque_external_call_count": len(calls),
        "opaque_external_calls": calls,
        "local_branch_count": 0,
        "local_edges": local_edges,
        "hole_count": 0,
        "frontier_count": 0,
        "strict_return": {
            "instruction_offsets": [0x08C57C, 0x08C57E, 0x08C580, 0x08C582],
            "raw_hex": epilogue.hex(),
            "proof": "pop_r0_then_bx_r0",
        },
        "literal_range": [LITERALS_START, LITERALS_END],
        "literal_sha256": _hash(rom[LITERALS_START:LITERALS_END]),
        "literal_bindings": [[source, target, f"0x{value:08X}"] for source, target, value in literal_rows],
        "next_entry_excluded": [UNKNOWN_TAIL_START, rom[UNKNOWN_TAIL_START : UNKNOWN_TAIL_START + 2].hex()],
        "instruction_vector_sha256": _hash(_json_bytes(vector)),
    }


def _live_coverage(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[int]]:
    raw = _checked_file(root, COVERAGE_PATH).read_bytes()
    if _hash(raw) != COVERAGE_SHA256:
        raise ValueError("live coverage no longer matches historical build baseline")
    coverage = json.loads(raw)
    segments = coverage.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("coverage segments missing")
    return coverage, segments, [segment["range"][0] for segment in segments]


def _require_unknown(segments: list[dict[str, Any]], starts: list[int]) -> None:
    for first, last in (
        (CODE_START, CODE_END),
        (LITERALS_START, LITERALS_END),
        (UNKNOWN_TAIL_START, UNKNOWN_TAIL_END),
    ):
        cursor = first
        while cursor < last:
            index = bisect.bisect_right(starts, cursor) - 1
            if index < 0:
                raise ValueError("coverage lookup underflow")
            segment = segments[index]
            if not segment["range"][0] <= cursor < segment["range"][1]:
                raise ValueError("coverage segment gap")
            if segment.get("primary_class") != "unknown":
                raise ValueError("candidate or preserved tail is not canonical unknown")
            cursor = min(last, segment["range"][1])


def rebuild_payload(
    root: Path,
    rom_override: bytes | None = None,
    *,
    validate_live_coverage: bool = True,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    rom = _checked_file(root, ROM_PATH).read_bytes() if rom_override is None else rom_override
    if len(rom) != ROM_SIZE or _hash(rom) != ROM_SHA256:
        raise ValueError("fixed ROM identity changed")
    dependency = _verify_dependency(root)
    producers = _direct_denominator(rom, TARGET)
    if producers != [[SOURCE_START, TARGET, "bl"]]:
        raise ValueError("independent direct producer denominator changed")
    thumb_words = _find_words(rom, ROM_BASE + TARGET + 1)
    even_words = _find_words(rom, ROM_BASE + TARGET)
    if thumb_words or even_words:
        raise ValueError("independent pointer denominator changed")
    if validate_live_coverage:
        coverage, segments, starts = _live_coverage(root)
        _require_unknown(segments, starts)
        classified = coverage["summary"]["classified_bytes"]
        unknown = coverage["summary"]["unknown_bytes"]
    else:
        classified = HISTORICAL_CLASSIFIED_BYTES
        unknown = HISTORICAL_UNKNOWN_BYTES
    cfg = _independent_cfg(rom)
    claims = []
    for kind, start, end in (
        ("reachable_thumb_code", CODE_START, CODE_END),
        ("consumed_literal_words", LITERALS_START, LITERALS_END),
    ):
        claims.append(
            {
                "id": f"story-state-entry-c4cc-{kind}-{start:06x}",
                "kind": kind,
                "range": [start, end],
                "bytes_sha256": _hash(rom[start:end]),
                "baseline_unknown_only": True,
            }
        )
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": _hash(rom)},
        "upstream_dependency": dependency,
        "producer_denominator": {
            "direct": producers,
            "thumb_pointer_occurrences": thumb_words,
            "even_u32_occurrences": even_words,
        },
        "target_local_cfg": cfg,
        "coverage_baseline": {
            "historical_reference": {"path": COVERAGE_PATH.as_posix(), "sha256": COVERAGE_SHA256},
            "state": "baseline_unknown",
            "classified_bytes": classified,
            "unknown_bytes": unknown,
            "observed_during_artifact_build": True,
            "replay_mode": "historical_build_receipt_replay",
            "live_coverage_verified_on_replay": False,
        },
        "promotion": {
            "primary_class": "armv4t_story_state_entry_cfg",
            "claim_kind": "story_state_entry_c4cc_exact_bytes",
            "code_ranges": [[CODE_START, CODE_END]],
            "literal_ranges": [[LITERALS_START, LITERALS_END]],
            "code_bytes": 184,
            "literal_bytes": 36,
            "promotion_bytes": 220,
            "remaining_unknown_range": [UNKNOWN_TAIL_START, UNKNOWN_TAIL_END],
            "remaining_unknown_bytes": 1548,
            "claims": claims,
        },
        "coverage_projection": {
            "gate": "projection_deferred_to_coverage_auditor",
            "post_promotion_owner": "exact_packet_owner_required",
        },
        "scope": {
            "natural_runtime_reachability": False,
            "external_callee_classification": False,
            "remaining_cluster_code_classification": False,
            "business_semantics": False,
            "editing_relocation_padding_or_free_space": False,
        },
    }


def verify_artifact(
    root: Path,
    artifact: Path,
    expected_receipt_path: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        root = root.resolve(strict=True)
        lexical_artifact = artifact if artifact.is_absolute() else root / artifact
        lexical_artifact = lexical_artifact.absolute()
        artifact = lexical_artifact.resolve(strict=True)
        if (
            lexical_artifact != artifact
            or lexical_artifact.is_symlink()
            or not artifact.is_relative_to(root)
            or not artifact.is_dir()
        ):
            raise ValueError("unsafe artifact directory")
        members = list(artifact.iterdir())
        if {member.name for member in members} != {MANIFEST_NAME, PAYLOAD_NAME}:
            raise ValueError("artifact members changed")
        if any(not member.is_file() or member.is_symlink() for member in members):
            raise ValueError("artifact contains nested or symlink members")
        manifest_raw = (artifact / MANIFEST_NAME).read_bytes()
        payload_raw = (artifact / PAYLOAD_NAME).read_bytes()
        manifest = json.loads(manifest_raw)
        payload = json.loads(payload_raw)
        if manifest_raw != _json_bytes(manifest) or payload_raw != _json_bytes(payload):
            raise ValueError("artifact JSON is not canonical")
        expected = rebuild_payload(root, validate_live_coverage=False)
        if payload != expected:
            raise ValueError("artifact payload differs from independent raw rebuild")
        if manifest.get("artifact_schema") != SCHEMA or manifest.get("artifact_status") not in {"candidate", "accepted"}:
            raise ValueError("artifact manifest contract changed")
        expected_files = {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _hash(payload_raw)}}
        if manifest.get("files") != expected_files:
            raise ValueError("artifact file receipt changed")
        if manifest.get("promotion") != payload["promotion"]:
            raise ValueError("artifact promotion receipt changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    receipt = expected_receipt_path or artifact
    return {
        "schema": "rom-story-state-entry-c4cc-verifier-report-v1",
        "verified": not errors,
        "contract_ok": not errors,
        "errors": errors,
        "artifact": receipt.as_posix(),
        "promotion_bytes": 220 if not errors else 0,
        "live_coverage_verified": False,
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
