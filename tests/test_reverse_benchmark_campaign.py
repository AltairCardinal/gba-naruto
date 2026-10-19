#!/usr/bin/env python3
"""Frozen campaign, per-request billing, and scheduler contracts."""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from tools.reverse_benchmark.billing import calculate_attempt_billing
from tools.reverse_benchmark.campaign import (
    ATTEMPT_SCHEMA,
    PLAN_SCHEMA,
    _retryable,
    create_smoke_plan,
    execute_smoke_plan,
    validate_smoke_plan,
)
from tools.reverse_benchmark.compatibility import (
    run_minimax_compatibility,
    run_openai_native_compatibility,
    run_openai_proxy_compatibility,
)
from tools.reverse_benchmark.credentials import LoadedCredential
from tools.reverse_benchmark.matrix import benchmark_matrix
from tools.reverse_benchmark.packets import (
    PACKET_CONTRACT_SCHEMA,
    SMOKE_CHALLENGE_IDS,
)
from tools.reverse_benchmark.pricing import NormalizedUsage
from tools.reverse_benchmark.report import (
    render_smoke_markdown,
    summarize_smoke_campaign,
)
from tools.reverse_benchmark.runner import (
    CODEX_NATIVE_TRANSPORT_PROFILE,
    benchmark_provider_contract,
    provider_contract_sha256,
)


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_IDS = {"openai": "a" * 64, "minimax": "b" * 64}
REDUCED_CONFIGURATION_IDS = (
    "openai-gpt-5.6-luna-max",
    "openai-gpt-5.6-terra-max",
    "openai-gpt-5.6-sol-medium",
    "openai-gpt-5.6-sol-ultra",
)


def _test_environment(configuration):
    if configuration.provider == "minimax":
        return {"BENCH_MINIMAX_API_KEY": "test-only-minimax-key"}
    return None


def _compatibility_receipts(output_root: Path):
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

    minimax = run_minimax_compatibility(
        repo_root=output_root,
        output_root=output_root / "minimax-compatibility",
        credential=LoadedCredential(value="fixture-secret", source="fixture"),
        static_preflight=static,
        attempt_executor=fake_attempt,
        created_at="2026-08-16T00:00:00+00:00",
    )
    openai = run_openai_proxy_compatibility(
        repo_root=output_root,
        output_root=output_root / "openai-compatibility",
        static_preflight=static,
        attempt_executor=fake_attempt,
        created_at="2026-08-16T00:00:00+00:00",
        allow_plaintext_auth_relay=True,
    )
    return {"openai": openai, "minimax": minimax}


def _receipt_ids(receipts):
    return {
        provider: receipt["receipt_id"]
        for provider, receipt in receipts.items()
    }


class SmokePlanTests(unittest.TestCase):
    def test_native_plan_without_ids_defaults_to_exact_reduced_matrix(self):
        plan = create_smoke_plan(
            20260820,
            compatibility_receipt_ids={"openai": "a" * 64},
            openai_transport_profile=CODEX_NATIVE_TRANSPORT_PROFILE,
            created_at="2026-08-19T00:00:00+00:00",
        )

        self.assertEqual(12, plan["logical_case_count"])
        self.assertEqual(
            set(REDUCED_CONFIGURATION_IDS),
            {item["id"] for item in plan["configurations"]},
        )

    def test_native_selected_plan_freezes_transport_and_disjoint_run_ids(self):
        proxy = create_smoke_plan(
            20260819,
            compatibility_receipt_ids={"openai": "a" * 64},
            configuration_ids=REDUCED_CONFIGURATION_IDS,
            created_at="2026-08-19T00:00:00+00:00",
        )
        native = create_smoke_plan(
            20260819,
            compatibility_receipt_ids={"openai": "b" * 64},
            configuration_ids=REDUCED_CONFIGURATION_IDS,
            openai_transport_profile=CODEX_NATIVE_TRANSPORT_PROFILE,
            created_at="2026-08-19T00:00:00+00:00",
        )

        self.assertEqual(
            {CODEX_NATIVE_TRANSPORT_PROFILE},
            {item["transport_profile"] for item in native["configurations"]},
        )
        self.assertEqual(
            CODEX_NATIVE_TRANSPORT_PROFILE,
            native["provider_contracts"]["openai"]["transport_profile"],
        )
        proxy_run_ids = {
            case[key]
            for case in proxy["cases"]
            for key in ("primary_run_id", "retry_run_id")
        }
        native_run_ids = {
            case[key]
            for case in native["cases"]
            for key in ("primary_run_id", "retry_run_id")
        }
        self.assertTrue(proxy_run_ids.isdisjoint(native_run_ids))
        validate_smoke_plan(proxy)
        validate_smoke_plan(native)
    def test_selected_openai_matrix_freezes_exact_twelve_cell_cross_product(self):
        plan = create_smoke_plan(
            20260819,
            compatibility_receipt_ids={"openai": "a" * 64},
            configuration_ids=REDUCED_CONFIGURATION_IDS,
            created_at="2026-08-19T00:00:00+00:00",
        )

        self.assertEqual(12, plan["logical_case_count"])
        self.assertEqual(
            set(REDUCED_CONFIGURATION_IDS),
            {item["id"] for item in plan["configurations"]},
        )
        self.assertEqual({"openai"}, set(plan["provider_contracts"]))
        self.assertEqual(
            {"openai": "a" * 64}, plan["compatibility_receipt_ids"]
        )
        self.assertEqual(
            {
                (configuration_id, challenge_id)
                for configuration_id in REDUCED_CONFIGURATION_IDS
                for challenge_id in SMOKE_CHALLENGE_IDS
            },
            {
                (case["configuration_id"], case["challenge_id"])
                for case in plan["cases"]
            },
        )
        validate_smoke_plan(plan)

        changed = copy.deepcopy(plan)
        changed["configurations"].pop()
        with self.assertRaises(ValueError):
            validate_smoke_plan(changed)

    def test_reduced_plan_report_contains_only_selected_configurations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipts = _compatibility_receipts(root / "gates")
            plan = create_smoke_plan(
                20260819,
                compatibility_receipt_ids={
                    "openai": receipts["openai"]["receipt_id"]
                },
                configuration_ids=REDUCED_CONFIGURATION_IDS,
                created_at="2026-08-19T00:00:00+00:00",
            )
            summary = summarize_smoke_campaign(
                plan,
                root / "empty-runs",
                compatibility_receipts={"openai": receipts["openai"]},
                expected_codex_sha256="b" * 64,
            )
            markdown = render_smoke_markdown(summary)

        self.assertEqual(
            set(REDUCED_CONFIGURATION_IDS),
            set(summary["aggregates"]["by_configuration"]),
        )
        self.assertIn("有效逻辑格：0/12", markdown)
        self.assertNotIn("MiniMax 兼容性回执", markdown)
        for configuration_id in REDUCED_CONFIGURATION_IDS:
            self.assertIn(configuration_id, markdown)

        native_summary = copy.deepcopy(summary)
        for row in native_summary["aggregates"]["by_configuration"].values():
            row["configuration"]["transport_profile"] = (
                CODEX_NATIVE_TRANSPORT_PROFILE
            )
        native_markdown = render_smoke_markdown(native_summary)
        self.assertIn("本机 Codex 原生兼容性回执", native_markdown)
        self.assertNotIn("OpenAI 代理兼容性回执", native_markdown)

    def test_seeded_plan_freezes_exact_fifty_seven_cell_cross_product(self):
        created_at = "2026-08-16T00:00:00+00:00"
        first = create_smoke_plan(
            20260816,
            compatibility_receipt_ids=RECEIPT_IDS,
            created_at=created_at,
        )
        second = create_smoke_plan(
            20260816,
            compatibility_receipt_ids=RECEIPT_IDS,
            created_at=created_at,
        )
        different = create_smoke_plan(
            20260817,
            compatibility_receipt_ids=RECEIPT_IDS,
            created_at=created_at,
        )

        self.assertEqual(first, second)
        self.assertEqual("reverse-model-benchmark-smoke-plan-v5", PLAN_SCHEMA)
        self.assertEqual("reverse-model-benchmark-attempt-v5", ATTEMPT_SCHEMA)
        self.assertEqual(PLAN_SCHEMA, first["schema"])
        self.assertEqual(
            PACKET_CONTRACT_SCHEMA, first["packet_contract_schema"]
        )
        self.assertEqual(57, first["logical_case_count"])
        self.assertEqual(57, len(first["cases"]))
        self.assertEqual(RECEIPT_IDS, first["compatibility_receipt_ids"])
        self.assertEqual(
            {
                provider: benchmark_provider_contract(
                    next(
                        configuration
                        for configuration in benchmark_matrix()
                        if configuration.provider == provider
                    )
                )
                for provider in ("openai", "minimax")
            },
            first["provider_contracts"],
        )
        expected_pairs = {
            (configuration.id, challenge_id)
            for configuration in benchmark_matrix()
            for challenge_id in SMOKE_CHALLENGE_IDS
        }
        actual_pairs = {
            (case["configuration_id"], case["challenge_id"])
            for case in first["cases"]
        }
        self.assertEqual(expected_pairs, actual_pairs)
        self.assertNotEqual(
            [case["case_id"] for case in first["cases"]],
            [case["case_id"] for case in different["cases"]],
        )
        for challenge_id in SMOKE_CHALLENGE_IDS:
            self.assertEqual(
                1,
                len(
                    {
                        case["seed"]
                        for case in first["cases"]
                        if case["challenge_id"] == challenge_id
                    }
                ),
            )
        run_ids = {
            case[key]
            for case in first["cases"]
            for key in ("primary_run_id", "retry_run_id")
        }
        self.assertEqual(114, len(run_ids))
        self.assertTrue(all(len(run_id) == 32 for run_id in run_ids))
        configuration_by_id = {
            configuration.id: configuration for configuration in benchmark_matrix()
        }
        for case in first["cases"]:
            self.assertEqual(
                provider_contract_sha256(
                    configuration_by_id[case["configuration_id"]]
                ),
                case["provider_contract_sha256"],
            )
        validate_smoke_plan(first)

    def test_plan_validator_rejects_missing_duplicate_and_tampered_cells(self):
        plan = create_smoke_plan(
            20260816,
            compatibility_receipt_ids=RECEIPT_IDS,
            created_at="2026-08-16T00:00:00+00:00",
        )
        for mutation in (
            "missing",
            "duplicate",
            "hash",
            "provider-contract",
            "receipt-id",
        ):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(plan)
                if mutation == "missing":
                    changed["cases"].pop()
                elif mutation == "duplicate":
                    changed["cases"][-1] = copy.deepcopy(changed["cases"][0])
                else:
                    if mutation == "hash":
                        changed["plan_id"] = "0" * 64
                    elif mutation == "provider-contract":
                        changed["provider_contracts"]["openai"]["base_url"] = (
                            "https://tampered.invalid/v1"
                        )
                    else:
                        changed["compatibility_receipt_ids"]["openai"] = "f" * 64
                with self.assertRaises(ValueError):
                    validate_smoke_plan(changed)


class AttemptBillingTests(unittest.TestCase):
    def test_cost_is_tiered_per_request_not_on_aggregate_usage(self):
        sol = next(item for item in benchmark_matrix() if item.id.endswith("sol-low"))
        m3 = next(item for item in benchmark_matrix() if item.model == "MiniMax-M3")

        sol_billing = calculate_attempt_billing(
            sol,
            [
                NormalizedUsage(uncached_input=200_000),
                NormalizedUsage(uncached_input=200_000),
            ],
            usage_granularities=["request", "request"],
            usage_complete=True,
            usage_scope="all-agent-threads",
        )
        m3_billing = calculate_attempt_billing(
            m3,
            [
                NormalizedUsage(uncached_input=300_000),
                NormalizedUsage(uncached_input=300_000),
            ],
            usage_granularities=["request", "request"],
            usage_complete=True,
            usage_scope="all-agent-threads",
        )

        self.assertEqual("2", sol_billing["totals"]["api_cost_usd"])
        self.assertEqual("50", sol_billing["totals"]["codex_credits_estimate"])
        self.assertEqual("1.26", m3_billing["totals"]["api_cost_cny"])
        self.assertEqual(2, len(sol_billing["requests"]))

    def test_long_context_boundaries_are_strictly_greater_than_threshold(self):
        sol = next(item for item in benchmark_matrix() if item.id.endswith("sol-low"))
        standard = calculate_attempt_billing(
            sol,
            [NormalizedUsage(uncached_input=272_000)],
            usage_granularities=["request"],
            usage_complete=True,
            usage_scope="all-agent-threads",
        )
        long_context = calculate_attempt_billing(
            sol,
            [NormalizedUsage(uncached_input=272_001)],
            usage_granularities=["request"],
            usage_complete=True,
            usage_scope="all-agent-threads",
        )

        self.assertEqual("standard-up-to-272k", standard["requests"][0]["tier"])
        self.assertEqual("long-context-over-272k", long_context["requests"][0]["tier"])

    def test_turn_aggregate_over_tier_threshold_preserves_only_exact_costs(self):
        sol = next(item for item in benchmark_matrix() if item.id.endswith("sol-low"))
        m3 = next(item for item in benchmark_matrix() if item.model == "MiniMax-M3")

        sol_billing = calculate_attempt_billing(
            sol,
            [NormalizedUsage(uncached_input=300_000, output=1_000)],
            usage_granularities=["turn-aggregate"],
            usage_complete=True,
            usage_scope="all-agent-threads",
        )
        m3_billing = calculate_attempt_billing(
            m3,
            [NormalizedUsage(uncached_input=600_000, output=2_000)],
            usage_granularities=["turn-aggregate"],
            usage_complete=True,
            usage_scope="all-agent-threads",
        )

        self.assertEqual("partial-known", sol_billing["status"])
        self.assertIsNone(sol_billing["totals"]["api_cost_usd"])
        self.assertEqual("38.25", sol_billing["totals"]["codex_credits_estimate"])
        self.assertIn("request boundaries", sol_billing["unknown_reason"])
        self.assertEqual("partial-known", m3_billing["status"])
        self.assertIsNone(m3_billing["totals"]["api_cost_cny"])
        self.assertEqual(
            600_000,
            m3_billing["totals"]["minimax_token_plan_input_tokens"],
        )
        self.assertEqual(
            2_000,
            m3_billing["totals"]["minimax_token_plan_output_tokens"],
        )
        self.assertIn("request boundaries", m3_billing["unknown_reason"])

    def test_root_only_ultra_usage_is_unknown_not_underpriced(self):
        ultra = next(
            item
            for item in benchmark_matrix()
            if item.model == "gpt-5.6-sol" and item.effort == "ultra"
        )

        billing = calculate_attempt_billing(
            ultra,
            [NormalizedUsage(uncached_input=10, output=1)],
            usage_granularities=["request"],
            usage_complete=True,
            usage_scope="root-thread-only",
        )

        self.assertEqual("unknown", billing["status"])
        self.assertIsNone(billing["totals"]["api_cost_usd"])
        self.assertIn("subagent", billing["unknown_reason"])


class SmokeSchedulerTests(unittest.TestCase):
    def test_campaign_requires_exact_plan_receipts_and_plaintext_authorization_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipts = _compatibility_receipts(root / "gates")
            plan = create_smoke_plan(
                20260816,
                compatibility_receipt_ids=_receipt_ids(receipts),
                created_at="2026-08-16T00:00:00+00:00",
            )
            runs = root / "runs"
            with self.assertRaisesRegex(ValueError, "plaintext auth relay"):
                execute_smoke_plan(
                    plan,
                    repo_root=ROOT,
                    output_root=runs,
                    compatibility_receipts=receipts,
                    expected_codex_sha256="b" * 64,
                    attempt_runner=lambda **_kwargs: self.fail("must not run"),
                    environment_for_configuration=_test_environment,
                )
            self.assertFalse(runs.exists())

            with self.assertRaisesRegex(ValueError, "match selected providers"):
                execute_smoke_plan(
                    plan,
                    repo_root=ROOT,
                    output_root=runs,
                    compatibility_receipts={"minimax": receipts["minimax"]},
                    allow_plaintext_auth_relay=True,
                    expected_codex_sha256="b" * 64,
                    attempt_runner=lambda **_kwargs: self.fail("must not run"),
                    environment_for_configuration=_test_environment,
                )
            self.assertFalse(runs.exists())

    def test_authentication_and_empty_ultra_transport_failures_get_one_retry(self):
        authentication_failure = {
            "status": "infrastructure-failed",
            "guard": {"reason": "child-exit"},
            "configuration": {"system_mode": "single-agent"},
            "telemetry": {
                "usage_complete": False,
                "requests": [],
                "errors": ["401 Unauthorized: invalid_api_key"],
            },
        }
        ultra_transport_failure = {
            "status": "infrastructure-failed",
            "guard": {"reason": "child-exit"},
            "configuration": {"system_mode": "multi-agent"},
            "telemetry": {
                "usage_complete": False,
                "requests": [],
                "errors": ["Ultra all-agent closure marker is missing"],
            },
        }
        generic_failure = {
            **authentication_failure,
            "telemetry": {
                "usage_complete": False,
                "requests": [],
                "errors": ["process exited with 1"],
            },
        }

        self.assertTrue(_retryable(authentication_failure))
        self.assertTrue(_retryable(ultra_transport_failure))
        self.assertFalse(_retryable(generic_failure))
        credential_failure = copy.deepcopy(authentication_failure)
        credential_failure["security"] = {
            "credential_material_detected": True,
            "surfaces": ["capture-stream"],
        }
        self.assertFalse(_retryable(credential_failure))

    def test_scheduler_aborts_campaign_on_credential_material_detection(self):
        calls: list[str] = []

        def fake_runner(**kwargs):
            calls.append(kwargs["run_id"])
            manifest = {
                "schema": ATTEMPT_SCHEMA,
                "run_id": kwargs["run_id"],
                "status": "infrastructure-failed",
                "configuration": asdict(kwargs["configuration"]),
                "challenge_id": kwargs["challenge_id"],
                "seed": kwargs["seed"],
                "plan_binding": kwargs["plan_binding"],
                "compatibility_receipt_id": kwargs[
                    "compatibility_receipt_id"
                ],
                "provider_contract": benchmark_provider_contract(
                    kwargs["configuration"]
                ),
                "security": {
                    "credential_material_detected": True,
                    "surfaces": ["capture-stream"],
                },
                "guard": {"reason": "child-exit"},
            }
            run_dir = Path(kwargs["output_root"]) / kwargs["run_id"]
            run_dir.mkdir()
            (run_dir / "manifest.json").write_text(json.dumps(manifest))
            return manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipts = _compatibility_receipts(root / "gates")
            plan = create_smoke_plan(
                20260816,
                compatibility_receipt_ids=_receipt_ids(receipts),
                created_at="2026-08-16T00:00:00+00:00",
            )
            with self.assertRaisesRegex(RuntimeError, "credential material"):
                execute_smoke_plan(
                    plan,
                    repo_root=ROOT,
                    output_root=root / "runs",
                    compatibility_receipts=receipts,
                    allow_plaintext_auth_relay=True,
                    expected_codex_sha256="b" * 64,
                    attempt_runner=fake_runner,
                    environment_for_configuration=_test_environment,
                )

        self.assertEqual(1, len(calls))

    def test_scheduler_retries_only_retryable_infrastructure_once_at_tail(self):
        calls: list[str] = []
        receipt_bindings: list[tuple[str, str]] = []
        plan = None
        first_case = None
        second_case = None
        third_case = None

        def fake_runner(**kwargs):
            run_id = kwargs["run_id"]
            calls.append(run_id)
            receipt_bindings.append(
                (
                    kwargs["configuration"].provider,
                    kwargs["compatibility_receipt_id"],
                )
            )
            if run_id == first_case["primary_run_id"]:
                status, reason = "infrastructure-failed", "lock-busy"
            elif run_id == second_case["primary_run_id"]:
                status, reason = "verified-failed", "completed"
            elif run_id == third_case["primary_run_id"]:
                status, reason = "infrastructure-failed", "wall-timeout"
            else:
                status, reason = "verified-passed", "completed"
            manifest = {
                "schema": ATTEMPT_SCHEMA,
                "run_id": run_id,
                "status": status,
                "configuration": asdict(kwargs["configuration"]),
                "challenge_id": kwargs["challenge_id"],
                "seed": kwargs["seed"],
                "plan_binding": kwargs["plan_binding"],
                "compatibility_receipt_id": kwargs[
                    "compatibility_receipt_id"
                ],
                "provider_contract": benchmark_provider_contract(
                    kwargs["configuration"]
                ),
                "security": {
                    "credential_material_detected": False,
                    "surfaces": [],
                },
                "guard": {"reason": reason},
            }
            if status in {"verified-passed", "verified-failed"}:
                manifest["verification"] = {
                    "score": 100 if status == "verified-passed" else 0,
                    "passed": status == "verified-passed",
                }
            run_dir = Path(kwargs["output_root"]) / run_id
            run_dir.mkdir()
            (run_dir / "manifest.json").write_text(json.dumps(manifest))
            return manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipts = _compatibility_receipts(root / "gates")
            plan = create_smoke_plan(
                20260816,
                compatibility_receipt_ids=_receipt_ids(receipts),
                created_at="2026-08-16T00:00:00+00:00",
            )
            first_case = plan["cases"][0]
            second_case = plan["cases"][1]
            third_case = plan["cases"][2]
            result = execute_smoke_plan(
                plan,
                repo_root=ROOT,
                output_root=root / "runs",
                compatibility_receipts=receipts,
                allow_plaintext_auth_relay=True,
                expected_codex_sha256="b" * 64,
                attempt_runner=fake_runner,
                environment_for_configuration=_test_environment,
            )

        self.assertEqual(58, len(calls))
        self.assertEqual(first_case["retry_run_id"], calls[-1])
        self.assertNotIn(second_case["retry_run_id"], calls)
        self.assertNotIn(third_case["retry_run_id"], calls)
        self.assertEqual(57, result["logical_cases_completed"])
        self.assertEqual(1, result["retry_count"])
        self.assertEqual(_receipt_ids(receipts), result["compatibility_receipt_ids"])
        primary_bindings = receipt_bindings[:57]
        self.assertEqual(51, sum(provider == "openai" for provider, _ in primary_bindings))
        self.assertEqual(6, sum(provider == "minimax" for provider, _ in primary_bindings))
        self.assertTrue(
            all(
                receipt_id == receipts[provider]["receipt_id"]
                for provider, receipt_id in primary_bindings
            )
        )

    def test_resume_skips_exact_binding_and_rejects_run_id_collision(self):
        calls: list[str] = []

        def fake_runner(**kwargs):
            calls.append(kwargs["run_id"])
            manifest = {
                "schema": ATTEMPT_SCHEMA,
                "run_id": kwargs["run_id"],
                "status": "verified-passed",
                "configuration": asdict(kwargs["configuration"]),
                "challenge_id": kwargs["challenge_id"],
                "seed": kwargs["seed"],
                "plan_binding": kwargs["plan_binding"],
                "compatibility_receipt_id": kwargs[
                    "compatibility_receipt_id"
                ],
                "provider_contract": benchmark_provider_contract(
                    kwargs["configuration"]
                ),
                "security": {
                    "credential_material_detected": False,
                    "surfaces": [],
                },
                "guard": {"reason": "completed"},
                "verification": {"score": 100, "passed": True},
            }
            run_dir = Path(kwargs["output_root"]) / kwargs["run_id"]
            run_dir.mkdir()
            (run_dir / "manifest.json").write_text(json.dumps(manifest))
            return manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipts = _compatibility_receipts(root / "gates")
            plan = create_smoke_plan(
                20260816,
                compatibility_receipt_ids=_receipt_ids(receipts),
                created_at="2026-08-16T00:00:00+00:00",
            )
            output_root = root / "runs"
            execute_smoke_plan(
                plan,
                repo_root=ROOT,
                output_root=output_root,
                compatibility_receipts=receipts,
                allow_plaintext_auth_relay=True,
                expected_codex_sha256="b" * 64,
                attempt_runner=fake_runner,
                environment_for_configuration=_test_environment,
            )
            self.assertEqual(57, len(calls))
            calls.clear()
            resumed = execute_smoke_plan(
                plan,
                repo_root=ROOT,
                output_root=output_root,
                compatibility_receipts=receipts,
                allow_plaintext_auth_relay=True,
                expected_codex_sha256="b" * 64,
                attempt_runner=fake_runner,
                environment_for_configuration=_test_environment,
            )
            self.assertEqual([], calls)
            self.assertEqual(0, resumed["physical_attempts_started"])

            first = plan["cases"][0]
            manifest_path = output_root / first["primary_run_id"] / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["plan_binding"]["case_id"] = "tampered"
            manifest_path.write_text(json.dumps(manifest))

            with self.assertRaisesRegex(ValueError, "binding mismatch"):
                execute_smoke_plan(
                    plan,
                    repo_root=ROOT,
                    output_root=output_root,
                    compatibility_receipts=receipts,
                    allow_plaintext_auth_relay=True,
                    expected_codex_sha256="b" * 64,
                    attempt_runner=fake_runner,
                    environment_for_configuration=_test_environment,
                )

    def test_resume_preflights_late_binding_conflict_before_filling_early_gap(self):
        calls: list[str] = []

        def fake_runner(**kwargs):
            calls.append(kwargs["run_id"])
            manifest = {
                "schema": ATTEMPT_SCHEMA,
                "run_id": kwargs["run_id"],
                "status": "verified-passed",
                "configuration": asdict(kwargs["configuration"]),
                "challenge_id": kwargs["challenge_id"],
                "seed": kwargs["seed"],
                "plan_binding": kwargs["plan_binding"],
                "compatibility_receipt_id": kwargs["compatibility_receipt_id"],
                "provider_contract": benchmark_provider_contract(
                    kwargs["configuration"]
                ),
                "security": {
                    "credential_material_detected": False,
                    "surfaces": [],
                },
                "guard": {"reason": "completed"},
                "verification": {"score": 100, "passed": True},
            }
            run_dir = Path(kwargs["output_root"]) / kwargs["run_id"]
            run_dir.mkdir()
            (run_dir / "manifest.json").write_text(json.dumps(manifest))
            return manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipts = _compatibility_receipts(root / "gates")
            plan = create_smoke_plan(
                20260816,
                compatibility_receipt_ids=_receipt_ids(receipts),
                created_at="2026-08-16T00:00:00+00:00",
            )
            runs = root / "runs"
            execute_smoke_plan(
                plan,
                repo_root=ROOT,
                output_root=runs,
                compatibility_receipts=receipts,
                allow_plaintext_auth_relay=True,
                expected_codex_sha256="b" * 64,
                attempt_runner=fake_runner,
                environment_for_configuration=_test_environment,
            )
            early = plan["cases"][0]
            late = plan["cases"][-1]
            early_dir = runs / early["primary_run_id"]
            shutil.rmtree(early_dir)
            late_path = runs / late["primary_run_id"] / "manifest.json"
            late_manifest = json.loads(late_path.read_text())
            late_provider = late_manifest["configuration"]["provider"]
            other_provider = "minimax" if late_provider == "openai" else "openai"
            late_manifest["compatibility_receipt_id"] = receipts[other_provider][
                "receipt_id"
            ]
            late_path.write_text(json.dumps(late_manifest))
            calls.clear()

            with self.assertRaisesRegex(ValueError, "binding mismatch"):
                execute_smoke_plan(
                    plan,
                    repo_root=ROOT,
                    output_root=runs,
                    compatibility_receipts=receipts,
                    allow_plaintext_auth_relay=True,
                    expected_codex_sha256="b" * 64,
                    attempt_runner=fake_runner,
                    environment_for_configuration=_test_environment,
                )

            self.assertEqual([], calls)
            self.assertFalse(early_dir.exists())


class SmokeReportTests(unittest.TestCase):
    def test_summary_uses_effective_retry_quality_but_bills_every_attempt(self):
        with tempfile.TemporaryDirectory() as gate_directory:
            receipts = _compatibility_receipts(Path(gate_directory))
        receipt_ids = _receipt_ids(receipts)
        plan = create_smoke_plan(
            20260816,
            compatibility_receipt_ids=receipt_ids,
            created_at="2026-08-16T00:00:00+00:00",
        )
        configuration_by_id = {
            configuration.id: configuration for configuration in benchmark_matrix()
        }
        expected_usd = 0
        expected_cny = 0
        expected_minimax_input = 0
        expected_minimax_output = 0
        first_case = plan["cases"][0]

        def manifest_for(case, run_id, status, score):
            configuration = configuration_by_id[case["configuration_id"]]
            if configuration.provider == "openai":
                totals = {
                    "api_cost_usd": "1",
                    "api_cost_cny": None,
                    "codex_credits_estimate": "10",
                    "minimax_token_plan_input_tokens": None,
                    "minimax_token_plan_output_tokens": None,
                }
            else:
                totals = {
                    "api_cost_usd": None,
                    "api_cost_cny": "2",
                    "codex_credits_estimate": None,
                    "minimax_token_plan_input_tokens": 11,
                    "minimax_token_plan_output_tokens": 3,
                }
            attempt_index = 1 if run_id == case["primary_run_id"] else 2
            return {
                "schema": ATTEMPT_SCHEMA,
                "run_id": run_id,
                "status": status,
                "configuration": asdict(configuration),
                "challenge_id": case["challenge_id"],
                "seed": case["seed"],
                "plan_binding": {
                    "plan_id": plan["plan_id"],
                    "case_id": case["case_id"],
                    "sequence": case["sequence"],
                    "attempt_index": attempt_index,
                    "provider_contract_sha256": case[
                        "provider_contract_sha256"
                    ],
                    "retry_of": (
                        None if attempt_index == 1 else case["primary_run_id"]
                    ),
                },
                "compatibility_receipt_id": receipt_ids[configuration.provider],
                "provider_contract": benchmark_provider_contract(configuration),
                "security": {
                    "credential_material_detected": False,
                    "surfaces": [],
                },
                "guard": {"reason": "completed"},
                "verification": {"score": score, "passed": score == 100},
                "telemetry": {"wall_time_ms": 1000},
                "billing": {"status": "complete", "totals": totals},
            }

        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            for case in plan["cases"]:
                configuration = configuration_by_id[case["configuration_id"]]
                manifest = manifest_for(
                    case,
                    case["primary_run_id"],
                    "verified-passed",
                    100,
                )
                run_dir = runs / case["primary_run_id"]
                run_dir.mkdir()
                (run_dir / "manifest.json").write_text(json.dumps(manifest))
                if configuration.provider == "openai":
                    expected_usd += 1
                else:
                    expected_cny += 2
                    expected_minimax_input += 11
                    expected_minimax_output += 3

            primary = runs / first_case["primary_run_id"] / "manifest.json"
            failed_primary = json.loads(primary.read_text())
            failed_primary["status"] = "infrastructure-failed"
            failed_primary["guard"] = {"reason": "lock-busy"}
            primary.write_text(json.dumps(failed_primary))
            retry = manifest_for(
                first_case,
                first_case["retry_run_id"],
                "verified-passed",
                100,
            )
            retry_dir = runs / first_case["retry_run_id"]
            retry_dir.mkdir()
            (retry_dir / "manifest.json").write_text(json.dumps(retry))
            first_configuration = configuration_by_id[first_case["configuration_id"]]
            if first_configuration.provider == "openai":
                expected_usd += 1
            else:
                expected_cny += 2
                expected_minimax_input += 11
                expected_minimax_output += 3

            summary = summarize_smoke_campaign(
                plan,
                runs,
                compatibility_receipts=receipts,
                expected_codex_sha256="b" * 64,
            )
            markdown = render_smoke_markdown(summary)

            unavailable_retry = copy.deepcopy(retry)
            unavailable_retry["status"] = "infrastructure-failed"
            unavailable_retry["guard"] = {"reason": "child-exit"}
            retry_manifest_path = retry_dir / "manifest.json"
            retry_manifest_path.write_text(json.dumps(unavailable_retry))
            unavailable_summary = summarize_smoke_campaign(
                plan,
                runs,
                compatibility_receipts=receipts,
                expected_codex_sha256="b" * 64,
            )
            unavailable_case = next(
                item
                for item in unavailable_summary["logical_cases"]
                if item["case_id"] == first_case["case_id"]
            )
            self.assertEqual("infrastructure-failed", unavailable_case["status"])
            self.assertIsNone(unavailable_case["score"])
            self.assertIsNone(unavailable_case["effective_wall_time_ms"])
            self.assertEqual("2000", unavailable_case["physical_wall_time_ms"])
            unavailable_row = unavailable_summary["aggregates"][
                "by_configuration"
            ][first_case["configuration_id"]]
            self.assertIsNone(
                unavailable_row["challenge_effective_wall_time_ms"][
                    first_case["challenge_id"]
                ]
            )
            retry_manifest_path.write_text(json.dumps(retry))

            failed_primary["guard"] = {"reason": "child-exit"}
            failed_primary["telemetry"] = {
                "wall_time_ms": 1000,
                "usage_complete": False,
                "requests": [],
                "errors": ["401 Unauthorized: invalid_api_key"],
            }
            primary.write_text(json.dumps(failed_primary))
            authentication_retry_summary = summarize_smoke_campaign(
                plan,
                runs,
                compatibility_receipts=receipts,
                expected_codex_sha256="b" * 64,
            )
            self.assertEqual(
                first_case["retry_run_id"],
                authentication_retry_summary["logical_cases"][0][
                    "effective_run_id"
                ],
            )
            failed_primary["guard"] = {"reason": "lock-busy"}
            failed_primary["telemetry"] = {"wall_time_ms": 1000}
            primary.write_text(json.dumps(failed_primary))

            partial_case = next(
                case
                for case in plan["cases"]
                if configuration_by_id[case["configuration_id"]].provider == "openai"
                and case["configuration_id"] != first_case["configuration_id"]
            )
            partial_path = (
                runs / partial_case["primary_run_id"] / "manifest.json"
            )
            partial_manifest = json.loads(partial_path.read_text())
            partial_manifest["billing"] = {
                "status": "partial-known",
                "unknown_reason": "request boundaries unavailable",
                "totals": {
                    "api_cost_usd": None,
                    "api_cost_cny": None,
                    "codex_credits_estimate": "10",
                    "minimax_token_plan_input_tokens": None,
                    "minimax_token_plan_output_tokens": None,
                },
            }
            partial_path.write_text(json.dumps(partial_manifest))
            boundary_summary = summarize_smoke_campaign(
                plan,
                runs,
                compatibility_receipts=receipts,
                expected_codex_sha256="b" * 64,
            )
            boundary_row = boundary_summary["aggregates"]["by_configuration"][
                partial_case["configuration_id"]
            ]
            self.assertEqual("partial-known", boundary_row["api_cost_usd_status"])
            self.assertEqual(
                ["request boundaries unavailable"],
                boundary_row["billing_unknown_reasons"],
            )
            self.assertEqual(
                ["request boundaries unavailable"],
                boundary_summary["aggregates"]["campaign"][
                    "billing_unknown_reasons"
                ],
            )
            self.assertEqual(
                "complete", boundary_row["codex_credits_estimate_status"]
            )
            self.assertEqual("30", boundary_row["codex_credits_estimate"])
            self.assertEqual(
                "partial-known",
                boundary_summary["aggregates"]["campaign"][
                    "api_cost_usd_status"
                ],
            )
            self.assertEqual(
                "complete",
                boundary_summary["aggregates"]["campaign"][
                    "codex_credits_estimate_status"
                ],
            )
            self.assertIn(
                "request boundaries unavailable",
                render_smoke_markdown(boundary_summary),
            )

            partial_manifest["billing"] = {
                "status": "unknown",
                "totals": {
                    "api_cost_usd": None,
                    "api_cost_cny": None,
                    "codex_credits_estimate": None,
                    "minimax_token_plan_input_tokens": None,
                    "minimax_token_plan_output_tokens": None,
                },
            }
            partial_manifest["telemetry"] = {"wall_time_ms": None}
            partial_path.write_text(json.dumps(partial_manifest))
            partial_summary = summarize_smoke_campaign(
                plan,
                runs,
                compatibility_receipts=receipts,
                expected_codex_sha256="b" * 64,
            )
            partial_row = partial_summary["aggregates"]["by_configuration"][
                partial_case["configuration_id"]
            ]
            self.assertEqual("partial-known", partial_row["billing_status"])
            self.assertEqual(
                "partial-known", partial_row["physical_wall_time_status"]
            )
            self.assertEqual(
                "partial-known", partial_row["effective_wall_time_status"]
            )
            self.assertEqual(
                "partial-known",
                partial_summary["aggregates"]["processing_total"][
                    "billing_status"
                ],
            )
            self.assertIn("部分已知", render_smoke_markdown(partial_summary))

            for case in plan["cases"]:
                if case["configuration_id"] != partial_case["configuration_id"]:
                    continue
                for run_id in (case["primary_run_id"], case["retry_run_id"]):
                    path = runs / run_id / "manifest.json"
                    if not path.is_file():
                        continue
                    manifest = json.loads(path.read_text())
                    manifest["billing"] = partial_manifest["billing"]
                    path.write_text(json.dumps(manifest))
            unknown_summary = summarize_smoke_campaign(
                plan,
                runs,
                compatibility_receipts=receipts,
                expected_codex_sha256="b" * 64,
            )
            unknown_row = unknown_summary["aggregates"]["by_configuration"][
                partial_case["configuration_id"]
            ]
            self.assertEqual("unknown", unknown_row["billing_status"])

            for case in plan["cases"]:
                for run_id in (case["primary_run_id"], case["retry_run_id"]):
                    path = runs / run_id / "manifest.json"
                    if not path.is_file():
                        continue
                    manifest = json.loads(path.read_text())
                    manifest["telemetry"] = {"wall_time_ms": None}
                    path.write_text(json.dumps(manifest))
            unknown_wall_summary = summarize_smoke_campaign(
                plan,
                runs,
                compatibility_receipts=receipts,
                expected_codex_sha256="b" * 64,
            )
            self.assertEqual(
                "unknown",
                unknown_wall_summary["aggregates"]["campaign"][
                    "physical_wall_time_status"
                ],
            )
            self.assertEqual(
                "partial-known",
                unknown_wall_summary["aggregates"]["processing_total"][
                    "physical_wall_time_status"
                ],
            )
            self.assertIn(
                "总处理开销：物理耗时 部分已知：",
                render_smoke_markdown(unknown_wall_summary),
            )
            self.assertIn(
                "Campaign 开销：有效 attempt 耗时 未知",
                render_smoke_markdown(unknown_wall_summary),
            )

            tampered_path = runs / first_case["retry_run_id"] / "manifest.json"
            untampered = json.loads(tampered_path.read_text())
            invalid_score = copy.deepcopy(untampered)
            invalid_score["verification"]["score"] = 101
            tampered_path.write_text(json.dumps(invalid_score))
            with self.assertRaisesRegex(ValueError, "verification"):
                summarize_smoke_campaign(
                    plan,
                    runs,
                    compatibility_receipts=receipts,
                    expected_codex_sha256="b" * 64,
                )

            invalid_passed = copy.deepcopy(untampered)
            invalid_passed["verification"]["passed"] = False
            tampered_path.write_text(json.dumps(invalid_passed))
            with self.assertRaisesRegex(ValueError, "verification"):
                summarize_smoke_campaign(
                    plan,
                    runs,
                    compatibility_receipts=receipts,
                    expected_codex_sha256="b" * 64,
                )

            tampered_path.write_text(json.dumps(untampered))
            tampered = json.loads(tampered_path.read_text())
            tampered["plan_binding"]["plan_id"] = "0" * 64
            tampered_path.write_text(json.dumps(tampered))
            with self.assertRaisesRegex(ValueError, "binding"):
                summarize_smoke_campaign(
                    plan,
                    runs,
                    compatibility_receipts=receipts,
                    expected_codex_sha256="b" * 64,
                )

        self.assertEqual(58, summary["completeness"]["physical_attempts"])
        self.assertEqual(57, summary["completeness"]["valid_logical_cases"])
        self.assertEqual(
            str(expected_usd),
            summary["aggregates"]["campaign"]["api_cost_usd"],
        )
        self.assertEqual(
            str(expected_cny),
            summary["aggregates"]["campaign"]["api_cost_cny"],
        )
        self.assertEqual(
            expected_minimax_input,
            summary["aggregates"]["campaign"][
                "minimax_token_plan_input_tokens"
            ],
        )
        self.assertEqual(
            expected_minimax_output,
            summary["aggregates"]["campaign"][
                "minimax_token_plan_output_tokens"
            ],
        )
        self.assertEqual(
            "0.0006804",
            summary["aggregates"]["compatibility"]["api_cost_cny"],
        )
        self.assertEqual(
            16,
            summary["aggregates"]["compatibility"]["physical_attempts"],
        )
        self.assertEqual(
            4,
            summary["aggregates"]["compatibility"]["by_provider"]["openai"][
                "physical_attempts"
            ],
        )
        self.assertEqual(
            receipts["openai"]["overhead"]["api_cost_usd"],
            summary["aggregates"]["compatibility"]["api_cost_usd"],
        )
        self.assertEqual(
            str(
                Decimal(expected_usd)
                + Decimal(receipts["openai"]["overhead"]["api_cost_usd"])
            ),
            summary["aggregates"]["processing_total"]["api_cost_usd"],
        )
        self.assertEqual(
            120,
            summary["aggregates"]["compatibility"][
                "minimax_token_plan_input_tokens"
            ],
        )
        self.assertEqual(
            expected_minimax_input + 120,
            summary["aggregates"]["processing_total"][
                "minimax_token_plan_input_tokens"
            ],
        )
        self.assertEqual(
            receipt_ids, summary["compatibility_receipt_ids"]
        )
        self.assertEqual(
            "57000", summary["aggregates"]["campaign"]["effective_wall_time_ms"]
        )
        self.assertEqual(
            "58000", summary["aggregates"]["campaign"]["physical_wall_time_ms"]
        )
        first_logical = next(
            item
            for item in summary["logical_cases"]
            if item["case_id"] == first_case["case_id"]
        )
        self.assertEqual(first_case["retry_run_id"], first_logical["effective_run_id"])
        self.assertEqual(100, first_logical["score"])
        self.assertEqual("1000", first_logical["effective_wall_time_ms"])
        self.assertEqual("2000", first_logical["physical_wall_time_ms"])
        self.assertEqual("complete", first_logical["physical_wall_time_status"])
        first_row = summary["aggregates"]["by_configuration"][
            first_case["configuration_id"]
        ]
        self.assertEqual(
            "1000",
            first_row["challenge_effective_wall_time_ms"][
                first_case["challenge_id"]
            ],
        )
        self.assertEqual(
            "2000",
            first_row["challenge_physical_wall_time_ms"][
                first_case["challenge_id"]
            ],
        )
        self.assertEqual(
            "complete",
            first_row["challenge_physical_wall_time_statuses"][
                first_case["challenge_id"]
            ],
        )
        self.assertEqual(
            {
                "openai_api": "https://developers.openai.com/api/docs/pricing",
                "codex_credits": "https://learn.chatgpt.com/docs/pricing",
                "minimax_api": "https://platform.minimaxi.com/docs/guides/pricing-paygo",
            },
            summary["cost_scope"]["rate_card_sources"],
        )
        self.assertIn("| 配置 |", markdown)
        self.assertIn("指针表分数 /100", markdown)
        self.assertIn("有效 attempt 耗时(s)", markdown)
        self.assertIn("物理耗时(s)", markdown)
        self.assertIn("MiniMax 输入 token", markdown)
        self.assertIn("兼容性门开销", markdown)
        self.assertIn(
            "| 配置 | 挑战 | 分数 /100 | 有效 attempt 耗时(s) | 物理总耗时(s) | 物理尝试 | 结果 |",
            markdown,
        )
        challenge_label = {
            "fixed-pointer-table": "固定指针表",
            "arm-thumb-control-flow": "ARM/Thumb 控制流",
            "tdd-manifest-contract": "TDD/Manifest 合同",
        }[first_case["challenge_id"]]
        self.assertIn(
            f"| {first_case['configuration_id']} | {challenge_label} | 100 | 1 | 2 | 2 | verified-passed |",
            markdown,
        )
        self.assertIn("OpenAI 官方 API 价表", markdown)
        self.assertIn("Codex 官方 credit 价表", markdown)
        self.assertIn("MiniMax 官方 API 价表", markdown)
        self.assertIn(receipt_ids["openai"], markdown)
        self.assertIn(receipt_ids["minimax"], markdown)


if __name__ == "__main__":
    unittest.main()
