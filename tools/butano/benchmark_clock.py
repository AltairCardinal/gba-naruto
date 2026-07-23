#!/usr/bin/env python3
"""Record immutable wall-clock evidence for the Butano agent benchmark."""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_manifest(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"task does not exist: {path.stem}")
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_replace(path: Path, payload: dict) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("x", encoding="utf-8") as output:
        json.dump(payload, output, indent=2, ensure_ascii=False)
        output.write("\n")
    os.replace(temp_path, path)


def start_task(path: Path, task_id: str) -> dict:
    started_ns = time.time_ns()
    payload = {
        "format": "gba-naruto-codex-wall-clock-v1",
        "task_id": task_id,
        "status": "running",
        "started_at": utc_now(),
        "started_unix_ns": started_ns,
        "events": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, ensure_ascii=False)
            output.write("\n")
    except FileExistsError as error:
        raise ValueError(f"task already exists: {task_id}") from error
    return payload


def add_event(path: Path, args: argparse.Namespace) -> dict:
    payload = load_manifest(path)
    if payload["status"] != "running":
        raise ValueError(f"task already finished: {payload['task_id']}")
    payload["events"].append(
        {
            "recorded_at": utc_now(),
            "recorded_unix_ns": time.time_ns(),
            "kind": args.kind,
            "command": args.command,
            "exit_code": args.exit_code,
            "note": args.note,
        }
    )
    atomic_replace(path, payload)
    return payload


def finish_task(path: Path) -> dict:
    payload = load_manifest(path)
    if payload["status"] != "running":
        raise ValueError(f"task already finished: {payload['task_id']}")
    ended_ns = time.time_ns()
    if ended_ns < payload["started_unix_ns"]:
        raise ValueError("wall clock moved backwards")
    payload.update(
        {
            "status": "finished",
            "finished_at": utc_now(),
            "finished_unix_ns": ended_ns,
            "duration_seconds": round(
                (ended_ns - payload["started_unix_ns"]) / 1_000_000_000, 6
            ),
        }
    )
    atomic_replace(path, payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("action", choices=("start", "event", "finish"))
    parser.add_argument("task_id")
    parser.add_argument("--kind")
    parser.add_argument("--command")
    parser.add_argument("--exit-code", type=int)
    parser.add_argument("--note", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    path = args.run_dir / f"{args.task_id}.json"
    try:
        if args.action == "start":
            payload = start_task(path, args.task_id)
        elif args.action == "event":
            if args.kind is None or args.command is None or args.exit_code is None:
                raise ValueError("event requires --kind, --command and --exit-code")
            payload = add_event(path, args)
        else:
            payload = finish_task(path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"benchmark clock error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
