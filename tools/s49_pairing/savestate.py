"""Read a mGBA ``.ss9`` savestate without the headless probe.

The probe's live IO read answers the registers from ``0x10`` upwards with a
per frame constant filler, which is why the judgment bench could only read a
**horizontal** camera component.  The savestate file itself carries the real
IO block, so reading it directly gives the **vertical** scroll registers as
well -- the two dimensional camera position the bench needed.

The container format is re-used read-only from ``tools/s49_victory_capture``
(W3's original-ROM state reader); nothing in that directory is modified.
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "s49_victory_capture"))
sys.path.insert(0, str(REPO / "tools"))

import s49_state  # noqa: E402
from s49_fidelity_report.pixels import load_rgb  # noqa: E402,F401

IO_BASE = 0x04000000
IO_LENGTH = 0x400
PRAM_BASE = 0x05000000
PRAM_LENGTH = 0x400
VRAM_BASE = 0x06000000
VRAM_LENGTH = 0x18000
EWRAM_BASE = 0x02000000
EWRAM_LENGTH = 0x40000

# A background scroll register is nine bits of hardware; the game may have
# written a wider word, so the value is masked before it is used as a camera
# position.
SCROLL_MASK = 0x1FF


def load(path: pathlib.Path):
    """Load a savestate and return the object with the ``read_memory`` method."""
    return s49_state.load_state(path)


def regions(state) -> dict:
    """The IO block, the palette RAM, the video RAM and the EWRAM."""
    return {
        "io": state.read_memory(IO_BASE, IO_LENGTH),
        "pram": state.read_memory(PRAM_BASE, PRAM_LENGTH),
        "vram": state.read_memory(VRAM_BASE, VRAM_LENGTH),
        "ewram": state.read_memory(EWRAM_BASE, EWRAM_LENGTH),
    }


def io_registers(io_bytes: bytes) -> dict:
    """The display registers of the IO block.

    ⭐ **2026-10-25（wave 20 / E3 查出，父代理修）：地址表此前是错的。**
    旧代码按 4 字节步长读 `0x04/0x08/0x0C` 当 BGxCNT、按 `0x06 + 4n` 当 BGxHOFS
    ⇒ 读到的是 DISPSTAT / VCOUNT / BG1CNT / BG3CNT。

    正确的 GBA 布局（**2 字节步长**）::

        0x00 DISPCNT  0x04 DISPSTAT  0x06 VCOUNT
        0x08 BG0CNT   0x0A BG1CNT   0x0C BG2CNT   0x0E BG3CNT
        0x10 BG0HOFS  0x12 BG0VOFS
        0x14 BG1HOFS  0x16 BG1VOFS
        0x18 BG2HOFS  0x1A BG2VOFS
        0x1C BG3HOFS  0x1E BG3VOFS
    """
    import struct

    values = struct.unpack_from("<32H", io_bytes)
    hofs_raw = [values[0x10 // 2 + 4 * index] for index in range(3)]
    vofs_raw = [values[0x12 // 2 + 4 * index] for index in range(3)]
    return {
        "dispcnt": values[0x00 // 2],
        "bg_cnt": [values[0x08 // 2 + index] for index in range(4)],
        "bg_hofs_raw": hofs_raw,
        "bg_hofs": [value & SCROLL_MASK for value in hofs_raw],
        "bg_vofs_raw": vofs_raw,
        "bg_vofs": [value & SCROLL_MASK for value in vofs_raw],
    }
