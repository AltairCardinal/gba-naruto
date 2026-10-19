"""Bind findings to exact raw instructions; all classifications stay conditional."""
import contextlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))
from analysis import BASE, ROM_SHA, descriptor, sha
from tools.verify_rom_cfg_inventory import _decode

HERE = Path(__file__).parent


def main(output):
    rom = Path('rom/base.gba').read_bytes()
    assert sha(rom) == ROM_SHA
    audit = json.loads((HERE / 'audit-final.json').read_text())
    expected = {
        0x626B4: 'f0b5', 0x626BC: 'e0b4', 0x626BE: '82b0',
        0x626CA: '0d9d', 0x62728: '0120', 0x6272A: '0543', 0x6272C: '1560',
        0x62750: '9082', 0x62752: 'd182', 0x62754: '1183',
        0x62756: '0099', 0x62758: 'd161', 0x6275E: '0e98', 0x62760: '9062',
        0x63244: '0820', 0x63246: '0840', 0x6326C: '985e', 0x63270: '08d0',
        0x63276: 'f882', 0x632B8: 'fc82', 0x632CC: 'fff764fa',
        0x632D4: '0433', 0x632D6: '0093', 0x632E6: '0978',
    }
    points = []
    for at, raw in expected.items():
        assert rom[at:at + len(bytes.fromhex(raw))].hex() == raw, hex(at)
        decoded = _decode(rom, at, 'thumb')
        assert decoded['accepted']
        points.append({'at': at, 'raw_hex': raw, 'decode': decoded})
    first_push, second_push, sub = [struct.unpack_from('<H', rom, at)[0]
                                    for at in (0x626B4, 0x626BC, 0x626BE)]
    delta = 4 * ((first_push & 255).bit_count() + int(bool(first_push & 0x100))
                 + (second_push & 255).bit_count() + (sub & 127))
    assert delta == 0x28
    flag_offset = 4 * (struct.unpack_from('<H', rom, 0x626CA)[0] & 255) - delta
    callback_offset = 4 * (struct.unpack_from('<H', rom, 0x6275E)[0] & 255) - delta
    assert (flag_offset, callback_offset) == (12, 16)
    first, second = (0x458474, 0x45848C)
    sequence = struct.unpack_from('<I', rom, second + 4)[0] - BASE
    record, duration, stop = struct.unpack_from('<HHh', rom, sequence)
    assert (sequence, record, duration, stop) == (0x458484, 1, 0, -1)
    target = struct.unpack_from('<I', rom, first + 4 * record)[0] - BASE
    parsed = descriptor(rom, target, 0x458794)
    assert parsed['consumed_range'] == [0x458420, 0x458472]
    assert len(parsed['entry_ranges']) == 4
    known_pool = [r for r in audit['rows'] if 'base_pair' in r]
    assert len(known_pool) == 47
    assert len([r for r in known_pool if r['group'] == 0]) == 45
    assert [r['site'] for r in known_pool if r['group'] == 1] == [0x86374, 0x88A80]
    descriptors = [r['descriptor'] for r in audit['pair_rows']] + [parsed]
    candidate_bytes = sum(r['consumed_range'][1] - r['consumed_range'][0] for r in descriptors)
    assert candidate_bytes == 496
    payload = {
        'schema': 'animation-pool-lifecycle-raw-facts-v1', 'rom_sha256': sha(rom),
        'audit_sha256': sha((HERE / 'audit-final.json').read_bytes()),
        'raw_instruction_points': points,
        'allocator_stack_delta': delta, 'flags_caller_stack_offset': flag_offset,
        'callback_caller_stack_offset': callback_offset,
        'allocator_flags_expression': 'caller_flags | 1', 'freeze_mask': 8, 'freeze_bit_index': 3,
        'group1': {'base_pair': [first, second], 'sequence_record_range': [sequence, sequence + 4],
                   'record_id': record, 'duration': duration, 'sentinel_head_range': [sequence + 4, sequence + 6],
                   'descriptor': parsed, 'caller_flags': 904, 'allocator_initial_flags': 905, 'callback': 0,
                   'initial_flag_mask_8_set': True, 'natural_execution': False},
        'descriptor_candidates': {'count': 8, 'bytes_including_only_sentinel_heads': candidate_bytes,
                                  'entry_count': sum(len(r['entry_ranges']) for r in descriptors),
                                  'all_descriptor_after_head_suffixes_unclassified': True},
        'advance_terminator_modes': {
            '0x00': 'clear active bit; keep slot; pointer remains at current sequence record',
            '0x10': 'set mask 8; keep slot; sequence pointer advances but frozen check stops further updates',
            '0x20': 'reset slot/timer; sequence pointer advances; next update can read sentinel duration',
            '0x30': 'call actual 62798 group-zero helper; reset group/slot/timer; do not advance pointer'},
        'counter_bound': 'LDRB at 632E6 gives a byte domain; probes do not prove the producer domain',
        'local_parameters': {'pool_calls': 47, 'group0': 45, 'group1': 2,
                             'flags_and_callback_both_known': 12, 'flags_or_callback_open': 35,
                             'known_nonzero_callbacks': [0x0808AA51, 0x0808EE41]},
        'open_obligations': ['Complete predecessor flags/callback domains across allocator call boundaries',
                             'Full raw interwork dispatch and callback effects including aliases/callees',
                             'External object pointer/group/slot/timer writers and handle lifetime',
                             'Independent frozen consumer/exporter/verifier and fail-closed publication',
                             'Mixed pool text/copy records require their own grammar contracts'],
        'promotion_bytes': 0,
    }
    Path(output).write_text(json.dumps(payload, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    with Path(sys.argv[2]).open('x') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            main(sys.argv[1])
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
