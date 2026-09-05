#!/usr/bin/env python3
"""Independently rebuild raw denominators for CFG proven-roots v17."""

from __future__ import annotations

import argparse
import bisect
from collections import Counter
import gzip
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
from tools.export_rom_cfg_proven_roots_v4 import _load_payload  # noqa: E402
from tools.export_rom_cfg_proven_roots_v7 import _baselines  # noqa: E402
from tools.rom_cfg_proven_roots_v17_contract import *  # noqa: E402,F403
from tools.thumb_branch import decode_thumb_bl  # noqa: E402


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


def _load_baseline(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[int]]:
    manifest_raw = _safe(root, PRECOVERAGE_DIR / MANIFEST_NAME).read_bytes()  # noqa: F405
    archive_raw = _safe(root, PRECOVERAGE_DIR / "rom-byte-coverage.json.gz").read_bytes()  # noqa: F405
    if _sha(manifest_raw) != PRECOVERAGE_MANIFEST_SHA256 or _sha(archive_raw) != PRECOVERAGE_ARCHIVE_SHA256:  # noqa: F405
        raise ValueError("immutable precoverage identity changed")
    record = json.loads(manifest_raw).get("files", {}).get("rom-byte-coverage.json.gz", {})
    if record != {"compression": "gzip", "sha256": PRECOVERAGE_ARCHIVE_SHA256, "size": len(archive_raw), "uncompressed_sha256": PRECOVERAGE_RAW_SHA256, "uncompressed_size": PRECOVERAGE_RAW_SIZE}:  # noqa: F405
        raise ValueError("immutable precoverage manifest changed")
    try:
        raw = gzip.decompress(archive_raw)
    except Exception as error:
        raise ValueError("immutable precoverage gzip invalid") from error
    if len(raw) != PRECOVERAGE_RAW_SIZE or _sha(raw) != PRECOVERAGE_RAW_SHA256:  # noqa: F405
        raise ValueError("immutable precoverage payload changed")
    coverage = json.loads(raw)
    if any(coverage.get("summary", {}).get(key) != value for key, value in BASELINE.items()):  # noqa: F405
        raise ValueError("immutable precoverage summary changed")
    segments = coverage.get("segments")
    if not isinstance(segments, list) or len(segments) != BASELINE["segment_count"]:  # noqa: F405
        raise ValueError("immutable precoverage segment denominator changed")
    starts, cursor = [], 0
    for row in segments:
        interval = row.get("range")
        if not isinstance(interval, list) or len(interval) != 2 or interval[0] != cursor or not isinstance(interval[1], int) or interval[1] <= cursor:
            raise ValueError("immutable precoverage segment order changed")
        starts.append(cursor)
        cursor = interval[1]
    if cursor != ROM_SIZE:  # noqa: F405
        raise ValueError("immutable precoverage accounting changed")
    source = {"artifact": PRECOVERAGE_DIR.as_posix(), "manifest_sha256": PRECOVERAGE_MANIFEST_SHA256, "archive_sha256": PRECOVERAGE_ARCHIVE_SHA256, "raw_sha256": PRECOVERAGE_RAW_SHA256, **BASELINE}  # noqa: F405
    return source, segments, starts


def _segment_at(segments: list[dict[str, Any]], starts: list[int], offset: int) -> dict[str, Any]:
    row = segments[bisect.bisect_right(starts, offset) - 1]
    if not row["range"][0] <= offset < row["range"][1]:
        raise ValueError("coverage segment lookup failed")
    return row


def _merge(intervals: list[tuple[int, int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for start, end in sorted(intervals):
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def _raw_rebuild(root: Path, rom: bytes, segments: list[dict[str, Any]], starts: list[int]) -> dict[str, Any]:
    matches = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        if decode_thumb_bl(offset, first, second) == ROOT:  # noqa: F405
            matches.append((offset, ROOT))  # noqa: F405
    if tuple(matches) != BL_MATCHES or _sha(b"".join(rom[offset : offset + 4] for offset, _ in matches)) != PRODUCER_PACKED_SHA256:  # noqa: F405
        raise ValueError("raw producer denominator changed")
    producers = []
    for offset, target in matches:
        owner = _segment_at(segments, starts, offset)
        if tuple(owner["range"]) != PRODUCER_OWNER_RANGE or owner.get("primary_class") != PRODUCER_OWNER_CLASS or owner.get("primary_claim_ids") != [PRODUCER_OWNER_CLAIM]:  # noqa: F405
            raise ValueError("raw producer owner changed")
        producers.append({"file_offset": offset, "gba_address": f"0x{ROM_BASE + offset:08X}", "target_file_offset": target, "target_gba_address": f"0x{ROM_BASE + target:08X}", "raw_hex": rom[offset : offset + 4].hex(), "bytes_sha256": _sha(rom[offset : offset + 4]), "coverage_owner_range": owner["range"], "coverage_owner_class": owner["primary_class"], "coverage_owner_claim_ids": owner["primary_claim_ids"], "accepted_as_root_proof": True})  # noqa: F405

    _, baseline_nodes, baseline_owners, _ = _baselines(root, rom)
    v7 = _load_payload(root, V7_PAYLOAD_PATH, V7_PAYLOAD_SHA256)  # noqa: F405
    nodes7, owners7 = _nodes_from_blocks(rom, v7["extension"]["blocks"], label="proven_roots_v7")
    baseline_nodes["proven_roots_v7"], baseline_owners["proven_roots_v7"] = nodes7, owners7
    root_row = {"root_id": "root-thumb-0914d8", "mode": "thumb", "file_offset": ROOT, "gba_address": f"0x{ROM_BASE + ROOT:08X}", "entry_size": 4, "entry_sha256": _sha(rom[ROOT : ROOT + 4]), "sources": [{"file_offset": offset} for offset, _ in matches]}  # noqa: F405
    if root_row["entry_sha256"] != ROOT_ENTRY_SHA256:  # noqa: F405
        raise ValueError("root entry changed")
    nodes, rejected, incoming, crosses = _traverse_delta(rom, [root_row], baseline_nodes)
    blocks, mapping = _build_blocks(rom, nodes, {("thumb", ROOT)})  # noqa: F405
    frontiers = _frontier_records(nodes, rejected, incoming, [root_row], mapping)
    full = {"instruction_count": len(nodes), "instruction_bytes": sum(row["size"] for row in nodes.values()), "basic_block_count": len(blocks), "decode_reject_count": len(rejected), "baseline_cross_edge_count": len(crosses), "frontier_count": len(frontiers)}
    if full != FULL_METRICS:  # noqa: F405
        raise ValueError("full raw closure changed")
    low, high = TARGET_RANGE  # noqa: F405
    local_nodes = {key: node for key, node in nodes.items() if low <= key[1] < high}
    local_blocks = [row for row in blocks if low <= row["range"][0] < high]
    local_crosses = [row for row in crosses if low <= row[0][1] < high]
    local_frontiers = [[row["source"]["instruction_offset"], row["reason"]] for row in frontiers if isinstance(row.get("source", {}).get("instruction_offset"), int) and low <= row["source"]["instruction_offset"] < high]
    code_ranges = _merge([(offset, offset + node["size"]) for (_, offset), node in local_nodes.items()])
    if tuple(map(tuple, code_ranges)) != CODE_RANGES or _vector_sha(code_ranges) != CODE_RANGE_SHA256 or _sha(b"".join(rom[start:end] for start, end in code_ranges)) != CODE_PACKED_SHA256:  # noqa: F405
        raise ValueError("raw local code projection changed")
    bindings = []
    # Rebuild all closure-wide LDR sources whose exact target word lies in the
    # promoted interval; source locality is intentionally not assumed.
    for (_, offset), node in sorted(nodes.items()):
        if node["size"] == 2:
            halfword = struct.unpack_from("<H", rom, offset)[0]
            if halfword & 0xF800 == 0x4800:
                target = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
                if low <= target and target + 4 <= high:
                    bindings.append([offset, target, rom[offset : offset + 2].hex(), rom[target : target + 4].hex()])
    targets = sorted({row[1] for row in bindings})
    literal_ranges = _merge([(target, target + 4) for target in targets])
    if tuple(map(tuple, literal_ranges)) != LITERAL_RANGES or _vector_sha(literal_ranges) != LITERAL_RANGE_SHA256 or _sha(b"".join(rom[start:end] for start, end in literal_ranges)) != LITERAL_PACKED_SHA256:  # noqa: F405
        raise ValueError("raw local literal projection changed")
    local = {"instruction_count": len(local_nodes), "instruction_bytes": sum(end - start for start, end in code_ranges), "basic_block_count": len(local_blocks), "baseline_call_edge_count": len(local_crosses), "frontiers": local_frontiers, "unique_literal_word_count": len(targets), "literal_reference_count": len(bindings), "literal_bytes": sum(end - start for start, end in literal_ranges), "flow_kind_counts": dict(Counter(node["flow_kind"] for node in local_nodes.values())), "literal_binding_vector_sha256": _vector_sha(bindings)}
    for key, value in LOCAL_METRICS.items():  # noqa: F405
        if local.get(key) != value:
            raise ValueError(f"raw local metric changed: {key}")
    if local_frontiers != [[0x091FD6, "indirect_pc_target"]] or any(row[1] != "call_target" for row in local_crosses):
        raise ValueError("raw local boundary changed")
    return {"producers": producers, "full": full, "local": local, "code_ranges": code_ranges, "literal_ranges": literal_ranges}


def _implementation(root: Path) -> dict[str, Any]:
    value: dict[str, Any] = {"binding": "contract-exporter-verifier-tests-hash-bound", "paths": {}}
    for name, path in IMPLEMENTATION_PATHS.items():  # noqa: F405
        value["paths"][name] = path.as_posix()
        value[f"{name}_sha256"] = _sha(_safe(root, path).read_bytes())
    return value


def _failure(error: Exception | str) -> dict[str, Any]:
    return {"schema": VERIFY_SCHEMA, "verified": False, "errors": [str(error)], "promotion_bytes": 0, "preserved_unknown_gap_count": len(GAPS)}  # noqa: F405


def verify_root(root: Path, artifact: Path, *, expected_receipt_path: Path | None = None) -> dict[str, Any]:
    try:
        root = root.resolve(strict=True)
        artifact = artifact if artifact.is_absolute() else root / artifact
        artifact = artifact.absolute()
        if artifact.is_symlink() or not artifact.is_dir() or {path.name for path in artifact.iterdir()} != {PAYLOAD_NAME, MANIFEST_NAME}:  # noqa: F405
            raise ValueError("artifact directory or file set changed")
        payload_raw = (artifact / PAYLOAD_NAME).read_bytes()  # noqa: F405
        manifest_raw = (artifact / MANIFEST_NAME).read_bytes()  # noqa: F405
        payload, manifest = json.loads(payload_raw), json.loads(manifest_raw)
        if _canonical(payload) != payload_raw or _canonical(manifest) != manifest_raw:
            raise ValueError("artifact JSON is not canonical")
        rom = _safe(root, ROM_PATH).read_bytes()  # noqa: F405
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:  # noqa: F405
            raise ValueError("base ROM identity changed")
        baseline, segments, starts = _load_baseline(root)
        rebuilt = _raw_rebuild(root, rom, segments, starts)
        if payload.get("schema") != SCHEMA or payload.get("rom") != {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256}:  # noqa: F405
            raise ValueError("payload schema or ROM identity changed")
        if payload.get("precoverage") != baseline or payload.get("implementation") != _implementation(root):
            raise ValueError("payload baseline or implementation identity changed")
        root_payload = payload.get("root", {})
        if root_payload != {"file_offset": ROOT, "gba_address": f"0x{ROM_BASE + ROOT:08X}", "entry_sha256": ROOT_ENTRY_SHA256, "accepted_producers": rebuilt["producers"]}:  # noqa: F405
            raise ValueError("payload root proof differs from raw rebuild")
        if payload.get("full_closure_denominator") != rebuilt["full"] or payload.get("target_local_denominator") != rebuilt["local"]:
            raise ValueError("payload traversal differs from raw rebuild")
        promotion = payload.get("promotion", {})
        semantic = rebuilt["code_ranges"] + rebuilt["literal_ranges"]
        for start, end in semantic:
            cursor = start
            while cursor < end:
                owner = _segment_at(segments, starts, cursor)
                if owner.get("primary_class") != "unknown":
                    raise ValueError("promotion escaped immutable baseline unknown")
                cursor = min(end, owner["range"][1])
        union = _merge([tuple(row) for row in semantic])
        claims = []
        for kind, rows in (("reachable_thumb_code", rebuilt["code_ranges"]), ("consumed_literal_words", rebuilt["literal_ranges"])):
            for index, (start, end) in enumerate(rows, 1):
                claims.append({"id": f"cfg-v17-{kind}-{index:02d}-{start:06x}", "kind": kind, "range": [start, end], "bytes_sha256": _sha(rom[start:end])})
        expected_promotion = {"promotion_batch": "rom-cfg-proven-roots-v17", "primary_class": "armv4t_cfg_proven_roots_v17", "claim_kind": "armv4t_cfg_proven_roots_v17_exact_bytes", "target_range": list(TARGET_RANGE), "code_ranges": rebuilt["code_ranges"], "literal_ranges": rebuilt["literal_ranges"], "union_ranges": union, "preserved_unknown_gaps": [list(row) for row in GAPS], "code_bytes": 2092, "literal_bytes": 308, "promotion_bytes": 2400, "preserved_unknown_bytes": 10, "claims": claims}  # noqa: F405
        if promotion != expected_promotion:
            raise ValueError("payload promotion differs from raw rebuild")
        expected_projection = {"baseline_unknown_bytes": BASELINE["unknown_bytes"], "promoted_bytes": 2400, "remaining_unknown_bytes": BASELINE["unknown_bytes"] - 2400}  # noqa: F405
        expected_scope = {"raw_rom_redecoded": True, "target_limited_direct_producer_denominator": True, "natural_runtime_reachability": False, "alignment_gap_classification": False, "adjacent_or_envelope_bytes": False, "editing_relocation_or_free_space": False}
        if payload.get("coverage_projection") != expected_projection or payload.get("scope") != expected_scope:
            raise ValueError("projection or scope changed")
        if manifest.get("files", {}).get(PAYLOAD_NAME) != {"sha256": _sha(payload_raw), "size": len(payload_raw)}:  # noqa: F405
            raise ValueError("manifest payload identity changed")
        if any(manifest.get(key) != payload.get(key) for key in ("rom", "precoverage", "implementation", "promotion", "coverage_projection", "scope")):
            raise ValueError("manifest payload projection changed")
        if manifest.get("schema") != "git-artifact-promotion-v1" or manifest.get("artifact_schema") != SCHEMA:  # noqa: F405
            raise ValueError("manifest schema changed")
        receipt = expected_receipt_path.absolute() if expected_receipt_path is not None else artifact
        relative = receipt.relative_to(root).as_posix()
        expected_commands = {
            "producer": ["python3", "-I", "-S", "tools/export_rom_cfg_proven_roots_v17.py", "--root", ".", "--output", relative],
            "verifier": ["python3", "-I", "-S", "tools/verify_rom_cfg_proven_roots_v17.py", "--root", ".", "--artifact", relative],
        }
        status = manifest.get("artifact_status")
        if manifest.get("producer", {}).get("command") != expected_commands["producer"] or manifest.get("verifier", {}).get("command") != expected_commands["verifier"]:
            raise ValueError("manifest command receipt changed")
        if status == "candidate":
            if manifest.get("verifier", {}).get("exit_code") is not None or "report" in manifest.get("verifier", {}):
                raise ValueError("candidate verifier receipt changed")
        elif status == "accepted":
            report = manifest.get("verifier", {}).get("report", {})
            if manifest.get("verifier", {}).get("exit_code") != 0 or not report.get("verified") or report.get("promotion_bytes") != 2400:
                raise ValueError("accepted verifier receipt changed")
        else:
            raise ValueError("artifact status changed")
        return {"schema": VERIFY_SCHEMA, "verified": True, "errors": [], "rom_sha256": ROM_SHA256, "precoverage_sha256": PRECOVERAGE_RAW_SHA256, "root_count": 1, "accepted_producer_count": 2, "instruction_count": 950, "code_bytes": 2092, "literal_word_count": 77, "literal_bytes": 308, "promotion_bytes": 2400, "preserved_unknown_gap_count": 5}  # noqa: F405
    except Exception as error:
        return _failure(error)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = verify_root(args.root, args.artifact)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
