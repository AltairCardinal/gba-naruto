import hashlib
import json
import struct
import subprocess
import unittest
from pathlib import Path

from tools.inspect_mgba_savestate import load_gba_state, png_screen_fingerprint


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINTS = ROOT / "artifacts/runtime-checkpoints"
LEDGER = CHECKPOINTS / "scenario-41-checkpoints.json"
EVIDENCE = CHECKPOINTS / "scenario-41-completion-evidence.json"
NOTE = ROOT / "notes/scenario-41-completion-runtime-20260718.md"

VICTORY_SHA256 = "7a24a7a628c301493418d93e88ab239c0fbb6b77de139a67b91e8e0bcadf6200"
POSTBATTLE_SHA256 = "950652381ae03ad60ad028f9063b9fc22f133ea532396fbafe7f5353d2553162"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Scenario41CompletionPersistenceTests(unittest.TestCase):
    def test_victory_checkpoint_preserves_natural_result(self):
        path = CHECKPOINTS / "scenario-41-victory.ss9"
        self.assertEqual(sha256_file(path), VICTORY_SHA256)
        state = load_gba_state(path)
        task2 = state.read_memory(0x03000AD4, 0x4C)
        self.assertEqual(struct.unpack_from("<I", task2, 8)[0] - 1, 0x08073114)
        self.assertEqual(state.read_memory(0x02026807, 1), b"\x01")
        self.assertEqual(state.read_memory(0x0200A880, 4).hex(), "00000100")
        self.assertEqual(
            png_screen_fingerprint(path)["rgb_pixels_sha256"],
            "6fc3d928abd921413dc8603c094387afa9c0c0b297fe8d9a5d79d7211396ffa2",
        )

    def test_postbattle_checkpoint_is_stable_world_map(self):
        path = CHECKPOINTS / "scenario-41-postbattle.ss9"
        self.assertEqual(sha256_file(path), POSTBATTLE_SHA256)
        state = load_gba_state(path)
        task2 = state.read_memory(0x03000AD4, 0x4C)
        self.assertEqual(struct.unpack_from("<I", task2, 8)[0] - 1, 0x08067D02)
        self.assertEqual(state.read_memory(0x02026807, 1), b"\x01")
        self.assertEqual(state.read_memory(0x0200A880, 4), b"\x00" * 4)
        self.assertEqual(
            png_screen_fingerprint(path)["rgb_pixels_sha256"],
            "298acd7711c13879ecb91cf3eb88563060b79584944289716a1811baa588e0ef",
        )

    def test_evidence_binds_base_control_stability_and_negative_save_boundary(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(evidence["outcome"], "accepted-victory-and-postbattle-world-map")
        self.assertEqual(evidence["checkpoints"]["victory"]["sha256"], VICTORY_SHA256)
        self.assertEqual(evidence["checkpoints"]["postbattle"]["sha256"], POSTBATTLE_SHA256)
        control = evidence["decisive_base_control"]
        self.assertEqual(control["run_id"], "dae8d9689279c84745f3312dcfc0dfd0")
        self.assertTrue(control["observer_visible_exact"])
        self.assertTrue(control["observer_wram_exact"])
        self.assertEqual(control["result_byte"], 1)
        self.assertEqual(evidence["stability"]["victory"]["run_id"], "c68415084dbc0168585cd3a841164773")
        self.assertEqual(evidence["stability"]["postbattle"]["run_id"], "5ad3c6ab83031b1e76525ab33517fc16")
        save = evidence["natural_save_boundary"]
        self.assertEqual(save["status"], "not-proven")
        self.assertEqual(save["hook"], "0x08074F2C")
        self.assertTrue(all(sample["scratch"] == "0000000000000000" for sample in save["samples"]))
        self.assertIn("does not prove", save["boundary"])

    def test_ledger_note_and_validator_keep_conservative_boundaries(self):
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        records = {item["name"]: item for item in ledger["checkpoints"]}
        victory = records["scenario-41-victory"]
        postbattle = records["scenario-41-postbattle"]
        self.assertEqual(victory["parent"], "scenario-41-turn-1-complete")
        self.assertEqual(postbattle["parent"], "scenario-41-victory")
        self.assertEqual(victory["allowed_evidence"], [])
        self.assertEqual(postbattle["allowed_evidence"], [])
        self.assertIn("natural result byte", victory["runtime_boundary"])
        self.assertIn("does not prove 0x08074F2C", postbattle["runtime_boundary"])
        result = subprocess.run(
            ["python3", "tools/runtime_checkpoint_ledger.py", str(LEDGER)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        note = NOTE.read_text(encoding="utf-8")
        for phrase in (
            VICTORY_SHA256,
            POSTBATTLE_SHA256,
            "0x02026807=1",
            "0x08074F2C",
            "未证明",
            "52.4453125 MiB",
        ):
            self.assertIn(phrase, note)


if __name__ == "__main__":
    unittest.main()
