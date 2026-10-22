#!/usr/bin/env python3
"""Independently verify the renderer script pointer-pool records at 0x0CEA.

This verifier never imports the exporter.  It re-derives the record cover, the
28-slot pointer table and the consumer contract straight from the ROM bytes and
requires the published payload to be byte-identical to that reconstruction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


SCHEMA = "rom-renderer-script-pointer-pool-records-v1"
VERIFY_SCHEMA = f"{SCHEMA}-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_BASE = 0x08000000
PAYLOAD_NAME = "rom-renderer-script-pointer-pool-records.json"
MANIFEST_NAME = "manifest.json"

POOL = (0x0CEA, 0x12F0)
POOL_DIGEST = "1730e92b4cc9ace8f484b61aedcbd2e670b45b522bd5807bdf72fd9cc03595cf"
RECORD_TOTAL = 27
RECORD_OPCODES = (1, 5, 4, 12, 3, 0)

TABLE = (0x53DF00, 0x53DF70)
TABLE_DIGEST = "f18680f6e461a60f54373e7377c580e9966e7f9be9966a9ab1d1a0eefa7451bc"
TABLE_SLOTS = 28
TABLE_LITERAL = 0x0853DF00

CONSUMER = (0x0712D0, 0x071350)
CONSUMER_DIGEST = "48e9363eeae7ca589654a66b5f963af9e4f4868facfc95cce8b2b878fedf882f"
LITERAL_LOAD = 0x0712EE
LITERAL_POOL = 0x071350
CALL_SITE = 0x071340
CALL_TARGET = 0x067158

INTERPRETER = (0x067158, 0x06836E)
INTERPRETER_DIGEST = "211812743de17ef5158ef63bd52deb3271c962b9119bf74f1bbd458b6bec96dd"
PARSER = (0x06626C, 0x066736)
PARSER_DIGEST = "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"
SJIS = (0x53D644, 0x53D73C)
SJIS_DIGEST = "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"
SJIS_COUNT = 31
LEFT = (0x0CC7, 0x0CEA)
LEFT_DIGEST = "bc6ed5847e9ae46dece7f4e309c0dcaf02fcfd6ab0159e36ca8072bb010f8cd2"
RIGHT = (0x12F0, 0x12FA)
RIGHT_DIGEST = "3ce42db81ef9c29faa251029044baca89172709af872513b4629e4b0b225f4bb"

CLAIM_KIND = "fixed_cfg_consumer_renderer_command_script_bytes"


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _read(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<H", rom, offset)[0]


def _word(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<I", rom, offset)[0]


def _width_table(rom: bytes) -> list[tuple[int, int]]:
    base = SJIS[0]
    table = []
    for entry in range(SJIS_COUNT):
        head = int.from_bytes(rom[base + entry * 8:base + entry * 8 + 2], "little")
        table.append((head, head + rom[base + entry * 8 + 2]))
    return table


def _token_width(rom: bytes, offset: int, table: list[tuple[int, int]]) -> int:
    lead = rom[offset]
    if lead < 0x80:
        return 3 if lead == 2 else (2 if lead == 1 else 1)
    if lead <= 0x9F:
        return 2
    code = lead * 256 + rom[offset + 1]
    return 2 if any(low <= code < high for low, high in table) else 1


def _run_end(rom: bytes, offset: int, limit: int, table: list[tuple[int, int]]) -> int:
    """Scan one renderer text run and return the offset after its NUL."""
    while offset < limit:
        if rom[offset] == 0:
            return offset + 1
        width = _token_width(rom, offset, table)
        if offset + width > limit:
            raise ValueError("truncated renderer token")
        offset += width
    raise ValueError("renderer terminator missing")


def _record_end(rom: bytes, start: int, limit: int, table: list[tuple[int, int]]) -> tuple[int, list[int]]:
    """Walk one command record; return the end offset and the opcode list."""
    position = start
    seen: list[int] = []
    while position < limit:
        opcode = rom[position]
        seen.append(opcode)
        if opcode == 0:
            return position + 1, seen
        if opcode == 1:
            position += 7
        elif opcode == 3:
            position += 2
        elif opcode in (4, 12):
            position += 1
        elif opcode == 5:
            position = _run_end(rom, position + 2, limit, table)
        else:
            raise ValueError(f"unsupported opcode {opcode}")
        if position > limit:
            raise ValueError("truncated fixed command")
    raise ValueError("record terminator missing")


def _rebuild(rom: bytes, *, verify_identity: bool = True) -> dict[str, Any]:
    if verify_identity and (len(rom) != ROM_SIZE or _digest(rom) != ROM_SHA256):
        raise ValueError("ROM identity changed")
    table = _width_table(rom)
    items = []
    cursor = POOL[0]
    while cursor < POOL[1]:
        end, opcodes = _record_end(rom, cursor, POOL[1], table)
        items.append({
            "index": len(items),
            "range": [cursor, end],
            "opcodes": opcodes,
            "bytes_sha256": _digest(rom[cursor:end]),
        })
        cursor = end
    if cursor != POOL[1] or len(items) != RECORD_TOTAL:
        raise ValueError("record denominator changed")
    if any(item["opcodes"] != list(RECORD_OPCODES) for item in items):
        raise ValueError("record opcode sequence changed")
    for position in range(1, len(items)):
        if items[position - 1]["range"][1] != items[position]["range"][0]:
            raise ValueError("record coverage is not gapless")
    if _digest(rom[POOL[0]:POOL[1]]) != POOL_DIGEST:
        raise ValueError("pool identity changed")

    slots = list(struct.unpack_from(f"<{TABLE_SLOTS}I", rom, TABLE[0]))
    if slots[0] != 0:
        raise ValueError("null slot changed")
    for position, item in enumerate(items):
        if slots[position + 1] != ROM_BASE + item["range"][0]:
            raise ValueError("pointer slot does not match its record root")
    if _digest(rom[TABLE[0]:TABLE[1]]) != TABLE_DIGEST:
        raise ValueError("pointer table identity changed")

    for span, digest, label in (
        (CONSUMER, CONSUMER_DIGEST, "consumer"),
        (INTERPRETER, INTERPRETER_DIGEST, "interpreter"),
        (PARSER, PARSER_DIGEST, "parser"),
        (SJIS, SJIS_DIGEST, "sjis table"),
        (LEFT, LEFT_DIGEST, "left neighbour record"),
        (RIGHT, RIGHT_DIGEST, "right neighbour record"),
    ):
        if _digest(rom[span[0]:span[1]]) != digest:
            raise ValueError(f"{label} identity changed")
    if LEFT[1] != POOL[0] or RIGHT[0] != POOL[1]:
        raise ValueError("neighbour record boundaries changed")
    needle = struct.pack("<I", TABLE_LITERAL)
    occurrences = []
    cursor = 0
    while True:
        cursor = rom.find(needle, cursor)
        if cursor < 0:
            break
        occurrences.append(cursor)
        cursor += 1
    if occurrences != [LITERAL_POOL]:
        raise ValueError("consumer literal denominator changed")
    load_half = _read(rom, LITERAL_LOAD)
    if load_half & 0xF800 != 0x4800:
        raise ValueError("consumer literal load changed")
    literal_pool_base = (LITERAL_LOAD + 4) & ~3
    if literal_pool_base + (load_half & 0xFF) * 4 != LITERAL_POOL:
        raise ValueError("consumer literal pool alignment changed")
    if _read(rom, CALL_SITE) & 0xF800 != 0xF000:
        raise ValueError("consumer call site changed")
    if _read(rom, CALL_SITE + 2) & 0xF800 != 0xF800:
        raise ValueError("consumer call site changed")

    claim = {
        "id": "renderer-script-pointer-pool-0cea",
        "range": list(POOL),
        "primary_class": "fixed_cfg_consumer_renderer_command_script",
        "claim_kind": CLAIM_KIND,
        "bytes_sha256": POOL_DIGEST,
    }
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "records": {
            "range": list(POOL),
            "bytes_sha256": POOL_DIGEST,
            "record_count": len(items),
            "root": POOL[0],
            "terminator_offset": POOL[1],
            "opcode_sequence": list(RECORD_OPCODES),
            "record_bytes": POOL[1] - POOL[0],
            "items": items,
        },
        "pointer_table": {
            "range": list(TABLE),
            "bytes_sha256": TABLE_DIGEST,
            "slot_count": TABLE_SLOTS,
            "null_slot": 0,
            "slots": slots,
            "slot_to_record_index": {
                str(position + 1): position for position in range(len(items))
            },
        },
        "consumer_contract": {
            "literal_load_site": LITERAL_LOAD,
            "literal_pool_site": LITERAL_POOL,
            "literal_value": TABLE_LITERAL,
            "literal_occurrence_denominator": {f"0x{TABLE_LITERAL:08X}": occurrences},
            "interpreter_call_site": CALL_SITE,
            "interpreter_call_target": CALL_TARGET,
            "row_index_source": "ram 6-byte row field",
            "index_domain_guard": None,
            "identity_ranges": [
                {"range": list(span), "bytes_sha256": digest}
                for span, digest in (
                    (CONSUMER, CONSUMER_DIGEST),
                    (INTERPRETER, INTERPRETER_DIGEST),
                    (PARSER, PARSER_DIGEST),
                    (SJIS, SJIS_DIGEST),
                    (LEFT, LEFT_DIGEST),
                    (RIGHT, RIGHT_DIGEST),
                )
            ],
        },
        "promotion": {
            "promotion_batch": SCHEMA,
            "promoted_from_primary_class": "unknown",
            "claims": [claim],
            "claim_count": 1,
            "promotion_bytes": POOL[1] - POOL[0],
        },
        "scope": {
            "natural_runtime_reachability": False,
            "index_domain_closed": False,
            "row_writer_lifecycle_closed": False,
            "null_slot_semantics_closed": False,
            "all_consumer_sites_closed": False,
        },
    }


def _expected_manifest(root: Path, payload_raw: bytes, artifact: Path) -> dict[str, Any]:
    exporter = Path("tools/export_rom_renderer_script_pointer_pool_records.py")
    verifier = Path("tools/verify_rom_renderer_script_pointer_pool_records.py")
    test = Path("tests/test_export_rom_renderer_script_pointer_pool_records.py")
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _digest(payload_raw)}},
        "summary": {
            "record_count": RECORD_TOTAL,
            "pointer_table_slots": TABLE_SLOTS,
            "promotion_bytes": POOL[1] - POOL[0],
        },
        "producer": {"command": ["python3", exporter.as_posix(), "--root", ".",
                                 "--output", artifact.as_posix()]},
        "verifier": {"command": ["python3", verifier.as_posix(), "--root", ".",
                                  "--artifact", artifact.as_posix()]},
        "implementation": {
            "exporter_sha256": _digest((root / exporter).read_bytes()),
            "verifier_sha256": _digest((root / verifier).read_bytes()),
            "test_sha256": _digest((root / test).read_bytes()),
        },
    }


def verify_artifact(root: Path, artifact: Path, expected_artifact: Path | None = None) -> dict[str, Any]:
    """Verify one published artifact directory; never partially succeed."""
    errors: list[str] = []
    try:
        root = root.resolve(strict=True)
        artifact = artifact.resolve(strict=True)
        if not artifact.is_relative_to(root):
            raise ValueError("artifact escapes the repository root")
        if artifact.is_symlink():
            raise ValueError("artifact directory is a symlink")
        members = sorted(path.name for path in artifact.iterdir())
        if members != [MANIFEST_NAME, PAYLOAD_NAME]:
            raise ValueError(f"artifact members changed: {members}")
        for member in artifact.iterdir():
            if member.is_symlink():
                raise ValueError("artifact member is a symlink")
        payload_path = artifact / PAYLOAD_NAME
        manifest_path = artifact / MANIFEST_NAME
        payload_raw = payload_path.read_bytes()
        manifest_raw = manifest_path.read_bytes()
        if payload_raw != _canonical(json.loads(payload_raw.decode("utf-8"))):
            raise ValueError("payload is not canonical JSON")
        if manifest_raw != _canonical(json.loads(manifest_raw.decode("utf-8"))):
            raise ValueError("manifest is not canonical JSON")
        rom = (root / ROM_PATH).read_bytes()
        rebuilt = _rebuild(rom)
        if payload_raw != _canonical(rebuilt):
            raise ValueError("payload does not match the independent ROM rebuild")
        target = expected_artifact if expected_artifact is not None else artifact
        try:
            relative = target.resolve(strict=False).relative_to(root).as_posix()
        except ValueError:
            raise ValueError("expected artifact escapes the repository root")
        expected = _expected_manifest(root, payload_raw, Path(relative))
        if manifest_raw != _canonical(expected):
            raise ValueError("manifest does not match the expected manifest")
        return {
            "schema": VERIFY_SCHEMA,
            "verified": True,
            "errors": [],
            "artifact": relative,
            "record_count": rebuilt["records"]["record_count"],
            "promotion_bytes": rebuilt["promotion"]["promotion_bytes"],
        }
    except Exception as error:  # fail closed
        return {
            "schema": VERIFY_SCHEMA,
            "verified": False,
            "errors": [f"{type(error).__name__}: {error}"],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--artifact", type=Path)
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        dest="artifact_dir",
        help="alias of --artifact used by the proof ledger commands",
    )
    args = parser.parse_args()
    artifact = args.artifact if args.artifact is not None else args.artifact_dir
    if artifact is None:
        parser.error("one of --artifact or --artifact-dir is required")
    report = verify_artifact(args.root, artifact)
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
