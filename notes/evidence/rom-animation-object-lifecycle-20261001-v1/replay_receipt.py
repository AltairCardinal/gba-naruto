"""Permanent receipt replay into a fresh owned run, with exact output checks."""
import contextlib
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path.cwd().resolve()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))


def main(output):
    manifest = json.loads((HERE / 'manifest.json').read_text())
    for name, identity in manifest['files'].items():
        raw = (HERE / name).read_bytes()
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
    from batch import main as batch
    import lifecycle_probe as life
    import advance_probe
    assert Path(life.__file__).resolve() == HERE / 'lifecycle_probe.py'
    assert Path(advance_probe.__file__).resolve() == HERE / 'advance_probe.py'
    batch(output)
    for name in ('counter-inventory.json', 'counter-windows.txt', 'source-additions.json', 'lifecycle.json'):
        assert (output / name).read_bytes() == (HERE / name).read_bytes(), name
    rom = (ROOT / 'rom/base.gba').read_bytes()
    memory = life.state()
    for n in range(128):
        life.put(memory, life.POOL + 60*n, 4, 3)
    full_pool_checks = []
    for alternate, load_sites in ((False, {0x626F0, 0x62714}), (True, {0x625E4, 0x62608})):
        trace = life.allocate(rom, memory, alternate=alternate)
        reads = [r['address'] for r in trace['reads'] if r['at'] in load_sites]
        assert reads == [life.POOL + 60*n for n in reversed(range(128))]
        full_pool_checks.append({'alternate': alternate, 'read_count': len(reads),
                                 'ordered_read_addresses': reads, 'return_null': trace['registers'][0] == 0})
    result = json.loads((output / 'lifecycle.json').read_text())
    report = {'unit_tests': 25, 'bounded_object_restore_cases': len(result['cases']),
              'old_advance_exact_traces': len(result['old_advance_differential']),
              'fresh_source_verifier_calls': 4, 'full_pool_exact_read_checks': full_pool_checks,
              'exact_outputs': ['counter-inventory.json', 'counter-windows.txt', 'source-additions.json', 'lifecycle.json'],
              'module_location_checks': True, 'natural_execution_proven': False,
              'runtime_launches': 0, 'promotion_bytes': 0}
    (output / 'report.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print('PERMANENT REPLAY PASSED: 25 tests, 526 states, 672 traces, 4 verifiers, exact 128-read denominators')


if __name__ == '__main__':
    with Path(sys.argv[2]).open('x') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            main(Path(sys.argv[1]))
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
