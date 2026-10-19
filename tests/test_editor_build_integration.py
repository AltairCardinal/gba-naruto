#!/usr/bin/env python3
"""Isolated editor DB -> production build integration coverage."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "web-editor" / "backend"))

import rom_models  # type: ignore  # noqa: E402
from tools import build_mod  # noqa: E402


class EditorBuildIntegrationTests(unittest.TestCase):
    def test_full_mirror_db_map_edit_builds_with_one_game_byte_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sequel" / "patches").mkdir(parents=True)
            (root / "rom").mkdir()
            (root / "web-editor").mkdir()
            (root / "web-editor" / "backend").symlink_to(
                ROOT / "web-editor" / "backend", target_is_directory=True
            )
            (root / "sequel" / "content").symlink_to(
                ROOT / "sequel" / "content", target_is_directory=True
            )
            shutil.copy2(ROOT / "rom" / "base.gba", root / "rom" / "base.gba")
            shutil.copy2(
                ROOT / "sequel" / "patches" / "manifest.json",
                root / "sequel" / "patches" / "manifest.json",
            )
            project = json.loads(
                (ROOT / "sequel" / "project.json").read_text(encoding="utf-8")
            )
            project["base_rom"]["path"] = "rom/base.gba"
            project_path = root / "sequel" / "project.json"
            project_path.write_text(json.dumps(project), encoding="utf-8")

            original_root = build_mod.ROOT
            build_mod.ROOT = root
            try:
                with patch.dict(os.environ):
                    os.environ.pop("BUILD_OUTPUT_DIR", None)
                    os.environ.pop("DB_PATH", None)
                    baseline_report = build_mod.build(project_path)
                    baseline = (
                        root / baseline_report["output_rom"]["path"]
                    ).read_bytes()

                    db_path = root / "request-editor.db"
                    conn = sqlite3.connect(db_path)
                    rom_models.init_rom_tables(conn)
                    rom_models.populate_rom_tables(conn)
                    conn.execute(
                        "UPDATE rom_map_headers SET width=32 WHERE _idx=40"
                    )
                    conn.commit()
                    conn.close()

                    os.environ["DB_PATH"] = str(db_path)
                    edited_report = build_mod.build(project_path)
                    edited = (
                        root / edited_report["output_rom"]["path"]
                    ).read_bytes()
            finally:
                build_mod.ROOT = original_root

            changed_game_offsets = [
                index
                for index, (before, after) in enumerate(zip(baseline, edited))
                if before != after and index < 0x5E0000
            ]
            self.assertEqual(changed_game_offsets, [0x53DE10])
            self.assertEqual((baseline[0x53DE10], edited[0x53DE10]), (36, 32))


if __name__ == "__main__":
    unittest.main()
