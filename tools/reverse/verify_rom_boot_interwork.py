#!/usr/bin/env python3
"""Independently verify the fixed boot interwork root and closed ARM CFG."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import capstone

from tools.verify_rom_cfg_inventory import _rebuild_instruction_entries


SCHEMA = "rom-boot-interwork-v1"
VERIFY_SCHEMA = "rom-boot-interwork-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PAYLOAD_NAME = "rom-boot-interwork.json"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME}

ROOT_OFFSET = 0x00024C
CODE_END = 0x0003BC
LITERAL_END = 0x0003E0
CODE_SHA256 = "b7a934aada08004fec2cd403027a1667c91d6cb93edfae149e237dd9c7908bf3"
LITERAL_POOL_SHA256 = "1f206af83e70f2bf5c7e21d4b96b42d639a75b6aa808fb975da4cc94cc41bcb3"
ROOT_REGION_SHA256 = "00fcaba38ae745f4416d9906be0d9fdec3eb1667f9a9b6fca684289287a82995"
ROOT_ENTRY_SHA256 = "8a04c2e346e7375c2cf164f2b0e91ba8c325ffdd38c50e62ec922b266aa6c4dd"

PRODUCER_SPECS = (
    ("thumb_bl", 0x061086, 0x06108A, "589051c73628c96114c0977c1ee91cd7446f42932dfeed31936f351e436d58b7", 0x09C56C),
    ("thumb_bx_pc", 0x09C56C, 0x09C56E, "aa1170db7a37e96c7cd2677a368bc6541819794ef3984f1d91b8b27914201f6e", 0x09C570),
    ("arm_b", 0x09C570, 0x09C574, "979a6ff29e93c31c8a5fd2a1d6502c75b4ae36e8dff16a0b6cabdd4d1a88e33e", ROOT_OFFSET),
)
VENEER_RANGE = (0x09C56C, 0x09C574)
VENEER_SHA256 = "bbf8fd2c580d0ac6a30f6022fb477322a80a12596a521f36877ea2858f6f773b"
SKIPPED_PADDING_RANGE = (0x09C56E, 0x09C570)
SKIPPED_PADDING_SHA256 = "3e39ed78e50103716c788d4147df413950e5eba73c6e33acd923f15865795676"
SIBLING_RANGE = (0x09C574, 0x09C57C)
SIBLING_SHA256 = "9da7a0a5140808bec385f359df25633c88e2af77824236cf5146be8661086e49"

EXPECTED_BLOCKS = (
    (0x24C, 0x294, 18, "123c770a668e6b87544ed2fc9f36fa1041a1d47c0c4f29ba928f8e6a2d3da94e"),
    (0x294, 0x328, 37, "1e524d95806cd937ff1d584da9cd9ed1cf8390972c2ca31f9d5aef66888dfd7e"),
    (0x328, 0x32C, 1, "c402c7ed1b0cac28463ca441dd5574cba9696725ae979ce47d0b71d0dab45da2"),
    (0x32C, 0x340, 5, "2b4f130de6415bf8acb6a2c7a469ca2c601052c2c9cb4712f81811cd3f52b520"),
    (0x340, 0x34C, 3, "1a972be8ec46452326d2110ffba4b7f0060fd000051b1963b9058aba729794e0"),
    (0x34C, 0x35C, 4, "fa989bd3ac9a381c64256ab842a5608c0b7099f5770028f089d0f5eb3946a8ef"),
    (0x35C, 0x3A8, 19, "9f8d955826095ddba631e62378b39e3bf5a5e40f996e637789e08dc7dc0beeaf"),
    (0x3A8, 0x3BC, 5, "ea608c8186d4d96305bb37df4131edb195646868103b578c209328e2da9317a1"),
)
EXPECTED_LITERALS = (
    (0x24C, 0x3BC, "0x03000D18"),
    (0x250, 0x3C0, "0x03000A88"),
    (0x258, 0x3C4, "0x03002E1C"),
    (0x260, 0x3C8, "0x03002E20"),
    (0x278, 0x3CC, "0x03000D18"),
    (0x27C, 0x3D0, "0x03000A84"),
    (0x284, 0x3D4, "0xFFFFFFFF"),
    (0x3A8, 0x3D8, "0x03002E20"),
    (0x3B0, 0x3DC, "0x03002E1C"),
)
EXPECTED_DENOMINATORS = {
    "instruction_vector_sha256": "c25c738607397cb60f90d73d7a6efe079ef52c89c11f787b0cc7d896101beebf",
    "block_vector_sha256": "1c9d08d16c2f4c3b5cdb4123d8ae94b6fd3bb4f7921c9a28a55b77f279c3af50",
    "edge_vector_sha256": "ba298a7c1f9f7811e7dd2ac899c7faa42d013599d9e94a6c41e129b34e7176e7",
    "literal_binding_vector_sha256": "1e812f886d0e0abe614780f0c4a94af1c789831fd966c59e85e0a6ef690f4e9f",
}
EXPECTED_SUMMARY = {
    "root_count": 1,
    "closed_root_count": 1,
    "producer_instruction_count": 3,
    "producer_instruction_bytes": 10,
    "arm_instruction_count": 92,
    "arm_instruction_bytes": 368,
    "basic_block_count": 8,
    "edge_count": 10,
    "frontier_count": 0,
    "literal_binding_count": 9,
    "literal_pool_bytes": 36,
    "coverage_claim_count": 5,
    "classified_bytes": 414,
    "range_overlap_bytes": 0,
}
SCOPE = {
    "fixed_interwork_spine_verified": True,
    "direct_producer_denominator_complete": True,
    "armv4t_instruction_set_enforced": True,
    "arm_root_static_cfg_closed": True,
    "consumed_literal_pool_complete": True,
    "runtime_reachability_complete": False,
    "reset_to_root_path_complete": False,
    "surrounding_40k_region_classified": False,
    "skipped_interwork_padding_classified": False,
    "ram_targets_classified_as_code": False,
    "physical_gba_verified": False,
}
LIMITATIONS = [
    "The fixed BL/BX-pc/ARM-B spine proves the ROM root, but the full reset-to-call runtime path is not established.",
    "Only the independently closed 0x24C..0x3BC ARM worklist and its nine consumed literals are classified.",
    "The skipped 0x9C56E..0x9C570 alignment bytes, sibling veneer, RAM values, and surrounding 0x24C..0x9F2E region remain outside this claim.",
    "Static reachability does not prove natural execution, timing behavior, mGBA replay, or physical-GBA behavior.",
]
DECODER_FILES = {
    "tools/_vendor/capstone/__init__.py": "17a8db1bfe9cb52a97cc89d4ddc9b3246b5d0ddd330fb592ea17060554032f8e",
    "tools/_vendor/capstone/arm.py": "bd8e7a96074481a55c77192f6202f92a52e8c9022aa68c2de5736edf0e04fff0",
    "tools/_vendor/capstone/arm_const.py": "ca87ac6edbf031e1eff66531743dc6f2e4ba8ea63d532da401a5d1fa28653192",
    "tools/_vendor/capstone/lib/libcapstone.dylib": "00f3876991807d87ef26b6564609dd2e2c46616c476336498f33a8c8501fb35f",
}
INDEPENDENT_CFG_ENGINE_PATH = "tools/verify_rom_cfg_inventory.py"
INDEPENDENT_CFG_ENGINE_SHA256 = "a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93"
INSTRUCTION_FIELDS = (
    "mode", "file_offset", "size", "bytes_sha256", "mnemonic", "op_str",
    "conditional", "flow_kind", "successors", "frontiers",
)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _canonical_sha(value: Any) -> str:
    return _digest(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _root_file(root: Path, relative: str | Path) -> Path:
    candidate = root / relative
    if candidate.is_symlink():
        raise ValueError(f"repository input must not be a symlink: {relative}")
    resolved = candidate.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repository input escapes root: {relative}")
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _bounded(data: bytes, start: int, end: int) -> bytes:
    if start < 0 or end < start or end > len(data):
        raise ValueError("independent boot-interwork slice escapes ROM")
    return data[start:end]


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(data, offset, offset + 2), "little")


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(data, offset, offset + 4), "little")


def _thumb_bl_target(data: bytes, offset: int) -> int:
    first = _u16(data, offset)
    second = _u16(data, offset + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError("independent Thumb BL encoding changed")
    encoded = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if encoded & 0x400000:
        encoded -= 0x800000
    return offset + 4 + encoded


def _arm_b_target(data: bytes, offset: int) -> int:
    word = _u32(data, offset)
    if word & 0x0F000000 != 0x0A000000:
        raise ValueError("independent ARM B encoding changed")
    encoded = (word & 0x00FFFFFF) << 2
    if encoded & 0x02000000:
        encoded -= 0x04000000
    return offset + 8 + encoded


def _scan_direct_producers(data: bytes) -> tuple[list[int], list[int]]:
    thumb = []
    for offset in range(0, len(data) - 3, 2):
        first = _u16(data, offset)
        second = _u16(data, offset + 2)
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800 and _thumb_bl_target(data, offset) == 0x09C56C:
            thumb.append(offset)
    arm = []
    for offset in range(0, len(data) - 3, 4):
        word = _u32(data, offset)
        if word >> 28 != 0xF and word & 0x0F000000 == 0x0A000000 and _arm_b_target(data, offset) == ROOT_OFFSET:
            arm.append(offset)
    return thumb, arm


def _producer_chain(rom: bytes) -> dict[str, Any]:
    spine = []
    for kind, start, end, digest, expected_target in PRODUCER_SPECS:
        if _digest(_bounded(rom, start, end)) != digest:
            raise ValueError(f"independent {kind} bytes changed")
        if kind == "thumb_bl":
            target = _thumb_bl_target(rom, start)
        elif kind == "thumb_bx_pc":
            if _u16(rom, start) != 0x4778:
                raise ValueError("independent Thumb BX pc changed")
            target = (start + 4) & ~3
        else:
            target = _arm_b_target(rom, start)
        if target != expected_target:
            raise ValueError(f"independent {kind} target changed")
        spine.append({
            "kind": kind,
            "range": [start, end],
            "gba_range": [_gba(start), _gba(end)],
            "size": end - start,
            "sha256": digest,
            "target": _gba(target),
        })
    thumb, arm = _scan_direct_producers(rom)
    if thumb != [0x061086] or arm != [0x09C570]:
        raise ValueError("independent direct producer denominator changed")
    if _digest(_bounded(rom, *VENEER_RANGE)) != VENEER_SHA256:
        raise ValueError("independent veneer changed")
    if _digest(_bounded(rom, *SKIPPED_PADDING_RANGE)) != SKIPPED_PADDING_SHA256:
        raise ValueError("independent skipped padding changed")
    if _digest(_bounded(rom, *SIBLING_RANGE)) != SIBLING_SHA256 or _u16(rom, SIBLING_RANGE[0]) != 0x4778 or _arm_b_target(rom, 0x09C578) != 0x00026C:
        raise ValueError("independent sibling veneer changed")
    return {
        "interwork_spine": spine,
        "veneer_range": list(VENEER_RANGE),
        "veneer_sha256": VENEER_SHA256,
        "skipped_padding_range": list(SKIPPED_PADDING_RANGE),
        "skipped_padding_sha256": SKIPPED_PADDING_SHA256,
        "excluded_sibling": {"range": list(SIBLING_RANGE), "sha256": SIBLING_SHA256, "target": _gba(0x00026C), "part_of_root": False},
        "unique_thumb_bl_producers": [0x061086],
        "unique_arm_b_producers": [0x09C570],
    }


def _instruction_vector(rom: bytes) -> list[dict[str, Any]]:
    nodes = _rebuild_instruction_entries(rom, [{"mode": "arm", "file_offset": ROOT_OFFSET}])
    expected_keys = [("arm", offset) for offset in range(ROOT_OFFSET, CODE_END, 4)]
    if sorted(nodes, key=lambda item: (item[1], item[0])) != expected_keys:
        raise ValueError("independent ARM worklist denominator changed")
    vector = [{field: nodes[key][field] for field in INSTRUCTION_FIELDS} for key in expected_keys]
    if any(item["frontiers"] for item in vector):
        raise ValueError("independent ARM worklist has a frontier")
    if _canonical_sha(vector) != EXPECTED_DENOMINATORS["instruction_vector_sha256"]:
        raise ValueError("independent instruction vector changed")
    return vector


def _block_and_edge_vectors(rom: bytes, instructions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_offset = {item["file_offset"]: item for item in instructions}
    predecessors = {offset: [] for offset in by_offset}
    for node in instructions:
        for edge in node["successors"]:
            predecessors[edge["file_offset"]].append(node["file_offset"])
    starts = {ROOT_OFFSET}
    for offset, incoming in predecessors.items():
        if offset == ROOT_OFFSET:
            continue
        if len(incoming) != 1:
            starts.add(offset)
            continue
        predecessor = by_offset[incoming[0]]
        if len(predecessor["successors"]) != 1 or predecessor["flow_kind"] != "linear" or predecessor["file_offset"] + predecessor["size"] != offset:
            starts.add(offset)
    if sorted(starts) != [item[0] for item in EXPECTED_BLOCKS]:
        raise ValueError("independent minimal block starts changed")
    block_by_offset = {}
    blocks = []
    for start, expected_end, expected_count, expected_digest in EXPECTED_BLOCKS:
        members = []
        offset = start
        while offset in by_offset and offset not in block_by_offset:
            node = by_offset[offset]
            members.append(node)
            block_by_offset[offset] = f"block-arm-{start:06x}"
            if len(node["successors"]) != 1 or node["flow_kind"] != "linear":
                break
            target = node["successors"][0]["file_offset"]
            if target in starts or target != offset + node["size"]:
                break
            offset = target
        end = members[-1]["file_offset"] + members[-1]["size"]
        if (end, len(members), _digest(_bounded(rom, start, end))) != (expected_end, expected_count, expected_digest):
            raise ValueError("independent block boundary changed")
        last = members[-1]
        blocks.append({
            "id": f"block-arm-{start:06x}",
            "mode": "arm",
            "range": [start, end],
            "instruction_count": len(members),
            "bytes_sha256": expected_digest,
            "terminator": {field: last[field] for field in ("file_offset", "size", "mnemonic", "op_str", "flow_kind", "conditional")},
            "successors": [],
        })
    if len(block_by_offset) != len(instructions):
        raise ValueError("independent block assignment incomplete")
    edges = []
    for block in blocks:
        last = by_offset[block["terminator"]["file_offset"]]
        for edge in last["successors"]:
            successor = {**edge, "block_id": block_by_offset[edge["file_offset"]]}
            block["successors"].append(successor)
            edges.append({"source_block_id": block["id"], **successor})
    if _canonical_sha(blocks) != EXPECTED_DENOMINATORS["block_vector_sha256"] or _canonical_sha(edges) != EXPECTED_DENOMINATORS["edge_vector_sha256"]:
        raise ValueError("independent block or edge vector changed")
    return blocks, edges


def _literal_bindings(rom: bytes) -> list[dict[str, Any]]:
    result = []
    for load_offset, expected_literal, expected_value in EXPECTED_LITERALS:
        word = _u32(rom, load_offset)
        if word & 0x0F7F0000 != 0x051F0000:
            raise ValueError("independent ARM literal encoding changed")
        displacement = word & 0xFFF
        literal = load_offset + 8 + (displacement if word & 0x00800000 else -displacement)
        value = f"0x{_u32(rom, literal):08X}"
        if literal != expected_literal or value != expected_value:
            raise ValueError("independent ARM literal binding changed")
        result.append({"load_offset": load_offset, "literal_offset": literal, "value": value})
    if _canonical_sha(result) != EXPECTED_DENOMINATORS["literal_binding_vector_sha256"]:
        raise ValueError("independent literal vector changed")
    return result


def _decoder_identity(root: Path) -> dict[str, Any]:
    files = {}
    for relative, expected in DECODER_FILES.items():
        digest = _digest(_root_file(root, relative).read_bytes())
        if digest != expected:
            raise ValueError(f"independent decoder dependency changed: {relative}")
        files[relative] = digest
    engine_digest = _digest(_root_file(root, INDEPENDENT_CFG_ENGINE_PATH).read_bytes())
    if engine_digest != INDEPENDENT_CFG_ENGINE_SHA256:
        raise ValueError("independent CFG engine identity changed")
    if capstone.__version__ != "5.0.7" or capstone.cs_version()[:2] != (5, 0):
        raise ValueError("independent Capstone version changed")
    return {
        "architecture": "ARM7TDMI / ARMv4T",
        "backend": "vendored-capstone",
        "version": capstone.__version__,
        "files": files,
        "independent_verifier_engine": {"path": INDEPENDENT_CFG_ENGINE_PATH, "sha256": engine_digest},
    }


def _expected(root: Path, rom: bytes) -> dict[str, Any]:
    if len(rom) != ROM_SIZE or _digest(rom) != ROM_SHA256:
        raise ValueError("base ROM identity mismatch")
    if _digest(_bounded(rom, ROOT_OFFSET, CODE_END)) != CODE_SHA256 or _digest(_bounded(rom, CODE_END, LITERAL_END)) != LITERAL_POOL_SHA256 or _digest(_bounded(rom, ROOT_OFFSET, LITERAL_END)) != ROOT_REGION_SHA256:
        raise ValueError("independent ARM root region changed")
    instructions = _instruction_vector(rom)
    blocks, edges = _block_and_edge_vectors(rom, instructions)
    literals = _literal_bindings(rom)
    claims = []
    for identifier, semantic_class, (start, end) in (
        ("arm-root-code", "arm_code", (ROOT_OFFSET, CODE_END)),
        ("arm-root-literal-pool", "arm_literal_pool", (CODE_END, LITERAL_END)),
        ("thumb-direct-caller", "thumb_code", (0x061086, 0x06108A)),
        ("thumb-bx-pc", "thumb_interwork_code", (0x09C56C, 0x09C56E)),
        ("arm-root-branch", "arm_interwork_code", (0x09C570, 0x09C574)),
    ):
        raw = _bounded(rom, start, end)
        claims.append({"id": identifier, "range": [start, end], "size": len(raw), "semantic_class": semantic_class, "sha256": _digest(raw)})
    implementation = {
        label: {"path": path, "sha256": _digest(_root_file(root, path).read_bytes())}
        for label, path in {
            "exporter": "tools/export_rom_boot_interwork.py",
            "verifier": "tools/verify_rom_boot_interwork.py",
            "test": "tests/test_export_rom_boot_interwork.py",
        }.items()
    }
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "decoder": _decoder_identity(root),
        "producer_chain": _producer_chain(rom),
        "root": {
            "root_id": "root-arm-00024c", "mode": "arm", "file_offset": ROOT_OFFSET,
            "gba_address": _gba(ROOT_OFFSET), "entry_size": 4, "entry_sha256": ROOT_ENTRY_SHA256,
            "traversal_status": "closed", "reachable_instruction_count": 92,
            "reachable_instruction_bytes": 368, "reachable_block_count": 8, "frontier_count": 0,
        },
        "instructions": instructions,
        "blocks": blocks,
        "edges": edges,
        "literal_bindings": literals,
        "denominators": dict(EXPECTED_DENOMINATORS),
        "coverage_claims": claims,
        "summary": dict(EXPECTED_SUMMARY),
        "scope": dict(SCOPE),
        "limitations": list(LIMITATIONS),
        "implementation": implementation,
    }


def _expected_manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": f"{SCHEMA}-artifact-manifest-v1",
        "artifact_schema": SCHEMA,
        "rom": payload["rom"],
        "summary": payload["summary"],
        "files": {name: {"size": len(content), "sha256": _digest(content)} for name, content in sorted(files.items())},
        "producer": payload["implementation"],
        "scope": payload["scope"],
        "verification": {
            "schema": VERIFY_SCHEMA,
            "command": ["python3", "tools/verify_rom_boot_interwork.py", "--root", ".", "--artifact-dir", f"artifacts/{SCHEMA}"],
            "verifier_sha256": payload["implementation"]["verifier"]["sha256"],
        },
    }


def _artifact_directory(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("artifact path uses a symlink")
        if not cursor.exists():
            break
    resolved = requested.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("artifact path is not a directory")
    return resolved


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    report: dict[str, Any] = {"schema": VERIFY_SCHEMA, "verified": False, "errors": []}
    try:
        root = Path(root).resolve(strict=True)
        if root != PROJECT_ROOT.resolve(strict=True):
            raise ValueError(
                "requested root differs from the loaded project root"
            )
        rom = _root_file(root, ROM_PATH).read_bytes()
        artifact = _artifact_directory(Path(artifact_dir))
        members = list(artifact.rglob("*"))
        names = {member.relative_to(artifact).as_posix() for member in members if member.is_file()}
        if names != EXPECTED_FILES or any(member.is_symlink() for member in members):
            raise ValueError("artifact file set differs")
        manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
        payload_bytes = (artifact / PAYLOAD_NAME).read_bytes()
        payload = json.loads(payload_bytes)
        expected = _expected(root, rom)
        expected_bytes = _canonical(expected)
        expected_files = {PAYLOAD_NAME: expected_bytes}
        if payload != expected:
            raise ValueError("artifact payload differs from independent reconstruction")
        if payload_bytes != expected_bytes:
            raise ValueError("artifact payload is not canonical JSON")
        if manifest != _expected_manifest(expected, expected_files):
            raise ValueError("artifact manifest differs from independent reconstruction")
        report.update({
            "verified": True,
            "artifact_schema": SCHEMA,
            "summary": expected["summary"],
            "instruction_vector_sha256": EXPECTED_DENOMINATORS["instruction_vector_sha256"],
            "block_vector_sha256": EXPECTED_DENOMINATORS["block_vector_sha256"],
            "edge_vector_sha256": EXPECTED_DENOMINATORS["edge_vector_sha256"],
            "literal_binding_vector_sha256": EXPECTED_DENOMINATORS["literal_binding_vector_sha256"],
        })
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        report["errors"].append(str(error))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, default=Path(f"artifacts/{SCHEMA}"))
    args = parser.parse_args()
    artifact = args.artifact_dir if args.artifact_dir.is_absolute() else args.root / args.artifact_dir
    report = verify_artifact(args.root, artifact)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
