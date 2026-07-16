import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "artifacts/runtime-checkpoints/scenario-41-controller-entry.ss9"
EVIDENCE = ROOT / "artifacts/runtime-checkpoints/scenario-41-controller-entry-evidence.json"
LEDGER = ROOT / "artifacts/runtime-checkpoints/scenario-41-checkpoints.json"
EXPECTED_CHECKPOINT_SHA256 = (
    "4569846c1bf2cfcc2b6ad8848266bd02d2ada332eeca7acf74456f7a762e7cd6"
)
EXPECTED_RGB_SHA256 = (
    "094b2c4f94ae1bac4141019c559fb06983386ba9b2ad09faa2e723fe8ac97dec"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Scenario41ControllerCheckpointPersistenceTests(unittest.TestCase):
    def test_canonical_checkpoint_exists_and_matches_the_accepted_p1_state(self):
        self.assertTrue(CHECKPOINT.is_file(), "canonical controller checkpoint is missing")
        self.assertEqual(sha256_file(CHECKPOINT), EXPECTED_CHECKPOINT_SHA256)

    def test_compact_evidence_accepts_only_stable_controller_entry(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

        self.assertEqual(evidence["outcome"], "accepted")
        self.assertEqual(evidence["verdict"], "accepted")
        self.assertEqual(evidence["scope"], "scenario-41-controller-entry")
        self.assertEqual(
            evidence["checkpoint"],
            {
                "path": "artifacts/runtime-checkpoints/scenario-41-controller-entry.ss9",
                "sha256": EXPECTED_CHECKPOINT_SHA256,
            },
        )

        provenance = evidence["provenance"]
        self.assertEqual(
            provenance,
            {
                "base_rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "binary_sha256": "20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408",
                "build_manifest_sha256": "9da6779d7c1ac3140e512b233f98abe754c4f11f3fbc8157af147e014661cc4d",
                "patch_sha256": "e76c8fc4f5451bdffe28b7f3595cd441bbb90fb1aa88a926cfbe4f1254d3d2a6",
                "single_input_lua_sha256": "867f5deff09476d0d50c87830611acece918dba7c72f6815e9662613612db562",
                "zero_input_lua_sha256": "1481f10cd8f72c7635326e8d3233c2466b76c7a4b812cefe1220fe43c29f9659",
            },
        )

        raw = evidence["controller_gate"]
        self.assertEqual(raw["run_id"], "9c4631126d8302ae32bc4f0cc0e487db")
        self.assertEqual(
            raw["state_sha256"],
            "7bd7d7b3666162b056c63da9750f531e974353c6083a96e475fbc6f0b4633f81",
        )
        self.assertEqual(
            raw["base_rom_entry_call"],
            {
                "callsite": "0x0808F952",
                "bytes": "e3f7affc",
                "decoded_target": "0x080732B4",
                "return": "0x0808F957",
                "static_thumb_bl_valid": True,
            },
        )
        self.assertEqual(
            raw["task_2"],
            {
                "resume_pc": "0x08073616",
                "sp": "0x03001224",
                "lr": "0x08073617",
            },
        )
        self.assertEqual(
            raw["raw_return_words"],
            ["0x0808F957", "0x08061C71", "0x08061C95"],
        )
        self.assertEqual(
            raw["memory_bytes"],
            {"0x0200A880": 0, "0x0200A882": 1, "0x0202680C": 0},
        )

        stability = evidence["zero_input_stability"]
        self.assertEqual(stability["period_frames"], 224)
        self.assertEqual(stability["normalized_rgb8_sha256"], EXPECTED_RGB_SHA256)
        self.assertEqual(
            [replay["run_id"] for replay in stability["replays"]],
            ["89a882a2ede41a4ab06f4f2cccc36906", "ad079170d922c5297f6556d2a9672a85"],
        )
        self.assertEqual(
            [replay["input_state_sha256"] for replay in stability["replays"]],
            [
                "7bd7d7b3666162b056c63da9750f531e974353c6083a96e475fbc6f0b4633f81",
                EXPECTED_CHECKPOINT_SHA256,
            ],
        )
        self.assertEqual(
            [replay["output_state_sha256"] for replay in stability["replays"]],
            [
                EXPECTED_CHECKPOINT_SHA256,
                "31337b507f2337fa9cc4946f88ffc16230a8d16bcbf427688efec2a0302add33",
            ],
        )
        for replay in stability["replays"]:
            self.assertEqual(replay["capture_frame"], 224)
            self.assertEqual(replay["inputs"], [])
            self.assertEqual(replay["pre_scripts"], [])
            self.assertTrue(replay["zero_input_verified"])
            self.assertEqual(replay["guard_reason"], "completed")
            self.assertEqual(replay["guard_exit_code"], 0)
            self.assertEqual(replay["completion_trigger"], "success-marker")
            self.assertFalse(replay["degraded"])

        scope = evidence["scope_boundary"]
        self.assertEqual(scope["proves"], ["stable controller entry"])
        self.assertEqual(
            scope["does_not_prove"],
            ["player control", "first turn", "MOVEDONE", "victory", "postbattle"],
        )
        self.assertTrue(evidence["superseded_history"])
        self.assertTrue(
            all(item["status"] == "superseded" for item in evidence["superseded_history"])
        )
        hypotheses = {item["hypothesis"] for item in evidence["superseded_history"]}
        self.assertEqual(
            hypotheses,
            {"B/B/Down", "outer-B-enters-controller", "outer-A-directly-enters-controller"},
        )

    def test_ledger_has_one_stable_accepted_controller_entry_record(self):
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        records = [
            record
            for record in ledger["checkpoints"]
            if record["name"] == "scenario-41-controller-entry"
        ]

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["status"], "accepted")
        self.assertEqual(
            record["path"],
            "artifacts/runtime-checkpoints/scenario-41-controller-entry.ss9",
        )
        self.assertEqual(record["sha256"], EXPECTED_CHECKPOINT_SHA256)
        self.assertEqual(record["parent"], "scenario-41-pre-controller-after-a")
        self.assertEqual(
            record["inputs"], ["B", "B", "A", "Down", "Down", "A", "B", "A", "A"]
        )
        self.assertTrue(record["stable_zero_input"])
        self.assertEqual(
            record["zero_input_evidence"],
            ["artifacts/runtime-checkpoints/scenario-41-controller-entry-evidence.json"],
        )
        self.assertEqual(record["allowed_evidence"], [])
        self.assertFalse(
            {"player-control", "movedone", "victory", "postbattle"}
            & set(record["allowed_evidence"])
        )


if __name__ == "__main__":
    unittest.main()
