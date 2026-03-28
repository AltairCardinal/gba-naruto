#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def summarize_map(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "map_id": data["map_id"],
        "status": data["status"],
        "reference": data.get("reference"),
        "layout_notes": data.get("layout_notes", []),
        "reverse_engineering_dependency": data.get(
            "reverse_engineering_dependency", []
        ),
        "patch_ready": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and summarize sequel map content."
    )
    parser.add_argument("map_spec")
    parser.add_argument("--output")
    args = parser.parse_args()

    report = summarize_map(ROOT / args.map_spec)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        (ROOT / args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
