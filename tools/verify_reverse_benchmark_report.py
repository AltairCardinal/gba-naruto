#!/usr/bin/env python3
"""Regenerate and independently verify a frozen reverse benchmark report."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.reverse_benchmark.billing import calculate_attempt_billing
from tools.reverse_benchmark.campaign import validate_smoke_plan
from tools.reverse_benchmark.capture import contains_credential_material_bytes
from tools.reverse_benchmark.matrix import (
    BenchmarkConfiguration,
    configuration_from_frozen,
)
from tools.reverse_benchmark.packets import SMOKE_CHALLENGE_IDS
from tools.reverse_benchmark.pricing import NormalizedUsage
from tools.reverse_benchmark.report import (
    render_smoke_markdown,
    summarize_smoke_campaign,
)


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON file: {path}") from error


def _report_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized_usage(value: object, field: str) -> NormalizedUsage:
    if not isinstance(value, dict):
        raise ValueError(f"manifest {field} is not normalized usage")
    try:
        usage = NormalizedUsage(**value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"manifest {field} is not normalized usage") from error
    if asdict(usage) != value:
        raise ValueError(f"manifest {field} has unexpected usage fields")
    return usage


def validate_manifest_accounting(
    manifest: object,
    configuration: BenchmarkConfiguration,
) -> None:
    """Recompute one attempt's billing from normalized request telemetry."""

    if not isinstance(manifest, dict):
        raise ValueError("attempt manifest is not an object")
    telemetry = manifest.get("telemetry")
    if not isinstance(telemetry, dict):
        raise ValueError("manifest telemetry is missing")
    usage_complete = telemetry.get("usage_complete")
    usage_scope = telemetry.get("usage_scope")
    requests = telemetry.get("requests")
    if not isinstance(usage_complete, bool):
        raise ValueError("manifest usage_complete is invalid")
    if not isinstance(usage_scope, str) or not isinstance(requests, list):
        raise ValueError("manifest usage scope or requests are invalid")

    request_usages: list[NormalizedUsage] = []
    request_granularities: list[str] = []
    for ordinal, request in enumerate(requests, start=1):
        if not isinstance(request, dict) or request.get("ordinal") != ordinal:
            raise ValueError("manifest request sequence is invalid")
        request_usages.append(
            _normalized_usage(request.get("usage"), f"request {ordinal} usage")
        )
        granularity = request.get("usage_granularity")
        if not isinstance(granularity, str):
            raise ValueError("manifest request granularity is invalid")
        request_granularities.append(granularity)

    aggregate = _normalized_usage(telemetry.get("usage"), "aggregate usage")
    if usage_complete:
        summed = NormalizedUsage()
        for request_usage in request_usages:
            summed += request_usage
        if summed != aggregate:
            raise ValueError("manifest aggregate usage does not match requests")

    if (
        manifest.get("status") in {"verified-passed", "verified-failed"}
        and configuration.system_mode == "multi-agent"
        and (not usage_complete or usage_scope != "all-agent-threads")
    ):
        raise ValueError("verified Ultra attempt lacks all-agent usage closure")

    expected_billing = calculate_attempt_billing(
        configuration,
        request_usages,
        usage_granularities=request_granularities,
        usage_complete=usage_complete,
        usage_scope=usage_scope,
    )
    if manifest.get("billing") != expected_billing:
        raise ValueError("manifest billing does not match telemetry recomputation")


def verify_benchmark_report(
    *,
    plan_path: Path,
    runs_root: Path,
    receipt_paths: Mapping[str, Path],
    report_json_path: Path,
    report_markdown_path: Path,
    expected_configuration_ids: Sequence[str],
    expected_codex_sha256: str | None = None,
    require_terminal: bool = True,
) -> dict[str, object]:
    """Verify bindings, exact regeneration, terminal coverage, and credentials."""

    plan_path = Path(plan_path)
    runs_root = Path(runs_root)
    report_json_path = Path(report_json_path)
    report_markdown_path = Path(report_markdown_path)
    plan = validate_smoke_plan(_load_json(plan_path))
    actual_configuration_ids = tuple(
        str(value["id"]) for value in plan["configurations"]
    )
    expected_ids = tuple(expected_configuration_ids)
    if (
        not expected_ids
        or len(set(expected_ids)) != len(expected_ids)
        or actual_configuration_ids != expected_ids
    ):
        raise ValueError("report plan configuration set or order is unexpected")
    expected_pairs = {
        (configuration_id, challenge_id)
        for configuration_id in expected_ids
        for challenge_id in SMOKE_CHALLENGE_IDS
    }
    actual_pairs = {
        (str(case["configuration_id"]), str(case["challenge_id"]))
        for case in plan["cases"]
    }
    if actual_pairs != expected_pairs or len(plan["cases"]) != len(expected_pairs):
        raise ValueError("report plan is not the exact selected challenge cross product")

    expected_providers = set(plan["compatibility_receipt_ids"])
    if set(receipt_paths) != expected_providers:
        raise ValueError("report receipt paths do not match selected providers")
    receipts = {
        provider: _load_json(Path(path))
        for provider, path in receipt_paths.items()
    }
    configurations = {
        configuration.id: configuration
        for configuration in (
            configuration_from_frozen(value)
            for value in plan["configurations"]
        )
    }
    for case in plan["cases"]:
        configuration = configurations[str(case["configuration_id"])]
        for key in ("primary_run_id", "retry_run_id"):
            manifest_path = runs_root / str(case[key]) / "manifest.json"
            if manifest_path.is_file():
                validate_manifest_accounting(
                    _load_json(manifest_path), configuration
                )
    regenerated = summarize_smoke_campaign(
        plan,
        runs_root,
        compatibility_receipts=receipts,
        expected_codex_sha256=expected_codex_sha256,
    )
    expected_json = _report_json_bytes(regenerated)
    try:
        actual_json = report_json_path.read_bytes()
        actual_markdown = report_markdown_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ValueError("report artifact is missing or unreadable") from error
    if actual_json != expected_json:
        raise ValueError("report JSON does not match deterministic regeneration")
    expected_markdown = render_smoke_markdown(regenerated)
    if actual_markdown != expected_markdown:
        raise ValueError("report Markdown does not match deterministic regeneration")

    completeness = regenerated["completeness"]
    logical_cases = int(completeness["logical_cases"])
    terminal_cases = int(completeness["valid_logical_cases"]) + int(
        completeness["unavailable_logical_cases"]
    )
    if require_terminal and terminal_cases != logical_cases:
        raise ValueError("report does not contain a terminal state for every logical case")

    scanned_paths = {
        plan_path,
        report_json_path,
        report_markdown_path,
        *(Path(path) for path in receipt_paths.values()),
    }
    for case in plan["cases"]:
        for key in ("primary_run_id", "retry_run_id"):
            manifest = runs_root / str(case[key]) / "manifest.json"
            if manifest.is_file():
                scanned_paths.add(manifest)
    credential_hits = [
        str(path)
        for path in sorted(scanned_paths)
        if contains_credential_material_bytes(path.read_bytes())
    ]
    if credential_hits:
        raise ValueError("credential material detected in benchmark report evidence")
    return {
        "plan_id": plan["plan_id"],
        "logical_cases": logical_cases,
        "terminal_cases": terminal_cases,
        "configuration_ids": list(actual_configuration_ids),
        "credential_scan_file_count": len(scanned_paths),
        "plan_sha256": _sha256(plan_path),
        "report_json_sha256": _sha256(report_json_path),
        "report_markdown_sha256": _sha256(report_markdown_path),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--openai-proxy-compatibility-receipt", type=Path)
    parser.add_argument("--openai-native-compatibility-receipt", type=Path)
    parser.add_argument("--minimax-compatibility-receipt", type=Path)
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--report-markdown", type=Path, required=True)
    parser.add_argument("--configuration-id", action="append", required=True)
    parser.add_argument("--allow-incomplete", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if (
        args.openai_proxy_compatibility_receipt is not None
        and args.openai_native_compatibility_receipt is not None
    ):
        raise ValueError("select exactly one OpenAI compatibility receipt transport")
    openai_receipt = (
        args.openai_native_compatibility_receipt
        if args.openai_native_compatibility_receipt is not None
        else args.openai_proxy_compatibility_receipt
    )
    receipt_paths = {
        provider: path
        for provider, path in (
            ("openai", openai_receipt),
            ("minimax", args.minimax_compatibility_receipt),
        )
        if path is not None
    }
    verified = verify_benchmark_report(
        plan_path=args.plan,
        runs_root=args.runs,
        receipt_paths=receipt_paths,
        report_json_path=args.report_json,
        report_markdown_path=args.report_markdown,
        expected_configuration_ids=args.configuration_id,
        require_terminal=not args.allow_incomplete,
    )
    print(json.dumps(verified, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
