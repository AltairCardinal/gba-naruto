from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-11-cross-shuriken.json"
ARTIFACT = ROOT / "artifacts/battle-effect-group11-pixel-ab-v1"
GROUP14_PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-14-fire-action.json"
GROUP14_ARTIFACT = ROOT / "artifacts/battle-effect-group14-pixel-ab-v1"
GROUP15_PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-15-action64-water-dragon.json"
GROUP15_ARTIFACT = ROOT / "artifacts/battle-effect-group15-pixel-ab-v1"
GROUP2_PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-02-action7-shadow-clone.json"
GROUP2_ARTIFACT = ROOT / "artifacts/battle-effect-group2-pixel-ab-v1"
GROUP4_PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-04-tool1-projectile.json"
GROUP4_ARTIFACT = ROOT / "artifacts/battle-effect-group4-pixel-ab-v1"


class ExportBattleEffectPixelAbEvidenceTests(unittest.TestCase):
    def test_classifies_only_the_known_vblank_wait_boundary_stack_phase(self):
        from tools import export_battle_effect_pixel_ab_evidence as exporter

        baseline = bytearray(0x8000)
        candidate = bytearray(0x8000)
        baseline[0x7F9C:0x7FA0] = (0x08061130).to_bytes(4, "little")
        candidate[0x7F9C:0x7FA0] = (0x0806112C).to_bytes(4, "little")
        self.assertEqual(
            exporter._vblank_wait_capture_phase(
                bytes(baseline), bytes(candidate), [0x7F9C]
            ),
            {
                "iwram_address": "0x03007F9C",
                "baseline_return_address": "0x08061130",
                "candidate_return_address": "0x0806112C",
                "classification": "vblank-wait-boundary",
            },
        )
        candidate[0x7F9C:0x7FA0] = (0x08070000).to_bytes(4, "little")
        self.assertIsNone(
            exporter._vblank_wait_capture_phase(
                bytes(baseline), bytes(candidate), [0x7F9C]
            )
        )

    def test_current_runtime_toolchain_contract_is_bound_to_tracked_profile(self):
        from tools import export_battle_effect_pixel_ab_evidence as exporter

        profile = json.loads(GROUP15_PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(
            exporter._runtime_toolchain_contract(ROOT, profile),
            {
                "kind": "current-desktop-runtime-profile",
                "path": "artifacts/rom-expansion-profile-v1/profile.json",
                "sha256": "e21d375914dda3c20b05ccec45c39406db310609e69ee19d04dfa342f4b70287",
                "binary_sha256": "c1135d28ec17def50c6cea0ef635bf1c4902290a4d2e9ba4a5376c300da642c8",
                "source_commit": "d8bad14b4540f9114246c0281d74985cf81adc68",
            },
        )

    def test_runtime_tile_base_derives_from_vram_load_and_component(self):
        from tools import export_battle_effect_pixel_ab_evidence as exporter

        profile = {
            "runtime_oam": {
                "obj_vram_address": "0x06012000",
                "obj_tile_base": 264,
            }
        }
        self.assertEqual(exporter._runtime_component_obj_tile_base(profile, 8), 264)

    def test_build_manifest_allows_only_a_validated_oam_instances_extension(self):
        from tools import export_battle_effect_pixel_ab_evidence as exporter

        profile = {
            "runtime_oam": {
                "oam_index": 0,
                "attributes": ["0x0048", "0x4027", "0x4908"],
                "instances": [{"oam_index": 0}],
            }
        }
        historical = {
            "profile_sha256": "1" * 64,
            "runtime_oam": {
                "oam_index": 0,
                "attributes": ["0x0048", "0x4027", "0x4908"],
            },
        }

        self.assertTrue(
            exporter._build_manifest_profile_metadata_matches(
                historical, profile, "2" * 64
            )
        )
        historical["runtime_oam"]["oam_index"] = 1
        self.assertFalse(
            exporter._build_manifest_profile_metadata_matches(
                historical, profile, "2" * 64
            )
        )

    def test_preserves_generation_hashes_when_resigning_existing_raw_evidence(self):
        from tools import export_battle_effect_pixel_ab_evidence as exporter

        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            raw = artifact / "raw"
            raw.mkdir(parents=True)
            marker = raw / "marker.bin"
            marker.write_bytes(b"runtime evidence")
            raw_hashes = {
                "marker.bin": hashlib.sha256(marker.read_bytes()).hexdigest()
            }
            current = {
                path: "2" * 64 for path in exporter.IMPLEMENTATION_PATHS
            }
            historical = {
                path: "1" * 64 for path in exporter.IMPLEMENTATION_PATHS
            }
            (artifact / "manifest.json").write_text(
                json.dumps(
                    {
                        "raw_files": raw_hashes,
                        "implementation_sha256": historical,
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                exporter._generation_implementation_hashes(
                    raw, raw_hashes, current
                ),
                historical,
            )

    def test_preload_evidence_allows_recorded_stale_baseline_elsewhere(self):
        from tools import export_battle_effect_pixel_ab_evidence as exporter

        baseline = b"ABCD"
        candidate = b"ABXD"
        vram = bytearray(32)
        vram[16:20] = baseline

        self.assertEqual(
            exporter._preload_evidence(bytes(vram), baseline, candidate, 0),
            {
                "candidate_resource_absent_before_input": True,
                "target_candidate_absent_before_input": True,
                "stale_baseline_locations": ["0x06010010"],
            },
        )

    def test_expected_pixels_support_multiple_rendered_instances(self):
        from tools import export_battle_effect_pixel_ab_evidence as exporter

        profile = {
            "screen_xy": [44, 73],
            "screen_pixels": [[44, 73], [37, 77]],
            "before_rgb": [148, 140, 90],
            "after_rgb": [222, 214, 148],
        }

        self.assertEqual(
            exporter._expected_pixels(profile),
            [
                {
                    "x": 44,
                    "y": 73,
                    "before_rgb": [148, 140, 90],
                    "after_rgb": [222, 214, 148],
                },
                {
                    "x": 37,
                    "y": 77,
                    "before_rgb": [148, 140, 90],
                    "after_rgb": [222, 214, 148],
                },
            ],
        )

    def test_active_action_uses_distinct_natural_route_scope(self):
        from tools import export_battle_effect_pixel_ab_evidence as exporter

        self.assertEqual(
            exporter._selector_scope({"kind": "active_action"}),
            {
                "natural_active_action_route": True,
                "production_relocation_route": True,
                "single_group_single_frame_single_pixel": True,
                "all_18_effect_groups_runtime_verified": False,
                "all_group_frames_runtime_verified": False,
                "full_affine_blend_timing_audio_equivalence": False,
                "physical_gba_verified": False,
            },
        )

    def test_hardcoded_action_handler_uses_distinct_natural_route_scope(self):
        from tools import export_battle_effect_pixel_ab_evidence as exporter

        scope = exporter._selector_scope(
            {"kind": "active_action_handler_immediate"}
        )

        self.assertTrue(scope["natural_active_action_handler_immediate_route"])
        self.assertTrue(scope["production_relocation_route"])

    def test_reexports_group11_natural_single_pixel_chain(self):
        from tools.export_battle_effect_pixel_ab_evidence import export_evidence

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "artifact"
            evidence = export_evidence(ROOT, PROFILE, ARTIFACT / "raw", output)

            self.assertTrue(evidence["verified"])
            self.assertEqual(
                evidence["runtime"]["memory_differences"],
                {
                    "EWRAM": [],
                    "IWRAM": [],
                    "IO": [],
                    "PRAM": [],
                    "VRAM": [0x12C16],
                    "OAM": [],
                },
            )
            self.assertEqual(
                evidence["runtime"]["pixels"]["changes"],
                [
                    {
                        "x": 172,
                        "y": 61,
                        "before_rgb": [255, 255, 255],
                        "after_rgb": [255, 214, 181],
                    }
                ],
            )
            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["schema"], "git-artifact-promotion-v1")
            self.assertEqual(manifest["artifact_status"], "accepted")
            self.assertNotIn("implementation_sha256", manifest)
            source_manifest = json.loads(
                (ARTIFACT / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["generated_with_implementation_sha256"],
                source_manifest.get(
                    "generated_with_implementation_sha256",
                    source_manifest.get("implementation_sha256"),
                ),
            )
            self.assertNotEqual(
                manifest["generated_with_implementation_sha256"],
                manifest["verified_with_implementation_sha256"],
            )
            self.assertEqual(manifest["verifier"]["exit_code"], 0)
            self.assertEqual(
                manifest["verifier"]["result"],
                {"errors": [], "verified": True},
            )

    def test_reexports_group14_active_action_single_pixel_chain(self):
        from tools.export_battle_effect_pixel_ab_evidence import export_evidence

        with tempfile.TemporaryDirectory() as tmp:
            evidence = export_evidence(
                ROOT,
                GROUP14_PROFILE,
                GROUP14_ARTIFACT / "raw",
                Path(tmp) / "artifact",
            )

        self.assertEqual(
            evidence["binding"],
            {
                "active_action_id": 16,
                "encoded_action_id": 16,
                "sequence_id": 16,
                "group_id": 14,
            },
        )
        self.assertEqual(evidence["runtime"]["memory_differences"]["VRAM"], [0x1243A])
        self.assertEqual(
            evidence["runtime"]["pixels"]["changes"],
            [
                {
                    "x": 173,
                    "y": 54,
                    "before_rgb": [255, 165, 49],
                    "after_rgb": [255, 239, 107],
                }
            ],
        )
        self.assertTrue(evidence["scope"]["natural_active_action_route"])

    def test_reexports_group15_current_toolchain_flipped_pixel_chain(self):
        from tools.export_battle_effect_pixel_ab_evidence import export_evidence

        with tempfile.TemporaryDirectory() as tmp:
            evidence = export_evidence(
                ROOT,
                GROUP15_PROFILE,
                GROUP15_ARTIFACT / "raw",
                Path(tmp) / "artifact",
            )

        self.assertEqual(evidence["runtime"]["memory_differences"]["VRAM"], [0x124A3])
        self.assertEqual(evidence["runtime"]["pixels"]["changes"][0]["x"], 65)
        self.assertEqual(
            evidence["runs"]["baseline"]["toolchain"]["kind"],
            "current-desktop-runtime-profile",
        )

    def test_reexports_group2_hardcoded_action_handler_pixel_chain(self):
        from tools.export_battle_effect_pixel_ab_evidence import export_evidence

        with tempfile.TemporaryDirectory() as tmp:
            evidence = export_evidence(
                ROOT,
                GROUP2_PROFILE,
                GROUP2_ARTIFACT / "raw",
                Path(tmp) / "artifact",
            )

        self.assertEqual(evidence["binding"]["active_action_id"], 7)
        self.assertEqual(evidence["binding"]["sequence_id"], 2)
        self.assertEqual(evidence["binding"]["group_id"], 2)
        self.assertEqual(evidence["runtime"]["pixels"]["count"], 1)
        self.assertEqual(evidence["runtime"]["pixels"]["changes"][0]["x"], 64)
        self.assertTrue(evidence["runtime"]["renderer_exact"])
        self.assertTrue(
            evidence["scope"]["natural_active_action_handler_immediate_route"]
        )

    def test_reexports_group4_natural_tool_confirmation_pixel_chain(self):
        from tools.export_battle_effect_pixel_ab_evidence import export_evidence

        with tempfile.TemporaryDirectory() as tmp:
            evidence = export_evidence(
                ROOT,
                GROUP4_PROFILE,
                GROUP4_ARTIFACT / "raw",
                Path(tmp) / "artifact",
            )

        self.assertEqual(
            evidence["binding"],
            {
                "encoded_action_id": 129,
                "group_id": 4,
                "ninja_tool_id": 1,
                "sequence_id": 4,
                "trigger_sequence_id": 13,
            },
        )
        self.assertEqual(evidence["runtime"]["memory_differences"]["VRAM"], [0x12099])
        self.assertEqual(
            evidence["runtime"]["pixels"]["changes"],
            [
                {
                    "x": 83,
                    "y": 72,
                    "before_rgb": [206, 148, 123],
                    "after_rgb": [189, 123, 115],
                }
            ],
        )
        self.assertTrue(evidence["scope"]["production_relocation_route"])

    def test_rejects_resigned_runtime_tool_provenance(self):
        from tools.export_battle_effect_pixel_ab_evidence import export_evidence

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            shutil.copytree(ARTIFACT / "raw", raw)
            for variant in ("baseline", "candidate"):
                for name in ("audit.json", "sentinel.json"):
                    path = raw / variant / name
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload["replay_script_sha256"] = "0" * 64
                    path.write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
            with self.assertRaisesRegex(ValueError, "runtime provenance"):
                export_evidence(ROOT, PROFILE, raw, Path(tmp) / "output")


if __name__ == "__main__":
    unittest.main()
