"""Reusable build recipe for hash-bound relocation fixtures.

Accept full importer specifications, an optional explicit layout and a shared
build manifest. Existing fixed-slot v1 remains frozen. This helper neither
allocates resources nor patches ROM bytes; the existing builder does both.
"""
import os
import subprocess
import sys
from tools.fixed_resource_roundtrip import _write


def build_cli(fixture,name,specs,*,patch_type,layout_path=None):
    """Relocation recipe adds frozen ownership/hash metadata and a ROM layout.

    Reuse v1 fixture writers. Its fixed-slot CLI recipe cannot express layout
    or multiple conflicting specifications; keep its frozen source unchanged.
    """
    case=fixture/'cases'/name;case.mkdir(parents=True,exist_ok=True)
    patches=[]
    for i,spec in enumerate(specs):
        _write(case/f'spec-{i}.json',spec)
        patches.append({'id':f'{name}-{i}','type':patch_type,'spec':f'cases/{name}/spec-{i}.json'})
    _write(case/'manifest.json',{'patches':patches})
    project={'project_id':name,'base_rom':{'path':'rom/base.gba','sha1':'26f60795fa5e63b4f0264b84e453beffd56b9f7d'},
             'patch_manifest':f'cases/{name}/manifest.json',
             'build':{'output_rom':f'cases/{name}/output.gba','report':f'cases/{name}/build-report.json'}}
    if layout_path is not None:project['rom_layout']=layout_path
    _write(case/'project.json',project)
    env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'LANG':'C','LC_ALL':'C','PYTHONHASHSEED':'0',
         'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(fixture),'DB_PATH':str(fixture/'sequel/absent-editor.db')}
    done=subprocess.run([sys.executable,str(fixture/'tools/build_mod.py'),'--project',f'cases/{name}/project.json'],
                        cwd=fixture,env=env,capture_output=True,text=True,timeout=90,check=False)
    (case/'stdout.txt').write_text(done.stdout);(case/'stderr.txt').write_text(done.stderr)
    return done,case

