#!/usr/bin/env python3
"""Frozen public contract for the overlap-aware CFG proven-roots v21 packet."""

from pathlib import Path


ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

SCHEMA = "rom-cfg-proven-roots-v21"
VERIFY_SCHEMA = f"{SCHEMA}-verification-v1"
PAYLOAD_NAME = f"{SCHEMA}.json"
MANIFEST_NAME = "manifest.json"
EXPERIMENT_ROOT = Path(
    "build/experiments/active/direct-root-overlap-cfg/root-063400-tier1-20260905"
)
OFFICIAL_ARTIFACT = Path("artifacts/rom-cfg-proven-roots-v21")

PRECOVERAGE = Path("artifacts/rom-post-story-dependency-precoverage-v1")
PRECOVERAGE_MANIFEST_SIZE = 1_017
PRECOVERAGE_MANIFEST_SHA256 = (
    "95cb2fef985e13eea7dda71b144e082e35fd3a7b004578df646dbfa18c0ee65a"
)
PRECOVERAGE_ARCHIVE_SIZE = 1_754_320
PRECOVERAGE_ARCHIVE_SHA256 = (
    "88365f670c9c820760cc1e199f48a1ec6583d1f9ec41b5e86a69866c06baa6b6"
)
PRECOVERAGE_RAW_SIZE = 31_378_342
PRECOVERAGE_RAW_SHA256 = (
    "2cc07bc74d24276b994219900ad7419787f9b8832dd62a66bb7839d09df42c01"
)
PRECOVERAGE_SUMMARY = {
    "classified_bytes": 6_202_729,
    "unknown_bytes": 88_727,
    "claim_count": 16_870,
    "segment_count": 18_641,
}

UPSTREAM_IDENTITIES = (
    (Path("artifacts/rom-boot-interwork-continuation-v1/manifest.json"), 10_337,
     "beb4220307bbc0b99b58d6652bfd3f7339928d9e30b104f0fde06c7ed62d82ff"),
    (Path("artifacts/rom-boot-interwork-continuation-v1/rom-boot-interwork-continuation.json"), 105_718,
     "43ba163ac9f8313b9579c660ab701a51006186b45f2b96247fd2e58f0c16babd"),
    (Path("tools/verify_rom_boot_interwork_continuation.py"), 48_890,
     "8da8303e47e8666a9883fc411fd274ab1d8bf3651da95a4530dabd152bdcec58"),
    (Path("artifacts/battle-effect-sprite-animations-v1/manifest.json"), 569_178,
     "46403c9f070c20561862b5f4ec572a7c511aa199eb3b7b7edae37e97f4877848"),
    (Path("tools/verify_battle_effect_sprite_animations.py"), 64_072,
     "ba22259f41e53398a0f271f806c831b5eaf0052f17784c831d2591c0220f0c6b"),
    (Path("artifacts/battle-effect-sequence-bindings-v1/manifest.json"), 156_832,
     "ec8f41571bb132577ecb7bc57f946a85f219b4c05f3697c89b75be73385b0c73"),
    (Path("tools/verify_battle_effect_sequence_bindings.py"), 21_527,
     "5d0012a1f0a03c6068d0150df16074bdd16cb426325dbb4508db521fc6555a2b"),
    (Path("artifacts/rom-cfg-inventory-v2/manifest.json"), 4_350,
     "ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753"),
    (Path("artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json"), 5_936_694,
     "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd"),
    (Path("tools/verify_rom_cfg_inventory.py"), 45_183,
     "a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93"),
)

ROOT = 0x063400
ENVELOPE = (0x063400, 0x063494)
ROOT_ENTRY_SHA256 = "a4e6ae50ea132622718382b96434f6cbe2f3d6ace48dea6a6c096ddd30199ab9"
ENVELOPE_SHA256 = "94a44c4fc958221054ea3ad5a681f5e67a97c55af97325c953d3b99cd9752b7e"
PRODUCERS = (
    (0x06108A, ROOT, "thumb_bl", 4, "02f0b9f9", True),
    (0x06131C, ROOT, "thumb_bl", 4, "02f070f8", False),
)
ACCEPTED_PRODUCER_CLAIM = "continuation-code-06108a-0610d4"
ACCEPTED_PRODUCER_RANGE = (0x06108A, 0x0610D4)
REJECTED_PRODUCER_CLAIM = "consumer-code-battle_effect_sprite_animations-0612bc"
REJECTED_PRODUCER_RANGE = (0x0612BC, 0x0614E4)

CODE_RANGES = ((0x063400, 0x063490),)
LITERAL_RANGES = ((0x063490, 0x063494),)
UNKNOWN_CODE_RANGES = ((0x063400, 0x06345E), (0x06347E, 0x063490))
UNKNOWN_LITERAL_RANGES = LITERAL_RANGES
EXISTING_OWNER_RANGE = (0x06345E, 0x06347E)
EXISTING_OWNER_CLAIM = "consumer-code-battle_effect_sequence_bindings-06345e"
CROSS_OWNER_INSTRUCTION = (0x06347C, 0x063480)
CROSS_OWNER_INSTRUCTION_RAW_HEX = "38f04afe"
CROSS_OWNER_INSTRUCTION_SHA256 = (
    "c647bdc6dc87ef40a65521e5df5041ce3684f70513f48d999ccda800e7e08fe9"
)

BLOCK_RANGES = (
    (0x063400, 0x063406), (0x063406, 0x063416), (0x063416, 0x06341E),
    (0x06341E, 0x063428), (0x063428, 0x063430), (0x063430, 0x063432),
    (0x063432, 0x06343C), (0x06343C, 0x063446), (0x063446, 0x063448),
    (0x063448, 0x06345C), (0x06345C, 0x063466), (0x063466, 0x06346C),
    (0x06346C, 0x063470), (0x063470, 0x06347A), (0x06347A, 0x063480),
    (0x063480, 0x06348A), (0x06348A, 0x063490),
)
BLOCK_RANGE_VECTOR_SHA256 = (
    "9528c1b1da73c078eac316674c3680fc50c24f05590239f62aa38fe057bfaee8"
)
OPAQUE_CALLS = ((0x063468, 0x09C114), (0x06347C, 0x09C114))
OPAQUE_OWNER = (0x09C114, 0x09C116, "cfg-thumb-0775-09c114")
OPAQUE_BLOCK_ID = "block-thumb-09c114"
FRONTIERS = ({"source": 0x06348E, "reason": "indirect_pc_target"},)
EPILOGUE = (0x06348A, 0x063490)
EPILOGUE_RAW_HEX = "70bc01bc0047"
EPILOGUE_SHA256 = "514f6aa802bdc4d077005cde997c6ee1f921c1ce496ca6cc35e22b9a405f8a71"
STACK_SITES = {0x063400: "70b5", 0x06348A: "70bc", 0x06348C: "01bc"}

CODE_PACKED_SHA256 = "127cd71c4bf8330654d9f6f31c9b347f9ae737c5a152270c5ff44e4d8d1e3ff1"
LITERAL_PACKED_SHA256 = "fca9848680d4fe8534cc39c6888c9698d5eb584ba61218286d90e4c238447d03"
CODE_THEN_LITERAL_SHA256 = ENVELOPE_SHA256
PROMOTION_PACKED_SHA256 = "227b429dc4028ddc6deddb4d2ddd738711f23c3cb1db42a623fdd2330de9302b"

METRICS = {
    "instruction_count": 70,
    "basic_block_count": 17,
    "code_bytes": 144,
    "literal_reference_count": 2,
    "unique_literal_word_count": 1,
    "literal_bytes": 4,
    "opaque_call_count": 2,
    "opaque_unique_target_count": 1,
    "structured_return_count": 0,
    "frontier_count": 1,
}

IMPLEMENTATION_PATHS = {
    "contract": Path("tools/rom_cfg_proven_roots_v21_contract.py"),
    "exporter": Path("tools/export_rom_cfg_proven_roots_v21.py"),
    "verifier": Path("tools/verify_rom_cfg_proven_roots_v21.py"),
    "test_exporter": Path("tests/test_export_rom_cfg_proven_roots_v21.py"),
}
