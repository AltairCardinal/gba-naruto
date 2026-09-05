#!/usr/bin/env python3
"""Frozen public contract for the two fixed pair tables near 0x53E00A.

This module intentionally contains constants only.  The exporter and the
independent verifier each decode the Thumb consumers themselves.
"""

from pathlib import Path


SCHEMA = "rom-fixed-pair-tables-v1"
VERIFY_SCHEMA = f"{SCHEMA}-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"

ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_BASE = 0x08000000

OFFICIAL = Path("artifacts/rom-fixed-pair-tables-v1")
PAYLOAD_NAME = "rom-fixed-pair-tables.json"
MANIFEST_NAME = "manifest.json"

TABLE_A_RANGE = (0x53E00A, 0x53E014)
TABLE_A_SHA256 = "cc82a04afbe44c3d7a74aa855326899f3cd23d9ad22432dda5edc4157bff2dd6"
TABLE_A_RAW_HEX = "000200fc000300fe0001"
TABLE_A_RECORD_SIZE = 2
TABLE_A_RECORD_COUNT = 5

TABLE_B_RANGE = (0x53E014, 0x53E034)
TABLE_B_SHA256 = "2dec89836378ee4d332104d626748e46a2fa34d5f36cf2aff2ee9c177195b7c4"
TABLE_B_RAW_HEX = (
    "00000000f6ff0a000a00140000001e0005000500fbff0f000f00190005002300"
)
TABLE_B_RECORD_SIZE = 4
TABLE_B_RECORD_COUNT = 8

COMBINED_RANGE = (0x53E00A, 0x53E034)
COMBINED_SHA256 = "302b9316bccc3a094764c7c1a21e24e053ceea53ff5490a258bb78fa95067d86"

# A is a ten-iteration loop.  The consumer begins with the literal load;
# the two instructions immediately before it establish sl == 0.
A_CFG_ROOT = 0x0807C0D2
A_CONSUMER_SITE = 0x0807C0D6
A_CFG_STOP = 0x0807C106
A_LITERAL_WORD_SITE = 0x0807C15C
A_BASE_VALUE = 0x0853E00A
A_BASE_LITERAL_RAW_HEX = "0ae05308"
A_BASE_LITERAL_OCCURRENCES = (0x0807C15C,)
A_ITERATION_COMPARE = 9
A_ITERATION_COUNT = 10
A_LOAD_COUNT = 5
A_LOAD_OFFSETS = (0, 2, 4, 6, 8)
A_RECORD_STRIDE = 2

# B has nine independent entry paths.  The first six use r7 as the loaded
# base and the final three are switch arms that use r2 and join a shared
# second-load continuation.
B_BASE_VALUE = 0x0853E014
B_BASE_LITERAL_RAW_HEX = "14e05308"
B_CONSUMER_LITERAL_SITES = (
    (0x0807BA38, 0x0807BAF4),
    (0x0807BB34, 0x0807BC5C),
    (0x0807BD14, 0x0807BDF0),
    (0x0807BF1C, 0x0807BFC8),
    (0x0807C00A, 0x0807C070),
    (0x0807C18C, 0x0807C334),
    (0x0807C7F8, 0x0807C814),
    (0x0807C824, 0x0807C83C),
    (0x0807C844, 0x0807C890),
)
B_BASE_LITERAL_OCCURRENCES = tuple(site for _, site in B_CONSUMER_LITERAL_SITES)
B_MASK = 7
B_INDEX_SHIFT = 2
B_RECORD_STRIDE = 4
B_RECORD_COUNT = 8
B_MAX_ACCESS_OFFSET = 30
B_LOAD_OFFSETS = (0, 2)

# The surrounding bytes are deliberately retained as unknown.  These values
# are file offsets, not claims that either interval is padding/free space.
LEFT_GAP_RANGE = (0x53DFBF, 0x53E00A)
RIGHT_GAP_RANGE = (0x53E034, 0x53E496)

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

# This is the single baseline segment containing both the promoted range and
# its two retained gaps.  The packet verifies the segment is still unknown;
# it does not write the coverage ledger.
COVERAGE_UNKNOWN_SEGMENT = (0x53DFBF, 0x53E496)
