#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const puppeteer = require('/tmp/gba-puppeteer/node_modules/puppeteer-core');
const {
  buildNavigationPlan, classifyMemorySnapshot, matchFormationPositions,
  buildArtifactPaths, buildProbeResult,
  buildSettlePlan, decodeBattleControl, decodeMapRuntime, classifyScreenMetrics,
  tailTransitionDecision, shouldRetryBack, decodeSaveRecord, compareSaveRecords,
  evaluateBattleArrival,
  decodeChapterScriptProbe,
} = require('./runtime-formation-probe-lib');

const URL = process.env.PROBE_URL || 'https://sh.kibox.com.cn/gba-naruto/play/';
const BROWSER_EXECUTABLE = process.env.PROBE_BROWSER || '/usr/bin/chromium';
const PROBE_ROM = process.env.PROBE_ROM || '';
const AUDIO_PROBE_RESULT = 0x0203FF60;
const NATURAL_SAVE_PROBE_RESULT = 0x0203FF40;
const POSTBATTLE_PROBE_LATCH = 0x0203FF30;
const FORCED_SAVE_CASE_HIT = 0x0203FF20;
const STOP_ON_MATCH = process.env.PROBE_STOP_ON_MATCH !== '0';
const ROOT = path.resolve(__dirname, '..', '..');
const BANK = JSON.parse(fs.readFileSync(path.join(ROOT, 'sequel/content/positions/bank.json'), 'utf8'));
const UNITS_BANK = JSON.parse(fs.readFileSync(path.join(ROOT, 'sequel/content/units/bank.json'), 'utf8'));
const WRAM_BASE = 0x020240C0;
const UNIT_STRIDE = 0x1D4;
const TEMPLATE_POOL = 0x02022E34;
const TEMPLATE_STRIDE = 0xBC;
const CHARACTER_RECORD_SIZE = 0xB4;
const TEMPLATE_COUNT = 24;
// 0x02026804 is the next proven battle-control block. With 0x1D4-byte unit
// records, only slots 0..20 fit before it; scanning slot 21+ reads unrelated
// control data and creates false (0,0) units.
const SLOT_COUNT = 21;
const BATTLE_CONTROL = 0x02026804;
const MAP_RUNTIME = 0x0201BE28;
const SAVE_RECORDS = [
  { index: 3, offset: 0x2548, length: 4732 },
  { index: 4, offset: 0x37D8, length: 20 },
  { index: 5, offset: 0x3800, length: 8 },
  { index: 6, offset: 0x381C, length: 24 },
  { index: 7, offset: 0x3848, length: 6084 },
  { index: 8, offset: 0x5020, length: 1404 },
  { index: 9, offset: 0x55B0, length: 512 },
];
const SAVE_PROBE_RESULT = 0x0203FFF0;
const EFFECT_PROBE_RESULT = 0x0203FFD0;
const CHAPTER_SCRIPT_PROBE_RESULT = 0x0203FFB0;
const SAVE_GROUP_PROBE_RESULT = 0x0203FFA0;
const GBA_KEYS = {
  Enter: 'Start',
  KeyZ: 'A',
  KeyX: 'B',
  ArrowUp: 'Up',
  ArrowDown: 'Down',
  ArrowLeft: 'Left',
  ArrowRight: 'Right',
  ShiftLeft: 'Select',
  ShiftRight: 'Select',
  KeyA: 'L',
  KeyS: 'R',
};

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function focusGameSurface(page) {
  await page.mouse.click(480, 215);
}

async function pressGbaKey(page, key, holdMs) {
  const gbaKey = GBA_KEYS[key];
  if (!gbaKey) throw new Error(`unsupported GBA key mapping: ${key}`);
  await page.evaluate(gbaKey => window.__mGBA.buttonPress(gbaKey), gbaKey);
  await sleep(holdMs);
  await page.evaluate(gbaKey => window.__mGBA.buttonUnpress(gbaKey), gbaKey);
}

function extractRuntimePositions(snapshot) {
  const positions = [];
  for (let slot = 1; slot < SLOT_COUNT; slot += 1) {
    const start = slot * UNIT_STRIDE;
    const record = snapshot.subarray(start, start + UNIT_STRIDE);
    const occupied = record.some(byte => byte !== 0);
    const x = record[0xC4];
    const y = record[0xC5];
    const initialX = record[0xC7];
    const initialY = record[0xC8];
    if (occupied && x < 64 && y < 64 && initialX === x && initialY === y) {
      positions.push({ slot, characterId: record[0], x, y });
    }
  }
  return positions;
}

function extractRuntimeTemplates(snapshot) {
  const templates = [];
  for (let slot = 0; slot < TEMPLATE_COUNT; slot += 1) {
    const start = slot * TEMPLATE_STRIDE;
    const record = snapshot.subarray(start, start + TEMPLATE_STRIDE);
    if (!record.some(byte => byte !== 0)) continue;
    templates.push({
      slot,
      characterId: record[0],
      first16Hex: Buffer.from(record.subarray(0, 16)).toString('hex'),
    });
  }
  return templates;
}

function matchTemplatesToUnits(templateSnapshot, unitSnapshot, runtimePositions) {
  return runtimePositions.map(position => {
    const unitStart = position.slot * UNIT_STRIDE;
    const unitRecord = unitSnapshot.subarray(unitStart, unitStart + TEMPLATE_STRIDE);
    const matches = [];
    for (let slot = 0; slot < TEMPLATE_COUNT; slot += 1) {
      const templateStart = slot * TEMPLATE_STRIDE;
      const templateRecord = templateSnapshot.subarray(templateStart, templateStart + TEMPLATE_STRIDE);
      if (Buffer.compare(Buffer.from(templateRecord), Buffer.from(unitRecord)) === 0) {
        matches.push(slot);
      }
    }
    return {
      unitSlot: position.slot,
      characterId: position.characterId,
      unitFirst16Hex: Buffer.from(unitRecord.subarray(0, 16)).toString('hex'),
      matchingTemplateSlots: matches,
    };
  });
}

function matchTemplatesToCharacterDefinitions(templateSnapshot, unitsBank) {
  return extractRuntimeTemplates(templateSnapshot).map(template => {
    const entry = unitsBank.entries.find(item => item.character_id === template.characterId);
    const templateStart = template.slot * TEMPLATE_STRIDE;
    const templateRecordHex = Buffer.from(
      templateSnapshot.subarray(templateStart + 1, templateStart + 1 + CHARACTER_RECORD_SIZE),
    ).toString('hex');
    const romRecordHex = entry?.raw_hex || '';
    let matchingPrefixBytes = 0;
    let firstMismatchOffset = null;
    const templateRecord = Buffer.from(templateRecordHex, 'hex');
    const romRecord = Buffer.from(romRecordHex, 'hex');
    const compareLength = Math.min(templateRecord.length, romRecord.length);
    for (let offset = 0; offset < compareLength; offset += 1) {
      if (templateRecord[offset] !== romRecord[offset]) {
        firstMismatchOffset = offset;
        break;
      }
      matchingPrefixBytes += 1;
    }
    if (firstMismatchOffset === null && templateRecord.length !== romRecord.length) {
      firstMismatchOffset = compareLength;
    }
    return {
      templateSlot: template.slot,
      characterId: template.characterId,
      romOffsetHex: entry?.rom_offset_hex || null,
      templateRecordFirst16Hex: templateRecordHex.slice(0, 32),
      romRecordFirst16Hex: romRecordHex.slice(0, 32) || null,
      matchingPrefixBytes: entry ? matchingPrefixBytes : null,
      firstMismatchOffset,
      rawRecordMatchesRom: Boolean(entry && templateRecordHex === romRecordHex),
    };
  });
}

async function readGbaBytes(page, address, length) {
  return Uint8Array.from(await page.evaluate(({ address, length }) => {
    const gba = window.__mGBA;
    if (!gba || typeof gba._readGbaByte !== 'function') throw new Error('mGBA readGbaByte hook unavailable');
    if (typeof gba._malloc !== 'function' || typeof gba._free !== 'function' || typeof gba._readGbaBytes !== 'function') {
      return Array.from({ length }, (_, offset) => gba._readGbaByte(address + offset));
    }
    const pointer = gba._malloc(length);
    try {
      const copied = gba._readGbaBytes(address, pointer, length);
      if (copied === 0) throw new Error(`readGbaBytes rejected 0x${address.toString(16)}`);
      return Array.from(gba.HEAPU8.subarray(pointer, pointer + length));
    } finally {
      gba._free(pointer);
    }
  }, { address, length }));
}

async function readSaveRecords(page) {
  const exported = await page.evaluate(() => {
    const save = window.__mGBA?.getSave?.();
    return save ? Array.from(save) : null;
  });
  const exportAvailable = Array.isArray(exported) && exported.length > 0;
  const saveBytes = exportAvailable ? Uint8Array.from(exported) : new Uint8Array(0x10000).fill(0xFF);
  const records = [];
  for (const record of SAVE_RECORDS) {
    if (record.offset + record.length + 1 > saveBytes.length) {
      throw new Error(`exported save is too short for descriptor ${record.index}: ${saveBytes.length} bytes`);
    }
    records.push({
      descriptorIndex: record.index,
      payloadLength: record.length,
      saveExportAvailable: exportAvailable,
      saveFileSize: saveBytes.length,
      ...decodeSaveRecord(record.offset, saveBytes.subarray(record.offset, record.offset + record.length + 1)),
    });
  }
  return records;
}

async function persistSaveExport(page) {
  const outputPath = process.env.PROBE_SAVE_DUMP;
  if (!outputPath) return null;
  const exported = await page.evaluate(() => Array.from(window.__mGBA?.getSave?.() || []));
  fs.writeFileSync(outputPath, Buffer.from(exported));
  return { path: outputPath, size: exported.length };
}

async function installProbeRomRoute(page, romPath) {
  if (!romPath) return null;
  const absolutePath = path.resolve(romPath);
  const romBytes = fs.readFileSync(absolutePath);
  await page.setRequestInterception(true);
  page.on('request', request => {
    const url = new globalThis.URL(request.url());
    if (url.pathname.endsWith('/rom/naruto-sequel-dev.gba')) {
      request.respond({
        status: 200,
        contentType: 'application/octet-stream',
        body: romBytes,
      }).catch(error => {
        console.warn(`failed to serve probe ROM ${absolutePath}: ${error.message}`);
      });
      return;
    }
    request.continue().catch(error => {
      console.warn(`failed to continue request ${request.url()}: ${error.message}`);
    });
  });
  return absolutePath;
}

async function captureScreenMetrics(page) {
  const base64 = await page.screenshot({ encoding: 'base64' });
  return page.evaluate(async encoded => {
    const image = new Image();
    image.src = `data:image/png;base64,${encoded}`;
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = image.width;
    canvas.height = image.height;
    const context = canvas.getContext('2d');
    context.drawImage(image, 0, 0);
    const pixels = context.getImageData(240, 55, 480, 320).data;
    let gray = 0;
    let pale = 0;
    let green = 0;
    const count = pixels.length / 4;
    for (let i = 0; i < pixels.length; i += 4) {
      const r = pixels[i]; const g = pixels[i + 1]; const b = pixels[i + 2];
      if (Math.abs(r - g) < 12 && Math.abs(g - b) < 12 && r > 60 && r < 220) gray += 1;
      if (r > 150 && g > 160 && b < 170) pale += 1;
      if (g > r * 1.15 && g > b * 1.15 && g > 80) green += 1;
    }
    return { grayRatio: gray / count, paleRatio: pale / count, greenRatio: green / count };
  }, base64);
}

async function main() {
  const artifacts = buildArtifactPaths(
    process.env.PROBE_RESULT || '/tmp/runtime-formation-probe-result.json',
    process.env.PROBE_SCREENSHOT || '/tmp/runtime-formation-probe-final.png',
  );
  const browser = await puppeteer.launch({
    executablePath: BROWSER_EXECUTABLE, headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--enable-features=SharedArrayBuffer'],
    defaultViewport: { width: 960, height: 720 },
  });
  const page = await browser.newPage();
  try {
    await installProbeRomRoute(page, PROBE_ROM);
    await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.click('#playBtn');
    await page.waitForFunction(() => (
      typeof window.__mGBA?._readGbaByte === 'function'
      && document.querySelector('.speed-btn[data-speed="1"]')?.disabled === false
      && window.__mGBA._readGbaByte(0x08000000) !== -1
    ), { timeout: 90000, polling: 1000 });
    await page.evaluate(() => document.querySelector('.speed-btn[data-speed="4"]')?.click());
    const initialSaveRecords = await readSaveRecords(page);
    const plan = buildNavigationPlan({
      startCount: Number(process.env.PROBE_START_COUNT ?? 30),
      advanceCount: Number(process.env.PROBE_ADVANCE_COUNT ?? 80),
      startDelayMs: Number(process.env.PROBE_START_DELAY_MS ?? 3000),
      confirmDelayMs: Number(process.env.PROBE_CONFIRM_DELAY_MS ?? 1500),
      advanceDelayMs: Number(process.env.PROBE_ADVANCE_DELAY_MS ?? 3000),
      keyHoldMs: Number(process.env.PROBE_KEY_HOLD_MS ?? 125),
      tailDelayMs: Number(process.env.PROBE_TAIL_DELAY_MS ?? 600),
      tailKeys: (process.env.PROBE_TAIL_KEYS || '').split(',').map(key => key.trim()).filter(Boolean),
    });
    const settlePlan = buildSettlePlan({
      count: Number(process.env.PROBE_SETTLE_COUNT ?? 20),
      delayMs: Number(process.env.PROBE_SETTLE_DELAY ?? 500),
      confirmEvery: Number(process.env.PROBE_SETTLE_CONFIRM_EVERY ?? 0),
      keyHoldMs: Number(process.env.PROBE_KEY_HOLD_MS ?? 125),
    });
    let previous = null;
    let lastDiagnostic = null;
    let latestMatch = null;
    const stages = [];
    for (let index = 0; index < plan.length; index += 1) {
      const action = plan[index];
      await sleep(action.delayMs);
      await pressGbaKey(page, action.key, action.holdMs);
      let screenMetrics = null;
      let screenState = null;
      let adaptiveRetries = 0;
      if (action.phase === 'tail' && action.key === 'KeyX') {
        screenMetrics = await captureScreenMetrics(page);
        screenState = classifyScreenMetrics(screenMetrics);
        let decision = tailTransitionDecision(screenState);
        while (decision !== 'ready' && adaptiveRetries < 20) {
          adaptiveRetries += 1;
          await sleep(action.delayMs);
          if (shouldRetryBack(decision, adaptiveRetries)) {
            await pressGbaKey(page, action.key, action.holdMs);
          }
          screenMetrics = await captureScreenMetrics(page);
          screenState = classifyScreenMetrics(screenMetrics);
          decision = tailTransitionDecision(screenState);
        }
      }
      if (screenState === null) {
        screenMetrics = await captureScreenMetrics(page);
        screenState = classifyScreenMetrics(screenMetrics);
      }
      const snapshot = await readGbaBytes(page, WRAM_BASE, UNIT_STRIDE * SLOT_COUNT);
      const templateSnapshot = await readGbaBytes(page, TEMPLATE_POOL, TEMPLATE_STRIDE * TEMPLATE_COUNT);
      const battleControl = decodeBattleControl(await readGbaBytes(page, BATTLE_CONTROL, 8));
      const mapRuntime = decodeMapRuntime(await readGbaBytes(page, MAP_RUNTIME, 4));
      const status = classifyMemorySnapshot(previous, snapshot);
      const runtimePositions = extractRuntimePositions(snapshot);
      const runtimeTemplates = extractRuntimeTemplates(templateSnapshot);
      const templateMatches = matchTemplatesToUnits(templateSnapshot, snapshot, runtimePositions);
      const characterDefinitionMatches = matchTemplatesToCharacterDefinitions(templateSnapshot, UNITS_BANK);
      lastDiagnostic = {
        step: index + 1,
        phase: action.phase,
        status,
        nonzeroBytes: snapshot.reduce((count, byte) => count + (byte !== 0), 0),
        firstBytesHex: Buffer.from(snapshot.subarray(0, 16)).toString('hex'),
        runtimePositions,
        runtimeTemplates,
        templateMatches,
        characterDefinitionMatches,
        battleControl,
        mapRuntime,
        saveProbeHex: Buffer.from(await readGbaBytes(page, SAVE_PROBE_RESULT, 2)).toString('hex'),
        effectProbeHex: Buffer.from(await readGbaBytes(page, EFFECT_PROBE_RESULT, 16)).toString('hex'),
        chapterScriptProbe: decodeChapterScriptProbe(await readGbaBytes(page, CHAPTER_SCRIPT_PROBE_RESULT, 12)),
        saveGroupProbeHex: Buffer.from(await readGbaBytes(page, SAVE_GROUP_PROBE_RESULT, 8)).toString('hex'),
        audioProbeHex: Buffer.from(await readGbaBytes(page, AUDIO_PROBE_RESULT, 16)).toString('hex'),
        naturalSaveProbeHex: Buffer.from(await readGbaBytes(page, NATURAL_SAVE_PROBE_RESULT, 4)).toString('hex'),
        postbattleProbeLatchHex: Buffer.from(await readGbaBytes(page, POSTBATTLE_PROBE_LATCH, 4)).toString('hex'),
        forcedSaveCaseHitHex: Buffer.from(await readGbaBytes(page, FORCED_SAVE_CASE_HIT, 4)).toString('hex'),
        screenMetrics,
        screenState,
        adaptiveRetries,
      };
      if (runtimePositions.length > 0) {
        const match = matchFormationPositions(BANK.entries, runtimePositions);
        latestMatch = match;
        const arrival = evaluateBattleArrival({ match, battleControl, mapRuntime, screenState });
        lastDiagnostic.arrival = arrival;
        console.log(JSON.stringify({ step: index + 1, phase: action.phase, status, runtimePositions, match, screenState, arrival }));
        if (STOP_ON_MATCH && arrival.arrived) {
          lastDiagnostic.saveRecords = compareSaveRecords(initialSaveRecords, await readSaveRecords(page));
          lastDiagnostic.saveExport = await persistSaveExport(page);
          await page.screenshot({ path: artifacts.finalScreenshotPath });
          fs.writeFileSync(artifacts.resultPath, `${JSON.stringify(buildProbeResult({ outcome: 'matched', reason: arrival.reason, stages, final: lastDiagnostic, match }), null, 2)}\n`);
          return;
        }
      } else if (status.state === 'changed') {
        console.log(JSON.stringify({ step: index + 1, phase: action.phase, status }));
      }
      const nextPhase = plan[index + 1]?.phase;
      if (nextPhase !== action.phase) {
        const screenshotPath = artifacts.phaseScreenshot(action.phase);
        await page.screenshot({ path: screenshotPath });
        stages.push({ ...lastDiagnostic, screenshotPath });
      }
      previous = snapshot;
    }
    if (!STOP_ON_MATCH && lastDiagnostic?.arrival?.arrived) {
      lastDiagnostic.saveRecords = compareSaveRecords(initialSaveRecords, await readSaveRecords(page));
      lastDiagnostic.saveExport = await persistSaveExport(page);
      await page.screenshot({ path: artifacts.finalScreenshotPath });
      fs.writeFileSync(artifacts.resultPath, `${JSON.stringify(buildProbeResult({ outcome: 'matched', reason: 'strict-battle-arrival-after-full-plan', stages, final: lastDiagnostic, match: latestMatch }), null, 2)}\n`);
      return;
    }
    for (const settle of settlePlan) {
      await sleep(settle.delayMs);
      if (settle.key) {
        await pressGbaKey(page, settle.key, settle.holdMs);
      }
      const snapshot = await readGbaBytes(page, WRAM_BASE, UNIT_STRIDE * SLOT_COUNT);
      const templateSnapshot = await readGbaBytes(page, TEMPLATE_POOL, TEMPLATE_STRIDE * TEMPLATE_COUNT);
      const battleControl = decodeBattleControl(await readGbaBytes(page, BATTLE_CONTROL, 8));
      const mapRuntime = decodeMapRuntime(await readGbaBytes(page, MAP_RUNTIME, 4));
      const status = classifyMemorySnapshot(previous, snapshot);
      const runtimePositions = extractRuntimePositions(snapshot);
      const runtimeTemplates = extractRuntimeTemplates(templateSnapshot);
      const templateMatches = matchTemplatesToUnits(templateSnapshot, snapshot, runtimePositions);
      const characterDefinitionMatches = matchTemplatesToCharacterDefinitions(templateSnapshot, UNITS_BANK);
      const screenMetrics = await captureScreenMetrics(page);
      const screenState = classifyScreenMetrics(screenMetrics);
      lastDiagnostic = {
        step: plan.length + settle.poll,
        phase: settle.phase,
        poll: settle.poll,
        recoveryKey: settle.key || null,
        status,
        nonzeroBytes: snapshot.reduce((count, byte) => count + (byte !== 0), 0),
        firstBytesHex: Buffer.from(snapshot.subarray(0, 16)).toString('hex'),
        runtimePositions,
        runtimeTemplates,
        templateMatches,
        characterDefinitionMatches,
        battleControl,
        mapRuntime,
        saveProbeHex: Buffer.from(await readGbaBytes(page, SAVE_PROBE_RESULT, 2)).toString('hex'),
        effectProbeHex: Buffer.from(await readGbaBytes(page, EFFECT_PROBE_RESULT, 16)).toString('hex'),
        chapterScriptProbe: decodeChapterScriptProbe(await readGbaBytes(page, CHAPTER_SCRIPT_PROBE_RESULT, 12)),
        saveGroupProbeHex: Buffer.from(await readGbaBytes(page, SAVE_GROUP_PROBE_RESULT, 8)).toString('hex'),
        audioProbeHex: Buffer.from(await readGbaBytes(page, AUDIO_PROBE_RESULT, 16)).toString('hex'),
        naturalSaveProbeHex: Buffer.from(await readGbaBytes(page, NATURAL_SAVE_PROBE_RESULT, 4)).toString('hex'),
        postbattleProbeLatchHex: Buffer.from(await readGbaBytes(page, POSTBATTLE_PROBE_LATCH, 4)).toString('hex'),
        forcedSaveCaseHitHex: Buffer.from(await readGbaBytes(page, FORCED_SAVE_CASE_HIT, 4)).toString('hex'),
        screenMetrics,
        screenState,
      };
      if (runtimePositions.length > 0) {
        const match = matchFormationPositions(BANK.entries, runtimePositions);
        const arrival = evaluateBattleArrival({ match, battleControl, mapRuntime, screenState });
        lastDiagnostic.arrival = arrival;
        console.log(JSON.stringify({ ...lastDiagnostic, match, arrival }));
        if (arrival.arrived) {
          lastDiagnostic.saveRecords = compareSaveRecords(initialSaveRecords, await readSaveRecords(page));
          lastDiagnostic.saveExport = await persistSaveExport(page);
          const screenshotPath = artifacts.phaseScreenshot('settle');
          await page.screenshot({ path: screenshotPath });
          stages.push({ ...lastDiagnostic, screenshotPath });
          await page.screenshot({ path: artifacts.finalScreenshotPath });
          fs.writeFileSync(artifacts.resultPath, `${JSON.stringify(buildProbeResult({ outcome: 'matched', reason: 'strict-battle-arrival-after-settle', stages, final: lastDiagnostic, match }), null, 2)}\n`);
          return;
        }
      } else if (status.state === 'changed') {
        console.log(JSON.stringify(lastDiagnostic));
      }
      previous = snapshot;
    }
    if (settlePlan.length > 0) {
      const screenshotPath = artifacts.phaseScreenshot('settle');
      await page.screenshot({ path: screenshotPath });
      stages.push({ ...lastDiagnostic, screenshotPath });
    }
    await page.screenshot({ path: artifacts.finalScreenshotPath });
    const result = buildProbeResult({ outcome: 'not-found', reason: 'settle-exhausted', stages, final: lastDiagnostic });
    fs.writeFileSync(artifacts.resultPath, `${JSON.stringify(result, null, 2)}\n`);
    throw new Error(`navigation and settle polling ended before a unique formation was observed; result=${artifacts.resultPath}; screenshot=${artifacts.finalScreenshotPath}; last=${JSON.stringify(lastDiagnostic)}`);
  } finally {
    await browser.close();
  }
}

if (require.main === module) main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });

module.exports = {
  extractRuntimePositions,
  extractRuntimeTemplates,
  focusGameSurface,
  matchTemplatesToCharacterDefinitions,
  matchTemplatesToUnits,
  readGbaBytes,
  readSaveRecords,
};
