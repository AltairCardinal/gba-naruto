#!/usr/bin/env python3
"""Independently verify the unbound strict type-0x10 syntax inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


SCHEMA = "rom-unbound-lz77-inventory-v1"
VERIFY_SCHEMA = "rom-unbound-lz77-inventory-verification-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PAYLOAD_NAME = "inventory.json"
COMPRESSED_NAME = "streams.lz77.bin"
DECOMPRESSED_NAME = "payloads.bin"
EXPECTED_FILES = {PAYLOAD_NAME, COMPRESSED_NAME, DECOMPRESSED_NAME, "manifest.json"}
ALLOWED_PRIMARY_CLASSES = {"unknown", "lz77_syntax_unbound"}

SELECTION_RULE = {
    "syntax": (
        "scan every byte for a valid GBA type-0x10 stream with exact "
        "declared-size termination, in-range back-references, no output "
        "overrun, and no ROM truncation"
    ),
    "pointer_scan": "all 4-byte-aligned u32 values mapped into this ROM",
    "aligned_pointer_reference_count": 0,
    "coverage": (
        "the complete half-open stream range has primary class unknown or "
        "lz77_syntax_unbound"
    ),
    "overlap": (
        "sort by (start,end), then greedily retain a candidate only when "
        "start >= the previous selected end"
    ),
    "runtime_reachability_claimed": False,
}

SCOPE = {
    "strict_type_0x10_syntax_scan_complete": True,
    "aligned_u32_rom_pointer_scan_complete": True,
    "selected_nonoverlapping_inventory_complete": True,
    "runtime_reachability_complete": False,
    "all_records_are_resources": False,
    "all_records_are_graphics": False,
    "consumer_identity_complete": False,
    "indirect_or_computed_references_excluded": True,
}

EXPECTED_SUMMARY = {
    "strict_candidate_count": 1_099,
    "raw_unknown_unreferenced_candidate_count": 43,
    "raw_unknown_unreferenced_compressed_bytes": 14_737,
    "raw_unknown_unreferenced_decompressed_bytes": 30_774,
    "selected_record_count": 41,
    "selected_compressed_bytes": 14_725,
    "selected_decompressed_bytes": 30_772,
}
EXPECTED_COMPRESSED_SHA256 = (
    "2db24f2804ad3d6c11d2cee7cde9a0205e86ae06eab4a02339c7ade130e41505"
)
EXPECTED_DECOMPRESSED_SHA256 = (
    "7027b4c7ca61cf2b5f92dd3851cefe24bf5b244c7354756504432901055cdd65"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def decode_lz77_strict(
    data: bytes, offset: int, *, materialize: bool = True
) -> tuple[int, bytes | None] | None:
    """Decode one exact-size GBA type-0x10 stream without trusting an exporter."""

    if offset < 0 or offset + 4 > len(data) or data[offset] != 0x10:
        return None
    declared = int.from_bytes(data[offset + 1 : offset + 4], "little")
    if declared <= 0:
        return None
    cursor = offset + 4
    output = bytearray() if materialize else None
    produced = 0
    try:
        while produced < declared:
            flags = data[cursor]
            cursor += 1
            for bit in range(7, -1, -1):
                if produced >= declared:
                    break
                if flags & (1 << bit):
                    first = data[cursor]
                    second = data[cursor + 1]
                    cursor += 2
                    length = (first >> 4) + 3
                    distance = (((first & 0x0F) << 8) | second) + 1
                    if distance > produced or produced + length > declared:
                        return None
                    if output is not None:
                        for _ in range(length):
                            output.append(output[-distance])
                    produced += length
                else:
                    value = data[cursor]
                    cursor += 1
                    if output is not None:
                        output.append(value)
                    produced += 1
    except IndexError:
        return None
    return cursor, bytes(output) if output is not None else None


def _strict_offsets(rom: bytes) -> list[int]:
    return [
        offset
        for offset in range(len(rom) - 3)
        if rom[offset] == 0x10
        and decode_lz77_strict(rom, offset, materialize=False) is not None
    ]


def _aligned_pointer_references(rom: bytes) -> dict[int, list[int]]:
    references: dict[int, list[int]] = {}
    mapped_end = ROM_BASE + len(rom)
    for pointer_offset in range(0, len(rom) - 3, 4):
        value = struct.unpack_from("<I", rom, pointer_offset)[0]
        if ROM_BASE <= value < mapped_end:
            references.setdefault(value - ROM_BASE, []).append(pointer_offset)
    return references


def _coverage_segments(root: Path, rom_size: int) -> list[dict[str, Any]]:
    document = json.loads((root / COVERAGE_PATH).read_bytes())
    if document.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage schema changed")
    if document.get("base_rom") != {
        "path": ROM_PATH.as_posix(),
        "size": rom_size,
        "sha256": ROM_SHA256,
    }:
        raise ValueError("coverage ROM identity changed")
    if document.get("domain") != [0, rom_size]:
        raise ValueError("coverage domain changed")
    if document.get("state_inventory_complete") is not True:
        raise ValueError("coverage state inventory is incomplete")
    segments = document.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("coverage segments are missing")
    cursor = 0
    primary_totals: dict[str, int] = {}
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("coverage segment is not an object")
        value = segment.get("range")
        primary_class = segment.get("primary_class")
        if (
            not isinstance(value, list)
            or len(value) != 2
            or not all(isinstance(item, int) for item in value)
            or value[0] != cursor
            or value[0] >= value[1]
            or value[1] > rom_size
            or not isinstance(primary_class, str)
        ):
            raise ValueError("coverage segments are not gap-free half-open ranges")
        primary_totals[primary_class] = (
            primary_totals.get(primary_class, 0) + value[1] - value[0]
        )
        cursor = value[1]
    if cursor != rom_size:
        raise ValueError("coverage segments do not cover the ROM")
    summary = document.get("summary")
    if (
        not isinstance(summary, dict)
        or summary.get("accounted_bytes") != rom_size
        or summary.get("unknown_bytes") != primary_totals.get("unknown", 0)
        or summary.get("classified_bytes")
        != rom_size - primary_totals.get("unknown", 0)
    ):
        raise ValueError("coverage summary does not match its segments")
    return segments


def _range_is_allowed(
    segments: list[dict[str, Any]], start: int, end: int
) -> bool:
    overlapping = [
        segment
        for segment in segments
        if segment["range"][0] < end and start < segment["range"][1]
    ]
    return bool(overlapping) and all(
        segment["primary_class"] in ALLOWED_PRIMARY_CLASSES
        for segment in overlapping
    )


def _reconstruct(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    rom = (root / ROM_PATH).read_bytes()
    if len(rom) != 6_291_456 or _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    segments = _coverage_segments(root, len(rom))
    references = _aligned_pointer_references(rom)
    strict_offsets = _strict_offsets(rom)

    raw: list[tuple[int, int, bytes]] = []
    for start in strict_offsets:
        parsed = decode_lz77_strict(rom, start, materialize=False)
        if parsed is None:
            raise ValueError(f"strict LZ77 candidate vanished at 0x{start:06X}")
        end, _ = parsed
        if start not in references and _range_is_allowed(segments, start, end):
            materialized = decode_lz77_strict(rom, start)
            if materialized is None or materialized[1] is None:
                raise ValueError(
                    f"strict LZ77 candidate could not be materialized at "
                    f"0x{start:06X}"
                )
            materialized_end, decompressed = materialized
            if materialized_end != end:
                raise ValueError(f"LZ77 end changed at 0x{start:06X}")
            raw.append((start, end, decompressed))

    selected: list[tuple[int, int, bytes]] = []
    previous_end = -1
    for item in sorted(raw, key=lambda value: (value[0], value[1])):
        if item[0] >= previous_end:
            selected.append(item)
            previous_end = item[1]

    compressed_bundle = bytearray()
    decompressed_bundle = bytearray()
    records = []
    for start, end, decompressed in selected:
        compressed = rom[start:end]
        records.append(
            {
                "range": [start, end],
                "classification": "lz77_syntax_unbound",
                "aligned_pointer_reference_count": 0,
                "runtime_reachability_claimed": False,
                "compressed_size": len(compressed),
                "compressed_sha256": _sha256(compressed),
                "compressed_bundle_offset": len(compressed_bundle),
                "decompressed_size": len(decompressed),
                "decompressed_sha256": _sha256(decompressed),
                "decompressed_bundle_offset": len(decompressed_bundle),
            }
        )
        compressed_bundle.extend(compressed)
        decompressed_bundle.extend(decompressed)

    summary = {
        "strict_candidate_count": len(strict_offsets),
        "raw_unknown_unreferenced_candidate_count": len(raw),
        "raw_unknown_unreferenced_compressed_bytes": sum(
            end - start for start, end, _ in raw
        ),
        "raw_unknown_unreferenced_decompressed_bytes": sum(
            len(decompressed) for _, _, decompressed in raw
        ),
        "selected_record_count": len(selected),
        "selected_compressed_bytes": len(compressed_bundle),
        "selected_decompressed_bytes": len(decompressed_bundle),
    }
    if summary != EXPECTED_SUMMARY:
        raise ValueError(f"unbound LZ77 denominator changed: {summary}")
    if _sha256(compressed_bundle) != EXPECTED_COMPRESSED_SHA256:
        raise ValueError("selected compressed bundle changed")
    if _sha256(decompressed_bundle) != EXPECTED_DECOMPRESSED_SHA256:
        raise ValueError("selected decompressed bundle changed")

    implementation = {
        "exporter_sha256": _sha256(
            (root / "tools/export_rom_unbound_lz77_inventory.py").read_bytes()
        ),
        "verifier_sha256": _sha256(Path(__file__).read_bytes()),
        "test_sha256": _sha256(
            (root / "tests/test_rom_unbound_lz77_inventory.py").read_bytes()
        ),
    }
    payload = {
        "schema": SCHEMA,
        "implementation": implementation,
        "rom": {
            "path": ROM_PATH.as_posix(),
            "size": len(rom),
            "sha256": ROM_SHA256,
        },
        "coverage": {
            "path": COVERAGE_PATH.as_posix(),
            "allowed_primary_classes": sorted(ALLOWED_PRIMARY_CLASSES),
            "hash_pinned": False,
            "hash_pin_omission_reason": (
                "coverage incorporates these claims, so a coverage hash would "
                "create a dependency cycle; the verifier reconstructs its "
                "gap-free state and allowed classes instead"
            ),
        },
        "selection_rule": SELECTION_RULE,
        "summary": summary,
        "records": records,
        "bundles": {
            "compressed": {
                "file": COMPRESSED_NAME,
                "size": len(compressed_bundle),
                "sha256": _sha256(compressed_bundle),
            },
            "decompressed": {
                "file": DECOMPRESSED_NAME,
                "size": len(decompressed_bundle),
                "sha256": _sha256(decompressed_bundle),
            },
        },
        "scope": SCOPE,
    }
    return payload, {
        COMPRESSED_NAME: bytes(compressed_bundle),
        DECOMPRESSED_NAME: bytes(decompressed_bundle),
        PAYLOAD_NAME: _canonical_json(payload),
    }


def _promotion(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_id": SCHEMA,
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "payload_schema": SCHEMA,
        "payload_file": PAYLOAD_NAME,
        "files": {
            relative: _sha256(data) for relative, data in sorted(files.items())
        },
        "scope": SCOPE,
        "producer": {
            "command": [
                "python3",
                "tools/export_rom_unbound_lz77_inventory.py",
                "--root",
                ".",
                "--output-dir",
                "artifacts/rom-unbound-lz77-inventory-v1",
            ],
            **payload["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_rom_unbound_lz77_inventory.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-unbound-lz77-inventory-v1",
            ],
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                **payload["summary"],
                "errors": [],
            },
        },
    }


def verify_rom_unbound_lz77_inventory(
    root: Path, artifact_dir: Path
) -> dict[str, Any]:
    errors: list[str] = []
    summary = EXPECTED_SUMMARY.copy()
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact_dir)
        if artifact.is_symlink() or not artifact.is_dir():
            raise ValueError("artifact directory is missing or symbolic")
        paths = list(artifact.iterdir())
        if {path.name for path in paths} != EXPECTED_FILES:
            raise ValueError("artifact file set changed")
        if any(path.is_symlink() or not path.is_file() for path in paths):
            raise ValueError("artifact contains a symlink or non-file entry")

        expected_payload, expected_files = _reconstruct(root)
        expected_manifest = _promotion(expected_payload, expected_files)
        actual_manifest = json.loads((artifact / "manifest.json").read_bytes())
        actual_payload = json.loads((artifact / PAYLOAD_NAME).read_bytes())
        if actual_manifest != expected_manifest:
            errors.append("promotion manifest differs from independent reconstruction")
        if actual_payload != expected_payload:
            errors.append("inventory payload differs from independent reconstruction")
        for relative, expected in expected_files.items():
            actual = (artifact / relative).read_bytes()
            if actual != expected:
                errors.append(f"artifact file differs from ROM reconstruction: {relative}")
        summary = expected_payload["summary"]
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        **summary,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/rom-unbound-lz77-inventory-v1"),
    )
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    artifact = args.artifact_dir
    if not artifact.is_absolute():
        artifact = root / artifact
    report = verify_rom_unbound_lz77_inventory(root, artifact)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
