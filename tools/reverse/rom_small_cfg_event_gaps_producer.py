"""Pure event gap builder reusing the tested callback boundary derivation.

The parent binds the upstream files and independently replays the source CFG.
This prototype is not a publication API or a canonical acceptance receipt.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

CONTRACT_SHA256 = 'a69a2fe7fbf9748957ee5258ae850c6049c829a63c3422047b06491debe85f0a'
HELPER_SHA256 = '241edc5022877fe05abce6ffcac760ecb7aa54414a7431a366b5d0e362315315'
helper_path = Path(__file__).absolute().parent / 'rom_small_cfg_callback_gaps_producer.py'
helper_raw = helper_path.read_bytes()
if hashlib.sha256(helper_raw).hexdigest() != HELPER_SHA256:
    raise ValueError('tested helper identity')
spec = importlib.util.spec_from_file_location('event_gap_producer_reuse', helper_path)
reuse = importlib.util.module_from_spec(spec)
exec(compile(helper_raw, str(helper_path), 'exec'), reuse.__dict__)


def build_payload(rom, source_raw, baseline_raw, contract_raw):
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    if sha(contract_raw) != CONTRACT_SHA256:
        raise ValueError('public contract identity')
    contract = json.loads(contract_raw)
    for raw, pin in ((rom, contract['rom']), (source_raw, contract['source_payload']),
                     (baseline_raw, {'size':contract['baseline_raw_size'],'sha256':contract['baseline_raw_sha256']})):
        if len(raw) != pin['size'] or sha(raw) != pin['sha256']:
            raise ValueError('raw input identity')
    source = json.loads(source_raw)
    if source['cfg'] != contract['source_cfg'] or source['promotion'] != contract['source_promotion']:
        raise ValueError('source artifact denominator')
    rows = reuse.derive_boundaries(rom, source['promotion']['code_ranges'], source['promotion']['literal_ranges'],
                                   contract['source_literal_bindings'])
    baseline = json.loads(baseline_raw)
    segments = reuse._validate_baseline_segments(baseline['segments'], rom_size=len(rom))
    claims = {row['id']:row for row in baseline['claims']}
    for index, row in enumerate(rows):
        row['id'] = f'event-handler-align4-{index:02d}-{row["range"][0]:06x}'
        owners = {}
        for side, key in [('left','left_code_range'),('gap','range'),('right','right_literal_range')]:
            a,b = row[key]
            portions = [copy.deepcopy(s) for s in segments if s['range'][0]<b and a<s['range'][1]]
            if side == 'gap' and any(s['primary_class']!='unknown' or s['primary_claim_ids'] or s['secondary_claim_ids'] for s in portions):
                raise ValueError('gap is not wholly unknown')
            owners[side] = {'segments':portions,'claims':[copy.deepcopy(claims[cid]) for s in portions for cid in s['primary_claim_ids']]}
        row['baseline_owners'] = owners
    if rows != contract['expected_boundaries']:
        raise ValueError('derived complete boundary denominator')
    return {'schema':contract['output_schema'],'rom':contract['rom'],'upstream_inputs':contract['upstream_inputs'],
            'baseline':{'archive_reference':contract['baseline_archive'],'raw_sha256':sha(baseline_raw),
                        'raw_size':len(baseline_raw),'archive_observed_during_this_build':False},
            'source':{'cfg':source['cfg'],'promotion':source['promotion'],
                      'literal_bindings':contract['source_literal_bindings'],
                      'zero_gap_literal_starts':contract['zero_gap_literal_starts'],
                      'excluded_holes':contract['excluded_holes']},
            'boundaries':rows,'scope':contract['scope'],
            'promotion':{'claim_count':len(rows),'promotion_bytes':sum(b-a for a,b in (r['range'] for r in rows)),
                         'claims':[{key:row[key] for key in ('id','kind','range','bytes_sha256')} for row in rows]}}
