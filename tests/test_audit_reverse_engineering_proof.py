#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from tools.audit_reverse_engineering_proof import (
    EXPECTED_BANKS,
    EXPECTED_DISPROVED_CANDIDATE_RANGES,
    GATE_CASES,
    VERIFIER_TIMEOUT_SECONDS,
    _contract,
    _execute_contract,
    _reuse_rom_coverage_contract,
    audit_proof,
)
from tools.verify_disproved_bank_candidates import DISPROVED_SPECS


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "sequel/reverse-engineering-proof.json"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReverseEngineeringProofAuditTests(unittest.TestCase):
    def test_current_spec_binds_latest_cfg_and_coverage_delta(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        self.assertEqual(
            "71f09c9d998b07b2f12ccd64e86f8589839a9dc659d90ad49b3d6c38d5880620",
            evidence[
                "artifacts/rom-parser-bound-zero-padding-v1/manifest.json"
            ],
        )
        self.assertEqual(
            "d9440e4ea32db1ea51dc6d00bbb3788c9f79ea5b8d20d0e1444f9a3d07c22baf",
            evidence[
                "artifacts/rom-scene-visual-source-ranges-v1/manifest.json"
            ],
        )
        self.assertEqual(
            "a0e97ec43858a145a7c26dc71c5b89dfe8c4d9a5d6074ccad88c4ae56e03afd5",
            evidence[
                "artifacts/rom-cutscene-obj-source-ranges-v1/manifest.json"
            ],
        )
        self.assertEqual(
            "8a8675c2724131a6caa9b956825d74280fa26fe99447470b3cc3810688e6f88b",
            evidence[
                "artifacts/rom-menu-portrait-palette-inventory-v1/manifest.json"
            ],
        )
        self.assertEqual(
            "094dbb593b2b8e09849ea795f4a09155598936cd3a1bc0b36e2eda6a413cf789",
            evidence[
                "artifacts/rom-selector-direct-source-records-v1/manifest.json"
            ],
        )
        self.assertEqual(
            "bb3f2588ad22567190c1084a12eca42a1615091bc335fe45788d2556299ba6c0",
            evidence["artifacts/rom-selector-code-windows-v1/manifest.json"],
        )
        self.assertEqual(
            "448da9894e01d750111cc0ea3467f3cbcd3c9f2b41fadf0f1972fc219809f9d3",
            evidence[
                "artifacts/rom-referenced-text-slot-padding-v1/manifest.json"
            ],
        )
        self.assertEqual(
            "282b4323bf965676a68b5326f2edbbdee35606b987412d351de137b82d50fe63",
            evidence["artifacts/rom-battle-controller-cfg-v1/manifest.json"],
        )
        self.assertEqual(
            "4aa979aa65408163e577f7d728ba32a99a13bd6c9615c40f28a570036e5ba275",
            evidence["artifacts/rom-cfg-proven-roots-v3/manifest.json"],
        )
        self.assertEqual(
            "e306ac59b4b9a815702fda8aef54058908fb9113a5afad4be938c69d42d67404",
            evidence["artifacts/rom-cfg-proven-roots-v4/manifest.json"],
        )
        self.assertEqual(
            "f6deb37d40ae4ea83e220adc8303c64646a9280d34d6c325d8ea0492963dcd8d",
            evidence["artifacts/rom-cfg-proven-roots-v5/manifest.json"],
        )
        self.assertEqual(
            "e00d8a1b7b08305a44f7ac3d36a5e294d1f69b5f05ceab151e14749cf92802f4",
            evidence["artifacts/rom-cfg-proven-roots-v6/manifest.json"],
        )
        self.assertEqual(
            "da9a1b5fe7ce8e7889fbba9fe8251c907ed18f6b273cbcc3be145101ece99114",
            evidence["artifacts/rom-cfg-proven-roots-v7/manifest.json"],
        )
        self.assertEqual(
            "0c9194507c50b7f2c00c6ee09b517211f64b7b344475952fe3c908b1e54e0002",
            evidence["artifacts/rom-cfg-proven-roots-v8/manifest.json"],
        )
        v8_manifest = json.loads(
            (ROOT / "artifacts/rom-cfg-proven-roots-v8/manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            "5fa1150d2ed9f785d50132a9eae316af192d70838fbee3061d7d3010c35fb1d6",
            v8_manifest["files"]["rom-cfg-proven-roots-v8.json"]["sha256"],
        )
        self.assertEqual(
            "1914d6244ceaa7791cb4c77d97143151b4f28183ea857c052c9c51d3c8a09e6b",
            evidence["artifacts/rom-cfg-proven-roots-v9/manifest.json"],
        )
        v9_manifest = json.loads(
            (ROOT / "artifacts/rom-cfg-proven-roots-v9/manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            "fb961c6d0ba5cdb56c016a5d10b149d87e5ce9158bcb1e6e9deae8664c46555b",
            v9_manifest["files"]["rom-cfg-proven-roots-v9.json"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        coverage_assertions = coverage["contract"]["assertions"]
        self.assertFalse(coverage_assertions["/semantic_classification_complete"])
        self.assertEqual(149_280, coverage_assertions["/summary/unknown_bytes"])
        self.assertEqual(6_142_176, coverage_assertions["/summary/classified_bytes"])
        self.assertEqual(15_940, coverage_assertions["/summary/claim_count"])
        self.assertEqual(17_344, coverage_assertions["/summary/segment_count"])
        self.assertEqual(
            "rom-positions-aux-dispatch-v1",
            coverage_assertions["/summary/positions_aux_dispatch_promotion_batch"],
        )
        self.assertEqual(
            "positions_aux_dispatch_cell_table_bytes",
            coverage_assertions["/summary/positions_aux_dispatch_claim_kind"],
        )
        self.assertEqual(
            9_216, coverage_assertions["/summary/positions_aux_dispatch_bytes"]
        )
        self.assertEqual(
            144, coverage_assertions["/summary/positions_aux_dispatch_claim_count"]
        )
        self.assertEqual(
            "47d995f09d6aaafcc4f4b4f88e3fbe81c2c4e0ea48ff10048674f1dbf6847d68",
            coverage_assertions[
                "/summary/positions_aux_dispatch_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "rom-cutscene-obj-palette-definition-alignment-gap-coverage-v1",
            coverage_assertions[
                "/summary/cutscene_obj_alignment_gap_promotion_batch"
            ],
        )
        self.assertEqual(
            "cutscene_obj_palette_definition_alignment_gap_bytes",
            coverage_assertions[
                "/summary/cutscene_obj_alignment_gap_claim_kind"
            ],
        )
        self.assertEqual(
            8,
            coverage_assertions["/summary/cutscene_obj_alignment_gap_bytes"],
        )
        self.assertEqual(
            4,
            coverage_assertions[
                "/summary/cutscene_obj_alignment_gap_claim_count"
            ],
        )
        self.assertEqual(
            "dae7c87fa52a1e1e9f1a72279fc7839d8f26f07b126e80aca07450286abcc137",
            coverage_assertions[
                "/summary/cutscene_obj_alignment_gap_claim_denominator_sha256"
            ],
        )
        self.assertEqual(
            "374c247199713cc2e172ebff551ae7a5e40df4289437f45cf76c814e84bed5e6",
            coverage_assertions[
                "/summary/cutscene_obj_alignment_gap_range_vector_sha256"
            ],
        )
        self.assertEqual(
            "af5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc",
            coverage_assertions[
                "/summary/cutscene_obj_alignment_gap_packed_bytes_sha256"
            ],
        )
        self.assertEqual(
            "c89ed50357f1497139aa81bc29e4b67c5947608c640fc572f0ff66ed01dd8f41",
            coverage_assertions[
                "/summary/cutscene_obj_alignment_gap_independent_verifier_report_sha256"
            ],
        )
        self.assertEqual(
            "rom-boot-interwork-padding-coverage-v1",
            coverage_assertions[
                "/summary/boot_interwork_padding_promotion_batch"
            ],
        )
        self.assertEqual(
            "boot_interwork_veneer_alignment_nop_bytes",
            coverage_assertions["/summary/boot_interwork_padding_claim_kind"],
        )
        self.assertEqual(
            2, coverage_assertions["/summary/boot_interwork_padding_bytes"]
        )
        self.assertEqual(
            1,
            coverage_assertions[
                "/summary/boot_interwork_padding_claim_count"
            ],
        )
        self.assertEqual(
            "639f595e03eb779de859b21c42fb77388cd5a93c26be5514b7c1f700fe1d09b9",
            coverage_assertions[
                "/summary/boot_interwork_padding_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "3e39ed78e50103716c788d4147df413950e5eba73c6e33acd923f15865795676",
            coverage_assertions[
                "/summary/boot_interwork_padding_packed_bytes_sha256"
            ],
        )
        self.assertEqual(
            "rom-dialogue-font-sjis-empty-lookup-rows-coverage-v1",
            coverage_assertions[
                "/summary/dialogue_font_sjis_empty_lookup_rows_promotion_batch"
            ],
        )
        self.assertEqual(
            "dialogue_font_sjis_empty_lookup_row_bytes",
            coverage_assertions[
                "/summary/dialogue_font_sjis_empty_lookup_rows_claim_kind"
            ],
        )
        self.assertEqual(
            40,
            coverage_assertions[
                "/summary/dialogue_font_sjis_empty_lookup_rows_bytes"
            ],
        )
        self.assertEqual(
            1,
            coverage_assertions[
                "/summary/dialogue_font_sjis_empty_lookup_rows_claim_count"
            ],
        )
        self.assertEqual(
            "000c60331b7d3e7da1c3597ac8ef3578b5f99a4cc24c811b5be5b38a079a676f",
            coverage_assertions[
                "/summary/dialogue_font_sjis_empty_lookup_rows_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "2c34ce1df23b838c5abf2a7f6437cca3d3067ed509ff25f11df6b11b582b51eb",
            coverage_assertions[
                "/summary/dialogue_font_sjis_empty_lookup_rows_packed_bytes_sha256"
            ],
        )
        self.assertEqual(
            "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1",
            coverage_assertions[
                "/summary/dialogue_font_sjis_empty_lookup_rows_full_table_sha256"
            ],
        )
        self.assertEqual(
            "rom-motion-spawn-sequence-descriptor-alignment-gap-coverage-v1",
            coverage_assertions[
                "/summary/motion_spawn_sequence_alignment_gap_promotion_batch"
            ],
        )
        self.assertEqual(
            "motion_spawn_sequence_descriptor_alignment_gap_bytes",
            coverage_assertions[
                "/summary/motion_spawn_sequence_alignment_gap_claim_kind"
            ],
        )
        self.assertEqual(
            2,
            coverage_assertions[
                "/summary/motion_spawn_sequence_alignment_gap_bytes"
            ],
        )
        self.assertEqual(
            1,
            coverage_assertions[
                "/summary/motion_spawn_sequence_alignment_gap_claim_count"
            ],
        )
        self.assertEqual(
            "6646067a0bc46bcc6c2fde5aa94299022ac51d7454b946048e51d929b0a58d03",
            coverage_assertions[
                "/summary/motion_spawn_sequence_alignment_gap_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "d1793f9c19b046ff1f431f28da31518c2093b77914b5c1f8b13f7e01d0ff1c6d",
            coverage_assertions[
                "/summary/motion_spawn_sequence_alignment_gap_motion_table_sha256"
            ],
        )
        self.assertEqual(
            "04d83157859089ee13c559a35bb6ab2f8814c71db59ee3f6616b917011428b9f",
            coverage_assertions[
                "/summary/motion_spawn_sequence_alignment_gap_sequence_table_sha256"
            ],
        )
        self.assertEqual(
            "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
            coverage_assertions[
                "/summary/motion_spawn_sequence_alignment_gap_packed_bytes_sha256"
            ],
        )
        self.assertEqual(
            "rom-battle-presentation-tile-assets-alignment-gap-coverage-v1",
            coverage_assertions[
                "/summary/battle_presentation_tile_assets_alignment_gap_promotion_batch"
            ],
        )
        self.assertEqual(
            "battle_presentation_tile_assets_alignment_gap_bytes",
            coverage_assertions[
                "/summary/battle_presentation_tile_assets_alignment_gap_claim_kind"
            ],
        )
        self.assertEqual(
            2,
            coverage_assertions[
                "/summary/battle_presentation_tile_assets_alignment_gap_bytes"
            ],
        )
        self.assertEqual(
            1,
            coverage_assertions[
                "/summary/battle_presentation_tile_assets_alignment_gap_claim_count"
            ],
        )
        self.assertEqual(
            "7649610dfb23720aa7a052893bf3fec739e423ddc826720e9cfa8529bea1882c",
            coverage_assertions[
                "/summary/battle_presentation_tile_assets_alignment_gap_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "8b5557e99d159b2b3ea1701bc0a15d0f2acc95f766003ec706263fc62a3719e8",
            coverage_assertions[
                "/summary/battle_presentation_tile_assets_alignment_gap_binding_table_sha256"
            ],
        )
        self.assertEqual(
            "0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73",
            coverage_assertions[
                "/summary/battle_presentation_tile_assets_alignment_gap_tile_assets_table_sha256"
            ],
        )
        self.assertEqual(
            "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
            coverage_assertions[
                "/summary/battle_presentation_tile_assets_alignment_gap_packed_bytes_sha256"
            ],
        )
        self.assertEqual(
            "rom-runtime-state-handler-table-alignment-gap-coverage-v1",
            coverage_assertions[
                "/summary/runtime_state_handler_table_alignment_gap_promotion_batch"
            ],
        )
        self.assertEqual(
            "runtime_state_handler_table_alignment_gap_bytes",
            coverage_assertions[
                "/summary/runtime_state_handler_table_alignment_gap_claim_kind"
            ],
        )
        self.assertEqual(
            2,
            coverage_assertions[
                "/summary/runtime_state_handler_table_alignment_gap_bytes"
            ],
        )
        self.assertEqual(
            1,
            coverage_assertions[
                "/summary/runtime_state_handler_table_alignment_gap_claim_count"
            ],
        )
        self.assertEqual(
            "11a9249d8cf1654cfbfa44bf13fa9fafc94677f7f1b075b892319e5e524f275c",
            coverage_assertions[
                "/summary/runtime_state_handler_table_alignment_gap_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "4c1ad8b8ac883eb301132c83258ba1e1216b2e131c9ce9866d0de62956d5a01b",
            coverage_assertions[
                "/summary/runtime_state_handler_table_alignment_gap_selector_table_sha256"
            ],
        )
        self.assertEqual(
            "20e4727cf65dca82626ffc9637cb36561d5851971500b22a282c5a8c65c7c945",
            coverage_assertions[
                "/summary/runtime_state_handler_table_alignment_gap_handler_table_sha256"
            ],
        )
        self.assertEqual(
            "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
            coverage_assertions[
                "/summary/runtime_state_handler_table_alignment_gap_packed_bytes_sha256"
            ],
        )
        self.assertEqual(
            "rom-direct-cpuset-bound-palette-coverage-v1",
            coverage_assertions[
                "/summary/direct_cpuset_bound_palette_promotion_batch"
            ],
        )
        self.assertEqual(
            "direct_cpuset_bound_palette_source_range",
            coverage_assertions["/summary/direct_cpuset_bound_palette_claim_kind"],
        )
        self.assertEqual(
            192,
            coverage_assertions["/summary/direct_cpuset_bound_palette_bytes"],
        )
        self.assertEqual(
            6,
            coverage_assertions[
                "/summary/direct_cpuset_bound_palette_claim_count"
            ],
        )
        self.assertEqual(
            12,
            coverage_assertions[
                "/summary/direct_cpuset_bound_palette_candidate_count"
            ],
        )
        self.assertEqual(
            6,
            coverage_assertions[
                "/summary/direct_cpuset_bound_palette_preowned_count"
            ],
        )
        self.assertEqual(
            "37ea9a17c34454a25866f790eb26b72d4b40b7a7a663b7f15366a6e3ad7fcf1f",
            coverage_assertions[
                "/summary/direct_cpuset_bound_palette_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "2381d20aeadf065b45306538b729c5b5ceecf41edcb4bbd6f3c40070a495607e",
            coverage_assertions[
                "/summary/direct_cpuset_bound_palette_candidate_denominator_sha256"
            ],
        )
        self.assertEqual(
            "4a03b75179c008e012ed89e2b571f052bd326a22cc2f1c5ae8fd82b073348225",
            coverage_assertions[
                "/summary/direct_cpuset_bound_palette_preowned_denominator_sha256"
            ],
        )
        self.assertEqual(
            "056a3625cc3a6735e56921aaec6ee37e646380bf31040cb6ad63fa8dbe757b70",
            coverage_assertions[
                "/summary/direct_cpuset_bound_palette_packed_bytes_sha256"
            ],
        )
        self.assertEqual(
            "selector-direct-source-records-v1",
            coverage_assertions[
                "/summary/selector_direct_source_record_promotion_batch"
            ],
        )
        self.assertEqual(
            920,
            coverage_assertions["/summary/selector_direct_source_record_bytes"],
        )
        self.assertEqual(
            46,
            coverage_assertions[
                "/summary/selector_direct_source_record_claim_count"
            ],
        )
        self.assertEqual(
            "a4fb31202d48f65f839217585495c2dc40d29cc63b25ff7a3d5594673056e608",
            coverage_assertions[
                "/summary/selector_direct_source_record_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "rom-selector-code-windows-v1",
            coverage_assertions["/summary/selector_code_window_promotion_batch"],
        )
        self.assertEqual(
            "consumer_code_slice",
            coverage_assertions["/summary/selector_code_window_claim_kind"],
        )
        self.assertEqual(
            1_252, coverage_assertions["/summary/selector_code_window_bytes"]
        )
        self.assertEqual(
            19, coverage_assertions["/summary/selector_code_window_claim_count"]
        )
        self.assertEqual(
            "1a1e50479424dbd441bc81adeca3c7d9075dc1a8ca13869e94693a71e702563e",
            coverage_assertions[
                "/summary/selector_code_window_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "rom-menu-portrait-palette-inventory-v1",
            coverage_assertions[
                "/summary/menu_portrait_palette_promotion_batch"
            ],
        )
        self.assertEqual(
            "menu_portrait_palette_source_range",
            coverage_assertions["/summary/menu_portrait_palette_claim_kind"],
        )
        self.assertEqual(
            8_960, coverage_assertions["/summary/menu_portrait_palette_bytes"]
        )
        self.assertEqual(
            70,
            coverage_assertions["/summary/menu_portrait_palette_claim_count"],
        )
        self.assertEqual(
            "84e8b9f99a51f94e1b9e0b972d6458c883428443aa173a9f739beaf601b4e338",
            coverage_assertions[
                "/summary/menu_portrait_palette_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "rom-scene-visual-source-ranges-v1",
            coverage_assertions["/summary/scene_visual_source_promotion_batch"],
        )
        self.assertEqual(
            "scene_visual_source_range",
            coverage_assertions["/summary/scene_visual_source_claim_kind"],
        )
        self.assertEqual(
            3_257, coverage_assertions["/summary/scene_visual_source_bytes"]
        )
        self.assertEqual(
            29, coverage_assertions["/summary/scene_visual_source_claim_count"]
        )
        self.assertEqual(
            {
                "scene_visual_shared_obj_palette_bgr555": 64,
                "scene_visual_background_palette_bgr555": 2_304,
                "scene_visual_definition_records": 697,
                "scene_visual_animation_records": 192,
            },
            coverage_assertions["/summary/scene_visual_source_class_bytes"],
        )
        self.assertEqual(
            {
                "scene_visual_shared_obj_palette_bgr555": 2,
                "scene_visual_background_palette_bgr555": 9,
                "scene_visual_definition_records": 9,
                "scene_visual_animation_records": 9,
            },
            coverage_assertions[
                "/summary/scene_visual_source_class_claim_counts"
            ],
        )
        self.assertEqual(
            "13dc504bebbff131700bb77869afb29e98a2f032d60bab4165eba90bcb2be7df",
            coverage_assertions[
                "/summary/scene_visual_source_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "rom-cutscene-obj-source-ranges-v1",
            coverage_assertions["/summary/cutscene_obj_source_promotion_batch"],
        )
        self.assertEqual(
            "cutscene_obj_source_range",
            coverage_assertions["/summary/cutscene_obj_source_claim_kind"],
        )
        self.assertEqual(
            400, coverage_assertions["/summary/cutscene_obj_source_bytes"]
        )
        self.assertEqual(
            28, coverage_assertions["/summary/cutscene_obj_source_claim_count"]
        )
        self.assertEqual(
            {
                "cutscene_obj_definition_records": 240,
                "cutscene_obj_definition_pointer_table": 40,
                "cutscene_obj_animation_timeline": 80,
                "cutscene_obj_animation_pointer_table": 40,
            },
            coverage_assertions["/summary/cutscene_obj_source_class_bytes"],
        )
        self.assertEqual(
            {
                "cutscene_obj_definition_records": 10,
                "cutscene_obj_definition_pointer_table": 4,
                "cutscene_obj_animation_timeline": 10,
                "cutscene_obj_animation_pointer_table": 4,
            },
            coverage_assertions[
                "/summary/cutscene_obj_source_class_claim_counts"
            ],
        )
        self.assertEqual(
            "c332e0ded3ae305162f774ffe1dfbbc5bbda14b534f5dd87b4f368337b8fb5a8",
            coverage_assertions[
                "/summary/cutscene_obj_source_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            25_284, coverage_assertions["/summary/consumer_code_slice_bytes"]
        )
        self.assertEqual(
            111, coverage_assertions["/summary/consumer_code_slice_claim_count"]
        )
        self.assertEqual(
            "referenced-text-slot-padding-v1",
            coverage_assertions[
                "/summary/referenced_text_slot_padding_promotion_batch"
            ],
        )
        self.assertEqual(
            1_255,
            coverage_assertions["/summary/referenced_text_slot_padding_bytes"],
        )
        self.assertEqual(
            133,
            coverage_assertions[
                "/summary/referenced_text_slot_padding_claim_count"
            ],
        )
        self.assertEqual(
            {
                "chapter_speaker_label_slot_zero_padding": 337,
                "selector_configured_text_slot_zero_padding": 368,
                "selector_direct_text_slot_zero_padding": 550,
            },
            coverage_assertions[
                "/summary/referenced_text_slot_padding_class_bytes"
            ],
        )
        self.assertEqual(
            {
                "chapter_speaker_label_slot_zero_padding": 49,
                "selector_configured_text_slot_zero_padding": 38,
                "selector_direct_text_slot_zero_padding": 46,
            },
            coverage_assertions[
                "/summary/referenced_text_slot_padding_class_claim_counts"
            ],
        )
        self.assertEqual(
            "0d565762f2bdfd18a6aa1f8c8cd25da5347da5184fe1c78e37de9c6334259b5a",
            coverage_assertions[
                "/summary/referenced_text_slot_padding_range_denominator_sha256"
            ],
        )
        self.assertEqual(956, coverage_assertions["/summary/cfg_reachable_arm_code_bytes"])
        self.assertEqual(148_778, coverage_assertions["/summary/cfg_reachable_thumb_code_bytes"])
        self.assertEqual(149_766, coverage_assertions["/summary/cfg_promoted_unknown_bytes"])
        self.assertEqual(3_835, coverage_assertions["/summary/cfg_primary_claim_count"])
        self.assertEqual(33, coverage_assertions["/summary/cfg_code_claim_kind_count"])
        self.assertEqual(
            "0874b75882eac082ff880b7ecca68f15b5f51972acc42b6d759f75b09f05448f",
            coverage_assertions["/summary/cfg_code_claim_kind_denominator_sha256"],
        )
        self.assertEqual(1_720, coverage_assertions["/summary/sprite_definition_resolved_window_bytes"])
        self.assertEqual(3, coverage_assertions["/summary/sprite_definition_resolved_window_claim_count"])
        self.assertEqual(25_926, coverage_assertions["/summary/cfg_proven_roots_v6_extension_code_bytes"])
        self.assertEqual(2_212, coverage_assertions["/summary/cfg_proven_roots_v6_extension_code_claim_count"])
        self.assertEqual(332, coverage_assertions["/summary/cfg_proven_roots_v7_extension_code_bytes"])
        self.assertEqual(38, coverage_assertions["/summary/cfg_proven_roots_v7_extension_code_claim_count"])
        self.assertEqual(246, coverage_assertions["/summary/cfg_proven_roots_v8_extension_code_bytes"])
        self.assertEqual(20, coverage_assertions["/summary/cfg_proven_roots_v8_extension_code_claim_count"])
        self.assertEqual(628, coverage_assertions["/summary/cfg_proven_roots_v9_extension_code_bytes"])
        self.assertEqual(62, coverage_assertions["/summary/cfg_proven_roots_v9_extension_code_claim_count"])
        self.assertEqual(
            32,
            coverage_assertions[
                "/summary/cfg_v3_sparse_dispatch_masked_residual_bytes"
            ],
        )
        self.assertEqual(
            8,
            coverage_assertions[
                "/summary/cfg_v3_sparse_dispatch_masked_residual_claim_count"
            ],
        )
        self.assertEqual(
            "f12097bd30174bd08f177f083fd886995edbdfc05de91c178b2d5ee96a65f9a5",
            coverage_assertions[
                "/summary/cfg_v3_sparse_dispatch_masked_residual_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            36,
            coverage_assertions[
                "/summary/cfg_proven_roots_v7_dispatch_table_bytes"
            ],
        )
        self.assertEqual(
            9,
            coverage_assertions[
                "/summary/cfg_proven_roots_v7_dispatch_table_claim_count"
            ],
        )
        self.assertEqual(
            "f01bf5984428f386feeed6b009913a5775ee6f23d41101a3ea423fb4047c6e9d",
            coverage_assertions[
                "/summary/cfg_proven_roots_v7_dispatch_table_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "rom-parser-bound-zero-padding-v1",
            coverage_assertions[
                "/summary/parser_bound_zero_padding_promotion_batch"
            ],
        )
        self.assertEqual(
            198,
            coverage_assertions["/summary/parser_bound_zero_padding_bytes"],
        )
        self.assertEqual(
            142,
            coverage_assertions[
                "/summary/parser_bound_zero_padding_claim_count"
            ],
        )
        self.assertEqual(
            "936959996300e6971bf0afa70ebe8fa116bb57c92a824b710daa91cd5b08a4c1",
            coverage_assertions[
                "/summary/parser_bound_zero_padding_range_denominator_sha256"
            ],
        )
        self.assertEqual(12_431, coverage_assertions["/summary/renderer_text_zero_padding_bytes"])
        self.assertEqual(6_738, coverage_assertions["/summary/fixed_consumer_text_zero_padding_bytes"])
        self.assertEqual(2_848, coverage_assertions["/summary/dialogue_font_source_padding_bytes"])
        self.assertEqual(648, coverage_assertions["/summary/lz77_alignment_padding_bytes"])
        self.assertEqual(1_293, coverage_assertions["/summary/battle_presentation_text_padding_bytes"])
        self.assertEqual(
            "battle-effect-sprite-animation-source-v1",
            coverage_assertions[
                "/summary/battle_effect_sprite_source_promotion_batch"
            ],
        )
        self.assertEqual(
            "battle_effect_sprite_animation_source_range",
            coverage_assertions[
                "/summary/battle_effect_sprite_source_claim_kind"
            ],
        )
        self.assertEqual(
            11_120,
            coverage_assertions["/summary/battle_effect_sprite_source_bytes"],
        )
        self.assertEqual(
            237,
            coverage_assertions[
                "/summary/battle_effect_sprite_source_claim_count"
            ],
        )
        self.assertEqual(
            {
                "battle_effect_sprite_component_records": 9_452,
                "battle_effect_sprite_definition_pointer_table": 712,
                "battle_effect_sprite_animation_timeline": 864,
                "battle_effect_sprite_animation_pointer_table": 92,
            },
            coverage_assertions[
                "/summary/battle_effect_sprite_source_class_bytes"
            ],
        )
        self.assertEqual(
            {
                "battle_effect_sprite_component_records": 178,
                "battle_effect_sprite_definition_pointer_table": 18,
                "battle_effect_sprite_animation_timeline": 23,
                "battle_effect_sprite_animation_pointer_table": 18,
            },
            coverage_assertions[
                "/summary/battle_effect_sprite_source_class_claim_counts"
            ],
        )
        self.assertEqual(
            "c30b25fbed4a80914e8bc9e8d33ec7545e47a01a005866460323ac8c9b84ba30",
            coverage_assertions[
                "/summary/battle_effect_sprite_source_claim_denominator_sha256"
            ],
        )
        self.assertEqual(
            3_919,
            coverage_assertions["/summary/verified_artifact_reuse_bytes"],
        )
        self.assertEqual(
            37,
            coverage_assertions[
                "/summary/verified_artifact_reuse_claim_count"
            ],
        )
        selector_source_verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1]
            == "tools/verify_rom_selector_direct_source_records.py"
        )
        self.assertEqual(
            [
                "python3",
                "tools/verify_rom_selector_direct_source_records.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-selector-direct-source-records-v1",
            ],
            selector_source_verifier["command"],
        )
        self.assertEqual(
            "510835b5d104f0009df09e3c8200beaefcb4f01836c40db7d3b1c11b475052d1",
            selector_source_verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-selector-direct-source-records-verification-v1",
                "/artifact_schema": "rom-selector-direct-source-records-v1",
                "/verified": True,
                "/errors": [],
                "/record_count": 46,
                "/record_bytes": 920,
                "/bundle_sha256": "a11475d1eea2ce15968ac2dc52addabcfa59354ccf80b702f922e2af548a4b56",
                "/record_vector_sha256": "065fca6237d166557a03cf30ddd309f695b825f5c850356a3c736e396d9478db",
            },
            selector_source_verifier["contract"]["assertions"],
        )
        slot_padding_verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1]
            == "tools/verify_rom_referenced_text_slot_padding.py"
        )
        self.assertEqual(
            [
                "python3",
                "tools/verify_rom_referenced_text_slot_padding.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-referenced-text-slot-padding-v1",
            ],
            slot_padding_verifier["command"],
        )
        self.assertEqual(
            "0f206e51b0fc151de7d6c875fe24ca338aa36dc77c963d50b4b59bdb62b40d5b",
            slot_padding_verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-referenced-text-slot-padding-verification-v1",
                "/artifact_schema": "rom-referenced-text-slot-padding-v1",
                "/verified": True,
                "/errors": [],
                "/padding_range_count": 133,
                "/padding_bytes": 1_255,
                "/zero_byte_count": 1_255,
                "/packed_bytes": 1_255,
                "/range_overlap_bytes": 0,
                "/bundle_sha256": "920b0cbd31dee627e4e6f4cd4d7805da10ec58ec47d4be3cb4a2dfc98a3b442b",
                "/group_summaries": {
                    "chapter_speaker": {
                        "packed_sha256": "3ad337042948f15072caf3da89730e6cc6d42657af2b2291806c4fd45ee1aae6",
                        "padding_bytes": 337,
                        "range_count": 49,
                        "range_denominator_sha256": "c2bdff7dad49f5446929b17b0a7fe6d5cd5a2a696c2ab091c5cebcd546912f16",
                    },
                    "selector_configured": {
                        "packed_sha256": "71818ecc26433c32172dd9a3544657971c7078daa2257da7c3c303e08693cb23",
                        "padding_bytes": 368,
                        "range_count": 38,
                        "range_denominator_sha256": "326f4c14065664e689b9c8245a931beb0a647241874a78953dfbc7dfcc2dddf3",
                    },
                    "selector_direct": {
                        "packed_sha256": "25778f162c4243167f8eaa876f1b0619e67afc158de7805600471a563ec5e8b7",
                        "padding_bytes": 550,
                        "range_count": 46,
                        "range_denominator_sha256": "647695b786a07f4c226bbad80246b0101d503eeb11912d71da500593812bb023",
                    },
                },
            },
            slot_padding_verifier["contract"]["assertions"],
        )
        padding_verifiers = {
            item["command"][1]: item
            for item in gate["verifiers"]
            if item["command"][1]
            in {
                "tools/verify_rom_renderer_text_padding.py",
                "tools/verify_rom_fixed_consumer_text_padding.py",
                "tools/verify_dialogue_font_source_padding.py",
                "tools/verify_rom_lz77_alignment_padding.py",
                "tools/verify_battle_presentation_text_padding.py",
            }
        }
        self.assertEqual(
            {
                "tools/verify_rom_renderer_text_padding.py",
                "tools/verify_rom_fixed_consumer_text_padding.py",
                "tools/verify_dialogue_font_source_padding.py",
                "tools/verify_rom_lz77_alignment_padding.py",
                "tools/verify_battle_presentation_text_padding.py",
            },
            set(padding_verifiers),
        )
        self.assertEqual(
            548,
            padding_verifiers["tools/verify_rom_renderer_text_padding.py"]
            ["contract"]["assertions"]["/padding_range_count"],
        )
        self.assertEqual(
            590,
            padding_verifiers[
                "tools/verify_rom_fixed_consumer_text_padding.py"
            ]["contract"]["assertions"]["/padding_range_count"],
        )
        self.assertEqual(
            19,
            padding_verifiers["tools/verify_dialogue_font_source_padding.py"]
            ["contract"]["assertions"]["/padding_range_count"],
        )
        self.assertEqual(
            341,
            padding_verifiers["tools/verify_rom_lz77_alignment_padding.py"]
            ["contract"]["assertions"]["/padding_range_count"],
        )
        self.assertEqual(
            78,
            padding_verifiers[
                "tools/verify_battle_presentation_text_padding.py"
            ]["contract"]["assertions"]["/padding_range_count"],
        )
        self.assertEqual(
            110,
            coverage_assertions[
                "/summary/cfg_proven_roots_v3_extension_code_bytes"
            ],
        )
        self.assertEqual(
            8,
            coverage_assertions[
                "/summary/cfg_proven_roots_v3_extension_code_claim_count"
            ],
        )
        self.assertEqual(
            1_044,
            coverage_assertions[
                "/summary/cfg_proven_roots_v4_extension_code_bytes"
            ],
        )
        self.assertEqual(
            118,
            coverage_assertions[
                "/summary/cfg_proven_roots_v4_extension_code_claim_count"
            ],
        )

        controller = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/verify_rom_battle_controller_cfg.py"
        )
        self.assertEqual(
            [
                "python3",
                "tools/verify_rom_battle_controller_cfg.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-battle-controller-cfg-v1",
            ],
            controller["command"],
        )
        self.assertEqual(
            "fc3c33d37b9fb2af885324915f82e3c0da74b3efd25967b8289b49d8b9169a87",
            controller["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-battle-controller-cfg-verification-v1",
                "/verified": True,
                "/errors": [],
                "/controller_range": [0x732B4, 0x7509C],
                "/controller_sha256": "c9bdc220590a851fa331960bcb32be90eb9ac7248a5cd3dabb9f8afa0b674bc1",
                "/dispatcher_nondefault_state_count": 38,
                "/dispatcher_default_state_count": 65_498,
                "/root_count": 38,
                "/summary/decoded_basic_block_count": 739,
                "/summary/decoded_instruction_count": 2_756,
                "/summary/frontier_count": 5,
                "/summary/frontier_reasons": {
                    "decode_failure": 1,
                    "indirect_pc_target": 2,
                    "unsupported_armv4t_instruction": 2,
                },
                "/summary/reachable_instruction_bytes": 6_172,
                "/summary/opaque_external_edge_count": 227,
                "/summary/opaque_baseline_edge_count": 9,
                "/summary/skipped_root_count": 1,
            },
            controller["contract"]["assertions"],
        )

        v3 = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/verify_rom_cfg_proven_roots_v3.py"
        )
        self.assertEqual(
            "15b06ae23285d397244ce49d153e3c4b93305af8d5a0b2dd81abe3b3655f5250",
            v3["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-cfg-proven-roots-verification-v3",
                "/verified": True,
                "/errors": [],
                "/control_flow_oracle": "armv4t-raw-encoding",
                "/independently_rebuilt_instruction_count": 52,
                "/root_count": 1,
                "/decoded_instruction_count": 52,
                "/decoded_basic_block_count": 8,
                "/reachable_instruction_bytes": 110,
                "/frontier_count": 0,
                "/baseline_cross_edge_count": 5,
            },
            v3["contract"]["assertions"],
        )

        v4 = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/verify_rom_cfg_proven_roots_v4.py"
        )
        self.assertEqual(
            "2520457a4862c628f86a236529d0d29fa227212b8b526e42f301b8f89a9606ba",
            v4["script_sha256"],
        )
        self.assertEqual(486, v4["contract"]["assertions"]["/decoded_instruction_count"])
        self.assertEqual(1_044, v4["contract"]["assertions"]["/reachable_instruction_bytes"])
        self.assertEqual(6, v4["contract"]["assertions"]["/frontier_count"])
        v5 = next(item for item in gate["verifiers"] if item["command"][1] == "tools/verify_rom_cfg_proven_roots_v5.py")
        self.assertEqual("ec188e5e674b87a1cdda4fa6848d6fe5a2d9fb0617ea6d818be43237d05997f9", v5["script_sha256"])
        self.assertEqual(1_252, v5["contract"]["assertions"]["/reachable_instruction_bytes"])
        v6 = next(item for item in gate["verifiers"] if item["command"][1] == "tools/verify_rom_cfg_proven_roots_v6.py")
        self.assertEqual("4fc2ad61b98ce3655f1528e773566f63f84f1184209086bd96d3e23c51a8ceb4", v6["script_sha256"])
        self.assertEqual(27_224, v6["contract"]["assertions"]["/reachable_instruction_bytes"])
        self.assertEqual(85, v6["contract"]["assertions"]["/frontier_count"])
        v7 = next(item for item in gate["verifiers"] if item["command"][1] == "tools/verify_rom_cfg_proven_roots_v7.py")
        self.assertEqual("30e67f172e8a34c85e93838bd7863f1d1417823c83b1cf2a74fa8cd61aae01a5", v7["script_sha256"])
        self.assertEqual(332, v7["contract"]["assertions"]["/reachable_instruction_bytes"])
        self.assertEqual(1, v7["contract"]["assertions"]["/frontier_count"])
        v8 = next(
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_cfg_proven_roots_v8.py" in item["command"]
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_cfg_proven_roots_v8.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-cfg-proven-roots-v8",
            ],
            v8["command"],
        )
        self.assertEqual("88d2726fbe2657105759d23ae04f95ae2685ad2ad416640a8a5bbd2bb826b254", v8["script_sha256"])
        self.assertEqual(
            {
                "/schema": "rom-cfg-proven-roots-verification-v8",
                "/verified": True,
                "/errors": [],
                "/control_flow_oracle": "armv4t-raw-encoding",
                "/independently_rebuilt_instruction_count": 113,
                "/root_count": 1,
                "/decoded_instruction_count": 113,
                "/decoded_basic_block_count": 20,
                "/reachable_instruction_bytes": 246,
                "/frontier_count": 1,
                "/baseline_cross_edge_count": 10,
            },
            v8["contract"]["assertions"],
        )
        v9 = next(
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_cfg_proven_roots_v9.py" in item["command"]
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_cfg_proven_roots_v9.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-cfg-proven-roots-v9",
            ],
            v9["command"],
        )
        self.assertEqual(
            "b75ed5bad517fb08ebf2ae08d336c1dcee6ab334c4927559f41a2fcfad399935",
            v9["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-cfg-proven-roots-verification-v9",
                "/verified": True,
                "/errors": [],
                "/control_flow_oracle": "armv4t-raw-encoding",
                "/independently_rebuilt_instruction_count": 299,
                "/root_count": 8,
                "/decoded_instruction_count": 299,
                "/decoded_basic_block_count": 62,
                "/reachable_instruction_bytes": 628,
                "/frontier_count": 0,
                "/baseline_cross_edge_count": 16,
            },
            v9["contract"]["assertions"],
        )
        parser_bound = next(
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_parser_bound_zero_padding.py" in item["command"]
        )
        self.assertEqual(
            [
                "python3",
                "tools/verify_rom_parser_bound_zero_padding.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-parser-bound-zero-padding-v1",
            ],
            parser_bound["command"],
        )
        self.assertEqual(
            "18a67696b11da789d2871402dd829e98a85800633c2f3d4da9b4ccefeafff07d",
            parser_bound["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-parser-bound-zero-padding-verification-v1",
                "/verified": True,
                "/errors": [],
                "/accepted_range_count": 142,
                "/accepted_byte_count": 198,
                "/accepted_range_sha256": "936959996300e6971bf0afa70ebe8fa116bb57c92a824b710daa91cd5b08a4c1",
                "/accepted_bundle_sha256": "a6eab4025a7c9c0877549f6e5d790f66af88ee7f2320e814954e638d8051f812",
                "/rejected_range_count": 9,
                "/rejected_byte_count": 3_688,
                "/contract_excluded_range_count": 2,
                "/contract_excluded_byte_count": 5,
                "/m4a_structure_count": 62,
                "/chapter_structure_count": 89,
            },
            parser_bound["contract"]["assertions"],
        )
        commands = [item["command"] for item in gate["verifiers"]]
        story = next(
            item
            for item in gate["verifiers"]
            if "tools/verify_story_scene_timelines.py" in item["command"]
        )
        self.assertLess(commands.index(v8["command"]), commands.index(v9["command"]))
        self.assertLess(
            commands.index(v9["command"]), commands.index(parser_bound["command"])
        )
        self.assertLess(
            commands.index(parser_bound["command"]), commands.index(story["command"])
        )

    def test_current_spec_binds_selector_code_window_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "bb3f2588ad22567190c1084a12eca42a1615091bc335fe45788d2556299ba6c0",
            evidence["artifacts/rom-selector-code-windows-v1/manifest.json"],
        )
        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/verify_rom_selector_code_windows.py"
        )
        self.assertEqual(
            [
                "python3",
                "tools/verify_rom_selector_code_windows.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-selector-code-windows-v1",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "e9d8ea4cbe5aec14359b5c8ba74ac3e8182f0441a3014d3f760196242601665b",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-selector-code-windows-verification-v1",
                "/artifact_schema": "rom-selector-code-windows-v1",
                "/verified": True,
                "/errors": [],
                "/source_window_count": 10,
                "/source_window_bytes": 2_754,
                "/promotion_range_count": 19,
                "/promotion_bytes": 1_252,
                "/primary_overlap_bytes": 1_502,
                "/source_window_range_denominator_sha256": "c45e828631f019ea506b0b24a0efeb16ed8508377277bc27936e8a8932fa8d43",
                "/promotion_range_denominator_sha256": "1a1e50479424dbd441bc81adeca3c7d9075dc1a8ca13869e94693a71e702563e",
                "/full_bundle_sha256": "4c1d5865350a66b57db7b483f68c6bf97e9c88fcd5372f021358d4ad8c917523",
                "/promotion_bundle_sha256": "2207f28f0e2635b7cff09660d4440d5f8c926017583d210b748a34ac2639672b",
                "/bridge_promotion_count": 0,
                "/mapper_promotion_count": 0,
            },
            verifier["contract"]["assertions"],
        )

    def test_current_spec_binds_menu_portrait_palette_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "8a8675c2724131a6caa9b956825d74280fa26fe99447470b3cc3810688e6f88b",
            evidence[
                "artifacts/rom-menu-portrait-palette-inventory-v1/manifest.json"
            ],
        )
        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1]
            == "tools/verify_rom_menu_portrait_palette_inventory.py"
        )
        self.assertEqual(
            [
                "python3",
                "tools/verify_rom_menu_portrait_palette_inventory.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-menu-portrait-palette-inventory-v1",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "63d60ffe786841d910b0655de31cbb4a3d52178b433fc1a40b24729f683cda46",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-menu-portrait-palette-inventory-verification-v1",
                "/verified": True,
                "/errors": [],
                "/logical_output_count": 311,
                "/source_resource_count": 74,
                "/unique_palette_count": 70,
                "/alias_group_count": 1,
                "/aliased_resource_count": 5,
                "/palette_bytes": 8_960,
                "/packed_bytes": 8_960,
                "/range_overlap_bytes": 0,
                "/range_vector_sha256": "84e8b9f99a51f94e1b9e0b972d6458c883428443aa173a9f739beaf601b4e338",
                "/bundle_sha256": "d5d80e37d88000ec81501d9549b4c6038c42e6ec172614127821213d9dbcdccc",
            },
            verifier["contract"]["assertions"],
        )

    def test_current_spec_binds_scene_visual_source_range_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "d9440e4ea32db1ea51dc6d00bbb3788c9f79ea5b8d20d0e1444f9a3d07c22baf",
            evidence[
                "artifacts/rom-scene-visual-source-ranges-v1/manifest.json"
            ],
        )
        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1]
            == "tools/verify_rom_scene_visual_source_ranges.py"
        )
        self.assertEqual(
            [
                "python3",
                "tools/verify_rom_scene_visual_source_ranges.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-scene-visual-source-ranges-v1",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "91f55da0370db3ae291f0845812b610bf3e2bd71efd8acf8501af62201f9af87",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-scene-visual-source-ranges-verification-v1",
                "/artifact_schema": "rom-scene-visual-source-ranges-v1",
                "/verified": True,
                "/errors": [],
                "/bundle_sha256": "2eec5a820e1f79cc817e5976dc710e889adbee1038a4247652812a695832bc95",
                "/summary/source_record_count": 57,
                "/summary/source_bytes": 88_756,
                "/summary/candidate_range_count": 29,
                "/summary/candidate_bytes": 3_288,
                "/summary/candidate_class_counts": {
                    "shared_obj_palette": {"range_count": 2, "byte_count": 64},
                    "background_palette": {
                        "range_count": 9,
                        "byte_count": 2_304,
                    },
                    "definition": {"range_count": 9, "byte_count": 728},
                    "animation": {"range_count": 9, "byte_count": 192},
                },
                "/summary/overlap_range_count": 1,
                "/summary/overlap_bytes": 31,
                "/summary/promotion_range_count": 29,
                "/summary/promotion_bytes": 3_257,
                "/summary/promotion_bundle_sha256": "2eec5a820e1f79cc817e5976dc710e889adbee1038a4247652812a695832bc95",
            },
            verifier["contract"]["assertions"],
        )

    def test_current_spec_binds_cutscene_obj_source_range_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "a0e97ec43858a145a7c26dc71c5b89dfe8c4d9a5d6074ccad88c4ae56e03afd5",
            evidence[
                "artifacts/rom-cutscene-obj-source-ranges-v1/manifest.json"
            ],
        )
        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1]
            == "tools/verify_rom_cutscene_obj_source_ranges.py"
        )
        self.assertEqual(
            [
                "python3",
                "tools/verify_rom_cutscene_obj_source_ranges.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-cutscene-obj-source-ranges-v1",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "a1075b8885378fe2c26c1c262126ad8098bb81c171a805cb3e08ed0d8217c446",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-cutscene-obj-source-ranges-verification-v1",
                "/artifact_schema": "rom-cutscene-obj-source-ranges-v1",
                "/verified": True,
                "/errors": [],
                "/range_count": 28,
                "/byte_count": 400,
                "/bundle_sha256": "a8a881804ae016cfad1f031ac5b080cd51bb7823416ff48c7db4ed1ed4e48d8c",
                "/range_vector_sha256": "5ffcd048916c21a3cd46a7baf5421c2db7812a4c5cf0d73edd83efb9eb03ab43",
            },
            verifier["contract"]["assertions"],
        )

    def test_current_spec_binds_positions_aux_dispatch_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "d7e7a19c0d2d0e3d77f6db558bce53ef0333667fec9f36fa3687059dd83e8d5a",
            evidence[
                "artifacts/rom-positions-aux-dispatch-v1/manifest.json"
            ],
        )
        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1]
            == "tools/verify_rom_positions_aux_dispatch.py"
        )
        self.assertEqual(
            [
                "python3",
                "tools/verify_rom_positions_aux_dispatch.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-positions-aux-dispatch-v1",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "17cd6b6c969230de39f23b22273f5f3410f245a7151932f0754bd18abf352d66",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-positions-aux-dispatch-verification-v1",
                "/artifact_schema": "rom-positions-aux-dispatch-v1",
                "/verified": True,
                "/errors": [],
                "/summary/table_count": 144,
                "/summary/cell_count": 2_304,
                "/summary/byte_count": 9_216,
                "/summary/bytes_per_table": 64,
                "/summary/cells_per_table": 16,
                "/summary/cell_stride": 4,
                "/summary/nonzero_byte_count": 699,
                "/summary/nonzero_table_count": 71,
                "/range_list_sha256": "47d995f09d6aaafcc4f4b4f88e3fbe81c2c4e0ea48ff10048674f1dbf6847d68",
                "/packed_range_bytes_sha256": "ce2ce373f1699899739903532424f59e89184afa8cd37a527f0adc4ecc8c2c57",
                "/per_range_sha256_vector_sha256": "29bee47cef98715a027f5df0ce76c03c03d11dcbd7a84b225e50524e6215d8cb",
                "/non_claims": {
                    "abi_stability_claimed": False,
                    "all_cells_naturally_reached_claimed": False,
                    "all_tags_naturally_reached_claimed": False,
                    "all_variants_naturally_reachable_claimed": False,
                    "allocatable_space_claimed": False,
                    "byte1_common_semantics_claimed": False,
                    "byte2_common_semantics_claimed": False,
                    "byte3_common_semantics_claimed": False,
                    "byte3_globally_unused_claimed": False,
                    "byte3_padding_claimed": False,
                    "byte3_reserved_claimed": False,
                    "editing_safety_claimed": False,
                    "exhaustive_positions_aux_consumers_claimed": False,
                    "existing_position_record_extension_claimed": False,
                    "final_post_candidate_gap_claimed": False,
                    "free_space_claimed": False,
                    "next_variant_headers_claimed": False,
                    "runtime_group_bound_claimed": False,
                    "runtime_variant_bound_claimed": False,
                    "tag_business_semantics_claimed": False,
                    "writeback_or_relocation_safety_claimed": False,
                },
            },
            verifier["contract"]["assertions"],
        )

    def test_current_spec_binds_battle_sound_selector_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "eb30940a42f9d2c0e7ece5f18939eb4c0b1fbb06c9d51bc756ad853bc13d8807",
            evidence["artifacts/rom-battle-sound-selector-v1/manifest.json"],
        )
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )

        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/verify_rom_battle_sound_selector.py"
        )
        self.assertEqual(
            [
                "python3",
                "tools/verify_rom_battle_sound_selector.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-battle-sound-selector-v1",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "71cda2a30e111efce8cd4b6399e0c18d7c5891556eecd16dcfde0116a142204a",
            verifier["script_sha256"],
        )
        non_claims = {
            "all_battle_audio_exhausted_claimed": False,
            "all_direct_paths_naturally_reached_claimed": False,
            "all_indices_naturally_reached_claimed": False,
            "all_selector_consumers_exhausted_claimed": False,
            "allocatable_space_claimed": False,
            "computed_or_ram_consumers_exhausted_claimed": False,
            "editing_safety_claimed": False,
            "free_space_claimed": False,
            "index_to_gameplay_semantics_claimed": False,
            "left_neighbor_structure_claimed": False,
            "nonzero_value_business_semantics_claimed": False,
            "play_routine_full_behavior_claimed": False,
            "relocation_safety_claimed": False,
            "right_neighbor_business_relation_claimed": False,
            "sound_playback_success_claimed": False,
            "writeback_safety_claimed": False,
            "zero_value_business_semantics_claimed": False,
        }
        self.assertEqual(
            {
                "/schema": "rom-battle-sound-selector-verification-v1",
                "/artifact_schema": "rom-battle-sound-selector-v1",
                "/verified": True,
                "/errors": [],
                "/rom/path": "rom/base.gba",
                "/rom/size": 6_291_456,
                "/rom/sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "/selector_range": [0x53E496, 0x53E596],
                "/entry_count": 256,
                "/direct_literal_consumer_count": 5,
                "/non_claims": non_claims,
                "/scope/physical_selector_table_complete": True,
                "/scope/direct_literal_consumer_denominator_complete": True,
                "/scope/coverage_classification_performed": False,
            },
            verifier["contract"]["assertions"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        assertions = coverage["contract"]["assertions"]
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        self.assertEqual(149_280, assertions["/summary/unknown_bytes"])
        self.assertEqual(6_142_176, assertions["/summary/classified_bytes"])
        self.assertEqual(15_940, assertions["/summary/claim_count"])
        self.assertEqual(17_344, assertions["/summary/segment_count"])
        self.assertEqual(
            "rom-battle-sound-selector-v1",
            assertions["/summary/battle_sound_selector_promotion_batch"],
        )
        self.assertEqual(
            "battle_gameplay_sound_selector_table_bytes",
            assertions["/summary/battle_sound_selector_claim_kind"],
        )
        self.assertEqual(256, assertions["/summary/battle_sound_selector_bytes"])
        self.assertEqual(1, assertions["/summary/battle_sound_selector_claim_count"])
        self.assertEqual(
            "2f77582ae5eea1711b079fc8ce67d36e95ec68bf0e2bd0a3d5780eb3d9819b5d",
            assertions["/summary/battle_sound_selector_table_sha256"],
        )
        self.assertEqual(
            "fc3c1c03d918f173b304633d84fcbd8ead4448f5185d30d687c2ef352a3fcd62",
            assertions[
                "/summary/battle_sound_selector_entry_denominator_sha256"
            ],
        )

    def test_current_spec_binds_battle_condition_records_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "c9ea59da9e2f870446f51a0424317ca6dfb23daa67a348bb0a78093b86d3c079",
            evidence["artifacts/rom-battle-condition-records-v1/manifest.json"],
        )
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )

        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1]
            == "tools/verify_rom_battle_condition_records.py"
        )
        self.assertEqual(
            [
                "python3",
                "tools/verify_rom_battle_condition_records.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-battle-condition-records-v1",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "05402eea4f0ffd7871da74e8dc70613b4370c5c87ba6fe99bddcc4257914628e",
            verifier["script_sha256"],
        )
        non_claims = {
            "all_battle_conditions_semantically_named_claimed": False,
            "all_battle_ids_naturally_reached_claimed": False,
            "all_condition_consumers_exhausted_claimed": False,
            "all_predicate_slots_naturally_evaluated_claimed": False,
            "all_variant_indices_naturally_reached_claimed": False,
            "allocatable_space_claimed": False,
            "battlefield_object_visible_behavior_names_claimed": False,
            "byte3_field_semantics_claimed": False,
            "complete_objective_engine_claimed": False,
            "computed_or_ram_consumers_exhausted_claimed": False,
            "editing_safety_claimed": False,
            "existing_primary_owner_reclassification_claimed": False,
            "free_space_claimed": False,
            "handlers_4_5_naturally_used_claimed": False,
            "payload_word_business_semantics_claimed": False,
            "positions_condition_business_relation_claimed": False,
            "prefix_field_semantics_claimed": False,
            "prefix_padding_or_reserved_claimed": False,
            "relocation_safety_claimed": False,
            "right_gap_padding_claimed": False,
            "right_gap_structure_claimed": False,
            "runtime_trigger_coverage_claimed": False,
            "writeback_safety_claimed": False,
        }
        implementation = {
            "exporter": {
                "path": "tools/export_rom_battle_condition_records.py",
                "sha256": "707213deb2026f36b5badcf73c394fc9e1788c7141eb838f865ef241ae55d0ba",
            },
            "tests": {
                "path": "tests/test_export_rom_battle_condition_records.py",
                "sha256": "8a1a7ca42869ac31d2311837fc73eeb7ac792ca874a3678904a3e11d4c900464",
            },
            "verifier": {
                "path": "tools/verify_rom_battle_condition_records.py",
                "sha256": "05402eea4f0ffd7871da74e8dc70613b4370c5c87ba6fe99bddcc4257914628e",
            },
        }
        scope = {
            "complete_physical_table": True,
            "coverage_classification_performed": False,
            "non_claims": non_claims,
            "raw_interpreter_bound_layout": True,
        }
        self.assertEqual(
            {
                "/schema": "rom-battle-condition-records-verification-v1",
                "/artifact_schema": "rom-battle-condition-records-v1",
                "/verified": True,
                "/errors": [],
                "/rom": {
                    "path": "rom/base.gba",
                    "sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                    "size": 6_291_456,
                },
                "/table_file_range": [0x594758, 0x596CCC],
                "/variant_count": 141,
                "/predicate_slot_count": 1_128,
                "/consumer_interpreter_verified": True,
                "/implementation": implementation,
                "/non_claims": non_claims,
                "/scope": scope,
            },
            verifier["contract"]["assertions"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        assertions = coverage["contract"]["assertions"]
        expected_summary = {
            "/summary/unknown_bytes": 149_280,
            "/summary/classified_bytes": 6_142_176,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/battle_condition_records_promotion_batch": "rom-battle-condition-records-v1",
            "/summary/battle_condition_records_claim_kind": "battle_condition_record_current_unknown_fragment",
            "/summary/battle_condition_projected_unknown_bytes": 2_772,
            "/summary/battle_condition_projected_unknown_claim_count": 84,
            "/summary/battle_condition_prefix_fragment_bytes": 164,
            "/summary/battle_condition_prefix_fragment_claim_count": 41,
            "/summary/battle_condition_predicate_fragment_bytes": 2_608,
            "/summary/battle_condition_predicate_fragment_claim_count": 43,
            "/summary/battle_condition_prefix_fragment_range_denominator_sha256": "11275ecaa34b3e4d187efcb04aa59ae8911bfb0ba9d6a147df313cae376b941d",
            "/summary/battle_condition_prefix_fragment_packed_bytes_sha256": "eae9d28d7679ffbf2ab2dc851a67b2e3e1c4c6f0dceb8ab805cd0f7218ce8d8b",
            "/summary/battle_condition_predicate_fragment_range_denominator_sha256": "f61a404bc830e0f78916268876bb62238d3a2d55267df5af3beda39af0861dcc",
            "/summary/battle_condition_predicate_fragment_packed_bytes_sha256": "e31d7da27eca37808d6a5937025991c2cf59785d7633c81c7695c1dc8800d64b",
            "/summary/battle_condition_combined_fragment_range_denominator_sha256": "72fff4ac415bd154e643b2205064c53822209fb9eb0fe90a8243284e8f32f77f",
            "/summary/battle_condition_projected_range_denominator_sha256": "1b639baa06f56a6273327a2df2dc0ad2595535af6a08b47c9d8038378836544a",
            "/summary/battle_condition_projected_packed_bytes_sha256": "f63949e16d48a198983a61099bcf6f18d3b01980dea2a94bd9440ed8d9f49810",
            "/summary/battle_condition_records_table_sha256": "0d6e137011aa4e97c5b5d165f1939b7fb0b33235b9b20fceb1566b485dc35bf4",
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(expected, assertions[pointer], pointer)

        self.assertTrue(
            any(
                "2,772 current-unknown bytes" in limitation
                and "144-byte right-side zero gap" in limitation
                for limitation in gate["limitations"]
            )
        )

    def test_current_spec_binds_cutscene_obj_palette_definition_alignment_gap_verifier(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )
        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1]
            == "tools/verify_rom_cutscene_obj_palette_definition_alignment_gaps.py"
        )
        self.assertEqual(
            [
                "python3",
                "tools/verify_rom_cutscene_obj_palette_definition_alignment_gaps.py",
                "--root",
                ".",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "b78a8726b65e6079be8f2a2d332b082d87386987831a2e7d4354997969548823",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-cutscene-obj-palette-definition-alignment-gaps-verification-v1",
                "/verified": True,
                "/errors": [],
                "/rom/sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "/gap_count": 4,
                "/byte_count": 8,
                "/zero_byte_count": 8,
                "/left_lz_count": 4,
                "/right_definition_count": 4,
                "/ranges": [
                    [0x12DEFA, 0x12DEFC],
                    [0x12E442, 0x12E444],
                    [0x12E95E, 0x12E960],
                    [0x12ED6E, 0x12ED70],
                ],
                "/range_vector_sha256": "374c247199713cc2e172ebff551ae7a5e40df4289437f45cf76c814e84bed5e6",
                "/boundary_vector_sha256": "779dae0d0811b3cde7817d9de9c0c61c35e7d9c54e5d2f9ecfd99eb0a80b211d",
                "/packed_bytes_sha256": "af5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc",
                "/resource_table_sha256": "16b13c432f37ba159697cd9d9d6d5d5147adc41c44c8cc0cc44ce7f2935f1401",
                "/sprite_table_sha256": "1c76f2100b2067e78abd713e312bd845d7c874b030f51ef08f968961862e198a",
                "/combined_table_sha256": "1e6d5016b58d0e565c5a40791a7f2684d6129e0a1c4e85e79317af4d2b1a7f62",
                "/root_row_vector_sha256": "8a0ab99bbb46e1fa58a0413ffae366bd67a3660e5f947b043228858688899e2d",
                "/compressed_stream_sha256": "6bdf4b41b3d1b6240499cb68ceddb82a6e98267709f05d075bc64389956681c2",
                "/decoded_stream_sha256": "99d45ddc5929d60c150146f1292cd55f56d89afbff70ffd0f377128fe75352af",
                "/all_parser_endpoints_exact": True,
                "/all_alignment_equations_hold": True,
                "/non_claims": {
                    "all_cutscene_gaps_exhaustive_claimed": False,
                    "allocatable_space_claimed": False,
                    "compiler_authorship_claimed": False,
                    "definition_unknown_field_semantics_claimed": False,
                    "editing_safety_claimed": False,
                    "final_pixel_equivalence_claimed": False,
                    "free_space_claimed": False,
                    "generic_lz_alignment_rule_claimed": False,
                    "graphics_or_palette_expansion_claimed": False,
                    "lz_trailing_bytes_claimed": False,
                    "natural_runtime_reachability_claimed": False,
                    "runtime_consumes_padding_claimed": False,
                    "writeback_or_relocation_safety_claimed": False,
                },
            },
            verifier["contract"]["assertions"],
        )

    def test_current_spec_binds_mplaymain_scheduler_and_exact_coverage_delta(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}

        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        self.assertEqual(
            "43399803451c393722522c9d2a363736541c34c37dd03d3cb2c1e292ed0b8f5d",
            evidence["artifacts/rom-mplaymain-scheduler-v1/manifest.json"],
        )

        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][3]
            == "tools/verify_rom_mplaymain_scheduler_bundle.py"
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_mplaymain_scheduler_bundle.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-mplaymain-scheduler-v1",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "caa5e042401ed06f1f7e9978e10c5e487c643e909c50a274b75aed32ce557c06",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-mplaymain-scheduler-bundle-verification-v1",
                "/verified": True,
                "/errors": [],
                "/artifact_schema": "rom-mplaymain-scheduler-v1",
                "/artifact_status": "accepted",
                "/artifact_bundle_verified": True,
                "/legacy_receipt_verified": True,
                "/live_coverage_verified": False,
                "/rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "/promotion_bytes": 612,
                "/promotion_claim_count": 2,
                "/promotion_range_count": 2,
                "/promotion_packed_sha256": "8ca6a2f02cd27d46b9d0e9dbae2491672f23702ee2230eb73fc460759ef14955",
                "/unclassified_historical_bytes": 2,
                "/legacy_verifier_sha256": "c064fc6a576a518cbd825630babc40d1c2dab2d369846078c3950b68748a2c2a",
                "/bundle_verifier_sha256": "caa5e042401ed06f1f7e9978e10c5e487c643e909c50a274b75aed32ce557c06",
                "/summary/block_count": 81,
                "/summary/budget_exhausted": False,
                "/summary/code_bytes": 600,
                "/summary/external_edge_count": 12,
                "/summary/external_target_count": 7,
                "/summary/frontier_count": 1,
                "/summary/instruction_bytes": 600,
                "/summary/instruction_count": 289,
                "/summary/internal_edge_count": 117,
                "/summary/literal_bytes": 12,
                "/summary/literal_ref_count": 4,
                "/summary/literal_word_count": 3,
                "/summary/owned_indirect_veneer_count": 1,
                "/summary/owned_provenance_bytes": 2,
                "/summary/promoted_bytes": 612,
                "/summary/raw_indirect_pc_count": 0,
                "/summary/return_count": 1,
                "/summary/unclassified_unknown_bytes": 2,
                "/promotion/code_bytes": 600,
                "/promotion/code_range_count": 1,
                "/promotion/current_known_overlap_bytes": 0,
                "/promotion/future_coverage_claim_projection": {
                    "code_claim_count": 1,
                    "literal_claim_count": 1,
                    "owned_claim_count": 0,
                    "unclassified_claim_count": 0,
                },
                "/promotion/literal_bytes": 12,
                "/promotion/literal_range_count": 1,
                "/promotion/owned_provenance_bytes": 2,
                "/promotion/owned_provenance_ranges": [[632_452, 632_454]],
                "/promotion/projected_totals": {
                    "claim_count": 14_484,
                    "classified_bytes": 6_122_489,
                    "segment_count": 16_593,
                    "unknown_bytes": 168_967,
                },
                "/promotion/unclassified_unknown_bytes": 2,
                "/promotion/unclassified_unknown_ranges": [[632_454, 632_456]],
                "/promotion/union_bytes": 612,
                "/promotion/union_bytes_sha256": "8ca6a2f02cd27d46b9d0e9dbae2491672f23702ee2230eb73fc460759ef14955",
                "/promotion/union_range_count": 2,
                "/promotion/union_range_vector_sha256": "a8e11002ba5439c3d758e03faa1850a686e749cbe3230496f871329283300b4d",
                "/promotion/union_ranges": [
                    [631_852, 632_452],
                    [632_456, 632_468],
                ],
            },
            verifier["contract"]["assertions"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        assertions = coverage["contract"]["assertions"]
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/mplaymain_scheduler_promotion_batch": "rom-mplaymain-scheduler-v1",
            "/summary/mplaymain_scheduler_code_claim_kind": "mplaymain_scheduler_reachable_instruction_bytes",
            "/summary/mplaymain_scheduler_literal_claim_kind": "mplaymain_scheduler_consumed_literal_bytes",
            "/summary/mplaymain_scheduler_code_bytes": 600,
            "/summary/mplaymain_scheduler_code_claim_count": 1,
            "/summary/mplaymain_scheduler_literal_bytes": 12,
            "/summary/mplaymain_scheduler_literal_claim_count": 1,
            "/summary/mplaymain_scheduler_promoted_bytes": 612,
            "/summary/mplaymain_scheduler_promotion_claim_count": 2,
            "/summary/mplaymain_scheduler_owned_provenance_bytes": 2,
            "/summary/mplaymain_scheduler_owned_provenance_range_count": 1,
            "/summary/mplaymain_scheduler_gap_bytes": 2,
            "/summary/mplaymain_scheduler_gap_range_count": 1,
            "/summary/mplaymain_scheduler_union_range_count": 2,
            "/summary/mplaymain_scheduler_union_range_vector_sha256": "a8e11002ba5439c3d758e03faa1850a686e749cbe3230496f871329283300b4d",
            "/summary/mplaymain_scheduler_frontier_count": 1,
            "/summary/mplaymain_scheduler_return_count": 1,
            "/summary/mplaymain_scheduler_block_count": 81,
            "/summary/mplaymain_scheduler_external_edge_count": 12,
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(expected, assertions[pointer], pointer)

        self.assertTrue(
            any(
                "MPlayMain scheduler artifact classifies exactly 600 bounded Thumb instruction bytes"
                in limitation
                and "two bytes remain unknown" in limitation
                and "callback lifecycle" in limitation
                and "natural runtime reachability" in limitation
                for limitation in gate["limitations"]
            )
        )

    def test_current_spec_binds_soundmain_relocated_cfg_and_exact_coverage_delta(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}

        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        self.assertEqual(
            "e6b9a2cbdb439c520b5c98a422279e44e03866dbf1541810626d28eb57ce0a37",
            evidence["artifacts/rom-soundmain-relocated-cfg-v1/manifest.json"],
        )

        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][3]
            == "tools/verify_rom_soundmain_relocated_cfg_bundle.py"
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_soundmain_relocated_cfg_bundle.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-soundmain-relocated-cfg-v1",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "312104efd51f2d4cc262aeebe4e06563c71d2d50f54d3a2aa180cd13cfb34199",
            verifier["script_sha256"],
        )
        assertions = verifier["contract"]["assertions"]
        expected_identity = {
            "/schema": "rom-soundmain-relocated-cfg-bundle-verification-v1",
            "/verified": True,
            "/errors": [],
            "/artifact_schema": "rom-soundmain-relocated-cfg-v1",
            "/artifact_status": "accepted",
            "/artifact_bundle_verified": True,
            "/legacy_receipt_verified": True,
            "/candidate_identity_verified": True,
            "/live_coverage_verified": False,
            "/rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
            "/promotion_bytes": 924,
            "/promotion_claim_count": 6,
            "/promotion_range_count": 6,
            "/promotion_union_range_count": 5,
            "/deferred_alignment_gap_bytes": 6,
            "/promotion_packed_sha256": "2e94dbb5f876de3420d1317db7ad646991b9778e15a3699659d7786d65de8331",
            "/accepted_manifest_sha256": "e6b9a2cbdb439c520b5c98a422279e44e03866dbf1541810626d28eb57ce0a37",
            "/candidate_manifest_sha256": "16aedff95afaf1e24f49cd74c01ded1f46433a79b5b708145dfa9a582fd2fa28",
            "/legacy_verifier_sha256": "321d5ca5b7d6f887a21ec93c1bb06640f6e1397248273068bb5a13d3d7167d82",
            "/bundle_verifier_sha256": "312104efd51f2d4cc262aeebe4e06563c71d2d50f54d3a2aa180cd13cfb34199",
        }
        for pointer, expected in expected_identity.items():
            self.assertEqual(expected, assertions[pointer], pointer)
        self.assertEqual(
            {
                "alignment_gap_bytes": 6,
                "alignment_gap_count": 3,
                "arm_instruction_bytes": 572,
                "arm_instruction_count": 143,
                "block_count": 73,
                "code_bytes": 916,
                "deferred_alignment_gap_bytes": 6,
                "external_block_edge_count": 1,
                "instruction_bytes": 916,
                "instruction_count": 315,
                "internal_block_edge_count": 112,
                "internal_return_count": 0,
                "literal_bytes": 8,
                "literal_ref_count": 2,
                "literal_word_count": 2,
                "mode_switch_count": 4,
                "opaque_return_count": 1,
                "owned_provenance_bytes": 2,
                "owned_return_veneer_count": 1,
                "promoted_bytes": 924,
                "promotion_claim_count": 6,
                "promotion_range_count": 6,
                "promotion_union_range_count": 5,
                "thumb_instruction_bytes": 344,
                "thumb_instruction_count": 172,
                "unresolved_frontier_count": 0,
            },
            assertions["/summary"],
        )
        self.assertEqual(
            {
                "alignment_gap_requires_accepted_immutable_artifact": True,
                "code_ranges": [
                    [630_288, 630_298],
                    [630_300, 630_466],
                    [630_472, 630_694],
                    [630_696, 631_214],
                ],
                "deferred_alignment_gap_bytes": 6,
                "deferred_alignment_gap_ranges": [
                    [630_298, 630_300],
                    [630_466, 630_468],
                    [630_694, 630_696],
                ],
                "literal_ranges": [[630_468, 630_472], [631_216, 631_220]],
                "post_gap_projected_totals": {
                    "claim_count": 14_493,
                    "classified_bytes": 6_123_419,
                    "segment_count": 16_600,
                    "unknown_bytes": 168_037,
                },
                "projected_totals": {
                    "claim_count": 14_490,
                    "classified_bytes": 6_123_413,
                    "segment_count": 16_600,
                    "unknown_bytes": 168_043,
                },
                "semantic_bytes": 924,
                "semantic_claim_count": 6,
                "semantic_packed_sha256": "2e94dbb5f876de3420d1317db7ad646991b9778e15a3699659d7786d65de8331",
                "semantic_union_range_vector_sha256": "edd9da8aad815cf4aea5ca9c02360c3903d523588f0a7a6d7a1fa214e57d8a94",
                "semantic_union_ranges": [
                    [630_288, 630_298],
                    [630_300, 630_466],
                    [630_468, 630_694],
                    [630_696, 631_214],
                    [631_216, 631_220],
                ],
            },
            assertions["/promotion"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        coverage_assertions = coverage["contract"]["assertions"]
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/soundmain_relocated_promotion_batch": "rom-soundmain-relocated-cfg-v1",
            "/summary/soundmain_relocated_code_claim_kind": "soundmain_relocated_reachable_instruction_bytes",
            "/summary/soundmain_relocated_literal_claim_kind": "soundmain_relocated_consumed_literal_bytes",
            "/summary/soundmain_relocated_code_bytes": 916,
            "/summary/soundmain_relocated_code_claim_count": 4,
            "/summary/soundmain_relocated_literal_bytes": 8,
            "/summary/soundmain_relocated_literal_claim_count": 2,
            "/summary/soundmain_relocated_promoted_bytes": 924,
            "/summary/soundmain_relocated_promotion_claim_count": 6,
            "/summary/soundmain_relocated_owned_provenance_bytes": 2,
            "/summary/soundmain_relocated_owned_provenance_range_count": 1,
            "/summary/soundmain_relocated_gap_bytes": 6,
            "/summary/soundmain_relocated_gap_range_count": 3,
            "/summary/soundmain_relocated_union_range_count": 5,
            "/summary/soundmain_relocated_union_range_vector_sha256": "edd9da8aad815cf4aea5ca9c02360c3903d523588f0a7a6d7a1fa214e57d8a94",
            "/summary/soundmain_relocated_mode_switch_count": 4,
            "/summary/soundmain_relocated_block_count": 73,
            "/summary/soundmain_relocated_external_edge_count": 1,
            "/summary/soundmain_relocated_opaque_return_count": 1,
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(expected, coverage_assertions[pointer], pointer)

        self.assertTrue(
            any(
                "SoundMain relocated-CFG artifact classifies exactly 916 bounded mixed ARM/Thumb instruction bytes"
                in limitation
                and "three two-byte alignment gaps remain unknown" in limitation
                and "dynamic IWRAM state" in limitation
                and "natural runtime reachability" in limitation
                for limitation in gate["limitations"]
            )
        )

    def test_current_spec_binds_soundmain_relocated_alignment_gap_proof(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}

        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )

        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][3]
            == "tools/verify_rom_soundmain_relocated_alignment_gaps.py"
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_soundmain_relocated_alignment_gaps.py",
                "--root",
                ".",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "0ae3c5c6f2a4d2315cd3f5b10f422faa2babfafe220d8b12069f510a6badc00a",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-soundmain-relocated-alignment-gaps-verification-v1",
                "/verified": True,
                "/errors": [],
                "/promotion_batch": "rom-soundmain-relocated-alignment-gaps-v1",
                "/primary_class": "soundmain_relocated_artifact_bound_4byte_alignment_bytes",
                "/claim_kind": "soundmain_relocated_alignment_gap_bytes",
                "/gap_count": 3,
                "/byte_count": 6,
                "/zero_byte_count": 6,
                "/ranges": [
                    [630_298, 630_300],
                    [630_466, 630_468],
                    [630_694, 630_696],
                ],
                "/range_vector_sha256": "80e7409ef3fd737361faa6a08ae8e2efbedd9891c31e4f4b98392a3ad91da3af",
                "/boundary_vector_sha256": "2f21e70062013bff5f99a9191920f3a6b4ee8996fd1adb0d8cfe577f7d450dd4",
                "/claim_denominator_sha256": "ed6703a2245ca526dc40809dafbaa65328faec20f5aa493ab735ab70128cbd6c",
                "/source_file_vector_sha256": "94d5aa4caa9f45d802f4cecde10d1f08ee4c5650a0c4f24bf40707f2ca1888a2",
                "/packed_bytes_sha256": "b0f66adc83641586656866813fd9dd0b8ebb63796075661ba45d1aa8089e1d44",
                "/source_artifact_count": 1,
                "/source_bundle_verified": True,
                "/all_alignment_equations_hold": True,
                "/all_boundaries_exact": True,
                "/semantic_packet_modified": False,
                "/non_claims": {
                    "all_alignment_gaps_exhaustive_claimed": False,
                    "allocatable_space_claimed": False,
                    "compiler_authorship_claimed": False,
                    "editing_writeback_relocation_safe_claimed": False,
                    "free_space_claimed": False,
                    "gap_instruction_semantics_claimed": False,
                    "global_unreachability_claimed": False,
                    "natural_runtime_reachability_claimed": False,
                    "nop_instruction_claimed": False,
                    "padding_semantics_claimed": False,
                    "reserved_space_claimed": False,
                    "right_structure_semantics_extended_claimed": False,
                },
            },
            verifier["contract"]["assertions"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        assertions = coverage["contract"]["assertions"]
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/soundmain_relocated_alignment_gap_promotion_batch": "rom-soundmain-relocated-alignment-gaps-v1",
            "/summary/soundmain_relocated_alignment_gap_claim_kind": "soundmain_relocated_alignment_gap_bytes",
            "/summary/soundmain_relocated_alignment_gap_bytes": 6,
            "/summary/soundmain_relocated_alignment_gap_claim_count": 3,
            "/summary/soundmain_relocated_alignment_gap_range_vector_sha256": "80e7409ef3fd737361faa6a08ae8e2efbedd9891c31e4f4b98392a3ad91da3af",
            "/summary/soundmain_relocated_alignment_gap_boundary_vector_sha256": "2f21e70062013bff5f99a9191920f3a6b4ee8996fd1adb0d8cfe577f7d450dd4",
            "/summary/soundmain_relocated_alignment_gap_claim_denominator_sha256": "ed6703a2245ca526dc40809dafbaa65328faec20f5aa493ab735ab70128cbd6c",
            "/summary/soundmain_relocated_alignment_gap_packed_bytes_sha256": "b0f66adc83641586656866813fd9dd0b8ebb63796075661ba45d1aa8089e1d44",
            "/summary/soundmain_relocated_alignment_gap_independent_verifier_report_sha256": "95b54d511b064b652c50b5b34519ae6bc887a41e60c0321aa56fc9cc4a059b5f",
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(expected, assertions[pointer], pointer)

        self.assertTrue(
            any(
                "separate immutable SoundMain boundary verifier" in limitation
                and "exactly three two-byte zero ranges totaling six bytes"
                in limitation
                and "superseded only for these three ranges" in limitation
                and "exhaustive SoundMain-gap claim" in limitation
                for limitation in gate["limitations"]
            )
        )

    def test_verifier_timeout_covers_the_current_guarded_coverage_rebuild(self):
        self.assertGreaterEqual(VERIFIER_TIMEOUT_SECONDS, 1_800)

    def test_current_disproved_banks_bind_the_shared_negative_verifier(self):
        catalog = json.loads(
            (ROOT / "sequel/bank-proofs.json").read_text(encoding="utf-8")
        )
        verifier_path = ROOT / "tools/verify_disproved_bank_candidates.py"
        verifier_sha256 = _sha256(verifier_path)
        for slug, spec in DISPROVED_SPECS.items():
            with self.subTest(slug=slug):
                proof = catalog["banks"][slug]
                self.assertEqual([], proof["limitations"])
                self.assertEqual(
                    list(spec["evidence"]),
                    [item["path"] for item in proof["evidence"]],
                )
                self.assertEqual(1, len(proof["verifiers"]))
                verifier = proof["verifiers"][0]
                self.assertEqual(
                    [
                        "python3",
                        "tools/verify_disproved_bank_candidates.py",
                        "--root",
                        ".",
                        "--bank",
                        slug,
                    ],
                    verifier["command"],
                )
                self.assertEqual(verifier_sha256, verifier["script_sha256"])
                assertions = verifier["contract"]["assertions"]
                self.assertEqual(
                    "disproved-bank-candidate-verification-v1",
                    assertions["/schema"],
                )
                self.assertTrue(assertions["/verified"])
                self.assertTrue(assertions["/rejected"])
                self.assertEqual(
                    "independent_physical_bank_candidate",
                    proof["rejection_scope"],
                )
                self.assertEqual(
                    "independent_physical_bank_candidate",
                    assertions["/rejection_scope"],
                )
                self.assertFalse(
                    assertions[
                        "/alternative_logical_consumers_exhaustively_excluded"
                    ]
                )
                self.assertEqual(slug, assertions["/bank"])
                self.assertEqual(proof["candidate_range"], assertions["/candidate_range"])
                self.assertEqual(
                    proof["candidate_sha256"], assertions["/candidate_sha256"]
                )
                self.assertEqual(proof["bank_sha256"], assertions["/bank_sha256"])
                self.assertEqual(
                    {item["path"]: item["sha256"] for item in proof["evidence"]},
                    assertions["/evidence_sha256"],
                )

    def test_disproved_alias_wording_does_not_claim_global_consumer_absence(self):
        catalog = json.loads(
            (ROOT / "sequel/bank-proofs.json").read_text(encoding="utf-8")
        )
        aliases = {
            "battle-handlers",
            "character-stats-b",
            "encounter-zones",
            "fonts",
            "items",
            "resource-pointers",
            "sprite-animations",
        }
        for slug in aliases:
            with self.subTest(slug=slug):
                bank = json.loads(
                    (ROOT / f"sequel/content/{slug}/bank.json").read_text(
                        encoding="utf-8"
                    )
                )
                proof = catalog["banks"][slug]
                self.assertEqual(
                    "independent_physical_bank_candidate",
                    proof["rejection_scope"],
                )
                self.assertNotIn(
                    "no independent", bank["verification_method"].lower()
                )
                self.assertNotIn(
                    "no independent", proof["rejection_reason"].lower()
                )

    def test_accepts_empty_errors_as_an_explicit_success_contract(self):
        value = {
            "format": "json",
            "assertions": {
                "/schema": "fixture-v1",
                "/errors": [],
            },
        }

        self.assertEqual(value, _contract(value))

    def test_rejects_nonempty_errors_without_verified_true(self):
        self.assertIsNone(
            _contract(
                {
                    "format": "json",
                    "assertions": {
                        "/schema": "fixture-v1",
                        "/errors": ["failure"],
                    },
                }
            )
        )

    def _fixture(
        self,
        root: Path,
        *,
        hardware_status: str = "verified",
        verifier_verified: bool = True,
        python_flags: tuple[str, ...] = (),
    ) -> Path:
        rom = b"fixture-rom"
        (root / "rom").mkdir()
        (root / "rom/base.gba").write_bytes(rom)
        evidence = root / "artifacts/example/evidence.json"
        _write_json(evidence, {"verified": True})
        gate_evidence = root / "artifacts/gate.json"
        _write_json(gate_evidence, {"verified": True})
        coverage_manifest = root / "sequel/rom-byte-coverage.json"
        _write_json(coverage_manifest, {"schema": "fixture-coverage-v1"})
        candidate_manifest = root / "sequel/similar-table-candidates-v1.json"
        _write_json(candidate_manifest, {"schema": "fixture-candidates-v1"})
        adjudication_manifest = root / "sequel/similar-table-adjudications-v1.json"
        _write_json(adjudication_manifest, {"schema": "fixture-adjudications-v1"})
        fixture_bank_payload = {
            "verification": "runtime_verified",
            "entry_count": 1,
            "entry_size": 1,
            "entry_format": {
                "fields": [
                    {"name": "value", "offset": 0, "size": 1, "type": "u8"}
                ]
            },
            "entries": [{"value": 1}],
        }
        fixture_bank_sha256 = hashlib.sha256(
            json.dumps(fixture_bank_payload).encode("utf-8")
        ).hexdigest()
        verifier = root / "tools/verify_example.py"
        verifier.parent.mkdir()
        verifier_payload = {
            "schema": "fixture-verifier-v1",
            "verified": verifier_verified,
            "record_ids_covered": ["0"],
            "field_ids_covered": ["value"],
            "bank_sha256": fixture_bank_sha256,
            "evidence_sha256": {
                evidence.relative_to(root).as_posix(): _sha256(evidence)
            },
            "gate_cases": {
                name: list(case_ids) for name, case_ids in GATE_CASES.items()
            },
            "gate_evidence": {
                name: {
                    path.relative_to(root).as_posix(): _sha256(path)
                    for path in (
                        [
                            coverage_manifest,
                            candidate_manifest,
                            adjudication_manifest,
                        ]
                        if name == "rom_byte_coverage"
                        else [gate_evidence]
                    )
                }
                for name in GATE_CASES
            },
        }
        verifier.write_text(
            "import json\n"
            f"print(json.dumps({verifier_payload!r}))\n",
            encoding="utf-8",
        )
        binding = {
            "evidence": [
                {
                    "path": "artifacts/example/evidence.json",
                    "sha256": _sha256(evidence),
                }
            ],
            "verifiers": [
                {
                    "command": [
                        "python3",
                        *python_flags,
                        "tools/verify_example.py",
                    ],
                    "script_sha256": _sha256(verifier),
                    "contract": {
                        "format": "json",
                        "assertions": {
                            "/schema": "fixture-verifier-v1",
                            "/verified": True,
                            "/record_ids_covered": ["0"],
                            "/field_ids_covered": ["value"],
                            "/bank_sha256": fixture_bank_sha256,
                            "/evidence_sha256": {
                                evidence.relative_to(root).as_posix(): _sha256(evidence)
                            },
                        },
                    },
                }
            ],
            "limitations": [],
        }
        bank_proof_entries = {}
        for slug in EXPECTED_BANKS:
            bank = root / f"sequel/content/{slug}/bank.json"
            _write_json(bank, fixture_bank_payload)
            bank_proof_entries[slug] = {
                "catalog_classification": "runtime_verified",
                "bank_sha256": _sha256(bank),
                **binding,
                "coverage": {
                    "status": "exhaustive",
                    "records_total": 1,
                    "records_covered": 1,
                    "record_ids_total": ["0"],
                    "record_ids_covered": ["0"],
                    "field_ids_total": ["value"],
                    "field_ids_covered": ["value"],
                },
            }
        bank_proofs = root / "sequel/bank-proofs.json"
        _write_json(
            bank_proofs,
            {
                "schema": "bank-proofs-v1",
                "banks": bank_proof_entries,
            },
        )
        gates = {}
        for name in GATE_CASES:
            bound_evidence = (
                [coverage_manifest, candidate_manifest, adjudication_manifest]
                if name == "rom_byte_coverage"
                else [gate_evidence]
            )
            gate_verifier = json.loads(json.dumps(binding["verifiers"][0]))
            gate_verifier["contract"]["assertions"][
                f"/gate_cases/{name}"
            ] = list(GATE_CASES[name])
            gate_verifier["contract"]["assertions"][
                f"/gate_evidence/{name}"
            ] = verifier_payload["gate_evidence"][name]
            gates[name] = {
                "status": hardware_status if name == "physical_hardware" else "verified",
                "coverage": {
                    "case_ids_total": list(GATE_CASES[name]),
                    "case_ids_covered": list(GATE_CASES[name]),
                },
                **{
                    **binding,
                    "verifiers": [gate_verifier],
                    "evidence": [
                        {
                            "path": path.relative_to(root).as_posix(),
                            "sha256": _sha256(path),
                        }
                        for path in bound_evidence
                    ],
                },
            }
        spec = root / "sequel/reverse-engineering-proof.json"
        _write_json(
            spec,
            {
                "schema": "reverse-engineering-proof-v1",
                "claim_status": "complete",
                "base_rom": {
                    "path": "rom/base.gba",
                    "size": len(rom),
                    "sha256": hashlib.sha256(rom).hexdigest(),
                },
                "bank_proofs": {
                    "path": "sequel/bank-proofs.json",
                    "sha256": _sha256(bank_proofs),
                },
                "gates": gates,
            },
        )
        return spec

    def _rewrite_bank_proofs(self, spec: Path, mutate) -> None:
        proof_path = spec.parent / "bank-proofs.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        mutate(payload)
        _write_json(proof_path, payload)
        specification = json.loads(spec.read_text(encoding="utf-8"))
        specification["bank_proofs"]["sha256"] = _sha256(proof_path)
        _write_json(spec, specification)

    def test_accepts_only_fully_bound_exhaustive_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)
            fixture_bank_hashes = {
                slug: _sha256(root / f"sequel/content/{slug}/bank.json")
                for slug in EXPECTED_BANKS
            }
            with mock.patch(
                "tools.audit_reverse_engineering_proof.EXPECTED_BANK_FILE_SHA256",
                fixture_bank_hashes,
            ), mock.patch(
                "tools.audit_reverse_engineering_proof.audit_rom_manifest",
                return_value={
                    "verified": True,
                    "state_inventory_complete": True,
                    "semantic_classification_complete": True,
                    "errors": [],
                },
            ), mock.patch(
                "tools.audit_reverse_engineering_proof.verify_similar_table_manifest",
                return_value={
                    "verified": True,
                    "candidate_count": 0,
                    "open_candidate_count": 0,
                    "errors": [],
                },
            ):
                result = audit_proof(
                    root,
                    spec,
                    execute_verifiers=True,
                    trusted_spec_sha256=_sha256(spec),
                )
        self.assertTrue(result["complete"], result["blockers"])

    def test_accepts_hash_bound_verifier_with_isolated_python_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root, python_flags=("-I", "-S"))
            fixture_bank_hashes = {
                slug: _sha256(root / f"sequel/content/{slug}/bank.json")
                for slug in EXPECTED_BANKS
            }
            with mock.patch(
                "tools.audit_reverse_engineering_proof.EXPECTED_BANK_FILE_SHA256",
                fixture_bank_hashes,
            ), mock.patch(
                "tools.audit_reverse_engineering_proof.audit_rom_manifest",
                return_value={
                    "verified": True,
                    "state_inventory_complete": True,
                    "semantic_classification_complete": True,
                    "errors": [],
                },
            ), mock.patch(
                "tools.audit_reverse_engineering_proof.verify_similar_table_manifest",
                return_value={
                    "verified": True,
                    "candidate_count": 0,
                    "open_candidate_count": 0,
                    "errors": [],
                },
            ):
                result = audit_proof(
                    root,
                    spec,
                    execute_verifiers=True,
                    trusted_spec_sha256=_sha256(spec),
                )

        self.assertTrue(result["complete"], result["blockers"])

    def test_isolated_contract_execution_drops_runtime_path_overrides(self):
        completed = mock.Mock(
            returncode=0,
            stdout=json.dumps({"verified": True}),
            stderr="",
        )
        blockers: list[str] = []
        with mock.patch(
            "tools.audit_reverse_engineering_proof.subprocess.run",
            return_value=completed,
        ) as run:
            result = _execute_contract(
                ROOT,
                "isolated fixture",
                ["python3", "-I", "-S", "tools/fixture.py"],
                {"format": "json", "assertions": {"/verified": True}},
                blockers,
            )

        environment = run.call_args.kwargs["env"]
        for name in ("PYTHONPATH", "PYTHONHOME", "LIBCAPSTONE_PATH"):
            self.assertNotIn(name, environment)
        self.assertTrue(result["contract_ok"], blockers)

        with mock.patch(
            "tools.audit_reverse_engineering_proof.subprocess.run",
            return_value=completed,
        ) as run:
            _execute_contract(
                ROOT,
                "non-isolated fixture",
                ["python3", "tools/fixture.py"],
                {"format": "json", "assertions": {"/verified": True}},
                [],
            )
        self.assertEqual(
            str(ROOT),
            run.call_args.kwargs["env"]["PYTHONPATH"],
        )

    def test_reuses_the_already_executed_rom_coverage_audit_contract(self):
        payload = {
            "schema": "rom-byte-coverage-audit-v1",
            "verified": True,
            "summary": {"unknown_bytes": 7},
        }
        blockers: list[str] = []
        result = _reuse_rom_coverage_contract(
            "gate rom_byte_coverage",
            ["python3", "tools/audit_rom_byte_coverage.py", "--root", "."],
            {
                "format": "json",
                "assertions": {
                    "/schema": "rom-byte-coverage-audit-v1",
                    "/verified": True,
                    "/summary/unknown_bytes": 7,
                },
            },
            payload,
            blockers,
        )

        self.assertTrue(result["contract_ok"], blockers)
        self.assertEqual("reused-in-process", result["execution"])
        self.assertEqual([], blockers)

        blockers = []
        mismatch = _reuse_rom_coverage_contract(
            "gate rom_byte_coverage",
            ["python3", "tools/audit_rom_byte_coverage.py", "--root", "."],
            {"format": "json", "assertions": {"/summary/unknown_bytes": 0}},
            payload,
            blockers,
        )
        self.assertFalse(mismatch["contract_ok"])
        self.assertIn("contract mismatch", blockers[0])

    def test_full_audit_does_not_spawn_the_rom_coverage_cli_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec_path = self._fixture(root)
            coverage_script = root / "tools/audit_rom_byte_coverage.py"
            coverage_script.write_text("raise SystemExit('must not run')\n", encoding="utf-8")
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            coverage_command = [
                "python3",
                "tools/audit_rom_byte_coverage.py",
                "--root",
                ".",
            ]
            spec["gates"]["rom_byte_coverage"]["verifiers"].append(
                {
                    "command": coverage_command,
                    "script_sha256": _sha256(coverage_script),
                    "contract": {
                        "format": "json",
                        "assertions": {
                            "/schema": "rom-byte-coverage-audit-v1",
                            "/verified": True,
                        },
                    },
                }
            )
            _write_json(spec_path, spec)
            coverage_report = {
                "schema": "rom-byte-coverage-audit-v1",
                "verified": True,
                "state_inventory_complete": True,
                "semantic_classification_complete": True,
                "errors": [],
            }
            fixture_bank_hashes = {
                slug: _sha256(root / f"sequel/content/{slug}/bank.json")
                for slug in EXPECTED_BANKS
            }

            def execute_without_process(root, label, command, contract, blockers):
                self.assertNotEqual(coverage_command, command)
                return {
                    "label": label,
                    "command": command,
                    "exit_code": 0,
                    "contract_ok": True,
                }

            with mock.patch(
                "tools.audit_reverse_engineering_proof.EXPECTED_BANK_FILE_SHA256",
                fixture_bank_hashes,
            ), mock.patch(
                "tools.audit_reverse_engineering_proof.audit_rom_manifest",
                return_value=coverage_report,
            ), mock.patch(
                "tools.audit_reverse_engineering_proof.verify_similar_table_manifest",
                return_value={
                    "verified": True,
                    "candidate_count": 0,
                    "open_candidate_count": 0,
                    "errors": [],
                },
            ), mock.patch(
                "tools.audit_reverse_engineering_proof._execute_contract",
                side_effect=execute_without_process,
            ):
                result = audit_proof(
                    root,
                    spec_path,
                    execute_verifiers=True,
                    trusted_spec_sha256=_sha256(spec_path),
                )

        reused = [
            item
            for item in result["verifiers_executed"]
            if item.get("execution") == "reused-in-process"
        ]
        self.assertEqual(1, len(reused), result["verifiers_executed"])
        self.assertTrue(Path(reused[0]["command"][0]).name.startswith("python"))
        self.assertEqual(coverage_command[1:], reused[0]["command"][1:])

    def test_complete_claim_requires_verifier_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)
            result = audit_proof(
                root,
                spec,
                trusted_spec_sha256=_sha256(spec),
            )
        self.assertFalse(result["complete"])
        self.assertIn(
            "complete claim requires verifier execution", result["blockers"]
        )

    def test_failed_verifier_marks_each_bound_subject_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root, verifier_verified=False)
            fixture_bank_hashes = {
                slug: _sha256(root / f"sequel/content/{slug}/bank.json")
                for slug in EXPECTED_BANKS
            }
            with mock.patch(
                "tools.audit_reverse_engineering_proof.EXPECTED_BANK_FILE_SHA256",
                fixture_bank_hashes,
            ), mock.patch(
                "tools.audit_reverse_engineering_proof.audit_rom_manifest",
                return_value={
                    "verified": True,
                    "state_inventory_complete": True,
                    "semantic_classification_complete": True,
                    "errors": [],
                },
            ), mock.patch(
                "tools.audit_reverse_engineering_proof.verify_similar_table_manifest",
                return_value={
                    "verified": True,
                    "candidate_count": 0,
                    "open_candidate_count": 0,
                    "errors": [],
                },
            ):
                result = audit_proof(
                    root,
                    spec,
                    execute_verifiers=True,
                    trusted_spec_sha256=_sha256(spec),
                )

        audio = next(item for item in result["bank_results"] if item["bank"] == "audio")
        self.assertFalse(audio["complete"])
        self.assertFalse(result["gate_results"]["resource_roundtrip"]["complete"])
        self.assertEqual(0, result["banks_complete"])

    def test_complete_claim_requires_external_root_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = audit_proof(
                root,
                self._fixture(root),
                execute_verifiers=True,
            )
        self.assertFalse(result["complete"])
        self.assertIn(
            "complete claim requires an external trusted spec SHA-256",
            result["blockers"],
        )

    def test_verified_rom_gate_still_rejects_unknown_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)
            with mock.patch(
                "tools.audit_reverse_engineering_proof.audit_rom_manifest",
                return_value={
                    "verified": True,
                    "state_inventory_complete": True,
                    "semantic_classification_complete": False,
                    "errors": [],
                },
            ):
                result = audit_proof(
                    root,
                    spec,
                    execute_verifiers=True,
                    trusted_spec_sha256=_sha256(spec),
                )
        self.assertFalse(result["complete"])
        self.assertIn(
            "gate rom_byte_coverage: semantic classification is incomplete",
            result["blockers"],
        )

    def test_rom_gate_surfaces_coverage_rebuild_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)
            with mock.patch(
                "tools.audit_reverse_engineering_proof.audit_rom_manifest",
                return_value={
                    "verified": False,
                    "semantic_classification_complete": False,
                    "errors": ["synthetic coverage rebuild failure"],
                },
            ):
                result = audit_proof(root, spec)

        self.assertIn(
            "gate rom_byte_coverage: coverage audit error: "
            "synthetic coverage rebuild failure",
            result["blockers"],
        )

    def test_rejects_exit_zero_verifier_without_structured_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)

            def mutate(payload):
                del payload["banks"][EXPECTED_BANKS[0]]["verifiers"][0]["contract"]

            self._rewrite_bank_proofs(spec, mutate)
            result = audit_proof(
                root,
                spec,
                execute_verifiers=True,
                trusted_spec_sha256=_sha256(spec),
            )
        self.assertFalse(result["complete"])
        self.assertTrue(
            any("lacks a structured JSON result contract" in item for item in result["blockers"]),
            result["blockers"],
        )

    def test_rejects_bank_contract_without_record_and_field_assertions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)

            def mutate(payload):
                assertions = payload["banks"][EXPECTED_BANKS[0]]["verifiers"][0][
                    "contract"
                ]["assertions"]
                del assertions["/record_ids_covered"]
                del assertions["/field_ids_covered"]

            self._rewrite_bank_proofs(spec, mutate)
            result = audit_proof(root, spec)

        self.assertFalse(result["complete"])
        self.assertIn(
            f"{EXPECTED_BANKS[0]}: no verifier contract binds the exhaustive record, field, bank and evidence IDs",
            result["blockers"],
        )

    def test_rejects_gate_contract_without_fixed_case_assertion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)
            payload = json.loads(spec.read_text(encoding="utf-8"))
            assertions = payload["gates"]["resource_roundtrip"]["verifiers"][0][
                "contract"
            ]["assertions"]
            del assertions["/gate_cases/resource_roundtrip"]
            _write_json(spec, payload)

            result = audit_proof(root, spec)

        self.assertFalse(result["complete"])
        self.assertIn(
            "gate resource_roundtrip: no verifier contract binds the fixed case and evidence IDs",
            result["blockers"],
        )

    def test_rejects_contract_that_does_not_bind_its_evidence_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)

            def mutate(payload):
                assertions = payload["banks"][EXPECTED_BANKS[0]]["verifiers"][0][
                    "contract"
                ]["assertions"]
                del assertions["/evidence_sha256"]

            self._rewrite_bank_proofs(spec, mutate)
            result = audit_proof(root, spec)

        self.assertFalse(result["complete"])
        self.assertIn(
            f"{EXPECTED_BANKS[0]}: no verifier contract binds the exhaustive record, field, bank and evidence IDs",
            result["blockers"],
        )

    def test_rejects_absolute_base_rom_path_even_when_hash_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)
            payload = json.loads(spec.read_text(encoding="utf-8"))
            payload["base_rom"]["path"] = str((root / "rom/base.gba").resolve())
            _write_json(spec, payload)
            result = audit_proof(
                root,
                spec,
                execute_verifiers=True,
                trusted_spec_sha256=_sha256(spec),
            )
        self.assertFalse(result["complete"])
        self.assertIn("base_rom path must be repository-relative", result["blockers"])

    def test_rejects_shrunk_bank_inventory(self):
        self.assertEqual(32, len(EXPECTED_BANKS))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)
            missing = EXPECTED_BANKS[-1]
            (root / f"sequel/content/{missing}/bank.json").unlink()
            self._rewrite_bank_proofs(
                spec, lambda payload: payload["banks"].pop(missing)
            )
            result = audit_proof(
                root,
                spec,
                execute_verifiers=True,
                trusted_spec_sha256=_sha256(spec),
            )
        self.assertFalse(result["complete"])
        self.assertTrue(
            any("fixed bank inventory mismatch" in item for item in result["blockers"]),
            result["blockers"],
        )

    def test_rejects_runtime_label_without_proof_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)
            self._rewrite_bank_proofs(
                spec, lambda payload: payload["banks"].pop(EXPECTED_BANKS[0])
            )
            result = audit_proof(root, spec)
        self.assertFalse(result["complete"])
        self.assertIn(f"{EXPECTED_BANKS[0]}: missing proof object", result["blockers"])

    def test_rejects_blocked_physical_hardware_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = audit_proof(
                root,
                self._fixture(root, hardware_status="blocked_external"),
            )
        self.assertFalse(result["complete"])
        self.assertIn(
            "gate physical_hardware: status is blocked_external, expected verified",
            result["blockers"],
        )

    def test_rejects_count_only_field_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)

            def mutate(payload):
                coverage = payload["banks"][EXPECTED_BANKS[0]]["coverage"]
                del coverage["field_ids_total"]
                del coverage["field_ids_covered"]
                coverage["fields_total"] = coverage["fields_covered"] = 1

            self._rewrite_bank_proofs(spec, mutate)
            result = audit_proof(root, spec)

        self.assertFalse(result["complete"])
        self.assertIn(
            f"{EXPECTED_BANKS[0]}: field denominator does not match entry_format",
            result["blockers"],
        )

    def test_rejects_self_declared_field_names_not_in_bank_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)

            def mutate(payload):
                coverage = payload["banks"][EXPECTED_BANKS[0]]["coverage"]
                coverage["field_ids_total"] = ["invented"]
                coverage["field_ids_covered"] = ["invented"]

            self._rewrite_bank_proofs(spec, mutate)
            result = audit_proof(root, spec)

        self.assertFalse(result["complete"])
        self.assertIn(
            f"{EXPECTED_BANKS[0]}: field denominator does not match entry_format",
            result["blockers"],
        )

    def test_rejects_declared_record_denominator_that_differs_from_bank(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)

            def mutate(payload):
                coverage = payload["banks"][EXPECTED_BANKS[0]]["coverage"]
                coverage["records_total"] = 2
                coverage["records_covered"] = 1

            self._rewrite_bank_proofs(spec, mutate)
            result = audit_proof(root, spec)

        self.assertFalse(result["complete"])
        self.assertIn(
            f"{EXPECTED_BANKS[0]}: declared record denominator 2 does not match bank entry count 1",
            result["blockers"],
        )

    def test_rejects_verifier_outside_tools_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)

            def mutate(payload):
                payload["banks"][EXPECTED_BANKS[0]]["verifiers"][0]["command"] = [
                    "python3",
                    "../verify_example.py",
                ]

            self._rewrite_bank_proofs(spec, mutate)
            result = audit_proof(root, spec)

        self.assertFalse(result["complete"])
        self.assertTrue(
            any("parent traversal" in blocker for blocker in result["blockers"]),
            result["blockers"],
        )

    def test_rejects_equals_style_absolute_verifier_path_argument(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)

            def mutate(payload):
                payload["banks"][EXPECTED_BANKS[0]]["verifiers"][0][
                    "command"
                ].append("--artifact=/etc/passwd")

            self._rewrite_bank_proofs(spec, mutate)
            result = audit_proof(root, spec)

        self.assertFalse(result["complete"])
        self.assertTrue(
            any("verifier path argument escapes repository" in item for item in result["blockers"]),
            result["blockers"],
        )

    def test_rejects_verifier_path_argument_through_symlink(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            spec = self._fixture(root)
            external = Path(outside) / "artifact"
            external.mkdir()
            (root / "artifacts/link").symlink_to(external, target_is_directory=True)

            def mutate(payload):
                payload["banks"][EXPECTED_BANKS[0]]["verifiers"][0][
                    "command"
                ].extend(["--artifact", "artifacts/link"])

            self._rewrite_bank_proofs(spec, mutate)
            result = audit_proof(root, spec)

        self.assertFalse(result["complete"])
        self.assertTrue(
            any("uses a symlink" in item for item in result["blockers"]),
            result["blockers"],
        )

    def test_rejects_tampered_evidence_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)
            (root / "artifacts/example/evidence.json").write_text(
                "{}", encoding="utf-8"
            )
            result = audit_proof(root, spec)

        self.assertFalse(result["complete"])
        self.assertTrue(
            any("evidence SHA-256 mismatch" in blocker for blocker in result["blockers"]),
            result["blockers"],
        )

    def test_rejects_unbound_bank_file_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)
            bank = root / f"sequel/content/{EXPECTED_BANKS[0]}/bank.json"
            payload = json.loads(bank.read_text(encoding="utf-8"))
            payload["entries"][0]["value"] = 2
            _write_json(bank, payload)

            result = audit_proof(root, spec)

        self.assertFalse(result["complete"])
        self.assertIn(
            f"{EXPECTED_BANKS[0]}: bank file is not bound by its exact SHA-256",
            result["blockers"],
        )

    def test_rejects_bank_denominator_change_even_when_local_hashes_are_resigned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)
            slug = EXPECTED_BANKS[0]
            fixture_bank_hashes = {
                bank_slug: _sha256(
                    root / f"sequel/content/{bank_slug}/bank.json"
                )
                for bank_slug in EXPECTED_BANKS
            }
            bank = root / f"sequel/content/{slug}/bank.json"
            payload = json.loads(bank.read_text(encoding="utf-8"))
            payload["entry_count"] = 2
            payload["entries"].append({"value": 2})
            _write_json(bank, payload)

            def mutate(catalog):
                proof = catalog["banks"][slug]
                proof["bank_sha256"] = _sha256(bank)
                proof["coverage"].update(
                    {
                        "records_total": 2,
                        "records_covered": 2,
                        "record_ids_total": ["0", "1"],
                        "record_ids_covered": ["0", "1"],
                    }
                )

            self._rewrite_bank_proofs(spec, mutate)
            with mock.patch(
                "tools.audit_reverse_engineering_proof.EXPECTED_BANK_FILE_SHA256",
                fixture_bank_hashes,
            ), mock.patch(
                "tools.audit_reverse_engineering_proof.audit_rom_manifest",
                return_value={
                    "verified": True,
                    "state_inventory_complete": True,
                    "semantic_classification_complete": True,
                    "errors": [],
                },
            ), mock.patch(
                "tools.audit_reverse_engineering_proof.verify_similar_table_manifest",
                return_value={
                    "verified": True,
                    "candidate_count": 0,
                    "open_candidate_count": 0,
                    "errors": [],
                },
            ):
                result = audit_proof(
                    root,
                    spec,
                    execute_verifiers=True,
                    trusted_spec_sha256=_sha256(spec),
                )

        self.assertFalse(result["complete"])
        self.assertIn(
            f"{slug}: fixed bank denominator changed",
            result["blockers"],
        )

    def test_rejects_disproved_candidate_range_outside_base_rom(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)
            slug = EXPECTED_BANKS[0]
            bank = root / f"sequel/content/{slug}/bank.json"
            payload = json.loads(bank.read_text(encoding="utf-8"))
            payload.update(
                {
                    "verification": "disproved",
                    "entry_count": 0,
                    "entries": [],
                    "entry_format": {"fields": []},
                }
            )
            _write_json(bank, payload)

            def mutate(catalog):
                proof = catalog["banks"][slug]
                proof.update(
                    {
                        "catalog_classification": "disproved",
                        "bank_sha256": _sha256(bank),
                        "coverage": {
                            "status": "disproved",
                            "records_total": 0,
                            "records_covered": 0,
                        },
                        "candidate_range": [0, len(b"fixture-rom") + 1],
                        "candidate_sha256": "0" * 64,
                        "rejection_reason": "fixture rejection",
                    }
                )

            self._rewrite_bank_proofs(spec, mutate)
            result = audit_proof(root, spec)

        self.assertFalse(result["complete"])
        self.assertIn(
            f"{slug}: disproved proof needs an in-ROM candidate range",
            result["blockers"],
        )

    def test_rejects_disproved_candidate_without_fixed_physical_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._fixture(root)
            slug = EXPECTED_BANKS[0]
            bank = root / f"sequel/content/{slug}/bank.json"
            payload = json.loads(bank.read_text(encoding="utf-8"))
            payload.update(
                {
                    "verification": "disproved",
                    "entry_count": 0,
                    "entries": [],
                    "entry_format": {"fields": []},
                }
            )
            _write_json(bank, payload)

            def mutate(catalog):
                proof = catalog["banks"][slug]
                proof.update(
                    {
                        "catalog_classification": "disproved",
                        "bank_sha256": _sha256(bank),
                        "coverage": {
                            "status": "disproved",
                            "records_total": 0,
                            "records_covered": 0,
                        },
                        "candidate_range": [0, 1],
                        "candidate_sha256": hashlib.sha256(b"f").hexdigest(),
                        "rejection_reason": "fixture physical alias",
                    }
                )
                proof.pop("rejection_scope", None)

            self._rewrite_bank_proofs(spec, mutate)
            result = audit_proof(root, spec)

        self.assertIn(
            f"{slug}: disproved proof must target the fixed independent physical bank scope",
            result["blockers"],
        )

    def test_current_proof_and_policy_publish_current_coverage_counts(self):
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        summary = coverage["summary"]
        expected_limitation = (
            "The manifest explicitly accounts for all "
            f"{summary['rom_bytes']} bytes, but {summary['unknown_bytes']} bytes "
            f"({summary['unknown_bytes'] / summary['rom_bytes'] * 100:.4f}%) remain "
            "semantically unknown."
        )
        limitations = specification["gates"]["rom_byte_coverage"]["limitations"]
        self.assertIn(expected_limitation, limitations)
        self.assertTrue(
            any(
                "five exact current-unknown empty rows" in item
                and "40 bytes" in item
                and "complete Unicode" in item
                for item in limitations
            )
        )
        self.assertTrue(
            any(
                "exactly the two current-unknown bytes" in item
                and "15×10-byte motion-spawn table" in item
                and "explicit terminator" in item
                and "22×24-byte sequence-descriptor table" in item
                and "4-byte alignment gap" in item
                and "reserved or free space" in item
                and "natural runtime reachability" in item
                and "global unreachability" in item
                and "editing or relocation safety" in item
                and "safe allocation" in item
                and "adjacent bytes" in item
                for item in limitations
            )
        )
        self.assertTrue(
            any(
                "file [0x005A320A,0x005A320C)" in item
                and "79×10-byte battle-presentation binding table" in item
                and "79×68-byte tile-assets table" in item
                and "fixed-count boundary" in item
                and "4-byte alignment gap" in item
                and "padding" in item
                and "reserved or free space" in item
                and "natural runtime reachability" in item
                and "global unreachability" in item
                and "editing or relocation safety" in item
                and "safe allocation" in item
                and "adjacent bytes" in item
                and "consumer completeness" in item
                for item in limitations
            )
        )
        self.assertTrue(
            any(
                "file [0x0053E696,0x0053E698)" in item
                and "256×1-byte runtime-state selector table" in item
                and "256×8-byte handler-pair table" in item
                and "fixed-count boundary" in item
                and "4-byte alignment gap" in item
                and "padding" in item
                and "reserved or free space" in item
                and "natural runtime reachability" in item
                and "global unreachability" in item
                and "editing or relocation safety" in item
                and "safe allocation" in item
                and "adjacent bytes" in item
                and "consumer completeness" in item
                and "cross-table dataflow" in item
                for item in limitations
            )
        )
        self.assertTrue(
            any(
                "four fixed Cutscene OBJ resource IDs" in item
                and "four 2-byte ranges totaling 8 bytes" in item
                and "strict type-0x10 palette parser endpoint" in item
                and "slot-0 first definition record" in item
                and "4-byte alignment gap" in item
                and "padding, reserved, free, or allocatable" in item
                and "natural runtime reachability" in item
                and "global unreachability" in item
                and "complete Cutscene gap denominator" in item
                and "editing or relocation safety" in item
                and "final-pixel equivalence" in item
                and "unknown definition-field semantics" in item
                for item in limitations
            )
        )
        self.assertTrue(any("fixed 263-root ARMv4T CFG" in item for item in limitations))
        self.assertTrue(any("one-generation" in item for item in limitations))
        self.assertTrue(
            any(
                "direct-call-proven two-root delta" in item
                and "12946" in item
                and "12 producer bytes" in item
                for item in limitations
            )
        )
        self.assertTrue(
            any("1219" in item and "16814" in item for item in limitations)
        )
        self.assertTrue(
            any("46" in item and "6798" in item and "38" in item for item in limitations)
        )
        self.assertTrue(
            any(
                "eleven fixed consumer text tables" in item
                and "3000" in item
                and "11177" in item
                and "735" in item
                for item in limitations
            )
        )
        self.assertTrue(
            any(
                "fixed 45-slot training table" in item
                and "44" in item
                and "2505" in item
                for item in limitations
            )
        )
        self.assertTrue(
            any(
                "fixed 38-slot value-range selector" in item
                and "152" in item
                and "862" in item
                for item in limitations
            )
        )
        self.assertTrue(
            any(
                "46-row selector source domain" in item
                and "324" in item
                and "316" in item
                and "176" in item
                for item in limitations
            )
        )
        self.assertTrue(
            any(
                "133 referenced post-NUL slot suffixes" in item
                and "1255" in item
                and "550" in item
                and "368" in item
                and "337" in item
                for item in limitations
            )
        )
        self.assertTrue(
            any(
                "ten frozen selector source windows" in item
                and "2754" in item
                and "19" in item
                and "1252" in item
                and "1502" in item
                and "instruction" in item
                and "runtime reachability" in item
                and "allocatable" in item
                for item in limitations
            )
        )
        self.assertTrue(
            any(
                "70 distinct physical" in item
                and "8960" in item
                and "74" in item
                and "311" in item
                and "128-byte" in item
                and "relocation" in item
                and "allocatable" in item
                for item in limitations
            )
        )
        self.assertTrue(
            any(
                "frozen 52 short all-zero ranges" in item
                and "pointer-reachable LZ77 endpoints" in item
                and "menu-portrait palette starts" in item
                and "generic alignment rule" in item
                and "allocatable space" in item
                for item in limitations
            )
        )
        self.assertTrue(
            any(
                "scene-visual source-range inventory" in item
                and "29" in item
                and "3257" in item
                and "31-byte" in item
                and "LZ77" in item
                and "natural reachability" in item
                and "relocation" in item
                and "allocatable" in item
                for item in limitations
            )
        )
        self.assertTrue(
            any(
                "Cutscene OBJ source-range inventory" in item
                and "28" in item
                and "400" in item
                and "unknown component field" in item
                and "natural runtime reachability" in item
                and "allocatable space" in item
                for item in limitations
            )
        )
        self.assertFalse(
            any(
                "Post-NUL zero suffixes" in item
                and "remain unclaimed" in item
                for item in limitations
            )
        )
        self.assertTrue(
            any(
                "fixed 79-slot battle-message table" in item
                and "1411" in item
                and "1329" in item
                and "140" in item
                for item in limitations
            )
        )
        self.assertTrue(
            any(
                "fixed BL/BX-pc/ARM-B interwork spine" in item
                and "414" in item
                and "92-instruction" in item
                and "C0 46" in item
                and "MOV r8,r8" in item
                and "separate additive" in item
                and "natural reachability" in item
                and "allocatable space" in item
                for item in limitations
            )
        )

        policy = (ROOT / "docs/reverse-engineering-proof-policy.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"`{summary['classified_bytes']:,}`", policy)
        self.assertIn(f"`{summary['unknown_bytes']:,}`", policy)
        self.assertIn("固定 263-root ARMv4T CFG", policy)
        self.assertIn("一次性 CFG 扩展", policy)
        self.assertIn("对话记录间零填充", policy)
        self.assertIn("46 条角色资料文本", policy)
        self.assertIn("11 张固定消费者文本指针表", policy)
        self.assertIn("45 槽训练文本命令脚本", policy)
        self.assertIn("38 槽值域选择文本表", policy)
        self.assertIn("46 行来源域 selector 文本", policy)
        self.assertIn("133 段引用槽 NUL 后结构零填充", policy)
        self.assertIn("10 段 selector 来源代码窗口", policy)
        self.assertIn("70 段菜单肖像物理调色板", policy)
        self.assertIn("52 段菜单肖像 LZ77→调色板短对齐间隙", policy)
        self.assertIn("29 段场景视觉来源范围", policy)
        self.assertIn("28 段 Cutscene OBJ 来源范围", policy)
        self.assertIn("79 槽战斗消息文本表", policy)
        self.assertIn("固定 interwork ARM 根闭包", policy)
        self.assertIn("motion spawn→sequence descriptor 两字节 4-byte 对齐间隙", policy)
        self.assertIn(
            "battle presentation binding→tile assets 两字节 4-byte 对齐间隙",
            policy,
        )
        self.assertIn(
            "runtime-state selector→handler pair 两字节 4-byte 对齐间隙",
            policy,
        )

    def test_current_spec_binds_profile_text_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "57979c4355a182f219702d48055ff21b3b81d132ffb5240c64e152ecb54503f8",
            evidence["artifacts/rom-profile-text-inventory-v1/manifest.json"],
        )
        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/verify_rom_profile_text_inventory.py"
        )
        self.assertEqual(
            "87830893bf507866e6966c8f9bda558bee094be890d442f3375970f2d3084009",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-profile-text-inventory-verification-v1",
                "/verified": True,
                "/errors": [],
                "/pointer_slot_count": 46,
                "/profile_text_record_count": 46,
                "/profile_text_bytes": 6_798,
                "/alignment_padding_bytes": 38,
                "/claimed_region_bytes": 6_836,
            },
            verifier["contract"]["assertions"],
        )

    def test_current_spec_binds_fixed_consumer_text_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "560464a6fed43de1a77c6339362dc2ef28534a7374ff976df572d05a9bad6b94",
            evidence[
                "artifacts/rom-fixed-consumer-text-inventory-v1/manifest.json"
            ],
        )
        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1]
            == "tools/verify_rom_fixed_consumer_text_inventory.py"
        )
        self.assertEqual(
            "3642d029654c7fadaaf34e354ed350e89d40d1085858aded689ad70cdcae2e44",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-fixed-consumer-text-inventory-verification-v1",
                "/verified": True,
                "/errors": [],
                "/pointer_table_count": 11,
                "/pointer_slot_count": 750,
                "/null_pointer_slot_count": 11,
                "/pointer_table_bytes": 3_000,
                "/unique_target_count": 735,
                "/renderer_record_count": 735,
                "/renderer_consumed_bytes": 11_177,
                "/classified_range_count": 746,
                "/classified_bytes": 14_177,
                "/parse_failure_count": 0,
                "/range_overlap_bytes": 0,
                "/packed_bytes": 14_177,
                "/bundle_sha256": (
                    "e71eefd9ee1d98333fdd0cd72c6b67ce6335a6874bf5f92c072177807ca1168a"
                ),
            },
            verifier["contract"]["assertions"],
        )

    def test_current_spec_binds_training_text_script_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "af609bc3b303e2617d79cc254d3b39d67e05f3606654441613309566d23e3c0b",
            evidence[
                "artifacts/rom-training-text-script-inventory-v1/manifest.json"
            ],
        )
        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1]
            == "tools/verify_rom_training_text_script_inventory.py"
        )
        self.assertEqual(
            "8058c27cb313c6d32d613feb9946444932c3d9dc64fe27929489fb1af72e5305",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-training-text-script-inventory-verification-v1",
                "/verified": True,
                "/errors": [],
                "/pointer_slot_count": 45,
                "/null_slot_count": 1,
                "/non_null_slot_count": 44,
                "/command_record_count": 44,
                "/command_count": 264,
                "/embedded_renderer_text_bytes": 1_889,
                "/record_bytes": 2_505,
                "/classified_range_count": 44,
                "/classified_bytes": 2_505,
                "/parse_failure_count": 0,
                "/range_overlap_bytes": 0,
                "/packed_bytes": 2_505,
                "/bundle_sha256": (
                    "fa9991353e99ecd63d8e0617fb078198b62527d548c8c5eb5fbac173d0302da0"
                ),
            },
            verifier["contract"]["assertions"],
        )

    def test_current_spec_binds_value_range_text_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "7bea3bcecd28d86a6bdbcd5bba58cbb4413dced0008691e219262de8f1a0faca",
            evidence[
                "artifacts/rom-value-range-text-inventory-v1/manifest.json"
            ],
        )
        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1]
            == "tools/verify_rom_value_range_text_inventory.py"
        )
        self.assertEqual(
            "2ea19627a36ccd9ff8034071e7294d7f6a7594193015efb504c17f5e72b1baae",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-value-range-text-inventory-verification-v1",
                "/verified": True,
                "/errors": [],
                "/pointer_slot_count": 38,
                "/pointer_table_bytes": 152,
                "/value_range_entry_count": 38,
                "/value_range_map_bytes": 152,
                "/renderer_record_count": 38,
                "/renderer_consumed_bytes": 862,
                "/classified_range_count": 39,
                "/classified_bytes": 1_014,
                "/parse_failure_count": 0,
                "/range_overlap_bytes": 0,
                "/packed_bytes": 1_014,
                "/bundle_sha256": (
                    "88f201f21194087ff7643f1822d0b89c309feff497fbef6155ff5ae6ce6bc3d0"
                ),
            },
            verifier["contract"]["assertions"],
        )

    def test_current_spec_binds_selector_text_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "05cd987a60990ca6b2d3ee187eae963fd6ac8728ef9b42b92d6b37b5dc4bc031",
            evidence[
                "artifacts/rom-selector-text-bindings-v1/manifest.json"
            ],
        )
        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1]
            == "tools/verify_rom_selector_text_bindings.py"
        )
        self.assertEqual(
            "a68a0d1e036be241bbac84538d5a082c7e76e2c6331ffa1d12cd384dc79e2f18",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-selector-text-bindings-verification-v1",
                "/verified": True,
                "/errors": [],
                "/artifact_schema": "rom-selector-text-bindings-v1",
                "/summary/direct_source_record_count": 46,
                "/summary/direct_text_candidate_slot_count": 46,
                "/summary/direct_text_consumed_bytes": 324,
                "/summary/direct_text_unclassified_suffix_bytes": 550,
                "/summary/configured_referenced_slot_count": 38,
                "/summary/configured_text_consumed_bytes": 316,
                "/summary/configured_text_unclassified_suffix_bytes": 368,
                "/summary/config_bytes": 164,
                "/summary/config_pointer_bytes": 12,
                "/summary/classified_range_count": 86,
                "/summary/classified_bytes": 816,
                "/summary/parse_failure_count": 0,
                "/summary/range_overlap_bytes": 0,
                "/summary/packed_bytes": 816,
            },
            verifier["contract"]["assertions"],
        )

    def test_current_spec_binds_battle_message_text_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "fff6410091d6165f338821b6400ecb5e0912a7221bad0c664bbce85d9daf5d54",
            evidence[
                "artifacts/rom-battle-message-text-inventory-v1/manifest.json"
            ],
        )
        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1]
            == "tools/verify_rom_battle_message_text_inventory.py"
        )
        self.assertEqual(
            "edc6f0f634d8137500f9adcb1f536ea2141dc48c470a17d6374717d7b42acfd2",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-battle-message-text-inventory-verification-v1",
                "/verified": True,
                "/errors": [],
                "/artifact_schema": "rom-battle-message-text-inventory-v1",
                "/summary/pointer_slot_count": 79,
                "/summary/renderer_record_count": 79,
                "/summary/renderer_consumed_bytes": 1_411,
                "/summary/zero_padding_range_count": 79,
                "/summary/zero_padding_bytes": 1_329,
                "/summary/classified_range_count": 158,
                "/summary/classified_bytes": 2_740,
                "/summary/parse_failure_count": 0,
                "/summary/range_overlap_bytes": 0,
                "/summary/packed_bytes": 2_740,
                "/bundle_sha256": (
                    "e0be9ff986140ae489c88769e483d98eab06febcf9f26ebf5fc6395fb428e0b9"
                ),
            },
            verifier["contract"]["assertions"],
        )

    def test_current_spec_binds_boot_interwork_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "f2673837955194f35daab4f9fb7c0b2fe2dd5967231fcd6d982d0cacb9f749be",
            evidence["artifacts/rom-boot-interwork-v1/manifest.json"],
        )
        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/verify_rom_boot_interwork.py"
        )
        self.assertEqual(
            "66d34dc56f837e09c22fcebdd58e2e67b132c133ea7402e8d50f7e187d54984b",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-boot-interwork-verification-v1",
                "/verified": True,
                "/errors": [],
                "/artifact_schema": "rom-boot-interwork-v1",
                "/summary/root_count": 1,
                "/summary/closed_root_count": 1,
                "/summary/producer_instruction_count": 3,
                "/summary/producer_instruction_bytes": 10,
                "/summary/arm_instruction_count": 92,
                "/summary/arm_instruction_bytes": 368,
                "/summary/basic_block_count": 8,
                "/summary/edge_count": 10,
                "/summary/frontier_count": 0,
                "/summary/literal_binding_count": 9,
                "/summary/literal_pool_bytes": 36,
                "/summary/coverage_claim_count": 5,
                "/summary/classified_bytes": 414,
                "/summary/range_overlap_bytes": 0,
                "/instruction_vector_sha256": (
                    "c25c738607397cb60f90d73d7a6efe079ef52c89c11f787b0cc7d896101beebf"
                ),
                "/block_vector_sha256": (
                    "1c9d08d16c2f4c3b5cdb4123d8ae94b6fd3bb4f7921c9a28a55b77f279c3af50"
                ),
                "/edge_vector_sha256": (
                    "ba298a7c1f9f7811e7dd2ac899c7faa42d013599d9e94a6c41e129b34e7176e7"
                ),
                "/literal_binding_vector_sha256": (
                    "1e812f886d0e0abe614780f0c4a94af1c789831fd966c59e85e0a6ef690f4e9f"
                ),
            },
            verifier["contract"]["assertions"],
        )

    def test_current_spec_binds_cfg_proven_roots_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "ea1230fe24cf111a91044c059468a1467e46c471363780b23c2a0311bab8644a",
            evidence["artifacts/rom-cfg-proven-roots-v1/manifest.json"],
        )
        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/verify_rom_cfg_proven_roots.py"
        )
        self.assertEqual(
            "693d9381f429346376a6400bea20025ca0c56e1e68d0bf3164b070ea722aa4d7",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-cfg-proven-roots-verification-v1",
                "/verified": True,
                "/control_flow_oracle": "armv4t-raw-encoding",
                "/independently_rebuilt_instruction_count": 6_166,
                "/root_count": 2,
                "/decoded_instruction_count": 6_166,
                "/decoded_basic_block_count": 1_203,
                "/reachable_instruction_bytes": 12_966,
                "/frontier_count": 28,
                "/baseline_cross_edge_count": 259,
                "/errors": [],
            },
            verifier["contract"]["assertions"],
        )

    def test_current_spec_binds_cfg_proven_roots_v2_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "a3683f3d21ec5a162b4cdb97c70b639ff261d9ff5e0f3bb4941848205bb4d9ca",
            evidence["artifacts/rom-cfg-proven-roots-v2/manifest.json"],
        )
        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/verify_rom_cfg_proven_roots_v2.py"
        )
        self.assertEqual(
            "3d834e1e92c1ea1c7cf4146ac6f23b940ea864c69783c341af64ba462545fe55",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-cfg-proven-roots-verification-v2",
                "/verified": True,
                "/control_flow_oracle": "armv4t-raw-encoding",
                "/independently_rebuilt_instruction_count": 4_809,
                "/root_count": 3,
                "/decoded_instruction_count": 4_809,
                "/decoded_basic_block_count": 835,
                "/reachable_instruction_bytes": 9_876,
                "/frontier_count": 28,
                "/baseline_cross_edge_count": 82,
                "/errors": [],
            },
            verifier["contract"]["assertions"],
        )

    def test_current_partial_coverage_contract_matches_reproducible_state(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        verifier = next(
            item
            for item in specification["gates"]["rom_byte_coverage"]["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertNotIn("--require-semantic-complete", verifier["command"])
        assertions = verifier["contract"]["assertions"]
        self.assertFalse(assertions["/semantic_classification_complete"])
        self.assertEqual(149_280, assertions["/summary/unknown_bytes"])
        self.assertEqual(6_142_176, assertions["/summary/classified_bytes"])
        self.assertEqual(15_940, assertions["/summary/claim_count"])
        self.assertEqual(17_344, assertions["/summary/segment_count"])
        self.assertEqual(
            "rom-positions-aux-dispatch-v1",
            assertions["/summary/positions_aux_dispatch_promotion_batch"],
        )
        self.assertEqual(
            "positions_aux_dispatch_cell_table_bytes",
            assertions["/summary/positions_aux_dispatch_claim_kind"],
        )
        self.assertEqual(9_216, assertions["/summary/positions_aux_dispatch_bytes"])
        self.assertEqual(
            144, assertions["/summary/positions_aux_dispatch_claim_count"]
        )
        self.assertEqual(
            "47d995f09d6aaafcc4f4b4f88e3fbe81c2c4e0ea48ff10048674f1dbf6847d68",
            assertions[
                "/summary/positions_aux_dispatch_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "rom-cutscene-obj-palette-definition-alignment-gap-coverage-v1",
            assertions["/summary/cutscene_obj_alignment_gap_promotion_batch"],
        )
        self.assertEqual(
            "cutscene_obj_palette_definition_alignment_gap_bytes",
            assertions["/summary/cutscene_obj_alignment_gap_claim_kind"],
        )
        self.assertEqual(8, assertions["/summary/cutscene_obj_alignment_gap_bytes"])
        self.assertEqual(
            4, assertions["/summary/cutscene_obj_alignment_gap_claim_count"]
        )
        self.assertEqual(
            "dae7c87fa52a1e1e9f1a72279fc7839d8f26f07b126e80aca07450286abcc137",
            assertions[
                "/summary/cutscene_obj_alignment_gap_claim_denominator_sha256"
            ],
        )
        self.assertEqual(
            "374c247199713cc2e172ebff551ae7a5e40df4289437f45cf76c814e84bed5e6",
            assertions[
                "/summary/cutscene_obj_alignment_gap_range_vector_sha256"
            ],
        )
        self.assertEqual(
            "af5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc",
            assertions[
                "/summary/cutscene_obj_alignment_gap_packed_bytes_sha256"
            ],
        )
        self.assertEqual(
            "c89ed50357f1497139aa81bc29e4b67c5947608c640fc572f0ff66ed01dd8f41",
            assertions[
                "/summary/cutscene_obj_alignment_gap_independent_verifier_report_sha256"
            ],
        )
        self.assertEqual(
            "rom-boot-interwork-padding-coverage-v1",
            assertions["/summary/boot_interwork_padding_promotion_batch"],
        )
        self.assertEqual(
            "boot_interwork_veneer_alignment_nop_bytes",
            assertions["/summary/boot_interwork_padding_claim_kind"],
        )
        self.assertEqual(2, assertions["/summary/boot_interwork_padding_bytes"])
        self.assertEqual(
            1, assertions["/summary/boot_interwork_padding_claim_count"]
        )
        self.assertEqual(
            "639f595e03eb779de859b21c42fb77388cd5a93c26be5514b7c1f700fe1d09b9",
            assertions[
                "/summary/boot_interwork_padding_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "3e39ed78e50103716c788d4147df413950e5eba73c6e33acd923f15865795676",
            assertions["/summary/boot_interwork_padding_packed_bytes_sha256"],
        )
        self.assertEqual(
            "rom-dialogue-font-sjis-empty-lookup-rows-coverage-v1",
            assertions[
                "/summary/dialogue_font_sjis_empty_lookup_rows_promotion_batch"
            ],
        )
        self.assertEqual(
            "dialogue_font_sjis_empty_lookup_row_bytes",
            assertions[
                "/summary/dialogue_font_sjis_empty_lookup_rows_claim_kind"
            ],
        )
        self.assertEqual(
            40,
            assertions["/summary/dialogue_font_sjis_empty_lookup_rows_bytes"],
        )
        self.assertEqual(
            1,
            assertions[
                "/summary/dialogue_font_sjis_empty_lookup_rows_claim_count"
            ],
        )
        self.assertEqual(
            "000c60331b7d3e7da1c3597ac8ef3578b5f99a4cc24c811b5be5b38a079a676f",
            assertions[
                "/summary/dialogue_font_sjis_empty_lookup_rows_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "2c34ce1df23b838c5abf2a7f6437cca3d3067ed509ff25f11df6b11b582b51eb",
            assertions[
                "/summary/dialogue_font_sjis_empty_lookup_rows_packed_bytes_sha256"
            ],
        )
        self.assertEqual(
            "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1",
            assertions[
                "/summary/dialogue_font_sjis_empty_lookup_rows_full_table_sha256"
            ],
        )
        self.assertEqual(
            "rom-motion-spawn-sequence-descriptor-alignment-gap-coverage-v1",
            assertions[
                "/summary/motion_spawn_sequence_alignment_gap_promotion_batch"
            ],
        )
        self.assertEqual(
            "motion_spawn_sequence_descriptor_alignment_gap_bytes",
            assertions[
                "/summary/motion_spawn_sequence_alignment_gap_claim_kind"
            ],
        )
        self.assertEqual(
            2, assertions["/summary/motion_spawn_sequence_alignment_gap_bytes"]
        )
        self.assertEqual(
            1,
            assertions[
                "/summary/motion_spawn_sequence_alignment_gap_claim_count"
            ],
        )
        self.assertEqual(
            "6646067a0bc46bcc6c2fde5aa94299022ac51d7454b946048e51d929b0a58d03",
            assertions[
                "/summary/motion_spawn_sequence_alignment_gap_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "d1793f9c19b046ff1f431f28da31518c2093b77914b5c1f8b13f7e01d0ff1c6d",
            assertions[
                "/summary/motion_spawn_sequence_alignment_gap_motion_table_sha256"
            ],
        )
        self.assertEqual(
            "04d83157859089ee13c559a35bb6ab2f8814c71db59ee3f6616b917011428b9f",
            assertions[
                "/summary/motion_spawn_sequence_alignment_gap_sequence_table_sha256"
            ],
        )
        self.assertEqual(
            "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
            assertions[
                "/summary/motion_spawn_sequence_alignment_gap_packed_bytes_sha256"
            ],
        )
        self.assertEqual(
            "rom-battle-presentation-tile-assets-alignment-gap-coverage-v1",
            assertions[
                "/summary/battle_presentation_tile_assets_alignment_gap_promotion_batch"
            ],
        )
        self.assertEqual(
            "battle_presentation_tile_assets_alignment_gap_bytes",
            assertions[
                "/summary/battle_presentation_tile_assets_alignment_gap_claim_kind"
            ],
        )
        self.assertEqual(
            2,
            assertions[
                "/summary/battle_presentation_tile_assets_alignment_gap_bytes"
            ],
        )
        self.assertEqual(
            1,
            assertions[
                "/summary/battle_presentation_tile_assets_alignment_gap_claim_count"
            ],
        )
        self.assertEqual(
            "7649610dfb23720aa7a052893bf3fec739e423ddc826720e9cfa8529bea1882c",
            assertions[
                "/summary/battle_presentation_tile_assets_alignment_gap_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "8b5557e99d159b2b3ea1701bc0a15d0f2acc95f766003ec706263fc62a3719e8",
            assertions[
                "/summary/battle_presentation_tile_assets_alignment_gap_binding_table_sha256"
            ],
        )
        self.assertEqual(
            "0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73",
            assertions[
                "/summary/battle_presentation_tile_assets_alignment_gap_tile_assets_table_sha256"
            ],
        )
        self.assertEqual(
            "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
            assertions[
                "/summary/battle_presentation_tile_assets_alignment_gap_packed_bytes_sha256"
            ],
        )
        self.assertEqual(
            "rom-runtime-state-handler-table-alignment-gap-coverage-v1",
            assertions[
                "/summary/runtime_state_handler_table_alignment_gap_promotion_batch"
            ],
        )
        self.assertEqual(
            "runtime_state_handler_table_alignment_gap_bytes",
            assertions[
                "/summary/runtime_state_handler_table_alignment_gap_claim_kind"
            ],
        )
        self.assertEqual(
            2,
            assertions["/summary/runtime_state_handler_table_alignment_gap_bytes"],
        )
        self.assertEqual(
            1,
            assertions[
                "/summary/runtime_state_handler_table_alignment_gap_claim_count"
            ],
        )
        self.assertEqual(
            "11a9249d8cf1654cfbfa44bf13fa9fafc94677f7f1b075b892319e5e524f275c",
            assertions[
                "/summary/runtime_state_handler_table_alignment_gap_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "4c1ad8b8ac883eb301132c83258ba1e1216b2e131c9ce9866d0de62956d5a01b",
            assertions[
                "/summary/runtime_state_handler_table_alignment_gap_selector_table_sha256"
            ],
        )
        self.assertEqual(
            "20e4727cf65dca82626ffc9637cb36561d5851971500b22a282c5a8c65c7c945",
            assertions[
                "/summary/runtime_state_handler_table_alignment_gap_handler_table_sha256"
            ],
        )
        self.assertEqual(
            "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
            assertions[
                "/summary/runtime_state_handler_table_alignment_gap_packed_bytes_sha256"
            ],
        )
        self.assertEqual(
            "rom-direct-cpuset-bound-palette-coverage-v1",
            assertions["/summary/direct_cpuset_bound_palette_promotion_batch"],
        )
        self.assertEqual(
            "direct_cpuset_bound_palette_source_range",
            assertions["/summary/direct_cpuset_bound_palette_claim_kind"],
        )
        self.assertEqual(
            192, assertions["/summary/direct_cpuset_bound_palette_bytes"]
        )
        self.assertEqual(
            6, assertions["/summary/direct_cpuset_bound_palette_claim_count"]
        )
        self.assertEqual(
            12,
            assertions["/summary/direct_cpuset_bound_palette_candidate_count"],
        )
        self.assertEqual(
            6,
            assertions["/summary/direct_cpuset_bound_palette_preowned_count"],
        )
        self.assertEqual(
            "37ea9a17c34454a25866f790eb26b72d4b40b7a7a663b7f15366a6e3ad7fcf1f",
            assertions[
                "/summary/direct_cpuset_bound_palette_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "2381d20aeadf065b45306538b729c5b5ceecf41edcb4bbd6f3c40070a495607e",
            assertions[
                "/summary/direct_cpuset_bound_palette_candidate_denominator_sha256"
            ],
        )
        self.assertEqual(
            "4a03b75179c008e012ed89e2b571f052bd326a22cc2f1c5ae8fd82b073348225",
            assertions[
                "/summary/direct_cpuset_bound_palette_preowned_denominator_sha256"
            ],
        )
        self.assertEqual(
            "056a3625cc3a6735e56921aaec6ee37e646380bf31040cb6ad63fa8dbe757b70",
            assertions[
                "/summary/direct_cpuset_bound_palette_packed_bytes_sha256"
            ],
        )
        self.assertEqual(
            628, assertions["/summary/cfg_proven_roots_v9_extension_code_bytes"]
        )
        self.assertEqual(
            62,
            assertions["/summary/cfg_proven_roots_v9_extension_code_claim_count"],
        )
        self.assertEqual(
            "selector-direct-source-records-v1",
            assertions["/summary/selector_direct_source_record_promotion_batch"],
        )
        self.assertEqual(
            920, assertions["/summary/selector_direct_source_record_bytes"]
        )
        self.assertEqual(
            46, assertions["/summary/selector_direct_source_record_claim_count"]
        )
        self.assertEqual(
            "a4fb31202d48f65f839217585495c2dc40d29cc63b25ff7a3d5594673056e608",
            assertions[
                "/summary/selector_direct_source_record_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "rom-selector-code-windows-v1",
            assertions["/summary/selector_code_window_promotion_batch"],
        )
        self.assertEqual(
            "consumer_code_slice",
            assertions["/summary/selector_code_window_claim_kind"],
        )
        self.assertEqual(1_252, assertions["/summary/selector_code_window_bytes"])
        self.assertEqual(
            19, assertions["/summary/selector_code_window_claim_count"]
        )
        self.assertEqual(
            "1a1e50479424dbd441bc81adeca3c7d9075dc1a8ca13869e94693a71e702563e",
            assertions["/summary/selector_code_window_range_denominator_sha256"],
        )
        self.assertEqual(
            "rom-menu-portrait-palette-inventory-v1",
            assertions["/summary/menu_portrait_palette_promotion_batch"],
        )
        self.assertEqual(
            "menu_portrait_palette_source_range",
            assertions["/summary/menu_portrait_palette_claim_kind"],
        )
        self.assertEqual(8_960, assertions["/summary/menu_portrait_palette_bytes"])
        self.assertEqual(
            70, assertions["/summary/menu_portrait_palette_claim_count"]
        )
        self.assertEqual(
            "84e8b9f99a51f94e1b9e0b972d6458c883428443aa173a9f739beaf601b4e338",
            assertions["/summary/menu_portrait_palette_range_denominator_sha256"],
        )
        self.assertEqual(
            "rom-scene-visual-source-ranges-v1",
            assertions["/summary/scene_visual_source_promotion_batch"],
        )
        self.assertEqual(
            "scene_visual_source_range",
            assertions["/summary/scene_visual_source_claim_kind"],
        )
        self.assertEqual(3_257, assertions["/summary/scene_visual_source_bytes"])
        self.assertEqual(
            29, assertions["/summary/scene_visual_source_claim_count"]
        )
        self.assertEqual(
            "13dc504bebbff131700bb77869afb29e98a2f032d60bab4165eba90bcb2be7df",
            assertions["/summary/scene_visual_source_range_denominator_sha256"],
        )
        self.assertEqual(
            "rom-cutscene-obj-source-ranges-v1",
            assertions["/summary/cutscene_obj_source_promotion_batch"],
        )
        self.assertEqual(400, assertions["/summary/cutscene_obj_source_bytes"])
        self.assertEqual(
            28, assertions["/summary/cutscene_obj_source_claim_count"]
        )
        self.assertEqual(
            "c332e0ded3ae305162f774ffe1dfbbc5bbda14b534f5dd87b4f368337b8fb5a8",
            assertions["/summary/cutscene_obj_source_range_denominator_sha256"],
        )
        self.assertEqual(25_284, assertions["/summary/consumer_code_slice_bytes"])
        self.assertEqual(
            111, assertions["/summary/consumer_code_slice_claim_count"]
        )
        self.assertEqual(
            1_255, assertions["/summary/referenced_text_slot_padding_bytes"]
        )
        self.assertEqual(
            133,
            assertions["/summary/referenced_text_slot_padding_claim_count"],
        )
        self.assertEqual(
            "0d565762f2bdfd18a6aa1f8c8cd25da5347da5184fe1c78e37de9c6334259b5a",
            assertions[
                "/summary/referenced_text_slot_padding_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            11_120, assertions["/summary/battle_effect_sprite_source_bytes"]
        )
        self.assertEqual(
            237,
            assertions["/summary/battle_effect_sprite_source_claim_count"],
        )
        self.assertEqual(
            "c30b25fbed4a80914e8bc9e8d33ec7545e47a01a005866460323ac8c9b84ba30",
            assertions[
                "/summary/battle_effect_sprite_source_claim_denominator_sha256"
            ],
        )
        self.assertEqual(
            12_946,
            assertions["/summary/cfg_proven_roots_extension_code_bytes"],
        )
        self.assertEqual(
            12, assertions["/summary/cfg_proven_roots_producer_code_bytes"]
        )
        self.assertEqual(
            9_876,
            assertions["/summary/cfg_proven_roots_v2_extension_code_bytes"],
        )
        self.assertEqual(
            20, assertions["/summary/cfg_proven_roots_v2_producer_code_bytes"]
        )
        self.assertEqual(2_505, assertions["/summary/training_text_script_bytes"])
        self.assertEqual(
            44, assertions["/summary/training_text_script_claim_count"]
        )
        self.assertEqual(152, assertions["/summary/value_range_text_map_bytes"])
        self.assertEqual(
            862, assertions["/summary/value_range_renderer_text_bytes"]
        )
        self.assertEqual(324, assertions["/summary/selector_direct_text_bytes"])
        self.assertEqual(
            316, assertions["/summary/selector_configured_text_bytes"]
        )
        self.assertEqual(
            164, assertions["/summary/selector_configuration_list_bytes"]
        )
        self.assertEqual(
            12, assertions["/summary/selector_configuration_pointer_bytes"]
        )
        self.assertEqual(
            1_411, assertions["/summary/battle_message_renderer_text_bytes"]
        )
        self.assertEqual(
            1_329, assertions["/summary/battle_message_zero_padding_bytes"]
        )
        self.assertEqual(372, assertions["/summary/boot_interwork_arm_code_bytes"])
        self.assertEqual(6, assertions["/summary/boot_interwork_thumb_code_bytes"])
        self.assertEqual(36, assertions["/summary/boot_interwork_literal_pool_bytes"])

    def test_current_spec_binds_cfg_proven_roots_v10_and_exact_coverage_delta(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        self.assertEqual(
            "7bc6a70cb8409b44075df6e1031b9d80bdb19898605735dedd2a2acf9d495991",
            evidence["artifacts/rom-cfg-proven-roots-v10/manifest.json"],
        )
        v10_manifest = json.loads(
            (ROOT / "artifacts/rom-cfg-proven-roots-v10/manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            "5edad0689b630e68c6ee304aac2f56e3d5c83e65ee7c2c7a7308e0fd980fd50e",
            v10_manifest["files"]["rom-cfg-proven-roots-v10.json"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/cfg_reachable_thumb_code_bytes": 148_778,
            "/summary/cfg_promoted_unknown_bytes": 149_766,
            "/summary/cfg_primary_claim_count": 3_835,
            "/summary/cfg_proven_roots_v10_extension_code_bytes": 72,
            "/summary/cfg_proven_roots_v10_extension_code_claim_count": 7,
            "/summary/cfg_proven_roots_v10_consumed_literal_bytes": 8,
            "/summary/cfg_proven_roots_v10_consumed_literal_claim_count": 2,
            "/summary/cfg_proven_roots_v10_promotion_bytes": 80,
            "/summary/cfg_proven_roots_v10_promotion_claim_count": 9,
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"][pointer], pointer
            )

        verifier = next(
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_cfg_proven_roots_v10.py" in item["command"]
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_cfg_proven_roots_v10.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-cfg-proven-roots-v10",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "88606960fdede458a25aebc10f6e78766d16fe5cf4b08f85c3cc1e7ec1203ba3",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-cfg-proven-roots-verification-v10",
                "/verified": True,
                "/errors": [],
                "/control_flow_oracle": "armv4t-raw-encoding",
                "/source_decoded_instruction_count": 264,
                "/source_decoded_basic_block_count": 35,
                "/source_reachable_instruction_bytes": 580,
                "/source_frontier_count": 0,
                "/source_external_call_edge_count": 26,
                "/independently_rebuilt_instruction_count": 36,
                "/decoded_basic_block_count": 7,
                "/reachable_instruction_bytes": 72,
                "/frontier_count": 0,
            },
            verifier["contract"]["assertions"],
        )
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )

    def test_current_spec_binds_cfg_proven_roots_v11_and_exact_coverage_delta(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        self.assertEqual(
            "3c0a4ae64b82a417e0577d28ea82b5f774ea3150d210ed4c117414938bc2b0d4",
            evidence["artifacts/rom-cfg-proven-roots-v11/manifest.json"],
        )
        v11_manifest = json.loads(
            (ROOT / "artifacts/rom-cfg-proven-roots-v11/manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            "4d62230f3477abd29ac24790eb9fc98870c95f79e1da8df4e49783fbf6d18480",
            v11_manifest["files"]["rom-cfg-proven-roots-v11.json"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/cfg_reachable_thumb_code_bytes": 148_778,
            "/summary/cfg_promoted_unknown_bytes": 149_766,
            "/summary/cfg_primary_claim_count": 3_835,
            "/summary/cfg_proven_roots_v11_extension_code_bytes": 62,
            "/summary/cfg_proven_roots_v11_extension_code_claim_count": 6,
            "/summary/cfg_proven_roots_v11_promotion_bytes": 62,
            "/summary/cfg_proven_roots_v11_promotion_claim_count": 6,
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"][pointer], pointer
            )

        verifier = next(
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_cfg_proven_roots_v11.py" in item["command"]
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_cfg_proven_roots_v11.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-cfg-proven-roots-v11",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "4dbcd849eba9b674ed9e3739e0ce8be278a4347b7c113a98d834ac2e4a82c563",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-cfg-proven-roots-verification-v11",
                "/verified": True,
                "/errors": [],
                "/control_flow_oracle": "armv4t-raw-encoding",
                "/raw_target_producer_count": 9,
                "/accepted_target_producer_count": 8,
                "/excluded_unproven_source_count": 1,
                "/source_root_count": 8,
                "/source_decoded_instruction_count": 537,
                "/source_decoded_basic_block_count": 92,
                "/source_reachable_instruction_bytes": 1_130,
                "/source_frontier_count": 0,
                "/source_external_call_edge_count": 28,
                "/independently_rebuilt_instruction_count": 30,
                "/decoded_basic_block_count": 6,
                "/reachable_instruction_bytes": 62,
                "/frontier_count": 0,
                "/external_call_edge_count": 1,
            },
            verifier["contract"]["assertions"],
        )
        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )

    def test_current_spec_binds_cfg_proven_roots_v12_and_exact_coverage_delta(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        self.assertEqual(
            "bf88e08f4eed6b53e1debef709c2ef13fb891c11e9c172485e494eef57954677",
            evidence["artifacts/rom-cfg-proven-roots-v12/manifest.json"],
        )
        v12_manifest = json.loads(
            (ROOT / "artifacts/rom-cfg-proven-roots-v12/manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            {
                "size": 327_605,
                "sha256": "fd9df8f3d93de1df5aa7e725040f27f854d08e8203d6cada51db829ddcd9bcee",
            },
            v12_manifest["files"]["rom-cfg-proven-roots-v12.json"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/cfg_reachable_thumb_code_bytes": 148_778,
            "/summary/cfg_promoted_unknown_bytes": 149_766,
            "/summary/cfg_primary_claim_count": 3_835,
            "/summary/cfg_proven_roots_v12_extension_code_bytes": 372,
            "/summary/cfg_proven_roots_v12_extension_code_claim_count": 4,
            "/summary/cfg_proven_roots_v12_consumed_literal_bytes": 128,
            "/summary/cfg_proven_roots_v12_consumed_literal_claim_count": 4,
            "/summary/cfg_proven_roots_v12_promotion_bytes": 500,
            "/summary/cfg_proven_roots_v12_promotion_claim_count": 8,
            "/summary/cfg_proven_roots_v12_unclassified_hole_bytes": 4,
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"][pointer], pointer
            )

        verifier = next(
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_cfg_proven_roots_v12_bundle.py" in item["command"]
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_cfg_proven_roots_v12_bundle.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-cfg-proven-roots-v12",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "ee1d50f3018b5d78d652eb5ed6d1f7108670669b60e5518b9956df987b60275a",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-cfg-proven-roots-v12-bundle-verification-v1",
                "/verified": True,
                "/errors": [],
                "/artifact_schema": "rom-cfg-proven-roots-v12",
                "/artifact_status": "accepted",
                "/artifact_bundle_verified": True,
                "/legacy_receipt_verified": True,
                "/legacy_control_flow_rebuilt": True,
                "/live_coverage_verified": False,
                "/rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "/manifest_sha256": "bf88e08f4eed6b53e1debef709c2ef13fb891c11e9c172485e494eef57954677",
                "/payload_sha256": "fd9df8f3d93de1df5aa7e725040f27f854d08e8203d6cada51db829ddcd9bcee",
                "/legacy_verifier_sha256": "1043291dfb16b90ef025242b976a4bf89a6a0173a0ac4904fc3534d625acbede",
                "/wrapper_verifier_sha256": "ee1d50f3018b5d78d652eb5ed6d1f7108670669b60e5518b9956df987b60275a",
                "/promotion_bytes": 500,
                "/promotion_range_count": 8,
                "/promotion_code_bytes": 372,
                "/promotion_literal_bytes": 128,
                "/promotion_range_vector_sha256": "b2b985dee623ffe0c5e3139112d2021bffd3ea0dbd32f8ad90c9fe91b14928cd",
                "/promotion_packed_sha256": "a8043f37679964db642c2d743812d5aab93a7193016d3ffd14d805b9105cf8e8",
                "/hole_bytes": 4,
                "/holes": [[0x0644C2, 0x0644C4], [0x06450A, 0x06450C]],
                "/source_decoded_instruction_count": 237,
                "/source_decoded_basic_block_count": 40,
                "/source_reachable_instruction_bytes": 508,
                "/source_frontier_count": 0,
                "/target_decoded_instruction_count": 182,
                "/target_decoded_basic_block_count": 35,
                "/target_reachable_instruction_bytes": 372,
                "/target_frontier_count": 0,
                "/target_literal_reference_count": 35,
                "/target_unique_literal_word_count": 32,
            },
            verifier["contract"]["assertions"],
        )
        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )

    def test_current_spec_binds_cfg_proven_roots_v13_and_exact_coverage_delta(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        self.assertEqual(
            "589dd8e1536b2b6d0cc3997f31c5841204593f64ce491d6c0647ca7230f8e133",
            evidence["artifacts/rom-cfg-proven-roots-v13/manifest.json"],
        )
        v13_manifest = json.loads(
            (ROOT / "artifacts/rom-cfg-proven-roots-v13/manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            {
                "size": 312_804,
                "sha256": "45b83aeb6e91249ebd5adefdb086c438b14c666e79aab780f7072a929343cb5b",
            },
            v13_manifest["files"]["rom-cfg-proven-roots-v13.json"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/cfg_reachable_thumb_code_bytes": 148_778,
            "/summary/cfg_promoted_unknown_bytes": 149_766,
            "/summary/cfg_primary_claim_count": 3_835,
            "/summary/cfg_proven_roots_v13_extension_code_bytes": 312,
            "/summary/cfg_proven_roots_v13_extension_code_claim_count": 3,
            "/summary/cfg_proven_roots_v13_consumed_literal_bytes": 80,
            "/summary/cfg_proven_roots_v13_consumed_literal_claim_count": 3,
            "/summary/cfg_proven_roots_v13_promotion_bytes": 392,
            "/summary/cfg_proven_roots_v13_promotion_claim_count": 6,
            "/summary/cfg_proven_roots_v13_unclassified_hole_bytes": 4,
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"][pointer], pointer
            )

        verifier = next(
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_cfg_proven_roots_v13_bundle.py"
            in item["command"]
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_cfg_proven_roots_v13_bundle.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-cfg-proven-roots-v13",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "0fe1b8c1d1aa1a191d8bc7e210db952551e4b54aceeed1c13aecd9db6c12c272",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-cfg-proven-roots-v13-bundle-verification-v1",
                "/verified": True,
                "/errors": [],
                "/artifact_schema": "rom-cfg-proven-roots-v13",
                "/artifact_status": "accepted",
                "/artifact_bundle_verified": True,
                "/legacy_receipt_verified": True,
                "/legacy_control_flow_rebuilt": True,
                "/live_coverage_verified": False,
                "/rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "/manifest_sha256": "589dd8e1536b2b6d0cc3997f31c5841204593f64ce491d6c0647ca7230f8e133",
                "/payload_sha256": "45b83aeb6e91249ebd5adefdb086c438b14c666e79aab780f7072a929343cb5b",
                "/legacy_verifier_sha256": "a687af7750e9a177b47883f1b540d555bd4c666d92865d56e521f85174c869a7",
                "/wrapper_verifier_sha256": "0fe1b8c1d1aa1a191d8bc7e210db952551e4b54aceeed1c13aecd9db6c12c272",
                "/promotion_bytes": 392,
                "/promotion_range_count": 6,
                "/promotion_code_bytes": 312,
                "/promotion_literal_bytes": 80,
                "/promotion_range_vector_sha256": "09f8682f0e4bab0db4108820c4034abf45e345e05f9e7bd9c4111cc2054114c0",
                "/promotion_packed_sha256": "d7449f4feb51fa169d011c0692d2009090633aa8cf7968064bd36063be491e40",
                "/hole_bytes": 4,
                "/holes": [
                    {
                        "range": [0x0652DE, 0x0652E0],
                        "raw_hex": "0000",
                        "sha256": "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
                    },
                    {
                        "range": [0x06536A, 0x06536C],
                        "raw_hex": "0000",
                        "sha256": "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
                    },
                ],
                "/source_decoded_instruction_count": 237,
                "/source_decoded_basic_block_count": 40,
                "/source_reachable_instruction_bytes": 508,
                "/source_frontier_count": 0,
                "/target_decoded_instruction_count": 153,
                "/target_decoded_basic_block_count": 25,
                "/target_reachable_instruction_bytes": 312,
                "/target_frontier_count": 1,
                "/target_frontiers": [[0x065368, "indirect_pc_target"]],
                "/target_instruction_internal_edge_count": 164,
                "/target_block_internal_edge_count": 36,
                "/target_literal_reference_count": 21,
                "/target_unique_literal_word_count": 20,
            },
            verifier["contract"]["assertions"],
        )
        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )

    def test_current_spec_binds_u8_indexed_u16_pair_lookup_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "926c2df1b1154181b28dcb65369471f87cdb35c986ce9d0c15a942a3e6fef81a",
            evidence[
                "artifacts/rom-u8-indexed-u16-pair-lookup-v1/manifest.json"
            ],
        )

        verifier = next(
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_u8_indexed_u16_pair_lookup.py"
            in item["command"]
        )
        self.assertEqual(
            [
                "python3",
                "tools/verify_rom_u8_indexed_u16_pair_lookup.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-u8-indexed-u16-pair-lookup-v1",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "d14a0784008a61ea8770fc28cf6bcfe5e9b3a6def56382e363f2ebde6da54f76",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-u8-indexed-u16-pair-lookup-verification-v1",
                "/artifact_schema": "rom-u8-indexed-u16-pair-lookup-v1",
                "/verified": True,
                "/errors": [],
                "/rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "/logical_sha256": "adaa3da39ee951908263186ab1587a95f827b3041b4a59055da9fb54eb7cdf53",
                "/logical_cell_count": 256,
                "/logical_bytes": 1024,
                "/current_unknown_primary_bytes": 144,
                "/existing_owner_overlap_bytes": 880,
                "/base_literal_occurrence_count": 3,
                "/consumer_count": 3,
                "/json_sha256": "40d08a678b7e5dcc13afb02f50f6def28787c1a72a245dbaaf2d117efabda90c",
                "/bin_sha256": "adaa3da39ee951908263186ab1587a95f827b3041b4a59055da9fb54eb7cdf53",
                "/implementation": {
                    "exporter": {
                        "path": "tools/export_rom_u8_indexed_u16_pair_lookup.py",
                        "sha256": "568e96a8ab58329f60d38db876f0845ada7ad433c1104c736a9465fe222d3654",
                    },
                    "tests": {
                        "path": "tests/test_export_rom_u8_indexed_u16_pair_lookup.py",
                        "sha256": "103dfb3f5017d84b1c1e5da8b97fac5f9ecdef503dd08506249ff4326343b735",
                    },
                    "verifier": {
                        "path": "tools/verify_rom_u8_indexed_u16_pair_lookup.py",
                        "sha256": "d14a0784008a61ea8770fc28cf6bcfe5e9b3a6def56382e363f2ebde6da54f76",
                    },
                },
            },
            verifier["contract"]["assertions"],
        )
        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        assertions = coverage["contract"]["assertions"]
        expected_summary = {
            "/summary/u8_indexed_u16_pair_lookup_promotion_batch": "rom-u8-indexed-u16-pair-lookup-v1",
            "/summary/u8_indexed_u16_pair_lookup_claim_kind": "u8_indexed_u16_pair_lookup_bytes",
            "/summary/u8_indexed_u16_pair_lookup_bytes": 144,
            "/summary/u8_indexed_u16_pair_lookup_claim_count": 1,
            "/summary/u8_indexed_u16_pair_lookup_logical_bytes": 1024,
            "/summary/u8_indexed_u16_pair_lookup_logical_cell_count": 256,
            "/summary/u8_indexed_u16_pair_lookup_existing_owner_overlap_bytes": 880,
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(expected, assertions[pointer], pointer)

    def test_current_spec_binds_boot_thumb_handoff_cfg_inventory(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "d5af12930ed8e7539396f81deda19ae938eee3f029b95c959f6fa5d57c676d74",
            evidence[
                "artifacts/rom-boot-thumb-handoff-cfg-v1/manifest.json"
            ],
        )

        verifier = next(
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_boot_thumb_handoff_cfg.py" in item["command"]
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_boot_thumb_handoff_cfg.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-boot-thumb-handoff-cfg-v1",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "2592e4f48f1a197e30cb4d360201228fc2bbeef5fad12879b1bbf77b29815b39",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-boot-thumb-handoff-cfg-verification-v1",
                "/verified": True,
                "/errors": [],
                "/summary/block_count": 125,
                "/summary/instruction_count": 583,
                "/summary/instruction_bytes": 1226,
                "/summary/internal_edge_count": 164,
                "/summary/external_edge_count": 14,
                "/summary/external_target_count": 11,
                "/summary/literal_ref_count": 77,
                "/summary/literal_word_count": 74,
                "/summary/literal_bytes": 296,
                "/summary/return_count": 14,
                "/summary/raw_indirect_pc_count": 15,
                "/summary/frontier_count": 2,
                "/summary/budget_exhausted": False,
                "/promotion/code_bytes": 1226,
                "/promotion/code_range_count": 27,
                "/promotion/literal_bytes": 296,
                "/promotion/literal_range_count": 22,
                "/promotion/union_bytes": 1522,
                "/promotion/union_range_count": 25,
                "/promotion/current_known_overlap_bytes": 0,
                "/promotion/future_coverage_claim_projection/code_claim_count": 27,
                "/promotion/future_coverage_claim_projection/literal_claim_count": 22,
                "/promotion/future_coverage_claim_projection/semantically_merged_union_claim_count": 0,
                "/promotion/union_bytes_sha256": "73033e06942ec6604fe036849e40c420728f6f9bd4ae5db6c0fe49ba6eca2f22",
                "/promotion/union_range_vector_sha256": "f8df15ea8c3feb1a9c460bd0a2aabd79572806100ed726ada64b360aabb92aa5",
                "/promotion/wide_envelope": [397228, 639128],
                "/promotion/wide_envelope_is_claim": False,
            },
            verifier["contract"]["assertions"],
        )
        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        assertions = coverage["contract"]["assertions"]
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/boot_thumb_handoff_promotion_batch": "rom-boot-thumb-handoff-cfg-v1",
            "/summary/boot_thumb_handoff_code_bytes": 1226,
            "/summary/boot_thumb_handoff_code_claim_count": 27,
            "/summary/boot_thumb_handoff_literal_bytes": 296,
            "/summary/boot_thumb_handoff_literal_claim_count": 22,
            "/summary/boot_thumb_handoff_union_bytes": 1522,
            "/summary/boot_thumb_handoff_promotion_claim_count": 49,
            "/summary/boot_thumb_handoff_union_range_count": 25,
            "/summary/boot_thumb_handoff_union_range_vector_sha256": "f8df15ea8c3feb1a9c460bd0a2aabd79572806100ed726ada64b360aabb92aa5",
            "/summary/boot_thumb_handoff_frontier_count": 2,
            "/summary/boot_thumb_handoff_return_count": 14,
            "/summary/cfg_reachable_thumb_code_bytes": 148_778,
            "/summary/cfg_promoted_unknown_bytes": 149_766,
            "/summary/cfg_primary_claim_count": 3_835,
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(expected, assertions[pointer], pointer)
        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )

    def test_current_spec_binds_task_scheduler_core_and_exact_coverage_delta(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        self.assertEqual(
            "88ef48526ed1bd096a8ece9a58aa4f5770f207084634a125f04dc99561c7d58c",
            evidence["artifacts/rom-task-scheduler-core-v1/manifest.json"],
        )

        verifier = next(
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_task_scheduler_core_bundle.py" in item["command"]
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_task_scheduler_core_bundle.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-task-scheduler-core-v1",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "13f3d3d31127572ce401d694ffee796b4ca4434c064f08a013b5a9e506565f70",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-task-scheduler-core-bundle-verification-v1",
                "/verified": True,
                "/errors": [],
                "/artifact_schema": "rom-task-scheduler-core-v1",
                "/artifact_status": "accepted",
                "/artifact_bundle_verified": True,
                "/legacy_receipt_verified": True,
                "/live_coverage_verified": False,
                "/rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "/promotion_bytes": 308,
                "/promotion_claim_count": 7,
                "/promotion_range_count": 7,
                "/unclassified_historical_bytes": 6,
                "/legacy_verifier_sha256": "90133f94b749dbd3d2d08404ac3be5a7a275f261076c82c8c01312271760d9f4",
                "/bundle_verifier_sha256": "13f3d3d31127572ce401d694ffee796b4ca4434c064f08a013b5a9e506565f70",
                "/summary/block_count": 33,
                "/summary/budget_exhausted": False,
                "/summary/code_bytes": 264,
                "/summary/external_edge_count": 5,
                "/summary/external_target_count": 4,
                "/summary/frontier_count": 1,
                "/summary/instruction_bytes": 264,
                "/summary/instruction_count": 116,
                "/summary/internal_edge_count": 33,
                "/summary/literal_bytes": 44,
                "/summary/literal_ref_count": 12,
                "/summary/literal_word_count": 11,
                "/summary/owned_provenance_bytes": 138,
                "/summary/promoted_bytes": 308,
                "/summary/raw_indirect_pc_count": 12,
                "/summary/return_count": 12,
                "/summary/unclassified_unknown_bytes": 6,
                "/promotion/code_bytes": 264,
                "/promotion/code_range_count": 4,
                "/promotion/current_known_overlap_bytes": 0,
                "/promotion/future_coverage_claim_projection/code_claim_count": 4,
                "/promotion/future_coverage_claim_projection/literal_claim_count": 3,
                "/promotion/future_coverage_claim_projection/owned_claim_count": 0,
                "/promotion/future_coverage_claim_projection/unclassified_claim_count": 0,
                "/promotion/literal_bytes": 44,
                "/promotion/literal_range_count": 3,
                "/promotion/owned_provenance_bytes": 138,
                "/promotion/owned_provenance_ranges": [
                    [400764, 400874],
                    [400896, 400924],
                ],
                "/promotion/unclassified_unknown_bytes": 6,
                "/promotion/unclassified_unknown_ranges": [
                    [400738, 400740],
                    [400762, 400764],
                    [400874, 400876],
                ],
                "/promotion/union_bytes": 308,
                "/promotion/union_bytes_sha256": "2cdbf5ee8ee1f24e9d5590363f05cf177c21821209d8b735666b4844c829842f",
                "/promotion/union_range_count": 3,
                "/promotion/union_range_vector_sha256": "094ce63366d095869c1826cb58de52d19849049bcb6312ca3f3009fdea31852f",
                "/promotion/union_ranges": [
                    [400472, 400738],
                    [400740, 400762],
                    [400876, 400896],
                ],
            },
            verifier["contract"]["assertions"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/cfg_reachable_thumb_code_bytes": 148_778,
            "/summary/cfg_promoted_unknown_bytes": 149_766,
            "/summary/cfg_primary_claim_count": 3_835,
            "/summary/task_scheduler_core_promotion_batch": "rom-task-scheduler-core-v1",
            "/summary/task_scheduler_core_code_claim_kind": "task_scheduler_core_reachable_instruction_bytes",
            "/summary/task_scheduler_core_literal_claim_kind": "task_scheduler_core_consumed_literal_bytes",
            "/summary/task_scheduler_core_code_bytes": 264,
            "/summary/task_scheduler_core_code_claim_count": 4,
            "/summary/task_scheduler_core_literal_bytes": 44,
            "/summary/task_scheduler_core_literal_claim_count": 3,
            "/summary/task_scheduler_core_promoted_bytes": 308,
            "/summary/task_scheduler_core_promotion_claim_count": 7,
            "/summary/task_scheduler_core_gap_bytes": 6,
            "/summary/task_scheduler_core_gap_range_count": 3,
            "/summary/task_scheduler_core_owned_provenance_bytes": 138,
            "/summary/task_scheduler_core_owned_provenance_range_count": 2,
            "/summary/task_scheduler_core_union_range_count": 3,
            "/summary/task_scheduler_core_union_range_vector_sha256": "094ce63366d095869c1826cb58de52d19849049bcb6312ca3f3009fdea31852f",
            "/summary/task_scheduler_core_frontier_count": 1,
            "/summary/task_scheduler_core_return_count": 12,
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"][pointer], pointer
            )
        self.assertIn(
            "The task scheduler core artifact classifies exactly 264 bounded "
            "Thumb instruction bytes and 44 consumed literal bytes; 138 "
            "already-owned bytes remain provenance and three two-byte gaps "
            "remain unknown. Dynamic callback targets, callback lifecycle, "
            "natural runtime reachability, global caller/code/indirect "
            "denominators, scheduler business semantics, editing, relocation, "
            "and allocatable space remain unclaimed.",
            gate["limitations"],
        )
        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )

    def test_current_spec_binds_directsound_pitch_lookup_and_exact_coverage_delta(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        self.assertEqual(
            "61f58bd4309d3b63389bdd09ddd62281dee6fe6ce91bcce0c351ce703012805d",
            evidence["artifacts/rom-directsound-pitch-lookup-v1/manifest.json"],
        )

        verifier = next(
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_directsound_pitch_lookup_bundle.py"
            in item["command"]
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_directsound_pitch_lookup_bundle.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-directsound-pitch-lookup-v1",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "319e72a642a510145da93c18615ea12964f5b04b54fb42662897308ffd617ea1",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-directsound-pitch-lookup-bundle-verification-v1",
                "/verified": True,
                "/errors": [],
                "/artifact_schema": "rom-directsound-pitch-lookup-v1",
                "/artifact_status": "accepted",
                "/artifact_bundle_verified": True,
                "/legacy_receipt_verified": True,
                "/live_coverage_verified": False,
                "/rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "/promotion_bytes": 344,
                "/promotion_claim_count": 5,
                "/promotion_range_count": 5,
                "/promotion_packed_sha256": "cdf62999570f66a283667ed85f535da4e04f8cbf5ea8a33ef66d1bee8ab0e850",
                "/legacy_verifier_sha256": "d4947c8e3081374122b2e7fcd78be3caf3586e892a557965c19e2054986d8250",
                "/bundle_verifier_sha256": "319e72a642a510145da93c18615ea12964f5b04b54fb42662897308ffd617ea1",
                "/legacy_report/schema": "rom-directsound-pitch-lookup-verification-v1",
                "/legacy_report/verified": True,
                "/legacy_report/errors": [],
                "/legacy_report/artifact_schema": "rom-directsound-pitch-lookup-v1",
                "/legacy_report/artifact_status": "accepted",
                "/legacy_report/rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "/legacy_report/coverage_baseline_sha256": "5c3c9bcaa90a4d55a2de5ef37effbd9947502aff75f01b73738b90aa704b0d9f",
                "/legacy_report/coverage_contract_verified": True,
                "/legacy_report/promotion_bytes": 344,
                "/legacy_report/promotion_claim_count": 5,
                "/legacy_report/promotion_range_count": 5,
                "/legacy_report/promotion_packed_sha256": "cdf62999570f66a283667ed85f535da4e04f8cbf5ea8a33ef66d1bee8ab0e850",
                "/legacy_report/producer_count": 2,
                "/legacy_report/consumer_instruction_count": 44,
                "/legacy_report/consumer_block_count": 5,
                "/legacy_report/consumer_frontier_count": 0,
                "/legacy_report/helper_instruction_count": 5,
                "/legacy_report/verifier_sha256": "d4947c8e3081374122b2e7fcd78be3caf3586e892a557965c19e2054986d8250",
            },
            verifier["contract"]["assertions"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/directsound_pitch_lookup_promotion_batch": "rom-directsound-pitch-lookup-v1",
            "/summary/directsound_pitch_lookup_bytes": 344,
            "/summary/directsound_pitch_lookup_claim_count": 5,
            "/summary/directsound_pitch_lookup_range_vector_sha256": "ac877e8eec80edbdab3d1b6f3991fc8a93dfc497a66c298dc9ee0c29034431bd",
            "/summary/directsound_pitch_lookup_packed_bytes_sha256": "cdf62999570f66a283667ed85f535da4e04f8cbf5ea8a33ef66d1bee8ab0e850",
            "/summary/directsound_pitch_lookup_class_bytes": {
                "armv4t_directsound_pitch_high32_interwork_code": 16,
                "armv4t_directsound_pitch_consumer_thumb_code": 92,
                "directsound_pitch_table_pointer_literals": 8,
                "directsound_pitch_scale_descriptor_table": 180,
                "directsound_pitch_frequency_u32_table": 48,
            },
            "/summary/directsound_pitch_lookup_class_claim_counts": {
                "armv4t_directsound_pitch_high32_interwork_code": 1,
                "armv4t_directsound_pitch_consumer_thumb_code": 1,
                "directsound_pitch_table_pointer_literals": 1,
                "directsound_pitch_scale_descriptor_table": 1,
                "directsound_pitch_frequency_u32_table": 1,
            },
            "/summary/directsound_pitch_lookup_producer_count": 2,
            "/summary/directsound_pitch_lookup_consumer_instruction_count": 44,
            "/summary/directsound_pitch_lookup_consumer_block_count": 5,
            "/summary/directsound_pitch_lookup_consumer_frontier_count": 0,
            "/summary/directsound_pitch_lookup_helper_instruction_count": 5,
            "/summary/directsound_pitch_lookup_helper_block_count": 2,
            "/summary/directsound_pitch_lookup_helper_frontier_count": 0,
            "/summary/directsound_pitch_lookup_scale_descriptor_count": 180,
            "/summary/directsound_pitch_lookup_frequency_entry_count": 12,
            "/summary/directsound_pitch_lookup_frequency_index_domain": [0, 11],
            "/summary/directsound_pitch_lookup_shift_domain": [0, 14],
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"][pointer], pointer
            )
        self.assertIn(
            "The DirectSound pitch lookup artifact classifies exactly 344 "
            "frozen bytes: a 16-byte mixed Thumb/ARM high32 helper, a 92-byte "
            "bounded Thumb consumer, eight consumed pointer-literal bytes, 180 "
            "u8 scale descriptors, and twelve little-endian u32 frequencies. "
            "Its proof is limited to the target-bounded two-producer raw Thumb "
            "BL denominator, closed consumer CFG and structured return, helper "
            "interwork, literal bindings, and exhaustive u8 table-index domains; "
            "producer bytes and source-instruction membership, natural runtime "
            "reachability, global code/caller/indirect or computed/RAM consumer "
            "denominators, playback behavior, editing, writeback, relocation, "
            "and allocatable space remain unclaimed.",
            gate["limitations"],
        )
        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )

    def test_current_spec_binds_psg_frequency_lookup_and_exact_coverage_delta(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        self.assertEqual(
            "4fffbcc7e252595834adb368d10b3ce8f13323aee18cc518d98e0ff9c519575f",
            evidence["artifacts/rom-psg-frequency-lookup-v1/manifest.json"],
        )

        verifier = next(
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_psg_frequency_lookup_bundle.py" in item["command"]
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_psg_frequency_lookup_bundle.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-psg-frequency-lookup-v1",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "f9bb2bed9239fd298e97438458df218c5640ae3a4c2b90c6a6dc6f0b5ed05e58",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-psg-frequency-lookup-bundle-verification-v1",
                "/verified": True,
                "/errors": [],
                "/artifact_schema": "rom-psg-frequency-lookup-v1",
                "/artifact_status": "accepted",
                "/artifact_bundle_verified": True,
                "/legacy_receipt_verified": True,
                "/live_coverage_verified": False,
                "/rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "/promotion_bytes": 226,
                "/promotion_claim_count": 5,
                "/promotion_range_count": 5,
                "/promotion_packed_sha256": "e625a5fcc208a971a1ec98723f12b863a707fa9dd3ba8442f7f6d86b3099623b",
                "/producer_count": 0,
                "/consumer_instruction_count": 77,
                "/consumer_block_count": 12,
                "/consumer_frontier_count": 0,
                "/legacy_verifier_sha256": "c87ab33b067a35a0105e21967dc0caad5fe91368942f34baf91218d69258f616",
                "/bundle_verifier_sha256": "f9bb2bed9239fd298e97438458df218c5640ae3a4c2b90c6a6dc6f0b5ed05e58",
                "/legacy_report/schema": "rom-psg-frequency-lookup-verification-v1",
                "/legacy_report/verified": True,
                "/legacy_report/errors": [],
                "/legacy_report/artifact_schema": "rom-psg-frequency-lookup-v1",
                "/legacy_report/artifact_status": "accepted",
                "/legacy_report/rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "/legacy_report/coverage_baseline_sha256": "922e06e9b195a31ae6a8ab8c03cb06159aee7218bc4268ac56e22c729b740de6",
                "/legacy_report/coverage_contract_verified": True,
                "/legacy_report/promotion_bytes": 226,
                "/legacy_report/promotion_claim_count": 5,
                "/legacy_report/promotion_range_count": 5,
                "/legacy_report/promotion_packed_sha256": "e625a5fcc208a971a1ec98723f12b863a707fa9dd3ba8442f7f6d86b3099623b",
                "/legacy_report/producer_count": 0,
                "/legacy_report/consumer_instruction_count": 77,
                "/legacy_report/consumer_block_count": 12,
                "/legacy_report/consumer_frontier_count": 0,
                "/legacy_report/verifier_sha256": "c87ab33b067a35a0105e21967dc0caad5fe91368942f34baf91218d69258f616",
            },
            verifier["contract"]["assertions"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/psg_frequency_lookup_promotion_batch": "rom-psg-frequency-lookup-v1",
            "/summary/psg_frequency_lookup_bytes": 226,
            "/summary/psg_frequency_lookup_claim_count": 5,
            "/summary/psg_frequency_lookup_range_vector_sha256": "5247ee79350c15d6292e52a5e1ef58bd7b7555f50a70bc157e3e936b8ffa0080",
            "/summary/psg_frequency_lookup_packed_bytes_sha256": "e625a5fcc208a971a1ec98723f12b863a707fa9dd3ba8442f7f6d86b3099623b",
            "/summary/psg_frequency_lookup_semantic_range_vector_sha256": "6683ef2206af27246bc97abb750a02023ea18909611b7dbda9e1987419e515eb",
            "/summary/psg_frequency_lookup_class_bytes": {
                "armv4t_psg_frequency_lookup_thumb_code": 154,
                "psg_frequency_lookup_consumed_pointer_literals": 12,
                "psg_noise_register_descriptor_table": 60,
            },
            "/summary/psg_frequency_lookup_class_claim_counts": {
                "armv4t_psg_frequency_lookup_thumb_code": 2,
                "psg_frequency_lookup_consumed_pointer_literals": 2,
                "psg_noise_register_descriptor_table": 1,
            },
            "/summary/psg_frequency_lookup_direct_branch_producer_count": 0,
            "/summary/psg_frequency_lookup_thumb_pointer_occurrence_count": 1,
            "/summary/psg_frequency_lookup_consumer_instruction_count": 77,
            "/summary/psg_frequency_lookup_consumer_block_count": 12,
            "/summary/psg_frequency_lookup_consumer_frontier_count": 0,
            "/summary/psg_frequency_lookup_noise_table_entry_count": 60,
            "/summary/psg_frequency_lookup_noise_index_domain": [0, 59],
            "/summary/psg_frequency_lookup_unclassified_gap_bytes": 2,
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"][pointer], pointer
            )
        self.assertIn(
            "The PSG frequency lookup artifact classifies exactly 226 frozen "
            "bytes: 154 bytes in two bounded Thumb code ranges, twelve bytes in "
            "three consumed pointer literals, and a 60-byte channel-4 noise "
            "register descriptor table. The two-byte 0x09B4C6..0x09B4C8 "
            "alignment gap remains unknown. Entry proof is limited to one fixed "
            "initializer-to-logical-SoundInfo+0x30-to-BX-r3 chain; global "
            "RAM/computed producers, writers, indirect callers, natural runtime "
            "reachability, the two non-noise target-table semantics, playback, "
            "editing, writeback, relocation, and allocatable space remain "
            "unclaimed.",
            gate["limitations"],
        )
        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )

    def test_current_spec_binds_u8_indexed_u8_triplet_lookup_and_exact_coverage_delta(
        self,
    ):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "54dacd5ceb13025b7878b90961016bb67cc5d8cacbf1a8408be4faae4efa933c",
            evidence[
                "artifacts/rom-u8-indexed-u8-triplet-lookup-v1/manifest.json"
            ],
        )
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )

        verifier = next(
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_u8_indexed_u8_triplet_lookup_bundle.py"
            in item["command"]
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_u8_indexed_u8_triplet_lookup_bundle.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-u8-indexed-u8-triplet-lookup-v1",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "8a396e54268a89cab7d92fcd78e3aacce297faf45c077b3d81ef9b013b1eea96",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-u8-indexed-u8-triplet-lookup-bundle-verification-v1",
                "/artifact_schema": "rom-u8-indexed-u8-triplet-lookup-v1",
                "/artifact_status": "accepted",
                "/artifact_bundle_verified": True,
                "/legacy_receipt_verified": True,
                "/live_coverage_verified": False,
                "/verified": True,
                "/errors": [],
                "/rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "/legacy_report/coverage_baseline_sha256": "5432e12ff0aa9bd2722f7e18e169ac0d82d67f6a1afd4601a8d0011e502eba89",
                "/promotion_claim_count": 2,
                "/promotion_range_count": 2,
                "/promotion_bytes": 19,
                "/promotion_range_vector_sha256": "99af22b0af2f42931bb29c3cbe187ff8836b1f651504eea40a45eb5be108d87f",
                "/promotion_packed_sha256": "4439669abd06a2c350f23e705c750821694c15e2f92a083bc00c89ab7506dcc6",
                "/consumer_instruction_count": 134,
                "/consumer_block_count": 28,
                "/consumer_frontier_count": 0,
                "/table_record_count": 5,
                "/legacy_report/json_sha256": "3c50f5a0f330c656ccaf26a5c8dcc29d032225e8ab0a45070d7452e48cc30891",
                "/legacy_report/bin_sha256": "4439669abd06a2c350f23e705c750821694c15e2f92a083bc00c89ab7506dcc6",
                "/legacy_report/verifier_sha256": "f1649387a243d30340801d8fcd5000c9b628d87cb5b2a94707f3102876e88a06",
                "/legacy_verifier_sha256": "f1649387a243d30340801d8fcd5000c9b628d87cb5b2a94707f3102876e88a06",
                "/bundle_verifier_sha256": "8a396e54268a89cab7d92fcd78e3aacce297faf45c077b3d81ef9b013b1eea96",
            },
            verifier["contract"]["assertions"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/u8_indexed_u8_triplet_lookup_promotion_batch": (
                "rom-u8-indexed-u8-triplet-lookup-v1"
            ),
            "/summary/u8_indexed_u8_triplet_lookup_bytes": 19,
            "/summary/u8_indexed_u8_triplet_lookup_claim_count": 2,
            "/summary/u8_indexed_u8_triplet_lookup_range_vector_sha256": (
                "99af22b0af2f42931bb29c3cbe187ff8836b1f651504eea40a45eb5be108d87f"
            ),
            "/summary/u8_indexed_u8_triplet_lookup_packed_bytes_sha256": (
                "4439669abd06a2c350f23e705c750821694c15e2f92a083bc00c89ab7506dcc6"
            ),
            "/summary/u8_indexed_u8_triplet_lookup_class_bytes": {
                "fixed_consumer_triplet_pointer_literal": 4,
                "fixed_consumer_triplet_table": 15,
            },
            "/summary/u8_indexed_u8_triplet_lookup_class_claim_counts": {
                "fixed_consumer_triplet_pointer_literal": 1,
                "fixed_consumer_triplet_table": 1,
            },
            "/summary/u8_indexed_u8_triplet_lookup_pointer_occurrence_count": 1,
            "/summary/u8_indexed_u8_triplet_lookup_table_record_count": 5,
            "/summary/u8_indexed_u8_triplet_lookup_index_domain": [0, 4],
            "/summary/u8_indexed_u8_triplet_lookup_consumer_instruction_provenance_count": 134,
            "/summary/u8_indexed_u8_triplet_lookup_consumer_block_provenance_count": 28,
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"][pointer], pointer
            )
        self.assertIn(
            "The u8-indexed u8-triplet lookup artifact classifies exactly 19 "
            "current-unknown bytes: one consumed four-byte pointer literal and "
            "one fifteen-byte five-by-three raw u8 record table. The 272 "
            "consumer code bytes retain their existing generic CFG owners and "
            "are provenance only; four literal pools and the right-hand "
            "diagnostic range remain unknown. The frozen static r5=0..4 and "
            "3*i field-load binding does not prove a newly closed CFG, return "
            "epilogue, natural runtime reachability, business field semantics, "
            "editing, relocation, or allocatable space.",
            gate["limitations"],
        )
        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )

    def test_current_spec_binds_artifact_bound_alignment_gaps_and_exact_coverage_delta(
        self,
    ):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )

        matches = [
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_artifact_bound_alignment_gaps.py"
            in item["command"]
        ]
        self.assertEqual(1, len(matches))
        verifier = matches[0]
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_artifact_bound_alignment_gaps.py",
                "--root",
                ".",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "784970276d8974c1390a4f33a12950dd5a2d2faefb894d7b7cc3856f38198227",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-artifact-bound-alignment-gaps-verification-v1",
                "/verified": True,
                "/errors": [],
                "/rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "/promotion_batch": "rom-artifact-bound-alignment-gaps-v1",
                "/primary_class": "artifact_bound_4byte_alignment_bytes",
                "/claim_kind": "artifact_bound_alignment_gap_bytes",
                "/gap_count": 13,
                "/byte_count": 26,
                "/zero_byte_count": 26,
                "/ranges": [
                    [0x061D62, 0x061D64],
                    [0x061D7A, 0x061D7C],
                    [0x061DEA, 0x061DEC],
                    [0x09B4C6, 0x09B4C8],
                    [0x09B572, 0x09B574],
                    [0x09B586, 0x09B588],
                    [0x09B676, 0x09B678],
                    [0x09B696, 0x09B698],
                    [0x09B702, 0x09B704],
                    [0x09B762, 0x09B764],
                    [0x09B94A, 0x09B94C],
                    [0x09B96E, 0x09B970],
                    [0x09B9E2, 0x09B9E4],
                ],
                "/range_vector_sha256": "d6582d3ca46f1bacb82537740370874320c79592f3c9512747affd4db5285741",
                "/boundary_vector_sha256": "7dd56d026c90f090f3b4fbceb055bbe3db35786e915e4ace4ae61a6b06230843",
                "/claim_denominator_sha256": "1962c626da011e7ac32287662593e55cea72d5d21b003a419e78085a087b8d46",
                "/source_file_vector_sha256": "d14919e7abafeb1891e1336d0511b5ab0e44ef6091ee010ca842ca6c6fd3f92f",
                "/packed_bytes_sha256": "659d36ca563ba4622daabb36a71dafaf6060cdcbf89bb12e75426198496d272c",
                "/right_kind_counts": {
                    "consumed_literal_range": 12,
                    "owned_thumb_function": 1,
                },
                "/source_artifact_count": 4,
                "/all_alignment_equations_hold": True,
                "/all_boundaries_exact": True,
                "/padding_semantics_claimed": False,
                "/nop_instruction_claimed": False,
                "/reserved_space_claimed": False,
                "/free_space_claimed": False,
                "/allocatable_space_claimed": False,
                "/natural_runtime_reachability_claimed": False,
                "/global_unreachability_claimed": False,
                "/compiler_authorship_claimed": False,
                "/editing_writeback_relocation_safe_claimed": False,
                "/right_structure_semantics_extended_claimed": False,
                "/all_alignment_gaps_exhaustive_claimed": False,
            },
            verifier["contract"]["assertions"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/artifact_bound_alignment_gap_promotion_batch": (
                "rom-artifact-bound-alignment-gaps-v1"
            ),
            "/summary/artifact_bound_alignment_gap_bytes": 26,
            "/summary/artifact_bound_alignment_gap_claim_count": 13,
            "/summary/artifact_bound_alignment_gap_claim_denominator_sha256": (
                "1962c626da011e7ac32287662593e55cea72d5d21b003a419e78085a087b8d46"
            ),
            "/summary/artifact_bound_alignment_gap_range_vector_sha256": (
                "d6582d3ca46f1bacb82537740370874320c79592f3c9512747affd4db5285741"
            ),
            "/summary/artifact_bound_alignment_gap_packed_bytes_sha256": (
                "659d36ca563ba4622daabb36a71dafaf6060cdcbf89bb12e75426198496d272c"
            ),
            "/summary/artifact_bound_alignment_gap_independent_verifier_report_sha256": (
                "58c8b2f9badfa2bb40edb570ddef879ab56412bdf4e477e9e16f074ebc121d28"
            ),
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"][pointer], pointer
            )
        self.assertIn(
            "A separate artifact-bound boundary verifier classifies exactly "
            "thirteen two-byte ranges totaling 26 bytes between accepted "
            "scheduler, PSG, CGB helper, or CgbSound structures under an exact "
            "align4 equation. The "
            "historical source artifact statements that these ranges were "
            "unknown remain scope-local receipts and are superseded only for "
            "these thirteen ranges. No instruction, NOP, padding, reserved/free/"
            "allocatable-space, natural-reachability, compiler-authorship, "
            "editing, writeback, relocation, right-structure semantic "
            "extension, or exhaustive-gap claim is made.",
            gate["limitations"],
        )
        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )

    def test_current_spec_binds_cgb_bounded_cfgs_and_exact_coverage_delta(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        self.assertEqual(
            "8a53b3ee982799583e08ef852fb2cac9771f856e77ed104cc2814cfd1e7ef6d1",
            evidence["artifacts/rom-cgb-helper-bounded-cfg-v1/manifest.json"],
        )
        self.assertEqual(
            "4248c0fed46682d06918ac124d3c861a60c12117023a773190ff831840963b6e",
            evidence["artifacts/rom-cgbsound-bounded-cfg-v1/manifest.json"],
        )

        bundle_matches = [
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_cgb_bounded_cfg_bundle.py" in item["command"]
        ]
        self.assertEqual(1, len(bundle_matches))
        bundle = bundle_matches[0]
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_cgb_bounded_cfg_bundle.py",
                "--root",
                ".",
            ],
            bundle["command"],
        )
        self.assertEqual(
            "4461680b6d01cbfc5e5f61c53129f2a1eb3dec2a11b9452fa0b3796b8a2136ee",
            bundle["script_sha256"],
        )
        bundle_assertions = bundle["contract"]["assertions"]
        self.assertEqual(
            "rom-cgb-bounded-cfg-bundle-verification-v1",
            bundle_assertions["/schema"],
        )
        self.assertTrue(bundle_assertions["/verified"])
        self.assertEqual([], bundle_assertions["/errors"])
        self.assertEqual(2, bundle_assertions["/artifact_count"])
        self.assertEqual(1_264, bundle_assertions["/promotion_bytes"])
        self.assertEqual(28, bundle_assertions["/promotion_claim_count"])
        self.assertEqual(
            "8a53b3ee982799583e08ef852fb2cac9771f856e77ed104cc2814cfd1e7ef6d1",
            bundle_assertions["/artifacts/rom-cgb-helper-bounded-cfg-v1"][
                "manifest_sha256"
            ],
        )
        self.assertEqual(
            "4248c0fed46682d06918ac124d3c861a60c12117023a773190ff831840963b6e",
            bundle_assertions["/artifacts/rom-cgbsound-bounded-cfg-v1"][
                "manifest_sha256"
            ],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/cgb_helper_bounded_cfg_promotion_batch": (
                "rom-cgb-helper-bounded-cfg-v1"
            ),
            "/summary/cgb_helper_bounded_cfg_code_bytes": 164,
            "/summary/cgb_helper_bounded_cfg_literal_bytes": 16,
            "/summary/cgb_helper_bounded_cfg_promoted_bytes": 180,
            "/summary/cgb_helper_bounded_cfg_promotion_claim_count": 9,
            "/summary/cgb_helper_bounded_cfg_range_vector_sha256": (
                "ea942377babe2613c9affe8711b6480f6e9e27e60da7aeb483112790de3b85b3"
            ),
            "/summary/cgb_helper_bounded_cfg_packed_bytes_sha256": (
                "87c62bbe5f0e9d25ee5b11398ecdd3ed5b41782d4873871205f71c1122a4c1dc"
            ),
            "/summary/cgb_helper_bounded_cfg_manifest_sha256": (
                "8a53b3ee982799583e08ef852fb2cac9771f856e77ed104cc2814cfd1e7ef6d1"
            ),
            "/summary/cgb_helper_bounded_cfg_payload_sha256": (
                "dccdca087744e57136b180dba1c3e4151c123efecec10d5d53f90894dc760960"
            ),
            "/summary/cgb_helper_bounded_cfg_independent_verifier_sha256": (
                "d09f828511215b59fe8b60ba4bcf7e63fca48fc36d4c105e75175fa3b11179f3"
            ),
            "/summary/cgbsound_bounded_cfg_promotion_batch": (
                "rom-cgbsound-bounded-cfg-v1"
            ),
            "/summary/cgbsound_bounded_cfg_code_bytes": 1_008,
            "/summary/cgbsound_bounded_cfg_literal_bytes": 76,
            "/summary/cgbsound_bounded_cfg_promoted_bytes": 1_084,
            "/summary/cgbsound_bounded_cfg_promotion_claim_count": 19,
            "/summary/cgbsound_bounded_cfg_range_vector_sha256": (
                "3386a673407d2191f9b9427725f95e3864b92009ea32de433d28c9665c618f57"
            ),
            "/summary/cgbsound_bounded_cfg_packed_bytes_sha256": (
                "edebdbe6e5cf5f9cf04fdb93839846f7e37e6516914b77a7517413c88ee9a151"
            ),
            "/summary/cgbsound_bounded_cfg_manifest_sha256": (
                "4248c0fed46682d06918ac124d3c861a60c12117023a773190ff831840963b6e"
            ),
            "/summary/cgbsound_bounded_cfg_payload_sha256": (
                "362a3dc1b5819a57310482b7fbdd94bb2f79e9d439ea44713798140d1d79b18d"
            ),
            "/summary/cgbsound_bounded_cfg_independent_verifier_sha256": (
                "6af3510f319c58cdb9cf70c115f6a1b2b3ffc0b4fb331f247604dbdb8e637961"
            ),
            "/summary/artifact_bound_alignment_gap_bytes": 26,
            "/summary/artifact_bound_alignment_gap_claim_count": 13,
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"][pointer], pointer
            )
        evidence_paths = [item["path"] for item in gate["evidence"]]
        self.assertLess(
            evidence_paths.index(
                "artifacts/rom-cgb-helper-bounded-cfg-v1/manifest.json"
            ),
            evidence_paths.index(
                "artifacts/rom-cgbsound-bounded-cfg-v1/manifest.json"
            ),
        )
        verifier_scripts = [
            item["command"][3]
            for item in gate["verifiers"]
            if len(item["command"]) > 3
        ]
        self.assertLess(
            verifier_scripts.index("tools/verify_rom_cgb_bounded_cfg_bundle.py"),
            verifier_scripts.index("tools/verify_rom_artifact_bound_alignment_gaps.py"),
        )
        self.assertIn(
            "The accepted bounded CGB helper artifact promotes exactly 180 "
            "bytes in nine frozen ranges: 164 bytes of bounded Thumb code and "
            "16 bytes of instruction-consumed literals. Two intervening "
            "two-byte align4 ranges are excluded here and classified only by "
            "the separate artifact-bound boundary verifier. Natural runtime "
            "reachability, literal business semantics, complete callers or "
            "RAM writers, audio behavior, editing, relocation, writeback, and "
            "allocatable space remain unclaimed.",
            gate["limitations"],
        )
        self.assertIn(
            "The accepted bounded CgbSound artifact promotes exactly 1,084 "
            "bytes in nineteen frozen ranges: 1,008 bytes of bounded Thumb "
            "code and 76 bytes of instruction-consumed literals. Seven "
            "intervening two-byte align4 ranges are excluded here and "
            "classified only by the separate artifact-bound boundary "
            "verifier. Natural runtime reachability, dynamic callback or RAM "
            "state, helper or literal business semantics, audio behavior, "
            "editing, relocation, writeback, and allocatable space remain "
            "unclaimed.",
            gate["limitations"],
        )
        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )

    def test_current_spec_binds_m4a_initializer_chain_and_exact_coverage_delta(
        self,
    ):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}

        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        self.assertEqual(
            "9b9b9f2f49a1ee8224703ca47b73dc608d75ba83d2be44564e24873c44237c9c",
            evidence["artifacts/rom-m4a-initializer-chain-v1/manifest.json"],
        )

        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][3]
            == "tools/verify_rom_m4a_initializer_chain.py"
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_m4a_initializer_chain.py",
                "artifacts/rom-m4a-initializer-chain-v1",
                "--root",
                ".",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "5cd9ccf232ebb10c69e89962e9861add7675dfb935c6e6a293b16049fd6cec31",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-m4a-initializer-chain-verification-v1",
                "/verified": True,
                "/contract_ok": True,
                "/artifact_status": "accepted",
                "/summary": {
                    "block_count": 25,
                    "code_bytes": 390,
                    "direct_call_count": 7,
                    "external_edge_count": 7,
                    "frontier_count": 0,
                    "gap_exclusion_bytes": 2,
                    "instruction_bytes": 390,
                    "instruction_count": 188,
                    "internal_block_edge_count": 31,
                    "internal_edge_count": 31,
                    "literal_bytes": 128,
                    "literal_ref_count": 33,
                    "literal_word_count": 32,
                    "producer_count": 3,
                    "promoted_bytes": 518,
                    "promotion_claim_count": 6,
                    "promotion_range_count": 6,
                    "structured_return_count": 3,
                    "unresolved_frontier_count": 0,
                },
                "/bundle_sha256": "f5c0a94ac06bf6750edc038e0db95fc5d4e96c321129e57a11abd461aa678ea7",
                "/payload_sha256": "7f019b01e800a3dd769463cbea907049429b1cad416dc17ed8719a561837babd",
                "/manifest_sha256": "9b9b9f2f49a1ee8224703ca47b73dc608d75ba83d2be44564e24873c44237c9c",
                "/coverage_baseline_sha256": "31cf4a9c14666345482cad325433814e7fe26d458327c3bc5d9a13e680616563",
            },
            verifier["contract"]["assertions"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/m4a_initializer_chain_promotion_batch": "rom-m4a-initializer-chain-v1",
            "/summary/m4a_initializer_chain_code_claim_kind": "m4a_initializer_chain_bounded_thumb_code",
            "/summary/m4a_initializer_chain_literal_claim_kind": "m4a_initializer_chain_consumed_literal_bytes",
            "/summary/m4a_initializer_chain_code_bytes": 390,
            "/summary/m4a_initializer_chain_code_claim_count": 3,
            "/summary/m4a_initializer_chain_literal_bytes": 128,
            "/summary/m4a_initializer_chain_literal_claim_count": 3,
            "/summary/m4a_initializer_chain_promoted_bytes": 518,
            "/summary/m4a_initializer_chain_promotion_claim_count": 6,
            "/summary/m4a_initializer_chain_union_range_count": 4,
            "/summary/m4a_initializer_chain_union_range_vector_sha256": "8bcba07694e7375d59dddeb3cb12eeb4903e61147c91723482d61d06a47dbd72",
            "/summary/m4a_initializer_chain_producer_count": 3,
            "/summary/m4a_initializer_chain_gap_bytes": 2,
            "/summary/m4a_initializer_chain_gap_range_count": 1,
            "/summary/m4a_initializer_chain_frontier_count": 0,
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"][pointer], pointer
            )
        self.assertIn(
            "The M4A initializer-chain artifact classifies exactly 390 "
            "bounded Thumb instruction bytes and 128 instruction-consumed "
            "literal bytes in three target-limited roots. The raw producer "
            "at 0x061E28 and the two-byte return-to-pool gap at "
            "0x09B1E6 remain unknown; dynamic RAM/callback values, natural "
            "reachability, global caller/code/indirect/computed producer "
            "denominators, literal-target semantics, audio behavior, "
            "editing, relocation, writeback, and allocatable space remain "
            "unclaimed.",
            gate["limitations"],
        )

    def test_current_spec_binds_mp2k_note_allocator_and_exact_coverage_delta(
        self,
    ):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}

        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        self.assertEqual(
            "a2f61cb3596c8e48294ba07c710a2681bbe8ca8173c6d9288beccd5dd3e1cf8a",
            evidence["artifacts/rom-mp2k-note-allocator-v1/manifest.json"],
        )

        verifier = next(
            item
            for item in gate["verifiers"]
            if item["command"][3]
            == "tools/verify_rom_mp2k_note_allocator.py"
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_mp2k_note_allocator.py",
                "artifacts/rom-mp2k-note-allocator-v1",
                "--root",
                ".",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "177d1fb694b01f5938d6169438cd454db0ff7a1e826cf101b32630ffc51d9716",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-mp2k-note-allocator-verification-v1",
                "/verified": True,
                "/contract_ok": True,
                "/artifact_status": "accepted",
                "/summary": {
                    "block_count": 66,
                    "budget_exhausted": False,
                    "code_bytes": 550,
                    "direct_call_count": 6,
                    "external_edge_count": 5,
                    "frontier_count": 0,
                    "gap_exclusion_bytes": 68,
                    "included_root_call_edge_count": 1,
                    "instruction_bytes": 550,
                    "instruction_count": 269,
                    "internal_edge_count": 99,
                    "literal_bytes": 8,
                    "literal_ref_count": 2,
                    "literal_word_count": 2,
                    "opaque_external_call_count": 5,
                    "ordinary_internal_edge_count": 98,
                    "pointer_bytes": 4,
                    "producer_count": 3,
                    "promoted_bytes": 562,
                    "promotion_claim_count": 4,
                    "promotion_range_count": 4,
                    "structured_return_count": 2,
                    "unresolved_frontier_count": 0,
                },
                "/bundle_sha256": "3c3a1dab618964db40570b65c28ae08500a30392c65c25d870291ee5abb1587c",
                "/payload_sha256": "a4ccf706d2c8db658b6fa402d13155c73d15e84c197f9da4e8975759a14b0fa6",
                "/manifest_sha256": "a2f61cb3596c8e48294ba07c710a2681bbe8ca8173c6d9288beccd5dd3e1cf8a",
                "/coverage_baseline_sha256": "ab315087593f23bfbcc96c66ac99b8bfd002e5c29cd462088dda343139f9ac27",
            },
            verifier["contract"]["assertions"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/mp2k_note_allocator_promotion_batch": "rom-mp2k-note-allocator-v1",
            "/summary/mp2k_note_allocator_code_bytes": 550,
            "/summary/mp2k_note_allocator_literal_bytes": 8,
            "/summary/mp2k_note_allocator_pointer_bytes": 4,
            "/summary/mp2k_note_allocator_promoted_bytes": 562,
            "/summary/mp2k_note_allocator_promotion_claim_count": 4,
            "/summary/mp2k_note_allocator_union_range_vector_sha256": "bd9139f26305fea7813e7daf944d6a6e131861b31c3c98065b5e7d13bf65c88b",
            "/summary/mp2k_note_allocator_excluded_bytes": 68,
            "/summary/mp2k_note_allocator_accepted_value_count": 49,
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"][pointer], pointer
            )
        self.assertIn(
            "The MP2K note-allocator artifact classifies exactly 550 bounded "
            "Thumb instruction bytes, 8 instruction-consumed literal bytes, "
            "and one 4-byte initializer-consumed Thumb entry pointer in four "
            "accepted ranges. Four neighboring ranges totaling 68 bytes "
            "remain unknown; natural runtime reachability, global caller/code/"
            "indirect/computed producer and RAM-writer denominators, literal-"
            "target semantics, audio behavior, editing, relocation, writeback, "
            "and allocatable space remain unclaimed.",
            gate["limitations"],
        )

    def test_current_spec_binds_mp2k_dispatcher_and_exact_coverage_delta(self):
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}

        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        self.assertEqual(
            "212c3849eb8ead7fd01c74f8ed8a1ae85b4f2324d966fa2234320a6b78882b48",
            evidence["artifacts/rom-mp2k-dispatcher-v1/manifest.json"],
        )

        verifier = next(
            item
            for item in gate["verifiers"]
            if len(item["command"]) > 3
            and item["command"][3] == "tools/verify_rom_mp2k_dispatcher.py"
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_mp2k_dispatcher.py",
                "artifacts/rom-mp2k-dispatcher-v1",
                "--root",
                ".",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "3b342efd7ec63cc38b3eb862a881ca7c562873375a9264fdb58fe5b752bd7397",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": "rom-mp2k-dispatcher-verification-v1",
                "/verified": True,
                "/contract_ok": True,
                "/artifact_status": "accepted",
                "/summary": {
                    "block_count": 36,
                    "budget_exhausted": False,
                    "code_bytes": 260,
                    "external_edge_count": 1,
                    "frontier_count": 0,
                    "gap_exclusion_bytes": 4,
                    "instruction_bytes": 260,
                    "instruction_count": 129,
                    "internal_edge_count": 65,
                    "literal_bytes": 8,
                    "literal_ref_count": 1,
                    "literal_word_count": 1,
                    "pointer_bytes": 0,
                    "producer_count": 19,
                    "promoted_bytes": 102,
                    "promotion_claim_count": 4,
                    "promotion_range_count": 4,
                    "resolved_dispatch_edge_count": 18,
                    "structured_return_count": 1,
                    "total_graph_edge_count": 66,
                    "unresolved_frontier_count": 0,
                },
                "/bundle_sha256": (
                    "83f220623fff3f5effb8bf6cd21b7e7ce8d543ab660d7fa721b8632bd26b3bd5"
                ),
                "/payload_sha256": (
                    "3ddac8d6c690af4850d74f7aeeee2a424f32c4108a7ebebd26c51f280672b23c"
                ),
                "/manifest_sha256": (
                    "212c3849eb8ead7fd01c74f8ed8a1ae85b4f2324d966fa2234320a6b78882b48"
                ),
                "/coverage_baseline_sha256": (
                    "3926d1cd6e09c8b45b85cb33d0b2f77d83578ec71c17d61fa1282d863f220735"
                ),
            },
            verifier["contract"]["assertions"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/mp2k_dispatcher_promotion_batch": "rom-mp2k-dispatcher-v1",
            "/summary/mp2k_dispatcher_code_bytes": 86,
            "/summary/mp2k_dispatcher_table_tail_bytes": 12,
            "/summary/mp2k_dispatcher_literal_bytes": 4,
            "/summary/mp2k_dispatcher_promoted_bytes": 102,
            "/summary/mp2k_dispatcher_promotion_claim_count": 4,
            "/summary/mp2k_dispatcher_union_range_vector_sha256": (
                "f7621079a8d84ce92aeebf1855856f30c0d8e551aed692531139bd6dccb39171"
            ),
            "/summary/mp2k_dispatcher_excluded_bytes": 4,
            "/summary/mp2k_dispatcher_accepted_value_count": 18,
            "/summary/mp2k_dispatcher_existing_owner_provenance_bytes": 238,
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"][pointer], pointer
            )
        self.assertIn(
            "The MP2K dispatcher artifact classifies exactly 86 bounded "
            "Thumb instruction bytes, 12 fixed table-tail bytes, and 4 "
            "instruction-consumed literal bytes in four accepted ranges. "
            "Five pre-existing owner ranges totaling 238 bytes remain "
            "provenance only and two 2-byte gaps remain unknown; natural "
            "runtime reachability, global caller/code/indirect/computed "
            "producer and RAM-writer denominators, literal-target semantics, "
            "audio behavior, editing, relocation, writeback, and allocatable "
            "space remain unclaimed.",
            gate["limitations"],
        )

    def test_current_repository_does_not_overclaim_completion(self):
        result = audit_proof(ROOT, SPEC)
        self.assertFalse(result["complete"])
        self.assertEqual(result["claim_status"], "incomplete")
        self.assertEqual(32, result["banks_proof_bound"])
        self.assertEqual(32, result["banks_with_valid_evidence"])
        self.assertEqual(21, result["banks_with_hash_bound_offline_verifier"])
        self.assertEqual(10, result["banks_with_contracted_verifier"])
        self.assertEqual(10, result["banks_complete"])
        self.assertEqual(
            {"records_total": 2954, "records_covered": 23},
            result["declared_runtime_record_coverage"],
        )
        self.assertFalse(result["trust_anchor"]["verified"])
        self.assertFalse(
            result["gate_results"]["rom_byte_coverage"]["rom_coverage_audit"][
                "semantic_classification_complete"
            ]
        )
        rom_gate = result["gate_results"]["rom_byte_coverage"]
        self.assertTrue(rom_gate["evidence_valid"])
        self.assertEqual(96, rom_gate["hash_bound_verifier_count"])
        self.assertEqual(92, rom_gate["contracted_verifier_count"])
        self.assertEqual([], rom_gate["rom_coverage_audit"].get("errors"))
        self.assertIn("summary", rom_gate["rom_coverage_audit"])
        self.assertEqual(
            144_416,
            rom_gate["rom_coverage_audit"]["summary"]["dialogue_font_bytes"],
        )
        self.assertEqual(
            155_188,
            rom_gate["rom_coverage_audit"]["summary"]["boot_framebuffer_bytes"],
        )
        self.assertEqual(
            14,
            rom_gate["rom_coverage_audit"]["summary"][
                "boot_framebuffer_claim_count"
            ],
        )
        self.assertEqual(
            149_280,
            rom_gate["rom_coverage_audit"]["summary"]["unknown_bytes"],
        )
        self.assertEqual(
            6_142_176,
            rom_gate["rom_coverage_audit"]["summary"]["classified_bytes"],
        )
        self.assertEqual(
            15_940,
            rom_gate["rom_coverage_audit"]["summary"]["claim_count"],
        )
        self.assertEqual(
            17_344,
            rom_gate["rom_coverage_audit"]["summary"]["segment_count"],
        )
        self.assertEqual(
            "rom-positions-aux-dispatch-v1",
            rom_gate["rom_coverage_audit"]["summary"]
            ["positions_aux_dispatch_promotion_batch"],
        )
        self.assertEqual(
            "positions_aux_dispatch_cell_table_bytes",
            rom_gate["rom_coverage_audit"]["summary"]
            ["positions_aux_dispatch_claim_kind"],
        )
        self.assertEqual(
            9_216,
            rom_gate["rom_coverage_audit"]["summary"]
            ["positions_aux_dispatch_bytes"],
        )
        self.assertEqual(
            144,
            rom_gate["rom_coverage_audit"]["summary"]
            ["positions_aux_dispatch_claim_count"],
        )
        self.assertEqual(
            "47d995f09d6aaafcc4f4b4f88e3fbe81c2c4e0ea48ff10048674f1dbf6847d68",
            rom_gate["rom_coverage_audit"]["summary"]
            ["positions_aux_dispatch_range_denominator_sha256"],
        )
        self.assertEqual(
            "rom-cutscene-obj-palette-definition-alignment-gap-coverage-v1",
            rom_gate["rom_coverage_audit"]["summary"]
            ["cutscene_obj_alignment_gap_promotion_batch"],
        )
        self.assertEqual(
            "cutscene_obj_palette_definition_alignment_gap_bytes",
            rom_gate["rom_coverage_audit"]["summary"]
            ["cutscene_obj_alignment_gap_claim_kind"],
        )
        self.assertEqual(
            8,
            rom_gate["rom_coverage_audit"]["summary"]
            ["cutscene_obj_alignment_gap_bytes"],
        )
        self.assertEqual(
            4,
            rom_gate["rom_coverage_audit"]["summary"]
            ["cutscene_obj_alignment_gap_claim_count"],
        )
        self.assertEqual(
            "dae7c87fa52a1e1e9f1a72279fc7839d8f26f07b126e80aca07450286abcc137",
            rom_gate["rom_coverage_audit"]["summary"]
            ["cutscene_obj_alignment_gap_claim_denominator_sha256"],
        )
        self.assertEqual(
            "374c247199713cc2e172ebff551ae7a5e40df4289437f45cf76c814e84bed5e6",
            rom_gate["rom_coverage_audit"]["summary"]
            ["cutscene_obj_alignment_gap_range_vector_sha256"],
        )
        self.assertEqual(
            "af5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc",
            rom_gate["rom_coverage_audit"]["summary"]
            ["cutscene_obj_alignment_gap_packed_bytes_sha256"],
        )
        self.assertEqual(
            "c89ed50357f1497139aa81bc29e4b67c5947608c640fc572f0ff66ed01dd8f41",
            rom_gate["rom_coverage_audit"]["summary"]
            ["cutscene_obj_alignment_gap_independent_verifier_report_sha256"],
        )
        self.assertEqual(
            "rom-dialogue-font-sjis-empty-lookup-rows-coverage-v1",
            rom_gate["rom_coverage_audit"]["summary"]
            ["dialogue_font_sjis_empty_lookup_rows_promotion_batch"],
        )
        self.assertEqual(
            "dialogue_font_sjis_empty_lookup_row_bytes",
            rom_gate["rom_coverage_audit"]["summary"]
            ["dialogue_font_sjis_empty_lookup_rows_claim_kind"],
        )
        self.assertEqual(
            40,
            rom_gate["rom_coverage_audit"]["summary"]
            ["dialogue_font_sjis_empty_lookup_rows_bytes"],
        )
        self.assertEqual(
            1,
            rom_gate["rom_coverage_audit"]["summary"]
            ["dialogue_font_sjis_empty_lookup_rows_claim_count"],
        )
        self.assertEqual(
            "000c60331b7d3e7da1c3597ac8ef3578b5f99a4cc24c811b5be5b38a079a676f",
            rom_gate["rom_coverage_audit"]["summary"]
            ["dialogue_font_sjis_empty_lookup_rows_range_denominator_sha256"],
        )
        self.assertEqual(
            "2c34ce1df23b838c5abf2a7f6437cca3d3067ed509ff25f11df6b11b582b51eb",
            rom_gate["rom_coverage_audit"]["summary"]
            ["dialogue_font_sjis_empty_lookup_rows_packed_bytes_sha256"],
        )
        self.assertEqual(
            "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1",
            rom_gate["rom_coverage_audit"]["summary"]
            ["dialogue_font_sjis_empty_lookup_rows_full_table_sha256"],
        )
        self.assertEqual(
            "rom-motion-spawn-sequence-descriptor-alignment-gap-coverage-v1",
            rom_gate["rom_coverage_audit"]["summary"]
            ["motion_spawn_sequence_alignment_gap_promotion_batch"],
        )
        self.assertEqual(
            "motion_spawn_sequence_descriptor_alignment_gap_bytes",
            rom_gate["rom_coverage_audit"]["summary"]
            ["motion_spawn_sequence_alignment_gap_claim_kind"],
        )
        self.assertEqual(
            2,
            rom_gate["rom_coverage_audit"]["summary"]
            ["motion_spawn_sequence_alignment_gap_bytes"],
        )
        self.assertEqual(
            1,
            rom_gate["rom_coverage_audit"]["summary"]
            ["motion_spawn_sequence_alignment_gap_claim_count"],
        )
        self.assertEqual(
            "6646067a0bc46bcc6c2fde5aa94299022ac51d7454b946048e51d929b0a58d03",
            rom_gate["rom_coverage_audit"]["summary"]
            ["motion_spawn_sequence_alignment_gap_range_denominator_sha256"],
        )
        self.assertEqual(
            "d1793f9c19b046ff1f431f28da31518c2093b77914b5c1f8b13f7e01d0ff1c6d",
            rom_gate["rom_coverage_audit"]["summary"]
            ["motion_spawn_sequence_alignment_gap_motion_table_sha256"],
        )
        self.assertEqual(
            "04d83157859089ee13c559a35bb6ab2f8814c71db59ee3f6616b917011428b9f",
            rom_gate["rom_coverage_audit"]["summary"]
            ["motion_spawn_sequence_alignment_gap_sequence_table_sha256"],
        )
        self.assertEqual(
            "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
            rom_gate["rom_coverage_audit"]["summary"]
            ["motion_spawn_sequence_alignment_gap_packed_bytes_sha256"],
        )
        self.assertEqual(
            "rom-battle-presentation-tile-assets-alignment-gap-coverage-v1",
            rom_gate["rom_coverage_audit"]["summary"]
            ["battle_presentation_tile_assets_alignment_gap_promotion_batch"],
        )
        self.assertEqual(
            "battle_presentation_tile_assets_alignment_gap_bytes",
            rom_gate["rom_coverage_audit"]["summary"]
            ["battle_presentation_tile_assets_alignment_gap_claim_kind"],
        )
        self.assertEqual(
            2,
            rom_gate["rom_coverage_audit"]["summary"]
            ["battle_presentation_tile_assets_alignment_gap_bytes"],
        )
        self.assertEqual(
            1,
            rom_gate["rom_coverage_audit"]["summary"]
            ["battle_presentation_tile_assets_alignment_gap_claim_count"],
        )
        self.assertEqual(
            "7649610dfb23720aa7a052893bf3fec739e423ddc826720e9cfa8529bea1882c",
            rom_gate["rom_coverage_audit"]["summary"]
            ["battle_presentation_tile_assets_alignment_gap_range_denominator_sha256"],
        )
        self.assertEqual(
            "8b5557e99d159b2b3ea1701bc0a15d0f2acc95f766003ec706263fc62a3719e8",
            rom_gate["rom_coverage_audit"]["summary"]
            ["battle_presentation_tile_assets_alignment_gap_binding_table_sha256"],
        )
        self.assertEqual(
            "0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73",
            rom_gate["rom_coverage_audit"]["summary"]
            ["battle_presentation_tile_assets_alignment_gap_tile_assets_table_sha256"],
        )
        self.assertEqual(
            "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
            rom_gate["rom_coverage_audit"]["summary"]
            ["battle_presentation_tile_assets_alignment_gap_packed_bytes_sha256"],
        )
        self.assertEqual(
            "rom-runtime-state-handler-table-alignment-gap-coverage-v1",
            rom_gate["rom_coverage_audit"]["summary"]
            ["runtime_state_handler_table_alignment_gap_promotion_batch"],
        )
        self.assertEqual(
            "runtime_state_handler_table_alignment_gap_bytes",
            rom_gate["rom_coverage_audit"]["summary"]
            ["runtime_state_handler_table_alignment_gap_claim_kind"],
        )
        self.assertEqual(
            2,
            rom_gate["rom_coverage_audit"]["summary"]
            ["runtime_state_handler_table_alignment_gap_bytes"],
        )
        self.assertEqual(
            1,
            rom_gate["rom_coverage_audit"]["summary"]
            ["runtime_state_handler_table_alignment_gap_claim_count"],
        )
        self.assertEqual(
            "11a9249d8cf1654cfbfa44bf13fa9fafc94677f7f1b075b892319e5e524f275c",
            rom_gate["rom_coverage_audit"]["summary"]
            ["runtime_state_handler_table_alignment_gap_range_denominator_sha256"],
        )
        self.assertEqual(
            "4c1ad8b8ac883eb301132c83258ba1e1216b2e131c9ce9866d0de62956d5a01b",
            rom_gate["rom_coverage_audit"]["summary"]
            ["runtime_state_handler_table_alignment_gap_selector_table_sha256"],
        )
        self.assertEqual(
            "20e4727cf65dca82626ffc9637cb36561d5851971500b22a282c5a8c65c7c945",
            rom_gate["rom_coverage_audit"]["summary"]
            ["runtime_state_handler_table_alignment_gap_handler_table_sha256"],
        )
        self.assertEqual(
            "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
            rom_gate["rom_coverage_audit"]["summary"]
            ["runtime_state_handler_table_alignment_gap_packed_bytes_sha256"],
        )
        self.assertEqual(
            1_255,
            rom_gate["rom_coverage_audit"]["summary"]
            ["referenced_text_slot_padding_bytes"],
        )
        self.assertEqual(
            133,
            rom_gate["rom_coverage_audit"]["summary"]
            ["referenced_text_slot_padding_claim_count"],
        )
        self.assertEqual(
            "selector-direct-source-records-v1",
            rom_gate["rom_coverage_audit"]["summary"]
            ["selector_direct_source_record_promotion_batch"],
        )
        self.assertEqual(
            920,
            rom_gate["rom_coverage_audit"]["summary"]
            ["selector_direct_source_record_bytes"],
        )
        self.assertEqual(
            46,
            rom_gate["rom_coverage_audit"]["summary"]
            ["selector_direct_source_record_claim_count"],
        )
        self.assertEqual(
            "a4fb31202d48f65f839217585495c2dc40d29cc63b25ff7a3d5594673056e608",
            rom_gate["rom_coverage_audit"]["summary"]
            ["selector_direct_source_record_range_denominator_sha256"],
        )
        self.assertEqual(
            "rom-selector-code-windows-v1",
            rom_gate["rom_coverage_audit"]["summary"]
            ["selector_code_window_promotion_batch"],
        )
        self.assertEqual(
            1_252,
            rom_gate["rom_coverage_audit"]["summary"]["selector_code_window_bytes"],
        )
        self.assertEqual(
            19,
            rom_gate["rom_coverage_audit"]["summary"]
            ["selector_code_window_claim_count"],
        )
        self.assertEqual(
            "rom-menu-portrait-palette-inventory-v1",
            rom_gate["rom_coverage_audit"]["summary"]
            ["menu_portrait_palette_promotion_batch"],
        )
        self.assertEqual(
            8_960,
            rom_gate["rom_coverage_audit"]["summary"]
            ["menu_portrait_palette_bytes"],
        )
        self.assertEqual(
            70,
            rom_gate["rom_coverage_audit"]["summary"]
            ["menu_portrait_palette_claim_count"],
        )
        self.assertEqual(
            "84e8b9f99a51f94e1b9e0b972d6458c883428443aa173a9f739beaf601b4e338",
            rom_gate["rom_coverage_audit"]["summary"]
            ["menu_portrait_palette_range_denominator_sha256"],
        )
        self.assertEqual(
            "rom-scene-visual-source-ranges-v1",
            rom_gate["rom_coverage_audit"]["summary"]
            ["scene_visual_source_promotion_batch"],
        )
        self.assertEqual(
            3_257,
            rom_gate["rom_coverage_audit"]["summary"]["scene_visual_source_bytes"],
        )
        self.assertEqual(
            29,
            rom_gate["rom_coverage_audit"]["summary"]
            ["scene_visual_source_claim_count"],
        )
        self.assertEqual(
            "13dc504bebbff131700bb77869afb29e98a2f032d60bab4165eba90bcb2be7df",
            rom_gate["rom_coverage_audit"]["summary"]
            ["scene_visual_source_range_denominator_sha256"],
        )
        self.assertEqual(
            "rom-cutscene-obj-source-ranges-v1",
            rom_gate["rom_coverage_audit"]["summary"]
            ["cutscene_obj_source_promotion_batch"],
        )
        self.assertEqual(
            400,
            rom_gate["rom_coverage_audit"]["summary"]["cutscene_obj_source_bytes"],
        )
        self.assertEqual(
            28,
            rom_gate["rom_coverage_audit"]["summary"]
            ["cutscene_obj_source_claim_count"],
        )
        self.assertEqual(
            "c332e0ded3ae305162f774ffe1dfbbc5bbda14b534f5dd87b4f368337b8fb5a8",
            rom_gate["rom_coverage_audit"]["summary"]
            ["cutscene_obj_source_range_denominator_sha256"],
        )
        self.assertEqual(
            11_120,
            rom_gate["rom_coverage_audit"]["summary"][
                "battle_effect_sprite_source_bytes"
            ],
        )
        self.assertEqual(
            237,
            rom_gate["rom_coverage_audit"]["summary"][
                "battle_effect_sprite_source_claim_count"
            ],
        )
        self.assertEqual(
            "c30b25fbed4a80914e8bc9e8d33ec7545e47a01a005866460323ac8c9b84ba30",
            rom_gate["rom_coverage_audit"]["summary"][
                "battle_effect_sprite_source_claim_denominator_sha256"
            ],
        )
        self.assertEqual(
            3_919,
            rom_gate["rom_coverage_audit"]["summary"][
                "verified_artifact_reuse_bytes"
            ],
        )
        self.assertEqual(
            37,
            rom_gate["rom_coverage_audit"]["summary"][
                "verified_artifact_reuse_claim_count"
            ],
        )
        self.assertEqual(
            16_814,
            rom_gate["rom_coverage_audit"]["summary"][
                "dialogue_inter_record_zero_padding_bytes"
            ],
        )
        self.assertEqual(
            1_219,
            rom_gate["rom_coverage_audit"]["summary"][
                "dialogue_inter_record_zero_padding_claim_count"
            ],
        )
        self.assertEqual(
            149_766,
            rom_gate["rom_coverage_audit"]["summary"][
                "cfg_promoted_unknown_bytes"
            ],
        )
        self.assertEqual(
            148_778,
            rom_gate["rom_coverage_audit"]["summary"][
                "cfg_reachable_thumb_code_bytes"
            ],
        )
        self.assertEqual(
            3_835,
            rom_gate["rom_coverage_audit"]["summary"][
                "cfg_primary_claim_count"
            ],
        )
        self.assertEqual(
            628,
            rom_gate["rom_coverage_audit"]["summary"][
                "cfg_proven_roots_v9_extension_code_bytes"
            ],
        )
        self.assertEqual(
            62,
            rom_gate["rom_coverage_audit"]["summary"][
                "cfg_proven_roots_v9_extension_code_claim_count"
            ],
        )
        self.assertEqual(
            12_946,
            rom_gate["rom_coverage_audit"]["summary"][
                "cfg_proven_roots_extension_code_bytes"
            ],
        )
        self.assertEqual(
            12,
            rom_gate["rom_coverage_audit"]["summary"][
                "cfg_proven_roots_producer_code_bytes"
            ],
        )
        self.assertEqual(
            9_876,
            rom_gate["rom_coverage_audit"]["summary"][
                "cfg_proven_roots_v2_extension_code_bytes"
            ],
        )
        self.assertEqual(
            20,
            rom_gate["rom_coverage_audit"]["summary"][
                "cfg_proven_roots_v2_producer_code_bytes"
            ],
        )
        self.assertEqual(
            9_060,
            rom_gate["rom_coverage_audit"]["summary"][
                "cfg_v3_extension_code_bytes"
            ],
        )
        self.assertEqual(
            448,
            rom_gate["rom_coverage_audit"]["summary"][
                "cfg_v3_dispatch_table_bytes"
            ],
        )
        self.assertEqual(
            14_725,
            rom_gate["rom_coverage_audit"]["summary"][
                "unbound_lz77_syntax_bytes"
            ],
        )
        self.assertEqual(
            334_060,
            rom_gate["rom_coverage_audit"]["summary"]["chapter_script_bytes"],
        )
        self.assertEqual(
            92,
            rom_gate["rom_coverage_audit"]["summary"][
                "chapter_script_claim_count"
            ],
        )
        self.assertEqual(
            86,
            rom_gate["rom_coverage_audit"]["summary"][
                "sprite_tile_offset_table_bytes"
            ],
        )
        self.assertEqual(
            251,
            rom_gate["rom_coverage_audit"]["summary"][
                "chapter_speaker_label_bytes"
            ],
        )
        self.assertEqual(
            22_588,
            rom_gate["rom_coverage_audit"]["summary"]["renderer_text_bytes"],
        )
        self.assertEqual(
            6_798,
            rom_gate["rom_coverage_audit"]["summary"]["profile_text_bytes"],
        )
        self.assertEqual(
            46,
            rom_gate["rom_coverage_audit"]["summary"]["profile_text_claim_count"],
        )
        self.assertEqual(
            38,
            rom_gate["rom_coverage_audit"]["summary"][
                "profile_text_alignment_padding_bytes"
            ],
        )
        self.assertEqual(
            19,
            rom_gate["rom_coverage_audit"]["summary"][
                "profile_text_alignment_padding_claim_count"
            ],
        )
        self.assertEqual(
            3_000,
            rom_gate["rom_coverage_audit"]["summary"][
                "fixed_consumer_pointer_table_bytes"
            ],
        )
        self.assertEqual(
            11,
            rom_gate["rom_coverage_audit"]["summary"][
                "fixed_consumer_pointer_table_claim_count"
            ],
        )
        self.assertEqual(
            11_177,
            rom_gate["rom_coverage_audit"]["summary"][
                "fixed_consumer_renderer_text_bytes"
            ],
        )
        self.assertEqual(
            735,
            rom_gate["rom_coverage_audit"]["summary"][
                "fixed_consumer_renderer_text_claim_count"
            ],
        )
        self.assertEqual(
            2_505,
            rom_gate["rom_coverage_audit"]["summary"][
                "training_text_script_bytes"
            ],
        )
        self.assertEqual(
            44,
            rom_gate["rom_coverage_audit"]["summary"][
                "training_text_script_claim_count"
            ],
        )
        self.assertEqual(
            152,
            rom_gate["rom_coverage_audit"]["summary"][
                "value_range_text_map_bytes"
            ],
        )
        self.assertEqual(
            862,
            rom_gate["rom_coverage_audit"]["summary"][
                "value_range_renderer_text_bytes"
            ],
        )
        self.assertEqual(
            1_411,
            rom_gate["rom_coverage_audit"]["summary"][
                "battle_message_renderer_text_bytes"
            ],
        )
        self.assertEqual(
            1_329,
            rom_gate["rom_coverage_audit"]["summary"][
                "battle_message_zero_padding_bytes"
            ],
        )
        self.assertEqual(
            372,
            rom_gate["rom_coverage_audit"]["summary"][
                "boot_interwork_arm_code_bytes"
            ],
        )
        self.assertEqual(
            6,
            rom_gate["rom_coverage_audit"]["summary"][
                "boot_interwork_thumb_code_bytes"
            ],
        )
        self.assertEqual(
            36,
            rom_gate["rom_coverage_audit"]["summary"][
                "boot_interwork_literal_pool_bytes"
            ],
        )
        self.assertEqual(
            "rom-boot-interwork-padding-coverage-v1",
            rom_gate["rom_coverage_audit"]["summary"][
                "boot_interwork_padding_promotion_batch"
            ],
        )
        self.assertEqual(
            "boot_interwork_veneer_alignment_nop_bytes",
            rom_gate["rom_coverage_audit"]["summary"][
                "boot_interwork_padding_claim_kind"
            ],
        )
        self.assertEqual(
            2,
            rom_gate["rom_coverage_audit"]["summary"][
                "boot_interwork_padding_bytes"
            ],
        )
        self.assertEqual(
            1,
            rom_gate["rom_coverage_audit"]["summary"][
                "boot_interwork_padding_claim_count"
            ],
        )
        self.assertEqual(
            "639f595e03eb779de859b21c42fb77388cd5a93c26be5514b7c1f700fe1d09b9",
            rom_gate["rom_coverage_audit"]["summary"][
                "boot_interwork_padding_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "3e39ed78e50103716c788d4147df413950e5eba73c6e33acd923f15865795676",
            rom_gate["rom_coverage_audit"]["summary"][
                "boot_interwork_padding_packed_bytes_sha256"
            ],
        )
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        self.assertIn(
            "artifacts/rom-boot-interwork-v1/manifest.json",
            {
                item["path"]
                for item in specification["gates"]["rom_byte_coverage"][
                    "evidence"
                ]
            },
        )
        self.assertTrue(
            any(
                verifier["command"][1] == "tools/verify_rom_boot_interwork.py"
                for verifier in specification["gates"]["rom_byte_coverage"][
                    "verifiers"
                ]
            )
        )
        self.assertIn(
            "artifacts/rom-chapter-script-inventory-v1/manifest.json",
            {
                item["path"]
                for item in specification["gates"]["rom_byte_coverage"][
                    "evidence"
                ]
            },
        )
        self.assertTrue(
            any(
                verifier["command"][1]
                == "tools/verify_rom_chapter_script_inventory.py"
                for verifier in specification["gates"]["rom_byte_coverage"][
                    "verifiers"
                ]
            )
        )
        self.assertIn(
            "artifacts/rom-value-range-text-inventory-v1/manifest.json",
            {
                item["path"]
                for item in specification["gates"]["rom_byte_coverage"][
                    "evidence"
                ]
            },
        )
        self.assertTrue(
            any(
                verifier["command"][1]
                == "tools/verify_rom_value_range_text_inventory.py"
                for verifier in specification["gates"]["rom_byte_coverage"][
                    "verifiers"
                ]
            )
        )
        self.assertIn(
            "artifacts/rom-renderer-text-inventory-v1/manifest.json",
            {
                item["path"]
                for item in specification["gates"]["rom_byte_coverage"][
                    "evidence"
                ]
            },
        )
        self.assertTrue(
            any(
                verifier["command"][1]
                == "tools/verify_rom_renderer_text_inventory.py"
                for verifier in specification["gates"]["rom_byte_coverage"][
                    "verifiers"
                ]
            )
        )
        self.assertIn(
            "artifacts/rom-profile-text-inventory-v1/manifest.json",
            {
                item["path"]
                for item in specification["gates"]["rom_byte_coverage"][
                    "evidence"
                ]
            },
        )
        self.assertTrue(
            any(
                verifier["command"][1]
                == "tools/verify_rom_profile_text_inventory.py"
                for verifier in specification["gates"]["rom_byte_coverage"][
                    "verifiers"
                ]
            )
        )
        self.assertIn(
            "artifacts/rom-fixed-consumer-text-inventory-v1/manifest.json",
            {
                item["path"]
                for item in specification["gates"]["rom_byte_coverage"][
                    "evidence"
                ]
            },
        )
        self.assertTrue(
            any(
                verifier["command"][1]
                == "tools/verify_rom_fixed_consumer_text_inventory.py"
                for verifier in specification["gates"]["rom_byte_coverage"][
                    "verifiers"
                ]
            )
        )
        self.assertIn(
            "artifacts/rom-training-text-script-inventory-v1/manifest.json",
            {
                item["path"]
                for item in specification["gates"]["rom_byte_coverage"][
                    "evidence"
                ]
            },
        )
        self.assertTrue(
            any(
                verifier["command"][1]
                == "tools/verify_rom_training_text_script_inventory.py"
                for verifier in specification["gates"]["rom_byte_coverage"][
                    "verifiers"
                ]
            )
        )
        self.assertTrue(
            any(
                verifier["command"][1]
                == "tools/verify_sprite_definition_runtime_chain.py"
                for verifier in specification["gates"]["rom_byte_coverage"][
                    "verifiers"
                ]
            )
        )
        self.assertIn(
            "artifacts/rom-cfg-inventory-v2/manifest.json",
            {
                item["path"]
                for item in specification["gates"]["rom_byte_coverage"][
                    "evidence"
                ]
            },
        )
        self.assertTrue(
            any(
                verifier["command"][1] == "tools/verify_rom_cfg_inventory.py"
                for verifier in specification["gates"]["rom_byte_coverage"][
                    "verifiers"
                ]
            )
        )
        self.assertIn(
            "artifacts/rom-cfg-inventory-v3/manifest.json",
            {
                item["path"]
                for item in specification["gates"]["rom_byte_coverage"][
                    "evidence"
                ]
            },
        )
        self.assertTrue(
            any(
                verifier["command"][1]
                == "tools/verify_rom_cfg_inventory_v3.py"
                for verifier in specification["gates"]["rom_byte_coverage"][
                    "verifiers"
                ]
            )
        )
        self.assertIn(
            "artifacts/rom-dialogue-padding-inventory-v1/manifest.json",
            {
                item["path"]
                for item in specification["gates"]["rom_byte_coverage"][
                    "evidence"
                ]
            },
        )
        self.assertTrue(
            any(
                verifier["command"][1]
                == "tools/verify_rom_dialogue_padding_inventory.py"
                for verifier in specification["gates"]["rom_byte_coverage"][
                    "verifiers"
                ]
            )
        )
        self.assertEqual(
            96,
            rom_gate["rom_coverage_audit"]["summary"][
                "direct_cpuset_palette_bytes"
            ],
        )
        self.assertEqual(
            18_207,
            rom_gate["rom_coverage_audit"]["summary"][
                "dialogue_encoded_text_bytes"
            ],
        )
        self.assertEqual(
            6_100,
            rom_gate["rom_coverage_audit"]["summary"][
                "dialogue_pointer_table_bytes"
            ],
        )
        self.assertEqual(
            9_984,
            rom_gate["rom_coverage_audit"]["summary"]["tile_bg_palette_bytes"],
        )
        self.assertEqual(
            25_284,
            rom_gate["rom_coverage_audit"]["summary"][
                "consumer_code_slice_bytes"
            ],
        )
        self.assertEqual(
            111,
            rom_gate["rom_coverage_audit"]["summary"]
            ["consumer_code_slice_claim_count"],
        )
        self.assertEqual(
            224,
            rom_gate["rom_coverage_audit"]["summary"][
                "bg_canvas_descriptor_bytes"
            ],
        )
        self.assertEqual(
            6_304,
            rom_gate["rom_coverage_audit"]["summary"][
                "candidate_adjudication_bytes"
            ],
        )
        candidate_audit = rom_gate["similar_table_candidate_audit"]
        self.assertEqual(114, candidate_audit["adjudicated_candidate_count"])
        self.assertEqual(
            {"accepted": 60, "alias_of": 26, "rejected": 28},
            candidate_audit["decision_counts"],
        )
        self.assertEqual(
            0,
            candidate_audit["open_candidate_count"],
        )
        self.assertNotIn(
            "pointer-table candidates remain open",
            "\n".join(result["blockers"]),
        )

    def test_current_spec_binds_menu_portrait_lz77_palette_gap_proof(self) -> None:
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]

        matches = [
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_menu_portrait_lz77_palette_alignment_gaps.py"
            in item["command"]
        ]
        self.assertEqual(1, len(matches), "menu portrait gap verifier is absent")
        verifier = matches[0]
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_menu_portrait_lz77_palette_alignment_gaps.py",
                "--root",
                ".",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "9bbf3532a5edde0cbf0f0d5924c037bb7df6873f6b02bd278f7215cd3b1af27d",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": (
                    "rom-menu-portrait-lz77-palette-alignment-gaps-verification-v1"
                ),
                "/verified": True,
                "/errors": [],
                "/promotion_batch": (
                    "rom-menu-portrait-lz77-palette-alignment-gaps-v1"
                ),
                "/primary_class": "menu_portrait_lz77_palette_alignment_bytes",
                "/claim_kind": "menu_portrait_lz77_palette_alignment_gap_bytes",
                "/gap_count": 52,
                "/gap_bytes": 110,
                "/size_counts": {"1": 16, "2": 14, "3": 22},
                "/range_vector_sha256": (
                    "e88d3a42d6e3144919668ade6db9f9caa21e8aab1502d8b3d9c84a148875bbf7"
                ),
                "/boundary_vector_sha256": (
                    "13ab975a67b42528abeef6075ff1f71b9440a7e53806f4f07f345d2e30900ddb"
                ),
                "/packed_bytes_sha256": (
                    "f23391587f1c9fc48eabd1e95f4caf16f585ef09941b7bc24f023d228e81ccd5"
                ),
                "/aligned_pointer_reachable_lz77_count": 896,
                "/menu_resource_count": 74,
                "/physical_palette_count": 70,
                "/non_claims": {
                    "padding_intent_claimed": False,
                    "reserved_space_claimed": False,
                    "free_space_claimed": False,
                    "allocatable_space_claimed": False,
                    "runtime_consumption_claimed": False,
                    "natural_runtime_reachability_claimed": False,
                    "generic_lz77_alignment_rule_claimed": False,
                    "all_menu_gaps_exhaustive_claimed": False,
                    "graphics_or_palette_semantics_expanded": False,
                    "editing_safety_claimed": False,
                    "writeback_or_relocation_safety_claimed": False,
                },
                "/limitations": [
                    "Only the frozen 52 short ranges between independently parsed pointer-reachable LZ77 endpoints and fixed menu portrait palette starts are classified.",
                    "The bytes are not claimed to be padding, reserved space, free space, allocatable space, or runtime-consumed data.",
                    "The helper does not claim natural runtime reachability, a generic LZ77 alignment rule, graphics or palette semantics beyond the bound source classes, editing safety, writeback safety, relocation safety, or an exhaustive menu-gap inventory.",
                    "The parent workflow performs current-unknown and adjacent-owner checks after this helper is accepted.",
                ],
            },
            verifier["contract"]["assertions"],
        )

        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/menu_portrait_lz77_palette_alignment_gap_promotion_batch": (
                "rom-menu-portrait-lz77-palette-alignment-gaps-v1"
            ),
            "/summary/menu_portrait_lz77_palette_alignment_gap_claim_kind": (
                "menu_portrait_lz77_palette_alignment_gap_bytes"
            ),
            "/summary/menu_portrait_lz77_palette_alignment_gap_bytes": 110,
            "/summary/menu_portrait_lz77_palette_alignment_gap_claim_count": 52,
            "/summary/menu_portrait_lz77_palette_alignment_gap_range_vector_sha256": (
                "e88d3a42d6e3144919668ade6db9f9caa21e8aab1502d8b3d9c84a148875bbf7"
            ),
            "/summary/menu_portrait_lz77_palette_alignment_gap_boundary_vector_sha256": (
                "13ab975a67b42528abeef6075ff1f71b9440a7e53806f4f07f345d2e30900ddb"
            ),
            "/summary/menu_portrait_lz77_palette_alignment_gap_packed_bytes_sha256": (
                "f23391587f1c9fc48eabd1e95f4caf16f585ef09941b7bc24f023d228e81ccd5"
            ),
            "/summary/menu_portrait_lz77_palette_alignment_gap_claim_denominator_sha256": (
                "c49c9c26422412414154b96397c621761cdcf611e8d6ecb6fe52fd6302a70d18"
            ),
            "/summary/menu_portrait_lz77_palette_alignment_gap_independent_verifier_report_sha256": (
                "e2d9a895e98c4359add5af092f26e74b0c2e6f03e8e758abefc81324302da7aa"
            ),
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"][pointer], pointer
            )
        self.assertIn(
            "Only the frozen 52 short all-zero ranges between independently "
            "parsed pointer-reachable LZ77 endpoints and their fixed menu-"
            "portrait palette starts are classified; padding intent, runtime "
            "consumption, a generic alignment rule, exhaustive menu gaps, "
            "editing or relocation safety, and free or allocatable space are "
            "not claimed.",
            gate["limitations"],
        )
        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )

    def test_current_spec_binds_tile_bg_lz77_palette_gap_proof(self) -> None:
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]

        matches = [
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_tile_bg_lz77_palette_alignment_gaps.py"
            in item["command"]
        ]
        self.assertEqual(1, len(matches), "tile-BG gap verifier is absent")
        verifier = matches[0]
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_tile_bg_lz77_palette_alignment_gaps.py",
                "--root",
                ".",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "cd4f61cb1226989c235dd710be7e37b039a6548eec6e5448b23bff97fccbc80b",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": (
                    "rom-tile-bg-lz77-palette-alignment-gaps-verification-v1"
                ),
                "/verified": True,
                "/errors": [],
                "/promotion_batch": (
                    "rom-tile-bg-lz77-palette-alignment-gaps-v1"
                ),
                "/primary_class": "tile_bg_lz77_palette_alignment_bytes",
                "/claim_kind": "tile_bg_lz77_palette_alignment_gap_bytes",
                "/gap_count": 84,
                "/gap_bytes": 165,
                "/size_counts": {"1": 31, "2": 25, "3": 28},
                "/range_vector_sha256": (
                    "684c4ad2fa1256261de50ed01f8a781bde09b7514f4cab0c5ec5dec9a0b472e2"
                ),
                "/boundary_vector_sha256": (
                    "b96f496cb68ed87905d62c39a148f67b2fef4e10bfa9e2b6b004f2d1644fe448"
                ),
                "/packed_bytes_sha256": (
                    "2aa1fd6b1e4d7e4352751c0a8b7acb6fd9aa3a3a4c994f52b0a214c6f346277d"
                ),
                "/aligned_pointer_reachable_lz77_count": 896,
                "/tile_descriptor_count": 79,
                "/tile_palette_entry_count": 236,
                "/tile_raw_palette_range_count": 108,
                "/tile_merged_palette_claim_count": 107,
                "/tile_merged_palette_bytes": 9_984,
                "/all_zero": True,
                "/right_end_align4": True,
                "/non_claims": [
                    "padding",
                    "reserved_space",
                    "free_space",
                    "allocatable_space",
                    "natural_runtime_reachability",
                    "global_unreachability",
                    "fixed_consumer_exhaustiveness",
                    "final_pixel_equivalence",
                    "editing_safety",
                    "relocation_safety",
                ],
                "/limitations": [
                    "Only the frozen 84 short ranges between independently parsed pointer-reachable LZ77 endpoints and fixed tile-BG palette source ranges are classified.",
                    "The bytes are not claimed to be padding, reserved space, free space, or allocatable space.",
                    "The helper does not claim natural runtime reachability, global unreachability, fixed-consumer exhaustiveness, final pixel equivalence, editing safety, or relocation safety.",
                    "The parent integration performs current-unknown and adjacent-owner checks after this independent helper is accepted.",
                    "The two nonzero long gaps and seven heterogeneous direct-CpuSet/reuse gaps remain outside this contract.",
                ],
            },
            verifier["contract"]["assertions"],
        )

        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/tile_bg_lz77_palette_alignment_gap_promotion_batch": (
                "rom-tile-bg-lz77-palette-alignment-gaps-v1"
            ),
            "/summary/tile_bg_lz77_palette_alignment_gap_claim_kind": (
                "tile_bg_lz77_palette_alignment_gap_bytes"
            ),
            "/summary/tile_bg_lz77_palette_alignment_gap_bytes": 165,
            "/summary/tile_bg_lz77_palette_alignment_gap_claim_count": 84,
            "/summary/tile_bg_lz77_palette_alignment_gap_range_vector_sha256": (
                "684c4ad2fa1256261de50ed01f8a781bde09b7514f4cab0c5ec5dec9a0b472e2"
            ),
            "/summary/tile_bg_lz77_palette_alignment_gap_boundary_vector_sha256": (
                "b96f496cb68ed87905d62c39a148f67b2fef4e10bfa9e2b6b004f2d1644fe448"
            ),
            "/summary/tile_bg_lz77_palette_alignment_gap_packed_bytes_sha256": (
                "2aa1fd6b1e4d7e4352751c0a8b7acb6fd9aa3a3a4c994f52b0a214c6f346277d"
            ),
            "/summary/tile_bg_lz77_palette_alignment_gap_claim_denominator_sha256": (
                "1a956208ab86931840693d8967455bea8612cf13ea03be7ee41d20feed80c244"
            ),
            "/summary/tile_bg_lz77_palette_alignment_gap_independent_verifier_report_sha256": (
                "4122e5404dc32e9f1f0429b06e8446d4025b01fb566eeaf1110d92cab0b9a4dc"
            ),
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"][pointer], pointer
            )
        self.assertIn(
            "Only the frozen 84 short all-zero ranges totaling 165 bytes "
            "between independently parsed aligned pointer-reachable LZ77 "
            "endpoints and fixed tile-BG palette source starts are classified. "
            "The two nonzero long gaps and seven heterogeneous direct-CpuSet/"
            "reuse short gaps remain outside this contract; padding, reserved/"
            "free/allocatable space, natural runtime reachability, global "
            "unreachability, fixed-consumer exhaustiveness, final pixel "
            "equivalence, editing safety, and relocation safety are not claimed.",
            gate["limitations"],
        )
        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )

    def test_current_spec_binds_boot_thumb_code_literal_alignment_gap_proof(
        self,
    ) -> None:
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]

        matches = [
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_boot_thumb_code_literal_alignment_gaps.py"
            in item["command"]
        ]
        self.assertEqual(1, len(matches), "boot code/literal gap verifier is absent")
        verifier = matches[0]
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_boot_thumb_code_literal_alignment_gaps.py",
                "--root",
                ".",
            ],
            verifier["command"],
        )
        self.assertEqual(
            "f3179bb3df6be2622272ebb87668cd29a3c1edf1333d282c0932e50078b64b30",
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/schema": (
                    "rom-boot-thumb-code-literal-alignment-gaps-verification-v1"
                ),
                "/verified": True,
                "/errors": [],
                "/promotion_batch": (
                    "rom-boot-thumb-code-literal-alignment-gaps-v1"
                ),
                "/primary_class": "boot_thumb_code_literal_alignment_bytes",
                "/claim_kind": "boot_thumb_code_literal_alignment_gap_bytes",
                "/contract_sha256": (
                    "2298b1f03236d77eb14e0970612c54cbfa2ba10f92ba595fc1cb6426a61f338b"
                ),
                "/rom/sha256": (
                    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
                ),
                "/source/manifest/sha256": (
                    "d5af12930ed8e7539396f81deda19ae938eee3f029b95c959f6fa5d57c676d74"
                ),
                "/source/payload/sha256": (
                    "a35b581e44b276399874a2fc393f22f3c548c6b99e053f504587bdd92fbad295"
                ),
                "/source_denominator/code_range_count": 27,
                "/source_denominator/code_bytes": 1_226,
                "/source_denominator/consumed_literal_range_count": 22,
                "/source_denominator/consumed_literal_bytes": 296,
                "/source_denominator/literal_binding_count": 77,
                "/source_denominator/target_limited_thumb_cfg_complete": True,
                "/source_denominator/all_positive_code_to_literal_neighbours_selected": True,
                "/summary/gap_count": 12,
                "/summary/gap_bytes": 24,
                "/summary/size_counts": {"2": 12},
                "/summary/flow_counts": {
                    "indirect_branch": 1,
                    "return": 5,
                    "unconditional_branch": 6,
                },
                "/summary/range_vector_sha256": (
                    "dec4177a9818ff7b3349a7c678f8e4a223f4a6e8ac254e2cd81bb4cf1362ce58"
                ),
                "/summary/boundary_vector_sha256": (
                    "2c1e60388f8fd7ef11118e7a61ac93fa7816aa6012e7f6e3478a45d4d080b54f"
                ),
                "/summary/packed_bytes_sha256": (
                    "9d908ecfb6b256def8b49a7c504e6c889c4b0e41fe6ce3e01863dd7b61a20aa0"
                ),
                "/summary/all_bytes_zero": True,
                "/new_packet_additive": True,
                "/source_artifact_historical_envelope_gaps_classified": False,
                "/source_wide_envelope_is_claim": False,
                "/non_claims": {
                    "complete_boot_runtime": False,
                    "editing_or_relocation_safety": False,
                    "free_or_allocatable_space": False,
                    "global_code_or_literal_denominator": False,
                    "indirect_target_resolution": False,
                    "natural_execution_reachability": False,
                    "original_artifact_envelope_gaps_classified": False,
                    "padding": False,
                    "reserved_space": False,
                },
                "/limitations": [
                    "Only the twelve fixed positive code-to-consumed-literal neighbours are classified as align4 gap bytes.",
                    "The gap bytes are not claimed to be instructions, padding, reserved space, free space, or allocatable space.",
                    "The accepted source artifact's wide envelope gaps remain historical non-claims; this packet is additive.",
                    "This verifier does not prove complete boot runtime, natural execution reachability, global code/literal coverage, or indirect target resolution.",
                ],
            },
            verifier["contract"]["assertions"],
        )

        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a",
            evidence["sequel/rom-byte-coverage.json"],
        )
        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598",
            coverage["script_sha256"],
        )
        expected_summary = {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/cfg_code_claim_kind_denominator_sha256": (
                "0874b75882eac082ff880b7ecca68f15b5f51972acc42b6d759f75b09f05448f"
            ),
            "/summary/boot_thumb_code_literal_alignment_gap_promotion_batch": (
                "rom-boot-thumb-code-literal-alignment-gaps-v1"
            ),
            "/summary/boot_thumb_code_literal_alignment_gap_claim_kind": (
                "boot_thumb_code_literal_alignment_gap_bytes"
            ),
            "/summary/boot_thumb_code_literal_alignment_gap_bytes": 24,
            "/summary/boot_thumb_code_literal_alignment_gap_claim_count": 12,
            "/summary/boot_thumb_code_literal_alignment_gap_range_vector_sha256": (
                "dec4177a9818ff7b3349a7c678f8e4a223f4a6e8ac254e2cd81bb4cf1362ce58"
            ),
            "/summary/boot_thumb_code_literal_alignment_gap_boundary_vector_sha256": (
                "2c1e60388f8fd7ef11118e7a61ac93fa7816aa6012e7f6e3478a45d4d080b54f"
            ),
            "/summary/boot_thumb_code_literal_alignment_gap_packed_bytes_sha256": (
                "9d908ecfb6b256def8b49a7c504e6c889c4b0e41fe6ce3e01863dd7b61a20aa0"
            ),
            "/summary/boot_thumb_code_literal_alignment_gap_claim_denominator_sha256": (
                "1fadc38e6e829c3603f3d9213e98ed2dd33272aa729accdfd8db48b898c5a574"
            ),
            "/summary/boot_thumb_code_literal_alignment_gap_independent_verifier_report_sha256": (
                "e486e518c7df41659b002c5d4ed7aedf58e41c68aa1883122b88caeba8347e62"
            ),
        }
        for pointer, expected in expected_summary.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"][pointer], pointer
            )

        self.assertIn(
            "Only the frozen 12 two-byte all-zero ranges totaling 24 bytes "
            "between independently verified boot Thumb code terminals and "
            "their consumed literal pools are classified as align4 gaps. "
            "The source artifact's wider envelope gaps remain historical "
            "non-claims; instructions, padding, reserved/free/allocatable "
            "space, complete boot runtime, natural execution reachability, "
            "global code/literal denominators, indirect-target resolution, "
            "editing, and relocation safety are not claimed.",
            gate["limitations"],
        )
        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))
        self.assertEqual(
            96,
            sum(
                len(item["verifiers"])
                for item in specification["gates"].values()
            ),
        )

    def test_rom_gate_requires_the_adjudication_overlay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec_path = self._fixture(root)
            spec = json.loads(spec_path.read_text())
            gate = spec["gates"]["rom_byte_coverage"]
            gate["evidence"] = [
                item
                for item in gate["evidence"]
                if item["path"] != "sequel/similar-table-adjudications-v1.json"
            ]
            _write_json(spec_path, spec)

            result = audit_proof(root, spec_path)

        self.assertIn(
            "gate rom_byte_coverage: canonical pointer-table adjudication manifest is missing",
            result["blockers"],
        )

    def test_disproved_candidate_must_match_fixed_historical_extent(self):
        changed = dict(EXPECTED_DISPROVED_CANDIDATE_RANGES)
        changed["battle-handlers"] = (0, 1)
        with mock.patch(
            "tools.audit_reverse_engineering_proof.EXPECTED_DISPROVED_CANDIDATE_RANGES",
            changed,
        ), mock.patch(
            "tools.audit_reverse_engineering_proof.audit_rom_manifest",
            return_value={
                "verified": True,
                "state_inventory_complete": True,
                "semantic_classification_complete": False,
                "errors": [],
            },
        ):
            result = audit_proof(ROOT, SPEC)

        self.assertIn(
            "battle-handlers: fixed disproved candidate range changed",
            result["blockers"],
        )
        self.assertTrue(
            any("physical_hardware" in blocker for blocker in result["blockers"])
        )


class CfgProvenRootsV14ProofSpecTests(unittest.TestCase):
    def test_current_spec_binds_v14_artifact_coverage_and_bundle(self) -> None:
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        for path in (
            "sequel/rom-byte-coverage.json",
            "artifacts/rom-cfg-proven-roots-v14/manifest.json",
        ):
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), evidence[path]
            )
        manifest = json.loads(
            (ROOT / "artifacts/rom-cfg-proven-roots-v14/manifest.json").read_bytes()
        )
        payload_identity = manifest["files"]["rom-cfg-proven-roots-v14.json"]
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "artifacts/rom-cfg-proven-roots-v14/rom-cfg-proven-roots-v14.json").read_bytes()
            ).hexdigest(),
            payload_identity["sha256"],
        )
        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        for pointer, expected in {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/cfg_reachable_arm_code_bytes": 956,
            "/summary/cfg_reachable_thumb_code_bytes": 148_778,
            "/summary/cfg_promoted_unknown_bytes": 149_766,
            "/summary/cfg_primary_claim_count": 3_835,
            "/summary/cfg_code_claim_kind_count": 33,
            "/summary/cfg_code_claim_kind_denominator_sha256": (
                "0874b75882eac082ff880b7ecca68f15b5f51972acc42b6d759f75b09f05448f"
            ),
            "/summary/cfg_proven_roots_v14_extension_code_bytes": 120,
            "/summary/cfg_proven_roots_v14_extension_code_claim_count": 2,
            "/summary/cfg_proven_roots_v14_consumed_literal_bytes": 40,
            "/summary/cfg_proven_roots_v14_consumed_literal_claim_count": 2,
            "/summary/cfg_proven_roots_v14_promotion_bytes": 160,
            "/summary/cfg_proven_roots_v14_promotion_claim_count": 4,
        }.items():
            self.assertEqual(expected, coverage["contract"]["assertions"][pointer])
        verifier = next(
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_cfg_proven_roots_v14_bundle.py" in item["command"]
        )
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_cfg_proven_roots_v14_bundle.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-cfg-proven-roots-v14",
            ],
            verifier["command"],
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_rom_cfg_proven_roots_v14_bundle.py").read_bytes()
            ).hexdigest(),
            verifier["script_sha256"],
        )
        self.assertEqual(
            {
                "/artifact_schema": "rom-cfg-proven-roots-v14",
                "/artifact_status": "accepted",
                "/hole_bytes": 0,
                "/promotion_bytes": 160,
                "/promotion_code_bytes": 120,
                "/promotion_literal_bytes": 40,
                "/promotion_range_count": 4,
                "/schema": "rom-cfg-proven-roots-v14-bundle-verification-v1",
                "/target_frontier_count": 2,
                "/target_root_count": 2,
                "/verified": True,
            },
            verifier["contract"]["assertions"],
        )


class CfgProvenRootsV15ProofSpecTests(unittest.TestCase):
    def test_current_spec_binds_v15_artifact_coverage_bundle_and_limits(self) -> None:
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence_items = [
            item
            for item in gate["evidence"]
            if item["path"]
            in {
                "sequel/rom-byte-coverage.json",
                "artifacts/rom-cfg-proven-roots-v15/manifest.json",
            }
        ]
        self.assertEqual(2, len(evidence_items))
        evidence = {item["path"]: item["sha256"] for item in evidence_items}
        for path in (
            "sequel/rom-byte-coverage.json",
            "artifacts/rom-cfg-proven-roots-v15/manifest.json",
        ):
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), evidence[path]
            )

        manifest = json.loads(
            (ROOT / "artifacts/rom-cfg-proven-roots-v15/manifest.json").read_bytes()
        )
        payload_path = (
            ROOT
            / "artifacts/rom-cfg-proven-roots-v15/rom-cfg-proven-roots-v15.json"
        )
        self.assertEqual(
            {
                "sha256": hashlib.sha256(payload_path.read_bytes()).hexdigest(),
                "size": payload_path.stat().st_size,
            },
            manifest["files"]["rom-cfg-proven-roots-v15.json"],
        )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/audit_rom_byte_coverage.py").read_bytes()
            ).hexdigest(),
            coverage["script_sha256"],
        )
        for pointer, expected in {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/cfg_reachable_arm_code_bytes": 956,
            "/summary/cfg_reachable_thumb_code_bytes": 148_778,
            "/summary/cfg_promoted_unknown_bytes": 149_766,
            "/summary/cfg_primary_claim_count": 3_835,
            "/summary/cfg_code_claim_kind_count": 33,
            "/summary/cfg_code_claim_kind_denominator_sha256": (
                "0874b75882eac082ff880b7ecca68f15b5f51972acc42b6d759f75b09f05448f"
            ),
            "/summary/cfg_proven_roots_v15_extension_code_bytes": 398,
            "/summary/cfg_proven_roots_v15_extension_code_claim_count": 6,
            "/summary/cfg_proven_roots_v15_consumed_literal_bytes": 52,
            "/summary/cfg_proven_roots_v15_consumed_literal_claim_count": 4,
            "/summary/cfg_proven_roots_v15_promotion_bytes": 450,
            "/summary/cfg_proven_roots_v15_promotion_claim_count": 10,
            "/summary/cfg_proven_roots_v15_preserved_unknown_hole_bytes": 386,
            "/summary/cfg_proven_roots_v15_rejected_root_count": 1,
        }.items():
            self.assertEqual(expected, coverage["contract"]["assertions"][pointer])

        verifiers = [
            item
            for item in gate["verifiers"]
            if "tools/verify_rom_cfg_proven_roots_v15_bundle.py" in item["command"]
        ]
        self.assertEqual(1, len(verifiers))
        verifier = verifiers[0]
        self.assertEqual(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_cfg_proven_roots_v15_bundle.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-cfg-proven-roots-v15",
            ],
            verifier["command"],
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_rom_cfg_proven_roots_v15_bundle.py").read_bytes()
            ).hexdigest(),
            verifier["script_sha256"],
        )
        expected_assertions = {
            "/accepted_root_count": 4,
            "/accepted_roots": [397812, 399612, 571120, 631776],
            "/artifact_bundle_verified": True,
            "/artifact_schema": "rom-cfg-proven-roots-v15",
            "/artifact_status": "accepted",
            "/decoded_basic_block_count": 31,
            "/decoded_instruction_count": 197,
            "/errors": [],
            "/external_call_edge_count": 2,
            "/frontier_count": 3,
            "/legacy_control_flow_rebuilt": True,
            "/legacy_receipt_verified": True,
            "/literal_only_bytes": 52,
            "/live_coverage_verified": False,
            "/preserved_unknown_hole_bytes": 386,
            "/promotion_bytes": 450,
            "/promotion_packed_sha256": (
                "764b272bc4d19be46d334c10e47d00419c05fa60d6878ef336f455d25e7b08e7"
            ),
            "/reachable_instruction_bytes": 398,
            "/rejected_root_count": 1,
            "/rejected_roots": [639220],
            "/rom_sha256": (
                "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
            ),
            "/schema": "rom-cfg-proven-roots-v15-bundle-verification-v1",
            "/semantic_range_vector_sha256": (
                "4cb1b785aa18b03873dee55781289574009c42231d1dfd198aa024bc41d38974"
            ),
            "/union_range_vector_sha256": (
                "9a91de64231f4d1cf2bbf41e4aa4858c4fa4e3af7dddf60a5ae79287da506ad0"
            ),
            "/verified": True,
        }
        self.assertEqual(expected_assertions, verifier["contract"]["assertions"])

        contract = json.loads(
            (
                ROOT
                / "build/experiments/active/cfg-proven-roots-v15-preflight-20260830/CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        frozen_assertions = contract["integration"]["proof"][
            "bundle_contract_assertions"
        ]
        self.assertEqual(
            frozen_assertions,
            {pointer: expected_assertions[pointer] for pointer in frozen_assertions},
        )

        v15_limitations = [
            limitation
            for limitation in gate["limitations"]
            if "CFG proven-roots v15" in limitation
        ]
        self.assertEqual(1, len(v15_limitations))
        limitation = v15_limitations[0]
        for phrase in (
            "450 previously unknown bytes",
            "398 reachable instruction bytes",
            "52 consumed literal bytes",
            "four accepted",
            "One rejected",
            "three unresolved indirect-PC frontiers",
            "386 hole bytes remain unknown",
            "Natural execution",
            "global caller/code/indirect-target denominators",
            "editing",
            "relocation",
        ):
            self.assertIn(phrase, limitation)

        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))


class CfgConsumedLiteralBatchProofSpecTests(unittest.TestCase):
    def test_current_spec_binds_batch_artifacts_coverage_and_independent_verifiers(self) -> None:
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        paths = {
            f"artifacts/rom-cfg-v{version}-consumed-literals-v1/{name}"
            for version in (1, 2, 6)
            for name in ("manifest.json", f"rom-cfg-v{version}-consumed-literals.json")
        }
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertTrue(paths <= evidence.keys())
        for path in paths:
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), evidence[path]
            )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            hashlib.sha256((ROOT / "tools/audit_rom_byte_coverage.py").read_bytes()).hexdigest(),
            coverage["script_sha256"],
        )
        for pointer, expected in {
            "/summary/classified_bytes": 6_142_176,
            "/summary/unknown_bytes": 149_280,
            "/summary/claim_count": 15_940,
            "/summary/segment_count": 17_344,
            "/summary/cfg_consumed_literal_batch_bytes": 14_492,
            "/summary/cfg_consumed_literal_batch_claim_count": 1_220,
            "/summary/cfg_v1_consumed_literal_bytes": 1_396,
            "/summary/cfg_v2_consumed_literal_bytes": 6_796,
            "/summary/cfg_v6_consumed_literal_bytes": 2_980,
        }.items():
            self.assertEqual(expected, coverage["contract"]["assertions"][pointer])

        for version, manifest_sha, payload_sha, target_bytes, ranges in (
            (1, "e4ec5df3c6f1d63c64fbdb8ea921a7afaa7ddee8dd82436f9ca9980e9f96f546", "3ecef13a05e15d8665d09d1ebbfbcf93481d07c43d361a8d02a08d7523dd466f", 1_396, 108),
            (2, "41a3adb156ce5c07481b7aa903a77f4880b08cc6c13260fc30d25b4227ed232f", "e08df7333e8b82f3d18497bf5a2a478bf3bf7a5743e50e898cfc819f0b5d29b1", 6_796, 653),
            (6, "4301f6f8d32ec7e2b750f1954860ac6672c2056069ce78452f87351bc4e31cc6", "270f238c3689cdabef0c62db4141e4cc4f0a32a12bccbe7173527e979e921564", 2_980, 185),
        ):
            script = f"tools/verify_rom_cfg_v{version}_consumed_literals.py"
            command = [
                "python3", "-I", "-S", script, "--root", ".", "--artifact",
                f"artifacts/rom-cfg-v{version}-consumed-literals-v1",
            ]
            matches = [item for item in gate["verifiers"] if item["command"] == command]
            self.assertEqual(1, len(matches))
            verifier = matches[0]
            self.assertEqual(
                hashlib.sha256((ROOT / script).read_bytes()).hexdigest(),
                verifier["script_sha256"],
            )
            assertions = verifier["contract"]["assertions"]
            self.assertEqual(True, assertions["/verified"])
            self.assertEqual(True, assertions["/contract_ok"])
            self.assertEqual(manifest_sha, assertions["/artifact/manifest_sha256"])
            self.assertEqual(payload_sha, assertions["/artifact/payload_sha256"])
            self.assertEqual(target_bytes, assertions["/summary/target_bytes"])
            self.assertEqual(ranges, assertions["/summary/merged_target_range_count"])

        self.assertEqual(96, len(gate["evidence"]))
        self.assertEqual(92, len(gate["verifiers"]))


class CfgConsumedLiteralBatch2ProofSpecTests(unittest.TestCase):
    PACKETS = (
        (
            "rom-cfg-v3-consumed-literals-v1",
            "rom-cfg-v3-consumed-literals.json",
            "tools/verify_rom_cfg_v3_consumed_literals.py",
            1_220,
            95,
        ),
        (
            "rom-cfg-proven-roots-batch-consumed-literals-v1",
            "rom-cfg-proven-roots-batch-consumed-literals.json",
            "tools/verify_rom_cfg_proven_roots_batch_consumed_literals.py",
            1_256,
            116,
        ),
        (
            "rom-battle-controller-consumed-literals-v1",
            "rom-battle-controller-consumed-literals.json",
            "tools/verify_rom_battle_controller_consumed_literals.py",
            536,
            46,
        ),
        (
            "rom-cfg-v2-shadowed-consumed-literals-v1",
            "rom-cfg-v2-shadowed-consumed-literals.json",
            "tools/verify_rom_cfg_v2_shadowed_consumed_literals.py",
            308,
            17,
        ),
    )

    def test_current_spec_binds_second_batch_and_final_coverage(self) -> None:
        specification = json.loads(SPEC.read_text(encoding="utf-8"))
        gate = specification["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        for artifact, payload, _, _, _ in self.PACKETS:
            for name in ("manifest.json", payload):
                path = f"artifacts/{artifact}/{name}"
                self.assertIn(path, evidence)
                self.assertEqual(
                    hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), evidence[path]
                )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            hashlib.sha256((ROOT / "tools/audit_rom_byte_coverage.py").read_bytes()).hexdigest(),
            coverage["script_sha256"],
        )
        for pointer, expected in {
            "/summary/classified_bytes": 6_144_296,
            "/summary/unknown_bytes": 147_160,
            "/summary/claim_count": 15_945,
            "/summary/segment_count": 17_349,
            "/summary/cfg_consumed_literal_batch_bytes": 14_492,
            "/summary/cfg_consumed_literal_batch_claim_count": 1_220,
            "/summary/cfg_v3_consumed_literal_bytes": 1_220,
            "/summary/cfg_proven_roots_batch_consumed_literal_bytes": 1_256,
            "/summary/battle_controller_consumed_literal_bytes": 536,
            "/summary/cfg_v2_shadowed_consumed_literal_bytes": 308,
        }.items():
            self.assertEqual(expected, coverage["contract"]["assertions"][pointer])

        for artifact, _, script, target_bytes, ranges in self.PACKETS:
            matches = [
                item
                for item in gate["verifiers"]
                if script in item["command"]
            ]
            self.assertEqual(1, len(matches))
            verifier = matches[0]
            self.assertEqual(
                hashlib.sha256((ROOT / script).read_bytes()).hexdigest(),
                verifier["script_sha256"],
            )
            assertions = verifier["contract"]["assertions"]
            self.assertIs(True, assertions["/verified"])
            self.assertIs(True, assertions["/contract_ok"])
            prefix = (
                "/denominator"
                if artifact == "rom-cfg-proven-roots-batch-consumed-literals-v1"
                else "/summary"
            )
            self.assertEqual(target_bytes, assertions[f"{prefix}/target_bytes"])
            self.assertEqual(ranges, assertions[f"{prefix}/merged_target_range_count"])

        self.assertEqual(104, len(gate["evidence"]))
        self.assertEqual(96, len(gate["verifiers"]))


class ConsumerCodeSliceBatch4ProofTests(unittest.TestCase):
    PACKETS = (
        (
            "rom-battle-status-bar-caller-slice-v1",
            "rom-battle-status-bar-caller-slice.json",
            "tools/verify_rom_battle_status_bar_caller_slice.py",
        ),
        (
            "rom-chapter-selector-code-slice-v1",
            "rom-chapter-selector-code-slice.json",
            "tools/verify_rom_chapter_selector_code_slice.py",
        ),
        (
            "rom-profile-selector-code-slices-v1",
            "rom-profile-selector-code-slices.json",
            "tools/verify_rom_profile_selector_code_slices.py",
        ),
        (
            "rom-sprite-loader-tail-v1",
            "rom-sprite-loader-tail.json",
            "tools/verify_rom_sprite_loader_tail.py",
        ),
    )

    def test_current_spec_binds_batch4_and_exact_post_coverage(self) -> None:
        gate = json.loads(SPEC.read_text(encoding="utf-8"))["gates"][
            "rom_byte_coverage"
        ]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        for artifact, payload, script in self.PACKETS:
            for name in ("manifest.json", payload):
                path = f"artifacts/{artifact}/{name}"
                self.assertEqual(
                    hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                    evidence.get(path),
                )
            self.assertEqual(
                1,
                sum(script in item["command"] for item in gate["verifiers"]),
            )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        for pointer, expected in {
            "/summary/classified_bytes": 6_144_296,
            "/summary/unknown_bytes": 147_160,
            "/summary/claim_count": 15_945,
            "/summary/segment_count": 17_349,
            "/summary/consumer_code_slice_bytes": 27_404,
            "/summary/consumer_code_slice_claim_count": 116,
        }.items():
            self.assertEqual(expected, coverage["contract"]["assertions"][pointer])
        self.assertEqual(104, len(gate["evidence"]))
        self.assertEqual(96, len(gate["verifiers"]))


class FastAuditFourPacketProofSpecTests(unittest.TestCase):
    EVIDENCE_PATHS = (
        "artifacts/rom-fast-audit-four-packet-baseline-v1/manifest.json",
        "artifacts/rom-fast-audit-four-packet-baseline-v1/rom-byte-coverage.json.gz",
        "artifacts/rom-event-handler-cfg-v1/manifest.json",
        "artifacts/rom-event-handler-cfg-v1/rom-event-handler-cfg.json",
        "artifacts/rom-sprite-component-source-v1/manifest.json",
        "artifacts/rom-sprite-component-source-v1/rom-sprite-component-source.json",
        "artifacts/rom-sprite-component-source-v1/rom-sprite-component-source.bin",
        "artifacts/rom-cfg-proven-roots-v16/manifest.json",
        "artifacts/rom-cfg-proven-roots-v16/rom-cfg-proven-roots-v16.json",
        "artifacts/rom-cfg-proven-roots-v16-consumed-literals-v1/manifest.json",
        "artifacts/rom-cfg-proven-roots-v16-consumed-literals-v1/rom-cfg-proven-roots-v16-consumed-literals.json",
    )

    def test_spec_binds_immutable_replay_and_exact_post_promotion_coverage(self):
        gate = json.loads(SPEC.read_text(encoding="utf-8"))["gates"][
            "rom_byte_coverage"
        ]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "sequel/rom-byte-coverage.json").read_bytes()
            ).hexdigest(),
            evidence["sequel/rom-byte-coverage.json"],
        )
        for path in self.EVIDENCE_PATHS:
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                evidence.get(path),
                path,
            )

        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        for pointer, expected in {
            "/summary/classified_bytes": 6_151_436,
            "/summary/unknown_bytes": 140_020,
            "/summary/claim_count": 16_061,
            "/summary/segment_count": 17_483,
            "/summary/fast_audit_four_packet_bytes": 7_140,
            "/summary/fast_audit_four_packet_claim_count": 116,
            "/summary/fast_audit_immutable_baseline_sha256": (
                "064370aa0eca861d99d96e4ee15be4b50c569bea86c67a279d4084517e543baa"
            ),
            "/summary/fast_audit_replay_verifier_sha256": (
                "eb73243101b92d6ec5a65639615c4da3c44de0bd09bc2b26e33b4517ad5673bf"
            ),
            "/summary/cfg_reachable_thumb_code_bytes": 153_466,
            "/summary/cfg_promoted_unknown_bytes": 154_454,
            "/summary/cfg_primary_claim_count": 3_878,
            "/summary/cfg_code_claim_kind_count": 35,
            "/summary/cfg_code_claim_kind_denominator_sha256": (
                "ad155f92858a1cbd167b807d400769bc7b5c7bad5190f838bf3605cd6467019c"
            ),
        }.items():
            self.assertEqual(expected, coverage["contract"]["assertions"][pointer])

        script = "tools/verify_rom_fast_audit_four_packet_coverage.py"
        command = ["python3", "-I", "-S", script, "--root", "."]
        matches = [item for item in gate["verifiers"] if item["command"] == command]
        self.assertEqual([], matches, "coverage audit already executes the replay verifier")

        self.assertEqual(115, len(gate["evidence"]))
        self.assertEqual(96, len(gate["verifiers"]))


class CfgProvenRootsV17ProofSpecTests(unittest.TestCase):
    EVIDENCE_PATHS = (
        "artifacts/rom-cfg-proven-roots-v17-precoverage-v1/manifest.json",
        "artifacts/rom-cfg-proven-roots-v17-precoverage-v1/rom-byte-coverage.json.gz",
        "artifacts/rom-cfg-proven-roots-v17/manifest.json",
        "artifacts/rom-cfg-proven-roots-v17/rom-cfg-proven-roots-v17.json",
    )

    def test_spec_binds_v17_once_through_coverage_audit(self):
        gate = json.loads(SPEC.read_text(encoding="utf-8"))["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        for path in self.EVIDENCE_PATHS:
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), evidence.get(path), path)
        self.assertEqual(
            hashlib.sha256((ROOT / "sequel/rom-byte-coverage.json").read_bytes()).hexdigest(),
            evidence["sequel/rom-byte-coverage.json"],
        )
        coverage = next(item for item in gate["verifiers"] if item["command"][1] == "tools/audit_rom_byte_coverage.py")
        for pointer, expected in {
            "/summary/classified_bytes": 6_153_836,
            "/summary/unknown_bytes": 137_620,
            "/summary/claim_count": 16_087,
            "/summary/segment_count": 17_513,
            "/summary/cfg_proven_roots_v17_bytes": 2_400,
            "/summary/cfg_proven_roots_v17_claim_count": 26,
            "/summary/cfg_reachable_thumb_code_bytes": 155_558,
            "/summary/cfg_promoted_unknown_bytes": 156_546,
            "/summary/cfg_primary_claim_count": 3_891,
            "/summary/cfg_code_claim_kind_count": 36,
            "/summary/cfg_code_claim_kind_denominator_sha256": "5a522d03c7e46dacb8db6e0e4e4ed9027136f89548929250f67d5c8c1a7d07ed",
        }.items():
            self.assertEqual(expected, coverage["contract"]["assertions"][pointer])
        command = ["python3", "-I", "-S", "tools/verify_rom_cfg_proven_roots_v17.py", "--root", ".", "--artifact", "artifacts/rom-cfg-proven-roots-v17"]
        self.assertEqual([], [item for item in gate["verifiers"] if item["command"] == command], "coverage audit executes v17 exactly once")
        self.assertEqual(119, len(gate["evidence"]))
        self.assertEqual(96, len(gate["verifiers"]))


class CfgProvenRootsV18ProofSpecTests(unittest.TestCase):
    EVIDENCE_PATHS = (
        "artifacts/rom-cfg-proven-roots-v18-precoverage-v1/manifest.json",
        "artifacts/rom-cfg-proven-roots-v18-precoverage-v1/rom-byte-coverage.json.gz",
        "artifacts/rom-cfg-proven-roots-v18/manifest.json",
        "artifacts/rom-cfg-proven-roots-v18/rom-cfg-proven-roots-v18.json",
    )
    def test_spec_binds_v18_once_through_coverage_audit(self):
        gate = json.loads(SPEC.read_text())["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        for path in self.EVIDENCE_PATHS:
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), evidence.get(path), path)
        coverage = next(item for item in gate["verifiers"] if item["command"][1] == "tools/audit_rom_byte_coverage.py")
        for pointer, expected in {
            "/summary/classified_bytes": 6_155_318, "/summary/unknown_bytes": 136_138,
            "/summary/claim_count": 16_104, "/summary/segment_count": 17_533,
            "/summary/cfg_proven_roots_v18_bytes": 1_482, "/summary/cfg_proven_roots_v18_claim_count": 17,
            "/summary/cfg_reachable_thumb_code_bytes": 156_944, "/summary/cfg_promoted_unknown_bytes": 157_932,
            "/summary/cfg_primary_claim_count": 3_900, "/summary/cfg_code_claim_kind_count": 37,
            "/summary/cfg_code_claim_kind_denominator_sha256": "86bc5addf6d158cba89f241628e3f776c35cd7db83292ff023e4668401d869b0",
        }.items(): self.assertEqual(expected, coverage["contract"]["assertions"][pointer])
        command = ["python3", "-I", "-S", "tools/verify_rom_cfg_proven_roots_v18.py", "--root", ".", "--artifact", "artifacts/rom-cfg-proven-roots-v18"]
        self.assertEqual([], [item for item in gate["verifiers"] if item["command"] == command])
        self.assertEqual(123, len(gate["evidence"]))
        self.assertEqual(96, len(gate["verifiers"]))


class BootContinuationAndCfgV19ProofSpecTests(unittest.TestCase):
    EVIDENCE_PATHS = (
        "artifacts/rom-boot-interwork-continuation-precoverage-v1/manifest.json",
        "artifacts/rom-boot-interwork-continuation-precoverage-v1/rom-byte-coverage.json.gz",
        "artifacts/rom-boot-interwork-continuation-v1/manifest.json",
        "artifacts/rom-boot-interwork-continuation-v1/rom-boot-interwork-continuation.json",
        "artifacts/rom-cfg-proven-roots-v19/manifest.json",
        "artifacts/rom-cfg-proven-roots-v19/rom-cfg-proven-roots-v19.json",
    )

    def test_spec_binds_dependency_dag_once_through_coverage_audit(self):
        gate = json.loads(SPEC.read_text())["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        for path in self.EVIDENCE_PATHS:
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), evidence.get(path), path)
        self.assertEqual(hashlib.sha256((ROOT / "sequel/rom-byte-coverage.json").read_bytes()).hexdigest(), evidence["sequel/rom-byte-coverage.json"])
        coverage = next(item for item in gate["verifiers"] if item["command"][1] == "tools/audit_rom_byte_coverage.py")
        for pointer, expected in {
            "/summary/classified_bytes": 6_160_258, "/summary/unknown_bytes": 131_198,
            "/summary/claim_count": 16_127, "/summary/segment_count": 17_559,
            "/summary/boot_interwork_continuation_bytes": 94, "/summary/boot_interwork_continuation_claim_count": 6,
            "/summary/cfg_proven_roots_v19_bytes": 1_660, "/summary/cfg_proven_roots_v19_claim_count": 14,
            "/summary/cfg_reachable_thumb_code_bytes": 158_618, "/summary/cfg_promoted_unknown_bytes": 159_606,
            "/summary/cfg_primary_claim_count": 3_908, "/summary/cfg_code_claim_kind_count": 39,
            "/summary/cfg_code_claim_kind_denominator_sha256": "1fc7b60019803c7b8062ff9f744a1b14747de900c5e4611e8c3368d13dbf758e",
        }.items():
            self.assertEqual(expected, coverage["contract"]["assertions"][pointer])
        for command in (
            ["python3", "-I", "-S", "tools/verify_rom_boot_interwork_continuation.py", "--root", ".", "--artifact", "artifacts/rom-boot-interwork-continuation-v1"],
            ["python3", "-I", "-S", "tools/verify_rom_cfg_proven_roots_v19.py", "--root", ".", "--artifact", "artifacts/rom-cfg-proven-roots-v19"],
        ):
            self.assertEqual([], [item for item in gate["verifiers"] if item["command"] == command])
        self.assertEqual(132, len(gate["evidence"]))
        self.assertEqual(96, len(gate["verifiers"]))


class UnboundChapterScriptTailProofSpecTests(unittest.TestCase):
    EVIDENCE_PATHS = (
        "artifacts/rom-chapter-script-unbound-tail-v1/manifest.json",
        "artifacts/rom-chapter-script-unbound-tail-v1/rom-chapter-script-unbound-tail.json",
        "artifacts/rom-chapter-script-unbound-tail-v1/chapter-script-unbound-tail.bin",
    )

    def test_spec_binds_unbound_tail_once_through_coverage_audit(self):
        gate = json.loads(SPEC.read_text())["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        for path in self.EVIDENCE_PATHS:
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                evidence.get(path),
                path,
            )
        self.assertEqual(
            hashlib.sha256((ROOT / "sequel/rom-byte-coverage.json").read_bytes()).hexdigest(),
            evidence["sequel/rom-byte-coverage.json"],
        )
        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        for pointer, expected in {
            "/summary/classified_bytes": 6_160_258,
            "/summary/unknown_bytes": 131_198,
            "/summary/claim_count": 16_127,
            "/summary/segment_count": 17_559,
            "/summary/unbound_chapter_script_tail_bytes": 3_186,
            "/summary/unbound_chapter_script_tail_claim_count": 3,
        }.items():
            self.assertEqual(expected, coverage["contract"]["assertions"].get(pointer), pointer)
        command = [
            "python3", "-I", "-S", "tools/verify_rom_unbound_chapter_script_tail.py",
            "--root", ".", "--artifact", "artifacts/rom-chapter-script-unbound-tail-v1",
        ]
        self.assertEqual([], [item for item in gate["verifiers"] if item["command"] == command])
        self.assertEqual(132, len(gate["evidence"]))
        self.assertEqual(96, len(gate["verifiers"]))


class ChapterScriptConsumerRootsProofSpecTests(unittest.TestCase):
    EVIDENCE_PATHS = (
        "artifacts/rom-chapter-script-consumer-roots-v1/manifest.json",
        "artifacts/rom-chapter-script-consumer-roots-v1/rom-chapter-script-consumer-roots.json",
        "artifacts/rom-chapter-script-consumer-roots-v1/chapter-script-consumer-roots.bin",
    )

    def test_spec_binds_consumer_roots_once_through_coverage_audit(self):
        gate = json.loads(SPEC.read_text())["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        for path in self.EVIDENCE_PATHS:
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                evidence.get(path),
                path,
            )
        self.assertEqual(
            hashlib.sha256((ROOT / "sequel/rom-byte-coverage.json").read_bytes()).hexdigest(),
            evidence["sequel/rom-byte-coverage.json"],
        )
        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            hashlib.sha256((ROOT / "tools/audit_rom_byte_coverage.py").read_bytes()).hexdigest(),
            coverage["script_sha256"],
        )
        for pointer, expected in {
            "/summary/classified_bytes": 6_184_516,
            "/summary/unknown_bytes": 106_940,
            "/summary/claim_count": 16_524,
            "/summary/segment_count": 18_175,
            "/summary/chapter_script_consumer_roots_bytes": 16_175,
            "/summary/chapter_script_consumer_roots_claim_count": 2,
        }.items():
            self.assertEqual(expected, coverage["contract"]["assertions"].get(pointer), pointer)
        command = [
            "python3", "-I", "-S", "tools/verify_rom_chapter_script_consumer_roots.py",
            "--root", ".", "--artifact", "artifacts/rom-chapter-script-consumer-roots-v1",
        ]
        self.assertEqual([], [item for item in gate["verifiers"] if item["command"] == command])
        self.assertEqual(145, len(gate["evidence"]))
        self.assertEqual(96, len(gate["verifiers"]))


class FourPacketMilestoneProofSpecTests(unittest.TestCase):
    EVIDENCE_PATHS = (
        "artifacts/rom-battle-condition-result-text-v1/manifest.json",
        "artifacts/rom-battle-condition-result-text-v1/battle-condition-result-text.json",
        "artifacts/rom-battle-condition-result-text-v1/battle-condition-result-text.bin",
        "artifacts/rom-alternate-dialogue-table-v1/manifest.json",
        "artifacts/rom-alternate-dialogue-table-v1/alternate-dialogue-table.json",
        "artifacts/rom-alternate-dialogue-table-v1/alternate-dialogue-text.bin",
        "artifacts/rom-story-state-callback-cfg-v1/manifest.json",
        "artifacts/rom-story-state-callback-cfg-v1/rom-story-state-callback-cfg.json",
        "artifacts/rom-story-state-entry-c4cc-v1/manifest.json",
        "artifacts/rom-story-state-entry-c4cc-v1/rom-story-state-entry-c4cc.json",
    )

    def test_spec_binds_four_packet_milestone_once_through_coverage_audit(self):
        gate = json.loads(SPEC.read_text())["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        for path in self.EVIDENCE_PATHS:
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                evidence.get(path),
                path,
            )
        self.assertEqual(
            hashlib.sha256((ROOT / "sequel/rom-byte-coverage.json").read_bytes()).hexdigest(),
            evidence["sequel/rom-byte-coverage.json"],
        )
        coverage = next(
            item
            for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            hashlib.sha256((ROOT / "tools/audit_rom_byte_coverage.py").read_bytes()).hexdigest(),
            coverage["script_sha256"],
        )
        for pointer, expected in {
            "/summary/classified_bytes": 6_184_516,
            "/summary/unknown_bytes": 106_940,
            "/summary/claim_count": 16_524,
            "/summary/segment_count": 18_175,
            "/summary/battle_condition_result_text_bytes": 3_961,
            "/summary/battle_condition_result_text_claim_count": 219,
            "/summary/alternate_dialogue_table_bytes": 3_200,
            "/summary/alternate_dialogue_table_claim_count": 161,
            "/summary/story_state_callback_cfg_bytes": 702,
            "/summary/story_state_callback_cfg_claim_count": 13,
            "/summary/story_state_entry_c4cc_bytes": 220,
            "/summary/story_state_entry_c4cc_claim_count": 2,
            "/summary/cfg_reachable_thumb_code_bytes": 159_480,
            "/summary/cfg_promoted_unknown_bytes": 160_468,
            "/summary/cfg_primary_claim_count": 3_917,
            "/summary/cfg_code_claim_kind_count": 41,
            "/summary/cfg_code_claim_kind_denominator_sha256": (
                "fb1f3714cf8dc7ff6a1d5f280c5e0088a5ce91d414333d24e40a16310125cc08"
            ),
        }.items():
            self.assertEqual(expected, coverage["contract"]["assertions"].get(pointer), pointer)
        self.assertEqual(145, len(gate["evidence"]))
        self.assertEqual(96, len(gate["verifiers"]))


class FourQueuedPacketTier2ProofSpecTests(unittest.TestCase):
    EVIDENCE_PATHS = (
        "artifacts/rom-boot-state-dispatcher-cfg-v1/manifest.json",
        "artifacts/rom-boot-state-dispatcher-cfg-v1/rom-boot-state-dispatcher-cfg.json",
        "artifacts/rom-fixed-animation-descriptor-groups-v1/manifest.json",
        "artifacts/rom-fixed-animation-descriptor-groups-v1/rom-fixed-animation-descriptor-groups.json",
        "artifacts/rom-battle-distance-dispatcher-cfg-v1/manifest.json",
        "artifacts/rom-battle-distance-dispatcher-cfg-v1/rom-battle-distance-dispatcher-cfg.json",
        "artifacts/rom-bounded-index-u16-pair-table-v1/manifest.json",
        "artifacts/rom-bounded-index-u16-pair-table-v1/rom-bounded-index-u16-pair-table.json",
    )

    def test_spec_binds_four_packet_tier2_once_through_coverage_audit(self):
        gate = json.loads(SPEC.read_text())["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        for path in self.EVIDENCE_PATHS:
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                evidence.get(path),
                path,
            )
        self.assertEqual(
            hashlib.sha256((ROOT / "sequel/rom-byte-coverage.json").read_bytes()).hexdigest(),
            evidence["sequel/rom-byte-coverage.json"],
        )
        coverage = next(
            item for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            hashlib.sha256((ROOT / "tools/audit_rom_byte_coverage.py").read_bytes()).hexdigest(),
            coverage["script_sha256"],
        )
        for pointer, expected in {
            "/summary/classified_bytes": 6_194_116,
            "/summary/unknown_bytes": 97_340,
            "/summary/claim_count": 16_652,
            "/summary/segment_count": 18_332,
            "/summary/cfg_reachable_thumb_code_bytes": 165_572,
            "/summary/cfg_promoted_unknown_bytes": 166_560,
            "/summary/cfg_primary_claim_count": 3_969,
            "/summary/cfg_code_claim_kind_count": 45,
            "/summary/cfg_code_claim_kind_denominator_sha256": (
                "140cd11a51f55efba1c9bada8627ad2ce17652d34fee8b459991705ce96b90cd"
            ),
        }.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"].get(pointer), pointer)
        commands = {
            tuple(item["command"])
            for item in gate["verifiers"]
        }
        for verifier, artifact in (
            ("tools/verify_rom_boot_state_dispatcher_cfg.py",
             "artifacts/rom-boot-state-dispatcher-cfg-v1"),
            ("tools/verify_rom_fixed_animation_descriptor_groups.py",
             "artifacts/rom-fixed-animation-descriptor-groups-v1"),
            ("tools/verify_rom_battle_distance_dispatcher_cfg.py",
             "artifacts/rom-battle-distance-dispatcher-cfg-v1"),
            ("tools/verify_rom_bounded_index_u16_pair_table.py",
             "artifacts/rom-bounded-index-u16-pair-table-v1"),
        ):
            self.assertNotIn(
                ("python3", "-I", "-S", verifier,
                 "--root", ".", "--artifact", artifact),
                commands,
            )
        self.assertEqual(153, len(gate["evidence"]))
        self.assertEqual(96, len(gate["verifiers"]))


class SceneSourceFourPacketTier2ProofSpecTests(unittest.TestCase):
    EVIDENCE_PATHS = (
        "artifacts/rom-scene-source-four-packet-precoverage-v1/manifest.json",
        "artifacts/rom-scene-source-four-packet-precoverage-v1/rom-byte-coverage.json.gz",
        "artifacts/rom-v17-v18-helper-cfg-v1/manifest.json",
        "artifacts/rom-v17-v18-helper-cfg-v1/rom-v17-v18-helper-cfg.json",
        "artifacts/rom-fixed-pair-tables-v1/manifest.json",
        "artifacts/rom-fixed-pair-tables-v1/rom-fixed-pair-tables.json",
        "artifacts/rom-prebattle-menu-controller-cfg-v1/manifest.json",
        "artifacts/rom-prebattle-menu-controller-cfg-v1/rom-prebattle-menu-controller-cfg.json",
        "artifacts/rom-scene-source-closures-v1/manifest.json",
        "artifacts/rom-scene-source-closures-v1/rom-scene-source-closures.json",
    )

    def test_spec_binds_scene_source_four_packet_tier2_once_through_coverage_audit(self):
        gate = json.loads(SPEC.read_text())["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        for path in self.EVIDENCE_PATHS:
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                evidence.get(path),
                path,
            )
        self.assertEqual(
            hashlib.sha256((ROOT / "sequel/rom-byte-coverage.json").read_bytes()).hexdigest(),
            evidence["sequel/rom-byte-coverage.json"],
        )
        coverage = next(
            item for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            hashlib.sha256((ROOT / "tools/audit_rom_byte_coverage.py").read_bytes()).hexdigest(),
            coverage["script_sha256"],
        )
        for pointer, expected in {
            "/summary/classified_bytes": 6_198_347,
            "/summary/unknown_bytes": 93_109,
            "/summary/claim_count": 16_793,
            "/summary/segment_count": 18_552,
            "/summary/cfg_reachable_thumb_code_bytes": 168_334,
            "/summary/cfg_promoted_unknown_bytes": 169_322,
            "/summary/cfg_primary_claim_count": 4_005,
            "/summary/cfg_code_claim_kind_count": 47,
            "/summary/cfg_code_claim_kind_denominator_sha256": (
                "c393be11c73cc8a701f7520430d149181458cdb72cd43d9dd25072ce14d59667"
            ),
        }.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"].get(pointer), pointer)
        commands = {tuple(item["command"]) for item in gate["verifiers"]}
        for verifier, artifact in (
            ("tools/verify_rom_v17_v18_helper_cfg.py", "artifacts/rom-v17-v18-helper-cfg-v1"),
            ("tools/verify_rom_fixed_pair_tables.py", "artifacts/rom-fixed-pair-tables-v1"),
            ("tools/verify_rom_prebattle_menu_controller_cfg.py", "artifacts/rom-prebattle-menu-controller-cfg-v1"),
            ("tools/verify_rom_scene_source_closures.py", "artifacts/rom-scene-source-closures-v1"),
        ):
            self.assertNotIn(
                ("python3", "-I", "-S", verifier,
                 "--root", ".", "--artifact", artifact),
                commands,
            )
        self.assertEqual(163, len(gate["evidence"]))
        self.assertEqual(96, len(gate["verifiers"]))


class StoryDependencyFourPacketTier2ProofSpecTests(unittest.TestCase):
    EVIDENCE_PATHS = (
        "artifacts/rom-story-callback-dependency-closures-precoverage-v1/manifest.json",
        "artifacts/rom-story-callback-dependency-closures-precoverage-v1/rom-byte-coverage.json.gz",
        "artifacts/rom-story-callback-dependency-closures-v1/manifest.json",
        "artifacts/rom-story-callback-dependency-closures-v1/rom-story-callback-dependency-closures.json",
        "artifacts/rom-cfg-proven-roots-v20/manifest.json",
        "artifacts/rom-cfg-proven-roots-v20/rom-cfg-proven-roots-v20.json",
        "artifacts/rom-story-next-dependency-cfg-v1/manifest.json",
        "artifacts/rom-story-next-dependency-cfg-v1/rom-story-next-dependency-cfg-v1.json",
        "artifacts/rom-boot-register-init-dependency-cfg-v1/manifest.json",
        "artifacts/rom-boot-register-init-dependency-cfg-v1/rom-boot-register-init-dependency-cfg-v1.json",
    )

    def test_spec_binds_dependency_four_packet_tier2_once_through_coverage_audit(self):
        gate = json.loads(SPEC.read_text())["gates"]["rom_byte_coverage"]
        evidence = {item["path"]: item["sha256"] for item in gate["evidence"]}
        for path in self.EVIDENCE_PATHS:
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                evidence.get(path),
                path,
            )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "sequel/rom-byte-coverage.json").read_bytes()
            ).hexdigest(),
            evidence["sequel/rom-byte-coverage.json"],
        )
        coverage = next(
            item for item in gate["verifiers"]
            if item["command"][1] == "tools/audit_rom_byte_coverage.py"
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/audit_rom_byte_coverage.py").read_bytes()
            ).hexdigest(),
            coverage["script_sha256"],
        )
        for pointer, expected in {
            "/summary/classified_bytes": 6_202_729,
            "/summary/unknown_bytes": 88_727,
            "/summary/claim_count": 16_870,
            "/summary/segment_count": 18_641,
            "/summary/cfg_reachable_thumb_code_bytes": 172_148,
            "/summary/cfg_promoted_unknown_bytes": 173_136,
            "/summary/cfg_primary_claim_count": 4_048,
            "/summary/cfg_code_claim_kind_count": 51,
            "/summary/cfg_code_claim_kind_denominator_sha256": (
                "f50253fd726f103682625d5bb8ab6870f0c56b3443a12429024700899d26fe02"
            ),
        }.items():
            self.assertEqual(
                expected, coverage["contract"]["assertions"].get(pointer), pointer)
        commands = {tuple(item["command"]) for item in gate["verifiers"]}
        for verifier, artifact in (
            ("tools/verify_rom_story_callback_dependency_closures.py",
             "artifacts/rom-story-callback-dependency-closures-v1"),
            ("tools/verify_rom_cfg_proven_roots_v20.py",
             "artifacts/rom-cfg-proven-roots-v20"),
            ("tools/verify_rom_story_next_dependency_cfg.py",
             "artifacts/rom-story-next-dependency-cfg-v1"),
            ("tools/verify_rom_boot_register_init_dependency_cfg.py",
             "artifacts/rom-boot-register-init-dependency-cfg-v1"),
        ):
            self.assertNotIn(
                ("python3", "-I", "-S", verifier,
                 "--root", ".", "--artifact", artifact),
                commands,
            )
        self.assertEqual(173, len(gate["evidence"]))
        self.assertEqual(96, len(gate["verifiers"]))


if __name__ == "__main__":
    unittest.main()
