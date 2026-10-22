#!/usr/bin/env python3
"""Verify thirteen fixed align4 byte ranges between accepted artifacts.

The source artifacts deliberately left these bytes unknown.  This verifier
does not reinterpret either source artifact.  It independently binds the raw
terminal instruction, the exact two-byte zero range, the align4 equation, and
the immediately following already-proven structure for each boundary.
"""

from __future__ import annotations

import argparse
from collections import Counter
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any


VERIFY_SCHEMA = "rom-artifact-bound-alignment-gaps-verification-v1"
PROMOTION_BATCH = "rom-artifact-bound-alignment-gaps-v1"
PRIMARY_CLASS = "artifact_bound_4byte_alignment_bytes"
CLAIM_KIND = "artifact_bound_alignment_gap_bytes"

ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
SOURCE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_SHA256 = SOURCE_ROM_SHA256

SCHEDULER_ARTIFACT = Path("artifacts/rom-task-scheduler-core-v1")
SCHEDULER_SCHEMA = "rom-task-scheduler-core-v1"
SCHEDULER_MANIFEST = SCHEDULER_ARTIFACT / "manifest.json"
SCHEDULER_PAYLOAD = SCHEDULER_ARTIFACT / "rom-task-scheduler-core.json"
SCHEDULER_BINARY = SCHEDULER_ARTIFACT / "rom-task-scheduler-core.bin"
SCHEDULER_MANIFEST_SHA256 = (
    "88ef48526ed1bd096a8ece9a58aa4f5770f207084634a125f04dc99561c7d58c"
)
SCHEDULER_MANIFEST_SIZE = 80_919
SCHEDULER_PAYLOAD_SHA256 = (
    "298dc0cf30765e0afe33487f92cce231bd76d4056719f825c1c9cef98d12a59d"
)
SCHEDULER_PAYLOAD_SIZE = 226_440
SCHEDULER_BINARY_SHA256 = (
    "2cdbf5ee8ee1f24e9d5590363f05cf177c21821209d8b735666b4844c829842f"
)
SCHEDULER_BINARY_SIZE = 308
SCHEDULER_VERIFIER_PATH = "tools/verify_rom_task_scheduler_core.py"
SCHEDULER_VERIFIER_SHA256 = (
    "90133f94b749dbd3d2d08404ac3be5a7a275f261076c82c8c01312271760d9f4"
)

PSG_ARTIFACT = Path("artifacts/rom-psg-frequency-lookup-v1")
PSG_SCHEMA = "rom-psg-frequency-lookup-v1"
PSG_MANIFEST = PSG_ARTIFACT / "manifest.json"
PSG_PAYLOAD = PSG_ARTIFACT / "rom-psg-frequency-lookup.json"
PSG_BINARY = PSG_ARTIFACT / "rom-psg-frequency-lookup.bin"
PSG_MANIFEST_SHA256 = (
    "4fffbcc7e252595834adb368d10b3ce8f13323aee18cc518d98e0ff9c519575f"
)
PSG_MANIFEST_SIZE = 10_899
PSG_PAYLOAD_SHA256 = (
    "d2631b1a65a2e9fa0114dbd76a4e2c89853e3b2f402a491fdbc466e79dacd733"
)
PSG_PAYLOAD_SIZE = 13_876
PSG_BINARY_SHA256 = (
    "e625a5fcc208a971a1ec98723f12b863a707fa9dd3ba8442f7f6d86b3099623b"
)
PSG_BINARY_SIZE = 226
PSG_VERIFIER_PATH = "tools/verify_rom_psg_frequency_lookup.py"
PSG_VERIFIER_SHA256 = (
    "c87ab33b067a35a0105e21967dc0caad5fe91368942f34baf91218d69258f616"
)

HELPER_ARTIFACT = Path("artifacts/rom-cgb-helper-bounded-cfg-v1")
HELPER_SCHEMA = "rom-cgb-helper-bounded-cfg-v1"
HELPER_MANIFEST = HELPER_ARTIFACT / "manifest.json"
HELPER_PAYLOAD = HELPER_ARTIFACT / "rom-cgb-helper-bounded-cfg.json"
HELPER_BINARY = HELPER_ARTIFACT / "rom-cgb-helper-bounded-cfg.bin"
HELPER_MANIFEST_SHA256 = "8a53b3ee982799583e08ef852fb2cac9771f856e77ed104cc2814cfd1e7ef6d1"
HELPER_MANIFEST_SIZE = 1_609
HELPER_PAYLOAD_SHA256 = "dccdca087744e57136b180dba1c3e4151c123efecec10d5d53f90894dc760960"
HELPER_PAYLOAD_SIZE = 42_154
HELPER_BINARY_SHA256 = "87c62bbe5f0e9d25ee5b11398ecdd3ed5b41782d4873871205f71c1122a4c1dc"
HELPER_BINARY_SIZE = 180
HELPER_VERIFIER_PATH = "tools/verify_rom_cgb_helper_bounded_cfg.py"
HELPER_VERIFIER_SHA256 = "d09f828511215b59fe8b60ba4bcf7e63fca48fc36d4c105e75175fa3b11179f3"
HELPER_CONTRACT_SHA256 = "e1f4d0b840d52b19ee996ee7c0ba18c41511f0c96b37f498f77954a24c9105b7"

CGBSOUND_ARTIFACT = Path("artifacts/rom-cgbsound-bounded-cfg-v1")
CGBSOUND_SCHEMA = "rom-cgbsound-bounded-cfg-v1"
CGBSOUND_MANIFEST = CGBSOUND_ARTIFACT / "manifest.json"
CGBSOUND_PAYLOAD = CGBSOUND_ARTIFACT / "rom-cgbsound-bounded-cfg.json"
CGBSOUND_BINARY = CGBSOUND_ARTIFACT / "rom-cgbsound-bounded-cfg.bin"
CGBSOUND_MANIFEST_SHA256 = "4248c0fed46682d06918ac124d3c861a60c12117023a773190ff831840963b6e"
CGBSOUND_MANIFEST_SIZE = 1_594
CGBSOUND_PAYLOAD_SHA256 = "362a3dc1b5819a57310482b7fbdd94bb2f79e9d439ea44713798140d1d79b18d"
CGBSOUND_PAYLOAD_SIZE = 178_551
CGBSOUND_BINARY_SHA256 = "edebdbe6e5cf5f9cf04fdb93839846f7e37e6516914b77a7517413c88ee9a151"
CGBSOUND_BINARY_SIZE = 1_084
CGBSOUND_VERIFIER_PATH = "tools/verify_rom_cgbsound_bounded_cfg.py"
CGBSOUND_VERIFIER_SHA256 = "6af3510f319c58cdb9cf70c115f6a1b2b3ffc0b4fb331f247604dbdb8e637961"
CGBSOUND_CONTRACT_SHA256 = "12171aa29cd29d14f26dc491e4b0a5bb8ddd3fe6d6daac9f73e732786194561a"

SCHEDULER_MANIFEST_KEYS = frozenset(
    {
        "artifact_schema", "artifact_status", "coverage_baseline", "entry_proof",
        "files", "implementation", "limitations", "producer", "promotion",
        "provenance_inputs", "rom", "schema", "scope", "summary",
        "verification", "verifier",
    }
)
PSG_MANIFEST_KEYS = frozenset(
    {
        "artifact_schema", "artifact_status", "coverage_baseline",
        "coverage_projection", "files", "implementation", "limitations",
        "producer", "promotion", "rom", "schema", "scope", "verification",
        "verifier",
    }
)
SCHEDULER_VERIFICATION_SHA256 = "3ed43912ca3771d8614ffe34a05e6af980dd67e52c63e5e00b5306e57bb7bdc9"
PSG_VERIFICATION_SHA256 = "a0ac8875f4d58390901c5e0f15d0839a5094c76c6abe80ab9598df5eab7770f4"
SCHEDULER_MANIFEST_SEMANTIC_SHA256 = "3b463a1b4ab8819a4e4a7879b94838e1881b1de21cd7a7e1aae3ce20602dc001"
SCHEDULER_PAYLOAD_SEMANTIC_SHA256 = "1f24e09a2276b73363662b8d671768b33f4b95b82a4eabed706194e8686dd0f8"
PSG_MANIFEST_SEMANTIC_SHA256 = "2140a778043f25a96667a70d21cf2ee0a4a368a50b59f8fe533ce3877c14fc80"
PSG_PAYLOAD_SEMANTIC_SHA256 = "1a0f9d01ac476c561d408238abbe6709e3fd13795c4d89289da9c3af9ef37235"
SCHEDULER_CLAIMS_SHA256 = "d6ac8e4ee3218cbdf5a4b8213f135a0053d35a04c4d9a9783d0f4631fc3a8e9a"
SCHEDULER_PROVENANCE_SHA256 = "e05e19024f3d9f036981a25266e849ed86b169758e9ffc9d0dc12f3dc1c7be82"
PSG_SEMANTIC_RANGES_SHA256 = "b11d2d0252fe2eb4d5554920d2f99c581ef5d792c9d770cb72e092e2569225ec"
PSG_LITERAL_BINDINGS_SHA256 = "f94390467bff7169734645aa566c5029c57104ec845b8f66c931e24639049b0c"

RANGE_VECTOR = (
    (0x061D62, 0x061D64),
    (0x061D7A, 0x061D7C),
    (0x061DEA, 0x061DEC),
    (0x09B4C6, 0x09B4C8),
    (0x09B572, 0x09B574),
    (0x09B586, 0x09B588),
    (0x09B676, 0x09B678),
    (0x09B696, 0x09B698),
    (0x09B702, 0x09B704),
    (0x09B762, 0x09B764),
    (0x09B94A, 0x09B94C),
    (0x09B96E, 0x09B970),
    (0x09B9E2, 0x09B9E4),
)
RANGE_VECTOR_SHA256 = (
    "d6582d3ca46f1bacb82537740370874320c79592f3c9512747affd4db5285741"
)
PACKED_BYTES_SHA256 = (
    "659d36ca563ba4622daabb36a71dafaf6060cdcbf89bb12e75426198496d272c"
)
ZERO_PAIR_SHA256 = (
    "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7"
)

BOUNDARY_VECTOR = (
    (
        "scheduler-return-to-literal-061d62",
        SCHEDULER_SCHEMA,
        (0x061D10, 0x061D62),
        "promoted_thumb_code",
        "scheduler-code-02-061d10",
        (0x061D60, 0x061D62),
        "return",
        "bx",
        "r0",
        "0047",
        None,
        (0x061D62, 0x061D64),
        "consumed_literal_range",
        (0x061D64, 0x061D70),
        "scheduler-literal-01-061d64",
    ),
    (
        "scheduler-branch-to-function-061d7a",
        SCHEDULER_SCHEMA,
        (0x061D70, 0x061D7A),
        "promoted_thumb_code",
        "scheduler-code-03-061d70",
        (0x061D78, 0x061D7A),
        "unconditional_branch",
        "b",
        "#0x8061d72",
        "fbe7",
        0x061D72,
        (0x061D7A, 0x061D7C),
        "owned_thumb_function",
        (0x061D7C, 0x061DEA),
        "cfg-thumb-0000-061d7c",
    ),
    (
        "scheduler-return-to-literal-061dea",
        SCHEDULER_SCHEMA,
        (0x061D7C, 0x061DEA),
        "owned_thumb_function",
        "cfg-thumb-0000-061d7c",
        (0x061DE8, 0x061DEA),
        "return",
        "bx",
        "r0",
        "0047",
        None,
        (0x061DEA, 0x061DEC),
        "consumed_literal_range",
        (0x061DEC, 0x061E00),
        "scheduler-literal-02-061dec",
    ),
    (
        "psg-branch-to-literal-09b4c6",
        PSG_SCHEMA,
        (0x09B494, 0x09B4C6),
        "promoted_thumb_code",
        "psg-frequency-code-a-09b494",
        (0x09B4C4, 0x09B4C6),
        "unconditional_branch",
        "b",
        "#0x809b52e",
        "33e0",
        0x09B52E,
        (0x09B4C6, 0x09B4C8),
        "consumed_literal_range",
        (0x09B4C8, 0x09B4CC),
        "psg-frequency-noise-literal-09b4c8",
    ),
    (
        "cgb-helper-branch-to-literal-09b572",
        HELPER_SCHEMA,
        (0x09B56C, 0x09B572),
        "cgb_helper_bounded_thumb_code",
        "cgb-helper-code-09b56c",
        (0x09B570, 0x09B572),
        "unconditional_branch",
        "b",
        "#0x809b582",
        "07e0",
        0x09B582,
        (0x09B572, 0x09B574),
        "consumed_literal_range",
        (0x09B574, 0x09B578),
        "cgb-helper-literal-09b574",
    ),
    (
        "cgb-helper-return-to-literal-09b586",
        HELPER_SCHEMA,
        (0x09B578, 0x09B586),
        "cgb_helper_bounded_thumb_code",
        "cgb-helper-code-09b578",
        (0x09B584, 0x09B586),
        "return",
        "bx",
        "lr",
        "7047",
        None,
        (0x09B586, 0x09B588),
        "consumed_literal_range",
        (0x09B588, 0x09B58C),
        "cgb-helper-literal-09b588",
    ),
    (
        "cgbsound-branch-to-literal-09b676",
        CGBSOUND_SCHEMA,
        (0x09B66C, 0x09B676),
        "cgbsound_bounded_thumb_code",
        "cgbsound-code-09b66c",
        (0x09B674, 0x09B676),
        "unconditional_branch",
        "b",
        "#0x809b6ac",
        "1ae0",
        0x09B6AC,
        (0x09B676, 0x09B678),
        "consumed_literal_range",
        (0x09B678, 0x09B684),
        "cgbsound-literal-09b678",
    ),
    (
        "cgbsound-branch-to-literal-09b696",
        CGBSOUND_SCHEMA,
        (0x09B684, 0x09B696),
        "cgbsound_bounded_thumb_code",
        "cgbsound-code-09b684",
        (0x09B694, 0x09B696),
        "unconditional_branch",
        "b",
        "#0x809b6b4",
        "0ee0",
        0x09B6B4,
        (0x09B696, 0x09B698),
        "consumed_literal_range",
        (0x09B698, 0x09B6A4),
        "cgbsound-literal-09b698",
    ),
    (
        "cgbsound-branch-to-literal-09b702",
        CGBSOUND_SCHEMA,
        (0x09B6A4, 0x09B702),
        "cgbsound_bounded_thumb_code",
        "cgbsound-code-09b6a4",
        (0x09B700, 0x09B702),
        "unconditional_branch",
        "b",
        "#0x809b770",
        "36e0",
        0x09B770,
        (0x09B702, 0x09B704),
        "consumed_literal_range",
        (0x09B704, 0x09B710),
        "cgbsound-literal-09b704",
    ),
    (
        "cgbsound-branch-to-literal-09b762",
        CGBSOUND_SCHEMA,
        (0x09B710, 0x09B762),
        "cgbsound_bounded_thumb_code",
        "cgbsound-code-09b710",
        (0x09B760, 0x09B762),
        "unconditional_branch",
        "b",
        "#0x809b78a",
        "13e0",
        0x09B78A,
        (0x09B762, 0x09B764),
        "consumed_literal_range",
        (0x09B764, 0x09B768),
        "cgbsound-literal-09b764",
    ),
    (
        "cgbsound-branch-to-literal-09b94a",
        CGBSOUND_SCHEMA,
        (0x09B768, 0x09B94A),
        "cgbsound_bounded_thumb_code",
        "cgbsound-code-09b768",
        (0x09B948, 0x09B94A),
        "unconditional_branch",
        "b",
        "#0x809b95e",
        "09e0",
        0x09B95E,
        (0x09B94A, 0x09B94C),
        "consumed_literal_range",
        (0x09B94C, 0x09B954),
        "cgbsound-literal-09b94c",
    ),
    (
        "cgbsound-branch-to-literal-09b96e",
        CGBSOUND_SCHEMA,
        (0x09B954, 0x09B96E),
        "cgbsound_bounded_thumb_code",
        "cgbsound-code-09b954",
        (0x09B96C, 0x09B96E),
        "unconditional_branch",
        "b",
        "#0x809b982",
        "09e0",
        0x09B982,
        (0x09B96E, 0x09B970),
        "consumed_literal_range",
        (0x09B970, 0x09B974),
        "cgbsound-literal-09b970",
    ),
    (
        "cgbsound-branch-to-literal-09b9e2",
        CGBSOUND_SCHEMA,
        (0x09B974, 0x09B9E2),
        "cgbsound_bounded_thumb_code",
        "cgbsound-code-09b974",
        (0x09B9E0, 0x09B9E2),
        "unconditional_branch",
        "b",
        "#0x809ba20",
        "1ee0",
        0x09BA20,
        (0x09B9E2, 0x09B9E4),
        "consumed_literal_range",
        (0x09B9E4, 0x09B9EC),
        "cgbsound-literal-09b9e4",
    ),
)
BOUNDARY_VECTOR_SHA256 = (
    "7dd56d026c90f090f3b4fbceb055bbe3db35786e915e4ace4ae61a6b06230843"
)

CLAIM_DENOMINATOR_VECTOR = tuple(
    (
        row[0],
        row[11],
        PRIMARY_CLASS,
        CLAIM_KIND,
        row[12],
        row[1],
    )
    for row in BOUNDARY_VECTOR
)
CLAIM_DENOMINATOR_SHA256 = (
    "1962c626da011e7ac32287662593e55cea72d5d21b003a419e78085a087b8d46"
)

SOURCE_FILE_VECTOR = (
    (
        SCHEDULER_MANIFEST.as_posix(),
        SCHEDULER_MANIFEST_SHA256,
        SCHEDULER_MANIFEST_SIZE,
    ),
    (
        SCHEDULER_PAYLOAD.as_posix(),
        SCHEDULER_PAYLOAD_SHA256,
        SCHEDULER_PAYLOAD_SIZE,
    ),
    (
        SCHEDULER_BINARY.as_posix(),
        SCHEDULER_BINARY_SHA256,
        SCHEDULER_BINARY_SIZE,
    ),
    (PSG_MANIFEST.as_posix(), PSG_MANIFEST_SHA256, PSG_MANIFEST_SIZE),
    (PSG_PAYLOAD.as_posix(), PSG_PAYLOAD_SHA256, PSG_PAYLOAD_SIZE),
    (PSG_BINARY.as_posix(), PSG_BINARY_SHA256, PSG_BINARY_SIZE),
    (HELPER_MANIFEST.as_posix(), HELPER_MANIFEST_SHA256, HELPER_MANIFEST_SIZE),
    (HELPER_PAYLOAD.as_posix(), HELPER_PAYLOAD_SHA256, HELPER_PAYLOAD_SIZE),
    (HELPER_BINARY.as_posix(), HELPER_BINARY_SHA256, HELPER_BINARY_SIZE),
    (
        CGBSOUND_MANIFEST.as_posix(),
        CGBSOUND_MANIFEST_SHA256,
        CGBSOUND_MANIFEST_SIZE,
    ),
    (
        CGBSOUND_PAYLOAD.as_posix(),
        CGBSOUND_PAYLOAD_SHA256,
        CGBSOUND_PAYLOAD_SIZE,
    ),
    (CGBSOUND_BINARY.as_posix(), CGBSOUND_BINARY_SHA256, CGBSOUND_BINARY_SIZE),
)
SOURCE_FILE_VECTOR_SHA256 = (
    "d14919e7abafeb1891e1336d0511b5ab0e44ef6091ee010ca842ca6c6fd3f92f"
)

NON_CLAIM_KEYS = (
    "padding_semantics_claimed",
    "nop_instruction_claimed",
    "reserved_space_claimed",
    "free_space_claimed",
    "allocatable_space_claimed",
    "natural_runtime_reachability_claimed",
    "global_unreachability_claimed",
    "compiler_authorship_claimed",
    "editing_writeback_relocation_safe_claimed",
    "right_structure_semantics_extended_claimed",
    "all_alignment_gaps_exhaustive_claimed",
)
NON_CLAIMS = {key: False for key in NON_CLAIM_KEYS}
LIMITATIONS = (
    "Only the thirteen listed two-byte ranges are classified as bytes required to reach each immediately following align4-bound fixed structure.",
    "The bytes are not claimed to be instructions, NOPs, padding, reserved space, free space, or allocatable space.",
    "The source artifacts retain their historical scopes and owners; this result does not extend the semantics of the right-hand literal ranges or Thumb function.",
    "Natural runtime reachability, global reachability or unreachability, compiler authorship, editing, writeback, and relocation safety remain unclaimed.",
)

SCHEDULER_CODE_RANGES = (
    (0x061C58, 0x061C80),
    (0x061C8C, 0x061D10),
    (0x061D10, 0x061D62),
    (0x061D70, 0x061D7A),
)
SCHEDULER_LITERAL_RANGES = (
    (0x061C80, 0x061C8C),
    (0x061D64, 0x061D70),
    (0x061DEC, 0x061E00),
)
SCHEDULER_OWNED_PROVENANCE_RANGES = (
    (0x061D7C, 0x061DEA),
    (0x061E00, 0x061E1C),
)
SCHEDULER_UNKNOWN_RANGES = RANGE_VECTOR[:3]
PSG_CODE_RANGES = ((0x09B494, 0x09B4C6), (0x09B4CC, 0x09B534))
PSG_UNKNOWN_RANGES = (RANGE_VECTOR[3],)

OWNER_SHA256 = {
    (0x061D10, 0x061D62): (
        "5d12c1a3a0baca5ccd5b4954d11584f758fcbec878ff80ff62fcbe029e44cabc"
    ),
    (0x061D70, 0x061D7A): (
        "0f2ccaffa103a304988869555af6236f0866af5f4f60f26fbbe2704bcf82e7bc"
    ),
    (0x061D7C, 0x061DEA): (
        "a95b7b4ebd38bd2422bad8c1ac40a932dae4f2173577b466152c8e1f0410660d"
    ),
    (0x09B494, 0x09B4C6): (
        "969892b0f481afc4872493396ed034c0a696cd3c56ca07d4c0b5d68369e7365d"
    ),
    (0x09B56C, 0x09B572): "30c6c9fcb611330459336092dfdf9059b742dabc6d5f773ae67f501c1caadc3f",
    (0x09B578, 0x09B586): "6531a1df4bcdc95692713b4c346c135e75339afb73d35dd2934ff15e9f606d99",
    (0x09B66C, 0x09B676): "82c41b731bb51eda5c4f1e518bcbe5bd24383285b310eb3529dbd332baa97721",
    (0x09B684, 0x09B696): "310b0efa036d4193e5031df362d88f684111106908b74a13bc8d8d6051de3f55",
    (0x09B6A4, 0x09B702): "322c40d1faf3a126ba4d2cb7647fbb8d0d7fe271576b32b6d7eea2815dca20b5",
    (0x09B710, 0x09B762): "1dd6c73c8e2889f9ec54a4298431541e92669bc1042021901f6548b03d7c6606",
    (0x09B768, 0x09B94A): "be11fa9cbce478459eaa53790d54b50be8af6b1f8ea979200e5d359a822a1dfb",
    (0x09B954, 0x09B96E): "3103fe9dbc2aef74901cc58e862444d4d05c8a894eea55b459af150e0c107e3c",
    (0x09B974, 0x09B9E2): "3dc08cf18753e9d393ec6063adf2391007679a59d5c76b1b8e4a292323c3de3d",
}
RIGHT_SHA256 = {
    (0x061D64, 0x061D70): (
        "b44c66f532b78332e719eed4e93fba84fdf5e09b552c1ef4abe0a51230e619c1"
    ),
    (0x061D7C, 0x061DEA): OWNER_SHA256[(0x061D7C, 0x061DEA)],
    (0x061DEC, 0x061E00): (
        "4fdd345be5715be0cc303f492e8a6b916ff3849b4916a45c16885ec64682890d"
    ),
    (0x09B4C8, 0x09B4CC): (
        "73cbc760a9346eacd3a16553ac98763cb1a6ee27dbf7d5fa1bfafdb4ce74d9b5"
    ),
    (0x09B574, 0x09B578): "d0455d972504810561aaa6b9cc70d69a9ad49abc84a3df38789afdd8eb9236eb",
    (0x09B588, 0x09B58C): "bd56e77404afec2e1cb1d293f4b56e5188b6e7c5d7aaf39d58dbd1de177f28fd",
    (0x09B678, 0x09B684): "164b6ec13f1c38fcd5d802c242991b31133912d7c9b7646a67b055dd9c37288f",
    (0x09B698, 0x09B6A4): "a0c75541973e91098dbe01f8d2a1a3c4e1e26a66d40f37239ef12477848d71f5",
    (0x09B704, 0x09B710): "5ad3ec1a7bdfa9663a8d12dd5b15cd1013a51d0eb50fd7032783061eed5003ca",
    (0x09B764, 0x09B768): "bfa1417d1dfb9abae35a079e4362dd0a8a3183f7d858197e967d25136e9b9717",
    (0x09B94C, 0x09B954): "4950d6ff3af2748c3139c4696c3e67ec47406f10330e83fce3f32a5f27a5f34a",
    (0x09B970, 0x09B974): "718d44854b4098ea99f25e6518f1dc48ee6f60a046ad5163ce18bb59f49b67dd",
    (0x09B9E4, 0x09B9EC): "1e2dbdfa88824243df8f52b267a7196eea98a7ca890c3877d74891272b0cbf1a",
}

HELPER_EXCLUDED = (
    (0x09B572, 0x09B574),
    (0x09B586, 0x09B588),
)
CGBSOUND_EXCLUDED = RANGE_VECTOR[6:]
HELPER_LITERAL_RANGES = (
    (0x09B560, 0x09B564),
    (0x09B568, 0x09B56C),
    (0x09B574, 0x09B578),
    (0x09B588, 0x09B58C),
)
CGBSOUND_LITERAL_RANGES = (
    (0x09B614, 0x09B618),
    (0x09B660, 0x09B66C),
    (0x09B678, 0x09B684),
    (0x09B698, 0x09B6A4),
    (0x09B704, 0x09B710),
    (0x09B764, 0x09B768),
    (0x09B94C, 0x09B954),
    (0x09B970, 0x09B974),
    (0x09B9E4, 0x09B9EC),
)

BOUNDED_CONTRACTS = {
    HELPER_SCHEMA: {
        "excluded": HELPER_EXCLUDED,
        "literal_ranges": HELPER_LITERAL_RANGES,
        "code_kind": "cgb_helper_bounded_thumb_code",
        "literal_kind": "cgb_helper_consumed_literal_bytes",
        "claim_count": 9,
        "code_bytes": 164,
        "literal_bytes": 16,
        "total_bytes": 180,
        "range_vector_sha256": "ea942377babe2613c9affe8711b6480f6e9e27e60da7aeb483112790de3b85b3",
        "packed_bytes_sha256": HELPER_BINARY_SHA256,
        "literal_range_vector_sha256": "ef5c2b2dbc43d612c4d0c96272f74cf4d2c0322306b359b04780c374ccbf563e",
        "literal_packed_sha256": "01d705cc2e13fbb303c3f9b4b889ead90b5082f621806104e9997b35f186b038",
        "literal_binding_count": 4,
        "literal_bindings_sha256": "86eead1f4aa940c096d2da57df6ef6e718785812862acc3cc3a2dec66c453313",
        "promotion_rows_sha256": "cf8014c749305df617b75cbc1bc2d80352883d92a4a461d505b95dd900c41133",
        "scope_false": (
            "allocatable_free_space_proven",
            "audio_behavior_proven",
            "natural_runtime_reachability",
        ),
    },
    CGBSOUND_SCHEMA: {
        "excluded": CGBSOUND_EXCLUDED,
        "literal_ranges": CGBSOUND_LITERAL_RANGES,
        "code_kind": "cgbsound_bounded_thumb_code",
        "literal_kind": "cgbsound_consumed_literal_bytes",
        "claim_count": 19,
        "code_bytes": 1008,
        "literal_bytes": 76,
        "total_bytes": 1084,
        "range_vector_sha256": "3386a673407d2191f9b9427725f95e3864b92009ea32de433d28c9665c618f57",
        "packed_bytes_sha256": CGBSOUND_BINARY_SHA256,
        "literal_range_vector_sha256": "826e54ab02a6a66cf9d7a2e4726c4efce7a89017e39c4ada47badfbad52c47b1",
        "literal_packed_sha256": "b846e32ff2c1871e4f7042efc7a1d8cad1515b23c1ab26349abc8208bd3c3da5",
        "literal_binding_count": 19,
        "literal_bindings_sha256": "6140171c9465f3a5133e1d306785b51fb8087bd13e6b51a1361645e9f803b860",
        "promotion_rows_sha256": "7a5d279cac8128089800ff5938ce22ca848ee9e0cabcc4ef988b5325d448fc84",
        "scope_false": (
            "allocatable_free_space_proven",
            "audio_behavior_proven",
            "natural_runtime_reachability",
        ),
    },
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _vector_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def _vector_sha(value: Any) -> str:
    return _sha(_vector_json(value))


def _semantic_sha(value: Any) -> str:
    return _sha(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


def _lists(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_lists(item) for item in value]
    if isinstance(value, list):
        return [_lists(item) for item in value]
    return value


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _slice(rom: bytes, start: int, end: int, label: str) -> bytes:
    if start < 0 or end < start or end > len(rom):
        raise ValueError(f"{label} range is outside the ROM")
    return rom[start:end]


def _safe_root(root: Path | str) -> Path:
    path = Path(root)
    if path.is_symlink():
        raise ValueError("repository root is a symlink")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ValueError("repository root is missing") from error
    if not resolved.is_dir():
        raise ValueError("repository root is not a directory")
    for marker in ("tools", "tests", "rom", "artifacts"):
        candidate = resolved / marker
        if not candidate.is_dir() or candidate.is_symlink():
            raise ValueError("repository root is outside the expected project tree")
    return resolved


def _safe_file(
    root: Path,
    relative: Path,
    expected_sha256: str,
    expected_size: int,
) -> bytes:
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"source file uses a symlink: {relative.as_posix()}")
    try:
        resolved = cursor.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"source file is missing: {relative.as_posix()}") from error
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"source file escapes repository root: {relative.as_posix()}") from error
    if not resolved.is_file():
        raise ValueError(f"source path is not a regular file: {relative.as_posix()}")
    raw = resolved.read_bytes()
    if len(raw) != expected_size or _sha(raw) != expected_sha256:
        raise ValueError(f"source file identity changed: {relative.as_posix()}")
    return raw


def _safe_artifact_directory(root: Path, relative: Path, names: set[str]) -> None:
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"source artifact uses a symlink: {relative.as_posix()}")
    try:
        resolved = cursor.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"source artifact is missing: {relative.as_posix()}") from error
    if not resolved.is_dir():
        raise ValueError(f"source artifact is not a directory: {relative.as_posix()}")
    entries = list(resolved.iterdir())
    if any(entry.is_symlink() or not entry.is_file() for entry in entries):
        raise ValueError(f"source artifact contains a symlink or non-file: {relative.as_posix()}")
    if {entry.name for entry in entries} != names:
        raise ValueError(f"source artifact file denominator changed: {relative.as_posix()}")


def _artifact_snapshot(
    root: Path,
    relative: Path,
    expected: dict[str, tuple[str, int]],
) -> dict[str, bytes]:
    if relative.is_absolute() or not relative.parts or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise ValueError(
            f"source artifact path is not repository-relative: {relative.as_posix()}"
        )
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    open_directories: list[int] = []
    anchored_components: list[
        tuple[int, str, int, tuple[int, int, int, int]]
    ] = []
    try:
        root_fd = os.open(root, directory_flags)
    except OSError as error:
        raise ValueError("repository root snapshot open failed") from error
    try:
        open_directories.append(root_fd)
        root_before = os.fstat(root_fd)
        if not stat.S_ISDIR(root_before.st_mode):
            raise ValueError("repository root snapshot is not a directory")

        parent_fd = root_fd
        for part in relative.parts:
            try:
                child_fd = os.open(part, directory_flags, dir_fd=parent_fd)
            except OSError as error:
                raise ValueError(
                    "source artifact ancestor open failed or uses a symlink: "
                    f"{relative.as_posix()}"
                ) from error
            child_before = os.fstat(child_fd)
            if not stat.S_ISDIR(child_before.st_mode):
                os.close(child_fd)
                raise ValueError(
                    f"source artifact ancestor is not a directory: {relative.as_posix()}"
                )
            open_directories.append(child_fd)
            anchored_components.append(
                (
                    parent_fd,
                    part,
                    child_fd,
                    (
                        child_before.st_dev,
                        child_before.st_ino,
                        child_before.st_mtime_ns,
                        child_before.st_ctime_ns,
                    ),
                )
            )
            parent_fd = child_fd

        directory_fd = parent_fd
        directory_before = os.fstat(directory_fd)
        if not stat.S_ISDIR(directory_before.st_mode):
            raise ValueError(f"source artifact is not a directory: {relative.as_posix()}")
        names_before = set(os.listdir(directory_fd))
        if names_before != set(expected):
            raise ValueError(f"source artifact member denominator changed: {relative.as_posix()}")

        result: dict[str, bytes] = {}
        for name, (expected_sha256, expected_size) in expected.items():
            try:
                member_fd = os.open(
                    name,
                    os.O_RDONLY | os.O_NOFOLLOW,
                    dir_fd=directory_fd,
                )
            except OSError as error:
                if error.errno == errno.ELOOP:
                    raise ValueError(
                        f"source artifact member is a symlink: {relative / name}"
                    ) from error
                raise ValueError(f"source artifact member open failed: {relative / name}") from error
            try:
                member_before = os.fstat(member_fd)
                if not stat.S_ISREG(member_before.st_mode):
                    raise ValueError(f"source artifact member is not regular: {relative / name}")
                chunks: list[bytes] = []
                while True:
                    chunk = os.read(member_fd, 1 << 20)
                    if not chunk:
                        break
                    chunks.append(chunk)
                raw = b"".join(chunks)
                member_after = os.fstat(member_fd)
                before_identity = (
                    member_before.st_dev,
                    member_before.st_ino,
                    member_before.st_size,
                    member_before.st_mtime_ns,
                    member_before.st_ctime_ns,
                )
                after_identity = (
                    member_after.st_dev,
                    member_after.st_ino,
                    member_after.st_size,
                    member_after.st_mtime_ns,
                    member_after.st_ctime_ns,
                )
                if before_identity != after_identity:
                    raise ValueError(f"source artifact member identity changed: {relative / name}")
                if len(raw) != expected_size or _sha(raw) != expected_sha256:
                    raise ValueError(f"source artifact member identity changed: {relative / name}")
                result[name] = raw
            finally:
                os.close(member_fd)

        names_after = set(os.listdir(directory_fd))
        directory_after = os.fstat(directory_fd)
        directory_identity_before = (
            directory_before.st_dev,
            directory_before.st_ino,
            directory_before.st_mtime_ns,
            directory_before.st_ctime_ns,
        )
        directory_identity_after = (
            directory_after.st_dev,
            directory_after.st_ino,
            directory_after.st_mtime_ns,
            directory_after.st_ctime_ns,
        )
        if (
            names_after != names_before
            or names_after != set(expected)
            or directory_identity_after != directory_identity_before
        ):
            raise ValueError(f"source artifact snapshot changed: {relative.as_posix()}")

        for ancestor_fd, name, child_fd, identity_before in anchored_components:
            try:
                link_after = os.stat(
                    name,
                    dir_fd=ancestor_fd,
                    follow_symlinks=False,
                )
            except OSError as error:
                raise ValueError(
                    f"source artifact ancestor snapshot changed: {relative.as_posix()}"
                ) from error
            child_after = os.fstat(child_fd)
            identity_after = (
                child_after.st_dev,
                child_after.st_ino,
                child_after.st_mtime_ns,
                child_after.st_ctime_ns,
            )
            if (
                not stat.S_ISDIR(link_after.st_mode)
                or (link_after.st_dev, link_after.st_ino)
                != identity_before[:2]
                or identity_after != identity_before
            ):
                raise ValueError(
                    f"source artifact ancestor snapshot changed: {relative.as_posix()}"
                )

        root_after = os.fstat(root_fd)
        try:
            root_link_after = os.stat(root, follow_symlinks=False)
        except OSError as error:
            raise ValueError("repository root snapshot changed") from error
        if (
            (root_after.st_dev, root_after.st_ino)
            != (root_before.st_dev, root_before.st_ino)
            or (root_link_after.st_dev, root_link_after.st_ino)
            != (root_before.st_dev, root_before.st_ino)
        ):
            raise ValueError("repository root snapshot changed")
        return result
    finally:
        for descriptor in reversed(open_directories):
            os.close(descriptor)


def _decode_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} JSON is invalid") from error
    if not isinstance(value, dict) or _canonical_json(value) != raw:
        raise ValueError(f"{label} JSON is not canonical")
    return value


def _validate_fixed_constants() -> None:
    ranges = _lists(RANGE_VECTOR)
    boundaries = _lists(BOUNDARY_VECTOR)
    claims = _lists(CLAIM_DENOMINATOR_VECTOR)
    sources = _lists(SOURCE_FILE_VECTOR)
    if len(RANGE_VECTOR) != 13 or any(end - start != 2 for start, end in RANGE_VECTOR):
        raise ValueError("gap denominator changed")
    if _vector_sha(ranges) != RANGE_VECTOR_SHA256:
        raise ValueError("range vector hash changed")
    if _vector_sha(boundaries) != BOUNDARY_VECTOR_SHA256:
        raise ValueError("boundary vector hash changed")
    if _vector_sha(claims) != CLAIM_DENOMINATOR_SHA256:
        raise ValueError("claim denominator hash changed")
    if _vector_sha(sources) != SOURCE_FILE_VECTOR_SHA256:
        raise ValueError("source file vector hash changed")
    if set(NON_CLAIMS) != set(NON_CLAIM_KEYS) or any(NON_CLAIMS.values()):
        raise ValueError("non-claim contract changed")


def _validate_manifest(
    manifest: dict[str, Any],
    *,
    schema: str,
    payload_name: str,
    payload_sha256: str,
    payload_size: int,
    binary_name: str,
    binary_sha256: str,
    binary_size: int,
    verifier_path: str,
    verifier_sha256: str,
    expected_keys: frozenset[str],
    verification_sha256: str,
    manifest_semantic_sha256: str,
    label: str,
) -> None:
    verification = manifest.get("verification")
    implementation = manifest.get("implementation")
    if (
        set(manifest) != expected_keys
        or manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != schema
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("files")
        != {
            binary_name: {"sha256": binary_sha256, "size": binary_size},
            payload_name: {"sha256": payload_sha256, "size": payload_size},
        }
        or not isinstance(implementation, dict)
        or implementation.get("verifier")
        != {"path": verifier_path, "sha256": verifier_sha256}
        or not isinstance(verification, dict)
        or verification.get("exit_code") != 0
        or verification.get("verifier_sha256") != verifier_sha256
        or manifest.get("verifier") != verification
        or _semantic_sha(verification) != verification_sha256
        or _semantic_sha(manifest) != manifest_semantic_sha256
    ):
        raise ValueError(f"{label} accepted receipt changed")


def _validate_bounded_manifest(
    manifest: dict[str, Any],
    *,
    schema: str,
    contract_sha256: str,
    payload_name: str,
    payload_sha256: str,
    payload_size: int,
    binary_name: str,
    binary_sha256: str,
    binary_size: int,
    verifier_path: str,
    verifier_sha256: str,
    source_candidate_artifact: str,
    source_manifest_sha256: str,
    label: str,
) -> None:
    expected = {
        "acceptance": {
            "kind": "independent-candidate-acceptance",
            "output_artifact": f"artifacts/{schema}",
            "source_candidate_artifact": source_candidate_artifact,
            "source_candidate_identity": {
                "artifact_status": "candidate",
                "bundle_sha256": binary_sha256,
                "manifest_sha256": source_manifest_sha256,
                "payload_sha256": payload_sha256,
            },
        },
        "artifact_schema": schema,
        "artifact_status": "accepted",
        "contract_sha256": contract_sha256,
        "files": {
            binary_name: {"sha256": binary_sha256, "size": binary_size},
            payload_name: {"sha256": payload_sha256, "size": payload_size},
        },
        "schema": "git-artifact-promotion-v1",
        "verification": {
            "bundle_sha256": binary_sha256,
            "contract_ok": True,
            "payload_sha256": payload_sha256,
            "schema": f"{schema.removesuffix('-v1')}-verification-v1",
            "status": "verified",
        },
        "verifier": {"path": verifier_path, "sha256": verifier_sha256},
    }
    if manifest != expected:
        raise ValueError(f"{label} accepted receipt changed")


def _validate_bounded_payload(
    payload: dict[str, Any],
    binary: bytes,
    rom: bytes,
    *,
    schema: str,
    label: str,
) -> None:
    contract = BOUNDED_CONTRACTS[schema]
    if payload.get("schema") != schema:
        raise ValueError(f"{label} payload schema changed")
    if payload.get("rom") != {
        "path": ROM_PATH.as_posix(),
        "sha256": SOURCE_ROM_SHA256,
        "size": ROM_SIZE,
    }:
        raise ValueError(f"{label} payload ROM receipt changed")

    promotion = payload.get("promotion")
    ranges = promotion.get("ranges") if isinstance(promotion, dict) else None
    if not isinstance(ranges, list):
        raise ValueError(f"{label} promotion range denominator changed")
    if (
        promotion.get("claim_count") != contract["claim_count"]
        or len(ranges) != contract["claim_count"]
        or promotion.get("code_bytes") != contract["code_bytes"]
        or promotion.get("literal_bytes") != contract["literal_bytes"]
        or promotion.get("total_bytes") != contract["total_bytes"]
        or promotion.get("range_vector_sha256")
        != contract["range_vector_sha256"]
        or promotion.get("packed_bytes_sha256")
        != contract["packed_bytes_sha256"]
        or payload.get("promotion_ranges") != ranges
        or _semantic_sha(ranges) != contract["promotion_rows_sha256"]
        or _vector_sha([row.get("range") for row in ranges if isinstance(row, dict)])
        != contract["range_vector_sha256"]
    ):
        raise ValueError(f"{label} promotion contract changed")
    packed = bytearray()
    previous_end = -1
    kind_bytes = {contract["code_kind"]: 0, contract["literal_kind"]: 0}
    for row in ranges:
        if not isinstance(row, dict) or set(row) != {"bytes", "kind", "range", "sha256"}:
            raise ValueError(f"{label} promotion row changed")
        start, end = row.get("range", [None, None])
        if not isinstance(start, int) or not isinstance(end, int) or start < previous_end:
            raise ValueError(f"{label} promotion order changed")
        raw = _slice(rom, start, end, f"{label} promotion")
        if row.get("bytes") != end - start or row.get("sha256") != _sha(raw):
            raise ValueError(f"{label} promotion identity changed")
        if row.get("kind") not in {contract["code_kind"], contract["literal_kind"]}:
            raise ValueError(f"{label} promotion kind changed")
        kind_bytes[row["kind"]] += len(raw)
        packed.extend(raw)
        previous_end = end
    if bytes(packed) != binary or _sha(packed) != contract["packed_bytes_sha256"]:
        raise ValueError(f"{label} promotion binary changed")
    if (
        kind_bytes[contract["code_kind"]] != contract["code_bytes"]
        or kind_bytes[contract["literal_kind"]] != contract["literal_bytes"]
    ):
        raise ValueError(f"{label} promotion byte totals changed")

    expected_excluded = [
        {
            "promoted": False,
            "range": list(range_pair),
            "raw_hex": "0000",
            "semantic_class": "unknown",
            "sha256": ZERO_PAIR_SHA256,
        }
        for range_pair in contract["excluded"]
    ]
    if payload.get("excluded_ranges") != expected_excluded:
        raise ValueError(f"{label} excluded gap contract changed")

    literals = payload.get("literal_projection")
    if (
        not isinstance(literals, dict)
        or literals.get("ranges") != _lists(contract["literal_ranges"])
        or literals.get("binding_count") != contract["literal_binding_count"]
        or literals.get("word_count") != contract["literal_binding_count"]
        or literals.get("bytes") != contract["literal_bytes"]
        or literals.get("range_vector_sha256")
        != contract["literal_range_vector_sha256"]
        or literals.get("packed_sha256") != contract["literal_packed_sha256"]
        or not isinstance(literals.get("bindings"), list)
        or len(literals["bindings"]) != contract["literal_binding_count"]
        or _semantic_sha(literals.get("bindings"))
        != contract["literal_bindings_sha256"]
        or _vector_sha(literals.get("ranges"))
        != contract["literal_range_vector_sha256"]
    ):
        raise ValueError(f"{label} literal projection changed")

    literal_packed = b"".join(
        _slice(rom, start, end, f"{label} literal range")
        for start, end in contract["literal_ranges"]
    )
    if _sha(literal_packed) != contract["literal_packed_sha256"]:
        raise ValueError(f"{label} literal packed identity changed")
    literal_offsets = {
        offset
        for start, end in contract["literal_ranges"]
        for offset in range(start, end, 4)
    }
    decoded_literal_offsets: list[int] = []
    for binding in literals["bindings"]:
        if schema == HELPER_SCHEMA:
            if not isinstance(binding, dict) or set(binding) != {
                "consumer_offset", "load_raw_hex", "range", "value"
            }:
                raise ValueError(f"{label} literal binding structure changed")
            consumer = binding["consumer_offset"]
            literal_range = binding["range"]
            if not isinstance(literal_range, list) or len(literal_range) != 2:
                raise ValueError(f"{label} literal binding range changed")
            literal, literal_end = literal_range
            value = binding["value"]
            load_hex = binding["load_raw_hex"]
            literal_hex = _slice(rom, literal, literal_end, f"{label} literal").hex()
        else:
            if not isinstance(binding, list) or len(binding) != 5:
                raise ValueError(f"{label} literal binding structure changed")
            consumer, literal, value, load_hex, literal_hex = binding
            literal_end = literal + 4
        load_raw = _slice(rom, consumer, consumer + 2, f"{label} literal load")
        halfword = int.from_bytes(load_raw, "little")
        decoded_literal = ((consumer + 4) & ~3) + (halfword & 0xFF) * 4
        literal_raw = _slice(rom, literal, literal_end, f"{label} literal")
        if (
            halfword & 0xF800 != 0x4800
            or load_raw.hex() != load_hex
            or decoded_literal != literal
            or literal_end - literal != 4
            or literal_raw.hex() != literal_hex
            or int.from_bytes(literal_raw, "little") != value
        ):
            raise ValueError(f"{label} literal binding semantics changed")
        decoded_literal_offsets.append(literal)
    if (
        len(set(decoded_literal_offsets)) != contract["literal_binding_count"]
        or set(decoded_literal_offsets) != literal_offsets
    ):
        raise ValueError(f"{label} literal binding denominator changed")
    for literal_range in contract["literal_ranges"]:
        literal_row = _find_by_range(
            ranges, literal_range, f"{label} literal promotion"
        )
        if literal_row.get("kind") != contract["literal_kind"]:
            raise ValueError(f"{label} literal promotion kind changed")

    instructions = payload.get("cfg", {}).get("instructions")
    if not isinstance(instructions, list):
        raise ValueError(f"{label} instruction denominator changed")
    artifact_boundaries = [row for row in BOUNDARY_VECTOR if row[1] == schema]
    for boundary in artifact_boundaries:
        terminal_range = boundary[5]
        expected = {
            "mnemonic": boundary[7],
            "offset": terminal_range[0],
            "op_str": boundary[8],
            "raw_hex": boundary[9],
            "size": 2,
            "successors": (
                []
                if boundary[6] == "return"
                else [{"kind": "branch", "target_offset": boundary[10]}]
            ),
        }
        matches = [row for row in instructions if isinstance(row, dict) and row.get("offset") == terminal_range[0]]
        if matches != [expected]:
            raise ValueError(f"{label} terminal instruction changed")
        left = _find_by_range(ranges, boundary[2], f"{label} left promotion")
        right = _find_by_range(ranges, boundary[13], f"{label} right promotion")
        if left.get("kind") != contract["code_kind"]:
            raise ValueError(f"{label} left promotion kind changed")
        if right.get("kind") != contract["literal_kind"]:
            raise ValueError(f"{label} right literal promotion kind changed")

    scope = payload.get("scope")
    if not isinstance(scope, dict) or any(scope.get(key) is not False for key in contract["scope_false"]):
        raise ValueError(f"{label} source non-claim contract changed")


def _find_by_range(rows: list[Any], expected: tuple[int, int], label: str) -> dict[str, Any]:
    matches = [row for row in rows if isinstance(row, dict) and row.get("range") == list(expected)]
    if len(matches) != 1:
        raise ValueError(f"{label} range denominator changed")
    return matches[0]


def _validate_scheduler_payload(payload: dict[str, Any]) -> None:
    if _semantic_sha(payload) != SCHEDULER_PAYLOAD_SEMANTIC_SHA256:
        raise ValueError("scheduler payload semantic receipt changed")
    if payload.get("schema") != SCHEDULER_SCHEMA:
        raise ValueError("scheduler payload schema changed")
    if payload.get("code_ranges") != _lists(SCHEDULER_CODE_RANGES):
        raise ValueError("scheduler code range denominator changed")
    if payload.get("literal_ranges") != _lists(SCHEDULER_LITERAL_RANGES):
        raise ValueError("scheduler literal range denominator changed")
    if payload.get("owned_provenance_ranges") != _lists(
        SCHEDULER_OWNED_PROVENANCE_RANGES
    ):
        raise ValueError("scheduler owned provenance range denominator changed")
    if payload.get("unclassified_unknown_ranges") != _lists(
        SCHEDULER_UNKNOWN_RANGES
    ):
        raise ValueError("scheduler unclassified range denominator changed")
    promotion = payload.get("promotion")
    if (
        not isinstance(promotion, dict)
        or promotion.get("unclassified_unknown_ranges")
        != _lists(SCHEDULER_UNKNOWN_RANGES)
        or promotion.get("unclassified_unknown_bytes") != 6
    ):
        raise ValueError("scheduler promotion gap denominator changed")
    scope = payload.get("scope")
    if (
        not isinstance(scope, dict)
        or scope.get("unclassified_ranges_are_padding_or_free") is not False
        or scope.get("existing_owned_provenance_not_reclaimed") is not True
    ):
        raise ValueError("scheduler source non-claim contract changed")

    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("scheduler block denominator changed")
    expected_blocks = {
        (0x061D52, 0x061D62): {
            "conditional": False,
            "file_offset": 0x061D60,
            "flow_kind": "return",
            "mnemonic": "bx",
            "op_str": "r0",
            "raw_hex": "0047",
            "size": 2,
        },
        (0x061D78, 0x061D7A): {
            "conditional": False,
            "file_offset": 0x061D78,
            "flow_kind": "unconditional_branch",
            "mnemonic": "b",
            "op_str": "#0x8061d72",
            "raw_hex": "fbe7",
            "size": 2,
        },
    }
    for range_pair, terminal in expected_blocks.items():
        block = _find_by_range(blocks, range_pair, "scheduler terminal block")
        if block.get("terminator") != terminal:
            raise ValueError("scheduler terminal block contract changed")

    claims = payload.get("coverage_claims")
    provenance = payload.get("existing_owned_provenance")
    if not isinstance(claims, list) or not isinstance(provenance, list):
        raise ValueError("scheduler owner denominator changed")
    if _semantic_sha(claims) != SCHEDULER_CLAIMS_SHA256:
        raise ValueError("scheduler coverage claim semantics changed")
    if _semantic_sha(provenance) != SCHEDULER_PROVENANCE_SHA256:
        raise ValueError("scheduler owned provenance semantics changed")
    expected_claims = {
        (0x061D10, 0x061D62): "scheduler-code-02-061d10",
        (0x061D70, 0x061D7A): "scheduler-code-03-061d70",
        (0x061D64, 0x061D70): "scheduler-literal-01-061d64",
        (0x061DEC, 0x061E00): "scheduler-literal-02-061dec",
    }
    for range_pair, claim_id in expected_claims.items():
        row = _find_by_range(claims, range_pair, "scheduler coverage claim")
        if row.get("id") != claim_id or row.get("sha256") not in {
            OWNER_SHA256.get(range_pair),
            RIGHT_SHA256.get(range_pair),
        }:
            raise ValueError("scheduler coverage claim identity changed")
    owned = _find_by_range(
        provenance, (0x061D7C, 0x061DEA), "scheduler owned function"
    )
    if (
        owned.get("claim_id") != "cfg-thumb-0000-061d7c"
        or owned.get("primary_class") != "armv4t_cfg_reachable_thumb_code"
        or owned.get("sha256") != OWNER_SHA256[(0x061D7C, 0x061DEA)]
    ):
        raise ValueError("scheduler owned function identity changed")


def _validate_psg_payload(payload: dict[str, Any]) -> None:
    if _semantic_sha(payload) != PSG_PAYLOAD_SEMANTIC_SHA256:
        raise ValueError("PSG payload semantic receipt changed")
    if payload.get("schema") != PSG_SCHEMA:
        raise ValueError("PSG payload schema changed")
    consumer = payload.get("consumer")
    if (
        not isinstance(consumer, dict)
        or consumer.get("code_ranges") != _lists(PSG_CODE_RANGES)
        or consumer.get("unclassified_unknown_ranges") != _lists(PSG_UNKNOWN_RANGES)
        or [0x09B4BE, 0x09B4C6] not in consumer.get("block_ranges", [])
        or consumer.get("frontier_count") != 0
    ):
        raise ValueError("PSG consumer range denominator changed")
    promotion = payload.get("promotion")
    semantic_ranges = (
        promotion.get("semantic_ranges") if isinstance(promotion, dict) else None
    )
    if not isinstance(semantic_ranges, list):
        raise ValueError("PSG semantic range denominator changed")
    if _semantic_sha(semantic_ranges) != PSG_SEMANTIC_RANGES_SHA256:
        raise ValueError("PSG semantic range contract changed")
    code = _find_by_range(
        semantic_ranges, (0x09B494, 0x09B4C6), "PSG left code owner"
    )
    literal = _find_by_range(
        semantic_ranges, (0x09B4C8, 0x09B4CC), "PSG right literal owner"
    )
    if (
        code.get("id") != "psg-frequency-code-a-09b494"
        or code.get("sha256") != OWNER_SHA256[(0x09B494, 0x09B4C6)]
        or literal.get("id") != "psg-frequency-noise-literal-09b4c8"
        or literal.get("sha256") != RIGHT_SHA256[(0x09B4C8, 0x09B4CC)]
    ):
        raise ValueError("PSG owner identity changed")
    bindings = payload.get("literal_bindings")
    if (
        not isinstance(bindings, list)
        or _semantic_sha(bindings) != PSG_LITERAL_BINDINGS_SHA256
        or not any(
        isinstance(row, dict)
        and row.get("literal_range") == [0x09B4C8, 0x09B4CC]
        and row.get("load_file_offset") == 0x09B4BE
        and row.get("load_raw_hex") == "0248"
        for row in bindings
        )
    ):
        raise ValueError("PSG consumed literal binding changed")
    scope = payload.get("scope")
    if (
        not isinstance(scope, dict)
        or scope.get("target_consumer_cfg_closed") is not True
        or scope.get("natural_runtime_reachability_complete") is not False
        or scope.get("allocatable_free_space_proven") is not False
    ):
        raise ValueError("PSG source non-claim contract changed")


def _decode_unconditional_branch(raw: bytes, offset: int) -> int:
    if len(raw) != 2:
        raise ValueError("branch terminal size changed")
    halfword = int.from_bytes(raw, "little")
    if halfword & 0xF800 != 0xE000:
        raise ValueError("branch terminal opcode changed")
    immediate = halfword & 0x07FF
    if immediate & 0x0400:
        immediate -= 0x0800
    return offset + 4 + immediate * 2


def _decode_bx_register(raw: bytes) -> int:
    if len(raw) != 2:
        raise ValueError("return terminal size changed")
    halfword = int.from_bytes(raw, "little")
    if halfword & 0xFF87 != 0x4700:
        raise ValueError("return terminal opcode changed")
    return (halfword >> 3) & 0xF


def _validate_raw_gap_boundaries(rom: bytes) -> None:
    for boundary in BOUNDARY_VECTOR:
        boundary_id = boundary[0]
        terminal_start, terminal_end = boundary[5]
        flow_kind = boundary[6]
        operand = boundary[8]
        terminal_hex = boundary[9]
        target_offset = boundary[10]
        gap_start, gap_end = boundary[11]
        terminal_raw = _slice(rom, terminal_start, terminal_end, "terminal")
        if terminal_raw.hex() != terminal_hex:
            raise ValueError(f"terminal boundary bytes changed: {boundary_id}")
        if flow_kind == "return":
            expected_register = {"r0": 0, "lr": 14}.get(operand)
            if _decode_bx_register(terminal_raw) != expected_register:
                raise ValueError(f"return terminal register changed: {boundary_id}")
        elif _decode_unconditional_branch(terminal_raw, terminal_start) != target_offset:
            raise ValueError(f"branch terminal target changed: {boundary_id}")
        gap_raw = _slice(rom, gap_start, gap_end, "alignment gap")
        if gap_raw != b"\x00\x00" or _sha(gap_raw) != ZERO_PAIR_SHA256:
            raise ValueError(f"alignment gap is not the exact zero pair: {boundary_id}")


def _verify_inputs(
    rom: bytes,
    *,
    scheduler_manifest: dict[str, Any],
    scheduler_payload: dict[str, Any],
    scheduler_binary: bytes,
    psg_manifest: dict[str, Any],
    psg_payload: dict[str, Any],
    psg_binary: bytes,
    helper_manifest: dict[str, Any],
    helper_payload: dict[str, Any],
    helper_binary: bytes,
    cgbsound_manifest: dict[str, Any],
    cgbsound_payload: dict[str, Any],
    cgbsound_binary: bytes,
) -> dict[str, Any]:
    _validate_fixed_constants()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("ROM identity changed")
    _validate_raw_gap_boundaries(rom)
    if _sha(_canonical_json(scheduler_manifest)) != SCHEDULER_MANIFEST_SHA256:
        raise ValueError("scheduler manifest identity changed")
    if _sha(_canonical_json(scheduler_payload)) != SCHEDULER_PAYLOAD_SHA256:
        raise ValueError("scheduler payload identity changed")
    if len(scheduler_binary) != SCHEDULER_BINARY_SIZE or _sha(
        scheduler_binary
    ) != SCHEDULER_BINARY_SHA256:
        raise ValueError("scheduler binary identity changed")
    if _sha(_canonical_json(psg_manifest)) != PSG_MANIFEST_SHA256:
        raise ValueError("PSG manifest identity changed")
    if _sha(_canonical_json(psg_payload)) != PSG_PAYLOAD_SHA256:
        raise ValueError("PSG payload identity changed")
    if len(psg_binary) != PSG_BINARY_SIZE or _sha(psg_binary) != PSG_BINARY_SHA256:
        raise ValueError("PSG binary identity changed")
    if _sha(_canonical_json(helper_payload)) != HELPER_PAYLOAD_SHA256:
        raise ValueError("CGB helper payload identity changed")
    if len(helper_binary) != HELPER_BINARY_SIZE or _sha(helper_binary) != HELPER_BINARY_SHA256:
        raise ValueError("CGB helper binary identity changed")
    _validate_bounded_payload(
        helper_payload,
        helper_binary,
        rom,
        schema=HELPER_SCHEMA,
        label="CGB helper",
    )
    if _sha(_canonical_json(helper_manifest)) != HELPER_MANIFEST_SHA256:
        raise ValueError("CGB helper manifest identity changed")
    if _sha(_canonical_json(cgbsound_payload)) != CGBSOUND_PAYLOAD_SHA256:
        raise ValueError("CgbSound payload identity changed")
    if len(cgbsound_binary) != CGBSOUND_BINARY_SIZE or _sha(cgbsound_binary) != CGBSOUND_BINARY_SHA256:
        raise ValueError("CgbSound binary identity changed")
    _validate_bounded_payload(
        cgbsound_payload,
        cgbsound_binary,
        rom,
        schema=CGBSOUND_SCHEMA,
        label="CgbSound",
    )
    if _sha(_canonical_json(cgbsound_manifest)) != CGBSOUND_MANIFEST_SHA256:
        raise ValueError("CgbSound manifest identity changed")

    _validate_manifest(
        scheduler_manifest,
        schema=SCHEDULER_SCHEMA,
        payload_name=SCHEDULER_PAYLOAD.name,
        payload_sha256=SCHEDULER_PAYLOAD_SHA256,
        payload_size=SCHEDULER_PAYLOAD_SIZE,
        binary_name=SCHEDULER_BINARY.name,
        binary_sha256=SCHEDULER_BINARY_SHA256,
        binary_size=SCHEDULER_BINARY_SIZE,
        verifier_path=SCHEDULER_VERIFIER_PATH,
        verifier_sha256=SCHEDULER_VERIFIER_SHA256,
        expected_keys=SCHEDULER_MANIFEST_KEYS,
        verification_sha256=SCHEDULER_VERIFICATION_SHA256,
        manifest_semantic_sha256=SCHEDULER_MANIFEST_SEMANTIC_SHA256,
        label="scheduler",
    )
    _validate_manifest(
        psg_manifest,
        schema=PSG_SCHEMA,
        payload_name=PSG_PAYLOAD.name,
        payload_sha256=PSG_PAYLOAD_SHA256,
        payload_size=PSG_PAYLOAD_SIZE,
        binary_name=PSG_BINARY.name,
        binary_sha256=PSG_BINARY_SHA256,
        binary_size=PSG_BINARY_SIZE,
        verifier_path=PSG_VERIFIER_PATH,
        verifier_sha256=PSG_VERIFIER_SHA256,
        expected_keys=PSG_MANIFEST_KEYS,
        verification_sha256=PSG_VERIFICATION_SHA256,
        manifest_semantic_sha256=PSG_MANIFEST_SEMANTIC_SHA256,
        label="PSG",
    )
    _validate_bounded_manifest(
        helper_manifest,
        schema=HELPER_SCHEMA,
        contract_sha256=HELPER_CONTRACT_SHA256,
        payload_name=HELPER_PAYLOAD.name,
        payload_sha256=HELPER_PAYLOAD_SHA256,
        payload_size=HELPER_PAYLOAD_SIZE,
        binary_name=HELPER_BINARY.name,
        binary_sha256=HELPER_BINARY_SHA256,
        binary_size=HELPER_BINARY_SIZE,
        verifier_path=HELPER_VERIFIER_PATH,
        verifier_sha256=HELPER_VERIFIER_SHA256,
        source_candidate_artifact="build/experiments/active/cgb-helper-bounded-cfg-20260829/candidate-r2",
        source_manifest_sha256="cad4873e706f5425e75ee080af43096420be41a85d0f0cdf863496f0f792b3ad",
        label="CGB helper",
    )
    _validate_bounded_manifest(
        cgbsound_manifest,
        schema=CGBSOUND_SCHEMA,
        contract_sha256=CGBSOUND_CONTRACT_SHA256,
        payload_name=CGBSOUND_PAYLOAD.name,
        payload_sha256=CGBSOUND_PAYLOAD_SHA256,
        payload_size=CGBSOUND_PAYLOAD_SIZE,
        binary_name=CGBSOUND_BINARY.name,
        binary_sha256=CGBSOUND_BINARY_SHA256,
        binary_size=CGBSOUND_BINARY_SIZE,
        verifier_path=CGBSOUND_VERIFIER_PATH,
        verifier_sha256=CGBSOUND_VERIFIER_SHA256,
        source_candidate_artifact="build/experiments/active/cgbsound-bounded-cfg-20260829/candidate",
        source_manifest_sha256="15e52e11fd9be4fa5ae7f485c65e8775b8e9c2bf01c05cfbef178e28e0ea65d4",
        label="CgbSound",
    )
    _validate_scheduler_payload(scheduler_payload)
    _validate_psg_payload(psg_payload)

    gaps: list[dict[str, Any]] = []
    packed = bytearray()
    for source in BOUNDARY_VECTOR:
        (
            boundary_id,
            source_schema,
            left_owner_range,
            left_owner_kind,
            left_source_id,
            terminal_range,
            flow_kind,
            mnemonic,
            operand,
            terminal_hex,
            target_offset,
            gap_range,
            right_kind,
            right_range,
            right_source_id,
        ) = source
        left_start, left_end = left_owner_range
        terminal_start, terminal_end = terminal_range
        gap_start, gap_end = gap_range
        right_start, right_end = right_range
        if (
            terminal_end != left_end
            or gap_start != left_end
            or gap_end != ((left_end + 3) & ~3)
            or right_start != gap_end
            or right_start & 3
        ):
            raise ValueError(f"boundary align4 equation changed: {boundary_id}")
        owner_raw = _slice(rom, left_start, left_end, "left owner")
        if _sha(owner_raw) != OWNER_SHA256[left_owner_range]:
            raise ValueError(f"left boundary owner identity changed: {boundary_id}")
        terminal_raw = _slice(rom, terminal_start, terminal_end, "terminal")
        if terminal_raw.hex() != terminal_hex:
            raise ValueError(f"terminal boundary bytes changed: {boundary_id}")
        if flow_kind == "return":
            register = _decode_bx_register(terminal_raw)
            expected_register = {"r0": 0, "lr": 14}.get(operand)
            if register != expected_register:
                raise ValueError(f"return terminal register changed: {boundary_id}")
            decoded_target = None
        else:
            decoded_target = _decode_unconditional_branch(
                terminal_raw, terminal_start
            )
            if decoded_target != target_offset:
                raise ValueError(f"branch terminal target changed: {boundary_id}")
        if boundary_id == "scheduler-return-to-literal-061dea" and _slice(
            rom, 0x061DE4, 0x061DEA, "scheduler owned epilogue"
        ).hex() != "f0bc01bc0047":
            raise ValueError("scheduler owned return epilogue changed")
        gap_raw = _slice(rom, gap_start, gap_end, "alignment gap")
        if gap_raw != b"\x00\x00" or _sha(gap_raw) != ZERO_PAIR_SHA256:
            raise ValueError(f"alignment gap is not the exact zero pair: {boundary_id}")
        right_raw = _slice(rom, right_start, right_end, "right structure")
        if _sha(right_raw) != RIGHT_SHA256[right_range]:
            raise ValueError(f"right boundary structure identity changed: {boundary_id}")
        packed.extend(gap_raw)
        gaps.append(
            {
                "id": boundary_id,
                "source_artifact_schema": source_schema,
                "left_owner_kind": left_owner_kind,
                "left_source_id": left_source_id,
                "left_owner_range": list(left_owner_range),
                "left_owner_gba_range": [_gba(left_start), _gba(left_end)],
                "left_owner_sha256": _sha(owner_raw),
                "left_terminal": {
                    "range": list(terminal_range),
                    "gba_range": [_gba(terminal_start), _gba(terminal_end)],
                    "raw_hex": terminal_raw.hex(),
                    "flow_kind": flow_kind,
                    "mnemonic": mnemonic,
                    "operand": operand,
                    "target_offset": decoded_target,
                    "target_gba_address": (
                        _gba(decoded_target) if decoded_target is not None else None
                    ),
                },
                "gap_range": list(gap_range),
                "gap_gba_range": [_gba(gap_start), _gba(gap_end)],
                "gap_size": len(gap_raw),
                "gap_raw_hex": gap_raw.hex(),
                "gap_sha256": _sha(gap_raw),
                "gap_start_equals_left_owner_end": gap_start == left_end,
                "gap_end_equals_align4_left_end": gap_end
                == ((left_end + 3) & ~3),
                "right_kind": right_kind,
                "right_range": list(right_range),
                "right_gba_range": [_gba(right_start), _gba(right_end)],
                "right_source_id": right_source_id,
                "right_sha256": _sha(right_raw),
                "right_start_equals_gap_end": right_start == gap_end,
                "primary_class": PRIMARY_CLASS,
                "claim_kind": CLAIM_KIND,
                "promotion_batch": PROMOTION_BATCH,
            }
        )

    if len(packed) != 26 or packed.count(0) != 26 or _sha(packed) != PACKED_BYTES_SHA256:
        raise ValueError("packed alignment byte denominator changed")
    right_kind_counts = dict(
        sorted(Counter(row["right_kind"] for row in gaps).items())
    )
    source_artifacts = {
        SCHEDULER_SCHEMA: {
            "artifact_status": "accepted",
            "manifest_path": SCHEDULER_MANIFEST.as_posix(),
            "manifest_sha256": SCHEDULER_MANIFEST_SHA256,
            "payload_path": SCHEDULER_PAYLOAD.as_posix(),
            "payload_sha256": SCHEDULER_PAYLOAD_SHA256,
            "binary_path": SCHEDULER_BINARY.as_posix(),
            "binary_sha256": SCHEDULER_BINARY_SHA256,
            "legacy_verifier_path": SCHEDULER_VERIFIER_PATH,
            "legacy_verifier_sha256": SCHEDULER_VERIFIER_SHA256,
            "files": {
                path: {"sha256": sha256, "size": size}
                for path, sha256, size in SOURCE_FILE_VECTOR[:3]
            },
        },
        PSG_SCHEMA: {
            "artifact_status": "accepted",
            "manifest_path": PSG_MANIFEST.as_posix(),
            "manifest_sha256": PSG_MANIFEST_SHA256,
            "payload_path": PSG_PAYLOAD.as_posix(),
            "payload_sha256": PSG_PAYLOAD_SHA256,
            "binary_path": PSG_BINARY.as_posix(),
            "binary_sha256": PSG_BINARY_SHA256,
            "legacy_verifier_path": PSG_VERIFIER_PATH,
            "legacy_verifier_sha256": PSG_VERIFIER_SHA256,
            "files": {
                path: {"sha256": sha256, "size": size}
                for path, sha256, size in SOURCE_FILE_VECTOR[3:6]
            },
        },
        HELPER_SCHEMA: {
            "artifact_status": "accepted",
            "contract_sha256": HELPER_CONTRACT_SHA256,
            "manifest_path": HELPER_MANIFEST.as_posix(),
            "manifest_sha256": HELPER_MANIFEST_SHA256,
            "payload_path": HELPER_PAYLOAD.as_posix(),
            "payload_sha256": HELPER_PAYLOAD_SHA256,
            "binary_path": HELPER_BINARY.as_posix(),
            "binary_sha256": HELPER_BINARY_SHA256,
            "legacy_verifier_path": HELPER_VERIFIER_PATH,
            "legacy_verifier_sha256": HELPER_VERIFIER_SHA256,
            "source_candidate_artifact": "build/experiments/active/cgb-helper-bounded-cfg-20260829/candidate-r2",
            "source_candidate_identity": {
                "artifact_status": "candidate",
                "bundle_sha256": HELPER_BINARY_SHA256,
                "manifest_sha256": "cad4873e706f5425e75ee080af43096420be41a85d0f0cdf863496f0f792b3ad",
                "payload_sha256": HELPER_PAYLOAD_SHA256,
            },
            "files": {
                path: {"sha256": sha256, "size": size}
                for path, sha256, size in SOURCE_FILE_VECTOR[6:9]
            },
        },
        CGBSOUND_SCHEMA: {
            "artifact_status": "accepted",
            "contract_sha256": CGBSOUND_CONTRACT_SHA256,
            "manifest_path": CGBSOUND_MANIFEST.as_posix(),
            "manifest_sha256": CGBSOUND_MANIFEST_SHA256,
            "payload_path": CGBSOUND_PAYLOAD.as_posix(),
            "payload_sha256": CGBSOUND_PAYLOAD_SHA256,
            "binary_path": CGBSOUND_BINARY.as_posix(),
            "binary_sha256": CGBSOUND_BINARY_SHA256,
            "legacy_verifier_path": CGBSOUND_VERIFIER_PATH,
            "legacy_verifier_sha256": CGBSOUND_VERIFIER_SHA256,
            "source_candidate_artifact": "build/experiments/active/cgbsound-bounded-cfg-20260829/candidate",
            "source_candidate_identity": {
                "artifact_status": "candidate",
                "bundle_sha256": CGBSOUND_BINARY_SHA256,
                "manifest_sha256": "15e52e11fd9be4fa5ae7f485c65e8775b8e9c2bf01c05cfbef178e28e0ea65d4",
                "payload_sha256": CGBSOUND_PAYLOAD_SHA256,
            },
            "files": {
                path: {"sha256": sha256, "size": size}
                for path, sha256, size in SOURCE_FILE_VECTOR[9:12]
            },
        },
    }
    report: dict[str, Any] = {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        "errors": [],
        "rom_sha256": _sha(rom),
        "promotion_batch": PROMOTION_BATCH,
        "primary_class": PRIMARY_CLASS,
        "claim_kind": CLAIM_KIND,
        "gap_count": len(gaps),
        "byte_count": len(packed),
        "zero_byte_count": packed.count(0),
        "ranges": _lists(RANGE_VECTOR),
        "range_vector_sha256": _vector_sha(_lists(RANGE_VECTOR)),
        "boundary_vector_sha256": _vector_sha(_lists(BOUNDARY_VECTOR)),
        "claim_denominator_sha256": _vector_sha(
            _lists(CLAIM_DENOMINATOR_VECTOR)
        ),
        "source_file_vector_sha256": _vector_sha(_lists(SOURCE_FILE_VECTOR)),
        "source_file_receipts": [
            {"path": path, "sha256": sha256, "size": size}
            for path, sha256, size in SOURCE_FILE_VECTOR
        ],
        "packed_bytes_hex": bytes(packed).hex(),
        "packed_bytes_sha256": _sha(packed),
        "right_kind_counts": right_kind_counts,
        "source_artifact_count": len(source_artifacts),
        "all_alignment_equations_hold": all(
            row["gap_start_equals_left_owner_end"]
            and row["gap_end_equals_align4_left_end"]
            and row["right_start_equals_gap_end"]
            for row in gaps
        ),
        "all_boundaries_exact": True,
        "gaps": gaps,
        "source_artifacts": source_artifacts,
        "limitations": list(LIMITATIONS),
        "non_claims": dict(NON_CLAIMS),
    }
    report.update(NON_CLAIMS)
    return report


def _failure(error: Exception | str) -> dict[str, Any]:
    message = str(error) or "verification failed"
    report: dict[str, Any] = {
        "schema": VERIFY_SCHEMA,
        "verified": False,
        "errors": [message],
        "promotion_batch": PROMOTION_BATCH,
        "limitations": list(LIMITATIONS),
        "non_claims": dict(NON_CLAIMS),
    }
    report.update(NON_CLAIMS)
    return report


def verify_inputs(
    rom: bytes,
    *,
    scheduler_manifest: dict[str, Any],
    scheduler_payload: dict[str, Any],
    scheduler_binary: bytes,
    psg_manifest: dict[str, Any],
    psg_payload: dict[str, Any],
    psg_binary: bytes,
    helper_manifest: dict[str, Any],
    helper_payload: dict[str, Any],
    helper_binary: bytes,
    cgbsound_manifest: dict[str, Any],
    cgbsound_payload: dict[str, Any],
    cgbsound_binary: bytes,
) -> dict[str, Any]:
    """Verify already-loaded raw inputs and always return a JSON report."""

    try:
        return _verify_inputs(
            bytes(rom),
            scheduler_manifest=scheduler_manifest,
            scheduler_payload=scheduler_payload,
            scheduler_binary=bytes(scheduler_binary),
            psg_manifest=psg_manifest,
            psg_payload=psg_payload,
            psg_binary=bytes(psg_binary),
            helper_manifest=helper_manifest,
            helper_payload=helper_payload,
            helper_binary=bytes(helper_binary),
            cgbsound_manifest=cgbsound_manifest,
            cgbsound_payload=cgbsound_payload,
            cgbsound_binary=bytes(cgbsound_binary),
        )
    except (KeyError, IndexError, TypeError, ValueError, OSError) as error:
        return _failure(error)


def verify_root(root: Path | str) -> dict[str, Any]:
    """Safely load the frozen repository inputs and verify all thirteen gaps."""

    try:
        resolved = _safe_root(root)
        rom = _safe_file(resolved, ROM_PATH, ROM_SHA256, ROM_SIZE)
        scheduler = _artifact_snapshot(
            resolved,
            SCHEDULER_ARTIFACT,
            {
                SCHEDULER_MANIFEST.name: (SCHEDULER_MANIFEST_SHA256, SCHEDULER_MANIFEST_SIZE),
                SCHEDULER_PAYLOAD.name: (SCHEDULER_PAYLOAD_SHA256, SCHEDULER_PAYLOAD_SIZE),
                SCHEDULER_BINARY.name: (SCHEDULER_BINARY_SHA256, SCHEDULER_BINARY_SIZE),
            },
        )
        psg = _artifact_snapshot(
            resolved,
            PSG_ARTIFACT,
            {
                PSG_MANIFEST.name: (PSG_MANIFEST_SHA256, PSG_MANIFEST_SIZE),
                PSG_PAYLOAD.name: (PSG_PAYLOAD_SHA256, PSG_PAYLOAD_SIZE),
                PSG_BINARY.name: (PSG_BINARY_SHA256, PSG_BINARY_SIZE),
            },
        )
        helper = _artifact_snapshot(
            resolved,
            HELPER_ARTIFACT,
            {
                HELPER_MANIFEST.name: (HELPER_MANIFEST_SHA256, HELPER_MANIFEST_SIZE),
                HELPER_PAYLOAD.name: (HELPER_PAYLOAD_SHA256, HELPER_PAYLOAD_SIZE),
                HELPER_BINARY.name: (HELPER_BINARY_SHA256, HELPER_BINARY_SIZE),
            },
        )
        cgbsound = _artifact_snapshot(
            resolved,
            CGBSOUND_ARTIFACT,
            {
                CGBSOUND_MANIFEST.name: (CGBSOUND_MANIFEST_SHA256, CGBSOUND_MANIFEST_SIZE),
                CGBSOUND_PAYLOAD.name: (CGBSOUND_PAYLOAD_SHA256, CGBSOUND_PAYLOAD_SIZE),
                CGBSOUND_BINARY.name: (CGBSOUND_BINARY_SHA256, CGBSOUND_BINARY_SIZE),
            },
        )
        return verify_inputs(
            rom,
            scheduler_manifest=_decode_json(
                scheduler[SCHEDULER_MANIFEST.name], "scheduler manifest"
            ),
            scheduler_payload=_decode_json(
                scheduler[SCHEDULER_PAYLOAD.name], "scheduler payload"
            ),
            scheduler_binary=scheduler[SCHEDULER_BINARY.name],
            psg_manifest=_decode_json(psg[PSG_MANIFEST.name], "PSG manifest"),
            psg_payload=_decode_json(psg[PSG_PAYLOAD.name], "PSG payload"),
            psg_binary=psg[PSG_BINARY.name],
            helper_manifest=_decode_json(helper[HELPER_MANIFEST.name], "CGB helper manifest"),
            helper_payload=_decode_json(helper[HELPER_PAYLOAD.name], "CGB helper payload"),
            helper_binary=helper[HELPER_BINARY.name],
            cgbsound_manifest=_decode_json(cgbsound[CGBSOUND_MANIFEST.name], "CgbSound manifest"),
            cgbsound_payload=_decode_json(cgbsound[CGBSOUND_PAYLOAD.name], "CgbSound payload"),
            cgbsound_binary=cgbsound[CGBSOUND_BINARY.name],
        )
    except (KeyError, IndexError, TypeError, ValueError, OSError) as error:
        return _failure(error)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    report = verify_root(args.root)
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
