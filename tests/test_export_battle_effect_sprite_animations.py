#!/usr/bin/env python3
"""ROM-backed tests for all battle-effect child sprite animations."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
RESOURCE_TABLE_SHA256 = (
    "7d9f94e05b975940bd2e17f55681120782cb7b6f07d0ab6245adef7260d24130"
)
SPRITE_PAIR_TABLE_SHA256 = (
    "c7025f5ca83b63b21ff3bf3e3183602447d157cf6cd1e63395b918a318e74392"
)
MOTION_TABLE_SHA256 = (
    "d1793f9c19b046ff1f431f28da31518c2093b77914b5c1f8b13f7e01d0ff1c6d"
)


class BattleEffectSpriteAnimationExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_battle_effect_sprite_animations import (
            export_battle_effect_sprite_animations,
        )

        cls._temporary = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls._temporary.name) / "effect-animations"
        cls.manifest = export_battle_effect_sprite_animations(
            ROOT,
            cls.output_dir,
        )

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def test_exports_hash_bound_tables_and_complete_counts(self):
        self.assertEqual(
            "battle-effect-sprite-animations-v1",
            self.manifest["schema"],
        )
        self.assertEqual(ROM_SHA256, self.manifest["rom"]["sha256"])
        self.assertEqual(
            {
                "file_offset": 0x59911C,
                "gba_address": "0x0859911C",
                "entry_count": 19,
                "entry_size": 8,
                "sha256": RESOURCE_TABLE_SHA256,
            },
            self.manifest["resource_pointer_table"],
        )
        self.assertEqual(
            {
                "file_offset": 0x5991B4,
                "gba_address": "0x085991B4",
                "entry_count": 19,
                "entry_size": 8,
                "sha256": SPRITE_PAIR_TABLE_SHA256,
            },
            self.manifest["sprite_pair_table"],
        )
        self.assertEqual(18, self.manifest["group_count"])
        self.assertEqual(178, self.manifest["frame_definition_count"])
        self.assertEqual(437, self.manifest["component_count"])
        self.assertEqual(23, self.manifest["animation_count"])
        self.assertEqual(193, self.manifest["keyframe_count"])
        self.assertEqual(179, self.manifest["artifact_file_count"])
        self.assertEqual(
            {
                "file_offset": 0x53EE98,
                "gba_address": "0x0853EE98",
                "entry_count": 15,
                "entry_size": 10,
                "sha256": MOTION_TABLE_SHA256,
            },
            self.manifest["motion_spawn_table"],
        )

    def test_preserves_every_group_frame_component_and_timeline_boundary(self):
        groups = self.manifest["groups"]
        self.assertEqual(list(range(1, 19)), [group["group_id"] for group in groups])
        self.assertEqual(
            [8, 26, 26, 4, 8, 11, 11, 11, 13, 7, 6, 6, 4, 8, 9, 5, 7, 8],
            [group["frame_count"] for group in groups],
        )
        self.assertEqual(
            [8, 26, 26, 4, 36, 47, 32, 28, 72, 40, 6, 8, 13, 23, 21, 5, 35, 7],
            [group["component_count"] for group in groups],
        )
        self.assertEqual(
            [1, 3, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1],
            [group["animation_count"] for group in groups],
        )
        self.assertTrue(
            all(group["definition_region_contiguous"] for group in groups)
        )
        self.assertTrue(
            all(group["timeline_region_contiguous"] for group in groups)
        )

    def test_animation_holds_match_static_and_existing_runtime_golden_durations(self):
        groups = {group["group_id"]: group for group in self.manifest["groups"]}
        self.assertEqual([59], groups[1]["animation_durations"])
        self.assertEqual([87, 52, 45], groups[2]["animation_durations"])
        self.assertEqual([7], groups[4]["animation_durations"])
        self.assertEqual([16], groups[5]["animation_durations"])
        self.assertEqual([8, 9], groups[13]["animation_durations"])
        self.assertEqual([30], groups[14]["animation_durations"])
        self.assertEqual([52], groups[18]["animation_durations"])
        self.assertEqual(
            [
                {"frame_id": 0, "hold_frames": 2},
                {"frame_id": 1, "hold_frames": 2},
                {"frame_id": 2, "hold_frames": 2},
                {"frame_id": 3, "hold_frames": 2},
                {"frame_id": 4, "hold_frames": 2},
                {"frame_id": 5, "hold_frames": 2},
                {"frame_id": 6, "hold_frames": 2},
                {"frame_id": 7, "hold_frames": 2},
            ],
            groups[5]["animations"][0]["keyframes"],
        )
        self.assertEqual(
            {
                "group_01_action_05_dust_frames": 59,
                "group_04_bomb_projectile_frames": 7,
                "group_05_action_05_hit_frames": 16,
                "group_14_action_16_fire_hit_frames": 30,
            },
            self.manifest["runtime_golden_duration_cross_checks"],
        )

    def test_closes_callback_spawn_plans_with_explicit_scheduler_boundary(self):
        plans = self.manifest["sequence_playback_plans"]
        self.assertEqual(list(range(22)), [plan["sequence_id"] for plan in plans])
        self.assertEqual("null", plans[0]["spawn_policy"])
        self.assertEqual([], plans[0]["spawn_events"])

        ballistic = plans[1]
        self.assertEqual("three_child_ballistic_rng", ballistic["spawn_policy"])
        self.assertEqual(3, len(ballistic["spawn_events"]))
        self.assertEqual([0, 0, 0], [
            event["spawn_tick"] for event in ballistic["spawn_events"]
        ])
        self.assertEqual(59, ballistic["last_child_static_completion_tick"])
        self.assertFalse(ballistic["screen_coordinates_complete"])

        motion = self.manifest["motion_spawn_records"]
        self.assertEqual(15, len(motion))
        self.assertEqual(-1, motion[-1]["effect_id"])
        self.assertEqual(
            [0, 4, 4, 8, 8, 8, 12, 12, 16, 16, 16, 20, 20, 24],
            [record["spawn_tick"] for record in motion[:-1]],
        )
        self.assertEqual(
            [1, 0, 2, 1, 1, 2, 0, 1, 1, 0, 2, 0, 0, 0],
            [record["effect_id"] for record in motion[:-1]],
        )
        for sequence_id in (2, 3):
            plan = plans[sequence_id]
            self.assertEqual("motion_table_fan_out", plan["spawn_policy"])
            self.assertEqual(14, len(plan["spawn_events"]))
            self.assertEqual(111, plan["last_child_static_completion_tick"])
        raw_render_attributes = [
            record["render_attributes"] for record in motion[:-1]
        ]
        self.assertEqual(
            [(value << 8) | 0x400 for value in raw_render_attributes],
            [
                event["render_attributes_argument"]
                for event in plans[2]["spawn_events"]
            ],
        )
        self.assertEqual(
            [value << 8 for value in raw_render_attributes],
            [
                event["render_attributes_argument"]
                for event in plans[3]["spawn_events"]
            ],
        )
        forced = plans[18]
        self.assertEqual("motion_table_forced_variant_zero", forced["spawn_policy"])
        self.assertTrue(all(
            event["animation_variant"] == 0
            for event in forced["spawn_events"]
        ))
        self.assertEqual(76, forced["last_child_static_completion_tick"])

        self.assertEqual(16, plans[6]["last_child_static_completion_tick"])
        self.assertEqual(8, plans[15]["last_child_static_completion_tick"])
        self.assertEqual(87, plans[21]["last_child_static_completion_tick"])
        self.assertEqual(
            {
                "minimum_extra_scheduler_ticks": 0,
                "maximum_extra_scheduler_ticks": 1,
                "reason": (
                    "parent/child task slot order within the user-visible "
                    "frame is not statically fixed"
                ),
            },
            self.manifest["parent_release_scheduler_boundary"],
        )

    def test_closes_every_child_task_origin_formula_without_overclaiming_oam(self):
        model = self.manifest["child_task_origin_model"]
        self.assertEqual(
            {
                "+0x00": "u32 render_flags",
                "+0x04": "s16 anchor_x",
                "+0x06": "s16 anchor_y",
                "+0x08": "s16 delta_x",
                "+0x0A": "s16 delta_y",
                "+0x2C": "s32 ballistic_x_q8_8",
                "+0x30": "s32 ballistic_y_q8_8",
                "+0x34": "s32 ballistic_angle; callback consumes low s16",
                "+0x38": "s32 ballistic_speed",
            },
            model["task_fields"],
        )
        self.assertEqual(
            "s16(parent_x + effective_x_offset)",
            model["constructor"]["initial_anchor_x"],
        )
        self.assertEqual(
            "s16(parent_y + y_offset)",
            model["constructor"]["initial_anchor_y"],
        )
        self.assertEqual(
            "s16(-x_offset)",
            model["constructor"]["mirrored_x_offset"],
        )
        self.assertEqual(
            "s16(actor_anchor_x(t) + delta_x)",
            model["actor_follow"]["task_origin_x_at_tick"],
        )
        self.assertEqual(
            "s16(actor_anchor_y(t) + delta_y)",
            model["actor_follow"]["task_origin_y_at_tick"],
        )
        self.assertEqual(
            "s16(component_x + task.anchor_x + task.delta_x)",
            model["actor_follow"]["consumer_x_formula"],
        )
        composition_slice = next(
            item
            for item in self.manifest["consumer_code_slices"]
            if item["name"]
            == "task_origin_and_component_position_composition"
        )
        self.assertEqual("0x08062C58", composition_slice["gba_start"])
        self.assertEqual("0x08062C7C", composition_slice["gba_end"])
        self.assertEqual(
            "dc022a30c9ef95ab0bcb78e1a00e9cfa5c3bc4793e9c8352dd664086323e8313",
            composition_slice["sha256"],
        )
        self.assertEqual(
            "max(0, speed_t - 24)",
            model["rng_ballistic"]["speed_transition"],
        )
        self.assertEqual(
            "truncate_toward_zero_q8_8(s32(x_q8_8_t))",
            model["rng_ballistic"]["task_origin_x_at_tick"],
        )
        self.assertEqual(
            "truncate_toward_zero_q8_8(s32(y_q8_8_t))",
            model["rng_ballistic"]["task_origin_y_at_tick"],
        )

        plans = self.manifest["sequence_playback_plans"]
        self.assertEqual("none", plans[0]["child_task_origin_model_id"])
        self.assertEqual(
            "rng_ballistic",
            plans[1]["child_task_origin_model_id"],
        )
        for sequence_id in (2, 3, 18):
            self.assertEqual(
                "parent_offset_static",
                plans[sequence_id]["child_task_origin_model_id"],
            )
        for sequence_id in (8, 9, 11, 16):
            self.assertEqual(
                "actor_anchor_follow",
                plans[sequence_id]["child_task_origin_model_id"],
            )
        for sequence_id in (4, 5, 6, 7, 10, 12, 13, 14, 15, 17, 19, 20, 21):
            self.assertEqual(
                "parent_origin_static",
                plans[sequence_id]["child_task_origin_model_id"],
            )

        scope = self.manifest["scope"]
        self.assertTrue(scope["child_task_origin_formulas_complete"])
        self.assertTrue(scope["child_task_side_mirroring_formula_complete"])
        self.assertFalse(scope["concrete_rng_trajectory_complete"])
        self.assertFalse(scope["screen_space_oam_composition_complete"])
        self.assertFalse(scope["runtime_affine_rasterization_complete"])

    def test_closes_static_oam_attribute_formulas_without_claiming_affine_pixels(self):
        model = self.manifest["oam_attribute_model"]
        self.assertEqual(
            {
                "8x8": "0x00000000",
                "8x16": "0x00008000",
                "8x32": "0x40008000",
                "16x8": "0x00004000",
                "16x16": "0x40000000",
                "16x32": "0x80008000",
                "32x8": "0x40004000",
                "32x16": "0x80004000",
                "32x32": "0x80000000",
                "32x64": "0xC0008000",
                "64x32": "0xC0004000",
                "64x64": "0xC0000000",
            },
            model["shape_size_combined_masks"],
        )
        self.assertEqual(
            [
                "8x8",
                "8x16",
                "8x32",
                "16x8",
                "16x16",
                "32x8",
                "32x16",
                "32x32",
            ],
            model["observed_component_sizes"],
        )
        self.assertEqual(
            "u8(renderer_final_y)",
            model["attr0"]["y_coordinate"],
        )
        self.assertEqual(
            "u9(renderer_final_x)",
            model["attr1"]["x_coordinate"],
        )
        self.assertEqual(
            "u2(component.tile_flags XOR ((task.render_flags & 0x00018000) >> 15))",
            model["attr1"]["non_affine_flip_bits"],
        )
        self.assertEqual(
            (
                "(renderer_stack_mode_byte & 1) == 0 and task.byte_13 == 0 "
                "and task.scale_xy_q8_8 == 0x01000100 and "
                "(task.render_flags & 0x00080000) == 0"
            ),
            model["attr1"]["non_affine_flip_placement_guard"],
        )
        self.assertEqual(
            "u16(task.tile_base + component.tile_index)",
            model["attr2"]["tile_index"],
        )
        self.assertEqual(
            "u4(task.palette_bank) << 12",
            model["attr2"]["palette_bank"],
        )
        self.assertEqual(
            "(task.render_flags & 0x000000C0) << 4",
            model["attr2"]["priority"],
        )
        self.assertEqual(
            [0, 256, 512, 784, 1024, 1280, 1536, 268435456],
            model["normal_path_reachability"][
                "reachable_render_attributes_arguments"
            ],
        )
        self.assertTrue(
            model["normal_path_reachability"][
                "all_reachable_arguments_clear_bit_22"
            ]
        )
        self.assertTrue(
            model["model_boundaries"][
                "pre_attr_coordinate_transform_model_linked"
            ]
        )
        self.assertFalse(
            model["model_boundaries"][
                "pre_attr_concrete_runtime_values_applied"
            ]
        )
        renderer_slice = next(
            item
            for item in self.manifest["consumer_code_slices"]
            if item["name"] == "oam_shape_size_affine_and_attribute_writer"
        )
        self.assertEqual("0x08062D92", renderer_slice["gba_start"])
        self.assertEqual("0x08063186", renderer_slice["gba_end"])
        self.assertEqual(
            "566415d7bf30967ce2f4228311e13e5b63e2de3d620b1d68e3622d58da9f8d23",
            renderer_slice["sha256"],
        )

        scope = self.manifest["scope"]
        self.assertTrue(scope["oam_shape_size_encoding_complete"])
        self.assertTrue(scope["oam_coordinate_field_wrapping_complete"])
        self.assertTrue(
            scope["normal_oam_tile_palette_priority_formula_complete"]
        )
        self.assertTrue(
            scope["guarded_oam_non_affine_flip_formula_complete"]
        )
        self.assertFalse(scope["screen_space_oam_composition_complete"])
        self.assertFalse(scope["runtime_affine_rasterization_complete"])

    def test_closes_pre_oam_offset_scale_and_visibility_formulas(self):
        model = self.manifest["pre_oam_coordinate_transform_model"]
        self.assertEqual(
            "0x03000054",
            model["runtime_offset_table"]["iwram_address"],
        )
        self.assertEqual(
            "(task.render_flags & 0x00001000) != 0",
            model["runtime_offset_table"]["enabled_when"],
        )
        self.assertEqual(
            "(task.render_flags & 0x00006000) >> 13",
            model["runtime_offset_table"]["pair_index"],
        )
        self.assertEqual(
            (
                "s16(x_after_origin - "
                "(s32(offset_table[pair_index*2]) >> 8))"
            ),
            model["runtime_offset_table"]["x_after_offset"],
        )
        self.assertEqual(
            (
                "s16(y_after_origin - "
                "(s32(offset_table[pair_index*2+1]) >> 8))"
            ),
            model["runtime_offset_table"]["y_after_offset"],
        )
        self.assertEqual(
            [
                {
                    "kind": "initialize_all_entries_to_zero",
                    "code_range": "0x08061624..0x08061710",
                    "write_range": "0x080616D0..0x080616E0",
                    "direct_caller_known": False,
                },
                {
                    "kind": "reset_runtime_selected_entry_to_zero",
                    "code_range": "0x08065404..0x08065554",
                    "write_range": "0x08065528..0x0806553A",
                    "direct_caller_count": 23,
                },
                {
                    "kind": "state_driven_dynamic_update",
                    "code_range": "0x0806E958..0x0806EA96",
                    "state_1_effect": "write entry 0 x/y from runtime sources",
                    "state_2_effect": (
                        "add/subtract runtime delta across entries 0 and 1"
                    ),
                },
            ],
            model["runtime_offset_table"]["writer_evidence"],
        )
        self.assertEqual(
            (
                "q8_8_mul_trunc0(a,b) = "
                "s32(a*b + (255 if s32(a*b) < 0 else 0)) >> 8"
            ),
            model["scale_and_extent"]["q8_8_multiply"],
        )
        self.assertEqual(
            (
                "min_s16(pre_scale_width,"
                "s16(q8_8_mul_trunc0("
                "q8_8_mul_trunc0(component.width,task.scale_x),"
                "component.scale_x)))"
            ),
            model["scale_and_extent"]["scaled_width"],
        )
        self.assertEqual(
            [
                {
                    "group_id": 2,
                    "frame_id": 1,
                    "component_index": 0,
                    "width": 32,
                    "height": 32,
                    "scale_x": 272,
                    "scale_y": 272,
                    "affine_mode": 1,
                },
                {
                    "group_id": 3,
                    "frame_id": 1,
                    "component_index": 0,
                    "width": 32,
                    "height": 32,
                    "scale_x": 272,
                    "scale_y": 272,
                    "affine_mode": 1,
                },
            ],
            model["scale_and_extent"]["observed_non_default_components"],
        )
        self.assertEqual(
            [
                "x_after_offset + scaled_width > 0",
                "y_after_offset + scaled_height > 0",
                (
                    "x_after_offset < 240 - "
                    "trunc0_div2(pre_scale_width-scaled_width)"
                ),
                (
                    "y_after_offset < 160 - "
                    "trunc0_div2(pre_scale_height-scaled_height)"
                ),
            ],
            model["visibility_gate"]["all_required_conditions"],
        )
        transform_slice = next(
            item
            for item in self.manifest["consumer_code_slices"]
            if item["name"] == "pre_oam_offset_scale_and_visibility"
        )
        self.assertEqual("0x08062C7C", transform_slice["gba_start"])
        self.assertEqual("0x08062D92", transform_slice["gba_end"])
        self.assertEqual(
            "725a25fba4d30a78d197ea94b4ebf272ab03d48692e20c3e3a7bcfac82264039",
            transform_slice["sha256"],
        )

        scope = self.manifest["scope"]
        self.assertTrue(scope["pre_oam_runtime_offset_formula_complete"])
        self.assertTrue(scope["pre_oam_scale_extent_formula_complete"])
        self.assertTrue(scope["pre_oam_visibility_gate_complete"])
        self.assertFalse(scope["concrete_runtime_offset_table_values_complete"])
        self.assertFalse(scope["screen_space_oam_composition_complete"])
        boundaries = model["model_boundaries"]
        self.assertTrue(boundaries["runtime_offset_table_initialization_known"])
        self.assertTrue(boundaries["runtime_offset_table_slot_reset_known"])
        self.assertTrue(
            boundaries["runtime_offset_table_dynamic_writer_family_known"]
        )
        self.assertFalse(
            boundaries["runtime_offset_table_complete_schedule_known"]
        )

        writer_slices = {
            item["name"]: item
            for item in self.manifest["consumer_code_slices"]
            if item["name"].startswith("runtime_offset_table_")
        }
        self.assertEqual(
            "e3ba1dadf23b428fd2a39b6d9aef48b7ba9521d825ca196b37d7a93403192dff",
            writer_slices["runtime_offset_table_initializer"]["sha256"],
        )
        self.assertEqual(
            "213423e70948ef3dbd91ed7854efb5c52fd7543f4b73b4a4a2219ffd89ce66f7",
            writer_slices["runtime_offset_table_slot_reset"]["sha256"],
        )
        self.assertEqual(
            "66f49791cd737c096ed6a7785591e202287b02dd679a4e2f5c095cd18c1c86a0",
            writer_slices["runtime_offset_table_dynamic_update"]["sha256"],
        )

    def test_all_decompressed_tiles_are_referenced_by_component_geometry(self):
        for group in self.manifest["groups"]:
            coverage = group["tile_coverage"]
            self.assertEqual(
                list(range(group["graphics"]["tile_count"])),
                coverage["referenced_tile_indices"],
            )
            self.assertEqual([], coverage["missing_tile_indices"])
            self.assertTrue(coverage["all_tiles_referenced"])
            self.assertEqual(32, group["palette"]["decompressed_size"])

    def test_outputs_indexed_source_space_preview_for_every_frame(self):
        pngs = sorted(self.output_dir.glob("group-*-frame-*.png"))
        self.assertEqual(178, len(pngs))
        group_five = self.manifest["groups"][4]
        frame_two = group_five["frames"][2]
        self.assertEqual(8, frame_two["component_count"])
        with Image.open(self.output_dir / frame_two["preview"]["png"]) as image:
            image.load()
            self.assertEqual("P", image.mode)
            self.assertEqual(
                (frame_two["preview"]["width"], frame_two["preview"]["height"]),
                image.size,
            )
            self.assertEqual(0, image.info["transparency"])
        empty = self.manifest["groups"][17]["frames"][7]
        self.assertEqual(0, empty["component_count"])
        self.assertEqual([1, 1], [
            empty["preview"]["width"],
            empty["preview"]["height"],
        ])

    def test_scope_closes_child_assets_without_overclaiming_screen_oam(self):
        self.assertEqual(
            {
                "all_nonzero_resource_groups_complete": True,
                "definition_pointer_tables_complete": True,
                "component_lists_complete": True,
                "child_animation_timelines_complete": True,
                "child_frame_hold_timing_complete": True,
                "component_local_geometry_complete": True,
                "source_tile_coverage_complete": True,
                "source_space_previews_complete": True,
                "callback_spawn_state_machines_complete": True,
                "callback_child_variant_and_hold_complete": True,
                "child_task_origin_formulas_complete": True,
                "child_task_side_mirroring_formula_complete": True,
                "oam_shape_size_encoding_complete": True,
                "oam_coordinate_field_wrapping_complete": True,
                "normal_oam_tile_palette_priority_formula_complete": True,
                "guarded_oam_non_affine_flip_formula_complete": True,
                "pre_oam_runtime_offset_formula_complete": True,
                "pre_oam_scale_extent_formula_complete": True,
                "pre_oam_visibility_gate_complete": True,
                "concrete_runtime_offset_table_values_complete": False,
                "concrete_rng_trajectory_complete": False,
                "callback_random_screen_coordinates_complete": False,
                "parent_visible_release_tick_exact": False,
                "screen_space_oam_composition_complete": False,
                "runtime_mirroring_and_affine_complete": False,
                "runtime_affine_rasterization_complete": False,
                "blend_and_audio_binding_complete": False,
            },
            self.manifest["scope"],
        )

    def test_independent_verifier_rejects_manifest_and_png_tampering(self):
        from tools.verify_battle_effect_sprite_animations import (
            verify_battle_effect_sprite_animations,
        )

        result = verify_battle_effect_sprite_animations(ROOT, self.output_dir)
        self.assertEqual([], result["errors"])
        self.assertEqual(18, result["verified_groups"])
        self.assertEqual(178, result["verified_frames"])
        self.assertEqual(437, result["verified_components"])
        self.assertEqual(23, result["verified_animations"])

        verifier_source = (
            ROOT / "tools/verify_battle_effect_sprite_animations.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("export_battle_effect_sprite_animations", verifier_source)

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "tampered"
            shutil.copytree(self.output_dir, tampered)
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["groups"][4]["animations"][0]["keyframes"][0][
                "hold_frames"
            ] = 3
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_battle_effect_sprite_animations(ROOT, tampered)
            self.assertTrue(
                any("hold_frames" in error for error in result["errors"]),
                result["errors"],
            )

            manifest["groups"][4]["animations"][0]["keyframes"][0][
                "hold_frames"
            ] = 2
            manifest["sequence_playback_plans"][2]["spawn_events"][0][
                "render_attributes_argument"
            ] = 0x402
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_battle_effect_sprite_animations(ROOT, tampered)
            self.assertTrue(
                any(
                    "render_attributes_argument" in error
                    for error in result["errors"]
                ),
                result["errors"],
            )

            manifest["sequence_playback_plans"][2]["spawn_events"][0][
                "render_attributes_argument"
            ] = 0x600
            manifest["child_task_origin_model"]["rng_ballistic"][
                "speed_transition"
            ] = "max(0, speed_t - 23)"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_battle_effect_sprite_animations(ROOT, tampered)
            self.assertTrue(
                any("speed_transition" in error for error in result["errors"]),
                result["errors"],
            )

            manifest["child_task_origin_model"]["rng_ballistic"][
                "speed_transition"
            ] = "max(0, speed_t - 24)"
            manifest["oam_attribute_model"]["attr2"]["priority"] = (
                "(task.render_flags & 0x00000080) << 3"
            )
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_battle_effect_sprite_animations(ROOT, tampered)
            self.assertTrue(
                any("attr2.priority" in error for error in result["errors"]),
                result["errors"],
            )

            manifest["oam_attribute_model"]["attr2"]["priority"] = (
                "(task.render_flags & 0x000000C0) << 4"
            )
            manifest["oam_attribute_model"]["shape_size_combined_masks"][
                "32x16"
            ] = "0x40004000"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_battle_effect_sprite_animations(ROOT, tampered)
            self.assertTrue(
                any(
                    "shape_size_combined_masks.32x16" in error
                    for error in result["errors"]
                ),
                result["errors"],
            )

            manifest["oam_attribute_model"]["shape_size_combined_masks"][
                "32x16"
            ] = "0x80004000"
            manifest["pre_oam_coordinate_transform_model"][
                "visibility_gate"
            ]["all_required_conditions"][0] = (
                "x_after_offset + scaled_width >= 0"
            )
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_battle_effect_sprite_animations(ROOT, tampered)
            self.assertTrue(
                any(
                    "visibility_gate.all_required_conditions[0]" in error
                    for error in result["errors"]
                ),
                result["errors"],
            )

            manifest["pre_oam_coordinate_transform_model"][
                "visibility_gate"
            ]["all_required_conditions"][0] = (
                "x_after_offset + scaled_width > 0"
            )
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            png_path = tampered / manifest["groups"][4]["frames"][0]["preview"]["png"]
            png_path.write_bytes(png_path.read_bytes() + b"tamper")
            result = verify_battle_effect_sprite_animations(ROOT, tampered)
            self.assertTrue(
                any("png_sha256" in error for error in result["errors"]),
                result["errors"],
            )

    def test_cli_export_is_deterministic_and_verifiable(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "export"
            export_command = [
                sys.executable,
                str(ROOT / "tools/export_battle_effect_sprite_animations.py"),
                "--root",
                str(ROOT),
                "--output-dir",
                str(output_dir),
            ]
            subprocess.run(export_command, check=True, cwd=ROOT)
            first_manifest = (output_dir / "manifest.json").read_bytes()
            first_png = (output_dir / "group-05-frame-06.png").read_bytes()
            subprocess.run(export_command, check=True, cwd=ROOT)
            self.assertEqual(
                first_manifest,
                (output_dir / "manifest.json").read_bytes(),
            )
            self.assertEqual(
                first_png,
                (output_dir / "group-05-frame-06.png").read_bytes(),
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/verify_battle_effect_sprite_animations.py"),
                    "--root",
                    str(ROOT),
                    "--artifact-dir",
                    str(output_dir),
                ],
                check=True,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertIn('"errors": []', completed.stdout)


if __name__ == "__main__":
    unittest.main()
