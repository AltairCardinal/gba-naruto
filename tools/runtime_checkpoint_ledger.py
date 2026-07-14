#!/usr/bin/env python3
"""Validate reproducible runtime-checkpoint lineage metadata."""

from __future__ import annotations

import hashlib
import json
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
BOUNDED_EVIDENCE = {"player-control", "movedone", "victory", "postbattle"}


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


def validate_record(record: dict[str, object], root: Path) -> list[str]:
    errors = [
        f"missing field: {name}" for name in sorted(REQUIRED_FIELDS - record.keys())
    ]
    if errors:
        return errors

    name = record["name"]
    status = record["status"]
    if status not in VALID_STATUSES:
        errors.append(f"invalid status: {name}")
    if not _is_sha256(record["sha256"]):
        errors.append(f"invalid sha256 metadata: {name}")
    if not _is_sha256(record["rom_sha256"]):
        errors.append(f"invalid rom_sha256 metadata: {name}")

    if status == "accepted":
        state = root / str(record["path"])
        rom = root / str(record["rom"])
        if not state.is_file() or sha256_file(state) != record["sha256"]:
            errors.append(f"checkpoint sha256 mismatch: {name}")
        if not rom.is_file() or sha256_file(rom) != record["rom_sha256"]:
            errors.append(f"ROM sha256 mismatch: {name}")
        if record["stable_zero_input"] is not True:
            errors.append(f"accepted checkpoint is not stable: {name}")

    before_hooks = record["before_hooks"]
    allowed_evidence = record["allowed_evidence"]
    if isinstance(before_hooks, list) and isinstance(allowed_evidence, list):
        for evidence in allowed_evidence:
            if evidence in BOUNDED_EVIDENCE and not before_hooks:
                errors.append(f"{evidence} evidence crossed its before_hooks boundary: {name}")

    return errors


def validate_ledger(payload: dict[str, object], root: Path) -> list[str]:
    checkpoints = payload.get("checkpoints")
    if not isinstance(checkpoints, list):
        return ["checkpoints must be a list"]

    errors: list[str] = []
    records = [record for record in checkpoints if isinstance(record, dict)]
    if len(records) != len(checkpoints):
        errors.append("every checkpoint must be an object")

    names = [record.get("name") for record in records]
    counts = Counter(names)
    for name, count in counts.items():
        if count > 1:
            errors.append(f"duplicate checkpoint name: {name}")

    all_names = set(names)
    seen_names: set[object] = set()
    for record in records:
        errors.extend(validate_record(record, root))
        parent = record.get("parent")
        if parent is not None:
            if parent not in all_names:
                errors.append(f"unknown parent: {record.get('name')} -> {parent}")
            elif parent not in seen_names:
                errors.append(
                    f"parent-before-child ordering violated: {record.get('name')} -> {parent}"
                )
        seen_names.add(record.get("name"))

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
        if isinstance(record, dict)
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
