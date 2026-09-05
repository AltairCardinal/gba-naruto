#!/usr/bin/env python3
"""Frozen public contract for the combined CFG proven-roots v17 packet."""

from pathlib import Path


ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "rom-cfg-proven-roots-v17"
VERIFY_SCHEMA = "rom-cfg-proven-roots-v17-verification-v1"
PAYLOAD_NAME = "rom-cfg-proven-roots-v17.json"
MANIFEST_NAME = "manifest.json"
EXPERIMENT_OUTPUT_ROOT = Path("build/experiments/active/cfg-proven-roots-v17-20260901")
OFFICIAL_ARTIFACT = Path("artifacts/rom-cfg-proven-roots-v17")

PRECOVERAGE_DIR = Path("artifacts/rom-cfg-proven-roots-v17-precoverage-v1")
PRECOVERAGE_MANIFEST_SHA256 = "c143d90e2e2396fe002fbfa623c213ef7f9313b02f564502aeed2e1e9ce6e449"
PRECOVERAGE_ARCHIVE_SHA256 = "ff5917864c0c2b3f039e18c531b392bcc117cd3470bb343a5c1cadde0c1ae2da"
PRECOVERAGE_RAW_SHA256 = "4e8ab6b090825901ab7b055326e64a6a16343ec95ac33cfe5e0dbe7721eb2440"
PRECOVERAGE_RAW_SIZE = 29_663_308
BASELINE = {"classified_bytes": 6_151_436, "unknown_bytes": 140_020, "claim_count": 16_061, "segment_count": 17_483}

ROOT = 0x0914D8
TARGET_RANGE = (0x091676, 0x091FE0)
BL_MATCHES = ((0x08F9E6, ROOT), (0x08F9F0, ROOT))
PRODUCER_OWNER_RANGE = (0x08F9E2, 0x08FA00)
PRODUCER_OWNER_CLASS = "consumer_code_slice"
PRODUCER_OWNER_CLAIM = "verified-reuse-wram-overview-entry-08f9e2"
ROOT_ENTRY_SHA256 = "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb"
PRODUCER_PACKED_SHA256 = "4a30dfc1942f89043ca3b2ab637963177cf3d0da20a93b0b53f5341ccb0d0963"

CODE_RANGES = (
    (0x091676, 0x091848), (0x0918F4, 0x0919BE), (0x0919C8, 0x091AA4),
    (0x091AB0, 0x091B0A), (0x091B14, 0x091B3C), (0x091B40, 0x091BB8),
    (0x091BBC, 0x091C2E), (0x091C38, 0x091D14), (0x091D2C, 0x091D7C),
    (0x091D88, 0x091E5A), (0x091E7C, 0x091EA4), (0x091EA8, 0x091F2E),
    (0x091F3C, 0x091FD8),
)
LITERAL_RANGES = (
    (0x091848, 0x0918F4), (0x0919C0, 0x0919C8), (0x091AA4, 0x091AB0),
    (0x091B0C, 0x091B14), (0x091B3C, 0x091B40), (0x091BB8, 0x091BBC),
    (0x091C30, 0x091C38), (0x091D14, 0x091D2C), (0x091D7C, 0x091D88),
    (0x091E5C, 0x091E7C), (0x091EA4, 0x091EA8), (0x091F30, 0x091F3C),
    (0x091FD8, 0x091FE0),
)
GAPS = ((0x0919BE, 0x0919C0), (0x091B0A, 0x091B0C), (0x091C2E, 0x091C30), (0x091E5A, 0x091E5C), (0x091F2E, 0x091F30))
CODE_RANGE_SHA256 = "a460cbeb156a6bb8733f224a298f8d9027b9d0600ca34129c47a423efafc70fa"
CODE_PACKED_SHA256 = "773e033e1dcc109082981e917c9b36a20d41c8c7d35e2926bb4c5a7bc382f9eb"
LITERAL_RANGE_SHA256 = "d514c7098781bd194f1f9895c91959a6498e02d09d2ba0b64c69aa6c664473bc"
LITERAL_PACKED_SHA256 = "50169780dda895e7ce6e9922eca1a7a28f318a260b052782bbce5f9e76783c32"
FULL_METRICS = {"instruction_count": 2217, "instruction_bytes": 4840, "basic_block_count": 377, "decode_reject_count": 0, "baseline_cross_edge_count": 165, "frontier_count": 15}
LOCAL_METRICS = {"instruction_count": 950, "instruction_bytes": 2092, "basic_block_count": 177, "baseline_call_edge_count": 74, "unique_literal_word_count": 77, "literal_bytes": 308}

V7_PAYLOAD_PATH = Path("artifacts/rom-cfg-proven-roots-v7/rom-cfg-proven-roots-v7.json")
V7_PAYLOAD_SHA256 = "184e9b84df829fb1ad41f272aabe931c1a1f86111eebd60629ad2d2a23d89a06"

IMPLEMENTATION_PATHS = {
    "contract": Path("tools/rom_cfg_proven_roots_v17_contract.py"),
    "exporter": Path("tools/export_rom_cfg_proven_roots_v17.py"),
    "verifier": Path("tools/verify_rom_cfg_proven_roots_v17.py"),
    "test_exporter": Path("tests/test_export_rom_cfg_proven_roots_v17.py"),
    "test_verifier": Path("tests/test_verify_rom_cfg_proven_roots_v17.py"),
}
