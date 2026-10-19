"""Frozen model/configuration matrix approved for the benchmark."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Mapping


OPENAI_PROXY_TRANSPORT_PROFILE = "openai-proxy"
CODEX_NATIVE_TRANSPORT_PROFILE = "codex-native"
CODEX_NATIVE_BENCHMARK_CONFIGURATION_IDS = (
    "openai-gpt-5.6-luna-max",
    "openai-gpt-5.6-terra-max",
    "openai-gpt-5.6-sol-medium",
    "openai-gpt-5.6-sol-ultra",
)


@dataclass(frozen=True, slots=True)
class BenchmarkConfiguration:
    """One independently runnable model/system configuration."""

    id: str
    provider: str
    model: str
    effort: str
    system_mode: str
    context_window: int
    transport_profile: str
    harness: str = "codex"


def _openai_configuration(model: str, effort: str) -> BenchmarkConfiguration:
    mode = "multi-agent" if effort == "ultra" else "single-agent"
    return BenchmarkConfiguration(
        id=f"openai-{model}-{effort}",
        provider="openai",
        model=model,
        effort=effort,
        system_mode=mode,
        context_window=1_050_000,
        transport_profile=OPENAI_PROXY_TRANSPORT_PROFILE,
    )


def benchmark_matrix() -> tuple[BenchmarkConfiguration, ...]:
    """Return the ordered, immutable 19-configuration benchmark matrix."""

    configurations: list[BenchmarkConfiguration] = []
    sol_terra_efforts = ("low", "medium", "high", "xhigh", "max", "ultra")
    for model in ("gpt-5.6-sol", "gpt-5.6-terra"):
        configurations.extend(
            _openai_configuration(model, effort) for effort in sol_terra_efforts
        )
    configurations.extend(
        _openai_configuration("gpt-5.6-luna", effort)
        for effort in ("low", "medium", "high", "xhigh", "max")
    )
    configurations.extend(
        (
            BenchmarkConfiguration(
                id="minimax-MiniMax-M3-adaptive",
                provider="minimax",
                model="MiniMax-M3",
                effort="adaptive",
                system_mode="single-agent",
                context_window=1_000_000,
                transport_profile="minimax-token-plan",
            ),
            BenchmarkConfiguration(
                id="minimax-MiniMax-M2.7-highspeed-native",
                provider="minimax",
                model="MiniMax-M2.7-highspeed",
                effort="native",
                system_mode="single-agent",
                context_window=204_800,
                transport_profile="minimax-token-plan",
            ),
        )
    )
    return tuple(configurations)


def benchmark_configuration(
    configuration_id: str,
    *,
    openai_transport_profile: str = OPENAI_PROXY_TRANSPORT_PROFILE,
) -> BenchmarkConfiguration:
    """Resolve one frozen identity with an explicitly selected OpenAI transport."""

    by_id = {item.id: item for item in benchmark_matrix()}
    try:
        configuration = by_id[configuration_id]
    except KeyError as error:
        raise ValueError(
            f"unknown benchmark configuration: {configuration_id}"
        ) from error
    if configuration.provider != "openai":
        return configuration
    if openai_transport_profile not in {
        OPENAI_PROXY_TRANSPORT_PROFILE,
        CODEX_NATIVE_TRANSPORT_PROFILE,
    }:
        raise ValueError("unsupported OpenAI transport profile")
    if (
        openai_transport_profile == CODEX_NATIVE_TRANSPORT_PROFILE
        and configuration_id not in CODEX_NATIVE_BENCHMARK_CONFIGURATION_IDS
    ):
        raise ValueError("configuration is not an approved native benchmark configuration")
    return replace(
        configuration,
        transport_profile=openai_transport_profile,
    )


def configuration_from_frozen(value: object) -> BenchmarkConfiguration:
    """Validate and restore a configuration serialized inside a frozen plan."""

    if not isinstance(value, Mapping) or set(value) != set(
        BenchmarkConfiguration.__dataclass_fields__
    ):
        raise ValueError("frozen benchmark configuration fields are invalid")
    try:
        configuration = BenchmarkConfiguration(**dict(value))
    except TypeError as error:
        raise ValueError("frozen benchmark configuration is invalid") from error
    expected = benchmark_configuration(
        configuration.id,
        openai_transport_profile=(
            configuration.transport_profile
            if configuration.provider == "openai"
            else OPENAI_PROXY_TRANSPORT_PROFILE
        ),
    )
    if asdict(configuration) != asdict(expected):
        raise ValueError("frozen benchmark configuration drifted from its identity")
    return configuration
