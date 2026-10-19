from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

from tools.build_menu_portrait_pointer_ab import build_pair
from tools.verify_menu_portrait_pixel_ab_evidence import _catalog_contract, _portrait, _rebuild_rom
from tools.verify_cutscene_obj_primary_ptr_ab import _lz77

ROOT = Path(__file__).resolve().parents[1]


class MenuPointerPairTests(unittest.TestCase):
    def test_real_pair_isolates_gfx_pointer_without_touching_palette_or_other_records(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve() / 'build'
            manifest = build_pair(ROOT, output)
            baseline = (output / 'baseline/baseline.gba').read_bytes()
            candidate = (output / 'candidate/candidate.gba').read_bytes()
            self.assertEqual([0x5A4E14, 0x5A4E15], [i for i, (a, b) in enumerate(zip(baseline, candidate, strict=True)) if a != b])
            self.assertEqual(manifest['edit']['field'], 'gfx_ptr_0')
            self.assertEqual(manifest['edit']['record_id'], '1')
            self.assertEqual(manifest['allocation']['offset'], 0xA80D6C)
            self.assertEqual(manifest['allocation']['size'], 3306)
            self.assertEqual(manifest['edit']['before_pointer'], 0x08A80000)
            self.assertEqual(manifest['edit']['after_pointer'], 0x08A80D6C)
            before = _lz77(baseline, 0x08A80000)
            after = _lz77(candidate, 0x08A80D6C)
            self.assertEqual((len(before), len(after)), (6400, 6400))
            self.assertEqual([5184], [i for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b])
            self.assertEqual((before[5184], after[5184]), (52, 14))
            base = (ROOT / 'rom/base.gba').read_bytes()
            _, palette = _catalog_contract(ROOT, base)
            source_stream, source_palette = _portrait(ROOT / 'artifacts/menu-portraits-v1/portrait_01_variant_0.png', palette)
            parent = bytearray(_rebuild_rom(base, source_stream, source_palette))
            parent[0xA80D6C:0xA81A56] = baseline[0xA80D6C:0xA81A56]
            self.assertEqual(bytes(parent), baseline)
            self.assertEqual(candidate[0x5A4E18:0x5A4E1C], bytes.fromhex('ec0ca808'))
            self.assertEqual(baseline[0xA80CEC:0xA80D6C], palette)
            for name, rom in [('baseline', baseline), ('candidate', candidate)]:
                self.assertEqual(manifest['variants'][name]['rom_sha256'], hashlib.sha256(rom).hexdigest())
            self.assertFalse(manifest['runtime_verified'])

    def test_nonempty_and_symlink_output_are_rejected_without_changes(self):
        for symbolic in [False, True]:
            with self.subTest(symbolic=symbolic), tempfile.TemporaryDirectory() as directory:
                parent = Path(directory).resolve()
                target = parent / 'owned'
                target.mkdir()
                (target / 'keep').write_bytes(b'user')
                output = target
                if symbolic:
                    output = parent / 'link'
                    output.symlink_to(target, target_is_directory=True)
                with self.assertRaises(ValueError):
                    build_pair(ROOT, output)
                self.assertEqual({p.name for p in target.iterdir()}, {'keep'})
                self.assertEqual((target / 'keep').read_bytes(), b'user')

    def test_cli_builds_real_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve() / 'build'
            result = subprocess.run([sys.executable, 'tools/build_menu_portrait_pointer_ab.py', '--root', str(ROOT),
                                     '--output', str(output)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads(result.stdout)
            self.assertEqual(manifest, json.loads((output / 'build-manifest.json').read_text()))
            self.assertEqual(manifest['isolation']['changed_rom_offsets'], [0x5A4E14, 0x5A4E15])
            self.assertTrue((output / 'candidate/candidate.gba').is_file())


if __name__ == '__main__':
    unittest.main()
