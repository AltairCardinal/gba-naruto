"""The Windows twin must restore exact legacy inputs without replacing existing files.

Mirrors the contract of tests/test_prepare_rom_verifier_contracts.py, which
covers the POSIX-only upstream tool (os.O_DIRECTORY / dir_fd) and therefore
cannot run on Windows at all.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tools import prepare_rom_verifier_contracts_win as preparer

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/prepare_rom_verifier_contracts_win.py'
DATA = Path('tools/data/rom-verifier-contracts-v1')
NAMES = ('cgbsound', 'cgb-helper', 'mp2k-dispatcher')
CONSUMERS = ('verify_rom_cgbsound_bounded_cfg.py',
             'verify_rom_cgb_helper_bounded_cfg.py',
             'verify_rom_mp2k_dispatcher.py')


class WindowsVerifierContractRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'checkout'
        (self.root / DATA).mkdir(parents=True)
        (self.root / 'tools').mkdir(parents=True, exist_ok=True)
        self.targets = []
        for name, consumer in zip(NAMES, CONSUMERS):
            shutil.copyfile(ROOT / DATA / (name + '.json'), self.root / DATA / (name + '.json'))
            shutil.copyfile(ROOT / 'tools' / consumer, self.root / 'tools' / consumer)
            self.targets.append(
                self.root / f'build/experiments/active/{name}-contract/codex-r1-20260829/CONTRACT.json')

    def run_cli(self, *, restore=False):
        return subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root),
                               *(['--restore'] if restore else [])],
                              capture_output=True, timeout=30, text=True)

    def assert_rejected(self, result):
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIs(False, json.loads(result.stdout)['verified'])

    def test_fresh_restore_and_repeat_are_exact_and_idempotent(self):
        result = self.run_cli(restore=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        first = json.loads(result.stdout)
        self.assertEqual('input_bytes_only', first['verification_scope'])
        self.assertEqual('rom-verifier-contract-input-preparation-v1', first['schema'])
        self.assertEqual(3, len({row['consumer_path'] for row in first['inputs']}))
        self.assertEqual((3, 0, False),
                         (first['created_count'], first['existing_count'],
                          first['semantic_verification_performed']))
        mtimes = []
        for name, target in zip(NAMES, self.targets):
            self.assertEqual((ROOT / DATA / (name + '.json')).read_bytes(), target.read_bytes())
            mtimes.append(target.stat().st_mtime_ns)
        repeated = self.run_cli(restore=True)
        self.assertEqual(0, repeated.returncode, repeated.stdout + repeated.stderr)
        self.assertEqual(0, json.loads(repeated.stdout)['created_count'])
        self.assertEqual(mtimes, [p.stat().st_mtime_ns for p in self.targets])
        self.assertEqual(0, self.run_cli().returncode)

    def test_default_check_does_not_create_missing_inputs(self):
        self.assert_rejected(self.run_cli())
        for target in self.targets:
            self.assertFalse(target.exists())

    def test_restored_bytes_match_the_pinned_digests(self):
        self.assertEqual(0, self.run_cli(restore=True).returncode)
        for (name, size, digest, _, _), target in zip(preparer.INPUTS, self.targets):
            raw = target.read_bytes()
            self.assertEqual(size, len(raw), name)
            self.assertEqual(digest, preparer.hashlib.sha256(raw).hexdigest(), name)

    def test_mutated_source_fails_closed(self):
        path = self.root / DATA / 'cgbsound.json'
        path.write_bytes(path.read_bytes() + b' ')
        self.assert_rejected(self.run_cli(restore=True))
        for target in self.targets:
            self.assertFalse(target.exists())

    def test_missing_source_fails_closed(self):
        (self.root / DATA / 'cgbsound.json').unlink()
        self.assert_rejected(self.run_cli(restore=True))

    def test_extra_source_file_fails_closed(self):
        (self.root / DATA / 'unexpected.json').write_bytes(b'{}')
        self.assert_rejected(self.run_cli(restore=True))

    def test_mutated_consumer_fails_closed(self):
        path = self.root / 'tools' / 'verify_rom_cgbsound_bounded_cfg.py'
        path.write_bytes(path.read_bytes() + b'\n')
        self.assert_rejected(self.run_cli(restore=True))
        for target in self.targets:
            self.assertFalse(target.exists())

    def test_existing_conflicting_contract_is_never_replaced(self):
        target = self.targets[0]
        target.parent.mkdir(parents=True)
        target.write_bytes(b'{"conflict": true}\n')
        self.assert_rejected(self.run_cli(restore=True))
        self.assertEqual(b'{"conflict": true}\n', target.read_bytes())

    def test_existing_identical_contract_is_reused(self):
        self.assertEqual(0, self.run_cli(restore=True).returncode)
        report = json.loads(self.run_cli().stdout)
        self.assertEqual((0, 3), (report['created_count'], report['existing_count']))


if __name__ == '__main__':
    unittest.main()
