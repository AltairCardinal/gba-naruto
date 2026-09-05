"""A checkout must restore exact legacy inputs without replacing existing files."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tools import prepare_rom_verifier_contracts as preparer

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/prepare_rom_verifier_contracts.py'
DATA = Path('tools/data/rom-verifier-contracts-v1')
NAMES = ('cgbsound', 'cgb-helper', 'mp2k-dispatcher')
CONSUMERS = ('verify_rom_cgbsound_bounded_cfg.py',
             'verify_rom_cgb_helper_bounded_cfg.py', 'verify_rom_mp2k_dispatcher.py')


class VerifierContractRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'checkout'
        (self.root / DATA).mkdir(parents=True)
        self.targets = []
        for name, consumer in zip(NAMES, CONSUMERS):
            shutil.copyfile(ROOT / DATA / (name + '.json'), self.root / DATA / (name + '.json'))
            shutil.copyfile(ROOT / 'tools' / consumer, self.root / 'tools' / consumer)
            self.targets.append(self.root / f'build/experiments/active/{name}-contract/codex-r1-20260829/CONTRACT.json')

    def run_cli(self, *, restore=False):
        return subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root),
                               *(['--restore'] if restore else [])], capture_output=True, timeout=5)

    def assert_rejected(self, result):
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIs(False, json.loads(result.stdout)['verified'])

    def test_fresh_restore_and_repeat_are_exact_and_idempotent(self):
        result = self.run_cli(restore=True)
        self.assertEqual(0, result.returncode, result.stderr)
        first = json.loads(result.stdout)
        self.assertEqual('input_bytes_only', first['verification_scope'])
        self.assertEqual(3, len({row['consumer_path'] for row in first['inputs']}))
        self.assertEqual((3, 0, False), (first['created_count'], first['existing_count'], first['semantic_verification_performed']))
        mtimes = []
        for name, target in zip(NAMES, self.targets):
            self.assertEqual((ROOT / DATA / (name + '.json')).read_bytes(), target.read_bytes())
            mtimes.append(target.stat().st_mtime_ns)
        repeated = self.run_cli(restore=True)
        self.assertEqual(0, repeated.returncode, repeated.stderr)
        self.assertEqual(0, json.loads(repeated.stdout)['created_count'])
        self.assertEqual(mtimes, [p.stat().st_mtime_ns for p in self.targets])
        self.assertEqual(0, self.run_cli().returncode)

    def test_default_check_does_not_create_missing_inputs(self):
        result = self.run_cli()
        self.assert_rejected(result)
        self.assertIn('missing restored contract', result.stdout.decode())
        self.assertFalse((self.root / 'build').exists())

    def test_unchanged_legacy_consumers_import_and_validate_restored_inputs(self):
        self.assertEqual(0, self.run_cli(restore=True).returncode)
        # Decoder runtime is shared only in this temporary test fixture. All
        # contract files and consumer source are separate exact regular files.
        (self.root / 'tools/_vendor').symlink_to(ROOT / 'tools/_vendor', target_is_directory=True)
        snippet = '''
from pathlib import Path
from tools import verify_rom_cgbsound_bounded_cfg as sound
from tools import verify_rom_cgb_helper_bounded_cfg as helper
from tools import verify_rom_mp2k_dispatcher as dispatcher
root = Path.cwd()
sound._contract(root)
helper._contract(root)
dispatcher._validate_contract(root)
print('three unchanged consumers accepted restored contracts')
'''
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        result = subprocess.run([sys.executable, '-c', snippet], cwd=self.root,
                                env=env, capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(b'three unchanged consumers accepted', result.stdout)

    def test_every_source_mutation_or_missing_source_fails_before_any_write(self):
        for name in NAMES:
            source = self.root / DATA / (name + '.json')
            raw = source.read_bytes()
            for mode in ('mutate', 'missing'):
                with self.subTest(name=name, mode=mode):
                    source.write_bytes(raw + b' ') if mode == 'mutate' else source.unlink()
                    self.assert_rejected(self.run_cli(restore=True))
                    self.assertFalse((self.root / 'build').exists())
                    source.write_bytes(raw)

    def test_changed_consumer_and_extra_input_fail_before_any_write(self):
        consumer = self.root / 'tools' / CONSUMERS[-1]
        raw = consumer.read_bytes()
        consumer.write_bytes(raw + b'\n')
        self.assert_rejected(self.run_cli(restore=True))
        self.assertFalse((self.root / 'build').exists())
        consumer.write_bytes(raw)
        (self.root / DATA / 'extra.json').write_text('{}')
        self.assert_rejected(self.run_cli(restore=True))
        self.assertFalse((self.root / 'build').exists())

    def test_later_existing_conflict_prevents_earlier_missing_writes(self):
        target = self.targets[-1]
        target.parent.mkdir(parents=True)
        target.write_bytes(b'user-owned conflict')
        result = self.run_cli(restore=True)
        self.assert_rejected(result)
        self.assertIn('existing contract differs', result.stdout.decode())
        self.assertEqual(b'user-owned conflict', target.read_bytes())
        self.assertFalse(any(p.exists() for p in self.targets[:-1]))

    def test_symlink_source_or_source_ancestor_is_rejected(self):
        source = self.root / DATA / (NAMES[0] + '.json')
        source.unlink()
        source.symlink_to(ROOT / DATA / source.name)
        self.assert_rejected(self.run_cli(restore=True))
        self.assertFalse((self.root / 'build').exists())
        source.unlink()
        shutil.rmtree(self.root / DATA)
        (self.root / DATA).symlink_to(ROOT / DATA, target_is_directory=True)
        self.assert_rejected(self.run_cli(restore=True))

    def test_symlink_target_or_target_ancestor_and_directory_are_rejected(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        (self.root / 'build').symlink_to(outside, target_is_directory=True)
        self.assert_rejected(self.run_cli(restore=True))
        self.assertEqual([], list(outside.iterdir()))
        (self.root / 'build').unlink()
        target = self.targets[-1]
        target.parent.mkdir(parents=True)
        target.symlink_to(ROOT / DATA / (NAMES[-1] + '.json'))
        self.assert_rejected(self.run_cli(restore=True))
        self.assertFalse(any(p.exists() for p in self.targets[:-1]))
        target.unlink()
        target.mkdir()
        self.assert_rejected(self.run_cli(restore=True))
        self.assertFalse(any(p.exists() for p in self.targets[:-1]))

    def test_fifo_target_fails_without_blocking_or_creating_other_inputs(self):
        target = self.targets[-1]
        target.parent.mkdir(parents=True)
        os.mkfifo(target)
        self.assert_rejected(self.run_cli(restore=True))
        self.assertFalse(any(p.exists() for p in self.targets[:-1]))

    def test_temporary_name_collision_preserves_preexisting_file(self):
        parent = self.targets[0].parent
        parent.mkdir(parents=True)
        occupied = parent / '.restore-fixed-collision'
        occupied.write_bytes(b'user-owned temporary name')
        with mock.patch.object(preparer.uuid, 'uuid4', return_value=SimpleNamespace(hex='fixed-collision')):
            with self.assertRaises(FileExistsError):
                preparer.prepare(self.root, restore=True)
        self.assertTrue(occupied.exists(), 'a failed exclusive open must not delete an unowned file')
        self.assertEqual(b'user-owned temporary name', occupied.read_bytes())
        self.assertFalse(any(p.exists() for p in self.targets))

    def test_source_ancestor_replaced_after_precheck_is_not_followed(self):
        source = self.root / DATA / 'cgbsound.json'
        original_check = preparer._reject_symlinks

        def swap_after_check(path):
            original_check(path)
            if path == source:
                archived = source.parent.with_name('original-data')
                source.parent.rename(archived)
                source.parent.symlink_to(archived, target_is_directory=True)

        with mock.patch.object(preparer, '_reject_symlinks', side_effect=swap_after_check):
            with self.assertRaises((OSError, ValueError)):
                preparer._read(source)


if __name__ == '__main__':
    unittest.main()
