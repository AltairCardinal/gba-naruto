#!/usr/bin/env python3
"""Export the two hash-bound chapter-script parser consumer closures.

The packet is deliberately self-contained: the parser grammar is decoded from
raw ROM bytes, while the two consumer slices provide the fixed data-flow roots.
The current coverage file is recorded only as a historical reference and is
never read by this exporter.
"""

from __future__ import annotations

import argparse
from collections import Counter
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import uuid
from typing import Any


SCHEMA = "rom-chapter-script-consumer-roots-v1"
MANIFEST_SCHEMA = "rom-chapter-script-consumer-roots-manifest-v1"
VERIFY_SCHEMA = "rom-chapter-script-consumer-roots-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_BASE = 0x08000000

# This identity is a historical reference only.  The exporter must not open
# or parse the mutable coverage file; projection is a later auditor concern.
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
COVERAGE_SHA256 = "3b13c811baf8f8d14af074e9c2dc9057932cfe720ad8e16e06f8f6cd17d09daf"

CONSUMER_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "consumer-root1",
        "range": (0x08A534, 0x08A588),
        "sha256": "2eebdb3fecb96d74024180c6c3ff764d9ed0af2a25860a985f714cc9da8d57ad",
        "root": 0x05CD41,
        "literal_offset": 0x08A558,
        "load_offset": 0x08A548,
        "call_offset": 0x08A54C,
    },
    {
        "id": "consumer-root2",
        "range": (0x08A588, 0x08A638),
        "sha256": "b530a0bcb184060e1e1a576307919bc09e937bb1c2297d55b0f0ea879c978299",
        "root": 0x05D593,
        "literal_offset": 0x08A630,
        "load_offset": 0x08A5E8,
        "call_offset": 0x08A5FC,
    },
)

ROOT_RANGES = ((0x05CD41, 0x05D593), (0x05D593, 0x060C70))
ROOTS = (ROOT_RANGES[0][0], ROOT_RANGES[1][0])
ROOT_BUNDLE_SHA256 = (
    "cab4ef4ab61ecdb4589627f9d6043291583668132020cd6f2678b0c49ced013c",
    "536e360a8006ace91135080e29981495559ff8555275fa0a505ae951cd9eee4f",
)
UNION_BUNDLE_SHA256 = "7e506f02abfe85c21a01066ce010b40d0a43b8d528fb53b77cc3be7cb1b22907"
NODE_VECTOR_SHA256 = "60c3a271dbd095b1d922d04215ce8050d6496bbd18e39410222e217304ff6a36"
EDGE_VECTOR_SHA256 = "3cea3a0c8a891d48e73a3d4a1ad13d3043a67236506a4ea6d3e160bc8b260ea4"

INTERPRETER_RANGE = (0x0977B8, 0x097E34)
INTERPRETER_SHA256 = "1e0c0550c08d7bbdd3395085112ccc864caffbd10db9d840a86294454f6cd249"
DISPATCH_RANGE = (0x0977F4, 0x0978DC)
DISPATCH_SHA256 = "a3d2eb7489c851b040b87afeb6c2a020e15e5b6d9086c57f036be4893b12792d"
RENDERER_RANGE = (0x06626C, 0x066736)
RENDERER_SHA256 = "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"
SJIS_RANGE = (0x53D644, 0x53D73C)
SJIS_SHA256 = "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"

PAYLOAD_NAME = "rom-chapter-script-consumer-roots.json"
BUNDLE_NAME = "chapter-script-consumer-roots.bin"
MANIFEST_NAME = "manifest.json"
EXPECTED_FILES = {PAYLOAD_NAME, BUNDLE_NAME, MANIFEST_NAME}

FIXED_LENGTHS = {
    0x02: 4,
    0x03: 2,
    0x04: 4,
    0x08: 2,
    0x09: 2,
    0x0A: 2,
    0x0E: 3,
    0x0F: 2,
    0x10: 1,
    0x11: 2,
    0x12: 5,
    0x14: 3,
    0x16: 2,
    0x17: 4,
    0x18: 4,
    0x19: 4,
    0x1A: 3,
    0x1B: 3,
    0x1C: 3,
    0x1D: 3,
    0x1E: 2,
    0x1F: 2,
    0x21: 5,
    0x22: 4,
    0x23: 3,
    0x33: 2,
    0x37: 3,
}
CONDITIONAL_LAYOUTS = {
    0x0B: (6, 2),
    0x0C: (6, 2),
    0x15: (8, 4),
    0x34: (8, 4),
    0x35: (9, 5),
    0x36: (8, 4),
    0x38: (7, 3),
    0x39: (6, 2),
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _compact_sha(value: Any) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("ascii"))


def _slice(rom: bytes, start: int, end: int) -> bytes:
    if start < 0 or end <= start or end > len(rom):
        raise ValueError(f"invalid ROM range: 0x{start:06X}..0x{end:06X}")
    return rom[start:end]


def _u8(rom: bytes, offset: int) -> int:
    return _slice(rom, offset, offset + 1)[0]


def _u16(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<H", _slice(rom, offset, offset + 2))[0]


def _u32(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<I", _slice(rom, offset, offset + 4))[0]


def _pointer(rom: bytes, offset: int, label: str) -> int:
    value = _u32(rom, offset)
    target = value - ROM_BASE
    if not ROM_BASE <= value < ROM_BASE + len(rom):
        raise ValueError(f"{label} is not an in-ROM pointer: 0x{value:08X}")
    return target


def _sjis_pair_valid(rom: bytes, lead: int, trail: int) -> bool:
    code = lead << 8 | trail
    for offset in range(SJIS_RANGE[0], SJIS_RANGE[1], 8):
        lower = int.from_bytes(_slice(rom, offset, offset + 2), "little")
        if lower <= code < lower + _u8(rom, offset + 2):
            return True
    return False


def _renderer_text_end(rom: bytes, offset: int) -> int:
    cursor = offset
    while True:
        value = _u8(rom, cursor)
        if value == 0:
            return cursor + 1
        if value == 1:
            width = 2
        elif value == 2:
            width = 3
        elif 0x80 <= value <= 0x9F:
            width = 2
        elif value >= 0xA0 and _sjis_pair_valid(rom, value, _u8(rom, cursor + 1)):
            width = 2
        else:
            width = 1
        _slice(rom, cursor, cursor + width)
        cursor += width


def _token_text_end(rom: bytes, offset: int) -> int:
    cursor = offset
    while True:
        value = _u8(rom, cursor)
        if value == 0:
            return cursor + 1
        if value == 1 or 0x80 <= value <= 0x9F:
            width = 2
        elif value == 2:
            width = 3
        else:
            width = 1
        _slice(rom, cursor, cursor + width)
        cursor += width


def _decode_node(rom: bytes, offset: int) -> tuple[int, int, list[int]]:
    """Decode one record using only raw-ROM parser grammar."""

    opcode = _u8(rom, offset)
    if opcode == 0:
        return opcode, 1, []
    if opcode in FIXED_LENGTHS:
        size = FIXED_LENGTHS[opcode]
        _slice(rom, offset, offset + size)
        return opcode, size, [offset + size]
    if opcode == 1:
        end = _renderer_text_end(rom, offset + 1)
        return opcode, end - offset, [end]
    if opcode in (5, 0x20):
        end = _renderer_text_end(rom, offset + 2)
        return opcode, end - offset, [end]
    if opcode == 6:
        return opcode, 9, [
            _pointer(rom, offset + 1, "opcode 0x06 first target"),
            _pointer(rom, offset + 5, "opcode 0x06 second target"),
        ]
    if opcode == 7:
        return opcode, 5, [_pointer(rom, offset + 1, "opcode 0x07 target")]
    if opcode in CONDITIONAL_LAYOUTS:
        size, pointer_offset = CONDITIONAL_LAYOUTS[opcode]
        return opcode, size, [
            _pointer(rom, offset + pointer_offset, f"opcode 0x{opcode:02X} target"),
            offset + size,
        ]
    if opcode == 0x0D:
        return opcode, 5, [
            _pointer(rom, offset + 1, "opcode 0x0D target"),
            offset + 5,
        ]
    if opcode == 0x13:
        first_end = _token_text_end(rom, offset + 4)
        if _u8(rom, offset + 2) == 0:
            return opcode, first_end - offset, [first_end]
        second_end = _token_text_end(rom, first_end + 1)
        return opcode, second_end - offset, [second_end]
    if opcode == 0x32:
        cursor = offset
        successors: list[int] = []
        while _u8(rom, cursor) == 0x32:
            successors.append(_pointer(rom, cursor + 1, "opcode 0x32 case target"))
            cursor += 5
        successors.append(cursor)
        return opcode, cursor - offset, successors
    if 0x24 <= opcode <= 0x31:
        raise ValueError(f"reserved opcode 0x{opcode:02X} at 0x{offset:06X}")
    raise ValueError(f"unsupported opcode 0x{opcode:02X} at 0x{offset:06X}")


def _edge_kind(opcode: int, successor_index: int, successor_count: int) -> str:
    pointer = opcode in (0x06, 0x07, 0x0D)
    pointer = pointer or (
        opcode in CONDITIONAL_LAYOUTS and successor_index == 0
    )
    pointer = pointer or (opcode == 0x32 and successor_index < successor_count - 1)
    return "pointer_target" if pointer else "fallthrough"


def _walk_root(rom: bytes, root: int, bounds: tuple[int, int]) -> list[dict[str, Any]]:
    pending = [root]
    decoded: dict[int, tuple[int, int, list[int]]] = {}
    while pending:
        offset = pending.pop(0)
        if offset in decoded:
            continue
        opcode, length, successors = _decode_node(rom, offset)
        start, end = bounds
        if not (start <= offset and offset + length <= end):
            raise ValueError(f"node escaped frozen root range at 0x{offset:06X}")
        if any(not (start <= target < end) for target in successors):
            raise ValueError(f"frontier escaped frozen root at 0x{offset:06X}")
        decoded[offset] = (opcode, length, successors)
        pending.extend(target for target in successors if target not in decoded)
    return [
        {
            "file_offset": offset,
            "opcode": f"0x{opcode:02X}",
            "length": length,
            "range": [offset, offset + length],
            "bytes_sha256": _sha(rom[offset : offset + length]),
            "successors": successors,
        }
        for offset, (opcode, length, successors) in sorted(decoded.items())
    ]


def _validate_evidence(rom: bytes) -> None:
    for spec in CONSUMER_SPECS:
        start, end = spec["range"]
        if _sha(_slice(rom, start, end)) != spec["sha256"]:
            raise ValueError(f"{spec['id']} consumer slice changed")
    for bounds, expected, label in (
        (INTERPRETER_RANGE, INTERPRETER_SHA256, "interpreter"),
        (DISPATCH_RANGE, DISPATCH_SHA256, "dispatch"),
        (RENDERER_RANGE, RENDERER_SHA256, "renderer"),
        (SJIS_RANGE, SJIS_SHA256, "SJIS"),
    ):
        if _sha(_slice(rom, *bounds)) != expected:
            raise ValueError(f"{label} grammar evidence changed")

    for spec in CONSUMER_SPECS:
        load = spec["load_offset"]
        halfword = _u16(rom, load)
        if halfword & 0xF800 != 0x4800:
            raise ValueError(f"{spec['id']} LDR literal instruction changed")
        literal = ((load + 4) & ~3) + (halfword & 0xFF) * 4
        if literal != spec["literal_offset"]:
            raise ValueError(f"{spec['id']} literal binding changed")
        if _pointer(rom, literal, f"{spec['id']} literal") != spec["root"]:
            raise ValueError(f"{spec['id']} root literal changed")
        expected_load_register = 0 if spec["id"] == "consumer-root1" else 5
        if (halfword >> 8) & 0x7 != expected_load_register:
            raise ValueError(f"{spec['id']} root load register changed")
        call = spec["call_offset"]
        first, second = _u16(rom, call), _u16(rom, call + 2)
        if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
            raise ValueError(f"{spec['id']} parser BL changed")
        displacement = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
        if displacement & (1 << 22):
            displacement -= 1 << 23
        if call + 4 + displacement != INTERPRETER_RANGE[0]:
            raise ValueError(f"{spec['id']} parser BL target changed")
        if spec["id"] == "consumer-root1" and _u16(rom, 0x08A54A) != 0x2100:
            raise ValueError("consumer-root1 parser argument setup changed")
        if spec["id"] == "consumer-root2" and (
            _u16(rom, 0x08A5F8) != 0x1C28 or _u16(rom, 0x08A5FA) != 0x1C31
        ):
            raise ValueError("consumer-root2 parser argument register flow changed")


def _records_for_root(nodes: list[dict[str, Any]]) -> tuple[list[list[int]], list[list[int]], Counter[str]]:
    node_vector = [
        [row["file_offset"], int(row["opcode"], 16), row["length"]]
        for row in nodes
    ]
    edge_vector: list[list[Any]] = []
    for row in nodes:
        for index, target in enumerate(row["successors"]):
            edge_vector.append(
                [
                    row["file_offset"],
                    target,
                    _edge_kind(int(row["opcode"], 16), index, len(row["successors"])),
                ]
            )
    edge_vector.sort(key=lambda row: (row[0], row[1], row[2]))
    return node_vector, edge_vector, Counter(row["opcode"] for row in nodes)


def _root_summary(nodes: list[dict[str, Any]], bounds: tuple[int, int]) -> dict[str, Any]:
    node_vector, edge_vector, counts = _records_for_root(nodes)
    return {
        "range": list(bounds),
        "bytes": bounds[1] - bounds[0],
        "node_count": len(nodes),
        "directed_edge_count": len(edge_vector),
        "terminal_node_count": counts["0x00"],
        "frontier_count": 0,
        "opcode_counts": dict(sorted(counts.items())),
        "bundle_sha256": ROOT_BUNDLE_SHA256[ROOT_RANGES.index(bounds)],
        "node_vector_sha256": _compact_sha(node_vector),
        "edge_vector_sha256": _compact_sha(edge_vector),
    }


def build_payload(root: Path, *, rom_override: bytes | None = None) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    rom = rom_override if rom_override is not None else (root / ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    _validate_evidence(rom)

    root_nodes = [
        _walk_root(rom, root_offset, bounds)
        for root_offset, bounds in zip(ROOTS, ROOT_RANGES)
    ]
    root_summaries = [
        _root_summary(nodes, bounds)
        for nodes, bounds in zip(root_nodes, ROOT_RANGES)
    ]
    all_nodes = sorted(
        [node for nodes in root_nodes for node in nodes],
        key=lambda row: row["file_offset"],
    )
    node_vector, edge_vector, counts = _records_for_root(all_nodes)
    if [
        (summary["node_count"], summary["directed_edge_count"], summary["terminal_node_count"], summary["bytes"])
        for summary in root_summaries
    ] != [(406, 608, 1, 2130), (714, 714, 101, 14045)]:
        raise ValueError("chapter consumer-root closure denominator changed")
    if _compact_sha(node_vector) != NODE_VECTOR_SHA256 or _compact_sha(edge_vector) != EDGE_VECTOR_SHA256:
        raise ValueError("chapter consumer-root canonical vector changed")
    if len(all_nodes) != 1120 or len(edge_vector) != 1322 or counts["0x00"] != 102:
        raise ValueError("chapter consumer-root union denominator changed")

    union_bundle = _slice(rom, ROOT_RANGES[0][0], ROOT_RANGES[-1][1])
    if _sha(union_bundle) != UNION_BUNDLE_SHA256:
        raise ValueError("chapter consumer-root union bytes changed")
    root_node_sets = [
        {row["file_offset"] for row in nodes} for nodes in root_nodes
    ]
    root_byte_sets = [
        {byte for row in nodes for byte in range(row["range"][0], row["range"][1])}
        for nodes in root_nodes
    ]
    if root_node_sets[0] & root_node_sets[1] or root_byte_sets[0] & root_byte_sets[1]:
        raise ValueError("chapter consumer-root closures overlap")
    root1_to_root2 = any(
        target >= ROOT_RANGES[1][0]
        for row in root_nodes[0]
        for target in row["successors"]
    )
    if root1_to_root2:
        raise ValueError("chapter consumer-root cross-edge changed")

    consumer_bindings = [
        {
            "id": spec["id"],
            "range": list(spec["range"]),
            "sha256": spec["sha256"],
            "root": spec["root"],
            "literal_offset": spec["literal_offset"],
            "load_offset": spec["load_offset"],
            "call_offset": spec["call_offset"],
        }
        for spec in CONSUMER_SPECS
    ]
    consumer_dataflow = [
        {
            **binding,
            "literal_value": f"0x{ROM_BASE + binding['root']:08X}",
            "literal_sha256": _sha(_slice(rom, binding["literal_offset"], binding["literal_offset"] + 4)),
            "parser_target": INTERPRETER_RANGE[0],
            "parser_target_gba": f"0x{ROM_BASE + INTERPRETER_RANGE[0]:08X}",
            "root_dataflow": "LDR literal -> root argument -> BL chapter parser",
            "root_register_flow": (
                {"load_register": "r0", "argument_register": "r0", "argument_move": None}
                if binding["id"] == "consumer-root1"
                else {
                    "load_register": "r5",
                    "argument_register": "r0",
                    "argument_move": {"offset": 0x08A5F8, "halfword": "0x1C28"},
                }
            ),
            "secondary_argument_move": (
                None
                if binding["id"] == "consumer-root1"
                else {"offset": 0x08A5FA, "halfword": "0x1C31", "register": "r1"}
            ),
        }
        for binding in consumer_bindings
    ]
    closures = {
        "roots": list(ROOTS),
        "ranges": [list(bounds) for bounds in ROOT_RANGES],
        "range_sha256": list(ROOT_BUNDLE_SHA256),
        "bundle_sha256": UNION_BUNDLE_SHA256,
        "merged_ranges": [[ROOT_RANGES[0][0], ROOT_RANGES[-1][1]]],
        "frontiers": [],
        "node_vector_sha256": NODE_VECTOR_SHA256,
        "edge_vector_sha256": EDGE_VECTOR_SHA256,
        "summary": {
            "root1": {
                "nodes": root_summaries[0]["node_count"],
                "edges": root_summaries[0]["directed_edge_count"],
                "terminals": root_summaries[0]["terminal_node_count"],
                "bytes": root_summaries[0]["bytes"],
            },
            "root2": {
                "nodes": root_summaries[1]["node_count"],
                "edges": root_summaries[1]["directed_edge_count"],
                "terminals": root_summaries[1]["terminal_node_count"],
                "bytes": root_summaries[1]["bytes"],
            },
            "union": {
                "nodes": len(all_nodes),
                "edges": len(edge_vector),
                "terminals": counts["0x00"],
                "bytes": ROOT_RANGES[-1][1] - ROOT_RANGES[0][0],
            },
        },
        "root_records": root_summaries,
        "root_intersection": {
            "node_offsets": sorted(root_node_sets[0] & root_node_sets[1]),
            "byte_offsets": sorted(root_byte_sets[0] & root_byte_sets[1]),
            "root1_to_root2_edge": root1_to_root2,
        },
        "nodes": all_nodes,
    }
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},
        "historical_coverage_reference": {
            "path": COVERAGE_PATH.as_posix(),
            "sha256": COVERAGE_SHA256,
            "observed_during_this_build": False,
            "projection_gate_deferred_to": "tools/audit_rom_byte_coverage.py",
        },
        "scope": {
            "fixed_consumer_dataflow_complete": True,
            "two_parser_consumer_closures_complete": True,
            "static_control_flow_closure_complete": True,
            "current_unknown_checked": False,
            "natural_reachability_complete": False,
            "natural_language_decoding_complete": False,
            "editing_relocation_safe": False,
        },
        "consumer_bindings": consumer_bindings,
        "consumer_dataflow": consumer_dataflow,
        "grammar": {
            "interpreter_range": list(INTERPRETER_RANGE),
            "interpreter_sha256": INTERPRETER_SHA256,
            "dispatch_range": list(DISPATCH_RANGE),
            "dispatch_sha256": DISPATCH_SHA256,
            "renderer_range": list(RENDERER_RANGE),
            "renderer_sha256": RENDERER_SHA256,
            "sjis_range": list(SJIS_RANGE),
            "sjis_sha256": SJIS_SHA256,
            "supported_opcodes": [f"0x{opcode:02X}" for opcode in sorted(set(FIXED_LENGTHS) | set(CONDITIONAL_LAYOUTS) | {0, 1, 5, 6, 7, 0x0D, 0x13, 0x20, 0x32})],
            "edge_policy": "preserve_order_and_duplicates",
            "edge_kinds": {"pointer_target": "encoded ROM pointer target", "fallthrough": "next record in parser grammar"},
        },
        "closures": closures,
        "non_claims": {
            "adjacent_boundaries": {"left": [0x05CD40, 0x05CD41], "right": [0x060C70, 0x060C74]},
            "claims": [
                {"range": [0x05CD40, 0x05CD41], "claimed": False, "reason": "left byte immediately before root1"},
                {"range": [0x060C70, 0x060C74], "claimed": False, "reason": "right bytes immediately after root2"},
            ],
        },
        "promotion": {
            "promotion_bytes": ROOT_RANGES[-1][1] - ROOT_RANGES[0][0],
            "claims": [
                {
                    "id": "chapter-script-consumer-root1-closure",
                    "range": list(ROOT_RANGES[0]),
                    "primary_class": "chapter_script_syntax_consumer_bound",
                    "bytes_sha256": ROOT_BUNDLE_SHA256[0],
                },
                {
                    "id": "chapter-script-consumer-root2-closure",
                    "range": list(ROOT_RANGES[1]),
                    "primary_class": "chapter_script_syntax_consumer_bound",
                    "bytes_sha256": ROOT_BUNDLE_SHA256[1],
                },
            ],
        },
        "limitations": [
            "The two exact consumer slices are bound as evidence; only the two closures are classified and promoted.",
            "The parser grammar proves byte-level syntax and control-flow closure, not natural gameplay reachability or natural-language decoding.",
            "The left boundary byte 0x05CD40 and right boundary bytes 0x060C70..0x060C74 are explicitly not claimed.",
            "Current-unknown coverage projection, padding/free-space status, editing, write-back, relocation, and allocatability are outside this packet.",
        ],
    }


def _reject_symlink_components(path: Path) -> None:
    absolute = Path(path).absolute()
    for candidate in (absolute, *absolute.parents):
        if candidate.is_symlink():
            raise ValueError(f"output path contains symlink: {candidate}")


def _open_directory_no_symlinks(path: Path) -> int:
    absolute = Path(path).absolute()
    directory_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in absolute.parts[1:]:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=directory_fd,
            )
            os.close(directory_fd)
            directory_fd = next_fd
        return directory_fd
    except Exception:
        os.close(directory_fd)
        raise


def _source_sha(path: Path) -> str:
    return _sha(path.read_bytes())


def _rename_noreplace_at(
    source_fd: int,
    source: str,
    destination_fd: int,
    destination: str,
) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename = libc.renameatx_np
        flag = 0x00000004  # RENAME_EXCL
    elif hasattr(libc, "renameat2"):
        rename = libc.renameat2
        flag = 0x00000001  # RENAME_NOREPLACE
    else:
        raise OSError(errno.ENOTSUP, "atomic no-replace rename is unavailable")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(source_fd, os.fsencode(source), destination_fd, os.fsencode(destination), flag):
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), destination)


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output = Path(output)
    _reject_symlink_components(output)
    if output.exists():
        raise ValueError("output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(root)
    payload_raw = _canonical(payload)
    rom = (root / ROM_PATH).read_bytes()
    bundle = _slice(rom, ROOT_RANGES[0][0], ROOT_RANGES[-1][1])
    exporter_path = Path(__file__).resolve()
    verifier_path = exporter_path.with_name("verify_rom_chapter_script_consumer_roots.py")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "artifact_status": "candidate",
        "files": {
            PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)},
            BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bundle)},
        },
        "implementation": {
            "exporter": {"path": exporter_path.relative_to(root).as_posix(), "sha256": _source_sha(exporter_path)},
            "verifier": {"path": verifier_path.relative_to(root).as_posix(), "sha256": _source_sha(verifier_path)},
        },
        "promotion": {"promotion_bytes": payload["promotion"]["promotion_bytes"], "claim_count": len(payload["promotion"]["claims"])},
    }
    parent_fd = _open_directory_no_symlinks(output.parent)
    temporary_name = f".{output.name}.{uuid.uuid4().hex}"
    temporary_fd = -1
    committed = False
    try:
        try:
            os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError("output already exists")
        os.mkdir(temporary_name, 0o700, dir_fd=parent_fd)
        temporary_fd = os.open(temporary_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        for name, raw in (
            (PAYLOAD_NAME, payload_raw),
            (BUNDLE_NAME, bundle),
            (MANIFEST_NAME, _canonical(manifest)),
        ):
            file_fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=temporary_fd)
            try:
                with os.fdopen(file_fd, "wb", closefd=False) as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                os.close(file_fd)
        os.fsync(temporary_fd)
        try:
            _rename_noreplace_at(parent_fd, temporary_name, parent_fd, output.name)
        except FileExistsError as error:
            raise ValueError("output already exists") from error
        committed = True
        temporary_name = ""
        os.fsync(parent_fd)
    except Exception:
        if temporary_fd >= 0 and not committed:
            for name in (PAYLOAD_NAME, BUNDLE_NAME, MANIFEST_NAME):
                try:
                    os.unlink(name, dir_fd=temporary_fd)
                except FileNotFoundError:
                    pass
        if temporary_name:
            try:
                os.rmdir(temporary_name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        raise
    finally:
        if temporary_fd >= 0:
            os.close(temporary_fd)
        os.close(parent_fd)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", "--output-dir", dest="output", type=Path, required=True)
    args = parser.parse_args(argv)
    export_artifact(args.root.resolve(), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
