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
                b["bank"] for b in audit["banks"]
                if b.get("verification") == "code_verified"
            ],
        }

    ob = report.get("observed_frame_phases", {})
    if isinstance(ob, dict) and "phase_verified_groups" in ob:
        all_groups = ob.get("all_groups", 18)
        phase_verified = ob.get("phase_verified_groups", 0)
        production_pixel = ob.get("production_pixel_ab_groups", 0)
        report["gap_summary"] = {
            "battle_effect_phase": f"{phase_verified}/{all_groups}",
            "battle_effect_phase_remaining_groups": sorted(
                set(range(1, all_groups + 1)) - {
                    1, 2, 3, 4, 5, 11, 14, 16, 17, 18  # from handoff 4 table
                }
            ),
            "battle_effect_production_pixel": f"{production_pixel}/{all_groups}",
            "battle_effect_production_pixel_remaining_groups": sorted(
                set(range(1, all_groups + 1)) - {
                    1, 2, 3, 4, 5, 11, 13, 14, 15, 16, 17, 18
                }
            ),
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