#!/usr/bin/env python3
"""Independently verify the battle-controller direct-BL CFG v9 packet."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import heapq
import json
import os
from pathlib import Path
import struct
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
_CLEAN_CLI_STARTUP_CONFIRMED = False


def _require_isolated_cli_runtime() -> None:
    global _CLEAN_CLI_STARTUP_CONFIRMED
    if __name__ != "__main__":
        return
    if not sys.flags.isolated or not sys.flags.no_site:
        raise RuntimeError("CFG v9 verifier requires Python -I -S isolation")
    if "capstone" in sys.modules:
        raise RuntimeError("CFG v9 verifier rejects preloaded Capstone modules")
    if os.environ.get("LIBCAPSTONE_PATH"):
        raise RuntimeError("CFG v9 verifier rejects LIBCAPSTONE_PATH overrides")
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
    _build_blocks,
    _canonical_sha,
    _decode_one,
    _frontier_records,
    _key,
    _safe_file,
    _root_results,
)
from tools.export_rom_cfg_proven_roots_v2 import _cross_edge_records, _extension_summary
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
COVERAGE_SHA256 = "2ff9bc857e182c4bfeeaa572929569801549765ef1d3566cf10c17334125b9d1"
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
CONTROLLER_PAYLOAD_SHA256 = "c8b1d1c2068d85912ede1fd35be31f0cf9cb43943beb10f1058d43c65c00449a"
CONTROLLER_MANIFEST_SHA256 = "282b4323bf965676a68b5326f2edbbdee35606b987412d351de137b82d50fe63"
CONTROLLER_VERIFIER = Path("tools/verify_rom_battle_controller_cfg.py")
CONTROLLER_VERIFIER_SHA256 = "fc3c33d37b9fb2af885324915f82e3c0da74b3efd25967b8289b49d8b9169a87"

EXPECTED_CONTROLLER_REPORT = {
    "controller_range": [471732, 479388],
    "controller_sha256": "c9bdc220590a851fa331960bcb32be90eb9ac7248a5cd3dabb9f8afa0b674bc1",
    "dispatcher_default_state_count": 65498,
    "dispatcher_nondefault_state_count": 38,
    "errors": [],
    "root_count": 38,
    "schema": "rom-battle-controller-cfg-verification-v1",
    "summary": {
        "decoded_basic_block_count": 739,
        "decoded_instruction_count": 2756,
        "frontier_count": 5,
        "frontier_reasons": {"decode_failure": 1, "indirect_pc_target": 2, "unsupported_armv4t_instruction": 2},
        "opaque_baseline_edge_count": 9,
        "opaque_external_edge_count": 227,
        "reachable_instruction_bytes": 6172,
        "skipped_root_count": 1,
    },
    "verified": True,
}

BASELINE_SPECS = (
    ("v2", Path("artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json"), "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd", "ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753", "rom-cfg-inventory-v2", Path("tools/verify_rom_cfg_inventory.py")),
    ("v3", Path("artifacts/rom-cfg-inventory-v3/rom-cfg-inventory-v3.json"), "596c4d8cffa57f3899858a0a59351894b1398006ee0405ce799ed9f32a81bf9d", "6aa788611f73856e621f5c74aab544d47b034307a9dc1180f6fd8f81cb1f423b", "rom-cfg-inventory-v3", Path("tools/verify_rom_cfg_inventory_v3.py")),
    ("proven_roots_v1", Path("artifacts/rom-cfg-proven-roots-v1/rom-cfg-proven-roots.json"), "7fdee7d0d62d3a8c82bfe7b03804e9cb0e3d213ebdf63acce6b0533045aecf54", "ea1230fe24cf111a91044c059468a1467e46c471363780b23c2a0311bab8644a", "rom-cfg-proven-roots-v1", Path("tools/verify_rom_cfg_proven_roots.py")),
    ("proven_roots_v2", Path("artifacts/rom-cfg-proven-roots-v2/rom-cfg-proven-roots-v2.json"), "a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba", "a3683f3d21ec5a162b4cdb97c70b639ff261d9ff5e0f3bb4941848205bb4d9ca", "rom-cfg-proven-roots-v2", Path("tools/verify_rom_cfg_proven_roots_v2.py")),
    ("battle_controller", CONTROLLER_PAYLOAD, CONTROLLER_PAYLOAD_SHA256, CONTROLLER_MANIFEST_SHA256, "rom-battle-controller-cfg-v1", CONTROLLER_VERIFIER),
    ("proven_roots_v3", Path("artifacts/rom-cfg-proven-roots-v3/rom-cfg-proven-roots-v3.json"), "f2de5ca57685e3542d5e483e5a171a30eb32bb6dc6ce9794cc683371579af9a2", "4aa979aa65408163e577f7d728ba32a99a13bd6c9615c40f28a570036e5ba275", "rom-cfg-proven-roots-v3", Path("tools/verify_rom_cfg_proven_roots_v3.py")),
    ("proven_roots_v4", Path("artifacts/rom-cfg-proven-roots-v4/rom-cfg-proven-roots-v4.json"), "d14c9f4198d9209d03d8511351b5dc997ade409a3218e9f05993c8c7f11456eb", "e306ac59b4b9a815702fda8aef54058908fb9113a5afad4be938c69d42d67404", "rom-cfg-proven-roots-v4", Path("tools/verify_rom_cfg_proven_roots_v4.py")),
    ("proven_roots_v5", Path("artifacts/rom-cfg-proven-roots-v5/rom-cfg-proven-roots-v5.json"), "680b03dffb5c3dbbca41d9a5d0872db560a1a05850d7928ce75243397a54f040", "f6deb37d40ae4ea83e220adc8303c64646a9280d34d6c325d8ea0492963dcd8d", "rom-cfg-proven-roots-v5", Path("tools/verify_rom_cfg_proven_roots_v5.py")),
    ("proven_roots_v6", Path("artifacts/rom-cfg-proven-roots-v6/rom-cfg-proven-roots-v6.json"), "e5b27a55c77cd1df4ac5ec39f2dd05735b0b53c01b7cbbcf1620db1681a3c3ec", "e00d8a1b7b08305a44f7ac3d36a5e294d1f69b5f05ceab151e14749cf92802f4", "rom-cfg-proven-roots-v6", Path("tools/verify_rom_cfg_proven_roots_v6.py")),
    ("proven_roots_v7", Path("artifacts/rom-cfg-proven-roots-v7/rom-cfg-proven-roots-v7.json"), "184e9b84df829fb1ad41f272aabe931c1a1f86111eebd60629ad2d2a23d89a06", "da9a1b5fe7ce8e7889fbba9fe8251c907ed18f6b273cbcc3be145101ece99114", "rom-cfg-proven-roots-v7", Path("tools/verify_rom_cfg_proven_roots_v7.py")),
    ("proven_roots_v8", Path("artifacts/rom-cfg-proven-roots-v8/rom-cfg-proven-roots-v8.json"), "5fa1150d2ed9f785d50132a9eae316af192d70838fbee3061d7d3010c35fb1d6", "0c9194507c50b7f2c00c6ee09b517211f64b7b344475952fe3c908b1e54e0002", "rom-cfg-proven-roots-v8", Path("tools/verify_rom_cfg_proven_roots_v8.py")),
)

EXPECTED_BASELINE_REPORTS = {
    "v2": {
        "schema": "rom-cfg-inventory-verification-v2", "verified": True,
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 40_872, "root_count": 263,
        "decoded_instruction_count": 40_872, "decoded_basic_block_count": 7_725,
        "reachable_instruction_bytes": 86_184, "frontier_count": 366,
        "closed_root_count": 4, "frontier_open_root_count": 259,
        "budget_exhausted": False, "errors": [],
    },
    "v3": {
        "schema": "rom-cfg-inventory-verification-v3", "verified": True,
        "control_flow_oracle": "armv4t-raw-encoding", "resolved_frontier_count": 29,
        "new_entry_seed_count": 101, "independently_rebuilt_instruction_count": 4_698,
        "decoded_basic_block_count": 891, "reachable_instruction_bytes": 9_902,
        "frontier_count": 16, "errors": [],
    },
    "proven_roots_v1": {
        "schema": "rom-cfg-proven-roots-verification-v1", "verified": True,
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 6_166, "root_count": 2,
        "decoded_instruction_count": 6_166, "decoded_basic_block_count": 1_203,
        "reachable_instruction_bytes": 12_966, "frontier_count": 28,
        "baseline_cross_edge_count": 259, "errors": [],
    },
    "proven_roots_v2": {
        "schema": "rom-cfg-proven-roots-verification-v2", "verified": True,
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 4_809, "root_count": 3,
        "decoded_instruction_count": 4_809, "decoded_basic_block_count": 835,
        "reachable_instruction_bytes": 9_876, "frontier_count": 28,
        "baseline_cross_edge_count": 82, "errors": [],
    },
    "battle_controller": EXPECTED_CONTROLLER_REPORT,
    "proven_roots_v3": {
        "schema": "rom-cfg-proven-roots-verification-v3", "verified": True,
        "errors": [], "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 52, "root_count": 1,
        "decoded_instruction_count": 52, "decoded_basic_block_count": 8,
        "reachable_instruction_bytes": 110, "frontier_count": 0,
        "baseline_cross_edge_count": 5,
    },
    "proven_roots_v4": {
        "schema": "rom-cfg-proven-roots-verification-v4", "verified": True,
        "errors": [], "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 486, "root_count": 1,
        "decoded_instruction_count": 486, "decoded_basic_block_count": 118,
        "reachable_instruction_bytes": 1_044, "frontier_count": 6,
        "baseline_cross_edge_count": 29,
    },
    "proven_roots_v5": {
        "schema": "rom-cfg-proven-roots-verification-v5", "verified": True,
        "errors": [], "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 576, "root_count": 3,
        "decoded_instruction_count": 576, "decoded_basic_block_count": 124,
        "reachable_instruction_bytes": 1_252, "frontier_count": 8,
        "baseline_cross_edge_count": 40,
    },
    "proven_roots_v6": {
        "schema": "rom-cfg-proven-roots-verification-v6", "verified": True,
        "errors": [], "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 12_564, "root_count": 5,
        "decoded_instruction_count": 12_564, "decoded_basic_block_count": 2_305,
        "reachable_instruction_bytes": 27_224, "frontier_count": 85,
        "baseline_cross_edge_count": 916,
    },
    "proven_roots_v7": {
        "schema": "rom-cfg-proven-roots-verification-v7", "verified": True,
        "errors": [], "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 155, "root_count": 8,
        "decoded_instruction_count": 155, "decoded_basic_block_count": 38,
        "reachable_instruction_bytes": 332, "frontier_count": 1,
        "baseline_cross_edge_count": 17,
    },
    "proven_roots_v8": {
        "schema": "rom-cfg-proven-roots-verification-v8", "verified": True,
        "errors": [], "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 113, "root_count": 1,
        "decoded_instruction_count": 113, "decoded_basic_block_count": 20,
        "reachable_instruction_bytes": 246, "frontier_count": 1,
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
    (0x06C010, 0x06C09E), (0x06C308, 0x06C364), (0x06C40C, 0x06C418),
    (0x06D46C, 0x06D49A), (0x070DD8, 0x070DEE), (0x073000, 0x073048),
    (0x075350, 0x0753F2), (0x0753F8, 0x075436), (0x07543C, 0x07544E),
)
RETURN_EXIT_PREFIXES = {0x06C09C: "01bc0047", 0x06C362: "01bc0047", 0x06D498: "01bc0047", 0x070DEC: "01bc0047", 0x073046: "01bc0047", 0x0753F0: "01bc0047", 0x07544C: "02bc0847"}
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
CAPSTONE_RUNTIME_PYTHON_NAMES = ("__init__.py", "arm.py", "arm64.py", "arm64_const.py", "arm_const.py", "bpf.py", "bpf_const.py", "evm.py", "evm_const.py", "m680x.py", "m680x_const.py", "m68k.py", "m68k_const.py", "mips.py", "mips_const.py", "mos65xx.py", "mos65xx_const.py", "ppc.py", "ppc_const.py", "riscv.py", "riscv_const.py", "sh.py", "sh_const.py", "sparc.py", "sparc_const.py", "systemz.py", "sysz_const.py", "tms320c64x.py", "tms320c64x_const.py", "tricore.py", "tricore_const.py", "wasm.py", "wasm_const.py", "x86.py", "x86_const.py", "xcore.py", "xcore_const.py")
CAPSTONE_RUNTIME_DIRECTORY = Path("tools/_vendor/capstone")
RUNTIME_DEPENDENCY_PATHS = tuple(Path(item) for item in ("tools/export_rom_cfg_inventory.py", "tools/export_rom_cfg_proven_roots.py", "tools/export_rom_cfg_proven_roots_v2.py", "tools/verify_rom_cfg_inventory.py", "tools/verify_rom_cfg_inventory_v3.py", "tools/verify_rom_cfg_seeds.py", "tools/verify_similar_table_candidates.py", "tools/verify_rom_cfg_proven_roots.py", "tools/verify_rom_cfg_proven_roots_v2.py", "tools/verify_rom_cfg_proven_roots_v3.py", "tools/verify_rom_cfg_proven_roots_v4.py", "tools/verify_rom_cfg_proven_roots_v5.py", "tools/verify_rom_cfg_proven_roots_v6.py", "tools/verify_rom_cfg_proven_roots_v7.py", "tools/verify_rom_cfg_proven_roots_v8.py", "tools/verify_rom_battle_controller_cfg.py")) + tuple(CAPSTONE_RUNTIME_DIRECTORY / name for name in CAPSTONE_RUNTIME_PYTHON_NAMES) + (Path("tools/_vendor/capstone/lib/libcapstone.dylib"),)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


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
        raise ValueError("independent direct-BL producer denominator changed")
    records = []
    for producer_id, offset, raw_hex, digest, target in EXPECTED_PRODUCERS:
        raw = rom[offset : offset + 4]
        if raw.hex() != raw_hex or _sha(raw) != digest:
            raise ValueError(f"independent producer bytes changed at 0x{offset:06X}")
        records.append({"producer_id": producer_id, "file_offset": offset, "gba_address": f"0x{ROM_BASE + offset:08X}", "raw_hex": raw_hex, "bytes_sha256": digest, "target_file_offset": target, "target_gba_address": f"0x{ROM_BASE + target:08X}"})
    return {"scan": {"mode": "thumb", "alignment_bytes": 2, "range": [0, len(rom)], "target_file_offsets": sorted(targets), "matching_producer_count": len(records)}, "producers": records, "denominator_sha256": _canonical_sha(records)}


def _load_json(root: Path, relative: Path, digest: str) -> dict[str, Any]:
    raw = _safe_file(root, relative).read_bytes()
    if _sha(raw) != digest:
        raise ValueError(f"independent frozen payload identity changed: {relative}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("independent frozen payload is not an object")
    return value


def _frozen_coverage_contract(
    block_ranges: list[tuple[int, int]],
) -> dict[str, Any]:
    """Rebuild the frozen pre-v9 observation without reading live coverage.

    Candidate export verifies the original coverage file and records its exact
    identity.  Artifact verification instead derives this compact receipt from
    the independently rebuilt CFG blocks, so later coverage promotion cannot
    create a coverage -> artifact -> coverage dependency cycle.
    """
    ordered = sorted(block_ranges)
    if ordered != block_ranges or any(
        start < 0 or end <= start or end > ROM_SIZE
        or (index and start < ordered[index - 1][1])
        for index, (start, end) in enumerate(ordered)
    ):
        raise ValueError("frozen coverage promotion block ranges changed")
    instruction_bytes = sum(end - start for start, end in ordered)
    range_vector = [list(item) for item in ordered]
    if (
        len(range_vector) != 62
        or instruction_bytes != 628
        or _canonical_sha(range_vector)
        != PROMOTION_BLOCK_RANGE_DENOMINATOR_SHA256
    ):
        raise ValueError("frozen coverage promotion denominator changed")
    return {
        "path": COVERAGE_PATH.as_posix(), "sha256": COVERAGE_SHA256,
        "summary": dict(EXPECTED_COVERAGE_SUMMARY),
        "promotion_block_count": len(ordered),
        "promotion_instruction_bytes": instruction_bytes,
        "promotion_block_ranges": range_vector,
        "promotion_block_range_denominator_sha256": (
            PROMOTION_BLOCK_RANGE_DENOMINATOR_SHA256
        ),
        "current_unknown_bytes": instruction_bytes,
        "current_known_overlap_bytes": 0,
    }


def _controller_source_provenance(root: Path, rom: bytes) -> dict[str, Any]:
    raw = _safe_file(root, CONTROLLER_PAYLOAD).read_bytes()
    manifest_raw = _safe_file(root, CONTROLLER_ARTIFACT / MANIFEST_NAME).read_bytes()
    if _sha(raw) != CONTROLLER_PAYLOAD_SHA256 or _sha(manifest_raw) != CONTROLLER_MANIFEST_SHA256:
        raise ValueError("independent controller source identity changed")
    payload = json.loads(raw)
    manifest = json.loads(manifest_raw)
    if payload.get("schema") != "rom-battle-controller-cfg-v1" or manifest.get("artifact_schema") != "rom-battle-controller-cfg-v1":
        raise ValueError("independent controller source schema changed")
    from tools.verify_rom_battle_controller_cfg import verify_rom_battle_controller_cfg

    report = verify_rom_battle_controller_cfg(root, root / CONTROLLER_ARTIFACT)
    if report != EXPECTED_CONTROLLER_REPORT:
        raise ValueError(f"independent controller source verification failed: {report}")
    blocks = payload.get("extension", {}).get("blocks")
    _, _, _, entries = _verify_blocks(rom, blocks)
    denominator = _producer_denominator(rom)
    records = []
    for producer in denominator["producers"]:
        offset = producer["file_offset"]; target = producer["target_file_offset"]; item = dict(producer)
        if offset in EXCLUDED_PRODUCER_OFFSETS:
            if ("thumb", offset) in entries:
                raise ValueError("independent excluded producer is a controller source")
            item.update({"provenance": "provenance_excluded", "provenance_reason": "not_a_source_instruction_in_frozen_controller_cfg"})
        else:
            source = entries.get(("thumb", offset))
            if source is None:
                raise ValueError(f"independent controller source missing: 0x{offset:06X}")
            matches = [edge for edge in payload["extension"]["opaque_edges"] if edge.get("source") == {"file_offset": offset, "mode": "thumb"} and edge.get("edge_kind") == "call_target" and edge.get("target_mode") == "thumb" and edge.get("target_file_offset") == target and edge.get("reason") == "outside_controller_range"]
            if len(matches) != 1:
                raise ValueError(f"independent controller source edge changed: 0x{offset:06X}")
            item.update({"provenance": "controller", "controller_source": {"instruction_sha256": source["bytes_sha256"], "opaque_edge": matches[0]}})
        records.append(item)
    if len([item for item in records if item["provenance"] == "controller"]) != 9 or len([item for item in records if item["provenance"] == "provenance_excluded"]) != 2:
        raise ValueError("independent controller provenance denominator changed")
    return {"artifact": {"path": CONTROLLER_ARTIFACT.as_posix(), "payload_sha256": CONTROLLER_PAYLOAD_SHA256, "manifest_sha256": CONTROLLER_MANIFEST_SHA256, "verifier_path": CONTROLLER_VERIFIER.as_posix(), "verifier_sha256": CONTROLLER_VERIFIER_SHA256}, "verification": report, "controller_source_count": 9, "excluded_source_count": 2, "producers": records}


def _root_seeds(rom: bytes, provenance: dict[str, Any]) -> list[dict[str, Any]]:
    by_target: dict[int, list[dict[str, str]]] = defaultdict(list)
    for producer in provenance["producers"]:
        if producer["provenance"] == "controller":
            by_target[producer["target_file_offset"]].append({"producer_id": producer["producer_id"]})
    roots = []
    for offset in sorted(ROOT_BYTES):
        raw_hex, digest = ROOT_BYTES[offset]; raw = rom[offset:offset + 4]
        if raw.hex() != raw_hex or _sha(raw) != digest or offset not in by_target:
            raise ValueError(f"independent root denominator changed at 0x{offset:06X}")
        roots.append({"root_id": f"root-thumb-{offset:06x}", "mode": "thumb", "file_offset": offset, "gba_address": f"0x{ROM_BASE + offset:08X}", "entry_size": 4, "entry_sha256": digest, "sources": by_target[offset]})
    return roots


def _payload_blocks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = payload.get("extension", {}).get("blocks")
    if blocks is None:
        blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("independent frozen baseline blocks are missing")
    return blocks


def _invoke_baseline_verifier(root: Path, label: str) -> dict[str, Any]:
    spec = next((item for item in BASELINE_SPECS if item[0] == label), None)
    if spec is None:
        raise ValueError(f"independent unknown baseline verifier label: {label}")
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
        raise ValueError(f"independent baseline verifier is not routed: {label}")
    return verify(root, artifact_dir)


def _baseline_verification_reports(root: Path) -> dict[str, dict[str, Any]]:
    reports = {}
    for label, *_ in BASELINE_SPECS:
        report = _invoke_baseline_verifier(root, label)
        if report != EXPECTED_BASELINE_REPORTS[label]:
            raise ValueError(f"independent baseline verification failed for {label}: {report}")
        reports[label] = report
    if set(reports) != set(EXPECTED_BASELINE_REPORTS):
        raise ValueError("independent baseline verifier report denominator changed")
    return reports


def _baseline_contract_uncached(root_name: str, rom_digest: str):
    root = Path(root_name).resolve(strict=True); rom = _safe_file(root, ROM_PATH).read_bytes()
    if _sha(rom) != rom_digest:
        raise ValueError("independent baseline ROM identity changed")
    verification_reports = _baseline_verification_reports(root)
    entries = {}; owners = {}; frozen = {}
    for label, relative, payload_digest, manifest_digest, schema, verifier_path in BASELINE_SPECS:
        payload = _load_json(root, relative, payload_digest)
        manifest_raw = _safe_file(root, relative.parent / MANIFEST_NAME).read_bytes()
        if _sha(manifest_raw) != manifest_digest:
            raise ValueError(f"independent baseline manifest identity changed: {label}")
        if payload.get("schema") != schema:
            raise ValueError(f"independent baseline schema changed: {label}")
        blocks = _payload_blocks(payload); _, _, _, decoded = _verify_blocks(rom, blocks)
        entries[label] = decoded; owners[label] = _owner_map(blocks, decoded)
        frozen[label] = {"path": relative.parent.as_posix(), "payload_file": relative.name, "schema": schema, "payload_sha256": payload_digest, "manifest_sha256": manifest_digest, "verifier_path": verifier_path.as_posix(), "verifier_sha256": _sha(_safe_file(root, verifier_path).read_bytes()), "summary": payload.get("extension", {}).get("summary", payload.get("summary"))}
    occupied = set()
    for label, decoded in entries.items():
        current = {byte for (_, offset), node in decoded.items() for byte in range(offset, offset + node["size"])}
        if occupied & current:
            raise ValueError(f"independent frozen baseline bytes overlap at {label}")
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
    if offset < 2 or rom[offset - 2:offset + 2].hex() != prefix:
        raise ValueError(f"independent return exit bytes changed at 0x{offset:06X}")
    pop, bx = struct.unpack_from("<HH", rom, offset - 2); mask = pop & 0xFF
    if pop & 0xFF00 != 0xBC00 or mask == 0 or mask & (mask - 1) or bx & 0xFF87 != 0x4700:
        raise ValueError(f"independent return exit idiom changed at 0x{offset:06X}")
    pop_register = mask.bit_length() - 1; bx_register = (bx >> 3) & 0xF
    if pop_register != bx_register:
        raise ValueError(f"independent return exit register mismatch at 0x{offset:06X}")
    return {"file_offset": offset, "mode": "thumb", "prefix_raw_hex": prefix, "prefix_sha256": _sha(rom[offset - 2:offset + 2]), "pop_register": f"r{pop_register}", "bx_register": f"r{bx_register}", "register": f"r{pop_register}"}


def _normalize_return_exit(rom: bytes, offset: int, node: dict[str, Any]) -> dict[str, Any]:
    prefix = RETURN_EXIT_PREFIXES.get(offset)
    if prefix is None:
        return node
    _validate_return_exit(rom, offset, prefix)
    if not node.get("accepted") or node.get("mnemonic") != "bx":
        raise ValueError(f"independent return exit instruction changed at 0x{offset:06X}")
    normalized = dict(node); normalized["successors"] = []; normalized["frontiers"] = []
    return normalized


def _traverse_bounded_roots(rom: bytes, roots: list[dict[str, Any]], baseline_nodes: dict[str, dict[tuple[str, int], dict[str, Any]]]):
    occupied = {byte for records in baseline_nodes.values() for (_, offset), node in records.items() for byte in range(offset, offset + node["size"])}
    pending = []; scheduled = set()
    for root in roots:
        item = (root["mode"], root["file_offset"])
        if item[0] != "thumb" or not _in_promotion_range(item[1]) or item[1] in occupied:
            raise ValueError("independent root overlaps or escapes frozen baseline")
        heapq.heappush(pending, _key(*item)); scheduled.add(item)
    nodes = {}; rejected = {}; incoming = defaultdict(list); crosses = []
    while pending:
        offset, _, mode = heapq.heappop(pending); item = (mode, offset)
        if item in nodes or item in rejected:
            continue
        if offset in occupied:
            raise ValueError("independent traversal entered baseline middle")
        decoded = _decode_one(rom, offset, mode)
        if not decoded["accepted"]:
            rejected[item] = decoded; continue
        decoded = _normalize_return_exit(rom, offset, decoded); end = offset + decoded["size"]
        if not _in_promotion_range(offset, end):
            raise ValueError("independent instruction escaped or straddled promotion range")
        if any(byte in occupied for byte in range(offset, end)):
            raise ValueError("independent instruction straddles frozen baseline")
        if len(nodes) >= MAX_INSTRUCTION_COUNT:
            raise ValueError("independent CFG instruction budget exhausted")
        nodes[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"]); matches = [label for label, records in baseline_nodes.items() if target in records]
            if len(matches) > 1:
                raise ValueError("independent baseline target is ambiguous")
            if matches:
                crosses.append((item, edge["kind"], matches[0], target)); continue
            if target[1] in occupied:
                raise ValueError("independent successor targets baseline middle")
            if target[0] != "thumb" or not _in_promotion_range(target[1]):
                raise ValueError("independent successor escaped promotion ranges")
            incoming[target].append((item, edge["kind"]))
            if target not in scheduled:
                heapq.heappush(pending, _key(*target)); scheduled.add(target)
    return nodes, rejected, incoming, crosses


def _loaded_capstone_identity() -> dict[str, Any]:
    if os.environ.get("LIBCAPSTONE_PATH"):
        raise ValueError("LIBCAPSTONE_PATH must be empty")
    modules = {}
    for name in CAPSTONE_RUNTIME_PYTHON_NAMES:
        module_name = "capstone" if name == "__init__.py" else f"capstone.{name[:-3]}"; module = capstone if module_name == "capstone" else sys.modules.get(module_name); loaded = getattr(module, "__file__", None)
        if not loaded or Path(loaded).resolve(strict=True) != (PROJECT_ROOT / CAPSTONE_RUNTIME_DIRECTORY / name).resolve(strict=True):
            raise ValueError(f"loaded Capstone module is not vendored: {module_name}")
        modules[module_name] = (CAPSTONE_RUNTIME_DIRECTORY / name).as_posix()
    library = getattr(getattr(capstone, "_cs", None), "_name", None); expected = PROJECT_ROOT / "tools/_vendor/capstone/lib/libcapstone.dylib"
    if not library or Path(library).resolve(strict=True) != expected.resolve(strict=True):
        raise ValueError("loaded Capstone dynamic library is not vendored")
    return {"python_modules": modules, "dynamic_library": "tools/_vendor/capstone/lib/libcapstone.dylib", "libcapstone_path_environment": None}


def _implementation(root: Path) -> dict[str, Any]:
    paths = {"exporter": Path("tools/export_rom_cfg_proven_roots_v9.py"), "verifier": Path("tools/verify_rom_cfg_proven_roots_v9.py"), "test": Path("tests/test_export_rom_cfg_proven_roots_v9.py")}
    if tuple(sorted(path.name for path in (Path(root) / CAPSTONE_RUNTIME_DIRECTORY).glob("*.py"))) != tuple(sorted(CAPSTONE_RUNTIME_PYTHON_NAMES)):
        raise ValueError("Capstone runtime Python dependency denominator changed")
    digests = {}
    for relative in RUNTIME_DEPENDENCY_PATHS:
        passed = _safe_file(root, relative).read_bytes(); loaded = _safe_file(PROJECT_ROOT, relative).read_bytes()
        if passed != loaded:
            raise ValueError(f"loaded implementation differs from passed root: {relative.as_posix()}")
        digests[relative.as_posix()] = _sha(passed)
    for relative in paths.values():
        passed = _safe_file(root, relative).read_bytes(); loaded = _safe_file(PROJECT_ROOT, relative).read_bytes()
        if passed != loaded:
            raise ValueError(f"loaded implementation differs from passed root: {relative.as_posix()}")
    return {"binding": "passed-root-equals-loaded-runtime-dependency-denominator-with-isolated-cli", "paths": {label: value.as_posix() for label, value in paths.items()}, "exporter_sha256": _sha(_safe_file(root, paths["exporter"]).read_bytes()), "verifier_sha256": _sha(_safe_file(root, paths["verifier"]).read_bytes()), "test_sha256": _sha(_safe_file(root, paths["test"]).read_bytes()), "runtime_dependency_sha256": digests, "loaded_runtime": _loaded_capstone_identity(), "execution_isolation": {"python_flags": ["-I", "-S"], "verifier_command": ["python3", "-I", "-S", "tools/verify_rom_cfg_proven_roots_v9.py"], "preimport_checks": ["isolated-runtime", "no-site", "capstone-not-preloaded", "libcapstone-path-empty"]}}


def _frozen_baseline_payloads(frozen: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {label: frozen[label] for label, *_ in BASELINE_SPECS}
    result["verification_chain"] = frozen["verification_chain"]
    return result


def _receipt_commands(
    root: Path, manifest: dict[str, Any]
) -> tuple[list[str], list[str]]:
    producer = manifest.get("producer")
    verifier = manifest.get("verifier")
    if not isinstance(producer, dict) or not isinstance(verifier, dict):
        raise ValueError("v9 promotion receipt is missing")
    producer_command = producer.get("command")
    verifier_command = verifier.get("command")
    producer_prefix = [
        "python3",
        "-I",
        "-S",
        EXPORTER_PATH.as_posix(),
        "--root",
        ".",
        "--output-dir",
    ]
    verifier_prefix = [
        "python3",
        "-I",
        "-S",
        VERIFIER_PATH.as_posix(),
        "--root",
        ".",
        "--artifact-dir",
    ]
    if (
        not isinstance(producer_command, list)
        or producer_command[:-1] != producer_prefix
        or not isinstance(verifier_command, list)
        or verifier_command[:-1] != verifier_prefix
        or producer_command[-1] != verifier_command[-1]
    ):
        raise ValueError("v9 promotion receipt command changed")
    recorded = Path(producer_command[-1])
    if recorded.is_absolute():
        raise ValueError("v9 promotion receipt path must be repository-relative")
    target = (root / recorded).resolve(strict=False)
    allowed = (root / EXPERIMENT_OUTPUT_ROOT).resolve(strict=False)
    if target != allowed and allowed not in target.parents:
        raise ValueError("v9 promotion receipt path escaped experiment subtree")
    return producer_command, verifier_command


def _expected_manifest(
    root: Path,
    manifest: dict[str, Any],
    payload: dict[str, Any],
    payload_raw: bytes,
    *,
    expected_rom: dict[str, Any],
    expected_source: dict[str, Any],
    expected_frozen: dict[str, Any],
    expected_producers: dict[str, Any],
    expected_coverage: dict[str, Any],
    expected_promotion: dict[str, Any],
    expected_summary: dict[str, Any],
    implementation: dict[str, Any],
    expected_scope: dict[str, Any],
) -> dict[str, Any]:
    producer_command, verifier_command = _receipt_commands(root, manifest)
    status = manifest.get("artifact_status")
    if status not in {"candidate", "accepted"}:
        raise ValueError("v9 promotion status changed")
    report = EXPECTED_VERIFIER_REPORT if status == "accepted" else None
    return {
        "schema": PROMOTION_SCHEMA,
        "artifact_schema": SCHEMA,
        "artifact_status": status,
        "rom": expected_rom,
        "source": expected_source,
        "frozen_baseline": expected_frozen,
        "producer_summary": {
            "count": 11,
            "controller_source_count": 9,
            "excluded_source_count": 2,
            "denominator_sha256": expected_producers["denominator_sha256"],
        },
        "root_count": 8,
        "coverage_baseline": expected_coverage,
        "promotion": expected_promotion,
        "extension_summary": expected_summary,
        "baseline_cross_edge_count": 16,
        "opaque_return_exit_count": 7,
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
        "scope": expected_scope,
    }


def _verify_in_process(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    summary: dict[str, Any] = {}; rebuilt_count = 0; cross_count = 0
    try:
        root = Path(root).resolve(strict=True); artifact = Path(artifact_dir).absolute()
        if artifact.resolve(strict=True) != artifact or not artifact.is_dir():
            raise ValueError("v9 artifact uses a symlink")
        members = list(artifact.iterdir())
        if {item.name for item in members} != {MANIFEST_NAME, PAYLOAD_NAME} or any(item.is_symlink() or not item.is_file() for item in members):
            raise ValueError("v9 artifact file set changed")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM identity changed")
        producers = _producer_denominator(rom); provenance = _controller_source_provenance(root, rom); roots = _root_seeds(rom, provenance)
        baseline_nodes, baseline_owners, frozen = _baseline_contract(root, rom)
        rebuilt, rejected, incoming, rebuilt_crosses = _traverse_bounded_roots(rom, roots, baseline_nodes); rebuilt_count = len(rebuilt)
        if rejected:
            raise ValueError("v9 closure has unresolved frontier entries")
        expected_blocks, node_to_block = _build_blocks(rom, rebuilt, {(item["mode"], item["file_offset"]) for item in roots})
        expected_frontiers = _frontier_records(rebuilt, rejected, incoming, roots, node_to_block)
        expected_cross_records, expected_cross_vector = _cross_edge_records(rebuilt_crosses, node_to_block, baseline_owners); cross_count = len(expected_cross_vector)
        expected_summary = _extension_summary(rebuilt, expected_blocks, expected_frontiers); summary = expected_summary
        expected_returns = [_validate_return_exit(rom, offset, prefix) for offset, prefix in RETURN_EXIT_PREFIXES.items() if ("thumb", offset) in rebuilt]
        expected_coverage = _frozen_coverage_contract(
            [tuple(block["range"]) for block in expected_blocks]
        )
        if expected_coverage["promotion_block_count"] != 62 or expected_coverage["promotion_instruction_bytes"] != 628:
            raise ValueError("independent v9 coverage promotion denominator changed")
        payload_raw = _safe_file(artifact, PAYLOAD_NAME).read_bytes(); manifest_raw = _safe_file(artifact, MANIFEST_NAME).read_bytes(); payload = json.loads(payload_raw); manifest = json.loads(manifest_raw)
        if payload_raw != _canonical_json(payload):
            raise ValueError("v9 payload is not canonical JSON")
        if manifest_raw != _canonical_json(manifest):
            raise ValueError("v9 manifest is not canonical JSON")
        expected_rom = {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256}
        expected_source = {"controller_cfg": provenance["artifact"], "verification": provenance["verification"], "provenance_summary": {"full_producer_count": len(provenance["producers"]), "controller_source_count": 9, "excluded_source_count": 2, "excluded_reason": "not_a_source_instruction_in_frozen_controller_cfg"}}
        expected_producers = {"scan": producers["scan"], "producers": provenance["producers"], "denominator_sha256": _canonical_sha(provenance["producers"])}
        expected_scope = dict(SCOPE)
        implementation = _implementation(root)
        expected_promotion = {"ranges": [list(item) for item in PROMOTION_RANGES], "current_known_overlap_bytes": 0}
        expected_extension = {"blocks": expected_blocks, "frontiers": expected_frontiers, "baseline_cross_edges": expected_cross_records, "cross_edge_denominator_sha256": _canonical_sha(expected_cross_vector), "opaque_return_exits": expected_returns, "summary": expected_summary}
        expected_payload = {"schema": SCHEMA, "rom": expected_rom, "source": expected_source, "frozen_baseline": _frozen_baseline_payloads(frozen), "producer_denominator": expected_producers, "roots": _root_results(roots, rebuilt, expected_frontiers, node_to_block), "extension": expected_extension, "coverage_baseline": expected_coverage, "promotion": expected_promotion, "implementation": implementation, "scope": expected_scope}
        if payload != expected_payload:
            raise ValueError("v9 payload contract changed")
        _, _, _, artifact_entries = _verify_blocks(rom, payload["extension"]["blocks"])
        if set(artifact_entries) != set(rebuilt):
            raise ValueError("v9 closure differs from independent worklist")
        if payload["extension"]["summary"] != {"decoded_basic_block_count": 62, "decoded_instruction_count": 299, "frontier_count": 0, "frontier_reasons": {}, "reachable_instruction_bytes": 628}:
            raise ValueError("v9 summary changed")
        expected_manifest = _expected_manifest(
            root,
            manifest,
            payload,
            payload_raw,
            expected_rom=expected_rom,
            expected_source=expected_source,
            expected_frozen=_frozen_baseline_payloads(frozen),
            expected_producers=expected_producers,
            expected_coverage=expected_coverage,
            expected_promotion=expected_promotion,
            expected_summary=expected_summary,
            implementation=implementation,
            expected_scope=expected_scope,
        )
        if manifest != expected_manifest:
            raise ValueError("v9 manifest contract changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    if not errors:
        return dict(EXPECTED_VERIFIER_REPORT)
    return {"schema": VERIFY_SCHEMA, "verified": False, "errors": errors, "control_flow_oracle": "armv4t-raw-encoding", "independently_rebuilt_instruction_count": rebuilt_count, "root_count": 0, "decoded_instruction_count": summary.get("decoded_instruction_count", 0), "decoded_basic_block_count": summary.get("decoded_basic_block_count", 0), "reachable_instruction_bytes": summary.get("reachable_instruction_bytes", 0), "frontier_count": summary.get("frontier_count", 0), "baseline_cross_edge_count": cross_count}


def verify_rom_cfg_proven_roots_v9(root: Path, artifact_dir: Path) -> dict[str, Any]:
    return _verify_in_process(root, artifact_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    artifact = args.artifact_dir if args.artifact_dir.is_absolute() else args.root / args.artifact_dir
    report = verify_rom_cfg_proven_roots_v9(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
