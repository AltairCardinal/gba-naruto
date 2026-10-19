#!/usr/bin/env python3
"""Bind the original battle AI target index, utility weights, and custom rules."""

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
CANDIDATE_APPEND = 0x08082040
CANDIDATE_APPEND_END = 0x080820A6
CANDIDATE_APPEND_SHA256 = "0d081b0ff74444e057215a6cf2d775d25fc6bdd9ceabc35900c2f603167c9e7b"
CANDIDATE_EXECUTOR = 0x080829CC
CANDIDATE_EXECUTOR_END = 0x08083040
CANDIDATE_EXECUTOR_SHA256 = "eaef7cf8e1e03d7b4bd6679ce20e16a93f5794ddfe9b97f9a786dbaa9e6fdb7b"
TARGET_INDEX = 0x0808400C
TARGET_INDEX_END = 0x08084266
TARGET_INDEX_SHA256 = "a88f30fb911dd6a20a1dc66bbe593912321f27dc2a45f1164d2b27398642a2fb"
DISTANCE_HELPER = 0x08083AF4
DISTANCE_HELPER_END = 0x0808400C
DISTANCE_HELPER_SHA256 = (
    "2be28ff4cdeaed7cd8e95ccdeaf48ae0204fcd62c0a4605f1e6f9036b6562374"
)
DISTANCE_RECORD_TABLE = 0x0853F888
DISTANCE_RECORD_SIZE = 16
DISTANCE_RECORDS_PER_MAP = 8
DISTANCE_MAP_COUNT = 47
DISTANCE_RECORD_TABLE_END = (
    DISTANCE_RECORD_TABLE
    + DISTANCE_RECORD_SIZE * DISTANCE_RECORDS_PER_MAP * DISTANCE_MAP_COUNT
)
DISTANCE_RECORD_TABLE_SHA256 = (
    "30aa5a8171c5091947f01e57eb2fdc041946d4c5b42ed19a741db66197c86621"
)
MAP_23_DISTANCE_LOOKUP = 0x08541008
MAP_23_DISTANCE_LOOKUP_SIZE = 255
MAP_23_DISTANCE_LOOKUP_SHA256 = (
    "a585f3c283f92327ebe85eda944b5e727e0660e09988988e124eb9564b98c3bd"
)
MAP_24_DISTANCE_LOOKUP = 0x08541107
MAP_24_DISTANCE_LOOKUP_SIZE = 221
MAP_24_DISTANCE_LOOKUP_SHA256 = (
    "f911bb28c98b438d28fa0dc28f9536be46c4db70d7b94fd69d5fa2ddde430004"
)
SCORER = 0x08084274
SCORER_END = 0x08085154
SCORER_SHA256 = "c9da91cd096b36f325f3b975a416c83578048a1d588f89cafa1e1ec9dc075830"
CONFIG_TABLE = 0x0853F348
CONFIG_RECORD_SIZE = 0xA8
CONFIG_RECORD_COUNT = 8
CONFIG_TABLE_END = CONFIG_TABLE + CONFIG_RECORD_SIZE * CONFIG_RECORD_COUNT
CONFIG_TABLE_SHA256 = "6bcd51c9faede066805b9f0e427217925b14ad5b7d99e7b98876d17f23e87504"

TARGET_INDEX_CALLS = [
    (0x08084126, 0x0809C14C),
    (0x08084148, 0x0809C14C),
    (0x0808419E, 0x08083AF4),
    (0x080841CA, 0x0806FDA4),
    (0x080841D6, 0x08082280),
    (0x08084212, 0x0806D85C),
    (0x0808422C, 0x0806D910),
]

SCORER_CALLS = [
    (0x080842AC, 0x0809C110),
    (0x080842B6, 0x08085144),
    (0x08084332, 0x08075B58),
    (0x080843CC, 0x08085144),
    (0x08084410, 0x0809C14C),
    (0x08084440, 0x0809C14C),
    (0x0808454C, 0x08083AF4),
    (0x080845E2, 0x0809C14C),
    (0x08084608, 0x0809C14C),
    (0x08084656, 0x0809C14C),
    (0x0808466A, 0x0809C14C),
    (0x080847A6, 0x08083AF4),
    (0x080847B4, 0x08083AF4),
    (0x080848B2, 0x0809C14C),
    (0x08084958, 0x0806C160),
    (0x0808496A, 0x0806C160),
    (0x0808497C, 0x0806C160),
    (0x0808498C, 0x0806C160),
    (0x0808499C, 0x0806C160),
    (0x080849BE, 0x0806C160),
    (0x080849CE, 0x0806C160),
    (0x080849DE, 0x0806C160),
    (0x08084B6A, 0x0806C160),
    (0x08084B92, 0x0806C160),
    (0x08084BBA, 0x0806C160),
    (0x08084BE0, 0x0806C160),
    (0x08084C02, 0x0806C160),
    (0x08084D04, 0x0806C160),
    (0x08084D1E, 0x0806C160),
    (0x08084E2A, 0x08083AF4),
    (0x08084E38, 0x08083AF4),
    (0x08084E56, 0x0809C14C),
    (0x08084E7C, 0x0809C14C),
    (0x08084EE8, 0x08083AF4),
    (0x08084EF6, 0x08083AF4),
    (0x08084F14, 0x0809C14C),
    (0x0808512C, 0x0809C110),
    (0x08085136, 0x0809C14C),
]

SCORER_ACTION_CONTROL_HALFWORDS = {
    0x08084458: 0x0118,  # selected descriptor index * 16
    0x08084462: 0x7800,  # descriptor kind byte
    0x08084464: 0x2804,
    0x0808446E: 0x2801,
    0x0808447C: 0x2805,
    0x08084486: 0x9A11,  # policy +0x18
    0x08084670: 0x980D,  # damage component-count increment
    0x08084688: 0x9C11,  # policy +0x20
    0x08084694: 0x9D11,  # policy +0x1C
    0x0808469A: 0x4A09,  # descriptor halfword at +1
    0x0808469E: 0x8800,
    0x080846A0: 0x21E0,
    0x080846A4: 0x4001,  # mask 0x0700
    0x080846E4: 0x6F58,  # policy +0x74
    0x080846EA: 0x6FA0,  # policy +0x78
    0x080846F0: 0x6FE8,  # policy +0x7C
    0x080846F6: 0x3080,  # policy +0x80
    0x080846FC: 0x3084,  # policy +0x84
    0x08084702: 0x980D,  # tool selector component-count increment
    0x08084714: 0x4807,  # no-selected-action candidate-kind array
    0x0808471C: 0x3802,
    0x08084722: 0x2801,  # candidate kind 2 or 3
    0x08084726: 0x9911,  # policy +0x24
    0x08084738: 0x9A11,  # policy +0x28
    0x08084742: 0x980D,  # common action component-count increment
    0x080848DE: 0x8800,
    0x080848E0: 0x21E0,
    0x080848E4: 0x4001,  # opposite-bank effect-low-3 gate
    0x080848EA: 0x4281,  # 0x0200
    0x080848F0: 0x0080,  # 0x0300
    0x080848FA: 0x9A0D,  # opposite-bank count + 1
    0x08084A7E: 0x9C14,  # commit opposite-bank component count
    0x08084AA4: 0x8800,
    0x08084AA6: 0x21E0,
    0x08084AAA: 0x4001,  # same-bank effect-low-3 gate
    0x08084AB0: 0x4281,  # 0x0100
    0x08084AB6: 0x00C0,  # 0x0500
    0x08084ABC: 0x20C0,
    0x08084AC0: 0x4281,  # 0x0300
    0x08084AC8: 0x9C0D,  # same-bank count + 1
    0x08084CD6: 0x9A14,  # commit same-bank component count
}

SCORER_ACTOR_PENALTY_HALFWORDS = {
    0x08084CEC: 0x243F,  # queued event low-6 mask
    0x08084CF0: 0x0169,  # queued event index * 32
    0x08084CF6: 0x89E9,  # event halfword +0x0E
    0x08084CFC: 0x2812,  # duplicate status 0x12
    0x08084D0C: 0x28FF,  # status lookup absent sentinel
    0x08084D16: 0x280D,  # duplicate status 0x0D
    0x08084D26: 0x28FF,  # status lookup absent sentinel
    0x08084D30: 0x2811,  # conditional restore event
    0x08084D36: 0x89C8,  # candidate maximum HP at +0x0E
    0x08084D38: 0x8989,  # candidate current HP at +0x0C
    0x08084D3A: 0x0840,  # floor(maximum HP / 2)
    0x08084D3C: 0x4281,  # current HP compared with half maximum
    0x08084D42: 0x7A10,  # candidate maximum chakra at +0x08
    0x08084D44: 0x79D1,  # candidate current chakra at +0x07
    0x08084D46: 0x0840,  # floor(maximum chakra / 2)
    0x08084D48: 0x4281,  # current chakra compared with half maximum
    0x08084D4E: 0x32C4,  # candidate X at +0xC4
    0x08084D52: 0x30C5,  # candidate Y at +0xC5
    0x08084D5A: 0x4348,  # Y * map width
    0x08084D5E: 0x1880,  # + X
    0x08084D64: 0x7801,  # candidate-field flags
    0x08084D66: 0x2001,  # threatened bit
    0x08084D68: 0x4008,  # flags & 1
    0x08084D70: 0x3084,  # policy weight +0x84
    0x08084D76: 0x1A24,  # subtract weight +0x84
    0x08084D7A: 0x69E8,  # policy weight +0x1C
    0x08084D7C: 0x1A24,  # subtract weight +0x1C
}

SCORER_EFFECT_7_BONUS_HALFWORDS = {
    0x08084DA8: 0x9013,  # no recognized scenario rule processed yet
    0x08084DBC: 0x2804,  # rule kind minus one within 0..4
    0x080850AA: 0x2501,  # recognized scenario rule marker
    0x080850AC: 0x9513,
    0x080850BC: 0x9A13,  # require no recognized scenario rule
    0x080850BE: 0x2A00,
    0x080850C2: 0x9B0E,  # selected action index
    0x080850C4: 0x2BFF,
    0x080850C8: 0x89E9,  # first queued event halfword +0x0E
    0x080850CA: 0x203F,
    0x080850CC: 0x4008,
    0x080850CE: 0x2807,  # effect low 6 equals 7
    0x080850D2: 0x7D68,  # event position selector +0x15
    0x080850D8: 0x78E9,  # event Y +0x03
    0x080850DE: 0x4348,  # event Y * map width
    0x080850E0: 0x78AD,  # event X +0x02
    0x080850E8: 0x7801,  # event-position candidate-field flags
    0x080850EA: 0x2001,
    0x080850EC: 0x4008,  # event-position threat bit
    0x08085102: 0x32C4,  # actor X +0xC4
    0x08085106: 0x30C5,  # actor Y +0xC5
    0x0808510E: 0x4348,  # actor Y * map width
    0x08085118: 0x7801,  # actor-position candidate-field flags
    0x0808511A: 0x2001,
    0x0808511C: 0x4008,  # actor-position threat bit
    0x08085122: 0x20FA,
    0x08085124: 0x0140,  # 0xFA << 5 == 8000
    0x08085126: 0x4481,  # add bonus to component sum only
}

SCORER_SCENARIO_RULE_COMPONENT_HALFWORDS = {
    0x08084DA8: 0x9013,  # clear recognized-rule marker
    0x08084DB4: 0x7838,  # rule kind
    0x08084DB6: 0x3801,  # normalize kind 1..5 to switch 0..4
    0x08084DBC: 0x2804,
    0x08084DF0: 0x3302,  # kind 1 contributes two components
    0x08084DF2: 0x9315,
    0x08084EA4: 0x9A15,  # commit kind-1 component count
    0x08084EC8: 0x9D0D,  # kind 2 current component count
    0x08084ECA: 0x3501,
    0x08084ECC: 0x9514,
    0x08084F72: 0x9A14,  # commit kind-2 component count
    0x08084F84: 0x9B0D,  # kind 3 contributes one component
    0x08084F86: 0x3301,
    0x08084F88: 0x9314,
    0x08084FC4: 0x9914,  # commit kind-3 component count
    0x0808501E: 0x980D,  # kind 4 contributes one component
    0x08085020: 0x3001,
    0x08085026: 0x900D,
    0x08085046: 0x9A0D,  # kind 5 contributes one component
    0x08085048: 0x3201,
    0x0808504A: 0x9214,
    0x080850A2: 0x9C14,  # commit kind-5 component count
    0x080850A8: 0x900D,
    0x080850AA: 0x2501,  # mark recognized rule after every kind
    0x080850AC: 0x9513,
    0x08085134: 0x990D,  # total component count enters final division
}


def _offset(address: int) -> int:
    return address - ROM_BASE


def _slice(rom: bytes, start: int, end: int) -> bytes:
    if not ROM_BASE <= start <= end <= ROM_BASE + len(rom):
        raise ValueError("AI evidence range is outside the mapped ROM")
    return rom[_offset(start) : _offset(end)]


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, _offset(address))[0]


def _i32(blob: bytes, offset: int) -> int:
    return struct.unpack_from("<i", blob, offset)[0]


def _hex(address: int) -> str:
    return f"0x{address:08X}"


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _calls(rom: bytes, start: int, end: int) -> list[tuple[int, int]]:
    return [
        (branch.address, branch.target)
        for branch in iter_thumb_direct_branches(
            rom, rom_base=ROM_BASE, start=start, end=end
        )
        if branch.mnemonic == "bl"
    ]


def _custom_rules(config_blob: bytes) -> list[dict[str, int]]:
    rules = []
    for config_id in range(CONFIG_RECORD_COUNT):
        record = config_blob[
            config_id * CONFIG_RECORD_SIZE : (config_id + 1) * CONFIG_RECORD_SIZE
        ]
        for slot in range(4):
            offset = 0x88 + slot * 8
            kind = record[offset]
            if kind:
                rules.append(
                    {
                        "config_id": config_id,
                        "slot": slot,
                        "kind": kind,
                        "parameter": record[offset + 1],
                        "weight": _i32(record, offset + 4),
                    }
                )
    return rules


def build_ai_utility_policy_manifest(rom_path: Path | str) -> dict[str, Any]:
    rom_path = Path(rom_path)
    rom = rom_path.read_bytes()
    candidate_append_blob = _slice(rom, CANDIDATE_APPEND, CANDIDATE_APPEND_END)
    candidate_executor_blob = _slice(
        rom, CANDIDATE_EXECUTOR, CANDIDATE_EXECUTOR_END
    )
    target_index_blob = _slice(rom, TARGET_INDEX, TARGET_INDEX_END)
    distance_helper_blob = _slice(
        rom, DISTANCE_HELPER, DISTANCE_HELPER_END
    )
    distance_record_blob = _slice(
        rom, DISTANCE_RECORD_TABLE, DISTANCE_RECORD_TABLE_END
    )
    map_23_distance_lookup = _slice(
        rom,
        MAP_23_DISTANCE_LOOKUP,
        MAP_23_DISTANCE_LOOKUP + MAP_23_DISTANCE_LOOKUP_SIZE,
    )
    map_24_distance_lookup = _slice(
        rom,
        MAP_24_DISTANCE_LOOKUP,
        MAP_24_DISTANCE_LOOKUP + MAP_24_DISTANCE_LOOKUP_SIZE,
    )
    scorer_blob = _slice(rom, SCORER, SCORER_END)
    config_blob = _slice(rom, CONFIG_TABLE, CONFIG_TABLE_END)
    _expect(
        hashlib.sha256(candidate_append_blob).hexdigest(),
        CANDIDATE_APPEND_SHA256,
        "AI candidate append SHA-256",
    )
    _expect(
        hashlib.sha256(candidate_executor_blob).hexdigest(),
        CANDIDATE_EXECUTOR_SHA256,
        "AI candidate executor SHA-256",
    )
    _expect(
        hashlib.sha256(target_index_blob).hexdigest(),
        TARGET_INDEX_SHA256,
        "AI target-index SHA-256",
    )
    _expect(
        hashlib.sha256(distance_helper_blob).hexdigest(),
        DISTANCE_HELPER_SHA256,
        "AI topology-distance helper SHA-256",
    )
    _expect(
        hashlib.sha256(distance_record_blob).hexdigest(),
        DISTANCE_RECORD_TABLE_SHA256,
        "AI topology-distance record-table SHA-256",
    )
    _expect(
        hashlib.sha256(map_23_distance_lookup).hexdigest(),
        MAP_23_DISTANCE_LOOKUP_SHA256,
        "map 23 distance lookup SHA-256",
    )
    _expect(
        hashlib.sha256(map_24_distance_lookup).hexdigest(),
        MAP_24_DISTANCE_LOOKUP_SHA256,
        "map 24 distance lookup SHA-256",
    )
    _expect(
        hashlib.sha256(scorer_blob).hexdigest(),
        SCORER_SHA256,
        "AI scorer SHA-256",
    )
    _expect(
        hashlib.sha256(config_blob).hexdigest(),
        CONFIG_TABLE_SHA256,
        "AI configuration table SHA-256",
    )
    _expect(_calls(rom, TARGET_INDEX, TARGET_INDEX_END), TARGET_INDEX_CALLS, "target-index calls")
    _expect(_calls(rom, SCORER, SCORER_END), SCORER_CALLS, "scorer calls")
    _expect(_u32(rom, 0x080842BC), 0x020240C0, "AI candidate unit pool literal")
    _expect(_u32(rom, 0x080842C0), 0x0202F564, "AI baseline unit pool literal")
    _expect(_u32(rom, 0x080820A8), 0x0202D228, "candidate append base")
    _expect(_u16(rom, 0x08082058), 0x3439, "candidate count offset")
    _expect(_u16(rom, 0x08082060), 0x323A, "candidate kind array offset")
    _expect(_u16(rom, 0x08082064), 0x7001, "candidate kind store")
    _expect(_u32(rom, 0x08082A78), 0x0202D228, "candidate executor base")
    for address, halfword in {
        0x08082BF0: 0x2101,
        0x08082A4C: 0x2102,
        0x08082AC0: 0x2103,
        0x08082EC6: 0x2104,
    }.items():
        _expect(
            _u16(rom, address),
            halfword,
            f"candidate kind argument at {_hex(address)}",
        )
    _expect(
        [
            (branch.address, branch.target)
            for branch in iter_thumb_direct_branches(
                rom,
                rom_base=ROM_BASE,
                start=CANDIDATE_EXECUTOR,
                end=CANDIDATE_EXECUTOR_END,
            )
            if branch.target == CANDIDATE_APPEND
        ],
        [
            (0x08082A50, CANDIDATE_APPEND),
            (0x08082AC4, CANDIDATE_APPEND),
            (0x08082BF4, CANDIDATE_APPEND),
            (0x08082C16, CANDIDATE_APPEND),
            (0x08082ECA, CANDIDATE_APPEND),
        ],
        "candidate append calls",
    )
    _expect(_u16(rom, 0x08084716), 0x303A, "scorer candidate kind offset")
    _expect(_u16(rom, 0x08084718), 0x1838, "scorer candidate index add")
    _expect(_u16(rom, 0x0808471A), 0x7800, "scorer candidate kind load")
    _expect(_u32(rom, 0x08084734), 0x0202D228, "scorer candidate base")
    for address, halfword in SCORER_ACTION_CONTROL_HALFWORDS.items():
        _expect(
            _u16(rom, address),
            halfword,
            f"AI action/selector control at {_hex(address)}",
        )
    for address, halfword in SCORER_ACTOR_PENALTY_HALFWORDS.items():
        _expect(
            _u16(rom, address),
            halfword,
            f"AI actor penalty control at {_hex(address)}",
        )
    for address, halfword in SCORER_EFFECT_7_BONUS_HALFWORDS.items():
        _expect(
            _u16(rom, address),
            halfword,
            f"AI effect-7 bonus control at {_hex(address)}",
        )
    for address, halfword in SCORER_SCENARIO_RULE_COMPONENT_HALFWORDS.items():
        _expect(
            _u16(rom, address),
            halfword,
            f"AI scenario-rule component control at {_hex(address)}",
        )
    _expect(
        _u32(rom, 0x08084D8C),
        0x0201BE2A,
        "AI actor penalty map-width literal",
    )
    _expect(
        _u32(rom, 0x08084D90),
        0x02002880,
        "AI actor penalty candidate-field literal",
    )
    for address, expected, label in (
        (0x080850F4, 0x0202681C, "first queued event"),
        (0x080850F8, 0x0201BE2A, "event-position map width"),
        (0x080850FC, 0x02002880, "event-position candidate field"),
        (0x08085154, 0x0201BE2A, "actor-position map width"),
        (0x08085158, 0x02002880, "actor-position candidate field"),
    ):
        _expect(
            _u32(rom, address),
            expected,
            f"AI effect-7 bonus {label} literal",
        )
    _expect(_u32(rom, 0x08084474), 0x0202D228, "selected descriptor base")
    _expect(_u32(rom, 0x08084478), 0x00003B01, "selected descriptor offset")
    _expect(_u32(rom, 0x080846C0), 0x00003B02, "selected effect halfword offset")
    _expect(_u32(rom, 0x08084830), 0x00003C5B, "opposite target bank offset")
    _expect(_u32(rom, 0x08084C50), 0x00003C54, "same target bank offset")
    _expect(
        [_u32(rom, address) for address in range(0x08084A04, 0x08084A24, 4)],
        [
            0x08084A08,
            0x08084A24,
            0x08084A2C,
            0x08084A34,
            0x08084A3C,
            0x08084A44,
            0x08084A4C,
            0x08084A54,
        ],
        "opposite target-selector jump table",
    )
    _expect(
        [_u32(rom, address) for address in range(0x08084C5C, 0x08084C7C, 4)],
        [
            0x08084C60,
            0x08084C7C,
            0x08084C84,
            0x08084C8C,
            0x08084C94,
            0x08084C9C,
            0x08084CA4,
            0x08084CAC,
        ],
        "same target-selector jump table",
    )

    # The target builder stores one unit slot per selector in separate banks.
    _expect(_u32(rom, 0x080840B0), 0x020240C0, "unit pool literal")
    _expect(_u32(rom, 0x080840B4), 0x0202D228, "battle globals literal")
    _expect(_u32(rom, 0x080840C0), 0x00003C54, "same-side target bank offset")
    _expect(_u32(rom, 0x0808410C), 0x00003C5B, "opposite-side target bank offset")
    for address in (0x08084132, 0x08084158, 0x08084166, 0x08084174, 0x08084182, 0x08084190, 0x080841AC):
        _expect(_u16(rom, address) & 0xFF00, 0xD200, f"strict-minimum reject at {_hex(address)}")
    _expect(
        _u32(rom, 0x08083B50),
        0x02026804,
        "topology-distance battle-control literal",
    )
    _expect(
        _u32(rom, 0x08083B54),
        DISTANCE_RECORD_TABLE,
        "topology-distance record-table literal",
    )
    _expect(
        _u32(rom, 0x08083B58),
        0x08083B5C,
        "topology-distance jump-table pointer",
    )
    _expect(
        [_u32(rom, address) for address in range(0x08083B5C, 0x08083B78, 4)],
        [
            0x08083B78,
            0x08083BAC,
            0x08083C8A,
            0x08083D20,
            0x08083DAE,
            0x08083E38,
            0x08083F0E,
        ],
        "topology-distance record-kind jump table",
    )
    _expect(
        _u32(rom, 0x08083DFC),
        MAP_23_DISTANCE_LOOKUP,
        "map 23 topology-distance lookup literal",
    )
    _expect(
        _u32(rom, 0x08083F04),
        MAP_24_DISTANCE_LOOKUP,
        "map 24 topology-distance lookup literal",
    )
    _expect(
        _u16(rom, 0x08083FF4),
        0x2807,
        "topology-distance eight-record loop bound",
    )

    standard = config_blob[CONFIG_RECORD_SIZE : 2 * CONFIG_RECORD_SIZE]
    common_prefix = standard[:0x88]
    for config_id in range(2, CONFIG_RECORD_COUNT):
        record = config_blob[
            config_id * CONFIG_RECORD_SIZE : (config_id + 1) * CONFIG_RECORD_SIZE
        ]
        _expect(record[:0x88], common_prefix, f"config {config_id} common weights")
    _expect(config_blob[:CONFIG_RECORD_SIZE], bytes(CONFIG_RECORD_SIZE), "config 0 zero policy")

    selectors = [
        {
            "index": 0,
            "metric": "floor(current_hp * 1000 / max_hp)",
            "comparison": "strictly_lower",
        },
        {"index": 1, "metric": "max_hp", "comparison": "strictly_lower"},
        {"index": 2, "metric": "attack", "comparison": "strictly_lower"},
        {"index": 3, "metric": "defense", "comparison": "strictly_lower"},
        {"index": 4, "metric": "agility", "comparison": "strictly_lower"},
        {"index": 5, "metric": "movement", "comparison": "strictly_lower"},
        {
            "index": 6,
            "metric": "map_distance(actor, candidate)",
            "comparison": "strictly_lower",
        },
    ]
    custom_rules = _custom_rules(config_blob)
    _expect(
        custom_rules,
        [
            {"config_id": 2, "slot": 0, "kind": 1, "parameter": 0, "weight": 10000},
            {"config_id": 3, "slot": 0, "kind": 2, "parameter": 0x1F, "weight": 10000},
            {"config_id": 3, "slot": 1, "kind": 3, "parameter": 0x4A, "weight": 10000},
            {"config_id": 3, "slot": 2, "kind": 3, "parameter": 0x4B, "weight": 10000},
            {"config_id": 4, "slot": 0, "kind": 2, "parameter": 0x1E, "weight": 10000},
            {"config_id": 5, "slot": 0, "kind": 5, "parameter": 0, "weight": 10000},
            {"config_id": 6, "slot": 0, "kind": 5, "parameter": 0, "weight": 10000},
            {"config_id": 7, "slot": 0, "kind": 4, "parameter": 0, "weight": 10000},
        ],
        "active custom AI rules",
    )

    hostile_weights = [_i32(standard, offset) for offset in range(0x2C, 0x48, 4)]
    friendly_weights = [_i32(standard, offset) for offset in range(0x48, 0x64, 4)]
    common_weight_fields = [
        {"offset": f"0x{offset:02X}", "value": _i32(standard, offset)}
        for offset in range(0, 0x88, 4)
    ]
    record_type_counts = {
        str(record_type): sum(
            1
            for offset in range(
                0,
                len(distance_record_blob),
                DISTANCE_RECORD_SIZE,
            )
            if distance_record_blob[offset] == record_type
        )
        for record_type in range(7)
    }
    _expect(
        record_type_counts,
        {
            "0": 320,
            "1": 18,
            "2": 33,
            "3": 1,
            "4": 1,
            "5": 2,
            "6": 1,
        },
        "topology-distance record type counts",
    )
    return {
        "schema_version": 1,
        "identity": "battle_ai_target_and_utility_policy",
        "rom": str(rom_path),
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "candidate_executor": {
            "function": _hex(CANDIDATE_EXECUTOR),
            "end": _hex(CANDIDATE_EXECUTOR_END),
            "sha256": CANDIDATE_EXECUTOR_SHA256,
            "append_function": _hex(CANDIDATE_APPEND),
            "append_function_end": _hex(CANDIDATE_APPEND_END),
            "append_function_sha256": CANDIDATE_APPEND_SHA256,
            "candidate_index": "u8(0x0202D261) - 1",
            "candidate_kind_array": "0x0202D262",
            "kinds": {
                "1": "move",
                "2": "replenish_chakra",
                "3": "rest",
                "4": "selected_action",
            },
        },
        "target_index": {
            "function": _hex(TARGET_INDEX),
            "end": _hex(TARGET_INDEX_END),
            "sha256": TARGET_INDEX_SHA256,
            "unit_pool": "0x020240C0",
            "unit_record_size": "0x01D4",
            "scan_order": "unit_slots_1_through_12",
            "partition": "unit[0xCC]_equal_to_actor[0xCC]",
            "selectors": selectors,
            "tie_break": "first_scanned_unit",
            "banks": {
                "same_affiliation": "0x02030E7C",
                "opposite_affiliation": "0x02030E83",
            },
            "forced_opponent_override": (
                "When battle role byte[unit_slot] is 2 and the role byte indexed by "
                "unit[0xCA] is 0, that unit fills all seven opposite-affiliation slots."
            ),
            "distance_helper": "0x08083AF4",
            "distance_model": {
                "function": _hex(DISTANCE_HELPER),
                "end": _hex(DISTANCE_HELPER_END),
                "sha256": DISTANCE_HELPER_SHA256,
                "record_table": _hex(DISTANCE_RECORD_TABLE),
                "record_table_sha256": DISTANCE_RECORD_TABLE_SHA256,
                "map_count": DISTANCE_MAP_COUNT,
                "records_per_map": DISTANCE_RECORDS_PER_MAP,
                "record_size": DISTANCE_RECORD_SIZE,
                "record_type_counts": record_type_counts,
                "record_kinds": {
                    "0": "finish_with_manhattan_segment",
                    "1": "vertical_barrier_with_passage_breakpoints",
                    "2": "horizontal_barrier_with_passage_breakpoints",
                    "3": "map_5_fixed_transition_adjustment",
                    "4": "map_23_signed_distance_lookup",
                    "5": "map_24_dual_entrance_distance_lookup",
                    "6": "map_17_and_37_fixed_transition_adjustment",
                },
                "map_23_lookup": _hex(MAP_23_DISTANCE_LOOKUP),
                "map_23_lookup_size": MAP_23_DISTANCE_LOOKUP_SIZE,
                "map_24_lookup": _hex(MAP_24_DISTANCE_LOOKUP),
                "map_24_lookup_size": MAP_24_DISTANCE_LOOKUP_SIZE,
                "fallback": "direct Manhattan when the first record is type 0",
            },
            "action_range_summary": {
                "available_action_builder": "0x0806FDA4",
                "runtime_template_builders": ["0x0806D85C", "0x0806D910"],
                "operation": "retain maximum low_5 action-range value",
                "destination": "0x02030E8A",
            },
        },
        "scorer": {
            "function": _hex(SCORER),
            "end": _hex(SCORER_END),
            "sha256": SCORER_SHA256,
            "candidate_source": "simulated battle state and queued effect events",
            "damage_utility": {
                "event_low_6": ["0x01", "0x14", "0x15"],
                "per_event_amount": "signed_u16(event+0x18) * event[0x12]",
                "aggregation": "sum_by_target_then_select_largest_total",
                "damage_fraction": "min(total_damage, target_current_hp) / target_current_hp",
                "success_component": "max(event[0x10]) / 100",
                "coverage_component": "distinct_targets / active_opposite_affiliation_units",
                "range_component": "max_map_distance / actor_max_action_range",
            },
            "hostile_target_matching": (
                "For each of the seven opposite-affiliation selector slots, add its "
                "weight when the simulated event target matches; one unit may match "
                "and accumulate several selector weights."
            ),
            "friendly_target_matching": (
                "The same seven selectors are recomputed for same-affiliation units "
                "and use an independent weight vector for supportive events."
            ),
            "status_filters": "bound separately by battle_ai_status_aware_event_score_policy",
            "actor_penalty": {
                "weight_offsets": ["0x84", "0x1C"],
                "application": (
                    "subtract once from the component sum before integer division"
                ),
                "component_count_increment": 0,
                "duplicate_status_events": {
                    "0x12": "actor already has status 0x12",
                    "0x0D": "actor already has status 0x0D",
                },
                "restore_event_0x11": {
                    "actor_fields": {
                        "current_hp": "unit+0x0C u16",
                        "maximum_hp": "unit+0x0E u16",
                        "current_chakra": "unit+0x07 u8",
                        "maximum_chakra": "unit+0x08 u8",
                        "x": "unit+0xC4 u8",
                        "y": "unit+0xC5 u8",
                    },
                    "candidate_field": "0x02002880",
                    "map_width": "u8(0x0201BE2A)",
                    "threat_bit": "0x01",
                    "penalize_when": (
                        "(current_hp > floor(maximum_hp / 2) and "
                        "current_chakra > floor(maximum_chakra / 2)) "
                        "or candidate_field[y * map_width + x] & 1"
                    ),
                },
            },
            "scenario_rule_components": {
                "recognized_kinds": [1, 2, 3, 4, 5],
                "kind_1": {
                    "components": [
                        "average opponent-progress utility",
                        "candidate-field safe-position utility",
                    ],
                    "component_count_increment": 2,
                },
                "kind_2": {
                    "component": (
                        "parameter-character progress plus matching "
                        "damage-event bonus"
                    ),
                    "component_count_increment": 1,
                },
                "kind_3": {
                    "component": "matching queued-event action bonus",
                    "component_count_increment": 1,
                },
                "kind_4": {
                    "component": "matching tile-class and side bonus",
                    "component_count_increment": 1,
                },
                "kind_5": {
                    "component": "eligible queued-event family bonus",
                    "component_count_increment": 1,
                },
                "zero_value_rule_component": (
                    "recognized rule kinds still increment the denominator "
                    "when their component value is zero"
                ),
                "combiner": (
                    "add rule component sums and counts before the final "
                    "integer mean"
                ),
            },
            "effect_7_safe_position_bonus": {
                "constant": 8000,
                "event_selection": "first queued event only",
                "requirements": [
                    "no scenario rule kind 1 through 5 was processed",
                    "selected action index is not 0xFF",
                    "first queued event low 6 bits equal 0x07",
                    "selected position candidate-field threat bit 0 is clear",
                ],
                "position_source": {
                    "event[0x15] == 0": "event[0x02], event[0x03]",
                    "event[0x15] != 0": "actor[0xC4], actor[0xC5]",
                },
                "candidate_field": "0x02002880",
                "map_width": "u8(0x0201BE2A)",
                "threat_bit": "0x01",
                "component_count_increment": 0,
            },
            "actor_projection_utility": {
                "candidate_pool": "0x020240C0",
                "baseline_pool": "0x0202F564",
                "base_bias": "weight[0x00] + weight[0x0C]",
                "hp_gain": (
                    "weight[0x04] * (candidate_hp - baseline_hp) "
                    "/ candidate_max_hp"
                ),
                "hp_retention": (
                    "weight[0x10] * candidate_hp / baseline_hp"
                ),
                "chakra_gain": (
                    "weight[0x08] * (candidate_chakra - baseline_chakra) "
                    "/ candidate_max_chakra"
                ),
                "chakra_retention": (
                    "weight[0x14] * candidate_chakra / baseline_chakra"
                ),
                "branching": (
                    "choose gain when candidate is strictly greater; "
                    "otherwise choose retention"
                ),
                "component_count_increment": 2,
            },
            "selected_action_utility": {
                "descriptor_table": "0x02030D29",
                "descriptor_stride": 16,
                "kind_offset": 0,
                "effect_halfword_offset": 1,
                "kind_1": {
                    "bias_weight_offset": "0x18",
                    "extra_component": "aggregated_damage_utility",
                    "component_count_increment": 2,
                },
                "kind_4": {
                    "bias_weight_offset": "0x20",
                    "component_count_increment": 1,
                },
                "kind_5": {
                    "bias_weight_offset": "0x1C",
                    "effect_low_3_weight_offsets": {
                        str(index): offset
                        for index, offset in enumerate(
                            [
                                "0x84",
                                "0x74",
                                "0x78",
                                "0x7C",
                                "0x80",
                                "0x74",
                                None,
                                None,
                            ]
                        )
                    },
                    "component_count_increment": 2,
                },
                "other_selected_kind": {
                    "bias_weight_offset": None,
                    "component_count_increment": 1,
                },
                "no_selected_action": {
                    "candidate_kind_source": "0x0202D262[candidate_index]",
                    "candidate_kind_2_or_3_weight_offset": "0x24",
                    "other_candidate_kind_weight_offset": "0x28",
                    "component_count_increment": 1,
                },
            },
            "target_selector_utility": {
                "effect_low_3_source": (
                    "(selected_runtime_descriptor_halfword_at_plus_1 "
                    "& 0x0700) >> 8"
                ),
                "opposite_affiliation": {
                    "bank": "0x02030E83",
                    "enabled_effect_low_3": [2, 3],
                    "weight_offsets": [
                        f"0x{offset:02X}" for offset in range(0x2C, 0x48, 4)
                    ],
                    "aggregation": (
                        "for each selector add its weight at most once when any "
                        "eligible queued event targets the indexed unit"
                    ),
                    "component_count_increment": 1,
                },
                "same_affiliation": {
                    "bank": "0x02030E7C",
                    "enabled_effect_low_3": [1, 3, 5],
                    "weight_offsets": [
                        f"0x{offset:02X}" for offset in range(0x48, 0x64, 4)
                    ],
                    "aggregation": (
                        "for each selector add its weight at most once when any "
                        "eligible queued event targets the indexed unit"
                    ),
                    "component_count_increment": 1,
                },
            },
            "component_combiner": "integer_mean",
            "final_random_term": "(rng_value * 10) >> 15",
            "random_only_override": (
                "If actor action-state bits (unit[0xC0] & 0x0E) equal 2, return a "
                "0..99 RNG-derived score without evaluating normal utility."
            ),
        },
        "configuration": {
            "table": _hex(CONFIG_TABLE),
            "end": _hex(CONFIG_TABLE_END),
            "sha256": CONFIG_TABLE_SHA256,
            "record_count": CONFIG_RECORD_COUNT,
            "record_size": CONFIG_RECORD_SIZE,
            "unit_config_field": "unit[0xCD]",
            "config_0_common_weights_all_zero": True,
            "configs_sharing_standard_common_weights": list(
                range(1, CONFIG_RECORD_COUNT)
            ),
            "standard_policy": {
                "config_id": 1,
                "base_weights": [_i32(standard, 0x00), _i32(standard, 0x0C)],
                "actor_hp_gain_weight": _i32(standard, 0x04),
                "actor_hp_survival_weight": _i32(standard, 0x10),
                "actor_chakra_gain_weight": _i32(standard, 0x08),
                "actor_chakra_retention_weight": _i32(standard, 0x14),
                "hostile_target_selector_weights": hostile_weights,
                "friendly_target_selector_weights": friendly_weights,
                "damage_weight": _i32(standard, 0x64),
                "success_rate_weight": _i32(standard, 0x68),
                "target_coverage_weight": _i32(standard, 0x6C),
                "range_usage_weight": _i32(standard, 0x70),
                "common_weight_fields": common_weight_fields,
            },
            "custom_rule_layout": {
                "slot_count": 4,
                "first_offset": "0x88",
                "stride": 8,
                "kind_offset": 0,
                "parameter_offset": 1,
                "weight_offset": 4,
            },
            "active_custom_rules": custom_rules,
            "custom_rule_semantics": [
                {
                    "kind": 1,
                    "operation": (
                        "score average movement-normalized progress toward active "
                        "opponents and add the rule weight on a tile whose flag bit 0 is clear"
                    ),
                },
                {
                    "kind": 2,
                    "operation": (
                        "score movement-normalized progress toward parameter character_id "
                        "and add the rule weight when a damage-family event targets it"
                    ),
                },
                {
                    "kind": 3,
                    "operation": "add the rule weight when a queued event action_id equals parameter",
                },
                {
                    "kind": 4,
                    "operation": (
                        "add the rule weight when the actor occupies tile class 6 and "
                        "the tile-side bit matches the active battle-side selector"
                    ),
                },
                {
                    "kind": 5,
                    "operation": (
                        "when unit[0xCA] is 0, add the rule weight for an eligible "
                        "queued event in low-6 family 0x02, 0x07, or 0x17"
                    ),
                },
            ],
        },
        "implementation_contract": [
            "Preserve outer candidate kinds: move=1, replenish_chakra=2, rest=3, selected_action=4.",
            "Build separate same- and opposite-affiliation target indexes before scoring.",
            "Preserve seven selector matches independently; do not collapse them to nearest or lowest HP.",
            "Score a simulated action result and queued events without mutating the committed battle state.",
            "Aggregate multi-hit damage per target, then add damage, hit-rate, coverage, and range as one component.",
            "Represent scenario priorities as typed weighted rule records, not scripted turn numbers or screenshots.",
            "Add scenario-rule component sums and counts before the shared integer mean; kind 1 contributes two components and kinds 2 through 5 contribute one each even when their value is zero.",
            "Keep deterministic unit-slot tie order and add RNG only at the proven final scoring boundary.",
            "For event 0x11, reuse the candidate threat field and subtract the actor penalty when both resources exceed half or the projected actor tile is threatened.",
            "For a first event of type 0x07 with no active typed scenario rule, add 8000 to the numerator only when its selected position is outside the candidate threat field.",
            "Use the battle-ID-selected eight-record topology-distance model for AI target indexes, queued-event range utility, and scenario-rule progress; do not substitute plain Manhattan distance on routed maps.",
        ],
        "conclusion": (
            "The original AI is a data-driven utility planner. It classifies move, "
            "resource, and selected-action candidates before scoring; indexes seven "
            "target properties separately for allies and opponents; scores simulated "
            "effect events with independent weight vectors; and composes up to four "
            "typed scenario rules from each unit-selected configuration."
        ),
        "boundary": (
            "This closes outer candidate kinds, selected descriptor classification, "
            "target-bank gates, selector component counts, aggregate damage component "
            "count, all three actor-penalty triggers, target order, standard weights, active "
            "custom rules and their component counts, deterministic ties, and final random term. The event 0x11 "
            "conditional branch and the final effect-low-6==7 safe-position bonus are "
            "closed; the complete table-driven topology-distance algorithm inside "
            "0x08083AF4 is also closed. Visible names for the five custom rule kinds "
            "remain intentionally neutral."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-ai-utility-policy-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_ai_utility_policy_manifest(args.rom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
