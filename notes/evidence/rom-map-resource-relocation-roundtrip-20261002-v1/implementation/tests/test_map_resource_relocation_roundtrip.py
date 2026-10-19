from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tools import audit_map_resource_relocation_roundtrip as auditor
from tools.experiment_workspace import init_run

ROOT=Path(__file__).resolve().parents[1]


class MapRelocationRoundtripTests(unittest.TestCase):
    def clone(self,root):
        names=set(json.loads((ROOT/auditor.CONTRACT).read_text())['inputs'])|{auditor.CONTRACT,auditor.SCRIPT}
        for name in names:
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)

    def test_real_cli_full_batches_and_negative_cases_in_rom_only_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();self.clone(root);run=init_run(root,'relocation-test','full')
            db=root/'unrelated.db';db.write_bytes(b'not an editor database')
            env={**os.environ,'DB_PATH':str(db),'BUILD_OUTPUT_DIR':str(root/'unrelated-output')}
            done=subprocess.run([sys.executable,str(root/auditor.SCRIPT),'--root',str(root),'--run',str(run)],
                                cwd=root,env=env,capture_output=True,text=True,check=False)
            self.assertEqual(done.returncode,0,done.stderr+done.stdout[-1000:])
            r=json.loads(done.stdout);self.assertTrue(r['verified'])
            self.assertEqual(r['summary']['resources'],166)
            self.assertEqual(r['summary']['physical_sources'],217)
            self.assertEqual(r['summary']['logical_references'],249)
            self.assertEqual(r['summary']['actual_build_cli_cases'],9)
            self.assertEqual(r['summary']['accepted_batches'],4)
            self.assertEqual(r['summary']['rejected_cases'],5)
            self.assertEqual(r['resource_ids_total'],r['resource_ids_checked'])
            self.assertEqual(len(set(r['resource_ids_total'])),166)
            self.assertEqual(len(r['overflow_resource_ids_total']),96)
            self.assertEqual(r['overflow_resource_ids_checked'],r['overflow_resource_ids_total'])
            self.assertEqual([x['resources_relocated'] for x in r['accepted']],[166,166,96,1])
            for row in r['accepted']:
                self.assertEqual(row['output_size'],0x1000000)
                self.assertTrue(row['whole_rom_exact'])
                self.assertTrue(row['all_249_logical_references_redecoded'])
                self.assertTrue(row['all_217_old_sources_unchanged'])
                self.assertTrue(row['allocation_ledger_exact'])
            for row in r['rejected']:
                self.assertFalse(row['output_rom_present']);self.assertFalse(row['output_report_present'])
            self.assertFalse(r['runtime_executed']);self.assertFalse(r['full_graphics_release_gate_complete'])
            self.assertFalse(r['computed_or_unaligned_consumers_exhausted'])
            self.assertEqual(db.read_bytes(),b'not an editor database');self.assertFalse((root/'unrelated-output').exists())
            self.assertEqual(r,json.loads((run/'roundtrip/result.json').read_text()))
            with self.assertRaises(FileExistsError):auditor.run_roundtrip(root,run)

    def test_actual_rom_and_ledger_faults_are_not_verified(self):
        real=auditor._build_cli
        for fault,message in [('old-source','independently rebuilt ROM'),
                              ('missing-alias','allocation/pointer ledger'),
                              ('wrong-owner','allocation/pointer ledger'),
                              ('partial-reject','atomically rejected')]:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as directory:
                root=Path(directory).resolve();self.clone(root);run=init_run(root,'relocation-test','fault')
                def broken(fixture,name,specs,**options):
                    done,case=real(fixture,name,specs,**options)
                    if done.returncode==0:
                        if fault=='old-source':
                            b=bytearray((case/'output.gba').read_bytes());b[0xB9F80]^=1;(case/'output.gba').write_bytes(b)
                        elif fault in ['missing-alias','wrong-owner']:
                            p=case/'build-report.json';r=json.loads(p.read_text())
                            if fault=='missing-alias':r['applied_patches'].pop()
                            else:r['applied_patches'][0]['allocation_region_owner']='foreign'
                            p.write_text(json.dumps(r))
                    elif fault=='partial-reject':(case/'output.gba').write_bytes(b'partial')
                    return done,case
                with patch.object(auditor,'_build_cli',side_effect=broken):
                    with self.assertRaisesRegex(ValueError,message):auditor.run_roundtrip(root,run)
                self.assertFalse((run/'roundtrip/result.json').exists())

    def test_frozen_input_and_run_guards_fail_before_materialization(self):
        for kind in ['contract','implementation','missing','symlink','inactive','unmanaged']:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as directory:
                root=Path(directory).resolve();self.clone(root);run=init_run(root,'relocation-test','guard')
                target=root/'tools/import_map_resource_relocations.py'
                if kind in ['contract','implementation']:
                    target=root/auditor.CONTRACT if kind=='contract' else target
                    with target.open('ab') as stream:stream.write(b' ')
                elif kind in ['missing','symlink']:
                    target.unlink()
                    if kind=='symlink':target.symlink_to(ROOT/'tools/import_map_resource_relocations.py')
                elif kind=='inactive':
                    p=run/'.experiment.json';m=json.loads(p.read_text());m['status']='completed';p.write_text(json.dumps(m))
                else:run=root/'outside'
                with self.assertRaises((ValueError,OSError)):auditor.run_roundtrip(root,run)
                self.assertFalse((run/'roundtrip').exists())

    def test_cli_missing_inputs_is_json_failure(self):
        with tempfile.TemporaryDirectory() as d:
            done=subprocess.run([sys.executable,str(ROOT/auditor.SCRIPT),'--root',d,'--run',d],capture_output=True,text=True,check=False)
            self.assertEqual(done.returncode,1)
            r=json.loads(done.stdout);self.assertFalse(r['verified']);self.assertTrue(r['errors'])


if __name__=='__main__':unittest.main()
