"""Bounded noncall graph closure and cached dependency discovery; no ABI guesses."""
from collections import deque
from tools.verify_rom_cfg_inventory import _decode


def noncall_closure(rom,root,offsets,*,budget=32000,decoded=None):
    if root not in offsets:
        return {'nodes':[],'child_targets':[],'return_nodes':[],
                'frontiers':[{'kind':'missing_source_root','target':root}]}
    if type(budget) is not int or budget < 1:
        raise ValueError('invalid graph budget')
    pending,seen,children,returns,frontiers=deque([root]),set(),set(),set(),[]
    while pending:
        at=pending.popleft()
        if at in seen:continue
        if at not in offsets:
            frontiers.append({'kind':'source_boundary','target':at});continue
        seen.add(at)
        if len(seen)>budget:raise ValueError('noncall graph budget exhausted')
        i=decoded[at] if decoded is not None else _decode(rom,at,'thumb')
        if not i['accepted']:raise ValueError('unsupported source instruction')
        h=int.from_bytes(rom[at:at+2],'little')
        if h & 0xff00 == 0xdf00:
            frontiers.append({'kind':'external_svc','at':at,'number':h & 255});continue
        if h & 0xff87 == 0x4700 or h & 0xff00 == 0xbd00:
            returns.add(at);continue
        if i['flow_kind'] not in ('linear','call','conditional_branch','unconditional_branch'):
            frontiers.append({'kind':'opaque_control','at':at,'flow_kind':i['flow_kind']});continue
        for e in i['successors']:
            if e['kind']=='call_target':children.add(e['file_offset'])
            else:pending.append(e['file_offset'])
    return {'nodes':sorted(seen),'child_targets':sorted(children),'return_nodes':sorted(returns),
            'frontiers':sorted(frontiers,key=lambda f:(f.get('at',0),f.get('target',0),f['kind']))}


def discover(inspect,prove,initial,*,max_targets=128,max_rounds=64,progress=None):
    registry=dict(initial)
    attempts,rounds={},[]
    for n in range(max_rounds):
        frontiers=inspect(registry)
        needed=sorted({f['target'] for f in frontiers if f['kind'].startswith('unproved_callee')
                       and f['target'] not in registry and f['target'] not in attempts})
        if len(attempts)+len(needed)>max_targets:raise ValueError('target discovery budget exhausted')
        rounds.append({'round':n+1,'new_targets':needed,'frontiers':frontiers})
        if progress is not None:progress(n+1,needed)
        for target in needed:
            report=prove(target)
            attempts[target]=report
            if report['accepted']:registry[target]=report['summary']
        if not needed:
            return {'registry':registry,'attempts':attempts,'rounds':rounds,'round_count':n+1,
                    'fixed_dependency_frontier':True}
    raise ValueError('dependency round budget exhausted')
