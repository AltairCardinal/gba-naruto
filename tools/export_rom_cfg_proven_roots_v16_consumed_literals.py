#!/usr/bin/env python3
"""Export exact literal words consumed by the frozen proven-roots-v16 Thumb CFG."""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import shutil
import struct
import tempfile
from pathlib import Path
from typing import Any

ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SOURCE_DIR = Path("artifacts/rom-cfg-proven-roots-v16")
SOURCE_MANIFEST = SOURCE_DIR / "manifest.json"
SOURCE_PAYLOAD = SOURCE_DIR / "rom-cfg-proven-roots-v16.json"
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
PAYLOAD_NAME = "rom-cfg-proven-roots-v16-consumed-literals.json"
PROMOTION_BATCH = "rom-cfg-proven-roots-v16-consumed-literals-v1"
PRIMARY_CLASS = "armv4t_cfg_proven_roots_v16_consumed_literal_word"
CLAIM_KIND = "armv4t_cfg_proven_roots_v16_consumed_literal_word_bytes"
SOURCE_IDENTITIES = {
    SOURCE_MANIFEST: "1a8bec0c59290851b388a1bedbbf58957b18b6e1eddf483558d6e30cd6dc650a",
    SOURCE_PAYLOAD: "2d8f65b5345a89e02778bcdba2de01f420f3b378149c9eeb6e549c7d2c0ad99a",
    Path("tools/rom_cfg_proven_roots_v16_contract.py"): "778e4ae0adddcbda32098350b57ca7bf8873ebe78156a4c5102acc71cf4ba107",
    Path("tools/export_rom_cfg_proven_roots_v16.py"): "2dd31b0ffc359f93754625bd46250aa1aa8578adead0de3c9d640471afaffbf4",
    Path("tools/verify_rom_cfg_proven_roots_v16.py"): "6dc8535453445edc07c975e003cb8cf2bf58b1f7e8ccfbae1e782aed7a7bc24a",
    Path("tests/test_export_rom_cfg_proven_roots_v16.py"): "60d6de65eafcb837fe2d52af7a9a2d931f8b5d9a6c4df7e4af9018538c5ddba6",
    Path("tests/test_verify_rom_cfg_proven_roots_v16.py"): "ea390f632e80f94dc584d0bdba8075ac7e9fcb533f4d0dc049da76bb13fe8213",
    COVERAGE_PATH: "064370aa0eca861d99d96e4ee15be4b50c569bea86c67a279d4084517e543baa",
}
IMPLEMENTATION_PATHS = {
    "exporter": Path("tools/export_rom_cfg_proven_roots_v16_consumed_literals.py"),
    "verifier": Path("tools/verify_rom_cfg_proven_roots_v16_consumed_literals.py"),
    "test_exporter": Path("tests/test_export_rom_cfg_proven_roots_v16_consumed_literals.py"),
    "test_verifier": Path("tests/test_verify_rom_cfg_proven_roots_v16_consumed_literals.py"),
}
BASELINE = {"classified_bytes": 6_144_296, "unknown_bytes": 147_160, "claim_count": 15_945, "segment_count": 17_349}
EXPECTED = {"range_count": 21, "instruction_count": 369, "instruction_bytes": 778, "bindings": 51, "unique_target_words": 51, "promotion_bytes": 204}
NON_CLAIMS = [
    "No CFG traversal, root, edge, or frontier is expanded beyond frozen v16 membership.",
    "Only the 51 exact aligned words consumed by v16 Thumb LDR-literal instructions are promoted.",
    "Loaded values receive no pointer, table, resource, business, editing, relocation, padding, or free-space meaning.",
    "This packet is not connected to canonical coverage or proof artifacts.",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _thumb_instruction_width(data: bytes, offset: int, end: int) -> int:
    if offset < 0 or offset + 2 > end or end > len(data):
        raise ValueError("Thumb instruction boundary escaped frozen range")
    first = struct.unpack_from("<H", data, offset)[0]
    if first & 0xF800 == 0xF000:
        if offset + 4 > end:
            raise ValueError("truncated Thumb BL instruction")
        if struct.unpack_from("<H", data, offset + 2)[0] & 0xF800 == 0xF800:
            return 4
    return 2


def _bound(root: Path, relative: Path) -> bytes:
    data = (root / relative).read_bytes()
    if _sha(data) != SOURCE_IDENTITIES[relative]:
        raise ValueError(f"bound input identity changed: {relative}")
    return data


def _implementation(root: Path) -> dict[str, Any]:
    rows: dict[str, Any] = {"paths": {}}
    for name, path in IMPLEMENTATION_PATHS.items():
        rows["paths"][name] = path.as_posix()
        rows[f"{name}_sha256"] = _sha((root / path).read_bytes())
    return rows


def _inputs(root: Path, rom_override: bytes | None):
    rom = (root / ROM_PATH).read_bytes() if rom_override is None else rom_override
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    source_manifest = json.loads(_bound(root, SOURCE_MANIFEST))
    source = json.loads(_bound(root, SOURCE_PAYLOAD))
    for path in SOURCE_IDENTITIES:
        if path not in {SOURCE_MANIFEST, SOURCE_PAYLOAD, COVERAGE_PATH}:
            _bound(root, path)
    coverage = json.loads(_bound(root, COVERAGE_PATH))
    if source_manifest.get("artifact_schema") != "rom-cfg-proven-roots-v16" or source.get("schema") != "rom-cfg-proven-roots-v16":
        raise ValueError("source artifact schema changed")
    if any(coverage.get("summary", {}).get(key) != value for key, value in BASELINE.items()):
        raise ValueError("coverage baseline changed")
    segments = coverage.get("segments")
    if not isinstance(segments, list) or len(segments) != BASELINE["segment_count"]:
        raise ValueError("coverage segment denominator changed")
    starts: list[int] = []
    cursor = 0
    for index, segment in enumerate(segments):
        interval = segment.get("range")
        if not isinstance(interval, list) or len(interval) != 2 or interval[0] != cursor or not isinstance(interval[1], int) or interval[1] <= cursor:
            raise ValueError(f"coverage segment {index} changed")
        starts.append(cursor)
        cursor = interval[1]
    if cursor != ROM_SIZE:
        raise ValueError("coverage segment denominator changed")
    return rom, source, segments, starts


def build_payload(root: Path, rom_override: bytes | None = None) -> dict[str, Any]:
    root = root.resolve()
    rom, source, segments, starts = _inputs(root, rom_override)
    ranges = source.get("traversal", {}).get("ranges")
    if not isinstance(ranges, list) or len(ranges) != EXPECTED["range_count"]:
        raise ValueError("v16 traversal range denominator changed")

    def segment_at(offset: int) -> dict[str, Any]:
        return segments[bisect.bisect_right(starts, offset) - 1]

    bindings: list[dict[str, Any]] = []
    instruction_count = instruction_bytes = 0
    previous_end = -1
    range_records = []
    for range_index, interval in enumerate(ranges):
        if not isinstance(interval, list) or len(interval) != 2:
            raise ValueError("v16 traversal range changed")
        start, end = interval
        if not isinstance(start, int) or not isinstance(end, int) or start < previous_end or not 0 <= start < end <= len(rom):
            raise ValueError("v16 traversal range order changed")
        previous_end = end
        range_sha = _sha(rom[start:end])
        range_records.append({"range": interval, "bytes_sha256": range_sha})
        offset = start
        while offset < end:
            width = _thumb_instruction_width(rom, offset, end)
            halfword = struct.unpack_from("<H", rom, offset)[0]
            instruction_count += 1
            instruction_bytes += width
            if width == 2 and halfword & 0xF800 == 0x4800:
                target = ((offset + 4) & ~3) + (halfword & 255) * 4
                if target % 4 or target < 0 or target + 4 > len(rom):
                    raise ValueError("LDR-literal target escaped aligned ROM word")
                target_owner = segment_at(target)
                if target_owner.get("primary_class") != "unknown" or target_owner["range"][0] > target or target + 4 > target_owner["range"][1]:
                    raise ValueError("literal target is not a complete baseline-unknown word")
                if any(target < code_end and code_start < target + 4 for code_start, code_end in ranges):
                    raise ValueError("literal target overlaps v16 code range")
                word = rom[target : target + 4]
                bindings.append({
                    "source_file_offset": offset,
                    "source_raw_hex": rom[offset : offset + 2].hex(),
                    "target_file_offset": target,
                    "word_raw_hex": word.hex(),
                    "word_sha256": _sha(word),
                    "owner": {"artifact": "rom-cfg-proven-roots-v16", "range_index": range_index, "range": interval, "bytes_sha256": range_sha},
                })
            offset += width
        if offset != end:
            raise ValueError("Thumb decode escaped frozen range")
    if (instruction_count, instruction_bytes) != (EXPECTED["instruction_count"], EXPECTED["instruction_bytes"]):
        raise ValueError("v16 decoded instruction denominator changed")
    targets = [row["target_file_offset"] for row in bindings]
    if len(bindings) != EXPECTED["bindings"] or len(set(targets)) != EXPECTED["unique_target_words"] or targets != sorted(targets):
        raise ValueError("v16 literal binding denominator changed")
    target_words = []
    claims = []
    for index, row in enumerate(bindings, 1):
        target = row["target_file_offset"]
        owner = segment_at(target)
        target_words.append({
            "target_file_offset": target,
            "word_raw_hex": row["word_raw_hex"],
            "word_sha256": row["word_sha256"],
            "source_file_offset": row["source_file_offset"],
            "baseline_owner": {"primary_class": owner["primary_class"], "range": owner["range"], "primary_claim_ids": owner.get("primary_claim_ids", [])},
        })
        claims.append({"id": f"cfg-v16-consumed-literal-{index:02d}-{target:06x}", "range": [target, target + 4], "bytes_sha256": row["word_sha256"]})
    union_ranges: list[list[int]] = []
    for target in targets:
        if union_ranges and target == union_ranges[-1][1]:
            union_ranges[-1][1] += 4
        else:
            union_ranges.append([target, target + 4])
    union_bytes = sum(end - start for start, end in union_ranges)
    if union_bytes != EXPECTED["promotion_bytes"]:
        raise ValueError("v16 literal promotion denominator changed")
    denominator = {
        **EXPECTED,
        "range_vector_sha256": _sha(_canonical(range_records)),
        "binding_vector_sha256": _sha(_canonical(bindings)),
        "target_vector_sha256": _sha(_canonical(target_words)),
        "claim_vector_sha256": _sha(_canonical(claims)),
        "packed_word_bytes_sha256": _sha(b"".join(rom[target : target + 4] for target in targets)),
    }
    source_artifact = {
        "path": SOURCE_DIR.as_posix(),
        "manifest_sha256": SOURCE_IDENTITIES[SOURCE_MANIFEST],
        "payload_sha256": SOURCE_IDENTITIES[SOURCE_PAYLOAD],
        "implementation": source.get("implementation"),
    }
    return {
        "schema": "rom-cfg-proven-roots-v16-consumed-literals-v1",
        "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},
        "source_artifact": source_artifact,
        "implementation": _implementation(root),
        "coverage_baseline": {"path": COVERAGE_PATH.as_posix(), "sha256": SOURCE_IDENTITIES[COVERAGE_PATH], **BASELINE},
        "source_denominator": {"ranges": ranges, "range_records": range_records, "range_count": len(ranges), "instruction_count": instruction_count, "instruction_bytes": instruction_bytes},
        "literal_denominator": denominator,
        "bindings": bindings,
        "target_words": target_words,
        "promotion": {"promotion_batch": PROMOTION_BATCH, "primary_class": PRIMARY_CLASS, "claim_kind": CLAIM_KIND, "claims": claims, "union_ranges": union_ranges, "union_bytes": union_bytes},
        "coverage_projection": {"baseline_unknown_bytes": BASELINE["unknown_bytes"], "promoted_bytes": union_bytes, "remaining_unknown_bytes": BASELINE["unknown_bytes"] - union_bytes, "conservation_ok": BASELINE["unknown_bytes"] == union_bytes + (BASELINE["unknown_bytes"] - union_bytes)},
        "scope": {"raw_rom_redecoded": True, "frozen_v16_ranges_reused": True, "all_targets_baseline_unknown": True, "targets_disjoint_from_v16_code": True, "canonical_coverage_connected": False, "canonical_proof_connected": False},
        "non_claims": NON_CLAIMS,
    }


def _replace(output: Path, files: dict[str, bytes]) -> None:
    if output.exists() and (not output.is_dir() or output.is_symlink() or any(output.iterdir())):
        raise ValueError("output artifact directory must be absent or empty")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as raw:
        staging = Path(raw) / output.name
        staging.mkdir()
        for name, data in files.items():
            (staging / name).write_bytes(data)
        if output.exists():
            output.rmdir()
        shutil.move(staging, output)


def export(root: Path, output: Path) -> dict[str, Any]:
    payload = build_payload(root)
    payload_bytes = json.dumps(payload, indent=2, sort_keys=True).encode() + b"\n"
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": "rom-cfg-proven-roots-v16-consumed-literals-artifact-v1",
        "artifact_status": "accepted",
        "payload_schema": payload["schema"],
        "rom": payload["rom"],
        "source_artifact": payload["source_artifact"],
        "implementation": payload["implementation"],
        "coverage_baseline": payload["coverage_baseline"],
        "literal_denominator": payload["literal_denominator"],
        "promotion": payload["promotion"],
        "coverage_projection": payload["coverage_projection"],
        "scope": payload["scope"],
        "non_claims": payload["non_claims"],
        "verifier": {"command": ["python3", "-I", "-S", "tools/verify_rom_cfg_proven_roots_v16_consumed_literals.py", "--root", ".", "--artifact", "artifacts/rom-cfg-proven-roots-v16-consumed-literals-v1"], "exit_code": 0},
        "files": {PAYLOAD_NAME: {"sha256": _sha(payload_bytes), "size": len(payload_bytes)}},
    }
    _replace(output, {PAYLOAD_NAME: payload_bytes, "manifest.json": json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n"})
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_payload(args.root.resolve())
    export(args.root.resolve(), args.output)
    print(json.dumps({"bindings": len(payload["bindings"]), "unique_target_words": len(payload["target_words"]), "promotion_bytes": payload["promotion"]["union_bytes"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
