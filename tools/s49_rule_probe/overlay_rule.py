#!/usr/bin/env python3
"""The original game's BG2 overlay rule.

Answer to the open question ("可达范围高亮 or 不可达范围压暗?"):
**the lit cells are the reachable-range highlight, not an unreachable dim.**

How that is established (see notes/s49-fidelity/F-rule.md for the evidence):

* the original's overlay palette (bank 12) is *bit-identical* to the remake's
  palette slots 225..235, and the remake's slots are already named:
  225 grid_secondary, 226 move_primary, 227 move_secondary,
  228 attack_primary, 229 attack_secondary, 230/231 cursor,
  232/233 target, 234/235 blocked;
* the overlay tile art matches those roles exactly:

      family     tiles      pixels drawn                 role
      blank      256,257    nothing (palette index 0)    outside the battlefield
      edge       258..261   1 px slate cell-border lines  walkable, not highlighted
      hatch      262..265   solid bright-cyan fill        **move (reachable) range**
      line_alt   266..269   solid orange fill             **attack range / move destination**
      band       270..273   solid yellow fill             **cursor cell**
      solid      278..281   50 % grey dither              **blocked cell**

* the cyan range moves with the cursor (field -> movegrid turns exactly the
  previous range back into plain lattice and paints a new one) while the
  blocked set stays put.

The executable criterion
------------------------

For every 16x16 px logical cell of the battlefield the original paints exactly
one family, chosen by this priority::

    cursor (band)  >  attack range (line_alt)  >  move range (hatch)
                  >  blocked (solid)           >  walkable (edge)
                  >  outside the battlefield (blank)

The state a caller must supply is therefore five cell sets::

    extent        cells that belong to the battlefield at all
    blocked       cells that cannot be entered (terrain / occupied by a unit)
    move_range    cells the selected unit can reach
    attack_range  cells the selected unit can hit (and the move destination)
    cursor        the cursor cell

which is exactly "unit cell coordinates + terrain attributes", resolved by the
game's own distance field.
"""

from __future__ import annotations

import dataclasses
from typing import Iterable, Mapping

from overlay_ground_truth import (
    FAMILY_ROLE,
    LOGICAL_COLS,
    LOGICAL_ROWS,
    MOMENTS,
    Moment,
    load_all,
    load_palette,
    load_tiles,
    tile_family,
)

# --- family <-> role -------------------------------------------------------

#: role -> family, in painting priority (highest first)
ROLE_PRIORITY: tuple[str, ...] = (
    "cursor",
    "target",
    "attack_range",
    "move_range",
    "blocked",
    "walkable",
    "nothing",
)

#: role -> family
ROLE_FAMILY: Mapping[str, str] = {
    "cursor": "band",
    "target": "hatch_shift",
    "attack_range": "line_alt",
    "move_range": "hatch",
    "blocked": "solid",
    "walkable": "edge",
    "nothing": "blank",
}

#: family -> role (the inverse of ROLE_FAMILY, plus the exporter's own names)
FAMILY_TO_ROLE: Mapping[str, str] = {
    "band": "cursor",
    "hatch_shift": "target",
    "line_alt": "attack_range",
    "hatch": "move_range",
    "solid": "blocked",
    "edge": "walkable",
    "blank": "nothing",
}

#: The original's bank-12 palette index each family paints (bank 12 == the
#: remake's palette slots 225..235 with slot = 224 + index; index 0 is the
#: transparent "nothing" colour, so the remake's 225 == bank-12 index 1).
FAMILY_PALETTE_INDEX: Mapping[str, tuple[int, ...]] = {
    "blank": (0,),
    "edge": (1,),
    "hatch": (2, 3),
    "line_alt": (4, 5),
    "band": (6, 7),
    "hatch_shift": (8, 9),
    "solid": (10, 11),
}

#: The transparent palette index (nothing is painted there).
TRANSPARENT_INDEX = 0

#: The remake's own role names (battle_range_ui_tile_kind) for each family.
FAMILY_REMAKE_ROLE: Mapping[str, str] = {
    "blank": "grid (nothing)",
    "edge": "grid",
    "hatch": "move",
    "line_alt": "attack_range",
    "band": "cursor",
    "hatch_shift": "target",
    "solid": "blocked",
}


@dataclasses.dataclass(frozen=True)
class OverlayState:
    """The semantic state the original's overlay is a function of."""

    extent: frozenset[tuple[int, int]] = frozenset()
    blocked: frozenset[tuple[int, int]] = frozenset()
    move_range: frozenset[tuple[int, int]] = frozenset()
    attack_range: frozenset[tuple[int, int]] = frozenset()
    cursor: frozenset[tuple[int, int]] = frozenset()
    target: frozenset[tuple[int, int]] = frozenset()

    @staticmethod
    def build(*, extent=None, blocked=None, move_range=None, attack_range=None,
              cursor=None, target=None) -> "OverlayState":
        def freeze(value):
            if value is None:
                return frozenset()
            if isinstance(value, frozenset):
                return value
            return frozenset(tuple(cell) for cell in value)

        return OverlayState(
            extent=freeze(extent),
            blocked=freeze(blocked),
            move_range=freeze(move_range),
            attack_range=freeze(attack_range),
            cursor=freeze(cursor),
            target=freeze(target),
        )


def cell_family(state: OverlayState, x: int, y: int) -> str:
    """The family the original paints at logical cell (x, y)."""
    cell = (x, y)
    if cell in state.cursor:
        return ROLE_FAMILY["cursor"]
    if cell in state.target:
        return ROLE_FAMILY["target"]
    if cell in state.attack_range:
        return ROLE_FAMILY["attack_range"]
    if cell in state.move_range:
        return ROLE_FAMILY["move_range"]
    if cell in state.blocked:
        return ROLE_FAMILY["blocked"]
    if cell in state.extent:
        return ROLE_FAMILY["walkable"]
    return ROLE_FAMILY["nothing"]


def predict(state: OverlayState) -> dict[tuple[int, int], str]:
    """The whole 16x16 logical overlay."""
    return {
        (x, y): cell_family(state, x, y)
        for y in range(LOGICAL_ROWS)
        for x in range(LOGICAL_COLS)
    }


def lit_cells(families: Mapping[tuple[int, int], str]) -> set[tuple[int, int]]:
    """The cells that paint at least one non-blank tile."""
    return {cell for cell, family in families.items() if family != "blank"}


# --- extracting the state from an observed overlay -------------------------

def roles_from_families(
        families: Mapping[tuple[int, int], str]) -> OverlayState:
    """Recover the five role sets from an observed per-cell family map.

    This is the *inverse* of :func:`predict`; it is used to turn the
    original's own tilemap into the state the rule consumes, and to check that
    the priority order above is consistent with what the original drew.
    """
    sets: dict[str, set[tuple[int, int]]] = {
        "cursor": set(), "target": set(), "attack_range": set(),
        "move_range": set(), "blocked": set(), "walkable": set(), "nothing": set(),
    }
    for cell, family in families.items():
        sets[FAMILY_TO_ROLE[family]].add(cell)
    return OverlayState.build(
        extent=frozenset(sets["walkable"] | sets["cursor"] | sets["target"]
                         | sets["attack_range"] | sets["move_range"]
                         | sets["blocked"]),
        blocked=frozenset(sets["blocked"]),
        move_range=frozenset(sets["move_range"]),
        attack_range=frozenset(sets["attack_range"]),
        cursor=frozenset(sets["cursor"]),
        target=frozenset(sets["target"]),
    )


def moment_families(moment: Moment) -> dict[tuple[int, int], str]:
    return {
        (x, y): moment.cell_family(x, y)
        for y in range(LOGICAL_ROWS)
        for x in range(LOGICAL_COLS)
    }


def moment_state(moment: Moment) -> OverlayState:
    return roles_from_families(moment_families(moment))


# --- palette cross-check ----------------------------------------------------

def palette_cross_check() -> dict[str, object]:
    """Prove that bank 12 index i == the remake's palette slot 225+i.

    The remake's role colours are read from its own product header
    (``battle_range_ui_style.h``); the original's are read from the exported
    bank-12 palette.  The claim is that they are equal entry by entry.
    """
    original = load_palette()
    remake_header = (
        r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha"
        r"\battle_range_ui_style.h"
    )
    import re
    text = pathlib_read(remake_header)
    entries: dict[int, tuple[int, int, int]] = {}
    for name, r5, g5, b5 in re.findall(
            r"battle_range_ui_(\w+)_color\s*=\s*\{\s*"
            r"(\d+),\s*(\d+),\s*(\d+),\s*\}", text):
        entries[name] = (int(r5), int(g5), int(b5))
    slots = {
        "grid_secondary": 225, "move_primary": 226, "move_secondary": 227,
        "attack_primary": 228, "attack_secondary": 229,
        "cursor_primary": 230, "cursor_secondary": 231,
        "target_primary": 232, "target_secondary": 233,
        "blocked_primary": 234, "blocked_secondary": 235,
    }
    rows = []
    for name, slot in slots.items():
        if name not in entries:
            continue
        r5, g5, b5 = entries[name]
        rgb8 = ((r5 << 3) | (r5 >> 2), (g5 << 3) | (g5 >> 2), (b5 << 3) | (b5 >> 2))
        # bank-12 index 0 is the transparent "nothing" colour, so the remake's
        # slot 225 (grid_secondary) is bank-12 index 1.
        original_index = slot - 224
        rows.append({
            "role": name,
            "remake_slot": slot,
            "original_bank12_index": original_index,
            "remake_rgb8": list(rgb8),
            "original_rgb8": list(original[original_index]),
            "equal": list(rgb8) == list(original[original_index]),
        })
    return {
        "rows": rows,
        "all_equal": all(row["equal"] for row in rows),
        "family_palette_index": {k: list(v) for k, v in FAMILY_PALETTE_INDEX.items()},
    }


def pathlib_read(path: str) -> str:
    import pathlib
    return pathlib.Path(path).read_text(encoding="utf-8")


def tile_family_summary() -> dict[str, object]:
    """What each of the 32 overlay tiles actually paints."""
    tiles = load_tiles()
    out: dict[str, object] = {}
    for index in range(256, 288):
        rows = tiles.get(index)
        if rows is None:
            continue
        colours = sorted({value for row in rows for value in row})
        out[str(index)] = {
            "family": tile_family(index),
            "colours": colours,
            "role": FAMILY_REMAKE_ROLE.get(tile_family(index), "?"),
        }
    return out


def main() -> int:
    import json
    check = palette_cross_check()
    print("=== palette identity: original bank 12 == remake slots 225..235 ===")
    for row in check["rows"]:
        print(f"  {row['role']:<18} slot {row['remake_slot']} / bank12 "
              f"{row['original_bank12_index']:>2}  {row['original_rgb8']} "
              f"{'==' if row['equal'] else '!='} {row['remake_rgb8']}")
    print(f"  all equal: {check['all_equal']}")
    print()
    print("=== the 32 overlay tiles ===")
    summary = tile_family_summary()
    for index, info in summary.items():
        if info["family"] == "blank" and info["colours"] == [0]:
            continue
        print(f"  tile {index:>3}: family {info['family']:<9} role "
              f"{info['role']:<16} colours {info['colours']}")
    print()
    print("=== role priority ===")
    for role in ROLE_PRIORITY:
        print(f"  {role:<14} -> family {ROLE_FAMILY[role]:<9} "
              f"(role name in the remake: {FAMILY_REMAKE_ROLE[ROLE_FAMILY[role]]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
