#!/usr/bin/env python3
"""Export the frozen table-rooted event-handler Thumb CFG packet."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import heapq
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"


def _require_isolated_cli_runtime() -> None:
    if __name__ != "__main__":
        return
    if not sys.flags.isolated or not sys.flags.no_site:
        raise RuntimeError("event-handler CFG CLI requires Python -I -S isolation")
    if "capstone" in sys.modules or os.environ.get("LIBCAPSTONE_PATH"):
        raise RuntimeError("event-handler CFG CLI rejects Capstone overrides")


_require_isolated_cli_runtime()
for _root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from tools import rom_event_handler_cfg_contract as C  # noqa: E402
from tools.export_rom_cfg_inventory import (  # noqa: E402
    _build_blocks,
    _decode_one,
    _reject_symlink_components,
    _safe_file,
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _assert_oracle_identities(root: Path) -> None:
    for identity in C.ORACLE_IDENTITIES.values():
        path = Path(identity["path"])
        if _sha(_safe_file(root, path).read_bytes()) != identity["sha256"]:
            raise ValueError(f"frozen decoder oracle identity changed: {path.as_posix()}")


def _vector_sha(value: object) -> str:
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


class _EscapedBound(ValueError):
    def __init__(self, source: int, target: int):
        super().__init__("non-call edge escaped frozen unknown bound")
        self.source = source
        self.target = target


def _producer_denominator(rom: bytes) -> dict[str, Any]:
    raw = rom[C.TABLE_RANGE[0] : C.TABLE_RANGE[1]]
    if len(raw) != C.TABLE_BYTES or _sha(raw) != C.TABLE_SHA256:
        raise ValueError("event-handler producer table changed")
    matching: list[list[int]] = []
    null_count = 0
    other_count = 0
    for slot, offset in enumerate(range(*C.TABLE_RANGE, 4)):
        value = struct.unpack_from("<I", rom, offset)[0]
        target = value - C.ROM_BASE - 1
        if value == 0:
            null_count += 1
        elif value & 1 and C.UNKNOWN_BOUND[0] <= target < C.UNKNOWN_BOUND[1]:
            matching.append([slot, offset, value, target])
        else:
            other_count += 1
    roots = sorted({row[3] for row in matching})
    occurrences = sorted(Counter(row[3] for row in matching).items())
    checks = (
        (len(matching), C.MATCHING_SLOT_COUNT, "matching slot count"),
        (null_count, C.NULL_SLOT_COUNT, "null slot count"),
        (other_count, C.OTHER_SLOT_COUNT, "other slot count"),
        (roots, list(C.ROOT_VECTOR), "root vector"),
        (_vector_sha(matching), C.MATCHING_SLOT_VECTOR_SHA256, "matching slot vector"),
        (_vector_sha(roots), C.ROOT_VECTOR_SHA256, "root vector hash"),
        (_vector_sha(occurrences), C.OCCURRENCE_VECTOR_SHA256, "occurrence vector"),
    )
    for actual, expected, label in checks:
        if actual != expected:
            raise ValueError(f"event-handler {label} changed")
    return {
        "range": list(C.TABLE_RANGE),
        "bytes": len(raw),
        "u32_slot_count": len(raw) // 4,
        "null_slot_count": null_count,
        "matching_slot_count": len(matching),
        "other_slot_count": other_count,
        "unique_root_count": len(roots),
        "table_sha256": _sha(raw),
        "matching_slots": matching,
        "root_occurrences": [list(row) for row in occurrences],
        "matching_slot_vector_sha256": _vector_sha(matching),
        "root_vector_sha256": _vector_sha(roots),
        "occurrence_vector_sha256": _vector_sha(occurrences),
    }


def _decode_root(rom: bytes, root: int) -> tuple[dict[tuple[str, int], dict[str, Any]], list[dict[str, Any]], list[list[Any]], list[list[Any]]]:
    pending = [(root, 1, "thumb")]
    scheduled = {("thumb", root)}
    nodes: dict[tuple[str, int], dict[str, Any]] = {}
    external: list[list[Any]] = []
    opaque: list[list[Any]] = []
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in nodes:
            continue
        if mode != "thumb" or not (C.UNKNOWN_BOUND[0] <= offset < C.UNKNOWN_BOUND[1]):
            raise _EscapedBound(offset, offset)
        decoded = _decode_one(rom, offset, mode)
        if not decoded["accepted"]:
            raise ValueError(f"raw CFG decode frontier at 0x{offset:06X}")
        if offset + decoded["size"] > C.UNKNOWN_BOUND[1]:
            raise _EscapedBound(offset, offset + decoded["size"])
        nodes[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            if target[0] == "thumb" and C.UNKNOWN_BOUND[0] <= target[1] < C.UNKNOWN_BOUND[1]:
                if target not in scheduled:
                    scheduled.add(target)
                    heapq.heappush(pending, (target[1], 1, target[0]))
            elif edge["kind"] == "call_target":
                external.append([offset, target[1], edge["kind"]])
            elif target[0] == "thumb" and any(a <= target[1] < b for a, b in C.OPAQUE_ACCEPTED_RANGES):
                opaque.append([offset, target[1], edge["kind"]])
            else:
                raise _EscapedBound(offset, target[1])
    blocks, _ = _build_blocks(rom, nodes, {("thumb", root)})
    return nodes, blocks, sorted(external), sorted(opaque)


def _merge(ranges: list[list[int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for start, end in sorted(ranges):
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def _cfg_rebuild(rom: bytes) -> dict[str, Any]:
    denominator = _producer_denominator(rom)
    roots = sorted({row[3] for row in denominator["matching_slots"]})
    all_nodes: dict[tuple[str, int], dict[str, Any]] = {}
    accepted: list[int] = []
    rejected: list[dict[str, Any]] = []
    external: set[tuple[Any, ...]] = set()
    opaque: set[tuple[Any, ...]] = set()
    for root in roots:
        try:
            nodes, _, root_external, root_opaque = _decode_root(rom, root)
        except _EscapedBound as error:
            rejected.append({"root": root, "reason": "non_call_edge_escaped_unknown_bound", "source_file_offset": error.source, "target_file_offset": error.target})
            continue
        accepted.append(root)
        all_nodes.update(nodes)
        external.update(map(tuple, root_external))
        opaque.update(map(tuple, root_opaque))
    if accepted != list(C.ACCEPTED_ROOTS) or rejected != [C.REJECTION_EVIDENCE]:
        raise ValueError("accepted/rejected event-handler root contract changed")
    blocks, _ = _build_blocks(rom, all_nodes, {("thumb", root) for root in accepted})
    ordered_nodes = [all_nodes[key] for key in sorted(all_nodes, key=lambda item: (item[1], item[0]))]
    instruction_edges = list({
        (node["file_offset"], edge["file_offset"], edge["kind"])
        for node in ordered_nodes for edge in node["successors"]
        if (edge["mode"], edge["file_offset"]) in all_nodes
    })
    instruction_edges.sort()
    block_edges = list({
        (block["terminator"]["file_offset"], edge["file_offset"], edge["kind"])
        for block in blocks for edge in block["successors"]
    })
    block_edges.sort()
    block_ranges = [block["range"] for block in blocks]
    semantic = [[node["file_offset"], node["size"], node["mnemonic"], node["op_str"]] for node in ordered_nodes]
    frontiers = sorted([node["file_offset"], frontier["reason"]] for node in ordered_nodes for frontier in node["frontiers"])
    result = {
        "instruction_count": len(all_nodes),
        "code_bytes": sum(node["size"] for node in all_nodes.values()),
        "block_count": len(blocks),
        "instruction_internal_edge_count": len(instruction_edges),
        "block_internal_edge_count": len(block_edges),
        "external_call_edge_count": len(external),
        "frontier_count": len(frontiers),
        "opaque_edge_count": len(opaque),
        "semantic_vector_sha256": _vector_sha(semantic),
        "instruction_internal_edge_vector_sha256": _vector_sha([list(row) for row in instruction_edges]),
        "block_range_vector_sha256": _vector_sha(block_ranges),
        "block_internal_edge_vector_sha256": _vector_sha([list(row) for row in block_edges]),
        "external_call_vector_sha256": _vector_sha([list(row) + ["opaque_external"] for row in sorted(external)]),
        "frontier_vector_sha256": _vector_sha(frontiers),
        "opaque_edge_vector_sha256": _vector_sha([list(row) for row in sorted(opaque)]),
        "literal_source_nodes": ordered_nodes,
    }
    expected = {
        "instruction_count": C.CFG_INSTRUCTION_COUNT,
        "code_bytes": C.CFG_CODE_BYTES,
        "block_count": C.CFG_BLOCK_COUNT,
        "instruction_internal_edge_count": C.CFG_INSTRUCTION_INTERNAL_EDGE_COUNT,
        "block_internal_edge_count": C.CFG_BLOCK_INTERNAL_EDGE_COUNT,
        "external_call_edge_count": C.CFG_EXTERNAL_CALL_EDGE_COUNT,
        "frontier_count": C.CFG_FRONTIER_COUNT,
        "opaque_edge_count": C.CFG_OPAQUE_EDGE_COUNT,
        "semantic_vector_sha256": C.CFG_SEMANTIC_VECTOR_SHA256,
        "instruction_internal_edge_vector_sha256": C.CFG_INSTRUCTION_INTERNAL_EDGE_VECTOR_SHA256,
        "block_range_vector_sha256": C.CFG_BLOCK_RANGE_VECTOR_SHA256,
        "block_internal_edge_vector_sha256": C.CFG_BLOCK_INTERNAL_EDGE_VECTOR_SHA256,
        "external_call_vector_sha256": C.CFG_EXTERNAL_CALL_VECTOR_SHA256,
        "frontier_vector_sha256": C.CFG_FRONTIER_VECTOR_SHA256,
        "opaque_edge_vector_sha256": C.CFG_OPAQUE_EDGE_VECTOR_SHA256,
    }
    observed = {key: result[key] for key in expected}
    if observed != expected:
        differing = {key: (observed[key], expected[key]) for key in expected if observed[key] != expected[key]}
        raise ValueError(f"event-handler CFG vector changed: {differing}")
    return result


def _promotion(rom: bytes, nodes: list[dict[str, Any]]) -> dict[str, Any]:
    code_ranges = _merge([[node["file_offset"], node["file_offset"] + node["size"]] for node in nodes])
    bindings: list[list[int]] = []
    words: set[int] = set()
    for node in nodes:
        offset = node["file_offset"]
        halfword = struct.unpack_from("<H", rom, offset)[0]
        if node["size"] == 2 and halfword & 0xF800 == 0x4800:
            target = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
            if not (C.UNKNOWN_BOUND[0] <= target and target + 4 <= C.UNKNOWN_BOUND[1]):
                raise ValueError("consumed literal escaped candidate bound")
            if any(a < target + 4 and target < b for a, b in code_ranges):
                raise ValueError("consumed literal overlaps reachable code")
            bindings.append([offset, target])
            words.add(target)
    literal_ranges = _merge([[offset, offset + 4] for offset in sorted(words)])
    semantic_ranges = sorted([[a, b, "reachable_thumb_code"] for a, b in code_ranges] + [[a, b, "consumed_literal_word"] for a, b in literal_ranges])
    union_ranges = _merge([[a, b] for a, b, _ in semantic_ranges])
    cursor = C.UNKNOWN_BOUND[0]
    holes: list[list[int]] = []
    for start, end in union_ranges:
        if cursor < start:
            holes.append([cursor, start])
        cursor = end
    if cursor < C.UNKNOWN_BOUND[1]:
        holes.append([cursor, C.UNKNOWN_BOUND[1]])
    result = {
        "code_ranges": code_ranges,
        "literal_ranges": literal_ranges,
        "semantic_ranges": semantic_ranges,
        "union_ranges": union_ranges,
        "preserved_unknown_holes": holes,
        "code_bytes": sum(b - a for a, b in code_ranges),
        "literal_bytes": sum(b - a for a, b in literal_ranges),
        "bytes": sum(b - a for a, b in union_ranges),
        "preserved_unknown_hole_bytes": sum(b - a for a, b in holes),
        "code_range_vector_sha256": _vector_sha(code_ranges),
        "literal_range_vector_sha256": _vector_sha(literal_ranges),
        "semantic_range_vector_sha256": _vector_sha(semantic_ranges),
        "union_range_vector_sha256": _vector_sha(union_ranges),
        "hole_range_vector_sha256": _vector_sha(holes),
        "literal_binding_vector_sha256": _vector_sha(sorted(bindings)),
        "packed_code_sha256": _sha(b"".join(rom[a:b] for a, b in code_ranges)),
        "packed_literal_sha256": _sha(b"".join(rom[a:b] for a, b in literal_ranges)),
        "packed_sha256": _sha(b"".join(rom[a:b] for a, b in union_ranges)),
    }
    frozen = {
        "code_ranges": [list(row) for row in C.CODE_RANGES], "literal_ranges": [list(row) for row in C.LITERAL_RANGES],
        "semantic_ranges": [list(row) for row in C.SEMANTIC_RANGES], "union_ranges": [list(row) for row in C.UNION_RANGES],
        "preserved_unknown_holes": [list(row) for row in C.PRESERVED_UNKNOWN_HOLES],
        "code_bytes": C.CFG_CODE_BYTES, "literal_bytes": 152, "bytes": 4062, "preserved_unknown_hole_bytes": 174,
        "code_range_vector_sha256": C.CODE_RANGE_VECTOR_SHA256, "literal_range_vector_sha256": C.LITERAL_RANGE_VECTOR_SHA256,
        "semantic_range_vector_sha256": C.SEMANTIC_RANGE_VECTOR_SHA256, "union_range_vector_sha256": C.UNION_RANGE_VECTOR_SHA256,
        "hole_range_vector_sha256": C.HOLE_RANGE_VECTOR_SHA256, "literal_binding_vector_sha256": C.LITERAL_BINDING_VECTOR_SHA256,
        "packed_code_sha256": C.PACKED_CODE_SHA256, "packed_literal_sha256": C.PACKED_LITERAL_SHA256, "packed_sha256": C.PACKED_PROMOTION_SHA256,
    }
    if result != frozen:
        differing = {key: (result[key], frozen[key]) for key in frozen if result[key] != frozen[key]}
        raise ValueError(f"event-handler promotion vector changed: {differing}")
    return result


def _coverage(root: Path) -> dict[str, Any]:
    raw = _safe_file(root, C.COVERAGE_PATH).read_bytes()
    if _sha(raw) != C.COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    coverage = json.loads(raw)
    summary = coverage.get("summary", {})
    for key in ("classified_bytes", "unknown_bytes", "claim_count", "segment_count"):
        if summary.get(key) != C.COVERAGE_EXPECTED[key]:
            raise ValueError("coverage baseline summary changed")
    owners = [row for row in coverage["segments"] if row["range"][0] < C.UNKNOWN_BOUND[1] and C.UNKNOWN_BOUND[0] < row["range"][1]]
    table = [row for row in coverage["segments"] if row["range"][0] < C.TABLE_RANGE[1] and C.TABLE_RANGE[0] < row["range"][1]]
    if owners != [C.UNKNOWN_OWNER] or table != [C.TABLE_OWNER]:
        raise ValueError("coverage owner projection changed")
    return {
        **C.COVERAGE_EXPECTED,
        "current_unknown_only": True,
        "candidate_owner": owners[0],
        "producer_owner": table[0],
        "promoted_from_unknown_bytes": 4062,
    }


def _implementation(root: Path) -> dict[str, Any]:
    paths = {
        "exporter": Path("tools/export_rom_event_handler_cfg.py"), "verifier": Path("tools/verify_rom_event_handler_cfg.py"),
        "test_exporter": Path("tests/test_export_rom_event_handler_cfg.py"), "test_verifier": Path("tests/test_verify_rom_event_handler_cfg.py"),
    }
    runtime = tuple(C.RUNTIME_DEPENDENCY_PATHS)
    return {
        "binding": "runtime-dependency-and-test-hash-bound",
        "paths": {key: path.as_posix() for key, path in paths.items()},
        **{f"{key}_sha256": _sha(_safe_file(root, path).read_bytes()) for key, path in paths.items()},
        "runtime_dependency_sha256": {path.as_posix(): _sha(_safe_file(root, path).read_bytes()) for path in runtime},
    }


def build_rom_event_handler_cfg_payload(root: Path, rom: bytes | None = None) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    _assert_oracle_identities(root)
    if rom is None:
        rom = _safe_file(root, C.ROM_PATH).read_bytes()
    if len(rom) != C.ROM_SIZE or _sha(rom) != C.ROM_SHA256:
        raise ValueError("base ROM identity changed")
    cfg = _cfg_rebuild(rom)
    promotion = _promotion(rom, cfg.pop("literal_source_nodes"))
    return {
        "schema": C.SCHEMA,
        "rom": {"path": C.ROM_PATH.as_posix(), "size": C.ROM_SIZE, "sha256": C.ROM_SHA256},
        "producer_denominator": _producer_denominator(rom),
        "accepted_roots": list(C.ACCEPTED_ROOTS), "rejected_roots": list(C.REJECTED_ROOTS),
        "rejection_evidence": dict(C.REJECTION_EVIDENCE),
        "candidate_unknown_range": list(C.UNKNOWN_BOUND), "opaque_accepted_ranges": [list(row) for row in C.OPAQUE_ACCEPTED_RANGES],
        "cfg": cfg, "promotion": promotion, "coverage_baseline": _coverage(root),
        "implementation": _implementation(root), "scope": dict(C.SCOPE),
    }


EXPECTED_REPORT = {
    "schema": C.VERIFY_SCHEMA, "verified": True, "errors": [], "accepted_root_count": len(C.ACCEPTED_ROOTS),
    "rejected_roots": list(C.REJECTED_ROOTS), "instruction_count": C.CFG_INSTRUCTION_COUNT, "code_bytes": C.CFG_CODE_BYTES,
    "block_count": C.CFG_BLOCK_COUNT, "frontier_count": C.CFG_FRONTIER_COUNT, "opaque_edge_count": C.CFG_OPAQUE_EDGE_COUNT,
    "promotion_bytes": 4062, "preserved_unknown_hole_bytes": 174, "nonclaims": {name: False for name in C.NONCLAIMS},
}


def _receipt_commands(root: Path, output: Path) -> tuple[list[str], list[str]]:
    relative = output.resolve(strict=False).relative_to(root).as_posix()
    return (
        ["python3", "-I", "-S", "tools/export_rom_event_handler_cfg.py", "--root", ".", "--output-dir", relative],
        ["python3", "-I", "-S", "tools/verify_rom_event_handler_cfg.py", "--root", ".", "--artifact-dir", relative],
    )


def _manifest(root: Path, output: Path, payload: dict[str, Any], raw: bytes, status: str, report: dict[str, Any] | None) -> dict[str, Any]:
    producer, verifier = _receipt_commands(root, output)
    return {
        "schema": C.PROMOTION_SCHEMA, "artifact_schema": C.SCHEMA, "artifact_status": status,
        "rom": payload["rom"], "producer_denominator": payload["producer_denominator"], "cfg": payload["cfg"], "promotion": payload["promotion"],
        "coverage_baseline": payload["coverage_baseline"], "files": {C.PAYLOAD_NAME: {"size": len(raw), "sha256": _sha(raw)}},
        "producer": {"command": producer, "implementation": payload["implementation"]},
        "verifier": {"schema": C.VERIFY_SCHEMA, "command": verifier, "exit_code": 0 if report else None, "report": report, "verifier_sha256": payload["implementation"]["verifier_sha256"]},
        "implementation": payload["implementation"], "scope": payload["scope"],
    }


def _run_isolated_verifier(root: Path, command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    if completed.returncode:
        raise ValueError(completed.stderr.strip() or completed.stdout.strip() or "independent verifier failed")
    report = json.loads(completed.stdout)
    if report != EXPECTED_REPORT:
        raise ValueError("independent verifier report changed")
    return report


def _validate_output(root: Path, output_dir: Path) -> Path:
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested)
    target = requested.resolve(strict=False)
    experiment = (root / C.EXPERIMENT_OUTPUT_ROOT).resolve(strict=False)
    official = (root / C.OFFICIAL_ARTIFACT).resolve(strict=False)
    if target != official and (target == experiment or experiment not in target.parents):
        raise ValueError("event-handler CFG output escaped experiment subtree")
    if target.exists():
        if not target.is_dir():
            raise ValueError("event-handler CFG output is not a directory")
        members = list(target.iterdir())
        if members and ({p.name for p in members} != {C.MANIFEST_NAME, C.PAYLOAD_NAME} or any(p.is_symlink() or not p.is_file() for p in members)):
            raise ValueError("event-handler CFG output is a foreign non-empty directory")
    return target


def export_rom_event_handler_cfg(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output = _validate_output(root, output_dir)
    payload = build_rom_event_handler_cfg_payload(root)
    raw = _canonical(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".rom-event-handler-cfg-", dir=output.parent))
    backup: Path | None = None
    committed = False
    try:
        candidate = _manifest(root, output, payload, raw, "candidate", None)
        (temporary / C.PAYLOAD_NAME).write_bytes(raw)
        (temporary / C.MANIFEST_NAME).write_bytes(_canonical(candidate))
        if output.exists():
            backup = output.with_name(f".{output.name}.backup-{uuid.uuid4().hex}")
            os.replace(output, backup)
        os.replace(temporary, output)
        report = _run_isolated_verifier(root, candidate["verifier"]["command"])
        accepted = _manifest(root, output, payload, raw, "accepted", report)
        manifest_tmp = output / f".{C.MANIFEST_NAME}.{uuid.uuid4().hex}.tmp"
        manifest_tmp.write_bytes(_canonical(accepted))
        os.replace(manifest_tmp, output / C.MANIFEST_NAME)
        if _run_isolated_verifier(root, accepted["verifier"]["command"]) != report:
            raise ValueError("accepted verifier postflight changed")
        committed = True
        if backup:
            shutil.rmtree(backup)
            backup = None
        return accepted
    except BaseException:
        if not committed:
            failed = None
            if output.exists():
                failed = output.with_name(f".{output.name}.failed-{uuid.uuid4().hex}")
                os.replace(output, failed)
            if backup and backup.exists():
                os.replace(backup, output)
                backup = None
            if failed and failed.exists():
                shutil.rmtree(failed)
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup and backup.exists() and not output.exists():
            os.replace(backup, output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = export_rom_event_handler_cfg(args.root, args.output_dir)
    print(json.dumps(manifest["promotion"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
