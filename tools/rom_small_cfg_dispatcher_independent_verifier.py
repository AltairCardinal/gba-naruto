"""Independent raw bounded-dispatch reconstruction; no producer imports."""
import gzip
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys

CONTRACT_SHA256 = 'f0cb65f5184ed6536c808e5d375441810a1251dbfd9bcb3feda648e1155ab711'
HERE = Path(__file__).absolute().parent
helper = HERE / 'rom_small_cfg_wrappers_independent_verifier.py'
helper_raw = helper.read_bytes()
if hashlib.sha256(helper_raw).hexdigest() != '3d1524d799a6b1f7d86de7488ba849605fdd533e8a4882922e539cb5dcbefdf8':
    raise ValueError('independent raw scan and IO helper identity')
spec = importlib.util.spec_from_file_location('dispatcher_verifier_reuse',helper)
reuse = importlib.util.module_from_spec(spec)
exec(compile(helper_raw,str(helper),'exec'),reuse.__dict__)
sha,canonical = reuse.sha,reuse.canonical


def decode_dispatch_raw(rom, root):
    """Decode the finite dataflow independently with numeric opcode families."""
    if type(root)!=int or root<0 or root%2 or root+26>len(rom):
        raise ValueError('prefix bounds')
    words = [int.from_bytes(rom[at:at+2],'little') for at in range(root,root+26,2)]
    fixed = {0:46576,3:26624,8:128,10:6208,11:26624,12:18055}
    if any(words[i]!=value for i,value in fixed.items()):
        raise ValueError('fixed Thumb dataflow')
    if (words[1]//256!=72 or words[2]//256!=48 or words[4]//2048!=15
            or words[4]%64!=0 or words[5]//256!=56 or words[6]//256!=40
            or words[7]//256!=216 or words[9]//256!=73):
        raise ValueError('load, subtract, comparison and unsigned condition registers')
    subtract, maximum = words[5]%256,words[6]%256
    if subtract+maximum>255:
        raise ValueError('complete u8 slot witnesses')
    literals = [(root+6)//4*4 + (words[1]%256)*4,
                (root+22)//4*4 + (words[9]%256)*4]
    if any(at<0 or at+4>len(rom) for at in literals):
        raise ValueError('literal bound')
    values = [int.from_bytes(rom[at:at+4],'little') for at in literals]
    table = values[1]-134217728
    stop = table+(maximum+1)*4
    if table<0 or table%4 or stop>len(rom):
        raise ValueError('table extent')
    domains = [[root,root+26],*[ [at,at+4] for at in literals ],[table,stop]]
    ordered = sorted(domains)
    if any(left[1]>right[0] for left,right in zip(ordered,ordered[1:])):
        raise ValueError('overlapping prefix and data domains')
    displacement = words[7]%256
    if displacement>=128:
        displacement-=256
    default = root+18+2*displacement
    def target_ok(at):
        return 0<=at<=len(rom)-2 and at%2==0 and all(not a<=at<b for a,b in domains)
    if not target_ok(default):
        raise ValueError('default target bound')
    entries = []
    for slot, at in enumerate(range(table,stop,4)):
        pointer = int.from_bytes(rom[at:at+4],'little')
        target = pointer-134217728
        if not target_ok(target):
            raise ValueError('retained Thumb target bound')
        entries.append({'slot_index':slot,'entry_offset':at,'raw_pointer':pointer,'target':target,'mode':'thumb'})
    inputs = []
    for byte in range(256):
        index = (byte-subtract) % 4294967296
        slot = index if index<=maximum else None
        inputs.append({'command':byte,'index_u32':index,'slot_index':slot,
                       'target':default if slot is None else entries[slot]['target']})
    if {r['slot_index'] for r in inputs if r['slot_index'] is not None}!=set(range(maximum+1)):
        raise ValueError('unwitnessed slot')
    return {'root':root,'prefix_range':[root,root+26],
            'instructions':[{'offset':at,'size':2,'raw_hex':rom[at:at+2].hex()} for at in range(root,root+26,2)],
            'literal_bindings':[[source,at,rom[at:at+4].hex()] for source,at in zip([root+2,root+18],literals)],
            'state_base_value':values[0],'state_pointer_field_offset':words[2]%256,
            'command_field_offset':(words[4]//64)%32,'subtract':subtract,'maximum_index':maximum,
            'default_target':default,'table_range':[table,stop],'table_sha256':sha(rom[table:stop]),
            'table_entries':entries,'input_domain':inputs}


def rebuild_closure(rom,c):
    dispatch = decode_dispatch_raw(rom,c['roots'][0])
    if (dispatch['table_range']!=c['table_range'] or dispatch['prefix_range']!=c['code_ranges'][0]
            or [[at,at+4] for _,at,_ in dispatch['literal_bindings']]!=c['literal_ranges']
            or dispatch['table_sha256']!='07712dfdc072fa241953a2215963626d186af7967991ddf18f66ec378479c363'
            or (dispatch['subtract'],dispatch['maximum_index'],dispatch['state_pointer_field_offset'],
                dispatch['command_field_offset'],dispatch['state_base_value'])!=(36,19,196,4,0x02026BE0)):
        raise ValueError('frozen dispatch domain or full table identity')
    for row in c['expected_projection']['ranges']:
        a,b=row['range']
        if sha(rom[a:b])!=row['sha256'] or rom[a:b].hex()!=row['raw_hex']:
            raise ValueError('frozen new semantic bytes')
    extra_start,extra_end = c['code_ranges'][1]
    branch = reuse._branch(rom,extra_start+2)
    if int.from_bytes(rom[extra_start:extra_start+2],'little')!=8344 or branch!=('thumb_bl',0x61E6C,4):
        raise ValueError('downstream immediate and call')
    if extra_end!=extra_start+6 or extra_end!=dispatch['default_target']:
        raise ValueError('downstream opaque fallthrough')
    if set(r['target'] for r in dispatch['table_entries'])!={extra_start,0x7DD2C,0x7DD34,0x7DD42}:
        raise ValueError('resolved dispatch targets')
    root = c['roots'][0]
    nodes = dispatch['instructions']+[
        {'offset':extra_start,'size':2,'raw_hex':rom[extra_start:extra_start+2].hex()},
        {'offset':extra_start+2,'size':4,'raw_hex':rom[extra_start+2:extra_end].hex()}]
    edges = [{'source':root+14,'kind':'branch_target','target':dispatch['default_target'],'scope':'opaque'},
             {'source':root+14,'kind':'fallthrough','target':root+16,'scope':'internal'}]
    for target in sorted({e['target'] for e in dispatch['table_entries']}):
        edges.append({'source':root+24,'kind':'dispatch_target','target':target,
                      'scope':'internal' if target==extra_start else 'opaque',
                      'slot_indices':[e['slot_index'] for e in dispatch['table_entries'] if e['target']==target]})
    edges.extend([{'source':extra_start+2,'kind':'call_target','target':branch[1],'scope':'opaque'},
                  {'source':extra_start+2,'kind':'fallthrough','target':extra_end,'scope':'opaque'}])
    blocks = [[root,root+16],[root+16,root+26],[extra_start,extra_end]]
    reachable = {root}
    changed = True
    while changed:
        changed = False
        for edge in edges:
            if any(a in reachable and a<=edge['source']<b for a,b in blocks) and edge['scope']=='internal' and edge['target'] not in reachable:
                reachable.add(edge['target']);changed=True
    if reachable!={a for a,b in blocks} or sum(r['size'] for r in nodes)!=sum(b-a for a,b in blocks):
        raise ValueError('complete root-reachable block denominator')
    opaque = {e['target'] for e in edges if e['scope']=='opaque'}
    if opaque!=set(c['opaque_entries']):
        raise ValueError('opaque boundary denominator')
    summary = {'instruction_count':len(nodes),'basic_block_count':len(blocks),'block_edge_count':len(edges),
               'code_bytes':sum(r['size'] for r in nodes),'literal_bytes':len(dispatch['literal_bindings'])*4,
               'table_bytes':dispatch['table_range'][1]-dispatch['table_range'][0],
               'table_slot_count':len(dispatch['table_entries']),'frontier_count':0,'structured_return_count':0,
               'producer_count':1,'opaque_entry_count':len(opaque),'existing_owner_bytes':80,
               'promotion_bytes':c['expected_projection']['bytes'],'claim_count':len(c['expected_projection']['ranges'])}
    return {'dispatch':dispatch,'instructions':nodes,'code_ranges':c['code_ranges'],
            'literal_ranges':c['literal_ranges'],'table_range':c['table_range'],'blocks':blocks,'edges':edges,
            'frontiers':[],'preserved_holes':c['preserved_holes'],'summary':summary}


def _upstream(root,rom,blobs,baseline,producers,c):
    if str(root) not in sys.path:
        sys.path.insert(0,str(root))
    event = importlib.import_module('tools.verify_rom_event_handler_cfg')
    inv = importlib.import_module('tools.verify_rom_cfg_inventory')
    for module in (event,inv):
        if Path(module.__file__).absolute()!=root/'tools'/(module.__name__.split('.')[-1]+'.py'):
            raise ValueError('upstream module identity')
    inv._decoder_identity(root);event._assert_oracle_identities(root)
    event_path = 'artifacts/rom-event-handler-cfg-v1/rom-event-handler-cfg.json'
    event_payload = json.loads(blobs[event_path])
    cfg,promotion = event._rebuild(rom)
    if cfg!=event_payload['cfg'] or promotion!=event_payload['promotion']:
        raise ValueError('raw event closure')
    members = {}
    for entry in event.C.ACCEPTED_ROOTS:
        nodes,_,_ = event._decode_root(rom,entry)
        for (_,at),node in nodes.items():
            members.setdefault(at,[]).append((entry,node['size']))
    claims = {row['id']:row for row in baseline['claims']}
    proof=[]
    for row in producers:
        at,size=row['source'],row['size']
        entries=members.get(at,[])
        if not entries or any(n!=size for _,n in entries):
            raise ValueError('producer raw instruction membership')
        own = [claims[cid] for s in reuse._owners(baseline,at,at+size) for cid in s['primary_claim_ids']]
        if len(own)!=1:
            raise ValueError('unique source owner')
        claim=own[0]
        matches=[i for i,r in enumerate(promotion['semantic_ranges']) if r==[*claim['range'],'reachable_thumb_code']]
        if (len(matches)!=1 or claim['claim_kind']!='event_handler_reachable_instruction_bytes'
                or claim['evidence_path']!=event_path or claim['evidence_sha256']!=sha(blobs[event_path])
                or claim['evidence_selector']!=f'/promotion/semantic_ranges/{matches[0]}'
                or claim['bytes_sha256']!=sha(rom[slice(*claim['range'])])):
            raise ValueError('exact event source owner')
        proof.append({'source':at,'target':row['target'],'size':size,'owner_claim_ids':[claim['id']],
                      'accepted_roots_reaching_source':sorted(e for e,_ in entries),'upstream_payload':event_path})
    inv_path='artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json'
    inventory=json.loads(blobs[inv_path]);opaque=[]
    for entry in c['opaque_entries']:
        blocks=[b for b in inventory['blocks'] if b['mode']=='thumb' and b['range'][0]==entry]
        if len(blocks)!=1:
            raise ValueError('opaque exact accepted block start')
        _,entries,_,_=inv._verify_blocks(rom,blocks)
        if ('thumb',entry) not in entries:
            raise ValueError('opaque raw boundary')
        owners=[claims[cid] for s in reuse._owners(baseline,*blocks[0]['range']) for cid in s['primary_claim_ids']]
        if not owners or any(claim['evidence_path']!=inv_path or claim['evidence_sha256']!=sha(blobs[inv_path])
                             or claim.get('mode')!='thumb' or claim['bytes_sha256']!=sha(rom[slice(*claim['range'])]) for claim in owners):
            raise ValueError('opaque canonical owner identity')
        opaque.append({'entry':entry,'block':blocks[0],'owner_claim_ids':sorted({cl['id'] for cl in owners})})
    return {'producer_instruction_membership':proof,'source_instruction_count':cfg['instruction_count'],
            'opaque_entry_membership':opaque,'source_full_verifier_replayed_here':False}


def verify_candidate(root, contract_path, candidate):
    root=Path(root).absolute()
    contract_raw=reuse._read(contract_path)
    if sha(contract_raw)!=CONTRACT_SHA256:
        raise ValueError('public contract identity')
    c=json.loads(contract_raw)
    rom=reuse._pinned(root,c['rom'])
    blobs={pin['path']:reuse._pinned(root,pin) for pin in c['upstream_inputs']}
    baseline_raw=gzip.decompress(reuse._pinned(root,c['baseline_archive']))
    if len(baseline_raw)!=c['baseline_raw_size'] or sha(baseline_raw)!=c['baseline_raw_sha256']:
        raise ValueError('immutable baseline identity')
    baseline=json.loads(baseline_raw);cursor=0
    for segment in baseline['segments']:
        a,b=segment['range']
        if a!=cursor or b<=a:
            raise ValueError('baseline partition')
        cursor=b
    if cursor!=len(rom):
        raise ValueError('complete baseline domain')
    claims={r['id']:r for r in baseline['claims']}
    producers=reuse.scan_producers(rom,c['roots'])
    for row in producers:
        a,b=row['source'],row['source']+row['size']
        row['owners']=[{'intersection':[max(a,s['range'][0]),min(b,s['range'][1])],'segment':s,
                        'claims':[{k:v for k,v in claims[cid].items() if k in reuse.CLAIM_FIELDS} for cid in s['primary_claim_ids']]}
                       for s in reuse._owners(baseline,a,b)]
    if producers!=c['expected_producers']:
        raise ValueError('raw complete producer denominator')
    pointers={}
    for entry in c['roots']:
        value=0x08000001+entry;needle=value.to_bytes(4,'little');start=0;found=[]
        while (offset:=rom.find(needle,start))>=0:
            found.append(offset);start=offset+1
        pointers[hex(value)]=found
    if pointers!=c['root_pointer_occurrences']:
        raise ValueError('root pointer denominator')
    closure=rebuild_closure(rom,c)
    new=[]
    for row in c['expected_projection']['ranges']:
        a,b=row['range'];owners=reuse._owners(baseline,a,b)
        if any(s['primary_class']!='unknown' or s['primary_claim_ids'] or s['secondary_claim_ids'] for s in owners):
            raise ValueError('promotion not wholly unknown')
        kind=('reachable_thumb_code' if [a,b] in closure['code_ranges'] else
              'consumed_literal_words' if [a,b] in closure['literal_ranges'] else
              'bounded_dispatch_table_slots' if [a,b]==c['new_table_tail_range'] else None)
        if kind is None:
            raise ValueError('unproven semantic projection')
        new.append({'id':f'u8-subtract-dispatch-{kind}-{len(new):02d}-{a:06x}','kind':kind,'range':[a,b],
                    'bytes_sha256':sha(rom[a:b]),'baseline_owners':owners})
    old=[]
    for a,b in [c['literal_ranges'][1],[c['table_range'][0],c['new_table_tail_range'][0]]]:
        segs=reuse._owners(baseline,a,b);owners=[claims[cid] for s in segs for cid in s['primary_claim_ids']]
        if len(owners)!=1 or owners[0]['range']!=[a,b] or owners[0]['bytes_sha256']!=sha(rom[a:b]):
            raise ValueError('exact preowned literal or table prefix')
        old.append({'range':[a,b],'bytes_sha256':sha(rom[a:b]),'segments':segs,'claims':owners})
    if sum(b-a for a,b in (row['range'] for row in old))!=closure['summary']['existing_owner_bytes']:
        raise ValueError('preowned byte denominator')
    expected={'schema':c['output_schema'],'rom':c['rom'],'upstream_inputs':c['upstream_inputs'],
              'baseline':{'archive_reference':c['baseline_archive'],'archive_observed_during_this_build':False,
                          'raw_size':len(baseline_raw),'raw_sha256':sha(baseline_raw)},
              'roots':c['roots'],'producers':producers,'root_pointer_occurrences':pointers,
              'closure':closure,'promotion':{'claims':new,'claim_count':len(new),'promotion_bytes':sum(b-a for a,b in (r['range'] for r in new))},
              'existing_owner_provenance':old,'scope':c['scope']}
    if canonical(candidate)!=canonical(expected):
        raise ValueError('candidate differs from independent raw reconstruction')
    upstream=_upstream(root,rom,blobs,baseline,producers,c)
    for pin in c['upstream_inputs']:
        reuse._pinned(root,pin)
    return {'schema':'rom-u8-subtract-bounded-movpc-dispatch-candidate-verification-v1','verified':True,
            **closure['summary'],**upstream,'canonical_promoted':False,'scope':c['scope'],
            'candidate_payload_sha256':sha(canonical(candidate)),'public_contract_sha256':CONTRACT_SHA256,
            'upstream_inputs':c['upstream_inputs'],'baseline_archive':c['baseline_archive'],
            'baseline_archive_observed_by_verifier':True,'baseline_raw_sha256':sha(baseline_raw)}
