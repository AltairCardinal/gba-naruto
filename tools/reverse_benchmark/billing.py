"""Per-request API-equivalent and Codex-plan billing calculations."""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from typing import Iterable

from .matrix import BenchmarkConfiguration
from .pricing import (
    NormalizedUsage,
    codex_credit_estimate,
    minimax_api_cost_cny,
    openai_api_cost_usd,
)


def _decimal_text(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _unknown_billing(reason: str) -> dict[str, object]:
    return {
        "status": "unknown",
        "unknown_reason": reason,
        "requests": [],
        "totals": {
            "api_cost_usd": None,
            "api_cost_cny": None,
            "codex_credits_estimate": None,
            "minimax_token_plan_input_tokens": None,
            "minimax_token_plan_output_tokens": None,
        },
        "codex_credit_is_actual_ledger_value": False,
    }


def calculate_attempt_billing(
    configuration: BenchmarkConfiguration,
    requests: Iterable[NormalizedUsage],
    *,
    usage_granularities: Iterable[str],
    usage_complete: bool,
    usage_scope: str,
) -> dict[str, object]:
    """Price each request before summing so tier thresholds remain correct."""

    request_values = tuple(requests)
    granularity_values = tuple(usage_granularities)
    if len(granularity_values) != len(request_values):
        raise ValueError("usage granularity count must match usage values")
    if any(
        granularity not in {"request", "turn-aggregate"}
        for granularity in granularity_values
    ):
        raise ValueError("unsupported usage granularity")
    if not usage_complete or not request_values:
        return _unknown_billing("usage telemetry is missing or incomplete")
    if (
        configuration.system_mode == "multi-agent"
        and usage_scope != "all-agent-threads"
    ):
        return _unknown_billing(
            "subagent usage is absent; root-thread tokens would underprice Ultra"
        )

    api_usd = Decimal(0)
    api_cny = Decimal(0)
    credits = Decimal(0)
    token_plan_input = 0
    token_plan_output = 0
    api_usd_known = True
    api_cny_known = True
    unknown_reasons: list[str] = []
    request_rows: list[dict[str, object]] = []
    for ordinal, (usage, granularity) in enumerate(
        zip(request_values, granularity_values, strict=True), start=1
    ):
        if not isinstance(usage, NormalizedUsage):
            raise TypeError("requests must contain NormalizedUsage values")
        request_input = usage.request_input_tokens
        row: dict[str, object] = {
            "ordinal": ordinal,
            "usage": asdict(usage),
            "request_input_tokens": request_input,
            "api_cost_usd": None,
            "api_cost_cny": None,
            "codex_credits_estimate": None,
        }
        if configuration.provider == "openai":
            request_credits = codex_credit_estimate(configuration.model, usage)
            credits += request_credits.credits
            row["codex_credits_estimate"] = _decimal_text(
                request_credits.credits
            )
            if granularity == "turn-aggregate" and request_input > 272_000:
                tier = "unknown-turn-aggregate-over-272k"
                api_usd_known = False
                unknown_reasons.append(
                    "OpenAI API cost needs request boundaries above 272K input tokens"
                )
            else:
                tier = (
                    "long-context-over-272k"
                    if request_input > 272_000
                    else "standard-up-to-272k"
                )
                request_api = openai_api_cost_usd(
                    configuration.model,
                    usage,
                    request_input_tokens=request_input,
                )
                api_usd += request_api
                row["api_cost_usd"] = _decimal_text(request_api)
        elif configuration.provider == "minimax":
            request_api: Decimal | None = None
            if (
                configuration.model == "MiniMax-M3"
                and granularity == "turn-aggregate"
                and request_input > 512_000
            ):
                tier = "unknown-turn-aggregate-over-512k"
                api_cny_known = False
                unknown_reasons.append(
                    "MiniMax-M3 API cost needs request boundaries above 512K input tokens"
                )
                request_api = None
            elif configuration.model == "MiniMax-M3":
                tier = (
                    "long-context-over-512k"
                    if request_input > 512_000
                    else "standard-up-to-512k"
                )
                request_api = minimax_api_cost_cny(
                    configuration.model,
                    usage,
                    request_input_tokens=request_input,
                )
            else:
                tier = "standard-fixed"
                request_api = minimax_api_cost_cny(
                    configuration.model,
                    usage,
                    request_input_tokens=request_input,
                )
            if request_api is not None:
                api_cny += request_api
                row["api_cost_cny"] = _decimal_text(request_api)
            token_plan_input += request_input
            token_plan_output += usage.output
        else:
            raise ValueError(
                f"unsupported benchmark provider: {configuration.provider}"
            )
        row["tier"] = tier
        request_rows.append(row)

    return {
        "status": "partial-known" if unknown_reasons else "complete",
        "unknown_reason": "; ".join(dict.fromkeys(unknown_reasons)) or None,
        "requests": request_rows,
        "totals": {
            "api_cost_usd": (
                _decimal_text(api_usd)
                if configuration.provider == "openai" and api_usd_known
                else None
            ),
            "api_cost_cny": (
                _decimal_text(api_cny)
                if configuration.provider == "minimax" and api_cny_known
                else None
            ),
            "codex_credits_estimate": (
                _decimal_text(credits)
                if configuration.provider == "openai"
                else None
            ),
            "minimax_token_plan_input_tokens": (
                token_plan_input
                if configuration.provider == "minimax"
                else None
            ),
            "minimax_token_plan_output_tokens": (
                token_plan_output
                if configuration.provider == "minimax"
                else None
            ),
        },
        "codex_credit_cache_write_assumption": (
            "input-rate" if configuration.provider == "openai" else None
        ),
        "codex_credit_is_actual_ledger_value": False,
        "api_cost_is_equivalent_not_invoice": True,
    }
