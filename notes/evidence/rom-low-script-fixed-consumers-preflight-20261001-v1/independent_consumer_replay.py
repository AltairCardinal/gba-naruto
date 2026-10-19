"""Independent exporter dataflow/parser replay of the frozen discovered sites."""
import gzip
import hashlib
import json
import struct
from pathlib import Path
from tools.export_rom_fixed_renderer_script_records import _prove_parameter_flow
from tools.export_rom_training_text_script_inventory import _parse_training_record, _sjis_ranges

run=Path(__file__).resolve().parent
report=json.loads((run/'consumers.json').read_text())
rom=Path('rom/base.gba').read_bytes()
assert hashlib.sha256(rom).hexdigest()==report['rom_sha256']
sjis=_sjis_ranges(rom)
records={}
for row in report['literal_candidates']:
    site=row['site'];half=struct.unpack_from('<H',rom,site)[0]
    assert half&0xf800==0x4800
    literal=((site+4)&~3)+4*(half&255)
    assert literal==row['literal'] and struct.unpack_from('<I',rom,literal)[0]==0x08000000+row['target']
    assert _prove_parameter_flow(rom,site,(half>>8)&7)==row['interpreter_callsite']
    try:
        parsed=_parse_training_record(rom,row['target'],row['pool'][1],sjis)
        assert [row['target'],parsed['end']]==row['syntax_candidate_range']
        assert parsed['opcode_sequence']==row['syntax_opcode_sequence']
        records[row['target']]=[row['target'],parsed['end']]
    except ValueError:
        assert row.get('syntax_exclusion')=='unsupported opcode 2'
raw=gzip.decompress(Path('notes/evidence/rom-small-cfg-batch-canonical-20260930-v1/coverage-after.json.gz').read_bytes())
assert hashlib.sha256(raw).hexdigest()=='b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
coverage=json.loads(raw)
unique=sorted(records.values())
assert unique==[[0x42b5,0x42bd],[0x42c2,0x42c6]]
unknown=sum(max(0,min(b,s['range'][1])-max(a,s['range'][0])) for a,b in unique for s in coverage['segments'] if s['primary_class']=='unknown')
assert unknown==12
print(json.dumps({'literal_and_parameter_flow_replayed_site_count':6,'syntax_unique_candidate_ranges':unique,
                  'unknown_intersection_bytes':unknown,'accepted_new_records':0,'promotion_bytes':0,
                  'full_runtime_or_context_invariants_proven':False},sort_keys=True,indent=2))
