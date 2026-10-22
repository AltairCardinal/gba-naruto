#!/usr/bin/env python3
"""Immutable contract for the table-rooted event-handler CFG packet.

The preflight report is intentionally not an input to product code.  Everything
needed to reproduce this bounded packet is frozen here as constants; the ROM,
coverage baseline, and the raw decoder are checked independently by the
exporter and verifier.
"""

from __future__ import annotations

from pathlib import Path


ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

SCHEMA = "rom-event-handler-cfg-v1"
VERIFY_SCHEMA = "rom-event-handler-cfg-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
PAYLOAD_NAME = "rom-event-handler-cfg.json"
MANIFEST_NAME = "manifest.json"
EXPERIMENT_OUTPUT_ROOT = Path(
    "build/experiments/active/event-handler-cfg-sol-20260901"
)
OFFICIAL_ARTIFACT = Path("artifacts/rom-event-handler-cfg-v1")

TABLE_RANGE = (0x53E698, 0x53EE98)
PRODUCER_RANGE = TABLE_RANGE
TABLE_BYTES = 2_048
TABLE_SLOT_COUNT = 512
TABLE_SHA256 = "20e4727cf65dca82626ffc9637cb36561d5851971500b22a282c5a8c65c7c945"
PRODUCER_TABLE_SHA256 = TABLE_SHA256
MATCHING_SLOT_COUNT = 247
NULL_SLOT_COUNT = 203
OTHER_SLOT_COUNT = 62
MATCHING_SLOT_VECTOR_SHA256 = (
    "94d3dddb301608d1acd16a34b89d80e1744fe37aea9da00bae8fd6d8c9025414"
)
ROOT_VECTOR_SHA256 = "16e6b875243fb94fb67743a40f5065d1af7b3a7d3acd40f4958cb48c0d7767a6"
OCCURRENCE_VECTOR_SHA256 = (
    "a095ebbba8310fb194cd9f49433086eb937dac02d02154de2cb7fcb8b64495f2"
)

UNKNOWN_BOUND = (0x07E070, 0x07F0FC)
CANDIDATE_UNKNOWN_RANGE = UNKNOWN_BOUND
OPAQUE_ACCEPTED_RANGES = ((0x07F0FC, 0x07F110),)

ACCEPTED_ROOTS = (
    0x07E070,
    0x07E1C8,
    0x07E340,
    0x07E4C4,
    0x07E648,
    0x07E774,
    0x07E86C,
    0x07E8A8,
    0x07EA00,
    0x07EA7C,
    0x07EAF8,
    0x07EBA0,
    0x07EC48,
    0x07ED20,
    0x07EE50,
    0x07EF80,
    0x07EFFC,
    0x07F038,
)
ROOT_VECTOR = ACCEPTED_ROOTS + (0x07F064,)
REJECTED_ROOT = 0x07F064
REJECTED_ROOTS = (REJECTED_ROOT,)
REJECTED_ROOT_VECTOR_SHA256 = (
    "f7793e4d1c31317d22a091f3b0e51eaed91bd31b2170262d6eb79f727e1ea033"
)
REJECTION_EVIDENCE = {
    "root": REJECTED_ROOT,
    "reason": "non_call_edge_escaped_unknown_bound",
    "source_file_offset": 0x07F0E8,
    "target_file_offset": 0x07F11E,
}

# The table owner and the unknown owner are the only baseline coverage facts
# needed by this packet.  The coverage file itself is read and hash-checked at
# export/verify time; no preflight artifact is consulted.
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
COVERAGE_SHA256 = "064370aa0eca861d99d96e4ee15be4b50c569bea86c67a279d4084517e543baa"
COVERAGE_EXPECTED = {
    "path": COVERAGE_PATH.as_posix(),
    "sha256": COVERAGE_SHA256,
    "classified_bytes": 6_144_296,
    "unknown_bytes": 147_160,
    "claim_count": 15_945,
    "segment_count": 17_349,
}
TABLE_OWNER = {
    "primary_claim_ids": ["bank-map-events-000"],
    "primary_class": "fixed_table",
    "range": list(TABLE_RANGE),
    "secondary_claim_ids": [],
}
UNKNOWN_OWNER = {
    "primary_claim_ids": [],
    "primary_class": "unknown",
    "range": list(UNKNOWN_BOUND),
    "secondary_claim_ids": [],
    "unknown_reason": "no accepted primary classification claim",
}

CODE_RANGES = (
    (0x07E070, 0x07E1BE),
    (0x07E1C8, 0x07E338),
    (0x07E340, 0x07E4BA),
    (0x07E4C4, 0x07E63E),
    (0x07E648, 0x07E76A),
    (0x07E774, 0x07E836),
    (0x07E848, 0x07E86A),
    (0x07E86C, 0x07E8A0),
    (0x07E8A8, 0x07E956),
    (0x07E968, 0x07E9D4),
    (0x07E9DC, 0x07E9FE),
    (0x07EA00, 0x07EA78),
    (0x07EA7C, 0x07EAF0),
    (0x07EAF8, 0x07EB98),
    (0x07EBA0, 0x07EC40),
    (0x07EC48, 0x07EC5E),
    (0x07EC64, 0x07ED18),
    (0x07ED20, 0x07EE48),
    (0x07EE50, 0x07EF78),
    (0x07EF80, 0x07EFF4),
    (0x07EFFC, 0x07F036),
    (0x07F038, 0x07F062),
)
LITERAL_RANGES = (
    (0x07E1C0, 0x07E1C8),
    (0x07E338, 0x07E340),
    (0x07E4BC, 0x07E4C4),
    (0x07E640, 0x07E648),
    (0x07E76C, 0x07E774),
    (0x07E838, 0x07E848),
    (0x07E8A0, 0x07E8A8),
    (0x07E958, 0x07E968),
    (0x07E9D4, 0x07E9DC),
    (0x07EA78, 0x07EA7C),
    (0x07EAF0, 0x07EAF8),
    (0x07EB98, 0x07EBA0),
    (0x07EC40, 0x07EC48),
    (0x07EC60, 0x07EC64),
    (0x07ED18, 0x07ED20),
    (0x07EE48, 0x07EE50),
    (0x07EF78, 0x07EF80),
    (0x07EFF4, 0x07EFFC),
)
SEMANTIC_RANGES = tuple(
    sorted(
        [(*row, "reachable_thumb_code") for row in CODE_RANGES]
        + [(*row, "consumed_literal_word") for row in LITERAL_RANGES]
    )
)
UNION_RANGES = (
    (0x07E070, 0x07E1BE),
    (0x07E1C0, 0x07E4BA),
    (0x07E4BC, 0x07E63E),
    (0x07E640, 0x07E76A),
    (0x07E76C, 0x07E836),
    (0x07E838, 0x07E86A),
    (0x07E86C, 0x07E956),
    (0x07E958, 0x07E9FE),
    (0x07EA00, 0x07EC5E),
    (0x07EC60, 0x07F036),
    (0x07F038, 0x07F062),
)
PRESERVED_UNKNOWN_HOLES = (
    (0x07E1BE, 0x07E1C0),
    (0x07E4BA, 0x07E4BC),
    (0x07E63E, 0x07E640),
    (0x07E76A, 0x07E76C),
    (0x07E836, 0x07E838),
    (0x07E86A, 0x07E86C),
    (0x07E956, 0x07E958),
    (0x07E9FE, 0x07EA00),
    (0x07EC5E, 0x07EC60),
    (0x07F036, 0x07F038),
    (0x07F062, 0x07F0FC),
)

CFG_INSTRUCTION_COUNT = 1_742
CFG_CODE_BYTES = 3_910
CFG_BLOCK_COUNT = 471
CFG_INSTRUCTION_INTERNAL_EDGE_COUNT = 1_869
CFG_BLOCK_INTERNAL_EDGE_COUNT = 598
CFG_EXTERNAL_CALL_EDGE_COUNT = 213
CFG_FRONTIER_COUNT = 18
CFG_OPAQUE_EDGE_COUNT = 0
CFG_SEMANTIC_VECTOR_SHA256 = (
    "81a570aabec618d2d17143cb45f41ff934274946eff2ae02b59bdbdaae30c269"
)
CFG_INSTRUCTION_INTERNAL_EDGE_VECTOR_SHA256 = (
    "195f1d8ed4a4655d35e23e77d2fc9b285aae9a01ef701fa51571c41ec832d782"
)
CFG_BLOCK_RANGE_VECTOR_SHA256 = (
    "06c7d122d9875aa4b149e21a1dab01b78d9912ee1a185dbaab72dc63a368c483"
)
CFG_BLOCK_INTERNAL_EDGE_VECTOR_SHA256 = (
    "eae4ba95a72342c261c7049ad7871e82d6c7c8dcd6d8791f66064b0828083c0c"
)
CFG_EXTERNAL_CALL_VECTOR_SHA256 = (
    "4444ea91b64053303004b6806bf7d65040de1163c05dcafd77b7e137015c922b"
)
CFG_FRONTIER_VECTOR_SHA256 = (
    "6c72b89540f61a55c2bbed96c505d9e95cf2db1b55a77a59ae051e9e905fed83"
)
CFG_OPAQUE_EDGE_VECTOR_SHA256 = (
    "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
)
CODE_RANGE_VECTOR_SHA256 = (
    "09bf797d304bf49baf00de20e1b0dca4daad61d77e41bb6db38949f827f956e1"
)
LITERAL_RANGE_VECTOR_SHA256 = (
    "3b5b308924f49575121cdd8d2d3b23aa2a1b7c8457b87cab8971ec232cf259ac"
)
SEMANTIC_RANGE_VECTOR_SHA256 = (
    "40c684f688d5e3e461d6cf7ef38f86813523f95bc86c5b87b1b6b62781a5f60f"
)
UNION_RANGE_VECTOR_SHA256 = (
    "1fedbc2f6daf37123079a26961f08dc76f81b060616c708ee4e57b0f1d44616b"
)
HOLE_RANGE_VECTOR_SHA256 = (
    "3cbceac0e45979038c3238ccb04b3b0d3616ee269a71fae0ccec94f5d91913e7"
)
PACKED_CODE_SHA256 = (
    "991ef71ab7a17c7a8c11e25f9f8ae6db7bc1d92a070e8851ffe151cfe43d3dba"
)
PACKED_LITERAL_SHA256 = (
    "1fcf8b9975c4ee0f2df0e072c908df7a549db0f1569ccb408f86038760569d5d"
)
PACKED_PROMOTION_SHA256 = (
    "03fe6762ba9ef5671330dcd8d04d99fc046e34429ebb8c44b3666e250318d96f"
)
PACKED_HOLES_SHA256 = (
    "aa4f5c64ad14135ae2704a78b6b82b50bb111a6ca8cd92d6115a6d3ea99d7f10"
)
LITERAL_BINDING_VECTOR_SHA256 = (
    "2b5c575c4e412df2f5296bc02d697ec73a47d8fe2cda2e234b65a44032004bb3"
)
LITERAL_UNIQUE_WORD_VECTOR_SHA256 = (
    "76d79865d755bb65377abb3ea2110684ccb35efe7aef3a0203482a851791cabb"
)

NONCLAIMS = (
    "natural_runtime_reachability",
    "global_handler_or_producer_denominator_exhaustiveness",
    "literal_business_meaning",
    "envelope_bytes_and_adjacent_holes",
    "padding_reserved_free_or_allocatable_status",
    "editing_writeback_relocation_or_gameplay_semantics",
)
SCOPE = {
    "fixed_table_slot_denominator_complete": True,
    "rooted_bounded_cfg_rebuilt_from_raw_rom": True,
    "consumed_literals_rebuilt_from_raw_instructions": True,
    "current_unknown_only": True,
    "all_roots_accepted": False,
    "natural_runtime_reachability_proven": False,
    "global_handler_denominator_complete": False,
    "global_producer_denominator_complete": False,
    "literal_business_meaning_proven": False,
    "envelope_bytes_promoted": False,
    "holes_padding_free_or_allocatable_proven": False,
    "editing_writeback_relocation_safe": False,
    "nonclaims": list(NONCLAIMS),
}

# The two v13 modules are the frozen decoder oracles used on opposite sides of
# this packet.  The verifier independently checks these hashes and never
# imports the event-handler exporter.
ORACLE_IDENTITIES = {
    "export_v13": {
        "path": "tools/export_rom_cfg_proven_roots_v13.py",
        "sha256": "7017045fc098faff14e1726873a05a379123222ee878d771e3bdb4b5d5a70c8c",
    },
    "verify_v13": {
        "path": "tools/verify_rom_cfg_proven_roots_v13.py",
        "sha256": "a687af7750e9a177b47883f1b540d555bd4c666d92865d56e521f85174c869a7",
    },
}

RUNTIME_DEPENDENCY_PATHS = (
    Path("tools/rom_event_handler_cfg_contract.py"),
    Path("tools/export_rom_cfg_proven_roots_v13.py"),
    Path("tools/verify_rom_cfg_proven_roots_v13.py"),
    Path("tools/export_rom_cfg_inventory.py"),
    Path("tools/verify_rom_cfg_inventory.py"),
    Path("tools/_vendor/capstone/__init__.py"),
    Path("tools/_vendor/capstone/arm.py"),
    Path("tools/_vendor/capstone/arm_const.py"),
    Path("tools/_vendor/capstone/lib/libcapstone.dylib"),
)
