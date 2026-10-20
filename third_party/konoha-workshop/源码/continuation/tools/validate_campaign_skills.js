'use strict';
const fs=require('fs'),assert=require('assert'),path=require('path'),crypto=require('crypto'),E=require('../../editor/campaign_editor');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'continuation/evidence/skills_roster_fix');
fs.mkdirSync(out,{recursive:true});
const native=fs.readFileSync(path.join(root,'build/naruto_role_swap_v0.1.5_EXPERIMENTAL.gba')),checks=[];
for(const filename of process.argv.slice(2)){
 const bytes=fs.readFileSync(filename),m=new E.Editor(bytes),l=m.layout(),campaign=m.campaign,sha=crypto.createHash('sha256').update(bytes).digest('hex');
 assert(campaign.chapters.length>0&&campaign.chapters.length<=48);
 const expected=Buffer.from(native.subarray(0x545458,0x545458+87*16));expected[5*16+4]=campaign.basicAttackPower;
 assert.deepEqual(bytes.subarray(l.skills,l.skills+87*16),expected,'Only the common basic attack has edition balancing; Whirlwind keeps its native cost and power.');
 let units=0;
 for(const chapter of campaign.chapters)for(let sub=0;sub<3;sub++)for(const a of m.actors(chapter.id,sub)){
  if(!a.id)continue;units++;
  const skills=Array.from({length:15},(_,i)=>m.byte(a.offset+16+i*4)).filter(Boolean);
  const allowed=a.id===12||(a.id===47&&chapter.aliases?.[47]!=='自来也');
  if(!allowed)assert(!skills.includes(41),`Whirlwind leaked into ${chapter.title}, actor ${a.id}`);
  if(a.id!==47)assert(skills.includes(5),'A shared native basic attack remains available.');
  if(!a.side){const p=l.loadouts+(chapter.id-56)*384+a.index*32;assert.equal(m.byte(p),1);assert.deepEqual(Array.from({length:15},(_,i)=>m.byte(p+1+i*2)).filter(Boolean),skills);}
 }
 const fixed=m.actors(56,0)[0];assert(fixed.id>0&&fixed.id<250);
 m.setActor(56,0,0,{...fixed,id:255});
 assert.equal(m.byte(l.loadouts),0,'Following a team slot must remove the old fixed-character loadout.');
 const project=m.project(sha),again=new E.Editor(bytes);again.importProject(project,sha);assert.deepEqual(again.build(),m.build());
 const rebuilt=new E.Editor(m.build());assert.equal(rebuilt.actors(56,0)[0].id,255);
 const added=new E.Editor(bytes),id=added.addCampaignBattle('新任务',56,56);
 for(let sub=0;sub<3;sub++)added.setActor(id,sub,0,{...added.actors(id,sub)[0],id:13});
 const extra=added.build(),reopened=new E.Editor(extra);assert.equal(reopened.byte(l.loadouts+(id-56)*384),0,'A new battle must not restore donor skills after replacing the actor.');
 const restored=new E.Editor(bytes);restored.importProject(added.project(sha),sha);assert.deepEqual(restored.build(),extra);
 const chained=added.addCampaignBattle('新任务',id,id),chain=added.build();
 for(const [key,size,a,b] of [['profiles',64,l.profiles+id*64,l.profiles+chained*64],['nameMap',256,l.nameMap+id*256,l.nameMap+chained*256],['loadouts',384,l.loadouts+(id-56)*384,l.loadouts+(chained-56)*384]])assert.deepEqual(chain.slice(a,a+size),chain.slice(b,b+size),'Chained new battle '+key);
 checks.push({filename,sha256:sha,checked_unit_records:units,all_three_configurations:true,whirlwind_ownership:'pass',native_skill_costs:'pass',fixed_to_team_slot_project_roundtrip:'pass',new_battle_replacement_disables_donor_skills:'pass',chained_new_battles_inherit_exported_data:'pass'});
}
fs.writeFileSync(path.join(out,'static_report.json'),JSON.stringify({result:'pass',kind:'ROM data and editor project checks; separate from actual gameplay',checks},null,2));
console.log(JSON.stringify(checks,null,2));
