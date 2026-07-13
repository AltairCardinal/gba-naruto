import json
import tempfile
import unittest
from pathlib import Path

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


class FakeProcess:
    def __init__(self, exit_code=0, polls_before_exit=0):
        self.pid = 4242
        self.stdout = None
        self.stderr = None
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


class ProjectResourceGuardTests(unittest.TestCase):
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
            with ProjectLock(lock_path):
                with self.assertRaisesRegex(BlockingIOError, "^heavy resource lock is busy$"):
                    with ProjectLock(lock_path):
                        self.fail("a contended lock must not be acquired")
            with ProjectLock(lock_path):
                pass

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

    def test_completed_and_nonzero_exit_return_child_exit_code(self):
        for exit_code, reason in ((0, "completed"), (7, "child-exit")):
            with self.subTest(exit_code=exit_code):
                result, summary = self._run(
                    launcher=RecordingLauncher(FakeProcess(exit_code=exit_code)),
                )
                self.assertEqual(result.reason, reason)
                self.assertEqual(result.exit_code, exit_code)
                self.assertEqual(summary["reason"], reason)

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

    def test_every_summary_contains_all_result_fields_and_no_temp_file(self):
        result, summary, remaining = self._run(
            launcher=RecordingLauncher(FakeProcess()),
            include_remaining=True,
        )
        self.assertEqual(set(summary), set(GuardResult.__dataclass_fields__))
        self.assertEqual(summary["reason"], result.reason)
        self.assertEqual(remaining, ["summary.json", "task.lock"])

    def _run(
        self,
        *,
        launcher,
        memory_reader=lambda: MemorySnapshot(4096, "fake-memory"),
        tree_rss_reader=lambda pid: 12.5,
        config=GuardConfig(),
        include_remaining=False,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_path = root / "summary.json"
            clock = FakeClock()
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
