#!/usr/bin/env python3
"""Frozen constants for the boot register-init dependency CFG packet."""
from pathlib import Path

ROM_BASE=0x08000000;ROM_PATH=Path("rom/base.gba");ROM_SIZE=6_291_456
ROM_SHA256="1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA="rom-boot-register-init-dependency-cfg-v1";VERIFY_SCHEMA=f"{SCHEMA}-verification-v1"
PAYLOAD_NAME=f"{SCHEMA}.json";MANIFEST_NAME="manifest.json"
EXPERIMENT_OUTPUT_ROOT=Path("build/experiments/active/boot-register-init-dependency-cfg-20260905")
OFFICIAL_ARTIFACT=Path("artifacts/rom-boot-register-init-dependency-cfg-v1")

PRECOVERAGE_DIR=Path("artifacts/rom-story-callback-dependency-closures-precoverage-v1")
PRECOVERAGE_MANIFEST_SHA256="fbdc769feb0c7d23752f73cf1caf7578a06a8c7df866cfaf0c64c738e1b0f423"
PRECOVERAGE_ARCHIVE_SHA256="af9fd00d9e5bc5bf10b1d7f63b5e44325498982efe2c9b8b46aada34faa21c00"
PRECOVERAGE_ARCHIVE_SIZE=1_739_024;PRECOVERAGE_RAW_SHA256="b14d1778bc9961356cca7f319c9d2ae85a07a6811276f9ee0cd1bc2070e96b82";PRECOVERAGE_RAW_SIZE=31_201_261
BASELINE={"classified_bytes":6_198_347,"unknown_bytes":93_109,"claim_count":16_793,"segment_count":18_552}

STORY_ARTIFACT=Path("artifacts/rom-story-callback-dependency-closures-v1");STORY_PAYLOAD_NAME="rom-story-callback-dependency-closures.json"
STORY_MANIFEST_SHA256="0c0209dcf0bb5081f83ec7d0c01816e9b40d318bf69b7a2bf9892716e10385ea";STORY_MANIFEST_SIZE=886
STORY_PAYLOAD_SHA256="62d3ad4455afac0c66d629097d2e50603e6c4dcff17b3c4fea5a72f28de0a18b";STORY_PAYLOAD_SIZE=31_998
STORY_VERIFIER=Path("tools/verify_rom_story_callback_dependency_closures.py");STORY_VERIFIER_SHA256="3338abdaeeca3e8187aad6484f7bfeba5b6b5e2a6affe16ca0613405df902364"
V20_ARTIFACT=Path("artifacts/rom-cfg-proven-roots-v20");V20_PAYLOAD_NAME="rom-cfg-proven-roots-v20.json"
V20_MANIFEST_SHA256="7f5ed6e408b834afc91e622898f0eabb7278b7906098dbfff39fa87283975f2d";V20_MANIFEST_SIZE=11_147
V20_PAYLOAD_SHA256="5d3186a688973b1733b0117aedee7c689a5270497c83f8726d4d2540bcfe1543";V20_PAYLOAD_SIZE=20_820
V20_VERIFIER=Path("tools/verify_rom_cfg_proven_roots_v20.py");V20_VERIFIER_SHA256="0f185e030fda6461d5652d67d34850c872f45836ba580ef6a3074883736fde66"
STORY_NEXT_ARTIFACT=Path("artifacts/rom-story-next-dependency-cfg-v1");STORY_NEXT_PAYLOAD_NAME="rom-story-next-dependency-cfg-v1.json"
STORY_NEXT_MANIFEST_SHA256="a5429f89ecfb60da5ce6950063ee5d9df2996eead6ad60d221474429d49e4669";STORY_NEXT_MANIFEST_SIZE=12_773
STORY_NEXT_PAYLOAD_SHA256="d12f4b28c68ba94bc122fc284cd3bbb8fd4fd59426c0bc46ab4b9dcf377a5e6b";STORY_NEXT_PAYLOAD_SIZE=32_054
STORY_NEXT_VERIFIER=Path("tools/verify_rom_story_next_dependency_cfg.py");STORY_NEXT_VERIFIER_SHA256="ed5b35817e06320089bb74914a60ec8765129a4e0c49013cdc6ee9959a1ecfa8"

CONTINUATION_ARTIFACT=Path("artifacts/rom-boot-interwork-continuation-v1");CONTINUATION_PAYLOAD_NAME="rom-boot-interwork-continuation.json"
CONTINUATION_MANIFEST_SHA256="beb4220307bbc0b99b58d6652bfd3f7339928d9e30b104f0fde06c7ed62d82ff";CONTINUATION_MANIFEST_SIZE=10_337
CONTINUATION_PAYLOAD_SHA256="43ba163ac9f8313b9579c660ab701a51006186b45f2b96247fd2e58f0c16babd";CONTINUATION_PAYLOAD_SIZE=105_718
CONTINUATION_VERIFIER=Path("tools/verify_rom_boot_interwork_continuation.py");CONTINUATION_VERIFIER_SHA256="8da8303e47e8666a9883fc411fd274ab1d8bf3651da95a4530dabd152bdcec58"

CFG_INVENTORY=Path("artifacts/rom-cfg-inventory-v2");CFG_INVENTORY_PAYLOAD_NAME="rom-cfg-inventory.json"
CFG_INVENTORY_MANIFEST_SHA256="ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753"
CFG_INVENTORY_PAYLOAD_SHA256="b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd"
CFG_INVENTORY_VERIFIER=Path("tools/verify_rom_cfg_inventory.py");CFG_INVENTORY_VERIFIER_SHA256="a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93"

ROOT=0x06178C;ROOT_ENTRY_RAW="30b581b0";ROOT_ENTRY_SHA256="766eede2e5578d16c3e11a092a16dd98e3716bb825b6e8009ca68c37cef8471b"
PRODUCER=(0x06109E,ROOT,"thumb_bl",4,"00f075fb","f0f0cde8bea058ba34b361665a446c13a6bf59e76f84ef87794d18fec046e8d4")
CODE_RANGES=((0x06178C,0x0617DC),(0x061804,0x06181E),(0x061FDC,0x06207C),(0x0620CC,0x062100))
CODE_RANGE_SHA256S=("de6ed5f3a6894bff2b3288355500648992dec50ad8e0ebd0827beceefba10825","8f68d05ffe42141e68d8c914794566ff1efc4c7867674a6b5eb11f982645c914","57541cc828c8022c18298e589cdf867c5d24bac49c00fefdc1382345c8cdf3e0","a63c55588a05dde5e738e8801e622432d128487d13d28a0f9e0fd5253c2aad82")
PACKED_CODE_SHA256="b20ae45a4169f822fb00419acd2ea55392d4c3c5f6a82279dd27c63af6a574ff"
BLOCK_RANGES=((0x06178C,0x06179C),(0x06179C,0x0617CE),(0x0617CE,0x0617DC),(0x061804,0x06180C),(0x06180C,0x061810),(0x061810,0x061816),(0x061816,0x06181E),(0x061FDC,0x062030),(0x062030,0x06203A),(0x06203A,0x062044),(0x062044,0x06207C),(0x0620CC,0x062100))
BLOCK_VECTOR_SHA256="df80730a62178129428211b83cc63d6569f6d3b5bdea8279f2701321a1e751e8"
LITERAL_RANGES=((0x0617DC,0x061804),(0x061820,0x061824),(0x06207C,0x0620B4),(0x062100,0x06211C))
LITERAL_RANGE_SHA256S=("90b35c9b4e354b737eef2b73be2fd90bc791ca9576ab9e9fbc02db74c1a44a19","ec059cd453eba29035fbeaf03c9b35e27ed128819bae55106b6600f04e3ee075","904cc0d0628a0c44a15b44b368d3eb24d70076442f645aa9ae4d8cbddc6c3306","2e3b65a880f2f91bd18a5b6d5af102755e58e8d43fb600561d33711f4c3cce35")
LITERAL_BINDING_VECTOR_SHA256="8c814cf29937f84f10501ff352936ef6f0843acb695de494308a9cfad3436b21";PACKED_LITERAL_SHA256="10e7bfc4175cd465f0fb324ca2f9d82fee5e664fc4d8901aa8a79e1d31379dae"
OPAQUE_CALLS=((0x06202C,0x09C0E0,"3af058f8"),(0x062036,0x09C0E0,"3af053f8"),(0x062040,0x09C0E0,"3af04ef8"))
FRONTIERS=((0x06181C,"indirect_pc_target","0047","r0"),(0x06207A,"indirect_pc_target","0047","r0"),(0x0620FE,"indirect_pc_target","0047","r0"))
UNION_RANGES=((0x06178C,0x06181E),(0x061820,0x061824),(0x061FDC,0x0620B4),(0x0620CC,0x06211C))
PACKED_PROMOTION_SHA256="86c06d3ccf840184cdfb583622624cec553daab5e0dd73981244d55b8e75694f"
UNKNOWN_HOLE=(0x06181E,0x061820);EXCLUSION=(0x0620B4,0x0620CC)
EXCLUSION_OWNERS=((0x0620B4,0x0620C6,"armv4t_boot_thumb_handoff_reachable_code","boot-thumb-handoff-code-11-0620b4"),(0x0620C6,0x0620C8,"boot_thumb_code_literal_alignment_bytes","boot-thumb-code-literal-gap-06-0620c6"),(0x0620C8,0x0620CC,"armv4t_boot_thumb_handoff_consumed_literal_pool","boot-thumb-handoff-literal-08-0620c8"))
METRICS={"instruction_count":154,"instruction_bytes":318,"basic_block_count":12,"literal_reference_count":32,"unique_literal_word_count":32,"literal_bytes":128,"opaque_call_count":3,"frontier_count":3,"structured_return_count":0}
IMPLEMENTATION_PATHS={"contract":Path("tools/rom_boot_register_init_dependency_cfg_contract.py"),"exporter":Path("tools/export_rom_boot_register_init_dependency_cfg.py"),"verifier":Path("tools/verify_rom_boot_register_init_dependency_cfg.py"),"test_exporter":Path("tests/test_export_rom_boot_register_init_dependency_cfg.py")}
