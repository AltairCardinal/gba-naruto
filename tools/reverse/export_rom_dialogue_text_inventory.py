#!/usr/bin/env python3
"""Export the consumer-bound 305-row dialogue text table and its NUL targets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
from typing import Any
import uuid


SCHEMA = "rom-dialogue-text-inventory-v1"
VERIFY_SCHEMA = "rom-dialogue-text-inventory-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_START = 0x461CE4
TABLE_END = 0x4634B8
ROW_COUNT = 305
ROW_SIZE = 20
TARGET_SLOTS = ("primary", "label_0", "label_1", "label_2")
PAYLOAD_NAME = "dialogue-text-inventory.json"
TABLE_NAME = "pointer-table.bin"
BUNDLE_NAME = "direct-nul-targets.bin"
EXPECTED_FILES = {PAYLOAD_NAME, TABLE_NAME, BUNDLE_NAME, "manifest.json"}
EXPECTED_SUMMARY = {
    "table_row_count": 305,
    "table_byte_count": 6_100,
    "sentinel_count": 305,
    "direct_pointer_slot_count": 1_220,
    "direct_target_count": 1_220,
    "unique_target_count": 1_220,
    "duplicate_target_count": 0,
    "overlapping_target_range_count": 0,
    "direct_target_bytes": 18_207,
    "target_payload_bytes": 16_987,
    "newline_target_count": 170,
    "newline_count": 203,
}
SCOPE = {
    "fixed_table_structure_complete": True,
    "direct_target_extraction_complete": True,
    "consumer_and_nul_protocol_bound": True,
    "all_rows_runtime_reachability_complete": False,
    "label_selector_upstream_bounds_complete": False,
    "natural_language_decoding_complete": False,
}
LIMITATIONS = [
    "one confirmed group-selection path uses u8; no path-level evidence proves runtime reachability of every row 0..304",
    "label selector values 0..2 are an upstream invariant not checked in this function",
    "raw game glyph codes are not claimed to be correctly decoded natural-language text",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _addr(value: int) -> str:
    return f"0x{value:08X}"


def _decode_bl(callsite: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return callsite + 4 + displacement


def _require_bl(rom: bytes, offset: int, target: int) -> None:
    first, second = struct.unpack_from("<HH", rom, offset)
    if _decode_bl(ROM_BASE + offset, first, second) != target:
        raise ValueError(
            f"dialogue consumer BL changed at 0x{ROM_BASE + offset:08X}"
        )


def _consumer_evidence(rom: bytes) -> dict[str, Any]:
    expected_windows = {
        (0x8F9E2, 0x8F9F4): "0320012101f077fd7ee70320002101f072fd",
        (0x917B0, 0x917C6): "4d4a0f92119b1a93504619900c99002901d14a4a0f92",
        (0x91950, 0x9195E): "f95e8800401880000f9908181090",
        (0x919DA, 0x919EC): "109a50680221009100210b9a0023d4f7b6fe",
        (0x66788, 0x6678E): "4946fff76ffd",
        (0x66302, 0x6630A): "b17c05aafff73dfe",
        (0x6671C, 0x66728): "079a1078002800d0abe50798",
        (0x65FB8, 0x65FC2): "1b18201c311cfff77bff",
    }
    for (start, end), expected_hex in expected_windows.items():
        if rom[start:end].hex() != expected_hex:
            raise ValueError(
                f"dialogue consumer instruction window changed at 0x{ROM_BASE + start:08X}"
            )
    if struct.unpack_from("<I", rom, 0x918E8)[0] != ROM_BASE + TABLE_START:
        raise ValueError("dialogue table literal changed")
    if struct.unpack_from("<I", rom, 0x918EC)[0] != 0x08459284:
        raise ValueError("dialogue alternate table literal changed")
    for callsite, target in (
        (0x8F9E6, 0x080914D8),
        (0x8F9F0, 0x080914D8),
        (0x919E8, 0x08066758),
        (0x6678A, 0x0806626C),
        (0x66306, 0x08065F84),
        (0x65FBE, 0x08065EB8),
    ):
        _require_bl(rom, callsite, target)

    expected_hashes = {
        "parser_sha256": (0x6626C, 0x66736, "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"),
        "glyph_wrapper_sha256": (0x65F84, 0x66034, "7e4316e63cbb44d09b26c7cc6592c580b83af0b328098c67669db1b05d1c784c"),
        "glyph_expander_sha256": (0x65EB8, 0x65F82, "354ace23de93d27679e6749fd3ea5d2f39608e85a5abd10eb767f47e418abb47"),
        "label_loop_sha256": (0x91A20, 0x91A68, "2746339b568a82686da18aaa91e1a2b818555ec44946650d8345e85536cdcafc"),
    }
    result: dict[str, Any] = {
        "entry_calls": ["0x0808F9E2", "0x0808F9EC"],
        "table_literal_load": "0x080917B0",
        "table_literal": "0x080918E8",
        "table_base": _addr(ROM_BASE + TABLE_START),
        "row_index_formula": "0x08091950",
        "primary_pointer_load": "0x080919DA",
        "text_object_wrapper": "0x08066758",
        "nul_terminated_parser": "0x0806626C",
        "glyph_wrapper": "0x08065F84",
        "glyph_expander": "0x08065EB8",
        "confirmed_address_formula": "table_base + group_index * 20",
        "confirmed_primary_field_offset": 4,
        "nul_termination_check": "0x0806671C..0x08066726",
    }
    for key, (start, end, expected) in expected_hashes.items():
        actual = _sha(rom[start:end])
        if actual != expected:
            raise ValueError(f"dialogue {key} changed")
        result[key] = actual
    return result


def _build(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    root = root.resolve(strict=True)
    rom = (root / ROM_PATH).read_bytes()
    if _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 changed")
    if TABLE_END - TABLE_START != ROW_COUNT * ROW_SIZE:
        raise AssertionError("dialogue table constants are inconsistent")
    consumer = _consumer_evidence(rom)
    table = rom[TABLE_START:TABLE_END]
    if _sha(table) != "5b36c67620030d5ccc8795a2a260aca604d90fad4a49f7c7cb9d4c7cdc63c73f":
        raise ValueError("dialogue table bytes changed")

    rows = []
    bundle = bytearray()
    ranges: list[tuple[int, int]] = []
    pointers: list[int] = []
    newline_target_count = 0
    newline_count = 0
    target_payload_bytes = 0
    target_id = 0
    for row_id in range(ROW_COUNT):
        row_start = TABLE_START + row_id * ROW_SIZE
        words = struct.unpack_from("<5I", rom, row_start)
        if words[0] != 0:
            raise ValueError(f"dialogue row {row_id} sentinel is not zero")
        targets = []
        for slot_index, (slot, pointer) in enumerate(zip(TARGET_SLOTS, words[1:])):
            start = pointer - ROM_BASE
            if not 0x459414 <= start < TABLE_START:
                raise ValueError(
                    f"dialogue row {row_id} {slot} pointer escapes the text bank"
                )
            try:
                end = rom.index(0, start, TABLE_START) + 1
            except ValueError as error:
                raise ValueError(
                    f"dialogue row {row_id} {slot} has no NUL terminator"
                ) from error
            raw = rom[start:end]
            payload = raw[:-1]
            invalid_controls = sorted({byte for byte in payload if byte < 0x20} - {0x0A})
            if invalid_controls:
                raise ValueError(
                    f"dialogue row {row_id} {slot} has unsupported control bytes"
                )
            linefeeds = payload.count(0x0A)
            packed_start = len(bundle)
            bundle.extend(raw)
            packed_end = len(bundle)
            table_offset = row_start + 4 * (slot_index + 1)
            targets.append(
                {
                    "target_id": target_id,
                    "slot": slot,
                    "table_offset": table_offset,
                    "pointer": _addr(pointer),
                    "range": [start, end],
                    "gba_range": [_addr(ROM_BASE + start), _addr(ROM_BASE + end)],
                    "packed_range": [packed_start, packed_end],
                    "size": len(raw),
                    "payload_size": len(payload),
                    "newline_count": linefeeds,
                    "bytes_sha256": _sha(raw),
                }
            )
            pointers.append(pointer)
            ranges.append((start, end))
            target_payload_bytes += len(payload)
            newline_count += linefeeds
            newline_target_count += linefeeds > 0
            target_id += 1
        rows.append(
            {
                "row_id": row_id,
                "table_range": [row_start, row_start + ROW_SIZE],
                "sentinel": 0,
                "targets": targets,
            }
        )

    duplicates = len(pointers) - len(set(pointers))
    ordered_ranges = sorted(ranges)
    overlaps = sum(
        current_start < previous_end
        for (_, previous_end), (current_start, _) in zip(
            ordered_ranges, ordered_ranges[1:]
        )
    )
    if pointers != sorted(pointers):
        raise ValueError("dialogue target pointers are not strictly ordered")
    summary = {
        "table_row_count": len(rows),
        "table_byte_count": len(table),
        "sentinel_count": sum(row["sentinel"] == 0 for row in rows),
        "direct_pointer_slot_count": len(pointers),
        "direct_target_count": len(ranges),
        "unique_target_count": len(set(pointers)),
        "duplicate_target_count": duplicates,
        "overlapping_target_range_count": overlaps,
        "direct_target_bytes": len(bundle),
        "target_payload_bytes": target_payload_bytes,
        "newline_target_count": newline_target_count,
        "newline_count": newline_count,
    }
    if summary != EXPECTED_SUMMARY:
        raise ValueError(f"dialogue inventory denominator changed: {summary}")
    if _sha(bytes(bundle)) != "7509a63b2f892ea9f2892ed4cc703da72457247df148a1435edbbee8b2d95569":
        raise ValueError("dialogue target bundle changed")

    implementation = {
        "exporter_sha256": _sha(Path(__file__).read_bytes()),
        "verifier_sha256": _sha(
            (root / "tools/verify_rom_dialogue_text_inventory.py").read_bytes()
        ),
        "test_sha256": _sha(
            (root / "tests/test_export_rom_dialogue_text_inventory.py").read_bytes()
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
        "table": {
            "file_range": [TABLE_START, TABLE_END],
            "gba_range": [_addr(ROM_BASE + TABLE_START), _addr(ROM_BASE + TABLE_END)],
            "row_size": ROW_SIZE,
            "row_count": ROW_COUNT,
            "word_layout": [
                "zero_sentinel",
                "primary_text_pointer",
                "label_0_text_pointer",
                "label_1_text_pointer",
                "label_2_text_pointer",
            ],
            "sha256": _sha(table),
        },
        "consumer_evidence": consumer,
        "summary": summary,
        "rows": rows,
        "files": {
            TABLE_NAME: {"size": len(table), "sha256": _sha(table)},
            BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bytes(bundle))},
        },
        "scope": SCOPE,
        "limitations": LIMITATIONS,
    }
    files = {
        PAYLOAD_NAME: (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode(),
        TABLE_NAME: table,
        BUNDLE_NAME: bytes(bundle),
    }
    return payload, files


def _manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    report = {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        **EXPECTED_SUMMARY,
        "errors": [],
    }
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {name: _sha(data) for name, data in sorted(files.items())},
        "scope": SCOPE,
        "producer": {
            "command": [
                "python3",
                "tools/export_rom_dialogue_text_inventory.py",
                "--root",
                ".",
                "--output-dir",
                f"artifacts/{SCHEMA}",
            ],
            **payload["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_rom_dialogue_text_inventory.py",
                "--root",
                ".",
                "--artifact-dir",
                f"artifacts/{SCHEMA}",
            ],
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": report,
        },
    }


def _validate_output(root: Path, output: Path) -> Path:
    target = output.expanduser().resolve()
    root = root.resolve()
    if output.is_symlink() or target == root or target in root.parents:
        raise ValueError("output directory is unsafe")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("refusing to replace foreign output")
    try:
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("refusing to replace foreign output") from error
    actual = {
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_file()
    }
    if (
        any(path.is_symlink() for path in target.rglob("*"))
        or manifest.get("artifact_schema") != SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or actual != EXPECTED_FILES
    ):
        raise ValueError("refusing to replace foreign output")
    for name, expected in manifest.get("files", {}).items():
        if _sha((target / name).read_bytes()) != expected:
            raise ValueError("refusing to replace corrupted output")
    return target


def _replace(output: Path, files: dict[str, bytes], manifest: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    backup = None
    try:
        for name, data in files.items():
            (temporary / name).write_bytes(data)
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if output.exists():
            backup = output.parent / f".{output.name}.backup-{uuid.uuid4().hex}"
            output.rename(backup)
        try:
            os.replace(temporary, output)
        except BaseException:
            if backup is not None and backup.exists() and not output.exists():
                backup.rename(output)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists():
            if not output.exists():
                backup.rename(output)
            else:
                shutil.rmtree(backup)


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    target = _validate_output(root, output)
    payload, files = _build(root)
    _replace(target, files, _manifest(payload, files))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(f"artifacts/{SCHEMA}"),
    )
    args = parser.parse_args()
    output = args.output_dir
    if not output.is_absolute():
        output = args.root / output
    payload = export_artifact(args.root, output)
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
