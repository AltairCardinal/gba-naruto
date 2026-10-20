'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto'),E=require('../../editor/music');
const R=path.resolve(__dirname,'../..'),out=path.join(R,'continuation/evidence/escape03_static');fs.mkdirSync(out,{recursive:false});const sha=b=>crypto.createHash('sha256').update(b).digest('hex'),checks=[];
try{
 for(const edition of ['restart','continuation']){
  const file=path.join(R,`continuation/build/naruto_${edition}_v044_ESCAPE03.gba`),r=fs.readFileSync(file),m=new E.Editor(r),old=new E.Editor(fs.readFileSync(path.join(R,`continuation/build/naruto_${edition}_v043_AUDIO04.gba`)));assert.equal(m.campaign.capabilities.arrivalRules,true);assert.equal(m.campaign.chapters.length,26);
  const l=m.layout(),ol=old.layout();let unchanged=0;
  for(const s of m.battleIds())for(let sub=0;sub<3;sub++){
   const rules=m.rules(s,sub);
   if(s===57){
    assert.equal(rules.turn,0);assert.deepEqual(rules.groups[0].filter(x=>x.type).map(x=>[x.type,x.a,x.b,x.c]),[[10,3,3,11]]);assert.deepEqual(rules.groups[1].filter(x=>x.type).map(x=>[x.type,x.a]),[[1,0]]);
    const a=m.actors(s,sub);assert.equal(a[0].id,3);assert.equal(a[0].invulnerable,false);assert.equal(a[1].id,4);assert.equal(a[1].level,99);assert.equal(a[1].invulnerable,true);
    const t=m.missionTexts(s,sub).map(x=>m.textValue(x));assert(t[0].includes('脱离心之陷阱'));assert.equal(t[1],'胜利：小樱到达青色撤离格。\n击败敌人、等待回合均不能过关。');assert(t[2].includes('向左上'));assert.equal(m.mapData(s).terrain[(11*13+3)*2]&15,0);
   }else{
    assert.deepEqual(r.subarray(m.actorBase(s,sub),m.actorBase(s,sub)+0x8e4),old.rom.slice(old.actorBase(s,sub),old.actorBase(s,sub)+0x8e4));assert.equal(rules.turn,old.rules(s,sub).turn);
    assert.deepEqual(rules.groups.map(g=>g.map(x=>[x.type,x.a,x.b,x.c])),old.rules(s,sub).groups.map(g=>g.map(x=>[x.type,x.a,x.b,x.c])));
    assert.deepEqual(m.missionTexts(s,sub).map(x=>m.textValue(x)),old.missionTexts(s,sub).map(x=>old.textValue(x)));assert.deepEqual(r.subarray(l.maps+s*32,l.maps+(s+1)*32),old.rom.slice(ol.maps+s*32,ol.maps+(s+1)*32));
    if(s>=56)assert.deepEqual(r.subarray(l.loadouts+(s-56)*384,l.loadouts+(s-55)*384),old.rom.slice(ol.loadouts+(s-56)*384,ol.loadouts+(s-55)*384));unchanged++;
   }
  }
  for(let s=0;s<104;s++)for(let sub=0;sub<3;sub++){const p=l.modifiers+s*6+sub*2;assert.equal(r[p]|r[p+1]<<8,s===57?2:0);}
  const project=edition==='restart'?'campaign.json':'campaign_continuation.json',j=JSON.parse(fs.readFileSync(path.join(R,'continuation/project',project))),before=JSON.parse(fs.readFileSync(path.join(R,'continuation/history/v043_before_escape_20261019/continuation/project',project)));assert.deepEqual(j.battles.filter((_,i)=>i!==1),before.battles.filter((_,i)=>i!==1));
  checks.push({edition,sha256:sha(r),second_battle_configurations:3,only_exit_can_win:true,no_turn_win:true,enemy_level:99,enemy_invulnerable:true,exit:[3,11],unchanged_other_configurations:unchanged,other_story_drafts:'unchanged'});
 }
 fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'pass',kind:'current ROM rules/text/presets/maps/modifiers plus source scope comparison; natural gameplay checked separately',checks},null,2));console.log(JSON.stringify(checks,null,2));
}catch(e){fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'failed',error:String(e),checks},null,2));throw e;}
