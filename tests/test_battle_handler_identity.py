import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.build_db_patches import generate_battle_handler_patches


ROOT = Path(__file__).resolve().parents[1]


class BattleHandlerIdentityTest(unittest.TestCase):
    def test_old_fourteen_entries_are_seven_pairs_from_handler_table(self):
        old = json.loads((ROOT / "sequel/content/battle-handlers/bank.json").read_text())
        handlers = json.loads((ROOT / "sequel/content/map-events/bank.json").read_text())
        flattened = []
        for pair in handlers["entries"][8:15]:
            flattened.extend((pair["primary_handler_ptr"], pair["secondary_handler_ptr"]))
        self.assertEqual([entry["handler_ptr"] for entry in old["former_entries"]], flattened)
        self.assertEqual(old["verification"], "disproved")
        self.assertEqual(old["entry_count"], 0)
        self.assertEqual(old["entries"], [])
        self.assertEqual(old["superseded_by"], "sequel/content/map-events/bank.json#entries[8:15]")
        self.assertTrue(old["do_not_write"])

    def test_legacy_battle_handler_rows_are_diagnostic_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "editor.db"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE rom_battle_handlers "
                "(_idx INTEGER, _rom_offset INTEGER, handler_ptr INTEGER)"
            )
            conn.execute(
                "INSERT INTO rom_battle_handlers VALUES (0, 0x53E6D8, 0x0807EFFD)"
            )
            conn.commit()
            conn.close()
            patches = generate_battle_handler_patches(db)
            self.assertEqual(len(patches), 1)
            self.assertEqual(patches[0]["type"], "db_battle_handler_unmapped")
            self.assertFalse(any(patch["type"] == "bytes" for patch in patches))


if __name__ == "__main__":
    unittest.main()
