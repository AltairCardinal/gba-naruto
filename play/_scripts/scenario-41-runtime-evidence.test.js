'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');

const {
  decodePublishedCall,
  decodeMovedoneRecord,
  evaluateMovedoneEvidence,
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

function nativeExpectedInputPlan() {
  return Object.freeze([1, 2, 3].map(step => Object.freeze({
    phase: 'active-current',
    step,
    logicalKey: 'KeyZ',
    gbaButton: 'A',
    downFrame: 5,
    upFrame: 13,
    holdFrames: 8,
    captureFrame: 80,
  })));
}

function completedNativeInputEvent(step, overrides = {}) {
  return {
    phase: 'active-current',
    step,
    logicalKey: 'KeyZ',
    gbaButton: 'A',
    downFrame: 5,
    upFrame: 13,
    holdFrames: 8,
    captureFrame: 80,
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

function validNativeSample() {
  return {
    ...validSample(),
    expectedInputPlan: nativeExpectedInputPlan(),
    inputEvents: [1, 2, 3].map(step => completedNativeInputEvent(step)),
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

test('accepts three ordered native frame-timed A events from independent guarded runs', () => {
  const result = evaluatePlayerControlEvidence(validNativeSample());
  assert.equal(result.verified, true);
  assert.equal(result.reason, 'player-control-verified');
});

test('rejects incomplete or invalid native frame timing plans', () => {
  for (const field of ['downFrame', 'upFrame', 'holdFrames', 'captureFrame']) {
    const sample = validNativeSample();
    const item = { ...sample.expectedInputPlan[0] };
    delete item[field];
    sample.expectedInputPlan = Object.freeze([
      Object.freeze(item),
      ...sample.expectedInputPlan.slice(1),
    ]);
    assert.equal(
      evaluatePlayerControlEvidence(sample).reason,
      'expected-input-plan-invalid',
      `missing ${field} must fail closed`,
    );
  }

  for (const [field, value] of [
    ['downFrame', 5.5],
    ['upFrame', 13.5],
    ['holdFrames', 8.5],
    ['captureFrame', 80.5],
    ['downFrame', 0],
    ['upFrame', 5],
    ['holdFrames', 7],
    ['captureFrame', 13],
  ]) {
    const sample = validNativeSample();
    sample.expectedInputPlan = Object.freeze([
      Object.freeze({ ...sample.expectedInputPlan[0], [field]: value }),
      ...sample.expectedInputPlan.slice(1),
    ]);
    assert.equal(
      evaluatePlayerControlEvidence(sample).reason,
      'expected-input-plan-invalid',
      `${field}=${value} must fail closed`,
    );
  }
});

test('rejects hybrid items and legacy/native timing mode mixtures', () => {
  const hybrid = validNativeSample();
  hybrid.expectedInputPlan = Object.freeze([
    Object.freeze({ ...hybrid.expectedInputPlan[0], holdMs: 125 }),
    ...hybrid.expectedInputPlan.slice(1),
  ]);
  assert.equal(evaluatePlayerControlEvidence(hybrid).reason, 'expected-input-plan-invalid');

  const mixed = validNativeSample();
  mixed.expectedInputPlan = Object.freeze([
    expectedInputPlan()[0],
    ...mixed.expectedInputPlan.slice(1),
  ]);
  assert.equal(evaluatePlayerControlEvidence(mixed).reason, 'expected-input-plan-invalid');
});

test('requires native events to match their plan timing mode and every timing field', () => {
  for (const [field, value] of [
    ['downFrame', 6],
    ['upFrame', 14],
    ['holdFrames', 7],
    ['captureFrame', 81],
    ['holdMs', 125],
  ]) {
    const sample = validNativeSample();
    sample.inputEvents[0] = completedNativeInputEvent(1, { [field]: value });
    assert.equal(
      evaluatePlayerControlEvidence(sample).reason,
      'input-plan-mismatch',
      `${field} mismatch must fail closed`,
    );
  }

  for (const field of ['downFrame', 'upFrame', 'holdFrames', 'captureFrame']) {
    const sample = validNativeSample();
    const event = completedNativeInputEvent(1);
    delete event[field];
    sample.inputEvents[0] = event;
    assert.equal(
      evaluatePlayerControlEvidence(sample).reason,
      'input-plan-mismatch',
      `event missing ${field} must fail closed`,
    );
  }

  const nativePlanWithLegacyEvent = validNativeSample();
  nativePlanWithLegacyEvent.inputEvents[0] = completedInputEvent({
    phase: 'active-current', step: 1,
  });
  assert.equal(
    evaluatePlayerControlEvidence(nativePlanWithLegacyEvent).reason,
    'input-plan-mismatch',
  );

  const legacyPlanWithNativeEvent = validSample();
  legacyPlanWithNativeEvent.inputEvents = [completedNativeInputEvent(1, { phase: 'tail' })];
  assert.equal(
    evaluatePlayerControlEvidence(legacyPlanWithNativeEvent).reason,
    'input-plan-mismatch',
  );
});

test('rejects extra, missing and out-of-order native events', () => {
  const extra = validNativeSample();
  extra.inputEvents.push(completedNativeInputEvent(4));
  assert.equal(evaluatePlayerControlEvidence(extra).reason, 'input-plan-mismatch');

  const missing = validNativeSample();
  missing.inputEvents.pop();
  assert.equal(evaluatePlayerControlEvidence(missing).reason, 'input-plan-mismatch');

  const outOfOrder = validNativeSample();
  [outOfOrder.inputEvents[0], outOfOrder.inputEvents[1]] = [
    outOfOrder.inputEvents[1],
    outOfOrder.inputEvents[0],
  ];
  assert.equal(evaluatePlayerControlEvidence(outOfOrder).reason, 'input-plan-mismatch');
});

test('keeps explicit classification and completed down/up gates for native events', () => {
  const automatic = validNativeSample();
  automatic.inputEvents[1] = completedNativeInputEvent(2, { classification: 'automatic' });
  assert.equal(evaluatePlayerControlEvidence(automatic).reason, 'unlisted-input-used');

  const incomplete = validNativeSample();
  incomplete.inputEvents[1] = completedNativeInputEvent(2, { upCompleted: false });
  assert.equal(evaluatePlayerControlEvidence(incomplete).reason, 'input-incomplete');
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

const MOVEDONE_MAGIC_1 = 0x31444F4D;

function movedoneCall(hitCount, sequence, overrides = {}) {
  return {
    magicValid: true,
    hitCount,
    sequence,
    eventCode: 1,
    sourceHook: '0x0807443C',
    snapshot: {
      objectAddress: 0x0202680C,
      objectSlot: 1,
      objectRecordPointer: 0x02024294,
      recordAddress: 0x02024294,
      characterId: 1,
      affiliation: 0,
      active: true,
      x: 4,
      y: 10,
      initialX: 4,
      initialY: 10,
      rawC0C3: '80010000',
      rawC4C7: '040a0004',
      rawC8CB: '0a112233',
      rawCCCF: '44556677',
    },
    ...overrides,
  };
}

function actingUnit(overrides = {}) {
  return {
    objectAddress: 0x0202680C,
    objectSlot: 1,
    objectRecordPointer: 0x02024294,
    slot: 1,
    recordAddress: 0x02024294,
    characterId: 1,
    affiliation: 0,
    active: true,
    x: 4,
    y: 10,
    initialX: 4,
    initialY: 10,
    actionStateRaw: '44556677',
    ...overrides,
  };
}

function validMovedoneSample() {
  return {
    scenario: 41,
    battleId: 41,
    map: { width: 36, height: 44, gridX: 9, gridY: 22 },
    mapLoaded: true,
    screenState: 'battle-map',
    baseline: {
      sequenceBoundary: 12,
      events: [movedoneCall(4, 10), movedoneCall(7, 12, {
        eventCode: 2, sourceHook: '0x08074918',
      })],
    },
    final: {
      events: [movedoneCall(5, 13), movedoneCall(7, 12, {
        eventCode: 2, sourceHook: '0x08074918',
      })],
    },
    controlledUnit: {
      slot: 1, recordAddress: 0x02024294, characterId: 1, affiliation: 0,
    },
    actingUnitBefore: actingUnit(),
    actingUnitAfter: actingUnit({ x: 5, actionStateRaw: '45556677' }),
    stateBefore: { address: '0x0200A880', raw: '00000100' },
    stateAfter: { address: '0x0200A880', raw: '00000100' },
    expectedInputPlan: Object.freeze([Object.freeze({
      phase: 'movedone-diagnostic', step: 1, logicalKey: 'KeyZ', gbaButton: 'A', holdMs: 125,
    })]),
    explicitInputs: [completedInputEvent({ phase: 'movedone-diagnostic' })],
    automaticInputs: [],
    automaticGameAction: false,
  };
}

test('decodes MOVEDONE metadata and hook-time current-object/unit snapshot', () => {
  assert.equal(typeof decodeMovedoneRecord, 'function');
  const bytes = Buffer.alloc(52);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  [MOVEDONE_MAGIC_1, 3, 8, 1, 0x0807443C, 0x01000001, 0x02024294,
    0x02024294, 0x0D0E0101, 0x00000180, 0x04000A04, 0x3322110A, 0x77665544]
    .forEach((value, index) => view.setUint32(index * 4, value, true));
  assert.deepEqual(decodeMovedoneRecord(bytes, MOVEDONE_MAGIC_1), {
    rawHex: bytes.toString('hex'),
    magicValid: true,
    hitCount: 3,
    sequence: 8,
    eventCode: 1,
    sourceHook: '0x0807443C',
    snapshot: {
      objectAddress: 0x0202680C,
      objectSlot: 1,
      objectRecordPointer: 0x02024294,
      recordAddress: 0x02024294,
      characterId: 1,
      affiliation: 0,
      active: true,
      x: 4,
      y: 10,
      initialX: 4,
      initialY: 10,
      rawC0C3: '80010000',
      rawC4C7: '040a0004',
      rawC8CB: '0a112233',
      rawCCCF: '44556677',
    },
  });
  assert.throws(() => decodeMovedoneRecord(bytes.subarray(0, 48), MOVEDONE_MAGIC_1), /52 bytes/);
});

test('MOVEDONE accepts one fresh allowed source bound to the same acting unit transition', () => {
  assert.equal(typeof evaluateMovedoneEvidence, 'function');
  const result = evaluateMovedoneEvidence(validMovedoneSample());
  assert.equal(result.verified, true);
  assert.equal(result.reason, 'movedone-verified');
  assert.equal(result.automaticGameAction, false);
});

test('MOVEDONE rejects stale, wrong-source, dual-source and unordered events', () => {
  const stale = validMovedoneSample();
  stale.final.events[0] = { ...stale.baseline.events[0] };
  assert.equal(evaluateMovedoneEvidence(stale).reason, 'movedone-event-count-invalid');

  const wrongSource = validMovedoneSample();
  wrongSource.final.events[0].sourceHook = '0x08074918';
  assert.equal(evaluateMovedoneEvidence(wrongSource).reason, 'movedone-source-invalid');

  const both = validMovedoneSample();
  both.final.events[1] = movedoneCall(8, 14, { eventCode: 2, sourceHook: '0x08074918' });
  assert.equal(evaluateMovedoneEvidence(both).reason, 'movedone-event-count-invalid');

  const unordered = validMovedoneSample();
  unordered.final.events[0].sequence = 12;
  assert.equal(evaluateMovedoneEvidence(unordered).reason, 'movedone-event-count-invalid');
});

test('MOVEDONE binds hook snapshot and before/after to one slot pointer and record identity', () => {
  for (const [mutation, reason] of [
    [sample => { sample.final.events[0].snapshot.objectSlot = 2; }, 'movedone-site-schema-invalid'],
    [sample => { sample.final.events[0].snapshot.objectRecordPointer = 0x02024468; }, 'movedone-site-schema-invalid'],
    [sample => { sample.final.events[0].snapshot.recordAddress = 0x02024468; }, 'movedone-site-schema-invalid'],
    [sample => { sample.actingUnitAfter.slot = 2; }, 'acting-unit-identity-mismatch'],
    [sample => { sample.actingUnitAfter.characterId = 30; }, 'acting-unit-identity-mismatch'],
    [sample => { sample.actingUnitAfter.affiliation = 1; }, 'acting-unit-identity-mismatch'],
    [sample => { sample.actingUnitAfter.recordAddress = 0x02024468; }, 'acting-unit-identity-mismatch'],
    [sample => { sample.actingUnitBefore.objectRecordPointer = 0x02024468; }, 'acting-unit-identity-mismatch'],
    [sample => { sample.actingUnitAfter.objectRecordPointer = 0x02024468; }, 'acting-unit-identity-mismatch'],
    [sample => { sample.final.events[0].snapshot.x = 3; }, 'movedone-site-schema-invalid'],
    [sample => { sample.final.events[0].snapshot.rawCCCF = '00000000'; }, 'acting-unit-identity-mismatch'],
    [sample => { sample.final.events[0].snapshot.rawC4C7 = '00000000'; }, 'movedone-site-schema-invalid'],
  ]) {
    const sample = validMovedoneSample();
    mutation(sample);
    assert.equal(evaluateMovedoneEvidence(sample).reason, reason);
  }
});

test('MOVEDONE reports a valid non-controlled diagnostic without accepting the player turn', () => {
  const sample = validMovedoneSample();
  sample.controlledUnit = {
    slot: 2, recordAddress: 0x02024468, characterId: 30, affiliation: 1,
  };
  const result = evaluateMovedoneEvidence(sample);
  assert.equal(result.diagnosticVerified, true);
  assert.equal(result.verified, false);
  assert.equal(result.checks.actingUnitControlled, false);
  assert.equal(result.classification, 'non-controlled');
  assert.equal(result.reason, 'non-controlled');
});

test('MOVEDONE requires coordinate change plus action or round transition', () => {
  const unchangedCoordinate = validMovedoneSample();
  unchangedCoordinate.actingUnitAfter.x = 4;
  assert.equal(evaluateMovedoneEvidence(unchangedCoordinate).reason, 'coordinates-unchanged');

  const unchangedState = validMovedoneSample();
  unchangedState.actingUnitAfter.actionStateRaw = unchangedState.actingUnitBefore.actionStateRaw;
  assert.equal(evaluateMovedoneEvidence(unchangedState).reason, 'action-round-state-unchanged');

  const roundChanged = validMovedoneSample();
  roundChanged.actingUnitAfter.actionStateRaw = roundChanged.actingUnitBefore.actionStateRaw;
  roundChanged.stateBefore = { address: '0x0200A880', raw: '00000100' };
  roundChanged.stateAfter = { address: '0x0200A880', raw: '00000200' };
  assert.equal(evaluateMovedoneEvidence(roundChanged).verified, true);
});

test('MOVEDONE requires complete uniquely paired sites in canonical source order', () => {
  for (const mutation of [
    sample => { sample.baseline.events.pop(); },
    sample => { sample.final.events.pop(); },
    sample => { sample.baseline.events[1] = { ...sample.baseline.events[0] }; },
    sample => { sample.final.events[1] = { ...sample.final.events[0] }; },
    sample => { sample.baseline.events.reverse(); },
    sample => { sample.final.events.reverse(); },
    sample => { sample.baseline.events[0].sourceHook = '0x08074918'; },
  ]) {
    const sample = validMovedoneSample();
    mutation(sample);
    assert.equal(evaluateMovedoneEvidence(sample).verified, false);
  }

  const crossSiteIndexTrap = validMovedoneSample();
  crossSiteIndexTrap.baseline.events.reverse();
  assert.equal(evaluateMovedoneEvidence(crossSiteIndexTrap).diagnosticVerified, false);
});

function assertMovedoneSiteSchemaInvalid(sample) {
  const result = evaluateMovedoneEvidence(sample);
  assert.equal(result.diagnosticVerified, false);
  assert.equal(result.verified, false);
  assert.equal(result.reason, 'movedone-site-schema-invalid');
  assert.equal(result.checks.movedoneSiteSchemaValid, false);
}

test('MOVEDONE requires every baseline and final site record field', () => {
  for (const boundary of ['baseline', 'final']) {
    for (const siteIndex of [0, 1]) {
      for (const field of ['magicValid', 'hitCount', 'sequence', 'snapshot']) {
        const sample = validMovedoneSample();
        delete sample[boundary].events[siteIndex][field];
        assertMovedoneSiteSchemaInvalid(sample);
      }
    }
  }
});

test('MOVEDONE requires the complete typed decoder snapshot at both sites', () => {
  const snapshotFields = [
    'objectAddress', 'objectSlot', 'objectRecordPointer', 'recordAddress',
    'characterId', 'affiliation', 'active', 'x', 'y', 'initialX', 'initialY',
    'rawC0C3', 'rawC4C7', 'rawC8CB', 'rawCCCF',
  ];
  for (const boundary of ['baseline', 'final']) {
    for (const siteIndex of [0, 1]) {
      for (const field of snapshotFields) {
        const sample = validMovedoneSample();
        delete sample[boundary].events[siteIndex].snapshot[field];
        assertMovedoneSiteSchemaInvalid(sample);
      }
    }
  }

  for (const mutation of [
    sample => { sample.baseline.events[1].magicValid = 1; },
    sample => { sample.final.events[1].hitCount = '7'; },
    sample => { sample.baseline.events[1].sequence = -1; },
    sample => { sample.final.events[1].snapshot.objectAddress = '0x0202680C'; },
    sample => { sample.baseline.events[1].snapshot.objectSlot = 1.5; },
    sample => { sample.final.events[1].snapshot.active = 1; },
    sample => { sample.baseline.events[1].snapshot.rawC0C3 = '8001000A'; },
    sample => { sample.final.events[1].snapshot.rawC4C7 = '00000000'; },
  ]) {
    const sample = validMovedoneSample();
    mutation(sample);
    assertMovedoneSiteSchemaInvalid(sample);
  }
});

test('MOVEDONE requires the companion magic and record identity to stay unchanged', () => {
  const wrongMagic = validMovedoneSample();
  wrongMagic.final.events[1].magicValid = false;
  assertMovedoneSiteSchemaInvalid(wrongMagic);

  const falseMagicOnNonzeroRecord = validMovedoneSample();
  falseMagicOnNonzeroRecord.baseline.events[1].magicValid = false;
  falseMagicOnNonzeroRecord.final.events[1].magicValid = false;
  assertMovedoneSiteSchemaInvalid(falseMagicOnNonzeroRecord);

  const changedIdentity = validMovedoneSample();
  Object.assign(changedIdentity.final.events[1].snapshot, {
    objectSlot: 2,
    objectRecordPointer: 0x02024468,
    recordAddress: 0x02024468,
    characterId: 30,
  });
  assertMovedoneSiteSchemaInvalid(changedIdentity);
});

test('MOVEDONE accepts a complete unchanged canonical zero companion record', () => {
  const sample = validMovedoneSample();
  const zeroSnapshot = {
    objectAddress: 0x0202680C,
    objectSlot: 0,
    objectRecordPointer: 0,
    recordAddress: 0,
    characterId: 0,
    affiliation: 0,
    active: false,
    x: 0,
    y: 0,
    initialX: 0,
    initialY: 0,
    rawC0C3: '00000000',
    rawC4C7: '00000000',
    rawC8CB: '00000000',
    rawCCCF: '00000000',
  };
  for (const boundary of ['baseline', 'final']) {
    sample[boundary].events[1] = movedoneCall(0, 0, {
      magicValid: false,
      eventCode: 2,
      sourceHook: '0x08074918',
      snapshot: { ...zeroSnapshot },
    });
  }
  assert.equal(evaluateMovedoneEvidence(sample).verified, true);
});

test('MOVEDONE rejects backward or inconsistent companion counters', () => {
  for (const mutation of [
    sample => { sample.final.events[1].hitCount = 6; },
    sample => { sample.final.events[1].sequence = 11; },
    sample => { sample.final.events[1].hitCount = 8; },
    sample => { sample.final.events[1].sequence = 13; },
  ]) {
    const sample = validMovedoneSample();
    mutation(sample);
    assertMovedoneSiteSchemaInvalid(sample);
  }
});

test('MOVEDONE accepts exactly one paired fresh site and rejects dual fresh sites', () => {
  assert.equal(evaluateMovedoneEvidence(validMovedoneSample()).verified, true);
  const dualFresh = validMovedoneSample();
  dualFresh.final.events[1] = movedoneCall(8, 14, {
    eventCode: 2, sourceHook: '0x08074918',
  });
  assert.equal(evaluateMovedoneEvidence(dualFresh).reason, 'movedone-event-count-invalid');
});

test('MOVEDONE validates exact lowercase round context and action-state words', () => {
  for (const mutation of [
    sample => { sample.stateBefore = { address: '0x0200A880', raw: 'x' }; },
    sample => { sample.stateAfter = { address: '0x0200A880', raw: '0000010' }; },
    sample => { sample.stateBefore.address = '0x0200A881'; },
    sample => { sample.stateAfter.raw = '0000010A'; },
    sample => { sample.stateBefore.raw = 0x100; },
    sample => { sample.actingUnitBefore.actionStateRaw = '4455667A'; },
    sample => { sample.actingUnitAfter.actionStateRaw = '4555667A'; },
  ]) {
    const sample = validMovedoneSample();
    mutation(sample);
    assert.equal(evaluateMovedoneEvidence(sample).verified, false);
  }
});

test('MOVEDONE requires explicit planned input, empty automatic driver inputs and recorded game action', () => {
  const automaticDriver = validMovedoneSample();
  automaticDriver.automaticInputs = ['KeyZ'];
  assert.equal(evaluateMovedoneEvidence(automaticDriver).reason, 'automatic-driver-input-used');

  const mismatch = validMovedoneSample();
  mismatch.explicitInputs[0].gbaButton = 'B';
  assert.equal(evaluateMovedoneEvidence(mismatch).reason, 'input-plan-mismatch');

  const missingGameClassification = validMovedoneSample();
  delete missingGameClassification.automaticGameAction;
  assert.equal(evaluateMovedoneEvidence(missingGameClassification).reason, 'automatic-game-action-invalid');

  const automaticGame = validMovedoneSample();
  automaticGame.automaticGameAction = true;
  const result = evaluateMovedoneEvidence(automaticGame);
  assert.equal(result.diagnosticVerified, true);
  assert.equal(result.verified, false);
  assert.equal(result.classification, 'automatic-game-action');
  assert.equal(result.reason, 'automatic-game-action');
  assert.equal(result.automaticGameAction, true);
});

test('MOVEDONE rejects malformed data and wrong battle/map context without throwing', () => {
  assert.equal(evaluateMovedoneEvidence({}).verified, false);
  const wrongScenario = validMovedoneSample();
  wrongScenario.scenario = 40;
  assert.equal(evaluateMovedoneEvidence(wrongScenario).reason, 'scenario-invalid');

  const badPointer = validMovedoneSample();
  badPointer.final.events[0].snapshot.objectRecordPointer = 0x08000000;
  assert.equal(evaluateMovedoneEvidence(badPointer).verified, false);

  const unloaded = validMovedoneSample();
  unloaded.mapLoaded = false;
  assert.equal(evaluateMovedoneEvidence(unloaded).reason, 'map-not-loaded');

  const wrongMap = validMovedoneSample();
  wrongMap.map.gridY = 21;
  assert.equal(evaluateMovedoneEvidence(wrongMap).reason, 'battle-map-context-invalid');
});
