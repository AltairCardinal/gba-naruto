'use strict';

const DEFAULTS = Object.freeze({
  startCount: 30,
  advanceCount: 80,
  startDelayMs: 3000,
  confirmDelayMs: 1500,
  advanceDelayMs: 3000,
  keyHoldMs: 125,
  tailDelayMs: 600,
});

function boundedInteger(value, fallback, name) {
  const number = value === undefined ? fallback : Number(value);
  if (!Number.isInteger(number) || number < 0) throw new TypeError(`${name} must be a non-negative integer`);
  return number;
}

function buildNavigationPlan(options = {}) {
  const startCount = boundedInteger(options.startCount, DEFAULTS.startCount, 'startCount');
  const advanceCount = boundedInteger(options.advanceCount, DEFAULTS.advanceCount, 'advanceCount');
  const startDelayMs = boundedInteger(options.startDelayMs, DEFAULTS.startDelayMs, 'startDelayMs');
  const confirmDelayMs = boundedInteger(options.confirmDelayMs, DEFAULTS.confirmDelayMs, 'confirmDelayMs');
  const advanceDelayMs = boundedInteger(options.advanceDelayMs, DEFAULTS.advanceDelayMs, 'advanceDelayMs');
  const holdMs = boundedInteger(options.keyHoldMs, DEFAULTS.keyHoldMs, 'keyHoldMs');
  const tailDelayMs = boundedInteger(options.tailDelayMs, DEFAULTS.tailDelayMs, 'tailDelayMs');
  const tailKeys = options.tailKeys || [];
  const skipNewGame = options.skipNewGame === true;
  if (!Array.isArray(tailKeys) || tailKeys.some(key => typeof key !== 'string' || key.length === 0)) {
    throw new TypeError('tailKeys must be an array of non-empty key names');
  }
  return [
    ...Array.from({ length: startCount }, () => ({ phase: 'boot', key: 'Enter', delayMs: startDelayMs, holdMs })),
    ...(skipNewGame ? [] : [{ phase: 'new-game', key: 'KeyZ', delayMs: confirmDelayMs, holdMs }]),
    ...Array.from({ length: advanceCount }, () => ({ phase: 'story', key: 'KeyZ', delayMs: advanceDelayMs, holdMs })),
    ...tailKeys.map(key => ({ phase: 'tail', key, delayMs: tailDelayMs, holdMs })),
  ];
}

function buildSettlePlan(options = {}) {
  const count = boundedInteger(options.count, 20, 'settleCount');
  const delayMs = boundedInteger(options.delayMs, 500, 'settleDelayMs');
  const confirmEvery = boundedInteger(options.confirmEvery, 0, 'settleConfirmEvery');
  const holdMs = boundedInteger(options.keyHoldMs, DEFAULTS.keyHoldMs, 'keyHoldMs');
  return Array.from({ length: count }, (_, index) => {
    const action = { phase: 'settle', poll: index + 1, delayMs };
    if (confirmEvery > 0 && (index + 1) % confirmEvery === 0) {
      action.key = 'KeyZ';
      action.holdMs = holdMs;
    }
    return action;
  });
}

function classifyMemorySnapshot(previous, current) {
  if (!(current instanceof Uint8Array)) throw new TypeError('current must be Uint8Array');
  if (previous !== null && (!(previous instanceof Uint8Array) || previous.length !== current.length)) {
    throw new TypeError('previous must be null or an equally sized Uint8Array');
  }
  let changedBytes = 0;
  let nonzero = 0;
  for (let i = 0; i < current.length; i += 1) {
    if (current[i] !== 0) nonzero += 1;
    if (previous !== null && previous[i] !== current[i]) changedBytes += 1;
  }
  return { state: nonzero === 0 ? 'empty' : changedBytes > 0 ? 'changed' : 'stable', changedBytes };
}

function coordinateKey(position) { return `${Number(position.x)},${Number(position.y)}`; }

function decodeBattleControl(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length !== 8) {
    throw new TypeError('battle control must be an 8-byte Uint8Array');
  }
  return { rawHex: Buffer.from(bytes).toString('hex'), chapterBattleId: bytes[1] };
}

function decodeMapRuntime(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length !== 4) {
    throw new TypeError('map runtime must be a 4-byte Uint8Array');
  }
  const [width, height, gridWidth, gridHeight] = bytes;
  return {
    rawHex: Buffer.from(bytes).toString('hex'),
    width,
    height,
    gridWidth,
    gridHeight,
    derivationConsistent: gridWidth === (width >> 2) && gridHeight === (height >> 1),
  };
}

function decodeChapterScriptProbe(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length !== 12) {
    throw new TypeError('chapter script probe must be a 12-byte Uint8Array');
  }
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const scriptPointer = view.getUint32(0, true);
  return {
    rawHex: Buffer.from(bytes).toString('hex'),
    scriptPointer,
    scriptPointerHex: `0x${scriptPointer.toString(16).toUpperCase().padStart(8, '0')}`,
    opcodeBytesHex: Buffer.from(bytes.subarray(4, 8)).toString('hex'),
    opcode: bytes[4],
    chapterBattleId: bytes[5],
    hitCount: bytes[8],
    pointerInRom: scriptPointer >= 0x08000000 && scriptPointer < 0x0E000000,
  };
}

function classifyScreenMetrics(metrics) {
  const dark = metrics.darkRatio || 0;
  // Texture density is the primary discriminator.  The isometric map can be
  // almost full-frame after the camera moves, so the old "black corners"
  // heuristic alone is not stable across camera positions.
  if ((metrics.edgeRatio || 0) > 0.2 && dark < 0.5) return 'battle-map';
  if (metrics.paleRatio > 0.3) return 'prebattle-menu';
  // Battle maps are diamond-shaped and leave large black viewport corners.
  // Character panels fill the viewport with green UI and almost no black.
  if (dark < 0.05 && metrics.greenRatio > 0.18) return 'character-panel';
  if (metrics.paleRatio < 0.2 && (
    (dark > 0.12 && dark < 0.5)
    || (dark < 0.05 && metrics.greenRatio < 0.18)
  )) return 'battle-map';
  return 'other';
}

function evaluateBattleArrival({ match, battleControl, mapRuntime, screenState }) {
  const checks = {
    uniqueCompleteFormation: Boolean(match?.best && match.best.missing === 0 && match.unique),
    battleIdPresent: Number(battleControl?.chapterBattleId || 0) !== 0,
    mapLoaded: Boolean(
      mapRuntime?.width > 0
      && mapRuntime?.height > 0
      && mapRuntime?.derivationConsistent,
    ),
    battleMapVisible: screenState === 'battle-map',
  };
  return {
    arrived: Object.values(checks).every(Boolean),
    checks,
    reason: Object.values(checks).every(Boolean) ? 'strict-battle-arrival' : 'arrival-evidence-incomplete',
  };
}

function tailTransitionDecision(screenState) {
  if (screenState === 'character-panel') return 'retry-back';
  if (screenState === 'prebattle-menu') return 'ready';
  return 'wait';
}

function shouldRetryBack(decision, poll) {
  return decision === 'retry-back' && poll > 0 && poll % 4 === 0;
}

function matchFormationPositions(entries, runtimePositions) {
  const observed = new Map();
  for (const position of runtimePositions) {
    const key = coordinateKey(position);
    observed.set(key, (observed.get(key) || 0) + 1);
  }
  const groups = new Map();
  for (const entry of entries) {
    if (!entry.active) continue;
    const key = `${entry.group_id}:${entry.variant_id}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(entry);
  }
  const candidates = [];
  for (const [key, records] of groups) {
    const remaining = new Map(observed);
    let matched = 0;
    for (const record of records) {
      const coordinate = coordinateKey(record);
      const count = remaining.get(coordinate) || 0;
      if (count > 0) {
        matched += 1;
        remaining.set(coordinate, count - 1);
      }
    }
    const [groupId, variantId] = key.split(':').map(Number);
    candidates.push({
      groupId,
      variantId,
      matched,
      missing: runtimePositions.length - matched,
      extra: records.length - matched,
    });
  }
  candidates.sort((a, b) => b.matched - a.matched || a.missing - b.missing || a.extra - b.extra || a.groupId - b.groupId || a.variantId - b.variantId);
  const best = candidates[0] || null;
  const tied = best ? candidates.filter(item => item.matched === best.matched && item.missing === best.missing && item.extra === best.extra) : [];
  return { best, unique: tied.length === 1, candidates: tied.length > 1 ? tied : candidates.slice(0, 5) };
}

function buildArtifactPaths(resultPath, finalScreenshotPath) {
  const extension = require('node:path').extname(finalScreenshotPath);
  const stem = finalScreenshotPath.slice(0, -extension.length);
  return {
    resultPath,
    finalScreenshotPath,
    phaseScreenshot: phase => `${stem}-${phase}${extension}`,
  };
}

function buildProbeResult({ outcome, reason, stages, final, match = null }) {
  return { schemaVersion: 1, outcome, reason, stages, final, match };
}

function saveChecksum(bytes) {
  return (~bytes.reduce((sum, byte) => (sum + byte) & 0xFF, 0)) & 0xFF;
}

function decodeSaveRecord(offset, bytes) {
  const data = Array.from(bytes);
  const headerLength = 0x13;
  if (data.length < headerLength + 2) throw new Error(`save record at 0x${offset.toString(16)} must contain header, payload and checksum`);
  const payloadLength = data.length - headerLength - 1;
  const header = data.slice(0, headerLength);
  const payload = data.slice(headerLength, headerLength + payloadLength);
  const expectedChecksum = saveChecksum(payload);
  const erased = data.every(byte => byte === 0xFF);
  return {
    sramOffset: offset,
    sramOffsetHex: `0x${offset.toString(16).toUpperCase().padStart(4, '0')}`,
    rawHex: Buffer.from(data).toString('hex'),
    headerHex: Buffer.from(header).toString('hex'),
    erased,
    payloadLength,
    checksum: data[headerLength + payloadLength],
    expectedChecksum,
    checksumValid: erased || data[headerLength + payloadLength] === expectedChecksum,
  };
}

function compareSaveRecords(before, after) {
  return after.map(record => {
    const old = before.find(candidate => candidate.sramOffset === record.sramOffset);
    return { ...record, changed: Boolean(old && old.rawHex !== record.rawHex), beforeRawHex: old?.rawHex || null };
  });
}

module.exports = {
  buildNavigationPlan, classifyMemorySnapshot, matchFormationPositions,
  buildArtifactPaths, buildProbeResult, buildSettlePlan, decodeBattleControl,
  decodeMapRuntime, classifyScreenMetrics, tailTransitionDecision, shouldRetryBack,
  decodeSaveRecord, compareSaveRecords, saveChecksum, evaluateBattleArrival,
  decodeChapterScriptProbe,
};
