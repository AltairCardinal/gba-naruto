import hashlib
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "artifacts/runtime-checkpoints/scenario-41-first-movedone-facing.ss9"
EVIDENCE = ROOT / "artifacts/runtime-checkpoints/scenario-41-first-movedone-facing-evidence.json"
LEDGER = ROOT / "artifacts/runtime-checkpoints/scenario-41-checkpoints.json"
NOTE = ROOT / "notes/scenario-41-movedone-runtime-20260717.md"
EXPECTED_CHECKPOINT_SHA256 = (
    "1bc95c63cb11d469e4b2e80e8bae5a937f04ad40e18d7a15706fc261cb9ffb94"
)
EXPECTED_RGB_SHA256 = (
    "54f5409df260ee24f35a4940069f32d4bb77b56e42acce566343b8814a73564f"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Scenario41FirstMovedoneFacingPersistenceTests(unittest.TestCase):
    def test_checkpoint_is_the_reviewed_p1_state(self):
        self.assertTrue(CHECKPOINT.is_file(), "canonical facing checkpoint is missing")
        self.assertEqual(sha256_file(CHECKPOINT), EXPECTED_CHECKPOINT_SHA256)

    def test_evidence_binds_fresh_primary_publication_and_fails_closed(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

        self.assertEqual(evidence["outcome"], "accepted-stable-facing-boundary")
        self.assertEqual(evidence["scope"], "scenario-41-first-movedone-facing")
        self.assertEqual(
            evidence["checkpoint"],
            {
                "path": "artifacts/runtime-checkpoints/scenario-41-first-movedone-facing.ss9",
                "sha256": EXPECTED_CHECKPOINT_SHA256,
            },
        )
        self.assertEqual(
            evidence["provenance"],
            {
                "base_rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "observer_rom_sha256": "2e0ef35475737789103403cfea454ace1de0ae6b6ed1789d49d7e55d5dc1737f",
                "observer_builder_sha256": "2998ad242e40fb5e7ad1b5a4b7192618aa77920148ae78b769a50c11dd543549",
                "binary_sha256": "20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408",
                "build_manifest_sha256": "9da6779d7c1ac3140e512b233f98abe754c4f11f3fbc8157af147e014661cc4d",
                "fixed_input_runner_sha256": "2f36d0bd8d3daddcbc4f6057b47fc75c9d62f5f2e71cda0992beae3439dc7ef9",
                "fixed_input_lua_sha256": "82fbae13b39d2e7dd4b53e4b79dcf89ccc56f29dcb9ea53466d007b1000b9412",
                "zero_input_runner_sha256": "44a117c53d272cbac8a62beb749d331927e4f3f043c20f3eb78681ceb7591bbc",
                "zero_input_lua_sha256": "1481f10cd8f72c7635326e8d3233c2466b76c7a4b812cefe1220fe43c29f9659",
                "guard_sha256": "ea34554547c374cd7f9d868792d73c2d7932884f59938a4ffff039eacaa28666",
            },
        )

        action = evidence["corrected_action"]
        self.assertEqual(action["run_id"], "d10c70cfe08e17f1b86f3f8c99ce9485")
        self.assertEqual(action["baseline"], {"counter": 0, "MOD1": "zero", "MOD2": "zero"})
        self.assertEqual(action["final"]["counter"], 1)
        self.assertEqual(action["final"]["MOD2"], "zero")
        self.assertEqual(
            action["final"]["MOD1"],
            {
                "raw_hex": "4d4f44310100000001000000010000003c44070801000001944202029442020201010e0d00010000040a00040a00000000ff0000",
                "hit_count": 1,
                "sequence": 1,
                "event_code": 1,
                "source_hook": "0x0807443C",
                "slot": 1,
                "record_address": "0x02024294",
                "character_id": 1,
                "affiliation": 0,
                "coordinates": [4, 10],
                "raw_c0": "0x00000100",
            },
        )
        self.assertEqual(action["unit_after"]["raw_c0"], "0x00000110")
        self.assertEqual(action["unit_after"]["coordinates"], [4, 10])
        self.assertEqual(action["task_resume"], "0x080745A4")

        result = evidence["evaluator"]["result"]
        self.assertFalse(result["verified"])
        self.assertFalse(result["diagnosticVerified"])
        self.assertEqual(result["reason"], "coordinates-unchanged")
        self.assertFalse(result["checks"]["coordinatesChanged"])

        script = """
const { evaluateMovedoneEvidence } = require('./play/_scripts/scenario-41-runtime-evidence');
const input = JSON.parse(process.argv[1]);
input.expectedInputPlan.forEach(Object.freeze);
Object.freeze(input.expectedInputPlan);
process.stdout.write(JSON.stringify(evaluateMovedoneEvidence(input)));
"""
        rerun = subprocess.run(
            ["node", "-e", script, json.dumps(evidence["evaluator"]["input"])],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(rerun.stdout), result)

    def test_evidence_binds_lineage_base_control_cycle_and_serial_replays(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

        self.assertEqual(
            evidence["lineage"],
            {
                "parent": "scenario-41-player-turn",
                "explicit_inputs": ["A", "Up", "A", "A"],
                "screen": "facing-direction-prompt",
            },
        )
        control = evidence["base_control"]
        self.assertEqual(control["run_id"], "e918e8f9f5f02b1f2e4db2291800a1ea")
        self.assertTrue(control["business_state_exact"])
        self.assertTrue(control["capture_png_exact"])
        self.assertEqual(control["normalized_rgb8_sha256"], EXPECTED_RGB_SHA256)
        self.assertEqual(control["ewram_delta"], "observer-scratch-only")
        self.assertEqual(
            control["business_state"],
            {
                "task_resume": "0x080745A4",
                "menu_row": 0,
                "menu_result": 1,
                "round": 1,
                "battle_id": 41,
                "map": [36, 44, 9, 22],
                "slot": 1,
                "record_address": "0x02024294",
                "character_id": 1,
                "affiliation": 0,
                "coordinates": [4, 10],
                "raw_c0": "0x00000110",
            },
        )

        self.assertEqual(evidence["cycle"]["period_frames"], 288)
        self.assertEqual(evidence["cycle"]["match_frames"], [0, 288, 576])
        stability = evidence["zero_input_stability"]
        self.assertEqual(stability["period_frames"], 288)
        self.assertEqual(stability["normalized_rgb8_sha256"], EXPECTED_RGB_SHA256)
        self.assertEqual(
            [replay["run_id"] for replay in stability["replays"]],
            ["04c16bc769e2d42b4ba4e3ea134dae58", "fd95cc6b7c33651a8b8453b3871c22b9"],
        )
        self.assertEqual(
            [replay["output_state_sha256"] for replay in stability["replays"]],
            [EXPECTED_CHECKPOINT_SHA256, "daf7de2aed6ec2122f07a33aad2fa6c3fae75fdc8e200355bef68589eba48a15"],
        )
        self.assertEqual(
            [replay["artifact_hashes"] for replay in stability["replays"]],
            [
                {
                    "audit_sha256": "071ec2c7f877eb5e9502811e2fedf57c853c01e5e58d95ec520160b680366130",
                    "guard_sha256": "045d3cd773efbe6c3c8238517ebf26ce5c7cd96000fb1da62072ebf7b1c28d79",
                    "done_sha256": "373747ee580ad863376ec65377422404ffd6dac3733bde467cde096d821b6a6f",
                },
                {
                    "audit_sha256": "b5dd1cb6e68c022ab5f3a3054dcd379d983a489776b076436564e35216223e1c",
                    "guard_sha256": "652b14ef82613e862e33ed63948b73d1530ce242ace326f52f72ed837eba44c5",
                    "done_sha256": "019f9e4ba27a5d00edea64d315b4454add34208cbd51e7ba1f43e0ecd54da9a5",
                },
            ],
        )
        for replay in stability["replays"]:
            self.assertEqual(replay["capture_frame"], 288)
            self.assertEqual(replay["inputs"], [])
            self.assertEqual(replay["pre_scripts"], [])
            self.assertTrue(replay["zero_input_verified"])
            self.assertEqual(replay["guard"]["reason"], "completed")
            self.assertEqual(replay["guard"]["exit_code"], 0)
            self.assertEqual(replay["guard"]["completion_trigger"], "success-marker")
            self.assertFalse(replay["guard"]["degraded"])

    def test_ledger_accepts_only_the_stable_facing_boundary(self):
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        records = [
            record
            for record in ledger["checkpoints"]
            if record["name"] == "scenario-41-first-movedone-facing"
        ]

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["status"], "accepted")
        self.assertEqual(record["sha256"], EXPECTED_CHECKPOINT_SHA256)
        self.assertEqual(record["parent"], "scenario-41-player-turn")
        self.assertEqual(record["inputs"], ["A", "Up", "A", "A"])
        self.assertEqual(record["screen"], "facing-direction-prompt")
        self.assertTrue(record["stable_zero_input"])
        self.assertEqual(record["before_hooks"], ["0x0807443C", "0x08074918"])
        self.assertEqual(record["allowed_evidence"], [])
        self.assertEqual(
            record["zero_input_evidence"],
            ["artifacts/runtime-checkpoints/scenario-41-first-movedone-facing-evidence.json"],
        )
        for phrase in (
            "stable facing-direction prompt",
            "fresh primary publication",
            "coordinates-unchanged",
            "does not prove completed turn",
            "accepted MOVEDONE evidence",
            "victory",
            "postbattle",
        ):
            self.assertIn(phrase, record["runtime_boundary"])

    def test_note_records_method_result_and_strict_boundary(self):
        note = NOTE.read_text(encoding="utf-8")
        for phrase in (
            EXPECTED_CHECKPOINT_SHA256,
            "d10c70cfe08e17f1b86f3f8c99ce9485",
            "e918e8f9f5f02b1f2e4db2291800a1ea",
            "0x0807443C",
            "0x08074918",
            "0x02024294",
            "0x080745A4",
            "coordinates-unchanged",
            "verified=false",
            "不证明回合完成",
            "不接受 MOVEDONE",
            "不证明胜利或 postbattle",
        ):
            self.assertIn(phrase, note)


if __name__ == "__main__":
    unittest.main()
