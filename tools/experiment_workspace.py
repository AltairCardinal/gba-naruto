#!/usr/bin/env python3
"""Manage ignored experiment runs, verified archives, and artifact promotion."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
from typing import Any, Iterator
import uuid


SCHEMA = "experiment-workspace-v1"
ARCHIVE_SCHEMA = "experiment-archive-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
DEFAULT_MAX_PROMOTED_FILES = 500
DEFAULT_MAX_PROMOTED_BYTES = 250 * 1024 * 1024


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"invalid identifier: {value!r}")
    return value


def _workspace(root: Path) -> Path:
    return root.resolve() / "build" / "experiments"


def _run_path(root: Path, task: str, run_id: str) -> Path:
    return (
        _workspace(root)
        / "active"
        / _validate_identifier(task)
        / _validate_identifier(run_id)
    )


def _metadata_path(run: Path) -> Path:
    return run / ".experiment.json"


def _inventory_path(run: Path) -> Path:
    return run / ".inventory.json"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(_canonical_json_bytes(value))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _restore_file(path: Path, existed: bool, raw: bytes | None) -> None:
    if not existed:
        path.unlink(missing_ok=True)
        return
    if raw is None:
        raise ValueError(f"missing rollback bytes for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.rollback")
    try:
        temporary.write_bytes(raw)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _reject_symlink_components(path: Path) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"promotion path uses a symlink: {current}")


def _payload_files(run: Path) -> list[Path]:
    excluded = {_metadata_path(run), _inventory_path(run)}
    result = []
    for path in sorted(run.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"experiment runs cannot contain symlinks: {path}")
        if path.is_file() and path not in excluded:
            result.append(path)
    return result


def _inventory(run: Path) -> dict[str, Any]:
    files = _payload_files(run)
    entries = {
        path.relative_to(run).as_posix(): {
            "sha256": _sha256(path),
            "size": path.stat().st_size,
        }
        for path in files
    }
    return {
        "schema": "experiment-inventory-v1",
        "file_count": len(entries),
        "byte_count": sum(item["size"] for item in entries.values()),
        "files": entries,
    }


def init_run(root: Path, task: str, run_id: str) -> Path:
    run = _run_path(root, task, run_id)
    if run.exists():
        raise FileExistsError(run)
    run.mkdir(parents=True)
    _write_json(
        _metadata_path(run),
        {
            "schema": SCHEMA,
            "task": task,
            "run_id": run_id,
            "status": "active",
            "created_at": _timestamp(),
        },
    )
    return run


def complete_run(root: Path, task: str, run_id: str) -> dict[str, Any]:
    run = _run_path(root, task, run_id)
    metadata = _read_json(_metadata_path(run))
    if metadata.get("status") not in {"active", "completed"}:
        raise ValueError(f"run status is not completable: {metadata.get('status')}")
    inventory = _inventory(run)
    _write_json(_inventory_path(run), inventory)
    metadata.update(
        {
            "status": "completed",
            "completed_at": metadata.get("completed_at") or _timestamp(),
            "inventory": {
                "file_count": inventory["file_count"],
                "byte_count": inventory["byte_count"],
                "sha256": _sha256(_inventory_path(run)),
            },
        }
    )
    _write_json(_metadata_path(run), metadata)
    return metadata


def _verify_archive(archive: Path, run: Path) -> None:
    expected = {
        f"{run.name}/{path.relative_to(run).as_posix()}"
        for path in run.rglob("*")
        if path.is_file()
    }
    with tarfile.open(archive, "r:gz") as bundle:
        actual = {member.name for member in bundle.getmembers() if member.isfile()}
    if actual != expected:
        raise ValueError("archive member inventory mismatch")


def archive_run(root: Path, task: str, run_id: str) -> dict[str, Path]:
    run = _run_path(root, task, run_id)
    metadata = _read_json(_metadata_path(run))
    if metadata.get("status") != "completed":
        raise ValueError("only explicitly completed runs can be archived")
    completed = datetime.fromisoformat(metadata["completed_at"])
    month = completed.astimezone(timezone.utc).strftime("%Y-%m")
    archive_dir = _workspace(root) / "archive" / task / month
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive = archive_dir / f"{run_id}.tar.gz"
    sidecar = archive.with_suffix(archive.suffix + ".json")
    if archive.exists() or sidecar.exists():
        raise FileExistsError(archive)
    temporary = archive.with_name(f".{archive.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tarfile.open(temporary, "w:gz", compresslevel=6) as bundle:
            bundle.add(run, arcname=run.name, recursive=True)
        _verify_archive(temporary, run)
        os.replace(temporary, archive)
        payload = {
            "schema": ARCHIVE_SCHEMA,
            "task": task,
            "run_id": run_id,
            "archived_at": _timestamp(),
            "archive": archive.relative_to(_workspace(root)).as_posix(),
            "archive_sha256": _sha256(archive),
            "archive_size": archive.stat().st_size,
            "inventory": metadata["inventory"],
            "verified": True,
        }
        _write_json(sidecar, payload)
        shutil.rmtree(run)
    finally:
        temporary.unlink(missing_ok=True)
    return {"archive_path": archive, "sidecar_path": sidecar}


def _validate_promotion_manifest(final: Path) -> dict[str, Any]:
    _reject_symlink_components(final)
    if not final.is_dir():
        raise ValueError("promotion final directory is missing")
    members = sorted(final.rglob("*"))
    for path in members:
        if path.is_symlink():
            raise ValueError(f"promotion member uses a symlink: {path}")
    manifest_path = final / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("promotion manifest is missing")
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    if not isinstance(manifest, dict):
        raise ValueError("promotion manifest must contain a JSON object")
    if manifest_raw != _canonical_json_bytes(manifest):
        raise ValueError("promotion manifest is not canonical JSON")
    if manifest.get("schema") != PROMOTION_SCHEMA:
        raise ValueError("promotion manifest schema mismatch")
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("promotion manifest is not accepted")
    verifier = manifest.get("verifier")
    if (
        not isinstance(verifier, dict)
        or verifier.get("exit_code") != 0
        or not isinstance(verifier.get("command"), list)
        or not verifier["command"]
    ):
        raise ValueError("promotion verifier evidence is missing")
    expected = manifest.get("files")
    if not isinstance(expected, dict):
        raise ValueError("promotion file hashes are missing")
    actual_paths = {
        path.relative_to(final).as_posix()
        for path in members
        if path.is_file() and path != manifest_path
    }
    if actual_paths != set(expected):
        raise ValueError("promotion file inventory mismatch")
    for relative, receipt in expected.items():
        expected_hash = receipt
        expected_size = None
        if isinstance(receipt, dict):
            if set(receipt) != {"sha256", "size"}:
                raise ValueError(
                    f"promotion file receipt is malformed: {relative}"
                )
            expected_hash = receipt["sha256"]
            expected_size = receipt["size"]
            if (
                not isinstance(expected_size, int)
                or isinstance(expected_size, bool)
                or expected_size < 0
            ):
                raise ValueError(
                    f"promotion file size receipt is invalid: {relative}"
                )
            if (final / relative).stat().st_size != expected_size:
                raise ValueError(f"promotion file size mismatch: {relative}")
        elif not isinstance(receipt, str):
            raise ValueError(f"promotion file receipt is malformed: {relative}")
        if (
            not isinstance(expected_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
        ):
            raise ValueError(f"promotion file hash receipt is invalid: {relative}")
        if _sha256(final / relative) != expected_hash:
            raise ValueError(f"promotion file hash mismatch: {relative}")
    return manifest


def promote_run(
    root: Path,
    task: str,
    run_id: str,
    artifact_name: str,
    *,
    max_files: int = DEFAULT_MAX_PROMOTED_FILES,
    max_bytes: int = DEFAULT_MAX_PROMOTED_BYTES,
) -> Path:
    artifact_name = _validate_identifier(artifact_name)
    run = _run_path(root, task, run_id)
    final = run / "final"
    manifest = _validate_promotion_manifest(final)
    files = [path for path in final.rglob("*") if path.is_file()]
    byte_count = sum(path.stat().st_size for path in files)
    if len(files) > max_files or byte_count > max_bytes:
        justification = manifest.get("large_artifact_justification")
        if not isinstance(justification, str) or not justification.strip():
            raise ValueError(
                "promotion exceeds file/byte budget without a justification"
            )
    artifacts = root.resolve() / "artifacts"
    _reject_symlink_components(artifacts)
    if artifacts.exists() and not artifacts.is_dir():
        raise ValueError("artifacts target root is not a directory")
    artifacts.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(artifacts)
    target = artifacts / artifact_name
    _reject_symlink_components(target)
    if target.exists():
        raise FileExistsError(target)
    temporary = artifacts / f".{artifact_name}.promoting-{uuid.uuid4().hex}"
    metadata_path = _metadata_path(run)
    inventory_path = _inventory_path(run)
    metadata_existed = metadata_path.exists()
    inventory_existed = inventory_path.exists()
    metadata_raw = metadata_path.read_bytes() if metadata_existed else None
    inventory_raw = inventory_path.read_bytes() if inventory_existed else None
    target_installed = False
    try:
        shutil.copytree(final, temporary)
        _validate_promotion_manifest(temporary)
        os.replace(temporary, target)
        target_installed = True
        metadata = complete_run(root, task, run_id)
        metadata["promoted_to"] = target.relative_to(root.resolve()).as_posix()
        metadata["promoted_at"] = _timestamp()
        _write_json(metadata_path, metadata)
    except Exception:
        if target_installed and target.exists():
            shutil.rmtree(target)
        if target_installed:
            _restore_file(metadata_path, metadata_existed, metadata_raw)
            _restore_file(inventory_path, inventory_existed, inventory_raw)
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return target


@contextmanager
def _maintenance_lock(root: Path) -> Iterator[None]:
    lock_path = _workspace(root) / ".maintenance.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield


def _archive_sidecars(root: Path) -> list[Path]:
    archive_root = _workspace(root) / "archive"
    return (
        sorted(archive_root.rglob("*.tar.gz.json"))
        if archive_root.is_dir()
        else []
    )


def maintenance(
    root: Path,
    *,
    apply: bool,
    archive_retention_days: int = 30,
    trash_retention_days: int = 7,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or _now()
    workspace = _workspace(root)
    completed = []
    active_root = workspace / "active"
    if active_root.is_dir():
        for metadata_path in sorted(active_root.glob("*/*/.experiment.json")):
            metadata = _read_json(metadata_path)
            if metadata.get("status") == "completed":
                completed.append(f"{metadata['task']}/{metadata['run_id']}")

    archive_cutoff = current - timedelta(days=archive_retention_days)
    trash_candidates = []
    for sidecar in _archive_sidecars(root):
        payload = _read_json(sidecar)
        if datetime.fromisoformat(payload["archived_at"]) <= archive_cutoff:
            trash_candidates.append(
                f"{payload['task']}/{payload['run_id']}"
            )

    purge_cutoff = current - timedelta(days=trash_retention_days)
    purge_candidates = []
    trash_root = workspace / "trash"
    if trash_root.is_dir():
        for sidecar in sorted(trash_root.rglob("*.tar.gz.json")):
            payload = _read_json(sidecar)
            trashed_at = datetime.fromisoformat(payload["trashed_at"])
            if trashed_at <= purge_cutoff:
                purge_candidates.append(
                    f"{payload['task']}/{payload['run_id']}"
                )

    result: dict[str, Any] = {
        "schema": "experiment-maintenance-v1",
        "apply": apply,
        "archive_candidates": completed,
        "trash_candidates": trash_candidates,
        "purge_candidates": purge_candidates,
        "archived": [],
        "trashed": [],
        "purged": [],
    }
    if not apply:
        return result

    with _maintenance_lock(root):
        for item in completed:
            task, run_id = item.split("/", 1)
            archive_run(root, task, run_id)
            result["archived"].append(item)

        for sidecar in _archive_sidecars(root):
            payload = _read_json(sidecar)
            item = f"{payload['task']}/{payload['run_id']}"
            if item not in trash_candidates:
                continue
            archive = sidecar.with_suffix("")
            month = Path(payload["archive"]).parent.name
            target_dir = workspace / "trash" / payload["task"] / month
            target_dir.mkdir(parents=True, exist_ok=True)
            target_archive = target_dir / archive.name
            target_sidecar = target_dir / sidecar.name
            payload["trashed_at"] = _timestamp(current)
            os.replace(archive, target_archive)
            _write_json(target_sidecar, payload)
            sidecar.unlink()
            result["trashed"].append(item)

        if trash_root.is_dir():
            for sidecar in sorted(trash_root.rglob("*.tar.gz.json")):
                payload = _read_json(sidecar)
                item = f"{payload['task']}/{payload['run_id']}"
                if item not in purge_candidates:
                    continue
                archive = sidecar.with_suffix("")
                archive.unlink(missing_ok=True)
                sidecar.unlink(missing_ok=True)
                result["purged"].append(item)
    return result


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("init", "complete", "archive"):
        child = subparsers.add_parser(command)
        child.add_argument("--task", required=True)
        child.add_argument("--run-id", required=True)
    promote = subparsers.add_parser("promote")
    promote.add_argument("--task", required=True)
    promote.add_argument("--run-id", required=True)
    promote.add_argument("--artifact-name", required=True)
    maintain = subparsers.add_parser("maintenance")
    maintain.add_argument("--apply", action="store_true")
    maintain.add_argument("--archive-retention-days", type=int, default=30)
    maintain.add_argument("--trash-retention-days", type=int, default=7)
    args = parser.parse_args()
    root = args.root.resolve()

    if args.command == "init":
        result: Any = {"run_path": init_run(root, args.task, args.run_id)}
    elif args.command == "complete":
        result = complete_run(root, args.task, args.run_id)
    elif args.command == "archive":
        result = archive_run(root, args.task, args.run_id)
    elif args.command == "promote":
        result = {
            "artifact_path": promote_run(
                root,
                args.task,
                args.run_id,
                args.artifact_name,
            )
        }
    else:
        result = maintenance(
            root,
            apply=args.apply,
            archive_retention_days=args.archive_retention_days,
            trash_retention_days=args.trash_retention_days,
        )
    print(json.dumps(_jsonable(result), ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
