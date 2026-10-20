#!/usr/bin/env python3
"""Independent emulator checks. Fixture calls are explicitly distinguished from gameplay."""
from pathlib import Path
import hashlib,json,re,struct,subprocess,sys,os

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('NARUTO_TEST_OUT',ROOT/'evidence/validation_v012'));OUT.mkdir(exist_ok=True)
ROM=Path(os.environ.get('NARUTO_TEST_ROM',ROOT/'build/naruto_role_swap_v0.1.2_EXPERIMENTAL.gba'))

class Probe:
    counter=0
    def __init__(self,rom=ROM,save=None):
        Probe.counter+=1
        args=[str(ROOT/'tools/gba_probe'),str(rom)]
        if save:args.append(str(save))
        self.errors=(OUT/f'emulator_errors_{Probe.counter:02}.log').open('w')
        self.trace=(OUT/f'commands_{Probe.counter:02}.log').open('w')
        self.p=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.errors,text=True,bufsize=1)
        assert self.p.stdout.readline().strip()=='READY'
    def command(self,s):
        self.trace.write(s+'\n');self.trace.flush()
        self.p.stdin.write(s+'\n');self.p.stdin.flush()
        line=self.p.stdout.readline().strip()
        if not line:raise RuntimeError(f'Probe stopped after {s}: {self.p.poll()}')
        return line
    def frames(self,n,k=0):return self.command(f'frames {n} {k:x}')
    def press(self,k):self.frames(8,k);self.frames(12)
    def shot(self,name):self.command(f'shot {OUT/name}')
    def state(self,name):self.command(f'state {OUT/name}')
    def load(self,name):self.command(f'loadstate {OUT/name}')
    def dump(self,name,address=0x2022e30,size=0x127c):
        self.command(f'dump {address:x} {size:x} {OUT/name}');return (OUT/name).read_bytes()
    def write(self,addr,val):self.command(f'w8 {addr:x} {val:x}')
    def call(self,addr,*args):
        before=self.command('regs')
        saved={k:int(v,16) for k,v in re.findall(r'(r\d+|cpsr)=([0-9A-Fa-f]+)',before)}
        result=self.command('call '+f'{addr:x} '+' '.join(f'{a:x}' for a in args))
        pc=int(re.search(r'return=([0-9A-Fa-f]+)',result).group(1),16)
        result=self.command(f'until {pc:x} 20 0')
        assert f'pc={pc:08X}' in result,result
        after=self.command('regs');sp=int(re.search(r'r13=([0-9A-Fa-f]+)',after).group(1),16)
        returned=int(re.search(r'r0=([0-9A-Fa-f]+)',after).group(1),16)
        assert sp==saved['r13'],(hex(addr),hex(sp),hex(saved['r13']))
        for name in [*(f'r{i}' for i in range(15)),'cpsr']:
            assert self.command(f'reg {name} {saved[name]:x}')=='REG 1'
        return returned
    def reward(self,stat,label):
        # Use the game's own script coroutine. Calling a yielding UI routine
        # from the scheduler's stack is not a valid execution fixture.
        self.frames(8)
        for _ in range(12):
            result=self.command('until 080977d8 90 1')
            if 'pc=080977D8' in result:break
            self.frames(8)
        else:raise AssertionError('Could not enter the native script coroutine')
        regs=self.command('regs');original=int(re.search(r'r7=([0-9A-Fa-f]+)',regs).group(1),16)
        self.command(f'w32 0203f100 {(7<<24)|(stat<<16)|(3<<8)|0x1d:x}')
        self.command(f'w32 0203f104 {original:x}')
        self.command('reg r7 0203f100')
        assert 'pc=080972F8' in self.command('until 080972f8 20 0')
        result=self.command('until 080977d8 90 0');self.shot(f'{label}_reward_text.png')
        for _ in range(12):
            if 'pc=080977D8' in result:
                regs=self.command('regs');current=int(re.search(r'r7=([0-9A-Fa-f]+)',regs).group(1),16)
                assert current==0x203f103,hex(current)
                self.command(f'reg r7 {original:x}');return
            result=self.command('until 080977d8 45 1')
            if 'pc=080977D8' not in result:result=self.command('until 080977d8 10 0')
        raise AssertionError(f'Reward did not return: {result}')
    def boot(self):self.frames(950);self.press(8);self.frames(90)
    def close(self):
        self.p.stdin.write('quit\n');self.p.stdin.flush();self.p.wait(timeout=10)
        self.trace.close();self.errors.close()

def actors(payload):
    result={}
    for slot in range(1,24):
        p=payload[4+slot*188:4+(slot+1)*188]
        if p[0]:result[p[0]]={'slot':slot,'level':p[1],'special':{p[0x50+i*4]:p[0x51+i*4] for i in range(24) if 23<p[0x50+i*4]<255}}
    return result

def objects(b):
    return [{'slot':i,'type':b[i*16],'target':struct.unpack_from('<H',b,i*16+6)[0]} for i in range(32) if b[i*16]]

def main():
    evidence={'rom_sha256':hashlib.sha256(ROM.read_bytes()).hexdigest(),'emulator':'local mGBA 0.11 research harness, Ubuntu WSL2','checks':[],'not_run':['full_natural_story_to_Haku','full_natural_story_to_curse_mark','natural_scroll_pickup_on_battle_map','complete_playthrough','hardware','all_character_combinations']}
    def record(name,kind,detail):
        evidence['checks'].append({'name':name,'kind':kind,'result':'pass','detail':detail});print(name,flush=True)
    p=Probe();p.boot();p.press(1);p.frames(180);p.shot('01_new_game_selector.png')
    # Normal UI input: Naruto position -> Lee (12), Sasuke -> Ino (4), Sakura -> Tenten (13).
    for _ in range(9):p.press(16)
    p.press(1);p.press(16);p.press(1)
    for _ in range(8):p.press(16)
    p.frames(30);p.shot('02_lee_ino_tenten.png');p.press(8);p.frames(150)
    b=p.dump('new_game_payload.bin');assert b[0x70:0x74]==b'NKT3' and list(b[0x74:0x77])==[12,4,13]
    assert actors(b)[12]['special']=={35:255}
    record('fresh_new_game_select_Lee_Ino_Tenten','natural_ui',{'choices':[12,4,13],'initial_actor':actors(b)})
    p.shot('03_opening_after_selection.png');p.state('fresh.state')
    p.call(0x8097614,1,2,1);p.call(0x8097614,1,3,1)
    b=p.dump('three_roles_locked.bin');a=actors(b)
    assert a[12]['special']=={35:255} and a[4]['special']=={27:255} and a[13]['special']=={36:1}
    record('three_initial_special_ability_states','native_entry_fixture',a)
    p.reward(24,'Lee');a=actors(p.dump('naruto_story_unlock.bin'))
    assert a[12]['special']=={35:0} and a[4]['special']=={27:255} and a[13]['special']=={36:1}
    record('Naruto_story_unlock_maps_to_Lee','native_script_coroutine_fixture',a)
    p.reward(25,'Ino');a=actors(p.dump('sasuke_story_unlock.bin'))
    assert a[4]['special']=={27:0}
    record('Sasuke_story_unlock_maps_to_Ino','native_script_coroutine_fixture',a)
    for cid in (1,2,3):p.call(0x806d4a0,cid,1)
    a=actors(p.dump('original_trio_locked.bin'));assert [a[c]['special'][23+c] for c in (1,2,3)]==[255,255,255]
    p.state('scrolls_before.state')
    cases=[('Lee',31,2,1),('Ino',25,2,2),('Tenten',27,2,3)]
    for label,stage,sub,target in cases:
        p.load('scrolls_before.state');p.write(0x2026805,stage);p.write(0x2026806,sub);p.call(0x806e810)
        objs=objects(p.dump(f'{label}_scroll_objects.bin',0x2026604,0x200))
        assert any(o['type']==4 and o['target']==target for o in objs),objs
        record(f'{label}_scroll_redirects_to_{target}','native_stage_object_fixture',{'stage':stage,'sub':sub,'objects':objs})
    p.load('scrolls_before.state')
    for cid in (1,2,3):p.call(0x806d5f8,cid)
    b=p.dump('original_trio_scroll_unlocked.bin');a=actors(b)
    assert [a[c]['special'][23+c] for c in (1,2,3)]==[0,0,0]
    assert a[12]['special']=={35:0} and a[13]['special']=={36:1}
    record('redirected_scroll_learning_effect','native_learning_fixture',a)
    p.state('scrolls_after.state')
    for label,stage,sub,target in cases:
        p.load('scrolls_after.state');p.write(0x2026805,stage);p.write(0x2026806,sub);p.call(0x806e810)
        objs=objects(p.dump(f'{label}_duplicate_objects.bin',0x2026604,0x200))
        assert not any(o['type']==4 and o['target']==target for o in objs)
    record('learned_scrolls_are_not_spawned_again','native_stage_object_fixture',{'roles':[1,2,3]})
    p.load('scrolls_after.state');p.call(0x8068848,0);p.call(0x8068848,2)
    p.command(f'savecopy {OUT/"roundtrip.sav"}');p.close()
    q=Probe(save=OUT/'roundtrip.sav');q.boot();q.press(1);q.frames(90)
    q.shot('04_coldboot_save_selection.png');q.press(1);q.frames(30);q.press(1);q.frames(90);q.press(1);q.frames(180)
    cold=q.dump('cold_loaded_payload.bin');assert cold[0x70:0x89]==b[0x70:0x89]
    assert actors(cold)==actors(b),(actors(cold),actors(b))
    record('SAV_only_coldboot_via_Continue_menu','coldboot_ui_from_fixture_save',actors(cold));q.shot('05_coldboot_world.png')
    q.press(128);q.press(1);q.frames(60);q.press(1);q.frames(60);q.shot('06_Lee_portrait_after_coldboot.png');q.close()
    source=(ROOT/'originals/naruto_konoha_bearteam_simp.gba').read_bytes()
    assert source[0x12d54:0x12d57]==bytes.fromhex('1d0318')
    assert source[0x2bd7e:0x2bd81]==bytes.fromhex('1d0319')
    record('original_story_unlock_command_bytes','static_source',{'Naruto_stat24':'0x08012d54','Sasuke_stat25':'0x0802bd7e'})
    # An overlapping permutation checks that source and destination IDs are not
    # remapped twice: Sakura -> Naruto role, Naruto -> Sasuke role, Sasuke -> Sakura role.
    c=Probe();c.boot();c.press(1);c.frames(180)
    for key in [16,1,32,1,32,64,64,32]:c.press(key)
    c.frames(30);c.shot('07_original_trio_cycle.png');c.press(8);c.frames(150)
    c.call(0x8097614,1,2,1);c.call(0x8097614,1,3,1)
    cyc=c.dump('cycle_before.bin');assert list(cyc[0x74:0x77])==[3,1,2]
    a=actors(cyc);assert a[3]['special']=={26:255} and a[1]['special']=={24:255} and a[2]['special']=={25:1}
    c.reward(24,'cycle_Sakura');c.reward(25,'cycle_Naruto')
    a=actors(c.dump('cycle_after.bin'));assert a[3]['special']=={26:0} and a[1]['special']=={24:0} and a[2]['special']=={25:1}
    record('overlapping_original_trio_cycle','natural_selection_and_native_script_fixture',a);c.close()
    legacy=[]
    for rom in [ROOT/'originals/naruto_konoha_bearteam_simp.gba',ROM]:
        old=Probe(rom,ROOT/'originals/user_clear_no_stat_points.sav');old.boot();old.call(0x8068684,1,1)
        payload=old.dump(f'legacy_{len(legacy)}.bin');assert payload[0x70:0x74]!=b'NKT3'
        legacy.append(actors(payload));old.close()
    assert legacy[0]==legacy[1]
    record('supplied_legacy_save_preserves_original_roster','native_save_loader_fixture',legacy[1])
    (OUT/'report.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print('REPORT',OUT/'report.json',flush=True)

if __name__=='__main__':main()
