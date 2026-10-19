#!/usr/bin/env python3
"""Run one project-owned command behind the heavy-resource guard."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from tools.mgba_runtime_safety import (
        DEFAULT_CRASH_DIR,
        DEFAULT_LATCH_PATH,
        MgbaSafetyError,
        finish_mgba_launch,
        prepare_mgba_launch,
    )
    from tools.project_resource_guard import GuardConfig, run_guarded
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from mgba_runtime_safety import (
        DEFAULT_CRASH_DIR,
        DEFAULT_LATCH_PATH,
        MgbaSafetyError,
        finish_mgba_launch,
        prepare_mgba_launch,
    )
    from project_resource_guard import GuardConfig, run_guarded


def build_parser() -> argparse.ArgumentParser:
    defaults = GuardConfig()
    parser = argparse.ArgumentParser(
        description="Run one owned process tree with memory and timeout protection."
    )
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--success-marker", type=Path)
    parser.add_argument(
        "--lock-file",
        type=Path,
        default=Path("build/resource-guard/heavy.lock"),
    )
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--min-available-mib", type=int, default=defaults.min_available_mib)
    parser.add_argument("--max-tree-rss-mib", type=int, default=defaults.max_tree_rss_mib)
    parser.add_argument("--wall-timeout-s", type=float, default=defaults.wall_timeout_s)
    parser.add_argument("--idle-timeout-s", type=float, default=defaults.idle_timeout_s)
    parser.add_argument("--sample-interval-s", type=float, default=defaults.sample_interval_s)
    parser.add_argument("--grace-period-s", type=float, default=defaults.grace_period_s)
    parser.add_argument("--allow-degraded", action="store_true")
    parser.add_argument(
        "--mgba-crash-report-dir", type=Path, default=DEFAULT_CRASH_DIR
    )
    parser.add_argument("--mgba-crash-latch", type=Path, default=DEFAULT_LATCH_PATH)
    parser.add_argument("--mgba-crash-baseline", type=Path)
    parser.add_argument("--mgba-crash-settle-s", type=float, default=2.0)
    return parser


def _write_safety_rejection(
    path: Path, command: list[str], cwd: Path, error: MgbaSafetyError
) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "child_pid": None,
        "peak_tree_rss_mib": 0.0,
        "protection_backend": "not-launched",
        "degraded": False,
        "command": command,
        "cwd": str(cwd),
        "started_at": now,
        "finished_at": now,
        "reason": "mgba-safety-rejected",
        "exit_code": 125,
        "safety_error": str(error),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if "--" not in raw_argv:
        parser.error("a literal -- separator is required before the command")
    separator = raw_argv.index("--")
    args = parser.parse_args(raw_argv[:separator])
    command = raw_argv[separator + 1 :]
    if not command:
        parser.error("a command is required after --")

    mgba_state: dict[str, object] = {"audit": None, "exit_code": None, "error": None}

    def locked_preflight() -> None:
        try:
            mgba_state["audit"] = prepare_mgba_launch(
                command,
                crash_dir=args.mgba_crash_report_dir,
                latch_path=args.mgba_crash_latch,
                baseline_path=args.mgba_crash_baseline,
                settle_timeout_s=args.mgba_crash_settle_s,
            )
        except MgbaSafetyError as error:
            mgba_state["error"] = error
            raise

    def locked_postflight(result) -> None:
        try:
            mgba_state["exit_code"] = finish_mgba_launch(
                mgba_state["audit"], args.summary, result.exit_code
            )
        except MgbaSafetyError as error:
            mgba_state["error"] = error
            raise

    config = GuardConfig(
        min_available_mib=args.min_available_mib,
        max_tree_rss_mib=args.max_tree_rss_mib,
        wall_timeout_s=args.wall_timeout_s,
        idle_timeout_s=args.idle_timeout_s,
        sample_interval_s=args.sample_interval_s,
        grace_period_s=args.grace_period_s,
        allow_degraded=args.allow_degraded,
    )
    result = run_guarded(
        command,
        cwd=args.cwd,
        summary_path=args.summary,
        lock_path=args.lock_file,
        config=config,
        success_marker=args.success_marker,
        locked_preflight=locked_preflight,
        locked_postflight=locked_postflight,
    )
    if mgba_state["error"] is not None:
        payload = _write_safety_rejection(
            args.summary, command, args.cwd, mgba_state["error"]
        )
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        return 125
    exit_code = (
        result.exit_code
        if mgba_state["exit_code"] is None
        else int(mgba_state["exit_code"])
    )
    payload = json.loads(args.summary.read_text(encoding="utf-8"))
    print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
