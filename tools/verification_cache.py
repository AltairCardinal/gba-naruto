#!/usr/bin/env python3
"""Content-addressed cache for verifier reports.

One ledger promotion costs 57 minutes because ``build_manifest`` re-runs
roughly 105 independent artifact verifiers, each of which re-derives its
artifact from the 6 MiB ROM.  Between two promotions most of those
verifiers and most of their inputs are byte-identical, so their reports can
be reused.

Reuse is only safe when *every* input is identical, so the cache key is the
SHA-256 of a canonical description of

* the verifier script's own digest,
* the base ROM's digest,
* and the digest of every input file the verifier reads.

A hit therefore carries exactly the evidence a fresh run would have
produced.  Any I/O problem is treated as a miss; the cache can never turn a
failure into a success.

The cache lives under ``build/`` because it is derived, regenerable data
that must never be mistaken for a committed receipt.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Iterable, Sequence


CACHE_SCHEMA = "rom-verification-report-cache-v1"
DEFAULT_CACHE_DIR = Path("build/experiments/cache/verification-reports")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def describe_inputs(root: Path, paths: Iterable[Path]) -> tuple[tuple[str, str], ...]:
    """Return ``(relative path, sha256)`` for every readable input.

    A missing or unreadable input is a hard error: the caller must not be
    able to obtain a cache key that hides a changed file.
    """

    root = root.resolve(strict=True)
    described: list[tuple[str, str]] = []
    for path in sorted(Path(item) for item in paths):
        candidate = path if path.is_absolute() else root / path
        if not candidate.is_file():
            raise ValueError(f"cache input is missing: {path}")
        try:
            relative = candidate.resolve(strict=True).relative_to(root).as_posix()
        except (OSError, ValueError) as error:
            raise ValueError(f"cache input escapes the repository: {path}") from error
        described.append((relative, _sha_file(candidate)))
    return tuple(described)


def fingerprint(
    verifier: Path,
    verifier_sha256: str,
    rom_sha256: str,
    inputs: Sequence[tuple[str, str]],
) -> str:
    """Return the cache key for one verifier invocation."""

    description = {
        "schema": CACHE_SCHEMA,
        "verifier": verifier.as_posix(),
        "verifier_sha256": verifier_sha256,
        "rom_sha256": rom_sha256,
        # Sorted so the key does not depend on the order in which the caller
        # happened to list the inputs.
        "inputs": sorted([list(item) for item in inputs]),
    }
    return _sha_bytes(_canonical(description))


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _report_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{key}.json"


def load_report(cache_dir: Path, key: str) -> dict[str, Any] | None:
    """Return the cached report, or ``None`` on any miss or corruption."""

    path = _report_path(cache_dir, key)
    try:
        raw = path.read_bytes()
        report = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(report, dict) or report.get("schema") != CACHE_SCHEMA:
        return None
    if report.get("cache_key") != key:
        return None
    payload = report.get("report")
    if not isinstance(payload, dict):
        return None
    return payload


def store_report(cache_dir: Path, key: str, report: dict[str, Any]) -> Path:
    """Store one report atomically; an existing entry is never overwritten."""

    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = _report_path(cache_dir, key)
    if destination.exists():
        return destination
    document = {
        "schema": CACHE_SCHEMA,
        "cache_key": key,
        "report": report,
    }
    with tempfile.TemporaryDirectory(dir=cache_dir, prefix=".cache-") as directory:
        stage = Path(directory) / "entry.json"
        stage.write_bytes(_canonical(document))
        os.replace(stage, destination)
    return destination


def cached_verify(
    *,
    root: Path,
    cache_dir: Path,
    verifier: Path,
    verifier_sha256: str,
    rom_sha256: str,
    inputs: Sequence[tuple[str, str]],
    compute: Callable[[], dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """Return ``(report, from_cache)`` for one verifier invocation.

    ``compute`` is only called on a cache miss.  A cache entry is written
    only when the fresh report is a verified one, so a failing verifier is
    never memoised into a success.
    """

    key = fingerprint(verifier, verifier_sha256, rom_sha256, inputs)
    cached = load_report(cache_dir, key)
    if cached is not None:
        return cached, True
    report = compute()
    if report.get("verified") is True:
        store_report(cache_dir, key, report)
    return report, False


__all__ = [
    "CACHE_SCHEMA",
    "DEFAULT_CACHE_DIR",
    "cached_verify",
    "describe_inputs",
    "fingerprint",
    "load_report",
    "store_report",
]
