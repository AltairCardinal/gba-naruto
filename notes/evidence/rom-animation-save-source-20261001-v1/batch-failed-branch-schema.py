"""Batch source identities, scheduler binding and full-entry finite save cases."""
import ast
import contextlib
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path.cwd().resolve()
HERE = Path(__file__).resolve().parent
PARENT = ROOT / 'notes/evidence/rom-animation-writer-domain-20261001-v1'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
import save_source as probe
from tools.verify_rom_cfg_proven_roots_v6 import verify_rom_cfg_proven_roots_v6
from tools.verify_rom_task_scheduler_core_bundle import verify_artifact_bundle
from tools.verify_rom_scheduler_callback_lifecycle_gate import verify_scheduler_callback_lifecycle_gate
from tools.thumb_branch import iter_thumb_direct_branches

PROGRESS = sys.stdout
IMPLEMENTATIONS = ('save_source.py','batch.py','test_save_source.py')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()


def compact(family, inputs, trace):
    return {'family':family,'input':inputs,'trace_sha256':sha(encode(trace)),
            'instruction_count':len(trace['visited']),'write_count':len(trace['writes']),
            'stop':trace['stop'],'final_sp':trace['registers'][13],
            'counter':trace.get('counter'),'saved':trace.get('saved'),
            'callee_targets':trace.get('callee_targets'),
            'task_marker_stores':trace.get('task_marker_stores'),
            'natural_execution_proven':False,'context_resume_proven':False}


def main(output):
    output = Path(output)
    if output.exists():
        raise ValueError('fresh output required')
    output.mkdir()
    for name in IMPLEMENTATIONS:
        raw=(HERE/name).read_bytes();ast.parse(raw)
        assert all(line==line.rstrip() for line in raw.decode().splitlines())
    import test_save_source
    tests=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_save_source))
    assert tests.wasSuccessful() and tests.testsRun==12
    inputs={}
    def read(name,expected=None):
        name=str(name);raw=(ROOT/name).read_bytes()
        if expected is not None:
            assert sha(raw)==expected,name
        inputs[name]={'size':len(raw),'sha256':sha(raw)}
        return raw
    manifest=json.loads(read(PARENT.relative_to(ROOT)/'manifest.json','b6ff4a622e59440301e0452e9c0df2c291047a7d3e8832de18fa817db3eaf6db'))
    for name,identity in manifest['files'].items():
        assert len(read(PARENT.relative_to(ROOT)/name,identity['sha256']))==identity['size']
    broad=json.loads((PARENT/'writer-domain.json').read_text())
    for name,identity in broad['inputs'].items():
        assert len(read(name,identity['sha256']))==identity['size']
    for folder in ('rom-task-scheduler-core-v1','rom-cfg-proven-roots-v6'):
        for path in sorted((ROOT/'artifacts'/folder).iterdir()):
            assert path.is_file() and not path.is_symlink()
            read(path.relative_to(ROOT))
    for module in list(sys.modules.values()):
        name=getattr(module,'__file__',None)
        if name:
            path=Path(name).resolve()
            if path.is_relative_to(ROOT/'tools') and path.is_file() and '__pycache__' not in path.parts:
                read(path.relative_to(ROOT))
    print('input identities checked',len(inputs),file=PROGRESS,flush=True)
    checks={'source_v6':verify_rom_cfg_proven_roots_v6(ROOT,ROOT/'artifacts/rom-cfg-proven-roots-v6'),
            'scheduler_bundle':verify_artifact_bundle(ROOT,ROOT/'artifacts/rom-task-scheduler-core-v1'),
            'callback_gate':verify_scheduler_callback_lifecycle_gate(ROOT)}
    assert all(row['verified'] for row in checks.values()),checks
    assert checks['callback_gate']['decision']['blocking_callback']=='0x0808F654'
    print('three independent source/lifecycle verifiers passed; 8F654 stays open',file=PROGRESS,flush=True)
    rom=read('rom/base.gba',broad['rom_sha256'])
    windows={'save_callback':(0x8584C,0x859B0),'status':(0x64A48,0x64A5C),'restore':(0x857E4,0x8584A),
             'cleanup':(0x61E00,0x61E1C),'saved_init':(0x857B8,0x857D0),
             'registration_wrapper':(0x61D7C,0x61D8C),'registration_inner':(0x61D8C,0x61DEA),
             'registration_producer':(0x859B8,0x85A1E),'postbattle_candidate':(0x68DE4,0x68DF8),
             'chapter_wrapper_candidate':(0x8F618,0x8F64C),'open_callback_candidate':(0x8F654,0x8F68A)}
    graphs={}
    for name,(a,b) in windows.items():
        graph=probe.closure(rom,a,b)
        assert probe.raw_closure(rom,a,b)==graph['nodes'],name
        graphs[name]={**graph,'window_bytes_sha256':sha(rom[a:b]),
                      'instruction_bytes_sha256':sha(b''.join(rom[n:n+(4 if int.from_bytes(rom[n:n+2],'little')&0xF800==0xF000 else 2)] for n in graph['nodes'])),
                      'literal_values':{word:int.from_bytes(rom[word:word+4],'little') for word in graph['literal_words']},
                      'entry_proven':name not in ('postbattle_candidate','chapter_wrapper_candidate','open_callback_candidate'),
                      'natural_execution_proven':False,'source_ranges_not_coverage_claims':True}
    source=json.loads(read('artifacts/rom-cfg-proven-roots-v6/rom-cfg-proven-roots-v6.json'))
    for at in (0x859B8,0x85A04,0x85A06,0x85A08):
        assert any(row['mode']=='thumb' and row['range'][0]<=at<row['range'][1]
                   for row in source['extension']['blocks']),hex(at)
        assert at in graphs['registration_producer']['nodes']
    bound=probe.binding(rom);bound_trace=bound.pop('trace')
    bound['trace_sha256']=sha(encode(bound_trace));bound['writes']=bound_trace['writes']
    assert bound['callback']==0x0808584D and bound['record_entry']==0x08061CBD and bound['argument']==0
    cases=[]
    for counter in range(256):
        params={'counter':counter,'saved':0,'guard':0,'wait':0}
        stored=probe.save(rom,**params);assert stored['counter']==1 and stored['saved']==counter
        cases.append(compact('save',params,stored))
        restore_params={'counter':stored['counter'],'saved':stored['saved'],'guard':0x303,'wait':0}
        restored=probe.save(rom,**restore_params)
        assert restored['counter']==(counter if counter else 1) and restored['saved']==0
        cases.append(compact('roundtrip_restore',restore_params,restored))
        if counter%64==63:
            print('save/restore counter values',counter+1,file=PROGRESS,flush=True)
    for saved in (1,128,255):
        params={'counter':173,'saved':saved,'guard':0,'wait':0}
        trace=probe.save(rom,**params);assert (trace['counter'],trace['saved'])==(173,saved)
        cases.append(compact('existing_saved',params,trace))
    flag_cases={'mixed':[0xA5000000|(n&3) for n in range(128)],'all_active':[0xFFFFFFFF]*128,
                'all_inactive':[0xFFFFFFFE]*128,'only_last':[1 if n==127 else 0 for n in range(128)]}
    freeze=[]
    for label,flags in flag_cases.items():
        params={'counter':173,'saved':201,'guard':0,'wait':59,'flag_words':flags}
        trace=probe.save(rom,**params)
        assert trace['stop']==0x858E4 and (trace['counter'],trace['saved'])==(173,0)
        expected=[probe.POOL+60*n for n,value in enumerate(flags) if value&1]
        writes=[w for w in trace['writes'] if probe.POOL<=w['address']<probe.POOL+60*128]
        assert [w['address'] for w in writes]==expected and trace['task_marker_stores']==8
        assert [r['after'] for r in trace['pool_flags']]==[v|8 if v&1 else v for v in flags]
        cases.append(compact('timeout_'+label,params,trace))
        freeze.append({'label':label,'pool_store_addresses':expected,'pool_flags':trace['pool_flags'],
                       'task_marker_writes':[w for w in trace['writes'] if 0x03000A88<=w['address']<0x03000A88+8*0x4C],
                       'callee_targets':trace['callee_targets'],'stop':trace['stop']})
    params={'counter':173,'saved':201,'guard':0,'wait':0,'busy':1}
    trace=probe.save(rom,**params);assert (trace['counter'],trace['saved'])==(173,201)
    cases.append(compact('busy',params,trace))
    post=probe.postbattle(rom,counter=173);cases.append(compact('postbattle_candidate',{'counter':173},post))
    targets=(0x68DE4,0x8584C,0x8F618,0x8F654)
    producers={at:[] for at in targets}
    for row in iter_thumb_direct_branches(rom,rom_base=0):
        if row.target in producers:
            producers[row.target].append({'at':row.address,'kind':row.kind})
    pointers={at:[] for at in targets}
    for root in targets:
        token=(0x08000000+root+1).to_bytes(4,'little');at=rom.find(token)
        while at>=0:
            pointers[root].append(at);at=rom.find(token,at+1)
    for name,identity in inputs.items():
        raw=(ROOT/name).read_bytes();assert len(raw)==identity['size'] and sha(raw)==identity['sha256'],name
    result={'schema':'animation-save-source-lifecycle-v1','rom_sha256':sha(rom),'inputs':inputs,
            'implementation_inputs':{name:sha((HERE/name).read_bytes()) for name in IMPLEMENTATIONS},
            'source_checks':checks,'source_graphs':graphs,'callback_binding':bound,'cases':cases,
            'freeze_cases':freeze,'direct_producer_shapes':producers,'thumb_pointer_occurrences':pointers,
            'facts':{'save_counter_domain_cases':256,'save_restore_roundtrips':256,
                     'original_zero_restores_to_one_under_fixture':True,'freeze_object_scan_count':128,
                     'cleanup_task_slots':[1,2,3,4],'save_callback_registered_slot':5,
                     'save_callback_bounded_source_from_fixed_registration':True,
                     'postbattle_68de4_entry_proven':False,'blocking_entry':0x8F654,
                     'counter_binary_natural_domain_proven':False,'global_writer_exhaustiveness_proven':False,
                     'same_context_resume_proven':False},'natural_execution_proven':False,
            'runtime_launches':0,'promotion_bytes':0}
    (output/'save-source.json').write_bytes(encode(result))
    print('RESULT',len(cases),'raw cases; source nodes',len(set(n for graph in graphs.values() for n in graph['nodes'])),file=PROGRESS,flush=True)


if __name__=='__main__':
    with Path(sys.argv[2]).open('x') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:
            main(Path(sys.argv[1]))
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
