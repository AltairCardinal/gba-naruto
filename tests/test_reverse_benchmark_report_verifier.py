#!/usr/bin/env python3
"""Independent report regeneration and completeness contracts."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from tests.test_reverse_benchmark_campaign import (
    REDUCED_CONFIGURATION_IDS,
    _compatibility_receipts,
)
from tools.reverse_benchmark.billing import calculate_attempt_billing
from tools.reverse_benchmark.campaign import create_smoke_plan
from tools.reverse_benchmark.compatibility import (
    evaluate_static_preflight,
    run_openai_native_compatibility,
)
from tools.reverse_benchmark.matrix import (
    CODEX_NATIVE_TRANSPORT_PROFILE,
    benchmark_configuration,
)
from tools.reverse_benchmark.pricing import NormalizedUsage
from tools.reverse_benchmark.report import (
    render_smoke_markdown,
    summarize_smoke_campaign,
)
from tools.verify_reverse_benchmark_report import (
    _parser,
    validate_manifest_accounting,
    verify_benchmark_report,
)


ROOT = Path(__file__).resolve().parents[1]


class ReverseBenchmarkReportVerifierTests(unittest.TestCase):
    def test_regenerates_native_plan_receipt_and_report_end_to_end(self):
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
            root = Path(directory)
            receipt_root = root / "native-compatibility"
            receipt = run_openai_native_compatibility(
                repo_root=root,
                output_root=receipt_root,
                static_preflight=static,
                attempt_executor=fake_attempt,
                created_at="2026-08-19T00:00:00+00:00",
            )
            plan = create_smoke_plan(
                20260820,
                compatibility_receipt_ids={"openai": receipt["receipt_id"]},
                openai_transport_profile=CODEX_NATIVE_TRANSPORT_PROFILE,
                created_at="2026-08-19T00:01:00+00:00",
            )
            plan_path = root / "plan.json"
            runs = root / "runs"
            report_json = root / "report.json"
            report_markdown = root / "report.md"
            plan_path.write_text(
                json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            )
            summary = summarize_smoke_campaign(
                plan,
                runs,
                compatibility_receipts={"openai": receipt},
                expected_codex_sha256="d" * 64,
            )
            report_json.write_text(
                json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False)
                + "\n"
            )
            report_markdown.write_text(render_smoke_markdown(summary))

            verified = verify_benchmark_report(
                plan_path=plan_path,
                runs_root=runs,
                receipt_paths={"openai": receipt_root / "receipt.json"},
                report_json_path=report_json,
                report_markdown_path=report_markdown,
                expected_configuration_ids=REDUCED_CONFIGURATION_IDS,
                expected_codex_sha256="d" * 64,
                require_terminal=False,
            )
            rendered_markdown = report_markdown.read_text()

        self.assertEqual(12, verified["logical_cases"])
        self.assertEqual(REDUCED_CONFIGURATION_IDS, tuple(verified["configuration_ids"]))
        self.assertIn("本机 Codex 原生兼容性回执", rendered_markdown)

    def test_direct_script_entrypoint_resolves_repository_package(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "tools" / "verify_reverse_benchmark_report.py"),
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("--report-json", completed.stdout)

    def test_recomputes_manifest_billing_and_requires_ultra_all_agent_scope(self):
        usage = NormalizedUsage(
            uncached_input=100,
            cached_input=20,
            output=10,
            reasoning_output=4,
        )

        def manifest_for(configuration, *, usage_scope="all-agent-threads"):
            billing = calculate_attempt_billing(
                configuration,
                [usage],
                usage_granularities=["request"],
                usage_complete=True,
                usage_scope=usage_scope,
            )
            return {
                "status": "verified-passed",
                "telemetry": {
                    "usage": asdict(usage),
                    "requests": [
                        {
                            "ordinal": 1,
                            "usage": asdict(usage),
                            "usage_granularity": "request",
                        }
                    ],
                    "usage_complete": True,
                    "usage_scope": usage_scope,
                },
                "billing": billing,
            }

        luna = benchmark_configuration(
            "openai-gpt-5.6-luna-max",
            openai_transport_profile=CODEX_NATIVE_TRANSPORT_PROFILE,
        )
        valid = manifest_for(luna)
        validate_manifest_accounting(valid, luna)

        tampered = json.loads(json.dumps(valid))
        tampered["billing"]["totals"]["codex_credits_estimate"] = "999"
        with self.assertRaisesRegex(ValueError, "billing"):
            validate_manifest_accounting(tampered, luna)

        ultra = benchmark_configuration(
            "openai-gpt-5.6-sol-ultra",
            openai_transport_profile=CODEX_NATIVE_TRANSPORT_PROFILE,
        )
        incomplete_scope = manifest_for(ultra, usage_scope="root-thread-only")
        with self.assertRaisesRegex(ValueError, "all-agent"):
            validate_manifest_accounting(incomplete_scope, ultra)

    def test_cli_accepts_native_openai_receipt_as_the_openai_provider_evidence(self):
        args = _parser().parse_args(
            [
                "--plan",
                "plan.json",
                "--runs",
                "runs",
                "--openai-native-compatibility-receipt",
                "native.json",
                "--report-json",
                "report.json",
                "--report-markdown",
                "report.md",
                "--configuration-id",
                "openai-gpt-5.6-luna-max",
            ]
        )

        self.assertEqual(Path("native.json"), args.openai_native_compatibility_receipt)
        self.assertIsNone(args.openai_proxy_compatibility_receipt)

    def test_regenerates_selected_report_and_rejects_tampering_or_missing_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipts = _compatibility_receipts(root / "gates")
            openai_receipt = receipts["openai"]
            plan = create_smoke_plan(
                20260819,
                compatibility_receipt_ids={
                    "openai": openai_receipt["receipt_id"]
                },
                configuration_ids=REDUCED_CONFIGURATION_IDS,
                created_at="2026-08-19T00:00:00+00:00",
            )
            plan_path = root / "plan.json"
            runs = root / "runs"
            report_json = root / "report.json"
            report_markdown = root / "report.md"
            receipt_path = root / "gates" / "openai-compatibility" / "receipt.json"
            plan_path.write_text(
                json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            )
            summary = summarize_smoke_campaign(
                plan,
                runs,
                compatibility_receipts={"openai": openai_receipt},
                expected_codex_sha256="b" * 64,
            )
            report_json.write_text(
                json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False)
                + "\n"
            )
            report_markdown.write_text(render_smoke_markdown(summary))

            verified = verify_benchmark_report(
                plan_path=plan_path,
                runs_root=runs,
                receipt_paths={"openai": receipt_path},
                report_json_path=report_json,
                report_markdown_path=report_markdown,
                expected_configuration_ids=REDUCED_CONFIGURATION_IDS,
                expected_codex_sha256="b" * 64,
                require_terminal=False,
            )
            self.assertEqual(12, verified["logical_cases"])
            self.assertEqual(0, verified["terminal_cases"])

            with self.assertRaisesRegex(ValueError, "terminal"):
                verify_benchmark_report(
                    plan_path=plan_path,
                    runs_root=runs,
                    receipt_paths={"openai": receipt_path},
                    report_json_path=report_json,
                    report_markdown_path=report_markdown,
                    expected_configuration_ids=REDUCED_CONFIGURATION_IDS,
                    expected_codex_sha256="b" * 64,
                )

            report_markdown.write_text(report_markdown.read_text() + "tampered\n")
            with self.assertRaisesRegex(ValueError, "Markdown"):
                verify_benchmark_report(
                    plan_path=plan_path,
                    runs_root=runs,
                    receipt_paths={"openai": receipt_path},
                    report_json_path=report_json,
                    report_markdown_path=report_markdown,
                    expected_configuration_ids=REDUCED_CONFIGURATION_IDS,
                    expected_codex_sha256="b" * 64,
                    require_terminal=False,
                )


if __name__ == "__main__":
    unittest.main()
