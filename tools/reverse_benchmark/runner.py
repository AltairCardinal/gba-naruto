"""Safe command construction and run identities for the benchmark."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from .matrix import (
    CODEX_NATIVE_BENCHMARK_CONFIGURATION_IDS,
    CODEX_NATIVE_TRANSPORT_PROFILE,
    OPENAI_PROXY_TRANSPORT_PROFILE,
    BenchmarkConfiguration,
    benchmark_configuration,
    benchmark_matrix,
)


MINIMAX_BASE_URL = "https://api.minimaxi.com/v1"
MINIMAX_ENV_KEY = "BENCH_MINIMAX_API_KEY"
OPENAI_PROXY_BASE_URL = "http://tokyo.kibox.com.cn:8787/v1"
OPENAI_PROXY_PROVIDER_ID = "benchmark_openai_proxy"
CODEX_NATIVE_PROVIDER_ID = "openai"
CODEX_NATIVE_HTTP_PROVIDER_ID = "benchmark_codex_native_http"
CODEX_NATIVE_HTTP_BASE_URL = "https://chatgpt.com/backend-api/codex"
CODEX_NATIVE_HTTP_PROVIDER_NAME = "Codex native HTTPS fallback"
_BUNDLED_CODEX = Path("/Applications/ChatGPT.app/Contents/Resources/codex")


def resolve_codex_executable() -> Path:
    """Resolve one explicit Codex binary so PATH changes cannot alter a run."""

    if _BUNDLED_CODEX.is_file():
        return _BUNDLED_CODEX.resolve()
    discovered = shutil.which("codex")
    if discovered is None:
        raise FileNotFoundError("Codex executable not found")
    return Path(discovered).resolve()


def new_run_id() -> str:
    """Return an opaque 128-bit run identifier."""

    return secrets.token_hex(16)


def _config(key: str, value: object) -> list[str]:
    if isinstance(value, (str, list, dict)):
        rendered = json.dumps(value, ensure_ascii=False)
    elif isinstance(value, bool):
        rendered = "true" if value else "false"
    else:
        rendered = str(value)
    return ["-c", f"{key}={rendered}"]


def openai_proxy_config_args() -> list[str]:
    """Return the secret-free frozen custom-provider command arguments."""

    provider = OPENAI_PROXY_PROVIDER_ID
    command: list[str] = []
    command.extend(_config("model_provider", provider))
    command.extend(
        _config(f"model_providers.{provider}.name", "OpenAI benchmark proxy")
    )
    command.extend(
        _config(f"model_providers.{provider}.base_url", OPENAI_PROXY_BASE_URL)
    )
    command.extend(_config(f"model_providers.{provider}.wire_api", "responses"))
    command.extend(
        _config(f"model_providers.{provider}.requires_openai_auth", True)
    )
    command.extend(_config(f"model_providers.{provider}.request_max_retries", 0))
    command.extend(_config(f"model_providers.{provider}.stream_max_retries", 0))
    return command


def codex_native_http_config_args() -> list[str]:
    """Return the official HTTPS fallback used by native Ultra app-server."""

    provider = CODEX_NATIVE_HTTP_PROVIDER_ID
    command: list[str] = []
    command.extend(_config("model_provider", provider))
    command.extend(
        _config(
            f"model_providers.{provider}.name",
            CODEX_NATIVE_HTTP_PROVIDER_NAME,
        )
    )
    command.extend(
        _config(f"model_providers.{provider}.base_url", CODEX_NATIVE_HTTP_BASE_URL)
    )
    command.extend(_config(f"model_providers.{provider}.wire_api", "responses"))
    command.extend(
        _config(f"model_providers.{provider}.requires_openai_auth", True)
    )
    command.extend(
        _config(f"model_providers.{provider}.supports_websockets", False)
    )
    command.extend(_config(f"model_providers.{provider}.request_max_retries", 0))
    command.extend(_config(f"model_providers.{provider}.stream_max_retries", 0))
    return command


def openai_proxy_provider_contract() -> dict[str, object]:
    """Describe the frozen proxy transport without loading authentication data."""

    models: dict[str, dict[str, object]] = {}
    for configuration in benchmark_matrix():
        if configuration.provider != "openai":
            continue
        model = models.setdefault(
            configuration.model,
            {
                "context_window": configuration.context_window,
                "efforts": [],
            },
        )
        efforts = model["efforts"]
        assert isinstance(efforts, list)
        efforts.append(configuration.effort)
    return {
        "provider_id": OPENAI_PROXY_PROVIDER_ID,
        "base_url": OPENAI_PROXY_BASE_URL,
        "wire_api": "responses",
        "requires_openai_auth": True,
        "transport_security": "plaintext-http-user-authorized",
        "credential_relay_scope": "third-party-remote",
        "model_catalog": "bundled-codex",
        "request_max_retries": 0,
        "stream_max_retries": 0,
        "models": models,
    }


def openai_native_provider_contract() -> dict[str, object]:
    """Describe local Codex's native provider without persisting auth or endpoint data."""

    models: dict[str, dict[str, object]] = {}
    for configuration in benchmark_matrix():
        if configuration.id not in CODEX_NATIVE_BENCHMARK_CONFIGURATION_IDS:
            continue
        model = models.setdefault(
            configuration.model,
            {
                "context_window": configuration.context_window,
                "efforts": [],
            },
        )
        efforts = model["efforts"]
        assert isinstance(efforts, list)
        efforts.append(configuration.effort)
    return {
        "provider_id": CODEX_NATIVE_PROVIDER_ID,
        "transport_profile": CODEX_NATIVE_TRANSPORT_PROFILE,
        "authentication": "local-codex-session",
        "credential_relay_scope": "none",
        "single_agent_transport": {
            "provider_id": CODEX_NATIVE_PROVIDER_ID,
            "endpoint_override": False,
            "retry_control": "codex-native-managed",
        },
        "ultra_transport": {
            "provider_id": CODEX_NATIVE_HTTP_PROVIDER_ID,
            "base_url": CODEX_NATIVE_HTTP_BASE_URL,
            "wire_api": "responses",
            "requires_openai_auth": True,
            "supports_websockets": False,
            "request_max_retries": 0,
            "stream_max_retries": 0,
            "usage_scope": "all-agent-threads",
        },
        "model_catalog": "bundled-codex",
        "models": models,
    }


def _require_frozen_configuration(
    configuration: BenchmarkConfiguration,
) -> BenchmarkConfiguration:
    try:
        expected = benchmark_configuration(
            configuration.id,
            openai_transport_profile=(
                configuration.transport_profile
                if configuration.provider == "openai"
                else OPENAI_PROXY_TRANSPORT_PROFILE
            ),
        )
    except ValueError as error:
        raise ValueError(
            "configuration is not in the frozen benchmark matrix"
        ) from error
    if configuration != expected:
        raise ValueError("configuration is not in the frozen benchmark matrix")
    return configuration


def build_codex_command(
    configuration: BenchmarkConfiguration,
    *,
    workspace: Path,
    minimax_env_key: str = MINIMAX_ENV_KEY,
    model_catalog: Path | None = None,
) -> list[str]:
    """Build a secret-free Codex exec command for one isolated packet."""

    configuration = _require_frozen_configuration(configuration)
    workspace = Path(workspace).resolve()
    command = [
        str(resolve_codex_executable()),
        "--ask-for-approval",
        "never",
        "exec",
        "--strict-config",
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--sandbox",
        "workspace-write",
        "-C",
        str(workspace),
        "-m",
        configuration.model,
    ]
    command.extend(_config("shell_environment_policy.inherit", "none"))
    command.extend(
        _config(
            "shell_environment_policy.set.PATH",
            "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        )
    )
    command.extend(
        _config("shell_environment_policy.set.PYTHONDONTWRITEBYTECODE", "1")
    )
    for feature in (
        "apps",
        "browser_use",
        "browser_use_external",
        "browser_use_full_cdp_access",
        "computer_use",
        "image_generation",
        "in_app_browser",
        "plugins",
        "recommended_plugins",
        "remote_plugin",
    ):
        command.extend(["--disable", feature])
    if configuration.provider == "openai":
        if configuration.transport_profile == OPENAI_PROXY_TRANSPORT_PROFILE:
            command.extend(openai_proxy_config_args())
        elif configuration.transport_profile != CODEX_NATIVE_TRANSPORT_PROFILE:
            raise ValueError("unsupported OpenAI transport profile")
        command.extend(_config("model_context_window", configuration.context_window))
        command.extend(_config("model_reasoning_effort", configuration.effort))
        command.extend(
            [
                "--enable" if configuration.system_mode == "multi-agent" else "--disable",
                "multi_agent",
            ]
        )
    elif configuration.provider == "minimax":
        command.extend(_config("model_provider", "minimax"))
        command.extend(_config("model_providers.minimax.name", "MiniMax"))
        command.extend(_config("model_providers.minimax.base_url", MINIMAX_BASE_URL))
        command.extend(_config("model_providers.minimax.env_key", minimax_env_key))
        command.extend(_config("model_providers.minimax.wire_api", "responses"))
        command.extend(
            _config("model_providers.minimax.requires_openai_auth", False)
        )
        command.extend(_config("model_providers.minimax.request_max_retries", 0))
        command.extend(_config("model_providers.minimax.stream_max_retries", 0))
        command.extend(_config("model_context_window", configuration.context_window))
        # MiniMax's Codex compatibility maps any non-none effort to native
        # adaptive thinking; it is not a tunable reasoning depth.
        command.extend(_config("model_reasoning_effort", "high"))
        command.extend(["--disable", "multi_agent"])
        if model_catalog is not None:
            command.extend(_config("model_catalog_json", str(model_catalog.resolve())))
    else:
        raise ValueError(f"unsupported benchmark provider: {configuration.provider}")
    command.append("-")
    return command


def build_ultra_appserver_command(
    configuration: BenchmarkConfiguration,
    *,
    workspace: Path,
    repo_root: Path,
) -> list[str]:
    """Build the Ultra worker command that captures the complete agent tree."""

    configuration = _require_frozen_configuration(configuration)
    if (
        configuration.provider != "openai"
        or configuration.effort != "ultra"
        or configuration.system_mode != "multi-agent"
        or configuration.harness != "codex"
    ):
        raise ValueError("app-server worker is reserved for OpenAI Codex Ultra")
    workspace = Path(workspace).resolve()
    worker = Path(repo_root).resolve() / "tools/reverse_benchmark/appserver_worker.py"
    command = [
        sys.executable,
        "-B",
        str(worker),
        "--workspace",
        str(workspace),
        "--model",
        configuration.model,
        "--effort",
        configuration.effort,
        "--model-provider",
        OPENAI_PROXY_PROVIDER_ID,
    ]
    if configuration.transport_profile == OPENAI_PROXY_TRANSPORT_PROFILE:
        command.extend(["--base-url", OPENAI_PROXY_BASE_URL])
    elif configuration.transport_profile == CODEX_NATIVE_TRANSPORT_PROFILE:
        command[command.index(OPENAI_PROXY_PROVIDER_ID)] = (
            CODEX_NATIVE_HTTP_PROVIDER_ID
        )
        command.extend(
            [
                "--base-url",
                CODEX_NATIVE_HTTP_BASE_URL,
                "--provider-name",
                CODEX_NATIVE_HTTP_PROVIDER_NAME,
                "--disable-provider-websockets",
                "--native-http-provider",
            ]
        )
    else:
        raise ValueError("unsupported OpenAI transport profile")
    return command


def _minimax_catalog_payload(
    configuration: BenchmarkConfiguration,
) -> dict[str, object]:
    modalities = ["text", "image"] if configuration.model == "MiniMax-M3" else ["text"]
    return {
        "models": [
            {
                "slug": configuration.model,
                "display_name": configuration.model,
                "description": "Frozen reverse benchmark MiniMax configuration",
                "default_reasoning_level": "high",
                "supported_reasoning_levels": [
                    {"effort": "high", "description": "Native thinking"}
                ],
                "shell_type": "shell_command",
                "visibility": "list",
                "supported_in_api": True,
                "priority": 0,
                "base_instructions": (
                    "You are a coding agent operating inside an isolated benchmark packet."
                ),
                "supports_reasoning_summaries": True,
                "default_reasoning_summary": "none",
                "support_verbosity": False,
                "truncation_policy": {"mode": "bytes", "limit": 10000},
                "supports_parallel_tool_calls": False,
                "experimental_supported_tools": [],
                "input_modalities": modalities,
            }
        ]
    }


def minimax_provider_contract() -> dict[str, object]:
    """Return the semantic provider/catalog contract shared by gate and campaign."""

    models: dict[str, object] = {}
    for configuration in benchmark_matrix():
        if configuration.provider != "minimax":
            continue
        catalog = _minimax_catalog_payload(configuration)
        canonical = json.dumps(
            catalog, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        models[configuration.model] = {
            "context_window": configuration.context_window,
            "catalog_sha256": hashlib.sha256(canonical).hexdigest(),
        }
    return {
        "base_url": MINIMAX_BASE_URL,
        "wire_api": "responses",
        "env_key": MINIMAX_ENV_KEY,
        "requires_openai_auth": False,
        "request_max_retries": 0,
        "stream_max_retries": 0,
        "effective_reasoning_effort": "high",
        "multi_agent": False,
        "models": models,
    }


def benchmark_provider_contract(
    configuration: BenchmarkConfiguration,
) -> dict[str, object]:
    """Return the non-secret transport contract used for one configuration."""

    configuration = _require_frozen_configuration(configuration)
    if configuration.provider == "openai":
        if configuration.transport_profile == OPENAI_PROXY_TRANSPORT_PROFILE:
            return openai_proxy_provider_contract()
        if configuration.transport_profile == CODEX_NATIVE_TRANSPORT_PROFILE:
            return openai_native_provider_contract()
        raise ValueError("unsupported OpenAI transport profile")
    if configuration.provider == "minimax":
        return minimax_provider_contract()
    raise ValueError(f"unsupported benchmark provider: {configuration.provider}")


def provider_contract_sha256(configuration: BenchmarkConfiguration) -> str:
    """Hash the exact non-secret transport contract bound to a plan cell."""

    canonical = json.dumps(
        benchmark_provider_contract(configuration),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def write_minimax_catalog(
    configuration: BenchmarkConfiguration,
    destination: Path,
) -> Path:
    """Write the minimal official-compatible Codex catalog for one MiniMax model."""

    if configuration.provider != "minimax":
        raise ValueError("MiniMax catalog requires a MiniMax configuration")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"catalog destination already exists: {destination}")
    payload = _minimax_catalog_payload(configuration)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination


def base_run_manifest(
    configuration: BenchmarkConfiguration,
    *,
    challenge_id: str,
    input_hashes: dict[str, str],
) -> dict[str, object]:
    return {
        "schema": "reverse-model-benchmark-run-v1",
        "run_id": new_run_id(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "id": configuration.id,
            "provider": configuration.provider,
            "model": configuration.model,
            "effort": configuration.effort,
            "system_mode": configuration.system_mode,
            "harness": configuration.harness,
            "context_window": configuration.context_window,
        },
        "challenge_id": challenge_id,
        "input_hashes": dict(sorted(input_hashes.items())),
        "status": "prepared",
    }
