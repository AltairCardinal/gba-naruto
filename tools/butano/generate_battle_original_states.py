#!/usr/bin/env python3
"""Generate the Butano-side constants for the original's 38 battle states.

The original ROM dispatches the battle scene on a 16-bit state code, and the
reverse engineering closed all 38 non-default states of that dispatcher
(`rom-battle-controller-cfg-v1`, 65,536 input denominator, canonical mapping
SHA-256 `ce5e8ea2…`).  The remake, on the other hand, runs its own 24-value
`battle_scene_phase` enum.  Nothing connected the two, which is why the
coverage measurement could only count a family as "consumed" when a name
happened to appear in a file.

This generator closes that gap on the Butano side:

* `battle_original_state` becomes a real enum of the original's 38 state
  codes, with the 26 states whose semantics the reverse engineering named
  carrying their names and the 12 that could not be named carrying their code
  alone.  No semantics are invented for the unknown ones.
* Every remake phase is bound to the original state(s) it corresponds to,
  with the binding kind recorded: `direct` (one-to-one), `sub_phase` (the
  remake splits one original state into several phases), `remake_only` (the
  remake has a phase the original does not) or `candidate` (a correspondence
  that is not settled).

The bindings are emitted **in the order the remake enum declares its values**,
so a phase's ordinal is its row index, and a gate checks that the enum, this
table and the state table all agree.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

STATE_TABLE = ROOT / "sequel/content/battle_controller_states.json"
CONTROLLER = ROOT / "butano-sequel/game/include/konoha/battle_scene_controller.h"
HEADER = ROOT / "butano-sequel/game/include/konoha/battle_original_states.h"

#: The products this generator writes.  The provenance auditor reads this
#: constant through the abstract syntax tree instead of guessing from file
#: names, so a generator states what it owns.
GENERATED_PRODUCTS = (
    "butano-sequel/game/include/konoha/battle_original_states.h",
)

#: The reverse result this header is derived from, and the ROM bytes it
#: consumes.  The dispatcher region is the one the family's manifest
#: certifies: it holds the 16-bit state dispatch the table enumerates.
REVERSE_FAMILY = "rom-battle-controller-cfg-v1"
REVERSE_MANIFEST_SHA256 = (
    "282b4323bf965676a68b5326f2edbbdee35606b987412d351de137b82d50fe63"
)
ROM_REGION = (0x733A0, 554)
ROM_REGION_SHA256 = (
    "43fe396227bb6815aeedd5c48783effdb842194634360999d3e42f0ee316e2b1"
)

BINDING_KINDS = {
    "direct": "direct",
    "sub_phase": "sub_phase",
    "remake_only": "remake_only",
    "candidate": "candidate",
}

ENUM_RE = re.compile(
    r"enum class battle_scene_phase : std::uint8_t\s*\{(.*?)\};", re.S
)
VALUE_RE = re.compile(r"^\s*([a-z_][a-z0-9_]*)\s*,?\s*$")


class GenerationError(RuntimeError):
    """The constants could not be generated from the state table."""


def parse_enum_phases(path: Path) -> list[str]:
    """The remake phase names, in declaration order."""

    source = path.read_text(encoding="utf-8")
    match = ENUM_RE.search(source)
    if not match:
        raise GenerationError(f"no battle_scene_phase enum in {path}")
    phases: list[str] = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        value = VALUE_RE.match(stripped)
        if not value:
            continue
        phases.append(value.group(1))
    if not phases:
        raise GenerationError(f"the battle_scene_phase enum is empty in {path}")
    return phases


def state_identifier(entry: dict) -> str:
    """The C++ identifier for one original state.

    A state the reverse engineering named keeps its name.  A state it could
    not name keeps only its code: naming it would invent semantics.
    """

    name = entry.get("name")
    code = int(entry["state"])
    if name:
        return str(name)
    return f"unknown_{code:04X}"


def render(
    table: dict,
    phases: list[str],
    table_path: Path,
) -> str:
    rows = {row["remake_phase"]: row for row in table["mapping"]}
    if len(rows) != len(table["mapping"]):
        raise GenerationError("the state table has duplicate mapping rows")
    missing = [phase for phase in phases if phase not in rows]
    if missing:
        raise GenerationError(
            f"the state table does not map the remake phases {missing}"
        )
    extra = [name for name in rows if name not in phases]
    if extra:
        raise GenerationError(
            f"the state table maps phases the enum does not have: {extra}"
        )

    states = sorted(table["states"], key=lambda entry: int(entry["state"]))
    named = [entry for entry in states if entry.get("name")]
    unknown = [entry for entry in states if not entry.get("name")]

    lines: list[str] = []
    lines.append("#ifndef KONOHA_BATTLE_ORIGINAL_STATES_H")
    lines.append("#define KONOHA_BATTLE_ORIGINAL_STATES_H")
    lines.append("")
    lines.append("#include <array>")
    lines.append("#include <cstdint>")
    lines.append("")
    lines.append("namespace konoha")
    lines.append("{")
    lines.append("")
    lines.append(
        "// Generated by tools/butano/generate_battle_original_states.py. "
        "Do not edit."
    )
    lines.append("// provenance-carrier: c-header-comment")
    lines.append(
        f"// reverse-source: {REVERSE_FAMILY} @ {REVERSE_MANIFEST_SHA256}"
    )
    offset, length = ROM_REGION
    lines.append(
        f"// reverse-source-rom: 0x{offset:06X}+{length} "
        f"sha256 {ROM_REGION_SHA256}"
    )
    lines.append("//")
    lines.append(f"// Source: {table_path.relative_to(ROOT)}")
    source = table.get("source", {})
    lines.append(
        f"// Reverse result: {source.get('artifact_family', '')} "
        f"@ {source.get('artifact_manifest_sha256', '')}"
    )
    lines.append("//")
    lines.append("// The original's battle scene dispatches on a 16-bit state code.")
    lines.append("// These are its 38 non-default states.  The 12 states whose")
    lines.append("// semantics the reverse engineering could not settle keep only")
    lines.append("// their code: naming them would invent behaviour.")
    lines.append("enum class battle_original_state : std::uint16_t")
    lines.append("{")
    for entry in states:
        lines.append(
            f"    {state_identifier(entry)} = 0x{int(entry['state']):04X},"
        )
    lines.append("};")
    lines.append("")
    lines.append(
        f"inline constexpr int battle_original_state_count = {len(states)};"
    )
    lines.append(f"inline constexpr int battle_original_named_state_count = {len(named)};")
    lines.append(
        f"inline constexpr int battle_original_unknown_state_count = {len(unknown)};"
    )
    lines.append("")
    lines.append("[[nodiscard]] constexpr std::uint16_t battle_original_state_code(")
    lines.append("        battle_original_state state)")
    lines.append("{")
    lines.append("    return static_cast<std::uint16_t>(state);")
    lines.append("}")
    lines.append("")
    lines.append("// How a remake phase relates to the original state machine.")
    lines.append("enum class battle_scene_phase_binding : std::uint8_t")
    lines.append("{")
    lines.append("    // One remake phase is one original state.")
    lines.append("    direct,")
    lines.append("    // The remake splits one original state into several phases.")
    lines.append("    sub_phase,")
    lines.append("    // The remake has a phase the original does not have.")
    lines.append("    remake_only,")
    lines.append("    // A correspondence that is not settled yet.")
    lines.append("    candidate,")
    lines.append("};")
    lines.append("")
    lines.append("struct battle_scene_phase_origin")
    lines.append("{")
    lines.append("    const char* remake_phase = nullptr;")
    lines.append("    battle_scene_phase_binding binding =")
    lines.append("            battle_scene_phase_binding::direct;")
    lines.append("    // The original states this phase stands for.  A phase that")
    lines.append("    // splits one original state lists that state once; a")
    lines.append("    // phase with no counterpart lists nothing.")
    lines.append("    std::array<std::uint16_t, 4> original_states = {};")
    lines.append("    std::uint8_t original_state_count = 0;")
    lines.append("};")
    lines.append("")
    lines.append("// The bindings, in the order the remake enum declares its values,")
    lines.append("// so a phase's ordinal is its row index.")
    lines.append(
        f"inline constexpr std::array<battle_scene_phase_origin, {len(phases)}>"
    )
    lines.append("battle_scene_phase_origins = {{")
    for phase in phases:
        row = rows[phase]
        codes = row.get("original_states", [])
        kind = BINDING_KINDS.get(row.get("status", ""))
        if kind is None:
            raise GenerationError(
                f"the state table row for {phase} has an unknown status "
                f"{row.get('status')!r}"
            )
        if len(codes) > 4:
            raise GenerationError(
                f"the state table row for {phase} lists {len(codes)} states, "
                f"which does not fit the table"
            )
        values = ", ".join(codes) if codes else ""
        lines.append(
            f'    {{ "{phase}", battle_scene_phase_binding::{kind}, '
            f"{{ {values} }}, {len(codes)} }},"
        )
    lines.append("}};")
    lines.append("")
    lines.append("}")
    lines.append("")
    lines.append("#endif")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-table", type=Path, default=STATE_TABLE)
    parser.add_argument("--controller", type=Path, default=CONTROLLER)
    parser.add_argument("--out", type=Path, default=HEADER)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed header matches, without writing it",
    )
    args = parser.parse_args()

    if not args.state_table.is_file():
        print(f"error: missing {args.state_table}", file=sys.stderr)
        return 1
    table = json.loads(args.state_table.read_text(encoding="utf-8"))
    phases = parse_enum_phases(args.controller)
    text = render(table, phases, args.state_table)

    if args.check:
        if not args.out.is_file():
            print(f"error: missing {args.out}", file=sys.stderr)
            return 1
        if args.out.read_text(encoding="utf-8") != text:
            print(
                f"error: {args.out} does not match the state table",
                file=sys.stderr,
            )
            return 1
        print(f"{args.out} matches the state table")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
