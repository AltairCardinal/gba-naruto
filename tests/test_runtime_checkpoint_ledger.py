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
            "schema_version": 1,
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

    def test_player_control_accepts_selector_with_either_current_unit_hook(self):
        for current_unit_hook in ("0x080739D8", "0x08073BAC"):
            with self.subTest(current_unit_hook=current_unit_hook):
                self.assertEqual(
                    validate_record(
                        self.make_record(
                            before_hooks=["0x08073946", current_unit_hook]
                        ),
                        self.root,
                    ),
                    [],
                )

    def test_player_control_rejects_incomplete_or_unrelated_hook_combinations(self):
        invalid_hook_sets = (
            ["0x08073946"],
            ["0x080739D8"],
            ["0x08073BAC"],
            ["0x080739D8", "0x08073BAC"],
            ["0xDEADBEEF"],
        )
        for hooks in invalid_hook_sets:
            with self.subTest(hooks=hooks):
                errors = validate_record(
                    self.make_record(before_hooks=hooks), self.root
                )
                self.assertTrue(any("player-control" in error for error in errors))

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
                    rom="base.gba",
                    sha256="1" * 64,
                    rom_sha256=hashlib.sha256(b"rom").hexdigest(),
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

    def test_requires_exact_hooks_and_rejects_unknown_evidence(self):
        required = {
            "player-control": ["0x08073946", "0x080739D8"],
            "movedone": ["0x0807443C", "0x08074918"],
            "victory": ["0x0807444E", "0x08074458"],
            "postbattle": ["0x080735C2"],
        }
        for evidence, hooks in required.items():
            with self.subTest(evidence=evidence):
                self.assertEqual(
                    validate_record(
                        self.make_record(allowed_evidence=[evidence], before_hooks=hooks),
                        self.root,
                    ),
                    [],
                )
                errors = validate_record(
                    self.make_record(
                        allowed_evidence=[evidence], before_hooks=["0xDEADBEEF"]
                    ),
                    self.root,
                )
                self.assertTrue(any(evidence in error for error in errors))

        errors = validate_record(
            self.make_record(allowed_evidence=["typo-or-unknown"]), self.root
        )
        self.assertTrue(any("unknown evidence" in error for error in errors))

    def test_rejects_noncanonical_hook_addresses(self):
        for hook in ("08073946", "0x8073946", "0X08073946", "0x08073946 ", 0x08073946):
            with self.subTest(hook=hook):
                errors = validate_record(
                    self.make_record(before_hooks=[hook]), self.root
                )
                self.assertTrue(any("before_hooks" in error for error in errors))

    def test_paths_are_repo_relative_contained_and_regular_files(self):
        outside = self.root.parent / "outside.ss9"
        outside.write_bytes(b"state")
        self.addCleanup(outside.unlink, missing_ok=True)
        for path in (str(outside), "../outside.ss9", ""):
            with self.subTest(path=path):
                errors = validate_record(self.make_record(path=path), self.root)
                self.assertTrue(any("path" in error for error in errors))

        (self.root / "state-dir").mkdir()
        errors = validate_record(self.make_record(path="state-dir"), self.root)
        self.assertTrue(any("regular file" in error for error in errors))

        for path in (
            "candidate.ss9",
            "artifacts/candidate.ss9",
            "../build/candidate.ss9",
            "build/../candidate.ss9",
        ):
            with self.subTest(candidate_path=path):
                errors = validate_record(
                    self.make_record(
                        status="candidate",
                        path=path,
                        sha256="1" * 64,
                        stable_zero_input=False,
                        allowed_evidence=[],
                        before_hooks=[],
                    ),
                    self.root,
                )
                self.assertTrue(any("build/" in error or "path" in error for error in errors))

        (self.root / "build").mkdir(exist_ok=True)
        (self.root / "build" / "directory.ss9").mkdir()
        errors = validate_record(
            self.make_record(
                status="rejected",
                path="build/directory.ss9",
                sha256="1" * 64,
                stable_zero_input=False,
                allowed_evidence=[],
                before_hooks=[],
            ),
            self.root,
        )
        self.assertTrue(any("directory" in error for error in errors))

    def test_candidate_rom_must_exist_inside_checkout_and_match_hash(self):
        errors = validate_record(
            self.make_record(
                status="candidate",
                path="build/unavailable.ss9",
                sha256="1" * 64,
                rom="build/unavailable.gba",
                rom_sha256="2" * 64,
                stable_zero_input=False,
                allowed_evidence=[],
                before_hooks=[],
            ),
            self.root,
        )
        self.assertTrue(any("ROM" in error for error in errors))

    def test_malformed_json_types_return_errors_without_tracebacks(self):
        malformed = self.make_record(
            name=[],
            status=[],
            path=1,
            rom={},
            parent=[],
            inputs="Down",
            screen=[],
            stable_zero_input=1,
            before_hooks="0x08073946",
            allowed_evidence={"player-control": True},
        )

        errors = validate_ledger(
            {"schema_version": 1, "checkpoints": [malformed]}, self.root
        )

        for field in (
            "name",
            "status",
            "path",
            "rom",
            "parent",
            "inputs",
            "screen",
            "stable_zero_input",
            "before_hooks",
            "allowed_evidence",
        ):
            self.assertTrue(any(field in error for error in errors), field)

    def test_requires_supported_schema_version(self):
        for payload in (
            {"checkpoints": []},
            {"schema_version": "1", "checkpoints": []},
            {"schema_version": 999, "checkpoints": []},
        ):
            with self.subTest(payload=payload):
                errors = validate_ledger(payload, self.root)
                self.assertTrue(any("schema_version" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
