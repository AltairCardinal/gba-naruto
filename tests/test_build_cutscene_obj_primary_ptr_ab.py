from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BuildCutsceneObjPrimaryPtrAbTests(unittest.TestCase):
    def test_changes_only_id1_primary_pointer_between_relocated_roms(self):
        from tools.build_cutscene_obj_primary_ptr_ab import (
            AFTER_POINTER,
            BEFORE_POINTER,
            POINTER_OFFSET,
            build_pair,
        )

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "build"
            manifest = build_pair(ROOT, output)
            baseline = (output / "baseline/baseline.gba").read_bytes()
            candidate = (output / "candidate/candidate.gba").read_bytes()

            self.assertEqual("cutscene-obj-id1-primary-ptr-ab-build-v1", manifest["schema"])
            self.assertEqual(0x53DF78, POINTER_OFFSET)
            self.assertEqual(BEFORE_POINTER, struct.unpack_from("<I", baseline, POINTER_OFFSET)[0])
            self.assertEqual(AFTER_POINTER, struct.unpack_from("<I", candidate, POINTER_OFFSET)[0])
            self.assertEqual(
                [POINTER_OFFSET, POINTER_OFFSET + 1],
                [index for index, pair in enumerate(zip(baseline, candidate)) if pair[0] != pair[1]],
            )
            self.assertEqual(
                "4da5caf8e6aedf78182b13e75829931398dfb61aee7b7f5f45cd6ec324a33c16",
                hashlib.sha256(baseline).hexdigest(),
            )
            self.assertEqual(
                hashlib.sha256(candidate).hexdigest(),
                manifest["variants"]["candidate"]["rom_sha256"],
            )
            self.assertEqual(
                {
                    "offset": POINTER_OFFSET,
                    "resource_id": 1,
                    "field": "primary_ptr",
                    "before_pointer": BEFORE_POINTER,
                    "after_pointer": AFTER_POINTER,
                    "donor_resource_id": 2,
                },
                manifest["edit"],
            )
            self.assertEqual(
                manifest,
                json.loads((output / "build-manifest.json").read_text(encoding="utf-8")),
            )

    def test_rejects_nonempty_output(self):
        from tools.build_cutscene_obj_primary_ptr_ab import build_pair

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "build"
            output.mkdir()
            (output / "keep").write_text("user data", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be empty"):
                build_pair(ROOT, output)

    def test_cli_runs_from_repository_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "build"
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/build_cutscene_obj_primary_ptr_ab.py",
                    "--root",
                    ".",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertTrue((output / "build-manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
