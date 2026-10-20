"""Declared native-rule, maximum-damage and knockout-prevention fixtures."""
from pathlib import Path
import os,json,hashlib
R=Path(__file__).resolve().parents[2];rom=Path(os.environ['NARUTO_ESCAPE_ROM']);name=os.environ.get('NARUTO_ESCAPE_FIXTURE','escape03_restart_rules_fixture')
os.environ['NARUTO_REPLAY_ROM']=str(rom);os.environ['NARUTO_REPLAY_NAME']=name;os.environ.pop('NARUTO_REPLAY_SAVE',None)
if os.environ.get('NARUTO_ESCAPE_SAVE'):os.environ['NARUTO_REPLAY_SAVE']=os.environ['NARUTO_ESCAPE_SAVE']
ns={'__file__':str(R/'continuation/tools/play_campaign.py')};exec((R/'continuation/tools/play_campaign.py').read_text().split('q=Player();report=')[0],ns)
q=ns['Player']();out=ns['out'];syms={p[2]:int(p[0],16)for line in Path(str(rom)+'.symbols.txt').read_text().splitlines()if len(p:=line.split())==3};layout=json.loads(Path(str(rom)+'.layout.json').read_text())['layout'];report={'rom_sha256':hashlib.sha256(rom.read_bytes()).hexdigest(),'kind':'controlled scene/configuration/HP/position/turn fixtures using native constructors and compiled runtime functions; NOT natural gameplay','checks':[]}
def check(n,v):
 assert v,n
 print('PASS',n,flush=True);report['checks'].append(n)
def call(name,*args):return q.p.call(syms[name]&~1,*args)
try:
 q.boot();q.start(56)
 for addr,value in [(0x20311ea,57),(0x20311ed,0),(0x2026805,57),(0x2026806,0),(0x2026807,0)]:q.p.write(addr,value)
 q.p.call(0x806a99c);q.p.call(0x806e1b4);call('campaign_protection_setup');q.p.write(0x2026804,1)
 ally=0x20240c0+468;enemy=0x20240c0+2*468;rule=0x8000000+layout['rules']+57*0xcc+4;exit_x,exit_y=q.read(rule+2,2);report['exit']=[exit_x,exit_y]
 check('real stage57 constructor produces protected Ino',q.actor(2)['id']==4 and q.actor(2)['hp']==999)
 for sub in range(3):
  q.p.write(0x2026806,sub)
  check('protection is active in configuration '+str(sub+1),all(call('campaign_guard_damage',enemy,d)==0 for d in [1,999,65535]))
  check('Sakura receives no unintended invulnerability in configuration '+str(sub+1),call('campaign_guard_damage',ally,999)==999)
 q.p.write(0x2026806,0)
 for turn in [4,20,99]:
  q.p.write(0x202680c,turn)
  check('waiting until turn '+str(turn)+' cannot satisfy the native win conditions',q.p.call(0x80777fc,1)==0)
 for a,v in [(enemy+196,exit_x),(enemy+197,exit_y),(enemy+192,17)]:q.p.write(a,v)
 check('enemy reaching exit cannot win for Sakura',call('campaign_arrived',rule)==0)
 for a,v in [(ally+196,exit_x),(ally+197,exit_y),(ally+192,0)]:q.p.write(a,v)
 check('Sakura must finish her action at the exit',call('campaign_arrived',rule)==0)
 q.p.write(ally+192,16);check('live Sakura after ending action satisfies arrival',call('campaign_arrived',rule)==1)
 q.p.command(f'w16 {ally+12:x} 0');check('defeated Sakura cannot trigger escape',call('campaign_arrived',rule)==0)
 q.p.command(f'w16 {enemy+12:x} 0');call('campaign_remove',2,1,0);check('even a fatal removal request leaves the pursuer alive',q.actor(2)['id']==4 and q.actor(2)['hp']==999)
 q.p.write(0x2026805,58);check('protection does not leak into the following battle',call('campaign_guard_damage',enemy,999)==999)
 q.p.write(0x2026805,57);q.p.write(0x2026807,1);check('protection is disabled after battle completion for native cleanup',call('campaign_guard_damage',enemy,999)==999)
 report['result']='pass'
except Exception as e:report.update(result='failed',error=str(e));q.shot('FAILED');raise
finally:q.p.close();(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
