"""Trace missing fields beyond newly verified callee-register boundaries."""
import contextlib
import json
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0,str(Path.cwd()))
sys.path.insert(0,str(Path(__file__).parent))
from analyze_batch import fixed_graph
from frontier import compile_graph, dependencies
from callee_effects import local

HERE = Path(__file__).parent


def main(output_root=None,parent_path=None):
    raw = (Path(parent_path) if parent_path is not None else HERE/'caller-effects-v2.json').read_bytes()
    report = json.loads(raw)
    for name,digest in report['implementation_inputs'].items():
        assert local.sha((HERE/name).read_bytes())==digest
    rom,offsets,parent,parent_sha=fixed_graph()
    assert report['parent_sha256']==parent_sha and report['rom_sha256']==local.sha(rom)
    roots=set(parent['root_offsets'])
    context=compile_graph(rom,offsets,roots)
    model=report['models']['five_callees_conditional_frames']
    summaries={int(k):v for k,v in model['callee_summaries'].items()}
    rows=[]
    for row in model['missing_fields']:
        field=12 if row['field']=='flags' else 16
        result=dependencies(rom,offsets,roots,row['site'],field,context=context,callees=summaries)
        rows.append({**row,'dependency_report':result})
    frontiers=[f for r in rows for f in r['dependency_report']['frontiers']]
    targets=sorted({f['target'] for f in frontiers if 'target' in f})
    payload={'schema':'animation-callee-updated-frontiers-v1','parent_sha256':local.sha(raw),
             'implementation_inputs':{name:local.sha((HERE/name).read_bytes()) for name in
                 ('frontier.py','profile_updated.py','test_summary_frontier.py')},
             'field_count':len(rows),'rows':rows,'frontier_kinds':dict(Counter(f['kind'] for f in frontiers)),
             'callee_targets':targets,
             'scope':'Backward planning only. Verified callee identities do not establish entry values; '
                     'branches are not narrowed and frame/call resumption assumptions remain unproved.',
             'promotion_bytes':0}
    destination=Path(output_root) if output_root is not None else HERE
    (destination/'updated-frontiers.json').write_text(json.dumps(payload,sort_keys=True,indent=2)+'\n')
    print('fields',len(rows),'kinds',payload['frontier_kinds'],'targets',[hex(t) for t in targets])


if __name__ == '__main__':
    with (HERE/'updated-frontiers.log').open('x') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:
            main()
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
