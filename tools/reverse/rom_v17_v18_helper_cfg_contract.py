#!/usr/bin/env python3
"""Frozen public constants for the V17/V18 helper CFG packet."""

from pathlib import Path


SCHEMA = "rom-v17-v18-helper-cfg-v1"
VERIFY_SCHEMA = f"{SCHEMA}-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_BASE = 0x08000000
OFFICIAL = Path("artifacts/rom-v17-v18-helper-cfg-v1")
PAYLOAD_NAME = "rom-v17-v18-helper-cfg.json"
MANIFEST_NAME = "manifest.json"

ROOTS = (
    0x090564, 0x090584, 0x0905A4, 0x090618, 0x090634, 0x090658,
    0x090758, 0x0908D8, 0x090A20, 0x090A90, 0x095F38,
)
CODE_RANGES = (
    (0x090564, 0x090610), (0x090618, 0x090656),
    (0x090658, 0x0906DE), (0x090758, 0x0908D2),
    (0x0908D8, 0x0909B0), (0x0909C4, 0x090A0A),
    (0x090A20, 0x090A8E), (0x090A90, 0x090AA8),
    (0x095F38, 0x095F58),
)
LITERAL_RANGES = (
    (0x090610, 0x090618), (0x0906E0, 0x0906E4),
    (0x0908D4, 0x0908D8), (0x0909B0, 0x0909C4),
    (0x090A0C, 0x090A20),
)
HOLES = (
    (0x090656, 0x090658), (0x0906DE, 0x0906E0),
    (0x090756, 0x090758), (0x0908D2, 0x0908D4),
    (0x090A0A, 0x090A0C), (0x090A8E, 0x090A90),
)
CODE_SHA256 = "a9b669d64133662aadfd480e4183ddaefc9ce96a2a7f9f7250c0476d399d5c5b"
LITERAL_SHA256 = "4376accd51fa65e224b815f034d24ce4d812de382ac087e6a9d04ca813489c9d"
HOLE_SHA256 = "15ec7bf0b50732b49f8228e07d24365338f9e3ab994b00af08e5a3bffe55fd8b"
CODE_RANGE_SHA256 = "e82e07178d0db21687eff74ba5fa3d5c768caa3f720b46e3ad4d79eaad0de114"
LITERAL_RANGE_SHA256 = "d3fcb3907c2d9909ddf21eedb19e2ffc4496f43b51ce35f5bdaae0a473e772f3"
HOLE_RANGE_SHA256 = "bbab8039af3c3e40afa24f5dfe8b686e21f762b03528f55017b2582a3e567055"
PROMOTION_RANGE_SHA256 = "fec06f25c6c13dd985e0b2d5081f3c7d74cd26f4da90e4417a557b1d1aba9e68"
PROMOTION_SHA256 = "0d14901d2a8bd0c9655f0ff353a19cc9ee64019a16ef87b8e7700057c2a52f27"
LITERAL_BINDING_SHA256 = "d31061da02fca1cb64a5f6ca38727a9076001aedb4f27e5563f7a95c31897870"
ROOT_VECTOR_SHA256 = "229eafc469731c9090410b0b22fe2305a78cb334c44c3a9407f16e684629df14"

DIRECT_BRANCH_COUNTS = {"bl": 13_070, "b": 31_345, "bcond": 55_494}
DIRECT_BRANCH_VECTOR_SHA256 = "d6410ee805b9977a1ce27d1abb156343b6d646ca265f0897c2f1c754b26b92ed"
ROOT_MATCH_VECTOR_SHA256 = "213d3a23b0e5be9da2d1fe64da396d258a95a42b1cde8c5825154168f015df04"
CODE_MATCH_VECTOR_SHA256 = "a4d7811fbcf0cbeae98f6a914c9892019752ba416bed6a9a514008aa9a75524b"
INTERNAL_MATCH_VECTOR_SHA256 = "2ebed82a60a6813fa1a54f045f1338875ad76e2e16d70a655e34b2288702f354"
EXTERNAL_MATCH_VECTOR_SHA256 = "9b1c83765e73f4cf5295b77395b62974fa75c82dd7b9285a495cbdf2644757b6"
UNBOUND_PRODUCER = (0x090FF0, 0x090758, "bl", 4, "fff7b2fb")
DATA_FALSE_POSITIVE = (0x485DAE, 0x0909A4, "bl", 4, "0af4f9fd")

OPAQUE_EXITS = (
    (0x09056A, 0x064700), (0x090572, 0x09C574),
    (0x090576, 0x064A48), (0x09058A, 0x064700),
    (0x090592, 0x09C574), (0x090596, 0x064A48),
    (0x0905B8, 0x09C110), (0x090670, 0x09C110),
    (0x09067E, 0x09C110), (0x090770, 0x0655B4),
    (0x0907B0, 0x0906E4), (0x090828, 0x0906E4),
    (0x0908BE, 0x063604), (0x0908F2, 0x0655B4),
    (0x0909A6, 0x0626B4), (0x0909DA, 0x09C0E0),
    (0x0909E8, 0x062788), (0x0909F6, 0x063604),
    (0x090A4A, 0x0655B4), (0x090A6C, 0x066758),
    (0x090A72, 0x0655B4), (0x090A98, 0x0655B4),
    (0x095F44, 0x0655B4), (0x095F4A, 0x095E8C),
)

REGISTER_RETURNS = (
    (0x090564, 0x090582, "01bc0047"),
    (0x090584, 0x0905A2, "01bc0047"),
    (0x0905A4, 0x09060E, "02bc0847"),
    (0x090634, 0x090654, "01bc0047"),
    (0x090658, 0x0906DC, "02bc0847"),
    (0x090758, 0x0908D0, "01bc0047"),
    (0x0908D8, 0x090A08, "01bc0047"),
    (0x090A20, 0x090A8C, "01bc0047"),
    (0x090A90, 0x090AA6, "01bc0047"),
    (0x095F38, 0x095F56, "02bc0847"),
)
LR_RETURN = (0x090618, 0x090632, "7047")
SP_OPERAND_VECTOR = (
    (0x090762, "sub", "sp, #8"), (0x09076E, "str", "r2, [sp]"),
    (0x090832, "str", "r0, [sp, #4]"), (0x09083E, "ldr", "r3, [sp, #4]"),
    (0x0908AE, "ldr", "r0, [sp]"), (0x0908C2, "add", "sp, #8"),
    (0x0908E2, "sub", "sp, #0x18"), (0x090982, "str", "r0, [sp]"),
    (0x09098E, "str", "r0, [sp, #4]"), (0x090994, "str", "r0, [sp, #8]"),
    (0x090998, "str", "r0, [sp, #0xc]"), (0x09099C, "str", "r0, [sp, #0x10]"),
    (0x0909C4, "add", "r2, sp, #0x14"), (0x0909D6, "add", "r0, sp, #0x14"),
    (0x0909FA, "add", "sp, #0x18"), (0x090A28, "sub", "sp, #4"),
    (0x090A32, "ldr", "r4, [sp, #0x1c]"), (0x090A62, "str", "r4, [sp]"),
    (0x090A80, "add", "sp, #4"),
)
SP_OPERAND_RAW_VECTOR_SHA256 = "a607678854a079427932f91b18f606e39c4aed025672a0c70794f5aaa068997f"

EVIDENCE_FILES = (
    (Path("artifacts/rom-cfg-proven-roots-v17/manifest.json"),
     "9ec11b3e29382a896a06064c5e8b878a6761c32dc910344e6be48c377fca2834"),
    (Path("artifacts/rom-cfg-proven-roots-v17/rom-cfg-proven-roots-v17.json"),
     "94a6adb989ac812a6a1730e1b0c47a4f0f985529e37c65ce29d531a1e7a0101d"),
    (Path("tools/verify_rom_cfg_proven_roots_v17.py"),
     "1be8ee4983775ff2f0bb61fbb4543e0578082d452d24bda6b498ddbe3b731f4c"),
    (Path("artifacts/rom-cfg-proven-roots-v18/manifest.json"),
     "0eccd4e7235e88ca2711f6afff4adad8d939e0ff8b757c405f6194b49138a651"),
    (Path("artifacts/rom-cfg-proven-roots-v18/rom-cfg-proven-roots-v18.json"),
     "fa92bc6fc3234bbc053e902567125cf2e1653aca39b3928e80ffb66043c76859"),
    (Path("tools/verify_rom_cfg_proven_roots_v18.py"),
     "002ed4e782a65ef7766993e8ac9ed6fe74b52ded3d22cc7369a1fe75c87ee683"),
    (Path("artifacts/rom-cfg-inventory-v2/manifest.json"),
     "ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753"),
    (Path("artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json"),
     "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd"),
    (Path("tools/verify_rom_cfg_inventory.py"),
     "a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93"),
    (Path("artifacts/rom-cfg-proven-roots-v6/manifest.json"),
     "e00d8a1b7b08305a44f7ac3d36a5e294d1f69b5f05ceab151e14749cf92802f4"),
    (Path("artifacts/rom-cfg-proven-roots-v6/rom-cfg-proven-roots-v6.json"),
     "e5b27a55c77cd1df4ac5ec39f2dd05735b0b53c01b7cbbcf1620db1681a3c3ec"),
    (Path("tools/verify_rom_cfg_proven_roots_v6.py"),
     "4fc2ad61b98ce3655f1528e773566f63f84f1184209086bd96d3e23c51a8ceb4"),
    (Path("artifacts/scene-visual-composites-v1/manifest.json"),
     "bfa901135f416e48ee5e646d88c1b6669ab8c36d4817b24f2e3664cf00be0da2"),
    (Path("artifacts/scene-visual-composites-v1/scene-visual-composites.json"),
     "0aded5f95a1cda0f2ee0bc778ab699cf4bc6d95a316f9f2d712eef668f78b71e"),
    (Path("tools/verify_scene_visual_composites.py"),
     "6ed97d66e3efd5a23ffcf4847060eec37d42af0cd908772e4df470dc2f5dcd71"),
    (Path("artifacts/rom-gpu-copy-queue-inventory-v1/manifest.json"),
     "3a3f4d06f27560dfcf2674c13802e2fbcc551246e5de121b1f62747a09f32a95"),
    (Path("artifacts/rom-gpu-copy-queue-inventory-v1/rom-gpu-copy-queue-inventory.json"),
     "798b72cbeb69cae522f77f586794cd0bf9d1775d57d590479daf89e808ca23bf"),
    (Path("tools/verify_rom_gpu_copy_queue_inventory.py"),
     "7314eef6758b055a9a30dc5778e1d001b1328a9c65a1435306f44759b52f2ce0"),
    (Path("artifacts/rom-m4a-byte-inventory-v1/manifest.json"),
     "1c0205bc8dde65c887f18f9f55fccce5770d2ebf283bb1a4589fd6d392c40194"),
    (Path("tools/verify_rom_m4a_byte_inventory.py"),
     "61f0ae3ddf40916e738030655fa5e5c41242cd98db5adbf102ab60f749d4c511"),
)
