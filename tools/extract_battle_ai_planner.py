#!/usr/bin/env python3
"""Extract hash-gated static evidence for the original battle AI planner."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.thumb_branch import iter_thumb_direct_branches


ROM_BASE = 0x08000000
FUNCTION_RANGES = {
    "planner": (0x080851F8, 0x080855FE),
    "tile_score": (0x08085160, 0x080851F4),
    "grid_candidate": (0x08085610, 0x080857B0),
}
EXPECTED_FUNCTION_HASHES = {
    "planner": "d94ce211153c95b9d6065691179a6887b149c443be27311c8baaf679c8d85b95",
    "tile_score": "f8cfc39845d11a4bd2d845d5e56803e834632cbd1d091f3dd903e6906b03ad7a",
    "grid_candidate": "8fa4917189c73d871232fce933e7f0b0f3e3c93ad418f65274cfda35c70966af",
}
EXPECTED_PLANNER_CALLS = [
    (0x08085246, 0x0809C0E0),
    (0x08085254, 0x0809C0E0),
    (0x0808528C, 0x0808400C),
    (0x0808529E, 0x0806FDA4),
    (0x080852AA, 0x08082280),
    (0x080852C4, 0x080833A8),
    (0x080852F8, 0x080833A8),
    (0x08085306, 0x08084274),
    (0x08085334, 0x08083278),
    (0x0808533A, 0x080829CC),
    (0x08085388, 0x08069DB8),
    (0x08085398, 0x0806AA38),
    (0x080853B2, 0x0806A9EC),
    (0x08085440, 0x0806D85C),
    (0x08085456, 0x0806D910),
    (0x080854A0, 0x0809C0D8),
    (0x08085512, 0x0806AA38),
    (0x08085528, 0x0806A9EC),
    (0x0808557A, 0x080833A8),
    (0x0808558C, 0x080833A8),
    (0x080855A2, 0x08085160),
    (0x080855C0, 0x08083364),
    (0x080855C6, 0x08083040),
    (0x080855DA, 0x0809C0E0),
    (0x080855EA, 0x0809C0E0),
]


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def _slice(rom: bytes, start: int, end: int) -> bytes:
    if not ROM_BASE <= start <= end <= ROM_BASE + len(rom):
        raise ValueError("AI function range is outside the mapped ROM")
    return rom[start - ROM_BASE : end - ROM_BASE]


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, address - ROM_BASE)[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, address - ROM_BASE)[0]


def _direct_calls(rom: bytes, start: int, end: int) -> list[tuple[int, int]]:
    return [
        (branch.address, branch.target)
        for branch in iter_thumb_direct_branches(
            rom, rom_base=ROM_BASE, start=start, end=end
        )
        if branch.mnemonic == "bl"
    ]


def extract_ai_planner(rom_path: Path | str) -> dict[str, Any]:
    rom_path = Path(rom_path)
    rom = rom_path.read_bytes()
    functions = {}
    for name, (start, end) in FUNCTION_RANGES.items():
        blob = _slice(rom, start, end)
        digest = hashlib.sha256(blob).hexdigest()
        if digest != EXPECTED_FUNCTION_HASHES[name]:
            raise ValueError(f"battle AI {name} SHA-256 mismatch")
        functions[name] = {
            "start": _hex(start),
            "end": _hex(end),
            "size": len(blob),
            "sha256": digest,
        }

    planner_start, planner_end = FUNCTION_RANGES["planner"]
    planner_calls = _direct_calls(rom, planner_start, planner_end)
    if planner_calls != EXPECTED_PLANNER_CALLS:
        raise ValueError("battle AI planner direct-call inventory mismatch")

    # CMP r2,r5; BLE +8 proves strict-greater replacement. The following two
    # LDM/STM pairs copy 3 words and then 2 words (20 bytes) into the best slot.
    expected_max_selection_halfwords = {
        0x080855A8: 0x42AA,
        0x080855AA: 0xDD08,
        0x080855B4: 0xC868,
        0x080855B6: 0xC168,
        0x080855B8: 0xC828,
        0x080855BA: 0xC128,
        0x080855BC: 0x1C15,
    }
    for address, expected in expected_max_selection_halfwords.items():
        if _u16(rom, address) != expected:
            raise ValueError(f"battle AI max-selection opcode mismatch at {_hex(address)}")

    score_literals = {
        "map_width_address": _u32(rom, 0x080851B4),
        "unit_pool_base": _u32(rom, 0x080851B8),
        "tile_flags_base": _u32(rom, 0x080851BC),
        "rng_state_pointer": _u32(rom, 0x080851F4),
    }
    expected_literals = {
        "map_width_address": 0x02002880,
        "unit_pool_base": 0x020240C0,
        "tile_flags_base": 0x0201BE2A,
        "rng_state_pointer": 0x03000010,
    }
    if score_literals != expected_literals:
        raise ValueError("battle AI tile-score literal inventory mismatch")
    tile_score_calls = _direct_calls(rom, 0x08085160, 0x080851F4)
    if tile_score_calls != [(0x080851E0, 0x0809C110)]:
        raise ValueError("battle AI tile-score RNG call mismatch")

    grid_calls = _direct_calls(rom, 0x08085610, 0x080857B0)
    if grid_calls != [
        (0x0808563E, 0x080833A8),
        (0x0808565E, 0x08069E44),
        (0x0808573C, 0x0809C110),
    ]:
        raise ValueError("battle AI grid-candidate call inventory mismatch")
    grid_literals = {
        "unit_pool_base": _hex(_u32(rom, 0x08085670)),
        "map_height_address": _hex(_u32(rom, 0x0808570C)),
        "map_width_address": _hex(_u32(rom, 0x08085710)),
        "tile_occupancy_base": _hex(_u32(rom, 0x08085714)),
        "tile_attribute_base": _hex(_u32(rom, 0x08085718)),
        "tile_type_table": _hex(_u32(rom, 0x0808571C)),
        "tile_flags_base": _hex(_u32(rom, 0x08085720)),
        "rng_state_pointer": _hex(_u32(rom, 0x080857B0)),
    }

    return {
        "schema_version": 1,
        "identity": "battle_ai_candidate_planner_static",
        "rom": str(rom_path),
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "functions": functions,
        "planner_direct_calls": [
            {"callsite": _hex(callsite), "target": _hex(target)}
            for callsite, target in planner_calls
        ],
        "max_candidate_selection": {
            "score_callsite": "0x080855A2",
            "score_target": "0x08085160",
            "comparison": "candidate_score > best_score",
            "comparison_address": "0x080855A8",
            "reject_address": "0x080855AA",
            "candidate_copy_size": 20,
            "best_score_update_address": "0x080855BC",
            "enumeration_calls": [
                {"callsite": "0x080855C0", "target": "0x08083364"},
                {"callsite": "0x080855C6", "target": "0x08083040"},
            ],
        },
        "tile_score": {
            "function": "0x08085160",
            "unit_pool_base": _hex(score_literals["unit_pool_base"]),
            "unit_record_size": "0x01D4",
            "position_offsets": ["0xC4", "0xC5"],
            "facing_offset": "0xC6",
            "candidate_facing_offset": "0xC9",
            "tile_flags_base": _hex(score_literals["tile_flags_base"]),
            "map_width_address": _hex(score_literals["map_width_address"]),
            "components": [
                {"when": "unit[0xC6] == unit[0xC9]", "add": 50},
                {"when": "tile_flags & 1 == 0", "add": 200},
                {
                    "when": "tile_flags & 1 != 0 and ((tile_flags >> (unit[0xC6] + 4)) & 1) == 0",
                    "add": 100,
                },
                {
                    "when": "tile_flags & 1 != 0",
                    "add": "(rng_value * 50) >> 15",
                },
            ],
            "rng_state_pointer": _hex(score_literals["rng_state_pointer"]),
            "rng_call": "0x0809C110",
        },
        "grid_candidate": {
            "function": "0x08085610",
            "direct_calls": [
                {"callsite": _hex(callsite), "target": _hex(target)}
                for callsite, target in grid_calls
            ],
            "literals": grid_literals,
            "proven_score_shape": (
                "Iterates bounded grid coordinates, rejects flagged candidates, "
                "adds a 100-or-50 terrain/direction term plus "
                "(rng_value * 50) >> 15, and retains only a strictly higher score."
            ),
        },
        "conclusion": (
            "The original enemy planner enumerates candidate families, scores concrete "
            "candidate state, and copies only a strictly better candidate. One bound "
            "score function is additive over facing, tile flags, and RNG; a separate "
            "grid helper performs bounded coordinate filtering and max selection."
        ),
        "boundary": (
            "This static slice does not establish target priority, damage utility, "
            "mission-objective weighting, helper semantics outside the proven calls, "
            "or the complete distribution and tie behavior of every AI branch. Runtime "
            "candidate/score captures are still required before implementing formulas."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, nargs="?", default=Path("rom/base.gba"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-ai-planner-static-20260723.json"),
    )
    args = parser.parse_args()
    result = extract_ai_planner(args.rom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
