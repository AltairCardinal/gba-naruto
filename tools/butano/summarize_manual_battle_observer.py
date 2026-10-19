#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LATEST = ROOT / "artifacts" / "manual-battle-observer-latest.txt"


def resolve_run_dir(argument: str | None) -> Path:
    if argument:
        return Path(argument).expanduser().resolve()
    if not LATEST.is_file():
        raise SystemExit(f"latest observer pointer not found: {LATEST}")
    value = LATEST.read_text(encoding="utf-8").strip()
    if not value:
        raise SystemExit(f"latest observer pointer is empty: {LATEST}")
    return Path(value).expanduser().resolve()


def load_records(trace_path: Path) -> tuple[list[dict], int]:
    records: list[dict] = []
    invalid_lines = 0
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            invalid_lines += 1
            continue
        if isinstance(record, dict):
            records.append(record)
        else:
            invalid_lines += 1
    return records, invalid_lines


def summarize(run_dir: Path) -> dict:
    trace_path = run_dir / "manual-battle-trace.jsonl"
    if not trace_path.is_file():
        raise SystemExit(f"observer trace not found: {trace_path}")
    records, invalid_lines = load_records(trace_path)
    battle_records = [record for record in records if "phase" in record]
    kinds = [record.get("kind") for record in records]
    focus_records = [
        record
        for record in records
        if record.get("kind") == "sasuke-taijutsu-focus-armed"
    ]
    presentation_records = [
        record
        for record in records
        if record.get("kind") == "presentation-start"
        or record.get("presentation_busy") == 1
    ]
    combat_stages = sorted(
        {
            int(record["presentation_combat_stage"])
            for record in presentation_records
            if isinstance(record.get("presentation_combat_stage"), int)
            and 0 <= record["presentation_combat_stage"] < 8
        }
    )
    error_records = [
        record
        for record in battle_records
        if record.get("last_control_error", 0) != 0
        or record.get("last_player_error", 0) != 0
    ]
    stalls = [
        record for record in records if record.get("kind") == "stall"
    ]
    assert_hits = [
        record for record in records if record.get("kind") == "assert-hit"
    ]
    target_confirmed = any(
        record.get("last_resolved_action_id") == 5
        or record.get("kind") == "presentation-start"
        for record in records
    )
    last = battle_records[-1] if battle_records else {}
    last_fields = (
        "observer_frame",
        "emulator_frame",
        "scenario_id",
        "battle_id",
        "phase",
        "round",
        "selected_unit",
        "selected_character_id",
        "selected_action_id",
        "last_resolved_action_id",
        "presentation_busy",
        "presentation_combat_stage",
        "presentation_combat_stage_frame",
        "render_stage",
        "last_control_error",
        "last_player_error",
        "keys",
        "pc",
        "lr",
        "sp",
    )
    return {
        "run_dir": str(run_dir),
        "trace_path": str(trace_path),
        "record_count": len(records),
        "invalid_line_count": invalid_lines,
        "first_observer_frame": (
            records[0].get("observer_frame") if records else None
        ),
        "last_observer_frame": (
            records[-1].get("observer_frame") if records else None
        ),
        "focus_armed": bool(focus_records),
        "focus_frame": (
            focus_records[0].get("observer_frame")
            if focus_records
            else None
        ),
        "target_confirmed": target_confirmed,
        "presentation_started": bool(presentation_records),
        "combat_stages": combat_stages,
        "maximum_combat_stage": (
            max(combat_stages) if combat_stages else None
        ),
        "transition_out_observed": 7 in combat_stages,
        "error_count": len(error_records),
        "stall_count": len(stalls),
        "stall_frames": [
            record.get("observer_frame") for record in stalls
        ],
        "assert_hit_count": len(assert_hits),
        "last_assert": (
            {
                field: assert_hits[-1][field]
                for field in (
                    "observer_frame",
                    "emulator_frame",
                    "pc",
                    "lr",
                    "sp",
                    "r0",
                    "r1",
                    "r2",
                    "r3",
                )
                if field in assert_hits[-1]
            }
            if assert_hits
            else None
        ),
        "kinds": sorted({kind for kind in kinds if isinstance(kind, str)}),
        "last_state": {
            field: last[field] for field in last_fields if field in last
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir")
    arguments = parser.parse_args()
    result = summarize(resolve_run_dir(arguments.run_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
