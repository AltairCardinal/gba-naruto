'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const {chromium}=require('/mnt/c/Users/APP/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const E=require('../../editor/campaign_editor');require('../../editor/flow');const root=path.resolve(__dirname,'../..'),out=path.join(root,'continuation/evidence',process.env.NARUTO_UI_OUT||'opening_portrait_ui');fs.mkdirSync(out,{recursive:true});
const sha=b=>crypto.createHash('sha256').update(b).digest('hex'),checks=[];
(async()=>{
 for(const edition of ['restart','continuation']){
  const name='naruto_'+edition+'_'+(process.env.NARUTO_NARRATION_TAG||'v042_PORTRAIT02')+'.gba',r=fs.readFileSync(path.join(root,'continuation/build',name)),m=new E.Editor(r);
  const old=fs.readFileSync(path.join(root,'continuation/build','naruto_'+edition+'_v041_FIX05.gba')),previous=new E.Editor(old),l=m.layout();
  for(const [key,size] of [['actors',104*0x1aac],['maps',104*32],['profiles',104*64],['loadouts',48*384],['skills',87*16]])assert.deepEqual(r.subarray(l[key],l[key]+size),old.subarray(l[key],l[key]+size),key+' must not change');
  assert.deepEqual(m.campaign.chapters.map(c=>c.actors),previous.campaign.chapters.map(c=>c.actors));
  let narration=0;
  for(const chapter of m.campaign.chapters){const g=m.scripts(chapter.id);assert.equal(g.issues.length,0);for(const n of g.nodes){if(n.op===2)assert(r[n.offset+2]>0,'Portrait zero is invalid');if(n.op===32&&!n.text.tokens.length)narration++;}}
  assert(narration>0);assert.deepEqual(m.dialogueSequence(56,{part:'before'}).map(e=>e.speaker),[0,0,2,7,0,2]);
  assert(m.dialogueSequence(56,{part:'before'}).every(e=>e.text.tokens.length));
  checks.push({edition,sha256:sha(r),narration_headers:narration,balance_and_actor_data:'unchanged',empty_window_commands_hidden:true,speaker_tracking:'pass'});
 }
 const browser=await chromium.launch({executablePath:'/home/app/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1680,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await page.goto(require('url').pathToFileURL(path.join(root,'editor/index.html')).href);
 assert((await page.locator('.brand').innerText()).includes(process.env.NARUTO_UI_VERSION||'0.4.2'));
 await page.locator('#romFile').setInputFiles(path.join(root,'continuation/build/naruto_restart_'+(process.env.NARUTO_NARRATION_TAG||'v042_PORTRAIT02')+'.gba'));await page.waitForFunction(()=>editorState.model);
 await page.locator('#flowGroup').selectOption({label:'少年篇续章'});await page.locator('[data-flow="campaign:56:story:before"]').click();
 assert.equal(await page.locator('.dialogrow').count(),6);assert((await page.locator('.dialogmeta').nth(4).innerText()).includes('旁白'));
 await page.screenshot({path:path.join(out,'01_narration_speakers.png'),fullPage:true});
 await page.locator('#addCampaignBattle').click();await page.locator('#newBattleTitle').fill('旁白切换验证');await page.locator('#newBattleTemplate').selectOption('56');await page.locator('#newBattlePrevious').selectOption('56');await page.locator('#createNewBattle').click();
 await page.locator('[data-tab=dialogue]').click();
 const before=page.locator('.newCampaignPages[data-kind=before]');await before.locator('select').first().selectOption('0');await before.locator('textarea').first().fill('新的任务开始了。');
 await before.locator('.addCampaignPage').click();await before.locator('select').nth(1).selectOption('7');await before.locator('textarea').nth(1).fill('留意队友的位置。');
 await before.locator('.addCampaignPage').click();await before.locator('select').nth(2).selectOption('0');await before.locator('textarea').nth(2).fill('完成任务，继续前进。');
 await page.locator('#saveNewPages').click();await page.screenshot({path:path.join(out,'02_new_narration.png'),fullPage:true});
 const exported=page.waitForEvent('download');await page.locator('#exportRom').click();const file=path.join(out,'narration_export.gba');await(await exported).saveAs(file);
 const project=await page.evaluate(()=>editorState.model.project(editorState.sha)),bytes=fs.readFileSync(file),m=new E.Editor(bytes),original=fs.readFileSync(path.join(root,'continuation/build/naruto_restart_'+(process.env.NARUTO_NARRATION_TAG||'v042_PORTRAIT02')+'.gba')),round=new E.Editor(original);round.importProject(project,sha(original));assert.deepEqual(Buffer.from(round.build()),bytes);
 assert.deepEqual(m.dialogueSequence(82,{part:'before'}).map(e=>e.speaker),[0,7,0]);
 assert(m.scripts(82).nodes.filter(n=>n.op===2).every(n=>bytes[n.offset+2]>0));
 fs.writeFileSync(path.join(out,'new_narration_project.json'),JSON.stringify(project,null,2));fs.writeFileSync(file+'.layout.json',JSON.stringify(m.campaignData(),null,2));assert.equal(errors.length,0);await browser.close();
 fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({result:'pass',kind:'ROM data checks and actual editor controls/export; emulator checked separately',checks,errors,new_battle:82,export_sha256:sha(bytes),project_roundtrip:'byte identical'},null,2));console.log('PASS narration data and editor export');
})().catch(e=>{console.error(e);process.exitCode=1;});
