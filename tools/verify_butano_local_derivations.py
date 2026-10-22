#!/usr/bin/env python3
"""Independently verify the local-derivation restoration receipt.

This verifier deliberately does **not** import the tool that produced the
receipt.  It re-reads the work tree and the reverse work tree, recomputes the
digests with its own implementation, and re-decides every claim the receipt
makes.  A receipt that only agrees with itself proves nothing.

What is checked:

* every family the receipt lists has a local copy that is byte-identical to
  the reverse work tree's copy (path set + per-file SHA-256);
* the manifest hashes the receipt quotes are the hashes actually on disk;
* the summary counts agree with the rows;
* the wiring receipt reports **zero** families in the ``local-derivation-missing``
  state -- the milestone's own gate;
* a family recorded as ``rederived`` names a producer that exists in this tree.

Usage::

    python3 tools/verify_butano_local_derivations.py \\
        --root . \\
        --reverse-root /Users/altair/github/gba-naruto-reverse \\
        --receipt artifacts/butano-local-derivations-v1/local.json \\
        --wiring artifacts/butano-wiring-coverage-v1/wiring.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_INPUT_ERROR = 2
EXIT_MISMATCH = 3


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_digests(directory: Path) -> dict[str, str]:
    """Relative path -> SHA-256 for every file under ``directory``."""
    return {
        path.relative_to(directory).as_posix(): _sha256(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def compare(local: Path, reverse: Path) -> dict[str, Any]:
    local_files = file_digests(local)
    reverse_files = file_digests(reverse)
    shared = set(local_files) & set(reverse_files)
    return {
        "identical": local_files == reverse_files,
        "only_local": sorted(set(local_files) - set(reverse_files)),
        "only_reverse": sorted(set(reverse_files) - set(local_files)),
        "differing": sorted(
            rel for rel in shared if local_files[rel] != reverse_files[rel]
        ),
    }


def verify(
    root: Path,
    reverse_root: Path,
    receipt_path: Path,
    wiring_path: Path | None,
) -> list[str]:
    problems: list[str] = []
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    rows = receipt.get("rows") or []

    if not rows:
        problems.append("receipt lists no families")

    for row in rows:
        family = str(row.get("family") or "")
        if not family:
            problems.append("a row has no family id")
            continue
        local = root / "artifacts" / family
        reverse = reverse_root / "artifacts" / family
        if not local.is_dir():
            problems.append(f"{family}: local copy is missing")
            continue
        if not reverse.is_dir():
            problems.append(f"{family}: reverse twin is missing")
            continue
        result = compare(local, reverse)
        if not result["identical"]:
            problems.append(
                f"{family}: local copy differs from the reverse twin "
                f"(only_local={result['only_local'][:3]} "
                f"only_reverse={result['only_reverse'][:3]} "
                f"differing={result['differing'][:3]})"
            )
            continue
        for key, path in (
            ("local_manifest_sha", local / "manifest.json"),
            ("reverse_manifest_sha", reverse / "manifest.json"),
        ):
            quoted = row.get(key)
            if quoted is None:
                continue
            actual = _sha256(path) if path.is_file() else None
            if actual != quoted:
                problems.append(f"{family}: {key} is {actual}, receipt says {quoted}")
        mode = row.get("mode")
        if mode == "rederived":
            producer = row.get("producer")
            if not producer:
                problems.append(f"{family}: rederived but no producer named")
            elif not (root / str(producer)).is_file():
                problems.append(f"{family}: producer {producer} is not in this tree")

    summary = receipt.get("summary") or {}
    counted = {
        "rederived": sum(1 for row in rows if row.get("mode") == "rederived"),
        "imported": sum(1 for row in rows if row.get("mode") == "imported"),
        "already_identical": sum(
            1 for row in rows if row.get("mode") == "already-identical"
        ),
        "diverged": sum(1 for row in rows if row.get("mode") == "diverged"),
        "unavailable": sum(1 for row in rows if row.get("mode") == "unavailable"),
        "error": sum(1 for row in rows if row.get("mode") == "error"),
    }
    for key, value in counted.items():
        if summary.get(key) != value:
            problems.append(
                f"summary.{key} is {summary.get(key)}, the rows say {value}"
            )
    if summary.get("diverged"):
        problems.append("the receipt reports a divergence; W1 cannot be closed")
    if summary.get("error"):
        problems.append("the receipt reports an error; W1 cannot be closed")

    if wiring_path is not None:
        wiring = json.loads(wiring_path.read_text(encoding="utf-8"))
        missing = [
            row
            for row in (wiring.get("source_rows") or [])
            if row.get("state") == "local-derivation-missing"
        ]
        if missing:
            problems.append(
                "the wiring receipt still reports "
                f"{len(missing)} families as local-derivation-missing: "
                + ", ".join(sorted(str(row.get("id")) for row in missing)[:8])
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--reverse-root",
        type=Path,
        default=Path("/Users/altair/github/gba-naruto-reverse"),
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path("artifacts/butano-local-derivations-v1/local.json"),
    )
    parser.add_argument(
        "--wiring",
        type=Path,
        default=Path("artifacts/butano-wiring-coverage-v1/wiring.json"),
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    reverse_root = args.reverse_root.resolve()
    receipt_path = args.receipt if args.receipt.is_absolute() else root / args.receipt
    wiring_path = args.wiring if args.wiring.is_absolute() else root / args.wiring

    if not receipt_path.is_file():
        print(f"receipt not found: {receipt_path}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    if not wiring_path.is_file():
        print(f"wiring receipt not found: {wiring_path}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    if not (reverse_root / "artifacts").is_dir():
        print(f"reverse tree not found: {reverse_root}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    problems = verify(root, reverse_root, receipt_path, wiring_path)
    if problems:
        for problem in problems:
            print(f"PROBLEM: {problem}", file=sys.stderr)
        return EXIT_MISMATCH
    print(f"ok: {receipt_path} verified against {reverse_root}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
