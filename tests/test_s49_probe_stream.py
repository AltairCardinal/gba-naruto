"""Windows real-pipe regressions for the interactive probe's reader lifecycle."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from tools.s49_victory_capture.probe import Probe, ProbeError


CHILD = r'''
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
print("READY")
for raw in sys.stdin:
    command = raw.rstrip("\r\n")
    if command in ("quit", "eof"):
        break
    if command.startswith("echo "):
        print(command[5:])
    elif command.startswith("bulk "):
        for index in range(int(command.split()[1])):
            print(f"行-{index}")
    elif command == "slow":
        time.sleep(0.15)
        print("late")
    elif command == "bad":
        sys.stdout.buffer.write(b"\xff\n")
        sys.stdout.buffer.flush()
    elif command == "error":
        print("ERR simulated")
    elif command == "flood":
        try:
            while True:
                print("x" * 256)
        except BrokenPipeError:
            os._exit(0)
    else:
        print("ok:" + command)
'''


class ProbeStreamTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="probe-stream-test-")
        self.addCleanup(self.directory.cleanup)
        self.child = pathlib.Path(self.directory.name) / "child.py"
        self.child.write_text(CHILD, encoding="utf-8")
        self.probe = Probe(self.child, exe=sys.executable, timeout=2)
        self.addCleanup(self.probe.close)

    def assert_readers_stopped(self):
        for reader in (self.probe._stdout_reader, self.probe._stderr_reader):
            self.assertIsNotNone(reader)
            self.assertFalse(reader.is_alive(), reader.name)

    def test_ten_thousand_lines_are_ordered_with_two_threads_total(self):
        started = []
        original = threading.Thread.start

        def record_start(thread):
            started.append(thread.name)
            return original(thread)

        with patch.object(threading.Thread, "start", record_start):
            self.probe.start()
            output = self.probe.run("bulk 10000")
            self.assertEqual([f"行-{index}" for index in range(10000)], output)
            self.assertEqual(["ok:next"], self.probe.run("next"))
            self.probe.close()
        self.assertCountEqual(
            ["mgba-probe-stdout", "mgba-probe-stderr"], started)
        self.assert_readers_stopped()

    def test_timeout_keeps_one_reader_and_does_not_steal_late_output(self):
        self.probe.start()
        reader = self.probe._stdout_reader
        self.probe.timeout = 0.02
        with self.assertRaisesRegex(ProbeError, "timed out"):
            self.probe.run("slow")
        self.probe.timeout = 2
        self.assertEqual("late\n", self.probe._read_line())
        self.assertEqual("___K_PROBE_END_1___\n", self.probe._read_line())
        self.assertEqual(["ok:next"], self.probe.run("next"))
        self.assertIs(reader, self.probe._stdout_reader)

    def test_eof_is_stable_and_close_is_idempotent(self):
        self.probe.start()
        process = self.probe._proc
        self.assertEqual([], self.probe.run("eof"))
        self.assertIsNone(self.probe._read_line())
        self.assertIsNone(self.probe._read_line())
        self.probe.close()
        self.probe.close()
        self.assertTrue(process.stdin.closed)
        self.assert_readers_stopped()

    def test_restart_uses_fresh_queue_and_streams(self):
        self.probe.start()
        first = self.probe._stdout_reader
        self.assertEqual(["ok:first"], self.probe.run("first"))
        self.probe.close()
        self.assert_readers_stopped()
        self.probe.start()
        self.assertIsNot(first, self.probe._stdout_reader)
        self.assertEqual(["ok:second"], self.probe.run("second"))
        self.probe.close()
        self.assert_readers_stopped()

    def test_full_queue_close_unblocks_producer_and_child(self):
        self.probe.start()
        self.probe._proc.stdin.write("flood\n")
        self.probe._proc.stdin.flush()
        deadline = time.monotonic() + 2
        while not self.probe._stdout_queue.full():
            self.assertLess(time.monotonic(), deadline, "queue did not fill")
            time.sleep(0.005)
        self.probe.close()
        self.assert_readers_stopped()

    def test_invalid_utf8_surfaces_reader_failure(self):
        self.probe.start()
        with self.assertRaisesRegex(ProbeError, "output reader failed") as error:
            self.probe.run("bad")
        self.assertIsInstance(error.exception.__cause__, UnicodeDecodeError)
        self.probe.close()
        self.assert_readers_stopped()

    def test_protocol_error_still_preserves_next_command_boundary(self):
        self.probe.start()
        with self.assertRaisesRegex(ProbeError, "ERR simulated"):
            self.probe.run("error")
        self.assertEqual(["ok:next"], self.probe.run("next"))

    def test_startup_timeout_closes_child_and_readers(self):
        self.child.write_text(
            CHILD.replace('print("READY")', 'time.sleep(0.1)\nprint("READY")'),
            encoding="utf-8")
        self.probe.timeout = 0.01
        with self.assertRaisesRegex(ProbeError, "timed out"):
            self.probe.start()
        self.assertIsNone(self.probe._proc)
        self.assert_readers_stopped()

    def test_partial_reader_start_failure_closes_child(self):
        original = threading.Thread.start

        def fail_stderr(thread):
            if thread.name == "mgba-probe-stderr":
                raise RuntimeError("simulated thread start failure")
            return original(thread)

        with patch.object(threading.Thread, "start", fail_stderr):
            with self.assertRaisesRegex(RuntimeError, "thread start failure"):
                self.probe.start()
        self.assertIsNone(self.probe._proc)
        self.assertFalse(self.probe._stdout_reader.is_alive())


if __name__ == "__main__":
    unittest.main()
