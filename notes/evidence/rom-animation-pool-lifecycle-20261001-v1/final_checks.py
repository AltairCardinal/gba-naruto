import ast
import contextlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from analysis import main as analyze, sha
from advance_probe import probe
from derive_facts import main as facts


def main():
    suite = unittest.TestSuite()
    for name in ('test_analysis', 'test_advance_probe'):
        spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful() and result.testsRun == 19
    analyze(HERE / 'audit-replay.json')
    assert (HERE / 'audit-replay.json').read_bytes() == (HERE / 'audit-final.json').read_bytes()
    facts(HERE / 'facts-replay.json')
    assert (HERE / 'facts-replay.json').read_bytes() == (HERE / 'facts-final-v2.json').read_bytes()
    validation = json.loads((HERE / 'validation.json').read_text())
    rom = Path('rom/base.gba').read_bytes()
    for row in validation['probe_matrix']:
        trace = probe(rom, row['sequence'], flags=row['flags'], count=row['count'], timer=row['initial_timer'])
        raw = json.dumps(trace, sort_keys=True, separators=(',', ':')).encode()
        assert sha(raw) == row['trace_sha256']
    python_files = list(HERE.glob('*.py'))
    for path in python_files:
        source = path.read_text()
        ast.parse(source)
        assert source.endswith('\n') and not any(line.rstrip() != line for line in source.splitlines())
    summary = {'schema': 'animation-lifecycle-final-checks-v1', 'unit_tests': result.testsRun,
               'unit_passed': True, 'audit_exact_replay': True, 'facts_exact_replay': True,
               'finite_probe_exact_replays': len(validation['probe_matrix']),
               'source_reports_passed': sum(r['verified'] and not r.get('errors')
                                             for r in validation['source_reports'].values()),
               'python_ast_and_whitespace_files': len(python_files),
               'unchanged_ledgers': {p: sha(Path(p).read_bytes()) for p in (
                   'sequel/rom-byte-coverage.json', 'sequel/reverse-engineering-proof.json', 'sequel/bank-proofs.json')},
               'mgba_launched': False, 'formal_rerun': False, 'promotion_bytes': 0}
    (HERE / 'final-checks.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    with (HERE / 'final-checks.log').open('x') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            main()
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
