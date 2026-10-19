import copy
import gzip
import json
from pathlib import Path
import unittest

from tools import rom_small_cfg_dispatcher_producer as producer
from tools import rom_small_cfg_dispatcher_independent_verifier as verifier
from tests.test_rom_small_cfg_dispatcher_dispatch_decode import _synthetic_fixture
from tools.rom_small_cfg_dispatch_decode import decode_dispatch

PACKET = Path(__file__).absolute().parent
ROOT = next(p for p in PACKET.parents if (p / 'rom/base.gba').is_file())


class ParentPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = (ROOT / 'tools/data/rom-small-cfg-dependency-v1/dispatcher.json').read_bytes()
        cls.contract = json.loads(cls.raw)
        cls.rom = (ROOT / 'rom/base.gba').read_bytes()
        cls.baseline = gzip.decompress((ROOT / cls.contract['baseline_archive']['path']).read_bytes())
        cls.payload = producer.build_payload(cls.rom, cls.baseline, cls.raw)

    def test_real_packet_source_owners_and_full_dispatch(self):
        report = verifier.verify_candidate(ROOT, ROOT / 'tools/data/rom-small-cfg-dependency-v1/dispatcher.json', self.payload)
        self.assertTrue(report['verified'])
        self.assertEqual((report['promotion_bytes'], report['claim_count']), (40, 4))
        self.assertEqual((report['instruction_count'], report['basic_block_count'], report['block_edge_count']), (15, 3, 8))
        self.assertEqual((report['table_slot_count'], report['code_bytes'], report['literal_bytes']), (20, 32, 8))
        self.assertEqual((report['frontier_count'], report['structured_return_count']), (0, 0))
        self.assertEqual((report['producer_count'], report['opaque_entry_count'], report['existing_owner_bytes']), (1, 4, 80))
        self.assertEqual(report['producer_instruction_membership'][0]['source'], 0x7E86E)
        self.assertEqual(report['source_instruction_count'], 1742)

    def test_independent_hidden_homologous_inputs(self):
        for options in ({}, {'root':0x42, 'subtract':31, 'maximum':1, 'targets':(0x180,0x188)}):
            rom = bytes(_synthetic_fixture(**options))
            root = options.get('root', 0x40)
            a = verifier.decode_dispatch_raw(rom, root)
            self.assertEqual(a, decode_dispatch(rom, root))
            self.assertEqual(len(a['input_domain']), 256)
            self.assertEqual(sorted({r['slot_index'] for r in a['input_domain'] if r['slot_index'] is not None}), list(range(a['maximum_index']+1)))
            for row in a['input_domain']:
                self.assertEqual(row['index_u32'], (row['command']-options.get('subtract',5)) % (2**32))

    def test_all_120_semantic_bytes_mutate_fail_closed(self):
        ranges = self.contract['code_ranges'] + self.contract['literal_ranges'] + [self.contract['table_range']]
        self.assertEqual(sum(b-a for a,b in ranges), 120)
        for a,b in ranges:
            for at in range(a,b):
                raw = bytearray(self.rom); raw[at] ^= 0x80
                with self.subTest(offset=hex(at)), self.assertRaises(ValueError):
                    verifier.rebuild_closure(bytes(raw), self.contract)

    def test_candidate_table_mode_owner_scope_and_hole_mutations(self):
        mutants = []
        for key, value in [('scope', {'canonical_promoted':True}), ('producers', []), ('existing_owner_provenance', [])]:
            p = copy.deepcopy(self.payload); p[key] = value; mutants.append(p)
        p = copy.deepcopy(self.payload); p['closure']['dispatch']['table_entries'][-1]['mode']='arm'; mutants.append(p)
        p = copy.deepcopy(self.payload); p['closure']['dispatch']['input_domain'][0]['slot_index']=0; mutants.append(p)
        p = copy.deepcopy(self.payload); p['promotion']['claims'][0]['range'][1]+=2; mutants.append(p)
        p = copy.deepcopy(self.payload); p['promotion']['claims'][-1]['baseline_owners'][0]['primary_class']='code'; mutants.append(p)
        for mutant in mutants:
            with self.assertRaises(ValueError):
                verifier.verify_candidate(ROOT, ROOT / 'tools/data/rom-small-cfg-dependency-v1/dispatcher.json', mutant)

    def test_raw_input_identities(self):
        for position in range(3):
            args=[self.rom,self.baseline,self.raw]; args[position]+=b' '
            with self.assertRaises(ValueError):
                producer.build_payload(*args)


if __name__ == '__main__':
    unittest.main()
