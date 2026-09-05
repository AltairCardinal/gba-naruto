#!/usr/bin/env python3
"""Independently rebuild and verify the CFG proven-roots v16 artifact."""

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
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
for _path in (PROJECT_ROOT, VENDOR_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from tools.export_rom_cfg_inventory import _build_blocks, _frontier_records  # noqa: E402
from tools.export_rom_cfg_proven_roots import _nodes_from_blocks  # noqa: E402
from tools.export_rom_cfg_proven_roots_v2 import _traverse_delta  # noqa: E402
from tools.export_rom_cfg_proven_roots_v4 import _extension_summary, _load_payload  # noqa: E402
from tools.export_rom_cfg_proven_roots_v7 import _baselines  # noqa: E402
from tools.rom_cfg_proven_roots_v16_contract import *  # noqa: E402,F403
from tools.thumb_branch import decode_thumb_bl  # noqa: E402


EXPECTED_REPORT = {
    "schema": VERIFY_SCHEMA,  # noqa: F405
    "verified": True,
    "errors": [],
    "control_flow_oracle": "armv4t-raw-encoding",
    "rom_sha256": ROM_SHA256,  # noqa: F405
    "coverage_sha256": COVERAGE_SHA256,  # noqa: F405
    "root_count": 15,
    "accepted_producer_count": 19,
    "rejected_nonproof_match_count": 2,
    "decoded_instruction_count": 369,
    "reachable_instruction_bytes": 778,
    "decoded_basic_block_count": 70,
    "decode_reject_count": 0,
    "baseline_cross_edge_count": 18,
    "promoted_from_unknown_bytes": 778,
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _vector_sha(value: object) -> str:
    return _sha((json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode())


def _safe(root: Path, relative: Path) -> Path:
    root = root.resolve(strict=True)
    path = root / relative
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root) or path.is_symlink():
        raise ValueError(f"unsafe input path: {relative}")
    return resolved


def _coverage(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[int]]:
    raw = _safe(root, COVERAGE_PATH).read_bytes()  # noqa: F405
    if _sha(raw) != COVERAGE_SHA256:  # noqa: F405
        raise ValueError("coverage baseline identity changed")
    value = json.loads(raw)
    summary = value.get("summary", {})
    if (summary.get("classified_bytes"), summary.get("unknown_bytes")) != (COVERAGE_CLASSIFIED_BYTES, COVERAGE_UNKNOWN_BYTES):  # noqa: F405
        raise ValueError("coverage baseline summary changed")
    if summary["classified_bytes"] + summary["unknown_bytes"] != ROM_SIZE:  # noqa: F405
        raise ValueError("coverage baseline accounting changed")
    segments = value["segments"]
    return {"path": COVERAGE_PATH.as_posix(), "sha256": COVERAGE_SHA256, "classified_bytes": summary["classified_bytes"], "unknown_bytes": summary["unknown_bytes"], "segment_count": len(segments)}, segments, [row["range"][0] for row in segments]  # noqa: F405


def _segment_at(segments: list[dict[str, Any]], starts: list[int], offset: int) -> dict[str, Any]:
    row = segments[bisect.bisect_right(starts, offset) - 1]
    if not row["range"][0] <= offset < row["range"][1]:
        raise ValueError("coverage segment lookup failed")
    return row


def _producer_denominator(rom: bytes, segments: list[dict[str, Any]], starts: list[int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    matches: list[tuple[int, int, bool]] = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        target = decode_thumb_bl(offset, first, second)
        if target in set(ROOTS):  # noqa: F405
            owner = _segment_at(segments, starts, offset)
            known = owner["range"][1] >= offset + 4 and owner["primary_class"] != "unknown" and any(token in owner["primary_class"] for token in ("code", "thumb", "arm"))
            matches.append((offset, target, known))
    if tuple(matches) != BL_MATCHES:  # noqa: F405
        raise ValueError("target-limited Thumb BL denominator changed")
    accepted, rejected = [], []
    for offset, target, known in matches:
        owner = _segment_at(segments, starts, offset)
        row = {
            "file_offset": offset, "gba_address": f"0x{ROM_BASE + offset:08X}",  # noqa: F405
            "target_file_offset": target, "target_gba_address": f"0x{ROM_BASE + target:08X}",  # noqa: F405
            "raw_hex": rom[offset : offset + 4].hex(), "bytes_sha256": _sha(rom[offset : offset + 4]),
            "coverage_owner_range": owner["range"], "coverage_owner_class": owner["primary_class"],
            "coverage_owner_claim_ids": owner["primary_claim_ids"],
        }
        if known:
            row["accepted_as_root_proof"] = True
            accepted.append(row)
        else:
            row.update({"accepted_as_root_proof": False, "promoted": False, "reason": "source_owner_unknown"})
            rejected.append(row)
    if len(accepted) != 19 or len(rejected) != 2:
        raise ValueError("producer partition changed")
    return accepted, rejected


def _merged_ranges(nodes: dict[tuple[str, int], dict[str, Any]]) -> list[list[int]]:
    result: list[list[int]] = []
    for (_, start), node in sorted(nodes.items(), key=lambda item: item[0][1]):
        end = start + node["size"]
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def _apply_soft_reset_terminal(
    rom: bytes,
    nodes: dict[tuple[str, int], dict[str, Any]],
    incoming: dict[tuple[str, int], list[tuple[tuple[str, int], str]]],
) -> None:
    terminal = ("thumb", 0x09C106)
    pool = tuple(("thumb", offset) for offset in range(0x09C108, 0x09C110, 2))
    node = nodes.get(terminal)
    if (
        rom[0x09C106:0x09C108] != b"\x00\xdf"
        or node is None
        or node.get("mnemonic") != "svc"
        or node.get("op_str") != "#0"
        or node.get("successors")
        != [{"kind": "fallthrough", "mode": "thumb", "file_offset": 0x09C108}]
    ):
        raise ValueError("frozen BIOS SoftReset terminal changed")
    for index, key in enumerate(pool):
        expected_source = terminal if index == 0 else pool[index - 1]
        if key not in nodes or incoming.get(key) != [(expected_source, "fallthrough")]:
            raise ValueError("SoftReset inline literal-pool boundary changed")
    node["successors"] = []
    node["flow_kind"] = "terminal_supervisor_call"
    for key in pool:
        del nodes[key]
        incoming.pop(key, None)


def _traversal(root: Path, rom: bytes, accepted: list[dict[str, Any]], segments: list[dict[str, Any]], starts: list[int]) -> dict[str, Any]:
    _, baseline_nodes, baseline_owners, _ = _baselines(root, rom)
    v7 = _load_payload(root, V7_PAYLOAD_PATH, V7_PAYLOAD_SHA256)  # noqa: F405
    nodes7, owners7 = _nodes_from_blocks(rom, v7["extension"]["blocks"], label="proven_roots_v7")
    baseline_nodes["proven_roots_v7"], baseline_owners["proven_roots_v7"] = nodes7, owners7
    by_target = {target: [] for target in ROOTS}  # noqa: F405
    for row in accepted:
        by_target[row["target_file_offset"]].append(row["file_offset"])
    roots = [{"root_id": f"root-thumb-{offset:06x}", "mode": "thumb", "file_offset": offset, "gba_address": f"0x{ROM_BASE + offset:08X}", "entry_size": 4, "entry_sha256": _sha(rom[offset : offset + 4]), "sources": [{"file_offset": source} for source in by_target[offset]]} for offset in ROOTS]  # noqa: F405
    nodes, rejected, incoming, crosses = _traverse_delta(rom, roots, baseline_nodes)
    _apply_soft_reset_terminal(rom, nodes, incoming)
    blocks, mapping = _build_blocks(rom, nodes, {("thumb", offset) for offset in ROOTS})  # noqa: F405
    frontiers = _frontier_records(nodes, rejected, incoming, roots, mapping)
    summary = _extension_summary(nodes, blocks, frontiers)
    summary.update({"decode_reject_count": len(rejected), "baseline_cross_edge_count": len(crosses)})
    if summary != {**EXPECTED_METRICS, "frontier_count": 12, "frontier_reasons": {"bios_swi_external": 2, "indirect_pc_target": 10}}:  # noqa: F405
        raise ValueError("merged traversal metrics changed")
    ranges = _merged_ranges(nodes)
    if tuple(map(tuple, ranges)) != PROMOTION_RANGES or _vector_sha(ranges) != PROMOTION_RANGE_SHA256:  # noqa: F405
        raise ValueError("promotion range vector changed")
    packed = b"".join(rom[start:end] for start, end in ranges)
    if len(packed) != 778 or _sha(packed) != PROMOTION_PACKED_SHA256:  # noqa: F405
        raise ValueError("promotion bytes changed")
    for start, end in ranges:
        cursor = start
        while cursor < end:
            owner = _segment_at(segments, starts, cursor)
            if owner["primary_class"] != "unknown":
                raise ValueError("promotion escaped baseline unknown")
            cursor = min(end, owner["range"][1])
    instruction_vector = [[mode, offset, node["size"], node["bytes_sha256"], node["mnemonic"], node["op_str"], node["flow_kind"]] for (mode, offset), node in sorted(nodes.items())]
    cross_vector = json.loads(json.dumps(crosses))
    return {"summary": summary, "ranges": ranges, "range_vector_sha256": PROMOTION_RANGE_SHA256, "packed_sha256": PROMOTION_PACKED_SHA256, "instruction_vector_sha256": _vector_sha(instruction_vector), "block_vector_sha256": _vector_sha(blocks), "frontier_vector_sha256": _vector_sha(frontiers), "baseline_cross_edges": cross_vector, "baseline_cross_edge_vector_sha256": _vector_sha(cross_vector)}  # noqa: F405


def _implementation(root: Path) -> dict[str, Any]:
    paths = {"contract": "tools/rom_cfg_proven_roots_v16_contract.py", "exporter": "tools/export_rom_cfg_proven_roots_v16.py", "verifier": "tools/verify_rom_cfg_proven_roots_v16.py", "test_exporter": "tests/test_export_rom_cfg_proven_roots_v16.py", "test_verifier": "tests/test_verify_rom_cfg_proven_roots_v16.py"}
    result: dict[str, Any] = {"binding": "artifact-contract-exporter-verifier-tests-hash-bound", "paths": paths}
    for name, relative in paths.items():
        result[f"{name}_sha256"] = _sha(_safe(root, Path(relative)).read_bytes())
    return result


def _expected_payload(root: Path) -> dict[str, Any]:
    rom = _safe(root, ROM_PATH).read_bytes()  # noqa: F405
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:  # noqa: F405
        raise ValueError("base ROM identity changed")
    coverage, segments, starts = _coverage(root)
    accepted, rejected = _producer_denominator(rom, segments, starts)
    traversal = _traversal(root, rom, accepted, segments, starts)
    return {"schema": SCHEMA, "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256}, "coverage_baseline": coverage, "roots": list(ROOTS), "accepted_producers": accepted, "rejected_nonproof_matches": rejected, "traversal": traversal, "promotion": {"ranges": traversal["ranges"], "promotion_bytes": 778, "promoted_from_unknown_bytes": 778, "baseline_unknown_bytes": COVERAGE_UNKNOWN_BYTES, "remaining_unknown_bytes": COVERAGE_UNKNOWN_BYTES - 778, "unknown_accounting_assertion": "baseline_unknown_bytes == remaining_unknown_bytes + promoted_from_unknown_bytes", "scope": "frozen_baseline_unknown_code_bytes_only"}, "implementation": _implementation(root), "scope": {"nonclaims": {name: False for name in NONCLAIMS}}}  # noqa: F405


def _commands(root: Path, output: Path) -> tuple[list[str], list[str]]:
    relative = output.resolve().relative_to(root.resolve()).as_posix()
    return (["python3", "-I", "-S", "tools/export_rom_cfg_proven_roots_v16.py", "--root", ".", "--output", relative], ["python3", "-I", "-S", "tools/verify_rom_cfg_proven_roots_v16.py", "--root", ".", "--artifact", relative])


def _expected_manifest(root: Path, receipt: Path, payload: dict[str, Any], raw: bytes) -> dict[str, Any]:
    producer, verifier = _commands(root, receipt)
    return {"schema": PROMOTION_SCHEMA, "artifact_schema": SCHEMA, "artifact_status": "accepted", "rom": payload["rom"], "coverage_baseline": payload["coverage_baseline"], "files": {PAYLOAD_NAME: {"size": len(raw), "sha256": _sha(raw)}}, "producer": {"command": producer, "implementation": payload["implementation"]}, "verifier": {"schema": VERIFY_SCHEMA, "command": verifier, "exit_code": 0, "report": EXPECTED_REPORT}, "implementation": payload["implementation"], "scope": payload["scope"]}  # noqa: F405


def _failure(error: Exception | str) -> dict[str, Any]:
    value = dict(EXPECTED_REPORT)
    value.update({"verified": False, "errors": [str(error)]})
    return value


def verify_rom_cfg_proven_roots_v16(root: Path, artifact_dir: Path, *, expected_receipt_path: Path | None = None) -> dict[str, Any]:
    try:
        root = root.resolve(strict=True)
        artifact = artifact_dir if artifact_dir.is_absolute() else root / artifact_dir
        artifact = artifact.absolute()
        if artifact.is_symlink() or not artifact.exists() or not artifact.is_dir():
            raise ValueError("artifact directory is missing or unsafe")
        if {path.name for path in artifact.iterdir()} != {PAYLOAD_NAME, MANIFEST_NAME}:  # noqa: F405
            raise ValueError("artifact file set changed")
        payload_path, manifest_path = artifact / PAYLOAD_NAME, artifact / MANIFEST_NAME  # noqa: F405
        if payload_path.is_symlink() or manifest_path.is_symlink():
            raise ValueError("artifact files may not be symlinks")
        payload_raw, manifest_raw = payload_path.read_bytes(), manifest_path.read_bytes()
        payload, manifest = json.loads(payload_raw), json.loads(manifest_raw)
        if _canonical(payload) != payload_raw or _canonical(manifest) != manifest_raw:
            raise ValueError("artifact JSON is not canonical")
        expected_payload = _expected_payload(root)
        if payload != expected_payload:
            raise ValueError("payload differs from independent raw-input rebuild")
        receipt = expected_receipt_path.absolute() if expected_receipt_path is not None else artifact
        if manifest != _expected_manifest(root, receipt, expected_payload, payload_raw):
            raise ValueError("manifest or identity receipt changed")
        return dict(EXPECTED_REPORT)
    except Exception as error:
        return _failure(error)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = verify_rom_cfg_proven_roots_v16(args.root, args.artifact)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
