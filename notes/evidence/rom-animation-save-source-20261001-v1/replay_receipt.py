"""Permanent exact replay using a fresh managed output and an isolated batch."""
import contextlib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd().resolve()
HERE = Path(__file__).resolve().parent


def main(output):
    manifest=json.loads((HERE/'manifest.json').read_text())
    for name,identity in manifest['files'].items():
        path=(HERE/name).resolve()
        assert path.is_relative_to(HERE),name
        raw=path.read_bytes()
        assert len(raw)==identity['size'] and hashlib.sha256(raw).hexdigest()==identity['sha256'],name
    output=output.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'build/experiments/active'):
        raise ValueError('fresh managed active output required')
    relative=output.relative_to(ROOT/'build/experiments/active')
    if len(relative.parts)!=3:
        raise ValueError('output must be task/run/output')
    metadata=json.loads((output.parent/'.experiment.json').read_text())
    if metadata['status']!='active' or [metadata['task'],metadata['run_id']]!=list(relative.parts[:2]):
        raise ValueError('output run is not active')
    print('START isolated permanent batch',flush=True)
    subprocess.run([sys.executable,str(HERE/'batch.py'),str(output),str(output.parent/'batch.log')],cwd=ROOT,check=True)
    assert (output/'save-source.json').read_bytes()==(HERE/'save-source.json').read_bytes()
    data=json.loads((output/'save-source.json').read_text())
    report={'unit_tests':12,'raw_trace_cases':len(data['cases']),
            'independent_source_or_lifecycle_verifier_calls':len(data['source_checks']),
            'raw_cfg_source_groups':len(data['source_graphs']),
            'raw_cfg_unique_instructions':len({n for g in data['source_graphs'].values() for n in g['nodes']}),
            'source_8f654_entry_remains_open':not data['facts']['postbattle_68de4_entry_proven'],
            'exact_outputs':['save-source.json'],'isolated_batch_process':True,
            'context_resume_proven':False,'natural_execution_proven':False,'runtime_launches':0,'promotion_bytes':0}
    (output/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print('PERMANENT REPLAY PASSED: 12 tests, 521 raw traces, 11 source groups, 3 verifiers, exact authority output')


if __name__=='__main__':
    with Path(sys.argv[2]).open('x') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:
            main(Path(sys.argv[1]))
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
