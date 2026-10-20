"""Cold start, win the first battle and escape the second using actual keys only."""
from pathlib import Path
import os,json,hashlib
R=Path(__file__).resolve().parents[2];rom=Path(os.environ['NARUTO_ESCAPE_ROM']);label=os.environ.get('NARUTO_ESCAPE_CASE','escape02_restart_actual');mode=os.environ.get('NARUTO_ESCAPE_MODE','flee')
os.environ['NARUTO_REPLAY_ROM']=str(rom);os.environ['NARUTO_REPLAY_NAME']=label
if os.environ.get('NARUTO_ESCAPE_SAVE'):os.environ['NARUTO_REPLAY_SAVE']=os.environ['NARUTO_ESCAPE_SAVE']
else:os.environ.pop('NARUTO_REPLAY_SAVE',None)
ns={'__file__':str(R/'continuation/tools/play_campaign.py')};exec((R/'continuation/tools/play_campaign.py').read_text().split('q=Player();report=')[0],ns)
q=ns['Player']();out=ns['out'];report={'rom_sha256':hashlib.sha256(rom.read_bytes()).hexdigest(),'kind':'cold boot actual title and battle keys; RAM reads only; no battle/HP/position injection','mode':mode,'input_save_sha256':hashlib.sha256(Path(os.environ['NARUTO_ESCAPE_SAVE']).read_bytes()).hexdigest()if os.environ.get('NARUTO_ESCAPE_SAVE')else None,'checks':[]}
def check(n,v):
 assert v,n
 report['checks'].append(n);print('PASS',n,flush=True)
def advance(scene,branch=1):
 for _ in range(180):
  if q.read(0x20311ea,1)[0]==scene and q.read(0x20311ec,1)[0]==branch:return
  q.key(1,100)
 raise AssertionError('Scene did not advance '+str(scene))
def next_turn(turn):
 for _ in range(24):
  q.p.frames(600)
  if q.read(0x2026807,1)[0]==2:raise AssertionError('Sakura defeated on escape route')
  if q.read(0x202680c,1)[0]>turn and q.read(0x202680e,1)[0]==0:return
  q.key(1,100)
 raise AssertionError('Enemy phase did not end')
try:
 q.boot()
 if not os.environ.get('NARUTO_ESCAPE_RESUME_SECOND'):
  q.start(56);report['first_initial']=q.units()
  for _ in range(60):
   if not q.alive_enemies()or q.read(0x20311ec,1)[0]!=1:break
   if q.read(0x2026807,1)[0]==2:raise AssertionError('First battle lost')
   if q.read(0x202680e,1)[0]:q.p.frames(600);q.key(1,200);continue
   for a in q.units():
    if not a['side']and not a['flags']&0x70:q.attack_or_approach(a['slot'])
   q.p.frames(400)
  else:raise AssertionError('First battle stalled')
 advance(57);q.start(57);initial=q.units();report['second_initial']=initial;print('SECOND',initial,flush=True)
 check('second battle has Sakura and an overwhelming protected opponent',initial[0]['id']==3 and initial[1]['id']==4 and initial[1]['level']==99 and initial[1]['hp']==999)
 check('escape marker cell is reachable terrain',q.read(0x2021e2c+(11*13+3)*2,1)[0]&15==0)
 q.shot('01_第二关与撤离标记');q.key(8);q.key(128);q.key(128);q.key(1,120);q.shot('02_实际胜负条件');q.key(2);q.key(2)
 if mode=='attack':
  q.action_turn=q.read(0x202680c,1)[0];q.attack(1,2,move=(6,15));q.shot('03_正面攻击无效');enemy=q.actor(2)
  check('actual normal attack cannot reduce the opponents HP',enemy['id']==4 and enemy['hp']==999)
  check('attacking does not advance to battle3',q.read(0x20311ea,1)[0]!=58)
  report['enemy_after_attack']=enemy
 else:
  q.move_wait(1,(3,13));q.shot('03_第一回合向左撤离');check('one square before the exit does not win',q.read(0x2026807,1)[0]==0 and q.read(0x20311ea,1)[0]==57)
  next_turn(1);q.move_wait(1,(3,11));q.p.frames(160);q.shot('04_到达撤离点');report['at_exit']=q.units();report['escape_turn']=q.read(0x202680c,1)[0]
  check('Sakura reaches the marked exit with the opponent alive',q.actor(1)['x']==3 and q.actor(1)['y']==11 and q.actor(2)['id']==4 and q.actor(2)['hp']==999)
  advance(58);q.shot('05_撤离后正常进入第三关');check('escaping advances through native victory and after-story to battle3',q.read(0x20311ea,1)[0]==58 and q.read(0x20311ec,1)[0]==1)
 forbidden=[s for s in(out/'commands_01.log').read_text().splitlines()if s.split()[0]in['w8','w16','w32','call','reg','loadstate']];check('entire replay has no mutating debug commands',not forbidden);report['mutating_debug_commands']=forbidden;report['result']='pass'
except Exception as e:report.update(result='failed',error=str(e));q.shot('FAILED');q.p.command('state '+str(out/'FAILED.state'));raise
finally:q.p.close();(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
