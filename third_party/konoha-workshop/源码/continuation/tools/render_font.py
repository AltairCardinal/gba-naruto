import json,sys,os
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
cache_path=Path(__file__).resolve().parents[1]/'project/font_glyphs.json'
cache=json.loads(cache_path.read_text())if cache_path.exists()and not os.environ.get('NARUTO_FONT')else{}
font=None
result={}
for ch in json.load(open(sys.argv[1],encoding='utf-8')):
 if ch in cache:result[ch]=cache[ch];continue
 if font is None:font=ImageFont.truetype(os.environ.get('NARUTO_FONT','/mnt/c/Windows/Fonts/simsun.ttc'),16)
 im=Image.new('L',(16,16));ImageDraw.Draw(im).text((0,-2),ch,font=font,fill=255)
 im=im.resize((8,16),Image.Resampling.BILINEAR);pixels=[3 if v>80 else 0 for v in im.get_flattened_data()];g=[0]*32
 for y in range(15,-1,-1):
  for x in range(7,-1,-1):
   if pixels[y*8+x]==3:
    if x<7 and pixels[y*8+x+1]==0:pixels[y*8+x+1]=1
    if y<15 and pixels[(y+1)*8+x]==0:pixels[(y+1)*8+x]=1
 for y in range(16):
  for x in range(8):g[y*2+x//4]|=pixels[y*8+x]<<((x%4)*2)
 if not any(g):raise RuntimeError('Empty glyph: '+ch)
 result[ch]=g
json.dump(result,open(sys.argv[2],'w',encoding='utf-8'),ensure_ascii=False)
