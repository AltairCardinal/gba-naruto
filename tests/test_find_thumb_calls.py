#!/usr/bin/env python3
from __future__ import annotations

import builtins
import importlib
import io
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.thumb_branch import encode_thumb_bl


ROM_BASE = 0x08000000


def import_without_capstone():
    original_import = builtins.__import__

    def reject_capstone(name, *args, **kwargs):
        if name == "capstone" or name.startswith("capstone."):
            raise ModuleNotFoundError("Capstone intentionally unavailable")
        return original_import(name, *args, **kwargs)

    sys.modules.pop("tools.find_thumb_calls", None)
    with mock.patch("builtins.__import__", side_effect=reject_capstone):
        return importlib.import_module("tools.find_thumb_calls")


class FindThumbCallsTests(unittest.TestCase):
    def test_import_does_not_require_capstone(self):
        module = import_without_capstone()
        self.assertTrue(callable(module.scan_calls))

    def test_scan_preserves_legacy_tuples_for_bl_and_unconditional_b(self):
        module = import_without_capstone()
        target = ROM_BASE + 0x0E
        blob = bytearray(16)
        blob[0:4] = encode_thumb_bl(ROM_BASE, target)
        blob[4:6] = struct.pack("<H", 0xE003)

        with tempfile.TemporaryDirectory() as temp_dir:
            rom_path = Path(temp_dir) / "fixture.gba"
            rom_path.write_bytes(blob)
            self.assertEqual(
                module.scan_calls(rom_path, target),
                [
                    (ROM_BASE, "bl", "#0x0800000e"),
                    (ROM_BASE + 4, "b", "#0x0800000e"),
                ],
            )

    def test_scan_bounds_are_exclusive_and_exclude_partial_bl(self):
        module = import_without_capstone()
        target = ROM_BASE + 0x0E
        blob = bytearray(16)
        blob[0:4] = encode_thumb_bl(ROM_BASE, target)
        blob[4:6] = struct.pack("<H", 0xE003)

        with tempfile.TemporaryDirectory() as temp_dir:
            rom_path = Path(temp_dir) / "fixture.gba"
            rom_path.write_bytes(blob)
            self.assertEqual(
                module.scan_calls(
                    rom_path,
                    target,
                    start=ROM_BASE,
                    end=ROM_BASE + 2,
                ),
                [],
            )
            self.assertEqual(
                module.scan_calls(
                    rom_path,
                    target,
                    start=ROM_BASE + 4,
                    end=ROM_BASE + 6,
                ),
                [(ROM_BASE + 4, "b", "#0x0800000e")],
            )

    def test_cli_parses_bounds_and_preserves_output_headers(self):
        module = import_without_capstone()
        argv = [
            "find_thumb_calls.py",
            "fixture.gba",
            "0x0800000E",
            "--start",
            "0x08000004",
            "--end",
            "0x08000006",
        ]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(
                module,
                "scan_calls",
                return_value=[(ROM_BASE + 4, "b", "#0x0800000e")],
            ) as scan_calls,
            mock.patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            self.assertEqual(module.main(), 0)

        scan_calls.assert_called_once_with(
            Path("fixture.gba"),
            ROM_BASE + 0x0E,
            start=ROM_BASE + 4,
            end=ROM_BASE + 6,
        )
        rendered = stdout.getvalue()
        self.assertIn("rom=fixture.gba\n", rendered)
        self.assertIn("target=0x0800000E\n", rendered)
        self.assertIn("matches=1\n", rendered)
        self.assertIn("0x08000004: b", rendered)


if __name__ == "__main__":
    unittest.main()
