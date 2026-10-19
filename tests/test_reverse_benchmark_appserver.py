#!/usr/bin/env python3
"""App-server aggregation contract for Ultra's complete thread tree."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.reverse_benchmark.appserver_worker import (
    AppServerProtocolError,
    UltraRun,
    _default_server_command,
    _provider_config_args,
    _run_ultra_turn,
    _start_ultra_turn,
)
from tools.reverse_benchmark.events import parse_codex_jsonl
from tools.reverse_benchmark.runner import (
    CODEX_NATIVE_HTTP_BASE_URL,
    CODEX_NATIVE_HTTP_PROVIDER_ID,
    CODEX_NATIVE_PROVIDER_ID,
    OPENAI_PROXY_BASE_URL,
    OPENAI_PROXY_PROVIDER_ID,
)


ROOT = Path(__file__).resolve().parents[1]


class AppServerWorkerTests(unittest.TestCase):
    def test_native_zero_usage_wait_failure_restarts_root_thread(self):
        class Client:
            def __init__(self):
                self.notification_handler = lambda _message: None
                self.thread_starts = 0

            def request(self, method, _params):
                if method == "thread/start":
                    self.thread_starts += 1
                    return {
                        "thread": {
                            "id": f"thread-{self.thread_starts}",
                            "sessionId": f"session-{self.thread_starts}",
                        }
                    }
                if method == "turn/start":
                    return {"turn": {"id": f"turn-{self.thread_starts}"}}
                raise AssertionError(method)

        def fake_wait(run):
            if run.root_thread_id == "thread-1":
                run.active_turn_by_thread["thread-1"] = "turn-1"
                run.protocol_errors.append("native connection failed")
                raise AppServerProtocolError("native connection failed")

        client = Client()
        with mock.patch.object(UltraRun, "wait_until_closed", fake_wait):
            ultra = _run_ultra_turn(
                client,  # type: ignore[arg-type]
                workspace=Path("/tmp/native-ultra-test"),
                model="gpt-5.6-sol",
                effort="ultra",
                prompt="probe",
                max_transport_retries=2,
            )

        self.assertEqual("thread-2", ultra.root_thread_id)
        self.assertEqual(1, ultra.transport_retry_count)
        self.assertEqual(2, client.thread_starts)

    def test_native_turn_start_retries_only_before_any_model_work_or_usage(self):
        class Client:
            def __init__(self):
                self.notification_handler = lambda _message: None
                self.thread_starts = 0
                self.turn_starts = 0

            def request(self, method, _params):
                if method == "thread/start":
                    self.thread_starts += 1
                    return {
                        "thread": {
                            "id": f"thread-{self.thread_starts}",
                            "sessionId": f"session-{self.thread_starts}",
                        }
                    }
                if method == "turn/start":
                    self.turn_starts += 1
                    if self.turn_starts == 1:
                        raise AppServerProtocolError("transient native transport error")
                    return {"turn": {"id": "turn-2"}}
                raise AssertionError(method)

        client = Client()
        ultra = _start_ultra_turn(
            client,  # type: ignore[arg-type]
            workspace=Path("/tmp/native-ultra-test"),
            model="gpt-5.6-sol",
            effort="ultra",
            prompt="probe",
            max_transport_retries=2,
        )

        self.assertEqual("thread-2", ultra.root_thread_id)
        self.assertEqual("session-2", ultra.session_id)
        self.assertEqual(1, ultra.transport_retry_count)
        self.assertEqual(2, client.thread_starts)
        self.assertEqual(2, client.turn_starts)

    def test_native_turn_start_does_not_retry_after_model_work_is_observed(self):
        class Client:
            def __init__(self):
                self.notification_handler = lambda _message: None
                self.thread_starts = 0

            def request(self, method, _params):
                if method == "thread/start":
                    self.thread_starts += 1
                    return {"thread": {"id": "thread-1", "sessionId": "session-1"}}
                if method == "turn/start":
                    self.notification_handler(
                        {
                            "method": "item/completed",
                            "params": {
                                "threadId": "thread-1",
                                "item": {
                                    "id": "message-1",
                                    "type": "agentMessage",
                                    "text": "partial",
                                    "phase": "final_answer",
                                },
                            },
                        }
                    )
                    raise AppServerProtocolError("error after work")
                raise AssertionError(method)

        client = Client()
        with self.assertRaisesRegex(AppServerProtocolError, "after work"):
            _start_ultra_turn(
                client,  # type: ignore[arg-type]
                workspace=Path("/tmp/native-ultra-test"),
                model="gpt-5.6-sol",
                effort="ultra",
                prompt="probe",
                max_transport_retries=2,
            )

        self.assertEqual(1, client.thread_starts)

    def test_completed_agent_message_is_emitted_in_codex_jsonl_shape(self):
        class Client:
            notification_handler = None

        run = UltraRun(Client())  # type: ignore[arg-type]
        output = io.StringIO()
        with mock.patch("sys.stdout", output):
            run.handle_notification(
                {
                    "method": "item/completed",
                    "params": {
                        "completedAtMs": 1,
                        "threadId": "root-thread",
                        "turnId": "root-turn",
                        "item": {
                            "id": "message-1",
                            "type": "agentMessage",
                            "text": "benchmark-nonce",
                            "phase": "final_answer",
                        },
                    },
                }
            )

        self.assertEqual([], run.protocol_errors)
        self.assertEqual(
            {
                "type": "item.completed",
                "item": {
                    "id": "message-1",
                    "type": "agent_message",
                    "text": "benchmark-nonce",
                    "phase": "final_answer",
                },
            },
            json.loads(output.getvalue()),
        )

    def test_provider_base_url_rejects_userinfo_query_and_fragment(self):
        for invalid in (
            "http://user:password@example.test/v1",
            "http://example.test/v1?token=value",
            "http://example.test/v1#fragment",
            "http:///v1",
        ):
            with self.subTest(url=invalid), self.assertRaisesRegex(
                ValueError, "base URL"
            ):
                _provider_config_args("benchmark_provider", invalid)

    def test_worker_aggregates_root_and_delayed_subagent_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_log = root / "requests.jsonl"
            server = root / "fake_appserver.py"
            server.write_text(
                "import json, sys\n"
                f"log = open({str(request_log)!r}, 'a', encoding='utf-8')\n"
                "def send(value):\n"
                "    print(json.dumps(value), flush=True)\n"
                "for line in sys.stdin:\n"
                "    request = json.loads(line)\n"
                "    log.write(json.dumps(request) + '\\n'); log.flush()\n"
                "    method = request.get('method')\n"
                "    if method == 'initialize':\n"
                "        send({'id': request['id'], 'result': {'userAgent': 'fake'}})\n"
                "    elif method == 'thread/start':\n"
                "        send({'id': request['id'], 'result': {'thread': "
                "{'id': 'root-thread', 'sessionId': 'session-1'}}})\n"
                "    elif method == 'turn/start':\n"
                "        send({'id': request['id'], 'result': {'turn': "
                "{'id': 'root-turn', 'status': 'inProgress', 'items': []}}})\n"
                "        send({'method': 'item/completed', 'params': "
                "{'completedAtMs': 1, 'threadId': 'root-thread', "
                "'turnId': 'root-turn', 'item': {'id': 'message-1', "
                "'type': 'agentMessage', 'text': 'benchmark-nonce', "
                "'phase': 'final_answer'}}})\n"
                "        send({'method': 'thread/tokenUsage/updated', 'params': "
                "{'threadId': 'root-thread', 'turnId': 'root-turn', 'tokenUsage': "
                "{'total': {'totalTokens': 12, 'inputTokens': 10, "
                "'cachedInputTokens': 0, 'cacheWriteInputTokens': 0, "
                "'outputTokens': 2, 'reasoningOutputTokens': 1}, "
                "'last': {'totalTokens': 12, 'inputTokens': 10, "
                "'cachedInputTokens': 0, 'cacheWriteInputTokens': 0, "
                "'outputTokens': 2, 'reasoningOutputTokens': 1}, "
                "'modelContextWindow': 1000}}})\n"
                "        send({'method': 'turn/completed', 'params': "
                "{'threadId': 'root-thread', 'turn': {'id': 'root-turn', "
                "'status': 'completed', 'items': []}}})\n"
                "        send({'method': 'item/started', 'params': "
                "{'threadId': 'root-thread', 'turnId': 'root-turn', 'item': "
                "{'id': 'spawn-1', 'type': 'subAgentActivity', "
                "'agentThreadId': 'child-thread', 'agentPath': '/child', "
                "'kind': 'spawn'}}})\n"
                "        send({'method': 'turn/completed', 'params': "
                "{'threadId': 'child-thread', 'turn': {'id': 'child-turn', "
                "'status': 'completed', 'items': []}}})\n"
                "        send({'method': 'thread/tokenUsage/updated', 'params': "
                "{'threadId': 'child-thread', 'turnId': 'child-turn', 'tokenUsage': "
                "{'total': {'totalTokens': 24, 'inputTokens': 20, "
                "'cachedInputTokens': 0, 'cacheWriteInputTokens': 0, "
                "'outputTokens': 4, 'reasoningOutputTokens': 3}, "
                "'last': {'totalTokens': 24, 'inputTokens': 20, "
                "'cachedInputTokens': 0, 'cacheWriteInputTokens': 0, "
                "'outputTokens': 4, 'reasoningOutputTokens': 3}, "
                "'modelContextWindow': 1000}}})\n"
                "    elif method == 'thread/loaded/list':\n"
                "        send({'id': request['id'], 'result': "
                "{'data': ['root-thread', 'child-thread'], 'nextCursor': None}})\n"
                "    elif method == 'thread/read':\n"
                "        if 'includeTurns' in request['params']:\n"
                "            send({'id': request['id'], 'error': {'code': -32600, "
                "'message': 'ephemeral threads do not support includeTurns'}})\n"
                "            continue\n"
                "        thread_id = request['params']['threadId']\n"
                "        if thread_id == 'root-thread':\n"
                "            thread = {'id': 'root-thread', 'sessionId': 'session-1', "
                "'status': {'type': 'idle'}, 'turns': []}\n"
                "        else:\n"
                "            thread = {'id': 'child-thread', 'sessionId': 'session-1', "
                "'parentThreadId': 'root-thread', 'status': {'type': 'idle'}, "
                "'turns': []}\n"
                "        send({'id': request['id'], 'result': {'thread': thread}})\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "tools.reverse_benchmark.appserver_worker",
                    "--workspace",
                    str(root),
                    "--model",
                    "gpt-5.6-sol",
                    "--effort",
                    "ultra",
                    "--model-provider",
                    OPENAI_PROXY_PROVIDER_ID,
                    "--base-url",
                    OPENAI_PROXY_BASE_URL,
                    "--server-command-json",
                    json.dumps([sys.executable, "-B", str(server)]),
                ],
                cwd=ROOT,
                input="finish the packet",
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            requests = [
                json.loads(line) for line in request_log.read_text().splitlines()
            ]

        telemetry = parse_codex_jsonl(completed.stdout)
        self.assertEqual(30, telemetry.usage.uncached_input)
        self.assertEqual(6, telemetry.usage.output)
        self.assertEqual(4, telemetry.usage.reasoning_output)
        self.assertEqual(2, len(telemetry.requests))
        self.assertEqual("all-agent-threads", telemetry.usage_scope)
        self.assertTrue(telemetry.usage_complete)
        agent_events = [
            event
            for event in map(json.loads, completed.stdout.splitlines())
            if event.get("type") == "item.completed"
            and event.get("item", {}).get("type") == "agent_message"
        ]
        self.assertEqual("benchmark-nonce", agent_events[0]["item"]["text"])
        thread_start = next(item for item in requests if item.get("method") == "thread/start")
        turn_start = next(item for item in requests if item.get("method") == "turn/start")
        self.assertEqual("workspace-write", thread_start["params"]["sandbox"])
        self.assertEqual(
            OPENAI_PROXY_PROVIDER_ID,
            thread_start["params"]["modelProvider"],
        )
        self.assertEqual("ultra", turn_start["params"]["effort"])
        self.assertEqual("workspaceWrite", turn_start["params"]["sandboxPolicy"]["type"])
        self.assertFalse(turn_start["params"]["sandboxPolicy"]["networkAccess"])
        self.assertIn('"usage_scope":"all-agent-threads"', completed.stdout)
        self.assertGreaterEqual(
            2,
            sum(item.get("method") == "thread/loaded/list" for item in requests),
        )

    def test_default_server_command_pins_proxy_without_credential_in_argv(self):
        secret_sentinel = "openai-proxy-secret-must-not-enter-ultra-argv"
        with mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": secret_sentinel,
                "CODEX_API_KEY": secret_sentinel,
                "CODEX_ACCESS_TOKEN": secret_sentinel,
            },
        ):
            command = _default_server_command(
                OPENAI_PROXY_PROVIDER_ID,
                OPENAI_PROXY_BASE_URL,
            )
        rendered = " ".join(command)

        self.assertIn(
            f'model_provider="{OPENAI_PROXY_PROVIDER_ID}"', command
        )
        self.assertIn(
            (
                f'model_providers.{OPENAI_PROXY_PROVIDER_ID}.base_url='
                f'"{OPENAI_PROXY_BASE_URL}"'
            ),
            command,
        )
        self.assertIn(
            (
                f"model_providers.{OPENAI_PROXY_PROVIDER_ID}."
                "requires_openai_auth=true"
            ),
            command,
        )
        self.assertNotIn(secret_sentinel, rendered)
        for forbidden in (
            ".env_key=",
            "experimental_bearer_token",
            "Authorization",
            "api_key",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_default_server_command_uses_native_provider_without_custom_endpoint(self):
        command = _default_server_command(
            CODEX_NATIVE_PROVIDER_ID,
            native_provider=True,
        )
        rendered = " ".join(command)

        self.assertIn("app-server", command)
        self.assertIn("multi_agent", command)
        self.assertNotIn("model_provider=", rendered)
        self.assertNotIn("model_providers.", rendered)
        self.assertNotIn(OPENAI_PROXY_BASE_URL, rendered)

    def test_default_server_command_freezes_official_native_http_fallback(self):
        command = _default_server_command(
            CODEX_NATIVE_HTTP_PROVIDER_ID,
            CODEX_NATIVE_HTTP_BASE_URL,
            provider_name="Codex native HTTPS fallback",
            supports_websockets=False,
        )

        self.assertIn(
            f'model_provider="{CODEX_NATIVE_HTTP_PROVIDER_ID}"', command
        )
        self.assertIn(
            (
                f'model_providers.{CODEX_NATIVE_HTTP_PROVIDER_ID}.base_url='
                f'"{CODEX_NATIVE_HTTP_BASE_URL}"'
            ),
            command,
        )
        self.assertIn(
            f"model_providers.{CODEX_NATIVE_HTTP_PROVIDER_ID}.supports_websockets=false",
            command,
        )
        self.assertNotIn(OPENAI_PROXY_BASE_URL, " ".join(command))

    def test_cumulative_usage_uses_monotonic_deltas_and_keeps_equal_requests(self):
        class Client:
            notification_handler = None

        client = Client()
        run = UltraRun(client)  # type: ignore[arg-type]
        run.root_thread_id = "root"
        run.known_threads.add("root")

        def record(total_input: int, last_input: int) -> None:
            run.handle_notification(
                {
                    "method": "thread/tokenUsage/updated",
                    "params": {
                        "threadId": "root",
                        "turnId": "turn-1",
                        "tokenUsage": {
                            "total": {
                                "totalTokens": total_input + total_input // 5,
                                "inputTokens": total_input,
                                "outputTokens": total_input // 5,
                                "reasoningOutputTokens": 0,
                            },
                            "last": {
                                "totalTokens": last_input + last_input // 5,
                                "inputTokens": last_input,
                                "outputTokens": last_input // 5,
                                "reasoningOutputTokens": 0,
                            },
                        },
                    },
                }
            )

        record(10, 10)
        record(10, 10)
        record(20, 10)

        self.assertEqual([], run.protocol_errors)
        self.assertEqual(2, len(run.usage_events))
        self.assertNotEqual(
            run.usage_events[0]["turn_id"], run.usage_events[1]["turn_id"]
        )
        self.assertEqual(
            [10, 10],
            [event["usage"]["input_tokens"] for event in run.usage_events],
        )

        record(30, 5)
        self.assertIn("request boundary was lost", run.protocol_errors[-1])

    def test_reconciliation_rejects_observed_nonfinal_thread_status(self):
        class Client:
            notification_handler = None

        run = UltraRun(Client())  # type: ignore[arg-type]
        run.root_thread_id = "root"
        run.known_threads.add("root")
        run.terminal_threads.add("root")

        run.thread_status["root"] = "future-unknown-status"
        self.assertFalse(run._ready_for_reconciliation())

        run.thread_status["root"] = "idle"
        self.assertTrue(run._ready_for_reconciliation())

    def test_child_failed_or_interrupted_turn_prevents_closure(self):
        class Client:
            notification_handler = None

        for status in ("failed", "interrupted"):
            with self.subTest(status=status):
                run = UltraRun(Client())  # type: ignore[arg-type]
                run.root_thread_id = "root"
                run.known_threads.update(("root", "child"))
                run.terminal_threads.add("root")
                run.handle_notification(
                    {
                        "method": "turn/completed",
                        "params": {
                            "threadId": "child",
                            "turn": {"id": "child-turn", "status": status},
                        },
                    }
                )

                self.assertTrue(run.protocol_errors)
                self.assertFalse(run._ready_for_reconciliation())

    def test_new_turn_reopens_a_previously_terminal_thread(self):
        class Client:
            notification_handler = None

        run = UltraRun(Client())  # type: ignore[arg-type]
        run.root_thread_id = "root"
        run.known_threads.add("root")
        run.handle_notification(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "root",
                    "turn": {"id": "turn-1", "status": "completed"},
                },
            }
        )
        self.assertIn("root", run.terminal_threads)

        run.handle_notification(
            {
                "method": "turn/started",
                "params": {
                    "threadId": "root",
                    "turn": {"id": "turn-2", "status": "inProgress"},
                },
            }
        )

        self.assertNotIn("root", run.terminal_threads)
        self.assertFalse(run._ready_for_reconciliation())

    def test_reconcile_uses_latest_turn_and_rejects_session_mismatch(self):
        class Client:
            notification_handler = None

            def __init__(self, child_session="session-1", child_turns=None):
                self.child_session = child_session
                self.child_turns = child_turns or [
                    {"id": "child-1", "status": "completed"},
                    {"id": "child-2", "status": "inProgress"},
                ]

            def request(self, method, params):
                if method == "thread/loaded/list":
                    return {"data": ["root", "child"], "nextCursor": None}
                if method == "thread/read":
                    thread_id = params["threadId"]
                    if thread_id == "root":
                        return {
                            "thread": {
                                "id": "root",
                                "sessionId": "session-1",
                                "status": {"type": "idle"},
                                "turns": [
                                    {"id": "root-turn", "status": "completed"}
                                ],
                            }
                        }
                    return {
                        "thread": {
                            "id": "child",
                            "sessionId": self.child_session,
                            "parentThreadId": "root",
                            "status": {"type": "active"},
                            "turns": self.child_turns,
                        }
                    }
                raise AssertionError(method)

        run = UltraRun(Client())  # type: ignore[arg-type]
        run.root_thread_id = "root"
        run.session_id = "session-1"
        run.known_threads.update(("root", "child"))
        run.parent_by_thread["child"] = "root"
        run.terminal_threads.update(("root", "child"))
        run.reconcile()
        self.assertNotIn("child", run.terminal_threads)

        stale = UltraRun(
            Client(
                child_turns=[{"id": "child-1", "status": "completed"}]
            )
        )  # type: ignore[arg-type]
        stale.root_thread_id = "root"
        stale.session_id = "session-1"
        stale.known_threads.update(("root", "child"))
        stale.parent_by_thread["child"] = "root"
        stale.active_turn_by_thread["child"] = "child-2"
        stale.terminal_threads.update(("root", "child"))
        stale.reconcile()
        self.assertNotIn("child", stale.terminal_threads)
        self.assertEqual("child-2", stale.active_turn_by_thread["child"])

        mismatched = UltraRun(Client(child_session="other-session"))  # type: ignore[arg-type]
        mismatched.root_thread_id = "root"
        mismatched.session_id = "session-1"
        mismatched.known_threads.update(("root", "child"))
        mismatched.parent_by_thread["child"] = "root"
        with self.assertRaisesRegex(Exception, "session"):
            mismatched.reconcile()

        for missing in ("status",):
            with self.subTest(missing=missing):
                class InvalidClient(Client):
                    def request(self, method, params):
                        response = super().request(method, params)
                        if (
                            method == "thread/read"
                            and params["threadId"] == "child"
                        ):
                            response["thread"].pop(missing, None)
                        return response

                invalid = UltraRun(InvalidClient())  # type: ignore[arg-type]
                invalid.root_thread_id = "root"
                invalid.session_id = "session-1"
                invalid.known_threads.update(("root", "child"))
                invalid.parent_by_thread["child"] = "root"
                with self.assertRaisesRegex(Exception, "status|turn"):
                    invalid.reconcile()


if __name__ == "__main__":
    unittest.main()
