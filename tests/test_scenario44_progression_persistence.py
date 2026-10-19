import hashlib
import json
import struct
import unittest
from pathlib import Path

from tools.inspect_mgba_savestate import load_gba_state, png_screen_fingerprint


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "artifacts/runtime-checkpoints/scenario-44-postbattle-world-map.ss9"
EVIDENCE = ROOT / "artifacts/runtime-checkpoints/scenario-44-progression-evidence.json"
NOTE = ROOT / "notes/scenario-44-progression-runtime-20260718.md"
CHECKPOINT_SHA256 = "b452a77ef623d36423ec19eb4b5635d58d186ec041fa7891b356889d367875cd"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Scenario44ProgressionPersistenceTests(unittest.TestCase):
    def test_checkpoint_preserves_natural_victory_and_three_character_rewards(self):
        self.assertEqual(sha256_file(CHECKPOINT), CHECKPOINT_SHA256)
        state = load_gba_state(CHECKPOINT)
        task2 = state.read_memory(0x03000AD4, 0x4C)
        self.assertEqual(struct.unpack_from("<I", task2, 8)[0] - 1, 0x08067D02)
        self.assertEqual(state.read_memory(0x02026804, 4).hex(), "002c0001")

        expected = {
            1: (3, 125, 2),
            2: (2, 45, 1),
            3: (1, 125, 0),
        }
        for character_id, (level, exp, training_points) in expected.items():
            template = state.read_memory(0x02022E34 + character_id * 0xBC, 0xBC)
            self.assertEqual(template[0], character_id)
            self.assertEqual(template[1], level)
            self.assertEqual(struct.unpack_from("<H", template, 0x10)[0], exp)
            self.assertEqual(template[0xBA], training_points)

        self.assertEqual(
            png_screen_fingerprint(CHECKPOINT)["rgb_pixels_sha256"],
            "80f987fd20333739f3710ba0b0f59ce83f2ae9ab66fdfa3c34314c49cea6cb69",
        )

    def test_evidence_records_two_stage_objective_and_stable_replay(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(evidence["outcome"], "scenario-44-natural-victory-two-stage-objective-verified")
        self.assertEqual(evidence["checkpoint"]["sha256"], CHECKPOINT_SHA256)
        self.assertTrue(evidence["checkpoint"]["zero_input_verified"])
        self.assertEqual(evidence["objective"]["battle_scenario"], 0x2C)
        self.assertEqual(evidence["objective"]["enemy_defeat_stored_hp"], 6)
        self.assertEqual(evidence["objective"]["accepted_tile"], [4, 3])
        self.assertEqual(evidence["objective"]["non_winning_tiles"], [[3, 9], [3, 4], [4, 4]])
        self.assertEqual(evidence["natural_reward"]["per_character_exp"], 125)
        self.assertEqual(evidence["natural_reward"]["sasuke_level"], 2)
        note = NOTE.read_text(encoding="utf-8")
        for phrase in (CHECKPOINT_SHA256, "两阶段", "(4,3)", "125 EXP", "107.890625 MiB"):
            self.assertIn(phrase, note)


if __name__ == "__main__":
    unittest.main()
