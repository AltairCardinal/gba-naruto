#!/usr/bin/env python3
"""Independent raw-ROM verifier for the story-selector dependency CFG packet."""

from __future__ import annotations

import argparse
import bisect
import gzip
import hashlib
import json
import struct
import sys
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


def _safe(root: Path, relative: Path) -> Path:
    root = root.resolve(strict=True)
    candidate = root / relative
    for node in (candidate, *candidate.parents):
        if node == root.parent:
            break
        if node.is_symlink():
            raise ValueError("symlink input")
    candidate = candidate.resolve(strict=True)
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise ValueError("input escape")
    return candidate


def _coverage(root: Path) -> tuple[list[dict], list[int]]:
    manifest = _safe(root, PRECOVERAGE_DIR / MANIFEST_NAME).read_bytes()
    archive = _safe(root, PRECOVERAGE_DIR / "rom-byte-coverage.json.gz").read_bytes()
    if (len(manifest), _sha(manifest), len(archive), _sha(archive)) != (
            PRECOVERAGE_MANIFEST_SIZE, PRECOVERAGE_MANIFEST_SHA256,
            PRECOVERAGE_ARCHIVE_SIZE, PRECOVERAGE_ARCHIVE_SHA256):
        raise ValueError("precoverage container identity")
    raw = gzip.decompress(archive)
    if (len(raw), _sha(raw)) != (PRECOVERAGE_RAW_SIZE, PRECOVERAGE_RAW_SHA256):
        raise ValueError("precoverage payload identity")
    value = json.loads(raw)
    if any(value["summary"].get(key) != expected for key, expected in BASELINE.items()):
        raise ValueError("precoverage summary")
    segments = value["segments"]
    if (len(segments) != BASELINE["segment_count"] or segments[0]["range"][0] != 0
            or segments[-1]["range"][1] != ROM_SIZE
            or any(left["range"][1] != right["range"][0]
                   for left, right in zip(segments, segments[1:]))):
        raise ValueError("precoverage partition")
    return segments, [row["range"][0] for row in segments]


def _segment(segments: list[dict], starts: list[int], offset: int) -> dict:
    row = segments[bisect.bisect_right(starts, offset) - 1]
    if not row["range"][0] <= offset < row["range"][1]:
        raise ValueError("coverage lookup")
    return row


def _decode_control(raw: bytes, offset: int) -> tuple[int, str, int] | None:
    opcode = int.from_bytes(raw[offset:offset + 2], "little")
    if offset + 4 <= len(raw):
        suffix = int.from_bytes(raw[offset + 2:offset + 4], "little")
        if opcode >> 11 == 0x1E and suffix >> 11 == 0x1F:
            delta = ((opcode & 0x7FF) << 12) | ((suffix & 0x7FF) << 1)
            delta = delta - 0x800000 if delta & 0x400000 else delta
            return offset + 4 + delta, "bl", 4
    if opcode >> 11 == 0x1C:
        delta = (opcode & 0x7FF) << 1
        delta = delta - 0x1000 if delta & 0x800 else delta
        return offset + 4 + delta, "b", 2
    condition = (opcode >> 8) & 0xF
    if opcode >> 12 == 0xD and condition <= 0xD:
        delta = (opcode & 0xFF) << 1
        delta = delta - 0x200 if delta & 0x100 else delta
        return offset + 4 + delta, "bcond", 2
    return None


def _producer_denominator(rom: bytes, segments: list[dict], starts: list[int]) -> list[dict]:
    raw_matches = []
    for offset in range(0, ROM_SIZE - 1, 2):
        decoded = _decode_control(rom, offset)
        if decoded is not None and ROOT_RANGE[0] <= decoded[0] < ROOT_RANGE[1]:
            raw_matches.append((offset, *decoded))
    expected = [(0x08F676, ROOT_RANGE[0], "bl", 4), (0x08F8DE, ROOT_RANGE[0], "bl", 4)]
    if raw_matches != expected:
        raise ValueError("raw direct internal-entry denominator")
    pointer = struct.pack("<I", ROM_BASE + ROOT_RANGE[0] + 1)
    if any(rom[index:index + 4] == pointer for index in range(0, ROM_SIZE - 3)):
        raise ValueError("root pointer denominator")
    rows = []
    for match, frozen in zip(raw_matches, PRODUCERS):
        offset, target, kind, size = match
        _, raw_hex, raw_sha, window, window_hex, window_sha, accepted = frozen
        if (rom[offset:offset + size].hex(), _sha(rom[offset:offset + size]),
                rom[window[0]:window[1]].hex(), _sha(rom[window[0]:window[1]])) != (
                raw_hex, raw_sha, window_hex, window_sha):
            raise ValueError("producer byte evidence")
        owner = _segment(segments, starts, offset)
        if accepted:
            owner_range, owner_class, owner_claim, owner_sha = ACCEPTED_OWNER
            if (tuple(owner["range"]), owner["primary_class"], owner.get("primary_claim_ids"),
                    _sha(rom[owner_range[0]:owner_range[1]])) != (
                    owner_range, owner_class, [owner_claim], owner_sha):
                raise ValueError("accepted owner evidence")
            rejection = None
        else:
            if tuple(owner["range"]) != REJECTED_OWNER_RANGE or owner["primary_class"] != "unknown":
                raise ValueError("rejected owner evidence")
            rejection = "source_owner_not_instruction_only"
        rows.append({"file_offset": offset, "target_file_offset": target, "kind": kind,
                     "size": size, "raw_hex": raw_hex, "raw_sha256": raw_sha,
                     "window_range": list(window), "window_raw_hex": window_hex,
                     "window_sha256": window_sha, "coverage_owner_range": owner["range"],
                     "coverage_owner_class": owner["primary_class"],
                     "coverage_owner_claim_ids": owner.get("primary_claim_ids", []),
                     "accepted_as_root_proof": accepted, "rejection_reason": rejection})
    return rows


def _rebuild_root_cfg(rom: bytes) -> tuple[list[dict], list[tuple[int, int]], list[list], list[dict]]:
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    decoded = list(decoder.disasm(rom[ROOT_RANGE[0]:ROOT_RANGE[1]], ROOT_RANGE[0]))
    if (not decoded or len(decoded) != INSTRUCTION_COUNT
            or sum(instruction.size for instruction in decoded) != ROOT_RANGE[1] - ROOT_RANGE[0]
            or decoded[-1].address + decoded[-1].size != ROOT_RANGE[1]):
        raise ValueError("independent instruction denominator")
    vector = []
    instruction_map = {}
    for instruction in decoded:
        raw = rom[instruction.address:instruction.address + instruction.size]
        vector.append({"file_offset": instruction.address, "size": instruction.size,
                       "raw_hex": raw.hex(), "mnemonic": instruction.mnemonic,
                       "op_str": instruction.op_str, "bytes_sha256": _sha(raw)})
        instruction_map[instruction.address] = instruction
    digest = _sha(_canonical(vector))
    if digest != INSTRUCTION_VECTOR_SHA256:
        raise ValueError("independent instruction vector denominator")

    pending = [ROOT_RANGE[0]]
    visited = set()
    calls: list[tuple[int, int]] = []
    internal: list[list] = []
    frontier: list[dict] = []
    exits = set()
    while pending:
        offset = pending.pop()
        if offset in visited:
            continue
        instruction = instruction_map.get(offset)
        if instruction is None:
            frontier.append({"source": None, "target": offset, "reason": "non_instruction_target"})
            continue
        visited.add(offset)
        next_offset = offset + instruction.size
        direct = _decode_control(rom, offset)
        if direct is not None:
            target, kind, _ = direct
            if kind == "bl":
                calls.append((offset, target))
                if next_offset < ROOT_RANGE[1]:
                    pending.append(next_offset)
                elif next_offset == ROOT_RANGE[1]:
                    exits.add(next_offset)
            else:
                if ROOT_RANGE[0] <= target < ROOT_RANGE[1]:
                    pending.append(target)
                    internal.append([offset, target, kind])
                else:
                    frontier.append({"source": offset, "target": target,
                                     "reason": f"external_{kind}"})
                if kind == "bcond":
                    if next_offset < ROOT_RANGE[1]:
                        pending.append(next_offset)
                    elif next_offset == ROOT_RANGE[1]:
                        exits.add(next_offset)
            continue
        indirect = (instruction.mnemonic in {"bx", "blx", "tbb", "tbh"}
                    or (instruction.mnemonic == "pop" and "pc" in instruction.op_str)
                    or (instruction.mnemonic in {"mov", "movs", "ldr", "add", "adds"}
                        and instruction.op_str.lstrip().startswith("pc,")))
        if indirect:
            frontier.append({"source": offset, "target": None,
                             "reason": f"dynamic_{instruction.mnemonic}"})
        elif next_offset < ROOT_RANGE[1]:
            pending.append(next_offset)
        elif next_offset == ROOT_RANGE[1]:
            exits.add(next_offset)
    holes = [[instruction.address, instruction.address + instruction.size]
             for instruction in decoded if instruction.address not in visited]
    if (sorted(calls) != sorted(OPAQUE_CALLS) or internal or frontier or holes
            or exits != {ROOT_RANGE[1]}):
        raise ValueError("independent raw CFG denominator")

    literals = []
    for instruction in decoded:
        if instruction.size == 2:
            opcode = int.from_bytes(rom[instruction.address:instruction.address + 2], "little")
            if opcode & 0xF800 == 0x4800:
                target = ((instruction.address + 4) & ~3) + (opcode & 0xFF) * 4
                literals.append((instruction.address, target))
    if literals != [(LITERAL[0], LITERAL[3][0])]:
        raise ValueError("independent PC-relative literal denominator")
    return vector, calls, internal, frontier


def _denominator(rom: bytes, segments: list[dict], starts: list[int]) -> dict:
    root_raw = rom[ROOT_RANGE[0]:ROOT_RANGE[1]]
    if root_raw.hex() != ROOT_RAW_HEX or _sha(root_raw) != ROOT_BYTES_SHA256:
        raise ValueError("root identity")
    instruction_vector, rebuilt_calls, local_edges, frontiers = _rebuild_root_cfg(rom)
    calls = []
    for source, target in OPAQUE_CALLS:
        raw_hex, raw_sha, frozen_target, owner_range, owner_class, owner_claim = OPAQUE_SPECS[source]
        call_raw = rom[source:source + 4]
        owner = _segment(segments, starts, target)
        if (_decode_control(rom, source), call_raw.hex(), _sha(call_raw), tuple(owner["range"]),
                owner["primary_class"], owner.get("primary_claim_ids")) != (
                (frozen_target, "bl", 4), raw_hex, raw_sha, owner_range, owner_class, [owner_claim]):
            raise ValueError("opaque boundary evidence")
        calls.append({"source": source, "target": target, "raw_hex": raw_hex,
                      "raw_sha256": raw_sha, "coverage_owner_range": owner["range"],
                      "coverage_owner_class": owner_class, "coverage_owner_claim_ids": [owner_claim],
                      "owner_granularity": "coarse" if owner_class == "consumer_code_slice" else "exact"})
    source, source_hex, source_sha, literal_range, literal_hex, value, literal_sha = LITERAL
    source_raw = rom[source:source + 2]
    literal_raw = rom[literal_range[0]:literal_range[1]]
    opcode = int.from_bytes(source_raw, "little")
    resolved = ((source + 4) & ~3) + (opcode & 0xFF) * 4
    literal_owner = _segment(segments, starts, literal_range[0])
    if (opcode >> 11, resolved, source_raw.hex(), _sha(source_raw), literal_raw.hex(),
            int.from_bytes(literal_raw, "little"), _sha(literal_raw), tuple(literal_owner["range"]),
            literal_owner["primary_class"], literal_owner.get("primary_claim_ids")) != (
            9, literal_range[0], source_hex, source_sha, literal_hex, value, literal_sha,
            FALLTHROUGH[3], FALLTHROUGH[4], [FALLTHROUGH[5]]):
        raise ValueError("preowned literal evidence")
    fall_offset, fall_hex, fall_sha, fall_range, fall_class, fall_claim = FALLTHROUGH
    fall_raw = rom[fall_offset:fall_offset + 2]
    fall_owner = _segment(segments, starts, fall_offset)
    if (fall_raw.hex(), _sha(fall_raw), tuple(fall_owner["range"]), fall_owner["primary_class"],
            fall_owner.get("primary_claim_ids")) != (
            fall_hex, fall_sha, fall_range, fall_class, [fall_claim]):
        raise ValueError("fallthrough evidence")
    if [(row["source"], row["target"]) for row in calls] != rebuilt_calls:
        raise ValueError("independent opaque call denominator")
    return {"instruction_count": len(instruction_vector), "instruction_bytes": 80,
            "capstone_end_file_offset": ROOT_RANGE[1],
            "instruction_vector_sha256": _sha(_canonical(instruction_vector)),
            "opaque_call_count": len(calls), "opaque_calls": calls,
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


def _failure(error: Exception) -> dict:
    return {"schema": VERIFY_SCHEMA, "verified": False, "errors": [str(error)], "promotion_bytes": 0}


def verify_root(root: Path, artifact: Path, *, expected_receipt_path: Path | None = None) -> dict:
    try:
        root = Path(root).resolve(strict=True)
        artifact = (Path(artifact) if Path(artifact).is_absolute() else root / artifact).absolute()
        if (artifact.resolve(strict=False) != artifact or artifact.is_symlink() or not artifact.is_dir()
                or {node.name for node in artifact.iterdir()} != {PAYLOAD_NAME, MANIFEST_NAME}
                or any(node.is_symlink() or not node.is_file() for node in artifact.iterdir())):
            raise ValueError("artifact member set")
        payload_raw = (artifact / PAYLOAD_NAME).read_bytes()
        manifest_raw = (artifact / MANIFEST_NAME).read_bytes()
        payload, manifest = json.loads(payload_raw), json.loads(manifest_raw)
        if payload_raw != _canonical(payload) or manifest_raw != _canonical(manifest):
            raise ValueError("noncanonical JSON")
        rom = _safe(root, ROM_PATH).read_bytes()
        if (len(rom), _sha(rom)) != (ROM_SIZE, ROM_SHA256):
            raise ValueError("ROM identity")
        segments, starts = _coverage(root)
        root_owner = _segment(segments, starts, ROOT_RANGE[0])
        if tuple(root_owner["range"]) != ROOT_RANGE or root_owner["primary_class"] != "unknown":
            raise ValueError("current-unknown range")
        producers = _producer_denominator(rom, segments, starts)
        denominator = _denominator(rom, segments, starts)
        dep_manifest = _safe(root, STORY_ARTIFACT / MANIFEST_NAME).read_bytes()
        dep_payload = _safe(root, STORY_ARTIFACT / STORY_PAYLOAD_NAME).read_bytes()
        dep_verifier = _safe(root, STORY_VERIFIER).read_bytes()
        if (len(dep_manifest), _sha(dep_manifest), len(dep_payload), _sha(dep_payload),
                _sha(dep_verifier)) != (STORY_MANIFEST_SIZE, STORY_MANIFEST_SHA256,
                STORY_PAYLOAD_SIZE, STORY_PAYLOAD_SHA256, STORY_VERIFIER_SHA256):
            raise ValueError("story dependency identity")
        dependency = {"artifact": STORY_ARTIFACT.as_posix(),
                      "manifest_sha256": STORY_MANIFEST_SHA256,
                      "payload_sha256": STORY_PAYLOAD_SHA256,
                      "verifier_sha256": STORY_VERIFIER_SHA256,
                      "accepted_owner_claim_id": ACCEPTED_OWNER[2]}
        claim = {"id": "story-selector-reachable-thumb-code-01-08f544",
                 "kind": "reachable_thumb_code", "mode": "thumb", "range": list(ROOT_RANGE),
                 "bytes_sha256": ROOT_BYTES_SHA256, "baseline_unknown_only": True}
        promotion = {"promotion_batch": SCHEMA,
                     "primary_class": "armv4t_story_selector_dependency_cfg",
                     "claim_kind": "armv4t_story_selector_dependency_cfg_exact_bytes",
                     "ranges": [list(ROOT_RANGE)], "promotion_bytes": 80,
                     "claim_count": 1, "claims": [claim]}
        projection = {"baseline_classified_bytes": BASELINE["classified_bytes"],
                      "baseline_unknown_bytes": BASELINE["unknown_bytes"],
                      "target_promoted_bytes": 80, "classified_bytes": 6_202_809,
                      "remaining_unknown_bytes": 88_647, "hole_bytes": 0, "frontier_count": 0}
        precoverage = {"artifact": PRECOVERAGE_DIR.as_posix(),
                       "manifest_sha256": PRECOVERAGE_MANIFEST_SHA256,
                       "archive_sha256": PRECOVERAGE_ARCHIVE_SHA256,
                       "raw_sha256": PRECOVERAGE_RAW_SHA256, **BASELINE}
        implementation = {"binding": "contract-exporter-independent-verifier-tests-hash-bound",
                          "paths": {key: path.as_posix() for key, path in IMPLEMENTATION_PATHS.items()},
                          **{f"{key}_sha256": _sha(_safe(root, path).read_bytes())
                             for key, path in IMPLEMENTATION_PATHS.items()}}
        scope = {"tier": 1, "raw_rom_redecoded": True,
                 "direct_internal_entry_denominator_complete_for_bl_b_bcond": True,
                 "root_pointer_denominator_count": 0, "current_unknown_bytes": 80,
                 "natural_runtime_reachability": False, "callee_bodies_or_abi": False,
                 "business_or_literal_semantics": False,
                 "consumer_code_slice_instruction_membership": False,
                 "adjacent_bytes_or_holes": False,
                 "editing_writeback_relocation_or_free_space": False}
        expected = {"schema": SCHEMA,
                    "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},
                    "precoverage": precoverage, "story_dependency": dependency,
                    "root": {"range": list(ROOT_RANGE), "raw_hex": ROOT_RAW_HEX,
                             "bytes_sha256": ROOT_BYTES_SHA256},
                    "producer_denominator": {"scan_range": [0, ROM_SIZE], "stride": 2,
                        "decoder_kinds": ["thumb_bl", "thumb_b", "thumb_bcond"],
                        "internal_entry_range": list(ROOT_RANGE), "pointer_match_count": 0,
                        "match_count": 2, "matches": producers},
                    "accepted_producers": [producers[1]], "rejected_producers": [producers[0]],
                    "target_local_denominator": denominator, "promotion": promotion,
                    "coverage_projection": projection, "implementation": implementation,
                    "scope": scope}
        if payload != expected:
            raise ValueError("payload exact contract")
        expected_keys = {"schema", "rom", "precoverage", "story_dependency", "root",
                         "producer_denominator", "accepted_producers", "rejected_producers",
                         "target_local_denominator", "promotion", "coverage_projection",
                         "implementation", "scope"}
        if set(payload) != expected_keys:
            raise ValueError("payload key denominator")
        for key in ("rom", "precoverage", "story_dependency", "promotion",
                    "coverage_projection", "implementation", "scope"):
            if manifest.get(key) != payload[key]:
                raise ValueError("manifest projection")
        if manifest.get("files", {}).get(PAYLOAD_NAME) != {
                "sha256": _sha(payload_raw), "size": len(payload_raw)}:
            raise ValueError("manifest payload binding")
        receipt = Path(expected_receipt_path).absolute() if expected_receipt_path else artifact
        relative = receipt.relative_to(root).as_posix()
        export_command = ["python3", "-I", "-S", "tools/export_rom_story_selector_dependency_cfg.py",
                          "--root", ".", "--output", relative]
        verify_command = ["python3", "-I", "-S", "tools/verify_rom_story_selector_dependency_cfg.py",
                          "--root", ".", "--artifact", relative]
        if (manifest.get("schema"), manifest.get("artifact_schema"),
                manifest.get("producer", {}).get("command"),
                manifest.get("verifier", {}).get("command")) != (
                "git-artifact-promotion-v1", SCHEMA, export_command, verify_command):
            raise ValueError("manifest commands")
        success = {"schema": VERIFY_SCHEMA, "verified": True, "errors": [],
                   "rom_sha256": ROM_SHA256, "root_count": 1,
                   "producer_match_count": 2, "accepted_producer_count": 1,
                   "rejected_producer_count": 1, "instruction_count": 37,
                   "instruction_bytes": 80, "opaque_call_count": 3,
                   "preowned_literal_count": 1, "hole_count": 0, "frontier_count": 0,
                   "promotion_bytes": 80, "remaining_unknown_bytes": 88_647}
        if manifest.get("artifact_status") == "candidate":
            if manifest.get("verifier", {}).get("exit_code") is not None or "report" in manifest["verifier"]:
                raise ValueError("candidate receipt")
        elif manifest.get("artifact_status") == "accepted":
            if (manifest.get("verifier", {}).get("exit_code") != 0
                    or manifest["verifier"].get("report") != success):
                raise ValueError("accepted receipt")
        else:
            raise ValueError("artifact status")
        return success
    except Exception as error:
        return _failure(error)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = verify_root(args.root, args.artifact)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
