#!/usr/bin/env python3
"""Frozen public contract for the scene source closure packet.

This module deliberately contains constants only.  The exporter and the
independent verifier each reconstruct the pointer denominator, Thumb literal
consumers, coverage ownership, parser-delimited records and OBJ structures.
"""

from __future__ import annotations

from pathlib import Path


ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

SCHEMA = "rom-scene-source-closures-v1"
VERIFY_SCHEMA = f"{SCHEMA}-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
PAYLOAD_NAME = "rom-scene-source-closures.json"
MANIFEST_NAME = "manifest.json"
EXPERIMENT_ROOT = Path(
    "build/experiments/active/scene-source-closures-sol-20260905"
)
OFFICIAL_ARTIFACT = Path("artifacts/rom-scene-source-closures-v1")

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

ENVELOPE = (0x46401C, 0x464534)
ACCIDENTAL_POINTER_WORD = (0x0FC054, 0x464441)
GENUINE_POINTER_WORD = (0x070768, 0x464034)
SELF_POINTER_WORD = (0x464034, 0x46401C)
LDR_ANCHOR = (0x07071C, 0x4812)

POINTER_HIT_COUNT = 138
POINTER_TARGET_COUNT = 84
POINTER_EXTERNAL_COUNT = 132
POINTER_SELF_COUNT = 6
POINTER_HIT_VECTOR_SHA256 = "bc2ba31ec1de0e22717045602661ac22dc61873a784717a25c7bd661351cfbe7"

LITERAL_COUNT = 131
CONSUMER_COUNT = 133
CONSUMER_ROOT_COUNT = 77
CLASSIFIED_CONSUMER_COUNT = 125
CURRENT_UNKNOWN_CONSUMER_COUNT = 8
CONSUMER_VECTOR_SHA256 = "4efafd28aebf3ff83c56bb4eb8b92c68dc796e191fc56706939f7a2370baa2da"
MEMBERSHIP_VECTOR_SHA256 = "19177345d98fbeb0cab3bfe0d40b88048e0b64dce4e2d4cf9a86b69ed554211f"

OBJ_TABLE_ROOTS = (0x464034, 0x464040, 0x46443C, 0x464454)
OBJ_SPECS = (
    {
        "closure_range": [0x46401C, 0x464044],
        "definition_table_range": [0x464034, 0x464038],
        "definition_targets": [0x46401C],
        "definition_component_counts": [1],
        "animation_table_range": [0x464040, 0x464044],
        "animation_targets": [0x464038],
    },
    {
        "closure_range": [0x46431C, 0x46445C],
        "definition_table_range": [0x46443C, 0x464444],
        "definition_targets": [0x4643C0, 0x46431C],
        "definition_component_counts": [6, 8],
        "animation_table_range": [0x464454, 0x46445C],
        "animation_targets": [0x464444, 0x46444C],
    },
)
OBJ_RANGES = ((0x46401C, 0x464044), (0x46431C, 0x46445C))
OBJ_CLAIM_COUNT = 2
OBJ_BYTES = 360
OBJ_RANGE_VECTOR_SHA256 = "a085d1eac184e3c575e09c0afff330c25d9fb9c7975828eb38b2bc56bc9c0d6e"
OBJ_PACKED_SHA256 = "27b20a96178fa060298cb8ad4b11dd223a398bf686440faa242cfbc9e26632ed"

REJECTED_UNOWNED_SOURCE_ROOTS = (0x464298, 0x4642AC)
SOURCE_CLAIM_COUNT = 71
SOURCE_BYTES = 655
SOURCE_RANGE_VECTOR_SHA256 = "d60a23e2c3a891f382bf638fce2ec52065608754f52bcd3bd24d7f51374ba657"
SOURCE_PACKED_SHA256 = "166509a082f6b68f937d83fd7213db1f71d2e5706154ba3daf001bfed208efaa"

PROMOTION_CLAIM_COUNT = 73
PROMOTION_BYTES = 1_015
PROMOTION_RANGE_VECTOR_SHA256 = "6ffb61cecaed71780c43b8c8d74b53dd72e890e0fde12b51eb1547f7d634ccce"
PROMOTION_PACKED_SHA256 = "76908b595f7c8e4a9beba4cba0f2cb378311749daa336d9d16561831f83024bf"

ALIGNMENT_GAP_RANGE_COUNT = 46
ALIGNMENT_GAP_BYTES = 90
ALIGNMENT_GAP_RANGE_VECTOR_SHA256 = "2606f1c6bb427e961243419f90a7254c668c47d9fa680e371e7e11607dc7ff05"
ALIGNMENT_GAP_PACKED_SHA256 = "988a09c9a6ee66322f9f274fe0ede1186eaf12b1c9fdd5f62152f998223521db"

UNKNOWN_HOLE_RANGE_COUNT = 23
UNKNOWN_HOLE_BYTES = 199
UNKNOWN_HOLE_RANGE_VECTOR_SHA256 = "fa0bf75960b1b3d600c8c0f46c78d58a61274e3bd6d110266bb9b43f45406254"
UNKNOWN_HOLE_PACKED_SHA256 = "44dc2b1c7ffda8ceea7ec731c91c5f91c3f20efac65622548378d7ae6933333f"

IMPLEMENTATION_PATHS = {
    "contract": Path("tools/rom_scene_source_closures_contract.py"),
    "exporter": Path("tools/export_rom_scene_source_closures.py"),
    "verifier": Path("tools/verify_rom_scene_source_closures.py"),
    "test": Path("tests/test_export_rom_scene_source_closures.py"),
}
OFFICIAL_EXPORT_COMMAND = (
    "python3", "tools/export_rom_scene_source_closures.py", "--root", ".",
    "--output", "artifacts/rom-scene-source-closures-v1",
)
OFFICIAL_VERIFY_COMMAND = (
    "python3", "tools/verify_rom_scene_source_closures.py", "--root", ".",
    "--artifact", "artifacts/rom-scene-source-closures-v1",
)

LIMITATIONS = (
    "Only parser-delimited source records with at least one accepted code/CFG literal consumer, plus two independently parsed OBJ closures, are classified.",
    "The two opcode-shaped roots at 0x464298 and 0x4642AC remain unknown because every apparent consumer is itself current-unknown.",
    "The 90 one-to-three-byte physical gaps are excluded for a separate alignment packet; 199 larger residual bytes remain unknown.",
    "No natural reachability, translated text semantics, padding intent, editing, relocation, free-space or allocation safety is claimed.",
)
