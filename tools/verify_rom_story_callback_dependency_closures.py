#!/usr/bin/env python3
"""Independently verify story callback dependency closures with a raw decoder."""

from __future__ import annotations

import argparse
import bisect
from collections import defaultdict
import gzip
import hashlib
import heapq
import json
from pathlib import Path
import struct
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.rom_story_callback_dependency_closures_contract import *  # noqa: E402,F403


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _vsha(value: Any) -> str:
    return _sha(json.dumps(value, separators=(",", ":"), sort_keys=True).encode())


def _packed(rom: bytes, ranges: Any) -> bytes:
    return b"".join(rom[start:end] for start, end in ranges)


def _inside(offset: int, ranges: Any = CODE_RANGES) -> bool:  # noqa: F405
    return any(start <= offset < end for start, end in ranges)


def _safe_file(root: Path, relative: Path) -> Path:
    base = root.resolve(strict=True)
    cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"unsafe input path: {relative}")
    result = cursor.resolve(strict=True)
    if not result.is_relative_to(base) or not result.is_file():
        raise ValueError(f"unsafe input path: {relative}")
    return result


def _safe_artifact(root: Path, artifact: Path) -> Path:
    base = root.resolve(strict=True)
    lexical = artifact if artifact.is_absolute() else base / artifact
    try:
        relative = lexical.relative_to(base)
    except ValueError as error:
        raise ValueError("artifact escapes root") from error
    cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("artifact symlink ancestor")
    result = lexical.resolve(strict=True)
    if not result.is_relative_to(base) or not result.is_dir():
        raise ValueError("artifact escapes root")
    return result


def _direct_target(rom: bytes, offset: int) -> tuple[int, str, int] | None:
    first = struct.unpack_from("<H", rom, offset)[0]
    if first & 0xF800 == 0xF000 and offset + 4 <= len(rom):
        second = struct.unpack_from("<H", rom, offset + 2)[0]
        if second & 0xF800 == 0xF800:
            delta = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
            if delta & (1 << 22):
                delta -= 1 << 23
            return offset + 4 + delta, "bl", 4
    if first & 0xF800 == 0xE000:
        delta = (first & 0x7FF) << 1
        if delta & 0x800:
            delta -= 0x1000
        return offset + 4 + delta, "b", 2
    condition = (first >> 8) & 0xF
    if first & 0xF000 == 0xD000 and condition < 14:
        delta = (first & 0xFF) << 1
        if delta & 0x100:
            delta -= 0x200
        return offset + 4 + delta, "bcond", 2
    return None


def _precoverage(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = _safe_file(root, PRECOVERAGE_MANIFEST)  # noqa: F405
    archive_path = _safe_file(root, PRECOVERAGE_ARCHIVE)  # noqa: F405
    if {path.name for path in manifest_path.parent.iterdir()} != {
        "manifest.json", "rom-byte-coverage.json.gz"
    }:
        raise ValueError("immutable precoverage file denominator changed")
    manifest_raw = manifest_path.read_bytes()
    archive_raw = archive_path.read_bytes()
    if _sha(manifest_raw) != PRECOVERAGE_MANIFEST_SHA256:  # noqa: F405
        raise ValueError("immutable precoverage manifest changed")
    if (len(archive_raw) != PRECOVERAGE_ARCHIVE_SIZE
            or _sha(archive_raw) != PRECOVERAGE_ARCHIVE_SHA256):  # noqa: F405
        raise ValueError("immutable precoverage archive changed")
    try:
        raw = gzip.decompress(archive_raw)
    except (gzip.BadGzipFile, EOFError) as error:
        raise ValueError("immutable precoverage gzip invalid") from error
    if len(raw) != PRECOVERAGE_RAW_SIZE or _sha(raw) != PRECOVERAGE_RAW_SHA256:  # noqa: F405
        raise ValueError("immutable precoverage payload changed")
    coverage = json.loads(raw)
    if raw != _canonical(coverage):
        raise ValueError("immutable precoverage JSON changed")
    return coverage, {
        "artifact": PRECOVERAGE_DIR.as_posix(),  # noqa: F405
        "manifest_sha256": PRECOVERAGE_MANIFEST_SHA256,  # noqa: F405
        "archive_sha256": PRECOVERAGE_ARCHIVE_SHA256,  # noqa: F405
        "coverage_sha256": PRECOVERAGE_RAW_SHA256,  # noqa: F405
    }


def _raw_thumb_linear_kind(halfword: int) -> str:
    if halfword & 0xE000 == 0x0000:
        return "shift_or_add_subtract"
    if halfword & 0xE000 == 0x2000:
        return "immediate_alu"
    if halfword & 0xFC00 == 0x4000:
        return "register_alu"
    if halfword & 0xFC00 == 0x4400:
        if (halfword >> 8) & 3 == 3:
            raise ValueError("illegal Thumb BX/BLX encoding")
        return "high_register_alu"
    if halfword & 0xF800 == 0x4800:
        return "pc_relative_load"
    if halfword & 0xF000 == 0x5000:
        return "register_offset_load_store"
    if halfword & 0xE000 == 0x6000:
        return "immediate_load_store"
    if halfword & 0xF000 == 0x8000:
        return "halfword_load_store"
    if halfword & 0xF000 == 0x9000:
        return "sp_relative_load_store"
    if halfword & 0xF000 == 0xA000:
        return "load_address"
    if halfword & 0xFF00 == 0xB000:
        return "adjust_sp"
    if halfword & 0xFE00 == 0xB400:
        return "push"
    if halfword & 0xFE00 == 0xBC00:
        return "pop"
    if halfword & 0xF000 == 0xC000 and halfword & 0xFF:
        return "multiple_load_store"
    if halfword & 0xFF00 == 0xDF00:
        return "software_interrupt"
    raise ValueError(f"illegal Thumb-1 encoding: 0x{halfword:04X}")


def _decode(rom: bytes, offset: int) -> dict[str, Any]:
    direct = _direct_target(rom, offset)
    if direct is not None:
        target, kind, size = direct
        if kind == "bl":
            return {"size": size, "flow_kind": "call",
                    "successors": [(offset + size, "fallthrough"),
                                   (target, "call_target")], "frontier": False}
        if kind == "bcond":
            return {"size": size, "flow_kind": "conditional_branch",
                    "successors": [(offset + size, "fallthrough"),
                                   (target, "branch_target")], "frontier": False}
        return {"size": size, "flow_kind": "unconditional_branch",
                "successors": [(target, "branch_target")], "frontier": False}
    halfword = struct.unpack_from("<H", rom, offset)[0]
    if halfword & 0xFF87 == 0x4700:
        return {"size": 2, "flow_kind": "indirect_return", "successors": [],
                "frontier": True}
    if halfword & 0xFF00 == 0xBD00 and halfword & 0x100:
        return {"size": 2, "flow_kind": "return", "successors": [],
                "frontier": False}
    _raw_thumb_linear_kind(halfword)
    return {"size": 2, "flow_kind": "linear",
            "successors": [(offset + 2, "fallthrough")], "frontier": False}


def _merge(nodes: dict[int, dict[str, Any]]) -> list[list[int]]:
    result: list[list[int]] = []
    for offset, node in sorted(nodes.items()):
        end = offset + node["size"]
        if result and offset <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([offset, end])
    return result


def _block_count(nodes: dict[int, dict[str, Any]]) -> int:
    resolved = {source: [target for target, _ in node["successors"] if target in nodes]
                for source, node in nodes.items()}
    predecessors: dict[int, list[int]] = defaultdict(list)
    for source, targets in resolved.items():
        for target in targets:
            predecessors[target].append(source)
    starts = set(ROOTS)  # noqa: F405
    for offset, node in nodes.items():
        incoming = predecessors[offset]
        if len(incoming) != 1:
            starts.add(offset)
            continue
        predecessor = incoming[0]
        prior = nodes[predecessor]
        if len(resolved[predecessor]) != 1 or predecessor + prior["size"] != offset \
                or prior["flow_kind"] != "linear":
            starts.add(offset)
    assigned: set[int] = set()
    pending = list(starts)
    heapq.heapify(pending)
    count = 0
    while len(assigned) < len(nodes):
        if not pending:
            heapq.heappush(pending, min(set(nodes) - assigned))
        current = heapq.heappop(pending)
        if current in assigned:
            continue
        count += 1
        while current not in assigned:
            assigned.add(current)
            node = nodes[current]
            targets = resolved[current]
            if len(targets) != 1 or node["flow_kind"] != "linear" \
                    or targets[0] in starts or targets[0] in assigned \
                    or targets[0] != current + node["size"]:
                break
            current = targets[0]
    return count


def _evidence(
    root: Path, rom: bytes, opaque_targets: list[int]
) -> tuple[dict[str, Any], dict[str, Any]]:
    identities = {}
    for path, digest in EVIDENCE_FILES:  # noqa: F405
        if _sha(_safe_file(root, path).read_bytes()) != digest:
            raise ValueError(f"upstream evidence identity changed: {path}")
        identities[path.as_posix()] = digest
    payload = json.loads(_safe_file(
        root, Path("artifacts/rom-story-state-callback-cfg-v1/rom-story-state-callback-cfg.json")
    ).read_bytes())
    calls = payload["target_local_denominator"]["opaque_external_calls"]
    selected = [[index, *calls[index]] for index in UPSTREAM_CALL_INDICES]  # noqa: F405
    expected = [[index, source, target] for index, (source, target) in zip(
        UPSTREAM_CALL_INDICES, UPSTREAM_PRODUCERS, strict=True  # noqa: F405
    )]
    if selected != expected:
        raise ValueError("upstream story callback producer evidence changed")
    coverage, baseline_identity = _precoverage(root)
    owners = [row for row in coverage["segments"]
              if row["range"][0] <= BOUNDARY[1] < row["range"][1]]  # noqa: F405
    if len(owners) != 1 or owners[0]["range"] != BOUNDARY_OWNER["range"] \
            or owners[0].get("primary_claim_ids") != [BOUNDARY_OWNER["claim_id"]]:  # noqa: F405
        raise ValueError("boundary accepted Thumb CFG owner changed")
    start, end = BOUNDARY_OWNER["range"]  # noqa: F405
    if _sha(rom[start:end]) != BOUNDARY_OWNER["bytes_sha256"]:  # noqa: F405
        raise ValueError("boundary accepted Thumb CFG owner bytes changed")
    opaque_owners = []
    for target in sorted(set(opaque_targets)):
        matches = [row for row in coverage["segments"]
                   if row["range"][0] <= target < row["range"][1]]
        if len(matches) != 1 or matches[0].get("primary_class") == "unknown":
            raise ValueError("opaque target canonical owner changed")
        row = matches[0]
        opaque_owners.append({"target_file_offset": target, "range": row["range"],
                              "primary_class": row["primary_class"],
                              "primary_claim_ids": row.get("primary_claim_ids", [])})
    if len(opaque_owners) != 37:
        raise ValueError("opaque target owner denominator changed")
    segments = coverage["segments"]
    starts = [row["range"][0] for row in segments]

    def assert_unknown(ranges: Any, label: str) -> int:
        total = 0
        for range_start, range_end in ranges:
            cursor = range_start
            while cursor < range_end:
                index = bisect.bisect_right(starts, cursor) - 1
                if index < 0:
                    raise ValueError(f"{label} coverage lookup failed")
                row = segments[index]
                if not row["range"][0] <= cursor < row["range"][1] \
                        or row.get("primary_class") != "unknown":
                    raise ValueError(f"{label} escaped current unknown")
                step = min(range_end, row["range"][1]) - cursor
                total += step
                cursor += step
        return total

    promotion_bytes = assert_unknown((*CODE_RANGES, *LITERAL_RANGES), "promotion")  # noqa: F405
    hole_bytes = assert_unknown(HOLES, "preserved hole")  # noqa: F405
    summary = coverage.get("summary", {})
    if summary.get("classified_bytes") != 6_198_347 \
            or summary.get("unknown_bytes") != 93_109:
        raise ValueError("coverage baseline summary changed")
    evidence = {"status": "identity_bound_upstream_story_callback", "files": identities,
                "accepted_story_callback_calls": selected, "boundary_owner": BOUNDARY_OWNER,
                "opaque_target_owners": opaque_owners}  # noqa: F405
    baseline = {"identity": baseline_identity,
                "role": "historical_read_only_projection_baseline",
                "mutation_performed": False,
                "validated_current_unknown_bytes": promotion_bytes,
                "preserved_unknown_hole_bytes": hole_bytes,
                "projected_classified_bytes": summary["classified_bytes"] + promotion_bytes,
                "projected_unknown_bytes": summary["unknown_bytes"] - promotion_bytes}
    return evidence, baseline


def _producer_denominator(rom: bytes) -> dict[str, Any]:
    rows = []
    roots = set(ROOTS)  # noqa: F405
    for offset in range(0, len(rom) - 1, 2):
        decoded = _direct_target(rom, offset)
        if decoded is not None and decoded[0] in roots:
            target, kind, size = decoded
            rows.append([offset, target, kind, size, rom[offset:offset + size].hex()])
    if [(row[0], row[1]) for row in rows] != sorted((*UPSTREAM_PRODUCERS, *RECURSIVE_PRODUCERS)) \
            or _vsha(rows) != PRODUCER_VECTOR_SHA256:  # noqa: F405
        raise ValueError("producer denominator changed")
    return {"scan_range": [0, len(rom)], "stride": 2,
            "decoder_kinds": ["thumb_bl", "thumb_b", "thumb_bcond"],
            "root_match_count": len(rows), "match_count_per_root": 1,
            "upstream_story_call_count": 6, "recursive_dependency_call_count": 3,
            "root_producers": rows, "root_match_vector_sha256": _vsha(rows)}


def _closure(rom: bytes) -> dict[str, Any]:
    if rom[BOUNDARY[0]:BOUNDARY[1]].hex() != "0024":  # noqa: F405
        raise ValueError("boundary continuation source changed")
    if _sha(_packed(rom, LITERAL_RANGES)) != LITERAL_SHA256:  # noqa: F405
        raise ValueError("literal identity changed")
    if _sha(_packed(rom, HOLES)) != HOLE_SHA256:  # noqa: F405
        raise ValueError("hole identity changed")
    if _sha(_packed(rom, CODE_RANGES)) != CODE_SHA256:  # noqa: F405
        raise ValueError("closure byte identity changed")
    pending = list(ROOTS)  # noqa: F405
    heapq.heapify(pending)
    scheduled = set(ROOTS)  # noqa: F405
    nodes: dict[int, dict[str, Any]] = {}
    exits: list[list[int]] = []
    boundaries: list[list[int]] = []
    while pending:
        offset = heapq.heappop(pending)
        if offset in nodes:
            continue
        if not _inside(offset):
            raise ValueError("closure worklist escaped frozen ranges")
        node = _decode(rom, offset)
        nodes[offset] = node
        for target, kind in node["successors"]:
            if _inside(target):
                if target not in scheduled:
                    scheduled.add(target)
                    heapq.heappush(pending, target)
            elif kind == "call_target":
                exits.append([offset, target])
            elif (offset, target) == BOUNDARY:  # noqa: F405
                boundaries.append([offset, target])
            else:
                raise ValueError("closure non-call edge escaped frozen ranges")
    code = _merge(nodes)
    bindings = []
    for offset, node in sorted(nodes.items()):
        if node["size"] == 2:
            halfword = struct.unpack_from("<H", rom, offset)[0]
            if halfword & 0xF800 == 0x4800:
                literal = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
                if not any(start <= literal and literal + 4 <= end
                           for start, end in LITERAL_RANGES):  # noqa: F405
                    raise ValueError("literal reference escaped frozen ranges")
                bindings.append([offset, literal, rom[offset:offset + 2].hex(),
                                 rom[literal:literal + 4].hex()])
    return_sites = sorted(offset for offset, node in nodes.items() if node["frontier"])
    if code != [list(row) for row in CODE_RANGES] or len(nodes) != 762 \
            or _block_count(nodes) != 156:  # noqa: F405
        raise ValueError("closure denominator changed")
    if len(bindings) != 71 or len({row[1] for row in bindings}) != 69 \
            or _vsha(bindings) != LITERAL_BINDING_SHA256:  # noqa: F405
        raise ValueError("literal binding denominator changed")
    if len(exits) != 63 or _vsha(sorted(exits)) != OPAQUE_EXIT_SHA256:  # noqa: F405
        raise ValueError("closure exit denominator changed")
    if boundaries != [list(BOUNDARY)]:  # noqa: F405
        raise ValueError("boundary continuation denominator changed")
    if len(return_sites) != 8:
        raise ValueError("structured return denominator changed")
    return_contracts = []
    for (root, prologue_start, prologue_end, prologue_hex,
         epilogue_start, epilogue_end, epilogue_hex, terminal) in RETURN_CONTRACTS:  # noqa: F405
        if prologue_start != root or rom[prologue_start:prologue_end].hex() != prologue_hex:
            raise ValueError("structured return prologue changed")
        if rom[epilogue_start:epilogue_end].hex() != epilogue_hex \
                or terminal not in return_sites:
            raise ValueError("structured return epilogue changed")
        return_contracts.append({"root": root, "terminal": terminal,
                                 "prologue_range": [prologue_start, prologue_end],
                                 "epilogue_range": [epilogue_start, epilogue_end]})
    if set(return_sites) != {row[-1] for row in RETURN_CONTRACTS}:  # noqa: F405
        raise ValueError("structured return site set changed")
    return {"roots": list(ROOTS), "root_count": 9, "upstream_root_count": 6,  # noqa: F405
            "recursive_root_count": 3, "instruction_count": len(nodes),
            "basic_block_count": 156, "code_ranges": code, "code_bytes": 1656,
            "code_sha256": CODE_SHA256, "literal_reference_count": len(bindings),  # noqa: F405
            "unique_literal_word_count": len({row[1] for row in bindings}),
            "literal_ranges": [list(row) for row in LITERAL_RANGES],  # noqa: F405
            "literal_bytes": 276, "literal_sha256": LITERAL_SHA256,  # noqa: F405
            "opaque_accepted_exits": sorted(exits), "opaque_accepted_exit_count": len(exits),
            "accepted_boundary_continuations": boundaries,
            "accepted_boundary_continuation_count": len(boundaries),
            "structured_return_sites": return_sites,
            "structured_return_contracts": return_contracts,
            "structured_return_count": 8,
            "boundary_continuation_root": BOUNDARY_CONTINUATION_ROOT,  # noqa: F405
            "frontier_count": 0, "preserved_unknown_holes": [list(row) for row in HOLES],  # noqa: F405
            "preserved_unknown_bytes": 12}


def _rebuild(rom: bytes, *, verify_identity: bool = True,
             root: Path | None = None) -> dict[str, Any]:
    root = PROJECT_ROOT if root is None else root.resolve(strict=True)
    if verify_identity and (len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256):  # noqa: F405
        raise ValueError("ROM identity changed")
    producers = _producer_denominator(rom)
    closure = _closure(rom)
    evidence, baseline = _evidence(
        root, rom, [target for _, target in closure["opaque_accepted_exits"]])
    return {"upstream_evidence": evidence,
            "coverage_baseline": baseline,
            "producer_denominator": producers,
            "target_closure": closure}


def _expected(root: Path, rom: bytes) -> dict[str, Any]:
    rebuilt = _rebuild(rom, root=root)
    claims = []
    for kind, ranges in (("reachable_thumb_code", CODE_RANGES),  # noqa: F405
                         ("consumed_literal_words", LITERAL_RANGES)):  # noqa: F405
        for index, (start, end) in enumerate(ranges, 1):
            claims.append({"id": f"story-dependency-{kind}-{index:02d}-{start:06x}",
                           "kind": kind, "range": [start, end],
                           "bytes_sha256": _sha(rom[start:end]),
                           "historical_baseline_projection": True})
    return {"schema": SCHEMA,  # noqa: F405
            "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},  # noqa: F405
            **rebuilt,
            "promotion": {"promotion_batch": SCHEMA, "claims": claims,  # noqa: F405
                          "claim_count": 32, "target_code_bytes": 1656,
                          "target_literal_bytes": 276, "promotion_bytes": 1932,
                          "projection_only": True},
            "scope": {"natural_runtime_reachability": False,
                      "all_callback_dependencies_exhausted": False,
                      "indirect_or_computed_producer_exhaustiveness": False,
                      "business_semantics_or_abi": False,
                      "alignment_holes_or_free_space": False,
                      "editing_or_relocation_safety": False}}


def verify_artifact(root: Path, artifact: Path,
                    *, expected_artifact: Path | None = None) -> dict[str, Any]:
    try:
        root = root.resolve(strict=True)
        directory = _safe_artifact(root, artifact)
        members = list(directory.iterdir())
        if {path.name for path in members} != {PAYLOAD_NAME, MANIFEST_NAME}:  # noqa: F405
            raise ValueError("artifact file denominator changed")
        if any(path.is_symlink() or not path.is_file() for path in members):
            raise ValueError("artifact member type changed")
        payload_raw = (directory / PAYLOAD_NAME).read_bytes()  # noqa: F405
        manifest_raw = (directory / MANIFEST_NAME).read_bytes()  # noqa: F405
        payload, manifest = json.loads(payload_raw), json.loads(manifest_raw)
        if payload_raw != _canonical(payload) or manifest_raw != _canonical(manifest):
            raise ValueError("artifact JSON not canonical")
        rom = _safe_file(root, ROM_PATH).read_bytes()  # noqa: F405
        if payload != _expected(root, rom):
            raise ValueError("payload contract changed")
        if expected_artifact is not None and expected_artifact.resolve(strict=False) \
                != (root / OFFICIAL).resolve(strict=False):  # noqa: F405
            raise ValueError("artifact receipt destination changed")
        paths = {"contract_sha256": Path("tools/rom_story_callback_dependency_closures_contract.py"),
                 "exporter_sha256": Path("tools/export_rom_story_callback_dependency_closures.py"),
                 "verifier_sha256": Path("tools/verify_rom_story_callback_dependency_closures.py"),
                 "test_sha256": Path("tests/test_export_rom_story_callback_dependency_closures.py")}
        expected_manifest = {"schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,  # noqa: F405
                             "artifact_status": "accepted",
                             "canonical_destination": OFFICIAL.as_posix(),  # noqa: F405
                             "files": {PAYLOAD_NAME: {"size": len(payload_raw),  # noqa: F405
                                                       "sha256": _sha(payload_raw)}},
                             "summary": {"root_count": 9, "promotion_bytes": 1932,
                                         "frontier_count": 0},
                             "implementation": {name: _sha(_safe_file(root, path).read_bytes())
                                                for name, path in paths.items()}}
        if manifest != expected_manifest:
            raise ValueError("manifest contract changed")
        return {"schema": VERIFY_SCHEMA, "verified": True, "contract_ok": True,  # noqa: F405
                "errors": [], "promotion_bytes": 1932, "frontier_count": 0,
                "root_count": 9}
    except Exception as error:
        return {"schema": VERIFY_SCHEMA, "verified": False, "contract_ok": False,  # noqa: F405
                "errors": [str(error)], "promotion_bytes": 0,
                "frontier_count": None, "root_count": None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
