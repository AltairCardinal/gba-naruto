#!/usr/bin/env python3
"""Unit contracts for the reverse-engineering model benchmark harness."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from unittest import mock

from tools.reverse_benchmark.events import parse_codex_jsonl, parse_pi_jsonl
from tools.reverse_benchmark.matrix import (
    CODEX_NATIVE_TRANSPORT_PROFILE,
    benchmark_configuration,
    benchmark_matrix,
)
from tools.reverse_benchmark.pricing import (
    NormalizedUsage,
    codex_credit_estimate,
    minimax_api_cost_cny,
    openai_api_cost_usd,
)
from tools.reverse_benchmark.runner import (
    CODEX_NATIVE_HTTP_BASE_URL,
    CODEX_NATIVE_HTTP_PROVIDER_ID,
    CODEX_NATIVE_PROVIDER_ID,
    CODEX_NATIVE_TRANSPORT_PROFILE,
    OPENAI_PROXY_BASE_URL,
    OPENAI_PROXY_PROVIDER_ID,
    base_run_manifest,
    build_codex_command,
    build_ultra_appserver_command,
    new_run_id,
    openai_native_provider_contract,
    openai_proxy_provider_contract,
    write_minimax_catalog,
)


ROOT = Path(__file__).resolve().parents[1]


class BenchmarkMatrixTests(unittest.TestCase):
    def test_native_transport_rejects_openai_configurations_outside_reduced_gate(self):
        with self.assertRaisesRegex(ValueError, "native benchmark configuration"):
            benchmark_configuration(
                "openai-gpt-5.6-sol-low",
                openai_transport_profile=CODEX_NATIVE_TRANSPORT_PROFILE,
            )

    def test_matrix_contains_the_approved_nineteen_configurations(self):
        configurations = benchmark_matrix()

        self.assertEqual(19, len(configurations))
        self.assertEqual(19, len({item.id for item in configurations}))
        self.assertNotIn("none", {item.effort for item in configurations})
        self.assertEqual(
            {
                "low",
                "medium",
                "high",
                "xhigh",
                "max",
                "ultra",
            },
            {
                item.effort
                for item in configurations
                if item.model in {"gpt-5.6-sol", "gpt-5.6-terra"}
            },
        )
        self.assertEqual(
            {"openai-proxy"},
            {
                item.transport_profile
                for item in configurations
                if item.provider == "openai"
            },
        )
        self.assertEqual(
            {"minimax-token-plan"},
            {
                item.transport_profile
                for item in configurations
                if item.provider == "minimax"
            },
        )
        self.assertEqual(
            {"low", "medium", "high", "xhigh", "max"},
            {
                item.effort
                for item in configurations
                if item.model == "gpt-5.6-luna"
            },
        )
        self.assertEqual(
            {
                ("MiniMax-M3", "adaptive"),
                ("MiniMax-M2.7-highspeed", "native"),
            },
            {
                (item.model, item.effort)
                for item in configurations
                if item.provider == "minimax"
            },
        )

    def test_ultra_is_explicitly_a_multi_agent_system_mode(self):
        configurations = benchmark_matrix()
        ultra = [item for item in configurations if item.effort == "ultra"]

        self.assertEqual(2, len(ultra))
        self.assertEqual(
            {"gpt-5.6-sol", "gpt-5.6-terra"},
            {item.model for item in ultra},
        )
        self.assertEqual({"multi-agent"}, {item.system_mode for item in ultra})
        self.assertTrue(
            all(
                item.system_mode == "single-agent"
                for item in configurations
                if item.effort != "ultra"
            )
        )


class BenchmarkPricingTests(unittest.TestCase):
    def test_openai_cost_uses_uncached_cached_write_and_output_buckets(self):
        usage = NormalizedUsage(
            uncached_input=90_000,
            cached_input=90_000,
            cache_write_input=90_000,
            output=1_000_000,
            reasoning_output=400_000,
        )

        self.assertEqual(
            Decimal("31.0575"),
            openai_api_cost_usd("gpt-5.6-sol", usage),
        )
        self.assertEqual(
            Decimal("12.423"),
            openai_api_cost_usd("gpt-5.6-terra", usage),
        )
        self.assertEqual(
            Decimal("1.2423"),
            openai_api_cost_usd("gpt-5.6-luna", usage),
        )

    def test_reasoning_tokens_are_not_double_billed_outside_output(self):
        without_breakout = NormalizedUsage(output=2_000_000)
        with_breakout = NormalizedUsage(
            output=2_000_000,
            reasoning_output=1_500_000,
        )

        self.assertEqual(
            openai_api_cost_usd("gpt-5.6-sol", without_breakout),
            openai_api_cost_usd("gpt-5.6-sol", with_breakout),
        )

    def test_codex_credit_estimate_keeps_cache_write_assumption_explicit(self):
        estimate = codex_credit_estimate(
            "gpt-5.6-terra",
            NormalizedUsage(
                uncached_input=1_000_000,
                cached_input=1_000_000,
                cache_write_input=1_000_000,
                output=1_000_000,
            ),
        )

        self.assertEqual(Decimal("405"), estimate.credits)
        self.assertEqual("input-rate", estimate.cache_write_assumption)
        self.assertFalse(estimate.is_actual_ledger_value)

    def test_minimax_cost_uses_native_thinking_models_without_fake_tiers(self):
        usage = NormalizedUsage(
            uncached_input=100_000,
            cached_input=100_000,
            cache_write_input=100_000,
            output=1_000_000,
        )

        self.assertEqual(
            Decimal("8.862"),
            minimax_api_cost_cny("MiniMax-M3", usage),
        )
        self.assertEqual(
            Decimal("17.5245"),
            minimax_api_cost_cny("MiniMax-M2.7-highspeed", usage),
        )

    def test_minimax_m3_long_context_rate_is_selected_per_request(self):
        usage = NormalizedUsage(uncached_input=513_000, output=1_000_000)

        self.assertEqual(
            Decimal("18.9546"),
            minimax_api_cost_cny(
                "MiniMax-M3",
                usage,
                request_input_tokens=513_000,
            ),
        )


class BenchmarkEventTests(unittest.TestCase):
    def test_recovered_codex_reconnect_is_not_a_terminal_failure(self):
        events = [
            {
                "type": "error",
                "message": (
                    "Reconnecting... 2/5 (stream disconnected before completion: "
                    "Connection reset by peer)"
                ),
            },
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 100,
                    "cached_input_tokens": 0,
                    "output_tokens": 10,
                    "reasoning_output_tokens": 2,
                },
            },
            {"type": "process.exited", "exit_code": 0},
        ]

        telemetry = parse_codex_jsonl(
            "\n".join(json.dumps(event) for event in events)
        )

        self.assertTrue(telemetry.usage_complete)
        self.assertFalse(telemetry.failed)
        self.assertEqual((), telemetry.errors)

    def test_unrecovered_codex_reconnect_still_fails_closed(self):
        events = [
            {"type": "error", "message": "Reconnecting... 5/5 (reset)"},
            {"type": "process.exited", "exit_code": 1},
        ]

        telemetry = parse_codex_jsonl(
            "\n".join(json.dumps(event) for event in events)
        )

        self.assertFalse(telemetry.usage_complete)
        self.assertTrue(telemetry.failed)
        self.assertIn("process exited with 1", telemetry.errors)
        self.assertIn("missing usage telemetry", telemetry.errors)

    def test_codex_parser_normalizes_cached_input_and_sums_turns(self):
        events = [
            {
                "type": "item.started",
                "item": {"id": "cmd-1", "type": "command_execution"},
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "cmd-1",
                    "type": "command_execution",
                    "exit_code": 0,
                },
            },
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 1000,
                    "cached_input_tokens": 600,
                    "cache_write_input_tokens": 100,
                    "output_tokens": 200,
                    "reasoning_output_tokens": 150,
                },
            },
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 500,
                    "cached_input_tokens": 0,
                    "output_tokens": 50,
                    "reasoning_output_tokens": 0,
                },
            },
        ]

        telemetry = parse_codex_jsonl(
            "\n".join(json.dumps(event) for event in events)
        )

        self.assertEqual(1, telemetry.tool_calls)
        self.assertEqual(1, telemetry.successful_tool_calls)
        self.assertEqual(800, telemetry.usage.uncached_input)
        self.assertEqual(600, telemetry.usage.cached_input)
        self.assertEqual(100, telemetry.usage.cache_write_input)
        self.assertEqual(250, telemetry.usage.output)
        self.assertEqual(150, telemetry.usage.reasoning_output)
        self.assertEqual(2, len(telemetry.requests))
        self.assertEqual("turn-aggregate", telemetry.usage_granularity)
        self.assertEqual(
            {"turn-aggregate"},
            {request.usage_granularity for request in telemetry.requests},
        )
        self.assertTrue(telemetry.usage_complete)
        self.assertFalse(telemetry.failed)

    def test_pi_parser_counts_only_message_end_and_ignores_duplicate_usage(self):
        usage = {
            "input": 100,
            "output": 20,
            "cacheRead": 50,
            "cacheWrite": 10,
            "reasoning": 12,
        }
        events = [
            {"type": "tool_execution_start", "toolCallId": "tool-1"},
            {
                "type": "tool_execution_end",
                "toolCallId": "tool-1",
                "isError": False,
            },
            {"type": "turn_end", "message": {"usage": usage}},
            {"type": "message_end", "message": {"usage": usage}},
            {"type": "agent_end", "messages": [{"usage": usage}]},
        ]

        telemetry = parse_pi_jsonl(
            "\n".join(json.dumps(event) for event in events)
        )

        self.assertEqual(1, telemetry.tool_calls)
        self.assertEqual(1, telemetry.successful_tool_calls)
        self.assertEqual(100, telemetry.usage.uncached_input)
        self.assertEqual(50, telemetry.usage.cached_input)
        self.assertEqual(10, telemetry.usage.cache_write_input)
        self.assertEqual(20, telemetry.usage.output)
        self.assertEqual(12, telemetry.usage.reasoning_output)
        self.assertEqual(1, len(telemetry.requests))
        self.assertTrue(telemetry.usage_complete)

    def test_explicit_duplicate_usage_ids_are_not_double_counted(self):
        codex_event = {
            "type": "turn.completed",
            "turn_id": "turn-1",
            "usage": {"input_tokens": 10, "output_tokens": 2},
        }
        pi_event = {
            "type": "message_end",
            "message": {
                "id": "message-1",
                "usage": {"input": 7, "output": 3, "cacheWrite": 4},
            },
        }

        codex = parse_codex_jsonl(
            "\n".join(json.dumps(codex_event) for _ in range(2))
        )
        pi = parse_pi_jsonl("\n".join(json.dumps(pi_event) for _ in range(2)))

        self.assertEqual(10, codex.usage.uncached_input)
        self.assertEqual(1, len(codex.requests))
        self.assertEqual(4, pi.usage.cache_write_input)
        self.assertEqual(1, len(pi.requests))

    def test_missing_usage_fails_closed_instead_of_becoming_zero_cost(self):
        telemetry = parse_codex_jsonl(
            json.dumps({"type": "process.exited", "exit_code": 0})
        )

        self.assertTrue(telemetry.failed)
        self.assertFalse(telemetry.usage_complete)
        self.assertIn("missing usage telemetry", telemetry.errors)

    def test_appserver_all_agent_scope_requires_a_valid_closure_marker(self):
        request = {
            "type": "turn.completed",
            "turn_id": "root-thread:1",
            "thread_id": "root-thread",
            "usage": {"input_tokens": 10, "output_tokens": 2},
        }
        marker = {
            "type": "benchmark.appserver.completed",
            "usage_scope": "all-agent-threads",
            "request_count": 1,
            "thread_ids": ["root-thread"],
        }

        complete = parse_codex_jsonl(
            "\n".join(json.dumps(event) for event in (request, marker))
        )
        incomplete = parse_codex_jsonl(json.dumps(request))
        mismatched = parse_codex_jsonl(
            "\n".join(
                json.dumps(event)
                for event in (request, {**marker, "request_count": 2})
            )
        )
        duplicate_threads = parse_codex_jsonl(
            "\n".join(
                json.dumps(event)
                for event in (
                    request,
                    {**marker, "thread_ids": ["root-thread", "root-thread"]},
                )
            )
        )
        wrong_threads = parse_codex_jsonl(
            "\n".join(
                json.dumps(event)
                for event in (
                    request,
                    {**marker, "thread_ids": ["different-thread"]},
                )
            )
        )

        self.assertEqual("all-agent-threads", complete.usage_scope)
        self.assertEqual("request", complete.usage_granularity)
        self.assertEqual("request", complete.requests[0].usage_granularity)
        self.assertTrue(complete.usage_complete)
        self.assertIsNone(incomplete.usage_scope)
        self.assertFalse(mismatched.usage_complete)
        self.assertTrue(mismatched.failed)
        self.assertFalse(duplicate_threads.usage_complete)
        self.assertTrue(duplicate_threads.failed)
        self.assertFalse(wrong_threads.usage_complete)
        self.assertTrue(wrong_threads.failed)

    def test_pi_cache_write_subbucket_is_not_added_to_total(self):
        event = {
            "type": "message_end",
            "message": {
                "id": "message-cache",
                "usage": {
                    "input": 1,
                    "output": 1,
                    "cacheWrite": 10,
                    "cacheWrite1h": 6,
                },
            },
        }

        telemetry = parse_pi_jsonl(json.dumps(event))

        self.assertEqual(10, telemetry.usage.cache_write_input)


class BenchmarkCommandTests(unittest.TestCase):
    def test_run_ids_are_unique_128_bit_lowercase_hex(self):
        first = new_run_id()
        second = new_run_id()

        self.assertRegex(first, r"^[0-9a-f]{32}$")
        self.assertRegex(second, r"^[0-9a-f]{32}$")
        self.assertNotEqual(first, second)

    def test_openai_command_is_ephemeral_machine_readable_and_config_isolated(self):
        configuration = next(
            item
            for item in benchmark_matrix()
            if item.id == "openai-gpt-5.6-sol-low"
        )
        with tempfile.TemporaryDirectory() as directory:
            command = build_codex_command(
                configuration,
                workspace=Path(directory),
            )

        self.assertTrue(Path(command[0]).is_absolute())
        self.assertEqual("codex", Path(command[0]).name)
        for required in (
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--strict-config",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
        ):
            self.assertIn(required, command)
        self.assertIn("gpt-5.6-sol", command)
        self.assertIn('model_reasoning_effort="low"', command)
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
            f'model_providers.{OPENAI_PROXY_PROVIDER_ID}.wire_api="responses"',
            command,
        )
        self.assertIn(
            (
                f"model_providers.{OPENAI_PROXY_PROVIDER_ID}."
                "requires_openai_auth=true"
            ),
            command,
        )
        self.assertIn("model_context_window=1050000", command)
        self.assertEqual(
            [command[0], "--ask-for-approval", "never", "exec"], command[:4]
        )
        self.assertIn('shell_environment_policy.inherit="none"', command)
        self.assertIn("plugins", command)
        self.assertEqual("-", command[-1])

    def test_openai_proxy_contract_uses_cached_auth_without_secret_material(self):
        secret_sentinel = "openai-proxy-secret-must-not-be-persisted"
        configuration = next(
            item for item in benchmark_matrix() if item.provider == "openai"
        )
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": secret_sentinel,
                "CODEX_API_KEY": secret_sentinel,
                "CODEX_ACCESS_TOKEN": secret_sentinel,
            },
        ):
            command = build_codex_command(
                configuration,
                workspace=Path(directory),
            )
            contract = openai_proxy_provider_contract()
        rendered = json.dumps(contract, sort_keys=True)
        rendered_command = " ".join(command)

        self.assertEqual(OPENAI_PROXY_BASE_URL, contract["base_url"])
        self.assertEqual("responses", contract["wire_api"])
        self.assertTrue(contract["requires_openai_auth"])
        self.assertEqual(
            "plaintext-http-user-authorized",
            contract["transport_security"],
        )
        self.assertNotIn("env_key", contract)
        self.assertNotIn("api_key", rendered.lower())
        self.assertNotIn(secret_sentinel, rendered)
        self.assertNotIn(secret_sentinel, rendered_command)
        for forbidden in (
            ".env_key=",
            "experimental_bearer_token",
            "Authorization",
            "api_key",
        ):
            self.assertNotIn(forbidden, rendered_command)
        self.assertNotIn("model_catalog_json", rendered_command)

        with self.assertRaisesRegex(ValueError, "frozen benchmark matrix"):
            build_codex_command(
                replace(configuration, model="unexpected-openai-model"),
                workspace=Path("/tmp"),
            )

    def test_openai_native_command_uses_local_codex_provider_without_endpoint_override(self):
        proxy_configuration = next(
            item
            for item in benchmark_matrix()
            if item.id == "openai-gpt-5.6-luna-max"
        )
        configuration = replace(
            proxy_configuration,
            transport_profile=CODEX_NATIVE_TRANSPORT_PROFILE,
        )
        with tempfile.TemporaryDirectory() as directory:
            command = build_codex_command(
                configuration,
                workspace=Path(directory),
            )
        contract = openai_native_provider_contract()
        rendered_command = " ".join(command)
        rendered_contract = json.dumps(contract, sort_keys=True)

        self.assertIn("gpt-5.6-luna", command)
        self.assertIn('model_reasoning_effort="max"', command)
        self.assertNotIn("model_provider=", rendered_command)
        self.assertNotIn("model_providers.", rendered_command)
        self.assertNotIn(OPENAI_PROXY_BASE_URL, rendered_command)
        self.assertEqual(CODEX_NATIVE_PROVIDER_ID, contract["provider_id"])
        self.assertEqual(
            CODEX_NATIVE_TRANSPORT_PROFILE,
            contract["transport_profile"],
        )
        self.assertEqual("none", contract["credential_relay_scope"])
        self.assertFalse(contract["single_agent_transport"]["endpoint_override"])
        self.assertEqual(
            CODEX_NATIVE_HTTP_BASE_URL,
            contract["ultra_transport"]["base_url"],
        )
        self.assertEqual(
            CODEX_NATIVE_HTTP_PROVIDER_ID,
            contract["ultra_transport"]["provider_id"],
        )
        self.assertFalse(contract["ultra_transport"]["supports_websockets"])
        self.assertNotIn("base_url", contract)
        self.assertNotIn(OPENAI_PROXY_BASE_URL, rendered_contract)
        self.assertEqual(
            {
                "gpt-5.6-luna": {"context_window": 1_050_000, "efforts": ["max"]},
                "gpt-5.6-terra": {"context_window": 1_050_000, "efforts": ["max"]},
                "gpt-5.6-sol": {
                    "context_window": 1_050_000,
                    "efforts": ["medium", "ultra"],
                },
            },
            contract["models"],
        )

    def test_native_ultra_command_uses_appserver_without_proxy_endpoint(self):
        proxy_configuration = next(
            item
            for item in benchmark_matrix()
            if item.id == "openai-gpt-5.6-sol-ultra"
        )
        configuration = replace(
            proxy_configuration,
            transport_profile=CODEX_NATIVE_TRANSPORT_PROFILE,
        )
        with tempfile.TemporaryDirectory() as directory:
            command = build_ultra_appserver_command(
                configuration,
                workspace=Path(directory),
                repo_root=ROOT,
            )

        self.assertIn("--native-http-provider", command)
        self.assertNotIn("--native-provider", command)
        self.assertIn(CODEX_NATIVE_HTTP_PROVIDER_ID, command)
        self.assertIn("--base-url", command)
        self.assertIn(CODEX_NATIVE_HTTP_BASE_URL, command)
        self.assertNotIn(OPENAI_PROXY_BASE_URL, " ".join(command))

    def test_minimax_command_uses_responses_env_key_without_secret_in_argv(self):
        configuration = next(
            item
            for item in benchmark_matrix()
            if item.id == "minimax-MiniMax-M2.7-highspeed-native"
        )
        with tempfile.TemporaryDirectory() as directory:
            command = build_codex_command(
                configuration,
                workspace=Path(directory),
                minimax_env_key="BENCH_MINIMAX_API_KEY",
            )

        rendered = " ".join(command)
        self.assertIn('model_provider="minimax"', command)
        self.assertIn(
            'model_providers.minimax.base_url="https://api.minimaxi.com/v1"',
            command,
        )
        self.assertIn('model_providers.minimax.wire_api="responses"', command)
        self.assertIn(
            'model_providers.minimax.env_key="BENCH_MINIMAX_API_KEY"',
            command,
        )
        self.assertIn(
            "model_providers.minimax.requires_openai_auth=false",
            command,
        )
        self.assertIn("model_context_window=204800", command)
        self.assertNotIn("minimax-secret-value", rendered)

    def test_minimax_catalog_is_per_model_and_refuses_overwrite(self):
        configuration = next(
            item
            for item in benchmark_matrix()
            if item.model == "MiniMax-M2.7-highspeed"
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "catalog.json"
            write_minimax_catalog(configuration, destination)
            catalog = json.loads(destination.read_text())
            with self.assertRaises(FileExistsError):
                write_minimax_catalog(configuration, destination)

        self.assertEqual(1, len(catalog["models"]))
        model = catalog["models"][0]
        self.assertEqual("MiniMax-M2.7-highspeed", model["slug"])
        self.assertEqual(["text"], model["input_modalities"])
        self.assertFalse(model["supports_parallel_tool_calls"])
        self.assertEqual(
            [{"effort": "high", "description": "Native thinking"}],
            model["supported_reasoning_levels"],
        )

    def test_ultra_command_routes_through_full_thread_appserver_worker(self):
        configuration = next(
            item
            for item in benchmark_matrix()
            if item.model == "gpt-5.6-sol" and item.effort == "ultra"
        )
        with tempfile.TemporaryDirectory() as directory:
            command = build_ultra_appserver_command(
                configuration,
                workspace=Path(directory),
                repo_root=ROOT,
            )
            completed = subprocess.run(
                [*command, "--help"],
                cwd=Path(directory),
                capture_output=True,
                text=True,
                timeout=15,
            )

        self.assertIn("appserver_worker.py", command[2])
        self.assertIn("gpt-5.6-sol", command)
        self.assertIn("ultra", command)
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_base_manifest_binds_configuration_challenge_and_inputs(self):
        configuration = benchmark_matrix()[0]
        manifest = base_run_manifest(
            configuration,
            challenge_id="fixed-pointer-table",
            input_hashes={"input/z.bin": "b", "input/a.bin": "a"},
        )

        self.assertEqual("reverse-model-benchmark-run-v1", manifest["schema"])
        self.assertRegex(manifest["run_id"], r"^[0-9a-f]{32}$")
        self.assertEqual(configuration.id, manifest["configuration"]["id"])
        self.assertEqual("fixed-pointer-table", manifest["challenge_id"])
        self.assertEqual(
            ["input/a.bin", "input/z.bin"],
            list(manifest["input_hashes"]),
        )
        self.assertEqual("prepared", manifest["status"])


if __name__ == "__main__":
    unittest.main()
