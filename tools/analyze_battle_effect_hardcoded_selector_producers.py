#!/usr/bin/env python3
"""Join hardcoded battle-effect selectors to runtime action handler pairs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "tools" / "_vendor"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CAPSTONE_PYTHON_PATH = os.environ.get("CAPSTONE_PYTHON_PATH")
if CAPSTONE_PYTHON_PATH:
    sys.path.insert(0, CAPSTONE_PYTHON_PATH)
elif str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs  # type: ignore  # noqa: E402

from tools.thumb_branch import decode_thumb_bl  # noqa: E402


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
HANDLER_TABLE_OFFSET = 0x53E698
HANDLER_PAIR_COUNT = 256
HANDLER_PAIR_SIZE = 8
SELECTOR_TARGET = 0x0807FE2C
MAX_HANDLER_BYTES = 0x400

SEQUENCE_MANIFEST = Path("artifacts/battle-effect-sequence-bindings-v1/manifest.json")
HANDLER_BANK = Path("sequel/content/map-events/bank.json")
ACTION_IDENTITIES = Path("sequel/content/battle-config/action-identities.json")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _u16(rom: bytes, gba_address: int) -> int:
    offset = gba_address - ROM_BASE
    if offset < 0 or offset + 2 > len(rom):
        raise ValueError(f"Thumb address outside ROM: 0x{gba_address:08X}")
    return int.from_bytes(rom[offset : offset + 2], "little")


def _u32(rom: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(rom):
        raise ValueError(f"u32 offset outside ROM: 0x{offset:X}")
    return int.from_bytes(rom[offset : offset + 4], "little")


def validate_handler_bank(rom: bytes, bank: dict[str, Any]) -> None:
    if bank.get("table_offset") != HANDLER_TABLE_OFFSET:
        raise ValueError("handler bank table offset mismatch")
    if bank.get("entry_count") != HANDLER_PAIR_COUNT:
        raise ValueError("handler bank entry count mismatch")
    if bank.get("entry_size") != HANDLER_PAIR_SIZE:
        raise ValueError("handler bank entry size mismatch")
    entries = bank.get("entries")
    if not isinstance(entries, list) or len(entries) != HANDLER_PAIR_COUNT:
        raise ValueError("handler bank rows mismatch")
    for index, row in enumerate(entries):
        expected_offset = HANDLER_TABLE_OFFSET + index * HANDLER_PAIR_SIZE
        if row.get("_index") != index or row.get("_raw_offset") != expected_offset:
            raise ValueError(f"handler row {index} identity mismatch")
        for slot, delta in (("primary", 0), ("secondary", 4)):
            key = f"{slot}_handler_ptr"
            pointer = row.get(key)
            if not isinstance(pointer, int):
                raise ValueError(f"handler row {index} {slot} is not an integer")
            if pointer:
                if not pointer & 1:
                    raise ValueError(f"handler row {index} {slot} is not a Thumb pointer")
                address = pointer & ~1
                if not ROM_BASE <= address < ROM_BASE + len(rom):
                    raise ValueError(f"handler row {index} {slot} points outside ROM")
            if pointer != _u32(rom, expected_offset + delta):
                raise ValueError(f"handler row {index} {slot} does not match ROM bytes")


def _validate_action_identities(payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    entries = payload.get("entries")
    if not isinstance(entries, list) or len(entries) != 87:
        raise ValueError("active action identity denominator mismatch")
    by_id: dict[int, dict[str, Any]] = {}
    for row in entries:
        action_id = row.get("action_id")
        if not isinstance(action_id, int) or action_id in by_id:
            raise ValueError("active action identities are not unique integers")
        by_id[action_id] = row
    if set(by_id) != set(range(87)):
        raise ValueError("active action identities do not cover 0..86")
    return by_id


def _parse_target(op_str: str) -> int | None:
    match = re.search(r"0x[0-9a-fA-F]+", op_str)
    return int(match.group(0), 16) if match else None


def _reachable_instructions(rom: bytes, start: int, end: int) -> set[int]:
    if not start < end <= ROM_BASE + len(rom):
        raise ValueError("invalid handler analysis window")
    blob = rom[start - ROM_BASE : end - ROM_BASE]
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    instructions = {insn.address: insn for insn in decoder.disasm(blob, start)}
    if start not in instructions:
        raise ValueError(f"handler root does not decode: 0x{start:08X}")
    reachable: set[int] = set()
    pending = deque([start])
    while pending:
        address = pending.popleft()
        if address in reachable:
            continue
        insn = instructions.get(address)
        if insn is None:
            continue
        reachable.add(address)
        fallthrough = address + insn.size
        mnemonic = insn.mnemonic.lower()
        successors: list[int] = []
        if mnemonic in {"bx", "blx", "tbb", "tbh"}:
            successors = []
        elif mnemonic == "pop" and "pc" in insn.op_str.lower():
            successors = []
        elif mnemonic == "b":
            target = _parse_target(insn.op_str)
            if target is not None:
                successors = [target]
        elif mnemonic.startswith("b") and mnemonic not in {"bl", "blx"}:
            target = _parse_target(insn.op_str)
            successors = [fallthrough]
            if target is not None:
                successors.append(target)
        elif mnemonic in {"cbz", "cbnz"}:
            target = _parse_target(insn.op_str)
            successors = [fallthrough]
            if target is not None:
                successors.append(target)
        else:
            successors = [fallthrough]
        pending.extend(next_address for next_address in successors if start <= next_address < end)
    return reachable


def _validate_selector_manifest(rom: bytes, manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != "battle-effect-sequence-bindings-v1":
        raise ValueError("selector manifest schema mismatch")
    if manifest.get("rom", {}).get("sha256") != ROM_SHA256:
        raise ValueError("selector manifest ROM hash mismatch")
    callsites = manifest.get("selector_callsites")
    if not isinstance(callsites, list) or len(callsites) != 67:
        raise ValueError("selector callsite denominator mismatch")
    immediate = 0
    dynamic = 0
    for row in callsites:
        address = int(row["gba_address"], 16)
        first = _u16(rom, address)
        second = _u16(rom, address + 2)
        if decode_thumb_bl(address, first, second) != SELECTOR_TARGET:
            raise ValueError(f"selector callsite target mismatch: 0x{address:08X}")
        if row.get("source") == "immediate_movs_r0":
            immediate += 1
            previous = _u16(rom, address - 2)
            if previous & 0xFF00 != 0x2000:
                raise ValueError(f"selector immediate is not MOVS r0: 0x{address:08X}")
            if previous & 0xFF != row.get("sequence_id"):
                raise ValueError(f"selector immediate sequence mismatch: 0x{address:08X}")
        else:
            dynamic += 1
    if (immediate, dynamic) != (66, 1):
        raise ValueError("selector immediate/dynamic denominator mismatch")


def analyze(root: Path) -> dict[str, Any]:
    root = root.resolve()
    rom_path = root / "rom/base.gba"
    sequence_path = root / SEQUENCE_MANIFEST
    handler_path = root / HANDLER_BANK
    identity_path = root / ACTION_IDENTITIES
    rom = rom_path.read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    sequence_manifest = _load_json(sequence_path)
    handler_bank = _load_json(handler_path)
    action_payload = _load_json(identity_path)
    _validate_selector_manifest(rom, sequence_manifest)
    validate_handler_bank(rom, handler_bank)
    actions = _validate_action_identities(action_payload)

    active_bindings = {
        row["action_id"]: row for row in sequence_manifest["active_action_bindings"]
    }
    sequences = {row["sequence_id"]: row for row in sequence_manifest["sequences"]}
    roots = sorted(
        {
            row[key] & ~1
            for row in handler_bank["entries"]
            for key in ("primary_handler_ptr", "secondary_handler_ptr")
            if row[key]
        }
    )
    reachable_by_root: dict[int, set[int]] = {}
    for index, start in enumerate(roots):
        next_root = roots[index + 1] if index + 1 < len(roots) else start + MAX_HANDLER_BYTES
        end = min(start + MAX_HANDLER_BYTES, next_root, ROM_BASE + len(rom))
        reachable_by_root[start] = _reachable_instructions(rom, start, end)

    pair_links_by_root: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in handler_bank["entries"]:
        pair_index = row["_index"]
        for slot in ("primary", "secondary"):
            pointer = row[f"{slot}_handler_ptr"]
            if not pointer:
                continue
            pair_links_by_root[pointer & ~1].append(
                {"pair_index": pair_index, "pair_slot": slot}
            )

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    dynamic_callsites: list[dict[str, Any]] = []
    for source_callsite in sequence_manifest["selector_callsites"]:
        if source_callsite.get("source") != "immediate_movs_r0":
            dynamic_callsites.append(dict(source_callsite))
            continue
        callsite_address = int(source_callsite["gba_address"], 16)
        sequence_id = source_callsite["sequence_id"]
        handler_links: list[dict[str, Any]] = []
        for handler_start in roots:
            if callsite_address not in reachable_by_root[handler_start]:
                continue
            for pair_link in pair_links_by_root[handler_start]:
                pair_index = pair_link["pair_index"]
                link: dict[str, Any] = {
                    "handler_start": f"0x{handler_start:08X}",
                    **pair_link,
                    "association": "runtime action index dispatches a handler that can execute this hardcoded selector",
                    "natural_route_status": "not_runtime_proven",
                }
                if pair_index in actions:
                    dynamic_sequence_id = active_bindings[pair_index]["sequence_id"]
                    link.update(
                        {
                            "identity_kind": "active_action",
                            "action_id": pair_index,
                            "display_name": actions[pair_index]["display_name"],
                            "name_confidence": actions[pair_index]["confidence"],
                            "dynamic_action_sequence_id": dynamic_sequence_id,
                            "hardcoded_and_dynamic_sequences_are_distinct": (
                                dynamic_sequence_id != sequence_id
                            ),
                        }
                    )
                else:
                    link["identity_kind"] = "unidentified_runtime_action_byte"
                handler_links.append(link)
        grouped[sequence_id].append(
            {
                "selector_callsite": f"0x{callsite_address:08X}",
                "selector_kind": "immediate_movs_r0",
                "hardcoded_sequence_id": sequence_id,
                "handler_links": handler_links,
                "association_status": "static_handler_linked" if handler_links else "unresolved",
            }
        )

    by_sequence: dict[str, dict[str, Any]] = {}
    for sequence_id in sorted(grouped):
        sequence = sequences[sequence_id]
        by_sequence[str(sequence_id)] = {
            "hardcoded_sequence_id": sequence_id,
            "descriptor": sequence["table_entry_gba_address"],
            "resource_group_ids": sequence["resource_group_ids"],
            "resource_pair_artifacts": sequence["resource_pair_artifacts"],
            "init_once_callback": sequence["init_once_callback_thumb"],
            "tick_callback": sequence["tick_callback_thumb"],
            "callsite_count": len(grouped[sequence_id]),
            "callsites": grouped[sequence_id],
        }

    return {
        "schema": "battle-effect-hardcoded-selector-producers-v1",
        "sources": {
            "rom": {"path": "rom/base.gba", "sha256": _sha256(rom)},
            "sequence_manifest": {
                "path": str(SEQUENCE_MANIFEST),
                "sha256": _sha256(sequence_path.read_bytes()),
            },
            "handler_bank": {
                "path": str(HANDLER_BANK),
                "sha256": _sha256(handler_path.read_bytes()),
            },
            "action_identities": {
                "path": str(ACTION_IDENTITIES),
                "sha256": _sha256(identity_path.read_bytes()),
            },
        },
        "counts": {
            "selector_callsites": 67,
            "immediate_selector_callsites": 66,
            "dynamic_selector_callsites": 1,
            "handler_pairs": 256,
        },
        "by_sequence": by_sequence,
        "dynamic_selector_callsites": dynamic_callsites,
        "scope": {
            "hardcoded_selector_producer_links_complete": True,
            "handler_pair_associations_are_static_only": True,
            "natural_route_proven": False,
            "modified_rom_pixel_ab_proven": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze(args.root)
    encoded = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
