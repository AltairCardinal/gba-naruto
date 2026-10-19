import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'web-editor/backend'))

from rom_models import init_rom_tables, populate_rom_tables
from tools.build_db_patches import generate_audio_sound_id_patches


class AudioSoundIdWritebackTest(unittest.TestCase):
    def make_db(self):
        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False); tmp.close()
        path = Path(tmp.name); self.addCleanup(path.unlink, missing_ok=True)
        conn = sqlite3.connect(path); init_rom_tables(conn); populate_rom_tables(conn)
        return path, conn

    def test_refresh_preserves_edit_and_targets_exact_sparse_id(self):
        path, conn = self.make_db()
        conn.execute(
            "UPDATE rom_audio_sound_ids SET descriptor_ptr=? WHERE _idx=118",
            (0x0853D08C,),
        )
        conn.commit(); populate_rom_tables(conn); conn.close()
        patches = generate_audio_sound_id_patches(path)
        patch = next(p for p in patches if p['db_row_id'] == 118)
        self.assertEqual(patch['type'], 'bytes')
        self.assertEqual(patch['offset'], 0x465B70 + 118 * 8)
        self.assertEqual(patch['after_hex'][:8], '8cd05308')

    def test_stale_provenance_and_bad_pointer_are_rejected(self):
        path, conn = self.make_db()
        conn.execute("UPDATE rom_audio_sound_ids SET base_descriptor_ptr=1 WHERE _idx=118")
        conn.execute("UPDATE rom_audio_sound_ids SET descriptor_ptr=0x02000000 WHERE _idx=117")
        conn.commit(); conn.close()
        by_id = {p['db_row_id']: p for p in generate_audio_sound_id_patches(path)}
        self.assertIn('immutable base descriptor', by_id[118]['error'])
        self.assertIn('outside 48 Mbit ROM', by_id[117]['error'])


if __name__ == '__main__':
    unittest.main()
