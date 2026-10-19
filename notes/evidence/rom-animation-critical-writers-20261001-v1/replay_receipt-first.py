"""Replay fixed critical writer provenance into a fresh managed output."""
import contextlib
import json
from pathlib import Path
import sys

ROOT=Path.cwd().resolve()
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(HERE))
from callee_effects import local
import unittest
import test_provenance
from writers import main as writers


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
    test_result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_provenance))
    assert test_result.wasSuccessful() and test_result.testsRun==9
    writers(output)
    name='critical-writers-v2.json'
    raw=(output/name).read_bytes()
    assert raw==(HERE/name).read_bytes()
    result=json.loads(raw)
    report={'unit_tests_passed':9,'accepted_source_instruction_count':result['accepted_source_instruction_count'],
            'exact_report_replays':[name],'output_sha256':local.sha(raw),
            'entry_hypotheses_replayed':len(result['reports']),
            'new_source_cfg_verifier_runs':2,'runtime_launches':0,
            'natural_execution_proven':False,'promotion_bytes':0}
    (output/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')


if __name__ == '__main__':
    with Path(sys.argv[2]).open('x') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:main(Path(sys.argv[1]).resolve())
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
