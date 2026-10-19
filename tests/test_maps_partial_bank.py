from pathlib import Path
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from tools import verify_maps_partial_bank as verifier
from tools.audit_reverse_engineering_proof import _check_bank, _execute_contract

ROOT=Path(__file__).resolve().parents[1]


class PartialMapsTests(unittest.TestCase):
    def clone(self,root):
        names=set(json.loads((ROOT/verifier.CONTRACT).read_text())['inputs'])|{verifier.CONTRACT,verifier.SCRIPT}
        for n in names:
            p=root/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/n,p)

    def test_four_actual_cells_and_all_uncovered_ids(self):
        r=verifier.verify_partial_bank(ROOT)
        self.assertTrue(r['verified']);self.assertEqual(r['record_ids_total'],[str(i) for i in range(47)])
        self.assertEqual(r['record_ids_covered'],['41']);self.assertEqual(r['cells_total'],423)
        fields=['tileset_ptr','tilemap_ptr','tilemap_alt_ptr','palette_ptr']
        self.assertEqual(r['field_ids_covered'],fields)
        self.assertEqual(r['cells_covered'],[{'record_id':'41','field_id':f} for f in fields])
        allcells={(str(i),f) for i in range(47) for f in r['field_ids_total']}
        seen={(x['record_id'],x['field_id']) for x in r['cells_uncovered']}
        covered={(x['record_id'],x['field_id']) for x in r['cells_covered']}
        self.assertEqual(len(seen),419);self.assertFalse(seen&covered);self.assertEqual(seen|covered,allcells)
        self.assertEqual([x['changed_pixel_count'] for x in r['causal_resources']],[1,119,204,56])
        self.assertFalse(r['header_pointer_value_ab_verified']);self.assertTrue(r['resource_content_ab_verified'])
        self.assertEqual(r['historical_captures'],6)
        for k in ['zero_input_control_verified','historical_shared_lock_verified','current_emulator_executed',
                  'physical_gba_verified','exhaustive']:self.assertFalse(r[k])

    def test_relocated_root_and_real_cli_match(self):
        expected=verifier.verify_partial_bank(ROOT)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();self.clone(root)
            self.assertEqual(verifier.verify_partial_bank(root),expected)
            p=subprocess.run([sys.executable,str(root/verifier.SCRIPT),'--root',str(root)],cwd=root,capture_output=True,text=True,check=False)
            self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout),expected)

    def test_inputs_contract_missing_and_symlinks_fail_closed(self):
        for kind in ['contract','bank','state','implementation','missing','symlink']:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as d:
                root=Path(d).resolve();self.clone(root)
                n={'contract':verifier.CONTRACT,'bank':verifier.BANK,
                   'state':'artifacts/map41-visual-resource-matrix-v1/tile_graphics/frame80.ss9',
                   'implementation':'tools/verify_map41_visual_resource_matrix_evidence.py',
                   'missing':verifier.BANK,'symlink':verifier.BANK}[kind];p=root/n
                if kind in ['missing','symlink']:
                    p.unlink()
                    if kind=='symlink':p.symlink_to(ROOT/n)
                else:
                    with p.open('ab') as s:s.write(b' ')
                with self.assertRaises((ValueError,OSError)):verifier.verify_partial_bank(root)

    def test_existing_auditor_contract_accepts_only_actual_partial_cells(self):
        r=verifier.verify_partial_bank(ROOT);proposal=verifier.proof_binding(ROOT,r)
        v=proposal['verifiers'][0];command=[sys.executable,*v['command'][1:]]
        errors=[];self.assertTrue(_execute_contract(ROOT,'maps',command,v['contract'],errors)['contract_ok'],errors)
        for key,value in [('/cells_covered',r['cells_covered']+[{'record_id':'41','field_id':'flags'}]),
                          ('/header_pointer_value_ab_verified',True),('/physical_gba_verified',True)]:
            forged=copy.deepcopy(v['contract']);forged['assertions'][key]=value
            self.assertFalse(_execute_contract(ROOT,'maps',command,forged,[])['contract_ok'])
        blockers=[];commands=[]
        checked=_check_bank(ROOT,'maps',ROOT/verifier.BANK,proposal,None,blockers,commands)
        self.assertFalse(checked['complete']);self.assertEqual(checked['contracted_verifier_count'],1)
        self.assertTrue(blockers)
        proposal['limitations']=[];proposal['coverage'].update({'status':'exhaustive','records_covered':47,
               'record_ids_covered':r['record_ids_total'],'field_ids_covered':r['field_ids_total']})
        checked=_check_bank(ROOT,'maps',ROOT/verifier.BANK,proposal,None,[],[])
        self.assertFalse(checked['complete'])

    def test_proof_binding_rejects_relabelled_counterfactual_and_guards(self):
        expected=verifier.verify_partial_bank(ROOT)
        for key in ['header_pointer_value_ab_verified','zero_input_control_verified','historical_shared_lock_verified']:
            with self.subTest(key=key):
                r=copy.deepcopy(expected);r[key]=True
                with self.assertRaisesRegex(ValueError,'result mismatch'):verifier.proof_binding(ROOT,r)

    def test_re_signed_raw_capture_substitution_fails_legacy_reconstruction(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();self.clone(root)
            artifact=root/'artifacts/map41-visual-resource-matrix-v1'
            p=artifact/'tile_graphics/frame80.ss9';shutil.copy2(artifact/'baseline/frame80.ss9',p)
            m=artifact/'manifest.json';data=json.loads(m.read_text());data['files']['tile_graphics/frame80.ss9']=hashlib.sha256(p.read_bytes()).hexdigest();m.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'legacy'):
                verifier.verify_artifacts(root)

    def test_cli_missing_input_is_json_failure(self):
        with tempfile.TemporaryDirectory() as d:
            p=subprocess.run([sys.executable,str(ROOT/verifier.SCRIPT),'--root',d],capture_output=True,text=True,check=False)
            self.assertEqual(p.returncode,1);r=json.loads(p.stdout);self.assertFalse(r['verified']);self.assertTrue(r['errors'])


if __name__=='__main__':unittest.main()
