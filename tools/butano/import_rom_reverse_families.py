#!/usr/bin/env python3
"""Shared machinery for importing closed reverse results into the Butano tree.

The reverse work tree holds signed results: every family carries a
``manifest.json`` that pins the SHA-256 of each of its own files.  Importing
one of those families into the remake tree has to be checkable, otherwise
"imported" means nothing more than "a file was copied".  The importers in this
package therefore share four rules, which live here once instead of being
re-typed per family group:

1.  **Only a signed manifest is imported.**  The manifest's SHA-256 is pinned
    in the importer that names the family, and the manifest is re-read from the
    reverse work tree at run time.  A manifest that moved, vanished or was
    edited is a hard failure naming the family -- never a silent skip.
2.  **Only ``accepted`` results are imported.**  ``candidate``, ``disproved``
    and ``superseded`` are rejected by name: a candidate is not a result.
3.  **Every file the manifest lists is re-hashed.**  A family whose bytes no
    longer match its own manifest is a hard failure.
4.  **The import is deterministic.**  The same reverse tree produces
    byte-identical output, so a third party can re-run the importer and diff
    the result.  No timestamps, no absolute paths and no iteration-order
    dependence leak into the written files.

The module is import-safe and side-effect free; the importers own the CLI.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

#: Default location of the reverse work tree.  Matches the default used by
#: ``tools/measure_butano_reverse_gap.py`` so both tools read the same tree.
DEFAULT_REVERSE_ROOT = Path("/Users/altair/github/gba-naruto-reverse")

#: The only artifact status that may be imported.
ACCEPTED_STATUS = "accepted"

#: Statuses that must never be imported, listed so the failure message can
#: name them instead of only reporting "not accepted".
REJECTED_STATUSES = ("candidate", "disproved", "superseded")

#: Exit codes shared by every importer in this package.
EXIT_OK = 0
EXIT_GATE_FAILED = 1
EXIT_INPUT_ERROR = 2
EXIT_HASH_MISMATCH = 3
EXIT_STATUS_REJECTED = 4
EXIT_FAMILY_FILE_MISMATCH = 5
EXIT_BASELINE_MISSING = 6


class FamilyImportError(RuntimeError):
    """A family could not be imported.  Always names the offending family."""

    def __init__(self, message: str, *, family: str = "", exit_code: int = EXIT_INPUT_ERROR):
        super().__init__(message)
        self.family = family
        self.exit_code = exit_code


@dataclass(frozen=True)
class FamilySpec:
    """One family to import, pinned by the SHA-256 of its manifest."""

    family: str
    manifest_sha256: str

    @property
    def manifest_relpath(self) -> str:
        return f"artifacts/{self.family}/manifest.json"


def as_specs(entries: Iterable[tuple[str, str]]) -> tuple[FamilySpec, ...]:
    """Turn ``(family, manifest_sha256)`` pairs into pinned specifications."""
    specs = tuple(FamilySpec(family=family, manifest_sha256=digest)
                  for family, digest in entries)
    for spec in specs:
        if len(spec.manifest_sha256) != 64:
            raise FamilyImportError(
                f"pinned manifest hash for {spec.family} is not a sha256",
                family=spec.family, exit_code=EXIT_INPUT_ERROR)
    return specs


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> str:
    """Write ``payload`` deterministically and return its SHA-256."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return sha256_bytes(text.encode("utf-8"))


def reverse_commit(reverse_root: Path) -> str:
    """The commit of the reverse work tree, or ``unknown`` when unavailable."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(reverse_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def manifest_path(reverse_root: Path, spec: FamilySpec) -> Path:
    return Path(reverse_root) / "artifacts" / spec.family / "manifest.json"


def load_verified_manifest(
    reverse_root: Path,
    spec: FamilySpec,
) -> tuple[Path, dict[str, Any]]:
    """Read the family manifest and check it against the pinned hash.

    Fails closed: a missing manifest, a hash mismatch and a non-``accepted``
    status are all hard errors naming the family.
    """
    path = manifest_path(reverse_root, spec)
    if not path.is_file():
        raise FamilyImportError(
            f"{spec.family}: manifest not found at {path}",
            family=spec.family, exit_code=EXIT_INPUT_ERROR)
    actual = sha256_file(path)
    if actual != spec.manifest_sha256:
        raise FamilyImportError(
            f"{spec.family}: manifest sha256 mismatch "
            f"(pinned {spec.manifest_sha256}, actual {actual})",
            family=spec.family, exit_code=EXIT_HASH_MISMATCH)
    manifest = read_json(path)
    if not isinstance(manifest, dict):
        raise FamilyImportError(
            f"{spec.family}: manifest is not a JSON object",
            family=spec.family, exit_code=EXIT_INPUT_ERROR)
    status = str(manifest.get("artifact_status") or "")
    if status != ACCEPTED_STATUS:
        raise FamilyImportError(
            f"{spec.family}: artifact_status is {status!r}, only {ACCEPTED_STATUS!r} "
            f"may be imported"
            + (f" (rejected statuses: {', '.join(REJECTED_STATUSES)})"
               if status in REJECTED_STATUSES else ""),
            family=spec.family, exit_code=EXIT_STATUS_REJECTED)
    return path, manifest


def verify_family_files(
    family_dir: Path,
    spec: FamilySpec,
    manifest: dict[str, Any],
) -> dict[str, str]:
    """Re-hash every file the manifest lists.

    Returns the verified ``{relative path: sha256}`` map.  A file that is
    missing or whose bytes moved is a hard failure naming the family.
    """
    family_dir = Path(family_dir)
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise FamilyImportError(
            f"{spec.family}: manifest lists no files",
            family=spec.family, exit_code=EXIT_INPUT_ERROR)
    verified: dict[str, str] = {}
    for relative in sorted(files):
        expected = files[relative]
        path = family_dir / relative
        if not path.is_file():
            raise FamilyImportError(
                f"{spec.family}: manifest file {relative} is missing",
                family=spec.family, exit_code=EXIT_FAMILY_FILE_MISMATCH)
        actual = sha256_file(path)
        if actual != expected:
            raise FamilyImportError(
                f"{spec.family}: file {relative} sha256 mismatch "
                f"(manifest {expected}, actual {actual})",
                family=spec.family, exit_code=EXIT_FAMILY_FILE_MISMATCH)
        verified[relative] = actual
    return verified


def manifest_verifier(manifest: dict[str, Any]) -> dict[str, Any]:
    """The manifest's own verifier record, preserved as provenance."""
    verifier = manifest.get("verifier")
    return verifier if isinstance(verifier, dict) else {}


def manifest_scope(manifest: dict[str, Any]) -> dict[str, Any]:
    """The manifest's applicability boundary, preserved as provenance."""
    scope = manifest.get("scope")
    return scope if isinstance(scope, dict) else {}


def copy_verified_file(source: Path, destination: Path, expected_sha256: str) -> str:
    """Copy one verified file and re-check its hash after the copy."""
    source, destination = Path(source), Path(destination)
    if sha256_file(source) != expected_sha256:
        raise FamilyImportError(
            f"{source}: bytes changed while importing", exit_code=EXIT_HASH_MISMATCH)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())
    written = sha256_file(destination)
    if written != expected_sha256:
        raise FamilyImportError(
            f"{destination}: written bytes do not match the manifest",
            exit_code=EXIT_HASH_MISMATCH)
    return written


def prune_previous_output(out_dir: Path, manifest_name: str) -> list[str]:
    """Remove the files a previous run of this importer wrote.

    Only files listed in the previous import manifest are removed, so a
    directory shared with unrelated tooling is never touched.
    """
    out_dir = Path(out_dir)
    manifest_path = out_dir / manifest_name
    if not manifest_path.is_file():
        return []
    try:
        previous = read_json(manifest_path)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(previous, dict):
        return []
    removed: list[str] = []
    for entry in previous.get("written_files") or []:
        relative = entry.get("path") if isinstance(entry, dict) else entry
        if not isinstance(relative, str) or not relative:
            continue
        target = out_dir / relative
        if target.is_file():
            target.unlink()
            removed.append(relative)
    return removed


def first_key(payload: dict[str, Any], names: Sequence[str]) -> Any:
    """Return the first present key from ``names`` (``None`` when absent)."""
    for name in names:
        if name in payload:
            return payload[name]
    return None


def dig(payload: Any, path: Sequence[str]) -> Any:
    """Follow ``path`` through nested dicts, returning ``None`` when absent."""
    current = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current
