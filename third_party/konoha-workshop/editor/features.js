/* Native map resources and battle event compiler. No assets are bundled. */
(function(root){
'use strict';
const E=typeof module==='undefined'?root.NarutoEditor:require('./core.js');
const {BASE,u32}=E,MAPS=0x53d910;
const U16=(r,p)=>r[p]|r[p+1]<<8,le=n=>[n&255,n>>>8&255,n>>>16&255,n>>>24&255];
const check=(v,lo,hi,name)=>{if(!Number.isInteger(v)||v<lo||v>hi)throw Error(`${name}须为 ${lo}～${hi} 的整数`);return v;};
const clone=v=>JSON.parse(JSON.stringify(v));
function decompress(r,p){
 if(p<0||p+4>r.length||r[p]!==16)throw Error('图像压缩格式或指针不正确');
 const n=r[p+1]|r[p+2]<<8|r[p+3]<<16;if(n>0x20000)throw Error('图像资源过大');
 const out=new Uint8Array(n);p+=4;let k=0;
 while(k<n){if(p>=r.length)throw Error('压缩资源不完整');const flags=r[p++];for(let bit=7;bit>=0&&k<n;bit--){
  if(flags>>bit&1){if(p+2>r.length)throw Error('压缩资源不完整');const a=r[p++],b=r[p++],dist=((a&15)<<8|b)+1,count=(a>>4)+3;if(dist>k)throw Error('压缩资源回溯越界');for(let j=0;j<count&&k<n;j++,k++)out[k]=out[k-dist];}
  else {if(p>=r.length)throw Error('压缩资源不完整');out[k++]=r[p++];}
 }}return out;
}
function compressLiteral(bytes){const o=[16,bytes.length&255,bytes.length>>>8&255,bytes.length>>>16&255];for(let i=0;i<bytes.length;i+=8)o.push(0,...bytes.slice(i,i+8));while(o.length%4)o.push(0);return o;}
function init(m){if(!m.extra)m.extra={maps:{},events:clone(m.featureSeed?.events||{}),bases:clone(m.featureSeed?.bases||{}),glyphCorrections:{},dirty:false};return m.extra;}
function tilePixel(gfx,entry,x,y,bpp=4){if(entry&1024)x=7-x;if(entry&2048)y=7-y;const p=(entry&1023)*(bpp===8?64:32)+y*(bpp===8?8:4)+(bpp===8?x:x>>1);let c=bpp===8?gfx[p]:(gfx[p]>>((x&1)*4))&15;return c?c+(bpp===8?0:(entry>>>12)*16):0;}
function rgbaColor(pal,index){const v=U16(pal,index*2);return [(v&31)*255/31,(v>>>5&31)*255/31,(v>>>10&31)*255/31,255];}
function renderTiles(gfx,pal,map,w,h,bpp=4){const out=new Uint8ClampedArray(w*h*4);for(let y=0;y<h;y++)for(let x=0;x<w;x++){const entry=U16(map,((y>>3)*32+(x>>3))*2),c=tilePixel(gfx,entry,x&7,y&7,bpp),rgba=rgbaColor(pal,c);out.set(rgba,(y*w+x)*4);}return {width:w,height:h,pixels:out};}
const proto=E.Editor.prototype;
// Names come from the same native tables used by the pickup windows.
E.objectTypes=[[0,'空位（不放置）'],[1,'忍具'],[2,'强化素材'],[3,'专属修行卷轴'],[4,'认识卡（人物图鉴）'],[5,'机关宝箱'],[6,'特殊机关（卷轴外观）'],[7,'剧情物件']];
const mechanismNames={1:'开门机关',2:'空箱 / 开门分支',3:'停止傀儡的机关',4:'开门机关（另一组）',5:'空箱 / 开门分支（另一组）',6:'停止傀儡的机关（另一组）',7:'密书',8:'空箱 / 密书分支',9:'甘薯（收集计数）',10:'发现奖励（强化剂剧情）',11:'空事件',12:'宝箱教学',13:'认识卡教学'};
proto.objectChoices=function(type){const table=(base,count)=>Array.from({length:count},(_,i)=>{const id=i+1,p=u32(this.rom,base+id*4)-BASE;return [id,E.decode(this.rom,E.scanText(this.rom,p),this.mapping).trim()];});
 if(type===1)return table(0x599634,93);if(type===2)return table(0x5a7e8c,16);
 if(type===3)return Array.from({length:21},(_,i)=>[i+1,`${this.characterName(i+1)}的专属修行卷轴`]);
 if(type===4)return table(0x599280,62).map(([id,name])=>[id,`${name}的认识卡`]);
 if([5,6,7].includes(type))return Object.entries(mechanismNames).map(([id,name])=>[+id,name]);return [];
};
proto.objectName=function(o){return o.type?(this.objectChoices(o.type).find(([id])=>id===o.target)?.[1]||`未识别内容（原编号 ${o.target}）`):'空位';};
proto.objectHint=function(o){if(!o.type)return '选择类别和具体物品，再点地图放置。';if(o.type===1)return '拾取后获得忍具，沿用游戏的持有上限和人物装备限制。';if(o.type===2)return '拾取后获得强化素材，用于忍具强化。';if(o.type===3)return '选择卷轴所属人物即可，不是修行技能编号。所属人物须已加入队伍，且尚未解锁专属修行；三人替代版会按开局选择交换归属。';if(o.type===4)return '用于人物图鉴，不是加入队伍的招募卡；已取得的认识卡不会再次生成。';return '调用原版机关或教学脚本，可能开门、停止傀儡或触发对话。效果依赖原关卡，不能当作通用奖励搬到任意地图。';};
proto.objectSpawns=function(stage,sub){let min=0,max=0;return this.objects(stage,sub).filter(o=>o.type).map(o=>{const conditional=[3,4].includes(o.type),row={...o,name:this.objectName(o),conditional,spawnMin:min+1,spawnMax:max+1};max++;if(!conditional)min++;return row;});};
proto.objectSlot=function(stage,sub,index){return this.objectSpawns(stage,sub).filter(o=>o.spawnMin<=index+1&&o.spawnMax>=index+1);};
proto.snapshotExtra=function(){return this.extra?clone(this.extra):null;};
proto.restoreExtra=function(v){this.extra=v?clone(v):undefined;this.mapping={...this.baseMapping,...(this.extra?.glyphCorrections||{})};};
proto.setGlyphLabel=function(code,label){check(code,0x8000,0x9fff,'字码');if(!E.glyph(this.rom,code))throw Error('原 ROM 没有这个字形');if(typeof label!=='string'||Array.from(label).length!==1||/[\s{}]/.test(label))throw Error('请输入一个对应的汉字或符号');const a=init(this);a.glyphCorrections??={};if(label===this.baseMapping[code])delete a.glyphCorrections[code];else a.glyphCorrections[code]=label;this.mapping={...this.baseMapping,...a.glyphCorrections};a.dirty=true;};
proto.renderPortrait=function(id,expression=1){check(id,1,60,'人物');check(expression,0,4,'表情');const key=`portrait:${id}:${expression}`;if(this.cache.has(key))return this.cache.get(key);const r=this.rom,p=0x5a4dec+id*40+expression*8,gfx=decompress(r,u32(r,p)-BASE),pal=u32(r,p+4)-BASE;if(gfx.length!==6400||pal<0||pal+128>r.length)throw Error('人物头像资源不完整');const pixels=new Uint8ClampedArray(80*80*4);let done=false;for(let i=0;i<20;i++){const q=0x4643c0+i*20,tile=u32(r,q);if(tile===65535){done=true;break;}const x=U16(r,q+4),y=U16(r,q+6),w=U16(r,q+8),h=U16(r,q+10);if(x+w>80||y+h>80||!w||!h)throw Error('头像拼块超出范围');for(let yy=0;yy<h;yy++)for(let xx=0;xx<w;xx++){const src=tile*32+((yy>>3)*(w>>3)+(xx>>3))*64+(yy&7)*8+(xx&7),c=gfx[src];if(src>=gfx.length||c>=64)throw Error('头像像素超出范围');if(c)pixels.set(rgbaColor(r.slice(pal,pal+128),c),((y+yy)*80+x+xx)*4);}}if(!done)throw Error('头像拼块没有结束');const result={width:80,height:80,pixels,placeholder:u32(r,p)===0x08408bd8};this.cache.set(key,result);return result;};
proto.hasExtraChanges=function(){return init(this).dirty;};
proto.mapData=function(stage){
 if(!this.battleIds().includes(stage))throw Error('请选择有效战场');const key=`map:${stage}`;let m=this.cache.get(key);if(!m){const p=this.layout().maps+stage*32,r=this.rom,width=this.byte(p)|this.byte(p+1)<<8,height=this.byte(p+2)|this.byte(p+3)<<8,load=d=>{const a=this.word(p+d);return a?decompress(r,a-BASE):null;};
  m={stage,descriptor:p,width:width/4,height:height/2,gfx:load(4),palette:load(8),layers:[load(12),load(16)],metatiles:load(20),terrain:load(24)};
  if(width%4||height%2||m.terrain.length!==m.width*m.height*2||m.layers[0].length!==width/2*height/2*2)throw Error('地图尺寸尚不支持');this.cache.set(key,m);
 }const changes=init(this).maps[stage];if(!changes)return m;
 const result={...m,layers:m.layers.map(a=>a?.slice()),terrain:m.terrain.slice()};
 for(const [i,v]of Object.entries(changes.terrain||{})){result.terrain[i*2]=v&255;result.terrain[i*2+1]=v>>>8;}
 for(const [l,entries]of Object.entries(changes.layers||{}))for(const[i,v]of Object.entries(entries)){result.layers[l][i*2]=v&255;result.layers[l][i*2+1]=v>>>8;}
 return result;
};
proto.setTerrain=function(stage,x,y,value){const m=this.mapData(stage);check(x,0,m.width-1,'X');check(y,0,m.height-1,'Y');check(value,0,15,'地形编号');const a=init(this);a.maps[stage]??={terrain:{},layers:{}};a.maps[stage].terrain[y*m.width+x]=value;a.dirty=true;};
proto.stampCell=function(stage,x,y,sx,sy,copyTerrain=true){const m=this.mapData(stage);for(const[v,max,label]of[[x,m.width-1,'X'],[y,m.height-1,'Y'],[sx,m.width-1,'来源 X'],[sy,m.height-1,'来源 Y']])check(v,0,max,label);
 const a=init(this);a.maps[stage]??={terrain:{},layers:{}};const c=a.maps[stage];
 m.layers.forEach((data,l)=>{if(!data)return;c.layers[l]??={};for(let j=0;j<2;j++){const from=(sy*m.width*2+sx*2+j)*2,to=y*m.width*2+x*2+j;c.layers[l][to]=U16(data,from);}});
 if(copyTerrain)c.terrain[y*m.width+x]=U16(m.terrain,(sy*m.width+sx)*2)&15;a.dirty=true;
};
proto.renderMap=function(stage){const m=this.mapData(stage),width=m.width*32,height=m.height*16,pixels=new Uint8ClampedArray(width*height*4),colors=Array.from({length:256},(_,i)=>rgbaColor(m.palette,i));
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){let c=0;for(const layer of m.layers){if(!layer)continue;const tx=x>>3,ty=y>>3,meta=U16(layer,((ty>>1)*m.width*2+(tx>>1))*2),entry=U16(m.metatiles,meta*8+((ty&1)*2+(tx&1))*2),index=tilePixel(m.gfx,entry,x&7,y&7);if(index)c=index;}pixels.set(colors[c]||[0,0,0,255],(y*width+x)*4);}return {width,height,pixels};
};
proto.backgrounds=function(){const out=[];for(let i=1;i<=13;i++){const p=0x59903c+i*16;try{if(this.rom[u32(this.rom,p)-BASE]!==16||this.rom[u32(this.rom,p+4)-BASE]!==16||this.rom[u32(this.rom,p+8)-BASE]!==16)continue;out.push(i);}catch(_){continue;}}return out;};
proto.renderBackground=function(scene,id){if(id===undefined)id=scene>=50&&scene<56?scene-41:this.byte(this.layout().maps+scene*32+28);if(!this.backgrounds().includes(id))throw Error('该剧情底图暂不能预览');const key=`bg:${id}`;if(this.cache.has(key))return this.cache.get(key);const p=0x59903c+id*16,load=d=>decompress(this.rom,u32(this.rom,p+d)-BASE),map=load(8),full=new Uint8Array(32*10*2);full.set(map.slice(0,640));if(this.rom[p+12])for(let i=640;i<full.length;i+=2)full[i]=30;const result={...renderTiles(load(0),load(4),full,240,80,this.rom[p+12]?8:4),id};this.cache.set(key,result);return result;};
proto.events=function(stage){if(!this.battleIds().includes(stage))throw Error('请选择有效战场');return clone(init(this).events[stage]||[]);};
proto.setEvents=function(stage,events){if(!this.battleIds().includes(stage))throw Error('请选择有效战场');if(!Array.isArray(events)||events.length>8)throw Error('每个战场最多新增 8 条事件');
 const list=events.map((event,i)=>{const e=clone(event);if(!['turn','absent'].includes(e.type))throw Error('触发条件不支持');if(!['once','phase'].includes(e.repeat))throw Error('触发次数不支持');check(e.phase,0,1,'回合方');check(e.sub,0,3,'配置（3 表示全部）');if(e.type==='turn')check(e.turn,1,99,'触发回合');else{check(e.side,0,1,'人物阵营');check(e.character,1,60,'触发人物');}if(!Array.isArray(e.pages)||!e.pages.length||e.pages.length>100)throw Error('请至少添加一段对话，最多 100 段');e.pages.forEach(p=>{check(p.speaker,1,60,'说话人');if(typeof p.text!=='string'||!p.text.trim()||p.text.length>16000)throw Error('对白内容为空或过长');this.tokenize(p.text.replaceAll('【分页】',''));});e.label=String(e.label||`事件 ${i+1}`).slice(0,80);return e;});
 const a=init(this);a.events[stage]=list;a.bases[stage]??={logic:u32(this.rom,this.layout().logic+stage*4),table:u32(this.rom,this.layout().events+stage*4)};a.dirty=true;
};
proto.extraTexts=function(){return Object.values(init(this).events).flat().flatMap(e=>e.pages.map(p=>({value:p.text})));};
proto.exportFeatures=function(){const a=init(this);return clone({maps:a.maps,events:a.events,bases:a.bases,glyphCorrections:a.glyphCorrections,dirty:a.dirty});};
proto.loadFeatures=function(features){if(!features){this.restoreExtra(null);return;}const a=init(this);a.maps={};a.events={};a.bases={};a.glyphCorrections={};this.mapping={...this.baseMapping};a.dirty=false;
 for(const [s,records]of Object.entries(features.maps||{})){const stage=+s,m=this.mapData(stage);for(const[i,v]of Object.entries(records.terrain||{})){check(+i,0,m.width*m.height-1,'地形位置');this.setTerrain(stage,+i%m.width,Math.floor(+i/m.width),v);}for(const[l,data]of Object.entries(records.layers||{})){if(!m.layers[l])throw Error('地图图层不存在');a.maps[stage]??={terrain:{},layers:{}};a.maps[stage].layers[l]={};for(const[i,v]of Object.entries(data)){check(+i,0,m.layers[l].length/2-1,'地图位置');check(v,0,m.metatiles.length/8-1,'地图块');a.maps[stage].layers[l][i]=v;}a.dirty=true;}}
 for(const [s,events]of Object.entries(features.events||{}))this.setEvents(+s,events);
 // Base pointers come from the ROM's own catalogue, never from untrusted project JSON.
 for(const [s,b]of Object.entries(this.featureSeed?.bases||{}))a.bases[s]=clone(b);
 if(!Object.keys(a.maps).length&&JSON.stringify(a.events)===JSON.stringify(this.featureSeed?.events||{}))a.dirty=false;
 for(const[c,label]of Object.entries(features.glyphCorrections||{}))this.setGlyphLabel(+c,label);
};
proto.featureMetadata=function(){const a=init(this);return {events:a.events,bases:a.bases};};
proto.dialogueParts=function(scene,entry){const key=`parts:${scene}`;let parts=this.cache.get(key);if(!parts){parts=new Map();for(const [kind,table]of [['before',this.layout().before],['after',this.layout().after],...(this.battleIds().includes(scene)?[['battle',this.layout().events]]:[])])for(const n of E.graph(this.rom,[u32(this.rom,table+scene*4)-BASE]).nodes){if(!n.text)continue;if(!parts.has(n.offset))parts.set(n.offset,[]);parts.get(n.offset).push(kind);}this.cache.set(key,parts);}return parts.get(entry.offset)||[];};
const nativeDialogues=proto.dialogues,nativeSetText=proto.setText;
proto.dialogues=function(scene){let custom=this.cache.get('custom-event-texts');if(!custom){custom=new Set();for(const[s,events]of Object.entries(this.featureSeed?.events||{})){if(!events.length)continue;const base=this.featureSeed.bases?.[s];if(!base)continue;let p=base.table-BASE,n=0;while(this.rom[p]===50&&n<255){n++;p+=5;}const current=u32(this.rom,this.layout().events+(+s)*4)-BASE;const roots=events.map((_,i)=>u32(this.rom,current+(n+i)*5+1)-BASE);for(const node of E.graph(this.rom,roots).nodes)if(node.text)custom.add(node.offset);}this.cache.set('custom-event-texts',custom);}return nativeDialogues.call(this,scene).map(e=>custom.has(e.offset)?{...e,customEvent:true}:e);};
proto.setText=function(entry,value,speaker=0){if(entry.customEvent)throw Error('此对白属于新增条件剧情，请在“条件剧情”页面修改，以保持触发事件与对白一致。');return nativeSetText.call(this,entry,value,speaker);};
function assembler(start){const bytes=[],labels={},fix=[];return {bytes,emit(...v){bytes.push(...v);},mark(n){labels[n]=start+bytes.length;},ptr(n){fix.push([bytes.length,n]);bytes.push(0,0,0,0);},finish(){for(const[p,n]of fix){if(labels[n]===undefined)throw Error('事件分支未连接');bytes.splice(p,4,...le(BASE+labels[n]));}return bytes;}};}
function queueBudget(r,ptr,events=[]){const nodes=new Map(E.graph(r,[ptr-BASE]).nodes.map(n=>[n.offset,n])),turns=new Set([0,1,255]);
 for(const n of nodes.values())if(n.op===52)for(let d=-1;d<=1;d++){const t=r[n.offset+2]+d;if(t>=0&&t<=255)turns.add(t);}
 for(const e of events)if(e.type==='turn'){turns.add(e.turn);if(e.turn>0)turns.add(e.turn-1);}
 let max=0;
 for(const turn of turns)for(let phase=0;phase<2;phase++)for(let sub=0;sub<3;sub++){const memo=new Map(),active=new Set();
 function walk(p,stack=[]){const key=p+':'+stack.join(',');if(memo.has(key))return memo.get(key);if(active.has(key)||stack.length>8)return 17;const n=nodes.get(p);if(!n)throw Error('原事件逻辑无法分析');active.add(key);let v;
  if(n.op===0)v=stack.length?walk(stack.at(-1),stack.slice(0,-1)):0;
  else if(n.op===13)v=walk(n.targets[0],[...stack,p+n.length]);
  else if(n.op===7||n.op===6)v=Math.max(...n.targets.map(t=>walk(t,stack)));
  else if(n.op===52){const op=r[p+1],target=r[p+2],matches=r[p+3]===phase&&(op===255||[turn===target,turn!==target,turn>target,turn>=target,turn<target,turn<=target][op]);v=walk(matches?n.targets[0]:p+n.length,stack);}
  else if(n.op===57)v=walk(r[p+1]===sub?n.targets[0]:p+n.length,stack);
  else v=(n.op===51?1:0)+Math.max(walk(p+n.length,stack),...(n.targets||[]).map(t=>walk(t,stack)));
  active.delete(key);memo.set(key,v);return v;
 }const extra=events.filter(e=>e.phase===phase&&(e.sub===3||e.sub===sub)&&(e.type!=='turn'||turn>=e.turn)).length;max=Math.max(max,walk(ptr-BASE)+extra);}return max;
}
proto.buildExtras=function({output,append,encode}){const a=init(this);if(!a.dirty)return;
 const put32=(p,n)=>output.splice(p,4,...le(n));
 for(const[s,changes]of Object.entries(a.maps)){const m=this.mapData(+s),p=m.descriptor;for(const[l,data]of Object.entries(changes.layers||{})){if(Object.keys(data).length)put32(p+12+(+l)*4,BASE+append(compressLiteral(m.layers[l])));}if(Object.keys(changes.terrain||{}).length)put32(p+24,BASE+append(compressLiteral(m.terrain)));}
 // Flags 0..11 and 127 are used by the original scripts/preparation. Scan all reachable native code as well.
 const used=new Set([0,1,2,3,4,5,6,7,8,9,10,11,127]);
 for(const s of this.sceneIds())for(const n of this.scripts(s).nodes)if(n.op===55||n.op===56)used.add(this.rom[n.offset+2]);
 for(const[s,list]of Object.entries(a.events)){
  if(JSON.stringify(list)===JSON.stringify(this.featureSeed?.events?.[s]||[]))continue;
  const stage=+s,base=a.bases[s];if(!base)throw Error('缺少原始事件入口');
  if(!list.length){put32(this.layout().logic+stage*4,base.logic);put32(this.layout().events+stage*4,base.table);continue;}
  if(queueBudget(this.rom,base.logic,list)>16)throw Error(`战场 ${stage} 的原事件加新增事件可能超过单次 16 条队列容量，请减少此战场的新增事件。`);
  // Preserve all existing table slots and their fallback, so original event IDs remain stable.
  const original=[];let p=base.table-BASE;while(this.rom[p]===50){original.push(u32(this.rom,p+1));p+=5;if(original.length>247)throw Error('原有关卡事件表过长');}
  if(p<0||p>=this.rom.length)throw Error('原事件入口越界');
  const flags=[];for(let f=126;f>=12&&flags.length<list.length;f--)if(!used.has(f))flags.push(f);
  if(flags.length<list.length)throw Error('战斗事件标记空间不足');
  const dialogPointers=[];
  list.forEach(e=>{const code=[];for(const page of e.pages)for(const text of page.text.split('【分页】'))code.push(2,0,page.speaker,1,8,page.speaker,1,...encode(text),0);code.push(0);dialogPointers.push(BASE+append(code));});
  const table=[];for(const ptr of [...original,...dialogPointers])table.push(50,...le(ptr));table.push(7,...le(BASE+p));put32(this.layout().events+stage*4,BASE+append(table));
  while(output.length%4)output.push(255);const start=output.length,b=assembler(start);b.emit(13,...le(base.logic));
  list.forEach((e,i)=>{const flag=flags[i],next=`next${i}`,active=`active${i}`,fire=`fire${i}`,reset=`reset${i}`;
   // Per-phase events rearm during the opposite side's phase. Never re-open within the same phase.
   if(e.repeat==='phase'){b.emit(52,255,0,1-e.phase);b.ptr(reset);}
   if(e.sub!==3){b.emit(57,e.sub);b.ptr(active);b.emit(7);b.ptr(next);b.mark(active);}
   b.emit(56,0,flag);b.ptr(next);
   if(e.type==='turn'){b.emit(52,3,e.turn,e.phase);b.ptr(fire);}
   else{b.emit(52,255,0,e.phase);b.ptr(`presence${i}`);b.emit(7);b.ptr(next);b.mark(`presence${i}`);b.emit(54,0,e.side,e.character);b.ptr(fire);}
   b.emit(7);b.ptr(next);b.mark(fire);b.emit(55,1,flag,51,original.length+i+1,7);b.ptr(next);
   if(e.repeat==='phase'){b.mark(reset);b.emit(55,0,flag);}
   b.mark(next);
  });b.emit(0);put32(this.layout().logic+stage*4,BASE+append(b.finish()));
 }
};
Object.assign(E,{decompress,compressLiteral});if(typeof module!=='undefined')module.exports=E;
})(typeof window==='undefined'?globalThis:window);
