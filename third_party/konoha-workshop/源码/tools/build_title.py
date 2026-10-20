#!/usr/bin/env python3
"""Add the requested small title credit to the existing v0.1.2 build."""
from pathlib import Path
import argparse,hashlib,json,struct,sys
sys.path.insert(0,str(Path(__file__).parent))
from build import ips
ROOT=Path(__file__).resolve().parents[1]
TEXT='你是谁怎么傻乎乎修改 免费分享'
SOURCE_HASH='736a7223ed1edc4a87c9f1be8263e7873ff7cd91fd14f0009fec93df3705df05'

def lz_read(data,p):
    assert data[p]==0x10
    size=int.from_bytes(data[p+1:p+4],'little');out=bytearray();p+=4
    while len(out)<size:
        flags=data[p];p+=1
        for shift in range(7,-1,-1):
            if len(out)>=size:break
            if flags>>shift&1:
                a,b=data[p:p+2];p+=2;length=(a>>4)+3;back=((a&15)<<8|b)+1
                for _ in range(length):out.append(out[-back])
            else:out.append(data[p]);p+=1
    return out

def lz_literal(data):
    out=bytearray([0x10])+len(data).to_bytes(3,'little')
    for p in range(0,len(data),8):out.append(0);out.extend(data[p:p+8])
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--regenerate-mask',action='store_true');args=ap.parse_args()
    maskfile=ROOT/'source/title_stamp_mask_left.bin'
    if args.regenerate_mask:
        from PIL import Image,ImageDraw,ImageFont
        im=Image.new('1',(104,32),0);d=ImageDraw.Draw(im);f=ImageFont.truetype('/mnt/c/Windows/Fonts/simsun.ttc',10)
        d.text((2,0),'你是谁怎么傻乎乎修改',font=f,fill=1)
        d.text((2,12),'免费分享',font=f,fill=1)
        maskfile.write_bytes(bytes(bool(v) for v in im.getdata()))
    mask=maskfile.read_bytes();assert len(mask)==104*32 and any(mask)
    src=ROOT/'build/naruto_role_swap_v0.1.2_EXPERIMENTAL.gba';rom=src.read_bytes()
    assert hashlib.sha256(rom).hexdigest()==SOURCE_HASH,'Unexpected v0.1.2 input'
    tiles=lz_read(rom,0x5b6880);originalmap=lz_read(rom,0x3f1c98)
    assert len(tiles)==0x2180 and len(originalmap)==24*12*2
    tilemap=bytearray(32*12*2)
    for y in range(12):tilemap[y*64+16:y*64+64]=originalmap[y*48:(y+1)*48]
    palette=struct.unpack_from('<16H',rom,0x3f0af0)
    ink=max(range(1,16),key=lambda i:sum((palette[i]>>shift)&31 for shift in [0,5,10]))
    first=len(tiles)//32
    for ty in range(4):
        for tx in range(13):
            q=(ty*32+tx)*2;entry=struct.unpack_from('<H',tilemap,q)[0]
            existing=tiles[(entry&1023)*32:(entry&1023)*32+32];t=bytearray(32)
            for y in range(8):
                for x in range(8):
                    ox=7-x if entry&0x400 else x;oy=7-y if entry&0x800 else y
                    color=existing[oy*4+ox//2]>>((ox%2)*4)&15
                    if mask[(ty*8+y)*104+tx*8+x]:color=ink
                    t[y*4+x//2]|=color<<((x%2)*4)
            tiles.extend(t);struct.pack_into('<H',tilemap,q,0x8000+first+ty*13+tx)
    assert len(tiles)<=0x3800
    out=bytearray(rom);records=[]
    def append(data):
        while len(out)%4:out.append(255)
        p=len(out);out.extend(data);return 0x08000000+p
    for p,old,new in [(0x8bd30,struct.pack('<I',0x085b6880),struct.pack('<I',append(lz_literal(tiles)))),(0x8bd38,struct.pack('<I',0x083f1c98),struct.pack('<I',append(lz_literal(tilemap)))),(0x8bbea,bytes.fromhex('1822'),bytes.fromhex('2022')),(0x8bbf2,bytes.fromhex('9020'),bytes.fromhex('c020')),(0x8bd44,struct.pack('<I',0x0600f810),struct.pack('<I',0x0600f800))]:
        assert rom[p:p+len(old)]==old,(hex(p),rom[p:p+len(old)].hex())
        out[p:p+len(new)]=new;records.append({'offset':p,'before':old.hex(),'after':new.hex()})
    dest=ROOT/'build/naruto_role_swap_v0.1.5_EXPERIMENTAL.gba';dest.write_bytes(out)
    baseline=(ROOT/'originals/naruto_konoha_bearteam_simp.gba').read_bytes()
    dest.with_suffix('.ips').write_bytes(ips(baseline,out))
    manifest={'version':'0.1.5-experimental','title_text':TEXT,'base_v012_sha256':SOURCE_HASH,'target_sha256':hashlib.sha256(out).hexdigest(),'size':len(out),'patches':records,'placement':'BG1 top left, white 10px text on two lines; native title image and copyright kept','runtime_validation':'pending'}
    (ROOT/'build/title_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps(manifest,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
