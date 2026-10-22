#!/usr/bin/env python3
"""Frozen contract for the story-next dependency CFG packet."""
from pathlib import Path

ROM_BASE=0x08000000;ROM_PATH=Path("rom/base.gba");ROM_SIZE=6_291_456
ROM_SHA256="1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA="rom-story-next-dependency-cfg-v1";VERIFY_SCHEMA=f"{SCHEMA}-verification-v1"
PAYLOAD_NAME=f"{SCHEMA}.json";MANIFEST_NAME="manifest.json"
EXPERIMENT_OUTPUT_ROOT=Path("build/experiments/active/story-next-dependency-cfg-20260905")
OFFICIAL_ARTIFACT=Path("artifacts/rom-story-next-dependency-cfg-v1")
PRECOVERAGE_DIR=Path("artifacts/rom-story-callback-dependency-closures-precoverage-v1")
PRECOVERAGE_MANIFEST_SHA256="fbdc769feb0c7d23752f73cf1caf7578a06a8c7df866cfaf0c64c738e1b0f423"
PRECOVERAGE_ARCHIVE_SHA256="af9fd00d9e5bc5bf10b1d7f63b5e44325498982efe2c9b8b46aada34faa21c00"
PRECOVERAGE_ARCHIVE_SIZE=1_739_024;PRECOVERAGE_RAW_SHA256="b14d1778bc9961356cca7f319c9d2ae85a07a6811276f9ee0cd1bc2070e96b82";PRECOVERAGE_RAW_SIZE=31_201_261
BASELINE={"classified_bytes":6_198_347,"unknown_bytes":93_109,"claim_count":16_793,"segment_count":18_552}
STORY_ARTIFACT=Path("artifacts/rom-story-callback-dependency-closures-v1");STORY_MANIFEST_SHA256="0c0209dcf0bb5081f83ec7d0c01816e9b40d318bf69b7a2bf9892716e10385ea";STORY_MANIFEST_SIZE=886;STORY_PAYLOAD_SHA256="62d3ad4455afac0c66d629097d2e50603e6c4dcff17b3c4fea5a72f28de0a18b";STORY_PAYLOAD_SIZE=31_998
V20_ARTIFACT=Path("artifacts/rom-cfg-proven-roots-v20");V20_MANIFEST_SHA256="7f5ed6e408b834afc91e622898f0eabb7278b7906098dbfff39fa87283975f2d";V20_MANIFEST_SIZE=11_147;V20_PAYLOAD_SHA256="5d3186a688973b1733b0117aedee7c689a5270497c83f8726d4d2540bcfe1543";V20_PAYLOAD_SIZE=20_820
CFG_INVENTORY=Path("artifacts/rom-cfg-inventory-v2");CFG_INVENTORY_MANIFEST_SHA256="ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753";CFG_INVENTORY_PAYLOAD_SHA256="b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd";CFG_INVENTORY_VERIFIER_SHA256="a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93";CFG_INVENTORY_BLOCK_BYTES_SHA256="f7d8295970d2e235a7f2c4ce12f73cef2c2676c49e417997706bb7612297ffcc"
CFG_INVENTORY_INTERNAL_BF4_BYTES_SHA256="1b92dd31980e42774253c6483a61134d2611d020391785b04df27c000f372a1d"
CFG_INVENTORY_INTERNAL_BLOCK_BYTES_SHA256="5bd9a7e48e33cae7099a1c0c11e8d2b60b5c07b2123e5e9737b18de3150eaf51"
ROOT=0x088F10;ROOT_ENTRY_SHA256="715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb"
PRODUCERS=((0x08F61A,ROOT,"bl",4,"f9f779fc",False),(0x08F928,ROOT,"bl",4,"f9f7f2fa",True))
CODE_RANGES=((0x088444,0x0884CC),(0x0884DC,0x088560),(0x08857C,0x08859A),(0x0885A0,0x08860E),(0x088620,0x08864A),(0x088F10,0x088F52),(0x088F58,0x088FB4),(0x088FB8,0x088FD0),(0x088FD4,0x089036),(0x08903C,0x089064))
LITERAL_RANGES=((0x0884CC,0x0884DC),(0x088560,0x08857C),(0x08859C,0x0885A0),(0x088610,0x088620),(0x08864C,0x088650),(0x088F54,0x088F58),(0x088FB4,0x088FB8),(0x088FD0,0x088FD4),(0x089038,0x08903C))
UNKNOWN_CODE_RANGES=CODE_RANGES;UNKNOWN_LITERAL_RANGES=LITERAL_RANGES
HOLES=((0x08859A,0x08859C),(0x08860E,0x088610),(0x08864A,0x08864C),(0x088F52,0x088F54),(0x089036,0x089038))
FRONTIERS=((0x0884CA,"indirect_pc_target","0047","r0"),(0x088648,"indirect_pc_target","0847","r1"),(0x089062,"indirect_pc_target","0847","r1"))
OPAQUE_CALLS=((0x88450,0x97130),(0x88468,0x66ae8),(0x8847e,0x66ae8),(0x88484,0x66e84),(0x8848e,0x66efc),(0x88498,0x66efc),(0x884a2,0x66efc),(0x884a6,0x97130),(0x884b4,0x66efc),(0x884ba,0x655b4),(0x884c0,0x6571c),(0x884f4,0x67158),(0x88514,0x9822c),(0x88526,0x66758),(0x8853a,0x66758),(0x8853e,0x6571c),(0x88552,0x8cbf4),(0x8858a,0x61e6c),(0x885a8,0x97130),(0x885b2,0x61e6c),(0x885bc,0x67158),(0x885e2,0x66ae8),(0x885ea,0x92e80),(0x885f0,0x66db4),(0x885f4,0x6571c),(0x88624,0x9c574),(0x8862e,0x8cc18),(0x88634,0x67158),(0x88f26,0x8a490),(0x88f2c,0x61e6c),(0x88f6c,0x62560),(0x88f92,0x65404),(0x88faa,0x61e88),(0x88fc6,0x886e8),(0x88ff2,0x88914),(0x89002,0x95e38),(0x8900c,0x8a490),(0x89020,0x75184),(0x89024,0x7509c),(0x89028,0x62560),(0x89030,0x8a490),(0x8903e,0x8768c),(0x89044,0x61e5c))
OPAQUE_OWNERS={0x61e5c:(0x61e5c,0x61e6a,"cfg-thumb-0002-061e5c"),0x61e6c:(0x61e6c,0x61e7a,"cfg-thumb-0003-061e6c"),0x61e88:(0x61e88,0x61e96,"cfg-thumb-0004-061e88"),0x62560:(0x62560,0x6259c,"cfg-thumb-0007-062560"),0x655b4:(0x655b4,0x655f0,"cfg-thumb-0053-0655b4"),0x6571c:(0x6571c,0x65724,"cfg-thumb-0056-06571c"),0x66758:(0x66758,0x667ca,"cfg-thumb-0074-066758"),0x66ae8:(0x66ae8,0x66b72,"cfg-thumb-0087-066ae8"),0x66db4:(0x66db4,0x66e56,"cfg-thumb-0092-066db4"),0x66e84:(0x66e84,0x66e9a,"cfg-thumb-0094-066e84"),0x66efc:(0x66efc,0x66ff0,"cfg-thumb-0096-066efc"),0x67158:(0x67158,0x6717c,"cfg-thumb-0097-067158"),0x7509c:(0x7509c,0x750ba,"cfg-proven-roots-v6-thumb-0283-00-07509c"),0x75184:(0x75184,0x7518c,"cfg-proven-roots-v6-thumb-0312-00-075184"),0x8768c:(0x8768c,0x87708,"prebattle-menu-controller-code-02-08768c"),0x886e8:(0x886e8,0x88706,"cfg-thumb-0560-0886e8"),0x88914:(0x88914,0x88938,"cfg-proven-roots-v6-thumb-0803-00-088914"),0x8a490:(0x8a490,0x8a4b4,"cfg-thumb-0583-08a490"),0x8cbf4:(0x8cbb4,0x8cc3c,"cfg-thumb-0589-08cbb4"),0x8cc18:(0x8cbb4,0x8cc3c,"cfg-thumb-0589-08cbb4"),0x92e80:(0x92e80,0x92ecc,"cfg-thumb-0646-092e80"),0x95e38:(0x95e38,0x95e4e,"cfg-proven-roots-v6-thumb-2285-00-095e38"),0x97130:(0x97130,0x971be,"cfg-thumb-0690-097130"),0x9822c:(0x9822c,0x98254,"cfg-proven-roots-v6-thumb-2301-00-09822c"),0x9c574:(0x9c574,0x9c576,"cfg-thumb-0786-09c574")}
METRICS={"instruction_count":338,"instruction_bytes":770,"basic_block_count":96,"decode_reject_count":0,"baseline_call_edge_count":43,"frontier_count":3,"unique_literal_word_count":21,"literal_reference_count":21,"literal_bytes":84}
IMPLEMENTATION_PATHS={"contract":Path("tools/rom_story_next_dependency_cfg_contract.py"),"exporter":Path("tools/export_rom_story_next_dependency_cfg.py"),"verifier":Path("tools/verify_rom_story_next_dependency_cfg.py"),"test_exporter":Path("tests/test_export_rom_story_next_dependency_cfg.py")}
