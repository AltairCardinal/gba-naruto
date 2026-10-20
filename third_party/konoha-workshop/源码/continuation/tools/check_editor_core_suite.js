'use strict';
const fs=require('fs'),path=require('path'),cp=require('child_process'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),out=path.join(root,process.env.NARUTO_EDITOR_CORE_OUT||'continuation/evidence/editor_full_v044/core');fs.mkdirSync(out,{recursive:true});
const results=[];
for(const file of ['tests_core.js','tests_features.js','tests_catalog.js','tests_objects.js','tests_imports.js','tests_campaign.js','tests_music.js']){
 const script=path.join(root,'editor',file),code="const fs=require('fs'),path=require('path'),out=process.argv[1],write=fs.writeFileSync;fs.writeFileSync=(p,b,...args)=>{if(!String(p).includes('/evidence/'))throw Error('Unexpected test write: '+p);return write(path.join(out,path.basename(p)),b,...args)};require(process.argv[2]);";
 const p=cp.spawnSync(process.execPath,['-e',code,out,script],{cwd:root,env:{...process.env,NARUTO_EDITOR_TEST_OUT:out},encoding:'utf8'});
 fs.writeFileSync(path.join(out,file+'.log'),p.stdout+p.stderr);results.push({file,result:p.status===0?'pass':'failed',exit_code:p.status});console.log(file,p.status);
}
const codeHashes=Object.fromEntries(fs.readdirSync(path.join(root,'editor')).filter(n=>/\.(js|html|css)$/.test(n)&&!n.startsWith('tests_')&&!n.startsWith('validate')).map(n=>[n,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'editor',n))).digest('hex')]));
const result={result:results.every(r=>r.result==='pass')?'pass':'failed',kind:'current editor parser/writer/project/map/event/asset/catalogue checks; original and historical sample compatibility; runtime tested separately',results,codeHashes};fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(result,null,2));if(result.result!=='pass')process.exitCode=1;
