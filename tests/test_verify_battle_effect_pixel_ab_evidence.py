from __future__ import annotations

import ast
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-effect-group11-pixel-ab-v1"
GROUP1_ARTIFACT = ROOT / "artifacts/battle-effect-group1-pixel-ab-v1"
GROUP14_PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-14-fire-action.json"
GROUP14_ARTIFACT = ROOT / "artifacts/battle-effect-group14-pixel-ab-v1"
GROUP5_ARTIFACT = ROOT / "artifacts/battle-effect-group5-pixel-ab-v1"
GROUP15_PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-15-action64-water-dragon.json"
GROUP15_ARTIFACT = ROOT / "artifacts/battle-effect-group15-pixel-ab-v1"


class VerifyBattleEffectPixelAbEvidenceTests(unittest.TestCase):
    def test_independently_maps_source_pixel_through_horizontal_flip(self):
        from tools import verify_battle_effect_pixel_ab_evidence as verifier

        profile = json.loads(GROUP15_PROFILE.read_text(encoding="utf-8"))
        instances = verifier._runtime_oam_instances(
            profile,
            14,
            8,
            component_width=32,
            component_height=32,
        )

        self.assertEqual(instances[0]["source_pixel_screen_xy"], [65, 56])

    def test_accepts_group15_natural_runtime_checkpoint_contract(self):
        from tools.verify_battle_effect_pixel_ab_evidence import _verify_checkpoint

        profile = json.loads(GROUP15_PROFILE.read_text(encoding="utf-8"))
        _verify_checkpoint(ROOT, profile)

    def test_independently_derives_runtime_tile_from_component_source(self):
        from tools import verify_battle_effect_pixel_ab_evidence as verifier

        profile = {
            "runtime_oam": {
                "obj_vram_address": "0x06012000",
                "obj_tile_base": 264,
            }
        }
        self.assertEqual(verifier._runtime_component_obj_tile_base(profile, 8), 264)
        profile["runtime_oam"]["obj_tile_base"] = 265
        with self.assertRaisesRegex(ValueError, "component tile mapping"):
            verifier._runtime_component_obj_tile_base(profile, 8)

    def test_accepts_historical_generation_and_current_verification_hashes(self):
        from tools import verify_battle_effect_pixel_ab_evidence as verifier

        manifest = {
            "generated_with_implementation_sha256": {
                path: "1" * 64 for path in verifier.IMPLEMENTATION_PATHS
            },
            "verified_with_implementation_sha256": {
                path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                for path in verifier.IMPLEMENTATION_PATHS
            },
        }

        verifier._validate_implementation_provenance(ROOT, manifest)

    def test_rejects_legacy_ambiguous_implementation_hash_field(self):
        from tools import verify_battle_effect_pixel_ab_evidence as verifier

        manifest = {
            "implementation_sha256": {
                path: "1" * 64 for path in verifier.IMPLEMENTATION_PATHS
            }
        }
        with self.assertRaisesRegex(ValueError, "implementation provenance"):
            verifier._validate_implementation_provenance(ROOT, manifest)

    def test_preload_evidence_allows_recorded_stale_baseline_elsewhere(self):
        from tools import verify_battle_effect_pixel_ab_evidence as verifier

        baseline = b"ABCD"
        candidate = b"ABXD"
        vram = bytearray(32)
        vram[16:20] = baseline

        self.assertEqual(
            verifier._preload_evidence(bytes(vram), baseline, candidate, 0),
            {
                "candidate_resource_absent_before_input": True,
                "target_candidate_absent_before_input": True,
                "stale_baseline_locations": ["0x06010010"],
            },
        )

    def test_expected_pixels_support_multiple_rendered_instances(self):
        from tools import verify_battle_effect_pixel_ab_evidence as verifier

        profile = {
            "screen_xy": [44, 73],
            "screen_pixels": [[44, 73], [37, 77]],
            "before_rgb": [148, 140, 90],
            "after_rgb": [222, 214, 148],
        }

        self.assertEqual(len(verifier._expected_pixels(profile)), 2)

    def test_accepts_active_action_confirmation_checkpoint_contract(self):
        from tools.verify_battle_effect_pixel_ab_evidence import _verify_checkpoint

        profile = json.loads(GROUP14_PROFILE.read_text(encoding="utf-8"))
        _verify_checkpoint(ROOT, profile)

    def test_accepts_promoted_action5_artifact_as_trigger_checkpoint_evidence(self):
        from tools.verify_battle_effect_pixel_ab_evidence import _verify_checkpoint

        profile = json.loads(GROUP14_PROFILE.read_text(encoding="utf-8"))
        evidence = GROUP5_ARTIFACT / "runtime-evidence.json"
        profile.update(
            {
                "group_id": 1,
                "sequence_id": 1,
                "trigger_sequence_id": 6,
                "trigger_group_id": 5,
                "selector": {
                    "kind": "active_action",
                    "id": 5,
                    "encoded_action_id": 5,
                },
                "input_state": (
                    "artifacts/runtime-checkpoints/"
                    "scenario-41-attack-confirmation.ss9"
                ),
                "input_state_sha256": (
                    "544cffbaea182a55d1963447965d95750984a915cae9877d66d6bc3aebbd560f"
                ),
                "input_evidence": evidence.relative_to(ROOT).as_posix(),
                "input_evidence_sha256": hashlib.sha256(
                    evidence.read_bytes()
                ).hexdigest(),
                "runtime_input": {
                    "key": "A",
                    "down_frame": 5,
                    "up_frame": 13,
                    "capture_frame": 120,
                },
            }
        )

        _verify_checkpoint(ROOT, profile)

    def test_independent_ledger_uses_production_lowercase_pointer_id(self):
        from tools.verify_battle_effect_pixel_ab_evidence import _ledger

        profile = json.loads(GROUP14_PROFILE.read_text(encoding="utf-8"))
        source = (
            ROOT / profile["source_graphics"]
        ).read_bytes()
        ledger = _ledger(
            profile, profile["source_graphics_sha256"], source
        )

        self.assertEqual(
            ledger[1]["id"], "battle-effect-graphics-000.pointer-59918c"
        )

    def test_promoted_json_contains_no_absolute_paths(self):
        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for item in value.values():
                    yield from strings(item)
            elif isinstance(value, list):
                for item in value:
                    yield from strings(item)

        for artifact in (
            ARTIFACT,
            GROUP1_ARTIFACT,
            GROUP14_ARTIFACT,
            GROUP15_ARTIFACT,
        ):
            for path in artifact.rglob("*.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(
                    [],
                    [value for value in strings(payload) if value.startswith("/")],
                    path,
                )

    def test_verifier_does_not_import_builder_or_exporter(self):
        source = (
            ROOT / "tools/verify_battle_effect_pixel_ab_evidence.py"
        ).read_text(encoding="utf-8")
        imports = {
            node.module
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ImportFrom)
        }
        imports.update(
            alias.name
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        self.assertNotIn("tools.build_battle_effect_pixel_ab", imports)
        self.assertNotIn("tools.export_battle_effect_pixel_ab_evidence", imports)

    def test_verifies_promoted_artifact(self):
        from tools.verify_battle_effect_pixel_ab_evidence import verify_evidence

        result = verify_evidence(ROOT, ARTIFACT)
        self.assertTrue(result["verified"], result["errors"])

    def test_verifies_promoted_multi_instance_action_artifact(self):
        from tools.verify_battle_effect_pixel_ab_evidence import verify_evidence

        result = verify_evidence(ROOT, GROUP1_ARTIFACT)
        self.assertTrue(result["verified"], result["errors"])

    def test_verifies_promoted_active_action_artifact(self):
        from tools.verify_battle_effect_pixel_ab_evidence import verify_evidence

        result = verify_evidence(ROOT, GROUP14_ARTIFACT)
        self.assertTrue(result["verified"], result["errors"])

    def test_verifies_promoted_current_toolchain_flipped_pixel_artifact(self):
        from tools.verify_battle_effect_pixel_ab_evidence import verify_evidence

        result = verify_evidence(ROOT, GROUP15_ARTIFACT)
        self.assertTrue(result["verified"], result["errors"])

    def test_rejects_resigned_semantic_tampering(self):
        from tools.verify_battle_effect_pixel_ab_evidence import verify_evidence

        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            evidence_path = copied / "runtime-evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["runtime"]["pixels"]["changes"][0]["after_rgb"] = [0, 0, 0]
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["payload_sha256"] = digest
            manifest["files"]["runtime-evidence.json"] = digest
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertFalse(verify_evidence(ROOT, copied)["verified"])

    def test_rejects_resigned_runtime_tool_provenance(self):
        from tools.verify_battle_effect_pixel_ab_evidence import verify_evidence

        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            evidence_path = copied / "runtime-evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            for variant in ("baseline", "candidate"):
                for name in ("audit.json", "sentinel.json"):
                    path = copied / "raw" / variant / name
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload["replay_script_sha256"] = "0" * 64
                    path.write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                evidence["runs"][variant]["replay_script_sha256"] = "0" * 64
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["payload_sha256"] = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            manifest["files"] = {
                path.relative_to(copied).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in sorted(copied.rglob("*"))
                if path.is_file() and path.name != "manifest.json"
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertFalse(verify_evidence(ROOT, copied)["verified"])


if __name__ == "__main__":
    unittest.main()
