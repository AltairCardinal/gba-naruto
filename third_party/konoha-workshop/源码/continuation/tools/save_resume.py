"""In-game ordinary save, close emulator, cold continue; no state loads or RAM writes."""
from pathlib import Path
import os,json,hashlib
ROOT=Path(__file__).resolve().parents[2]
ROM=Path(os.environ.get('NARUTO_SAVE_ROM',ROOT/'continuation/build/naruto_restart_v040_RC5.gba'))
os.environ['NARUTO_REPLAY_ROM']=str(ROM);os.environ['NARUTO_REPLAY_NAME']=os.environ.get('NARUTO_SAVE_NAME','save_resume_rc5_01')
if os.environ.get('NARUTO_SAVE_INPUT'):os.environ['NARUTO_REPLAY_SAVE']=os.environ['NARUTO_SAVE_INPUT']
native_skills=bytearray((ROOT/'build/naruto_role_swap_v0.1.5_EXPERIMENTAL.gba').read_bytes()[0x545458:0x545458+87*16]);native_skills[5*16+4]=json.loads(Path(str(ROM)+'.layout.json').read_text())['basicAttackPower']
ns={'__file__':str(ROOT/'continuation/tools/play_campaign.py')};exec((ROOT/'continuation/tools/play_campaign.py').read_text().split('q=Player();report=')[0],ns)
Player=ns['Player'];out=ns['out'];save=out/'ordinary_save.sav';q=Player();target=int(os.environ.get('NARUTO_SAVE_SCENE','56'))
try:
 q.boot()
 if target==57:
  q.start(56);q.limit=0
  for _ in range(40):
   if not q.alive_enemies():break
   if q.read(0x202680e,1)[0]:q.p.frames(600);q.key(1,200);continue
   for a in q.units():
    if not a['side']and not a['flags']&0x70:q.attack_or_approach(a['slot'])
   q.key(1,200)
  assert not q.alive_enemies()
  for _ in range(120):
   if q.read(0x20311ea,1)[0]==target and q.read(0x20311ec,1)[0]==1:break
   q.key(1,100)
 for _ in range(120):
  if q.read(0x20311ea,1)[0]==target and q.read(0x20311ec,1)[0]==1:break
  q.key(1,100)
 else:raise AssertionError('Briefing not ready')
 q.key(1)
 for _ in range(3):q.key(128)
 q.key(1,200);q.shot('01_select_ordinary_slot');q.key(1,180);q.shot('02_native_save_confirmation');
 q.key(1,300)
 if os.environ.get('NARUTO_SAVE_INPUT'):q.shot('03_existing_slot_overwrite');q.key(64);q.key(1,300)
 q.shot('03_native_save_completed');q.p.command('savecopy '+str(save));before=q.read(0x2022e34,24*188)
finally:q.p.close()
assert save.exists()and save.stat().st_size==32768
saved_sha=hashlib.sha256(save.read_bytes()).hexdigest();os.environ['NARUTO_REPLAY_SAVE']=str(save);q=Player()
try:
 q.boot();q.shot('04_cold_continue');assert q.read(0x20311ea,1)[0]==target;assert q.read(0x20311ec,1)[0]==1
 after=q.read(0x2022e34,24*188);assert before==after,'Party changed across ordinary save/cold continue'
 assert any(q.read(0x203e800,256));assert q.read(0x203e900,87*16)==native_skills;q.start(target);initial=q.units();assert any(a['side']==0 for a in initial);assert q.read(0x2026805,1)[0]==target and q.read(0x202680c,1)[0]>0;q.p.frames(180);q.shot('05_resumed_battle_started')
 result={'result':'pass','kind':'native in-game save; emulator process closed; new process cold boots the ordinary SAV; actual keys and RAM reads only','rom_sha256':hashlib.sha256(ROM.read_bytes()).hexdigest(),'saved_sav_sha256':saved_sha,'saved_sav_size':save.stat().st_size,'party_bytes_identical_after_reload':True,'initial_battle':initial,'resumed_scene':target,'resumed_battle_started':True,'name_and_skill_tables_initialized':True,'instant_state_loading':False,'not_run':['hardware power loss','all save slots','every chapter checkpoint']}
 (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False),flush=True)
finally:q.p.close()
assert hashlib.sha256(save.read_bytes()).hexdigest()==saved_sha
