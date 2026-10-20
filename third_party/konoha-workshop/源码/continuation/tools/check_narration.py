"""Cold-boot narration and first-battle checks; actual keys, RAM reads only."""
from pathlib import Path
import hashlib,json,os

ROOT=Path(__file__).resolve().parents[2]
ROM=Path(os.environ['NARUTO_REPLAY_ROM'])
ns={'__file__':str(ROOT/'continuation/tools/play_campaign.py')}
exec((ROOT/'continuation/tools/play_campaign.py').read_text().split('q=Player();report=')[0],ns)
q=ns['Player']();out=ns['out'];substitute=os.environ.get('NARUTO_OPENING_SUBSTITUTE')=='1'
report={'rom_sha256':hashlib.sha256(ROM.read_bytes()).hexdigest(),
        'kind':'cold boot actual keys; RAM reads only', 'pages':[],
        'substituted_trio':substitute,'not_run':['hardware','all trio combinations']}
def portraits():
    result=[]
    for i in range(2):
        ptr=int.from_bytes(q.read(0x03005e50+i*4,4),'little')
        result.append({'pointer':ptr,'state':q.read(ptr+0x2c,1)[0] if ptr else None})
    return result
try:
    q.p.frames(950);q.key(8,100);q.key(1,180)
    if substitute:
        for _ in range(9):q.key(16,12)
        q.key(1,12);q.key(16,12);q.key(1,12)
        for _ in range(8):q.key(16,12)
    q.shot('00_selected_trio');q.key(8,300)
    for i,speaker in enumerate([0,0,2,7,0,2]):
        assert q.read(0x020311ea,1)[0]==56 and q.read(0x020311ec,1)[0]==0
        state=portraits()
        if speaker==0:assert all(p['state'] in [None,48] for p in state),state
        else:assert any(p['state']==16 for p in state),state
        q.shot(f'01_opening_{i:02}_speaker_{speaker}')
        report['pages'].append({'index':i,'speaker':speaker,'portraits':state})
        q.key(1,300)
    assert q.read(0x020311ec,1)[0]==1,'Opening did not reach preparation'
    q.start(56);report['first_battle_units']=q.units()
    if not substitute:
        assert q.actor(1)['id']==2 and q.actor(1)['skills']==[5,19]
        a=q.actor(1);e=q.actor(2);q.cursor(a['x'],a['y']);q.key(1);q.key(128);q.key(1)
        menu=q.read(0x02026a8c,100);ids=[menu[1+i*6] for i in range(menu[0])]
        assert ids==[5,19] and 41 not in ids,ids
        q.shot('02_sasuke_skill_list');q.key(128);q.shot('03_lion_combo_selected')
        q.key(1);q.cursor(e['x'],e['y']);q.key(1);q.key(1);q.shot('04_confirm_attack')
        q.key(1,1)
        for i in range(32):q.p.frames(12);q.shot(f'05_lion_animation_{i:02}')
        q.action_turn=1;q.finish(1);q.shot('06_after_lion_combo')
        report['sasuke_skill_menu']=ids;report['after_lion_combo']=q.units()
        assert q.actor(1)['hp']==a['hp']-80,'Native Lion Combo must consume 80 HP'
        for step in range(40):
            if not q.alive_enemies():break
            if q.read(0x0202680e,1)[0]:q.p.frames(600);q.key(1,200);continue
            for unit in q.units():
                if not unit['side'] and not unit['flags']&0x70:q.attack_or_approach(unit['slot'])
            q.key(1,200)
        assert not q.alive_enemies(),'First battle was not won'
        for _ in range(120):
            if q.read(0x020311ea,1)[0]==57 and q.read(0x020311ec,1)[0]==1:break
            q.key(1,150)
        else:raise AssertionError('Next battle did not become available')
        q.shot('07_next_battle');report['first_battle_won']=True
    report['result']='pass'
except Exception as e:
    report.update(result='failed',error=str(e));q.shot('FAILED');raise
finally:
    q.p.close()
    trace=(out/'commands_01.log').read_text().splitlines()
    report['mutating_debug_commands']=[s for s in trace if s.split()[0] in ['w8','w16','w32','reg','call','loadstate']]
    assert not report['mutating_debug_commands']
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(out,flush=True)
