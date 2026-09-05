#!/usr/bin/env python3
"""Frozen public contract for target-local CFG proven-roots v18."""

from pathlib import Path

ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "rom-cfg-proven-roots-v18"
VERIFY_SCHEMA = "rom-cfg-proven-roots-v18-verification-v1"
PAYLOAD_NAME = "rom-cfg-proven-roots-v18.json"
MANIFEST_NAME = "manifest.json"
EXPERIMENT_OUTPUT_ROOT = Path("build/experiments/active/cfg-proven-roots-v18-20260901")
OFFICIAL_ARTIFACT = Path("artifacts/rom-cfg-proven-roots-v18")

PRECOVERAGE_DIR = Path("artifacts/rom-cfg-proven-roots-v18-precoverage-v1")
PRECOVERAGE_MANIFEST_SHA256 = "8f9e5941703dc1146ad88f62f06c2642556511123be609dc962d202d48e2f146"
PRECOVERAGE_ARCHIVE_SHA256 = "9668600b980dfc067b340ce6cb499fb181cbff6509b1bf94ee36d042b7f2e8de"
PRECOVERAGE_RAW_SHA256 = "23eb0ceaf4d38b8cadb74e05ddf8686de454d5e73c433da26073075d1fa71e78"
PRECOVERAGE_RAW_SIZE = 29_710_693
BASELINE = {"classified_bytes": 6_153_836, "unknown_bytes": 137_620, "claim_count": 16_087, "segment_count": 17_513}

ROOTS = (0x0910D0, 0x0914D8)
TARGET_RANGE = (0x09106C, 0x09163E)
PRODUCERS = ((0x091E82, 0x0910D0), (0x091F1C, 0x0910D0), (0x08F9E6, 0x0914D8), (0x08F9F0, 0x0914D8))
ROOT_ENTRY_SHA256 = "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb"
PRODUCER_PACKED_SHA256 = "f7203f43fb54e29e812a0b35be08f807e5badf87005ba1fe63a67dca287a1c43"

CODE_RANGES = ((0x091070, 0x0910B4), (0x0910BC, 0x0910CE), (0x0910D0, 0x091110), (0x091114, 0x091236), (0x091254, 0x09133A), (0x091350, 0x0913B0), (0x0913BC, 0x091438), (0x091440, 0x0914CA), (0x0914D8, 0x09163E))
LITERAL_RANGES = ((0x09106C, 0x091070), (0x0910B4, 0x0910BC), (0x091110, 0x091114), (0x091238, 0x091254), (0x09133C, 0x091350), (0x0913B0, 0x0913BC), (0x091438, 0x091440), (0x0914CC, 0x0914D8))
GAPS = ((0x0910CE, 0x0910D0), (0x091236, 0x091238), (0x09133A, 0x09133C), (0x0914CA, 0x0914CC))
CODE_RANGE_SHA256 = "b0223b4e9a49c6a1340408ac49eb25416833fbbce0ebea1fee17c725ef965027"
CODE_PACKED_SHA256 = "9c5a623396e5dd9c6eb5801bf6ff26142374138109f71304bbdfc5d521130898"
LITERAL_RANGE_SHA256 = "3483b3f9830c1affd9fe6b3971d62b2de2f1ab5460f3cd0ff13e607b9a74b503"
LITERAL_PACKED_SHA256 = "58ba0e14ab531cd56ff0b6337485d0043177f7f4e6c5a195ec3ff447ebdf7e62"
UNION_RANGE_SHA256 = "ec336cd80c0c541d3105adccb4c2c0878af6812dfa7d27d301ac1aff841658fd"
UNION_PACKED_SHA256 = "db106abe3c335c6f41703f70e2f142a202c79def79a61ada462d79e5dfa28f92"
FULL_METRICS = {"instruction_count": 2217, "instruction_bytes": 4840, "basic_block_count": 377, "decode_reject_count": 0, "baseline_cross_edge_count": 165, "frontier_count": 15}
LOCAL_METRICS = {"instruction_count": 617, "instruction_bytes": 1386, "basic_block_count": 106, "baseline_call_edge_count": 60, "unique_literal_word_count": 24, "literal_reference_count": 26, "literal_bytes": 96}

V7_PAYLOAD_PATH = Path("artifacts/rom-cfg-proven-roots-v7/rom-cfg-proven-roots-v7.json")
V7_PAYLOAD_SHA256 = "184e9b84df829fb1ad41f272aabe931c1a1f86111eebd60629ad2d2a23d89a06"
IMPLEMENTATION_PATHS = {
    "contract": Path("tools/rom_cfg_proven_roots_v18_contract.py"),
    "exporter": Path("tools/export_rom_cfg_proven_roots_v18.py"),
    "verifier": Path("tools/verify_rom_cfg_proven_roots_v18.py"),
    "test_exporter": Path("tests/test_export_rom_cfg_proven_roots_v18.py"),
    "test_verifier": Path("tests/test_verify_rom_cfg_proven_roots_v18.py"),
}
