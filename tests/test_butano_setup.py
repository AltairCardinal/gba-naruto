import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY_PATH = ROOT / "tools" / "butano" / "verify_setup.py"


class ButanoSetupTest(unittest.TestCase):
    @staticmethod
    def _load_verifier():
        spec = importlib.util.spec_from_file_location("verify_setup", VERIFY_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_collect_setup_errors_reports_every_missing_contract(self):
        verifier = self._load_verifier()
        with tempfile.TemporaryDirectory() as temp_dir:
            errors = verifier.collect_setup_errors(Path(temp_dir))

        self.assertEqual(
            errors,
            [
                "missing .gitmodules entry for third_party/butano",
                "missing Butano checkout: third_party/butano",
                "missing offline docs: third_party/butano/docs/index.html",
                "missing minimal project Makefile: butano-sequel/Makefile",
                "missing minimal project source: butano-sequel/src/main.cpp",
                "missing toolchain lock: tools/butano/toolchain.lock",
            ],
        )

    def test_cli_returns_two_for_incomplete_repository(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [sys.executable, str(VERIFY_PATH), "--root", temp_dir],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("Butano setup is incomplete", result.stderr)

    def test_repository_wiring_is_complete(self):
        verifier = self._load_verifier()
        errors = verifier.collect_setup_errors(ROOT)
        self.assertEqual(errors, [])

    def test_generated_butano_outputs_are_ignored(self):
        paths = (
            "butano-sequel/build/main.o",
            "butano-sequel/butano-sequel.gba",
            "build/butano-agent-benchmark-example/B1.json",
        )
        result = subprocess.run(
            ["git", "check-ignore", *paths],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(result.stdout.splitlines()), set(paths))


if __name__ == "__main__":
    unittest.main()
