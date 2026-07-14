"""Shared admission and monitoring guard for project-owned heavy tasks."""

from __future__ import annotations

import ctypes
import errno
import json
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence


@dataclass(frozen=True)
class MemorySnapshot:
    available_physical_mib: float
    source: str


@dataclass(frozen=True)
class GuardConfig:
    min_available_mib: int = 1024
    max_tree_rss_mib: int = 1536
    wall_timeout_s: float = 600
    idle_timeout_s: float = 60
    sample_interval_s: float = 1
    grace_period_s: float = 5
    allow_degraded: bool = False


@dataclass(frozen=True)
class GuardResult:
    reason: str
    exit_code: int
    child_pid: int | None
    peak_tree_rss_mib: float
    protection_backend: str
    degraded: bool


class ProjectLock:
    """Cross-platform non-blocking one-byte file lock."""

    def __init__(self, path: str | Path, label: str = "heavy"):
        self.path = Path(path)
        self.label = label
        self._file = None

    def __enter__(self) -> ProjectLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self.path.open("a+b")
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        try:
            _acquire_file_lock(lock_file)
        except OSError as error:
            lock_file.close()
            if _is_lock_contention(error):
                raise _HeavyResourceLockBusy(f"{self.label} resource lock is busy") from error
            raise
        self._file = lock_file
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        lock_file = self._file
        self._file = None
        if lock_file is None:
            return
        try:
            lock_file.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()


class _HeavyResourceLockBusy(BlockingIOError):
    """Identify only an operating-system lock contention condition."""


def _acquire_file_lock(lock_file) -> None:
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _is_lock_contention(error: OSError) -> bool:
    if error.errno in {errno.EACCES, errno.EAGAIN}:
        return True
    return os.name == "nt" and getattr(error, "winerror", None) in {33, 36}


def available_physical_memory_mib() -> MemorySnapshot:
    """Return currently available physical memory for supported platforms."""

    if sys.platform.startswith("linux"):
        with Path("/proc/meminfo").open("r", encoding="ascii") as meminfo:
            for line in meminfo:
                if line.startswith("MemAvailable:"):
                    available_kib = int(line.split()[1])
                    return MemorySnapshot(available_kib / 1024, "proc-meminfo")
        raise RuntimeError("MemAvailable is absent from /proc/meminfo")

    if os.name == "nt":
        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError(ctypes.get_last_error(), "GlobalMemoryStatusEx failed")
        return MemorySnapshot(status.ullAvailPhys / (1024 * 1024), "global-memory-status-ex")

    raise RuntimeError(f"physical memory reader is unsupported on {sys.platform}")


def run_guarded(
    command: Sequence[str],
    *,
    cwd: str | Path | None = None,
    summary_path: str | Path,
    config: GuardConfig = GuardConfig(),
    lock_path: str | Path | None = None,
    launcher: Callable[..., object] = subprocess.Popen,
    memory_reader: Callable[[], MemorySnapshot | float] = available_physical_memory_mib,
    tree_rss_reader: Callable[[int], float] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    protection_backend: str = "process-tree-rss",
) -> GuardResult:
    """Run one owned child under lock, admission, and resource monitoring."""

    summary_path = Path(summary_path)
    cwd_path = Path.cwd() if cwd is None else Path(cwd)
    effective_lock_path = (
        Path(lock_path)
        if lock_path is not None
        else cwd_path / "build" / "resource-guard" / "heavy.lock"
    )
    try:
        with ProjectLock(effective_lock_path, "heavy"):
            result = _run_while_locked(
                command,
                cwd=cwd_path,
                config=config,
                launcher=launcher,
                memory_reader=memory_reader,
                tree_rss_reader=tree_rss_reader,
                clock=clock,
                sleeper=sleeper,
                protection_backend=protection_backend,
            )
    except _HeavyResourceLockBusy:
        result = GuardResult("lock-busy", 75, None, 0.0, protection_backend, False)
    except Exception:
        result = GuardResult("protection-failure", 125, None, 0.0, protection_backend, False)
    _write_summary_atomic(summary_path, result)
    return result


def _run_while_locked(
    command: Sequence[str],
    *,
    cwd: Path,
    config: GuardConfig,
    launcher: Callable[..., object],
    memory_reader: Callable[[], MemorySnapshot | float],
    tree_rss_reader: Callable[[int], float] | None,
    clock: Callable[[], float],
    sleeper: Callable[[float], None],
    protection_backend: str,
) -> GuardResult:
    degraded = False
    try:
        memory_value = memory_reader()
        memory = (
            memory_value
            if isinstance(memory_value, MemorySnapshot)
            else MemorySnapshot(float(memory_value), "injected-memory-reader")
        )
    except Exception:
        if not config.allow_degraded:
            return GuardResult("protection-failure", 125, None, 0.0, protection_backend, False)
        degraded = True
        memory = None

    if memory is not None and memory.available_physical_mib < config.min_available_mib:
        return GuardResult("admission-rejected", 75, None, 0.0, protection_backend, degraded)

    if tree_rss_reader is None:
        if not config.allow_degraded:
            return GuardResult("protection-failure", 125, None, 0.0, protection_backend, False)
        degraded = True

    try:
        process = launcher(
            list(command),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except Exception:
        return GuardResult("launch-error", 125, None, 0.0, protection_backend, degraded)

    child_pid = process.pid
    started_at = clock()
    progress = _ProgressTracker(clock, started_at)
    drainers = _start_output_drainers(process, progress)
    peak_rss = 0.0
    rss_enabled = tree_rss_reader is not None

    while True:
        child_exit = process.poll()
        if child_exit is not None:
            _finish_output_drainers(drainers, config.grace_period_s)
            reason = "completed" if child_exit == 0 else "child-exit"
            return GuardResult(reason, child_exit, child_pid, peak_rss, protection_backend, degraded)

        now = clock()
        if now - started_at >= config.wall_timeout_s:
            return _stop_with_result(
                process, drainers, "wall-timeout", 124, child_pid, peak_rss, protection_backend, degraded, config
            )
        if progress.is_idle(now, config.idle_timeout_s):
            return _stop_with_result(
                process, drainers, "idle-timeout", 124, child_pid, peak_rss, protection_backend, degraded, config
            )

        if rss_enabled:
            try:
                current_rss = float(tree_rss_reader(child_pid))
            except Exception:
                if config.allow_degraded:
                    degraded = True
                    rss_enabled = False
                else:
                    return _stop_with_result(
                        process,
                        drainers,
                        "protection-failure",
                        125,
                        child_pid,
                        peak_rss,
                        protection_backend,
                        degraded,
                        config,
                    )
            else:
                peak_rss = max(peak_rss, current_rss)
                if current_rss > config.max_tree_rss_mib:
                    return _stop_with_result(
                        process,
                        drainers,
                        "memory-limit",
                        125,
                        child_pid,
                        peak_rss,
                        protection_backend,
                        degraded,
                        config,
                    )

        sleeper(config.sample_interval_s)


class _ProgressTracker:
    def __init__(self, clock: Callable[[], float], started_at: float):
        self._clock = clock
        self._last_progress = started_at
        self._lock = threading.Lock()

    def record_complete_line(self) -> None:
        observed_at = self._clock()
        with self._lock:
            self._last_progress = max(self._last_progress, observed_at)

    def is_idle(self, now: float, timeout: float) -> bool:
        with self._lock:
            return now - self._last_progress >= timeout


def _start_output_drainers(process, progress: _ProgressTracker) -> list[threading.Thread]:
    threads = []
    for stream in (getattr(process, "stdout", None), getattr(process, "stderr", None)):
        if stream is None:
            continue
        thread = threading.Thread(target=_drain_stream, args=(stream, progress), daemon=True)
        thread.start()
        threads.append(thread)
    return threads


def _drain_stream(stream, progress: _ProgressTracker) -> None:
    try:
        for line in iter(stream.readline, ""):
            if line.endswith("\n"):
                progress.record_complete_line()
    except (OSError, ValueError):
        return


def _finish_output_drainers(threads: Iterable[threading.Thread], timeout: float) -> None:
    for thread in threads:
        thread.join(timeout=max(0.0, timeout))


def _stop_with_result(
    process,
    drainers: Iterable[threading.Thread],
    reason: str,
    exit_code: int,
    child_pid: int,
    peak_rss: float,
    protection_backend: str,
    degraded: bool,
    config: GuardConfig,
) -> GuardResult:
    stopped = _stop_child(process, config.grace_period_s)
    _finish_output_drainers(drainers, config.grace_period_s)
    if not stopped:
        return GuardResult(
            "protection-failure",
            125,
            child_pid,
            peak_rss,
            protection_backend,
            degraded,
        )
    return GuardResult(reason, exit_code, child_pid, peak_rss, protection_backend, degraded)


def _stop_child(process, grace_period_s: float) -> bool:
    timeout = max(0.0, grace_period_s)
    terminate = _bounded_call(process.terminate, timeout)
    if not terminate.completed or terminate.error is not None:
        _report_stop_failure("terminate", terminate)
        if _confirm_stopped(process, timeout, "poll-after-terminate"):
            return True
    else:
        wait_after_terminate = _bounded_call(lambda: process.wait(timeout=timeout), timeout)
        if wait_after_terminate.completed and wait_after_terminate.error is None:
            if _confirm_stopped(process, timeout, "poll-after-terminate-wait"):
                return True
        else:
            _report_stop_failure("graceful-wait", wait_after_terminate)
            if _confirm_stopped(process, timeout, "poll-after-terminate-wait"):
                return True

    kill = _bounded_call(process.kill, timeout)
    if not kill.completed or kill.error is not None:
        _report_stop_failure("kill", kill)
    else:
        wait_after_kill = _bounded_call(lambda: process.wait(timeout=timeout), timeout)
        if not wait_after_kill.completed or wait_after_kill.error is not None:
            _report_stop_failure("final-wait", wait_after_kill)
    return _confirm_stopped(process, timeout, "final-poll")


@dataclass(frozen=True)
class _BoundedCallResult:
    completed: bool
    value: object = None
    error: BaseException | None = None


def _bounded_call(action: Callable[[], object], timeout: float) -> _BoundedCallResult:
    outcomes: queue.Queue[_BoundedCallResult] = queue.Queue(maxsize=1)

    def invoke() -> None:
        try:
            outcomes.put(_BoundedCallResult(True, value=action()))
        except BaseException as error:
            outcomes.put(_BoundedCallResult(True, error=error))

    thread = threading.Thread(target=invoke, daemon=True)
    thread.start()
    thread.join(timeout=max(0.0, timeout))
    if thread.is_alive():
        return _BoundedCallResult(False, error=TimeoutError("bounded process action timed out"))
    return outcomes.get_nowait()


def _confirm_stopped(process, timeout: float, stage: str) -> bool:
    outcome = _bounded_call(process.poll, timeout)
    if not outcome.completed or outcome.error is not None:
        _report_stop_failure(stage, outcome)
        return False
    return outcome.completed and outcome.error is None and outcome.value is not None


def _report_stop_failure(stage: str, outcome: _BoundedCallResult) -> None:
    error = outcome.error or RuntimeError("bounded process action did not complete")
    print(
        f"resource guard stop step {stage} failed: {type(error).__name__}: {error}",
        file=sys.stderr,
        flush=True,
    )


def _write_summary_atomic(path: Path, result: GuardResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


__all__ = [
    "GuardConfig",
    "GuardResult",
    "MemorySnapshot",
    "ProjectLock",
    "available_physical_memory_mib",
    "run_guarded",
]
