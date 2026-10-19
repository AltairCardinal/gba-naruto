"""Read-only planning snapshot. Not a semantic verifier or promotion producer."""
import hashlib
import json
from pathlib import Path

root = Path('.')
paths = ['sequel/rom-byte-coverage.json', 'sequel/reverse-engineering-proof.json',
         'sequel/bank-proofs.json', 'rom/base.gba',
         'build/experiments/active/late-cfg-consumers/schemas15-21-20261001-v1/screen.json']
inputs = {p: {'sha256': hashlib.sha256((root / p).read_bytes()).hexdigest(),
              'size': (root / p).stat().st_size} for p in paths}
assert inputs[paths[0]]['sha256'] == 'b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
assert inputs['rom/base.gba']['sha256'] == '1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
c = json.loads((root / paths[0]).read_text())
p = json.loads((root / paths[1]).read_text())
b = json.loads((root / paths[2]).read_text())['banks']
s = json.loads((root / paths[4]).read_text())
unknown = [x['range'] for x in c['segments'] if x['primary_class'] == 'unknown']
total = sum(hi - lo for lo, hi in unknown)
assert total == c['summary']['unknown_bytes'] == 87631
large = [r for r in unknown if r[1] - r[0] >= 1024]
banks = {name: data['coverage'] for name, data in b.items()
         if data['catalog_classification'] != 'disproved'}
rows = s['unknown_literal_consumers']
text_candidates = [r for r in rows if 0x463914 <= r['target'] <= 0x463b18]
result = {
    'schema': 'reverse-work-planning-snapshot-v1', 'inputs': inputs,
    'canonical': {k: c['summary'][k] for k in ['classified_bytes', 'unknown_bytes', 'claim_count', 'segment_count']},
    'unknown_ranges': len(unknown), 'large_range_count': len(large),
    'large_range_bytes': sum(hi-lo for lo, hi in large),
    'top_ranges': [{'range': r, 'bytes': r[1]-r[0]} for r in sorted(unknown, key=lambda r:r[1]-r[0], reverse=True)[:22]],
    'gates': {k: {'status': v['status'], 'coverage': v.get('coverage'),
                  'limitations': v.get('limitations', [])} for k, v in p['gates'].items()},
    'valid_banks': banks, 'valid_bank_count': len(banks),
    'declared_records_total': sum(v['records_total'] for v in banks.values()),
    'declared_records_covered': sum(v['records_covered'] for v in banks.values()),
    'late_cfg_screen': {'code_bytes': sum(d['screened_code_bytes'] for d in s['domains']),
                       'instructions': sum(d['screened_instruction_count'] for d in s['domains']),
                       'literal_sites': len(rows), 'text_candidate_sites': len(text_candidates),
                       'text_candidate_targets': sorted({r['target'] for r in text_candidates}),
                       'source_semantic_verifiers_rerun': s['source_semantic_verifiers_rerun']},
    'scope': 'Inventory arithmetic and existing declared status only; no new semantic acceptance, runtime proof or promotion.',
    'promotion_bytes': 0,
}
assert len(banks) == 22
assert result['declared_records_total'] == 2954
assert result['declared_records_covered'] == 23
assert len(rows) == 32
print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
