"""Permanent input composition for four independently verified CFG packets.

The pure builders and raw verifiers remain separate. This registry shares only
path selection and input I/O; it does not publish or accept artifacts.
"""
import gzip
import importlib
import json
from pathlib import Path

PACKETS = ('callback_gaps','wrappers','event_gaps','dispatcher')
CONTRACT_DIRECTORY = Path('tools/data/rom-small-cfg-dependency-v1')


def _module(root,key,role):
    if key not in PACKETS:
        raise ValueError('unknown frozen packet')
    name=f'tools.rom_small_cfg_{key}_{role}'
    module=importlib.import_module(name)
    if Path(module.__file__).absolute()!=Path(root).absolute()/'tools'/(name.split('.')[-1]+'.py'):
        raise ValueError('packet module belongs to a different repository')
    return module


def build_candidate(root,key):
    root=Path(root).absolute()
    producer=_module(root,key,'producer')
    # Reuse only the established no-follow input I/O, never semantic derivation.
    io=_module(root,'callback_gaps','independent_verifier')
    raw=io.read_regular(root/CONTRACT_DIRECTORY/(key+'.json'))
    contract=json.loads(raw)
    rom=io.read_pinned(root,contract['rom'])
    baseline=gzip.decompress(io.read_pinned(root,contract['baseline_archive']))
    if key in ('callback_gaps','event_gaps'):
        source=io.read_pinned(root,contract['source_payload'])
        return producer.build_payload(rom,source,baseline,raw)
    return producer.build_payload(rom,baseline,raw)


def verify_candidate(root,key,payload):
    root=Path(root).absolute()
    verifier=_module(root,key,'independent_verifier')
    return verifier.verify_candidate(root,root/CONTRACT_DIRECTORY/(key+'.json'),payload)
