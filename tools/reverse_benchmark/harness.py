"""Guarded lifecycle for one reverse-benchmark smoke attempt."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Mapping, Sequence

from .billing import calculate_attempt_billing
from .capture import (
    _redact_credential_material,
    contains_credential_material,
    contains_credential_material_bytes,
)
from .events import parse_codex_jsonl, parse_pi_jsonl
from .matrix import BenchmarkConfiguration
from .packets import PreparedPacket, prepare_smoke_packet
from .pricing import NormalizedUsage
from .runner import (
    benchmark_provider_contract,
    build_codex_command,
    build_ultra_appserver_command,
    write_minimax_catalog,
)
from .schemas import ATTEMPT_SCHEMA
from .verifier import VerificationResult, verify_smoke_submission


_RUN_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_PLAN_ID_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_ARCHIVE_FILES = 512
_MAX_ARCHIVE_FILE_BYTES = 8 * 1024 * 1024
_MAX_ARCHIVE_TOTAL_BYTES = 32 * 1024 * 1024
_PROMPT = """Work only inside this benchmark packet.
Read AGENTS.md and TASK.md, then complete every requested deliverable under
submission/. Run the focused tests and reproduction command before finishing.
"""


def _json_file(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _safe_command(command: Sequence[str]) -> list[str]:
    if isinstance(command, (str, bytes)):
        raise ValueError("benchmark command must be a sequence, not a string")
    rendered = list(command)
    if not rendered or not all(isinstance(item, str) and item for item in rendered):
        raise ValueError("benchmark command must contain non-empty strings")
    return rendered


def _secret_free_command(
    command: Sequence[str], sensitive_values: Sequence[str] = ()
) -> list[str]:
    rendered = _safe_command(command)
    serialized = json.dumps(rendered, ensure_ascii=False, separators=(",", ":"))
    if contains_credential_material(serialized, tuple(sensitive_values)):
        raise ValueError("credential material is forbidden in child command")
    return rendered


def _validated_plan_binding(
    value: Mapping[str, object] | None,
) -> dict[str, object] | None:
    if value is None:
        return None
    expected_keys = {
        "plan_id",
        "case_id",
        "sequence",
        "attempt_index",
        "provider_contract_sha256",
        "retry_of",
    }
    if set(value) != expected_keys:
        raise ValueError("plan_binding fields do not match the frozen contract")
    plan_id = value.get("plan_id")
    case_id = value.get("case_id")
    sequence = value.get("sequence")
    attempt_index = value.get("attempt_index")
    provider_contract_hash = value.get("provider_contract_sha256")
    retry_of = value.get("retry_of")
    if not isinstance(plan_id, str) or not _PLAN_ID_RE.fullmatch(plan_id):
        raise ValueError("plan_binding plan_id is invalid")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("plan_binding case_id is invalid")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence <= 0:
        raise ValueError("plan_binding sequence is invalid")
    if attempt_index not in {1, 2}:
        raise ValueError("plan_binding attempt_index is invalid")
    if (
        not isinstance(provider_contract_hash, str)
        or not _PLAN_ID_RE.fullmatch(provider_contract_hash)
    ):
        raise ValueError("plan_binding provider contract hash is invalid")
    if attempt_index == 1 and retry_of is not None:
        raise ValueError("primary plan binding cannot have retry_of")
    if attempt_index == 2 and (
        not isinstance(retry_of, str) or not _RUN_ID_RE.fullmatch(retry_of)
    ):
        raise ValueError("retry plan binding requires a valid retry_of run id")
    return {key: value[key] for key in sorted(expected_keys)}


def _guard_command(
    *,
    repo_root: Path,
    workspace: Path,
    run_dir: Path,
    child_command: Sequence[str],
    wall_timeout_s: float,
    idle_timeout_s: float,
    redact_environment_names: Sequence[str] = (),
) -> list[str]:
    safe_child_command = _secret_free_command(child_command)
    capture_command = [
        sys.executable,
        "-B",
        str(repo_root / "tools/reverse_benchmark/capture.py"),
        "--events",
        str(run_dir / "events.jsonl"),
        "--stderr",
        str(run_dir / "stderr.jsonl"),
        "--stdin",
        str(run_dir / "prompt.txt"),
    ]
    for name in sorted(redact_environment_names):
        capture_command.extend(["--redact-env", name])
    capture_command.extend(["--", *safe_child_command])
    return [
        sys.executable,
        "-B",
        str(repo_root / "tools/run_guarded.py"),
        "--summary",
        str(run_dir / "guard-summary.json"),
        "--lock-file",
        str(repo_root / "build/resource-guard/heavy.lock"),
        "--cwd",
        str(workspace),
        "--wall-timeout-s",
        str(wall_timeout_s),
        "--idle-timeout-s",
        str(idle_timeout_s),
        "--",
        *capture_command,
    ]


def _empty_telemetry(error: str) -> dict[str, object]:
    return {
        "usage": {
            "uncached_input": 0,
            "cached_input": 0,
            "cache_write_input": 0,
            "output": 0,
            "reasoning_output": 0,
        },
        "requests": [],
        "usage_complete": False,
        "tool_calls": 0,
        "successful_tool_calls": 0,
        "failed": True,
        "errors": [error],
        "wall_time_ms": None,
        "usage_scope": None,
        "usage_granularity": None,
    }


def _empty_verification(error: str) -> VerificationResult:
    return VerificationResult(
        passed=False,
        score=0,
        errors=(error,),
        error_codes=("harness-error",),
    )


def _child_environment(extra: Mapping[str, str] | None) -> dict[str, str]:
    allowed_names = {
        "CODEX_HOME",
        "HOME",
        "LANG",
        "LOGNAME",
        "PATH",
        "SHELL",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "TERM",
        "TMPDIR",
        "USER",
    }
    environment = {
        name: value
        for name, value in os.environ.items()
        if name in allowed_names or name.startswith("LC_")
    }
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra:
        for name, value in extra.items():
            if (
                not isinstance(name, str)
                or not name
                or "=" in name
                or not isinstance(value, str)
            ):
                raise ValueError("child_environment must contain valid string pairs")
            environment[name] = value
    return environment


def _redact_text(text: str, sensitive_values: Sequence[str]) -> str:
    redacted = text
    for value in sensitive_values:
        if not value:
            continue
        redacted = redacted.replace(value, "[REDACTED]")
        escaped = json.dumps(value, ensure_ascii=False)[1:-1]
        redacted = redacted.replace(escaped, "[REDACTED]")
    redacted, _ = _redact_credential_material(redacted, tuple(sensitive_values))
    return redacted


def _redact_object(value: object, sensitive_values: Sequence[str]) -> object:
    if isinstance(value, str):
        return _redact_text(value, sensitive_values)
    if isinstance(value, list):
        return [_redact_object(item, sensitive_values) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _redact_object(item, sensitive_values)
            for key, item in value.items()
        }
    return value


def _sanitize_log(path: Path, sensitive_values: Sequence[str]) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    redacted = _redact_text(text, sensitive_values)
    if redacted != text:
        path.write_text(redacted, encoding="utf-8")
        return True
    return False


def _archive_packet(
    packet: PreparedPacket,
    destination: Path,
    *,
    sensitive_values: Sequence[str],
) -> dict[str, object]:
    destination.mkdir()
    rejected: list[str] = []
    credential_paths: list[str] = []
    file_count = 0
    total_bytes = 0

    def copy_directory(source: Path, target: Path, relative: Path) -> None:
        nonlocal file_count, total_bytes
        for entry in sorted(os.scandir(source), key=lambda item: item.name):
            entry_relative = relative / entry.name
            rendered = entry_relative.as_posix()
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError:
                rejected.append(rendered)
                continue
            if stat.S_ISDIR(info.st_mode):
                child_target = target / entry.name
                child_target.mkdir()
                copy_directory(Path(entry.path), child_target, entry_relative)
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                rejected.append(rendered)
                continue
            if (
                file_count >= _MAX_ARCHIVE_FILES
                or info.st_size > _MAX_ARCHIVE_FILE_BYTES
                or total_bytes + info.st_size > _MAX_ARCHIVE_TOTAL_BYTES
            ):
                rejected.append(rendered)
                continue
            data = Path(entry.path).read_bytes()
            if contains_credential_material_bytes(data, tuple(sensitive_values)):
                rejected.append(rendered)
                credential_paths.append(rendered)
                continue
            (target / entry.name).write_bytes(data)
            file_count += 1
            total_bytes += len(data)

    copy_directory(packet.root, destination, Path())
    return {
        "safe": not rejected,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "rejected_paths": rejected,
        "credential_paths": credential_paths,
    }


def _ensure_stream_evidence(run_dir: Path) -> None:
    for name, stream in (("events.jsonl", "stdout"), ("stderr.jsonl", "stderr")):
        path = run_dir / name
        if not path.exists():
            path.write_text(
                json.dumps(
                    {
                        "type": "harness.missing-stream",
                        "stream": stream,
                        "reason": "capture-did-not-start",
                    },
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )


def run_smoke_attempt(
    *,
    repo_root: Path,
    output_root: Path,
    configuration: BenchmarkConfiguration,
    challenge_id: str,
    seed: int,
    run_id: str,
    wall_timeout_s: float = 1_800,
    idle_timeout_s: float = 600,
    command_override: Sequence[str] | None = None,
    child_environment: Mapping[str, str] | None = None,
    plan_binding: Mapping[str, object] | None = None,
    compatibility_receipt_id: str | None = None,
) -> dict[str, object]:
    """Run, verify, and persist one immutable smoke attempt."""

    if not _RUN_ID_RE.fullmatch(run_id):
        raise ValueError("run_id must be 32 lowercase hexadecimal characters")
    if (
        not math.isfinite(wall_timeout_s)
        or not math.isfinite(idle_timeout_s)
        or wall_timeout_s <= 0
        or idle_timeout_s <= 0
    ):
        raise ValueError("benchmark timeouts must be finite and positive")
    if configuration.harness not in {"codex", "pi"}:
        raise ValueError(f"unsupported benchmark harness: {configuration.harness}")
    sensitive_values = tuple(
        value for value in (child_environment or {}).values() if value
    )
    if command_override is not None:
        _secret_free_command(command_override, sensitive_values)
    frozen_plan_binding = _validated_plan_binding(plan_binding)
    if frozen_plan_binding is not None and compatibility_receipt_id is None:
        raise ValueError(
            "plan-bound attempt requires compatibility_receipt_id"
        )
    if compatibility_receipt_id is not None and (
        not isinstance(compatibility_receipt_id, str)
        or not _PLAN_ID_RE.fullmatch(compatibility_receipt_id)
    ):
        raise ValueError("compatibility_receipt_id is invalid")

    repo_root = Path(repo_root).resolve()
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = output_root / run_id
    try:
        run_dir.mkdir()
    except FileExistsError as error:
        raise FileExistsError(f"run directory already exists: {run_dir}") from error

    workspace = Path(tempfile.mkdtemp(prefix=f"reverse-benchmark-{run_id}-"))
    workspace_state = "present"
    packet: PreparedPacket | None = None
    completed_returncode = 125
    completed_stdout = ""
    completed_stderr = ""
    telemetry: dict[str, object] = _empty_telemetry("attempt did not start")
    verification = _empty_verification("attempt did not reach verification")
    guard_summary: object = {
        "reason": "not-started",
        "exit_code": 125,
        "degraded": False,
    }
    archive: dict[str, object] = {
        "safe": False,
        "file_count": 0,
        "total_bytes": 0,
        "rejected_paths": [],
        "credential_paths": [],
    }
    harness_errors: list[str] = []
    billing: dict[str, object] = {
        "status": "unknown",
        "unknown_reason": "attempt did not start",
        "requests": [],
        "totals": {
            "api_cost_usd": None,
            "api_cost_cny": None,
            "codex_credits_estimate": None,
            "minimax_token_plan_input_tokens": None,
            "minimax_token_plan_output_tokens": None,
        },
    }
    security_surfaces: set[str] = set()

    try:
        packet = prepare_smoke_packet(challenge_id, workspace / "packet", seed=seed)
        (run_dir / "prompt.txt").write_text(_PROMPT, encoding="utf-8")

        if command_override is None:
            catalog = None
            if configuration.provider == "minimax":
                catalog = write_minimax_catalog(
                    configuration,
                    run_dir / "model-catalog.json",
                )
            if configuration.system_mode == "multi-agent":
                child_command = build_ultra_appserver_command(
                    configuration,
                    workspace=packet.root,
                    repo_root=repo_root,
                )
            else:
                child_command = build_codex_command(
                    configuration,
                    workspace=packet.root,
                    model_catalog=catalog,
                )
        else:
            child_command = _secret_free_command(command_override, sensitive_values)

        child_command = _secret_free_command(child_command, sensitive_values)

        guard_command = _guard_command(
            repo_root=repo_root,
            workspace=packet.root,
            run_dir=run_dir,
            child_command=child_command,
            wall_timeout_s=wall_timeout_s,
            idle_timeout_s=idle_timeout_s,
            redact_environment_names=tuple((child_environment or {}).keys()),
        )
        completed = subprocess.run(
            guard_command,
            cwd=repo_root,
            env=_child_environment(child_environment),
            capture_output=True,
            text=True,
            check=False,
        )
        completed_returncode = completed.returncode
        completed_stdout = completed.stdout
        completed_stderr = completed.stderr

        _ensure_stream_evidence(run_dir)
        sanitized_logs = [
            _sanitize_log(run_dir / log_name, sensitive_values)
            for log_name in ("events.jsonl", "stderr.jsonl")
        ]
        capture_reported_credential = any(
            path.is_file()
            and "security.credential-material-redacted"
            in path.read_text(encoding="utf-8", errors="replace")
            for path in (run_dir / "events.jsonl", run_dir / "stderr.jsonl")
        )
        credential_material_detected = any(sanitized_logs) or (
            capture_reported_credential
        )
        if credential_material_detected:
            security_surfaces.add("capture-stream")
            harness_errors.append(
                "credential-shaped material detected and redacted from child streams"
            )
        try:
            event_text = (run_dir / "events.jsonl").read_text(encoding="utf-8")
            parser = parse_pi_jsonl if configuration.harness == "pi" else parse_codex_jsonl
            telemetry = asdict(parser(event_text))
        except (OSError, UnicodeError, ValueError) as error:
            telemetry = _empty_telemetry(f"telemetry parse failed: {error}")

        reported_scope = telemetry.get("usage_scope")
        if configuration.system_mode == "multi-agent":
            if reported_scope == "all-agent-threads":
                usage_scope = "all-agent-threads"
            else:
                usage_scope = "root-thread-only"
                telemetry["usage_complete"] = False
                telemetry["failed"] = True
                errors = telemetry.get("errors")
                error_values = list(errors) if isinstance(errors, (list, tuple)) else []
                error_values.append("Ultra all-agent closure marker is missing")
                telemetry["errors"] = error_values
        else:
            usage_scope = "all-agent-threads"
        telemetry["usage_scope"] = usage_scope
        request_usages = []
        request_granularities = []
        for request in telemetry.get("requests", []):
            if not isinstance(request, dict) or not isinstance(
                request.get("usage"), dict
            ):
                continue
            request_usages.append(NormalizedUsage(**request["usage"]))
            request_granularities.append(request.get("usage_granularity"))
        billing = calculate_attempt_billing(
            configuration,
            request_usages,
            usage_granularities=request_granularities,
            usage_complete=bool(telemetry.get("usage_complete")),
            usage_scope=usage_scope,
        )

        try:
            verification = verify_smoke_submission(packet)
        except Exception as error:  # evidence must survive verifier failures
            verification = _empty_verification(
                f"verifier raised {type(error).__name__}: {error}"
            )
            harness_errors.append(verification.errors[0])

        guard_summary_path = run_dir / "guard-summary.json"
        if guard_summary_path.is_file():
            try:
                guard_summary = _redact_object(
                    _json_file(guard_summary_path), sensitive_values
                )
                _write_json(guard_summary_path, guard_summary)
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                guard_summary = {
                    "reason": "invalid-summary",
                    "exit_code": completed.returncode,
                    "degraded": False,
                    "error": str(error),
                }
                _write_json(guard_summary_path, guard_summary)
                harness_errors.append(f"invalid guard summary: {error}")
        else:
            guard_summary = {
                "reason": "missing-summary",
                "exit_code": completed.returncode,
                "degraded": False,
            }
            _write_json(guard_summary_path, guard_summary)
            harness_errors.append("guard summary missing")

        try:
            archive = _archive_packet(
                packet,
                run_dir / "packet",
                sensitive_values=sensitive_values,
            )
            if archive.get("credential_paths"):
                security_surfaces.add("packet-archive")
            if not archive["safe"]:
                harness_errors.append("unsafe packet paths rejected during archive")
        except (OSError, ValueError) as error:
            harness_errors.append(f"packet archive failed: {error}")
    except Exception as error:
        harness_errors.append(f"harness raised {type(error).__name__}: {error}")
    finally:
        try:
            shutil.rmtree(workspace)
            workspace_state = "removed"
        except OSError as error:
            workspace_state = "retained"
            harness_errors.append(f"workspace cleanup failed: {error}")

    _ensure_stream_evidence(run_dir)
    infrastructure_ok = (
        not harness_errors
        and completed_returncode == 0
        and isinstance(guard_summary, dict)
        and guard_summary.get("reason") == "completed"
        and not telemetry["failed"]
        and archive["safe"]
        and workspace_state == "removed"
        and not security_surfaces
    )
    if infrastructure_ok and verification.passed:
        status = "verified-passed"
    elif infrastructure_ok:
        status = "verified-failed"
    else:
        status = "infrastructure-failed"

    manifest: dict[str, object] = {
        "schema": ATTEMPT_SCHEMA,
        "run_id": run_id,
        "status": status,
        "configuration": asdict(configuration),
        "challenge_id": challenge_id,
        "seed": seed,
        "plan_binding": frozen_plan_binding,
        "compatibility_receipt_id": compatibility_receipt_id,
        "provider_contract": benchmark_provider_contract(configuration),
        "security": {
            "credential_material_detected": bool(security_surfaces),
            "surfaces": sorted(security_surfaces),
        },
        "input_hashes": (
            dict(sorted(packet.input_hashes.items())) if packet is not None else {}
        ),
        "workspace": {
            "ephemeral_path": str(workspace),
            "final_state": workspace_state,
        },
        "guard": guard_summary,
        "process": {
            "exit_code": completed_returncode,
            "stdout_tail": _redact_text(completed_stdout[-2_000:], sensitive_values),
            "stderr_tail": _redact_text(completed_stderr[-2_000:], sensitive_values),
        },
        "telemetry": telemetry,
        "billing": billing,
        "verification": asdict(verification),
        "archive": archive,
        "harness_errors": harness_errors,
    }
    raw_manifest = json.dumps(manifest, ensure_ascii=False)
    if contains_credential_material(raw_manifest, sensitive_values):
        security_surfaces.add("manifest")
        manifest["status"] = "infrastructure-failed"
        manifest["harness_errors"] = [
            *harness_errors,
            "credential-shaped material detected and redacted from manifest",
        ]
        manifest["security"] = {
            "credential_material_detected": True,
            "surfaces": sorted(security_surfaces),
        }
    redacted_manifest = _redact_object(manifest, sensitive_values)
    assert isinstance(redacted_manifest, dict)
    manifest = redacted_manifest
    _write_json(run_dir / "manifest.json", manifest)
    persisted_manifest = _json_file(run_dir / "manifest.json")
    assert isinstance(persisted_manifest, dict)
    return persisted_manifest
