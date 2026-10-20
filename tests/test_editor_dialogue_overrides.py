#!/usr/bin/env python3
"""The editor -> build dialogue override chain must actually connect.

`sequel/editor.db` is gitignored, so the chain used to be exercised against
a file that does not exist in a clean checkout -- and against the *wrong*
key space besides: editor.db's `dialogues.key` is a `dialogue-bank-full.json`
slot (``group0``) while the write-back bank uses ``group0.main``.  The naive
key comparison therefore produced zero overrides even with a fully populated
database.

These tests build a synthetic editor.db and assert that:

  * an untouched seed row does NOT become an override (the seed comes from
    the dev ROM and does not match ``rom/base.gba``), and
  * a row the author actually edited DOES become an override, keyed by the
    entry id the content file uses.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.build_db_patches import generate_editor_dialogue_overrides

REPO = Path(__file__).resolve().parents[1]
CONTENT = REPO / "sequel" / "content" / "text"


class EditorDialogueOverrideTests(unittest.TestCase):
    def make_db(self, rows: list[tuple[str, str, str | None]]) -> Path:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        path = Path(tmp.name)
        conn = sqlite3.connect(path)
        conn.execute(
            "CREATE TABLE dialogues (key TEXT PRIMARY KEY, speaker TEXT, "
            "text_ja TEXT, text_zh TEXT, byte_count INTEGER, max_bytes INTEGER)"
        )
        conn.executemany(
            "INSERT INTO dialogues (key, speaker, text_ja, text_zh, byte_count, "
            "max_bytes) VALUES (?, NULL, ?, ?, 0, 0)",
            rows,
        )
        conn.commit()
        conn.close()
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def seed_text(self, slot: str) -> str:
        full = json.loads((CONTENT / "dialogue-bank-full.json").read_text(
            encoding="utf-8"))
        for entry in full:
            if entry.get("slot") == slot and not entry.get("empty"):
                return entry.get("text_ja") or entry.get("text_zh") or ""
        self.fail(f"slot {slot} not found in dialogue-bank-full.json")

    def test_untouched_seed_row_is_not_an_override(self):
        seed = self.seed_text("group0")
        db = self.make_db([("group0", seed, None)])
        self.assertEqual(generate_editor_dialogue_overrides(db), {})

    def test_author_edit_becomes_an_override_keyed_by_the_bank_entry_id(self):
        seed = self.seed_text("group0")
        db = self.make_db([("group0", "作者改写的台词", None)])
        overrides = generate_editor_dialogue_overrides(db)
        self.assertEqual(overrides, {"group0.main": "作者改写的台词"})
        self.assertNotEqual(seed, "作者改写的台词")

    def test_unknown_slot_is_ignored(self):
        db = self.make_db([("not-a-slot", "随便什么", None)])
        self.assertEqual(generate_editor_dialogue_overrides(db), {})


if __name__ == "__main__":
    unittest.main()
