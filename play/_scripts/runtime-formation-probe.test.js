'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildNavigationPlan,
  classifyMemorySnapshot,
  matchFormationPositions,
  buildArtifactPaths,
  buildProbeResult,
  buildSettlePlan,
  decodeBattleControl,
  decodeMapRuntime,
  classifyScreenMetrics,
  evaluateBattleArrival,
  decodeChapterScriptProbe,
  decodeAlternateChapterProbe,
  evaluateAlternateChapterEvidence,
  tailTransitionDecision,
  shouldRetryBack,
  decodeSaveRecord,
  compareSaveRecords,
} = require('./runtime-formation-probe-lib');
const {
  captureAlternateChapterEvidence,
  createPlayerControlEvidenceTracker,
  decodePlayerControlProbe,
  extractOccupiedUnitSummaries,
  formatProgress,
  pressGbaKey,
  shouldStopForAlternateChapter,
  mapResourceDumpSpecs,
  allowsLegacyEvidenceStop,
} = require('./runtime-formation-probe');

test('decodePlayerControlProbe validates the dedicated published sample', () => {
  const bytes = Buffer.from('50434f31030000000900000000000100', 'hex');
  assert.deepEqual(decodePlayerControlProbe(bytes), {
    rawHex: '50434f31030000000900000000000100',
    magicValid: true,
    hitCount: 3,
    argument0: 9,
    argument1: 0,
    argument2: 1,
  });
  bytes[0] = 0;
  assert.equal(decodePlayerControlProbe(bytes).magicValid, false);

  const currentUnit = Buffer.from('50435531010000000100000000000000', 'hex');
  assert.equal(decodePlayerControlProbe(currentUnit, 0x31554350).magicValid, true);
});

test('runtime evidence wiring reads immutable 24-byte baseline and plan/settle diagnostics', async () => {
  const reads = [];
  const counters = new Map();
  const fakeReadGbaBytes = async (_page, address, length) => {
    reads.push({ address, length });
    const hitCount = counters.get(address) || 0;
    counters.set(address, hitCount + 1);
    const bytes = Buffer.alloc(24);
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const player = address === 0x0203F080;
    view.setUint32(0, player ? 0x314F4350 : 0x31554350, true);
    view.setUint32(4, hitCount, true);
    view.setUint32(8, 1, true);
    view.setUint16(14, 1, true);
    view.setUint32(16, hitCount === 0 ? 0 : (hitCount * 2) - (player ? 1 : 0), true);
    view.setUint32(20, player ? 1 : 2, true);
    return bytes;
  };
  const inputAudit = { explicitInputs: ['KeyZ'], automaticInputs: [] };
  const tracker = createPlayerControlEvidenceTracker({
    page: {},
    readGbaBytes: fakeReadGbaBytes,
    inputAudit,
  });
  const baseline = await tracker.captureBaseline();
  assert.equal(Object.isFrozen(baseline), true);

  const diagnostic = phase => ({
    phase,
    battleControl: { chapterBattleId: 41 },
    mapRuntime: { width: 36, height: 44, derivationConsistent: true },
    screenState: 'battle-map',
    occupiedUnitSummaries: [{ slot: 1, characterId: 1 }],
  });
  const plan = await tracker.attachEvidence(diagnostic('tail'));
  inputAudit.automaticInputs.push('KeyZ');
  const settle = await tracker.attachEvidence(diagnostic('settle'));

  assert.equal(plan.playerControlEvidence.verified, true);
  assert.deepEqual(plan.inputAudit, { explicitInputs: ['KeyZ'], automaticInputs: [] });
  assert.equal(settle.playerControlEvidence.verified, false);
  assert.equal(settle.playerControlEvidence.reason, 'unlisted-input-used');
  assert.deepEqual(settle.inputAudit, {
    explicitInputs: ['KeyZ'],
    automaticInputs: ['KeyZ'],
  });
  assert.deepEqual(reads, [
    { address: 0x0203F080, length: 24 },
    { address: 0x0203F060, length: 24 },
    { address: 0x0203F080, length: 24 },
    { address: 0x0203F060, length: 24 },
    { address: 0x0203F080, length: 24 },
    { address: 0x0203F060, length: 24 },
  ]);
});

test('pressGbaKey audits plan/tail input as explicit and recovery input as automatic', async () => {
  const pressed = [];
  const page = {
    evaluate: async (_callback, gbaKey) => pressed.push(gbaKey),
  };
  const audit = { explicitInputs: [], automaticInputs: [] };

  await pressGbaKey(page, 'KeyZ', 0, audit, 'explicit');
  await pressGbaKey(page, 'KeyX', 0, audit, 'explicit');
  await pressGbaKey(page, 'KeyX', 0, audit, 'automatic');
  await pressGbaKey(page, 'KeyZ', 0, audit, 'automatic');

  assert.deepEqual(audit, {
    explicitInputs: ['KeyZ', 'KeyX'],
    automaticInputs: ['KeyX', 'KeyZ'],
  });
  assert.equal(pressed.length, 8);
});

test('settle confirm interval zero produces no audited input', async () => {
  const audit = { explicitInputs: [], automaticInputs: [] };
  const settlePlan = buildSettlePlan({ count: 3, delayMs: 0, confirmEvery: 0 });
  for (const settle of settlePlan) {
    if (settle.key) await pressGbaKey({}, settle.key, 0, audit, 'automatic');
  }
  assert.deepEqual(audit, { explicitInputs: [], automaticInputs: [] });
});

test('player-control evidence mode rejects every legacy arrival success path', () => {
  assert.equal(allowsLegacyEvidenceStop('player-control'), false);
  assert.equal(allowsLegacyEvidenceStop(''), true);
  assert.equal(allowsLegacyEvidenceStop('alternate-chapter'), true);
});

test('formatProgress emits one parseable resource-progress JSON line', () => {
  const line = formatProgress(
    'browser-launched',
    { pid: 123 },
    () => new Date('2026-07-14T00:00:00.000Z'),
  );
  assert.equal(line.includes('\n'), false);
  assert.deepEqual(JSON.parse(line), {
    type: 'resource-progress',
    stage: 'browser-launched',
    timestamp: '2026-07-14T00:00:00.000Z',
    details: { pid: 123 },
  });
});

test('runtime probe wires progress to every required lifecycle boundary only', () => {
  const source = require('node:fs').readFileSync(require.resolve('./runtime-formation-probe'), 'utf8');
  const wiredStages = [...source.matchAll(/emitProgress\('([^']+)'/g)].map(match => match[1]);
  const requiredStages = [
    'browser-launched',
    'page-loaded',
    'core-ready',
    'checkpoint-loaded',
    'phase-start',
    'result-written',
  ];
  assert.deepEqual([...new Set(wiredStages)].sort(), requiredStages.sort());
  for (const stage of requiredStages) assert.ok(wiredStages.includes(stage), `missing ${stage}`);
  assert.match(
    source,
    /if \(stateLoad \|\| saveLoad\) emitProgress\('checkpoint-loaded'/,
    'checkpoint-loaded must only be emitted after an actual state/save load',
  );
});

test('package exposes the shared guarded runtime-probe entry', () => {
  const packageJson = require('./package.json');
  assert.equal(packageJson.scripts.test, 'node --test runtime-formation-probe.test.js');
  assert.equal(
    packageJson.scripts['probe:guarded'],
    'python ../../tools/run_guarded.py --summary ../../build/resource-guard/runtime-probe.json --lock-file ../../build/resource-guard/heavy.lock -- node runtime-formation-probe.js',
  );
});

test('extractOccupiedUnitSummaries preserves raw stat and coordinate evidence', () => {
  const bytes = new Uint8Array(0x1D4 * 2);
  const base = 0x1D4;
  bytes[base] = 7;
  bytes[base + 0x0C] = 0x34;
  bytes[base + 0x0D] = 0x12;
  bytes[base + 0x0E] = 0x78;
  bytes[base + 0x0F] = 0x56;
  bytes[base + 0xC4] = 9;
  bytes[base + 0xC5] = 10;
  const result = extractOccupiedUnitSummaries(bytes);
  assert.equal(result.length, 1);
  assert.deepEqual(
    { slot: result[0].slot, characterId: result[0].characterId, value0c: result[0].value0c, value0e: result[0].value0e, x: result[0].x, y: result[0].y },
    { slot: 1, characterId: 7, value0c: 0x1234, value0e: 0x5678, x: 9, y: 10 },
  );
});
const {
  extractRuntimePositions,
  extractRuntimeTemplates,
  focusGameSurface,
  matchTemplatesToCharacterDefinitions,
  matchTemplatesToUnits,
} = require('./runtime-formation-probe');

test('extractRuntimePositions stops before battle-control memory', () => {
  const stride = 0x1D4;
  const snapshot = new Uint8Array(stride * 24);
  snapshot[stride + 0xC4] = 4;
  snapshot[stride + 0xC5] = 4;
  snapshot[stride + 0xC7] = 4;
  snapshot[stride + 0xC8] = 4;
  // Slot 21 starts at 0x02026724 and crosses the 0x02026804 control block.
  snapshot[stride * 21 + 0xC4] = 7;
  snapshot[stride * 21 + 0xC5] = 8;
  snapshot[stride * 21 + 0xC7] = 7;
  snapshot[stride * 21 + 0xC8] = 8;

  assert.deepEqual(extractRuntimePositions(snapshot), [{ slot: 1, characterId: 0, x: 4, y: 4 }]);
});

test('focusGameSurface focuses the page without clicking the touch-sensitive canvas', async () => {
  const clicks = [];
  const evaluations = [];
  await focusGameSurface({
    mouse: { click: async (x, y) => clicks.push([x, y]) },
    evaluate: async callback => {
      evaluations.push(callback.toString());
    },
  });
  assert.deepEqual(clicks, []);
  assert.equal(evaluations.length, 1);
});

test('decodeSaveRecord validates header plus payload plus NOT-sum checksum', () => {
  const bytes = Buffer.alloc(21, 0);
  bytes[19] = 1;
  bytes[20] = 0xFE;
  assert.deepEqual(decodeSaveRecord(0x1C, bytes), {
    sramOffset: 0x1C,
    sramOffsetHex: '0x001C',
    rawHex: `${'00'.repeat(19)}01fe`,
    headerHex: '00'.repeat(19),
    erased: false,
    payloadLength: 1,
    checksum: 0xFE,
    expectedChecksum: 0xFE,
    checksumValid: true,
  });
});

test('compareSaveRecords identifies changed SRAM records', () => {
  const before = [decodeSaveRecord(0x1C, Buffer.alloc(21, 0xFF))];
  const changed = Buffer.alloc(21, 0);
  changed[20] = 0xFF;
  const result = compareSaveRecords(before, [decodeSaveRecord(0x1C, changed)]);
  assert.equal(result[0].changed, true);
  assert.equal(result[0].checksumValid, true);
  assert.equal(result[0].beforeRawHex, 'ff'.repeat(21));
});

test('extractRuntimeTemplates reports non-empty character templates', () => {
  const stride = 0xBC;
  const snapshot = new Uint8Array(stride * 24);
  snapshot[stride * 3] = 1;
  snapshot[stride * 3 + 1] = 0x0e;
  snapshot[stride * 3 + 2] = 0x0d;
  snapshot[stride * 3 + 3] = 0x08;

  assert.deepEqual(extractRuntimeTemplates(snapshot), [{
    slot: 3,
    characterId: 1,
    first16Hex: '010e0d08000000000000000000000000',
  }]);
});

test('matchTemplatesToUnits links copied template bytes to unit slots', () => {
  const templateStride = 0xBC;
  const unitStride = 0x1D4;
  const templateSnapshot = new Uint8Array(templateStride * 24);
  const unitSnapshot = new Uint8Array(unitStride * 21);
  const templateStart = templateStride * 2;
  const unitStart = unitStride * 1;
  for (let i = 0; i < templateStride; i += 1) {
    templateSnapshot[templateStart + i] = i % 251;
    unitSnapshot[unitStart + i] = i % 251;
  }
  templateSnapshot[templateStart] = 1;
  unitSnapshot[unitStart] = 1;

  assert.deepEqual(matchTemplatesToUnits(
    templateSnapshot,
    unitSnapshot,
    [{ slot: 1, characterId: 1, x: 4, y: 4 }],
  ), [{
    unitSlot: 1,
    characterId: 1,
    unitFirst16Hex: '010102030405060708090a0b0c0d0e0f',
    matchingTemplateSlots: [2],
  }]);
});

test('matchTemplatesToCharacterDefinitions links template payload to ROM raw record', () => {
  const templateStride = 0xBC;
  const record = Buffer.from('010e0d08030505000f00500002010000', 'hex');
  const templateSnapshot = new Uint8Array(templateStride * 24);
  const templateStart = templateStride * 1;
  templateSnapshot[templateStart] = 1;
  templateSnapshot.set(record, templateStart + 1);

  const rawHex = record.toString('hex').padEnd(0xB4 * 2, '0');
  const mismatchedRawHex = `${rawHex.slice(0, -2)}ff`;
  assert.deepEqual(matchTemplatesToCharacterDefinitions(templateSnapshot, {
    entries: [{
      character_id: 1,
      rom_offset_hex: '0x5424D0',
      raw_hex: mismatchedRawHex,
    }],
  }), [{
    templateSlot: 1,
    characterId: 1,
    romOffsetHex: '0x5424D0',
    templateRecordFirst16Hex: '010e0d08030505000f00500002010000',
    romRecordFirst16Hex: '010e0d08030505000f00500002010000',
    matchingPrefixBytes: 179,
    firstMismatchOffset: 179,
    rawRecordMatchesRom: false,
  }]);

  templateSnapshot.fill(0, templateStart + 1);
  templateSnapshot.set(Buffer.from(rawHex, 'hex'), templateStart + 1);
  assert.deepEqual(matchTemplatesToCharacterDefinitions(templateSnapshot, {
    entries: [{
      character_id: 1,
      rom_offset_hex: '0x5424D0',
      raw_hex: rawHex,
    }],
  })[0], {
    templateSlot: 1,
    characterId: 1,
    romOffsetHex: '0x5424D0',
    templateRecordFirst16Hex: '010e0d08030505000f00500002010000',
    romRecordFirst16Hex: '010e0d08030505000f00500002010000',
    matchingPrefixBytes: 180,
    firstMismatchOffset: null,
    rawRecordMatchesRom: true,
  });

  assert.equal(matchTemplatesToCharacterDefinitions(templateSnapshot, {
    entries: [{
      character_id: 1,
      rom_offset_hex: '0x5424D0',
      raw_hex: rawHex.slice(0, 16),
    }],
  })[0].firstMismatchOffset, 8);
});

test('decodeBattleControl preserves raw bytes and exposes the chapter/battle id', () => {
  assert.deepEqual(decodeBattleControl(Uint8Array.from([0x80, 0x28, 1, 2, 3, 4, 5, 6])), {
    rawHex: '8028010203040506',
    chapterBattleId: 0x28,
  });
});

test('decodeMapRuntime exposes dimensions and their loader-derived grid sizes', () => {
  assert.deepEqual(decodeMapRuntime(Uint8Array.from([36, 44, 9, 22])), {
    rawHex: '242c0916',
    width: 36,
    height: 44,
    gridWidth: 9,
    gridHeight: 22,
    derivationConsistent: true,
  });
});

test('decodeChapterScriptProbe exposes the live script cursor and chapter operand', () => {
  const bytes = Uint8Array.from([0x34, 0x12, 0x59, 0x08, 0x2a, 0x28, 0x01, 0x00, 0x03, 0, 0, 0]);
  assert.deepEqual(decodeChapterScriptProbe(bytes), {
    rawHex: '341259082a28010003000000',
    scriptPointer: 0x08591234,
    scriptPointerHex: '0x08591234',
    opcodeBytesHex: '2a280100',
    opcode: 0x2a,
    chapterBattleId: 40,
    hitCount: 3,
    pointerInRom: true,
  });
});

test('alternate probe decoder exposes selector, dispatch and chapter-state evidence', () => {
  const bytes = new Uint8Array(32);
  const view = new DataView(bytes.buffer);
  view.setUint32(0, 0x52504341, true);
  view.setUint32(4, 8, true);
  view.setUint32(8, 39, true);
  view.setUint32(12, 0x08031281, true);
  view.setUint32(16, 45, true);
  view.setUint32(20, 0x0803142E, true);
  bytes.set([0, 0, 0, 0], 24);
  assert.deepEqual(decodeAlternateChapterProbe(bytes, 0), {
    rawHex: Buffer.from(bytes).toString('hex'),
    magicValid: true,
    selectorHitCount: 8,
    scenarioId: 39,
    selectedScriptStart: 0x08031281,
    opcodeHitCount: 45,
    lastOpcodeCursor: 0x0803142E,
    lastOpcodeCursorHex: '0x0803142E',
    opcodeBytesHex: '00000000',
    opcode: 0,
    chapterState: 0,
  });
});

test('runtime wiring reads ROM bytes and verifies fresh alternate-script termination', async () => {
  const scratch = new Uint8Array(32);
  const view = new DataView(scratch.buffer);
  view.setUint32(0, 0x52504341, true);
  view.setUint32(4, 1, true);
  view.setUint32(8, 39, true);
  view.setUint32(12, 0x08031281, true);
  view.setUint32(16, 25, true);
  view.setUint32(20, 0x0803142E, true);
  const memory = new Map([
    ['33816496:32', Array.from(scratch)],
    ['33755626:1', [0]],
    ['134419502:4', [0, 0, 0, 0]],
  ]);
  const page = { evaluate: async (_callback, { address, length }) => memory.get(`${address}:${length}`) };
  const result = await captureAlternateChapterEvidence(page, {
    selectorHitCount: 0,
    opcodeHitCount: 0,
    chapterState: 0,
  });
  assert.equal(result.romOpcodeBytesHex, '00000000');
  assert.equal(result.evidence.verified, true);
  assert.equal(result.evidence.reason, 'alternate-script-terminated');
});

test('runtime wiring accepts a configured codec-authored semantic script', async () => {
  const scratch = new Uint8Array(32);
  const view = new DataView(scratch.buffer);
  view.setUint32(0, 0x52504341, true);
  view.setUint32(4, 1, true);
  view.setUint32(8, 39, true);
  view.setUint32(12, 0x0809E800, true);
  view.setUint32(16, 2, true);
  view.setUint32(20, 0x0809E803, true);
  const memory = new Map([
    ['33816496:32', Array.from(scratch)],
    ['33755626:1', [40]],
    [`${0x0809E803}:4`, [0, 0, 0, 0]],
  ]);
  const page = { evaluate: async (_callback, { address, length }) => memory.get(`${address}:${length}`) };
  const result = await captureAlternateChapterEvidence(page, {
    selectorHitCount: 0,
    opcodeHitCount: 0,
    chapterState: 39,
  }, {
    expectedScenarioId: 39,
    expectedScriptStart: 0x0809E800,
    expectedScriptEnd: 0x0809E803,
    evidenceKind: 'semantic',
  });
  assert.equal(result.romOpcodeBytesHex, '00000000');
  assert.equal(result.evidence.verified, true);
  assert.equal(result.evidence.reason, 'semantic-script-terminated');
});

test('alternate chapter completion stops before later input overwrites terminal evidence', () => {
  assert.equal(shouldStopForAlternateChapter({ evidence: { verified: true } }), true);
  assert.equal(shouldStopForAlternateChapter({ evidence: { verified: false } }), false);
  assert.equal(shouldStopForAlternateChapter(null), false);
});

test('map resource dump captures every loader destination at one boundary', () => {
  assert.deepEqual(mapResourceDumpSpecs(), [
    { name: 'ewram.bin', address: 0x02000000, length: 0x40000 },
    { name: 'palette-ram.bin', address: 0x05000000, length: 0x400 },
    { name: 'vram.bin', address: 0x06000000, length: 0x18000 },
  ]);
});

test('alternate chapter evidence requires fresh selector and dispatch hits through opcode 00', () => {
  const baseline = { selectorHitCount: 7, opcodeHitCount: 20, chapterState: 0 };
  const current = {
    magicValid: true,
    selectorHitCount: 8,
    scenarioId: 39,
    selectedScriptStart: 0x08031281,
    opcodeHitCount: 45,
    lastOpcodeCursor: 0x0803142E,
    opcode: 0,
    opcodeBytesHex: '00000000',
    chapterState: 0,
  };
  assert.deepEqual(evaluateAlternateChapterEvidence({
    baseline, current,
    expectedScenarioId: 39,
    expectedScriptStart: 0x08031281,
    expectedScriptEnd: 0x0803142E,
    romOpcodeBytesHex: '00000000',
  }), {
    verified: true,
    reason: 'alternate-script-terminated',
    checks: {
      magicValid: true,
      freshSelectorHit: true,
      scenarioMatches: true,
      selectedScriptMatches: true,
      freshOpcodeHit: true,
      cursorInScript: true,
      opcodeMatchesRom: true,
      stateChangedOrTerminated: true,
    },
  });
});

test('alternate chapter evidence rejects stale, wrong-table and out-of-range captures', () => {
  const baseline = { selectorHitCount: 7, opcodeHitCount: 20, chapterState: 0 };
  const current = {
    magicValid: true,
    selectorHitCount: 7,
    scenarioId: 38,
    selectedScriptStart: 0x08031020,
    opcodeHitCount: 20,
    lastOpcodeCursor: 0x080317A9,
    opcode: 0,
    opcodeBytesHex: '01020304',
    chapterState: 0,
  };
  const result = evaluateAlternateChapterEvidence({
    baseline, current,
    expectedScenarioId: 39,
    expectedScriptStart: 0x08031281,
    expectedScriptEnd: 0x0803142E,
    romOpcodeBytesHex: '00000000',
  });
  assert.equal(result.verified, false);
  assert.deepEqual(result.checks, {
    magicValid: true,
    freshSelectorHit: false,
    scenarioMatches: false,
    selectedScriptMatches: false,
    freshOpcodeHit: false,
    cursorInScript: false,
    opcodeMatchesRom: false,
    stateChangedOrTerminated: true,
  });
});

test('classifyScreenMetrics recognizes the character panel without OCR', () => {
  assert.equal(classifyScreenMetrics({ grayRatio: 0.01, paleRatio: 0.12, greenRatio: 0.26, darkRatio: 0.01, edgeRatio: 0.126 }), 'character-panel');
  assert.equal(classifyScreenMetrics({ grayRatio: 0, paleRatio: 0.46, greenRatio: 0.291, darkRatio: 0.05, edgeRatio: 0.09 }), 'prebattle-menu');
  assert.equal(classifyScreenMetrics({ grayRatio: 0, paleRatio: 0.61, greenRatio: 0.4, darkRatio: 0.01, edgeRatio: 0.344 }), 'battle-map');
  assert.equal(classifyScreenMetrics({ grayRatio: 0, paleRatio: 0, greenRatio: 0, darkRatio: 0.82, edgeRatio: 0.01 }), 'other');
  assert.notEqual(classifyScreenMetrics({ grayRatio: 0.01, paleRatio: 0.12, greenRatio: 0.26, darkRatio: 0.01, edgeRatio: 0.126 }), 'battle-map');
});

test('buildNavigationPlan can skip the implicit new-game confirm for loaded states', () => {
  const plan = buildNavigationPlan({ startCount: 0, advanceCount: 0, skipNewGame: true });
  assert.deepEqual(plan, []);
});

test('strict battle arrival rejects preloaded formation during dialogue', () => {
  const match = { best: { missing: 0 }, unique: true };
  const battleControl = { chapterBattleId: 40 };
  const mapRuntime = { width: 36, height: 44, derivationConsistent: true };
  const dialogue = evaluateBattleArrival({ match, battleControl, mapRuntime, screenState: 'other' });
  assert.equal(dialogue.arrived, false);
  assert.equal(dialogue.checks.battleMapVisible, false);
  const battle = evaluateBattleArrival({ match, battleControl, mapRuntime, screenState: 'battle-map' });
  assert.equal(battle.arrived, true);
  assert.equal(battle.reason, 'strict-battle-arrival');
});

test('strict battle arrival requires every independent evidence factor', () => {
  const result = evaluateBattleArrival({
    match: { best: { missing: 0 }, unique: false },
    battleControl: { chapterBattleId: 0 },
    mapRuntime: { width: 0, height: 0, derivationConsistent: true },
    screenState: 'battle-map',
  });
  assert.equal(result.arrived, false);
  assert.deepEqual(result.checks, {
    uniqueCompleteFormation: false,
    battleIdPresent: false,
    mapLoaded: false,
    battleMapVisible: true,
  });
});

test('tailTransitionDecision waits through transition frames before menu input', () => {
  assert.equal(tailTransitionDecision('character-panel'), 'retry-back');
  assert.equal(tailTransitionDecision('other'), 'wait');
  assert.equal(tailTransitionDecision('prebattle-menu'), 'ready');
});

test('shouldRetryBack gives an accepted back press a transition grace period', () => {
  assert.equal(shouldRetryBack('retry-back', 1), false);
  assert.equal(shouldRetryBack('retry-back', 3), false);
  assert.equal(shouldRetryBack('retry-back', 4), true);
  assert.equal(shouldRetryBack('wait', 4), false);
});

test('buildNavigationPlan expands bounded phases with sampled key hold time', () => {
  assert.deepEqual(buildNavigationPlan({ startCount: 2, advanceCount: 3, keyHoldMs: 125 }), [
    { phase: 'boot', key: 'Enter', delayMs: 3000, holdMs: 125 },
    { phase: 'boot', key: 'Enter', delayMs: 3000, holdMs: 125 },
    { phase: 'new-game', key: 'KeyZ', delayMs: 1500, holdMs: 125 },
    { phase: 'story', key: 'KeyZ', delayMs: 3000, holdMs: 125 },
    { phase: 'story', key: 'KeyZ', delayMs: 3000, holdMs: 125 },
    { phase: 'story', key: 'KeyZ', delayMs: 3000, holdMs: 125 },
  ]);
});

test('buildSettlePlan schedules read-only polls without key actions', () => {
  assert.deepEqual(buildSettlePlan({ count: 3, delayMs: 750 }), [
    { phase: 'settle', poll: 1, delayMs: 750 },
    { phase: 'settle', poll: 2, delayMs: 750 },
    { phase: 'settle', poll: 3, delayMs: 750 },
  ]);
});

test('buildSettlePlan can schedule bounded recovery confirms', () => {
  assert.deepEqual(buildSettlePlan({ count: 5, delayMs: 500, confirmEvery: 2, keyHoldMs: 150 }), [
    { phase: 'settle', poll: 1, delayMs: 500 },
    { phase: 'settle', poll: 2, delayMs: 500, key: 'KeyZ', holdMs: 150 },
    { phase: 'settle', poll: 3, delayMs: 500 },
    { phase: 'settle', poll: 4, delayMs: 500, key: 'KeyZ', holdMs: 150 },
    { phase: 'settle', poll: 5, delayMs: 500 },
  ]);
});

test('buildNavigationPlan appends a configurable menu-tail key sequence', () => {
  const plan = buildNavigationPlan({
    startCount: 0,
    advanceCount: 0,
    tailKeys: ['KeyX', 'ArrowRight', 'KeyZ'],
    tailDelayMs: 600,
    keyHoldMs: 125,
  });
  assert.deepEqual(plan.slice(1), [
    { phase: 'tail', key: 'KeyX', delayMs: 600, holdMs: 125 },
    { phase: 'tail', key: 'ArrowRight', delayMs: 600, holdMs: 125 },
    { phase: 'tail', key: 'KeyZ', delayMs: 600, holdMs: 125 },
  ]);
});

test('buildNavigationPlan can repeat a verified tail interaction sequence', () => {
  const plan = buildNavigationPlan({
    startCount: 0, advanceCount: 0, skipNewGame: true,
    tailKeys: ['ArrowDown', 'KeyZ'], tailRepeat: 3,
    tailDelayMs: 500, keyHoldMs: 100,
  });
  assert.deepEqual(plan.map(action => action.key), [
    'ArrowDown', 'KeyZ', 'ArrowDown', 'KeyZ', 'ArrowDown', 'KeyZ',
  ]);
});

test('buildArtifactPaths keeps every phase artifact under configured paths', () => {
  const paths = buildArtifactPaths('/tmp/probe.json', '/tmp/final.png');
  assert.equal(paths.resultPath, '/tmp/probe.json');
  assert.equal(paths.finalScreenshotPath, '/tmp/final.png');
  assert.equal(paths.phaseScreenshot('story'), '/tmp/final-story.png');
});

test('buildProbeResult preserves stage snapshots and explicit failure reason', () => {
  const result = buildProbeResult({
    outcome: 'not-found',
    reason: 'plan-exhausted',
    stages: [{ phase: 'story', nonzeroBytes: 0 }],
    final: { step: 41 },
  });
  assert.equal(result.schemaVersion, 1);
  assert.equal(result.outcome, 'not-found');
  assert.equal(result.reason, 'plan-exhausted');
  assert.deepEqual(result.stages, [{ phase: 'story', nonzeroBytes: 0 }]);
  assert.deepEqual(result.final, { step: 41 });
});

test('classifyMemorySnapshot distinguishes empty, stable and changed unit arrays', () => {
  const zero = Uint8Array.from([0, 0, 0, 0]);
  const active = Uint8Array.from([0, 7, 0, 0]);
  assert.deepEqual(classifyMemorySnapshot(null, zero), { state: 'empty', changedBytes: 0 });
  assert.deepEqual(classifyMemorySnapshot(active, active), { state: 'stable', changedBytes: 0 });
  assert.deepEqual(classifyMemorySnapshot(zero, active), { state: 'changed', changedBytes: 1 });
});

test('matchFormationPositions finds a unique group/variant by active WRAM coordinates', () => {
  const entries = [
    { group_id: 0, variant_id: 0, record_id: 0, active: true, x: 1, y: 2 },
    { group_id: 0, variant_id: 0, record_id: 1, active: true, x: 3, y: 4 },
    { group_id: 1, variant_id: 2, record_id: 0, active: true, x: 10, y: 9 },
    { group_id: 1, variant_id: 2, record_id: 1, active: true, x: 10, y: 6 },
    { group_id: 2, variant_id: 0, record_id: 0, active: false, x: 10, y: 9 },
  ];
  const result = matchFormationPositions(entries, [{ x: 10, y: 9 }, { x: 10, y: 6 }]);
  assert.equal(result.best.groupId, 1);
  assert.equal(result.best.variantId, 2);
  assert.equal(result.best.matched, 2);
  assert.equal(result.best.missing, 0);
  assert.equal(result.unique, true);
});

test('matchFormationPositions reports ambiguity instead of guessing', () => {
  const entries = [
    { group_id: 0, variant_id: 0, active: true, x: 5, y: 6 },
    { group_id: 1, variant_id: 0, active: true, x: 5, y: 6 },
  ];
  const result = matchFormationPositions(entries, [{ x: 5, y: 6 }]);
  assert.equal(result.unique, false);
  assert.equal(result.candidates.length, 2);
});
