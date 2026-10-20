'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto'),E=require('../../editor/campaign_editor');require('../../editor/flow');
const root=path.resolve(__dirname,'../..'),checks=[];
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const rows=r=>r.groups.map(g=>g.filter(v=>v.type).map(({type,a,b,c})=>({type,a,b,c})));
for(const filename of process.argv.slice(2)){
 const r=fs.readFileSync(filename),m=new E.Editor(r),edition=m.campaign.edition,old=new E.Editor(fs.readFileSync(path.join(root,'continuation/build','naruto_'+edition+'_v042_PORTRAIT02.gba'))),l=m.layout();let configurations=0;
 for(const [key,size]of[['actors',104*0x1aac],['maps',104*32],['profiles',104*64],['loadouts',48*384],['skills',87*16]])assert.deepEqual(r.subarray(l[key],l[key]+size),old.rom.subarray(l[key],l[key]+size),key+' gameplay data changed unexpectedly');
 for(const b of m.campaign.chapters)for(let sub=0;sub<3;sub++){
  const rule=m.rules(b.id,sub),previous=old.rules(b.id,sub),limit=b.turnLimit||0,round=String(limit).replace(/[0-9]/g,c=>'０１２３４５６７８９'[+c]);
  assert.equal(rule.turn,limit);assert.deepEqual(rows(rule),rows(previous),'Victory/loss logic must not silently change');
  assert.deepEqual(rows(rule)[0],limit?[{type:2,a:1,b:0,c:0},{type:1,a:1,b:0,c:0}]:[{type:1,a:1,b:0,c:0}]);
  assert.deepEqual(rows(rule)[1],[{type:1,a:0,b:0,c:0}]);
  const text=m.missionTexts(b.id,sub).map(e=>m.textValue(e));
  assert.equal(text[0],b.title);assert.equal(text[1],limit?'胜利：进入第'+round+'回合，\n或击退敌方全部人物。':'胜利：击退敌方全部人物。');assert(text[2].startsWith('失败：我方全员退场。\n'));
  assert.equal(b.description,text[1]);assert.equal(b.hint,text[2]);
  for(const line of[...text[1].split('\n'),...text[2].split('\n')])assert([...line].length<=24,'Conditions overflow the native text window');
  for(const n of m.scripts(b.id).nodes)if(n.op===2)assert(r[n.offset+2]>0,'Invalid portrait zero reappeared');
  configurations++;
 }
 checks.push({filename,sha256:sha(r),edition,configurations,conditions_match_actual_rules:'pass',actor_balance_unchanged:'pass',narration_no_invalid_portrait:'pass'});
}
assert.equal(checks.length,2,'Validate both editions together');
const out=path.join(root,'continuation/evidence/reset03_release_static');fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'pass',kind:'static all-configuration release regression checks; warm restart verified separately',checks},null,2));console.log(JSON.stringify(checks,null,2));
