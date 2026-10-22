#!/usr/bin/env python3
"""Independently verify the battle-distance dispatcher bounded CFG packet."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import heapq
import json
from pathlib import Path
import struct
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.thumb_branch import decode_thumb_b, decode_thumb_bl


SCHEMA = "rom-battle-distance-dispatcher-cfg-v1"
VERIFY_SCHEMA = f"{SCHEMA}-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
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
CODE_RANGES = ((0x083B78, 0x083DFC), (0x083E00, 0x083F04),
               (0x083F08, 0x083F52), (0x083F58, 0x083F64),
               (0x083F68, 0x083FBE), (0x083FC4, 0x083FD8),
               (0x083FDC, 0x083FEA))
LITERAL_RANGES = ((0x083DFC, 0x083E00), (0x083F04, 0x083F08),
                  (0x083F54, 0x083F58), (0x083F64, 0x083F68),
                  (0x083FC0, 0x083FC4), (0x083FD8, 0x083FDC))
HOLES = ((0x083F52, 0x083F54), (0x083FBE, 0x083FC0))
CODE_SHA256 = "6bf6a49a0d362d5bae7a5c836a776015c24f79a61913d1f6345771b7a3b31950"
LITERAL_SHA256 = "aed4c39effd0707dc652c1e000599d4bdd2e2da298e8aebe1b2f14339ea1a8de"
HOLE_SHA256 = "df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119"
LITERAL_BINDING_SHA256 = "df9fe28184662f990b33e9102b404bca4d74f5f0840105cea4b21bbf757f3b1b"
EXIT_SOURCE_SHA256 = "16da3a30ac9904e75314f54c9e4fc0d90a41ad0dc389aff03c123131288b60e9"
EXIT_VECTOR_SHA256 = "1f1d3e5527e0c4ae263b1f4d0b29e656cb090060991e396b5bda96eb59fe38b9"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _packed(rom: bytes, ranges: tuple[tuple[int, int], ...]) -> bytes:
    return b"".join(rom[start:end] for start, end in ranges)


def _safe_file(root: Path, relative: Path) -> Path:
    base = root.resolve(strict=True)
    cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("unsafe input path")
    result = cursor.resolve(strict=True)
    if not result.is_relative_to(base) or not result.is_file():
        raise ValueError("unsafe input path")
    return result


def _safe_artifact(root: Path, artifact: Path) -> Path:
    base = root.resolve(strict=True)
    lexical = artifact if artifact.is_absolute() else base / artifact
    try:
        relative = lexical.relative_to(base)
    except ValueError as error:
        raise ValueError("artifact escapes root") from error
    cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("artifact symlink ancestor")
    resolved = lexical.resolve(strict=True)
    if not resolved.is_relative_to(base) or not resolved.is_dir():
        raise ValueError("artifact escapes root")
    return resolved


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


def _decode(rom: bytes, offset: int) -> dict[str, Any]:
    first = struct.unpack_from("<H", rom, offset)[0]
    if first & 0xF800 == 0xF000:
        if offset + 4 > len(rom):
            raise ValueError("closure truncated BL")
        second = struct.unpack_from("<H", rom, offset + 2)[0]
        target = decode_thumb_bl(offset, first, second)
        if target is None:
            raise ValueError("closure unexpected Thumb-2 prefix")
        return {"size": 4, "flow_kind": "call", "frontiers": [],
                "successors": [(offset + 4, "fallthrough"),
                               (target, "call_target")]}
    condition = (first >> 8) & 0xF
    if first & 0xF000 == 0xD000 and condition < 14:
        delta = (first & 0xFF) << 1
        if delta & 0x100:
            delta -= 0x200
        return {"size": 2, "flow_kind": "conditional_branch", "frontiers": [],
                "successors": [(offset + 2, "fallthrough"),
                               (offset + 4 + delta, "branch_target")]}
    if first & 0xF800 == 0xE000:
        target = decode_thumb_b(offset, first)
        if target is None:
            raise ValueError("closure branch decode failed")
        return {"size": 2, "flow_kind": "branch", "frontiers": [],
                "successors": [(target, "branch_target")]}
    if first & 0xFF87 == 0x4700 or first & 0xFF00 == 0xBD00:
        return {"size": 2, "flow_kind": "indirect", "frontiers": [offset],
                "successors": []}
    return {"size": 2, "flow_kind": "linear", "frontiers": [],
            "successors": [(offset + 2, "fallthrough")]}


def _block_count(nodes: dict[int, dict[str, Any]]) -> int:
    resolved = {source: [target for target, _ in node["successors"] if target in nodes]
                for source, node in nodes.items()}
    predecessors: dict[int, list[int]] = defaultdict(list)
    for source, targets in resolved.items():
        for target in targets:
            predecessors[target].append(source)
    starts = set(ROOTS)
    for offset, node in nodes.items():
        incoming = predecessors[offset]
        if len(incoming) != 1:
            starts.add(offset)
            continue
        predecessor = incoming[0]
        prior = nodes[predecessor]
        if (len(resolved[predecessor]) != 1 or predecessor + prior["size"] != offset
                or prior["flow_kind"] != "linear"):
            starts.add(offset)
    assigned: set[int] = set()
    block_count = 0
    pending = list(starts)
    heapq.heapify(pending)
    while len(assigned) < len(nodes):
        if not pending:
            heapq.heappush(pending, min(set(nodes) - assigned))
        current = heapq.heappop(pending)
        if current in assigned:
            continue
        block_count += 1
        while current not in assigned:
            assigned.add(current)
            node = nodes[current]
            targets = resolved[current]
            if (len(targets) != 1 or node["flow_kind"] != "linear"
                    or targets[0] in starts or targets[0] in assigned
                    or targets[0] != current + node["size"]):
                break
            current = targets[0]
    return block_count


def _merge(nodes: dict[int, dict[str, Any]]) -> list[list[int]]:
    result: list[list[int]] = []
    for offset, node in sorted(nodes.items()):
        end = offset + node["size"]
        if result and offset <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([offset, end])
    return result


def _closure(rom: bytes) -> dict[str, Any]:
    pending = list(ROOTS)
    heapq.heapify(pending)
    scheduled = set(ROOTS)
    nodes: dict[int, dict[str, Any]] = {}
    exits: list[list[Any]] = []
    while pending:
        offset = heapq.heappop(pending)
        if offset in nodes:
            continue
        if not BOUND[0] <= offset < BOUND[1]:
            raise ValueError("closure worklist escaped frozen bound")
        node = _decode(rom, offset)
        if offset + node["size"] > BOUND[1]:
            raise ValueError("closure instruction straddles frozen bound")
        nodes[offset] = node
        for target, kind in node["successors"]:
            if target in OPAQUE_BASELINE_TARGETS:
                exits.append([offset, kind, target])
                continue
            if not BOUND[0] <= target < BOUND[1]:
                raise ValueError("closure non-baseline edge escaped frozen bound")
            if target not in scheduled:
                heapq.heappush(pending, target)
                scheduled.add(target)
    bindings = []
    for offset in sorted(nodes):
        halfword = struct.unpack_from("<H", rom, offset)[0]
        if halfword & 0xF800 == 0x4800:
            literal = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
            bindings.append([offset, literal, struct.unpack_from("<I", rom, literal)[0]])
    literals = [[literal, literal + 4] for literal in sorted({row[1] for row in bindings})]
    if literals != [list(row) for row in LITERAL_RANGES]:
        raise ValueError("literal denominator changed")
    if _sha(_packed(rom, LITERAL_RANGES)) != LITERAL_SHA256:
        raise ValueError("literal identity changed")
    code = _merge(nodes)
    if code != [list(row) for row in CODE_RANGES] or len(nodes) != 555:
        raise ValueError("closure denominator changed")
    blocks = _block_count(nodes)
    if blocks != 126:
        raise ValueError("closure block denominator changed")
    exits.sort()
    if _sha(b"".join(rom[source:source + 2] for source, _, _ in exits)) != EXIT_SOURCE_SHA256:
        raise ValueError("exit source identity changed")
    if _sha(json.dumps(exits, separators=(",", ":")).encode()) != EXIT_VECTOR_SHA256:
        raise ValueError("exit denominator changed")
    if _sha(_packed(rom, CODE_RANGES)) != CODE_SHA256:
        raise ValueError("closure byte identity changed")
    if _sha(json.dumps(bindings, separators=(",", ":")).encode()) != LITERAL_BINDING_SHA256:
        raise ValueError("literal binding denominator changed")
    if _sha(_packed(rom, HOLES)) != HOLE_SHA256:
        raise ValueError("hole identity changed")
    frontiers = sum(len(node["frontiers"]) for node in nodes.values())
    if frontiers:
        raise ValueError("closure frontier denominator changed")
    return {"roots": list(ROOTS), "root_count": 7, "bound": list(BOUND),
            "instruction_count": 555, "basic_block_count": blocks,
            "code_bytes": 1110, "code_ranges": code, "code_sha256": CODE_SHA256,
            "literal_reference_count": len(bindings),
            "unique_literal_word_count": len(literals), "literal_bytes": 24,
            "literal_ranges": literals, "literal_sha256": LITERAL_SHA256,
            "opaque_baseline_targets": list(OPAQUE_BASELINE_TARGETS),
            "opaque_baseline_exit_count": len(exits),
            "opaque_baseline_exits": exits,
            "opaque_exit_target_counts": {str(key): value for key, value in
                                           sorted(Counter(row[2] for row in exits).items())},
            "frontier_count": frontiers,
            "preserved_unknown_holes": [list(row) for row in HOLES],
            "preserved_unknown_bytes": 4}


def _rebuild(rom: bytes, *, verify_identity: bool = True) -> dict[str, Any]:
    if verify_identity and (len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256):
        raise ValueError("ROM identity changed")
    if _sha(rom[slice(*DISPATCHER_CODE)]) != DISPATCHER_CODE_SHA256:
        raise ValueError("dispatcher instruction identity changed")
    if _sha(rom[slice(*DISPATCHER_LITERAL)]) != DISPATCHER_LITERAL_SHA256:
        raise ValueError("dispatcher literal identity changed")
    if rom[slice(*DISPATCHER_CODE)].hex() != "0878062800d952e280000449401800688746":
        raise ValueError("dispatcher index semantics changed")
    if struct.unpack_from("<I", rom, 0x083B58)[0] != 0x08083B5C:
        raise ValueError("dispatcher table base changed")
    raw = rom[slice(*TABLE_RANGE)]
    if _sha(raw) != TABLE_SHA256:
        raise ValueError("table identity changed")
    pointers = tuple(struct.unpack_from("<7I", raw))
    if pointers != tuple(0x08000000 + root for root in ROOTS):
        raise ValueError("table root denominator changed")
    dispatcher = {"instruction_range": list(DISPATCHER_CODE),
                  "instruction_sha256": DISPATCHER_CODE_SHA256,
                  "literal_range": list(DISPATCHER_LITERAL),
                  "literal_sha256": DISPATCHER_LITERAL_SHA256,
                  "index_load_site": 0x083B3C, "unsigned_max_index": 6,
                  "out_of_range_target": 0x083FEA,
                  "table_base_load_site": 0x083B46,
                  "table_range": list(TABLE_RANGE), "table_sha256": TABLE_SHA256,
                  "slot_count": 7, "root_pointers": list(pointers),
                  "roots": list(ROOTS)}
    return {"dispatcher_contract": dispatcher, "target_closure": _closure(rom)}


def _expected(root: Path, rom: bytes) -> dict[str, Any]:
    rebuilt = _rebuild(rom)
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
            "upstream_dispatcher_owner": _upstream_contract(root), **rebuilt,
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


def verify_artifact(root: Path, artifact: Path,
                    *, expected_artifact: Path | None = None) -> dict[str, Any]:
    try:
        root = root.resolve(strict=True)
        directory = _safe_artifact(root, artifact)
        members = list(directory.iterdir())
        if {path.name for path in members} != {PAYLOAD_NAME, MANIFEST_NAME}:
            raise ValueError("artifact file denominator changed")
        if any(path.is_symlink() or not path.is_file() for path in members):
            raise ValueError("artifact member type changed")
        payload_raw = (directory / PAYLOAD_NAME).read_bytes()
        manifest_raw = (directory / MANIFEST_NAME).read_bytes()
        payload = json.loads(payload_raw)
        manifest = json.loads(manifest_raw)
        if payload_raw != _canonical(payload) or manifest_raw != _canonical(manifest):
            raise ValueError("artifact JSON not canonical")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("ROM identity changed")
        if payload != _expected(root, rom):
            raise ValueError("payload contract changed")
        receipt = expected_artifact if expected_artifact is not None else directory
        receipt = receipt if receipt.is_absolute() else root / receipt
        relative = receipt.resolve(strict=False).relative_to(root).as_posix()
        exporter = Path("tools/export_rom_battle_distance_dispatcher_cfg.py")
        verifier = Path("tools/verify_rom_battle_distance_dispatcher_cfg.py")
        test = Path("tests/test_export_rom_battle_distance_dispatcher_cfg.py")
        expected_manifest = {
            "schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,
            "artifact_status": "accepted",
            "files": {PAYLOAD_NAME: {"size": len(payload_raw),
                                     "sha256": _sha(payload_raw)}},
            "summary": {"root_count": 7, "promotion_bytes": 1162,
                        "frontier_count": 0},
            "producer": {"command": ["python3", exporter.as_posix(), "--root", ".",
                                     "--output", relative]},
            "verifier": {"command": ["python3", verifier.as_posix(), "--root", ".",
                                     "--artifact", relative]},
            "implementation": {
                "exporter_sha256": _sha(_safe_file(root, exporter).read_bytes()),
                "verifier_sha256": _sha(_safe_file(root, verifier).read_bytes()),
                "test_sha256": _sha(_safe_file(root, test).read_bytes())}}
        if manifest != expected_manifest:
            raise ValueError("manifest contract changed")
        return {"schema": VERIFY_SCHEMA, "verified": True, "contract_ok": True,
                "errors": [], "promotion_bytes": 1162, "frontier_count": 0,
                "root_count": 7}
    except Exception as error:
        return {"schema": VERIFY_SCHEMA, "verified": False, "contract_ok": False,
                "errors": [str(error)], "promotion_bytes": 0,
                "frontier_count": None, "root_count": None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
