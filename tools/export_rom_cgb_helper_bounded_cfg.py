#!/usr/bin/env python3
"""Build the candidate-only bounded CGB helper CFG packet."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import sys
from typing import Any

VENDOR = Path(__file__).resolve().parent / "_vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))
from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = Path("build/experiments/active/cgb-helper-contract/codex-r1-20260829")
OUTPUT_EXPERIMENT = Path("build/experiments/active/cgb-helper-bounded-cfg-20260829")
CONTRACT_PATH = EXPERIMENT / "CONTRACT.json"
CONTRACT_SHA256 = "e1f4d0b840d52b19ee996ee7c0ba18c41511f0c96b37f498f77954a24c9105b7"
SCHEMA = "rom-cgb-helper-bounded-cfg-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "22f8f88ca0929468289b749cb94b4aaa4c47d7a53fa68fe10cb93c9a01816839"
COVERAGE_SIZE = 23152713
COVERAGE_SUMMARY = {"claim_count": 14507, "classified_bytes": 6124601, "segment_count": 16617, "unknown_bytes": 166855}
CODE_RANGES = [[636220, 636256], [636260, 636264], [636268, 636274], [636280, 636294], [636300, 636404]]
LITERAL_RANGES = [[636256, 636260], [636264, 636268], [636276, 636280], [636296, 636300]]
EXCLUDED_RANGES = [[636274, 636276], [636294, 636296]]
ROOTS = [636220, 636300]
PROMOTION_RANGES = [
    {"bytes": 36, "kind": "cgb_helper_bounded_thumb_code", "range": [636220, 636256], "sha256": "ac01b052dd7ab7f97e74b52e671f1e8bdc2c423caeebeee4c5618c905f29bca1"},
    {"bytes": 4, "kind": "cgb_helper_consumed_literal_bytes", "range": [636256, 636260], "sha256": "22f7252bc2b8f2444cb6c59642ab9d902a8cac23e4c27e48623e8513b28ddeee"},
    {"bytes": 4, "kind": "cgb_helper_bounded_thumb_code", "range": [636260, 636264], "sha256": "df358c07b036a56dcc30711ce42e97371d6e3f08f6a1e8027e0beb713f85c56d"},
    {"bytes": 4, "kind": "cgb_helper_consumed_literal_bytes", "range": [636264, 636268], "sha256": "60e226a6318302bbe245079f99e6724c5cd2431c689d5ae9992b08bdcc592a04"},
    {"bytes": 6, "kind": "cgb_helper_bounded_thumb_code", "range": [636268, 636274], "sha256": "30c6c9fcb611330459336092dfdf9059b742dabc6d5f773ae67f501c1caadc3f"},
    {"bytes": 4, "kind": "cgb_helper_consumed_literal_bytes", "range": [636276, 636280], "sha256": "d0455d972504810561aaa6b9cc70d69a9ad49abc84a3df38789afdd8eb9236eb"},
    {"bytes": 14, "kind": "cgb_helper_bounded_thumb_code", "range": [636280, 636294], "sha256": "6531a1df4bcdc95692713b4c346c135e75339afb73d35dd2934ff15e9f606d99"},
    {"bytes": 4, "kind": "cgb_helper_consumed_literal_bytes", "range": [636296, 636300], "sha256": "bd56e77404afec2e1cb1d293f4b56e5188b6e7c5d7aaf39d58dbd1de177f28fd"},
    {"bytes": 104, "kind": "cgb_helper_bounded_thumb_code", "range": [636300, 636404], "sha256": "584762a3caa5fe9d71f2afd7fe58f2e5a8d2ef8efb2c4d68df84a621b84c9b88"},
]
EXPECTED_CFG_HASHES = {
    "semantic_instruction_vector_sha256": "66df11b0f24f38a6aa9aa3b202c5b07b949ff98631ddb3f8c97f46d602d8f5db",
    "block_range_vector_sha256": "421415d1f0c255dc581a1076ec73441ef031ed7fd623ce6d8e224b2e51ab55ce",
    "edge_vector_sha256": "7c080763f41c5afb6556bc4dcdf44ccd884a96ac8b14d8270aa68f77c36a2978",
}
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
    if len(bundle) != 180 or _sha(bundle) != "87c62bbe5f0e9d25ee5b11398ecdd3ed5b41782d4873871205f71c1122a4c1dc":
        raise ValueError("promotion bundle mismatch")
    return bundle


def _raw_flow(rom: bytes, offset: int) -> list[dict[str, Any]]:
    halfword = struct.unpack_from("<H", rom, offset)[0]
    if halfword & 0xF000 == 0xD000 and ((halfword >> 8) & 0xF) < 0xE:
        delta = halfword & 0xFF
        if delta & 0x80:
            delta -= 0x100
        return [{"kind": "branch", "target_offset": offset + 4 + delta * 2}, {"kind": "fallthrough", "target_offset": offset + 2}]
    if halfword & 0xF800 == 0xE000:
        delta = halfword & 0x7FF
        if delta & 0x400:
            delta -= 0x800
        return [{"kind": "branch", "target_offset": offset + 4 + delta * 2}]
    if halfword & 0xFF87 == 0x4700:
        return []
    return [{"kind": "fallthrough", "target_offset": offset + 2}]


def _reachable(rom: bytes) -> tuple[list[int], dict[int, list[dict[str, Any]]]]:
    valid = {offset for start, end in CODE_RANGES for offset in range(start, end, 2)}
    seen: set[int] = set()
    pending = list(ROOTS)
    flows: dict[int, list[dict[str, Any]]] = {}
    while pending:
        offset = pending.pop()
        if offset in seen:
            continue
        if offset not in valid:
            raise ValueError(f"CFG target escapes or enters instruction middle/gap: {offset}")
        seen.add(offset)
        flows[offset] = _raw_flow(rom, offset)
        pending.extend(edge["target_offset"] for edge in flows[offset])
    if seen != valid:
        raise ValueError("CFG has unreachable expected instruction or new frontier")
    return sorted(seen), flows


def _blocks(offsets: list[int], flows: dict[int, list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seen = set(offsets)
    leaders = set(ROOTS)
    for offset in offsets:
        flow = flows[offset]
        leaders.update(edge["target_offset"] for edge in flow if edge["kind"] == "branch")
        if len(flow) == 2:
            leaders.add(offset + 2)
    ranges = []
    for start in sorted(leaders):
        if start not in seen:
            continue
        end_instruction = start
        while True:
            flow = flows[end_instruction]
            following = end_instruction + 2
            if not flow or any(edge["kind"] == "branch" for edge in flow) or following in leaders or following not in seen:
                break
            end_instruction = following
        ranges.append([start, end_instruction + 2])
    block_by_offset = {offset: index for index, (start, end) in enumerate(ranges) for offset in range(start, end, 2)}
    blocks = []
    edges = []
    for index, interval in enumerate(ranges):
        start, end = interval
        terminal = end - 2
        successors = []
        for edge in flows[terminal]:
            target = edge["target_offset"]
            row = {"source_instruction_offset": terminal, "target_offset": target, "kind": edge["kind"]}
            successors.append(row)
            edges.append(row)
        blocks.append({"id": f"block-{start:06x}", "range": interval, "instruction_count": (end - start) // 2, "successors": successors})
    edges.sort(key=lambda row: (row["source_instruction_offset"], 0 if row["kind"] == "branch" else 1))
    return blocks, edges


def analyze_cfg_from_rom(rom: bytes) -> dict[str, Any]:
    offsets, flows = _reachable(rom)
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    semantic_rows = []
    capstone_rows: dict[int, tuple[str, str]] = {}
    for start, end in CODE_RANGES:
        decoded = list(engine.disasm(rom[start:end], 0x08000000 + start))
        if sum(insn.size for insn in decoded) != end - start:
            raise ValueError("Capstone did not consume exact code range")
        for insn in decoded:
            offset = insn.address - 0x08000000
            capstone_rows[offset] = (insn.mnemonic, insn.op_str)
    instructions = []
    blocks, block_edges = _blocks(offsets, flows)
    terminal_sources = {row["source_instruction_offset"] for row in block_edges}
    for offset in offsets:
        mnemonic, op_str = capstone_rows[offset]
        semantic_rows.append([offset, 2, mnemonic, op_str])
        instructions.append({"offset": offset, "size": 2, "raw_hex": rom[offset:offset + 2].hex(), "mnemonic": mnemonic, "op_str": op_str, "successors": flows[offset] if offset in terminal_sources else []})
    block_vector = [row["range"] for row in blocks]
    edge_vector = [[row["source_instruction_offset"], row["target_offset"], row["kind"]] for row in block_edges]
    cfg = {
        "instruction_count": len(instructions), "code_bytes": sum(row["size"] for row in instructions),
        "block_count": len(blocks), "internal_edge_count": len(block_edges), "external_edge_count": 0,
        "structured_return_count": 2, "frontier_count": 0, "budget_exhausted": False,
        "code_ranges": CODE_RANGES, "return_offsets": [636292, 636402], "frontiers": [],
        "instructions": instructions, "blocks": blocks, "block_edges": block_edges,
        "returns": [{"offset": 636292, "register": "lr"}, {"offset": 636402, "register": "r0"}],
        "semantic_instruction_vector_sha256": _sha(_canonical(semantic_rows)),
        "block_range_vector_sha256": _sha(_canonical(block_vector)),
        "edge_vector_sha256": _sha(_canonical(edge_vector)),
    }
    for key, expected in EXPECTED_CFG_HASHES.items():
        if cfg[key] != expected:
            raise ValueError(f"CFG {key} mismatch")
    if (len(instructions), len(blocks), len(block_edges)) != (82, 23, 29):
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
    manifest_path = _safe_file(root, directory / "manifest.json")
    archive_path = _safe_file(root, directory / "rom-byte-coverage.json.gz")
    manifest_raw = manifest_path.read_bytes()
    archive_raw = archive_path.read_bytes()
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


def _covering_segments(coverage: dict[str, Any], interval: list[int]) -> list[dict[str, Any]]:
    start, end = interval
    rows = [row for row in coverage.get("segments", []) if row["range"][0] < end and start < row["range"][1]]
    rows.sort(key=lambda row: row["range"][0])
    cursor = start
    for row in rows:
        left, right = row["range"]
        if left > cursor or right <= cursor:
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
    owner_rows = _covering_segments(coverage, [634368, 634372])
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
        634224: {"raw_hex": "2348", "mnemonic": "ldr", "op_str": "r0, [pc, #0x8c]"},
        634226: {"raw_hex": "e062", "mnemonic": "str", "op_str": "r0, [r4, #0x2c]"},
    }
    for offset, semantic in expected.items():
        row = instructions.get(offset)
        if not isinstance(row, dict) or any(row.get(key) != value for key, value in semantic.items()):
            raise ValueError("upstream initializer semantic instruction mismatch")
    return UPSTREAM


def decode_initializer_semantics(rom: bytes) -> dict[str, Any]:
    load_offset = 634224
    store_offset = 634226
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
    expected = {
        "destination_address": 50361676, "entry_pointer": 134853949, "entry_pointer_occurrences": [634368],
        "entry_pointer_root_offset": 636220, "field_offset": 44,
        "load_instruction": {"offset": 634224, "raw_hex": "2348"},
        "pointer_literal": {"range": [634368, 634372], "raw_hex": "3db50908", "sha256": "1a648773d0593fdc9669da7e1ca0bb40589edbdddcfdb0dda47230d8a3db5581"},
        "store_instruction": {"offset": 634226, "raw_hex": "e062"}, "structure_base": 50361632,
    }
    semantics = decode_initializer_semantics(rom)
    if semantics != {
        "load": {"offset": 634224, "rt": "r0", "pc_base": 634228, "literal_offset": 634368, "value": 0x0809B53D},
        "store": {"offset": 634226, "source": "r0", "base": "r4", "width": "word", "field_offset": 0x2C},
    }:
        raise ValueError("initializer raw semantic binding mismatch")
    _validate_upstream_receipts(root)
    occurrences = [i for i in range(len(rom) - 3) if rom[i:i + 4] == bytes.fromhex("3db50908")]
    if occurrences != [634368]:
        raise ValueError("initializer pointer occurrence denominator mismatch")
    return expected


PRODUCER_FORMS = ["thumb_bl", "thumb_b", "thumb_b_conditional", "arm_b", "arm_bl", "bytewise_u32_entry", "bytewise_u32_thumb_pointer"]
_PRODUCER_CACHE: dict[str, dict[str, Any]] = {}


def _scan_producers(rom: bytes) -> dict[str, Any]:
    identity = _sha(rom)
    if identity in _PRODUCER_CACHE:
        return json.loads(json.dumps(_PRODUCER_CACHE[identity]))
    targets = {636220: {name: [] for name in PRODUCER_FORMS}, 636300: {name: [] for name in PRODUCER_FORMS}}
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
    rows = [{"target_file_offset": target, "forms": targets[target]} for target in sorted(targets)]
    vector = [[row["target_file_offset"], [[name, row["forms"][name]] for name in PRODUCER_FORMS]] for row in rows]
    result = {"forms": PRODUCER_FORMS, "scan_range": [0, size], "targets": rows, "vector_sha256": "536020c92992d0ea9387b79d4ef15f9aa9e09b3f82c100b8c396fe1af98c4ab1"}
    expected = _contract(PROJECT_ROOT)["producer_denominator"] if PROJECT_ROOT.exists() else None
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
    cfg["roots"] = contract["cfg"]["roots"]
    cfg["packed_code_sha256"] = contract["cfg"]["packed_code_sha256"]
    cfg["vector_encoding"] = contract["cfg"]["vector_encoding"]
    upstream = _validate_upstream_receipts(root)
    if coverage_baseline_artifact is None:
        coverage, raw = _coverage_from_file(root)
        source = {"path": COVERAGE_PATH.as_posix(), "kind": "live"}
        immutable = contract["coverage_baseline"]["immutable_artifact"]
    else:
        coverage, source, raw = _coverage_from_artifact(root, coverage_baseline_artifact)
        immutable = {"path": source["artifact"], "archive_sha256": ARCHIVE_SHA256, "manifest_sha256": ARCHIVE_MANIFEST_SHA256}
    analyze_coverage_baseline(coverage)
    literal_bindings = contract["literal_projection"]["bindings"]
    for row in literal_bindings:
        start, end = row["range"]
        halfword = struct.unpack_from("<H", rom, row["consumer_offset"])[0]
        target = ((row["consumer_offset"] + 4) & ~3) + (halfword & 0xFF) * 4
        if target != start or struct.unpack_from("<I", rom, start)[0] != row["value"] or rom[row["consumer_offset"]:row["consumer_offset"] + 2].hex() != row["load_raw_hex"]:
            raise ValueError("literal PC-align binding mismatch")
    excluded = [{**row, "promoted": False, "semantic_class": "unknown"} for row in contract["excluded_ranges"]]
    payload = {
        "schema": SCHEMA,
        "rom": contract["base_rom"],
        "envelope": contract["envelope"],
        "roots": contract["cfg"]["roots"],
        "cfg": cfg,
        "promotion": contract["promotion"],
        "promotion_ranges": contract["promotion"]["ranges"],
        "literal_projection": contract["literal_projection"],
        "excluded_ranges": excluded,
        "initializer_binding": _initializer(rom, root),
        "producer_denominator": _scan_producers(rom),
        "coverage_baseline": {"path": contract["coverage_baseline"]["path"], "sha256": _sha(raw), "size": len(raw), "summary": COVERAGE_SUMMARY, "immutable_artifact": immutable},
        "coverage_baseline_source": source,
        "coverage_projection": contract["coverage_projection"],
        "upstream_receipts": upstream,
        "scope": contract["scope"],
    }
    return payload, bundle


def build_payload(root: Path | str = PROJECT_ROOT, *, coverage_baseline_artifact: Path | str | None = None) -> tuple[dict[str, Any], bytes]:
    root = Path(root).resolve()
    return build_payload_from_rom(root, _safe_file(root, ROM_PATH).read_bytes(), coverage_baseline_artifact=coverage_baseline_artifact)


def _validate_output(root: Path, output: Path | str) -> tuple[Path, tuple[int, int]]:
    root = root.resolve()
    requested = Path(output)
    if ".." in requested.parts:
        raise ValueError("output parent '..' components are forbidden")
    if not requested.is_absolute(): requested = root / requested
    output = Path(os.path.abspath(requested))
    experiments = [(root / value).resolve() for value in (EXPERIMENT, OUTPUT_EXPERIMENT)]
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
        with os.fdopen(fd, "wb", closefd=False) as stream: stream.write(raw)
    finally: os.close(fd)


def write_candidate(root: Path | str, output: Path | str, *, coverage_baseline_artifact: Path | str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    target, identity = _validate_output(root, output)
    payload, bundle = build_payload(root, coverage_baseline_artifact=coverage_baseline_artifact)
    payload_raw = _pretty(payload)
    files = {
        "rom-cgb-helper-bounded-cfg.bin": bundle,
        "rom-cgb-helper-bounded-cfg.json": payload_raw,
    }
    manifest = {"schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA, "artifact_status": "candidate", "contract_sha256": CONTRACT_SHA256,
                "files": {name: {"sha256": _sha(raw), "size": len(raw)} for name, raw in files.items()}}
    files["manifest.json"] = _pretty(manifest)
    parent_fd = _open_directory_beneath(root, target.parent, identity)
    child_fd = None
    try:
        os.mkdir(target.name, 0o755, dir_fd=parent_fd)
        flags = os.O_RDONLY | os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"): flags |= os.O_NOFOLLOW
        child_fd = os.open(target.name, flags, dir_fd=parent_fd)
        for name, raw in files.items(): _write_file_at(child_fd, name, raw)
    except Exception:
        if child_fd is not None: os.close(child_fd); child_fd = None
        try: shutil.rmtree(target)
        except Exception: pass
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
