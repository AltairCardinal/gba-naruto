"""Native battle suspension, process exit, cold resume; actual keys/read-only RAM."""
from pathlib import Path
import os,json,hashlib
R=Path(__file__).resolve().parents[2];ROM=R/'continuation/build/naruto_restart_v040_RC9.gba';os.environ['NARUTO_REPLAY_ROM']=str(ROM);os.environ['NARUTO_REPLAY_NAME']='save_suspend_rc9_03'
os.environ['NARUTO_REPLAY_SAVE']=str(R/'continuation/evidence/save_resume_restart_rc9_01/ordinary_save.sav')
ns={'__file__':str(R/'continuation/tools/play_campaign.py')};exec((R/'continuation/tools/play_campaign.py').read_text().split('q=Player();report=')[0],ns);out=ns['out'];save=out/'suspend.sav';q=ns['Player']()
try:
 q.boot();q.start(56);before=[{k:a[k]for k in['id','level','hp','x','y','side']}for a in q.units()];q.key(8)
 for _ in range(3):q.key(128)
 q.key(1,180);q.shot('01_suspend_confirmation');q.key(64);q.key(1,500);q.shot('02_suspended');q.p.command('savecopy '+str(save))
finally:q.p.close()
os.environ['NARUTO_REPLAY_SAVE']=str(save);q=ns['Player']()
try:
 q.p.frames(950);q.key(8,100);q.shot('03_cold_mainmenu');q.key(128);q.key(1,120);q.key(1,120);q.key(1,300);q.p.frames(300);q.shot('03_cold_resume');after=[{k:a[k]for k in['id','level','hp','x','y','side']}for a in q.units()];assert before==after,(before,after);assert q.read(0x2026805,1)[0]==56 and q.read(0x202680c,1)[0]==1;assert q.read(0x203e900+41*16,16)[4]==25;assert any(q.read(0x203e800,256));r={'result':'pass','kind':'native suspend menu, emulator closed, new process cold resumes the SAV; actual keys and read-only RAM','rom_sha256':hashlib.sha256(ROM.read_bytes()).hexdigest(),'saved_sav_sha256':hashlib.sha256(save.read_bytes()).hexdigest(),'battle_units_identical':True,'name_and_skill_tables_initialized':True,'instant_state_loading':False};(out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False),flush=True)
finally:q.p.close()
