#!/usr/bin/env python3
"""Frozen public contract for the story-selector dependency CFG packet."""

from pathlib import Path

ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

SCHEMA = "rom-story-selector-dependency-cfg-v1"
VERIFY_SCHEMA = f"{SCHEMA}-verification-v1"
PAYLOAD_NAME = f"{SCHEMA}.json"
MANIFEST_NAME = "manifest.json"
EXPERIMENT_OUTPUT_ROOT = Path("build/experiments/active/story-selector-dependency-cfg-20260905")
OFFICIAL_ARTIFACT = Path("artifacts/rom-story-selector-dependency-cfg-v1")

PRECOVERAGE_DIR = Path("artifacts/rom-post-story-dependency-precoverage-v1")
PRECOVERAGE_MANIFEST_SHA256 = "95cb2fef985e13eea7dda71b144e082e35fd3a7b004578df646dbfa18c0ee65a"
PRECOVERAGE_MANIFEST_SIZE = 1_017
PRECOVERAGE_ARCHIVE_SHA256 = "88365f670c9c820760cc1e199f48a1ec6583d1f9ec41b5e86a69866c06baa6b6"
PRECOVERAGE_ARCHIVE_SIZE = 1_754_320
PRECOVERAGE_RAW_SHA256 = "2cc07bc74d24276b994219900ad7419787f9b8832dd62a66bb7839d09df42c01"
PRECOVERAGE_RAW_SIZE = 31_378_342
BASELINE = {"classified_bytes": 6_202_729, "unknown_bytes": 88_727,
            "claim_count": 16_870, "segment_count": 18_641}

STORY_ARTIFACT = Path("artifacts/rom-story-state-callback-cfg-v1")
STORY_PAYLOAD_NAME = "rom-story-state-callback-cfg.json"
STORY_MANIFEST_SHA256 = "8384dee3207e426361545a94be1b0c1052381a177e159ef85f452f636db5380a"
STORY_MANIFEST_SIZE = 5_858
STORY_PAYLOAD_SHA256 = "f82f2472f49d9b6b620aee162a65ca372ead47ae5aa73c4f5e25888482d57ab5"
STORY_PAYLOAD_SIZE = 16_837
STORY_VERIFIER = Path("tools/verify_rom_story_state_callback_cfg.py")
STORY_VERIFIER_SHA256 = "ab808e73e40858b4bf737875ddcebfb8286a662b55af0c36424215e506867d98"

ROOT_RANGE = (0x08F544, 0x08F594)
ROOT_RAW_HEX = "f0b54f464646c0b486b00004040c1749c2225201101c088080225200e02040000090032001900e20029000200390f420800004900f20059003200021c023d5f73fff201cfff7a4ff01201021d5f7b6f8"
ROOT_BYTES_SHA256 = "ec6b47d0f464048c6403a5ce1d2dc8772c7b67bc82890081ec575bf8cb18cf6b"
INSTRUCTION_COUNT = 37
INSTRUCTION_VECTOR_SHA256 = "45a21a888ddd96cbbaa13236e1b47a2c32d4e0ee08b98f8b5d406d2e771df9e8"

PRODUCERS = (
    (0x08F676, "fff765ff", "e8cc38d7b0ddd8450c1c6463287ef3229ada1767989ed9e5783ce0fac23a870c",
     (0x08F672, 0x08F67A), "20040014fff765ff", "20d5038fe78abf3eaf6291199079fa27afd169d54ff1d369676971595e1e9fab", False),
    (0x08F8DE, "fff731fe", "60b405249b08c8a9510ffc20c50e00c9dea4cfa8596d941b57979c53b42bdaff",
     (0x08F8DA, 0x08F8E2), "3ae7a07dfff731fe", "49622b097f64f1fac7ce6e77dddcecc23bdec5365cbceb70e95a51c6163ddaf8", True),
)
ACCEPTED_OWNER = ((0x08F872, 0x08F8EE), "armv4t_story_state_callback_reachable_thumb_code",
                  "story-callback-reachable_thumb_code-04-08f872",
                  "e6fad7438b65c96f937c5599389b4bee0fac098c52634e2eaa04e463d7b87908")
REJECTED_OWNER_RANGE = (0x08F5D4, 0x08F68C)

OPAQUE_CALLS = ((0x08F582, 0x065404), (0x08F588, 0x08F4D4), (0x08F590, 0x064700))
OPAQUE_SPECS = {
    0x08F582: ("d5f73fff", "36c44bbbb82d3fd96a5f59d1c15a011b6b3c1636f4f19278e5da302e432ecf44", 0x065404,
               (0x065404, 0x065554), "consumer_code_slice", "consumer-code-battle_effect_sprite_animations-065404"),
    0x08F588: ("fff7a4ff", "40eea546e3f9b746f976e7a051e0648554f62bf10a8304aa23876b685b36eb61", 0x08F4D4,
               (0x08F4D4, 0x08F500), "armv4t_cfg_reachable_thumb_code", "cfg-thumb-0608-08f4d4"),
    0x08F590: ("d5f7b6f8", "829c7e9347c269d726046d4106a64b3fff74f0be7ef50da75b9149c53e65ebc1", 0x064700,
               (0x064700, 0x06474C), "armv4t_cfg_reachable_thumb_code", "cfg-thumb-0025-064700"),
}
LITERAL = (0x08F552, "1749", "c29226ca4227e3cc237a46511b82bd43ae23a9be213429106f57327b54c1042a",
           (0x08F5B0, 0x08F5B4), "4c000003", 0x0300004C,
           "cb8a71dc0af46fe8acd79c3998e0878090e80516a09b6e04d647d9c59e21f7e1")
FALLTHROUGH = (0x08F594, "074f", "566565361ec05ac7d42c40b8732d8b560ebbf08b512067e674a872fff1ffc3df",
               (0x08F594, 0x08F5D4), "consumer_code_slice", "chapter-root-table-selector")

IMPLEMENTATION_PATHS = {
    "contract": Path("tools/rom_story_selector_dependency_cfg_contract.py"),
    "exporter": Path("tools/export_rom_story_selector_dependency_cfg.py"),
    "verifier": Path("tools/verify_rom_story_selector_dependency_cfg.py"),
    "test_exporter": Path("tests/test_export_rom_story_selector_dependency_cfg.py"),
}
