#!/usr/bin/env python3
"""Command-line safety and wiring contracts for the benchmark."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.reverse_benchmark import cli
from tools.reverse_benchmark.campaign import create_smoke_plan
from tools.reverse_benchmark.matrix import CODEX_NATIVE_TRANSPORT_PROFILE


ROOT = Path(__file__).resolve().parents[1]


class ReverseBenchmarkCliTests(unittest.TestCase):
    def test_native_plan_and_run_need_no_proxy_relay_or_minimax_credential(self):
        selected = (
            "openai-gpt-5.6-luna-max",
            "openai-gpt-5.6-terra-max",
            "openai-gpt-5.6-sol-medium",
            "openai-gpt-5.6-sol-ultra",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt_path = root / "native.json"
            receipt_path.write_text("{}")
            plan_path = root / "plan.json"
            with mock.patch(
                "tools.reverse_benchmark.cli.validate_compatibility_receipt_set",
                return_value={"openai": {"receipt_id": "a" * 64}},
            ), mock.patch(
                "tools.reverse_benchmark.cli.load_minimax_credential"
            ) as credential_loader:
                arguments = [
                    "plan",
                    "--seed",
                    "20260820",
                    "--output",
                    str(plan_path),
                    "--openai-native-compatibility-receipt",
                    str(receipt_path),
                ]
                for configuration_id in selected:
                    arguments.extend(["--configuration-id", configuration_id])
                self.assertEqual(0, cli.main(arguments))
            plan = json.loads(plan_path.read_text())
            self.assertEqual(
                {CODEX_NATIVE_TRANSPORT_PROFILE},
                {item["transport_profile"] for item in plan["configurations"]},
            )

            with mock.patch(
                "tools.reverse_benchmark.cli.validate_compatibility_receipt_set",
                return_value={"openai": {"receipt_id": "a" * 64}},
            ), mock.patch(
                "tools.reverse_benchmark.cli.execute_smoke_plan",
                return_value={"unavailable_count": 0},
            ) as executor:
                self.assertEqual(
                    0,
                    cli.main(
                        [
                            "run",
                            "--repo-root",
                            str(ROOT),
                            "--plan",
                            str(plan_path),
                            "--runs",
                            str(root / "runs"),
                            "--openai-native-compatibility-receipt",
                            str(receipt_path),
                            "--execute",
                        ]
                    ),
                )

        credential_loader.assert_not_called()
        self.assertFalse(executor.call_args.kwargs["allow_plaintext_auth_relay"])
        self.assertIsNone(executor.call_args.kwargs["environment_for_configuration"])

    def test_plan_revalidates_receipt_against_created_provider_contract_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt_path = root / "native.json"
            receipt_path.write_text("{}")
            destination = root / "plan.json"
            validated_receipt = {"openai": {"receipt_id": "a" * 64}}
            with mock.patch(
                "tools.reverse_benchmark.cli.validate_compatibility_receipt_set",
                side_effect=[
                    validated_receipt,
                    ValueError("provider contract mismatch"),
                ],
            ) as validator:
                with self.assertRaisesRegex(ValueError, "provider contract mismatch"):
                    cli.main(
                        [
                            "plan",
                            "--seed",
                            "20260820",
                            "--output",
                            str(destination),
                            "--openai-native-compatibility-receipt",
                            str(receipt_path),
                        ]
                    )

        self.assertEqual(2, validator.call_count)
        self.assertFalse(destination.exists())

    def test_openai_native_compatibility_uses_local_session_without_relay_flag(self):
        receipt = {"compatible": True, "receipt_id": "e" * 64}
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "tools.reverse_benchmark.cli.collect_openai_native_static_preflight",
            return_value={"compatible": True},
        ) as static, mock.patch(
            "tools.reverse_benchmark.cli.run_openai_native_compatibility",
            return_value=receipt,
        ) as runner, mock.patch(
            "tools.reverse_benchmark.cli.load_minimax_credential"
        ) as credential_loader:
            result = cli.main(
                [
                    "compat-openai-native",
                    "--repo-root",
                    str(ROOT),
                    "--output",
                    str(Path(directory) / "native-compat"),
                    "--execute",
                ]
            )

        self.assertEqual(0, result)
        static.assert_called_once_with()
        runner.assert_called_once()
        credential_loader.assert_not_called()

    def test_reduced_openai_plan_never_requires_minimax_receipt_or_credential(self):
        selected = (
            "openai-gpt-5.6-luna-max",
            "openai-gpt-5.6-terra-max",
            "openai-gpt-5.6-sol-medium",
            "openai-gpt-5.6-sol-ultra",
        )
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "tools.reverse_benchmark.cli.load_minimax_credential"
        ) as credential_loader, mock.patch(
            "tools.reverse_benchmark.cli.validate_compatibility_receipt_set",
            return_value={"openai": {"receipt_id": "a" * 64}},
        ) as receipt_validator:
            root = Path(directory)
            destination = root / "plan.json"
            openai_receipt = root / "openai.json"
            openai_receipt.write_text("{}")
            arguments = [
                "plan",
                "--seed",
                "20260819",
                "--output",
                str(destination),
                "--openai-proxy-compatibility-receipt",
                str(openai_receipt),
            ]
            for configuration_id in selected:
                arguments.extend(["--configuration-id", configuration_id])

            self.assertEqual(0, cli.main(arguments))
            plan = json.loads(destination.read_text())

        credential_loader.assert_not_called()
        self.assertEqual(2, receipt_validator.call_count)
        self.assertEqual(
            mock.call({"openai": {}}), receipt_validator.call_args_list[0]
        )
        self.assertEqual(12, plan["logical_case_count"])
        self.assertEqual(set(selected), {item["id"] for item in plan["configurations"]})
        self.assertEqual({"openai": "a" * 64}, plan["compatibility_receipt_ids"])

    def test_reduced_openai_run_never_loads_minimax_credential(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_path = root / "plan.json"
            receipt_path = root / "openai.json"
            plan_path.write_text(
                json.dumps(
                    create_smoke_plan(
                        20260819,
                        compatibility_receipt_ids={"openai": "a" * 64},
                        configuration_ids=("openai-gpt-5.6-luna-max",),
                        created_at="2026-08-19T00:00:00+00:00",
                    )
                )
            )
            receipt_path.write_text("{}")
            with mock.patch(
                "tools.reverse_benchmark.cli.validate_compatibility_receipt_set",
                return_value={"openai": {"receipt_id": "a" * 64}},
            ), mock.patch(
                "tools.reverse_benchmark.cli.load_minimax_credential"
            ) as credential_loader, mock.patch(
                "tools.reverse_benchmark.cli.execute_smoke_plan",
                return_value={"unavailable_count": 0},
            ) as executor:
                result = cli.main(
                    [
                        "run",
                        "--repo-root",
                        str(ROOT),
                        "--plan",
                        str(plan_path),
                        "--runs",
                        str(root / "runs"),
                        "--openai-proxy-compatibility-receipt",
                        str(receipt_path),
                        "--execute",
                        "--allow-plaintext-auth-relay",
                    ]
                )

        self.assertEqual(0, result)
        credential_loader.assert_not_called()
        self.assertIsNone(executor.call_args.kwargs["environment_for_configuration"])

    def test_matrix_and_plan_are_model_and_credential_free(self):
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "tools.reverse_benchmark", "matrix"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(19, len(json.loads(completed.stdout)))

        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "tools.reverse_benchmark.cli.load_minimax_credential"
        ) as credential_loader, mock.patch(
            "tools.reverse_benchmark.cli.validate_compatibility_receipt_set",
            return_value={
                "openai": {"receipt_id": "a" * 64},
                "minimax": {"receipt_id": "b" * 64},
            },
        ) as receipt_validator:
            destination = Path(directory) / "plan.json"
            openai_receipt = Path(directory) / "openai.json"
            minimax_receipt = Path(directory) / "minimax.json"
            openai_receipt.write_text("{}")
            minimax_receipt.write_text("{}")
            self.assertEqual(
                0,
                cli.main(
                    [
                        "plan",
                        "--seed",
                        "20260816",
                        "--output",
                        str(destination),
                        "--openai-proxy-compatibility-receipt",
                        str(openai_receipt),
                        "--minimax-compatibility-receipt",
                        str(minimax_receipt),
                    ]
                ),
            )
            plan = json.loads(destination.read_text())

        credential_loader.assert_not_called()
        self.assertEqual(2, receipt_validator.call_count)
        self.assertEqual(57, len(plan["cases"]))
        self.assertEqual(
            {"openai": "a" * 64, "minimax": "b" * 64},
            plan["compatibility_receipt_ids"],
        )

    def test_costly_commands_require_explicit_execute_before_loading_credentials(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "tools.reverse_benchmark.cli.load_minimax_credential"
        ) as credential_loader:
            with self.assertRaises(SystemExit):
                cli.main(
                    [
                        "compat-minimax",
                        "--repo-root",
                        str(ROOT),
                        "--output",
                        str(Path(directory) / "compat"),
                    ]
                )
            with self.assertRaises(SystemExit):
                cli.main(
                    [
                        "compat-openai-proxy",
                        "--repo-root",
                        str(ROOT),
                        "--output",
                        str(Path(directory) / "proxy-compat"),
                    ]
                )
            with self.assertRaises(SystemExit):
                cli.main(
                    [
                        "run",
                        "--repo-root",
                        str(ROOT),
                        "--plan",
                        str(Path(directory) / "plan.json"),
                        "--runs",
                        str(Path(directory) / "runs"),
                        "--openai-proxy-compatibility-receipt",
                        str(Path(directory) / "openai-receipt.json"),
                        "--minimax-compatibility-receipt",
                        str(Path(directory) / "minimax-receipt.json"),
                    ]
                )

        credential_loader.assert_not_called()

    def test_openai_proxy_compatibility_never_loads_minimax_credential(self):
        receipt = {
            "compatible": True,
            "receipt_id": "e" * 64,
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "tools.reverse_benchmark.cli.collect_openai_proxy_static_preflight",
            return_value={"compatible": True},
        ) as static, mock.patch(
            "tools.reverse_benchmark.cli.run_openai_proxy_compatibility",
            return_value=receipt,
        ) as runner, mock.patch(
            "tools.reverse_benchmark.cli.load_minimax_credential"
        ) as credential_loader:
            result = cli.main(
                [
                    "compat-openai-proxy",
                    "--repo-root",
                    str(ROOT),
                    "--output",
                    str(Path(directory) / "proxy-compat"),
                    "--execute",
                    "--allow-plaintext-auth-relay",
                ]
            )

        self.assertEqual(0, result)
        static.assert_called_once_with()
        runner.assert_called_once()
        credential_loader.assert_not_called()

    def test_openai_proxy_execute_still_requires_plaintext_authorization(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "tools.reverse_benchmark.cli.collect_openai_proxy_static_preflight"
        ) as static, mock.patch(
            "tools.reverse_benchmark.cli.run_openai_proxy_compatibility"
        ) as runner:
            with self.assertRaises(SystemExit):
                cli.main(
                    [
                        "compat-openai-proxy",
                        "--repo-root",
                        str(ROOT),
                        "--output",
                        str(Path(directory) / "proxy-compat"),
                        "--execute",
                    ]
                )

        static.assert_not_called()
        runner.assert_not_called()

    def test_invalid_receipt_stops_run_before_credentials_and_run_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_path = root / "plan.json"
            receipt_path = root / "receipt.json"
            openai_receipt_path = root / "openai-receipt.json"
            runs = root / "runs"
            plan_path.write_text(
                json.dumps(
                    create_smoke_plan(
                        20260816,
                        compatibility_receipt_ids={
                            "openai": "a" * 64,
                            "minimax": "b" * 64,
                        },
                        created_at="2026-08-16T00:00:00+00:00",
                    )
                )
            )
            receipt_path.write_text(json.dumps({"compatible": True}))
            openai_receipt_path.write_text(json.dumps({"compatible": True}))
            with mock.patch(
                "tools.reverse_benchmark.cli.load_minimax_credential"
            ) as credential_loader, mock.patch(
                "tools.reverse_benchmark.cli.execute_smoke_plan"
            ) as executor:
                with self.assertRaisesRegex(ValueError, "receipt"):
                    cli.main(
                        [
                            "run",
                            "--repo-root",
                            str(ROOT),
                            "--plan",
                            str(plan_path),
                            "--runs",
                            str(runs),
                            "--openai-proxy-compatibility-receipt",
                            str(openai_receipt_path),
                            "--minimax-compatibility-receipt",
                            str(receipt_path),
                            "--execute",
                            "--allow-plaintext-auth-relay",
                        ]
                    )

            credential_loader.assert_not_called()
            executor.assert_not_called()
            self.assertFalse(runs.exists())

    def test_report_requires_compatibility_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_path = root / "plan.json"
            plan_path.write_text(
                json.dumps(
                    create_smoke_plan(
                        20260816,
                        compatibility_receipt_ids={
                            "openai": "a" * 64,
                            "minimax": "b" * 64,
                        },
                        created_at="2026-08-16T00:00:00+00:00",
                    )
                )
            )
            with self.assertRaisesRegex(ValueError, "compatibility receipt"):
                cli.main(
                    [
                        "report",
                        "--plan",
                        str(plan_path),
                        "--runs",
                        str(root / "runs"),
                        "--json",
                        str(root / "summary.json"),
                        "--markdown",
                        str(root / "summary.md"),
                    ]
                )


if __name__ == "__main__":
    unittest.main()
