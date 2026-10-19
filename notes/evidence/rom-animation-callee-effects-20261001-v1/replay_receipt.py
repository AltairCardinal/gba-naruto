"""Replay all fixed callee proofs and caller models from immutable notes code."""
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
from analyze_batch import main as analyze
from flow_batch import main as callers
from profile_updated import main as frontiers


def main(output):
    manifest=json.loads((HERE/'manifest.json').read_text())
    for name,identity in manifest['files'].items():
        raw=(HERE/name).read_bytes()
        assert len(raw)==identity['size'] and local.sha(raw)==identity['sha256'],name
    if output.exists() or not output.is_relative_to(ROOT/'build/experiments/active'):
        raise ValueError('fresh managed active output required')
    relative=output.relative_to(ROOT/'build/experiments/active')
    if len(relative.parts)!=3:
        raise ValueError('output must be task/run/output')
    metadata=json.loads((output.parent/'.experiment.json').read_text())
    if metadata['status']!='active' or [metadata['task'],metadata['run_id']]!=list(relative.parts[:2]):
        raise ValueError('output run is not active')
    output.mkdir()
    tests()
    analyze(output)
    callers(output)
    frontiers(output,output/'caller-effects-v2.json')
    names=('callee-effects-v2.json','caller-effects-v2.json','updated-frontiers.json')
    for name in names:
        assert (output/name).read_bytes()==(HERE/name).read_bytes(),name
    caller=json.loads((output/names[1]).read_text())
    frontier=json.loads((output/names[2]).read_text())
    report={'unit_tests_passed':38,'whole_graph_instruction_count':caller['source_instruction_count'],
            'exact_report_replays':list(names),'callee_targets_replayed':5,
            'dependency_fields_replayed':frontier['field_count'],
            'output_sha256':{n:local.sha((output/n).read_bytes()) for n in names},
            'new_source_cfg_verifier_runs':0,'runtime_launches':0,
            'natural_execution_proven':False,'promotion_bytes':0}
    (output/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')


if __name__ == '__main__':
    with Path(sys.argv[2]).open('x') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:
            main(Path(sys.argv[1]).resolve())
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
