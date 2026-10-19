from pathlib import Path
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

from tools.audit_reverse_engineering_proof import _check_bank, _execute_contract
from tools.verify_map_sprites_partial_bank import proof_binding, verify_partial_bank

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "tools/data/map-sprites-partial-bank-contract-v1.json"
BANK = "sequel/content/map-sprites/bank.json"


class PartialBankTests(unittest.TestCase):
    def clone(self, destination):
        names = list(json.loads((ROOT / CONTRACT).read_text())["inputs"]) + [CONTRACT]
        for name in names:
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, path)

    def test_real_evidence_has_one_of_86_cells(self):
        result = verify_partial_bank(ROOT)
        self.assertTrue(result["verified"])
        self.assertEqual(result["record_ids_total"], [str(i) for i in range(43)])
        self.assertEqual(result["record_ids_covered"], ["1"])
        self.assertEqual(result["field_ids_total"], ["definition_ptr", "animation_ptr"])
        self.assertEqual(result["field_ids_covered"], ["definition_ptr"])
        self.assertEqual(result["cells_covered"], [{"record_id": "1", "field_id": "definition_ptr"}])
        self.assertEqual((result["cells_total"], len(result["cells_uncovered"])), (86, 85))
        self.assertEqual(result["changed_pixel_count"], 213)
        self.assertFalse(result["natural_loader_reentry"])
        self.assertFalse(result["exhaustive"])

    def test_bank_and_source_drift_fail_closed(self):
        for name in [BANK, "tools/render_mode0_checkpoint.py"]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.clone(root)
                with (root / name).open("ab") as stream:
                    stream.write(b"\n ")
                with self.assertRaisesRegex(ValueError, "input hash mismatch"):
                    verify_partial_bank(root)

    def test_evidence_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.clone(root)
            name = "artifacts/map-sprites-definition-id1-pixel-ab-v1/evidence.json"
            (root / name).write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "input hash mismatch"):
                verify_partial_bank(root)

    def test_contract_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.clone(root)
            (root / CONTRACT).write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "contract hash mismatch"):
                verify_partial_bank(root)

    def test_symlink_and_missing_input_fail_closed(self):
        for symbolic in [False, True]:
            with self.subTest(symbolic=symbolic), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.clone(root)
                (root / BANK).unlink()
                if symbolic:
                    (root / BANK).symlink_to(ROOT / BANK)
                with self.assertRaises(ValueError):
                    verify_partial_bank(root)

    def test_existing_auditor_accepts_cli_contract(self):
        result = verify_partial_bank(ROOT)
        proof = proof_binding(ROOT, result)
        verifier = proof["verifiers"][0]
        blockers = []
        replay = _execute_contract(ROOT, "map-sprites", [sys.executable, *verifier["command"][1:]], verifier["contract"], blockers)
        self.assertTrue(replay["contract_ok"], blockers)
        wrong = copy.deepcopy(verifier["contract"])
        wrong["assertions"]["/record_ids_covered"] = [str(i) for i in range(43)]
        rejected = _execute_contract(ROOT, "map-sprites", [sys.executable, *verifier["command"][1:]], wrong, blockers)
        self.assertFalse(rejected["contract_ok"])
        self.assertTrue(any("contract mismatch" in b for b in blockers))

    def test_partial_proof_cannot_pass_exhaustive_bank_gate(self):
        result = verify_partial_bank(ROOT)
        proof = proof_binding(ROOT, result)
        blockers, commands = [], []
        audited = _check_bank(ROOT, "map-sprites", ROOT / BANK, proof, None, blockers, commands)
        self.assertFalse(audited["complete"])
        self.assertEqual(audited["contracted_verifier_count"], 1)
        self.assertEqual(len(commands), 1)
        self.assertTrue(any("not exhaustively ID-bound" in b for b in blockers))
        self.assertTrue(any("field coverage is not exhaustive" in b for b in blockers))
        self.assertFalse(any("lacks a structured" in b for b in blockers))

    def test_binding_cannot_relabel_claims(self):
        result = verify_partial_bank(ROOT)
        result["record_ids_covered"] = ["0", "1"]
        with self.assertRaisesRegex(ValueError, "result mismatch"):
            proof_binding(ROOT, result)

    def test_cli_rejects_missing_inputs_with_json_error(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [sys.executable, str(ROOT / "tools/verify_map_sprites_partial_bank.py"),
                 "--root", directory], text=True, capture_output=True, check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertFalse(result["verified"])
            self.assertTrue(result["errors"])

    def test_relabeling_coverage_exhaustive_does_not_upgrade_contract(self):
        result = verify_partial_bank(ROOT)
        proof = proof_binding(ROOT, result)
        proof["limitations"] = []
        proof["coverage"].update({
            "status": "exhaustive", "records_covered": 43,
            "record_ids_covered": result["record_ids_total"],
            "field_ids_covered": result["field_ids_total"],
        })
        blockers, commands = [], []
        audited = _check_bank(ROOT, "map-sprites", ROOT / BANK, proof, None, blockers, commands)
        self.assertFalse(audited["complete"])
        self.assertTrue(any("no verifier contract binds the exhaustive" in b for b in blockers))


if __name__ == "__main__":
    unittest.main()
