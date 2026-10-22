#!/usr/bin/env python3
"""Export the bounded selector-menu CFG proven-roots v10 packet."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import heapq
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
_CLEAN_CLI_STARTUP_CONFIRMED = False


def _require_isolated_cli_runtime() -> None:
    global _CLEAN_CLI_STARTUP_CONFIRMED
    if __name__ != "__main__":
        return
    if not sys.flags.isolated or not sys.flags.no_site:
        raise RuntimeError("CFG v10 CLI requires Python -I -S isolation")
    if "capstone" in sys.modules:
        raise RuntimeError("CFG v10 CLI rejects preloaded Capstone modules")
    if os.environ.get("LIBCAPSTONE_PATH"):
        raise RuntimeError("CFG v10 CLI rejects LIBCAPSTONE_PATH overrides")
    _CLEAN_CLI_STARTUP_CONFIRMED = True


_require_isolated_cli_runtime()

for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from tools.export_rom_cfg_inventory import (  # noqa: E402
    _build_blocks,
    _canonical_json,
    _canonical_sha,
    _decode_one,
    _key,
    _reject_symlink_components,
    _replace_output_dir,
    _safe_file,
    _sha,
    _union_bytes,
)


ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "rom-cfg-proven-roots-v10"
VERIFY_SCHEMA = "rom-cfg-proven-roots-verification-v10"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
PAYLOAD_NAME = "rom-cfg-proven-roots-v10.json"
MANIFEST_NAME = "manifest.json"

EXPECTED_REPORT = {
    "schema": VERIFY_SCHEMA,
    "verified": True,
    "errors": [],
    "control_flow_oracle": "armv4t-raw-encoding",
    "source_decoded_instruction_count": 264,
    "source_decoded_basic_block_count": 35,
    "source_reachable_instruction_bytes": 580,
    "source_frontier_count": 0,
    "source_external_call_edge_count": 26,
    "independently_rebuilt_instruction_count": 36,
    "decoded_basic_block_count": 7,
    "reachable_instruction_bytes": 72,
    "frontier_count": 0,
}

SOURCE_RANGE = (0x08B2C8, 0x08B580)
SOURCE_ROOT = 0x08B2C8
SOURCE_ROOT_RAW = "f0b55746"
SOURCE_ROOT_SHA256 = "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb"
SOURCE_SLICE_SHA256 = "fe12c74a937dae0e60f0ba1e566788cd4dc842596d168632c9c45809f88dd07e"
SOURCE_PRODUCER = 0x08B640
SOURCE_PRODUCER_TARGET = SOURCE_ROOT
SOURCE_PRODUCER_RAW = "fff742fe"
SOURCE_PRODUCER_SHA256 = "8bb61927c644fe29c71e934d8e119ec88a0e85273bc4c75ab66c7dc70aadf2f4"
SOURCE_EXTERNAL_VECTOR_SHA256 = "60bfe46619672256529ff046ffe8231259911e49303be42b80eac5175885cb0f"
SOURCE_BLOCK_RANGE_SHA256 = "1f3ed3239ae466d2b6f0461ba45ae446b17790ae518d8b119895d14267914346"

TARGET_RANGE = (0x08B278, 0x08B2C4)
TARGET_ENVELOPE = (0x08B278, 0x08B2C8)
TARGET_ROOT = 0x08B278
TARGET_ROOT_RAW = "10b5041c"
TARGET_ROOT_SHA256 = "3e46e3c4aedc598659e8b54f9ca4d75ca6b3463a987e1230f775c064f8d0cdc6"
TARGET_PRODUCERS = (
    (0x08B428, TARGET_ROOT, "fff726ff", "caf18015a8293721c3793fead7a0e280298b190f450999515742eb065e08cdd1"),
    (0x08B4F8, TARGET_ROOT, "fff7befe", "6667248043fe28776675c44a4433980294a1fd0365fcf064b08ef4080cd0fcbd"),
)
TARGET_BLOCK_RANGE_SHA256 = "4da59c1e58dd71ce16462a5e6a33ff62003fbc4c43aa570b56fea7900b05aed7"
ENVELOPE_SHA256 = "bac5ad25e409197b0594658159d14f2993dfabb2a20b842ffa9fd8bddfe70890"

RETURN_PREFIX = "01bc0047"
RETURN_SHA256 = "15a0c45072c4f43ac42d0c62cb597469cb73ae8294c056a31dc8415af2bc0d3c"
SOURCE_RETURN_BX = 0x08B578
TARGET_RETURN_BX = 0x08B2C2

LITERAL_RANGE_SHA256 = "a7ec3a41a610f7fad5af7f702db7684430e1cc86aa850d89000129426e3c4506"
PACKED_LITERAL_SHA256 = "da9566975c6272f3ec6be2401beabfa49089f1b951e7a60a0c63611d0b7b985d"
LITERAL_RAW = "fffffdff"
LITERAL_VALUE = 4_294_836_223
LITERAL_SPECS = (
    (0x08B294, "064a", (0x08B2B0, 0x08B2B4)),
    (0x08B2B8, "024a", (0x08B2C4, 0x08B2C8)),
)

COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
COVERAGE_SHA256 = "dd2a64883da6a5b561336a70d90ceb97a6ca7eb282b3bd09b0f3ec2d9ed0d156"
EXPERIMENT_OUTPUT_ROOT = Path("build/experiments/active/cfg-proven-roots-v10")

UPSTREAM = {
    "artifact_schema": "rom-selector-text-bindings-v1",
    "payload_path": "artifacts/rom-selector-text-bindings-v1/selector-text-bindings.json",
    "payload_sha256": "8737d04de14949cbbbb9215c892a7776476c4230eb1e2b0c2abbbbe4440ce2eb",
    "manifest_path": "artifacts/rom-selector-text-bindings-v1/manifest.json",
    "manifest_sha256": "05cd987a60990ca6b2d3ee187eae963fd6ac8728ef9b42b92d6b37b5dc4bc031",
    "verifier_path": "tools/verify_rom_selector_text_bindings.py",
    "verifier_sha256": "a68a0d1e036be241bbac84538d5a082c7e76e2c6331ffa1d12cd384dc79e2f18",
    "verification_schema": "rom-selector-text-bindings-verification-v1",
    "menu_selector_range": [0x08B2C8, 0x08B580],
}

NONCLAIMS = [
    "natural_execution_reachability",
    "global_code_denominator",
    "global_caller_denominator",
    "global_indirect_target_denominator",
    "source_window_all_instructions",
    "literal_editability",
    "adjacent_region_code_or_free_space",
]
SCOPE = {
    "fixed_direct_producer_denominator_complete": True,
    "source_slice_bounded_worklist_complete": True,
    "target_envelope_complete": True,
    "baseline_entries_treated_as_opaque": True,
    "promotion_window_complete": True,
    "current_known_overlap_bytes": 0,
    "runtime_reachability_complete": False,
    "global_code_denominator_complete": False,
    "global_caller_denominator_complete": False,
    "global_indirect_target_denominator_complete": False,
    "source_window_all_instructions": False,
    "literal_editability_proven": False,
    "adjacent_region_code_or_free_space": False,
    "nonclaims": NONCLAIMS,
}

CAPSTONE_RUNTIME_DIRECTORY = Path("tools/_vendor/capstone")
RUNTIME_DEPENDENCY_PATHS = (
    Path("tools/export_rom_cfg_inventory.py"),
    Path("tools/verify_rom_cfg_inventory.py"),
    Path("tools/verify_rom_selector_text_bindings.py"),
    Path("tools/verify_rom_cfg_seeds.py"),
    Path("tools/verify_similar_table_candidates.py"),
) + tuple(
    CAPSTONE_RUNTIME_DIRECTORY / path.name
    for path in sorted(CAPSTONE_RUNTIME_DIRECTORY.glob("*.py"))
) + (CAPSTONE_RUNTIME_DIRECTORY / "lib/libcapstone.dylib",)


def _producer_target(callsite: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return callsite + 4 + displacement


def _producer_denominator(rom: bytes) -> dict[str, Any]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    expected = (*TARGET_PRODUCERS, (SOURCE_PRODUCER, SOURCE_PRODUCER_TARGET, SOURCE_PRODUCER_RAW, SOURCE_PRODUCER_SHA256))
    targets = {item[1] for item in expected}
    actual = []
    for offset in range(0, len(rom) - 3, 2):
        first = int.from_bytes(rom[offset : offset + 2], "little")
        second = int.from_bytes(rom[offset + 2 : offset + 4], "little")
        target = _producer_target(offset, first, second)
        if target in targets:
            actual.append((offset, target))
    expected_offsets = [(item[0], item[1]) for item in expected]
    if actual != expected_offsets:
        raise ValueError("direct-BL producer denominator changed")
    records = []
    for offset, target, raw_hex, digest in expected:
        raw = rom[offset : offset + 4]
        if raw.hex() != raw_hex or _sha(raw) != digest:
            raise ValueError(f"producer bytes changed at 0x{offset:06X}")
        records.append(
            {
                "file_offset": offset,
                "gba_address": f"0x{ROM_BASE + offset:08X}",
                "raw_hex": raw_hex,
                "bytes_sha256": digest,
                "target_file_offset": target,
                "target_gba_address": f"0x{ROM_BASE + target:08X}",
            }
        )
    return {
        "scan": {
            "mode": "thumb",
            "alignment_bytes": 2,
            "range": [0, len(rom)],
            "target_file_offsets": sorted(targets),
            "matching_producer_count": len(records),
        },
        "producers": records,
        "denominator_sha256": _canonical_sha(records),
    }


def _return_record(rom: bytes, bx_offset: int) -> dict[str, Any]:
    prefix_start = bx_offset - 2
    prefix_end = bx_offset + 2
    prefix = rom[prefix_start:prefix_end]
    if prefix.hex() != RETURN_PREFIX or _sha(prefix) != RETURN_SHA256:
        raise ValueError(f"return idiom changed at 0x{bx_offset:06X}")
    if rom[bx_offset : bx_offset + 2] != b"\x00\x47":
        raise ValueError(f"return BX changed at 0x{bx_offset:06X}")
    return {
        "kind": "bx",
        "mode": "thumb",
        "bx_file_offset": bx_offset,
        "prefix_range": [prefix_start, prefix_end],
        "prefix_hex": RETURN_PREFIX,
        "prefix_sha256": RETURN_SHA256,
    }


def _merged_ranges(nodes: dict[tuple[str, int], dict[str, Any]]) -> list[list[int]]:
    ranges = sorted((offset, offset + node["size"]) for (_, offset), node in nodes.items())
    merged: list[list[int]] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _bounded_worklist(
    rom: bytes,
    root: int,
    bound: tuple[int, int],
    opaque_target: int | None,
) -> tuple[dict[tuple[str, int], dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    pending = [(root, 1, "thumb")]
    scheduled = {("thumb", root)}
    nodes: dict[tuple[str, int], dict[str, Any]] = {}
    rejected: dict[tuple[str, int], dict[str, Any]] = {}
    external: list[dict[str, Any]] = []
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in nodes or item in rejected:
            continue
        if offset < bound[0] or offset >= bound[1]:
            raise ValueError("bounded CFG worklist escaped frozen range")
        decoded = _decode_one(rom, offset, mode)
        if not decoded["accepted"]:
            rejected[item] = decoded
            continue
        if offset in (SOURCE_RETURN_BX, TARGET_RETURN_BX) and mode == "thumb":
            decoded = {**decoded, "flow_kind": "return", "frontiers": [], "successors": []}
        if offset + decoded["size"] > bound[1]:
            raise ValueError("bounded CFG instruction straddles frozen range")
        nodes[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            if not (bound[0] <= target[1] < bound[1]) or target[0] != "thumb":
                if edge["kind"] != "call_target":
                    raise ValueError("bounded CFG non-call edge escapes frozen range")
                reason = "target_producer" if target[1] == opaque_target else "opaque_external"
                external.append(
                    {
                        "source": {"mode": mode, "file_offset": offset},
                        "edge_kind": edge["kind"],
                        "target_mode": target[0],
                        "target_file_offset": target[1],
                        "reason": reason,
                    }
                )
                continue
            if target not in scheduled:
                heapq.heappush(pending, _key(*target))
                scheduled.add(target)
    blocks, _ = _build_blocks(rom, nodes, {("thumb", root)})
    return nodes, blocks, external


def _summary(nodes: dict[tuple[str, int], dict[str, Any]], blocks: list[dict[str, Any]], external: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "decoded_basic_block_count": len(blocks),
        "decoded_instruction_count": len(nodes),
        "frontier_count": sum(len(node["frontiers"]) for node in nodes.values()),
        "reachable_instruction_bytes": _union_bytes(
            [(offset, offset + node["size"]) for (_, offset), node in nodes.items()]
        ),
        "external_call_edge_count": len(external),
        "external_call_edge_reasons": dict(sorted(Counter(edge["reason"] for edge in external).items())),
    }


def _node_list(nodes: dict[tuple[str, int], dict[str, Any]]) -> list[dict[str, Any]]:
    return [nodes[item] for item in sorted(nodes, key=lambda key: _key(*key))]


def _source_worklist(rom: bytes) -> dict[str, Any]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    raw_slice = rom[SOURCE_RANGE[0] : SOURCE_RANGE[1]]
    if _sha(raw_slice) != SOURCE_SLICE_SHA256:
        raise ValueError("source selector slice changed")
    if rom[SOURCE_ROOT : SOURCE_ROOT + 4].hex() != SOURCE_ROOT_RAW:
        raise ValueError("source root bytes changed")
    return_record = _return_record(rom, SOURCE_RETURN_BX)
    nodes, blocks, external = _bounded_worklist(rom, SOURCE_ROOT, SOURCE_RANGE, TARGET_ROOT)
    summary = _summary(nodes, blocks, external)
    expected = {
        "decoded_instruction_count": 264,
        "decoded_basic_block_count": 35,
        "reachable_instruction_bytes": 580,
        "frontier_count": 0,
        "external_call_edge_count": 26,
        "external_call_edge_reasons": {"opaque_external": 24, "target_producer": 2},
    }
    if summary != expected:
        raise ValueError(f"source bounded CFG denominator changed: {summary}")
    block_ranges = [block["range"] for block in blocks]
    if _canonical_sha(block_ranges) != SOURCE_BLOCK_RANGE_SHA256:
        raise ValueError("source block range denominator changed")
    external_vector_sha256 = _canonical_sha(external)
    if external_vector_sha256 != SOURCE_EXTERNAL_VECTOR_SHA256:
        raise ValueError("source external edge vector denominator changed")
    if len([edge for edge in external if edge["reason"] == "target_producer"]) != 2:
        raise ValueError("source target-producer edge denominator changed")
    return {
        "range": list(SOURCE_RANGE),
        "size": SOURCE_RANGE[1] - SOURCE_RANGE[0],
        "slice_sha256": SOURCE_SLICE_SHA256,
        "nodes": _node_list(nodes),
        "blocks": blocks,
        "frontiers": [],
        "external_edges": external,
        "external_vector_sha256": external_vector_sha256,
        "block_range_sha256": SOURCE_BLOCK_RANGE_SHA256,
        "merged_ranges": _merged_ranges(nodes),
        "summary": summary,
        "frontier_count": 0,
        "return": return_record,
    }


def _literal_records(rom: bytes) -> list[dict[str, Any]]:
    records = []
    for ldr_offset, ldr_raw, literal_range in LITERAL_SPECS:
        actual_ldr = rom[ldr_offset : ldr_offset + 2]
        if actual_ldr.hex() != ldr_raw:
            raise ValueError(f"LDR literal instruction changed at 0x{ldr_offset:06X}")
        halfword = int.from_bytes(actual_ldr, "little")
        computed_start = ((ldr_offset + 4) & ~3) + (halfword & 0xFF) * 4
        if computed_start != literal_range[0] or literal_range[1] != computed_start + 4:
            raise ValueError("LDR literal address formula changed")
        raw = rom[literal_range[0] : literal_range[1]]
        if raw.hex() != LITERAL_RAW or int.from_bytes(raw, "little") != LITERAL_VALUE:
            raise ValueError(f"literal bytes changed at 0x{literal_range[0]:06X}")
        records.append(
            {
                "ldr_file_offset": ldr_offset,
                "ldr_raw_hex": ldr_raw,
                "literal_range": list(literal_range),
                "literal_raw_hex": LITERAL_RAW,
                "value_u32": LITERAL_VALUE,
                "bytes_sha256": _sha(raw),
            }
        )
    return records


def _target_worklist(rom: bytes) -> dict[str, Any]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    envelope = rom[TARGET_ENVELOPE[0] : TARGET_ENVELOPE[1]]
    if _sha(envelope) != ENVELOPE_SHA256:
        raise ValueError("target envelope changed")
    if rom[TARGET_ROOT : TARGET_ROOT + 4].hex() != TARGET_ROOT_RAW:
        raise ValueError("target root bytes changed")
    return_record = _return_record(rom, TARGET_RETURN_BX)
    literals = _literal_records(rom)
    nodes, blocks, external = _bounded_worklist(rom, TARGET_ROOT, TARGET_RANGE, None)
    summary = _summary(nodes, blocks, external)
    expected = {
        "decoded_instruction_count": 36,
        "decoded_basic_block_count": 7,
        "reachable_instruction_bytes": 72,
        "frontier_count": 0,
        "external_call_edge_count": 0,
        "external_call_edge_reasons": {},
    }
    if summary != expected:
        raise ValueError(f"target bounded CFG denominator changed: {summary}")
    block_ranges = [block["range"] for block in blocks]
    if _canonical_sha(block_ranges) != TARGET_BLOCK_RANGE_SHA256:
        raise ValueError("target block range denominator changed")
    literal_ranges = [item["literal_range"] for item in literals]
    if _canonical_sha(literal_ranges) != LITERAL_RANGE_SHA256:
        raise ValueError("literal range denominator changed")
    packed = b"".join(bytes.fromhex(item["literal_raw_hex"]) for item in literals)
    if _sha(packed) != PACKED_LITERAL_SHA256:
        raise ValueError("packed literal denominator changed")
    return {
        "envelope": list(TARGET_ENVELOPE),
        "envelope_size": TARGET_ENVELOPE[1] - TARGET_ENVELOPE[0],
        "envelope_sha256": ENVELOPE_SHA256,
        "code_ranges": [[0x08B278, 0x08B2B0], [0x08B2B4, 0x08B2C4]],
        "nodes": _node_list(nodes),
        "blocks": blocks,
        "frontiers": [],
        "external_edges": external,
        "block_range_sha256": TARGET_BLOCK_RANGE_SHA256,
        "summary": summary,
        "frontier_count": 0,
        "return": return_record,
        "literals": literals,
        "literal_range_sha256": LITERAL_RANGE_SHA256,
        "packed_literals_sha256": PACKED_LITERAL_SHA256,
    }


def _coverage_baseline(root: Path, promotion_ranges: list[list[int]]) -> dict[str, Any]:
    raw = _safe_file(Path(root).resolve(strict=True), COVERAGE_PATH).read_bytes()
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage identity changed")
    coverage = json.loads(raw)
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage schema changed")
    if coverage.get("base_rom") != {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256}:
        raise ValueError("coverage ROM identity changed")
    if promotion_ranges != [list(TARGET_ENVELOPE)]:
        raise ValueError("promotion envelope denominator changed")
    unknown = 0
    known = 0
    for segment in coverage.get("segments", []):
        start, end = segment.get("range", [-1, -1])
        overlap = max(0, min(end, TARGET_ENVELOPE[1]) - max(start, TARGET_ENVELOPE[0]))
        if segment.get("primary_class") == "unknown":
            unknown += overlap
        else:
            known += overlap
    if known:
        raise ValueError(f"coverage marks {known} current known overlap bytes")
    if unknown != 80:
        raise ValueError(f"coverage prebaseline unknown bytes changed: {unknown}")
    return {
        "path": COVERAGE_PATH.as_posix(),
        "sha256": COVERAGE_SHA256,
        "promotion_envelope": list(TARGET_ENVELOPE),
        "promotion_bytes": 80,
        "promotion_code_bytes": 72,
        "promotion_literal_bytes": 8,
        "current_unknown_bytes": unknown,
        "current_known_overlap_bytes": known,
        "unknown_bytes": unknown,
    }


def _upstream_contract(root: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    payload_path = _safe_file(root, UPSTREAM["payload_path"])
    manifest_path = _safe_file(root, UPSTREAM["manifest_path"])
    verifier_path = _safe_file(root, UPSTREAM["verifier_path"])
    if _sha(payload_path.read_bytes()) != UPSTREAM["payload_sha256"]:
        raise ValueError("selector-text upstream payload identity changed")
    if _sha(manifest_path.read_bytes()) != UPSTREAM["manifest_sha256"]:
        raise ValueError("selector-text upstream manifest identity changed")
    if _sha(verifier_path.read_bytes()) != UPSTREAM["verifier_sha256"]:
        raise ValueError("selector-text upstream verifier identity changed")
    payload = json.loads(payload_path.read_bytes())
    if payload.get("schema") != UPSTREAM["artifact_schema"]:
        raise ValueError("selector-text upstream schema changed")
    menu = payload.get("consumer_evidence", {}).get("direct_producer", {}).get("menu_selector", {})
    if menu.get("range") != UPSTREAM["menu_selector_range"] or menu.get("sha256") != SOURCE_SLICE_SHA256:
        raise ValueError("selector-text upstream menu selector range changed")
    from tools.verify_rom_selector_text_bindings import verify_artifact

    report = verify_artifact(root, root / "artifacts/rom-selector-text-bindings-v1")
    if report.get("schema") != UPSTREAM["verification_schema"] or report.get("verified") is not True or report.get("errors") != []:
        raise ValueError(f"selector-text upstream independent verification failed: {report}")
    return dict(UPSTREAM)


def _implementation(root: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    paths = {
        "exporter": Path("tools/export_rom_cfg_proven_roots_v10.py"),
        "verifier": Path("tools/verify_rom_cfg_proven_roots_v10.py"),
        "test": Path("tests/test_export_rom_cfg_proven_roots_v10.py"),
    }
    dependencies: dict[str, str] = {}
    for relative in RUNTIME_DEPENDENCY_PATHS:
        dependencies[relative.as_posix()] = _sha(_safe_file(root, relative).read_bytes())
    result = {
        "binding": "passed-root-runtime-dependency-and-test-hash-bound",
        "paths": {label: path.as_posix() for label, path in paths.items()},
        "exporter_sha256": _sha(_safe_file(root, paths["exporter"]).read_bytes()),
        "verifier_sha256": _sha(_safe_file(root, paths["verifier"]).read_bytes()),
        "test_sha256": _sha(_safe_file(root, paths["test"]).read_bytes()),
        "runtime_dependency_sha256": dependencies,
    }
    return result


def build_cfg_proven_roots_v10_payload(root: Path, rom: bytes | None = None) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    if rom is None:
        rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    source_worklist = _source_worklist(rom)
    target_worklist = _target_worklist(rom)
    denominator = _producer_denominator(rom)
    producer_map = {(item["file_offset"], item["target_file_offset"]): item for item in denominator["producers"]}
    source = {
        "root": {
            "mode": "thumb",
            "file_offset": SOURCE_ROOT,
            "entry_raw_hex": SOURCE_ROOT_RAW,
            "entry_sha256": SOURCE_ROOT_SHA256,
        },
        "producer": producer_map[(SOURCE_PRODUCER, SOURCE_ROOT)],
        "return": source_worklist.pop("return"),
        "worklist": source_worklist,
    }
    target = {
        "root": {
            "mode": "thumb",
            "file_offset": TARGET_ROOT,
            "entry_raw_hex": TARGET_ROOT_RAW,
            "entry_sha256": TARGET_ROOT_SHA256,
        },
        "producers": [producer_map[(offset, TARGET_ROOT)] for offset, _, _, _ in TARGET_PRODUCERS],
        "return": target_worklist.pop("return"),
        "worklist": target_worklist,
    }
    coverage = _coverage_baseline(root, [list(TARGET_ENVELOPE)])
    implementation = _implementation(root)
    promotion = {
        "envelope": list(TARGET_ENVELOPE),
        "envelope_sha256": ENVELOPE_SHA256,
        "promotion_bytes": 80,
        "promotion_code_bytes": 72,
        "promotion_literal_bytes": 8,
        "current_known_overlap_bytes": 0,
    }
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},
        "upstream": _upstream_contract(root),
        "source": source,
        "target": target,
        "promotion": promotion,
        "coverage_baseline": coverage,
        "implementation": implementation,
        "scope": dict(SCOPE),
    }


def _receipt_commands(root: Path, output: Path) -> tuple[list[str], list[str]]:
    relative_output = output.resolve(strict=False).relative_to(root).as_posix()
    producer = [
        "python3",
        "-I",
        "-S",
        "tools/export_rom_cfg_proven_roots_v10.py",
        "--root",
        ".",
        "--output-dir",
        relative_output,
    ]
    verifier = [
        "python3",
        "-I",
        "-S",
        "tools/verify_rom_cfg_proven_roots_v10.py",
        "--root",
        ".",
        "--artifact-dir",
        relative_output,
    ]
    return producer, verifier


def _promotion_manifest(
    root: Path,
    output: Path,
    payload: dict[str, Any],
    payload_raw: bytes,
    *,
    status: str,
    report: dict[str, Any] | None,
) -> dict[str, Any]:
    if status not in {"candidate", "accepted"}:
        raise ValueError("invalid CFG v10 promotion status")
    if (status == "accepted") != (report is not None):
        raise ValueError("CFG v10 verifier receipt/status mismatch")
    producer_command, verifier_command = _receipt_commands(root, output)
    implementation = payload["implementation"]
    verifier_receipt = {
        "schema": VERIFY_SCHEMA,
        "command": verifier_command,
        "exit_code": 0 if report is not None else None,
        "report": report,
        "verifier_sha256": implementation["verifier_sha256"],
    }
    return {
        "schema": PROMOTION_SCHEMA,
        "artifact_schema": SCHEMA,
        "artifact_status": status,
        "rom": payload["rom"],
        "upstream": payload["upstream"],
        "source": payload["source"],
        "target": payload["target"],
        "promotion": payload["promotion"],
        "coverage_baseline": payload["coverage_baseline"],
        "files": {PAYLOAD_NAME: _sha(payload_raw)},
        "producer": {
            "command": producer_command,
            "implementation": implementation,
        },
        "verifier": verifier_receipt,
        "implementation": implementation,
        "scope": payload["scope"],
    }


def _run_isolated_verifier(root: Path, command: list[str]) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        command,
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"independent CFG v10 verifier rejected candidate: {detail}")
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("independent CFG v10 verifier returned invalid JSON") from error
    if report != EXPECTED_REPORT:
        raise ValueError(f"independent CFG v10 verifier report changed: {report}")
    return report


def _write_manifest_atomic(output: Path, manifest: dict[str, Any]) -> None:
    temporary = output / f".{MANIFEST_NAME}.{uuid.uuid4().hex}.tmp"
    try:
        temporary.write_bytes(_canonical_json(manifest))
        os.replace(temporary, output / MANIFEST_NAME)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_output_dir(root: Path, output_dir: Path) -> Path:
    root = Path(root).resolve(strict=True)
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested)
    target = requested.resolve(strict=False)
    experiment = (root / EXPERIMENT_OUTPUT_ROOT).resolve(strict=False)
    try:
        target.relative_to(experiment)
    except ValueError as error:
        raise ValueError("CFG v10 output must stay inside experiment subtree") from error
    if target == experiment:
        raise ValueError("CFG v10 output cannot be experiment root")
    if target.exists():
        if not target.is_dir():
            raise ValueError("CFG v10 output is not a directory")
        members = list(target.iterdir())
        if not members:
            return target
        if {item.name for item in members} != {MANIFEST_NAME, PAYLOAD_NAME} or any(item.is_symlink() or not item.is_file() for item in members):
            raise ValueError("CFG v10 output is a foreign non-empty directory")
        from tools.verify_rom_cfg_proven_roots_v10 import verify_rom_cfg_proven_roots_v10

        report = verify_rom_cfg_proven_roots_v10(root, target)
        if report.get("verified") is not True:
            raise ValueError(f"existing same-schema v10 output failed independent verification: {report.get('errors', [])}")
    return target


def export_rom_cfg_proven_roots_v10(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output = _validate_output_dir(root, output_dir)
    payload = build_cfg_proven_roots_v10_payload(root)
    payload_raw = _canonical_json(payload)
    candidate = _promotion_manifest(
        root, output, payload, payload_raw, status="candidate", report=None
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".rom-cfg-proven-roots-v10-", dir=output.parent))
    backup: Path | None = None
    committed = False
    try:
        (temporary / PAYLOAD_NAME).write_bytes(payload_raw)
        (temporary / MANIFEST_NAME).write_bytes(_canonical_json(candidate))
        if output.exists():
            backup = output.with_name(f".{output.name}.old-{uuid.uuid4().hex}")
            os.replace(output, backup)
        os.replace(temporary, output)
        report = _run_isolated_verifier(root, candidate["verifier"]["command"])
        accepted = _promotion_manifest(
            root, output, payload, payload_raw, status="accepted", report=report
        )
        _write_manifest_atomic(output, accepted)
        postflight_report = _run_isolated_verifier(
            root, accepted["verifier"]["command"]
        )
        if postflight_report != report:
            raise ValueError("accepted postflight verifier report changed")
        committed = True
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
        return accepted
    except BaseException:
        if not committed:
            failed: Path | None = None
            if output.exists():
                failed = output.with_name(f".{output.name}.failed-{uuid.uuid4().hex}")
                os.replace(output, failed)
            if backup is not None and backup.exists():
                os.replace(backup, output)
                backup = None
            if failed is not None and failed.exists():
                shutil.rmtree(failed)
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists() and not output.exists():
            os.replace(backup, output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = export_rom_cfg_proven_roots_v10(args.root, args.output_dir)
    print(json.dumps(manifest["promotion"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
