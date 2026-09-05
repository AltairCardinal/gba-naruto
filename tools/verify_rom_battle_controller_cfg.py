#!/usr/bin/env python3
"""Independently verify the corrected range-bounded battle-controller CFG."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import heapq
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from tools.verify_rom_cfg_inventory import (
    MAX_BLOCK_INSTRUCTION_COUNT,
    MAX_INSTRUCTION_COUNT,
    ROM_PATH,
    _decode,
    _safe_file,
    _sha,
    _union_bytes,
    _verify_blocks,
)


ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

SCHEMA = "rom-battle-controller-cfg-v1"
VERIFY_SCHEMA = "rom-battle-controller-cfg-verification-v1"
PAYLOAD_NAME = "rom-battle-controller-cfg.json"
MANIFEST_NAME = "manifest.json"

CONTROLLER_RANGE = (0x732B4, 0x7509C)
CONTROLLER_SHA256 = (
    "c9bdc220590a851fa331960bcb32be90eb9ac7248a5cd3dabb9f8afa0b674bc1"
)
DISPATCH_RANGE = (0x733A0, 0x735CA)
DISPATCH_SHA256 = "43fe396227bb6815aeedd5c48783effdb842194634360999d3e42f0ee316e2b1"
DEFAULT_TARGET = 0x7504E
DISPATCH_MAPPING_VECTOR_SHA256 = (
    "ce5e8ea24e274c4456482611609ee90144d31e064fccf0d85bf8f4643f44ac15"
)

# §9.1 #4 — frozen baseline JSON payload raw-byte identity table.
# Independently defined in the verifier so the verifier never imports the
# exporter (already enforced by ``VerifierExporterBoundaryTests``).  Each
# entry is the SHA256 of the canonical raw bytes of one of the four frozen
# CFG baseline artifacts; ``_baseline_occupied_bytes`` reads each payload's
# raw bytes and compares the SHA256 against this table before parsing JSON.
# Any deviation — constant key set not exactly the four expected paths, a
# missing key for a payload we look up, or a raw SHA256 mismatch — fails
# closed with ``ValueError`` before any JSON parsing happens.
FROZEN_BASELINE_PAYLOAD_SHA256: dict[str, str] = {
    "artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json": (
        "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd"
    ),
    "artifacts/rom-cfg-inventory-v3/rom-cfg-inventory-v3.json": (
        "596c4d8cffa57f3899858a0a59351894b1398006ee0405ce799ed9f32a81bf9d"
    ),
    "artifacts/rom-cfg-proven-roots-v1/rom-cfg-proven-roots.json": (
        "7fdee7d0d62d3a8c82bfe7b03804e9cb0e3d213ebdf63acce6b0533045aecf54"
    ),
    "artifacts/rom-cfg-proven-roots-v2/rom-cfg-proven-roots-v2.json": (
        "a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba"
    ),
}

EXISTING_PRODUCER_RANGES: tuple[tuple[int, int], ...] = (
    (0x73688, 0x7368C),
    (0x73690, 0x73694),
    (0x7425A, 0x7425E),
    (0x7434E, 0x74352),
    (0x7443C, 0x74440),
    (0x74448, 0x7444C),
    (0x74918, 0x7491C),
    (0x74F2C, 0x74F30),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _canonical_sha(value: object) -> str:
    return _sha256(_canonical_json(value))


def _signed(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value & (sign - 1)) - (value & sign)


def _u16(rom: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(rom):
        raise ValueError("dispatcher instruction escapes ROM")
    return int.from_bytes(rom[offset : offset + 2], "little")


def _thumb_bl_target(offset: int, first: int, second: int) -> int:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError("dispatcher contains malformed Thumb BL")
    displacement = (_signed(first & 0x07FF, 11) << 12) + (
        (second & 0x07FF) << 1
    )
    return offset + 4 + displacement


def _dispatch_one(rom: bytes, state: int) -> dict[str, Any]:
    """Independent reimplementation of the fixed Thumb-1 dispatcher.

    Produces the same record shape as the exporter's dispatcher so the
    mapping SHA-256 reproduces the frozen value.
    """

    if state < 0 or state > 0xFFFF:
        raise ValueError("dispatcher input is not a u16")
    start, end = DISPATCH_RANGE
    controller_start, controller_end = CONTROLLER_RANGE
    registers: dict[int, int] = {6: state}
    compared: tuple[int, int] | None = None
    offset = start
    path: list[dict[str, Any]] = []

    for _ in range(256):
        if offset < start or offset >= end or offset % 2:
            raise ValueError("dispatcher entered an invalid instruction boundary")
        first = _u16(rom, offset)
        size = 2
        next_offset = offset + size

        if first & 0xF800 == 0x2000:  # MOVS
            registers[(first >> 8) & 7] = first & 0xFF
            operation = "movs_imm"
        elif first & 0xF800 == 0x0000:  # LSLS
            immediate = (first >> 6) & 0x1F
            source = (first >> 3) & 7
            destination = first & 7
            registers[destination] = (registers[source] << immediate) & 0xFFFFFFFF
            operation = "lsls_imm"
        elif first & 0xFFC0 == 0x4280:  # CMP Rn, Rm
            compared = (
                registers[first & 7] & 0xFFFFFFFF,
                registers[(first >> 3) & 7] & 0xFFFFFFFF,
            )
            operation = "cmp_reg"
        elif first & 0xF800 == 0x2800:  # CMP Rn, #imm8
            compared = (registers[(first >> 8) & 7] & 0xFFFFFFFF, first & 0xFF)
            operation = "cmp_imm"
        elif first & 0xF800 in (0x3000, 0x3800):  # ADDS/SUBS
            register = (first >> 8) & 7
            delta = first & 0xFF
            registers[register] = (
                (registers[register] - delta)
                if first & 0xF800 == 0x3800
                else (registers[register] + delta)
            ) & 0xFFFFFFFF
            operation = "subs_imm" if first & 0xF800 == 0x3800 else "adds_imm"
        elif first & 0xF800 == 0x4800:  # LDR Rt, [PC, #imm8*4]
            register = (first >> 8) & 7
            literal = ((offset + 4) & ~3) + ((first & 0xFF) << 2)
            registers[register] = int.from_bytes(rom[literal : literal + 4], "little")
            operation = "ldr_literal"
        elif first & 0xF000 == 0xD000:  # conditional branch
            condition = (first >> 8) & 0xF
            left, right = compared if compared is not None else (0, 0)
            if condition == 0x1:
                operation = "bne"
                take = left != right
            elif condition == 0xC:
                operation = "bgt"
                signed_left = left if left < 0x80000000 else left - 0x100000000
                signed_right = right if right < 0x80000000 else right - 0x100000000
                take = signed_left > signed_right
            else:
                raise ValueError("dispatcher uses an unsupported condition")
            if take:
                next_offset = offset + 4 + (_signed(first & 0xFF, 8) << 1)
        elif first & 0xF800 == 0xE000:  # unconditional B
            operation = "b"
            target = offset + 4 + (_signed(first & 0x07FF, 11) << 1)
            raw = rom[offset : offset + 2]
            path.append(
                {
                    "offset": offset,
                    "size": 2,
                    "raw_hex": raw.hex(),
                    "operation": operation,
                }
            )
            if controller_start <= target < controller_end and target % 2 == 0:
                result = {
                    "target_offset": target,
                    "transfer_offset": offset,
                    "transfer_kind": "branch_target",
                    "transfer_raw_hex": raw.hex(),
                }
                if target != DEFAULT_TARGET:
                    result["decision_path_sha256"] = _canonical_sha(path)
                return result
            raise ValueError("dispatcher branch target escapes the controller")
        elif first & 0xF800 == 0xF000:  # BL
            operation = "bl"
            second = _u16(rom, offset + 2)
            target = _thumb_bl_target(offset, first, second)
            size = 4
            next_offset = offset + size
            raw = rom[offset : offset + size]
            path.append(
                {
                    "offset": offset,
                    "size": size,
                    "raw_hex": raw.hex(),
                    "operation": operation,
                }
            )
            if controller_start <= target < controller_end and target % 2 == 0:
                result = {
                    "target_offset": target,
                    "transfer_offset": offset,
                    "transfer_kind": "call_target",
                    "transfer_raw_hex": raw.hex(),
                }
                if target != DEFAULT_TARGET:
                    result["decision_path_sha256"] = _canonical_sha(path)
                return result
            raise ValueError("dispatcher call target escapes the controller")
        else:
            raise ValueError(
                f"dispatcher uses unsupported Thumb encoding 0x{first:04X} "
                f"at 0x{offset:06X}"
            )

        path.append(
            {
                "offset": offset,
                "size": size,
                "raw_hex": rom[offset : offset + size].hex(),
                "operation": operation,
            }
        )
        offset = next_offset
    raise ValueError("dispatcher execution budget exhausted")


def _rebuild_dispatcher(rom: bytes) -> dict[str, Any]:
    """Independently rebuild the dispatcher 65,536→38 mapping.

    The mapping record shape matches the exporter exactly so the canonical
    mapping SHA-256 reproduces the frozen value.
    """

    if len(rom) != ROM_SIZE or _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    if _sha256(rom[CONTROLLER_RANGE[0]:CONTROLLER_RANGE[1]]) != CONTROLLER_SHA256:
        raise ValueError("battle-controller body changed")
    if _sha256(rom[DISPATCH_RANGE[0]:DISPATCH_RANGE[1]]) != DISPATCH_SHA256:
        raise ValueError("battle-controller dispatcher changed")
    targets: dict[int, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for state in range(0x10000):
        outcome = _dispatch_one(rom, state)
        targets[outcome["target_offset"]].append((state, outcome))
    defaults = targets.pop(DEFAULT_TARGET, [])
    if len(defaults) + sum(len(v) for v in targets.values()) != 0x10000:
        raise ValueError("dispatcher input denominator is incomplete")
    mappings: list[dict[str, Any]] = []
    for target, members in sorted(targets.items()):
        if len(members) != 1:
            raise ValueError(
                f"dispatcher target 0x{target:06X} has {len(members)} sources"
            )
        state, outcome = members[0]
        entry = rom[target : target + 4]
        mapping = {
            "state": state,
            "state_hex": f"0x{state:04X}",
            "target_offset": target,
            "target_gba_address": f"0x{ROM_BASE + target:08X}",
            "entry_size": len(entry),
            "entry_sha256": _sha256(entry),
            "transfer_offset": outcome["transfer_offset"],
            "transfer_kind": outcome["transfer_kind"],
            "transfer_raw_hex": outcome["transfer_raw_hex"],
        }
        if "decision_path_sha256" in outcome:
            mapping["decision_path_sha256"] = outcome["decision_path_sha256"]
        mappings.append(mapping)
    mappings.sort(key=lambda item: item["state"])
    default_transfers = {
        (
            outcome["transfer_offset"],
            outcome["transfer_kind"],
            outcome["transfer_raw_hex"],
        ): {
            "target_offset": DEFAULT_TARGET,
            "transfer_offset": outcome["transfer_offset"],
            "transfer_kind": outcome["transfer_kind"],
            "transfer_raw_hex": outcome["transfer_raw_hex"],
        }
        for _state, outcome in defaults
    }
    return {
        "input_domain": [0, 0x10000],
        "input_denominator": 0x10000,
        "nondefault_state_count": len(mappings),
        "default_state_count": len(defaults),
        "default_target": DEFAULT_TARGET,
        "dispatcher_range": list(DISPATCH_RANGE),
        "dispatcher_sha256": DISPATCH_SHA256,
        "default_transfers": [
            default_transfers[key] for key in sorted(default_transfers)
        ],
        "mappings": mappings,
        "mapping_vector_sha256": _canonical_sha(mappings),
    }


def _baseline_middle_error(offset: int, kind: str) -> ValueError:
    return ValueError(
        f"{kind} target 0x{offset:06X} lands inside a frozen baseline "
        "instruction middle byte; only legal baseline instruction entry "
        "points may be opaque stops"
    )


def _baseline_occupied_bytes(
    root: Path, rom: bytes
) -> tuple[set[int], set[tuple[str, int]]]:
    """Independently rebuild frozen baseline occupied bytes and the legal
    instruction entries inside every baseline block.

    §9.1 #4: only block-start shortcuts fail closed; the verifier must
    independently walk each baseline block through ``_decode`` so a
    single instruction whose decoded size disagrees with the block range
    or whose ``bytes_sha256`` disagrees with the ROM bytes cannot slip
    through as opaque.  ``occupied`` covers every byte inside every block
    range; ``exact_entries`` contains the exact ``(mode, file_offset)``
    of every accepted baseline instruction (one entry per decoded
    instruction, not just the block start).

    Identity contract: each payload's raw bytes are read first and
    compared against ``FROZEN_BASELINE_PAYLOAD_SHA256`` by relative path.
    Any deviation — constant key set not exactly the four expected paths,
    a missing key for a payload we look up, or a raw SHA256 mismatch —
    fails closed with ``ValueError`` before any JSON parsing happens.
    Only after the identity check passes do we ``json.loads(raw)`` and
    run the per-block semantic validation.
    """

    expected_paths = frozenset(FROZEN_BASELINE_PAYLOAD_SHA256.keys())
    canonical_paths = frozenset(
        {
            "artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json",
            "artifacts/rom-cfg-inventory-v3/rom-cfg-inventory-v3.json",
            "artifacts/rom-cfg-proven-roots-v1/rom-cfg-proven-roots.json",
            "artifacts/rom-cfg-proven-roots-v2/rom-cfg-proven-roots-v2.json",
        }
    )
    if expected_paths != canonical_paths or len(expected_paths) != 4:
        raise ValueError(
            "FROZEN_BASELINE_PAYLOAD_SHA256 must contain exactly the four "
            "frozen baseline payload paths; missing="
            f"{sorted(canonical_paths - expected_paths)}, extra="
            f"{sorted(expected_paths - canonical_paths)}"
        )

    occupied: set[int] = set()
    entries: set[tuple[str, int]] = set()
    for artifact_path, payload_name in (
        ("artifacts/rom-cfg-inventory-v2", "rom-cfg-inventory.json"),
        ("artifacts/rom-cfg-inventory-v3", "rom-cfg-inventory-v3.json"),
        ("artifacts/rom-cfg-proven-roots-v1", "rom-cfg-proven-roots.json"),
        ("artifacts/rom-cfg-proven-roots-v2", "rom-cfg-proven-roots-v2.json"),
    ):
        relative_path = f"{artifact_path}/{payload_name}"
        try:
            raw = _safe_file(root, Path(artifact_path) / payload_name).read_bytes()
        except (OSError, ValueError) as error:
            raise ValueError(
                f"frozen baseline payload is unreadable: {relative_path}"
            ) from error
        # §9.1 #4 identity check: raw SHA must match the module constant
        # BEFORE any JSON parsing.  No artefact self-reported hash, no
        # canonical-JSON normalisation before hashing.
        expected_sha = FROZEN_BASELINE_PAYLOAD_SHA256.get(relative_path)
        if expected_sha is None:
            raise ValueError(
                f"frozen baseline payload path is not in the identity table: "
                f"{relative_path}"
            )
        actual_sha = _sha(raw)
        if actual_sha != expected_sha:
            raise ValueError(
                f"frozen baseline payload SHA mismatch: {relative_path} "
                f"expected={expected_sha} actual={actual_sha}"
            )
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError(
                f"frozen baseline payload is not valid JSON: {relative_path}"
            ) from error
        if payload.get("schema") in {
            "rom-cfg-inventory-v2",
            "rom-cfg-inventory-v3",
            "rom-cfg-proven-roots-v1",
            "rom-cfg-proven-roots-v2",
        }:
            blocks = payload.get("blocks") or payload.get("extension", {}).get(
                "blocks"
            )
        else:
            raise ValueError(
                f"frozen baseline payload schema is not recognised: "
                f"{payload.get('schema')}"
            )
        if not isinstance(blocks, list):
            raise ValueError(f"frozen baseline blocks missing: {artifact_path}")
        for block in blocks:
            if not isinstance(block, dict):
                raise ValueError("frozen baseline block invalid")
            value = block.get("range")
            if (
                not isinstance(value, list)
                or len(value) != 2
                or any(type(byte) is not int for byte in value)
            ):
                raise ValueError("frozen baseline block range invalid")
            start, end = value
            if start < 0 or start >= end or end > len(rom):
                raise ValueError("frozen baseline block range escapes ROM")

            mode = block.get("mode")
            if mode not in {"thumb", "arm"}:
                raise ValueError(
                    f"frozen baseline block mode invalid: {artifact_path} -> {mode!r}"
                )

            instruction_count = block.get("instruction_count")
            if type(instruction_count) is not int or instruction_count <= 0:
                raise ValueError("frozen baseline instruction_count invalid")
            bytes_sha256 = block.get("bytes_sha256")
            if (
                not isinstance(bytes_sha256, str)
                or len(bytes_sha256) != 64
                or any(
                    character not in "0123456789abcdef" for character in bytes_sha256
                )
                or _sha(rom[start:end]) != bytes_sha256
            ):
                raise ValueError("frozen baseline block bytes_sha256 mismatch")

            offset = start
            decoded_count = 0
            while offset < end:
                instruction = _decode(rom, offset, mode)
                if (
                    not isinstance(instruction, dict)
                    or not instruction.get("accepted")
                ):
                    raise ValueError("frozen baseline instruction rejected")
                if instruction.get("mode") != mode:
                    raise ValueError("frozen baseline instruction mode mismatch")
                if instruction.get("file_offset") != offset:
                    raise ValueError("frozen baseline instruction offset mismatch")
                size = instruction.get("size")
                if type(size) is not int or size <= 0:
                    raise ValueError("frozen baseline instruction size invalid")
                instruction_end = offset + size
                if instruction_end > end:
                    raise ValueError(
                        "frozen baseline instruction escapes block end"
                    )

                entries.add((mode, offset))
                occupied.update(range(offset, instruction_end))
                decoded_count += 1
                offset = instruction_end

            if offset != end:
                raise ValueError("frozen baseline block decode did not end exactly")
            if decoded_count != instruction_count:
                raise ValueError("frozen baseline instruction_count mismatch")
    return occupied, entries


def _producer_occupied_bytes() -> tuple[set[int], set[tuple[str, int]]]:
    """Independent reimplementation of the producer-byte opaque set.

    These bytes are already classified as cfg_proven_roots_*_direct_thumb_bl_producer
    claims and must not appear in the bounded CFG reachable set.  Each
    4-byte Thumb BL contributes only its **start** as a legal instruction
    entry — the remaining three bytes are opaque occupied bytes whose
    legal entry has already been audited upstream.
    """

    occupied: set[int] = set()
    entries: set[tuple[str, int]] = set()
    for start, end in EXISTING_PRODUCER_RANGES:
        if end - start != 4:
            raise ValueError(
                f"existing producer range is not a 4-byte Thumb BL: "
                f"[0x{start:06X}, 0x{end:06X})"
            )
        entries.add(("thumb", start))
        for byte in range(start, end):
            occupied.add(byte)
    return occupied, entries


def _rebuild_bounded(
    rom: bytes,
    roots: list[dict[str, Any]],
    baseline_occupied: set[int],
    *,
    baseline_entries: set[tuple[str, int]] | None = None,
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], list[tuple[tuple[str, int], str]]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Independently rebuild the bounded CFG traversal.

    §9.1 #4: every byte covered by the four frozen baseline artifacts
    plus the eight frozen producer ranges must be treated as opaque
    stop targets; only the **exact legal instruction entry** offset of
    every frozen baseline instruction may yield an opaque
    ``frozen_baseline_entry`` edge.  An edge whose target lands in
    ``baseline_occupied`` but whose ``(mode, offset)`` is not in
    ``baseline_entries`` is a baseline-middle violation and must fail
    closed — silently mis-labelling such a hit would let the bounded
    CFG drop an instruction from the worklist under the
    ``frozen_baseline_entry`` reason, which is precisely the bug the
    hand-off forbids.
    """

    if baseline_entries is None:
        baseline_entries = set()
    controller_start, controller_end = CONTROLLER_RANGE
    pending: list[tuple[int, int, str]] = []
    scheduled: set[tuple[str, int]] = set()
    skipped: list[dict[str, Any]] = []
    for root in roots:
        item = ("thumb", root["target_offset"])
        if item[1] in baseline_occupied:
            if item not in baseline_entries:
                raise _baseline_middle_error(item[1], "dedup root")
            skipped.append(
                {
                    "source": {"file_offset": item[1], "mode": item[0]},
                    "edge_kind": "root_entry",
                    "target_mode": item[0],
                    "target_file_offset": item[1],
                    "reason": "frozen_baseline_entry",
                }
            )
            continue
        if item[1] < controller_start or item[1] >= controller_end:
            raise ValueError("dedup root escapes the controller range")
        if item[1] % 2:
            raise ValueError("dedup root is misaligned")
        if item not in scheduled:
            heapq.heappush(pending, (item[1], 1, item[0]))
            scheduled.add(item)
    nodes: dict[tuple[str, int], dict[str, Any]] = {}
    rejected: dict[tuple[str, int], dict[str, Any]] = {}
    incoming: dict[
        tuple[str, int], list[tuple[tuple[str, int], str]]
    ] = defaultdict(list)
    opaque_edges: list[dict[str, Any]] = []
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in nodes or item in rejected:
            continue
        if offset in baseline_occupied:
            raise _baseline_middle_error(offset, "bounded traversal")
        if len(nodes) >= MAX_INSTRUCTION_COUNT:
            raise ValueError("bounded CFG instruction budget exhausted")
        decoded = _decode(rom, offset, mode)
        if not decoded["accepted"]:
            rejected[item] = decoded
            continue
        if any(
            byte in baseline_occupied
            for byte in range(offset, offset + decoded["size"])
        ):
            raise _baseline_middle_error(offset, "bounded instruction")
        nodes[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            target_offset = target[1]
            in_range = (
                controller_start <= target_offset < controller_end
                and target[0] == "thumb"
                and target_offset % 2 == 0
                and 0 <= target_offset < len(rom)
            )
            if not in_range:
                opaque_edges.append(
                    {
                        "source": {"file_offset": offset, "mode": mode},
                        "edge_kind": edge["kind"],
                        "target_mode": target[0],
                        "target_file_offset": target_offset,
                        "reason": "outside_controller_range",
                    }
                )
                continue
            if any(
                byte in baseline_occupied
                for byte in range(target_offset, target_offset + 2)
            ):
                if target not in baseline_entries:
                    raise _baseline_middle_error(target_offset, "CFG edge")
                opaque_edges.append(
                    {
                        "source": {"file_offset": offset, "mode": mode},
                        "edge_kind": edge["kind"],
                        "target_mode": target[0],
                        "target_file_offset": target_offset,
                        "reason": "frozen_baseline_entry",
                    }
                )
                continue
            incoming[target].append((item, edge["kind"]))
            if target not in scheduled:
                heapq.heappush(pending, (target[1], 1, target[0]))
                scheduled.add(target)
    return nodes, rejected, incoming, opaque_edges, skipped


def _expected_frontiers(
    rom: bytes,
    blocks: list[dict[str, Any]],
    decoded_last: list[dict[str, Any]],
    entries: dict[tuple[str, int], dict[str, Any]],
    rejected: dict[tuple[str, int], dict[str, Any]],
    opaque_targets: set[tuple[str, int]],
    roots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expected_frontiers: list[dict[str, Any]] = []
    for block, decoded in zip(blocks, decoded_last, strict=True):
        expected_edges = []
        for edge in decoded["successors"]:
            target_key = (edge["mode"], edge["file_offset"])
            if target_key in opaque_targets:
                continue
            target_block = entries.get(target_key)
            if target_block is not None:
                expected_edges.append({**edge, "block_id": target_block["id"]})
                continue
            rejected_record = rejected.get(target_key)
            if rejected_record is None:
                raise ValueError(
                    f"verifier omits a successor at 0x{edge['file_offset']:06X}"
                )
            expected_frontiers.append(
                {
                    "source": {
                        "kind": "block",
                        "block_id": block["id"],
                        "instruction_offset": decoded["file_offset"],
                        "edge_kind": edge["kind"],
                    },
                    "reason": rejected_record["frontier_reason"],
                    "target": {
                        "mode": edge["mode"],
                        "file_offset": edge["file_offset"],
                    },
                }
            )
        if block.get("successors") != expected_edges:
            raise ValueError(f"block successors changed: {block['id']}")
        for frontier in decoded["frontiers"]:
            expected_frontiers.append(
                {
                    "source": {
                        "kind": "block",
                        "block_id": block["id"],
                        "instruction_offset": decoded["file_offset"],
                    },
                    **frontier,
                }
            )
    expected_frontiers.sort(
        key=lambda record: json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    )
    return [
        {"id": f"frontier-{index:06d}", **record}
        for index, record in enumerate(expected_frontiers)
    ]


def _expected_opaque_edges(
    rebuilt_opaque: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records = [
        {
            "source": edge["source"],
            "edge_kind": edge["edge_kind"],
            "target_mode": edge["target_mode"],
            "target_file_offset": edge["target_file_offset"],
            "reason": edge["reason"],
        }
        for edge in rebuilt_opaque
    ]
    records.sort(
        key=lambda item: (
            item["source"]["file_offset"],
            item["source"]["mode"],
            item["edge_kind"],
            item["target_file_offset"],
            item["target_mode"],
        )
    )
    return records


def _summary(
    blocks: list[dict[str, Any]],
    frontiers: list[dict[str, Any]],
    opaque_edges: list[dict[str, Any]],
) -> dict[str, Any]:
    decoded_last_count = len(blocks)
    decoded_instruction_count = sum(block["instruction_count"] for block in blocks)
    reachable_bytes = _union_bytes(
        [
            (block["range"][0], block["range"][1])
            for block in blocks
            if block["mode"] == "thumb"
        ]
    )
    frontier_reasons = Counter(
        item.get("reason") for item in frontiers if item.get("reason") is not None
    )
    return {
        "decoded_basic_block_count": decoded_last_count,
        "decoded_instruction_count": decoded_instruction_count,
        "frontier_count": len(frontiers),
        "frontier_reasons": dict(sorted(frontier_reasons.items())),
        "reachable_instruction_bytes": reachable_bytes,
        "opaque_external_edge_count": sum(
            1 for item in opaque_edges if item["reason"] == "outside_controller_range"
        ),
        "opaque_baseline_edge_count": sum(
            1 for item in opaque_edges if item["reason"] == "frozen_baseline_entry"
        ),
        "skipped_root_count": sum(
            1 for item in opaque_edges if item.get("edge_kind") == "root_entry"
        ),
    }


def _derive_rebuilt_skipped_root_targets(
    rebuilt_skipped: list[dict[str, Any]],
) -> set[int]:
    """Derive the independently-skipped root-target offsets (§9.1 #5).

    The bounded-CFG rebuild independently classifies each dedup root
    that lands on a frozen-baseline legal entry as a
    ``frozen_baseline_entry`` edge and records it in ``rebuilt_skipped``
    with ``edge_kind="root_entry"``.  That is the sole signal the
    verifier uses to populate ``independently_skipped_root_targets``;
    the artifact's own ``entry_block_id`` / ``reachable_instruction_count``
    are NEVER consulted here because inferring the skip from the
    artifact side would let a tampered artifact bypass the closure
    check.

    Returns a ``set[int]`` of the ``target_file_offset`` values, each
    validated as ``int``.  Any record whose shape disagrees fails
    closed: the assumption is that ``_rebuild_bounded`` already
    validated every record's shape before it appended to its
    ``skipped`` list, so a shape disagreement here is a real
    inconsistency rather than silent corruption.
    """

    if not isinstance(rebuilt_skipped, list):
        raise ValueError("rebuilt_skipped is not a list")
    targets: set[int] = set()
    for index, edge in enumerate(rebuilt_skipped):
        if not isinstance(edge, dict):
            raise ValueError(
                f"rebuilt_skipped {index} is not an object: "
                f"{type(edge).__name__}"
            )
        if edge.get("edge_kind") != "root_entry":
            # The skip-set derivation only accepts ``root_entry``
            # edges from the bounded CFG rebuild; every other
            # opaque-edge reason (``outside_controller_range``,
            # ``frozen_baseline_entry`` on a non-root edge, etc.)
            # belongs to a different code path and must NOT feed the
            # per-root allowlist.
            continue
        if edge.get("reason") != "frozen_baseline_entry":
            continue
        target = edge.get("target_file_offset")
        if type(target) is not int:
            raise ValueError(
                f"rebuilt_skipped {index} target_file_offset is not an "
                f"int: {type(target).__name__}"
            )
        targets.add(target)
    return targets


def _expected_root_records(
    root_records: list[dict[str, Any]],
    blocks: list[dict[str, Any]],
    member_to_block: dict[tuple[str, int], str],
    *,
    independently_skipped_root_targets: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Independently rebuild per-root reachable counts via a
    block-successor worklist (§9.1 #5).

    Each returned record contains four keys:

    * ``target_offset`` — round-tripped from the input root.
    * ``entry_block_id`` — looked up via ``member_to_block`` from the
      root's ``("thumb", target_offset)``, or ``None`` for any root
      whose target lands in ``independently_skipped_root_targets``
      and therefore escapes the block map (the producer-side
      frozen-baseline case).
    * ``reachable_instruction_count`` — total number of mapped
      ``(mode, file_offset)`` keys for every block reached by walking
      ``blocks[*].successors[*].block_id`` from the entry block, or
      ``0`` when the root is in the skip set.
    * ``source_states`` — round-tripped from the input root.

    The skip set is a keyword-only parameter precisely because the
    decision must come from the caller (the bounded-CFG rebuild that
    independently classifies each ``root_entry`` as
    ``frozen_baseline_entry``); inferring skip from the artifact's
    ``entry_block_id`` or ``reachable_instruction_count`` would let a
    tampered artifact silently bypass the closure check.

    Fails closed on:

    * a ``independently_skipped_root_targets`` whose type is not
      ``set`` or whose elements are not ``int``;
    * a root that is both mapped via ``member_to_block`` AND listed
      in ``independently_skipped_root_targets`` (contradictory
      evidence — the root cannot be a member of a block AND be
      an opaque skip at the same time);
    * a root whose ``("thumb", target_offset)`` is missing from
      ``member_to_block`` and is NOT in ``independently_skipped_root_targets``;
    * a dangling successor whose ``block_id`` is absent from the
      supplied ``blocks`` list;
    * a duplicated ``block["id"]`` inside ``blocks``.
    """

    if not isinstance(root_records, list):
        raise ValueError("root_records is not a list")
    if not isinstance(blocks, list):
        raise ValueError("blocks is not a list")
    if not isinstance(member_to_block, dict):
        raise ValueError("member_to_block is not a dict")

    # §9.1 #5: validate the skip-set type strictly.  A non-int
    # element here would let a tampered artifact smuggle in a
    # string-shaped "offset" that the lookup later compares with
    # an int target; the early type check closes that gap.
    if independently_skipped_root_targets is None:
        skip_set: set[int] = set()
    elif not isinstance(independently_skipped_root_targets, set):
        raise ValueError(
            "independently_skipped_root_targets must be a set[int]; "
            f"got {type(independently_skipped_root_targets).__name__}"
        )
    elif any(type(item) is not int for item in independently_skipped_root_targets):
        raise ValueError(
            "independently_skipped_root_targets must contain only int "
            "target offsets; a non-int element breaks the lookup"
        )
    else:
        skip_set = independently_skipped_root_targets

    block_index: dict[str, dict[str, Any]] = {}
    for block in blocks:
        if not isinstance(block, dict):
            raise ValueError("blocks entry is not an object")
        block_id = block.get("id")
        if not isinstance(block_id, str) or not block_id:
            raise ValueError("block id is missing")
        if block_id in block_index:
            raise ValueError(f"duplicate block id: {block_id!r}")
        block_index[block_id] = block

    members_by_block: dict[str, set[tuple[str, int]]] = {}
    for member_key, block_id in member_to_block.items():
        if not isinstance(member_key, tuple) or len(member_key) != 2:
            raise ValueError("member_to_block key is not a (mode, offset) tuple")
        mode, _offset = member_key
        if mode not in {"thumb", "arm"}:
            raise ValueError(f"member_to_block key mode is invalid: {mode!r}")
        if block_id not in block_index:
            raise ValueError(f"member_to_block points at unknown block: {block_id!r}")
        members_by_block.setdefault(block_id, set()).add(member_key)

    expected: list[dict[str, Any]] = []
    for record in root_records:
        if not isinstance(record, dict):
            raise ValueError("root record is not an object")
        target = record.get("target_offset")
        source_states = record.get("source_states")
        if not isinstance(target, int):
            raise ValueError("root target_offset is not an int")
        if not isinstance(source_states, list):
            raise ValueError("root source_states is not a list")

        key = ("thumb", target)
        entry_block_id = member_to_block.get(key)
        if entry_block_id is not None:
            if target in skip_set:
                # Contradictory evidence: the same target cannot be a
                # member of a block AND be an independently-skipped
                # opaque stop.  Fail closed; do not silently emit
                # the (None, 0) shape, because the caller's skip set
                # must be the precise allowlist of escaped targets.
                raise ValueError(
                    f"root target is both mapped to block "
                    f"{entry_block_id!r} and listed in "
                    f"independently_skipped_root_targets: 0x{target:06X}"
                )
        elif target in skip_set:
            # §9.1 #5: the bounded-CFG rebuild classified this root as
            # a frozen_baseline_entry opaque stop.  Emit a
            # (None, 0) record; round-trip target_offset and
            # source_states verbatim.
            expected.append(
                {
                    "target_offset": target,
                    "entry_block_id": None,
                    "reachable_instruction_count": 0,
                    "source_states": source_states,
                }
            )
            continue
        else:
            raise ValueError(
                f"root target escapes blocks: 0x{target:06X}"
            )

        visited: set[str] = set()
        pending: list[str] = [entry_block_id]
        while pending:
            block_id = pending.pop()
            if block_id in visited:
                continue
            if block_id not in block_index:
                raise ValueError(f"dangling block edge: {block_id!r}")
            visited.add(block_id)
            block = block_index[block_id]
            successors = block.get("successors")
            if successors is None:
                continue
            if not isinstance(successors, list):
                raise ValueError(
                    f"block successors is not a list: {block_id!r}"
                )
            for edge in successors:
                if not isinstance(edge, dict):
                    raise ValueError(
                        f"block successor is not an object: {block_id!r}"
                    )
                successor_block_id = edge.get("block_id")
                if successor_block_id is None:
                    continue
                if successor_block_id not in block_index:
                    raise ValueError(
                        f"dangling block edge: {successor_block_id!r}"
                    )
                if successor_block_id not in visited:
                    pending.append(successor_block_id)

        reachable_instruction_count = sum(
            len(members_by_block.get(block_id, ())) for block_id in visited
        )

        expected.append(
            {
                "target_offset": target,
                "entry_block_id": entry_block_id,
                "reachable_instruction_count": reachable_instruction_count,
                "source_states": source_states,
            }
        )
    return expected


def _artifact_root_projection(
    root_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Strict projection of artifact root records into the four fields
    the contract helper compares against an independent rebuild
    (§9.1 #5).

    The projection is intentionally narrow: it validates that every
    input is a list of dicts and that every record carries the four
    contract fields.  Two paired shapes are accepted:

    * ``entry_block_id=None`` with ``reachable_instruction_count=0`` —
      the root is an independently-skipped frozen-baseline opaque
      stop (its decision lives in ``_expected_root_records`` via the
      caller-provided ``independently_skipped_root_targets`` set, NOT
      in this projection).
    * ``entry_block_id`` is a non-empty ``str`` with
      ``reachable_instruction_count`` a **positive** ``int`` — the root
      is a normal block-root.

    Any other pairing — ``None``/positive, ``str``/0, empty string,
    negative count — is contradictory evidence and fails closed.  The
    projection never infers the skip decision from the artifact's own
    fields; it only validates shape and copies the four fields
    verbatim.

    A tamper of any of the four fields on the artifact side survives
    the projection unchanged and is detected downstream by
    ``_verify_root_records_contract`` when it compares this projection
    against the independently rebuilt ``expected`` list.
    """

    if not isinstance(root_records, list):
        raise ValueError("artifact roots is not a list")
    projection: list[dict[str, Any]] = []
    for index, record in enumerate(root_records):
        if not isinstance(record, dict):
            raise ValueError(f"artifact root {index} is not an object")
        target = record.get("target_offset")
        if type(target) is not int:
            raise ValueError(
                f"artifact root {index} target_offset is not an int: "
                f"{type(target).__name__}"
            )
        entry_block_id = record.get("entry_block_id")
        reachable_instruction_count = record.get("reachable_instruction_count")
        # §9.1 #5: two valid paired shapes only.
        #   * (None, 0):  independently-skipped frozen-baseline stop.
        #   * (non-empty str, positive int):  normal block root.
        # Any other pairing — including (None, positive), (str, 0),
        # empty string, or negative count — is contradictory evidence
        # and fails closed.  The shape check never decides the skip
        # by itself; the caller's skip set is the sole signal.
        is_skipped_shape = (
            entry_block_id is None
            and type(reachable_instruction_count) is int
            and reachable_instruction_count == 0
        )
        is_block_shape = (
            type(entry_block_id) is str
            and bool(entry_block_id)
            and type(reachable_instruction_count) is int
            and reachable_instruction_count > 0
        )
        if not (is_skipped_shape or is_block_shape):
            raise ValueError(
                f"artifact root {index} has a contradictory "
                f"entry_block_id/reachable_instruction_count pair: "
                f"entry_block_id={entry_block_id!r} "
                f"type={type(entry_block_id).__name__}, "
                f"reachable_instruction_count="
                f"{reachable_instruction_count!r} "
                f"type={type(reachable_instruction_count).__name__}; "
                "only (None, 0) or (non-empty str, positive int) are "
                "permitted"
            )
        source_states = record.get("source_states")
        if not isinstance(source_states, list) or len(source_states) == 0:
            raise ValueError(
                f"artifact root {index} source_states is not a non-empty list"
            )
        if any(type(state) is not int for state in source_states):
            raise ValueError(
                f"artifact root {index} source_states contains a non-int entry"
            )
        if len(set(source_states)) != len(source_states):
            raise ValueError(
                f"artifact root {index} source_states contains a duplicate"
            )
        projection.append(
            {
                "target_offset": target,
                "entry_block_id": entry_block_id,
                "reachable_instruction_count": reachable_instruction_count,
                "source_states": source_states,
            }
        )
    return projection


def _verify_root_records_contract(
    artifact: list[dict[str, Any]],
    expected: list[dict[str, Any]],
) -> None:
    """Strict per-record contract between artifact and expected root
    records (§9.1 #5).

    Both arguments must be equal-length lists of dicts carrying the
    four fields ``target_offset``, ``entry_block_id``,
    ``reachable_instruction_count``, and ``source_states``.  Any drift
    — length mismatch, missing field, or mismatched field — raises
    ``ValueError`` mentioning the offending field.  Returns ``None``
    on success.  Inputs are not mutated.
    """

    if not isinstance(artifact, list):
        raise ValueError("artifact roots is not a list")
    if not isinstance(expected, list):
        raise ValueError("expected roots is not a list")
    if len(artifact) != len(expected):
        raise ValueError(
            f"root record count drifted: artifact={len(artifact)} "
            f"expected={len(expected)}"
        )

    fields = (
        "target_offset",
        "entry_block_id",
        "reachable_instruction_count",
        "source_states",
    )
    for index, (artifact_record, expected_record) in enumerate(
        zip(artifact, expected, strict=True)
    ):
        if not isinstance(artifact_record, dict):
            raise ValueError(f"artifact root {index} is not an object")
        if not isinstance(expected_record, dict):
            raise ValueError(f"expected root {index} is not an object")
        for field in fields:
            if field not in artifact_record:
                raise ValueError(
                    f"artifact root {index} missing field: {field}"
                )
            if field not in expected_record:
                raise ValueError(
                    f"expected root {index} missing field: {field}"
                )
            if artifact_record[field] != expected_record[field]:
                raise ValueError(
                    f"root record {index} field {field!r} drifted: "
                    f"artifact={artifact_record[field]!r} "
                    f"expected={expected_record[field]!r}"
                )
    return None


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha256(
            (root / "tools/export_rom_battle_controller_cfg.py").read_bytes()
        ),
        "verifier_sha256": _sha256(
            (root / "tools/verify_rom_battle_controller_cfg.py").read_bytes()
        ),
        "test_sha256": _sha256(
            (root / "tests/test_export_rom_battle_controller_cfg.py").read_bytes()
        ),
    }


def verify_rom_battle_controller_cfg(
    root: Path,
    artifact_dir: Path,
    *,
    allow_implementation_drift: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact_dir).absolute()
        resolved = artifact.resolve(strict=True)
        if resolved != artifact or not artifact.is_dir():
            raise ValueError("battle-controller CFG artifact uses a symlink")
        members = list(artifact.iterdir())
        if (
            {member.name for member in members} != {MANIFEST_NAME, PAYLOAD_NAME}
            or any(member.is_symlink() or not member.is_file() for member in members)
        ):
            raise ValueError("battle-controller CFG artifact file set changed")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        rebuilt = _rebuild_dispatcher(rom)
        if rebuilt["mapping_vector_sha256"] != DISPATCH_MAPPING_VECTOR_SHA256:
            raise ValueError("battle-controller dispatcher mapping SHA changed")
        if (
            rebuilt["nondefault_state_count"] != 38
            or rebuilt["default_state_count"] != 65_498
            or rebuilt["default_target"] != DEFAULT_TARGET
        ):
            raise ValueError(
                f"battle-controller dispatcher denominator changed: {rebuilt}"
            )

        payload_path = artifact / PAYLOAD_NAME
        manifest_path = artifact / MANIFEST_NAME
        payload_raw = payload_path.read_bytes()
        manifest_raw = manifest_path.read_bytes()
        payload = json.loads(payload_raw)
        manifest = json.loads(manifest_raw)
        expected_rom = {
            "path": ROM_PATH.as_posix(),
            "size": len(rom),
            "sha256": ROM_SHA256,
        }
        if (
            manifest.get("artifact_schema") != SCHEMA
            or manifest.get("rom") != expected_rom
            or manifest.get("controller") != {
                "range": list(CONTROLLER_RANGE),
                "sha256": CONTROLLER_SHA256,
            }
            or manifest.get("dispatch_summary", {}).get(
                "mapping_denominator_sha256"
            ) != DISPATCH_MAPPING_VECTOR_SHA256
        ):
            raise ValueError("battle-controller CFG manifest contract changed")
        if (
            payload.get("schema") != SCHEMA
            or payload.get("rom") != expected_rom
            or payload.get("controller") != {
                "range": list(CONTROLLER_RANGE),
                "sha256": CONTROLLER_SHA256,
            }
        ):
            raise ValueError("battle-controller CFG payload top-level contract changed")
        limits = payload.get("limits", {})
        if (
            limits.get("max_instruction_count") != MAX_INSTRUCTION_COUNT
            or limits.get("max_basic_block_instruction_count") != MAX_BLOCK_INSTRUCTION_COUNT
            or limits.get("decode_window_bytes") != 4
        ):
            raise ValueError("battle-controller CFG limits contract changed")

        dispatcher = payload.get("dispatcher")
        if not isinstance(dispatcher, dict):
            raise ValueError("battle-controller CFG dispatcher payload missing")
        if (
            set(dispatcher)
            != {
                "input_domain",
                "input_denominator",
                "nondefault_state_count",
                "default_state_count",
                "default_target",
                "default_transfers",
                "dispatcher_range",
                "dispatcher_sha256",
                "mappings",
                "mapping_denominator_sha256",
            }
            or dispatcher.get("input_domain") != rebuilt["input_domain"]
            or dispatcher.get("input_denominator") != 0x10000
            or dispatcher.get("nondefault_state_count") != 38
            or dispatcher.get("default_state_count") != 65_498
            or dispatcher.get("default_target") != DEFAULT_TARGET
            or dispatcher.get("dispatcher_range") != list(DISPATCH_RANGE)
            or dispatcher.get("dispatcher_sha256") != DISPATCH_SHA256
            or dispatcher.get("mapping_denominator_sha256")
            != DISPATCH_MAPPING_VECTOR_SHA256
            or dispatcher.get("mappings") != rebuilt["mappings"]
            or dispatcher.get("default_transfers")
            != rebuilt["default_transfers"]
        ):
            raise ValueError("battle-controller CFG dispatcher payload contract changed")

        root_records = payload.get("roots")
        if not isinstance(root_records, list) or len(root_records) != 38:
            raise ValueError("battle-controller CFG roots payload contract changed")
        # Root dedup invariant: one root per dispatcher target, no duplicates.
        targets_seen: set[int] = set()
        for record in root_records:
            if not isinstance(record, dict):
                raise ValueError("root record is not an object")
            target = record.get("target_offset")
            states = record.get("source_states")
            if (
                not isinstance(target, int)
                or not isinstance(states, list)
                or len(states) != 1
                or target in targets_seen
            ):
                raise ValueError(
                    f"root dedup invariant violated: target=0x{target:06X}"
                )
            targets_seen.add(target)
            state = states[0]
            rebuilt_match = next(
                (
                    item
                    for item in rebuilt["mappings"]
                    if item["target_offset"] == target
                ),
                None,
            )
            if rebuilt_match is None:
                raise ValueError(
                    f"root target is not a dispatcher mapping: 0x{target:06X}"
                )
            if rebuilt_match["state"] != state:
                raise ValueError(
                    f"root source state disagrees with dispatcher: "
                    f"target=0x{target:06X}"
                )
            if (
                record.get("entry_sha256") != rebuilt_match["entry_sha256"]
                or record.get("entry_size") != rebuilt_match["entry_size"]
            ):
                raise ValueError(
                    f"root entry bytes disagree with ROM: 0x{target:06X}"
                )

        extension = payload.get("extension")
        if not isinstance(extension, dict) or set(extension) != {
            "blocks",
            "frontiers",
            "opaque_edges",
            "summary",
        }:
            raise ValueError("battle-controller CFG extension contract changed")
        baseline_occupied, baseline_entries = _baseline_occupied_bytes(root, rom)
        producer_occupied, producer_entries = _producer_occupied_bytes()
        baseline_occupied = baseline_occupied | producer_occupied
        baseline_entries = baseline_entries | producer_entries
        rebuilt_nodes, rebuilt_rejected, rebuilt_incoming, rebuilt_opaque, rebuilt_skipped = (
            _rebuild_bounded(
                rom,
                root_records,
                baseline_occupied,
                baseline_entries=baseline_entries,
            )
        )

        blocks = extension["blocks"]
        decoded_last, entries, by_id, artifact_entries = _verify_blocks(rom, blocks)
        if set(artifact_entries) != set(rebuilt_nodes):
            raise ValueError(
                "battle-controller CFG closure disagrees with independent rebuild"
            )
        member_to_block: dict[tuple[str, int], str] = {}
        for member_key in artifact_entries:
            mode, file_offset = member_key
            owner_id: str | None = None
            for block in blocks:
                block_start, block_end = block["range"]
                if (
                    block["mode"] == mode
                    and block_start <= file_offset < block_end
                ):
                    owner_id = block["id"]
                    break
            if owner_id is None:
                raise ValueError(
                    "battle-controller CFG instruction escapes any block: "
                    f"({mode!r}, 0x{file_offset:06X})"
                )
            member_to_block[member_key] = owner_id
        expected_root_records = _expected_root_records(
            root_records,
            blocks,
            member_to_block,
            independently_skipped_root_targets=_derive_rebuilt_skipped_root_targets(
                rebuilt_skipped
            ),
        )
        artifact_root_projection = _artifact_root_projection(root_records)
        _verify_root_records_contract(
            artifact_root_projection, expected_root_records
        )
        frontiers = extension["frontiers"]
        all_opaque_targets = (
            {(edge["target_mode"], edge["target_file_offset"]) for edge in rebuilt_opaque}
            | {
                (edge["target_mode"], edge["target_file_offset"])
                for edge in rebuilt_skipped
            }
        )
        expected_frontiers = _expected_frontiers(
            rom, blocks, decoded_last, entries, rebuilt_rejected, all_opaque_targets,
            root_records,
        )
        if frontiers != expected_frontiers:
            raise ValueError("battle-controller CFG frontier set disagrees")
        opaque_records = extension["opaque_edges"]
        expected_opaque = _expected_opaque_edges(
            list(rebuilt_opaque) + list(rebuilt_skipped)
        )
        if opaque_records != expected_opaque:
            raise ValueError("battle-controller CFG opaque-edge set disagrees")
        summary = _summary(blocks, frontiers, opaque_records)
        if summary != extension["summary"]:
            raise ValueError("battle-controller CFG summary disagrees")
        expected_implementation = _implementation(root)
        artifact_implementation = payload.get("implementation")
        if allow_implementation_drift:
            if (
                not isinstance(artifact_implementation, dict)
                or set(artifact_implementation)
                != {"exporter_sha256", "verifier_sha256", "test_sha256"}
                or any(
                    not isinstance(value, str)
                    or len(value) != 64
                    or any(c not in "0123456789abcdef" for c in value)
                    for value in artifact_implementation.values()
                )
            ):
                raise ValueError(
                    "battle-controller CFG prior implementation identity is invalid"
                )
        elif artifact_implementation != expected_implementation:
            raise ValueError(
                "battle-controller CFG implementation identity changed"
            )
        return {
            "schema": VERIFY_SCHEMA,
            "verified": True,
            "errors": [],
            "controller_range": list(CONTROLLER_RANGE),
            "controller_sha256": CONTROLLER_SHA256,
            "dispatcher_nondefault_state_count": 38,
            "dispatcher_default_state_count": 65_498,
            "root_count": 38,
            "summary": summary,
        }
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append(str(error))
        return {
            "schema": VERIFY_SCHEMA,
            "verified": False,
            "errors": errors,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/rom-battle-controller-cfg-v1"),
    )
    args = parser.parse_args()
    report = verify_rom_battle_controller_cfg(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("verified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
