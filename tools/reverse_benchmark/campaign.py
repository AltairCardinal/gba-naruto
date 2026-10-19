"""Frozen selected-matrix smoke plan creation, validation, and serial execution."""

from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .compatibility import validate_compatibility_receipt_set
from .harness import run_smoke_attempt
from .matrix import (
    CODEX_NATIVE_BENCHMARK_CONFIGURATION_IDS,
    CODEX_NATIVE_TRANSPORT_PROFILE,
    OPENAI_PROXY_TRANSPORT_PROFILE,
    BenchmarkConfiguration,
    benchmark_configuration,
    configuration_from_frozen,
)
from .packets import PACKET_CONTRACT_SCHEMA, SMOKE_CHALLENGE_IDS
from .runner import benchmark_provider_contract, provider_contract_sha256
from .schemas import ATTEMPT_SCHEMA, PLAN_SCHEMA


_RECEIPT_ID_RE = re.compile(r"^[0-9a-f]{64}$")
_RUN_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_ATTEMPT_STATUSES = {
    "verified-passed",
    "verified-failed",
    "infrastructure-failed",
}
_SECURITY_SURFACES = {
    "capture-stream",
    "child-command",
    "manifest",
    "packet-archive",
}


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _derived_hex(*parts: object, length: int) -> str:
    payload = "\0".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:length]


def _challenge_seed(master_seed: int, challenge_id: str) -> int:
    return int(
        _derived_hex(PLAN_SCHEMA, master_seed, challenge_id, length=16),
        16,
    )


def _plan_id(payload: dict[str, object]) -> str:
    canonical = {
        key: value
        for key, value in payload.items()
        if key not in {"plan_id", "created_at"}
    }
    return hashlib.sha256(_canonical_json(canonical)).hexdigest()


def _validated_compatibility_receipt_ids(
    value: object,
    *,
    providers: tuple[str, ...] = ("openai", "minimax"),
) -> dict[str, str]:
    if not providers or len(set(providers)) != len(providers):
        raise ValueError("compatibility receipt providers are invalid")
    if not isinstance(value, dict) or set(value) != set(providers):
        raise ValueError("compatibility_receipt_ids must match selected providers")
    if any(
        not isinstance(receipt_id, str)
        or _RECEIPT_ID_RE.fullmatch(receipt_id) is None
        for receipt_id in value.values()
    ):
        raise ValueError("compatibility receipt id is invalid")
    return {provider: str(value[provider]) for provider in providers}


def _selected_configurations(
    configuration_ids: object,
    *,
    openai_transport_profile: str = OPENAI_PROXY_TRANSPORT_PROFILE,
) -> tuple[BenchmarkConfiguration, ...]:
    from .matrix import benchmark_matrix

    matrix = benchmark_matrix()
    if configuration_ids is None:
        if openai_transport_profile == CODEX_NATIVE_TRANSPORT_PROFILE:
            configuration_ids = CODEX_NATIVE_BENCHMARK_CONFIGURATION_IDS
        else:
            return matrix
    if (
        not isinstance(configuration_ids, (list, tuple))
        or not configuration_ids
        or any(not isinstance(value, str) for value in configuration_ids)
        or len(set(configuration_ids)) != len(configuration_ids)
    ):
        raise ValueError("configuration_ids must be a non-empty unique string list")
    by_id = {configuration.id: configuration for configuration in matrix}
    unknown = [value for value in configuration_ids if value not in by_id]
    if unknown:
        raise ValueError(f"unknown benchmark configuration: {unknown[0]}")
    return tuple(
        benchmark_configuration(
            value,
            openai_transport_profile=openai_transport_profile,
        )
        for value in configuration_ids
    )


def _frozen_configurations(value: object) -> tuple[BenchmarkConfiguration, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("smoke plan configurations are invalid")
    return tuple(configuration_from_frozen(item) for item in value)


def create_smoke_plan(
    master_seed: int,
    *,
    compatibility_receipt_ids: object,
    configuration_ids: object = None,
    openai_transport_profile: str = OPENAI_PROXY_TRANSPORT_PROFILE,
    created_at: str | None = None,
) -> dict[str, object]:
    if not isinstance(master_seed, int) or isinstance(master_seed, bool):
        raise ValueError("master_seed must be an integer")
    configurations = _selected_configurations(
        configuration_ids,
        openai_transport_profile=openai_transport_profile,
    )
    providers = tuple(dict.fromkeys(item.provider for item in configurations))
    frozen_receipt_ids = _validated_compatibility_receipt_ids(
        compatibility_receipt_ids,
        providers=providers,
    )
    configuration_by_id = {
        configuration.id: configuration for configuration in configurations
    }
    pairs = [
        (configuration.id, challenge_id)
        for configuration in configurations
        for challenge_id in SMOKE_CHALLENGE_IDS
    ]
    random.Random(master_seed).shuffle(pairs)
    challenge_seeds = {
        challenge_id: _challenge_seed(master_seed, challenge_id)
        for challenge_id in SMOKE_CHALLENGE_IDS
    }
    cases = []
    for sequence, (configuration_id, challenge_id) in enumerate(pairs, start=1):
        case_id = f"{configuration_id}::{challenge_id}"
        cases.append(
            {
                "sequence": sequence,
                "case_id": case_id,
                "configuration_id": configuration_id,
                "challenge_id": challenge_id,
                "seed": challenge_seeds[challenge_id],
                "provider_contract_sha256": provider_contract_sha256(
                    configuration_by_id[configuration_id]
                ),
                "primary_run_id": _derived_hex(
                    PLAN_SCHEMA,
                    master_seed,
                    *(
                        ()
                        if openai_transport_profile == OPENAI_PROXY_TRANSPORT_PROFILE
                        else (f"openai-transport:{openai_transport_profile}",)
                    ),
                    case_id,
                    "primary",
                    length=32,
                ),
                "retry_run_id": _derived_hex(
                    PLAN_SCHEMA,
                    master_seed,
                    *(
                        ()
                        if openai_transport_profile == OPENAI_PROXY_TRANSPORT_PROFILE
                        else (f"openai-transport:{openai_transport_profile}",)
                    ),
                    case_id,
                    "retry",
                    length=32,
                ),
            }
        )
    payload: dict[str, object] = {
        "schema": PLAN_SCHEMA,
        "plan_id": "",
        "created_at": (
            datetime.now(timezone.utc).isoformat()
            if created_at is None
            else created_at
        ),
        "master_seed": master_seed,
        "packet_contract_schema": PACKET_CONTRACT_SCHEMA,
        "logical_case_count": len(cases),
        "configurations": [asdict(configuration) for configuration in configurations],
        "provider_contracts": {
            provider: benchmark_provider_contract(
                next(
                    configuration
                    for configuration in configurations
                    if configuration.provider == provider
                )
            )
            for provider in providers
        },
        "compatibility_receipt_ids": frozen_receipt_ids,
        "challenge_ids": list(SMOKE_CHALLENGE_IDS),
        "challenge_seeds": challenge_seeds,
        "retry_policy": {"max_retries": 1, "placement": "tail-fifo"},
        "cases": cases,
    }
    payload["plan_id"] = _plan_id(payload)
    return payload


def validate_smoke_plan(plan: object) -> dict[str, object]:
    if not isinstance(plan, dict):
        raise ValueError("smoke plan must be a JSON object")
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("smoke plan schema mismatch")
    master_seed = plan.get("master_seed")
    created_at = plan.get("created_at")
    frozen_configurations = plan.get("configurations")
    configurations = _frozen_configurations(frozen_configurations)
    configuration_ids = [
        item.get("id") if isinstance(item, dict) else None
        for item in frozen_configurations
    ]
    openai_profiles = {
        item.transport_profile
        for item in configurations
        if item.provider == "openai"
    }
    if len(openai_profiles) > 1:
        raise ValueError("smoke plan mixes OpenAI transport profiles")
    openai_transport_profile = next(
        iter(openai_profiles), OPENAI_PROXY_TRANSPORT_PROFILE
    )
    providers = tuple(dict.fromkeys(item.provider for item in configurations))
    compatibility_receipt_ids = _validated_compatibility_receipt_ids(
        plan.get("compatibility_receipt_ids"),
        providers=providers,
    )
    if not isinstance(master_seed, int) or isinstance(master_seed, bool):
        raise ValueError("smoke plan master_seed is invalid")
    if not isinstance(created_at, str) or not created_at:
        raise ValueError("smoke plan created_at is invalid")
    expected = create_smoke_plan(
        master_seed,
        compatibility_receipt_ids=compatibility_receipt_ids,
        configuration_ids=configuration_ids,
        openai_transport_profile=openai_transport_profile,
        created_at=created_at,
    )
    if plan != expected:
        raise ValueError("smoke plan content or plan_id does not match frozen matrix")
    return plan


def attempt_plan_binding(
    plan_id: object,
    case: dict[str, object],
    *,
    attempt_index: int,
) -> dict[str, object]:
    return {
        "plan_id": plan_id,
        "case_id": case["case_id"],
        "sequence": case["sequence"],
        "attempt_index": attempt_index,
        "provider_contract_sha256": case["provider_contract_sha256"],
        "retry_of": None if attempt_index == 1 else case["primary_run_id"],
    }


def validate_attempt_manifest(
    manifest: object,
    *,
    plan_id: object,
    case: dict[str, object],
    configuration: BenchmarkConfiguration,
    run_id: str,
    attempt_index: int,
    compatibility_receipt_id: str,
) -> dict[str, object]:
    expected_binding = attempt_plan_binding(
        plan_id, case, attempt_index=attempt_index
    )
    security = manifest.get("security") if isinstance(manifest, dict) else None
    security_valid = (
        isinstance(security, dict)
        and set(security) == {"credential_material_detected", "surfaces"}
        and isinstance(security.get("credential_material_detected"), bool)
        and isinstance(security.get("surfaces"), list)
        and all(
            isinstance(surface, str) and surface in _SECURITY_SURFACES
            for surface in security.get("surfaces", [])
        )
        and len(set(security.get("surfaces", [])))
        == len(security.get("surfaces", []))
        and bool(security.get("surfaces"))
        == security.get("credential_material_detected")
    )
    status = manifest.get("status") if isinstance(manifest, dict) else None
    verification = (
        manifest.get("verification") if isinstance(manifest, dict) else None
    )
    if status in {"verified-passed", "verified-failed"}:
        score = (
            verification.get("score") if isinstance(verification, dict) else None
        )
        passed = (
            verification.get("passed") if isinstance(verification, dict) else None
        )
        verification_valid = (
            isinstance(score, int)
            and not isinstance(score, bool)
            and 0 <= score <= 100
            and isinstance(passed, bool)
            and passed == (score == 100)
            and (status == "verified-passed") == passed
        )
    else:
        verification_valid = True
    valid = (
        isinstance(manifest, dict)
        and manifest.get("schema") == ATTEMPT_SCHEMA
        and _RUN_ID_RE.fullmatch(run_id) is not None
        and manifest.get("run_id") == run_id
        and manifest.get("configuration") == asdict(configuration)
        and manifest.get("challenge_id") == case["challenge_id"]
        and manifest.get("seed") == case["seed"]
        and manifest.get("plan_binding") == expected_binding
        and manifest.get("compatibility_receipt_id") == compatibility_receipt_id
        and manifest.get("provider_contract")
        == benchmark_provider_contract(configuration)
        and security_valid
        and status in _ATTEMPT_STATUSES
        and verification_valid
    )
    if not valid:
        if not verification_valid:
            raise ValueError(f"attempt manifest verification mismatch: {run_id}")
        raise ValueError(f"attempt manifest binding mismatch: {run_id}")
    return manifest


def _load_existing_manifest(
    run_dir: Path,
    *,
    case: dict[str, object],
    configuration: BenchmarkConfiguration,
    run_id: str,
    plan_id: object,
    attempt_index: int,
    compatibility_receipt_id: str,
) -> dict[str, object]:
    try:
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"existing run is missing a valid manifest: {run_dir}") from error
    return validate_attempt_manifest(
        manifest,
        plan_id=plan_id,
        case=case,
        configuration=configuration,
        run_id=run_id,
        attempt_index=attempt_index,
        compatibility_receipt_id=compatibility_receipt_id,
    )


def _retryable(manifest: dict[str, object]) -> bool:
    security = manifest.get("security")
    if isinstance(security, dict) and security.get(
        "credential_material_detected"
    ) is True:
        return False
    if manifest.get("status") != "infrastructure-failed":
        return False
    guard = manifest.get("guard")
    if not isinstance(guard, dict):
        return False
    if guard.get("reason") in {"lock-busy", "admission-rejected"}:
        return True
    if guard.get("reason") != "child-exit":
        return False
    telemetry = manifest.get("telemetry")
    if (
        not isinstance(telemetry, dict)
        or telemetry.get("usage_complete") is not False
        or telemetry.get("requests") != []
    ):
        return False
    errors = telemetry.get("errors")
    if not isinstance(errors, list) or not all(
        isinstance(error, str) for error in errors
    ):
        return False
    error_text = "\n".join(errors)
    if "401 Unauthorized" in error_text or "invalid_api_key" in error_text:
        return True
    configuration = manifest.get("configuration")
    return (
        isinstance(configuration, dict)
        and configuration.get("system_mode") == "multi-agent"
        and "Ultra all-agent closure marker is missing" in error_text
    )


def execute_smoke_plan(
    plan: object,
    *,
    repo_root: Path,
    output_root: Path,
    compatibility_receipts: object,
    allow_plaintext_auth_relay: bool = False,
    expected_codex_sha256: str | None = None,
    attempt_runner: Callable[..., dict[str, object]] = run_smoke_attempt,
    wall_timeout_s: float = 1_800,
    idle_timeout_s: float = 600,
    environment_for_configuration: Callable[
        [BenchmarkConfiguration], dict[str, str] | None
    ]
    | None = None,
) -> dict[str, object]:
    validated = validate_smoke_plan(plan)
    frozen_configurations = _frozen_configurations(validated["configurations"])
    proxy_selected = any(
        item.provider == "openai"
        and item.transport_profile == OPENAI_PROXY_TRANSPORT_PROFILE
        for item in frozen_configurations
    )
    if proxy_selected and allow_plaintext_auth_relay is not True:
        raise ValueError(
            "campaign execution requires explicit plaintext auth relay authorization"
        )
    selected_configurations = frozen_configurations
    providers = tuple(
        dict.fromkeys(item.provider for item in selected_configurations)
    )
    receipt_ids = _validated_compatibility_receipt_ids(
        validated["compatibility_receipt_ids"],
        providers=providers,
    )
    validate_compatibility_receipt_set(
        compatibility_receipts,
        expected_receipt_ids=receipt_ids,
        expected_provider_contracts=validated["provider_contracts"],
        expected_codex_sha256=expected_codex_sha256,
    )
    output_root = Path(output_root)
    configurations = {item.id: item for item in selected_configurations}
    existing_manifests: dict[str, dict[str, object]] = {}
    for case_value in validated["cases"]:
        assert isinstance(case_value, dict)
        configuration = configurations[str(case_value["configuration_id"])]
        expected_receipt_id = receipt_ids[configuration.provider]
        primary_run_id = str(case_value["primary_run_id"])
        retry_run_id = str(case_value["retry_run_id"])
        primary_dir = output_root / primary_run_id
        retry_dir = output_root / retry_run_id
        if primary_dir.is_symlink() or retry_dir.is_symlink():
            raise ValueError("existing campaign run directories cannot be symlinks")
        primary = None
        if primary_dir.exists():
            if not primary_dir.is_dir():
                raise ValueError(f"existing run path is not a directory: {primary_dir}")
            primary = _load_existing_manifest(
                primary_dir,
                case=case_value,
                configuration=configuration,
                run_id=primary_run_id,
                plan_id=validated["plan_id"],
                attempt_index=1,
                compatibility_receipt_id=expected_receipt_id,
            )
            existing_manifests[primary_run_id] = primary
        if retry_dir.exists():
            if not retry_dir.is_dir():
                raise ValueError(f"existing run path is not a directory: {retry_dir}")
            if primary is None or not _retryable(primary):
                raise ValueError(
                    f"existing retry is not authorized by its primary: {retry_run_id}"
                )
            retry = _load_existing_manifest(
                retry_dir,
                case=case_value,
                configuration=configuration,
                run_id=retry_run_id,
                plan_id=validated["plan_id"],
                attempt_index=2,
                compatibility_receipt_id=expected_receipt_id,
            )
            existing_manifests[retry_run_id] = retry
    environments: dict[str, dict[str, str] | None] = {}
    for configuration in configurations.values():
        value = (
            None
            if environment_for_configuration is None
            else environment_for_configuration(configuration)
        )
        if configuration.provider == "openai":
            if value not in (None, {}):
                raise ValueError("OpenAI attempts cannot receive MiniMax credentials")
            environments[configuration.id] = None
            continue
        if (
            not isinstance(value, dict)
            or set(value) != {"BENCH_MINIMAX_API_KEY"}
            or not isinstance(value.get("BENCH_MINIMAX_API_KEY"), str)
            or not value["BENCH_MINIMAX_API_KEY"].strip()
        ):
            raise ValueError("MiniMax credential must be loaded before campaign execution")
        environments[configuration.id] = dict(value)
    output_root.mkdir(parents=True, exist_ok=True)
    retry_queue: list[tuple[dict[str, object], BenchmarkConfiguration]] = []
    effective: dict[str, dict[str, object]] = {}
    physical_attempts = 0

    def run_case(
        case: dict[str, object],
        configuration: BenchmarkConfiguration,
        run_id: str,
        *,
        attempt_index: int,
    ) -> dict[str, object]:
        nonlocal physical_attempts
        run_dir = output_root / run_id
        expected_receipt_id = receipt_ids[configuration.provider]
        plan_binding = attempt_plan_binding(
            validated["plan_id"], case, attempt_index=attempt_index
        )
        if run_id in existing_manifests:
            return existing_manifests[run_id]
        child_environment = environments[configuration.id]
        physical_attempts += 1
        manifest = attempt_runner(
            repo_root=repo_root,
            output_root=output_root,
            configuration=configuration,
            challenge_id=str(case["challenge_id"]),
            seed=int(case["seed"]),
            run_id=run_id,
            wall_timeout_s=wall_timeout_s,
            idle_timeout_s=idle_timeout_s,
            child_environment=child_environment,
            plan_binding=plan_binding,
            compatibility_receipt_id=expected_receipt_id,
        )
        return validate_attempt_manifest(
            manifest,
            plan_id=validated["plan_id"],
            case=case,
            configuration=configuration,
            run_id=run_id,
            attempt_index=attempt_index,
            compatibility_receipt_id=expected_receipt_id,
        )

    def abort_if_security_failure(manifest: dict[str, object]) -> None:
        security = manifest["security"]
        assert isinstance(security, dict)
        if security["credential_material_detected"] is True:
            raise RuntimeError(
                "benchmark campaign aborted after credential material detection"
            )

    for case_value in validated["cases"]:
        assert isinstance(case_value, dict)
        case = case_value
        configuration = configurations[str(case["configuration_id"])]
        manifest = run_case(
            case,
            configuration,
            str(case["primary_run_id"]),
            attempt_index=1,
        )
        abort_if_security_failure(manifest)
        effective[str(case["case_id"])] = manifest
        if _retryable(manifest):
            retry_queue.append((case, configuration))

    for case, configuration in retry_queue:
        manifest = run_case(
            case,
            configuration,
            str(case["retry_run_id"]),
            attempt_index=2,
        )
        abort_if_security_failure(manifest)
        effective[str(case["case_id"])] = manifest

    unavailable = sum(
        manifest.get("status") == "infrastructure-failed"
        for manifest in effective.values()
    )
    return {
        "schema": "reverse-model-benchmark-execution-v1",
        "plan_id": validated["plan_id"],
        "compatibility_receipt_ids": receipt_ids,
        "logical_cases_completed": len(effective),
        "physical_attempts_started": physical_attempts,
        "retry_count": len(retry_queue),
        "unavailable_count": unavailable,
        "effective_run_ids": {
            case_id: manifest.get("run_id")
            for case_id, manifest in effective.items()
        },
    }
