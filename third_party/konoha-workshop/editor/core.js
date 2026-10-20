/* Naruto Konoha Senki editor. Local files only. No ROM assets are bundled. */
(function (root) {
'use strict';
const BASE=0x08000000, ACTORS=0x5461c4, RULES=0x594758, FONT=0x53d644;
const textCatalog=typeof module==='undefined'?root.NarutoTextCatalog:require('./text_catalog.js');
const names=['无','漩涡鸣人','宇智波佐助','春野樱','山中井野','奈良鹿丸','秋道丁次','旗木卡卡西','犬冢牙','油女志乃','日向雏田','日向宁次','李洛克','天天','我爱罗','勘九郎','手鞠','萨克','多斯','金','桃地再不斩','白'];
const hex=(n,w=6)=>n.toString(16).toUpperCase().padStart(w,'0');
const u32=(r,p)=>(r[p]|r[p+1]<<8|r[p+2]<<16|r[p+3]<<24)>>>0;
const le=n=>[n&255,n>>>8&255,n>>>16&255,n>>>24&255];
const fail=m=>{throw Error(m);};
function integer(n,min,max,label){if(!Number.isInteger(n)||n<min||n>max)fail(`${label}须为 ${min}～${max} 的整数`);return n;}
function fontSegments(r){const a=[];for(let i=0;i<31;i++){let p=FONT+i*8;a.push({index:i,start:r[p]|r[p+1]<<8,count:r[p+2],offset:u32(r,p+4)-BASE});}return a;}
function glyph(r,code){const s=fontSegments(r).find(s=>s.count&&code>=s.start&&code<s.start+s.count);if(!s)return null;return r.slice(s.offset+(code-s.start)*32,s.offset+(code-s.start+1)*32);}
function scanText(r,p){const start=p,tokens=[];for(let count=0;count<8192;count++){
 if(p>=r.length)fail('文字超出 ROM 边界');let a=r[p];if(!a)return {start,end:p,next:p+1,tokens};
 if(a===1||a===2){let n=a===1?2:3;if(p+n>r.length)fail('文字控制码不完整');tokens.push({raw:Array.from(r.slice(p,p+n)),control:true});p+=n;}
 else if(a>=0x80&&a<=0x9f){if(p+1>=r.length||!r[p+1])fail('双字节字码不完整');tokens.push({raw:[a,r[p+1]],code:a*256+r[p+1]});p+=2;}
 else {tokens.push({raw:[a],code:a});p++;}
 }fail('文字长度异常');}
function seedMapping(r){const result={};for(let id=1;id<names.length;id++){
 let p=u32(r,0x599280+id*4)-BASE;let ts=scanText(r,p).tokens.filter(t=>!t.control&&t.code>=0x8000);let chars=Array.from(names[id]);
 if(chars.length===ts.length)ts.forEach((t,i)=>result[t.code]=chars[i]);
 }return result;}
function catalogMapping(r){const result={};for(const s of fontSegments(r)){if(!s.count)continue;let h=2166136261;for(const b of r.slice(s.offset,s.offset+s.count*32))h=Math.imul(h^b,16777619)>>>0;const known=textCatalog?.segments.find(t=>t.start===s.start&&t.count===s.count&&t.signature===h.toString(16).padStart(8,'0'));if(known)for(let c=s.start;c<s.start+s.count;c++)if(textCatalog.mapping[c])result[c]=textCatalog.mapping[c];}return result;}
function decode(r,t,mapping){return t.tokens.map(t=>{
 if(t.control)return `{#${t.raw.map(n=>hex(n,2)).join('')}}`;
 if(t.code===10)return '\n';if(t.code===3)return '{#03}';
 if(t.code>=32&&t.code<127)return String.fromCharCode(t.code);
 if(t.code===0x8140)return '　';
 return mapping[t.code]||`{字${hex(t.code,4)}}`;
 }).join('');}
const lengths={0:1,2:4,3:2,4:4,7:5,8:2,9:2,10:2,11:6,12:6,13:5,14:3,15:2,16:1,17:2,18:5,20:3,21:8,22:2,23:4,24:4,25:4,26:3,27:3,28:3,29:3,30:2,31:2,33:5,34:4,35:3,50:5,51:2,52:8,53:9,54:8,55:3,56:7,57:6};
function graph(r,roots){const seen=new Map(),queue=roots.filter(p=>p>=0&&p<r.length),issues=[];let budget=50000;
 while(queue.length&&budget--){let p=queue.pop();if(seen.has(p))continue;const op=r[p];let n=lengths[op],node={offset:p,op};
 try{
  if([1,5,32].includes(op)){const text=scanText(r,p+(op===1?1:2));node.text=text;n=text.next-p;}
  if(op===19){let t=scanText(r,p+4),next=t.next;if(r[p+2])next=scanText(r,next+1).next;n=next-p;}
  if(op===6){node.targets=[u32(r,p+1)-BASE,u32(r,p+5)-BASE];n=9;}
  if(n===undefined)fail(`未支持的指令 ${hex(op,2)}`);if(p+n>r.length)fail('指令超出边界');node.length=n;
  if([7,13,50].includes(op))node.targets=[u32(r,p+1)-BASE];
  const branch={11:2,12:2,21:4,52:4,53:5,54:4,56:3,57:2}[op];if(branch!==undefined)node.targets=[u32(r,p+branch)-BASE];
  seen.set(p,node);if(node.targets)for(const t of node.targets){if(t<0||t>=r.length)fail('分支指针越界');queue.push(t);}
  if(![0,7,6].includes(op))queue.push(p+n);
 }catch(e){issues.push({offset:p,message:e.message});}
 }if(budget<=0)issues.push({message:'脚本扫描达到上限'});return {nodes:[...seen.values()].sort((a,b)=>a.offset-b.offset),issues};}
class Editor{
 constructor(bytes,label='game.gba'){
  this.rom=new Uint8Array(bytes);this.label=label;const r=this.rom;
  if(r.length<0x600000||r.length>0x2000000||String.fromCharCode(...r.slice(0xac,0xb0))!=='AUEJ')fail('请选择所提供的《火影忍者 木叶战记》简体汉化 ROM 或三人替代版。');
  if(u32(r,0x60c7c)!==0x0800bfc9||u32(r,0x599284)!==0x08001cd5||u32(r,FONT+4)!==0x0809d954)fail('此 ROM 的关卡或字库布局不同，暂不支持导出。');
  this.mapping={...seedMapping(r),...catalogMapping(r)};this.edits=new Map();this.textEdits=new Map();this.unicode={};this.history=[];this.featureSeed=null;
  // Editor-produced ROMs carry a small trailing catalogue so reopened text stays editable.
  if(String.fromCharCode(...r.slice(-8))==='NKEDIT01'){
   const size=u32(r,r.length-12),start=r.length-12-size;
   if(start>=0&&size<1000000){try{const meta=JSON.parse(new TextDecoder().decode(r.slice(start,start+size)));if(meta.version===1){Object.assign(this.mapping,meta.mapping);this.unicode=meta.unicode||{};this.featureSeed=meta.features||null;this.campaign=meta.campaign||null;}}catch(_){fail('编辑器目录损坏，请使用之前保存的 ROM。');}}
  }
  this.baseMapping={...this.mapping};this.characters=[];for(let i=1;i<=60;i++){const p=u32(r,0x599280+i*4)-BASE;if(p<0||p>=r.length)break;try{const text=scanText(r,p);this.characters.push({id:i,name:names[i]||decode(r,text,this.mapping).trim()||`未命名角色（编号 ${i}）`,text});}catch(_){break;}}
  this.cache=new Map();
 }
 byte(p){return this.edits.has(p)?this.edits.get(p):this.rom[p];}
 characterName(id){if(names[id])return names[id];const character=this.characters.find(c=>c.id===id);if(character){const value=decode(this.rom,character.text,this.mapping).replace(/　/g,' ').trim();if(value)return value;}return `未命名角色（编号 ${id}）`;}
 word(p){return (this.byte(p)|this.byte(p+1)<<8|this.byte(p+2)<<16|this.byte(p+3)<<24)>>>0;}
 put(p,value){integer(p,0,this.rom.length-1,'位置');integer(value,0,255,'数值');if(value===this.rom[p])this.edits.delete(p);else this.edits.set(p,value);}
 transaction(label,fn){const before={edits:new Map(this.edits),texts:new Map(this.textEdits),extra:this.snapshotExtra?.()};try{fn();this.history.push({label,...before});}catch(e){this.edits=before.edits;this.textEdits=before.texts;this.restoreExtra?.(before.extra);throw e;}}
 undo(){const b=this.history.pop();if(b){this.edits=b.edits;this.textEdits=b.texts;this.restoreExtra?.(b.extra);}return b?.label;}
 battleIds(){return [...Array.from({length:46},(_,i)=>i+1),...(this.campaignData?.()?.chapters||this.campaign?.chapters||[]).map(c=>c.id)];}
 sceneIds(){return [...Array.from({length:55},(_,i)=>i+1),...(this.campaignData?.()?.chapters||this.campaign?.chapters||[]).map(c=>c.id)];}
 layout(){return this.campaign?.layout||{maps:0x53d910,actors:ACTORS,rules:RULES,before:0x60c74,after:0x60d54,logic:0x60e34,events:0x60ef0,missionIndex:0x348dac,missionTables:[0x59aa5c,0x59d214,0x59e920]};}
 actorBase(stage,sub){if(!this.battleIds().includes(stage))fail('请选择有效战场');integer(sub,0,2,'配置');return this.layout().actors+stage*0x1aac+sub*0x8e4;}
 actors(stage,sub){let base=this.actorBase(stage,sub);return Array.from({length:12},(_,i)=>{const p=base+4+i*0xb8;return {index:i,offset:p,id:this.byte(p),side:this.byte(p+1),x:this.byte(p+2),y:this.byte(p+3),facing:this.byte(p+4),level:this.byte(p+15)};});}
 setActor(stage,sub,index,values){integer(index,0,11,'人物位置');const p=this.actorBase(stage,sub)+4+index*0xb8;
  const validIds=new Set([0,...this.characters.map(c=>c.id),250,251,252,253,254,255]);if(!validIds.has(values.id))fail('未支持的人物编号');
  for(const [key,max]of [['side',1],['x',63],['y',63],['facing',3],['level',99]])integer(values[key],key==='level'&&values.id>0&&values.id<250?1:0,max,key);
  // Preserve preset skill/stat/item bytes. Changing a preset character copies that character's template.
  const old=this.byte(p);if((values.id!==old||(values.side===1&&this.byte(p+1)!==1))&&values.id>0&&values.id<250){const t=0x54241c+values.id*0xb4;if(t+0xb4>ACTORS)fail('人物模板越界');for(let i=0;i<0x9c;i++)this.put(p+0x10+i,this.rom[t+0xc+i]);for(let i=0;i<9;i++)this.put(p+0xac+i,this.rom[t+0xa8+i]);}
  for(const [key,delta]of [['id',0],['side',1],['x',2],['y',3],['facing',4],['level',15]])this.put(p+delta,values[key]);
 }
 objects(stage,sub){const p=this.actorBase(stage,sub)+0x8a4;return Array.from({length:16},(_,i)=>({index:i,offset:p+i*4,type:this.byte(p+i*4),target:this.byte(p+i*4+1),x:this.byte(p+i*4+2),y:this.byte(p+i*4+3)}));}
 setObject(stage,sub,index,v){integer(index,0,15,'物品位置');const p=this.actorBase(stage,sub)+0x8a4+index*4;for(const[k,max]of[['type',7],['target',255],['x',63],['y',63]])integer(v[k],0,max,k);['type','target','x','y'].forEach((k,i)=>this.put(p+i,v[k]));}
 rules(stage,sub){this.actorBase(stage,sub);const p=this.layout().rules+stage*0xcc+sub*0x44;
  return {offset:p,turn:this.byte(p),groups:[0,1].map(g=>Array.from({length:4},(_,i)=>{let q=p+4+g*32+i*8;return {index:i,offset:q,type:this.byte(q),a:this.byte(q+1),b:this.byte(q+2),c:this.byte(q+3),pointer:this.word(q+4)-BASE};}))};}
 setRule(stage,sub,group,index,v){integer(group,0,1,'条件分组');integer(index,0,3,'条件位置');const p=this.rules(stage,sub).groups[group][index].offset;
  if(![0,1,2,3,4,5,6,7,8,9,10].includes(v.type))fail('条件类型无效');for(const k of ['a','b','c'])integer(v[k],0,255,k);
  if([1,3,5,7,8,9].includes(v.type)&&v.a>1)fail('阵营须为我方或敌方');if(v.type===6&&v.a>15)fail('物品序号须为 0～15');
  if(v.type===3&&!this.characters.some(c=>c.id===v.b))fail('指定人物编号无效');if(v.type===10){if(!this.campaign?.capabilities?.arrivalRules)fail('此游戏版本不支持到达指定位置条件');if(!this.characters.some(c=>c.id===v.a))fail('请选择撤离的我方人物');const m=this.mapData(stage);if(v.b>=m.width||v.c>=m.height)fail('撤离点超出地图');}
  if(v.type&&!(this.word(p+4)>=BASE&&this.word(p+4)<BASE+this.rom.length))fail('这个空条件没有说明文字指针；请复制已有条件后再编辑。');
  [v.type,v.a,v.b,v.c].forEach((n,i)=>this.put(p+i,n));
 }
 copyRule(stage,sub,group,index,from){const p=this.rules(stage,sub).groups[group][index].offset;integer(from,0,3,'来源');const q=this.rules(stage,sub).groups[group][from].offset;for(let i=0;i<8;i++)this.put(p+i,this.byte(q+i));}
 setTurn(stage,sub,n){this.put(this.rules(stage,sub).offset,integer(n,0,255,'回合限制'));}
 scripts(scene){if(!this.sceneIds().includes(scene))fail('请选择有效剧情');if(this.cache.has(scene))return this.cache.get(scene);const roots=[this.layout().before,this.layout().after].map(t=>u32(this.rom,t+scene*4)-BASE);if(this.battleIds().includes(scene))roots.push(...[this.layout().logic,this.layout().events].map(t=>u32(this.rom,t+scene*4)-BASE));const g=graph(this.rom,roots);this.cache.set(scene,g);return g;}
 textValue(entry){return this.textEdits.get(entry.key)?.value??decode(this.rom,entry.text,this.mapping);}
 speaker(entry){return this.textEdits.get(entry.key)?.speaker||0;}
 dialogues(scene){return this.scripts(scene).nodes.filter(n=>[1,5,32].includes(n.op)&&(n.op!==32||n.text.tokens.length)).map(n=>({key:`script:${n.offset}`,kind:'script',offset:n.offset,length:n.length,prefix:Array.from(this.rom.slice(n.offset,n.text.start)),op:n.op,text:n.text}));}
 ruleText(rule){const ptr=rule.pointer;if(ptr<0||ptr>=this.rom.length)return null;try{return {key:`pointer:${rule.offset+4}`,kind:'pointer',offset:rule.offset+4,text:scanText(this.rom,ptr)};}catch(_){return null;}}
 missionTexts(stage,sub){this.actorBase(stage,sub);const index=this.rom[this.layout().missionIndex+stage]+sub;return this.layout().missionTables.map((t,i)=>[t,['任务标题','任务说明','任务提示'][i]]).map(([table,label])=>{const offset=table+index*4,ptr=this.word(offset)-BASE;return {key:`pointer:${offset}`,kind:'pointer',offset,label,text:scanText(this.rom,ptr)};});}
 setText(entry,value,speaker=0){if(entry.kind==='script'&&(entry.op!==1||entry.length<5))fail('当前版本仅写入普通对话；选择菜单与过短片段暂为只读。');if(typeof value!=='string'||value.length>16000)fail('文字过长');
  integer(speaker,0,60,'说话人');if(entry.kind!=='script'&&speaker)fail('条件说明不使用说话人');
  if(value.includes('【分页】')&&(entry.kind!=='script'||!speaker))fail('分页对话需要先选择说话人');
  const original=decode(this.rom,entry.text,this.mapping);if(value===original&&!speaker)this.textEdits.delete(entry.key);else this.textEdits.set(entry.key,{...entry,value,speaker});}
 tokenize(value){const out=[];for(let i=0;i<value.length;){const tail=value.slice(i),raw=tail.match(/^\{#([0-9a-f]+)\}/i),code=tail.match(/^\{字([0-9a-f]{4})\}/i);
  if(raw){const bytes=raw[1].match(/../g)?.map(n=>parseInt(n,16));if(!bytes||raw[1].length%2||!([1,2,3].includes(bytes[0]))||bytes.length!==({1:2,2:3,3:1}[bytes[0]]))fail('控制码格式错误；请保留原控制码');out.push({raw:bytes});i+=raw[0].length;}
  else if(code){const n=parseInt(code[1],16);if(n<0x8000||!glyph(this.rom,n))fail('字形编号不存在');out.push({raw:[n>>>8,n&255]});i+=code[0].length;}
  else {const ch=String.fromCodePoint(value.codePointAt(i));if(ch==='{'||ch==='}')fail('花括号用于游戏字码，请使用全角括号');if(ch==='\r'){i++;continue;}if(ch==='\n')out.push({raw:[10]});else if(ch==='　')out.push({raw:[0x81,0x40]});else if(ch.codePointAt(0)>=32&&ch.codePointAt(0)<127)out.push({raw:[ch.charCodeAt(0)]});else if(ch.codePointAt(0)<32)fail('文字包含不支持的控制字符');else out.push({char:ch});i+=ch.length;}
 }return out;}
 build(glyphProvider){
  const changes=[...this.edits],textChanges=[...this.textEdits.values()];if(!changes.length&&!textChanges.length&&!this.hasExtraChanges?.())return this.rom.slice();
  let output=Array.from(this.rom);for(const[p,v]of changes)output[p]=v;
  const append=bytes=>{while(output.length%4)output.push(255);const p=output.length;for(const byte of bytes)output.push(byte);if(output.length>0x1000000)fail('当前版本仅支持导出 16 MB 以内的 ROM');return p;};
  const mapping={...this.mapping},unicode={...this.unicode};const reverse={};for(const[k,v]of Object.entries(mapping))reverse[v]=+k;
  const tokens=[...textChanges,...(this.extraTexts?.()||[])].map(t=>this.tokenize(t.value.replaceAll('【分页】',''))),newChars=[...new Set(tokens.flat().filter(t=>t.char&&!reverse[t.char]).map(t=>t.char))];
  const slots=fontSegments(this.rom).filter(s=>!s.count),starts=[0x9d40,0x9e40,0x9f40,0x8440,0x8540].filter(start=>!fontSegments(this.rom).some(s=>s.count&&start<s.start+s.count&&start+189>s.start));
  if(newChars.length>Math.min(slots.length,starts.length)*189)fail('新汉字数量超过剩余字库容量，请减少新字或使用原游戏字形。');
  for(let block=0;block*189<newChars.length;block++){
   const chars=newChars.slice(block*189,(block+1)*189),bytes=[];for(let j=0;j<chars.length;j++){let ch=chars[j],code=starts[block]+j;const g=glyphProvider(ch);if(!g||g.length!==32||!g.some(v=>v))fail(`无法生成汉字：${ch}`);bytes.push(...g);mapping[code]=ch;unicode[ch]=code;reverse[ch]=code;}
   const data=append(bytes),p=FONT+slots[block].index*8,start=starts[block];output.splice(p,8,start&255,start>>>8,chars.length,0,...le(BASE+data));
  }
  // Reuse the entry's native bytes for retained characters, including duplicate
  // codes that display the same Unicode label. A lookup correction must not
  // silently change unrelated original glyphs when one sentence is edited.
  const encode=(value,entry)=>{const ts=this.tokenize(value);if(ts.length>8191)fail('单页文字过长，请分页后再导出');let original=[],prefix=0,suffix=0;const hints=new Map(),key=t=>t.char||`raw:${t.raw.join(',')}`;
   if(entry){original=this.tokenize(decode(this.rom,entry.text,this.mapping));while(prefix<ts.length&&prefix<original.length&&key(ts[prefix])===key(original[prefix]))prefix++;while(suffix<ts.length-prefix&&suffix<original.length-prefix&&key(ts[ts.length-1-suffix])===key(original[original.length-1-suffix]))suffix++;original.forEach((t,i)=>{if(t.char){if(!hints.has(t.char))hints.set(t.char,new Set());hints.get(t.char).add(entry.text.tokens[i].raw.join(','));}});}
   return ts.flatMap((t,i)=>{if(t.raw)return t.raw;if(i<prefix)return entry.text.tokens[i].raw;if(i>=ts.length-suffix)return entry.text.tokens[original.length-(ts.length-i)].raw;const choices=hints.get(t.char);if(choices?.size===1)return [...choices][0].split(',').map(Number);return [reverse[t.char]>>>8,reverse[t.char]&255];});};
  textChanges.forEach((entry,i)=>{
   if(entry.kind==='script'){const continuation=BASE+entry.offset+entry.length,code=[];for(const page of entry.value.split('【分页】')){if(entry.speaker)code.push(2,0,entry.speaker,1,8,entry.speaker);code.push(...entry.prefix,...encode(page,entry),0);}code.push(7,...le(continuation));const dest=append(code);output.splice(entry.offset,5,7,...le(BASE+dest));}
   else {const dest=append([...encode(entry.value,entry),0]);output.splice(entry.offset,4,...le(BASE+dest));}
  });
  this.buildExtras?.({output,append,encode});
  const meta=new TextEncoder().encode(JSON.stringify({version:1,mapping,unicode,features:this.featureMetadata?.(),campaign:this.campaignData?.()||this.campaign}));if(meta.length>=1000000)fail('新增事件的工程目录超过 1 MB，请减少新增对白');if(output.length+meta.length+12>=0x1000000)fail('新增内容超过 16 MB 容量');for(const byte of meta)output.push(byte);output.push(...le(meta.length),...Array.from('NKEDIT01').map(c=>c.charCodeAt(0)));
  if(output.length>=0x1000000)fail('导出含目录后超过 16 MB 容量，请减少新增内容');
  return new Uint8Array(output);
 }
 project(hash){return {format:'naruto-stage-project',version:1,baseline:{name:this.label,sha256:hash,size:this.rom.length},edits:[...this.edits].sort((a,b)=>a[0]-b[0]).map(([offset,value])=>({offset,before:this.rom[offset],value})),texts:[...this.textEdits.values()].map(e=>({key:e.key,value:e.value,speaker:e.speaker})),features:this.exportFeatures?.()};}
 importProject(project,hash){if(project.format!=='naruto-stage-project'||project.version!==1||project.baseline?.sha256!==hash||project.baseline?.size!==this.rom.length)fail('工程与当前 ROM 不匹配，请打开保存工程时使用的同一份 ROM。');
  const allowed=new Set();for(const s of this.battleIds())for(let sub=0;sub<3;sub++){let b=this.actorBase(s,sub);for(let i=0;i<12;i++)for(let j=0;j<0xb4;j++)allowed.add(b+4+i*0xb8+j);for(let j=0;j<64;j++)allowed.add(b+0x8a4+j);let p=this.rules(s,sub).offset;allowed.add(p);for(let i=0;i<64;i++)allowed.add(p+4+i);}
  for(const b of this.extra?.campaignAdditions||[]){for(let i=0;i<32;i++)allowed.add(this.layout().maps+b.id*32+i);for(let sub=0;sub<3;sub++){for(let i=0;i<0x8e4;i++)allowed.add(this.actorBase(b.id,sub)+i);for(let i=0;i<0x44;i++)allowed.add(this.rules(b.id,sub).offset+i);}const root=u32(this.rom,this.layout().after+b.previous*4)-BASE;for(const n of graph(this.rom,[root]).nodes)if(n.op===26){allowed.add(n.offset+1);allowed.add(n.offset+2);}}
  if(this.layout().modifiers)for(const scene of this.battleIds())for(let i=0;i<6;i++)allowed.add(this.layout().modifiers+scene*6+i);
  if(this.layout().loadouts)for(const e of project.edits||[]){const p=this.layout().loadouts;if(e.offset>=p&&e.offset<p+48*384&&e.value===0)allowed.add(e.offset);}
  if(this.musicCommands)for(const scene of this.sceneIds())for(const c of this.musicCommands(scene,{part:'all'}))allowed.add(c.offset+1);
  const entries=new Map();for(const scene of this.sceneIds())for(const e of this.dialogues(scene))entries.set(e.key,e);for(const s of this.battleIds())for(let sub=0;sub<3;sub++){for(const e of this.missionTexts(s,sub))entries.set(e.key,e);for(const rule of this.rules(s,sub).groups.flat()){let e=this.ruleText(rule);if(e)entries.set(e.key,e);}}
  this.transaction('载入工程',()=>{this.edits.clear();this.textEdits.clear();for(const e of project.edits||[]){if(!allowed.has(e.offset)||this.rom[e.offset]!==e.before)fail('工程的原字节或修改位置校验失败');this.put(e.offset,e.value);}for(const s of this.battleIds())for(let sub=0;sub<3;sub++)for(const rule of this.rules(s,sub).groups.flat()){const entry=this.ruleText(rule);if(entry)entries.set(entry.key,entry);}for(const t of project.texts||[]){const e=entries.get(t.key);if(!e)fail('找不到工程中的文字');this.setText(e,t.value,t.speaker||0);}this.loadFeatures?.(project.features);});
 }
}
function ips(before,after){if(after.length>=0x1000000)fail('IPS 仅支持小于 16 MB 的文件');const bytes=[80,65,84,67,72];for(let p=0;p<after.length;){if(p<before.length&&before[p]===after[p]){p++;continue;}let start=p,chunk=[];if(start===0x454f46){start--;chunk.push(after[start]);}while(p<after.length&&chunk.length<65535&&(p>=before.length||before[p]!==after[p]))chunk.push(after[p++]);bytes.push(start>>>16&255,start>>>8&255,start&255,chunk.length>>>8,chunk.length&255,...chunk);}bytes.push(69,79,70);return new Uint8Array(bytes);}
const api={Editor,graph,scanText,decode,glyph,fontSegments,names,hex,u32,ips,BASE,textCatalog};if(typeof module!=='undefined')module.exports=api;else root.NarutoEditor=api;
})(typeof window==='undefined'?globalThis:window);
