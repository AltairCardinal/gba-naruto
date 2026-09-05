#!/usr/bin/env python3
"""Independently verify proven-roots-v6 consumed literal words."""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SOURCE_DIR = Path("artifacts/rom-cfg-proven-roots-v6")
SOURCE_MANIFEST = SOURCE_DIR / "manifest.json"
SOURCE_PAYLOAD = SOURCE_DIR / "rom-cfg-proven-roots-v6.json"
SOURCE_EXPORTER = Path("tools/export_rom_cfg_proven_roots_v6.py")
SOURCE_VERIFIER = Path("tools/verify_rom_cfg_proven_roots_v6.py")
SOURCE_TEST = Path("tests/test_export_rom_cfg_proven_roots_v6.py")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
PAYLOAD_NAME = "rom-cfg-v6-consumed-literals.json"
CONTRACT_SHA256 = "6ff685e5c20b313e2c447c0ec898b4f152fc46969a5d5f2372238500a19f6586"
SOURCE_CLASS = "armv4t_cfg_proven_roots_v6_reachable_thumb_code"
PRIMARY_CLASS = "armv4t_cfg_v6_consumed_literal_word"
CLAIM_KIND = "armv4t_cfg_v6_consumed_literal_word_bytes"
PROMOTION_BATCH = "rom-cfg-v6-consumed-literals-v1"

IDENTITIES = {
    SOURCE_MANIFEST: "e00d8a1b7b08305a44f7ac3d36a5e294d1f69b5f05ceab151e14749cf92802f4",
    SOURCE_PAYLOAD: "e5b27a55c77cd1df4ac5ec39f2dd05735b0b53c01b7cbbcf1620db1681a3c3ec",
    SOURCE_EXPORTER: "e8f629c8cccc726a25770eb20396eb1885f899f4125ac786defd0fd2b9aa273f",
    SOURCE_VERIFIER: "4fc2ad61b98ce3655f1528e773566f63f84f1184209086bd96d3e23c51a8ceb4",
    SOURCE_TEST: "ef6ced68a6aeff2df19520fc8d12eba1b98bd609dc4fdf26528fd839eca152c9",
    COVERAGE_PATH: "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
}
EXPECTED = {
    "root_count": 5,
    "frontier_count": 85,
    "thumb_block_count": 2_305,
    "thumb_instruction_count": 12_564,
    "thumb_instruction_bytes": 27_224,
    "source_instruction_count": 800,
    "unique_target_word_count": 745,
    "target_bytes": 2_980,
    "merged_target_range_count": 185,
    "thumb_block_denominator_sha256": "58e61406cf88315855d0d6b3e9ddbf0363d6b56991bc9ad2f5bfa4bf62519ca9",
    "source_vector_sha256": "5974706f5687be74f23005632887ac9531af11544bb6f99e29f8d930d02d3d49",
    "source_offset_vector_sha256": "e587b9cc622f48afcc79e1abb16945afd89333bfb93daa31bf49f1bb55ed1a91",
    "target_vector_sha256": "624b0a9f14cab3953d8370c4986204a69b100482bdec80984b373ce0f2657832",
    "target_offset_vector_sha256": "240cfce281501abf4e14388c4b579da73474e06f1a350499553a41e64d0169f9",
    "range_vector_sha256": "95ada8efd9a3315fd0a43850327c5460930395c9d6d901c28373f8b579730dce",
    "packed_target_bytes_sha256": "1a27c7b05a6fd1093ed2741193111021cb12d40e33a24be5c9ce8f2a29372700",
}
BASELINE_SUMMARY = {"classified_bytes": 6_127_684, "unknown_bytes": 163_772, "claim_count": 14_720, "segment_count": 16_693}
PROJECTED_SUMMARY = {"classified_bytes": 6_130_664, "unknown_bytes": 160_792, "claim_count": 14_905, "segment_count": 16_790, "delta": {"classified_bytes": 2_980, "unknown_bytes": -2_980, "claim_count": 185, "segment_count": 97}}
NON_CLAIMS = [
    "No v2, v1, other proven-roots, consumer_code_slice, ARM literal-load, or non-PC-relative load source is included.",
    "No traversal is expanded beyond the already accepted v6 extension block membership and none of the 85 frontiers is resolved.",
    "No adjacent unknown byte or whole unknown segment is promoted unless it is one of the 745 exact target words.",
    "The loaded word value has no pointer, constant, table, resource, or business meaning beyond consumed literal data.",
    "Natural runtime reachability, global denominators, editing, writeback, relocation, padding, and free space remain unproven.",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _thumb_instruction_width(data: bytes, offset: int, end: int) -> int:
    if offset < 0 or offset + 2 > end or end > len(data):
        raise ValueError("Thumb instruction boundary escaped block")
    first = struct.unpack_from("<H", data, offset)[0]
    if first & 0xF800 == 0xF000:
        if offset + 4 > end:
            raise ValueError("truncated Thumb BL instruction")
        second = struct.unpack_from("<H", data, offset + 2)[0]
        if second & 0xF800 == 0xF800:
            return 4
    return 2


def _decode_ldr_literal_target(source_file_offset: int, raw_halfword: int) -> int:
    if raw_halfword & 0xF800 != 0x4800:
        raise ValueError("halfword is not Thumb LDR-literal")
    return ((source_file_offset + 4) & ~3) + (raw_halfword & 0xFF) * 4


def _bound_bytes(root: Path, relative: Path) -> bytes:
    data = (root / relative).read_bytes()
    if _sha(data) != IDENTITIES[relative]:
        raise ValueError(f"bound input identity changed: {relative}")
    return data


def _read_inputs(root: Path):
    rom = (root / ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    manifest = json.loads(_bound_bytes(root, SOURCE_MANIFEST))
    source = json.loads(_bound_bytes(root, SOURCE_PAYLOAD))
    _bound_bytes(root, SOURCE_EXPORTER)
    _bound_bytes(root, SOURCE_VERIFIER)
    _bound_bytes(root, SOURCE_TEST)
    coverage_bytes = (root / COVERAGE_PATH).read_bytes()
    coverage = json.loads(coverage_bytes)
    if manifest.get("artifact_schema") != "rom-cfg-proven-roots-v6" or source.get("schema") != "rom-cfg-proven-roots-v6":
        raise ValueError("source artifact schema changed")
    extension = source.get("extension", {})
    if len(source.get("roots", [])) != EXPECTED["root_count"] or len(extension.get("frontiers", [])) != EXPECTED["frontier_count"]:
        raise ValueError("source artifact denominator changed")
    baseline_mode = _sha(coverage_bytes) == IDENTITIES[COVERAGE_PATH]
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage schema changed")
    if baseline_mode and any(coverage.get("summary", {}).get(key) != value for key, value in BASELINE_SUMMARY.items()):
        raise ValueError("coverage baseline summary changed")
    segments = coverage.get("segments")
    if not isinstance(segments, list) or (baseline_mode and len(segments) != BASELINE_SUMMARY["segment_count"]):
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

    def segment_at(offset: int) -> dict[str, Any]:
        index = bisect.bisect_right(starts, offset) - 1
        if index < 0:
            raise ValueError("coverage lookup escaped ROM")
        return segments[index]

    return rom, source, segment_at, baseline_mode


def _rebuild_payload(root: Path) -> dict[str, Any]:
    rom, source, segment_at, baseline_mode = _read_inputs(root)
    blocks = [block for block in source["extension"]["blocks"] if block.get("mode") == "thumb"]
    if len(blocks) != EXPECTED["thumb_block_count"]:
        raise ValueError("Thumb block denominator changed")
    block_rows = [{"id": b.get("id"), "range": b.get("range"), "instruction_count": b.get("instruction_count"), "bytes_sha256": b.get("bytes_sha256")} for b in blocks]
    if _sha(_canonical(block_rows)) != EXPECTED["thumb_block_denominator_sha256"]:
        raise ValueError("Thumb block denominator changed")
    sources: list[dict[str, Any]] = []
    target_sources: dict[int, list[int]] = {}
    instruction_count = instruction_bytes = 0
    previous_end = -1
    for block in blocks:
        start, end = block.get("range", [None, None])
        if not isinstance(start, int) or not isinstance(end, int) or start < previous_end or not 0 <= start < end <= len(rom):
            raise ValueError("Thumb block order or range changed")
        previous_end = end
        if _sha(rom[start:end]) != block.get("bytes_sha256"):
            raise ValueError("Thumb block bytes changed")
        offset = start
        block_count = 0
        while offset < end:
            width = _thumb_instruction_width(rom, offset, end)
            halfword = struct.unpack_from("<H", rom, offset)[0]
            owner = segment_at(offset)
            if width == 2 and halfword & 0xF800 == 0x4800 and owner.get("primary_class") == SOURCE_CLASS and owner["range"][0] <= offset and offset + 2 <= owner["range"][1]:
                target = _decode_ldr_literal_target(offset, halfword)
                if target + 4 <= len(rom):
                    target_owner = segment_at(target)
                    if target_owner.get("primary_class") == ("unknown" if baseline_mode else PRIMARY_CLASS) and target_owner["range"][0] <= target and target + 4 <= target_owner["range"][1]:
                        sources.append({"source_file_offset": offset, "source_raw_hex": rom[offset:offset + 2].hex(), "target_file_offset": target, "target_raw_hex": rom[target:target + 4].hex()})
                        target_sources.setdefault(target, []).append(offset)
            offset += width
            block_count += 1
            instruction_count += 1
            instruction_bytes += width
        if offset != end or block_count != block.get("instruction_count"):
            raise ValueError("Thumb block instruction denominator changed")
    targets = [{"target_file_offset": target, "target_raw_hex": rom[target:target + 4].hex(), "source_file_offsets": source_offsets} for target, source_offsets in sorted(target_sources.items())]
    ranges: list[list[int]] = []
    for target in sorted(target_sources):
        if ranges and target == ranges[-1][1]:
            ranges[-1][1] += 4
        else:
            ranges.append([target, target + 4])
    range_records = [{"range": interval, "bytes_sha256": _sha(rom[interval[0]:interval[1]])} for interval in ranges]
    packed = b"".join(rom[target:target + 4] for target in sorted(target_sources))
    denominator = {
        "source_instruction_count": len(sources),
        "unique_target_word_count": len(targets),
        "target_bytes": len(packed),
        "merged_target_range_count": len(ranges),
        "source_vector_sha256": _sha(_canonical(sources)),
        "source_offset_vector_sha256": _sha(_canonical([row["source_file_offset"] for row in sources])),
        "target_vector_sha256": _sha(_canonical(targets)),
        "target_offset_vector_sha256": _sha(_canonical(sorted(target_sources))),
        "range_vector_sha256": _sha(_canonical(range_records)),
        "packed_target_bytes_sha256": _sha(packed),
    }
    for key, value in denominator.items():
        if EXPECTED.get(key) != value:
            raise ValueError(f"literal denominator changed: {key}")
    if instruction_count != EXPECTED["thumb_instruction_count"] or instruction_bytes != EXPECTED["thumb_instruction_bytes"]:
        raise ValueError("decoded Thumb denominator changed")
    summary = {key: denominator[key] for key in ("source_instruction_count", "unique_target_word_count", "target_bytes", "merged_target_range_count")}
    coverage_baseline = {"path": COVERAGE_PATH.as_posix(), "sha256": IDENTITIES[COVERAGE_PATH], "source_primary_class": SOURCE_CLASS, "summary": BASELINE_SUMMARY}
    source_artifact = {"path": SOURCE_DIR.as_posix(), "manifest_sha256": IDENTITIES[SOURCE_MANIFEST], "payload_sha256": IDENTITIES[SOURCE_PAYLOAD], "source_exporter_sha256": IDENTITIES[SOURCE_EXPORTER], "source_verifier_sha256": IDENTITIES[SOURCE_VERIFIER], "source_test_sha256": IDENTITIES[SOURCE_TEST]}
    scope = {"frozen_v6_extension_membership_reused": True, "source_owner_restricted_to_v6_cfg": True, "target_words_complete_current_unknown": True, "cfg_traversal_expanded": False, "frontiers_resolved": False, "loaded_value_semantics_proven": False}
    return {
        "schema": "rom-cfg-v6-consumed-literals-v1",
        "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},
        "public_contract_sha256": CONTRACT_SHA256,
        "source_artifact": source_artifact,
        "coverage_baseline": coverage_baseline,
        "source_denominator": {"summary": {"block_count": len(blocks), "instruction_count": instruction_count, "instruction_bytes": instruction_bytes}, "thumb_block_denominator_sha256": EXPECTED["thumb_block_denominator_sha256"]},
        "literal_denominator": denominator,
        "source_to_target": sources,
        "target_words": targets,
        "promotion": {"promotion_batch": PROMOTION_BATCH, "primary_class": PRIMARY_CLASS, "claim_kind": CLAIM_KIND, "ranges": ranges, "range_records": range_records},
        "coverage_projection": PROJECTED_SUMMARY,
        "summary": summary,
        "scope": scope,
        "non_claims": NON_CLAIMS,
    }


def _read_artifact(artifact: Path) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    if artifact.is_symlink() or not artifact.is_dir():
        raise ValueError("artifact directory is missing or a symlink")
    members = list(artifact.iterdir())
    if {path.name for path in members} != {"manifest.json", PAYLOAD_NAME} or any(path.is_symlink() or not path.is_file() for path in members):
        raise ValueError("artifact file set changed")
    manifest = json.loads((artifact / "manifest.json").read_bytes())
    payload_bytes = (artifact / PAYLOAD_NAME).read_bytes()
    payload = json.loads(payload_bytes)
    record = manifest.get("files", {}).get(PAYLOAD_NAME, {})
    if record != {"sha256": _sha(payload_bytes), "size": len(payload_bytes)}:
        raise ValueError("payload identity does not match artifact file record")
    return manifest, payload, payload_bytes


def verify_root(root: Path, artifact: Path) -> dict[str, Any]:
    root = root.resolve()
    artifact = artifact.absolute()
    manifest, payload, payload_bytes = _read_artifact(artifact)
    expected_payload = _rebuild_payload(root)
    if payload != expected_payload:
        raise ValueError("payload does not match independently rebuilt contract")
    expected_manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": "rom-cfg-v6-consumed-literals-artifact-v1",
        "artifact_status": "accepted",
        "payload_schema": expected_payload["schema"],
        "public_contract_sha256": CONTRACT_SHA256,
        "rom": expected_payload["rom"],
        "source_artifact": expected_payload["source_artifact"],
        "coverage_baseline": expected_payload["coverage_baseline"],
        "literal_denominator": expected_payload["literal_denominator"],
        "promotion": expected_payload["promotion"],
        "coverage_projection": expected_payload["coverage_projection"],
        "summary": expected_payload["summary"],
        "scope": expected_payload["scope"],
        "non_claims": expected_payload["non_claims"],
        "verifier": {"command": ["python3", "-I", "-S", "tools/verify_rom_cfg_v6_consumed_literals.py", "--root", ".", "--artifact", "artifacts/rom-cfg-v6-consumed-literals-v1"], "exit_code": 0},
        "files": {PAYLOAD_NAME: {"sha256": _sha(payload_bytes), "size": len(payload_bytes)}},
    }
    if manifest != expected_manifest:
        raise ValueError("artifact manifest does not match independently rebuilt contract")
    return {
        "schema": "rom-cfg-v6-consumed-literals-verification-v1",
        "verified": True,
        "contract_ok": True,
        "artifact": {"path": artifact.as_posix(), "manifest_sha256": _sha((artifact / "manifest.json").read_bytes()), "payload_sha256": _sha(payload_bytes)},
        "source_denominator": {"thumb_block_count": EXPECTED["thumb_block_count"], "thumb_instruction_count": EXPECTED["thumb_instruction_count"], "thumb_instruction_bytes": EXPECTED["thumb_instruction_bytes"], "thumb_block_denominator_sha256": EXPECTED["thumb_block_denominator_sha256"]},
        "literal_denominator": expected_payload["literal_denominator"],
        "summary": expected_payload["summary"],
        "coverage_projection": PROJECTED_SUMMARY,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_root(args.root, args.artifact), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
