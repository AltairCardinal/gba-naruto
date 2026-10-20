from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'));import validate_candidate as v
import validate_editor_mission as game
out=ROOT/'continuation/evidence/prototype_combat_09';out.mkdir(exist_ok=True);v.OUT=out;game.out=out;game.ROM=ROOT/'continuation/build/naruto_continuation_PROTOTYPE.gba'
class Player(game.Player):
 def alive_enemies(self):return [a for i in[2]if(a:=self.actor(i))['id']]
q=Player();p=q.p
try:
 p.frames(950);q.key(8,100);q.key(1,180);q.key(8,250)
 for i in range(28):
  if q.read(0x20311ec,1)[0]==1:break
  q.key(1,100)
 q.key(1);q.key(128);q.key(128);q.key(1);q.key(1,400)
 for _ in range(8):
  if q.read(0x202680c,1)[0]>0:break
  q.key(1,150)
 p.frames(350)
 for turn in range(1,10):
  q.attack(1,2);print(turn,q.actor(1),q.actor(2),flush=True)
  q.shot(f'turn{turn}')
  if not q.alive_enemies():break
  q.enemy_phase(turn)
 for i in range(45):
  q.key(1,200)
  if q.read(0x20311ea,1)[0]==54:break
 q.shot('ending');print('scene',q.read(0x20311d4,32).hex(),flush=True)
 p.command(f'savecopy {out/"completed.sav"}')
 (out/'result.json').write_text(json.dumps({'scene':q.read(0x20311ea,1)[0],'turns':turn,'party':q.read(0x2022e34+188,16).hex()}))
except Exception as e:
 q.shot('FAILED');p.command(f'state {out/"FAILED.state"}');(out/'failure.json').write_text(json.dumps({'result':'failed','error':str(e)}));raise
finally:p.close()
