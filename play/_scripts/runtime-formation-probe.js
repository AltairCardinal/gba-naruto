#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
let puppeteer;
try {
  puppeteer = require('puppeteer-core');
} catch (error) {
  // Compatibility with older local setups; fresh clones should run
  // `npm install --prefix play/_scripts` and use the standard dependency.
  puppeteer = require('/tmp/gba-puppeteer/node_modules/puppeteer-core');
}
const {
  buildNavigationPlan, classifyMemorySnapshot, matchFormationPositions,
  buildArtifactPaths, buildProbeResult,
  buildSettlePlan, decodeBattleControl, decodeMapRuntime, classifyScreenMetrics,
  tailTransitionDecision, shouldRetryBack, decodeSaveRecord, compareSaveRecords,
  evaluateBattleArrival,
  decodeChapterScriptProbe,
  decodeAlternateChapterProbe,
  evaluateAlternateChapterEvidence,
} = require('./runtime-formation-probe-lib');
const {
  decodePublishedCall,
  evaluatePlayerControlEvidence,
} = require('./scenario-41-runtime-evidence');

const URL = process.env.PROBE_URL || 'https://sh.kibox.com.cn/gba-naruto/play/';
const BROWSER_EXECUTABLE = process.env.PROBE_BROWSER || '/usr/bin/chromium';
const PROBE_ROM = process.env.PROBE_ROM || '';
const AUDIO_PROBE_RESULT = 0x0203FF60;
const PLAYER_CURRENT_UNIT_PROBE_RESULT = 0x0203F060;
const PLAYER_CURRENT_UNIT_MAGIC = 0x31554350;
const PLAYER_CONTROL_PROBE_RESULT = 0x0203F080;
const PLAYER_CONTROL_MAGIC = 0x314F4350;
const NATURAL_SAVE_PROBE_RESULT = 0x0203FF40;
const NATURAL_LOAD_PROBE_RESULT = 0x0E007FF0;
const POSTBATTLE_PROBE_LATCH = 0x0203FF30;
const FORCED_SAVE_CASE_HIT = 0x0203FF20;
const STOP_ON_MATCH = process.env.PROBE_STOP_ON_MATCH !== '0';
const POST_ARRIVAL_POLLS = Number(process.env.PROBE_POST_ARRIVAL_POLLS || 0);
const ROOT = path.resolve(__dirname, '..', '..');

function formatProgress(stage, details = {}, clock = () => new Date()) {
  return JSON.stringify({
    type: 'resource-progress',
    stage,
    timestamp: clock().toISOString(),
    details,
  });
}

function emitProgress(stage, details = {}) {
  console.log(formatProgress(stage, details));
}

function writeProbeResult(resultPath, result) {
  fs.writeFileSync(resultPath, `${JSON.stringify(result, null, 2)}\n`);
  emitProgress('result-written', { outcome: result.outcome, reason: result.reason });
}

function decodePlayerControlProbe(bytes, expectedMagic = 0x314F4350) {
  const data = Buffer.from(bytes);
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  return {
    rawHex: data.toString('hex'),
    magicValid: view.getUint32(0, true) === expectedMagic,
    hitCount: view.getUint32(4, true),
    argument0: view.getUint32(8, true),
    argument1: view.getUint16(12, true),
    argument2: view.getUint16(14, true),
  };
}
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
const CHAPTER_STATE = 0x020311EA;
const ALTERNATE_SCENARIO_ID = 39;
const ALTERNATE_SCRIPT_START = 0x08031281;
const ALTERNATE_SCRIPT_END = 0x0803142E;
const CHAPTER_EVIDENCE_CONFIG = {
  expectedScenarioId: Number(process.env.PROBE_EXPECTED_SCENARIO_ID || ALTERNATE_SCENARIO_ID),
  expectedScriptStart: Number(process.env.PROBE_EXPECTED_SCRIPT_START || ALTERNATE_SCRIPT_START),
  expectedScriptEnd: Number(process.env.PROBE_EXPECTED_SCRIPT_END || ALTERNATE_SCRIPT_END),
  evidenceKind: process.env.PROBE_CHAPTER_EVIDENCE_KIND || 'alternate',
};
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
const BROWSER_KEYS = {
  Enter: 'Enter', KeyZ: 'z', KeyX: 'x',
  ArrowUp: 'ArrowUp', ArrowDown: 'ArrowDown',
  ArrowLeft: 'ArrowLeft', ArrowRight: 'ArrowRight',
  ShiftLeft: 'Shift', ShiftRight: 'Shift', KeyA: 'a', KeyS: 's',
};

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function focusGameSurface(page) {
  await page.evaluate(() => {
    document.body.tabIndex = -1;
    document.body.focus({ preventScroll: true });
  });
}

async function pressGbaKey(page, key, holdMs, inputAudit, inputKind) {
  const gbaKey = GBA_KEYS[key];
  if (!gbaKey) throw new Error(`unsupported GBA key mapping: ${key}`);
  if (inputAudit) {
    if (inputKind !== 'explicit' && inputKind !== 'automatic') {
      throw new Error(`input audit kind must be explicit or automatic, got ${inputKind}`);
    }
    inputAudit[`${inputKind}Inputs`].push(key);
  }
  if (process.env.PROBE_INPUT_MODE === 'keyboard') {
    await focusGameSurface(page);
    const browserKey = BROWSER_KEYS[key];
    if (!browserKey) throw new Error(`unsupported browser key mapping: ${key}`);
    await page.keyboard.down(browserKey);
    await sleep(holdMs);
    await page.keyboard.up(browserKey);
    return;
  }
  await page.evaluate(gbaKey => window.__mGBA.buttonPress(gbaKey), gbaKey);
  await sleep(holdMs);
  await page.evaluate(gbaKey => window.__mGBA.buttonUnpress(gbaKey), gbaKey);
}

function createPlayerControlEvidenceTracker({
  page,
  readGbaBytes: readBytes = readGbaBytes,
  inputAudit,
}) {
  let baseline = null;

  async function readRecords() {
    const player = decodePublishedCall(
      await readBytes(page, PLAYER_CONTROL_PROBE_RESULT, 24),
      PLAYER_CONTROL_MAGIC,
    );
    const current = decodePublishedCall(
      await readBytes(page, PLAYER_CURRENT_UNIT_PROBE_RESULT, 24),
      PLAYER_CURRENT_UNIT_MAGIC,
    );
    return { player, current };
  }

  return {
    async captureBaseline() {
      const records = await readRecords();
      baseline = Object.freeze({
        player: Object.freeze(records.player),
        current: Object.freeze(records.current),
      });
      return baseline;
    },
    async attachEvidence(diagnostic) {
      if (!baseline) throw new Error('player-control baseline must be captured first');
      const final = await readRecords();
      const controlledSlot = final.player.argument0;
      const controlledUnit = diagnostic.occupiedUnitSummaries
        ?.find(unit => unit.slot === controlledSlot);
      const auditSnapshot = Object.freeze({
        explicitInputs: Object.freeze([...(inputAudit?.explicitInputs || [])]),
        automaticInputs: Object.freeze([...(inputAudit?.automaticInputs || [])]),
      });
      diagnostic.playerControlProbe = final.player;
      diagnostic.playerCurrentUnitProbe = final.current;
      diagnostic.inputAudit = auditSnapshot;
      diagnostic.playerControlEvidence = evaluatePlayerControlEvidence({
        baseline,
        final,
        battleId: diagnostic.battleControl?.chapterBattleId,
        mapLoaded: diagnostic.mapRuntime?.width > 0 && diagnostic.mapRuntime?.height > 0,
        screenState: diagnostic.screenState,
        controlledCharacterId: controlledUnit?.characterId,
        controlledSlot: controlledUnit?.slot,
        explicitInputs: auditSnapshot.explicitInputs,
        automaticInputs: auditSnapshot.automaticInputs,
      });
      return diagnostic;
    },
  };
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

function extractOccupiedUnitSummaries(snapshot) {
  const units = [];
  for (let slot = 0; slot < SLOT_COUNT; slot += 1) {
    const start = slot * UNIT_STRIDE;
    const record = snapshot.subarray(start, start + UNIT_STRIDE);
    if (!record.some(byte => byte !== 0)) continue;
    units.push({
      slot,
      characterId: record[0],
      first32Hex: Buffer.from(record.subarray(0, 32)).toString('hex'),
      value0c: record[0x0C] | (record[0x0D] << 8),
      value0e: record[0x0E] | (record[0x0F] << 8),
      x: record[0xC4],
      y: record[0xC5],
      initialX: record[0xC7],
      initialY: record[0xC8],
    });
  }
  return units;
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

async function readAlternateChapterProbe(page) {
  const bytes = await readGbaBytes(page, CHAPTER_SCRIPT_PROBE_RESULT, 32);
  const chapterState = (await readGbaBytes(page, CHAPTER_STATE, 1))[0];
  return decodeAlternateChapterProbe(bytes, chapterState);
}

async function captureAlternateChapterEvidence(page, baseline, config = CHAPTER_EVIDENCE_CONFIG) {
  const current = await readAlternateChapterProbe(page);
  let romOpcodeBytesHex = null;
  if (current.lastOpcodeCursor >= config.expectedScriptStart
      && current.lastOpcodeCursor <= config.expectedScriptEnd) {
    romOpcodeBytesHex = Buffer.from(await readGbaBytes(page, current.lastOpcodeCursor, 4)).toString('hex');
  }
  return {
    ...current,
    baseline,
    romOpcodeBytesHex,
    evidence: evaluateAlternateChapterEvidence({
      baseline,
      current,
      expectedScenarioId: config.expectedScenarioId,
      expectedScriptStart: config.expectedScriptStart,
      expectedScriptEnd: config.expectedScriptEnd,
      romOpcodeBytesHex,
      evidenceKind: config.evidenceKind,
    }),
  };
}

function shouldStopForAlternateChapter(probe) {
  return probe?.evidence?.verified === true;
}

function allowsLegacyEvidenceStop(evidenceMode) {
  return evidenceMode !== 'player-control';
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
    if (record.offset + record.length + 0x14 > saveBytes.length) {
      throw new Error(`exported save is too short for descriptor ${record.index}: ${saveBytes.length} bytes`);
    }
    records.push({
      descriptorIndex: record.index,
      payloadLength: record.length,
      saveExportAvailable: exportAvailable,
      saveFileSize: saveBytes.length,
      ...decodeSaveRecord(record.offset, saveBytes.subarray(record.offset, record.offset + record.length + 0x14)),
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

async function persistMemoryDump(page) {
  const outputPath = process.env.PROBE_MEMORY_DUMP;
  if (!outputPath) return null;
  const address = Number(process.env.PROBE_MEMORY_ADDRESS || 0x02000000);
  const length = Number(process.env.PROBE_MEMORY_LENGTH || 0x40000);
  const bytes = await readGbaBytes(page, address, length);
  fs.writeFileSync(outputPath, Buffer.from(bytes));
  return { path: outputPath, address, length };
}

function mapResourceDumpSpecs() {
  return [
    { name: 'ewram.bin', address: 0x02000000, length: 0x40000 },
    { name: 'palette-ram.bin', address: 0x05000000, length: 0x400 },
    { name: 'vram.bin', address: 0x06000000, length: 0x18000 },
  ];
}

async function persistMapResourceDumps(page) {
  const outputDir = process.env.PROBE_MAP_RESOURCE_DUMP_DIR;
  if (!outputDir) return null;
  const absoluteDir = path.resolve(outputDir);
  fs.mkdirSync(absoluteDir, { recursive: true });
  const results = [];
  for (const spec of mapResourceDumpSpecs()) {
    const bytes = await readGbaBytes(page, spec.address, spec.length);
    const outputPath = path.join(absoluteDir, spec.name);
    fs.writeFileSync(outputPath, Buffer.from(bytes));
    results.push({ ...spec, path: outputPath });
  }
  return results;
}

async function persistStateExport(page) {
  const outputPath = process.env.PROBE_STATE_DUMP;
  if (!outputPath) return null;
  const state = await page.evaluate(async () => {
    const gba = window.__mGBA;
    const slot = 9;
    const stateDir = '/data/states/';
    for (const name of gba.FS.readdir(stateDir).filter(item => item.endsWith(`.ss${slot}`))) {
      gba.FS.unlink(`${stateDir}${name}`);
    }
    const saved = gba.saveState(slot);
    if (!saved) throw new Error(`saveState(${slot}) failed`);
    await new Promise(resolve => setTimeout(resolve, 250));
    const names = gba.FS.readdir(stateDir).filter(item => item.endsWith(`.ss${slot}`));
    if (names.length !== 1) throw new Error(`state slot ${slot} expected one fresh file, got ${names.length}`);
    const name = names[0];
    return { slot, name, data: Array.from(gba.FS.readFile(`${stateDir}${name}`)) };
  });
  fs.writeFileSync(outputPath, Buffer.from(state.data));
  return { path: outputPath, slot: state.slot, name: state.name, size: state.data.length };
}

async function loadStateCheckpoint(page) {
  const inputPath = process.env.PROBE_STATE_LOAD;
  if (!inputPath) return null;
  const absolutePath = path.resolve(inputPath);
  const data = fs.readFileSync(absolutePath);
  const result = await page.evaluate(async ({ bytes, buttons }) => {
    const gba = window.__mGBA;
    const slot = 9;
    const name = `naruto-sequel-dev.ss${slot}`;
    gba.FS.writeFile(`/data/states/${name}`, Uint8Array.from(bytes));
    const loaded = gba.loadState(slot);
    await new Promise(resolve => setTimeout(resolve, 500));
    // A checkpoint can capture the emulator between the browser keydown and
    // keyup callbacks. Clear every logical GBA button so replay does not stay
    // latched in a state that ignores all later confirms.
    for (const button of buttons) gba.buttonUnpress(button);
    return { slot, name, loaded };
  }, { bytes: Array.from(data), buttons: [...new Set(Object.values(GBA_KEYS))] });
  if (!result.loaded) throw new Error(`loadState(${result.slot}) failed for ${absolutePath}`);
  return { path: absolutePath, size: data.length, ...result };
}

async function loadSaveExport(page) {
  const inputPath = process.env.PROBE_SAVE_LOAD;
  if (!inputPath) return null;
  if (process.env.PROBE_STATE_LOAD) throw new Error('PROBE_SAVE_LOAD and PROBE_STATE_LOAD are mutually exclusive');
  const absolutePath = path.resolve(inputPath);
  const data = fs.readFileSync(absolutePath);
  const result = await page.evaluate(async bytes => {
    const gba = window.__mGBA;
    gba.FS.writeFile(gba.saveName, Uint8Array.from(bytes));
    const reloaded = gba._quickReload();
    await new Promise(resolve => setTimeout(resolve, 1500));
    return { saveName: gba.saveName, reloaded };
  }, Array.from(data));
  return { path: absolutePath, size: data.length, ...result };
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
    let dark = 0;
    let edges = 0;
    let edgeSamples = 0;
    const count = pixels.length / 4;
    for (let i = 0; i < pixels.length; i += 4) {
      const r = pixels[i]; const g = pixels[i + 1]; const b = pixels[i + 2];
      if (Math.abs(r - g) < 12 && Math.abs(g - b) < 12 && r > 60 && r < 220) gray += 1;
      if (r > 150 && g > 160 && b < 170) pale += 1;
      if (g > r * 1.15 && g > b * 1.15 && g > 80) green += 1;
      if (r < 30 && g < 30 && b < 30) dark += 1;
      const pixel = i / 4;
      if (pixel % 480 !== 0) {
        const previous = i - 4;
        if (Math.abs(r - pixels[previous]) + Math.abs(g - pixels[previous + 1]) + Math.abs(b - pixels[previous + 2]) > 60) edges += 1;
        edgeSamples += 1;
      }
    }
    return { grayRatio: gray / count, paleRatio: pale / count, greenRatio: green / count, darkRatio: dark / count, edgeRatio: edges / edgeSamples };
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
  emitProgress('browser-launched');
  const page = await browser.newPage();
  try {
    await installProbeRomRoute(page, PROBE_ROM);
    await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
    emitProgress('page-loaded');
    await page.click('#playBtn');
    await page.waitForFunction(() => (
      typeof window.__mGBA?._readGbaByte === 'function'
      && document.querySelector('.speed-btn[data-speed="1"]')?.disabled === false
      && window.__mGBA._readGbaByte(0x08000000) !== -1
    ), { timeout: 90000, polling: 1000 });
    emitProgress('core-ready');
    const saveLoad = await loadSaveExport(page);
    const stateLoad = await loadStateCheckpoint(page);
    if (stateLoad || saveLoad) emitProgress('checkpoint-loaded', { kind: stateLoad ? 'state' : 'save' });
    const inputAudit = { explicitInputs: [], automaticInputs: [] };
    const playerControlEvidenceTracker = createPlayerControlEvidenceTracker({
      page,
      inputAudit,
    });
    await playerControlEvidenceTracker.captureBaseline();
    const evidenceMode = process.env.PROBE_EVIDENCE_MODE || '';
    const legacyEvidenceStop = allowsLegacyEvidenceStop(evidenceMode);
    const alternateChapterBaseline = await readAlternateChapterProbe(page);
    const probeSpeed = String(process.env.PROBE_SPEED || '4');
    await page.evaluate(speed => document.querySelector(`.speed-btn[data-speed="${speed}"]`)?.click(), probeSpeed);
    const initialSaveRecords = await readSaveRecords(page);
    const plan = buildNavigationPlan({
      startCount: Number(process.env.PROBE_START_COUNT ?? 30),
      advanceCount: Number(process.env.PROBE_ADVANCE_COUNT ?? 80),
      startDelayMs: Number(process.env.PROBE_START_DELAY_MS ?? 3000),
      confirmDelayMs: Number(process.env.PROBE_CONFIRM_DELAY_MS ?? 1500),
      advanceDelayMs: Number(process.env.PROBE_ADVANCE_DELAY_MS ?? 3000),
      keyHoldMs: Number(process.env.PROBE_KEY_HOLD_MS ?? 125),
      tailDelayMs: Number(process.env.PROBE_TAIL_DELAY_MS ?? 600),
      tailRepeat: Number(process.env.PROBE_TAIL_REPEAT ?? 1),
      tailKeys: (process.env.PROBE_TAIL_KEYS || '').split(',').map(key => key.trim()).filter(Boolean),
      skipNewGame: process.env.PROBE_SKIP_NEW_GAME === '1',
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
    let arrivalFirstPoll = null;
    const stages = [];
    for (let index = 0; index < plan.length; index += 1) {
      const action = plan[index];
      emitProgress('phase-start', { phase: action.phase, step: index + 1 });
      await sleep(action.delayMs);
      await pressGbaKey(page, action.key, action.holdMs, inputAudit, 'explicit');
      let screenMetrics = null;
      let screenState = null;
      let adaptiveRetries = 0;
      if (action.phase === 'tail' && action.key === 'KeyX' && process.env.PROBE_ADAPTIVE_BACK !== '0') {
        screenMetrics = await captureScreenMetrics(page);
        screenState = classifyScreenMetrics(screenMetrics);
        let decision = tailTransitionDecision(screenState);
        while (decision !== 'ready' && adaptiveRetries < 20) {
          adaptiveRetries += 1;
          await sleep(action.delayMs);
          if (shouldRetryBack(decision, adaptiveRetries)) {
            await pressGbaKey(page, action.key, action.holdMs, inputAudit, 'automatic');
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
        occupiedUnitSummaries: extractOccupiedUnitSummaries(snapshot),
        runtimeTemplates,
        templateMatches,
        characterDefinitionMatches,
        battleControl,
        mapRuntime,
        saveProbeHex: Buffer.from(await readGbaBytes(page, SAVE_PROBE_RESULT, 2)).toString('hex'),
        effectProbeHex: Buffer.from(await readGbaBytes(page, EFFECT_PROBE_RESULT, 16)).toString('hex'),
        chapterScriptProbe: decodeChapterScriptProbe(await readGbaBytes(page, CHAPTER_SCRIPT_PROBE_RESULT, 12)),
        alternateChapterProbe: await captureAlternateChapterEvidence(page, alternateChapterBaseline),
        saveGroupProbeHex: Buffer.from(await readGbaBytes(page, SAVE_GROUP_PROBE_RESULT, 8)).toString('hex'),
        audioProbeHex: Buffer.from(await readGbaBytes(page, AUDIO_PROBE_RESULT, 16)).toString('hex'),
        naturalSaveProbeHex: Buffer.from(await readGbaBytes(page, NATURAL_SAVE_PROBE_RESULT, 4)).toString('hex'),
        naturalLoadProbeHex: Buffer.from(await readGbaBytes(page, NATURAL_LOAD_PROBE_RESULT, 4)).toString('hex'),
        postbattleProbeLatchHex: Buffer.from(await readGbaBytes(page, POSTBATTLE_PROBE_LATCH, 4)).toString('hex'),
        forcedSaveCaseHitHex: Buffer.from(await readGbaBytes(page, FORCED_SAVE_CASE_HIT, 4)).toString('hex'),
        screenMetrics,
        screenState,
        adaptiveRetries,
      };
      await playerControlEvidenceTracker.attachEvidence(lastDiagnostic);
      if (evidenceMode === 'player-control' && lastDiagnostic.playerControlEvidence.verified) {
        lastDiagnostic.saveRecords = compareSaveRecords(initialSaveRecords, await readSaveRecords(page));
        lastDiagnostic.saveExport = await persistSaveExport(page);
        lastDiagnostic.stateLoad = stateLoad;
        lastDiagnostic.saveLoad = saveLoad;
        lastDiagnostic.stateExport = await persistStateExport(page);
        lastDiagnostic.memoryDump = await persistMemoryDump(page);
        lastDiagnostic.mapResourceDumps = await persistMapResourceDumps(page);
        await page.screenshot({ path: artifacts.finalScreenshotPath });
        writeProbeResult(artifacts.resultPath, buildProbeResult({
          outcome: 'verified',
          reason: lastDiagnostic.playerControlEvidence.reason,
          stages,
          final: lastDiagnostic,
        }));
        return;
      }
      if (legacyEvidenceStop && shouldStopForAlternateChapter(lastDiagnostic.alternateChapterProbe)) {
        lastDiagnostic.saveRecords = compareSaveRecords(initialSaveRecords, await readSaveRecords(page));
        lastDiagnostic.saveExport = await persistSaveExport(page);
        lastDiagnostic.stateLoad = stateLoad;
        lastDiagnostic.saveLoad = saveLoad;
        lastDiagnostic.stateExport = await persistStateExport(page);
        lastDiagnostic.memoryDump = await persistMemoryDump(page);
        lastDiagnostic.mapResourceDumps = await persistMapResourceDumps(page);
        await page.screenshot({ path: artifacts.finalScreenshotPath });
        writeProbeResult(artifacts.resultPath, buildProbeResult({
          outcome: 'verified',
          reason: lastDiagnostic.alternateChapterProbe.evidence.reason,
          stages,
          final: lastDiagnostic,
        }));
        return;
      }
      if (runtimePositions.length > 0) {
        const match = matchFormationPositions(BANK.entries, runtimePositions);
        latestMatch = match;
        const arrival = evaluateBattleArrival({ match, battleControl, mapRuntime, screenState });
        lastDiagnostic.arrival = arrival;
        console.log(JSON.stringify({ step: index + 1, phase: action.phase, status, runtimePositions, match, screenState, arrival }));
        if (legacyEvidenceStop && STOP_ON_MATCH && arrival.arrived) {
          lastDiagnostic.saveRecords = compareSaveRecords(initialSaveRecords, await readSaveRecords(page));
          lastDiagnostic.saveExport = await persistSaveExport(page);
          lastDiagnostic.stateLoad = stateLoad;
          lastDiagnostic.saveLoad = saveLoad;
          lastDiagnostic.stateExport = await persistStateExport(page);
          lastDiagnostic.memoryDump = await persistMemoryDump(page);
          lastDiagnostic.mapResourceDumps = await persistMapResourceDumps(page);
          await page.screenshot({ path: artifacts.finalScreenshotPath });
          writeProbeResult(artifacts.resultPath, buildProbeResult({ outcome: 'matched', reason: arrival.reason, stages, final: lastDiagnostic, match }));
          return;
        }
      } else if (status.state === 'changed') {
        console.log(JSON.stringify({ step: index + 1, phase: action.phase, status }));
      }
      const nextPhase = plan[index + 1]?.phase;
      if (nextPhase !== action.phase) {
        if (process.env.PROBE_STATE_DUMP_PHASE === action.phase) {
          lastDiagnostic.stateExport = await persistStateExport(page);
        }
        const screenshotPath = artifacts.phaseScreenshot(action.phase);
        await page.screenshot({ path: screenshotPath });
        stages.push({ ...lastDiagnostic, screenshotPath });
      }
      previous = snapshot;
    }
    if (legacyEvidenceStop && !STOP_ON_MATCH
        && process.env.PROBE_FORCE_SETTLE !== '1' && lastDiagnostic?.arrival?.arrived) {
      lastDiagnostic.saveRecords = compareSaveRecords(initialSaveRecords, await readSaveRecords(page));
      lastDiagnostic.saveExport = await persistSaveExport(page);
      lastDiagnostic.stateLoad = stateLoad;
      lastDiagnostic.saveLoad = saveLoad;
      lastDiagnostic.stateExport = await persistStateExport(page);
      lastDiagnostic.memoryDump = await persistMemoryDump(page);
      lastDiagnostic.mapResourceDumps = await persistMapResourceDumps(page);
      await page.screenshot({ path: artifacts.finalScreenshotPath });
      writeProbeResult(artifacts.resultPath, buildProbeResult({ outcome: 'matched', reason: 'strict-battle-arrival-after-full-plan', stages, final: lastDiagnostic, match: latestMatch }));
      return;
    }
    for (const settle of settlePlan) {
      emitProgress('phase-start', { phase: settle.phase, step: plan.length + settle.poll });
      await sleep(settle.delayMs);
      if (settle.key && arrivalFirstPoll === null) {
        await pressGbaKey(page, settle.key, settle.holdMs, inputAudit, 'automatic');
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
        occupiedUnitSummaries: extractOccupiedUnitSummaries(snapshot),
        runtimeTemplates,
        templateMatches,
        characterDefinitionMatches,
        battleControl,
        mapRuntime,
        saveProbeHex: Buffer.from(await readGbaBytes(page, SAVE_PROBE_RESULT, 2)).toString('hex'),
        effectProbeHex: Buffer.from(await readGbaBytes(page, EFFECT_PROBE_RESULT, 16)).toString('hex'),
        chapterScriptProbe: decodeChapterScriptProbe(await readGbaBytes(page, CHAPTER_SCRIPT_PROBE_RESULT, 12)),
        alternateChapterProbe: await captureAlternateChapterEvidence(page, alternateChapterBaseline),
        saveGroupProbeHex: Buffer.from(await readGbaBytes(page, SAVE_GROUP_PROBE_RESULT, 8)).toString('hex'),
        audioProbeHex: Buffer.from(await readGbaBytes(page, AUDIO_PROBE_RESULT, 16)).toString('hex'),
        naturalSaveProbeHex: Buffer.from(await readGbaBytes(page, NATURAL_SAVE_PROBE_RESULT, 4)).toString('hex'),
        naturalLoadProbeHex: Buffer.from(await readGbaBytes(page, NATURAL_LOAD_PROBE_RESULT, 4)).toString('hex'),
        postbattleProbeLatchHex: Buffer.from(await readGbaBytes(page, POSTBATTLE_PROBE_LATCH, 4)).toString('hex'),
        forcedSaveCaseHitHex: Buffer.from(await readGbaBytes(page, FORCED_SAVE_CASE_HIT, 4)).toString('hex'),
        screenMetrics,
        screenState,
      };
      await playerControlEvidenceTracker.attachEvidence(lastDiagnostic);
      if (evidenceMode === 'player-control' && lastDiagnostic.playerControlEvidence.verified) {
        lastDiagnostic.saveRecords = compareSaveRecords(initialSaveRecords, await readSaveRecords(page));
        lastDiagnostic.saveExport = await persistSaveExport(page);
        lastDiagnostic.stateLoad = stateLoad;
        lastDiagnostic.saveLoad = saveLoad;
        lastDiagnostic.stateExport = await persistStateExport(page);
        lastDiagnostic.memoryDump = await persistMemoryDump(page);
        lastDiagnostic.mapResourceDumps = await persistMapResourceDumps(page);
        const screenshotPath = artifacts.phaseScreenshot('settle');
        await page.screenshot({ path: screenshotPath });
        stages.push({ ...lastDiagnostic, screenshotPath });
        await page.screenshot({ path: artifacts.finalScreenshotPath });
        writeProbeResult(artifacts.resultPath, buildProbeResult({
          outcome: 'verified',
          reason: lastDiagnostic.playerControlEvidence.reason,
          stages,
          final: lastDiagnostic,
        }));
        return;
      }
      if (runtimePositions.length > 0) {
        const match = matchFormationPositions(BANK.entries, runtimePositions);
        const arrival = evaluateBattleArrival({ match, battleControl, mapRuntime, screenState });
        lastDiagnostic.arrival = arrival;
        console.log(JSON.stringify({ ...lastDiagnostic, match, arrival }));
        if (legacyEvidenceStop && arrival.arrived) {
          if (arrivalFirstPoll === null) arrivalFirstPoll = settle.poll;
          if (settle.poll - arrivalFirstPoll < POST_ARRIVAL_POLLS) {
            previous = snapshot;
            continue;
          }
          lastDiagnostic.saveRecords = compareSaveRecords(initialSaveRecords, await readSaveRecords(page));
          lastDiagnostic.saveExport = await persistSaveExport(page);
          lastDiagnostic.stateLoad = stateLoad;
          lastDiagnostic.saveLoad = saveLoad;
          lastDiagnostic.stateExport = await persistStateExport(page);
          lastDiagnostic.memoryDump = await persistMemoryDump(page);
          lastDiagnostic.mapResourceDumps = await persistMapResourceDumps(page);
          const screenshotPath = artifacts.phaseScreenshot('settle');
          await page.screenshot({ path: screenshotPath });
          stages.push({ ...lastDiagnostic, screenshotPath });
          await page.screenshot({ path: artifacts.finalScreenshotPath });
          writeProbeResult(artifacts.resultPath, buildProbeResult({ outcome: 'matched', reason: 'strict-battle-arrival-after-settle', stages, final: lastDiagnostic, match }));
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
    if (lastDiagnostic) {
      lastDiagnostic.saveRecords = compareSaveRecords(initialSaveRecords, await readSaveRecords(page));
      lastDiagnostic.saveExport = await persistSaveExport(page);
      lastDiagnostic.stateLoad = stateLoad;
      lastDiagnostic.saveLoad = saveLoad;
      lastDiagnostic.stateExport = await persistStateExport(page);
      lastDiagnostic.memoryDump = await persistMemoryDump(page);
      lastDiagnostic.mapResourceDumps = await persistMapResourceDumps(page);
    }
    await page.screenshot({ path: artifacts.finalScreenshotPath });
    if (legacyEvidenceStop && lastDiagnostic?.alternateChapterProbe?.evidence?.verified) {
      const result = buildProbeResult({
        outcome: 'verified',
        reason: lastDiagnostic.alternateChapterProbe.evidence.reason,
        stages,
        final: lastDiagnostic,
      });
      writeProbeResult(artifacts.resultPath, result);
      return;
    }
    const result = buildProbeResult({ outcome: 'not-found', reason: 'settle-exhausted', stages, final: lastDiagnostic });
    writeProbeResult(artifacts.resultPath, result);
    throw new Error(`navigation and settle polling ended before a unique formation was observed; result=${artifacts.resultPath}; screenshot=${artifacts.finalScreenshotPath}; last=${JSON.stringify(lastDiagnostic)}`);
  } finally {
    await browser.close();
  }
}

if (require.main === module) main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });

module.exports = {
  allowsLegacyEvidenceStop,
  createPlayerControlEvidenceTracker,
  decodePlayerControlProbe,
  formatProgress,
  extractRuntimePositions,
  extractOccupiedUnitSummaries,
  extractRuntimeTemplates,
  focusGameSurface,
  matchTemplatesToCharacterDefinitions,
  matchTemplatesToUnits,
  captureAlternateChapterEvidence,
  mapResourceDumpSpecs,
  pressGbaKey,
  shouldStopForAlternateChapter,
  readGbaBytes,
  readSaveRecords,
};
