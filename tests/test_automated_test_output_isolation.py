#!/usr/bin/env python3
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from tools import build_mod


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AutomatedTestOutputIsolationTests(unittest.TestCase):
    def test_external_build_output_is_verified_without_touching_global_build(self):
        global_rom = ROOT / "build/naruto-sequel-dev.gba"
        global_report = ROOT / "build/naruto-sequel-build-report.json"
        before = (sha256(global_rom), sha256(global_report))

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "build-id"
            automated_report = output / "automated-test-report.json"
            request_db = Path(tmp) / "request-editor.db"
            build_mod.sync_rom_mirrors(request_db)
            env = os.environ.copy()
            env["BUILD_OUTPUT_DIR"] = str(output)
            env["DB_PATH"] = str(request_db)
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/automated_test.py",
                    "--json-output",
                    str(automated_report),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            rom = output / "naruto-sequel-dev.gba"
            build_report_path = output / "naruto-sequel-build-report.json"
            self.assertTrue(rom.exists())
            self.assertTrue(build_report_path.exists())
            self.assertTrue(automated_report.exists())
            test_report = json.loads(automated_report.read_text())
            self.assertEqual(test_report["failed"], 0)
            build_report = json.loads(build_report_path.read_text())
            self.assertEqual(build_report["output_rom"]["sha1"], hashlib.sha1(rom.read_bytes()).hexdigest())

        self.assertEqual((sha256(global_rom), sha256(global_report)), before)


if __name__ == "__main__":
    unittest.main()
