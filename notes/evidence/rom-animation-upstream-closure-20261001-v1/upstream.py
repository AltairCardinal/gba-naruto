"""One bounded upstream batch, then one whole caller-graph recomputation."""
import contextlib
import gc
import json
from collections import Counter,deque
from pathlib import Path
import sys

sys.path.insert(0,str(Path.cwd()))
sys.path.insert(0,str(Path(__file__).parent))
from analyze_batch import fixed_graph
from callee_effects import analyze,local
from closure import noncall_closure,discover
from flow import run_flow
from frontier import compile_graph,dependencies

HERE=Path(__file__).parent
PARENT=Path('notes/evidence/rom-animation-callee-effects-20261001-v1')
PROGRESS=sys.stdout


def main(output_root=None):
    manifest_raw=(PARENT/'manifest.json').read_bytes()
    assert local.sha(manifest_raw)=='43cc8b641d17f22d8ed5caba54be59b80c8260a6d69f76a33aa3adcd0110e663'
    manifest=json.loads(manifest_raw)
    for name,identity in manifest['files'].items():
        raw=(PARENT/name).read_bytes()
        assert len(raw)==identity['size'] and local.sha(raw)==identity['sha256']
    previous=json.loads((PARENT/'caller-effects-v2.json').read_text())
    model=previous['models']['five_callees_conditional_frames']
    rom,offsets,parent,parent_sha=fixed_graph()
    roots=set(parent['root_offsets'])
    graph=compile_graph(rom,offsets,roots)
    registry={int(k):v for k,v in model['callee_summaries'].items()}
    cache,field_reports={},[]

    def prove(target):
        if target in cache:return cache[target]
        if len(cache)>=128:raise ValueError('callee proof cache budget exhausted')
        closure=noncall_closure(rom,target,offsets,decoded=graph['decoded'])
        packet={'root':target,'closure':closure,'accepted':False}
        if closure['nodes']:
            try:
                strict=analyze(rom,target,set(closure['nodes']))
                conditional=analyze(rom,target,set(closure['nodes']),conditional_frame=True)
                packet.update({'strict':strict,'conditional_frame':conditional})
                best=strict if strict['return_identity_proven'] else conditional
                if best['return_identity_proven']:
                    packet.update({'accepted':True,'summary':best})
            except ValueError as error:
                packet['failure_closed_reason']=str(error)
        else:packet['failure_closed_reason']='root not in fixed source graph'
        cache[target]=packet
        return packet

    def inspect(summaries):
        nonlocal field_reports
        field_reports=[]
        for row in model['missing_fields']:
            field=12 if row['field']=='flags' else 16
            result=dependencies(rom,offsets,roots,row['site'],field,context=graph,callees=summaries)
            field_reports.append({**row,'dependency_report':result})
        return [f for r in field_reports for f in r['dependency_report']['frontiers']]

    def progress(n,targets):
        print('Dependency round',n,'new targets',[hex(t) for t in targets],file=PROGRESS,flush=True)

    discovered=discover(inspect,prove,registry,progress=progress)
    registry=discovered['registry']
    final_frontiers=[f for r in field_reports for f in r['dependency_report']['frontiers']]
    # For unsaved register frontiers, inspect all real child dependencies down
    # to proved preservation, source/SVC/control boundaries, or local effects.
    pending=deque((f['target'],f['index']) for f in final_frontiers
                  if f['kind']=='unproved_callee_register_effect')
    seen,audit=set(),[]
    while pending:
        target,reg=pending.popleft()
        if (target,reg) in seen:continue
        seen.add((target,reg))
        if len(seen)>128:raise ValueError('unsaved identity dependency budget exhausted')
        packet=prove(target)
        summary=packet.get('summary')
        preserved=summary is not None and reg in summary['preserved_registers']
        audit.append({'target':target,'register':reg,'preserved_under_packet_conditions':preserved,
                      'child_targets':packet['closure']['child_targets'],
                      'source_frontiers':packet['closure']['frontiers'],
                      'failure_closed_reason':packet.get('failure_closed_reason')})
        if not preserved:
            pending.extend((child,reg) for child in packet['closure']['child_targets'])
    print('Whole caller graph once; summaries',len(registry),'proof packets',len(cache),file=PROGRESS,flush=True)
    result=run_flow(rom,offsets,roots,callees=registry)
    rows,missing=[],[]
    for prior in parent['models']['all_callees_opaque']['rows']:
        at=prior['site'];state=result['states'][at]
        pair=[state['registers'].get(r,0)-local.BASE for r in (0,1)]
        assert pair==prior['historical_base_pair'] and state['registers'].get(2)==prior['historical_group']
        row={'site':at,'base_pair':pair,'group':state['registers'][2],
             'flags':state['stack'].get(12),'callback':state['stack'].get(16),
             'conditional_callee_preservation':state['conditional_callee_preservation'],
             'unverified_call_continuation':state['unverified_call_continuation']}
        rows.append(row)
        for key in ('flags','callback'):
            if row[key] is None:missing.append({'site':at,'field':key})
    counts={'pair_group_rebuilt':len(rows),'flags_fixed':sum(r['flags'] is not None for r in rows),
            'callbacks_fixed':sum(r['callback'] is not None for r in rows),
            'both_fields_fixed':sum(r['flags'] is not None and r['callback'] is not None for r in rows),
            'missing_fields':len(missing)}
    del result
    gc.collect()
    payload={'schema':'animation-upstream-dependency-closure-v1','parent_manifest_sha256':local.sha(manifest_raw),
             'source_parent_sha256':parent_sha,'rom_sha256':local.sha(rom),
             'source_instruction_count':len(offsets),'root_count':len(roots),
             'implementation_inputs':{n:local.sha((HERE/n).read_bytes()) for n in
                  ('closure.py','upstream.py','callee_effects.py','flow.py','frontier.py','analyze_batch.py','test_closure.py')},
             'discovery':discovered,'proof_packets':cache,'fixed_field_reports':field_reports,
             'frontier_kinds':dict(Counter(f['kind'] for f in final_frontiers)),
             'unsaved_identity_dependencies':audit,'caller_rows':rows,'caller_counts':counts,
             'remaining_fields':missing,'whole_graph_recomputations':1,
             'caller_stack_facts_preserved':False,'natural_execution_proven':False,
             'scope':'Fixed source graph and explicit frame/return preconditions only. Child dependency audit '
                     'does not invent unsaved GPR effects, BIOS contracts, caller memory domains or natural reachability.',
             'promotion_bytes':0}
    destination=Path(output_root) if output_root is not None else HERE
    (destination/'upstream-closure-v2.json').write_text(json.dumps(payload,sort_keys=True,indent=2)+'\n')
    print('Final counts',counts,file=PROGRESS,flush=True)


if __name__ == '__main__':
    with (HERE/'upstream-v2.log').open('x') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:main()
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
