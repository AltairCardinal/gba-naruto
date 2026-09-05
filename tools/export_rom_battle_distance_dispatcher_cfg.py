#!/usr/bin/env python3
"""Export the fixed seven-way battle-distance dispatcher bounded CFG."""

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
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.export_rom_cfg_proven_roots_v11 import (
    _build_blocks, _decode_one, _key, _merged_ranges,
)


SCHEMA = "rom-battle-distance-dispatcher-cfg-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
OFFICIAL = Path("artifacts/rom-battle-distance-dispatcher-cfg-v1")
PAYLOAD_NAME = "rom-battle-distance-dispatcher-cfg.json"
MANIFEST_NAME = "manifest.json"

UPSTREAM = Path("artifacts/rom-cfg-proven-roots-v2")
UPSTREAM_FILES = (
    (UPSTREAM / MANIFEST_NAME,
     "a3683f3d21ec5a162b4cdb97c70b639ff261d9ff5e0f3bb4941848205bb4d9ca"),
    (UPSTREAM / "rom-cfg-proven-roots-v2.json",
     "a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba"),
    (Path("tools/verify_rom_cfg_proven_roots_v2.py"),
     "3d834e1e92c1ea1c7cf4146ac6f23b940ea864c69783c341af64ba462545fe55"),
    (Path("artifacts/rom-cfg-proven-roots-batch-consumed-literals-v1/manifest.json"),
     "8688e87bdec227322a7b27f2d2feb84428f3ff82e4c782348db2c33b125e2d5f"),
    (Path("artifacts/rom-cfg-proven-roots-batch-consumed-literals-v1/rom-cfg-proven-roots-batch-consumed-literals.json"),
     "35efe834638717ce963af95343bcccfc70311b0a124718c2e732263880fbc4d0"),
    (Path("tools/verify_rom_cfg_proven_roots_batch_consumed_literals.py"),
     "36dceec30462bd3b55910d577d5eea277ef5f0da362915d1ab11237ce7d591ca"),
)

DISPATCHER_CODE = (0x083B3C, 0x083B4E)
DISPATCHER_CODE_SHA256 = "7ea90d4beeeb4a31cbe17cb0b69c1a0097180f13c5a3b21e6f4bff464e952ad2"
DISPATCHER_LITERAL = (0x083B50, 0x083B5C)
DISPATCHER_LITERAL_SHA256 = "1c310bbbd162171998503b80ac7d20291572c071aec0aec321cb7514328f7142"
TABLE_RANGE = (0x083B5C, 0x083B78)
TABLE_SHA256 = "0186fb9894e0c12d8d8b2b9e0c5191f47dbe16041427105fde3edfbb04a0cfde"
ROOTS = (0x083B78, 0x083BAC, 0x083C8A, 0x083D20,
         0x083DAE, 0x083E38, 0x083F0E)
BOUND = (0x083B78, 0x083FEA)
OPAQUE_BASELINE_TARGETS = (0x083FEA, 0x083FFA)

CODE_RANGES = (
    (0x083B78, 0x083DFC), (0x083E00, 0x083F04),
    (0x083F08, 0x083F52), (0x083F58, 0x083F64),
    (0x083F68, 0x083FBE), (0x083FC4, 0x083FD8),
    (0x083FDC, 0x083FEA),
)
LITERAL_RANGES = (
    (0x083DFC, 0x083E00), (0x083F04, 0x083F08),
    (0x083F54, 0x083F58), (0x083F64, 0x083F68),
    (0x083FC0, 0x083FC4), (0x083FD8, 0x083FDC),
)
HOLES = ((0x083F52, 0x083F54), (0x083FBE, 0x083FC0))
CODE_SHA256 = "6bf6a49a0d362d5bae7a5c836a776015c24f79a61913d1f6345771b7a3b31950"
LITERAL_SHA256 = "aed4c39effd0707dc652c1e000599d4bdd2e2da298e8aebe1b2f14339ea1a8de"
HOLE_SHA256 = "df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119"
LITERAL_BINDING_SHA256 = "df9fe28184662f990b33e9102b404bca4d74f5f0840105cea4b21bbf757f3b1b"
BLOCK_SHA256 = "2fe3ca43fd1b0959c6adf9f9100c78cd48c4ccc0435f3cafabfc470535641f8a"
EXIT_SOURCE_SHA256 = "16da3a30ac9904e75314f54c9e4fc0d90a41ad0dc389aff03c123131288b60e9"
EXIT_VECTOR_SHA256 = "1f1d3e5527e0c4ae263b1f4d0b29e656cb090060991e396b5bda96eb59fe38b9"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _packed(rom: bytes, ranges: tuple[tuple[int, int], ...] | list[list[int]]) -> bytes:
    return b"".join(rom[start:end] for start, end in ranges)


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
    """Atomically publish one directory without replacing any destination."""
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


def _upstream_contract(root: Path) -> dict[str, Any]:
    for path, digest in UPSTREAM_FILES:
        if _sha(_safe_file(root, path).read_bytes()) != digest:
            raise ValueError("upstream dispatcher owner identity changed")
    payload = json.loads(_safe_file(root, UPSTREAM_FILES[1][0]).read_bytes())
    blocks = payload["extension"]["blocks"]
    owners = [row for row in blocks if row["id"] in {
        "block-thumb-083b2a", "block-thumb-083b42", "block-thumb-083b44"}]
    if [row["range"] for row in owners] != [
            [0x083B2A, 0x083B42], [0x083B42, 0x083B44], [0x083B44, 0x083B4E]]:
        raise ValueError("upstream dispatcher code ownership changed")
    opaque_owners = [row for row in blocks if row["id"] in {
        "block-thumb-083fea", "block-thumb-083ffa"}]
    if [row["range"] for row in opaque_owners] != [
            [0x083FEA, 0x083FF8], [0x083FFA, 0x08400C]]:
        raise ValueError("upstream opaque exit ownership changed")
    literal_payload = json.loads(_safe_file(root, UPSTREAM_FILES[4][0]).read_bytes())
    words = [row for row in literal_payload["target_words"]
             if row["target_file_offset"] in (0x083B50, 0x083B54, 0x083B58)]
    if [(row["target_file_offset"], row["target_raw_hex"]) for row in words] != [
            (0x083B50, "04680202"), (0x083B54, "88f85308"),
            (0x083B58, "5c3b0808")]:
        raise ValueError("upstream dispatcher literal ownership changed")
    return {"artifact_schema": payload["schema"],
            "literal_artifact_schema": literal_payload["schema"],
            "status": "identity_bound_verified_upstream",
            "files": {path.as_posix(): digest for path, digest in UPSTREAM_FILES},
            "code_owner_block_ids": [row["id"] for row in owners],
            "opaque_exit_owner_block_ids": [row["id"] for row in opaque_owners],
            "literal_owner_word_offsets": [row["target_file_offset"] for row in words]}


def _dispatcher_contract(rom: bytes) -> dict[str, Any]:
    if _sha(rom[slice(*DISPATCHER_CODE)]) != DISPATCHER_CODE_SHA256:
        raise ValueError("dispatcher instruction identity changed")
    if _sha(rom[slice(*DISPATCHER_LITERAL)]) != DISPATCHER_LITERAL_SHA256:
        raise ValueError("dispatcher literal identity changed")
    expected = "0878062800d952e280000449401800688746"
    if rom[slice(*DISPATCHER_CODE)].hex() != expected:
        raise ValueError("dispatcher index semantics changed")
    if struct.unpack_from("<I", rom, 0x083B58)[0] != 0x08083B5C:
        raise ValueError("dispatcher table base changed")
    raw = rom[slice(*TABLE_RANGE)]
    if _sha(raw) != TABLE_SHA256:
        raise ValueError("table identity changed")
    pointers = tuple(struct.unpack_from("<7I", raw))
    if pointers != tuple(0x08000000 + root for root in ROOTS):
        raise ValueError("table root denominator changed")
    return {"instruction_range": list(DISPATCHER_CODE),
            "instruction_sha256": DISPATCHER_CODE_SHA256,
            "literal_range": list(DISPATCHER_LITERAL),
            "literal_sha256": DISPATCHER_LITERAL_SHA256,
            "index_load_site": 0x083B3C, "unsigned_max_index": 6,
            "out_of_range_target": 0x083FEA,
            "table_base_load_site": 0x083B46,
            "table_range": list(TABLE_RANGE), "table_sha256": TABLE_SHA256,
            "slot_count": 7, "root_pointers": list(pointers), "roots": list(ROOTS)}


def _walk(rom: bytes) -> tuple[dict[tuple[str, int], dict[str, Any]],
                                list[dict[str, Any]], list[list[Any]]]:
    pending: list[tuple[int, int, str]] = []
    scheduled: set[tuple[str, int]] = set()
    for root in ROOTS:
        heapq.heappush(pending, _key("thumb", root))
        scheduled.add(("thumb", root))
    nodes: dict[tuple[str, int], dict[str, Any]] = {}
    exits: list[list[Any]] = []
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in nodes:
            continue
        if mode != "thumb" or not BOUND[0] <= offset < BOUND[1]:
            raise ValueError("closure worklist escaped frozen bound")
        decoded = _decode_one(rom, offset, mode)
        if not decoded["accepted"]:
            raise ValueError("closure decoder frontier changed")
        if offset + decoded["size"] > BOUND[1]:
            raise ValueError("closure instruction straddles frozen bound")
        nodes[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            if target[0] == "thumb" and target[1] in OPAQUE_BASELINE_TARGETS:
                exits.append([offset, edge["kind"], target[1]])
                continue
            if target[0] != "thumb" or not BOUND[0] <= target[1] < BOUND[1]:
                raise ValueError("closure non-baseline edge escaped frozen bound")
            if target not in scheduled:
                heapq.heappush(pending, _key(*target))
                scheduled.add(target)
    blocks, _ = _build_blocks(rom, nodes, {("thumb", root) for root in ROOTS})
    return nodes, blocks, sorted(exits)


def _closure(rom: bytes) -> dict[str, Any]:
    nodes, blocks, exits = _walk(rom)
    code = _merged_ranges(nodes)
    bindings: list[list[int]] = []
    for (_, offset), node in sorted(nodes.items()):
        halfword = struct.unpack_from("<H", rom, offset)[0]
        if halfword & 0xF800 == 0x4800:
            literal = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
            bindings.append([offset, literal, struct.unpack_from("<I", rom, literal)[0]])
    literals = [[literal, literal + 4] for literal in sorted({row[1] for row in bindings})]
    if literals != [list(row) for row in LITERAL_RANGES]:
        raise ValueError("literal denominator changed")
    if _sha(_packed(rom, LITERAL_RANGES)) != LITERAL_SHA256:
        raise ValueError("literal identity changed")
    if code != [list(row) for row in CODE_RANGES]:
        raise ValueError("closure range denominator changed")
    if len(nodes) != 555 or len(blocks) != 126:
        raise ValueError("closure instruction/block denominator changed")
    if _sha(b"".join(rom[source:source + 2] for source, _, _ in exits)) != EXIT_SOURCE_SHA256:
        raise ValueError("exit source identity changed")
    if _sha(json.dumps(exits, separators=(",", ":")).encode()) != EXIT_VECTOR_SHA256:
        raise ValueError("exit denominator changed")
    if _sha(_packed(rom, CODE_RANGES)) != CODE_SHA256:
        raise ValueError("closure byte identity changed")
    if _sha(json.dumps(bindings, separators=(",", ":")).encode()) != LITERAL_BINDING_SHA256:
        raise ValueError("literal binding denominator changed")
    if _sha(_canonical(blocks)) != BLOCK_SHA256:
        # The frozen digest above uses compact JSON, so keep that encoding explicit.
        if _sha(json.dumps(blocks, separators=(",", ":"),
                           sort_keys=True).encode()) != BLOCK_SHA256:
            raise ValueError("closure block denominator changed")
    if _sha(_packed(rom, HOLES)) != HOLE_SHA256:
        raise ValueError("hole identity changed")
    frontier_count = sum(len(node["frontiers"]) for node in nodes.values())
    if frontier_count:
        raise ValueError("closure frontier denominator changed")
    return {"roots": list(ROOTS), "root_count": len(ROOTS),
            "bound": list(BOUND), "instruction_count": len(nodes),
            "basic_block_count": len(blocks), "code_bytes": 1110,
            "code_ranges": code, "code_sha256": CODE_SHA256,
            "literal_reference_count": len(bindings),
            "unique_literal_word_count": len(literals), "literal_bytes": 24,
            "literal_ranges": literals, "literal_sha256": LITERAL_SHA256,
            "opaque_baseline_targets": list(OPAQUE_BASELINE_TARGETS),
            "opaque_baseline_exit_count": len(exits),
            "opaque_baseline_exits": exits,
            "opaque_exit_target_counts": {str(key): value for key, value in
                                           sorted(Counter(row[2] for row in exits).items())},
            "frontier_count": frontier_count,
            "preserved_unknown_holes": [list(row) for row in HOLES],
            "preserved_unknown_bytes": 4}


def _build_from_rom(root: Path, rom: bytes, *, verify_identity: bool = True) -> dict[str, Any]:
    if verify_identity and (len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256):
        raise ValueError("ROM identity changed")
    upstream = _upstream_contract(root)
    dispatcher = _dispatcher_contract(rom)
    closure = _closure(rom)
    claims = [{"id": "battle-distance-dispatch-table-083b5c",
               "range": list(TABLE_RANGE),
               "claim_kind": "bounded_thumb_dispatch_table",
               "bytes_sha256": TABLE_SHA256}]
    for kind, ranges in (("reachable_thumb_code", CODE_RANGES),
                         ("consumed_literal_words", LITERAL_RANGES)):
        for index, (start, end) in enumerate(ranges, 1):
            claims.append({"id": f"battle-distance-{kind}-{index:02d}-{start:06x}",
                           "range": [start, end], "claim_kind": kind,
                           "bytes_sha256": _sha(rom[start:end])})
    return {"schema": SCHEMA,
            "rom": {"path": ROM_PATH.as_posix(), "size": len(rom),
                    "sha256": ROM_SHA256},
            "upstream_dispatcher_owner": upstream,
            "dispatcher_contract": dispatcher, "target_closure": closure,
            "promotion": {"promotion_batch": SCHEMA,
                          "promoted_from_primary_class": "unknown",
                          "claims": claims, "claim_count": 14,
                          "dispatcher_table_bytes": 28,
                          "target_code_bytes": 1110,
                          "target_literal_bytes": 24,
                          "promotion_bytes": 1162},
            "scope": {"natural_runtime_reachability": False,
                      "distance_metric_semantics": False,
                      "opaque_baseline_target_semantics": False,
                      "padding_or_free_space": False,
                      "editing_or_relocation_safety": False}}


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
    exporter = Path("tools/export_rom_battle_distance_dispatcher_cfg.py")
    verifier = Path("tools/verify_rom_battle_distance_dispatcher_cfg.py")
    test = Path("tests/test_export_rom_battle_distance_dispatcher_cfg.py")
    manifest = {"schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,
                "artifact_status": "accepted",
                "files": {PAYLOAD_NAME: {"size": len(payload_raw),
                                         "sha256": _sha(payload_raw)}},
                "summary": {"root_count": 7, "promotion_bytes": 1162,
                            "frontier_count": 0},
                "producer": {"command": ["python3", exporter.as_posix(), "--root", ".",
                                         "--output", output.relative_to(root).as_posix()]},
                "verifier": {"command": ["python3", verifier.as_posix(), "--root", ".",
                                         "--artifact", output.relative_to(root).as_posix()]},
                "implementation": {
                    "exporter_sha256": _sha(_safe_file(root, exporter).read_bytes()),
                    "verifier_sha256": _sha(_safe_file(root, verifier).read_bytes()),
                    "test_sha256": _sha(_safe_file(root, test).read_bytes())}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,
                                     prefix=".battle-distance-") as directory:
        stage = Path(directory)
        (stage / PAYLOAD_NAME).write_bytes(payload_raw)
        (stage / MANIFEST_NAME).write_bytes(_canonical(manifest))
        from tools.verify_rom_battle_distance_dispatcher_cfg import verify_artifact
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
