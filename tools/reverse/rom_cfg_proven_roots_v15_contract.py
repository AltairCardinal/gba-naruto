#!/usr/bin/env python3
"""Frozen constants for the raw-ROM CFG proven-roots v15 candidate packet.

This module is the checked-in implementation contract.  It intentionally
contains no code that discovers or reads the sealed preflight report (and no
live coverage path): product code rebuilds the vectors below from the ROM and
the hash-bound v8/v12/v13 upstream packets.
"""

from __future__ import annotations

from pathlib import Path


ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "rom-cfg-proven-roots-v15"
VERIFY_SCHEMA = "rom-cfg-proven-roots-v15-verification-v1"
BUNDLE_VERIFY_SCHEMA = "rom-cfg-proven-roots-v15-bundle-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
PAYLOAD_NAME = "rom-cfg-proven-roots-v15.json"
MANIFEST_NAME = "manifest.json"
EXPERIMENT_OUTPUT_ROOT = Path(
    "build/experiments/active/cfg-proven-roots-v15-implementation-20260830"
)
OFFICIAL_ARTIFACT = Path("artifacts/rom-cfg-proven-roots-v15")


# The public contract deliberately exposes only these immutable dependency
# identities.  In particular, the live coverage manifest is not an input to
# either product verifier.
UPSTREAM = {
    "v12": {
        "manifest_path": "artifacts/rom-cfg-proven-roots-v12/manifest.json",
        "manifest_sha256": "bf88e08f4eed6b53e1debef709c2ef13fb891c11e9c172485e494eef57954677",
        "payload_path": "artifacts/rom-cfg-proven-roots-v12/rom-cfg-proven-roots-v12.json",
        "payload_sha256": "fd9df8f3d93de1df5aa7e725040f27f854d08e8203d6cada51db829ddcd9bcee",
    },
    "v13": {
        "manifest_path": "artifacts/rom-cfg-proven-roots-v13/manifest.json",
        "manifest_sha256": "589dd8e1536b2b6d0cc3997f31c5841204593f64ce491d6c0647ca7230f8e133",
        "payload_path": "artifacts/rom-cfg-proven-roots-v13/rom-cfg-proven-roots-v13.json",
        "payload_sha256": "45b83aeb6e91249ebd5adefdb086c438b14c666e79aab780f7072a929343cb5b",
    },
    "v8": {
        "manifest_path": "artifacts/rom-cfg-proven-roots-v8/manifest.json",
        "manifest_sha256": "0c9194507c50b7f2c00c6ee09b517211f64b7b344475952fe3c908b1e54e0002",
        "payload_path": "artifacts/rom-cfg-proven-roots-v8/rom-cfg-proven-roots-v8.json",
        "payload_sha256": "5fa1150d2ed9f785d50132a9eae316af192d70838fbee3061d7d3010c35fb1d6",
    },
}

ORACLE_IDENTITIES = {
    "export": {
        "path": "tools/export_rom_cfg_proven_roots_v13.py",
        "sha256": "7017045fc098faff14e1726873a05a379123222ee878d771e3bdb4b5d5a70c8c",
    },
    "verify": {
        "path": "tools/verify_rom_cfg_proven_roots_v13.py",
        "sha256": "a687af7750e9a177b47883f1b540d555bd4c666d92865d56e521f85174c869a7",
    },
}


def _producer(
    file_offset: int,
    raw_hex: str,
    bytes_sha256: str,
    upstream_version: int,
    source_pointer: str,
    target: int,
    owner_range: list[int],
    owner_claim_id: str,
    *,
    kind: str = "v12-accepted-source-node",
    owner_class: str = "consumer_code_slice",
    source_worklist_range: list[int] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "file_offset": file_offset,
        "gba_address": f"0x{ROM_BASE + file_offset:08X}",
        "target_file_offset": target,
        "target_gba_address": f"0x{ROM_BASE + target:08X}",
        "raw_hex": raw_hex,
        "bytes_sha256": bytes_sha256,
        "upstream_version": upstream_version,
        "upstream_manifest_sha256": UPSTREAM[f"v{upstream_version}"]["manifest_sha256"],
        "upstream_payload_sha256": UPSTREAM[f"v{upstream_version}"]["payload_sha256"],
        "coverage_owner_range": owner_range,
        "coverage_owner_class": owner_class,
        "coverage_owner_claim_id": owner_claim_id,
        "kind": kind,
        "source_pointer": source_pointer,
    }
    if source_worklist_range is not None:
        value["source_worklist_range"] = source_worklist_range
    return value


_OWNER_BATTLE = "consumer-code-battle_effect_sprite_animations-0612bc"
_OWNER_SCENE = "verified-reuse-scene-visual-pack-setup-08bafc"


TARGET_SPECS = (
    {
        "name": "root-09a3e0",
        "root": 0x09A3E0,
        "root_raw_hex": "aa480068",
        "root_sha256": "8224015870e393eef6ab6de05eb1777743ce01af88efc59a8cc4c8d35f8f4314",
        "envelope": [0x09A3E0, 0x09A42C],
        "envelope_bytes": 76,
        "envelope_sha256": "dc1f26a42cabf2ec4cddeffe54d52fe85e61473478f237d16d3b4f2774defd91",
        "code_ranges": [[0x09A3E0, 0x09A422]],
        "code_range_vector_sha256": "04042f6768764c6cad59a956e7438e4cf6abd3af64f0a12369d1f8f0735aa57d",
        "literal_ranges": [[0x09A424, 0x09A42C]],
        "literal_range_vector_sha256": "cc028ad9c32b2129258a9071e911574651828fd20e3eb6973d110bc9cd136470",
        "promotion_ranges": [[0x09A3E0, 0x09A422], [0x09A424, 0x09A42C]],
        "promotion_range_vector_sha256": "eb5bfece96cbf9e9f303513ba763eecf668df9afeac79a45906dc3d369388240",
        "promotion_bytes": 74,
        "block_ranges": [
            [0x09A3E0, 0x09A3EE],
            [0x09A3EE, 0x09A3F6],
            [0x09A3F6, 0x09A402],
            [0x09A402, 0x09A406],
            [0x09A406, 0x09A40C],
            [0x09A40C, 0x09A410],
            [0x09A410, 0x09A420],
            [0x09A420, 0x09A422],
        ],
        "block_range_vector_sha256": "bfdb4d39bfd19cb77c9f56d7494da647ceb48a6b0dae1a3aae4fcebef1739d28",
        "decoded_instruction_count": 33,
        "decoded_basic_block_count": 8,
        "reachable_instruction_bytes": 66,
        "semantic_instruction_vector_sha256": "3204851d18249f4c5b94d4cf1d9fac50d04119ac34b347dda8ec1164f62bffda",
        "instruction_internal_edge_count": 36,
        "instruction_internal_edge_vector_sha256": "1f75c3c241ab3ab7d14c431cbac9830008b7beff6bebe23e8775e7104483fe3d",
        "block_internal_edge_count": 11,
        "block_internal_edge_vector_sha256": "6a7342282ff3a022ce471f05c3a9f9dfbcb1d3a8167b5cf385d5441538b44e3b",
        "external_edges": [],
        "external_edge_vector_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "boundary_edges": [],
        "frontiers": [],
        "frontier_vector_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "literal_binding_vector": [
            [0x09A3E0, 0x09A68C],
            [0x09A3E4, 0x09A690],
            [0x09A3FA, 0x09A424],
            [0x09A402, 0x09A428],
            [0x09A40C, 0x09A428],
        ],
        "literal_binding_vector_sha256": "4d528e3773d6c5f8300654db033f07b54c87612fa08216a1eb49b2f94ece0bfb",
        "literal_reference_count": 5,
        "unique_literal_word_count": 4,
        "literal_bytes": 8,
        "packed_code_sha256": "30850910827424666137a474df6fc7ad26262f70f6047d2bf68fd6dcb0bd4c84",
        "packed_literals_sha256": "bf6a5df3083f3996afa62523d42508bf1d286a17e318da60f717c38ad488b4db",
        "packed_promotion_sha256": "d768becc596cf187cfb6fcecc81cf811c8a43e8ef7a36d06cf5dc643e03348bb",
        "holes": [[0x09A422, 0x09A424]],
        "known_external_literal_ranges": [[0x09A68C, 0x09A694]],
        "producer_denominator": {
            "aligned_arm_pointers": [],
            "arm_b_bl": [],
            "thumb_b": [],
            "thumb_bcond": [],
            "thumb_bl": [0x0612C8],
            "thumb_pointers": [],
            "vector": [[0x0612C8, 0x09A3E0, "thumb_bl"]],
            "vector_sha256": "be586822e6d1efd806a48a63974ced4ef1f3dc1fe6c3670f74f85f967fdd1088",
        },
        "producers": [
            _producer(
                0x0612C8,
                "39f08af8",
                "ba05baa0ae5ae3c2bfbfa22edb5326121496b77a6cf45cbf2c80df3e24922b0a",
                12,
                "/source/nodes/6",
                0x09A3E0,
                [0x0612BC, 0x0614E4],
                _OWNER_BATTLE,
            )
        ],
    },
    {
        "name": "root-0611f4",
        "root": 0x0611F4,
        "root_raw_hex": "10b51148",
        "root_sha256": "0b9341dcc0f11aef976462b4ee9403dfb8d33bdba4e4dcd1d359fbcb92255ff2",
        "envelope": [0x0611F4, 0x0612BC],
        "envelope_bytes": 200,
        "envelope_sha256": "dd9f2ec693efe476274481ac356aab725e9490e6c9656ec3786a27bac0b04acd",
        "code_ranges": [[0x0611F4, 0x06123A], [0x061250, 0x061276]],
        "code_range_vector_sha256": "12a2c7060af8dd490febafd8e986e7f44ca489c5a2dffc2577bd396391055b41",
        "literal_ranges": [[0x06123C, 0x061250], [0x061278, 0x06128C]],
        "literal_range_vector_sha256": "400abecec590b8e364a45cd7b8c7a3959e82b9e3d1a1f84749722d4bbfcdb59c",
        "promotion_ranges": [[0x0611F4, 0x06123A], [0x06123C, 0x061276], [0x061278, 0x06128C]],
        "promotion_range_vector_sha256": "1eabfdb561cd5955641fcd211fd2f4d73adb95d485cae6ce14b47ccd07187a53",
        "promotion_bytes": 148,
        "block_ranges": [
            [0x0611F4, 0x061202],
            [0x061202, 0x06120E],
            [0x06120E, 0x061226],
            [0x061226, 0x06123A],
            [0x061250, 0x061258],
            [0x061258, 0x061270],
            [0x061270, 0x061276],
        ],
        "block_range_vector_sha256": "5ae15feea976567ee01e0499d43a2265a7ec10f3f788568eab14262680964e8a",
        "decoded_instruction_count": 53,
        "decoded_basic_block_count": 7,
        "reachable_instruction_bytes": 108,
        "semantic_instruction_vector_sha256": "43ffe2530765ebc908f0461bf495ac909d2a115e674cb8ca4d5ac9484743dc0d",
        "instruction_internal_edge_count": 55,
        "instruction_internal_edge_vector_sha256": "6779b8c6bed5bfb3d3b55223c904bb0c0b83971fda37cca9f7ee3ee27e364587",
        "block_internal_edge_count": 9,
        "block_internal_edge_vector_sha256": "7a81095bb3e1e546fe2f453068f38eba7ebb3f78035fbcf5c9100de82f82ad28",
        "external_edges": [
            {"source_file_offset": 0x06126C, "target_file_offset": 0x06154C, "edge_kind": "call_target", "reason": "opaque_external"}
        ],
        "external_edge_vector_sha256": "5773ff521ef55199c96b2218d641bc3a7f476a40b0d41d7ec40433821dbe4314",
        "boundary_edges": [],
        "frontiers": [[0x061274, "indirect_pc_target"]],
        "frontier_vector_sha256": "a5bb96aeb05a3f59cde8d0c3b48b1e76c2e211a3de933db953cb509f8d20bc0f",
        "literal_binding_vector": [
            [0x0611F6, 0x06123C],
            [0x061202, 0x061240],
            [0x061206, 0x061244],
            [0x06120E, 0x061248],
            [0x061218, 0x06124C],
            [0x061226, 0x06124C],
            [0x061250, 0x061278],
            [0x061258, 0x06127C],
            [0x06125C, 0x061280],
            [0x061262, 0x061284],
            [0x061266, 0x061288],
        ],
        "literal_binding_vector_sha256": "2d3ecd6d922c39c10731e6ce596c125538b6c099ed1e0e796f60dcc9c95d76be",
        "literal_reference_count": 11,
        "unique_literal_word_count": 10,
        "literal_bytes": 40,
        "packed_code_sha256": "5538b1ade987c1ea2ba3930a03fa0df2ac388868f0d1cf49fb20c5e3430f34ce",
        "packed_literals_sha256": "ae25094faca6b4e4b53ef0e8f6fd8a47fa4fb24bc6693523d750ebdf04703ffc",
        "packed_promotion_sha256": "a77c6640f585163f527230d3f587dc74cdc5dfec45e72ddb2cb39a706e457b37",
        "holes": [[0x06123A, 0x06123C], [0x061276, 0x061278], [0x06128C, 0x0612BC]],
        "known_external_literal_ranges": [],
        "producer_denominator": {
            "aligned_arm_pointers": [],
            "arm_b_bl": [],
            "thumb_b": [],
            "thumb_bcond": [],
            "thumb_bl": [0x06144A],
            "thumb_pointers": [],
            "vector": [[0x06144A, 0x0611F4, "thumb_bl"]],
            "vector_sha256": "7c9f535dad62e3e3c8f1d611496530e01201bdcff788d2ae674cc6c02ebaff0d",
        },
        "producers": [
            _producer(
                0x06144A,
                "fff7d3fe",
                "c684260e8922f3083767f3583c6f01701f0f6c92acf8affbe395e2bc0b14b66b",
                12,
                "/source/nodes/168",
                0x0611F4,
                [0x0612BC, 0x0614E4],
                _OWNER_BATTLE,
            )
        ],
    },
    {
        "name": "root-0618fc",
        "root": 0x0618FC,
        "root_raw_hex": "30b5084c",
        "root_sha256": "0d499deab1b5e26d0930e0dacc3d0e9a2db99df9f4827e29e2c1d699678fd0cf",
        "envelope": [0x0618FC, 0x061A80],
        "envelope_bytes": 388,
        "envelope_sha256": "61283963470a4195bc3a7b2531aba32ecbef91502cd86cda255866bfb39579ee",
        "code_ranges": [[0x0618FC, 0x061920], [0x061924, 0x061936]],
        "code_range_vector_sha256": "3ffa707793f636228f79645772c1f278e5b44a6012df5292be59e026b967f394",
        "literal_ranges": [[0x061920, 0x061924]],
        "literal_range_vector_sha256": "ae48f570e2232b82533505b50045a79d6d71bc3b153c8ea611e2803fdabd546c",
        "promotion_ranges": [[0x0618FC, 0x061936]],
        "promotion_range_vector_sha256": "0f67faae3672b4b0d6723a8737b71a2f1c3a5a2018ad98f83004c32943be893d",
        "promotion_bytes": 58,
        "block_ranges": [
            [0x0618FC, 0x061906],
            [0x061906, 0x06190A],
            [0x06190A, 0x061910],
            [0x061910, 0x061916],
            [0x061916, 0x06191C],
            [0x06191C, 0x061920],
            [0x061924, 0x061928],
            [0x061928, 0x061930],
            [0x061930, 0x061936],
        ],
        "block_range_vector_sha256": "2c20cd6957fbcfa9ac0df88aa0842baa51bd2a2b907dbc2f4c3b86d30c65f775",
        "decoded_instruction_count": 26,
        "decoded_basic_block_count": 9,
        "reachable_instruction_bytes": 54,
        "semantic_instruction_vector_sha256": "083cbea57dfd42ca617fba267ce00e0531913e4d3f4bbf7851c37ddb386e200b",
        "instruction_internal_edge_count": 29,
        "instruction_internal_edge_vector_sha256": "02cc6462fd755477d7565c78b49ac9ac72b29a3a649205944f7f49861bfccd93",
        "block_internal_edge_count": 12,
        "block_internal_edge_vector_sha256": "cdaa1b3f821721ce0fb1c2b9c39d3466ff67a9d0f89d69a1c9dd84f58e0d7afd",
        "external_edges": [
            {"source_file_offset": 0x061918, "target_file_offset": 0x09C114, "edge_kind": "call_target", "reason": "opaque_external"}
        ],
        "external_edge_vector_sha256": "cd34903d76f36912120aed5fe2fbdd305934044b35e98af05886242849d532d2",
        "boundary_edges": [],
        "frontiers": [[0x061934, "indirect_pc_target"]],
        "frontier_vector_sha256": "ca9c4c492850a3f5c0b5d971a92cb28e656a6047c0bf6a3793f1445c12136501",
        "literal_binding_vector": [[0x0618FE, 0x061920]],
        "literal_binding_vector_sha256": "658a43eb1e28f77c898e232a3494fcf0142bc4487dad23334be4bd3f25ea4d97",
        "literal_reference_count": 1,
        "unique_literal_word_count": 1,
        "literal_bytes": 4,
        "packed_code_sha256": "d60c056e4a69ea8dcfab5134fad5690c675d727197533fa2c50c28141d5a370c",
        "packed_literals_sha256": "ab75ee2e74b92ed8c18bc0982efd954972ef47c20e8274c1445c71fba7cc9c9a",
        "packed_promotion_sha256": "9b8e2672a69855e923ce2ee460a088940c1db93e911154b1cc071f309160c685",
        "holes": [[0x061936, 0x061A80]],
        "known_external_literal_ranges": [],
        "producer_denominator": {
            "aligned_arm_pointers": [],
            "arm_b_bl": [],
            "thumb_b": [],
            "thumb_bcond": [],
            "thumb_bl": [0x061456],
            "thumb_pointers": [],
            "vector": [[0x061456, 0x0618FC, "thumb_bl"]],
            "vector_sha256": "a357c59daec4bd61f9e00e8bcc787e745fb726ea53e7fa137ca8aa6e79794175",
        },
        "producers": [
            _producer(
                0x061456,
                "00f051fa",
                "46debfa97fff199d8166b31bc1697c5d0e2e1a1ca2b28ee66a2bf1fba6788cf2",
                12,
                "/source/nodes/173",
                0x0618FC,
                [0x0612BC, 0x0614E4],
                _OWNER_BATTLE,
            )
        ],
    },
    {
        "name": "root-08b6f0",
        "root": 0x08B6F0,
        "root_raw_hex": "f0b55746",
        "root_sha256": "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb",
        "envelope": [0x08B6F0, 0x08B79C],
        "envelope_bytes": 172,
        "envelope_sha256": "5d82ab507ffc535d39e2fd6969bf8e301ed9b6d7a0ababa6dcd66f8e36104066",
        "code_ranges": [[0x08B6F0, 0x08B79A]],
        "code_range_vector_sha256": "c0fad3e6e146839953e94c61f926afd47393587c5c172f4955882f97dc913b55",
        "literal_ranges": [],
        "literal_range_vector_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "promotion_ranges": [[0x08B6F0, 0x08B79A]],
        "promotion_range_vector_sha256": "c0fad3e6e146839953e94c61f926afd47393587c5c172f4955882f97dc913b55",
        "promotion_bytes": 170,
        "block_ranges": [
            [0x08B6F0, 0x08B74C],
            [0x08B74C, 0x08B75C],
            [0x08B75C, 0x08B768],
            [0x08B768, 0x08B76C],
            [0x08B76C, 0x08B780],
            [0x08B780, 0x08B78C],
            [0x08B78C, 0x08B79A],
        ],
        "block_range_vector_sha256": "21d48f041ffb0d61b72e1e2f23052bf04320782c4dd13f2f83144fa5d6a2ad8b",
        "decoded_instruction_count": 85,
        "decoded_basic_block_count": 7,
        "reachable_instruction_bytes": 170,
        "semantic_instruction_vector_sha256": "78f1549b462a0a48177de60b965988e4b1454f8b07bc5ab623f3f3e9822aed1a",
        "instruction_internal_edge_count": 88,
        "instruction_internal_edge_vector_sha256": "a1a826de7f184c62eee11c5ab69ea55689de70ff50217bc1aba48ebed5028479",
        "block_internal_edge_count": 10,
        "block_internal_edge_vector_sha256": "8735636fd5b512ccb6a1f1e8e22c6412abcfd53fdc69726d99257b46cacf77e3",
        "external_edges": [],
        "external_edge_vector_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "boundary_edges": [],
        "frontiers": [[0x08B798, "indirect_pc_target"]],
        "frontier_vector_sha256": "b619bf05e8309a7b59eb4255be3884b2dd981192a250a3d99978e57bf49276ab",
        "literal_binding_vector": [],
        "literal_binding_vector_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "literal_reference_count": 0,
        "unique_literal_word_count": 0,
        "literal_bytes": 0,
        "packed_code_sha256": "fbc2ee13417cb7ac37b2e668ff6b2f4d3b1fa0a4637c52c9ca9d53183ec91fc1",
        "packed_literals_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "packed_promotion_sha256": "fbc2ee13417cb7ac37b2e668ff6b2f4d3b1fa0a4637c52c9ca9d53183ec91fc1",
        "holes": [[0x08B79A, 0x08B79C]],
        "known_external_literal_ranges": [],
        "producer_denominator": {
            "aligned_arm_pointers": [],
            "arm_b_bl": [],
            "thumb_b": [],
            "thumb_bcond": [],
            "thumb_bl": [0x08BBAA],
            "thumb_pointers": [],
            "vector": [[0x08BBAA, 0x08B6F0, "thumb_bl"]],
            "vector_sha256": "3bd668893a7235226f1560bfffb3feb395c48aa70ed4a9273d7db1df2688d681",
        },
        "producers": [
            _producer(
                0x08BBAA,
                "fff7a1fd",
                "26b656da1202d1fc837ddc2d419acf0f005af2843eafcdb83eb7ce18f72c6399",
                8,
                "/source/worklist/accepted_instruction_offsets/114",
                0x08B6F0,
                [0x08BAFC, 0x08BBD4],
                _OWNER_SCENE,
                kind="v8-accepted-source-worklist-offset",
                source_worklist_range=[0x08BAB0, 0x08BEDE],
            )
        ],
    },
)


REJECTED_TARGET_SPEC = {
    "name": "root-09c0f4-rejected",
    "root": 0x09C0F4,
    "root_raw_hex": "044b0022",
    "root_sha256": "5241b62224a24fc25ee6a35ecb82dcac617c106fa34e1da352a60459e80f8db0",
    "envelope": [0x09C0F4, 0x09C110],
    "envelope_bytes": 28,
    "envelope_sha256": "db9e196e2017f65966801dc2de56caec130721776e440457c6b56c36ceee4fd1",
    "code_ranges": [[0x09C0F4, 0x09C110]],
    "code_range_vector_sha256": "f3bf1fbee195bd5eee469801ca38354fc584b89af9dbe57647affda8ec54da9a",
    "literal_ranges": [[0x09C108, 0x09C110]],
    "literal_range_vector_sha256": "227c765ea12f2fd63e85b337647e7d75851026d85a9e396007078b9accac2989",
    "promotion_ranges": [[0x09C0F4, 0x09C110]],
    "promotion_range_vector_sha256": "f3bf1fbee195bd5eee469801ca38354fc584b89af9dbe57647affda8ec54da9a",
    "promotion_bytes": 28,
    "block_ranges": [[0x09C0F4, 0x09C106], [0x09C106, 0x09C108], [0x09C108, 0x09C110]],
    "block_range_vector_sha256": "50f8383f68c9f036a169590c3ba6a7cf8826637d298500dd9cd609944f513693",
    "decoded_instruction_count": 14,
    "decoded_basic_block_count": 3,
    "reachable_instruction_bytes": 28,
    "semantic_instruction_vector_sha256": "4cc07b260e0877d22c0ee6cad130bac8e2065dbab77f37d122d3fde5d0413f4f",
    "instruction_internal_edge_count": 13,
    "instruction_internal_edge_vector_sha256": "a569ad18934b01f103d9eceadfde8ea63e32f1687cce67ed930717c0d1c72cfb",
    "block_internal_edge_count": 2,
    "block_internal_edge_vector_sha256": "1a05203f1f1ebda6b94129b0593152b332aeb3f50a6f782167a795ecdd791137",
    "external_edges": [],
    "external_edge_vector_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
    "boundary_edges": [
        {"source_file_offset": 0x09C10E, "target_file_offset": 0x09C110, "edge_kind": "opaque_boundary", "reason": "accepted_owner_beginning"}
    ],
    "frontiers": [[0x09C104, "bios_swi_external"], [0x09C106, "bios_swi_external"]],
    "frontier_vector_sha256": "baf48f33d14bf82cb58d75c2f2d972fdd50e4613e449bc5b7bac58230028a4c6",
    "literal_binding_vector": [[0x09C0F4, 0x09C108], [0x09C0FA, 0x09C10C]],
    "literal_binding_vector_sha256": "c3615edc4020c480aa561168a5f73993b4f1922ac31706d0c6021257a900cdb4",
    "literal_reference_count": 2,
    "unique_literal_word_count": 2,
    "literal_bytes": 0,
    "packed_code_sha256": "db9e196e2017f65966801dc2de56caec130721776e440457c6b56c36ceee4fd1",
    "packed_literals_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "packed_promotion_sha256": "db9e196e2017f65966801dc2de56caec130721776e440457c6b56c36ceee4fd1",
    "holes": [],
    "known_external_literal_ranges": [],
    "literal_code_overlap_ranges": [[0x09C108, 0x09C110]],
    "unbound_raw_thumb_bl_matches": [0x0610C6],
    "producer_denominator": {
        "aligned_arm_pointers": [],
        "arm_b_bl": [],
        "thumb_b": [],
        "thumb_bcond": [],
        "thumb_bl": [0x0610C6, 0x061318],
        "thumb_pointers": [],
        "vector": [[0x0610C6, 0x09C0F4, "thumb_bl"], [0x061318, 0x09C0F4, "thumb_bl"]],
        "vector_sha256": "67196eaaeb5bcb8763f4b218c81361bb3491a957645e1ffff995f0dfc7343b1e",
    },
    "producers": [
        _producer(
            0x061318,
            "3af0ecfe",
            "8457f13ae76adf50d9b87a3699fd685267c2ccc363647a243b4a253b3e477390",
            12,
            "/source/nodes/43",
            0x09C0F4,
            [0x0612BC, 0x0614E4],
            _OWNER_BATTLE,
        )
    ],
    "reasons": ["literal_code_overlap", "unbound_raw_thumb_bl_match"],
    "unbound_raw_matches": {
        0x0610C6: {
            "file_offset": 0x0610C6,
            "raw_hex": "3bf015f8",
            "bytes_sha256": "236e183cb82e127acd67a528c471fcbefcd128be9fe40916145ed608852f83ca",
            "decoded_target": 0x09C0F4,
            "coverage_owner_range": [0x06108A, 0x0610E8],
            "coverage_owner_class": "unknown",
            "source_membership": False,
            "promoted": False,
        }
    },
}

EXCLUDED_SOURCE_SPEC = {
    "file_offset": 0x08B644,
    "raw_hex": "fff740fb",
    "bytes_sha256": "f7e047cc350bda582135e51f36c556fb0e6445de6ee9c286ae9383c6bbefdc7a",
    "decoded_target": 0x08ACC8,
    "accepted": False,
    "reason": "absent_from_v8_accepted_source_worklist",
}


PROMOTION_CODE_RANGES = [
    [0x0611F4, 0x06123A],
    [0x061250, 0x061276],
    [0x0618FC, 0x061920],
    [0x061924, 0x061936],
    [0x08B6F0, 0x08B79A],
    [0x09A3E0, 0x09A422],
]
PROMOTION_LITERAL_RANGES = [
    [0x06123C, 0x061250],
    [0x061278, 0x06128C],
    [0x061920, 0x061924],
    [0x09A424, 0x09A42C],
]
PROMOTION_SEMANTIC_RANGES = [
    [0x0611F4, 0x06123A],
    [0x06123C, 0x061250],
    [0x061250, 0x061276],
    [0x061278, 0x06128C],
    [0x0618FC, 0x061920],
    [0x061920, 0x061924],
    [0x061924, 0x061936],
    [0x08B6F0, 0x08B79A],
    [0x09A3E0, 0x09A422],
    [0x09A424, 0x09A42C],
]
PROMOTION_UNION_RANGES = [
    [0x0611F4, 0x06123A],
    [0x06123C, 0x061276],
    [0x061278, 0x06128C],
    [0x0618FC, 0x061936],
    [0x08B6F0, 0x08B79A],
    [0x09A3E0, 0x09A422],
    [0x09A424, 0x09A42C],
]
PROMOTION_SEMANTIC_RANGE_SHA256 = "4cb1b785aa18b03873dee55781289574009c42231d1dfd198aa024bc41d38974"
PROMOTION_UNION_RANGE_SHA256 = "9a91de64231f4d1cf2bbf41e4aa4858c4fa4e3af7dddf60a5ae79287da506ad0"
PROMOTION_PACKED_SHA256 = "764b272bc4d19be46d334c10e47d00419c05fa60d6878ef336f455d25e7b08e7"
PROMOTION_CODE_PACKED_SHA256 = "3a6a2a8af4439bad3e307febe821e577af334d111e551974c8cc2efb977d184e"
PROMOTION_LITERAL_PACKED_SHA256 = "c0c380051fe84e2e4b2ce1a295015623f9642c6dbe6527c21d713e2bf83779eb"


NONCLAIMS = [
    "natural_execution_or_runtime_reachability",
    "global_code_caller_or_producer_denominator",
    "global_indirect_computed_or_ram_target_denominator",
    "bios_swi0_terminal_or_return_semantics",
    "callee_code_abi_or_business_semantics",
    "literal_business_meaning_or_compiler_authorship",
    "adjacent_bytes_padding_or_allocatable_space",
    "editing_writeback_relocation_or_gameplay_behavior",
]
SCOPE = {
    "fixed_target_matching_encoding_denominators_complete": True,
    "accepted_roots_have_accepted_source_membership": True,
    "accepted_sources_bound_to_current_coverage_owner": True,
    "target_worklists_bounded_to_frozen_envelopes": True,
    "literal_bindings_rebuilt_from_raw_rom": True,
    "promotion_is_exact_unknown_union_within_frozen_envelopes": True,
    "rejected_root_isolated": True,
    "literal_overlap_rejected_fail_closed": True,
    "known_external_literals_provenance_only": True,
    "unknown_external_calls_remain_opaque": True,
    "three_indirect_pc_frontiers_explicit_and_unresolved": True,
    "all_candidate_roots_accepted": False,
    "all_raw_matching_encodings_source_bound": False,
    "runtime_reachability_complete": False,
    "global_code_denominator_complete": False,
    "global_caller_denominator_complete": False,
    "global_indirect_target_denominator_complete": False,
    "bios_terminal_semantics_proven": False,
    "callee_semantics_proven": False,
    "literal_business_meaning_proven": False,
    "editing_relocation_safe": False,
    "nonclaims": NONCLAIMS,
}


RUNTIME_DEPENDENCY_PATHS = (
    Path("tools/export_rom_cfg_inventory.py"),
    Path("tools/verify_rom_cfg_inventory.py"),
    Path("tools/verify_battle_effect_sprite_animations.py"),
) + tuple(
    Path("tools/_vendor/capstone") / path.name
    for path in sorted((Path(__file__).resolve().parents[1] / "tools/_vendor/capstone").glob("*.py"))
) + (Path("tools/_vendor/capstone/lib/libcapstone.dylib"),)
