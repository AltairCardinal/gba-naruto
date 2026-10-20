"""Play into a browser-created battle and inspect its narration transitions."""
from pathlib import Path
import hashlib,json,os
ROOT=Path(__file__).resolve().parents[2]
os.environ['NARUTO_REPLAY_ROM']=os.environ.get('NARUTO_EXPORT_ROM',str(ROOT/'continuation/evidence/opening_portrait_ui/narration_export.gba'))
os.environ['NARUTO_REPLAY_NAME']=os.environ.get('NARUTO_EXPORT_TEST_NAME','opening_portrait_export_runtime')
ns={'__file__':str(ROOT/'continuation/tools/play_campaign.py')}
exec((ROOT/'continuation/tools/play_campaign.py').read_text().split('q=Player();report=')[0],ns)
q=ns['Player']();out=ns['out'];report={'kind':'cold boot actual keys; RAM reads only','rom_sha256':hashlib.sha256(ns['ROM'].read_bytes()).hexdigest()}
try:
 q.boot();q.start(56)
 for _ in range(40):
  if not q.alive_enemies():break
  if q.read(0x0202680e,1)[0]:q.p.frames(600);q.key(1,200);continue
  for a in q.units():
   if not a['side'] and not a['flags']&0x70:q.attack_or_approach(a['slot'])
  q.key(1,200)
 assert not q.alive_enemies()
 for _ in range(120):
  if q.read(0x020311ea,1)[0]==82:break
  q.key(1,150)
 else:raise AssertionError('Browser-created battle did not begin')
 q.p.frames(300);report['pages']=[]
 for i,speaker in enumerate([0,7,0]):
  assert q.read(0x020311ec,1)[0]==0
  ptr=int.from_bytes(q.read(0x03005e50,4),'little');state=q.read(ptr+0x2c,1)[0] if ptr else None
  assert state in ([None,48] if not speaker else [16]),(i,state)
  q.shot(f'new_battle_page_{i:02}');report['pages'].append({'speaker':speaker,'portrait_state':state});q.key(1,300)
 assert q.read(0x020311ec,1)[0]==1;q.start(82);q.shot('new_battle_started');report['result']='pass'
except Exception as e:report.update(result='failed',error=str(e));q.shot('FAILED');raise
finally:
 q.p.close();report['mutating_debug_commands']=[s for s in(out/'commands_01.log').read_text().splitlines()if s.split()[0] in ['w8','w16','w32','call','reg','loadstate']];assert not report['mutating_debug_commands'];(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(out,flush=True)
