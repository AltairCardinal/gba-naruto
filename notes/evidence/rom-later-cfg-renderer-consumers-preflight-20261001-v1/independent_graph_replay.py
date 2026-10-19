"""Rewalk using Capstone PC targets, not the builder's raw branch helper."""
import hashlib
import json
from pathlib import Path
from tools._vendor.capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, arm_const as A

run = Path(__file__).resolve().parent
report = json.loads((run / 'inspection-v3.json').read_text())
rom = Path('rom/base.gba').read_bytes()
assert hashlib.sha256(rom).hexdigest() == report['rom_sha256']
engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
engine.detail = True
results = []
for handler in report['handlers']:
    lo, hi = handler['bounds']
    stops = set(handler['stops'])
    work, seen, edges, stores = [handler['root']], set(), set(), []
    def edge(source, target, kind):
        edges.add((source, target, kind))
        if target not in stops:
            assert lo <= target < hi
            work.append(target)
    while work:
        at = work.pop()
        if at in seen:
            continue
        seen.add(at)
        insn = next(engine.disasm(rom[at:at + 4], at, count=1))
        if insn.id == A.ARM_INS_BL:
            target = insn.operands[0].imm
            if lo <= target < hi:
                edge(at, target, 'internal_call_target')
            kind = 'conditional_context_resumption' if target == 0x9c574 else 'conditional_call_return'
            edge(at, at + insn.size, kind)
        elif insn.id == A.ARM_INS_B:
            kind = 'b' if insn.cc == A.ARM_CC_AL else 'bcond'
            edge(at, insn.operands[0].imm, kind)
            if kind == 'bcond':
                edge(at, at + insn.size, 'conditional_fallthrough')
        else:
            assert A.ARM_REG_PC not in insn.regs_access()[1]
            edge(at, at + insn.size, 'fallthrough')
        if insn.id == A.ARM_INS_STR and insn.operands[1].mem.base == A.ARM_REG_SP:
            register = int(insn.reg_name(insn.operands[0].reg)[1:])
            stores.append({'offset': at, 'source_register': register,
                           'sp_relative_offset': insn.operands[1].mem.disp})
    actual_edges = {(e['source'], e['target'], e['kind']) for e in handler['edges']}
    assert edges == actual_edges
    assert seen == {i['offset'] for i in handler['instructions']}
    assert sorted(stores, key=lambda x: x['offset']) == handler['direct_sp_word_stores']
    results.append({'label': handler['label'], 'instructions': len(seen), 'edges': len(edges),
                    'direct_sp_word_stores': len(stores), 'replayed': True})
print(json.dumps({'independent_pc_target_and_store_replay': results,
                  'callee_side_effects_or_context_resumption_proven': False,
                  'promotion_bytes': 0}, sort_keys=True, indent=2))
