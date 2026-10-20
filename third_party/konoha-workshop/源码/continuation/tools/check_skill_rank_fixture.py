"""Controlled regression fixture. RAM rank setup is not natural gameplay acceptance."""
from pathlib import Path
import os,json,hashlib
R=Path(__file__).resolve().parents[2];rom=R/'continuation/build/naruto_restart_v041_FIX05.gba'
os.environ['NARUTO_REPLAY_ROM']=str(rom);os.environ['NARUTO_REPLAY_NAME']='skill_rank_fixture_05'
ns={'__file__':str(R/'continuation/tools/play_campaign.py')};exec((R/'continuation/tools/play_campaign.py').read_text().split('q=Player();report=')[0],ns)
q=ns['Player']();out=ns['out']
try:
 q.boot()
 for _ in range(180):
  if q.read(0x20311ea,1)[0]==56 and q.read(0x20311ec,1)[0]==1:break
  q.key(1,100)
 actor=next(0x2022e34+n*188 for n in range(1,24) if q.read(0x2022e34+n*188,1)[0]==2)
 record=next(actor+0x14+i*4 for i in range(15) if q.read(actor+0x14+i*4,1)[0]==5)
 original=q.read(record,4);q.p.command(f'w8 {record+1:x} 2')
 expected=bytes([5,2,original[2],original[3]])
 q.start(56)
 actual=q.read(0x20240c0+468+0x14,4);assert actual==expected,(actual,expected)
 assert q.read(actor+0x14,4)==expected
 (out/'report.json').write_text(json.dumps({'result':'pass','kind':'controlled RAM setup fixture; separate from actual-key full replay','rom_sha256':hashlib.sha256(rom.read_bytes()).hexdigest(),'skill':5,'rank_before_entry':2,'rank_after_entry':actual[1],'usage_bytes_retained':actual[2:]==original[2:],'debug_rank_write':True,'claims_natural_training':False},indent=2))
 print('PASS learned rank is retained on entry (controlled fixture)')
finally:q.p.close()
