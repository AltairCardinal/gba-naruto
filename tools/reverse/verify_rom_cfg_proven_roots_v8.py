#!/usr/bin/env python3
"""Independently verify the bounded scene-panel Thumb CFG root artifact."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import heapq
import json
import os
from pathlib import Path
import struct
import subprocess
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
        raise RuntimeError("CFG v8 CLI requires Python -I -S isolation")
    if "capstone" in sys.modules:
        raise RuntimeError("CFG v8 CLI rejects preloaded Capstone modules")
    if os.environ.get("LIBCAPSTONE_PATH"):
        raise RuntimeError("CFG v8 CLI rejects LIBCAPSTONE_PATH overrides")
    _CLEAN_CLI_STARTUP_CONFIRMED = True


_require_isolated_cli_runtime()

for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import capstone

from tools.verify_rom_cfg_inventory import (
    ROM_PATH,
    ROM_SHA256,
    _canonical_sha,
    _decode,
    _expected_roots,
    _safe_file,
    _sha,
    _verify_blocks,
    _union_bytes,
)
from tools.verify_rom_cfg_proven_roots_v2 import (
    _expected_frontiers_and_crosses,
    _extension_summary,
    _owner_map,
    _simple_cross_vector,
)
from tools.verify_rom_cfg_proven_roots_v3 import _all_baselines
from tools.verify_rom_cfg_proven_roots_v7 import verify_rom_cfg_proven_roots_v7


ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
SCHEMA = "rom-cfg-proven-roots-v8"
VERIFY_SCHEMA = "rom-cfg-proven-roots-verification-v8"
PAYLOAD_NAME = "rom-cfg-proven-roots-v8.json"
MANIFEST_NAME = "manifest.json"
SOURCE_SLICE = (0x08BAB0, 0x08BEDE)
SOURCE_SLICE_SHA256 = "49e5707f975743b374bc93b685bdeb8465674c46b17bf543574ed010f318929f"
SOURCE_ENTRY = 0x08BAB0
PROMOTION_WINDOW = (0x08B834, 0x08BAB0)
PROMOTION_WINDOW_SHA256 = "be129513ff0d9f89105f78010d9c515bfc5f1e53831e17ebb91b4dd6f7a04a1a"
PRODUCER_OFFSET = 0x08BE5C
PRODUCER_RAW_HEX = "fff79efd"
PRODUCER_SHA256 = "6348d4c27cc6782b65fd065f96b2fc205deddacbea049b25b0b953e33495305c"
ROOT_OFFSET = 0x08B99C
ROOT_RAW_HEX = "f0b55746"
ROOT_SHA256 = "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb"
SOURCE_MANIFEST_PATH = Path("artifacts/scene-visual-packs-v1/manifest.json")
SOURCE_MANIFEST_SHA256 = "4bb40dff9ac2e5641b5e13f46b1dc90bdaa28b9b5615deab7e2a914ae002d5f4"
SOURCE_VERIFIER_PATH = Path("tools/verify_scene_visual_packs.py")
SOURCE_VERIFIER_SHA256 = "477d27ac7d8b1c11ecfaf3fe23d70bab9087349df5b36c041bb94911bca2293d"
SOURCE_SELECTOR = "/consumer_evidence/setup_and_initial_row"
SOURCE_ARTIFACT_PATH = Path("artifacts/scene-visual-packs-v1")
SOURCE_VERIFICATION_REPORT = {
    "verified": True,
    "errors": [],
    "pack_count": 9,
    "obj_frame_count": 16,
    "obj_animation_count": 16,
}
CAPSTONE_RUNTIME_DIRECTORY = Path("tools/_vendor/capstone")
CAPSTONE_RUNTIME_PYTHON_NAMES = (
    "__init__.py",
    "arm.py",
    "arm64.py",
    "arm64_const.py",
    "arm_const.py",
    "bpf.py",
    "bpf_const.py",
    "evm.py",
    "evm_const.py",
    "m680x.py",
    "m680x_const.py",
    "m68k.py",
    "m68k_const.py",
    "mips.py",
    "mips_const.py",
    "mos65xx.py",
    "mos65xx_const.py",
    "ppc.py",
    "ppc_const.py",
    "riscv.py",
    "riscv_const.py",
    "sh.py",
    "sh_const.py",
    "sparc.py",
    "sparc_const.py",
    "systemz.py",
    "sysz_const.py",
    "tms320c64x.py",
    "tms320c64x_const.py",
    "tricore.py",
    "tricore_const.py",
    "wasm.py",
    "wasm_const.py",
    "x86.py",
    "x86_const.py",
    "xcore.py",
    "xcore_const.py",
)
CAPSTONE_RUNTIME_DEPENDENCY_PATHS = tuple(
    CAPSTONE_RUNTIME_DIRECTORY / name for name in CAPSTONE_RUNTIME_PYTHON_NAMES
)
RUNTIME_DEPENDENCY_PATHS = tuple(
    Path(item)
    for item in (
        "tools/export_rom_cfg_inventory.py",
        "tools/export_rom_cfg_proven_roots.py",
        "tools/export_rom_cfg_proven_roots_v2.py",
        "tools/verify_rom_cfg_inventory.py",
        "tools/verify_rom_cfg_inventory_v3.py",
        "tools/verify_rom_cfg_proven_roots.py",
        "tools/verify_rom_cfg_proven_roots_v2.py",
        "tools/verify_rom_cfg_proven_roots_v3.py",
        "tools/verify_rom_cfg_proven_roots_v7.py",
        "tools/verify_rom_cfg_seeds.py",
        "tools/verify_similar_table_candidates.py",
        "tools/verify_scene_visual_packs.py",
    )
) + CAPSTONE_RUNTIME_DEPENDENCY_PATHS + (
    Path("tools/_vendor/capstone/lib/libcapstone.dylib"),
)
EXECUTION_ISOLATION_CONTRACT = {
    "python_flags": ["-I", "-S"],
    "verifier_command": [
        "python3",
        "-I",
        "-S",
        "tools/verify_rom_cfg_proven_roots_v8.py",
    ],
    "preimport_checks": [
        "isolated-runtime",
        "no-site",
        "capstone-not-preloaded",
        "libcapstone-path-empty",
    ],
}
V7_ARTIFACT = Path("artifacts/rom-cfg-proven-roots-v7")
V7_PAYLOAD_PATH = V7_ARTIFACT / "rom-cfg-proven-roots-v7.json"
V7_PAYLOAD_SHA256 = "184e9b84df829fb1ad41f272aabe931c1a1f86111eebd60629ad2d2a23d89a06"
V7_MANIFEST_SHA256 = "da9a1b5fe7ce8e7889fbba9fe8251c907ed18f6b273cbcc3be145101ece99114"
EXTRA_BASELINES = (
    (
        "proven_roots_v3",
        Path("artifacts/rom-cfg-proven-roots-v3/rom-cfg-proven-roots-v3.json"),
        "f2de5ca57685e3542d5e483e5a171a30eb32bb6dc6ce9794cc683371579af9a2",
    ),
    (
        "proven_roots_v4",
        Path("artifacts/rom-cfg-proven-roots-v4/rom-cfg-proven-roots-v4.json"),
        "d14c9f4198d9209d03d8511351b5dc997ade409a3218e9f05993c8c7f11456eb",
    ),
    (
        "proven_roots_v5",
        Path("artifacts/rom-cfg-proven-roots-v5/rom-cfg-proven-roots-v5.json"),
        "680b03dffb5c3dbbca41d9a5d0872db560a1a05850d7928ce75243397a54f040",
    ),
    (
        "proven_roots_v6",
        Path("artifacts/rom-cfg-proven-roots-v6/rom-cfg-proven-roots-v6.json"),
        "e5b27a55c77cd1df4ac5ec39f2dd05735b0b53c01b7cbbcf1620db1681a3c3ec",
    ),
    ("proven_roots_v7", V7_PAYLOAD_PATH, V7_PAYLOAD_SHA256),
)
SCOPE = {
    "fixed_direct_producer_denominator_complete": True,
    "source_slice_bounded_worklist_complete": True,
    "baseline_entries_treated_as_opaque": True,
    "promotion_window_complete": True,
    "current_known_overlap_bytes": 0,
    "runtime_reachability_complete": False,
    "global_function_entry_denominator_complete": False,
    "global_indirect_target_denominator_complete": False,
    "source_slice": list(SOURCE_SLICE),
    "promotion_window": list(PROMOTION_WINDOW),
}


def _key(mode: str, offset: int) -> tuple[int, int, str]:
    return offset, 0 if mode == "arm" else 1, mode


def _decode_thumb_bl(callsite: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return callsite + 4 + displacement


def _source_worklist(rom: bytes) -> dict[str, Any]:
    start, end = SOURCE_SLICE
    if len(rom) != ROM_SIZE or _sha(rom[start:end]) != SOURCE_SLICE_SHA256:
        raise ValueError("independent source consumer slice changed")
    if _sha(rom[PROMOTION_WINDOW[0] : PROMOTION_WINDOW[1]]) != PROMOTION_WINDOW_SHA256:
        raise ValueError("independent promotion window changed")
    pending = [_key("thumb", SOURCE_ENTRY)]
    heapq.heapify(pending)
    scheduled = {("thumb", SOURCE_ENTRY)}
    entries: dict[tuple[str, int], dict[str, Any]] = {}
    incoming: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    rejected: set[tuple[str, int]] = set()
    opaque: list[dict[str, Any]] = []
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in entries or item in rejected:
            continue
        if not (start <= offset < end):
            raise ValueError("independent source worklist escaped bounded slice")
        decoded = _decode(rom, offset, mode)
        if not decoded["accepted"]:
            rejected.add(item)
            continue
        if offset + decoded["size"] > end:
            raise ValueError("independent source instruction straddles bounded slice")
        entries[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            if start <= target[1] < end:
                incoming[target].append(
                    {"source": {"mode": mode, "file_offset": offset}, "edge_kind": edge["kind"]}
                )
                if target not in scheduled:
                    heapq.heappush(pending, _key(*target))
                    scheduled.add(target)
            else:
                opaque.append(
                    {
                        "source": {"mode": mode, "file_offset": offset},
                        "edge_kind": edge["kind"],
                        "target": {"mode": target[0], "file_offset": target[1]},
                    }
                )
    if rejected:
        raise ValueError("independent source worklist contains unresolved entries")
    key = ("thumb", PRODUCER_OFFSET)
    if key not in entries or not incoming.get(key):
        raise ValueError("independent producer boundary is not reachable")
    accepted_bytes = sum(item["size"] for item in entries.values())
    return {
        "entry": {"mode": "thumb", "file_offset": SOURCE_ENTRY, "gba_address": f"0x{ROM_BASE + SOURCE_ENTRY:08X}"},
        "range": list(SOURCE_SLICE),
        "size": end - start,
        "sha256": SOURCE_SLICE_SHA256,
        "accepted_instruction_count": len(entries),
        "accepted_instruction_bytes": accepted_bytes,
        "accepted_instruction_offsets": sorted(offset for _, offset in entries),
        "unresolved_entry_count": len(rejected),
        "opaque_target_count": len(opaque),
        "unreachable_byte_count": end - start - accepted_bytes,
        "reachable_boundary_proof": {
            "mode": "thumb",
            "file_offset": PRODUCER_OFFSET,
            "raw_hex": rom[PRODUCER_OFFSET : PRODUCER_OFFSET + 4].hex(),
            "bytes_sha256": _sha(rom[PRODUCER_OFFSET : PRODUCER_OFFSET + 4]),
            "predecessors": sorted(
                incoming[key],
                key=lambda item: (item["source"]["file_offset"], item["edge_kind"]),
            ),
        },
    }


def _producer_denominator(rom: bytes) -> dict[str, Any]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("independent base ROM identity changed")
    actual = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        target = _decode_thumb_bl(offset, first, second)
        if target == ROOT_OFFSET:
            actual.append((offset, target))
    if actual != [(PRODUCER_OFFSET, ROOT_OFFSET)]:
        raise ValueError("independent direct-call producer denominator changed")
    raw = rom[PRODUCER_OFFSET : PRODUCER_OFFSET + 4]
    if raw.hex() != PRODUCER_RAW_HEX or _sha(raw) != PRODUCER_SHA256:
        raise ValueError("independent producer bytes changed")
    producers = [
        {
            "producer_id": "producer_08be5c",
            "file_offset": PRODUCER_OFFSET,
            "gba_address": f"0x{ROM_BASE + PRODUCER_OFFSET:08X}",
            "raw_hex": PRODUCER_RAW_HEX,
            "bytes_sha256": PRODUCER_SHA256,
            "target_file_offset": ROOT_OFFSET,
            "target_gba_address": f"0x{ROM_BASE + ROOT_OFFSET:08X}",
        }
    ]
    return {
        "scan": {"mode": "thumb", "alignment_bytes": 2, "range": [0, len(rom)], "target_file_offsets": [ROOT_OFFSET], "matching_producer_count": 1},
        "producers": producers,
        "denominator_sha256": _canonical_sha(producers),
    }


def _roots(rom: bytes, producers: dict[str, Any]) -> list[dict[str, Any]]:
    raw = rom[ROOT_OFFSET : ROOT_OFFSET + 4]
    if raw.hex() != ROOT_RAW_HEX or _sha(raw) != ROOT_SHA256:
        raise ValueError("independent root bytes changed")
    if [item["target_file_offset"] for item in producers["producers"]] != [ROOT_OFFSET]:
        raise ValueError("independent producer/root binding changed")
    return [
        {
            "root_id": f"root-thumb-{ROOT_OFFSET:06x}",
            "mode": "thumb",
            "file_offset": ROOT_OFFSET,
            "gba_address": f"0x{ROM_BASE + ROOT_OFFSET:08X}",
            "entry_size": 4,
            "entry_sha256": ROOT_SHA256,
            "sources": [{"producer_id": "producer_08be5c"}],
        }
    ]


def _source_evidence(root: Path) -> dict[str, Any]:
    manifest_raw = _safe_file(root, SOURCE_MANIFEST_PATH).read_bytes()
    verifier_raw = _safe_file(root, SOURCE_VERIFIER_PATH).read_bytes()
    if _sha(manifest_raw) != SOURCE_MANIFEST_SHA256:
        raise ValueError("source manifest changed")
    if _sha(verifier_raw) != SOURCE_VERIFIER_SHA256:
        raise ValueError("source verifier changed")
    manifest = json.loads(manifest_raw)
    selected = manifest.get("consumer_evidence", {}).get("setup_and_initial_row")
    expected = {
        "gba_range": ["0x0808BAB0", "0x0808BEDE"],
        "size": SOURCE_SLICE[1] - SOURCE_SLICE[0],
        "sha256": SOURCE_SLICE_SHA256,
    }
    if selected != expected:
        raise ValueError("source selector changed")
    from tools.verify_scene_visual_packs import verify_artifact

    verification = verify_artifact(root, root / SOURCE_ARTIFACT_PATH)
    if verification != SOURCE_VERIFICATION_REPORT:
        raise ValueError(
            "source artifact independent verification failed: "
            f"{verification}"
        )
    return {
        "manifest": {
            "path": SOURCE_MANIFEST_PATH.as_posix(),
            "sha256": SOURCE_MANIFEST_SHA256,
            "selector": SOURCE_SELECTOR,
        },
        "verifier": {
            "path": SOURCE_VERIFIER_PATH.as_posix(),
            "sha256": SOURCE_VERIFIER_SHA256,
        },
        "consumer_evidence": expected,
        "independent_verification": {
            "artifact_path": SOURCE_ARTIFACT_PATH.as_posix(),
            "report": verification,
        },
    }


def _load_baselines_uncached(root: Path, rom: bytes):
    v7_raw = _safe_file(root, V7_PAYLOAD_PATH).read_bytes()
    v7_manifest = _safe_file(root, V7_ARTIFACT / MANIFEST_NAME).read_bytes()
    if _sha(v7_raw) != V7_PAYLOAD_SHA256 or _sha(v7_manifest) != V7_MANIFEST_SHA256:
        raise ValueError("independent v7 baseline identity changed")
    report = verify_rom_cfg_proven_roots_v7(root, root / V7_ARTIFACT)
    if report != {
        "schema": "rom-cfg-proven-roots-verification-v7", "verified": True, "errors": [],
        "control_flow_oracle": "armv4t-raw-encoding", "independently_rebuilt_instruction_count": 155,
        "root_count": 8, "decoded_instruction_count": 155, "decoded_basic_block_count": 38,
        "reachable_instruction_bytes": 332, "frontier_count": 1, "baseline_cross_edge_count": 17,
    }:
        raise ValueError(f"independent v7 baseline verification failed: {report}")
    entries, owners = _all_baselines(root, rom)
    payloads: dict[str, dict[str, Any]] = {}
    for label, relative, digest in EXTRA_BASELINES:
        raw = _safe_file(root, relative).read_bytes()
        if _sha(raw) != digest:
            raise ValueError(f"independent frozen baseline identity changed: {label}")
        payload = json.loads(raw)
        blocks = payload["extension"]["blocks"]
        _, _, _, decoded = _verify_blocks(rom, blocks)
        entries[label] = decoded
        owners[label] = _owner_map(blocks, decoded)
        payloads[label] = payload
    occupied: set[int] = set()
    for label, decoded in entries.items():
        current = {
            byte
            for (_, offset), item in decoded.items()
            for byte in range(offset, offset + item["size"])
        }
        if occupied & current:
            raise ValueError(f"independent frozen baselines overlap at {label}")
        occupied.update(current)
    payloads["v7"] = json.loads(v7_raw)
    return entries, owners, payloads


def _load_baselines(root: Path, rom: bytes):
    return _load_baselines_uncached(Path(root).resolve(strict=True), rom)


def _traverse_root(rom: bytes, roots: list[dict[str, Any]], baseline_entries):
    start, end = PROMOTION_WINDOW
    occupied = {
        byte
        for decoded in baseline_entries.values()
        for (_, offset), item in decoded.items()
        for byte in range(offset, offset + item["size"])
    }
    pending = []
    scheduled = set()
    for root in roots:
        item = (root["mode"], root["file_offset"])
        if not (start <= item[1] < end):
            raise ValueError("independent root is outside promotion window")
        if any(item in decoded for decoded in baseline_entries.values()) or item[1] in occupied:
            raise ValueError("independent root overlaps baseline entry or byte")
        heapq.heappush(pending, (item[1], 1, item[0]))
        scheduled.add(item)
    entries = {}
    rejected = {}
    incoming = defaultdict(list)
    crosses = []
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in entries or item in rejected:
            continue
        if not (start <= offset < end):
            raise ValueError("independent root CFG escaped promotion window")
        if offset in occupied:
            raise ValueError("independent root CFG entered baseline byte")
        decoded = _decode(rom, offset, mode)
        if not decoded["accepted"]:
            rejected[item] = decoded
            continue
        if offset + decoded["size"] > end:
            raise ValueError("independent root instruction straddles promotion window")
        if any(byte in occupied for byte in range(offset, offset + decoded["size"])):
            raise ValueError("independent root instruction straddles baseline")
        entries[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            matched = [label for label, decoded_entries in baseline_entries.items() if target in decoded_entries]
            if len(matched) > 1:
                raise ValueError("independent baseline target is ambiguous")
            if matched:
                crosses.append((item, edge["kind"], matched[0], target))
                continue
            if target[1] in occupied:
                raise ValueError("independent successor targets baseline middle or straddle")
            if not (start <= target[1] < end):
                raise ValueError("independent successor escaped promotion window")
            incoming[target].append((item, edge["kind"]))
            if target not in scheduled:
                heapq.heappush(pending, (target[1], 1 if target[0] == "thumb" else 0, target[0]))
                scheduled.add(target)
    return entries, rejected, incoming, crosses


def _loaded_capstone_identity() -> dict[str, Any]:
    if os.environ.get("LIBCAPSTONE_PATH"):
        raise ValueError("LIBCAPSTONE_PATH must be empty for frozen Capstone identity")

    python_modules: dict[str, str] = {}
    for name in CAPSTONE_RUNTIME_PYTHON_NAMES:
        module_name = "capstone" if name == "__init__.py" else f"capstone.{name[:-3]}"
        module = capstone if module_name == "capstone" else sys.modules.get(module_name)
        loaded_file = getattr(module, "__file__", None)
        if not loaded_file:
            raise ValueError(f"loaded Capstone module missing: {module_name}")
        try:
            loaded_path = Path(loaded_file).resolve(strict=True)
            expected_path = (PROJECT_ROOT / CAPSTONE_RUNTIME_DIRECTORY / name).resolve(
                strict=True
            )
        except OSError as error:
            raise ValueError(
                f"loaded Capstone module path is invalid: {module_name}"
            ) from error
        if loaded_path != expected_path:
            raise ValueError(
                f"loaded Capstone module is not vendored: {module_name}: {loaded_path}"
            )
        python_modules[module_name] = (
            CAPSTONE_RUNTIME_DIRECTORY / name
        ).as_posix()

    loaded_library = getattr(getattr(capstone, "_cs", None), "_name", None)
    expected_library_relative = Path(
        "tools/_vendor/capstone/lib/libcapstone.dylib"
    )
    if not loaded_library:
        raise ValueError("loaded Capstone dynamic library identity is unavailable")
    try:
        loaded_library_path = Path(loaded_library).resolve(strict=True)
        expected_library_path = (PROJECT_ROOT / expected_library_relative).resolve(
            strict=True
        )
    except OSError as error:
        raise ValueError("loaded Capstone dynamic library path is invalid") from error
    if loaded_library_path != expected_library_path:
        raise ValueError(
            "loaded Capstone dynamic library is not vendored: "
            f"{loaded_library_path}"
        )
    return {
        "python_modules": python_modules,
        "dynamic_library": expected_library_relative.as_posix(),
        "libcapstone_path_environment": None,
    }


def _implementation(root: Path) -> dict[str, Any]:
    paths = {
        "exporter": Path("tools") / ("export_rom_cfg_proven_roots_" + "v8.py"),
        "verifier": Path("tools/verify_rom_cfg_proven_roots_v8.py"),
        "test": Path("tests") / ("test_export_rom_cfg_proven_roots_" + "v8.py"),
    }
    expected_capstone_names = tuple(sorted(CAPSTONE_RUNTIME_PYTHON_NAMES))
    for checked_root in (root, PROJECT_ROOT):
        capstone_directory = checked_root / CAPSTONE_RUNTIME_DIRECTORY
        actual_capstone_names = tuple(
            sorted(path.name for path in capstone_directory.iterdir() if path.suffix == ".py")
        )
        if actual_capstone_names != expected_capstone_names:
            raise ValueError(
                "Capstone runtime Python dependency denominator changed: "
                f"{actual_capstone_names}"
            )
    runtime_dependency_sha256: dict[str, str] = {}
    for path in RUNTIME_DEPENDENCY_PATHS:
        passed = _safe_file(root, path).read_bytes()
        loaded = _safe_file(PROJECT_ROOT, path).read_bytes()
        if passed != loaded:
            raise ValueError(
                f"loaded implementation differs from passed root: {path.as_posix()}"
            )
        runtime_dependency_sha256[path.as_posix()] = _sha(passed)
    for label in ("exporter", "verifier"):
        path = paths[label]
        passed = _safe_file(root, path).read_bytes()
        loaded = _safe_file(PROJECT_ROOT, path).read_bytes()
        if passed != loaded:
            raise ValueError(
                f"loaded implementation differs from passed root: {path.as_posix()}"
            )
    return {
        "binding": "passed-root-equals-loaded-runtime-dependency-denominator-with-isolated-cli",
        "paths": {label: path.as_posix() for label, path in paths.items()},
        "exporter_sha256": _sha(_safe_file(root, paths["exporter"]).read_bytes()),
        "verifier_sha256": _sha(_safe_file(root, paths["verifier"]).read_bytes()),
        "test_sha256": _sha(_safe_file(root, paths["test"]).read_bytes()),
        "runtime_dependency_sha256": runtime_dependency_sha256,
        "loaded_runtime": _loaded_capstone_identity(),
        "execution_isolation": EXECUTION_ISOLATION_CONTRACT,
    }


def _frozen_baseline_contract() -> dict[str, dict[str, Any]]:
    return {
        "v2": {"schema": "rom-cfg-inventory-v2"},
        "v3": {"schema": "rom-cfg-inventory-v3"},
        "proven_roots_v1": {"schema": "rom-cfg-proven-roots-v1"},
        "proven_roots_v2": {"schema": "rom-cfg-proven-roots-v2", "payload_sha256": "a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba"},
        "battle_controller": {"schema": "rom-battle-controller-cfg-v1", "payload_sha256": "c8b1d1c2068d85912ede1fd35be31f0cf9cb43943beb10f1058d43c65c00449a"},
        "proven_roots_v3": {"schema": "rom-cfg-proven-roots-v3", "payload_sha256": "f2de5ca57685e3542d5e483e5a171a30eb32bb6dc6ce9794cc683371579af9a2"},
        "proven_roots_v4": {"schema": "rom-cfg-proven-roots-v4", "payload_sha256": "d14c9f4198d9209d03d8511351b5dc997ade409a3218e9f05993c8c7f11456eb"},
        "proven_roots_v5": {"schema": "rom-cfg-proven-roots-v5", "payload_sha256": "680b03dffb5c3dbbca41d9a5d0872db560a1a05850d7928ce75243397a54f040"},
        "proven_roots_v6": {"schema": "rom-cfg-proven-roots-v6", "payload_sha256": "e5b27a55c77cd1df4ac5ec39f2dd05735b0b53c01b7cbbcf1620db1681a3c3ec"},
        "proven_roots_v7": {"schema": "rom-cfg-proven-roots-v7", "payload_sha256": V7_PAYLOAD_SHA256, "manifest_sha256": V7_MANIFEST_SHA256},
    }


def _verify_rom_cfg_proven_roots_v8_in_process(
    root: Path, artifact_dir: Path
) -> dict[str, Any]:
    errors: list[str] = []
    summary: dict[str, Any] = {}
    rebuilt_count = 0
    cross_count = 0
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact_dir).absolute()
        if artifact.resolve(strict=True) != artifact or not artifact.is_dir():
            raise ValueError("v8 artifact uses a symlink")
        members = list(artifact.iterdir())
        if {item.name for item in members} != {MANIFEST_NAME, PAYLOAD_NAME} or any(item.is_symlink() or not item.is_file() for item in members):
            raise ValueError("v8 artifact file set changed")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM identity changed")
        source = _source_worklist(rom)
        producer = _producer_denominator(rom)
        roots = _roots(rom, producer)
        baseline_entries, baseline_owners, _ = _load_baselines(root, rom)
        rebuilt, rejected, incoming, rebuilt_crosses = _traverse_root(rom, roots, baseline_entries)
        rebuilt_count = len(rebuilt)
        payload_raw = (artifact / PAYLOAD_NAME).read_bytes()
        payload = json.loads(payload_raw)
        manifest_raw = (artifact / MANIFEST_NAME).read_bytes()
        manifest = json.loads(manifest_raw)
        expected_rom = {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256}
        expected_source_evidence = _source_evidence(root)
        if (
            set(payload) != {"schema", "rom", "source", "frozen_baseline", "producer_denominator", "roots", "extension", "promotion", "implementation", "scope"}
            or payload.get("schema") != SCHEMA
            or payload.get("rom") != expected_rom
            or payload.get("source") != {"evidence": expected_source_evidence, "worklist": source}
            or payload.get("frozen_baseline") != _frozen_baseline_contract()
            or payload.get("producer_denominator") != producer
            or payload.get("scope") != SCOPE
        ):
            raise ValueError("v8 top-level contract changed")
        if payload["promotion"] != {"window": list(PROMOTION_WINDOW), "window_sha256": PROMOTION_WINDOW_SHA256, "current_known_overlap_bytes": 0}:
            raise ValueError("v8 promotion contract changed")
        implementation = _implementation(root)
        if payload.get("implementation") != implementation:
            raise ValueError("v8 implementation binding changed")
        blocks = payload["extension"]["blocks"]
        decoded_last, block_entries, by_id, artifact_entries = _verify_blocks(rom, blocks)
        if set(artifact_entries) != set(rebuilt):
            raise ValueError("v8 closure differs from independent worklist")
        if any(not (PROMOTION_WINDOW[0] <= offset < PROMOTION_WINDOW[1]) for _, offset in artifact_entries):
            raise ValueError("v8 closure escaped promotion window")
        frontiers, cross_records, cross_vector = _expected_frontiers_and_crosses(
            rom, blocks, decoded_last, block_entries, artifact_entries,
            baseline_entries, baseline_owners, roots,
        )
        if _simple_cross_vector(rebuilt_crosses) != cross_vector:
            raise ValueError("v8 cross worklists disagree")
        summary = _extension_summary(blocks, frontiers)
        expected_summary = {"decoded_basic_block_count": 20, "decoded_instruction_count": 113, "frontier_count": 1, "frontier_reasons": {"indirect_pc_target": 1}, "reachable_instruction_bytes": 246}
        if summary != expected_summary:
            raise ValueError("v8 summary changed")
        cross_count = len(cross_vector)
        if cross_count != 10:
            raise ValueError("v8 cross-edge denominator changed")
        expected_extension = {
            "blocks": blocks,
            "frontiers": frontiers,
            "baseline_cross_edges": cross_records,
            "cross_edge_denominator_sha256": _canonical_sha(cross_vector),
            "summary": summary,
        }
        if payload["extension"] != expected_extension:
            raise ValueError("v8 root or edge contract changed")
        expected_roots = _expected_roots(roots, block_entries, by_id, frontiers)
        if payload["roots"] != expected_roots:
            raise ValueError("v8 root result contract changed")
        expected_manifest = {
            "artifact_schema": SCHEMA,
            "rom": expected_rom,
            "source": payload["source"],
            "frozen_baseline": payload["frozen_baseline"],
            "producer_summary": {"count": 1, "denominator_sha256": producer["denominator_sha256"]},
            "root_count": 1,
            "promotion": payload["promotion"],
            "extension_summary": summary,
            "baseline_cross_edge_count": 10,
            "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}},
            "implementation": implementation,
            "scope": SCOPE,
        }
        if manifest != expected_manifest:
            raise ValueError("v8 manifest changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "errors": errors,
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": rebuilt_count,
        "root_count": 1 if not errors else 0,
        "decoded_instruction_count": summary.get("decoded_instruction_count", 0),
        "decoded_basic_block_count": summary.get("decoded_basic_block_count", 0),
        "reachable_instruction_bytes": summary.get("reachable_instruction_bytes", 0),
        "frontier_count": summary.get("frontier_count", 0),
        "baseline_cross_edge_count": cross_count,
    }


def verify_rom_cfg_proven_roots_v8(root: Path, artifact_dir: Path) -> dict[str, Any]:
    if _CLEAN_CLI_STARTUP_CONFIRMED:
        return _verify_rom_cfg_proven_roots_v8_in_process(root, artifact_dir)

    root = Path(root).resolve(strict=True)
    artifact = Path(artifact_dir).absolute()
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(PROJECT_ROOT / "tools/verify_rom_cfg_proven_roots_v8.py"),
            "--root",
            str(root),
            "--artifact-dir",
            str(artifact),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "schema": VERIFY_SCHEMA,
            "verified": False,
            "errors": [
                "isolated verifier process failed before JSON report: "
                f"rc={result.returncode}; stderr={result.stderr.strip()}"
            ],
            "control_flow_oracle": "armv4t-raw-encoding",
            "independently_rebuilt_instruction_count": 0,
            "root_count": 0,
            "decoded_instruction_count": 0,
            "decoded_basic_block_count": 0,
            "reachable_instruction_bytes": 0,
            "frontier_count": 0,
            "baseline_cross_edge_count": 0,
        }
    if not isinstance(report, dict):
        raise ValueError("isolated verifier returned a non-object report")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    artifact = args.artifact_dir if args.artifact_dir.is_absolute() else args.root / args.artifact_dir
    report = verify_rom_cfg_proven_roots_v8(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
