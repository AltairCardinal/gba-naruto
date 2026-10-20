"""Play the ROM produced by the comprehensive editor UI. Keys only, RAM reads."""
from pathlib import Path
import os,json,hashlib,collections,struct
R=Path(__file__).resolve().parents[2]
rom=Path(os.environ.get('NARUTO_EDITOR_GAMEPLAY_ROM',R/'continuation/evidence/editor_full_v044/workflow/综合演习_导出.gba'))
os.environ['NARUTO_REPLAY_ROM']=str(rom);os.environ['NARUTO_REPLAY_NAME']=os.environ.get('NARUTO_EDITOR_GAMEPLAY_OUT','editor_full_v044_gameplay')
ns={'__file__':str(R/'continuation/tools/play_campaign.py')};exec((R/'continuation/tools/play_campaign.py').read_text().split('q=Player();report=')[0],ns)
Base=ns['Player'];out=ns['out'];report={'rom_sha256':hashlib.sha256(rom.read_bytes()).hexdigest(),'kind':'editor-generated ROM; cold boot, actual keys, RAM reads only','checks':[]}
class Player(Base):
 def __init__(self):super().__init__();self.draining=False;self.seen=set();self.dialogue_events=[]
 def key(self,k,wait=60):
  super().key(k,wait)
  if not self.draining:self.drain()
 def drain(self):
  self.draining=True
  try:
   for _ in range(30):
    count,index=self.read(0x20311ef,2)
    if not count or index>=count:return
    self.p.frames(200);count,index=self.read(0x20311ef,2)
    if not count or index>=count:return
    t=self.read(0x202680c,1)[0];phase=self.read(0x202680e,1)[0];eid=self.read(0x20311f1+index,1)[0];key=(t,phase,index,eid)
    if key not in self.seen:self.seen.add(key);self.dialogue_events.append({'turn':t,'phase':phase,'event_id':eid});self.shot(f'event_{t}_{phase}_{eid}')
    self.p.press(1);self.p.frames(160)
   raise AssertionError('Event did not finish')
  finally:self.draining=False
 def enemies(self,previous):
  for _ in range(24):
   self.p.frames(600);self.drain()
   if self.read(0x20311ec,1)[0]!=1:return
   if self.read(0x202680c,1)[0]>previous and not self.read(0x202680e,1)[0]:return
   self.key(1,100)
  raise AssertionError('Enemy phase stalled')
q=Player()
def check(n,v):
 assert v,n
 report['checks'].append(n);print('PASS',n,flush=True)
try:
 q.boot();q.shot('01_导入头像与长对白');q.start(56);q.shot('02_地图人物与物品')
 initial=q.units();report['initial']=initial;print('INITIAL',initial,flush=True)
 check('edited ally Lee actually spawns in battle',initial[0]['id']==12 and initial[0]['level']==3 and (initial[0]['x'],initial[0]['y'])==(6,13))
 check('edited enemy spawns at new position',initial[1]['y']==16)
 check('obstacle and passable imported tile are loaded by native game',q.read(0x2021e2c+(15*13+6)*2,1)[0]&15==7 and q.read(0x2021e2c+(13*13+5)*2,1)[0]&15==0)
 objects_before=q.read(0x2026604,512);report['objects_before']=objects_before.hex();item_slots=[i for i in range(32)if objects_before[i*16] and objects_before[i*16+1:i*16+3]==bytes([5,13]) and objects_before[i*16+4]==1 and int.from_bytes(objects_before[i*16+6:i*16+8],'little')==1];check('native item is present at placed cell',len(item_slots)==1);item_slot=item_slots[0]
 q.key(8);q.key(128);q.key(128);q.key(1,150);q.shot('03_自定义胜负条件');q.key(2);q.key(2)
 a=q.actor(1);q.cursor(a['x'],a['y']);q.key(1);q.key(1);reach=q.read(0x202ca27,13*26*2);check('blocked tile excluded from native movement range',reach[(15*13+6)*2]==255);q.key(2);q.key(2)
 q.move_wait(1,(5,13));q.shot('04_拾取忍具');objects_after=q.read(0x2026604,512);report['objects_after']=objects_after.hex();check('item disappears after moving to its cell',objects_after[item_slot*16]==0)
 check('one-time opening event fires exactly once',[e['event_id']for e in q.dialogue_events]==[1]);q.key(2,120)
 for i in range(100):
  if q.read(0x20311ea,1)[0]==57:break
  q.key(2 if i%4==3 else 1,120)
  if i<12:q.shot(f'07_战后对白_{i:02}')
 else:raise AssertionError('No progress to next battle')
 check('edited mission wins and advances to battle57',True);report['dialogue_events']=q.dialogue_events
 forbidden=[s for s in (out/'commands_01.log').read_text().splitlines()if s.split()[0]in['w8','w16','w32','call','reg','loadstate']];check('gameplay uses no mutating debug commands',not forbidden);report['mutating_debug_commands']=forbidden;report['result']='pass'
except Exception as e:report.update(result='failed',error=str(e),dialogue_events=q.dialogue_events);q.shot('FAILED');q.p.command(f'state {out/"FAILED.state"}');raise
finally:(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));q.p.close()
