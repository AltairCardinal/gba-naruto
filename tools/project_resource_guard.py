"""Shared admission and monitoring guard for project-owned heavy tasks."""

from __future__ import annotations

import ctypes
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

    def __init__(self, path: str | Path):
        self.path = Path(path)
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
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as error:
            lock_file.close()
            raise BlockingIOError("heavy resource lock is busy") from error
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
    lock_path: str | Path,
    summary_path: str | Path,
    config: GuardConfig = GuardConfig(),
    launcher: Callable[..., object] = subprocess.Popen,
    memory_reader: Callable[[], MemorySnapshot] = available_physical_memory_mib,
    tree_rss_reader: Callable[[int], float],
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    protection_backend: str = "process-tree-rss",
) -> GuardResult:
    """Run one owned child under lock, admission, and resource monitoring."""

    summary_path = Path(summary_path)
    result: GuardResult
    try:
        with ProjectLock(lock_path):
            result = _run_while_locked(
                command,
                config=config,
                launcher=launcher,
                memory_reader=memory_reader,
                tree_rss_reader=tree_rss_reader,
                clock=clock,
                sleeper=sleeper,
                protection_backend=protection_backend,
            )
    except BlockingIOError:
        result = GuardResult("lock-busy", 75, None, 0.0, protection_backend, False)
    _write_summary_atomic(summary_path, result)
    return result


def _run_while_locked(
    command: Sequence[str],
    *,
    config: GuardConfig,
    launcher: Callable[..., object],
    memory_reader: Callable[[], MemorySnapshot],
    tree_rss_reader: Callable[[int], float],
    clock: Callable[[], float],
    sleeper: Callable[[float], None],
    protection_backend: str,
) -> GuardResult:
    degraded = False
    try:
        memory = memory_reader()
    except Exception:
        if not config.allow_degraded:
            return GuardResult("protection-failure", 125, None, 0.0, protection_backend, False)
        degraded = True
        memory = None

    if memory is not None and memory.available_physical_mib < config.min_available_mib:
        return GuardResult("admission-rejected", 75, None, 0.0, protection_backend, degraded)

    try:
        process = launcher(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except Exception:
        return GuardResult("launch-error", 125, None, 0.0, protection_backend, degraded)

    child_pid = process.pid
    progress = queue.SimpleQueue()
    drainers = _start_output_drainers(process, progress)
    started_at = clock()
    last_progress = started_at
    peak_rss = 0.0
    rss_enabled = True

    while True:
        if _discard_progress(progress):
            last_progress = clock()

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
        if now - last_progress >= config.idle_timeout_s:
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


def _start_output_drainers(process, progress: queue.SimpleQueue) -> list[threading.Thread]:
    threads = []
    for stream in (getattr(process, "stdout", None), getattr(process, "stderr", None)):
        if stream is None:
            continue
        thread = threading.Thread(target=_drain_stream, args=(stream, progress), daemon=True)
        thread.start()
        threads.append(thread)
    return threads


def _drain_stream(stream, progress: queue.SimpleQueue) -> None:
    try:
        for line in iter(stream.readline, ""):
            if line.endswith("\n"):
                progress.put(None)
    except (OSError, ValueError):
        return


def _discard_progress(progress: queue.SimpleQueue) -> bool:
    found = False
    while True:
        try:
            progress.get_nowait()
            found = True
        except queue.Empty:
            return found


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
    _stop_child(process, config.grace_period_s)
    _finish_output_drainers(drainers, config.grace_period_s)
    return GuardResult(reason, exit_code, child_pid, peak_rss, protection_backend, degraded)


def _stop_child(process, grace_period_s: float) -> None:
    try:
        process.terminate()
        process.wait(timeout=max(0.0, grace_period_s))
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    except (OSError, ProcessLookupError):
        return


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
