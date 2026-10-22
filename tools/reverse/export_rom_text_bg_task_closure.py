#!/usr/bin/env python3
"""Export the dependency-gated text-BG task and callback closure packet."""

from __future__ import annotations

import argparse
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
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.export_rom_cfg_proven_roots_v11 import _bounded_worklist, _merged_ranges
from tools.thumb_branch import decode_thumb_bl
from tools.verify_rom_text_bg_loop_continuation import verify_artifact as verify_text_dependency


SCHEMA = "rom-text-bg-task-closure-v1"
VERIFY_SCHEMA = f"{SCHEMA}-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
OFFICIAL = Path("artifacts/rom-text-bg-task-closure-v1")
PAYLOAD_NAME = "rom-text-bg-task-closure.json"
MANIFEST_NAME = "manifest.json"
TEXT_DIR = Path("artifacts/rom-text-bg-loop-continuation-v1")
TEXT_MANIFEST_SHA256 = "b1e29845d1d1b9597009c68cd532ca4436b043da1130abb8b8438515e8e3bea2"
TEXT_PAYLOAD_SHA256 = "b5d16813fab51b14d8752b7e9479997d488c557c9f1baba9e37bfaaca672b67e"
TEXT_VERIFIER_SHA256 = "abad4787f14ec2f793f5aeb7d38ed24967c066f26f00937ee7494a79d3edd114"
TASK_DIR = Path("artifacts/character-runtime-oam-task-bindings-v1")
TASK_MANIFEST_SHA256 = "df2fc83e3322c0584c9410f6b23c798e6dfd400f6a21377552395756152cddfc"
TASK_PAYLOAD_SHA256 = "8930a32d0b72c5ea61b2cf66f1493fcac25fd98a8d75f4ddb488013bcc53771a"
TASK_VERIFIER_SHA256 = "7d63146f71d7870ebcc6e052bea924d99966f917f46d2351606a8e71edb29512"

# name, root, end-exclusive bound, strict BX return
ROOT_SPECS = (
    ("text_bg_task", 0x08ACC8, 0x08AF48, 0x08AF44),
    ("setup", 0x08A708, 0x08A7B4, 0x08A7A8),
    ("helper_c5a8", 0x08C5A8, 0x08C5D8, 0x08C5D6),
    ("helper_c5d8", 0x08C5D8, 0x08C648, 0x08C646),
    ("callback", 0x08AA50, 0x08ACC8, 0x08ACC4),
    ("callback_worker", 0x08A84C, 0x08AA50, 0x08AA48),
    ("helper_a7b4", 0x08A7B4, 0x08A84C, 0x08A848),
    ("helper_c70c", 0x08C70C, 0x08C880, 0x08C87E),
    ("helper_ca4c", 0x08CA4C, 0x08CB6C, 0x08CB6A),
    ("helper_c8b4", 0x08C8B4, 0x08C938, 0x08C934),
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


def _safe_directory(root: Path, relative: Path) -> Path:
    base = root.resolve(strict=True)
    cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"unsafe input path: {relative}")
    result = cursor.resolve(strict=True)
    if not result.is_relative_to(base) or not result.is_dir():
        raise ValueError(f"unsafe input path: {relative}")
    return result


def _packed_sha(rom: bytes, ranges: list[list[int]]) -> str:
    return _sha(b"".join(rom[start:end] for start, end in ranges))


def _literal_bindings(rom: bytes, nodes: dict[tuple[str, int], dict[str, Any]]) -> list[list[int]]:
    result = []
    for (_, offset), node in sorted(nodes.items(), key=lambda item: item[0][1]):
        halfword = struct.unpack_from("<H", rom, offset)[0]
        if halfword & 0xF800 == 0x4800:
            literal = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
            result.append([offset, literal, struct.unpack_from("<I", rom, literal)[0]])
    return result


def _callback_registration(rom: bytes) -> dict[str, Any]:
    callback_pointer = 0x0808AA51
    denominator = [offset for offset in range(0, len(rom) - 3, 4)
                   if struct.unpack_from("<I", rom, offset)[0] == callback_pointer]
    if denominator != [0x08AF0C] or rom[0x08AF0C:0x08AF10] != struct.pack("<I", callback_pointer):
        raise ValueError("callback pointer denominator changed")
    if rom[0x08ADCE:0x08ADD2].hex() != "4f4a0492":
        raise ValueError("callback stack registration changed")
    first, second = struct.unpack_from("<HH", rom, 0x08ADD6)
    if decode_thumb_bl(0x08ADD6, first, second) != 0x0626B4:
        raise ValueError("callback allocator call changed")
    if rom[0x06275E:0x062762].hex() != "0e989062":
        raise ValueError("callback field store changed")
    if rom[0x06294C:0x062958].hex() != "b96a002902d0381c39f0defb":
        raise ValueError("dispatch field path changed")
    if decode_thumb_bl(0x062954, *struct.unpack_from("<HH", rom, 0x062954)) != 0x09C114:
        raise ValueError("dispatch wrapper call changed")
    if rom[0x09C114:0x09C118].hex() != "0847c046":
        raise ValueError("dispatch wrapper changed")
    return {
        "callback_pointer": "0x0808AA51", "callback_pointer_literal": "0x0808AF0C",
        "callback_pointer_denominator": ["0x0808AF0C"], "caller_load": "0x0808ADCE",
        "caller_stack_store": "0x0808ADD0", "caller_stack_offset": "0x10",
        "allocator_callsite": "0x0808ADD6", "allocator_variant": "0x080626B4",
        "allocator_arg8_load": "0x0806275E", "allocator_callback_store": "0x08062760",
        "task_callback_field": "0x28", "dispatch_field_load": "0x0806294C",
        "dispatch_wrapper_callsite": "0x08062954", "dispatch_bx_r1_wrapper": "0x0809C114",
        "upstream_task_binding_verified": True,
    }


def _upstream(root: Path) -> dict[str, Any]:
    identities = (
        (TEXT_DIR / MANIFEST_NAME, TEXT_MANIFEST_SHA256, "text dependency manifest"),
        (TEXT_DIR / "rom-text-bg-loop-continuation.json", TEXT_PAYLOAD_SHA256, "text dependency payload"),
        (Path("tools/verify_rom_text_bg_loop_continuation.py"), TEXT_VERIFIER_SHA256, "text dependency verifier"),
        (TASK_DIR / MANIFEST_NAME, TASK_MANIFEST_SHA256, "task binding manifest"),
        (TASK_DIR / "bindings.json", TASK_PAYLOAD_SHA256, "task binding payload"),
        (Path("tools/verify_character_runtime_oam_task_bindings.py"), TASK_VERIFIER_SHA256, "task binding verifier"),
    )
    for path, expected, label in identities:
        if _sha(_safe_file(root, path).read_bytes()) != expected:
            raise ValueError(f"{label} identity changed")
    text = verify_text_dependency(root, _safe_directory(root, TEXT_DIR))
    bindings = json.loads(_safe_file(root, TASK_DIR / "bindings.json").read_text())
    contract = bindings.get("static_contract", {})
    if contract.get("task_fields", {}).get("callback_u32") != "0x28":
        raise ValueError("upstream task callback field changed")
    if contract.get("task_pool", {}).get("base") != "0x03003BB8" or contract.get("task_pool", {}).get("record_size") != 60:
        raise ValueError("upstream task pool contract changed")
    if text.get("verified") is not True:
        raise ValueError("text dependency independent verification failed")
    return {
        "text_bg_loop_continuation": {"verified": True, "manifest_sha256": TEXT_MANIFEST_SHA256,
            "payload_sha256": TEXT_PAYLOAD_SHA256, "verifier_sha256": TEXT_VERIFIER_SHA256},
        "character_runtime_oam_task_bindings": {"relevant_task_field_contract_replayed": True,
            "whole_artifact_verifier_currently_verified": False,
            "whole_artifact_verifier_blocker": "parent OAM bindings are not independently verified",
            "manifest_sha256": TASK_MANIFEST_SHA256, "payload_sha256": TASK_PAYLOAD_SHA256,
            "verifier_sha256": TASK_VERIFIER_SHA256},
    }


def _closure(rom: bytes) -> dict[str, Any]:
    all_nodes: dict[tuple[str, int], dict[str, Any]] = {}
    root_rows = []
    external = []
    for name, root, end, return_bx in ROOT_SPECS:
        nodes, blocks, edges = _bounded_worklist(
            rom, root, (root, end), return_bx, target_is_producer=False
        )
        all_nodes.update(nodes)
        root_rows.append({"name": name, "root": root, "bound": [root, end],
                          "return_bx": return_bx, "instruction_count": len(nodes),
                          "code_bytes": sum(node["size"] for node in nodes.values()),
                          "basic_block_count": len(blocks)})
        external.extend({**edge, "root_name": name} for edge in edges)
    code_ranges = _merged_ranges(all_nodes)
    bindings = _literal_bindings(rom, all_nodes)
    literal_ranges = []
    for literal in sorted({row[1] for row in bindings}):
        if literal_ranges and literal <= literal_ranges[-1][1]:
            literal_ranges[-1][1] = max(literal_ranges[-1][1], literal + 4)
        else:
            literal_ranges.append([literal, literal + 4])
    if len(all_nodes) != 1330 or sum(node["size"] for node in all_nodes.values()) != 2782:
        raise ValueError("closure instruction denominator changed")
    if code_ranges != FULL_CODE_RANGES or _packed_sha(rom, code_ranges) != "e838c91e123f085650bd0618c8404be31651a2596c9f461cb912b093a88c5d59":
        raise ValueError("closure code bytes changed")
    if len(bindings) != 80 or len({row[1] for row in bindings}) != 65:
        raise ValueError("closure literal binding denominator changed")
    if literal_ranges != FULL_LITERAL_RANGES or _packed_sha(rom, literal_ranges) != "f94d37c6c3e101caf1b284db2f7bdcc43ab87c67f210b7aa9e1e5974dfa8a2bc":
        raise ValueError("closure literal bytes changed")
    roots = {root for _, root, _, _ in ROOT_SPECS}
    dependency_edges = sorted(
        [[edge["source_file_offset"], edge["target_file_offset"]] for edge in external
         if edge["target_file_offset"] in roots]
    )
    opaque = sorted(
        [{"source": edge["source_file_offset"], "target": edge["target_file_offset"],
          "root_name": edge["root_name"]} for edge in external
         if edge["target_file_offset"] not in roots], key=lambda row: (row["source"], row["target"])
    )
    return {"roots": root_rows, "instruction_count": 1330, "code_bytes": 2782,
            "code_ranges": code_ranges, "code_bytes_sha256": _packed_sha(rom, code_ranges),
            "literal_bindings": bindings, "literal_reference_count": 80,
            "unique_literal_word_count": 65, "literal_bytes": 260,
            "literal_ranges": literal_ranges, "literal_bytes_sha256": _packed_sha(rom, literal_ranges),
            "dependency_call_edges": dependency_edges, "opaque_external_calls": opaque,
            "frontier_count": 0}


def _build_from_rom(root: Path, rom: bytes, *, verify_rom_identity: bool = True) -> dict[str, Any]:
    if len(rom) != ROM_SIZE:
        raise ValueError("ROM size changed")
    callback = _callback_registration(rom)
    closure = _closure(rom)
    if verify_rom_identity and _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    promotion = {
        "code_ranges": PROMOTION_CODE_RANGES, "code_bytes": 2692,
        "code_bytes_sha256": _packed_sha(rom, PROMOTION_CODE_RANGES), "code_primary_class": CODE_CLASS,
        "literal_ranges": PROMOTION_LITERAL_RANGES, "literal_bytes": 248,
        "literal_bytes_sha256": _packed_sha(rom, PROMOTION_LITERAL_RANGES),
        "literal_primary_class": LITERAL_CLASS, "promotion_bytes": 2940,
        "promoted_from_primary_class": "unknown", "promotion_batch": SCHEMA,
        "excluded_dependencies": {
            "queued_code_ranges": [[0x08ACC8, 0x08ACF2]],
            "queued_literal_ranges": [[0x08AEB4, 0x08AEC0]],
            "canonical_owner_ranges": [[0x08ACF2, 0x08AD08], [0x08AD30, 0x08AD4A]],
        },
    }
    if promotion["code_bytes_sha256"] != "08bfc04a19934023b26625f1334733a8a22ac539c7f3e8624677b90cdbdcb9bf":
        raise ValueError("promotion code bytes changed")
    if promotion["literal_bytes_sha256"] != "3f24f548c7eea5ee66c6014eddb53a925ad675c25c30114375b699b3e22a15a9":
        raise ValueError("promotion literal bytes changed")
    return {"schema": SCHEMA, "rom": {"path": ROM_PATH.as_posix(), "size": len(rom),
            "sha256": ROM_SHA256}, "upstream_evidence": _upstream(root),
            "callback_registration": callback, "closure": closure, "promotion": promotion,
            "scope": {"dependency_gated_local_thumb_closure": True, "consumed_literal_words": True,
                "whole_program_natural_runtime": False, "business_semantics": False,
                "adjacent_bytes": False, "padding_or_free_space": False,
                "editing_or_relocation_safety": False}}


def build_payload(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    return _build_from_rom(root, _safe_file(root, ROM_PATH).read_bytes())


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
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(parent_fd, os.fsencode(source.name), parent_fd, os.fsencode(destination.name), flag):
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), destination)
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def export_artifact(root: Path, output: Path) -> Path:
    root = root.resolve(strict=True)
    output = output if output.is_absolute() else root / output
    parent = output.parent.resolve(strict=True)
    if not parent.is_relative_to(root):
        raise ValueError("output escapes project root")
    cursor = root
    for part in output.relative_to(root).parts[:-1]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("output has symlink ancestor")
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    payload = build_payload(root)
    relative = output.relative_to(root).as_posix()
    stage = Path(tempfile.mkdtemp(dir=parent, prefix=f".{output.name}."))
    try:
        payload_raw = _canonical(payload)
        (stage / PAYLOAD_NAME).write_bytes(payload_raw)
        manifest = {"schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,
            "artifact_status": "accepted", "files": {PAYLOAD_NAME: {"size": len(payload_raw),
            "sha256": _sha(payload_raw)}}, "summary": {"root_count": 10,
            "instruction_count": 1330, "code_bytes": 2692, "literal_bytes": 248,
            "promotion_bytes": 2940}, "producer": {"command": ["python3",
            "tools/export_rom_text_bg_task_closure.py", "--root", ".", "--output", relative]},
            "verifier": {"command": ["python3", "tools/verify_rom_text_bg_task_closure.py",
            "--root", ".", "--artifact", relative]}, "implementation": {
            "exporter_sha256": _sha(_safe_file(root, Path("tools/export_rom_text_bg_task_closure.py")).read_bytes()),
            "verifier_sha256": _sha(_safe_file(root, Path("tools/verify_rom_text_bg_task_closure.py")).read_bytes()),
            "test_sha256": _sha(_safe_file(root, Path("tests/test_export_rom_text_bg_task_closure.py")).read_bytes())}}
        (stage / MANIFEST_NAME).write_bytes(_canonical(manifest))
        for path in stage.iterdir():
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
        directory_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        _publish_exclusive(stage, output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=OFFICIAL)
    args = parser.parse_args()
    export_artifact(args.root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
