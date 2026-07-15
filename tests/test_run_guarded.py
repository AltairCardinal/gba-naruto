import ctypes
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from tools import project_resource_guard as guard


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "run_guarded.py"
SLEEP_COMMAND = [sys.executable, "-c", "import time; time.sleep(30)"]


def _stop_exact_process(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
    try:
        process.communicate(timeout=1)
    except (subprocess.TimeoutExpired, ValueError):
        pass
    for stream in (process.stdout, process.stderr, process.stdin):
        if stream is not None:
            stream.close()


def _pid_is_alive(pid: int) -> bool:
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        kernel32.GetExitCodeProcess.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_uint32()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == 259
        finally:
            kernel32.CloseHandle(handle)

    stat_path = Path("/proc") / str(pid) / "stat"
    try:
        state = stat_path.read_text(encoding="ascii").rsplit(")", 1)[1].split()[0]
    except (FileNotFoundError, ProcessLookupError):
        return False
    return state != "Z"


def _wait_pid_gone(pid: int, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_is_alive(pid):
            return True
        time.sleep(0.02)
    return not _pid_is_alive(pid)


def _terminate_exact_pid(pid: int) -> None:
    if not _pid_is_alive(pid):
        return
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.TerminateProcess.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel32.OpenProcess(0x0001, False, pid)
        if not handle:
            return
        try:
            kernel32.TerminateProcess(handle, 125)
        finally:
            kernel32.CloseHandle(handle)
        _wait_pid_gone(pid)
        return
    try:
        os.kill(pid, 9)
    except ProcessLookupError:
        return
    _wait_pid_gone(pid)


class RunGuardedCliTests(unittest.TestCase):
    def _run_cli(self, args, *, timeout=8):
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    def test_timeout_removes_child_and_grandchild_and_writes_full_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pid_file = root / "tree.json"
            summary_path = root / "summary.json"
            helper = (
                "import json, os, subprocess, sys, time; "
                "from pathlib import Path; "
                "grandchild=subprocess.Popen([sys.executable, '-c', "
                "'import time; time.sleep(30)']); "
                f"Path({str(pid_file)!r}).write_text(json.dumps([os.getpid(), grandchild.pid])); "
                "time.sleep(30)"
            )

            completed = self._run_cli(
                [
                    "--summary",
                    str(summary_path),
                    "--lock-file",
                    str(root / "heavy.lock"),
                    "--min-available-mib",
                    "0",
                    "--max-tree-rss-mib",
                    "256",
                    "--wall-timeout-s",
                    "0.8",
                    "--idle-timeout-s",
                    "5",
                    "--sample-interval-s",
                    "0.05",
                    "--grace-period-s",
                    "0.2",
                    "--",
                    sys.executable,
                    "-c",
                    helper,
                ]
            )

            self.assertEqual(completed.returncode, 124, completed.stderr)
            pids = json.loads(pid_file.read_text(encoding="utf-8"))
            self.assertEqual(len(pids), 2)
            self.assertTrue(all(_wait_pid_gone(pid) for pid in pids), pids)

            stdout_lines = completed.stdout.splitlines()
            self.assertEqual(len(stdout_lines), 1, completed.stdout)
            printed = json.loads(stdout_lines[0])
            written = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(printed, written)
            required = {
                "child_pid",
                "peak_tree_rss_mib",
                "protection_backend",
                "command",
                "cwd",
                "started_at",
                "finished_at",
                "reason",
                "exit_code",
            }
            self.assertTrue(required.issubset(written), written.keys())
            self.assertEqual(written["child_pid"], pids[0])
            self.assertEqual(written["reason"], "wall-timeout")
            self.assertEqual(
                written["protection_backend"],
                "windows-job-object" if os.name == "nt" else "posix-process-group",
            )

    def test_unrelated_same_name_python_sentinel_survives_tree_cleanup(self):
        sentinel = subprocess.Popen(SLEEP_COMMAND)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                completed = self._run_cli(
                    [
                        "--summary",
                        str(root / "summary.json"),
                        "--lock-file",
                        str(root / "heavy.lock"),
                        "--min-available-mib",
                        "0",
                        "--wall-timeout-s",
                        "0.3",
                        "--idle-timeout-s",
                        "5",
                        "--sample-interval-s",
                        "0.05",
                        "--grace-period-s",
                        "0.1",
                        "--",
                        *SLEEP_COMMAND,
                    ]
                )
                self.assertEqual(completed.returncode, 124, completed.stderr)
                self.assertIsNone(sentinel.poll(), "unrelated sentinel was terminated")
        finally:
            _stop_exact_process(sentinel)

    def test_root_exit_does_not_abandon_live_grandchild(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pid_file = root / "natural-root.json"
            summary_path = root / "summary.json"
            helper = (
                "import json, os, subprocess, sys; "
                "from pathlib import Path; "
                "grandchild=subprocess.Popen([sys.executable, '-c', "
                "'import time; time.sleep(30)']); "
                f"Path({str(pid_file)!r}).write_text(json.dumps([os.getpid(), grandchild.pid]))"
            )
            completed = self._run_cli(
                [
                    "--summary", str(summary_path),
                    "--lock-file", str(root / "heavy.lock"),
                    "--min-available-mib", "0",
                    "--wall-timeout-s", "0.8",
                    "--idle-timeout-s", "5",
                    "--sample-interval-s", "0.05",
                    "--grace-period-s", "0.2",
                    "--", sys.executable, "-c", helper,
                ]
            )
            self.assertEqual(completed.returncode, 124, completed.stderr)
            root_pid, grandchild_pid = json.loads(pid_file.read_text())
            self.assertTrue(_wait_pid_gone(root_pid))
            self.assertTrue(_wait_pid_gone(grandchild_pid))
            self.assertEqual(json.loads(summary_path.read_text())["reason"], "wall-timeout")

    def test_monitor_exception_with_blocked_pipe_kills_exact_owned_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pid_file = root / "exception-tree.json"
            summary_path = root / "summary.json"
            helper = (
                "import json, os, subprocess, sys, time; "
                "from pathlib import Path; "
                "grandchild=subprocess.Popen([sys.executable, '-c', "
                "'import time; time.sleep(30)']); "
                f"Path({str(pid_file)!r}).write_text(json.dumps([os.getpid(), grandchild.pid])); "
                "time.sleep(30)"
            )
            reader_threads = []

            def crash_after_reader_blocks(process, **kwargs):
                reader = threading.Thread(target=process.stdout.readline, daemon=True)
                reader.start()
                reader_threads.append(reader)
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and not pid_file.exists():
                    time.sleep(0.01)
                if not pid_file.exists():
                    raise AssertionError("owned child did not publish PIDs")
                raise RuntimeError("injected monitor crash")

            pids = []
            try:
                started = time.monotonic()
                with mock.patch.object(
                    guard,
                    "_monitor_started_process",
                    side_effect=crash_after_reader_blocks,
                ):
                    result = guard.run_guarded(
                        [sys.executable, "-c", helper],
                        cwd=root,
                        summary_path=summary_path,
                        lock_path=root / "heavy.lock",
                        config=guard.GuardConfig(
                            min_available_mib=0,
                            wall_timeout_s=5,
                            idle_timeout_s=5,
                            sample_interval_s=0.05,
                            grace_period_s=0.5,
                        ),
                    )
                self.assertLess(time.monotonic() - started, 5)
                pids = json.loads(pid_file.read_text())
                self.assertEqual((result.reason, result.exit_code), ("protection-failure", 125))
                self.assertEqual(result.child_pid, pids[0])
                self.assertTrue(all(_wait_pid_gone(pid) for pid in pids), pids)
                for reader in reader_threads:
                    reader.join(timeout=1)
                    self.assertFalse(reader.is_alive(), "pipe reader remained blocked")
                summary = json.loads(summary_path.read_text())
                self.assertEqual(summary["child_pid"], pids[0])
                self.assertEqual(summary["reason"], "protection-failure")
            finally:
                for pid in pids:
                    _terminate_exact_pid(pid)


class RunGuardedCliAndPosixTests(unittest.TestCase):
    _run_cli = RunGuardedCliTests._run_cli

    @unittest.skipUnless(sys.platform == "darwin", "macOS resource integration")
    def test_darwin_cli_launches_and_monitors_an_owned_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "launched.txt"
            summary_path = root / "summary.json"
            helper = (
                "from pathlib import Path; "
                f"Path({str(marker)!r}).write_text('launched')"
            )

            completed = self._run_cli(
                [
                    "--summary", str(summary_path),
                    "--lock-file", str(root / "heavy.lock"),
                    "--min-available-mib", "0",
                    "--wall-timeout-s", "5",
                    "--idle-timeout-s", "5",
                    "--sample-interval-s", "0.05",
                    "--",
                    sys.executable, "-c", helper,
                ]
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(marker.read_text(), "launched")
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["reason"], "completed")
            self.assertEqual(summary["protection_backend"], "posix-process-group")
            self.assertGreater(summary["peak_tree_rss_mib"], 0)

    def test_posix_launcher_uses_new_session_and_exact_process_group(self):
        recorded = {}

        class StubProcess:
            pid = 4321
            stdout = None
            stderr = None

        def launcher(command, **kwargs):
            recorded["command"] = command
            recorded.update(kwargs)
            return StubProcess()

        owned = guard._launch_posix_owned_process(
            ["python", "helper.py"],
            cwd=ROOT,
            launcher=launcher,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertTrue(recorded["start_new_session"])
        self.assertEqual(recorded["cwd"], ROOT)
        self.assertEqual(recorded["command"], ["python", "helper.py"])

        with (
            mock.patch.object(guard.os, "killpg", create=True) as killpg,
            mock.patch.object(guard.signal, "SIGKILL", 9, create=True),
        ):
            owned.terminate()
            owned.kill()
            owned.close_protection()
        self.assertEqual(
            killpg.call_args_list,
            [
                mock.call(4321, guard.signal.SIGTERM),
                mock.call(4321, 9),
                mock.call(4321, 9),
            ],
        )

    def test_posix_rss_sums_only_rooted_descendants(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc_root = Path(tmp)

            def write_process(pid, parent, resident_pages):
                directory = proc_root / str(pid)
                directory.mkdir()
                (directory / "stat").write_text(
                    f"{pid} (fixture) S {parent} 0 0 0\n", encoding="ascii"
                )
                (directory / "statm").write_text(
                    f"100 {resident_pages} 0 0 0 0 0\n", encoding="ascii"
                )

            write_process(100, 1, 2)
            write_process(101, 100, 3)
            write_process(102, 101, 4)
            write_process(999, 1, 50)

            rss = guard._posix_descendant_rss_mib(
                100,
                proc_root=proc_root,
                page_size=1024 * 1024,
            )
        self.assertEqual(rss, 9.0)

    def test_missing_or_empty_command_is_rejected_by_argparse(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = str(Path(tmp) / "summary.json")
            for args in (["--summary", summary], ["--summary", summary, "--"]):
                with self.subTest(args=args):
                    completed = self._run_cli(args)
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn("usage:", completed.stderr.lower())

    def test_command_without_literal_separator_is_rejected_without_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "must-not-launch.txt"
            helper = f"from pathlib import Path; Path({str(marker)!r}).write_text('bad')"
            completed = self._run_cli(
                [
                    "--summary", str(root / "summary.json"),
                    "--min-available-mib", "0",
                    sys.executable, "-c", helper,
                ]
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("usage:", completed.stderr.lower())
            self.assertFalse(marker.exists())

    def test_shared_lock_returns_75_without_launching_second_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_file = root / "heavy.lock"
            first_marker = root / "first.txt"
            second_marker = root / "second.txt"
            first_helper = (
                "import os, time; from pathlib import Path; "
                f"Path({str(first_marker)!r}).write_text(str(os.getpid())); time.sleep(30)"
            )
            first = subprocess.Popen(
                [
                    sys.executable,
                    str(CLI),
                    "--summary",
                    str(root / "first-summary.json"),
                    "--lock-file",
                    str(lock_file),
                    "--min-available-mib",
                    "0",
                    "--wall-timeout-s",
                    "2",
                    "--idle-timeout-s",
                    "30",
                    "--sample-interval-s",
                    "0.05",
                    "--",
                    sys.executable,
                    "-c",
                    first_helper,
                ],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline and not first_marker.exists():
                    if first.poll() is not None:
                        self.fail(first.communicate(timeout=1)[1])
                    time.sleep(0.02)
                self.assertTrue(first_marker.exists(), "first guarded child did not start")

                second_helper = (
                    "from pathlib import Path; "
                    f"Path({str(second_marker)!r}).write_text('launched')"
                )
                completed = self._run_cli(
                    [
                        "--summary",
                        str(root / "second-summary.json"),
                        "--lock-file",
                        str(lock_file),
                        "--min-available-mib",
                        "0",
                        "--",
                        sys.executable,
                        "-c",
                        second_helper,
                    ]
                )
                self.assertEqual(completed.returncode, 75, completed.stderr)
                self.assertFalse(second_marker.exists(), "second child was launched")
                summary = json.loads((root / "second-summary.json").read_text(encoding="utf-8"))
                self.assertEqual(summary["reason"], "lock-busy")
                self.assertIsNone(summary["child_pid"])
            finally:
                try:
                    first.communicate(timeout=4)
                except subprocess.TimeoutExpired:
                    _stop_exact_process(first)
                first_pid = int(first_marker.read_text()) if first_marker.exists() else None
                if first_pid is not None:
                    if not _wait_pid_gone(first_pid):
                        if os.name != "nt":
                            try:
                                os.killpg(first_pid, 9)
                            except ProcessLookupError:
                                pass
                        else:
                            _terminate_exact_pid(first_pid)
                    self.assertTrue(_wait_pid_gone(first_pid), first_pid)

    def test_static_source_contains_no_broad_process_cleanup(self):
        source = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in (ROOT / "tools" / "project_resource_guard.py", CLI)
            if path.exists()
        )
        forbidden = (
            "pkill",
            "killall",
            "taskkill /im",
            "win32_process",
            "get-ciminstance",
            "process_iter(",
            "tasklist",
        )
        for pattern in forbidden:
            with self.subTest(pattern=pattern):
                self.assertNotIn(pattern, source)

    @unittest.skipUnless(os.name == "nt", "Windows Job Object failure path")
    def test_assignment_failure_cleans_only_created_child_and_keeps_sentinel(self):
        sentinel = subprocess.Popen(SLEEP_COMMAND)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                summary_path = root / "summary.json"
                self.assertTrue(hasattr(guard, "_windows_assign_process"))
                diagnostics = io.StringIO()
                with (
                    contextlib.redirect_stderr(diagnostics),
                    mock.patch.object(
                        guard,
                        "_windows_assign_process",
                        side_effect=OSError("injected assignment failure"),
                    ),
                ):
                    result = guard.run_guarded(
                        SLEEP_COMMAND,
                        cwd=root,
                        summary_path=summary_path,
                        lock_path=root / "heavy.lock",
                        config=guard.GuardConfig(
                            min_available_mib=0,
                            wall_timeout_s=5,
                            idle_timeout_s=5,
                            sample_interval_s=0.05,
                            grace_period_s=0.1,
                        ),
                    )
                self.assertEqual((result.reason, result.exit_code), ("protection-failure", 125))
                self.assertIsNotNone(result.child_pid)
                self.assertTrue(_wait_pid_gone(result.child_pid))
                self.assertIsNone(sentinel.poll(), "unrelated sentinel was terminated")
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                self.assertEqual(summary["reason"], "protection-failure")
                self.assertIn(str(result.child_pid), diagnostics.getvalue())
                self.assertIn("injected assignment failure", diagnostics.getvalue())
        finally:
            _stop_exact_process(sentinel)

    def test_assignment_failure_cleanup_does_not_swallow_exact_child_failure(self):
        class UnkillableProcess:
            pid = 2468
            stdout = None
            stderr = None

            def __init__(self):
                self.kill_calls = 0

            def kill(self):
                self.kill_calls += 1
                raise OSError("injected exact-child kill failure")

            def wait(self, timeout=None):
                raise subprocess.TimeoutExpired("fixture", timeout)

            def poll(self):
                return None

        process = UnkillableProcess()
        with self.assertRaisesRegex(RuntimeError, "2468.*cleanup"):
            guard._cleanup_windows_launch_failure(process, 0, False)
        self.assertGreaterEqual(process.kill_calls, 2)


if __name__ == "__main__":
    unittest.main()
