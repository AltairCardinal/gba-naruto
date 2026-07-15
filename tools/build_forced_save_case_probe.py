#!/usr/bin/env python3
"""Enter postbattle UI and force its real 0xF400 save dispatch case."""
from __future__ import annotations
import argparse,hashlib,struct
from pathlib import Path
try:
 from tools.build_postbattle_natural_save_probe import build_probe as build_combined
except ModuleNotFoundError:
 from build_postbattle_natural_save_probe import build_probe as build_combined
try:
 from tools.build_save_state_runtime_probe import encode_thumb_bl
except ModuleNotFoundError:
 from build_save_state_runtime_probe import encode_thumb_bl

STATE_INIT=0x732F8
BEFORE=bytes.fromhex('80267601') # movs r6,#0x80; lsls r6,#5 => 0x1000
AFTER=bytes.fromhex('f4263602')  # movs r6,#0xF4; lsls r6,#8 => 0xF400
ROM_BASE=0x08000000; POSTBATTLE=0x080732B4
CALLERS=(0x08068DEC,0x08087328,0x0808F952)
GATE_STUB=0x0809E8C0; GATE_STUB_OFFSET=GATE_STUB-ROM_BASE
SAVE_UI_GATES=0x0200A880
POSTBATTLE_MODE_FLAG=0x03000075
SAVE_CASE_CALL=0x080735C2; SAVE_FUNCTION=0x08074EE6
CASE_STUB=0x0809E920; CASE_STUB_OFFSET=CASE_STUB-ROM_BASE
CASE_HIT=0x0203FF20
def build_probe(base:bytes)->bytes:
 out=bytearray(build_combined(base))
 if base[STATE_INIT:STATE_INIT+4]!=BEFORE:raise ValueError('postbattle state init mismatch')
 out[STATE_INIT:STATE_INIT+4]=AFTER
 for caller in CALLERS:
  off=caller-ROM_BASE
  if base[off:off+4]!=encode_thumb_bl(caller,POSTBATTLE):raise ValueError(f'postbattle caller mismatch {caller:08X}')
 if any(base[GATE_STUB_OFFSET:GATE_STUB_OFFSET+36]):raise ValueError('gate stub cave not zero')
 stub=struct.pack('<HHHHHHHH',0xB500,0x4B06,0x2200,0x701A,0x2201,0x709A,0x4B04,0x701A)
 stub+=encode_thumb_bl(GATE_STUB+16,POSTBATTLE)+struct.pack('<H',0xBD00)
 stub+=bytes(28-len(stub))+struct.pack('<II',SAVE_UI_GATES,POSTBATTLE_MODE_FLAG)
 out[GATE_STUB_OFFSET:GATE_STUB_OFFSET+36]=stub
 for caller in CALLERS:out[caller-ROM_BASE:caller-ROM_BASE+4]=encode_thumb_bl(caller,GATE_STUB)
 case_off=SAVE_CASE_CALL-ROM_BASE
 if base[case_off:case_off+4]!=encode_thumb_bl(SAVE_CASE_CALL,SAVE_FUNCTION):raise ValueError('save case call mismatch')
 if any(base[CASE_STUB_OFFSET:CASE_STUB_OFFSET+32]):raise ValueError('case stub cave not zero')
 case=struct.pack('<HHHHHHHH',0xB500,0x4B05,0x2200,0x701A,0x2201,0x709A,0x4B03,0x22A6)
 case+=struct.pack('<H',0x701A)+encode_thumb_bl(CASE_STUB+18,SAVE_FUNCTION)+struct.pack('<H',0xBD00)
 case+=bytes(24-len(case))+struct.pack('<II',SAVE_UI_GATES,CASE_HIT)
 out[CASE_STUB_OFFSET:CASE_STUB_OFFSET+32]=case
 out[case_off:case_off+4]=encode_thumb_bl(SAVE_CASE_CALL,CASE_STUB)
 return bytes(out)
def main():
 p=argparse.ArgumentParser();p.add_argument('base_rom',type=Path);p.add_argument('output_rom',type=Path);a=p.parse_args()
 out=build_probe(a.base_rom.read_bytes());a.output_rom.write_bytes(out);print(f'wrote {a.output_rom}: sha256={hashlib.sha256(out).hexdigest()}')
if __name__=='__main__':main()
