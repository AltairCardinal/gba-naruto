/* Original music IDs 1..18 are nonempty songs on native music player 0. */
(function(root){'use strict';const E=typeof module==='undefined'?root.NarutoEditor:require('./campaign_editor'),P=E.Editor.prototype;
E.musicCatalog=Array.from({length:18},(_,i)=>({id:i+1,label:`原版曲目 ${String(i+1).padStart(2,'0')}`,file:`music/track_${String(i+1).padStart(2,'0')}.wav`}));
P.musicCommands=function(scene,{part='before',root}={}){const l=this.layout(),tables=part==='all'?[l.before,l.after]:[{before:l.before,after:l.after,battle:l.events}[part]],roots=root===undefined?tables.filter(Boolean).map(t=>E.u32(this.rom,t+scene*4)-E.BASE):[root];return E.graph(this.rom,roots).nodes.filter(n=>n.op===27&&this.rom[n.offset+1]>=1&&this.rom[n.offset+1]<=18&&this.rom[n.offset+2]===0).map(n=>({offset:n.offset,id:this.byte(n.offset+1)}));};
P.setMusic=function(scene,offset,id){if(!Number.isInteger(id)||id<1||id>18)throw Error('请选择原版音乐曲目');if(!this.musicCommands(scene,{part:'all'}).some(c=>c.offset===offset))throw Error('请选择此处已有的音乐指令');this.put(offset+1,id);};
if(typeof module!=='undefined')module.exports=E;})(typeof window==='undefined'?globalThis:window);
