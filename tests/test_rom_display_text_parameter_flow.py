"""Raw parameter effects with real ROM integration and fail-closed mutations."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DisplayTextParameterFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / 'rom/base.gba').read_bytes()
        base = ROOT / 'notes/evidence'
        cls.paths = json.loads((base / 'rom-renderer-flow-cost-20261001-v1/cost.json').read_text())['rows']
        cls.members = {r['site']: r for r in json.loads((base / 'rom-renderer-source-plan-20261001-v1/source-map.json').read_text())['rows']}

    def prove(self, rom, row=None, **overrides):
        from tools.rom_display_text_parameter_flow import prove_parameter_flow
        row = row or self.paths[0]
        member = self.members[row['site']]
        kwargs = dict(site=row['site'], sink=row['sink'], target=member['target'], owner_range=member['claim_range'])
        kwargs.update(overrides)
        return prove_parameter_flow(rom, **kwargs)

    def mutate(self, at, data):
        rom = bytearray(self.rom)
        rom[at:at + len(data)] = data
        return bytes(rom)

    def test_real_rom_all_92_paths_and_both_display_bridges(self):
        results = [self.prove(self.rom, row) for row in self.paths]
        self.assertEqual(92, len(results))
        self.assertEqual(559, sum(r['instruction_count'] for r in results))
        self.assertEqual({0x66758: 75, 0x667A0: 17}, {callee: sum(r['callee'] == callee for r in results) for callee in (0x66758, 0x667A0)})
        for row, result in zip(self.paths, results):
            self.assertEqual(row['path_sha256'], result['path_sha256'])
            self.assertEqual(self.members[row['site']]['target'], result['target'])

    def test_r0_overwrite_at_every_real_path_rejected(self):
        for row in self.paths:
            with self.subTest(site=hex(row['site'])):
                with self.assertRaisesRegex(ValueError, 'r0'):
                    self.prove(self.mutate(row['site'] + 2, b'\x00\x20'), row)

    def test_high_register_mov_and_stack_load_cannot_clobber_r0(self):
        row = self.paths[0]
        for half in (0x4640, 0x9800, 0x3001, 0x1C08, 0x4801):
            with self.subTest(half=hex(half)):
                with self.assertRaisesRegex(ValueError, 'r0'):
                    self.prove(self.mutate(row['site'] + 2, half.to_bytes(2, 'little')), row)

    def test_early_control_flow_and_unknown_encodings_rejected(self):
        row = self.paths[0]
        for half in (0xE000, 0xD000, 0x4700, 0xBD00, 0xF000, 0x0000, 0x468D, 0x468F):
            with self.subTest(half=hex(half)):
                with self.assertRaisesRegex(ValueError, 'unsupported|control'):
                    self.prove(self.mutate(row['site'] + 2, half.to_bytes(2, 'little')), row)

    def test_low_register_mov_encoding_outside_required_subset_rejected(self):
        row = self.paths[0]
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            self.prove(self.mutate(row['site'] + 2, b'\x09\x46'), row)

    def test_literal_register_or_target_change_rejected(self):
        row = self.paths[0]
        site = row['site']
        half = int.from_bytes(self.rom[site:site + 2], 'little')
        with self.assertRaisesRegex(ValueError, 'literal.*r0'):
            self.prove(self.mutate(site, (half | 0x100).to_bytes(2, 'little')), row)
        literal = ((site + 4) & ~3) + 4 * (half & 255)
        with self.assertRaisesRegex(ValueError, 'literal target'):
            self.prove(self.mutate(literal, b'\x00\x00\x00\x08'), row)

    def test_wrong_call_target_or_missing_bl_rejected(self):
        row = self.paths[0]
        with self.assertRaisesRegex(ValueError, 'callee'):
            self.prove(self.mutate(row['sink'] + 2, b'\x00\xf8'), row)
        with self.assertRaisesRegex(ValueError, 'BL'):
            self.prove(self.mutate(row['sink'], b'\x00\x20'), row)

    def test_path_bounds_alignment_and_integer_contract_rejected(self):
        row = self.paths[0]
        for kwargs in ({'site': row['site'] + 1}, {'sink': row['sink'] + 1},
                       {'owner_range': [row['site'], row['sink'] + 2]},
                       {'owner_range': [-2, len(self.rom)]}, {'site': True},
                       {'sink': row['site']}, {'sink': row['site'] + 64},
                       {'target': len(self.rom)}, {'owner_range': [0]}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    self.prove(self.rom, row, **kwargs)

    def test_no_rom_writes_or_natural_execution_claim(self):
        before = hashlib.sha256(self.rom).hexdigest()
        result = self.prove(self.rom)
        self.assertEqual(before, hashlib.sha256(self.rom).hexdigest())
        self.assertFalse(result['natural_runtime_reachability'])
        self.assertFalse(result['source_cfg_verified'])


if __name__ == '__main__':
    unittest.main()
