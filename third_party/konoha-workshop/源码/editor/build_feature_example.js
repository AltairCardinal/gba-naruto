'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),E=require('./features');
const root=path.resolve(__dirname,'..'),bytes=fs.readFileSync(path.join(root,'build/naruto_fog_harbor_sample_v0.1.0.gba'));
const m=new E.Editor(bytes,'雾港信标_v0.1.0.gba'),fonts=require('../build/feature_example_glyphs.json');
m.transaction('地图与条件对白示例',()=>{
 m.stampCell(1,6,7,8,5);m.stampCell(1,6,8,8,6);m.stampCell(1,8,5,7,5);m.stampCell(1,8,6,7,6);
 m.setTerrain(1,6,7,7);m.setTerrain(1,6,8,7);m.setTerrain(1,8,5,0);m.setTerrain(1,8,6,0);
 m.setEvents(1,require('./events_example.json'));
});
const result=m.build(ch=>{if(!fonts[ch])throw Error(`缺字 ${ch}`);return fonts[ch];}),name=path.join(root,'build/naruto_fog_harbor_sample_v0.2.0');
fs.writeFileSync(name+'.gba',result);const original=fs.readFileSync(path.join(root,'originals/naruto_konoha_bearteam_simp.gba'));fs.writeFileSync(name+'_原版基底.ips',E.ips(original,result));fs.writeFileSync(name+'_示例v010基底.ips',E.ips(bytes,result));
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');fs.writeFileSync(path.join(root,'build/feature_example_project.json'),JSON.stringify(m.project(hash(bytes)),null,2));
fs.writeFileSync(name+'_manifest.json',JSON.stringify({baseline_sha256:hash(bytes),sha256:hash(result),size:result.length,events:m.events(1),map:{new_blocks:[[6,7],[6,8]],opened:[[8,5],[8,6]]},runtime:'not_run'},null,2));console.log('Built',result.length,hash(result));
