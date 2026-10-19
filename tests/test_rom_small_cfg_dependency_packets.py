"""Permanent-path integration for the four frozen small CFG packets."""
import json
from pathlib import Path
import unittest

from tools import rom_small_cfg_dependency_packets as packets

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {'callback_gaps':(10,5), 'wrappers':(54,5), 'event_gaps':(14,7), 'dispatcher':(40,4)}


class PermanentPacketTests(unittest.TestCase):
    def test_four_permanent_candidates_replay_and_do_not_overlap(self):
        claims=[]
        for key,expected in EXPECTED.items():
            with self.subTest(packet=key):
                payload = packets.build_candidate(ROOT,key)
                first = packets.verify_candidate(ROOT,key,payload)
                second = packets.verify_candidate(ROOT,key,payload)
                self.assertEqual(first,second)
                self.assertTrue(first['verified'])
                self.assertFalse(first['canonical_promoted'])
                self.assertEqual((first['promotion_bytes'],payload['promotion']['claim_count']),expected)
                claims.extend(payload['promotion']['claims'])
                for pin in payload.get('upstream_inputs', payload.get('source_inputs', [])):
                    self.assertFalse(pin['path'].startswith('build/'))
                    self.assertFalse(Path(pin['path']).is_absolute())
        spans=sorted(r['range'] for r in claims)
        self.assertEqual((sum(b-a for a,b in spans),len(spans)),(118,21))
        self.assertTrue(all(a[1]<=b[0] for a,b in zip(spans,spans[1:])))

    def test_packet_registry_rejects_unknown_key(self):
        with self.assertRaises(ValueError):
            packets.build_candidate(ROOT,'../wrappers')

    def test_no_pending_bytes_in_canonical_before_tier2(self):
        # This is an immutable precoverage test, so it also runs after promotion.
        import gzip
        raw = gzip.decompress((ROOT / 'notes/evidence/rom-evidence-selector-repair-20260905/coverage-after.json.gz').read_bytes())
        baseline=json.loads(raw)
        self.assertEqual(baseline['summary']['unknown_bytes'],87749)
        self.assertEqual(baseline['summary']['classified_bytes'],6203707)


if __name__ == '__main__':
    unittest.main()
