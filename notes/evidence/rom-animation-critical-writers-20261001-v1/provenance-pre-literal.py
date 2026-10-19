"""Fixed-source pointer provenance, not exhaustive alias or natural-domain proof."""
from collections import deque
import copy
import struct
from callee_effects import local,register
from flow import validate_callees
from tools.verify_rom_cfg_inventory import _decode

CRITICAL=((0,4),(0x14,0x1a),(0x1c,0x24),(0x28,0x2c))
POOL=(0x03003bb8,0x030059b8)


def plus(value,delta):
    if isinstance(value,int) and isinstance(delta,int):return (value+delta)&0xffffffff
    if isinstance(value,tuple) and value[0] in ('object','sp') and isinstance(delta,int):
        if -4096<=value[1]+delta<=4096:return (value[0],value[1]+delta)
    return None


def meet(a,b):
    return {k:{r:v for r,v in a[k].items() if b[k].get(r)==v} for k in ('regs','memory')}


def address(inst,regs):
    if len(inst.operands)!=2:return None
    m=inst.operands[1].mem
    base=regs.get(register(inst.reg_name(m.base)))
    index=regs.get(register(inst.reg_name(m.index))) if m.index else 0
    if not isinstance(index,int):return None
    return plus(base,m.disp+index)


def event(at,inst,addr,value):
    width=1 if inst.mnemonic.endswith('b') else 2 if inst.mnemonic.endswith('h') else 4
    obj=isinstance(addr,tuple) and addr[0]=='object'
    critical=obj and any(addr[1]<b and a<addr[1]+width for a,b in CRITICAL)
    alias=True if not isinstance(addr,int) else addr<POOL[1] and POOL[0]<addr+width
    return {'at':at,'raw_hex':inst.bytes.hex(),'mnemonic':inst.mnemonic,'operands':inst.op_str,
            'width':width,'address':list(addr) if isinstance(addr,tuple) else addr,
            'source_value':list(value) if isinstance(value,tuple) else value,
            'critical_field_overlap':critical,'may_alias_pool':alias}


def audit(rom,root,offsets,initial,*,callees=None,budget=32000,stop_sites=()):
    if root not in offsets or type(budget) is not int or budget<1:raise ValueError('invalid fixed-source inputs')
    callees=validate_callees(rom,offsets,callees or {})
    stops=set(stop_sites)
    if not stops<=offsets:raise ValueError('stop sites lack source membership')
    initial=dict(initial);initial[13]=('sp',0)
    states={root:{'regs':initial,'memory':{}}};pending=deque([root]);queued={root};decoded={};updates=0

    def instruction(at):
        if at not in offsets:raise ValueError('noncall edge escaped source membership')
        if at not in decoded:
            d=_decode(rom,at,'thumb')
            if not d['accepted'] or (d['size']==4 and at+2 in offsets):raise ValueError('invalid source partition')
            inst=next(local.ENGINE.disasm(rom[at:at+d['size']],at,count=1))
            decoded[at]=(d,inst)
        return decoded[at]

    def step(at,state):
        d,i=instruction(at);h=struct.unpack_from('<H',rom,at)[0]
        state=copy.deepcopy(state);old=dict(state['regs']);memory=state['memory'];out=state['regs']
        stores,reads,calls,frontiers=[],[],[],[]
        if at in stops:return state,[],stores,reads,calls,[{'at':at,'kind':'explicit_iteration_boundary'}]
        if h&0xff00==0xdf00:return state,[],stores,reads,calls,[{'at':at,'kind':'external_svc','number':h&255}]
        if d['flow_kind']=='call':
            target=next(e['file_offset'] for e in d['successors'] if e['kind']=='call_target')
            proof=callees.get(target)
            preserved=set(proof['preserved_registers'])&set(range(4,12)) if proof else set()
            calls.append({'at':at,'target':target,'args':{r:list(v) if isinstance(v,tuple) else v for r,v in old.items() if r<4},
                          'preservation_bound':proof is not None,'preserved_registers':sorted(preserved),
                          'conditional_context_resumption':True,'alias_effects_proven':False})
            state['regs']={r:v for r,v in old.items() if r in preserved or r==13};state['memory']={}
            routes=[e['file_offset'] for e in d['successors'] if e['kind']=='fallthrough']
            return state,routes,stores,reads,calls,frontiers
        if h==0x46f7 or h&0xff87==0x4700 or h&0xff00==0xbd00:
            return state,[],stores,reads,calls,[{'at':at,'kind':'return_or_indirect_boundary','structured_return_proven':False}]
        if d['flow_kind'] in ('conditional_branch','unconditional_branch'):
            return state,[e['file_offset'] for e in d['successors']],stores,reads,calls,frontiers
        if d['flow_kind']!='linear':raise ValueError('unhandled raw control')
        if h&0xfe00==0xb400:
            regs=[r for r in range(8) if h&(1<<r)]+([14] if h&0x100 else [])
            sp=plus(old.get(13),-4*len(regs))
            if sp is None:raise ValueError('unbounded SP')
            out[13]=sp
            for n,r in enumerate(regs):
                key=sp[1]+4*n;memory.pop(key,None)
                if r in old:memory[key]=old[r]
        elif h&0xfe00==0xbc00:
            regs=[r for r in range(8) if h&(1<<r)]
            sp=old.get(13)
            if not isinstance(sp,tuple) or sp[0]!='sp':raise ValueError('dynamic SP')
            for n,r in enumerate(regs):
                key=sp[1]+4*n;out.pop(r,None)
                if key in memory:out[r]=memory[key]
                memory.pop(key,None)
            out[13]=plus(sp,4*len(regs))
        elif h&0xff00==0xb000:
            out[13]=plus(old.get(13),(h&127)*4*(-1 if h&128 else 1))
            if out[13] is None:raise ValueError('unbounded SP')
        else:
            writes={register(i.reg_name(r)) for r in i.regs_access()[1]}-{None}
            if 13 in writes or 15 in writes:raise ValueError('dynamic SP/PC')
            for r in writes:out.pop(r,None)
            group=h&0xf800
            addr=None
            if i.mnemonic in ('str','strh','strb','ldr','ldrh','ldrb','ldrsh','ldrsb') and len(i.operands)==2:
                addr=address(i,old)
            if i.mnemonic in ('str','strh','strb'):
                source=old.get(register(i.reg_name(i.operands[0].reg)))
                stores.append(event(at,i,addr,source))
                if isinstance(addr,tuple) and addr[0]=='sp':
                    width=stores[-1]['width']
                    for key in list(memory):
                        if key<addr[1]+width and addr[1]<key+4:del memory[key]
                    if width==4 and addr[1]%4==0 and source is not None:memory[addr[1]]=source
                else:memory.clear()
            elif i.mnemonic in ('stm','stmia'):
                stores.append({'at':at,'raw_hex':i.bytes.hex(),'mnemonic':i.mnemonic,'operands':i.op_str,
                               'address':None,'width':None,'source_value':None,'critical_field_overlap':False,'may_alias_pool':True})
                memory.clear()
            elif i.mnemonic.startswith('ldr'):
                reads.append(event(at,i,addr,None))
                dst=register(i.reg_name(i.operands[0].reg))
                if i.mnemonic=='ldr' and isinstance(addr,tuple) and addr[0]=='sp' and addr[1] in memory:
                    out[dst]=memory[addr[1]]
                elif group==0x4800:
                    word=((at+4)&~3)+4*(h&255)
                    if word+4>len(rom):raise ValueError('literal outside ROM')
                    out[(h>>8)&7]=struct.unpack_from('<I',rom,word)[0]
            elif h&0xff00==0x4600:
                dst,src=(h&7)|((h>>4)&8),(h>>3)&15
                if src in old:out[dst]=old[src]
            elif group==0x1800:
                dst,src=h&7,(h>>3)&7
                operand=(h>>6)&7;v=operand if h&0x400 else old.get(operand)
                if not h&0x200:
                    value=plus(old.get(src),v)
                    if value is None:value=plus(v,old.get(src))
                else:value=plus(old.get(src),-v) if isinstance(v,int) else None
                if value is not None:out[dst]=value
            elif group in (0x3000,0x3800):
                dst=(h>>8)&7;v=plus(old.get(dst),(h&255)*(-1 if group==0x3800 else 1))
                if v is not None:out[dst]=v
            elif h&0xff00==0x4400:
                dst,src=(h&7)|((h>>4)&8),(h>>3)&15
                v=plus(old.get(dst),old.get(src))
                if v is not None:out[dst]=v
            elif group==0xa800:
                out[(h>>8)&7]=plus(old.get(13),4*(h&255))
            else:
                numeric={r:v for r,v in old.items() if isinstance(v,int)}
                try:
                    values=local.argument_path(rom,at,at+d['size'],numeric)['registers']
                    for r in writes:
                        if r in values:out[r]=values[r]
                except ValueError:pass
        return state,[e['file_offset'] for e in d['successors']],stores,reads,calls,frontiers

    while pending:
        at=pending.popleft();queued.remove(at);updates+=1
        if updates>budget:raise ValueError('pointer worklist budget exhausted')
        new,routes,*_=step(at,states[at])
        for target in routes:
            instruction(target)
            joined=meet(states[target],new) if target in states else copy.deepcopy(new)
            if target not in states or joined!=states[target]:
                states[target]=joined
                if target not in queued:pending.append(target);queued.add(target)
    # Emit from final joined input states, never stale first-path facts.
    stores,reads,calls,frontiers=[],[],[],[]
    for at in sorted(states):
        _,_,s,r,c,f=step(at,states[at]);stores.extend(s);reads.extend(r);calls.extend(c);frontiers.extend(f)
    return {'root':root,'visited_instruction_count':len(states),'updates':updates,'stores':stores,'reads':reads,
            'calls':calls,'frontiers':frontiers,'caller_memory_preserved':False,'promotion_bytes':0,
            'natural_execution_proven':False,'entry_object_domain_proven':False,
            'scope':'Fixed entry pointer hypothesis; all branch edges, opaque aliases and context resumption remain unproved.'}
