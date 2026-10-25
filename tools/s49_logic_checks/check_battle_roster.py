#!/usr/bin/env python3
"""The S49 battlefield roster, original against remake, slot for slot.

S49 is the original's battle 14.  The claim "the remake copies the original
battle" used to rest on rendered frames; this check closes it at the data
level, on this machine, from four independent sources:

1. **The original's own memory.**  The original keeps its live units in one
   contiguous EWRAM pool::

       pool base   0x020240C0
       stride      0x1D4, 13 records (slot 0..12)
       +0x00       character id (0 marks an empty slot)
       +0x01       level
       +0x0C       current HP
       +0x0E       max HP
       +0xC4       grid X
       +0xC5       grid Y
       +0xCE       carried battle experience

   The pool is dumped again here from the same battle 14 entry savestate and
   has to be byte identical to the macOS capture
   (``artifacts/s49-original-battle14-roster-v1/unit_pool.bin``).

2. **The remake's formation table** -- ``sequel/content/positions/bank.json``
   (the original's formation table at ROM ``0x5461C4``): who fights, where,
   on which side, at which level, with how much carried experience.

3. **The remake's stat tables** -- ``sequel/content/units/bank.json`` (base
   max HP) and ``sequel/content/character-stats/bank.json`` (per level
   growth).  The remake's runtime computes
   ``max_hp = base + growth * (level - 1) / 100``, the original's growth
   shape.

4. **The reverse side's signed record** -- the battle 14 unit bindings and
   the prose runtime note, used as a second original-side source.

Usage::

    python tools/s49_logic_checks/check_battle_roster.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from s49_logic_common import (  # noqa: E402
    EXIT_INPUT_ERROR,
    EXIT_OK,
    FAIL,
    MACOS_ROSTER,
    PASS,
    REMAKE_ROOT,
    ROSTER_POOL,
    UNDECIDED,
    Check,
    CheckInputError,
    read_json,
    sha256_file,
)

#: The reverse work tree.  Read-only; it holds the signed original-side
#: bindings and the runtime note.
REVERSE_ROOT = Path(r"D:\Shell\Github\gba-naruto-reverse")

POOL_BASE = 0x020240C0
POOL_RECORD_SIZE = 0x1D4
POOL_RECORD_COUNT = 13
POOL_SIZE = POOL_RECORD_SIZE * POOL_RECORD_COUNT

CHARACTER_ID_OFFSET = 0x00
LEVEL_OFFSET = 0x01
CURRENT_HP_OFFSET = 0x0C
MAX_HP_OFFSET = 0x0E
GRID_X_OFFSET = 0xC4
GRID_Y_OFFSET = 0xC5
CARRIED_EXPERIENCE_OFFSET = 0xCE

BATTLE_ID = 14
BATTLE_VARIANT = 0

#: The campaign owns the party levels; the formation table leaves them at 1.
PARTY_LEVELS = {1: 5, 2: 4, 3: 5}

#: The reverse side's prose record of the same roster, from a natural
#: playthrough.  Independent of the bytes above, so the two are compared.
NOTE_ROSTER = (
    (1, 1, 5, 138),
    (2, 2, 4, 104),
    (3, 3, 5, 110),
    (4, 30, 3, 40),
    (5, 55, 5, 25),
    (6, 55, 5, 25),
    (7, 55, 5, 25),
    (8, 55, 5, 25),
    (9, 55, 5, 25),
)

#: Which side each original slot belongs to.  The original's pool record has
#: no side field; the side comes from the reverse side's runtime note, which
#: names slots 1..4 as the player's side and 5..9 as the bees.
ORIGINAL_SIDE = {1: 0, 2: 0, 3: 0, 4: 0, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1}


def parse_unit_pool(pool: bytes) -> list[dict[str, Any]]:
    """Return the live units of one original battle unit pool."""

    if len(pool) != POOL_SIZE:
        raise CheckInputError(
            f"unit pool is {len(pool)} bytes, expected {POOL_SIZE}"
        )
    units: list[dict[str, Any]] = []
    for slot in range(POOL_RECORD_COUNT):
        record = pool[
            slot * POOL_RECORD_SIZE:(slot + 1) * POOL_RECORD_SIZE
        ]
        character_id = record[CHARACTER_ID_OFFSET]
        if character_id == 0:
            continue
        units.append(
            {
                "slot": slot,
                "character_id": character_id,
                "level": record[LEVEL_OFFSET],
                "current_hp": int.from_bytes(
                    record[CURRENT_HP_OFFSET:CURRENT_HP_OFFSET + 2], "little"
                ),
                "max_hp": int.from_bytes(
                    record[MAX_HP_OFFSET:MAX_HP_OFFSET + 2], "little"
                ),
                "grid_x": record[GRID_X_OFFSET],
                "grid_y": record[GRID_Y_OFFSET],
                "carried_experience": int.from_bytes(
                    record[
                        CARRIED_EXPERIENCE_OFFSET:
                        CARRIED_EXPERIENCE_OFFSET + 2
                    ],
                    "little",
                ),
            }
        )
    return units


def grown_max_hp(base: int, growth: int, level: int) -> int:
    """The remake's level formula: base + growth * (level - 1) / 100."""

    normalized = level if level > 0 else 1
    return base + growth * (normalized - 1) // 100


def load_formation(root: Path) -> list[dict[str, Any]]:
    positions = read_json(root / "sequel/content/positions/bank.json")
    rows = [
        row
        for row in positions["entries"]
        if row["group_id"] == BATTLE_ID
        and row["variant_id"] == BATTLE_VARIANT
        and row.get("active")
    ]
    rows.sort(key=lambda row: row["record_id"])
    return rows


def load_stat_tables(root: Path) -> tuple[dict[int, int], dict[int, int]]:
    units = read_json(root / "sequel/content/units/bank.json")
    growth = read_json(root / "sequel/content/character-stats/bank.json")
    base_hp: dict[int, int] = {}
    growth_hp: dict[int, int] = {}
    for row in units["entries"]:
        base_hp[int(row["character_id"])] = int(row["template_0e_base"])
    for row in growth["entries"]:
        growth_hp[int(row["character_id"])] = int(row["template_0e_growth"])
    return base_hp, growth_hp


def party_levels_from_runtime(root: Path) -> dict[int, int] | None:
    """Read the party levels out of the campaign header, not out of a note."""

    route = root / "butano-sequel/game/include/konoha/battle_campaign_route.h"
    if not route.is_file():
        return None
    text = route.read_text(encoding="utf-8")
    found: dict[int, int] = {}
    for character_id, level in PARTY_LEVELS.items():
        pattern = re.compile(
            r"ensure_battle_campaign_character\(\s*"
            r"campaign,\s*" + str(character_id) + r",\s*"
            r"initialize_defaults \? " + str(level) + r" : 1"
        )
        if pattern.search(text):
            found[character_id] = level
    return found or None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remake-root", default=str(REMAKE_ROOT))
    args = parser.parse_args(argv)
    root = Path(args.remake_root).resolve()

    check = Check(
        name="battle-14-roster",
        title="battle 14 名册：原版内存 ↔ 重制侧数据表，逐槽逐字段",
        source="tools/s49_logic_checks/check_battle_roster.py",
    )

    # --- 1. the original's own memory -----------------------------------
    local_pool = ROSTER_POOL / "unit_pool.bin"
    macos_pool = MACOS_ROSTER / "unit_pool.bin"
    if not local_pool.is_file():
        check.add(
            "original-pool-capture", UNDECIDED,
            "本机没有 EWRAM 战斗单位池转储；先跑 record_evidence.py --only roster-pool",
            missing=str(local_pool),
        )
        return _finish(check)
    local_digest = sha256_file(local_pool)
    macos_digest = sha256_file(macos_pool) if macos_pool.is_file() else None
    check.add(
        "original-pool-capture",
        PASS if macos_digest == local_digest else FAIL,
        "从 battle 14 入口存档重新 dump 原版 EWRAM 单位池，与 macOS 捕获逐字节比对",
        original=f"sha256 {macos_digest[:16]}…" if macos_digest else "缺失",
        remake=f"sha256 {local_digest[:16]}…（{local_pool.stat().st_size} 字节）",
        delta="0 字节" if macos_digest == local_digest else "字节不同",
    )

    original_units = parse_unit_pool(local_pool.read_bytes())
    formation = load_formation(root)
    base_hp, growth_hp = load_stat_tables(root)

    check.add(
        "unit-count",
        PASS if len(original_units) == len(formation) == 9 else FAIL,
        "比较原版存活单位数与重制侧编队记录数",
        original=f"{len(original_units)} 个存活单位",
        remake=f"{len(formation)} 条编队记录",
        delta=0 if len(original_units) == len(formation) else "数量不同",
    )

    # --- 2. the party levels come from the campaign, not from a note -----
    runtime_levels = party_levels_from_runtime(root)
    check.add(
        "party-level-source",
        PASS if runtime_levels == PARTY_LEVELS else FAIL,
        "在 battle_campaign_route.h 里核对三个队友槽的默认等级",
        original="LV5 / LV4 / LV5（逆向侧运行时记录）",
        remake=f"{runtime_levels if runtime_levels else '未找到'}（"
               f"battle_campaign_route.h）",
        delta=0 if runtime_levels == PARTY_LEVELS else "不一致",
    )

    # --- 3. slot by slot -------------------------------------------------
    for index, unit in enumerate(original_units):
        slot = index + 1
        if index >= len(formation):
            check.add(
                f"slot-{slot}", UNDECIDED,
                "重制侧没有对应的编队记录",
                missing=f"slot {slot}",
            )
            continue
        row = formation[index]
        character_id = unit["character_id"]
        expected_level = (
            PARTY_LEVELS[character_id]
            if character_id in PARTY_LEVELS
            else int(row["level"])
        )
        expected_hp = (
            grown_max_hp(
                base_hp[character_id], growth_hp[character_id], unit["level"]
            )
            if character_id in base_hp and character_id in growth_hp
            else None
        )
        formation_experience = row.get("battle_experience")
        differences = []
        if int(row["selector"]) != character_id:
            differences.append(
                f"角色 {row['selector']} vs {character_id}"
            )
        if int(row["affiliation"]) != ORIGINAL_SIDE[slot]:
            differences.append(
                f"阵营 {row['affiliation']} vs {ORIGINAL_SIDE[slot]}"
            )
        if int(row["x"]) != unit["grid_x"] or int(row["y"]) != unit["grid_y"]:
            differences.append(
                f"坐标 ({row['x']},{row['y']}) vs "
                f"({unit['grid_x']},{unit['grid_y']})"
            )
        if expected_level != unit["level"]:
            differences.append(f"等级 {expected_level} vs {unit['level']}")
        if expected_hp is None:
            differences.append("重制侧没有该角色的属性表")
        elif expected_hp != unit["max_hp"]:
            differences.append(f"最大 HP {expected_hp} vs {unit['max_hp']}")
        if unit["current_hp"] != unit["max_hp"]:
            differences.append(
                f"原版出场即带伤 {unit['current_hp']}/{unit['max_hp']}"
            )
        if formation_experience is not None and \
                int(formation_experience) != unit["carried_experience"]:
            differences.append(
                f"携带经验 {formation_experience} vs "
                f"{unit['carried_experience']}"
            )
        check.add(
            f"slot-{slot}",
            PASS if not differences else FAIL,
            "比较该槽的角色 / 阵营 / 坐标 / 等级 / 当前与最大 HP / 携带经验",
            original=f"char {character_id} side {ORIGINAL_SIDE[slot]} "
                     f"({unit['grid_x']},{unit['grid_y']}) LV{unit['level']} "
                     f"HP {unit['current_hp']}/{unit['max_hp']} "
                     f"EXP {unit['carried_experience']}",
            remake=f"char {int(row['selector'])} side {int(row['affiliation'])} "
                   f"({int(row['x'])},{int(row['y'])}) LV{expected_level} "
                   f"maxHP {expected_hp} "
                   f"EXP {formation_experience}",
            delta="无差异" if not differences else "; ".join(differences),
        )

    # --- 4. the reverse side's two independent records -------------------
    note_units = [
        (slot, character_id, level, max_hp)
        for (slot, character_id, level, max_hp) in NOTE_ROSTER
    ]
    memory_units = [
        (unit["slot"], unit["character_id"], unit["level"], unit["max_hp"])
        for unit in original_units
    ]
    check.add(
        "reverse-note-cross-check",
        PASS if note_units == memory_units else FAIL,
        "把原版内存读出的名册与逆向侧的自然流程记录逐槽比对",
        original=f"内存 {memory_units}",
        remake=f"逆向记录 {note_units}",
        delta="一致" if note_units == memory_units else "不一致",
    )

    bindings_path = (
        REVERSE_ROOT / "artifacts" / "character-runtime-unit-oam-bindings-v1"
        / "bindings.json"
    )
    if bindings_path.is_file():
        data = json.loads(bindings_path.read_text(encoding="utf-8"))
        signed = None
        for checkpoint in data.get("checkpoints", []):
            if checkpoint.get("path") != (
                "artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9"
            ):
                continue
            signed = {
                int(unit["slot"]): (
                    int(unit["character_id"]),
                    int(unit["grid_x"]),
                    int(unit["grid_y"]),
                )
                for unit in checkpoint.get("unit_pool", {}).get("live_units", [])
            }
            pool_hash = checkpoint.get("unit_pool", {}).get("sha256")
        problems = []
        if signed is None:
            problems.append("逆向绑定里没有 battle 14 入口存档这一条")
        else:
            if pool_hash != local_digest:
                problems.append(
                    f"单位池哈希不同 {pool_hash} vs {local_digest}"
                )
            for unit in original_units:
                entry = signed.get(unit["slot"])
                if entry is None:
                    problems.append(f"槽 {unit['slot']} 不在逆向绑定里")
                elif entry != (unit["character_id"], unit["grid_x"], unit["grid_y"]):
                    problems.append(
                        f"槽 {unit['slot']} 逆向绑定 {entry} vs "
                        f"{(unit['character_id'], unit['grid_x'], unit['grid_y'])}"
                    )
        check.add(
            "reverse-bindings-cross-check",
            PASS if not problems else FAIL,
            "把本机 dump 的单位池与逆向侧签名的单位绑定（含单位池哈希）比对",
            original=f"单位池 sha256 {local_digest[:16]}…",
            remake=f"逆向绑定 {len(signed) if signed else 0} 条",
            delta="无差异" if not problems else "; ".join(problems),
        )
    else:
        check.add(
            "reverse-bindings-cross-check", UNDECIDED,
            "逆向线的签名单位绑定在本机不存在",
            missing=str(bindings_path),
        )

    # --- 5. what is still not decided ------------------------------------
    check.add(
        "remake-runtime-pool", UNDECIDED,
        "重制侧运行时单位池没有 dump：重制侧的单位结构是 C++ 结构体，"
        "布局与原版的 0x1D4 记录不同，要判定就得先定位结构体在 EWRAM 的地址",
        original="原版运行时单位池已在本机 dump 并逐字节核对",
        remake="未判定",
        delta="缺：重制侧运行时单位池的内存布局",
        missing="重制侧 battle unit 结构体在 EWRAM 中的地址与字段偏移",
    )

    return _finish(check)


def _finish(check: Check) -> int:
    path = check.write()
    print(check.render())
    print(f"\nreceipt: {path}")
    return check.exit_code()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckInputError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(EXIT_INPUT_ERROR)
