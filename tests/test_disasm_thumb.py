#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock


capstone = ModuleType("capstone")
capstone.CS_ARCH_ARM = 0
capstone.CS_MODE_THUMB = 0
capstone.Cs = object
with mock.patch.dict("sys.modules", {"capstone": capstone}):
    from tools.disasm_thumb import ROM_BASE, read_window


class DisasmThumbWindowTests(unittest.TestCase):
    def test_read_window_seeks_and_reads_only_the_requested_bytes(self):
        rom_path = Path("fixture.gba")
        handle = mock.MagicMock()
        handle.read.return_value = b"abcdefgh"
        context = mock.MagicMock()
        context.__enter__.return_value = handle

        with (
            mock.patch.object(
                Path, "stat", return_value=SimpleNamespace(st_size=0x20)
            ) as stat,
            mock.patch.object(Path, "open", return_value=context) as open_file,
            mock.patch.object(
                Path,
                "read_bytes",
                side_effect=AssertionError("whole-file reads are forbidden"),
            ),
        ):
            start, blob = read_window(rom_path, ROM_BASE + 10, before=4, size=8)

        self.assertEqual((start, blob), (ROM_BASE + 6, b"abcdefgh"))
        stat.assert_called_once_with()
        open_file.assert_called_once_with("rb")
        handle.seek.assert_called_once_with(6)
        handle.read.assert_called_once_with(8)

    def test_read_window_caps_read_at_end_of_rom(self):
        rom_path = Path("fixture.gba")
        handle = mock.MagicMock()
        handle.read.return_value = b"abcdef"
        context = mock.MagicMock()
        context.__enter__.return_value = handle

        with (
            mock.patch.object(Path, "stat", return_value=SimpleNamespace(st_size=0x20)),
            mock.patch.object(Path, "open", return_value=context),
        ):
            start, blob = read_window(rom_path, ROM_BASE + 30, before=4, size=8)

        self.assertEqual((start, blob), (ROM_BASE + 26, b"abcdef"))
        handle.seek.assert_called_once_with(26)
        handle.read.assert_called_once_with(6)

    def test_read_window_validates_arguments_and_mapped_focus(self):
        rom_path = Path("fixture.gba")
        with mock.patch.object(
            Path, "stat", return_value=SimpleNamespace(st_size=0x20)
        ):
            for args, message in (
                ((ROM_BASE, -1, 8), "before must be non-negative"),
                ((ROM_BASE, 0, 0), "size must be positive"),
                ((ROM_BASE - 2, 0, 8), "inside the mapped ROM"),
                ((ROM_BASE + 0x20, 0, 8), "inside the mapped ROM"),
            ):
                with self.subTest(args=args):
                    with self.assertRaisesRegex(ValueError, message):
                        read_window(rom_path, *args)


if __name__ == "__main__":
    unittest.main()
