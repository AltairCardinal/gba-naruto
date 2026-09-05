#!/usr/bin/env python3
"""Export the frozen story-selector dependency CFG Tier-1 packet."""

from __future__ import annotations

import argparse
import bisect
import ctypes
import errno
import gzip
import hashlib
import json
import os
import shutil
import struct
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for path in (PROJECT_ROOT, PROJECT_ROOT / "tools/_vendor"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
from tools.rom_story_selector_dependency_cfg_contract import *


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _safe_file(root: Path, relative: Path) -> Path:
    root = root.resolve(strict=True)
    lexical = root / relative
    for member in (lexical, *lexical.parents):
        if member == root.parent:
            break
        if member.is_symlink():
            raise ValueError("symlink input")
    resolved = lexical.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("input escape")
    return resolved


def _load_precoverage(root: Path) -> tuple[dict, list[dict], list[int]]:
    manifest = _safe_file(root, PRECOVERAGE_DIR / MANIFEST_NAME).read_bytes()
    archive = _safe_file(root, PRECOVERAGE_DIR / "rom-byte-coverage.json.gz").read_bytes()
    if (len(manifest), _sha(manifest)) != (PRECOVERAGE_MANIFEST_SIZE, PRECOVERAGE_MANIFEST_SHA256):
        raise ValueError("precoverage manifest identity")
    if (len(archive), _sha(archive)) != (PRECOVERAGE_ARCHIVE_SIZE, PRECOVERAGE_ARCHIVE_SHA256):
        raise ValueError("precoverage archive identity")
    raw = gzip.decompress(archive)
    if (len(raw), _sha(raw)) != (PRECOVERAGE_RAW_SIZE, PRECOVERAGE_RAW_SHA256):
        raise ValueError("precoverage raw identity")
    coverage = json.loads(raw)
    if any(coverage["summary"].get(key) != value for key, value in BASELINE.items()):
        raise ValueError("precoverage summary")
    segments = coverage["segments"]
    if (len(segments) != BASELINE["segment_count"] or segments[0]["range"][0] != 0
            or segments[-1]["range"][1] != ROM_SIZE
            or any(segments[i]["range"][1] != segments[i + 1]["range"][0]
                   for i in range(len(segments) - 1))):
        raise ValueError("precoverage partition")
    return coverage, segments, [row["range"][0] for row in segments]


def _owner(segments: list[dict], starts: list[int], offset: int) -> dict:
    row = segments[bisect.bisect_right(starts, offset) - 1]
    if not row["range"][0] <= offset < row["range"][1]:
        raise ValueError("owner lookup")
    return row


def _direct_target(rom: bytes, offset: int) -> tuple[int, str, int] | None:
    first = struct.unpack_from("<H", rom, offset)[0]
    if offset + 4 <= len(rom):
        second = struct.unpack_from("<H", rom, offset + 2)[0]
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
            if displacement & 0x400000:
                displacement -= 0x800000
            return offset + 4 + displacement, "bl", 4
    if first & 0xF800 == 0xE000:
        displacement = (first & 0x7FF) << 1
        if displacement & 0x800:
            displacement -= 0x1000
        return offset + 4 + displacement, "b", 2
    if first & 0xF000 == 0xD000 and ((first >> 8) & 0xF) < 0xE:
        displacement = (first & 0xFF) << 1
        if displacement & 0x100:
            displacement -= 0x200
        return offset + 4 + displacement, "bcond", 2
    return None


def _producer_rows(rom: bytes, segments: list[dict], starts: list[int]) -> list[dict]:
    matches = []
    for offset in range(0, len(rom) - 1, 2):
        decoded = _direct_target(rom, offset)
        if decoded and ROOT_RANGE[0] <= decoded[0] < ROOT_RANGE[1]:
            matches.append((offset, decoded[0], decoded[1], decoded[2]))
    if matches != [(0x08F676, ROOT_RANGE[0], "bl", 4), (0x08F8DE, ROOT_RANGE[0], "bl", 4)]:
        raise ValueError("direct internal-entry denominator")
    pointer = struct.pack("<I", ROM_BASE + ROOT_RANGE[0] + 1)
    if any(rom[index:index + 4] == pointer for index in range(0, ROM_SIZE - 3)):
        raise ValueError("root pointer denominator")
    rows = []
    for (offset, target, kind, size), frozen in zip(matches, PRODUCERS):
        _, raw_hex, raw_sha, window, window_hex, window_sha, accepted = frozen
        raw = rom[offset:offset + size]
        window_raw = rom[window[0]:window[1]]
        if (raw.hex(), _sha(raw), window_raw.hex(), _sha(window_raw)) != (
                raw_hex, raw_sha, window_hex, window_sha):
            raise ValueError("producer bytes")
        owner = _owner(segments, starts, offset)
        if accepted:
            expected_range, expected_class, expected_claim, expected_sha = ACCEPTED_OWNER
            if (tuple(owner["range"]), owner["primary_class"], owner.get("primary_claim_ids")) != (
                    expected_range, expected_class, [expected_claim]):
                raise ValueError("accepted producer owner")
            if _sha(rom[expected_range[0]:expected_range[1]]) != expected_sha:
                raise ValueError("accepted owner bytes")
            rejection = None
        else:
            if tuple(owner["range"]) != REJECTED_OWNER_RANGE or owner["primary_class"] != "unknown":
                raise ValueError("rejected producer owner")
            rejection = "source_owner_not_instruction_only"
        rows.append({"file_offset": offset, "target_file_offset": target, "kind": kind,
                     "size": size, "raw_hex": raw_hex, "raw_sha256": raw_sha,
                     "window_range": list(window), "window_raw_hex": window_hex,
                     "window_sha256": window_sha, "coverage_owner_range": owner["range"],
                     "coverage_owner_class": owner["primary_class"],
                     "coverage_owner_claim_ids": owner.get("primary_claim_ids", []),
                     "accepted_as_root_proof": accepted, "rejection_reason": rejection})
    return rows


def _dependency(root: Path) -> dict:
    manifest = _safe_file(root, STORY_ARTIFACT / MANIFEST_NAME).read_bytes()
    payload = _safe_file(root, STORY_ARTIFACT / STORY_PAYLOAD_NAME).read_bytes()
    verifier = _safe_file(root, STORY_VERIFIER).read_bytes()
    if (len(manifest), _sha(manifest), len(payload), _sha(payload), _sha(verifier)) != (
            STORY_MANIFEST_SIZE, STORY_MANIFEST_SHA256, STORY_PAYLOAD_SIZE,
            STORY_PAYLOAD_SHA256, STORY_VERIFIER_SHA256):
        raise ValueError("story dependency identity")
    return {"artifact": STORY_ARTIFACT.as_posix(), "manifest_sha256": STORY_MANIFEST_SHA256,
            "payload_sha256": STORY_PAYLOAD_SHA256, "verifier_sha256": STORY_VERIFIER_SHA256,
            "accepted_owner_claim_id": ACCEPTED_OWNER[2]}


def _decode_root_cfg(rom: bytes) -> tuple[list[dict], list[tuple[int, int]], list[list], list[dict]]:
    raw = rom[ROOT_RANGE[0]:ROOT_RANGE[1]]
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    decoded = list(engine.disasm(raw, ROOT_RANGE[0]))
    if (len(decoded) != INSTRUCTION_COUNT or sum(row.size for row in decoded) != len(raw)
            or not decoded or decoded[-1].address + decoded[-1].size != ROOT_RANGE[1]):
        raise ValueError("Capstone instruction denominator")
    vector = []
    by_offset = {}
    for row in decoded:
        row_raw = rom[row.address:row.address + row.size]
        item = {"file_offset": row.address, "size": row.size, "raw_hex": row_raw.hex(),
                "mnemonic": row.mnemonic, "op_str": row.op_str,
                "bytes_sha256": _sha(row_raw)}
        vector.append(item)
        by_offset[row.address] = row
    vector_sha = _sha(_canonical(vector))
    if vector_sha != INSTRUCTION_VECTOR_SHA256:
        raise ValueError("instruction vector denominator")

    worklist = [ROOT_RANGE[0]]
    reached = set()
    opaque_calls: list[tuple[int, int]] = []
    local_edges: list[list] = []
    frontiers: list[dict] = []
    fallthroughs = []
    while worklist:
        offset = worklist.pop()
        if offset in reached:
            continue
        row = by_offset.get(offset)
        if row is None:
            frontiers.append({"source": None, "target": offset, "reason": "non_instruction_target"})
            continue
        reached.add(offset)
        control = _direct_target(rom, offset)
        next_offset = offset + row.size
        if control is not None:
            target, kind, _ = control
            if kind == "bl":
                opaque_calls.append((offset, target))
                if next_offset < ROOT_RANGE[1]:
                    worklist.append(next_offset)
                elif next_offset == ROOT_RANGE[1]:
                    fallthroughs.append(next_offset)
            else:
                if ROOT_RANGE[0] <= target < ROOT_RANGE[1]:
                    worklist.append(target)
                    local_edges.append([offset, target, kind])
                else:
                    frontiers.append({"source": offset, "target": target,
                                      "reason": f"external_{kind}"})
                if kind == "bcond":
                    if next_offset < ROOT_RANGE[1]:
                        worklist.append(next_offset)
                    elif next_offset == ROOT_RANGE[1]:
                        fallthroughs.append(next_offset)
            continue
        dynamic = (row.mnemonic in {"bx", "blx", "tbb", "tbh"}
                   or (row.mnemonic == "pop" and "pc" in row.op_str)
                   or (row.mnemonic in {"mov", "movs", "ldr", "add", "adds"}
                       and row.op_str.lstrip().startswith("pc,")))
        if dynamic:
            frontiers.append({"source": offset, "target": None,
                              "reason": f"dynamic_{row.mnemonic}"})
        elif next_offset < ROOT_RANGE[1]:
            worklist.append(next_offset)
        elif next_offset == ROOT_RANGE[1]:
            fallthroughs.append(next_offset)

    holes = [[row.address, row.address + row.size] for row in decoded if row.address not in reached]
    if (sorted(opaque_calls) != sorted(OPAQUE_CALLS) or local_edges or frontiers or holes
            or sorted(set(fallthroughs)) != [ROOT_RANGE[1]]):
        raise ValueError("raw CFG denominator")
    pc_literals = []
    for row in decoded:
        if row.size != 2:
            continue
        halfword = struct.unpack_from("<H", rom, row.address)[0]
        if halfword & 0xF800 == 0x4800:
            pc_literals.append((row.address, ((row.address + 4) & ~3) + (halfword & 0xFF) * 4))
    if pc_literals != [(LITERAL[0], LITERAL[3][0])]:
        raise ValueError("PC-relative literal denominator")
    return vector, opaque_calls, local_edges, frontiers


def _root_denominator(rom: bytes, segments: list[dict], starts: list[int]) -> dict:
    raw = rom[ROOT_RANGE[0]:ROOT_RANGE[1]]
    if raw.hex() != ROOT_RAW_HEX or _sha(raw) != ROOT_BYTES_SHA256:
        raise ValueError("root bytes")
    instruction_vector, rebuilt_opaque, local_edges, frontiers = _decode_root_cfg(rom)
    opaque = []
    for source, target in OPAQUE_CALLS:
        raw_hex, raw_sha, expected_target, owner_range, owner_class, owner_claim = OPAQUE_SPECS[source]
        call_raw = rom[source:source + 4]
        decoded = _direct_target(rom, source)
        owner = _owner(segments, starts, target)
        if (call_raw.hex(), _sha(call_raw), decoded) != (raw_hex, raw_sha, (expected_target, "bl", 4)):
            raise ValueError("opaque call bytes")
        if (tuple(owner["range"]), owner["primary_class"], owner.get("primary_claim_ids")) != (
                owner_range, owner_class, [owner_claim]):
            raise ValueError("opaque call owner")
        opaque.append({"source": source, "target": target, "raw_hex": raw_hex,
                       "raw_sha256": raw_sha, "coverage_owner_range": owner["range"],
                       "coverage_owner_class": owner_class, "coverage_owner_claim_ids": [owner_claim],
                       "owner_granularity": "coarse" if owner_class == "consumer_code_slice" else "exact"})
    source, source_hex, source_sha, literal_range, literal_hex, value, literal_sha = LITERAL
    literal_raw = rom[literal_range[0]:literal_range[1]]
    source_raw = rom[source:source + 2]
    halfword = struct.unpack_from("<H", source_raw)[0]
    target = ((source + 4) & ~3) + (halfword & 0xFF) * 4
    literal_owner = _owner(segments, starts, literal_range[0])
    if (source_raw.hex(), _sha(source_raw), target, literal_raw.hex(),
            struct.unpack("<I", literal_raw)[0], _sha(literal_raw)) != (
            source_hex, source_sha, literal_range[0], literal_hex, value, literal_sha):
        raise ValueError("literal binding")
    if (halfword & 0xF800 != 0x4800 or tuple(literal_owner["range"]) != FALLTHROUGH[3]
            or literal_owner["primary_class"] != "consumer_code_slice"
            or literal_owner.get("primary_claim_ids") != [FALLTHROUGH[5]]):
        raise ValueError("literal coarse owner")
    fall_offset, fall_hex, fall_sha, fall_range, fall_class, fall_claim = FALLTHROUGH
    fall_raw = rom[fall_offset:fall_offset + 2]
    fall_owner = _owner(segments, starts, fall_offset)
    if (fall_raw.hex(), _sha(fall_raw), tuple(fall_owner["range"]), fall_owner["primary_class"],
            fall_owner.get("primary_claim_ids")) != (
            fall_hex, fall_sha, fall_range, fall_class, [fall_claim]):
        raise ValueError("fallthrough boundary")
    if [(row["source"], row["target"]) for row in opaque] != rebuilt_opaque:
        raise ValueError("opaque call denominator")
    return {"instruction_count": len(instruction_vector), "instruction_bytes": 80,
            "capstone_end_file_offset": ROOT_RANGE[1],
            "instruction_vector_sha256": _sha(_canonical(instruction_vector)),
            "opaque_call_count": len(opaque), "opaque_calls": opaque,
            "preowned_literal_count": 1, "preowned_literals": [{"source": source,
                "source_raw_hex": source_hex, "source_sha256": source_sha,
                "range": list(literal_range), "raw_hex": literal_hex, "value_u32": value,
                "bytes_sha256": literal_sha, "coverage_owner_range": literal_owner["range"],
                "coverage_owner_class": literal_owner["primary_class"],
                "coverage_owner_claim_ids": literal_owner["primary_claim_ids"],
                "owner_granularity": "coarse", "promotion": False}],
            "fallthrough": {"file_offset": fall_offset, "raw_hex": fall_hex,
                "bytes_sha256": fall_sha, "coverage_owner_range": list(fall_range),
                "coverage_owner_class": fall_class, "coverage_owner_claim_ids": [fall_claim],
                "owner_granularity": "coarse", "promotion": False},
            "local_edge_count": len(local_edges), "local_edges": local_edges,
            "hole_count": 0, "holes": [], "frontier_count": len(frontiers),
            "frontiers": frontiers}


def _implementation(root: Path) -> dict:
    return {"binding": "contract-exporter-independent-verifier-tests-hash-bound",
            "paths": {key: path.as_posix() for key, path in IMPLEMENTATION_PATHS.items()},
            **{f"{key}_sha256": _sha(_safe_file(root, path).read_bytes())
               for key, path in IMPLEMENTATION_PATHS.items()}}


def build_payload(root: Path, rom_bytes: bytes | None = None) -> dict:
    root = Path(root).resolve(strict=True)
    rom = _safe_file(root, ROM_PATH).read_bytes() if rom_bytes is None else rom_bytes
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("ROM identity")
    _, segments, starts = _load_precoverage(root)
    owner = _owner(segments, starts, ROOT_RANGE[0])
    if tuple(owner["range"]) != ROOT_RANGE or owner["primary_class"] != "unknown":
        raise ValueError("root current-unknown gate")
    producers = _producer_rows(rom, segments, starts)
    denominator = _root_denominator(rom, segments, starts)
    claim = {"id": "story-selector-reachable-thumb-code-01-08f544",
             "kind": "reachable_thumb_code", "mode": "thumb", "range": list(ROOT_RANGE),
             "bytes_sha256": ROOT_BYTES_SHA256, "baseline_unknown_only": True}
    promotion = {"promotion_batch": SCHEMA,
                 "primary_class": "armv4t_story_selector_dependency_cfg",
                 "claim_kind": "armv4t_story_selector_dependency_cfg_exact_bytes",
                 "ranges": [list(ROOT_RANGE)], "promotion_bytes": 80,
                 "claim_count": 1, "claims": [claim]}
    precoverage = {"artifact": PRECOVERAGE_DIR.as_posix(),
                   "manifest_sha256": PRECOVERAGE_MANIFEST_SHA256,
                   "archive_sha256": PRECOVERAGE_ARCHIVE_SHA256,
                   "raw_sha256": PRECOVERAGE_RAW_SHA256, **BASELINE}
    return {"schema": SCHEMA, "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE,
                "sha256": ROM_SHA256}, "precoverage": precoverage,
            "story_dependency": _dependency(root),
            "root": {"range": list(ROOT_RANGE), "raw_hex": ROOT_RAW_HEX,
                     "bytes_sha256": ROOT_BYTES_SHA256},
            "producer_denominator": {"scan_range": [0, ROM_SIZE], "stride": 2,
                "decoder_kinds": ["thumb_bl", "thumb_b", "thumb_bcond"],
                "internal_entry_range": list(ROOT_RANGE), "pointer_match_count": 0,
                "match_count": 2, "matches": producers},
            "accepted_producers": [producers[1]], "rejected_producers": [producers[0]],
            "target_local_denominator": denominator, "promotion": promotion,
            "coverage_projection": {"baseline_classified_bytes": BASELINE["classified_bytes"],
                "baseline_unknown_bytes": BASELINE["unknown_bytes"], "target_promoted_bytes": 80,
                "classified_bytes": BASELINE["classified_bytes"] + 80,
                "remaining_unknown_bytes": BASELINE["unknown_bytes"] - 80,
                "hole_bytes": 0, "frontier_count": 0},
            "implementation": _implementation(root),
            "scope": {"tier": 1, "raw_rom_redecoded": True,
                "direct_internal_entry_denominator_complete_for_bl_b_bcond": True,
                "root_pointer_denominator_count": 0, "current_unknown_bytes": 80,
                "natural_runtime_reachability": False, "callee_bodies_or_abi": False,
                "business_or_literal_semantics": False, "consumer_code_slice_instruction_membership": False,
                "adjacent_bytes_or_holes": False, "editing_writeback_relocation_or_free_space": False}}


def _publish_exclusive(source: Path, destination: Path) -> None:
    parent_fd = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            rename, flag = libc.renameatx_np, 0x00000004
        elif hasattr(libc, "renameat2"):
            rename, flag = libc.renameat2, 0x00000001
        else:
            raise OSError(errno.ENOTSUP, "atomic no-replace rename unavailable")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                           ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(parent_fd, os.fsencode(source.name), parent_fd,
                  os.fsencode(destination.name), flag):
            code = ctypes.get_errno()
            if code == errno.EEXIST:
                raise FileExistsError(code, os.strerror(code), destination)
            raise OSError(code, os.strerror(code), destination)
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def export(root: Path, output: Path) -> dict:
    root = Path(root).resolve(strict=True)
    lexical = (Path(output) if Path(output).is_absolute() else root / output).absolute()
    resolved = lexical.resolve(strict=False)
    allowed = (root / EXPERIMENT_OUTPUT_ROOT).resolve()
    official = (root / OFFICIAL_ARTIFACT).resolve(strict=False)
    if resolved != lexical or not (resolved.is_relative_to(allowed) or resolved == official):
        raise ValueError("unsafe output")
    if resolved.exists():
        raise ValueError("output already exists")
    payload = build_payload(root)
    payload_raw = _canonical(payload)
    receipt = resolved.relative_to(root).as_posix()
    from tools import verify_rom_story_selector_dependency_cfg as verifier
    manifest = {"schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,
                "artifact_status": "candidate", "rom": payload["rom"],
                "precoverage": payload["precoverage"], "story_dependency": payload["story_dependency"],
                "promotion": payload["promotion"], "coverage_projection": payload["coverage_projection"],
                "implementation": payload["implementation"], "scope": payload["scope"],
                "producer": {"command": ["python3", "-I", "-S",
                    "tools/export_rom_story_selector_dependency_cfg.py", "--root", ".", "--output", receipt]},
                "verifier": {"command": ["python3", "-I", "-S",
                    "tools/verify_rom_story_selector_dependency_cfg.py", "--root", ".", "--artifact", receipt],
                    "exit_code": None},
                "files": {PAYLOAD_NAME: {"sha256": _sha(payload_raw), "size": len(payload_raw)}}}
    resolved.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(dir=resolved.parent, prefix=f".{resolved.name}-"))
    try:
        for name, data in ((PAYLOAD_NAME, payload_raw),
                           (MANIFEST_NAME, _canonical(manifest))):
            with (stage / name).open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        report = verifier.verify_root(root, stage, expected_receipt_path=resolved)
        if not report["verified"]:
            raise ValueError(report["errors"])
        manifest["artifact_status"] = "accepted"
        manifest["verifier"].update({"exit_code": 0, "report": report})
        with (stage / MANIFEST_NAME).open("wb") as stream:
            stream.write(_canonical(manifest))
            stream.flush()
            os.fsync(stream.fileno())
        directory_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        try:
            _publish_exclusive(stage, resolved)
        except FileExistsError as error:
            raise ValueError("output already exists") from error
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
