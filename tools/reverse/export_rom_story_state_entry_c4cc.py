#!/usr/bin/env python3
"""Export the frozen target-local CFG rooted at story-state entry 0x0808C4CC."""

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
from tools.verify_rom_story_state_callback_cfg import verify_artifact as verify_upstream


SCHEMA = "rom-story-state-entry-c4cc-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
UPSTREAM = Path("artifacts/rom-story-state-callback-cfg-v1")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "b71a91d1e3c469a884f6d434a82ce23e751e201e83728e6ffc040a6226bfed52"
HISTORICAL_CLASSIFIED_BYTES = 6_176_433
HISTORICAL_UNKNOWN_BYTES = 115_023
ROOT = 0x08C4CC
SOURCE_RANGE = (0x08FA26, 0x08FA2A)
CODE_RANGE = (0x08C4CC, 0x08C584)
LITERAL_RANGE = (0x08C584, 0x08C5A8)
REMAINING_RANGE = (0x08C5A8, 0x08CBB4)
PAYLOAD_NAME = "rom-story-state-entry-c4cc.json"
MANIFEST_NAME = "manifest.json"
OFFICIAL = Path("artifacts/rom-story-state-entry-c4cc-v1")
EXPERIMENT = Path("build/experiments/active/story-state-entry-c4cc-20260902/sol-r1")
EXPECTED_BINDINGS = (
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
_UPSTREAM_CACHE: tuple[tuple[str, str], dict[str, Any]] | None = None


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _safe_file(root: Path, relative: Path) -> Path:
    root = root.resolve(strict=True)
    lexical = root / relative
    resolved = lexical.resolve(strict=True)
    if lexical.is_symlink() or not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"unsafe input path: {relative}")
    return resolved


def _safe_artifact(root: Path, relative: Path) -> Path:
    root = root.resolve(strict=True)
    lexical = root / relative
    resolved = lexical.resolve(strict=True)
    if lexical.is_symlink() or not resolved.is_relative_to(root) or not resolved.is_dir():
        raise ValueError(f"unsafe dependency artifact: {relative}")
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


def _target_matches(rom: bytes, target: int) -> list[list[Any]]:
    matches: list[list[Any]] = []
    for offset in range(0, len(rom) - 3, 2):
        decoded = _branch(rom, offset)
        if decoded is not None and decoded[1] == target:
            matches.append([offset, target, decoded[0]])
    return matches


def _occurrences(rom: bytes, value: int) -> list[int]:
    needle = struct.pack("<I", value)
    offsets: list[int] = []
    cursor = 0
    while True:
        cursor = rom.find(needle, cursor)
        if cursor < 0:
            return offsets
        offsets.append(cursor)
        cursor += 1


def _upstream_dependency(root: Path) -> dict[str, Any]:
    global _UPSTREAM_CACHE
    artifact = _safe_artifact(root, UPSTREAM)
    manifest_path = _safe_file(root, UPSTREAM / MANIFEST_NAME)
    payload_path = _safe_file(root, UPSTREAM / "rom-story-state-callback-cfg.json")
    manifest_raw = manifest_path.read_bytes()
    payload_raw = payload_path.read_bytes()
    cache_key = (_sha(manifest_raw), _sha(payload_raw))
    if _UPSTREAM_CACHE is not None and _UPSTREAM_CACHE[0] == cache_key:
        return dict(_UPSTREAM_CACHE[1])
    report = verify_upstream(root, artifact)
    if not report.get("verified"):
        raise ValueError(f"upstream callback verifier failed: {report.get('errors')}")
    manifest = json.loads(manifest_raw)
    payload = json.loads(payload_raw)
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("upstream callback artifact is not accepted")
    promotion = payload.get("promotion", {})
    if promotion.get("primary_class") != "armv4t_story_state_callback_cfg":
        raise ValueError("upstream callback primary class changed")
    owners = [0] * (SOURCE_RANGE[1] - SOURCE_RANGE[0])
    owner_ids: list[str] = []
    for claim in promotion.get("claims", []):
        claim_range = claim.get("range")
        if claim.get("kind") != "reachable_thumb_code" or not isinstance(claim_range, list):
            continue
        overlap_start = max(SOURCE_RANGE[0], claim_range[0])
        overlap_end = min(SOURCE_RANGE[1], claim_range[1])
        if overlap_start < overlap_end:
            owner_ids.append(claim["id"])
            for offset in range(overlap_start, overlap_end):
                owners[offset - SOURCE_RANGE[0]] += 1
    if owners != [1] * len(owners):
        raise ValueError("upstream callback claims do not uniquely own source BL")
    result = {
        "artifact": UPSTREAM.as_posix(),
        "artifact_schema": manifest.get("artifact_schema"),
        "manifest_sha256": _sha(manifest_raw),
        "payload_sha256": _sha(payload_raw),
        "verifier": "tools/verify_rom_story_state_callback_cfg.py",
        "verifier_report_schema": report.get("schema"),
        "verified": True,
        "required_source_range": list(SOURCE_RANGE),
        "required_primary_class": promotion["primary_class"],
        "covering_claim_ids": sorted(owner_ids),
    }
    _UPSTREAM_CACHE = (cache_key, result)
    return dict(result)


def _decode_cfg(rom: bytes) -> dict[str, Any]:
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    rows = list(engine.disasm(rom[CODE_RANGE[0] : CODE_RANGE[1]], ROM_BASE + CODE_RANGE[0]))
    if not rows or sum(row.size for row in rows) != CODE_RANGE[1] - CODE_RANGE[0]:
        raise ValueError("target code range no longer decodes exactly")
    instructions: list[dict[str, Any]] = []
    opaque: list[list[int]] = []
    local: list[list[Any]] = []
    bindings: list[tuple[int, int, int]] = []
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
        flow = _branch(rom, offset)
        if flow is not None:
            kind, target = flow
            if kind == "bl":
                opaque.append([offset, target])
            else:
                local.append([offset, target, kind])
        if row.size == 2:
            halfword = struct.unpack_from("<H", rom, offset)[0]
            if halfword & 0xF800 == 0x4800:
                target = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
                bindings.append((offset, target, struct.unpack_from("<I", rom, target)[0]))
    if len(rows) != 78 or len(opaque) != 14 or local:
        raise ValueError("target-local CFG denominator changed")
    if tuple(bindings) != EXPECTED_BINDINGS:
        raise ValueError("target literal binding denominator changed")
    if rom[0x08C57C:0x08C584] != bytes.fromhex("06b010bc01bc0047"):
        raise ValueError("strict pop-r0/bx-r0 return changed")
    if rom[0x08C5A8:0x08C5AA] != bytes.fromhex("10b5"):
        raise ValueError("next function entry boundary changed")
    return {
        "root": ROOT,
        "code_range": list(CODE_RANGE),
        "code_sha256": _sha(rom[CODE_RANGE[0] : CODE_RANGE[1]]),
        "instruction_count": len(rows),
        "instruction_bytes": sum(row.size for row in rows),
        "basic_block_count": len(opaque) + 1,
        "opaque_external_call_count": len(opaque),
        "opaque_external_calls": opaque,
        "local_branch_count": len(local),
        "local_edges": local,
        "hole_count": 0,
        "frontier_count": 0,
        "strict_return": {
            "instruction_offsets": [0x08C57C, 0x08C57E, 0x08C580, 0x08C582],
            "raw_hex": rom[0x08C57C:0x08C584].hex(),
            "proof": "pop_r0_then_bx_r0",
        },
        "literal_range": list(LITERAL_RANGE),
        "literal_sha256": _sha(rom[LITERAL_RANGE[0] : LITERAL_RANGE[1]]),
        "literal_bindings": [[source, target, f"0x{value:08X}"] for source, target, value in bindings],
        "next_entry_excluded": [0x08C5A8, rom[0x08C5A8:0x08C5AA].hex()],
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
    for start, end in (CODE_RANGE, LITERAL_RANGE, REMAINING_RANGE):
        cursor = start
        while cursor < end:
            index = bisect.bisect_right(starts, cursor) - 1
            if index < 0:
                raise ValueError("coverage segment lookup failed")
            row = segments[index]
            if not row["range"][0] <= cursor < row["range"][1] or row.get("primary_class") != "unknown":
                raise ValueError("target packet escaped canonical unknown")
            cursor = min(end, row["range"][1])


def build_payload(root: Path, rom_override: bytes | None = None) -> dict[str, Any]:
    root = root.resolve(strict=True)
    rom = _safe_file(root, ROM_PATH).read_bytes() if rom_override is None else rom_override
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("fixed ROM identity changed")
    dependency = _upstream_dependency(root)
    direct = _target_matches(rom, ROOT)
    if direct != [[SOURCE_RANGE[0], ROOT, "bl"]]:
        raise ValueError("0x0808C4CC direct producer denominator changed")
    thumb_pointers = _occurrences(rom, ROM_BASE + ROOT + 1)
    even_words = _occurrences(rom, ROM_BASE + ROOT)
    if thumb_pointers or even_words:
        raise ValueError("0x0808C4CC pointer denominator changed")
    coverage, segments, starts = _coverage(root)
    _assert_unknown(segments, starts)
    cfg = _decode_cfg(rom)
    claims = []
    for kind, (start, end) in (
        ("reachable_thumb_code", CODE_RANGE),
        ("consumed_literal_words", LITERAL_RANGE),
    ):
        claims.append(
            {
                "id": f"story-state-entry-c4cc-{kind}-{start:06x}",
                "kind": kind,
                "range": [start, end],
                "bytes_sha256": _sha(rom[start:end]),
                "baseline_unknown_only": True,
            }
        )
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": _sha(rom)},
        "upstream_dependency": dependency,
        "producer_denominator": {
            "direct": direct,
            "thumb_pointer_occurrences": thumb_pointers,
            "even_u32_occurrences": even_words,
        },
        "target_local_cfg": cfg,
        "coverage_baseline": {
            "historical_reference": {"path": COVERAGE_PATH.as_posix(), "sha256": COVERAGE_SHA256},
            "state": "baseline_unknown",
            "classified_bytes": coverage["summary"]["classified_bytes"],
            "unknown_bytes": coverage["summary"]["unknown_bytes"],
            "observed_during_artifact_build": True,
            "replay_mode": "historical_build_receipt_replay",
            "live_coverage_verified_on_replay": False,
        },
        "promotion": {
            "primary_class": "armv4t_story_state_entry_cfg",
            "claim_kind": "story_state_entry_c4cc_exact_bytes",
            "code_ranges": [list(CODE_RANGE)],
            "literal_ranges": [list(LITERAL_RANGE)],
            "code_bytes": 184,
            "literal_bytes": 36,
            "promotion_bytes": 220,
            "remaining_unknown_range": list(REMAINING_RANGE),
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


def _output_path(root: Path, output: Path) -> Path:
    lexical = (output if output.is_absolute() else root / output).absolute()
    resolved = lexical.resolve(strict=False)
    allowed = (root / EXPERIMENT).resolve(strict=True)
    official = (root / OFFICIAL).resolve(strict=False)
    if resolved != lexical or lexical.is_symlink() or not (
        resolved.is_relative_to(allowed) or resolved == official
    ):
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
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".story-entry-c4cc-") as raw:
        stage = Path(raw) / output.name
        stage.mkdir()
        (stage / PAYLOAD_NAME).write_bytes(payload_raw)
        (stage / MANIFEST_NAME).write_bytes(_canonical(manifest))
        from tools.verify_rom_story_state_entry_c4cc import verify_artifact

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
