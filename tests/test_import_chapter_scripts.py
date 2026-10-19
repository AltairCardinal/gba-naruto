#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.import_chapter_scripts import resolve_chapter_script_patches


class ChapterScriptImportTests(unittest.TestCase):
    def fixture(self, *, scripts=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        spec_path = Path(tmp.name) / "chapters.json"
        spec = {
            "version": 1,
            "scripts": scripts or [{
                "id": "alternate-39",
                "table": "alternate",
                "scenario_id": 39,
                "base_script_ptr": "0x08000180",
                "commands": [
                    {"name": "set_battle", "battle_id": 40, "mode": 2},
                    {"name": "end"},
                ],
            }],
        }
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        rom = bytearray(b"\x00" * 0x400)
        pointer_offset = 0x80 + 39 * 4
        rom[pointer_offset:pointer_offset + 4] = (0x08000180).to_bytes(4, "little")
        rom[0x300:0x400] = b"\xFF" * 0x100
        return spec_path, bytes(rom), pointer_offset

    def resolve(self, spec_path, rom, *, end=0x400):
        return resolve_chapter_script_patches(
            spec_path,
            rom=rom,
            free_space_start=0x300,
            free_space_end=end,
            table_offsets={"alternate": 0x80},
        )

    def test_allocates_aligned_payload_and_guarded_pointer_as_one_plan(self):
        spec_path, rom, pointer_offset = self.fixture()
        patches = self.resolve(spec_path, rom)
        self.assertEqual([patch["type"] for patch in patches], ["bytes", "pointer_redirect"])
        self.assertEqual(patches[0]["offset"], 0x300)
        self.assertEqual(patches[0]["before_hex"], "ffffffff")
        self.assertEqual(patches[0]["after_hex"], "1a280200")
        self.assertEqual(patches[1]["pointer_table_offset"], pointer_offset)
        self.assertEqual(patches[1]["expected_pointer_hex"], "80010008")
        self.assertEqual(patches[1]["new_pointer_hex"], "00030008")

    def test_rejects_pointer_mismatch_non_ff_partition_duplicate_and_overflow(self):
        spec_path, rom, _ = self.fixture()
        bad_pointer = bytearray(rom)
        bad_pointer[0x80 + 39 * 4] ^= 1
        with self.assertRaisesRegex(ValueError, "base pointer mismatch"):
            self.resolve(spec_path, bytes(bad_pointer))

        bad_space = bytearray(rom)
        bad_space[0x350] = 0
        with self.assertRaisesRegex(ValueError, "not entirely 0xFF"):
            self.resolve(spec_path, bytes(bad_space))

        duplicate = [{
            "id": suffix,
            "table": "alternate",
            "scenario_id": 39,
            "base_script_ptr": "0x08000180",
            "commands": [{"name": "end"}],
        } for suffix in ("a", "b")]
        duplicate_path, duplicate_rom, _ = self.fixture(scripts=duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.resolve(duplicate_path, duplicate_rom)

        with self.assertRaisesRegex(ValueError, "exhausted"):
            self.resolve(spec_path, rom, end=0x302)

    def test_can_semantically_reencode_a_guarded_base_script_range(self):
        scripts = [{
            "id": "alternate-39-base-round-trip",
            "table": "alternate",
            "scenario_id": 39,
            "base_script_ptr": "0x08000180",
            "base_script_range": {"offset": "0x180", "length": 4},
        }]
        spec_path, rom, _ = self.fixture(scripts=scripts)
        base = bytearray(rom)
        base[0x180:0x184] = bytes.fromhex("1a280200")
        patches = self.resolve(spec_path, bytes(base))
        self.assertEqual(patches[0]["after_hex"], "1a280200")


if __name__ == "__main__":
    unittest.main()
