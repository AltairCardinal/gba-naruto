#!/usr/bin/env python3
"""Credential-loading and provider-scoping contracts for the benchmark."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.reverse_benchmark.campaign import create_smoke_plan, execute_smoke_plan
from tools.reverse_benchmark.credentials import (
    MissingMiniMaxCredential,
    load_minimax_credential,
    minimax_environment_provider,
)
from tools.reverse_benchmark.matrix import benchmark_matrix


ROOT = Path(__file__).resolve().parents[1]


class MiniMaxCredentialTests(unittest.TestCase):
    def test_loader_uses_keychain_then_environment_then_mmx_config(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text(json.dumps({"api_key": "config-key"}))

            keychain = load_minimax_credential(
                environ={
                    "MINIMAX_API_KEY": "environment-key",
                    "ANTHROPIC_API_KEY": "anthropic-key",
                },
                keychain_reader=lambda: "keychain-key",
                config_path=config,
            )
            environment = load_minimax_credential(
                environ={"MINIMAX_API_KEY": "environment-key"},
                keychain_reader=lambda: None,
                config_path=config,
            )
            fallback = load_minimax_credential(
                environ={},
                keychain_reader=lambda: None,
                config_path=config,
            )

        self.assertEqual("keychain", keychain.source)
        self.assertEqual("keychain-key", keychain.value)
        self.assertEqual("MINIMAX_API_KEY", environment.source)
        self.assertEqual("environment-key", environment.value)
        self.assertEqual("mmx-config", fallback.source)
        self.assertEqual("config-key", fallback.value)

    def test_missing_or_blank_values_fail_without_leaking_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text(json.dumps({"api_key": "   "}))
            with self.assertRaises(MissingMiniMaxCredential) as raised:
                load_minimax_credential(
                    environ={"MINIMAX_API_KEY": "   "},
                    keychain_reader=lambda: None,
                    config_path=config,
                )

        self.assertNotIn("api_key", str(raised.exception).lower())
        self.assertNotIn("   ", str(raised.exception))

    def test_environment_provider_scopes_secret_only_to_minimax(self):
        credential = load_minimax_credential(
            environ={"MINIMAX_API_KEY": "scoped-secret"},
            keychain_reader=lambda: None,
            config_path=Path("/definitely/missing"),
        )
        provider = minimax_environment_provider(credential)
        openai = next(item for item in benchmark_matrix() if item.provider == "openai")
        minimax = next(item for item in benchmark_matrix() if item.provider == "minimax")

        self.assertIsNone(provider(openai))
        self.assertEqual(
            {"BENCH_MINIMAX_API_KEY": "scoped-secret"}, provider(minimax)
        )

    def test_campaign_missing_credentials_fails_before_creating_runs(self):
        plan = create_smoke_plan(
            20260816,
            compatibility_receipt_ids={"openai": "a" * 64, "minimax": "b" * 64},
            created_at="2026-08-16T00:00:00+00:00",
        )
        calls: list[object] = []
        with tempfile.TemporaryDirectory() as directory, patch(
            "tools.reverse_benchmark.campaign.validate_compatibility_receipt_set",
            return_value={"openai": {}, "minimax": {}},
        ):
            output_root = Path(directory) / "runs"
            with self.assertRaisesRegex(ValueError, "MiniMax credential"):
                execute_smoke_plan(
                    plan,
                    repo_root=ROOT,
                    output_root=output_root,
                    compatibility_receipts={"openai": {}, "minimax": {}},
                    allow_plaintext_auth_relay=True,
                    attempt_runner=lambda **kwargs: calls.append(kwargs),
                )
            self.assertFalse(output_root.exists())

        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
