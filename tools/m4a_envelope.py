#!/usr/bin/env python3
"""ROM-exact DirectSound envelope primitives for this game's MP2K engine."""

from __future__ import annotations

from dataclasses import dataclass

STATUS_ATTACK = 3
STATUS_DECAY = 2
STATUS_SUSTAIN = 1
STATUS_ECHO = 0x04
STATUS_LOOP = 0x10
STATUS_RELEASE = 0x40
STATUS_NEW = 0x80


@dataclass
class EnvelopeState:
    status: int
    level: int = 0
    echo_remaining: int = 0

    @classmethod
    def new(cls, *, released: bool = False, looped_sample: bool = False):
        status = STATUS_NEW
        if released:
            status |= STATUS_RELEASE
        if looped_sample:
            status |= STATUS_LOOP
        return cls(status=status)

    @classmethod
    def release(cls, *, level: int, pseudo_echo_length: int = 0):
        return cls(
            status=STATUS_RELEASE,
            level=level,
            echo_remaining=pseudo_echo_length,
        )

    @property
    def active(self) -> bool:
        return self.status != 0

    @property
    def phase(self) -> str:
        if not self.active:
            return "inactive"
        if self.status & STATUS_ECHO:
            return "echo"
        if self.status & STATUS_RELEASE:
            return "release"
        return {
            STATUS_ATTACK: "attack",
            STATUS_DECAY: "decay",
            STATUS_SUSTAIN: "sustain",
        }.get(self.status & 3, "new")


def _stop(state: EnvelopeState) -> bool:
    state.status = 0
    return False


def _enter_echo_or_stop(
    state: EnvelopeState, *, pseudo_echo_volume: int
) -> bool:
    state.level = pseudo_echo_volume
    if state.level == 0:
        return _stop(state)
    state.status |= STATUS_ECHO
    return True


def advance_envelope(
    state: EnvelopeState,
    *,
    attack: int,
    decay: int,
    sustain: int,
    release: int,
    pseudo_echo_volume: int,
) -> bool:
    """Advance one SoundMain mixer invocation (0x08099EC8..0x08099F68).

    Returns whether the channel produces gains during this invocation.
    Parameters and stored values intentionally retain their u8 integer rules.
    """
    if not state.active:
        return False

    if state.status & STATUS_NEW:
        if state.status & STATUS_RELEASE:
            return _stop(state)
        loop = state.status & STATUS_LOOP
        state.status = loop | STATUS_ATTACK
        state.level = 0

    if state.status & STATUS_ECHO:
        before = state.echo_remaining
        state.echo_remaining = (before - 1) & 0xFF
        if before <= 1:
            return _stop(state)
        return True

    if state.status & STATUS_RELEASE:
        state.level = (state.level * release) >> 8
        if state.level <= pseudo_echo_volume:
            return _enter_echo_or_stop(
                state, pseudo_echo_volume=pseudo_echo_volume
            )
        return True

    phase = state.status & 3
    if phase == STATUS_DECAY:
        state.level = (state.level * decay) >> 8
        if state.level <= sustain:
            state.level = sustain
            if state.level == 0:
                return _enter_echo_or_stop(
                    state, pseudo_echo_volume=pseudo_echo_volume
                )
            state.status = (state.status & ~3) | STATUS_SUSTAIN
        return True

    if phase == STATUS_ATTACK:
        level = state.level + attack
        if level >= 0xFF:
            state.level = 0xFF
            state.status = (state.status & ~3) | STATUS_DECAY
        else:
            state.level = level
        return True

    return phase == STATUS_SUSTAIN


def mixer_gains(
    pre_envelope_right: int,
    pre_envelope_left: int,
    *,
    level: int,
    master_volume: int,
) -> tuple[int, int]:
    """Reproduce 0x08099F6A..0x08099F82 channel gain writes."""
    master_envelope = ((master_volume + 1) * level) >> 4
    right = ((pre_envelope_right * master_envelope) >> 8) & 0xFF
    left = ((pre_envelope_left * master_envelope) >> 8) & 0xFF
    return right, left
