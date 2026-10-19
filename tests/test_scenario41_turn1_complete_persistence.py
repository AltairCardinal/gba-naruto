import hashlib
import json
import struct
import subprocess
import unittest
from pathlib import Path

from tools.inspect_mgba_savestate import load_gba_state, png_screen_fingerprint


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "artifacts/runtime-checkpoints/scenario-41-turn-1-complete.ss9"
EVIDENCE = ROOT / "artifacts/runtime-checkpoints/scenario-41-turn-1-complete-evidence.json"
LEDGER = ROOT / "artifacts/runtime-checkpoints/scenario-41-checkpoints.json"
NOTE = ROOT / "notes/scenario-41-movedone-runtime-20260717.md"
EXPECTED_CHECKPOINT_SHA256 = "a9e255d86f983c0b6d062aee2467674d89685d8ca88896e2f2fefe6b3a7e5ae5"
EXPECTED_RGB_SHA256 = "fa0bb87531d63182e939cfda56b3f2d9dccc21a9308572bccf18b6cc77d5d186"
EXPECTED_UNITS_SHA256 = "a38f0186b6066f06934f039de5fe5008d94e2176f3db0f2977118519cc62ff4b"
EXPECTED_MOD1 = "4d4f44310200000003000000010000003c4407080100010268440202684402021e01060601010000040402040402000001023200"
EXPECTED_MOD2 = "4d4f4432020000000400000002000000184907080100010268440202684402021e01060611010000060401060401000001023200"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Scenario41Turn1CompletePersistenceTests(unittest.TestCase):
    def test_checkpoint_is_the_stable_post_enemy_dialogue_boundary(self):
        self.assertTrue(CHECKPOINT.is_file(), "turn-1-complete checkpoint is missing")
        self.assertEqual(sha256_file(CHECKPOINT), EXPECTED_CHECKPOINT_SHA256)
        state = load_gba_state(CHECKPOINT)
        task2 = state.read_memory(0x03000AD4, 0x4C)
        self.assertEqual(struct.unpack_from("<I", task2, 8)[0] - 1, 0x08095F12)
        self.assertEqual(state.read_memory(0x0200A880, 8).hex(), "0100010001000000")
        self.assertEqual(state.read_memory(0x02026804, 8).hex(), "0029000000000000")
        self.assertEqual(state.read_memory(0x0201BE28, 4).hex(), "242c0916")
        self.assertEqual(state.read_memory(0x0202680C, 8).hex(), "0200000000000000")
        units = state.read_memory(0x020241C0, 0x1D4 * 12)
        self.assertEqual(hashlib.sha256(units).hexdigest(), EXPECTED_UNITS_SHA256)
        self.assertEqual(state.read_memory(0x0203F0E0, 4).hex(), "04000000")
        self.assertEqual(state.read_memory(0x0203F100, 52).hex(), EXPECTED_MOD1)
        self.assertEqual(state.read_memory(0x0203F140, 52).hex(), EXPECTED_MOD2)
        self.assertEqual(png_screen_fingerprint(CHECKPOINT)["rgb_pixels_sha256"], EXPECTED_RGB_SHA256)

    def test_evidence_binds_contiguous_runs_secondary_movedone_and_base_control(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(evidence["outcome"], "accepted-turn-1-complete")
        self.assertEqual(evidence["scope"], "scenario-41-turn-1-complete")
        self.assertEqual(
            evidence["checkpoint"],
            {
                "path": "artifacts/runtime-checkpoints/scenario-41-turn-1-complete.ss9",
                "sha256": EXPECTED_CHECKPOINT_SHA256,
            },
        )
        chain = evidence["state_chain"]
        self.assertEqual(
            [(item["run_id"], item["input_state_sha256"], item["output_state_sha256"]) for item in chain],
            [
                ("6930e2c4d30fa6d54ef1d8a350f9a11a", "54cf5ecacd9cd89dd679b2b8926e6b6de2f27080da28331aae06c17abe414101", "a25d31da280741cdcb6235abdd10c0e2e05fc95ef46a2d20bd1cc8bb9daeea15"),
                ("e512f1e3ccec6a5abf52365670155c24", "a25d31da280741cdcb6235abdd10c0e2e05fc95ef46a2d20bd1cc8bb9daeea15", "7e12bfbe67b6e9a229594bd1ae41c90a08d3ecdd63df3e003758c1861520ba3c"),
                ("e3ee3f20a2307813a29bbb4c23749a6a", "7e12bfbe67b6e9a229594bd1ae41c90a08d3ecdd63df3e003758c1861520ba3c", "9b98d6567e5c8e86496639eaa61cbdd09064a916ed917ac67e7339eb21c983f4"),
                ("c7e552dd06348f1da2642465587f9d13", "9b98d6567e5c8e86496639eaa61cbdd09064a916ed917ac67e7339eb21c983f4", EXPECTED_CHECKPOINT_SHA256),
            ],
        )
        self.assertEqual(chain[0]["timing"], {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8, "capture_frame": 128})
        for item in chain[1:]:
            self.assertEqual(item["inputs"], [])
            self.assertEqual(item["pre_scripts"], [])
            self.assertTrue(item["zero_input_verified"])
        self.assertTrue(evidence["stability"]["business_state_exact"])
        self.assertTrue(evidence["stability"]["capture_png_exact"])
        self.assertEqual(evidence["stability"]["task_resume"], "0x08095F12")
        control = evidence["base_control"]
        self.assertEqual(control["run_id"], "2eb0007720eaff85feb68f49f9b76ff8")
        self.assertTrue(control["business_state_exact"])
        self.assertTrue(control["capture_png_exact"])
        self.assertEqual(control["ewram_delta"], "observer-scratch-only")

        evaluator = evidence["evaluator"]
        script = """
const { evaluateMovedoneEvidence } = require('./play/_scripts/scenario-41-runtime-evidence');
const input = JSON.parse(process.argv[1]);
input.expectedInputPlan.forEach(Object.freeze);
Object.freeze(input.expectedInputPlan);
process.stdout.write(JSON.stringify(evaluateMovedoneEvidence(input)));
"""
        rerun = subprocess.run(
            ["node", "-e", script, json.dumps(evaluator["input"])],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(rerun.stdout), evaluator["result"])
        self.assertTrue(evaluator["result"]["verified"])
        self.assertEqual(evaluator["result"]["reason"], "movedone-verified")
        self.assertFalse(evaluator["result"]["checks"]["coordinatesChanged"])
        self.assertTrue(evaluator["result"]["checks"]["movementOrStationaryCompletion"])

    def test_ledger_and_note_preserve_the_strict_boundary(self):
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        records = [r for r in ledger["checkpoints"] if r["name"] == "scenario-41-turn-1-complete"]
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["status"], "accepted")
        self.assertEqual(record["parent"], "scenario-41-first-movedone-facing")
        self.assertEqual(record["inputs"], ["A"])
        self.assertEqual(record["allowed_evidence"], ["movedone"])
        self.assertTrue(record["stable_zero_input"])
        for phrase in ("secondary MOVEDONE", "first turn", "enemy settle", "does not prove second turn", "victory", "postbattle"):
            self.assertIn(phrase, record["runtime_boundary"])

        note = NOTE.read_text(encoding="utf-8")
        for phrase in (
            EXPECTED_CHECKPOINT_SHA256,
            "6930e2c4d30fa6d54ef1d8a350f9a11a",
            "2eb0007720eaff85feb68f49f9b76ff8",
            "0x08074918",
            "0x08095F12",
            "movementOrStationaryCompletion",
            "第一回合完成",
            "不证明第二回合、胜利或 postbattle",
        ):
            self.assertIn(phrase, note)


if __name__ == "__main__":
    unittest.main()
