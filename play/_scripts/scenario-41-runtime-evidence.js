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

function expectedInputPlanValid(plan) {
  return Array.isArray(plan)
    && Object.isFrozen(plan)
    && plan.length > 0
    && plan.every(item => Object.isFrozen(item)
      && typeof item.phase === 'string'
      && Number.isInteger(item.step)
      && typeof item.logicalKey === 'string'
      && typeof item.gbaButton === 'string'
      && Number.isInteger(item.holdMs)
      && item.holdMs >= 0);
}

function inputMatchesPlan(events, plan) {
  return events.length === plan.length && events.every((event, index) => {
    const expected = plan[index];
    return event.phase === expected.phase
      && event.step === expected.step
      && event.logicalKey === expected.logicalKey
      && event.gbaButton === expected.gbaButton
      && event.holdMs === expected.holdMs;
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

module.exports = {
  decodePublishedCall,
  evaluatePlayerControlEvidence,
};
