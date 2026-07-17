'use strict';

const PLAYER_CONTROL_EVENT = 1;
const CURRENT_UNIT_EVENT = 2;
const UINT32_HALF_RANGE = 0x80000000;

function decodePublishedCall(bytes, expectedMagic) {
  const data = Buffer.from(bytes);
  if (data.length !== 24) {
    throw new RangeError(`published call record must be 24 bytes, got ${data.length}`);
  }
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  return {
    rawHex: data.toString('hex'),
    magicValid: view.getUint32(0, true) === expectedMagic,
    hitCount: view.getUint32(4, true),
    argument0: view.getUint32(8, true),
    argument1: view.getUint16(12, true),
    argument2: view.getUint16(14, true),
    sequence: view.getUint32(16, true),
    eventCode: view.getUint32(20, true),
  };
}

function hexWord(bytes, offset) {
  return bytes.subarray(offset, offset + 4).toString('hex');
}

function decodeMovedoneRecord(bytes, expectedMagic) {
  const data = Buffer.from(bytes);
  if (data.length !== 52) {
    throw new RangeError(`MOVEDONE observer record must be 52 bytes, got ${data.length}`);
  }
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  const objectWord = view.getUint32(20, true);
  const recordWord00 = view.getUint32(32, true);
  const recordWordC0 = view.getUint32(36, true);
  const recordWordC4 = view.getUint32(40, true);
  const recordWordC8 = view.getUint32(44, true);
  return {
    rawHex: data.toString('hex'),
    magicValid: view.getUint32(0, true) === expectedMagic,
    hitCount: view.getUint32(4, true),
    sequence: view.getUint32(8, true),
    eventCode: view.getUint32(12, true),
    sourceHook: `0x${view.getUint32(16, true).toString(16).toUpperCase().padStart(8, '0')}`,
    snapshot: {
      objectAddress: 0x0202680C,
      objectSlot: objectWord >>> 24,
      objectRecordPointer: view.getUint32(24, true),
      recordAddress: view.getUint32(28, true),
      characterId: recordWord00 & 0xFF,
      affiliation: recordWordC0 & 1,
      active: (recordWordC0 & 0x80) !== 0,
      x: recordWordC4 & 0xFF,
      y: (recordWordC4 >>> 8) & 0xFF,
      initialX: (recordWordC4 >>> 24) & 0xFF,
      initialY: recordWordC8 & 0xFF,
      rawC0C3: hexWord(data, 36),
      rawC4C7: hexWord(data, 40),
      rawC8CB: hexWord(data, 44),
      rawCCCF: hexWord(data, 48),
    },
  };
}

function isBoundedForward(after, before) {
  if (!Number.isInteger(after) || after < 0 || after > 0xFFFFFFFF
      || !Number.isInteger(before) || before < 0 || before > 0xFFFFFFFF) {
    return false;
  }
  const distance = ((after >>> 0) - (before >>> 0)) >>> 0;
  return distance !== 0 && distance < UINT32_HALF_RANGE;
}

function isFresh(after = {}, before = {}) {
  return after.magicValid === true
    && isBoundedForward(after.hitCount, before.hitCount)
    && isBoundedForward(after.sequence, before.sequence);
}

function isControlledSlot(value) {
  return Number.isInteger(value) && value > 0 && value <= 20;
}

function isCharacterId(value) {
  return Number.isInteger(value) && value > 0 && value <= 0xFF;
}

function isAffiliation(value) {
  return value === 0 || value === 1;
}

function inputTimingMode(item) {
  if (item === null || typeof item !== 'object') {
    return null;
  }
  const hasLegacyTiming = Object.hasOwn(item, 'holdMs');
  const nativeFields = ['downFrame', 'upFrame', 'holdFrames', 'captureFrame'];
  const hasNativeTiming = nativeFields.some(field => Object.hasOwn(item, field));
  if (hasLegacyTiming && !hasNativeTiming) {
    return Number.isInteger(item.holdMs) && item.holdMs >= 0 ? 'legacy' : null;
  }
  if (!hasLegacyTiming && nativeFields.every(field => Object.hasOwn(item, field))) {
    return Number.isInteger(item.downFrame)
      && Number.isInteger(item.upFrame)
      && Number.isInteger(item.holdFrames)
      && Number.isInteger(item.captureFrame)
      && item.downFrame > 0
      && item.upFrame > item.downFrame
      && item.holdFrames === item.upFrame - item.downFrame
      && item.captureFrame > item.upFrame
      ? 'native'
      : null;
  }
  return null;
}

function expectedInputPlanValid(plan) {
  if (!Array.isArray(plan) || !Object.isFrozen(plan) || plan.length === 0) {
    return false;
  }
  const timingMode = inputTimingMode(plan[0]);
  return timingMode !== null
    && plan.every(item => Object.isFrozen(item)
      && typeof item.phase === 'string'
      && Number.isInteger(item.step)
      && typeof item.logicalKey === 'string'
      && typeof item.gbaButton === 'string'
      && inputTimingMode(item) === timingMode);
}

function inputMatchesPlan(events, plan) {
  return events.length === plan.length && events.every((event, index) => {
    const expected = plan[index];
    const timingMode = inputTimingMode(expected);
    const timingMatches = timingMode === inputTimingMode(event)
      && (timingMode === 'legacy'
        ? event.holdMs === expected.holdMs
        : event.downFrame === expected.downFrame
          && event.upFrame === expected.upFrame
          && event.holdFrames === expected.holdFrames
          && event.captureFrame === expected.captureFrame);
    return timingMatches
      && event.phase === expected.phase
      && event.step === expected.step
      && event.logicalKey === expected.logicalKey
      && event.gbaButton === expected.gbaButton;
  });
}

const CURRENT_UNIT_SOURCES = new Map([
  [2, '0x080739D8'],
  [3, '0x08073BAC'],
]);

function evaluatePlayerControlEvidence(input = {}) {
  const baseline = input.baseline || {};
  const final = input.final || {};
  const player = final.player || {};
  const current = final.current || {};
  const inputEvents = Array.isArray(input.inputEvents) ? input.inputEvents : [];
  const controlledDiagnosticValid = isControlledSlot(input.controlledSlot)
    && isCharacterId(input.controlledCharacterId)
    && isAffiliation(input.controlledAffiliation);
  const selectorProtocolValid = player.argument0 === 9
    && player.argument1 === 0
    && player.argument2 === 1;
  const currentSourceValid = CURRENT_UNIT_SOURCES.get(current.eventCode)
    === input.currentSourceHook;
  const controlledUnitConsistent = input.controlledUnitFromWram === true
    && controlledDiagnosticValid
    && current.argument0 === input.controlledSlot;
  const immutableExpectedPlan = expectedInputPlanValid(input.expectedInputPlan);
  const checks = {
    playerObserverFresh: isFresh(player, baseline.player),
    currentUnitObserverFresh: isFresh(current, baseline.current),
    playerAfterBaselineBoundary: isBoundedForward(player.sequence, baseline.sequenceBoundary),
    currentAfterBaselineBoundary: isBoundedForward(current.sequence, baseline.sequenceBoundary),
    observerOrderValid: isBoundedForward(current.sequence, player.sequence),
    eventCodesValid: player.eventCode === PLAYER_CONTROL_EVENT
      && CURRENT_UNIT_SOURCES.has(current.eventCode),
    selectorProtocolValid,
    currentSourceValid,
    battleIdValid: input.battleId === 41,
    mapLoaded: input.mapLoaded === true,
    battleMapForeground: input.screenState === 'battle-map',
    controlledUnitDiagnosticValid: controlledDiagnosticValid,
    controlledUnitConsistent,
    expectedInputPlanValid: immutableExpectedPlan,
    noUnlistedInputs: inputEvents.every(event => event?.classification === 'explicit'),
    inputComplete: inputEvents.length > 0
      && inputEvents.every(event => event?.downCompleted === true && event?.upCompleted === true),
    inputPlanMatches: immutableExpectedPlan
      && inputMatchesPlan(inputEvents, input.expectedInputPlan),
  };

  const failures = [
    ['playerObserverFresh', 'player-observer-not-fresh'],
    ['currentUnitObserverFresh', 'current-unit-observer-not-fresh'],
    ['playerAfterBaselineBoundary', 'player-observer-not-after-baseline-boundary'],
    ['currentAfterBaselineBoundary', 'current-unit-observer-not-after-baseline-boundary'],
    ['eventCodesValid', 'observer-event-code-invalid'],
    ['selectorProtocolValid', 'player-selector-protocol-invalid'],
    ['currentSourceValid', 'current-unit-source-invalid'],
    ['observerOrderValid', 'observer-order-invalid'],
    ['battleIdValid', 'battle-id-invalid'],
    ['mapLoaded', 'map-not-loaded'],
    ['battleMapForeground', 'battle-map-not-foreground'],
    ['controlledUnitDiagnosticValid', 'controlled-unit-diagnostic-invalid'],
    ['controlledUnitConsistent', 'controlled-unit-inconsistent'],
    ['expectedInputPlanValid', 'expected-input-plan-invalid'],
    ['noUnlistedInputs', 'unlisted-input-used'],
    ['inputComplete', 'input-incomplete'],
    ['inputPlanMatches', 'input-plan-mismatch'],
  ];
  const failure = failures.find(([check]) => !checks[check]);
  return {
    verified: failure === undefined,
    reason: failure ? failure[1] : 'player-control-verified',
    checks,
  };
}

const MOVEDONE_SOURCES = new Map([
  [1, '0x0807443C'],
  [2, '0x08074918'],
]);
const UNIT_RECORD_BASE = 0x020240C0;
const UNIT_RECORD_SIZE = 0x1D4;

function isEwramPointer(value) {
  return Number.isInteger(value) && value >= 0x02000000 && value < 0x02040000;
}

function validUnitIdentity(unit = {}) {
  return isControlledSlot(unit.slot)
    && isEwramPointer(unit.recordAddress)
    && unit.recordAddress === UNIT_RECORD_BASE + unit.slot * UNIT_RECORD_SIZE
    && isCharacterId(unit.characterId)
    && isAffiliation(unit.affiliation);
}

function isRawWord(value) {
  return typeof value === 'string' && /^[0-9a-fA-F]{8}$/.test(value);
}

function isByte(value) {
  return Number.isInteger(value) && value >= 0 && value <= 0xFF;
}

function snapshotRawFieldsMatch(snapshot = {}) {
  if (![snapshot.rawC0C3, snapshot.rawC4C7, snapshot.rawC8CB, snapshot.rawCCCF]
    .every(isRawWord)) {
    return false;
  }
  const c0 = Buffer.from(snapshot.rawC0C3, 'hex');
  const c4 = Buffer.from(snapshot.rawC4C7, 'hex');
  const c8 = Buffer.from(snapshot.rawC8CB, 'hex');
  return snapshot.affiliation === (c0[0] & 1)
    && snapshot.active === ((c0[0] & 0x80) !== 0)
    && snapshot.x === c4[0]
    && snapshot.y === c4[1]
    && snapshot.initialX === c4[3]
    && snapshot.initialY === c8[0];
}

function validActingUnit(unit = {}) {
  return validUnitIdentity(unit)
    && unit.objectAddress === 0x0202680C
    && unit.objectSlot === unit.slot
    && unit.objectRecordPointer === unit.recordAddress
    && typeof unit.active === 'boolean'
    && isByte(unit.x)
    && isByte(unit.y)
    && isByte(unit.initialX)
    && isByte(unit.initialY)
    && isRawWord(unit.actionStateRaw);
}

function sameIdentity(left = {}, right = {}) {
  return left.slot === right.slot
    && left.recordAddress === right.recordAddress
    && left.characterId === right.characterId
    && left.affiliation === right.affiliation;
}

function snapshotMatchesUnit(snapshot = {}, unit = {}) {
  return snapshot.objectAddress === 0x0202680C
    && snapshot.objectSlot === unit.slot
    && snapshot.objectRecordPointer === unit.recordAddress
    && snapshot.recordAddress === unit.recordAddress
    && snapshot.characterId === unit.characterId
    && snapshot.affiliation === unit.affiliation
    && snapshot.active === unit.active
    && snapshot.x === unit.x
    && snapshot.y === unit.y
    && snapshot.initialX === unit.initialX
    && snapshot.initialY === unit.initialY
    && snapshot.rawCCCF === unit.actionStateRaw
    && snapshotRawFieldsMatch(snapshot)
    && isEwramPointer(snapshot.objectRecordPointer);
}

function evaluateMovedoneEvidence(input = {}) {
  const baselineEvents = Array.isArray(input.baseline?.events) ? input.baseline.events : [];
  const finalEvents = Array.isArray(input.final?.events) ? input.final.events : [];
  const freshEvents = finalEvents.filter((event, index) => isFresh(event, baselineEvents[index])
    && isBoundedForward(event.sequence, input.baseline?.sequenceBoundary));
  const event = freshEvents[0] || {};
  const before = input.actingUnitBefore || {};
  const after = input.actingUnitAfter || {};
  const controlled = input.controlledUnit || {};
  const expectedPlanValid = expectedInputPlanValid(input.expectedInputPlan);
  const explicitInputs = Array.isArray(input.explicitInputs) ? input.explicitInputs : [];
  const automaticInputs = Array.isArray(input.automaticInputs) ? input.automaticInputs : null;
  const sourceValid = MOVEDONE_SOURCES.get(event.eventCode) === event.sourceHook;
  const actingIdentityValid = validActingUnit(before)
    && validActingUnit(after)
    && sameIdentity(before, after)
    && snapshotMatchesUnit(event.snapshot, before);
  const battleMapContextValid = input.map?.width === 36
    && input.map?.height === 44
    && input.map?.gridX === 9
    && input.map?.gridY === 22;
  const coordinatesChanged = Number.isInteger(before.x) && Number.isInteger(before.y)
    && Number.isInteger(after.x) && Number.isInteger(after.y)
    && (before.x !== after.x || before.y !== after.y);
  const actionChanged = typeof before.actionStateRaw === 'string'
    && typeof after.actionStateRaw === 'string'
    && before.actionStateRaw !== after.actionStateRaw;
  const roundChanged = typeof input.stateBefore?.roundOrPhaseRaw === 'string'
    && typeof input.stateAfter?.roundOrPhaseRaw === 'string'
    && input.stateBefore.roundOrPhaseRaw !== input.stateAfter.roundOrPhaseRaw;
  const checks = {
    movedoneEventCountValid: freshEvents.length === 1,
    movedoneSourceValid: sourceValid,
    scenarioValid: input.scenario === 41,
    battleIdValid: input.battleId === 41,
    mapLoaded: input.mapLoaded === true,
    battleMapForeground: input.screenState === 'battle-map',
    battleMapContextValid,
    actingUnitIdentityValid: actingIdentityValid,
    controlledUnitValid: validUnitIdentity(controlled),
    actingUnitControlled: sameIdentity(before, controlled),
    coordinatesChanged,
    actionOrRoundStateChanged: actionChanged || roundChanged,
    expectedInputPlanValid: expectedPlanValid,
    explicitInputsOnly: explicitInputs.length > 0
      && explicitInputs.every(item => item?.classification === 'explicit'),
    explicitInputsComplete: explicitInputs.length > 0
      && explicitInputs.every(item => item?.downCompleted === true && item?.upCompleted === true),
    inputPlanMatches: expectedPlanValid && inputMatchesPlan(explicitInputs, input.expectedInputPlan),
    noAutomaticDriverInputs: automaticInputs !== null && automaticInputs.length === 0,
    automaticGameActionRecorded: typeof input.automaticGameAction === 'boolean',
  };
  const failures = [
    ['movedoneEventCountValid', 'movedone-event-count-invalid'],
    ['movedoneSourceValid', 'movedone-source-invalid'],
    ['scenarioValid', 'scenario-invalid'],
    ['battleIdValid', 'battle-id-invalid'],
    ['mapLoaded', 'map-not-loaded'],
    ['battleMapForeground', 'battle-map-not-foreground'],
    ['battleMapContextValid', 'battle-map-context-invalid'],
    ['actingUnitIdentityValid', 'acting-unit-identity-mismatch'],
    ['controlledUnitValid', 'controlled-unit-invalid'],
    ['actingUnitControlled', 'acting-unit-not-controlled'],
    ['coordinatesChanged', 'coordinates-unchanged'],
    ['actionOrRoundStateChanged', 'action-round-state-unchanged'],
    ['expectedInputPlanValid', 'expected-input-plan-invalid'],
    ['explicitInputsOnly', 'explicit-input-invalid'],
    ['explicitInputsComplete', 'input-incomplete'],
    ['inputPlanMatches', 'input-plan-mismatch'],
    ['noAutomaticDriverInputs', 'automatic-driver-input-used'],
    ['automaticGameActionRecorded', 'automatic-game-action-invalid'],
  ];
  const failure = failures.find(([check]) => !checks[check]);
  return {
    verified: failure === undefined,
    reason: failure ? failure[1] : 'movedone-verified',
    checks,
    automaticGameAction: input.automaticGameAction,
  };
}

module.exports = {
  decodePublishedCall,
  decodeMovedoneRecord,
  evaluateMovedoneEvidence,
  evaluatePlayerControlEvidence,
};
