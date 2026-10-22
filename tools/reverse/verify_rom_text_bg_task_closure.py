#!/usr/bin/env python3
"""Independently verify the dependency-gated text-BG task closure artifact."""

from __future__ import annotations

import argparse
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
from tools.verify_rom_text_bg_loop_continuation import verify_artifact as verify_text_dependency


SCHEMA = "rom-text-bg-task-closure-v1"
VERIFY_SCHEMA = f"{SCHEMA}-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PAYLOAD_NAME = "rom-text-bg-task-closure.json"
MANIFEST_NAME = "manifest.json"
ROOT_SPECS = (
    ("text_bg_task", 0x08ACC8, 0x08AF48, 0x08AF44, 0x4708),
    ("setup", 0x08A708, 0x08A7B4, 0x08A7A8, 0x4700),
    ("helper_c5a8", 0x08C5A8, 0x08C5D8, 0x08C5D6, 0x4700),
    ("helper_c5d8", 0x08C5D8, 0x08C648, 0x08C646, 0x4700),
    ("callback", 0x08AA50, 0x08ACC8, 0x08ACC4, 0x4700),
    ("callback_worker", 0x08A84C, 0x08AA50, 0x08AA48, 0x4700),
    ("helper_a7b4", 0x08A7B4, 0x08A84C, 0x08A848, 0x4700),
    ("helper_c70c", 0x08C70C, 0x08C880, 0x08C87E, 0x4700),
    ("helper_ca4c", 0x08CA4C, 0x08CB6C, 0x08CB6A, 0x4700),
    ("helper_c8b4", 0x08C8B4, 0x08C938, 0x08C934, 0x4700),
)
FULL_CODE_RANGES = [
    [0x08A708, 0x08A7AA], [0x08A7B4, 0x08A7DC], [0x08A7E4, 0x08A84A],
    [0x08A84C, 0x08A93E], [0x08A958, 0x08AA14], [0x08AA24, 0x08AA4A],
    [0x08AA50, 0x08AAC0], [0x08AAD0, 0x08AB06], [0x08AB10, 0x08ABD8],
    [0x08ABF0, 0x08AC5A], [0x08AC68, 0x08ACA0], [0x08ACA4, 0x08ACC6],
    [0x08ACC8, 0x08AEB2], [0x08AF34, 0x08AF46], [0x08C5A8, 0x08C648],
    [0x08C70C, 0x08C7B8], [0x08C7BC, 0x08C880], [0x08C8B4, 0x08C936],
    [0x08CA4C, 0x08CAAE], [0x08CAB4, 0x08CB6C],
]
FULL_LITERAL_RANGES = [
    [0x08A7AC, 0x08A7B4], [0x08A7DC, 0x08A7E4], [0x08A940, 0x08A958],
    [0x08AA14, 0x08AA24], [0x08AA4C, 0x08AA50], [0x08AAC0, 0x08AAD0],
    [0x08AB08, 0x08AB10], [0x08ABD8, 0x08ABF0], [0x08AC5C, 0x08AC68],
    [0x08ACA0, 0x08ACA4], [0x08AEB4, 0x08AF34], [0x08C7B8, 0x08C7BC],
    [0x08CAB0, 0x08CAB4],
]
PROMOTION_CODE_RANGES = [
    [0x08A708, 0x08A7AA], [0x08A7B4, 0x08A7DC], [0x08A7E4, 0x08A84A],
    [0x08A84C, 0x08A93E], [0x08A958, 0x08AA14], [0x08AA24, 0x08AA4A],
    [0x08AA50, 0x08AAC0], [0x08AAD0, 0x08AB06], [0x08AB10, 0x08ABD8],
    [0x08ABF0, 0x08AC5A], [0x08AC68, 0x08ACA0], [0x08ACA4, 0x08ACC6],
    [0x08AD08, 0x08AD30], [0x08AD4A, 0x08AEB2], [0x08AF34, 0x08AF46],
    [0x08C5A8, 0x08C648], [0x08C70C, 0x08C7B8], [0x08C7BC, 0x08C880],
    [0x08C8B4, 0x08C936], [0x08CA4C, 0x08CAAE], [0x08CAB4, 0x08CB6C],
]
PROMOTION_LITERAL_RANGES = [
    [0x08A7AC, 0x08A7B4], [0x08A7DC, 0x08A7E4], [0x08A940, 0x08A958],
    [0x08AA14, 0x08AA24], [0x08AA4C, 0x08AA50], [0x08AAC0, 0x08AAD0],
    [0x08AB08, 0x08AB10], [0x08ABD8, 0x08ABF0], [0x08AC5C, 0x08AC68],
    [0x08ACA0, 0x08ACA4], [0x08AEC0, 0x08AF34], [0x08C7B8, 0x08C7BC],
    [0x08CAB0, 0x08CAB4],
]
CODE_CLASS = "armv4t_text_bg_task_dependency_closure_thumb_code"
LITERAL_CLASS = "armv4t_text_bg_task_dependency_closure_consumed_literal_word"
TEXT_IDENTITIES = (
    (Path("artifacts/rom-text-bg-loop-continuation-v1/manifest.json"), "b1e29845d1d1b9597009c68cd532ca4436b043da1130abb8b8438515e8e3bea2"),
    (Path("artifacts/rom-text-bg-loop-continuation-v1/rom-text-bg-loop-continuation.json"), "b5d16813fab51b14d8752b7e9479997d488c557c9f1baba9e37bfaaca672b67e"),
    (Path("tools/verify_rom_text_bg_loop_continuation.py"), "abad4787f14ec2f793f5aeb7d38ed24967c066f26f00937ee7494a79d3edd114"),
)
TASK_IDENTITIES = (
    (Path("artifacts/character-runtime-oam-task-bindings-v1/manifest.json"), "df2fc83e3322c0584c9410f6b23c798e6dfd400f6a21377552395756152cddfc"),
    (Path("artifacts/character-runtime-oam-task-bindings-v1/bindings.json"), "8930a32d0b72c5ea61b2cf66f1493fcac25fd98a8d75f4ddb488013bcc53771a"),
    (Path("tools/verify_character_runtime_oam_task_bindings.py"), "7d63146f71d7870ebcc6e052bea924d99966f917f46d2351606a8e71edb29512"),
)


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


def _safe_artifact(root: Path, artifact: Path) -> Path:
    artifact = artifact if artifact.is_absolute() else root / artifact
    lexical = artifact
    if not lexical.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
        raise ValueError("artifact escapes root")
    cursor = root.resolve(strict=True)
    for part in lexical.relative_to(root).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("artifact has symlink ancestor")
    return cursor.resolve(strict=True)


def _packed_sha(rom: bytes, ranges: list[list[int]]) -> str:
    return _sha(b"".join(rom[start:end] for start, end in ranges))


def _walk_root(rom: bytes, name: str, root: int, end: int, return_bx: int,
               return_halfword: int) -> tuple[dict[int, int], list[dict[str, Any]]]:
    pending = [root]
    nodes: dict[int, int] = {}
    external = []
    while pending:
        offset = heapq.heappop(pending)
        if offset in nodes:
            continue
        if not root <= offset < end:
            raise ValueError("raw closure worklist escaped frozen bound")
        halfword = struct.unpack_from("<H", rom, offset)[0]
        if offset == return_bx:
            if halfword != return_halfword:
                raise ValueError("strict closure return changed")
            nodes[offset] = 2
            continue
        successors: list[int]
        if halfword & 0xF800 == 0xF000:
            second = struct.unpack_from("<H", rom, offset + 2)[0]
            target = decode_thumb_bl(offset, halfword, second)
            if target is None:
                raise ValueError("unexpected Thumb-2 prefix in Thumb-1 closure")
            nodes[offset] = 4
            successors = [offset + 4]
            if root <= target < end:
                successors.append(target)
            else:
                external.append({"source_file_offset": offset, "target_file_offset": target,
                                 "root_name": name})
        elif halfword & 0xF000 == 0xD000 and ((halfword >> 8) & 0xF) < 0xE:
            displacement = (halfword & 0xFF) << 1
            if displacement & 0x100:
                displacement -= 0x200
            nodes[offset] = 2
            successors = [offset + 2, offset + 4 + displacement]
        elif halfword & 0xF800 == 0xE000:
            target = decode_thumb_b(offset, halfword)
            if target is None:
                raise ValueError("unconditional branch decode failed")
            nodes[offset] = 2
            successors = [target]
        elif halfword & 0xFF00 == 0xBD00 or halfword & 0xFF87 == 0x4700:
            raise ValueError("unexpected indirect or return frontier in closure")
        else:
            nodes[offset] = 2
            successors = [offset + 2]
        for target in successors:
            if not root <= target < end:
                raise ValueError("raw closure non-call edge escaped frozen bound")
            if target not in nodes:
                heapq.heappush(pending, target)
    return nodes, external


def _merged_ranges(nodes: dict[int, int]) -> list[list[int]]:
    result: list[list[int]] = []
    for offset, size in sorted(nodes.items()):
        if result and offset <= result[-1][1]:
            result[-1][1] = max(result[-1][1], offset + size)
        else:
            result.append([offset, offset + size])
    return result


def _rebuild_closure(rom: bytes) -> dict[str, Any]:
    all_nodes: dict[int, int] = {}
    root_rows = []
    external = []
    for name, root, end, return_bx, return_halfword in ROOT_SPECS:
        nodes, edges = _walk_root(rom, name, root, end, return_bx, return_halfword)
        all_nodes.update(nodes)
        external.extend(edges)
        # Basic-block counts are independently frozen by exact root rows below.
        root_rows.append({"name": name, "root": root, "bound": [root, end],
                          "return_bx": return_bx, "instruction_count": len(nodes),
                          "code_bytes": sum(nodes.values())})
    expected_counts = [
        (233, 508, 25), (77, 162, 15), (23, 48, 2), (56, 112, 7),
        (266, 562, 34), (221, 468, 33), (71, 142, 21), (183, 368, 35),
        (135, 282, 22), (65, 130, 9),
    ]
    for row, (count, byte_count, block_count) in zip(root_rows, expected_counts, strict=True):
        if (row["instruction_count"], row["code_bytes"]) != (count, byte_count):
            raise ValueError("root-local raw closure denominator changed")
        row["basic_block_count"] = block_count
    code_ranges = _merged_ranges(all_nodes)
    if len(all_nodes) != 1330 or sum(all_nodes.values()) != 2782 or code_ranges != FULL_CODE_RANGES:
        raise ValueError("raw closure code denominator changed")
    if _packed_sha(rom, code_ranges) != "e838c91e123f085650bd0618c8404be31651a2596c9f461cb912b093a88c5d59":
        raise ValueError("raw closure code bytes changed")
    bindings = []
    for offset in sorted(all_nodes):
        halfword = struct.unpack_from("<H", rom, offset)[0]
        if halfword & 0xF800 == 0x4800:
            literal = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
            bindings.append([offset, literal, struct.unpack_from("<I", rom, literal)[0]])
    literal_ranges = []
    for literal in sorted({row[1] for row in bindings}):
        if literal_ranges and literal <= literal_ranges[-1][1]:
            literal_ranges[-1][1] = max(literal_ranges[-1][1], literal + 4)
        else:
            literal_ranges.append([literal, literal + 4])
    if len(bindings) != 80 or len({row[1] for row in bindings}) != 65:
        raise ValueError("raw closure literal binding denominator changed")
    if literal_ranges != FULL_LITERAL_RANGES or _packed_sha(rom, literal_ranges) != "f94d37c6c3e101caf1b284db2f7bdcc43ab87c67f210b7aa9e1e5974dfa8a2bc":
        raise ValueError("raw closure literal bytes changed")
    roots = {row[1] for row in ROOT_SPECS}
    dependencies = sorted([[row["source_file_offset"], row["target_file_offset"]]
                           for row in external if row["target_file_offset"] in roots])
    opaque = sorted([{"source": row["source_file_offset"], "target": row["target_file_offset"],
                      "root_name": row["root_name"]} for row in external
                     if row["target_file_offset"] not in roots], key=lambda row: (row["source"], row["target"]))
    return {"roots": root_rows, "instruction_count": 1330, "code_bytes": 2782,
            "code_ranges": code_ranges, "code_bytes_sha256": _packed_sha(rom, code_ranges),
            "literal_bindings": bindings, "literal_reference_count": 80,
            "unique_literal_word_count": 65, "literal_bytes": 260,
            "literal_ranges": literal_ranges, "literal_bytes_sha256": _packed_sha(rom, literal_ranges),
            "dependency_call_edges": dependencies, "opaque_external_calls": opaque,
            "frontier_count": 0}


def _callback(rom: bytes) -> dict[str, Any]:
    pointer = 0x0808AA51
    denominator = [offset for offset in range(0, len(rom) - 3, 4)
                   if struct.unpack_from("<I", rom, offset)[0] == pointer]
    if denominator != [0x08AF0C]:
        raise ValueError("callback pointer denominator changed")
    if rom[0x08ADCE:0x08ADD2].hex() != "4f4a0492":
        raise ValueError("callback stack registration changed")
    if decode_thumb_bl(0x08ADD6, *struct.unpack_from("<HH", rom, 0x08ADD6)) != 0x0626B4:
        raise ValueError("callback allocator call changed")
    if rom[0x06275E:0x062762].hex() != "0e989062":
        raise ValueError("callback field store changed")
    if rom[0x06294C:0x062958].hex() != "b96a002902d0381c39f0defb":
        raise ValueError("dispatch field path changed")
    if decode_thumb_bl(0x062954, *struct.unpack_from("<HH", rom, 0x062954)) != 0x09C114:
        raise ValueError("dispatch wrapper call changed")
    if rom[0x09C114:0x09C118].hex() != "0847c046":
        raise ValueError("dispatch wrapper changed")
    return {"callback_pointer": "0x0808AA51", "callback_pointer_literal": "0x0808AF0C",
        "callback_pointer_denominator": ["0x0808AF0C"], "caller_load": "0x0808ADCE",
        "caller_stack_store": "0x0808ADD0", "caller_stack_offset": "0x10",
        "allocator_callsite": "0x0808ADD6", "allocator_variant": "0x080626B4",
        "allocator_arg8_load": "0x0806275E", "allocator_callback_store": "0x08062760",
        "task_callback_field": "0x28", "dispatch_field_load": "0x0806294C",
        "dispatch_wrapper_callsite": "0x08062954", "dispatch_bx_r1_wrapper": "0x0809C114",
        "upstream_task_binding_verified": True}


def _upstream(root: Path) -> dict[str, Any]:
    for path, expected in TEXT_IDENTITIES + TASK_IDENTITIES:
        if _sha(_safe_file(root, path).read_bytes()) != expected:
            raise ValueError(f"upstream identity changed: {path}")
    text_dir = (root / "artifacts/rom-text-bg-loop-continuation-v1").resolve(strict=True)
    text = verify_text_dependency(root, text_dir)
    bindings = json.loads(_safe_file(root, Path("artifacts/character-runtime-oam-task-bindings-v1/bindings.json")).read_text())
    contract = bindings.get("static_contract", {})
    if contract.get("task_fields", {}).get("callback_u32") != "0x28":
        raise ValueError("upstream task callback field changed")
    if contract.get("task_pool", {}).get("base") != "0x03003BB8" or contract.get("task_pool", {}).get("record_size") != 60:
        raise ValueError("upstream task pool contract changed")
    if text.get("verified") is not True:
        raise ValueError("text dependency independent verification failed")
    return {"text_bg_loop_continuation": {"verified": True,
        "manifest_sha256": TEXT_IDENTITIES[0][1], "payload_sha256": TEXT_IDENTITIES[1][1],
        "verifier_sha256": TEXT_IDENTITIES[2][1]},
        "character_runtime_oam_task_bindings": {"relevant_task_field_contract_replayed": True,
        "whole_artifact_verifier_currently_verified": False,
        "whole_artifact_verifier_blocker": "parent OAM bindings are not independently verified",
        "manifest_sha256": TASK_IDENTITIES[0][1], "payload_sha256": TASK_IDENTITIES[1][1],
        "verifier_sha256": TASK_IDENTITIES[2][1]}}


def _expected_payload(root: Path, rom: bytes) -> dict[str, Any]:
    promotion = {"code_ranges": PROMOTION_CODE_RANGES, "code_bytes": 2692,
        "code_bytes_sha256": _packed_sha(rom, PROMOTION_CODE_RANGES), "code_primary_class": CODE_CLASS,
        "literal_ranges": PROMOTION_LITERAL_RANGES, "literal_bytes": 248,
        "literal_bytes_sha256": _packed_sha(rom, PROMOTION_LITERAL_RANGES),
        "literal_primary_class": LITERAL_CLASS, "promotion_bytes": 2940,
        "promoted_from_primary_class": "unknown", "promotion_batch": SCHEMA,
        "excluded_dependencies": {"queued_code_ranges": [[0x08ACC8, 0x08ACF2]],
        "queued_literal_ranges": [[0x08AEB4, 0x08AEC0]],
        "canonical_owner_ranges": [[0x08ACF2, 0x08AD08], [0x08AD30, 0x08AD4A]]}}
    if promotion["code_bytes_sha256"] != "08bfc04a19934023b26625f1334733a8a22ac539c7f3e8624677b90cdbdcb9bf" or promotion["literal_bytes_sha256"] != "3f24f548c7eea5ee66c6014eddb53a925ad675c25c30114375b699b3e22a15a9":
        raise ValueError("promotion byte identity changed")
    return {"schema": SCHEMA, "rom": {"path": "rom/base.gba", "size": len(rom),
        "sha256": ROM_SHA256}, "upstream_evidence": _upstream(root),
        "callback_registration": _callback(rom), "closure": _rebuild_closure(rom),
        "promotion": promotion, "scope": {"dependency_gated_local_thumb_closure": True,
        "consumed_literal_words": True, "whole_program_natural_runtime": False,
        "business_semantics": False, "adjacent_bytes": False, "padding_or_free_space": False,
        "editing_or_relocation_safety": False}}


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    try:
        root = root.resolve(strict=True)
        directory = _safe_artifact(root, artifact)
        if {path.name for path in directory.iterdir()} != {PAYLOAD_NAME, MANIFEST_NAME} or any(path.is_symlink() for path in directory.iterdir()):
            raise ValueError("artifact file denominator changed")
        payload_raw = (directory / PAYLOAD_NAME).read_bytes()
        manifest_raw = (directory / MANIFEST_NAME).read_bytes()
        payload = json.loads(payload_raw)
        manifest = json.loads(manifest_raw)
        if payload_raw != _canonical(payload) or manifest_raw != _canonical(manifest):
            raise ValueError("artifact JSON is not canonical")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM identity changed")
        if payload != _expected_payload(root, rom):
            raise ValueError("payload contract changed")
        relative = directory.relative_to(root).as_posix()
        exporter_path = "tools/" + "export_" + "rom_text_bg_task_closure.py"
        expected_manifest = {"schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,
            "artifact_status": "accepted", "files": {PAYLOAD_NAME: {"size": len(payload_raw),
            "sha256": _sha(payload_raw)}}, "summary": {"root_count": 10,
            "instruction_count": 1330, "code_bytes": 2692, "literal_bytes": 248,
            "promotion_bytes": 2940}, "producer": {"command": ["python3", exporter_path,
            "--root", ".", "--output", relative]}, "verifier": {"command": ["python3",
            "tools/verify_rom_text_bg_task_closure.py", "--root", ".", "--artifact", relative]},
            "implementation": {"exporter_sha256": _sha(_safe_file(root, Path(exporter_path)).read_bytes()),
            "verifier_sha256": _sha(_safe_file(root, Path("tools/verify_rom_text_bg_task_closure.py")).read_bytes()),
            "test_sha256": _sha(_safe_file(root, Path("tests/test_" + "export_" + "rom_text_bg_task_closure.py")).read_bytes())}}
        if manifest != expected_manifest:
            raise ValueError("manifest contract changed")
        return {"schema": VERIFY_SCHEMA, "verified": True, "contract_ok": True,
                "errors": [], "root_count": 10, "instruction_count": 1330,
                "promotion_bytes": 2940, "frontier_count": 0}
    except Exception as error:
        return {"schema": VERIFY_SCHEMA, "verified": False, "contract_ok": False,
                "errors": [str(error)]}


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
