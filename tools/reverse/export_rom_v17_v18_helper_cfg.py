#!/usr/bin/env python3
"""Export the producer-bound V17/V18 helper bounded Thumb CFG."""

from __future__ import annotations

import argparse
from collections import Counter
import ctypes
import errno
import hashlib
import heapq
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _path in (PROJECT_ROOT, PROJECT_ROOT / "tools/_vendor"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs  # type: ignore

from tools.export_rom_cfg_proven_roots_v11 import (  # noqa: E402
    _build_blocks, _decode_one, _key, _merged_ranges,
)
from tools.rom_v17_v18_helper_cfg_contract import *  # noqa: E402,F403


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _vsha(value: Any) -> str:
    return _sha(json.dumps(value, separators=(",", ":"), sort_keys=True).encode())


def _packed(rom: bytes, ranges: Any) -> bytes:
    return b"".join(rom[start:end] for start, end in ranges)


def _inside(offset: int, ranges: Any = CODE_RANGES) -> bool:  # noqa: F405
    return any(start <= offset < end for start, end in ranges)


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


def _publish_exclusive(source: Path, destination: Path) -> None:
    source = source.absolute()
    destination = destination.absolute()
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
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                           ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(parent_fd, os.fsencode(source.name), parent_fd,
                  os.fsencode(destination.name), flag):
            code = ctypes.get_errno()
            if code == errno.EEXIST:
                raise FileExistsError(destination)
            raise OSError(code, os.strerror(code), destination)
    finally:
        os.close(parent_fd)


def _evidence(root: Path, rom: bytes) -> dict[str, Any]:
    for path, digest in EVIDENCE_FILES:  # noqa: F405
        if _sha(_safe_file(root, path).read_bytes()) != digest:
            raise ValueError(f"upstream evidence identity changed: {path}")

    source_claims = []
    for version in ("v17", "v18"):
        path = Path(f"artifacts/rom-cfg-proven-roots-{version}/"
                    f"rom-cfg-proven-roots-{version}.json")
        payload = json.loads(_safe_file(root, path).read_bytes())
        for claim in payload["promotion"]["claims"]:
            if claim.get("kind") == "reachable_thumb_code":
                source_claims.append({"artifact": version, **claim})
    expected_ids = {
        "cfg-v18-reachable_thumb_code-04-091114",
        "cfg-v18-reachable_thumb_code-05-091254",
        "cfg-v18-reachable_thumb_code-06-091350",
        "cfg-v18-reachable_thumb_code-07-0913bc",
        "cfg-v18-reachable_thumb_code-08-091440",
        "cfg-v18-reachable_thumb_code-09-0914d8",
        "cfg-v17-reachable_thumb_code-01-091676",
        "cfg-v17-reachable_thumb_code-02-0918f4",
        "cfg-v17-reachable_thumb_code-03-0919c8",
        "cfg-v17-reachable_thumb_code-04-091ab0",
        "cfg-v17-reachable_thumb_code-06-091b40",
        "cfg-v17-reachable_thumb_code-08-091c38",
        "cfg-v17-reachable_thumb_code-09-091d2c",
        "cfg-v17-reachable_thumb_code-10-091d88",
        "cfg-v17-reachable_thumb_code-12-091ea8",
        "cfg-v17-reachable_thumb_code-13-091f3c",
    }
    selected = [row for row in source_claims if row["id"] in expected_ids]
    if {row["id"] for row in selected} != expected_ids:
        raise ValueError("upstream producer owner denominator changed")
    for row in selected:
        start, end = row["range"]
        if _sha(rom[start:end]) != row["bytes_sha256"]:
            raise ValueError("upstream producer owner bytes changed")

    v2 = json.loads(_safe_file(
        root, Path("artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json")
    ).read_bytes())
    v2_targets = {0x064700, 0x09C574, 0x064A48, 0x09C110,
                  0x0655B4, 0x09C0E0, 0x062788, 0x066758, 0x095E8C}
    v2_owners = []
    for target in sorted(v2_targets):
        matches = [row for row in v2["blocks"]
                   if row["range"][0] <= target < row["range"][1]]
        if len(matches) != 1 or matches[0].get("mode") != "thumb":
            raise ValueError("opaque v2 exit owner changed")
        row = matches[0]
        start, end = row["range"]
        if _sha(rom[start:end]) != row["bytes_sha256"]:
            raise ValueError("opaque v2 exit owner bytes changed")
        v2_owners.append({"target": target, "artifact": "rom-cfg-inventory-v2",
                          "owner_id": row["id"], "range": row["range"],
                          "bytes_sha256": row["bytes_sha256"]})

    v6 = json.loads(_safe_file(
        root, Path("artifacts/rom-cfg-proven-roots-v6/rom-cfg-proven-roots-v6.json")
    ).read_bytes())
    matches = [row for row in v6["extension"]["blocks"]
               if row["range"][0] == 0x0906E4]
    if len(matches) != 1 or matches[0]["range"] != [0x0906E4, 0x0906FA]:
        raise ValueError("opaque v6 exit owner changed")
    v6_owner = {"target": 0x0906E4, "artifact": "rom-cfg-proven-roots-v6",
                "owner_id": matches[0]["id"], "range": matches[0]["range"],
                "bytes_sha256": matches[0]["bytes_sha256"]}

    scene = json.loads(_safe_file(
        root, Path("artifacts/scene-visual-composites-v1/scene-visual-composites.json")
    ).read_bytes())["code_evidence"]["allocator"]
    if scene != {"start": "0x080626B4", "end_exclusive": "0x08062768",
                 "size": 180,
                 "sha256": "bed7ee16174877d036a3999979b69651fabd7ba619d8bbeaef2f41602b6e44eb"}:
        raise ValueError("opaque scene exit owner changed")
    gpu = json.loads(_safe_file(
        root, Path("artifacts/rom-gpu-copy-queue-inventory-v1/"
                   "rom-gpu-copy-queue-inventory.json")
    ).read_bytes())["queue_abi"]["status_3_enqueue_helper"]
    if gpu != {"start": "0x08063604", "end_exclusive": "0x0806365C",
               "size": 88,
               "sha256": "1047025449c9094921f9e0b1229014cfb9f1ed9e4f919d87253bf62e3b57331a"}:
        raise ValueError("opaque GPU exit owner changed")

    m4a = json.loads(_safe_file(
        root, Path("artifacts/rom-m4a-byte-inventory-v1/manifest.json")
    ).read_bytes())
    wave = [row for row in m4a["claims"] if row["id"] == "m4a-wave-4851b4"]
    if len(wave) != 1 or wave[0]["range"] != [0x4851B4, 0x48938F] \
            or wave[0]["semantic_class"] != "m4a_directsound_wave":
        raise ValueError("producer data false-positive owner changed")

    return {
        "status": "identity_bound_upstream_evidence",
        "files": {path.as_posix(): digest for path, digest in EVIDENCE_FILES},
        "producer_source_claims": sorted(selected, key=lambda row: row["id"]),
        "opaque_target_owners": [*v2_owners, v6_owner,
            {"target": 0x0626B4, "artifact": "scene-visual-composites-v1", **scene},
            {"target": 0x063604, "artifact": "rom-gpu-copy-queue-inventory-v1", **gpu}],
        "data_false_positive_owner": wave[0],
    }


def _direct_target(rom: bytes, offset: int) -> tuple[int, str, int] | None:
    first = struct.unpack_from("<H", rom, offset)[0]
    if first & 0xF800 == 0xF000 and offset + 4 <= len(rom):
        second = struct.unpack_from("<H", rom, offset + 2)[0]
        if second & 0xF800 == 0xF800:
            delta = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
            if delta & (1 << 22):
                delta -= 1 << 23
            return offset + 4 + delta, "bl", 4
    if first & 0xF800 == 0xE000:
        delta = (first & 0x7FF) << 1
        if delta & 0x800:
            delta -= 0x1000
        return offset + 4 + delta, "b", 2
    condition = (first >> 8) & 0xF
    if first & 0xF000 == 0xD000 and condition < 14:
        delta = (first & 0xFF) << 1
        if delta & 0x100:
            delta -= 0x200
        return offset + 4 + delta, "bcond", 2
    return None


def _producer_denominator(rom: bytes, evidence: dict[str, Any]) -> dict[str, Any]:
    roots = set(ROOTS)  # noqa: F405
    all_rows, root_rows, code_rows = [], [], []
    counts: Counter[str] = Counter()
    for offset in range(0, len(rom) - 1, 2):
        decoded = _direct_target(rom, offset)
        if decoded is None or not 0 <= decoded[0] < len(rom):
            continue
        target, kind, size = decoded
        row = [offset, target, kind, size, rom[offset:offset + size].hex()]
        all_rows.append(row)
        counts[kind] += 1
        if target in roots:
            root_rows.append(row)
        if _inside(target):
            code_rows.append(row)
    if dict(counts) != DIRECT_BRANCH_COUNTS or len(all_rows) != 99_909:  # noqa: F405
        raise ValueError("producer scan count changed")
    if _vsha(all_rows) != DIRECT_BRANCH_VECTOR_SHA256:  # noqa: F405
        raise ValueError("producer scan vector changed")
    if len(root_rows) != 34 or _vsha(root_rows) != ROOT_MATCH_VECTOR_SHA256:  # noqa: F405
        raise ValueError("producer root denominator changed")
    internal = [row for row in code_rows if _inside(row[0])]
    external = [row for row in code_rows if not _inside(row[0])]
    if (len(code_rows), len(internal), len(external)) != (66, 31, 35) \
            or _vsha(code_rows) != CODE_MATCH_VECTOR_SHA256 \
            or _vsha(internal) != INTERNAL_MATCH_VECTOR_SHA256 \
            or _vsha(external) != EXTERNAL_MATCH_VECTOR_SHA256:  # noqa: F405
        raise ValueError("producer code-target denominator changed")

    source_claims = evidence["producer_source_claims"]
    accepted, rejected = [], []
    for row in root_rows:
        owners = [claim for claim in source_claims
                  if claim["range"][0] <= row[0]
                  and row[0] + row[3] <= claim["range"][1]]
        record = {"file_offset": row[0], "target_file_offset": row[1],
                  "kind": row[2], "size": row[3], "raw_hex": row[4]}
        if len(owners) == 1:
            accepted.append({**record, "owner_artifact": owners[0]["artifact"],
                             "owner_claim_id": owners[0]["id"],
                             "accepted_as_root_proof": True})
        else:
            rejected.append({**record, "reason": "source_owner_unbound",
                             "accepted_as_root_proof": False})
    if len(accepted) != 33 or len(rejected) != 1 \
            or tuple(rejected[0][key] for key in
                     ("file_offset", "target_file_offset", "kind", "size", "raw_hex")) \
            != UNBOUND_PRODUCER:  # noqa: F405
        raise ValueError("producer accepted/unbound partition changed")
    false_rows = [row for row in external
                  if tuple(row) == DATA_FALSE_POSITIVE]  # noqa: F405
    if len(false_rows) != 1:
        raise ValueError("producer data false-positive changed")
    false_positive = {"file_offset": false_rows[0][0],
                      "target_file_offset": false_rows[0][1],
                      "kind": false_rows[0][2], "size": false_rows[0][3],
                      "raw_hex": false_rows[0][4],
                      "reason": "source_owned_by_m4a_directsound_wave",
                      "accepted_as_root_proof": False}
    if sorted(row[0] for row in external) != sorted(
            [row["file_offset"] for row in accepted]
            + [rejected[0]["file_offset"], false_positive["file_offset"]]):
        raise ValueError("producer external partition changed")
    return {
        "scan_range": [0, len(rom)], "stride": 2,
        "decoder_kinds": ["thumb_bl", "thumb_b", "thumb_bcond"],
        "decoded_direct_branch_count": len(all_rows),
        "decoded_kind_counts": dict(sorted(counts.items())),
        "direct_branch_vector_sha256": _vsha(all_rows),
        "root_match_count": len(root_rows),
        "root_match_vector_sha256": _vsha(root_rows),
        "accepted_root_producer_count": len(accepted),
        "accepted_root_producers": accepted,
        "rejected_unbound_root_producer_count": len(rejected),
        "rejected_unbound_root_producers": rejected,
        "internal_code_edge_count": len(internal),
        "external_code_match_count": len(external),
        "rejected_data_false_positive_count": 1,
        "rejected_data_false_positives": [false_positive],
    }


def _structured_returns(rom: bytes,
                        nodes: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
    for root, terminal, raw_hex in REGISTER_RETURNS:  # noqa: F405
        if struct.unpack_from("<H", rom, root)[0] & 0x0100 == 0:
            raise ValueError("structured return prologue changed")
        if rom[terminal - 2:terminal + 2].hex() != raw_hex \
                or ("thumb", terminal) not in nodes:
            raise ValueError("structured return epilogue changed")
    root, terminal, raw_hex = LR_RETURN  # noqa: F405
    if rom[terminal:terminal + 2].hex() != raw_hex or ("thumb", terminal) not in nodes:
        raise ValueError("structured leaf return changed")
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    observed = []
    for (_, offset), node in sorted(nodes.items()):
        row = next(iter(engine.disasm(rom[offset:offset + node["size"]],
                                      ROM_BASE + offset, count=1)), None)  # noqa: F405
        if row is None or row.size != node["size"]:
            raise ValueError("structured return Capstone confirmation changed")
        if "sp" in row.op_str:
            observed.append((offset, row.mnemonic, row.op_str))
    if tuple(observed) != SP_OPERAND_VECTOR:  # noqa: F405
        raise ValueError("structured return SP operand denominator changed")
    if rom[0x09C0E0:0x09C0E4].hex() != "0bdf7047":
        raise ValueError("structured return LZ77 SWI wrapper changed")
    return {
        "register_return_count": len(REGISTER_RETURNS),  # noqa: F405
        "leaf_lr_return_count": 1,
        "register_return_sites": [terminal for _, terminal, _ in REGISTER_RETURNS],  # noqa: F405
        "leaf_lr_return_site": terminal,
        "sp_operand_sites": [row[0] for row in observed],
        "stack_source_alias_sites": [0x0909C4, 0x0909D6],
        "lz77_swi_callsite": 0x0909DA,
        "lz77_swi_wrapper": 0x09C0E0,
        "lz77_swi": 0x0B,
        "stack_source_offset": 0x14,
        "saved_lr_offset": 0x34,
        "source_only": True,
        "saved_lr_slot_written": False,
    }


def _closure(rom: bytes) -> dict[str, Any]:
    pending: list[tuple[int, int, str]] = []
    scheduled: set[tuple[str, int]] = set()
    for root in ROOTS:  # noqa: F405
        heapq.heappush(pending, _key("thumb", root))
        scheduled.add(("thumb", root))
    nodes: dict[tuple[str, int], dict[str, Any]] = {}
    exits: list[list[int]] = []
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in nodes:
            continue
        if mode != "thumb" or not _inside(offset):
            raise ValueError("closure worklist escaped frozen ranges")
        decoded = _decode_one(rom, offset, mode)
        if not decoded["accepted"]:
            raise ValueError("closure decoder rejected instruction")
        nodes[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            if target[0] == "thumb" and _inside(target[1]):
                if target not in scheduled:
                    heapq.heappush(pending, _key(*target))
                    scheduled.add(target)
            elif edge["kind"] == "call_target":
                exits.append([offset, target[1]])
            else:
                raise ValueError("closure non-call edge escaped frozen ranges")
    blocks, _ = _build_blocks(rom, nodes, {("thumb", root) for root in ROOTS})  # noqa: F405
    code = _merged_ranges(nodes)
    bindings = []
    for (_, offset), node in sorted(nodes.items()):
        if node["size"] != 2:
            continue
        halfword = struct.unpack_from("<H", rom, offset)[0]
        if halfword & 0xF800 == 0x4800:
            literal = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
            if any(start <= literal and literal + 4 <= end
                   for start, end in LITERAL_RANGES):  # noqa: F405
                bindings.append([offset, literal, rom[offset:offset + 2].hex(),
                                 rom[literal:literal + 4].hex()])
    literals = []
    for literal in sorted({row[1] for row in bindings}):
        if literals and literal <= literals[-1][1]:
            literals[-1][1] = max(literals[-1][1], literal + 4)
        else:
            literals.append([literal, literal + 4])
    exits.sort()
    if exits != [list(row) for row in OPAQUE_EXITS]:  # noqa: F405
        raise ValueError("closure exit denominator changed")
    if code != [list(row) for row in CODE_RANGES] or len(nodes) != 575:  # noqa: F405
        raise ValueError("closure code denominator changed")
    if len(blocks) != 81:
        raise ValueError("closure block denominator changed")
    if literals != [list(row) for row in LITERAL_RANGES] or len(bindings) != 14:  # noqa: F405
        raise ValueError("literal denominator changed")
    if _sha(_packed(rom, LITERAL_RANGES)) != LITERAL_SHA256 \
            or _vsha(bindings) != LITERAL_BINDING_SHA256:  # noqa: F405
        raise ValueError("literal identity changed")
    if _sha(_packed(rom, HOLES)) != HOLE_SHA256:  # noqa: F405
        raise ValueError("hole identity changed")
    if _sha(_packed(rom, CODE_RANGES)) != CODE_SHA256:  # noqa: F405
        raise ValueError("closure byte identity changed")
    returns = _structured_returns(rom, nodes)
    raw_frontiers = [(offset, row["frontiers"])
                     for (_, offset), row in nodes.items() if row["frontiers"]]
    expected_frontiers = {terminal for _, terminal, _ in REGISTER_RETURNS}  # noqa: F405
    if {offset for offset, _ in raw_frontiers} != expected_frontiers:
        raise ValueError("structured return frontier denominator changed")
    flow = Counter(row["flow_kind"] for row in nodes.values())
    flow["return"] += flow.pop("indirect_branch", 0)
    expected_flow = {"call": 24, "conditional_branch": 24, "linear": 509,
                     "return": 11, "unconditional_branch": 7}
    if dict(sorted(flow.items())) != dict(sorted(expected_flow.items())):
        raise ValueError("closure flow denominator changed")
    return {
        "roots": list(ROOTS), "root_count": len(ROOTS),  # noqa: F405
        "root_vector_sha256": _vsha(list(ROOTS)),  # noqa: F405
        "instruction_count": len(nodes), "basic_block_count": len(blocks),
        "code_bytes": 1198, "code_ranges": code, "code_sha256": CODE_SHA256,  # noqa: F405
        "literal_reference_count": len(bindings),
        "unique_literal_word_count": len({row[1] for row in bindings}),
        "literal_bytes": 56, "literal_ranges": literals,
        "literal_sha256": LITERAL_SHA256,  # noqa: F405
        "opaque_accepted_exits": exits,
        "opaque_accepted_exit_count": len(exits),
        "structured_return_count": 11,
        "structured_return_contract": returns,
        "flow_kind_counts": dict(sorted(flow.items())), "frontier_count": 0,
        "preserved_unknown_holes": [list(row) for row in HOLES],  # noqa: F405
        "preserved_unknown_bytes": 12,
    }


def _build_from_rom(root: Path, rom: bytes, *, verify_identity: bool = True) -> dict[str, Any]:
    if verify_identity and (len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256):  # noqa: F405
        raise ValueError("ROM identity changed")
    evidence = _evidence(root, rom)
    closure = _closure(rom)
    producers = _producer_denominator(rom, evidence)
    claims = []
    for kind, ranges in (("reachable_thumb_code", CODE_RANGES),  # noqa: F405
                         ("consumed_literal_words", LITERAL_RANGES)):  # noqa: F405
        for index, (start, end) in enumerate(ranges, 1):
            claims.append({"id": f"v17-v18-helper-{kind}-{index:02d}-{start:06x}",
                           "range": [start, end], "claim_kind": kind,
                           "bytes_sha256": _sha(rom[start:end])})
    return {
        "schema": SCHEMA,  # noqa: F405
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom),  # noqa: F405
                "sha256": ROM_SHA256},  # noqa: F405
        "upstream_evidence": evidence,
        "producer_denominator": producers,
        "target_closure": closure,
        "promotion": {"promotion_batch": SCHEMA,  # noqa: F405
                      "promoted_from_primary_class": "unknown",
                      "claims": claims, "claim_count": 14,
                      "target_code_bytes": 1198,
                      "target_literal_bytes": 56,
                      "promotion_bytes": 1254},
        "scope": {"natural_runtime_reachability": False,
                  "all_inbound_producers_accepted": False,
                  "indirect_or_computed_producer_exhaustiveness": False,
                  "business_semantics_or_abi": False,
                  "padding_or_free_space": False,
                  "editing_or_relocation_safety": False},
    }


def build_payload(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    return _build_from_rom(root, _safe_file(root, ROM_PATH).read_bytes())  # noqa: F405


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
    relative_output = output.relative_to(root)
    if relative_output != OFFICIAL and relative_output.parts[:2] != (  # noqa: F405
            "build", "experiments"):
        raise ValueError("staging output must be under build/experiments")
    raw = _canonical(build_payload(root))
    exporter = Path("tools/export_rom_v17_v18_helper_cfg.py")
    verifier = Path("tools/verify_rom_v17_v18_helper_cfg.py")
    test = Path("tests/test_export_rom_v17_v18_helper_cfg.py")
    # The immutable receipt names the committed destination, even while the
    # bytes are first assembled in an ignored experiment staging directory.
    relative = OFFICIAL.as_posix()  # noqa: F405
    manifest = {
        "schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,  # noqa: F405
        "artifact_status": "accepted",
        "canonical_destination": OFFICIAL.as_posix(),  # noqa: F405
        "artifact_portability": "content_verified_independent_of_copy_path",
        "files": {PAYLOAD_NAME: {"size": len(raw), "sha256": _sha(raw)}},  # noqa: F405
        "summary": {"root_count": 11, "promotion_bytes": 1254,
                    "frontier_count": 0,
                    "accepted_root_producer_count": 33,
                    "rejected_unbound_root_producer_count": 1},
        "producer": {"command": ["python3", exporter.as_posix(), "--root", ".",
                                  "--output", relative],
                     "command_role": "canonical_reproduction_recipe"},
        "verifier": {"command": ["python3", verifier.as_posix(), "--root", ".",
                                  "--artifact", relative],
                     "command_role": "canonical_reproduction_recipe",
                     "exit_code": 0},
        "implementation": {
            "contract_sha256": _sha(_safe_file(
                root, Path("tools/rom_v17_v18_helper_cfg_contract.py")).read_bytes()),
            "exporter_sha256": _sha(_safe_file(root, exporter).read_bytes()),
            "verifier_sha256": _sha(_safe_file(root, verifier).read_bytes()),
            "test_sha256": _sha(_safe_file(root, test).read_bytes())},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".v17-v18-helper-") as directory:
        stage = Path(directory)
        (stage / PAYLOAD_NAME).write_bytes(raw)  # noqa: F405
        (stage / MANIFEST_NAME).write_bytes(_canonical(manifest))  # noqa: F405
        from tools.verify_rom_v17_v18_helper_cfg import verify_artifact
        report = verify_artifact(root, stage, expected_artifact=root / OFFICIAL)  # noqa: F405
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
