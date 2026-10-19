"""Joint finite native object lifecycle, lookups, callbacks and sentinel footprints."""
import ast
import contextlib
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
ROOT=Path.cwd().resolve()
sys.path[:0]=[str(HERE),str(ROOT)]
import object_native as p
from tools.verify_rom_cfg_inventory import verify_rom_cfg_inventory
from tools.verify_rom_text_bg_task_closure import verify_artifact as verify_long
from tools.verify_rom_cfg_proven_roots_v20 import verify_root as verify_v20


def encode(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def sort_oracle(flags,keys,alt):
    result=[]
    signed=lambda k:(k&65535)-65536 if k&0x8000 else k&65535
    for candidate in range(128):
        cf=flags[candidate]
        if not cf&1:
            continue
        pos=len(result)
        ck=signed(alt[candidate] if cf&0x2000000 else keys[candidate])
        while pos:
            previous=result[pos-1]
            pf=flags[previous]
            cp,pp=(cf&0xC0,cf&0x300),(pf&0xC0,pf&0x300)
            shift=cp<pp or (cp==pp and cf&0x40000 and (not pf&0x40000 or ck>signed(alt[previous] if pf&0x2000000 else keys[previous])))
            if not shift:
                break
            pos-=1
        result.insert(pos,candidate)
    return result


def main(output):
    output=Path(output)
    if output.exists():
        raise ValueError('fresh output required')
    output.mkdir()
    inputs={}
    def read(path,expected=None):
        path=Path(path)
        full=path if path.is_absolute() else ROOT/path
        raw=full.read_bytes()
        if expected and sha(raw)!=expected:
            raise ValueError(f'input identity {path}')
        inputs[str(path)]={'size':len(raw),'sha256':sha(raw)}
        return raw
    for directory,digest,authority in (
        ('rom-animation-irq-arm-native-20261001-v2','df5c56b0dc8e76a4460c706cec5a89bb03c313b457b1af58698924016740373f','irq-arm-native.json'),
        ('rom-animation-object-lifecycle-20261001-v1','7c34067d76ae81ecc15d03b9681295e78ac8971df2d05e59c024e3a69c12db8b','lifecycle.json')):
        folder=Path('notes/evidence')/directory
        manifest=json.loads(read(folder/'manifest.json',digest))
        for name,identity in manifest['files'].items():
            assert len(read(folder/name,identity['sha256']))==identity['size']
        data=json.loads(read(folder/authority))
        for name,identity in data['inputs'].items():
            assert len(read(name,identity['sha256']))==identity['size']
    oldpool=Path('notes/evidence/rom-animation-pool-lifecycle-20261001-v1')
    audit=json.loads(read(oldpool/'audit.json'))
    oldvalidation=json.loads(read(oldpool/'validation.json'))
    for name,identity in audit['inputs'].items():
        assert len(read(name,identity['sha256']))==identity['size']
    for folder in ('rom-text-bg-task-closure-v1','rom-cfg-proven-roots-v20'):
        for path in sorted((ROOT/'artifacts'/folder).rglob('*')):
            if path.is_file():read(path.relative_to(ROOT))
    provider=json.loads((HERE/'provider-contract.json').read_text())
    for name,identity in provider['files'].items():
        assert len(read(name,identity['sha256']))==identity['size']
    assert sha((HERE/'mgba-arm-probe').read_bytes())==provider['native_binary_sha256']
    for name in ('object_native.py','batch.py','test_object_native.py'):
        raw=(HERE/name).read_bytes();ast.parse(raw)
        assert all(line==line.rstrip() for line in raw.decode().splitlines()),name
    import test_object_native
    tests=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_object_native))
    assert tests.wasSuccessful() and tests.testsRun==16
    print('VERIFY fixed lifecycle and long-callback source graphs',flush=True)
    sources={
        'v2_lifecycle':verify_rom_cfg_inventory(ROOT,ROOT/'artifacts/rom-cfg-inventory-v2'),
        'long_callback':verify_long(ROOT,ROOT/'artifacts/rom-text-bg-task-closure-v1'),
        'v20_dependency':verify_v20(ROOT,ROOT/'artifacts/rom-cfg-proven-roots-v20')}
    assert all(x['verified'] for x in sources.values()),sources
    certificate=p.lookup_certificate(p.ROM)
    records=[]
    rawfile=(output/'native-traces.jsonl.gz').open('xb')
    archive=gzip.GzipFile(filename='',mode='wb',fileobj=rawfile,mtime=0)
    def record(family,parameters,row):
        fixture=row.pop('input')
        raw=encode({'family':family,'parameters':parameters,'input':fixture,'trace':row})
        archive.write(raw)
        records.append({'family':family,'parameters':parameters,'input_sha256':sha(encode(fixture)),
                        'record_sha256':sha(raw),'instruction_steps':len(row['visited']),
                        'reads':len(row['reads']),'writes':len(row['writes'])})
    print('RUN 258 allocator cases',flush=True)
    for alternate in (False,True):
        fixtures=[p.allocation_fixture(free=i,context=0xA1234567,alternate=alternate) for i in range(128)]
        fixtures.append(p.allocation_fixture(free=None,alternate=alternate))
        for free,row in enumerate(p.execute(fixtures)):
            handle=0 if free==128 else p.POOL+free*60
            assert row['registers'][0]==handle
            if handle:
                assert p.values(row)[(handle+0x2C,4)]==0xA1234567
            assert row['registers'][13]==p.SP
            record('allocate',[alternate,free if free<128 else None],row)
    print('RUN all u8 needles at ten matches and no-match',flush=True)
    for needle in range(256):
        fixtures=[]
        for target in range(11):
            tags=[needle if i==target else needle^255 for i in range(10)]
            fixtures.append(p.fixture(0x655B4,[(0x655B4,0x655F0)],regs={0:needle},
                                      memory=[[1,p.MANAGER+i*0x4D0+0x13,t] for i,t in enumerate(tags)]))
        for target,row in enumerate(p.execute(fixtures)):
            assert row['registers'][0]==p.MANAGER+target*0x4D0
            tags=[r['address'] for r in row['reads'] if r.get('pc') in (p.BASE+0x655BE,p.BASE+0x655DC)]
            assert all(p.MANAGER<=a<p.MANAGER+10*0x4D0 for a in tags)
            record('manager-lookup',[needle,target],row)
    print('RUN 768 callback fast paths including actual embedded BIOS initialization',flush=True)
    for context in (0,1,65535):
        for slot in range(256):
            row=p.callback(context=context,manager_slot=slot,last_slot=0,pending=0)
            assert row['own_fields'][0x2C]==(16 if context==0 else context)
            assert (p.BASE+0x9C0E0 in row['visited'])==(context==0)
            if context==0:
                writes=[w for w in row['writes'] if isinstance(w,list) and p.MANAGER+3*0x4D0+0x1E<=w[2]<p.MANAGER+3*0x4D0+0x1E+234]
                assert len(writes)==117 and [(w[2],w[1],w[3]) for w in writes]==[(p.MANAGER+3*0x4D0+0x1E+2*i,2,1) for i in range(117)]
            record('callback-fast',[context,slot],row)
    print('RUN callback tail byte boundaries and handle alias roles',flush=True)
    metadata={(v,1,1) for v in range(256)}|{(1,v,1) for v in range(256)}|{(1,1,v) for v in range(256)}
    metadata|={(a,b,c) for a in (0,255) for b in (0,255) for c in (0,255)}
    for triplet in sorted(metadata):
        row=p.callback_tail(meta2=triplet[0],meta3=triplet[1],meta12=triplet[2])
        record('callback-tail',list(triplet),row)
    for pattern in ((127,127,125),(127,126,127),(127,126,126),(127,127,127)):
        for triplet in ((0,0,0),(0,1,1),(1,0,1),(255,255,255)):
            row=p.callback_tail(meta2=triplet[0],meta3=triplet[1],meta12=triplet[2],handles=[p.POOL+60*i for i in pattern])
            record('callback-tail-alias',[list(pattern),list(triplet)],row)
    print('RUN full scan and sort against separate insertion oracle',flush=True)
    sort_cases=[]
    for mode in (0,0x40000,0x2040000):
        for keymode in ('ascending','descending','signed-boundaries','equal'):
            flags=[mode|1]*128
            keys=list(range(128)) if keymode=='ascending' else list(reversed(range(128))) if keymode=='descending' else [0,32767,32768,65535][0:]*32 if keymode=='signed-boundaries' else [17]*128
            sort_cases.append((flags,keys,[-k for k in keys],mode,keymode))
    for seed in range(8):
        flags=[((i*17+seed)%4)|(((i+seed)%4)*0x40)|(((i*3+seed)%4)*0x100)| (0x40000 if i%3 else 0) | (0x2000000 if i%5 else 0) for i in range(128)]
        keys=[(i*719+seed*997)&65535 for i in range(128)]
        sort_cases.append((flags,keys,[k^65535 for k in keys],seed,'mixed'))
    for flags,keys,alt,mode,keymode in sort_cases:
        row=p.sort_pool(flags,keys,alternate_keys=alt)
        assert row['order']==sort_oracle(flags,keys,alt),(mode,keymode,row['order'])
        assert row['registers'][13]==p.SP
        record('full-scan-sort',[mode,keymode],row)
    for context in (0,1,16,65535,0xA1234567):
        for stage,row in enumerate(p.lifecycle_chain(context=context)):
            record('persistent-lifecycle',[context,stage],row)
    print('RUN 672 native vs bounded Thumb advance cases',flush=True)
    lifecycle=ROOT/'notes/evidence/rom-animation-object-lifecycle-20261001-v1'
    sys.path.insert(0,str(lifecycle))
    spec=importlib.util.spec_from_file_location('legacy_advance_probe',lifecycle/'advance_probe.py')
    legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
    fixtures=[]
    obj=p.POOL+127*60
    for old in oldvalidation['probe_matrix']:
        fixtures.append(p.fixture(0x63238,[(0x63238,0x632F8),(0x62798,0x627AA)],stop=p.BASE+0x632F8,budget=20000,regs={7:obj},
            memory=[[4,obj,old['flags']],[2,obj+0x18,old['initial_timer']],[1,0x03000075,old['count']],[4,p.SP,p.BASE+old['sequence']]],
            peek=[[4,obj],*[[2,obj+off] for off in (0x14,0x16,0x18)]]))
    suffixes=set()
    for start,end in p.SOURCE:
        if not (start<0x632F8 and end>0x62798):continue
        at=max(start,0x62798)
        while at<min(end,0x632F8):
            node=p._decode(p.ROM,at,'thumb')
            if node['size']==4:suffixes.add(at+2)
            at+=node['size']
    for begin in range(0,len(fixtures),32):
        rows=p.execute(fixtures[begin:begin+32])
        for old,row in zip(oldvalidation['probe_matrix'][begin:begin+32],rows,strict=True):
            expected=legacy.probe(p.ROM,old['sequence'],flags=old['flags'],count=old['count'],timer=old['initial_timer'])
            data=p.values(row)
            assert [data[(obj,4)],data[(obj+0x14,2)],data[(obj+0x16,2)],data[(obj+0x18,2)]]==[expected[k] for k in ('flags','group','slot','timer')]
            seqreads=[[r['address']-p.BASE,r['width']] for r in row['reads'] if p.BASE+old['sequence']<=r.get('address',0)<p.BASE+old['sequence']+8]
            assert seqreads==expected['sequence_reads']
            assert [a-p.BASE for a in row['visited'] if a-p.BASE not in suffixes]==expected['visited']
            record('advance-differential',[old['sequence'],old['flags'],old['count'],old['initial_timer']],row)
    print('RUN descriptor head paths for eight descriptors',flush=True)
    descriptors=[(r['group0_sequence_range'][0],r['base_pair'][0]) for r in audit['pair_rows']]
    descriptors.append((0x458484,0x458474))
    descriptor_reports=[]
    for sequence,table in descriptors:
        result=p.descriptor_heads(sequence=sequence,descriptor_table=table)
        for step,row in enumerate(result.pop('traces')):
            record('descriptor-head',[sequence,table,step],row)
        assert result['sentinel']+2 not in result['read_bytes']
        descriptor_reports.append(result)
    archive.close();rawfile.close()
    for module in list(sys.modules.values()):
        path=getattr(module,'__file__',None)
        if path:
            path=Path(path).resolve()
            if path.is_file() and path.is_relative_to(ROOT/'tools'):read(path.relative_to(ROOT))
    for name,identity in inputs.items():
        path=Path(name) if Path(name).is_absolute() else ROOT/name
        raw=path.read_bytes()
        assert len(raw)==identity['size'] and sha(raw)==identity['sha256'],name
    result={'schema':'rom-animation-object-native-v1','rom_sha256':sha(p.ROM),'inputs':inputs,'provider':provider,
            'source_checks':sources,'manager_leaf_certificate':certificate,'unit_tests':16,'cases':records,
            'descriptor_head_reports':descriptor_reports,'trace_archive':{'size':(output/'native-traces.jsonl.gz').stat().st_size,'sha256':sha((output/'native-traces.jsonl.gz').read_bytes())},
            'facts':{'allocator_keeps_callback_context':True,'inactive_scan_clears_bit1_only':True,'lookup_no_match_returns_index10':True,
                     'actual_allocated_callback_dispatched':True,'full_sort_return_checked':True,'advance_differential_cases':672,
                     'descriptor_body_rendered':False,'sequence_sentinel_suffix_may_be_read':True,'descriptor_head_width':2,
                     'persistent_ram_five_stage_chain':True,'manual_entry_registers_between_stages':True,
                     'whole_renderer_proven':False,'natural_handle_slot_domain_proven':False,'all_metadata_cross_product_tested':False,
                     'full_writer_domain_closed':False,'natural_execution_proven':False,'hardware_bios_proven':False,'promotion_bytes':0,'formal_rerun':False}}
    (output/'object-native.json').write_bytes(encode(result))
    print(f'PASSED {len(records)} native traces / 16 tests / 3 fresh source verifiers',flush=True)


if __name__=='__main__':
    with Path(sys.argv[2]).open('x') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        try:main(Path(sys.argv[1]))
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
