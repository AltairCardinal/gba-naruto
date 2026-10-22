#!/usr/bin/env python3
"""Independently verify and accept the bounded CGB helper CFG packet."""

from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import struct
import subprocess
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = Path("build/experiments/active/cgb-helper-contract/codex-r1-20260829")
OUTPUT_EXPERIMENT = Path("build/experiments/active/cgb-helper-bounded-cfg-20260829")
CANONICAL_TARGET = Path("artifacts/rom-cgb-helper-bounded-cfg-v1")
SOURCE_CANDIDATE = OUTPUT_EXPERIMENT / "candidate-r2"
CONTRACT_PATH = EXPERIMENT / "CONTRACT.json"
CONTRACT_SHA256 = "e1f4d0b840d52b19ee996ee7c0ba18c41511f0c96b37f498f77954a24c9105b7"
SCHEMA = "rom-cgb-helper-bounded-cfg-v1"
VERIFY_SCHEMA = "rom-cgb-helper-bounded-cfg-verification-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "22f8f88ca0929468289b749cb94b4aaa4c47d7a53fa68fe10cb93c9a01816839"
COVERAGE_SIZE = 23152713
COVERAGE_SUMMARY = {"claim_count": 14507, "classified_bytes": 6124601, "segment_count": 16617, "unknown_bytes": 166855}
ARCHIVE_SHA256 = "e345bf5a605d796c1e38a4243b4aefbcb7b8229f70bea13ce40ca044d4edf04b"
ARCHIVE_MANIFEST_SHA256 = "73be947de76ede7948780faba669d74320d2f37d91c95a6bdd99a3c5b02b94c1"
CODE_RANGES = [[636220, 636256], [636260, 636264], [636268, 636274], [636280, 636294], [636300, 636404]]
EXPECTED_CODE_RANGES = CODE_RANGES
EXCLUDED_RANGES = [[636274, 636276], [636294, 636296]]
ROOTS = [636220, 636300]
PROMOTION_RANGES = [
    {"bytes": 36, "range": [636220, 636256], "sha256": "ac01b052dd7ab7f97e74b52e671f1e8bdc2c423caeebeee4c5618c905f29bca1"},
    {"bytes": 4, "range": [636256, 636260], "sha256": "22f7252bc2b8f2444cb6c59642ab9d902a8cac23e4c27e48623e8513b28ddeee"},
    {"bytes": 4, "range": [636260, 636264], "sha256": "df358c07b036a56dcc30711ce42e97371d6e3f08f6a1e8027e0beb713f85c56d"},
    {"bytes": 4, "range": [636264, 636268], "sha256": "60e226a6318302bbe245079f99e6724c5cd2431c689d5ae9992b08bdcc592a04"},
    {"bytes": 6, "range": [636268, 636274], "sha256": "30c6c9fcb611330459336092dfdf9059b742dabc6d5f773ae67f501c1caadc3f"},
    {"bytes": 4, "range": [636276, 636280], "sha256": "d0455d972504810561aaa6b9cc70d69a9ad49abc84a3df38789afdd8eb9236eb"},
    {"bytes": 14, "range": [636280, 636294], "sha256": "6531a1df4bcdc95692713b4c346c135e75339afb73d35dd2934ff15e9f606d99"},
    {"bytes": 4, "range": [636296, 636300], "sha256": "bd56e77404afec2e1cb1d293f4b56e5188b6e7c5d7aaf39d58dbd1de177f28fd"},
    {"bytes": 104, "range": [636300, 636404], "sha256": "584762a3caa5fe9d71f2afd7fe58f2e5a8d2ef8efb2c4d68df84a621b84c9b88"},
]
UPSTREAM_PATHS = {"manifest": Path("artifacts/rom-m4a-initializer-chain-v1/manifest.json"), "payload": Path("artifacts/rom-m4a-initializer-chain-v1/rom-m4a-initializer-chain.json")}
UPSTREAM = {"m4a_initializer_chain": {"manifest_sha256": "9b9b9f2f49a1ee8224703ca47b73dc608d75ba83d2be44564e24873c44237c9c", "payload_sha256": "7f019b01e800a3dd769463cbea907049429b1cad416dc17ed8719a561837babd"}}
EXPECTED_HASHES = {
    "semantic_instruction_vector_sha256": "66df11b0f24f38a6aa9aa3b202c5b07b949ff98631ddb3f8c97f46d602d8f5db",
    "block_range_vector_sha256": "421415d1f0c255dc581a1076ec73441ef031ed7fd623ce6d8e224b2e51ab55ce",
    "edge_vector_sha256": "7c080763f41c5afb6556bc4dcdf44ccd884a96ac8b14d8270aa68f77c36a2978",
}
PRODUCER_FORMS = ["thumb_bl", "thumb_b", "thumb_b_conditional", "arm_b", "arm_bl", "bytewise_u32_entry", "bytewise_u32_thumb_pointer"]
_PRODUCER_CACHE: dict[str, dict[str, Any]] = {}

_SEMANTIC_TEXT = """
636220|lsls|r0, r0, #0x18
636222|lsrs|r0, r0, #0x18
636224|adds|r1, r0, #0
636226|cmp|r0, #2
636228|beq|#0x809b564
636230|cmp|r0, #2
636232|bgt|#0x809b550
636234|cmp|r0, #1
636236|beq|#0x809b556
636238|b|#0x809b578
636240|cmp|r1, #3
636242|beq|#0x809b56c
636244|b|#0x809b578
636246|ldr|r1, [pc, #8]
636248|movs|r0, #8
636250|strb|r0, [r1]
636252|adds|r1, #2
636254|b|#0x809b580
636260|ldr|r1, [pc, #0]
636262|b|#0x809b57a
636268|ldr|r1, [pc, #4]
636270|movs|r0, #0
636272|b|#0x809b582
636280|ldr|r1, [pc, #0xc]
636282|movs|r0, #8
636284|strb|r0, [r1]
636286|adds|r1, #4
636288|movs|r0, #0x80
636290|strb|r0, [r1]
636292|bx|lr
636300|push|{r4, lr}
636302|adds|r1, r0, #0
636304|ldrb|r0, [r1, #2]
636306|lsls|r2, r0, #0x18
636308|lsrs|r4, r2, #0x18
636310|ldrb|r3, [r1, #3]
636312|lsls|r0, r3, #0x18
636314|lsrs|r3, r0, #0x18
636316|cmp|r4, r3
636318|blo|#0x809b5ac
636320|lsrs|r0, r2, #0x19
636322|cmp|r0, r3
636324|blo|#0x809b5b8
636326|movs|r0, #0xf
636328|strb|r0, [r1, #0x1b]
636330|b|#0x809b5c6
636332|lsrs|r0, r0, #0x19
636334|cmp|r0, r4
636336|blo|#0x809b5b8
636338|movs|r0, #0xf0
636340|strb|r0, [r1, #0x1b]
636342|b|#0x809b5c6
636344|movs|r0, #0xff
636346|strb|r0, [r1, #0x1b]
636348|ldrb|r2, [r1, #3]
636350|ldrb|r3, [r1, #2]
636352|adds|r0, r2, r3
636354|lsrs|r0, r0, #4
636356|b|#0x809b5d6
636358|ldrb|r2, [r1, #3]
636360|ldrb|r3, [r1, #2]
636362|adds|r0, r2, r3
636364|lsrs|r0, r0, #4
636366|strb|r0, [r1, #0xa]
636368|cmp|r0, #0xf
636370|bls|#0x809b5d8
636372|movs|r0, #0xf
636374|strb|r0, [r1, #0xa]
636376|ldrb|r2, [r1, #6]
636378|ldrb|r3, [r1, #0xa]
636380|adds|r0, r2, #0
636382|muls|r0, r3, r0
636384|adds|r0, #0xf
636386|asrs|r0, r0, #4
636388|strb|r0, [r1, #0x19]
636390|ldrb|r0, [r1, #0x1c]
636392|ldrb|r2, [r1, #0x1b]
636394|ands|r0, r2
636396|strb|r0, [r1, #0x1b]
636398|pop|{r4}
636400|pop|{r0}
636402|bx|r0
""".strip()
SEMANTICS = {int(line.split("|", 2)[0]): tuple(line.split("|", 2)[1:]) for line in _SEMANTIC_TEXT.splitlines()}


def _sha(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()
def _canonical(value: Any) -> bytes: return json.dumps(value, separators=(",", ":"), sort_keys=False).encode()
def _pretty(value: Any) -> bytes: return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _safe_file(root: Path, relative: Path | str) -> Path:
    root = root.resolve(); value = Path(relative)
    if value.is_absolute():
        try: value = value.relative_to(root)
        except ValueError as exc: raise ValueError("path escapes repository") from exc
    if ".." in value.parts: raise ValueError("parent escape")
    current = root
    for part in value.parts:
        current /= part
        if current.is_symlink(): raise ValueError("symlink component")
    try: current.resolve().relative_to(root)
    except ValueError as exc: raise ValueError("path escapes repository") from exc
    return current


def _contract(root: Path) -> dict[str, Any]:
    raw = _safe_file(root, CONTRACT_PATH).read_bytes()
    if _sha(raw) != CONTRACT_SHA256: raise ValueError("contract identity mismatch")
    return json.loads(raw)


def _validate_rom(rom: bytes) -> None:
    if len(rom) != 6291456 or _sha(rom) != ROM_SHA256: raise ValueError("ROM identity mismatch")


def _check_promotion(rom: bytes) -> bytes:
    pieces = []
    for row in PROMOTION_RANGES:
        start, end = row["range"]; raw = rom[start:end]
        if len(raw) != row["bytes"] or _sha(raw) != row["sha256"]: raise ValueError(f"promotion range identity mismatch at {start}")
        pieces.append(raw)
    bundle = b"".join(pieces)
    if _sha(bundle) != "87c62bbe5f0e9d25ee5b11398ecdd3ed5b41782d4873871205f71c1122a4c1dc": raise ValueError("promotion bundle mismatch")
    return bundle


def _raw_flow(rom: bytes, offset: int) -> list[dict[str, Any]]:
    h = struct.unpack_from("<H", rom, offset)[0]
    if h & 0xF000 == 0xD000 and ((h >> 8) & 15) < 14:
        d = h & 255
        if d & 128: d -= 256
        return [{"kind": "branch", "target_offset": offset + 4 + d * 2}, {"kind": "fallthrough", "target_offset": offset + 2}]
    if h & 0xF800 == 0xE000:
        d = h & 0x7FF
        if d & 0x400: d -= 0x800
        return [{"kind": "branch", "target_offset": offset + 4 + d * 2}]
    if h & 0xFF87 == 0x4700: return []
    return [{"kind": "fallthrough", "target_offset": offset + 2}]


def _raw_cfg(rom: bytes) -> tuple[list[int], dict[int, list[dict[str, Any]]]]:
    valid = {offset for start, end in CODE_RANGES for offset in range(start, end, 2)}
    seen: set[int] = set(); pending = list(ROOTS); flows = {}
    while pending:
        offset = pending.pop()
        if offset in seen: continue
        if offset not in valid: raise ValueError("CFG target instruction-middle/gap escape")
        seen.add(offset); flows[offset] = _raw_flow(rom, offset); pending.extend(edge["target_offset"] for edge in flows[offset])
    if seen != valid: raise ValueError("CFG frontier/unreachable mismatch")
    return sorted(seen), flows


def _make_blocks(offsets: list[int], flows: dict[int, list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seen = set(offsets); leaders = set(ROOTS)
    for offset in offsets:
        leaders.update(edge["target_offset"] for edge in flows[offset] if edge["kind"] == "branch")
        if len(flows[offset]) == 2: leaders.add(offset + 2)
    ranges = []
    for start in sorted(leaders):
        if start not in seen: continue
        terminal = start
        while True:
            following = terminal + 2
            if not flows[terminal] or any(edge["kind"] == "branch" for edge in flows[terminal]) or following in leaders or following not in seen: break
            terminal = following
        ranges.append([start, terminal + 2])
    blocks = []; edges = []
    for start, end in ranges:
        terminal = end - 2
        successors = [{"source_instruction_offset": terminal, "target_offset": edge["target_offset"], "kind": edge["kind"]} for edge in flows[terminal]]
        blocks.append({"id": f"block-{start:06x}", "range": [start, end], "instruction_count": (end - start) // 2, "successors": successors}); edges.extend(successors)
    edges.sort(key=lambda row: (row["source_instruction_offset"], 0 if row["kind"] == "branch" else 1))
    return blocks, edges


def rebuild_cfg_from_rom(rom: bytes) -> dict[str, Any]:
    _check_promotion(rom)
    offsets, flows = _raw_cfg(rom); blocks, edges = _make_blocks(offsets, flows)
    terminal_sources = {row["source_instruction_offset"] for row in edges}
    instructions = []
    semantic = []
    for offset in offsets:
        mnemonic, op_str = SEMANTICS[offset]
        instructions.append({"offset": offset, "size": 2, "raw_hex": rom[offset:offset + 2].hex(), "mnemonic": mnemonic, "op_str": op_str, "successors": flows[offset] if offset in terminal_sources else []})
        semantic.append([offset, 2, mnemonic, op_str])
    cfg = {"instruction_count": len(instructions), "code_bytes": 164, "block_count": len(blocks), "internal_edge_count": len(edges), "external_edge_count": 0,
           "structured_return_count": 2, "frontier_count": 0, "budget_exhausted": False, "code_ranges": CODE_RANGES, "return_offsets": [636292, 636402], "frontiers": [],
           "instructions": instructions, "blocks": blocks, "block_edges": edges, "returns": [{"offset": 636292, "register": "lr"}, {"offset": 636402, "register": "r0"}],
           "semantic_instruction_vector_sha256": _sha(_canonical(semantic)), "block_range_vector_sha256": _sha(_canonical([row["range"] for row in blocks])),
           "edge_vector_sha256": _sha(_canonical([[row["source_instruction_offset"], row["target_offset"], row["kind"]] for row in edges]))}
    if (len(instructions), len(blocks), len(edges)) != (82, 23, 29) or any(cfg[key] != value for key, value in EXPECTED_HASHES.items()): raise ValueError("independent CFG denominator/vector mismatch")
    return cfg


_rebuild_cfg = rebuild_cfg_from_rom


def _coverage_from_file(root: Path) -> tuple[dict[str, Any], bytes]:
    raw = _safe_file(root, COVERAGE_PATH).read_bytes()
    if len(raw) != COVERAGE_SIZE or _sha(raw) != COVERAGE_SHA256: raise ValueError("live coverage mismatch")
    return json.loads(raw), raw


def _coverage_from_artifact(root: Path, artifact: Path | str) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    directory = _safe_file(root, artifact)
    manifest_raw = _safe_file(root, directory / "manifest.json").read_bytes(); archive_raw = _safe_file(root, directory / "rom-byte-coverage.json.gz").read_bytes()
    if _sha(manifest_raw) != ARCHIVE_MANIFEST_SHA256 or _sha(archive_raw) != ARCHIVE_SHA256: raise ValueError("precoverage outer manifest/archive mismatch")
    manifest = json.loads(manifest_raw)
    if manifest.get("schema") != "rom-byte-coverage-prepromotion-baseline-v1" or manifest.get("artifact_status") != "accepted" or manifest.get("recovery", {}).get("kind") != "direct-frozen-prepromotion-snapshot": raise ValueError("precoverage recovery/schema/status mismatch")
    archive = manifest.get("coverage", {}).get("archive", {}); meta = manifest.get("coverage", {}).get("raw", {})
    if archive != {"compression": "gzip", "file": "rom-byte-coverage.json.gz", "sha256": ARCHIVE_SHA256, "size": len(archive_raw)}: raise ValueError("precoverage archive metadata mismatch")
    if meta != {"canonical_json": True, "schema": "rom-byte-coverage-v1", "sha256": COVERAGE_SHA256, "size": COVERAGE_SIZE, "summary": COVERAGE_SUMMARY}: raise ValueError("precoverage raw identity mismatch")
    try: raw = gzip.decompress(archive_raw)
    except Exception as exc: raise ValueError("precoverage gzip invalid") from exc
    if len(raw) != COVERAGE_SIZE or _sha(raw) != COVERAGE_SHA256: raise ValueError("precoverage decompressed identity mismatch")
    return json.loads(raw), raw, {"artifact": directory.relative_to(root.resolve()).as_posix()}


def _covering(coverage: dict[str, Any], interval: list[int]) -> list[dict[str, Any]]:
    start, end = interval; rows = sorted([row for row in coverage.get("segments", []) if row["range"][0] < end and start < row["range"][1]], key=lambda row: row["range"][0]); cursor = start
    for row in rows:
        left, right = row["range"]
        if left > cursor or right <= cursor: raise ValueError("coverage overlap/duplicate")
        cursor = max(cursor, right)
    if cursor < end: raise ValueError("coverage whole-range missing")
    return rows


def _analyze_coverage(coverage: Any) -> None:
    if not isinstance(coverage, dict): raise ValueError("coverage non-object")
    summary = coverage.get("summary", {})
    if coverage.get("schema") != "rom-byte-coverage-v1" or any(summary.get(key) != value for key, value in COVERAGE_SUMMARY.items()): raise ValueError("coverage summary mismatch")
    contract = _contract(PROJECT_ROOT)
    for interval in [row["range"] for row in contract["promotion"]["ranges"]] + EXCLUDED_RANGES:
        if any(row.get("primary_class") != "unknown" or row.get("primary_claim_ids") != [] for row in _covering(coverage, interval)): raise ValueError("coverage promotion/gap owner mismatch")
    if any(row.get("primary_class") != "m4a_initializer_chain_consumed_literal_bytes" or row.get("primary_claim_ids") != ["psg-initializer-literals-09adc0"] for row in _covering(coverage, [634368, 634372])): raise ValueError("initializer owner mismatch")


def _validate_upstream(root: Path) -> dict[str, Any]:
    manifest = _safe_file(root, UPSTREAM_PATHS["manifest"]).read_bytes(); payload_raw = _safe_file(root, UPSTREAM_PATHS["payload"]).read_bytes()
    if _sha(manifest) != UPSTREAM["m4a_initializer_chain"]["manifest_sha256"] or _sha(payload_raw) != UPSTREAM["m4a_initializer_chain"]["payload_sha256"]: raise ValueError("upstream identity mismatch")
    payload = json.loads(payload_raw); owners = [row for row in payload.get("coverage_claims", []) if row.get("id") == "psg-initializer-literals-09adc0"]
    if len(owners) != 1 or owners[0].get("range") != [634304, 634384] or owners[0].get("semantic_class") != "m4a_initializer_chain_consumed_literal_bytes": raise ValueError("upstream owner mismatch")
    instructions = {row.get("offset"): row for row in payload.get("cfg", {}).get("instructions", [])}
    for offset, expected in {
        634224: {"raw_hex": "2348", "mnemonic": "ldr", "op_str": "r0, [pc, #0x8c]"},
        634226: {"raw_hex": "e062", "mnemonic": "str", "op_str": "r0, [r4, #0x2c]"},
    }.items():
        row = instructions.get(offset)
        if not isinstance(row, dict) or any(row.get(key) != value for key, value in expected.items()): raise ValueError("upstream initializer semantic mismatch")
    return UPSTREAM


def decode_initializer_semantics(rom: bytes) -> dict[str, Any]:
    load_offset = 634224; store_offset = 634226
    load = struct.unpack_from("<H", rom, load_offset)[0]
    if load & 0xF800 != 0x4800: raise ValueError("initializer load semantic mismatch")
    rt = (load >> 8) & 7; pc_base = (load_offset + 4) & ~3; literal_offset = pc_base + (load & 0xFF) * 4
    if literal_offset + 4 > len(rom): raise ValueError("initializer literal semantic escape")
    value = struct.unpack_from("<I", rom, literal_offset)[0]
    store = struct.unpack_from("<H", rom, store_offset)[0]
    if store & 0xF800 != 0x6000: raise ValueError("initializer store semantic mismatch")
    return {"load": {"offset": load_offset, "rt": f"r{rt}", "pc_base": pc_base, "literal_offset": literal_offset, "value": value},
            "store": {"offset": store_offset, "source": f"r{store & 7}", "base": f"r{(store >> 3) & 7}", "width": "word", "field_offset": ((store >> 6) & 31) * 4}}


def _initializer(rom: bytes, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    if decode_initializer_semantics(rom) != {"load": {"offset": 634224, "rt": "r0", "pc_base": 634228, "literal_offset": 634368, "value": 0x0809B53D},
                                             "store": {"offset": 634226, "source": "r0", "base": "r4", "width": "word", "field_offset": 44}}:
        raise ValueError("initializer raw semantic binding mismatch")
    _validate_upstream(root)
    occurrences = [i for i in range(len(rom) - 3) if rom[i:i + 4] == bytes.fromhex("3db50908")]
    if occurrences != [634368]: raise ValueError("initializer occurrence mismatch")
    return {"destination_address": 50361676, "entry_pointer": 134853949, "entry_pointer_occurrences": [634368], "entry_pointer_root_offset": 636220, "field_offset": 44,
            "load_instruction": {"offset": 634224, "raw_hex": "2348"}, "pointer_literal": {"range": [634368, 634372], "raw_hex": "3db50908", "sha256": "1a648773d0593fdc9669da7e1ca0bb40589edbdddcfdb0dda47230d8a3db5581"},
            "store_instruction": {"offset": 634226, "raw_hex": "e062"}, "structure_base": 50361632}


def _scan_producers(rom: bytes) -> dict[str, Any]:
    identity = _sha(rom)
    if identity in _PRODUCER_CACHE: return json.loads(json.dumps(_PRODUCER_CACHE[identity]))
    targets = {636220: {name: [] for name in PRODUCER_FORMS}, 636300: {name: [] for name in PRODUCER_FORMS}}; size = len(rom)
    for offset in range(0, size - 1, 2):
        h = struct.unpack_from("<H", rom, offset)[0]
        if h & 0xF800 == 0xE000:
            d = h & 0x7FF
            if d & 0x400: d -= 0x800
            target = offset + 4 + d * 2
            if target in targets: targets[target]["thumb_b"].append(offset)
        if h & 0xF000 == 0xD000 and ((h >> 8) & 15) < 14:
            d = h & 255
            if d & 128: d -= 256
            target = offset + 4 + d * 2
            if target in targets: targets[target]["thumb_b_conditional"].append(offset)
        if offset + 3 < size:
            h2 = struct.unpack_from("<H", rom, offset + 2)[0]
            if h & 0xF800 == 0xF000 and h2 & 0xF800 == 0xF800:
                hi = h & 0x7FF
                if hi & 0x400: hi -= 0x800
                target = offset + 4 + (hi << 12) + ((h2 & 0x7FF) << 1)
                if target in targets: targets[target]["thumb_bl"].append(offset)
    for offset in range(0, size - 3, 4):
        word = struct.unpack_from("<I", rom, offset)[0]; op = word & 0xFF000000
        if op in (0xEA000000, 0xEB000000):
            d = word & 0xFFFFFF
            if d & 0x800000: d -= 0x1000000
            target = offset + 8 + d * 4
            if target in targets: targets[target]["arm_bl" if op == 0xEB000000 else "arm_b"].append(offset)
    values = {0x08000000 + target: (target, "bytewise_u32_entry") for target in targets}; values.update({0x08000001 + target: (target, "bytewise_u32_thumb_pointer") for target in targets})
    for offset in range(size - 3):
        item = values.get(struct.unpack_from("<I", rom, offset)[0])
        if item: targets[item[0]][item[1]].append(offset)
    result = {"forms": PRODUCER_FORMS, "scan_range": [0, size], "targets": [{"target_file_offset": target, "forms": targets[target]} for target in sorted(targets)], "vector_sha256": "536020c92992d0ea9387b79d4ef15f9aa9e09b3f82c100b8c396fe1af98c4ab1"}
    if result != _contract(PROJECT_ROOT)["producer_denominator"]: raise ValueError("producer denominator mismatch")
    _PRODUCER_CACHE[identity] = result; return result


def independent_rebuild(root: Path | str, rom: bytes, *, coverage_baseline_artifact: Path | str | None = None) -> dict[str, Any]:
    root = Path(root).resolve(); contract = _contract(root); _validate_rom(rom); bundle = _check_promotion(rom)
    if EXPECTED_CODE_RANGES != CODE_RANGES: raise ValueError("expected code ranges drift")
    cfg = _rebuild_cfg(rom); cfg["roots"] = contract["cfg"]["roots"]; cfg["packed_code_sha256"] = contract["cfg"]["packed_code_sha256"]; cfg["vector_encoding"] = contract["cfg"]["vector_encoding"]
    upstream = _validate_upstream(root)
    if coverage_baseline_artifact is None:
        coverage, raw = _coverage_from_file(root); source = {"path": COVERAGE_PATH.as_posix(), "kind": "live"}; immutable = contract["coverage_baseline"]["immutable_artifact"]
    else:
        coverage, raw, source = _coverage_from_artifact(root, coverage_baseline_artifact); immutable = {"path": source["artifact"], "archive_sha256": ARCHIVE_SHA256, "manifest_sha256": ARCHIVE_MANIFEST_SHA256}
    _analyze_coverage(coverage)
    for row in contract["literal_projection"]["bindings"]:
        start, _ = row["range"]; h = struct.unpack_from("<H", rom, row["consumer_offset"])[0]
        if ((row["consumer_offset"] + 4) & ~3) + (h & 255) * 4 != start or rom[row["consumer_offset"]:row["consumer_offset"] + 2].hex() != row["load_raw_hex"] or struct.unpack_from("<I", rom, start)[0] != row["value"]: raise ValueError("literal binding mismatch")
    producer = _scan_producers(rom)
    initializer = _initializer(rom, root)
    payload = {"schema": SCHEMA, "rom": contract["base_rom"], "envelope": contract["envelope"], "roots": contract["cfg"]["roots"], "cfg": cfg,
               "promotion": contract["promotion"], "promotion_ranges": contract["promotion"]["ranges"], "literal_projection": contract["literal_projection"],
               "excluded_ranges": [{**row, "promoted": False, "semantic_class": "unknown"} for row in contract["excluded_ranges"]], "initializer_binding": initializer,
               "producer_denominator": producer, "coverage_baseline": {"path": contract["coverage_baseline"]["path"], "sha256": _sha(raw), "size": len(raw), "summary": COVERAGE_SUMMARY, "immutable_artifact": immutable},
               "coverage_baseline_source": source, "coverage_projection": contract["coverage_projection"], "upstream_receipts": upstream, "scope": contract["scope"]}
    return {"schema": VERIFY_SCHEMA, "verified": True, "bundle_sha256": _sha(bundle), "bundle_size": len(bundle), "payload": payload}


def _read_member(directory_fd: int, name: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(name, flags, dir_fd=directory_fd)
    except OSError as exc:
        raise ValueError(f"artifact member symlink or open failure: {name}") from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode): raise ValueError(f"artifact member is not regular: {name}")
        chunks = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk: break
            chunks.append(chunk)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns): raise ValueError(f"artifact member identity changed: {name}")
        return b"".join(chunks)
    finally:
        os.close(fd)


def _artifact_files(directory: Path) -> tuple[dict[str, Any], dict[str, Any], bytes, dict[str, bytes]]:
    expected = {"manifest.json", "rom-cgb-helper-bounded-cfg.json", "rom-cgb-helper-bounded-cfg.bin"}
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    try: directory_fd = os.open(directory, flags)
    except OSError as exc: raise ValueError("artifact directory symlink or open failure") from exc
    try:
        if set(os.listdir(directory_fd)) != expected: raise ValueError("artifact file set mismatch")
        files = {name: _read_member(directory_fd, name) for name in expected}
    finally: os.close(directory_fd)
    manifest_raw = files["manifest.json"]; payload_raw = files["rom-cgb-helper-bounded-cfg.json"]; bundle = files["rom-cgb-helper-bounded-cfg.bin"]
    manifest = json.loads(manifest_raw); payload = json.loads(payload_raw)
    if manifest_raw != _pretty(manifest) or payload_raw != _pretty(payload): raise ValueError("canonical JSON required")
    for name, raw in (("rom-cgb-helper-bounded-cfg.json", payload_raw), ("rom-cgb-helper-bounded-cfg.bin", bundle)):
        if manifest.get("files", {}).get(name) != {"sha256": _sha(raw), "size": len(raw)}: raise ValueError("manifest file identity mismatch")
    if manifest.get("schema") != "git-artifact-promotion-v1" or manifest.get("artifact_schema") != SCHEMA or manifest.get("contract_sha256") != CONTRACT_SHA256: raise ValueError("manifest schema/contract mismatch")
    return manifest, payload, bundle, files


def _candidate_identity(files: dict[str, bytes]) -> dict[str, Any]:
    return {"artifact_status": "candidate", "manifest_sha256": _sha(files["manifest.json"]), "payload_sha256": _sha(files["rom-cgb-helper-bounded-cfg.json"]), "bundle_sha256": _sha(files["rom-cgb-helper-bounded-cfg.bin"])}


def verify_artifact(root: Path | str, artifact: Path | str, *, allow_candidate: bool = False, coverage_baseline_artifact: Path | str | None = None) -> dict[str, Any]:
    root = Path(root).resolve(); directory = _safe_file(root, artifact)
    if not directory.is_dir(): raise ValueError("artifact directory missing")
    manifest, payload, bundle, files = _artifact_files(directory); status = manifest.get("artifact_status")
    if status == "candidate" and not allow_candidate: raise ValueError("candidate requires explicit opt-in")
    if status not in ({"candidate", "accepted"} if allow_candidate else {"accepted"}): raise ValueError("artifact status invalid")
    base_keys = {"schema", "artifact_schema", "artifact_status", "contract_sha256", "files"}
    expected_keys = base_keys if status == "candidate" else base_keys | {"acceptance", "verifier", "verification"}
    if set(manifest) != expected_keys:
        if status == "accepted": raise ValueError("accepted artifact acceptance receipt manifest keys changed")
        raise ValueError("manifest key schema changed")
    source = payload.get("coverage_baseline_source", {})
    embedded = None if source.get("kind") == "live" else source.get("artifact")
    if coverage_baseline_artifact is not None and str(coverage_baseline_artifact) != str(embedded): raise ValueError("external coverage conflicts with embedded coverage")
    rom = _safe_file(root, ROM_PATH).read_bytes()
    expected = independent_rebuild(root, rom, coverage_baseline_artifact=embedded)
    expected_bundle = b"".join(rom[start:end] for start, end in [row["range"] for row in PROMOTION_RANGES])
    if payload != expected["payload"] or bundle != expected_bundle: raise ValueError("artifact differs from independent raw rebuild")
    if status == "accepted":
        candidate_manifest = {key: value for key, value in manifest.items() if key in base_keys}; candidate_manifest["artifact_status"] = "candidate"
        source_identity = _candidate_identity({**files, "manifest.json": _pretty(candidate_manifest)})
        artifact_relative = directory.relative_to(root).as_posix()
        acceptance = manifest.get("acceptance")
        if not isinstance(acceptance, dict): raise ValueError("accepted artifact acceptance receipt missing")
        source_candidate = acceptance.get("source_candidate_artifact")
        if not isinstance(source_candidate, str): raise ValueError("accepted artifact source-candidate receipt missing")
        source_path = Path(source_candidate)
        if source_path.is_absolute() or ".." in source_path.parts: raise ValueError("accepted artifact source-candidate path changed")
        canonical_directory = (root / CANONICAL_TARGET).resolve()
        if directory.resolve() == canonical_directory:
            if source_path != SOURCE_CANDIDATE: raise ValueError("canonical source-candidate artifact changed")
        else:
            resolved_source = (root / source_path).resolve()
            allowed_sources = [(root / value).resolve() for value in (EXPERIMENT, OUTPUT_EXPERIMENT)]
            if not any(resolved_source != allowed and resolved_source.is_relative_to(allowed) for allowed in allowed_sources):
                raise ValueError("accepted artifact source-candidate path escapes allowed experiments")
        expected_acceptance = {"kind": "independent-candidate-acceptance", "source_candidate_artifact": source_candidate, "source_candidate_identity": source_identity, "output_artifact": artifact_relative}
        if acceptance != expected_acceptance: raise ValueError("accepted artifact acceptance/source-candidate identity receipt changed")
        verifier_path = Path("tools/verify_rom_cgb_helper_bounded_cfg.py")
        expected_verifier = {"path": verifier_path.as_posix(), "sha256": _sha(_safe_file(root, verifier_path).read_bytes())}
        if manifest.get("verifier") != expected_verifier: raise ValueError("accepted verifier receipt changed")
        expected_verification = {"status": "verified", "contract_ok": True, "schema": VERIFY_SCHEMA, "bundle_sha256": _sha(bundle), "payload_sha256": _sha(files["rom-cgb-helper-bounded-cfg.json"])}
        if manifest.get("verification") != expected_verification: raise ValueError("accepted verification receipt changed")
        identity = source_identity
    else:
        identity = _candidate_identity(files)
    return {"verified": True, "artifact_status": status, "contract_ok": True, "bundle_sha256": expected["bundle_sha256"], "candidate_identity": identity}


def _validate_output(root: Path, output: Path | str) -> tuple[Path, tuple[int, int]]:
    root = root.resolve(); requested = Path(output)
    if ".." in requested.parts: raise ValueError("output parent '..' components are forbidden")
    if not requested.is_absolute(): requested = root / requested
    output = Path(os.path.abspath(requested))
    experiments = [(root / value).resolve() for value in (EXPERIMENT, OUTPUT_EXPERIMENT)]
    canonical = (root / CANONICAL_TARGET).resolve()
    if output != canonical and not any(output != experiment and output.is_relative_to(experiment) for experiment in experiments): raise ValueError("output is not the canonical target or an allowed test experiment path")
    if os.path.lexists(output): raise ValueError("output must be new")
    current = root
    for part in output.relative_to(root).parts[:-1]:
        current /= part
        if current.is_symlink(): raise ValueError("symlink output component")
    try: parent = output.parent.resolve(strict=True)
    except OSError as exc: raise ValueError("output parent must exist") from exc
    output = parent / output.name
    info = parent.stat(); return output, (info.st_dev, info.st_ino)


def _open_parent(directory: Path, identity: tuple[int, int]) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"): flags |= os.O_NOFOLLOW
    try: fd = os.open(directory, flags)
    except OSError as exc: raise ValueError("symlink or invalid output parent") from exc
    info = os.fstat(fd)
    if (info.st_dev, info.st_ino) != identity: os.close(fd); raise ValueError("output parent identity changed")
    return fd


def _write_file_at(directory_fd: int, name: str, raw: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"): flags |= os.O_NOFOLLOW
    fd = os.open(name, flags, 0o644, dir_fd=directory_fd)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    finally: os.close(fd)


def _identity(value: os.stat_result) -> tuple[int, int]: return value.st_dev, value.st_ino


def _remove_tree_at(parent_fd: int, name: str, expected_identity: tuple[int, int] | None = None) -> None:
    try: named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError: return
    if expected_identity is not None and _identity(named) != expected_identity: return
    if not stat.S_ISDIR(named.st_mode) or stat.S_ISLNK(named.st_mode): return
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    try: directory_fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError: return
    opened = _identity(os.fstat(directory_fd))
    if expected_identity is not None and opened != expected_identity: os.close(directory_fd); return
    try:
        for child in os.listdir(directory_fd):
            try: child_stat = os.stat(child, dir_fd=directory_fd, follow_symlinks=False)
            except FileNotFoundError: continue
            if stat.S_ISDIR(child_stat.st_mode) and not stat.S_ISLNK(child_stat.st_mode): _remove_tree_at(directory_fd, child, _identity(child_stat))
            else:
                try: os.unlink(child, dir_fd=directory_fd)
                except FileNotFoundError: pass
    finally: os.close(directory_fd)
    try: current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError: return
    if _identity(current) == opened:
        try: os.rmdir(name, dir_fd=parent_fd)
        except FileNotFoundError: pass


def accept_candidate(root: Path | str, candidate: Path | str, output: Path | str) -> dict[str, Any]:
    root = Path(root).resolve(); candidate_path = _safe_file(root, candidate); target, identity = _validate_output(root, output)
    candidate_resolved = candidate_path.resolve()
    if target == candidate_resolved or candidate_resolved in target.parents or target in candidate_resolved.parents: raise ValueError("candidate/output overlap")
    report = verify_artifact(root, candidate_path, allow_candidate=True)
    manifest, payload, bundle, candidate_files = _artifact_files(candidate_path)
    if _candidate_identity(candidate_files) != report.get("candidate_identity"): raise ValueError("candidate identity changed after verification")
    source_candidate = candidate_path.relative_to(root).as_posix(); output_artifact = target.relative_to(root).as_posix()
    accepted = dict(manifest); accepted["artifact_status"] = "accepted"
    accepted["acceptance"] = {"kind": "independent-candidate-acceptance", "source_candidate_artifact": source_candidate, "source_candidate_identity": report["candidate_identity"], "output_artifact": output_artifact}
    verifier_path = Path("tools/verify_rom_cgb_helper_bounded_cfg.py")
    accepted["verifier"] = {"path": verifier_path.as_posix(), "sha256": _sha(_safe_file(root, verifier_path).read_bytes())}
    accepted["verification"] = {"status": "verified", "contract_ok": True, "schema": VERIFY_SCHEMA, "bundle_sha256": _sha(bundle), "payload_sha256": _sha(candidate_files["rom-cgb-helper-bounded-cfg.json"])}
    files = {"rom-cgb-helper-bounded-cfg.bin": bundle, "rom-cgb-helper-bounded-cfg.json": candidate_files["rom-cgb-helper-bounded-cfg.json"], "manifest.json": _pretty(accepted)}
    parent_fd = _open_parent(target.parent, identity); staging_name = None; published_identity = None
    try:
        try: os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError: pass
        else: raise ValueError("output appeared during acceptance")
        for _ in range(64):
            name = f".{target.name}.{secrets.token_hex(12)}"
            try: os.mkdir(name, 0o700, dir_fd=parent_fd)
            except FileExistsError: continue
            staging_name = name; break
        if staging_name is None: raise ValueError("could not reserve anchored staging")
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        staging_fd = os.open(staging_name, flags, dir_fd=parent_fd)
        try:
            for name, raw in files.items(): _write_file_at(staging_fd, name, raw)
            os.fsync(staging_fd)
        finally: os.close(staging_fd)
        try: os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError: pass
        else: raise ValueError("output appeared during acceptance")
        os.replace(staging_name, target.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd); staging_name = None; os.fsync(parent_fd)
        published_identity = _identity(os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False))
        accepted_report = verify_artifact(root, target)
    except Exception:
        if staging_name is not None: _remove_tree_at(parent_fd, staging_name)
        if published_identity is not None: _remove_tree_at(parent_fd, target.name, published_identity)
        raise
    finally: os.close(parent_fd)
    return {**accepted_report, "artifact_status": "accepted"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("artifact", type=Path)
    group = parser.add_mutually_exclusive_group(); group.add_argument("--allow-candidate", action="store_true"); group.add_argument("--accept-to", type=Path)
    args = parser.parse_args(argv)
    try:
        report = accept_candidate(PROJECT_ROOT, args.artifact, args.accept_to) if args.accept_to is not None else verify_artifact(PROJECT_ROOT, args.artifact, allow_candidate=args.allow_candidate)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema": VERIFY_SCHEMA, "verified": False, "error": str(exc)}, sort_keys=True)); return 1
    print(json.dumps(report, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
