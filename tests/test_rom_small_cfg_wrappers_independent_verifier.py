"""Independent wrapper raw graph, producer membership and owner checks."""
import copy
import gzip
import json
from pathlib import Path
import unittest

from tools import rom_small_cfg_wrappers_producer as producer
from tools import rom_small_cfg_wrappers_independent_verifier as verifier

PACKET = Path(__file__).absolute().parent
ROOT = next(p for p in PACKET.parents if (p / 'rom/base.gba').is_file())


class IndependentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_raw = (ROOT / 'tools/data/rom-small-cfg-dependency-v1/wrappers.json').read_bytes()
        cls.contract = json.loads(cls.contract_raw)
        cls.rom = (ROOT / 'rom/base.gba').read_bytes()
        cls.baseline = gzip.decompress((ROOT / cls.contract['baseline_archive']['path']).read_bytes())
        cls.payload = producer.build_payload(cls.rom, cls.baseline, cls.contract_raw)

    def test_full_real_packet_has_fifteen_proven_sources_and_exact_opaque_entries(self):
        result = verifier.verify_candidate(ROOT, ROOT / 'tools/data/rom-small-cfg-dependency-v1/wrappers.json', self.payload)
        self.assertTrue(result['verified'])
        self.assertEqual(result['promotion_bytes'], 54)
        self.assertEqual(len(result['producer_instruction_membership']), 15)
        self.assertEqual(result['upstream_event_instruction_count'], 1742)
        self.assertEqual(result['upstream_text_bg_instruction_count'], 1330)
        self.assertEqual([r['entry'] for r in result['opaque_entry_membership']], [0x7ADBC, 0x7B888])
        self.assertEqual(result['frontier_count'], 3)
        self.assertEqual(result['structured_return_count'], 0)
        self.assertFalse(result['canonical_promoted'])

    def test_candidate_semantic_and_provenance_tampering_is_rejected(self):
        for field in ('source', 'frontier', 'claim', 'owner', 'scope'):
            with self.subTest(field=field):
                candidate = copy.deepcopy(self.payload)
                if field == 'source':
                    candidate['producers'][0]['source'] += 2
                elif field == 'frontier':
                    candidate['closure']['frontiers'][0]['reason'] = 'structured_return'
                elif field == 'claim':
                    candidate['promotion']['claims'][0]['range'][1] += 2
                elif field == 'owner':
                    candidate['producers'][0]['owners'][0]['claims'][0]['range'][0] -= 2
                else:
                    candidate['scope']['accepted'] = True
                with self.assertRaisesRegex(ValueError, 'candidate'):
                    verifier.verify_candidate(ROOT, ROOT / 'tools/data/rom-small-cfg-dependency-v1/wrappers.json', candidate)

    def test_independent_scanner_excludes_reserved_conditions_and_covers_tail(self):
        rom = bytes.fromhex('00de00df0000fee7')
        self.assertEqual(verifier.scan_producers(rom, [4, 6]), [
            {'kind': 'thumb_b', 'source': 6, 'target': 6, 'raw_hex': 'fee7', 'size': 2}])

    def test_independent_raw_closure_rejects_each_candidate_code_byte_mutation(self):
        for start, end in self.contract['code_ranges']:
            for offset in range(start, end):
                with self.subTest(offset=hex(offset)):
                    rom = bytearray(self.rom)
                    rom[offset] ^= 0x80
                    with self.assertRaises(ValueError):
                        verifier.rebuild_closure(rom, self.contract)


if __name__ == '__main__':
    unittest.main()
