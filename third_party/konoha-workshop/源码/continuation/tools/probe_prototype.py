from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'));import validate_candidate as v
v.OUT=ROOT/'continuation/evidence/prototype_01';v.OUT.mkdir(exist_ok=True);p=v.Probe(ROOT/'continuation/build/naruto_continuation_PROTOTYPE.gba')
read=lambda a,n:bytes.fromhex(p.command(f'read {a:x} {n:x}'))
def key(k,wait=100):p.press(k);p.frames(wait)
try:
 p.frames(950);key(8,100);key(1,180);key(8,250)
 p.command(f'shot {v.OUT/"01_opening.png"}')
 for i in range(28):
  print(i,read(0x20311d4,0x1c).hex(),flush=True)
  if read(0x20311ec,1)[0]==1:break
  key(1,100)
 p.command(f'shot {v.OUT/"02_briefing.png"}')
 key(1);key(128);key(128);key(1);key(1,400)
 for _ in range(8):
  if read(0x202680c,1)[0]>0:break
  key(1,150)
 p.frames(180);p.command(f'shot {v.OUT/"03_battle.png"}');p.command(f'state {v.OUT/"battle.state"}')
 print('runtime',read(0x2026804,16).hex());print('actors',[(i,read(0x20240c0+i*468,16).hex())for i in range(1,5)]);print('party',[(i,read(0x2022e34+i*188,4).hex())for i in range(1,24)]);p.command(f'savecopy {v.OUT/"current.sav"}')
finally:p.close()
