"""Replay immutable receipt code into a fresh managed run without build inputs."""
import contextlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path.cwd().resolve()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from analysis import main as analyze, sha
from advance_probe import probe
from derive_facts import main as facts


def main(output):
    if output.exists() or not output.is_relative_to(ROOT / 'build/experiments/active'):
        raise ValueError('fresh active managed output required')
    relative = output.relative_to(ROOT / 'build/experiments/active')
    if len(relative.parts) != 3:
        raise ValueError('output must be task/run/output')
    metadata = json.loads((output.parent / '.experiment.json').read_text())
    if metadata['status'] != 'active' or [metadata['task'], metadata['run_id']] != list(relative.parts[:2]):
        raise ValueError('output run is not active')
    output.mkdir()
    suite = unittest.TestSuite()
    for name in ('test_analysis', 'test_advance_probe'):
        spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful() and result.testsRun == 19
    analyze(output / 'audit.json')
    expected = json.loads((HERE / 'audit-final.json').read_text())
    actual = json.loads((output / 'audit.json').read_text())
    # Only the self-source locator moves. Its bytes must retain their identity.
    code_sha = sha((HERE / 'analysis.py').read_bytes())
    for payload in (expected, actual):
        keys = [k for k in payload['inputs'] if k.endswith('/analysis.py')]
        assert len(keys) == 1 and payload['inputs'][keys[0]]['sha256'] == code_sha
        del payload['inputs'][keys[0]]
    assert actual == expected
    facts(output / 'facts.json')
    assert (output / 'facts.json').read_bytes() == (HERE / 'facts-final-v2.json').read_bytes()
    validation = json.loads((HERE / 'validation.json').read_text())
    rom = Path('rom/base.gba').read_bytes()
    for row in validation['probe_matrix']:
        trace = probe(rom, row['sequence'], flags=row['flags'], count=row['count'], timer=row['initial_timer'])
        assert sha(json.dumps(trace, sort_keys=True, separators=(',', ':')).encode()) == row['trace_sha256']
    report = {'unit_tests_passed': 19, 'audit_semantic_replay_equal': True,
              'only_self_source_locator_changed': True, 'self_source_sha256': code_sha,
              'facts_exact_replay_equal': True, 'finite_probe_exact_replays': 672,
              'new_source_cfg_verifier_runs': 0, 'runtime_launches': 0,
              'natural_execution_proven': False, 'promotion_bytes': 0}
    (output / 'report.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    output = Path(sys.argv[1]).resolve()
    with Path(sys.argv[2]).open('x') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            main(output)
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
