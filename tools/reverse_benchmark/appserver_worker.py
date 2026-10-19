"""Run one Ultra turn through Codex app-server and close its thread tree.

Stdout is deliberately limited to normalized Codex JSONL events consumed by
``events.parse_codex_jsonl``.  App-server diagnostics are drained to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Sequence
from urllib.parse import urlsplit

_TERMINAL_TURN_STATUSES = {"completed", "failed", "interrupted"}
_FINAL_THREAD_STATUSES = {"idle", "systemError", "notLoaded"}
_USAGE_FIELDS = (
    "totalTokens",
    "inputTokens",
    "cachedInputTokens",
    "cacheWriteInputTokens",
    "outputTokens",
    "reasoningOutputTokens",
)
_PROVIDER_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _provider_config_args(
    model_provider: str,
    base_url: str,
    *,
    provider_name: str = "OpenAI benchmark proxy",
    supports_websockets: bool | None = None,
) -> list[str]:
    if not _PROVIDER_ID_RE.fullmatch(model_provider):
        raise ValueError("model provider id is invalid")
    try:
        parsed = urlsplit(base_url)
        parsed.port
    except ValueError as error:
        raise ValueError("provider base URL is invalid") from error
    if (
        base_url != base_url.strip()
        or parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or bool(parsed.query)
        or bool(parsed.fragment)
    ):
        raise ValueError(
            "provider base URL must be an absolute HTTP(S) URL without userinfo, query, or fragment"
        )

    def config(key: str, value: object) -> list[str]:
        return ["-c", f"{key}={json.dumps(value, ensure_ascii=False)}"]

    command: list[str] = []
    command.extend(config("model_provider", model_provider))
    command.extend(
        config(f"model_providers.{model_provider}.name", provider_name)
    )
    command.extend(
        config(f"model_providers.{model_provider}.base_url", base_url)
    )
    command.extend(
        config(f"model_providers.{model_provider}.wire_api", "responses")
    )
    command.extend(
        config(f"model_providers.{model_provider}.requires_openai_auth", True)
    )
    if supports_websockets is not None:
        command.extend(
            config(
                f"model_providers.{model_provider}.supports_websockets",
                supports_websockets,
            )
        )
    command.extend(
        config(f"model_providers.{model_provider}.request_max_retries", 0)
    )
    command.extend(
        config(f"model_providers.{model_provider}.stream_max_retries", 0)
    )
    return command


def _emit(payload: dict[str, object]) -> None:
    print(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )


def _non_negative_int(payload: dict[str, object], name: str) -> int:
    value = payload.get(name, 0)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"invalid token usage field {name}")
    return value


@dataclass(frozen=True, slots=True)
class UsageSnapshot:
    total_tokens: int = 0
    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0

    @classmethod
    def from_wire(cls, payload: object) -> "UsageSnapshot":
        if not isinstance(payload, dict):
            raise ValueError("token usage breakdown is not an object")
        values = [_non_negative_int(payload, name) for name in _USAGE_FIELDS]
        snapshot = cls(*values)
        if snapshot.cached_input_tokens + snapshot.cache_write_input_tokens > snapshot.input_tokens:
            raise ValueError("cached/cache-write input exceeds total input")
        return snapshot

    def delta_from(self, previous: "UsageSnapshot") -> "UsageSnapshot":
        current = self.as_tuple()
        before = previous.as_tuple()
        if any(value < old for value, old in zip(current, before, strict=True)):
            raise ValueError("cumulative token usage moved backwards")
        return UsageSnapshot(
            *(value - old for value, old in zip(current, before, strict=True))
        )

    def as_tuple(self) -> tuple[int, ...]:
        return (
            self.total_tokens,
            self.input_tokens,
            self.cached_input_tokens,
            self.cache_write_input_tokens,
            self.output_tokens,
            self.reasoning_output_tokens,
        )

    def is_zero(self) -> bool:
        return not any(self.as_tuple())

    def codex_usage(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "cache_write_input_tokens": self.cache_write_input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_output_tokens": self.reasoning_output_tokens,
        }


class AppServerProtocolError(RuntimeError):
    """The local app-server did not satisfy the benchmark wire contract."""


class AppServerClient:
    def __init__(self, command: Sequence[str]) -> None:
        if not command or not all(isinstance(value, str) and value for value in command):
            raise ValueError("server command must contain non-empty strings")
        self._process = subprocess.Popen(
            list(command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert self._process.stdin is not None
        assert self._process.stdout is not None
        assert self._process.stderr is not None
        self._messages: queue.Queue[object] = queue.Queue()
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr,
            args=(self._process.stderr,),
            daemon=True,
        )
        self._stdout_thread = threading.Thread(
            target=self._read_stdout,
            args=(self._process.stdout,),
            daemon=True,
        )
        self._stderr_thread.start()
        self._stdout_thread.start()
        self._next_request_id = 1
        self.pending_responses: dict[int, dict[str, object]] = {}
        self.notification_handler = lambda _message: None

    def _read_stdout(self, stream: IO[str]) -> None:
        try:
            for raw_line in stream:
                try:
                    message = json.loads(raw_line)
                except json.JSONDecodeError as error:
                    self._messages.put(
                        AppServerProtocolError(f"invalid app-server JSON: {error}")
                    )
                    return
                if not isinstance(message, dict):
                    self._messages.put(
                        AppServerProtocolError("app-server message is not an object")
                    )
                    return
                self._messages.put(message)
        finally:
            self._messages.put(None)

    @staticmethod
    def _drain_stderr(stream: IO[str]) -> None:
        for raw_line in stream:
            sys.stderr.write(raw_line)
            sys.stderr.flush()

    def send_notification(self, method: str, params: dict[str, object]) -> None:
        self._send({"method": method, "params": params})

    def request(self, method: str, params: dict[str, object]) -> object:
        request_id = self._next_request_id
        self._next_request_id += 1
        self._send({"method": method, "id": request_id, "params": params})
        while request_id not in self.pending_responses:
            self.pump_one()
        response = self.pending_responses.pop(request_id)
        if "error" in response:
            raise AppServerProtocolError(
                f"app-server {method} failed: {response['error']}"
            )
        if "result" not in response:
            raise AppServerProtocolError(
                f"app-server {method} response has no result"
            )
        return response["result"]

    def _send(self, payload: dict[str, object]) -> None:
        if self._process.poll() is not None:
            raise AppServerProtocolError(
                f"app-server exited with {self._process.returncode}"
            )
        assert self._process.stdin is not None
        self._process.stdin.write(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
        self._process.stdin.flush()

    def pump_one(self) -> None:
        value = self._messages.get()
        if value is None:
            raise AppServerProtocolError(
                f"app-server closed stdout with exit code {self._process.poll()}"
            )
        if isinstance(value, Exception):
            raise value
        assert isinstance(value, dict)
        identifier = value.get("id")
        if isinstance(identifier, int) and ("result" in value or "error" in value):
            if identifier in self.pending_responses:
                raise AppServerProtocolError("duplicate app-server response id")
            self.pending_responses[identifier] = value
            return
        if isinstance(identifier, int) and isinstance(value.get("method"), str):
            raise AppServerProtocolError(
                f"unexpected app-server request: {value.get('method')}"
            )
        self.notification_handler(value)

    def close(self) -> None:
        if self._process.stdin is not None:
            try:
                self._process.stdin.close()
            except OSError:
                pass
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        self._stdout_thread.join(timeout=1)
        self._stderr_thread.join(timeout=1)


class UltraRun:
    def __init__(self, client: AppServerClient) -> None:
        self.client = client
        self.root_thread_id: str | None = None
        self.session_id: str | None = None
        self.known_threads: set[str] = set()
        self.parent_by_thread: dict[str, str] = {}
        self.terminal_threads: set[str] = set()
        self.active_turn_by_thread: dict[str, str] = {}
        self.turn_status_by_thread: dict[str, str] = {}
        self.thread_status: dict[str, str] = {}
        self.usage_totals: dict[str, UsageSnapshot] = {}
        self.usage_events: list[dict[str, object]] = []
        self.usage_count_by_thread: dict[str, int] = {}
        self.work_item_count = 0
        self.transport_retry_count = 0
        self.root_turn_failed = False
        self.protocol_errors: list[str] = []
        client.notification_handler = self.handle_notification

    @staticmethod
    def _params(message: dict[str, object]) -> dict[str, object]:
        params = message.get("params")
        return params if isinstance(params, dict) else {}

    def _discover_item_threads(self, thread_id: str | None, item: object) -> None:
        if not isinstance(item, dict):
            return
        item_type = item.get("type")
        child = item.get("agentThreadId")
        if item_type == "subAgentActivity" and isinstance(child, str) and child:
            self.known_threads.add(child)
            if thread_id:
                self.parent_by_thread[child] = thread_id
        receivers = item.get("receiverThreadIds")
        if item_type == "collabAgentToolCall" and isinstance(receivers, list):
            for receiver in receivers:
                if isinstance(receiver, str) and receiver:
                    self.known_threads.add(receiver)
                    if thread_id:
                        self.parent_by_thread[receiver] = thread_id

    def _record_usage(self, params: dict[str, object]) -> None:
        thread_id = params.get("threadId")
        token_usage = params.get("tokenUsage")
        if not isinstance(thread_id, str) or not isinstance(token_usage, dict):
            raise ValueError("token usage notification is missing threadId/tokenUsage")
        if thread_id not in self.known_threads:
            raise ValueError("token usage arrived for an undiscovered thread")
        total = UsageSnapshot.from_wire(token_usage.get("total"))
        previous = self.usage_totals.get(thread_id, UsageSnapshot())
        delta = total.delta_from(previous)
        if delta.is_zero():
            return
        last = UsageSnapshot.from_wire(token_usage.get("last"))
        if delta != last:
            raise ValueError(
                "cumulative token delta does not match last request; request boundary was lost"
            )
        self.usage_totals[thread_id] = total
        sequence = self.usage_count_by_thread.get(thread_id, 0) + 1
        self.usage_count_by_thread[thread_id] = sequence
        turn_id = params.get("turnId")
        rendered_turn = turn_id if isinstance(turn_id, str) else "unknown-turn"
        self.usage_events.append(
            {
                "type": "turn.completed",
                "turn_id": f"appserver:{thread_id}:{rendered_turn}:{sequence}",
                "thread_id": thread_id,
                "usage_scope": "all-agent-threads",
                "usage": delta.codex_usage(),
            }
        )

    @staticmethod
    def _normalized_item_event(
        method: str, params: dict[str, object]
    ) -> dict[str, object] | None:
        item = params.get("item")
        if not isinstance(item, dict):
            return None
        item_type = item.get("type")
        if item_type == "agentMessage":
            if method != "item/completed":
                return None
            normalized_type = "agent_message"
        else:
            normalized_type = {
                "commandExecution": "command_execution",
                "mcpToolCall": "mcp_tool_call",
            }.get(str(item_type))
        if normalized_type is None:
            return None
        normalized = dict(item)
        normalized["type"] = normalized_type
        if "exitCode" in normalized:
            normalized["exit_code"] = normalized.pop("exitCode")
        return {
            "type": "item.started" if method == "item/started" else "item.completed",
            "item": normalized,
        }

    def handle_notification(self, message: dict[str, object]) -> None:
        method = message.get("method")
        if not isinstance(method, str):
            return
        params = self._params(message)
        thread_value = params.get("threadId")
        thread_id = thread_value if isinstance(thread_value, str) else None
        try:
            if method in {"item/started", "item/completed"}:
                self._discover_item_threads(thread_id, params.get("item"))
                normalized = self._normalized_item_event(method, params)
                if normalized is not None:
                    self.work_item_count += 1
                    _emit(normalized)
            elif method == "thread/tokenUsage/updated":
                self._record_usage(params)
            elif method == "turn/started" and thread_id:
                if thread_id not in self.known_threads:
                    raise ValueError("turn started for an undiscovered thread")
                turn = params.get("turn")
                turn_id = turn.get("id") if isinstance(turn, dict) else None
                if not isinstance(turn_id, str) or not turn_id:
                    raise ValueError("turn/started omitted a turn id")
                self.active_turn_by_thread[thread_id] = turn_id
                self.turn_status_by_thread[thread_id] = "inProgress"
                self.terminal_threads.discard(thread_id)
            elif method == "turn/completed" and thread_id:
                if thread_id not in self.known_threads:
                    raise ValueError("turn completed for an undiscovered thread")
                turn = params.get("turn")
                turn_id = turn.get("id") if isinstance(turn, dict) else None
                status = turn.get("status") if isinstance(turn, dict) else None
                if not isinstance(turn_id, str) or not turn_id:
                    raise ValueError("turn/completed omitted a turn id")
                if status not in _TERMINAL_TURN_STATUSES:
                    raise ValueError("turn/completed did not contain a terminal status")
                active_turn = self.active_turn_by_thread.get(thread_id)
                if active_turn is not None and active_turn != turn_id:
                    raise ValueError("turn/completed did not match the active turn")
                self.active_turn_by_thread.pop(thread_id, None)
                self.turn_status_by_thread[thread_id] = status
                if status == "completed":
                    self.terminal_threads.add(thread_id)
                else:
                    self.terminal_threads.discard(thread_id)
                    self.root_turn_failed = True
                    raise ValueError(
                        f"thread {thread_id} ended with unsuccessful status {status}"
                    )
            elif method == "thread/status/changed" and thread_id:
                status_value = params.get("status")
                status = (
                    status_value.get("type")
                    if isinstance(status_value, dict)
                    else None
                )
                if isinstance(status, str):
                    self.thread_status[thread_id] = status
                    if status in {"systemError", "notLoaded"}:
                        raise ValueError(
                            f"thread {thread_id} entered unsuccessful status {status}"
                        )
            elif method in {"error", "turn/failed"}:
                self.protocol_errors.append(str(params.get("message") or method))
        except ValueError as error:
            self.protocol_errors.append(str(error))

    def _ready_for_reconciliation(self) -> bool:
        if self.protocol_errors:
            return False
        if self.root_thread_id is None or self.root_thread_id not in self.terminal_threads:
            return False
        if not self.known_threads.issubset(self.terminal_threads):
            return False
        return all(
            status in _FINAL_THREAD_STATUSES
            for thread_id, status in self.thread_status.items()
            if thread_id in self.known_threads
        )

    def _loaded_thread_ids(self) -> list[str]:
        cursor: str | None = None
        loaded: list[str] = []
        while True:
            params: dict[str, object] = {"limit": 100}
            if cursor is not None:
                params["cursor"] = cursor
            result = self.client.request("thread/loaded/list", params)
            if not isinstance(result, dict) or not isinstance(result.get("data"), list):
                raise AppServerProtocolError("invalid thread/loaded/list response")
            for value in result["data"]:
                if not isinstance(value, str):
                    raise AppServerProtocolError("loaded thread id is not a string")
                loaded.append(value)
            next_cursor = result.get("nextCursor")
            if next_cursor is None:
                return loaded
            if not isinstance(next_cursor, str) or not next_cursor:
                raise AppServerProtocolError("invalid loaded-list cursor")
            cursor = next_cursor

    def _read_thread(self, thread_id: str) -> dict[str, object] | None:
        result = self.client.request("thread/read", {"threadId": thread_id})
        thread = result.get("thread") if isinstance(result, dict) else None
        return thread if isinstance(thread, dict) else None

    def reconcile(self) -> None:
        loaded = self._loaded_thread_ids()
        loaded_set = set(loaded)
        missing_known = self.known_threads - loaded_set
        if missing_known:
            raise AppServerProtocolError(
                "known threads are absent from loaded list: "
                + ", ".join(sorted(missing_known))
            )
        metadata: dict[str, dict[str, object]] = {}
        for thread_id in loaded:
            thread = self._read_thread(thread_id)
            if thread_id in self.known_threads and (
                thread is None or thread.get("sessionId") != self.session_id
            ):
                raise AppServerProtocolError(
                    f"known thread {thread_id} has a mismatched session"
                )
            if thread is not None and thread.get("sessionId") == self.session_id:
                metadata[thread_id] = thread

        changed = True
        while changed:
            changed = False
            for thread_id, thread in metadata.items():
                if thread_id in self.known_threads:
                    continue
                parent = thread.get("parentThreadId")
                if isinstance(parent, str) and parent in self.known_threads:
                    self.known_threads.add(thread_id)
                    self.parent_by_thread[thread_id] = parent
                    changed = True

        for thread_id in self.known_threads:
            thread = metadata.get(thread_id)
            if thread is None:
                raise AppServerProtocolError(
                    f"known thread {thread_id} has no readable metadata"
                )
            if thread_id != self.root_thread_id:
                parent = thread.get("parentThreadId")
                if not isinstance(parent, str) or parent not in self.known_threads:
                    raise AppServerProtocolError(
                        f"known child thread {thread_id} has an invalid parent"
                    )
                observed_parent = self.parent_by_thread.get(thread_id)
                if observed_parent is not None and observed_parent != parent:
                    raise AppServerProtocolError(
                        f"known child thread {thread_id} changed parent"
                    )
                self.parent_by_thread[thread_id] = parent
            status_value = thread.get("status")
            status = (
                status_value.get("type") if isinstance(status_value, dict) else None
            )
            if status not in {"active", *_FINAL_THREAD_STATUSES}:
                raise AppServerProtocolError(
                    f"thread {thread_id} has invalid or missing status"
                )
            self.thread_status[thread_id] = status
            if status in {"systemError", "notLoaded"}:
                raise AppServerProtocolError(
                    f"thread {thread_id} entered unsuccessful status {status}"
                )
            turns = thread.get("turns")
            if turns is None or turns == []:
                if status == "active":
                    self.terminal_threads.discard(thread_id)
                    continue
                observed_status = self.turn_status_by_thread.get(thread_id)
                if observed_status is None:
                    self.terminal_threads.discard(thread_id)
                    continue
                if observed_status != "completed":
                    self.terminal_threads.discard(thread_id)
                    raise AppServerProtocolError(
                        f"thread {thread_id} observed unsuccessful turn status"
                    )
                self.active_turn_by_thread.pop(thread_id, None)
                self.terminal_threads.add(thread_id)
                continue
            if not isinstance(turns, list) or not turns:
                raise AppServerProtocolError(
                    f"thread {thread_id} has invalid or missing turns"
                )
            latest = turns[-1]
            latest_id = latest.get("id") if isinstance(latest, dict) else None
            latest_status = (
                latest.get("status") if isinstance(latest, dict) else None
            )
            if not isinstance(latest_id, str) or not isinstance(
                latest_status, str
            ):
                raise AppServerProtocolError(
                    f"thread {thread_id} has invalid latest turn metadata"
                )
            active_turn = self.active_turn_by_thread.get(thread_id)
            if active_turn is not None and latest_id != active_turn:
                self.terminal_threads.discard(thread_id)
                continue
            self.turn_status_by_thread[thread_id] = latest_status
            if latest_status == "completed":
                self.active_turn_by_thread.pop(thread_id, None)
                self.terminal_threads.add(thread_id)
            elif latest_status in {"failed", "interrupted"}:
                self.terminal_threads.discard(thread_id)
                raise AppServerProtocolError(
                    f"thread {thread_id} latest turn failed: {latest_status}"
                )
            elif latest_status == "inProgress":
                self.active_turn_by_thread[thread_id] = latest_id
                self.terminal_threads.discard(thread_id)
            else:
                raise AppServerProtocolError(
                    f"thread {thread_id} has unsupported latest turn status"
                )

    def closure_signature(self) -> tuple[object, ...]:
        return (
            tuple(sorted(self.known_threads)),
            tuple(sorted(self.terminal_threads)),
            tuple(
                sorted(
                    (thread_id, snapshot.as_tuple())
                    for thread_id, snapshot in self.usage_totals.items()
                    if thread_id in self.known_threads
                )
            ),
            tuple(
                sorted(
                    (thread_id, status)
                    for thread_id, status in self.thread_status.items()
                    if thread_id in self.known_threads
                )
            ),
        )

    def wait_until_closed(self) -> None:
        stable_signature: tuple[object, ...] | None = None
        while True:
            if self.protocol_errors:
                raise AppServerProtocolError("; ".join(self.protocol_errors))
            if not self._ready_for_reconciliation():
                self.client.pump_one()
                stable_signature = None
                continue
            self.reconcile()
            if not self._ready_for_reconciliation():
                stable_signature = None
                continue
            signature = self.closure_signature()
            if signature == stable_signature:
                break
            stable_signature = signature

        if self.root_turn_failed:
            raise AppServerProtocolError("root Ultra turn did not complete successfully")
        missing_usage = sorted(self.known_threads - self.usage_totals.keys())
        if missing_usage:
            raise AppServerProtocolError(
                "missing token usage for closed threads: " + ", ".join(missing_usage)
            )
        for event in self.usage_events:
            if event.get("thread_id") in self.known_threads:
                _emit(event)
        _emit(
            {
                "type": "benchmark.appserver.completed",
                "usage_scope": "all-agent-threads",
                "request_count": len(self.usage_events),
                "transport_retry_count": self.transport_retry_count,
                "thread_ids": sorted(self.known_threads),
            }
        )


def _default_server_command(
    model_provider: str,
    base_url: str | None = None,
    *,
    native_provider: bool = False,
    provider_name: str = "OpenAI benchmark proxy",
    supports_websockets: bool | None = None,
) -> list[str]:
    bundled = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
    executable = str(bundled.resolve()) if bundled.is_file() else shutil.which("codex")
    if executable is None:
        raise FileNotFoundError("Codex executable not found")
    command = [
        executable,
        "app-server",
        "--strict-config",
        "-c",
        "mcp_servers={}",
        "-c",
        'shell_environment_policy.inherit="none"',
        "--disable",
        "apps",
        "--disable",
        "plugins",
        "--disable",
        "remote_plugin",
        "--enable",
        "multi_agent",
    ]
    if native_provider:
        if model_provider != "openai" or base_url is not None:
            raise ValueError("native provider requires the built-in openai provider")
    else:
        if base_url is None:
            raise ValueError("custom provider requires a base URL")
        command.extend(
            _provider_config_args(
                model_provider,
                base_url,
                provider_name=provider_name,
                supports_websockets=supports_websockets,
            )
        )
    return command


def _server_command(
    value: str | None,
    *,
    model_provider: str,
    base_url: str | None,
    native_provider: bool,
    provider_name: str,
    supports_websockets: bool | None,
) -> list[str]:
    if value is None:
        return _default_server_command(
            model_provider,
            base_url,
            native_provider=native_provider,
            provider_name=provider_name,
            supports_websockets=supports_websockets,
        )
    decoded = json.loads(value)
    if not isinstance(decoded, list) or not decoded or not all(
        isinstance(item, str) and item for item in decoded
    ):
        raise ValueError("--server-command-json must be a non-empty string array")
    return decoded


def _object_result(value: object, method: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AppServerProtocolError(f"invalid {method} response")
    return value


def _start_ultra_turn(
    client: AppServerClient,
    *,
    workspace: Path,
    model: str,
    effort: str,
    prompt: str,
    max_transport_retries: int,
    model_provider: str = "openai",
) -> UltraRun:
    """Start one root turn, retrying only pre-work native transport failures."""

    if (
        not isinstance(max_transport_retries, int)
        or isinstance(max_transport_retries, bool)
        or max_transport_retries < 0
    ):
        raise ValueError("max transport retries must be a non-negative integer")
    workspace = Path(workspace).resolve()
    for attempt_index in range(max_transport_retries + 1):
        ultra = UltraRun(client)
        started = _object_result(
            client.request(
                "thread/start",
                {
                    "model": model,
                    "modelProvider": model_provider,
                    "cwd": str(workspace),
                    "sandbox": "workspace-write",
                    "approvalPolicy": "never",
                    "ephemeral": True,
                    "runtimeWorkspaceRoots": [str(workspace)],
                    "allowProviderModelFallback": False,
                },
            ),
            "thread/start",
        )
        thread = started.get("thread")
        if not isinstance(thread, dict):
            raise AppServerProtocolError("thread/start omitted thread")
        root_thread_id = thread.get("id")
        session_id = thread.get("sessionId")
        if not isinstance(root_thread_id, str) or not isinstance(session_id, str):
            raise AppServerProtocolError(
                "thread/start omitted thread/session identity"
            )
        ultra.root_thread_id = root_thread_id
        ultra.session_id = session_id
        ultra.known_threads.add(root_thread_id)
        try:
            client.request(
                "turn/start",
                {
                    "threadId": root_thread_id,
                    "input": [{"type": "text", "text": prompt}],
                    "model": model,
                    "effort": effort,
                    "cwd": str(workspace),
                    "approvalPolicy": "never",
                    "runtimeWorkspaceRoots": [str(workspace)],
                    "sandboxPolicy": {
                        "type": "workspaceWrite",
                        "writableRoots": [str(workspace)],
                        "networkAccess": False,
                    },
                },
            )
        except AppServerProtocolError:
            observed_work = bool(
                ultra.work_item_count
                or ultra.usage_events
                or ultra.active_turn_by_thread
                or len(ultra.known_threads) != 1
            )
            if observed_work or attempt_index >= max_transport_retries:
                raise
            continue
        ultra.transport_retry_count = attempt_index
        return ultra
    raise AssertionError("unreachable Ultra transport retry state")


def _transport_retry_safe(ultra: UltraRun) -> bool:
    return not (
        ultra.work_item_count
        or ultra.usage_events
        or len(ultra.known_threads) != 1
    )


def _run_ultra_turn(
    client: AppServerClient,
    *,
    workspace: Path,
    model: str,
    effort: str,
    prompt: str,
    max_transport_retries: int,
    model_provider: str = "openai",
) -> UltraRun:
    """Run and close Ultra, restarting only a zero-work failed root turn."""

    total_retries = 0
    while True:
        ultra = _start_ultra_turn(
            client,
            workspace=workspace,
            model=model,
            effort=effort,
            prompt=prompt,
            max_transport_retries=max_transport_retries - total_retries,
            model_provider=model_provider,
        )
        total_retries += ultra.transport_retry_count
        try:
            ultra.wait_until_closed()
        except AppServerProtocolError:
            if (
                total_retries >= max_transport_retries
                or not _transport_retry_safe(ultra)
            ):
                raise
            total_retries += 1
            continue
        ultra.transport_retry_count = total_retries
        return ultra


def run(args: argparse.Namespace, prompt: str) -> None:
    workspace = Path(args.workspace).resolve()
    if not workspace.is_dir():
        raise ValueError("workspace must be an existing directory")
    if not prompt.strip():
        raise ValueError("benchmark prompt is empty")
    client = AppServerClient(
        _server_command(
            args.server_command_json,
            model_provider=args.model_provider,
            base_url=args.base_url,
            native_provider=args.native_provider,
            provider_name=args.provider_name,
            supports_websockets=(
                False if args.disable_provider_websockets else None
            ),
        )
    )
    try:
        client.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "reverse-benchmark-runner",
                    "title": "Reverse Benchmark Runner",
                    "version": "1.0.0",
                },
                "capabilities": {"experimentalApi": True},
            },
        )
        client.send_notification("initialized", {})
        _run_ultra_turn(
            client,
            workspace=workspace,
            model=args.model,
            effort=args.effort,
            prompt=prompt,
            max_transport_retries=(
                2 if args.native_provider or args.native_http_provider else 0
            ),
            model_provider=args.model_provider,
        )
    finally:
        client.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--model-provider", required=True)
    parser.add_argument("--base-url")
    parser.add_argument("--native-provider", action="store_true")
    parser.add_argument("--native-http-provider", action="store_true")
    parser.add_argument("--provider-name", default="OpenAI benchmark proxy")
    parser.add_argument("--disable-provider-websockets", action="store_true")
    parser.add_argument("--server-command-json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        run(args, sys.stdin.read())
        return 0
    except (AppServerProtocolError, OSError, ValueError, json.JSONDecodeError) as error:
        _emit({"type": "error", "message": str(error)})
        print(f"reverse benchmark app-server worker: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
