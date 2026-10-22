#!/usr/bin/env python3
"""Read-only, fail-closed checks for an owned mGBA PGID and listeners."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from typing import Any


PS_COMMAND = ["ps", "-axo", "pid=,pgid=,comm="]
LSOF_COMMAND = [
    "lsof",
    "-nP",
    "-iTCP",
    "-sTCP:LISTEN",
    "-a",
    "-c",
    "mGBA",
    "-Fpcn",
]


class RuntimeResidueError(ValueError):
    """A residue probe was unavailable, malformed, or found owned runtime state."""


def _valid_pgid(pgid: Any) -> bool:
    return isinstance(pgid, int) and not isinstance(pgid, bool) and pgid > 0


def validate_runtime_residue(
    pgid: int, ps_output: str, lsof_output: str, *, lsof_exit_code: int
) -> dict[str, object]:
    if not _valid_pgid(pgid):
        raise RuntimeResidueError("owned PGID must be a positive integer")

    matching_rows: list[str] = []
    for line in ps_output.splitlines():
        if not line.strip():
            continue
        columns = line.split(maxsplit=2)
        if len(columns) < 2:
            raise RuntimeResidueError(f"ps output is malformed: {line!r}")
        try:
            pid, row_pgid = int(columns[0]), int(columns[1])
        except ValueError as error:
            raise RuntimeResidueError(f"ps output is malformed: {line!r}") from error
        if pid <= 0 or row_pgid <= 0:
            raise RuntimeResidueError(f"ps output is malformed: {line!r}")
        if row_pgid == pgid:
            matching_rows.append(line.strip())
    if matching_rows:
        raise RuntimeResidueError(f"PGID {pgid} still has residual processes")

    if lsof_exit_code not in (0, 1):
        raise RuntimeResidueError(f"lsof failed with exit code {lsof_exit_code}")
    listener_rows = [line.strip() for line in lsof_output.splitlines() if line.strip()]
    if listener_rows or lsof_exit_code != 1:
        raise RuntimeResidueError("mGBA listener residue detected")

    return {
        "checked_pgid": pgid,
        "pgid_clean": True,
        "pgid_matching_rows": [],
        "mgba_listener_clean": True,
        "mgba_listener_rows": [],
        "ps_command": list(PS_COMMAND),
        "lsof_command": list(LSOF_COMMAND),
        "lsof_exit_code": lsof_exit_code,
    }


def _run_probe(command: list[str], label: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeResidueError(f"{label} query failed: {error}") from error


def probe_runtime_residue(pgid: int) -> dict[str, object]:
    if not _valid_pgid(pgid):
        raise RuntimeResidueError("owned PGID must be a positive integer")
    ps_result = _run_probe(PS_COMMAND, "ps")
    if ps_result.returncode != 0:
        raise RuntimeResidueError(
            f"ps query failed with exit code {ps_result.returncode}: {ps_result.stderr.strip()}"
        )
    lsof_result = _run_probe(LSOF_COMMAND, "lsof")
    residue = validate_runtime_residue(
        pgid,
        ps_result.stdout,
        lsof_result.stdout or lsof_result.stderr,
        lsof_exit_code=lsof_result.returncode,
    )
    residue["checked_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return residue
