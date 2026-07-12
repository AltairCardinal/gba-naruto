#!/usr/bin/env python3
"""Combine forced postbattle entry with the exact natural-caller observer."""
from __future__ import annotations
import argparse,hashlib
from pathlib import Path
try:
 from tools.build_postbattle_save_probe import build_probe as build_postbattle
 from tools.build_natural_save_runtime_probe import build_probe as build_observer
except ModuleNotFoundError:
 from build_postbattle_save_probe import build_probe as build_postbattle
 from build_natural_save_runtime_probe import build_probe as build_observer

def build_probe(base:bytes)->bytes:
    a=build_postbattle(base); b=build_observer(base); out=bytearray(base)
    changed_a={i for i,(x,y) in enumerate(zip(base,a)) if x!=y}
    changed_b={i for i,(x,y) in enumerate(zip(base,b)) if x!=y}
    if changed_a & changed_b: raise ValueError('diagnostic probe patches overlap')
    for i in changed_a: out[i]=a[i]
    for i in changed_b: out[i]=b[i]
    return bytes(out)
def main():
 p=argparse.ArgumentParser();p.add_argument('base_rom',type=Path);p.add_argument('output_rom',type=Path);x=p.parse_args()
 out=build_probe(x.base_rom.read_bytes());x.output_rom.write_bytes(out);print(f'wrote {x.output_rom}: sha256={hashlib.sha256(out).hexdigest()}')
if __name__=='__main__':main()
