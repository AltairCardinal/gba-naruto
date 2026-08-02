from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-11-cross-shuriken.json"
GROUP1_PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-01-action5-dust.json"
GROUP14_PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-14-fire-action.json"
GROUP15_PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-15-action64-water-dragon.json"
GROUP13_PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-13-action61-execution.json"
GROUP2_PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-02-action7-shadow-clone.json"
GROUP4_PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-04-tool1-projectile.json"


class BattleEffectPixelAbBuilderTests(unittest.TestCase):
    def setUp(self):
        from tools import build_battle_effect_pixel_ab

        self.builder = build_battle_effect_pixel_ab

    def test_group11_profile_builds_same_topology_one_byte_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "pair"
            result = self.builder.build_pair(ROOT, PROFILE, output)

            self.assertEqual(result["schema"], "battle-effect-pixel-ab-build-v1")
            self.assertEqual(result["profile_id"], "group-11-cross-shuriken")
            self.assertEqual(result["binding"]["ninja_tool_id"], 1)
            self.assertEqual(result["binding"]["encoded_action_id"], 129)
            self.assertEqual(result["binding"]["sequence_id"], 13)
            self.assertEqual(result["binding"]["group_id"], 11)
            self.assertEqual(result["edit"]["graphics_byte_offset"], 0x16)
            self.assertEqual(result["edit"]["screen_xy"], [172, 61])
            self.assertTrue(result["same_patch_topology"])
            self.assertTrue(result["same_encoded_size"])

            baseline = (output / result["variants"]["baseline"]["graphics_path"]).read_bytes()
            candidate = (output / result["variants"]["candidate"]["graphics_path"]).read_bytes()
            changed = [
                index
                for index, pair in enumerate(zip(baseline, candidate))
                if pair[0] != pair[1]
            ]
            self.assertEqual(changed, [0x16])
            self.assertEqual((baseline[0x16], candidate[0x16]), (0x21, 0x22))
            self.assertEqual(
                result["variants"]["baseline"]["encoded_graphics_size"],
                488,
            )
            self.assertEqual(
                result["variants"]["candidate"]["encoded_graphics_size"],
                488,
            )
            for variant in ("baseline", "candidate"):
                ledger = result["variants"][variant]["patch_ledger"]
                self.assertEqual(len(ledger), 2)
                self.assertEqual(ledger[0]["kind"], "allocation")
                self.assertEqual(ledger[0]["offset"], 0xB40000)
                self.assertEqual(ledger[1]["kind"], "redirect")
                self.assertEqual(ledger[1]["offset"], 0x599174)

    def test_group2_profile_splits_shared_group3_graphics_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "pair"
            result = self.builder.build_pair(ROOT, GROUP2_PROFILE, output)

            self.assertEqual(
                result["binding"],
                {
                    "active_action_id": 7,
                    "encoded_action_id": 7,
                    "sequence_id": 2,
                    "selector_kind": "active_action_handler_immediate",
                    "pair_slot": "primary",
                    "handler_start": "0x0807E1C8",
                    "selector_callsite": "0x0807E1D0",
                    "dynamic_action_sequence_id": 0,
                    "group_id": 2,
                },
            )
            for variant in ("baseline", "candidate"):
                ledger = result["variants"][variant]["patch_ledger"]
                self.assertEqual(len(ledger), 2)
                self.assertEqual(ledger[1]["offset"], 0x59912C)
                rom = (output / result["variants"][variant]["rom_path"]).read_bytes()
                base = (ROOT / "rom/base.gba").read_bytes()
                self.assertNotEqual(rom[0x59912C:0x599130], base[0x59912C:0x599130])
                self.assertEqual(rom[0x599134:0x599138], base[0x599134:0x599138])

    def test_active_action_selector_resolves_action16_sequence16(self):
        catalog = json.loads(
            (
                ROOT
                / "artifacts/battle-effect-sequence-bindings-v1/manifest.json"
            ).read_text(encoding="utf-8")
        )

        binding, build_binding = self.builder._resolve_selector_binding(
            {
                "kind": "active_action",
                "id": 16,
                "encoded_action_id": 16,
            },
            catalog,
            sequence_id=16,
        )

        self.assertEqual(binding["action_id"], 16)
        self.assertEqual(binding["sequence_id"], 16)
        self.assertEqual(
            build_binding,
            {
                "active_action_id": 16,
                "encoded_action_id": 16,
                "sequence_id": 16,
            },
        )

    def test_active_action_can_trigger_a_distinct_resource_sequence(self):
        catalog = json.loads(
            (
                ROOT
                / "artifacts/battle-effect-sequence-bindings-v1/manifest.json"
            ).read_text(encoding="utf-8")
        )

        binding, build_binding = self.builder._resolve_selector_binding(
            {
                "kind": "active_action",
                "id": 5,
                "encoded_action_id": 5,
            },
            catalog,
            sequence_id=1,
            trigger_sequence_id=6,
        )

        self.assertEqual(binding["action_id"], 5)
        self.assertEqual(binding["sequence_id"], 6)
        self.assertEqual(
            build_binding,
            {
                "active_action_id": 5,
                "encoded_action_id": 5,
                "sequence_id": 1,
                "trigger_sequence_id": 6,
            },
        )

    def test_active_action_handler_can_bind_hardcoded_resource_sequence(self):
        sequence_catalog = json.loads(
            (
                ROOT
                / "artifacts/battle-effect-sequence-bindings-v1/manifest.json"
            ).read_text(encoding="utf-8")
        )
        producer_catalog = json.loads(
            (
                ROOT
                / "notes/battle-effect-hardcoded-selector-producers-20260802.json"
            ).read_text(encoding="utf-8")
        )

        binding, build_binding = self.builder._resolve_selector_binding(
            {
                "kind": "active_action_handler_immediate",
                "id": 7,
                "encoded_action_id": 7,
                "pair_slot": "primary",
                "handler_start": "0x0807E1C8",
                "selector_callsite": "0x0807E1D0",
            },
            sequence_catalog,
            sequence_id=2,
            hardcoded_selector_producers=producer_catalog,
        )

        self.assertEqual(binding["action_id"], 7)
        self.assertEqual(binding["dynamic_action_sequence_id"], 0)
        self.assertEqual(
            build_binding,
            {
                "active_action_id": 7,
                "encoded_action_id": 7,
                "sequence_id": 2,
                "selector_kind": "active_action_handler_immediate",
                "pair_slot": "primary",
                "handler_start": "0x0807E1C8",
                "selector_callsite": "0x0807E1D0",
                "dynamic_action_sequence_id": 0,
            },
        )

    def test_active_action_handler_rejects_wrong_hardcoded_callsite(self):
        sequence_catalog = json.loads(
            (
                ROOT
                / "artifacts/battle-effect-sequence-bindings-v1/manifest.json"
            ).read_text(encoding="utf-8")
        )
        producer_catalog = json.loads(
            (
                ROOT
                / "notes/battle-effect-hardcoded-selector-producers-20260802.json"
            ).read_text(encoding="utf-8")
        )

        with self.assertRaisesRegex(ValueError, "hardcoded handler binding mismatch"):
            self.builder._resolve_selector_binding(
                {
                    "kind": "active_action_handler_immediate",
                    "id": 7,
                    "encoded_action_id": 7,
                    "pair_slot": "primary",
                    "handler_start": "0x0807E1C8",
                    "selector_callsite": "0x0807E076",
                },
                sequence_catalog,
                sequence_id=2,
                hardcoded_selector_producers=producer_catalog,
            )

    def test_profile_screen_pixels_supports_multiple_rendered_instances(self):
        profile = {
            "screen_xy": [44, 73],
            "screen_pixels": [[44, 73], [37, 77]],
        }

        self.assertEqual(
            self.builder._profile_screen_pixels(profile),
            [(44, 73), (37, 77)],
        )

    def test_runtime_oam_instances_bind_every_natural_child(self):
        profile = json.loads(GROUP1_PROFILE.read_text(encoding="utf-8"))

        instances = self.builder._runtime_oam_instances(profile, 5, 1)

        self.assertEqual([item["oam_index"] for item in instances], [0, 1, 2])
        self.assertEqual(
            [item["source_pixel_screen_xy"] for item in instances],
            [[44, 73], [37, 77], [40, 86]],
        )
        self.assertEqual(
            [item["visible_in_final_difference"] for item in instances],
            [True, True, False],
        )

    def test_runtime_oam_instances_reject_unbound_secondary_attributes(self):
        profile = json.loads(GROUP1_PROFILE.read_text(encoding="utf-8"))
        profile["runtime_oam"]["instances"][1]["attributes"][1] = "0x4021"

        with self.assertRaisesRegex(ValueError, "OAM instance screen mapping"):
            self.builder._runtime_oam_instances(profile, 5, 1)

    def test_runtime_oam_instances_require_boolean_visibility(self):
        profile = json.loads(GROUP1_PROFILE.read_text(encoding="utf-8"))
        profile["runtime_oam"]["instances"][2][
            "visible_in_final_difference"
        ] = 0

        with self.assertRaisesRegex(ValueError, "OAM instance contract"):
            self.builder._runtime_oam_instances(profile, 5, 1)

    def test_runtime_oam_instances_map_source_pixel_through_horizontal_flip(self):
        profile = {
            "frame_id": 0,
            "component_index": 0,
            "component_pixel_xy": [12, 10],
            "screen_xy": [67, 58],
            "runtime_oam": {
                "oam_index": 1,
                "attributes": ["0x0030", "0x9030", "0x5920"],
                "obj_tile_base": 288,
                "palette_bank": 5,
            },
        }

        instances = self.builder._runtime_oam_instances(
            profile,
            12,
            10,
            component_width=32,
            component_height=32,
        )

        self.assertEqual(instances[0]["source_pixel_screen_xy"], [67, 58])

    def test_active_action_selector_resolves_action64_sequence17(self):
        catalog = json.loads(
            (
                ROOT
                / "artifacts/battle-effect-sequence-bindings-v1/manifest.json"
            ).read_text(encoding="utf-8")
        )
        binding, build_binding = self.builder._resolve_selector_binding(
            {
                "kind": "active_action",
                "id": 64,
                "encoded_action_id": 64,
            },
            catalog,
            sequence_id=17,
        )

        self.assertEqual(binding["action_id"], 64)
        self.assertEqual(binding["sequence_id"], 17)
        self.assertEqual(
            build_binding,
            {
                "active_action_id": 64,
                "encoded_action_id": 64,
                "sequence_id": 17,
            },
        )

    def test_runtime_oam_tile_is_bound_to_loaded_component_tile(self):
        profile = json.loads(GROUP1_PROFILE.read_text(encoding="utf-8"))

        self.assertEqual(
            self.builder._runtime_component_obj_tile_base(profile, 8), 264
        )
        profile["runtime_oam"]["obj_tile_base"] = 265
        with self.assertRaisesRegex(ValueError, "component tile mapping"):
            self.builder._runtime_component_obj_tile_base(profile, 8)

    def test_group14_active_action_profile_builds_same_topology_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.builder.build_pair(
                ROOT, GROUP14_PROFILE, Path(tmp) / "pair"
            )

        self.assertEqual(
            result["binding"],
            {
                "active_action_id": 16,
                "encoded_action_id": 16,
                "sequence_id": 16,
                "group_id": 14,
            },
        )
        self.assertEqual(result["edit"]["graphics_byte_offset"], 58)
        self.assertEqual(result["edit"]["screen_xy"], [173, 54])
        self.assertTrue(result["same_patch_topology"])
        self.assertTrue(result["same_encoded_size"])
        for variant in ("baseline", "candidate"):
            self.assertEqual(
                result["variants"][variant]["encoded_graphics_size"], 2138
            )

    def test_group15_natural_action_profile_builds_flipped_single_pixel_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.builder.build_pair(
                ROOT, GROUP15_PROFILE, Path(tmp) / "pair"
            )

        self.assertEqual(
            result["binding"],
            {
                "active_action_id": 64,
                "encoded_action_id": 64,
                "sequence_id": 17,
                "group_id": 15,
            },
        )
        self.assertEqual(result["edit"]["graphics_byte_offset"], 163)
        self.assertEqual(result["edit"]["screen_xy"], [65, 56])
        self.assertEqual(result["runtime_oam"]["attributes"][1], "0x9030")
        self.assertTrue(result["same_patch_topology"])
        self.assertTrue(result["same_encoded_size"])
        for variant in ("baseline", "candidate"):
            self.assertEqual(
                result["variants"][variant]["encoded_graphics_size"], 1560
            )

    def test_group13_natural_action_profile_builds_flipped_single_pixel_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.builder.build_pair(
                ROOT, GROUP13_PROFILE, Path(tmp) / "pair"
            )

        self.assertEqual(
            result["binding"],
            {
                "active_action_id": 61,
                "encoded_action_id": 61,
                "sequence_id": 15,
                "group_id": 13,
            },
        )
        self.assertEqual(result["edit"]["graphics_byte_offset"], 93)
        self.assertEqual(result["edit"]["screen_xy"], [96, 63])
        self.assertEqual(result["runtime_oam"]["attributes"][1], "0x9044")
        self.assertTrue(result["same_patch_topology"])
        self.assertTrue(result["same_encoded_size"])
        for variant in ("baseline", "candidate"):
            self.assertEqual(
                result["variants"][variant]["encoded_graphics_size"], 555
            )

    def test_group1_profile_keeps_trigger_and_resource_sequences_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.builder.build_pair(
                ROOT, GROUP1_PROFILE, Path(tmp) / "pair"
            )

        self.assertEqual(
            result["binding"],
            {
                "active_action_id": 5,
                "encoded_action_id": 5,
                "sequence_id": 1,
                "trigger_sequence_id": 6,
                "group_id": 1,
            },
        )
        self.assertEqual(result["edit"]["screen_pixels"], [[44, 73], [37, 77]])
        self.assertTrue(result["same_patch_topology"])
        self.assertTrue(result["same_encoded_size"])

    def test_group4_ninja_tool_profile_keeps_trigger_and_resource_sequences_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.builder.build_pair(
                ROOT, GROUP4_PROFILE, Path(tmp) / "pair"
            )

        self.assertEqual(
            result["binding"],
            {
                "ninja_tool_id": 1,
                "encoded_action_id": 129,
                "sequence_id": 4,
                "trigger_sequence_id": 13,
                "group_id": 4,
            },
        )
        self.assertEqual(result["edit"]["graphics_byte_offset"], 153)
        self.assertEqual(result["edit"]["screen_xy"], [83, 72])
        self.assertEqual(result["runtime_oam"]["attributes"], [
            "0x003A",
            "0x8051",
            "0x4900",
        ])
        self.assertTrue(result["same_patch_topology"])

    def test_profile_tampering_fails_closed(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        mutations = (
            {"group_id": 10},
            {"sequence_id": 12},
            {"graphics_byte_offset": 0x17},
            {"before_byte": 0x20},
            {"input_state_sha256": "0" * 64},
            {"input_evidence_sha256": "0" * 64},
            {"graphics_allocation_offset": 0xB41000},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(
                dir=ROOT / "build"
            ) as tmp:
                altered = copy.deepcopy(profile)
                altered.update(mutation)
                path = Path(tmp) / "profile.json"
                path.write_text(json.dumps(altered), encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.builder.build_pair(ROOT, path, Path(tmp) / "out")

    def test_rejects_nonempty_output_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            output.mkdir()
            marker = output / "keep"
            marker.write_text("user", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "empty"):
                self.builder.build_pair(ROOT, PROFILE, output)
            self.assertEqual(marker.read_text(encoding="utf-8"), "user")

    def test_rejects_external_profile_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile.json"
            profile.write_bytes(PROFILE.read_bytes())
            output = Path(tmp) / "out"
            with self.assertRaisesRegex(ValueError, "profile.*repository"):
                self.builder.build_pair(ROOT, profile, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
