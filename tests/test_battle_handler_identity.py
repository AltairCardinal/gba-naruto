import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.build_db_patches import generate_battle_handler_patches


ROOT = Path(__file__).resolve().parents[1]


class BattleHandlerIdentityTest(unittest.TestCase):
    def test_battle_handlers_bank_is_the_proved_handler_pair_table(self):
        """2026-10-22 merge: the bank got its real base.

        The old claim was "there is no battle-handler bank" -- the candidate
        base 0x53E6D8 has no native reader and is 8 records late inside the
        256-record handler-pair table at 0x53E698.  The consumer scan found
        the real base (2 native readers, 0x0807F934 / 0x0807FD28) and the
        bank now carries it -- the **same table** as ``map-events``.
        """
        old = json.loads((ROOT / "sequel/content/battle-handlers/bank.json").read_text())
        handlers = json.loads((ROOT / "sequel/content/map-events/bank.json").read_text())
        self.assertEqual(old["table_offset"], 0x53E698)
        self.assertEqual(old["entry_count"], 256)
        self.assertEqual(old["entry_size"], 8)
        self.assertEqual(old["verification"], "code_verified")
        # battle-handlers and map-events are the same table.
        self.assertEqual(handlers["table_offset"], 0x53E698)
        self.assertEqual(handlers["entry_count"], 256)
        # The legacy base stays on record as a zero-reader window, 8 records
        # late inside the same table.
        from tools import table_registry
        self.assertIn("0x53e6d8", table_registry.CONFLICTS)
        self.assertEqual(
            "repoint", table_registry.CONFLICTS["0x53e6d8"]["verdict"])

    def test_legacy_battle_handler_rows_are_diagnostic_only(self):
        """A row still pointing at the legacy base must not be written.

        The writer now targets 0x53E698 with an 8-byte record stride, so a
        row whose ``_rom_offset`` is the legacy 0x53E6D8 is rejected by the
        writer's own stale-offset guard.  The invariant is the same as
        before: **no ROM byte is written to the falsified base**.
        """
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "editor.db"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE rom_battle_handlers "
                "(_idx INTEGER, _rom_offset INTEGER, code_ptr_0 INTEGER)"
            )
            conn.execute(
                "INSERT INTO rom_battle_handlers VALUES (0, 0x53E6D8, 0x0807EFFD)"
            )
            conn.commit()
            conn.close()
            patches = generate_battle_handler_patches(db)
            self.assertFalse(any(patch["type"] == "bytes" for patch in patches))


if __name__ == "__main__":
    unittest.main()
