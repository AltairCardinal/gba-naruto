#!/usr/bin/env python3
"""Export the renderer script records behind the 28-slot pointer pool at 0x53DF00.

The pool at 0x0CEA..0x12F0 was already closed by the accepted renderer-script
grammar: 27 records, no gaps, no overlaps, all with the same opcode sequence.
What was missing was a contract that binds the records to their consumer.  The
consumer is a 28-slot ROM pointer table whose slot 0 is null and whose slots
1..27 point at the 27 record roots in order; the interpreter call site is
0x071340 -> 0x067158.

The records themselves are unknown bytes in the live coverage ledger, so this
package is the promotion candidate for 1,542 bytes.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


SCHEMA = "rom-renderer-script-pointer-pool-records-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_BASE = 0x08000000
OFFICIAL = Path("artifacts/rom-renderer-script-pointer-pool-records-v1")
PAYLOAD_NAME = "rom-renderer-script-pointer-pool-records.json"
MANIFEST_NAME = "manifest.json"

POOL_RANGE = (0x0CEA, 0x12F0)
POOL_SHA256 = "1730e92b4cc9ace8f484b61aedcbd2e670b45b522bd5807bdf72fd9cc03595cf"
POOL_ROOT = 0x0CEA
POOL_END = 0x12F0
RECORD_COUNT = 27
RECORD_OPCODES = [1, 5, 4, 12, 3, 0]

POINTER_TABLE_RANGE = (0x53DF00, 0x53DF70)
POINTER_TABLE_SHA256 = "f18680f6e461a60f54373e7377c580e9966e7f9be9966a9ab1d1a0eefa7451bc"
POINTER_TABLE_SLOTS = 28
POINTER_TABLE_LITERAL = 0x0853DF00

CONSUMER_RANGE = (0x0712D0, 0x071350)
CONSUMER_SHA256 = "48e9363eeae7ca589654a66b5f963af9e4f4868facfc95cce8b2b878fedf882f"
CONSUMER_LITERAL_LOAD_SITE = 0x0712EE
CONSUMER_LITERAL_POOL_SITE = 0x071350
CONSUMER_CALL_SITE = 0x071340
CONSUMER_CALL_TARGET = 0x067158

INTERPRETER_RANGE = (0x067158, 0x06836E)
INTERPRETER_SHA256 = "211812743de17ef5158ef63bd52deb3271c962b9119bf74f1bbd458b6bec96dd"
PARSER_RANGE = (0x06626C, 0x066736)
PARSER_SHA256 = "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"
SJIS_RANGE = (0x53D644, 0x53D73C)
SJIS_SHA256 = "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"
SJIS_ENTRY_COUNT = 31

LEFT_NEIGHBOUR_RANGE = (0x0CC7, 0x0CEA)
LEFT_NEIGHBOUR_SHA256 = "bc6ed5847e9ae46dece7f4e309c0dcaf02fcfd6ab0159e36ca8072bb010f8cd2"
RIGHT_NEIGHBOUR_RANGE = (0x12F0, 0x12FA)
RIGHT_NEIGHBOUR_SHA256 = "3ce42db81ef9c29faa251029044baca89172709af872513b4629e4b0b225f4bb"

PRIMARY_CLASS = "fixed_cfg_consumer_renderer_command_script"
CLAIM_KIND = "fixed_cfg_consumer_renderer_command_script_bytes"

OPCODE_WIDTHS = {1: 7, 3: 2, 4: 1, 12: 1}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _publish_exclusive(source: Path, destination: Path) -> None:
    """Atomically publish one directory without replacing any destination."""
    source = source.absolute()
    destination = destination.absolute()
    if source.parent != destination.parent:
        raise ValueError("exclusive publication requires a shared parent")
    parent_fd = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            rename, flag = libc.renameatx_np, 0x00000004  # RENAME_EXCL
        elif hasattr(libc, "renameat2"):
            rename, flag = libc.renameat2, 0x00000001  # RENAME_NOREPLACE
        else:
            raise OSError(errno.ENOTSUP, "atomic no-replace rename is unavailable")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                           ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(parent_fd, os.fsencode(source.name), parent_fd,
                  os.fsencode(destination.name), flag):
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), destination)
    finally:
        os.close(parent_fd)


def _safe_file(root: Path, relative: Path) -> Path:
    base = root.resolve(strict=True)
    cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"unsafe input path: {relative}")
    result = cursor.resolve(strict=True)
    if not result.is_relative_to(base) or not result.is_file():
        raise ValueError(f"unsafe input path: {relative}")
    return result


def _pin(rom: bytes, span: tuple[int, int], digest: str, label: str) -> None:
    if _sha(rom[span[0]:span[1]]) != digest:
        raise ValueError(f"{label} identity changed")


def _all_occurrences(raw: bytes, needle: bytes) -> list[int]:
    result: list[int] = []
    cursor = 0
    while True:
        cursor = raw.find(needle, cursor)
        if cursor < 0:
            return result
        result.append(cursor)
        cursor += 1


def _sjis_ranges(rom: bytes) -> tuple[tuple[int, int], ...]:
    """Read the 31-entry SJIS width table that fixes renderer text widths."""
    base = SJIS_RANGE[0]
    ranges = []
    for index in range(SJIS_ENTRY_COUNT):
        start = int.from_bytes(rom[base + index * 8:base + index * 8 + 2], "little")
        span = rom[base + index * 8 + 2]
        ranges.append((start, start + span))
    return tuple(ranges)


def _text_end(rom: bytes, start: int, limit: int, ranges: tuple[tuple[int, int], ...]) -> int:
    """Return the offset just past the NUL that closes one renderer text run."""
    cursor = start
    while cursor < limit:
        first = rom[cursor]
        if first == 0:
            return cursor + 1
        if first == 1:
            width = 2
        elif first == 2:
            width = 3
        elif 0x80 <= first <= 0x9F:
            width = 2
        elif first >= 0xA0:
            if cursor + 1 >= limit:
                raise ValueError("truncated renderer pair")
            code = (first << 8) | rom[cursor + 1]
            width = 2 if any(low <= code < high for low, high in ranges) else 1
        else:
            width = 1
        if cursor + width > limit:
            raise ValueError("truncated renderer token")
        cursor += width
    raise ValueError("renderer terminator missing")


def _parse_record(rom: bytes, start: int, limit: int,
                  ranges: tuple[tuple[int, int], ...]) -> tuple[int, list[int]]:
    """Parse one renderer command record and return its end and opcode list."""
    cursor = start
    opcodes: list[int] = []
    while cursor < limit:
        opcode = rom[cursor]
        opcodes.append(opcode)
        if opcode == 0:
            return cursor + 1, opcodes
        if opcode in OPCODE_WIDTHS:
            cursor += OPCODE_WIDTHS[opcode]
        elif opcode == 5:
            if cursor + 2 > limit:
                raise ValueError("truncated renderer command")
            cursor = _text_end(rom, cursor + 2, limit, ranges)
        else:
            raise ValueError(f"unsupported opcode {opcode}")
        if cursor > limit:
            raise ValueError("truncated fixed command")
    raise ValueError("record terminator missing")


def _parse_pool(rom: bytes) -> dict[str, Any]:
    """Chain-parse the pool and require an exact, gapless 27-record cover."""
    ranges = _sjis_ranges(rom)
    items: list[dict[str, Any]] = []
    cursor = POOL_ROOT
    while cursor < POOL_END:
        end, opcodes = _parse_record(rom, cursor, POOL_END, ranges)
        if end > POOL_END:
            raise ValueError("record crosses the pool end")
        items.append({
            "index": len(items),
            "range": [cursor, end],
            "opcodes": opcodes,
            "bytes_sha256": _sha(rom[cursor:end]),
        })
        cursor = end
    if cursor != POOL_END:
        raise ValueError("pool terminator offset changed")
    if len(items) != RECORD_COUNT:
        raise ValueError("record denominator changed")
    for index, item in enumerate(items):
        if item["opcodes"] != RECORD_OPCODES:
            raise ValueError("record opcode sequence changed")
        if index and items[index - 1]["range"][1] != item["range"][0]:
            raise ValueError("record coverage is not gapless")
    if _sha(rom[POOL_RANGE[0]:POOL_RANGE[1]]) != POOL_SHA256:
        raise ValueError("pool identity changed")
    return {
        "range": list(POOL_RANGE),
        "bytes_sha256": POOL_SHA256,
        "record_count": len(items),
        "root": POOL_ROOT,
        "terminator_offset": POOL_END,
        "opcode_sequence": list(RECORD_OPCODES),
        "record_bytes": POOL_END - POOL_ROOT,
        "items": items,
    }


def _pointer_table(rom: bytes, records: dict[str, Any]) -> dict[str, Any]:
    """Read the 28-slot table and require slots 1..27 to match the records."""
    slots = list(struct.unpack_from(f"<{POINTER_TABLE_SLOTS}I", rom, POINTER_TABLE_RANGE[0]))
    if slots[0] != 0:
        raise ValueError("null slot changed")
    roots = [item["range"][0] for item in records["items"]]
    for index, root in enumerate(roots):
        if slots[index + 1] != ROM_BASE + root:
            raise ValueError("pointer slot does not match its record root")
    if _sha(rom[POINTER_TABLE_RANGE[0]:POINTER_TABLE_RANGE[1]]) != POINTER_TABLE_SHA256:
        raise ValueError("pointer table identity changed")
    return {
        "range": list(POINTER_TABLE_RANGE),
        "bytes_sha256": POINTER_TABLE_SHA256,
        "slot_count": POINTER_TABLE_SLOTS,
        "null_slot": 0,
        "slots": slots,
        "slot_to_record_index": {str(index + 1): index for index in range(len(roots))},
    }


def _consumer_contract(rom: bytes) -> dict[str, Any]:
    _pin(rom, CONSUMER_RANGE, CONSUMER_SHA256, "consumer")
    _pin(rom, INTERPRETER_RANGE, INTERPRETER_SHA256, "interpreter")
    _pin(rom, PARSER_RANGE, PARSER_SHA256, "parser")
    _pin(rom, SJIS_RANGE, SJIS_SHA256, "sjis table")
    _pin(rom, LEFT_NEIGHBOUR_RANGE, LEFT_NEIGHBOUR_SHA256, "left neighbour record")
    _pin(rom, RIGHT_NEIGHBOUR_RANGE, RIGHT_NEIGHBOUR_SHA256, "right neighbour record")
    if LEFT_NEIGHBOUR_RANGE[1] != POOL_ROOT or RIGHT_NEIGHBOUR_RANGE[0] != POOL_END:
        raise ValueError("neighbour record boundaries changed")
    occurrences = _all_occurrences(rom, struct.pack("<I", POINTER_TABLE_LITERAL))
    if occurrences != [CONSUMER_LITERAL_POOL_SITE]:
        raise ValueError("consumer literal denominator changed")
    if struct.unpack_from("<I", rom, CONSUMER_LITERAL_POOL_SITE)[0] != POINTER_TABLE_LITERAL:
        raise ValueError("consumer literal value changed")
    # The literal load is a Thumb LDR whose PC-relative pool must land exactly
    # on the single occurrence of the table literal.
    half = struct.unpack_from("<H", rom, CONSUMER_LITERAL_LOAD_SITE)[0]
    if half & 0xF800 != 0x4800:
        raise ValueError("consumer literal load changed")
    pool_base = (CONSUMER_LITERAL_LOAD_SITE + 4) & ~3
    if pool_base + (half & 0xFF) * 4 != CONSUMER_LITERAL_POOL_SITE:
        raise ValueError("consumer literal pool alignment changed")
    # The interpreter call is a Thumb BL whose target is the known entry point.
    if struct.unpack_from("<H", rom, CONSUMER_CALL_SITE)[0] & 0xF800 != 0xF000:
        raise ValueError("consumer call site changed")
    if struct.unpack_from("<H", rom, CONSUMER_CALL_SITE + 2)[0] & 0xF800 != 0xF800:
        raise ValueError("consumer call site changed")
    return {
        "literal_load_site": CONSUMER_LITERAL_LOAD_SITE,
        "literal_pool_site": CONSUMER_LITERAL_POOL_SITE,
        "literal_value": POINTER_TABLE_LITERAL,
        "literal_occurrence_denominator": {
            f"0x{POINTER_TABLE_LITERAL:08X}": occurrences,
        },
        "interpreter_call_site": CONSUMER_CALL_SITE,
        "interpreter_call_target": CONSUMER_CALL_TARGET,
        "row_index_source": "ram 6-byte row field",
        "index_domain_guard": None,
        "identity_ranges": [
            {"range": list(span), "bytes_sha256": digest}
            for span, digest in (
                (CONSUMER_RANGE, CONSUMER_SHA256),
                (INTERPRETER_RANGE, INTERPRETER_SHA256),
                (PARSER_RANGE, PARSER_SHA256),
                (SJIS_RANGE, SJIS_SHA256),
                (LEFT_NEIGHBOUR_RANGE, LEFT_NEIGHBOUR_SHA256),
                (RIGHT_NEIGHBOUR_RANGE, RIGHT_NEIGHBOUR_SHA256),
            )
        ],
    }


def _build_from_rom(root: Path, rom: bytes, *, verify_identity: bool = True) -> dict[str, Any]:
    if verify_identity and (len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256):
        raise ValueError("ROM identity changed")
    records = _parse_pool(rom)
    table = _pointer_table(rom, records)
    consumer = _consumer_contract(rom)
    claim = {
        "id": "renderer-script-pointer-pool-0cea",
        "range": list(POOL_RANGE),
        "primary_class": PRIMARY_CLASS,
        "claim_kind": CLAIM_KIND,
        "bytes_sha256": POOL_SHA256,
    }
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "records": records,
        "pointer_table": table,
        "consumer_contract": consumer,
        "promotion": {
            "promotion_batch": SCHEMA,
            "promoted_from_primary_class": "unknown",
            "claims": [claim],
            "claim_count": 1,
            "promotion_bytes": POOL_RANGE[1] - POOL_RANGE[0],
        },
        "scope": {
            "natural_runtime_reachability": False,
            "index_domain_closed": False,
            "row_writer_lifecycle_closed": False,
            "null_slot_semantics_closed": False,
            "all_consumer_sites_closed": False,
        },
    }


def build_payload(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    return _build_from_rom(root, _safe_file(root, ROM_PATH).read_bytes())


def export_artifact(root: Path, output: Path) -> Path:
    root = root.resolve(strict=True)
    lexical = output if output.is_absolute() else root / output
    for parent in [lexical, *lexical.parents]:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("output has symlink ancestor")
    output = lexical.resolve(strict=False)
    if not output.is_relative_to(root) or output.exists():
        raise FileExistsError("output exists or escapes root")
    payload_raw = _canonical(build_payload(root))
    exporter = Path("tools/export_rom_renderer_script_pointer_pool_records.py")
    verifier = Path("tools/verify_rom_renderer_script_pointer_pool_records.py")
    test = Path("tests/test_export_rom_renderer_script_pointer_pool_records.py")
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}},
        "summary": {
            "record_count": RECORD_COUNT,
            "pointer_table_slots": POINTER_TABLE_SLOTS,
            "promotion_bytes": POOL_RANGE[1] - POOL_RANGE[0],
        },
        "producer": {"command": ["python3", exporter.as_posix(), "--root", ".",
                                 "--output", output.relative_to(root).as_posix()]},
        "verifier": {"command": ["python3", verifier.as_posix(), "--root", ".",
                                  "--artifact", output.relative_to(root).as_posix()]},
        "implementation": {
            "exporter_sha256": _sha(_safe_file(root, exporter).read_bytes()),
            "verifier_sha256": _sha(_safe_file(root, verifier).read_bytes()),
            "test_sha256": _sha(_safe_file(root, test).read_bytes()),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".pointer-pool-") as directory:
        stage = Path(directory)
        (stage / PAYLOAD_NAME).write_bytes(payload_raw)
        (stage / MANIFEST_NAME).write_bytes(_canonical(manifest))
        from tools.verify_rom_renderer_script_pointer_pool_records import verify_artifact
        report = verify_artifact(root, stage, expected_artifact=output)
        if not report["verified"]:
            raise ValueError(report["errors"])
        _publish_exclusive(stage, output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export_artifact(args.root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
