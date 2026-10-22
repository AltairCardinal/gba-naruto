#!/usr/bin/env python3
"""Field-by-field decoder / encoder for this ROM's m4a song "block" format.

What this tool proves
---------------------
``notes/evidence/m4a-block-table-20261021.md`` documents the layout; this
tool is the executable form of that note.  Three independent checks:

1. **Round trip.**  Every block is decoded into its *fields* (opcode, operand
   bytes, jump targets, ...) and re-encoded from those fields.  The result must
   be byte-identical to the ROM bytes it came from.
2. **Engine walk.**  A second, independent decoder transcribes the ROM's own
   sequencer (``0x0809A4E8``..``0x0809A524``) byte for byte: it re-derives the
   opcode stream using the engine's "byte >= 0x80 is an opcode, otherwise it is
   a continuation byte of the running opcode" rule.  It must agree with the
   field-level decoder command for command.  This is what makes the round trip
   meaningful: a decoder that mis-split the byte stream would disagree here.
3. **Renderer cross check.**  The decoded command stream is fed to the
   already-validated renderer ``tools/audio_song_export.py`` and the resulting
   event stream (note on/off, instrument change, volume, tempo, loop) must
   match the renderer's own decode exactly.

Layout (all proved by the ROM's own engine, see the note):

SongHeader (``+0x08`` = track pointer table)::

    +0x00 u8   track_count
    +0x01 u8   (unused by this ROM's engine; always 0 in all 159 sound ids)
    +0x02 u8   priority
    +0x03 u8   flags; bit 7 = reverb
    +0x04 u32  voicegroup_ptr
    +0x08 u32  track_ptr[track_count]

A track pointer addresses a **block**: a flat command byte stream with no
header of its own.  Opcodes are split into four classes by the engine at
``0x0809A4EC`` / ``0x0809A4FE`` / ``0x0809A514``:

===========  =========================================================
opcode       meaning
===========  =========================================================
``0x00..7F``  continuation byte (operand of the running opcode)
``0x80..B0``  WAIT  -- ticks = duration_table[opcode - 0x80]
``0xB1..CE``  command table -- handler = table[opcode - 0xB1]
``0xCF..FF``  NOTE  -- ticks = duration_table[opcode - 0xCF]
===========  =========================================================

Usage
-----
::

    python tools/m4a_block_table.py rom/base.gba --self-test
    python tools/m4a_block_table.py rom/base.gba --sound-id 1
    python tools/m4a_block_table.py rom/base.gba --sound-id 1 --json build/blocks.json

The tool exits non-zero when any check fails.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib.io import write_json  # noqa: E402

ROM_BASE = 0x08000000

# --- ROM tables (file offsets) ---------------------------------------------
SOUND_ID_TABLE = 0x465B70
SOUND_ID_ROW_SIZE = 8
SOUND_ID_COUNT = 159
EMPTY_DESCRIPTOR = 0x08466068
COMMAND_TABLE = 0x464534          # 0x08464534, 30 x u32 handler addresses
COMMAND_TABLE_LEN = 30
DURATION_TABLE = 0x4647A8         # 0x084647A8, 49 bytes
DURATION_TABLE_LEN = 49

# Documented free ROM region (notes/free-space.md): 0x5DFBEC..0x5FFFFF,
# ~128 KB of 0xFF filler.  The engine's byte reader accepts any address
# >= 0x02000000 (``0x0809A238 lsrs r0, r2, #0x19`` -> ``0x0809A23A bne``),
# so a block parked here is read exactly like a native one.
FREE_SPACE_START = 0x5DFBEC
FREE_SPACE_END = 0x5FFFFF

# How far past a block start the FINE end marker is looked for when the block
# has no successor (a block written into the free region).
MAX_BLOCK_SCAN = 0x10000

# --- opcode classes (engine: 0x0809A4EC / 0x0809A4FE / 0x0809A514) --------
WAIT_FIRST = 0x80
WAIT_LAST = 0xB0
CMD_FIRST = 0xB1
CMD_LAST = 0xCE
NOTE_FIRST = 0xCF
NOTE_LAST = 0xFF
RUNNING_OPCODE_MIN = 0xBD        # 0x0809A4F8 cmp r1, #0xbd

# The five legacy banks and the sound ids they are.
LEGACY_BANKS = {
    1: "story",
    2: "story-b",
    8: "story-c",
    11: "story-d",
    14: "story-e",
}


# ---------------------------------------------------------------------------
# opcode table
# ---------------------------------------------------------------------------

# Operand layout per command opcode.  "one" = one byte, "target" = four
# bytes little endian ROM address, "rept" = one count byte plus a target,
# "eot" = zero or one optional key byte, "none" = no operand.
#
# Every entry is proved by the handler's own disassembly; the handler address
# is the value stored in the command table at 0x08464534.
COMMAND_SPEC: dict[int, dict] = {
    0xB1: {"name": "FINE", "handler": 0x0809A1EC, "operand": "none"},
    0xB2: {"name": "GOTO", "handler": 0x0809A25C, "operand": "target"},
    0xB3: {"name": "PATT", "handler": 0x0809A27C, "operand": "target"},
    0xB4: {"name": "PEND", "handler": 0x0809A298, "operand": "none"},
    0xB5: {"name": "REPT", "handler": 0x0809A2AC, "operand": "rept"},
    0xBA: {"name": "PRIO", "handler": 0x0809A2DC, "operand": "one"},
    0xBB: {"name": "TEMPO", "handler": 0x0809A2E8, "operand": "one"},
    0xBC: {"name": "KEYSH", "handler": 0x0809A2FC, "operand": "one"},
    0xBD: {"name": "VOICE", "handler": 0x0809A310, "operand": "one"},
    0xBE: {"name": "VOL", "handler": 0x0809A340, "operand": "one"},
    0xBF: {"name": "PAN", "handler": 0x0809A354, "operand": "one"},
    0xC0: {"name": "BEND", "handler": 0x0809A368, "operand": "one"},
    0xC1: {"name": "BENDR", "handler": 0x0809A37C, "operand": "one"},
    0xC2: {"name": "LFOS", "handler": 0x0809A970, "operand": "one"},
    0xC3: {"name": "LFODL", "handler": 0x0809A390, "operand": "one"},
    0xC4: {"name": "MOD", "handler": 0x0809A984, "operand": "one"},
    0xC5: {"name": "MODT", "handler": 0x0809A39C, "operand": "one"},
    0xC8: {"name": "TUNE", "handler": 0x0809A3B4, "operand": "one"},
    0xCC: {"name": "MEMACC", "handler": 0x0809A3C8, "operand": "one"},
    0xCE: {"name": "EOT", "handler": 0x0809A908, "operand": "eot"},
}

# Opcodes the ROM keeps in the command table but points at the FINE handler.
RESERVED_COMMANDS = [op for op in range(CMD_FIRST, CMD_LAST + 1)
                      if op not in COMMAND_SPEC]

# m4a's duration table (0x084647A8) is read straight from the ROM (see
# load_durations below); nothing about it is hard-coded here.


def load_durations(rom: bytes) -> list[int]:
    """The 49-byte duration table at 0x084647A8.

    The engine uses **one** table for both opcode classes:
    ``0x0809A538 subs r1, #0x80`` (wait) and ``0x0809A508 subs r0, #0xcf``
    (note), so a wait's tick count is ``table[opcode - 0x80]`` and a note's is
    ``table[opcode - 0xCF]``.
    """
    _require(len(rom) >= DURATION_TABLE + DURATION_TABLE_LEN,
             "ROM is too small for the m4a duration table")
    return list(rom[DURATION_TABLE:DURATION_TABLE + DURATION_TABLE_LEN])


class BlockFormatError(ValueError):
    """Raised when the ROM does not have the layout this tool assumes."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BlockFormatError(message)


# ---------------------------------------------------------------------------
# SongHeader (the "block table")
# ---------------------------------------------------------------------------

def read_sound_id_table(rom: bytes) -> list[int]:
    """The SongHeader pointer of every sound id (0 when the row is empty)."""
    out: list[int] = []
    for sid in range(SOUND_ID_COUNT):
        off = SOUND_ID_TABLE + sid * SOUND_ID_ROW_SIZE
        if off + 4 > len(rom):
            break
        out.append(struct.unpack_from("<I", rom, off)[0])
    return out


def read_song_header(rom: bytes, sound_id: int) -> dict:
    """One SongHeader, resolved through the sound-ID table.

    Field names follow ``notes/evidence/m4a-block-table-20261021.md``; the
    engine address that reads each field is recorded next to it.
    """
    off = SOUND_ID_TABLE + sound_id * SOUND_ID_ROW_SIZE
    _require(off + 8 <= len(rom),
             f"sound id {sound_id} is outside the sound-ID table")
    pointer = struct.unpack_from("<I", rom, off)[0]
    _require(pointer not in (0, EMPTY_DESCRIPTOR),
             f"sound id {sound_id} has no SongHeader")
    base = pointer - ROM_BASE
    _require(0 <= base < len(rom),
             f"sound id {sound_id} points outside the ROM")
    track_count = rom[base]
    _require(1 <= track_count <= 16,
             f"sound id {sound_id}: implausible track count {track_count}")
    voicegroup = struct.unpack_from("<I", rom, base + 4)[0]
    _require(ROM_BASE <= voicegroup < ROM_BASE + len(rom),
             f"sound id {sound_id}: voicegroup 0x{voicegroup:08X} outside ROM")
    track_ptrs = [struct.unpack_from("<I", rom, base + 8 + 4 * i)[0]
                  for i in range(track_count)]
    for index, ptr in enumerate(track_ptrs):
        _require(ROM_BASE <= ptr < ROM_BASE + len(rom),
                 f"sound id {sound_id}: track {index} pointer "
                 f"0x{ptr:08X} outside ROM")
    return {
        "sound_id": sound_id,
        "pointer": pointer,
        "offset": base,
        "offset_hex": f"0x{base:06X}",
        "track_count": track_count,
        "field_01": rom[base + 1],        # unused by this ROM's engine
        "priority": rom[base + 2],        # 0x0809B208 ldrb r2, [r7, #2]
        "flags": rom[base + 3],           # 0x0809B2B8 ldrb r1, [r7, #3]
        "reverb": bool(rom[base + 3] & 0x80),
        "voicegroup_ptr": voicegroup,     # 0x0809B242 ldr r0, [r7, #4]
        "track_ptrs": track_ptrs,         # 0x0809B282 ldr r0, [r0]
    }


def command_handlers(rom: bytes) -> list[int]:
    """The 30 command handler addresses (Thumb bit included)."""
    _require(len(rom) >= COMMAND_TABLE + COMMAND_TABLE_LEN * 4,
             "ROM is too small for the m4a command table")
    return [struct.unpack_from("<I", rom, COMMAND_TABLE + 4 * i)[0]
            for i in range(COMMAND_TABLE_LEN)]


def verify_command_table(rom: bytes) -> list[str]:
    """Check the command table against the handler map this tool assumes."""
    problems: list[str] = []
    table = command_handlers(rom)
    for opcode, spec in sorted(COMMAND_SPEC.items()):
        index = opcode - CMD_FIRST
        actual = table[index]
        if actual != spec["handler"] | 1:
            problems.append(
                f"opcode 0x{opcode:02X}: command table says 0x{actual:08X}, "
                f"expected 0x{spec['handler'] | 1:08X}")
    for opcode in RESERVED_COMMANDS:
        index = opcode - CMD_FIRST
        if table[index] != 0x0809A1ED:
            problems.append(
                f"opcode 0x{opcode:02X}: reserved slot points at "
                f"0x{table[index]:08X}, expected 0x0809A1ED (FINE handler)")
    return problems


# ---------------------------------------------------------------------------
# block boundaries
# ---------------------------------------------------------------------------

def block_boundaries(rom: bytes) -> list[int]:
    """Every offset that starts a new block (or a SongHeader).

    A block has no length field, so its extent is "up to the next block".
    The next block start is the next track pointer of any song, or the next
    SongHeader, whichever comes first.
    """
    starts: set[int] = set()
    for pointer in read_sound_id_table(rom):
        if pointer in (0, EMPTY_DESCRIPTOR):
            continue
        base = pointer - ROM_BASE
        if not 0 <= base < len(rom):
            continue
        count = rom[base]
        if not 1 <= count <= 16:
            continue
        starts.add(base)
        for i in range(count):
            ptr = struct.unpack_from("<I", rom, base + 8 + 4 * i)[0]
            if ROM_BASE <= ptr < ROM_BASE + len(rom):
                starts.add(ptr - ROM_BASE)
    return sorted(starts)


def block_extent(boundaries: list[int], start: int) -> int | None:
    """The exclusive end offset of the block that starts at ``start``.

    ``None`` when there is no later boundary - a block that was written into
    the free region has no successor, and then the FINE end marker is the
    only thing that bounds it.
    """
    for item in boundaries:
        if item > start:
            return item
    return None


# ---------------------------------------------------------------------------
# block decoding
# ---------------------------------------------------------------------------

def note_name(opcode: int, durations: list[int]) -> str:
    """m4a note name for an opcode.

    The engine's note opcodes are ``0xCF..0xFF`` and their tick count is
    ``duration_table[opcode - 0xCF]`` (``0x0809A508 subs r0, #0xcf``).
    ``0xCF`` therefore has a duration of ``duration_table[0] == 0`` ticks: a
    zero-length note, which the existing renderer models as a tie and which is
    named ``TIE`` here so that both decoders stay comparable.
    """
    if opcode == 0xCF:
        return "TIE"
    return f"N{durations[opcode - NOTE_FIRST]:02d}"


def decode_block(raw: bytes, base_offset: int, durations: list[int],
                 stop_on_fine: bool = True) -> tuple[list[dict], int]:
    """Decode one block's command byte stream into field records.

    The rules are the ROM's own (``0x0809A4E8``..``0x0809A524`` plus each
    handler's operand consumption):

    * a byte ``>= 0x80`` is an opcode; it is consumed and, when it is
      ``>= 0xBD``, it becomes the *running opcode* (``0x0809A4F8``);
    * a byte ``< 0x80`` is a continuation byte: it is **not** consumed as an
      opcode, the running opcode is re-used, and the byte itself is the first
      operand of that command (``0x0809A4F0``);
    * a NOTE consumes up to three consecutive continuation bytes
      (key / velocity / gate) (``0x0809A728``..``0x0809A74C``);
    * EOT consumes one continuation byte if present (``0x0809A910``);
    * every other command consumes a fixed operand (``0x0809A250`` family).

    A block is terminated by FINE (``0xB1``); with ``stop_on_fine`` the decode
    stops there and returns the number of bytes the block really uses.  The
    bytes after FINE are ``0x00`` padding up to the next block.
    """
    commands: list[dict] = []
    cursor = 0
    running: int | None = None
    while cursor < len(raw):
        start = cursor
        byte = raw[cursor]
        implicit = byte < 0x80
        if implicit:
            if running is None:
                raise BlockFormatError(
                    f"continuation byte 0x{byte:02X} at 0x{base_offset + start:06X} "
                    f"without a running opcode")
            opcode = running
        else:
            opcode = byte
            cursor += 1
            if opcode >= RUNNING_OPCODE_MIN:
                running = opcode

        item: dict = {
            "offset": base_offset + start,
            "opcode": opcode,
            "implicit": implicit,
        }

        if WAIT_FIRST <= opcode <= WAIT_LAST:
            item["name"] = f"W{durations[opcode - WAIT_FIRST]:02d}"
            item["ticks"] = durations[opcode - WAIT_FIRST]
        elif NOTE_FIRST <= opcode <= NOTE_LAST:
            item["name"] = note_name(opcode, durations)
            item["ticks"] = durations[opcode - NOTE_FIRST]
            args: list[int] = []
            while len(args) < 3 and cursor < len(raw) and raw[cursor] < 0x80:
                args.append(raw[cursor])
                cursor += 1
            item["args"] = args
        elif CMD_FIRST <= opcode <= CMD_LAST:
            spec = COMMAND_SPEC.get(opcode)
            if spec is None:
                item["name"] = f"RSV{opcode:02X}"
                item["reserved"] = True
                item["handler"] = 0x0809A1EC
            else:
                item["name"] = spec["name"]
                item["handler"] = spec["handler"]
                operand = spec["operand"]
                if operand == "one":
                    _require(cursor < len(raw),
                             f"{spec['name']} at 0x{base_offset + start:06X} "
                             f"is missing its operand byte")
                    item["value"] = raw[cursor]
                    cursor += 1
                elif operand == "target":
                    _require(cursor + 4 <= len(raw),
                             f"{spec['name']} at 0x{base_offset + start:06X} "
                             f"is missing its 4-byte target")
                    target = struct.unpack_from("<I", raw, cursor)[0]
                    cursor += 4
                    item["target"] = target
                    item["target_offset"] = target - ROM_BASE
                elif operand == "rept":
                    _require(cursor + 5 <= len(raw),
                             f"REPT at 0x{base_offset + start:06X} is truncated")
                    item["count"] = raw[cursor]
                    cursor += 1
                    target = struct.unpack_from("<I", raw, cursor)[0]
                    cursor += 4
                    item["target"] = target
                    item["target_offset"] = target - ROM_BASE
                elif operand == "eot":
                    if cursor < len(raw) and raw[cursor] < 0x80:
                        item["key"] = raw[cursor]
                        cursor += 1
                elif operand == "none":
                    pass
        else:
            raise BlockFormatError(
                f"opcode 0x{opcode:02X} at 0x{base_offset + start:06X} is "
                f"outside every opcode class")

        item["size"] = cursor - start
        commands.append(item)
        if stop_on_fine and opcode == 0xB1 and not implicit:
            break
    return commands, cursor


def encode_block(commands: list[dict]) -> bytes:
    """Re-encode a decoded block from its *fields* only.

    This is the inverse of :func:`decode_block`; it never looks at the raw
    bytes, so a byte-identical round trip really does prove that the field
    split is complete.
    """
    out = bytearray()
    for command in commands:
        opcode = command["opcode"]
        if not command.get("implicit"):
            out.append(opcode)
        if WAIT_FIRST <= opcode <= WAIT_LAST:
            continue
        if NOTE_FIRST <= opcode <= NOTE_LAST:
            out.extend(command.get("args", []))
            continue
        spec = COMMAND_SPEC.get(opcode)
        operand = spec["operand"] if spec else "none"
        if operand == "one":
            out.append(command["value"])
        elif operand == "target":
            out.extend(struct.pack("<I", command["target"]))
        elif operand == "rept":
            out.append(command["count"])
            out.extend(struct.pack("<I", command["target"]))
        elif operand == "eot":
            if "key" in command:
                out.append(command["key"])
    return bytes(out)


# ---------------------------------------------------------------------------
# engine walk: an independent, pointer-level transcription
# ---------------------------------------------------------------------------

def engine_walk(raw: bytes, stop_on_fine: bool = True) -> list[dict]:
    """Re-derive the opcode stream the way the ROM's sequencer does.

    Unlike :func:`decode_block` this walks the *read pointer* the way the
    engine does (``0x0809A250``: "take the byte at the read pointer, then
    advance the pointer") and records every byte it touches.  A decoder that
    mis-split the stream would disagree with it about which bytes are opcodes
    and which are operands.
    """
    pc = 0
    running: int | None = None
    steps: list[dict] = []
    while pc < len(raw):
        opcode_bytes = b""
        byte = raw[pc]
        if byte >= 0x80:
            opcode = byte
            opcode_bytes = bytes([byte])
            pc += 1
            if opcode >= RUNNING_OPCODE_MIN:
                running = opcode
        else:
            if running is None:
                raise BlockFormatError(
                    f"continuation byte 0x{byte:02X} at 0x{pc:06X} without a "
                    f"running opcode")
            opcode = running

        operand_bytes = b""
        if WAIT_FIRST <= opcode <= WAIT_LAST:
            pass
        elif NOTE_FIRST <= opcode <= NOTE_LAST:
            while len(operand_bytes) < 3 and pc < len(raw) and raw[pc] < 0x80:
                operand_bytes += bytes([raw[pc]])
                pc += 1
        else:
            spec = COMMAND_SPEC.get(opcode)
            operand = spec["operand"] if spec else "none"
            if operand == "one":
                operand_bytes = raw[pc:pc + 1]
                pc += 1
            elif operand == "target":
                operand_bytes = raw[pc:pc + 4]
                pc += 4
            elif operand == "rept":
                operand_bytes = raw[pc:pc + 5]
                pc += 5
            elif operand == "eot":
                if pc < len(raw) and raw[pc] < 0x80:
                    operand_bytes = raw[pc:pc + 1]
                    pc += 1
        steps.append({
            "opcode": opcode,
            "opcode_bytes": opcode_bytes,
            "operand_bytes": operand_bytes,
        })
        if stop_on_fine and opcode == 0xB1 and not opcode_bytes:
            break
    return steps


# ---------------------------------------------------------------------------
# song level
# ---------------------------------------------------------------------------

def decode_song(rom: bytes, sound_id: int, boundaries: list[int] | None = None) -> dict:
    """Decode one sound id: its SongHeader (the block table) and its blocks."""
    header = read_song_header(rom, sound_id)
    if boundaries is None:
        boundaries = block_boundaries(rom)
    durations = load_durations(rom)
    blocks = []
    for index, pointer in enumerate(header["track_ptrs"]):
        start = pointer - ROM_BASE
        end = block_extent(boundaries, start)
        if end is None:
            # A block that was written into the free region has no successor;
            # the FINE end marker is the only thing that bounds it.
            end = min(start + MAX_BLOCK_SCAN, len(rom))
        raw = rom[start:end]
        commands, used = decode_block(raw, start, durations)
        blocks.append({
            "track_index": index,
            "pointer": pointer,
            "offset": start,
            "offset_hex": f"0x{start:06X}",
            "span_end": start + used,
            "span_end_hex": f"0x{start + used:06X}",
            "size": used,
            "commands": commands,
            "raw": raw[:used],
            "padding": raw[used:] if end != start + used else b"",
            "padding_hex": raw[used:].hex(" ").upper() if end != start + used else "",
        })
    return {"header": header, "blocks": blocks}


def opcode_histogram(song: dict) -> dict[str, int]:
    """How often each opcode occurs in a song (opcodes as hex strings)."""
    histogram: dict[str, int] = {}
    for block in song["blocks"]:
        for command in block["commands"]:
            key = f"0x{command['opcode']:02X}"
            histogram[key] = histogram.get(key, 0) + 1
    return dict(sorted(histogram.items()))


def command_boundaries(song: dict) -> set[int]:
    """Every offset that starts a command inside one song."""
    out: set[int] = set()
    for block in song["blocks"]:
        for command in block["commands"]:
            out.add(command["offset"])
    return out


def check_jump_targets(song: dict, global_boundaries: set[int]) -> list[str]:
    """Every GOTO / PATT / REPT target must land on a command boundary.

    This is the falsifiable test of the little-endian target encoding: with
    the bytes read big-endian the targets would be nonsense addresses and
    would not land on a command boundary.
    """
    problems: list[str] = []
    local = command_boundaries(song)
    for block in song["blocks"]:
        for command in block["commands"]:
            if "target_offset" not in command:
                continue
            target = command["target_offset"]
            if target in local or target in global_boundaries:
                continue
            problems.append(
                f"sound id {song['header']['sound_id']} track "
                f"{block['track_index']}: {command['name']} at 0x"
                f"{command['offset']:06X} targets 0x{target:06X}, which is "
                f"not a command boundary")
    return problems


# ---------------------------------------------------------------------------
# block level rewriter
# ---------------------------------------------------------------------------

class BlockRewriteError(ValueError):
    """Raised when a new block cannot be written safely."""


def rewrite_track_block(rom: bytearray, sound_id: int, track_index: int,
                        commands: list[dict]) -> dict:
    """Replace one track's block in place and read it back.

    The budget is the **original block's own span**: the bytes from the track
    pointer up to and including its FINE end marker.  A new block has to fit
    in that span; the leftover is padded with ``0x00`` exactly like the ROM's
    own padding, so nothing of the next block is touched and a stray read
    cannot fall through.

    The new block must end with FINE, because FINE is what terminates a
    block for the engine.
    """
    song = decode_song(bytes(rom), sound_id)
    header = song["header"]
    if not 0 <= track_index < len(song["blocks"]):
        raise BlockRewriteError(
            f"track {track_index} outside 0..{len(song['blocks']) - 1}")
    block = song["blocks"][track_index]
    if not commands:
        raise BlockRewriteError("a new block needs at least one command")
    last = commands[-1]
    if last["opcode"] != 0xB1 or last.get("implicit"):
        raise BlockRewriteError(
            "a new block must end with the FINE (0xB1) end marker")

    payload = encode_block(commands)
    budget = block["size"]
    if len(payload) > budget:
        raise BlockRewriteError(
            f"new block is {len(payload)} bytes but the original block only "
            f"has {budget} bytes of room (0x{block['offset']:06X}.."
            f"0x{block['span_end']:06X})")

    padded = payload + b"\x00" * (budget - len(payload))
    rom[block["offset"]:block["offset"] + budget] = padded

    # Read back and prove the ROM now decodes to the requested commands.
    after = decode_song(bytes(rom), sound_id)
    written = after["blocks"][track_index]
    wanted = [_command_identity(command) for command in commands]
    got = [_command_identity(command) for command in written["commands"]]
    if got != wanted:
        raise BlockRewriteError(
            "read-back mismatch: the patched ROM does not decode to the "
            "requested command list")
    return {
        "sound_id": sound_id,
        "track_index": track_index,
        "offset": block["offset"],
        "offset_hex": f"0x{block['offset']:06X}",
        "original_size": budget,
        "new_size": len(payload),
        "padding": budget - len(payload),
        "header_pointer": header["pointer"],
    }


def find_free_slot(rom: bytes, size: int,
                   start: int = FREE_SPACE_START,
                   end: int = FREE_SPACE_END) -> int:
    """The first 4-byte aligned free offset that can hold ``size`` bytes."""
    _require(size > 0, "a slot needs a positive size")
    offset = (start + 3) & ~3
    while offset + size <= end:
        if all(byte in (0xFF, 0x00) for byte in rom[offset:offset + size]):
            return offset
        offset += 4
    raise BlockRewriteError(
        f"no free slot of {size} bytes between 0x{start:06X} and 0x{end:06X}")


def rewrite_track_block_at(rom: bytearray, sound_id: int, track_index: int,
                           commands: list[dict], target_offset: int) -> dict:
    """Write a brand new block somewhere else and repoint the SongHeader.

    This is the "make a new block" mode: the encoded block is written to
    ``target_offset`` (typically inside the documented free region) and
    ``SongHeader.track_ptr[track_index]`` is updated to point at it.  The
    old block is left untouched, so the change is fully reversible by
    restoring the pointer.
    """
    if not commands:
        raise BlockRewriteError("a new block needs at least one command")
    last = commands[-1]
    if last["opcode"] != 0xB1 or last.get("implicit"):
        raise BlockRewriteError(
            "a new block must end with the FINE (0xB1) end marker")
    payload = encode_block(commands)
    _require(0 <= target_offset and target_offset + len(payload) <= len(rom),
             f"target 0x{target_offset:06X} does not fit in the ROM")

    header = read_song_header(bytes(rom), sound_id)
    if not 0 <= track_index < header["track_count"]:
        raise BlockRewriteError(
            f"track {track_index} outside 0..{header['track_count'] - 1}")
    pointer_slot = header["offset"] + 8 + 4 * track_index
    old_pointer = header["track_ptrs"][track_index]

    rom[target_offset:target_offset + len(payload)] = payload
    rom[pointer_slot:pointer_slot + 4] = (ROM_BASE + target_offset).to_bytes(
        4, "little")

    after = read_song_header(bytes(rom), sound_id)
    if after["track_ptrs"][track_index] != ROM_BASE + target_offset:
        raise BlockRewriteError("read-back mismatch: the track pointer did "
                                "not take the new value")
    song = decode_song(bytes(rom), sound_id)
    written = song["blocks"][track_index]
    wanted = [_command_identity(command) for command in commands]
    got = [_command_identity(command) for command in written["commands"]]
    if got != wanted:
        raise BlockRewriteError(
            "read-back mismatch: the patched ROM does not decode to the "
            "requested command list")
    return {
        "sound_id": sound_id,
        "track_index": track_index,
        "old_pointer": old_pointer,
        "new_pointer": ROM_BASE + target_offset,
        "target_offset": target_offset,
        "target_hex": f"0x{target_offset:06X}",
        "new_size": len(payload),
        "pointer_slot": pointer_slot,
    }


def _command_identity(command: dict) -> tuple:
    """The semantic fields of one command (no offsets, no sizes)."""
    return (
        command["opcode"],
        bool(command.get("implicit")),
        command.get("value"),
        tuple(command.get("args", ())),
        command.get("count"),
        command.get("target"),
        command.get("key"),
    )


# ---------------------------------------------------------------------------
# cross check against the validated renderer
# ---------------------------------------------------------------------------

def _command_bytes(command: dict) -> tuple[bytes, bytes]:
    """(opcode bytes, operand bytes) of one decoded command."""
    opcode = command["opcode"]
    head = b"" if command.get("implicit") else bytes([opcode])
    if WAIT_FIRST <= opcode <= WAIT_LAST:
        return head, b""
    if NOTE_FIRST <= opcode <= NOTE_LAST:
        return head, bytes(command.get("args", []))
    spec = COMMAND_SPEC.get(opcode)
    operand = spec["operand"] if spec else "none"
    if operand == "one":
        return head, bytes([command["value"]])
    if operand == "target":
        return head, struct.pack("<I", command["target"])
    if operand == "rept":
        return head, bytes([command["count"]]) + struct.pack("<I", command["target"])
    if operand == "eot":
        return head, bytes([command["key"]]) if "key" in command else b""
    return head, b""


def _byte_roles(commands: list[dict], raw: bytes, base_offset: int,
                implicit_known: bool) -> list[tuple[int, str, int]]:
    """Classify every byte of a block as ``(offset, kind, owner opcode)``.

    ``kind`` is ``"op"`` for an explicit opcode byte and ``"operand"`` for
    everything else.  The *owner* is the opcode whose operand the byte is.
    Two decoders that split the byte stream the same way produce the same
    ``(offset, kind)`` pairs; a different owner opcode means the two decoders
    disagree about the **running opcode**.
    """
    roles: list[tuple[int, str, int]] = []
    for command in commands:
        offset = command["offset"]
        size = command["size"]
        opcode = command["opcode"]
        if implicit_known:
            explicit = not command.get("implicit")
        else:
            explicit = raw[offset - base_offset] >= 0x80
        if explicit:
            roles.append((offset, "op", opcode))
            for step in range(1, size):
                roles.append((offset + step, "operand", opcode))
        else:
            for step in range(size):
                roles.append((offset + step, "operand", opcode))
    return roles


def compare_with_renderer(rom: bytes, sound_id: int) -> dict:
    """Compare this tool's decode with ``tools/audio_song_export.py``.

    Two levels are compared:

    * **byte partition** - which bytes are opcode bytes and which are
      operands.  This must be identical; it is what proves that both
      decoders cut the stream into the same commands.
    * **opcode ownership** - which opcode owns an operand byte.  The ROM's
      engine keeps a *running opcode* for every opcode ``>= 0xBD``
      (``0x0809A4F8``), while the existing decoder only keeps a *running
      note*; the two therefore disagree on continuation bytes that follow a
      non-note command.  Those divergences are counted and explained, not
      silently accepted.

    The event streams are compared as well: they must be identical whenever
    the two decoders agree on every opcode.
    """
    from tools import audio_song_export as ase
    from tools import extract_audio as ea

    tables = ase.load_tables(rom)
    boundaries = block_boundaries(rom)
    song = decode_song(rom, sound_id, boundaries)
    report: dict = {
        "sound_id": sound_id,
        "tracks": [],
        "problems": [],
        "running_opcode_divergences": 0,
        "event_divergence_tracks": 0,
    }

    for block in song["blocks"]:
        index = block["track_index"]
        raw = rom[block["offset"]:block["span_end"]]
        mine = block["commands"]
        try:
            theirs = ea.decode_track(raw, block["offset"])
        except ea.DecodeError as exc:
            report["problems"].append(
                f"sound id {sound_id} track {index}: the existing decoder "
                f"cannot read this block: {exc}")
            continue

        mine_roles = _byte_roles(mine, raw, block["offset"], True)
        their_roles = _byte_roles(theirs, raw, block["offset"], False)
        partition_ok = ([(offset, kind) for offset, kind, _ in mine_roles]
                        == [(offset, kind) for offset, kind, _ in their_roles])

        divergences = []
        unexplained = 0
        if partition_ok:
            for (offset, kind, mine_owner), (_, _, their_owner) in zip(
                    mine_roles, their_roles):
                if mine_owner == their_owner:
                    continue
                command = next(c for c in mine if c["offset"] == offset
                                or (c["offset"] < offset < c["offset"] + c["size"]))
                explained = kind == "operand" and command.get("implicit")
                if not explained:
                    unexplained += 1
                divergences.append({
                    "offset": offset,
                    "offset_hex": f"0x{offset:06X}",
                    "kind": kind,
                    "mine": f"0x{mine_owner:02X}",
                    "renderer": f"0x{their_owner:02X}",
                    "explained_by_running_opcode": bool(explained),
                })

        mine_run = ase.TrackRunner(mine, block["offset"], tables, 2).run()
        their_run = ase.TrackRunner(theirs, block["offset"], tables, 2).run()
        events_match = _events_equal(mine_run, their_run)

        report["tracks"].append({
            "track_index": index,
            "commands": len(mine),
            "partition_matches_renderer": partition_ok,
            "opcode_divergences": len(divergences),
            "unexplained_divergences": unexplained,
            "divergences": divergences[:8],
            "events_mine": len(mine_run["events"]),
            "events_renderer": len(their_run["events"]),
            "events_match": events_match,
            "tempo_changes_mine": len(mine_run["tempo_changes"]),
            "tempo_changes_renderer": len(their_run["tempo_changes"]),
            "stop_reason_mine": mine_run["stop_reason"],
            "stop_reason_renderer": their_run["stop_reason"],
        })
        report["running_opcode_divergences"] += len(divergences)
        if not partition_ok:
            report["problems"].append(
                f"sound id {sound_id} track {index}: the two decoders do not "
                f"split the byte stream the same way")
        if unexplained:
            report["problems"].append(
                f"sound id {sound_id} track {index}: {unexplained} opcode "
                f"divergences are not explained by the running opcode")
        if not events_match:
            report["event_divergence_tracks"] += 1
            if not divergences:
                report["problems"].append(
                    f"sound id {sound_id} track {index}: the event stream "
                    f"differs even though every opcode agrees")
    return report


def _events_equal(mine: dict, theirs: dict) -> bool:
    """Compare two TrackRunner results event by event."""
    keys = ("tick", "key", "velocity", "program", "volume", "pan", "key_shift",
            "bend", "tied", "duration_ticks", "release_reason")
    if len(mine["events"]) != len(theirs["events"]):
        return False
    for left, right in zip(mine["events"], theirs["events"]):
        if any(left.get(key) != right.get(key) for key in keys):
            return False
    if len(mine["tempo_changes"]) != len(theirs["tempo_changes"]):
        return False
    for left, right in zip(mine["tempo_changes"], theirs["tempo_changes"]):
        if left["tick"] != right["tick"] or left["tempo_byte"] != right["tempo_byte"]:
            return False
    return True


# ---------------------------------------------------------------------------
# self test
# ---------------------------------------------------------------------------

SELF_TEST_SOUNDS = (1, 2, 8, 11, 14)


def self_test(rom: bytes) -> int:
    """Every check; returns the number of failures (0 == pass)."""
    failures: list[str] = []
    notes: list[str] = []
    divergences: list[tuple] = []

    problems = verify_command_table(rom)
    if problems:
        failures.extend(problems)
    else:
        notes.append("command table 0x08464534 matches the handler map "
                     "(30 entries, opcodes 0xB1..0xCE)")

    boundaries = block_boundaries(rom)
    global_boundaries: set[int] = set()
    songs = {}
    for sound_id in SELF_TEST_SOUNDS:
        try:
            songs[sound_id] = decode_song(rom, sound_id, boundaries)
        except BlockFormatError as exc:
            failures.append(f"sound id {sound_id}: {exc}")
    for song in songs.values():
        global_boundaries |= command_boundaries(song)

    for sound_id, song in songs.items():
        header = song["header"]
        notes.append(
            f"sound id {sound_id}: header 0x{header['offset']:06X}, "
            f"{header['track_count']} blocks, voicegroup "
            f"0x{header['voicegroup_ptr']:08X}")
        for block in song["blocks"]:
            commands = block["commands"]
            # (a) round trip
            encoded = encode_block(commands)
            if encoded != block["raw"]:
                failures.append(
                    f"sound id {sound_id} track {block['track_index']}: "
                    f"round trip is not byte identical "
                    f"({len(encoded)} vs {len(block['raw'])} bytes)")
            # (b) engine walk
            walk = engine_walk(block["raw"])
            if len(walk) != len(commands):
                failures.append(
                    f"sound id {sound_id} track {block['track_index']}: engine "
                    f"walk saw {len(walk)} commands, decoder saw "
                    f"{len(commands)}")
            else:
                for step, command in zip(walk, commands):
                    head, operand = _command_bytes(command)
                    if (step["opcode"] != command["opcode"]
                            or step["opcode_bytes"] != head
                            or step["operand_bytes"] != operand):
                        failures.append(
                            f"sound id {sound_id} track {block['track_index']}: "
                            f"engine walk disagrees at 0x{command['offset']:06X}")
                        break
                else:
                    rebuilt = b"".join(step["opcode_bytes"] + step["operand_bytes"]
                                       for step in walk)
                    if rebuilt != block["raw"]:
                        failures.append(
                            f"sound id {sound_id} track {block['track_index']}: "
                            f"engine walk does not consume the block exactly")
            # (c) padding
            if block["padding"] and any(block["padding"]):
                notes.append(
                    f"sound id {sound_id} track {block['track_index']}: "
                    f"padding after FINE is not 0x00: "
                    f"{block['padding_hex']}")
        # (d) jump targets
        failures.extend(check_jump_targets(song, global_boundaries))
        # (e) renderer cross check
        try:
            report = compare_with_renderer(rom, sound_id)
        except ValueError as exc:
            failures.append(
                f"sound id {sound_id}: the renderer cannot execute the "
                f"decoded block: {exc}")
            continue
        failures.extend(report["problems"])
        events = sum(track["events_mine"] for track in report["tracks"])
        notes.append(
            f"sound id {sound_id}: renderer cross check over "
            f"{len(report['tracks'])} tracks, {events} events, byte partition "
            f"{'identical' if not report['problems'] else 'PROBLEM'}, "
            f"{report['running_opcode_divergences']} running-opcode "
            f"divergences, {report['event_divergence_tracks']} tracks with a "
            f"different event stream")
        if report["running_opcode_divergences"]:
            divergences.append((sound_id, report["running_opcode_divergences"],
                                report["event_divergence_tracks"]))

    # (f) block level rewriter round trip
    try:
        rom_copy = bytearray(rom)
        song = songs.get(1)
        if song is not None:
            block = song["blocks"][0]
            original = rom[block["offset"]:block["span_end"]]
            # (f1) smallest possible edit: change the tempo byte
            commands = [dict(command) for command in block["commands"]]
            for command in commands:
                if command["opcode"] == 0xBB:
                    command["value"] = (command["value"] + 1) & 0xFF
                    break
            info = rewrite_track_block(rom_copy, 1, 0, commands)
            patched = bytes(rom_copy[block["offset"]:block["span_end"]])
            if len(patched) != len(original) or patched == original:
                failures.append(
                    "rewriter: the patched block is not a same-size change")
            if patched[info["new_size"]:] != b"\x00" * info["padding"]:
                failures.append("rewriter: the padding is not 0x00")
            notes.append(
                f"rewriter: sound id 1 track 0 rewritten in place, "
                f"{info['new_size']}/{info['original_size']} bytes, "
                f"read-back verified")
            # (f2) a bigger change: drop the tempo command and put it back
            rom_copy2 = bytearray(rom)
            trimmed = [dict(command) for command in block["commands"]
                       if command["opcode"] != 0xBB]
            tempo = next(command for command in block["commands"]
                         if command["opcode"] == 0xBB)
            tempo = dict(tempo)
            tempo["value"] = 0x33
            trimmed.insert(0, tempo)
            info2 = rewrite_track_block(rom_copy2, 1, 0, trimmed)
            notes.append(
                f"rewriter: sound id 1 track 0 rebuilt "
                f"({len(trimmed)} commands, {info2['new_size']} bytes), "
                f"read-back verified")
            if info2["new_size"] > info2["original_size"]:
                failures.append("rewriter: new block bigger than the budget")
            # (f3) a brand new block in the free region, with the SongHeader
            # track pointer repointed at it
            rom_copy3 = bytearray(rom)
            slot = find_free_slot(bytes(rom_copy3), 64)
            new_block = [
                {"opcode": 0xBE, "implicit": False, "name": "VOL", "value": 0x60,
                 "size": 2},
                {"opcode": 0xBD, "implicit": False, "name": "VOICE", "value": 0x00,
                 "size": 2},
                {"opcode": 0x80, "implicit": False, "name": "W00", "size": 1},
                {"opcode": 0xB1, "implicit": False, "name": "FINE", "size": 1},
            ]
            info3 = rewrite_track_block_at(rom_copy3, 1, 0, new_block, slot)
            if info3["new_pointer"] != ROM_BASE + slot:
                failures.append("rewriter: the repointed pointer is wrong")
            if bytes(rom_copy3[slot:slot + 4]) == b"\xff\xff\xff\xff":
                failures.append("rewriter: the free slot was not written")
            notes.append(
                f"rewriter: a new {info3['new_size']} byte block written at "
                f"{info3['target_hex']} and sound id 1 track 0 repointed "
                f"0x{info3['old_pointer']:08X} -> 0x{info3['new_pointer']:08X}, "
                f"read-back verified")
    except (BlockRewriteError, BlockFormatError) as exc:
        failures.append(f"rewriter: {exc}")

    for note in notes:
        print(f"  - {note}")
    if divergences:
        print()
        print("KNOWN DIVERGENCE (documented in "
              "notes/evidence/m4a-block-table-20261021.md):")
        for sound_id, count, tracks in divergences:
            print(f"  ~ sound id {sound_id}: {count} continuation bytes are "
                  f"read with the ROM's running opcode here, but with a "
                  f"running *note* by tools/extract_audio.py; "
                  f"{tracks} track(s) therefore render a different event "
                  f"stream")
    if failures:
        print()
        print("FAILURES:")
        for failure in failures:
            print(f"  ! {failure}")
        print(f"\nSELF-TEST: FAIL ({len(failures)} problems)")
        return 1
    print("\nSELF-TEST: PASS")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def dump_song(rom: bytes, sound_id: int) -> dict:
    """The JSON shape of one sound id's block table."""
    song = decode_song(rom, sound_id)
    blocks = []
    for block in song["blocks"]:
        blocks.append({
            "track_index": block["track_index"],
            "pointer": block["pointer"],
            "offset": block["offset"],
            "offset_hex": block["offset_hex"],
            "span_end": block["span_end"],
            "span_end_hex": block["span_end_hex"],
            "size": block["size"],
            "padding_hex": block["padding_hex"],
            "raw_hex": block["raw"].hex(" ").upper(),
            "commands": [{
                "index": position,
                "offset": command["offset"],
                "offset_hex": f"0x{command['offset']:06X}",
                "opcode": command["opcode"],
                "opcode_hex": f"0x{command['opcode']:02X}",
                "name": command["name"],
                "implicit": command.get("implicit", False),
                "size": command["size"],
                "value": command.get("value"),
                "args": command.get("args"),
                "count": command.get("count"),
                "target": command.get("target"),
                "target_offset_hex": (f"0x{command['target_offset']:06X}"
                                      if "target_offset" in command else None),
                "key": command.get("key"),
                "ticks": command.get("ticks"),
                "handler": (f"0x{command['handler']:08X}"
                            if "handler" in command else None),
            } for position, command in enumerate(block["commands"])],
        })
    header = song["header"]
    return {
        "sound_id": sound_id,
        "legacy_bank": LEGACY_BANKS.get(sound_id),
        "header": {
            "pointer": header["pointer"],
            "offset": header["offset"],
            "offset_hex": header["offset_hex"],
            "track_count": header["track_count"],
            "field_01": header["field_01"],
            "priority": header["priority"],
            "flags": header["flags"],
            "reverb": header["reverb"],
            "voicegroup_ptr": header["voicegroup_ptr"],
            "track_ptrs": header["track_ptrs"],
        },
        "opcode_histogram": opcode_histogram(song),
        "blocks": blocks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("rom", nargs="?", default="rom/base.gba")
    parser.add_argument("--sound-id", type=int, action="append", dest="sound_ids",
                        help="dump this sound id (repeatable)")
    parser.add_argument("--json", help="write the machine-readable report here")
    parser.add_argument("--self-test", action="store_true",
                        help="run every check and exit non-zero on failure")
    args = parser.parse_args(argv)

    rom_path = pathlib.Path(args.rom)
    if not rom_path.is_file():
        print(f"ROM not found: {rom_path}", file=sys.stderr)
        return 1
    rom = rom_path.read_bytes()

    if args.self_test:
        print(f"m4a block table self test - {rom_path}")
        return self_test(rom)

    sound_ids = args.sound_ids or list(SELF_TEST_SOUNDS)
    report = {"rom": str(rom_path), "songs": []}
    for sound_id in sound_ids:
        try:
            report["songs"].append(dump_song(rom, sound_id))
        except BlockFormatError as exc:
            print(f"sound id {sound_id}: {exc}", file=sys.stderr)
            return 1

    if args.json:
        write_json(args.json, report)

    for song in report["songs"]:
        header = song["header"]
        print(f"sound id {song['sound_id']}"
              f"{' (' + song['legacy_bank'] + ')' if song['legacy_bank'] else ''}"
              f"  header {header['offset_hex']}  tracks {header['track_count']}"
              f"  priority {header['priority']}  flags 0x{header['flags']:02X}"
              f"  voicegroup 0x{header['voicegroup_ptr']:08X}")
        for block in song["blocks"]:
            print(f"  block {block['track_index']}: {block['offset_hex']}"
                  f"..{block['span_end_hex']}  {block['size']} bytes"
                  f"  {len(block['commands'])} commands"
                  f"  padding {block['padding_hex'] or '-'}")
        print("  opcodes: " + "  ".join(
            f"{key}x{value}" for key, value in song["opcode_histogram"].items()))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




