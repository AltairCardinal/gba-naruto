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
  tailTransitionDecision,
  shouldRetryBack,
  decodeSaveRecord,
  compareSaveRecords,
} = require('./runtime-formation-probe-lib');
const { extractOccupiedUnitSummaries } = require('./runtime-formation-probe');

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

test('focusGameSurface restores keyboard focus to the emulator viewport', async () => {
  const clicks = [];
  await focusGameSurface({ mouse: { click: async (x, y) => clicks.push([x, y]) } });
  assert.deepEqual(clicks, [[480, 215]]);
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
