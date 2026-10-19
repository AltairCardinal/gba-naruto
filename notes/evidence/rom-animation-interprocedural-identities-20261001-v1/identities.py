"""Bind acyclic child identities and one proven dispatch, then rebuild 47 calls."""
import contextlib
import json
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0,str(Path.cwd()))
sys.path.insert(0,str(Path(__file__).parent))
from analyze_batch import fixed_graph
from callee_effects import analyze,local
from closure import noncall_closure
from dispatch_contracts import bind,INPUTS
from flow import run_flow
from frontier import compile_graph,dependencies
from tools.verify_rom_cfg_inventory import _decode

HERE=Path(__file__).parent
PARENT=Path('notes/evidence/rom-animation-upstream-closure-20261001-v1')
PROGRESS=sys.stdout


def main(output_root=None):
    raw=(PARENT/'manifest.json').read_bytes()
    assert local.sha(raw)=='24b1b0705de42cc3b0f37eda2ff3f6d01889468b08e4c53710fe845ef2c8150c'
    for name,i in json.loads(raw)['files'].items():
        b=(PARENT/name).read_bytes()
        assert len(b)==i['size'] and local.sha(b)==i['sha256']
    previous_raw=(PARENT/'upstream-closure-v2.json').read_bytes()
    previous=json.loads(previous_raw)
    rom,offsets,parent,source_sha=fixed_graph()
    graph=compile_graph(rom,offsets,set(parent['root_offsets']))
    targets={int(k) for k in previous['proof_packets']} | {int(k) for k in previous['discovery']['registry']}
    cache,cycles={},[]

    def derive(target,ancestors=()):
        if target in cache:return cache[target]
        if target in ancestors:
            cycles.append({'target':target,'ancestor_chain':list(ancestors)})
            return None
        if len(ancestors)>=32:raise ValueError('library child depth budget exhausted')
        dispatches=bind(rom,target,offsets,{0x6dc72}) if target==0x6d964 else {}
        closure=noncall_closure(rom,target,offsets,decoded=graph['decoded'],dispatches=dispatches)
        children={}
        for child in closure['child_targets']:
            if child in targets:
                packet=derive(child,ancestors+(target,))
                if packet is not None and packet.get('accepted'):
                    children[child]=packet['summary']
        packet={'root':target,'closure':closure,'accepted':False}
        if closure['nodes']:
            try:
                strict=analyze(rom,target,set(closure['nodes']),children=children,dispatches=dispatches)
                conditional=analyze(rom,target,set(closure['nodes']),conditional_frame=True,
                                    children=children,dispatches=dispatches)
                packet.update({'strict':strict,'conditional_frame':conditional})
                best=strict if strict['return_identity_proven'] else conditional
                if best['return_identity_proven']:
                    packet.update({'accepted':True,'summary':best})
            except ValueError as error:packet['failure_closed_reason']=str(error)
        else:packet['failure_closed_reason']='missing fixed source root'
        cache[target]=packet
        print('Library root',hex(target),'accepted',packet['accepted'],file=PROGRESS,flush=True)
        return packet

    discovery_rounds=[]
    for round_index in range(16):
        cache.clear()
        for target in sorted(targets):derive(target)
        registry={target:p['summary'] for target,p in cache.items() if p['accepted']}
        frontier_rows=[]
        for row in previous['remaining_fields']:
            report=dependencies(rom,offsets,set(parent['root_offsets']),row['site'],
                                12 if row['field']=='flags' else 16,context=graph,callees=registry)
            frontier_rows.extend(report['frontiers'])
        new=sorted({f['target'] for f in frontier_rows if f['kind'].startswith('unproved_callee')
                    and f['target'] not in targets})
        discovery_rounds.append({'round':round_index+1,'new_targets':new,
                                 'frontier_kinds':dict(Counter(f['kind'] for f in frontier_rows))})
        print('Identity discovery round',round_index+1,'new',[hex(t) for t in new],file=PROGRESS,flush=True)
        if not new:break
        targets.update(new)
        if len(targets)>128:raise ValueError('identity target budget exhausted')
    else:raise ValueError('identity round budget exhausted')
    print('Whole 47-caller graph',file=PROGRESS,flush=True)
    result=run_flow(rom,offsets,set(parent['root_offsets']),callees=registry)
    rows,missing=[],[]
    for prior in parent['models']['all_callees_opaque']['rows']:
        at=prior['site'];s=result['states'][at]
        pair=[s['registers'].get(r,0)-local.BASE for r in (0,1)]
        assert pair==prior['historical_base_pair'] and s['registers'].get(2)==prior['historical_group']
        row={'site':at,'base_pair':pair,'group':s['registers'][2],
             'flags':s['stack'].get(12),'callback':s['stack'].get(16),
             'conditional_callee_preservation':s['conditional_callee_preservation'],
             'unverified_call_continuation':s['unverified_call_continuation']}
        rows.append(row)
        for key in ('flags','callback'):
            if row[key] is None:missing.append({'site':at,'field':key})
    del result
    field_reports=[]
    for row in missing:
        print('Remaining field',hex(row['site']),row['field'],file=PROGRESS,flush=True)
        report=dependencies(rom,offsets,set(parent['root_offsets']),row['site'],
                            12 if row['field']=='flags' else 16,context=graph,callees=registry)
        field_reports.append({**row,'dependency_report':report})
    # Exact mode spine, without classifying the sibling veneer or treating the
    # scheduler as an ordinary returning callee.
    assert rom[0x9c574:0x9c576].hex()=='7847'
    arm_branch=_decode(rom,0x9c578,'arm')
    assert arm_branch['accepted'] and arm_branch['flow_kind']=='unconditional_branch'
    assert arm_branch['successors'][0]['file_offset']==0x26c
    coverage_raw=Path('sequel/rom-byte-coverage.json').read_bytes()
    assert local.sha(coverage_raw)==local.COVERAGE_SHA
    coverage=json.loads(coverage_raw)
    claim=next(c for c in coverage['claims'] if c['primary_class']=='boot_interwork_arm_code'
               and c['range'][0]<=0x26c<c['range'][1])
    boot_raw=Path(claim['evidence_path']).read_bytes()
    assert local.sha(boot_raw)==claim['evidence_sha256']
    boot=json.loads(boot_raw)
    counts={'pair_group_rebuilt':len(rows),'flags_fixed':sum(r['flags'] is not None for r in rows),
            'callbacks_fixed':sum(r['callback'] is not None for r in rows),
            'both_fields_fixed':sum(r['flags'] is not None and r['callback'] is not None for r in rows),
            'missing_fields':len(missing)}
    fronts=[f for r in field_reports for f in r['dependency_report']['frontiers']]
    payload={'schema':'animation-interprocedural-identities-v1','parent_sha256':local.sha(previous_raw),
             'source_parent_sha256':source_sha,'rom_sha256':local.sha(rom),
             'source_instruction_count':len(offsets),'root_count':len(parent['root_offsets']),
             'implementation_inputs':{n:local.sha((HERE/n).read_bytes()) for n in
                 ('callee_effects.py','flow.py','frontier.py','closure.py','dispatch_contracts.py','identities.py',
                  'test_children.py','test_dispatch.py','test_summary_flow.py')},
             'dispatch_inputs':{n:{'sha256':v[0],'size':len(Path(n).read_bytes())} for n,v in INPUTS.items()},
             'library':cache,'registry':registry,'excluded_recursive_child_edges':cycles,
             'identity_discovery_rounds':discovery_rounds,
             'caller_rows':rows,'caller_counts':counts,'remaining_fields':missing,
             'remaining_field_reports':field_reports,'frontier_kinds':dict(Counter(f['kind'] for f in fronts)),
             'context_switch_spine':{'thumb_bx_pc_offset':0x9c574,'thumb_raw_hex':'7847',
                 'arm_branch_offset':0x9c578,'arm_branch_raw_hex':rom[0x9c578:0x9c57c].hex(),
                 'arm_target':0x26c,'boot_artifact':claim['evidence_path'],
                 'boot_artifact_sha256':local.sha(boot_raw),'existing_arm_root':boot['root'],
                 'ordinary_callee_contract_accepted':False,'same_context_resumption_proven':False,
                 'sibling_veneer_bytes_promoted':False},
             'caller_stack_facts_preserved':False,'natural_execution_proven':False,
             'scope':'Fixed Thumb sources, verified acyclic child identities and a dominated fixed 10-slot dispatch. '
                     'Frame/private memory/context resumption, BIOS, record writers and natural lifecycle remain unproved.',
             'promotion_bytes':0}
    destination=Path(output_root) if output_root is not None else HERE
    (destination/'interprocedural-identities-v2.json').write_text(json.dumps(payload,sort_keys=True,indent=2)+'\n')
    print('Final counts',counts,file=PROGRESS,flush=True)


if __name__ == '__main__':
    with (HERE/'identities-v2.log').open('x') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:main()
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
