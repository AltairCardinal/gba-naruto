#!/usr/bin/env python3
"""The remake's phases must stay aligned with the original's state machine.

The original ROM dispatches the battle scene on a 16-bit code, and the reverse
engineering closed all 38 non-default states of that dispatcher
(`rom-battle-controller-cfg-v1`, 65,536 input denominator, canonical mapping
SHA-256 `ce5e8ea2…`).  The remake runs its own 24-value `battle_scene_phase`
enum, and the two were not connected: nothing said which original state a
remake phase stands for, or whether a correspondence was settled at all.

This gate keeps that alignment layer honest.  It checks three things:

* the generated constants header still matches the state table, so the
  binding cannot drift from the reverse result it comes from;
* every remake phase is mapped, and the mapping's kinds say what each
  correspondence is worth (`direct`, `sub_phase`, `remake_only`, `candidate`);
* the twelve states whose semantics the reverse engineering could not settle
  keep only their code, and the runtime exposes the alignment instead of
  hiding it.

The gate fails closed: a missing state table, a missing header or a header
that does not match is an error, not a skip.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_TABLE = ROOT / "sequel/content/battle_controller_states.json"
HEADER = ROOT / "butano-sequel/game/include/konoha/battle_original_states.h"
CONTROLLER = ROOT / "butano-sequel/game/include/konoha/battle_scene_controller.h"
GENERATOR = ROOT / "tools/butano/generate_battle_original_states.py"

ENUM_RE = re.compile(
    r"enum class battle_scene_phase : std::uint8_t\s*\{(.*?)\};", re.S
)
VALUE_RE = re.compile(r"^\s*([a-z_][a-z0-9_]*)\s*,?\s*$")
IDENTIFIER_RE = re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*0x([0-9A-F]{4}),")


def enum_phases() -> list[str]:
    source = CONTROLLER.read_text(encoding="utf-8")
    match = ENUM_RE.search(source)
    if not match:
        raise AssertionError("the battle_scene_phase enum is gone")
    phases: list[str] = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        value = VALUE_RE.match(stripped)
        if value:
            phases.append(value.group(1))
    return phases


def header_states() -> dict[str, int]:
    source = HEADER.read_text(encoding="utf-8")
    match = re.search(
        r"enum class battle_original_state : std::uint16_t\s*\{(.*?)\};", source, re.S
    )
    if not match:
        raise AssertionError("the original state enum is gone")
    states: dict[str, int] = {}
    for line in match.group(1).splitlines():
        value = IDENTIFIER_RE.match(line)
        if value:
            states[value.group(1)] = int(value.group(2), 16)
    return states


def header_bindings() -> list[tuple[str, str, list[int]]]:
    source = HEADER.read_text(encoding="utf-8")
    match = re.search(
        r"battle_scene_phase_origins = \{\{(.*?)\n\}\};", source, re.S
    )
    if not match:
        raise AssertionError("the generated binding table is gone")
    rows: list[tuple[str, str, list[int]]] = []
    for line in match.group(1).splitlines():
        entry = re.match(
            r'\s*\{ "([a-z_]+)", battle_scene_phase_binding::([a-z_]+), '
            r"\{([^}]*)\}, (\d+) \},",
            line,
        )
        if not entry:
            continue
        codes = [
            int(code.strip(), 16)
            for code in entry.group(3).split(",")
            if code.strip()
        ]
        rows.append((entry.group(1), entry.group(2), codes))
    return rows


class BattleScenePhaseMappingTest(unittest.TestCase):
    def setUp(self):
        if not STATE_TABLE.is_file():
            self.skipTest("the battle controller state table is unavailable")
        self.table = json.loads(STATE_TABLE.read_text(encoding="utf-8"))

    def test_the_generated_header_matches_the_state_table(self):
        result = subprocess.run(
            [
                sys.executable,
                str(GENERATOR),
                "--state-table",
                str(STATE_TABLE),
                "--controller",
                str(CONTROLLER),
                "--out",
                str(HEADER),
                "--check",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"the generated header drifted from the state table:\n"
            f"{result.stdout}\n{result.stderr}",
        )

    def test_every_phase_is_mapped_exactly_once(self):
        phases = enum_phases()
        rows = header_bindings()
        self.assertEqual(
            [row[0] for row in rows],
            phases,
            "the binding table and the phase enum disagree on the phases or "
            "on their order",
        )
        table_phases = [row["remake_phase"] for row in self.table["mapping"]]
        self.assertEqual(
            sorted(table_phases),
            sorted(phases),
            "the state table does not map every remake phase exactly once",
        )

    def test_the_binding_kinds_say_what_each_correspondence_is_worth(self):
        kinds = {row[1] for row in header_bindings()}
        self.assertTrue(
            kinds <= {"direct", "sub_phase", "remake_only", "candidate"},
            f"unknown binding kinds: {kinds}",
        )
        remake_only = {
            row[0] for row in header_bindings() if row[1] == "remake_only"
        }
        self.assertEqual(
            remake_only,
            set(self.table["remake_only_phases"]),
            "the phases the original does not have are not the ones the "
            "state table records",
        )
        for phase, kind, codes in header_bindings():
            if kind == "remake_only":
                self.assertEqual(
                    codes, [], f"{phase} is remake only but names a state"
                )
            else:
                self.assertTrue(
                    codes, f"{phase} is bound to no original state"
                )

    def test_the_unknown_states_keep_only_their_code(self):
        states = header_states()
        table_states = {
            int(entry["state"]): entry.get("name")
            for entry in self.table["states"]
        }
        self.assertEqual(
            len(states),
            len(table_states),
            "the header and the state table disagree on the state count",
        )
        for code, name in table_states.items():
            identifier = next(
                key for key, value in states.items() if value == code
            )
            if name:
                self.assertEqual(
                    identifier,
                    name,
                    f"the state 0x{code:04X} lost its name",
                )
            else:
                self.assertEqual(
                    identifier,
                    f"unknown_{code:04X}",
                    f"the state 0x{code:04X} was given a name the reverse "
                    f"engineering did not establish",
                )

    def test_the_runtime_exposes_the_alignment(self):
        source = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn(
            "battle_original_state_code",
            source,
            "the snapshot does not expose the original state code, so the "
            "alignment cannot be observed at runtime",
        )
        self.assertIn(
            "battle_scene_phase_binding",
            source,
            "the snapshot does not expose the binding kind",
        )
        self.assertIn(
            "battle_scene_phase_origin_of",
            source,
            "the controller does not use the generated binding table",
        )

    def test_the_original_only_states_are_recorded(self):
        original_only = self.table["original_only_states"]
        self.assertTrue(
            original_only,
            "the state table no longer records the states the original has "
            "and the remake does not",
        )
        states = header_states()
        for code in original_only:
            value = int(code, 16)
            self.assertIn(
                value,
                states.values(),
                f"the original-only state {code} is not in the header",
            )


if __name__ == "__main__":
    unittest.main()
