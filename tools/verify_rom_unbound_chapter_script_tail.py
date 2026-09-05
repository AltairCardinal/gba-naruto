#!/usr/bin/env python3
"""Independent verifier for the unbound chapter-script tail artifact."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
from typing import Any
import uuid


ROM_BASE = 0x08000000
ROM_SHA = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_SIZE = 6_291_456
BASELINE_SHA = "b51f322daf9e1b9af453f5423fad590d81eb42ae0440cc76482553a15d574008"
VECTOR = (0x060FA4, 0x060FAC)
VECTOR_RAW = bytes.fromhex("dfbf0508d3c60508")
VECTOR_SHA = "ff3c2f49e8e01470390987ec0e7978068910c45f3ea0f020c1bb0c5f588e553f"
CLOSURES = ((0x05BFDF, 0x05C5DC), (0x05C6D3, 0x05CD40))
CLOSURE_SHA = "7f6400492903560a93ba7d226a75986dbb298e78040156b0dc4bcf4cda5655e4"
ROOT45, ROOT46 = 0x05BFDF, 0x05C6D3
LEFT = (0x060EF0, 0x060FA4, "d5f04183747f3a68bc9c6e087c89b18a4b71e7a12cf85f6eec589050338594ed")
RIGHT = (0x060FAC, 0x061024, "9cd0b990d2e1a021448f60d31e4f340700005794c25edb8d6327989b7ca31944")
EVIDENCE = (
    (0x0977B8, 0x097E34, "1e0c0550c08d7bbdd3395085112ccc864caffbd10db9d840a86294454f6cd249"),
    (0x0977F4, 0x0978DC, "a3d2eb7489c851b040b87afeb6c2a020e15e5b6d9086c57f036be4893b12792d"),
    (0x06626C, 0x066736, "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"),
    (0x53D644, 0x53D73C, "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"),
)
PAYLOAD = "rom-chapter-script-unbound-tail.json"
BUNDLE = "chapter-script-unbound-tail.bin"
FILES = {"manifest.json", PAYLOAD, BUNDLE}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


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


def _read_regular_at(directory_fd: int, name: str) -> bytes:
    file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
    try:
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            raise ValueError("artifact contains non-regular file")
        chunks = []
        while True:
            chunk = os.read(file_fd, 1 << 20)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
    finally:
        os.close(file_fd)


def _ptr(raw: bytes, offset: int) -> int:
    value = struct.unpack_from("<I", raw, offset)[0]
    if not ROM_BASE <= value < ROM_BASE + len(raw):
        raise ValueError("pointer escaped ROM")
    return value - ROM_BASE


def _sjis(raw: bytes, lead: int, trail: int) -> bool:
    code = lead << 8 | trail
    for offset in range(0x53D644, 0x53D73C, 8):
        lower = int.from_bytes(raw[offset : offset + 2], "little")
        if lower <= code < lower + raw[offset + 2]:
            return True
    return False


def _text_end(raw: bytes, offset: int) -> int:
    cursor = offset
    while cursor < len(raw):
        value = raw[cursor]
        if value == 0:
            return cursor + 1
        if value == 1 or 0x80 <= value <= 0x9F:
            width = 2
        elif value == 2:
            width = 3
        elif value >= 0xA0 and cursor + 1 < len(raw) and _sjis(raw, value, raw[cursor + 1]):
            width = 2
        else:
            width = 1
        cursor += width
    raise ValueError("unterminated renderer string")


def _decode(raw: bytes, offset: int) -> tuple[int, int, list[int]]:
    opcode = raw[offset]
    if opcode == 0:
        return opcode, 1, []
    if opcode == 1:
        end = _text_end(raw, offset + 1)
        return opcode, end - offset, [end]
    if opcode in (2, 4):
        return opcode, 4, [offset + 4]
    if opcode == 8:
        return opcode, 2, [offset + 2]
    if opcode == 0x12:
        return opcode, 5, [offset + 5]
    if opcode == 0x32:
        cursor, edges = offset, []
        while raw[cursor] == 0x32:
            edges.append(_ptr(raw, cursor + 1))
            cursor += 5
        edges.append(cursor)
        return opcode, cursor - offset, edges
    raise ValueError(f"unsupported opcode {opcode:#x}")


def _independent_walk(raw: bytes) -> tuple[list[dict[str, Any]], list[list[int]], dict[str, Any]]:
    pending, decoded = [ROOT45, ROOT46], {}
    while pending:
        offset = pending.pop(0)
        if offset in decoded:
            continue
        opcode, length, edges = _decode(raw, offset)
        if not any(start <= offset and offset + length <= end for start, end in CLOSURES):
            raise ValueError("node escaped closure")
        if any(not any(start <= edge < end for start, end in CLOSURES) for edge in edges):
            raise ValueError("edge escaped closure")
        decoded[offset] = (opcode, length, edges)
        pending.extend(edge for edge in edges if edge not in decoded)
    nodes = [
        {"file_offset": o, "opcode": f"0x{op:02X}", "length": n,
         "range": [o, o + n], "bytes_sha256": _sha(raw[o:o+n]), "successors": edges}
        for o, (op, n, edges) in sorted(decoded.items())
    ]
    merged: list[list[int]] = []
    for row in nodes:
        a, b = row["range"]
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    counts = Counter(row["opcode"] for row in nodes)
    summary = {"node_count": len(nodes), "directed_edge_count": sum(len(r["successors"]) for r in nodes),
               "terminal_node_count": counts["0x00"], "opcode_counts": dict(sorted(counts.items())),
               "frontier_count": 0, "consumed_bytes": sum(b-a for a,b in merged)}
    return nodes, merged, summary


def _verify(root: Path, artifact: Path) -> dict[str, Any]:
    artifact_fd = _open_directory_no_symlinks(artifact)
    try:
        if set(os.listdir(artifact_fd)) != FILES:
            raise ValueError("artifact file denominator changed")
        artifact_files = {name: _read_regular_at(artifact_fd, name) for name in FILES}
    finally:
        os.close(artifact_fd)
    rom = (root / "rom/base.gba").read_bytes()
    # BASELINE_SHA remains frozen only as a historical reference in the exact
    # payload contract below.  The coverage auditor separately proves
    # current-unknown before accepting these claims.
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA:
        raise ValueError("input identity changed")
    if rom[VECTOR[0]:VECTOR[1]] != VECTOR_RAW or _sha(VECTOR_RAW) != VECTOR_SHA:
        raise ValueError("vector changed")
    if (_ptr(rom, VECTOR[0]), _ptr(rom, VECTOR[0]+4)) != (ROOT45, ROOT46):
        raise ValueError("root vector changed")
    for start, end, expected in (LEFT, RIGHT, *EVIDENCE):
        if _sha(rom[start:end]) != expected:
            raise ValueError("bound evidence changed")
    manifest_raw = artifact_files["manifest.json"]
    payload_raw = artifact_files[PAYLOAD]
    bundle = artifact_files[BUNDLE]
    manifest, payload = json.loads(manifest_raw), json.loads(payload_raw)
    expected_impl = {
        "exporter": {"path": "tools/export_rom_unbound_chapter_script_tail.py", "sha256": _sha((root / "tools/export_rom_unbound_chapter_script_tail.py").read_bytes())},
        "verifier": {"path": "tools/verify_rom_unbound_chapter_script_tail.py", "sha256": _sha((root / "tools/verify_rom_unbound_chapter_script_tail.py").read_bytes())},
    }
    expected_manifest = {
        "schema": "rom-chapter-script-unbound-tail-manifest-v1",
        "artifact_status": "candidate",
        "files": {
            PAYLOAD: {"size": len(payload_raw), "sha256": _sha(payload_raw)},
            BUNDLE: {"size": len(bundle), "sha256": _sha(bundle)},
        },
        "implementation": expected_impl,
        "promotion": {"promotion_bytes": 3186, "claim_count": 3},
    }
    if manifest != expected_manifest:
        raise ValueError("manifest receipt changed")
    nodes, merged, summary = _independent_walk(rom)
    if merged != [list(row) for row in CLOSURES] or summary != {"node_count":128,"directed_edge_count":128,"terminal_node_count":13,"opcode_counts":{"0x00":13,"0x01":47,"0x02":4,"0x04":3,"0x08":47,"0x12":12,"0x32":2},"frontier_count":0,"consumed_bytes":3178}:
        raise ValueError("independent closure changed")
    expected_bundle = b"".join(rom[start:end] for start, end in CLOSURES)
    if bundle != expected_bundle or _sha(bundle) != CLOSURE_SHA:
        raise ValueError("bundle changed")
    expected_claims = [
        {"id":"chapter-unbound-tail-root-vector","range":[*VECTOR],"primary_class":"chapter_script_unbound_root_pointer_vector","bytes_sha256":VECTOR_SHA},
        {"id":"chapter-unbound-tail-slot45-closure","range":[*CLOSURES[0]],"primary_class":"chapter_script_syntax_unbound","bytes_sha256":"8888bf12f58d66e2f8200d98459cadeefbd07f92a808ebc8ec5cc2bb90a620d7"},
        {"id":"chapter-unbound-tail-slot46-closure","range":[*CLOSURES[1]],"primary_class":"chapter_script_syntax_unbound","bytes_sha256":"97d34f067a098b873371892801f5cde232ef4059a7889dd33b1549ddbd3695ba"},
    ]
    node_vector_sha = _sha(json.dumps(nodes, sort_keys=True, separators=(",", ":")).encode())
    expected_payload = {
        "schema": "rom-chapter-script-unbound-tail-v1",
        "rom": {"path": "rom/base.gba", "size": ROM_SIZE, "sha256": ROM_SHA},
        "historical_coverage_reference": {
            "path": "sequel/rom-byte-coverage.json",
            "sha256": BASELINE_SHA,
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
            "file_range": [*VECTOR],
            "bytes": VECTOR_RAW.hex(),
            "sha256": VECTOR_SHA,
            "kind": "fixed_physical_tail_root_vector",
            "consumer_asserted": False,
            "natural_reachability_asserted": False,
            "left_bound_table": {"range": [LEFT[0], LEFT[1]], "sha256": LEFT[2]},
            "right_bound_code": {"range": [RIGHT[0], RIGHT[1]], "sha256": RIGHT[2]},
            "entries": [
                {"slot":45,"target_file_offset":ROOT45,"target_already_classified":False},
                {"slot":46,"target_file_offset":ROOT46,"target_already_classified":False},
            ],
        },
        "grammar": {
            "interpreter_range": [EVIDENCE[0][0], EVIDENCE[0][1]],
            "interpreter_sha256": EVIDENCE[0][2],
            "dispatch_range": [EVIDENCE[1][0], EVIDENCE[1][1]],
            "dispatch_sha256": EVIDENCE[1][2],
            "renderer_range": [EVIDENCE[2][0], EVIDENCE[2][1]],
            "renderer_sha256": EVIDENCE[2][2],
            "sjis_range": [EVIDENCE[3][0], EVIDENCE[3][1]],
            "sjis_sha256": EVIDENCE[3][2],
            "supported_opcodes": ["0x00", "0x01", "0x02", "0x04", "0x08", "0x12", "0x32"],
            "edge_policy": "preserve_order_and_duplicates",
        },
        "nodes": nodes,
        "closure": {
            "roots": [ROOT45, ROOT46],
            "merged_ranges": merged,
            "frontiers": [],
            "bundle_sha256": CLOSURE_SHA,
            "node_vector_sha256": node_vector_sha,
            "summary": summary,
        },
        "promotion": {"promotion_bytes":3186,"claims":expected_claims},
        "limitations": [
            "The two physical tail pointers are not asserted to have a live consumer.",
            "The two root closures prove interpreter syntax only, not natural gameplay reachability or decoded language.",
            "No editing, relocation, padding, or allocatable-space claim is made.",
        ],
    }
    if payload != expected_payload:
        raise ValueError("payload semantic contract changed")
    return {
        "schema": "rom-chapter-script-unbound-tail-verification-v1",
        "verified": True,
        "promotion_bytes": 3186,
        "node_count": 128,
        "frontier_count": 0,
        "artifact_manifest_sha256": _sha(manifest_raw),
        "payload_sha256": _sha(payload_raw),
        "current_unknown_checked": False,
        "coverage_projection_gate_deferred": True,
    }


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    try:
        return _verify(Path(root).resolve(), Path(artifact))
    except Exception as error:
        return {"schema":"rom-chapter-script-unbound-tail-verification-v1","verified":False,"error":str(error)}


def _reject_symlink_components(path: Path) -> None:
    absolute = path.absolute()
    for candidate in (absolute, *absolute.parents):
        if candidate.is_symlink():
            raise ValueError(f"output path contains symlink: {candidate}")


def write_report_atomic(path: Path, report: dict[str, Any]) -> None:
    path = Path(path)
    _reject_symlink_components(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    parent_fd = _open_directory_no_symlinks(path.parent)
    temporary = f".{path.name}.{uuid.uuid4().hex}"
    file_fd = -1
    try:
        try:
            os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError("report output already exists")
        file_fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o644,
            dir_fd=parent_fd,
        )
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
        with os.fdopen(file_fd, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.close(file_fd)
        file_fd = -1
        os.rename(temporary, path.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        temporary = ""
        os.fsync(parent_fd)
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if temporary:
            try:
                os.unlink(temporary, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        os.close(parent_fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    raw = (json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.output:
        write_report_atomic(args.output, report)
    else:
        print(raw, end="")
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
