"""Positive signed-branch canaries for reused independent scan primitives."""
import sys,json
from pathlib import Path
root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root))
from tools.verify_rom_prebattle_menu_controller_cfg import _direct_target
from tools.verify_rom_boot_interwork import _arm_b_target, _scan_direct_producers, ROOT_OFFSET
for word,expected in [(0xe7fe,(0,'b',2)),(0xd1fe,(0,'bcond',2)),(0xd000,(4,'bcond',2)),(0xdf00,None),(0xde00,None)]:
 assert _direct_target(word.to_bytes(2,'little'),0)==expected
for word,expected in [(0xea000000,8),(0xeb000000,8),(0xeafffffe,0),(0xebfffffe,0)]:
 assert _arm_b_target((word&~(1<<24)).to_bytes(4,'little'),0)==expected
encoded=(ROOT_OFFSET-8)//4
assert _scan_direct_producers((0xea000000|encoded).to_bytes(4,"little"))==([],[0])
assert _scan_direct_producers((0xfa000000|encoded).to_bytes(4,"little"))==([],[])
print(json.dumps({'schema':'rom-ai-producer-decoder-canary-v1','verified':True,'thumb_cases':5,'arm_b_bl_target_cases':4,'nv_vs_al_scan_cases':2,'promotion_bytes':0},sort_keys=True))
