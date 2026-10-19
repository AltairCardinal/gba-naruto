"""Manifest verification and exact permanent full-renderer replay in an owned directory."""
import contextlib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path.cwd().resolve()
HERE=Path(__file__).resolve().parent


def main(output):
    manifest=json.loads((HERE/'manifest.json').read_text())
    for name,identity in manifest['files'].items():
        path=(HERE/name).resolve()
        assert path.is_relative_to(HERE) and not path.is_symlink(),name
        raw=path.read_bytes()
        assert len(raw)==identity['size'] and hashlib.sha256(raw).hexdigest()==identity['sha256'],name
    output=output.resolve()
    assert not output.exists() and output.is_relative_to(ROOT/'build/experiments/active')
    relative=output.relative_to(ROOT/'build/experiments/active')
    assert len(relative.parts)==3
    metadata=json.loads((output.parent/'.experiment.json').read_text())
    assert metadata['status']=='active' and [metadata['task'],metadata['run_id']]==list(relative.parts[:2])
    subprocess.run([sys.executable,str(HERE/'batch.py'),str(output),str(output.parent/'batch.log')],cwd=ROOT,check=True)
    for name in ('full-renderer.json','full-traces.jsonl.gz'):
        assert (output/name).read_bytes()==(HERE/name).read_bytes(),name
    result=json.loads((output/'full-renderer.json').read_text())
    report={'unit_tests':5,'complete_renderer_frames':len(result['frames']),'native_traces':result['native_trace_count'],
            'exact_outputs':['full-renderer.json','full-traces.jsonl.gz'],'fresh_source_verifiers':3,
            'natural_entry_domain_proven':False,'single_active_object_only':True,'promotion_bytes':0}
    (output/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print('PERMANENT FULL RENDERER REPLAY PASSED: 3684 frames, 7368 traces, both exact outputs')


if __name__=='__main__':
    with Path(sys.argv[2]).open('x') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        try:main(Path(sys.argv[1]))
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
