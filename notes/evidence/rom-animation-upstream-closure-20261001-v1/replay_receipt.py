"""Replay fixed upstream graph discovery into a fresh managed output."""
import contextlib
import json
from pathlib import Path
import sys

ROOT=Path.cwd().resolve()
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(HERE))
from callee_effects import local
from run_all_tests import main as tests
from upstream import main as upstream


def main(output):
    manifest=json.loads((HERE/'manifest.json').read_text())
    for name,identity in manifest['files'].items():
        raw=(HERE/name).read_bytes()
        assert len(raw)==identity['size'] and local.sha(raw)==identity['sha256'],name
    if output.exists() or not output.is_relative_to(ROOT/'build/experiments/active'):
        raise ValueError('fresh managed active output required')
    relative=output.relative_to(ROOT/'build/experiments/active')
    if len(relative.parts)!=3:raise ValueError('output must be task/run/output')
    metadata=json.loads((output.parent/'.experiment.json').read_text())
    if metadata['status']!='active' or [metadata['task'],metadata['run_id']]!=list(relative.parts[:2]):
        raise ValueError('output run is not active')
    output.mkdir()
    tests()
    upstream(output)
    name='upstream-closure-v2.json'
    raw=(output/name).read_bytes()
    assert raw==(HERE/name).read_bytes()
    result=json.loads(raw)
    report={'unit_tests_passed':48,'whole_graph_instruction_count':result['source_instruction_count'],
            'exact_report_replays':[name],'output_sha256':local.sha(raw),
            'callee_packets_replayed':len(result['proof_packets']),
            'caller_counts':result['caller_counts'],'whole_graph_recomputations':1,
            'new_source_cfg_verifier_runs':0,'runtime_launches':0,
            'natural_execution_proven':False,'promotion_bytes':0}
    (output/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')


if __name__ == '__main__':
    with Path(sys.argv[2]).open('x') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:main(Path(sys.argv[1]).resolve())
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
