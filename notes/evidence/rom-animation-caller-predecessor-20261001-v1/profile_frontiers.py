import contextlib
import json
from pathlib import Path
import sys
from collections import Counter

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))
from frontier import compile_graph, dependencies
from flow import local
from tools.verify_rom_cfg_inventory import _decode

HERE = Path(__file__).parent


def main(output_root=None, parent_path=None):
    raw = (Path(parent_path) if parent_path is not None else HERE / 'predecessors-v4.json').read_bytes()
    parent = json.loads(raw)
    for p, digest in parent['implementation_inputs'].items():
        assert local.sha((HERE / p).read_bytes()) == digest
    rom = Path('rom/base.gba').read_bytes()
    assert local.sha(rom) == parent['rom_sha256']
    offsets = set()
    for row in parent['source_ranges']:
        start, end = row['range']
        assert local.sha(rom[start:end]) == row['sha256']
        at = start
        while at < end:
            decoded = _decode(rom, at, 'thumb')
            assert decoded['accepted'] and at + decoded['size'] <= end
            offsets.add(at)
            at += decoded['size']
    roots = set(parent['root_offsets'])
    assert len(offsets) == parent['source_instruction_count']
    context = compile_graph(rom, offsets, roots)
    rows = []
    for row in parent['models']['raw_allocator_conditional_registers']['rows']:
        for key, offset in [('flags', 12), ('callback', 16)]:
            if row.get(key) is None:
                report = dependencies(rom, offsets, roots, row['site'], offset, context=context)
                rows.append({'site': row['site'], 'field': key, 'dependency_report': report})
    all_frontiers = [f for r in rows for f in r['dependency_report']['frontiers']]
    targets = sorted({f['target'] for f in all_frontiers if 'target' in f})
    payload = {'schema': 'animation-caller-dependency-frontiers-v1', 'parent_sha256': local.sha(raw),
               'inputs': {p: local.sha((HERE / p).read_bytes()) for p in ('frontier.py', 'profile_frontiers.py', 'test_frontier.py')},
               'field_count': len(rows), 'rows': rows, 'frontier_kinds': dict(Counter(f['kind'] for f in all_frontiers)),
               'callee_targets': [{'target': at, 'head_raw_hex': rom[at:at + 16].hex(),
                                    'head_sha256': local.sha(rom[at:at + 16])} for at in targets],
               'scope': 'Dependency work-package planning only; no complete field or callee proof.',
               'promotion_bytes': 0}
    destination = Path(output_root) if output_root is not None else HERE
    (destination / 'frontiers-v3.json').write_text(json.dumps(payload, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    with (HERE / 'frontiers-v3.log').open('x') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            main()
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
