#!/usr/bin/env python3
"""MiniMax custom-provider compatibility gate contracts."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.reverse_benchmark.compatibility import (
    OPENAI_NATIVE_COMPATIBILITY_SCHEMA,
    _actual_canary_attempt,
    _normalized_canary_attempt,
    _receipt_id,
    evaluate_static_preflight,
    run_openai_proxy_compatibility,
    run_openai_native_compatibility,
    run_minimax_compatibility,
    validate_compatibility_receipt_set,
    validate_openai_proxy_compatibility_receipt,
    validate_openai_native_compatibility_receipt,
    validate_minimax_compatibility_receipt,
)
from tools.reverse_benchmark.credentials import LoadedCredential
from tools.reverse_benchmark.matrix import benchmark_matrix
from tools.reverse_benchmark.runner import (
    minimax_provider_contract,
    openai_native_provider_contract,
    openai_proxy_provider_contract,
)


class MiniMaxCompatibilityTests(unittest.TestCase):
    def test_receipt_set_dispatches_native_openai_receipt_by_schema(self):
        receipt = {
            "schema": OPENAI_NATIVE_COMPATIBILITY_SCHEMA,
            "receipt_id": "a" * 64,
            "provider_contract": openai_native_provider_contract(),
        }
        with patch(
            "tools.reverse_benchmark.compatibility.validate_openai_native_compatibility_receipt",
            return_value=receipt,
        ) as native_validator, patch(
            "tools.reverse_benchmark.compatibility.validate_openai_proxy_compatibility_receipt"
        ) as proxy_validator:
            actual = validate_compatibility_receipt_set(
                {"openai": receipt},
                expected_receipt_ids={"openai": "a" * 64},
                expected_provider_contracts={
                    "openai": openai_native_provider_contract()
                },
                expected_codex_sha256="c" * 64,
            )

        self.assertEqual({"openai": receipt}, actual)
        native_validator.assert_called_once_with(
            receipt, expected_codex_sha256="c" * 64
        )
        proxy_validator.assert_not_called()

    def test_receipt_set_accepts_exact_openai_only_provider_subset(self):
        receipt = {
            "receipt_id": "a" * 64,
            "provider_contract": {"kind": "openai"},
        }
        with patch(
            "tools.reverse_benchmark.compatibility.validate_openai_proxy_compatibility_receipt",
            return_value=receipt,
        ) as openai_validator, patch(
            "tools.reverse_benchmark.compatibility.validate_minimax_compatibility_receipt"
        ) as minimax_validator:
            actual = validate_compatibility_receipt_set(
                {"openai": receipt},
                expected_receipt_ids={"openai": "a" * 64},
                expected_provider_contracts={"openai": {"kind": "openai"}},
                expected_codex_sha256="c" * 64,
            )

        self.assertEqual({"openai": receipt}, actual)
        openai_validator.assert_called_once_with(
            receipt, expected_codex_sha256="c" * 64
        )
        minimax_validator.assert_not_called()

    def test_receipt_set_requires_valid_selected_providers_and_one_codex_identity(self):
        receipts = {
            "openai": {
                "receipt_id": "a" * 64,
                "provider_contract": openai_proxy_provider_contract(),
            },
            "minimax": {
                "receipt_id": "b" * 64,
                "provider_contract": minimax_provider_contract(),
            },
        }
        with patch(
            "tools.reverse_benchmark.compatibility.validate_openai_proxy_compatibility_receipt",
            return_value=receipts["openai"],
        ) as openai_validator, patch(
            "tools.reverse_benchmark.compatibility.validate_minimax_compatibility_receipt",
            return_value=receipts["minimax"],
        ) as minimax_validator:
            validated = validate_compatibility_receipt_set(
                receipts,
                expected_receipt_ids={"openai": "a" * 64, "minimax": "b" * 64},
                expected_provider_contracts={
                    "openai": openai_proxy_provider_contract(),
                    "minimax": minimax_provider_contract(),
                },
                expected_codex_sha256="c" * 64,
            )

        self.assertEqual(receipts, validated)
        openai_validator.assert_called_once_with(
            receipts["openai"], expected_codex_sha256="c" * 64
        )
        minimax_validator.assert_called_once_with(
            receipts["minimax"], expected_codex_sha256="c" * 64
        )
        for invalid in (
            {},
            {**receipts, "unexpected": {}},
        ):
            with self.subTest(keys=sorted(invalid)), self.assertRaisesRegex(
                ValueError, "invalid providers"
            ):
                validate_compatibility_receipt_set(
                    invalid, expected_codex_sha256="c" * 64
                )

    def test_openai_proxy_dynamic_gate_requires_explicit_plaintext_authorization(self):
        static = {"compatible": True}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "proxy-compatibility"
            with self.assertRaisesRegex(ValueError, "plaintext auth relay"):
                run_openai_proxy_compatibility(
                    repo_root=Path(directory),
                    output_root=output,
                    static_preflight=static,
                    attempt_executor=lambda **_kwargs: self.fail(
                        "dynamic canary must not run without authorization"
                    ),
                )
            self.assertFalse(output.exists())

    def test_openai_proxy_gate_runs_four_model_and_harness_canaries(self):
        calls: list[tuple[str, str, str, object]] = []
        required_help = " ".join(
            (
                "--json",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--strict-config",
                "--sandbox",
            )
        )
        static = evaluate_static_preflight(
            codex_path="/Applications/Codex/codex",
            codex_sha256="d" * 64,
            version="codex-cli 1.0",
            version_returncode=0,
            exec_help=required_help,
            help_returncode=0,
            config_probe_returncode=0,
            config_probe_output="proxy config ok",
        )

        def fake_attempt(**kwargs):
            configuration = kwargs["configuration"]
            calls.append(
                (
                    configuration.id,
                    configuration.system_mode,
                    kwargs["kind"],
                    kwargs["credential"],
                )
            )
            tool = kwargs["kind"] == "tool-loop"
            usage = {
                "uncached_input": 10,
                "cached_input": 0,
                "cache_write_input": 0,
                "output": 2,
                "reasoning_output": 1,
            }
            return {
                "passed": True,
                "exit_code": 0,
                "guard_reason": "completed",
                "usage_complete": True,
                "telemetry_failed": False,
                "telemetry_errors": [],
                "usage": usage,
                "requests": [{"usage": usage}],
                "request_count": 1,
                "tool_calls": 1 if tool else 0,
                "successful_tool_calls": 1 if tool else 0,
                "answer_matched": True,
                "wall_time_ms": 100,
            }

        with tempfile.TemporaryDirectory() as directory:
            receipt = run_openai_proxy_compatibility(
                repo_root=Path(directory),
                output_root=Path(directory) / "proxy-compatibility",
                static_preflight=static,
                attempt_executor=fake_attempt,
                created_at="2026-08-16T00:00:00+00:00",
                allow_plaintext_auth_relay=True,
            )
            persisted = json.loads(
                (
                    Path(directory)
                    / "proxy-compatibility"
                    / "receipt.json"
                ).read_text()
            )

        self.assertEqual(receipt, persisted)
        self.assertTrue(receipt["compatible"])
        self.assertEqual(openai_proxy_provider_contract(), receipt["provider_contract"])
        self.assertEqual(
            {
                "openai-gpt-5.6-luna-low",
                "openai-gpt-5.6-terra-low",
                "openai-gpt-5.6-sol-low",
                "openai-gpt-5.6-sol-ultra",
            },
            {configuration_id for configuration_id, _, _, _ in calls},
        )
        self.assertEqual(1, sum(mode == "multi-agent" for _, mode, _, _ in calls))
        self.assertEqual(
            {("openai-gpt-5.6-luna-low", "tool-loop")},
            {
                (configuration_id, kind)
                for configuration_id, _, kind, _ in calls
                if kind == "tool-loop"
            },
        )
        self.assertTrue(all(credential is None for _, _, _, credential in calls))
        self.assertEqual(4, receipt["overhead"]["physical_attempts"])
        self.assertTrue(receipt["plaintext_auth_relay_authorized"])
        self.assertNotIn("credential_source", receipt)
        self.assertNotIn("env_key", json.dumps(receipt).lower())
        validate_openai_proxy_compatibility_receipt(
            receipt,
            expected_codex_sha256="d" * 64,
        )

        changed = copy.deepcopy(receipt)
        changed["plaintext_auth_relay_authorized"] = False
        changed["receipt_id"] = _receipt_id(changed)
        with self.assertRaisesRegex(ValueError, "plaintext auth relay"):
            validate_openai_proxy_compatibility_receipt(
                changed,
                expected_codex_sha256="d" * 64,
            )

    def test_openai_native_gate_runs_exact_reduced_models_without_relay(self):
        calls: list[tuple[str, str, str, str]] = []
        required_help = " ".join(
            (
                "--json",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--strict-config",
                "--sandbox",
            )
        )
        static = evaluate_static_preflight(
            codex_path="/Applications/Codex/codex",
            codex_sha256="d" * 64,
            version="codex-cli 1.0",
            version_returncode=0,
            exec_help=required_help,
            help_returncode=0,
            config_probe_returncode=0,
            config_probe_output="native config ok",
        )

        def fake_attempt(**kwargs):
            configuration = kwargs["configuration"]
            calls.append(
                (
                    configuration.id,
                    configuration.transport_profile,
                    configuration.system_mode,
                    kwargs["kind"],
                )
            )
            tool = kwargs["kind"] == "tool-loop"
            usage = {
                "uncached_input": 10,
                "cached_input": 0,
                "cache_write_input": 0,
                "output": 2,
                "reasoning_output": 1,
            }
            return {
                "passed": True,
                "exit_code": 0,
                "guard_reason": "completed",
                "usage_complete": True,
                "telemetry_failed": False,
                "telemetry_errors": [],
                "usage": usage,
                "requests": [{"usage": usage}],
                "request_count": 1,
                "tool_calls": 1 if tool else 0,
                "successful_tool_calls": 1 if tool else 0,
                "answer_matched": True,
                "wall_time_ms": 100,
            }

        with tempfile.TemporaryDirectory() as directory:
            receipt = run_openai_native_compatibility(
                repo_root=Path(directory),
                output_root=Path(directory) / "native-compatibility",
                static_preflight=static,
                attempt_executor=fake_attempt,
                created_at="2026-08-19T00:00:00+00:00",
            )

        self.assertTrue(receipt["compatible"])
        self.assertEqual(
            openai_native_provider_contract(), receipt["provider_contract"]
        )
        self.assertNotIn("plaintext_auth_relay_authorized", receipt)
        self.assertEqual(
            {
                "openai-gpt-5.6-luna-max",
                "openai-gpt-5.6-terra-max",
                "openai-gpt-5.6-sol-medium",
                "openai-gpt-5.6-sol-ultra",
            },
            {configuration_id for configuration_id, _, _, _ in calls},
        )
        self.assertEqual({"codex-native"}, {profile for _, profile, _, _ in calls})
        self.assertEqual(1, sum(mode == "multi-agent" for _, _, mode, _ in calls))
        self.assertEqual(
            {("openai-gpt-5.6-luna-max", "tool-loop")},
            {
                (configuration_id, kind)
                for configuration_id, _, _, kind in calls
                if kind == "tool-loop"
            },
        )
        validate_openai_native_compatibility_receipt(
            receipt,
            expected_codex_sha256="d" * 64,
        )

    def test_openai_proxy_static_failure_skips_dynamic_canaries(self):
        calls: list[object] = []
        static = {"compatible": False}
        with tempfile.TemporaryDirectory() as directory:
            receipt = run_openai_proxy_compatibility(
                repo_root=Path(directory),
                output_root=Path(directory) / "proxy-compatibility",
                static_preflight=static,
                attempt_executor=lambda **kwargs: calls.append(kwargs),
                created_at="2026-08-16T00:00:00+00:00",
            )

        self.assertFalse(receipt["compatible"])
        self.assertEqual([], calls)
        with self.assertRaises(ValueError):
            validate_openai_proxy_compatibility_receipt(receipt)

    def test_actual_canary_cleans_workspace_when_execution_raises(self):
        configuration = next(
            item for item in benchmark_matrix() if item.model == "MiniMax-M3"
        )
        credential = LoadedCredential(value="sentinel-secret", source="fixture")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "canary"
            with patch(
                "tools.reverse_benchmark.compatibility.subprocess.run",
                side_effect=RuntimeError("simulated runner failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "simulated runner failure"):
                    _actual_canary_attempt(
                        repo_root=Path(directory),
                        output_dir=output,
                        configuration=configuration,
                        credential=credential,
                        kind="plain-text",
                        index=1,
                        nonce="BENCH_cleanup_nonce",
                    )

            self.assertFalse((output / "workspace").exists())

    def test_static_preflight_requires_every_cli_and_config_capability(self):
        required_help = " ".join(
            (
                "--json",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--strict-config",
                "--sandbox",
            )
        )
        compatible = evaluate_static_preflight(
            codex_path="/Applications/Codex/codex",
            codex_sha256="a" * 64,
            version="codex-cli 1.0",
            version_returncode=0,
            exec_help=required_help,
            help_returncode=0,
            config_probe_returncode=0,
            config_probe_output="catalog ok",
        )
        incompatible = evaluate_static_preflight(
            codex_path="/Applications/Codex/codex",
            codex_sha256="a" * 64,
            version="codex-cli 1.0",
            version_returncode=0,
            exec_help=required_help.replace("--strict-config", ""),
            help_returncode=0,
            config_probe_returncode=0,
            config_probe_output="catalog ok",
        )

        self.assertTrue(compatible["compatible"])
        self.assertFalse(incompatible["compatible"])
        self.assertFalse(incompatible["capabilities"]["--strict-config"])
        self.assertNotIn("catalog ok", json.dumps(compatible))

        command_failed = evaluate_static_preflight(
            codex_path="/Applications/Codex/codex",
            codex_sha256="a" * 64,
            version="codex-cli 1.0",
            version_returncode=0,
            exec_help=required_help,
            help_returncode=7,
            config_probe_returncode=0,
            config_probe_output="catalog ok",
        )
        self.assertFalse(command_failed["compatible"])

    def test_dynamic_gate_requires_three_text_and_three_tool_runs_per_model(self):
        calls: list[tuple[str, str, int]] = []
        credential = LoadedCredential(value="sentinel-secret", source="fixture")
        static = {
            "compatible": True,
            "codex": {
                "path": "/Applications/Codex/codex",
                "sha256": "b" * 64,
                "version": "codex-cli 1.0",
            },
            "capabilities": {
                flag: True
                for flag in (
                    "--json",
                    "--ephemeral",
                    "--ignore-user-config",
                    "--ignore-rules",
                    "--strict-config",
                    "--sandbox",
                )
            },
            "command_checks": {
                "version_returncode": 0,
                "help_returncode": 0,
            },
            "config_probe": {"returncode": 0, "output_sha256": "c" * 64},
        }

        def fake_attempt(**kwargs):
            calls.append((kwargs["configuration"].model, kwargs["kind"], kwargs["index"]))
            tool = kwargs["kind"] == "tool-loop"
            usage = {
                "uncached_input": 10,
                "cached_input": 0,
                "cache_write_input": 0,
                "output": 2,
                "reasoning_output": 1,
            }
            return {
                "passed": True,
                "exit_code": 0,
                "guard_reason": "completed",
                "usage_complete": True,
                "telemetry_failed": False,
                "telemetry_errors": [],
                "usage": usage,
                "requests": [{"usage": usage}],
                "request_count": 1,
                "tool_calls": 1 if tool else 0,
                "successful_tool_calls": 1 if tool else 0,
                "answer_matched": True,
                "wall_time_ms": 100,
            }

        with tempfile.TemporaryDirectory() as directory:
            receipt = run_minimax_compatibility(
                repo_root=Path(directory),
                output_root=Path(directory) / "compatibility",
                credential=credential,
                static_preflight=static,
                attempt_executor=fake_attempt,
                created_at="2026-08-16T00:00:00+00:00",
            )

        self.assertEqual(12, len(calls))
        self.assertEqual(
            {
                (model, kind, index)
                for model in ("MiniMax-M3", "MiniMax-M2.7-highspeed")
                for kind in ("plain-text", "tool-loop")
                for index in (1, 2, 3)
            },
            set(calls),
        )
        self.assertTrue(receipt["compatible"])
        self.assertNotIn("sentinel-secret", json.dumps(receipt))
        self.assertEqual(
            {
                "billing_status": "complete",
                "physical_attempts": 12,
                "physical_wall_time_ms": "1200",
                "api_cost_cny": "0.0006804",
                "minimax_token_plan_input_tokens": 120,
                "minimax_token_plan_output_tokens": 24,
            },
            receipt["overhead"],
        )
        failed_telemetry = fake_attempt(
            configuration=next(
                item for item in benchmark_matrix() if item.model == "MiniMax-M3"
            ),
            kind="plain-text",
            index=99,
        )
        failed_telemetry["telemetry_failed"] = True
        failed_telemetry["telemetry_errors"] = ["turn.failed"]
        normalized_failed = _normalized_canary_attempt(
            next(item for item in benchmark_matrix() if item.model == "MiniMax-M3"),
            "plain-text",
            1,
            "d" * 64,
            failed_telemetry,
        )
        self.assertFalse(normalized_failed["passed"])
        validate_minimax_compatibility_receipt(
            receipt,
            expected_codex_sha256="b" * 64,
        )

        tampered = copy.deepcopy(receipt)
        tampered["models"]["MiniMax-M3"]["plain-text"]["attempts"].pop()
        with self.assertRaises(ValueError):
            validate_minimax_compatibility_receipt(
                tampered,
                expected_codex_sha256="b" * 64,
            )

        for mutation in (
            "exit",
            "telemetry_error",
            "telemetry_failed",
            "duplicate_canary",
            "provider_contract",
            "pi",
            "created_at",
            "overhead",
        ):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(receipt)
                if mutation == "exit":
                    changed["models"]["MiniMax-M3"]["plain-text"]["attempts"][0][
                        "exit_code"
                    ] = 7
                    changed["receipt_id"] = _receipt_id(changed)
                elif mutation == "telemetry_error":
                    changed["models"]["MiniMax-M3"]["plain-text"]["attempts"][0][
                        "telemetry_error"
                    ] = "parser reported an error"
                    changed["receipt_id"] = _receipt_id(changed)
                elif mutation == "telemetry_failed":
                    changed["models"]["MiniMax-M3"]["plain-text"]["attempts"][0][
                        "telemetry_failed"
                    ] = True
                    changed["models"]["MiniMax-M3"]["plain-text"]["attempts"][0][
                        "telemetry_errors"
                    ] = ["turn.failed"]
                    changed["receipt_id"] = _receipt_id(changed)
                elif mutation == "duplicate_canary":
                    first = changed["models"]["MiniMax-M3"]["plain-text"][
                        "attempts"
                    ][0]["canary_id"]
                    changed["models"]["MiniMax-M2.7-highspeed"]["tool-loop"][
                        "attempts"
                    ][2]["canary_id"] = first
                    changed["receipt_id"] = _receipt_id(changed)
                elif mutation == "provider_contract":
                    changed["provider_contract"]["base_url"] = (
                        "https://drift.invalid/v1"
                    )
                    changed["receipt_id"] = _receipt_id(changed)
                elif mutation == "pi":
                    changed["pi_fallback"]["enabled"] = True
                    changed["receipt_id"] = _receipt_id(changed)
                elif mutation == "created_at":
                    changed["created_at"] = "2099-01-01T00:00:00+00:00"
                else:
                    changed["overhead"]["api_cost_cny"] = "999"
                    changed["receipt_id"] = _receipt_id(changed)
                with self.assertRaises(ValueError):
                    validate_minimax_compatibility_receipt(
                        changed,
                        expected_codex_sha256="b" * 64,
                    )

    def test_executor_exception_becomes_a_failed_secret_free_receipt(self):
        credential = LoadedCredential(value="sentinel-secret", source="fixture")
        static = {
            "compatible": True,
            "codex": {
                "path": "/Applications/Codex/codex",
                "sha256": "f" * 64,
                "version": "codex-cli 1.0",
            },
            "capabilities": {
                flag: True
                for flag in (
                    "--json",
                    "--ephemeral",
                    "--ignore-user-config",
                    "--ignore-rules",
                    "--strict-config",
                    "--sandbox",
                )
            },
            "command_checks": {
                "version_returncode": 0,
                "help_returncode": 0,
            },
            "config_probe": {"returncode": 0, "output_sha256": "e" * 64},
        }

        def raising_attempt(**_kwargs):
            raise RuntimeError("sentinel-secret must not be persisted")

        with tempfile.TemporaryDirectory() as directory:
            receipt = run_minimax_compatibility(
                repo_root=Path(directory),
                output_root=Path(directory) / "compatibility",
                credential=credential,
                static_preflight=static,
                attempt_executor=raising_attempt,
                created_at="2026-08-16T00:00:00+00:00",
            )

        serialized = json.dumps(receipt)
        self.assertFalse(receipt["compatible"])
        self.assertNotIn("sentinel-secret", serialized)
        self.assertEqual(12, receipt["overhead"]["physical_attempts"])
        self.assertEqual("unknown", receipt["overhead"]["billing_status"])

    def test_failed_canary_never_produces_a_compatible_receipt(self):
        credential = LoadedCredential(value="sentinel-secret", source="fixture")
        static = {
            "compatible": True,
            "codex": {
                "path": "/Applications/Codex/codex",
                "sha256": "d" * 64,
                "version": "codex-cli 1.0",
            },
            "capabilities": {},
            "command_checks": {
                "version_returncode": 0,
                "help_returncode": 0,
            },
            "config_probe": {"returncode": 0, "output_sha256": "e" * 64},
        }

        def failed_attempt(**kwargs):
            return {
                "passed": kwargs["index"] != 2,
                "exit_code": 1 if kwargs["index"] == 2 else 0,
                "guard_reason": "completed",
                "usage_complete": kwargs["index"] != 2,
                "usage": None,
                "request_count": 0,
                "tool_calls": 0,
                "successful_tool_calls": 0,
                "answer_matched": False,
            }

        with tempfile.TemporaryDirectory() as directory:
            receipt = run_minimax_compatibility(
                repo_root=Path(directory),
                output_root=Path(directory) / "compatibility",
                credential=credential,
                static_preflight=static,
                attempt_executor=failed_attempt,
                created_at="2026-08-16T00:00:00+00:00",
            )

        self.assertFalse(receipt["compatible"])
        with self.assertRaises(ValueError):
            validate_minimax_compatibility_receipt(
                receipt,
                expected_codex_sha256="d" * 64,
            )


if __name__ == "__main__":
    unittest.main()
