#!/usr/bin/env python3
"""Frozen public constants for the two-root CFG proven-roots v14 packet."""

from __future__ import annotations

from pathlib import Path


ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "rom-cfg-proven-roots-v14"
VERIFY_SCHEMA = "rom-cfg-proven-roots-verification-v14"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
PAYLOAD_NAME = "rom-cfg-proven-roots-v14.json"
MANIFEST_NAME = "manifest.json"
EXPERIMENT_OUTPUT_ROOT = Path(
    "build/experiments/active/cfg-proven-roots-v14-red-20260830"
)
OFFICIAL_ARTIFACT = Path("artifacts/rom-cfg-proven-roots-v14")

COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
COVERAGE_EXPECTED = {
    "path": COVERAGE_PATH.as_posix(),
    "sha256": "e8787f8e200e84b2966c6f6b8c70ea164a0f90d81348d88e5daa614ea3cb8004",
    "classified_bytes": 6_126_775,
    "unknown_bytes": 164_681,
    "claim_count": 14_558,
    "segment_count": 16_673,
    "promotion_bytes": 160,
    "known_overlap_bytes": 0,
}

UPSTREAM = {
    "v12": {
        "claim_class": "armv4t_cfg_proven_roots_v12_reachable_thumb_code",
        "manifest_path": "artifacts/rom-cfg-proven-roots-v12/manifest.json",
        "manifest_sha256": "bf88e08f4eed6b53e1debef709c2ef13fb891c11e9c172485e494eef57954677",
        "payload_path": "artifacts/rom-cfg-proven-roots-v12/rom-cfg-proven-roots-v12.json",
        "payload_sha256": "fd9df8f3d93de1df5aa7e725040f27f854d08e8203d6cada51db829ddcd9bcee",
    },
    "v13": {
        "claim_class": "armv4t_cfg_proven_roots_v13_reachable_thumb_code",
        "manifest_path": "artifacts/rom-cfg-proven-roots-v13/manifest.json",
        "manifest_sha256": "589dd8e1536b2b6d0cc3997f31c5841204593f64ce491d6c0647ca7230f8e133",
        "payload_path": "artifacts/rom-cfg-proven-roots-v13/rom-cfg-proven-roots-v13.json",
        "payload_sha256": "45b83aeb6e91249ebd5adefdb086c438b14c666e79aab780f7072a929343cb5b",
    },
}

TARGET_SPECS = (
    {
        "name": "root-0624c0",
        "root": 402_624,
        "root_raw_hex": "30b50d1c",
        "root_sha256": "45e2dca2a38dbec64e088121f36cdb12cf992e19435a246dd119085906149a97",
        "envelope": [402_624, 402_704],
        "envelope_bytes": 80,
        "envelope_sha256": "7c17a9e9fc5d12be5a93723ed0e8bf4d1479eeef0b4b3c51bb37442fbf6563ae",
        "code_ranges": [[402_624, 402_688]],
        "code_range_vector_sha256": "1fc30445da985be5dc3ea9d37d10cc5fb63cefc19c936db4fa9af2192f12b1b4",
        "literal_ranges": [[402_688, 402_704]],
        "literal_range_vector_sha256": "7981b07d5130aa71707077da3e2fdbc09f550de3ac210c6eb0981a8a7d2bb98a",
        "promotion_ranges": [[402_624, 402_688], [402_688, 402_704]],
        "promotion_range_vector_sha256": "4cddc1996161cd551509320b04eb4aa8b540561d0f7a0c69cc34e745fb7ee0a7",
        "promotion_bytes": 80,
        "block_ranges": [
            [402_624, 402_644],
            [402_644, 402_650],
            [402_650, 402_656],
            [402_656, 402_676],
            [402_676, 402_688],
        ],
        "block_range_vector_sha256": "e49760df777f2467a950f633e3d9de8f0b26307046494e475885321da6323841",
        "decoded_instruction_count": 32,
        "decoded_basic_block_count": 5,
        "reachable_instruction_bytes": 64,
        "semantic_instruction_vector_sha256": "cbfeca9de654e6c965ba16c82b5c0d7d46b619f250190b0c9dfd2632202d26ea",
        "instruction_internal_edge_count": 34,
        "instruction_internal_edge_vector_sha256": "35c92712328e2a33ebbb4f1880a483f3f74ee2253c47ebd0121ac69932585974",
        "block_internal_edge_count": 7,
        "block_internal_edge_vector_sha256": "dbfaa2e714f83edc1102799af4eea516b6cb10ca71fc295c9cbfe7a4a876da86",
        "external_edges": [],
        "external_edge_vector_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "boundary_edges": [],
        "frontiers": [[402_686, "indirect_pc_target"]],
        "frontier_vector_sha256": "12058f3ecce9b183815569991b15429950825ab0882c9a350ed52771265ff78b",
        "literal_binding_vector": [
            [402_632, 402_688],
            [402_636, 402_692],
            [402_656, 402_696],
            [402_666, 402_700],
        ],
        "literal_binding_vector_sha256": "975621afe38c6d0cbbc69561bbf8227a2c331f0a845371d92d9b4df1678351a5",
        "literal_reference_count": 4,
        "unique_literal_word_count": 4,
        "literal_bytes": 16,
        "packed_code_sha256": "a58bd92d8189cb4cb10e4a317714daaa48e35b4e834c318ad1208c6552b54ff4",
        "packed_literals_sha256": "56390d79e3596668bfb260ae852cfb46432e7f04783985773ced7b5af0ca26c1",
        "packed_promotion_sha256": "7c17a9e9fc5d12be5a93723ed0e8bf4d1479eeef0b4b3c51bb37442fbf6563ae",
        "holes": [],
        "producer_denominator": {
            "aligned_arm_pointers": [],
            "arm_b_bl": [],
            "thumb_b": [],
            "thumb_bcond": [],
            "thumb_bl": [411_028, 414_260],
            "thumb_pointers": [],
            "vector": [
                [411_028, 402_624, "thumb_bl"],
                [414_260, 402_624, "thumb_bl"],
            ],
            "vector_sha256": "90f39e5bf4ebf575592160fdd5ad445130c01c4abf796151c6b77f61849732b8",
        },
        "producers": [
            {
                "file_offset": 411_028,
                "raw_hex": "fdf794ff",
                "bytes_sha256": "466e37544f3e924f96016bb23689e342bbc301371477e1594df76c6b1b068ceb",
                "upstream_version": 12,
                "coverage_owner_claim_id": "cfg-proven-roots-v12-thumb-0003-064574",
                "coverage_owner_range": [410_996, 411_180],
            },
            {
                "file_offset": 414_260,
                "raw_hex": "fdf744f9",
                "bytes_sha256": "230f0adc7eb4891b1c6417ac2a81b771a1b047878143e80b1f4ce73a72bf4e86",
                "upstream_version": 13,
                "coverage_owner_claim_id": "cfg-proven-roots-v13-thumb-0000-0651f8",
                "coverage_owner_range": [414_200, 414_268],
            },
        ],
    },
    {
        "name": "root-062510",
        "root": 402_704,
        "root_raw_hex": "00b50006",
        "root_sha256": "59495eec8cd58cb20a8653e06060b861cf812a935637265e68473f0ca1c9599c",
        "envelope": [402_704, 402_784],
        "envelope_bytes": 80,
        "envelope_sha256": "b50e8017c2219ab3f25184d94e19eb515b363927094345969eb968f5c3e07013",
        "code_ranges": [[402_704, 402_760]],
        "code_range_vector_sha256": "3311aee0f01d27778b6a4276576a56a00ce5f1c3439e7d12d3ba076cc62bad49",
        "literal_ranges": [[402_760, 402_784]],
        "literal_range_vector_sha256": "1f8e68310be1a2ded1a09106f5f0c0708cf1d99d6267ea17b617e68e2b7bf45e",
        "promotion_ranges": [[402_704, 402_760], [402_760, 402_784]],
        "promotion_range_vector_sha256": "194265fa23ea7ac2c75322d4e758361499217348cd6bbee664dd4df2fd8b2541",
        "promotion_bytes": 80,
        "block_ranges": [
            [402_704, 402_724],
            [402_724, 402_730],
            [402_730, 402_736],
            [402_736, 402_756],
            [402_756, 402_760],
        ],
        "block_range_vector_sha256": "befc2ce46548aa68b033a6c2bc1e1071741d578d0805ee5a1f958b92dee3a2ec",
        "decoded_instruction_count": 28,
        "decoded_basic_block_count": 5,
        "reachable_instruction_bytes": 56,
        "semantic_instruction_vector_sha256": "e5b85e998792e394999ec1420b6474da67c623c68996c7a936290d938c3cc665",
        "instruction_internal_edge_count": 30,
        "instruction_internal_edge_vector_sha256": "15e31b0055a3414cfd023daaa0dbf4bc854976d74497a8fbc26806e636ffc801",
        "block_internal_edge_count": 7,
        "block_internal_edge_vector_sha256": "ab412ca0fc4050d028e536ad2ed8adf0da4a8bbaebc1534a2acee67c47921b59",
        "external_edges": [],
        "external_edge_vector_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "boundary_edges": [],
        "frontiers": [[402_758, "indirect_pc_target"]],
        "frontier_vector_sha256": "ffe21dbc265d85edd1823629156ce207a4de27b21ab37b1952a5dcde824439e3",
        "literal_binding_vector": [
            [402_708, 402_760],
            [402_714, 402_764],
            [402_736, 402_768],
            [402_740, 402_772],
            [402_746, 402_776],
            [402_750, 402_780],
        ],
        "literal_binding_vector_sha256": "4487371e1b9ea8cc9295fb8044c064479daedf2818151cf4af4ec61c0a989be3",
        "literal_reference_count": 6,
        "unique_literal_word_count": 6,
        "literal_bytes": 24,
        "packed_code_sha256": "f894a7d66905a2a4c0aefad17269e82796f0a4a2eda2f364c15859bebbc2e174",
        "packed_literals_sha256": "ab479d32e27e116dfe295fae19561f47dac42395385b18392b2aab32fb98d8cf",
        "packed_promotion_sha256": "b50e8017c2219ab3f25184d94e19eb515b363927094345969eb968f5c3e07013",
        "holes": [],
        "producer_denominator": {
            "aligned_arm_pointers": [],
            "arm_b_bl": [],
            "thumb_b": [],
            "thumb_bcond": [],
            "thumb_bl": [410_866, 410_924, 414_296],
            "thumb_pointers": [],
            "vector": [
                [410_866, 402_704, "thumb_bl"],
                [410_924, 402_704, "thumb_bl"],
                [414_296, 402_704, "thumb_bl"],
            ],
            "vector_sha256": "a6f76c181f2cee24a8829df91071e77427d118f951afb931e4f07002151c1105",
        },
        "producers": [
            {
                "file_offset": 410_866,
                "raw_hex": "fef70df8",
                "bytes_sha256": "4d74df788c0c1329dd5ed60984c92c509cd3edac6e5b85512be19c12a7859397",
                "upstream_version": 12,
                "coverage_owner_claim_id": "cfg-proven-roots-v12-thumb-0001-0644d8",
                "coverage_owner_range": [410_840, 410_890],
            },
            {
                "file_offset": 410_924,
                "raw_hex": "fdf7f0ff",
                "bytes_sha256": "202461872e6bf6112810711936218f766883c75db142863cf858da6cc2ae4137",
                "upstream_version": 12,
                "coverage_owner_claim_id": "cfg-proven-roots-v12-thumb-0002-064518",
                "coverage_owner_range": [410_904, 410_968],
            },
            {
                "file_offset": 414_296,
                "raw_hex": "fdf75af9",
                "bytes_sha256": "ed8630140e86e181fda41a9919a69c69527c632c090d791b3f69f9928743ee40",
                "upstream_version": 13,
                "coverage_owner_claim_id": "cfg-proven-roots-v13-thumb-0001-06524c",
                "coverage_owner_range": [414_284, 414_430],
            },
        ],
    },
)

PROMOTION_RANGES = [[402_624, 402_688], [402_688, 402_704], [402_704, 402_760], [402_760, 402_784]]
PROMOTION_RANGE_SHA256 = "ed05dacca1ab7200679b3c8754a61ff116ce0bc96bd718d3c80fa1f0b2b2a4ed"
PROMOTION_PACKED_SHA256 = "25f6db2c2844ed30e0ea9ae4315568d0e33047be99e268bb6a9ae28f90fec1a8"

NONCLAIMS = [
    "natural_execution_or_runtime_reachability",
    "global_code_caller_or_producer_denominator",
    "global_indirect_computed_or_ram_target_denominator",
    "bx_r0_indirect_target_or_runtime_dispatch_denominator",
    "callee_code_abi_or_business_semantics",
    "literal_business_meaning_or_compiler_authorship",
    "adjacent_bytes_padding_or_allocatable_space",
    "editing_writeback_relocation_or_gameplay_behavior",
]
SCOPE = {
    "fixed_target_direct_producer_denominators_complete": True,
    "all_producers_bound_to_accepted_v12_or_v13_nodes": True,
    "all_producers_bound_to_current_coverage_owner": True,
    "target_worklists_bounded_to_frozen_envelopes": True,
    "literal_bindings_rebuilt_from_raw_rom": True,
    "promotion_is_exact_unknown_union_within_frozen_envelopes": True,
    "two_indirect_pc_frontiers_explicit_and_unresolved": True,
    "runtime_reachability_complete": False,
    "global_code_denominator_complete": False,
    "global_caller_denominator_complete": False,
    "global_indirect_target_denominator_complete": False,
    "structured_returns_proven": False,
    "callee_semantics_proven": False,
    "literal_business_meaning_proven": False,
    "editing_relocation_safe": False,
    "nonclaims": NONCLAIMS,
}
