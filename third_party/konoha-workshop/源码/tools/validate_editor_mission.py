#!/usr/bin/env python3
"""Uninterrupted actual-key replay. Reads RAM for assertions; never writes RAM.

No instantaneous state is loaded. The ROM is cold-booted, a trio is selected,
and the battle is played using the original menus, movement and attacks.
"""
from pathlib import Path
import hashlib,json,struct,collections,os
import validate_candidate as v
ROOT=v.ROOT
ROM=ROOT/'build/naruto_fog_harbor_sample_v0.1.0.gba'
base=ROOT/'evidence/editor_v010/replay'
out=base
for i in range(1,100):
    out=base.with_name('replay_'+str(i).zfill(2))
    if not out.exists():break
if not os.environ.get('NARUTO_HELPER_NO_OUTPUT'):out.mkdir(parents=True);v.OUT=out

class Player:
    def __init__(self):self.p=v.Probe(ROM);self.events=[]
    def read(self,a,n):return bytes.fromhex(self.p.command(f'read {a:x} {n:x}'))
    def key(self,k,wait=60):self.p.press(k);self.p.frames(wait)
    def shot(self,name):self.p.command(f'shot {out/name}.png')
    def actor(self,i):
        a=self.read(0x20240c0+i*468,468)
        return {'slot':i,'id':a[0],'hp':int.from_bytes(a[12:14],'little'),'x':a[196],'y':a[197],'flags':int.from_bytes(a[192:196],'little')}
    def alive_enemies(self):return [a for i in [4,5] if (a:=self.actor(i))['id']]
    def cursor(self,x,y):
        for _ in range(80):
            cx,cy=self.read(0x2026a78,2)
            if (cx,cy)==(x,y):return
            self.key(16 if cx<x else 32 if cx>x else 128 if cy<y else 64,25)
        raise AssertionError(f'Cursor stuck at {(cx,cy)}, target {(x,y)}')
    def finish(self,slot):
        for _ in range(18):
            if not self.alive_enemies():return
            if not self.actor(slot)['flags']&0x100:return
            self.key(1,180)
        raise AssertionError('Action did not finish')
    def adjacent_destination(self,slot,target):
        a,t=self.actor(slot),self.actor(target)
        if abs(a['x']-t['x'])+abs(a['y']-t['y'])==1:return None
        w,h=self.read(0x201be2a,2);tiles=struct.unpack('<'+'H'*(w*h),self.read(0x2021e2c,w*h*2))
        actors=[self.actor(i) for i in range(1,6)];occupied={(b['x'],b['y']) for b in actors if b['id'] and b['slot']!=slot}
        start=(a['x'],a['y']);queue=collections.deque([(start,0)]);seen={start}
        while queue:
            (x,y),cost=queue.popleft()
            if (x,y)not in occupied and abs(x-t['x'])+abs(y-t['y'])==1:return (x,y)
            if cost==3:continue
            for nx,ny in [(x+1,y),(x-1,y),(x,y+1),(x,y-1)]:
                if 0<=nx<w and 0<=ny<h and (nx,ny)not in seen and (nx,ny)not in occupied and tiles[ny*w+nx]&15 not in [7,15] and not tiles[ny*w+nx]&64:
                    seen.add((nx,ny));queue.append(((nx,ny),cost+1))
        raise AssertionError(f'No reachable melee position for {slot} -> {target}')
    def attack(self,slot,target,skillrow=0,move=None):
        a=self.actor(slot)
        if not a['id'] or not self.actor(target)['id']:return
        if move is None:move=self.adjacent_destination(slot,target)
        self.cursor(a['x'],a['y']);self.key(1)
        if move:
            self.key(1);self.cursor(*move);self.key(1,160);self.key(1)
        else:self.key(128);self.key(1)
        if skillrow:self.key(128)
        self.key(1);t=self.actor(target);self.cursor(t['x'],t['y']);self.key(1);self.key(1);self.key(1,800)
        self.finish(slot);self.events.append({'action':'attack','actor':slot,'target':target,'after':[self.actor(i)for i in range(1,6)]})
    def move_wait(self,slot,xy):
        a=self.actor(slot);self.cursor(a['x'],a['y']);self.key(1);self.key(1);self.cursor(*xy);self.key(1,160);self.key(128);self.key(1);self.finish(slot)
    def enemy_phase(self,previous_turn):
        for _ in range(18):
            if not self.alive_enemies():return
            self.p.frames(600)
            if self.read(0x202680c,1)[0]>previous_turn and self.read(0x202680e,1)[0]==0:
                self.p.frames(180);return
            self.key(1,200)
        raise AssertionError('Enemy phase did not finish')

def main():
    q=Player();p=q.p
    try:
        p.frames(950);q.shot('01_title');q.key(8,100);q.key(1,180)
        for _ in range(9):q.key(16,12)
        q.key(1,12);q.key(16,12);q.key(1,12)
        for _ in range(8):q.key(16,12)
        q.key(8,180);q.shot('02_opening')
        for _ in range(28):
            if q.read(0x20311ec,1)[0]==1:break
            q.key(1,110)
        else:raise AssertionError('Opening did not finish')
        p.frames(160);q.shot('03_mission_brief')
        q.key(1);q.key(128);q.key(128);q.key(1);q.key(1,350)
        for _ in range(8):
            if q.read(0x202680c,1)[0]>0:break
            q.key(1,180)
        p.frames(200)
        assert [q.actor(i)['id']for i in range(1,6)]==[12,4,13,17,18]
        assert q.read(0x2026805,2)==b'\x01\x00'
        q.shot('04_battle_turn1')
        for turn in range(1,9):
            assert q.read(0x202680c,1)[0]==turn
            if q.actor(5)['id']:q.attack(1,5,move=(11,9)if turn==1 else None)
            elif q.actor(4)['id']:q.attack(1,4)
            if not q.alive_enemies():break
            if q.actor(2)['id']and q.actor(4)['id']:q.attack(2,4,1,move=(11,5)if turn==1 else None)
            if not q.alive_enemies():break
            if turn<=2:q.move_wait(3,(7,6)if turn==1 else(7,4))
            elif q.actor(4)['id']:q.attack(3,4,1,move=(9,5)if turn==3 else None)
            elif q.actor(5)['id']:q.attack(3,5,1)
            if not q.alive_enemies():break
            q.enemy_phase(turn);q.shot(f'turn_{turn+1}')
            print('turn',turn,'finished',flush=True)
        else:raise AssertionError('Mission not cleared in eight turns')
        p.frames(200);q.shot('05_victory_condition');q.shot('06_before_victory_banner')
        saw_victory=False
        for i in range(64):
            q.key(1,200)
            if i<24:q.shot(f'ending_{i:02}')
            current=q.read(0x20311ea,1)[0]
            if current==2:
                saw_victory=True;q.shot('07_next_chapter');break
        assert saw_victory,'No progression to original chapter 2'
        trace=(out/'commands_01.log').read_text()
        forbidden=[line for line in trace.splitlines()if line.split(' ')[0]in['w8','w16','w32','call','reg','loadstate']]
        assert not forbidden,forbidden
        report={'result':'pass','rom_sha256':hashlib.sha256(ROM.read_bytes()).hexdigest(),'kind':'uninterrupted cold boot and actual key input; RAM reads only','trio':[12,4,13],'victory_turn':turn,'ending_scene':2,'forbidden_mutating_debug_commands':forbidden,'events':q.events,'not_run':['full_game','all_trio_choices','hardware','Windows_native_emulator']}
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('PASS',out,flush=True)
    except Exception:
        q.shot('FAILED');p.command(f'state {out/"FAILED.state"}');raise
    finally:p.close()

if __name__=='__main__':main()
