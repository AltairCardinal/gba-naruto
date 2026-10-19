"""Compile all nine fixed source artifacts and compare two explicit flow models."""
import contextlib
import gc
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))
from flow import allocator_contract, run_flow, local
from tools.verify_rom_cfg_inventory import _decode

HERE = Path(__file__).parent
RECEIPT = Path('notes/evidence/rom-animation-pool-lifecycle-20261001-v1')
PROGRESS = sys.stdout


def roots_in(source):
    roots = set()

    def walk(value, name=''):
        if isinstance(value, dict):
            if ('root' in name or name in ('new_entry_seeds', 'target_seeds')) and value.get('mode') == 'thumb':
                at = value.get('file_offset', value.get('entry_file_offset'))
                if type(at) is int:
                    roots.add(at)
            for key, child in value.items():
                walk(child, key)
        elif isinstance(value, list):
            if name in ('root_producers', 'matches'):
                for row in value:
                    if isinstance(row, list) and len(row) >= 3 and row[2] in ('bl', 'b', 'bcond'):
                        roots.add(row[1])
            for child in value:
                walk(child, name)
    walk(source)
    return roots


def main(output_root=None):
    manifest = json.loads((RECEIPT / 'manifest.json').read_text())
    for name, identity in manifest['files'].items():
        raw = (RECEIPT / name).read_bytes()
        assert len(raw) == identity['size'] and local.sha(raw) == identity['sha256']
    audit = json.loads((RECEIPT / 'audit-final.json').read_text())
    validation = json.loads((RECEIPT / 'validation.json').read_text())
    assert validation['source_count'] == 9
    assert all(r['verified'] and not r.get('errors') for r in validation['source_reports'].values())
    for path, identity in audit['inputs'].items():
        if path.endswith('/analysis.py'):
            raw = (RECEIPT / 'analysis.py').read_bytes()
        else:
            raw = Path(path).read_bytes()
        assert len(raw) == identity['size'] and local.sha(raw) == identity['sha256'], path
    rom = Path('rom/base.gba').read_bytes()
    instructions, source_ranges, roots = {}, [], set()
    paths = sorted(validation['source_reports'])
    for path in paths:
        print('Compiling source graph: ' + path, file=PROGRESS, flush=True)
        source = json.loads(Path(path).read_text())
        roots |= roots_in(source)
        ranges = local.source_ranges(source)
        for (start, end), digest in ranges:
            if digest:
                assert local.sha(rom[start:end]) == digest
            source_ranges.append({'path': path, 'range': [start, end], 'sha256': local.sha(rom[start:end])})
            at = start
            while at < end:
                i = _decode(rom, at, 'thumb')
                assert i['accepted'] and at + i['size'] <= end
                if at in instructions:
                    assert instructions[at] == i
                instructions[at] = i
                at += i['size']
    offsets = set(instructions)
    predecessors = {at: set() for at in offsets}
    for at, i in instructions.items():
        for edge in i['successors']:
            target = edge['file_offset']
            if target not in offsets:
                continue
            if edge['kind'] == 'call_target':
                roots.add(target)
            else:
                predecessors[target].add(at)
    roots = (roots & offsets) | {at for at, incoming in predecessors.items() if not incoming}
    # Disconnected closed cycles have no proved entry. Seed every node in them,
    # rather than inventing one convenient root and deriving constants from it.
    reachable, pending = set(), list(roots)
    while pending:
        at = pending.pop()
        if at in reachable:
            continue
        reachable.add(at)
        pending.extend(e['file_offset'] for e in instructions[at]['successors']
                       if e['kind'] != 'call_target' and e['file_offset'] in offsets)
    disconnected = offsets - reachable
    roots |= disconnected
    pool_rows = [r for r in audit['rows'] if 'base_pair' in r]
    assert len(pool_rows) == 47 and all(r['site'] in offsets for r in pool_rows)
    modes = {}
    contract = allocator_contract(rom)
    for name, summary in [('all_callees_opaque', None), ('raw_allocator_conditional_registers', contract)]:
        print('Constant-flow fixed point: ' + name, file=PROGRESS, flush=True)
        result = run_flow(rom, offsets, roots, allocator=summary)
        rows = []
        for prior in pool_rows:
            state = result['states'].get(prior['site'])
            row = {'site': prior['site'], 'historical_base_pair': prior['base_pair'],
                   'historical_group': prior['group'], 'reachable_in_model': state is not None,
                   'historical_local_flags': prior['flags_stack_argument'],
                   'historical_local_callback': prior['callback_stack_argument']}
            if state is not None:
                row.update({'known_registers': state['registers'], 'known_stack': state['stack'],
                            'flags': state['stack'].get(12), 'callback': state['stack'].get(16),
                            'conditional_allocator_preservation': state['conditional_allocator_preservation'],
                            'unverified_call_continuation': state['unverified_call_continuation']})
                pair = [state['registers'].get(r, 0) - local.BASE for r in (0, 1)]
                row['pair_and_group_rebuilt'] = (pair == prior['base_pair']
                                                  and state['registers'].get(2) == prior['group'])
            rows.append(row)
        modes[name] = {'rows': rows, 'updates': result['updates'], 'root_count': len(roots),
                       'both_fields_fixed': sum(r.get('flags') is not None and r.get('callback') is not None for r in rows),
                       'flags_fixed': sum(r.get('flags') is not None for r in rows),
                       'callbacks_fixed': sum(r.get('callback') is not None for r in rows),
                       'pair_group_rebuilt': sum(r.get('pair_and_group_rebuilt', False) for r in rows)}
        del result
        gc.collect()
    payload = {'schema': 'animation-caller-predecessor-audit-v1',
               'implementation_inputs': {p: local.sha((HERE / p).read_bytes())
                                         for p in ('flow.py', 'analyze_batch.py', 'test_flow.py')},
               'rom_sha256': local.sha(rom), 'prior_manifest_sha256': local.sha((RECEIPT / 'manifest.json').read_bytes()),
               'prior_audit_sha256': local.sha((RECEIPT / 'audit-final.json').read_bytes()),
               'source_ranges': source_ranges, 'source_instruction_count': len(offsets),
               'root_offsets': sorted(roots), 'disconnected_unproven_entry_nodes': sorted(disconnected),
               'root_scope': 'artifact roots, direct call entries, missing predecessors and all disconnected nodes',
               'allocator_contract': contract, 'models': modes,
               'scope': 'Fixed known source graph only. Neither model proves additional indirect/ARM entries, '
                        'private stack non-aliasing, opaque-call context resumption, callback effects, '
                        'object lifecycle or natural runtime reachability.',
               'promotion_bytes': 0}
    destination = Path(output_root) if output_root is not None else HERE
    (destination / 'predecessors-v4.json').write_text(json.dumps(payload, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    with (HERE / 'analysis-v4.log').open('x') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            main()
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
