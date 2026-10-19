from pathlib import Path
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tools import audit_map_resource_fixed_roundtrip as auditor
from tools.experiment_workspace import init_run

ROOT = Path(__file__).resolve().parents[1]


class LinkedDomainTests(unittest.TestCase):
    def example(self):
        contents = {'tile_graphics':bytes(64),'bg_palette':bytes(32),
                    'metatile_definitions':bytes(16),'collision_grid':bytes(2),
                    'primary_layout':bytes(4)}
        sources = {r:{'sha256':r} for r in contents}
        sources['alternate_layout'] = None
        cat = {'entries':[{'map_id':7,'dimensions_tiles':[4,2],'resources':sources}]}
        return cat, {(r,r):b for r,b in contents.items()}

    def test_valid_domain_and_flip_flags(self):
        cat, contents = self.example()
        self.assertEqual(auditor.linked_domain(cat,contents), [])
        for value in [0x0401,0x0801,0x0C01]:
            replacement = value.to_bytes(2,'little') + bytes(14)
            self.assertEqual(auditor.linked_domain(cat,contents,
                             {('metatile_definitions','metatile_definitions'):replacement}), [])

    def test_size_indices_and_palette_boundaries(self):
        cat, contents = self.example()
        cases = [('primary_layout',(2).to_bytes(4,'little'),'layout-metatile-index'),
                 ('primary_layout',(2<<16).to_bytes(4,'little'),'layout-metatile-index'),
                 ('metatile_definitions',(2).to_bytes(2,'little')+bytes(14),'metatile-tile-index'),
                 ('metatile_definitions',(0x1000).to_bytes(2,'little')+bytes(14),'metatile-palette-bank'),
                 ('collision_grid',bytes(4),'collision-size'),
                 ('primary_layout',bytes(8),'layout-size')]
        for role,content,kind in cases:
            with self.subTest(role=role,kind=kind):
                errors = auditor.linked_domain(cat,contents,{(role,role):content})
                self.assertTrue(errors)
                self.assertEqual(errors[0]['kind'],kind)
                self.assertEqual(errors[0]['map_id'],7)

    def test_every_logical_alias_is_checked(self):
        cat, contents = self.example()
        other = copy.deepcopy(cat['entries'][0]); other['map_id']=8
        other['resources']['tile_graphics']={'sha256':'small'}
        cat['entries'].append(other)
        contents['tile_graphics','small']=bytes(32)
        mutation=(1).to_bytes(2,'little')+bytes(14)
        errors=auditor.linked_domain(cat,contents,{('metatile_definitions','metatile_definitions'):mutation})
        self.assertEqual([e['map_id'] for e in errors],[8])


class MapRoundtripTests(unittest.TestCase):
    def clone(self,root):
        names=set(json.loads((ROOT/auditor.CONTRACT).read_text())['inputs'])|{auditor.CONTRACT,auditor.SCRIPT}
        for name in names:
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/name,target)

    def test_full_matrix_in_relocated_root_real_cli_and_isolated_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();self.clone(root)
            run=init_run(root,'map-test','matrix')
            db=root/'unrelated.db';db.write_bytes(b'not an editor database')
            environment={**os.environ,'DB_PATH':str(db),'BUILD_OUTPUT_DIR':str(root/'unrelated-output')}
            completed=subprocess.run([sys.executable,str(root/auditor.SCRIPT),'--root',str(root),'--run',str(run)],
                                     cwd=root,env=environment,capture_output=True,text=True,check=False)
            self.assertEqual(completed.returncode,0,completed.stderr+completed.stdout[-1000:])
            result=json.loads(completed.stdout)
            self.assertTrue(result['verified'])
            self.assertEqual(result['summary']['resources'],166)
            self.assertEqual(result['summary']['physical_slots'],217)
            self.assertEqual(result['summary']['logical_references'],249)
            self.assertEqual(result['summary']['actual_build_cli_cases'],167)
            self.assertEqual(result['summary']['mutation_accepted_resources'],70)
            self.assertEqual(result['summary']['mutation_capacity_rejected_resources'],96)
            self.assertEqual(result['summary']['mutation_domain_rejected_resources'],0)
            self.assertEqual(result['resource_ids_total'],result['resource_ids_checked'])
            self.assertEqual(len(set(result['resource_ids_total'])),166)
            self.assertTrue(result['all_resource_noop_rom_exact'])
            self.assertFalse(result['runtime_executed'])
            self.assertFalse(result['full_graphics_release_gate_complete'])
            self.assertFalse(result['arbitrary_edit_capacity_complete'])
            self.assertEqual(db.read_bytes(),b'not an editor database')
            self.assertFalse((root/'unrelated-output').exists())
            self.assertEqual(result,json.loads((run/'roundtrip/result.json').read_text()))
            for row in result['rows']:
                self.assertTrue(row['linked_domain_valid'])
                if row['mutation_accepted']:
                    self.assertTrue(row['all_target_aliases_redecoded'])
                    self.assertTrue(row['outside_target_slots_unchanged'])
                    self.assertTrue(row['pointer_table_unchanged'])
                else:
                    self.assertFalse(row['output_rom_present'])
                    self.assertFalse(row['output_report_present'])
                    self.assertEqual(row['rejection_class'],'capacity')
            with self.assertRaises(FileExistsError):auditor.run_roundtrip(root,run)

    def test_real_output_faults_fail_without_publishing_verified_result(self):
        real_build=auditor._build_cli
        for fault,message in [('outside-slot','outside independently rebuilt'),
                              ('missing-alias-report','bind all physical aliases'),
                              ('rejected-output','atomically rejected')]:
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                root=Path(directory).resolve();self.clone(root);run=init_run(root,'map-test','fault')
                def broken(fixture,name,edits,**recipe):
                    done,case=real_build(fixture,name,edits,**recipe)
                    if name=='all-resource-noop':return done,case
                    if done.returncode==0:
                        if fault=='outside-slot':
                            data=bytearray((case/'output.gba').read_bytes());data[0x10]^=1
                            (case/'output.gba').write_bytes(data)
                        elif fault=='missing-alias-report':
                            report=json.loads((case/'build-report.json').read_text());report['applied_patches']=[]
                            (case/'build-report.json').write_text(json.dumps(report))
                    elif fault=='rejected-output':(case/'output.gba').write_bytes(b'partial')
                    return done,case
                with patch.object(auditor,'_build_cli',side_effect=broken):
                    with self.assertRaisesRegex(ValueError,message):auditor.run_roundtrip(root,run)
                self.assertFalse((run/'roundtrip/result.json').exists())

    def test_actual_cli_rejects_linked_indices_before_capacity_and_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();self.clone(root)
            _, inputs=auditor._inputs(root)
            fixture=root/'fixture';fixture.mkdir()
            auditor._fixture_inputs(fixture,inputs,(*auditor.TOOLCHAIN,'rom/base.gba',auditor.CATALOG))
            capacity=auditor.independent._expected_payload(root)
            catalog=json.loads(inputs[auditor.CATALOG])
            contents={(r['resource_type'],r['resource_sha256']):inputs[auditor._source_path(r)]
                      for r in capacity['resources']}
            for role,word in [('primary_layout',0xFFFF),('alternate_layout',0xFFFF),
                              ('metatile_definitions',0x03FF),('metatile_definitions',0xF000)]:
                row=next(r for r in capacity['resources'] if r['resource_type']==role)
                content=bytearray(contents[role,row['resource_sha256']]);content[:2]=word.to_bytes(2,'little')
                errors=auditor.linked_domain(catalog,contents,{(role,row['resource_sha256']):bytes(content)})
                self.assertTrue(errors)
                name=f'invalid-{role}-{word}'
                target=fixture/'cases'/name/'edited.bin';target.parent.mkdir(parents=True)
                target.write_bytes(content)
                done,case=auditor._build_cli(fixture,name,[auditor._edit(row,f'cases/{name}/edited.bin')],**auditor.RECIPE)
                self.assertNotEqual(done.returncode,0)
                self.assertTrue(auditor.rejection_matches(errors,done.stderr),done.stderr)
                self.assertNotIn('does not fit every physical slot',done.stderr)
                self.assertFalse((case/'output.gba').exists())
                self.assertFalse((case/'build-report.json').exists())

    def test_identity_missing_symlink_and_managed_state_fail_before_build(self):
        for kind in ['contract','implementation','missing','symlink','inactive','unmanaged']:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root=Path(directory).resolve();self.clone(root);run=init_run(root,'map-test','guard')
                target=root/'tools/import_map_resources.py'
                if kind in ['contract','implementation']:
                    target=root/auditor.CONTRACT if kind=='contract' else target
                    with target.open('ab') as stream:stream.write(b' ')
                elif kind in ['missing','symlink']:
                    target.unlink()
                    if kind=='symlink':target.symlink_to(ROOT/'tools/import_map_resources.py')
                elif kind=='inactive':
                    p=run/'.experiment.json';value=json.loads(p.read_text());value['status']='completed';p.write_text(json.dumps(value))
                else:run=root/'outside'
                with self.assertRaises((ValueError,OSError)):auditor.run_roundtrip(root,run)
                self.assertFalse((run/'roundtrip').exists())


if __name__=='__main__':unittest.main()
