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


class ExportBattleEffectPixelAbEvidenceTests(unittest.TestCase):
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
