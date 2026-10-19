"""Joint fixed-source callbacks, helpers and one-task advance provenance."""
import contextlib,json,sys,struct
from pathlib import Path
HERE=Path(__file__).parent
PARENT=Path('notes/evidence/rom-animation-interprocedural-identities-20261001-v1')
sys.path.insert(0,str(Path.cwd()));sys.path.insert(0,str(PARENT));sys.path.insert(0,str(HERE))
from analyze_batch import fixed_graph
from callee_effects import analyze,local
from closure import noncall_closure
from provenance import audit
from tools.verify_rom_cfg_inventory import _decode
from tools.verify_rom_cfg_proven_roots_v20 import verify_root
from tools.verify_rom_text_bg_task_closure import verify_artifact
PROGRESS=sys.stdout


def main(output=None):
    output=Path(output) if output else HERE
    mraw=(PARENT/'manifest.json').read_bytes()
    assert local.sha(mraw)=='1aca46ee19d8af2ddf051f1daa1fbfec1cd660245578020f689303116ff78e70'
    for n,i in json.loads(mraw)['files'].items():
        b=(PARENT/n).read_bytes();assert len(b)==i['size'] and local.sha(b)==i['sha256']
    old=json.loads((PARENT/'interprocedural-identities-v2.json').read_text())
    rom,offsets,parent,source_sha=fixed_graph();old_count=len(offsets)
    inputs={}
    for name in ('artifacts/rom-cfg-proven-roots-v20/manifest.json','artifacts/rom-cfg-proven-roots-v20/rom-cfg-proven-roots-v20.json','tools/verify_rom_cfg_proven_roots_v20.py','tools/rom_cfg_proven_roots_v20_contract.py','artifacts/rom-text-bg-task-closure-v1/manifest.json','artifacts/rom-text-bg-task-closure-v1/rom-text-bg-task-closure.json','tools/verify_rom_text_bg_task_closure.py','sequel/rom-byte-coverage.json'):
        b=Path(name).read_bytes();inputs[name]={'size':len(b),'sha256':local.sha(b)}
    assert inputs['artifacts/rom-cfg-proven-roots-v20/rom-cfg-proven-roots-v20.json']['sha256']=='5d3186a688973b1733b0117aedee7c689a5270497c83f8726d4d2540bcfe1543'
    assert inputs['sequel/rom-byte-coverage.json']['sha256']==local.COVERAGE_SHA
    v20check=verify_root(Path.cwd(),Path('artifacts/rom-cfg-proven-roots-v20'))
    assert v20check['verified'];print('v20 independent source replay passed',file=PROGRESS,flush=True)
    callbackcheck=verify_artifact(Path.cwd(),Path('artifacts/rom-text-bg-task-closure-v1'))
    assert callbackcheck['verified'];print('long callback independent source replay passed',file=PROGRESS,flush=True)
    v20=json.loads(Path('artifacts/rom-cfg-proven-roots-v20/rom-cfg-proven-roots-v20.json').read_text())
    added=set()
    for start,end in v20['target_local_denominator']['code_ranges']:
        at=start
        while at<end:
            i=_decode(rom,at,'thumb');assert i['accepted'] and at+i['size']<=end
            added.add(at);at+=i['size']
    offsets |= added
    # A separately labelled raw callback candidate, not a new canonical source claim.
    assert rom[0x8ee40:0x8ee56].hex()=='00b5011c04480078002802d0081cd3f79bfc01bc0047'
    short_nodes=set();at=0x8ee40
    while at<0x8ee56:
        i=_decode(rom,at,'thumb');assert i['accepted'] and at+i['size']<=0x8ee56
        short_nodes.add(at);at+=i['size']
    short_calls=[row for row in old['caller_rows'] if row['callback']==0x0808ee41]
    assert [r['site'] for r in short_calls]==[0x8eea2,0x8eec6]
    ptr=[at for at in range(len(rom)-3) if rom[at:at+4]==bytes.fromhex('41ee0808')]
    assert ptr==[0x8eeec]
    assert all(r['site'] in offsets for r in short_calls)
    literal=((0x8ee44+4)&~3)+4*4
    short_binding={'root':0x8ee40,'candidate_code_range':[0x8ee40,0x8ee56],
                   'candidate_code_sha256':local.sha(rom[0x8ee40:0x8ee56]),
                   'candidate_instruction_count':len(short_nodes),'pointer_occurrences_all_byte_offsets':ptr,
                   'registered_callers':short_calls,'registration_is_conditional_model':True,
                   'canonical_source_membership':False,'literal_offset':literal,
                   'literal_value':struct.unpack_from('<I',rom,literal)[0],
                   'suffix_range_excluded':[0x8ee56,0x8ee58],'promotion_bytes':0}
    working=offsets|short_nodes
    registry={int(k):v for k,v in old['registry'].items()}
    for root in (0x62788,0x62798):
        c=noncall_closure(rom,root,offsets)
        summary=analyze(rom,root,set(c['nodes']))
        assert summary['return_identity_proven'];registry[root]=summary
    specs=[('long_callback',0x8aa50,{0:('object',0)},()),
           ('short_callback_candidate',0x8ee40,{0:('object',0)},()),
           ('disable_helper',0x62788,{0:('object',0)},()),
           ('group_reset_helper',0x62798,{0:('object',0)},()),
           ('sequence_advance',0x63238,{7:('object',0)},(0x632f8,)),
           ('sequence_selection',0x62982,{7:('object',0)},(0x629b0,0x629b4)),
           ('callback_dispatch',0x62940,{7:('object',0)},(0x62958,)),
           ('active_list_filter',0x627d6,{6:('object',0)},(0x62808,))]
    rows={}
    for name,root,seed,stops in specs:
        c=noncall_closure(rom,root,working)
        used={t:registry[t] for t in c['child_targets'] if t in registry}
        report=audit(rom,root,working,seed,callees=used,stop_sites=stops)
        report['callee_identity_inputs']={t:local.sha(json.dumps(v,sort_keys=True).encode()) for t,v in used.items()}
        rows[name]=report
        print(name,'nodes',report['visited_instruction_count'],'stores',len(report['stores']),
              'object stores',sum(isinstance(s['address'],list) and s['address'][0]=='object' for s in report['stores']),file=PROGRESS,flush=True)
    assert not rows['short_callback_candidate']['stores']
    call=rows['short_callback_candidate']['calls'];assert len(call)==1 and call[0]['target']==0x62788 and call[0]['args'][0]==['object',0]
    assert [s['address'] for s in rows['disable_helper']['stores']]==[['object',0]]
    assert [s['address'] for s in rows['group_reset_helper']['stores']]==[['object',0x14],['object',0x16],['object',0x18],['object',0]]
    assert rows['group_reset_helper']['stores'][1]['source_value']==0 and rows['group_reset_helper']['stores'][2]['source_value']==0
    assert [s['address'][1] for s in rows['sequence_advance']['stores'] if s['at'] in (0x6325a,0x63276,0x632b8,0x632ba)]==[0x18,0x16,0x16,0x18]
    assert next(r for r in rows['sequence_selection']['reads'] if r['at']==0x6298c)['address']==['object',0x14]
    assert next(r for r in rows['sequence_selection']['reads'] if r['at']==0x6298e)['address']==['object',0x20]
    assert next(r for r in rows['sequence_selection']['reads'] if r['at']==0x62994)['address']==['object',0x16]
    assert next(c for c in rows['callback_dispatch']['calls'] if c['at']==0x62954)['args'][0]==['object',0]
    assert next(s for s in rows['active_list_filter']['stores'] if s['at']==0x62806)['address']==['object',0]
    facts={'short_callback_calls_disable_on_nonzero_ram_flag':True,'disable_helper_flags':'(old_flags & 0xFFFFFFFE) | 2',
           'group_reset_fields':[0x14,0x16,0x18],'group_reset_mask':struct.unpack_from('<I',rom,0x627ac)[0],
           'sequence_selection_precedes_freeze_test':True,'freeze_test_site':0x63244,
           'timer_load_store_sites':[0x63256,0x6325a],'timer_width_bits':16,
           'duration_signed_load_site':0x63260,'duration_width_bits':16,'timer_compare_site':0x63264,
           'counter_address':0x03000075,'counter_width_bits':8,
           'callbacks_before_active_list_filter':True,'active_list_rechecks_bit0':True,
           'counter_producer_domain_proven':False,'global_writer_exhaustiveness_proven':False,
           'callback_alias_effects_proven':False,'object_handle_lifetime_proven':False,
           'full_timer_domain_runtime_proven':False}
    assert rom[0x62788:0x62798].hex()=='01680222524211400222114301607047'
    assert rom[0x62798:0x627aa].hex()=='00228182c28202830168024a114001607047'
    assert rom[0x63256:0x63268].hex()=='388b01303883009a0223d05e3a8b904237d1'
    payload={'schema':'animation-critical-writers-v1','parent_manifest_sha256':local.sha(mraw),
             'rom_sha256':local.sha(rom),'old_source_instruction_count':old_count,
             'accepted_source_instruction_count':len(offsets),'v20_source_instruction_count':len(added),
             'v20_net_new_instruction_count':len(offsets)-old_count,
             'source_inputs':inputs,'source_sha256':source_sha,'source_verifiers':{'v20':v20check,'long_callback':callbackcheck},
             'short_callback_candidate_binding':short_binding,'reports':rows,'facts':facts,
             'implementation_inputs':{n:local.sha((HERE/n).read_bytes()) for n in ('provenance.py','writers.py','test_provenance.py')},
             'scope':'Joint fixed-entry pointer hypotheses; conditional callee preservation. Unknown aliases, all natural domains and writer exhaustiveness remain open.',
             'promotion_bytes':0,'natural_execution_proven':False}
    (output/'critical-writers.json').write_text(json.dumps(payload,sort_keys=True,indent=2)+'\n')


if __name__=='__main__':
    with (HERE/'writers.log').open('x') as s,contextlib.redirect_stdout(s),contextlib.redirect_stderr(s):
        try:main()
        except BaseException:
            import traceback;traceback.print_exc();raise SystemExit(1)
