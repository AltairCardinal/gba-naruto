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
  tailTransitionDecision,
  shouldRetryBack,
} = require('./runtime-formation-probe-lib');
const { extractRuntimePositions, focusGameSurface } = require('./runtime-formation-probe');

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

test('classifyScreenMetrics recognizes the character panel without OCR', () => {
  assert.equal(classifyScreenMetrics({ grayRatio: 0.344, paleRatio: 0.033, greenRatio: 0.18 }), 'character-panel');
  assert.equal(classifyScreenMetrics({ grayRatio: 0, paleRatio: 0.46, greenRatio: 0.291 }), 'prebattle-menu');
  assert.equal(classifyScreenMetrics({ grayRatio: 0, paleRatio: 0.08, greenRatio: 0.23 }), 'other');
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
