import json
from pathlib import Path
import full_renderer as p
out=Path(__file__).resolve().parent/'inspect-frames.json'
assert not out.exists()
rows=[]
for flags in (0,8,0x10,0x20,0x30,0x60,0x88,0x388,0x20020):
 row=p.frame(sequence_table=0x458558,descriptor_table=0x45854C,group=0,flags=flags,count=2,x=16,y=16)
 rows.append({'flags_input':flags,'flags':row['flags'],'group':row['group'],'slot':row['slot'],'timer':row['timer'],
              'steps':len(row['visited']),'bios_instructions':len([a for a in row['visited'] if a<0x4000]),
              'div_swi':0x0809C0E4 in row['visited'],'sequence_reads':row['sequence_reads'],
              'head_reads':[r for r in row['descriptor_reads'] if r['pc'] in (0x080629FC,0x080631FE)]})
out.write_text(json.dumps(rows,sort_keys=True,indent=2)+'\n')
print(json.dumps(rows,sort_keys=True))
