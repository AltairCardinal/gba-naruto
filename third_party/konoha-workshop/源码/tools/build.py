#!/usr/bin/env python3
"""Build the experimental role-swap ROM against the exact supplied baseline."""
from pathlib import Path
import argparse, hashlib, json, os, struct, subprocess, zlib

ROOT=Path(__file__).resolve().parents[1]
BASE_HASH='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
VERSION='0.1.2'

def run(args):
    subprocess.run([str(x) for x in args],check=True)

def prepare_ui():
    from PIL import Image,ImageDraw,ImageFont
    fontpath=Path(os.environ.get('NARUTO_UI_FONT','/mnt/c/Windows/Fonts/simsun.ttc'))
    font=ImageFont.truetype(str(fontpath),12)
    bg=(16,16,32)
    def panel(size,text,fg=(245,241,218),at=(5,2)):
        im=Image.new('RGB',size,bg);ImageDraw.Draw(im).text(at,text,font=font,fill=fg)
        return [((r>>3)|((g>>3)<<5)|((b>>3)<<10)) for r,g,b in im.getdata()]
    header=panel((240,24),'新游戏：选择三人替代者',(255,204,71),(22,5))
    labels=[panel((96,16),s) for s in ['鸣人位置','佐助位置','小樱位置']]
    footer=panel((240,28),'左右选人  上下换位\nA 下一位  START 确认开始',at=(13,0))
    def arr(name,values,decl):return 'const unsigned short '+name+decl+'={'+','.join(map(str,values))+'};\n'
    text=arr('ui_header',header,'[240*24]')
    text+='const unsigned short ui_labels[3][96*16]={'
    text+=','.join('{'+','.join(map(str,v))+'}' for v in labels)+'};\n'
    text+=arr('ui_footer',footer,'[240*28]')
    (ROOT/'build/ui.c').write_text(text)

def ips(src,dst):
    out=bytearray(b'PATCH');i=0
    while i<len(dst):
        if i<len(src) and src[i]==dst[i]:i+=1;continue
        start=i;i+=1
        while i<len(dst) and i-start<65535 and (i>=len(src) or src[i]!=dst[i]):i+=1
        # The three-byte value EOF is reserved by the IPS format.
        if start==0x454f46:start-=1
        chunk=dst[start:i];out+=start.to_bytes(3,'big')+len(chunk).to_bytes(2,'big')+chunk
    return bytes(out+b'EOF')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--toolchain-prefix',default='arm-none-eabi-');ap.add_argument('--regenerate-ui',action='store_true')
    a=ap.parse_args();prefix=a.toolchain_prefix
    (ROOT/'build').mkdir(exist_ok=True)
    src=ROOT/'originals/naruto_konoha_bearteam_simp.gba';rom=src.read_bytes()
    assert hashlib.sha256(rom).hexdigest()==BASE_HASH,'Unexpected input ROM'
    if a.regenerate_ui:
        prepare_ui()
        (ROOT/'source/ui_assets.c').write_bytes((ROOT/'build/ui.c').read_bytes())
    common=['-mcpu=arm7tdmi','-mthumb','-mthumb-interwork','-Os','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-fomit-frame-pointer','-Wall']
    for name,path in [('swap',ROOT/'source/role_swap.c'),('ui',ROOT/'source/ui_assets.c')]:
        run([prefix+'gcc',*common,'-c',path,'-o',ROOT/f'build/{name}.o'])
    elf=ROOT/'build/role_swap.elf'
    run([prefix+'gcc','-mcpu=arm7tdmi','-mthumb','-mthumb-interwork','-nostdlib','-T',ROOT/'source/linker.ld',ROOT/'build/swap.o',ROOT/'build/ui.o','-lgcc','-o',elf])
    run([prefix+'objcopy','-O','binary',elf,ROOT/'build/role_swap.bin'])
    nm=subprocess.check_output([prefix+'nm','-n',str(elf)],text=True)
    (ROOT/'build/symbols.txt').write_text(nm)
    symbols={s[2]:int(s[0],16) for l in nm.splitlines() if len(s:=l.split())==3}
    out=bytearray(rom);blob=(ROOT/'build/role_swap.bin').read_bytes();out+=blob
    hooks=[(0x68dfc,'10b581b000200090','hook_init'),(0x6d4a0,'f0b557464e464546','hook_add'),(0x97614,'f0b557464e464546','hook_story'),(0x972f8,'f0b54f464646c0b4','hook_reward'),(0x6e898,'6078fef7ddfe751c','hook_scroll'),
           (0x6e2f4,'bc20604340440079','hook_fixed_ally'),
           (0x8927c,'071c0df057ff0028','hook_level_popup'),
           (0x89984,'0df0d4fb002802d1','hook_level_check'),
           (0x93a78,'03d0534618780328','hook_exp_display'),
           (0x899ec,'f0b5474680b4061c','hook_auto_skills'),
           (0x958d8,'07d101f029fc0028','hook_equipment_edit'),
           (0x95c90,'03d901f04dfa0028','hook_equipment_owner'),
           (0x8fc20,'10b50006040e0906','hook_item_compatible')]
    records=[]
    for off,before,name in hooks:
        assert rom[off:off+8]==bytes.fromhex(before),(hex(off),name)
        addr=symbols[name]|1
        after=bytes.fromhex('004b1847')+struct.pack('<I',addr) # ldr r3,[pc]; bx r3
        out[off:off+8]=after;records.append({'offset':off,'before':before,'after':after.hex(),'function':name,'target':hex(addr)})
    # Opcode 0x23 shares its add-r7 tail with many other VM handlers. Redirect
    # only its dispatch-table pointer; keep that shared native tail intact.
    off=0x977f4+0x23*4
    before=struct.pack('<I',0x08097e22)
    assert rom[off:off+4]==before
    addr=symbols['hook_team_script']
    after=struct.pack('<I',addr)
    out[off:off+4]=after
    records.append({'offset':off,'before':before.hex(),'after':after.hex(),'function':'hook_team_script','target':hex(addr),'kind':'thumb_vm_pointer'})
    dest=ROOT/f'build/naruto_role_swap_v{VERSION}_EXPERIMENTAL.gba';dest.write_bytes(out)
    (ROOT/f'build/naruto_role_swap_v{VERSION}_EXPERIMENTAL.ips').write_bytes(ips(rom,out))
    manifest={'version':VERSION+'-experimental','baseline_sha256':BASE_HASH,'target_sha256':hashlib.sha256(out).hexdigest(),'target_size':len(out),'hooks':records,'runtime_acceptance':'not_run'}
    (ROOT/'build/build_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
