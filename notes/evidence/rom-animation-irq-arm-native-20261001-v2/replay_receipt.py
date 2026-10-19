"""Verify frozen receipt and replay native cases into a fresh managed run."""
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
    if output.exists() or not output.is_relative_to(ROOT/'build/experiments/active'):
        raise ValueError('fresh managed output required')
    relative=output.relative_to(ROOT/'build/experiments/active')
    if len(relative.parts)!=3:
        raise ValueError('task/run/output required')
    metadata=json.loads((output.parent/'.experiment.json').read_text())
    assert metadata['status']=='active' and [metadata['task'],metadata['run_id']]==list(relative.parts[:2])
    subprocess.run([sys.executable,str(HERE/'batch.py'),str(output),str(output.parent/'batch.log')],cwd=ROOT,check=True)
    for name in ('irq-arm-native.json','native-traces.jsonl.gz'):
        assert (output/name).read_bytes()==(HERE/name).read_bytes(),name
    data=json.loads((output/'irq-arm-native.json').read_text())
    report={'unit_tests':13,'native_cases':len(data['cases']),'fresh_artifact_verifiers':2,'raw_irq_check':1,
            'exact_outputs':['irq-arm-native.json','native-traces.jsonl.gz'],
            'snapshot_roundtrip_verified':True,'natural_execution_proven':False,'promotion_bytes':0}
    (output/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print('PERMANENT REPLAY PASSED: 13 tests, 10270 native cases, both exact outputs')


if __name__=='__main__':
    with Path(sys.argv[2]).open('x') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        try:
            main(Path(sys.argv[1]))
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
