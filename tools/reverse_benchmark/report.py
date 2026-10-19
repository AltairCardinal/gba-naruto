"""Build an auditable smoke summary with separate campaign/gate costs."""

from __future__ import annotations

import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from .campaign import _retryable, validate_attempt_manifest, validate_smoke_plan
from .compatibility import validate_compatibility_receipt_set
from .matrix import (
    CODEX_NATIVE_TRANSPORT_PROFILE,
    BenchmarkConfiguration,
    configuration_from_frozen,
)
from .packets import SMOKE_CHALLENGE_IDS
from .pricing import RATE_CARD_SOURCES
from .schemas import SUMMARY_SCHEMA

_CHALLENGE_LABELS = {
    "fixed-pointer-table": "固定指针表",
    "arm-thumb-control-flow": "ARM/Thumb 控制流",
    "tdd-manifest-contract": "TDD/Manifest 合同",
}


def _decimal_text(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _load_manifest(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid attempt manifest: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"attempt manifest is not an object: {path}")
    return value


def _decimal_value(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f"complete billing has invalid {field}")
    try:
        parsed = Decimal(str(value))
    except Exception as error:
        raise ValueError(f"complete billing has invalid {field}") from error
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"complete billing has invalid {field}")
    return parsed


def _token_value(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"complete billing has invalid {field}")
    return value


def _wall_time_ms(manifest: dict[str, object]) -> Decimal | None:
    telemetry = manifest.get("telemetry")
    value = telemetry.get("wall_time_ms") if isinstance(telemetry, dict) else None
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or value < 0
    ):
        return None
    parsed = Decimal(str(value))
    return parsed if parsed.is_finite() else None


def _scope_status(known: int, unknown: int) -> str:
    if unknown == 0 and known > 0:
        return "complete"
    if known > 0 and unknown > 0:
        return "partial-known"
    if unknown > 0:
        return "unknown"
    return "not-run"


def _merge_statuses(*statuses: str) -> str:
    known = any(status in {"complete", "partial-known"} for status in statuses)
    unknown = any(status in {"unknown", "partial-known"} for status in statuses)
    if known and unknown:
        return "partial-known"
    if known:
        return "complete"
    if unknown:
        return "unknown"
    return "not-run"


_COST_METRICS = (
    "api_cost_usd",
    "api_cost_cny",
    "codex_credits_estimate",
    "minimax_token_plan_input_tokens",
    "minimax_token_plan_output_tokens",
)


def _retry_is_authorized(primary: dict[str, object]) -> bool:
    return _retryable(primary)


def _new_configuration_scope(
    configuration: BenchmarkConfiguration,
) -> dict[str, object]:
    scope: dict[str, object] = {
        "configuration": asdict(configuration),
        "challenge_scores": {
            challenge_id: None for challenge_id in SMOKE_CHALLENGE_IDS
        },
        "challenge_effective_wall_time_ms": {
            challenge_id: None for challenge_id in SMOKE_CHALLENGE_IDS
        },
        "challenge_physical_attempt_counts": {
            challenge_id: 0 for challenge_id in SMOKE_CHALLENGE_IDS
        },
        "challenge_physical_wall_time_ms": {
            challenge_id: None for challenge_id in SMOKE_CHALLENGE_IDS
        },
        "challenge_physical_wall_time_statuses": {
            challenge_id: "not-run" for challenge_id in SMOKE_CHALLENGE_IDS
        },
        "challenge_statuses": {
            challenge_id: "missing" for challenge_id in SMOKE_CHALLENGE_IDS
        },
        "valid_cases": 0,
        "passed_cases": 0,
        "unavailable_cases": 0,
        "average_score": None,
        "effective_wall_time_ms": "0",
        "effective_wall_time_status": "not-run",
        "physical_wall_time_ms": "0",
        "physical_wall_time_status": "not-run",
        "physical_attempt_count": 0,
        "api_cost_usd": "0" if configuration.provider == "openai" else None,
        "api_cost_cny": "0" if configuration.provider == "minimax" else None,
        "codex_credits_estimate": (
            "0" if configuration.provider == "openai" else None
        ),
        "minimax_token_plan_input_tokens": (
            0 if configuration.provider == "minimax" else None
        ),
        "minimax_token_plan_output_tokens": (
            0 if configuration.provider == "minimax" else None
        ),
        "billing_status": "not-run",
        "billing_complete_attempts": 0,
        "billing_partial_attempts": 0,
        "billing_unknown_attempts": 0,
        "billing_unknown_reasons": [],
        "_effective_wall_known": 0,
        "_effective_wall_unknown": 0,
        "_physical_wall_known": 0,
        "_physical_wall_unknown": 0,
    }
    for metric in _COST_METRICS:
        applicable = scope[metric] is not None
        scope[f"{metric}_status"] = "not-run" if applicable else "not-applicable"
        scope[f"_{metric}_known"] = 0
        scope[f"_{metric}_unknown"] = 0
    return scope


def _add_attempt_billing(
    scope: dict[str, object],
    manifest: dict[str, object],
    configuration: BenchmarkConfiguration,
) -> None:
    scope["physical_attempt_count"] = int(scope["physical_attempt_count"]) + 1
    wall = _wall_time_ms(manifest)
    if wall is None:
        scope["_physical_wall_unknown"] = int(scope["_physical_wall_unknown"]) + 1
    else:
        scope["_physical_wall_known"] = int(scope["_physical_wall_known"]) + 1
        scope["physical_wall_time_ms"] = _decimal_text(
            Decimal(str(scope["physical_wall_time_ms"])) + wall
        )

    applicable_metrics = (
        ("api_cost_usd", "codex_credits_estimate")
        if configuration.provider == "openai"
        else (
            "api_cost_cny",
            "minimax_token_plan_input_tokens",
            "minimax_token_plan_output_tokens",
        )
    )

    def mark_all_unknown() -> None:
        for metric in applicable_metrics:
            scope[f"_{metric}_unknown"] = int(
                scope[f"_{metric}_unknown"]
            ) + 1

    billing = manifest.get("billing")
    totals = billing.get("totals") if isinstance(billing, dict) else None
    status = billing.get("status") if isinstance(billing, dict) else None
    if status != "complete":
        reason = (
            billing.get("unknown_reason") if isinstance(billing, dict) else None
        )
        if not isinstance(reason, str) or not reason.strip():
            reason = "billing reason was not recorded"
        reasons = scope["billing_unknown_reasons"]
        assert isinstance(reasons, list)
        if reason not in reasons:
            reasons.append(reason)
    if (
        status not in {"complete", "partial-known"}
        or not isinstance(totals, dict)
    ):
        scope["billing_unknown_attempts"] = int(
            scope["billing_unknown_attempts"]
        ) + 1
        mark_all_unknown()
        return

    if configuration.provider == "openai":
        if any(
            totals.get(key) is not None
            for key in (
                "api_cost_cny",
                "minimax_token_plan_input_tokens",
                "minimax_token_plan_output_tokens",
            )
        ):
            raise ValueError("OpenAI billing contains MiniMax-only totals")
        parsers = {
            "api_cost_usd": _decimal_value,
            "codex_credits_estimate": _decimal_value,
        }
    else:
        if any(
            totals.get(key) is not None
            for key in ("api_cost_usd", "codex_credits_estimate")
        ):
            raise ValueError("MiniMax billing contains OpenAI-only totals")
        parsers = {
            "api_cost_cny": _decimal_value,
            "minimax_token_plan_input_tokens": _token_value,
            "minimax_token_plan_output_tokens": _token_value,
        }

    known_values = 0
    unknown_values = 0
    for metric, parser in parsers.items():
        raw_value = totals.get(metric)
        if raw_value is None:
            if status == "complete":
                raise ValueError(f"complete billing has invalid {metric}")
            scope[f"_{metric}_unknown"] = int(scope[f"_{metric}_unknown"]) + 1
            unknown_values += 1
            continue
        parsed = parser(raw_value, metric)
        scope[f"_{metric}_known"] = int(scope[f"_{metric}_known"]) + 1
        known_values += 1
        if isinstance(parsed, Decimal):
            scope[metric] = _decimal_text(Decimal(str(scope[metric])) + parsed)
        else:
            scope[metric] = int(scope[metric]) + parsed

    if status == "partial-known":
        if known_values == 0 or unknown_values == 0:
            raise ValueError("partial billing must contain known and unknown totals")
        scope["billing_partial_attempts"] = int(
            scope["billing_partial_attempts"]
        ) + 1
        scope["billing_unknown_attempts"] = int(
            scope["billing_unknown_attempts"]
        ) + 1
    else:
        scope["billing_complete_attempts"] = int(
            scope["billing_complete_attempts"]
        ) + 1


def _finalize_configuration_scope(scope: dict[str, object]) -> None:
    scores = [
        value
        for value in scope["challenge_scores"].values()
        if isinstance(value, int)
    ]
    if scores:
        scope["average_score"] = _decimal_text(
            Decimal(sum(scores)) / Decimal(len(scores))
        )
    metric_statuses: list[str] = []
    for metric in _COST_METRICS:
        if scope[metric] is None:
            continue
        metric_status = _scope_status(
            int(scope[f"_{metric}_known"]),
            int(scope[f"_{metric}_unknown"]),
        )
        scope[f"{metric}_status"] = metric_status
        scope[f"{metric}_known_attempts"] = int(scope[f"_{metric}_known"])
        scope[f"{metric}_unknown_attempts"] = int(scope[f"_{metric}_unknown"])
        metric_statuses.append(metric_status)
    scope["billing_status"] = _merge_statuses(*metric_statuses)
    scope["effective_wall_time_status"] = _scope_status(
        int(scope["_effective_wall_known"]),
        int(scope["_effective_wall_unknown"]),
    )
    scope["physical_wall_time_status"] = _scope_status(
        int(scope["_physical_wall_known"]),
        int(scope["_physical_wall_unknown"]),
    )
    scope["effective_wall_known_attempts"] = int(scope["_effective_wall_known"])
    scope["effective_wall_unknown_attempts"] = int(
        scope["_effective_wall_unknown"]
    )
    scope["physical_wall_known_attempts"] = int(scope["_physical_wall_known"])
    scope["physical_wall_unknown_attempts"] = int(
        scope["_physical_wall_unknown"]
    )
    for key in (
        "_effective_wall_known",
        "_effective_wall_unknown",
        "_physical_wall_known",
        "_physical_wall_unknown",
        *(
            internal
            for metric in _COST_METRICS
            for internal in (f"_{metric}_known", f"_{metric}_unknown")
        ),
    ):
        del scope[key]


def summarize_smoke_campaign(
    plan: object,
    runs_root: Path,
    *,
    compatibility_receipts: object,
    expected_codex_sha256: str | None = None,
) -> dict[str, object]:
    validated = validate_smoke_plan(plan)
    receipt_ids = dict(validated["compatibility_receipt_ids"])
    receipts = validate_compatibility_receipt_set(
        compatibility_receipts,
        expected_receipt_ids=receipt_ids,
        expected_provider_contracts=validated["provider_contracts"],
        expected_codex_sha256=expected_codex_sha256,
    )
    runs_root = Path(runs_root)
    selected_configurations = [
        configuration_from_frozen(item) for item in validated["configurations"]
    ]
    configurations = {item.id: item for item in selected_configurations}
    by_configuration = {
        item.id: _new_configuration_scope(item) for item in selected_configurations
    }
    physical_attempts: list[
        tuple[dict[str, object], BenchmarkConfiguration]
    ] = []
    logical_cases: list[dict[str, object]] = []

    campaign_effective_wall = Decimal(0)
    campaign_effective_wall_known = 0
    campaign_effective_wall_unknown = 0
    for case_value in validated["cases"]:
        assert isinstance(case_value, dict)
        case = case_value
        configuration = configurations[str(case["configuration_id"])]
        receipt_id = str(receipt_ids[configuration.provider])
        primary = _load_manifest(
            runs_root / str(case["primary_run_id"]) / "manifest.json"
        )
        retry = _load_manifest(
            runs_root / str(case["retry_run_id"]) / "manifest.json"
        )
        if primary is not None:
            primary = validate_attempt_manifest(
                primary,
                plan_id=validated["plan_id"],
                case=case,
                configuration=configuration,
                run_id=str(case["primary_run_id"]),
                attempt_index=1,
                compatibility_receipt_id=receipt_id,
            )
            physical_attempts.append((primary, configuration))
        if retry is not None:
            if primary is None or not _retry_is_authorized(primary):
                raise ValueError(
                    f"attempt manifest binding has an unauthorized retry: {case['case_id']}"
                )
            retry = validate_attempt_manifest(
                retry,
                plan_id=validated["plan_id"],
                case=case,
                configuration=configuration,
                run_id=str(case["retry_run_id"]),
                attempt_index=2,
                compatibility_receipt_id=receipt_id,
            )
            physical_attempts.append((retry, configuration))

        effective = retry if retry is not None else primary
        status = "missing" if effective is None else str(effective.get("status"))
        verification = (
            effective.get("verification") if isinstance(effective, dict) else None
        )
        score = (
            verification.get("score")
            if status in {"verified-passed", "verified-failed"}
            and isinstance(verification, dict)
            and isinstance(verification.get("score"), int)
            and not isinstance(verification.get("score"), bool)
            else None
        )
        aggregate = by_configuration[configuration.id]
        challenge_id = str(case["challenge_id"])
        physical_attempt_count = int(primary is not None) + int(retry is not None)
        aggregate["challenge_statuses"][challenge_id] = status
        aggregate["challenge_physical_attempt_counts"][
            challenge_id
        ] = physical_attempt_count
        physical_walls = [
            _wall_time_ms(attempt)
            for attempt in (primary, retry)
            if attempt is not None
        ]
        known_physical_walls = [
            wall for wall in physical_walls if wall is not None
        ]
        physical_wall = sum(known_physical_walls, Decimal(0))
        physical_wall_status = _scope_status(
            len(known_physical_walls),
            len(physical_walls) - len(known_physical_walls),
        )
        if known_physical_walls:
            aggregate["challenge_physical_wall_time_ms"][
                challenge_id
            ] = _decimal_text(physical_wall)
        aggregate["challenge_physical_wall_time_statuses"][
            challenge_id
        ] = physical_wall_status
        if status in {"verified-passed", "verified-failed"} and score is not None:
            aggregate["challenge_scores"][challenge_id] = score
            aggregate["valid_cases"] = int(aggregate["valid_cases"]) + 1
            aggregate["passed_cases"] = int(aggregate["passed_cases"]) + (
                status == "verified-passed"
            )
        elif status == "infrastructure-failed":
            aggregate["unavailable_cases"] = int(aggregate["unavailable_cases"]) + 1

        effective_wall = (
            _wall_time_ms(effective)
            if status in {"verified-passed", "verified-failed"}
            and effective is not None
            else None
        )
        if status in {"verified-passed", "verified-failed"}:
            if effective_wall is None:
                aggregate["_effective_wall_unknown"] = int(
                    aggregate["_effective_wall_unknown"]
                ) + 1
                campaign_effective_wall_unknown += 1
            else:
                aggregate["_effective_wall_known"] = int(
                    aggregate["_effective_wall_known"]
                ) + 1
                aggregate["effective_wall_time_ms"] = _decimal_text(
                    Decimal(str(aggregate["effective_wall_time_ms"]))
                    + effective_wall
                )
                aggregate["challenge_effective_wall_time_ms"][
                    challenge_id
                ] = _decimal_text(effective_wall)
                campaign_effective_wall += effective_wall
                campaign_effective_wall_known += 1

        logical_cases.append(
            {
                "sequence": case["sequence"],
                "case_id": case["case_id"],
                "configuration_id": configuration.id,
                "challenge_id": challenge_id,
                "primary_run_id": case["primary_run_id"],
                "retry_run_id": case["retry_run_id"] if retry is not None else None,
                "effective_run_id": (
                    effective.get("run_id") if effective is not None else None
                ),
                "status": status,
                "score": score,
                "effective_wall_time_ms": (
                    _decimal_text(effective_wall)
                    if effective_wall is not None
                    else None
                ),
                "physical_attempt_count": physical_attempt_count,
                "physical_wall_time_ms": (
                    _decimal_text(physical_wall) if known_physical_walls else None
                ),
                "physical_wall_time_status": physical_wall_status,
            }
        )

    for manifest, configuration in physical_attempts:
        _add_attempt_billing(
            by_configuration[configuration.id], manifest, configuration
        )
    for scope in by_configuration.values():
        _finalize_configuration_scope(scope)

    campaign = {
        "billing_status": "not-run",
        "billing_complete_attempts": 0,
        "billing_partial_attempts": 0,
        "billing_unknown_attempts": 0,
        "billing_unknown_reasons": [],
        "physical_attempts": len(physical_attempts),
        "effective_wall_time_ms": _decimal_text(campaign_effective_wall),
        "effective_wall_time_status": _scope_status(
            campaign_effective_wall_known, campaign_effective_wall_unknown
        ),
        "physical_wall_time_ms": "0",
        "physical_wall_time_status": "not-run",
        "api_cost_usd": "0",
        "api_cost_cny": "0",
        "codex_credits_estimate": "0",
        "minimax_token_plan_input_tokens": 0,
        "minimax_token_plan_output_tokens": 0,
    }
    for metric in _COST_METRICS:
        campaign[f"{metric}_status"] = "not-run"
        campaign[f"{metric}_known_attempts"] = 0
        campaign[f"{metric}_unknown_attempts"] = 0
    physical_wall_known = 0
    physical_wall_unknown = 0
    for scope in by_configuration.values():
        campaign["billing_complete_attempts"] += int(
            scope["billing_complete_attempts"]
        )
        campaign["billing_partial_attempts"] += int(
            scope["billing_partial_attempts"]
        )
        campaign["billing_unknown_attempts"] += int(
            scope["billing_unknown_attempts"]
        )
        for reason in scope["billing_unknown_reasons"]:
            if reason not in campaign["billing_unknown_reasons"]:
                campaign["billing_unknown_reasons"].append(reason)
        physical_wall_known += int(scope["physical_wall_known_attempts"])
        physical_wall_unknown += int(scope["physical_wall_unknown_attempts"])
        campaign["physical_wall_time_ms"] = _decimal_text(
            Decimal(str(campaign["physical_wall_time_ms"]))
            + Decimal(str(scope["physical_wall_time_ms"]))
        )
        for metric in _COST_METRICS:
            if scope[metric] is None:
                continue
            campaign[f"{metric}_known_attempts"] += int(
                scope[f"{metric}_known_attempts"]
            )
            campaign[f"{metric}_unknown_attempts"] += int(
                scope[f"{metric}_unknown_attempts"]
            )
            if metric in {
                "api_cost_usd",
                "api_cost_cny",
                "codex_credits_estimate",
            }:
                campaign[metric] = _decimal_text(
                    Decimal(str(campaign[metric])) + Decimal(str(scope[metric]))
                )
            else:
                campaign[metric] += int(scope[metric])
    campaign_metric_statuses = []
    for metric in _COST_METRICS:
        metric_status = _scope_status(
            int(campaign[f"{metric}_known_attempts"]),
            int(campaign[f"{metric}_unknown_attempts"]),
        )
        campaign[f"{metric}_status"] = metric_status
        campaign_metric_statuses.append(metric_status)
    campaign["billing_status"] = _merge_statuses(*campaign_metric_statuses)
    campaign["physical_wall_time_status"] = _scope_status(
        physical_wall_known, physical_wall_unknown
    )

    compatibility_by_provider: dict[str, dict[str, object]] = {}
    if "openai" in receipts:
        openai_compatibility = dict(receipts["openai"]["overhead"])
        openai_compatibility["receipt_id"] = receipt_ids["openai"]
        openai_compatibility["physical_wall_time_status"] = "complete"
        openai_compatibility["api_cost_usd_status"] = openai_compatibility[
            "billing_status"
        ]
        openai_compatibility["api_cost_cny_status"] = "not-applicable"
        openai_compatibility["codex_credits_estimate_status"] = (
            openai_compatibility["billing_status"]
        )
        openai_compatibility["minimax_token_plan_input_tokens_status"] = (
            "not-applicable"
        )
        openai_compatibility["minimax_token_plan_output_tokens_status"] = (
            "not-applicable"
        )
        compatibility_by_provider["openai"] = openai_compatibility
    if "minimax" in receipts:
        minimax_compatibility = dict(receipts["minimax"]["overhead"])
        minimax_compatibility["receipt_id"] = receipt_ids["minimax"]
        minimax_compatibility["physical_wall_time_status"] = "complete"
        minimax_compatibility["api_cost_usd_status"] = "not-applicable"
        minimax_compatibility["api_cost_cny_status"] = minimax_compatibility[
            "billing_status"
        ]
        minimax_compatibility["codex_credits_estimate_status"] = "not-applicable"
        minimax_compatibility["minimax_token_plan_input_tokens_status"] = (
            minimax_compatibility["billing_status"]
        )
        minimax_compatibility["minimax_token_plan_output_tokens_status"] = (
            minimax_compatibility["billing_status"]
        )
        compatibility_by_provider["minimax"] = minimax_compatibility
    openai_compatibility = compatibility_by_provider.get("openai", {})
    minimax_compatibility = compatibility_by_provider.get("minimax", {})
    compatibility = {
        "receipt_ids": receipt_ids,
        "by_provider": compatibility_by_provider,
        "billing_status": _merge_statuses(
            *(str(value["billing_status"]) for value in compatibility_by_provider.values())
        ),
        "physical_attempts": sum(
            int(value["physical_attempts"])
            for value in compatibility_by_provider.values()
        ),
        "physical_wall_time_ms": _decimal_text(
            sum(
                (
                    Decimal(str(value["physical_wall_time_ms"]))
                    for value in compatibility_by_provider.values()
                ),
                Decimal(0),
            )
        ),
        "physical_wall_time_status": "complete",
        "api_cost_usd": str(openai_compatibility.get("api_cost_usd", "0")),
        "api_cost_usd_status": str(
            openai_compatibility.get("billing_status", "not-applicable")
        ),
        "api_cost_cny": str(minimax_compatibility.get("api_cost_cny", "0")),
        "api_cost_cny_status": str(
            minimax_compatibility.get("billing_status", "not-applicable")
        ),
        "codex_credits_estimate": str(
            openai_compatibility.get("codex_credits_estimate", "0")
        ),
        "codex_credits_estimate_status": str(
            openai_compatibility.get("billing_status", "not-applicable")
        ),
        "minimax_token_plan_input_tokens": int(
            minimax_compatibility.get("minimax_token_plan_input_tokens", 0)
        ),
        "minimax_token_plan_input_tokens_status": str(
            minimax_compatibility.get("billing_status", "not-applicable")
        ),
        "minimax_token_plan_output_tokens": int(
            minimax_compatibility.get("minimax_token_plan_output_tokens", 0)
        ),
        "minimax_token_plan_output_tokens_status": str(
            minimax_compatibility.get("billing_status", "not-applicable")
        ),
    }
    processing_metric_statuses = {
        "api_cost_usd_status": _merge_statuses(
            str(campaign["api_cost_usd_status"]),
            str(compatibility["api_cost_usd_status"]),
        ),
        "api_cost_cny_status": _merge_statuses(
            str(campaign["api_cost_cny_status"]),
            str(compatibility["api_cost_cny_status"]),
        ),
        "codex_credits_estimate_status": _merge_statuses(
            str(campaign["codex_credits_estimate_status"]),
            str(compatibility["codex_credits_estimate_status"]),
        ),
        "minimax_token_plan_input_tokens_status": _merge_statuses(
            str(campaign["minimax_token_plan_input_tokens_status"]),
            str(compatibility["minimax_token_plan_input_tokens_status"]),
        ),
        "minimax_token_plan_output_tokens_status": _merge_statuses(
            str(campaign["minimax_token_plan_output_tokens_status"]),
            str(compatibility["minimax_token_plan_output_tokens_status"]),
        ),
    }
    processing_total = {
        "billing_status": _merge_statuses(
            *processing_metric_statuses.values()
        ),
        **processing_metric_statuses,
        "physical_wall_time_status": _merge_statuses(
            str(campaign["physical_wall_time_status"]),
            str(compatibility["physical_wall_time_status"]),
        ),
        "physical_wall_time_ms": _decimal_text(
            Decimal(str(campaign["physical_wall_time_ms"]))
            + Decimal(str(compatibility["physical_wall_time_ms"]))
        ),
        "api_cost_usd": _decimal_text(
            Decimal(str(campaign["api_cost_usd"]))
            + Decimal(str(compatibility["api_cost_usd"]))
        ),
        "api_cost_cny": _decimal_text(
            Decimal(str(campaign["api_cost_cny"]))
            + Decimal(str(compatibility["api_cost_cny"]))
        ),
        "codex_credits_estimate": _decimal_text(
            Decimal(str(campaign["codex_credits_estimate"]))
            + Decimal(str(compatibility["codex_credits_estimate"]))
        ),
        "minimax_token_plan_input_tokens": int(
            campaign["minimax_token_plan_input_tokens"]
        )
        + int(compatibility["minimax_token_plan_input_tokens"]),
        "minimax_token_plan_output_tokens": int(
            campaign["minimax_token_plan_output_tokens"]
        )
        + int(compatibility["minimax_token_plan_output_tokens"]),
    }

    valid_cases = sum(
        item["status"] in {"verified-passed", "verified-failed"}
        for item in logical_cases
    )
    unavailable = sum(
        item["status"] == "infrastructure-failed" for item in logical_cases
    )
    missing = len(logical_cases) - valid_cases - unavailable
    return {
        "schema": SUMMARY_SCHEMA,
        "plan_id": validated["plan_id"],
        "compatibility_receipt_ids": receipt_ids,
        "master_seed": validated["master_seed"],
        "rate_card_as_of": "2026-08-16",
        "completeness": {
            "logical_cases": len(logical_cases),
            "valid_logical_cases": valid_cases,
            "unavailable_logical_cases": unavailable,
            "missing_logical_cases": missing,
            "physical_attempts": len(physical_attempts),
            "billing_unknown_attempts": campaign["billing_unknown_attempts"],
        },
        "logical_cases": logical_cases,
        "aggregates": {
            "by_configuration": by_configuration,
            "campaign": campaign,
            "compatibility": compatibility,
            "processing_total": processing_total,
        },
        "cost_scope": {
            "api_prices": "equivalent rate-card cost, not invoice data",
            "codex_credits": "token-derived estimate, not product ledger data",
            "minimax_tokens": "China Token Plan metered input/output token counts",
            "currencies_combined": False,
            "rate_card_sources": dict(RATE_CARD_SOURCES),
        },
    }


def _seconds(milliseconds: object) -> str:
    return _decimal_text(Decimal(str(milliseconds)) / Decimal(1000))


def _display(value: object, status: str, *, applicable: bool = True) -> str:
    if not applicable:
        return "—"
    if status == "complete":
        return str(value)
    if status == "partial-known":
        return f"部分已知：{value}"
    if status == "unknown":
        return "未知"
    return "—"


def render_smoke_markdown(summary: dict[str, object]) -> str:
    aggregates = summary["aggregates"]["by_configuration"]
    openai_profiles = {
        row["configuration"].get("transport_profile")
        for row in aggregates.values()
        if row["configuration"].get("provider") == "openai"
    }
    openai_label = (
        "本机 Codex 原生"
        if openai_profiles == {CODEX_NATIVE_TRANSPORT_PROFILE}
        else "OpenAI 代理"
    )
    receipt_labels = {"openai": openai_label, "minimax": "MiniMax"}
    receipt_text = "；".join(
        f"{receipt_labels.get(provider, provider)}兼容性回执：`{receipt_id}`"
        for provider, receipt_id in summary["compatibility_receipt_ids"].items()
    )
    lines = [
        "# 逆向模型冒烟测评汇总",
        "",
        (
            f"Plan ID：`{summary['plan_id']}`；{receipt_text}；主种子："
            f"`{summary['master_seed']}`。"
        ),
        "",
        "| 配置 | 指针表分数 /100 | ARM/Thumb 分数 /100 | TDD/Manifest 分数 /100 | 平均分 /100 | 有效格 | 有效 attempt 耗时(s) | 物理耗时(s) | API USD | API CNY | Codex credits(估算) | MiniMax 输入 token | MiniMax 输出 token | 成本状态 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for configuration_id, row in aggregates.items():
        configuration = row["configuration"]
        scores = [
            "—"
            if row["challenge_scores"][challenge] is None
            else str(row["challenge_scores"][challenge])
            for challenge in SMOKE_CHALLENGE_IDS
        ]
        status = str(row["billing_status"])
        lines.append(
            "| "
            + " | ".join(
                [
                    configuration_id,
                    *scores,
                    str(row["average_score"] or "—"),
                    f"{row['valid_cases']}/3",
                    _display(
                        _seconds(row["effective_wall_time_ms"]),
                        str(row["effective_wall_time_status"]),
                    ),
                    _display(
                        _seconds(row["physical_wall_time_ms"]),
                        str(row["physical_wall_time_status"]),
                    ),
                    _display(
                        row["api_cost_usd"],
                        str(row["api_cost_usd_status"]),
                        applicable=configuration["provider"] == "openai",
                    ),
                    _display(
                        row["api_cost_cny"],
                        str(row["api_cost_cny_status"]),
                        applicable=configuration["provider"] == "minimax",
                    ),
                    _display(
                        row["codex_credits_estimate"],
                        str(row["codex_credits_estimate_status"]),
                        applicable=configuration["provider"] == "openai",
                    ),
                    _display(
                        row["minimax_token_plan_input_tokens"],
                        str(row["minimax_token_plan_input_tokens_status"]),
                        applicable=configuration["provider"] == "minimax",
                    ),
                    _display(
                        row["minimax_token_plan_output_tokens"],
                        str(row["minimax_token_plan_output_tokens_status"]),
                        applicable=configuration["provider"] == "minimax",
                    ),
                    status,
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 每挑战明细",
            "",
            "| 配置 | 挑战 | 分数 /100 | 有效 attempt 耗时(s) | 物理总耗时(s) | 物理尝试 | 结果 |",
            "| --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for configuration_id, row in aggregates.items():
        for challenge_id in SMOKE_CHALLENGE_IDS:
            score = row["challenge_scores"][challenge_id]
            wall_time = row["challenge_effective_wall_time_ms"][challenge_id]
            physical_wall_time = row["challenge_physical_wall_time_ms"][
                challenge_id
            ]
            physical_wall_status = str(
                row["challenge_physical_wall_time_statuses"][challenge_id]
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        configuration_id,
                        _CHALLENGE_LABELS[challenge_id],
                        "—" if score is None else str(score),
                        "—" if wall_time is None else _seconds(wall_time),
                        _display(
                            _seconds(
                                0 if physical_wall_time is None else physical_wall_time
                            ),
                            physical_wall_status,
                        ),
                        str(
                            row["challenge_physical_attempt_counts"][challenge_id]
                        ),
                        str(row["challenge_statuses"][challenge_id]),
                    ]
                )
                + " |"
            )

    campaign = summary["aggregates"]["campaign"]
    compatibility = summary["aggregates"]["compatibility"]
    total = summary["aggregates"]["processing_total"]
    completeness = summary["completeness"]
    lines.extend(
        [
            "",
            (
                f"有效逻辑格：{completeness['valid_logical_cases']}/{completeness['logical_cases']}；"
                f"campaign 物理尝试：{completeness['physical_attempts']}；"
                f"含未知成本的尝试：{completeness['billing_unknown_attempts']}。"
            ),
            "",
            (
                "Campaign 开销：有效 attempt 耗时 "
                f"{_display(_seconds(campaign['effective_wall_time_ms']), str(campaign['effective_wall_time_status']))} 秒，物理耗时 "
                f"{_display(_seconds(campaign['physical_wall_time_ms']), str(campaign['physical_wall_time_status']))} 秒；API 等价成本 "
                f"USD {_display('$' + str(campaign['api_cost_usd']), str(campaign['api_cost_usd_status']))} / "
                f"CNY {_display('¥' + str(campaign['api_cost_cny']), str(campaign['api_cost_cny_status']))}；"
                f"Codex credits 估算 {_display(campaign['codex_credits_estimate'], str(campaign['codex_credits_estimate_status']))}；"
                f"MiniMax token {_display(campaign['minimax_token_plan_input_tokens'], str(campaign['minimax_token_plan_input_tokens_status']))} 输入 / "
                f"{_display(campaign['minimax_token_plan_output_tokens'], str(campaign['minimax_token_plan_output_tokens_status']))} 输出；状态 "
                f"`{campaign['billing_status']}`。"
            ),
            "",
            (
                f"兼容性门开销：{compatibility['physical_attempts']} 次 canary，物理耗时 "
                f"`{_seconds(compatibility['physical_wall_time_ms'])}` 秒；"
                f"API 等价成本 `${compatibility['api_cost_usd']}` / `¥{compatibility['api_cost_cny']}`；"
                f"Codex credits 估算 `{compatibility['codex_credits_estimate']}`；MiniMax token "
                f"`{compatibility['minimax_token_plan_input_tokens']}` 输入 / "
                f"`{compatibility['minimax_token_plan_output_tokens']}` 输出；状态 "
                f"`{compatibility['billing_status']}`。"
            ),
            "",
            (
                "总处理开销：物理耗时 "
                f"{_display(_seconds(total['physical_wall_time_ms']), str(total['physical_wall_time_status']))} 秒；API 等价成本 "
                f"USD {_display('$' + str(total['api_cost_usd']), str(total['api_cost_usd_status']))} / "
                f"CNY {_display('¥' + str(total['api_cost_cny']), str(total['api_cost_cny_status']))}；Codex "
                f"credits 估算 {_display(total['codex_credits_estimate'], str(total['codex_credits_estimate_status']))}；MiniMax token "
                f"{_display(total['minimax_token_plan_input_tokens'], str(total['minimax_token_plan_input_tokens_status']))} 输入 / "
                f"{_display(total['minimax_token_plan_output_tokens'], str(total['minimax_token_plan_output_tokens_status']))} 输出；状态 "
                f"`{total['billing_status']}`。"
            ),
            "",
            (
                "API 金额是冻结价表等价成本，不是账单；Codex credits 是 token "
                "推算，不是账户 ledger。USD 与 CNY 不做汇率换算或相加。"
            ),
            "",
            (
                "价表来源（冻结于 "
                f"{summary['rate_card_as_of']}）："
                f"[OpenAI 官方 API 价表]({RATE_CARD_SOURCES['openai_api']})；"
                f"[Codex 官方 credit 价表]({RATE_CARD_SOURCES['codex_credits']})；"
                f"[MiniMax 官方 API 价表]({RATE_CARD_SOURCES['minimax_api']})。"
            ),
            "",
        ]
    )
    unknown_rows = [
        (configuration_id, reason)
        for configuration_id, row in aggregates.items()
        for reason in row["billing_unknown_reasons"]
    ]
    if unknown_rows:
        lines.extend(
            [
                "## 成本未知原因",
                "",
                "| 配置 | 原因 |",
                "| --- | --- |",
                *[
                    f"| {configuration_id} | {reason.replace('|', '&#124;')} |"
                    for configuration_id, reason in unknown_rows
                ],
                "",
            ]
        )
    return "\n".join(lines)
