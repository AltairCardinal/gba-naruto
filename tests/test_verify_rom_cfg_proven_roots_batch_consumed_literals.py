#!/usr/bin/env python3
from __future__ import annotations
import ast,json,shutil
from pathlib import Path
import tempfile,unittest
from tools import export_rom_cfg_proven_roots_batch_consumed_literals as exporter
ROOT=Path(__file__).resolve().parents[1]
def load():
 try:from tools import verify_rom_cfg_proven_roots_batch_consumed_literals as module
 except (ImportError,ModuleNotFoundError) as error:raise AssertionError('batch verifier is absent') from error
 return module
class BatchVerifierTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.module=load()
 def candidate(self,d):p=d/'candidate';shutil.copytree(ROOT/'artifacts/rom-cfg-proven-roots-batch-consumed-literals-v1',p);return p
 def test_independently_rebuilds_union(self):
  with tempfile.TemporaryDirectory() as raw:r=self.module.verify_root(ROOT,self.candidate(Path(raw)))
  self.assertTrue(r['verified']);self.assertTrue(r['contract_ok']);self.assertEqual(314,r['denominator']['unique_target_word_count']);self.assertEqual(1256,r['denominator']['target_bytes']);self.assertEqual(7,len(r['families']))
 def test_independent_decoder(self):
  self.assertEqual(4,self.module._thumb_width(bytes.fromhex('00f000f8'),0,4));self.assertEqual(2,self.module._thumb_width(bytes.fromhex('0048'),0,2));self.assertEqual(0x110,self.module._ldr_target(0x102,0x4803))
 def test_rejects_tampering_and_is_independent(self):
  with tempfile.TemporaryDirectory() as raw:
   p=self.candidate(Path(raw));q=p/exporter.PAYLOAD_NAME;d=json.loads(q.read_text());d['target_words'][0]['target_file_offset']+=4;q.write_text(json.dumps(d,sort_keys=True))
   with self.assertRaisesRegex(ValueError,'identity|payload'):self.module.verify_root(ROOT,p)
  tree=ast.parse((ROOT/'tools/verify_rom_cfg_proven_roots_batch_consumed_literals.py').read_text());imports=[];names=[]
  for n in ast.walk(tree):
   if isinstance(n,ast.ImportFrom) and n.module:imports.append(n.module)
   if isinstance(n,ast.Name):names.append(n.id)
  self.assertFalse(any('consumed_literals' in x for x in imports));self.assertNotIn('_decode_one',names)
if __name__=='__main__':unittest.main()
