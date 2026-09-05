#!/usr/bin/env python3
"""Independent verifier tests for proven-roots-v1 consumed literals."""

from __future__ import annotations
import ast, json, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from tools import export_rom_cfg_v1_consumed_literals as exporter

ROOT=Path(__file__).resolve().parents[1]
def _load():
    try: from tools import verify_rom_cfg_v1_consumed_literals as verifier
    except (ImportError,ModuleNotFoundError) as error: raise AssertionError("v1 verifier is absent") from error
    return verifier

class CfgV1ConsumedLiteralsVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.verifier=_load()
    def _candidate(self,directory:Path):
        path=directory/"candidate"
        shutil.copytree(ROOT/"artifacts/rom-cfg-v1-consumed-literals-v1",path)
        return path
    def test_full_independent_rebuild(self):
        with tempfile.TemporaryDirectory() as raw: report=self.verifier.verify_root(ROOT,self._candidate(Path(raw)))
        self.assertTrue(report["contract_ok"])
        self.assertTrue(report["verified"])
        self.assertEqual({"source_instruction_count":398,"unique_target_word_count":349,"target_bytes":1396,"merged_target_range_count":108},report["summary"])
        self.assertEqual((1203,6166,12966),(report["source_denominator"]["thumb_block_count"],report["source_denominator"]["thumb_instruction_count"],report["source_denominator"]["thumb_instruction_bytes"]))
    def test_decoder_and_isolated_cli(self):
        self.assertEqual(4,self.verifier._thumb_instruction_width(bytes.fromhex("00f000f8"),0,4)); self.assertEqual(2,self.verifier._thumb_instruction_width(bytes.fromhex("0048"),0,2)); self.assertEqual(0x110,self.verifier._decode_ldr_literal_target(0x102,0x4803))
        with tempfile.TemporaryDirectory() as raw:
            candidate=self._candidate(Path(raw)); result=subprocess.run([sys.executable,"-I","-S","tools/verify_rom_cfg_v1_consumed_literals.py","--root",".","--artifact",str(candidate)],cwd=ROOT,capture_output=True,text=True,check=False)
            self.assertEqual(0,result.returncode,result.stderr); self.assertTrue(json.loads(result.stdout)["contract_ok"])
    def test_tamper_foreign_file_and_symlink_fail(self):
        with tempfile.TemporaryDirectory() as raw:
            candidate=self._candidate(Path(raw)); payload=candidate/exporter.PAYLOAD_NAME; data=json.loads(payload.read_text()); data["summary"]["target_bytes"]+=4; payload.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
            with self.assertRaisesRegex(ValueError,"payload identity|artifact file"): self.verifier.verify_root(ROOT,candidate)
        with tempfile.TemporaryDirectory() as raw:
            candidate=self._candidate(Path(raw)); (candidate/"foreign").write_text("no")
            with self.assertRaisesRegex(ValueError,"artifact file set"): self.verifier.verify_root(ROOT,candidate)
        with tempfile.TemporaryDirectory() as raw:
            d=Path(raw); candidate=self._candidate(d); alias=d/"alias"; alias.symlink_to(candidate,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,"symlink"): self.verifier.verify_root(ROOT,alias)
    def test_no_exporter_or_generic_decoder_dependency(self):
        tree=ast.parse((ROOT/"tools/verify_rom_cfg_v1_consumed_literals.py").read_text()); imports=[]; names=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import): imports.extend(a.name for a in node.names)
            elif isinstance(node,ast.ImportFrom) and node.module: imports.append(node.module)
            elif isinstance(node,ast.Name): names.append(node.id)
        self.assertFalse(any("consumed_literals" in x or "export_rom_cfg" in x for x in imports)); self.assertNotIn("_decode_one",names)
if __name__=="__main__": unittest.main()
