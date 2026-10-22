#!/usr/bin/env python3
"""Independently verify the frozen boot ROM copy-source packet."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.thumb_branch import decode_thumb_b, decode_thumb_bl
from tools.verify_rom_boot_thumb_handoff_cfg import verify_artifact as verify_boot


SCHEMA = "rom-boot-copy-sources-v1"
VERIFY_SCHEMA = "rom-boot-copy-sources-verification-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PAYLOAD_NAME = "rom-boot-copy-sources.json"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME}
CANDIDATE_RANGE = [0x4C8, 0x734]
CANDIDATE_SHA256 = "0be5228ec171480a4097db134e32c030972f43fbf637a425f3f4826450944e80"
LOCAL_CODE_RANGE = [0x61624, 0x61710]
LOCAL_CODE_SHA256 = "e3ba1dadf23b428fd2a39b6d9aef48b7ba9521d825ca196b37d7a93403192dff"
LOCAL_LITERAL_RANGE = [0x61710, 0x6178C]
LOCAL_LITERAL_SHA256 = "e1bdf99fdcdfa92e4bc900e57730c3ee8d1cea55f1eaeed7ec1a56768b561031"
BOOT_DIR = Path("artifacts/rom-boot-thumb-handoff-cfg-v1")
V12_DIR = Path("artifacts/rom-cfg-proven-roots-v12")
IDENTITIES = {
    BOOT_DIR / "manifest.json": "d5af12930ed8e7539396f81deda19ae938eee3f029b95c959f6fa5d57c676d74",
    BOOT_DIR / "rom-boot-thumb-handoff-cfg.json": "a35b581e44b276399874a2fc393f22f3c548c6b99e053f504587bdd92fbad295",
    Path("tools/verify_rom_boot_thumb_handoff_cfg.py"): "2592e4f48f1a197e30cb4d360201228fc2bbeef5fad12879b1bbf77b29815b39",
    V12_DIR / "manifest.json": "bf88e08f4eed6b53e1debef709c2ef13fb891c11e9c172485e494eef57954677",
    V12_DIR / "rom-cfg-proven-roots-v12.json": "fd9df8f3d93de1df5aa7e725040f27f854d08e8203d6cada51db829ddcd9bcee",
    Path("tools/verify_rom_cfg_proven_roots_v12.py"): "1043291dfb16b90ef025242b976a4bf89a6a0173a0ac4904fc3534d625acbede",
    Path("tools/verify_rom_cfg_proven_roots_v12_bundle.py"): "ee1d50f3018b5d78d652eb5ed6d1f7108670669b60e5518b9956df987b60275a",
}
EXPECTED_RANGES = [[0x4C8, 0x6C8], [0x520, 0x5C4], [0x5AC, 0x60C], [0x638, 0x694], [0x690, 0x734]]
EXPECTED_DESCRIPTORS = [
    {"index": 0, "source": "0x08000104", "destination": "0x0300007C", "control": "0x84000080", "copy_bytes": 512, "candidate_hit": False},
    {"index": 1, "source": "0x0853D5B4", "destination": "0x03000014", "control": "0x8400000E", "copy_bytes": 56, "candidate_hit": False},
    {"index": 2, "source": "0x080004C8", "destination": "0x03000680", "control": "0x84000080", "copy_bytes": 512, "candidate_hit": True},
    {"index": 3, "source": "0x08000520", "destination": "0x0300088C", "control": "0x84000029", "copy_bytes": 164, "candidate_hit": True},
    {"index": 4, "source": "0x080005AC", "destination": "0x03000930", "control": "0x84000018", "copy_bytes": 96, "candidate_hit": True},
    {"index": 5, "source": "sp_zero_halfword", "destination": "0x06000000", "control": "0x8100C000", "copy_bytes": 98304, "candidate_hit": False},
    {"index": 6, "source": "sp_0x7fff_halfword", "destination": "0x05000000", "control": "0x81000002", "copy_bytes": 4, "candidate_hit": False},
    {"index": 7, "source": "sp_zero_word", "destination": "0x0300027C", "control": "0x85000100", "copy_bytes": 1024, "candidate_hit": False},
    {"index": 8, "source": "0x0300027C", "destination": "0x07000000", "control": "0x84000100", "copy_bytes": 1024, "candidate_hit": False},
]
EXPECTED_OPERATIONS = [
    {"id": "dma-2", "consumer": "DMA3", "callsite": 0x6164A, "source_range": [0x4C8, 0x6C8], "destination": "0x03000680", "control": "0x84000080", "copy_bytes": 512},
    {"id": "dma-3", "consumer": "DMA3", "callsite": 0x61656, "source_range": [0x520, 0x5C4], "destination": "0x0300088C", "control": "0x84000029", "copy_bytes": 164},
    {"id": "dma-4", "consumer": "DMA3", "callsite": 0x61664, "source_range": [0x5AC, 0x60C], "destination": "0x03000930", "control": "0x84000018", "copy_bytes": 96},
    {"id": "cpuset-v12", "consumer": "CpuSet", "callsite": 0x6459E, "source_range": [0x638, 0x694], "destination": "0x03005CE8", "control": "0x04000017", "copy_bytes": 92},
    {"id": "cpuset-boot", "consumer": "CpuSet", "callsite": 0x646DE, "source_range": [0x690, 0x734], "destination": "0x03005D50", "control": "0x04000029", "copy_bytes": 164},
]
EXPECTED_SCOPE = {"fixed_rom_copy_source_bytes": True, "arm_code_semantics": False,
    "natural_runtime_reachability": False, "business_semantics": False,
    "editing_or_relocation_safety": False, "allocatable_space": False,
    "adjacent_boot_bytes": False}
EXPECTED_ROM = {"path": "rom/base.gba", "size": 6_291_456, "sha256": ROM_SHA256}
EXPECTED_UPSTREAM = {
    "boot_thumb_handoff": {"verified": True,
        "manifest_sha256": IDENTITIES[BOOT_DIR / "manifest.json"],
        "payload_sha256": IDENTITIES[BOOT_DIR / "rom-boot-thumb-handoff-cfg.json"],
        "verifier_sha256": IDENTITIES[Path("tools/verify_rom_boot_thumb_handoff_cfg.py")],
        "source_code_ranges": [[0x60FAC, 0x61022], [0x646D0, 0x646EC]]},
    "cfg_v12": {"verified": True,
        "manifest_sha256": IDENTITIES[V12_DIR / "manifest.json"],
        "payload_sha256": IDENTITIES[V12_DIR / "rom-cfg-proven-roots-v12.json"],
        "legacy_verifier_sha256": IDENTITIES[Path("tools/verify_rom_cfg_proven_roots_v12.py")],
        "verifier_sha256": IDENTITIES[Path("tools/verify_rom_cfg_proven_roots_v12_bundle.py")],
        "source_code_range": [0x64574, 0x6462C]},
}
EXPECTED_PROMOTION = {"range": CANDIDATE_RANGE, "bytes": 620,
    "bytes_sha256": CANDIDATE_SHA256,
    "primary_class": "boot_fixed_rom_copy_source_bytes",
    "claim_kind": "fixed_rom_copy_source_bytes", "promotion_batch": SCHEMA,
    "promoted_from_primary_class": "unknown"}


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


def _artifact_directory(root: Path, artifact: Path) -> Path:
    base = root.resolve(strict=True)
    lexical = artifact if artifact.is_absolute() else base / artifact
    try:
        relative = lexical.absolute().relative_to(base)
    except ValueError as error:
        raise ValueError("artifact escapes project root") from error
    cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("artifact path uses symlink ancestor")
    result = lexical.resolve(strict=True)
    if not result.is_relative_to(base) or not result.is_dir():
        raise ValueError("unsafe artifact directory")
    return result


def _u32(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<I", rom, offset)[0]


def _literal_value(rom: bytes, instruction: int) -> int:
    halfword = struct.unpack_from("<H", rom, instruction)[0]
    if halfword & 0xF800 != 0x4800:
        raise ValueError("literal instruction changed")
    return _u32(rom, ((instruction + 4) & ~3) + (halfword & 0xFF) * 4)


def _producers(rom: bytes) -> dict[str, list[int]]:
    result = {"thumb_bl": [], "thumb_b": [], "thumb_bcond": [], "rom_pointers": []}
    for offset in range(0, len(rom) - 3, 2):
        first = struct.unpack_from("<H", rom, offset)[0]
        second = struct.unpack_from("<H", rom, offset + 2)[0]
        if decode_thumb_bl(offset, first, second) == 0x61624:
            result["thumb_bl"].append(offset)
        if decode_thumb_b(offset, first) == 0x61624:
            result["thumb_b"].append(offset)
        condition = (first >> 8) & 0xF
        if first & 0xF000 == 0xD000 and condition < 0xE:
            delta = (first & 0xFF) << 1
            if delta & 0x100:
                delta -= 0x200
            if offset + 4 + delta == 0x61624:
                result["thumb_bcond"].append(offset)
    for offset in range(0, len(rom) - 3, 4):
        if _u32(rom, offset) in (0x08061624, 0x08061625):
            result["rom_pointers"].append(offset)
    return result


def _decode_local_cfg(rom: bytes) -> list[dict[str, Any]]:
    """Decode the complete straight-line local function without trusting its slice hash."""
    rows: list[dict[str, Any]] = []
    offset = LOCAL_CODE_RANGE[0]
    while offset < LOCAL_CODE_RANGE[1]:
        halfword = struct.unpack_from("<H", rom, offset)[0]
        if halfword & 0xF800 == 0xF000:
            if offset + 4 > LOCAL_CODE_RANGE[1]:
                raise ValueError("local DMA CFG changed: truncated BL")
            second = struct.unpack_from("<H", rom, offset + 2)[0]
            target = decode_thumb_bl(offset, halfword, second)
            if target is None:
                raise ValueError("local DMA CFG changed: invalid BL")
            rows.append({"address": offset, "width": 4, "kind": "call", "target": target})
            offset += 4
            continue
        if halfword == 0x4700:
            if offset != LOCAL_CODE_RANGE[1] - 2:
                raise ValueError("local DMA CFG changed: early BX")
            rows.append({"address": offset, "width": 2, "kind": "return"})
            offset += 2
            continue
        if halfword & 0xF000 == 0xD000 or halfword & 0xF800 == 0xE000 \
                or halfword & 0xFF87 == 0x4700:
            raise ValueError("local DMA CFG changed: unexpected branch")
        rows.append({"address": offset, "width": 2, "kind": "fallthrough"})
        offset += 2
    if not rows or rows[-1]["kind"] != "return" or len(rows) != 112:
        raise ValueError("local DMA CFG changed: membership denominator")
    return rows


def _rebuild_dma_descriptors(rom: bytes) -> list[dict[str, Any]]:
    """Interpret the DMA setup prefix and rebuild all nine descriptors from raw opcodes."""
    registers: list[Any] = [None] * 8
    stack: dict[int, Any] = {}
    writes: dict[int, Any] = {}
    descriptors: list[dict[str, Any]] = []
    offset = 0x61628
    while offset < 0x616C0:
        op = struct.unpack_from("<H", rom, offset)[0]
        if op & 0xF800 == 0x4800:  # ldr Rd, [pc, #imm]
            rd = (op >> 8) & 7
            registers[rd] = _u32(rom, ((offset + 4) & ~3) + (op & 0xFF) * 4)
        elif op & 0xF800 == 0x6000:  # str Rd, [Rn, #imm]
            rd, rn, displacement = op & 7, (op >> 3) & 7, ((op >> 6) & 0x1F) * 4
            base = registers[rn]
            if not isinstance(base, int):
                raise ValueError("DMA descriptor dataflow changed: non-address store")
            address, value = base + displacement, registers[rd]
            writes[address] = value
            if address == 0x040000DC:
                source, destination = writes.get(0x040000D4), writes.get(0x040000D8)
                if isinstance(source, tuple) and source[0] == "sp":
                    source = stack.get(source[1])
                if source is None or destination is None or value is None:
                    raise ValueError("DMA descriptor dataflow changed: incomplete descriptor")
                copy_bytes = (value & 0xFFFF) * (4 if value & 0x04000000 else 2)
                descriptors.append({"index": len(descriptors),
                    "source": f"0x{source:08X}" if isinstance(source, int) else source,
                    "destination": f"0x{destination:08X}", "control": f"0x{value:08X}",
                    "copy_bytes": copy_bytes,
                    "candidate_hit": isinstance(source, int) and 0x080004C8 <= source < 0x08000734})
        elif op & 0xF800 == 0x6800:  # ldr Rd, [Rn, #imm]
            rd, rn, displacement = op & 7, (op >> 3) & 7, ((op >> 6) & 0x1F) * 4
            base = registers[rn]
            registers[rd] = writes.get(base + displacement) if isinstance(base, int) else None
        elif op in (0x4669, 0x466A):  # mov r1/r2, sp
            registers[op & 7] = ("sp", 0)
        elif op & 0xF800 == 0x2000:  # movs Rd, #imm
            registers[(op >> 8) & 7] = op & 0xFF
        elif op & 0xF800 == 0x0000:  # lsls Rd, Rm, #imm
            rd, rm, shift = op & 7, (op >> 3) & 7, (op >> 6) & 0x1F
            registers[rd] = registers[rm] << shift
        elif op & 0xFE00 == 0x1C00:  # adds Rd, Rn, #imm3
            rd, rn, immediate = op & 7, (op >> 3) & 7, (op >> 6) & 7
            registers[rd] = registers[rn] + immediate
        elif op & 0xF800 == 0x8000:  # strh Rd, [Rn, #imm]
            rd, rn, displacement = op & 7, (op >> 3) & 7, ((op >> 6) & 0x1F) * 2
            base = registers[rn]
            if isinstance(base, tuple) and base[0] == "sp":
                value = registers[rd]
                stack[base[1] + displacement] = (
                    "sp_zero_halfword" if value == 0 else
                    "sp_0x7fff_halfword" if value == 0x7FFF else value)
            elif not isinstance(base, int):
                raise ValueError("DMA descriptor dataflow changed: invalid halfword store")
        elif op & 0xF800 == 0x9000:  # str Rd, [sp, #imm]
            value = registers[(op >> 8) & 7]
            stack[(op & 0xFF) * 4] = "sp_zero_word" if value == 0 else value
        elif op & 0xF800 == 0xA800:  # add Rd, sp, #imm
            registers[(op >> 8) & 7] = ("sp", (op & 0xFF) * 4)
        else:
            raise ValueError(f"DMA descriptor dataflow changed: opcode 0x{op:04X} at 0x{offset:X}")
        offset += 2
    if descriptors != EXPECTED_DESCRIPTORS:
        raise ValueError("DMA descriptor dataflow changed: rebuilt denominator")
    return descriptors


def _verify_raw_contract(rom: bytes, payload: dict[str, Any]) -> None:
    if len(rom) != 6_291_456 or _sha(rom) != ROM_SHA256:
        raise ValueError("ROM identity changed")
    if _sha(rom[0x4C8:0x734]) != CANDIDATE_SHA256:
        raise ValueError("copy-source bytes changed")
    if _sha(rom[0x61624:0x61710]) != LOCAL_CODE_SHA256:
        raise ValueError("local DMA consumer changed")
    if _sha(rom[0x61710:0x6178C]) != LOCAL_LITERAL_SHA256:
        raise ValueError("local DMA literals changed")
    if rom[0x61708:0x61710].hex() != "02b030bc01bc0047":
        raise ValueError("strict return changed")
    if _producers(rom) != {"thumb_bl": [0x60FE0], "thumb_b": [], "thumb_bcond": [], "rom_pointers": []}:
        raise ValueError("producer denominator changed")
    _decode_local_cfg(rom)
    rebuilt_descriptors = _rebuild_dma_descriptors(rom)
    local = payload.get("local_dma_consumer", {})
    if (local.get("code_range") != LOCAL_CODE_RANGE or local.get("code_sha256") != LOCAL_CODE_SHA256
            or local.get("literal_range") != LOCAL_LITERAL_RANGE or local.get("literal_sha256") != LOCAL_LITERAL_SHA256
            or local.get("producer_denominator") != _producers(rom)
            or local.get("dma_descriptor_denominator") != rebuilt_descriptors
            or local.get("strict_return") != "bx r0"):
        raise ValueError("DMA descriptor denominator changed")
    literal_values = tuple(_literal_value(rom, site) for site in (0x6164A, 0x6164E, 0x61656, 0x6165A, 0x6165E, 0x61664, 0x61668, 0x6166C))
    if literal_values != (0x080004C8, 0x03000680, 0x08000520, 0x0300088C, 0x84000029, 0x080005AC, 0x03000930, 0x84000018):
        raise ValueError("DMA candidate binding changed")
    if rom[0x6458E:0x645A2].hex() != "294c0020211cfdf794ff2748284a211c37f09ffd" \
            or tuple(_literal_value(rom, x) for x in (0x6458E, 0x64598, 0x6459A)) \
            != (0x03005CE8, 0x08000638, 0x04000017):
        raise ValueError("v12 CpuSet binding changed")
    if rom[0x646D0:0x646E2].hex() != "10b506480024047005480649064a37f0fffc" or tuple(_literal_value(rom, x) for x in (0x646D8, 0x646DA, 0x646DC)) != (0x08000690, 0x03005D50, 0x04000029):
        raise ValueError("boot CpuSet binding changed")
    if payload.get("copy_operations") != EXPECTED_OPERATIONS:
        raise ValueError("copy operation range vector changed")
    if payload.get("copy_operation_union") != {"range": CANDIDATE_RANGE, "bytes": 620,
            "range_vector_sha256": "2f181c055623f48a0eb22a66571ae04c357fc760d92588694edf52056494386f"}:
        raise ValueError("copy operation union changed")
    if payload.get("rom") != EXPECTED_ROM:
        raise ValueError("ROM contract changed")
    if payload.get("upstream_evidence") != EXPECTED_UPSTREAM:
        raise ValueError("upstream evidence contract changed")
    if payload.get("promotion") != EXPECTED_PROMOTION:
        raise ValueError("promotion contract changed")
    if payload.get("scope") != EXPECTED_SCOPE:
        raise ValueError("scope widened")


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    report = {"schema": VERIFY_SCHEMA, "verified": False, "contract_ok": False,
        "promotion_bytes": 0, "copy_operation_count": 0, "dma_descriptor_count": 0,
        "upstream_boot_verified": False, "upstream_v12_verified": False, "errors": []}
    try:
        root = root.resolve(strict=True)
        directory = _artifact_directory(root, artifact)
        if {p.name for p in directory.iterdir()} != EXPECTED_FILES:
            raise ValueError("artifact file set changed")
        manifest_raw = (directory / "manifest.json").read_bytes()
        payload_raw = (directory / PAYLOAD_NAME).read_bytes()
        manifest = json.loads(manifest_raw)
        payload = json.loads(payload_raw)
        if _canonical(manifest) != manifest_raw:
            raise ValueError("manifest is not canonical JSON")
        if _canonical(payload) != payload_raw:
            raise ValueError("payload is not canonical JSON")
        if manifest.get("schema") != "git-artifact-promotion-v1" or manifest.get("artifact_schema") != SCHEMA or manifest.get("artifact_status") != "accepted":
            raise ValueError("manifest contract changed")
        file_row = manifest.get("files", {}).get(PAYLOAD_NAME, {})
        if file_row != {"size": len(payload_raw), "sha256": _sha(payload_raw)}:
            raise ValueError("payload identity changed")
        if payload.get("schema") != SCHEMA:
            raise ValueError("payload schema changed")
        for path, expected in IDENTITIES.items():
            if _sha(_safe_file(root, path).read_bytes()) != expected:
                raise ValueError(f"upstream identity changed: {path}")
        boot = verify_boot(root, _safe_directory(root, BOOT_DIR))
        completed = subprocess.run(
            [sys.executable, "-I", "-S", str(_safe_file(root, Path("tools/verify_rom_cfg_proven_roots_v12_bundle.py"))),
             "--root", str(root), "--artifact-dir", str(_safe_directory(root, V12_DIR))],
            cwd=root, check=False, capture_output=True, text=True,
        )
        try:
            v12 = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise ValueError("v12 bundle verifier emitted invalid JSON") from error
        if completed.returncode != 0 or boot.get("verified") is not True or v12.get("verified") is not True:
            raise ValueError("upstream verification failed")
        report["upstream_boot_verified"] = report["upstream_v12_verified"] = True
        _verify_raw_contract(_safe_file(root, ROM_PATH).read_bytes(), payload)
        implementation = manifest.get("implementation", {})
        for key, path in {"exporter": Path("tools/export_rom_boot_copy_sources.py"),
                          "verifier": Path("tools/verify_rom_boot_copy_sources.py"),
                          "test": Path("tests/test_export_rom_boot_copy_sources.py")}.items():
            if implementation.get(f"{key}_sha256") != _sha(_safe_file(root, path).read_bytes()):
                raise ValueError(f"{key} implementation identity changed")
        report.update({"verified": True, "contract_ok": True, "promotion_bytes": 620,
            "copy_operation_count": 5, "dma_descriptor_count": 9})
    except Exception as error:
        report["errors"].append(str(error))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
