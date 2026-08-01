from __future__ import annotations

import importlib
import hashlib
import inspect
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-effect-frame-phase-v1"
OBSERVED_GROUP_ARTIFACTS = {
    1: (ROOT / "artifacts/battle-effect-frame-phase-group1-v1", 12),
    2: (ROOT / "artifacts/battle-effect-frame-phase-group2-v1", 0),
    5: (ROOT / "artifacts/battle-effect-frame-phase-group5-v1", 2),
    14: (ROOT / "artifacts/battle-effect-frame-phase-group14-v1", 2),
}


class BattleEffectFramePhaseVerifierTests(unittest.TestCase):
    def test_independent_verifier_accepts_production_artifact(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        source = inspect.getsource(verifier)
        self.assertNotIn("export_battle_effect_frame_phase", source)
        result = verifier.verify_artifact(ARTIFACT)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["group_id"], 11)
        self.assertEqual(result["pending_sequence"], [0, 1, 0])
        self.assertTrue(result["ack_shadow_matches_hardware"])
        self.assertTrue(result["renderer_shadow_differs_from_hardware"])
        self.assertEqual(result["non_state_equivalent_dumps"], ["io.bin"])
        self.assertEqual(
            result["breakpoint_addresses"],
            ["0x08063328", "0x08061126", "0x080612AA"],
        )
        self.assertEqual(result["target_dispatch_ordinals"], [0, 0, 0])

    def test_thumb_breakpoint_pc_and_dispatch_membership_are_independent(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        self.assertEqual(
            verifier.thumb_breakpoint_address(0x0806332A, 0x6000003F),
            0x08063328,
        )
        slots = verifier.decode_active_task_slots(
            b"\x03",
            bytes.fromhex("c8580003045900037c590003") + bytes(0x200 - 12),
        )
        self.assertEqual(slots, [124, 125, 127])
        self.assertEqual(verifier.target_dispatch_ordinal(slots, 124), 0)
        self.assertEqual(verifier.target_dispatch_ordinal(slots, 127), 2)
        with self.assertRaisesRegex(ValueError, "exactly once"):
            verifier.target_dispatch_ordinal([125, 127], 124)
        with self.assertRaisesRegex(ValueError, "aligned"):
            verifier.decode_active_task_slots(
                b"\x01", bytes.fromhex("c9580003") + bytes(0x200 - 4)
            )

    def test_group_identity_is_derived_from_animation_catalog(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        catalog = json.loads(
            (
                ROOT
                / "artifacts/battle-effect-sprite-animations-v1/manifest.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            verifier.effect_group_identity(catalog, 14),
            (0x083468D0, 0x08346914),
        )
        with self.assertRaisesRegex(ValueError, "exactly once"):
            verifier.effect_group_identity(catalog, 99)

    def test_rejects_toolchain_profile_hash_tampering(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["toolchain"]["sha256"] = "0" * 64
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = verifier.verify_artifact(artifact)
            self.assertIn("toolchain profile hash mismatch", result["errors"])

    def test_rejects_runtime_audit_profile_hash_tampering(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            audit_path = artifact / "runtime-audit.json"
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            audit["profile_sha256"] = "0" * 64
            audit_path.write_text(
                json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["runtime-audit.json"] = hashlib.sha256(
                audit_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = verifier.verify_artifact(artifact)
            self.assertIn("runtime audit profile hash mismatch", result["errors"])

    def test_accepts_every_new_observed_group_phase_artifact(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        for group_id, (artifact, ordinal) in OBSERVED_GROUP_ARTIFACTS.items():
            with self.subTest(group_id=group_id):
                result = verifier.verify_artifact(artifact)
                self.assertEqual(result["errors"], [])
                self.assertEqual(result["group_id"], group_id)
                self.assertEqual(
                    result["target_dispatch_ordinals"], [ordinal, ordinal, ordinal]
                )
                self.assertEqual(result["pending_sequence"], [0, 1, 0])
                self.assertTrue(result["ack_shadow_matches_hardware"])

    def test_rejects_unaccepted_source_runtime_evidence_provenance(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_runtime_provenance"]["contract"]["accepted_parent"][
                "manifest_sha256"
            ] = "0" * 64
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = verifier.verify_artifact(artifact)
            self.assertIn(
                "source runtime artifact manifest hash mismatch",
                result["errors"],
            )

    def test_rejects_artifact_level_pc_and_dispatcher_tampering(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        cases = (
            (
                "pc",
                "raw/renderer-post/capture-phase.json",
                lambda phase: phase.__setitem__("address", "0x0806332A"),
                "renderer-post address mismatch",
            ),
            (
                "dispatcher",
                "raw/renderer-post/capture-phase.json",
                lambda phase: phase.__setitem__("task_slot", 0),
                "renderer-post dispatcher membership mismatch",
            ),
        )
        for name, relative, mutate, expected_error in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                artifact = Path(tmp) / "artifact"
                shutil.copytree(ARTIFACT, artifact)
                phase_path = artifact / relative
                phase = json.loads(phase_path.read_text(encoding="utf-8"))
                mutate(phase)
                phase_path.write_text(
                    json.dumps(phase, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
                manifest_path = artifact / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["files"][relative] = hashlib.sha256(
                    phase_path.read_bytes()
                ).hexdigest()
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
                result = verifier.verify_artifact(artifact)
                self.assertTrue(
                    any(expected_error in error for error in result["errors"]),
                    result["errors"],
                )


if __name__ == "__main__":
    unittest.main()
