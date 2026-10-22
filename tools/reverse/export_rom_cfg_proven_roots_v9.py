#!/usr/bin/env python3
"""Export the battle-controller direct-BL CFG proven-roots v9 packet."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import heapq
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Any
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
_CLEAN_CLI_STARTUP_CONFIRMED = False


def _require_isolated_cli_runtime() -> None:
    global _CLEAN_CLI_STARTUP_CONFIRMED
    if __name__ != "__main__":
        return
    if not sys.flags.isolated or not sys.flags.no_site:
        raise RuntimeError("CFG v9 CLI requires Python -I -S isolation")
    if "capstone" in sys.modules:
        raise RuntimeError("CFG v9 CLI rejects preloaded Capstone modules")
    if os.environ.get("LIBCAPSTONE_PATH"):
        raise RuntimeError("CFG v9 CLI rejects LIBCAPSTONE_PATH overrides")
    _CLEAN_CLI_STARTUP_CONFIRMED = True


_require_isolated_cli_runtime()

for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import capstone

from tools.export_rom_cfg_inventory import (
    MAX_INSTRUCTION_COUNT,
    ROM_PATH,
    ROM_SHA256,
    _assert_nonoverlapping_nodes,
    _build_blocks,
    _canonical_json,
    _canonical_sha,
    _decode_one,
    _frontier_records,
    _key,
    _reject_symlink_components,
    _replace_output_dir,
    _root_results,
    _safe_file,
)
from tools.export_rom_cfg_proven_roots_v2 import (
    _cross_edge_records,
    _extension_summary,
)
from tools.verify_rom_cfg_inventory import _verify_blocks
from tools.verify_rom_cfg_proven_roots_v2 import _owner_map


ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
SCHEMA = "rom-cfg-proven-roots-v9"
VERIFY_SCHEMA = "rom-cfg-proven-roots-verification-v9"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
PAYLOAD_NAME = "rom-cfg-proven-roots-v9.json"
MANIFEST_NAME = "manifest.json"
EXPORTER_PATH = Path("tools/export_rom_cfg_proven_roots_v9.py")
VERIFIER_PATH = Path("tools/verify_rom_cfg_proven_roots_v9.py")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
COVERAGE_SHA256 = (
    "2ff9bc857e182c4bfeeaa572929569801549765ef1d3566cf10c17334125b9d1"
)
EXPECTED_COVERAGE_SUMMARY = {
    "classified_bytes": 6_105_778,
    "unknown_bytes": 185_678,
    "claim_count": 13_929,
    "segment_count": 16_171,
}
PROMOTION_BLOCK_RANGE_DENOMINATOR_SHA256 = (
    "058f90da96cf556a2b406fbea2952435bbd64c302654657c4981841587fd7aeb"
)
EXPERIMENT_OUTPUT_ROOT = Path("build/experiments/active/cfg-proven-roots-v9")

EXPECTED_VERIFIER_REPORT = {
    "schema": VERIFY_SCHEMA,
    "verified": True,
    "errors": [],
    "control_flow_oracle": "armv4t-raw-encoding",
    "independently_rebuilt_instruction_count": 299,
    "root_count": 8,
    "decoded_instruction_count": 299,
    "decoded_basic_block_count": 62,
    "reachable_instruction_bytes": 628,
    "frontier_count": 0,
    "baseline_cross_edge_count": 16,
}

CONTROLLER_ARTIFACT = Path("artifacts/rom-battle-controller-cfg-v1")
CONTROLLER_PAYLOAD = CONTROLLER_ARTIFACT / "rom-battle-controller-cfg.json"
CONTROLLER_PAYLOAD_SHA256 = (
    "c8b1d1c2068d85912ede1fd35be31f0cf9cb43943beb10f1058d43c65c00449a"
)
CONTROLLER_MANIFEST_SHA256 = (
    "282b4323bf965676a68b5326f2edbbdee35606b987412d351de137b82d50fe63"
)
CONTROLLER_VERIFIER = Path("tools/verify_rom_battle_controller_cfg.py")
CONTROLLER_VERIFIER_SHA256 = (
    "fc3c33d37b9fb2af885324915f82e3c0da74b3efd25967b8289b49d8b9169a87"
)

EXPECTED_CONTROLLER_REPORT = {
    "controller_range": [471732, 479388],
    "controller_sha256": (
        "c9bdc220590a851fa331960bcb32be90eb9ac7248a5cd3dabb9f8afa0b674bc1"
    ),
    "dispatcher_default_state_count": 65498,
    "dispatcher_nondefault_state_count": 38,
    "errors": [],
    "root_count": 38,
    "schema": "rom-battle-controller-cfg-verification-v1",
    "summary": {
        "decoded_basic_block_count": 739,
        "decoded_instruction_count": 2756,
        "frontier_count": 5,
        "frontier_reasons": {
            "decode_failure": 1,
            "indirect_pc_target": 2,
            "unsupported_armv4t_instruction": 2,
        },
        "opaque_baseline_edge_count": 9,
        "opaque_external_edge_count": 227,
        "reachable_instruction_bytes": 6172,
        "skipped_root_count": 1,
    },
    "verified": True,
}

BASELINE_SPECS = (
    (
        "v2",
        Path("artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json"),
        "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd",
        "ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753",
        "rom-cfg-inventory-v2",
        Path("tools/verify_rom_cfg_inventory.py"),
    ),
    (
        "v3",
        Path("artifacts/rom-cfg-inventory-v3/rom-cfg-inventory-v3.json"),
        "596c4d8cffa57f3899858a0a59351894b1398006ee0405ce799ed9f32a81bf9d",
        "6aa788611f73856e621f5c74aab544d47b034307a9dc1180f6fd8f81cb1f423b",
        "rom-cfg-inventory-v3",
        Path("tools/verify_rom_cfg_inventory_v3.py"),
    ),
    (
        "proven_roots_v1",
        Path("artifacts/rom-cfg-proven-roots-v1/rom-cfg-proven-roots.json"),
        "7fdee7d0d62d3a8c82bfe7b03804e9cb0e3d213ebdf63acce6b0533045aecf54",
        "ea1230fe24cf111a91044c059468a1467e46c471363780b23c2a0311bab8644a",
        "rom-cfg-proven-roots-v1",
        Path("tools/verify_rom_cfg_proven_roots.py"),
    ),
    (
        "proven_roots_v2",
        Path("artifacts/rom-cfg-proven-roots-v2/rom-cfg-proven-roots-v2.json"),
        "a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba",
        "a3683f3d21ec5a162b4cdb97c70b639ff261d9ff5e0f3bb4941848205bb4d9ca",
        "rom-cfg-proven-roots-v2",
        Path("tools/verify_rom_cfg_proven_roots_v2.py"),
    ),
    (
        "battle_controller",
        CONTROLLER_PAYLOAD,
        CONTROLLER_PAYLOAD_SHA256,
        CONTROLLER_MANIFEST_SHA256,
        "rom-battle-controller-cfg-v1",
        CONTROLLER_VERIFIER,
    ),
    (
        "proven_roots_v3",
        Path("artifacts/rom-cfg-proven-roots-v3/rom-cfg-proven-roots-v3.json"),
        "f2de5ca57685e3542d5e483e5a171a30eb32bb6dc6ce9794cc683371579af9a2",
        "4aa979aa65408163e577f7d728ba32a99a13bd6c9615c40f28a570036e5ba275",
        "rom-cfg-proven-roots-v3",
        Path("tools/verify_rom_cfg_proven_roots_v3.py"),
    ),
    (
        "proven_roots_v4",
        Path("artifacts/rom-cfg-proven-roots-v4/rom-cfg-proven-roots-v4.json"),
        "d14c9f4198d9209d03d8511351b5dc997ade409a3218e9f05993c8c7f11456eb",
        "e306ac59b4b9a815702fda8aef54058908fb9113a5afad4be938c69d42d67404",
        "rom-cfg-proven-roots-v4",
        Path("tools/verify_rom_cfg_proven_roots_v4.py"),
    ),
    (
        "proven_roots_v5",
        Path("artifacts/rom-cfg-proven-roots-v5/rom-cfg-proven-roots-v5.json"),
        "680b03dffb5c3dbbca41d9a5d0872db560a1a05850d7928ce75243397a54f040",
        "f6deb37d40ae4ea83e220adc8303c64646a9280d34d6c325d8ea0492963dcd8d",
        "rom-cfg-proven-roots-v5",
        Path("tools/verify_rom_cfg_proven_roots_v5.py"),
    ),
    (
        "proven_roots_v6",
        Path("artifacts/rom-cfg-proven-roots-v6/rom-cfg-proven-roots-v6.json"),
        "e5b27a55c77cd1df4ac5ec39f2dd05735b0b53c01b7cbbcf1620db1681a3c3ec",
        "e00d8a1b7b08305a44f7ac3d36a5e294d1f69b5f05ceab151e14749cf92802f4",
        "rom-cfg-proven-roots-v6",
        Path("tools/verify_rom_cfg_proven_roots_v6.py"),
    ),
    (
        "proven_roots_v7",
        Path("artifacts/rom-cfg-proven-roots-v7/rom-cfg-proven-roots-v7.json"),
        "184e9b84df829fb1ad41f272aabe931c1a1f86111eebd60629ad2d2a23d89a06",
        "da9a1b5fe7ce8e7889fbba9fe8251c907ed18f6b273cbcc3be145101ece99114",
        "rom-cfg-proven-roots-v7",
        Path("tools/verify_rom_cfg_proven_roots_v7.py"),
    ),
    (
        "proven_roots_v8",
        Path("artifacts/rom-cfg-proven-roots-v8/rom-cfg-proven-roots-v8.json"),
        "5fa1150d2ed9f785d50132a9eae316af192d70838fbee3061d7d3010c35fb1d6",
        "0c9194507c50b7f2c00c6ee09b517211f64b7b344475952fe3c908b1e54e0002",
        "rom-cfg-proven-roots-v8",
        Path("tools/verify_rom_cfg_proven_roots_v8.py"),
    ),
)

EXPECTED_BASELINE_REPORTS = {
    "v2": {
        "schema": "rom-cfg-inventory-verification-v2",
        "verified": True,
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 40_872,
        "root_count": 263,
        "decoded_instruction_count": 40_872,
        "decoded_basic_block_count": 7_725,
        "reachable_instruction_bytes": 86_184,
        "frontier_count": 366,
        "closed_root_count": 4,
        "frontier_open_root_count": 259,
        "budget_exhausted": False,
        "errors": [],
    },
    "v3": {
        "schema": "rom-cfg-inventory-verification-v3",
        "verified": True,
        "control_flow_oracle": "armv4t-raw-encoding",
        "resolved_frontier_count": 29,
        "new_entry_seed_count": 101,
        "independently_rebuilt_instruction_count": 4_698,
        "decoded_basic_block_count": 891,
        "reachable_instruction_bytes": 9_902,
        "frontier_count": 16,
        "errors": [],
    },
    "proven_roots_v1": {
        "schema": "rom-cfg-proven-roots-verification-v1",
        "verified": True,
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 6_166,
        "root_count": 2,
        "decoded_instruction_count": 6_166,
        "decoded_basic_block_count": 1_203,
        "reachable_instruction_bytes": 12_966,
        "frontier_count": 28,
        "baseline_cross_edge_count": 259,
        "errors": [],
    },
    "proven_roots_v2": {
        "schema": "rom-cfg-proven-roots-verification-v2",
        "verified": True,
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 4_809,
        "root_count": 3,
        "decoded_instruction_count": 4_809,
        "decoded_basic_block_count": 835,
        "reachable_instruction_bytes": 9_876,
        "frontier_count": 28,
        "baseline_cross_edge_count": 82,
        "errors": [],
    },
    "battle_controller": EXPECTED_CONTROLLER_REPORT,
    "proven_roots_v3": {
        "schema": "rom-cfg-proven-roots-verification-v3",
        "verified": True,
        "errors": [],
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 52,
        "root_count": 1,
        "decoded_instruction_count": 52,
        "decoded_basic_block_count": 8,
        "reachable_instruction_bytes": 110,
        "frontier_count": 0,
        "baseline_cross_edge_count": 5,
    },
    "proven_roots_v4": {
        "schema": "rom-cfg-proven-roots-verification-v4",
        "verified": True,
        "errors": [],
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 486,
        "root_count": 1,
        "decoded_instruction_count": 486,
        "decoded_basic_block_count": 118,
        "reachable_instruction_bytes": 1_044,
        "frontier_count": 6,
        "baseline_cross_edge_count": 29,
    },
    "proven_roots_v5": {
        "schema": "rom-cfg-proven-roots-verification-v5",
        "verified": True,
        "errors": [],
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 576,
        "root_count": 3,
        "decoded_instruction_count": 576,
        "decoded_basic_block_count": 124,
        "reachable_instruction_bytes": 1_252,
        "frontier_count": 8,
        "baseline_cross_edge_count": 40,
    },
    "proven_roots_v6": {
        "schema": "rom-cfg-proven-roots-verification-v6",
        "verified": True,
        "errors": [],
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 12_564,
        "root_count": 5,
        "decoded_instruction_count": 12_564,
        "decoded_basic_block_count": 2_305,
        "reachable_instruction_bytes": 27_224,
        "frontier_count": 85,
        "baseline_cross_edge_count": 916,
    },
    "proven_roots_v7": {
        "schema": "rom-cfg-proven-roots-verification-v7",
        "verified": True,
        "errors": [],
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 155,
        "root_count": 8,
        "decoded_instruction_count": 155,
        "decoded_basic_block_count": 38,
        "reachable_instruction_bytes": 332,
        "frontier_count": 1,
        "baseline_cross_edge_count": 17,
    },
    "proven_roots_v8": {
        "schema": "rom-cfg-proven-roots-verification-v8",
        "verified": True,
        "errors": [],
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 113,
        "root_count": 1,
        "decoded_instruction_count": 113,
        "decoded_basic_block_count": 20,
        "reachable_instruction_bytes": 246,
        "frontier_count": 1,
        "baseline_cross_edge_count": 10,
    },
}

EXPECTED_PRODUCERS = (
    ("producer_07363e", 0x07363E, "fff7dffc", "1c089fb695d1060f948e8ba877cfece69f65166a4b9badc3fab7a20e2703b5a0", 0x073000),
    ("producer_07365a", 0x07365A, "01f0cdfe", "b6f835b147e47546adefd6c7ff34dc02cefb5aefb7c00eacb1dffb159edd48b1", 0x0753F8),
    ("producer_07367c", 0x07367C, "f8f744fe", "dae5c8f0aee4436b61b01d472df78215f2a58ef7c5bc3a0e922f5157a1d0c339", 0x06C308),
    ("producer_073680", 0x073680, "f8f7c4fe", "094d93ee8022c7361763cf96ce75e1f9bba7dbaf660cd57f91db2f8f4b781547", 0x06C40C),
    ("producer_0736a4", 0x0736A4, "f8f7b2fe", "5987e0c3245a1752ec49b6703226854b8f2aabc0ee683b4fec900e1d5735096a", 0x06C40C),
    ("producer_0736e4", 0x0736E4, "01f034fe", "34b5b9d65861365a1fb5208418fc9501100757583c4d708b32702255efbdd83a", 0x075350),
    ("producer_073d92", 0x073D92, "f8f73df9", "348fd24e3193d9e48d3c74f963f74dfd74c18b7d9441b4bfb31ca1b9fc42f7e7", 0x06C010),
    ("producer_07416c", 0x07416C, "f7f750ff", "4890a93105385eb97e91f79071787b2c2b3469ac51b7a15ee95d21307c1478ae", 0x06C010),
    ("producer_074184", 0x074184, "fcf728fe", "412874a8ef805772f7a4b26f44e70eff74b5945ea2b16c7628dd761884c0ae7a", 0x070DD8),
    ("producer_07445c", 0x07445C, "f7f7d6ff", "70850957feb2530845de8025a4dabf91cef7b0a5faa06b1f0cf7e519651f74c3", 0x06C40C),
    ("producer_075058", 0x075058, "f8f708fa", "d47055c2d5971691a56a5463693024247c3b2f996b53044a762e97aec01c86a1", 0x06D46C),
)
EXCLUDED_PRODUCER_OFFSETS = {0x0736A4, 0x07445C}

ROOT_BYTES = {
    0x06C010: ("f0b54f46", "8a1d56a49bd75817476a967ee4e23ecef2beeffa6748599c19bc8e7ed7620257"),
    0x06C308: ("f0b50125", "38d84a618b60c05122c81bcf237705255315d62ff514f1101c1c381f7b1bf84f"),
    0x06C40C: ("f0b55746", "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb"),
    0x06D46C: ("10b50122", "f9285d0356648cafa73cb3c5165eec1c9543674d71a73bf0f56b53ab64b3d2c4"),
    0x070DD8: ("00b50548", "10fbec2abe0b764143f9439fc967f2168d34042c4a7a9580898fe107353a53a2"),
    0x073000: ("30b50024", "084b652a396ba0b09104d77ed2eb65a9bbe477ee1620d3c0cf5e861944bfd405"),
    0x075350: ("70b50006", "d883b6a8cd5ef418c7a77a5dcf2ecd057c71851d6d22fe691dd930084317f453"),
    0x0753F8: ("30b50006", "cede13811d1cad27a7d27f09911219f8c9e6560ebdc98269cf4044456f763502"),
}

PROMOTION_RANGES = (
    (0x06C010, 0x06C09E),
    (0x06C308, 0x06C364),
    (0x06C40C, 0x06C418),
    (0x06D46C, 0x06D49A),
    (0x070DD8, 0x070DEE),
    (0x073000, 0x073048),
    (0x075350, 0x0753F2),
    (0x0753F8, 0x075436),
    (0x07543C, 0x07544E),
)
RETURN_EXIT_PREFIXES = {
    0x06C09C: "01bc0047",
    0x06C362: "01bc0047",
    0x06D498: "01bc0047",
    0x070DEC: "01bc0047",
    0x073046: "01bc0047",
    0x0753F0: "01bc0047",
    0x07544C: "02bc0847",
}

SCOPE = {
    "fixed_direct_producer_denominator_complete": True,
    "controller_provenance_denominator_complete": True,
    "baseline_entries_treated_as_opaque": True,
    "baseline_identity_complete": True,
    "promotion_ranges_complete": True,
    "promotion_ranges": [list(item) for item in PROMOTION_RANGES],
    "current_known_overlap_bytes": 0,
    "opaque_return_exit_count": 7,
    "runtime_reachability_complete": False,
    "global_function_entry_denominator_complete": False,
    "global_indirect_target_denominator_complete": False,
}

CAPSTONE_RUNTIME_PYTHON_NAMES = (
    "__init__.py", "arm.py", "arm64.py", "arm64_const.py", "arm_const.py",
    "bpf.py", "bpf_const.py", "evm.py", "evm_const.py", "m680x.py", "m680x_const.py",
    "m68k.py", "m68k_const.py", "mips.py", "mips_const.py", "mos65xx.py", "mos65xx_const.py",
    "ppc.py", "ppc_const.py", "riscv.py", "riscv_const.py", "sh.py", "sh_const.py",
    "sparc.py", "sparc_const.py", "systemz.py", "sysz_const.py", "tms320c64x.py",
    "tms320c64x_const.py", "tricore.py", "tricore_const.py", "wasm.py", "wasm_const.py",
    "x86.py", "x86_const.py", "xcore.py", "xcore_const.py",
)
CAPSTONE_RUNTIME_DIRECTORY = Path("tools/_vendor/capstone")

RUNTIME_DEPENDENCY_PATHS = tuple(
    Path(item)
    for item in (
        "tools/export_rom_cfg_inventory.py",
        "tools/export_rom_cfg_proven_roots.py",
        "tools/export_rom_cfg_proven_roots_v2.py",
        "tools/verify_rom_cfg_inventory.py",
        "tools/verify_rom_cfg_inventory_v3.py",
        "tools/verify_rom_cfg_seeds.py",
        "tools/verify_similar_table_candidates.py",
        "tools/verify_rom_cfg_proven_roots.py",
        "tools/verify_rom_cfg_proven_roots_v2.py",
        "tools/verify_rom_cfg_proven_roots_v3.py",
        "tools/verify_rom_cfg_proven_roots_v4.py",
        "tools/verify_rom_cfg_proven_roots_v5.py",
        "tools/verify_rom_cfg_proven_roots_v6.py",
        "tools/verify_rom_cfg_proven_roots_v7.py",
        "tools/verify_rom_cfg_proven_roots_v8.py",
        "tools/verify_rom_battle_controller_cfg.py",
    )
) + tuple(CAPSTONE_RUNTIME_DIRECTORY / name for name in CAPSTONE_RUNTIME_PYTHON_NAMES) + (
    Path("tools/_vendor/capstone/lib/libcapstone.dylib"),
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode_thumb_bl(callsite: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return callsite + 4 + displacement


def _producer_denominator(rom: bytes) -> dict[str, Any]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    targets = {item[4] for item in EXPECTED_PRODUCERS}
    actual = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        target = _decode_thumb_bl(offset, first, second)
        if target in targets:
            actual.append((offset, target))
    expected = [(item[1], item[4]) for item in EXPECTED_PRODUCERS]
    if actual != expected:
        raise ValueError("direct-BL producer denominator changed")
    records = []
    for producer_id, offset, raw_hex, digest, target in EXPECTED_PRODUCERS:
        raw = rom[offset : offset + 4]
        if raw.hex() != raw_hex or _sha(raw) != digest:
            raise ValueError(f"producer bytes changed at 0x{offset:06X}")
        records.append(
            {
                "producer_id": producer_id,
                "file_offset": offset,
                "gba_address": f"0x{ROM_BASE + offset:08X}",
                "raw_hex": raw_hex,
                "bytes_sha256": digest,
                "target_file_offset": target,
                "target_gba_address": f"0x{ROM_BASE + target:08X}",
            }
        )
    return {
        "scan": {
            "mode": "thumb",
            "alignment_bytes": 2,
            "range": [0, len(rom)],
            "target_file_offsets": sorted(targets),
            "matching_producer_count": len(records),
        },
        "producers": records,
        "denominator_sha256": _canonical_sha(records),
    }


def _load_json(root: Path, relative: Path, digest: str) -> dict[str, Any]:
    raw = _safe_file(root, relative).read_bytes()
    if _sha(raw) != digest:
        raise ValueError(f"frozen payload identity changed: {relative.as_posix()}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"frozen payload is not an object: {relative.as_posix()}")
    return value


def _coverage_contract(
    root: Path, block_ranges: list[tuple[int, int]]
) -> dict[str, Any]:
    raw = _safe_file(root, COVERAGE_PATH).read_bytes()
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage identity changed")
    coverage = json.loads(raw)
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage schema changed")
    if coverage.get("base_rom") != {
        "path": ROM_PATH.as_posix(),
        "size": ROM_SIZE,
        "sha256": ROM_SHA256,
    }:
        raise ValueError("coverage ROM identity changed")
    if coverage.get("domain") != [0, ROM_SIZE]:
        raise ValueError("coverage domain changed")
    summary = coverage.get("summary")
    selected_summary = {
        key: summary.get(key) if isinstance(summary, dict) else None
        for key in EXPECTED_COVERAGE_SUMMARY
    }
    if selected_summary != EXPECTED_COVERAGE_SUMMARY:
        raise ValueError("coverage summary changed")
    segments = coverage.get("segments")
    if not isinstance(segments, list) or len(segments) != selected_summary["segment_count"]:
        raise ValueError("coverage segment denominator changed")
    normalized_segments: list[tuple[int, int, str]] = []
    cursor = 0
    classified = 0
    unknown = 0
    for segment in segments:
        bounds = segment.get("range") if isinstance(segment, dict) else None
        primary_class = segment.get("primary_class") if isinstance(segment, dict) else None
        if (
            not isinstance(bounds, list)
            or len(bounds) != 2
            or not all(isinstance(item, int) for item in bounds)
            or bounds[0] != cursor
            or bounds[1] <= bounds[0]
            or bounds[1] > ROM_SIZE
            or not isinstance(primary_class, str)
        ):
            raise ValueError("coverage segment partition changed")
        size = bounds[1] - bounds[0]
        if primary_class == "unknown":
            unknown += size
        else:
            classified += size
        normalized_segments.append((bounds[0], bounds[1], primary_class))
        cursor = bounds[1]
    if cursor != ROM_SIZE or {
        "classified_bytes": classified,
        "unknown_bytes": unknown,
    } != {
        "classified_bytes": selected_summary["classified_bytes"],
        "unknown_bytes": selected_summary["unknown_bytes"],
    }:
        raise ValueError("coverage byte accounting changed")
    ordered = sorted(block_ranges)
    if ordered != block_ranges or any(
        start < 0
        or end <= start
        or end > ROM_SIZE
        or (index and start < ordered[index - 1][1])
        for index, (start, end) in enumerate(ordered)
    ):
        raise ValueError("coverage promotion block ranges changed")
    unknown_bytes = 0
    known_bytes = 0
    for start, end in ordered:
        for segment_start, segment_end, primary_class in normalized_segments:
            overlap = max(0, min(end, segment_end) - max(start, segment_start))
            if not overlap:
                continue
            if primary_class == "unknown":
                unknown_bytes += overlap
            else:
                known_bytes += overlap
    instruction_bytes = sum(end - start for start, end in ordered)
    if unknown_bytes + known_bytes != instruction_bytes:
        raise ValueError("coverage does not account for all promotion bytes")
    if known_bytes:
        raise ValueError(f"coverage marks {known_bytes} v9 extension bytes as current known")
    range_vector = [list(item) for item in ordered]
    if (
        len(range_vector) != 62
        or instruction_bytes != 628
        or _canonical_sha(range_vector)
        != PROMOTION_BLOCK_RANGE_DENOMINATOR_SHA256
    ):
        raise ValueError("coverage promotion block range denominator changed")
    return {
        "path": COVERAGE_PATH.as_posix(),
        "sha256": COVERAGE_SHA256,
        "summary": selected_summary,
        "promotion_block_count": len(ordered),
        "promotion_instruction_bytes": instruction_bytes,
        "promotion_block_ranges": range_vector,
        "promotion_block_range_denominator_sha256": (
            PROMOTION_BLOCK_RANGE_DENOMINATOR_SHA256
        ),
        "current_unknown_bytes": unknown_bytes,
        "current_known_overlap_bytes": known_bytes,
    }


def _controller_entries(
    root: Path, rom: bytes, payload: dict[str, Any]
) -> tuple[dict[tuple[str, int], dict[str, Any]], dict[tuple[str, int], dict[str, Any]]]:
    blocks = payload.get("extension", {}).get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("controller extension blocks are missing")
    _, _, _, decoded = _verify_blocks(rom, blocks)
    return decoded, _owner_map(blocks, decoded)


def _controller_source_provenance_uncached(
    root_name: str, rom_digest: str
) -> dict[str, Any]:
    root = Path(root_name).resolve(strict=True)
    rom = _safe_file(root, ROM_PATH).read_bytes()
    if _sha(rom) != rom_digest:
        raise ValueError("controller provenance ROM identity changed")
    payload_raw = _safe_file(root, CONTROLLER_PAYLOAD).read_bytes()
    manifest_raw = _safe_file(root, CONTROLLER_ARTIFACT / MANIFEST_NAME).read_bytes()
    if _sha(payload_raw) != CONTROLLER_PAYLOAD_SHA256:
        raise ValueError("controller source payload identity changed")
    if _sha(manifest_raw) != CONTROLLER_MANIFEST_SHA256:
        raise ValueError("controller source manifest identity changed")
    payload = json.loads(payload_raw)
    manifest = json.loads(manifest_raw)
    if payload.get("schema") != "rom-battle-controller-cfg-v1":
        raise ValueError("controller source schema changed")
    if manifest.get("artifact_schema") != "rom-battle-controller-cfg-v1":
        raise ValueError("controller source manifest schema changed")
    from tools.verify_rom_battle_controller_cfg import verify_rom_battle_controller_cfg

    report = verify_rom_battle_controller_cfg(root, root / CONTROLLER_ARTIFACT)
    if report != EXPECTED_CONTROLLER_REPORT:
        raise ValueError(f"controller source independent verification failed: {report}")
    entries, owners = _controller_entries(root, rom, payload)
    denominator = _producer_denominator(rom)
    records = []
    for producer in denominator["producers"]:
        offset = producer["file_offset"]
        target = producer["target_file_offset"]
        item = dict(producer)
        if offset in EXCLUDED_PRODUCER_OFFSETS:
            if ("thumb", offset) in entries:
                raise ValueError("excluded producer is a controller decoded source")
            item.update(
                {
                    "provenance": "provenance_excluded",
                    "provenance_reason": "not_a_source_instruction_in_frozen_controller_cfg",
                }
            )
        else:
            source = entries.get(("thumb", offset))
            if source is None:
                raise ValueError(f"controller producer source missing: 0x{offset:06X}")
            matching = [
                edge
                for edge in payload["extension"]["opaque_edges"]
                if edge.get("source") == {"file_offset": offset, "mode": "thumb"}
                and edge.get("edge_kind") == "call_target"
                and edge.get("target_mode") == "thumb"
                and edge.get("target_file_offset") == target
                and edge.get("reason") == "outside_controller_range"
            ]
            if len(matching) != 1:
                raise ValueError(f"controller producer opaque edge changed: 0x{offset:06X}")
            item.update(
                {
                    "provenance": "controller",
                    "controller_source": {
                        "instruction_sha256": source["bytes_sha256"],
                        "opaque_edge": matching[0],
                    },
                }
            )
        records.append(item)
    if len([item for item in records if item["provenance"] == "controller"]) != 9:
        raise ValueError("controller producer provenance count changed")
    if len([item for item in records if item["provenance"] == "provenance_excluded"]) != 2:
        raise ValueError("excluded producer provenance count changed")
    return {
        "artifact": {
            "path": CONTROLLER_ARTIFACT.as_posix(),
            "payload_sha256": CONTROLLER_PAYLOAD_SHA256,
            "manifest_sha256": CONTROLLER_MANIFEST_SHA256,
            "verifier_path": CONTROLLER_VERIFIER.as_posix(),
            "verifier_sha256": CONTROLLER_VERIFIER_SHA256,
        },
        "verification": report,
        "controller_source_count": 9,
        "excluded_source_count": 2,
        "producers": records,
        "controller_entry_count": len(entries),
        "controller_owner_count": len(owners),
    }


def _controller_source_provenance(root: Path, rom: bytes) -> dict[str, Any]:
    return _controller_source_provenance_uncached(str(Path(root).resolve(strict=True)), _sha(rom))


def _root_seeds(
    rom: bytes, producers: dict[str, Any], provenance: dict[str, Any]
) -> list[dict[str, Any]]:
    by_target: dict[int, list[dict[str, str]]] = defaultdict(list)
    for producer in provenance["producers"]:
        if producer["provenance"] == "controller":
            by_target[producer["target_file_offset"]].append(
                {"producer_id": producer["producer_id"]}
            )
    roots = []
    for offset in sorted(ROOT_BYTES):
        raw_hex, digest = ROOT_BYTES[offset]
        raw = rom[offset : offset + 4]
        if raw.hex() != raw_hex or _sha(raw) != digest:
            raise ValueError(f"root bytes changed at 0x{offset:06X}")
        if offset not in by_target:
            raise ValueError(f"root has no controller producer source: 0x{offset:06X}")
        roots.append(
            {
                "root_id": f"root-thumb-{offset:06x}",
                "mode": "thumb",
                "file_offset": offset,
                "gba_address": f"0x{ROM_BASE + offset:08X}",
                "entry_size": 4,
                "entry_sha256": digest,
                "sources": by_target[offset],
            }
        )
    if len(roots) != 8:
        raise ValueError("direct-BL root denominator changed")
    return roots


def _payload_blocks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = payload.get("extension", {}).get("blocks")
    if blocks is None:
        blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("frozen baseline blocks are missing")
    return blocks


def _invoke_baseline_verifier(root: Path, label: str) -> dict[str, Any]:
    spec = next((item for item in BASELINE_SPECS if item[0] == label), None)
    if spec is None:
        raise ValueError(f"unknown baseline verifier label: {label}")
    artifact_dir = root / spec[1].parent
    if label == "v2":
        from tools.verify_rom_cfg_inventory import verify_rom_cfg_inventory as verify
    elif label == "v3":
        from tools.verify_rom_cfg_inventory_v3 import verify_rom_cfg_inventory_v3 as verify
    elif label == "proven_roots_v1":
        from tools.verify_rom_cfg_proven_roots import verify_rom_cfg_proven_roots as verify
    elif label == "proven_roots_v2":
        from tools.verify_rom_cfg_proven_roots_v2 import verify_rom_cfg_proven_roots_v2 as verify
    elif label == "battle_controller":
        from tools.verify_rom_battle_controller_cfg import verify_rom_battle_controller_cfg as verify
    elif label == "proven_roots_v3":
        from tools.verify_rom_cfg_proven_roots_v3 import verify_rom_cfg_proven_roots_v3 as verify
    elif label == "proven_roots_v4":
        from tools.verify_rom_cfg_proven_roots_v4 import verify_rom_cfg_proven_roots_v4 as verify
    elif label == "proven_roots_v5":
        from tools.verify_rom_cfg_proven_roots_v5 import verify_rom_cfg_proven_roots_v5 as verify
    elif label == "proven_roots_v6":
        from tools.verify_rom_cfg_proven_roots_v6 import verify_rom_cfg_proven_roots_v6 as verify
    elif label == "proven_roots_v7":
        from tools.verify_rom_cfg_proven_roots_v7 import verify_rom_cfg_proven_roots_v7 as verify
    elif label == "proven_roots_v8":
        from tools.verify_rom_cfg_proven_roots_v8 import verify_rom_cfg_proven_roots_v8 as verify
    else:
        raise ValueError(f"baseline verifier is not routed: {label}")
    return verify(root, artifact_dir)


def _baseline_verification_reports(root: Path) -> dict[str, dict[str, Any]]:
    reports = {}
    for label, *_ in BASELINE_SPECS:
        report = _invoke_baseline_verifier(root, label)
        expected = EXPECTED_BASELINE_REPORTS[label]
        if report != expected:
            raise ValueError(f"baseline independent verification failed for {label}: {report}")
        reports[label] = report
    if set(reports) != set(EXPECTED_BASELINE_REPORTS):
        raise ValueError("baseline verifier report denominator changed")
    return reports


def _baseline_record(
    root: Path,
    label: str,
    relative: Path,
    payload_digest: str,
    manifest_digest: str,
    schema: str,
    verifier_path: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    verifier_raw = _safe_file(root, verifier_path).read_bytes()
    return {
        "path": relative.parent.as_posix(),
        "payload_file": relative.name,
        "schema": schema,
        "payload_sha256": payload_digest,
        "manifest_sha256": manifest_digest,
        "verifier_path": verifier_path.as_posix(),
        "verifier_sha256": _sha(verifier_raw),
        "summary": payload.get("extension", {}).get("summary", payload.get("summary")),
    }


def _baseline_contract_uncached(
    root_name: str, rom_digest: str
) -> tuple[
    dict[str, dict[tuple[str, int], dict[str, Any]]],
    dict[str, dict[tuple[str, int], dict[str, Any]]],
    dict[str, dict[str, Any]],
]:
    root = Path(root_name).resolve(strict=True)
    rom = _safe_file(root, ROM_PATH).read_bytes()
    if _sha(rom) != rom_digest:
        raise ValueError("baseline ROM identity changed")
    verification_reports = _baseline_verification_reports(root)

    entries: dict[str, dict[tuple[str, int], dict[str, Any]]] = {}
    owners: dict[str, dict[tuple[str, int], dict[str, Any]]] = {}
    frozen: dict[str, dict[str, Any]] = {}
    for label, relative, payload_digest, manifest_digest, schema, verifier_path in BASELINE_SPECS:
        payload = _load_json(root, relative, payload_digest)
        manifest_path = relative.parent / MANIFEST_NAME
        manifest_raw = _safe_file(root, manifest_path).read_bytes()
        if _sha(manifest_raw) != manifest_digest:
            raise ValueError(f"frozen baseline manifest identity changed: {label}")
        if payload.get("schema") != schema:
            raise ValueError(f"frozen baseline schema changed: {label}")
        blocks = _payload_blocks(payload)
        _, _, _, decoded = _verify_blocks(rom, blocks)
        entries[label] = decoded
        owners[label] = _owner_map(blocks, decoded)
        frozen[label] = _baseline_record(
            root, label, relative, payload_digest, manifest_digest, schema, verifier_path, payload
        )
    if set(frozen) != {item[0] for item in BASELINE_SPECS}:
        raise ValueError("frozen baseline set changed")
    occupied: set[int] = set()
    for label, decoded in entries.items():
        current = {
            byte
            for (_, offset), node in decoded.items()
            for byte in range(offset, offset + node["size"])
        }
        if occupied & current:
            raise ValueError(f"frozen baseline bytes overlap at {label}")
        occupied.update(current)
    frozen["verification_chain"] = {
        "report_count": len(verification_reports),
        "reports": verification_reports,
    }
    return entries, owners, frozen


def _baseline_contract(root: Path, rom: bytes):
    return _baseline_contract_uncached(str(Path(root).resolve(strict=True)), _sha(rom))


def _in_promotion_range(start: int, end: int | None = None) -> bool:
    finish = start if end is None else end
    return any(left <= start and finish <= right for left, right in PROMOTION_RANGES)


def _validate_return_exit(rom: bytes, offset: int, prefix: str) -> dict[str, Any]:
    if offset < 2 or rom[offset - 2 : offset + 2].hex() != prefix:
        raise ValueError(f"return exit bytes changed at 0x{offset:06X}")
    pop_halfword, bx_halfword = struct.unpack_from("<HH", rom, offset - 2)
    pop_mask = pop_halfword & 0xFF
    if pop_halfword & 0xFF00 != 0xBC00 or pop_mask == 0 or pop_mask & (pop_mask - 1):
        raise ValueError(f"return exit pop idiom changed at 0x{offset:06X}")
    pop_register = pop_mask.bit_length() - 1
    if bx_halfword & 0xFF87 != 0x4700:
        raise ValueError(f"return exit bx idiom changed at 0x{offset:06X}")
    bx_register = (bx_halfword >> 3) & 0xF
    if bx_register != pop_register:
        raise ValueError(f"return exit register mismatch at 0x{offset:06X}")
    return {
        "file_offset": offset,
        "mode": "thumb",
        "prefix_raw_hex": prefix,
        "prefix_sha256": _sha(rom[offset - 2 : offset + 2]),
        "pop_register": f"r{pop_register}",
        "bx_register": f"r{bx_register}",
        "register": f"r{pop_register}",
    }


def _normalize_return_exit(rom: bytes, offset: int, node: dict[str, Any]) -> dict[str, Any]:
    prefix = RETURN_EXIT_PREFIXES.get(offset)
    if prefix is None:
        return node
    _validate_return_exit(rom, offset, prefix)
    if not node.get("accepted") or node.get("mnemonic") != "bx":
        raise ValueError(f"return exit instruction changed at 0x{offset:06X}")
    normalized = dict(node)
    normalized["successors"] = []
    normalized["frontiers"] = []
    return normalized


def _traverse_bounded_roots(
    rom: bytes,
    roots: list[dict[str, Any]],
    baseline_nodes: dict[str, dict[tuple[str, int], dict[str, Any]]],
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], list[tuple[tuple[str, int], str]]],
    list[tuple[tuple[str, int], str, str, tuple[str, int]]],
]:
    occupied = {
        byte
        for records in baseline_nodes.values()
        for (_, offset), node in records.items()
        for byte in range(offset, offset + node["size"])
    }
    pending: list[tuple[int, int, str]] = []
    scheduled: set[tuple[str, int]] = set()
    for root in roots:
        item = (root["mode"], root["file_offset"])
        if item[0] != "thumb" or not _in_promotion_range(item[1]):
            raise ValueError("root is outside promotion ranges")
        if item in {key for value in baseline_nodes.values() for key in value} or item[1] in occupied:
            raise ValueError("root overlaps frozen baseline entry or byte")
        heapq.heappush(pending, _key(*item))
        scheduled.add(item)
    nodes: dict[tuple[str, int], dict[str, Any]] = {}
    rejected: dict[tuple[str, int], dict[str, Any]] = {}
    incoming: dict[tuple[str, int], list[tuple[tuple[str, int], str]]] = defaultdict(list)
    crosses: list[tuple[tuple[str, int], str, str, tuple[str, int]]] = []
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in nodes or item in rejected:
            continue
        if offset in occupied:
            raise ValueError("bounded traversal entered frozen baseline middle")
        decoded = _decode_one(rom, offset, mode)
        if not decoded["accepted"]:
            rejected[item] = decoded
            continue
        decoded = _normalize_return_exit(rom, offset, decoded)
        end = offset + decoded["size"]
        if not _in_promotion_range(offset, end):
            raise ValueError("instruction escapes or straddles promotion range")
        if any(byte in occupied for byte in range(offset, end)):
            raise ValueError("instruction straddles frozen baseline bytes")
        if len(nodes) >= MAX_INSTRUCTION_COUNT:
            raise ValueError("bounded CFG instruction budget exhausted")
        nodes[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            matched = [label for label, records in baseline_nodes.items() if target in records]
            if len(matched) > 1:
                raise ValueError("baseline target is ambiguous")
            if matched:
                crosses.append((item, edge["kind"], matched[0], target))
                continue
            if target[1] in occupied:
                raise ValueError("successor targets baseline middle or straddle")
            if target[0] != "thumb" or not _in_promotion_range(target[1]):
                raise ValueError("successor escaped promotion ranges")
            incoming[target].append((item, edge["kind"]))
            if target not in scheduled:
                heapq.heappush(pending, _key(*target))
                scheduled.add(target)
    _assert_nonoverlapping_nodes(nodes)
    return nodes, rejected, incoming, crosses


def _loaded_capstone_identity() -> dict[str, Any]:
    if os.environ.get("LIBCAPSTONE_PATH"):
        raise ValueError("LIBCAPSTONE_PATH must be empty")
    modules: dict[str, str] = {}
    for name in CAPSTONE_RUNTIME_PYTHON_NAMES:
        module_name = "capstone" if name == "__init__.py" else f"capstone.{name[:-3]}"
        module = capstone if module_name == "capstone" else sys.modules.get(module_name)
        loaded = getattr(module, "__file__", None)
        if not loaded:
            raise ValueError(f"loaded Capstone module missing: {module_name}")
        if Path(loaded).resolve(strict=True) != (PROJECT_ROOT / CAPSTONE_RUNTIME_DIRECTORY / name).resolve(strict=True):
            raise ValueError(f"loaded Capstone module is not vendored: {module_name}")
        modules[module_name] = (CAPSTONE_RUNTIME_DIRECTORY / name).as_posix()
    loaded_library = getattr(getattr(capstone, "_cs", None), "_name", None)
    expected_library = PROJECT_ROOT / "tools/_vendor/capstone/lib/libcapstone.dylib"
    if not loaded_library or Path(loaded_library).resolve(strict=True) != expected_library.resolve(strict=True):
        raise ValueError("loaded Capstone dynamic library is not vendored")
    return {
        "python_modules": modules,
        "dynamic_library": "tools/_vendor/capstone/lib/libcapstone.dylib",
        "libcapstone_path_environment": None,
    }


def _implementation(root: Path) -> dict[str, Any]:
    paths = {
        "exporter": Path("tools/export_rom_cfg_proven_roots_v9.py"),
        "verifier": Path("tools/verify_rom_cfg_proven_roots_v9.py"),
        "test": Path("tests/test_export_rom_cfg_proven_roots_v9.py"),
    }
    for checked_root in (Path(root), PROJECT_ROOT):
        names = tuple(sorted(path.name for path in (checked_root / CAPSTONE_RUNTIME_DIRECTORY).glob("*.py")))
        if names != tuple(sorted(CAPSTONE_RUNTIME_PYTHON_NAMES)):
            raise ValueError("Capstone runtime Python dependency denominator changed")
    digests: dict[str, str] = {}
    for relative in RUNTIME_DEPENDENCY_PATHS:
        passed = _safe_file(root, relative).read_bytes()
        loaded = _safe_file(PROJECT_ROOT, relative).read_bytes()
        if passed != loaded:
            raise ValueError(f"loaded implementation differs from passed root: {relative.as_posix()}")
        digests[relative.as_posix()] = _sha(passed)
    for relative in paths.values():
        passed = _safe_file(root, relative).read_bytes()
        loaded = _safe_file(PROJECT_ROOT, relative).read_bytes()
        if passed != loaded:
            raise ValueError(f"loaded implementation differs from passed root: {relative.as_posix()}")
    return {
        "binding": "passed-root-equals-loaded-runtime-dependency-denominator-with-isolated-cli",
        "paths": {label: value.as_posix() for label, value in paths.items()},
        "exporter_sha256": _sha(_safe_file(root, paths["exporter"]).read_bytes()),
        "verifier_sha256": _sha(_safe_file(root, paths["verifier"]).read_bytes()),
        "test_sha256": _sha(_safe_file(root, paths["test"]).read_bytes()),
        "runtime_dependency_sha256": digests,
        "loaded_runtime": _loaded_capstone_identity(),
        "execution_isolation": {
            "python_flags": ["-I", "-S"],
            "verifier_command": ["python3", "-I", "-S", "tools/verify_rom_cfg_proven_roots_v9.py"],
            "preimport_checks": ["isolated-runtime", "no-site", "capstone-not-preloaded", "libcapstone-path-empty"],
        },
    }


def _frozen_baseline_payloads(frozen: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {label: frozen[label] for label, *_ in BASELINE_SPECS}
    result["verification_chain"] = frozen["verification_chain"]
    return result


def build_cfg_proven_roots_v9_payload(root: Path, rom: bytes | None = None) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    rom = _safe_file(root, ROM_PATH).read_bytes() if rom is None else rom
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    producers = _producer_denominator(rom)
    provenance = _controller_source_provenance(root, rom)
    producers_with_provenance = provenance["producers"]
    roots = _root_seeds(rom, producers, provenance)
    baseline_nodes, baseline_owners, frozen = _baseline_contract(root, rom)
    nodes, rejected, incoming, crosses = _traverse_bounded_roots(rom, roots, baseline_nodes)
    if rejected:
        raise ValueError(f"v9 closure has unresolved frontier entries: {sorted(rejected)}")
    blocks, node_to_block = _build_blocks(rom, nodes, {(root_item["mode"], root_item["file_offset"]) for root_item in roots})
    frontiers = _frontier_records(nodes, rejected, incoming, roots, node_to_block)
    cross_records, cross_vector = _cross_edge_records(crosses, node_to_block, baseline_owners)
    summary = _extension_summary(nodes, blocks, frontiers)
    expected_summary = {
        "decoded_basic_block_count": 62,
        "decoded_instruction_count": 299,
        "frontier_count": 0,
        "frontier_reasons": {},
        "reachable_instruction_bytes": 628,
    }
    if summary != expected_summary:
        raise ValueError(f"v9 CFG closure denominator changed: {summary}")
    if len(cross_vector) != 16:
        raise ValueError("v9 baseline cross-edge denominator changed")
    if _canonical_sha(cross_vector) != "a2a75f2aa14da225f62474a336cb573896528209887ac71a46b5c06a503f1140":
        raise ValueError("v9 cross-edge vector changed")
    return_exits = [_validate_return_exit(rom, offset, prefix) for offset, prefix in RETURN_EXIT_PREFIXES.items() if ("thumb", offset) in nodes]
    if len(return_exits) != 7:
        raise ValueError("v9 return-exit denominator changed")
    coverage_baseline = _coverage_contract(
        root, [tuple(block["range"]) for block in blocks]
    )
    if coverage_baseline["promotion_block_count"] != 62 or coverage_baseline[
        "promotion_instruction_bytes"
    ] != 628:
        raise ValueError("v9 coverage promotion denominator changed")
    occupied = {
        byte
        for values in baseline_nodes.values()
        for (_, offset), node in values.items()
        for byte in range(offset, offset + node["size"])
    }
    current = {
        byte
        for (_, offset), node in nodes.items()
        for byte in range(offset, offset + node["size"])
    }
    overlap = occupied & current
    if overlap:
        raise ValueError("v9 closure overlaps current-known baseline bytes")
    scope = dict(SCOPE)
    scope["current_known_overlap_bytes"] = len(overlap)
    source = {
        "controller_cfg": provenance["artifact"],
        "verification": provenance["verification"],
        "provenance_summary": {
            "full_producer_count": len(producers_with_provenance),
            "controller_source_count": provenance["controller_source_count"],
            "excluded_source_count": provenance["excluded_source_count"],
            "excluded_reason": "not_a_source_instruction_in_frozen_controller_cfg",
        },
    }
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "source": source,
        "frozen_baseline": _frozen_baseline_payloads(frozen),
        "producer_denominator": {
            "scan": producers["scan"],
            "producers": producers_with_provenance,
            "denominator_sha256": _canonical_sha(producers_with_provenance),
        },
        "roots": _root_results(roots, nodes, frontiers, node_to_block),
        "extension": {
            "blocks": blocks,
            "frontiers": frontiers,
            "baseline_cross_edges": cross_records,
            "cross_edge_denominator_sha256": _canonical_sha(cross_vector),
            "opaque_return_exits": return_exits,
            "summary": summary,
        },
        "coverage_baseline": coverage_baseline,
        "promotion": {
            "ranges": [list(item) for item in PROMOTION_RANGES],
            "current_known_overlap_bytes": len(overlap),
        },
        "implementation": _implementation(root),
        "scope": scope,
    }


def _receipt_commands(root: Path, output: Path) -> tuple[list[str], list[str]]:
    relative_output = output.resolve(strict=False).relative_to(root).as_posix()
    producer = [
        "python3",
        "-I",
        "-S",
        EXPORTER_PATH.as_posix(),
        "--root",
        ".",
        "--output-dir",
        relative_output,
    ]
    verifier = [
        "python3",
        "-I",
        "-S",
        VERIFIER_PATH.as_posix(),
        "--root",
        ".",
        "--artifact-dir",
        relative_output,
    ]
    return producer, verifier


def _promotion_manifest(
    root: Path,
    output: Path,
    payload: dict[str, Any],
    payload_raw: bytes,
    *,
    status: str,
    report: dict[str, Any] | None,
) -> dict[str, Any]:
    if status not in {"candidate", "accepted"}:
        raise ValueError("invalid CFG v9 promotion status")
    if (status == "accepted") != (report is not None):
        raise ValueError("CFG v9 verifier receipt/status mismatch")
    producer_command, verifier_command = _receipt_commands(root, output)
    implementation = payload["implementation"]
    return {
        "schema": PROMOTION_SCHEMA,
        "artifact_schema": SCHEMA,
        "artifact_status": status,
        "rom": payload["rom"],
        "source": payload["source"],
        "frozen_baseline": payload["frozen_baseline"],
        "producer_summary": {
            "count": len(payload["producer_denominator"]["producers"]),
            "controller_source_count": 9,
            "excluded_source_count": 2,
            "denominator_sha256": payload["producer_denominator"][
                "denominator_sha256"
            ],
        },
        "root_count": len(payload["roots"]),
        "coverage_baseline": payload["coverage_baseline"],
        "promotion": payload["promotion"],
        "extension_summary": payload["extension"]["summary"],
        "baseline_cross_edge_count": len(
            payload["extension"]["baseline_cross_edges"]
        ),
        "opaque_return_exit_count": len(
            payload["extension"]["opaque_return_exits"]
        ),
        "files": {PAYLOAD_NAME: _sha(payload_raw)},
        "producer": {
            "command": producer_command,
            "implementation": implementation,
        },
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
    completed = subprocess.run(
        command,
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(
            f"independent CFG v9 verifier rejected candidate: {detail}"
        )
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("independent CFG v9 verifier returned invalid JSON") from error
    if report != EXPECTED_VERIFIER_REPORT:
        raise ValueError(
            f"independent CFG v9 verifier report changed: {report}"
        )
    return report


def _write_manifest_atomic(output: Path, manifest: dict[str, Any]) -> None:
    temporary = output / f".{MANIFEST_NAME}.{uuid.uuid4().hex}.tmp"
    try:
        temporary.write_bytes(_canonical_json(manifest))
        os.replace(temporary, output / MANIFEST_NAME)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_output_dir(root: Path, output_dir: Path) -> Path:
    root = Path(root).resolve(strict=True)
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    target = _reject_symlink_components(requested).resolve(strict=False)
    allowed = (root / EXPERIMENT_OUTPUT_ROOT).resolve(strict=False)
    if target != allowed and allowed not in target.parents:
        raise ValueError("CFG v9 output must stay inside the experiment subtree")
    if target == root or target in root.parents:
        raise ValueError("CFG v9 output cannot be repository root or ancestor")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("CFG v9 output is not a directory")
    members = list(target.iterdir())
    if not members:
        return target
    if {item.name for item in members} != {MANIFEST_NAME, PAYLOAD_NAME} or any(item.is_symlink() or not item.is_file() for item in members):
        raise ValueError("CFG v9 output is a foreign non-empty directory")
    from tools.verify_rom_cfg_proven_roots_v9 import verify_rom_cfg_proven_roots_v9

    report = verify_rom_cfg_proven_roots_v9(root, target)
    if not report.get("verified"):
        raise ValueError(f"existing same-schema v9 output failed independent verification: {report.get('errors', [])}")
    return target


def export_rom_cfg_proven_roots_v9(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output = _validate_output_dir(root, output_dir)
    payload = build_cfg_proven_roots_v9_payload(root)
    payload_raw = _canonical_json(payload)
    candidate = _promotion_manifest(
        root, output, payload, payload_raw, status="candidate", report=None
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".rom-cfg-proven-roots-v9-", dir=output.parent))
    backup: Path | None = None
    committed = False
    try:
        (temporary / PAYLOAD_NAME).write_bytes(payload_raw)
        (temporary / MANIFEST_NAME).write_bytes(_canonical_json(candidate))
        if output.exists():
            backup = output.with_name(f".{output.name}.old-{uuid.uuid4().hex}")
            os.replace(output, backup)
        os.replace(temporary, output)
        report = _run_isolated_verifier(
            root, candidate["verifier"]["command"]
        )
        accepted = _promotion_manifest(
            root, output, payload, payload_raw, status="accepted", report=report
        )
        _write_manifest_atomic(output, accepted)
        postflight_report = _run_isolated_verifier(
            root, accepted["verifier"]["command"]
        )
        if postflight_report != report:
            raise ValueError("accepted CFG v9 verifier report changed")
        committed = True
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
        return accepted
    except BaseException:
        if not committed:
            failed: Path | None = None
            if output.exists():
                failed = output.with_name(
                    f".{output.name}.failed-{uuid.uuid4().hex}"
                )
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
    manifest = export_rom_cfg_proven_roots_v9(args.root, args.output_dir)
    print(json.dumps(manifest["extension_summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
