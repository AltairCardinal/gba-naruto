#!/usr/bin/env python3
"""Join passive definitions, ROM consumers, content references and Butano coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.analyze_battle_passive_consumers import (
    build_passive_consumer_manifest,
)
from tools.analyze_battle_passive_action_modifiers import (
    build_passive_action_modifier_manifest,
)
from tools.analyze_battle_persistent_passive_stats import (
    build_persistent_passive_stat_manifest,
)
from tools.analyze_battle_passive_query import build_passive_query_manifest


INLINE_STAT_TARGETS = set(range(1, 12))
INLINE_ACTION_MODIFIER_TARGETS = set(range(13, 20))
IMPLEMENTED_GAMEPLAY_TARGETS = {
    0x0C,
    0x14,
    0x15,
    0x16,
    0x17,
    0x18,
    0x19,
    0x1D,
    0x1E,
    0x1F,
}
TERRAIN_TARGETS = {0x1A, 0x1B, 0x1C}
VISUAL_TARGETS: set[int] = set()
BATTLE_11_TARGET = 0x20
BATTLE_11_IMPLEMENTATION_MARKER = "battle_11_dual_boost"
TERRAIN_IMPLEMENTATION_MARKER = "battle_terrain_traversal_limits"
PERSISTENT_STAT_IMPLEMENTATION_MARKER = "apply_persistent_passive_stats"
ACTION_MODIFIER_IMPLEMENTATION_MARKER = (
    "apply_persistent_passive_action_modifiers"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _butano_status(
    target_type: int,
    battle_11_implemented: bool,
    terrain_implemented: bool,
    persistent_stats_implemented: bool,
    action_modifiers_implemented: bool,
) -> str:
    if target_type in INLINE_STAT_TARGETS:
        return (
            "implemented_gameplay"
            if persistent_stats_implemented
            else "withheld_gameplay"
        )
    if target_type in INLINE_ACTION_MODIFIER_TARGETS:
        return (
            "implemented_gameplay"
            if action_modifiers_implemented
            else "withheld_gameplay"
        )
    if target_type in IMPLEMENTED_GAMEPLAY_TARGETS:
        return "implemented_gameplay"
    if target_type in TERRAIN_TARGETS:
        return (
            "implemented_gameplay"
            if terrain_implemented
            else "withheld_gameplay"
        )
    if target_type in VISUAL_TARGETS:
        return "unimplemented_visual"
    if target_type == BATTLE_11_TARGET:
        return (
            "implemented_gameplay"
            if battle_11_implemented
            else "withheld_gameplay"
        )
    return "no_rom_consumer"


def build_passive_coverage_manifest(
    root_path: Path | str,
) -> dict[str, Any]:
    root = Path(root_path)
    rom_path = root / "rom/base.gba"
    catalog_path = root / "notes/battle-content-catalog-20260723.json"
    side_start_source = (
        root
        / "butano-sequel/game/include/konoha/battle_side_start_passives.h"
    )
    terrain_source = (
        root
        / "butano-sequel/game/include/konoha/battle_terrain_traversal.h"
    )
    progression_source = (
        root
        / "butano-sequel/game/include/konoha/battle_progression.h"
    )
    action_loadout_source = (
        root
        / "butano-sequel/game/include/konoha/battle_action_loadout.h"
    )

    query = build_passive_query_manifest(rom_path)
    consumers = build_passive_consumer_manifest(rom_path)
    persistent_stats = build_persistent_passive_stat_manifest(rom_path)
    action_modifiers = build_passive_action_modifier_manifest(rom_path)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_rows = {
        row["passive_id"]: row for row in catalog["passives"]
    }
    calls_by_target: dict[int, list[dict[str, str]]] = defaultdict(list)
    for call in consumers["direct_calls"]:
        calls_by_target[call["target_type"]].append(
            {
                "callsite": call["callsite"],
                "context": call["context"],
            }
        )

    battle_11_implemented = (
        BATTLE_11_IMPLEMENTATION_MARKER
        in side_start_source.read_text(encoding="utf-8")
    )
    terrain_implemented = (
        TERRAIN_IMPLEMENTATION_MARKER
        in terrain_source.read_text(encoding="utf-8")
    )
    persistent_stats_implemented = (
        PERSISTENT_STAT_IMPLEMENTATION_MARKER
        in progression_source.read_text(encoding="utf-8")
    )
    action_modifiers_implemented = (
        ACTION_MODIFIER_IMPLEMENTATION_MARKER
        in action_loadout_source.read_text(encoding="utf-8")
    )
    rows = []
    for definition in query["records"]:
        passive_id = definition["passive_id"]
        target_type = definition["target_type"]
        rom_calls = calls_by_target[target_type]
        status = _butano_status(
            target_type,
            battle_11_implemented,
            terrain_implemented,
            persistent_stats_implemented,
            action_modifiers_implemented,
        )
        inline_consumers = []
        if target_type in INLINE_STAT_TARGETS:
            inline_consumers.append(
                {
                    "function": "0x0806D964",
                    "context":
                        "persistent_character_stat_recalculation",
                    "pass_order": (
                        "percentage_and_reduction"
                        if target_type in {2, 6, 8, 11}
                        else "flat_addition"
                    ),
                }
            )
        if target_type in INLINE_ACTION_MODIFIER_TARGETS:
            inline_consumers.append(
                {
                    "function": "0x0806D6B8",
                    "context": "runtime_action_definition_modifier",
                    "pass_order": (
                        "percentage"
                        if target_type in {14, 16}
                        else "flat_addition"
                    ),
                }
            )
        if rom_calls:
            evidence_status = "rom_direct_query_consumer"
        elif target_type in INLINE_STAT_TARGETS:
            evidence_status = "rom_inline_stat_consumer"
        elif target_type in INLINE_ACTION_MODIFIER_TARGETS:
            evidence_status = (
                "rom_inline_action_modifier_consumer"
            )
        else:
            evidence_status = "no_rom_consumer"
        rows.append(
            {
                **definition,
                "referenced_by_unit_ids": catalog_rows[passive_id][
                    "referenced_by_unit_ids"
                ],
                "rom_calls": rom_calls,
                "inline_consumers": inline_consumers,
                "evidence_status": evidence_status,
                "butano_status": status,
            }
        )

    direct_query_rows = [
        row
        for row in rows
        if row["evidence_status"] == "rom_direct_query_consumer"
    ]
    inline_stat_rows = [
        row
        for row in rows
        if row["evidence_status"] == "rom_inline_stat_consumer"
    ]
    inline_action_modifier_rows = [
        row
        for row in rows
        if row["evidence_status"] ==
        "rom_inline_action_modifier_consumer"
    ]
    consumer_rows = [
        row
        for row in rows
        if row["evidence_status"] != "no_rom_consumer"
    ]
    status_counts = Counter(row["butano_status"] for row in rows)
    return {
        "schema_version": 3,
        "identity": "battle_passive_coverage",
        "rom": str(rom_path.relative_to(root)),
        "rom_sha256": query["rom_sha256"],
        "sources": {
            str(catalog_path.relative_to(root)): _sha256(catalog_path),
            str(side_start_source.relative_to(root)): _sha256(
                side_start_source
            ),
            str(terrain_source.relative_to(root)): _sha256(
                terrain_source
            ),
            str(progression_source.relative_to(root)): _sha256(
                progression_source
            ),
            str(action_loadout_source.relative_to(root)): _sha256(
                action_loadout_source
            ),
        },
        "persistent_stat_binding": persistent_stats["function"],
        "action_modifier_binding": action_modifiers["function"],
        "definition_count": len(rows),
        "rom_consumer_row_count": len(consumer_rows),
        "rom_direct_query_consumer_row_count": len(
            direct_query_rows
        ),
        "rom_inline_stat_consumer_row_count": len(
            inline_stat_rows
        ),
        "rom_inline_action_modifier_consumer_row_count": len(
            inline_action_modifier_rows
        ),
        "rom_no_consumer_row_count": len(rows) - len(consumer_rows),
        "rom_consumer_target_types": sorted(
            {row["target_type"] for row in consumer_rows}
        ),
        "rom_direct_query_consumer_target_types": sorted(
            {row["target_type"] for row in direct_query_rows}
        ),
        "rom_inline_stat_consumer_target_types": sorted(
            {row["target_type"] for row in inline_stat_rows}
        ),
        "rom_inline_action_modifier_consumer_target_types": sorted(
            {
                row["target_type"]
                for row in inline_action_modifier_rows
            }
        ),
        "butano_summary": {
            "implemented_gameplay_rows": status_counts[
                "implemented_gameplay"
            ],
            "unimplemented_visual_rows": status_counts[
                "unimplemented_visual"
            ],
            "withheld_gameplay_rows": status_counts["withheld_gameplay"],
            "no_rom_consumer_rows": status_counts[
                "no_rom_consumer"
            ],
            "unimplemented_visual_target_types": sorted(VISUAL_TARGETS),
            "terrain_traversal_target_types": sorted(TERRAIN_TARGETS),
        },
        "rows": rows,
        "boundary": (
            "A progression row is not a gameplay effect by itself. Only target "
            "types with either a verified direct query call or verified inline "
            "consumption in 0x0806D964 or 0x0806D6B8 are counted as production "
            "consumers. "
            "Targets 1-11 are inline stat consumers and do not call the generic "
            "query at 0x0806DDA4. Targets 13-19 modify per-command runtime "
            "action definitions after action-level growth or tool-template "
            "loading. Terrain targets 0x1A-0x1C are path-local "
            "traversal limits, not visual configuration."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_passive_coverage_manifest(args.root)
    text = json.dumps(
        result, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
