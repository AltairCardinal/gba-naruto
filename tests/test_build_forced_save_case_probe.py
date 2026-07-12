import unittest
from pathlib import Path
from tools.build_forced_save_case_probe import AFTER,STATE_INIT,GATE_STUB,GATE_STUB_OFFSET,CASE_STUB,CASE_STUB_OFFSET,build_probe
ROOT=Path(__file__).resolve().parent.parent
class ForcedSaveCaseProbeTest(unittest.TestCase):
 def test_dispatch_state_is_f400(self):
  b=(ROOT/'rom/base.gba').read_bytes();p=build_probe(b)
  self.assertEqual(p[STATE_INIT:STATE_INIT+4],AFTER)
  self.assertEqual(len(p),len(b))
  self.assertLess(GATE_STUB_OFFSET+36,CASE_STUB_OFFSET)
if __name__=='__main__':unittest.main()
