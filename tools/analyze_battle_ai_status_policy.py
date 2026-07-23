#!/usr/bin/env python3
"""Bind status-aware event scoring policies in the original battle AI."""

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
SCORER = 0x08084274
SCORER_END = 0x08085154
SCORER_SHA256 = "c9da91cd096b36f325f3b975a416c83578048a1d588f89cafa1e1ec9dc075830"
STATUS_LOOKUP = 0x0806C160
EXPECTED_STATUS_LOOKUPS = [
    (0x08084958, 0x3F),
    (0x0808496A, 0x3E),
    (0x0808497C, 0x3D),
    (0x0808498C, 0x0F),
    (0x0808499C, 0x11),
    (0x080849BE, 0x1F),
    (0x080849CE, 0x21),
    (0x080849DE, 0x23),
    (0x08084B6A, 0x1E),
    (0x08084B92, 0x20),
    (0x08084BBA, 0x22),
    (0x08084BE0, 0x24),
    (0x08084C02, 0x1B),
    (0x08084D04, 0x12),
    (0x08084D1E, 0x0D),
]


def _offset(address: int) -> int:
    return address - ROM_BASE


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _format_address(address: int) -> str:
    return f"0x{address:08X}"


def _format_code(code: int) -> str:
    return f"0x{code:02X}"


def build_ai_status_policy_manifest(rom_path: Path | str) -> dict[str, Any]:
    rom = Path(rom_path).read_bytes()
    scorer = rom[_offset(SCORER) : _offset(SCORER_END)]
    _expect(
        hashlib.sha256(scorer).hexdigest(),
        SCORER_SHA256,
        "AI event scorer SHA-256",
    )

    lookup_calls = [
        branch.address
        for branch in iter_thumb_direct_branches(
            rom,
            rom_base=ROM_BASE,
            start=SCORER,
            end=SCORER_END,
        )
        if branch.mnemonic == "bl" and branch.target == STATUS_LOOKUP
    ]
    _expect(
        lookup_calls,
        [callsite for callsite, _ in EXPECTED_STATUS_LOOKUPS],
        "AI scorer status lookup callsites",
    )
    decoded_lookups = []
    for callsite, expected_code in EXPECTED_STATUS_LOOKUPS:
        preceding = _u16(rom, callsite - 2)
        _expect(preceding & 0xFF00, 0x2100, f"MOVS r1 before {_format_address(callsite)}")
        _expect(
            preceding & 0xFF,
            expected_code,
            f"status code before {_format_address(callsite)}",
        )
        decoded_lookups.append(
            {"callsite": _format_address(callsite), "status_code": _format_code(expected_code)}
        )

    return {
        "schema_version": 1,
        "identity": "battle_ai_status_aware_event_score_policy",
        "scorer": _format_address(SCORER),
        "scorer_end": _format_address(SCORER_END),
        "scorer_sha256": SCORER_SHA256,
        "status_lookup_count": len(decoded_lookups),
        "status_lookups": decoded_lookups,
        "target_status_group_policies": [
            {
                "event_selector": "low_6_in_[0x3F,0x0F,0x0E]_or_raw_bit_0x80",
                "target_status_any": ["0x3F", "0x3E", "0x3D", "0x0F", "0x11"],
                "effect": "skip_matching_event_score_contribution",
            },
            {
                "event_selector": "raw_bit_0x40",
                "target_status_any": ["0x1F", "0x21", "0x23"],
                "effect": "skip_matching_event_score_contribution",
            },
        ],
        "target_same_family_policies": [
            {"event_low_6": ["0x1E", "0x26"], "target_status": "0x1E"},
            {"event_low_6": ["0x20", "0x26"], "target_status": "0x20"},
            {"event_low_6": ["0x22", "0x26"], "target_status": "0x22"},
            {"event_low_6": ["0x24"], "target_status": "0x24"},
            {"event_low_6": ["0x26"], "target_status": "0x1B"},
        ],
        "same_family_effect": "skip_matching_event_score_contribution",
        "actor_event_status_penalties": [
            {"queued_event_low_6": "0x12", "actor_status": "0x12"},
            {"queued_event_low_6": "0x0D", "actor_status": "0x0D"},
        ],
        "actor_penalty_operation": (
            "subtract_weight_fields_0x84_and_0x1c_from_candidate_score"
        ),
        "proves_visible_status_names": False,
        "conclusion": (
            "The AI scorer is status-aware at the event-contribution level. It "
            "suppresses contributions through two target status groups, prevents "
            "several same-family event/status combinations, and applies a separate "
            "actor penalty for queued-event/status pairs 0x12 and 0x0D."
        ),
        "boundary": (
            "The lookup matrix and score operations are statically closed. This does "
            "not identify visible status names, prove the gameplay meaning of the "
            "event codes, or close damage utility, mission weights, full target "
            "priority, runtime score magnitudes, or tie behavior."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-ai-status-policy-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_ai_status_policy_manifest(args.rom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
