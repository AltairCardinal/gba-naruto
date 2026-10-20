"""Actual UI warm restarts after controlled native defeats, first three stages.

Winning prerequisite battles uses only actual keys. Defeat is a declared fixture:
clear the friendly unit ID, then let the native loss-condition code handle it.
No story variables, pointers, program counters or save data are injected.
"""
from pathlib import Path
import hashlib,json,os
ROOT=Path(__file__).resolve().parents[2]
ns={'__file__':str(ROOT/'continuation/tools/play_campaign.py')}
exec((ROOT/'continuation/tools/play_campaign.py').read_text().split('q=Player();report=')[0],ns)
q=ns['Player']();out=ns['out'];ROM=ns['ROM'];report={'rom_sha256':hashlib.sha256(ROM.read_bytes()).hexdigest(),'kind':'actual title/new-game UI after controlled native defeat; prerequisite victories use actual keys','fixture':'write ID zero to friendly battle units only; no story-state or PC injection','checks':[]}
def win(scene):
 q.start(scene);q.limit=4 if scene==57 else 0
 for _ in range(100):
  if q.read(0x020311ec,1)[0]!=1 or not q.alive_enemies():break
  if q.read(0x0202680e,1)[0]:q.p.frames(600);q.key(1,200);continue
  turn=q.read(0x0202680c,1)[0]
  if q.limit and turn>=q.limit and not any(not a['flags']&0x70 for a in q.units() if not a['side']):q.key(2);break
  for a in q.units():
   if not a['side'] and not a['flags']&0x70:q.attack_or_approach(a['slot'])
  q.p.frames(600)
  if not q.read(0x0202680e,1)[0] and not any(not a['flags']&0x70 for a in q.units() if not a['side']):q.key(1,200)
 else:raise AssertionError('Prerequisite combat stalled')
 for _ in range(120):
  if q.read(0x020311ea,1)[0]==scene+1 and q.read(0x020311ec,1)[0]==1:return
  q.key(1,100)
 raise AssertionError('Prerequisite victory did not advance')
try:
 q.boot()
 for scene in [56,57,58]:
  for earlier in range(56,scene):win(earlier)
  q.start(scene);q.key(8);q.key(128);q.key(128);q.key(1);q.shot(f'{scene}_conditions');q.key(2);q.key(2)
  for a in q.units():
   if not a['side']:q.p.command(f'w8 {0x020240c0+a["slot"]*468:x} 0')
  q.key(8);q.key(1);q.key(64);q.key(1,800);q.shot(f'{scene}_controlled_defeat')
  for _ in range(3):q.key(1,200)
  q.shot(f'{scene}_returned_title');q.key(8,150);q.key(1,180);q.shot(f'{scene}_new_game_selector');q.key(8,300)
  q.shot(f'{scene}_new_game_opening');assert q.read(0x020311ea,1)[0]==56 and q.read(0x020311ec,1)[0]==0,'New game entered the original after-story'
  assert q.read(0x020311ed,3)==bytes(3),'Previous configuration/branch flags survived new game'
  report['checks'].append({'defeated_scene':scene,'new_scene':56,'before_story_branch':True,'result':'pass'})
 report['result']='pass'
except Exception as e:report.update(result='failed',error=str(e));q.shot('FAILED');raise
finally:
 q.p.close();report['mutations']=[s for s in(out/'commands_01.log').read_text().splitlines()if s.split()[0] in ['w8','w16','w32','call','reg','loadstate']];(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(out,flush=True)
