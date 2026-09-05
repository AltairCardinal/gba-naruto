#!/usr/bin/env python3
"""Independently verify the frozen battle-controller literal packet."""

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
SOURCE_DIR = Path("artifacts/rom-battle-controller-cfg-v1")
SOURCE_MANIFEST = SOURCE_DIR / "manifest.json"
SOURCE_PAYLOAD = SOURCE_DIR / "rom-battle-controller-cfg.json"
SOURCE_EXPORTER = Path("tools/export_rom_battle_controller_cfg.py")
SOURCE_VERIFIER = Path("tools/verify_rom_battle_controller_cfg.py")
SOURCE_TEST = Path("tests/test_export_rom_battle_controller_cfg.py")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
POST_COVERAGE_SUMMARY = {"classified_bytes": 6_142_176, "unknown_bytes": 149_280, "claim_count": 15_940, "segment_count": 17_344}
PAYLOAD_NAME = "rom-battle-controller-consumed-literals.json"
CONTRACT_SHA256 = "be5729a6cc965762b3cb9e3722162612dd11c821b6a5e5609d25c753f0763613"
SOURCE_CLASS = "armv4t_cfg_battle_controller_reachable_thumb_code"
PRIMARY_CLASS = "armv4t_cfg_battle_controller_consumed_literal_word"
CLAIM_KIND = "armv4t_cfg_battle_controller_consumed_literal_word_bytes"
PROMOTION_BATCH = "rom-battle-controller-consumed-literals-v1"

IDENTITIES = {
    SOURCE_MANIFEST: "282b4323bf965676a68b5326f2edbbdee35606b987412d351de137b82d50fe63",
    SOURCE_PAYLOAD: "c8b1d1c2068d85912ede1fd35be31f0cf9cb43943beb10f1058d43c65c00449a",
    SOURCE_EXPORTER: "f3ca36b2a9b08cab6b10f05e7ac780c0b537fb954f22263c1e61e7a70b237841",
    SOURCE_VERIFIER: "fc3c33d37b9fb2af885324915f82e3c0da74b3efd25967b8289b49d8b9169a87",
    SOURCE_TEST: "412ae14c68d0ccd0a402f199fcaf9fbf1333ab75369fbd6212c4494b2aadf1a7",
    COVERAGE_PATH: "66a5e95bd2927f9db13435f6862a052ad60634cfbd3a8b5dfad07459a4a12329",
}

SOURCE_ARTIFACT = {
    "directory": SOURCE_DIR.as_posix(),
    "schema": "rom-battle-controller-cfg-v1",
    "manifest_sha256": IDENTITIES[SOURCE_MANIFEST],
    "payload": SOURCE_PAYLOAD.name,
    "payload_sha256": IDENTITIES[SOURCE_PAYLOAD],
    "source_exporter": SOURCE_EXPORTER.as_posix(),
    "source_exporter_sha256": IDENTITIES[SOURCE_EXPORTER],
    "source_verifier": SOURCE_VERIFIER.as_posix(),
    "source_verifier_sha256": IDENTITIES[SOURCE_VERIFIER],
    "source_test": SOURCE_TEST.as_posix(),
    "source_test_sha256": IDENTITIES[SOURCE_TEST],
    "root_count": 38,
    "thumb_block_count": 739,
    "thumb_instruction_count": 2756,
    "thumb_instruction_bytes": 6172,
    "frontier_count": 5,
    "thumb_block_denominator_sha256": "1da7f9256ca6def602ceb8b5f296e7bf3a3f8a4e4763f0271c3908daad977c6d",
}

OVERLAP_BASELINE = {
    "v3_packet": {
        "manifest_path": "artifacts/rom-cfg-v3-consumed-literals-v1/manifest.json",
        "manifest_sha256": "2ab82e1747256f0b0f8c7cd22b96d1cd802aeffb40cebea56b6a417de8f72940",
        "payload_path": "artifacts/rom-cfg-v3-consumed-literals-v1/rom-cfg-v3-consumed-literals.json",
        "payload_sha256": "1407aa1204218c4861e620192226a5b4cd718172e5983f03f2f953263f186b4d",
        "payload_schema": "rom-cfg-v3-consumed-literals-v1",
        "target_word_count": 305,
        "target_offset_vector_sha256": "8e2e15cf823c1a2bbc8c4d3128d536b6c9b447706686e638e4e61d37f8e30d43",
        "target_vector_sha256": "54dbac6a3f0b57c8d2d783e7781b3736b6d15f217e223a7df861af625815ce62",
    },
    "proven_roots_batch": {
        "manifest_path": "artifacts/rom-cfg-proven-roots-batch-consumed-literals-v1/manifest.json",
        "manifest_sha256": "8688e87bdec227322a7b27f2d2feb84428f3ff82e4c782348db2c33b125e2d5f",
        "payload_path": "artifacts/rom-cfg-proven-roots-batch-consumed-literals-v1/rom-cfg-proven-roots-batch-consumed-literals.json",
        "payload_sha256": "35efe834638717ce963af95343bcccfc70311b0a124718c2e732263880fbc4d0",
        "payload_schema": "rom-cfg-proven-roots-batch-consumed-literals-v1",
        "target_word_count": 314,
        "target_offset_vector_sha256": "7e87f1da67026609cb5dd06ff7e45039578da62f738ec945ee3b56db64ccb26e",
        "target_vector_sha256": "33f69b5ca6d465b8c3a92d8937108df59388ab85a5aac3059b7fa8dc0ff7357f",
    },
    "expected_target_overlap_word_count": 0,
}

BASELINE_SUMMARY = {
    "classified_bytes": 6_138_856,
    "unknown_bytes": 152_600,
    "claim_count": 15_666,
    "segment_count": 17_182,
}
PROJECTED_SUMMARY = {
    "classified_bytes": 6_139_392,
    "unknown_bytes": 152_064,
    "claim_count": 15_712,
    "segment_count": 17_213,
    "delta": {
        "classified_bytes": 536,
        "unknown_bytes": -536,
        "claim_count": 46,
        "segment_count": 31,
    },
}
EXPECTED_SOURCE_SUMMARY = {"block_count": 739, "instruction_count": 2756, "instruction_bytes": 6172}
EXPECTED_SELECTION_FUNNEL = {
    "raw_source_instruction_count": 226,
    "raw_unique_target_word_count": 209,
    "source_owner_eligible_instruction_count": 226,
    "excluded_non_battle_controller_owner_source_count": 0,
    "excluded_non_unknown_target_source_count": 85,
}
EXPECTED_LITERAL = {
    "encoding": "Thumb-1 LDR Rd,[PC,#imm8*4] where raw_halfword & 0xF800 == 0x4800",
    "target_formula": "align4(source_file_offset + 4) + imm8 * 4",
    "source_instruction_count": 141,
    "unique_target_word_count": 134,
    "target_bytes": 536,
    "merged_target_range_count": 46,
    "source_vector_sha256": "840af5ad270eba1add2f4178f8ee3b86fee380318565e2b87e9adfc00b89bd48",
    "source_offset_vector_sha256": "d1f3a4d4c32ed039bca8fb932bba07805ab802c738fe45733341704c8a271e0a",
    "target_vector_sha256": "5cac97ba0a1a0f85cea03055b101f30b65515f39f67739f81ae899680dca7c9a",
    "target_offset_vector_sha256": "64f2eb5b754055daa98cfb22fd6154ac1b5866a32e34a960ffa3e9b429d96414",
    "range_vector_sha256": "09e6880ee491e9765f37c0fea0c6af16f32482ce1c9b8ef0bd842d8e889699a2",
    "packed_target_bytes_sha256": "8a0e477e1e6ced4e66f34f13ce0a4571fe4a2515a4a0673830c961e9bc503621",
}
NON_CLAIMS = [
    "No CFG traversal is expanded and none of the five source frontiers is resolved.",
    "No adjacent unknown byte or whole unknown segment is promoted; only the 134 exact consumed words are promoted.",
    "Loaded values receive no pointer, constant, table, resource, business, editing, relocation, padding, or free-space meaning.",
    "No natural runtime reachability or global code/BL/literal denominator is claimed beyond the frozen 739-block source artifact.",
    "Zero overlap is asserted only against the two bound prior packets and does not prove other unbound consumers absent.",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _bound_bytes(root: Path, relative: Path, expected_sha256: str) -> bytes:
    data = (root / relative).read_bytes()
    if _sha(data) != expected_sha256:
        raise ValueError(f"bound input identity changed: {relative}")
    return data


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


def _segment_lookup(segments: list[dict[str, Any]]):
    starts: list[int] = []
    cursor = 0
    for index, segment in enumerate(segments):
        interval = segment.get("range")
        if (
            not isinstance(interval, list)
            or len(interval) != 2
            or interval[0] != cursor
            or not isinstance(interval[1], int)
            or interval[1] <= cursor
        ):
            raise ValueError(f"coverage segment {index} changed")
        starts.append(cursor)
        cursor = interval[1]
    if cursor != ROM_SIZE:
        raise ValueError("coverage segment denominator changed")

    def segment_at(offset: int) -> dict[str, Any]:
        if not isinstance(offset, int) or offset < 0 or offset >= ROM_SIZE:
            raise ValueError("coverage lookup escaped ROM")
        index = bisect.bisect_right(starts, offset) - 1
        if index < 0:
            raise ValueError("coverage lookup escaped ROM")
        return segments[index]

    return segment_at


def _read_overlap_targets(root: Path) -> dict[str, set[int]]:
    result: dict[str, set[int]] = {}
    for name, bound in OVERLAP_BASELINE.items():
        if name == "expected_target_overlap_word_count":
            continue
        manifest_path = Path(bound["manifest_path"])
        payload_path = Path(bound["payload_path"])
        manifest = json.loads(_bound_bytes(root, manifest_path, bound["manifest_sha256"]))
        payload = json.loads(_bound_bytes(root, payload_path, bound["payload_sha256"]))
        if manifest.get("files", {}).get(payload_path.name, {}).get("sha256") != bound["payload_sha256"]:
            raise ValueError(f"overlap packet payload identity changed: {name}")
        if payload.get("schema") != bound["payload_schema"]:
            raise ValueError(f"overlap packet schema changed: {name}")
        target_words = payload.get("target_words")
        if not isinstance(target_words, list) or len(target_words) != bound["target_word_count"]:
            raise ValueError(f"overlap packet target denominator changed: {name}")
        offsets = [row.get("target_file_offset") for row in target_words]
        if offsets != sorted(offsets) or len(offsets) != len(set(offsets)):
            raise ValueError(f"overlap packet target order changed: {name}")
        if _sha(_canonical(offsets)) != bound["target_offset_vector_sha256"] or _sha(_canonical(target_words)) != bound["target_vector_sha256"]:
            raise ValueError(f"overlap packet target vector changed: {name}")
        result[name] = set(offsets)
    return result


def _read_inputs(root: Path):
    rom = (root / ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    manifest = json.loads(_bound_bytes(root, SOURCE_MANIFEST, IDENTITIES[SOURCE_MANIFEST]))
    source = json.loads(_bound_bytes(root, SOURCE_PAYLOAD, IDENTITIES[SOURCE_PAYLOAD]))
    _bound_bytes(root, SOURCE_EXPORTER, IDENTITIES[SOURCE_EXPORTER])
    _bound_bytes(root, SOURCE_VERIFIER, IDENTITIES[SOURCE_VERIFIER])
    _bound_bytes(root, SOURCE_TEST, IDENTITIES[SOURCE_TEST])
    coverage_bytes = (root / COVERAGE_PATH).read_bytes()
    coverage_sha256 = _sha(coverage_bytes)
    baseline_mode = coverage_sha256 == IDENTITIES[COVERAGE_PATH]
    coverage = json.loads(coverage_bytes)
    if manifest.get("artifact_schema") != SOURCE_ARTIFACT["schema"] or source.get("schema") != SOURCE_ARTIFACT["schema"]:
        raise ValueError("source artifact schema changed")
    if manifest.get("rom") != {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256}:
        raise ValueError("source artifact ROM binding changed")
    extension_summary = manifest.get("extension_summary", {})
    if extension_summary.get("decoded_basic_block_count") != 739 or extension_summary.get("decoded_instruction_count") != 2756 or extension_summary.get("reachable_instruction_bytes") != 6172 or extension_summary.get("frontier_count") != 5:
        raise ValueError("source artifact denominator changed")
    extension = source.get("extension", {})
    if extension.get("summary", {}).get("decoded_basic_block_count") != 739 or extension.get("summary", {}).get("decoded_instruction_count") != 2756 or extension.get("summary", {}).get("reachable_instruction_bytes") != 6172 or extension.get("summary", {}).get("frontier_count") != 5:
        raise ValueError("source artifact denominator changed")
    summary = coverage.get("summary")
    claims = coverage.get("claims")
    segments = coverage.get("segments")
    if coverage.get("schema") != "rom-byte-coverage-v1" or not isinstance(summary, dict) or not isinstance(claims, list) or not isinstance(segments, list):
        raise ValueError("coverage structure changed")
    if baseline_mode:
        if any(summary.get(key) != value for key, value in BASELINE_SUMMARY.items()) or len(claims) != BASELINE_SUMMARY["claim_count"] or len(segments) != BASELINE_SUMMARY["segment_count"]:
            raise ValueError("coverage baseline summary changed")
    elif summary.get("claim_count") != len(claims) or summary.get("segment_count") != len(segments):
        raise ValueError("coverage summary denominator changed")
    segment_at = _segment_lookup(segments)
    if not baseline_mode:
        classified = sum(segment["range"][1] - segment["range"][0] for segment in segments if segment.get("primary_class") != "unknown")
        unknown = ROM_SIZE - classified
        if summary.get("classified_bytes") != classified or summary.get("unknown_bytes") != unknown:
            raise ValueError("coverage summary changed")
    overlap_targets = _read_overlap_targets(root)
    return rom, source, coverage, segment_at, overlap_targets, baseline_mode


def _project_segment_count(segments: list[dict[str, Any]], ranges: list[list[int]]) -> int:
    projected_count = 0
    range_index = 0
    for segment in segments:
        start, end = segment["range"]
        cursor = start
        while range_index < len(ranges) and ranges[range_index][1] <= start:
            range_index += 1
        index = range_index
        while index < len(ranges) and ranges[index][0] < end:
            left, right = ranges[index]
            if left > cursor:
                projected_count += 1
            if left < start or right > end:
                raise ValueError("promotion range crosses coverage segment")
            projected_count += 1
            cursor = right
            index += 1
        if cursor < end:
            projected_count += 1
    return projected_count


def _rebuild_payload(root: Path) -> dict[str, Any]:
    root = root.resolve()
    rom, source, coverage, segment_at, overlap_targets, baseline_mode = _read_inputs(root)
    blocks = source.get("extension", {}).get("blocks")
    if not isinstance(blocks, list) or len(blocks) != EXPECTED_SOURCE_SUMMARY["block_count"] or any(block.get("mode") != "thumb" for block in blocks):
        raise ValueError("Thumb block denominator changed")
    block_rows = [
        {
            "id": block.get("id"),
            "range": block.get("range"),
            "instruction_count": block.get("instruction_count"),
            "bytes_sha256": block.get("bytes_sha256"),
        }
        for block in blocks
    ]
    block_denominator_sha256 = _sha(_canonical(block_rows))
    if block_denominator_sha256 != SOURCE_ARTIFACT["thumb_block_denominator_sha256"]:
        raise ValueError("Thumb block denominator changed")

    sources: list[dict[str, Any]] = []
    target_sources: dict[int, list[int]] = {}
    raw_source_count = 0
    raw_targets: set[int] = set()
    source_owner_eligible_count = 0
    instruction_count = 0
    instruction_bytes = 0
    previous_end = -1
    for block in blocks:
        start, end = block.get("range", [None, None])
        if not isinstance(start, int) or not isinstance(end, int) or start < previous_end or not 0 <= start < end <= len(rom):
            raise ValueError("Thumb block order or range changed")
        previous_end = end
        if _sha(rom[start:end]) != block.get("bytes_sha256"):
            raise ValueError("Thumb block bytes changed")
        offset = start
        block_instruction_count = 0
        while offset < end:
            size = _thumb_instruction_width(rom, offset, end)
            halfword = struct.unpack_from("<H", rom, offset)[0]
            owner = segment_at(offset)
            if size == 2 and halfword & 0xF800 == 0x4800:
                target = _decode_ldr_literal_target(offset, halfword)
                if target + 4 <= len(rom):
                    raw_source_count += 1
                    raw_targets.add(target)
                    if owner.get("primary_class") == SOURCE_CLASS and owner["range"][0] <= offset and offset + 2 <= owner["range"][1]:
                        source_owner_eligible_count += 1
                        target_owner = segment_at(target)
                        if target_owner.get("primary_class") == ("unknown" if baseline_mode else PRIMARY_CLASS) and target_owner["range"][0] <= target and target + 4 <= target_owner["range"][1]:
                            sources.append(
                                {
                                    "source_file_offset": offset,
                                    "source_raw_hex": rom[offset : offset + 2].hex(),
                                    "target_file_offset": target,
                                    "target_raw_hex": rom[target : target + 4].hex(),
                                }
                            )
                            target_sources.setdefault(target, []).append(offset)
            offset += size
            block_instruction_count += 1
            instruction_count += 1
            instruction_bytes += size
        if offset != end or block_instruction_count != block.get("instruction_count"):
            raise ValueError("Thumb block instruction denominator changed")

    sources.sort(key=lambda row: (row["source_file_offset"], row["target_file_offset"]))
    targets = [
        {
            "target_file_offset": target,
            "target_raw_hex": rom[target : target + 4].hex(),
            "source_file_offsets": source_offsets,
        }
        for target, source_offsets in sorted(target_sources.items())
    ]
    ranges: list[list[int]] = []
    for target in sorted(target_sources):
        if ranges and target == ranges[-1][1]:
            ranges[-1][1] += 4
        else:
            ranges.append([target, target + 4])
    range_records = [
        {"range": interval, "bytes_sha256": _sha(rom[interval[0] : interval[1]])}
        for interval in ranges
    ]
    packed = b"".join(rom[target : target + 4] for target in sorted(target_sources))
    literal_denominator = {
        "encoding": EXPECTED_LITERAL["encoding"],
        "target_formula": EXPECTED_LITERAL["target_formula"],
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
    if literal_denominator != EXPECTED_LITERAL:
        raise ValueError("literal denominator changed")
    selection_funnel = {
        "raw_source_instruction_count": raw_source_count,
        "raw_unique_target_word_count": len(raw_targets),
        "source_owner_eligible_instruction_count": source_owner_eligible_count,
        "excluded_non_battle_controller_owner_source_count": raw_source_count - source_owner_eligible_count,
        "excluded_non_unknown_target_source_count": source_owner_eligible_count - len(sources),
    }
    if selection_funnel != EXPECTED_SELECTION_FUNNEL:
        raise ValueError("literal selection funnel changed")
    source_summary = {
        "block_count": len(blocks),
        "instruction_count": instruction_count,
        "instruction_bytes": instruction_bytes,
    }
    if source_summary != EXPECTED_SOURCE_SUMMARY:
        raise ValueError("decoded Thumb denominator changed")
    overlap_counts = {
        "v3_packet_target_overlap_word_count": len(set(target_sources) & overlap_targets["v3_packet"]),
        "proven_roots_batch_target_overlap_word_count": len(set(target_sources) & overlap_targets["proven_roots_batch"]),
    }
    if any(value != 0 for value in overlap_counts.values()):
        raise ValueError("target overlap with bound prior packet")
    if baseline_mode and _project_segment_count(coverage["segments"], ranges) != PROJECTED_SUMMARY["segment_count"]:
        raise ValueError("coverage projection segment denominator changed")
    coverage_baseline = {
        "path": COVERAGE_PATH.as_posix(),
        "sha256": IDENTITIES[COVERAGE_PATH],
        "source_primary_class": SOURCE_CLASS,
        "summary": BASELINE_SUMMARY,
    }
    summary = {
        key: literal_denominator[key]
        for key in ("source_instruction_count", "unique_target_word_count", "target_bytes", "merged_target_range_count")
    }
    return {
        "schema": "rom-battle-controller-consumed-literals-v1",
        "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},
        "public_contract_sha256": CONTRACT_SHA256,
        "source_artifact": SOURCE_ARTIFACT,
        "coverage_baseline": coverage_baseline,
        "overlap_baseline": OVERLAP_BASELINE,
        "source_denominator": {
            "summary": source_summary,
            "thumb_block_denominator_sha256": block_denominator_sha256,
            "selection_funnel": selection_funnel,
        },
        "literal_denominator": literal_denominator,
        "source_to_target": sources,
        "target_words": targets,
        **overlap_counts,
        "promotion": {
            "promotion_batch": PROMOTION_BATCH,
            "primary_class": PRIMARY_CLASS,
            "claim_kind": CLAIM_KIND,
            "ranges": ranges,
            "range_records": range_records,
        },
        "coverage_projection": PROJECTED_SUMMARY,
        "summary": summary,
        "scope": {
            "frozen_battle_controller_extension_membership_reused": True,
            "source_owner_exact_battle_controller_cfg": True,
            "target_words_complete_current_unknown": True,
            "prior_packet_target_overlap_excluded_and_frozen": True,
            "cfg_traversal_expanded": False,
            "frontiers_resolved": False,
            "loaded_value_semantics_proven": False,
        },
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
        "artifact_schema": "rom-battle-controller-consumed-literals-artifact-v1",
        "artifact_status": "accepted",
        "payload_schema": expected_payload["schema"],
        "public_contract_sha256": CONTRACT_SHA256,
        "rom": expected_payload["rom"],
        "source_artifact": expected_payload["source_artifact"],
        "coverage_baseline": expected_payload["coverage_baseline"],
        "overlap_baseline": expected_payload["overlap_baseline"],
        "literal_denominator": expected_payload["literal_denominator"],
        "source_denominator": expected_payload["source_denominator"],
        "promotion": expected_payload["promotion"],
        "coverage_projection": expected_payload["coverage_projection"],
        "summary": expected_payload["summary"],
        "scope": expected_payload["scope"],
        "non_claims": expected_payload["non_claims"],
        "v3_packet_target_overlap_word_count": expected_payload["v3_packet_target_overlap_word_count"],
        "proven_roots_batch_target_overlap_word_count": expected_payload["proven_roots_batch_target_overlap_word_count"],
        "verifier": {
            "command": [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_battle_controller_consumed_literals.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/rom-battle-controller-consumed-literals-v1",
            ],
            "exit_code": 0,
        },
        "files": {PAYLOAD_NAME: {"sha256": _sha(payload_bytes), "size": len(payload_bytes)}},
    }
    if manifest != expected_manifest:
        raise ValueError("artifact manifest does not match independently rebuilt contract")
    return {
        "schema": "rom-battle-controller-consumed-literals-verification-v1",
        "verified": True,
        "contract_ok": True,
        "artifact": {
            "path": artifact.as_posix(),
            "manifest_sha256": _sha((artifact / "manifest.json").read_bytes()),
            "payload_sha256": _sha(payload_bytes),
        },
        "source_denominator": {
            "thumb_block_count": EXPECTED_SOURCE_SUMMARY["block_count"],
            "thumb_instruction_count": EXPECTED_SOURCE_SUMMARY["instruction_count"],
            "thumb_instruction_bytes": EXPECTED_SOURCE_SUMMARY["instruction_bytes"],
            "thumb_block_denominator_sha256": SOURCE_ARTIFACT["thumb_block_denominator_sha256"],
            "selection_funnel": EXPECTED_SELECTION_FUNNEL,
        },
        "literal_denominator": expected_payload["literal_denominator"],
        "summary": expected_payload["summary"],
        "coverage_projection": PROJECTED_SUMMARY,
        "v3_packet_target_overlap_word_count": expected_payload["v3_packet_target_overlap_word_count"],
        "proven_roots_batch_target_overlap_word_count": expected_payload["proven_roots_batch_target_overlap_word_count"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_root(args.root, args.artifact), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
