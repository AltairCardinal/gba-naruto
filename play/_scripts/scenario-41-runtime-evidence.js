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

function evaluatePlayerControlEvidence(input = {}) {
  const baseline = input.baseline || {};
  const final = input.final || {};
  const player = final.player || {};
  const current = final.current || {};
  const controlledSlot = input.controlledSlot ?? player.argument0;
  const affiliationMatches = input.controlledAffiliation === undefined
    || (player.argument2 === input.controlledAffiliation
      && current.argument2 === input.controlledAffiliation);
  const checks = {
    playerObserverFresh: isFresh(player, baseline.player),
    currentUnitObserverFresh: isFresh(current, baseline.current),
    observerOrderValid: isBoundedForward(current.sequence, player.sequence),
    eventCodesValid: player.eventCode === PLAYER_CONTROL_EVENT
      && current.eventCode === CURRENT_UNIT_EVENT,
    battleIdValid: input.battleId === 41,
    mapLoaded: input.mapLoaded === true,
    battleMapForeground: input.screenState === 'battle-map',
    controlledUnitConsistent: player.argument0 === controlledSlot
      && current.argument0 === input.controlledCharacterId
      && affiliationMatches,
    explicitInputPresent: Array.isArray(input.explicitInputs) && input.explicitInputs.length > 0,
    noUnlistedInputs: Array.isArray(input.automaticInputs) && input.automaticInputs.length === 0,
  };

  const failures = [
    ['playerObserverFresh', 'player-observer-not-fresh'],
    ['currentUnitObserverFresh', 'current-unit-observer-not-fresh'],
    ['eventCodesValid', 'observer-event-code-invalid'],
    ['observerOrderValid', 'observer-order-invalid'],
    ['battleIdValid', 'battle-id-invalid'],
    ['mapLoaded', 'map-not-loaded'],
    ['battleMapForeground', 'battle-map-not-foreground'],
    ['controlledUnitConsistent', 'controlled-unit-inconsistent'],
    ['noUnlistedInputs', 'unlisted-input-used'],
    ['explicitInputPresent', 'explicit-input-missing'],
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
