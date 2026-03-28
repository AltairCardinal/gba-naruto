#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def summarize_battle(units_path: Path, story_path: Path) -> dict:
    units = json.loads(units_path.read_text(encoding="utf-8"))
    story = json.loads(story_path.read_text(encoding="utf-8"))
    slice_spec = story.get("battle_slice", {})
    return {
        "episode_id": story["episode_id"],
        "allied_party": slice_spec.get("allied_party", []),
        "enemy_groups": slice_spec.get("enemy_groups", []),
        "unit_ids": [unit["id"] for unit in units.get("units", [])],
        "win_condition": slice_spec.get("win_condition"),
        "lose_condition": slice_spec.get("lose_condition"),
        "patch_ready": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and summarize battle config content."
    )
    parser.add_argument("--units", default="sequel/content/units/sequel-units.json")
    parser.add_argument("--story", default="sequel/content/story/episode-01.json")
    parser.add_argument("--output")
    args = parser.parse_args()

    report = summarize_battle(ROOT / args.units, ROOT / args.story)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        (ROOT / args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
