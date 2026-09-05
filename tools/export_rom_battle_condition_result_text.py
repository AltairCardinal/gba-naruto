#!/usr/bin/env python3
"""Export renderer-bounded result text selected by battle-condition rows."""

from __future__ import annotations

import argparse
from collections import Counter
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


SCHEMA = "rom-battle-condition-result-text-v1"
JSON_NAME = "battle-condition-result-text.json"
BIN_NAME = "battle-condition-result-text.bin"
ROM_PATH = Path("rom/base.gba")
UPSTREAM_PATH = Path("artifacts/rom-battle-condition-records-v1/battle-condition-records.json")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
UPSTREAM_SHA256 = "5228c96a98e22e3e28ea39deaa8e13894528d6b302634944b81e1cc0493c5abf"
TABLE_START, TABLE_END = 0x594758, 0x596CCC
TABLE_SHA256 = "0d6e137011aa4e97c5b5d165f1939b7fb0b33235b9b20fceb1566b485dc35bf4"
CANDIDATE_START, CANDIDATE_END = 0x7F1D, 0x9F2E
CANDIDATE_SHA256 = "f0aaf27a655d55916d70df08890bcbfd9643c0b20e2929c0b610b78328026784"
RESULT_RENDERER = (0x77764, 0x777F6, "3fe6370ac0e3a76325d5907b2e113a403f21712bb4299af26cb970336938dc89")
BRIDGE = (0x667A0, 0x667CA, "5fcd96135c0633225308088ddfc51ca18ef151d1f317a55c70a3a7adb65044b1")
PARSER = (0x6626C, 0x66736, "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be")
SJIS_LOOKUP = (0x65E80, 0x65EB6, "242a528abb2866b87b760cabe7470db82a4f504cd697be6984333d026f2f2c8e")
SJIS_TABLE_START, SJIS_COUNT, SJIS_STRIDE = 0x53D644, 31, 8
SJIS_TABLE_SHA256 = "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"
RANGE_VECTOR_SHA256 = "7d81f7ec06a8969969305002afc307da90b7f3787f8f958fc5799c72ed844fe4"
PACKED_SHA256 = "9826a706b7c4e840117c5ff1a3a6c9d06057cac9188c66f2bd523592cf533d91"
EXPECTED_TYPES = {0: 898, 1: 155, 2: 11, 3: 18, 6: 8, 7: 16, 8: 16, 9: 6}
HANDLER_READS = {"1": [1], "2": [], "3": [1, 2], "4": [], "5": [1, 2], "6": [1], "7": [1], "8": [1], "9": [1]}
SCOPE_FALSE = (
    "inter_record_gaps_claimed", "tail_9974_9980_claimed", "script_9980_9986_claimed",
    "tail_9986_9f2e_claimed", "positions_group47_independent_provenance_claimed",
    "natural_reachability_claimed", "unicode_decoding_claimed", "editing_safety_claimed",
    "writeback_safety_claimed", "relocation_safety_claimed", "free_space_claimed",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _compact(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("ascii")


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "little")


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 4], "little")


def _bl_target(data: bytes, offset: int) -> int:
    first, second = _u16(data, offset), _u16(data, offset + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError(f"expected Thumb BL at 0x{offset:06X}")
    delta = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if delta & (1 << 22):
        delta -= 1 << 23
    return offset + 4 + delta


def _safe_file(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink():
        raise ValueError("repository input uses a symlink")
    resolved = path.resolve(strict=True)
    if root != resolved and root not in resolved.parents:
        raise ValueError("repository input escapes root")
    return resolved


def _publish_exclusive(source: Path, destination: Path) -> None:
    """Atomically publish one directory without replacing an existing path."""
    source = source.absolute()
    destination = destination.absolute()
    if source.parent != destination.parent:
        raise ValueError("exclusive publication requires a shared parent")
    parent_fd = os.open(
        source.parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            rename = libc.renameatx_np
            flag = 0x00000004  # RENAME_EXCL
        elif hasattr(libc, "renameat2"):
            rename = libc.renameat2
            flag = 0x00000001  # RENAME_NOREPLACE
        else:
            raise OSError(
                errno.ENOTSUP,
                "atomic no-replace rename is unavailable",
            )
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        if rename(
            parent_fd,
            os.fsencode(source.name),
            parent_fd,
            os.fsencode(destination.name),
            flag,
        ):
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), destination)
    finally:
        os.close(parent_fd)


def _sjis_ranges(rom: bytes) -> tuple[tuple[int, int], ...]:
    result = []
    for index in range(SJIS_COUNT):
        raw = rom[SJIS_TABLE_START + index * SJIS_STRIDE:SJIS_TABLE_START + index * SJIS_STRIDE + 3]
        lower = int.from_bytes(raw[:2], "little")
        result.append((lower, lower + raw[2]))
    return tuple(result)


def _renderer_end(rom: bytes, start: int, limit: int, sjis: tuple[tuple[int, int], ...]) -> int:
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
                raise ValueError("renderer record has truncated high byte")
            code = first << 8 | rom[cursor + 1]
            width = 2 if any(lower <= code < upper for lower, upper in sjis) else 1
        else:
            width = 1
        if cursor + width > limit:
            raise ValueError("renderer record has truncated command or pair")
        cursor += width
    raise ValueError("renderer record lacks bounded NUL terminator")


def _slice(rom: bytes, bounds: tuple[int, int, str], label: str) -> dict[str, Any]:
    start, end, digest = bounds
    raw = rom[start:end]
    if _sha(raw) != digest:
        raise ValueError(f"{label} identity changed")
    return {"range": [start, end], "gba_range": [ROM_BASE + start, ROM_BASE + end], "sha256": digest}


def _consumer_evidence(rom: bytes) -> dict[str, Any]:
    result = _slice(rom, RESULT_RENDERER, "result renderer")
    bridge = _slice(rom, BRIDGE, "renderer bridge")
    parser = _slice(rom, PARSER, "renderer parser")
    lookup = _slice(rom, SJIS_LOOKUP, "SJIS lookup")
    sjis_end = SJIS_TABLE_START + SJIS_COUNT * SJIS_STRIDE
    if _sha(rom[SJIS_TABLE_START:sjis_end]) != SJIS_TABLE_SHA256:
        raise ValueError("SJIS table identity changed")
    if _bl_target(rom, 0x777E4) != 0x667A0 or _bl_target(rom, 0x667BA) != 0x6626C:
        raise ValueError("renderer call dataflow changed")
    if _sha(rom[0x77B70:0x77B7E]) != "24889d595b578aac65fd6e11d6a8a62b31901587a3620f0233d3bb4b2ca72e73" or _sha(rom[0x77B90:0x77BA0]) != "abfbe16623eaa2663a2e814dbd9f8389b9a7b26132114b122342a69faa7c4f2b":
        raise ValueError("common arbitration payload slices changed")
    expected_halfwords = {
        0x7789C: 0x786C, 0x77924: 0x786C, 0x77940: 0x78A9,
        0x779BA: 0x7869, 0x779C0: 0x78A9, 0x779D6: 0x7869,
        0x77A5A: 0x7868, 0x77ADE: 0x7868, 0x77B10: 0x7868,
        0x77B7C: 0x6800, 0x77B9C: 0x6800,
    }
    for offset, expected in expected_halfwords.items():
        if _u16(rom, offset) != expected:
            raise ValueError(f"condition row field consumer changed at 0x{offset:06X}")
    if _bl_target(rom, 0x77B9E) != 0x77764 or _bl_target(rom, 0x77BE8) != 0x77764:
        raise ValueError("common condition payload renderer call changed")
    result["renderer_callsite"] = 0x777E4
    result["renderer_call_target"] = "0x080667A0"
    bridge["parser_callsite"] = 0x667BA
    bridge["parser_target"] = "0x0806626C"
    return {
        "handler_row_byte_reads": HANDLER_READS,
        "common_payload_loads": {
            "win": {"range": [0x77B70, 0x77B7E], "load_offset": 0x77B7C, "call_offset": 0x77BE8},
            "lose": {"range": [0x77B90, 0x77BA0], "load_offset": 0x77B9C, "call_offset": 0x77B9E},
        },
        "result_renderer": result, "bridge": bridge, "parser": parser, "sjis_lookup": lookup,
        "sjis_table": {"range": [SJIS_TABLE_START, sjis_end], "sha256": SJIS_TABLE_SHA256, "row_count": SJIS_COUNT, "row_stride": SJIS_STRIDE},
    }


def build_payload(root: Path, rom_override: bytes | None = None) -> dict[str, Any]:
    root = root.resolve(strict=True)
    rom_path = _safe_file(root, ROM_PATH)
    upstream = _safe_file(root, UPSTREAM_PATH)
    if _sha(upstream.read_bytes()) != UPSTREAM_SHA256:
        raise ValueError("upstream battle-condition artifact identity changed")
    rom = rom_path.read_bytes() if rom_override is None else rom_override
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        # Mutation tests still need to reach the precise contracts.
        if rom_override is None or len(rom) != ROM_SIZE:
            raise ValueError("ROM identity changed")
    if _sha(rom[TABLE_START:TABLE_END]) != TABLE_SHA256:
        raise ValueError("condition table identity changed")
    if _sha(rom[CANDIDATE_START:CANDIDATE_END]) != CANDIDATE_SHA256:
        raise ValueError("candidate text cluster identity changed")
    consumer = _consumer_evidence(rom)
    rows = []
    types: Counter[int] = Counter()
    for battle in range(47):
        for variant in range(3):
            base = TABLE_START + battle * 0xCC + variant * 0x44
            for group, group_offset in (("win", 4), ("lose", 0x24)):
                for slot in range(4):
                    offset = base + group_offset + slot * 8
                    condition_type, arg0, arg1, byte3, pointer = struct.unpack_from("<BBBBI", rom, offset)
                    types[condition_type] += 1
                    row = {"range": [offset, offset + 8], "battle_id": battle, "variant_index": variant, "group": group, "slot_index": slot, "condition_type": condition_type, "arg0": arg0, "arg1": arg1, "byte3_raw": byte3, "payload_word": pointer}
                    if condition_type == 0:
                        if pointer != 0:
                            raise ValueError("empty condition row has nonzero payload")
                    else:
                        if not ROM_BASE + CANDIDATE_START <= pointer < ROM_BASE + CANDIDATE_END:
                            raise ValueError("active condition payload escapes candidate cluster")
                        rows.append(row)
    if dict(sorted(types.items())) != EXPECTED_TYPES or len(rows) != 230:
        raise ValueError("complete condition slot denominator changed")
    targets = sorted({row["payload_word"] - ROM_BASE for row in rows})
    if len(targets) != 219:
        raise ValueError("condition result target denominator changed")
    sjis = _sjis_ranges(rom)
    records = []
    by_target: dict[int, list[int]] = {}
    for index, row in enumerate(rows):
        by_target.setdefault(row["payload_word"] - ROM_BASE, []).append(index)
    for target in targets:
        end = _renderer_end(rom, target, CANDIDATE_END, sjis)
        records.append({"target": ROM_BASE + target, "range": [target, end], "size": end - target, "sha256": _sha(rom[target:end]), "source_row_indices": by_target[target]})
    ranges = [record["range"] for record in records]
    if any(left[1] > right[0] for left, right in zip(ranges, ranges[1:])):
        raise ValueError("renderer result records overlap")
    packed = b"".join(rom[start:end] for start, end in ranges)
    gaps = sum(right[0] - left[1] for left, right in zip(ranges, ranges[1:]))
    if _sha(_compact(ranges)) != RANGE_VECTOR_SHA256 or _sha(packed) != PACKED_SHA256 or len(packed) != 3961 or gaps != 2782 or ranges[-1] != [0x9963, 0x9974]:
        raise ValueError("renderer result record denominator changed")
    if _sha(rom) != ROM_SHA256:
        raise ValueError("ROM identity changed")
    promotion_claims = [
        {
            "id": f"battle-condition-result-text-{index:03d}",
            "range": record["range"],
            "primary_class": "battle_condition_result_renderer_text",
            "claim_kind": "battle_condition_result_renderer_consumed_record_bytes",
            "bytes_sha256": record["sha256"],
        }
        for index, record in enumerate(records)
    ]
    implementation = {}
    for role, relative in (("exporter", Path("tools/export_rom_battle_condition_result_text.py")), ("verifier", Path("tools/verify_rom_battle_condition_result_text.py")), ("tests", Path("tests/test_export_rom_battle_condition_result_text.py"))):
        path = _safe_file(root, relative)
        implementation[role] = {"path": relative.as_posix(), "sha256": _sha(path.read_bytes())}
    limitations = [
        "Only the 219 renderer-consumed NUL records selected by the complete physical condition-row denominator are promoted.",
        "The 2,782 inter-record gap bytes and the ranges [0x9974,0x9980), [0x9980,0x9986), and [0x9986,0x9F2E) are not promoted.",
        "Positions group 47 begins at 0x594758 and is a physical alias of the condition table; its pointer-looking aux words are not independent provenance.",
        "Natural reachability, Unicode decoding, editing, writeback, relocation, and free-space safety remain unclaimed.",
    ]
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": _sha(rom)},
        "upstream": {"path": UPSTREAM_PATH.as_posix(), "sha256": UPSTREAM_SHA256, "used_as_identity_only": True},
        "condition_denominator": {"table_range": [TABLE_START, TABLE_END], "table_sha256": TABLE_SHA256, "battle_count": 47, "variant_count": 3, "group_count": 2, "slots_per_group": 4, "slot_count": 1128, "type_counts": {str(key): value for key, value in sorted(types.items())}, "active_rows": rows},
        "consumer_evidence": consumer,
        "records": records,
        "promotion": {
            "promotion_bytes": len(packed),
            "claims": promotion_claims,
        },
        "records_range_vector_sha256": RANGE_VECTOR_SHA256,
        "packed_bytes_sha256": PACKED_SHA256,
        "summary": {"condition_slot_count": 1128, "empty_slot_count": 898, "active_slot_count": 230, "distinct_target_count": 219, "record_count": 219, "record_bytes": 3961, "inter_record_gap_bytes_unclaimed": 2782, "parse_failure_count": 0},
        "scope": {field: False for field in SCOPE_FALSE},
        "limitations": limitations,
        "implementation": implementation,
    }


def export_artifact(root: Path, output_dir: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    output = output_dir.absolute()
    if output == root:
        raise ValueError("output cannot be repository root")
    cursor = Path(output.anchor)
    for part in output.parts[1:]:
        cursor /= part
        if cursor.is_symlink() and cursor not in {Path("/tmp"), Path("/var")}:
            raise ValueError("output path uses symlink")
    if output.exists():
        raise ValueError("output exists or is non-empty/foreign; publication is no-overwrite")
    payload = build_payload(root)
    rom = _safe_file(root, ROM_PATH).read_bytes()
    packed = b"".join(rom[a:b] for a, b in (record["range"] for record in payload["records"]))
    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{SCHEMA}-", dir=parent))
    committed = False
    try:
        (temporary / JSON_NAME).write_bytes(_canonical(payload))
        (temporary / BIN_NAME).write_bytes(packed)
        manifest = {"schema": SCHEMA, "files": {JSON_NAME: _sha((temporary / JSON_NAME).read_bytes()), BIN_NAME: _sha(packed)}, "limitations": payload["limitations"], "implementation": payload["implementation"]}
        (temporary / "manifest.json").write_bytes(_canonical(manifest))
        try:
            _publish_exclusive(temporary, output)
        except FileExistsError as error:
            raise ValueError("output exists; publication is no-overwrite") from error
        committed = True
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except Exception:
        if not committed and temporary.exists():
            for child in temporary.iterdir(): child.unlink()
            temporary.rmdir()
        raise
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    payload = export_artifact(args.root, args.out_dir)
    print(json.dumps(payload["summary"], sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
