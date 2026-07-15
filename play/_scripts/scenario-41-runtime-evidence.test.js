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

function validSample() {
  return {
    baseline: {
      player: call(0, 0),
      current: call(0, 0, { eventCode: 2 }),
    },
    final: {
      player: call(1, 4),
      current: call(1, 5, { eventCode: 2 }),
    },
    battleId: 41,
    mapLoaded: true,
    screenState: 'battle-map',
    controlledCharacterId: 1,
    controlledSlot: 1,
    explicitInputs: ['KeyZ'],
    automaticInputs: [],
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
  };
  sample.final = {
    player: call(0, 0),
    current: call(0, 1, { eventCode: 2 }),
  };
  assert.equal(evaluatePlayerControlEvidence(sample).verified, true);
});

test('rejects stale, reversed and automatic-input samples', () => {
  const stale = validSample();
  stale.final.player = { ...stale.baseline.player };
  assert.equal(evaluatePlayerControlEvidence(stale).reason, 'player-observer-not-fresh');

  const reversed = validSample();
  reversed.final.current.sequence = 3;
  assert.equal(evaluatePlayerControlEvidence(reversed).reason, 'observer-order-invalid');

  const automatic = validSample();
  automatic.automaticInputs = ['KeyZ'];
  assert.equal(evaluatePlayerControlEvidence(automatic).reason, 'unlisted-input-used');

  const automaticOnly = validSample();
  automaticOnly.explicitInputs = [];
  automaticOnly.automaticInputs = ['KeyZ'];
  assert.equal(evaluatePlayerControlEvidence(automaticOnly).reason, 'unlisted-input-used');
});

test('rejects wrong event codes and inconsistent controlled unit evidence', () => {
  const wrongEvent = validSample();
  wrongEvent.final.current.eventCode = 1;
  assert.equal(evaluatePlayerControlEvidence(wrongEvent).reason, 'observer-event-code-invalid');

  const wrongCharacter = validSample();
  wrongCharacter.controlledCharacterId = 7;
  assert.equal(evaluatePlayerControlEvidence(wrongCharacter).reason, 'controlled-unit-inconsistent');
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
