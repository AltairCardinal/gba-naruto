"""Real input and adversarial candidate tests for the additive gap verifier."""
import copy
import gzip
import json
from pathlib import Path
import unittest

from tools import rom_small_cfg_callback_gaps_producer as producer
from tools import rom_small_cfg_callback_gaps_independent_verifier as verifier

PACKET = Path(__file__).absolute().parent
ROOT = next(p for p in PACKET.parents if (p / 'rom/base.gba').is_file())


class IndependentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / 'rom/base.gba').read_bytes()
        cls.contract_raw = (ROOT / 'tools/data/rom-small-cfg-dependency-v1/callback_gaps.json').read_bytes()
        cls.contract = json.loads(cls.contract_raw)
        cls.source = (ROOT / cls.contract['source_payload']['path']).read_bytes()
        cls.baseline = gzip.decompress((ROOT / cls.contract['baseline_archive']['path']).read_bytes())
        cls.candidate = producer.build_payload(cls.rom, cls.source, cls.baseline, cls.contract_raw)

    def test_real_candidate_replays_upstream_raw_closure_and_projection(self):
        report = verifier.verify_candidate(ROOT, ROOT / 'tools/data/rom-small-cfg-dependency-v1/callback_gaps.json', self.candidate)
        self.assertTrue(report['verified'])
        self.assertEqual(report['promotion_bytes'], 10)
        self.assertEqual(report['gap_count'], 5)
        self.assertEqual(report['source_instruction_count'], 342)
        self.assertEqual(report['source_literal_binding_count'], 15)
        self.assertEqual(report['source_frontiers'], [{'source': 0x79144, 'reason': 'indirect_pc_target'}])
        self.assertFalse(report['source_full_lifecycle_replayed_here'])
        self.assertFalse(report['canonical_promoted'])

    def test_candidate_cannot_forge_return_or_owner_or_add_bytes(self):
        for mutation in ('return', 'owner', 'range', 'extra'):
            with self.subTest(mutation=mutation):
                candidate = copy.deepcopy(self.candidate)
                if mutation == 'return':
                    candidate['boundaries'][-1]['terminal']['kind'] = 'structured_return'
                elif mutation == 'owner':
                    candidate['boundaries'][0]['baseline_owners']['gap'][0]['unknown_reason'] = 'forged'
                elif mutation == 'range':
                    candidate['promotion']['claims'][0]['range'][0] -= 2
                else:
                    candidate['scope']['accepted'] = True
                with self.assertRaisesRegex(ValueError, 'candidate'):
                    verifier.verify_candidate(ROOT, ROOT / 'tools/data/rom-small-cfg-dependency-v1/callback_gaps.json', candidate)

    def test_raw_gap_and_literal_mutations_fail_at_derivation(self):
        source = json.loads(self.source)
        expected = verifier.derive_boundaries(self.rom, source['closure'])
        self.assertEqual(len(expected), 5)
        for start, end in source['closure']['holes']:
            for position in range(start, end):
                with self.subTest(position=hex(position)):
                    rom = bytearray(self.rom)
                    rom[position] = 1
                    with self.assertRaises(ValueError):
                        verifier.derive_boundaries(rom, source['closure'])


if __name__ == '__main__':
    unittest.main()
