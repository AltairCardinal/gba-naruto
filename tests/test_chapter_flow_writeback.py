import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'web-editor/backend'))

from rom_models import init_rom_tables, populate_rom_tables
from tools.build_db_patches import generate_chapter_flow_primary_patches


class ChapterFlowWritebackTest(unittest.TestCase):
    def make_db(self):
        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False); tmp.close()
        path = Path(tmp.name); self.addCleanup(path.unlink, missing_ok=True)
        conn = sqlite3.connect(path); init_rom_tables(conn); populate_rom_tables(conn)
        return path, conn

    def test_refresh_preserves_edit_but_pointer_only_writeback_is_rejected(self):
        path, conn = self.make_db()
        conn.execute("UPDATE rom_chapter_flow_primary SET script_ptr=? WHERE _idx=39", (0x08031024,))
        conn.commit(); populate_rom_tables(conn); conn.close()
        patches = generate_chapter_flow_primary_patches(path)
        patch = next(item for item in patches if item['db_row_id'] == 39)
        self.assertEqual(patch['type'], 'db_chapter_flow_pointer_error')
        self.assertIn('semantic chapter importer', patch['error'])

    def test_stale_base_pointer_and_nonnull_sentinel_are_rejected(self):
        path, conn = self.make_db()
        conn.execute("UPDATE rom_chapter_flow_primary SET base_script_ptr=1 WHERE _idx=39")
        conn.execute("UPDATE rom_chapter_flow_primary SET script_ptr=0x08000000 WHERE _idx=0")
        conn.commit(); conn.close()
        patches = generate_chapter_flow_primary_patches(path)
        by_id = {item['db_row_id']: item for item in patches}
        self.assertIn('immutable base pointer mismatch', by_id[39]['error'])
        self.assertIn('must remain null', by_id[0]['error'])


if __name__ == '__main__':
    unittest.main()
