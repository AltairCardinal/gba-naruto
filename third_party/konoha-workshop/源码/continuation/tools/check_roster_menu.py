from pathlib import Path
import os,json
R=Path(__file__).resolve().parents[2]
os.environ['NARUTO_REPLAY_NAME']='roster_menu_inspect_02'
os.environ['NARUTO_REPLAY_ROM']=str(R/'continuation/build/naruto_restart_v041_SKILLS01.gba')
ns={'__file__':str(R/'continuation/tools/play_campaign.py')}
exec((R/'continuation/tools/play_campaign.py').read_text().split('q=Player();report=')[0],ns)
q=ns['Player']();out=ns['out']
try:
 q.boot()
 for _ in range(180):
  if q.read(0x20311ea,1)[0]==56 and q.read(0x20311ec,1)[0]==1:break
  q.key(1,100)
 q.shot('briefing');q.key(1);q.shot('menu');q.key(1,100);q.shot('party_menu')
 print('formation',list(q.read(0x2024045,3)),flush=True)
 print('party',[(n,q.read(0x2022e34+n*188,2).hex())for n in range(1,24)if q.read(0x2022e34+n*188,1)[0]],flush=True)
 q.p.command('state '+str(out/'menu.state'))
finally:q.p.close()
