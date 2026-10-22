#!/usr/bin/env python3
"""Independently verify the fixed animation descriptor group artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
from typing import Any


SCHEMA = "rom-fixed-animation-descriptor-groups-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PAYLOAD_NAME = "rom-fixed-animation-descriptor-groups.json"
MANIFEST_NAME = "manifest.json"
TABLE_RANGE = (0x12D574, 0x12D9E4)
TABLE_SHA256 = "7ec09a078b86ee22ca7d7ae1be34130eb19bbdf8d0266769d23dd919ce493a8d"
IDENTITIES = (
    ((0x071E74, 0x071F00), "2f57b17a42eaec539eeb532e0d481c89740a525a1ed382d7ff6175c8921e3afc", "caller"),
    ((0x0626B4, 0x062766), "09cd85fb8fcdc85751019c67ef6b91d6d3d64c1fbeb0b0496e270234f846d804", "allocator"),
    ((0x062924, 0x062A0A), "23ead2fcc1537d16a632bf68dbccdb96a142af170410f862baaf4c1d750e0a18", "renderer"),
    ((0x0631F6, 0x063208), "79cb19c28c7f5a75ed323f99c837e131c0e11dd06c91f422e60ac9ff859e8f44", "renderer descriptor-step"),
    ((0x063238, 0x0632BA), "b6dc39ac66ecaac48e16f37406bab7e579362759e9e3570e9c6fa9e24ec0ab23", "renderer advance"),
)
LITERALS = {0x0812D964: [0x071F4C], 0x0812D9D4: [0x071F50]}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


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


def _occurrences(raw: bytes, value: int) -> list[int]:
    needle = struct.pack("<I", value)
    result: list[int] = []
    cursor = 0
    while True:
        cursor = raw.find(needle, cursor)
        if cursor < 0:
            return result
        result.append(cursor)
        cursor += 1


def _rebuild(rom: bytes, *, verify_identity: bool = True) -> dict[str, Any]:
    if verify_identity and (len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256):
        raise ValueError("ROM identity changed")
    descriptor_starts = [0x12D574 + index * 0x54 for index in range(12)]
    descriptors = []
    for index, descriptor_start in enumerate(descriptor_starts):
        entry_heads = [struct.unpack_from("<H", rom, descriptor_start + entry * 0x14)[0]
                       for entry in range(4)]
        terminator = struct.unpack_from("<I", rom, descriptor_start + 0x50)[0]
        if any(value == 0xFFFF for value in entry_heads) or terminator != 0x0000FFFF:
            raise ValueError("descriptor terminator changed")
        descriptors.append({"descriptor_index": index,
                            "range": [descriptor_start, descriptor_start + 0x54],
                            "entry_count": 4, "entry_stride": 0x14,
                            "entry_heads": entry_heads, "terminator": terminator & 0xFFFF,
                            "bytes_sha256": _sha(rom[descriptor_start:descriptor_start + 0x54])})
    descriptor_pointers = list(struct.unpack_from("<12I", rom, 0x12D964))
    if descriptor_pointers != [0x08000000 + offset for offset in descriptor_starts]:
        raise ValueError("pointer table changed")
    group_pointers = list(struct.unpack_from("<4I", rom, 0x12D9D4))
    if group_pointers != [0x0812D994 + index * 0x10 for index in range(4)]:
        raise ValueError("pointer table changed")
    groups: list[dict[str, Any]] = []
    record_denominator: list[int] = []
    terminators: list[int] = []
    for group_index in range(4):
        group_start = 0x12D994 + group_index * 0x10
        words = list(struct.unpack_from("<4I", rom, group_start))
        records = [word & 0xFFFF for word in words[:3]]
        durations = [word >> 16 for word in words[:3]]
        if records != list(range(group_index * 3, group_index * 3 + 3)):
            raise ValueError("group record denominator changed")
        if durations != [5, 5, 5] or words[3] != 0xFFFF:
            raise ValueError("terminator changed")
        record_denominator.extend(records)
        terminators.append(words[3] & 0xFFFF)
        groups.append({"group_index": group_index, "range": [group_start, group_start + 0x10],
                       "record_indices": records, "durations": durations,
                       "terminator": words[3] & 0xFFFF})
    if _sha(rom[TABLE_RANGE[0]:TABLE_RANGE[1]]) != TABLE_SHA256:
        raise ValueError("table identity changed")

    for span, digest, label in IDENTITIES:
        if _sha(rom[span[0]:span[1]]) != digest:
            raise ValueError(f"{label} consumer identity changed")
    for value, offsets in LITERALS.items():
        if _occurrences(rom, value) != offsets:
            raise ValueError("consumer literal denominator changed")
    # These checks are intentionally expressed as independent raw opcode
    # predicates rather than invoking exporter helpers or its decoder.
    half = lambda offset: struct.unpack_from("<H", rom, offset)[0]
    if not (half(0x071EA8) == 0x2600 and half(0x071EAE) == 0xD907
            and half(0x071EB0) == 0x2601 and half(0x071EB8) == 0x2602
            and half(0x071EBC) == 0xD900 and half(0x071EBE) == 0x2603):
        raise ValueError("consumer group-domain changed")
    if not (half(0x071EC0) == 0x4822 and half(0x071EC2) == 0x4923
            and half(0x071EFA) == 0x1C32 and rom[0x071EFC:0x071F00].hex() == "f0f7dafb"):
        raise ValueError("consumer call chain changed")
    if not (half(0x062730) == 0x2100
            and half(0x06274E) == 0x4650 and half(0x062750) == 0x8290
            and half(0x062752) == 0x82D1
            and half(0x062756) == 0x9900 and half(0x062758) == 0x61D1
            and half(0x06275A) == 0x9B01 and half(0x06275C) == 0x6213):
        raise ValueError("consumer allocator fields changed")
    if not (half(0x06298C) == 0x8AB9 and half(0x06298E) == 0x6A38
            and half(0x062994) == 0x8AF8 and half(0x062998) == 0x6809
            and half(0x0629E8) == 0x2400 and half(0x0629EA) == 0x5F18
            and half(0x0629EC) == 0x69F9 and half(0x0629F0) == 0x1840
            and half(0x0629F2) == 0x6800):
        raise ValueError("consumer renderer indexing changed")
    if not (half(0x0631F6) == 0x2514 and half(0x0631F8) == 0x44A8
            and half(0x0631FA) == 0x4640 and half(0x0631FC) == 0x2200
            and half(0x0631FE) == 0x5E81 and half(0x063200) == 0x2001
            and half(0x063202) == 0x4240 and half(0x063204) == 0x4281
            and half(0x063206) == 0xD00B):
        raise ValueError("consumer descriptor stride/stop changed")
    if not (half(0x063256) == 0x8B38 and half(0x063258) == 0x3001
            and half(0x06325A) == 0x8338 and half(0x063268) == 0x9B00
            and half(0x06326A) == 0x2204 and half(0x06326C) == 0x5E98
            and half(0x06326E) == 0x4540 and half(0x063270) == 0xD008
            and half(0x063272) == 0x8AF8 and half(0x063274) == 0x3001
            and half(0x063276) == 0x82F8):
        raise ValueError("consumer terminator advance changed")

    tables = {"range": list(TABLE_RANGE), "bytes_sha256": TABLE_SHA256,
              "descriptor_range": [0x12D574, 0x12D964], "descriptor_count": 12,
              "descriptor_size": 0x54, "descriptors": descriptors,
              "descriptor_pointer_range": [0x12D964, 0x12D994],
              "descriptor_pointer_count": 12, "descriptor_pointers": descriptor_pointers,
              "group_sequence_range": [0x12D994, 0x12D9D4],
              "group_pointer_range": [0x12D9D4, 0x12D9E4], "group_count": 4,
              "records_per_group": 3, "groups": groups,
              "record_index_denominator": record_denominator,
              "group_index_denominator": list(range(4)), "group_terminators": terminators}
    consumer = {"literal_load_sites": [0x071EC0, 0x071EC2],
                "literal_word_sites": [0x071F4C, 0x071F50],
                "literal_occurrence_denominator": {f"0x{value:08X}": offsets
                                                   for value, offsets in LITERALS.items()},
                "allocator_call_site": 0x071EFC, "allocator_call_target": 0x0626B4,
                "allocator_object_fields": {"group_index": 0x14, "record_slot": 0x16,
                                            "descriptor_table": 0x1C, "group_table": 0x20},
                "renderer_root": 0x062924, "caller_group_domain": [0, 3],
                "runtime_record_slot_domain": [0, 2], "terminator": 0xFFFF,
                "out_of_range_reads": 0,
                "identity_ranges": [{"range": list(span), "bytes_sha256": digest}
                                    for span, digest, _ in IDENTITIES]}
    return {"schema": SCHEMA,
            "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
            "tables": tables, "consumer_contract": consumer,
            "promotion": {"promotion_batch": SCHEMA, "promoted_from_primary_class": "unknown",
                          "claims": [{"id": "fixed-animation-descriptor-groups-12d574",
                                      "range": list(TABLE_RANGE),
                                      "claim_kind": "fixed_consumer_animation_descriptor_groups",
                                      "bytes_sha256": TABLE_SHA256}],
                          "claim_count": 1, "promotion_bytes": 1136},
            "scope": {"natural_runtime_reachability": False,
                      "all_callers_share_this_input": False,
                      "descriptor_editing_safety": False,
                      "opaque_renderer_side_effects": False}}


def verify_artifact(root: Path, artifact: Path, *, expected_artifact: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    try:
        root = root.resolve(strict=True)
        lexical = artifact if artifact.is_absolute() else root / artifact
        lexical = Path(os.path.abspath(lexical))
        try:
            relative = lexical.relative_to(root)
        except ValueError as error:
            raise ValueError("artifact escapes root") from error
        cursor = root
        for part in relative.parts:
            cursor /= part
            if cursor.is_symlink():
                raise ValueError("artifact path has a symlink component")
        artifact = lexical.resolve(strict=True)
        if not artifact.is_relative_to(root) or not artifact.is_dir():
            raise ValueError("artifact escapes root")
        if set(path.name for path in artifact.iterdir()) != {MANIFEST_NAME, PAYLOAD_NAME}:
            raise ValueError("artifact file denominator changed")
        for name in (MANIFEST_NAME, PAYLOAD_NAME):
            member = artifact / name
            if member.is_symlink() or not member.is_file():
                raise ValueError("artifact member is unsafe")
        manifest_raw = (artifact / MANIFEST_NAME).read_bytes()
        payload_raw = (artifact / PAYLOAD_NAME).read_bytes()
        manifest = json.loads(manifest_raw)
        if _canonical(manifest) != manifest_raw:
            raise ValueError("manifest is not canonical JSON")
        file_row = manifest["files"][PAYLOAD_NAME]
        if file_row != {"size": len(payload_raw), "sha256": _sha(payload_raw)}:
            raise ValueError("manifest payload identity mismatch")
        payload = json.loads(payload_raw)
        rebuilt = _rebuild(_safe_file(root, ROM_PATH).read_bytes())
        if payload != rebuilt or _canonical(rebuilt) != payload_raw:
            raise ValueError("payload differs from canonical independent rebuild")
        final = expected_artifact if expected_artifact is not None else artifact
        final = final if final.is_absolute() else root / final
        final_relative = final.resolve(strict=False).relative_to(root).as_posix()
        exporter = Path("tools/export_rom_fixed_animation_descriptor_groups.py")
        verifier = Path("tools/verify_rom_fixed_animation_descriptor_groups.py")
        test = Path("tests/test_export_rom_fixed_animation_descriptor_groups.py")
        expected_manifest = {
            "schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,
            "artifact_status": "accepted",
            "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}},
            "summary": {"descriptor_count": 12, "group_count": 4,
                        "promotion_bytes": 1136},
            "producer": {"command": ["python3", exporter.as_posix(), "--root", ".",
                                     "--output", final_relative]},
            "verifier": {"command": ["python3", verifier.as_posix(), "--root", ".",
                                     "--artifact", final_relative]},
            "implementation": {"exporter_sha256": _sha(_safe_file(root, exporter).read_bytes()),
                               "verifier_sha256": _sha(_safe_file(root, verifier).read_bytes()),
                               "test_sha256": _sha(_safe_file(root, test).read_bytes())},
        }
        if manifest != expected_manifest:
            raise ValueError("manifest differs from complete expected contract")
        if expected_artifact is not None:
            expected = expected_artifact if expected_artifact.is_absolute() else root / expected_artifact
            if expected.resolve(strict=False) == artifact:
                raise ValueError("staging path unexpectedly equals final path")
    except Exception as exc:  # fail closed and preserve the reason in a stable report
        errors.append(f"{type(exc).__name__}: {exc}")
    return {"schema": "rom-fixed-animation-descriptor-groups-verification-v1",
            "verified": not errors, "errors": errors,
            "promotion_bytes": 1136 if not errors else 0,
            "descriptor_count": 12 if not errors else 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
