"""Fixed initializer and local registration arithmetic; no global lifecycle claim."""
import hashlib
import json
import struct
from pathlib import Path
from tools.analyze_rom_ai_entry_domains import read_coverage
from tools._vendor.capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

root = Path('.')
rom = (root / 'rom/base.gba').read_bytes()
assert hashlib.sha256(rom).hexdigest() == '1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
coverage = read_coverage(root)
points = [0x61d16,0x61d1c,0x61d1e,0x61d30,0x61d34,0x61d36,0x61d38,
          0x61d3c,0x61d40,0x61d46,0x61d48,0x61d52,0x61d54,0x61d56,
          0x61d98,0x61d9e,0x61da8,0x61daa,0x61dac,0x61dae,0x61db0,
          0x61db2,0x61db6,0x61db8,0x61dc0,0x61dc2,0x61dc6,0x61dd4,
          0x61dd6,0x61dda,0x61ddc,0x61de2,0x61e04,0x61e06,0x61e12,0x61e18,
          0x7c5ea,0x7c5ee,0x7c5f0,0x7c60c,0x7c60e,0x7c610,0x7c61c]
engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
rows = []
for at in points:
    insn = next(engine.disasm(rom[at:at+4], 0x08000000+at, count=1))
    owners = [row for row in coverage['claims'] if row['role']=='primary'
              and row['range'][0]<=at and at+insn.size<=row['range'][1]]
    assert len(owners)==1 and 'reachable_instruction_bytes' in owners[0]['claim_kind']
    rows.append({'offset':at,'bytes':rom[at:at+insn.size].hex(),'mnemonic':insn.mnemonic,
                 'operands':insn.op_str,'owner':owners[0]['id']})

def literal(at, expected):
    half = struct.unpack_from('<H', rom, at)[0]
    assert half & 0xf800 == 0x4800
    word_offset = ((at+4)&~3)+(half&255)*4
    value = struct.unpack_from('<I', rom, word_offset)[0]
    assert value == expected
    return {'instruction':at,'literal':word_offset,'value':value}

bindings = [literal(0x61d1c,0x03000a88),literal(0x61d98,0x03000a88),
            literal(0x61db2,0x03000d1c),literal(0x61db8,0x03000ce8),
            literal(0x61dc2,0x03000d00),literal(0x61dd4,0x0853d5f0),
            literal(0x61e04,0x03000a88)]
assert rom[0x61d16:0x61d18].hex()=='0022'
assert rom[0x61d1e:0x61d20].hex()=='4c20'
assert rom[0x61d34:0x61d36].hex()=='0132'
assert rom[0x61d46:0x61d4a].hex()=='072af1d9'
assert struct.unpack_from('<I',rom,0x53d5f0)[0]==0xffffffff
pool, stride = 0x03000a88, 0x4c
records = [{'slot':i,'record_base':pool+i*stride,'initial_tag':i+1,
            'initial_wait_byte':1,'initial_sp':0xffffffff,'initial_pc':0xffffffff}
           for i in range(8)]
# Registrar's r0 index is u8. The five-root wrapper has no domain guard; this
# expression requires unchanged r4 across 7FE2C, an unclosed callee obligation.
local_slots = sorted({((value & 255)+2)&255 for value in range(256)})
assert local_slots == list(range(256))
stack_tops = [{'slot':i,'declared_initial_sp':0x03000d1c+i*0x580} for i in range(1,7)]
alias = {'hypothetical_slot':8,'record_base':pool+8*stride,
         'callback_array_base':0x03000ce8,'saved_sp_store_address':pool+8*stride+4,
         'callback_array_slot2_address':0x03000ce8+4,
         'natural_slot8_registration_proven':False}
assert alias['record_base']==alias['callback_array_base']
assert alias['saved_sp_store_address']==alias['callback_array_slot2_address']
inputs = {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in [
    'tools/analyze_rom_ai_entry_domains.py','tools/_vendor/capstone/__init__.py']}
print(json.dumps({'schema':'coroutine-fixed-record-shapes-preflight-v1',
                  'rom_sha256':hashlib.sha256(rom).hexdigest(),
                  'coverage_sha256':'b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2',
                  'helper_inputs_observed':inputs,'points':rows,'literal_bindings':bindings,
                  'fixed_initializer_records':records,'pool_end':pool+8*stride,
                  'sentinel_tag8_record_slot':7,'slot_zero_resume_table_value':0xffffffff,
                  'slot_zero_callback_argument_not_stored_on_zero_branch':True,
                  'declared_registration_initial_stack_tops':stack_tops,
                  'unrestricted_u8_plus2_mod256_domain':local_slots,
                  'unchanged_r4_across_callee_proven':False,'alias_arithmetic':alias,
                  'all_task_writers_and_resume_lifecycle_closed':False,
                  'global_slot_domain_proven':False,'promotion_bytes':0},sort_keys=True,indent=2))
