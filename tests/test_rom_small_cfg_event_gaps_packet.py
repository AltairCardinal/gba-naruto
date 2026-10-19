"""Reuse tests for the event-handler additive boundary packet."""
import copy
import gzip
import json
from pathlib import Path
import unittest
from tools import rom_small_cfg_event_gaps_producer as producer
from tools import rom_small_cfg_event_gaps_independent_verifier as verifier

PACKET = Path(__file__).absolute().parent
ROOT = next(p for p in PACKET.parents if (p / 'rom/base.gba').is_file())


class EventGapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = (ROOT / 'tools/data/rom-small-cfg-dependency-v1/event_gaps.json').read_bytes()
        cls.contract = json.loads(cls.raw)
        cls.rom = (ROOT / 'rom/base.gba').read_bytes()
        cls.source = (ROOT / cls.contract['source_payload']['path']).read_bytes()
        cls.baseline = gzip.decompress((ROOT / cls.contract['baseline_archive']['path']).read_bytes())
        cls.candidate = producer.build_payload(cls.rom, cls.source, cls.baseline, cls.raw)

    def test_seven_positive_boundaries_and_complete_exclusions(self):
        result = verifier.verify_candidate(ROOT, ROOT / 'tools/data/rom-small-cfg-dependency-v1/event_gaps.json', self.candidate)
        self.assertTrue(result['verified'])
        self.assertEqual(result['promotion_bytes'], 14)
        self.assertEqual(result['gap_count'], 7)
        self.assertEqual(result['source_instruction_count'], 1742)
        self.assertEqual(result['source_literal_binding_count'], 53)
        self.assertEqual(result['zero_gap_count'], 11)
        self.assertEqual(result['excluded_hole_bytes'], 160)
        self.assertFalse(result['canonical_promoted'])

    def test_each_gap_byte_and_each_literal_binding_value_mutation_is_rejected(self):
        closure = {'code_ranges': self.contract['source_promotion']['code_ranges'],
                   'literal_ranges': self.contract['source_promotion']['literal_ranges'],
                   'literal_bindings': self.contract['source_literal_bindings'],
                   'holes': [row['range'] for row in self.contract['expected_boundaries']]}
        for start, end in closure['holes']:
            for offset in range(start, end):
                with self.subTest(offset=hex(offset)):
                    rom = bytearray(self.rom)
                    rom[offset] = 1
                    with self.assertRaises(ValueError):
                        verifier.reuse.derive_boundaries(rom, closure)
        for index in range(len(closure['literal_bindings'])):
            altered = copy.deepcopy(closure)
            altered['literal_bindings'][index][2] = 'ffffffff'
            with self.subTest(binding=index), self.assertRaises(ValueError):
                verifier.reuse.derive_boundaries(self.rom, altered)

    def test_false_return_owner_and_tail_promotion_fail_closed(self):
        for mutation in ('return', 'owner', 'tail', 'scope'):
            with self.subTest(mutation=mutation):
                candidate = copy.deepcopy(self.candidate)
                if mutation == 'return':
                    candidate['boundaries'][0]['terminal']['kind'] = 'structured_return'
                elif mutation == 'owner':
                    candidate['boundaries'][0]['baseline_owners']['left']['claims'][0]['range'][0] -= 2
                elif mutation == 'tail':
                    candidate['promotion']['claims'].append({'range': [0x7F062, 0x7F0FC]})
                else:
                    candidate['scope']['accepted'] = True
                with self.assertRaisesRegex(ValueError, 'candidate'):
                    verifier.verify_candidate(ROOT, ROOT / 'tools/data/rom-small-cfg-dependency-v1/event_gaps.json', candidate)

    def test_raw_input_identity_mismatch_fails_closed(self):
        for index in range(4):
            args = [self.rom, self.source, self.baseline, self.raw]
            args[index] = b'changed'
            with self.subTest(input=index), self.assertRaises(ValueError):
                producer.build_payload(*args)


if __name__ == '__main__':
    unittest.main()
