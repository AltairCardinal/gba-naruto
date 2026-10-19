#!/usr/bin/env python3
"""Bind specialized battle-effect families to the original ROM dispatcher."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.thumb_branch import iter_thumb_direct_branches


ROM_BASE = 0x08000000
HANDLER_START = 0x08077040
HANDLER_END = 0x0807764E
HANDLER_SHA256 = (
    "2e80b66092e3dd94ecdc20afdfb93e9cd41b6e549ab04e92c33c1cf6fc2282c0"
)


def _offset(address: int) -> int:
    return address - ROM_BASE


def _hex(address: int) -> str:
    return f"0x{address:08X}"


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def build_effect_handler_manifest(rom_path: Path | str) -> dict[str, Any]:
    rom_path = Path(rom_path)
    rom = rom_path.read_bytes()
    handler_blob = rom[_offset(HANDLER_START) : _offset(HANDLER_END)]
    _expect(
        hashlib.sha256(handler_blob).hexdigest(),
        HANDLER_SHA256,
        "effect-handler range SHA-256",
    )

    branches = {
        branch.address: branch.target
        for branch in iter_thumb_direct_branches(
            rom,
            rom_base=ROM_BASE,
            start=HANDLER_START,
            end=HANDLER_END,
        )
        if branch.mnemonic == "bl"
    }
    expected_calls = {
        0x08077058: 0x08076A30,
        0x08077074: 0x0806ADD0,
        0x080771B8: 0x0806AEE8,
        0x080773D6: 0x0806A8C0,
        0x080774CC: 0x08076A30,
        0x080774FA: 0x0806A8C0,
        0x0807750E: 0x0806B030,
        0x0807752C: 0x08081024,
        0x08077560: 0x0806A8C0,
    }
    for callsite, target in expected_calls.items():
        _expect(branches.get(callsite), target, f"call at {_hex(callsite)}")

    return {
        "schema_version": 1,
        "identity": "battle_effect_handler_families",
        "rom": str(rom_path),
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "handler_range": {
            "start": _hex(HANDLER_START),
            "end": _hex(HANDLER_END),
            "sha256": hashlib.sha256(handler_blob).hexdigest(),
        },
        "families": {
            "summon": {
                "0x02": "copy_source_and_link",
                "0x07": "identity_variant_copy_and_link",
                "0x17": "paired_clone_graph",
            },
            "battlefield_object": {
                "0x0C": "type_2",
                "0x18": "type_1_with_source",
            },
            "resource": {
                "0x06": "max_hp_percent_heal",
                "0x11": "status_2_plus_hp_and_chakra_restore",
                "0x1A": "max_hp_percent_heal",
                "0x1C": "chakra_add_capped",
                "0x1D": "chakra_subtract_floored",
            },
            "damage": {
                "0x01": "normal",
                "0x14": "status_0x13_gated_then_consumed",
                "0x15": "damage_then_status_and_reaction_state",
            },
            "state": {
                "0x0F": "status_plus_reaction_state_0x30",
                "0x3F": "reaction_state_0x30",
            },
        },
        "helper_calls": {
            "single_summon": _hex(0x0806ADD0),
            "variant_summon": _hex(0x0806AEE8),
            "paired_summon": _hex(0x0806B030),
            "battlefield_object_allocate": _hex(0x08081024),
            "damage_resolve": _hex(0x08076A30),
            "reaction_state": _hex(0x0806A8C0),
        },
        "implementation_contract": [
            "Dispatch every nonempty action through its numeric effect code.",
            "Action cost is committed once before a specialized handler mutates its targets.",
            "Summons copy source battle data, preserve stable slot identities, and create explicit links.",
            "Percent healing scales from target maximum HP and clamps at that maximum.",
            "Chakra additions clamp at maximum and subtractions clamp at zero.",
            "Battlefield objects live in the encounter session used by condition evaluation.",
            "Unknown presentation work remains outside the deterministic domain transaction.",
        ],
        "boundary": (
            "This manifest closes deterministic handler routing and state mutations. "
            "Sprite, sound, camera, and message calls in the same range are presentation-only."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_effect_handler_manifest(args.rom)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
