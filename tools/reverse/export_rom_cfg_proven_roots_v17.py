#!/usr/bin/env python3
"""Export the combined code/literal CFG proven-roots v17 packet."""

from __future__ import annotations

import argparse
import bisect
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
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


def _precoverage(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[int]]:
    manifest_raw = _safe(root, PRECOVERAGE_DIR / MANIFEST_NAME).read_bytes()  # noqa: F405
    archive_raw = _safe(root, PRECOVERAGE_DIR / "rom-byte-coverage.json.gz").read_bytes()  # noqa: F405
    if _sha(manifest_raw) != PRECOVERAGE_MANIFEST_SHA256 or _sha(archive_raw) != PRECOVERAGE_ARCHIVE_SHA256:  # noqa: F405
        raise ValueError("immutable precoverage identity changed")
    manifest = json.loads(manifest_raw)
    record = manifest.get("files", {}).get("rom-byte-coverage.json.gz", {})
    if record != {
        "compression": "gzip", "sha256": PRECOVERAGE_ARCHIVE_SHA256, "size": len(archive_raw),  # noqa: F405
        "uncompressed_sha256": PRECOVERAGE_RAW_SHA256, "uncompressed_size": PRECOVERAGE_RAW_SIZE,  # noqa: F405
    }:
        raise ValueError("immutable precoverage manifest changed")
    try:
        raw = gzip.decompress(archive_raw)
    except Exception as error:
        raise ValueError("immutable precoverage gzip invalid") from error
    if len(raw) != PRECOVERAGE_RAW_SIZE or _sha(raw) != PRECOVERAGE_RAW_SHA256:  # noqa: F405
        raise ValueError("immutable precoverage payload changed")
    coverage = json.loads(raw)
    summary = coverage.get("summary", {})
    if any(summary.get(key) != value for key, value in BASELINE.items()):  # noqa: F405
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
    source = {
        "artifact": PRECOVERAGE_DIR.as_posix(), "manifest_sha256": PRECOVERAGE_MANIFEST_SHA256,  # noqa: F405
        "archive_sha256": PRECOVERAGE_ARCHIVE_SHA256, "raw_sha256": PRECOVERAGE_RAW_SHA256,  # noqa: F405
        **BASELINE,  # noqa: F405
    }
    return source, segments, starts


def _segment_at(segments: list[dict[str, Any]], starts: list[int], offset: int) -> dict[str, Any]:
    row = segments[bisect.bisect_right(starts, offset) - 1]
    if not row["range"][0] <= offset < row["range"][1]:
        raise ValueError("coverage segment lookup failed")
    return row


def _producers(rom: bytes, segments: list[dict[str, Any]], starts: list[int]) -> list[dict[str, Any]]:
    matches = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        if decode_thumb_bl(offset, first, second) == ROOT:  # noqa: F405
            matches.append((offset, ROOT))  # noqa: F405
    if tuple(matches) != BL_MATCHES:  # noqa: F405
        raise ValueError("target-limited Thumb BL denominator changed")
    if _sha(b"".join(rom[offset : offset + 4] for offset, _ in matches)) != PRODUCER_PACKED_SHA256:  # noqa: F405
        raise ValueError("producer bytes changed")
    result = []
    for offset, target in matches:
        owner = _segment_at(segments, starts, offset)
        if tuple(owner["range"]) != PRODUCER_OWNER_RANGE or owner.get("primary_class") != PRODUCER_OWNER_CLASS or owner.get("primary_claim_ids") != [PRODUCER_OWNER_CLAIM]:  # noqa: F405
            raise ValueError("producer coverage owner changed")
        result.append({
            "file_offset": offset, "gba_address": f"0x{ROM_BASE + offset:08X}",  # noqa: F405
            "target_file_offset": target, "target_gba_address": f"0x{ROM_BASE + target:08X}",  # noqa: F405
            "raw_hex": rom[offset : offset + 4].hex(), "bytes_sha256": _sha(rom[offset : offset + 4]),
            "coverage_owner_range": owner["range"], "coverage_owner_class": owner["primary_class"],
            "coverage_owner_claim_ids": owner["primary_claim_ids"], "accepted_as_root_proof": True,
        })
    return result


def _merged_ranges(intervals: list[tuple[int, int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for start, end in sorted(intervals):
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def _traversal(root: Path, rom: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    _, baseline_nodes, baseline_owners, _ = _baselines(root, rom)
    v7 = _load_payload(root, V7_PAYLOAD_PATH, V7_PAYLOAD_SHA256)  # noqa: F405
    nodes7, owners7 = _nodes_from_blocks(rom, v7["extension"]["blocks"], label="proven_roots_v7")
    baseline_nodes["proven_roots_v7"], baseline_owners["proven_roots_v7"] = nodes7, owners7
    root_row = {
        "root_id": "root-thumb-0914d8", "mode": "thumb", "file_offset": ROOT,  # noqa: F405
        "gba_address": f"0x{ROM_BASE + ROOT:08X}", "entry_size": 4,  # noqa: F405
        "entry_sha256": _sha(rom[ROOT : ROOT + 4]),  # noqa: F405
        "sources": [{"file_offset": offset} for offset, _ in BL_MATCHES],  # noqa: F405
    }
    if root_row["entry_sha256"] != ROOT_ENTRY_SHA256:  # noqa: F405
        raise ValueError("root entry changed")
    nodes, rejected, incoming, crosses = _traverse_delta(rom, [root_row], baseline_nodes)
    blocks, mapping = _build_blocks(rom, nodes, {("thumb", ROOT)})  # noqa: F405
    frontiers = _frontier_records(nodes, rejected, incoming, [root_row], mapping)
    full = {
        "instruction_count": len(nodes), "instruction_bytes": sum(node["size"] for node in nodes.values()),
        "basic_block_count": len(blocks), "decode_reject_count": len(rejected),
        "baseline_cross_edge_count": len(crosses), "frontier_count": len(frontiers),
    }
    if full != FULL_METRICS:  # noqa: F405
        raise ValueError("full root closure metrics changed")
    target_start, target_end = TARGET_RANGE  # noqa: F405
    local_nodes = {key: node for key, node in nodes.items() if target_start <= key[1] < target_end}
    local_blocks = [block for block in blocks if target_start <= block["range"][0] < target_end]
    local_crosses = [row for row in crosses if target_start <= row[0][1] < target_end]
    local_frontiers = [
        [row["source"]["instruction_offset"], row["reason"]]
        for row in frontiers
        if isinstance(row.get("source", {}).get("instruction_offset"), int)
        and target_start <= row["source"]["instruction_offset"] < target_end
    ]
    code_ranges = _merged_ranges([(offset, offset + node["size"]) for (_, offset), node in local_nodes.items()])
    if tuple(map(tuple, code_ranges)) != CODE_RANGES or _vector_sha(code_ranges) != CODE_RANGE_SHA256:  # noqa: F405
        raise ValueError("target-local code range denominator changed")
    code_packed = b"".join(rom[start:end] for start, end in code_ranges)
    if len(code_packed) != LOCAL_METRICS["instruction_bytes"] or _sha(code_packed) != CODE_PACKED_SHA256:  # noqa: F405
        raise ValueError("target-local code bytes changed")
    literal_bindings = []
    # The source denominator is the whole proven root closure: 19 of the
    # consumed target-local words are read by reachable callers outside the
    # target interval.  Restricting sources to local_nodes would undercount.
    for (_, offset), node in sorted(nodes.items()):
        if node["size"] != 2:
            continue
        halfword = struct.unpack_from("<H", rom, offset)[0]
        if halfword & 0xF800 != 0x4800:
            continue
        target = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
        if target_start <= target and target + 4 <= target_end:
            literal_bindings.append([offset, target, rom[offset : offset + 2].hex(), rom[target : target + 4].hex()])
    literal_targets = sorted({row[1] for row in literal_bindings})
    literal_ranges = _merged_ranges([(target, target + 4) for target in literal_targets])
    if tuple(map(tuple, literal_ranges)) != LITERAL_RANGES or _vector_sha(literal_ranges) != LITERAL_RANGE_SHA256:  # noqa: F405
        raise ValueError("target-local literal range denominator changed")
    literal_packed = b"".join(rom[start:end] for start, end in literal_ranges)
    if len(literal_packed) != LOCAL_METRICS["literal_bytes"] or _sha(literal_packed) != LITERAL_PACKED_SHA256:  # noqa: F405
        raise ValueError("target-local literal bytes changed")
    local = {
        "instruction_count": len(local_nodes), "instruction_bytes": len(code_packed),
        "basic_block_count": len(local_blocks), "baseline_call_edge_count": len(local_crosses),
        "frontiers": local_frontiers, "unique_literal_word_count": len(literal_targets),
        "literal_reference_count": len(literal_bindings), "literal_bytes": len(literal_packed),
        "flow_kind_counts": {kind: sum(node["flow_kind"] == kind for node in local_nodes.values()) for kind in ("linear", "call", "conditional_branch", "unconditional_branch", "indirect_branch")},
        "literal_binding_vector_sha256": _vector_sha(literal_bindings),
    }
    for key, value in LOCAL_METRICS.items():  # noqa: F405
        if local.get(key) != value:
            raise ValueError(f"target-local metric changed: {key}")
    if local_frontiers != [[0x091FD6, "indirect_pc_target"]] or any(row[1] != "call_target" for row in local_crosses):
        raise ValueError("target-local frontier or opaque call denominator changed")
    return {"full_closure": full, "target_local": local}, {"code_ranges": code_ranges, "literal_ranges": literal_ranges}


def _assert_unknown(segments: list[dict[str, Any]], starts: list[int], ranges: list[list[int]]) -> None:
    for start, end in ranges:
        cursor = start
        while cursor < end:
            owner = _segment_at(segments, starts, cursor)
            if owner.get("primary_class") != "unknown":
                raise ValueError("promotion escaped immutable baseline unknown")
            cursor = min(end, owner["range"][1])


def _implementation(root: Path) -> dict[str, Any]:
    value: dict[str, Any] = {"binding": "contract-exporter-verifier-tests-hash-bound", "paths": {}}
    for name, path in IMPLEMENTATION_PATHS.items():  # noqa: F405
        value["paths"][name] = path.as_posix()
        value[f"{name}_sha256"] = _sha(_safe(root, path).read_bytes())
    return value


def build_payload(root: Path, rom_override: bytes | None = None) -> dict[str, Any]:
    root = root.resolve(strict=True)
    rom = _safe(root, ROM_PATH).read_bytes() if rom_override is None else rom_override  # noqa: F405
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:  # noqa: F405
        raise ValueError("base ROM identity changed")
    precoverage, segments, starts = _precoverage(root)
    producers = _producers(rom, segments, starts)
    traversal, ranges = _traversal(root, rom)
    semantic_ranges = ranges["code_ranges"] + ranges["literal_ranges"]
    _assert_unknown(segments, starts, semantic_ranges)
    union_ranges = _merged_ranges([tuple(row) for row in semantic_ranges])
    gaps = [list(row) for row in GAPS]  # noqa: F405
    promotion_bytes = sum(end - start for start, end in union_ranges)
    if promotion_bytes != 2400 or sum(end - start for start, end in gaps) != 10:
        raise ValueError("promotion accounting changed")
    claims = []
    for kind, rows in (("reachable_thumb_code", ranges["code_ranges"]), ("consumed_literal_words", ranges["literal_ranges"])):
        for index, (start, end) in enumerate(rows, 1):
            claims.append({"id": f"cfg-v17-{kind}-{index:02d}-{start:06x}", "kind": kind, "range": [start, end], "bytes_sha256": _sha(rom[start:end])})
    return {
        "schema": SCHEMA,  # noqa: F405
        "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},  # noqa: F405
        "precoverage": precoverage,
        "root": {"file_offset": ROOT, "gba_address": f"0x{ROM_BASE + ROOT:08X}", "entry_sha256": ROOT_ENTRY_SHA256, "accepted_producers": producers},  # noqa: F405
        "full_closure_denominator": traversal["full_closure"],
        "target_local_denominator": traversal["target_local"],
        "promotion": {
            "promotion_batch": "rom-cfg-proven-roots-v17", "primary_class": "armv4t_cfg_proven_roots_v17",
            "claim_kind": "armv4t_cfg_proven_roots_v17_exact_bytes", "target_range": list(TARGET_RANGE),  # noqa: F405
            "code_ranges": ranges["code_ranges"], "literal_ranges": ranges["literal_ranges"],
            "union_ranges": union_ranges, "preserved_unknown_gaps": gaps,
            "code_bytes": LOCAL_METRICS["instruction_bytes"], "literal_bytes": LOCAL_METRICS["literal_bytes"],  # noqa: F405
            "promotion_bytes": promotion_bytes, "preserved_unknown_bytes": 10, "claims": claims,
        },
        "coverage_projection": {"baseline_unknown_bytes": BASELINE["unknown_bytes"], "promoted_bytes": promotion_bytes, "remaining_unknown_bytes": BASELINE["unknown_bytes"] - promotion_bytes},  # noqa: F405
        "implementation": _implementation(root),
        "scope": {"raw_rom_redecoded": True, "target_limited_direct_producer_denominator": True, "natural_runtime_reachability": False, "alignment_gap_classification": False, "adjacent_or_envelope_bytes": False, "editing_relocation_or_free_space": False},
    }


def _validate_output(root: Path, output: Path) -> Path:
    output = output if output.is_absolute() else root / output
    output = output.absolute()
    allowed = (root / EXPERIMENT_OUTPUT_ROOT).resolve()  # noqa: F405
    official = (root / OFFICIAL_ARTIFACT).absolute()  # noqa: F405
    if not (output.is_relative_to(allowed) or output == official) or output.is_symlink():
        raise ValueError("output outside v17 experiment or official artifact scope")
    return output


def export(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    output = _validate_output(root, output)
    payload = build_payload(root)
    payload_raw = _canonical(payload)
    relative = output.relative_to(root).as_posix()
    from tools import verify_rom_cfg_proven_roots_v17 as verifier
    manifest = {
        "schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA, "artifact_status": "candidate",  # noqa: F405
        "rom": payload["rom"], "precoverage": payload["precoverage"], "implementation": payload["implementation"],
        "promotion": payload["promotion"], "coverage_projection": payload["coverage_projection"], "scope": payload["scope"],
        "producer": {"command": ["python3", "-I", "-S", "tools/export_rom_cfg_proven_roots_v17.py", "--root", ".", "--output", relative]},
        "verifier": {"command": ["python3", "-I", "-S", "tools/verify_rom_cfg_proven_roots_v17.py", "--root", ".", "--artifact", relative], "exit_code": None},
        "files": {PAYLOAD_NAME: {"sha256": _sha(payload_raw), "size": len(payload_raw)}},  # noqa: F405
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".v17-") as raw:
        staging = Path(raw) / output.name
        staging.mkdir()
        (staging / PAYLOAD_NAME).write_bytes(payload_raw)  # noqa: F405
        (staging / MANIFEST_NAME).write_bytes(_canonical(manifest))  # noqa: F405
        report = verifier.verify_root(root, staging, expected_receipt_path=output)
        if not report["verified"]:
            raise ValueError(f"independent verifier rejected candidate: {report['errors']}")
        manifest["artifact_status"] = "accepted"
        manifest["verifier"].update({"exit_code": 0, "report": report})
        (staging / MANIFEST_NAME).write_bytes(_canonical(manifest))  # noqa: F405
        if output.exists():
            if not output.is_dir() or any(output.iterdir()):
                raise ValueError("output artifact directory must be absent or empty")
            output.rmdir()
        shutil.move(staging, output)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
