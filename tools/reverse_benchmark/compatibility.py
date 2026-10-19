"""Fail-closed MiniMax compatibility gate for the Codex Responses harness."""

from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable, Mapping

from .billing import calculate_attempt_billing
from .credentials import CHILD_ENVIRONMENT_NAME, LoadedCredential
from .events import parse_codex_jsonl
from .harness import (
    _child_environment,
    _guard_command,
    _redact_object,
    _sanitize_log,
)
from .matrix import (
    CODEX_NATIVE_TRANSPORT_PROFILE,
    BenchmarkConfiguration,
    benchmark_configuration,
    benchmark_matrix,
)
from .pricing import NormalizedUsage
from .runner import (
    MINIMAX_BASE_URL,
    build_codex_command,
    build_ultra_appserver_command,
    codex_native_http_config_args,
    minimax_provider_contract,
    openai_native_provider_contract,
    openai_proxy_config_args,
    openai_proxy_provider_contract,
    resolve_codex_executable,
    write_minimax_catalog,
)


COMPATIBILITY_SCHEMA = "reverse-model-benchmark-minimax-compatibility-v2"
OPENAI_PROXY_COMPATIBILITY_SCHEMA = (
    "reverse-model-benchmark-openai-proxy-compatibility-v2"
)
OPENAI_NATIVE_COMPATIBILITY_SCHEMA = (
    "reverse-model-benchmark-openai-native-compatibility-v1"
)
_REQUIRED_EXEC_FLAGS = (
    "--json",
    "--ephemeral",
    "--ignore-user-config",
    "--ignore-rules",
    "--strict-config",
    "--sandbox",
)
_CANARY_KINDS = ("plain-text", "tool-loop")
_CANARY_REPETITIONS = 3
_OPENAI_PROXY_CANARY_CASES = (
    ("openai-gpt-5.6-luna-low", "tool-loop"),
    ("openai-gpt-5.6-terra-low", "plain-text"),
    ("openai-gpt-5.6-sol-low", "plain-text"),
    ("openai-gpt-5.6-sol-ultra", "plain-text"),
)
_OPENAI_PROXY_CANARY_CONFIGURATION_IDS = tuple(
    configuration_id for configuration_id, _ in _OPENAI_PROXY_CANARY_CASES
)
_OPENAI_NATIVE_CANARY_CASES = (
    ("openai-gpt-5.6-luna-max", "tool-loop"),
    ("openai-gpt-5.6-terra-max", "plain-text"),
    ("openai-gpt-5.6-sol-medium", "plain-text"),
    ("openai-gpt-5.6-sol-ultra", "plain-text"),
)
_OPENAI_NATIVE_CANARY_CONFIGURATION_IDS = tuple(
    configuration_id for configuration_id, _ in _OPENAI_NATIVE_CANARY_CASES
)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _receipt_id(receipt: Mapping[str, object]) -> str:
    canonical = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_id"
    }
    return _sha256_bytes(_canonical_json(canonical))


def evaluate_static_preflight(
    *,
    codex_path: str,
    codex_sha256: str,
    version: str,
    version_returncode: int,
    exec_help: str,
    help_returncode: int,
    config_probe_returncode: int,
    config_probe_output: str,
) -> dict[str, object]:
    """Reduce local CLI evidence without retaining potentially noisy output."""

    capabilities = {flag: flag in exec_help for flag in _REQUIRED_EXEC_FLAGS}
    valid_identity = (
        Path(codex_path).is_absolute()
        and isinstance(codex_sha256, str)
        and len(codex_sha256) == 64
        and bool(version.strip())
    )
    return {
        "compatible": (
            valid_identity
            and version_returncode == 0
            and help_returncode == 0
            and all(capabilities.values())
            and config_probe_returncode == 0
        ),
        "codex": {
            "path": codex_path,
            "sha256": codex_sha256,
            "version": version.strip(),
        },
        "capabilities": capabilities,
        "command_checks": {
            "version_returncode": version_returncode,
            "help_returncode": help_returncode,
        },
        "config_probe": {
            "returncode": config_probe_returncode,
            "output_sha256": _sha256_bytes(config_probe_output.encode("utf-8")),
        },
    }


def collect_static_preflight() -> dict[str, object]:
    """Check the frozen Codex binary and strict custom-provider configuration."""

    executable = resolve_codex_executable()
    codex_sha256 = _sha256_bytes(executable.read_bytes())
    child_environment = _child_environment(None)
    version = subprocess.run(
        [str(executable), "--version"],
        env=child_environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    help_result = subprocess.run(
        [str(executable), "exec", "--help"],
        env=child_environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    configuration = next(
        item for item in benchmark_matrix() if item.model == "MiniMax-M3"
    )
    with tempfile.TemporaryDirectory(prefix="reverse-benchmark-static-") as directory:
        catalog = write_minimax_catalog(
            configuration, Path(directory) / "catalog.json"
        )
        probe_command = [
            str(executable),
            "app-server",
            "--strict-config",
            "-c",
            'model_provider="minimax"',
            "-c",
            'model_providers.minimax.name="MiniMax"',
            "-c",
            f'model_providers.minimax.base_url="{MINIMAX_BASE_URL}"',
            "-c",
            f'model_providers.minimax.env_key="{CHILD_ENVIRONMENT_NAME}"',
            "-c",
            'model_providers.minimax.wire_api="responses"',
            "-c",
            "model_providers.minimax.requires_openai_auth=false",
            "-c",
            f'model_catalog_json="{catalog}"',
            "-c",
            "mcp_servers={}",
        ]
        probe_input = (
            json.dumps(
                {
                    "method": "initialize",
                    "id": 1,
                    "params": {
                        "clientInfo": {
                            "name": "reverse-benchmark-static-probe",
                            "title": "Reverse Benchmark Static Probe",
                            "version": "1.0.0",
                        },
                        "capabilities": {"experimentalApi": True},
                    },
                },
                separators=(",", ":"),
            )
            + "\n"
            + json.dumps(
                {"method": "initialized", "params": {}},
                separators=(",", ":"),
            )
            + "\n"
        )
        process = subprocess.run(
            probe_command,
            env=child_environment,
            input=probe_input,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        probe_stdout, probe_stderr = process.stdout, process.stderr
        initialized = False
        for line in probe_stdout.splitlines():
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict) and message.get("id") == 1 and "result" in message:
                initialized = True
                break
        probe_returncode = 0 if process.returncode == 0 and initialized else 1
    combined_help = help_result.stdout + help_result.stderr
    combined_probe = probe_stdout + probe_stderr
    return evaluate_static_preflight(
        codex_path=str(executable),
        codex_sha256=codex_sha256,
        version=version.stdout + version.stderr,
        version_returncode=version.returncode,
        exec_help=combined_help,
        help_returncode=help_result.returncode,
        config_probe_returncode=probe_returncode,
        config_probe_output=combined_probe,
    )


def collect_openai_proxy_static_preflight() -> dict[str, object]:
    """Check the frozen Codex binary and OpenAI proxy provider configuration."""

    executable = resolve_codex_executable()
    codex_sha256 = _sha256_bytes(executable.read_bytes())
    child_environment = _child_environment(None)
    version = subprocess.run(
        [str(executable), "--version"],
        env=child_environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    help_result = subprocess.run(
        [str(executable), "exec", "--help"],
        env=child_environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    probe_command = [
        str(executable),
        "app-server",
        "--strict-config",
        "-c",
        "mcp_servers={}",
        *openai_proxy_config_args(),
    ]
    probe_input = (
        json.dumps(
            {
                "method": "initialize",
                "id": 1,
                "params": {
                    "clientInfo": {
                        "name": "reverse-benchmark-openai-proxy-probe",
                        "title": "Reverse Benchmark OpenAI Proxy Probe",
                        "version": "1.0.0",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            },
            separators=(",", ":"),
        )
        + "\n"
        + json.dumps(
            {"method": "initialized", "params": {}},
            separators=(",", ":"),
        )
        + "\n"
    )
    process = subprocess.run(
        probe_command,
        env=child_environment,
        input=probe_input,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    initialized = False
    for line in process.stdout.splitlines():
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(message, dict) and message.get("id") == 1 and "result" in message:
            initialized = True
            break
    probe_returncode = 0 if process.returncode == 0 and initialized else 1
    return evaluate_static_preflight(
        codex_path=str(executable),
        codex_sha256=codex_sha256,
        version=version.stdout + version.stderr,
        version_returncode=version.returncode,
        exec_help=help_result.stdout + help_result.stderr,
        help_returncode=help_result.returncode,
        config_probe_returncode=probe_returncode,
        config_probe_output=process.stdout + process.stderr,
    )


def collect_openai_native_static_preflight() -> dict[str, object]:
    """Check the frozen Codex binary and built-in native provider app-server."""

    executable = resolve_codex_executable()
    codex_sha256 = _sha256_bytes(executable.read_bytes())
    child_environment = _child_environment(None)
    version = subprocess.run(
        [str(executable), "--version"],
        env=child_environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    help_result = subprocess.run(
        [str(executable), "exec", "--help"],
        env=child_environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    probe_command = [
        str(executable),
        "app-server",
        "--strict-config",
        "-c",
        "mcp_servers={}",
        *codex_native_http_config_args(),
    ]
    probe_input = (
        json.dumps(
            {
                "method": "initialize",
                "id": 1,
                "params": {
                    "clientInfo": {
                        "name": "reverse-benchmark-openai-native-probe",
                        "title": "Reverse Benchmark OpenAI Native Probe",
                        "version": "1.0.0",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            },
            separators=(",", ":"),
        )
        + "\n"
        + json.dumps(
            {"method": "initialized", "params": {}},
            separators=(",", ":"),
        )
        + "\n"
    )
    process = subprocess.run(
        probe_command,
        env=child_environment,
        input=probe_input,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    initialized = False
    for line in process.stdout.splitlines():
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(message, dict) and message.get("id") == 1 and "result" in message:
            initialized = True
            break
    probe_returncode = 0 if process.returncode == 0 and initialized else 1
    return evaluate_static_preflight(
        codex_path=str(executable),
        codex_sha256=codex_sha256,
        version=version.stdout + version.stderr,
        version_returncode=version.returncode,
        exec_help=help_result.stdout + help_result.stderr,
        help_returncode=help_result.returncode,
        config_probe_returncode=probe_returncode,
        config_probe_output=process.stdout + process.stderr,
    )


def _decoded_inner_events(path: Path) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        try:
            outer = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(outer, dict):
            continue
        value: object = outer
        if outer.get("type") == "stream.line" and outer.get("stream") == "stdout":
            line = outer.get("line")
            if not isinstance(line, str):
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
        if isinstance(value, dict):
            events.append(value)
    return events


def _agent_text(events: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for event in events:
        item = event.get("item")
        if event.get("type") != "item.completed" or not isinstance(item, dict):
            continue
        if item.get("type") not in {"agent_message", "agentMessage"}:
            continue
        for key in ("text", "content"):
            value = item.get(key)
            if isinstance(value, str):
                parts.append(value)
    return "\n".join(parts)


def _read_guard_reason(path: Path) -> str:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "invalid-summary"
    reason = value.get("reason") if isinstance(value, dict) else None
    return reason if isinstance(reason, str) else "invalid-summary"


def _actual_canary_attempt(
    *,
    repo_root: Path,
    output_dir: Path,
    configuration: BenchmarkConfiguration,
    credential: LoadedCredential | None,
    kind: str,
    index: int,
    nonce: str,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=False)
    workspace = output_dir / "workspace"
    workspace.mkdir()
    try:
        if kind == "plain-text":
            prompt = (
                "Do not use any tool. Reply with exactly this token and nothing else: "
                + nonce
            )
        elif kind == "tool-loop":
            (workspace / "probe.txt").write_text(nonce + "\n", encoding="utf-8")
            prompt = (
                "Use the shell tool to read probe.txt. Then reply with exactly the token "
                "from that file and nothing else."
            )
        else:
            raise ValueError(f"unknown canary kind: {kind}")
        (output_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")
        if configuration.provider == "minimax":
            if credential is None:
                raise ValueError("MiniMax canary requires its scoped credential")
            catalog = write_minimax_catalog(
                configuration, output_dir / "catalog.json"
            )
            child_command = build_codex_command(
                configuration,
                workspace=workspace,
                model_catalog=catalog,
            )
            child_environment = {
                CHILD_ENVIRONMENT_NAME: credential.value
            }
            redact_environment_names = (CHILD_ENVIRONMENT_NAME,)
            sensitive_values = (credential.value,)
        elif configuration.provider == "openai":
            if credential is not None:
                raise ValueError("OpenAI proxy canary cannot receive a credential")
            child_command = (
                build_ultra_appserver_command(
                    configuration,
                    workspace=workspace,
                    repo_root=repo_root,
                )
                if configuration.system_mode == "multi-agent"
                else build_codex_command(configuration, workspace=workspace)
            )
            child_environment = None
            redact_environment_names = ()
            sensitive_values = ()
        else:
            raise ValueError(
                f"unsupported canary provider: {configuration.provider}"
            )
        guard_command = _guard_command(
            repo_root=repo_root,
            workspace=workspace,
            run_dir=output_dir,
            child_command=child_command,
            wall_timeout_s=300,
            idle_timeout_s=120,
            redact_environment_names=redact_environment_names,
        )
        completed = subprocess.run(
            guard_command,
            cwd=repo_root,
            env=_child_environment(child_environment),
            capture_output=True,
            text=True,
            check=False,
        )
        for path in (output_dir / "events.jsonl", output_dir / "stderr.jsonl"):
            _sanitize_log(path, sensitive_values)
        try:
            event_text = (output_dir / "events.jsonl").read_text(encoding="utf-8")
            telemetry = parse_codex_jsonl(event_text)
            events = _decoded_inner_events(output_dir / "events.jsonl")
            answer_matched = _agent_text(events).strip() == nonce
            usage_nonzero = sum(asdict(telemetry.usage).values()) > 0
            tool_contract = (
                telemetry.tool_calls == 0
                if kind == "plain-text"
                else telemetry.tool_calls == telemetry.successful_tool_calls == 1
            )
            telemetry_error = None
        except (OSError, UnicodeError, ValueError) as error:
            telemetry = None
            answer_matched = False
            usage_nonzero = False
            tool_contract = False
            telemetry_error = f"{type(error).__name__}: {error}"
        guard_reason = _read_guard_reason(output_dir / "guard-summary.json")
        passed = bool(
            completed.returncode == 0
            and guard_reason == "completed"
            and telemetry is not None
            and telemetry.usage_complete
            and not telemetry.failed
            and telemetry.wall_time_ms is not None
            and usage_nonzero
            and answer_matched
            and tool_contract
        )
        return {
            "passed": passed,
            "exit_code": completed.returncode,
            "guard_reason": guard_reason,
            "usage_complete": bool(telemetry and telemetry.usage_complete),
            "telemetry_failed": bool(telemetry is None or telemetry.failed),
            "telemetry_errors": (
                list(telemetry.errors) if telemetry is not None else []
            ),
            "usage": asdict(telemetry.usage) if telemetry is not None else None,
            "requests": (
                [
                    {
                        "source_id": request.source_id,
                        "usage": asdict(request.usage),
                        "usage_granularity": request.usage_granularity,
                    }
                    for request in telemetry.requests
                ]
                if telemetry is not None
                else []
            ),
            "request_count": len(telemetry.requests) if telemetry is not None else 0,
            "tool_calls": telemetry.tool_calls if telemetry is not None else 0,
            "successful_tool_calls": (
                telemetry.successful_tool_calls if telemetry is not None else 0
            ),
            "answer_matched": answer_matched,
            "wall_time_ms": (
                telemetry.wall_time_ms if telemetry is not None else None
            ),
            "telemetry_error": telemetry_error,
            "evidence_dir": str(output_dir),
        }
    finally:
        if workspace.exists():
            shutil.rmtree(workspace)


def _decimal_text(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _usage_value(value: object) -> NormalizedUsage:
    if not isinstance(value, dict):
        raise ValueError("canary usage must be an object")
    expected = {
        "uncached_input",
        "cached_input",
        "cache_write_input",
        "output",
        "reasoning_output",
    }
    if set(value) != expected:
        raise ValueError("canary usage fields do not match the normalized contract")
    return NormalizedUsage(**value)


def _normalized_canary_attempt(
    configuration: BenchmarkConfiguration,
    kind: str,
    index: int,
    canary_id: str,
    value: object,
    *,
    fallback_wall_time_ms: float | None = None,
) -> dict[str, object]:
    source = value if isinstance(value, dict) else {}
    request_values = source.get("requests")
    request_rows: list[dict[str, object]] = []
    request_usages: list[NormalizedUsage] = []
    request_granularities: list[str] = []
    requests_valid = isinstance(request_values, list)
    if requests_valid:
        try:
            for request in request_values:
                if not isinstance(request, dict):
                    raise ValueError("canary request must be an object")
                usage = _usage_value(request.get("usage"))
                source_id = request.get("source_id")
                if source_id is not None and not isinstance(source_id, str):
                    raise ValueError("canary request source_id must be a string or null")
                granularity_value = request.get("usage_granularity")
                granularity = (
                    "turn-aggregate"
                    if granularity_value is None
                    else granularity_value
                )
                if granularity not in {"request", "turn-aggregate"}:
                    raise ValueError("canary request granularity is invalid")
                request_usages.append(usage)
                request_granularities.append(granularity)
                row: dict[str, object] = {
                    "source_id": source_id,
                    "usage": asdict(usage),
                }
                if granularity_value is not None:
                    row["usage_granularity"] = granularity
                request_rows.append(row)
        except (TypeError, ValueError):
            requests_valid = False
            request_rows = []
            request_usages = []
            request_granularities = []

    aggregate = NormalizedUsage()
    for usage in request_usages:
        aggregate = aggregate + usage
    try:
        reported_usage = _usage_value(source.get("usage"))
        usage_matches = reported_usage == aggregate
    except (TypeError, ValueError):
        reported_usage = None
        usage_matches = False

    usage_complete = source.get("usage_complete") is True
    telemetry_failed_value = source.get("telemetry_failed")
    telemetry_failed = (
        telemetry_failed_value
        if isinstance(telemetry_failed_value, bool)
        else True
    )
    telemetry_errors_value = source.get("telemetry_errors")
    telemetry_errors = (
        list(telemetry_errors_value)
        if isinstance(telemetry_errors_value, list)
        and all(isinstance(error, str) for error in telemetry_errors_value)
        else ["invalid-or-missing-telemetry-errors"]
    )
    billing = calculate_attempt_billing(
        configuration,
        request_usages,
        usage_granularities=request_granularities,
        usage_complete=usage_complete and requests_valid and usage_matches,
        usage_scope="all-agent-threads",
    )
    wall_value = source.get("wall_time_ms")
    if (
        not isinstance(wall_value, (int, float))
        or isinstance(wall_value, bool)
        or not math.isfinite(float(wall_value))
        or wall_value <= 0
    ):
        wall_value = fallback_wall_time_ms
    wall_valid = (
        isinstance(wall_value, (int, float))
        and not isinstance(wall_value, bool)
        and math.isfinite(float(wall_value))
        and wall_value > 0
    )
    request_count = source.get("request_count")
    exit_code = source.get("exit_code")
    tool_calls = source.get("tool_calls")
    successful_tool_calls = source.get("successful_tool_calls")
    expected_tools = 0 if kind == "plain-text" else 1
    passed = bool(
        isinstance(exit_code, int)
        and not isinstance(exit_code, bool)
        and exit_code == 0
        and source.get("guard_reason") == "completed"
        and usage_complete
        and telemetry_failed is False
        and not telemetry_errors
        and requests_valid
        and usage_matches
        and isinstance(request_count, int)
        and not isinstance(request_count, bool)
        and request_count == len(request_rows)
        and request_count > 0
        and sum(asdict(aggregate).values()) > 0
        and isinstance(tool_calls, int)
        and not isinstance(tool_calls, bool)
        and tool_calls == expected_tools
        and isinstance(successful_tool_calls, int)
        and not isinstance(successful_tool_calls, bool)
        and successful_tool_calls == expected_tools
        and source.get("answer_matched") is True
        and source.get("telemetry_error") is None
        and source.get("execution_error") is None
        and wall_valid
        and billing.get("status") == "complete"
    )
    telemetry_error = source.get("telemetry_error")
    if telemetry_error is not None and not isinstance(telemetry_error, str):
        telemetry_error = "invalid-telemetry-error"
    evidence_dir = source.get("evidence_dir")
    if evidence_dir is not None and not isinstance(evidence_dir, str):
        evidence_dir = None
    execution_error = source.get("execution_error")
    if execution_error is not None and not isinstance(execution_error, str):
        execution_error = "invalid-execution-error"
    return {
        "index": index,
        "canary_id": canary_id,
        "passed": passed,
        "exit_code": exit_code if isinstance(exit_code, int) else None,
        "guard_reason": source.get("guard_reason"),
        "usage_complete": usage_complete,
        "telemetry_failed": telemetry_failed,
        "telemetry_errors": telemetry_errors,
        "usage": asdict(reported_usage) if reported_usage is not None else None,
        "requests": request_rows,
        "request_count": request_count if isinstance(request_count, int) else 0,
        "tool_calls": tool_calls if isinstance(tool_calls, int) else 0,
        "successful_tool_calls": (
            successful_tool_calls
            if isinstance(successful_tool_calls, int)
            else 0
        ),
        "answer_matched": source.get("answer_matched") is True,
        "wall_time_ms": float(wall_value) if wall_valid else None,
        "billing": billing,
        "telemetry_error": telemetry_error,
        "execution_error": execution_error,
        "evidence_dir": evidence_dir,
    }


def _compatibility_overhead(models: Mapping[str, object]) -> dict[str, object]:
    attempts: list[dict[str, object]] = []
    for model_value in models.values():
        if not isinstance(model_value, dict):
            continue
        for kind in _CANARY_KINDS:
            group = model_value.get(kind)
            values = group.get("attempts") if isinstance(group, dict) else None
            if isinstance(values, list):
                attempts.extend(item for item in values if isinstance(item, dict))
    known = 0
    cny = Decimal(0)
    token_input = 0
    token_output = 0
    wall_time = Decimal(0)
    for attempt in attempts:
        wall = attempt.get("wall_time_ms")
        if isinstance(wall, (int, float)) and not isinstance(wall, bool):
            wall_time += Decimal(str(wall))
        billing = attempt.get("billing")
        totals = billing.get("totals") if isinstance(billing, dict) else None
        if (
            not isinstance(billing, dict)
            or billing.get("status") != "complete"
            or not isinstance(totals, dict)
        ):
            continue
        known += 1
        cny += Decimal(str(totals.get("api_cost_cny", 0)))
        token_input += int(totals.get("minimax_token_plan_input_tokens", 0))
        token_output += int(totals.get("minimax_token_plan_output_tokens", 0))
    if not attempts or known == 0:
        billing_status = "unknown"
    elif known == len(attempts):
        billing_status = "complete"
    else:
        billing_status = "partial-known"
    return {
        "billing_status": billing_status,
        "physical_attempts": len(attempts),
        "physical_wall_time_ms": _decimal_text(wall_time),
        "api_cost_cny": _decimal_text(cny),
        "minimax_token_plan_input_tokens": token_input,
        "minimax_token_plan_output_tokens": token_output,
    }


def _openai_proxy_overhead(
    canaries: Mapping[str, object],
) -> dict[str, object]:
    attempts = [
        value.get("attempt")
        for value in canaries.values()
        if isinstance(value, dict) and isinstance(value.get("attempt"), dict)
    ]
    known = 0
    usd = Decimal(0)
    credits = Decimal(0)
    wall_time = Decimal(0)
    for attempt_value in attempts:
        assert isinstance(attempt_value, dict)
        wall = attempt_value.get("wall_time_ms")
        if isinstance(wall, (int, float)) and not isinstance(wall, bool):
            wall_time += Decimal(str(wall))
        billing = attempt_value.get("billing")
        totals = billing.get("totals") if isinstance(billing, dict) else None
        if (
            not isinstance(billing, dict)
            or billing.get("status") != "complete"
            or not isinstance(totals, dict)
            or totals.get("api_cost_usd") is None
            or totals.get("codex_credits_estimate") is None
        ):
            continue
        known += 1
        usd += Decimal(str(totals["api_cost_usd"]))
        credits += Decimal(str(totals["codex_credits_estimate"]))
    if not attempts or known == 0:
        billing_status = "unknown"
    elif known == len(attempts):
        billing_status = "complete"
    else:
        billing_status = "partial-known"
    return {
        "billing_status": billing_status,
        "physical_attempts": len(attempts),
        "physical_wall_time_ms": _decimal_text(wall_time),
        "api_cost_usd": _decimal_text(usd),
        "codex_credits_estimate": _decimal_text(credits),
    }


def run_openai_proxy_compatibility(
    *,
    repo_root: Path,
    output_root: Path,
    static_preflight: Mapping[str, object] | None = None,
    attempt_executor: Callable[..., dict[str, object]] | None = None,
    created_at: str | None = None,
    allow_plaintext_auth_relay: bool = False,
) -> dict[str, object]:
    """Run one plain-text canary per GPT slug plus the Ultra app-server path."""

    static = (
        collect_openai_proxy_static_preflight()
        if static_preflight is None
        else dict(static_preflight)
    )
    if static.get("compatible") is True and allow_plaintext_auth_relay is not True:
        raise ValueError(
            "OpenAI proxy compatibility requires explicit plaintext auth relay authorization"
        )
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    executor = _actual_canary_attempt if attempt_executor is None else attempt_executor
    configuration_by_id = {
        item.id: item for item in benchmark_matrix() if item.provider == "openai"
    }
    canaries: dict[str, object] = {}
    if static.get("compatible") is True:
        for configuration_id, kind in _OPENAI_PROXY_CANARY_CASES:
            configuration = configuration_by_id[configuration_id]
            nonce = (
                "BENCH_"
                + hashlib.sha256(
                    f"{configuration.id}:{secrets.token_hex(8)}".encode("utf-8")
                ).hexdigest()[:20]
            )
            canary_id = _sha256_bytes(
                f"{configuration.id}:{kind}:1:{nonce}".encode("utf-8")
            )
            started_ns = time.monotonic_ns()
            try:
                raw_result = executor(
                    repo_root=Path(repo_root).resolve(),
                    output_dir=output_root / configuration.id,
                    configuration=configuration,
                    credential=None,
                    kind=kind,
                    index=1,
                    nonce=nonce,
                )
            except Exception:
                raw_result = {
                    "execution_error": "attempt-executor-raised",
                    "guard_reason": "executor-error",
                }
            elapsed_ms = (time.monotonic_ns() - started_ns) / 1_000_000
            result = _normalized_canary_attempt(
                configuration,
                kind,
                1,
                canary_id,
                _redact_object(raw_result, ()),
                fallback_wall_time_ms=elapsed_ms,
            )
            canaries[configuration_id] = {
                "configuration": asdict(configuration),
                "attempt": result,
            }

    compatible = bool(
        static.get("compatible") is True
        and set(canaries) == set(_OPENAI_PROXY_CANARY_CONFIGURATION_IDS)
        and all(
            isinstance(value, dict)
            and isinstance(value.get("attempt"), dict)
            and value["attempt"].get("passed") is True
            for value in canaries.values()
        )
    )
    receipt: dict[str, object] = {
        "schema": OPENAI_PROXY_COMPATIBILITY_SCHEMA,
        "receipt_id": "",
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "compatible": compatible,
        "plaintext_auth_relay_authorized": allow_plaintext_auth_relay is True,
        "static_preflight": static,
        "provider_contract": openai_proxy_provider_contract(),
        "canary_policy": {
            "repetitions": 1,
            "cases": [
                {"configuration_id": configuration_id, "kind": kind}
                for configuration_id, kind in _OPENAI_PROXY_CANARY_CASES
            ],
        },
        "canaries": canaries,
        "overhead": _openai_proxy_overhead(canaries),
    }
    receipt["receipt_id"] = _receipt_id(receipt)
    serialized = json.dumps(
        receipt, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"
    temporary = output_root / "receipt.json.tmp"
    temporary.write_text(serialized, encoding="utf-8")
    os.replace(temporary, output_root / "receipt.json")
    return receipt


def validate_openai_proxy_compatibility_receipt(
    receipt: object,
    *,
    expected_codex_sha256: str | None = None,
) -> dict[str, object]:
    if not isinstance(receipt, dict):
        raise ValueError("OpenAI proxy compatibility receipt must be an object")
    if receipt.get("schema") != OPENAI_PROXY_COMPATIBILITY_SCHEMA:
        raise ValueError("OpenAI proxy compatibility receipt schema mismatch")
    if receipt.get("receipt_id") != _receipt_id(receipt):
        raise ValueError("OpenAI proxy compatibility receipt hash mismatch")
    if receipt.get("compatible") is not True:
        raise ValueError("OpenAI proxy compatibility gate did not pass")
    if receipt.get("plaintext_auth_relay_authorized") is not True:
        raise ValueError("OpenAI proxy plaintext auth relay was not authorized")
    if receipt.get("provider_contract") != openai_proxy_provider_contract():
        raise ValueError("OpenAI proxy provider contract drifted after gate")
    static = receipt.get("static_preflight")
    codex = static.get("codex") if isinstance(static, dict) else None
    capabilities = static.get("capabilities") if isinstance(static, dict) else None
    config_probe = static.get("config_probe") if isinstance(static, dict) else None
    command_checks = (
        static.get("command_checks") if isinstance(static, dict) else None
    )
    if (
        not isinstance(static, dict)
        or static.get("compatible") is not True
        or not isinstance(codex, dict)
        or not isinstance(capabilities, dict)
        or set(capabilities) != set(_REQUIRED_EXEC_FLAGS)
        or any(capabilities.get(flag) is not True for flag in _REQUIRED_EXEC_FLAGS)
        or command_checks
        != {"version_returncode": 0, "help_returncode": 0}
        or not isinstance(config_probe, dict)
        or config_probe.get("returncode") != 0
    ):
        raise ValueError("OpenAI proxy compatibility static preflight is invalid")
    codex_path = codex.get("path")
    codex_hash = codex.get("sha256")
    codex_version = codex.get("version")
    probe_hash = config_probe.get("output_sha256")
    if (
        not isinstance(codex_path, str)
        or not Path(codex_path).is_absolute()
        or not isinstance(codex_hash, str)
        or len(codex_hash) != 64
        or any(character not in "0123456789abcdef" for character in codex_hash)
        or not isinstance(codex_version, str)
        or not codex_version.strip()
        or not isinstance(probe_hash, str)
        or len(probe_hash) != 64
        or any(character not in "0123456789abcdef" for character in probe_hash)
    ):
        raise ValueError("OpenAI proxy compatibility Codex identity is invalid")
    expected_hash = expected_codex_sha256
    if expected_hash is None:
        expected_hash = _sha256_bytes(resolve_codex_executable().read_bytes())
    if codex_hash != expected_hash:
        raise ValueError("OpenAI proxy receipt targets a different Codex binary")
    expected_policy = {
        "repetitions": 1,
        "cases": [
            {"configuration_id": configuration_id, "kind": kind}
            for configuration_id, kind in _OPENAI_PROXY_CANARY_CASES
        ],
    }
    if receipt.get("canary_policy") != expected_policy:
        raise ValueError("OpenAI proxy canary policy mismatch")
    canaries = receipt.get("canaries")
    if not isinstance(canaries, dict) or set(canaries) != set(
        _OPENAI_PROXY_CANARY_CONFIGURATION_IDS
    ):
        raise ValueError("OpenAI proxy canary set mismatch")
    configuration_by_id = {
        item.id: item for item in benchmark_matrix() if item.provider == "openai"
    }
    seen_canary_ids: set[str] = set()
    for configuration_id, kind in _OPENAI_PROXY_CANARY_CASES:
        value = canaries[configuration_id]
        configuration = configuration_by_id[configuration_id]
        attempt = value.get("attempt") if isinstance(value, dict) else None
        if (
            not isinstance(value, dict)
            or value.get("configuration") != asdict(configuration)
            or not isinstance(attempt, dict)
        ):
            raise ValueError(f"OpenAI proxy canary binding failed for {configuration_id}")
        canary_id = attempt.get("canary_id")
        if (
            not isinstance(canary_id, str)
            or len(canary_id) != 64
            or any(character not in "0123456789abcdef" for character in canary_id)
            or canary_id in seen_canary_ids
        ):
            raise ValueError(f"OpenAI proxy canary identity failed for {configuration_id}")
        seen_canary_ids.add(canary_id)
        normalized = _normalized_canary_attempt(
            configuration,
            kind,
            1,
            canary_id,
            attempt,
        )
        if normalized != attempt or attempt.get("passed") is not True:
            raise ValueError(f"OpenAI proxy canary failed for {configuration_id}")
    if receipt.get("overhead") != _openai_proxy_overhead(canaries):
        raise ValueError("OpenAI proxy overhead does not match canary evidence")
    return receipt


def run_openai_native_compatibility(
    *,
    repo_root: Path,
    output_root: Path,
    static_preflight: Mapping[str, object] | None = None,
    attempt_executor: Callable[..., dict[str, object]] | None = None,
    created_at: str | None = None,
) -> dict[str, object]:
    """Gate the exact reduced matrix through the local Codex native provider."""

    static = (
        collect_openai_native_static_preflight()
        if static_preflight is None
        else dict(static_preflight)
    )
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    executor = _actual_canary_attempt if attempt_executor is None else attempt_executor
    configurations = {
        configuration_id: benchmark_configuration(
            configuration_id,
            openai_transport_profile=CODEX_NATIVE_TRANSPORT_PROFILE,
        )
        for configuration_id in _OPENAI_NATIVE_CANARY_CONFIGURATION_IDS
    }
    canaries: dict[str, object] = {}
    if static.get("compatible") is True:
        for configuration_id, kind in _OPENAI_NATIVE_CANARY_CASES:
            configuration = configurations[configuration_id]
            nonce = (
                "BENCH_"
                + hashlib.sha256(
                    f"{configuration.id}:{secrets.token_hex(8)}".encode("utf-8")
                ).hexdigest()[:20]
            )
            canary_id = _sha256_bytes(
                f"{configuration.id}:{kind}:1:{nonce}".encode("utf-8")
            )
            started_ns = time.monotonic_ns()
            try:
                raw_result = executor(
                    repo_root=Path(repo_root).resolve(),
                    output_dir=output_root / configuration.id,
                    configuration=configuration,
                    credential=None,
                    kind=kind,
                    index=1,
                    nonce=nonce,
                )
            except Exception:
                raw_result = {
                    "execution_error": "attempt-executor-raised",
                    "guard_reason": "executor-error",
                }
            elapsed_ms = (time.monotonic_ns() - started_ns) / 1_000_000
            result = _normalized_canary_attempt(
                configuration,
                kind,
                1,
                canary_id,
                _redact_object(raw_result, ()),
                fallback_wall_time_ms=elapsed_ms,
            )
            canaries[configuration_id] = {
                "configuration": asdict(configuration),
                "attempt": result,
            }

    compatible = bool(
        static.get("compatible") is True
        and set(canaries) == set(_OPENAI_NATIVE_CANARY_CONFIGURATION_IDS)
        and all(
            isinstance(value, dict)
            and isinstance(value.get("attempt"), dict)
            and value["attempt"].get("passed") is True
            for value in canaries.values()
        )
    )
    receipt: dict[str, object] = {
        "schema": OPENAI_NATIVE_COMPATIBILITY_SCHEMA,
        "receipt_id": "",
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "compatible": compatible,
        "static_preflight": static,
        "provider_contract": openai_native_provider_contract(),
        "canary_policy": {
            "repetitions": 1,
            "cases": [
                {"configuration_id": configuration_id, "kind": kind}
                for configuration_id, kind in _OPENAI_NATIVE_CANARY_CASES
            ],
        },
        "canaries": canaries,
        "overhead": _openai_proxy_overhead(canaries),
    }
    receipt["receipt_id"] = _receipt_id(receipt)
    serialized = json.dumps(
        receipt, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"
    temporary = output_root / "receipt.json.tmp"
    temporary.write_text(serialized, encoding="utf-8")
    os.replace(temporary, output_root / "receipt.json")
    return receipt


def validate_openai_native_compatibility_receipt(
    receipt: object,
    *,
    expected_codex_sha256: str | None = None,
) -> dict[str, object]:
    if not isinstance(receipt, dict):
        raise ValueError("OpenAI native compatibility receipt must be an object")
    if receipt.get("schema") != OPENAI_NATIVE_COMPATIBILITY_SCHEMA:
        raise ValueError("OpenAI native compatibility receipt schema mismatch")
    if receipt.get("receipt_id") != _receipt_id(receipt):
        raise ValueError("OpenAI native compatibility receipt hash mismatch")
    if receipt.get("compatible") is not True:
        raise ValueError("OpenAI native compatibility gate did not pass")
    if receipt.get("provider_contract") != openai_native_provider_contract():
        raise ValueError("OpenAI native provider contract drifted after gate")
    static = receipt.get("static_preflight")
    codex = static.get("codex") if isinstance(static, dict) else None
    capabilities = static.get("capabilities") if isinstance(static, dict) else None
    config_probe = static.get("config_probe") if isinstance(static, dict) else None
    command_checks = (
        static.get("command_checks") if isinstance(static, dict) else None
    )
    if (
        not isinstance(static, dict)
        or static.get("compatible") is not True
        or not isinstance(codex, dict)
        or not isinstance(capabilities, dict)
        or set(capabilities) != set(_REQUIRED_EXEC_FLAGS)
        or any(capabilities.get(flag) is not True for flag in _REQUIRED_EXEC_FLAGS)
        or command_checks != {"version_returncode": 0, "help_returncode": 0}
        or not isinstance(config_probe, dict)
        or config_probe.get("returncode") != 0
    ):
        raise ValueError("OpenAI native compatibility static preflight is invalid")
    codex_path = codex.get("path")
    codex_hash = codex.get("sha256")
    codex_version = codex.get("version")
    probe_hash = config_probe.get("output_sha256")
    if (
        not isinstance(codex_path, str)
        or not Path(codex_path).is_absolute()
        or not isinstance(codex_hash, str)
        or len(codex_hash) != 64
        or any(character not in "0123456789abcdef" for character in codex_hash)
        or not isinstance(codex_version, str)
        or not codex_version.strip()
        or not isinstance(probe_hash, str)
        or len(probe_hash) != 64
        or any(character not in "0123456789abcdef" for character in probe_hash)
    ):
        raise ValueError("OpenAI native compatibility Codex identity is invalid")
    expected_hash = expected_codex_sha256
    if expected_hash is None:
        expected_hash = _sha256_bytes(resolve_codex_executable().read_bytes())
    if codex_hash != expected_hash:
        raise ValueError("OpenAI native receipt targets a different Codex binary")
    expected_policy = {
        "repetitions": 1,
        "cases": [
            {"configuration_id": configuration_id, "kind": kind}
            for configuration_id, kind in _OPENAI_NATIVE_CANARY_CASES
        ],
    }
    if receipt.get("canary_policy") != expected_policy:
        raise ValueError("OpenAI native canary policy mismatch")
    canaries = receipt.get("canaries")
    if not isinstance(canaries, dict) or set(canaries) != set(
        _OPENAI_NATIVE_CANARY_CONFIGURATION_IDS
    ):
        raise ValueError("OpenAI native canary set mismatch")
    configurations = {
        configuration_id: benchmark_configuration(
            configuration_id,
            openai_transport_profile=CODEX_NATIVE_TRANSPORT_PROFILE,
        )
        for configuration_id in _OPENAI_NATIVE_CANARY_CONFIGURATION_IDS
    }
    seen_canary_ids: set[str] = set()
    for configuration_id, kind in _OPENAI_NATIVE_CANARY_CASES:
        value = canaries[configuration_id]
        configuration = configurations[configuration_id]
        attempt = value.get("attempt") if isinstance(value, dict) else None
        if (
            not isinstance(value, dict)
            or value.get("configuration") != asdict(configuration)
            or not isinstance(attempt, dict)
        ):
            raise ValueError(f"OpenAI native canary binding failed for {configuration_id}")
        canary_id = attempt.get("canary_id")
        if (
            not isinstance(canary_id, str)
            or len(canary_id) != 64
            or any(character not in "0123456789abcdef" for character in canary_id)
            or canary_id in seen_canary_ids
        ):
            raise ValueError(f"OpenAI native canary identity failed for {configuration_id}")
        seen_canary_ids.add(canary_id)
        normalized = _normalized_canary_attempt(
            configuration,
            kind,
            1,
            canary_id,
            attempt,
        )
        if normalized != attempt or attempt.get("passed") is not True:
            raise ValueError(f"OpenAI native canary failed for {configuration_id}")
    if receipt.get("overhead") != _openai_proxy_overhead(canaries):
        raise ValueError("OpenAI native overhead does not match canary evidence")
    return receipt


def validate_compatibility_receipt_set(
    receipts: object,
    *,
    expected_receipt_ids: Mapping[str, object] | None = None,
    expected_provider_contracts: Mapping[str, object] | None = None,
    expected_codex_sha256: str | None = None,
) -> dict[str, dict[str, object]]:
    """Validate the exact selected-provider gate set against one Codex binary."""

    allowed_provider_keys = {"openai", "minimax"}
    if (
        not isinstance(receipts, dict)
        or not receipts
        or not set(receipts).issubset(allowed_provider_keys)
    ):
        raise ValueError("compatibility receipt set contains invalid providers")
    provider_keys = set(receipts)
    if expected_receipt_ids is not None and (
        not isinstance(expected_receipt_ids, Mapping)
        or set(expected_receipt_ids) != provider_keys
    ):
        raise ValueError("expected receipt ids must match selected providers")
    if expected_provider_contracts is not None and (
        not isinstance(expected_provider_contracts, Mapping)
        or set(expected_provider_contracts) != provider_keys
    ):
        raise ValueError(
            "expected provider contracts must match selected providers"
        )
    codex_sha256 = expected_codex_sha256
    if codex_sha256 is None:
        codex_sha256 = _sha256_bytes(resolve_codex_executable().read_bytes())
    openai_receipt = receipts.get("openai")
    openai_schema = (
        openai_receipt.get("schema")
        if isinstance(openai_receipt, dict)
        else None
    )
    openai_validator = (
        validate_openai_native_compatibility_receipt
        if openai_schema == OPENAI_NATIVE_COMPATIBILITY_SCHEMA
        else validate_openai_proxy_compatibility_receipt
    )
    validators = {
        "openai": openai_validator,
        "minimax": validate_minimax_compatibility_receipt,
    }
    validated = {
        provider: validators[provider](
            receipts[provider], expected_codex_sha256=codex_sha256
        )
        for provider in ("openai", "minimax")
        if provider in provider_keys
    }
    if expected_receipt_ids is not None:
        actual_ids = {
            provider: receipt.get("receipt_id")
            for provider, receipt in validated.items()
        }
        if actual_ids != dict(expected_receipt_ids):
            raise ValueError("compatibility receipt ids do not match the frozen plan")
    if expected_provider_contracts is not None:
        actual_contracts = {
            provider: receipt.get("provider_contract")
            for provider, receipt in validated.items()
        }
        if actual_contracts != dict(expected_provider_contracts):
            raise ValueError("compatibility provider contracts do not match the frozen plan")
    return validated


def run_minimax_compatibility(
    *,
    repo_root: Path,
    output_root: Path,
    credential: LoadedCredential,
    static_preflight: Mapping[str, object] | None = None,
    attempt_executor: Callable[..., dict[str, object]] | None = None,
    created_at: str | None = None,
) -> dict[str, object]:
    """Run the frozen 2 × (3 text + 3 tool) MiniMax compatibility matrix."""

    static = (
        collect_static_preflight()
        if static_preflight is None
        else dict(static_preflight)
    )
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    executor = _actual_canary_attempt if attempt_executor is None else attempt_executor
    models: dict[str, object] = {}
    configurations = [item for item in benchmark_matrix() if item.provider == "minimax"]
    if static.get("compatible") is True:
        for configuration in configurations:
            groups: dict[str, object] = {}
            for kind in _CANARY_KINDS:
                attempts: list[dict[str, object]] = []
                for index in range(1, _CANARY_REPETITIONS + 1):
                    nonce = (
                        "BENCH_"
                        + hashlib.sha256(
                            f"{configuration.model}:{kind}:{index}:{secrets.token_hex(8)}".encode()
                        ).hexdigest()[:20]
                    )
                    canary_id = _sha256_bytes(
                        f"{configuration.model}:{kind}:{index}:{nonce}".encode(
                            "utf-8"
                        )
                    )
                    started_ns = time.monotonic_ns()
                    try:
                        raw_result = executor(
                            repo_root=Path(repo_root).resolve(),
                            output_dir=output_root
                            / configuration.model
                            / kind
                            / str(index),
                            configuration=configuration,
                            credential=credential,
                            kind=kind,
                            index=index,
                            nonce=nonce,
                        )
                    except Exception:
                        raw_result = {
                            "execution_error": "attempt-executor-raised",
                            "guard_reason": "executor-error",
                        }
                    elapsed_ms = (time.monotonic_ns() - started_ns) / 1_000_000
                    result = _normalized_canary_attempt(
                        configuration,
                        kind,
                        index,
                        canary_id,
                        _redact_object(raw_result, (credential.value,)),
                        fallback_wall_time_ms=elapsed_ms,
                    )
                    attempts.append(result)
                groups[kind] = {
                    "required": _CANARY_REPETITIONS,
                    "passed": sum(item.get("passed") is True for item in attempts),
                    "attempts": attempts,
                }
            model_compatible = all(
                isinstance(groups[kind], dict)
                and groups[kind]["passed"] == _CANARY_REPETITIONS
                for kind in _CANARY_KINDS
            )
            models[configuration.model] = {
                "harness": "codex-responses",
                "compatible": model_compatible,
                **groups,
            }

    expected_models = {item.model for item in configurations}
    compatible = bool(
        static.get("compatible") is True
        and set(models) == expected_models
        and all(
            isinstance(value, dict) and value.get("compatible") is True
            for value in models.values()
        )
    )
    receipt: dict[str, object] = {
        "schema": COMPATIBILITY_SCHEMA,
        "receipt_id": "",
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "compatible": compatible,
        "credential_source": credential.source,
        "static_preflight": static,
        "provider_contract": minimax_provider_contract(),
        "models": models,
        "overhead": _compatibility_overhead(models),
        "pi_fallback": {
            "enabled": False,
            "reason": (
                "Pi does not provide a proved workspace sandbox and tool-child "
                "credential isolation for this campaign"
            ),
        },
    }
    receipt["receipt_id"] = _receipt_id(receipt)
    serialized = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if credential.value in serialized:
        raise ValueError("credential appeared in compatibility receipt")
    temporary = output_root / "receipt.json.tmp"
    temporary.write_text(serialized, encoding="utf-8")
    os.replace(temporary, output_root / "receipt.json")
    return receipt


def validate_minimax_compatibility_receipt(
    receipt: object,
    *,
    expected_codex_sha256: str | None = None,
) -> dict[str, object]:
    if not isinstance(receipt, dict):
        raise ValueError("compatibility receipt must be an object")
    if receipt.get("schema") != COMPATIBILITY_SCHEMA:
        raise ValueError("compatibility receipt schema mismatch")
    if receipt.get("receipt_id") != _receipt_id(receipt):
        raise ValueError("compatibility receipt hash mismatch")
    if receipt.get("compatible") is not True:
        raise ValueError("MiniMax compatibility gate did not pass")
    if receipt.get("provider_contract") != minimax_provider_contract():
        raise ValueError("MiniMax provider contract drifted after compatibility gate")
    static = receipt.get("static_preflight")
    if not isinstance(static, dict) or static.get("compatible") is not True:
        raise ValueError("compatibility receipt static preflight did not pass")
    codex = static.get("codex") if isinstance(static, dict) else None
    if not isinstance(codex, dict):
        raise ValueError("compatibility receipt has no Codex identity")
    codex_path = codex.get("path")
    codex_hash = codex.get("sha256")
    codex_version = codex.get("version")
    if (
        not isinstance(codex_path, str)
        or not Path(codex_path).is_absolute()
        or not isinstance(codex_hash, str)
        or len(codex_hash) != 64
        or any(character not in "0123456789abcdef" for character in codex_hash)
        or not isinstance(codex_version, str)
        or not codex_version.strip()
    ):
        raise ValueError("compatibility receipt Codex identity is invalid")
    capabilities = static.get("capabilities")
    if (
        not isinstance(capabilities, dict)
        or set(capabilities) != set(_REQUIRED_EXEC_FLAGS)
        or any(capabilities.get(flag) is not True for flag in _REQUIRED_EXEC_FLAGS)
    ):
        raise ValueError("compatibility receipt CLI capabilities are incomplete")
    command_checks = static.get("command_checks")
    if command_checks != {
        "version_returncode": 0,
        "help_returncode": 0,
    }:
        raise ValueError("compatibility receipt CLI command checks failed")
    config_probe = static.get("config_probe")
    probe_hash = (
        config_probe.get("output_sha256")
        if isinstance(config_probe, dict)
        else None
    )
    if (
        not isinstance(config_probe, dict)
        or config_probe.get("returncode") != 0
        or not isinstance(probe_hash, str)
        or len(probe_hash) != 64
        or any(character not in "0123456789abcdef" for character in probe_hash)
    ):
        raise ValueError("compatibility receipt config probe is invalid")
    pi_fallback = receipt.get("pi_fallback")
    if (
        not isinstance(pi_fallback, dict)
        or pi_fallback.get("enabled") is not False
        or not isinstance(pi_fallback.get("reason"), str)
        or not pi_fallback["reason"]
    ):
        raise ValueError("compatibility receipt must keep Pi fallback disabled")
    expected_hash = expected_codex_sha256
    if expected_hash is None:
        expected_hash = _sha256_bytes(resolve_codex_executable().read_bytes())
    if codex_hash != expected_hash:
        raise ValueError("compatibility receipt targets a different Codex binary")
    models = receipt.get("models")
    expected_models = {"MiniMax-M3", "MiniMax-M2.7-highspeed"}
    if not isinstance(models, dict) or set(models) != expected_models:
        raise ValueError("compatibility receipt model set mismatch")
    configurations = {
        item.model: item for item in benchmark_matrix() if item.provider == "minimax"
    }
    seen_canary_ids: set[str] = set()
    for model in expected_models:
        value = models[model]
        if (
            not isinstance(value, dict)
            or set(value) != {"harness", "compatible", *_CANARY_KINDS}
            or value.get("harness") != "codex-responses"
            or value.get("compatible") is not True
        ):
            raise ValueError(f"compatibility receipt failed for {model}")
        for kind in _CANARY_KINDS:
            group = value.get(kind)
            attempts = group.get("attempts") if isinstance(group, dict) else None
            if (
                not isinstance(attempts, list)
                or len(attempts) != _CANARY_REPETITIONS
                or group.get("required") != _CANARY_REPETITIONS
                or group.get("passed") != _CANARY_REPETITIONS
            ):
                raise ValueError(f"compatibility canary set is incomplete for {model}/{kind}")
            for index, attempt in enumerate(attempts, start=1):
                if not isinstance(attempt, dict):
                    raise ValueError(
                        f"compatibility canary is invalid for {model}/{kind}/{index}"
                    )
                canary_id = attempt.get("canary_id")
                if (
                    attempt.get("index") != index
                    or not isinstance(canary_id, str)
                    or len(canary_id) != 64
                    or any(
                        character not in "0123456789abcdef"
                        for character in canary_id
                    )
                    or canary_id in seen_canary_ids
                ):
                    raise ValueError(
                        f"compatibility canary identity is invalid for {model}/{kind}/{index}"
                    )
                seen_canary_ids.add(canary_id)
                normalized = _normalized_canary_attempt(
                    configurations[model],
                    kind,
                    index,
                    canary_id,
                    attempt,
                )
                if normalized != attempt or attempt.get("passed") is not True:
                    raise ValueError(
                        f"compatibility canary contract failed for {model}/{kind}/{index}"
                    )
    if receipt.get("overhead") != _compatibility_overhead(models):
        raise ValueError("compatibility overhead does not match canary evidence")
    return receipt
