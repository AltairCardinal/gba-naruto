#!/usr/bin/env python3
"""Independently verify the frozen event-handler table-rooted CFG artifact."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import heapq
import json
import os
from pathlib import Path
import struct
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"


def _require_isolated_cli_runtime() -> None:
    if __name__ != "__main__":
        return
    if not sys.flags.isolated or not sys.flags.no_site:
        raise RuntimeError("event-handler CFG verifier requires Python -I -S isolation")
    if "capstone" in sys.modules or os.environ.get("LIBCAPSTONE_PATH"):
        raise RuntimeError("event-handler CFG verifier rejects Capstone overrides")


_require_isolated_cli_runtime()
for _root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from tools import rom_event_handler_cfg_contract as C  # noqa: E402
from tools.verify_rom_cfg_inventory import _decode, _safe_file  # noqa: E402


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
        self.source, self.target = source, target


def _producer(rom: bytes) -> dict[str, Any]:
    raw = rom[C.TABLE_RANGE[0] : C.TABLE_RANGE[1]]
    if len(raw) != C.TABLE_BYTES or _sha(raw) != C.TABLE_SHA256:
        raise ValueError("producer table identity changed")
    matching: list[list[int]] = []
    nulls = others = 0
    for slot, offset in enumerate(range(*C.TABLE_RANGE, 4)):
        value = struct.unpack_from("<I", rom, offset)[0]
        target = value - C.ROM_BASE - 1
        if value == 0:
            nulls += 1
        elif value & 1 and C.UNKNOWN_BOUND[0] <= target < C.UNKNOWN_BOUND[1]:
            matching.append([slot, offset, value, target])
        else:
            others += 1
    roots = sorted({row[3] for row in matching})
    occurrences = sorted(Counter(row[3] for row in matching).items())
    if (len(matching), nulls, others, roots, _vector_sha(matching), _vector_sha(roots), _vector_sha(occurrences)) != (
        C.MATCHING_SLOT_COUNT, C.NULL_SLOT_COUNT, C.OTHER_SLOT_COUNT, list(C.ROOT_VECTOR), C.MATCHING_SLOT_VECTOR_SHA256, C.ROOT_VECTOR_SHA256, C.OCCURRENCE_VECTOR_SHA256
    ):
        raise ValueError("producer table denominator changed")
    return {
        "range": list(C.TABLE_RANGE), "bytes": len(raw), "u32_slot_count": len(raw) // 4,
        "null_slot_count": nulls, "matching_slot_count": len(matching), "other_slot_count": others,
        "unique_root_count": len(roots), "table_sha256": _sha(raw), "matching_slots": matching,
        "root_occurrences": [list(row) for row in occurrences], "matching_slot_vector_sha256": _vector_sha(matching),
        "root_vector_sha256": _vector_sha(roots), "occurrence_vector_sha256": _vector_sha(occurrences),
    }


def _blocks(rom: bytes, nodes: dict[tuple[str, int], dict[str, Any]], roots: set[tuple[str, int]]) -> list[dict[str, Any]]:
    resolved: dict[tuple[str, int], list[tuple[str, int]]] = {}
    incoming: dict[tuple[str, int], list[tuple[str, int]]] = defaultdict(list)
    for item, node in nodes.items():
        targets = []
        for edge in node["successors"]:
            target = (edge["mode"], edge["file_offset"])
            if target in nodes:
                targets.append(target)
                incoming[target].append(item)
        resolved[item] = targets
    starts = {item for item in roots if item in nodes}
    for item, node in nodes.items():
        preds = incoming[item]
        if len(preds) != 1:
            starts.add(item)
            continue
        pred = preds[0]
        prior = nodes[pred]
        if len(resolved[pred]) != 1 or pred[0] != item[0] or pred[1] + prior["size"] != item[1] or prior["flow_kind"] != "linear":
            starts.add(item)
    def key(item: tuple[str, int]) -> tuple[int, int, str]:
        return (item[1], 0 if item[0] == "arm" else 1, item[0])
    pending = [key(item) for item in starts]
    heapq.heapify(pending)
    assigned: dict[tuple[str, int], str] = {}
    raw_blocks: list[tuple[list[tuple[str, int]], dict[str, Any]]] = []
    while len(assigned) < len(nodes):
        if not pending:
            heapq.heappush(pending, key(min((item for item in nodes if item not in assigned), key=key)))
        offset, _, mode = heapq.heappop(pending)
        first = (mode, offset)
        if first in assigned:
            continue
        block_id = f"block-{mode}-{offset:06x}"
        members, current = [], first
        while current not in assigned:
            members.append(current)
            assigned[current] = block_id
            node, targets = nodes[current], resolved[current]
            if len(targets) != 1 or node["flow_kind"] != "linear" or targets[0] in starts or targets[0] in assigned or targets[0][0] != current[0] or targets[0][1] != current[1] + node["size"]:
                break
            current = targets[0]
        last, last_node = members[-1], nodes[members[-1]]
        raw_blocks.append((members, {"id": block_id, "mode": mode, "range": [members[0][1], last[1] + last_node["size"]], "instruction_count": len(members), "terminator": {field: last_node[field] for field in ("file_offset", "size", "mnemonic", "op_str", "flow_kind", "conditional")}, "successors": []}))
    result = []
    for members, block in raw_blocks:
        for edge in nodes[members[-1]]["successors"]:
            target = (edge["mode"], edge["file_offset"])
            if target in nodes:
                block["successors"].append({**edge, "block_id": assigned[target]})
        result.append(block)
    result.sort(key=lambda block: (block["range"][0], block["mode"]))
    return result


def _decode_root(rom: bytes, root: int) -> tuple[dict[tuple[str, int], dict[str, Any]], list[list[Any]], list[list[Any]]]:
    pending, scheduled, nodes = [(root, 1, "thumb")], {("thumb", root)}, {}
    external: list[list[Any]] = []
    opaque: list[list[Any]] = []
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in nodes:
            continue
        if mode != "thumb" or not (C.UNKNOWN_BOUND[0] <= offset < C.UNKNOWN_BOUND[1]):
            raise _EscapedBound(offset, offset)
        decoded = _decode(rom, offset, mode)
        if not decoded["accepted"]:
            raise ValueError("raw CFG decoder frontier changed")
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
    return nodes, sorted(external), sorted(opaque)


def _merge(ranges: list[list[int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for start, end in sorted(ranges):
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def _rebuild(rom: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    producer = _producer(rom)
    all_nodes: dict[tuple[str, int], dict[str, Any]] = {}
    accepted, rejected = [], []
    external: set[tuple[Any, ...]] = set()
    opaque: set[tuple[Any, ...]] = set()
    for root in sorted({row[3] for row in producer["matching_slots"]}):
        try:
            nodes, calls, boundaries = _decode_root(rom, root)
        except _EscapedBound as error:
            rejected.append({"root": root, "reason": "non_call_edge_escaped_unknown_bound", "source_file_offset": error.source, "target_file_offset": error.target})
            continue
        accepted.append(root)
        all_nodes.update(nodes)
        external.update(map(tuple, calls))
        opaque.update(map(tuple, boundaries))
    if accepted != list(C.ACCEPTED_ROOTS) or rejected != [C.REJECTION_EVIDENCE]:
        raise ValueError("root acceptance contract changed")
    blocks = _blocks(rom, all_nodes, {("thumb", root) for root in accepted})
    ordered = [all_nodes[key] for key in sorted(all_nodes, key=lambda item: (item[1], item[0]))]
    instruction_edges = sorted({(node["file_offset"], edge["file_offset"], edge["kind"]) for node in ordered for edge in node["successors"] if (edge["mode"], edge["file_offset"]) in all_nodes})
    block_edges = sorted({(block["terminator"]["file_offset"], edge["file_offset"], edge["kind"]) for block in blocks for edge in block["successors"]})
    semantic = [[node["file_offset"], node["size"], node["mnemonic"], node["op_str"]] for node in ordered]
    frontiers = sorted([node["file_offset"], frontier["reason"]] for node in ordered for frontier in node["frontiers"])
    cfg = {
        "instruction_count": len(all_nodes), "code_bytes": sum(node["size"] for node in all_nodes.values()), "block_count": len(blocks),
        "instruction_internal_edge_count": len(instruction_edges), "block_internal_edge_count": len(block_edges), "external_call_edge_count": len(external),
        "frontier_count": len(frontiers), "opaque_edge_count": len(opaque), "semantic_vector_sha256": _vector_sha(semantic),
        "instruction_internal_edge_vector_sha256": _vector_sha([list(row) for row in instruction_edges]),
        "block_range_vector_sha256": _vector_sha([block["range"] for block in blocks]),
        "block_internal_edge_vector_sha256": _vector_sha([list(row) for row in block_edges]),
        "external_call_vector_sha256": _vector_sha([list(row) + ["opaque_external"] for row in sorted(external)]),
        "frontier_vector_sha256": _vector_sha(frontiers), "opaque_edge_vector_sha256": _vector_sha([list(row) for row in sorted(opaque)]),
    }
    expected_cfg = {
        "instruction_count": C.CFG_INSTRUCTION_COUNT, "code_bytes": C.CFG_CODE_BYTES, "block_count": C.CFG_BLOCK_COUNT,
        "instruction_internal_edge_count": C.CFG_INSTRUCTION_INTERNAL_EDGE_COUNT, "block_internal_edge_count": C.CFG_BLOCK_INTERNAL_EDGE_COUNT,
        "external_call_edge_count": C.CFG_EXTERNAL_CALL_EDGE_COUNT, "frontier_count": C.CFG_FRONTIER_COUNT, "opaque_edge_count": C.CFG_OPAQUE_EDGE_COUNT,
        "semantic_vector_sha256": C.CFG_SEMANTIC_VECTOR_SHA256, "instruction_internal_edge_vector_sha256": C.CFG_INSTRUCTION_INTERNAL_EDGE_VECTOR_SHA256,
        "block_range_vector_sha256": C.CFG_BLOCK_RANGE_VECTOR_SHA256, "block_internal_edge_vector_sha256": C.CFG_BLOCK_INTERNAL_EDGE_VECTOR_SHA256,
        "external_call_vector_sha256": C.CFG_EXTERNAL_CALL_VECTOR_SHA256, "frontier_vector_sha256": C.CFG_FRONTIER_VECTOR_SHA256,
        "opaque_edge_vector_sha256": C.CFG_OPAQUE_EDGE_VECTOR_SHA256,
    }
    if cfg != expected_cfg:
        raise ValueError("independent CFG reconstruction changed")
    code = _merge([[node["file_offset"], node["file_offset"] + node["size"]] for node in ordered])
    bindings, words = [], set()
    for node in ordered:
        offset = node["file_offset"]
        halfword = struct.unpack_from("<H", rom, offset)[0]
        if node["size"] == 2 and halfword & 0xF800 == 0x4800:
            target = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
            if not (C.UNKNOWN_BOUND[0] <= target and target + 4 <= C.UNKNOWN_BOUND[1]) or any(a < target + 4 and target < b for a, b in code):
                raise ValueError("independent literal projection escaped or overlapped code")
            bindings.append([offset, target]); words.add(target)
    literals = _merge([[word, word + 4] for word in sorted(words)])
    semantic_ranges = sorted([[a, b, "reachable_thumb_code"] for a, b in code] + [[a, b, "consumed_literal_word"] for a, b in literals])
    union = _merge([[a, b] for a, b, _ in semantic_ranges])
    holes, cursor = [], C.UNKNOWN_BOUND[0]
    for start, end in union:
        if cursor < start: holes.append([cursor, start])
        cursor = end
    if cursor < C.UNKNOWN_BOUND[1]: holes.append([cursor, C.UNKNOWN_BOUND[1]])
    promotion = {
        "code_ranges": code, "literal_ranges": literals, "semantic_ranges": semantic_ranges, "union_ranges": union, "preserved_unknown_holes": holes,
        "code_bytes": sum(b-a for a,b in code), "literal_bytes": sum(b-a for a,b in literals), "bytes": sum(b-a for a,b in union),
        "preserved_unknown_hole_bytes": sum(b-a for a,b in holes), "code_range_vector_sha256": _vector_sha(code), "literal_range_vector_sha256": _vector_sha(literals),
        "semantic_range_vector_sha256": _vector_sha(semantic_ranges), "union_range_vector_sha256": _vector_sha(union), "hole_range_vector_sha256": _vector_sha(holes),
        "literal_binding_vector_sha256": _vector_sha(sorted(bindings)), "packed_code_sha256": _sha(b"".join(rom[a:b] for a,b in code)),
        "packed_literal_sha256": _sha(b"".join(rom[a:b] for a,b in literals)), "packed_sha256": _sha(b"".join(rom[a:b] for a,b in union)),
    }
    frozen = {
        "code_ranges": [list(row) for row in C.CODE_RANGES], "literal_ranges": [list(row) for row in C.LITERAL_RANGES], "semantic_ranges": [list(row) for row in C.SEMANTIC_RANGES],
        "union_ranges": [list(row) for row in C.UNION_RANGES], "preserved_unknown_holes": [list(row) for row in C.PRESERVED_UNKNOWN_HOLES], "code_bytes": 3910,
        "literal_bytes": 152, "bytes": 4062, "preserved_unknown_hole_bytes": 174, "code_range_vector_sha256": C.CODE_RANGE_VECTOR_SHA256,
        "literal_range_vector_sha256": C.LITERAL_RANGE_VECTOR_SHA256, "semantic_range_vector_sha256": C.SEMANTIC_RANGE_VECTOR_SHA256,
        "union_range_vector_sha256": C.UNION_RANGE_VECTOR_SHA256, "hole_range_vector_sha256": C.HOLE_RANGE_VECTOR_SHA256,
        "literal_binding_vector_sha256": C.LITERAL_BINDING_VECTOR_SHA256, "packed_code_sha256": C.PACKED_CODE_SHA256,
        "packed_literal_sha256": C.PACKED_LITERAL_SHA256, "packed_sha256": C.PACKED_PROMOTION_SHA256,
    }
    if promotion != frozen:
        raise ValueError("independent promotion reconstruction changed")
    return cfg, promotion


def _coverage(root: Path) -> dict[str, Any]:
    raw = _safe_file(root, C.COVERAGE_PATH).read_bytes()
    if _sha(raw) != C.COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    coverage = json.loads(raw)
    for key in ("classified_bytes", "unknown_bytes", "claim_count", "segment_count"):
        if coverage.get("summary", {}).get(key) != C.COVERAGE_EXPECTED[key]: raise ValueError("coverage summary changed")
    owners = [row for row in coverage["segments"] if row["range"][0] < C.UNKNOWN_BOUND[1] and C.UNKNOWN_BOUND[0] < row["range"][1]]
    table = [row for row in coverage["segments"] if row["range"][0] < C.TABLE_RANGE[1] and C.TABLE_RANGE[0] < row["range"][1]]
    if owners != [C.UNKNOWN_OWNER] or table != [C.TABLE_OWNER]: raise ValueError("coverage owner projection changed")
    return {
        **C.COVERAGE_EXPECTED,
        "current_unknown_only": True,
        "candidate_owner": owners[0],
        "producer_owner": table[0],
        "promoted_from_unknown_bytes": 4062,
    }


def _implementation(root: Path) -> dict[str, Any]:
    paths = {"exporter": Path("tools/export_rom_event_handler_cfg.py"), "verifier": Path("tools/verify_rom_event_handler_cfg.py"), "test_exporter": Path("tests/test_export_rom_event_handler_cfg.py"), "test_verifier": Path("tests/test_verify_rom_event_handler_cfg.py")}
    return {"binding": "runtime-dependency-and-test-hash-bound", "paths": {k:v.as_posix() for k,v in paths.items()},
        **{f"{k}_sha256": _sha(_safe_file(root,v).read_bytes()) for k,v in paths.items()},
        "runtime_dependency_sha256": {path.as_posix(): _sha(_safe_file(root,path).read_bytes()) for path in C.RUNTIME_DEPENDENCY_PATHS}}


EXPECTED_REPORT = {"schema": C.VERIFY_SCHEMA, "verified": True, "errors": [], "accepted_root_count": len(C.ACCEPTED_ROOTS), "rejected_roots": list(C.REJECTED_ROOTS),
    "instruction_count": C.CFG_INSTRUCTION_COUNT, "code_bytes": C.CFG_CODE_BYTES, "block_count": C.CFG_BLOCK_COUNT, "frontier_count": C.CFG_FRONTIER_COUNT,
    "opaque_edge_count": C.CFG_OPAQUE_EDGE_COUNT, "promotion_bytes": 4062, "preserved_unknown_hole_bytes": 174, "nonclaims": {name: False for name in C.NONCLAIMS}}


def _expected_payload(root: Path, rom: bytes) -> dict[str, Any]:
    _assert_oracle_identities(root)
    cfg, promotion = _rebuild(rom)
    return {"schema": C.SCHEMA, "rom": {"path": C.ROM_PATH.as_posix(), "size": C.ROM_SIZE, "sha256": C.ROM_SHA256}, "producer_denominator": _producer(rom),
        "accepted_roots": list(C.ACCEPTED_ROOTS), "rejected_roots": list(C.REJECTED_ROOTS), "rejection_evidence": dict(C.REJECTION_EVIDENCE),
        "candidate_unknown_range": list(C.UNKNOWN_BOUND), "opaque_accepted_ranges": [list(row) for row in C.OPAQUE_ACCEPTED_RANGES], "cfg": cfg,
        "promotion": promotion, "coverage_baseline": _coverage(root), "implementation": _implementation(root), "scope": dict(C.SCOPE)}


def _receipt(root: Path, artifact: Path, manifest: dict[str, Any]) -> tuple[list[str], list[str]]:
    producer = manifest.get("producer", {}).get("command")
    verifier = manifest.get("verifier", {}).get("command")
    pp = ["python3", "-I", "-S", "tools/export_rom_event_handler_cfg.py", "--root", ".", "--output-dir"]
    vp = ["python3", "-I", "-S", "tools/verify_rom_event_handler_cfg.py", "--root", ".", "--artifact-dir"]
    if not isinstance(producer,list) or not isinstance(verifier,list) or producer[:-1] != pp or verifier[:-1] != vp or producer[-1] != verifier[-1]:
        raise ValueError("promotion receipt command changed")
    recorded = Path(producer[-1])
    if recorded.is_absolute(): raise ValueError("promotion receipt path must be relative")
    target = (root / recorded).resolve(strict=False)
    experiment, official = (root / C.EXPERIMENT_OUTPUT_ROOT).resolve(), (root / C.OFFICIAL_ARTIFACT).resolve(strict=False)
    if target != official and (target == experiment or experiment not in target.parents): raise ValueError("promotion receipt escaped experiment subtree")
    if target != artifact.resolve(strict=True): raise ValueError("promotion receipt does not match artifact directory")
    return producer, verifier


def _expected_manifest(root: Path, artifact: Path, manifest: dict[str, Any], payload: dict[str, Any], raw: bytes) -> dict[str, Any]:
    producer, verifier = _receipt(root, artifact, manifest)
    status = manifest.get("artifact_status")
    if status not in {"candidate", "accepted"}: raise ValueError("artifact status changed")
    report = EXPECTED_REPORT if status == "accepted" else None
    return {"schema": C.PROMOTION_SCHEMA, "artifact_schema": C.SCHEMA, "artifact_status": status, "rom": payload["rom"], "producer_denominator": payload["producer_denominator"],
        "cfg": payload["cfg"], "promotion": payload["promotion"], "coverage_baseline": payload["coverage_baseline"], "files": {C.PAYLOAD_NAME:{"size":len(raw),"sha256":_sha(raw)}},
        "producer":{"command":producer,"implementation":payload["implementation"]}, "verifier":{"schema":C.VERIFY_SCHEMA,"command":verifier,"exit_code":0 if report else None,
        "report":report,"verifier_sha256":payload["implementation"]["verifier_sha256"]}, "implementation":payload["implementation"], "scope":payload["scope"]}


def _failure(message: str) -> dict[str, Any]:
    report = dict(EXPECTED_REPORT); report["verified"] = False; report["errors"] = [message]; return report


def verify_rom_event_handler_cfg(root: Path, artifact_dir: Path) -> dict[str, Any]:
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact_dir).expanduser().absolute()
        if artifact.is_symlink() or not artifact.is_dir(): raise ValueError("artifact directory is missing or uses a symlink")
        members = list(artifact.rglob("*"))
        if {p.relative_to(artifact).as_posix() for p in members if p.is_file()} != {C.MANIFEST_NAME, C.PAYLOAD_NAME} or any(p.is_symlink() for p in members):
            raise ValueError("artifact file set changed")
        payload_path, manifest_path = artifact / C.PAYLOAD_NAME, artifact / C.MANIFEST_NAME
        if not payload_path.is_file() or not manifest_path.is_file(): raise ValueError("artifact files are incomplete")
        payload_raw, manifest_raw = payload_path.read_bytes(), manifest_path.read_bytes()
        payload, manifest = json.loads(payload_raw), json.loads(manifest_raw)
        if payload_raw != _canonical(payload) or manifest_raw != _canonical(manifest): raise ValueError("artifact JSON is not canonical")
        rom = _safe_file(root, C.ROM_PATH).read_bytes()
        if len(rom) != C.ROM_SIZE or _sha(rom) != C.ROM_SHA256: raise ValueError("base ROM identity changed")
        expected = _expected_payload(root, rom)
        if payload != expected: raise ValueError("payload differs from independent reconstruction")
        if manifest != _expected_manifest(root, artifact, manifest, expected, payload_raw): raise ValueError("manifest differs from independent reconstruction")
        return dict(EXPECTED_REPORT)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        return _failure(str(error))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    report = verify_rom_event_handler_cfg(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
