"""Joint writer inventory, literal/raw producer denominator and finite domains."""
import ast
import contextlib
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT=Path.cwd().resolve()
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
import coupled_probe as probe
from tools.verify_rom_boot_thumb_handoff_cfg import verify_artifact
from tools.verify_rom_cfg_proven_roots_v14_bundle import verify_bundle
from tools.thumb_branch import decode_thumb_b,decode_thumb_bl

PROGRESS=sys.stdout
IMPLEMENTATIONS=('coupled_probe.py','coupled_batch.py','test_coupled_probe.py')


def sha(raw):return hashlib.sha256(raw).hexdigest()


def encode(value):return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()


def main(output):
    output=Path(output)
    if output.exists():raise ValueError('fresh output required')
    output.mkdir()
    for name in IMPLEMENTATIONS:
        raw=(HERE/name).read_bytes();ast.parse(raw)
        assert all(line==line.rstrip() for line in raw.decode().splitlines())
    import test_coupled_probe
    tests=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_coupled_probe))
    assert tests.wasSuccessful() and tests.testsRun==5
    raw=(HERE/'writer-domain.json').read_bytes()
    broad=json.loads(raw)
    assert sha(raw)=='f54b8e5ea44cf0ccecd57db66f9bef99b5a65e75c19d537e3f62df2bc2ff0caf', 'broad inventory identity changed'
    inputs=dict(broad['inputs'])
    for name,identity in inputs.items():
        data=(ROOT/name).read_bytes();assert len(data)==identity['size'] and sha(data)==identity['sha256'],name
    checks={
        'boot_thumb_handoff':verify_artifact(ROOT,ROOT/'artifacts/rom-boot-thumb-handoff-cfg-v1'),
        'vector_v14':verify_bundle(ROOT,ROOT/'artifacts/rom-cfg-proven-roots-v14')}
    assert all(v['verified'] for v in checks.values()),checks
    print('boot and vector independent source verifier replay passed',file=PROGRESS,flush=True)
    rom=(ROOT/'rom/base.gba').read_bytes()
    dma=probe.boot_dma(rom)
    cpu=dma.pop('cpu_trace')
    dma['cpu_trace_sha256']=sha(encode(cpu))
    dma['cpu_writes']=cpu['writes'];dma['cpu_instruction_count']=len(cpu['visited'])
    rows=[]
    for remove in (False,True):
        for slot in range(256):
            trace=probe.vector(rom,slot,remove=remove)
            expected=0x15 if remove else 0x56
            assert trace['counter']==(expected if slot==29 else 0xA5)
            rows.append({'slot':slot,'remove':remove,'trace_sha256':sha(encode(trace)),
                         'vector_writes':[w for w in trace['writes'] if 0x03000000<=w['address']<0x03000400],
                         'counter':trace['counter'],'final_sp':trace['registers'][13]})
    default=[]
    for slot in range(3):
        trace=probe.vector(rom,slot,remove=True,default_vector=True)
        assert trace['counter']==0xA5
        default.append({'slot':slot,'trace_sha256':sha(encode(trace)),
                        'irq_enable':trace['irq_enable'],'display_status':trace['display_status']})
    clear=probe.clear_saved(rom)
    assert clear['saved']==0 and clear['counter']==0xA5
    clear_result={'root':0x857B8,'trace_sha256':sha(encode(clear)),
                  'writes':clear['writes'],'counter':clear['counter'],'saved':clear['saved']}
    print('512 vector cases, 3 default vectors, saved init and DMA configuration passed',file=PROGRESS,flush=True)
    effects={e['at']:e for e in broad['opaque_memory_effects'] if e['kind']=='opaque_call'}
    roots=(0x624C0,0x62510,0x857B8)
    producers={root:[] for root in roots}
    for at in range(0,len(rom)-3,2):
        h,second=struct.unpack_from('<HH',rom,at)
        target=decode_thumb_bl(at,h,second);kind='bl'
        if target is None:
            target=decode_thumb_b(at,h);kind='b'
        if target is None and h&0xF000==0xD000 and h>>8&15<14:
            delta=(h&255)*2;delta=delta-512 if delta&256 else delta
            target=at+4+delta;kind='bcond'
        if target in producers:
            record=effects.get(at)
            producers[target].append({'at':at,'kind':kind,'raw_hex':rom[at:at+(4 if kind=='bl' else 2)].hex(),
                                      'actual_call_model_member':record is not None,
                                      'known_args_under_opaque_model':record.get('args') if record else None})
    pointers={}
    for root in roots:
        token=struct.pack('<I',0x08000000+root+1)
        rows_at=[];at=rom.find(token)
        while at>=0:rows_at.append(at);at=rom.find(token,at+1)
        pointers[root]=rows_at
    direct_model=[{'target':root,**row} for root,group in producers.items() if root in (0x624C0,0x62510)
                  for row in group if row['actual_call_model_member']]
    assert len(direct_model)==5
    assert all(row['known_args_under_opaque_model'].get('0') in (0,2) for row in direct_model)
    assert [row['known_args_under_opaque_model']['0'] for row in direct_model]==[0,2,0,0,2]
    # Pin all loaded current implementation dependencies, including isolated-wrapper files.
    for module in list(sys.modules.values()):
        path=getattr(module,'__file__',None)
        if path:
            path=Path(path).resolve()
            if path.is_relative_to(ROOT/'tools') and path.is_file() and '__pycache__' not in path.parts:
                name=path.relative_to(ROOT).as_posix();data=path.read_bytes();inputs[name]={'size':len(data),'sha256':sha(data)}
    for name,identity in inputs.items():
        data=(ROOT/name).read_bytes();assert len(data)==identity['size'] and sha(data)==identity['sha256'],name
    result={'schema':'animation-coupled-writer-domains-v1','rom_sha256':sha(rom),
            'broad_inventory_sha256':sha(raw),'inputs':inputs,
            'implementation_inputs':{name:sha((HERE/name).read_bytes()) for name in IMPLEMENTATIONS},
            'iwram_reference_sha256':sha((HERE/'iwram-bus-reference.json').read_bytes()),
            'fresh_source_checks':checks,'boot_dma_configuration':dma,'vector_cases':rows,
            'default_vector_cases':default,'saved_initializer':clear_result,
            'all_rom_halfword_direct_producer_shapes':producers,
            'all_rom_byte_thumb_pointer_occurrences':pointers,'five_modelled_vector_callers':direct_model,
            'facts':{'vector_u8_argument_domain':256,'vector_word_range':[0x03000000,0x03000400],
                     'counter_alias_slot':29,'observed_direct_vector_call_args':[0,2],
                     'direct_model_callers_with_fixed_small_args':5,
                     'vector_valid_index_domain_global_proven':False,'all_computed_or_indirect_producers_excluded':False,
                     'boot_zero_fill_conditional_range':[0x03000000,0x03007B00],
                     'counter_saved_and_pool_boot_zero_proven_under_model':True,
                     'counter_binary_natural_domain_proven':False,'global_writer_exhaustiveness_proven':False},
            'natural_execution_proven':False,'runtime_launches':0,'promotion_bytes':0}
    (output/'coupled-writers.json').write_bytes(encode(result))
    print('producer shapes',{hex(r):len(v) for r,v in producers.items()},'pointer occurrences',pointers,file=PROGRESS,flush=True)


if __name__=='__main__':
    with Path(sys.argv[2]).open('x') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:main(Path(sys.argv[1]))
        except BaseException:
            import traceback;traceback.print_exc();raise SystemExit(1)
