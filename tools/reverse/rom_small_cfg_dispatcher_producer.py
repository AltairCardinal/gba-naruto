"""Pure bounded dispatcher packet composition; no publication API."""
import hashlib
import importlib.util
import json
from pathlib import Path

CONTRACT_SHA256 = 'f0cb65f5184ed6536c808e5d375441810a1251dbfd9bcb3feda648e1155ab711'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def _load(path, name, digest):
    raw = path.read_bytes()
    if sha(raw) != digest:
        raise ValueError('tested pure helper identity')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


HERE = Path(__file__).absolute().parent
reuse = _load(HERE / 'rom_small_cfg_wrappers_producer.py', 'dispatcher_producer_reuse',
              '34dfb4bde185df959931bb7cdfe144d9ab9fe87f5444e3129bbf397ec8727932')
dispatch = _load(HERE / 'rom_small_cfg_dispatch_decode.py', 'dispatcher_finite_decode',
                 '44aa4a516f32efeb421c4f326ef4d99c756a06f571b2e641603b6aabc4839b9c')


def build_payload(rom, baseline_raw, contract_raw):
    if sha(contract_raw) != CONTRACT_SHA256:
        raise ValueError('public contract identity')
    c = json.loads(contract_raw)
    for raw,pin in ((rom,c['rom']), (baseline_raw,{'size':c['baseline_raw_size'],'sha256':c['baseline_raw_sha256']})):
        if len(raw)!=pin['size'] or sha(raw)!=pin['sha256']:
            raise ValueError('raw input identity')
    baseline = json.loads(baseline_raw)
    segments = reuse._validate_baseline_segments(baseline['segments'], rom_size=len(rom))
    claims = {row['id']:row for row in baseline['claims']}
    producers = reuse.scan_producers(rom,c['roots'])
    for row in producers:
        row['owners'] = reuse._producer_owners(segments,claims,row['source'],row['source']+row['size'])
    if producers != c['expected_producers']:
        raise ValueError('full ROM target-limited producer denominator')
    pointers = reuse._scan_pointer_occurrences(rom,c['roots'])
    if pointers != c['root_pointer_occurrences']:
        raise ValueError('root pointer occurrence denominator')
    witness = dispatch.decode_dispatch(rom,c['roots'][0])
    if witness['prefix_range']!=c['code_ranges'][0] or witness['table_range']!=c['table_range']:
        raise ValueError('bounded dispatch domains')
    second,end = c['code_ranges'][1]
    first = int.from_bytes(rom[second:second+2],'little')
    target = reuse._decode_bl_target(second+2,int.from_bytes(rom[second+2:second+4],'little'),int.from_bytes(rom[second+4:end],'little'))
    if first != 0x2098 or target!=0x61E6C or end!=witness['default_target']:
        raise ValueError('downstream immediate and call boundary')
    instructions = witness['instructions'] + [
        {'offset':second,'size':2,'raw_hex':rom[second:second+2].hex()},
        {'offset':second+2,'size':4,'raw_hex':rom[second+2:end].hex()}]
    root = c['roots'][0]
    edges = [{'source':root+14,'kind':'branch_target','target':witness['default_target'],'scope':'opaque'},
             {'source':root+14,'kind':'fallthrough','target':root+16,'scope':'internal'}]
    for dest in sorted({r['target'] for r in witness['table_entries']}):
        edges.append({'source':root+24,'kind':'dispatch_target','target':dest,
                      'scope':'internal' if dest==second else 'opaque',
                      'slot_indices':[r['slot_index'] for r in witness['table_entries'] if r['target']==dest]})
    edges += [{'source':second+2,'kind':'call_target','target':target,'scope':'opaque'},
              {'source':second+2,'kind':'fallthrough','target':end,'scope':'opaque'}]
    summary = {'instruction_count':len(instructions),'basic_block_count':3,'block_edge_count':len(edges),
               'code_bytes':sum(b-a for a,b in c['code_ranges']), 'literal_bytes':8,'table_bytes':80,
               'table_slot_count':len(witness['table_entries']),'frontier_count':0,'structured_return_count':0,
               'producer_count':len(producers),'opaque_entry_count':4,'existing_owner_bytes':80,
               'promotion_bytes':40,'claim_count':4}
    closure = {'dispatch':witness,'instructions':instructions,'code_ranges':c['code_ranges'],
               'literal_ranges':c['literal_ranges'],'table_range':c['table_range'],
               'blocks':[[root,root+16],[root+16,root+26],[second,end]],'edges':edges,
               'frontiers':[],'preserved_holes':c['preserved_holes'],'summary':summary}
    new_ranges = sorted([[a,b,'reachable_thumb_code'] for a,b in c['code_ranges']]+[
        [*c['literal_ranges'][0],'consumed_literal_words'],[*c['new_table_tail_range'],'bounded_dispatch_table_slots']])
    promotion = []
    for a,b,kind in new_ranges:
        own = reuse._owners_for_range(segments,claims,a,b,require_unknown=True)
        promotion.append({'id':f'u8-subtract-dispatch-{kind}-{len(promotion):02d}-{a:06x}',
                          'kind':kind,'range':[a,b],'bytes_sha256':sha(rom[a:b]),'baseline_owners':own})
    old = []
    for a,b in [c['literal_ranges'][1],[c['table_range'][0],c['new_table_tail_range'][0]]]:
        portions = reuse._owners_for_range(segments,claims,a,b,require_unknown=False)
        old.append({'range':[a,b],'bytes_sha256':sha(rom[a:b]),'segments':portions,
                    'claims':[claims[cid] for s in portions for cid in s['primary_claim_ids']]})
    return {'schema':c['output_schema'],'rom':c['rom'],'upstream_inputs':c['upstream_inputs'],
            'baseline':{'archive_reference':c['baseline_archive'],'archive_observed_during_this_build':False,
                        'raw_size':len(baseline_raw),'raw_sha256':sha(baseline_raw)},
            'roots':c['roots'],'producers':producers,'root_pointer_occurrences':pointers,
            'closure':closure,'promotion':{'claims':promotion,'claim_count':len(promotion),
                                         'promotion_bytes':sum(r['range'][1]-r['range'][0] for r in promotion)},
            'existing_owner_provenance':old,'scope':c['scope']}
