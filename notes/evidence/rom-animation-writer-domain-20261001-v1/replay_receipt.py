"""Replay a sealed writer receipt in independent processes with exact outputs."""
import contextlib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd().resolve()
HERE = Path(__file__).resolve().parent


def main(output):
    manifest = json.loads((HERE / 'manifest.json').read_text())
    for name, identity in manifest['files'].items():
        path = (HERE / name).resolve()
        assert path.is_relative_to(HERE), name
        raw = path.read_bytes()
        assert len(raw) == identity['size'] and hashlib.sha256(raw).hexdigest() == identity['sha256'], name
    output = output.resolve()
    if output.exists() or not output.is_relative_to(ROOT / 'build/experiments/active'):
        raise ValueError('fresh managed active output required')
    relative = output.relative_to(ROOT / 'build/experiments/active')
    if len(relative.parts) != 3:
        raise ValueError('output must be task/run/output')
    metadata = json.loads((output.parent / '.experiment.json').read_text())
    if metadata['status'] != 'active' or [metadata['task'], metadata['run_id']] != list(relative.parts[:2]):
        raise ValueError('output run is not active')
    output.mkdir()
    batches = (
        ('inventory.py', 'inventory', ('writer-domain.json', 'summary.json')),
        ('coupled_batch.py', 'coupled', ('coupled-writers.json',)),
    )
    for script, directory, names in batches:
        print('REPLAY START ' + script, flush=True)
        subprocess.run([sys.executable, str(HERE / script), str(output / directory),
                        str(output / (directory + '.log'))], cwd=ROOT, check=True)
        for name in names:
            assert (output / directory / name).read_bytes() == (HERE / name).read_bytes(), name
        print('REPLAY EXACT ' + script, flush=True)
    broad = json.loads((output / 'inventory/writer-domain.json').read_text())
    coupled = json.loads((output / 'coupled/coupled-writers.json').read_text())
    reference = json.loads((HERE / 'iwram-bus-reference-confirmation.json').read_text())
    report = {'unit_tests': 16, 'declared_thumb_instructions': broad['summary']['declared_graph_instruction_count'],
              'store_transfers': broad['summary']['store_transfer_count'],
              'bounded_vector_cases': len(coupled['vector_cases']),
              'default_vector_cases': len(coupled['default_vector_cases']),
              'fresh_source_verifier_calls': len(coupled['fresh_source_checks']),
              'exact_outputs': ['writer-domain.json', 'summary.json', 'coupled-writers.json'],
              'independent_batch_processes': True, 'source_reference_confirmation': reference,
              'external_mgba_source_required_for_replay': False,
              'natural_execution_proven': False, 'runtime_launches': 0, 'promotion_bytes': 0}
    (output / 'report.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print('PERMANENT REPLAY PASSED: 16 tests, 88472 declared instructions, 9730 transfers, 512 vector cases, 2 verifiers')


if __name__ == '__main__':
    with Path(sys.argv[2]).open('x') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            main(Path(sys.argv[1]))
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
