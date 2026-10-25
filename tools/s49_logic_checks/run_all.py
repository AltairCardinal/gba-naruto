#!/usr/bin/env python3
"""Run every S49 logic state check and print the red / green table.

One command, one table, one exit code.

Exit codes
----------

======  ==========================================================
0       every line is green
1       at least one line is red (未通过) -- the headline
2       an input is missing (a check could not even start)
3       no red line, but at least one line is 无法判定
======  ==========================================================

The priority is explicit, not numeric: a missing input (2) beats a red
line (1), and a red line (1) beats an undecided line (3).

Usage::

    python tools/s49_logic_checks/run_all.py
    python tools/s49_logic_checks/run_all.py --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from s49_logic_common import (  # noqa: E402
    EXIT_FAIL,
    EXIT_INPUT_ERROR,
    EXIT_OK,
    EXIT_UNDECIDED,
    FAIL,
    PASS,
    RECEIPTS,
    UNDECIDED,
)

#: The checks, in the order they are run.
CHECKS = (
    ("equivalence-original-recording", "check_original_equivalence.py"),
    ("battle-14-roster", "check_battle_roster.py"),
    ("rule-standby-state", "check_rule_standby_state.py"),
    ("rule-ai-facing", "check_rule_ai_facing.py"),
    ("rule-move-grid", "check_rule_move_grid.py"),
    ("rule-idle-sequence", "check_rule_idle_sequence.py"),
    ("rule-fbff", "check_rule_fbff.py"),
)

MARK = {PASS: "绿", FAIL: "红", UNDECIDED: "灰"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the table as JSON")
    args = parser.parse_args(argv)

    RECEIPTS.mkdir(parents=True, exist_ok=True)
    results = []
    has_input_error = False
    has_fail = False
    has_undecided = False
    for name, script in CHECKS:
        completed = subprocess.run(
            [sys.executable, str(HERE / script)],
            capture_output=True,
            text=True,
            check=False,
        )
        receipt_path = RECEIPTS / f"{name}.json"
        receipt = None
        if receipt_path.is_file():
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        verdict = receipt["verdict"] if receipt else UNDECIDED
        results.append(
            {
                "check": name,
                "script": script,
                "exit_code": completed.returncode,
                "verdict": verdict,
                "items": receipt["items"] if receipt else [],
                "notes": receipt.get("notes", []) if receipt else [],
            }
        )
        if completed.returncode == EXIT_INPUT_ERROR:
            has_input_error = True
        if FAIL in verdict:
            has_fail = True
        if UNDECIDED in verdict:
            has_undecided = True

    if has_input_error:
        worst = EXIT_INPUT_ERROR
    elif has_fail:
        worst = EXIT_FAIL
    elif has_undecided:
        worst = EXIT_UNDECIDED
    else:
        worst = EXIT_OK

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return worst

    total_items = 0
    counts = {PASS: 0, FAIL: 0, UNDECIDED: 0}
    print("=" * 78)
    print("S49 逻辑状态一致性 —— 逐项红绿表")
    print("=" * 78)
    for result in results:
        items = result["items"]
        total_items += len(items)
        for item in items:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        print()
        print(f"[{result['verdict']}] {result['check']}")
        for item in items:
            missing = f"  缺: {item['missing']}" if item.get("missing") else ""
            print(f"  {MARK.get(item['status'], '?')} {item['name']}{missing}")
            print(f"      依据: {item['basis']}")
            print(
                f"      原版: {item['original']}"
                f"  |  重制: {item['remake']}  |  差异: {item['delta']}"
            )
        for note in result["notes"]:
            print(f"  注: {note}")
    print()
    print("=" * 78)
    print(
        f"共 {total_items} 条：绿 {counts.get(PASS, 0)} / "
        f"红 {counts.get(FAIL, 0)} / 灰 {counts.get(UNDECIDED, 0)}"
    )
    print(f"收据目录: {RECEIPTS}")
    print(f"退出码: {worst}")
    print("=" * 78)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
