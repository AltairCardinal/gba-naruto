#!/usr/bin/env python3
"""Export the source-owned text-BG loop continuation CFG packet."""

from __future__ import annotations

import argparse
import bisect
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _path in (PROJECT_ROOT, PROJECT_ROOT / "tools/_vendor"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs  # type: ignore

from tools.thumb_branch import decode_thumb_b, decode_thumb_bl


SCHEMA = "rom-text-bg-loop-continuation-v1"
VERIFY_SCHEMA = f"{SCHEMA}-verification-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
OFFICIAL = Path("artifacts/rom-text-bg-loop-continuation-v1")
PAYLOAD_NAME = "rom-text-bg-loop-continuation.json"
MANIFEST_NAME = "manifest.json"
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
BASELINE_COVERAGE_SHA256 = "e48c8f6d0df1d3469be2336caa71f628d82a51d4e637d6df42ebded412359c36"
ROOT = 0x08ACC8
PRODUCER = 0x08B644
SOURCE_RANGE = (0x08B640, 0x08B64E)
SOURCE_CLASS = "consumer_code_slice"
SOURCE_CLAIMS = ["verified-reuse-text-bg-loop-link-08b640"]
CODE_RANGE = (0x08ACC8, 0x08ACF2)
LITERAL_RANGE = (0x08AEB4, 0x08AEC0)
CODE_CLASS = "armv4t_text_bg_loop_continuation_reachable_thumb_code"
LITERAL_CLASS = "armv4t_text_bg_loop_continuation_consumed_literal_word"
PROMOTION_BATCH = SCHEMA
EXPECTED_BINDINGS = [
    [0x08ACD4, 0x08AEB4, 0x02002880],
    [0x08ACD6, 0x08AEB8, 0x0300004C],
    [0x08ACE4, 0x08AEB8, 0x0300004C],
    [0x08ACE8, 0x08AEBC, 0x03000054],
]
NONCLAIMS = {
    "natural_runtime_reachability": False,
    "code_after_0x08acf2": False,
    "literal_business_semantics": False,
    "adjacent_padding_or_free_space": False,
    "editing_relocation_or_writeback": False,
}
UPSTREAM_ARTIFACT = Path("artifacts/residual-text-bg-tilemap-resource-ownership-v1")
UPSTREAM_PAYLOAD = "resource-ownership.json"
UPSTREAM_MANIFEST_SHA256 = "a4db6c9ecfb5bf1d4a408630900a1d6b061f0a04aa30191479522904a71b8ccc"
UPSTREAM_PAYLOAD_SHA256 = "95c4baf0febd70151d68c08d276bb694daa1f544035466f9b078f73e538d8741"
SOURCE_PATH_RANGES = ((0x08B58C, 0x08B60A), (0x08B644, 0x08B648))
SOURCE_PATH_PACKED_SHA256 = "bd33f635a92ec41c617e3638c0c3f7b0183c8f5b80cd52414da2038d3e323d97"
SOURCE_PATH_SEMANTIC_SHA256 = "be2a286014fa336d32da7ac145f3971617514e36bcab632c48cbd36067203675"
BOUNDARY_RANGE = [0x08ACF2, 0x08AD08]
BOUNDARY_CLASS = "consumer_code_slice"
BOUNDARY_CLAIMS = ["verified-reuse-wram-selection-bg-setup-08acf2"]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _safe_file(root: Path, relative: Path) -> Path:
    base = root.resolve(strict=True)
    lexical = base / relative
    cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"unsafe input path: {relative}")
    resolved = lexical.resolve(strict=True)
    if lexical.is_symlink() or not resolved.is_relative_to(base) or not resolved.is_file():
        raise ValueError(f"unsafe input path: {relative}")
    return resolved


def _safe_directory(root: Path, relative: Path) -> Path:
    base = root.resolve(strict=True)
    cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"unsafe input path: {relative}")
    resolved = cursor.resolve(strict=True)
    if not resolved.is_relative_to(base) or not resolved.is_dir():
        raise ValueError(f"unsafe input path: {relative}")
    return resolved


def _publish_exclusive(source: Path, destination: Path) -> None:
    if source.parent != destination.parent:
        raise ValueError("exclusive publication requires a shared parent")
    parent_fd = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            rename, flag = libc.renameatx_np, 0x00000004
        elif hasattr(libc, "renameat2"):
            rename, flag = libc.renameat2, 0x00000001
        else:
            raise OSError(errno.ENOTSUP, "atomic no-replace rename unavailable")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(parent_fd, os.fsencode(source.name), parent_fd, os.fsencode(destination.name), flag):
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), destination)
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def _branch(rom: bytes, offset: int) -> tuple[str, int] | None:
    first = struct.unpack_from("<H", rom, offset)[0]
    target = decode_thumb_bl(offset, first, struct.unpack_from("<H", rom, offset + 2)[0])
    if target is not None:
        return "thumb_bl", target
    target = decode_thumb_b(offset, first)
    if target is not None:
        return "thumb_b", target
    if first & 0xF000 == 0xD000 and ((first >> 8) & 0xF) < 0xE:
        displacement = (first & 0xFF) << 1
        if displacement & 0x100:
            displacement -= 0x200
        return "thumb_bcond", offset + 4 + displacement
    return None


def _producer_denominator(rom: bytes) -> dict[str, Any]:
    forms: dict[str, list[int]] = {
        "thumb_bl": [], "thumb_b": [], "thumb_bcond": [],
        "arm_b_bl": [], "aligned_arm_pointer": [], "thumb_pointer": [],
    }
    for offset in range(0, len(rom) - 3, 2):
        decoded = _branch(rom, offset)
        if decoded is not None and decoded[1] == ROOT:
            forms[decoded[0]].append(offset)
        if struct.unpack_from("<I", rom, offset)[0] == ROM_BASE + ROOT + 1:
            forms["thumb_pointer"].append(offset)
    for offset in range(0, len(rom) - 3, 4):
        word = struct.unpack_from("<I", rom, offset)[0]
        if word == ROM_BASE + ROOT:
            forms["aligned_arm_pointer"].append(offset)
        if word >> 28 != 0xF and (word >> 25) & 7 == 5:
            displacement = (word & 0xFFFFFF) << 2
            if displacement & 0x02000000:
                displacement -= 0x04000000
            if offset + 8 + displacement == ROOT:
                forms["arm_b_bl"].append(offset)
    expected = {key: [] for key in forms}
    expected["thumb_bl"] = [PRODUCER]
    if forms != expected:
        raise ValueError("target-limited producer denominator changed")
    raw = rom[PRODUCER : PRODUCER + 4]
    if raw.hex() != "fff740fb" or _sha(raw) != "f7e047cc350bda582135e51f36c556fb0e6445de6ee9c286ae9383c6bbefdc7a":
        raise ValueError("producer bytes changed")
    return {"target_file_offset": ROOT, "forms": forms, "matching_producer_count": 1,
            "producer_raw_hex": raw.hex(), "producer_bytes_sha256": _sha(raw)}


def _segments(coverage: dict[str, Any]) -> tuple[list[dict[str, Any]], list[int]]:
    rows = coverage.get("segments")
    if not isinstance(rows, list) or not rows:
        raise ValueError("coverage segment denominator missing")
    starts: list[int] = []
    cursor = 0
    for row in rows:
        interval = row.get("range")
        if not isinstance(interval, list) or len(interval) != 2 or interval[0] != cursor or interval[1] <= cursor:
            raise ValueError("coverage segment denominator changed")
        starts.append(cursor)
        cursor = interval[1]
    if cursor != ROM_SIZE:
        raise ValueError("coverage accounting changed")
    return rows, starts


def _segment_at(rows: list[dict[str, Any]], starts: list[int], offset: int) -> dict[str, Any]:
    row = rows[bisect.bisect_right(starts, offset) - 1]
    if not row["range"][0] <= offset < row["range"][1]:
        raise ValueError("coverage lookup failed")
    return row


def _coverage_contract(raw: bytes) -> tuple[dict[str, Any], str]:
    digest = _sha(raw)
    coverage = json.loads(raw)
    rows, starts = _segments(coverage)
    owner = _segment_at(rows, starts, PRODUCER)
    expected_owner = {"range": list(SOURCE_RANGE), "primary_class": SOURCE_CLASS,
                      "primary_claim_ids": SOURCE_CLAIMS}
    if any(owner.get(key) != value for key, value in expected_owner.items()):
        raise ValueError("producer source owner changed")
    boundary = _segment_at(rows, starts, CODE_RANGE[1])
    expected_boundary = {"range": BOUNDARY_RANGE, "primary_class": BOUNDARY_CLASS,
                         "primary_claim_ids": BOUNDARY_CLAIMS}
    if any(boundary.get(key) != value for key, value in expected_boundary.items()):
        raise ValueError("opaque boundary owner changed")
    states: list[str] = []
    for start, end, expected_class in (*[(CODE_RANGE[0], CODE_RANGE[1], CODE_CLASS)],
                                       *[(LITERAL_RANGE[0], LITERAL_RANGE[1], LITERAL_CLASS)]):
        offset = start
        local: set[str] = set()
        while offset < end:
            row = _segment_at(rows, starts, offset)
            primary = row.get("primary_class")
            if primary == "unknown":
                local.add("baseline")
            elif primary == expected_class:
                local.add("post-promotion")
            else:
                raise ValueError("promotion range is neither baseline unknown nor accepted post-state")
            offset = min(row["range"][1], end)
        if len(local) != 1:
            raise ValueError("mixed promotion coverage state")
        states.extend(local)
    if len(set(states)) != 1:
        raise ValueError("mixed packet coverage state")
    state = states[0]
    if state == "baseline" and digest != BASELINE_COVERAGE_SHA256:
        raise ValueError("baseline coverage identity changed")
    return coverage, state


def _source_membership(root: Path, rom: bytes) -> dict[str, Any]:
    from tools.verify_residual_text_bg_tilemap_resource_ownership import verify_artifact

    artifact = _safe_directory(root, UPSTREAM_ARTIFACT)
    manifest_raw = _safe_file(root, UPSTREAM_ARTIFACT / MANIFEST_NAME).read_bytes()
    payload_raw = _safe_file(root, UPSTREAM_ARTIFACT / UPSTREAM_PAYLOAD).read_bytes()
    if _sha(manifest_raw) != UPSTREAM_MANIFEST_SHA256 or _sha(payload_raw) != UPSTREAM_PAYLOAD_SHA256:
        raise ValueError("upstream text-BG ownership identity changed")
    report = verify_artifact(root, artifact)
    if report.get("verified") is not True:
        raise ValueError("upstream text-BG ownership verification failed")
    upstream = json.loads(payload_raw)
    scope = upstream.get("scope", {})
    record = upstream.get("ownership_record", {})
    if scope.get("static_natural_caller_chain_complete") is not True or record.get("natural_entry_callers") != ["0x0808F844", "0x0808FA04"] or record.get("resource_setup_function") != "0x0808B58C":
        raise ValueError("upstream static caller chain changed")
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    decoded = []
    for start, end in SOURCE_PATH_RANGES:
        rows = list(engine.disasm(rom[start:end], ROM_BASE + start))
        if sum(row.size for row in rows) != end - start:
            raise ValueError("source membership path decode changed")
        decoded.extend(rows)
    semantic = [[row.address - ROM_BASE, row.size, row.mnemonic, row.op_str] for row in decoded]
    packed = b"".join(rom[start:end] for start, end in SOURCE_PATH_RANGES)
    if len(decoded) != 55 or len(packed) != 130 or _sha(packed) != SOURCE_PATH_PACKED_SHA256 or _sha(_canonical(semantic)) != SOURCE_PATH_SEMANTIC_SHA256:
        raise ValueError("source membership path denominator changed")
    branch = _branch(rom, 0x08B608)
    producer = _branch(rom, PRODUCER)
    if branch != ("thumb_b", PRODUCER) or producer != ("thumb_bl", ROOT):
        raise ValueError("source membership branch chain changed")
    return {
        "upstream_artifact": UPSTREAM_ARTIFACT.as_posix(),
        "upstream_manifest_sha256": UPSTREAM_MANIFEST_SHA256,
        "upstream_payload_sha256": UPSTREAM_PAYLOAD_SHA256,
        "upstream_verified": True,
        "natural_entry_callers": [0x08F844, 0x08FA04],
        "root_file_offset": 0x08B58C,
        "path_ranges": [list(row) for row in SOURCE_PATH_RANGES],
        "instruction_count": 55,
        "instruction_bytes": 130,
        "packed_sha256": SOURCE_PATH_PACKED_SHA256,
        "semantic_instruction_vector_sha256": SOURCE_PATH_SEMANTIC_SHA256,
        "terminal_branch": {"file_offset": 0x08B608, "target_file_offset": PRODUCER},
        "producer_instruction_membership_proven": True,
    }


def _cfg(rom: bytes) -> dict[str, Any]:
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    instructions = list(engine.disasm(rom[CODE_RANGE[0] : CODE_RANGE[1]], ROM_BASE + CODE_RANGE[0]))
    if len(instructions) != 21 or sum(row.size for row in instructions) != 42 or any(row.size != 2 for row in instructions):
        raise ValueError("target-local Thumb instruction denominator changed")
    semantic = [[row.address - ROM_BASE, row.size, row.mnemonic, row.op_str] for row in instructions]
    if _sha(rom[CODE_RANGE[0] : CODE_RANGE[1]]) != "63b9d3ea83926af1934f0941783b87c11fd20e4f1d574077042c433103444b60":
        raise ValueError("target-local code bytes changed")
    bindings: list[list[int]] = []
    for row in instructions:
        offset = row.address - ROM_BASE
        halfword = struct.unpack_from("<H", rom, offset)[0]
        if halfword & 0xF800 == 0x4800:
            literal = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
            bindings.append([offset, literal, struct.unpack_from("<I", rom, literal)[0]])
    if bindings != EXPECTED_BINDINGS:
        raise ValueError("consumed literal binding denominator changed")
    if _sha(rom[LITERAL_RANGE[0] : LITERAL_RANGE[1]]) != "bcdc220c3e327144ba44963a55291fe4bf8d4357ca1de84904b883b8bb1f4525":
        raise ValueError("consumed literal bytes changed")
    return {
        "root_file_offset": ROOT, "mode": "thumb", "instruction_count": 21,
        "basic_block_count": 1, "frontier_count": 0, "code_range": list(CODE_RANGE),
        "code_bytes": 42, "code_bytes_sha256": _sha(rom[CODE_RANGE[0] : CODE_RANGE[1]]),
        "semantic_instruction_vector": semantic,
        "semantic_instruction_vector_sha256": _sha(_canonical(semantic)),
        "boundary": {"source_file_offset": 0x08ACF0, "target_file_offset": 0x08ACF2,
                     "edge_kind": "opaque_boundary", "reason": "accepted_owner_beginning"},
        "literal_bindings": bindings, "literal_reference_count": 4,
        "unique_literal_word_count": 3, "literal_range": list(LITERAL_RANGE),
        "literal_bytes": 12, "literal_bytes_sha256": _sha(rom[LITERAL_RANGE[0] : LITERAL_RANGE[1]]),
    }


def build_payload(root: Path) -> dict[str, Any]:
    rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    coverage_raw = _safe_file(root, COVERAGE_PATH).read_bytes()
    _, coverage_state = _coverage_contract(coverage_raw)
    producer = _producer_denominator(rom)
    source_membership = _source_membership(root, rom)
    cfg = _cfg(rom)
    claims = [
        {"id": "text-bg-loop-continuation-code", "range": list(CODE_RANGE), "role": "primary",
         "kind": "reachable_thumb_code",
         "primary_class": CODE_CLASS, "claim_kind": "reachable_thumb_code", "mode": "thumb",
         "promotion_batch": PROMOTION_BATCH, "promoted_from_primary_class": "unknown",
         "bytes_sha256": cfg["code_bytes_sha256"]},
        {"id": "text-bg-loop-continuation-literals", "range": list(LITERAL_RANGE), "role": "primary",
         "kind": "consumed_literal_words",
         "primary_class": LITERAL_CLASS, "claim_kind": "consumed_literal_word",
         "promotion_batch": PROMOTION_BATCH, "promoted_from_primary_class": "unknown",
         "bytes_sha256": cfg["literal_bytes_sha256"]},
    ]
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": _sha(rom)},
        "coverage_baseline": {"path": COVERAGE_PATH.as_posix(), "historical_sha256": BASELINE_COVERAGE_SHA256,
                              "observed_during_artifact_build": True},
        "producer_denominator": producer,
        "source_owner": {"range": list(SOURCE_RANGE), "primary_class": SOURCE_CLASS, "primary_claim_ids": SOURCE_CLAIMS},
        "source_membership": source_membership,
        "opaque_boundary_owner": {"range": BOUNDARY_RANGE, "primary_class": BOUNDARY_CLASS,
                                  "primary_claim_ids": BOUNDARY_CLAIMS},
        "target_local_cfg": cfg,
        "promotion": {"batch": PROMOTION_BATCH, "claims": claims, "code_bytes": 42,
                      "literal_bytes": 12, "promotion_bytes": 54},
        "scope": NONCLAIMS,
    }


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    lexical_target = (output if output.is_absolute() else root / output).absolute()
    try:
        lexical_relative = lexical_target.relative_to(root)
    except ValueError as error:
        raise ValueError("output escapes project root") from error
    cursor = root
    for part in lexical_relative.parts[:-1]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("output path uses symlink ancestor")
    target = lexical_target.resolve(strict=False)
    if target.exists() or lexical_target.is_symlink():
        raise FileExistsError(f"output already exists: {output}")
    if not target.resolve(strict=False).is_relative_to(root):
        raise ValueError("output escapes project root")
    payload = build_payload(root)
    payload_raw = _canonical(payload)
    relative = target.relative_to(root)
    manifest = {
        "schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}},
        "summary": {"producer_count": 1, "instruction_count": 21, "code_bytes": 42,
                    "literal_word_count": 3, "literal_bytes": 12, "promotion_bytes": 54},
        "producer": {"command": ["python3", "tools/export_rom_text_bg_loop_continuation.py",
                                  "--root", ".", "--output", relative.as_posix()]},
        "verifier": {"command": ["python3", "tools/verify_rom_text_bg_loop_continuation.py",
                                  "--root", ".", "--artifact", relative.as_posix()]},
        "implementation": {
            "exporter_sha256": _sha(_safe_file(root, Path("tools/export_rom_text_bg_loop_continuation.py")).read_bytes()),
            "verifier_sha256": _sha(_safe_file(root, Path("tools/verify_rom_text_bg_loop_continuation.py")).read_bytes()),
            "test_sha256": _sha(_safe_file(root, Path("tests/test_export_rom_text_bg_loop_continuation.py")).read_bytes()),
        },
    }
    manifest_raw = _canonical(manifest)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
    try:
        for name, raw in ((PAYLOAD_NAME, payload_raw), (MANIFEST_NAME, manifest_raw)):
            with (temporary / name).open("xb") as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        directory_fd = os.open(temporary, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(directory_fd)
        finally: os.close(directory_fd)
        _publish_exclusive(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=OFFICIAL)
    args = parser.parse_args()
    manifest = export_artifact(args.root, args.output)
    print(json.dumps(manifest["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
