/* Story catalogue: milestone order comes from native progress commands and transitions.
 * Reused scene roots are separate rows. Optional routes stay in separate groups. */
(function(root){
'use strict';
const E=typeof module==='undefined'?root.NarutoEditor:require('./features.js'),{u32,BASE}=E;
const proto=E.Editor.prototype;
E.directions=[[0,'上'],[2,'下'],[3,'左'],[1,'右']];
const story=(scene,title,at,progress)=>({scene,title,kind:'story',part:'before',root:at,progress});
const battle=(scene,title,progress)=>({scene,title,kind:'battle',progress});
const milestones=[
 story(54,'一乐拉面 · 忍者故事开场',0x49e9e,0),story(50,'忍者学校 · 毕业说明',0x3627b,0),
 battle(40,'伊鲁卡的移动练习',5),battle(41,'与木叶丸练习攻击',10),story(41,'木叶丸的约定',0x31feb,25),
 story(54,'一乐拉面 · 修炼前',0x4a96a,27),battle(42,'体力与查克拉练习',30),battle(43,'高级战斗与影分身',40),
 story(50,'第七班成立',0x36fde,45),battle(44,'卡卡西的宝箱考验',49),battle(45,'团队合作考验',59),
 story(54,'一乐拉面 · 第七班成立后',0x4afa7,69),story(50,'第一次任务',0x37bc0,70),battle(9,'抓猫任务',80),
 story(50,'木叶丸的新委托',0x393cb,89),battle(15,'保护木叶丸',89),story(50,'采收委托',0x3a83f,90),battle(20,'挖甘薯',90),
 story(50,'新的修炼任务',0x3b232,100),battle(18,'森林中的老虎',100),story(50,'出发前往波之国',0x3fc0d,110),
 battle(1,'前往波之国 · 鬼兄弟',120),battle(2,'波之国 · 卡多的手下',130),battle(3,'再不斩 · 救出卡卡西',140),
 story(51,'达兹纳家 · 休养与修炼',0x41402,150),battle(4,'爬树修炼与森林遭遇',155),
 story(51,'达兹纳家 · 晚餐',0x43097,159),story(51,'达兹纳家 · 修炼归来',0x43777,169),
 story(51,'达兹纳家 · 绑架者来袭',0x44965,172),battle(5,'击退草鞋与草履',170),
 battle(6,'桥上的战斗',179),battle(7,'白 · 魔镜冰晶',190),battle(8,'卡卡西与再不斩',211),
 story(51,'波之国任务结束',0x452ef,225),story(50,'返回木叶 · 密书委托',0x3b911,230),battle(23,'找出密书',230),
 story(50,'木叶的新委托',0x3c11d,240),battle(12,'再次寻找小虎',240),story(50,'寻找不明忍者',0x3cd02,250),battle(11,'不明忍者',250),
 story(50,'中忍考试前',0x3d5d5,260),battle(9,'中忍考试前的抓猫任务',261),battle(31,'与李洛克交手',261),
 story(52,'中忍考试 · 第一场',undefined,270),battle(52,'第一场考试的特殊流程',270),
 battle(24,'死亡森林 · 蜈蚣',280),battle(25,'卷轴争夺分支 · 井野小队',285),battle(26,'卷轴争夺分支 · 牙的小队',285),battle(27,'死亡森林 · 宁次小队',290),
 battle(28,'死亡森林 · 大蛇',300),battle(29,'死亡森林 · 音忍',319),battle(30,'死亡森林 · 雨忍',329),battle(46,'死亡森林 · 最后冲刺',339),
 story(53,'中央塔 · 天地卷轴',undefined,340),story(50,'第二场考试结束',0x40cf8,360)
];
proto.flowItems=function(){const list=[];let n=0;const start=this.rom[0x8f698]===1?milestones.findIndex(x=>x.scene===1):0;
 for(const source of milestones.slice(start)){const m={...source};if(m.scene===1)m.title=this.textValue(this.missionTexts(1,0)[0]).replace(/[　\n]/g,'').trim();if(m.kind==='battle'){
  // Scene 52 uses its own exam flow and has no editable battlefield descriptor.
  if(m.scene>46){list.push({...m,kind:'story',part:'after',id:`main:${n++}`,group:'主线流程',title:'中忍考试 · 第一场结束'});continue;}
  for(const [kind,part,prefix]of[['story','before','战前'],['battle',null,'战场'],['story','after','战后']]){if(kind==='story'&&!this.dialogueSequence(m.scene,{part,progress:m.progress}).length)continue;list.push({...m,kind,part,id:`main:${n++}`,group:'主线流程',title:`${m.title} · ${prefix}`});}
 }else list.push({...m,id:`main:${n++}`,group:'主线流程'});}
 const used=new Set(list.filter(m=>m.kind==='battle').map(m=>m.scene));
 for(let s=1;s<=46;s++)if(!used.has(s))list.push({id:`branch:${s}`,scene:s,title:s>=32&&s<=38?`竞技场 ${s-30}`:s===39?'卡卡西的自由演习':this.textValue(this.missionTexts(s,0)[0]).replace(/[　\n]/g,'').trim(),kind:'branch',part:'all',group:s>=32&&s<=38?'竞技场（独立分支）':'可选任务与自由演习'});
 for(const [scene,at,progress,title]of[[54,0x4b5b5,80,'一乐拉面 · 首次任务期间'],[54,0x4b957,229,'一乐拉面 · 后期对话']])list.push({id:`branch:story:${scene}:${progress}`,scene,root:at,progress,title,kind:'story',part:'before',group:'可选地点对话'});
 for(const c of this.campaignData?.()?.chapters||this.campaign?.chapters||[])for(const [kind,part,suffix]of[['story','before','战前'],['battle',null,'战场'],['story','after','战后']])list.push({id:`campaign:${c.id}:${kind}:${part}`,scene:c.id,title:`${c.title} · ${suffix}`,kind,part,group:'少年篇续章'});
 return list;
};
proto.dialogueSequence=function(scene,{part='all',root:customRoot,progress}={}){
 const r=this.rom,entries=new Map(this.dialogues(scene).map(e=>[e.offset,e])),out=[],seen=new Set(),walked=new Set();let budget=50000;
 const l=this.layout(),tables=part==='all'?[l.before,l.after,...(this.battleIds().includes(scene)?[l.events]:[])]:[{before:l.before,after:l.after,battle:l.events}[part]];
 const roots=customRoot!==undefined?[customRoot]:tables.filter(Boolean).map(t=>u32(r,t+scene*4)-BASE);
 const nodes=new Map(E.graph(r,roots).nodes.map(n=>[n.offset,n]));
 function walk(p,state={speaker:0,expression:1,background:undefined},stack=[]){state={...state};while(budget-->0){const visit=p+':'+stack.join(',');if(walked.has(visit))return;walked.add(visit);const n=nodes.get(p);if(!n)return;
  if(n.op===2){state.speaker=r[p+2];state.expression=r[p+3];}
  if(n.op===3&&(r[p+1]===255||r[p+1]===0))state.speaker=0;
  if(n.op===30)state.background=r[p+1];
  if(entries.has(p)&&!seen.has(p)){out.push({...entries.get(p),...state});seen.add(p);}
  if(n.op===0){if(!stack.length)return;p=stack.at(-1);stack=stack.slice(0,-1);continue;}
  if(n.op===7){p=n.targets[0];continue;}
  if(n.op===13){stack=[...stack,p+n.length];p=n.targets[0];continue;}
  if(n.op===21&&progress!==undefined){const a=progress&255,b=(r[p+2]|r[p+3]<<8)&255,match=[a===b,a!==b,a>b,a>=b,a<b,a<=b][r[p+1]];p=match?n.targets[0]:p+n.length;continue;}
  if(n.targets&&n.op!==50){if(n.op!==6)walk(p+n.length,state,[...stack]);for(const q of n.targets)walk(q,state,[...stack]);return;}
  if(n.op===50)walk(n.targets[0],state,[]);
  p+=n.length;
 }}
 for(const p of roots)walk(p);
 return out;
};
if(typeof module!=='undefined')module.exports=E;
})(typeof window==='undefined'?globalThis:window);
