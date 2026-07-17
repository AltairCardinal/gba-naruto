'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');

const {
  decodePublishedCall,
  evaluatePlayerControlEvidence,
} = require('./scenario-41-runtime-evidence');

const PLAYER_MAGIC = 0x314F4350;
const CURRENT_MAGIC = 0x31554350;

function call(hitCount, sequence, overrides = {}) {
  return {
    magicValid: true,
    hitCount,
    argument0: 1,
    argument1: 0,
    argument2: 1,
    sequence,
    eventCode: overrides.eventCode ?? 1,
    ...overrides,
  };
}

function expectedInputPlan() {
  return Object.freeze([
    Object.freeze({
      phase: 'tail', step: 1, logicalKey: 'KeyZ', gbaButton: 'A', holdMs: 125,
    }),
  ]);
}

function completedInputEvent(overrides = {}) {
  return {
    phase: 'tail',
    step: 1,
    logicalKey: 'KeyZ',
    gbaButton: 'A',
    holdMs: 125,
    classification: 'explicit',
    downCompleted: true,
    upCompleted: true,
    ...overrides,
  };
}

function validSample() {
  return {
    baseline: {
      player: call(0, 0),
      current: call(0, 0, { eventCode: 2 }),
      sequenceBoundary: 0,
    },
    final: {
      player: call(1, 1, { argument0: 9, argument1: 0, argument2: 1, eventCode: 1 }),
      current: call(1, 2, { argument0: 1, eventCode: 3 }),
    },
    currentSourceHook: '0x08073BAC',
    battleId: 41,
    mapLoaded: true,
    screenState: 'battle-map',
    controlledSlot: 1,
    controlledCharacterId: 0x31,
    controlledAffiliation: 0,
    controlledUnitFromWram: true,
    expectedInputPlan: expectedInputPlan(),
    inputEvents: [completedInputEvent()],
  };
}

test('decodePublishedCall decodes the complete ordered observer record', () => {
  const bytes = Buffer.alloc(24);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  view.setUint32(0, PLAYER_MAGIC, true);
  view.setUint32(4, 3, true);
  view.setUint32(8, 9, true);
  view.setUint16(12, 7, true);
  view.setUint16(14, 1, true);
  view.setUint32(16, 0xFFFFFFFF, true);
  view.setUint32(20, 1, true);

  assert.deepEqual(decodePublishedCall(bytes, PLAYER_MAGIC), {
    rawHex: bytes.toString('hex'),
    magicValid: true,
    hitCount: 3,
    argument0: 9,
    argument1: 7,
    argument2: 1,
    sequence: 0xFFFFFFFF,
    eventCode: 1,
  });
  assert.throws(
    () => decodePublishedCall(bytes.subarray(0, 16), PLAYER_MAGIC),
    /published call record must be 24 bytes, got 16/,
  );
});

test('accepts only a fresh ordered player-control chain', () => {
  const result = evaluatePlayerControlEvidence(validSample());
  assert.equal(result.verified, true);
  assert.equal(result.reason, 'player-control-verified');
});

test('accepts uint32 hit-count and sequence wrap as bounded forward progress', () => {
  const sample = validSample();
  sample.baseline = {
    player: call(0xFFFFFFFF, 0xFFFFFFFF),
    current: call(0xFFFFFFFF, 0xFFFFFFFF, { eventCode: 2 }),
    sequenceBoundary: 0xFFFFFFFF,
  };
  sample.final = {
    player: call(0, 0, { argument0: 9, argument1: 0, argument2: 1, eventCode: 1 }),
    current: call(0, 1, { argument0: 1, eventCode: 3 }),
  };
  assert.equal(evaluatePlayerControlEvidence(sample).verified, true);
});

test('rejects stale, reversed and automatic-input samples', () => {
  const stale = validSample();
  stale.final.player = { ...stale.baseline.player };
  assert.equal(evaluatePlayerControlEvidence(stale).reason, 'player-observer-not-fresh');

  const reversed = validSample();
  reversed.final.player.sequence = 4;
  reversed.final.current.sequence = 3;
  assert.equal(evaluatePlayerControlEvidence(reversed).reason, 'observer-order-invalid');

  const automatic = validSample();
  automatic.inputEvents = [completedInputEvent({ classification: 'automatic' })];
  assert.equal(evaluatePlayerControlEvidence(automatic).reason, 'unlisted-input-used');
});

test('rejects a player hit captured before the shared baseline boundary', () => {
  const raced = validSample();
  raced.baseline = {
    player: call(0, 100),
    current: call(5, 200, { eventCode: 2 }),
    sequenceBoundary: 201,
  };
  raced.final = {
    player: call(1, 201),
    current: call(6, 202, { eventCode: 2 }),
  };
  assert.equal(
    evaluatePlayerControlEvidence(raced).reason,
    'player-observer-not-after-baseline-boundary',
  );
});

test('rejects wrong event codes and a current-unit slot mismatch', () => {
  const wrongEvent = validSample();
  wrongEvent.final.current.eventCode = 1;
  assert.equal(evaluatePlayerControlEvidence(wrongEvent).reason, 'observer-event-code-invalid');

  const wrongSlot = validSample();
  wrongSlot.final.current.argument0 = 2;
  assert.equal(evaluatePlayerControlEvidence(wrongSlot).reason, 'controlled-unit-inconsistent');

  for (const missing of ['controlledSlot', 'controlledCharacterId', 'controlledAffiliation']) {
    const sample = validSample();
    delete sample[missing];
    assert.equal(
      evaluatePlayerControlEvidence(sample).reason,
      'controlled-unit-diagnostic-invalid',
      `${missing} must fail closed`,
    );
  }

  for (const [field, value] of [
    ['controlledSlot', 21],
    ['controlledCharacterId', 0x100],
    ['controlledAffiliation', 2],
  ]) {
    const sample = validSample();
    sample[field] = value;
    assert.equal(
      evaluatePlayerControlEvidence(sample).reason,
      'controlled-unit-diagnostic-invalid',
      `${field} out of range must fail closed`,
    );
  }
});

test('rejects any deviation from the exact PCO1 selector protocol', () => {
  for (const [field, value] of [
    ['argument0', 1],
    ['argument1', 1],
    ['argument2', 0],
  ]) {
    const sample = validSample();
    sample.final.player[field] = value;
    assert.equal(
      evaluatePlayerControlEvidence(sample).reason,
      'player-selector-protocol-invalid',
      `${field} must match the PCO1 (9, 0, 1) protocol`,
    );
  }
});

test('binds each current-unit event to its exact source hook', () => {
  const wrongEvent2Source = validSample();
  wrongEvent2Source.final.current.eventCode = 2;
  assert.equal(
    evaluatePlayerControlEvidence(wrongEvent2Source).reason,
    'current-unit-source-invalid',
  );

  const event2 = validSample();
  event2.final.current.eventCode = 2;
  event2.currentSourceHook = '0x080739D8';
  assert.equal(evaluatePlayerControlEvidence(event2).verified, true);

  const wrongEvent3Source = validSample();
  wrongEvent3Source.currentSourceHook = '0x080739D8';
  assert.equal(
    evaluatePlayerControlEvidence(wrongEvent3Source).reason,
    'current-unit-source-invalid',
  );
});

test('binds the current argument to the WRAM slot and ignores unrelated entry registers', () => {
  const differentValidCharacter = validSample();
  differentValidCharacter.controlledCharacterId = 0x32;
  assert.equal(evaluatePlayerControlEvidence(differentValidCharacter).verified, true);

  const missingWramSource = validSample();
  delete missingWramSource.controlledUnitFromWram;
  assert.equal(
    evaluatePlayerControlEvidence(missingWramSource).reason,
    'controlled-unit-inconsistent',
  );

  const oldSlotSelectorSample = validSample();
  oldSlotSelectorSample.final.player.argument0 = oldSlotSelectorSample.controlledSlot;
  assert.equal(
    evaluatePlayerControlEvidence(oldSlotSelectorSample).reason,
    'player-selector-protocol-invalid',
  );

  const ignoredCurrentRegisters = validSample();
  ignoredCurrentRegisters.final.current.argument1 = 0xFFFF;
  ignoredCurrentRegisters.final.current.argument2 = 0xFFFF;
  assert.equal(evaluatePlayerControlEvidence(ignoredCurrentRegisters).verified, true);
});

test('requires one completed explicit A matching the immutable expected plan', () => {
  const releasedFailed = validSample();
  releasedFailed.inputEvents = [completedInputEvent({ upCompleted: false })];
  assert.equal(evaluatePlayerControlEvidence(releasedFailed).reason, 'input-incomplete');

  const arbitrary = validSample();
  arbitrary.inputEvents = [completedInputEvent({ logicalKey: 'KeyX', gbaButton: 'B' })];
  assert.equal(evaluatePlayerControlEvidence(arbitrary).reason, 'input-plan-mismatch');

  const extra = validSample();
  extra.inputEvents = [completedInputEvent(), completedInputEvent()];
  assert.equal(evaluatePlayerControlEvidence(extra).reason, 'input-plan-mismatch');

  assert.equal(evaluatePlayerControlEvidence(validSample()).verified, true);
});

test('rejects evidence outside scenario 41 foreground battle-map context', () => {
  const wrongBattle = validSample();
  wrongBattle.battleId = 40;
  assert.equal(evaluatePlayerControlEvidence(wrongBattle).reason, 'battle-id-invalid');

  const unloaded = validSample();
  unloaded.mapLoaded = false;
  assert.equal(evaluatePlayerControlEvidence(unloaded).reason, 'map-not-loaded');

  const background = validSample();
  background.screenState = 'other';
  assert.equal(evaluatePlayerControlEvidence(background).reason, 'battle-map-not-foreground');
});

test('decodes current-unit magic independently from player-control magic', () => {
  const bytes = Buffer.alloc(24);
  new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).setUint32(0, CURRENT_MAGIC, true);
  assert.equal(decodePublishedCall(bytes, CURRENT_MAGIC).magicValid, true);
  assert.equal(decodePublishedCall(bytes, PLAYER_MAGIC).magicValid, false);
});

test('rejects incomplete baseline evidence without throwing', () => {
  const sample = validSample();
  sample.baseline = {};
  const result = evaluatePlayerControlEvidence(sample);
  assert.equal(result.verified, false);
  assert.equal(result.reason, 'player-observer-not-fresh');
});
