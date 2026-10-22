#!/usr/bin/env python3
"""Frozen public contract for the pre-battle menu controller CFG packet.

The contract intentionally contains constants only.  The exporter and the
independent verifier both rebuild the selector, raw Thumb closure, coverage
owners and promotion ranges from their inputs.
"""

from __future__ import annotations

from pathlib import Path


ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

SCHEMA = "rom-prebattle-menu-controller-cfg-v1"
VERIFY_SCHEMA = f"{SCHEMA}-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
PAYLOAD_NAME = "rom-prebattle-menu-controller-cfg.json"
MANIFEST_NAME = "manifest.json"
EXPERIMENT_ROOT = Path(
    "build/experiments/active/prebattle-menu-controller-cfg/luna-r1-20260904"
)
OFFICIAL_ARTIFACT = Path("artifacts/rom-prebattle-menu-controller-cfg-v1")

COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
COVERAGE_SHA256 = "ae7c69330285bd3d668612b057a793f1b98edda5e0df421a8bda6f5e90290024"
PRECOVERAGE_ARTIFACT = Path(
    "artifacts/rom-scene-source-four-packet-precoverage-v1"
)
PRECOVERAGE_MANIFEST_SHA256 = "b3aaeca20cb2fb6c9c3345d2bb79cb1c2be2672788993661339e45ad5010220a"
PRECOVERAGE_MANIFEST_SIZE = 1_859
PRECOVERAGE_ARCHIVE_NAME = "rom-byte-coverage.json.gz"
PRECOVERAGE_ARCHIVE_SHA256 = "9b1d55e79921dcac25718368cf80419be39f84b8db4c615f429091e7b6e625ff"
PRECOVERAGE_ARCHIVE_SIZE = 1_722_453
PRECOVERAGE_RAW_SIZE = 30_889_492
COVERAGE_SUMMARY = {
    "rom_bytes": ROM_SIZE,
    "accounted_bytes": ROM_SIZE,
    "classified_bytes": 6_194_116,
    "unknown_bytes": 97_340,
    "claim_count": 16_652,
    "segment_count": 18_332,
}

ROOT = 0x08F190
ROOT_ENTRY_SHA256 = "8a1d56a49bd75817476a967ee4e23ecef2beeffa6748599c19bc8e7ed7620257"
PRODUCER = (0x08F894, ROOT, "bl", 4, "fff77cfc")
PRODUCER_RAW_SHA256 = "9159c211f4b47b3a55fd6a6d7218cecf60a61afc18d70b5d7046fd3899b2daec"
PRODUCER_SCAN_DENOMINATOR = {
    "decoder_kinds": ["thumb_bl", "thumb_b", "thumb_bcond"],
    "rom_range": [0, ROM_SIZE],
    "stride": 2,
    "target_file_offset": ROOT,
}
PRODUCER_SCAN_DENOMINATOR_SHA256 = "a2c444d413c7e75551bc4c360a6f2e91b47c3f6cbfc855a7b50eceaa3f4f03d7"
PRODUCER_MATCH_VECTOR_SHA256 = "265516024d3d3c53826a28fdcf3691e4a10c5ab5a2df4a0efd840957c47c3172"

PRODUCER_OWNER_CLAIM_ID = "story-callback-reachable_thumb_code-04-08f872"
PRODUCER_OWNER_RANGE = (0x08F872, 0x08F8EE)
PRODUCER_OWNER_PRIMARY_CLASS = "armv4t_story_state_callback_reachable_thumb_code"
PRODUCER_OWNER_BYTES_SHA256 = "e6fad7438b65c96f937c5599389b4bee0fac098c52634e2eaa04e463d7b87908"
UPSTREAM_ARTIFACT = Path("artifacts/rom-story-state-callback-cfg-v1")
UPSTREAM_SCHEMA = "rom-story-state-callback-cfg-v1"
UPSTREAM_PRIMARY_CLASS = "armv4t_story_state_callback_cfg"
UPSTREAM_PROMOTION_BYTES = 702
UPSTREAM_MANIFEST_SHA256 = "8384dee3207e426361545a94be1b0c1052381a177e159ef85f452f636db5380a"
UPSTREAM_MANIFEST_SIZE = 5_858
UPSTREAM_PAYLOAD_NAME = "rom-story-state-callback-cfg.json"
UPSTREAM_PAYLOAD_SHA256 = "f82f2472f49d9b6b620aee162a65ca372ead47ae5aa73c4f5e25888482d57ab5"
UPSTREAM_PAYLOAD_SIZE = 16_837
UPSTREAM_VERIFIER = Path("tools/verify_rom_story_state_callback_cfg.py")
UPSTREAM_VERIFIER_SHA256 = "ab808e73e40858b4bf737875ddcebfb8286a662b55af0c36424215e506867d98"
UPSTREAM_CODE_CLAIM_BYTES_SHA256 = PRODUCER_OWNER_BYTES_SHA256

SELECTOR_RANGE = (0x08F380, 0x08F394)
SELECTOR_RAW_HEX = "04480078052800d981e080000249401800688746"
SELECTOR_SHA256 = "c2855eb9815a1ad5136c8d03c3e20120e93c362b1f39c980ff3208d7ef318759"
SELECTOR_LOAD_SITE = 0x08F382
SELECTOR_BOUND_SITE = 0x08F384
SELECTOR_MAX = 5
SELECTOR_BRANCH_SITE = 0x08F386
SELECTOR_BRANCH_TARGET = 0x08F38A
SELECTOR_FALLBACK_SITE = 0x08F388
SELECTOR_FALLBACK_TARGET = 0x08F48E
SELECTOR_INDEX_SHIFT = 2
SELECTOR_INDEX_SITE = 0x08F38A
PC_LITERAL_SITE = 0x08F398
PC_LITERAL_RAW_HEX = "9cf30808"
TABLE_BASE_VALUE = 0x0808F39C
TABLE_RANGE = (0x08F39C, 0x08F3B4)
TABLE_TARGETS = (0x08F3B4, 0x08F3C4, 0x08F3CA, 0x08F3D6, 0x08F3E2, 0x08F3EC)
TABLE_POINTERS = tuple(ROM_BASE + target for target in TABLE_TARGETS)
TABLE_RAW_HEX = "b4f30808c4f30808caf30808d6f30808e2f30808ecf30808"
TABLE_SHA256 = "6ad82039898c09ad9fc0b56291d5634355887cb9b6c6f6df190c7bdc86373db4"
INDIRECT_SELECTOR_SITE = 0x08F392

ENVELOPE = (0x08EE40, 0x08F4CA)
ROOTS = (ROOT,) + TABLE_TARGETS

CURRENT_UNKNOWN_CODE_RANGES = (
    (0x068848, 0x0688A0),
    (0x068D0C, 0x068D1E),
    (0x08768C, 0x087708),
    (0x087724, 0x087846),
    (0x08787C, 0x0878CC),
    (0x0878D8, 0x0878E8),
    (0x0878EC, 0x087906),
    (0x087914, 0x08793E),
    (0x08CD40, 0x08CD5A),
    (0x08CDF8, 0x08CE24),
    (0x08EE5C, 0x08EED8),
    (0x08EEF8, 0x08EF0E),
    (0x08EF14, 0x08EF28),
    (0x08F190, 0x08F1F2),
    (0x08F208, 0x08F284),
    (0x08F2A2, 0x08F2F0),
    (0x08F30C, 0x08F326),
    (0x08F32C, 0x08F34C),
    (0x08F350, 0x08F370),
    (0x08F378, 0x08F394),
    (0x08F3B4, 0x08F3C0),
    (0x08F3C4, 0x08F3E8),
    (0x08F3EC, 0x08F3F2),
    (0x08F3F8, 0x08F400),
    (0x08F404, 0x08F434),
    (0x08F450, 0x08F46E),
    (0x08F474, 0x08F4CA),
)
CURRENT_UNKNOWN_CODE_BYTES = 1_564
CURRENT_UNKNOWN_CODE_RANGE_SHA256 = "76a037c53bb22a38683506269c66ad66f6e72f883f328847d611ced563ba03d7"
CURRENT_UNKNOWN_CODE_PACKED_SHA256 = "57d8f3d6c90e6eb54a53aa0f0dd4982805262f7731ad31d9adc4e4fe53602f29"

DEPENDENCY_CODE_RANGES = ((0x08CD5A, 0x08CDF8), (0x08F284, 0x08F2A2))
DEPENDENCY_CODE_BYTES = 188
DEPENDENCY_CODE_RANGE_SHA256 = "ad0c21948ead969c143d97e3387381013401168c051910a55dfc673d2ccebb2a"
DEPENDENCY_CODE_PACKED_SHA256 = "c606dd7165d97ea1aadb379c704bf117851791698570ee067d5dbbb57b505ecf"
DEPENDENCY_CODE_OWNERS = (
    {
        "range": [0x08CD5A, 0x08CDF8],
        "primary_class": "consumer_code_slice",
        "claim_id": "selector-code-window-15-08cd5a",
    },
    {
        "range": [0x08F284, 0x08F2A2],
        "primary_class": "consumer_code_slice",
        "claim_id": "verified-reuse-world-map-selection-load-calls-08f284",
    },
)

CURRENT_UNKNOWN_LITERAL_RANGES = (
    (0x0688A0, 0x0688B8),
    (0x087708, 0x087724),
    (0x087848, 0x08787C),
    (0x0878CC, 0x0878D8),
    (0x0878E8, 0x0878EC),
    (0x087908, 0x087914),
    (0x08CE24, 0x08CE4C),
    (0x08EED8, 0x08EEF8),
    (0x08EF10, 0x08EF14),
    (0x08EF28, 0x08EF2C),
    (0x08F1F4, 0x08F208),
    (0x08F2F0, 0x08F2F8),
    (0x08F300, 0x08F30C),
    (0x08F328, 0x08F32C),
    (0x08F34C, 0x08F350),
    (0x08F370, 0x08F378),
    (0x08F394, 0x08F39C),
    (0x08F3C0, 0x08F3C4),
    (0x08F3E8, 0x08F3EC),
    (0x08F3F4, 0x08F3F8),
    (0x08F400, 0x08F404),
    (0x08F434, 0x08F450),
    (0x08F470, 0x08F474),
    (0x08F4CC, 0x08F4D4),
)
CURRENT_UNKNOWN_LITERAL_BYTES = 332
CURRENT_UNKNOWN_LITERAL_REFERENCE_COUNT = 84
CURRENT_UNKNOWN_LITERAL_WORD_COUNT = 83
LITERAL_RANGE_SHA256 = "ff5a94625061782582f3edc58c9c24109ec31162c1c7b6dcf8ffc3ae12168e07"
LITERAL_PACKED_SHA256 = "3bebe882bcc3cab4ba4ec9a6702a7b1f4c622d7ace680d07ee97b5706dc3efea"
EXISTING_DEPENDENCY_LITERAL_RANGES = ((0x08F2F8, 0x08F300),)
EXISTING_DEPENDENCY_LITERAL_WORD_COUNT = 2

UNION_RANGES = (
    (0x068848, 0x0688B8),
    (0x068D0C, 0x068D1E),
    (0x08768C, 0x087846),
    (0x087848, 0x087906),
    (0x087908, 0x08793E),
    (0x08CD40, 0x08CD5A),
    (0x08CDF8, 0x08CE4C),
    (0x08EE5C, 0x08EF0E),
    (0x08EF10, 0x08EF2C),
    (0x08F190, 0x08F1F2),
    (0x08F1F4, 0x08F284),
    (0x08F2A2, 0x08F2F8),
    (0x08F300, 0x08F326),
    (0x08F328, 0x08F3F2),
    (0x08F3F4, 0x08F46E),
    (0x08F470, 0x08F4CA),
    (0x08F4CC, 0x08F4D4),
)
PROMOTION_BYTES = 1_920
PROMOTION_RANGE_SHA256 = "921dee8cd4e919ab6ee63e63dfdf59021d67eff2003208637706b722210c3d15"
PROMOTION_PACKED_SHA256 = "ba37224c2db89cdf8718874a8dd6c0fd865dd11cc427f00679ff456a7ffe8311"
JUMP_TABLE_BYTES = 24
JUMP_TABLE_PACKED_SHA256 = TABLE_SHA256

FRONTIER_OFFSETS = (0x06889E, 0x068D1C, 0x08793C, 0x08CE22, 0x08EED6, 0x08EF26, 0x08F4C8)
FRONTIERS = tuple((offset, "indirect_pc_target") for offset in FRONTIER_OFFSETS)
TRAVERSAL_INSTRUCTION_COUNT = 786
TRAVERSAL_INSTRUCTION_BYTES = 1_752
TRAVERSAL_BLOCK_COUNT = 200
TRAVERSAL_INTERNAL_EDGE_COUNT = 839
TRAVERSAL_BLOCK_EDGE_COUNT = 253
TRAVERSAL_FRONTIER_COUNT = 7
OPAQUE_CALL_COUNT = 83
OPAQUE_UNIQUE_TARGET_COUNT = 35
OPAQUE_CALL_VECTOR_SHA256 = "87ca1bf80f687a992269851581c396c6bc81ff4375617b74df30ffd8bd4e8ee9"

IMPLEMENTATION_PATHS = {
    "contract": Path("tools/rom_prebattle_menu_controller_cfg_contract.py"),
    "exporter": Path("tools/export_rom_prebattle_menu_controller_cfg.py"),
    "verifier": Path("tools/verify_rom_prebattle_menu_controller_cfg.py"),
    "test_exporter": Path("tests/test_export_rom_prebattle_menu_controller_cfg.py"),
}

SCOPE = {
    "raw_thumb_cfg_redecoded": True,
    "selector_table_targets_derived_from_raw_table": True,
    "target_limited_direct_producer_denominator_complete": True,
    "producer_owner_claim_independently_verified": True,
    "unknown_callees_recursively_decoded": True,
    "existing_code_dependencies_decoded_without_reclaim": True,
    "current_unknown_only_promotion": True,
    "natural_runtime_reachability": False,
    "global_function_entry_denominator_complete": False,
    "indirect_pc_target_resolution_complete": False,
    "business_semantics": False,
    "padding_or_free_space": False,
    "editing_writeback_or_relocation_safety": False,
}

LIMITATIONS = (
    "This packet proves a bounded static Thumb closure rooted at the menu controller and its raw jump-table targets.",
    "Unknown external callees are recursively decoded only along direct static successors; existing non-unknown code targets are opaque call dependencies.",
    "Existing code dependency bytes and existing literal words are traversal evidence only and are never re-claimed.",
    "The seven indirect PC targets remain frontiers; the selector's one fixed jump table is the sole indirect target expansion.",
    "No natural runtime reachability, gameplay semantics, padding/free-space status, edit safety, or relocation safety is claimed.",
)
