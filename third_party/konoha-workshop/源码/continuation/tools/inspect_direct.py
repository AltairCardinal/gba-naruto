from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'));import validate_candidate as v
v.OUT=ROOT/'continuation/evidence/menu_02';v.OUT.mkdir(exist_ok=True);p=v.Probe(ROOT/'continuation/build/naruto_continuation_PROTOTYPE.gba');p.load(ROOT/'continuation/evidence/prototype_01/battle.state')
try:
 for i,k in enumerate([1,128,128,1]):
  p.press(k);p.frames(80);p.command(f'shot {v.OUT/str(i)}.png');print(i,p.command('read 02026a78 2'),flush=True)
finally:p.close()
