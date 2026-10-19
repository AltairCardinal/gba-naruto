"""Bounded route and consumption preflight; no semantic claims or publication."""
import hashlib
import json
import struct
from pathlib import Path
from collections import Counter
from tools._vendor.capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from tools.export_rom_fixed_consumer_text_inventory import _renderer_record_end, _sjis_ranges
from tools.verify_rom_fixed_consumer_text_inventory import _independent_renderer_end, _independent_sjis_ranges

root = Path('.')
for relative, expected in json.loads(Path(__file__).with_name('inputs.json').read_text()).items():
    assert hashlib.sha256(Path(relative).read_bytes()).hexdigest() == expected, relative
screen_path = Path('notes/evidence/reverse-work-plan-20261001-v1/late-cfg-screen.json')
screen = json.loads(screen_path.read_text())
rom = Path('rom/base.gba').read_bytes()
assert hashlib.sha256(rom).hexdigest() == '1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
coverage_raw = Path('sequel/rom-byte-coverage.json').read_bytes()
assert hashlib.sha256(coverage_raw).hexdigest() == 'b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
coverage = json.loads(coverage_raw)
unknown = [s['range'] for s in coverage['segments'] if s['primary_class'] == 'unknown']
engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
engine.detail = True
rows = []
windows = {}

def raw_bl(at):
    a, b = struct.unpack_from('<HH', rom, at)
    assert a & 0xf800 == 0xf000 and b & 0xf800 == 0xf800
    displacement = ((a & 0x7ff) << 12) | ((b & 0x7ff) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return at + 4 + displacement

for item in screen['unknown_literal_consumers']:
    if not 0x463914 <= item['target'] <= 0x463b18:
        continue
    at = item['site']
    half = int.from_bytes(rom[at:at+2], 'little')
    assert half & 0xf800 == 0x4800
    register = f'r{(half >> 8) & 7}'
    literal = ((at + 4) & ~3) + (half & 255) * 4
    assert literal == item['literal_word']
    assert int.from_bytes(rom[literal:literal+4], 'little') - 0x08000000 == item['target']
    hi = min(at + 44, item['owner_range'][1])
    trace = []
    call = None
    unchanged = True
    for insn in engine.disasm(rom[at:hi], at):
        trace.append({'at': insn.address, 'bytes': insn.bytes.hex(), 'mnemonic': insn.mnemonic, 'operands': insn.op_str})
        if insn.mnemonic == 'bl':
            call = {'at': insn.address, 'target': raw_bl(insn.address)}
            assert call['target'] == int(insn.op_str[1:], 16)
            break
        if insn.address != at:
            if register in [insn.reg_name(r) for r in insn.regs_access()[1]]:
                unchanged = False
            if insn.mnemonic.startswith('b') or insn.mnemonic in ('pop', 'svc'):
                unchanged = False
    assert call is not None
    row = dict(item, first_call=call, literal_register=register,
               no_register_write_before_first_call=unchanged, trace=trace)
    target = item['target']
    route = call['target']
    if unchanged and register == 'r0' and route in (0x66758, 0x667a0, 0x90a20):
        end = _renderer_record_end(rom, target, min(target + 512, len(rom)), _sjis_ranges(rom))
        assert end == _independent_renderer_end(rom, target, min(target+512, len(rom)), _independent_sjis_ranges(rom))
        row.update(hypothetical_read_range=[target, end], assumption='Renderer bridge contract and all required source/ABI proofs must be accepted separately.')
    elif unchanged and register == 'r1' and route == 0x9c3ec:
        assert trace[-2]['bytes'] == '0322'
        row.update(hypothetical_read_range=[target, target+3], assumption='Fixed length 3 byte-copy callee CFG contract required; not a whole text record.')
    elif unchanged and register == 'r1' and route == 0x66efc:
        cursor, count = target, 2
        reads = []
        while True:
            reads.append(cursor)
            byte = rom[cursor]
            if byte == 0:
                reason = 'source_nul'
                break
            if byte == 1:
                cursor += 1
                reads.append(cursor)
                count = (count + 1) & 255
            cursor += 1
            count = (count + 1) & 255
            if count > 0x23:
                reason = 'output_count_limit'
                break
        row.update(hypothetical_read_range=[target, max(reads)+1], source_reads=sorted(set(reads)),
                   stop_reason=reason, assumption='Only a local-loop simulation; independent raw CFG/parser proof and source contracts still required.')
    if 'hypothetical_read_range' in row:
        lo, hi = row['hypothetical_read_range']
        row['immutable_unknown_bytes'] = sum(max(0, min(hi,b)-max(lo,a)) for a,b in unknown)
        row['read_bytes_sha256'] = hashlib.sha256(rom[lo:hi]).hexdigest()
    rows.append(row)

for lo, hi in [(0x66758,0x66790),(0x667a0,0x667ca),(0x90a20,0x90a8e),(0x66efc,0x66ffc),(0x9c3ec,0x9c44a)]:
    windows[f'{lo:06x}-{hi:06x}'] = {'raw_hex': rom[lo:hi].hex(), 'sha256': hashlib.sha256(rom[lo:hi]).hexdigest()}
inputs = {}
for p in [screen_path, Path('sequel/rom-byte-coverage.json'), Path('tools/export_rom_fixed_consumer_text_inventory.py'), Path('tools/verify_rom_fixed_consumer_text_inventory.py')]:
    inputs[p.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
ranges = sorted(r['hypothetical_read_range'] for r in rows if 'hypothetical_read_range' in r)
assert all(a[1] <= b[0] for a,b in zip(ranges,ranges[1:]))
print(json.dumps({'schema':'fixed-text-route-preflight-v1','inputs':inputs,'rows':rows,'callee_windows':windows,
                  'first_call_counts':{f'{k:06x}':v for k,v in sorted(Counter(r['first_call']['target'] for r in rows).items())},
                  'hypothetical_read_bytes':sum(b-a for a,b in ranges),
                  'hypothetical_unknown_bytes':sum(r.get('immutable_unknown_bytes',0) for r in rows),
                  'source_semantic_verifiers_rerun':False,'promotion_bytes':0,
                  'limitations':['Bounded literal-to-first-call windows only; Capstone write analysis is not an independent taint verifier.', 'Wrapper and byte-copy consumption contracts are pending; no natural execution, editable text or whole-cluster claim.']},sort_keys=True,indent=2))
