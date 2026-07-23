from __future__ import annotations

import unittest
from pathlib import Path

from tools.inspect_mgba_savestate import load_gba_state
from tools.patch_mgba_savestate_memory import patch_savestate


ROOT = Path(__file__).resolve().parents[1]


class PatchMgbaSavestateMemoryTests(unittest.TestCase):
    def test_patches_requested_ewram_bytes_and_preserves_other_memory(self):
        source = ROOT / "artifacts/runtime-checkpoints/scenario-41-first-turn-technique-menu.ss9"
        original = load_gba_state(source)
        output = patch_savestate(
            source.read_bytes(),
            [(0x02026A8D, bytes.fromhex("81 81 81 81"))],
        )
        patched_path = self.enterContext(__import__("tempfile").TemporaryDirectory())
        target = Path(patched_path) / "patched.ss9"
        target.write_bytes(output)
        patched = load_gba_state(target)

        self.assertEqual(patched.read_memory(0x02026A8D, 4), bytes([0x81]) * 4)
        self.assertEqual(
            patched.read_memory(0x02026A80, 13),
            original.read_memory(0x02026A80, 13),
        )
        self.assertEqual(
            patched.read_memory(0x02026A91, 15),
            original.read_memory(0x02026A91, 15),
        )

    def test_rejects_overlapping_or_unsupported_writes(self):
        source = ROOT / "artifacts/runtime-checkpoints/scenario-41-first-turn-technique-menu.ss9"
        container = source.read_bytes()
        with self.assertRaisesRegex(ValueError, "overlap"):
            patch_savestate(container, [(0x02000010, b"ab"), (0x02000011, b"c")])
        with self.assertRaisesRegex(ValueError, "unsupported"):
            patch_savestate(container, [(0x08000000, b"x")])


if __name__ == "__main__":
    unittest.main()
