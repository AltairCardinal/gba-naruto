"""One joint frozen source/provider/native-case batch; no canonical promotion."""
import ast
import contextlib
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = Path.cwd().resolve()
sys.path[:0] = [str(HERE),str(ROOT)]
import arm_probe as p
from tools.verify_rom_boot_copy_sources import verify_artifact as verify_copies
from tools.verify_rom_boot_interwork import verify_artifact as verify_context
from tools.verify_rom_boot_framebuffers import analyze_arm_startup_chain


def encode(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main(output):
    output = Path(output)
    if output.exists():
        raise ValueError('fresh output required')
    output.mkdir()
    inputs = {}
    def read(path, expected=None):
        path = Path(path)
        full = path if path.is_absolute() else ROOT/path
        raw = full.read_bytes()
        if expected and sha(raw) != expected:
            raise ValueError(f'input identity {path}')
        inputs[str(path)] = {'size':len(raw),'sha256':sha(raw)}
        return raw
    parent = Path('notes/evidence/rom-animation-save-source-20261001-v1')
    manifest = json.loads(read(parent/'manifest.json','965e91b1843c02eb9d105a84f3f18ee5683b7076bcd45f3f7a635082b44b84da'))
    for name,identity in manifest['files'].items():
        assert len(read(parent/name,identity['sha256'])) == identity['size']
    saved = json.loads(read(parent/'save-source.json'))
    for name,identity in saved['inputs'].items():
        assert len(read(name,identity['sha256'])) == identity['size']
    for folder in ('rom-boot-copy-sources-v1','rom-boot-interwork-v1','rom-boot-thumb-handoff-cfg-v1','rom-cfg-proven-roots-v12'):
        for path in sorted((ROOT/'artifacts'/folder).rglob('*')):
            if path.is_file():
                read(path.relative_to(ROOT))
    provider = json.loads((HERE/'provider-contract.json').read_text())
    for name,identity in provider['files'].items():
        assert len(read(name,identity['sha256'])) == identity['size']
    assert sha((HERE/'mgba-arm-probe').read_bytes()) == provider['native_binary_sha256']
    for name in ('arm_probe.py','batch.py','test_arm_probe.py'):
        raw=(HERE/name).read_bytes()
        ast.parse(raw)
        assert all(line==line.rstrip() for line in raw.decode().splitlines())
    import test_arm_probe
    tests=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_arm_probe))
    assert tests.wasSuccessful() and tests.testsRun==12
    print('CHECK fixed copy, context and IRQ raw sources',flush=True)
    source_checks = {'copy_sources':verify_copies(ROOT,ROOT/'artifacts/rom-boot-copy-sources-v1'),
                     'context_root':verify_context(ROOT,ROOT/'artifacts/rom-boot-interwork-v1'),
                     'irq_raw_chain':analyze_arm_startup_chain(p.ROM.read_bytes())}
    assert source_checks['copy_sources']['verified'] and source_checks['context_root']['verified']
    assert source_checks['irq_raw_chain']['irq_callback']['range'] == [0x104,0x244]
    cases=[]
    rawfile=(output/'native-traces.jsonl.gz').open('xb')
    archive=gzip.GzipFile(filename='',mode='wb',fileobj=rawfile,mtime=0)
    def record(family,params,fixture,row):
        payload={'family':family,'parameters':params,'input':fixture,'trace':row}
        raw=encode(payload)
        archive.write(raw)
        cases.append({'family':family,'parameters':params,'input_sha256':sha(encode(fixture)),
                      'full_record_sha256':sha(raw),'instructions':len(row['visited']),'write_calls':len(row['writes'])})
    keys=set()
    for root in (0x638,0x690):
        active_set=(False,) if root==0x638 else (False,True)
        banks=(0,1,204,205,255) if root==0x638 else (0,1,255)
        for ram in (False,True):
            for active in active_set:
                keys.update((root,ram,line,bank,active) for line in range(160) for bank in banks)
                keys.update((root,ram,line,bank,active) for line in (0,159,160,65535) for bank in range(256))
    ordered=sorted(keys)
    fixtures=[p.raster_fixture(*key) for key in ordered]
    print(f'RUN {len(fixtures)} raster cases',flush=True)
    rows=p.execute(fixtures)
    paired={}
    for key,fixture,row in zip(ordered,fixtures,rows,strict=True):
        root,ram,line,bank,active=key
        delta=fixture['root']-root
        normalized={'visited':[a-delta for a in row['visited']],
                    'writes':[[w[0]-delta,*w[1:]] for w in row['writes']],
                    'registers':row['registers'],'cpsr':row['cpsr'],'spsr':row['spsr'],'peek':row['peek']}
        pairkey=(root,line,bank,active)
        if ram:
            assert paired[pairkey]==normalized,(key,'relocation mismatch')
        else:
            paired[pairkey]=normalized
        record('raster',list(key),fixture,row)
    print('RUN finite context and IRQ domains',flush=True)
    contexts={(2,wait,0) for wait in range(256)}
    contexts.update((slot,wait,variant) for slot in range(1,7) for wait in (0,1,2,255) for variant in (0,1))
    for slot,wait,variant in sorted(contexts):
        saved,resumed=p.context_pair(slot,wait,variant=variant)
        for family,row in (('context-save',saved),('context-resume',resumed)):
            fixture=row.pop('input')
            record(family,[slot,wait,variant],fixture,row)
    for root,active in ((0x638,False),(0x690,False),(0x690,True)):
        for ram in (False,True):
            for line in (0,159,160,65535):
                for bank in (0,255):
                    row=p.irq_case(root,line,bank,active,relocated_irq=ram)
                    fixture=row.pop('input')
                    record('irq-dispatch',[root,active,ram,line,bank],fixture,row)
    for source,_,_ in p.COPIES:
        row=p.cpuset_case(source)
        fixture=row.pop('input')
        record('cpuset-embedded-bios',[source],fixture,row)
    archive.close()
    rawfile.close()
    for module in list(sys.modules.values()):
        path=getattr(module,'__file__',None)
        if path:
            path=Path(path).resolve()
            if path.is_relative_to(ROOT/'tools') and path.is_file():
                read(path.relative_to(ROOT))
    for name,identity in inputs.items():
        full=Path(name) if Path(name).is_absolute() else ROOT/name
        assert len(full.read_bytes())==identity['size'] and sha(full.read_bytes())==identity['sha256'],name
    result={'schema':'rom-animation-irq-arm-native-v1','rom_sha256':p.ROM_SHA,'inputs':inputs,
            'provider':provider,'source_checks':source_checks,'copies':p.COPIES,'tests':12,'cases':cases,
            'trace_archive':{'sha256':sha((output/'native-traces.jsonl.gz').read_bytes()),'size':(output/'native-traces.jsonl.gz').stat().st_size},
            'facts':{'register_restore_r1_r2_crossed':True,'wait_one_stays_one_on_select':True,'wait_zero_wraps_to_255_and_skips':True,
                     'callback_destinations_are_fixed_io':True,'snapshot_roundtrip_verified':True,'same_register_context_identity_proven':False,
                     'natural_execution_proven':False,'hardware_bios_semantics_proven':False,'full_writer_domain_closed':False,
                     'all_cross_products_exhausted':False,'promotion_bytes':0,'formal_rerun':False}}
    (output/'irq-arm-native.json').write_bytes(encode(result))
    print(f'PASSED {len(cases)} native cases, 12 tests, 2 artifact verifiers, 1 raw IRQ source check',flush=True)


if __name__=='__main__':
    with Path(sys.argv[2]).open('x') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        try:
            main(Path(sys.argv[1]))
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
