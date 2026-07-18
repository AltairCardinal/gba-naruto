import hashlib
import json
import struct
import unittest
from pathlib import Path

from tools.inspect_mgba_savestate import load_gba_state, png_screen_fingerprint


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "artifacts/runtime-checkpoints/scenario-43-postbattle-next-task-prompt.ss9"
EVIDENCE = ROOT / "artifacts/runtime-checkpoints/scenario-43-progression-evidence.json"
NOTE = ROOT / "notes/scenario-43-progression-runtime-20260718.md"
CHECKPOINT_SHA256 = "55375b7736481505dc68cdfe774e1182d90ea77d31264d7be10c80279a978ce9"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Scenario43ProgressionPersistenceTests(unittest.TestCase):
    def test_checkpoint_preserves_level_three_and_next_task_prompt(self):
        self.assertEqual(sha256_file(CHECKPOINT), CHECKPOINT_SHA256)
        state = load_gba_state(CHECKPOINT)
        template = state.read_memory(0x02022EF0, 0xC0)
        task2 = state.read_memory(0x03000AD4, 0x4C)
        self.assertEqual(struct.unpack_from("<I", task2, 8)[0] - 1, 0x08092FCE)
        self.assertEqual(template[1], 3)
        self.assertEqual(struct.unpack_from("<H", template, 0x10)[0], 0)
        self.assertEqual(template[0xBA], 2)
        self.assertEqual(bytes(template[0x51 + index * 4] for index in range(24)), b"\xFF" * 24)
        self.assertEqual(
            png_screen_fingerprint(CHECKPOINT)["rgb_pixels_sha256"],
            "d57e39a268fe602010467cb904bfb2076331003dcc75e97ae9d774febb5d66df",
        )

    def test_evidence_and_note_preserve_natural_combat_findings(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(evidence["outcome"], "scenario-43-natural-victory-level-three-verified")
        self.assertEqual(evidence["checkpoint"]["sha256"], CHECKPOINT_SHA256)
        self.assertTrue(evidence["checkpoint"]["zero_input_verified"])
        self.assertEqual(evidence["natural_reward"]["level_before"], 2)
        self.assertEqual(evidence["natural_reward"]["level_after"], 3)
        self.assertEqual(evidence["natural_reward"]["training_points_after"], 2)
        self.assertEqual(evidence["combat_findings"]["rest_hp_gain"], 18)
        self.assertEqual(evidence["combat_findings"]["defeated_enemy_stored_hp"], [2, 5, 8])
        note = NOTE.read_text(encoding="utf-8")
        for phrase in (CHECKPOINT_SHA256, "LV2→LV3", "休息", "18 HP", "影分身", "107.64453125 MiB"):
            self.assertIn(phrase, note)


if __name__ == "__main__":
    unittest.main()
