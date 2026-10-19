"""Replay this frozen research packet into a fresh active managed output."""
import ast
import contextlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path.cwd().resolve()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from flow import local
from analyze_batch import main as analyze
from profile_frontiers import main as profile
from inspect_callees import main as inspect


def main(output):
    manifest = json.loads((HERE/'manifest.json').read_text())
    for name, identity in manifest['files'].items():
        raw = (HERE/name).read_bytes()
        assert len(raw) == identity['size'] and local.sha(raw) == identity['sha256'], name
    if output.exists() or not output.is_relative_to(ROOT/'build/experiments/active'):
        raise ValueError('fresh managed active output required')
    relative = output.relative_to(ROOT/'build/experiments/active')
    if len(relative.parts) != 3:
        raise ValueError('output must be task/run/output')
    metadata = json.loads((output.parent/'.experiment.json').read_text())
    if metadata['status'] != 'active' or [metadata['task'], metadata['run_id']] != list(relative.parts[:2]):
        raise ValueError('output run is not active')
    output.mkdir()
    suite = unittest.TestSuite()
    for name in ('test_flow', 'test_frontier'):
        spec = importlib.util.spec_from_file_location(name, HERE/(name+'.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful() and result.testsRun == 18
    for path in sorted(HERE.glob('*.py')):
        ast.parse(path.read_text())
        assert not any(line.rstrip() != line for line in path.read_text().splitlines()), path
    analyze(output)
    profile(output, output/'predecessors-v4.json')
    inspect(output, output/'predecessors-v4.json')
    names = ('predecessors-v4.json', 'frontiers-v3.json', 'callee-windows.json')
    for name in names:
        assert (output/name).read_bytes() == (HERE/name).read_bytes(), name
    parent = json.loads((output/names[0]).read_text())
    frontier = json.loads((output/names[1]).read_text())
    report = {'unit_tests_passed': 18, 'whole_graph_instruction_count': parent['source_instruction_count'],
              'exact_report_replays': list(names), 'dependency_fields_replayed': frontier['field_count'],
              'source_receipt_all_members_verified': True, 'new_source_cfg_verifier_runs': 0,
              'runtime_launches': 0, 'natural_execution_proven': False, 'promotion_bytes': 0,
              'output_sha256': {name: local.sha((output/name).read_bytes()) for name in names}}
    (output/'report.json').write_text(json.dumps(report, sort_keys=True, indent=2)+'\n')


if __name__ == '__main__':
    with Path(sys.argv[2]).open('x') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            main(Path(sys.argv[1]).resolve())
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
