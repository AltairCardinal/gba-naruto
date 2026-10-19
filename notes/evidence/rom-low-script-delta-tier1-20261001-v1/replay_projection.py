"""Read-only independent source alignment plus accepted delta coverage projection."""
import gzip
import hashlib
import json
from pathlib import Path
from tools._vendor.capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from tools.verify_rom_low_script_delta import project_unknown_claims

root = Path('.')
rom = (root / 'rom/base.gba').read_bytes()
coverage_path = root / 'notes/evidence/rom-small-cfg-batch-canonical-20260930-v1/coverage-after.json.gz'
raw = gzip.decompress(coverage_path.read_bytes())
assert hashlib.sha256(raw).hexdigest() == 'b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
coverage = json.loads(raw)
artifact = root / 'artifacts/rom-low-script-delta-v1'
payload = json.loads((artifact / 'rom-low-script-delta.json').read_bytes())
cfg = json.loads((root / 'artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json').read_bytes())
engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
for row in payload['consumers']:
    owners = [b for b in cfg['blocks'] if b.get('mode') == 'thumb' and b['range'][0] <= row['site'] < b['range'][1]]
    assert len(owners) == 1
    start, end = owners[0]['range']
    assert row['site'] in {i.address - 0x08000000 for i in engine.disasm(rom[start:end], 0x08000000 + start)}
claims = project_unknown_claims(root, artifact, coverage['segments'])
assert [c['range'] for c in claims] == [[0x42B5, 0x42BD], [0x42C2, 0x42C6]]
assert sum(b-a for a,b in (c['range'] for c in claims)) == 12
result = {'accepted_tier1_packet': 'rom-low-script-delta-v1', 'source_instruction_membership_count': 6,
          'projected_unknown_bytes': 12, 'claim_ranges': [c['range'] for c in claims],
          'excluded_root': 0x42BD, 'canonical_changed': False, 'canonical_unknown_bytes': 87631,
          'tier2_accepted': False, 'natural_runtime_reachability': False,
          'coverage_sha256': hashlib.sha256(raw).hexdigest(),
          'rom_sha256': hashlib.sha256(rom).hexdigest()}
print(json.dumps(result, sort_keys=True, indent=2))
