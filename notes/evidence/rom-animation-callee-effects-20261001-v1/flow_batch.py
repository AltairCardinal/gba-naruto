"""Rebuild all 47 pool calls under leaf-only and conditional frame identities."""
import contextlib
import gc
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path.cwd()))
sys.path.insert(0,str(Path(__file__).parent))
from analyze_batch import fixed_graph, derive
from flow import run_flow
from callee_effects import local

HERE = Path(__file__).parent
PROGRESS = sys.stdout


def main(output_root=None):
    rom, offsets, parent, parent_sha = fixed_graph()
    rows = derive(rom,offsets)
    summaries = {row['range'][0]: row['strict'] if row['strict']['return_identity_proven']
                 else row['conditional_frame'] for row in rows}
    assert all(s['return_identity_proven'] for s in summaries.values())
    models = {}
    selected = [('leaf_only', {0x6571C:summaries[0x6571C]}),
                ('five_callees_conditional_frames', summaries)]
    for name, contracts in selected:
        print('Whole source graph: '+name,file=PROGRESS,flush=True)
        result = run_flow(rom,offsets,set(parent['root_offsets']),callees=contracts)
        calls, missing = [], []
        for prior in parent['models']['all_callees_opaque']['rows']:
            at = prior['site']
            state = result['states'][at]
            pair = [state['registers'].get(r,0)-local.BASE for r in (0,1)]
            assert pair == prior['historical_base_pair'] and state['registers'].get(2) == prior['historical_group']
            row = {'site': at,'base_pair': pair,'group': state['registers'][2],
                   'flags': state['stack'].get(12),'callback': state['stack'].get(16),
                   'conditional_callee_preservation':state['conditional_callee_preservation'],
                   'unverified_call_continuation':state['unverified_call_continuation']}
            calls.append(row)
            for field in ('flags','callback'):
                if row[field] is None:
                    missing.append({'site':at,'field':field})
        models[name] = {'rows':calls,'missing_fields':missing,'updates':result['updates'],
                        'pair_group_rebuilt':len(calls),'flags_fixed':sum(r['flags'] is not None for r in calls),
                        'callbacks_fixed':sum(r['callback'] is not None for r in calls),
                        'both_fields_fixed':sum(r['flags'] is not None and r['callback'] is not None for r in calls),
                        'callee_summaries':contracts}
        del result
        gc.collect()
    payload = {'schema':'animation-callee-caller-flow-v1','parent_sha256':parent_sha,
               'rom_sha256':local.sha(rom),'source_instruction_count':len(offsets),
               'root_count':len(parent['root_offsets']),
               'implementation_inputs':{name:local.sha((HERE/name).read_bytes()) for name in
                   ('flow.py','callee_effects.py','flow_batch.py','analyze_batch.py','test_effects.py','test_summary_flow.py')},
               'historical_parent_models':{name:{key:model[key] for key in
                    ('flags_fixed','callbacks_fixed','both_fields_fixed','pair_group_rebuilt')} for name,model in parent['models'].items()},
               'models':models,'caller_stack_facts_preserved':False,
               'scope':'Fixed known source graph only; frame/child return assumptions, all caller stack memory, '
                       'BIOS effects, additional indirect/ARM entries, callbacks and lifecycle remain unproved.',
               'promotion_bytes':0}
    destination = Path(output_root) if output_root is not None else HERE
    (destination/'caller-effects-v2.json').write_text(json.dumps(payload,sort_keys=True,indent=2)+'\n')


if __name__ == '__main__':
    with (HERE/'flow-batch-v2.log').open('x') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:
            main()
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
