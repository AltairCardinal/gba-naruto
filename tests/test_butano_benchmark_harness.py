import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLOCK = ROOT / "tools" / "butano" / "benchmark_clock.py"
CPP_RUNNER = ROOT / "tools" / "butano" / "run_cpp_benchmark_tests.py"


class ButanoBenchmarkHarnessTest(unittest.TestCase):
    def test_clock_records_an_immutable_task_lifecycle(self):
        self.assertTrue(CLOCK.is_file(), "benchmark clock is missing")
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            start = subprocess.run(
                [sys.executable, str(CLOCK), str(run_dir), "start", "B1"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(start.returncode, 0, start.stderr)

            duplicate = subprocess.run(
                [sys.executable, str(CLOCK), str(run_dir), "start", "B1"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("already exists", duplicate.stderr)

            event = subprocess.run(
                [
                    sys.executable,
                    str(CLOCK),
                    str(run_dir),
                    "event",
                    "B1",
                    "--kind",
                    "red",
                    "--command",
                    "false",
                    "--exit-code",
                    "1",
                    "--note",
                    "missing header",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(event.returncode, 0, event.stderr)

            finish = subprocess.run(
                [sys.executable, str(CLOCK), str(run_dir), "finish", "B1"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(finish.returncode, 0, finish.stderr)

            manifest = json.loads((run_dir / "B1.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["task_id"], "B1")
            self.assertEqual(manifest["status"], "finished")
            self.assertGreaterEqual(manifest["duration_seconds"], 0)
            self.assertEqual(manifest["events"][0]["kind"], "red")
            self.assertEqual(manifest["events"][0]["exit_code"], 1)

            second_finish = subprocess.run(
                [sys.executable, str(CLOCK), str(run_dir), "finish", "B1"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(second_finish.returncode, 0)
            self.assertIn("already finished", second_finish.stderr)

    def test_cpp_runner_fails_closed_when_no_tests_are_selected(self):
        self.assertTrue(CPP_RUNNER.is_file(), "C++ benchmark runner is missing")
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [sys.executable, str(CPP_RUNNER), "--root", temp_dir],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("no C++ benchmark tests selected", result.stderr)


if __name__ == "__main__":
    unittest.main()
