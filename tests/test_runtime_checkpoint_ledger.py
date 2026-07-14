import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.runtime_checkpoint_ledger import validate_ledger, validate_record


class RuntimeCheckpointLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "state.ss9").write_bytes(b"state")
        (self.root / "base.gba").write_bytes(b"rom")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def make_record(self, **overrides):
        record = {
            "name": "scenario-41-start-row",
            "status": "accepted",
            "path": "state.ss9",
            "sha256": hashlib.sha256(b"state").hexdigest(),
            "rom": "base.gba",
            "rom_sha256": hashlib.sha256(b"rom").hexdigest(),
            "parent": "tutorial-ui-save",
            "inputs": ["Down", "Down"],
            "screen": "scenario-41-start-row",
            "stable_zero_input": True,
            "before_hooks": ["0x08073946", "0x080739D8"],
            "allowed_evidence": ["player-control"],
        }
        record.update(overrides)
        return record

    def make_ledger(self):
        return {
            "checkpoints": [
                self.make_record(
                    name="tutorial-ui-save",
                    parent=None,
                    inputs=[],
                    allowed_evidence=[],
                    before_hooks=[],
                ),
                self.make_record(),
            ]
        }

    def test_accepts_a_traced_stable_pre_hook_checkpoint(self):
        self.assertEqual(validate_record(self.make_record(), self.root), [])

    def test_rejects_wrong_hash_unknown_parent_and_crossed_hook(self):
        payload = self.make_ledger()
        payload["checkpoints"][0]["sha256"] = "0" * 64
        payload["checkpoints"][1]["parent"] = "missing"
        payload["checkpoints"][1]["before_hooks"] = []

        errors = validate_ledger(payload, self.root)

        self.assertTrue(any("sha256" in error for error in errors))
        self.assertTrue(any("parent" in error for error in errors))
        self.assertTrue(any("player-control" in error for error in errors))

    def test_rejects_missing_fields_and_unstable_accepted_checkpoint(self):
        record = self.make_record(stable_zero_input=False)
        del record["screen"]

        self.assertEqual(validate_record(record, self.root), ["missing field: screen"])

        errors = validate_record(self.make_record(stable_zero_input=False), self.root)
        self.assertTrue(any("not stable" in error for error in errors))

    def test_allows_unavailable_candidate_and_rejected_source_paths(self):
        for status in ("candidate", "rejected"):
            with self.subTest(status=status):
                record = self.make_record(
                    status=status,
                    path="build/unavailable.ss9",
                    rom="build/unavailable.gba",
                    sha256="1" * 64,
                    rom_sha256="2" * 64,
                    stable_zero_input=False,
                    allowed_evidence=[],
                    before_hooks=[],
                )
                self.assertEqual(validate_record(record, self.root), [])

    def test_rejects_duplicate_names_bad_hash_metadata_and_child_before_parent(self):
        payload = self.make_ledger()
        payload["checkpoints"][0]["rom_sha256"] = "not-a-sha256"
        payload["checkpoints"].append(
            self.make_record(name="tutorial-ui-save", parent="later-parent")
        )
        payload["checkpoints"].append(
            self.make_record(name="later-parent", parent=None)
        )

        errors = validate_ledger(payload, self.root)

        self.assertTrue(any("duplicate" in error for error in errors))
        self.assertTrue(any("rom_sha256" in error for error in errors))
        self.assertTrue(any("parent-before-child" in error for error in errors))

    def test_rejects_unknown_status_and_evidence_boundary(self):
        payload = self.make_ledger()
        payload["checkpoints"][1]["status"] = "promoted"
        payload["checkpoints"][1]["allowed_evidence"] = ["movedone"]
        payload["checkpoints"][1]["before_hooks"] = []

        errors = validate_ledger(payload, self.root)

        self.assertTrue(any("status" in error for error in errors))
        self.assertTrue(any("movedone" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
