#!/usr/bin/env python3
"""Build an offline, font-fingerprinted Chinese lookup; this never modifies a ROM.

GB2312 order was inferred from native glyph samples and dialogue context.
8959=焙 is explicitly user-confirmed. Other inferred entries remain reviewable.
"""
from pathlib import Path
import json,struct
ROOT=Path(__file__).resolve().parents[1]
r=(ROOT/'originals/naruto_konoha_bearteam_simp.gba').read_bytes()
source=json.loads((ROOT/'analysis/text_mapping_candidate.json').read_text())
rare={0x987b:'吵',0x9886:'嗦',0x9889:'阱',0x988a:'喽',0x988b:'咦',0x988f:'镖',0x9898:'嗝',0x989d:'嗯',0x989e:'哼',0x989f:'险',0x9cc5:'嗷',0x9cc6:'篝',0x9cc7:'胧',0x9cc8:'冥',0x9cc9:'蜈',0x9cca:'蚣',0x9ccc:'蟑',0x9ccd:'螂',0x9cce:'嘻',0x9ccf:'唧',0x9cd1:'呗',0x9cd2:'哧',0x9cd3:'吱',0x9cd9:'啰',0x9cda:'嘀',0x9cdb:'狩',0x9cdc:'飙',0x9cdd:'蚱'}
source.update({str(k):v for k,v in rare.items()})
confirmed_file=ROOT/'analysis/confirmed_glyph_labels.json'
confirmed=json.loads(confirmed_file.read_text())['labels'] if confirmed_file.exists() else {'8959':'焙'}
source.update({str(int(k,16)):v for k,v in confirmed.items()})
def fnv(data):
 h=2166136261
 for x in data:h=((h^x)*16777619)&0xffffffff
 return f'{h:08x}'
segments=[];mapping={}
for i in range(26):
 start,count,_,p=struct.unpack_from('<HBBI',r,0x53d644+i*8);p-=0x8000000
 segments.append({'start':start,'count':count,'signature':fnv(r[p:p+count*32])})
 for c in range(start,start+count):
  data=r[p+(c-start)*32:p+(c-start+1)*32]
  # Invalid SJIS slot 7F is blank; the extension's tail is placeholder boxes.
  if c&255==0x7f or c>=0x9cf7 or not any(data):continue
  if str(c)in source and len(source[str(c)])==1:mapping[str(c)]=source[str(c)]
catalog={'version':1,'description':'原始字形对照推断；confirmed 中列出的字已由用户确认，其余待人工校对。','segments':segments,'mapping':mapping,'confirmed':{str(int(k,16)):v for k,v in confirmed.items()},'previousInference':{'35161':'被'}}
out=ROOT/'editor/text_catalog.js'
out.write_text('/* Derived character labels only; contains no game graphics. */\n(function(root){const data='+json.dumps(catalog,ensure_ascii=False,separators=(',',':'))+';if(typeof module!=="undefined")module.exports=data;else root.NarutoTextCatalog=data;})(typeof window==="undefined"?globalThis:window);\n',encoding='utf-8')
print('catalog entries',len(mapping),'user-confirmed',catalog['confirmed'])
