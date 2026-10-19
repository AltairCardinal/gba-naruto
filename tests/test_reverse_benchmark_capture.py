#!/usr/bin/env python3
"""Process-level integration contract for timestamped benchmark capture."""

from __future__ import annotations

import json
import io
import os
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from tools.reverse_benchmark import capture


ROOT = Path(__file__).resolve().parents[1]


class BenchmarkCaptureTests(unittest.TestCase):
    def test_capture_refuses_to_finish_while_a_stream_reader_is_alive(self):
        class StuckReader:
            def __init__(self):
                self.joined = False

            def join(self, timeout):
                self.joined = True

            def is_alive(self):
                return True

        reader = StuckReader()
        with self.assertRaisesRegex(RuntimeError, "stream reader did not finish"):
            capture._join_drain_threads((reader,), timeout=0)  # type: ignore[attr-defined]
        self.assertTrue(reader.joined)

    def test_stream_reader_reports_exceptions_instead_of_silently_finishing(self):
        class BrokenSource:
            def readline(self):
                raise OSError("simulated pipe failure")

        errors = queue.Queue()
        capture._drain(
            BrokenSource(),  # type: ignore[arg-type]
            io.StringIO(),
            stream_name="stdout",
            lock=threading.Lock(),
            activity_lock=threading.Lock(),
            errors=errors,
        )

        with self.assertRaisesRegex(RuntimeError, "stream reader failed"):
            capture._raise_reader_errors(errors)

    def test_capture_records_both_streams_monotonic_time_and_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.reverse_benchmark.capture",
                    "--events",
                    str(output / "events.jsonl"),
                    "--stderr",
                    str(output / "stderr.jsonl"),
                    "--stdin",
                    str(output / "stdin.txt"),
                    "--",
                    sys.executable,
                    "-c",
                    (
                        "import sys; "
                        "data=sys.stdin.read(); "
                        "print('out:'+data); "
                        "print('err', file=sys.stderr)"
                    ),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertNotEqual(0, completed.returncode)
            (output / "stdin.txt").write_text("prompt", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.reverse_benchmark.capture",
                    "--events",
                    str(output / "events.jsonl"),
                    "--stderr",
                    str(output / "stderr.jsonl"),
                    "--stdin",
                    str(output / "stdin.txt"),
                    "--",
                    sys.executable,
                    "-c",
                    (
                        "import sys; "
                        "data=sys.stdin.read(); "
                        "print('out:'+data); "
                        "print('err', file=sys.stderr)"
                    ),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=10,
            )

            stdout_events = [
                json.loads(line)
                for line in (output / "events.jsonl").read_text().splitlines()
            ]
            stderr_events = [
                json.loads(line)
                for line in (output / "stderr.jsonl").read_text().splitlines()
            ]
            activity_lines = completed.stdout.splitlines()

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual("process.started", stdout_events[0]["type"])
        self.assertEqual("out:prompt", stdout_events[1]["line"])
        self.assertEqual("process.exited", stdout_events[-1]["type"])
        self.assertEqual(0, stdout_events[-1]["exit_code"])
        self.assertEqual("err", stderr_events[0]["line"])
        self.assertEqual(
            ["benchmark-child-activity", "benchmark-child-activity"],
            activity_lines,
        )
        self.assertNotIn("out:prompt", completed.stdout)
        self.assertNotIn("err", completed.stdout)
        monotonic_values = [
            event["monotonic_ns"]
            for event in stdout_events + stderr_events
        ]
        self.assertTrue(all(value >= 0 for value in monotonic_values))

    def test_capture_redacts_credentials_before_stream_evidence_is_written(self):
        shaped_secret = "sk-capture-shaped-sentinel-1234567890"
        environment_secret = "arbitrary-environment-secret-sentinel"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "stdin.txt").write_text("prompt", encoding="utf-8")
            environment = dict(os.environ)
            environment["BENCH_CAPTURE_SECRET"] = environment_secret
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.reverse_benchmark.capture",
                    "--events",
                    str(output / "events.jsonl"),
                    "--stderr",
                    str(output / "stderr.jsonl"),
                    "--stdin",
                    str(output / "stdin.txt"),
                    "--redact-env",
                    "BENCH_CAPTURE_SECRET",
                    "--",
                    sys.executable,
                    "-c",
                    (
                        "import os, sys; "
                        "a='sk-'+'capture-shaped-sentinel-1234567890'; "
                        "b=os.environ['BENCH_CAPTURE_SECRET']; "
                        "print(a); print('Authorization: Bearer '+b, file=sys.stderr)"
                    ),
                ],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=10,
            )
            evidence = (output / "events.jsonl").read_text() + (
                output / "stderr.jsonl"
            ).read_text()

        self.assertEqual(86, completed.returncode, completed.stderr)
        self.assertNotIn(shaped_secret, evidence)
        self.assertNotIn(environment_secret, evidence)
        self.assertIn("[REDACTED]", evidence)
        self.assertIn("security.credential-material-redacted", evidence)


if __name__ == "__main__":
    unittest.main()
