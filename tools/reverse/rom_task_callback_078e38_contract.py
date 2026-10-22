#!/usr/bin/env python3
"""Frozen constants for the 0x078E38 task-callback closure packet."""

from pathlib import Path

ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "rom-task-callback-078e38-closure-v1"
VERIFY_SCHEMA = f"{SCHEMA}-verification-v1"
PAYLOAD_NAME = f"{SCHEMA}.json"
MANIFEST_NAME = "manifest.json"
OFFICIAL_ARTIFACT = Path("artifacts") / SCHEMA
EXPERIMENT_ROOT = Path("build/experiments/active/task-callback-078e38-closure-20260905")

ROOT = 0x078E38
ENVELOPE = (0x078E38, 0x07914C)
ENVELOPE_SIZE = 788
ENVELOPE_SHA256 = "05503553bc42650c8d3d42c4ae1f4178efed6014b77dae610cf17524c4cb06bf"
CODE_RANGES = (
    (0x078E38, 0x078E6E), (0x078E78, 0x078F02),
    (0x078F08, 0x078FC0), (0x078FD0, 0x079008),
    (0x07900C, 0x07903C), (0x079040, 0x07905E),
    (0x079064, 0x079106), (0x079118, 0x079146),
)
LITERAL_RANGES = (
    (0x078E70, 0x078E78), (0x078F04, 0x078F08),
    (0x078FC0, 0x078FD0), (0x079008, 0x07900C),
    (0x07903C, 0x079040), (0x079060, 0x079064),
    (0x079108, 0x079118), (0x079148, 0x07914C),
)
HOLES = (
    (0x078E6E, 0x078E70), (0x078F02, 0x078F04),
    (0x07905E, 0x079060), (0x079106, 0x079108),
    (0x079146, 0x079148),
)
BLOCK_RANGES = (
    (495160,495188),(495188,495196),(495196,495202),(495202,495208),
    (495208,495212),(495212,495214),(495224,495244),(495244,495250),
    (495250,495278),(495278,495296),(495296,495300),(495300,495314),
    (495314,495318),(495318,495330),(495330,495336),(495336,495344),
    (495344,495348),(495348,495352),(495352,495362),(495368,495376),
    (495376,495388),(495388,495392),(495392,495418),(495418,495424),
    (495424,495426),(495426,495432),(495432,495434),(495434,495444),
    (495444,495456),(495456,495458),(495458,495476),(495476,495490),
    (495490,495504),(495504,495516),(495516,495528),(495528,495546),
    (495546,495550),(495550,495552),(495568,495578),(495578,495596),
    (495596,495622),(495622,495624),(495628,495654),(495654,495674),
    (495674,495676),(495680,495696),(495696,495710),(495716,495720),
    (495720,495746),(495746,495750),(495750,495780),(495780,495800),
    (495800,495806),(495806,495818),(495818,495836),(495836,495862),
    (495862,495876),(495876,495878),(495896,495922),(495922,495926),
    (495926,495942),
)
OPAQUE_CALLS = (
    (0x078E50,0x0655B4),(0x078F7E,0x066D14),(0x078F98,0x066D14),
    (0x078FB6,0x078930),(0x078FBA,0x06571C),(0x078FE8,0x078930),
    (0x079002,0x066758),(0x079022,0x066758),(0x079036,0x0708BC),
    (0x07907E,0x0708BC),(0x0790A0,0x066758),(0x0790B4,0x066758),
    (0x0790C6,0x066D14),(0x0790F2,0x066758),(0x079100,0x094CC8),
    (0x07912E,0x066758),(0x079132,0x06571C),
)
CODE_PACKED_SHA256 = "5e4a0aa24845934f720ec9aece56e635416d319b6e3f05b7e9b4b4cddb00df14"
LITERAL_PACKED_SHA256 = "3e4411efa69c56cc72b45c72ff8b21f9312ff406339b54e5d277907c029d1b34"
CODE_THEN_LITERAL_SHA256 = "39a86a9609bd90115ec76bd8beb64208e2271820f9ee7afc34ee8cadef032e27"
ADDRESS_ORDER_UNION_SHA256 = "361878bfaf3c4edf5da0f7db4266cb1d08446a1fcd4b96393cdfc88d602eb41e"
HOLES_PACKED_SHA256 = "01d448afd928065458cf670b60f5a594d735af0172c8d67f22a81680132681ca"
BLOCK_RANGE_VECTOR_SHA256 = "143f73676153beb89ec21c7a2570b27bac44b7aafd7bb37572f4ee69e9925bde"
METRICS = {"instruction_count":342,"basic_block_count":61,"code_bytes":718,
           "literal_reference_count":15,"unique_literal_word_count":15,
           "literal_bytes":60,"opaque_call_count":17,"opaque_unique_target_count":7,
           "structured_return_count":0,"frontier_count":1}

FRONTIERS = ({"source": 0x079144, "reason": "indirect_pc_target"},)

EPILOGUE = (0x079136, 0x079146)
EPILOGUE_RAW_HEX = "02b038bc9846a146aa46f0bc01bc0047"
EPILOGUE_SHA256 = "b3072b4016ff811fcd06b302dc4b3eff9c521411df3a843f0c9307bddba94ee7"
STACK_SITES = {
    0x078E38:"f0b5",0x078E40:"e0b4",0x078E42:"82b0",0x078F7C:"0192",
    0x078F8A:"019a",0x078FFC:"0096",0x07901C:"0096",0x07909A:"0094",
    0x0790AE:"0094",0x0790EC:"0093",0x07912A:"0091",0x079136:"02b0",
    0x079138:"38bc",0x079140:"f0bc",0x079142:"01bc",
}

POINTER_BYTES = bytes.fromhex("398e0708")
POINTER_OCCURRENCES = (0x079378,)
SOURCE_RANGE = (0x0792B0, 0x0792CE)
SOURCE_SHA256 = "8af88308aafd917f15c527cfb080ae3421582ea1cee99ec94afdff82ef59e55a"
ALLOCATOR_RANGE = (0x0626B4, 0x062768)
ALLOCATOR_SHA256 = "bed7ee16174877d036a3999979b69651fabd7ba619d8bbeaef2f41602b6e44eb"
DISPATCHER_RANGE = (0x062940, 0x062958)
DISPATCHER_SHA256 = "21caf82d007b2b6eca4e31bf893f0a8aa16ce84b6946a88b1fa76f3349e21e0f"
VENEER_RANGE = (0x09C114, 0x09C116)
VENEER_SHA256 = "bac8ca6ee9f77b46c7ab5824c7c59d99fd0ca53ae998ea2872b78bb6a5189cc5"

PRECOVERAGE = Path("artifacts/rom-post-story-dependency-precoverage-v1")
PRECOVERAGE_MANIFEST_SHA256 = "95cb2fef985e13eea7dda71b144e082e35fd3a7b004578df646dbfa18c0ee65a"
PRECOVERAGE_MANIFEST_SIZE = 1017
PRECOVERAGE_ARCHIVE_SHA256 = "88365f670c9c820760cc1e199f48a1ec6583d1f9ec41b5e86a69866c06baa6b6"
PRECOVERAGE_ARCHIVE_SIZE = 1_754_320
PRECOVERAGE_RAW_SHA256 = "2cc07bc74d24276b994219900ad7419787f9b8832dd62a66bb7839d09df42c01"
PRECOVERAGE_RAW_SIZE = 31_378_342
PRECOVERAGE_SUMMARY = {"classified_bytes":6202729,"unknown_bytes":88727,
                       "claim_count":16870,"segment_count":18641}

# path, size, sha256
UPSTREAM_IDENTITIES = (
    (Path("artifacts/rom-cfg-inventory-v2/manifest.json"),4350,"ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753"),
    (Path("artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json"),5936694,"b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd"),
    (Path("tools/verify_rom_cfg_inventory.py"),45183,"a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93"),
    (Path("artifacts/rom-cfg-v2-consumed-literals-v1/manifest.json"),148487,"41a3adb156ce5c07481b7aa903a77f4880b08cc6c13260fc30d25b4227ed232f"),
    (Path("artifacts/rom-cfg-v2-consumed-literals-v1/rom-cfg-v2-consumed-literals.json"),666483,"e08df7333e8b82f3d18497bf5a2a478bf3bf7a5743e50e898cfc819f0b5d29b1"),
    (Path("tools/verify_rom_cfg_v2_consumed_literals.py"),16274,"77d956f412b3ba4de15958e272b473b42286d054c47965b35384d85659a464a8"),
    (Path("artifacts/scene-visual-composites-v1/manifest.json"),2076,"bfa901135f416e48ee5e646d88c1b6669ab8c36d4817b24f2e3664cf00be0da2"),
    (Path("artifacts/scene-visual-composites-v1/scene-visual-composites.json"),21469,"0aded5f95a1cda0f2ee0bc778ab699cf4bc6d95a316f9f2d712eef668f78b71e"),
    (Path("tools/verify_scene_visual_composites.py"),29659,"6ed97d66e3efd5a23ffcf4847060eec37d42af0cd908772e4df470dc2f5dcd71"),
    (Path("artifacts/rom-cfg-proven-roots-v20/manifest.json"),11147,"7f5ed6e408b834afc91e622898f0eabb7278b7906098dbfff39fa87283975f2d"),
    (Path("artifacts/rom-cfg-proven-roots-v20/rom-cfg-proven-roots-v20.json"),20820,"5d3186a688973b1733b0117aedee7c689a5270497c83f8726d4d2540bcfe1543"),
    (Path("tools/verify_rom_cfg_proven_roots_v20.py"),16852,"0f185e030fda6461d5652d67d34850c872f45836ba580ef6a3074883736fde66"),
    (Path("artifacts/character-runtime-oam-task-bindings-v1/manifest.json"),1973,"df2fc83e3322c0584c9410f6b23c798e6dfd400f6a21377552395756152cddfc"),
    (Path("artifacts/character-runtime-oam-task-bindings-v1/bindings.json"),408877,"8930a32d0b72c5ea61b2cf66f1493fcac25fd98a8d75f4ddb488013bcc53771a"),
    (Path("tools/verify_character_runtime_oam_task_bindings.py"),39944,"7d63146f71d7870ebcc6e052bea924d99966f917f46d2351606a8e71edb29512"),
)
OWNER_CLAIMS = {
    "source":"cfg-thumb-0417-07914c",
    "veneer":"cfg-thumb-0775-09c114",
    "allocator":"consumer-code-scene_visual_composites-0626b4",
    "dispatcher":"cfg-v20-reachable_thumb_code-05-062924",
}

IMPLEMENTATION_PATHS = {
    "contract": Path("tools/rom_task_callback_078e38_contract.py"),
    "exporter": Path("tools/export_rom_task_callback_078e38_closure.py"),
    "verifier": Path("tools/verify_rom_task_callback_078e38_closure.py"),
    "test": Path("tests/test_export_rom_task_callback_078e38_closure.py"),
}
