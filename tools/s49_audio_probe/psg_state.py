#!/usr/bin/env python3
"""Decode the GBA sound / DMA register block into a comparable state dict.

The block read by the probe starts at 0x04000060 and is 0x80 bytes long, so it
covers:

    0x04000060  NR10   square 1 sweep
    0x04000062  NR11   square 1 duty / length
    0x04000064  NR12   square 1 envelope
    0x04000066  NR13   square 1 frequency low
    0x04000068  NR14   square 1 frequency high / trigger
    0x0400006C  NR21   square 2 duty / length
    0x04000070  NR22   square 2 envelope
    0x04000072  NR23   square 2 frequency low
    0x04000074  NR24   square 2 frequency high / trigger
    0x04000078  NR30   wave channel enable
    0x0400007C  NR31   wave length
    0x0400007E  NR32   wave volume
    0x04000080  NR33   wave frequency low
    0x04000082  NR34   wave frequency high / trigger
    0x04000088  NR41   noise length
    0x0400008C  NR42   noise envelope
    0x0400008E  NR43   noise frequency
    0x04000090  NR44   noise trigger
    0x04000094  NR50   SOUNDCNT_L  (master volume L/R)
    0x04000096  NR51   SOUNDCNT_H  (per-channel + DirectSound volumes)
    0x04000098  NR52   SOUNDCNT_X  (sound master enable / IRQ)
    0x0400009C  SOUNDBIAS
    0x040000A0  FIFO A
    0x040000A4  FIFO B
    0x040000B0  DMA0 source / dest / control
    0x040000BC  DMA1 source / dest / control
    0x040000C8  DMA2 source / dest / control
    0x040000D4  DMA3 source / dest / control

All of these are 16-bit registers, so the low byte sits at the even address.
"""
from __future__ import annotations

PSG_BASE = 0x04000060
PSG_LENGTH = 0x80

_U16 = {
    # PSG channel 1-3 registers (GBA layout, 0x04000060..0x0400007F)
    "nr10": 0x00, "nr11": 0x02, "nr12": 0x04, "nr13": 0x06, "nr14": 0x08,
    "nr21": 0x0C, "nr22": 0x0E, "nr23": 0x10, "nr24": 0x12,
    "nr30": 0x18, "nr31": 0x1C, "nr32": 0x1E,
    # Sound control (GBA keeps the GB control block at 0x04000080..0x87).
    # This is the same map the reverse line's oracle/audio_io_probe.py uses
    # ("SOUNDCNT 0x80-0x88", "SOUNDBIAS 0x88-0x90").
    "nr50": 0x20,   # SOUNDCNT_L  master volume
    "nr51": 0x22,   # SOUNDCNT_H  per-channel + DirectSound volumes
    "nr52": 0x24,   # SOUNDCNT_X  master enable / IRQ
    "bias": 0x28,   # SOUNDBIAS
    "fifo_a": 0x40, "fifo_b": 0x44,
    "dma0_sad": 0x50, "dma0_dad": 0x54, "dma0_cnt": 0x58,
    "dma1_sad": 0x5C, "dma1_dad": 0x60, "dma1_cnt": 0x64,
    "dma2_sad": 0x68, "dma2_dad": 0x6C, "dma2_cnt": 0x70,
    "dma3_sad": 0x74, "dma3_dad": 0x78, "dma3_cnt": 0x7C,
}

# SOUNDCNT_H (NR51) bit layout (GB / GBA compatible)
NR51_PSG_CHANNELS = 0x0FFF       # ch1..ch4 right/left volume enables
NR51_DIRECT_A = 0x3000           # DirectSound A right/left
NR51_DIRECT_B = 0xC000           # DirectSound B right/left

# SOUNDCNT_X (NR52) bit layout (GB compatible)
NR52_STATUS_BITS = 0x000F        # channel 1/2 status (read only)
NR52_MASTER_ENABLE = 0x0080
NR52_IRQ = 0x4000


def decode(buffer: bytes) -> dict:
    """Decode one PSG / DMA window into a comparable state dict."""
    def u16(offset: int) -> int:
        return buffer[offset] | (buffer[offset + 1] << 8)

    def u32(offset: int) -> int:
        return (buffer[offset] | (buffer[offset + 1] << 8)
                | (buffer[offset + 2] << 16) | (buffer[offset + 3] << 24))

    state = {name: u16(offset) for name, offset in _U16.items()}
    state["psg_channels_enabled"] = state["nr51"] & NR51_PSG_CHANNELS
    state["directsound_a"] = bool(state["nr51"] & NR51_DIRECT_A)
    state["directsound_b"] = bool(state["nr51"] & NR51_DIRECT_B)
    state["dma_a_enabled"] = bool(state["nr52"] & 0x0100)
    state["dma_b_enabled"] = bool(state["nr52"] & 0x0200)
    state["master_enable"] = bool(state["nr52"] & NR52_MASTER_ENABLE)
    state["dma1_control"] = u32(_U16["dma1_cnt"])
    state["dma2_control"] = u32(_U16["dma2_cnt"])
    state["dma1_running"] = bool(state["dma1_control"] & 0x8000)
    state["dma2_running"] = bool(state["dma2_control"] & 0x8000)
    state["dma1_dest"] = u32(_U16["dma1_dad"]) & 0x0FFFFFFE
    state["dma2_dest"] = u32(_U16["dma2_dad"]) & 0x0FFFFFFE
    return state


# Fields that describe "is the PSG doing anything at all".  A frame where all
# of these are constant means "no audio hardware activity".
ACTIVITY_KEYS = (
    "nr10", "nr11", "nr12", "nr13", "nr14",
    "nr21", "nr22", "nr23", "nr24",
    "nr30", "nr31", "nr32",
    "nr50", "nr51", "nr52",
    "fifo_a", "fifo_b",
    "dma1_control", "dma2_control",
)


def activity_signature(state: dict) -> tuple:
    return tuple(state[key] for key in ACTIVITY_KEYS)


def is_audible(state: dict) -> bool:
    """True when the sound hardware is configured to produce something."""
    if not state["master_enable"]:
        return False
    if state["psg_channels_enabled"]:
        return True
    if state["directsound_a"] or state["directsound_b"]:
        return True
    return False


def episodes(signatures: list[tuple], audible: list[bool]) -> list[dict]:
    """Collapse a per-frame trace into contiguous episodes of equal state."""
    out: list[dict] = []
    start = 0
    for index in range(1, len(signatures) + 1):
        if index == len(signatures) or signatures[index] != signatures[start]:
            if audible[start]:
                out.append({
                    "start_frame": start + 1,
                    "end_frame": index,
                    "frames": index - start,
                    "signature": {
                        key: value for key, value in
                        zip(ACTIVITY_KEYS, signatures[start])
                    },
                })
            start = index
    return out
