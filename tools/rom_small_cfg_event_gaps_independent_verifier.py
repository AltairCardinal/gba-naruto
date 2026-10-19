"""Independent event gap verification using accepted raw CFG and gap logic."""
import copy
import gzip
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys

CONTRACT_SHA256 = 'a69a2fe7fbf9748957ee5258ae850c6049c829a63c3422047b06491debe85f0a'
HELPER_SHA256 = 'c6244e7fbb08b63dd8387cbba9b381564e24ad72b13f717d1cc9752dd3f3d083'
helper_path = Path(__file__).absolute().parent / 'rom_small_cfg_callback_gaps_independent_verifier.py'
helper_raw = helper_path.read_bytes()
if hashlib.sha256(helper_raw).hexdigest() != HELPER_SHA256:
    raise ValueError('independent boundary helper identity')
spec = importlib.util.spec_from_file_location('event_gap_verifier_reuse', helper_path)
reuse = importlib.util.module_from_spec(spec)
exec(compile(helper_raw, str(helper_path), 'exec'), reuse.__dict__)
canonical = reuse.canonical
sha = reuse.sha


def verify_candidate(root, contract_path, candidate):
    root = Path(root).absolute()
    raw = reuse.read_regular(contract_path)
    if sha(raw) != CONTRACT_SHA256:
        raise ValueError('public contract identity')
    contract = json.loads(raw)
    rom = reuse.read_pinned(root, contract['rom'])
    blobs = {pin['path']:reuse.read_pinned(root, pin) for pin in contract['upstream_inputs']}
    archive = reuse.read_pinned(root, contract['baseline_archive'])
    baseline_raw = gzip.decompress(archive)
    if len(baseline_raw) != contract['baseline_raw_size'] or sha(baseline_raw) != contract['baseline_raw_sha256']:
        raise ValueError('immutable baseline identity')
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    source = importlib.import_module('tools.verify_rom_event_handler_cfg')
    decoder = importlib.import_module('tools.verify_rom_cfg_inventory')
    for module in (source, decoder):
        if Path(module.__file__).absolute() != root / 'tools' / (module.__name__.split('.')[-1] + '.py'):
            raise ValueError('raw source module path')
    decoder._decoder_identity(root)
    source._assert_oracle_identities(root)
    cfg, promotion = source._rebuild(rom)
    source_payload = json.loads(blobs[contract['source_payload']['path']])
    if cfg != source_payload['cfg'] or promotion != source_payload['promotion']:
        raise ValueError('source full raw closure identity')
    nodes = {}
    for entry in source.C.ACCEPTED_ROOTS:
        partial, _, _ = source._decode_root(rom, entry)
        nodes.update(partial)
    bindings = []
    for (_, offset), node in sorted(nodes.items(), key=lambda item:item[0][1]):
        h = int.from_bytes(rom[offset:offset+2], 'little')
        if node['size']==2 and h >> 11 == 9:
            target = ((offset+4)//4 + (h & 255))*4
            bindings.append([offset,target,rom[target:target+4].hex()])
    code, literals = promotion['code_ranges'], promotion['literal_ranges']
    ordered = sorted([[a,b,'code'] for a,b in code]+[[a,b,'literal'] for a,b in literals])
    eligible = [[b,c] for (a,b,left),(c,d,right) in zip(ordered,ordered[1:])
                if left=='code' and right=='literal' and b<c]
    excluded = [{'range':[a,b],'reason':'right_neighbor_is_code' if b-a==2 else 'unbounded_tail_includes_rejected_root'}
                for a,b in promotion['preserved_unknown_holes'] if [a,b] not in eligible]
    zero_gaps = [a for a,b in literals if any(end==a for start,end in code)]
    closure = {'code_ranges':code,'literal_ranges':literals,'literal_bindings':bindings,'holes':eligible}
    rows = reuse.derive_boundaries(rom, closure)
    baseline = json.loads(baseline_raw)
    claims = {c['id']:c for c in baseline['claims']}
    for index,row in enumerate(rows):
        row['id'] = f'event-handler-align4-{index:02d}-{row["range"][0]:06x}'
        owners = {}
        for side,key in [('left','left_code_range'),('gap','range'),('right','right_literal_range')]:
            a,b = row[key]
            segments = [copy.deepcopy(s) for s in baseline['segments'] if s['range'][0]<b and a<s['range'][1]]
            full_claims = [copy.deepcopy(claims[cid]) for s in segments for cid in s['primary_claim_ids']]
            if not segments:
                raise ValueError('missing owner segment')
            if side=='gap':
                if any(s['primary_class']!='unknown' or s['primary_claim_ids'] or s['secondary_claim_ids'] for s in segments):
                    raise ValueError('gap is not wholly unknown')
            else:
                semantic_kind = 'reachable_thumb_code' if side=='left' else 'consumed_literal_word'
                matching = [(i,r) for i,r in enumerate(promotion['semantic_ranges']) if r==[a,b,semantic_kind]]
                if len(matching)!=1 or len(full_claims)!=1:
                    raise ValueError('complete source owner denominator')
                claim = full_claims[0]
                expected_kind = 'event_handler_reachable_instruction_bytes' if side=='left' else 'armv4t_event_handler_consumed_literal_word_bytes'
                if (claim['range']!=[a,b] or claim['claim_kind']!=expected_kind or claim['role']!='primary'
                        or claim['evidence_path']!=contract['source_payload']['path']
                        or claim['evidence_sha256']!=contract['source_payload']['sha256']
                        or claim['evidence_selector']!=f'/promotion/semantic_ranges/{matching[0][0]}'
                        or claim['bytes_sha256']!=sha(rom[a:b])):
                    raise ValueError('exact accepted source owner')
            owners[side] = {'segments':segments,'claims':full_claims}
        row['baseline_owners'] = owners
    if (rows!=contract['expected_boundaries'] or bindings!=contract['source_literal_bindings']
            or excluded!=contract['excluded_holes'] or zero_gaps!=contract['zero_gap_literal_starts']):
        raise ValueError('full boundary and exclusion denominator')
    expected = {'schema':contract['output_schema'],'rom':contract['rom'],'upstream_inputs':contract['upstream_inputs'],
                'baseline':{'archive_reference':contract['baseline_archive'],'raw_sha256':sha(baseline_raw),
                            'raw_size':len(baseline_raw),'archive_observed_during_this_build':False},
                'source':{'cfg':cfg,'promotion':promotion,'literal_bindings':bindings,
                          'zero_gap_literal_starts':zero_gaps,'excluded_holes':excluded},
                'boundaries':rows,'scope':contract['scope'],
                'promotion':{'claim_count':len(rows),'promotion_bytes':sum(b-a for a,b in eligible),
                             'claims':[{k:r[k] for k in ('id','kind','range','bytes_sha256')} for r in rows]}}
    if canonical(candidate)!=canonical(expected):
        raise ValueError('candidate differs from independent raw reconstruction')
    summary = {'gap_count':len(rows),'promotion_bytes':sum(b-a for a,b in eligible),
               'claim_count':len(rows),
               'unconditional_branch_count':sum(r['terminal']['kind']=='unconditional_branch' for r in rows),
               'indirect_pc_target_count':sum(r['terminal']['kind']=='indirect_pc_target' for r in rows),
               'source_instruction_count':len(nodes),'source_code_range_count':len(code),
               'source_literal_range_count':len(literals),'source_literal_binding_count':len(bindings)}
    if summary!=contract['summary']:
        raise ValueError('raw summary denominator')
    for pin in contract['upstream_inputs']:
        reuse.read_pinned(root,pin)
    return {'schema':'rom-event-handler-seven-gaps-candidate-verification-v1','verified':True,
            **summary,'candidate_payload_sha256':sha(canonical(candidate)),
            'public_contract_sha256':CONTRACT_SHA256,'upstream_inputs':contract['upstream_inputs'],
            'baseline_archive_observed_by_verifier':True,'baseline_archive':contract['baseline_archive'],
            'baseline_raw_sha256':sha(baseline_raw),'zero_gap_count':len(zero_gaps),
            'excluded_hole_bytes':sum(b-a for row in excluded for a,b in [row['range']]),
            'source_frontier_count':cfg['frontier_count'],'source_full_verifier_replayed_here':False,
            'canonical_promoted':False,'scope':contract['scope']}
