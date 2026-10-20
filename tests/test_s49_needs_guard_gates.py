#!/usr/bin/env python3
"""Real behavioural gates for the S49-relevant ``needs_guard`` reverse notes.

``artifacts/reverse-notes-index-v1/notes-index.json`` sorts 435 reverse notes
into five buckets, and 339 of them land in ``needs_guard``: the note states an
original-ROM conclusion but nothing in this tree consumes it yet.  The P2
milestone of ``docs/butano-reverse-gap-roadmap.md`` is explicit about what
leaves that bucket -- "分类不等于消费" (classifying is not consuming).  A note
only becomes consumed when a test actually asserts its conclusion.

Every test method below pins **one** note to **one** observable value:

* the value is read out of a captured receipt that already exists in this
  tree -- the immutable base ROM (``rom/base.gba``), a captured runtime
  evidence file under ``artifacts/runtime-checkpoints/``, the S49 battle-14
  roster capture, or the reverse-results index -- never out of the note prose
  alone;
* the receipt is pinned by SHA-256, so a missing or altered receipt fails the
  test with a readable message instead of silently skipping;
* the asserted values are exact: byte ranges, ROM pointers, palette hashes,
  layer counts, glyph-slot counts, unit coordinates.

Notes that live only in the read-only reverse tree
(``/Users/altair/github/gba-naruto-reverse``) are cited with an explicit
``reverse tree:`` prefix; their conclusions are still checked against
receipts that live in *this* tree.

Rejected candidates (conclusions that are not mechanically checkable from
receipts in this tree) are listed in
``notes/s49-needs-guard-gates-20261020.md``.
"""

from __future__ import annotations

import hashlib
import json
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ROM_PATH = "rom/base.gba"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

INDEX_PATH = "artifacts/reverse-results-index-v1/index.json"

ACTION_DETAIL_RECEIPT = (
    "artifacts/runtime-checkpoints/action-detail-renderer-evidence.json"
)
ACTION_DETAIL_SHA256 = (
    "c89e91e849371c23578471534f4b0f486c3588b5b51f53b05506a5672ad35c2c"
)

PROFILE_TEXT_RECEIPT = (
    "artifacts/runtime-checkpoints/profile-text-runtime-evidence.json"
)
PROFILE_TEXT_SHA256 = (
    "552b94be0613af35642524136f631b211c47d71e113c575111154ee2a529b363"
)

VISUAL_VARIANT_RECEIPT = (
    "artifacts/runtime-checkpoints/visual-variant-runtime-evidence.json"
)
VISUAL_VARIANT_SHA256 = (
    "3abe72ddadba5a51c22b738b79dd1db59cad79a806835d97d1c517a9ceab0e9a"
)

ROSTER_POOL = "artifacts/s49-original-battle14-roster-v1/unit_pool.bin"
ROSTER_POOL_SHA256 = (
    "9d508d991fb5a454a4bfe0b9008a7627490fafe99f7aa1dca63b316a4788c2c5"
)
ROSTER_JSON = "artifacts/s49-original-battle14-roster-v1/roster.json"
ROSTER_JSON_SHA256 = (
    "b53417ce5210d1d26b12355dab71cdb1c294bc7e987c9a8246d91b47f9513809"
)

# Battle visual descriptor table (0x44 bytes per record, 79 records).
VISUAL_DESCRIPTOR_TABLE = 0x5A320C
VISUAL_DESCRIPTOR_STRIDE = 0x44
VISUAL_DESCRIPTOR_COUNT = 79
# Layer groups inside one descriptor record: (gfx, layout/object, palette).
VISUAL_LAYER_GROUPS = {
    "A": (0x0C, 0x10, 0x14),
    "B": (0x18, 0x1C, 0x20),
    "C": (0x28, 0x2C, 0x30),
    "D": (0x38, 0x3C, 0x40),
}
# Message -> glyph binding table (79 rows of 10 bytes).
VISUAL_BINDING_TABLE = 0x5A2EF4
VISUAL_BINDING_STRIDE = 10
VISUAL_BINDING_ROWS = 79
# Message pointer table (79 pointers) and LZ77 graphic pointer table (172).
VISUAL_MESSAGE_TABLE = 0x5A2B08
VISUAL_GRAPHIC_TABLE = 0x5A2C44
VISUAL_GRAPHIC_COUNT = 172
# Character x visual slot descriptor matrix (62 characters x 9 slots x 16 bytes).
CHARACTER_MATRIX = 0x596D5C
CHARACTER_MATRIX_END = 0x59903C
CHARACTER_COUNT = 62
CHARACTER_VISUAL_SLOTS = 9
# Battle scenario config table (16 records of 16 bytes).
SCENARIO_TABLE = 0x53D910
SCENARIO_STRIDE = 16
SCENARIO_COUNT = 16
# Unit pool layout.
UNIT_POOL_BASE = 0x020240C0
UNIT_POOL_STRIDE = 0x1D4
UNIT_POOL_SLOTS = 13
UNIT_POOL_X_OFFSET = 0xC4
UNIT_POOL_Y_OFFSET = 0xC5


def _require_bytes(relative: str, expected_sha256: str) -> bytes:
    """Return a receipt's bytes, failing closed when it is missing or altered."""
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError(f"missing receipt: {relative}")
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_sha256:
        raise AssertionError(
            f"receipt {relative} hash mismatch: "
            f"expected {expected_sha256}, got {actual}"
        )
    return data


def _require_rom() -> bytes:
    return _require_bytes(ROM_PATH, ROM_SHA256)


def _require_json(relative: str, expected_sha256: str):
    return json.loads(_require_bytes(relative, expected_sha256).decode("utf-8"))


def _load_index() -> dict:
    """Load the reverse-results index.

    The index is rebuilt by the release round, so it is *not* pinned by file
    hash; the artifact-family facts taken out of it are pinned by content.
    """
    path = ROOT / INDEX_PATH
    if not path.is_file():
        raise AssertionError(f"missing receipt: {INDEX_PATH}")
    return json.loads(path.read_text(encoding="utf-8"))


def _index_family(index: dict, family_id: str) -> dict:
    for entry in index.get("entries", []):
        if entry.get("kind") == "artifact" and entry.get("id") == family_id:
            return entry
    raise AssertionError(
        f"artifact family {family_id!r} is missing from {INDEX_PATH}"
    )


def _u16(record: bytes, offset: int) -> int:
    return struct.unpack_from("<H", record, offset)[0]


def _u32(record: bytes, offset: int) -> int:
    return struct.unpack_from("<I", record, offset)[0]


def _descriptor(rom: bytes, descriptor_id: int) -> bytes:
    start = VISUAL_DESCRIPTOR_TABLE + descriptor_id * VISUAL_DESCRIPTOR_STRIDE
    return rom[start : start + VISUAL_DESCRIPTOR_STRIDE]


class S49NeedsGuardGatesTest(unittest.TestCase):
    """One test method per reverse note, each pinning an observable value."""

    # ------------------------------------------------------------------
    # notes/battle-scenario-config.md
    # ------------------------------------------------------------------
    def test_battle_scenario_config_table(self) -> None:
        """notes/battle-scenario-config.md (this tree).

        Conclusion pinned: the battle scenario config table lives at ARM
        ``0x0853D910`` (file offset ``0x53D910``) as 16 records of 16 bytes
        with the layout ``+0x00 u16 tiles_x, +0x02 u16 tiles_y, +0x04 u32
        ptr1, +0x08 u32 ptr2, +0x0C u16 flag``, and S49's battle (battle id
        14) is entry 14: a 60x32 arena whose ``ptr1`` is ``0x080CD260`` and
        whose ``ptr2`` is ``0x080D0054``.

        Receipt: ``rom/base.gba`` @ sha256
        ``1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b``
        (the immutable base ROM the note names as its working ROM).

        Not pinned: the note's second table, the WRAM allocation table at
        ``0x53D848``.  Its addresses are mis-parsed -- the note reads
        ``0x02002E30`` where the ROM holds ``0x02022E30`` (it splits one
        ``u32`` into two ``u16`` and mistakes the high half for a size), and
        its sizes are shifted by one field.  The corrected reading is pinned
        by ``test_first_battle_savestate_unit_pool_layout`` instead.
        """
        rom = _require_rom()

        # The note's stated table range end, 0x0853D9F0, is the start of
        # entry 14 -- i.e. the S49 record -- not the end of the 16 records.
        self.assertEqual(SCENARIO_TABLE + 14 * SCENARIO_STRIDE, 0x53D9F0)

        rows = {
            0: (92, 64, 0x080B9F80, 0x080BD608, 0xD70C),
            1: (None, None, 0x080BE10C, 0x080BF250, 0x0001),
            2: (60, 30, 0x080BF318, 0x080C166C, 0x1710),
            3: (None, None, 0x080C18EC, 0x080C1CAC, 0x0001),
            4: (36, 36, 0x080C1CF8, 0x080C416C, 0x4210),
            5: (None, None, 0x080C43E4, 0x080C4844, 0x0001),
            6: (36, 40, 0x080C4880, 0x080C5F24, 0x5FC8),
            7: (None, None, 0x080C6140, 0x080C6410, 0x0001),
            8: (36, 40, 0x080C6450, 0x080C8454, 0x84F8),
            9: (None, None, 0x080C86D8, 0x080C8ABC, 0x0001),
            10: (36, 46, 0x080C8AF4, 0x080CAA94, 0xAB30),
            11: (None, None, 0x080CAD38, 0x080CB138, 0x0001),
            12: (60, 32, 0x080CB18C, 0x080CCB54, 0xCC28),
            13: (None, None, 0x080CCE1C, 0x080CD21C, 0x0002),
            14: (60, 32, 0x080CD260, 0x080D0054, 0x0154),
            15: (None, None, 0x080D0638, 0x080D1238, 0x0102),
        }
        self.assertEqual(len(rows), SCENARIO_COUNT)
        for index, expected in rows.items():
            tiles_x, tiles_y, ptr1, ptr2, flag = expected
            start = SCENARIO_TABLE + index * SCENARIO_STRIDE
            record = rom[start : start + SCENARIO_STRIDE]
            self.assertEqual(len(record), SCENARIO_STRIDE)
            self.assertEqual(_u32(record, 4), ptr1, f"entry {index} ptr1")
            self.assertEqual(_u32(record, 8), ptr2, f"entry {index} ptr2")
            self.assertEqual(_u16(record, 12), flag, f"entry {index} flag")
            if tiles_x is None:
                # The note marks the odd entries "(invalid)": their tile
                # dimensions are not a usable arena size.
                self.assertNotIn(
                    _u16(record, 0), (92, 60, 36), f"entry {index} tiles_x"
                )
            else:
                self.assertEqual(_u16(record, 0), tiles_x, f"entry {index} tiles_x")
                self.assertEqual(_u16(record, 2), tiles_y, f"entry {index} tiles_y")

        # S49 is battle 14 -> entry 14: 60x32 tiles, the note's pointers.
        s49 = rows[14]
        self.assertEqual((s49[0], s49[1]), (60, 32))
        self.assertEqual(s49[2], 0x080CD260)
        self.assertEqual(s49[3], 0x080D0054)

    # ------------------------------------------------------------------
    # notes/battle-action-detail-renderer-20260713.md
    # ------------------------------------------------------------------
    def test_battle_action_detail_renderer_trace(self) -> None:
        """notes/battle-action-detail-renderer-20260713.md (this tree).

        Conclusion pinned: the action detail page renderer is ``0x080708BC``
        and it branches on action id bit 7 -- bit 7 clear means the low seven
        bits are a *battle effect* id (``0x080708F0 -> 0x0806D85C``), bit 7 set
        means they are a skill id (``0x08070906 -> 0x0806D910``).  The
        tutorial's "忍者组合拳" therefore passes ``effect_id = 2`` and **not**
        ``skill_id = 2``, which is why the skill-initializer probe never hit.

        Receipt: ``artifacts/runtime-checkpoints/action-detail-renderer-evidence.json``
        @ sha256
        ``c89e91e849371c23578471534f4b0f486c3588b5b51f53b05506a5672ad35c2c``.

        The writer trace is pinned too: the tilemap writer was hit 4 times
        (first ``0x08066E92``/panel 4, last ``0x0806ED9E``/panel 0), the
        numeric writer twice (``0x080710AA -> 80``, ``0x080710C4 -> 5``, the
        bottom HP/chakra HUD rather than the detail numbers) and the text
        writer 10 times inside ``0x08070922..0x08071222``.
        """
        receipt = _require_json(ACTION_DETAIL_RECEIPT, ACTION_DETAIL_SHA256)

        self.assertEqual(receipt["detail_renderer"], "0x080708BC")
        self.assertEqual(
            receipt["branches"]["effect"],
            "0x080708F0 -> 0x0806D85C when action_id bit 7 is clear",
        )
        self.assertEqual(
            receipt["branches"]["skill"],
            "0x08070906 -> 0x0806D910 when action_id bit 7 is set",
        )

        observed = receipt["observed_tutorial_action"]
        self.assertEqual(observed["label"], "忍者组合拳")
        self.assertEqual(observed["action_id"], 2)
        self.assertEqual(observed["classification"], "battle effect, not skill")

        tilemap = receipt["writer_traces"]["tilemap"]
        self.assertEqual(tilemap["hit_count"], 4)
        self.assertEqual(tilemap["first_call_site"], "0x08066E92")
        self.assertEqual(tilemap["first_panel_id"], 4)
        self.assertEqual(tilemap["last_call_site"], "0x0806ED9E")
        self.assertEqual(tilemap["last_panel_id"], 0)

        numeric = receipt["writer_traces"]["numeric"]
        self.assertEqual(
            [(call["call_site"], call["value"]) for call in numeric["calls"]],
            [("0x080710AA", 80), ("0x080710C4", 5)],
        )
        self.assertEqual(numeric["interpretation"], "bottom HUD HP/chakra, not detail values")

        text = receipt["writer_traces"]["text"]
        self.assertEqual(text["hit_count"], 10)
        self.assertEqual(text["call_range"], "0x08070922..0x08071222")

        forced = receipt["forced_skill_diagnostic"]
        self.assertEqual(forced["skill_id"], 2)
        self.assertEqual(forced["level_context"], "0x02024294")
        self.assertEqual(forced["destination"], "0x02026B80")
        control = forced["control_output_hex"]
        variant = forced["variant_output_hex"]
        self.assertEqual(control, "0501010206035a830200000000000000")
        self.assertEqual(variant, "0501010207035a830200000000000000")
        # Only the source record's +4 field changes: 6 -> 7 in the runtime block.
        self.assertEqual(control[:8], variant[:8])
        self.assertEqual(control[8:10], "06")
        self.assertEqual(variant[8:10], "07")
        self.assertEqual(control[10:], variant[10:])
        self.assertNotEqual(
            forced["control_scratch_sha256"], forced["variant_scratch_sha256"]
        )

    # ------------------------------------------------------------------
    # notes/battle-status-bars-export-20260730.md
    # ------------------------------------------------------------------
    def test_battle_status_bar_generator_code_slice(self) -> None:
        """notes/battle-status-bars-export-20260730.md (reverse tree:
        ``notes/battle-status-bars-export-20260730.md``).

        Conclusion pinned: the battle status bars are not static ROM art --
        they are generated at runtime by the code object at ``0x08068370``.
        The note records two exact code hashes: the generator body
        ``[0x08068370, 0x08068642)`` (722 bytes) and the same object including
        its trailing literal pool ``[0x08068370, 0x08068660)`` (752 bytes).

        Receipt: ``rom/base.gba`` @ sha256
        ``1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b``
        for the code slices, plus ``artifacts/reverse-results-index-v1/index.json``
        for the artifact-family manifest hash the note points at.

        Not pinned: the note's "exactly four direct call sites"
        (``0x0806F0D6``/``0x0806F0EC``/``0x0807A83C``/``0x0807A8A6``) and the
        30-checkpoint runtime route -- those need a Thumb/ARM call-graph
        decode that this tree has no tool for, so they are not asserted
        rather than being asserted from the prose.
        """
        rom = _require_rom()

        body = rom[0x68370:0x68642]
        self.assertEqual(len(body), 722)
        self.assertEqual(
            hashlib.sha256(body).hexdigest(),
            "13ef2ceedfe889bee6b7a6666d268246f43daa3fe5ad0be83a37f275e4ff4b20",
        )

        whole = rom[0x68370:0x68660]
        self.assertEqual(len(whole), 752)
        self.assertEqual(
            hashlib.sha256(whole).hexdigest(),
            "9ed2404ba8cae02b834b691ef5f7b9df8db76eca6cc52f280a4e3737dd8e0b3e",
        )

        family = _index_family(_load_index(), "battle-status-bars-v1")
        self.assertEqual(
            family["manifest_sha256"],
            "d88242fa88213b96d8fe48430a0758a3bb79adf7dd6bb6d22e7d00da9711c0d0",
        )

    # ------------------------------------------------------------------
    # notes/battle-start-control-flow-20260713.md
    # ------------------------------------------------------------------
    def test_battle_start_control_flow_address_filter(self) -> None:
        """notes/battle-start-control-flow-20260713.md (reverse tree:
        ``notes/battle-start-control-flow-20260713.md``).

        Conclusion pinned: ``0x0200A884``/``0x0200A885`` are **one** 16-bit
        filtered-input bitmap, not two independent UI status bytes.  The
        original ROM contains no literal reference to ``0x0200A885`` at all,
        while ``0x0200A884`` and ``0x0200A882`` are both referenced many
        times; the high byte that was once read as "team ready" is just the
        high half of the ``0x0200A884`` halfword.

        Receipt: ``rom/base.gba`` @ sha256
        ``1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b``
        (literal-pool scan; the note names the same working ROM).

        The exact counts 0 / 20 / 64 are measured here rather than quoted
        from the note -- the note only says "zero" and "many" -- but they are
        measured from the same pinned ROM, so they are exact and stable.
        """
        rom = _require_rom()

        def literal_references(address: int) -> int:
            return rom.count(address.to_bytes(4, "little"))

        self.assertEqual(literal_references(0x0200A885), 0)
        self.assertEqual(literal_references(0x0200A884), 20)
        self.assertEqual(literal_references(0x0200A882), 64)

    # ------------------------------------------------------------------
    # notes/character-battle-visuals-export-20260729.md
    # ------------------------------------------------------------------
    def test_character_battle_visual_descriptor_matrix(self) -> None:
        """notes/character-battle-visuals-export-20260729.md (this tree).

        Conclusion pinned: the battle OBJ matrix lives at
        ``0x08596D5C..0x0859903C`` -- 62 characters x 9 visual slots x 16
        bytes (``0x22E0`` bytes, sha256
        ``baa3f86793e15d0d4abd44fcf10518da15ba0d76588b918838c3660e042e01dc``)
        -- and each row is four ``u32`` pointers.  Of the 558 rows, 342 have
        all four pointers, 216 are entirely zero and **none** is partially
        filled; slots 0-4 are complete for all 62 characters while slots 5-8
        only have 8 each.  The row is addressed as
        ``0x08596CCC + character_id * 0x90 + visual_slot * 0x10``, and the
        matrix ends exactly at ``0x59903C`` where an independent 14x16 BG
        table starts with an all-zero sentinel row.

        Receipt: ``rom/base.gba`` @ sha256
        ``1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b``.
        """
        rom = _require_rom()

        matrix = rom[CHARACTER_MATRIX:CHARACTER_MATRIX_END]
        self.assertEqual(len(matrix), 558 * 16)
        self.assertEqual(len(matrix), 0x22E0)
        self.assertEqual(
            hashlib.sha256(matrix).hexdigest(),
            "baa3f86793e15d0d4abd44fcf10518da15ba0d76588b918838c3660e042e01dc",
        )

        selector = rom[0x7AE04:0x7B284]
        self.assertEqual(
            hashlib.sha256(selector).hexdigest(),
            "5a0d06474ee94f5d3fd68cfe6c90224ce5a4cc8ffbb8ceeb6c4529c67ecd1b0b",
        )

        complete = zero = partial = 0
        per_slot = [0] * CHARACTER_VISUAL_SLOTS
        for character_id in range(1, CHARACTER_COUNT + 1):
            for slot in range(CHARACTER_VISUAL_SLOTS):
                row = (character_id - 1) * CHARACTER_VISUAL_SLOTS + slot
                start = CHARACTER_MATRIX + row * 16
                record = rom[start : start + 16]
                pointers = [_u32(record, offset) for offset in (0, 4, 8, 12)]
                if all(pointer == 0 for pointer in pointers):
                    zero += 1
                elif all(pointer != 0 for pointer in pointers):
                    complete += 1
                    per_slot[slot] += 1
                else:
                    partial += 1
                # The note's addressing formula must land on the same row.
                self.assertEqual(
                    0x08596CCC + character_id * 0x90 + slot * 0x10,
                    0x08596D5C + row * 16,
                )

        self.assertEqual((complete, zero, partial), (342, 216, 0))
        self.assertEqual(per_slot, [62, 62, 62, 62, 62, 8, 8, 8, 8])

        # The matrix ends exactly at 0x59903C; the next table's first row is
        # the all-zero sentinel of table id 0.
        self.assertEqual(rom[CHARACTER_MATRIX_END : CHARACTER_MATRIX_END + 16], b"\x00" * 16)

    # ------------------------------------------------------------------
    # notes/battle-presentation-glyphs-export-20260729.md
    # ------------------------------------------------------------------
    def test_battle_presentation_glyph_tables(self) -> None:
        """notes/battle-presentation-glyphs-export-20260729.md (this tree).

        Conclusion pinned: ``0x085A2B08..0x085A2C44`` is 79 NUL-terminated
        message string pointers, ``0x085A2C44..0x085A2EF4`` is 172 LZ77
        graphic block pointers, and ``0x085A2EF4..0x085A320A`` is the 79x10
        message -> glyph binding.  The binding's count byte gives 294 slots
        of which exactly 10 are ``0xFF`` skip slots, leaving **284** real
        glyph slots; 138 distinct glyph ids are referenced and the remaining
        34 of the 172 graphics are unbound but preserved.  Messages
        13/31/32/46 have an empty binding.

        Also pinned: the runtime 16-colour BGR555 palette at ``0x083E4AF0``
        (sha256 ``91469795b385e7b06edde2a8fcba8d562ddf5c2bca69350e1dc7880974419981``)
        and the palette-initializer code slice ``[0x080983B8, 0x08098624)``
        (sha256 ``7a7598a7edfef279bf745897ba5ea0f94e5361e2db84acee7a84a23f06a61422``).

        Receipt: ``rom/base.gba`` @ sha256
        ``1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b``.
        """
        rom = _require_rom()

        palette = rom[0x3E4AF0 : 0x3E4AF0 + 32]
        self.assertEqual(len(palette), 32)
        self.assertEqual(
            hashlib.sha256(palette).hexdigest(),
            "91469795b385e7b06edde2a8fcba8d562ddf5c2bca69350e1dc7880974419981",
        )

        initializer = rom[0x983B8:0x98624]
        self.assertEqual(
            hashlib.sha256(initializer).hexdigest(),
            "7a7598a7edfef279bf745897ba5ea0f94e5361e2db84acee7a84a23f06a61422",
        )

        # 79 message pointers, each pointing at a NUL-terminated string.
        for message_id in range(VISUAL_BINDING_ROWS):
            pointer = _u32(rom, VISUAL_MESSAGE_TABLE + 4 * message_id)
            offset = pointer - 0x08000000
            self.assertTrue(0 <= offset < len(rom), f"message {message_id}")
            terminator = rom.find(b"\x00", offset)
            self.assertTrue(0 < terminator - offset < 0x1000, f"message {message_id}")

        # 172 LZ77 graphic pointers, every one carrying an LZ77 header.
        for glyph_id in range(VISUAL_GRAPHIC_COUNT):
            pointer = _u32(rom, VISUAL_GRAPHIC_TABLE + 4 * glyph_id)
            offset = pointer - 0x08000000
            self.assertTrue(0 <= offset < len(rom), f"graphic {glyph_id}")
            self.assertEqual(rom[offset] >> 4, 0x1, f"graphic {glyph_id} header")

        # 79x10 message -> glyph binding.
        empty = []
        slots = 0
        skipped = 0
        referenced = set()
        for message_id in range(VISUAL_BINDING_ROWS):
            start = VISUAL_BINDING_TABLE + message_id * VISUAL_BINDING_STRIDE
            row = rom[start : start + VISUAL_BINDING_STRIDE]
            count = row[0]
            if count == 0:
                empty.append(message_id)
            for glyph in row[1 : 1 + count]:
                slots += 1
                if glyph == 0xFF:
                    skipped += 1
                else:
                    referenced.add(glyph)

        self.assertEqual(empty, [13, 31, 32, 46])
        self.assertEqual(slots, 294)
        self.assertEqual(skipped, 10)
        self.assertEqual(slots - skipped, 284)
        self.assertEqual(len(referenced), 138)
        self.assertEqual(VISUAL_GRAPHIC_COUNT - len(referenced), 34)

        # Two zero padding bytes sit between the binding and the descriptors.
        self.assertEqual(rom[0x5A320A:0x5A320C], b"\x00\x00")

    # ------------------------------------------------------------------
    # notes/battle-visual-catalog-export-20260729.md
    # ------------------------------------------------------------------
    def test_battle_visual_catalog_descriptor_table(self) -> None:
        """notes/battle-visual-catalog-export-20260729.md (this tree).

        Conclusion pinned: the 79 battle visual descriptors live at
        ``0x085A320C`` as 79 records of ``0x44`` bytes (the last byte is
        ``0x085A4707``); four of them -- ids 13, 31, 32 and 46 -- are
        all-zero sentinels.  Counting a layer as "complete" when its three
        pointers are all non-zero gives exactly **236** complete static
        layers (A 75, B 75, C 75, D 11).  Descriptor 0's D layer is the
        documented exception: it carries the tilemap ``0x0836774C`` but its
        gfx pointer is zero, so the installer refuses it, while descriptor 4's
        D layer is complete.

        Receipt: ``rom/base.gba`` @ sha256
        ``1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b``,
        plus ``artifacts/reverse-results-index-v1/index.json`` for the
        manifest hash the note quotes
        (``1ccbdfda751953328104c845e061074150324ca69a569330a25263e5be787bcc``)
        and the selection-chain formula it states.

        Not pinned: the 79 preview PNGs and the 284 glyph / 10 skip-slot
        counts of the catalog -- the previews live in the reverse tree; the
        glyph counts are pinned by the presentation-glyphs test instead.
        """
        rom = _require_rom()

        # 79 records of 0x44 bytes, the last byte being 0x085A4707.
        self.assertEqual(
            VISUAL_DESCRIPTOR_TABLE + VISUAL_DESCRIPTOR_COUNT * VISUAL_DESCRIPTOR_STRIDE - 1,
            0x5A4707,
        )

        sentinels = []
        layers = {name: 0 for name in VISUAL_LAYER_GROUPS}
        for descriptor_id in range(VISUAL_DESCRIPTOR_COUNT):
            record = _descriptor(rom, descriptor_id)
            self.assertEqual(len(record), VISUAL_DESCRIPTOR_STRIDE)
            if record == b"\x00" * VISUAL_DESCRIPTOR_STRIDE:
                sentinels.append(descriptor_id)
            for name, offsets in VISUAL_LAYER_GROUPS.items():
                if all(_u32(record, offset) for offset in offsets):
                    layers[name] += 1

        self.assertEqual(sentinels, [13, 31, 32, 46])
        self.assertEqual(sum(layers.values()), 236)
        self.assertEqual(layers, {"A": 75, "B": 75, "C": 75, "D": 11})

        # Descriptor 0's D layer: tilemap only, the gfx pointer is zero.
        descriptor0 = _descriptor(rom, 0)
        self.assertEqual(_u32(descriptor0, 0x3C), 0x0836774C)
        self.assertEqual(_u32(descriptor0, 0x38), 0)
        self.assertEqual(_u32(descriptor0, 0x40), 0)

        # Descriptor 4's D layer is a complete triple.
        descriptor4 = _descriptor(rom, 4)
        for offset in VISUAL_LAYER_GROUPS["D"]:
            self.assertNotEqual(_u32(descriptor4, offset), 0)

        # Exactly one descriptor has a D tilemap but no D gfx.
        broken = [
            descriptor_id
            for descriptor_id in range(VISUAL_DESCRIPTOR_COUNT)
            if _u32(_descriptor(rom, descriptor_id), 0x3C)
            and not _u32(_descriptor(rom, descriptor_id), 0x38)
        ]
        self.assertEqual(broken, [0])

        family = _index_family(_load_index(), "battle-visual-catalog-v1")
        self.assertEqual(
            family["manifest_sha256"],
            "1ccbdfda751953328104c845e061074150324ca69a569330a25263e5be787bcc",
        )
        self.assertIn(
            "descriptor = 0x085A320C + state.message_id * 0x44",
            " ".join(family.get("formulas", [])),
        )

    # ------------------------------------------------------------------
    # notes/battle-visual-runtime-timelines-export-20260729.md
    # ------------------------------------------------------------------
    def test_battle_visual_runtime_timeline_descriptor_fields(self) -> None:
        """notes/battle-visual-runtime-timelines-export-20260729.md (this tree).

        Conclusion pinned: the per-descriptor runtime model the note
        describes is anchored in the descriptor record itself.  Descriptor 0
        carries ``origin_x = 72`` and cue ``119``; descriptor 2 is callback
        mode 3 with the same ``origin_x = 72`` and the same cue ``119``;
        descriptors 1 and 3 are the ``0x0100`` branch (callback mode 0) and
        both carry cue ``137``.  Of the 79 descriptors, 75 are playable -- the
        other four are the all-zero sentinels 13/31/32/46.

        The note states the *values* but not the field offsets, so the offsets
        used here (``+0x04`` origin_x, ``+0x06`` callback mode / flags,
        ``+0x08`` cue) are proven here by uniqueness: inside descriptor 0's
        record the value 72 occurs at exactly one 16-bit slot (``+0x04``) and
        119 at exactly one (``+0x08``).

        Receipt: ``rom/base.gba`` @ sha256
        ``1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b``,
        plus ``artifacts/reverse-results-index-v1/index.json`` for the
        manifest hash the note quotes
        (``7a3fd143f76a72f9f996029cef6aca218aa4bed5e2f2f16e63a6b7a76c55250b``).

        Not pinned: the "106 linked ticks per timeline" and the
        ``84 + 6 x binding_count`` frame formula -- those come from the
        reverse tree's offline tick model, not from a receipt in this tree.
        """
        rom = _require_rom()

        def header(descriptor_id: int):
            record = _descriptor(rom, descriptor_id)
            return record, struct.unpack_from("<6H", record, 0)

        record0, head0 = header(0)
        self.assertEqual(head0[2], 72)  # origin_x
        self.assertEqual(head0[4], 119)  # cue

        _, head2 = header(2)
        self.assertEqual(head2[3] & 0x00FF, 3)  # callback mode 3
        self.assertEqual(head2[2], 72)
        self.assertEqual(head2[4], 119)

        for descriptor_id in (1, 3):
            _, head = header(descriptor_id)
            self.assertEqual(head[3] & 0x0100, 0x0100)  # the 0x0100 branch
            self.assertEqual(head[3] & 0x00FF, 0)  # callback mode 0
            self.assertEqual(head[4], 137)  # cue 137

        # The field offsets are unique inside the record.
        for value, offset in ((72, 4), (119, 8)):
            occurrences = [
                slot
                for slot in range(0, VISUAL_DESCRIPTOR_STRIDE, 2)
                if _u16(record0, slot) == value
            ]
            self.assertEqual(occurrences, [offset])

        playable = [
            descriptor_id
            for descriptor_id in range(VISUAL_DESCRIPTOR_COUNT)
            if _descriptor(rom, descriptor_id) != b"\x00" * VISUAL_DESCRIPTOR_STRIDE
        ]
        self.assertEqual(len(playable), 75)
        self.assertEqual(
            [descriptor_id for descriptor_id in range(VISUAL_DESCRIPTOR_COUNT)
             if descriptor_id not in playable],
            [13, 31, 32, 46],
        )

        family = _index_family(_load_index(), "battle-visual-runtime-timelines-v1")
        self.assertEqual(
            family["manifest_sha256"],
            "7a3fd143f76a72f9f996029cef6aca218aa4bed5e2f2f16e63a6b7a76c55250b",
        )

    # ------------------------------------------------------------------
    # notes/text-and-battle-visual-consumers-20260713.md
    # ------------------------------------------------------------------
    def test_text_and_battle_visual_consumers(self) -> None:
        """notes/text-and-battle-visual-consumers-20260713.md (this tree).

        Conclusion pinned: the character/profile description text is a
        46-pointer table at ``0x5A143C`` (last byte ``0x5A14F3``), the
        historical ``data-table-a@0x5A14A4`` being physical entry 26 of it.
        A runtime A/B reached the profile card through hook ``0x0808B1A4``:
        with entry 0 selected the reader returned ``0x0859F988`` and with
        entry 7 patched in it returned ``0x0859FDE8``.

        The visual variant matrix is addressed as
        ``0x085A4DEC + record_id * 40 + variant * 8``; record 7 / variant 0
        therefore lives at ``0x5A4F04`` and holds the pair
        ``(0x08418A88, 0x084196C8)``, while record 3 / variant 0 holds
        ``(0x08411CD4, 0x08412984)``.  Record 0 is intentionally all zero and
        the table is 63 records, ending at ``0x5A57C4``.

        Receipts: ``artifacts/runtime-checkpoints/profile-text-runtime-evidence.json``
        @ sha256 ``552b94be0613af35642524136f631b211c47d71e113c575111154ee2a529b363``,
        ``artifacts/runtime-checkpoints/visual-variant-runtime-evidence.json``
        @ sha256 ``3abe72ddadba5a51c22b738b79dd1db59cad79a806835d97d1c517a9ceab0e9a``,
        and ``rom/base.gba`` @ sha256
        ``1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b``
        for the byte-level cross-check.
        """
        profile = _require_json(PROFILE_TEXT_RECEIPT, PROFILE_TEXT_SHA256)
        variant = _require_json(VISUAL_VARIANT_RECEIPT, VISUAL_VARIANT_SHA256)
        rom = _require_rom()

        # Profile text table.
        self.assertEqual(profile["table"], "0x085A143C")
        self.assertEqual(profile["hook"], "0x0808B1A4")
        self.assertEqual(profile["control"]["table_entry"], "0x085A143C")
        self.assertEqual(profile["control"]["selected_pointer"], "0x0859F988")
        self.assertEqual(profile["variant"]["selected_pointer"], "0x0859FDE8")
        self.assertEqual(profile["control"]["magic"], "PTPR")
        self.assertEqual(profile["variant"]["magic"], "PTPR")
        self.assertEqual(profile["single_factor_patch"]["rom_offset"], "0x5A143C")
        self.assertEqual(profile["single_factor_patch"]["size"], 4)
        self.assertEqual(profile["single_factor_patch"]["source_entry"], 7)

        # 46 pointers, last byte 0x5A14F3, historical entry 26 at 0x5A14A4.
        self.assertEqual(0x5A143C + 46 * 4 - 1, 0x5A14F3)
        self.assertEqual(0x5A143C + 26 * 4, 0x5A14A4)
        self.assertEqual(_u32(rom, 0x5A143C), 0x0859F988)
        self.assertEqual(_u32(rom, 0x5A143C + 7 * 4), 0x0859FDE8)

        # Visual variant matrix.
        self.assertEqual(variant["table_offset"], "0x5A4DEC")
        self.assertEqual(variant["record_id"], 7)
        self.assertEqual(variant["variant"], 0)
        self.assertEqual(variant["target_pair_offset"], "0x5A4F04")
        self.assertEqual(variant["control_pair_hex"], "888a4108c8964108")
        self.assertEqual(variant["replacement_source_record_id"], 3)
        self.assertEqual(variant["replacement_pair_hex"], "d41c410884294108")
        self.assertEqual(variant["control_visible_portrait"], "Kakashi")
        self.assertEqual(variant["changed_visible_portrait"], "Sakura")

        # The formula, checked against the ROM.
        self.assertEqual(0x5A4DEC + 7 * 40 + 0 * 8, 0x5A4F04)
        self.assertEqual(0x5A4DEC + 3 * 40 + 0 * 8, 0x5A4E64)
        self.assertEqual(0x5A4DEC + 63 * 40, 0x5A57C4)
        self.assertEqual(_u32(rom, 0x5A4F04), 0x08418A88)
        self.assertEqual(_u32(rom, 0x5A4F08), 0x084196C8)
        self.assertEqual(_u32(rom, 0x5A4E64), 0x08411CD4)
        self.assertEqual(_u32(rom, 0x5A4E68), 0x08412984)
        self.assertEqual(rom[0x5A4DEC : 0x5A4DEC + 40], b"\x00" * 40)

    # ------------------------------------------------------------------
    # notes/first-battle-savestate-checkpoints-20260712.md
    # ------------------------------------------------------------------
    def test_first_battle_savestate_unit_pool_layout(self) -> None:
        """notes/first-battle-savestate-checkpoints-20260712.md (this tree).

        Conclusion pinned: the live battle unit position lives in the unit
        pool record, not in the cursor -- the pool base is ``0x020240C0``,
        the stride is ``0x1D4`` and the grid coordinates sit at record
        ``+0xC4`` / ``+0xC5``.  The captured S49 battle-14 pool proves it:
        for every one of the nine occupied slots the record's ``+0x00`` is
        the character id, ``+0xC4`` is the x coordinate and ``+0xC5`` is the
        y coordinate, and the pool is exactly 13 slots of ``0x1D4`` bytes
        (6084).

        Receipts: ``artifacts/s49-original-battle14-roster-v1/unit_pool.bin``
        @ sha256
        ``9d508d991fb5a454a4bfe0b9008a7627490fafe99f7aa1dca63b316a4788c2c5``
        and ``artifacts/s49-original-battle14-roster-v1/roster.json`` @ sha256
        ``b53417ce5210d1d26b12355dab71cdb1c294bc7e987c9a8246d91b47f9513809``,
        plus ``rom/base.gba`` for the WRAM allocation row that names the pool
        base and its 6084-byte size.

        The note's own ``/tmp/*.ss9`` checkpoints are not in this tree, so
        the captured pool is the receipt for the layout claim.
        """
        pool = _require_bytes(ROSTER_POOL, ROSTER_POOL_SHA256)
        roster = _require_json(ROSTER_JSON, ROSTER_JSON_SHA256)
        rom = _require_rom()

        self.assertEqual(roster["battle_id"], 14)
        self.assertEqual(len(pool), UNIT_POOL_SLOTS * UNIT_POOL_STRIDE)
        self.assertEqual(len(pool), 6084)

        units = roster["original_units"]
        self.assertEqual(len(units), 9)
        for unit in units:
            slot = unit["slot"]
            record = pool[slot * UNIT_POOL_STRIDE : (slot + 1) * UNIT_POOL_STRIDE]
            self.assertEqual(len(record), UNIT_POOL_STRIDE)
            self.assertEqual(record[0], unit["character_id"], f"slot {slot} id")
            self.assertEqual(
                record[UNIT_POOL_X_OFFSET], unit["grid_x"], f"slot {slot} x"
            )
            self.assertEqual(
                record[UNIT_POOL_Y_OFFSET], unit["grid_y"], f"slot {slot} y"
            )

        # The ROM's WRAM allocation table names the same pool: base 0x020240C0
        # with a size of 6084 bytes.
        self.assertEqual(_u32(rom, 0x53D880), UNIT_POOL_BASE)
        self.assertEqual(_u16(rom, 0x53D884), 6084)
        self.assertEqual(6084, UNIT_POOL_SLOTS * UNIT_POOL_STRIDE)


if __name__ == "__main__":
    unittest.main()
