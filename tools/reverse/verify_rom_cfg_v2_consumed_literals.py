#!/usr/bin/env python3
"""Independently verify the frozen v2 consumed-literal artifact."""

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
SOURCE_MANIFEST = Path("artifacts/rom-cfg-inventory-v2/manifest.json")
SOURCE_PAYLOAD = Path("artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json")
SOURCE_EXPORTER = Path("tools/export_rom_cfg_inventory.py")
SOURCE_VERIFIER = Path("tools/verify_rom_cfg_inventory.py")
SOURCE_TEST = Path("tests/test_export_rom_cfg_inventory.py")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
PAYLOAD_NAME = "rom-cfg-v2-consumed-literals.json"
CONTRACT_SHA256 = "e2a629158d5846b89aaeb691cdea5714911a206a4d96020a1398c3ef787e4834"
SOURCE_CLASS = "armv4t_cfg_reachable_thumb_code"
PRIMARY_CLASS = "armv4t_cfg_v2_consumed_literal_word"

IDENTITIES = {
    SOURCE_MANIFEST: "ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753",
    SOURCE_PAYLOAD: "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd",
    SOURCE_EXPORTER: "2e50e58f753d88dbbfac617709280cc79207a1990a13dd06cb1c3eae5856e0ca",
    SOURCE_VERIFIER: "a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93",
    SOURCE_TEST: "68543c6d27d745ae1a8880393c5481a3b329e2772b2e708232b68edc8310b7a2",
    COVERAGE_PATH: "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
}
EXPECTED = {
    "root_count": 263,
    "frontier_count": 366,
    "thumb_block_count": 7_648,
    "thumb_instruction_count": 40_635,
    "thumb_instruction_bytes": 85_236,
    "source_instruction_count": 1_841,
    "unique_target_word_count": 1_699,
    "target_bytes": 6_796,
    "merged_target_range_count": 653,
    "thumb_block_denominator_sha256": "03cbf5a60b3f317b978891dfcad72c50bd9cb8bc54de271b96b0c303245f9c80",
    "source_vector_sha256": "e0357e03d77943a182f3d749ac77695743af44141d7e27de6b5a96c97614e2c2",
    "source_offset_vector_sha256": "6ac05f8ea00e6b28a70ccc6bd61bc9369180a28eb8b5001507ea90258638dde7",
    "target_vector_sha256": "79d8874a6e192695543c6cde000dc3fc16b54e4a9cb8d9355d6e68c4f52e142f",
    "target_offset_vector_sha256": "0edd98402935aba85860d9de7529af2f0fbde67a1b53a486bac61c2ec119294b",
    "range_vector_sha256": "627e1224f088259206139b27a3706d10360a8cffc339ef6aa050f9a405594c03",
    "packed_target_bytes_sha256": "99a1e239b0a9ab3848a919d8378445eb3cfe3839961ba53a716aa2ad4f437925",
}
BASELINE_SUMMARY = {
    "classified_bytes": 6_127_684,
    "unknown_bytes": 163_772,
    "claim_count": 14_720,
    "segment_count": 16_693,
}
PROJECTED_SUMMARY = {
    "classified_bytes": 6_134_480,
    "unknown_bytes": 156_976,
    "claim_count": 15_373,
    "segment_count": 17_028,
    "delta": {
        "classified_bytes": 6_796,
        "unknown_bytes": -6_796,
        "claim_count": 653,
        "segment_count": 335,
    },
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


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


def _bound_json(root: Path, relative: Path) -> dict[str, Any]:
    data = (root / relative).read_bytes()
    if _sha(data) != IDENTITIES[relative]:
        raise ValueError(f"bound input identity changed: {relative}")
    return json.loads(data)


def _read_bound_inputs(root: Path):
    rom = (root / ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    source_manifest = _bound_json(root, SOURCE_MANIFEST)
    source = _bound_json(root, SOURCE_PAYLOAD)
    for relative in (SOURCE_EXPORTER, SOURCE_VERIFIER, SOURCE_TEST):
        data = (root / relative).read_bytes()
        if _sha(data) != IDENTITIES[relative]:
            raise ValueError(f"bound input identity changed: {relative}")
    coverage_bytes = (root / COVERAGE_PATH).read_bytes()
    coverage = json.loads(coverage_bytes)
    if (
        source_manifest.get("artifact_schema") != "rom-cfg-inventory-v2"
        or source.get("schema") != "rom-cfg-inventory-v2"
        or source.get("summary") != source_manifest.get("summary")
    ):
        raise ValueError("source artifact contract changed")
    if (
        len(source.get("roots", [])) != EXPECTED["root_count"]
        or len(source.get("frontiers", [])) != EXPECTED["frontier_count"]
    ):
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
        index = bisect.bisect_right(starts, offset) - 1
        if index < 0:
            raise ValueError("coverage lookup escaped ROM")
        return segments[index]

    return rom, source, coverage, segment_at, baseline_mode


def _artifact_files(artifact: Path) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    if artifact.is_symlink() or not artifact.is_dir():
        raise ValueError("artifact directory is missing or a symlink")
    members = list(artifact.iterdir())
    if (
        {path.name for path in members} != {"manifest.json", PAYLOAD_NAME}
        or any(path.is_symlink() or not path.is_file() for path in members)
    ):
        raise ValueError("artifact file set changed")
    manifest = json.loads((artifact / "manifest.json").read_bytes())
    payload_bytes = (artifact / PAYLOAD_NAME).read_bytes()
    payload = json.loads(payload_bytes)
    file_record = manifest.get("files", {}).get(PAYLOAD_NAME, {})
    if (
        file_record.get("sha256") != _sha(payload_bytes)
        or file_record.get("size") != len(payload_bytes)
    ):
        raise ValueError("payload identity does not match artifact file record")
    return manifest, payload, payload_bytes


def _rebuild(root: Path) -> dict[str, Any]:
    rom, source, _coverage, segment_at, baseline_mode = _read_bound_inputs(root)
    blocks = [block for block in source["blocks"] if block.get("mode") == "thumb"]
    if len(blocks) != EXPECTED["thumb_block_count"]:
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
    if _sha(_canonical(block_rows)) != EXPECTED["thumb_block_denominator_sha256"]:
        raise ValueError("Thumb block denominator changed")

    sources: list[dict[str, Any]] = []
    target_sources: dict[int, list[int]] = {}
    instruction_count = 0
    instruction_bytes = 0
    previous_start = -1
    for block in blocks:
        start, end = block["range"]
        if start <= previous_start or end <= start or end > len(rom):
            raise ValueError("Thumb block order or range changed")
        previous_start = start
        if _sha(rom[start:end]) != block["bytes_sha256"]:
            raise ValueError("Thumb block bytes changed")
        offset = start
        block_count = 0
        while offset < end:
            width = _thumb_instruction_width(rom, offset, end)
            halfword = struct.unpack_from("<H", rom, offset)[0]
            source_segment = segment_at(offset)
            if (
                width == 2
                and halfword & 0xF800 == 0x4800
                and source_segment.get("primary_class") == SOURCE_CLASS
                and source_segment["range"][0] <= offset
                and offset + 2 <= source_segment["range"][1]
            ):
                target = _decode_ldr_literal_target(offset, halfword)
                if target + 4 <= len(rom):
                    target_segment = segment_at(target)
                    if (
                        target_segment.get("primary_class") == ("unknown" if baseline_mode else PRIMARY_CLASS)
                        and target_segment["range"][0] <= target
                        and target + 4 <= target_segment["range"][1]
                    ):
                        sources.append(
                            {
                                "source_file_offset": offset,
                                "source_raw_hex": rom[offset : offset + 2].hex(),
                                "target_file_offset": target,
                                "target_raw_hex": rom[target : target + 4].hex(),
                            }
                        )
                        target_sources.setdefault(target, []).append(offset)
            offset += width
            block_count += 1
            instruction_count += 1
            instruction_bytes += width
        if offset != end or block_count != block["instruction_count"]:
            raise ValueError("Thumb block instruction denominator changed")
    if (
        instruction_count != EXPECTED["thumb_instruction_count"]
        or instruction_bytes != EXPECTED["thumb_instruction_bytes"]
    ):
        raise ValueError("Thumb instruction denominator changed")

    targets = [
        {
            "target_file_offset": target,
            "target_raw_hex": rom[target : target + 4].hex(),
            "source_file_offsets": offsets,
        }
        for target, offsets in sorted(target_sources.items())
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
    denominator = {
        "source_instruction_count": len(sources),
        "unique_target_word_count": len(targets),
        "target_bytes": len(packed),
        "merged_target_range_count": len(ranges),
        "source_vector_sha256": _sha(_canonical(sources)),
        "source_offset_vector_sha256": _sha(
            _canonical([row["source_file_offset"] for row in sources])
        ),
        "target_vector_sha256": _sha(_canonical(targets)),
        "target_offset_vector_sha256": _sha(_canonical(sorted(target_sources))),
        "range_vector_sha256": _sha(_canonical(range_records)),
        "packed_target_bytes_sha256": _sha(packed),
    }
    for key, value in denominator.items():
        if EXPECTED[key] != value:
            raise ValueError(f"literal denominator changed: {key}")
    return {
        "sources": sources,
        "targets": targets,
        "ranges": ranges,
        "range_records": range_records,
        "denominator": denominator,
        "thumb_block_count": len(blocks),
        "thumb_instruction_count": instruction_count,
        "thumb_instruction_bytes": instruction_bytes,
    }


def verify_root(root: Path, artifact: Path) -> dict[str, Any]:
    root = root.resolve()
    artifact = artifact.absolute()
    manifest, payload, payload_bytes = _artifact_files(artifact)
    rebuilt = _rebuild(root)
    if (
        manifest.get("artifact_schema")
        != "rom-cfg-v2-consumed-literals-artifact-v1"
        or manifest.get("artifact_status") != "accepted"
        or payload.get("schema") != "rom-cfg-v2-consumed-literals-v1"
        or manifest.get("public_contract_sha256") != CONTRACT_SHA256
        or payload.get("public_contract_sha256") != CONTRACT_SHA256
    ):
        raise ValueError("artifact schema or contract identity changed")
    if payload.get("source_to_target") != rebuilt["sources"]:
        raise ValueError("source-to-target vector changed")
    if payload.get("target_words") != rebuilt["targets"]:
        raise ValueError("target word vector changed")
    promotion = payload.get("promotion", {})
    if (
        promotion.get("promotion_batch") != "rom-cfg-v2-consumed-literals-v1"
        or promotion.get("primary_class") != "armv4t_cfg_v2_consumed_literal_word"
        or promotion.get("claim_kind") != "armv4t_cfg_v2_consumed_literal_word_bytes"
        or promotion.get("ranges") != rebuilt["ranges"]
        or promotion.get("range_records") != rebuilt["range_records"]
    ):
        raise ValueError("promotion vector changed")
    if payload.get("literal_denominator") != rebuilt["denominator"]:
        raise ValueError("literal denominator report changed")
    expected_summary = {
        key: EXPECTED[key]
        for key in (
            "source_instruction_count",
            "unique_target_word_count",
            "target_bytes",
            "merged_target_range_count",
        )
    }
    if payload.get("summary") != expected_summary:
        raise ValueError("payload summary changed")
    if payload.get("coverage_projection") != PROJECTED_SUMMARY:
        raise ValueError("coverage projection changed")
    if manifest.get("summary") != expected_summary:
        raise ValueError("manifest summary changed")
    if manifest.get("literal_denominator") != rebuilt["denominator"]:
        raise ValueError("manifest denominator changed")
    return {
        "schema": "rom-cfg-v2-consumed-literals-verification-v1",
        "verified": True,
        "contract_ok": True,
        "artifact": {
            "path": artifact.as_posix(),
            "manifest_sha256": _sha((artifact / "manifest.json").read_bytes()),
            "payload_sha256": _sha(payload_bytes),
        },
        "source_denominator": {
            "thumb_block_count": rebuilt["thumb_block_count"],
            "thumb_instruction_count": rebuilt["thumb_instruction_count"],
            "thumb_instruction_bytes": rebuilt["thumb_instruction_bytes"],
            "thumb_block_denominator_sha256": EXPECTED["thumb_block_denominator_sha256"],
        },
        "literal_denominator": rebuilt["denominator"],
        "summary": expected_summary,
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
