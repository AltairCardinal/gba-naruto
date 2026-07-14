#!/usr/bin/env python3
"""Run one project-owned command behind the heavy-resource guard."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from tools.project_resource_guard import GuardConfig, run_guarded
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from project_resource_guard import GuardConfig, run_guarded


def build_parser() -> argparse.ArgumentParser:
    defaults = GuardConfig()
    parser = argparse.ArgumentParser(
        description="Run one owned process tree with memory and timeout protection."
    )
    parser.add_argument("--summary", required=True, type=Path)
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
    return parser


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
    )
    payload = json.loads(args.summary.read_text(encoding="utf-8"))
    print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
