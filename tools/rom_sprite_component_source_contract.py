#!/usr/bin/env python3
"""Frozen contract for the directly consumed sprite component source packet.

This module is deliberately data-only.  Exporter and verifier each decode the
ROM independently while sharing these immutable, reviewable denominators.
"""

from __future__ import annotations

from pathlib import Path


SCHEMA = "rom-sprite-component-source-v1"
VERIFY_SCHEMA = "rom-sprite-component-source-verification-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "064370aa0eca861d99d96e4ee15be4b50c569bea86c67a279d4084517e543baa"

SOURCE_RANGE = (0x12C904, 0x12D134)
COMPONENT_RANGE = (0x12C904, 0x12D0B4)
DEFINITION_TABLE_RANGE = (0x12D0B4, 0x12D0E4)
TIMELINE_RANGE = (0x12D0E4, 0x12D124)
ANIMATION_TABLE_RANGE = (0x12D124, 0x12D134)
SOURCE_BYTES = SOURCE_RANGE[1] - SOURCE_RANGE[0]
COMPONENT_BYTES = COMPONENT_RANGE[1] - COMPONENT_RANGE[0]
DEFINITION_TABLE_BYTES = DEFINITION_TABLE_RANGE[1] - DEFINITION_TABLE_RANGE[0]
TIMELINE_BYTES = TIMELINE_RANGE[1] - TIMELINE_RANGE[0]
ANIMATION_TABLE_BYTES = ANIMATION_TABLE_RANGE[1] - ANIMATION_TABLE_RANGE[0]

COMPONENT_LIST_COUNT = 12
COMPONENT_RECORD_COUNT = 96
COMPONENT_RECORD_SIZE = 20
COMPONENT_LIST_SIZE = 164
COMPONENT_STRUCT = "<HHhhHHHHBBH"
COMPONENT_TERMINATOR = bytes.fromhex("ffff0000")
COMPONENT_TERMINATOR_HEX = COMPONENT_TERMINATOR.hex()

TIMELINE_COUNT = 4
KEYFRAME_COUNT = 12
KEYFRAME_SIZE = 4
TIMELINE_SIZE = 16
TIMELINE_TERMINATOR = COMPONENT_TERMINATOR
TIMELINE_TERMINATOR_HEX = TIMELINE_TERMINATOR.hex()

EXPECTED_DEFINITION_POINTERS = tuple(
    ROM_BASE + COMPONENT_RANGE[0] + index * COMPONENT_LIST_SIZE
    for index in range(COMPONENT_LIST_COUNT)
)
EXPECTED_ANIMATION_POINTERS = tuple(
    ROM_BASE + TIMELINE_RANGE[0] + index * TIMELINE_SIZE
    for index in range(TIMELINE_COUNT)
)

SEMANTIC_RANGES = (
    (COMPONENT_RANGE[0], COMPONENT_RANGE[1], "sprite_component_records"),
    (DEFINITION_TABLE_RANGE[0], DEFINITION_TABLE_RANGE[1], "sprite_definition_pointer_table"),
    (TIMELINE_RANGE[0], TIMELINE_RANGE[1], "sprite_animation_timelines"),
    (ANIMATION_TABLE_RANGE[0], ANIMATION_TABLE_RANGE[1], "sprite_animation_pointer_table"),
)

CONSUMER_SETUP_RANGE = (0x06F2AA, 0x06F2C8)
CONSUMER_SETUP_SHA256 = "567e30a28f94ac7c4004701c2ecadcb0c6c313ebee25e19fbecca22a201168da"
CONSUMER_LITERAL_LOADS = (
    {
        "instruction": 0x06F2AA,
        "raw_u16": 0x4829,
        "register": 0,
        "literal": 0x06F350,
        "value": 0x0812D0B4,
        "role": "definition_table",
    },
    {
        "instruction": 0x06F2AC,
        "raw_u16": 0x4929,
        "register": 1,
        "literal": 0x06F354,
        "value": 0x0812D124,
        "role": "animation_table",
    },
)
CONSUMER_CALL = {
    "instruction": 0x06F2C4,
    "raw_u16": (0xF7F3, 0xF9F6),
    "target": 0x0626B4,
    "role": "thumb_bl",
}
CONSUMER_PATH = (
    (0x06F2AA, 0x06F350, 0x0812D0B4, "ldr_r0"),
    (0x06F2AC, 0x06F354, 0x0812D124, "ldr_r1"),
    (0x06F2C4, 0x0626B4, "thumb_bl"),
    (0x0626B4, 0x06275E, "allocator"),
    (0x06298C, 0x062A0A, "selector"),
    (0x063122, 0x0631F6, "component_renderer"),
    (0x0631F6, 0x063210, "component_stride_terminator"),
    (0x063256, 0x0632D8, "animation_timing"),
)
CONSUMER_PATH_SHA256 = "978caa4e5f2f2960dd49144c4dc408548e5087e39d1de6d458258cf5f27a61b5"

CONSUMER_CODE_SLICES = (
    (0x0626B4, 0x06275E, "allocator", "1b0a793b761f650bfe43d75ad76186c395d6315dd67a130b9575184b11ce2f87"),
    (0x06298C, 0x062A0A, "selector", "722200eb6511a974b79fe00ee335f21e557cc0fc1898343a5eab4c7032e8ed2f"),
    (0x063122, 0x0631F6, "renderer", "fe6814464976f17f5e708266b02a79aaa195d1bf96985fa852b80d1f3df9afc3"),
    (0x0631F6, 0x063210, "stride_terminator", "71906dd2a83fd26e1065d14aecb07a05190a96d46ff95ca1cd12a05fa8c93fe4"),
    (0x063256, 0x0632D8, "timing", "1ec4801f36351e56d511caaa6cc5fdf31d52142292e64d3c9cf6567eed468be0"),
)

REPORT_HASHES = {
    "source_packed_sha256": "896a1b46f36cd8ad7f5e1c95a048b9aca099eb03ba55c21d4a43730979edcafb",
    "source_semantic_range_vector_sha256": "98b46b8e02a02738d5aa1a0f1723d3832dd6ee1377f52d88a3ebb165d4e4c0e8",
    "component_packed_sha256": "d350356c3542156fe5a5fa9a9387da0a30c8e4c560ffb99c83a229ca04f1ddae",
    "component_pointer_vector_sha256": "c38ed9fd2384bd1627327dc8dd4b44df08128d340a17664db201b53504c48b3a",
    "component_list_vector_sha256": "272625f12dca716c721fc6ed9d7e7e7c5e224c640e45bfff36dbe0001e41a2cd",
    "component_vector_sha256": "7f08e6f16284550c29aba25734067d8664a16723c50d374e2ace69fd6cccb87a",
    "definition_table_packed_sha256": "fcce5f0198755b553f0ffa1285b2920aecba265b4556af0a04e185eb8a520207",
    "timeline_packed_sha256": "1452c17f0d224141b16fd677b0f9b9984ae6c10c5a0d630825a560c6eb752858",
    "timeline_vector_sha256": "fa9e0183c2cf9e1e4201f1b8156a9249c01a84bfa50b6a356d68c42d671917a8",
    "keyframe_vector_sha256": "40294acde5c027c8645af9b93fa1ee82ac0c520136205358d72731c75cb9811a",
    "animation_table_packed_sha256": "1e469e7113da8202a0871bfcbcdc68b7de0921a977caddf053d935cfef8c1f65",
    "animation_pointer_vector_sha256": "40b9c5830c7a62ec410a339936b1d2713736ba912c59b2eb81a6ade530cce3ca",
    "consumer_setup_window_sha256": CONSUMER_SETUP_SHA256,
    "consumer_path_sha256": CONSUMER_PATH_SHA256,
}

COMPONENT_LIST_SHA256 = (
    "72bd5cc53939c2760a456f5ba3819896e232ee6543854ded41e51bd6e7a59e76",
    "d09098d4939d4619ff150c88c3423a7bac4ccd191518ebc7798a5b7296c0c566",
    "f4e53df70bb9d2a6195949e33fea700fc3a4dfc70f66a675d1dfd4b8faf2e95c",
    "34acd2b24a8736c62488da45bef157b159c664af4ece348e7a67e4d625aab59d",
    "eda35ba15955c8d7cb2ac541826f91f722a00a099db66a75cd3b5e8b939a6336",
    "6f156597c9e881a33ade081cefc93fb0fbdf177663cea4a2b6e112bff37a8f11",
    "b8e2f2eb65fde2e5ad20afb904bb6ca14e4b07f243a141c4798efc2079aea319",
    "564b565c6ee75e5d8f9afc21eafa46d536010494cdf4bb0a603318742bc2ee5b",
    "74ecfc4d58e18c808a3f9e752d85a074909371979a2ba33ea44c5028798d934b",
    "62a2e91c3953e383e23285feb055fa15f78b204958a5d119b41b5f626b42dfbd",
    "fe372a2c98b0a4793b286a3e66b2bfa8d230dbb42dd2da6ef46ad5fd06e9d96b",
    "0899937a20c5142dbb491ef8ed976fe484004aa910cf712fbd067d8e37f10ed0",
)

TIMELINE_SHA256 = (
    "b8102c291f2fe456dbca2dae8264cf93e449e875ed9d9380d90b0653d3a5aaec",
    "bc67cfaf377ab7d694eddd26d10ba20fb920e57686fcd7e72bee0c0d44296a6b",
    "4d7e5e4d2362ac9de09e625559fd6c1faed375c5e4dcff08e4d6980ea707c732",
    "07d0cd2e0a170f47fce29fc86b01fb0fa50c4eb5f77ac6a7673f5aadcb3a6241",
)

BASELINE_COVERAGE_SUMMARY = {
    "classified_bytes": 6_144_296,
    "unknown_bytes": 147_160,
    "claim_count": 15_945,
    "segment_count": 17_349,
}
PROMOTED_FROM_UNKNOWN_BYTES = SOURCE_BYTES
BASELINE_SOURCE_OWNER_RANGE = (0x12C901, 0x12D134)
EXCLUDED_ADJACENT_RANGE = (0x12C901, 0x12C904)
CURRENT_UNKNOWN_PROVENANCE_RANGE = (0x0631F6, 0x063210)

PAYLOAD_NAME = "rom-sprite-component-source.json"
BUNDLE_NAME = "rom-sprite-component-source.bin"
MANIFEST_NAME = "manifest.json"
EXPECTED_FILES = frozenset({MANIFEST_NAME, PAYLOAD_NAME, BUNDLE_NAME})
ROOT_CONTRACT_PATH = Path("tools/rom_sprite_component_source_contract.py")

SCOPE = {
    "primary_class": "sprite_component_source",
    "claim_kind": "sprite_component_source_range",
    "fixed_consumer_binding_proven": True,
    "record_and_table_denominators_frozen": True,
    "source_four_semantic_ranges_only": True,
    "consumer_code_promoted": False,
    "stride_terminator_current_unknown_preserved": True,
    "baseline_current_unknown_only": True,
    "natural_runtime_reachability_proven": False,
    "global_sprite_animation_denominator_complete": False,
    "tile_palette_pixel_business_identity_proven": False,
    "dynamic_state_proven": False,
    "padding_or_free_space_claimed": False,
    "editing_writeback_or_relocation_safe": False,
    "safe_editing": False,
}

LIMITATIONS = [
    "Only the fixed source range and its four semantic partitions are promoted.",
    "The five consumer slices are hash-bound provenance; no consumer-code bytes are promoted.",
    "The stride/terminator slice at 0x0631F6..0x063210 remains current-unknown and is not a primary claim.",
    "No natural reachability, complete global sprite/animation denominator, dynamic state, tile/palette/pixel identity, padding/free-space, editing, write-back, or relocation claim is made.",
    "The adjacent 0x12C901..0x12C904 bytes remain outside the promoted source range.",
]
