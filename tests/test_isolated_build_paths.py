#!/usr/bin/env python3
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from tools import automated_test, build_mod


class IsolatedBuildPathTests(unittest.TestCase):
    def test_build_mod_prefers_request_db_path(self):
        with patch.dict(os.environ, {"DB_PATH": "/tmp/request/editor.db"}):
            self.assertEqual(
                build_mod.editor_db_path(), Path("/tmp/request/editor.db")
            )

    def test_automated_checks_follow_build_output_dir(self):
        with patch.dict(
            os.environ,
            {"BUILD_OUTPUT_DIR": "/tmp/request/output"},
        ):
            self.assertEqual(
                automated_test.build_report_path(),
                Path("/tmp/request/output/naruto-sequel-build-report.json"),
            )
            self.assertEqual(
                automated_test.output_rom_path(),
                Path("/tmp/request/output/naruto-sequel-dev.gba"),
            )


if __name__ == "__main__":
    unittest.main()
