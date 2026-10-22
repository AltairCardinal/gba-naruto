#!/usr/bin/env python3
"""Export the fixed boot-state dispatcher and its five bounded Thumb closures."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.export_rom_cfg_proven_roots_v11 import _bounded_worklist, _merged_ranges
from tools.thumb_branch import decode_thumb_b, decode_thumb_bl
from tools.verify_rom_boot_interwork_continuation import verify_artifact as verify_upstream

SCHEMA = "rom-boot-state-dispatcher-cfg-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_SIZE = 6_291_456
OFFICIAL = Path("artifacts/rom-boot-state-dispatcher-cfg-v1")
PAYLOAD_NAME = "rom-boot-state-dispatcher-cfg.json"
MANIFEST_NAME = "manifest.json"
UPSTREAM = Path("artifacts/rom-boot-interwork-continuation-v1")
UPSTREAM_FILES = (
    (UPSTREAM / MANIFEST_NAME, "beb4220307bbc0b99b58d6652bfd3f7339928d9e30b104f0fde06c7ed62d82ff"),
    (UPSTREAM / "rom-boot-interwork-continuation.json", "43ba163ac9f8313b9579c660ab701a51006186b45f2b96247fd2e58f0c16babd"),
    (Path("tools/verify_rom_boot_interwork_continuation.py"), "8da8303e47e8666a9883fc411fd274ab1d8bf3651da95a4530dabd152bdcec58"),
)
DISPATCHER = (0x064670, 0x0646D0)
DISPATCHER_SHA256 = "b825f224bf8677ace2b5936e48afcc7e3a1950ac72ed397bbdbbf1cb0af1ba51"
ROOT_SPECS = (
    ("root_63adc", 0x063ADC, 0x063C34, 0x063C2E),
    ("root_63c34", 0x063C34, 0x063F7C, 0x063F78),
    ("root_63f7c", 0x063F7C, 0x0642DC, 0x0642D8),
    ("root_642dc", 0x0642DC, 0x064394, 0x064392),
    ("root_64394", 0x064394, 0x064478, 0x064472),
)
CODE_RANGES = [[408284,408382],[408404,408452],[408456,408624],[408628,408790],
 [408816,409320],[409336,409466],[409468,409518],[409536,409770],
 [409780,409836],[409840,409896],[409904,409948],[409952,410086],
 [410096,410152],[410156,410214],[410224,410268],[410272,410330],
 [410332,410382],[410404,410586],[410604,410608],[410612,410662],
 [410668,410688],[410692,410710],[410716,410740]]
LITERAL_RANGES = [[408384,408404],[408452,408456],[408624,408628],[408792,408816],
 [409320,409336],[409520,409536],[409772,409780],[409836,409840],
 [409896,409904],[409948,409952],[410088,410096],[410152,410156],
 [410216,410224],[410268,410272],[410384,410404],[410588,410604],
 [410608,410612],[410664,410668],[410688,410692],[410712,410716],
 [410740,410744]]
HOLES = [[408382,408384],[408790,408792],[409466,409468],[409518,409520],
 [409770,409772],[410086,410088],[410214,410216],[410330,410332],
 [410382,410384],[410586,410588],[410662,410664],[410710,410712]]
CODE_SHA256 = "317a042eb54cee46eff733c8dd19be71b73b7a5b7a3d240097a5322ed6d460e4"
LITERAL_SHA256 = "026339c45f3ec48ebefe3e194933bbd62daa792bc8b9d11ffe112e2cc56e3245"
HOLE_SHA256 = "9d908ecfb6b256def8b49a7c504e6c889c4b0e41fe6ce3e01863dd7b61a20aa0"
BINDING_SHA256 = "6dc27eb222f284bc49914ed2a3dee06ae9cb0802527a8165e00de757f7caa78a"
PRODUCERS = [[0x06109A,0x064670,"bl",4,"03f0e9fa"],[0x0646B0,0x063ADC,"bl",4,"fff714fa"],
 [0x0646B6,0x063C34,"bl",4,"fff7bdfa"],[0x0646BC,0x063F7C,"bl",4,"fff75efc"],
 [0x0646C2,0x0642DC,"bl",4,"fff70bfe"],[0x0646C8,0x064394,"bl",4,"fff764fe"]]
OPAQUE_CALLS = [[408410,639204],[408708,639196],[409578,400076],[409608,400000],
 [410552,639788],[410570,639668],[410640,639788],[410672,639668]]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _safe_file(root: Path, relative: Path) -> Path:
    base = root.resolve(strict=True); cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"unsafe input path: {relative}")
    result = cursor.resolve(strict=True)
    if not result.is_relative_to(base) or not result.is_file():
        raise ValueError(f"unsafe input path: {relative}")
    return result


def _packed(rom: bytes, ranges: list[list[int]]) -> bytes:
    return b"".join(rom[a:b] for a, b in ranges)


def _upstream(root: Path) -> dict[str, Any]:
    for path, digest in UPSTREAM_FILES:
        if _sha(_safe_file(root, path).read_bytes()) != digest:
            raise ValueError("upstream continuation identity changed")
    report = verify_upstream(root, (root / UPSTREAM).resolve(strict=True))
    if report.get("verified") is not True:
        raise ValueError("upstream continuation verification failed")
    payload = json.loads(_safe_file(root, UPSTREAM_FILES[1][0]).read_bytes())
    owners = [row for row in payload["promotion"]["claims"]
              if row["range"][0] <= 0x06109A and 0x06109E <= row["range"][1]]
    if len(owners) != 1:
        raise ValueError("producer source membership changed")
    return {"verified": True, "files": {p.as_posix(): d for p, d in UPSTREAM_FILES},
            "producer_owner_claim_id": owners[0]["id"], "producer_source": 0x06109A}


def _scan_producers(rom: bytes) -> dict[str, Any]:
    targets = {row[1] for row in PRODUCERS}; found = []
    for offset in range(0, len(rom) - 1, 2):
        half = struct.unpack_from("<H", rom, offset)[0]; decoded = None
        if offset + 4 <= len(rom):
            target = decode_thumb_bl(offset, half, struct.unpack_from("<H", rom, offset + 2)[0])
            if target is not None: decoded = (target, "bl", 4)
        if decoded is None:
            target = decode_thumb_b(offset, half)
            if target is not None: decoded = (target, "b", 2)
        if decoded is None and half & 0xF000 == 0xD000 and ((half >> 8) & 15) < 14:
            delta = (half & 255) << 1
            if delta & 0x100: delta -= 0x200
            decoded = (offset + 4 + delta, "bcond", 2)
        if decoded is not None and decoded[0] in targets:
            target, kind, size = decoded; found.append([offset, target, kind, size, rom[offset:offset + size].hex()])
    if found != PRODUCERS:
        raise ValueError("producer denominator changed")
    return {"decoder_kinds": ["thumb_bl", "thumb_b", "thumb_bcond"], "range": [0, len(rom)], "stride": 2,
            "targets": sorted(targets), "matches": found, "match_count": 6,
            "vector_sha256": _sha(json.dumps(found, separators=(",", ":")).encode())}


def _dispatcher(rom: bytes) -> dict[str, Any]:
    raw = rom[DISPATCHER[0]:DISPATCHER[1]]
    if _sha(raw) != DISPATCHER_SHA256:
        raise ValueError("dispatcher identity changed")
    if rom[0x064670:0x06468E].hex() != "00b507480178002928d0072008400138052823d880000349401800688746":
        raise ValueError("dispatcher state/index semantics changed")
    if struct.unpack_from("<II", rom, 0x064690) != (0x03005CBC, 0x08064698):
        raise ValueError("dispatcher literals changed")
    slots = [struct.unpack_from("<I", rom, 0x064698 + i * 4)[0] for i in range(6)]
    expected = [0x080646CC,0x080646B0,0x080646B6,0x080646BC,0x080646C2,0x080646C8]
    if slots != expected or rom[0x0646CC:0x0646D0].hex() != "01bc0047":
        raise ValueError("dispatcher table/return changed")
    return {"range": list(DISPATCHER), "bytes_sha256": DISPATCHER_SHA256,
            "state_address": "0x03005CBC", "mask": 7, "subtract": 1,
            "unsigned_max": 5, "table_range": [0x064698,0x0646B0],
            "slots": slots, "slot_count": 6, "structured_return": 0x0646CE}


def _structured_return_contract(rom: bytes, nodes: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
    aliases = sorted(offset for (_, offset) in nodes
                     if struct.unpack_from("<H", rom, offset)[0] == 0x4668)
    stores = sorted([offset, (struct.unpack_from("<H", rom, offset)[0] & 0xFF) * 4]
                    for (_, offset) in nodes
                    if struct.unpack_from("<H", rom, offset)[0] & 0xF800 == 0x9000)
    expected_stores = [[0x063C7C,0],[0x063CA2,12],[0x063CCE,8],[0x063CD2,4],
        [0x063CF6,8],[0x063CFA,4],[0x063CFE,8],[0x063D00,4],[0x063D30,8],
        [0x063D36,8],[0x063D4E,4],[0x063D54,4],[0x063DCA,16],[0x063E26,16],
        [0x063E5E,16],[0x063ED6,12],[0x06402A,0],[0x064036,0],
        [0x064040,4],[0x06404C,4]]
    if aliases != [0x063C7E] or stores != expected_stores:
        raise ValueError("structured return SP alias/store denominator changed")
    if rom[0x063C7A:0x063C88].hex() != "1a480090684619491a4a38f02afa":
        raise ValueError("CpuFastSet callsite changed")
    if tuple(struct.unpack_from("<III", rom, 0x063CE4)) != (0xFF00FF00,0x02000A00,0x01000050):
        raise ValueError("CpuFastSet arguments changed")
    if rom[0x09C0DC:0x09C0E0].hex() != "0cdf7047":
        raise ValueError("CpuFastSet wrapper changed")
    # GBA BIOS CpuFastSet (SWI 0x0C): bit 24 requests fill mode, so this call
    # reads only the first source word at SP and writes the EWRAM destination.
    # The saved LR is SP+0x30 and no direct SP store exceeds SP+0x10.
    return {"sp_alias_sites": aliases, "sp_relative_store_sites_and_offsets": stores,
            "saved_lr_offset_at_cpufastset": 0x30, "max_direct_sp_store_offset": 0x10,
            "cpufastset_callsite": 0x063C84, "cpufastset_wrapper": 0x09C0DC,
            "cpufastset_swi": 0x0C, "source": "sp", "destination": "0x02000A00",
            "control": "0x01000050", "fill_mode": True,
            "source_read_bytes": 4, "saved_lr_slot_written": False,
            "cpufastset_source_only": True}


def _closure(rom: bytes) -> dict[str, Any]:
    nodes = {}; external = []; roots = []
    for name, root, end, return_bx in ROOT_SPECS:
        if struct.unpack_from("<H", rom, root)[0] & 0x0100 == 0:
            raise ValueError("structured return prologue changed")
        if rom[return_bx - 2:return_bx + 2].hex() != "01bc0047":
            raise ValueError("structured return epilogue changed")
        local, blocks, edges = _bounded_worklist(
            rom, root, (root, end), return_bx, target_is_producer=False)
        nodes.update(local); external.extend(edges)
        roots.append({"name": name, "root": root, "bound": [root, end],
                      "return_bx": return_bx, "instruction_count": len(local),
                      "code_bytes": sum(row["size"] for row in local.values()),
                      "basic_block_count": len(blocks)})
    code = _merged_ranges(nodes)
    bindings = []
    for (_, offset), node in sorted(nodes.items()):
        half = struct.unpack_from("<H", rom, offset)[0]
        if half & 0xF800 == 0x4800:
            literal = ((offset + 4) & ~3) + (half & 0xFF) * 4
            bindings.append([offset, literal, struct.unpack_from("<I", rom, literal)[0]])
    literals = []
    for offset in sorted({row[1] for row in bindings}):
        if literals and offset <= literals[-1][1]: literals[-1][1] = max(literals[-1][1], offset + 4)
        else: literals.append([offset, offset + 4])
    opaque = sorted([[row["source_file_offset"], row["target_file_offset"]] for row in external])
    return_contract = _structured_return_contract(rom, nodes)
    if code != CODE_RANGES or literals != LITERAL_RANGES:
        raise ValueError("target closure range denominator changed")
    if _sha(_packed(rom, code)) != CODE_SHA256 or _sha(_packed(rom, literals)) != LITERAL_SHA256:
        raise ValueError("target closure bytes changed")
    if _sha(json.dumps(bindings, separators=(",", ":")).encode()) != BINDING_SHA256:
        raise ValueError("literal binding denominator changed")
    if opaque != OPAQUE_CALLS:
        raise ValueError("opaque call denominator changed")
    if _sha(_packed(rom, HOLES)) != HOLE_SHA256:
        raise ValueError("hole denominator changed")
    return {"roots": roots, "root_count": 5, "instruction_count": len(nodes),
            "code_bytes": 2248, "code_ranges": code, "literal_reference_count": 49,
            "unique_literal_word_count": 47, "literal_bytes": 188,
            "literal_ranges": literals, "opaque_calls": opaque, "opaque_call_count": 8,
            "structured_return_count": 5, "frontier_count": 0,
            "structured_return_contract": return_contract,
            "preserved_unknown_holes": HOLES, "preserved_unknown_bytes": 24}


def _build_from_rom(root: Path, rom: bytes, *, verify_identity: bool = True) -> dict[str, Any]:
    if verify_identity and (len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256):
        raise ValueError("ROM identity changed")
    upstream = _upstream(root); producers = _scan_producers(rom)
    dispatcher = _dispatcher(rom); closure = _closure(rom)
    claims = []
    for kind, ranges in (("reachable_thumb_code", CODE_RANGES),
                         ("consumed_literal_words", LITERAL_RANGES)):
        for i, (start, end) in enumerate(ranges, 1):
            claims.append({"id": f"boot-state-{kind}-{i:02d}-{start:06x}",
                           "range": [start, end], "claim_kind": kind,
                           "bytes_sha256": _sha(rom[start:end])})
    claims.append({"id": "boot-state-dispatcher-064670", "range": list(DISPATCHER),
                   "claim_kind": "bounded_state_dispatcher_bytes",
                   "bytes_sha256": DISPATCHER_SHA256})
    return {"schema": SCHEMA, "rom": {"path": ROM_PATH.as_posix(), "size": len(rom),
            "sha256": ROM_SHA256}, "upstream_continuation": upstream,
            "producer_denominator": producers, "dispatcher": dispatcher,
            "target_closure": closure, "promotion": {"promotion_batch": SCHEMA,
            "promoted_from_primary_class": "unknown", "claims": claims,
            "claim_count": 45, "target_code_bytes": 2248, "target_literal_bytes": 188,
            "dispatcher_bytes": 96, "promotion_bytes": 2532},
            "scope": {"natural_runtime_reachability": False,
            "ram_state_writer_denominator": False, "opaque_callee_semantics": False,
            "padding_or_free_space": False, "editing_or_relocation_safety": False}}


def build_payload(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    return _build_from_rom(root, _safe_file(root, ROM_PATH).read_bytes())


def export_artifact(root: Path, output: Path) -> Path:
    root = root.resolve(strict=True); lexical = output if output.is_absolute() else root / output
    for parent in [lexical, *lexical.parents]:
        if parent == root: break
        if parent.is_symlink(): raise ValueError("output has symlink ancestor")
    output = lexical.resolve(strict=False)
    if not output.is_relative_to(root) or output.exists(): raise FileExistsError("output exists or escapes root")
    payload = build_payload(root); raw = _canonical(payload)
    exporter = Path("tools/export_rom_boot_state_dispatcher_cfg.py")
    verifier = Path("tools/verify_rom_boot_state_dispatcher_cfg.py")
    test = Path("tests/test_export_rom_boot_state_dispatcher_cfg.py")
    manifest = {"schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,
        "artifact_status": "accepted", "files": {PAYLOAD_NAME: {"size": len(raw), "sha256": _sha(raw)}},
        "summary": {"root_count": 5, "promotion_bytes": 2532, "frontier_count": 0},
        "producer": {"command": ["python3", exporter.as_posix(), "--root", ".", "--output", output.relative_to(root).as_posix()]},
        "verifier": {"command": ["python3", verifier.as_posix(), "--root", ".", "--artifact", output.relative_to(root).as_posix()]},
        "implementation": {"exporter_sha256": _sha(_safe_file(root, exporter).read_bytes()),
            "verifier_sha256": _sha(_safe_file(root, verifier).read_bytes()),
            "test_sha256": _sha(_safe_file(root, test).read_bytes())}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".boot-state-") as directory:
        stage = Path(directory) / output.name; stage.mkdir()
        (stage / PAYLOAD_NAME).write_bytes(raw); (stage / MANIFEST_NAME).write_bytes(_canonical(manifest))
        from tools.verify_rom_boot_state_dispatcher_cfg import verify_artifact
        report = verify_artifact(root, stage, expected_artifact=output)
        if not report["verified"]: raise ValueError(report["errors"])
        if output.exists(): raise FileExistsError("output appeared during export")
        os.rename(stage, output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--root", type=Path, default=Path(".")); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); export_artifact(args.root, args.output); return 0


if __name__ == "__main__": raise SystemExit(main())
