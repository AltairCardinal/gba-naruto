#!/usr/bin/env python3
"""ROM-backed bindings from 24 story overlays to their linked BG layers."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_IDS = [
    4, 10, 14, 24, 17, 18, 21, 25, 29, 28, 34, 76,
    30, 47, 48, 49, 51, 52, 58, 61, 74, 16, 77, 5,
]


class StorySceneLayerBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_story_scene_layer_bindings import (
            export_story_scene_layer_bindings,
        )

        cls._temporary = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls._temporary.name) / "bindings"
        cls.manifest = export_story_scene_layer_bindings(
            ROOT,
            cls.output_dir,
        )

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def test_exports_all_direct_zero_based_story_links(self):
        self.assertEqual(
            "story-scene-layer-bindings-v1",
            self.manifest["schema"],
        )
        self.assertEqual(24, self.manifest["binding_count"])
        self.assertEqual(
            CONFIG_IDS,
            [binding["config_id"] for binding in self.manifest["bindings"]],
        )
        self.assertEqual(
            [config_id + 1 for config_id in CONFIG_IDS],
            [binding["consumer_id"] for binding in self.manifest["bindings"]],
        )
        self.assertEqual([], self.manifest["sentinel_config_ids"])
        self.assertEqual(
            "direct_zero_based_config_id_times_0x44",
            self.manifest["selection"]["indexing"],
        )

    def test_binds_consumer_proven_hardware_layers_without_layer_a(self):
        binding = self.manifest["bindings"][0]
        by_name = {layer["name"]: layer for layer in binding["layers"]}
        self.assertEqual({"story_overlay", "B", "C", "D"}, set(by_name))
        self.assertEqual(
            {
                "background": "BG3",
                "priority": 0,
                "charblock": 3,
                "screenblock": 3,
                "palette_bank": 15,
                "bits_per_pixel": 4,
            },
            by_name["story_overlay"]["hardware"],
        )
        self.assertEqual(
            {
                "status": "resolved",
                "initializer_bgcnt": "0x0300",
                "story_override_bgcnt": "0x030C",
                "story_override_gba_address": "0x08087CEA",
                "configured_tile_address": "0x0600E800",
                "graphics_destination": "0x0600E800",
                "resource_address_implied_charblock": 3,
                "reason": (
                    "story_override_selects_charblock_3_before_bg3_enable"
                ),
            },
            by_name["story_overlay"]["layout_consistency"],
        )
        self.assertEqual(
            {
                "background": "BG2",
                "priority": 3,
                "charblock": 3,
                "screenblock": 2,
                "palette_bank": 12,
                "bits_per_pixel": 4,
            },
            by_name["B"]["hardware"],
        )
        self.assertEqual(8, by_name["C"]["hardware"]["bits_per_pixel"])
        self.assertEqual(0, by_name["C"]["hardware"]["palette_bank"])
        self.assertEqual(
            "consumer_argument_path_not_used_by_story_installer",
            binding["excluded_layer_a"]["reason"],
        )

    def test_records_priority_swap_and_d_load_enable_gates(self):
        by_config = {
            binding["config_id"]: binding
            for binding in self.manifest["bindings"]
        }
        self.assertEqual(1, by_config[61]["layers"][2]["hardware"]["priority"])
        self.assertEqual(2, by_config[61]["layers"][3]["hardware"]["priority"])
        self.assertEqual(
            [10, 16, 61, 74],
            sorted(
                config_id
                for config_id, binding in by_config.items()
                if binding["layers"][3]["resource_loaded"]
            ),
        )
        self.assertEqual(
            [16],
            sorted(
                config_id
                for config_id, binding in by_config.items()
                if binding["layers"][3]["initially_enabled"]
            ),
        )
        self.assertFalse(by_config[4]["layers"][3]["resource_loaded"])
        self.assertEqual(
            "suppressed_by_descriptor_flag_0x0400",
            by_config[4]["layers"][3]["load_state"],
        )

    def test_scope_refuses_to_claim_a_runtime_final_composite(self):
        self.assertFalse(self.manifest["scope"]["final_composite"])
        self.assertEqual(
            90,
            self.manifest["timing"]["linked_transition_frames_before_overlay"],
        )
        self.assertEqual(
            240,
            self.manifest["timing"]["story_overlay_visible_frames"],
        )
        self.assertEqual(
            {
                "scroll_and_wrap",
                "blend_and_brightness",
                "palette_transform",
                "dynamic_bg_enable",
                "shared_c_d_vram_state",
            },
            set(self.manifest["scope"]["runtime_state_still_required"]),
        )

    def test_independent_verifier_rebuilds_and_rejects_tampering(self):
        from tools.verify_story_scene_layer_bindings import (
            verify_story_scene_layer_bindings,
        )

        result = verify_story_scene_layer_bindings(ROOT, self.output_dir)
        self.assertEqual(
            "story-scene-layer-bindings-verification-v1",
            result["schema"],
        )
        self.assertEqual(24, result["verified_bindings"])
        self.assertEqual([], result["errors"])

        manifest_path = self.output_dir / "manifest.json"
        original = manifest_path.read_bytes()
        tampered = json.loads(original)
        tampered["bindings"][0]["config_id"] = 5
        tampered["bindings"][19]["layers"][2]["hardware"]["priority"] = 2
        tampered["bindings"][21]["layers"][3]["initially_enabled"] = False
        tampered["bindings"][0]["layers"][0]["layout_consistency"]["status"] = (
            "unresolved"
        )
        tampered["scope"]["final_composite"] = True
        try:
            manifest_path.write_text(
                json.dumps(tampered, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_story_scene_layer_bindings(ROOT, self.output_dir)
        finally:
            manifest_path.write_bytes(original)
        self.assertIn("manifest does not match ROM-derived bindings", result["errors"])

    def test_cli_and_committed_manifest_repeat_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bindings"
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/export_story_scene_layer_bindings.py",
                    "--root",
                    ".",
                    "--output-dir",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertIn("24 story scene bindings", completed.stdout)
            self.assertEqual(
                (self.output_dir / "manifest.json").read_bytes(),
                (output / "manifest.json").read_bytes(),
            )
            self.assertEqual(
                (self.output_dir / "manifest.json").read_bytes(),
                (
                    ROOT
                    / "artifacts/story-scene-layer-bindings-v1/manifest.json"
                ).read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
