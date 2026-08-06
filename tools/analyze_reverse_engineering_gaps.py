#!/usr/bin/env python3
"""Analyze current reverse engineering gaps against handoff section 4 metrics.

Output JSON to stdout or to --output. Reads:
- artifacts/battle-effect-observed-frame-phases-v1/manifest.json
- artifacts/battle-effect-resource-pairs-v1/manifest.json
- notes/re-completion-audit.json
- tools/verify_battle_effect_observed_frame_phases.py (default invocation)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = args.root
    report: dict = {"schema": "reverse-engineering-gap-analysis-v1", "root": str(root)}

    try:
        result = subprocess.run(
            ["python3", "tools/verify_battle_effect_observed_frame_phases.py",
             "--root", str(root), "--artifact", "artifacts/battle-effect-observed-frame-phases-v1"],
            capture_output=True, text=True, cwd=root, timeout=30,
        )
        report["observed_frame_phases"] = json.loads(result.stdout) if result.stdout.strip().startswith("{") else {"raw": result.stdout[-2000:]}
    except Exception as exc:
        report["observed_frame_phases_error"] = str(exc)

    audit_path = root / "notes" / "re-completion-audit.json"
    if audit_path.exists():
        audit = json.loads(audit_path.read_text())
        report["bank_audit"] = {
            "total_banks": audit["summary"]["banks_found"],
            "active_banks": audit["summary"]["active_data_banks"],
            "disproved_tombstones": audit["summary"]["disproved_tombstones"],
            "verification_distribution": audit["summary"]["verification_distribution"],
            "code_verified_banks": [
                b["structure"] for b in audit["banks"]
                if b.get("verification") == "code_verified"
            ],
        }

    coverage_path = root / "artifacts" / "battle-effect-observed-frame-phases-v1" / "coverage.json"
    if coverage_path.exists():
        coverage = json.loads(coverage_path.read_text())
        all_groups = coverage.get("all_group_denominator", 18)
        phase_verified_ids = set(coverage.get("phase_verified_group_ids", []))
        production_pixel_ids = set(coverage.get("production_pixel_ab_group_ids", []))
        phase_remaining = sorted(set(range(1, all_groups + 1)) - phase_verified_ids)
        pixel_remaining = sorted(set(range(1, all_groups + 1)) - production_pixel_ids)
        report["coverage"] = coverage
        report["gap_summary"] = {
            "battle_effect_phase": f"{len(phase_verified_ids)}/{all_groups}",
            "battle_effect_phase_verified_group_ids": sorted(phase_verified_ids),
            "battle_effect_phase_remaining_groups": phase_remaining,
            "battle_effect_production_pixel": f"{len(production_pixel_ids)}/{all_groups}",
            "battle_effect_production_pixel_verified_group_ids": sorted(production_pixel_ids),
            "battle_effect_production_pixel_remaining_groups": pixel_remaining,
        }

    output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(f"gap analysis written to {args.output}")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())