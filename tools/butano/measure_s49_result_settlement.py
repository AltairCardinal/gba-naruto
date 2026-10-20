#!/usr/bin/env python3
"""Measure the remake's post-battle settlement for S49 and keep the receipt.

The C++ probe in ``butano-sequel/benchmark/tests/test_battle_result_settlement.cpp``
runs the production settlement over the production tables and prints one JSON
payload.  This tool runs it through the repository's benchmark runner and keeps
the payload as an artifact, so the measurement can be diffed between rounds
without re-reading C++.

Usage::

    python3 tools/butano/measure_s49_result_settlement.py
    python3 tools/butano/measure_s49_result_settlement.py --out-dir <path>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools/butano/run_cpp_benchmark_tests.py"
PROBE = "test_battle_result_settlement"
DEFAULT_OUT = ROOT / "artifacts/s49-result-settlement-v1"


class SettlementMeasurementError(RuntimeError):
    """The probe did not produce a usable receipt."""


def measure(out_dir: Path) -> dict[str, object]:
    if not RUNNER.is_file():
        raise SettlementMeasurementError(f"missing C++ test runner: {RUNNER}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt = out_dir / "settlement.json"
    if receipt.exists():
        receipt.unlink()
    environment = {**os.environ, "KONOHA_SETTLEMENT_RECEIPT": str(receipt)}
    completed = subprocess.run(
        [sys.executable, str(RUNNER), PROBE],
        cwd=str(ROOT),
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SettlementMeasurementError(
            f"the C++ settlement probe failed with exit {completed.returncode}:\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    if not receipt.is_file():
        raise SettlementMeasurementError(
            f"the C++ settlement probe wrote no receipt:\n{completed.stdout}")
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    manifest = {
        "schema": "konoha.s49-result-settlement-measurement.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runner": str(RUNNER),
        "probe": PROBE,
        "probe_source": "butano-sequel/benchmark/tests/"
                        "test_battle_result_settlement.cpp",
        "runner_stdout": completed.stdout.strip(),
        "receipt": "settlement.json",
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        payload = measure(args.out_dir)
    except SettlementMeasurementError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
