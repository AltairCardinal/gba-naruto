#!/usr/bin/env python3
"""Persistent MP2K musical registers and command-to-channel requests."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from tools.render_m4a_midi import _track_mix_coefficients
except ModuleNotFoundError:  # direct ``python tools/...`` execution
    from render_m4a_midi import _track_mix_coefficients


def _signed8(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def _note_ticks(name: str) -> int:
    return int(name[1:])


@dataclass(frozen=True)
class NoteRequest:
    tick: int
    track_ptr: int
    voice: int
    key: int
    velocity: int
    gate_time: int | None
    tied: bool
    pitch_key: int
    pitch_fine: int
    track_right: int
    track_left: int


class MPlayMusicalState:
    """Track registers updated by decoded commands between VM control steps."""

    def __init__(self, *, track_ptr: int):
        self.track_ptr = track_ptr
        self.tempo_raw = 75
        self.priority = 0
        self.key = 60
        self.velocity = 100
        self.voice = 0
        self.volume = 127
        self.volume_multiplier = 64
        self.pan = 64
        self.pan_extra = 0
        self.key_shift = 0
        self.bend = 0
        self.bend_range = 2
        self.tune = 0
        self.lfo_speed = 22
        self.lfo_delay = 0
        self.lfo_countdown = 0
        self.lfo_phase = 0
        self.mod_depth = 0
        self.mod_type = 0
        self.mod_value = 0
        self.pitch_dirty = False
        self.mix_dirty = False
        self.note_requests: list[NoteRequest] = []
        self.release_keys: list[int] = []
        self.stop_requested = False

    def pitch_components(self) -> dict[str, int]:
        return {
            "key_shift": self.key_shift,
            "bend": self.bend,
            "bend_range": self.bend_range,
            "tune": self.tune,
        }

    def _pitch(self) -> tuple[int, int]:
        modulation = (self.mod_value << 4) if self.mod_type == 0 else 0
        total = (
            ((self.tune + self.bend * self.bend_range) << 2)
            + (self.key_shift << 8)
            + modulation
        )
        return max(0, self.key + (total >> 8)), total & 0xFF

    def _mix(self) -> tuple[int, int]:
        return _track_mix_coefficients(
            self.volume,
            self.volume_multiplier,
            self.pan,
            mod_type=self.mod_type,
            mod_value=self.mod_value,
            pan_extra=self.pan_extra,
        )

    def handle_command(self, command: dict, *, tick: int) -> None:
        name = command["name"]
        value = command.get("value")
        if name == "TEMPO":
            self.tempo_raw = value
        elif name == "PRIO":
            self.priority = value
        elif name == "VOICE":
            self.voice = value
        elif name == "VOL":
            self.volume = value
            self.mix_dirty = True
        elif name == "PAN":
            self.pan = value
            self.mix_dirty = True
        elif name == "KEYSH":
            self.key_shift = _signed8(value)
            self.pitch_dirty = True
        elif name == "BEND":
            self.bend = value - 0x40
            self.pitch_dirty = True
        elif name == "BENDR":
            self.bend_range = value
            self.pitch_dirty = True
        elif name == "TUNE":
            self.tune = value - 0x40
            self.pitch_dirty = True
        elif name == "LFOS":
            self.lfo_speed = value
            if value == 0:
                self.mod_value = 0
                self.lfo_phase = 0
                self._mark_mod_dirty()
        elif name == "LFODL":
            self.lfo_delay = value
        elif name == "MOD":
            self.mod_depth = value
            if value == 0:
                self.mod_value = 0
                self.lfo_phase = 0
                self._mark_mod_dirty()
        elif name == "MODT":
            previous = self.mod_type
            self.mod_type = value
            if previous == 0 or value == 0:
                self.pitch_dirty = True
            if previous in (1, 2) or value in (1, 2):
                self.mix_dirty = True
        elif name == "EOT":
            self.release_keys.append(command.get("key", self.key))
        elif name == "FINE":
            self.stop_requested = True
        elif name == "TIE" or name.startswith("N"):
            args = command.get("args", [])
            if len(args) >= 1:
                self.key = args[0]
            if len(args) >= 2:
                self.velocity = args[1]
            gate = args[2] if len(args) >= 3 else 0
            self.lfo_countdown = self.lfo_delay
            pitch_key, pitch_fine = self._pitch()
            right, left = self._mix()
            tied = name == "TIE"
            self.note_requests.append(NoteRequest(
                tick=tick,
                track_ptr=self.track_ptr,
                voice=self.voice,
                key=self.key,
                velocity=self.velocity,
                gate_time=None if tied else _note_ticks(name) + gate,
                tied=tied,
                pitch_key=pitch_key,
                pitch_fine=pitch_fine,
                track_right=right,
                track_left=left,
            ))

    def _mark_mod_dirty(self) -> None:
        if self.mod_type == 0:
            self.pitch_dirty = True
        elif self.mod_type in (1, 2):
            self.mix_dirty = True

    def advance_lfo(self, *, tick: int) -> None:
        del tick  # retained in the API for later timed propagation diagnostics
        if self.lfo_speed == 0 or self.mod_depth == 0:
            return
        if self.lfo_countdown:
            self.lfo_countdown = (self.lfo_countdown - 1) & 0xFF
            return
        self.lfo_phase = (self.lfo_phase + self.lfo_speed) & 0xFF
        if 0x40 <= self.lfo_phase <= 0xBF:
            triangle = 0x80 - self.lfo_phase
        else:
            triangle = _signed8(self.lfo_phase)
        next_mod = (self.mod_depth * triangle) >> 6
        if (next_mod & 0xFF) == (self.mod_value & 0xFF):
            return
        self.mod_value = next_mod
        self._mark_mod_dirty()

    def clear_dirty(self) -> None:
        self.pitch_dirty = False
        self.mix_dirty = False
