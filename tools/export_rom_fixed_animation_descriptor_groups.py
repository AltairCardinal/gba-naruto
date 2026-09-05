#!/usr/bin/env python3
"""Export the fixed four-group animation descriptor inventory at 0x12D574."""

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


SCHEMA = "rom-fixed-animation-descriptor-groups-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
OFFICIAL = Path("artifacts/rom-fixed-animation-descriptor-groups-v1")
PAYLOAD_NAME = "rom-fixed-animation-descriptor-groups.json"
MANIFEST_NAME = "manifest.json"

TABLE_RANGE = (0x12D574, 0x12D9E4)
DESCRIPTOR_RANGE = (0x12D574, 0x12D964)
DESCRIPTOR_SIZE = 0x54
DESCRIPTOR_POINTER_RANGE = (0x12D964, 0x12D994)
GROUP_SEQUENCE_RANGE = (0x12D994, 0x12D9D4)
GROUP_POINTER_RANGE = (0x12D9D4, 0x12D9E4)
TABLE_SHA256 = "7ec09a078b86ee22ca7d7ae1be34130eb19bbdf8d0266769d23dd919ce493a8d"
CALLER_RANGE = (0x071E74, 0x071F00)
CALLER_SHA256 = "2f57b17a42eaec539eeb532e0d481c89740a525a1ed382d7ff6175c8921e3afc"
ALLOCATOR_RANGE = (0x0626B4, 0x062766)
ALLOCATOR_SHA256 = "09cd85fb8fcdc85751019c67ef6b91d6d3d64c1fbeb0b0496e270234f846d804"
RENDERER_SELECT_RANGE = (0x062924, 0x062A0A)
RENDERER_SELECT_SHA256 = "23ead2fcc1537d16a632bf68dbccdb96a142af170410f862baaf4c1d750e0a18"
RENDERER_DESCRIPTOR_STEP_RANGE = (0x0631F6, 0x063208)
RENDERER_DESCRIPTOR_STEP_SHA256 = "79cb19c28c7f5a75ed323f99c837e131c0e11dd06c91f422e60ac9ff859e8f44"
RENDERER_ADVANCE_RANGE = (0x063238, 0x0632BA)
RENDERER_ADVANCE_SHA256 = "b6dc39ac66ecaac48e16f37406bab7e579362759e9e3570e9c6fa9e24ec0ab23"
EXPECTED_LITERAL_OCCURRENCES = {
    0x0812D964: [0x071F4C],
    0x0812D9D4: [0x071F50],
}


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
        raise ValueError(f"{label} consumer identity changed")


def _all_occurrences(raw: bytes, needle: bytes) -> list[int]:
    result: list[int] = []
    cursor = 0
    while True:
        cursor = raw.find(needle, cursor)
        if cursor < 0:
            return result
        result.append(cursor)
        cursor += 1


def _parse_tables(rom: bytes) -> dict[str, Any]:
    start, end = TABLE_RANGE
    descriptor_starts = list(range(DESCRIPTOR_RANGE[0], DESCRIPTOR_RANGE[1], DESCRIPTOR_SIZE))
    if len(descriptor_starts) != 12 or descriptor_starts[-1] + DESCRIPTOR_SIZE != DESCRIPTOR_RANGE[1]:
        raise ValueError("descriptor denominator changed")
    descriptors = []
    for index, descriptor_start in enumerate(descriptor_starts):
        entry_heads = [struct.unpack_from("<H", rom, descriptor_start + entry * 0x14)[0]
                       for entry in range(4)]
        terminator = struct.unpack_from("<I", rom, descriptor_start + 0x50)[0]
        if any(value == 0xFFFF for value in entry_heads) or terminator != 0x0000FFFF:
            raise ValueError("descriptor terminator changed")
        descriptors.append({"descriptor_index": index,
                            "range": [descriptor_start, descriptor_start + DESCRIPTOR_SIZE],
                            "entry_count": 4, "entry_stride": 0x14,
                            "entry_heads": entry_heads, "terminator": terminator & 0xFFFF,
                            "bytes_sha256": _sha(rom[descriptor_start:descriptor_start + DESCRIPTOR_SIZE])})
    pointers = list(struct.unpack_from("<12I", rom, DESCRIPTOR_POINTER_RANGE[0]))
    expected_pointers = [0x08000000 + offset for offset in descriptor_starts]
    if pointers != expected_pointers:
        raise ValueError("pointer table changed")

    group_pointers = list(struct.unpack_from("<4I", rom, GROUP_POINTER_RANGE[0]))
    expected_group_pointers = [0x08000000 + GROUP_SEQUENCE_RANGE[0] + i * 0x10
                               for i in range(4)]
    if group_pointers != expected_group_pointers:
        raise ValueError("pointer table changed")
    groups: list[dict[str, Any]] = []
    flat: list[int] = []
    terminators: list[int] = []
    for group_index in range(4):
        group_start = GROUP_SEQUENCE_RANGE[0] + group_index * 0x10
        words = list(struct.unpack_from("<4I", rom, group_start))
        record_ids = [word & 0xFFFF for word in words[:3]]
        durations = [(word >> 16) & 0xFFFF for word in words[:3]]
        terminator = words[3] & 0xFFFF
        if record_ids != list(range(group_index * 3, group_index * 3 + 3)):
            raise ValueError("group record denominator changed")
        if durations != [5, 5, 5] or words[3] != 0x0000FFFF:
            raise ValueError("terminator changed")
        flat.extend(record_ids)
        terminators.append(terminator)
        groups.append({"group_index": group_index, "range": [group_start, group_start + 0x10],
                       "record_indices": record_ids, "durations": durations,
                       "terminator": terminator})
    if _sha(rom[start:end]) != TABLE_SHA256:
        raise ValueError("table identity changed")
    return {"range": list(TABLE_RANGE), "bytes_sha256": TABLE_SHA256,
            "descriptor_range": list(DESCRIPTOR_RANGE), "descriptor_count": 12,
            "descriptor_size": DESCRIPTOR_SIZE, "descriptors": descriptors,
            "descriptor_pointer_range": list(DESCRIPTOR_POINTER_RANGE),
            "descriptor_pointer_count": len(pointers), "descriptor_pointers": pointers,
            "group_sequence_range": list(GROUP_SEQUENCE_RANGE),
            "group_pointer_range": list(GROUP_POINTER_RANGE), "group_count": 4,
            "records_per_group": 3, "groups": groups,
            "record_index_denominator": flat, "group_index_denominator": list(range(4)),
            "group_terminators": terminators}


def _consumer_contract(rom: bytes) -> dict[str, Any]:
    _pin(rom, CALLER_RANGE, CALLER_SHA256, "caller")
    _pin(rom, ALLOCATOR_RANGE, ALLOCATOR_SHA256, "allocator")
    _pin(rom, RENDERER_SELECT_RANGE, RENDERER_SELECT_SHA256, "renderer")
    _pin(rom, RENDERER_DESCRIPTOR_STEP_RANGE, RENDERER_DESCRIPTOR_STEP_SHA256,
         "renderer descriptor-step")
    _pin(rom, RENDERER_ADVANCE_RANGE, RENDERER_ADVANCE_SHA256, "renderer advance")
    for value, expected in EXPECTED_LITERAL_OCCURRENCES.items():
        if _all_occurrences(rom, struct.pack("<I", value)) != expected:
            raise ValueError("consumer literal denominator changed")
    # Caller sets r6 to 0/1/2/3 on the exhaustive compare paths, loads both
    # table literals, then passes r6 as r2 to the allocator.
    half = lambda offset: struct.unpack_from("<H", rom, offset)[0]
    if not (half(0x071EA8) == 0x2600 and half(0x071EAE) == 0xD907
            and half(0x071EB0) == 0x2601 and half(0x071EB8) == 0x2602
            and half(0x071EBC) == 0xD900 and half(0x071EBE) == 0x2603):
        raise ValueError("consumer group-domain changed")
    if rom[0x071EC0:0x071F00].hex() != (
        "22482349ea2252001c1c5443e419221cc43213785b011033c534227812051d4c1"
        "21912140092c822920001920f22029283225201039200220492321cf0f7dafb"):
        raise ValueError("consumer call chain changed")
    # Generic allocator stores r2 at object+0x14 and the two bases at +0x1c/+0x20.
    if not (half(0x062730) == 0x2100 and half(0x06274E) == 0x4650
            and half(0x062750) == 0x8290 and half(0x062752) == 0x82D1
            and half(0x062756) == 0x9900 and half(0x062758) == 0x61D1
            and half(0x06275A) == 0x9B01 and half(0x06275C) == 0x6213):
        raise ValueError("consumer allocator fields changed")
    # Renderer selects group pointer by object+0x14, sequence slot by +0x16,
    # then maps the low halfword through the 12-slot descriptor pointer table.
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
    # Slot begins at zero; it increments only when the next low halfword is
    # not 0xffff.  Every frozen group therefore exposes slots 0..2 only.
    if rom[0x063256:0x06327A].hex() != "388b01303883009a0223d05e3a8b904237d1009b0422985e404508d0f88a0130f8821fe0":
        raise ValueError("consumer terminator advance changed")
    return {"literal_load_sites": [0x071EC0, 0x071EC2],
            "literal_word_sites": [0x071F4C, 0x071F50],
            "literal_occurrence_denominator": {f"0x{value:08X}": offsets
                                               for value, offsets in EXPECTED_LITERAL_OCCURRENCES.items()},
            "allocator_call_site": 0x071EFC, "allocator_call_target": 0x0626B4,
            "allocator_object_fields": {"group_index": 0x14, "record_slot": 0x16,
                                        "descriptor_table": 0x1C, "group_table": 0x20},
            "renderer_root": 0x062924, "caller_group_domain": [0, 3],
            "runtime_record_slot_domain": [0, 2], "terminator": 0xFFFF,
            "out_of_range_reads": 0,
            "identity_ranges": [{"range": list(span), "bytes_sha256": digest}
                                for span, digest in ((CALLER_RANGE, CALLER_SHA256),
                                    (ALLOCATOR_RANGE, ALLOCATOR_SHA256),
                                    (RENDERER_SELECT_RANGE, RENDERER_SELECT_SHA256),
                                    (RENDERER_DESCRIPTOR_STEP_RANGE,
                                     RENDERER_DESCRIPTOR_STEP_SHA256),
                                    (RENDERER_ADVANCE_RANGE, RENDERER_ADVANCE_SHA256))]}


def _build_from_rom(root: Path, rom: bytes, *, verify_identity: bool = True) -> dict[str, Any]:
    if verify_identity and (len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256):
        raise ValueError("ROM identity changed")
    tables = _parse_tables(rom)
    consumer = _consumer_contract(rom)
    claim = {"id": "fixed-animation-descriptor-groups-12d574",
             "range": list(TABLE_RANGE),
             "claim_kind": "fixed_consumer_animation_descriptor_groups",
             "bytes_sha256": TABLE_SHA256}
    return {"schema": SCHEMA,
            "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
            "tables": tables, "consumer_contract": consumer,
            "promotion": {"promotion_batch": SCHEMA, "promoted_from_primary_class": "unknown",
                          "claims": [claim], "claim_count": 1,
                          "promotion_bytes": TABLE_RANGE[1] - TABLE_RANGE[0]},
            "scope": {"natural_runtime_reachability": False,
                      "all_callers_share_this_input": False,
                      "descriptor_editing_safety": False,
                      "opaque_renderer_side_effects": False}}


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
    exporter = Path("tools/export_rom_fixed_animation_descriptor_groups.py")
    verifier = Path("tools/verify_rom_fixed_animation_descriptor_groups.py")
    test = Path("tests/test_export_rom_fixed_animation_descriptor_groups.py")
    manifest = {"schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,
                "artifact_status": "accepted",
                "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}},
                "summary": {"descriptor_count": 12, "group_count": 4,
                            "promotion_bytes": 1136},
                "producer": {"command": ["python3", exporter.as_posix(), "--root", ".",
                                         "--output", output.relative_to(root).as_posix()]},
                "verifier": {"command": ["python3", verifier.as_posix(), "--root", ".",
                                         "--artifact", output.relative_to(root).as_posix()]},
                "implementation": {"exporter_sha256": _sha(_safe_file(root, exporter).read_bytes()),
                                   "verifier_sha256": _sha(_safe_file(root, verifier).read_bytes()),
                                   "test_sha256": _sha(_safe_file(root, test).read_bytes())}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".fixed-animation-") as directory:
        stage = Path(directory)
        (stage / PAYLOAD_NAME).write_bytes(payload_raw)
        (stage / MANIFEST_NAME).write_bytes(_canonical(manifest))
        from tools.verify_rom_fixed_animation_descriptor_groups import verify_artifact
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
