#!/usr/bin/env python3
"""The shelf families that verify file by file must be imported and stay so.

``docs/butano-wiring-roadmap.md`` (W4) asks that the closed-but-unused
families be wired in.  The pixel-A/B importer only fits families with a
baseline/candidate frame pair, so the rest need a carrier of their own: a
family whose manifest lists **every file with its SHA-256**.  Importing one is
a *content equivalence* acceptance.

These tests pin:

* every imported file matches the hash the reverse side's manifest records;
* the manifest hash matches the pin;
* the families whose own manifest disagrees with their own files are **not**
  imported -- that is a defect in the reverse side's promotion, and an
  importer that copied them would hide it.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "butano" / "import_rom_shelf_families.py"
REVERSE_ROOT = Path("/Users/altair/github/gba-naruto-reverse")
OUT_DIR = ROOT / "artifacts" / "butano-reverse-m3-import-v1" / "shelf"

sys.path.insert(0, str(ROOT))

from tools.butano.import_rom_shelf_families import (  # noqa: E402
    SHELF_FAMILIES_NOT_IMPORTED,
    SHELF_FAMILIES,
)
from tools.butano.import_rom_reverse_families import (  # noqa: E402
    as_specs,
    load_verified_manifest,
    verify_family_files,
)


class ShelfFamilyImportTest(unittest.TestCase):
    def test_every_pinned_family_verifies_file_by_file(self) -> None:
        if not REVERSE_ROOT.is_dir():
            self.skipTest("reverse work tree not present")
        for spec in as_specs(SHELF_FAMILIES):
            with self.subTest(family=spec.family):
                manifest_path, manifest = load_verified_manifest(REVERSE_ROOT, spec)
                verified = verify_family_files(manifest_path.parent, spec, manifest)
                self.assertGreater(len(verified), 0)

    def test_the_local_copies_match_the_signed_hashes(self) -> None:
        if not REVERSE_ROOT.is_dir() or not (OUT_DIR / "families.json").is_file():
            self.skipTest("no imported shelf families in this tree")
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "verify",
                    "--reverse-root",
                    str(REVERSE_ROOT),
                    "--out-dir",
                    str(OUT_DIR),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["problems"], 0)
            self.assertEqual(payload["families"], len(SHELF_FAMILIES))

    def test_the_inconsistent_families_are_not_imported(self) -> None:
        imported = {name for name, _sha in SHELF_FAMILIES}
        for family in SHELF_FAMILIES_NOT_IMPORTED:
            with self.subTest(family=family):
                self.assertNotIn(family, imported)

    def test_the_index_records_the_families_it_imported(self) -> None:
        if not (OUT_DIR / "families.json").is_file():
            self.skipTest("no imported shelf families in this tree")
        payload = json.loads((OUT_DIR / "families.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["family_count"], len(SHELF_FAMILIES))
        self.assertEqual(
            sorted(family["family"] for family in payload["families"]),
            sorted(name for name, _sha in SHELF_FAMILIES),
        )
        self.assertEqual(
            sorted(payload["not_imported_inconsistent"]),
            sorted(SHELF_FAMILIES_NOT_IMPORTED),
        )


if __name__ == "__main__":
    unittest.main()
