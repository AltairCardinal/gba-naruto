from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'));import validate_candidate as v
v.OUT=ROOT/'continuation/evidence/confirm_target_01';v.OUT.mkdir(exist_ok=True);p=v.Probe(ROOT/'continuation/build/naruto_continuation_PROTOTYPE.gba');p.load(ROOT/'continuation/evidence/prototype_combat_05/FAILED.state')
try:
 for i in range(7):
  p.press(1);p.frames(250);p.command(f'shot {v.OUT/str(i)}.png');print(i,p.command('read 02024294 10'),p.command('read 02024468 10'),p.command('read 0202680c 4'),flush=True)
finally:p.close()
