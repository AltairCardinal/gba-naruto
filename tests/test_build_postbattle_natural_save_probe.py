import unittest
from pathlib import Path
from tools.build_postbattle_natural_save_probe import build_probe
ROOT=Path(__file__).resolve().parent.parent
class CombinedSaveProbeTest(unittest.TestCase):
 def test_builds(self):
  b=(ROOT/'rom/base.gba').read_bytes();p=build_probe(b);self.assertEqual(len(b),len(p));self.assertNotEqual(b,p)
if __name__=='__main__':unittest.main()
