"""Actual-key campaign replay. No RAM writes, function calls or state injection."""
from pathlib import Path
import sys,os,json,collections,struct,hashlib
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'));import validate_candidate as v
os.environ['NARUTO_HELPER_NO_OUTPUT']='1'
import validate_editor_mission as game
ROM=Path(os.environ.get('NARUTO_REPLAY_ROM',ROOT/'continuation/build/naruto_restart_ALPHA02.gba'))
out=ROOT/'continuation/evidence'/os.environ.get('NARUTO_REPLAY_NAME','restart_alpha02_01');out.mkdir();v.OUT=out;game.out=out;game.ROM=ROM
class Player(game.Player):
 def __init__(self):self.p=v.Probe(ROM,Path(os.environ['NARUTO_REPLAY_SAVE'])if os.environ.get('NARUTO_REPLAY_SAVE')else None);self.events=[]
 def actor(self,i):
  b=self.read(0x20240c0+i*468,468);return{'slot':i,'id':b[0],'level':b[1],'side':b[204],'hp':int.from_bytes(b[12:14],'little'),'x':b[196],'y':b[197],'flags':int.from_bytes(b[192:196],'little'),'skills':[b[20+j*4]for j in range(15)if b[20+j*4]and b[21+j*4]]}
 def units(self):return[a for i in range(1,13)if(a:=self.actor(i))['id']]
 def alive_enemies(self):return[a for a in self.units()if a['side']==1]
 def cursor(self,x,y):
  directions=[(16,32,1,0),(32,16,-1,0),(128,64,0,1),(64,128,0,-1)]
  start=tuple(self.read(0x2026a78,2));seen={start};stack=[[start,sorted(directions,key=lambda d:abs(start[0]+d[2]-x)+abs(start[1]+d[3]-y)),None]]
  for _ in range(1200):
   pos,choices,back=stack[-1]
   if pos==(x,y):return
   if not choices:
    stack.pop()
    if not stack:break
    self.key(back,25);continue
   key,inverse,dx,dy=choices.pop(0);self.key(key,25);now=tuple(self.read(0x2026a78,2))
   if now==pos:continue
   if now in seen:self.key(inverse,25);continue
   seen.add(now);stack.append([now,sorted(directions,key=lambda d:abs(now[0]+d[2]-x)+abs(now[1]+d[3]-y)),inverse])
  raise AssertionError(f'Cursor cannot reach {(x,y)} from {start}')
 def finish(self,slot):
  for _ in range(18):
   if not self.alive_enemies() or self.read(0x202680e,1)[0] or self.read(0x20311ec,1)[0]!=1 or self.read(0x202680c,1)[0]>self.action_turn:return
   if self.actor(slot)['flags']&0x10:
    self.key(1,200);self.key(1,200)
    for _ in range(4):self.key(2,30)
    return
   self.key(1,180)
  raise AssertionError('Action did not finish')
 def move_wait(self,slot,xy):
  self.action_turn=self.read(0x202680c,1)[0];return super().move_wait(slot,xy)
 def choices(self,slot):
  a=self.actor(slot);w,h=self.read(0x201be2a,2);tiles=struct.unpack('<'+'H'*(w*h),self.read(0x2021e2c,w*h*2));occupied={(b['x'],b['y'])for b in self.units()if b['slot']!=slot};queue=collections.deque([((a['x'],a['y']),0)]);seen={(a['x'],a['y'])};res=[]
  while queue:
   (x,y),cost=queue.popleft();res.append((x,y,cost))
   if cost>=3:continue
   for nx,ny in[(x+1,y),(x-1,y),(x,y+1),(x,y-1)]:
    if 0<=nx<w and 0<=ny<h and(nx,ny)not in seen and(nx,ny)not in occupied and tiles[ny*w+nx]&15 not in[7,15]and not tiles[ny*w+nx]&64:seen.add((nx,ny));queue.append(((nx,ny),cost+1))
  return res
 def attack_or_approach(self,slot):
  self.action_turn=self.read(0x202680c,1)[0]
  for _ in range(4):self.key(2,20)
  a=self.actor(slot);enemies=self.alive_enemies();enemies=[e for e in enemies if not e['flags']&0xa0]or enemies
  self.cursor(a['x'],a['y']);self.key(1);self.key(1)
  w,h=self.read(0x201be2a,2);native=self.read(0x202ca27,w*h*2);terrain=struct.unpack('<'+'H'*(w*h),self.read(0x2021e2c,w*h*2));occupied={(u['x'],u['y'])for u in self.units()if u['slot']!=slot}
  cells=[(x,y,native[(y*w+x)*2])for y in range(h)for x in range(w)if native[(y*w+x)*2]!=255 and terrain[y*w+x]&15==0 and(x,y)not in occupied and((x,y)==(a['x'],a['y'])or(1<=x<w-1 and 4<=y<h-3))]
  assert cells,'No native reachable cells'
  distances={};routes=collections.deque()
  for e in enemies:
   distances[(e['x'],e['y'])]=0;routes.append((e['x'],e['y']))
  while routes:
   x,y=routes.popleft()
   for nx,ny in[(x+1,y),(x-1,y),(x,y+1),(x,y-1)]:
    if 0<=nx<w and 4<=ny<h-3 and terrain[ny*w+nx]&15==0 and(nx,ny)not in distances:
     distances[(nx,ny)]=distances[(x,y)]+1;routes.append((nx,ny))
  hits=[(cost,e,(x,y))for x,y,cost in cells for e in enemies if abs(x-e['x'])+abs(y-e['y'])==1]
  if getattr(self,'limit',0) or (a['id']==47 and a['hp']<=40):
   x,y,_=max(cells,key=lambda p:(min(abs(p[0]-e['x'])+abs(p[1]-e['y'])for e in enemies),-p[2]));move=(x,y);target=None
  elif hits:_,target,move=min(hits,key=lambda p:(p[1]['hp'],p[0]))
  else:
   x,y,_=min(cells,key=lambda p:(distances.get((p[0],p[1]),999),p[2]));move=(x,y);target=None
  if move!=(a['x'],a['y']):
   self.cursor(*move);self.key(1,200)
   if target:self.key(1)
   else:self.key(64);self.key(1);self.key(1,800);self.finish(slot);return
  else:
   self.key(2)
   if target:self.key(128);self.key(1)
   else:self.key(64);self.key(1);self.key(1,800);self.finish(slot);return
  menu=self.read(0x2026a8c,100);ids=[menu[1+i*6]for i in range(menu[0])];wanted=next((s for s in (5,41,64,79,81) if s in ids),None);assert wanted is not None,ids
  for _ in range(ids.index(wanted)):self.key(128)
  self.key(1);target=self.actor(target['slot']);self.cursor(target['x'],target['y']);self.key(1);self.key(1,1000);self.finish(slot)
 def boot(self):
  self.p.frames(950);self.key(8,100)
  if os.environ.get('NARUTO_REPLAY_SAVE'):
   for wait in[90,30,90,250]:self.key(1,wait)
  else:self.key(1,180);self.key(8,250)
 def start(self,scene):
  for _ in range(180):
   if self.read(0x20311ea,1)[0]==scene and self.read(0x20311ec,1)[0]==1:break
   self.key(1,100)
  else:raise AssertionError('Story not ready '+str(scene))
  self.shot(f'{scene}_briefing');
  if str(scene)==os.environ.get('NARUTO_REPLAY_PAUSE_SCENE'):self.p.frames(int(os.environ.get('NARUTO_REPLAY_PAUSE_FRAMES','0')))
  self.key(1);self.key(128);self.key(128);self.key(1);self.key(1,400)
  for _ in range(30):
   if self.read(0x2026805,1)[0]==scene and self.read(0x202680c,1)[0]>0:break
   self.key(1,150)
  self.p.frames(250);assert self.read(0x2026805,1)[0]==scene;self.shot(f'{scene}_turn1')
q=Player();report={'rom_sha256':hashlib.sha256(ROM.read_bytes()).hexdigest(),'kind':'cold boot actual keys; RAM reads only','input_sav_sha256':hashlib.sha256(Path(os.environ['NARUTO_REPLAY_SAVE']).read_bytes()).hexdigest()if os.environ.get('NARUTO_REPLAY_SAVE')else None,'input_pause':{'scene':os.environ.get('NARUTO_REPLAY_PAUSE_SCENE'),'frames':os.environ.get('NARUTO_REPLAY_PAUSE_FRAMES')},'battles':[],'not_run':['hardware','all role substitutions','all optional paths']}
try:
 q.boot()
 for scene in range(int(os.environ.get('NARUTO_REPLAY_FIRST','56')),int(os.environ.get('NARUTO_REPLAY_LAST','81'))+1):
  q.start(scene);initial=q.units();print('START',scene,initial,flush=True)
  for step in range(100):
   if q.read(0x20311ec,1)[0]!=1:break
   if not q.alive_enemies():break
   allies=[a for a in q.units()if not a['side']]
   if not allies:raise AssertionError('All allies lost')
   turn=q.read(0x202680c,1)[0];phase=q.read(0x202680e,1)[0]
   campaign=json.loads(Path(str(ROM)+'.layout.json').read_text())if Path(str(ROM)+'.layout.json').exists()else None
   limit=next((b.get('turnLimit',0)for b in campaign['chapters']if b['id']==scene),0)if campaign else 0
   q.limit=limit
   if limit and turn>=limit and not any(not a['flags']&0x70 for a in allies):q.key(2,60);break
   if phase:q.p.frames(600);q.key(1,200);continue
   for a in allies:
    if q.read(0x2026805,1)[0]!=scene or q.read(0x202680e,1)[0] or q.read(0x202680c,1)[0]!=turn or not q.alive_enemies():break
    if q.actor(a['slot'])['id']and not q.actor(a['slot'])['flags']&0x70:q.attack_or_approach(a['slot'])
   if q.read(0x202680c,1)[0]>=20:raise AssertionError('Battle exceeded 20 turns')
   if q.read(0x20311ec,1)[0]!=1:break
   q.p.frames(600)
   if not q.read(0x202680e,1)[0]and not any(not a['flags']&0x70 for a in q.units()if not a['side']):q.key(1,200)
  else:raise AssertionError('Combat stalled')
  q.shot(f'{scene}_result');turn=q.read(0x202680c,1)[0];entry={'scene':scene,'turns':turn,'initial':initial,'final':q.units()};report['battles'].append(entry);print('END',scene,turn,flush=True)
  # Dismiss real results and story; stop when the following battle is ready.
  next_scene=scene+1 if scene<int(os.environ.get('NARUTO_REPLAY_CAMPAIGN_LAST','81')) else 54
  for _ in range(180):
   if q.read(0x20311ea,1)[0]==next_scene and (next_scene==54 or q.read(0x20311ec,1)[0]==1):break
   q.key(2 if _%4==3 else 1,100)
  else:raise AssertionError('Next scene did not begin '+str(scene))
  q.p.command(f'savecopy {out/f"after_{scene}.sav"}')
 
 if int(os.environ.get('NARUTO_REPLAY_LAST','81'))==81:
  q.p.frames(240);assert q.read(0x20311ea,1)[0]==54;assert int.from_bytes(q.read(0x20311e4,2),'little')==385;assert q.read(0x203150f,1)[0]&128;report['final_progress']=385;report['completion_flag_restored']=True
 report['result']='pass';q.shot('ending');(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
except Exception as e:
 report.update(result='failed',error=str(e));q.shot('FAILED');q.p.command(f'state {out/"FAILED.state"}');(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));raise
finally:q.p.close()
