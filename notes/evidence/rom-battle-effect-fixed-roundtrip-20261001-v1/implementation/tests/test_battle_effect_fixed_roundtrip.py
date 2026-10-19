from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import audit_battle_effect_fixed_roundtrip as auditor
from tools.audit_battle_effect_fixed_roundtrip import run_roundtrip
from tools.experiment_workspace import init_run

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "tools/data/battle-effect-fixed-roundtrip-contract-v1.json"
SCRIPT = "tools/audit_battle_effect_fixed_roundtrip.py"


class FixedRoundtripTests(unittest.TestCase):
    def clone(self, root):
        names = set(json.loads((ROOT / CONTRACT).read_text())["inputs"]) | {CONTRACT, SCRIPT}
        for name in names:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)

    def test_all_resources_build_and_read_back_or_reject_capacity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.clone(root)
            run = init_run(root, "roundtrip-test", "all-resources")
            result = run_roundtrip(root, run)
            self.assertTrue(result["verified"])
            self.assertEqual(len(result["resource_ids_total"]), 34)
            self.assertEqual(result["resource_ids_checked"], result["resource_ids_total"])
            self.assertEqual(result["summary"], {
                "resources": 34, "physical_slots": 35, "logical_references": 36,
                "mutation_accepted_resources": 23, "mutation_rejected_resources": 11,
                "mutation_written_slots": 24, "mutation_written_logical_references": 24,
                "actual_build_cli_cases": 35, "all_resource_noop_patches": 0,
            })
            self.assertTrue(result["all_resource_noop_rom_exact"])
            self.assertFalse(result["arbitrary_edit_capacity_complete"])
            self.assertFalse(result["editor_db_connected"])
            self.assertFalse(result["full_graphics_release_gate_complete"])
            self.assertFalse(result["runtime_executed"])
            self.assertEqual(result, json.loads((run / "roundtrip/result.json").read_text()))
            for row in result["rows"]:
                self.assertTrue(row["base_rom_unchanged"])
                if row["mutation_accepted"]:
                    self.assertTrue(row["all_target_aliases_redecoded"])
                    self.assertTrue(row["outside_target_slots_unchanged"])
                    self.assertTrue(row["pointer_table_unchanged"])
                    self.assertGreater(row["changed_rom_bytes"], 0)
                else:
                    self.assertFalse(row["output_rom_present"])
                    self.assertFalse(row["output_report_present"])
                    self.assertIn("does not fit every physical slot", row["rejection_reason"])
            with self.assertRaisesRegex((ValueError, FileExistsError), "exists|already"):
                run_roundtrip(root, run)

    def test_cli_runs_in_relocated_root_with_isolated_build_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.clone(root)
            run = init_run(root, "roundtrip-test", "cli")
            command = [sys.executable, str(root / SCRIPT), "--root", str(root), "--run", str(run)]
            unrelated_db = root / "unrelated-editor.db"
            unrelated_db.write_bytes(b"not an editor database")
            environment = {**os.environ, "DB_PATH": str(unrelated_db),
                           "BUILD_OUTPUT_DIR": str(root / "unrelated-output")}
            completed = subprocess.run(command, cwd=root, env=environment,
                                       text=True, capture_output=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertTrue(result["verified"])
            self.assertTrue(result["build_environment_isolated"])
            self.assertEqual(result["summary"]["actual_build_cli_cases"], 35)
            self.assertEqual(unrelated_db.read_bytes(), b"not an editor database")
            self.assertFalse((root / "unrelated-output").exists())

    def test_actual_output_and_build_report_faults_are_detected(self):
        real_build = auditor._build_cli
        for fault in ["outside-slot", "missing-alias-report", "overflow-output"]:
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                self.clone(root)
                run = init_run(root, "roundtrip-test", "fault")

                def broken_build(fixture, name, edits):
                    completed, case = real_build(fixture, name, edits)
                    if name == "all-resource-noop":
                        return completed, case
                    if completed.returncode == 0:
                        if fault == "outside-slot":
                            raw = bytearray((case / "output.gba").read_bytes())
                            raw[0x10] ^= 1
                            (case / "output.gba").write_bytes(raw)
                        elif fault == "missing-alias-report":
                            report = json.loads((case / "build-report.json").read_text())
                            report["applied_patches"] = []
                            (case / "build-report.json").write_text(json.dumps(report))
                    elif fault == "overflow-output":
                        (case / "output.gba").write_bytes(b"partial output")
                    return completed, case

                message = {"outside-slot": "outside independently rebuilt fixed slots",
                           "missing-alias-report": "bind all physical aliases",
                           "overflow-output": "atomically rejected"}[fault]
                with patch.object(auditor, "_build_cli", side_effect=broken_build):
                    with self.assertRaisesRegex(ValueError, message):
                        run_roundtrip(root, run)
                self.assertFalse((run / "roundtrip/result.json").exists())

    def test_contract_and_repository_drift_fail_before_build(self):
        for name in [CONTRACT, "tools/import_battle_effect_resources.py", "rom/base.gba"]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                self.clone(root)
                run = init_run(root, "roundtrip-test", "drift")
                with (root / name).open("ab") as stream:
                    stream.write(b" ")
                with self.assertRaisesRegex(ValueError, "identity"):
                    run_roundtrip(root, run)
                self.assertFalse((run / "roundtrip").exists())

    def test_missing_and_symbolic_input_fail_closed(self):
        for symbolic in [False, True]:
            with self.subTest(symbolic=symbolic), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                self.clone(root)
                run = init_run(root, "roundtrip-test", "unsafe-input")
                target = root / "tools/rom_layout.py"
                target.unlink()
                if symbolic:
                    target.symlink_to(ROOT / "tools/rom_layout.py")
                with self.assertRaises((ValueError, OSError)):
                    run_roundtrip(root, run)
                self.assertFalse((run / "roundtrip").exists())

    def test_unmanaged_or_completed_run_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.clone(root)
            unmanaged = root / "output"
            unmanaged.mkdir()
            with self.assertRaisesRegex(ValueError, "managed|active"):
                run_roundtrip(root, unmanaged)
            run = init_run(root, "roundtrip-test", "completed")
            metadata = json.loads((run / ".experiment.json").read_text())
            metadata["status"] = "completed"
            (run / ".experiment.json").write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, "active"):
                run_roundtrip(root, run)
            self.assertFalse((run / "roundtrip").exists())

    def test_cli_missing_input_is_json_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            command = [sys.executable, str(ROOT / SCRIPT), "--root", directory, "--run", directory]
            completed = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(completed.returncode, 1, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertFalse(result["verified"])
            self.assertTrue(result["errors"])


if __name__ == "__main__":
    unittest.main()
