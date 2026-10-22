#!/usr/bin/env python3
"""Independently verify the overlap-aware CFG proven-roots v21 artifact."""

from __future__ import annotations

import argparse
import bisect
import gzip
import hashlib
import heapq
import json
import os
import stat
import struct
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _path in (PROJECT_ROOT, PROJECT_ROOT / "tools/_vendor"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from capstone import arm_const

from tools import rom_cfg_proven_roots_v21_contract as C
from tools.thumb_branch import decode_thumb_b, decode_thumb_bl


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _packed(rom: bytes, ranges) -> bytes:
    return b"".join(rom[start:end] for start, end in ranges)


def _vector_sha(value: Any) -> str:
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _file_identity(row):
    return (row.st_dev, row.st_ino, row.st_mode, row.st_size,
            row.st_mtime_ns, row.st_ctime_ns)


def _member_snapshot(directory_fd: int):
    names = {C.PAYLOAD_NAME, C.MANIFEST_NAME}
    if set(os.listdir(directory_fd)) != names:
        raise ValueError("artifact member denominator changed")
    result = {}
    for name in sorted(names):
        row = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(row.st_mode):
            raise ValueError(f"artifact member not regular: {name}")
        result[name] = _file_identity(row)
    return result


def _read_regular_at(directory_fd: int, name: str) -> bytes:
    file_fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                      dir_fd=directory_fd)
    try:
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"artifact member not regular: {name}")
        chunks = []
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(file_fd)
        named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (_file_identity(before) != _file_identity(after) or
                _file_identity(after) != _file_identity(named)):
            raise ValueError(f"artifact member changed: {name}")
        return b"".join(chunks)
    finally:
        os.close(file_fd)


def _read_repo_file(root: Path, relative: Path) -> bytes:
    root = Path(root).resolve(strict=True)
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("unsafe repository input")
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    directory_fd = os.open(root, flags)
    try:
        for part in relative.parts[:-1]:
            child_fd = os.open(part, flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = child_fd
        return _read_regular_at(directory_fd, relative.parts[-1])
    finally:
        os.close(directory_fd)


def _artifact_parts(root: Path, artifact: Path):
    value = Path(artifact)
    if ".." in value.parts:
        raise ValueError("unsafe artifact path")
    raw = value if value.is_absolute() else root / value
    absolute = Path(os.path.abspath(raw))
    try:
        return absolute, absolute.relative_to(root)
    except ValueError as error:
        raise ValueError("unsafe artifact path") from error


def _open_artifact(root: Path, artifact: Path):
    absolute, relative = _artifact_parts(root, artifact)
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    directory_fd = os.open(root, flags)
    try:
        for part in relative.parts:
            child_fd = os.open(part, flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = child_fd
        return absolute, directory_fd
    except Exception:
        os.close(directory_fd)
        raise


def _merge(ranges):
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _raw_baseline(root: Path):
    manifest = _read_repo_file(root, C.PRECOVERAGE / C.MANIFEST_NAME)
    archive = _read_repo_file(root, C.PRECOVERAGE / "rom-byte-coverage.json.gz")
    if (len(manifest), _sha(manifest), len(archive), _sha(archive)) != (
        C.PRECOVERAGE_MANIFEST_SIZE,
        C.PRECOVERAGE_MANIFEST_SHA256,
        C.PRECOVERAGE_ARCHIVE_SIZE,
        C.PRECOVERAGE_ARCHIVE_SHA256,
    ):
        raise ValueError("precoverage identity")
    raw = gzip.decompress(archive)
    if (len(raw), _sha(raw)) != (C.PRECOVERAGE_RAW_SIZE, C.PRECOVERAGE_RAW_SHA256):
        raise ValueError("precoverage raw identity")
    coverage = json.loads(raw)
    segments = coverage["segments"]
    if any(coverage["summary"].get(key) != value
           for key, value in C.PRECOVERAGE_SUMMARY.items()):
        raise ValueError("precoverage summary")
    if (len(segments) != C.PRECOVERAGE_SUMMARY["segment_count"] or
            segments[0]["range"][0] != 0 or
            segments[-1]["range"][1] != C.ROM_SIZE or
            any(segments[index]["range"][1] != segments[index + 1]["range"][0]
                for index in range(len(segments) - 1))):
        raise ValueError("precoverage partition")
    return segments, [row["range"][0] for row in segments]


def _owner(segments, starts, offset):
    row = segments[bisect.bisect_right(starts, offset) - 1]
    if not row["range"][0] <= offset < row["range"][1]:
        raise ValueError("coverage owner lookup")
    return row


def _rebuild_upstream(root: Path, rom: bytes, segments, starts):
    blobs = {}
    identities = {}
    for path, size, digest in C.UPSTREAM_IDENTITIES:
        raw = _read_repo_file(root, path)
        if (len(raw), _sha(raw)) != (size, digest):
            raise ValueError(f"upstream identity: {path}")
        blobs[path.as_posix()] = raw
        identities[path.as_posix()] = {"size": size, "sha256": digest}
    continuation = json.loads(blobs[
        "artifacts/rom-boot-interwork-continuation-v1/rom-boot-interwork-continuation.json"
    ])
    accepted = [row for row in continuation["promotion"]["claims"]
                if row["id"] == C.ACCEPTED_PRODUCER_CLAIM]
    if len(accepted) != 1 or accepted[0]["range"] != list(C.ACCEPTED_PRODUCER_RANGE):
        raise ValueError("accepted producer artifact claim")
    cfg = json.loads(blobs["artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json"])
    veneer = [row for row in cfg["blocks"] if row["id"] == C.OPAQUE_BLOCK_ID]
    if (len(veneer) != 1 or veneer[0]["range"] != list(C.OPAQUE_OWNER[:2]) or
            veneer[0]["bytes_sha256"] != _sha(rom[C.OPAQUE_OWNER[0]:C.OPAQUE_OWNER[1]])):
        raise ValueError("opaque veneer artifact record")
    expected_owners = (
        (0x06108A, C.ACCEPTED_PRODUCER_RANGE, C.ACCEPTED_PRODUCER_CLAIM,
         "armv4t_boot_interwork_continuation_code"),
        (0x06131C, C.REJECTED_PRODUCER_RANGE, C.REJECTED_PRODUCER_CLAIM,
         "consumer_code_slice"),
        (C.EXISTING_OWNER_RANGE[0], C.EXISTING_OWNER_RANGE, C.EXISTING_OWNER_CLAIM,
         "consumer_code_slice"),
        (C.OPAQUE_OWNER[0], C.OPAQUE_OWNER[:2], C.OPAQUE_OWNER[2],
         "armv4t_cfg_reachable_thumb_code"),
    )
    owner_rows = []
    for offset, expected_range, claim_id, primary_class in expected_owners:
        row = _owner(segments, starts, offset)
        if (tuple(row["range"]) != tuple(expected_range) or
                row.get("primary_claim_ids") != [claim_id] or
                row.get("primary_class") != primary_class):
            raise ValueError("upstream coverage owner")
        owner_rows.append({
            "file_offset": offset,
            "coverage_owner_range": list(expected_range),
            "coverage_owner_claim_id": claim_id,
            "coverage_owner_class": primary_class,
        })
    return {"identities": identities, "coverage_owners": owner_rows,
            "whole_upstream_verifiers_replayed": False}


def _decode_node(rom: bytes, offset: int, engine: Cs):
    instructions = tuple(engine.disasm(
        rom[offset:offset + 4], C.ROM_BASE + offset, count=1))
    if len(instructions) != 1:
        raise ValueError("raw closure decode")
    instruction = instructions[0]
    raw = rom[offset:offset + instruction.size]
    if instruction.size not in (2, 4) or (
            instruction.size == 4 and instruction.id != arm_const.ARM_INS_BL):
        raise ValueError("raw closure instruction")
    halfword = int.from_bytes(raw[:2], "little")
    edges = []
    frontiers = []
    target = None
    call = False
    conditional = False
    if instruction.size == 4:
        target = decode_thumb_bl(
            offset, halfword, int.from_bytes(raw[2:4], "little"))
        call = True
    elif halfword & 0xF000 == 0xD000 and ((halfword >> 8) & 15) < 14:
        displacement = (halfword & 0xFF) << 1
        if displacement & 0x100:
            displacement -= 0x200
        target = offset + 4 + displacement
        conditional = True
    else:
        target = decode_thumb_b(offset, halfword)
    if target is not None:
        edges.append(("call_target" if call else "branch_target", target))
        if call or conditional:
            edges.append(("fallthrough", offset + instruction.size))
        flow = "call" if call else (
            "conditional_branch" if conditional else "unconditional_branch")
    elif halfword & 0xFF87 == 0x4700:
        flow = "indirect_branch"
        frontiers.append("indirect_pc_target")
    elif instruction.id == arm_const.ARM_INS_SVC:
        flow = "supervisor_call"
        frontiers.append("bios_swi_external")
        edges.append(("fallthrough", offset + instruction.size))
    else:
        flow = "linear"
        edges.append(("fallthrough", offset + instruction.size))
    return {
        "offset": offset,
        "size": instruction.size,
        "raw_hex": raw.hex(),
        "mnemonic": instruction.mnemonic,
        "op_str": instruction.op_str,
        "flow": flow,
        "edges": edges,
        "frontiers": frontiers,
    }


def _direct_target(rom: bytes, offset: int):
    halfword = struct.unpack_from("<H", rom, offset)[0]
    if offset + 4 <= len(rom):
        target = decode_thumb_bl(
            offset, halfword, struct.unpack_from("<H", rom, offset + 2)[0])
        if target is not None:
            return target, "thumb_bl", 4
    if halfword & 0xF000 == 0xD000 and ((halfword >> 8) & 15) < 14:
        displacement = (halfword & 0xFF) << 1
        if displacement & 0x100:
            displacement -= 0x200
        return offset + 4 + displacement, "thumb_bcond", 2
    target = decode_thumb_b(offset, halfword)
    if target is not None:
        return target, "thumb_b", 2
    return None


def _rebuild_producers(rom: bytes, segments, starts):
    raw_matches = []
    for offset in range(0, len(rom) - 1, 2):
        decoded = _direct_target(rom, offset)
        if decoded and decoded[0] == C.ROOT:
            target, kind, size = decoded
            raw_matches.append([offset, target, kind, size,
                                rom[offset:offset + size].hex()])
    if raw_matches != [list(row[:5]) for row in C.PRODUCERS]:
        raise ValueError("raw producer denominator")
    matches = []
    for raw, frozen in zip(raw_matches, C.PRODUCERS):
        offset, target, kind, size, raw_hex = raw
        owner = _owner(segments, starts, offset)
        accepted = frozen[5]
        instruction_only = (
            owner.get("primary_claim_ids") == [C.ACCEPTED_PRODUCER_CLAIM] and
            tuple(owner["range"]) == C.ACCEPTED_PRODUCER_RANGE and
            owner.get("primary_class") == "armv4t_boot_interwork_continuation_code"
        )
        if accepted != instruction_only:
            if accepted:
                raise ValueError("accepted producer owner")
            if (tuple(owner["range"]) != C.REJECTED_PRODUCER_RANGE or
                    owner.get("primary_claim_ids") != [C.REJECTED_PRODUCER_CLAIM] or
                    owner.get("primary_class") != "consumer_code_slice"):
                raise ValueError("rejected producer owner")
        matches.append({
            "file_offset": offset,
            "target_file_offset": target,
            "kind": kind,
            "size": size,
            "raw_hex": raw_hex,
            "coverage_owner_range": owner["range"],
            "coverage_owner_class": owner["primary_class"],
            "coverage_owner_claim_ids": owner.get("primary_claim_ids", []),
            "instruction_only": instruction_only,
            "accepted_as_root_proof": accepted,
            "rejection_reason": (None if accepted
                                 else "coverage_owner_not_instruction_only"),
        })
    return matches


def _rebuild_cfg(rom: bytes, segments, starts):
    inside = lambda offset: any(start <= offset < end for start, end in C.CODE_RANGES)
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    engine.detail = True
    engine.skipdata = False
    pending = [C.ROOT]
    nodes = {}
    calls = []
    while pending:
        offset = heapq.heappop(pending)
        if offset in nodes:
            continue
        if offset % 2 or not inside(offset):
            raise ValueError("raw closure worklist escape")
        node = _decode_node(rom, offset, engine)
        nodes[offset] = node
        for kind, target in node["edges"]:
            if inside(target):
                heapq.heappush(pending, target)
            elif kind == "call_target":
                calls.append((offset, target))
            else:
                raise ValueError("raw closure outbound branch")
    frontiers = [{"source": offset, "reason": reason}
                 for offset, node in sorted(nodes.items())
                 for reason in node["frontiers"]]
    code = _merge((offset, offset + node["size"])
                  for offset, node in nodes.items())
    predecessors = {offset: [] for offset in nodes}
    for offset, node in nodes.items():
        for _, target in node["edges"]:
            if target in nodes:
                predecessors[target].append(offset)
    starts_set = {C.ROOT}
    for offset, incoming in predecessors.items():
        if offset == C.ROOT:
            continue
        if len(incoming) != 1:
            starts_set.add(offset)
            continue
        previous = nodes[incoming[0]]
        internal = [target for _, target in previous["edges"] if target in nodes]
        if (previous["flow"] != "linear" or internal != [offset] or
                incoming[0] + previous["size"] != offset):
            starts_set.add(offset)
    blocks = []
    for start in sorted(starts_set):
        offset = start
        while True:
            node = nodes[offset]
            internal = [target for _, target in node["edges"] if target in nodes]
            next_offset = offset + node["size"]
            if (node["flow"] != "linear" or internal != [next_offset] or
                    next_offset in starts_set):
                break
            offset = next_offset
        blocks.append([start, offset + nodes[offset]["size"]])
    bindings = []
    for offset, node in sorted(nodes.items()):
        halfword = int.from_bytes(rom[offset:offset + 2], "little")
        if node["size"] == 2 and halfword & 0xF800 == 0x4800:
            target = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
            bindings.append([offset, target, node["raw_hex"], rom[target:target + 4].hex()])
    literals = _merge((target, target + 4) for _, target, _, _ in bindings)
    metrics = {
        "instruction_count": len(nodes),
        "basic_block_count": len(blocks),
        "code_bytes": sum(node["size"] for node in nodes.values()),
        "literal_reference_count": len(bindings),
        "unique_literal_word_count": len({row[1] for row in bindings}),
        "literal_bytes": sum(end - start for start, end in literals),
        "opaque_call_count": len(calls),
        "opaque_unique_target_count": len({target for _, target in calls}),
        "structured_return_count": 0,
        "frontier_count": len(frontiers),
    }
    if (metrics != C.METRICS or tuple(map(tuple, code)) != C.CODE_RANGES or
            tuple(map(tuple, literals)) != C.LITERAL_RANGES or
            tuple(map(tuple, blocks)) != C.BLOCK_RANGES or
            tuple(calls) != C.OPAQUE_CALLS or tuple(frontiers) != C.FRONTIERS or
            _vector_sha(blocks) != C.BLOCK_RANGE_VECTOR_SHA256):
        raise ValueError("raw closure denominator")
    if (_sha(_packed(rom, C.CODE_RANGES)),
            _sha(_packed(rom, C.LITERAL_RANGES)),
            _sha(_packed(rom, C.CODE_RANGES) + _packed(rom, C.LITERAL_RANGES)),
            _sha(_packed(rom, C.UNKNOWN_CODE_RANGES + C.UNKNOWN_LITERAL_RANGES))) != (
                C.CODE_PACKED_SHA256, C.LITERAL_PACKED_SHA256,
                C.CODE_THEN_LITERAL_SHA256, C.PROMOTION_PACKED_SHA256):
        raise ValueError("raw closure identity")
    cross_start, cross_end = C.CROSS_OWNER_INSTRUCTION
    cross_node = nodes.get(cross_start)
    if (cross_node is None or cross_node["size"] != cross_end - cross_start or
            cross_node["raw_hex"] != C.CROSS_OWNER_INSTRUCTION_RAW_HEX or
            _sha(rom[cross_start:cross_end]) != C.CROSS_OWNER_INSTRUCTION_SHA256 or
            ("call_target", C.OPAQUE_CALLS[1][1]) not in cross_node["edges"]):
        raise ValueError("raw cross-owner instruction")
    epilogue_raw = rom[slice(*C.EPILOGUE)]
    stack_sites = {offset: node["raw_hex"] for offset, node in nodes.items()
                   if "sp" in node["op_str"] or node["mnemonic"] in ("push", "pop")}
    if (epilogue_raw.hex() != C.EPILOGUE_RAW_HEX or
            _sha(epilogue_raw) != C.EPILOGUE_SHA256 or
            stack_sites != C.STACK_SITES or nodes[0x06348E]["raw_hex"] != "0047" or
            nodes[0x06348E]["op_str"] != "r0"):
        raise ValueError("raw return candidate")
    opaque_owner = _owner(segments, starts, C.OPAQUE_OWNER[0])
    if (tuple(opaque_owner["range"]) != C.OPAQUE_OWNER[:2] or
            opaque_owner.get("primary_claim_ids") != [C.OPAQUE_OWNER[2]]):
        raise ValueError("raw opaque owner")
    return {
        **metrics,
        "code_ranges": code,
        "literal_ranges": literals,
        "blocks": blocks,
        "literal_bindings": bindings,
        "opaque_calls": [{"source": source, "target": target}
                         for source, target in calls],
        "opaque_target_owner": {
            "entry_file_offset": C.OPAQUE_OWNER[0],
            "coverage_owner_range": list(C.OPAQUE_OWNER[:2]),
            "coverage_owner_claim_id": C.OPAQUE_OWNER[2],
        },
        "frontiers": frontiers,
        "code_bytes_sha256": C.CODE_PACKED_SHA256,
        "literal_bytes_sha256": C.LITERAL_PACKED_SHA256,
        "code_then_literal_sha256": C.CODE_THEN_LITERAL_SHA256,
        "return_candidate": {
            "epilogue_range": list(C.EPILOGUE),
            "epilogue_sha256": C.EPILOGUE_SHA256,
            "terminal_branch": {"source": 0x06348E, "raw_hex": "0047", "register": "r0"},
            "observed_stack_site_count": len(stack_sites),
            "opaque_callee_stack_effects_proven": False,
            "structured_return_proven": False,
        },
    }


def _implementation(root: Path):
    return {key: {"path": path.as_posix(), "sha256": _sha(_read_repo_file(root, path))}
            for key, path in C.IMPLEMENTATION_PATHS.items()}


def _expected_payload(root: Path, rom: bytes):
    segments, starts = _raw_baseline(root)
    upstream = _rebuild_upstream(root, rom, segments, starts)
    producers = _rebuild_producers(rom, segments, starts)
    denominator = _rebuild_cfg(rom, segments, starts)
    ranges = C.UNKNOWN_CODE_RANGES + C.UNKNOWN_LITERAL_RANGES
    for start, end in ranges:
        offset = start
        while offset < end:
            owner = _owner(segments, starts, offset)
            if owner.get("primary_class") != "unknown" or owner.get("primary_claim_ids"):
                raise ValueError("raw promotion owner")
            offset = min(end, owner["range"][1])
    existing = _owner(segments, starts, C.EXISTING_OWNER_RANGE[0])
    if (tuple(existing["range"]) != C.EXISTING_OWNER_RANGE or
            existing.get("primary_claim_ids") != [C.EXISTING_OWNER_CLAIM] or
            existing.get("primary_class") != "consumer_code_slice"):
        raise ValueError("raw existing owner provenance")
    claims = [
        {
            "id": f"cfg-v21-{kind}-{index:02d}-{start:06x}",
            "kind": kind,
            "range": [start, end],
            "bytes_sha256": _sha(rom[start:end]),
            "baseline_unknown_only": True,
        }
        for kind, ranges in (
            ("reachable_thumb_code", C.UNKNOWN_CODE_RANGES),
            ("consumed_literal_words", C.UNKNOWN_LITERAL_RANGES),
        )
        for index, (start, end) in enumerate(ranges, 1)
    ]
    union = _merge(ranges)
    if len(claims) != 3 or sum(end - start for start, end in union) != 116:
        raise ValueError("raw promotion denominator")
    promotion = {
        "promotion_batch": C.SCHEMA,
        "primary_class": "armv4t_cfg_proven_roots_v21",
        "claim_kind": "armv4t_cfg_proven_roots_v21_exact_bytes",
        "code_ranges": [list(row) for row in C.UNKNOWN_CODE_RANGES],
        "literal_ranges": [list(row) for row in C.UNKNOWN_LITERAL_RANGES],
        "union_ranges": union,
        "code_bytes": 112,
        "literal_bytes": 4,
        "promotion_bytes": 116,
        "claim_count": 3,
        "claims": claims,
        "existing_owner_code_provenance_bytes": 32,
    }
    return {
        "schema": C.SCHEMA,
        "rom": {"path": C.ROM_PATH.as_posix(), "size": C.ROM_SIZE,
                "sha256": C.ROM_SHA256},
        "precoverage": {"artifact": C.PRECOVERAGE.as_posix(),
                        "manifest_sha256": C.PRECOVERAGE_MANIFEST_SHA256,
                        "archive_sha256": C.PRECOVERAGE_ARCHIVE_SHA256,
                        "raw_sha256": C.PRECOVERAGE_RAW_SHA256,
                        **C.PRECOVERAGE_SUMMARY},
        "upstream": upstream,
        "root": {"file_offset": C.ROOT, "entry_sha256": C.ROOT_ENTRY_SHA256,
                 "envelope": list(C.ENVELOPE), "envelope_sha256": C.ENVELOPE_SHA256},
        "producer_denominator": {
            "scan_range": [0, C.ROM_SIZE], "stride": 2,
            "decoder_kinds": ["thumb_bl", "thumb_b", "thumb_bcond"],
            "match_count": len(producers), "matches": producers,
        },
        "accepted_producers": [row for row in producers if row["accepted_as_root_proof"]],
        "rejected_producers": [row for row in producers if not row["accepted_as_root_proof"]],
        "target_local_denominator": denominator,
        "cross_owner_instruction": {
            "instruction_range": list(C.CROSS_OWNER_INSTRUCTION),
            "raw_hex": C.CROSS_OWNER_INSTRUCTION_RAW_HEX,
            "bytes_sha256": C.CROSS_OWNER_INSTRUCTION_SHA256,
            "source": C.CROSS_OWNER_INSTRUCTION[0],
            "target": C.OPAQUE_CALLS[1][1],
            "size": 4,
            "full_instruction_decoded": True,
            "existing_owner_range": list(C.EXISTING_OWNER_RANGE),
            "existing_owner_claim_id": C.EXISTING_OWNER_CLAIM,
            "existing_owner_prefix_range": [0x06347C, 0x06347E],
            "promoted_suffix_range": [0x06347E, 0x063480],
            "existing_owner_reclassified": False,
        },
        "promotion": promotion,
        "coverage_projection": {
            "baseline_classified_bytes": 6_202_729,
            "baseline_unknown_bytes": 88_727,
            "v21_promoted_bytes": 116,
            "classified_bytes": 6_202_845,
            "remaining_unknown_bytes": 88_611,
        },
        "implementation": _implementation(root),
        "scope": {
            "raw_rom_redecoded": True,
            "target_limited_direct_producer_denominator": True,
            "natural_runtime_reachability": False,
            "global_caller_or_code_exhaustiveness": False,
            "indirect_computed_or_ram_producers": False,
            "rejected_producer_validity": False,
            "frontier_target_or_structured_return": False,
            "opaque_callee_stack_or_memory_effects": False,
            "existing_owner_reclassification": False,
            "literal_business_semantics": False,
            "holes_alignment_padding_or_free_space": False,
            "editing_writeback_relocation_or_gameplay": False,
        },
    }


def _intended_relative(root: Path, artifact: Path) -> str:
    absolute, relative = _artifact_parts(root, artifact)
    allowed = root / C.EXPERIMENT_ROOT
    official = root / C.OFFICIAL_ARTIFACT
    if absolute != official and not (
            absolute != allowed and absolute.is_relative_to(allowed)):
        raise ValueError("intended artifact path outside allowed outputs")
    return relative.as_posix()


def _report(status, errors):
    okay = not errors
    return {
        "schema": C.VERIFY_SCHEMA,
        "verified": okay,
        "errors": errors,
        "contract_ok": okay,
        "artifact_status": status,
        "promotion_bytes": 116 if okay else None,
        "instruction_count": C.METRICS["instruction_count"] if okay else None,
        "frontier_count": C.METRICS["frontier_count"] if okay else None,
    }


def verify_artifact(root: Path, artifact: Path, *, intended_artifact=None):
    """Verify accepted outputs; candidates require a distinct explicit staging target."""
    errors = []
    status = None
    directory_fd = None
    try:
        root = Path(root).resolve(strict=True)
        artifact_absolute, directory_fd = _open_artifact(root, artifact)
        member_identities = _member_snapshot(directory_fd)
        payload_raw = _read_regular_at(directory_fd, C.PAYLOAD_NAME)
        manifest_raw = _read_regular_at(directory_fd, C.MANIFEST_NAME)
        payload = json.loads(payload_raw)
        manifest = json.loads(manifest_raw)
        if (payload_raw != _canonical(payload) or
                manifest_raw != _canonical(manifest)):
            raise ValueError("noncanonical artifact")
        rom = _read_repo_file(root, C.ROM_PATH)
        if (len(rom), _sha(rom), _sha(rom[slice(*C.ENVELOPE)])) != (
                C.ROM_SIZE, C.ROM_SHA256, C.ENVELOPE_SHA256):
            raise ValueError("ROM identity")
        expected_payload = _expected_payload(root, rom)
        if payload != expected_payload:
            raise ValueError("payload exact contract mismatch")
        intended = artifact if intended_artifact is None else intended_artifact
        relative = _intended_relative(root, intended)
        implementation = _implementation(root)
        verifier_command = ["python3", "tools/verify_rom_cfg_proven_roots_v21.py",
                            "--root", ".", "--artifact", relative]
        base = {
            "schema": "git-artifact-promotion-v1",
            "artifact_schema": C.SCHEMA,
            "files": {C.PAYLOAD_NAME: {"size": len(payload_raw),
                                             "sha256": _sha(payload_raw)}},
            "summary": {**C.METRICS, "promotion_bytes": 116, "claim_count": 3,
                        "existing_owner_code_provenance_bytes": 32},
            "implementation": implementation,
            "producer": {"command": [
                "python3", "tools/export_rom_cfg_proven_roots_v21.py", "--root", ".",
                "--output", relative]},
        }
        status = manifest.get("artifact_status")
        if status == "candidate":
            if (intended_artifact is None or
                    artifact_absolute == root / relative or
                    artifact_absolute == root / C.OFFICIAL_ARTIFACT):
                raise ValueError("candidate requires explicit unpublished staging verification")
            expected_manifest = {
                **base,
                "artifact_status": "candidate",
                "verifier": {"command": verifier_command, "exit_code": None},
            }
        elif status == "accepted":
            expected_manifest = {
                **base,
                "artifact_status": "accepted",
                "verifier": {"command": verifier_command, "exit_code": 0,
                             "report": _report("candidate", [])},
            }
        else:
            raise ValueError("artifact status contract")
        if manifest != expected_manifest:
            raise ValueError("manifest exact contract mismatch")
        if _member_snapshot(directory_fd) != member_identities:
            raise ValueError("artifact member identity changed during verification")
    except Exception as error:
        errors.append(str(error))
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
    return _report(status, errors)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--artifact", type=Path, default=C.OFFICIAL_ARTIFACT)
    arguments = parser.parse_args()
    report = verify_artifact(arguments.root, arguments.artifact)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
