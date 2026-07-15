import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.build_db_patches import generate_encounter_zone_patches

ROOT = Path(__file__).resolve().parents[1]


class EncounterZoneIdentityTest(unittest.TestCase):
    def test_revoked_zone_alias_is_the_runtime_proven_map_flags_field(self):
        maps = json.loads((ROOT / "sequel/content/maps/bank.json").read_text())
        zones = json.loads((ROOT / "sequel/content/encounter-zones/bank.json").read_text())
        rom = (ROOT / "rom/base.gba").read_bytes()
        for index, entry in enumerate(maps["entries"]):
            flags = int.from_bytes(rom[0x53D910 + index * 0x20 + 0x1C:0x53D930 + index * 0x20], "little")
            self.assertEqual(entry["flags"], flags)
        self.assertEqual(zones["verification"], "disproved")
        self.assertEqual(zones["entry_count"], 0)
        self.assertEqual(zones["entries"], [])
        self.assertEqual(zones["superseded_by"], "sequel/content/maps/bank.json#flags")
        self.assertTrue(zones["do_not_write"])

    def test_legacy_editor_rows_cannot_write_the_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "editor.db"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE encounter_zones (id INTEGER, map_id INTEGER, zone_id INTEGER)")
            conn.execute("INSERT INTO encounter_zones VALUES (1, 41, 7)")
            conn.commit(); conn.close()
            patches = generate_encounter_zone_patches(db)
            self.assertEqual(len(patches), 1)
            self.assertEqual(patches[0]["type"], "db_encounter_zone_unmapped")


if __name__ == "__main__":
    unittest.main()
