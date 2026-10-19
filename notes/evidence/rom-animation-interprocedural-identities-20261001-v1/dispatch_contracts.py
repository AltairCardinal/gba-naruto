"""Reuse the independently rebuilt frozen 10-slot v3 dispatcher, with dominance."""
from collections import deque
import copy
import json
from pathlib import Path
from tools.verify_rom_cfg_inventory import _decode
from tools.verify_rom_cfg_inventory_v3 import (
    _v2_artifact_contract, _resolve_thumb_indexed_dispatches_independently,
)
from callee_effects import local

_cached_dispatch=None

INPUTS={
 'artifacts/rom-cfg-inventory-v2/manifest.json':('ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753',None),
 'artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json':('b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd',5936694),
 'tools/verify_rom_cfg_inventory.py':('a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93',None),
 'artifacts/rom-cfg-inventory-v3/manifest.json':('6aa788611f73856e621f5c74aab544d47b034307a9dc1180f6fd8f81cb1f423b',4617),
 'artifacts/rom-cfg-inventory-v3/rom-cfg-inventory-v3.json':('596c4d8cffa57f3899858a0a59351894b1398006ee0405ce799ed9f32a81bf9d',1322391),
 'tools/verify_rom_cfg_inventory_v3.py':('46400e44866a93b571745f30779296cc5686889ac5d465891c648296d2dbe00a',41141),
}


def bind(rom,root,offsets,sites):
    global _cached_dispatch
    if set(sites)!={0x6dc72} or root not in offsets:
        raise ValueError('unsupported fixed dispatch selection')
    if local.sha(rom)!=local.ROM_SHA:
        raise ValueError('fixed dispatch ROM changed')
    for name,(digest,size) in INPUTS.items():
        raw=Path(name).read_bytes()
        if (size is not None and len(raw)!=size) or local.sha(raw)!=digest:raise ValueError('dispatch input identity changed')
    if _cached_dispatch is None:
        baseline,_=_v2_artifact_contract(Path.cwd(),rom)
        derived=_resolve_thumb_indexed_dispatches_independently(rom,baseline)
        payload=json.loads(Path('artifacts/rom-cfg-inventory-v3/rom-cfg-inventory-v3.json').read_text())
        public={k:v for k,v in derived.items() if k!='nonfixed_root_target_seeds'}
        if public!=payload['static_dispatches']:raise ValueError('independent dispatch replay differs')
        _cached_dispatch=copy.deepcopy(next(r for r in derived['dispatches'] if r['terminal_offset']==0x6dc72))
    row=copy.deepcopy(_cached_dispatch)
    targets={r['file_offset'] for r in row['targets']}
    if not targets <= offsets:raise ValueError('dispatch targets lack source membership')
    start,end=row['proof_range']
    at=start
    while at<end:
        if at not in offsets:raise ValueError('dispatch proof lacks source membership')
        i=_decode(rom,at,'thumb')
        if not i['accepted']:raise ValueError('dispatch proof partition changed')
        at+=i['size']
    # Remove the only inside edge of the proved unsigned guard. A terminal
    # reachable without that edge cannot inherit its finite index domain.
    guard=row['bound_branch']['file_offset'];inside=row['bound_branch']['target_offset']
    pending,seen=deque([root]),set()
    while pending:
        at=pending.popleft()
        if at in seen or at not in offsets:continue
        if at==row['terminal_offset']:raise ValueError('dispatch guard does not dominate terminal')
        seen.add(at)
        if len(seen)>32000:raise ValueError('dispatch dominance budget exhausted')
        i=_decode(rom,at,'thumb')
        if not i['accepted']:raise ValueError('unsupported dominance source')
        for e in i['successors']:
            if e['kind']=='call_target' or (at==guard and e['file_offset']==inside):continue
            pending.append(e['file_offset'])
    return {row['terminal_offset']:copy.deepcopy(row)}


def validate(rom,root,offsets,rows):
    if rows != bind(rom,root,offsets,set(rows)):
        raise ValueError('unverified dispatch vector')
    return rows
