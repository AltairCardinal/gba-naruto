from __future__ import annotations

import importlib
import inspect
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-effect-frame-phase-v1"


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
        with self.assertRaisesRegex(ValueError, "exactly once"):
            verifier.target_dispatch_ordinal([125, 127], 124)
        with self.assertRaisesRegex(ValueError, "aligned"):
            verifier.decode_active_task_slots(
                b"\x01", bytes.fromhex("c9580003") + bytes(0x200 - 4)
            )

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


if __name__ == "__main__":
    unittest.main()
