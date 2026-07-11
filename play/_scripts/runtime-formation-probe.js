#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const puppeteer = require('/tmp/gba-puppeteer/node_modules/puppeteer-core');
const {
  buildNavigationPlan, classifyMemorySnapshot, matchFormationPositions,
  buildArtifactPaths, buildProbeResult,
  buildSettlePlan, decodeBattleControl, decodeMapRuntime, classifyScreenMetrics,
  tailTransitionDecision, shouldRetryBack,
} = require('./runtime-formation-probe-lib');

const URL = process.env.PROBE_URL || 'https://sh.kibox.com.cn/gba-naruto/play/';
const BROWSER_EXECUTABLE = process.env.PROBE_BROWSER || '/usr/bin/chromium';
const PROBE_ROM = process.env.PROBE_ROM || '';
const ROOT = path.resolve(__dirname, '..', '..');
const BANK = JSON.parse(fs.readFileSync(path.join(ROOT, 'sequel/content/positions/bank.json'), 'utf8'));
const WRAM_BASE = 0x020240C0;
const UNIT_STRIDE = 0x1D4;
// 0x02026804 is the next proven battle-control block. With 0x1D4-byte unit
// records, only slots 0..20 fit before it; scanning slot 21+ reads unrelated
// control data and creates false (0,0) units.
const SLOT_COUNT = 21;
const BATTLE_CONTROL = 0x02026804;
const MAP_RUNTIME = 0x0201BE28;
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
    const stages = [];
    for (let index = 0; index < plan.length; index += 1) {
      const action = plan[index];
      await sleep(action.delayMs);
      await pressGbaKey(page, action.key, action.holdMs);
      let screenState = null;
      let adaptiveRetries = 0;
      if (action.phase === 'tail' && action.key === 'KeyX') {
        screenState = classifyScreenMetrics(await captureScreenMetrics(page));
        let decision = tailTransitionDecision(screenState);
        while (decision !== 'ready' && adaptiveRetries < 20) {
          adaptiveRetries += 1;
          await sleep(action.delayMs);
          if (shouldRetryBack(decision, adaptiveRetries)) {
            await pressGbaKey(page, action.key, action.holdMs);
          }
          screenState = classifyScreenMetrics(await captureScreenMetrics(page));
          decision = tailTransitionDecision(screenState);
        }
      }
      const snapshot = await readGbaBytes(page, WRAM_BASE, UNIT_STRIDE * SLOT_COUNT);
      const battleControl = decodeBattleControl(await readGbaBytes(page, BATTLE_CONTROL, 8));
      const mapRuntime = decodeMapRuntime(await readGbaBytes(page, MAP_RUNTIME, 4));
      const status = classifyMemorySnapshot(previous, snapshot);
      const runtimePositions = extractRuntimePositions(snapshot);
      lastDiagnostic = {
        step: index + 1,
        phase: action.phase,
        status,
        nonzeroBytes: snapshot.reduce((count, byte) => count + (byte !== 0), 0),
        firstBytesHex: Buffer.from(snapshot.subarray(0, 16)).toString('hex'),
        runtimePositions,
        battleControl,
        mapRuntime,
        screenState,
        adaptiveRetries,
      };
      if (runtimePositions.length > 0) {
        const match = matchFormationPositions(BANK.entries, runtimePositions);
        console.log(JSON.stringify({ step: index + 1, phase: action.phase, status, runtimePositions, match }));
        if (match.best && match.best.missing === 0 && match.unique) {
          await page.screenshot({ path: artifacts.finalScreenshotPath });
          fs.writeFileSync(artifacts.resultPath, `${JSON.stringify(buildProbeResult({ outcome: 'matched', reason: 'unique-formation', stages, final: lastDiagnostic, match }), null, 2)}\n`);
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
    for (const settle of settlePlan) {
      await sleep(settle.delayMs);
      if (settle.key) {
        await pressGbaKey(page, settle.key, settle.holdMs);
      }
      const snapshot = await readGbaBytes(page, WRAM_BASE, UNIT_STRIDE * SLOT_COUNT);
      const battleControl = decodeBattleControl(await readGbaBytes(page, BATTLE_CONTROL, 8));
      const mapRuntime = decodeMapRuntime(await readGbaBytes(page, MAP_RUNTIME, 4));
      const status = classifyMemorySnapshot(previous, snapshot);
      const runtimePositions = extractRuntimePositions(snapshot);
      lastDiagnostic = {
        step: plan.length + settle.poll,
        phase: settle.phase,
        poll: settle.poll,
        recoveryKey: settle.key || null,
        status,
        nonzeroBytes: snapshot.reduce((count, byte) => count + (byte !== 0), 0),
        firstBytesHex: Buffer.from(snapshot.subarray(0, 16)).toString('hex'),
        runtimePositions,
        battleControl,
        mapRuntime,
      };
      if (runtimePositions.length > 0) {
        const match = matchFormationPositions(BANK.entries, runtimePositions);
        console.log(JSON.stringify({ ...lastDiagnostic, match }));
        if (match.best && match.best.missing === 0 && match.unique) {
          const screenshotPath = artifacts.phaseScreenshot('settle');
          await page.screenshot({ path: screenshotPath });
          stages.push({ ...lastDiagnostic, screenshotPath });
          await page.screenshot({ path: artifacts.finalScreenshotPath });
          fs.writeFileSync(artifacts.resultPath, `${JSON.stringify(buildProbeResult({ outcome: 'matched', reason: 'unique-formation-after-settle', stages, final: lastDiagnostic, match }), null, 2)}\n`);
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

module.exports = { extractRuntimePositions, focusGameSurface, readGbaBytes };
