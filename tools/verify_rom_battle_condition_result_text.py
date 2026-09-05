#!/usr/bin/env python3
"""Independently verify the battle-condition result renderer-text artifact."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


SCHEMA = "rom-battle-condition-result-text-v1"
VERIFY_SCHEMA = "rom-battle-condition-result-text-verification-v1"
JSON_NAME = "battle-condition-result-text.json"
BIN_NAME = "battle-condition-result-text.bin"
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
UPSTREAM = Path("artifacts/rom-battle-condition-records-v1/battle-condition-records.json")
UPSTREAM_SHA256 = "5228c96a98e22e3e28ea39deaa8e13894528d6b302634944b81e1cc0493c5abf"
TABLE = (0x594758, 0x596CCC)
TABLE_SHA256 = "0d6e137011aa4e97c5b5d165f1939b7fb0b33235b9b20fceb1566b485dc35bf4"
CANDIDATE = (0x7F1D, 0x9F2E)
CANDIDATE_SHA256 = "f0aaf27a655d55916d70df08890bcbfd9643c0b20e2929c0b610b78328026784"
RANGE_SHA256 = "7d81f7ec06a8969969305002afc307da90b7f3787f8f958fc5799c72ed844fe4"
PACKED_SHA256 = "9826a706b7c4e840117c5ff1a3a6c9d06057cac9188c66f2bd523592cf533d91"
TYPE_COUNTS = {0: 898, 1: 155, 2: 11, 3: 18, 6: 8, 7: 16, 8: 16, 9: 6}
HANDLER_READS = {"1": [1], "2": [], "3": [1, 2], "4": [], "5": [1, 2], "6": [1], "7": [1], "8": [1], "9": [1]}
FALSE_SCOPE = {
    "inter_record_gaps_claimed", "tail_9974_9980_claimed", "script_9980_9986_claimed",
    "tail_9986_9f2e_claimed", "positions_group47_independent_provenance_claimed",
    "natural_reachability_claimed", "unicode_decoding_claimed", "editing_safety_claimed",
    "writeback_safety_claimed", "relocation_safety_claimed", "free_space_claimed",
}
SLICES = {
    "result_renderer": (0x77764, 0x777F6, "3fe6370ac0e3a76325d5907b2e113a403f21712bb4299af26cb970336938dc89"),
    "bridge": (0x667A0, 0x667CA, "5fcd96135c0633225308088ddfc51ca18ef151d1f317a55c70a3a7adb65044b1"),
    "parser": (0x6626C, 0x66736, "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"),
    "sjis_lookup": (0x65E80, 0x65EB6, "242a528abb2866b87b760cabe7470db82a4f504cd697be6984333d026f2f2c8e"),
}
SJIS_START, SJIS_COUNT, SJIS_STRIDE = 0x53D644, 31, 8
SJIS_SHA256 = "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _compact(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("ascii")


def _u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise ValueError("halfword escapes ROM")
    return int.from_bytes(data[offset:offset + 2], "little")


def _branch(data: bytes, offset: int) -> int:
    first, second = _u16(data, offset), _u16(data, offset + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError("consumer call is not Thumb BL")
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return offset + 4 + displacement


def _safe(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink():
        raise ValueError("input symlink")
    resolved = path.resolve(strict=True)
    if root != resolved and root not in resolved.parents:
        raise ValueError("input escapes root")
    return resolved


def _character_ranges(rom: bytes) -> tuple[tuple[int, int], ...]:
    ranges = []
    for index in range(SJIS_COUNT):
        offset = SJIS_START + index * SJIS_STRIDE
        lower = int.from_bytes(rom[offset:offset + 2], "little")
        ranges.append((lower, lower + rom[offset + 2]))
    return tuple(ranges)


def _parse_end(rom: bytes, start: int, limit: int, character_ranges: tuple[tuple[int, int], ...]) -> int:
    cursor = start
    while cursor < limit:
        value = rom[cursor]
        if value == 0:
            return cursor + 1
        if value == 1:
            width = 2
        elif value == 2:
            width = 3
        elif 0x80 <= value <= 0x9F:
            width = 2
        elif value >= 0xA0:
            if cursor + 1 >= limit:
                raise ValueError("truncated renderer pair")
            code = value << 8 | rom[cursor + 1]
            width = 2 if any(low <= code < high for low, high in character_ranges) else 1
        else:
            width = 1
        if cursor + width > limit:
            raise ValueError("truncated renderer token")
        cursor += width
    raise ValueError("missing renderer terminator")


def rebuild_expected(root: Path, rom_override: bytes | None = None) -> dict[str, Any]:
    root = root.resolve(strict=True)
    rom_path = _safe(root, Path("rom/base.gba"))
    upstream_path = _safe(root, UPSTREAM)
    if _sha(upstream_path.read_bytes()) != UPSTREAM_SHA256:
        raise ValueError("upstream identity mismatch")
    rom = rom_path.read_bytes() if rom_override is None else rom_override
    if len(rom) != ROM_SIZE:
        raise ValueError("ROM size mismatch")
    if _sha(rom[TABLE[0]:TABLE[1]]) != TABLE_SHA256:
        raise ValueError("raw condition denominator mismatch")
    if _sha(rom[CANDIDATE[0]:CANDIDATE[1]]) != CANDIDATE_SHA256:
        raise ValueError("raw candidate cluster mismatch")
    evidence: dict[str, Any] = {}
    for name, (start, end, digest) in SLICES.items():
        if _sha(rom[start:end]) != digest:
            raise ValueError(f"{name} mismatch")
        evidence[name] = {"range": [start, end], "gba_range": [ROM_BASE + start, ROM_BASE + end], "sha256": digest}
    sjis_end = SJIS_START + SJIS_COUNT * SJIS_STRIDE
    if _sha(rom[SJIS_START:sjis_end]) != SJIS_SHA256:
        raise ValueError("SJIS table mismatch")
    if _branch(rom, 0x777E4) != 0x667A0 or _branch(rom, 0x667BA) != 0x6626C:
        raise ValueError("result renderer to parser flow mismatch")
    if _sha(rom[0x77B70:0x77B7E]) != "24889d595b578aac65fd6e11d6a8a62b31901587a3620f0233d3bb4b2ca72e73" or _sha(rom[0x77B90:0x77BA0]) != "abfbe16623eaa2663a2e814dbd9f8389b9a7b26132114b122342a69faa7c4f2b":
        raise ValueError("raw arbitration payload slices mismatch")
    loads = {0x7789C: 0x786C, 0x77924: 0x786C, 0x77940: 0x78A9, 0x779BA: 0x7869, 0x779C0: 0x78A9, 0x779D6: 0x7869, 0x77A5A: 0x7868, 0x77ADE: 0x7868, 0x77B10: 0x7868, 0x77B7C: 0x6800, 0x77B9C: 0x6800}
    if any(_u16(rom, offset) != halfword for offset, halfword in loads.items()):
        raise ValueError("handler row read footprint mismatch")
    if _branch(rom, 0x77B9E) != 0x77764 or _branch(rom, 0x77BE8) != 0x77764:
        raise ValueError("arbitration payload call mismatch")
    counts: Counter[int] = Counter()
    active = []
    table_start = TABLE[0]
    for battle_id in range(47):
        for variant_index in range(3):
            variant = table_start + battle_id * 0xCC + variant_index * 0x44
            for group, group_offset in (("win", 4), ("lose", 0x24)):
                for slot_index in range(4):
                    offset = variant + group_offset + slot_index * 8
                    condition_type, arg0, arg1, byte3, pointer = struct.unpack_from("<BBBBI", rom, offset)
                    counts[condition_type] += 1
                    if condition_type == 0:
                        if pointer:
                            raise ValueError("empty slot payload mismatch")
                        continue
                    if not ROM_BASE + CANDIDATE[0] <= pointer < ROM_BASE + CANDIDATE[1]:
                        raise ValueError("active payload pointer escapes cluster")
                    active.append({"range": [offset, offset + 8], "battle_id": battle_id, "variant_index": variant_index, "group": group, "slot_index": slot_index, "condition_type": condition_type, "arg0": arg0, "arg1": arg1, "byte3_raw": byte3, "payload_word": pointer})
    if dict(sorted(counts.items())) != TYPE_COUNTS or len(active) != 230:
        raise ValueError("slot/type denominator mismatch")
    targets = sorted({row["payload_word"] - ROM_BASE for row in active})
    if len(targets) != 219:
        raise ValueError("distinct target denominator mismatch")
    source_indices: dict[int, list[int]] = {}
    for index, row in enumerate(active):
        source_indices.setdefault(row["payload_word"] - ROM_BASE, []).append(index)
    grammar = _character_ranges(rom)
    records = []
    for target in targets:
        end = _parse_end(rom, target, CANDIDATE[1], grammar)
        records.append({"target": ROM_BASE + target, "range": [target, end], "size": end - target, "sha256": _sha(rom[target:end]), "source_row_indices": source_indices[target]})
    ranges = [record["range"] for record in records]
    if any(left[1] > right[0] for left, right in zip(ranges, ranges[1:])):
        raise ValueError("records overlap")
    packed = b"".join(rom[start:end] for start, end in ranges)
    gaps = sum(right[0] - left[1] for left, right in zip(ranges, ranges[1:]))
    if _sha(_compact(ranges)) != RANGE_SHA256 or _sha(packed) != PACKED_SHA256 or len(packed) != 3961 or gaps != 2782 or ranges[-1] != [0x9963, 0x9974]:
        raise ValueError("record range/byte denominator mismatch")
    promotion = {
        "promotion_bytes": len(packed),
        "claims": [
            {
                "id": f"battle-condition-result-text-{index:03d}",
                "range": record["range"],
                "primary_class": "battle_condition_result_renderer_text",
                "claim_kind": "battle_condition_result_renderer_consumed_record_bytes",
                "bytes_sha256": record["sha256"],
            }
            for index, record in enumerate(records)
        ],
    }
    # Full ROM identity is checked after domain-specific failures remain observable.
    if _sha(rom) != ROM_SHA256:
        raise ValueError("ROM identity mismatch")
    evidence["result_renderer"].update({"renderer_callsite": 0x777E4, "renderer_call_target": "0x080667A0"})
    evidence["bridge"].update({"parser_callsite": 0x667BA, "parser_target": "0x0806626C"})
    consumer = {"handler_row_byte_reads": HANDLER_READS, "common_payload_loads": {"win": {"range": [0x77B70, 0x77B7E], "load_offset": 0x77B7C, "call_offset": 0x77BE8}, "lose": {"range": [0x77B90, 0x77BA0], "load_offset": 0x77B9C, "call_offset": 0x77B9E}}, "result_renderer": evidence["result_renderer"], "bridge": evidence["bridge"], "parser": evidence["parser"], "sjis_lookup": evidence["sjis_lookup"], "sjis_table": {"range": [SJIS_START, sjis_end], "sha256": SJIS_SHA256, "row_count": SJIS_COUNT, "row_stride": SJIS_STRIDE}}
    return {"rom": rom, "active": active, "counts": counts, "records": records, "ranges": ranges, "packed": packed, "consumer": consumer, "gaps": gaps, "promotion": promotion}


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors = []
    try:
        root = root.resolve(strict=True)
        artifact = artifact_dir.resolve(strict=True)
        expected = rebuild_expected(root)
        members = {path.name for path in artifact.iterdir() if path.is_file()}
        if members != {JSON_NAME, BIN_NAME, "manifest.json"}:
            raise ValueError("artifact file set mismatch")
        payload_raw = (artifact / JSON_NAME).read_bytes()
        payload = json.loads(payload_raw)
        binary = (artifact / BIN_NAME).read_bytes()
        manifest = json.loads((artifact / "manifest.json").read_bytes())
        if binary != expected["packed"]:
            raise ValueError("packed binary mismatch")
        if payload.get("schema") != SCHEMA or payload.get("records") != expected["records"] or payload.get("consumer_evidence") != expected["consumer"]:
            raise ValueError("payload reconstruction mismatch")
        if payload.get("promotion") != expected["promotion"]:
            raise ValueError("payload promotion claims mismatch")
        denominator = payload.get("condition_denominator", {})
        if denominator.get("active_rows") != expected["active"] or denominator.get("slot_count") != 1128 or denominator.get("type_counts") != {str(key): value for key, value in sorted(TYPE_COUNTS.items())}:
            raise ValueError("payload condition denominator mismatch")
        summary = payload.get("summary")
        expected_summary = {"condition_slot_count": 1128, "empty_slot_count": 898, "active_slot_count": 230, "distinct_target_count": 219, "record_count": 219, "record_bytes": 3961, "inter_record_gap_bytes_unclaimed": 2782, "parse_failure_count": 0}
        if summary != expected_summary or payload.get("records_range_vector_sha256") != RANGE_SHA256 or payload.get("packed_bytes_sha256") != PACKED_SHA256:
            raise ValueError("payload summary mismatch")
        scope = payload.get("scope")
        if not isinstance(scope, dict) or set(scope) != FALSE_SCOPE or any(scope.values()):
            raise ValueError("scope/nonclaims mismatch")
        limitations = payload.get("limitations")
        if not isinstance(limitations, list) or not any("physical alias" in item for item in limitations):
            raise ValueError("positions alias limitation missing")
        implementation = payload.get("implementation")
        if not isinstance(implementation, dict):
            raise ValueError("implementation identities missing")
        for role, relative in (("exporter", "tools/export_rom_battle_condition_result_text.py"), ("verifier", "tools/verify_rom_battle_condition_result_text.py"), ("tests", "tests/test_export_rom_battle_condition_result_text.py")):
            item = implementation.get(role, {})
            if item != {"path": relative, "sha256": _sha(_safe(root, Path(relative)).read_bytes())}:
                raise ValueError("implementation identity mismatch")
        if manifest != {"schema": SCHEMA, "files": {JSON_NAME: _sha(payload_raw), BIN_NAME: _sha(binary)}, "limitations": limitations, "implementation": implementation}:
            raise ValueError("manifest mismatch")
    except Exception as error:
        errors.append(f"{type(error).__name__}: {error}")
    return {"schema": VERIFY_SCHEMA, "artifact_schema": SCHEMA, "verified": not errors, "errors": errors, "summary": None if errors else payload["summary"], "promotion_bytes": None if errors else len(expected["packed"]), "promotion_claim_count": None if errors else len(expected["promotion"]["claims"]), "range_vector_sha256": None if errors else RANGE_SHA256, "packed_bytes_sha256": None if errors else PACKED_SHA256}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    raw = _canonical(report)
    if args.output:
        args.output.write_bytes(raw)
    print(raw.decode(), end="")
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
