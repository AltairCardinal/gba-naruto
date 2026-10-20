/* A separate runtime fixture. Never overwrites any released ROM. */
'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),E=require('./flow');
const root=path.resolve(__dirname,'..'),out=path.join(root,'evidence/editor_v021/runtime_export'),source=fs.readFileSync(path.join(root,'build/naruto_fog_harbor_sample_v0.2.0.gba')),m=new E.Editor(source),entry=m.dialogueSequence(1,{part:'before'})[0],old=m.textValue(entry);
if(!old.includes('三次'))throw Error('Unexpected sample text');m.setText(entry,old.replace('三次','四次'));const result=m.build(ch=>{throw Error('Unexpected new glyph '+ch)});fs.mkdirSync(out,{recursive:true});const name=path.join(out,'opening_edit.gba');if(fs.existsSync(name)&&!fs.readFileSync(name).equals(Buffer.from(result)))throw Error('Different fixture already exists; preserve it before rebuilding');fs.writeFileSync(name,result);console.log(crypto.createHash('sha256').update(result).digest('hex'));
