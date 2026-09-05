#!/usr/bin/env python3
"""Export the two unbound tail roots and the closed syntax at slot 46."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
from typing import Any
import uuid


SCHEMA = "rom-chapter-script-unbound-tail-v1"
ROM_PATH = Path("rom/base.gba")
BASELINE_COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_SIZE = 6_291_456
BASELINE_SHA256 = "b51f322daf9e1b9af453f5423fad590d81eb42ae0440cc76482553a15d574008"
ROM_BASE = 0x08000000

VECTOR_RANGE = (0x060FA4, 0x060FAC)
VECTOR_BYTES = bytes.fromhex("dfbf0508d3c60508")
VECTOR_SHA256 = "ff3c2f49e8e01470390987ec0e7978068910c45f3ea0f020c1bb0c5f588e553f"
LEFT_TABLE_RANGE = (0x060EF0, 0x060FA4)
LEFT_TABLE_SHA256 = "d5f04183747f3a68bc9c6e087c89b18a4b71e7a12cf85f6eec589050338594ed"
RIGHT_CODE_RANGE = (0x060FAC, 0x061024)
RIGHT_CODE_SHA256 = "9cd0b990d2e1a021448f60d31e4f340700005794c25edb8d6327989b7ca31944"
ROOT45 = 0x05BFDF
ROOT46 = 0x05C6D3
CLOSURE_RANGES = ((0x05BFDF, 0x05C5DC), (0x05C6D3, 0x05CD40))
CLOSURE_SHA256 = "7f6400492903560a93ba7d226a75986dbb298e78040156b0dc4bcf4cda5655e4"

INTERPRETER_RANGE = (0x0977B8, 0x097E34)
INTERPRETER_SHA256 = "1e0c0550c08d7bbdd3395085112ccc864caffbd10db9d840a86294454f6cd249"
DISPATCH_RANGE = (0x0977F4, 0x0978DC)
DISPATCH_SHA256 = "a3d2eb7489c851b040b87afeb6c2a020e15e5b6d9086c57f036be4893b12792d"
RENDERER_RANGE = (0x06626C, 0x066736)
RENDERER_SHA256 = "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"
SJIS_RANGE = (0x53D644, 0x53D73C)
SJIS_SHA256 = "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"

PAYLOAD_NAME = "rom-chapter-script-unbound-tail.json"
BUNDLE_NAME = "chapter-script-unbound-tail.bin"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _slice(raw: bytes, start: int, end: int) -> bytes:
    if not 0 <= start < end <= len(raw):
        raise ValueError(f"invalid ROM range: {start:#x}..{end:#x}")
    return raw[start:end]


def _u32(raw: bytes, offset: int) -> int:
    return struct.unpack_from("<I", _slice(raw, offset, offset + 4))[0]


def _pointer(raw: bytes, offset: int) -> int:
    value = _u32(raw, offset)
    target = value - ROM_BASE
    if not ROM_BASE <= value < ROM_BASE + len(raw):
        raise ValueError(f"invalid ROM pointer at {offset:#x}: {value:#x}")
    return target


def _sjis_pair_valid(raw: bytes, lead: int, trail: int) -> bool:
    code = lead << 8 | trail
    for offset in range(SJIS_RANGE[0], SJIS_RANGE[1], 8):
        lower = int.from_bytes(_slice(raw, offset, offset + 2), "little")
        if lower <= code < lower + raw[offset + 2]:
            return True
    return False


def _renderer_end(raw: bytes, offset: int) -> int:
    cursor = offset
    while True:
        value = _slice(raw, cursor, cursor + 1)[0]
        if value == 0:
            return cursor + 1
        if value == 1:
            width = 2
        elif value == 2:
            width = 3
        elif 0x80 <= value <= 0x9F:
            width = 2
        elif value >= 0xA0 and _sjis_pair_valid(raw, value, raw[cursor + 1]):
            width = 2
        else:
            width = 1
        _slice(raw, cursor, cursor + width)
        cursor += width


def _decode(raw: bytes, offset: int) -> tuple[int, int, list[int]]:
    opcode = raw[offset]
    if opcode == 0:
        return opcode, 1, []
    if opcode == 1:
        end = _renderer_end(raw, offset + 1)
        return opcode, end - offset, [end]
    if opcode in (2, 4):
        return opcode, 4, [offset + 4]
    if opcode == 8:
        return opcode, 2, [offset + 2]
    if opcode == 0x12:
        return opcode, 5, [offset + 5]
    if opcode == 0x32:
        cursor = offset
        successors: list[int] = []
        while raw[cursor] == 0x32:
            successors.append(_pointer(raw, cursor + 1))
            cursor += 5
        successors.append(cursor)
        return opcode, cursor - offset, successors
    raise ValueError(f"unsupported opcode {opcode:#x} at {offset:#x}")


def _walk(raw: bytes) -> tuple[list[dict[str, Any]], list[list[int]]]:
    pending = [ROOT45, ROOT46]
    nodes: dict[int, tuple[int, int, list[int]]] = {}
    while pending:
        offset = pending.pop()
        if offset in nodes:
            continue
        opcode, length, successors = _decode(raw, offset)
        if not any(start <= offset and offset + length <= end for start, end in CLOSURE_RANGES):
            raise ValueError(f"closure escaped frozen range at {offset:#x}")
        if any(not any(start <= edge < end for start, end in CLOSURE_RANGES) for edge in successors):
            raise ValueError(f"frontier escaped frozen range at {offset:#x}")
        nodes[offset] = (opcode, length, successors)
        pending.extend(reversed(successors))
    records = [
        {
            "file_offset": offset,
            "opcode": f"0x{opcode:02X}",
            "length": length,
            "range": [offset, offset + length],
            "bytes_sha256": _sha(raw[offset : offset + length]),
            "successors": successors,
        }
        for offset, (opcode, length, successors) in sorted(nodes.items())
    ]
    ranges: list[list[int]] = []
    for row in records:
        start, end = row["range"]
        if ranges and start <= ranges[-1][1]:
            ranges[-1][1] = max(ranges[-1][1], end)
        else:
            ranges.append([start, end])
    return records, ranges


def build_payload(root: Path, *, rom_override: bytes | None = None) -> dict[str, Any]:
    root = Path(root)
    rom = rom_override if rom_override is not None else (root / ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    # BASELINE_SHA256 is a historical reference, not an input observed by this
    # replayable build.  The coverage auditor proves current-unknown immediately
    # before projection and records that separate gate on the accepted claims.
    if _slice(rom, *VECTOR_RANGE) != VECTOR_BYTES or _sha(VECTOR_BYTES) != VECTOR_SHA256:
        raise ValueError("tail root vector changed")
    for start, end, expected, label in (
        (*LEFT_TABLE_RANGE, LEFT_TABLE_SHA256, "left table"),
        (*RIGHT_CODE_RANGE, RIGHT_CODE_SHA256, "right code"),
        (*INTERPRETER_RANGE, INTERPRETER_SHA256, "interpreter"),
        (*DISPATCH_RANGE, DISPATCH_SHA256, "dispatch"),
        (*RENDERER_RANGE, RENDERER_SHA256, "renderer"),
        (*SJIS_RANGE, SJIS_SHA256, "SJIS ranges"),
    ):
        if _sha(_slice(rom, start, end)) != expected:
            raise ValueError(f"{label} identity changed")
    if (_pointer(rom, VECTOR_RANGE[0]), _pointer(rom, VECTOR_RANGE[0] + 4)) != (ROOT45, ROOT46):
        raise ValueError("tail roots changed")
    nodes, merged = _walk(rom)
    bundle = b"".join(rom[a:b] for a, b in merged)
    counts = Counter(row["opcode"] for row in nodes)
    edge_count = sum(len(row["successors"]) for row in nodes)
    summary = {
        "node_count": len(nodes),
        "directed_edge_count": edge_count,
        "terminal_node_count": counts["0x00"],
        "opcode_counts": dict(sorted(counts.items())),
        "frontier_count": 0,
        "consumed_bytes": len(bundle),
    }
    expected_summary = {
        "node_count": 128,
        "directed_edge_count": 128,
        "terminal_node_count": 13,
        "opcode_counts": {"0x00": 13, "0x01": 47, "0x02": 4, "0x04": 3, "0x08": 47, "0x12": 12, "0x32": 2},
        "frontier_count": 0,
        "consumed_bytes": 3178,
    }
    if summary != expected_summary or merged != [list(row) for row in CLOSURE_RANGES] or _sha(bundle) != CLOSURE_SHA256:
        raise ValueError("unbound chapter closure denominator changed")
    node_vector_sha = _sha(json.dumps(nodes, sort_keys=True, separators=(",", ":")).encode())
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},
        "historical_coverage_reference": {
            "path": BASELINE_COVERAGE_PATH.as_posix(),
            "sha256": BASELINE_SHA256,
            "observed_during_this_build": False,
            "projection_gate_deferred_to": "tools/audit_rom_byte_coverage.py",
        },
        "scope": {
            "fixed_physical_tail_vector_complete": True,
            "both_tail_roots_parser_consumed_union_complete": True,
            "consumer_bound": False,
            "natural_reachability_complete": False,
            "editing_safety_proven": False,
        },
        "root_vector": {
            "file_range": [*VECTOR_RANGE], "bytes": VECTOR_BYTES.hex(), "sha256": VECTOR_SHA256,
            "kind": "fixed_physical_tail_root_vector", "consumer_asserted": False,
            "natural_reachability_asserted": False,
            "left_bound_table": {"range": [*LEFT_TABLE_RANGE], "sha256": LEFT_TABLE_SHA256},
            "right_bound_code": {"range": [*RIGHT_CODE_RANGE], "sha256": RIGHT_CODE_SHA256},
            "entries": [
                {"slot": 45, "target_file_offset": ROOT45, "target_already_classified": False},
                {"slot": 46, "target_file_offset": ROOT46, "target_already_classified": False},
            ],
        },
        "grammar": {
            "interpreter_range": [*INTERPRETER_RANGE], "interpreter_sha256": INTERPRETER_SHA256,
            "dispatch_range": [*DISPATCH_RANGE], "dispatch_sha256": DISPATCH_SHA256,
            "renderer_range": [*RENDERER_RANGE], "renderer_sha256": RENDERER_SHA256,
            "sjis_range": [*SJIS_RANGE], "sjis_sha256": SJIS_SHA256,
            "supported_opcodes": ["0x00", "0x01", "0x02", "0x04", "0x08", "0x12", "0x32"],
            "edge_policy": "preserve_order_and_duplicates",
        },
        "nodes": nodes,
        "closure": {
            "roots": [ROOT45, ROOT46], "merged_ranges": merged, "frontiers": [],
            "bundle_sha256": CLOSURE_SHA256, "node_vector_sha256": node_vector_sha,
            "summary": summary,
        },
        "promotion": {
            "promotion_bytes": 3186,
            "claims": [
                {"id": "chapter-unbound-tail-root-vector", "range": [*VECTOR_RANGE], "primary_class": "chapter_script_unbound_root_pointer_vector", "bytes_sha256": VECTOR_SHA256},
                {"id": "chapter-unbound-tail-slot45-closure", "range": [*CLOSURE_RANGES[0]], "primary_class": "chapter_script_syntax_unbound", "bytes_sha256": "8888bf12f58d66e2f8200d98459cadeefbd07f92a808ebc8ec5cc2bb90a620d7"},
                {"id": "chapter-unbound-tail-slot46-closure", "range": [*CLOSURE_RANGES[1]], "primary_class": "chapter_script_syntax_unbound", "bytes_sha256": "97d34f067a098b873371892801f5cde232ef4059a7889dd33b1549ddbd3695ba"},
            ],
        },
        "limitations": [
            "The two physical tail pointers are not asserted to have a live consumer.",
            "The two root closures prove interpreter syntax only, not natural gameplay reachability or decoded language.",
            "No editing, relocation, padding, or allocatable-space claim is made.",
        ],
    }


def _source_sha(path: Path) -> str:
    return _sha(path.read_bytes())


def _reject_symlink_components(path: Path) -> None:
    absolute = path.absolute()
    for candidate in (absolute, *absolute.parents):
        if candidate.is_symlink():
            raise ValueError(f"output path contains symlink: {candidate}")


def _open_directory_no_symlinks(path: Path) -> int:
    absolute = path.absolute()
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


def export_artifact(root: Path, output: Path) -> None:
    root, output = Path(root), Path(output)
    _reject_symlink_components(output)
    if output.exists():
        raise ValueError("output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(root)
    payload_raw = _canonical(payload)
    rom = (root / ROM_PATH).read_bytes()
    bundle = b"".join(rom[start:end] for start, end in CLOSURE_RANGES)
    exporter_path = Path(__file__).resolve()
    verifier_path = exporter_path.with_name("verify_rom_unbound_chapter_script_tail.py")
    manifest = {
        "schema": "rom-chapter-script-unbound-tail-manifest-v1",
        "artifact_status": "candidate",
        "files": {
            PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)},
            BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bundle)},
        },
        "implementation": {
            "exporter": {"path": exporter_path.relative_to(root.resolve()).as_posix(), "sha256": _source_sha(exporter_path)},
            "verifier": {"path": verifier_path.relative_to(root.resolve()).as_posix(), "sha256": _source_sha(verifier_path)},
        },
        "promotion": {"promotion_bytes": 3186, "claim_count": 3},
    }
    parent_fd = _open_directory_no_symlinks(output.parent)
    temporary_name = f".{output.name}.{uuid.uuid4().hex}"
    temporary_fd = -1
    try:
        try:
            os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError("output already exists")
        os.mkdir(temporary_name, 0o700, dir_fd=parent_fd)
        temporary_fd = os.open(
            temporary_name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        for name, raw in (
            (PAYLOAD_NAME, payload_raw),
            (BUNDLE_NAME, bundle),
            ("manifest.json", _canonical(manifest)),
        ):
            file_fd = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o644,
                dir_fd=temporary_fd,
            )
            try:
                with os.fdopen(file_fd, "wb", closefd=False) as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                os.close(file_fd)
        os.fsync(temporary_fd)
        os.rename(
            temporary_name,
            output.name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
        os.fsync(parent_fd)
        temporary_name = ""
    except Exception:
        if temporary_fd >= 0:
            for name in (PAYLOAD_NAME, BUNDLE_NAME, "manifest.json"):
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export_artifact(args.root.resolve(), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
