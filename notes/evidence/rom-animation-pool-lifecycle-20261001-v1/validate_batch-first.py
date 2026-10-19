"""Fresh independent source replay plus a finite artificial-state probe matrix."""
import contextlib
import hashlib
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))
from advance_probe import probe
from analysis import sha

HERE = Path(__file__).parent
ROOT = Path.cwd()
SOURCES = {
    'artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json':
        ('tools.verify_rom_cfg_inventory', 'verify_rom_cfg_inventory'),
    'artifacts/rom-cfg-inventory-v3/rom-cfg-inventory-v3.json':
        ('tools.verify_rom_cfg_inventory_v3', 'verify_rom_cfg_inventory_v3'),
    'artifacts/rom-battle-controller-cfg-v1/rom-battle-controller-cfg.json':
        ('tools.verify_rom_battle_controller_cfg', 'verify_rom_battle_controller_cfg'),
    'artifacts/rom-story-callback-dependency-closures-v1/rom-story-callback-dependency-closures.json':
        ('tools.verify_rom_story_callback_dependency_closures', 'verify_artifact'),
    'artifacts/rom-prebattle-menu-controller-cfg-v1/rom-prebattle-menu-controller-cfg.json':
        ('tools.verify_rom_prebattle_menu_controller_cfg', 'verify_artifact'),
    'artifacts/rom-text-bg-task-closure-v1/rom-text-bg-task-closure.json':
        ('tools.verify_rom_text_bg_task_closure', 'verify_artifact'),
    'artifacts/rom-cfg-proven-roots-v6/rom-cfg-proven-roots-v6.json':
        ('tools.verify_rom_cfg_proven_roots_v6', 'verify_rom_cfg_proven_roots_v6'),
    'artifacts/rom-cfg-proven-roots-v17/rom-cfg-proven-roots-v17.json':
        ('tools.verify_rom_cfg_proven_roots_v17', 'verify_root'),
    'artifacts/rom-v17-v18-helper-cfg-v1/rom-v17-v18-helper-cfg.json':
        ('tools.verify_rom_v17_v18_helper_cfg', 'verify_artifact'),
}


def main():
    raw = (HERE / 'audit-final.json').read_bytes()
    audit = json.loads(raw)
    rom = (ROOT / 'rom/base.gba').read_bytes()
    reports = {}
    paths = sorted({r['owner']['evidence_path'] for r in audit['rows']
                    if r.get('source_instruction_membership_checked')})
    assert set(paths) == set(SOURCES)
    for path in paths:
        module, function = SOURCES[path]
        report = getattr(importlib.import_module(module), function)(ROOT, ROOT / Path(path).parent)
        reports[path] = report
        (HERE / 'source-reports.json').write_text(json.dumps(reports, indent=2, sort_keys=True) + '\n')
        assert report['verified'] and not report.get('errors'), (path, report)
    matrix = []
    examples = []
    for pair in audit['pair_rows']:
        sequence = pair['group0_sequence_range'][0]
        assert rom[sequence:sequence + 8] == bytes.fromhex('00000100ffff0000')
        for mode in range(0, 0x40, 8):
            for count in (0, 1, 2, 255):
                for timer in (0, 65534, 65535):
                    flags = mode | 1
                    result = probe(rom, sequence, flags=flags, count=count, timer=timer)
                    assert result['slot'] == 0 and result['group'] == 0
                    trace_raw = json.dumps(result, sort_keys=True, separators=(',', ':')).encode()
                    matrix.append({'sequence': sequence, 'flags': flags, 'count': count,
                                   'initial_timer': timer, 'slot': result['slot'],
                                   'final_timer': result['timer'], 'final_flags': result['flags'],
                                   'unique_sequence_reads': sorted({tuple(r) for r in result['sequence_reads']}),
                                   'trace_sha256': sha(trace_raw), 'instruction_count': len(result['visited'])})
                    if mode == 0x20 and count == 2 and timer == 0:
                        examples.append({'sequence': sequence, 'flags': flags, 'count': count,
                                         'initial_timer': timer, 'trace': result})
    # Mutation demonstrates that suffix is not innocuous under loop mode.
    sequence = audit['pair_rows'][0]['group0_sequence_range'][0]
    modified = bytearray(rom)
    modified[sequence + 6:sequence + 8] = b'\x01\x00'
    suffix_negative = None
    try:
        probe(bytes(modified), sequence, flags=0x21, count=2)
    except ValueError as error:
        suffix_negative = str(error)
    assert suffix_negative == 'sequence read passed the frozen suffix boundary'
    output = {'schema': 'animation-pool-lifecycle-batch-validation-v1',
              'audit_sha256': sha(raw), 'rom_sha256': sha(rom),
              'source_reports': reports, 'source_count': len(paths),
              'instruction_members_checked': audit['summary']['instruction_members'],
              'finite_probe_count': len(matrix), 'probe_matrix': matrix, 'examples': examples,
              'suffix_mutation_failure': suffix_negative,
              'scope': 'Finite artificial probes only, not exhaustive timer/high-flags coverage; '
                       'no external writers or callback execution. Source CFG replay verifies '
                       'instruction membership, not caller predecessor domains or natural reachability.',
              'promotion_bytes': 0}
    (HERE / 'validation.json').write_text(json.dumps(output, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    with (HERE / 'validation.log').open('x') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        main()
