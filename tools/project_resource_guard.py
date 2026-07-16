"""Shared admission and monitoring guard for project-owned heavy tasks."""

from __future__ import annotations

import ctypes
import errno
import json
import os
import queue
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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

    if sys.platform == "darwin":
        completed = subprocess.run(
            ["vm_stat"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = completed.stdout.splitlines()
        marker = "page size of "
        if not lines or marker not in lines[0]:
            raise RuntimeError("vm_stat output has no page size")
        page_size = int(lines[0].split(marker, 1)[1].split()[0])
        available_labels = {"Pages free", "Pages inactive", "Pages speculative"}
        pages = {}
        for line in lines[1:]:
            label, separator, raw_value = line.partition(":")
            if separator and label in available_labels:
                pages[label] = int(raw_value.strip().rstrip("."))
        missing = available_labels.difference(pages)
        if missing:
            raise RuntimeError(
                "vm_stat output is missing available page counters: "
                + ", ".join(sorted(missing))
            )
        available_bytes = sum(pages.values()) * page_size
        return MemorySnapshot(available_bytes / (1024 * 1024), "vm-stat")

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


class _OwnedProcessProtectionError(RuntimeError):
    def __init__(self, message: str, child_pid: int | None, protection_backend: str):
        super().__init__(message)
        self.child_pid = child_pid
        self.protection_backend = protection_backend


class _GuardInterrupted(BaseException):
    def __init__(self, original: BaseException, result: GuardResult):
        super().__init__(str(original))
        self.original = original
        self.result = result


def _platform_backend_name() -> str:
    return "windows-job-object" if os.name == "nt" else "posix-process-group"


def _launch_owned_process(command, **kwargs):
    if os.name == "nt":
        return _launch_windows_owned_process(command, **kwargs)
    return _launch_posix_owned_process(command, **kwargs)


class _PosixOwnedProcess:
    protection_backend = "posix-process-group"

    def __init__(self, process):
        self._process = process
        self.pid = process.pid
        self.stdout = process.stdout
        self.stderr = process.stderr

    def poll(self):
        root_exit = self._process.poll()
        if root_exit is None:
            return None
        try:
            os.killpg(self.pid, 0)
        except ProcessLookupError:
            return root_exit
        except PermissionError:
            return None
        return None

    def wait(self, timeout=None):
        started = time.monotonic()
        root_exit = self._process.wait(timeout=timeout)
        while True:
            try:
                os.killpg(self.pid, 0)
            except ProcessLookupError:
                return root_exit
            except PermissionError:
                pass
            if timeout is not None and time.monotonic() - started >= timeout:
                raise subprocess.TimeoutExpired(self._process.args, timeout)
            time.sleep(0.01)

    def terminate(self):
        try:
            os.killpg(self.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    def kill(self):
        try:
            os.killpg(self.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def tree_rss_mib(self, _root_pid: int) -> float:
        return _posix_descendant_rss_mib(self.pid)

    def close_protection(self) -> None:
        self.kill()


def _launch_posix_owned_process(
    command,
    *,
    cwd,
    launcher=subprocess.Popen,
    **popen_kwargs,
):
    process = launcher(
        list(command),
        cwd=cwd,
        start_new_session=True,
        **popen_kwargs,
    )
    return _PosixOwnedProcess(process)


def _posix_descendant_rss_mib(
    root_pid: int,
    *,
    proc_root: Path = Path("/proc"),
    page_size: int | None = None,
) -> float:
    if sys.platform == "darwin" and proc_root == Path("/proc"):
        return _darwin_process_group_rss_mib(root_pid)

    parents: dict[int, int] = {}
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text(encoding="ascii")
            fields = stat[stat.rfind(")") + 1 :].split()
            parents[int(entry.name)] = int(fields[1])
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError, IndexError):
            continue

    descendants = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, parent_pid in parents.items():
            if parent_pid in descendants and pid not in descendants:
                descendants.add(pid)
                changed = True

    resident_pages = 0
    for pid in descendants:
        try:
            fields = (proc_root / str(pid) / "statm").read_text(encoding="ascii").split()
            resident_pages += int(fields[1])
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError, IndexError):
            continue
    effective_page_size = page_size if page_size is not None else os.sysconf("SC_PAGE_SIZE")
    return resident_pages * effective_page_size / (1024 * 1024)


def _darwin_process_group_rss_mib(process_group_id: int) -> float:
    completed = subprocess.run(
        ["ps", "-axo", "pid=,pgid=,rss="],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    owned_resident_kib = []
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) != 3:
            continue
        try:
            pid, candidate_group_id, rss_kib = (int(field) for field in fields)
        except ValueError:
            continue
        if pid <= 0 or candidate_group_id <= 0 or rss_kib < 0:
            continue
        if candidate_group_id == process_group_id:
            owned_resident_kib.append(rss_kib)
    if not owned_resident_kib:
        raise RuntimeError("ps output has no owned process group")
    return sum(owned_resident_kib) / 1024


class _WinIoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _WinBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _WinExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _WinBasicLimitInformation),
        ("IoInfo", _WinIoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _WinBasicAccountingInformation(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_longlong),
        ("TotalKernelTime", ctypes.c_longlong),
        ("ThisPeriodTotalUserTime", ctypes.c_longlong),
        ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
        ("TotalPageFaultCount", ctypes.c_uint32),
        ("TotalProcesses", ctypes.c_uint32),
        ("ActiveProcesses", ctypes.c_uint32),
        ("TotalTerminatedProcesses", ctypes.c_uint32),
    ]


def _windows_api(name, argtypes, restype):
    function = getattr(ctypes.WinDLL("kernel32", use_last_error=True), name)
    function.argtypes = argtypes
    function.restype = restype
    return function


def _windows_create_job() -> int:
    create_job = _windows_api(
        "CreateJobObjectW",
        [ctypes.c_void_p, ctypes.c_wchar_p],
        ctypes.c_void_p,
    )
    job = create_job(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    information = _WinExtendedLimitInformation()
    information.BasicLimitInformation.LimitFlags = 0x00002000
    set_information = _windows_api(
        "SetInformationJobObject",
        [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32],
        ctypes.c_int,
    )
    if not set_information(job, 9, ctypes.byref(information), ctypes.sizeof(information)):
        error = ctypes.WinError(ctypes.get_last_error())
        _windows_close_handle(job)
        raise error
    return job


def _windows_assign_process(job: int, process_handle: int) -> None:
    assign = _windows_api(
        "AssignProcessToJobObject",
        [ctypes.c_void_p, ctypes.c_void_p],
        ctypes.c_int,
    )
    if not assign(job, process_handle):
        raise ctypes.WinError(ctypes.get_last_error())


def _windows_resume_process(process_handle: int) -> None:
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    resume = ntdll.NtResumeProcess
    resume.argtypes = [ctypes.c_void_p]
    resume.restype = ctypes.c_long
    status = resume(process_handle)
    if status != 0:
        raise OSError(status, "NtResumeProcess failed")


def _windows_terminate_job(job: int, exit_code: int = 1) -> None:
    terminate = _windows_api(
        "TerminateJobObject",
        [ctypes.c_void_p, ctypes.c_uint32],
        ctypes.c_int,
    )
    if not terminate(job, exit_code):
        raise ctypes.WinError(ctypes.get_last_error())


def _windows_close_handle(handle: int) -> None:
    close = _windows_api("CloseHandle", [ctypes.c_void_p], ctypes.c_int)
    if not close(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def _windows_query_job(job: int, information_class: int, structure):
    query = _windows_api(
        "QueryInformationJobObject",
        [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p],
        ctypes.c_int,
    )
    if not query(job, information_class, ctypes.byref(structure), ctypes.sizeof(structure), None):
        raise ctypes.WinError(ctypes.get_last_error())
    return structure


class _WindowsJobOwnedProcess:
    protection_backend = "windows-job-object"

    def __init__(self, process, job: int):
        self._process = process
        self._job = job
        self.pid = process.pid
        self.stdout = process.stdout
        self.stderr = process.stderr

    def poll(self):
        root_exit = self._process.poll()
        accounting = _windows_query_job(self._job, 1, _WinBasicAccountingInformation())
        if accounting.ActiveProcesses:
            return None
        if root_exit is None:
            try:
                root_exit = self._process.wait(timeout=0)
            except subprocess.TimeoutExpired:
                return None
        return root_exit

    def wait(self, timeout=None):
        started = time.monotonic()
        while True:
            accounting = _windows_query_job(self._job, 1, _WinBasicAccountingInformation())
            if not accounting.ActiveProcesses:
                remaining = None
                if timeout is not None:
                    remaining = max(0.0, timeout - (time.monotonic() - started))
                return self._process.wait(timeout=remaining)
            if timeout is not None and time.monotonic() - started >= timeout:
                raise subprocess.TimeoutExpired(self._process.args, timeout)
            time.sleep(0.01)

    def terminate(self):
        _windows_terminate_job(self._job)

    def kill(self):
        _windows_terminate_job(self._job)

    def tree_rss_mib(self, _root_pid: int) -> float:
        information = _windows_query_job(self._job, 9, _WinExtendedLimitInformation())
        return information.PeakJobMemoryUsed / (1024 * 1024)

    def close_protection(self) -> None:
        if self._job is None:
            return
        job = self._job
        self._job = None
        _windows_close_handle(job)


def _cleanup_windows_launch_failure(process, job: int, assigned: bool) -> None:
    errors = []
    try:
        for attempt in range(2):
            try:
                if assigned:
                    _windows_terminate_job(job, 125)
                else:
                    process.kill()
                process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired) as error:
                errors.append(f"attempt {attempt + 1}: {type(error).__name__}: {error}")
            try:
                if process.poll() is not None:
                    return
            except OSError as error:
                errors.append(f"poll: {type(error).__name__}: {error}")
    finally:
        _close_process_streams(process)
    detail = "; ".join(errors) or "child remained active after exact-handle cleanup"
    raise RuntimeError(f"exact child PID {process.pid} cleanup could not be confirmed: {detail}")


def _launch_windows_owned_process(
    command,
    *,
    cwd,
    launcher=subprocess.Popen,
    **popen_kwargs,
):
    backend = "windows-job-object"
    try:
        job = _windows_create_job()
    except Exception as error:
        raise _OwnedProcessProtectionError(str(error), None, backend) from error

    creationflags = popen_kwargs.pop("creationflags", 0) | getattr(
        subprocess, "CREATE_SUSPENDED", 0x00000004
    )
    try:
        process = launcher(
            list(command),
            cwd=cwd,
            creationflags=creationflags,
            **popen_kwargs,
        )
    except Exception:
        _windows_close_handle(job)
        raise

    assigned = False
    try:
        _windows_assign_process(job, int(process._handle))
        assigned = True
        _windows_resume_process(int(process._handle))
    except Exception as error:
        cleanup_error = None
        close_error = None
        try:
            _cleanup_windows_launch_failure(process, job, assigned)
        except Exception as caught:
            cleanup_error = caught
        try:
            _windows_close_handle(job)
        except Exception as caught:
            close_error = caught
        details = [str(error)]
        if cleanup_error is not None:
            details.append(str(cleanup_error))
        if close_error is not None:
            details.append(f"job close failed: {close_error}")
        raise _OwnedProcessProtectionError("; ".join(details), process.pid, backend) from error
    return _WindowsJobOwnedProcess(process, job)


def run_guarded(
    command: Sequence[str],
    *,
    cwd: str | Path | None = None,
    summary_path: str | Path,
    config: GuardConfig = GuardConfig(),
    lock_path: str | Path | None = None,
    launcher: Callable[..., object] | None = None,
    memory_reader: Callable[[], MemorySnapshot | float] = available_physical_memory_mib,
    tree_rss_reader: Callable[[int], float] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    protection_backend: str | None = None,
    success_marker: str | Path | None = None,
) -> GuardResult:
    """Run one owned child under lock, admission, and resource monitoring."""

    summary_path = Path(summary_path)
    cwd_path = Path.cwd() if cwd is None else Path(cwd)
    owned_tree = launcher is None
    effective_launcher = _launch_owned_process if owned_tree else launcher
    effective_backend = protection_backend or _platform_backend_name()
    success_marker_path = None if success_marker is None else Path(success_marker)
    started_at = _utc_timestamp()
    summary_state = {"written": False, "result": None}
    completion_state = {"trigger": None}

    def write_summary(result: GuardResult) -> None:
        metadata = {
            "command": list(command),
            "cwd": str(cwd_path.resolve()),
            "started_at": started_at,
            "finished_at": _utc_timestamp(),
        }
        if (
            completion_state["trigger"] is not None
            and result.reason == "completed"
            and result.exit_code == 0
        ):
            metadata["completion_trigger"] = completion_state["trigger"]
        _write_summary_atomic(summary_path, result, metadata)
        summary_state["written"] = True
        summary_state["result"] = result

    effective_lock_path = (
        Path(lock_path)
        if lock_path is not None
        else cwd_path / "build" / "resource-guard" / "heavy.lock"
    )
    fatal_error = None
    try:
        with ProjectLock(effective_lock_path, "heavy"):
            try:
                result = _run_while_locked(
                    command,
                    cwd=cwd_path,
                    config=config,
                    launcher=effective_launcher,
                    memory_reader=memory_reader,
                    tree_rss_reader=tree_rss_reader,
                    clock=clock,
                    sleeper=sleeper,
                    protection_backend=effective_backend,
                    owned_tree=owned_tree,
                    summary_writer=write_summary,
                    success_marker=success_marker_path,
                    completion_state=completion_state,
                )
            except _GuardInterrupted as interrupted:
                result = interrupted.result
                fatal_error = interrupted.original
            except BaseException as error:
                result = GuardResult(
                    "protection-failure", 125, None, 0.0, effective_backend, False
                )
                if not isinstance(error, Exception):
                    fatal_error = error
            if not summary_state["written"] or summary_state["result"] != result:
                write_summary(result)
    except _HeavyResourceLockBusy:
        result = GuardResult("lock-busy", 75, None, 0.0, effective_backend, False)
        write_summary(result)
    except BaseException as error:
        result = GuardResult("protection-failure", 125, None, 0.0, effective_backend, False)
        if not summary_state["written"] or summary_state["result"] != result:
            write_summary(result)
        if not isinstance(error, Exception):
            fatal_error = error
    if fatal_error is not None:
        raise fatal_error
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
    owned_tree: bool,
    summary_writer: Callable[[GuardResult], None],
    success_marker: Path | None,
    completion_state: dict[str, str | None],
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

    if tree_rss_reader is None and not owned_tree:
        if not config.allow_degraded:
            return GuardResult("protection-failure", 125, None, 0.0, protection_backend, False)
        degraded = True

    if success_marker is not None and os.path.lexists(success_marker):
        return GuardResult("protection-failure", 125, None, 0.0, protection_backend, degraded)

    try:
        process = launcher(
            list(command),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except _OwnedProcessProtectionError as error:
        _best_effort_stderr(
            f"resource guard ownership setup failed for child PID "
            f"{error.child_pid}: {error}"
        )
        return GuardResult(
            "protection-failure",
            125,
            error.child_pid,
            0.0,
            error.protection_backend,
            False,
        )
    except Exception:
        return GuardResult("launch-error", 125, None, 0.0, protection_backend, degraded)

    child_pid = process.pid
    if owned_tree:
        protection_backend = process.protection_backend
        tree_rss_reader = process.tree_rss_mib
    result = None
    monitor_error = None
    try:
        result = _monitor_started_process(
            process,
            child_pid=child_pid,
            config=config,
            tree_rss_reader=tree_rss_reader,
            clock=clock,
            sleeper=sleeper,
            protection_backend=protection_backend,
            degraded=degraded,
            success_marker=success_marker,
            completion_state=completion_state,
        )
    except BaseException as error:
        monitor_error = error
        result = GuardResult(
            "protection-failure", 125, child_pid, 0.0, protection_backend, degraded
        )

    shutdown_ok = _ensure_owned_tree_stopped(
        process, max(0.0, config.grace_period_s)
    )
    streams_closed = _bounded_call(
        lambda: _close_process_streams(process), max(0.0, config.grace_period_s)
    )
    if not streams_closed.completed or streams_closed.error is not None:
        _report_stop_failure("close-streams", streams_closed)
        shutdown_ok = False
    if not shutdown_ok:
        result = GuardResult(
            "protection-failure",
            125,
            child_pid,
            result.peak_tree_rss_mib,
            protection_backend,
            result.degraded,
        )

    summary_error = None
    try:
        summary_writer(result)
    except BaseException as error:
        summary_error = error
    protection_closed = _close_owned_protection_handle(
        process, max(0.0, config.grace_period_s)
    )
    if not protection_closed:
        result = GuardResult(
            "protection-failure",
            125,
            child_pid,
            result.peak_tree_rss_mib,
            protection_backend,
            result.degraded,
        )
        if summary_error is None:
            summary_writer(result)
    if summary_error is not None:
        if isinstance(summary_error, Exception):
            raise summary_error
        raise _GuardInterrupted(summary_error, result)
    if monitor_error is not None:
        if isinstance(monitor_error, Exception):
            return result
        raise _GuardInterrupted(monitor_error, result)
    return result


def _ensure_owned_tree_stopped(process, timeout: float) -> bool:
    confirmed_stopped = False
    initial_poll = _bounded_call(process.poll, timeout)
    if initial_poll.completed and initial_poll.error is None:
        confirmed_stopped = initial_poll.value is not None
    else:
        _report_stop_failure("protection-poll", initial_poll)

    if not confirmed_stopped:
        killed = _bounded_call(process.kill, timeout)
        if not killed.completed or killed.error is not None:
            _report_stop_failure("protection-kill", killed)
        waited = _bounded_call(lambda: process.wait(timeout=timeout), timeout)
        if not waited.completed or waited.error is not None:
            _report_stop_failure("protection-wait", waited)
        final_poll = _bounded_call(process.poll, timeout)
        if not final_poll.completed or final_poll.error is not None:
            _report_stop_failure("protection-final-poll", final_poll)
        else:
            confirmed_stopped = final_poll.value is not None

    return confirmed_stopped


def _close_owned_protection_handle(process, timeout: float) -> bool:
    close_protection = getattr(process, "close_protection", None)
    if close_protection is None:
        return True
    closed = _bounded_call(close_protection, timeout)
    if not closed.completed or closed.error is not None:
        _report_stop_failure("close-protection", closed)
        return False
    return True


def _close_process_streams(process) -> None:
    for stream in (getattr(process, "stdout", None), getattr(process, "stderr", None)):
        close = getattr(stream, "close", None)
        if close is None:
            continue
        try:
            close()
        except (OSError, ValueError):
            pass


def _monitor_started_process(
    process,
    *,
    child_pid: int,
    config: GuardConfig,
    tree_rss_reader: Callable[[int], float] | None,
    clock: Callable[[], float],
    sleeper: Callable[[float], None],
    protection_backend: str,
    degraded: bool,
    success_marker: Path | None,
    completion_state: dict[str, str | None],
) -> GuardResult:
    started_at = clock()
    progress = _ProgressTracker(clock, started_at)
    drainers = _start_output_drainers(process, progress)
    peak_rss = 0.0
    rss_enabled = tree_rss_reader is not None

    while True:
        try:
            child_exit = process.poll()
        except Exception:
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
        if child_exit is not None:
            _finish_output_drainers(drainers, config.grace_period_s)
            reason = "completed" if child_exit == 0 else "child-exit"
            return GuardResult(reason, child_exit, child_pid, peak_rss, protection_backend, degraded)

        if success_marker is not None:
            try:
                marker_ready = stat.S_ISREG(success_marker.lstat().st_mode)
            except FileNotFoundError:
                marker_ready = False
            except OSError:
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
            if marker_ready:
                completion_state["trigger"] = "success-marker"
                return _stop_with_result(
                    process,
                    drainers,
                    "completed",
                    0,
                    child_pid,
                    peak_rss,
                    protection_backend,
                    degraded,
                    config,
                )

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
    _best_effort_stderr(
        f"resource guard stop step {stage} failed: {type(error).__name__}: {error}"
    )


def _best_effort_stderr(message: str) -> None:
    try:
        print(message, file=sys.stderr, flush=True)
    except Exception:
        pass


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_summary_atomic(path: Path, result: GuardResult, metadata=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    payload = asdict(result)
    if metadata:
        payload.update(metadata)
    try:
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
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
