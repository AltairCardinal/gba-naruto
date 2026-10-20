"""Cold boot, real menus and RAM reads only: fixed actor versus native team slot."""
from pathlib import Path
import os,json,hashlib
ROOT=Path(__file__).resolve().parents[2]
ROM=Path(os.environ['NARUTO_ROSTER_ROM'])
os.environ['NARUTO_REPLAY_ROM']=str(ROM)
os.environ['NARUTO_REPLAY_NAME']=os.environ['NARUTO_ROSTER_NAME']
ns={'__file__':str(ROOT/'continuation/tools/play_campaign.py')}
exec((ROOT/'continuation/tools/play_campaign.py').read_text().split('q=Player();report=')[0],ns)
q=ns['Player']();out=ns['out'];mode=os.environ['NARUTO_ROSTER_MODE']
try:
 q.boot();q.start(56)
 formation=list(q.read(0x2024045,3))
 team=[q.read(0x2022e34+n*188,1)[0] if n else 0 for n in formation]
 actors=q.units();friendly=[a for a in actors if not a['side']]
 assert friendly[0]['id']==(team[0] if mode=='team' else 2)
 assert all(41 not in a['skills'] for a in actors)
 if mode=='team':assert 19 not in friendly[0]['skills'],'Fixed Sasuke loadout leaked into the selected team member'
 data=q.read(0x203e900,87*16);native=(ROOT/'build/naruto_role_swap_v0.1.5_EXPERIMENTAL.gba').read_bytes()[0x545458:0x545458+87*16]
 assert data[41*16:42*16]==native[41*16:42*16]
 q.shot('03_deployed_actors');q.cursor(friendly[0]['x'],friendly[0]['y']);q.key(1);q.key(128);q.key(1);q.shot('04_actual_attack_menu')
 trace=(out/'commands_01.log').read_text().splitlines()
 forbidden=[s for s in trace if s.split()[0] in ['w8','w16','w32','call','reg','loadstate']]
 assert not forbidden
 result={'result':'pass','kind':'cold boot; actual key input; RAM reads only','mode':mode,'rom_sha256':hashlib.sha256(ROM.read_bytes()).hexdigest(),'current_team':team,'deployed':actors,'native_whirlwind_data_restored':True,'forbidden_mutating_commands':forbidden}
 (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
finally:q.p.close()
