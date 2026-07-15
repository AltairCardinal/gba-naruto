import json
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path

from tools.build_db_patches import (
    generate_map_sprite_patches,
    generate_palette_patches,
    generate_sprite_animation_patches,
)


ROOT = Path(__file__).resolve().parents[1]


class OverlappingVisualTableIdentityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.motion = json.loads((ROOT / "sequel/content/palettes/bank.json").read_text())
        cls.pairs = json.loads((ROOT / "sequel/content/map-sprites/bank.json").read_text())
        cls.alias = json.loads((ROOT / "sequel/content/sprite-animations/bank.json").read_text())

    def test_palette_slug_is_fifteen_motion_records_through_terminal(self):
        self.assertEqual(self.motion["table_offset"], 0x53EE98)
        self.assertEqual(self.motion["entry_count"], 15)
        self.assertEqual(self.motion["entry_size"], 10)
        self.assertEqual(self.motion["verification"], "code_verified")
        for index, entry in enumerate(self.motion["entries"]):
            self.assertEqual(
                (entry["effect_id"], entry["x_offset"], entry["y_offset"],
                 entry["render_attributes"], entry["duration_control"]),
                struct.unpack_from("<5h", self.rom, 0x53EE98 + index * 10),
            )
        self.assertEqual((self.motion["entries"][-1]["effect_id"],
                          self.motion["entries"][-1]["x_offset"],
                          self.motion["entries"][-1]["y_offset"],
                          self.motion["entries"][-1]["render_attributes"],
                          self.motion["entries"][-1]["duration_control"]),
                         (-1, 0, 0, 0, 0))

    def test_map_sprite_slug_is_full_forty_three_pair_table(self):
        self.assertEqual(self.pairs["table_offset"], 0x53F140)
        self.assertEqual(self.pairs["entry_count"], 43)
        self.assertEqual(self.pairs["entry_size"], 8)
        self.assertEqual(self.pairs["verification"], "code_verified")
        for index, entry in enumerate(self.pairs["entries"]):
            self.assertEqual(
                (entry["definition_ptr"], entry["animation_ptr"]),
                struct.unpack_from("<II", self.rom, 0x53F140 + index * 8),
            )

    def test_old_sprite_animation_bank_is_exact_pair_subset(self):
        flattened = []
        for pair in self.pairs["entries"][24:43]:
            flattened.extend((pair["definition_ptr"], pair["animation_ptr"]))
        former_words = list(struct.unpack_from("<38I", self.rom, 0x53F200))
        self.assertEqual(former_words, flattened)
        self.assertEqual(self.alias["verification"], "disproved")
        self.assertEqual(self.alias["entries"], [])
        self.assertEqual(self.alias["superseded_by"],
                         "sequel/content/map-sprites/bank.json#entries[24:43]")
        self.assertTrue(self.alias["do_not_write"])

    def test_consumers_pin_stride_literals_and_pair_install(self):
        for literal in (0x80744, 0x807F0, 0x80898):
            self.assertEqual(struct.unpack_from("<I", self.rom, literal)[0], 0x0853EE98)
        self.assertEqual(self.rom[0x806B2:0x806BE].hex(), "116888004018400022494418")
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x80B54)[0], 0x0853F140)
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x80B5C)[0], 0x0853F298)
        self.assertEqual(self.rom[0x62668:0x62676].hex(),
                         "f800009940180168e16140682062")

    def test_all_three_legacy_editor_shapes_are_diagnostic_only(self):
        schemas = (
            ("rom_palettes", "palette_ptr", 0x53F138, generate_palette_patches,
             "db_palette_unmapped"),
            ("rom_map_sprites", "sprite_ptr", 0x53F1DC, generate_map_sprite_patches,
             "db_map_sprite_unmapped"),
            ("rom_sprite_animations", "anim_ptr", 0x53F200,
             generate_sprite_animation_patches, "db_sprite_animation_unmapped"),
        )
        for table, column, offset, generator, expected_type in schemas:
            with self.subTest(table=table), tempfile.TemporaryDirectory() as tmp:
                db = Path(tmp) / "editor.db"
                conn = sqlite3.connect(db)
                conn.execute(
                    f'CREATE TABLE "{table}" '
                    f'(_idx INTEGER, _rom_offset INTEGER, "{column}" INTEGER)'
                )
                conn.execute(f'INSERT INTO "{table}" VALUES (0, ?, 0x0812F5B0)',
                             (offset,))
                conn.commit()
                conn.close()
                patches = generator(db)
                self.assertEqual(len(patches), 1)
                self.assertEqual(patches[0]["type"], expected_type)
                self.assertFalse(any(patch["type"] == "bytes" for patch in patches))


if __name__ == "__main__":
    unittest.main()
