"""Verify parent receipt and derive the five raw bounded callee summaries."""
import contextlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))
from callee_effects import analyze, local
from tools.verify_rom_cfg_inventory import _decode

HERE = Path(__file__).parent
PARENT = Path('notes/evidence/rom-animation-caller-predecessor-20261001-v1')
WINDOWS = [(0x626B4, 0x62786), (0x6571C, 0x65724), (0x66758, 0x667A0),
           (0x6F5BC, 0x6F70C), (0x8D580, 0x8D65E)]


def fixed_graph():
    manifest_raw = (PARENT/'manifest.json').read_bytes()
    assert local.sha(manifest_raw) == '1ba62270af82fec601f758a6fb2637521f5e05f5a46efde4ce9cdc213fa918c8'
    manifest = json.loads(manifest_raw)
    for name, identity in manifest['files'].items():
        raw = (PARENT/name).read_bytes()
        assert len(raw) == identity['size'] and local.sha(raw) == identity['sha256']
    parent_raw = (PARENT/'predecessors-v4.json').read_bytes()
    parent = json.loads(parent_raw)
    rom = Path('rom/base.gba').read_bytes()
    assert local.sha(rom) == parent['rom_sha256']
    offsets = set()
    for row in parent['source_ranges']:
        start, end = row['range']
        assert local.sha(rom[start:end]) == row['sha256']
        at = start
        while at < end:
            i = _decode(rom, at, 'thumb')
            assert i['accepted'] and at+i['size'] <= end
            offsets.add(at)
            at += i['size']
    assert len(offsets) == parent['source_instruction_count']
    return rom, offsets, parent, local.sha(parent_raw)


def derive(rom, offsets):
    rows = []
    for start, end in WINDOWS:
        allowed = offsets & set(range(start, end))
        assert start in allowed
        rows.append({'range': [start, end], 'raw_window_sha256': local.sha(rom[start:end]),
                     'strict': analyze(rom, start, allowed),
                     'conditional_frame': analyze(rom, start, allowed, conditional_frame=True)})
    return rows


def main(output_root=None):
    rom, offsets, parent, parent_sha = fixed_graph()
    rows = derive(rom, offsets)
    # The BIOS stub is raw evidence, not one of the five source callee contracts.
    svc = analyze(rom, 0x9C0E0, {0x9C0E0, 0x9C0E2}, conditional_frame=True)
    assert svc['frontiers'] == [{'kind': 'external_svc', 'at': 0x9C0E0, 'number': 11}]
    payload = {'schema': 'animation-callee-identities-v1', 'parent_sha256': parent_sha,
               'rom_sha256': local.sha(rom), 'source_instruction_count': len(offsets),
               'implementation_inputs': {name: local.sha((HERE/name).read_bytes())
                                         for name in ('callee_effects.py','analyze_batch.py','test_effects.py')},
               'rows': rows, 'bios_stub': svc,
               'scope': 'Bounded identities only; child/private-frame preconditions are unproved for callers. '
                        'No BIOS effect contract, caller memory preservation or natural execution.',
               'promotion_bytes': 0}
    destination = Path(output_root) if output_root is not None else HERE
    (destination/'callee-effects-v2.json').write_text(json.dumps(payload, sort_keys=True, indent=2)+'\n')
    for row in rows:
        print(hex(row['range'][0]), {k: {'returns': row[k]['return_count'],
               'preserved': row[k]['preserved_registers'], 'frontiers': row[k]['frontiers'],
               'conditions': len(row[k]['preconditions'])} for k in ('strict','conditional_frame')})


if __name__ == '__main__':
    with (HERE/'analysis-v2.log').open('x') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            main()
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
