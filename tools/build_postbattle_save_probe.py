#!/usr/bin/env python3
"""Enter the official post-battle UI once after battle-unit initialization."""
from __future__ import annotations

import argparse, hashlib, struct
from pathlib import Path
try:
    from tools.build_save_state_runtime_probe import encode_thumb_bl
except ModuleNotFoundError:
    from build_save_state_runtime_probe import encode_thumb_bl

BASE_SHA1="26f60795fa5e63b4f0264b84e453beffd56b9f7d"
ROM_BASE=0x08000000; HOOK=0x0806D5C6; ORIGINAL=0x0806D964
POSTBATTLE=0x08068DE4; STUB=0x0809E880; STUB_OFFSET=STUB-ROM_BASE
LATCH=0x0203FF30; SAVE_UI_GATES=0x0200A880; STUB_SIZE=48

def build_probe(base: bytes)->bytes:
    if hashlib.sha1(base).hexdigest()!=BASE_SHA1: raise ValueError('base ROM mismatch')
    rom=bytearray(base); off=HOOK-ROM_BASE
    if rom[off:off+4]!=encode_thumb_bl(HOOK,ORIGINAL): raise ValueError('hook mismatch')
    if any(rom[STUB_OFFSET:STUB_OFFSET+STUB_SIZE]): raise ValueError('stub cave not zero')
    # Preserve original return. Enter the official postbattle wrapper once.
    stub=struct.pack('<H',0xB510)+encode_thumb_bl(STUB+2,ORIGINAL)
    stub+=struct.pack('<HHHHHH',0x1C04,0x4907,0x780A,0x2A00,0xD108,0x2201)
    stub+=struct.pack('<HHHHH',0x700A,0x4B05,0x2200,0x701A,0x2201)
    stub+=struct.pack('<H',0x709A)+encode_thumb_bl(STUB+30,POSTBATTLE)
    stub+=struct.pack('<HH',0x1C20,0xBD10)
    stub+=bytes(40-len(stub))+struct.pack('<II',LATCH,SAVE_UI_GATES)
    if len(stub)!=STUB_SIZE: raise AssertionError(len(stub))
    rom[STUB_OFFSET:STUB_OFFSET+STUB_SIZE]=stub; rom[off:off+4]=encode_thumb_bl(HOOK,STUB)
    return bytes(rom)

def main():
    p=argparse.ArgumentParser();p.add_argument('base_rom',type=Path);p.add_argument('output_rom',type=Path);a=p.parse_args()
    out=build_probe(a.base_rom.read_bytes());a.output_rom.write_bytes(out)
    print(f'wrote {a.output_rom}: sha256={hashlib.sha256(out).hexdigest()}')
if __name__=='__main__':main()
