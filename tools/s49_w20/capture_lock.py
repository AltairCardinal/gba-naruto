#!/usr/bin/env python3
"""Global capture lock for the S49 lanes.

Why: the mGBA recorder eats 7-8 GB and leaks ~10 MB/s.  With 32.5 GB of RAM
and ~7 GB free, **only one long recording may run on the whole machine at a
time**.  Four lanes working in parallel would otherwise OOM each other and
produce truncated captures that look like product defects.

Usage (from the master repo root)::

    python tools/s49_w20/capture_lock.py --run -- <command> [args...]
    python tools/s49_w20/capture_lock.py --status
    python tools/s49_w20/capture_lock.py --release

The lock is a directory-based mutex (``<lockdir>/owner.json``).  It is
**stale-safe**: if the owner file is older than ``--stale-seconds`` (default
5400) the lock is considered abandoned and is taken over automatically, so a
killed lane cannot wedge the others.

Exit codes: 0 = the command ran; 2 = could not acquire the lock (another
capture is running); the command's own exit code is propagated otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
LOCK_DIR = REPO / "build" / ".capture-lock"
OWNER = LOCK_DIR / "owner.json"


def _read_owner() -> dict | None:
    try:
        return json.loads(OWNER.read_text(encoding="utf-8"))
    except Exception:
        return None


def _lock_is_stale(age_seconds: int) -> bool:
    owner = _read_owner()
    if owner is None:
        # No owner file at all: either the lock was never taken, or the owner
        # died between mkdir and write.  Treat "no owner but lock dir exists"
        # as stale only after the directory itself has aged past the limit.
        try:
            age = time.time() - LOCK_DIR.stat().st_mtime
        except OSError:
            return False
        return age > age_seconds
    try:
        age = time.time() - owner.get("pid_started", 0)
    except Exception:
        return True
    return age > age_seconds


def acquire(wait_seconds: int, stale_seconds: int, label: str) -> bool:
    deadline = time.time() + wait_seconds
    while True:
        try:
            LOCK_DIR.mkdir(parents=True)
        except FileExistsError:
            if _lock_is_stale(stale_seconds):
                print(f"[lock] stale lock detected -> taking over "
                      f"(owner={_read_owner()})", flush=True)
                try:
                    shutil.rmtree(LOCK_DIR, ignore_errors=True)
                except Exception:
                    pass
                continue
            if time.time() >= deadline:
                return False
            time.sleep(5)
            continue
        payload = {
            "pid": os.getpid(),
            "label": label,
            "pid_started": time.time(),
            "host": os.environ.get("COMPUTERNAME", "?"),
        }
        OWNER.write_text(json.dumps(payload, indent=2), encoding="utf-8",
                         newline="\n")
        return True


def release() -> None:
    if _read_owner() and _read_owner().get("pid") == os.getpid():
        shutil.rmtree(LOCK_DIR, ignore_errors=True)


def status() -> int:
    owner = _read_owner()
    if owner is None:
        print("[lock] free (no owner)")
        return 0
    age = time.time() - owner.get("pid_started", 0)
    print(f"[lock] held by pid={owner.get('pid')} label={owner.get('label')} "
          f"age={age:.0f}s")
    return 0


def _raw_command() -> list[str]:
    """The command after the first '--' in sys.argv, verbatim.

    argparse's REMAINDER is unusable here: it re-interprets the trailing
    tokens, which breaks arguments that contain a comma (the probe's
    ``--keys ,``) and any literal '--' the command itself needs.
    """
    argv = sys.argv[1:]
    if "--" not in argv:
        return []
    index = argv.index("--")
    return argv[index + 1:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true",
                        help="acquire the lock, then run the given command")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--wait-seconds", type=int, default=3600)
    parser.add_argument("--stale-seconds", type=int, default=5400)
    parser.add_argument("--label", default="capture")
    # The command after "--" is taken raw from sys.argv (see _raw_command),
    # so argparse must not try to interpret it -> parse_known_args.
    args, _unknown = parser.parse_known_args()

    if args.status:
        return status()
    if args.release:
        release()
        print("[lock] released")
        return 0
    if not args.run:
        parser.error("need --run, --status or --release")

    # ⭐ 2026-10-25 (wave 22 / D3 报): the command must be taken **raw** from
    # sys.argv and split at the FIRST "--" only.  The old code dropped *every*
    # "--", which also ate a "--" that belonged to the command itself (the
    # probe uses it as a separator) => the probe died with
    # "OSError: [Errno 22]" and it looked like a probe crash.
    #
    # ⚠️ A bare "," in the command is eaten by **PowerShell** (it is the array
    # separator), not by this script: quote it as ',' if you need a literal
    # comma (the probe's `--keys ,`).
    command = _raw_command()
    if not command:
        parser.error("--run needs a command after '--'")

    if not acquire(args.wait_seconds, args.stale_seconds, args.label):
        owner = _read_owner()
        print(f"[lock] could not acquire (held by {owner})", file=sys.stderr)
        return 2
    try:
        print(f"[lock] acquired for {args.label}", flush=True)
        completed = subprocess.run(command)
        return completed.returncode
    finally:
        release()


if __name__ == "__main__":
    sys.exit(main())
