from pathlib import Path
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

from tools.audit_reverse_engineering_proof import _check_bank, _execute_contract
from tools.verify_data_table_b_partial_bank import (
    proof_binding, verify_archive_contents, verify_partial_bank,
)
from tools.verify_data_table_b_message0_pointer_ab import (
    MESSAGE_ID, collect_evidence, extract_raw, verify_artifact,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "tools/data/data-table-b-partial-bank-contract-v2.json"
BANK = "sequel/content/data-table-b/bank.json"
ARTIFACT = "artifacts/data-table-b-message0-pointer-pixel-ab-v1"
SCRIPT = "tools/verify_data_table_b_partial_bank.py"


class PartialMessageBankTests(unittest.TestCase):
    def clone(self, root):
        names = set(json.loads((ROOT / CONTRACT).read_text())["inputs"]) | {CONTRACT, SCRIPT}
        for name in names:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, path)

    def test_real_cell_and_all_uncovered_ids(self):
        result = verify_partial_bank(ROOT)
        self.assertTrue(result["verified"])
        self.assertEqual(result["record_ids_total"], [str(i) for i in range(79)])
        self.assertEqual(result["record_ids_covered"], ["0"])
        self.assertEqual(result["field_ids_total"], ["text_ptr"])
        self.assertEqual(result["cells_covered"], [{"record_id": "0", "field_id": "text_ptr"}])
        self.assertEqual(result["cells_uncovered"], [
            {"record_id": str(i), "field_id": "text_ptr"} for i in range(1, 79)
        ])
        self.assertEqual(result["cells_total"], 79)
        self.assertEqual(result["changed_pixel_count"], 928)
        self.assertFalse(result["zero_input_control_verified"])
        self.assertFalse(result["historical_shared_lock_verified"])
        self.assertFalse(result["physical_gba_verified"])
        self.assertFalse(result["exhaustive"])
        self.assertEqual(result["scope"], "legacy_archived_natural_action7_pointer_ab")

    def test_frozen_legacy_verifier_agrees(self):
        # The legacy verifier binds the whole artifact to the capture-time tree,
        # so it stopped accepting the artifact once project_resource_guard.py
        # changed (that file is never executed by the offline replay).  Its
        # independent offline reconstruction stays the cross-check, and the one
        # remaining divergence is pinned so it cannot drift unnoticed.
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory).resolve(strict=True)
            extract_raw(ROOT / ARTIFACT / "raw.tar", raw)
            evidence, _ = collect_evidence(ROOT, raw)
        result = verify_partial_bank(ROOT)
        self.assertEqual(result["record_ids_covered"], [str(MESSAGE_ID)])
        self.assertEqual(result["changed_pixel_count"], evidence["runtime_effect"]["different_pixel_count"])
        self.assertEqual(evidence["runtime_effect"]["different_pixel_count"], 928)
        with self.assertRaisesRegex(ValueError, "implementation hash mismatch: tools/project_resource_guard.py"):
            verify_artifact(ROOT, ROOT / ARTIFACT)

    def test_portable_root_and_real_cli_without_capture_host_files(self):
        expected = verify_partial_bank(ROOT)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.clone(root)
            self.assertEqual(verify_partial_bank(root), expected)
            p = subprocess.run([sys.executable, str(root / SCRIPT), "--root", str(root)],
                               cwd=root, text=True, capture_output=True, check=False)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(json.loads(p.stdout), expected)

    def test_repository_input_drift_fails_closed(self):
        for name in [BANK, f"{ARTIFACT}/raw.tar", f"{ARTIFACT}/evidence.json",
                     "tools/thumb_branch.py", "tools/inspect_mgba_savestate.py"]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.clone(root)
                with (root / name).open("ab") as stream:
                    stream.write(b" ")
                with self.assertRaisesRegex(ValueError, "input identity"):
                    verify_partial_bank(root)

    def test_contract_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.clone(root)
            (root / CONTRACT).write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "contract identity"):
                verify_partial_bank(root)

    def test_missing_and_symbolic_input_fail_closed(self):
        for symbolic in [False, True]:
            with self.subTest(symbolic=symbolic), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.clone(root)
                (root / BANK).unlink()
                if symbolic:
                    (root / BANK).symlink_to(ROOT / BANK)
                with self.assertRaises((ValueError, OSError)):
                    verify_partial_bank(root)

    def test_archive_audit_selector_inputs_and_guard_recomputed(self):
        mutations = [
            ("baseline/audit.json", "capture_frame", 301),
            ("baseline/audit.json", "automatic_inputs", [{"key": "A"}]),
            ("candidate/audit.json", "input_state", "/unrelated/scenario-50.ss9"),
            ("candidate/guard.json", "degraded", True),
            ("candidate/guard.json", "command", ["wrong-binary"]),
        ]
        for name, key, value in mutations:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                raw = Path(directory)
                extract_raw(ROOT / ARTIFACT / "raw.tar", raw)
                p = raw / name
                v = json.loads(p.read_text()); v[key] = value
                p.write_text(json.dumps(v))
                if name.endswith("audit.json"):
                    (p.parent / "sentinel.json").write_text(json.dumps(v))
                with self.assertRaisesRegex(ValueError, "provenance"):
                    verify_archive_contents(ROOT, raw)

    def test_archive_selector_memory_is_not_just_a_receipt_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            extract_raw(ROOT / ARTIFACT / "raw.tar", raw)
            shutil.copyfile(raw / "candidate/output.ss9", raw / "baseline/output.ss9")
            with self.assertRaisesRegex(ValueError, "selector scratch"):
                verify_archive_contents(ROOT, raw)

    def test_archive_embedded_screen_is_recomputed(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            extract_raw(ROOT / ARTIFACT / "raw.tar", raw)
            shutil.copyfile(raw / "candidate/output.png", raw / "baseline/output.png")
            with self.assertRaisesRegex(ValueError, "embedded screen"):
                verify_archive_contents(ROOT, raw)

    def test_archive_checkpoint_and_launch_identity_are_recomputed(self):
        for member in ["input.ss9", "launch-identity.json"]:
            with self.subTest(member=member), tempfile.TemporaryDirectory() as directory:
                raw = Path(directory)
                extract_raw(ROOT / ARTIFACT / "raw.tar", raw)
                (raw / member).write_text("{}\n")
                with self.assertRaisesRegex(ValueError, "identity mismatch"):
                    verify_archive_contents(ROOT, raw)

    def test_existing_auditor_executes_contract_and_rejects_wrong_ids(self):
        result = verify_partial_bank(ROOT)
        proof = proof_binding(ROOT, result)
        v = proof["verifiers"][0]
        command = [sys.executable, *v["command"][1:]]
        blockers = []
        accepted = _execute_contract(ROOT, "data-table-b", command, v["contract"], blockers)
        self.assertTrue(accepted["contract_ok"], blockers)
        wrong = copy.deepcopy(v["contract"])
        wrong["assertions"]["/record_ids_covered"] = ["0", "1"]
        rejected = _execute_contract(ROOT, "data-table-b", command, wrong, blockers)
        self.assertFalse(rejected["contract_ok"])

    def test_partial_gate_and_false_exhaustive_upgrade_rejected(self):
        result = verify_partial_bank(ROOT)
        proposal = proof_binding(ROOT, result)
        blockers, commands = [], []
        checked = _check_bank(ROOT, "data-table-b", ROOT / BANK, proposal, None, blockers, commands)
        self.assertFalse(checked["complete"])
        self.assertEqual(checked["contracted_verifier_count"], 1)
        self.assertEqual(len(commands), 1)
        self.assertTrue(any("not exhaustively ID-bound" in b for b in blockers))
        proposal["limitations"] = []
        proposal["coverage"].update({"status": "exhaustive", "records_covered": 79,
                                       "record_ids_covered": result["record_ids_total"]})
        blockers, commands = [], []
        checked = _check_bank(ROOT, "data-table-b", ROOT / BANK, proposal, None, blockers, commands)
        self.assertFalse(checked["complete"])
        self.assertTrue(any("no verifier contract binds the exhaustive" in b for b in blockers))

    def test_binding_rejects_relabelled_claims(self):
        result = verify_partial_bank(ROOT)
        result["zero_input_control_verified"] = True
        with self.assertRaisesRegex(ValueError, "result mismatch"):
            proof_binding(ROOT, result)

    def test_cli_missing_input_reports_json_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            p = subprocess.run([sys.executable, str(ROOT / SCRIPT), "--root", directory],
                               text=True, capture_output=True, check=False)
            self.assertEqual(p.returncode, 1, p.stderr)
            value = json.loads(p.stdout)
            self.assertFalse(value["verified"])
            self.assertTrue(value["errors"])


if __name__ == "__main__":
    unittest.main()
