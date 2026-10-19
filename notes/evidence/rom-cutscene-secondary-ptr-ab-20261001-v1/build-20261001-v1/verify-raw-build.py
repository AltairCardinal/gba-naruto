from pathlib import Path
import hashlib,json
from tools.verify_cutscene_obj_primary_ptr_ab import _lz77
r=Path('build/experiments/active/cutscene-secondary-ptr-ab/build-20261001-v1')
m=json.loads((r/'build/build-manifest.json').read_text());a=(r/'build/baseline/baseline.gba').read_bytes();b=(r/'build/candidate/candidate.gba').read_bytes();offset=m['allocation']['offset'];size=m['allocation']['size'];old=bytearray(a);old[offset:offset+size]=b'\xff'*size
assert hashlib.sha256(old).hexdigest()=='4da5caf8e6aedf78182b13e75829931398dfb61aee7b7f5f45cd6ec324a33c16'
restored=bytearray(b);restored[0x53DF7C:0x53DF80]=a[0x53DF7C:0x53DF80];assert bytes(restored)==a
before=_lz77(a,m['edit']['before_pointer']);after=_lz77(b,m['edit']['after_pointer']);assert len(before)==len(after)==32;assert before[:2]==after[:2] and before[4:]==after[4:];assert int.from_bytes(after[2:4],'little')==int.from_bytes(before[2:4],'little')^31
assert offset>=0xBA0000 and offset+size<=0xBB0000
for v in ['baseline','candidate']:assert hashlib.sha256((r/'build'/m['variants'][v]['rom_path']).read_bytes()).hexdigest()==m['variants'][v]['rom_sha256']
result={'verified':True,'independent_decoder':'tools.verify_cutscene_obj_primary_ptr_ab._lz77','original_parent_reconstructed_by_restoring_only_new_allocation':True,'candidate_reconstructs_baseline_by_restoring_only_pointer_field':True,'decompressed_palette_bytes':32,'only_color_index_1_changed':True,'registered_region':'cutscene-obj-bundle','allocation_range':[offset,offset+size],'source_and_variant_hashes':{v:m['variants'][v]['rom_sha256'] for v in ['baseline','candidate']},'runtime_verified':False}
assert result==json.loads((r/'raw-build-verification.json').read_text())
(r/'raw-build-verification-repeated.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print('independent raw build repeated identically')
