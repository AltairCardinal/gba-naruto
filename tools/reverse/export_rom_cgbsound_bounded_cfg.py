#!/usr/bin/env python3
"""Build the candidate-only bounded CgbSound CFG packet."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import sys
from typing import Any

VENDOR = Path(__file__).resolve().parent / "_vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))
from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = Path("build/experiments/active/cgbsound-contract/codex-r1-20260829")
OUTPUT_EXPERIMENT = Path("build/experiments/active/cgbsound-bounded-cfg-20260829")
CONTRACT_PATH = EXPERIMENT / "CONTRACT.json"
CONTRACT_SHA256 = "12171aa29cd29d14f26dc491e4b0a5bb8ddd3fe6d6daac9f73e732786194561a"
SCHEMA = "rom-cgbsound-bounded-cfg-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "22f8f88ca0929468289b749cb94b4aaa4c47d7a53fa68fe10cb93c9a01816839"
COVERAGE_SIZE = 23152713
COVERAGE_SUMMARY = {"claim_count": 14507, "classified_bytes": 6124601, "segment_count": 16617, "unknown_bytes": 166855}
_FROZEN = json.loads((PROJECT_ROOT / CONTRACT_PATH).read_bytes())
CODE_RANGES = _FROZEN["cfg"]["code_ranges"]
LITERAL_RANGES = _FROZEN["literal_projection"]["ranges"]
EXCLUDED_RANGES = _FROZEN["excluded_ranges"]["ranges"]
ROOTS = [636404]
PROMOTION_RANGES = _FROZEN["promotion"]["ranges"]
EXPECTED_CFG_HASHES = {
    "semantic_instruction_vector_sha256": "07671aee1abdfc89e88571dc3589b56d61fa2763e5b403f2b415ac270f148204",
    "block_range_vector_sha256": "d7ec26b89231c6129cd49ecae68c80b9ffef223e8665c71aa39bfc6a2f843837",
    "edge_vector_sha256": "0380614c5c113eb322a59cff00d41aea0f03e696529d6be18f47d9c6d1bacab6",
}
OPAQUE_CALLS = {636654: 636300, 636882: 636220, 636976: 636300}
UPSTREAM_PATHS = {
    "manifest": Path("artifacts/rom-m4a-initializer-chain-v1/manifest.json"),
    "payload": Path("artifacts/rom-m4a-initializer-chain-v1/rom-m4a-initializer-chain.json"),
}
UPSTREAM = {"m4a_initializer_chain": {"manifest_sha256": "9b9b9f2f49a1ee8224703ca47b73dc608d75ba83d2be44564e24873c44237c9c", "payload_sha256": "7f019b01e800a3dd769463cbea907049429b1cad416dc17ed8719a561837babd"}}
ARCHIVE_SHA256 = "e345bf5a605d796c1e38a4243b4aefbcb7b8229f70bea13ce40ca044d4edf04b"
ARCHIVE_MANIFEST_SHA256 = "73be947de76ede7948780faba669d74320d2f37d91c95a6bdd99a3c5b02b94c1"
RECOVERY_KIND = "direct-frozen-prepromotion-snapshot"
EXPECTED_CODE_RANGES = CODE_RANGES


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=False).encode()


def _pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _contract(root: Path) -> dict[str, Any]:
    raw = _safe_file(root, CONTRACT_PATH).read_bytes()
    if _sha(raw) != CONTRACT_SHA256:
        raise ValueError("contract identity mismatch")
    return json.loads(raw)


def _safe_file(root: Path, relative: Path | str) -> Path:
    root = root.resolve()
    value = Path(relative)
    if value.is_absolute():
        try:
            value = value.relative_to(root)
        except ValueError as exc:
            raise ValueError("path escapes repository") from exc
    if ".." in value.parts:
        raise ValueError("parent path escape")
    current = root
    for part in value.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("symlink component rejected")
    try:
        current.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError("path escapes repository") from exc
    return current


def _validate_rom(rom: bytes) -> None:
    if len(rom) != 6291456 or _sha(rom) != ROM_SHA256:
        raise ValueError("ROM identity mismatch")


def _check_promotion_bytes(rom: bytes) -> bytes:
    pieces = []
    for row in PROMOTION_RANGES:
        start, end = row["range"]
        raw = rom[start:end]
        if len(raw) != row["bytes"] or _sha(raw) != row["sha256"]:
            raise ValueError(f"promotion range identity mismatch at {start}")
        pieces.append(raw)
    bundle = b"".join(pieces)
    if len(bundle) != 1084 or _sha(bundle) != "edebdbe6e5cf5f9cf04fdb93839846f7e37e6516914b77a7517413c88ee9a151":
        raise ValueError("promotion bundle mismatch")
    return bundle


def _raw_flow(rom: bytes, offset: int) -> tuple[int, list[dict[str, Any]]]:
    halfword = struct.unpack_from("<H", rom, offset)[0]
    if halfword & 0xF800 == 0xF000:
        second = struct.unpack_from("<H", rom, offset + 2)[0]
        if second & 0xF800 != 0xF800:
            raise ValueError("invalid Thumb BL second halfword")
        high = halfword & 0x7FF
        if high & 0x400: high -= 0x800
        target = offset + 4 + (high << 12) + ((second & 0x7FF) << 1)
        if offset not in OPAQUE_CALLS or target != OPAQUE_CALLS[offset]:
            raise ValueError("unexpected opaque BL target")
        return 4, [{"kind": "opaque_call", "target_offset": target}, {"kind": "fallthrough", "target_offset": offset + 4}]
    if halfword & 0xF000 == 0xD000 and ((halfword >> 8) & 0xF) < 0xE:
        delta = halfword & 0xFF
        if delta & 0x80:
            delta -= 0x100
        return 2, [{"kind": "branch", "target_offset": offset + 4 + delta * 2}, {"kind": "fallthrough", "target_offset": offset + 2}]
    if halfword & 0xF800 == 0xE000:
        delta = halfword & 0x7FF
        if delta & 0x400:
            delta -= 0x800
        return 2, [{"kind": "branch", "target_offset": offset + 4 + delta * 2}]
    if halfword & 0xFF87 == 0x4700:
        return 2, []
    return 2, [{"kind": "fallthrough", "target_offset": offset + 2}]


def _reachable(rom: bytes, roots: list[int]) -> tuple[list[int], dict[int, list[dict[str, Any]]], dict[int, int]]:
    valid, sizes = set(), {}
    for start, end in CODE_RANGES:
        cursor = start
        while cursor < end:
            size, _ = _raw_flow(rom, cursor)
            valid.add(cursor); sizes[cursor] = size; cursor += size
        if cursor != end: raise ValueError("raw instruction crosses code range")
    seen: set[int] = set()
    pending = list(roots)
    flows: dict[int, list[dict[str, Any]]] = {}
    while pending:
        offset = pending.pop()
        if offset in seen:
            continue
        if offset not in valid:
            raise ValueError(f"CFG target escapes or enters instruction middle/gap: {offset}")
        seen.add(offset)
        _, flows[offset] = _raw_flow(rom, offset)
        pending.extend(edge["target_offset"] for edge in flows[offset] if edge["kind"] != "opaque_call")
    if seen != valid:
        raise ValueError("CFG has unreachable expected instruction or new frontier")
    return sorted(seen), flows, sizes


def _blocks(offsets, flows, sizes):
    seen = set(offsets)
    leaders = set(ROOTS)
    for offset in offsets:
        flow = flows[offset]
        leaders.update(edge["target_offset"] for edge in flow if edge["kind"] == "branch")
        if len(flow) == 2:
            leaders.add(offset + sizes[offset])
    ranges = []
    for start in sorted(leaders):
        if start not in seen:
            continue
        end_instruction = start
        while True:
            flow = flows[end_instruction]
            following = end_instruction + sizes[end_instruction]
            if not flow or any(edge["kind"] in ("branch", "opaque_call") for edge in flow) or following in leaders or following not in seen:
                break
            end_instruction = following
        ranges.append([start, end_instruction + sizes[end_instruction]])
    blocks = []
    edges = []
    for index, interval in enumerate(ranges):
        start, end = interval
        terminal = max(o for o in offsets if start <= o < end)
        successors = []
        for edge in flows[terminal]:
            target = edge["target_offset"]
            row = {"source_instruction_offset": terminal, "target_offset": target, "kind": edge["kind"]}
            successors.append(row)
            edges.append(row)
        blocks.append({"id": f"block-{start:06x}", "range": interval, "instruction_count": sum(start <= o < end for o in offsets), "successors": successors})
    rank = {"branch": 0, "opaque_call": 1, "fallthrough": 2}
    edges.sort(key=lambda row: (row["source_instruction_offset"], rank[row["kind"]]))
    return blocks, edges


def analyze_structured_return(rom: bytes) -> dict[str, Any]:
    expected = _contract(PROJECT_ROOT)["cfg"]["structured_return"]
    raw = rom[637486:637502]
    if raw.hex() != expected["epilogue_raw_hex"] or _sha(raw) != expected["epilogue_sha256"]:
        raise ValueError("structured return epilogue mismatch")
    if struct.unpack_from("<H", rom, 637498)[0] != 0xBC01 or struct.unpack_from("<H", rom, 637500)[0] != 0x4700:
        raise ValueError("POP r0/BX r0 mismatch")
    return expected


def analyze_cfg_from_rom(rom: bytes, *, roots: list[int] | None = None, check_identity: bool = True) -> dict[str, Any]:
    if check_identity: _check_promotion_bytes(rom)
    offsets, flows, sizes = _reachable(rom, roots or ROOTS)
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    semantic_rows = []
    capstone_rows: dict[int, tuple[str, str]] = {}
    for start, end in CODE_RANGES:
        decoded = list(engine.disasm(rom[start:end], 0x08000000 + start))
        if sum(insn.size for insn in decoded) != end - start:
            raise ValueError("Capstone did not consume exact code range")
        for insn in decoded:
            offset = insn.address - 0x08000000
            capstone_rows[offset] = (insn.size, insn.mnemonic, insn.op_str)
    if set(capstone_rows) != set(offsets) or any(capstone_rows[o][0] != sizes[o] for o in offsets):
        raise ValueError("raw/Capstone instruction boundary mismatch")
    instructions = []
    blocks, block_edges = _blocks(offsets, flows, sizes)
    terminal_sources = {row["source_instruction_offset"] for row in block_edges}
    for offset in offsets:
        size, mnemonic, op_str = capstone_rows[offset]
        semantic_rows.append([offset, size, mnemonic, op_str])
        instructions.append({"offset": offset, "size": size, "raw_hex": rom[offset:offset + size].hex(), "mnemonic": mnemonic, "op_str": op_str, "successors": flows[offset] if offset in terminal_sources else []})
    block_vector = [row["range"] for row in blocks]
    edge_vector = [[row["source_instruction_offset"], row["target_offset"], row["kind"]] for row in block_edges]
    cfg = {
        "instruction_count": len(instructions), "code_bytes": sum(row["size"] for row in instructions),
        "block_count": len(blocks), "internal_edge_count": sum(e["kind"] != "opaque_call" for e in block_edges), "external_edge_count": sum(e["kind"] == "opaque_call" for e in block_edges),
        "total_graph_edge_count": len(block_edges), "structured_return_count": 1, "frontier_count": 0, "budget_exhausted": False,
        "code_ranges": CODE_RANGES, "frontiers": [], "structured_return": analyze_structured_return(rom),
        "instructions": instructions, "blocks": blocks, "block_edges": block_edges,
        "semantic_instruction_vector_sha256": _sha(_canonical(semantic_rows)),
        "block_range_vector_sha256": _sha(_canonical(block_vector)),
        "edge_vector_sha256": _sha(_canonical(edge_vector)),
    }
    for key, expected in EXPECTED_CFG_HASHES.items():
        if cfg[key] != expected:
            raise ValueError(f"CFG {key} mismatch")
    if (len(instructions), sum(row["size"] for row in instructions), len(blocks), len(block_edges)) != (501, 1008, 100, 151):
        raise ValueError("CFG denominator mismatch")
    return cfg


_analyze_cfg = analyze_cfg_from_rom


def _coverage_from_file(root: Path) -> tuple[dict[str, Any], bytes]:
    path = _safe_file(root, COVERAGE_PATH)
    raw = path.read_bytes()
    if len(raw) != COVERAGE_SIZE or _sha(raw) != COVERAGE_SHA256:
        raise ValueError("live coverage identity mismatch")
    return json.loads(raw), raw


def _coverage_from_artifact(root: Path, artifact: Path | str) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    directory = _safe_file(root, artifact)
    if not directory.is_dir():
        raise ValueError("precoverage artifact is not a directory")
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    try: directory_fd = os.open(directory, flags)
    except OSError as exc: raise ValueError("precoverage directory identity failure") from exc
    try:
        manifest_raw = _read_regular_at(directory_fd, "manifest.json")
        archive_raw = _read_regular_at(directory_fd, "rom-byte-coverage.json.gz")
    finally: os.close(directory_fd)
    if _sha(manifest_raw) != ARCHIVE_MANIFEST_SHA256 or _sha(archive_raw) != ARCHIVE_SHA256:
        raise ValueError("precoverage outer manifest/archive identity mismatch")
    manifest = json.loads(manifest_raw)
    if manifest.get("schema") != "rom-byte-coverage-prepromotion-baseline-v1" or manifest.get("artifact_status") != "accepted":
        raise ValueError("precoverage outer manifest schema/status mismatch")
    if manifest.get("recovery", {}).get("kind") != RECOVERY_KIND:
        raise ValueError("precoverage recovery kind mismatch")
    archive = manifest.get("coverage", {}).get("archive", {})
    raw_meta = manifest.get("coverage", {}).get("raw", {})
    if archive != {"compression": "gzip", "file": "rom-byte-coverage.json.gz", "sha256": ARCHIVE_SHA256, "size": len(archive_raw)}:
        raise ValueError("precoverage archive metadata mismatch")
    try:
        raw = gzip.decompress(archive_raw)
    except Exception as exc:
        raise ValueError("precoverage gzip invalid") from exc
    if raw_meta != {"canonical_json": True, "schema": "rom-byte-coverage-v1", "sha256": COVERAGE_SHA256, "size": COVERAGE_SIZE, "summary": COVERAGE_SUMMARY}:
        raise ValueError("precoverage raw identity mismatch")
    if len(raw) != COVERAGE_SIZE or _sha(raw) != COVERAGE_SHA256:
        raise ValueError("precoverage decompressed raw mismatch")
    relative = directory.relative_to(root.resolve()).as_posix()
    return json.loads(raw), {"artifact": relative}, raw


def _read_regular_at(directory_fd: int, name: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try: fd = os.open(name, flags, dir_fd=directory_fd)
    except OSError as exc: raise ValueError(f"snapshot member open failure: {name}") from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode): raise ValueError(f"snapshot member not regular: {name}")
        chunks=[]
        while True:
            chunk=os.read(fd,1024*1024)
            if not chunk: break
            chunks.append(chunk)
        after=os.fstat(fd)
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns): raise ValueError(f"snapshot member changed: {name}")
        return b"".join(chunks)
    finally: os.close(fd)


def _covering_segments(coverage: dict[str, Any], interval: list[int]) -> list[dict[str, Any]]:
    start, end = interval
    rows = [row for row in coverage.get("segments", []) if row["range"][0] < end and start < row["range"][1]]
    rows.sort(key=lambda row: row["range"][0])
    cursor = start
    for index, row in enumerate(rows):
        left, right = row["range"]
        if (index == 0 and (left > cursor or right <= cursor)) or (index > 0 and (left != cursor or right <= cursor)):
            raise ValueError("coverage whole-range overlap/duplicate failure")
        cursor = max(cursor, right)
    if cursor < end:
        raise ValueError("coverage whole-range missing")
    return rows


def analyze_coverage_baseline(coverage: Any) -> dict[str, Any]:
    if not isinstance(coverage, dict):
        raise ValueError("coverage must be object")
    summary = coverage.get("summary", {})
    if coverage.get("schema") != "rom-byte-coverage-v1" or any(summary.get(key) != value for key, value in COVERAGE_SUMMARY.items()):
        raise ValueError("coverage summary/schema mismatch")
    for interval in [row["range"] for row in PROMOTION_RANGES] + EXCLUDED_RANGES:
        for row in _covering_segments(coverage, interval):
            if row.get("primary_class") != "unknown" or row.get("primary_claim_ids") != []:
                raise ValueError("promotion/gap must be whole-range unknown")
    owner_rows = _covering_segments(coverage, [634364, 634368])
    if any(row.get("primary_class") != "m4a_initializer_chain_consumed_literal_bytes" or row.get("primary_claim_ids") != ["psg-initializer-literals-09adc0"] for row in owner_rows):
        raise ValueError("initializer pointer owner mismatch")
    return {"summary": COVERAGE_SUMMARY}


def _validate_upstream_receipts(root: Path) -> dict[str, Any]:
    manifest = _safe_file(root, UPSTREAM_PATHS["manifest"]).read_bytes()
    payload_raw = _safe_file(root, UPSTREAM_PATHS["payload"]).read_bytes()
    if _sha(manifest) != UPSTREAM["m4a_initializer_chain"]["manifest_sha256"] or _sha(payload_raw) != UPSTREAM["m4a_initializer_chain"]["payload_sha256"]:
        raise ValueError("upstream initializer identity mismatch")
    payload = json.loads(payload_raw)
    owners = [row for row in payload.get("coverage_claims", []) if row.get("id") == "psg-initializer-literals-09adc0"]
    if len(owners) != 1 or owners[0].get("range") != [634304, 634384] or owners[0].get("semantic_class") != "m4a_initializer_chain_consumed_literal_bytes":
        raise ValueError("upstream initializer owner mismatch")
    instructions = {row.get("offset"): row for row in payload.get("cfg", {}).get("instructions", [])}
    expected = {
        634220: {"raw_hex": "2348", "mnemonic": "ldr", "op_str": "r0, [pc, #0x8c]"},
        634222: {"raw_hex": "a062", "mnemonic": "str", "op_str": "r0, [r4, #0x28]"},
    }
    for offset, semantic in expected.items():
        row = instructions.get(offset)
        if not isinstance(row, dict) or any(row.get(key) != value for key, value in semantic.items()):
            raise ValueError("upstream initializer semantic instruction mismatch")
    return UPSTREAM


def decode_initializer_semantics(rom: bytes) -> dict[str, Any]:
    load_offset = 634220
    store_offset = 634222
    load = struct.unpack_from("<H", rom, load_offset)[0]
    if load & 0xF800 != 0x4800:
        raise ValueError("initializer load semantic mismatch")
    load_rt = (load >> 8) & 7
    pc_base = (load_offset + 4) & ~3
    literal_offset = pc_base + (load & 0xFF) * 4
    if literal_offset + 4 > len(rom):
        raise ValueError("initializer load semantic literal escape")
    value = struct.unpack_from("<I", rom, literal_offset)[0]
    store = struct.unpack_from("<H", rom, store_offset)[0]
    if store & 0xF800 != 0x6000:
        raise ValueError("initializer store semantic mismatch")
    store_rt = store & 7
    store_base = (store >> 3) & 7
    field_offset = ((store >> 6) & 0x1F) * 4
    return {
        "load": {"offset": load_offset, "rt": f"r{load_rt}", "pc_base": pc_base, "literal_offset": literal_offset, "value": value},
        "store": {"offset": store_offset, "source": f"r{store_rt}", "base": f"r{store_base}", "width": "word", "field_offset": field_offset},
    }


def _initializer(rom: bytes, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    expected = _contract(root)["initializer_binding"]
    semantics = decode_initializer_semantics(rom)
    if semantics != {
        "load": {"offset": 634220, "rt": "r0", "pc_base": 634224, "literal_offset": 634364, "value": 0x0809B5F5},
        "store": {"offset": 634222, "source": "r0", "base": "r4", "width": "word", "field_offset": 0x28},
    }:
        raise ValueError("initializer raw semantic binding mismatch")
    _validate_upstream_receipts(root)
    pointer_raw = bytes.fromhex("f5b50908")
    occurrences = [i for i in range(len(rom) - 3) if rom[i:i + 4] == pointer_raw]
    if occurrences != [634364] or expected["destination_address"] != expected["structure_base"] + semantics["store"]["field_offset"]:
        raise ValueError("initializer pointer occurrence denominator mismatch")
    return expected


PRODUCER_FORMS = ["thumb_bl", "thumb_b", "thumb_b_conditional", "arm_b", "arm_bl", "bytewise_u32_entry", "bytewise_u32_thumb_pointer"]
_PRODUCER_CACHE: dict[str, dict[str, Any]] = {}


def _scan_producers(rom: bytes) -> dict[str, Any]:
    identity = _sha(rom)
    if identity in _PRODUCER_CACHE:
        return json.loads(json.dumps(_PRODUCER_CACHE[identity]))
    targets = {636404: {name: [] for name in PRODUCER_FORMS}}
    size = len(rom)
    for offset in range(0, size - 1, 2):
        h = struct.unpack_from("<H", rom, offset)[0]
        if h & 0xF800 == 0xE000:
            d = h & 0x7FF
            if d & 0x400: d -= 0x800
            target = offset + 4 + d * 2
            if target in targets: targets[target]["thumb_b"].append(offset)
        if h & 0xF000 == 0xD000 and ((h >> 8) & 0xF) < 0xE:
            d = h & 0xFF
            if d & 0x80: d -= 0x100
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
        word = struct.unpack_from("<I", rom, offset)[0]
        op = word & 0xFF000000
        if op in (0xEA000000, 0xEB000000):
            d = word & 0xFFFFFF
            if d & 0x800000: d -= 0x1000000
            target = offset + 8 + d * 4
            if target in targets: targets[target]["arm_bl" if op == 0xEB000000 else "arm_b"].append(offset)
    values = {0x08000000 + target: (target, "bytewise_u32_entry") for target in targets}
    values.update({0x08000001 + target: (target, "bytewise_u32_thumb_pointer") for target in targets})
    for offset in range(size - 3):
        item = values.get(struct.unpack_from("<I", rom, offset)[0])
        if item: targets[item[0]][item[1]].append(offset)
    target_row = {"forms": {name: targets[636404][name] for name in sorted(PRODUCER_FORMS)}, "target_file_offset": 636404}
    result = {"forms": PRODUCER_FORMS, "scan_range": [0, size], "target": target_row,
              "vector_encoding": _contract(PROJECT_ROOT)["producer_denominator"]["vector_encoding"],
              "vector_sha256": _sha(json.dumps([target_row], separators=(",", ":"), sort_keys=True).encode())}
    expected = _contract(PROJECT_ROOT)["producer_denominator"]
    if result != expected:
        raise ValueError("producer denominator mismatch")
    _PRODUCER_CACHE[identity] = result
    return result


def build_payload_from_rom(root: Path | str, rom: bytes, *, coverage_baseline_artifact: Path | str | None = None) -> tuple[dict[str, Any], bytes]:
    root = Path(root).resolve()
    contract = _contract(root)
    _validate_rom(rom)
    bundle = _check_promotion_bytes(rom)
    cfg = analyze_cfg_from_rom(rom)
    cfg["packed_code_sha256"] = contract["cfg"]["packed_code_sha256"]
    cfg["vector_encoding"] = contract["cfg"]["vector_encoding"]
    upstream = _validate_upstream_receipts(root)
    if coverage_baseline_artifact is None:
        coverage, raw = load_live_coverage(root)
        source = {"path": COVERAGE_PATH.as_posix(), "kind": "live"}
        immutable = contract["coverage_baseline"]["immutable_artifact"]
    else:
        coverage, source, raw = _coverage_from_artifact(root, coverage_baseline_artifact)
        immutable = {"path": source["artifact"], "archive_sha256": ARCHIVE_SHA256, "manifest_sha256": ARCHIVE_MANIFEST_SHA256}
    analyze_coverage_baseline(coverage)
    for consumer, literal, value, load_hex, literal_hex in contract["literal_projection"]["bindings"]:
        halfword = struct.unpack_from("<H", rom, consumer)[0]
        target = ((consumer + 4) & ~3) + (halfword & 0xFF) * 4
        if target != literal or struct.unpack_from("<I", rom, literal)[0] != value or rom[consumer:consumer + 2].hex() != load_hex or rom[literal:literal + 4].hex() != literal_hex:
            raise ValueError("literal PC-align binding mismatch")
    excluded = [{"range": interval, "raw_hex": rom[interval[0]:interval[1]].hex(), "sha256": _sha(rom[interval[0]:interval[1]]), "promoted": False, "semantic_class": "unknown"} for interval in EXCLUDED_RANGES]
    projection = {"claim_delta": len(PROMOTION_RANGES), "classified_delta": sum(r["bytes"] for r in PROMOTION_RANGES),
                  "segment_delta": len(PROMOTION_RANGES) + len(EXCLUDED_RANGES) + 1,
                  "unknown_delta": -sum(r["bytes"] for r in PROMOTION_RANGES)}
    projection["post_if_applied_alone"] = {"claim_count": COVERAGE_SUMMARY["claim_count"] + projection["claim_delta"], "classified_bytes": COVERAGE_SUMMARY["classified_bytes"] + projection["classified_delta"], "segment_count": COVERAGE_SUMMARY["segment_count"] + projection["segment_delta"], "unknown_bytes": COVERAGE_SUMMARY["unknown_bytes"] + projection["unknown_delta"]}
    if projection != contract["coverage_projection"]: raise ValueError("coverage projection mismatch")
    payload = {
        "schema": SCHEMA,
        "rom": contract["base_rom"],
        "envelope": contract["envelope"],
        "root_offset": contract["cfg"]["root_offset"],
        "cfg": cfg,
        "promotion": contract["promotion"],
        "promotion_ranges": contract["promotion"]["ranges"],
        "literal_projection": contract["literal_projection"],
        "excluded_ranges": excluded,
        "initializer_binding": _initializer(rom, root),
        "producer_denominator": _scan_producers(rom),
        "coverage_baseline": {"path": contract["coverage_baseline"]["path"], "sha256": _sha(raw), "size": len(raw), "summary": COVERAGE_SUMMARY, "immutable_artifact": immutable},
        "coverage_baseline_source": source,
        "coverage_projection": projection,
        "coverage_projection_recomputed": True,
        "coverage_snapshot_read_count": 1,
        "upstream_receipts": upstream,
        "scope": contract["scope"],
    }
    return payload, bundle


def build_payload(root: Path | str = PROJECT_ROOT, *, coverage_baseline_artifact: Path | str | None = None) -> tuple[dict[str, Any], bytes]:
    root = Path(root).resolve()
    return build_payload_from_rom(root, _safe_file(root, ROM_PATH).read_bytes(), coverage_baseline_artifact=coverage_baseline_artifact)


load_live_coverage = _coverage_from_file


def analyze_initializer(root: Path | str, rom: bytes) -> dict[str, Any]:
    return _initializer(rom, Path(root).resolve())


scan_producers = _scan_producers


def _validate_output(root: Path, output: Path | str) -> tuple[Path, tuple[int, int]]:
    root = root.resolve()
    requested = Path(output)
    if ".." in requested.parts:
        raise ValueError("output parent '..' components are forbidden")
    if not requested.is_absolute(): requested = root / requested
    output = Path(os.path.abspath(requested))
    experiments = [(root / OUTPUT_EXPERIMENT).resolve()]
    if not any(output != experiment and output.is_relative_to(experiment) for experiment in experiments):
        raise ValueError("output escapes candidate experiment")
    if os.path.lexists(output): raise ValueError("output must be a new empty path")
    current = root
    for part in output.relative_to(root).parts[:-1]:
        current /= part
        if current.is_symlink(): raise ValueError("symlink output component")
    try:
        parent = output.parent.resolve(strict=True)
    except OSError as exc:
        raise ValueError("output parent must already exist") from exc
    output = parent / output.name
    info = parent.stat()
    return output, (info.st_dev, info.st_ino)


def _open_directory_beneath(root: Path, directory: Path, expected_identity: tuple[int, int]) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"): flags |= os.O_NOFOLLOW
    try:
        fd = os.open(directory, flags)
    except OSError as exc:
        raise ValueError("symlink or invalid output parent") from exc
    info = os.fstat(fd)
    if (info.st_dev, info.st_ino) != expected_identity:
        os.close(fd); raise ValueError("output parent identity changed")
    return fd


def _write_file_at(directory_fd: int, name: str, raw: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"): flags |= os.O_NOFOLLOW
    fd = os.open(name, flags, 0o644, dir_fd=directory_fd)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    finally: os.close(fd)


def _remove_created_at(parent_fd: int, name: str, identity: tuple[int, int] | None) -> None:
    try: current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError: return
    if identity is not None and (current.st_dev, current.st_ino) != identity: return
    if not stat.S_ISDIR(current.st_mode) or stat.S_ISLNK(current.st_mode): return
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0); fd = os.open(name, flags, dir_fd=parent_fd)
    try:
        for child in os.listdir(fd): os.unlink(child, dir_fd=fd)
    finally: os.close(fd)
    try: os.rmdir(name, dir_fd=parent_fd)
    except FileNotFoundError: pass


def write_candidate(root: Path | str, output: Path | str, *, coverage_baseline_artifact: Path | str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    target, identity = _validate_output(root, output)
    payload, bundle = build_payload(root, coverage_baseline_artifact=coverage_baseline_artifact)
    payload_raw = _pretty(payload)
    files = {
        "rom-cgbsound-bounded-cfg.bin": bundle,
        "rom-cgbsound-bounded-cfg.json": payload_raw,
    }
    manifest = {"schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA, "artifact_status": "candidate", "contract_sha256": CONTRACT_SHA256,
                "files": {name: {"sha256": _sha(raw), "size": len(raw)} for name, raw in files.items()}}
    files["manifest.json"] = _pretty(manifest)
    parent_fd = _open_directory_beneath(root, target.parent, identity)
    child_fd = None; created_identity = None
    try:
        os.mkdir(target.name, 0o755, dir_fd=parent_fd)
        created = os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False); created_identity = (created.st_dev, created.st_ino)
        flags = os.O_RDONLY | os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"): flags |= os.O_NOFOLLOW
        child_fd = os.open(target.name, flags, dir_fd=parent_fd)
        info = os.fstat(child_fd)
        if (info.st_dev, info.st_ino) != created_identity: raise ValueError("candidate directory identity changed")
        for name, raw in files.items(): _write_file_at(child_fd, name, raw)
        os.fsync(child_fd); os.fsync(parent_fd)
    except Exception:
        if child_fd is not None: os.close(child_fd); child_fd = None
        _remove_created_at(parent_fd, target.name, created_identity)
        raise
    finally:
        if child_fd is not None: os.close(child_fd)
        os.close(parent_fd)
    return {"bundle_sha256": _sha(bundle), "output": str(target), "artifact_status": "candidate"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--coverage-baseline-artifact", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(write_candidate(PROJECT_ROOT, args.output, coverage_baseline_artifact=args.coverage_baseline_artifact), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
