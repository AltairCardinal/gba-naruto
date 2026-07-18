import hashlib
import json
import struct
import unittest
from pathlib import Path

from tools.inspect_mgba_savestate import load_gba_state, png_screen_fingerprint


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "artifacts/runtime-checkpoints/scenario-42-postbattle-world-map.ss9"
EVIDENCE = ROOT / "artifacts/runtime-checkpoints/scenario-42-progression-evidence.json"
NOTE = ROOT / "notes/scenario-42-progression-runtime-20260718.md"
CHECKPOINT_SHA256 = "35fce6be208aa50044bdaa2232eab5986d9ea76340bc08c68b107f34b5a5b5a1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Scenario42ProgressionPersistenceTests(unittest.TestCase):
    def test_checkpoint_preserves_natural_exp_gain_without_levels_unlock(self):
        self.assertEqual(sha256_file(CHECKPOINT), CHECKPOINT_SHA256)
        state = load_gba_state(CHECKPOINT)
        template = state.read_memory(0x02022EF0, 0xC0)
        task2 = state.read_memory(0x03000AD4, 0x4C)
        self.assertEqual(struct.unpack_from("<I", task2, 8)[0] - 1, 0x08067D02)
        self.assertEqual(template[1], 2)
        self.assertEqual(struct.unpack_from("<H", template, 0x10)[0], 110)
        self.assertEqual(template[0xBA], 1)
        self.assertEqual(bytes(template[0x51 + index * 4] for index in range(24)), b"\xFF" * 24)
        self.assertEqual(state.read_memory(0x0200A880, 4), b"\x00" * 4)
        self.assertEqual(
            png_screen_fingerprint(CHECKPOINT)["rgb_pixels_sha256"],
            "ed68845076f0dc2eb40397bb870e4c9b7cd1f6567323dabdff8e3e9b364e15d6",
        )

    def test_evidence_and_note_keep_levels_boundary_conservative(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(evidence["outcome"], "scenario-42-natural-victory-exp-verified")
        self.assertEqual(evidence["checkpoint"]["sha256"], CHECKPOINT_SHA256)
        self.assertEqual(evidence["natural_reward"]["exp_before"], 0)
        self.assertEqual(evidence["natural_reward"]["exp_after"], 110)
        self.assertEqual(evidence["natural_reward"]["level_after"], 2)
        self.assertEqual(evidence["levels_boundary"]["verification"], "code_verified")
        self.assertEqual(evidence["levels_boundary"]["secondary_active_count"], 0)
        self.assertIn("does not prove", evidence["levels_boundary"]["boundary"])
        note = NOTE.read_text(encoding="utf-8")
        for phrase in (CHECKPOINT_SHA256, "0→110", "type 4", "code_verified", "107.5625 MiB"):
            self.assertIn(phrase, note)


if __name__ == "__main__":
    unittest.main()
