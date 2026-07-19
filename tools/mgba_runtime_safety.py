#!/usr/bin/env python3
"""Fail-closed launch policy and crash latch for guarded mGBA runs."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


DEFAULT_CRASH_DIR = Path.home() / "Library" / "Logs" / "DiagnosticReports"
DEFAULT_LATCH_PATH = (
    Path(__file__).resolve().parents[1]
    / "build"
    / "resource-guard"
    / "mgba-crash-latch.json"
)
DEFAULT_BASELINE_PATH = DEFAULT_LATCH_PATH.with_name("mgba-crash-baseline.json")
CRASH_EXIT_CODE = 125
_DANGEROUS_LUA = (
    re.compile(
        r"\bos\s*(?:\.\s*|\[\s*['\"])(?:exit|execute)(?:['\"]\s*\])?\s*\(?",
        re.IGNORECASE,
    ),
    re.compile(r"\bffi\s*\.\s*C\s*\.\s*(?:exit|abort|kill)\s*\(", re.IGNORECASE),
    re.compile(r"\bposix\s*\.\s*(?:exit|abort|kill)\s*\(", re.IGNORECASE),
    re.compile(r"\b(?:_G|_ENV|getfenv|setfenv|rawget|load|loadstring|dofile|require|package|debug)\b"),
    re.compile(r"\bio\s*(?:\.\s*|\[\s*['\"])popen\b", re.IGNORECASE),
)
_SAFE_GLOBAL_ACCESS = (
    re.compile(r"\bos\s*\.\s*getenv\s*\(", re.IGNORECASE),
    re.compile(r"\bio\s*\.\s*open\s*\(", re.IGNORECASE),
)
_SENSITIVE_GLOBAL = re.compile(r"\b(?:os|io|ffi|posix)\b", re.IGNORECASE)


class MgbaSafetyError(RuntimeError):
    """An mGBA launch cannot be proven safe."""


@dataclass(frozen=True)
class LaunchAudit:
    command: tuple[str, ...]
    crash_dir: Path
    latch_path: Path
    baseline_path: Path
    crash_reports_before: Mapping[str, tuple[int, int]]
    settle_timeout_s: float


def _is_mgba_command(command: Sequence[str]) -> bool:
    if not command:
        return False
    executable = Path(str(command[0])).name.casefold()
    return executable == "mgba" or executable.startswith("mgba-")


def _script_paths(command: Sequence[str]) -> list[Path]:
    scripts: list[Path] = []
    index = 1
    while index < len(command):
        argument = str(command[index])
        if argument == "--script":
            if index + 1 >= len(command):
                raise MgbaSafetyError("mGBA --script is missing its path")
            scripts.append(Path(str(command[index + 1])))
            index += 2
            continue
        if argument.startswith("--script="):
            value = argument.partition("=")[2]
            if not value:
                raise MgbaSafetyError("mGBA --script is missing its path")
            scripts.append(Path(value))
        index += 1
    return scripts


def _validate_lua_script(path: Path) -> None:
    try:
        resolved = path.expanduser().resolve(strict=True)
        if not resolved.is_file():
            raise MgbaSafetyError(f"mGBA Lua is not a regular file: {resolved}")
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise MgbaSafetyError(f"cannot inspect mGBA Lua {path}: {error}") from error
    for pattern in _DANGEROUS_LUA:
        if pattern.search(text):
            raise MgbaSafetyError(f"dangerous Lua process termination in {resolved}")
    without_safe_access = text
    for safe_access in _SAFE_GLOBAL_ACCESS:
        without_safe_access = safe_access.sub("", without_safe_access)
    if _SENSITIVE_GLOBAL.search(without_safe_access):
        raise MgbaSafetyError(f"dangerous Lua process termination in {resolved}")


def _snapshot_crash_reports(crash_dir: Path) -> dict[str, tuple[int, int]]:
    directory = crash_dir.expanduser()
    if not directory.exists():
        return {}
    if not directory.is_dir():
        raise MgbaSafetyError(f"mGBA crash report path is not a directory: {directory}")
    snapshot: dict[str, tuple[int, int]] = {}
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                if not entry.name.startswith("mGBA-") or not entry.name.endswith(".ips"):
                    continue
                stat_result = entry.stat(follow_symlinks=False)
                if not entry.is_file(follow_symlinks=False):
                    continue
                path = Path(entry.path).resolve()
                snapshot[str(path)] = (stat_result.st_mtime_ns, stat_result.st_size)
    except OSError as error:
        raise MgbaSafetyError(f"cannot inspect mGBA crash reports: {error}") from error
    return snapshot


def _load_object(path: Path, label: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise MgbaSafetyError(f"invalid {label} {path}: {error}") from error
    if not isinstance(payload, dict):
        raise MgbaSafetyError(f"invalid {label} {path}: expected JSON object")
    return payload


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise MgbaSafetyError(f"cannot write mGBA safety state {path}: {error}") from error


def _baseline_payload(snapshot: Mapping[str, tuple[int, int]]) -> dict[str, object]:
    return {
        "format": "gba-naruto-mgba-crash-baseline-v1",
        "reports": {
            path: {"mtime_ns": metadata[0], "size": metadata[1]}
            for path, metadata in sorted(snapshot.items())
        },
    }


def _load_baseline(path: Path) -> dict[str, tuple[int, int]]:
    payload = _load_object(path, "mGBA crash baseline")
    reports = payload.get("reports")
    if not isinstance(reports, dict):
        raise MgbaSafetyError(f"invalid mGBA crash baseline {path}: expected reports object")
    parsed: dict[str, tuple[int, int]] = {}
    for report, metadata in reports.items():
        if not isinstance(report, str) or not isinstance(metadata, dict):
            raise MgbaSafetyError(f"invalid mGBA crash baseline {path}: invalid report")
        mtime_ns, size = metadata.get("mtime_ns"), metadata.get("size")
        if not isinstance(mtime_ns, int) or not isinstance(size, int):
            raise MgbaSafetyError(f"invalid mGBA crash baseline {path}: invalid metadata")
        parsed[report] = (mtime_ns, size)
    return parsed


def _report_records(
    current: Mapping[str, tuple[int, int]], baseline: Mapping[str, tuple[int, int]]
) -> list[dict[str, object]]:
    return [
        {"path": path, "mtime_ns": metadata[0], "size": metadata[1]}
        for path, metadata in sorted(current.items())
        if baseline.get(path) != metadata
    ]


def _write_latch(path: Path, command: Sequence[str], reports: list[dict[str, object]]) -> None:
    _write_json_atomic(
        path,
        {
            "format": "gba-naruto-mgba-crash-latch-v1",
            "reason": "mgba-crash-report",
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "command": list(command),
            "reports": reports,
        },
    )


def prepare_mgba_launch(
    command: Sequence[str],
    crash_dir: Path = DEFAULT_CRASH_DIR,
    latch_path: Path = DEFAULT_LATCH_PATH,
    baseline_path: Path | None = None,
    *,
    settle_timeout_s: float = 2.0,
) -> LaunchAudit | None:
    """Validate an mGBA command and snapshot crash state before launch."""
    if not _is_mgba_command(command):
        return None
    if settle_timeout_s < 0:
        raise MgbaSafetyError("mGBA crash-report settle timeout must be non-negative")
    latch = latch_path.expanduser().resolve(strict=False)
    baseline = (
        baseline_path.expanduser().resolve(strict=False)
        if baseline_path is not None
        else latch.with_name("mgba-crash-baseline.json")
    )
    if latch.exists():
        previous = _load_object(latch, "mGBA crash latch")
        raise MgbaSafetyError(
            f"mGBA launch is latched after an unacknowledged crash: {previous.get('reason')}"
        )
    for script in _script_paths(command):
        _validate_lua_script(script)
    directory = crash_dir.expanduser().resolve(strict=False)
    current = _snapshot_crash_reports(directory)
    if baseline.exists():
        unacknowledged = _report_records(current, _load_baseline(baseline))
        if unacknowledged:
            _write_latch(latch, command, unacknowledged)
            raise MgbaSafetyError("unacknowledged mGBA crash report appeared after the previous run")
    else:
        _write_json_atomic(baseline, _baseline_payload(current))
    return LaunchAudit(
        tuple(map(str, command)),
        directory,
        latch,
        baseline,
        current,
        float(settle_timeout_s),
    )


def _new_reports(audit: LaunchAudit) -> list[dict[str, object]]:
    current = _snapshot_crash_reports(audit.crash_dir)
    return _report_records(current, audit.crash_reports_before)


def finish_mgba_launch(
    audit: LaunchAudit | None, summary_path: Path, exit_code: int
) -> int:
    """Turn a newly reported mGBA crash into a latched guard failure."""
    if audit is None:
        return exit_code
    deadline = time.monotonic() + audit.settle_timeout_s
    reports = _new_reports(audit)
    while not reports and time.monotonic() < deadline:
        time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
        reports = _new_reports(audit)
    if not reports:
        _write_json_atomic(
            audit.baseline_path,
            _baseline_payload(_snapshot_crash_reports(audit.crash_dir)),
        )
        return exit_code

    _write_latch(audit.latch_path, audit.command, reports)

    summary = _load_object(summary_path, "resource guard summary")
    summary["pre_crash_reason"] = summary.get("reason")
    summary["pre_crash_exit_code"] = summary.get("exit_code")
    summary["reason"] = "mgba-crash-report"
    summary["exit_code"] = CRASH_EXIT_CODE
    summary["mgba_crash_reports"] = reports
    summary["mgba_crash_latch"] = str(audit.latch_path)
    _write_json_atomic(summary_path, summary)
    return CRASH_EXIT_CODE


def clear_crash_latch(
    latch_path: Path = DEFAULT_LATCH_PATH,
    crash_dir: Path = DEFAULT_CRASH_DIR,
    baseline_path: Path | None = None,
) -> None:
    """Explicitly acknowledge a crash latch while retaining an audit event."""
    latch = latch_path.expanduser().resolve(strict=False)
    if not latch.exists():
        raise MgbaSafetyError(f"mGBA crash latch does not exist: {latch}")
    previous = _load_object(latch, "mGBA crash latch")
    event = {
        "format": "gba-naruto-mgba-crash-latch-history-v1",
        "action": "clear",
        "cleared_at": datetime.now(timezone.utc).isoformat(),
        "previous": previous,
        "crash_reports_at_clear": [
            {"path": path, "mtime_ns": metadata[0], "size": metadata[1]}
            for path, metadata in sorted(
                _snapshot_crash_reports(crash_dir).items()
            )
        ],
    }
    history = Path(f"{latch}.history.jsonl")
    history.parent.mkdir(parents=True, exist_ok=True)
    with history.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
    baseline = (
        baseline_path.expanduser().resolve(strict=False)
        if baseline_path is not None
        else latch.with_name("mgba-crash-baseline.json")
    )
    _write_json_atomic(baseline, _baseline_payload(_snapshot_crash_reports(crash_dir)))
    latch.unlink()
