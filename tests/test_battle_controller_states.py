#!/usr/bin/env python3
"""M2 gate: the original 38-state battle controller must stay bound to the remake.

The original ROM runs a 16-bit battle-scene dispatcher with 38 non-default
states.  The remake side (``battle_scene_phase``) is a self-designed 24-value
enum.  Nothing in the tree used to say which original state each remake phase
corresponds to, or which original states the remake has no counterpart for at
all.

This gate is data-driven.  Two data files carry the claims:

* ``sequel/content/battle_controller_states.json`` -- the 38 dispatcher states,
  their names (or an explicit ``unknown``), the 38<->24 mapping and the
  declared boundary.
* ``sequel/content/battle_controller_transitions.json`` -- the state
  transition table (input x RAM state -> next state + guard).

Rules this test pins down:

* the state table must contain **exactly** the 38 states of the signed
  dispatcher denominator (``rom-battle-controller-cfg-v1``), matched by
  handler entry address against the reverse work tree and against the
  reverse tree's own per-item assertion;
* every state must carry at least one evidence record whose source file is
  hash-pinned;
* a state may only be **named** if a verbatim quote from a pinned source
  supports the name.  A state whose behaviour cannot be quoted stays
  ``unknown`` with an explicit list of the evidence that is still missing --
  never a guess;
* the mapping must be symmetric: every original state and every remake phase
  appears on both sides, and the remake phases that the original does not have
  are listed as such;
* every transition must reference known states and carry a guard plus
  evidence;
* the nested dispatcher layer (``0x0809xxxx``) must be excluded explicitly.

The gate fails closed: a missing reverse-tree manifest, a missing state item
or a missing pinned source file fails the test and names the missing item.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATES = ROOT / "sequel" / "content" / "battle_controller_states.json"
TRANSITIONS = ROOT / "sequel" / "content" / "battle_controller_transitions.json"
DOC = ROOT / "docs" / "reverse-results-index" / "battle-controller-states.md"
REMAKE_HEADER = (
    ROOT
    / "butano-sequel"
    / "game"
    / "include"
    / "konoha"
    / "battle_scene_controller.h"
)

DEFAULT_REVERSE_ROOT = Path("/Users/altair/github/gba-naruto-reverse")
FAMILY = "rom-battle-controller-cfg-v1"
FAMILY_MANIFEST = "artifacts/rom-battle-controller-cfg-v1/manifest.json"
FAMILY_PAYLOAD = "artifacts/rom-battle-controller-cfg-v1/rom-battle-controller-cfg.json"
FAMILY_TEST = "tests/test_export_rom_battle_controller_cfg.py"
MAPPING_DENOMINATOR_SHA256 = (
    "ce5e8ea24e274c4456482611609ee90144d31e064fccf0d85bf8f4643f44ac15"
)
STATE_COUNT = 38
REMAKE_PHASE_COUNT = 24
ROM_BASE = 0x08000000


def _reverse_root() -> Path:
    return Path(os.environ.get("KONOHA_REVERSE_ROOT", DEFAULT_REVERSE_ROOT))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(relative: str, root: str = "reverse") -> Path:
    """Resolve a pinned source file.

    ``root == "reverse"`` reads the reverse work tree first and falls back to
    the copy mirrored into this work tree.  ``root == "local"`` pins the
    mirrored copy itself, which is used for the one note whose mirrored copy
    carries an extra section compared with the reverse work tree copy.
    """
    if root == "local":
        return ROOT / relative
    reverse = _reverse_root() / relative
    if reverse.is_file():
        return reverse
    return ROOT / relative


def _read(relative: str, root: str = "reverse") -> str:
    path = _resolve(relative, root)
    if not path.is_file():
        raise AssertionError(
            f"pinned source file is missing: {relative} "
            f"(root={root}, reverse work tree: {_reverse_root()})"
        )
    return path.read_text(encoding="utf-8", errors="replace")


def _load(path: Path) -> dict:
    if not path.is_file():
        raise AssertionError(f"required data file is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _state_hexes(payload: dict) -> list[str]:
    return [
        f"0x{state:04X}"
        for state in sorted(
            {
                int(source)
                for root in payload["roots"]
                for source in root["source_states"]
            }
        )
    ]


def _header_phase_names() -> list[str] | None:
    """Return the remake's ``battle_scene_phase`` enumerators, or None if gone."""
    if not REMAKE_HEADER.is_file():
        return None
    text = REMAKE_HEADER.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r"enum\s+class\s+battle_scene_phase[^{]*\{(?P<body>[^}]*)\}", text
    )
    if match is None:
        return None
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", match.group("body"))


class BattleControllerReverseTreeTest(unittest.TestCase):
    """The gate is fail-closed: the signed reverse work tree must be reachable."""

    def test_reverse_work_tree_and_signed_manifest_are_reachable(self) -> None:
        root = _reverse_root()
        self.assertTrue(
            root.is_dir(),
            f"the reverse work tree is missing: {root}. Point KONOHA_REVERSE_ROOT at "
            "the reverse work tree (default /Users/altair/github/gba-naruto-reverse).",
        )
        manifest = root / FAMILY_MANIFEST
        self.assertTrue(
            manifest.is_file(),
            f"the reverse work tree has no signed manifest: {manifest}",
        )
        self.assertTrue(
            (root / FAMILY_PAYLOAD).is_file(),
            f"the reverse work tree has no dispatcher payload: {root / FAMILY_PAYLOAD}",
        )


class BattleControllerStateTableTest(unittest.TestCase):
    """The 38 dispatcher states and their provenance."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.states = _load(STATES)
        cls.payload = json.loads(_read(FAMILY_PAYLOAD))
        cls.rows = cls.states["states"]

    def test_dispatcher_manifest_is_pinned_and_complete(self) -> None:
        manifest_path = _resolve(FAMILY_MANIFEST)
        self.assertTrue(
            manifest_path.is_file(),
            f"reverse work tree manifest is missing: {FAMILY_MANIFEST}",
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        dispatch = manifest["dispatch_summary"]
        self.assertEqual(dispatch["input_denominator"], 65_536)
        self.assertEqual(dispatch["nondefault_state_count"], STATE_COUNT)
        self.assertEqual(dispatch["default_state_count"], 65_498)
        self.assertEqual(
            dispatch["mapping_denominator_sha256"], MAPPING_DENOMINATOR_SHA256
        )
        self.assertEqual(
            self.states["source"]["artifact_manifest_sha256"],
            _sha256(manifest_path),
            "the state table must pin the signed manifest hash",
        )
        self.assertEqual(
            self.states["source"]["artifact_payload_sha256"],
            _sha256(_resolve(FAMILY_PAYLOAD)),
        )
        self.assertEqual(
            self.states["source"]["mapping_denominator_sha256"],
            MAPPING_DENOMINATOR_SHA256,
        )

    def test_state_table_covers_all_38_dispatch_states(self) -> None:
        expected = _state_hexes(self.payload)
        self.assertEqual(len(expected), STATE_COUNT)
        actual = [row["state_hex"] for row in self.rows]
        self.assertEqual(len(actual), STATE_COUNT)
        missing = [hex_id for hex_id in expected if hex_id not in actual]
        self.assertEqual(
            missing, [], f"state table is missing dispatcher states: {missing}"
        )
        extra = [hex_id for hex_id in actual if hex_id not in expected]
        self.assertEqual(
            extra, [], f"state table invents states the dispatcher does not have: {extra}"
        )

    def test_handler_entry_addresses_match_the_dispatcher(self) -> None:
        by_state = {row["state_hex"]: row for row in self.rows}
        for root in self.payload["roots"]:
            for source in root["source_states"]:
                hex_id = f"0x{source:04X}"
                row = by_state[hex_id]
                self.assertEqual(
                    row["entry_address"],
                    root["gba_address"],
                    f"{hex_id} handler entry address does not match the dispatcher",
                )
                self.assertEqual(
                    row["entry_sha256"],
                    root["entry_sha256"],
                    f"{hex_id} handler entry digest does not match the dispatcher",
                )

    def test_state_table_matches_the_reverse_tree_per_item_assertion(self) -> None:
        text = _read(FAMILY_TEST)
        tree = ast.parse(text)
        mappings: dict[int, int] | None = None
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            if not node.keys:
                continue
            if not all(
                isinstance(key, ast.Constant) and isinstance(key.value, int)
                for key in node.keys
            ):
                continue
            candidate = ast.literal_eval(node)
            if isinstance(candidate, dict) and 0x0000 in candidate:
                mappings = candidate
        self.assertIsNotNone(
            mappings, "no per-item mapping assertion found in the reverse tree test"
        )
        self.assertEqual(len(mappings), STATE_COUNT)
        by_state = {row["state_hex"]: row for row in self.rows}
        for state, offset in sorted(mappings.items()):
            hex_id = f"0x{state:04X}"
            self.assertIn(hex_id, by_state)
            self.assertEqual(
                by_state[hex_id]["entry_address"],
                f"0x{ROM_BASE + offset:08X}",
                f"{hex_id} entry address disagrees with the per-item assertion",
            )

    def test_every_state_carries_hash_pinned_evidence(self) -> None:
        for row in self.rows:
            hex_id = row["state_hex"]
            evidence = row.get("evidence") or []
            self.assertTrue(
                evidence, f"{hex_id} has no evidence record at all"
            )
            for record in evidence:
                self.assertIn("kind", record)
                self.assertIn("source", record)
                self.assertIn("source_root", record)
                self.assertIn("source_sha256", record)
                self.assertTrue(record["quote"].strip(), f"{hex_id} empty quote")
                path = _resolve(record["source"], record["source_root"])
                self.assertTrue(
                    path.is_file(),
                    f"{hex_id} pins a missing source file: {record['source']}",
                )
                self.assertEqual(
                    _sha256(path),
                    record["source_sha256"],
                    f"{hex_id} source hash drift: {record['source']} "
                    f"(resolved {path})",
                )

    def test_named_states_quote_their_source_verbatim(self) -> None:
        for row in self.rows:
            hex_id = row["state_hex"]
            if row["name_status"] != "named":
                self.assertIsNone(
                    row.get("name"),
                    f"{hex_id} is not named but carries a name",
                )
                self.assertTrue(
                    (row.get("missing_evidence") or "").strip(),
                    f"{hex_id} is unknown but does not say what evidence is missing",
                )
                continue
            self.assertTrue(row["name"].strip(), f"{hex_id} has an empty name")
            quote = row["quote"]
            source = row["name_source"]
            text = _read(source, row.get("name_source_root", "reverse"))
            self.assertIn(
                quote,
                text,
                f"{hex_id} name is not supported by a verbatim quote in {source}",
            )

    def test_unknown_states_are_explicitly_listed(self) -> None:
        unknown = [row["state_hex"] for row in self.rows if row["name_status"] == "unknown"]
        named = [row["state_hex"] for row in self.rows if row["name_status"] == "named"]
        self.assertEqual(len(unknown) + len(named), STATE_COUNT)
        self.assertEqual(self.states["unknown_count"], len(unknown))
        self.assertEqual(self.states["named_count"], len(named))
        self.assertEqual(
            self.states["unknown_states"],
            unknown,
            "the declared unknown list must match the rows",
        )
        for row in self.rows:
            if row["name_status"] == "unknown":
                self.assertTrue(
                    row["missing_evidence"].strip(),
                    f"{row['state_hex']} does not state the missing evidence",
                )
                self.assertNotIn(
                    "name",
                    [key for key in row if key == "name" and row[key]],
                )


class BattleControllerMappingTest(unittest.TestCase):
    """The 38 <-> 24 mapping must be symmetric and honest in both directions."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.states = _load(STATES)
        cls.rows = cls.states["states"]
        cls.mapping = cls.states["mapping"]

    def test_mapping_has_one_row_per_remake_phase(self) -> None:
        phases = [row["remake_phase"] for row in self.mapping]
        self.assertEqual(len(phases), REMAKE_PHASE_COUNT)
        self.assertEqual(len(set(phases)), REMAKE_PHASE_COUNT)

    def test_mapping_only_uses_known_original_states(self) -> None:
        known = {row["state_hex"] for row in self.rows}
        for row in self.mapping:
            for state_hex in row["original_states"]:
                self.assertIn(
                    state_hex,
                    known,
                    f"mapping row {row['remake_phase']} uses unknown state {state_hex}",
                )

    def test_mapping_is_symmetric(self) -> None:
        forward: dict[str, list[str]] = {}
        for row in self.mapping:
            for state_hex in row["original_states"]:
                forward.setdefault(state_hex, []).append(row["remake_phase"])
        for row in self.rows:
            declared = list(row.get("remake_phases") or [])
            expected = sorted(forward.get(row["state_hex"], []))
            self.assertEqual(
                sorted(declared),
                expected,
                f"{row['state_hex']} mapping is not symmetric with the mapping rows",
            )

    def test_remake_only_phases_are_declared_with_a_reason(self) -> None:
        remake_only = {row["remake_phase"] for row in self.mapping if not row["original_states"]}
        self.assertEqual(
            remake_only,
            set(self.states["remake_only_phases"]),
            "the declared remake-only set must match the mapping rows",
        )
        for row in self.mapping:
            if not row["original_states"]:
                self.assertTrue(
                    (row.get("note") or "").strip(),
                    f"remake-only phase {row['remake_phase']} must say why",
                )

    def test_original_only_states_are_declared(self) -> None:
        original_only = {
            row["state_hex"] for row in self.rows if not row.get("remake_phases")
        }
        self.assertEqual(
            original_only,
            set(self.states["original_only_states"]),
            "the declared original-only set must match the state rows",
        )

    def test_remake_phase_names_still_exist_in_the_remake_header(self) -> None:
        phases = _header_phase_names()
        if phases is None:
            self.skipTest(
                "the remake no longer declares battle_scene_phase; the mapping "
                "rows keep the historical phase names"
            )
        self.assertEqual(
            sorted(phases),
            sorted(row["remake_phase"] for row in self.mapping),
            "the mapping must cover exactly the remake's current battle phases",
        )

    def test_mapping_does_not_claim_implementation(self) -> None:
        for row in self.mapping:
            self.assertIn(
                row["status"],
                {"direct", "sub_phase", "candidate", "remake_only"},
                f"unknown mapping status on {row['remake_phase']}",
            )
        self.assertFalse(
            self.states.get("implemented", False),
            "the mapping table must not claim the remake already implements it",
        )


class BattleControllerTransitionTest(unittest.TestCase):
    """The transition table must be evidence-bound and fail closed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.states = _load(STATES)
        cls.transitions = _load(TRANSITIONS)

    def test_every_transition_uses_known_states(self) -> None:
        known = {row["state_hex"] for row in self.states["states"]}
        for row in self.transitions["transitions"]:
            for key in ("from_state", "to_state"):
                self.assertIn(
                    row[key],
                    known,
                    f"transition {row['id']} uses unknown state {row[key]}",
                )
            for alternative in row.get("to_state_alternatives") or []:
                self.assertIn(
                    alternative,
                    known,
                    f"transition {row['id']} lists unknown alternative {alternative}",
                )
                self.assertTrue(
                    (row.get("ambiguity") or "").strip(),
                    f"transition {row['id']} has an alternative but no ambiguity note",
                )

    def test_every_transition_has_a_guard_and_evidence(self) -> None:
        for row in self.transitions["transitions"]:
            self.assertTrue(
                (row.get("guard") or "").strip(),
                f"transition {row['id']} has no guard condition",
            )
            self.assertTrue(
                (row.get("input") or "").strip(),
                f"transition {row['id']} does not say which input it needs",
            )
            evidence = row.get("evidence") or []
            self.assertTrue(
                evidence, f"transition {row['id']} has no evidence record"
            )
            for record in evidence:
                path = _resolve(record["source"], record.get("source_root", "reverse"))
                self.assertTrue(
                    path.is_file(),
                    f"transition {row['id']} pins a missing source: {record['source']}",
                )
                self.assertEqual(
                    _sha256(path),
                    record["source_sha256"],
                    f"transition {row['id']} source hash drift: {record['source']}",
                )
                self.assertTrue(record["quote"].strip())

    def test_transition_quotes_are_verbatim(self) -> None:
        cache: dict[str, str] = {}
        for row in self.transitions["transitions"]:
            for record in row.get("evidence") or []:
                source = record["source"]
                root = record.get("source_root", "reverse")
                key = (source, root)
                if key not in cache:
                    cache[key] = _read(source, root)
                self.assertIn(
                    record["quote"],
                    cache[key],
                    f"transition {row['id']} quote is not verbatim in {source}",
                )

    def test_transition_count_is_consistent(self) -> None:
        self.assertEqual(
            self.transitions["transition_count"], len(self.transitions["transitions"])
        )
        ids = [row["id"] for row in self.transitions["transitions"]]
        self.assertEqual(len(set(ids)), len(ids), "transition ids must be unique")


class BattleControllerDocumentTest(unittest.TestCase):
    """The human document must not drift away from the data."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.states = _load(STATES)
        cls.transitions = _load(TRANSITIONS)
        cls.doc = DOC.read_text(encoding="utf-8") if DOC.is_file() else ""

    def test_document_exists_and_lists_every_unknown_state(self) -> None:
        self.assertTrue(DOC.is_file(), f"missing document: {DOC}")
        for row in self.states["states"]:
            if row["name_status"] != "unknown":
                continue
            self.assertIn(
                row["state_hex"],
                self.doc,
                f"the document does not list unknown state {row['state_hex']}",
            )
            self.assertIn(
                row["entry_address"],
                self.doc,
                f"the document does not list handler {row['entry_address']}",
            )

    def test_document_states_the_nested_dispatcher_boundary(self) -> None:
        self.assertIn("0x0809", self.doc)
        for payload in (self.states, self.transitions):
            boundary = (payload.get("boundary") or "")
            self.assertTrue(boundary.strip(), "the boundary must be declared")
            self.assertIn("0x0809", boundary)

    def test_family_token_is_present_for_the_gap_measurement(self) -> None:
        text = STATES.read_text(encoding="utf-8")
        self.assertIn(
            FAMILY,
            text,
            "the state table must name the reverse artifact family it consumes",
        )
        self.assertIn(FAMILY, self.states["source"]["artifact_family"])


if __name__ == "__main__":
    unittest.main()
