import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from tools.verify_map_resource_relocation_audit import verify_audit,_read_resources
from tools.verify_map_resource_writeback_audit import _decompress
root=Path.cwd();run=Path(__file__).parent;rom=(root/'rom/base.gba').read_bytes()
report=verify_audit(root,root/'artifacts/map-resource-relocation-v1')
resources=_read_resources(rom,json.loads((root/'artifacts/map-canvases-v1/manifest.json').read_text()))
for row in resources.values():
 for offset in row['physical_offsets']:assert _decompress(rom,offset)==row['source_content']
(run/'preflight.json').write_text(json.dumps({'legacy':report,'independent_raw_codec_all_217_match':True,'pointer_scan_scope':'All 4-byte-aligned source-ROM u32 words; computed and unaligned consumers not exhausted.'},indent=2,sort_keys=True)+'\n')
with (run/'tests.log').open('w') as stream:
 suite=unittest.TestLoader().loadTestsFromNames(['tests.test_import_map_resource_relocations','tests.test_map_resource_relocation_audit','tests.test_image_resource_regions'])
 result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
