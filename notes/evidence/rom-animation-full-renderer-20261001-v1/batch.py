"""Complete single-object native renderer matrix, source checks and legacy advance comparison."""
import ast
import contextlib
import gzip
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import unittest

PROGRESS=sys.stdout
HERE=Path(__file__).resolve().parent
ROOT=Path.cwd().resolve()
sys.path[:0]=[str(HERE),str(ROOT)]
import full_renderer as p
from tools.verify_rom_cfg_inventory import verify_rom_cfg_inventory
from tools.verify_rom_text_bg_task_closure import verify_artifact as verify_long
from tools.verify_rom_cfg_proven_roots_v20 import verify_root as verify_v20


def encode(value):return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def progress(message):
    print(message,flush=True)
    if sys.stdout is not PROGRESS:print(message,file=PROGRESS,flush=True)


def main(output):
    output=Path(output)
    assert not output.exists()
    output.mkdir()
    inputs={}
    def read(path,expected=None):
        path=Path(path);full=path if path.is_absolute() else ROOT/path;raw=full.read_bytes()
        if expected and sha(raw)!=expected:raise ValueError(f'input identity {path}')
        inputs[str(path)]={'size':len(raw),'sha256':sha(raw)}
        return raw
    parent=Path('notes/evidence/rom-animation-object-native-20261001-v1')
    manifest=json.loads(read(parent/'manifest.json','fb75aefaa155ee21c43af4c4e7afa25d3e5410b10c5bcebd81946e39ce365a73'))
    for name,identity in manifest['files'].items():assert len(read(parent/name,identity['sha256']))==identity['size']
    prior=json.loads(read(parent/'object-native.json'))
    for name,identity in prior['inputs'].items():assert len(read(name,identity['sha256']))==identity['size']
    identity_folder=Path('notes/evidence/rom-animation-interprocedural-identities-20261001-v1')
    oldmanifest=json.loads(read(identity_folder/'manifest.json','1aca46ee19d8af2ddf051f1daa1fbfec1cd660245578020f689303116ff78e70'))
    for name,identity in oldmanifest['files'].items():assert len(read(identity_folder/name,identity['sha256']))==identity['size']
    callers=json.loads(read(identity_folder/'interprocedural-identities-v2.json'))['caller_rows']
    implementations={n:sha((HERE/n).read_bytes()) for n in ('full_renderer.py','test_full_renderer.py','batch.py')}
    for name in implementations:
        raw=(HERE/name).read_text();ast.parse(raw);assert all(s==s.rstrip() for s in raw.splitlines())
    import test_full_renderer
    tests=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_full_renderer))
    assert tests.wasSuccessful() and tests.testsRun==5
    progress('VERIFY v2 renderer / long callback / v20 dependency')
    sources={'v2_renderer':verify_rom_cfg_inventory(ROOT,ROOT/'artifacts/rom-cfg-inventory-v2'),
             'long_callback':verify_long(ROOT,ROOT/'artifacts/rom-text-bg-task-closure-v1'),
             'v20_dependency':verify_v20(ROOT,ROOT/'artifacts/rom-cfg-proven-roots-v20')}
    assert all(r['verified'] for r in sources.values()),sources
    life=ROOT/'notes/evidence/rom-animation-object-lifecycle-20261001-v1';sys.path.insert(0,str(life))
    spec=importlib.util.spec_from_file_location('independent_advance',life/'advance_probe.py')
    advance=importlib.util.module_from_spec(spec);spec.loader.exec_module(advance)
    domains=[(d,s,g) for (d,s),n in sorted(p.TABLE_DOMAINS.items()) for g in range(n)]
    # Explicit grids are finite fixtures, not natural producer domains or exhaustive hardware states.
    keys=set()
    for (d,s,g),flags,count,(x,y) in itertools.product(domains,(0,8,0x10,0x20,0x30,0x60,0x88,0x388,0x20020),(0,1,2,3,15,127,255),((0,0),(16,16),(239,159),(-1,-1),(256,160))):
        keys.add((d,s,g,flags,count,x,y,True,256,256,0))
    for (d,s,g),(sx,sy),angle,(x,y) in itertools.product(domains,((128,512),(512,128),(-128,256),(256,-128),(0,256),(256,0)),(0,1,63,64,127,128,192,255),((0,0),(16,16),(239,159))):
        keys.add((d,s,g,0x20,2,x,y,True,sx,sy,angle))
    accepted=[];excluded=[]
    for caller in callers:
        reason='flags unknown' if caller['flags'] is None else 'callback unknown' if caller['callback'] is None else 'short raw candidate is outside fixed source membership' if caller['callback']==0x0808EE41 else None
        if reason:
            excluded.append({'site':caller['site'],'reason':reason});continue
        assert caller['callback'] in (0,0x0808AA51)
        d,s=caller['base_pair'];g=caller['group']
        key=(d,s,g,caller['flags'],1,0,0,bool(caller['callback']),256,256,0)
        keys.add(key);accepted.append({'site':caller['site'],'parameters':list(key),'conditional_callee_preservation':caller['conditional_callee_preservation'],'natural_entry_proven':False})
    assert len(accepted)==29 and len(excluded)==18
    rows=[];frame_reports=[];families={'body':0,'skipped_body':0,'division_swi':0,'arm_bios_steps':0,'sequence_suffix_read':0}
    rawfile=(output/'full-traces.jsonl.gz').open('xb');archive=gzip.GzipFile(filename='',mode='wb',fileobj=rawfile,mtime=0)
    def record(key,stage,row):
        fixture=row.pop('input');raw=encode({'parameters':list(key),'stage':stage,'input':fixture,'trace':row})
        archive.write(raw);rows.append({'parameters':list(key),'stage':stage,'record_sha256':sha(raw),'input_sha256':sha(encode(fixture)),'steps':len(row['visited'])})
    ordered=sorted(keys)
    progress(f'RUN {len(ordered)} unique complete renderer frames')
    for number,key in enumerate(ordered):
        if number%128==0:progress(f'frame {number}/{len(ordered)}')
        d,s,g,flags,count,x,y,callback,sx,sy,angle=key
        row=p.frame(descriptor_table=d,sequence_table=s,group=g,flags=flags,count=count,x=x,y=y,callback=callback,scale_x=sx,scale_y=sy,angle=angle)
        allocated=row.pop('allocation');sequence=row['sequence'];descriptor=row['descriptor']
        expected=advance.probe(p.native.ROM,sequence,flags=flags|1,count=count)
        assert (row['slot'],row['timer'])==(expected['slot'],expected['timer'])
        # Legacy helper resets group to 0 only when mode30 actually reaches its terminal.
        reset=p.native.BASE+0x62798 in row['visited']
        assert row['group']==(0 if reset else g)
        assert row['flags']&~0x1000000==expected['flags']&~0x1000000
        seqreads=[[r['address']-p.native.BASE,r['width']] for r in row['reads'] if p.native.BASE+0x63238<=r['pc']<p.native.BASE+0x632F8 and p.native.BASE+sequence<=r.get('address',0)<p.native.BASE+sequence+8]
        assert seqreads==expected['sequence_reads']
        heads=[]
        for n in range(17):
            at=descriptor+20*n;heads.append(at)
            if p.native.ROM[at:at+2]==b'\xff\xff':break
        else:raise ValueError('finite descriptor bound')
        observed=[r['address']-p.native.BASE for r in row['reads'] if r.get('pc') in (p.native.BASE+0x629FC,p.native.BASE+0x631FE)]
        skip=bool(flags&0x20000) or sx==0 or sy==0
        assert observed==([] if skip else heads),(key,observed,heads)
        families['skipped_body' if skip else 'body']+=1
        for r in row['reads']:
            a=r.get('address',0)-p.native.BASE
            if descriptor<=a<heads[-1]+4:
                assert a+r['width']<=heads[-1]+2,('descriptor suffix read',key,r)
        families['division_swi']+=p.native.BASE+0x9C0E4 in row['visited']
        families['arm_bios_steps']+=sum(a<0x4000 for a in row['visited'])
        families['sequence_suffix_read']+=any(a==sequence+6 for a,w in seqreads)
        assert p.native.BASE+0x62924 in row['visited'] and p.native.BASE+0x63336 in row['visited']
        assert (p.native.BASE+0x8AA50 in row['visited'])==callback
        frame_reports.append({'parameters':list(key),'group':row['group'],'slot':row['slot'],'timer':row['timer'],'flags':row['flags'],
                              'descriptor':descriptor,'heads':observed,'descriptor_body_skipped':skip,
                              'advance_matches':True,'sequence_reads':seqreads,'division_swi':p.native.BASE+0x9C0E4 in row['visited'],
                              'bios_steps':sum(a<0x4000 for a in row['visited'])})
        record(key,'allocate',allocated);record(key,'full-renderer',row)
    archive.close();rawfile.close()
    assert families['division_swi']>0 and families['sequence_suffix_read']>0
    for module in list(sys.modules.values()):
        name=getattr(module,'__file__',None)
        if name:
            path=Path(name).resolve()
            if path.is_file() and path.is_relative_to(ROOT/'tools'):read(path.relative_to(ROOT))
    for name,identity in inputs.items():
        path=Path(name) if Path(name).is_absolute() else ROOT/name;raw=path.read_bytes()
        assert len(raw)==identity['size'] and sha(raw)==identity['sha256'],name
    assert implementations=={n:sha((HERE/n).read_bytes()) for n in implementations}
    result={'schema':'rom-animation-full-renderer-v1','rom_sha256':sha(p.native.ROM),'inputs':inputs,'implementation_inputs':implementations,
            'source_checks':sources,'provider':prior['provider'],'unit_tests':5,'native_trace_count':len(rows),'cases':rows,'frames':frame_reports,
            'family_counts':families,'conditional_caller_fixtures':accepted,'excluded_callers':excluded,
            'archive':{'size':(output/'full-traces.jsonl.gz').stat().st_size,'sha256':sha((output/'full-traces.jsonl.gz').read_bytes())},
            'facts':{'complete_62924_return_executed':True,'actual_callback_scan_sort_body_chain':True,'slot_timer_legacy_differential':True,
                     'descriptor_sentinel_suffix_read':False,'single_active_object_only':True,'source_stack_sp_disjoint_fixture_only':True,
                     'post_allocation_transform_fixture_writes':True,'all_external_writers_closed':False,'natural_entry_domain_proven':False,
                     'all_field_cross_products_exhausted':False,'hardware_bios_or_event_timing_proven':False,'bank_complete':False,'promotion_bytes':0,'formal_rerun':False}}
    (output/'full-renderer.json').write_bytes(encode(result))
    progress(f'PASSED {len(frame_reports)} full frames / {len(rows)} native traces / 5 tests')


if __name__=='__main__':
    with Path(sys.argv[2]).open('x') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        try:main(Path(sys.argv[1]))
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
