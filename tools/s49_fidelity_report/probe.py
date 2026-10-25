"""Read the machine state of a captured step.

Every step of the walk saved a savestate next to its PNG, so the state that
produced the frame can be re-loaded and inspected **without re-running the
walk**: the headless probe loads the savestate and dumps the regions the
content anchors are read from.

    load <step>.ss9
    dump <io base> <io len>      -- the IO register block
    dump <pram base> <pram len>  -- the palette RAM
    dump <vram base> <vram len>  -- the video RAM

The probe's ``dump`` command parses its address argument as a **decimal**
number, so the bases are converted here.

The dumps are cached as ``.bin`` files next to the capture, so a second run
of the bench does not touch the probe at all and the report stays
byte-identical.
"""

from __future__ import annotations

import pathlib
import struct
import subprocess

from .paths import PROBE_EXE

IO_BASE = 0x04000000
IO_LENGTH = 0x40
PRAM_BASE = 0x05000000
PRAM_LENGTH = 0x400
VRAM_BASE = 0x06000000
VRAM_LENGTH = 0x18000
# A background scroll register is 9 bits of hardware.
SCROLL_MASK = 0x1FF


class ProbeError(RuntimeError):
    pass


class Probe:
    """A single probe process, driven over its stdin/stdout pipe."""

    def __init__(self, rom: pathlib.Path, exe: pathlib.Path = PROBE_EXE):
        self.rom = pathlib.Path(rom)
        self.exe = pathlib.Path(exe)
        if not self.exe.exists():
            raise ProbeError(f"probe executable missing: {self.exe}")
        if not self.rom.exists():
            raise ProbeError(f"rom missing: {self.rom}")
        self.process = subprocess.Popen(
            [str(self.exe), str(self.rom)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace")
        banner = self.process.stdout.readline()
        if banner and not banner.strip().startswith("READY"):
            # The banner is informational; the probe still works.
            pass

    def close(self) -> None:
        try:
            self.process.stdin.write("quit\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()

    def __enter__(self) -> "Probe":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def command(self, text: str) -> list[str]:
        self.process.stdin.write(text + "\n")
        self.process.stdin.write("echo __PROBE_END__\n")
        self.process.stdin.flush()
        lines = []
        while True:
            line = self.process.stdout.readline()
            if not line:
                break
            line = line.rstrip("\r\n")
            if line == "__PROBE_END__":
                break
            lines.append(line)
        return lines

    def dump(self, address: int, length: int) -> bytes:
        payload = []
        collecting = False
        for line in self.command(f"dump {address} {length}"):
            if line.startswith("DUMP "):
                collecting = True
                continue
            if line == "ENDDUMP":
                break
            if collecting:
                payload.append(line)
        data = bytes.fromhex("".join(payload))
        if len(data) != length:
            raise ProbeError(
                f"dump {address:#x} returned {len(data)} of {length} bytes")
        return data

    def read_state(self, savestate: pathlib.Path) -> dict:
        """Load one savestate and read the IO, PRAM and VRAM regions."""
        self.command(f"load {savestate}")
        return {
            "io": self.dump(IO_BASE, IO_LENGTH),
            "pram": self.dump(PRAM_BASE, PRAM_LENGTH),
            "vram": self.dump(VRAM_BASE, VRAM_LENGTH),
        }


def io_registers(io_bytes: bytes) -> dict:
    """The IO registers the bench reads out of the register block.

    Register layout (plain GBA)::

        0x00 DISPCNT   0x02 (green swap)
        0x04 DISPSTAT  0x06 VCOUNT
        0x08 BG0CNT    0x0A BG1CNT   0x0C BG2CNT   0x0E BG3CNT
        0x10 BG0HOFS   0x12 BG0VOFS
        0x14 BG1HOFS   0x16 BG1VOFS
        0x18 BG2HOFS   0x1A BG2VOFS
        0x1C BG3HOFS   0x1E BG3VOFS

    ⭐ **2026-10-25（wave 20 / E3 查出，父代理修）：本函数的地址表此前是错的。**
    旧代码按 **4 字节步长**读 `0x04/0x08/0x0C` 当作 BGxCNT、按 `0x06 + 4n` 当作
    BGxHOFS ⇒ 读到的是 **DISPSTAT / VCOUNT / BG1CNT / BG3CNT**
    （E3 实测：原版侧读出 `0xD1FC`、重制侧读出 `0x30B8`，**两侧都读出同一个重复值
    ⇒ open bus，不是滚动寄存器**）。
    ⇒ **凡引用过 `bg_hofs` 的结论都建立在错寄存器上**
    （`notes/s49-fidelity/W18-PARENT-residual-structure.md` §3 锚点表、
    `W20-PARENT-wrapup.md` §4.3 的「相机/布景不在同一个位置」）。

    正确的 GBA 地址是 **2 字节步长**：BGxCNT = `0x08 + 2x`、BGxHOFS = `0x10 + 4x`、
    BGxVOFS = `0x12 + 4x`。

    Two measured limitations of the headless debugger's IO read are baked in
    here:

    * the registers from 0x10 upwards are answered with a **per frame
      constant filler** instead of the register value (measured: the original
      returns the same word for 0x10..0x3E in every frame, and that word
      changes from frame to frame).  **E3 re-measured this on the corrected
      address map and it still holds**: with the right addresses every BG's
      HOFS/VOFS reads back as the *same* filler word (original `0xD1FC`,
      remake `0x30B8`) ⇒ **the horizontal scroll is not observable through
      this debugger at all** ⇒ ``bg_hofs`` is kept for backwards compatibility
      but it is **not** a camera reading; ``bg_hofs_readable`` says so.
    * a background scroll register is **9 bits** of hardware; the game may
      have written more, so the values are masked.  The raw values are kept
      next to the masked ones so a reader can see when the raw word was
      wider than the register.
    """
    values = struct.unpack_from("<32H", io_bytes)
    # 2-byte stride: BGxCNT = 0x08 + 2x, BGxHOFS = 0x10 + 4x, BGxVOFS = 0x12 + 4x.
    raw_hofs = [values[0x10 // 2 + 4 * index] for index in range(3)]
    raw_vofs = [values[0x12 // 2 + 4 * index] for index in range(3)]
    # the filler region reads back the same word for every scroll register
    readable = len(set(raw_hofs + raw_vofs)) > 1
    return {
        "dispcnt": values[0x00 // 2],
        "bg_cnt": [values[0x08 // 2 + index] for index in range(4)],
        "bg_hofs_raw": raw_hofs,
        "bg_hofs": [value & SCROLL_MASK for value in raw_hofs],
        "bg_vofs_raw": raw_vofs,
        "bg_vofs": [value & SCROLL_MASK for value in raw_vofs],
        "bg_hofs_readable": readable,
    }



def pram_is_black(pram: bytes) -> bool:
    """True when every palette entry is black (the whole screen is blank)."""
    return all(byte == 0 for byte in pram)
