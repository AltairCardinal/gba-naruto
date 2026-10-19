from pathlib import Path
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest

from tools.build_cutscene_obj_secondary_ptr_ab import build_pair
from tools.extract_tileset import lz77_decompress

ROOT = Path(__file__).resolve().parents[1]
POINTER_OFFSET = 0x53DF7C


class SecondaryPointerPairTests(unittest.TestCase):
    def test_real_pair_changes_only_record1_secondary_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve() / "build"
            manifest = build_pair(ROOT, output)
            baseline = (output / "baseline/baseline.gba").read_bytes()
            candidate = (output / "candidate/candidate.gba").read_bytes()
            before = struct.unpack_from("<I", baseline, POINTER_OFFSET)[0]
            after = struct.unpack_from("<I", candidate, POINTER_OFFSET)[0]
            self.assertNotEqual(before, after)
            changes = [i for i, (a, b) in enumerate(zip(baseline, candidate, strict=True)) if a != b]
            self.assertTrue(changes)
            self.assertTrue(all(POINTER_OFFSET <= i < POINTER_OFFSET + 4 for i in changes))
            self.assertEqual(changes, manifest["isolation"]["changed_rom_offsets"])
            self.assertEqual(len(baseline), 0x1000000)
            old = lz77_decompress(baseline, before - 0x08000000)
            new = lz77_decompress(candidate, after - 0x08000000)
            self.assertEqual((len(old), len(new)), (32, 32))
            self.assertEqual(old[:2], new[:2])
            self.assertEqual(old[4:], new[4:])
            self.assertEqual(int.from_bytes(new[2:4], "little"), int.from_bytes(old[2:4], "little") ^ 0x1F)
            self.assertEqual(baseline[after - 0x08000000:after - 0x08000000 + manifest["allocation"]["size"]], candidate[after - 0x08000000:after - 0x08000000 + manifest["allocation"]["size"]])
            self.assertEqual(manifest["edit"]["record_id"], "1")
            self.assertEqual(manifest["edit"]["field"], "secondary_ptr")
            self.assertFalse(manifest["runtime_verified"])
            for name, payload in [("baseline", baseline), ("candidate", candidate)]:
                self.assertEqual(hashlib.sha256(payload).hexdigest(), manifest["variants"][name]["rom_sha256"])
            self.assertEqual(manifest, json.loads((output / "build-manifest.json").read_text()))

    def test_nonempty_and_symlink_output_preserve_user_data(self):
        for symbolic in [False, True]:
            with self.subTest(symbolic=symbolic), tempfile.TemporaryDirectory() as directory:
                parent = Path(directory).resolve()
                target = parent / "target"
                target.mkdir()
                (target / "keep").write_text("user data")
                output = parent / "output"
                if symbolic:
                    output.symlink_to(target, target_is_directory=True)
                else:
                    output = target
                with self.assertRaises(ValueError):
                    build_pair(ROOT, output)
                self.assertEqual((target / "keep").read_text(), "user data")

    def test_cli_builds_real_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve() / "build"
            completed = subprocess.run(
                [sys.executable, "tools/build_cutscene_obj_secondary_ptr_ab.py", "--root", ".", "--output", str(output)],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout), json.loads((output / "build-manifest.json").read_text()))


if __name__ == "__main__":
    unittest.main()
