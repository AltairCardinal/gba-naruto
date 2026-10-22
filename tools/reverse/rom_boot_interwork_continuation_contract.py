"""Frozen public contract for the boot interwork call-continuation candidate.

This module contains only constants.  In particular, it does not import the
exporter or the verifier, so either implementation can bind the same packet
without making the independent verifier depend on product code.
"""

from __future__ import annotations

from pathlib import Path


ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

SCHEMA = "rom-boot-interwork-continuation-v1"
VERIFY_SCHEMA = "rom-boot-interwork-continuation-verification-v1"
PAYLOAD_NAME = "rom-boot-interwork-continuation.json"
MANIFEST_NAME = "manifest.json"
EXPERIMENT_ROOT = Path(
    "build/experiments/active/boot-interwork-continuation-luna-20260901"
)
DEFAULT_CANDIDATE = EXPERIMENT_ROOT / "candidate"
OFFICIAL_OUTPUT = Path("artifacts/rom-boot-interwork-continuation-v1")

# The baseline is frozen as an immutable deterministic gzip artifact.  This
# lets the accepted continuation remain independently verifiable after the
# live coverage file is rebuilt to include its promotion.
PRECOVERAGE_DIR = Path("artifacts/rom-boot-interwork-continuation-precoverage-v1")
PRECOVERAGE_MANIFEST_SHA256 = "1274d157a6a61c61d1e9b8709f31d97355174118574310d667a5c8f906118bb5"
PRECOVERAGE_ARCHIVE_SHA256 = "7be5ee2d603ac73d77d39bd1911acd5fda4ab1c0ff07d8583e411fcf882645eb"
PRECOVERAGE_ARCHIVE_SIZE = 1_765_648
PRECOVERAGE_RAW_SHA256 = "984eb8ed8ef72691e1b580b00465d24e1762bb5c0604c35fe76db40153fc42e0"
PRECOVERAGE_RAW_SIZE = 29_741_790
COVERAGE_SCHEMA = "rom-byte-coverage-v1"
COVERAGE_CLASSIFIED_BYTES = 6_155_318
COVERAGE_UNKNOWN_BYTES = 136_138
COVERAGE_CLAIM_COUNT = 16_104
COVERAGE_SEGMENT_COUNT = 17_533

# The fixed producer and its LR continuation.
BL_PRODUCER_OFFSET = 0x061086
BL_PRODUCER_END = 0x06108A
BL_PRODUCER_TARGET = 0x09C56C
BL_PRODUCER_SHA256 = (
    "589051c73628c96114c0977c1ee91cd7446f42932dfeed31936f351e436d58b7"
)
BL_PRODUCER_RAW_HEX = "3bf071fa"
CONTINUATION_ROOT = 0x06108A
CONTINUATION_END = 0x0610E8
CONTINUATION_CODE_END = 0x0610D4
CONTINUATION_RANGE = (CONTINUATION_ROOT, CONTINUATION_END)
CONTINUATION_CODE_RANGE = (CONTINUATION_ROOT, CONTINUATION_CODE_END)
CONTINUATION_LITERAL_RANGES = (
    (0x0610D4, 0x0610D8),
    (0x0610D8, 0x0610DC),
    (0x0610DC, 0x0610E0),
    (0x0610E0, 0x0610E4),
    (0x0610E4, 0x0610E8),
)
CONTINUATION_CODE_BYTES = 74
CONTINUATION_LITERAL_BYTES = 20
CONTINUATION_PROMOTION_BYTES = 94
CONTINUATION_CODE_SHA256 = (
    "dfda6e9d1919d3a5b14515a8c3e0abe5415b105a13651aba7652cfe003fc215a"
)
CONTINUATION_LITERAL_PACKED_SHA256 = (
    "92b2d4d677e8dab743857d1a0142212b216d0fc502ee2641c3f126c3636cb290"
)
CONTINUATION_UNION_RANGE_SHA256 = (
    "29b72618b1e2c07b84a67d8e00c6e239e75562f4daa06b6c0e1fca21eeb16811"
)
CONTINUATION_UNION_PACKED_SHA256 = (
    "837d10f9c983e6f0530ef9c9eb1afda32dc5fb1b2ec35e5da3fd6dee38a666e0"
)

# The continuation is a static root after the BL.  Its final B returns to the
# already classified caller prefix at 0x61082; direct calls are retained as
# opaque outbound edges and are never used to claim their targets here.
CONTINUATION_INSTRUCTION_COUNT = 29
CONTINUATION_BLOCK_COUNT = 11
CONTINUATION_FRONTIER_COUNT = 0
CONTINUATION_LITERAL_BINDING_COUNT = 5
CONTINUATION_EXTERNAL_EDGE_COUNT = 9

# The two-byte Thumb mode switch and ARM branch are part of the fixed call
# spine; they are checked from raw ROM before the existing ARM closure is
# accepted as this candidate's callee.
VENEER_BX_OFFSET = 0x09C56C
VENEER_BX_END = 0x09C56E
VENEER_BX_RAW_HEX = "7847"
VENEER_BX_SHA256 = "aa1170db7a37e96c7cd2677a368bc6541819794ef3984f1d91b8b27914201f6e"
VENEER_ARM_B_OFFSET = 0x09C570
VENEER_ARM_B_END = 0x09C574
VENEER_ARM_B_RAW_HEX = "358ffdea"
VENEER_ARM_B_SHA256 = "979a6ff29e93c31c8a5fd2a1d6502c75b4ae36e8dff16a0b6cabdd4d1a88e33e"

DECODER_FILES = {
    "tools/_vendor/capstone/__init__.py": "17a8db1bfe9cb52a97cc89d4ddc9b3246b5d0ddd330fb592ea17060554032f8e",
    "tools/_vendor/capstone/arm.py": "bd8e7a96074481a55c77192f6202f92a52e8c9022aa68c2de5736edf0e04fff0",
    "tools/_vendor/capstone/arm_const.py": "ca87ac6edbf031e1eff66531743dc6f2e4ba8ea63d532da401a5d1fa28653192",
    "tools/_vendor/capstone/lib/libcapstone.dylib": "00f3876991807d87ef26b6564609dd2e2c46616c476336498f33a8c8501fb35f",
}
DECODER_VERSION = "5.0.7"

# The call target is the previously accepted ARM interwork artifact.  These
# values are intentionally duplicated here so a future replacement artifact
# cannot silently satisfy this contract.
OFFICIAL_ARTIFACT_DIR = Path("artifacts/rom-boot-interwork-v1")
OFFICIAL_MANIFEST_PATH = OFFICIAL_ARTIFACT_DIR / "manifest.json"
OFFICIAL_PAYLOAD_PATH = OFFICIAL_ARTIFACT_DIR / "rom-boot-interwork.json"
OFFICIAL_MANIFEST_SHA256 = (
    "f2673837955194f35daab4f9fb7c0b2fe2dd5967231fcd6d982d0cacb9f749be"
)
OFFICIAL_PAYLOAD_SHA256 = (
    "2f78132647235ca1c9fd155b950ff4128e4b01ca10d0fa0ae0fcfa4fdd37e30d"
)
OFFICIAL_VERIFIER_PATH = Path("tools/verify_rom_boot_interwork.py")
OFFICIAL_VERIFIER_SHA256 = (
    "66d34dc56f837e09c22fcebdd58e2e67b132c133ea7402e8d50f7e187d54984b"
)
OFFICIAL_EXPORTER_PATH = Path("tools/export_rom_boot_interwork.py")
OFFICIAL_EXPORTER_SHA256 = (
    "e9b87cba69eba1307403300d501d660c48ebb99356dd26cccdd1b2f962eadf41"
)
OFFICIAL_TEST_PATH = Path("tests/test_export_rom_boot_interwork.py")
OFFICIAL_TEST_SHA256 = (
    "7d98ef28788ef6d5a44ba0af2b36a7e1834db0be213c6c1138a4d06d5b829d50"
)
OFFICIAL_ROOT_OFFSET = 0x00024C
OFFICIAL_ROOT_END = 0x0003BC
OFFICIAL_ROOT_ENTRY_SHA256 = (
    "8a04c2e346e7375c2cf164f2b0e91ba8c325ffdd38c50e62ec922b266aa6c4dd"
)
OFFICIAL_ARM_INSTRUCTION_COUNT = 92
OFFICIAL_ARM_INSTRUCTION_BYTES = 368
OFFICIAL_ARM_FRONTIER_COUNT = 0
OFFICIAL_ARM_BLOCK_COUNT = 8
OFFICIAL_ARM_EDGE_COUNT = 10
OFFICIAL_ARM_RETURN_OFFSETS = (0x03A4, 0x03B8)
OFFICIAL_ARM_CODE_SHA256 = (
    "b7a934aada08004fec2cd403027a1667c91d6cb93edfae149e237dd9c7908bf3"
)
OFFICIAL_ARM_LITERAL_POOL_SHA256 = (
    "1f206af83e70f2bf5c7e21d4b96b42d639a75b6aa808fb975da4cc94cc41bcb3"
)
OFFICIAL_ARM_REGION_SHA256 = (
    "00fcaba38ae745f4416d9906be0d9fdec3eb1667f9a9b6fca684289287a82995"
)
OFFICIAL_ARM_INSTRUCTION_VECTOR_SHA256 = (
    "c25c738607397cb60f90d73d7a6efe079ef52c89c11f787b0cc7d896101beebf"
)
OFFICIAL_ARM_BLOCK_VECTOR_SHA256 = (
    "1c9d08d16c2f4c3b5cdb4123d8ae94b6fd3bb4f7921c9a28a55b77f279c3af50"
)
OFFICIAL_ARM_EDGE_VECTOR_SHA256 = (
    "ba298a7c1f9f7811e7dd2ac899c7faa42d013599d9e94a6c41e129b34e7176e7"
)
OFFICIAL_ARM_LITERAL_VECTOR_SHA256 = (
    "1e812f886d0e0abe614780f0c4a94af1c789831fd966c59e85e0a6ef690f4e9f"
)

SCOPE = {
    "static_call_continuation_root_proven": True,
    "unique_direct_bl_producer_rebuilt": True,
    "callee_arm_closure_rebuilt_from_raw": True,
    "thumb_continuation_exact_decoder": True,
    "current_unknown_owner_verified": True,
    "natural_runtime_reachability_complete": False,
    "reset_to_root_path_complete": False,
    "business_semantics_proven": False,
    "holes_padding_free_or_edit_safe": False,
    "physical_gba_verified": False,
    "global_code_denominator_complete": False,
    "callee_targets_semantics_proven": False,
}

LIMITATIONS = (
    "This packet proves a static LR continuation after the fixed Thumb BL; it does not prove natural runtime reachability.",
    "The existing ARM interwork artifact is independently re-bound and raw-rebuilt only as the callee closure; no reset-to-root path is claimed.",
    "Only the exact current-unknown continuation code and its five consumed PC-relative literal words are classified.",
    "Outbound calls and the loop back to the known caller prefix remain opaque edges; their target semantics are not claimed.",
    "No business semantics, holes, padding, free space, edit safety, relocation safety, or physical-GBA behavior is claimed.",
)

IMPLEMENTATION_PATHS = {
    "contract": Path("tools/rom_boot_interwork_continuation_contract.py"),
    "exporter": Path("tools/export_rom_boot_interwork_continuation.py"),
    "verifier": Path("tools/verify_rom_boot_interwork_continuation.py"),
    "test_exporter": Path("tests/test_export_rom_boot_interwork_continuation.py"),
    "test_verifier": Path("tests/test_verify_rom_boot_interwork_continuation.py"),
}
