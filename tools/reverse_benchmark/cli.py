"""Command-line entry points for selected frozen reverse-model campaigns."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from .campaign import create_smoke_plan, execute_smoke_plan, validate_smoke_plan
from .compatibility import (
    collect_openai_native_static_preflight,
    collect_openai_proxy_static_preflight,
    collect_static_preflight,
    run_openai_proxy_compatibility,
    run_openai_native_compatibility,
    run_minimax_compatibility,
    validate_compatibility_receipt_set,
)
from .credentials import load_minimax_credential, minimax_environment_provider
from .matrix import (
    CODEX_NATIVE_TRANSPORT_PROFILE,
    OPENAI_PROXY_TRANSPORT_PROFILE,
    benchmark_matrix,
)
from .report import render_smoke_markdown, summarize_smoke_campaign


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON file: {path}") from error


def _write_new_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _load_provided_compatibility_receipts(args: argparse.Namespace) -> dict[str, object]:
    proxy_path = getattr(args, "openai_proxy_compatibility_receipt", None)
    native_path = getattr(args, "openai_native_compatibility_receipt", None)
    if proxy_path is not None and native_path is not None:
        raise ValueError("select exactly one OpenAI compatibility receipt transport")
    paths = {
        "openai": native_path if native_path is not None else proxy_path,
        "minimax": getattr(args, "minimax_compatibility_receipt", None),
    }
    receipts = {
        provider: _load_json(path)
        for provider, path in paths.items()
        if path is not None
    }
    if not receipts:
        raise ValueError("at least one compatibility receipt is required")
    return receipts


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("matrix", help="print the frozen 19-configuration matrix")

    plan = commands.add_parser("plan", help="create an immutable selected matrix plan")
    plan.add_argument("--seed", type=int, required=True)
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--configuration-id", action="append")
    plan.add_argument("--openai-proxy-compatibility-receipt", type=Path)
    plan.add_argument("--openai-native-compatibility-receipt", type=Path)
    plan.add_argument("--minimax-compatibility-receipt", type=Path)

    compatibility = commands.add_parser(
        "compat-minimax", help="run the MiniMax static and dynamic compatibility gate"
    )
    compatibility.add_argument("--repo-root", type=Path, required=True)
    compatibility.add_argument("--output", type=Path, required=True)
    compatibility.add_argument("--execute", action="store_true")

    proxy_compatibility = commands.add_parser(
        "compat-openai-proxy",
        help="run the OpenAI proxy static and dynamic compatibility gate",
    )
    proxy_compatibility.add_argument("--repo-root", type=Path, required=True)
    proxy_compatibility.add_argument("--output", type=Path, required=True)
    proxy_compatibility.add_argument("--execute", action="store_true")
    proxy_compatibility.add_argument(
        "--allow-plaintext-auth-relay", action="store_true"
    )

    native_compatibility = commands.add_parser(
        "compat-openai-native",
        help="run the local Codex native provider compatibility gate",
    )
    native_compatibility.add_argument("--repo-root", type=Path, required=True)
    native_compatibility.add_argument("--output", type=Path, required=True)
    native_compatibility.add_argument("--execute", action="store_true")

    run = commands.add_parser("run", help="execute or resume the frozen campaign")
    run.add_argument("--repo-root", type=Path, required=True)
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--runs", type=Path, required=True)
    run.add_argument("--openai-proxy-compatibility-receipt", type=Path)
    run.add_argument("--openai-native-compatibility-receipt", type=Path)
    run.add_argument("--minimax-compatibility-receipt", type=Path)
    run.add_argument("--wall-timeout-s", type=float, default=1_800)
    run.add_argument("--idle-timeout-s", type=float, default=600)
    run.add_argument("--execute", action="store_true")
    run.add_argument("--allow-plaintext-auth-relay", action="store_true")

    report = commands.add_parser("report", help="render JSON and Markdown summaries")
    report.add_argument("--plan", type=Path, required=True)
    report.add_argument("--runs", type=Path, required=True)
    report.add_argument("--openai-proxy-compatibility-receipt", type=Path)
    report.add_argument("--openai-native-compatibility-receipt", type=Path)
    report.add_argument("--minimax-compatibility-receipt", type=Path)
    report.add_argument("--json", type=Path, required=True)
    report.add_argument("--markdown", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "matrix":
        print(
            json.dumps(
                [asdict(item) for item in benchmark_matrix()],
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "plan":
        receipts = validate_compatibility_receipt_set(
            _load_provided_compatibility_receipts(args)
        )
        plan = create_smoke_plan(
            args.seed,
            compatibility_receipt_ids={
                provider: str(receipt["receipt_id"])
                for provider, receipt in receipts.items()
            },
            configuration_ids=args.configuration_id,
            openai_transport_profile=(
                CODEX_NATIVE_TRANSPORT_PROFILE
                if args.openai_native_compatibility_receipt is not None
                else OPENAI_PROXY_TRANSPORT_PROFILE
            ),
        )
        validate_compatibility_receipt_set(
            receipts,
            expected_receipt_ids=plan["compatibility_receipt_ids"],
            expected_provider_contracts=plan["provider_contracts"],
        )
        _write_new_json(args.output, plan)
        return 0
    if args.command == "compat-minimax":
        if not args.execute:
            parser.error("compat-minimax requires --execute")
        static = collect_static_preflight()
        credential = load_minimax_credential()
        receipt = run_minimax_compatibility(
            repo_root=args.repo_root,
            output_root=args.output,
            credential=credential,
            static_preflight=static,
        )
        print(
            json.dumps(
                {
                    "compatible": receipt["compatible"],
                    "receipt_id": receipt["receipt_id"],
                    "receipt": str(args.output.resolve() / "receipt.json"),
                },
                sort_keys=True,
            )
        )
        return 0 if receipt["compatible"] else 2
    if args.command == "compat-openai-proxy":
        if not args.execute:
            parser.error("compat-openai-proxy requires --execute")
        if not args.allow_plaintext_auth_relay:
            parser.error(
                "compat-openai-proxy requires --allow-plaintext-auth-relay"
            )
        static = collect_openai_proxy_static_preflight()
        receipt = run_openai_proxy_compatibility(
            repo_root=args.repo_root,
            output_root=args.output,
            static_preflight=static,
            allow_plaintext_auth_relay=args.allow_plaintext_auth_relay,
        )
        print(
            json.dumps(
                {
                    "compatible": receipt["compatible"],
                    "receipt_id": receipt["receipt_id"],
                    "receipt": str(args.output.resolve() / "receipt.json"),
                },
                sort_keys=True,
            )
        )
        return 0 if receipt["compatible"] else 2
    if args.command == "compat-openai-native":
        if not args.execute:
            parser.error("compat-openai-native requires --execute")
        static = collect_openai_native_static_preflight()
        receipt = run_openai_native_compatibility(
            repo_root=args.repo_root,
            output_root=args.output,
            static_preflight=static,
        )
        print(
            json.dumps(
                {
                    "compatible": receipt["compatible"],
                    "receipt_id": receipt["receipt_id"],
                    "receipt": str(args.output.resolve() / "receipt.json"),
                },
                sort_keys=True,
            )
        )
        return 0 if receipt["compatible"] else 2
    if args.command == "run":
        if not args.execute:
            parser.error("run requires --execute")
        plan = validate_smoke_plan(_load_json(args.plan))
        proxy_selected = any(
            isinstance(configuration, dict)
            and configuration.get("provider") == "openai"
            and configuration.get("transport_profile")
            == OPENAI_PROXY_TRANSPORT_PROFILE
            for configuration in plan["configurations"]
        )
        if proxy_selected and not args.allow_plaintext_auth_relay:
            parser.error("proxy-backed run requires --allow-plaintext-auth-relay")
        receipts = validate_compatibility_receipt_set(
            _load_provided_compatibility_receipts(args),
            expected_receipt_ids=plan["compatibility_receipt_ids"],
            expected_provider_contracts=plan["provider_contracts"],
        )
        environment_provider = None
        if "minimax" in receipts:
            credential = load_minimax_credential()
            environment_provider = minimax_environment_provider(credential)
        result = execute_smoke_plan(
            plan,
            repo_root=args.repo_root,
            output_root=args.runs,
            compatibility_receipts=receipts,
            allow_plaintext_auth_relay=args.allow_plaintext_auth_relay,
            wall_timeout_s=args.wall_timeout_s,
            idle_timeout_s=args.idle_timeout_s,
            environment_for_configuration=environment_provider,
        )
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
        return 0 if result["unavailable_count"] == 0 else 2
    if args.command == "report":
        plan = validate_smoke_plan(_load_json(args.plan))
        receipts = _load_provided_compatibility_receipts(args)
        summary = summarize_smoke_campaign(
            plan,
            args.runs,
            compatibility_receipts=receipts,
        )
        _write_atomic(
            args.json,
            json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        )
        _write_atomic(args.markdown, render_smoke_markdown(summary))
        return 0
    parser.error(f"unsupported command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
