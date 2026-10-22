#!/usr/bin/env python3
"""Validate reproducible runtime-checkpoint lineage metadata."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path


REQUIRED_FIELDS = {
    "name",
    "status",
    "path",
    "sha256",
    "rom",
    "rom_sha256",
    "parent",
    "inputs",
    "screen",
    "stable_zero_input",
    "before_hooks",
    "allowed_evidence",
}
VALID_STATUSES = {"accepted", "candidate", "rejected"}
EVIDENCE_HOOK_ALTERNATIVES = {
    "player-control": (
        {"0x08073946", "0x080739D8"},
        {"0x08073946", "0x08073BAC"},
    ),
    "movedone": ({"0x0807443C", "0x08074918"},),
    "victory": ({"0x0807444E", "0x08074458"},),
    "postbattle": ({"0x080735C2"},),
}
HOOK_PATTERN = re.compile(r"0x[0-9A-F]{8}\Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _repo_path(value: str, root: Path, field: str) -> tuple[Path | None, str | None]:
    relative = Path(value)
    if not value or relative.is_absolute():
        return None, f"{field} must be a non-empty repo-relative path"
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    if not resolved.is_relative_to(resolved_root):
        return None, f"{field} escapes repository root"
    return resolved, None


def _validate_string_list(
    record: dict[str, object], field: str, errors: list[str]
) -> bool:
    value = record[field]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        errors.append(f"{field} must be a list of strings")
        return False
    return True


def validate_record(record: dict[str, object], root: Path) -> list[str]:
    errors = [
        f"missing field: {name}" for name in sorted(REQUIRED_FIELDS - record.keys())
    ]
    if errors:
        return errors

    name = record["name"] if isinstance(record["name"], str) else "<invalid>"
    status = record["status"]
    for field in ("name", "status", "path", "rom", "screen"):
        if not isinstance(record[field], str) or not record[field]:
            errors.append(f"{field} must be a non-empty string: {name}")
    parent = record["parent"]
    if parent is not None and (not isinstance(parent, str) or not parent):
        errors.append(f"parent must be null or a non-empty string: {name}")
    if type(record["stable_zero_input"]) is not bool:
        errors.append(f"stable_zero_input must be a boolean: {name}")
    _validate_string_list(record, "inputs", errors)
    hooks_valid = _validate_string_list(record, "before_hooks", errors)
    evidence_valid = _validate_string_list(record, "allowed_evidence", errors)

    if not isinstance(status, str) or status not in VALID_STATUSES:
        errors.append(f"invalid status: {name}")
    if not _is_sha256(record["sha256"]):
        errors.append(f"invalid sha256 metadata: {name}")
    if not _is_sha256(record["rom_sha256"]):
        errors.append(f"invalid rom_sha256 metadata: {name}")

    state: Path | None = None
    rom: Path | None = None
    if isinstance(record["path"], str):
        state, path_error = _repo_path(record["path"], root, "path")
        if path_error:
            errors.append(f"{path_error}: {name}")
    if isinstance(record["rom"], str):
        rom, rom_path_error = _repo_path(record["rom"], root, "rom")
        if rom_path_error:
            errors.append(f"{rom_path_error}: {name}")

    if isinstance(status, str) and status in VALID_STATUSES and state is not None:
        if status == "accepted":
            if not state.is_file():
                errors.append(f"checkpoint path is not a regular file: {name}")
            elif _is_sha256(record["sha256"]) and sha256_file(state) != record["sha256"]:
                errors.append(f"checkpoint sha256 mismatch: {name}")
        else:
            build_root = (root.resolve() / "build").resolve()
            if not state.is_relative_to(build_root):
                errors.append(f"{status} path must use repo-relative build/ source: {name}")
            if state.exists() and not state.is_file():
                errors.append(f"{status} path is an existing directory, not a file: {name}")

    if rom is not None:
        if not rom.is_file():
            errors.append(f"ROM path is not a regular file: {name}")
        elif _is_sha256(record["rom_sha256"]) and sha256_file(rom) != record["rom_sha256"]:
            errors.append(f"ROM sha256 mismatch: {name}")

    if status == "accepted" and record["stable_zero_input"] is not True:
        errors.append(f"accepted checkpoint is not stable: {name}")

    if hooks_valid:
        before_hooks = record["before_hooks"]
        for hook in before_hooks:
            if not HOOK_PATTERN.fullmatch(hook):
                errors.append(f"before_hooks contains noncanonical address: {name}")
    if evidence_valid:
        allowed_evidence = record["allowed_evidence"]
        for evidence in allowed_evidence:
            alternatives = EVIDENCE_HOOK_ALTERNATIVES.get(evidence)
            if alternatives is None:
                errors.append(f"unknown evidence: {evidence}: {name}")
            elif hooks_valid and not any(
                required.issubset(set(record["before_hooks"]))
                for required in alternatives
            ):
                errors.append(f"{evidence} evidence crossed its before_hooks boundary: {name}")

    return errors


def validate_ledger(payload: dict[str, object], root: Path) -> list[str]:
    errors: list[str] = []
    if type(payload.get("schema_version")) is not int or payload.get("schema_version") != 1:
        errors.append("schema_version must be integer 1")
    checkpoints = payload.get("checkpoints")
    if not isinstance(checkpoints, list):
        return [*errors, "checkpoints must be a list"]

    records = [record for record in checkpoints if isinstance(record, dict)]
    if len(records) != len(checkpoints):
        errors.append("every checkpoint must be an object")

    names = [record.get("name") for record in records if isinstance(record.get("name"), str)]
    counts = Counter(names)
    for name, count in counts.items():
        if count > 1:
            errors.append(f"duplicate checkpoint name: {name}")

    all_names = set(names)
    seen_names: set[object] = set()
    for record in records:
        errors.extend(validate_record(record, root))
        record_name = record.get("name")
        parent = record.get("parent")
        if isinstance(parent, str) and parent:
            if parent not in all_names:
                errors.append(f"unknown parent: {record_name} -> {parent}")
            elif parent not in seen_names:
                errors.append(
                    f"parent-before-child ordering violated: {record_name} -> {parent}"
                )
        if isinstance(record_name, str):
            seen_names.add(record_name)

    return errors


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print("usage: runtime_checkpoint_ledger.py LEDGER.json", file=sys.stderr)
        return 1

    ledger_path = Path(arguments[0])
    try:
        payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"ledger error: {error}", file=sys.stderr)
        return 1

    if not isinstance(payload, dict):
        print("ledger error: top-level JSON value must be an object", file=sys.stderr)
        return 1

    root = Path(__file__).resolve().parents[1]
    errors = validate_ledger(payload, root)
    checkpoints = payload.get("checkpoints", [])
    statuses = Counter(
        record.get("status")
        for record in checkpoints
        if isinstance(record, dict) and isinstance(record.get("status"), str)
    )
    print(
        f"accepted={statuses['accepted']} candidate={statuses['candidate']} "
        f"rejected={statuses['rejected']} errors={len(errors)}"
    )
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
