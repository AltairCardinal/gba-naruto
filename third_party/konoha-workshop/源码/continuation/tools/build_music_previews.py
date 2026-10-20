"""Generate browser previews from the game's own sound engine, using temporary ROM copies."""
from pathlib import Path
import json,subprocess,re,wave,array,math,hashlib
R=Path(__file__).resolve().parents[2];out=R/'continuation/evidence/music_preview';out.mkdir(exist_ok=True);base=R/'originals/naruto_konoha_bearteam_simp.gba';raw=base.read_bytes();import struct,os;rows=[];script=bytes([27,4,0,30,1,3,255,32,2,0,1,77,85,83,73,67,0,0]);offset=len(raw)
for id in range(1,19):
 rom=out/f'preview_{id:02}.gba';data=bytearray(raw+script);struct.pack_into("<I",data,0x60c74+54*4,0x08000000+offset);data[offset+1]=id;rom.write_bytes(data);pcm=out/f'preview_{id:02}.pcm';p=subprocess.run([str(R/'continuation/tools/gba_music_preview'),str(rom),str(pcm)],capture_output=True,text=True,check=True,env={**os.environ,"PREVIEW_ORIGINAL":"1"});(out/f'preview_{id:02}_capture.log').write_text(p.stdout+p.stderr);rate=int(re.search(r'RATE (\d+)',p.stdout)[1]);a=array.array('h',pcm.read_bytes());row={'id':id,'rate':rate,'frames':len(a)//2,'peak':max(map(abs,a)),'rms':math.sqrt(sum(x*x for x in a)/len(a)),'pcm_sha256':hashlib.sha256(pcm.read_bytes()).hexdigest()};rows.append(row);print(row,flush=True)
 with wave.open(str(out/f'preview_{id:02}.wav'),'wb')as w:w.setparams((2,2,rate,0,'NONE',''));w.writeframes(a.tobytes())
(out/'report.json').write_text(json.dumps({'result':'research','source_sha256':hashlib.sha256(raw).hexdigest(),'rows':rows},indent=2))
