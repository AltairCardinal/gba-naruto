"""Broad declared-source writer investigation, not a global completion proof."""
import ast
from collections import Counter
import contextlib
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path.cwd().resolve()
HERE = Path(__file__).resolve().parent
BASE = ROOT / 'notes/evidence/rom-animation-object-lifecycle-20261001-v1'
PARENT = ROOT / 'notes/evidence/rom-animation-interprocedural-identities-20261001-v1'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(HERE))
from flow import run_flow
from tools.verify_rom_cfg_inventory import _decode
from writer_domain import root_set, stores, cover_range

PROGRESS = sys.stdout
IMPLEMENTATIONS = ('writer_domain.py', 'inventory.py', 'test_writer_domain.py')
COVERAGE_SHA = 'b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def main(output):
    output = Path(output)
    if output.exists():
        raise ValueError('fresh output required')
    output.mkdir()
    for name in IMPLEMENTATIONS:
        raw = (HERE / name).read_bytes()
        ast.parse(raw)
        assert all(line == line.rstrip() for line in raw.decode().splitlines())
    import test_writer_domain
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_writer_domain))
    assert result.wasSuccessful() and result.testsRun == 11
    inputs = {}
    def read(name, expected=None):
        name = str(name)
        raw = (ROOT / name).read_bytes()
        if expected is not None:
            assert sha(raw) == expected, name
        inputs[name] = {'size': len(raw), 'sha256': sha(raw)}
        return raw
    def receipt(directory, expected):
        relative = directory.relative_to(ROOT)
        raw = read(relative / 'manifest.json', expected)
        for name, identity in json.loads(raw)['files'].items():
            member = read(relative / name, identity['sha256'])
            assert len(member) == identity['size']
    receipt(BASE, '7c34067d76ae81ecc15d03b9681295e78ac8971df2d05e59c024e3a69c12db8b')
    receipt(PARENT, '1aca46ee19d8af2ddf051f1daa1fbfec1cd660245578020f689303116ff78e70')
    prior = json.loads((BASE / 'lifecycle.json').read_text())
    for name, identity in prior['inputs'].items():
        assert len(read(name, identity['sha256'])) == identity['size']
    rom = read('rom/base.gba', prior['rom_sha256'])
    coverage = json.loads(read('sequel/rom-byte-coverage.json', COVERAGE_SHA))
    counter = json.loads((BASE / 'counter-inventory.json').read_text())
    additions = json.loads((BASE / 'source-additions.json').read_text())
    offsets = set()
    def add_range(start, end):
        assert 0 <= start < end <= len(rom) and not (start | end) & 1
        at = start
        while at < end:
            instruction = _decode(rom, at, 'thumb')
            assert instruction['accepted'] and at + instruction['size'] <= end
            offsets.add(at)
            at += instruction['size']
    for start, end in counter['source_ranges']:
        add_range(start, end)
    for group in additions['source_groups'].values():
        for start, end in group['code_ranges']:
            add_range(start, end)
    assert len(offsets) == 67243
    old_count = len(offsets)
    declared = set()
    claims, excluded = [], []
    explicit_source_ranges = []
    source_paths = {c['evidence_path']: c['evidence_sha256'] for c in coverage['claims']
                    if c.get('role') == 'primary' and 'instruction' in c.get('claim_kind', '') and c.get('mode') == 'thumb'}
    def raw_blocks(value, path=''):
        if isinstance(value, dict):
            if value.get('mode') == 'thumb' and 'instruction_count' in value and 'range' in value:
                yield path, value['range']
            # Explicit full Thumb CFG schemas; promotion is never inferred to be a full partition.
            for key in ('target_local_denominator', 'target_local_cfg', 'thumb_continuation'):
                if isinstance(value.get(key), dict) and 'code_ranges' in value[key]:
                    for n, bounds in enumerate(value[key]['code_ranges']):
                        yield path + '/' + key + '/code_ranges/' + str(n), bounds
            for key, child in value.items():
                if key not in ('promotion', 'promotion_ranges', 'coverage_claims'):
                    yield from raw_blocks(child, path+'/'+key)
        elif isinstance(value, list):
            for n, child in enumerate(value):
                yield from raw_blocks(child, path+'/'+str(n))
    for name, digest in sorted(source_paths.items()):
        source = json.loads(read(name, digest))
        for selector, bounds in raw_blocks(source):
            before = len(offsets)
            try:
                result = cover_range(rom, *bounds, offsets)
            except ValueError as error:
                excluded.append({'path': name, 'selector': selector, 'range': bounds,
                                 'reason': 'explicit_source_partition_not_accepted', 'error': str(error)})
                continue
            offsets.update(result['new_nodes'])
            explicit_source_ranges.append({'path': name, 'selector': selector, 'range': bounds,
                                           'net_new_declared_nodes': len(offsets)-before})
    for claim in coverage['claims']:
        if claim.get('role') != 'primary' or 'instruction' not in claim.get('claim_kind', ''):
            continue
        start, end = claim['range']
        if claim.get('mode') != 'thumb':
            excluded.append({'id': claim['id'], 'range': claim['range'], 'mode': claim.get('mode'),
                             'reason': 'explicit_thumb_mode_required_not_inferred_from_class'})
            continue
        assert sha(rom[start:end]) == claim['bytes_sha256'], claim['id']
        read(claim['evidence_path'], claim['evidence_sha256'])
        read(claim['independent_verifier_path'], claim['independent_verifier_sha256'])
        if 'promotion_manifest_path' in claim:
            read(claim['promotion_manifest_path'], claim['promotion_manifest_sha256'])
        # These new ranges are ledger declarations with current identity binding.
        # No fresh semantic verifier replay is claimed for this broad inventory.
        try:
            partition = cover_range(rom, start, end, offsets)
        except ValueError as error:
            excluded.append({'id': claim['id'], 'range': claim['range'], 'mode': 'thumb',
                             'reason': 'complete_instruction_partition_unresolved', 'error': str(error)})
            continue
        offsets.update(partition['new_nodes'])
        if partition['range_start_is_instruction']:
            declared.add(start)
        claims.append({'id': claim['id'], 'range': claim['range'], 'path': claim['evidence_path'],
                       'sha256': claim['bytes_sha256'], 'evidence_selector': claim['evidence_selector'],
                       'new_source_semantic_verifier_replayed': False, 'partition': partition})
    parent = json.loads((ROOT / 'notes/evidence/rom-animation-caller-predecessor-20261001-v1/predecessors-v4.json').read_text())
    declared |= set(parent['root_offsets'])
    decoded = {at: _decode(rom, at, 'thumb') for at in sorted(offsets)}
    assert all(row['accepted'] for row in decoded.values())
    roots = root_set(decoded, declared)
    print('fixed writer graph', len(offsets), 'roots', len(roots['roots']), 'declared claims', len(claims), file=PROGRESS, flush=True)
    model = run_flow(rom, offsets, set(roots['roots']))
    print('opaque constant flow updates', model['updates'], 'states', len(model['states']), file=PROGRESS, flush=True)
    events = stores(rom, offsets, model['states'])
    effects = []
    for at, instruction in decoded.items():
        state = model['states'].get(at)
        if instruction['flow_kind'] == 'call':
            effects.append({'at': at, 'kind': 'opaque_call', 'target': next(e['file_offset'] for e in instruction['successors'] if e['kind'] == 'call_target'),
                            'args': {r: value for r, value in (state or {}).get('registers', {}).items() if r < 4},
                            'reachable_in_model': state is not None, 'memory_effects_proven': False})
        elif struct.unpack_from('<H', rom, at)[0] & 0xFF00 == 0xDF00:
            effects.append({'at': at, 'kind': 'external_svc', 'number': rom[at], 'memory_effects_proven': False})
        elif instruction['flow_kind'] not in ('linear', 'conditional_branch', 'unconditional_branch'):
            effects.append({'at': at, 'kind': 'return_or_indirect_or_mode_boundary', 'flow_kind': instruction['flow_kind'],
                            'memory_effects_proven': False})
    target_events = [e for e in events if e['overlaps']]
    summary = {'old_source_instruction_count': old_count, 'declared_graph_instruction_count': len(offsets),
               'net_new_declared_members': len(offsets) - old_count, 'primary_thumb_claim_count': len(claims),
               'explicit_mode_excluded_claim_count': sum(e['reason'].startswith('explicit_thumb_mode') for e in excluded),
               'partition_exclusion_count': sum(not e['reason'].startswith('explicit_thumb_mode') for e in excluded),
               'cross_boundary_claim_count': sum(bool(c['partition']['cross_boundary_existing_nodes']) for c in claims),
               'entry_root_count': len(roots['roots']),
               'constant_flow_updates': model['updates'], 'model_reached_instructions': len(model['states']),
               'store_instruction_count': len({e['at'] for e in events}), 'store_transfer_count': len(events),
               'unknown_address_transfer_count': sum(e['address_unknown'] for e in events),
               'not_reached_transfer_count': sum(not e['reachable_in_model'] for e in events),
               'known_direct_target_transfer_count': len(target_events),
               'known_direct_target_labels': dict(Counter(label for e in target_events for label in e['overlaps'])),
               'known_dma_register_transfer_count': sum(e['dma_control_or_address_write'] for e in events),
               'opaque_memory_effect_count': len(effects), 'model': 'all_callees_opaque'}
    for name, identity in inputs.items():
        raw = (ROOT / name).read_bytes()
        assert len(raw) == identity['size'] and sha(raw) == identity['sha256'], name
    payload = {'schema': 'animation-writer-domain-v1', 'rom_sha256': sha(rom), 'inputs': inputs,
               'implementation_inputs': {name: sha((HERE / name).read_bytes()) for name in IMPLEMENTATIONS},
               'summary': summary, 'root_model': roots, 'declared_primary_sources': claims,
               'explicit_mode_or_partition_exclusions': excluded, 'declared_explicit_source_ranges': explicit_source_ranges,
               'target_stores': target_events,
               'all_store_transfers': events, 'opaque_memory_effects': effects,
               'natural_execution_proven': False, 'global_writer_exhaustiveness_proven': False,
               'new_source_semantic_verifier_runs': 0, 'runtime_launches': 0, 'promotion_bytes': 0,
               'scope': 'Old verified source plus hash-bound canonical-declared Thumb ranges. Extra indirect entries, missing/mixed/ARM code, caller/SP domains, unknown addresses and all external memory effects remain open.'}
    (output / 'writer-domain.json').write_bytes(encode(payload))
    (output / 'summary.json').write_bytes(encode(summary))
    print(json.dumps(summary, sort_keys=True), file=PROGRESS, flush=True)


if __name__ == '__main__':
    with Path(sys.argv[2]).open('x') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            main(Path(sys.argv[1]))
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
