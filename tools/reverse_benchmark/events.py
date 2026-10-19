"""Normalize Codex and Pi JSONL events without double counting usage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

from .pricing import NormalizedUsage


@dataclass(frozen=True, slots=True)
class RequestTelemetry:
    ordinal: int
    source_event: str
    source_id: str | None
    usage: NormalizedUsage
    usage_granularity: str


@dataclass(frozen=True, slots=True)
class RunTelemetry:
    usage: NormalizedUsage
    requests: tuple[RequestTelemetry, ...]
    usage_complete: bool
    tool_calls: int
    successful_tool_calls: int
    failed: bool
    errors: tuple[str, ...]
    wall_time_ms: float | None = None
    usage_scope: str | None = None
    usage_granularity: str | None = None


def _decoded_events(text: str) -> Iterable[dict[str, object]]:
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSONL at line {line_number}: {error}") from error
        if not isinstance(event, dict):
            raise ValueError(f"JSONL line {line_number} is not an object")
        if event.get("type") == "stream.line" and event.get("stream") == "stdout":
            inner = event.get("line")
            if not isinstance(inner, str):
                continue
            try:
                decoded = json.loads(inner)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, dict):
                yield decoded
            continue
        yield event


def _non_negative_int(value: object, field: str) -> int:
    if value is None:
        return 0
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _codex_usage(payload: object) -> NormalizedUsage:
    if not isinstance(payload, dict):
        raise ValueError("Codex turn.completed usage must be an object")
    if "input_tokens" not in payload or "output_tokens" not in payload:
        raise ValueError("Codex usage is missing required input/output token fields")
    total_input = _non_negative_int(payload.get("input_tokens"), "input_tokens")
    cached = _non_negative_int(
        payload.get("cached_input_tokens"), "cached_input_tokens"
    )
    cache_write = _non_negative_int(
        payload.get("cache_write_input_tokens"), "cache_write_input_tokens"
    )
    if cached + cache_write > total_input:
        raise ValueError("Codex cached/cache-write tokens exceed input_tokens")
    return NormalizedUsage(
        uncached_input=total_input - cached - cache_write,
        cached_input=cached,
        cache_write_input=cache_write,
        output=_non_negative_int(payload.get("output_tokens"), "output_tokens"),
        reasoning_output=_non_negative_int(
            payload.get("reasoning_output_tokens"), "reasoning_output_tokens"
        ),
    )


def _wrapper_wall_time(events: Iterable[dict[str, object]]) -> float | None:
    started = None
    exited = None
    for event in events:
        value = event.get("monotonic_ns")
        if not isinstance(value, int):
            continue
        if event.get("type") == "process.started":
            started = value
        elif event.get("type") == "process.exited":
            exited = value
    if started is None or exited is None or exited < started:
        return None
    return (exited - started) / 1_000_000


def parse_codex_jsonl(text: str) -> RunTelemetry:
    raw_events = list(_decoded_events(text))
    emits_request_deltas = any(
        event.get("type") == "benchmark.appserver.completed"
        for event in raw_events
    )
    request_granularity = "request" if emits_request_deltas else "turn-aggregate"
    usage = NormalizedUsage()
    started_tools: set[str] = set()
    successful_tools: set[str] = set()
    errors: list[str] = []
    failed = False
    process_exit = None
    requests: list[RequestTelemetry] = []
    request_thread_ids: list[str | None] = []
    seen_usage_ids: set[str] = set()
    appserver_markers: list[dict[str, object]] = []
    for event in raw_events:
        event_type = event.get("type")
        item = event.get("item")
        if event_type == "item.started" and isinstance(item, dict):
            if item.get("type") in {"command_execution", "mcp_tool_call"}:
                started_tools.add(str(item.get("id", f"anonymous-{len(started_tools)}")))
        elif event_type == "item.completed" and isinstance(item, dict):
            if item.get("type") in {"command_execution", "mcp_tool_call"}:
                identifier = str(item.get("id", ""))
                exit_code = item.get("exit_code")
                status = item.get("status")
                if (
                    identifier in started_tools
                    and exit_code in (None, 0)
                    and status not in {"failed", "error"}
                ):
                    successful_tools.add(identifier)
        elif event_type == "turn.completed":
            source_value = event.get("turn_id") or event.get("id")
            source_id = source_value if isinstance(source_value, str) else None
            if source_id is not None and source_id in seen_usage_ids:
                continue
            request_usage = _codex_usage(event.get("usage"))
            if source_id is not None:
                seen_usage_ids.add(source_id)
            requests.append(
                RequestTelemetry(
                    ordinal=len(requests) + 1,
                    source_event="turn.completed",
                    source_id=source_id,
                    usage=request_usage,
                    usage_granularity=request_granularity,
                )
            )
            thread_value = event.get("thread_id")
            request_thread_ids.append(
                thread_value if isinstance(thread_value, str) and thread_value else None
            )
            usage = usage + request_usage
        elif event_type in {"turn.failed", "error"}:
            message = str(event.get("message") or event.get("error") or event_type)
            if event_type == "error" and message.startswith("Reconnecting... "):
                # Native Codex emits these while its transport retries.  A later
                # completed turn with usage proves recovery; absent that, the
                # process exit/missing-usage checks below still fail closed.
                continue
            failed = True
            errors.append(message)
        elif event_type == "benchmark.appserver.completed":
            appserver_markers.append(event)
        elif event_type == "process.exited":
            process_exit = event.get("exit_code")
    if isinstance(process_exit, int) and process_exit != 0:
        failed = True
        errors.append(f"process exited with {process_exit}")
    usage_scope = None
    usage_complete = bool(requests)
    if appserver_markers:
        if len(appserver_markers) != 1:
            failed = True
            usage_complete = False
            errors.append("invalid app-server completion marker count")
        else:
            marker = appserver_markers[0]
            marker_threads = marker.get("thread_ids")
            valid_marker_threads = (
                isinstance(marker_threads, list)
                and bool(marker_threads)
                and all(
                    isinstance(thread_id, str) and bool(thread_id)
                    for thread_id in marker_threads
                )
                and len(set(marker_threads)) == len(marker_threads)
                and all(thread_id is not None for thread_id in request_thread_ids)
                and set(marker_threads) == set(request_thread_ids)
            )
            if (
                marker.get("usage_scope") != "all-agent-threads"
                or marker.get("request_count") != len(requests)
                or not valid_marker_threads
            ):
                failed = True
                usage_complete = False
                errors.append("invalid app-server completion marker")
            else:
                usage_scope = "all-agent-threads"
    if not usage_complete:
        failed = True
        errors.append("missing usage telemetry")
    return RunTelemetry(
        usage=usage,
        requests=tuple(requests),
        usage_complete=usage_complete,
        tool_calls=len(started_tools),
        successful_tool_calls=len(successful_tools),
        failed=failed,
        errors=tuple(errors),
        wall_time_ms=_wrapper_wall_time(raw_events),
        usage_scope=usage_scope,
        usage_granularity=request_granularity if requests else None,
    )


def _pi_usage(payload: object) -> NormalizedUsage:
    if not isinstance(payload, dict):
        raise ValueError("Pi message_end usage must be an object")
    if "input" not in payload or "output" not in payload:
        raise ValueError("Pi usage is missing required input/output token fields")
    cache_write_value = payload.get("cacheWrite")
    if cache_write_value is None:
        cache_write = _non_negative_int(
            payload.get("cacheWrite5m"), "cacheWrite5m"
        ) + _non_negative_int(payload.get("cacheWrite1h"), "cacheWrite1h")
    else:
        cache_write = _non_negative_int(cache_write_value, "cacheWrite")
    return NormalizedUsage(
        uncached_input=_non_negative_int(payload.get("input"), "input"),
        cached_input=_non_negative_int(payload.get("cacheRead"), "cacheRead"),
        cache_write_input=cache_write,
        output=_non_negative_int(payload.get("output"), "output"),
        reasoning_output=_non_negative_int(payload.get("reasoning"), "reasoning"),
    )


def parse_pi_jsonl(text: str) -> RunTelemetry:
    raw_events = list(_decoded_events(text))
    usage = NormalizedUsage()
    started_tools: set[str] = set()
    successful_tools: set[str] = set()
    errors: list[str] = []
    failed = False
    process_exit = None
    requests: list[RequestTelemetry] = []
    seen_usage_ids: set[str] = set()
    for event in raw_events:
        event_type = event.get("type")
        if event_type == "tool_execution_start":
            started_tools.add(
                str(event.get("toolCallId", f"anonymous-{len(started_tools)}"))
            )
        elif event_type == "tool_execution_end":
            identifier = str(event.get("toolCallId", ""))
            if identifier in started_tools and not event.get("isError", False):
                successful_tools.add(identifier)
            else:
                errors.append(f"tool {identifier} failed")
        elif event_type == "message_end":
            message = event.get("message")
            if isinstance(message, dict):
                source_value = message.get("id") or event.get("messageId")
                source_id = source_value if isinstance(source_value, str) else None
                if source_id is not None and source_id in seen_usage_ids:
                    continue
                request_usage = _pi_usage(message.get("usage"))
                if source_id is not None:
                    seen_usage_ids.add(source_id)
                requests.append(
                    RequestTelemetry(
                        ordinal=len(requests) + 1,
                        source_event="message_end",
                        source_id=source_id,
                        usage=request_usage,
                        usage_granularity="request",
                    )
                )
                usage = usage + request_usage
        elif event_type in {"agent_error", "error"}:
            failed = True
            errors.append(str(event.get("message") or event.get("error") or event_type))
        elif event_type == "process.exited":
            process_exit = event.get("exit_code")
    if isinstance(process_exit, int) and process_exit != 0:
        failed = True
        errors.append(f"process exited with {process_exit}")
    usage_complete = bool(requests)
    if not usage_complete:
        failed = True
        errors.append("missing usage telemetry")
    return RunTelemetry(
        usage=usage,
        requests=tuple(requests),
        usage_complete=usage_complete,
        tool_calls=len(started_tools),
        successful_tool_calls=len(successful_tools),
        failed=failed,
        errors=tuple(errors),
        wall_time_ms=_wrapper_wall_time(raw_events),
        usage_scope="all-agent-threads",
        usage_granularity="request" if requests else None,
    )
