"""One guarded source/ISA/state package with no canonical promotion."""
import ast
import contextlib
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path.cwd().resolve()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import counter_inventory
import lifecycle_probe as life
from advance_probe import probe
from tools.verify_rom_cfg_inventory import _decode, verify_rom_cfg_inventory
from tools.verify_rom_boot_thumb_handoff_cfg import verify_artifact as handoff_verify
from tools.verify_rom_boot_interwork_continuation import verify_artifact as continuation_verify
from tools.verify_rom_story_state_callback_cfg import verify_artifact as story_verify

PROGRESS = sys.stdout
OLD = ROOT / 'notes/evidence/rom-animation-pool-lifecycle-20261001-v1'
SOURCE_SPECS = (
    ('artifacts/rom-boot-thumb-handoff-cfg-v1', 'rom-boot-thumb-handoff-cfg.json', 'code_ranges', handoff_verify),
    ('artifacts/rom-boot-interwork-continuation-v1', 'rom-boot-interwork-continuation.json', 'promotion', continuation_verify),
    ('artifacts/rom-story-state-callback-cfg-v1', 'rom-story-state-callback-cfg.json', 'target_local_denominator', story_verify),
)
IMPLEMENTATIONS = ('bounded_thumb.py', 'lifecycle_probe.py', 'advance_probe.py', 'counter_inventory.py',
                   'batch.py', 'test_lifecycle.py', 'test_advance_probe.py', 'test_bounded_thumb.py')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def compact(trace):
    memory = trace['memory']
    return {'trace_sha256': sha(encode(trace)), 'instruction_count': len(trace['visited']),
            'unique_instruction_count': len(set(trace['visited'])),
            'write_count': len(trace['writes']), 'read_count': len(trace['reads']),
            'return_r0': trace['registers'][0], 'final_sp': trace['registers'][13],
            'stop': trace['stop'], 'ordinary_return': trace['ordinary_return'],
            'memory_sha256': sha(encode(memory))}


def freeze_inputs():
    names = {'rom/base.gba', 'sequel/rom-byte-coverage.json',
             'sequel/reverse-engineering-proof.json', 'sequel/bank-proofs.json'}
    for directory, _, _, _ in SOURCE_SPECS:
        names.update(p.relative_to(ROOT).as_posix() for p in (ROOT / directory).iterdir() if p.is_file())
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT / 'artifacts/rom-cfg-inventory-v2').iterdir() if p.is_file())
    # Bind the actual loaded verifier/helper/decoder modules, including vendor code.
    for module in list(sys.modules.values()):
        path = getattr(module, '__file__', None)
        if path:
            path = Path(path).resolve()
            if path.is_file() and path.is_relative_to(ROOT / 'tools') and '__pycache__' not in path.parts:
                names.add(path.relative_to(ROOT).as_posix())
    return {n: {'size': (ROOT / n).stat().st_size, 'sha256': sha((ROOT / n).read_bytes())} for n in sorted(names)}


def source_inventory(rom, original):
    nodes = set()
    for start, end in original['source_ranges']:
        at = start
        while at < end:
            item = _decode(rom, at, 'thumb')
            assert item['accepted'] and at + item['size'] <= end
            nodes.add(at)
            at += item['size']
    assert len(nodes) == 66295
    results = {'v2_lifecycle_source': verify_rom_cfg_inventory(ROOT, ROOT / 'artifacts/rom-cfg-inventory-v2')}
    assert results['v2_lifecycle_source']['verified'], results
    print('v2 lifecycle source verifier passed', file=PROGRESS, flush=True)
    groups = {}
    for directory, name, key, verify in SOURCE_SPECS:
        results[directory] = verify(ROOT, ROOT / directory)
        assert results[directory]['verified'], results[directory]
        print(directory, 'source verifier passed', file=PROGRESS, flush=True)
        payload = json.loads((ROOT / directory / name).read_text())
        ranges = payload[key] if key == 'code_ranges' else payload[key]['code_ranges']
        added = set()
        for start, end in ranges:
            at = start
            while at < end:
                item = _decode(rom, at, 'thumb')
                assert item['accepted'] and at + item['size'] <= end
                added.add(at)
                at += item['size']
        groups[directory] = {'instruction_count': len(added), 'net_new_in_union': len(added - nodes), 'code_ranges': ranges}
        nodes |= added
    refs = [dict(r, expanded_source_instruction_member=r['at'] in nodes)
            for r in original['all_halfword_ldr_literal_shapes'] if r['value'] == 0x03000075]
    assert len(refs) == 14 and sum(r['expanded_source_instruction_member'] for r in refs) == 12
    assert [r['at'] for r in refs if not r['expanded_source_instruction_member']] == [0x68DE6, 0x85880]
    return {'base_source_instruction_count': 66295, 'expanded_source_instruction_count': len(nodes),
            'source_groups': groups, 'fresh_verifiers': results, 'counter_75_literal_refs': refs,
            'counter_75_pointer_occurrences': [r for r in original['all_byte_pointer_occurrences'] if r['value'] == 0x03000075],
            'literal_denominator_is_not_all_writers': True, 'computed_base_irq_bios_alias_writers_exhausted': False,
            'candidate_refs_unpromoted': [0x68DE6, 0x85880], 'promotion_bytes': 0}


def run_cases(rom):
    rows = []
    def record(name, inputs, result):
        rows.append({'name': name, 'inputs': inputs, **compact(result)})
    init = life.initialize(rom, life.state())
    record('initialize_poison', {}, init)
    external = [w for w in init['writes'] if not life.SP - 64 <= w['address'] < life.SP]
    expected_addresses = [life.POOL + 60*n for n in range(128)] + [life.OTHER + 180*n for n in range(16)]
    assert [(w['address'],w['size'],w['value']) for w in external] == [(a,4,0) for a in expected_addresses]
    for alternate in (False, True):
        for free in range(128):
            memory = life.state()
            for n in range(128): life.put(memory, life.POOL+60*n,4,3)
            life.put(memory,life.POOL+60*free,4,0xA5000004)
            result=life.allocate(rom,memory,alternate=alternate)
            assert result['registers'][0] == life.POOL+60*free
            assert result['registers'][4:12] == life.registers()[4:12] and result['registers'][13] == life.SP
            record('alternate_allocate' if alternate else 'direct_allocate', {'only_free_slot':free}, result)
        memory=life.state()
        for n in range(128): life.put(memory,life.POOL+60*n,4,3)
        result=life.allocate(rom,memory,alternate=alternate)
        assert result['registers'][0] == 0
        assert not any(life.POOL <= w['address'] < life.POOL+128*60 for w in result['writes'])
        record('alternate_full' if alternate else 'direct_full',{},result)
    for pattern in ('inactive','active','mixed'):
        memory=life.state()
        flags=[0xA0000000 | (0 if pattern=='inactive' else 1 if pattern=='active' else n%4) for n in range(128)]
        for n,value in enumerate(flags): life.put(memory,life.POOL+60*n,4,value)
        result=life.filter_scan(rom,memory)
        active=[life.POOL+60*n for n,value in enumerate(flags) if value&1]
        assert life.get(result['memory'],0x03005BB8,1)==len(active)
        assert [life.get(result['memory'],0x030059B8+4*n,4) for n in range(len(active))]==active
        for n,value in enumerate(flags): assert life.get(result['memory'],life.POOL+60*n,4)==(value if value&1 else value&0xFFFFFFFD)
        record('filter_scan',{'pattern':pattern,'active_count':len(active)},result)
    memory=life.state()
    for n in range(128):life.put(memory,life.POOL+60*n,4,3)
    address=life.POOL+127*60;life.put(memory,address,4,0xA0000001)
    for stage in ('disable','reserved_allocate','filter_scan','reallocate'):
        if stage=='disable': result=life.disable(rom,memory,address)
        elif stage=='filter_scan': result=life.filter_scan(rom,memory)
        else: result=life.allocate(rom,memory)
        record('release_chain',{'stage':stage,'slot':127},result)
        memory=result['memory']
        if stage=='reserved_allocate':assert result['registers'][0]==0
        if stage=='reallocate':assert result['registers'][0]==address
    for saved in range(256):
        result=life.restore_counter(rom,guard=0x303,saved=saved,counter=173,argument=0)
        assert life.get(result['memory'],0x03000075,1)==(saved or 173)
        assert life.get(result['memory'],0x03005E2D,1)==0
        record('restore_saved_counter',{'saved':saved,'counter':173,'guard':0x303},result)
    for argument,count in ((0,59),(1,58),(1,59),(255,255)):
        result=life.restore_counter(rom,guard=0,saved=254,counter=173,argument=argument,wait=count)
        record('restore_wrong_guard',{'argument':argument,'wait':count},result)
    refusals=[]
    memory=life.state()
    for n in range(128):life.put(memory,life.POOL+60*n,4,3)
    life.put(memory,life.POOL+127*60,4,0)
    try: life.allocate(rom,memory,alternate=True,flags=0x400000)
    except ValueError as error:
        assert 'unexpected callee: 09c0dc' in str(error)
        refusals.append({'case':'alternate_bios_copy','error':str(error),'natural_bios_effects_proven':False})
    else: raise AssertionError('BIOS must fail closed')
    return rows,refusals


def main(output):
    output=Path(output)
    assert not output.exists()
    output.mkdir()
    for name in IMPLEMENTATIONS:
        raw=(HERE/name).read_bytes();ast.parse(raw)
        assert all(line==line.rstrip() for line in raw.decode().splitlines()),name
    suite=unittest.TestSuite()
    for name in ('test_lifecycle','test_advance_probe','test_bounded_thumb'):
        spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    tests=unittest.TextTestRunner(verbosity=2).run(suite)
    assert tests.wasSuccessful() and tests.testsRun==25
    print('25 unit/integration tests passed',file=PROGRESS,flush=True)
    rom=(ROOT/'rom/base.gba').read_bytes()
    assert sha(rom)=='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
    inputs=freeze_inputs()
    counter_inventory.main(output)
    assert (output/'counter-inventory.json').read_bytes()==(HERE/'counter-inventory.json').read_bytes()
    inventory=json.loads((output/'counter-inventory.json').read_text())
    sources=source_inventory(rom,inventory)
    (output/'source-additions.json').write_bytes(encode(sources))
    rows,refusals=run_cases(rom)
    print('object/restore bounded cases',len(rows),'BIOS refusals',len(refusals),file=PROGRESS,flush=True)
    validation=json.loads((OLD/'validation.json').read_text())
    original_spec=importlib.util.spec_from_file_location('original_advance',OLD/'advance_probe.py')
    original_module=importlib.util.module_from_spec(original_spec);original_spec.loader.exec_module(original_module)
    differential=[]
    for row in validation['probe_matrix']:
        arguments={'flags':row['flags'],'count':row['count'],'timer':row['initial_timer']}
        expected=original_module.probe(rom,row['sequence'],**arguments)
        assert sha(json.dumps(expected,sort_keys=True,separators=(',',':')).encode())==row['trace_sha256']
        actual=probe(rom,row['sequence'],**arguments)
        assert actual==expected
        differential.append({'sequence':row['sequence'],**arguments,'trace_sha256':row['trace_sha256']})
    assert len(differential)==672
    print('672 old advance traces exactly matched shared executor',file=PROGRESS,flush=True)
    assert inputs==freeze_inputs(),'live inputs changed during run'
    payload={'schema':'animation-object-lifecycle-v1','rom_sha256':sha(rom),
             'implementation_inputs':{n:sha((HERE/n).read_bytes()) for n in IMPLEMENTATIONS},
             'inputs':inputs,'source_report_sha256':sha(encode(sources)),
             'old_advance_manifest_sha256':sha((OLD/'manifest.json').read_bytes()),
             'old_advance_validation_sha256':sha((OLD/'validation.json').read_bytes()),
             'old_advance_implementation_sha256':sha((OLD/'advance_probe.py').read_bytes()),
             'unit_tests':25,'cases':rows,'refusals':refusals,'old_advance_differential':differential,
             'facts':{'initializer_flag_words':144,'initializer_other_fields_preserved':True,
                      'allocator_slot_count':128,'direct_and_simple_alternate_highest_free_slot_checked':True,
                      'disable_reserves_until_filter_clears_bit1':True,'active_scan_slots':128,
                      'active_scan_stop_before_sort':0x62816,'full_active_list_sort_verified':False,
                      'counter_restore_all_saved_u8_values_checked':True,'saved_zero_means_no_restore':True,
                      'counter_globally_binary_proven':False,'global_writers_exhausted':False,
                      'entry_pointer_domain_proven':False,'private_stack_disjointness_natural_proven':False,
                      'alternate_bios_copy_effects_proven':False},
             'natural_execution_proven':False,'runtime_launches':0,'promotion_bytes':0,
             'scope':'Artificial poisoned RAM states and frozen source code; limited executor. No natural lifetime, all writer, alias, BIOS, coroutine or full bank-domain proof.'}
    (output/'lifecycle.json').write_bytes(encode(payload))


if __name__=='__main__':
    with Path(sys.argv[2]).open('x') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:main(Path(sys.argv[1]))
        except BaseException:
            import traceback;traceback.print_exc();raise SystemExit(1)
