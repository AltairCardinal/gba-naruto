#!/usr/bin/env python3
"""Export the frozen boot ROM copy-source packet."""

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
import subprocess
import sys
import tempfile
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.thumb_branch import decode_thumb_b, decode_thumb_bl
from tools.verify_rom_boot_thumb_handoff_cfg import verify_artifact as verify_boot


SCHEMA = "rom-boot-copy-sources-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
BASELINE_COVERAGE_SHA256 = "e48c8f6d0df1d3469be2336caa71f628d82a51d4e637d6df42ebded412359c36"
OFFICIAL = Path("artifacts/rom-boot-copy-sources-v1")
PAYLOAD_NAME = "rom-boot-copy-sources.json"
MANIFEST_NAME = "manifest.json"
CANDIDATE_RANGE = [0x4C8, 0x734]
CANDIDATE_SHA256 = "0be5228ec171480a4097db134e32c030972f43fbf637a425f3f4826450944e80"
LOCAL_CODE_RANGE = [0x61624, 0x61710]
LOCAL_CODE_SHA256 = "e3ba1dadf23b428fd2a39b6d9aef48b7ba9521d825ca196b37d7a93403192dff"
LOCAL_LITERAL_RANGE = [0x61710, 0x6178C]
LOCAL_LITERAL_SHA256 = "e1bdf99fdcdfa92e4bc900e57730c3ee8d1cea55f1eaeed7ec1a56768b561031"
CPUSET_RANGE = [0x9C0E0, 0x9C0E4]
CPUSET_SHA256 = "07967ebdc3979cd4fd4de37fd22b3e6de8965b00dae4ac5585577c9709839652"
BOOT_DIR = Path("artifacts/rom-boot-thumb-handoff-cfg-v1")
BOOT_MANIFEST_SHA256 = "d5af12930ed8e7539396f81deda19ae938eee3f029b95c959f6fa5d57c676d74"
BOOT_PAYLOAD_SHA256 = "a35b581e44b276399874a2fc393f22f3c548c6b99e053f504587bdd92fbad295"
BOOT_VERIFIER_PATH = Path("tools/verify_rom_boot_thumb_handoff_cfg.py")
BOOT_VERIFIER_SHA256 = "2592e4f48f1a197e30cb4d360201228fc2bbeef5fad12879b1bbf77b29815b39"
V12_DIR = Path("artifacts/rom-cfg-proven-roots-v12")
V12_MANIFEST_SHA256 = "bf88e08f4eed6b53e1debef709c2ef13fb891c11e9c172485e494eef57954677"
V12_PAYLOAD_SHA256 = "fd9df8f3d93de1df5aa7e725040f27f854d08e8203d6cada51db829ddcd9bcee"
V12_VERIFIER_PATH = Path("tools/verify_rom_cfg_proven_roots_v12.py")
V12_VERIFIER_SHA256 = "1043291dfb16b90ef025242b976a4bf89a6a0173a0ac4904fc3534d625acbede"
V12_BUNDLE_VERIFIER_PATH = Path("tools/verify_rom_cfg_proven_roots_v12_bundle.py")
V12_BUNDLE_VERIFIER_SHA256 = "ee1d50f3018b5d78d652eb5ed6d1f7108670669b60e5518b9956df987b60275a"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _safe_file(root: Path, relative: Path) -> Path:
    if relative.is_absolute():
        return relative.resolve(strict=True)
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


def _u32(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<I", rom, offset)[0]


def _literal_value(rom: bytes, instruction: int) -> int:
    halfword = struct.unpack_from("<H", rom, instruction)[0]
    if halfword & 0xF800 != 0x4800:
        raise ValueError(f"literal load changed at 0x{instruction:X}")
    return _u32(rom, ((instruction + 4) & ~3) + (halfword & 0xFF) * 4)


def _producer_denominator(rom: bytes) -> dict[str, list[int]]:
    target = LOCAL_CODE_RANGE[0]
    result = {"thumb_bl": [], "thumb_b": [], "thumb_bcond": [], "rom_pointers": []}
    for offset in range(0, len(rom) - 3, 2):
        first = struct.unpack_from("<H", rom, offset)[0]
        second = struct.unpack_from("<H", rom, offset + 2)[0]
        if decode_thumb_bl(offset, first, second) == target:
            result["thumb_bl"].append(offset)
        if decode_thumb_b(offset, first) == target:
            result["thumb_b"].append(offset)
        condition = (first >> 8) & 0xF
        if first & 0xF000 == 0xD000 and condition < 0xE:
            delta = (first & 0xFF) << 1
            if delta & 0x100:
                delta -= 0x200
            if offset + 4 + delta == target:
                result["thumb_bcond"].append(offset)
    for offset in range(0, len(rom) - 3, 4):
        if _u32(rom, offset) in (ROM_BASE + target, ROM_BASE + target + 1):
            result["rom_pointers"].append(offset)
    expected = {"thumb_bl": [0x60FE0], "thumb_b": [], "thumb_bcond": [], "rom_pointers": []}
    if result != expected:
        raise ValueError("local DMA consumer producer denominator changed")
    return result


def _dma_descriptors(rom: bytes) -> list[dict[str, Any]]:
    if _sha(rom[LOCAL_CODE_RANGE[0]:LOCAL_CODE_RANGE[1]]) != LOCAL_CODE_SHA256:
        raise ValueError("local DMA consumer changed")
    if _sha(rom[LOCAL_LITERAL_RANGE[0]:LOCAL_LITERAL_RANGE[1]]) != LOCAL_LITERAL_SHA256:
        raise ValueError("local DMA literal denominator changed")
    if rom[0x61708:0x61710].hex() != "02b030bc01bc0047":
        raise ValueError("local DMA strict return changed")
    expected_literals = {
        0x61628: 0x040000D4, 0x6162A: 0x08000104, 0x6162E: 0x0300007C,
        0x61632: 0x84000080, 0x6163C: 0x0853D5B4, 0x61640: 0x03000014,
        0x61644: 0x8400000E, 0x6164A: 0x080004C8, 0x6164E: 0x03000680,
        0x61656: 0x08000520, 0x6165A: 0x0300088C, 0x6165E: 0x84000029,
        0x61664: 0x080005AC, 0x61668: 0x03000930, 0x6166C: 0x84000018,
        0x61684: 0x8100C000, 0x6169A: 0x81000002, 0x616A8: 0x0300027C,
        0x616AC: 0x85000100, 0x616BA: 0x84000100,
    }
    if {site: _literal_value(rom, site) for site in expected_literals} != expected_literals:
        raise ValueError("local DMA descriptor literal binding changed")
    return [
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


def _copy_operations(rom: bytes) -> list[dict[str, Any]]:
    if _sha(rom[CPUSET_RANGE[0]:CPUSET_RANGE[1]]) != CPUSET_SHA256:
        raise ValueError("CpuSet wrapper changed")
    if rom[0x6458E:0x645A2].hex() != "294c0020211cfdf794ff2748284a211c37f09ffd":
        raise ValueError("v12 CpuSet consumer changed")
    if _literal_value(rom, 0x6458E) != 0x03005CE8:
        raise ValueError("v12 CpuSet destination changed")
    if (_literal_value(rom, 0x64598), _literal_value(rom, 0x6459A)) != (0x08000638, 0x04000017):
        raise ValueError("v12 CpuSet literals changed")
    if rom[0x646D0:0x646E2].hex() != "10b506480024047005480649064a37f0fffc":
        raise ValueError("boot CpuSet consumer changed")
    if tuple(_literal_value(rom, site) for site in (0x646D8, 0x646DA, 0x646DC)) != (0x08000690, 0x03005D50, 0x04000029):
        raise ValueError("boot CpuSet literals changed")
    return [
        {"id": "dma-2", "consumer": "DMA3", "callsite": 0x6164A, "source_range": [0x4C8, 0x6C8], "destination": "0x03000680", "control": "0x84000080", "copy_bytes": 512},
        {"id": "dma-3", "consumer": "DMA3", "callsite": 0x61656, "source_range": [0x520, 0x5C4], "destination": "0x0300088C", "control": "0x84000029", "copy_bytes": 164},
        {"id": "dma-4", "consumer": "DMA3", "callsite": 0x61664, "source_range": [0x5AC, 0x60C], "destination": "0x03000930", "control": "0x84000018", "copy_bytes": 96},
        {"id": "cpuset-v12", "consumer": "CpuSet", "callsite": 0x6459E, "source_range": [0x638, 0x694], "destination": "0x03005CE8", "control": "0x04000017", "copy_bytes": 92},
        {"id": "cpuset-boot", "consumer": "CpuSet", "callsite": 0x646DE, "source_range": [0x690, 0x734], "destination": "0x03005D50", "control": "0x04000029", "copy_bytes": 164},
    ]


def _identity(root: Path, path: Path, expected: str, label: str) -> None:
    if _sha(_safe_file(root, path).read_bytes()) != expected:
        raise ValueError(f"{label} identity changed")


def _upstream(root: Path) -> dict[str, Any]:
    for path, expected, label in (
        (BOOT_DIR / MANIFEST_NAME, BOOT_MANIFEST_SHA256, "boot manifest"),
        (BOOT_DIR / "rom-boot-thumb-handoff-cfg.json", BOOT_PAYLOAD_SHA256, "boot payload"),
        (BOOT_VERIFIER_PATH, BOOT_VERIFIER_SHA256, "boot verifier"),
        (V12_DIR / MANIFEST_NAME, V12_MANIFEST_SHA256, "v12 manifest"),
        (V12_DIR / "rom-cfg-proven-roots-v12.json", V12_PAYLOAD_SHA256, "v12 payload"),
        (V12_VERIFIER_PATH, V12_VERIFIER_SHA256, "v12 verifier"),
        (V12_BUNDLE_VERIFIER_PATH, V12_BUNDLE_VERIFIER_SHA256, "v12 bundle verifier"),
    ):
        _identity(root, path, expected, label)
    boot = verify_boot(root, _safe_directory(root, BOOT_DIR))
    completed = subprocess.run(
        [sys.executable, "-I", "-S", str(_safe_file(root, V12_BUNDLE_VERIFIER_PATH)),
         "--root", str(root), "--artifact-dir", str(_safe_directory(root, V12_DIR))],
        cwd=root, check=False, capture_output=True, text=True,
    )
    try:
        v12 = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("v12 bundle verifier emitted invalid JSON") from error
    if completed.returncode != 0 or boot.get("verified") is not True or v12.get("verified") is not True:
        raise ValueError("upstream independent verification failed")
    return {
        "boot_thumb_handoff": {"verified": True, "manifest_sha256": BOOT_MANIFEST_SHA256,
            "payload_sha256": BOOT_PAYLOAD_SHA256, "verifier_sha256": BOOT_VERIFIER_SHA256,
            "source_code_ranges": [[0x60FAC, 0x61022], [0x646D0, 0x646EC]]},
        "cfg_v12": {"verified": True, "manifest_sha256": V12_MANIFEST_SHA256,
            "payload_sha256": V12_PAYLOAD_SHA256, "legacy_verifier_sha256": V12_VERIFIER_SHA256,
            "verifier_sha256": V12_BUNDLE_VERIFIER_SHA256,
            "source_code_range": [0x64574, 0x6462C]},
    }


def build_payload(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE:
        raise ValueError("ROM size changed")
    if _sha(rom[CANDIDATE_RANGE[0]:CANDIDATE_RANGE[1]]) != CANDIDATE_SHA256:
        raise ValueError("copy-source bytes changed")
    local = {"code_range": LOCAL_CODE_RANGE, "code_sha256": LOCAL_CODE_SHA256,
        "literal_range": LOCAL_LITERAL_RANGE, "literal_sha256": LOCAL_LITERAL_SHA256,
        "producer_denominator": _producer_denominator(rom),
        "dma_descriptor_denominator": _dma_descriptors(rom), "strict_return": "bx r0"}
    operations = _copy_operations(rom)
    if _sha(rom) != ROM_SHA256:
        raise ValueError("ROM SHA-256 changed")
    return {"schema": SCHEMA, "rom": {"path": "rom/base.gba", "size": len(rom), "sha256": ROM_SHA256},
        "upstream_evidence": _upstream(root), "local_dma_consumer": local,
        "copy_operations": operations,
        "copy_operation_union": {"range": CANDIDATE_RANGE, "bytes": 620,
            "range_vector_sha256": "2f181c055623f48a0eb22a66571ae04c357fc760d92588694edf52056494386f"},
        "promotion": {"range": CANDIDATE_RANGE, "bytes": 620, "bytes_sha256": CANDIDATE_SHA256,
            "primary_class": "boot_fixed_rom_copy_source_bytes", "claim_kind": "fixed_rom_copy_source_bytes",
            "promotion_batch": SCHEMA, "promoted_from_primary_class": "unknown"},
        "scope": {"fixed_rom_copy_source_bytes": True, "arm_code_semantics": False,
            "natural_runtime_reachability": False, "business_semantics": False,
            "editing_or_relocation_safety": False, "allocatable_space": False,
            "adjacent_boot_bytes": False}}


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
            if code == errno.EEXIST:
                raise FileExistsError(code, os.strerror(code), destination)
            raise OSError(code, os.strerror(code), destination)
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    lexical = (output if output.is_absolute() else root / output).absolute()
    try:
        relative = lexical.relative_to(root)
    except ValueError as error:
        raise ValueError("output escapes project root") from error
    cursor = root
    for part in relative.parts[:-1]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("output path uses symlink ancestor")
    target = lexical.resolve(strict=False)
    if target.exists() or lexical.is_symlink():
        raise FileExistsError(f"output already exists: {output}")
    if not target.is_relative_to(root):
        raise ValueError("output escapes project root")
    payload_raw = _canonical(build_payload(root))
    implementation = {}
    for key, path in {"exporter": Path(__file__).relative_to(root),
                      "verifier": Path("tools/verify_rom_boot_copy_sources.py"),
                      "test": Path("tests/test_export_rom_boot_copy_sources.py")}.items():
        implementation[f"{key}_sha256"] = _sha(_safe_file(root, path).read_bytes())
    manifest = {"schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,
        "artifact_status": "accepted", "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}},
        "summary": {"copy_operation_count": 5, "dma_descriptor_count": 9, "promotion_bytes": 620},
        "implementation": implementation,
        "producer": {"command": ["python3", "tools/export_rom_boot_copy_sources.py", "--root", ".", "--output", relative.as_posix()]},
        "verifier": {"command": ["python3", "tools/verify_rom_boot_copy_sources.py", "--root", ".", "--artifact", relative.as_posix()]}}
    manifest_raw = _canonical(manifest)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
    try:
        for name, raw in ((PAYLOAD_NAME, payload_raw), (MANIFEST_NAME, manifest_raw)):
            with (temporary / name).open("xb") as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        fd = os.open(temporary, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(fd)
        finally: os.close(fd)
        _publish_exclusive(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=OFFICIAL)
    args = parser.parse_args()
    print(json.dumps(export_artifact(args.root, args.output)["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
