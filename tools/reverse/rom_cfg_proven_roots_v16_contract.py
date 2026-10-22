#!/usr/bin/env python3
"""Frozen public contract for the raw-ROM CFG proven-roots v16 packet."""

from pathlib import Path


ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
COVERAGE_SHA256 = "064370aa0eca861d99d96e4ee15be4b50c569bea86c67a279d4084517e543baa"
COVERAGE_CLASSIFIED_BYTES = 6_144_296
COVERAGE_UNKNOWN_BYTES = 147_160
SCHEMA = "rom-cfg-proven-roots-v16"
VERIFY_SCHEMA = "rom-cfg-proven-roots-v16-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
PAYLOAD_NAME = "rom-cfg-proven-roots-v16.json"
MANIFEST_NAME = "manifest.json"
EXPERIMENT_OUTPUT_ROOT = Path("build/experiments/active/cfg-proven-roots-v16-sol-20260901")
OFFICIAL_ARTIFACT = Path("artifacts/rom-cfg-proven-roots-v16")

ROOTS = (
    0x08BF78, 0x068D20, 0x0986B0, 0x06188C, 0x061290,
    0x097110, 0x09C0F4, 0x06154C, 0x09AE14, 0x09AE28,
    0x061538, 0x09C44C, 0x06128C, 0x061150, 0x061F24,
)

# Exact target-limited all-ROM Thumb BL denominator.  The final boolean is the
# frozen baseline owner decision: only known-code source owners prove roots.
BL_MATCHES = (
    (0x0610C6, 0x09C0F4, False),
    (0x06126C, 0x06154C, True),
    (0x0612CC, 0x061150, True),
    (0x061318, 0x09C0F4, True),
    (0x0614E0, 0x06128C, True),
    (0x0614E4, 0x061290, True),
    (0x0616C4, 0x06188C, True),
    (0x0616C8, 0x061538, True),
    (0x0616CC, 0x06154C, True),
    (0x0616F4, 0x09C44C, True),
    (0x087EB4, 0x061F24, True),
    (0x08BB42, 0x068D20, True),
    (0x08C266, 0x08BF78, True),
    (0x08CD7C, 0x097110, True),
    (0x098D86, 0x0986B0, True),
    (0x09A4B8, 0x09AE14, True),
    (0x09A4CC, 0x09AE28, True),
    (0x09A5F8, 0x09AE14, True),
    (0x09A84A, 0x09AE14, True),
    (0x09ACD2, 0x09AE28, False),
    (0x09B1A2, 0x09AE28, True),
)

PROMOTION_RANGES = (
    (397648, 397718), (397744, 397792), (397964, 397966),
    (397968, 397996), (398648, 398660), (398668, 398688),
    (399500, 399546), (401188, 401224), (402224, 402310),
    (402328, 402362), (429344, 429428), (573304, 573344),
    (573348, 573440), (618768, 618796), (624304, 624360),
    (633372, 633398), (633944, 633958), (634388, 634402),
    (634408, 634422), (639220, 639240), (640076, 640084),
)
PROMOTION_RANGE_SHA256 = "4b6891b3740a5d81285005259081e16d7a0caf3b25abf6eef4ff579fc5b63fbd"
PROMOTION_PACKED_SHA256 = "5312c767d66bfb70291a1a0ed38dc4b8540ee6d84ec06e1c51be5dfc9e0a6b59"

EXPECTED_METRICS = {
    "decoded_instruction_count": 369,
    "reachable_instruction_bytes": 778,
    "decoded_basic_block_count": 70,
    "decode_reject_count": 0,
    "baseline_cross_edge_count": 18,
}

NONCLAIMS = (
    "natural_execution_or_runtime_reachability",
    "global_code_or_indirect_computed_target_denominator",
    "rejected_unknown_owner_matches_are_producers",
    "literal_pool_or_adjacent_byte_classification",
    "callee_abi_business_semantics_or_compiler_authorship",
    "editing_writeback_relocation_or_allocatable_space",
)

V7_PAYLOAD_PATH = Path("artifacts/rom-cfg-proven-roots-v7/rom-cfg-proven-roots-v7.json")
V7_PAYLOAD_SHA256 = "184e9b84df829fb1ad41f272aabe931c1a1f86111eebd60629ad2d2a23d89a06"
