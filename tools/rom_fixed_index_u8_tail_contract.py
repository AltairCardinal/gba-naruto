"""Frozen public contract for the four-byte fixed-index u8 tail packet."""

from pathlib import Path

SCHEMA = "rom-fixed-index-u8-tail-v1"
VERIFY_SCHEMA = f"{SCHEMA}-verification-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "2cc07bc74d24276b994219900ad7419787f9b8832dd62a66bb7839d09df42c01"
PRECOVERAGE_ARTIFACT = Path("artifacts/rom-post-story-dependency-precoverage-v1")
PRECOVERAGE_MANIFEST_SIZE = 1_017
PRECOVERAGE_MANIFEST_SHA256 = "95cb2fef985e13eea7dda71b144e082e35fd3a7b004578df646dbfa18c0ee65a"
PRECOVERAGE_ARCHIVE_NAME = "rom-byte-coverage.json.gz"
PRECOVERAGE_ARCHIVE_SIZE = 1_754_320
PRECOVERAGE_ARCHIVE_SHA256 = "88365f670c9c820760cc1e199f48a1ec6583d1f9ec41b5e86a69866c06baa6b6"
COVERAGE_SIZE = 31_378_342

ROM_BASE = 0x08000000
TABLE_BASE = 0x53E424
CANDIDATE_RANGE = (0x53E492, 0x53E496)
CANDIDATE_RAW = bytes.fromhex("2b2c363f")
CANDIDATE_SHA256 = "bd902ab864b10eae585043d085f4375c20be295e5d64021f885e2fca391fd3ba"
FIXED_INDICES = (0x6E, 0x6F, 0x70, 0x71)

CONSUMER_RANGE = (0x07C724, 0x07C7B2)
CONSUMER_SHA256 = "30db564e71b99a0b9b28c2736aa4c5903f46f62be3f38a37fe7ec9ebe512025e"
PROOF_RANGE = (0x07C728, 0x07C734)
PROOF_RAW = bytes.fromhex("0006000e214d224a80180078")
PROOF_SHA256 = "91b96b971bcbe695b8ec202767dc1589845d32e987901326ff0e66e7504d3c4f"
LITERAL_RANGE = (0x07C7B8, 0x07C7BC)
LITERAL_RAW = bytes.fromhex("24e45308")
LITERAL_VALUE = 0x0853E424
LITERAL_SHA256 = "cc764aa911c7040d08dbff3d89d6ef6a0f34e693e8c83631ce9e9ad6e29ec757"

CALL_TARGET = 0x07C724
CALL_OFFSETS = (
    0x07B9EC, 0x07BC94, 0x07CD5A, 0x07E1F8, 0x07E370, 0x07E4F4,
    0x07EB14, 0x07EBBC, 0x07EC6E, 0x07EC90, 0x07F020, 0x07F04C, 0x07F0BC,
)
FIXED_CALL_OFFSETS = (0x07EB14, 0x07EBBC, 0x07EC6E, 0x07EC90)
EXCLUDED_NON_FIXED_CALL_OFFSETS = tuple(
    offset for offset in CALL_OFFSETS if offset not in FIXED_CALL_OFFSETS
)
CALLER_WINDOWS = (
    (0x07EB10, 0x07EB18, bytes.fromhex("6e200021fdf706fe"), "9f8ed86a27ff7601c8e6232ee575a8f9852ac3562bb4bc51051ce83713e23f8e"),
    (0x07EBB8, 0x07EBC0, bytes.fromhex("6f200021fdf7b2fd"), "993182dfbc8c3619ec0959bc620752445b1c9a407cbef5ee252205032b93d014"),
    (0x07EC6A, 0x07EC72, bytes.fromhex("70200021fdf759fd"), "f00dda4173d39a2f2fd38399ae2201603f6f408450c81cd52555aa815447f008"),
    (0x07EC8C, 0x07EC94, bytes.fromhex("71200021fdf748fd"), "2c8715a50f7041b47fe4749c3e3d87cf32fbeaa533518b1b0dc33d55fec61377"),
)
CALLER_CONCAT_SHA256 = "847c299dd8820bd8d584af07241cbc49d8cb54c726e9c38ae39dba86def6313b"

PAYLOAD_NAME = "rom-fixed-index-u8-tail.json"
MANIFEST_NAME = "manifest.json"
ARTIFACT_PATH = Path("artifacts/rom-fixed-index-u8-tail-v1")
EXPORTER_PATH = Path("tools/export_rom_fixed_index_u8_tail.py")
VERIFIER_PATH = Path("tools/verify_rom_fixed_index_u8_tail.py")
CONTRACT_PATH = Path("tools/rom_fixed_index_u8_tail_contract.py")
TEST_PATH = Path("tests/test_export_rom_fixed_index_u8_tail.py")

OWNER_SEGMENTS = (
    (CONSUMER_RANGE, "armv4t_cfg_reachable_thumb_code", ("cfg-thumb-0461-07c724",)),
    (LITERAL_RANGE, "armv4t_cfg_v2_consumed_literal_word", ("cfg-v2-consumed-literal-0404-07c7b4",)),
    ((0x07EB10, 0x07EB18), "armv4t_event_handler_reachable_thumb_code", ("event-handler-cfg-024-07eaf8",)),
    ((0x07EBB8, 0x07EBC0), "armv4t_event_handler_reachable_thumb_code", ("event-handler-cfg-026-07eba0",)),
    ((0x07EC6A, 0x07EC94), "armv4t_event_handler_reachable_thumb_code", ("event-handler-cfg-030-07ec64",)),
)

NON_CLAIMS = {
    "complete_114_byte_table": False,
    "dynamic_index_domain": False,
    "natural_runtime_reachability": False,
    "business_semantics": False,
    "editing_writeback_or_relocation_safety": False,
    "free_or_allocatable_space": False,
}
