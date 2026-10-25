#!/usr/bin/env python3
"""Ratchet check: the workspace unit test failure set must be a subset of the
pinned baseline's failure set (same names).

Usage::

    python tools/s49_y3/check_unit_ratchet.py \
        --baseline build/s49-package/baseline/unit-tests-workspace.tsv \
        --workspace build/s49-y3/unit-tests-workspace.tsv
"""

from __future__ import annotations

import argparse
import pathlib
import sys


def failures(path: pathlib.Path) -> set[str]:
    """The failing test names.

    Accepts either the TSV receipts (``name<TAB>fail<TAB>...``) or the raw
    runner output (``FAIL(run) name`` / ``FAIL(compile) name``).
    """
    names = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1].strip() == "fail":
            names.add(parts[0].strip())
            continue
        if line.startswith("FAIL("):
            head, _, tail = line.partition(")")
            names.add(tail.strip())
    return names


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", type=pathlib.Path, required=True)
    ap.add_argument("--workspace", type=pathlib.Path, required=True)
    args = ap.parse_args()

    base = failures(args.baseline)
    work = failures(args.workspace)
    added = sorted(work - base)
    removed = sorted(base - work)
    print(f"baseline failures : {len(base)}")
    print(f"workspace failures: {len(work)}")
    print(f"new (regression)  : {added}")
    print(f"fixed (improvement): {removed}")
    if added:
        print("RATCHET: RED -- the workspace has failures the baseline does not")
        return 1
    print("RATCHET: GREEN -- the failure set is a subset of the baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
