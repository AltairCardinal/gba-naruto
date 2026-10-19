"""Frozen 2026-08-16 rate cards and auditable cost calculations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


MILLION = Decimal(1_000_000)

RATE_CARD_SOURCES = {
    "openai_api": "https://developers.openai.com/api/docs/pricing",
    "codex_credits": "https://learn.chatgpt.com/docs/pricing",
    "minimax_api": "https://platform.minimaxi.com/docs/guides/pricing-paygo",
}


@dataclass(frozen=True, slots=True)
class NormalizedUsage:
    """Disjoint token buckets used by all harness parsers.

    ``output`` already includes reasoning tokens. ``reasoning_output`` is a
    diagnostic subset and must never be billed a second time.
    """

    uncached_input: int = 0
    cached_input: int = 0
    cache_write_input: int = 0
    output: int = 0
    reasoning_output: int = 0

    def __post_init__(self) -> None:
        for field_name in (
            "uncached_input",
            "cached_input",
            "cache_write_input",
            "output",
            "reasoning_output",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.reasoning_output > self.output:
            raise ValueError("reasoning_output must be a subset of output")

    def __add__(self, other: object) -> "NormalizedUsage":
        if not isinstance(other, NormalizedUsage):
            return NotImplemented
        return NormalizedUsage(
            uncached_input=self.uncached_input + other.uncached_input,
            cached_input=self.cached_input + other.cached_input,
            cache_write_input=self.cache_write_input + other.cache_write_input,
            output=self.output + other.output,
            reasoning_output=self.reasoning_output + other.reasoning_output,
        )

    @property
    def request_input_tokens(self) -> int:
        return self.uncached_input + self.cached_input + self.cache_write_input


@dataclass(frozen=True, slots=True)
class CreditEstimate:
    credits: Decimal
    cache_write_assumption: str
    is_actual_ledger_value: bool = False


_OPENAI_API_RATES = {
    "gpt-5.6-sol": (Decimal("5"), Decimal("0.5"), Decimal("30")),
    "gpt-5.6-terra": (Decimal("2"), Decimal("0.2"), Decimal("12")),
    "gpt-5.6-luna": (Decimal("0.2"), Decimal("0.02"), Decimal("1.2")),
}

_CODEX_CREDIT_RATES = {
    "gpt-5.6-sol": (Decimal("125"), Decimal("12.5"), Decimal("750")),
    "gpt-5.6-terra": (Decimal("50"), Decimal("5"), Decimal("300")),
    "gpt-5.6-luna": (Decimal("5"), Decimal("0.5"), Decimal("30")),
}


def _weighted_cost(
    usage: NormalizedUsage,
    *,
    input_rate: Decimal,
    cached_rate: Decimal,
    cache_write_rate: Decimal,
    output_rate: Decimal,
) -> Decimal:
    return (
        Decimal(usage.uncached_input) * input_rate
        + Decimal(usage.cached_input) * cached_rate
        + Decimal(usage.cache_write_input) * cache_write_rate
        + Decimal(usage.output) * output_rate
    ) / MILLION


def openai_api_cost_usd(
    model: str,
    usage: NormalizedUsage,
    *,
    request_input_tokens: int | None = None,
) -> Decimal:
    """Return standard API-equivalent USD cost for one request/turn.

    Requests above 272K input tokens use the documented 2x input and 1.5x
    output multipliers for the full request. Cache writes are 1.25x the
    uncached input rate.
    """

    try:
        input_rate, cached_rate, output_rate = _OPENAI_API_RATES[model]
    except KeyError as error:
        raise ValueError(f"unsupported OpenAI benchmark model: {model}") from error
    effective_input = (
        usage.request_input_tokens
        if request_input_tokens is None
        else request_input_tokens
    )
    if effective_input < 0:
        raise ValueError("request_input_tokens must be non-negative")
    if effective_input > 272_000:
        input_rate *= 2
        cached_rate *= 2
        output_rate *= Decimal("1.5")
    return _weighted_cost(
        usage,
        input_rate=input_rate,
        cached_rate=cached_rate,
        cache_write_rate=input_rate * Decimal("1.25"),
        output_rate=output_rate,
    )


def codex_credit_estimate(
    model: str,
    usage: NormalizedUsage,
) -> CreditEstimate:
    """Estimate credits using the public three-bucket Codex rate card.

    The public card has no separate cache-write row, so cache creation is
    explicitly estimated at the uncached-input rate. The actual product ledger
    remains authoritative when it is available.
    """

    try:
        input_rate, cached_rate, output_rate = _CODEX_CREDIT_RATES[model]
    except KeyError as error:
        raise ValueError(f"unsupported Codex benchmark model: {model}") from error
    return CreditEstimate(
        credits=_weighted_cost(
            usage,
            input_rate=input_rate,
            cached_rate=cached_rate,
            cache_write_rate=input_rate,
            output_rate=output_rate,
        ),
        cache_write_assumption="input-rate",
    )


def minimax_api_cost_cny(
    model: str,
    usage: NormalizedUsage,
    *,
    request_input_tokens: int | None = None,
) -> Decimal:
    """Return Standard-tier MiniMax API-equivalent CNY cost for one request."""

    effective_input = (
        usage.request_input_tokens
        if request_input_tokens is None
        else request_input_tokens
    )
    if effective_input < 0:
        raise ValueError("request_input_tokens must be non-negative")
    if model == "MiniMax-M3":
        long_context = effective_input > 512_000
        input_rate = Decimal("4.2") if long_context else Decimal("2.1")
        cached_rate = Decimal("0.84") if long_context else Decimal("0.42")
        output_rate = Decimal("16.8") if long_context else Decimal("8.4")
        # M3 automatic cache creation has no separate premium; newly written
        # tokens remain ordinary input tokens.
        cache_write_rate = input_rate
    elif model == "MiniMax-M2.7-highspeed":
        input_rate = Decimal("4.2")
        cached_rate = Decimal("0.42")
        cache_write_rate = Decimal("2.625")
        output_rate = Decimal("16.8")
    else:
        raise ValueError(f"unsupported MiniMax benchmark model: {model}")
    return _weighted_cost(
        usage,
        input_rate=input_rate,
        cached_rate=cached_rate,
        cache_write_rate=cache_write_rate,
        output_rate=output_rate,
    )
