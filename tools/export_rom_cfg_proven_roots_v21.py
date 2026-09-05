#!/usr/bin/env python3
"""Export the overlap-aware 0x063400 CFG proven-roots v21 packet."""

from __future__ import annotations

import argparse
import bisect
import ctypes
import errno
import gzip
import hashlib
import heapq
import json
import os
import secrets
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


def _read_repo_file(root: Path, relative: Path) -> bytes:
    root = root.resolve(strict=True)
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("unsafe repository input")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    directory_fd = os.open(root, directory_flags)
    try:
        for part in relative.parts[:-1]:
            child_fd = os.open(part, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = child_fd
        file_fd = os.open(
            relative.parts[-1], os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_fd,
        )
        try:
            before = os.fstat(file_fd)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("repository input is not regular")
            chunks = []
            while True:
                chunk = os.read(file_fd, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            after = os.fstat(file_fd)
            identity = lambda row: (row.st_dev, row.st_ino, row.st_size, row.st_mtime_ns)
            if identity(before) != identity(after):
                raise ValueError("repository input changed while reading")
            return b"".join(chunks)
        finally:
            os.close(file_fd)
    finally:
        os.close(directory_fd)


def _merge(ranges):
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _baseline(root: Path):
    manifest = _read_repo_file(root, C.PRECOVERAGE / C.MANIFEST_NAME)
    archive = _read_repo_file(root, C.PRECOVERAGE / "rom-byte-coverage.json.gz")
    if (len(manifest), _sha(manifest), len(archive), _sha(archive)) != (
        C.PRECOVERAGE_MANIFEST_SIZE,
        C.PRECOVERAGE_MANIFEST_SHA256,
        C.PRECOVERAGE_ARCHIVE_SIZE,
        C.PRECOVERAGE_ARCHIVE_SHA256,
    ):
        raise ValueError("precoverage identity changed")
    raw = gzip.decompress(archive)
    if (len(raw), _sha(raw)) != (C.PRECOVERAGE_RAW_SIZE, C.PRECOVERAGE_RAW_SHA256):
        raise ValueError("precoverage payload identity changed")
    coverage = json.loads(raw)
    segments = coverage["segments"]
    if any(coverage["summary"].get(key) != value
           for key, value in C.PRECOVERAGE_SUMMARY.items()):
        raise ValueError("precoverage summary changed")
    if (len(segments) != C.PRECOVERAGE_SUMMARY["segment_count"] or
            segments[0]["range"][0] != 0 or
            segments[-1]["range"][1] != C.ROM_SIZE or
            any(segments[index]["range"][1] != segments[index + 1]["range"][0]
                for index in range(len(segments) - 1))):
        raise ValueError("precoverage partition changed")
    return coverage, segments, [row["range"][0] for row in segments]


def _owner(segments, starts, offset):
    row = segments[bisect.bisect_right(starts, offset) - 1]
    if not row["range"][0] <= offset < row["range"][1]:
        raise ValueError("coverage owner lookup failed")
    return row


def _upstream(root: Path, rom: bytes, segments, starts):
    blobs = {}
    identities = {}
    for path, size, digest in C.UPSTREAM_IDENTITIES:
        raw = _read_repo_file(root, path)
        if (len(raw), _sha(raw)) != (size, digest):
            raise ValueError(f"upstream identity changed: {path}")
        blobs[path.as_posix()] = raw
        identities[path.as_posix()] = {"size": size, "sha256": digest}

    continuation = json.loads(blobs[
        "artifacts/rom-boot-interwork-continuation-v1/rom-boot-interwork-continuation.json"
    ])
    accepted = [row for row in continuation["promotion"]["claims"]
                if row["id"] == C.ACCEPTED_PRODUCER_CLAIM]
    if len(accepted) != 1 or accepted[0]["range"] != list(C.ACCEPTED_PRODUCER_RANGE):
        raise ValueError("accepted producer artifact claim changed")

    cfg = json.loads(blobs["artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json"])
    veneer = [row for row in cfg["blocks"] if row["id"] == C.OPAQUE_BLOCK_ID]
    if (len(veneer) != 1 or veneer[0]["range"] != list(C.OPAQUE_OWNER[:2]) or
            veneer[0]["bytes_sha256"] != _sha(
                rom[C.OPAQUE_OWNER[0]:C.OPAQUE_OWNER[1]])):
        raise ValueError("opaque veneer artifact record changed")

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
            raise ValueError("upstream coverage owner changed")
        owner_rows.append({
            "file_offset": offset,
            "coverage_owner_range": list(expected_range),
            "coverage_owner_claim_id": claim_id,
            "coverage_owner_class": primary_class,
        })
    return {"identities": identities, "coverage_owners": owner_rows,
            "whole_upstream_verifiers_replayed": False}


def _decode(rom: bytes, offset: int, engine: Cs):
    instructions = tuple(engine.disasm(
        rom[offset:offset + 4], C.ROM_BASE + offset, count=1))
    if len(instructions) != 1:
        raise ValueError("closure decode failure")
    instruction = instructions[0]
    raw = rom[offset:offset + instruction.size]
    if instruction.size not in (2, 4) or (
            instruction.size == 4 and instruction.id != arm_const.ARM_INS_BL):
        raise ValueError("closure unsupported instruction")
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
        "flow_kind": flow,
        "successors": edges,
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


def _producers(rom: bytes, segments, starts):
    raw_matches = []
    for offset in range(0, len(rom) - 1, 2):
        decoded = _direct_target(rom, offset)
        if decoded and decoded[0] == C.ROOT:
            target, kind, size = decoded
            raw_matches.append([offset, target, kind, size,
                                rom[offset:offset + size].hex()])
    if raw_matches != [list(row[:5]) for row in C.PRODUCERS]:
        raise ValueError("producer denominator changed")
    matches = []
    for raw, frozen in zip(raw_matches, C.PRODUCERS):
        offset, target, kind, size, raw_hex = raw
        owner = _owner(segments, starts, offset)
        expected_accepted = frozen[5]
        instruction_only = (
            owner.get("primary_claim_ids") == [C.ACCEPTED_PRODUCER_CLAIM] and
            tuple(owner["range"]) == C.ACCEPTED_PRODUCER_RANGE and
            owner.get("primary_class") == "armv4t_boot_interwork_continuation_code"
        )
        if expected_accepted != instruction_only:
            if expected_accepted:
                raise ValueError("accepted producer owner changed")
            if (tuple(owner["range"]) != C.REJECTED_PRODUCER_RANGE or
                    owner.get("primary_claim_ids") != [C.REJECTED_PRODUCER_CLAIM] or
                    owner.get("primary_class") != "consumer_code_slice"):
                raise ValueError("rejected producer owner changed")
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
            "accepted_as_root_proof": expected_accepted,
            "rejection_reason": (None if expected_accepted
                                 else "coverage_owner_not_instruction_only"),
        })
    return matches


def _cfg(rom: bytes, segments, starts):
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
            raise ValueError("closure worklist escaped")
        node = _decode(rom, offset, engine)
        nodes[offset] = node
        for kind, target in node["successors"]:
            if inside(target):
                heapq.heappush(pending, target)
            elif kind == "call_target":
                calls.append((offset, target))
            else:
                raise ValueError("closure non-call edge escaped")

    frontiers = [{"source": offset, "reason": reason}
                 for offset, node in sorted(nodes.items())
                 for reason in node["frontiers"]]
    code = _merge((offset, offset + node["size"])
                  for offset, node in nodes.items())
    predecessors = {offset: [] for offset in nodes}
    for offset, node in nodes.items():
        for _, target in node["successors"]:
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
        internal = [target for _, target in previous["successors"] if target in nodes]
        if (previous["flow_kind"] != "linear" or internal != [offset] or
                incoming[0] + previous["size"] != offset):
            starts_set.add(offset)
    blocks = []
    for start in sorted(starts_set):
        offset = start
        while True:
            node = nodes[offset]
            internal = [target for _, target in node["successors"] if target in nodes]
            next_offset = offset + node["size"]
            if (node["flow_kind"] != "linear" or internal != [next_offset] or
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
        raise ValueError("closure denominator changed")

    code_raw = _packed(rom, C.CODE_RANGES)
    literal_raw = _packed(rom, C.LITERAL_RANGES)
    promotion_raw = _packed(rom, C.UNKNOWN_CODE_RANGES + C.UNKNOWN_LITERAL_RANGES)
    if (_sha(code_raw), _sha(literal_raw), _sha(code_raw + literal_raw),
            _sha(promotion_raw)) != (
                C.CODE_PACKED_SHA256, C.LITERAL_PACKED_SHA256,
                C.CODE_THEN_LITERAL_SHA256, C.PROMOTION_PACKED_SHA256):
        raise ValueError("closure or literal identity changed")

    cross_start, cross_end = C.CROSS_OWNER_INSTRUCTION
    cross_node = nodes.get(cross_start)
    if (cross_node is None or cross_node["size"] != cross_end - cross_start or
            cross_node["raw_hex"] != C.CROSS_OWNER_INSTRUCTION_RAW_HEX or
            _sha(rom[cross_start:cross_end]) != C.CROSS_OWNER_INSTRUCTION_SHA256 or
            ("call_target", C.OPAQUE_CALLS[1][1]) not in cross_node["successors"]):
        raise ValueError("cross-owner instruction changed")

    epilogue_raw = rom[slice(*C.EPILOGUE)]
    stack_sites = {offset: node["raw_hex"] for offset, node in nodes.items()
                   if "sp" in node["op_str"] or node["mnemonic"] in ("push", "pop")}
    if (epilogue_raw.hex() != C.EPILOGUE_RAW_HEX or
            _sha(epilogue_raw) != C.EPILOGUE_SHA256 or
            stack_sites != C.STACK_SITES or
            nodes[0x06348E]["raw_hex"] != "0047" or
            nodes[0x06348E]["op_str"] != "r0"):
        raise ValueError("return candidate changed")

    opaque_owner = _owner(segments, starts, C.OPAQUE_OWNER[0])
    if (tuple(opaque_owner["range"]) != C.OPAQUE_OWNER[:2] or
            opaque_owner.get("primary_claim_ids") != [C.OPAQUE_OWNER[2]]):
        raise ValueError("opaque target owner changed")
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


def _build_from_rom(root: Path, rom: bytes, *, verify_rom_identity: bool = True):
    root = Path(root).resolve(strict=True)
    if len(rom) != C.ROM_SIZE or (verify_rom_identity and _sha(rom) != C.ROM_SHA256):
        raise ValueError("ROM identity changed")
    if (_sha(rom[slice(*C.ENVELOPE)]) != C.ENVELOPE_SHA256 or
            _sha(rom[C.ROOT:C.ROOT + 4]) != C.ROOT_ENTRY_SHA256):
        raise ValueError("closure envelope changed")
    _, segments, starts = _baseline(root)
    upstream = _upstream(root, rom, segments, starts)
    producers = _producers(rom, segments, starts)
    denominator = _cfg(rom, segments, starts)

    promotion_ranges = C.UNKNOWN_CODE_RANGES + C.UNKNOWN_LITERAL_RANGES
    for start, end in promotion_ranges:
        offset = start
        while offset < end:
            owner = _owner(segments, starts, offset)
            if owner.get("primary_class") != "unknown" or owner.get("primary_claim_ids"):
                raise ValueError("promotion range is not current unknown")
            offset = min(end, owner["range"][1])
    existing = _owner(segments, starts, C.EXISTING_OWNER_RANGE[0])
    if (tuple(existing["range"]) != C.EXISTING_OWNER_RANGE or
            existing.get("primary_claim_ids") != [C.EXISTING_OWNER_CLAIM] or
            existing.get("primary_class") != "consumer_code_slice"):
        raise ValueError("existing owner provenance changed")

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
    union = _merge(promotion_ranges)
    if len(claims) != 3 or sum(end - start for start, end in union) != 116:
        raise ValueError("promotion denominator changed")
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
    cross_owner = {
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
            "scan_range": [0, C.ROM_SIZE],
            "stride": 2,
            "decoder_kinds": ["thumb_bl", "thumb_b", "thumb_bcond"],
            "match_count": len(producers),
            "matches": producers,
        },
        "accepted_producers": [row for row in producers if row["accepted_as_root_proof"]],
        "rejected_producers": [row for row in producers if not row["accepted_as_root_proof"]],
        "target_local_denominator": denominator,
        "cross_owner_instruction": cross_owner,
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


def build_payload(root: Path):
    root = Path(root).resolve(strict=True)
    return _build_from_rom(root, _read_repo_file(root, C.ROM_PATH))


def _publish_exclusive_at(parent_fd: int, source_name: str, destination_name: str):
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename, flag = libc.renameatx_np, 0x4
    elif hasattr(libc, "renameat2"):
        rename, flag = libc.renameat2, 0x1
    else:
        raise OSError(errno.ENOTSUP, "atomic no-replace rename unavailable")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                       ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(parent_fd, os.fsencode(source_name), parent_fd,
              os.fsencode(destination_name), flag):
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            raise FileExistsError(destination_name)
        raise OSError(code, os.strerror(code), destination_name)
    os.fsync(parent_fd)


def _output_parent(root: Path, output: Path):
    requested = Path(output)
    if ".." in requested.parts:
        raise ValueError("unsafe output path")
    raw = requested if requested.is_absolute() else root / requested
    destination = Path(os.path.abspath(raw))
    try:
        relative = destination.relative_to(root)
    except ValueError as error:
        raise ValueError("unsafe output path") from error
    allowed = root / C.EXPERIMENT_ROOT
    official = root / C.OFFICIAL_ARTIFACT
    if destination != official and not (
            destination != allowed and destination.is_relative_to(allowed)):
        raise ValueError("unsafe output path")
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    directory_fd = os.open(root, flags)
    try:
        try:
            for part in relative.parts[:-1]:
                child_fd = os.open(part, flags, dir_fd=directory_fd)
                os.close(directory_fd)
                directory_fd = child_fd
        except OSError as error:
            raise ValueError("unsafe output parent") from error
        try:
            os.stat(relative.parts[-1], dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError(destination)
        return destination, directory_fd
    except Exception:
        os.close(directory_fd)
        raise


def _write_file_at(directory_fd: int, name: str, raw: bytes):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    file_fd = os.open(name, flags, 0o644, dir_fd=directory_fd)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(file_fd, view)
            if written <= 0:
                raise OSError("short artifact write")
            view = view[written:]
        os.fsync(file_fd)
    finally:
        os.close(file_fd)


def _replace_file_at(directory_fd: int, name: str, raw: bytes):
    temporary = f".{name}-{secrets.token_hex(8)}"
    try:
        _write_file_at(directory_fd, temporary, raw)
        os.replace(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        os.fsync(directory_fd)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def _remove_stage_at(parent_fd: int, name: str, identity):
    try:
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if ((named.st_dev, named.st_ino) != identity or
            not stat.S_ISDIR(named.st_mode)):
        return
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    directory_fd = os.open(name, flags, dir_fd=parent_fd)
    try:
        for child in os.listdir(directory_fd):
            os.unlink(child, dir_fd=directory_fd)
    finally:
        os.close(directory_fd)
    try:
        os.rmdir(name, dir_fd=parent_fd)
    except FileNotFoundError:
        pass


def export_artifact(root: Path, output: Path):
    from tools import verify_rom_cfg_proven_roots_v21 as independent_verifier

    root = Path(root).resolve(strict=True)
    destination, parent_fd = _output_parent(root, output)
    payload = build_payload(root)
    payload_raw = _canonical(payload)
    relative = destination.relative_to(root).as_posix()
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
    candidate = {**base, "artifact_status": "candidate",
                 "verifier": {"command": verifier_command, "exit_code": None}}
    stage_name = f".{destination.name}-{secrets.token_hex(12)}"
    stage_fd = None
    stage_identity = None
    published = False
    try:
        os.mkdir(stage_name, 0o700, dir_fd=parent_fd)
        named = os.stat(stage_name, dir_fd=parent_fd, follow_symlinks=False)
        stage_identity = (named.st_dev, named.st_ino)
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        stage_fd = os.open(stage_name, flags, dir_fd=parent_fd)
        opened = os.fstat(stage_fd)
        if (opened.st_dev, opened.st_ino) != stage_identity:
            raise ValueError("staging identity changed")
        _write_file_at(stage_fd, C.PAYLOAD_NAME, payload_raw)
        _write_file_at(stage_fd, C.MANIFEST_NAME, _canonical(candidate))
        os.fsync(stage_fd)
        os.fsync(parent_fd)
        report = independent_verifier.verify_artifact(
            root, destination.parent / stage_name, intended_artifact=destination)
        if not report.get("verified") or not report.get("contract_ok"):
            raise ValueError(f"independent verifier rejected candidate: {report.get('errors')}")
        _publish_exclusive_at(parent_fd, stage_name, destination.name)
        published = True
        named = os.stat(destination.name, dir_fd=parent_fd, follow_symlinks=False)
        published_identity = (named.st_dev, named.st_ino)
        opened = os.fstat(stage_fd)
        if (published_identity != stage_identity or
                published_identity != (opened.st_dev, opened.st_ino)):
            _remove_stage_at(parent_fd, destination.name, published_identity)
            raise ValueError("published artifact identity does not match verified staging")
        accepted = {**base, "artifact_status": "accepted",
                    "verifier": {"command": verifier_command,
                                 "exit_code": 0, "report": report}}
        _replace_file_at(stage_fd, C.MANIFEST_NAME, _canonical(accepted))
        accepted_members = independent_verifier._member_snapshot(stage_fd)
        final_report = independent_verifier.verify_artifact(root, destination)
        if not final_report.get("verified") or not final_report.get("contract_ok"):
            raise ValueError(
                f"independent verifier rejected accepted artifact: {final_report.get('errors')}")
        if independent_verifier._member_snapshot(stage_fd) != accepted_members:
            raise ValueError("published artifact member identity changed after verification")
        final_named = os.stat(destination.name, dir_fd=parent_fd, follow_symlinks=False)
        final_opened = os.fstat(stage_fd)
        if ((final_named.st_dev, final_named.st_ino) != stage_identity or
                (final_opened.st_dev, final_opened.st_ino) != stage_identity):
            raise ValueError("published artifact identity changed after final verification")
        stage_identity = None
    finally:
        if stage_fd is not None:
            os.close(stage_fd)
        if stage_identity is not None:
            _remove_stage_at(parent_fd,
                             destination.name if published else stage_name,
                             stage_identity)
        os.close(parent_fd)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=C.OFFICIAL_ARTIFACT)
    arguments = parser.parse_args()
    export_artifact(arguments.root, arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
