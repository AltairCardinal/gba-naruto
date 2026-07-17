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
  return typeof value === 'string' && /^[0-9a-f]{8}$/.test(value);
}

function isUint32(value) {
  return Number.isInteger(value) && value >= 0 && value <= 0xFFFFFFFF;
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

const MOVEDONE_SNAPSHOT_FIELDS = [
  'objectAddress', 'objectSlot', 'objectRecordPointer', 'recordAddress',
  'characterId', 'affiliation', 'active', 'x', 'y', 'initialX', 'initialY',
  'rawC0C3', 'rawC4C7', 'rawC8CB', 'rawCCCF',
];

function isZeroMovedoneSnapshot(snapshot) {
  return snapshot.objectSlot === 0
    && snapshot.objectRecordPointer === 0
    && snapshot.recordAddress === 0
    && snapshot.characterId === 0
    && snapshot.affiliation === 0
    && snapshot.active === false
    && snapshot.x === 0
    && snapshot.y === 0
    && snapshot.initialX === 0
    && snapshot.initialY === 0
    && [snapshot.rawC0C3, snapshot.rawC4C7, snapshot.rawC8CB, snapshot.rawCCCF]
      .every(word => word === '00000000');
}

function validMovedoneSnapshot(snapshot = {}) {
  const fieldsValid = snapshot !== null
    && typeof snapshot === 'object'
    && !Array.isArray(snapshot)
    && snapshot.objectAddress === 0x0202680C
    && isByte(snapshot.objectSlot)
    && isUint32(snapshot.objectRecordPointer)
    && isUint32(snapshot.recordAddress)
    && isByte(snapshot.characterId)
    && isAffiliation(snapshot.affiliation)
    && typeof snapshot.active === 'boolean'
    && isByte(snapshot.x)
    && isByte(snapshot.y)
    && isByte(snapshot.initialX)
    && isByte(snapshot.initialY)
    && snapshotRawFieldsMatch(snapshot);
  if (!fieldsValid) {
    return false;
  }
  const boundRecord = isControlledSlot(snapshot.objectSlot)
    && snapshot.objectRecordPointer === snapshot.recordAddress
    && snapshot.recordAddress === UNIT_RECORD_BASE + snapshot.objectSlot * UNIT_RECORD_SIZE
    && isCharacterId(snapshot.characterId);
  return isZeroMovedoneSnapshot(snapshot) || boundRecord;
}

function validMovedoneRecord(record, eventCode, sourceHook) {
  const countersAreZero = record?.hitCount === 0 && record?.sequence === 0;
  return record !== null
    && typeof record === 'object'
    && !Array.isArray(record)
    && typeof record.magicValid === 'boolean'
    && isUint32(record.hitCount)
    && isUint32(record.sequence)
    && record.eventCode === eventCode
    && record.sourceHook === sourceHook
    && validMovedoneSnapshot(record.snapshot)
    && (countersAreZero
      ? record.magicValid === false && isZeroMovedoneSnapshot(record.snapshot)
      : record.magicValid === true);
}

function sameMovedoneRecord(left, right) {
  return left.magicValid === right.magicValid
    && left.hitCount === right.hitCount
    && left.sequence === right.sequence
    && left.eventCode === right.eventCode
    && left.sourceHook === right.sourceHook
    && MOVEDONE_SNAPSHOT_FIELDS.every(field => left.snapshot[field] === right.snapshot[field]);
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
  const allowedSites = [...MOVEDONE_SOURCES.entries()];
  const sourcesValid = [baselineEvents, finalEvents].every(events => events.length === 2
    && events.every(event => MOVEDONE_SOURCES.get(event?.eventCode) === event?.sourceHook));
  const recordSchemaValid = sourcesValid
    && [baselineEvents, finalEvents].every(events => allowedSites.every(
      ([eventCode, sourceHook], index) => events[index]?.eventCode === eventCode
        && events[index]?.sourceHook === sourceHook
        && validMovedoneRecord(events[index], eventCode, sourceHook),
    ));
  const pairedSites = recordSchemaValid ? allowedSites.map(
    (_site, index) => ({
      beforeEvent: baselineEvents[index],
      afterEvent: finalEvents[index],
    }),
  ) : [];
  const freshEvents = pairedSites.flatMap(({ beforeEvent, afterEvent }) => (
    isFresh(afterEvent, beforeEvent)
      && isBoundedForward(afterEvent.sequence, input.baseline?.sequenceBoundary)
      ? [afterEvent] : []
  ));
  const staleSitesUnchanged = recordSchemaValid && pairedSites.every(
    ({ beforeEvent, afterEvent }) => isFresh(afterEvent, beforeEvent)
      || sameMovedoneRecord(afterEvent, beforeEvent),
  );
  const siteSchemaValid = recordSchemaValid && staleSitesUnchanged;
  const event = freshEvents[0] || {};
  const before = input.actingUnitBefore || {};
  const after = input.actingUnitAfter || {};
  const controlled = input.controlledUnit || {};
  const expectedPlanValid = expectedInputPlanValid(input.expectedInputPlan);
  const explicitInputs = Array.isArray(input.explicitInputs) ? input.explicitInputs : [];
  const automaticInputs = Array.isArray(input.automaticInputs) ? input.automaticInputs : null;
  const sourceValid = sourcesValid;
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
  const roundContextValid = input.stateBefore?.address === '0x0200A880'
    && input.stateAfter?.address === '0x0200A880'
    && isRawWord(input.stateBefore.raw)
    && isRawWord(input.stateAfter.raw);
  const roundChanged = roundContextValid && input.stateBefore.raw !== input.stateAfter.raw;
  const checks = {
    movedoneSiteSchemaValid: siteSchemaValid,
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
    roundContextValid,
    actionOrRoundStateChanged: actionChanged || roundChanged,
    expectedInputPlanValid: expectedPlanValid,
    explicitInputsOnly: explicitInputs.length > 0
      && explicitInputs.every(item => item?.classification === 'explicit'),
    explicitInputsComplete: explicitInputs.length > 0
      && explicitInputs.every(item => item?.downCompleted === true && item?.upCompleted === true),
    inputPlanMatches: expectedPlanValid && inputMatchesPlan(explicitInputs, input.expectedInputPlan),
    noAutomaticDriverInputs: automaticInputs !== null && automaticInputs.length === 0,
    automaticGameActionRecorded: typeof input.automaticGameAction === 'boolean',
    automaticGameActionManual: input.automaticGameAction === false,
  };
  const failures = [
    ['movedoneSourceValid', 'movedone-source-invalid'],
    ['movedoneSiteSchemaValid', 'movedone-site-schema-invalid'],
    ['movedoneEventCountValid', 'movedone-event-count-invalid'],
    ['scenarioValid', 'scenario-invalid'],
    ['battleIdValid', 'battle-id-invalid'],
    ['mapLoaded', 'map-not-loaded'],
    ['battleMapForeground', 'battle-map-not-foreground'],
    ['battleMapContextValid', 'battle-map-context-invalid'],
    ['actingUnitIdentityValid', 'acting-unit-identity-mismatch'],
    ['controlledUnitValid', 'controlled-unit-invalid'],
    ['coordinatesChanged', 'coordinates-unchanged'],
    ['roundContextValid', 'round-context-invalid'],
    ['actionOrRoundStateChanged', 'action-round-state-unchanged'],
    ['expectedInputPlanValid', 'expected-input-plan-invalid'],
    ['explicitInputsOnly', 'explicit-input-invalid'],
    ['explicitInputsComplete', 'input-incomplete'],
    ['inputPlanMatches', 'input-plan-mismatch'],
    ['noAutomaticDriverInputs', 'automatic-driver-input-used'],
    ['automaticGameActionRecorded', 'automatic-game-action-invalid'],
  ];
  const failure = failures.find(([check]) => !checks[check]);
  const diagnosticVerified = failure === undefined;
  let classification = diagnosticVerified ? 'player-controlled-manual' : 'invalid';
  let reason = failure ? failure[1] : 'movedone-verified';
  if (diagnosticVerified && !checks.actingUnitControlled) {
    classification = 'non-controlled';
    reason = 'non-controlled';
  } else if (diagnosticVerified && !checks.automaticGameActionManual) {
    classification = 'automatic-game-action';
    reason = 'automatic-game-action';
  }
  return {
    diagnosticVerified,
    verified: diagnosticVerified
      && checks.actingUnitControlled
      && checks.automaticGameActionManual,
    classification,
    reason,
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
