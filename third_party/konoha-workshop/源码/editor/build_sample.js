/* Rebuild the original example from the user's v0.1.5 ROM. No ROM is embedded. */
'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),E=require('./core.js');
const root=path.resolve(__dirname,'..'),out=path.join(root,'build'),story=require('./sample_story.json');
const baseline=fs.readFileSync(path.join(out,'naruto_role_swap_v0.1.5_EXPERIMENTAL.gba'));
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
if(digest(baseline)!=='52a33419f601b2f01b26ba13d9305b4a0aebde634a907e85577ba9c6c2165250')throw Error('Unexpected v0.1.5 baseline');
const font=JSON.parse(fs.readFileSync(path.join(__dirname,'sample_glyphs.json'),'utf8'));
let data=Array.from(baseline),entries=[];
const le=n=>[n&255,n>>>8&255,n>>>16&255,n>>>24&255],put=(p,bytes)=>data.splice(p,bytes.length,...bytes);
const append=bytes=>{while(data.length%4)data.push(255);let p=data.length;data.push(...bytes);return p;};
function sequence(lines,preamble=[],ending=[]){let code=[...preamble],offsets=[];for(const line of lines){offsets.push({relative:code.length,line});code.push(1,...Array.from('DIALOG').map(c=>c.charCodeAt(0)),0);}code.push(...ending,0);const p=append(code);entries.push(...offsets.map(e=>({offset:p+e.relative,...e.line})));return p;}
const before=sequence(story.before,[27,4,0,34,1,2,1,34,1,3,1,35,1,1,35,1,2,35,1,3,31,0],[22,0]);
const after=sequence(story.after,[27,13,0],[26,2,0]);
const empty=append([0]);
for(const[p,value]of [[0x60c78,before],[0x60d58,after],[0x60e38,empty],[0x60ef4,empty]])put(p,le(E.BASE+value));
if(data[0x8f698]!==0x36||data[0x8f699]!==0x20)throw Error('Unexpected new-game chapter instruction');
put(0x8f698,[1,0x20]); // The example starts at the new first mission after choosing the trio.
const m=new E.Editor(new Uint8Array(data),'雾港信标_结构基底.gba');
m.transaction('原创第一关出场配置',()=>{
 for(let sub=0;sub<3;sub++){
  const a=m.actors(1,sub);
  // Use all three ordinary allies, two level-one enemies, and no escort actor.
  const positions=[[10,9],[10,6],[4,6],[6,7],[11,4],[11,10]];
  for(let i=0;i<12;i++){
   let id=i<3?i+1:i===4?17:i===5?18:0,xy=positions[i]||[0,0];
   m.setActor(1,sub,i,{...a[i],id,side:i===4||i===5?1:0,level:id?1:0,x:xy[0],y:xy[1],facing:a[i].facing});
  }
  const r=m.rules(1,sub);m.setTurn(1,sub,0);
  for(const[i,entry]of m.missionTexts(1,sub).entries())m.setText(entry,story.mission_texts[i]);
  for(let g=0;g<2;g++){
   if(!r.groups[g][0].type)m.copyRule(1,sub,g,0,0);
   for(let i=0;i<4;i++){
    const q=r.groups[g][i];
    // Empty subconfigurations inherit their description pointer from config zero.
    if(i===0&&q.pointer<0){const from=m.rules(1,0).groups[g][0].offset+4;for(let j=0;j<4;j++)m.put(q.offset+4+j,m.byte(from+j));}
    m.setRule(1,sub,g,i,{type:i===0?1:0,a:g===0?1:0,b:0,c:0});
   }
   const rule=m.rules(1,sub).groups[g][0],entry=m.ruleText(rule);m.setText(entry,g===0?'击退两名破坏者':'我方全员倒下');
  }
 }
});
for(const line of entries){const text=E.scanText(m.rom,line.offset+1);m.setText({key:`script:${line.offset}`,kind:'script',offset:line.offset,length:text.next-line.offset,prefix:[1],op:1,text},line.text,line.speaker);}
const result=m.build(ch=>{if(!font[ch])throw Error(`Missing glyph ${ch}`);return Uint8Array.from(font[ch]);});
const file=path.join(out,'naruto_fog_harbor_sample_v0.1.0.gba');fs.writeFileSync(file,result);fs.writeFileSync(file.replace('.gba','.ips'),E.ips(baseline,result));
const original=fs.readFileSync(path.join(root,'originals/naruto_konoha_bearteam_simp.gba'));fs.writeFileSync(file.replace('.gba','_原版基底.ips'),E.ips(original,result));
const reopened=new E.Editor(result);const reachable=reopened.dialogues(1);if(reachable.filter(e=>e.op===1).length!==[...story.before,...story.after].reduce((n,line)=>n+line.text.split('【分页】').length,0))throw Error('Unexpected sample dialogue count');
const report={title:story.title,baseline_sha256:digest(baseline),target_sha256:digest(result),target_size:result.length,before_root:before,after_root:after,dialogue_count:entries.length,native_battle_condition:'opposite-side annihilation',new_game_starts_scene:1,ending_scene:2,runtime:'not_run'};fs.writeFileSync(path.join(out,'sample_story_manifest.json'),JSON.stringify(report,null,2));console.log(report);
