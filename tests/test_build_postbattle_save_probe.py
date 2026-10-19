import unittest
from pathlib import Path
from tools.build_postbattle_save_probe import HOOK,ROM_BASE,STUB_OFFSET,LATCH,build_probe
ROOT=Path(__file__).resolve().parent.parent
class PostbattleSaveProbeTest(unittest.TestCase):
 def test_contained(self):
  b=(ROOT/'rom/base.gba').read_bytes();p=build_probe(b)
  c=[i for i,(x,y) in enumerate(zip(b,p)) if x!=y]
  self.assertTrue(all(HOOK-ROM_BASE<=i<HOOK-ROM_BASE+4 or STUB_OFFSET<=i<STUB_OFFSET+48 for i in c))
  self.assertEqual(int.from_bytes(p[STUB_OFFSET+40:STUB_OFFSET+44],'little'),LATCH)
if __name__=='__main__':unittest.main()
