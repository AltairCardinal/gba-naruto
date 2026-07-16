import contextlib
import errno
import io
import json
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from tools import project_resource_guard as guard_module
from tools.project_resource_guard import (
    GuardConfig,
    GuardResult,
    MemorySnapshot,
    ProjectLock,
    run_guarded,
)


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class ControlledStream:
    """Expose one chunk only when the fake sleeper reaches a chosen sample."""

    def __init__(self, chunk):
        self.chunk = chunk
        self.release = threading.Event()
        self.drained = threading.Event()
        self._returned = False

    def readline(self):
        if not self._returned:
            self.release.wait(timeout=1)
            self._returned = True
            return self.chunk
        self.drained.set()
        return ""


class IdleDecisionClock(FakeClock):
    """Release output while the monitor obtains the idle-decision timestamp."""

    def __init__(self, stream, release_at):
        super().__init__()
        self.stream = stream
        self.release_at = release_at
        self.released = False

    def __call__(self):
        if (
            threading.current_thread() is threading.main_thread()
            and self.value == self.release_at
            and not self.released
        ):
            self.released = True
            self.stream.release.set()
            if not self.stream.drained.wait(timeout=1):
                raise AssertionError("output drainer did not consume fake stream")
        return self.value


class FakeProcess:
    def __init__(self, exit_code=0, polls_before_exit=0, stdout=None, stderr=None):
        self.pid = 4242
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.polls_before_exit = polls_before_exit
        self.poll_count = 0
        self.terminated = False
        self.killed = False

    def poll(self):
        self.poll_count += 1
        if self.terminated or self.killed:
            return self.exit_code
        if self.poll_count <= self.polls_before_exit:
            return None
        return self.exit_code

    def wait(self, timeout=None):
        return self.exit_code

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class RecordingLauncher:
    def __init__(self, process=None, error=None):
        self.process = process
        self.error = error
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if self.error is not None:
            raise self.error
        return self.process


class FailingStopProcess(FakeProcess):
    def __init__(self, failure):
        super().__init__(polls_before_exit=100)
        self.failure = failure
        self.call_log = []
        self.wait_timeouts = []
        self.wait_calls = 0

    def poll(self):
        self.call_log.append("poll")
        return super().poll()

    def terminate(self):
        self.call_log.append("terminate")
        if self.failure == "terminate":
            raise OSError("terminate failed")
        if self.failure == "terminate-timeout":
            raise subprocess.TimeoutExpired("terminate", 0.1)

    def wait(self, timeout=None):
        self.call_log.append(("wait", timeout))
        self.wait_timeouts.append(timeout)
        self.wait_calls += 1
        if self.wait_calls == 1:
            raise subprocess.TimeoutExpired("fake", timeout)
        if self.failure == "final-wait":
            raise subprocess.TimeoutExpired("fake", timeout)
        return self.exit_code

    def kill(self):
        self.call_log.append("kill")
        if self.failure == "kill":
            raise OSError("kill failed")
        if self.failure != "final-wait":
            self.killed = True


class ProjectResourceGuardTests(unittest.TestCase):
    def test_darwin_available_memory_counts_free_inactive_and_speculative_pages(self):
        vm_stat = """Mach Virtual Memory Statistics: (page size of 4096 bytes)
Pages free:                               1000.
Pages active:                            9000.
Pages inactive:                          2000.
Pages speculative:                        500.
Pages wired down:                        3000.
"""
        completed = subprocess.CompletedProcess(
            ["vm_stat"], 0, stdout=vm_stat, stderr=""
        )

        with (
            mock.patch.object(guard_module.sys, "platform", "darwin"),
            mock.patch.object(
                guard_module.subprocess, "run", return_value=completed
            ) as run,
        ):
            snapshot = guard_module.available_physical_memory_mib()

        self.assertEqual(snapshot.source, "vm-stat")
        self.assertEqual(snapshot.available_physical_mib, 13.671875)
        run.assert_called_once_with(
            ["vm_stat"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

    def test_darwin_rss_sums_only_owned_process_group_from_ps_snapshot(self):
        ps_snapshot = """  PID  PGID    RSS
  100   100   2048
  101   100   3072
  102   100   4096
  999   999  51200
"""
        completed = subprocess.CompletedProcess(
            ["ps"], 0, stdout=ps_snapshot, stderr=""
        )

        with (
            mock.patch.object(guard_module.sys, "platform", "darwin"),
            mock.patch.object(
                guard_module.subprocess, "run", return_value=completed
            ) as run,
        ):
            rss = guard_module._posix_descendant_rss_mib(100)

        self.assertEqual(rss, 9.0)
        run.assert_called_once_with(
            ["ps", "-axo", "pid=,pgid=,rss="],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

    def test_darwin_rss_keeps_counting_owned_group_after_root_exits(self):
        ps_snapshot = """  PID  PGID    RSS
  102   100  40960
  999   999  51200
"""
        completed = subprocess.CompletedProcess(
            ["ps"], 0, stdout=ps_snapshot, stderr=""
        )

        with (
            mock.patch.object(guard_module.sys, "platform", "darwin"),
            mock.patch.object(
                guard_module.subprocess, "run", return_value=completed
            ),
        ):
            rss = guard_module._posix_descendant_rss_mib(100)

        self.assertEqual(rss, 40.0)

    def test_darwin_rss_fails_closed_for_unusable_ps_snapshots(self):
        snapshots = {
            "empty": "",
            "malformed": "PID PGID RSS\nnot process data\n",
            "owned group absent": "999 999 51200\n",
        }

        for label, ps_snapshot in snapshots.items():
            with self.subTest(label=label):
                completed = subprocess.CompletedProcess(
                    ["ps"], 0, stdout=ps_snapshot, stderr=""
                )
                with (
                    mock.patch.object(guard_module.sys, "platform", "darwin"),
                    mock.patch.object(
                        guard_module.subprocess, "run", return_value=completed
                    ),
                    self.assertRaisesRegex(
                        RuntimeError, "ps output has no owned process group"
                    ),
                ):
                    guard_module._posix_descendant_rss_mib(100)

    def test_guard_config_has_exact_defaults(self):
        self.assertEqual(
            GuardConfig(),
            GuardConfig(
                min_available_mib=1024,
                max_tree_rss_mib=1536,
                wall_timeout_s=600,
                idle_timeout_s=60,
                sample_interval_s=1,
                grace_period_s=5,
                allow_degraded=False,
            ),
        )

    def test_project_lock_fails_fast_and_is_reusable_after_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "heavy.lock"
            with ProjectLock(lock_path, "heavy"):
                with self.assertRaisesRegex(BlockingIOError, "^heavy resource lock is busy$"):
                    with ProjectLock(lock_path, "heavy"):
                        self.fail("a contended lock must not be acquired")
            with ProjectLock(lock_path, "heavy"):
                pass

    def test_plan_api_derives_lock_accepts_numeric_memory_and_passes_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "summary.json"
            rejected_launcher = RecordingLauncher(FakeProcess())
            rejected = run_guarded(
                ["unused"],
                cwd=root,
                summary_path=summary_path,
                memory_reader=lambda: 512,
                launcher=rejected_launcher,
            )
            self.assertEqual(rejected.reason, "admission-rejected")
            self.assertEqual(rejected_launcher.calls, [])

            launcher = RecordingLauncher(FakeProcess())
            completed = run_guarded(
                ["fake-command"],
                cwd=root,
                summary_path=summary_path,
                memory_reader=lambda: MemorySnapshot(4096, "fake-memory"),
                tree_rss_reader=lambda pid: 1,
                launcher=launcher,
            )
            self.assertEqual(completed.reason, "completed")
            self.assertEqual(launcher.calls[0][1]["cwd"], root)
            self.assertTrue((root / "build" / "resource-guard" / "heavy.lock").exists())

    def test_admission_rejection_does_not_launch_and_writes_summary(self):
        launcher = RecordingLauncher(process=FakeProcess())
        result, summary = self._run(
            launcher=launcher,
            memory_reader=lambda: MemorySnapshot(512, "fake-memory"),
        )

        self.assertEqual(result.reason, "admission-rejected")
        self.assertEqual(result.exit_code, 75)
        self.assertEqual(launcher.calls, [])
        self.assertEqual(summary["reason"], "admission-rejected")

    def test_missing_rss_reader_fails_closed_before_launch_unless_degraded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "summary.json"
            launcher = RecordingLauncher(FakeProcess())
            result = run_guarded(
                ["fake-command"],
                cwd=root,
                summary_path=summary_path,
                memory_reader=lambda: 4096,
                launcher=launcher,
            )
            self.assertEqual((result.reason, result.exit_code), ("protection-failure", 125))
            self.assertFalse(result.degraded)
            self.assertEqual(launcher.calls, [])
            self.assertEqual(json.loads(summary_path.read_text())["reason"], "protection-failure")

            degraded_launcher = RecordingLauncher(FakeProcess())
            degraded_result = run_guarded(
                ["fake-command"],
                cwd=root,
                summary_path=summary_path,
                config=GuardConfig(allow_degraded=True),
                memory_reader=lambda: 4096,
                launcher=degraded_launcher,
            )
            self.assertEqual(degraded_result.reason, "completed")
            self.assertTrue(degraded_result.degraded)
            self.assertEqual(len(degraded_launcher.calls), 1)

    def test_completed_and_nonzero_exit_return_child_exit_code(self):
        for exit_code, reason in ((0, "completed"), (7, "child-exit")):
            with self.subTest(exit_code=exit_code):
                result, summary = self._run(
                    launcher=RecordingLauncher(FakeProcess(exit_code=exit_code)),
                )
                self.assertEqual(result.reason, reason)
                self.assertEqual(result.exit_code, exit_code)
                self.assertEqual(summary["reason"], reason)
                self.assertNotIn("completion_trigger", summary)

    def test_preexisting_success_marker_rejects_without_launching_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "done.marker"
            marker.write_text("stale", encoding="utf-8")
            launcher = RecordingLauncher(FakeProcess(polls_before_exit=100))

            result = run_guarded(
                ["fake-command"],
                lock_path=root / "task.lock",
                summary_path=root / "summary.json",
                success_marker=marker,
                launcher=launcher,
                memory_reader=lambda: MemorySnapshot(4096, "fake-memory"),
                tree_rss_reader=lambda pid: 1,
                protection_backend="fake-process-tree",
            )

            self.assertEqual((result.reason, result.exit_code), ("protection-failure", 125))
            self.assertEqual(launcher.calls, [])
            summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
            self.assertNotIn("completion_trigger", summary)

    def test_fresh_success_marker_stops_owned_tree_and_reports_trigger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "done.marker"
            process = FakeProcess(polls_before_exit=100)
            clock = FakeClock()

            def create_marker_after_first_sample(seconds):
                clock.sleep(seconds)
                marker.write_text("done", encoding="utf-8")

            result = run_guarded(
                ["fake-command"],
                lock_path=root / "task.lock",
                summary_path=root / "summary.json",
                success_marker=marker,
                config=GuardConfig(
                    wall_timeout_s=100,
                    idle_timeout_s=100,
                    sample_interval_s=1,
                ),
                launcher=RecordingLauncher(process),
                memory_reader=lambda: MemorySnapshot(4096, "fake-memory"),
                tree_rss_reader=lambda pid: 1,
                clock=clock,
                sleeper=create_marker_after_first_sample,
                protection_backend="fake-process-tree",
            )

            self.assertEqual((result.reason, result.exit_code), ("completed", 0))
            self.assertTrue(process.terminated)
            summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["completion_trigger"], "success-marker")

    def test_missing_or_symlink_success_marker_still_times_out(self):
        for marker_kind in ("missing", "symlink"):
            with self.subTest(marker_kind=marker_kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                marker = root / "done.marker"
                process = FakeProcess(polls_before_exit=100)
                clock = FakeClock()

                def sample(seconds):
                    clock.sleep(seconds)
                    if marker_kind == "symlink" and not marker.is_symlink():
                        target = root / "target.marker"
                        target.write_text("done", encoding="utf-8")
                        marker.symlink_to(target)

                result = run_guarded(
                    ["fake-command"],
                    lock_path=root / "task.lock",
                    summary_path=root / "summary.json",
                    success_marker=marker,
                    config=GuardConfig(
                        wall_timeout_s=2,
                        idle_timeout_s=100,
                        sample_interval_s=1,
                    ),
                    launcher=RecordingLauncher(process),
                    memory_reader=lambda: MemorySnapshot(4096, "fake-memory"),
                    tree_rss_reader=lambda pid: 1,
                    clock=clock,
                    sleeper=sample,
                    protection_backend="fake-process-tree",
                )

                self.assertEqual((result.reason, result.exit_code), ("wall-timeout", 124))
                summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
                self.assertNotIn("completion_trigger", summary)

    def test_wall_timeout_stops_only_owned_child(self):
        process = FakeProcess(polls_before_exit=100)
        result, _ = self._run(
            launcher=RecordingLauncher(process),
            config=GuardConfig(wall_timeout_s=2, idle_timeout_s=100, sample_interval_s=1),
        )
        self.assertEqual((result.reason, result.exit_code), ("wall-timeout", 124))
        self.assertTrue(process.terminated)

    def test_idle_timeout_uses_injected_clock_without_real_sleep(self):
        process = FakeProcess(polls_before_exit=100)
        result, _ = self._run(
            launcher=RecordingLauncher(process),
            config=GuardConfig(wall_timeout_s=100, idle_timeout_s=2, sample_interval_s=1),
        )
        self.assertEqual((result.reason, result.exit_code), ("idle-timeout", 124))
        self.assertTrue(process.terminated)

    def test_memory_limit_reports_peak_and_stops_child(self):
        process = FakeProcess(polls_before_exit=100)
        result, summary = self._run(
            launcher=RecordingLauncher(process),
            tree_rss_reader=lambda pid: 200.5,
            config=GuardConfig(
                max_tree_rss_mib=200,
                wall_timeout_s=100,
                idle_timeout_s=100,
            ),
        )
        self.assertEqual((result.reason, result.exit_code), ("memory-limit", 125))
        self.assertEqual(result.peak_tree_rss_mib, 200.5)
        self.assertEqual(summary["peak_tree_rss_mib"], 200.5)
        self.assertTrue(process.terminated)

    def test_complete_stdout_or_stderr_line_refreshes_idle_at_boundary(self):
        for stream_name in ("stdout", "stderr"):
            with self.subTest(stream=stream_name):
                stream = ControlledStream("progress\n")
                process = FakeProcess(polls_before_exit=3, **{stream_name: stream})
                clock = IdleDecisionClock(stream, release_at=2)
                result, _ = self._run(
                    launcher=RecordingLauncher(process),
                    config=GuardConfig(
                        wall_timeout_s=100,
                        idle_timeout_s=2,
                        sample_interval_s=1,
                    ),
                    clock=clock,
                )
                self.assertEqual(result.reason, "completed")

    def test_output_fragment_without_newline_does_not_refresh_idle(self):
        stream = ControlledStream("partial progress")
        process = FakeProcess(polls_before_exit=100, stdout=stream)
        clock = IdleDecisionClock(stream, release_at=2)
        result, _ = self._run(
            launcher=RecordingLauncher(process),
            config=GuardConfig(
                wall_timeout_s=100,
                idle_timeout_s=2,
                sample_interval_s=1,
            ),
            clock=clock,
        )
        self.assertEqual(result.reason, "idle-timeout")

    def test_launch_error_has_no_child(self):
        result, summary = self._run(
            launcher=RecordingLauncher(error=OSError("cannot launch")),
        )
        self.assertEqual((result.reason, result.exit_code), ("launch-error", 125))
        self.assertIsNone(result.child_pid)
        self.assertEqual(summary["child_pid"], None)

    def test_protection_failure_is_terminal_unless_degraded_is_allowed(self):
        process = FakeProcess(polls_before_exit=100)

        def fail_rss(pid):
            raise RuntimeError("rss unavailable")

        result, _ = self._run(
            launcher=RecordingLauncher(process),
            tree_rss_reader=fail_rss,
            config=GuardConfig(wall_timeout_s=100, idle_timeout_s=100),
        )
        self.assertEqual((result.reason, result.exit_code), ("protection-failure", 125))
        self.assertTrue(process.terminated)

        degraded_result, _ = self._run(
            launcher=RecordingLauncher(FakeProcess(polls_before_exit=1)),
            tree_rss_reader=fail_rss,
            config=GuardConfig(allow_degraded=True),
        )
        self.assertEqual(degraded_result.reason, "completed")
        self.assertTrue(degraded_result.degraded)

    def test_memory_reader_failure_becomes_protection_failure(self):
        launcher = RecordingLauncher(FakeProcess())

        def fail_memory():
            raise OSError("memory API failed")

        result, _ = self._run(launcher=launcher, memory_reader=fail_memory)
        self.assertEqual((result.reason, result.exit_code), ("protection-failure", 125))
        self.assertEqual(launcher.calls, [])

    def test_stop_failures_are_protection_failure_and_all_waits_are_bounded(self):
        for failure in ("terminate", "terminate-timeout", "kill", "final-wait"):
            with self.subTest(failure=failure):
                process = FailingStopProcess(failure)
                diagnostics = io.StringIO()
                with contextlib.redirect_stderr(diagnostics):
                    result, summary = self._run(
                        launcher=RecordingLauncher(process),
                        config=GuardConfig(
                            wall_timeout_s=1,
                            idle_timeout_s=100,
                            sample_interval_s=1,
                            grace_period_s=0.1,
                        ),
                    )
                if failure in {"terminate", "terminate-timeout"}:
                    self.assertEqual((result.reason, result.exit_code), ("wall-timeout", 124))
                    self.assertTrue(process.killed)
                else:
                    self.assertEqual((result.reason, result.exit_code), ("protection-failure", 125))
                    self.assertIsNone(process.poll())
                self.assertEqual(summary["reason"], result.reason)
                self.assertIn("kill", process.call_log)
                waits = [entry for entry in process.call_log if isinstance(entry, tuple)]
                self.assertGreaterEqual(len(waits), 1)
                self.assertTrue(all(timeout is not None for _, timeout in waits))
                self.assertTrue(all(0 <= timeout <= 0.1 for _, timeout in waits))
                self.assertIn("poll", process.call_log)
                expected_stage = "terminate" if failure == "terminate-timeout" else failure
                self.assertIn(expected_stage, diagnostics.getvalue())

    def test_non_contention_lock_error_is_protection_failure_with_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "summary.json"
            with mock.patch(
                "tools.project_resource_guard._acquire_file_lock",
                side_effect=OSError(errno.EIO, "disk failure"),
            ):
                result = run_guarded(
                    ["unused"],
                    cwd=root,
                    summary_path=summary_path,
                    memory_reader=lambda: 4096,
                    launcher=RecordingLauncher(FakeProcess()),
                )
            self.assertEqual((result.reason, result.exit_code), ("protection-failure", 125))
            self.assertEqual(json.loads(summary_path.read_text())["reason"], "protection-failure")

    def test_lock_release_failure_rewrites_summary_to_match_returned_result(self):
        original_exit = ProjectLock.__exit__

        def fail_after_release(lock, exc_type, exc_value, traceback):
            original_exit(lock, exc_type, exc_value, traceback)
            raise OSError("injected unlock failure")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "summary.json"
            with mock.patch.object(ProjectLock, "__exit__", fail_after_release):
                result = run_guarded(
                    ["fake-command"],
                    cwd=root,
                    summary_path=summary_path,
                    launcher=RecordingLauncher(FakeProcess()),
                    memory_reader=lambda: 4096,
                    tree_rss_reader=lambda pid: 1.0,
                )
            summary = json.loads(summary_path.read_text())
            self.assertEqual((result.reason, result.exit_code), ("protection-failure", 125))
            self.assertEqual(summary["reason"], result.reason)
            self.assertEqual(summary["exit_code"], result.exit_code)

    def test_owned_protection_is_closed_when_monitor_raises(self):
        class OwnedFakeProcess(FakeProcess):
            protection_backend = "fake-owned-tree"

            def __init__(self, events):
                super().__init__(polls_before_exit=100)
                self.events = events
                self.protection_closed = False
                self.stdout = mock.Mock()
                self.stdout.close.side_effect = lambda: self.events.append("stream-close")

            def tree_rss_mib(self, pid):
                return 1.0

            def close_protection(self):
                self.events.append("protection-close")
                self.protection_closed = True

            def kill(self):
                self.events.append("tree-kill")
                super().kill()

        events = []
        process = OwnedFakeProcess(events)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "summary.json"
            original_write = guard_module._write_summary_atomic

            def record_summary(*args, **kwargs):
                events.append("summary")
                return original_write(*args, **kwargs)

            with (
                mock.patch(
                    "tools.project_resource_guard._launch_owned_process",
                    return_value=process,
                ),
                mock.patch(
                    "tools.project_resource_guard._monitor_started_process",
                    side_effect=RuntimeError("monitor crashed"),
                ),
                mock.patch(
                    "tools.project_resource_guard._write_summary_atomic",
                    side_effect=record_summary,
                ),
            ):
                result = run_guarded(
                    ["fake-command"],
                    cwd=root,
                    summary_path=summary_path,
                    memory_reader=lambda: 4096,
                )

            self.assertEqual((result.reason, result.exit_code), ("protection-failure", 125))
            self.assertTrue(process.protection_closed)
            summary = json.loads(summary_path.read_text())
            self.assertEqual(summary["reason"], "protection-failure")
            self.assertEqual(summary["child_pid"], process.pid)
            self.assertLess(events.index("tree-kill"), events.index("stream-close"))
            self.assertLess(events.index("stream-close"), events.index("summary"))
            self.assertLess(events.index("summary"), events.index("protection-close"))

    def test_closed_stderr_cannot_interrupt_owned_tree_cleanup(self):
        class OwnedFakeProcess(FakeProcess):
            protection_backend = "fake-owned-tree"

            def __init__(self):
                super().__init__(polls_before_exit=100)
                self.protection_closed = False

            def poll(self):
                if self.killed:
                    return 125
                raise OSError("injected poll failure")

            def close_protection(self):
                self.protection_closed = True

        process = OwnedFakeProcess()
        closed_stderr = io.StringIO()
        closed_stderr.close()
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "summary.json"
            with (
                mock.patch.object(guard_module, "_monitor_started_process", side_effect=RuntimeError("monitor failed")),
                mock.patch.object(guard_module.sys, "stderr", closed_stderr),
            ):
                result = run_guarded(
                    ["fake-command"],
                    cwd=tmp,
                    summary_path=summary_path,
                    launcher=RecordingLauncher(process),
                    memory_reader=lambda: 4096,
                    tree_rss_reader=lambda pid: 1.0,
                )
            summary = json.loads(summary_path.read_text())
            self.assertTrue(process.killed)
            self.assertTrue(process.protection_closed)
            self.assertEqual(result.child_pid, process.pid)
            self.assertEqual(summary["child_pid"], process.pid)

    def test_closed_stderr_preserves_owned_setup_failure_pid_and_result(self):
        error = guard_module._OwnedProcessProtectionError(
            "injected assignment failure", 4343, "windows-job-object"
        )
        closed_stderr = io.StringIO()
        closed_stderr.close()
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "summary.json"
            with mock.patch.object(guard_module.sys, "stderr", closed_stderr):
                result = run_guarded(
                    ["fake-command"],
                    cwd=tmp,
                    summary_path=summary_path,
                    launcher=RecordingLauncher(error=error),
                    memory_reader=lambda: 4096,
                    tree_rss_reader=lambda pid: 1.0,
                    protection_backend="windows-job-object",
                )
            summary = json.loads(summary_path.read_text())
            self.assertEqual((result.reason, result.child_pid), ("protection-failure", 4343))
            self.assertEqual(summary["child_pid"], 4343)

    def test_base_exception_writes_summary_and_closes_protection_before_reraise(self):
        class OwnedFakeProcess(FakeProcess):
            protection_backend = "fake-owned-tree"

            def __init__(self):
                super().__init__(polls_before_exit=100)
                self.protection_closed = False

            def tree_rss_mib(self, pid):
                return 1.0

            def close_protection(self):
                self.protection_closed = True

        process = OwnedFakeProcess()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "summary.json"
            with (
                mock.patch(
                    "tools.project_resource_guard._launch_owned_process",
                    return_value=process,
                ),
                mock.patch(
                    "tools.project_resource_guard._monitor_started_process",
                    side_effect=KeyboardInterrupt(),
                ),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    run_guarded(
                        ["fake-command"],
                        cwd=root,
                        summary_path=summary_path,
                        memory_reader=lambda: 4096,
                    )

            summary = json.loads(summary_path.read_text())
            self.assertEqual(summary["reason"], "protection-failure")
            self.assertEqual(summary["child_pid"], process.pid)
            self.assertTrue(process.protection_closed)

    def test_summary_write_failure_still_closes_owned_protection(self):
        class OwnedFakeProcess(FakeProcess):
            protection_backend = "fake-owned-tree"

            def __init__(self):
                super().__init__()
                self.protection_closed = False

            def tree_rss_mib(self, pid):
                return 1.0

            def close_protection(self):
                self.protection_closed = True

        process = OwnedFakeProcess()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (
                mock.patch(
                    "tools.project_resource_guard._launch_owned_process",
                    return_value=process,
                ),
                mock.patch(
                    "tools.project_resource_guard._write_summary_atomic",
                    side_effect=OSError("injected summary failure"),
                ),
            ):
                with self.assertRaisesRegex(OSError, "injected summary failure"):
                    run_guarded(
                        ["fake-command"],
                        cwd=root,
                        summary_path=root / "summary.json",
                        memory_reader=lambda: 4096,
                    )
        self.assertTrue(process.protection_closed)

    def test_every_summary_contains_all_result_fields_and_no_temp_file(self):
        result, summary, remaining = self._run(
            launcher=RecordingLauncher(FakeProcess()),
            include_remaining=True,
        )
        self.assertTrue(set(GuardResult.__dataclass_fields__).issubset(summary))
        self.assertTrue(
            {"command", "cwd", "started_at", "finished_at"}.issubset(summary)
        )
        self.assertEqual(summary["reason"], result.reason)
        self.assertEqual(remaining, ["summary.json", "task.lock"])

    def _run(
        self,
        *,
        launcher,
        memory_reader=lambda: MemorySnapshot(4096, "fake-memory"),
        tree_rss_reader=lambda pid: 12.5,
        config=GuardConfig(),
        clock=None,
        include_remaining=False,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "summary.json"
            clock = clock or FakeClock()
            result = run_guarded(
                ["fake-command"],
                lock_path=root / "task.lock",
                summary_path=summary_path,
                config=config,
                launcher=launcher,
                memory_reader=memory_reader,
                tree_rss_reader=tree_rss_reader,
                clock=clock,
                sleeper=clock.sleep,
                protection_backend="fake-process-tree",
            )
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            remaining = sorted(path.name for path in root.iterdir())
            if include_remaining:
                return result, summary, remaining
            return result, summary


if __name__ == "__main__":
    unittest.main()
