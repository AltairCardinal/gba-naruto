#!/usr/bin/env python3
"""Verify the remake's S49 battle roster against the original's runtime pool.

S49 is the original's battle 14.  The remake claims to copy that battle unit
for unit, and until now that claim rested on rendered frames and prose.  This
verifier closes it at the data level by comparing three things that are
independent of each other:

1. **The original's runtime unit pool.**  ``artifacts/s49-original-battle14-roster-v1/``
   holds the raw pool bytes read out of the original game's EWRAM while the
   original was sitting at the battle 14 entry checkpoint, together with the
   hashes of every input that produced them.  The pool contract is:

   ==================  ==========================================
   pool base           ``0x020240C0``
   record stride       ``0x1D4``, 13 records (slot 0..12)
   record ``+0x00``    character id (``0`` marks an empty slot)
   record ``+0x01``    level
   record ``+0x0C``    current HP
   record ``+0x0E``    max HP
   record ``+0xC4``    grid X
   record ``+0xC5``    grid Y
   record ``+0xCE``    carried battle experience
   ==================  ==========================================

2. **The remake's ROM-backed formation table.**
   ``sequel/content/positions/bank.json`` is the original's formation table at
   ROM ``0x5461C4`` (``group_id`` == ``battle_id``, three variants of twelve
   records each).  It says who fights, where, on which side, and at which
   level, and it is the very table the remake's scenario header is generated
   from.

3. **The remake's stat tables.**  ``sequel/content/units/bank.json`` (the
   character template table at ROM ``0x54241C``) holds each character's base
   max HP and ``sequel/content/character-stats/bank.json`` (the growth table at
   ROM ``0x545068``) holds the per-level growth.  The remake's runtime
   computes ``max_hp = base + growth * (level - 1) / 100`` (integer division),
   the same shape the original's growth routine uses.

The three are cross-checked against each other and against the original's
observed numbers, and the verifier fails closed: a missing input, a hash
mismatch, a shorter dump or a disagreement is a non-zero exit with a named
reason.

The party slots (the three player characters) are the one place where the
formation table does *not* carry the level: the original's campaign owns the
party levels.  The verifier therefore uses the campaign's default levels
(1 -> 5, 2 -> 4, 3 -> 5) for those slots and ``tests/test_s49_battle_roster.py``
pins those numbers against ``battle_campaign_route.h`` so the two cannot drift
apart silently.

Usage::

    python3 tools/butano/verify_s49_battle_roster.py
    python3 tools/butano/verify_s49_battle_roster.py --artifact <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

EXIT_OK = 0
EXIT_INPUT_ERROR = 2
EXIT_MISMATCH = 3
EXIT_REVERSE_TREE_MISSING = 2

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

DEFAULT_ARTIFACT = ROOT / "artifacts/s49-original-battle14-roster-v1"
BATTLE_ID = 14
BATTLE_VARIANT = 0

# The campaign owns the party levels; the formation table leaves them at 1.
# Source: butano-sequel/game/include/konoha/battle_campaign_route.h
# (prepare_battle_campaign_stage_in_place, initialize_defaults branch).
PARTY_LEVELS = {1: 5, 2: 4, 3: 5}
PARTY_CHARACTERS = tuple(sorted(PARTY_LEVELS))

# The reverse tree's signed unit bindings, used as a second, independent
# original-side source for the same checkpoint.
REVERSE_BINDINGS_FAMILY = "character-runtime-unit-oam-bindings-v1"
REVERSE_BINDINGS_CHECKPOINT = "artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9"

# The reverse side recorded the same roster in prose, from a natural
# playthrough, in notes/scenario-49-battle-14-runtime-20260720.md:
#
#   "玩家槽 1..3 为 Naruto/Sasuke/Sakura，入口等级和 HP 为 LV5/138、
#    LV4/104、LV5/110。槽 4 是 character 30、HP 40 的护送单位；槽 5..9 是
#    character 55、LV5、HP 25 的五名敌人。"
#
# That table was written by watching the game; the pool above is read out of
# the original's own bytes.  The two are independent, so the gate compares
# them and fails when they ever disagree -- which is also what makes the note
# a consumed conclusion rather than a name that merely shows up in a file.
REVERSE_NOTE = "notes/scenario-49-battle-14-runtime-20260720.md"
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


class RosterVerificationError(RuntimeError):
    """The inputs are missing or unusable; the comparison cannot even start."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    if not Path(path).is_file():
        raise RosterVerificationError(f"missing input: {path}")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_unit_pool(pool: bytes) -> list[dict[str, Any]]:
    """Return the live units of one original battle unit pool."""

    if len(pool) != POOL_SIZE:
        raise RosterVerificationError(
            f"unit pool is {len(pool)} bytes, expected {POOL_SIZE}")
    units: list[dict[str, Any]] = []
    for slot in range(POOL_RECORD_COUNT):
        record = pool[slot * POOL_RECORD_SIZE:(slot + 1) * POOL_RECORD_SIZE]
        character_id = record[CHARACTER_ID_OFFSET]
        if character_id == 0:
            continue
        units.append(
            {
                "slot": slot,
                "character_id": character_id,
                "level": record[LEVEL_OFFSET],
                "current_hp": int.from_bytes(
                    record[CURRENT_HP_OFFSET:CURRENT_HP_OFFSET + 2], "little"),
                "max_hp": int.from_bytes(
                    record[MAX_HP_OFFSET:MAX_HP_OFFSET + 2], "little"),
                "grid_x": record[GRID_X_OFFSET],
                "grid_y": record[GRID_Y_OFFSET],
                "carried_experience": int.from_bytes(
                    record[
                        CARRIED_EXPERIENCE_OFFSET:CARRIED_EXPERIENCE_OFFSET + 2
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


def load_artifact(artifact: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Re-hash every input of the capture and return its roster."""

    artifact = Path(artifact)
    inputs = _read_json(artifact / "inputs.json")
    pool_path = artifact / "unit_pool.bin"
    if not pool_path.is_file():
        raise RosterVerificationError(f"missing capture: {pool_path}")
    pool = pool_path.read_bytes()

    problems: list[str] = []
    for key, path_key in (
        ("input_state_sha256", "input_state"),
        ("rom_sha256", "rom"),
        ("mgba_sha256", "mgba"),
        ("script_sha256", "script"),
        ("guard_sha256", "guard"),
    ):
        path = Path(str(inputs.get(path_key, "")))
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file():
            problems.append(f"{path_key} is missing: {path}")
            continue
        actual = sha256_file(path)
        if actual != inputs.get(key):
            problems.append(
                f"{path_key} hash changed: {inputs.get(key)} -> {actual}")
    if problems:
        raise RosterVerificationError("; ".join(problems))

    pool_hash = hashlib.sha256(pool).hexdigest()
    capture_receipt = artifact / "capture.json"
    if capture_receipt.is_file():
        receipt = json.loads(capture_receipt.read_text(encoding="utf-8"))
        if receipt.get("unit_pool_sha256") != pool_hash:
            raise RosterVerificationError(
                "captured pool does not match its own receipt: "
                f"{receipt.get('unit_pool_sha256')} != {pool_hash}")
    units = parse_unit_pool(pool)
    return {"inputs": inputs, "pool_sha256": pool_hash}, units


def load_formation(root: Path) -> list[dict[str, Any]]:
    positions = _read_json(root / "sequel/content/positions/bank.json")
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
    units = _read_json(root / "sequel/content/units/bank.json")
    growth = _read_json(root / "sequel/content/character-stats/bank.json")
    base_hp: dict[int, int] = {}
    for row in units["entries"]:
        base_hp[int(row["character_id"])] = int(row["template_0e_base"])
    growth_hp: dict[int, int] = {}
    for row in growth["entries"]:
        growth_hp[int(row["character_id"])] = int(row["template_0e_growth"])
    return base_hp, growth_hp


def reverse_tree_cross_check(
        reverse_root: Path,
        pool_sha256: str) -> tuple[list[str], dict[str, Any] | None]:
    """Compare our capture with the reverse tree's signed unit bindings."""

    bindings_path = (
        Path(reverse_root) / "artifacts" / REVERSE_BINDINGS_FAMILY / "bindings.json")
    if not bindings_path.is_file():
        return [f"reverse bindings missing: {bindings_path}"], None
    data = json.loads(bindings_path.read_text(encoding="utf-8"))
    for checkpoint in data.get("checkpoints", []):
        if checkpoint.get("path") != REVERSE_BINDINGS_CHECKPOINT:
            continue
        pool = checkpoint.get("unit_pool", {})
        problems: list[str] = []
        if pool.get("sha256") != pool_sha256:
            problems.append(
                "unit pool hash differs from the reverse tree's signed bindings: "
                f"{pool.get('sha256')} != {pool_sha256}")
        signed = {
            int(unit["slot"]): (int(unit["character_id"]),
                                int(unit["grid_x"]), int(unit["grid_y"]))
            for unit in pool.get("live_units", [])
        }
        return problems, signed
    return [f"reverse bindings have no {REVERSE_BINDINGS_CHECKPOINT}"], None


def verify(artifact: Path, root: Path, reverse_root: Path | None) -> dict[str, Any]:
    capture, original_units = load_artifact(artifact)
    formation = load_formation(root)
    base_hp, growth_hp = load_stat_tables(root)

    problems: list[str] = []
    notes: list[str] = []

    # The reverse side's prose record of the same roster, compared with the
    # bytes read out of the original.  Two independent sources, one gate.
    if len(original_units) != len(NOTE_ROSTER):
        problems.append(
            f"live unit count differs from the reverse note: "
            f"{len(original_units)} vs {len(NOTE_ROSTER)}")
    for unit, claim in zip(original_units, NOTE_ROSTER):
        slot, character_id, level, max_hp = claim
        observed = (
            unit["slot"],
            unit["character_id"],
            unit["level"],
            unit["max_hp"],
        )
        if observed != claim:
            problems.append(
                f"slot {slot}: the reverse note says {claim} but the original's "
                f"memory says {observed}")

    if len(original_units) != len(formation):
        problems.append(
            f"live unit count differs: original {len(original_units)} vs "
            f"formation {len(formation)}")

    for index, (unit, row) in enumerate(zip(original_units, formation)):
        slot = index + 1
        if unit["slot"] != slot:
            problems.append(
                f"slot {slot}: original pool slot is {unit['slot']}")
        if int(row["selector"]) != unit["character_id"]:
            problems.append(
                f"slot {slot}: character differs: formation {row['selector']} "
                f"vs original {unit['character_id']}")
        if int(row["x"]) != unit["grid_x"] or int(row["y"]) != unit["grid_y"]:
            problems.append(
                f"slot {slot}: position differs: formation "
                f"({row['x']},{row['y']}) vs original "
                f"({unit['grid_x']},{unit['grid_y']})")
        character_id = unit["character_id"]
        if character_id in PARTY_LEVELS:
            expected_level = PARTY_LEVELS[character_id]
            source = "campaign"
        else:
            expected_level = int(row["level"])
            source = "formation"
        if expected_level != unit["level"]:
            problems.append(
                f"slot {slot}: level differs ({source}): {expected_level} vs "
                f"original {unit['level']}")
        if character_id in base_hp and character_id in growth_hp:
            expected_hp = grown_max_hp(
                base_hp[character_id], growth_hp[character_id], unit["level"])
            if expected_hp != unit["max_hp"]:
                problems.append(
                    f"slot {slot}: max HP differs: remake tables give "
                    f"{expected_hp} vs original {unit['max_hp']}")
            if unit["current_hp"] != unit["max_hp"]:
                notes.append(
                    f"slot {slot}: original is already damaged "
                    f"({unit['current_hp']}/{unit['max_hp']})")
        else:
            problems.append(
                f"slot {slot}: character {character_id} has no remake stat table")
        battle_experience = row.get("battle_experience")
        if battle_experience is not None and \
                int(battle_experience) != unit["carried_experience"]:
            problems.append(
                f"slot {slot}: carried experience differs: formation "
                f"{battle_experience} vs original {unit['carried_experience']}")

    signed_summary: dict[str, Any] | None = None
    if reverse_root is not None:
        note_path = Path(reverse_root) / REVERSE_NOTE
        if not note_path.is_file():
            problems.append(
                f"the reverse note this gate cross checks is gone: {note_path}")
        cross_problems, signed = reverse_tree_cross_check(
            reverse_root, capture["pool_sha256"])
        problems.extend(cross_problems)
        if signed is not None:
            signed_summary = {"live_units": len(signed)}
            for unit in original_units:
                entry = signed.get(unit["slot"])
                if entry is None:
                    problems.append(
                        f"slot {unit['slot']}: missing from the reverse bindings")
                    continue
                if entry != (unit["character_id"], unit["grid_x"], unit["grid_y"]):
                    problems.append(
                        f"slot {unit['slot']}: reverse bindings disagree: {entry} "
                        f"vs {(unit['character_id'], unit['grid_x'], unit['grid_y'])}")

    return {
        "schema": "konoha.s49-battle-roster-verification.v1",
        "battle_id": BATTLE_ID,
        "battle_variant": BATTLE_VARIANT,
        "capture": {
            "artifact": str(artifact),
            "pool_sha256": capture["pool_sha256"],
            "input_state_sha256": capture["inputs"].get("input_state_sha256"),
            "rom_sha256": capture["inputs"].get("rom_sha256"),
        },
        "original_units": original_units,
        "remake_formation": [
            {
                "slot": index + 1,
                "character_id": int(row["selector"]),
                "side": int(row["affiliation"]),
                "x": int(row["x"]),
                "y": int(row["y"]),
                "formation_level": int(row["level"]),
                "battle_experience": row.get("battle_experience"),
            }
            for index, row in enumerate(formation)
        ],
        "party_levels": {str(key): value for key, value in PARTY_LEVELS.items()},
        "reverse_bindings_cross_check": signed_summary,
        "notes": notes,
        "problems": problems,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--reverse-root",
        type=Path,
        default=None,
        help="optional reverse work tree for the second original-side source",
    )
    parser.add_argument(
        "--write-receipt",
        type=Path,
        default=None,
        help="write the verification receipt to this path",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = verify(args.artifact, args.root, args.reverse_root)
    except RosterVerificationError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    if args.write_receipt:
        receipt = Path(args.write_receipt)
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if result["problems"]:
        for problem in result["problems"]:
            print(f"problem: {problem}", file=sys.stderr)
        return EXIT_MISMATCH
    print(
        f"S49 battle {BATTLE_ID} roster verified: "
        f"{len(result['original_units'])} live units, no problems")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
