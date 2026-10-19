from pathlib import Path
import hashlib,json,sys
root=Path.cwd().resolve();sys.path.insert(0,str(root))
from tools.inspect_mgba_savestate import load_gba_state
from tools.verify_menu_portrait_pixel_ab_evidence import DOMAINS,_diff,_rgb,_pixel_changes
p=root/'notes/evidence/rom-menu-gfx-pointer-ab-20261001-v1/source'
a=load_gba_state(p/'runtime/input-baseline/frame80.ss9');b=load_gba_state(p/'runtime/input-candidate/frame80.ss9')
x=_rgb(p/'runtime/input-baseline/frame80.png');y=_rgb(p/'runtime/input-candidate/frame80.png')
r={'version_magic':hex(a.version_magic),'memory_differences':{n:_diff(a.read_memory(addr,size),b.read_memory(addr,size)) for n,(addr,size) in DOMAINS.items()},'pixel_changes':_pixel_changes(x,y),'baseline_rgb_sha256':hashlib.sha256(x).hexdigest(),'candidate_rgb_sha256':hashlib.sha256(y).hexdigest()}
(root/'build/experiments/active/menu-portrait-pointer-ab/contract-20261001-v1/observation.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
print(json.dumps(r))
