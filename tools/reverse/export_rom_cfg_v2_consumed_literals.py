#!/usr/bin/env python3
"""Export literal words consumed by the frozen v2 Thumb CFG."""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.export_rom_cfg_inventory import _decode_one


ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SOURCE_DIR = Path("artifacts/rom-cfg-inventory-v2")
SOURCE_MANIFEST = SOURCE_DIR / "manifest.json"
SOURCE_PAYLOAD = SOURCE_DIR / "rom-cfg-inventory.json"
SOURCE_EXPORTER = Path("tools/export_rom_cfg_inventory.py")
SOURCE_VERIFIER = Path("tools/verify_rom_cfg_inventory.py")
SOURCE_TEST = Path("tests/test_export_rom_cfg_inventory.py")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
PAYLOAD_NAME = "rom-cfg-v2-consumed-literals.json"

IDENTITIES = {
    SOURCE_MANIFEST: "ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753",
    SOURCE_PAYLOAD: "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd",
    SOURCE_EXPORTER: "2e50e58f753d88dbbfac617709280cc79207a1990a13dd06cb1c3eae5856e0ca",
    SOURCE_VERIFIER: "a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93",
    SOURCE_TEST: "68543c6d27d745ae1a8880393c5481a3b329e2772b2e708232b68edc8310b7a2",
    COVERAGE_PATH: "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
}
CONTRACT_SHA256 = "e2a629158d5846b89aaeb691cdea5714911a206a4d96020a1398c3ef787e4834"
SOURCE_CLASS = "armv4t_cfg_reachable_thumb_code"
PRIMARY_CLASS = "armv4t_cfg_v2_consumed_literal_word"
CLAIM_KIND = "armv4t_cfg_v2_consumed_literal_word_bytes"
PROMOTION_BATCH = "rom-cfg-v2-consumed-literals-v1"

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
}
PROJECTION_DELTA = {
    "classified_bytes": 6_796,
    "unknown_bytes": -6_796,
    "claim_count": 653,
    "segment_count": 335,
}
NON_CLAIMS = [
    "No v3, proven-roots, consumer_code_slice, ARM literal-load, or non-PC-relative load source is included.",
    "No traversal is expanded beyond the already accepted v2 block membership and no frontier is resolved.",
    "No adjacent unknown byte or whole unknown segment is promoted unless it is one of the 1699 exact target words.",
    "The loaded word value is not assigned a pointer, constant, table, resource, or business meaning beyond being consumed literal data.",
    "Natural runtime reachability, global code or literal denominators, editing, writeback, relocation, padding, and free or allocatable space remain unproven.",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _read_bound(root: Path, relative: Path) -> bytes:
    path = root / relative
    data = path.read_bytes()
    expected = IDENTITIES[relative]
    if _sha(data) != expected:
        raise ValueError(f"bound input identity changed: {relative}")
    return data


def _segment_lookup(segments: list[dict[str, Any]]):
    starts = [segment["range"][0] for segment in segments]
    if not starts or starts[0] != 0:
        raise ValueError("coverage segment denominator changed")
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
        cursor = interval[1]
    if cursor != ROM_SIZE:
        raise ValueError("coverage segment denominator changed")

    def lookup(offset: int) -> dict[str, Any]:
        index = bisect.bisect_right(starts, offset) - 1
        if index < 0:
            raise ValueError("coverage lookup escaped ROM")
        return segments[index]

    return lookup


def _validate_inputs(root: Path, rom_override: bytes | None):
    rom = (root / ROM_PATH).read_bytes() if rom_override is None else rom_override
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    source_manifest = json.loads(_read_bound(root, SOURCE_MANIFEST))
    source_payload = json.loads(_read_bound(root, SOURCE_PAYLOAD))
    _read_bound(root, SOURCE_EXPORTER)
    _read_bound(root, SOURCE_VERIFIER)
    _read_bound(root, SOURCE_TEST)
    coverage = json.loads(_read_bound(root, COVERAGE_PATH))
    if (
        source_manifest.get("artifact_schema") != "rom-cfg-inventory-v2"
        or source_payload.get("schema") != "rom-cfg-inventory-v2"
        or source_payload.get("summary") != source_manifest.get("summary")
    ):
        raise ValueError("source artifact contract changed")
    summary = source_payload.get("summary", {})
    if (
        len(source_payload.get("roots", [])) != EXPECTED["root_count"]
        or len(source_payload.get("frontiers", [])) != EXPECTED["frontier_count"]
        or summary.get("thumb_instruction_count")
        != EXPECTED["thumb_instruction_count"]
        or summary.get("thumb_instruction_bytes") != EXPECTED["thumb_instruction_bytes"]
    ):
        raise ValueError("source artifact denominator changed")
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage schema changed")
    if any(coverage.get("summary", {}).get(key) != value for key, value in BASELINE_SUMMARY.items()):
        raise ValueError("coverage baseline summary changed")
    segments = coverage.get("segments")
    if not isinstance(segments, list) or len(segments) != BASELINE_SUMMARY["segment_count"]:
        raise ValueError("coverage segment denominator changed")
    return rom, source_manifest, source_payload, coverage, _segment_lookup(segments)


def build_cfg_v2_consumed_literals_payload(
    root: Path, rom_override: bytes | None = None
) -> dict[str, Any]:
    root = root.resolve()
    rom, _manifest, source, coverage, segment_at = _validate_inputs(
        root, rom_override
    )
    thumb_blocks = [block for block in source["blocks"] if block.get("mode") == "thumb"]
    if len(thumb_blocks) != EXPECTED["thumb_block_count"]:
        raise ValueError("Thumb block denominator changed")
    block_rows = [
        {
            "id": block.get("id"),
            "range": block.get("range"),
            "instruction_count": block.get("instruction_count"),
            "bytes_sha256": block.get("bytes_sha256"),
        }
        for block in thumb_blocks
    ]
    if _sha(_canonical(block_rows)) != EXPECTED["thumb_block_denominator_sha256"]:
        raise ValueError("Thumb block denominator changed")

    source_rows: list[dict[str, Any]] = []
    target_sources: dict[int, list[int]] = {}
    decoded_count = 0
    decoded_bytes = 0
    previous_start = -1
    for block in thumb_blocks:
        interval = block["range"]
        if (
            not isinstance(interval, list)
            or len(interval) != 2
            or not all(isinstance(value, int) for value in interval)
        ):
            raise ValueError("Thumb block range changed")
        start, end = interval
        if start <= previous_start or end <= start or end > len(rom):
            raise ValueError("Thumb block order or range changed")
        previous_start = start
        if _sha(rom[start:end]) != block["bytes_sha256"]:
            raise ValueError("Thumb block bytes changed")
        offset = start
        block_count = 0
        while offset < end:
            node = _decode_one(rom, offset, "thumb")
            if not node.get("accepted") or node.get("size") not in {2, 4}:
                raise ValueError(f"Thumb block decode failed at 0x{offset:06X}")
            size = node["size"]
            if offset + size > end:
                raise ValueError("Thumb instruction crosses block boundary")
            raw_halfword = struct.unpack_from("<H", rom, offset)[0]
            source_segment = segment_at(offset)
            if (
                size == 2
                and raw_halfword & 0xF800 == 0x4800
                and source_segment.get("primary_class") == SOURCE_CLASS
                and source_segment["range"][0] <= offset
                and offset + 2 <= source_segment["range"][1]
            ):
                target = ((offset + 4) & ~3) + (raw_halfword & 0xFF) * 4
                if target + 4 <= len(rom):
                    target_segment = segment_at(target)
                    if (
                        target_segment.get("primary_class") == "unknown"
                        and target_segment["range"][0] <= target
                        and target + 4 <= target_segment["range"][1]
                    ):
                        row = {
                            "source_file_offset": offset,
                            "source_raw_hex": rom[offset : offset + 2].hex(),
                            "target_file_offset": target,
                            "target_raw_hex": rom[target : target + 4].hex(),
                        }
                        source_rows.append(row)
                        target_sources.setdefault(target, []).append(offset)
            offset += size
            block_count += 1
            decoded_count += 1
            decoded_bytes += size
        if offset != end or block_count != block["instruction_count"]:
            raise ValueError("Thumb block instruction denominator changed")

    target_rows = [
        {
            "target_file_offset": target,
            "target_raw_hex": rom[target : target + 4].hex(),
            "source_file_offsets": sources,
        }
        for target, sources in sorted(target_sources.items())
    ]
    merged_ranges: list[list[int]] = []
    for target in sorted(target_sources):
        if merged_ranges and target == merged_ranges[-1][1]:
            merged_ranges[-1][1] += 4
        else:
            merged_ranges.append([target, target + 4])
    range_rows = [
        {"range": interval, "bytes_sha256": _sha(rom[interval[0] : interval[1]])}
        for interval in merged_ranges
    ]
    packed = b"".join(rom[target : target + 4] for target in sorted(target_sources))
    actual = {
        "source_instruction_count": len(source_rows),
        "unique_target_word_count": len(target_rows),
        "target_bytes": len(packed),
        "merged_target_range_count": len(merged_ranges),
        "source_vector_sha256": _sha(_canonical(source_rows)),
        "source_offset_vector_sha256": _sha(
            _canonical([row["source_file_offset"] for row in source_rows])
        ),
        "target_vector_sha256": _sha(_canonical(target_rows)),
        "target_offset_vector_sha256": _sha(
            _canonical(sorted(target_sources))
        ),
        "range_vector_sha256": _sha(_canonical(range_rows)),
        "packed_target_bytes_sha256": _sha(packed),
    }
    for key, expected in EXPECTED.items():
        if key in actual and actual[key] != expected:
            raise ValueError(f"literal denominator changed: {key}")
    if (
        decoded_count != EXPECTED["thumb_instruction_count"]
        or decoded_bytes != EXPECTED["thumb_instruction_bytes"]
    ):
        raise ValueError("decoded Thumb denominator changed")

    coverage_baseline = {
        "path": COVERAGE_PATH.as_posix(),
        "sha256": IDENTITIES[COVERAGE_PATH],
        "source_primary_class": SOURCE_CLASS,
        "summary": BASELINE_SUMMARY,
    }
    return {
        "schema": "rom-cfg-v2-consumed-literals-v1",
        "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},
        "public_contract_sha256": CONTRACT_SHA256,
        "source_artifact": {
            "path": SOURCE_DIR.as_posix(),
            "manifest_sha256": IDENTITIES[SOURCE_MANIFEST],
            "payload_sha256": IDENTITIES[SOURCE_PAYLOAD],
            "source_exporter_sha256": IDENTITIES[SOURCE_EXPORTER],
            "source_verifier_sha256": IDENTITIES[SOURCE_VERIFIER],
            "source_test_sha256": IDENTITIES[SOURCE_TEST],
        },
        "coverage_baseline": coverage_baseline,
        "source_denominator": {
            "summary": {
                "block_count": len(thumb_blocks),
                "instruction_count": decoded_count,
                "instruction_bytes": decoded_bytes,
            },
            "thumb_block_denominator_sha256": EXPECTED["thumb_block_denominator_sha256"],
        },
        "literal_denominator": actual,
        "source_to_target": source_rows,
        "target_words": target_rows,
        "promotion": {
            "promotion_batch": PROMOTION_BATCH,
            "primary_class": PRIMARY_CLASS,
            "claim_kind": CLAIM_KIND,
            "ranges": merged_ranges,
            "range_records": range_rows,
        },
        "coverage_projection": {
            **PROJECTED_SUMMARY,
            "delta": PROJECTION_DELTA,
        },
        "summary": {
            "source_instruction_count": len(source_rows),
            "unique_target_word_count": len(target_rows),
            "target_bytes": len(packed),
            "merged_target_range_count": len(merged_ranges),
        },
        "scope": {
            "frozen_v2_cfg_membership_reused": True,
            "source_owner_restricted_to_v2_cfg": True,
            "target_words_complete_current_unknown": True,
            "cfg_traversal_expanded": False,
            "frontiers_resolved": False,
            "loaded_value_semantics_proven": False,
        },
        "non_claims": NON_CLAIMS,
    }


def _replace_output(output: Path, files: dict[str, bytes]) -> None:
    if output.exists() and any(output.iterdir()):
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


def export_rom_cfg_v2_consumed_literals(root: Path, output: Path) -> dict[str, Any]:
    payload = build_cfg_v2_consumed_literals_payload(root)
    payload_bytes = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": "rom-cfg-v2-consumed-literals-artifact-v1",
        "artifact_status": "accepted",
        "payload_schema": payload["schema"],
        "public_contract_sha256": CONTRACT_SHA256,
        "rom": payload["rom"],
        "source_artifact": payload["source_artifact"],
        "coverage_baseline": payload["coverage_baseline"],
        "literal_denominator": payload["literal_denominator"],
        "promotion": payload["promotion"],
        "coverage_projection": payload["coverage_projection"],
        "summary": payload["summary"],
        "scope": payload["scope"],
        "non_claims": payload["non_claims"],
        "verifier": {
            "command": [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_cfg_v2_consumed_literals.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/rom-cfg-v2-consumed-literals-v1",
            ],
            "exit_code": 0,
        },
        "files": {PAYLOAD_NAME: {"sha256": _sha(payload_bytes), "size": len(payload_bytes)}},
    }
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    _replace_output(output, {PAYLOAD_NAME: payload_bytes, "manifest.json": manifest_bytes})
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = export_rom_cfg_v2_consumed_literals(args.root.resolve(), args.output)
    print(json.dumps(manifest["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
