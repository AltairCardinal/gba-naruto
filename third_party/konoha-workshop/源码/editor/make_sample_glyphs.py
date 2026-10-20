from pathlib import Path
import json,sys
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parent
story=json.loads((root/'sample_story.json').read_text())
texts=[line['text'] for phase in ['before','after'] for line in story[phase]]+story['mission_texts']+['击退两名破坏者','我方全员倒下']
font=ImageFont.truetype('/mnt/c/Windows/Fonts/simsun.ttc',16)
output={}
for ch in sorted(set(''.join(texts))-{'\n',' '}):
    im=Image.new('1',(16,16),0);ImageDraw.Draw(im).text((0,-1),ch,font=font,fill=1)
    pixels=[0]*128
    for y in range(16):
        for x in range(8):
            if im.getpixel((x*2,y)) or im.getpixel((x*2+1,y)):pixels[y*8+x]=3
    for y in range(15,-1,-1):
        for x in range(7,-1,-1):
            if pixels[y*8+x]==3:
                if x<7 and not pixels[y*8+x+1]:pixels[y*8+x+1]=1
                if y<15 and not pixels[(y+1)*8+x]:pixels[(y+1)*8+x]=1
    data=[sum(pixels[(j//2)*8+(j%2)*4+k]<<(k*2) for k in range(4)) for j in range(32)]
    output[ch]=data
(root/'sample_glyphs.json').write_text(json.dumps(output,ensure_ascii=False,separators=(',',':'))+'\n')
print('Generated',len(output),'characters')
