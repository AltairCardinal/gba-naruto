"""Fixed raw windows for next shared-callee work package; no value proof."""
import json
from pathlib import Path
from flow import local
from tools.verify_rom_cfg_inventory import _decode

HERE = Path(__file__).parent
WINDOWS = [(0x626B4, 0x62786), (0x6571C, 0x65728),
           (0x66758, 0x667A0), (0x6F5BC, 0x6F70C),
           (0x8D580, 0x8D65E), (0x9C0E0, 0x9C0E4)]


def main(output_root=None, parent_path=None):
    parent_raw = (Path(parent_path) if parent_path is not None else HERE / 'predecessors-v4.json').read_bytes()
    parent = json.loads(parent_raw)
    rom = Path('rom/base.gba').read_bytes()
    assert local.sha(rom) == parent['rom_sha256']
    members = set()
    for row in parent['source_ranges']:
        start, end = row['range']
        assert local.sha(rom[start:end]) == row['sha256']
        at = start
        while at < end:
            i = _decode(rom, at, 'thumb')
            assert i['accepted'] and at + i['size'] <= end
            members.add(at)
            at += i['size']
    rows = []
    for start, end in WINDOWS:
        actual = []
        for at in sorted(members & set(range(start, end))):
            i = _decode(rom, at, 'thumb')
            actual.append({'at': at, 'raw_hex': rom[at:at+i['size']].hex(),
                           'flow_kind': i['flow_kind'], 'successors': i['successors']})
        rows.append({'range': [start, end], 'raw_hex': rom[start:end].hex(),
                     'sha256': local.sha(rom[start:end]), 'source_instructions': actual,
                     'window_is_complete_callee_contract': False})
    assert rom[0x6571C:0x65724].hex() == '0149012008707047'
    assert int.from_bytes(rom[0x65724:0x65728], 'little') == 0x0201BD68
    assert rom[0x9C0E0:0x9C0E4].hex() == '0bdf7047'
    payload = {'schema': 'animation-callee-raw-windows-v1',
               'parent_sha256': local.sha(parent_raw), 'rom_sha256': local.sha(rom),
               'implementation_sha256': local.sha((HERE/'inspect_callees.py').read_bytes()),
               'windows': rows,
               'leaf_6571c': {'instructions_hex': '0149012008707047', 'literal_address': 0x65724,
                              'global_byte_store_address': 0x0201BD68,
                              'register_preservation_contract_accepted': False},
               'bios_stub_9c0e0': {'raw_hex': '0bdf7047', 'thumb_svc_number': 11,
                                   'bios_register_effects_proven_from_rom': False},
               'scope': 'Raw windows and known source membership only; callee boundaries, '
                        'child effects, private-frame aliasing and BIOS semantics remain separate proof obligations.',
               'promotion_bytes': 0}
    destination = Path(output_root) if output_root is not None else HERE
    (destination/'callee-windows.json').write_text(json.dumps(payload, sort_keys=True, indent=2)+'\n')


if __name__ == '__main__':
    main()
