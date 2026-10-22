#!/usr/bin/env python3
"""Export the frozen two-root raw-ROM CFG proven-roots v14 packet."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"


def _require_isolated_cli_runtime() -> None:
    if __name__ != "__main__":
        return
    if not sys.flags.isolated or not sys.flags.no_site:
        raise RuntimeError("CFG v14 CLI requires Python -I -S isolation")
    if "capstone" in sys.modules:
        raise RuntimeError("CFG v14 CLI rejects preloaded Capstone modules")
    if os.environ.get("LIBCAPSTONE_PATH"):
        raise RuntimeError("CFG v14 CLI rejects LIBCAPSTONE_PATH overrides")


_require_isolated_cli_runtime()
for _root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from tools import export_rom_cfg_proven_roots_v13 as _base  # noqa: E402
from tools.rom_cfg_proven_roots_v14_contract import (  # noqa: E402
    COVERAGE_EXPECTED,
    COVERAGE_PATH,
    EXPERIMENT_OUTPUT_ROOT,
    MANIFEST_NAME,
    NONCLAIMS,
    OFFICIAL_ARTIFACT,
    PAYLOAD_NAME,
    PROMOTION_PACKED_SHA256,
    PROMOTION_RANGE_SHA256,
    PROMOTION_RANGES,
    PROMOTION_SCHEMA,
    ROM_BASE,
    ROM_PATH,
    ROM_SHA256,
    ROM_SIZE,
    SCHEMA,
    SCOPE,
    TARGET_SPECS,
    UPSTREAM,
    VERIFY_SCHEMA,
)


_canonical_json = _base._canonical_json
_canonical_sha = _base._canonical_sha
_reject_symlink_components = _base._reject_symlink_components
_safe_file = _base._safe_file
_sha = _base._sha

RUNTIME_DEPENDENCY_PATHS = tuple(
    sorted(
        {
            Path("tools/rom_cfg_proven_roots_v14_contract.py"),
            Path("tools/export_rom_cfg_proven_roots_v13.py"),
            Path("tools/verify_rom_cfg_proven_roots_v13.py"),
            *_base.RUNTIME_DEPENDENCY_PATHS,
        },
        key=lambda path: path.as_posix(),
    )
)

EXPECTED_REPORT = {
    "schema": VERIFY_SCHEMA,
    "verified": True,
    "errors": [],
    "control_flow_oracle": "armv4t-raw-encoding",
    "rom_sha256": ROM_SHA256,
    "target_root_count": 2,
    "producer_count": 5,
    "target_decoded_instruction_count": 60,
    "target_decoded_basic_block_count": 10,
    "target_reachable_instruction_bytes": 120,
    "target_frontier_count": 2,
    "target_frontiers": [
        [402_686, "indirect_pc_target"],
        [402_758, "indirect_pc_target"],
    ],
    "target_instruction_internal_edge_count": 64,
    "target_block_internal_edge_count": 14,
    "target_external_call_edge_count": 0,
    "target_literal_reference_count": 10,
    "target_unique_literal_word_count": 10,
    "target_literal_bytes": 40,
    "promotion_range_count": 4,
    "promotion_bytes": 160,
    "promotion_code_bytes": 120,
    "promotion_literal_bytes": 40,
    "hole_bytes": 0,
    "nonclaims": {name: False for name in NONCLAIMS},
}


def _require_rom(rom: bytes) -> None:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")


def _producer_target(callsite: int, first: int, second: int) -> int | None:
    return _base._producer_target(callsite, first, second)


def _producer_denominator(rom: bytes, target_root: int) -> dict[str, Any]:
    _require_rom(rom)
    matches = [spec for spec in TARGET_SPECS if spec["root"] == target_root]
    if len(matches) != 1:
        raise ValueError("target root is outside the frozen v14 denominator")
    spec = matches[0]
    thumb_bl: list[int] = []
    thumb_b: list[int] = []
    thumb_bcond: list[int] = []
    for offset in range(0, len(rom) - 3, 2):
        first = int.from_bytes(rom[offset : offset + 2], "little")
        second = int.from_bytes(rom[offset + 2 : offset + 4], "little")
        if _producer_target(offset, first, second) == target_root:
            thumb_bl.append(offset)
        elif first & 0xF800 == 0xE000:
            displacement = (first & 0x7FF) << 1
            if displacement & 0x800:
                displacement -= 0x1000
            if offset + 4 + displacement == target_root:
                thumb_b.append(offset)
        elif first & 0xF000 == 0xD000 and ((first >> 8) & 0xF) <= 0xD:
            displacement = (first & 0xFF) << 1
            if displacement & 0x100:
                displacement -= 0x200
            if offset + 4 + displacement == target_root:
                thumb_bcond.append(offset)
    arm_b_bl: list[int] = []
    aligned_arm_pointers: list[int] = []
    for offset in range(0, len(rom) - 3, 4):
        word = int.from_bytes(rom[offset : offset + 4], "little")
        if word == ROM_BASE + target_root:
            aligned_arm_pointers.append(offset)
        if word >> 28 != 0xF and (word >> 25) & 0x7 == 0b101:
            displacement = (word & 0xFFFFFF) << 2
            if displacement & 0x02000000:
                displacement -= 0x04000000
            if offset + 8 + displacement == target_root:
                arm_b_bl.append(offset)
    thumb_pointers: list[int] = []
    pointer = (ROM_BASE + target_root) | 1
    for offset in range(0, len(rom) - 3, 2):
        if int.from_bytes(rom[offset : offset + 4], "little") == pointer:
            thumb_pointers.append(offset)
    vector = [[offset, target_root, "thumb_bl"] for offset in thumb_bl]
    actual = {
        "aligned_arm_pointers": aligned_arm_pointers,
        "arm_b_bl": arm_b_bl,
        "thumb_b": thumb_b,
        "thumb_bcond": thumb_bcond,
        "thumb_bl": thumb_bl,
        "thumb_pointers": thumb_pointers,
        "vector": vector,
        "vector_sha256": _canonical_sha(vector),
    }
    if actual != spec["producer_denominator"]:
        raise ValueError("target-limited producer denominator changed")
    for producer in spec["producers"]:
        raw = rom[producer["file_offset"] : producer["file_offset"] + 4]
        if raw.hex() != producer["raw_hex"] or _sha(raw) != producer["bytes_sha256"]:
            raise ValueError("producer bytes changed")
    return copy.deepcopy(actual)


def _literal_projection(
    rom: bytes,
    nodes: dict[tuple[str, int], dict[str, Any]],
    spec: dict[str, Any],
) -> dict[str, Any]:
    binding_vector: list[list[int]] = []
    bindings: list[list[Any]] = []
    for node in _base._nodes(nodes):
        offset = node["file_offset"]
        if node["mnemonic"] != "ldr" or "[pc," not in node["op_str"]:
            continue
        raw = rom[offset : offset + 2]
        halfword = int.from_bytes(raw, "little")
        if halfword & 0xF800 != 0x4800:
            continue
        literal = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
        if not any(
            start <= literal and literal + 4 <= end
            for start, end in spec["literal_ranges"]
        ):
            continue
        literal_raw = rom[literal : literal + 4]
        binding_vector.append([offset, literal])
        bindings.append(
            [
                offset,
                literal,
                int.from_bytes(literal_raw, "little"),
                raw.hex(),
                literal_raw.hex(),
            ]
        )
    if (
        binding_vector != spec["literal_binding_vector"]
        or _canonical_sha(binding_vector) != spec["literal_binding_vector_sha256"]
        or len(bindings) != spec["literal_reference_count"]
        or len({row[1] for row in bindings}) != spec["unique_literal_word_count"]
        or _base._packed(rom, spec["literal_ranges"])
        != spec["packed_literals_sha256"]
    ):
        raise ValueError("target literal projection changed")
    return {
        "bindings": bindings,
        "binding_vector": binding_vector,
        "binding_vector_sha256": spec["literal_binding_vector_sha256"],
        "literal_reference_count": len(bindings),
        "unique_literal_word_count": len({row[1] for row in bindings}),
        "bytes": spec["literal_bytes"],
        "ranges": copy.deepcopy(spec["literal_ranges"]),
        "range_vector_sha256": spec["literal_range_vector_sha256"],
        "packed_sha256": spec["packed_literals_sha256"],
    }


def _target_worklist(rom: bytes, target_index: int) -> dict[str, Any]:
    _require_rom(rom)
    try:
        spec = TARGET_SPECS[target_index]
    except IndexError as error:
        raise ValueError("target index is outside the frozen v14 denominator") from error
    start, end = spec["envelope"]
    if _sha(rom[start:end]) != spec["envelope_sha256"]:
        raise ValueError("target envelope changed")
    nodes, blocks, external, boundary = _base._bounded_worklist(
        rom, spec["root"], (start, end), None
    )
    if (
        len(nodes) != spec["decoded_instruction_count"]
        or len(blocks) != spec["decoded_basic_block_count"]
        or boundary != spec["boundary_edges"]
    ):
        raise ValueError("target CFG denominator changed")
    code_ranges = _base._merged_ranges(nodes)
    block_ranges = [block["range"] for block in blocks]
    instruction_internal = [
        [node["file_offset"], edge["file_offset"], edge["kind"]]
        for node in _base._nodes(nodes)
        for edge in node["successors"]
        if (edge["mode"], edge["file_offset"]) in nodes
    ]
    instruction_internal.sort(
        key=lambda row: (row[0], 0 if row[2] == "branch_target" else 1, row[1])
    )
    block_internal = [
        [block["terminator"]["file_offset"], edge["file_offset"], edge["kind"]]
        for block in blocks
        for edge in block["successors"]
    ]
    block_internal.sort(
        key=lambda row: (row[0], 0 if row[2] == "branch_target" else 1, row[1])
    )
    external_vector = [
        [row["source_file_offset"], row["target_file_offset"], row["edge_kind"]]
        for row in sorted(external, key=lambda row: row["source_file_offset"])
    ]
    frontiers = _base._frontier_vector(nodes)
    semantic = _base._semantic_vector(nodes)
    literals = _literal_projection(rom, nodes, spec)
    checks = {
        "code ranges": code_ranges == spec["code_ranges"],
        "block ranges": block_ranges == spec["block_ranges"],
        "frontiers": frontiers == spec["frontiers"],
        "external edges": external_vector == spec["external_edges"],
        "code hash": _canonical_sha(code_ranges)
        == spec["code_range_vector_sha256"],
        "block hash": _canonical_sha(block_ranges)
        == spec["block_range_vector_sha256"],
        "semantic hash": _canonical_sha(semantic)
        == spec["semantic_instruction_vector_sha256"],
        "instruction edge count": len(instruction_internal)
        == spec["instruction_internal_edge_count"],
        "instruction edge hash": _canonical_sha(instruction_internal)
        == spec["instruction_internal_edge_vector_sha256"],
        "block edge count": len(block_internal)
        == spec["block_internal_edge_count"],
        "block edge hash": _canonical_sha(block_internal)
        == spec["block_internal_edge_vector_sha256"],
        "external hash": _canonical_sha(external_vector)
        == spec["external_edge_vector_sha256"],
        "frontier hash": _canonical_sha(frontiers)
        == spec["frontier_vector_sha256"],
        "code bytes": _base._packed(rom, code_ranges)
        == spec["packed_code_sha256"],
        "promotion bytes": _base._packed(rom, spec["promotion_ranges"])
        == spec["packed_promotion_sha256"],
        "promotion ranges": _canonical_sha(spec["promotion_ranges"])
        == spec["promotion_range_vector_sha256"],
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError("target CFG vector changed: " + ", ".join(failed))
    frontier_offset = spec["frontiers"][0][0]
    frontier = nodes.get(("thumb", frontier_offset))
    if (
        frontier is None
        or frontier["mnemonic"] != "bx"
        or frontier["op_str"] != "r0"
        or frontier["flow_kind"] != "indirect_branch"
        or frontier["successors"]
    ):
        raise ValueError("target indirect-PC frontier changed")
    return {
        "name": spec["name"],
        "root": _base._entry(
            rom, spec["root"], spec["root_raw_hex"], spec["root_sha256"]
        ),
        "envelope": copy.deepcopy(spec["envelope"]),
        "envelope_bytes": spec["envelope_bytes"],
        "envelope_sha256": spec["envelope_sha256"],
        "nodes": _base._nodes(nodes),
        "blocks": blocks,
        "block_ranges": block_ranges,
        "code_ranges": code_ranges,
        "literal_ranges": copy.deepcopy(spec["literal_ranges"]),
        "promotion_ranges": copy.deepcopy(spec["promotion_ranges"]),
        "holes": [],
        "frontiers": frontiers,
        "instruction_internal_edges": instruction_internal,
        "block_internal_edges": block_internal,
        "external_edges": external,
        "boundary_edges": boundary,
        "literal_projection": literals,
        "block_range_vector_sha256": spec["block_range_vector_sha256"],
        "code_range_vector_sha256": spec["code_range_vector_sha256"],
        "literal_range_vector_sha256": spec["literal_range_vector_sha256"],
        "promotion_range_vector_sha256": spec[
            "promotion_range_vector_sha256"
        ],
        "instruction_internal_edge_vector_sha256": spec[
            "instruction_internal_edge_vector_sha256"
        ],
        "block_internal_edge_vector_sha256": spec[
            "block_internal_edge_vector_sha256"
        ],
        "external_edge_vector_sha256": spec["external_edge_vector_sha256"],
        "frontier_vector_sha256": spec["frontier_vector_sha256"],
        "semantic_instruction_vector_sha256": spec[
            "semantic_instruction_vector_sha256"
        ],
        "literal_binding_vector_sha256": spec[
            "literal_binding_vector_sha256"
        ],
        "packed_code_sha256": spec["packed_code_sha256"],
        "packed_literals_sha256": spec["packed_literals_sha256"],
        "packed_promotion_sha256": spec["packed_promotion_sha256"],
        "summary": {
            "decoded_instruction_count": len(nodes),
            "decoded_basic_block_count": len(blocks),
            "reachable_instruction_bytes": spec["reachable_instruction_bytes"],
            "frontier_count": len(frontiers),
            "instruction_internal_edge_count": len(instruction_internal),
            "block_internal_edge_count": len(block_internal),
            "external_call_edge_count": len(external),
            "literal_reference_count": literals["literal_reference_count"],
            "unique_literal_word_count": literals["unique_literal_word_count"],
            "literal_bytes": literals["bytes"],
            "promotion_range_count": len(spec["promotion_ranges"]),
            "promotion_bytes": spec["promotion_bytes"],
            "hole_bytes": 0,
        },
    }


def _load_upstream_payloads(root: Path) -> dict[int, dict[str, Any]]:
    payloads: dict[int, dict[str, Any]] = {}
    for label, identity in UPSTREAM.items():
        version = int(label.removeprefix("v"))
        manifest_path = _safe_file(root, identity["manifest_path"])
        payload_path = _safe_file(root, identity["payload_path"])
        manifest_raw = manifest_path.read_bytes()
        payload_raw = payload_path.read_bytes()
        if (
            _sha(manifest_raw) != identity["manifest_sha256"]
            or _sha(payload_raw) != identity["payload_sha256"]
        ):
            raise ValueError(f"accepted upstream {label} identity changed")
        manifest = json.loads(manifest_raw)
        payload = json.loads(payload_raw)
        expected_schema = f"rom-cfg-proven-roots-v{version}"
        if (
            manifest.get("artifact_status") != "accepted"
            or manifest.get("artifact_schema") != expected_schema
            or payload.get("schema") != expected_schema
            or manifest.get("files", {})
            .get(Path(identity["payload_path"]).name, {})
            .get("sha256")
            != identity["payload_sha256"]
        ):
            raise ValueError(f"accepted upstream {label} contract changed")
        payloads[version] = payload
    return payloads


def _upstream_contract(root: Path) -> dict[str, Any]:
    _load_upstream_payloads(root)
    return copy.deepcopy(UPSTREAM)


def _coverage_data(root: Path) -> dict[str, Any]:
    path = _safe_file(root, COVERAGE_PATH)
    raw = path.read_bytes()
    if _sha(raw) != COVERAGE_EXPECTED["sha256"]:
        raise ValueError("coverage baseline identity changed")
    value = json.loads(raw)
    summary = value.get("summary", {})
    for key in ("classified_bytes", "unknown_bytes", "claim_count", "segment_count"):
        if summary.get(key) != COVERAGE_EXPECTED[key]:
            raise ValueError("coverage baseline summary changed")
    return value


def _coverage_baseline(root: Path) -> dict[str, Any]:
    coverage = _coverage_data(root)
    known_bytes = 0
    unknown_bytes = 0
    for start, end in PROMOTION_RANGES:
        for segment in coverage.get("segments", []):
            left, right = segment["range"]
            overlap_start = max(start, left)
            overlap_end = min(end, right)
            if overlap_start >= overlap_end:
                continue
            if segment["primary_class"] == "unknown":
                unknown_bytes += overlap_end - overlap_start
            else:
                known_bytes += overlap_end - overlap_start
    if known_bytes != 0 or unknown_bytes != 160:
        raise ValueError("coverage baseline promotion projection changed")
    return copy.deepcopy(COVERAGE_EXPECTED)


def _producer_membership(
    root: Path,
    rom: bytes,
    target_index: int,
    payloads: dict[int, dict[str, Any]],
    coverage: dict[str, Any],
) -> list[dict[str, Any]]:
    spec = TARGET_SPECS[target_index]
    claims = {row.get("id"): row for row in coverage.get("claims", [])}
    result: list[dict[str, Any]] = []
    for frozen in spec["producers"]:
        version = frozen["upstream_version"]
        upstream = payloads[version]
        nodes = [
            row
            for row in upstream.get("target", {}).get("nodes", [])
            if row.get("file_offset") == frozen["file_offset"]
        ]
        if len(nodes) != 1:
            raise ValueError("accepted upstream producer node denominator changed")
        node = nodes[0]
        call_targets = [
            edge
            for edge in node.get("successors", [])
            if edge.get("kind") == "call_target"
        ]
        raw = rom[frozen["file_offset"] : frozen["file_offset"] + 4]
        if (
            node.get("accepted") is not True
            or node.get("mode") != "thumb"
            or node.get("mnemonic") != "bl"
            or node.get("flow_kind") != "call"
            or node.get("bytes_sha256") != frozen["bytes_sha256"]
            or call_targets
            != [
                {
                    "file_offset": spec["root"],
                    "kind": "call_target",
                    "mode": "thumb",
                }
            ]
            or raw.hex() != frozen["raw_hex"]
            or _sha(raw) != frozen["bytes_sha256"]
        ):
            raise ValueError("accepted upstream producer membership changed")
        claim = claims.get(frozen["coverage_owner_claim_id"])
        identity = UPSTREAM[f"v{version}"]
        if (
            not isinstance(claim, dict)
            or claim.get("range") != frozen["coverage_owner_range"]
            or claim.get("primary_class") != identity["claim_class"]
            or claim.get("evidence_sha256") != identity["payload_sha256"]
            or claim.get("promotion_manifest_sha256")
            != identity["manifest_sha256"]
        ):
            raise ValueError("producer coverage owner changed")
        result.append({**copy.deepcopy(frozen), "artifact_node": copy.deepcopy(node)})
    return result


def _implementation(root: Path) -> dict[str, Any]:
    paths = {
        "exporter": Path("tools/export_rom_cfg_proven_roots_v14.py"),
        "verifier": Path("tools/verify_rom_cfg_proven_roots_v14.py"),
        "test_exporter": Path("tests/test_export_rom_cfg_proven_roots_v14.py"),
        "test_verifier": Path("tests/test_verify_rom_cfg_proven_roots_v14.py"),
    }
    return {
        "binding": "passed-root-runtime-dependency-and-test-hash-bound",
        "paths": {name: path.as_posix() for name, path in paths.items()},
        "exporter_sha256": _sha(_safe_file(root, paths["exporter"]).read_bytes()),
        "verifier_sha256": _sha(_safe_file(root, paths["verifier"]).read_bytes()),
        "test_exporter_sha256": _sha(
            _safe_file(root, paths["test_exporter"]).read_bytes()
        ),
        "test_verifier_sha256": _sha(
            _safe_file(root, paths["test_verifier"]).read_bytes()
        ),
        "runtime_dependency_sha256": {
            path.as_posix(): _sha(_safe_file(root, path).read_bytes())
            for path in RUNTIME_DEPENDENCY_PATHS
        },
    }


def build_cfg_proven_roots_v14_payload(
    root: Path, rom: bytes | None = None
) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    if rom is None:
        rom = _safe_file(root, ROM_PATH).read_bytes()
    _require_rom(rom)
    payloads = _load_upstream_payloads(root)
    coverage = _coverage_data(root)
    targets = []
    for index, spec in enumerate(TARGET_SPECS):
        target = _target_worklist(rom, index)
        target["producer_denominator"] = _producer_denominator(rom, spec["root"])
        target["producers"] = _producer_membership(
            root, rom, index, payloads, coverage
        )
        targets.append(target)
    if _base._packed(rom, PROMOTION_RANGES) != PROMOTION_PACKED_SHA256:
        raise ValueError("v14 packed promotion bytes changed")
    if _canonical_sha(PROMOTION_RANGES) != PROMOTION_RANGE_SHA256:
        raise ValueError("v14 promotion range vector changed")
    return {
        "schema": SCHEMA,
        "rom": {
            "path": ROM_PATH.as_posix(),
            "size": ROM_SIZE,
            "sha256": ROM_SHA256,
        },
        "upstream": copy.deepcopy(UPSTREAM),
        "targets": targets,
        "promotion": {
            "batch": "cfg-proven-roots-v14",
            "ranges": copy.deepcopy(PROMOTION_RANGES),
            "promotion_range_count": 4,
            "promotion_bytes": 160,
            "promotion_code_bytes": 120,
            "promotion_literal_bytes": 40,
            "hole_bytes": 0,
            "packed_sha256": PROMOTION_PACKED_SHA256,
            "range_vector_sha256": PROMOTION_RANGE_SHA256,
            "unclassified_hole_bytes": 0,
        },
        "coverage_baseline": _coverage_baseline(root),
        "implementation": _implementation(root),
        "scope": copy.deepcopy(SCOPE),
    }


def _receipt_commands(root: Path, output: Path) -> tuple[list[str], list[str]]:
    relative = output.resolve(strict=False).relative_to(root.resolve()).as_posix()
    return (
        [
            "python3",
            "-I",
            "-S",
            "tools/export_rom_cfg_proven_roots_v14.py",
            "--root",
            ".",
            "--output-dir",
            relative,
        ],
        [
            "python3",
            "-I",
            "-S",
            "tools/verify_rom_cfg_proven_roots_v14.py",
            "--root",
            ".",
            "--artifact-dir",
            relative,
        ],
    )


def _manifest(
    root: Path,
    output: Path,
    payload: dict[str, Any],
    payload_raw: bytes,
    status: str,
    report: dict[str, Any] | None,
) -> dict[str, Any]:
    if status not in {"candidate", "accepted"} or (
        (status == "accepted") != (report is not None)
    ):
        raise ValueError("invalid v14 manifest status or receipt")
    producer_command, verifier_command = _receipt_commands(root, output)
    implementation = payload["implementation"]
    return {
        "schema": PROMOTION_SCHEMA,
        "artifact_schema": SCHEMA,
        "artifact_status": status,
        "rom": payload["rom"],
        "upstream": payload["upstream"],
        "targets": payload["targets"],
        "promotion": payload["promotion"],
        "coverage_baseline": payload["coverage_baseline"],
        "files": {
            PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}
        },
        "producer": {"command": producer_command, "implementation": implementation},
        "verifier": {
            "schema": VERIFY_SCHEMA,
            "command": verifier_command,
            "exit_code": 0 if report is not None else None,
            "report": report,
            "verifier_sha256": implementation["verifier_sha256"],
        },
        "implementation": implementation,
        "scope": payload["scope"],
    }


def _run_isolated_verifier(root: Path, command: list[str]) -> dict[str, Any]:
    environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "LIBCAPSTONE_PATH"):
        environment.pop(name, None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        command,
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise ValueError(
            completed.stderr.strip()
            or completed.stdout.strip()
            or "independent v14 verifier failed"
        )
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("independent v14 verifier returned invalid JSON") from error
    if report != EXPECTED_REPORT:
        raise ValueError(f"independent v14 verifier report changed: {report}")
    return report


def _validate_output_dir(root: Path, output_dir: Path) -> Path:
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested)
    target = requested.resolve(strict=False)
    experiment = (root / EXPERIMENT_OUTPUT_ROOT).resolve(strict=False)
    official = (root / OFFICIAL_ARTIFACT).resolve(strict=False)
    if target != official:
        try:
            target.relative_to(experiment)
        except ValueError as error:
            raise ValueError(
                "CFG v14 output must stay inside experiment subtree or official artifact"
            ) from error
        if target == experiment:
            raise ValueError("CFG v14 output cannot be the experiment root")
    if target.exists():
        if not target.is_dir():
            raise ValueError("CFG v14 output is not a directory")
        members = list(target.iterdir())
        if members and (
            {path.name for path in members} != {MANIFEST_NAME, PAYLOAD_NAME}
            or any(path.is_symlink() or not path.is_file() for path in members)
        ):
            raise ValueError("CFG v14 output is a foreign non-empty directory")
    return target


def _write_manifest_atomic(output: Path, manifest: dict[str, Any]) -> None:
    temporary = output / f".{MANIFEST_NAME}.{uuid.uuid4().hex}.tmp"
    try:
        temporary.write_bytes(_canonical_json(manifest))
        os.replace(temporary, output / MANIFEST_NAME)
    finally:
        temporary.unlink(missing_ok=True)


def export_rom_cfg_proven_roots_v14(
    root: Path, output_dir: Path
) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output = _validate_output_dir(root, output_dir)
    payload = build_cfg_proven_roots_v14_payload(root)
    payload_raw = _canonical_json(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".rom-cfg-proven-roots-v14-", dir=output.parent)
    )
    backup: Path | None = None
    committed = False
    try:
        candidate = _manifest(root, output, payload, payload_raw, "candidate", None)
        (temporary / PAYLOAD_NAME).write_bytes(payload_raw)
        (temporary / MANIFEST_NAME).write_bytes(_canonical_json(candidate))
        if output.exists():
            backup = output.with_name(f".{output.name}.backup-{uuid.uuid4().hex}")
            os.replace(output, backup)
        os.replace(temporary, output)
        report = _run_isolated_verifier(root, candidate["verifier"]["command"])
        accepted = _manifest(root, output, payload, payload_raw, "accepted", report)
        _write_manifest_atomic(output, accepted)
        if _run_isolated_verifier(root, accepted["verifier"]["command"]) != report:
            raise ValueError("accepted v14 postflight report changed")
        committed = True
        if backup is not None and backup.exists():
            shutil.rmtree(backup)
            backup = None
        return accepted
    except BaseException:
        if not committed:
            failed = None
            if output.exists():
                failed = output.with_name(f".{output.name}.failed-{uuid.uuid4().hex}")
                os.replace(output, failed)
            if backup is not None and backup.exists():
                os.replace(backup, output)
                backup = None
            if failed is not None and failed.exists():
                shutil.rmtree(failed)
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists() and not output.exists():
            os.replace(backup, output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = export_rom_cfg_proven_roots_v14(args.root, args.output_dir)
    print(json.dumps(manifest["promotion"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
