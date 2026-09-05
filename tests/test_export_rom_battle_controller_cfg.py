#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.export_rom_battle_controller_cfg import (
    CONTROLLER_RANGE,
    CONTROLLER_SHA256,
    DEFAULT_TARGET,
    DISPATCH_MAPPING_VECTOR_SHA256,
    DISPATCH_RANGE,
    ROM_SHA256,
    _baseline_occupied_bytes,
    _bounded_root_records,
    _dispatch_denominator,
    _sha,
    _traverse_bounded,
)


_BASELINE_LOADER_SCHEMA_LAYOUT: dict[str, str] = {
    # Match the actual schema convention: v2 keeps blocks at the top level;
    # v3 and the proven-roots artifacts keep them under ``extension.blocks``.
    "rom-cfg-inventory-v2": "top",
    "rom-cfg-inventory-v3": "extension",
    "rom-cfg-proven-roots-v1": "extension",
    "rom-cfg-proven-roots-v2": "extension",
}


def _write_baseline_artifact(
    root: Path,
    artifact_dir: str,
    payload_name: str,
    schema: str,
    block: dict,
) -> Path:
    """Write a single frozen baseline payload under ``root``.

    Only the schema, blocks layout and per-block fields required by
    ``_baseline_occupied_bytes`` are populated; no other verifier-required
    fields are fabricated.
    """

    artifact_root = root / artifact_dir
    artifact_root.mkdir(parents=True, exist_ok=True)
    if _BASELINE_LOADER_SCHEMA_LAYOUT[schema] == "extension":
        payload = {"schema": schema, "extension": {"blocks": [block]}}
    else:
        payload = {"schema": schema, "blocks": [block]}
    payload_path = artifact_root / payload_name
    payload_path.write_bytes(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    )
    return payload_path


ROOT = Path(__file__).resolve().parents[1]


class RomBattleControllerDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.dispatch = _dispatch_denominator(cls.rom)

    def test_exhaustively_rebuilds_the_real_38_state_denominator(self) -> None:
        result = self.dispatch

        self.assertEqual(ROM_SHA256, "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b")
        self.assertEqual(CONTROLLER_RANGE, (0x732B4, 0x7509C))
        self.assertEqual(DISPATCH_RANGE, (0x733A0, 0x735CA))
        self.assertEqual(result["input_denominator"], 65_536)
        self.assertEqual(result["nondefault_state_count"], 38)
        self.assertEqual(result["default_state_count"], 65_498)
        self.assertEqual(result["default_target"], 0x7504E)
        self.assertEqual(
            result["mapping_denominator_sha256"],
            DISPATCH_MAPPING_VECTOR_SHA256,
        )

        mappings = {
            item["state"]: item["target_offset"] for item in result["mappings"]
        }
        self.assertEqual(
            mappings,
            {
                0x0000: 0x735CA,
                0x0010: 0x73638,
                0x1000: 0x7364A,
                0x1100: 0x7367C,
                0x1200: 0x736B0,
                0x1210: 0x736F8,
                0x1220: 0x737E6,
                0x1300: 0x738C0,
                0x2000: 0x73940,
                0x2010: 0x739D0,
                0x3000: 0x73A04,
                0x3100: 0x73B84,
                0x3110: 0x73BA8,
                0x3200: 0x73E14,
                0x3210: 0x73EB0,
                0x3220: 0x74074,
                0x3300: 0x740D4,
                0x4000: 0x7410C,
                0x4100: 0x74190,
                0x5000: 0x74200,
                0x6000: 0x742A4,
                0x7000: 0x742E4,
                0x8000: 0x743D4,
                0x8010: 0x74510,
                0x9000: 0x74550,
                0x9100: 0x747E0,
                0x9110: 0x74834,
                0xA000: 0x7484E,
                0xB000: 0x74870,
                0xC000: 0x748AC,
                0xD000: 0x74918,
                0xE000: 0x74988,
                0xE010: 0x749CC,
                0xF000: 0x74A98,
                0xF100: 0x74C2E,
                0xF200: 0x74C7C,
                0xF300: 0x74E48,
                0xF400: 0x74EE6,
            },
        )
        self.assertTrue(all(item["target_offset"] % 2 == 0 for item in result["mappings"]))
        self.assertTrue(
            all(
                CONTROLLER_RANGE[0] <= item["target_offset"] < CONTROLLER_RANGE[1]
                for item in result["mappings"]
            )
        )

    def test_preserves_the_three_old_false_states_as_default_inputs(self) -> None:
        result = self.dispatch
        mapped = {item["state"] for item in result["mappings"]}
        self.assertTrue({0x1020, 0x3310, 0x9200}.isdisjoint(mapped))

    def test_rejects_dispatcher_tampering(self) -> None:
        changed = bytearray(self.rom)
        changed[DISPATCH_RANGE[0]] ^= 1
        with self.assertRaisesRegex(ValueError, "dispatcher"):
            _dispatch_denominator(bytes(changed))


class RomBattleControllerRangeBoundaryTests(unittest.TestCase):
    """The corrected controller range must end at 0x7509C (next function entry).

    The historical v1 cut-off at 0x75082 truncated a 4-byte Thumb BL that
    starts at 0x75080; the next function begins at 0x7509C, so the corrected
    body must contain the full BL but must exclude the sibling function.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_corrected_controller_sha_matches_full_body(self) -> None:
        start, end = CONTROLLER_RANGE
        self.assertEqual(start, 0x732B4)
        self.assertEqual(end, 0x7509C)
        body = self.rom[start:end]
        # Canonical corrected SHA (handoff §4.1).
        from tools.export_rom_battle_controller_cfg import CONTROLLER_SHA256

        self.assertEqual(
            CONTROLLER_SHA256,
            "c9bdc220590a851fa331960bcb32be90eb9ac7248a5cd3dabb9f8afa0b674bc1",
        )
        self.assertEqual(_sha(body), CONTROLLER_SHA256)

    def test_full_four_byte_BL_at_0x75080_lives_inside_range(self) -> None:
        start, end = CONTROLLER_RANGE
        bl_offset = 0x75080
        self.assertGreaterEqual(bl_offset, start)
        self.assertLessEqual(bl_offset + 4, end)
        first = int.from_bytes(self.rom[bl_offset : bl_offset + 2], "little")
        second = int.from_bytes(self.rom[bl_offset + 2 : bl_offset + 4], "little")
        # Thumb-1 BL: top 5 bits of each halfword must be 0b11110 / 0b11111.
        self.assertEqual(first & 0xF800, 0xF000)
        self.assertEqual(second & 0xF800, 0xF800)
        # The full 4-byte BL must lie inside the controller range; the range
        # must extend strictly past the BL end so the closure includes the
        # following 4-byte BL at 0x75084 and the epilogue.
        self.assertGreater(end, bl_offset + 4)

    def test_next_function_entry_at_0x7509C_is_outside_controller(self) -> None:
        start, end = CONTROLLER_RANGE
        next_function = 0x7509C
        self.assertGreaterEqual(next_function, end)
        # The byte at the next function entry is the prologue of a separate
        # function (typically PUSH / SUB sp,#imm / MOV rN, rM).  Document the
        # observed first halfword so the boundary is auditable.
        first = int.from_bytes(
            self.rom[next_function : next_function + 2], "little"
        )
        # 0xB500 is the canonical Thumb `PUSH {regs}` prologue; record but do
        # not hard-pin the encoding so that a corrected ROM diff would still
        # fail the SHA check above.
        self.assertTrue(
            (first & 0xFE00) in (0xB400, 0xB500, 0xB080, 0x4800, 0xB000),
            msg=f"unexpected prologue at 0x{next_function:06X}: 0x{first:04X}",
        )

    def test_dispatcher_default_target_sits_within_corrected_range(self) -> None:
        start, end = CONTROLLER_RANGE
        self.assertGreaterEqual(DEFAULT_TARGET, start)
        self.assertLess(DEFAULT_TARGET, end)
        # The default BL at 0x735C6 must remain inside the dispatcher window.
        self.assertGreaterEqual(0x735C6, DISPATCH_RANGE[0])
        self.assertLess(0x735C6, DISPATCH_RANGE[1])


# ---------------------------------------------------------------------------
# §4.5 #4 + §9.1 #4 + §9.1 #5 — bounded CFG traversal and per-root reachable
# instruction counts.  These tests do NOT touch the real ROM, the exporter
# main entry, the verifier, coverage or proof.  They drive
# ``_traverse_bounded`` and ``_bounded_root_records`` directly through
# ``unittest.mock.patch`` on the module-level ``CONTROLLER_RANGE`` and
# ``_decode_one`` symbols.
# ---------------------------------------------------------------------------

_TEST_RANGE = (0x100, 0x300)
_SYNTHETIC_ROM = b"\x00" * 0x400  # 1 KiB; comfortably covers _TEST_RANGE.


def _make_decoded(
    offset: int,
    size: int,
    successors: list[dict],
    mode: str = "thumb",
) -> dict:
    """Build a synthetic decoded record accepted by ``_traverse_bounded``.

    The real ``_decode_one`` produces many more fields; ``_traverse_bounded``
    only reads ``accepted``, ``size`` and ``successors``, so this minimum
    shape is sufficient.
    """

    return {
        "accepted": True,
        "mode": mode,
        "file_offset": offset,
        "size": size,
        "bytes_sha256": _sha(b"\x00" * size),
        "mnemonic": "synthetic",
        "op_str": "",
        "conditional": False,
        "flow_kind": "linear",
        "successors": successors,
        "frontiers": [],
    }


class BoundedTraversalTests(unittest.TestCase):
    """§4.5 #4 + §9.1 #4: bounded CFG traversal must respect frozen baseline
    bytes and record outside-range targets as opaque edges without dropping
    in-range fallthroughs."""

    def setUp(self) -> None:
        self.rom = _SYNTHETIC_ROM
        # patch.dict with ``clear=False`` semantics would clobber the module
        # dict; instead restore the constant in ``tearDown``.
        self._saved_range = CONTROLLER_RANGE
        self._patcher = patch(
            "tools.export_rom_battle_controller_cfg.CONTROLLER_RANGE",
            _TEST_RANGE,
        )
        self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()
        # Belt-and-braces: even if the patcher was somehow interrupted, never
        # let a tainted module constant leak into other tests in the file.
        import tools.export_rom_battle_controller_cfg as exporter

        exporter.CONTROLLER_RANGE = self._saved_range

    # ---- test 1 ---------------------------------------------------------

    def test_root_at_exact_baseline_byte_is_recorded_as_skipped(self) -> None:
        """A root whose target coincides with a frozen baseline byte must be
        recorded as a skipped entry and excluded from the worklist."""

        root_offset = 0x150  # inside _TEST_RANGE
        baseline_entries = {("thumb", root_offset)}
        baseline_occupied = {root_offset, root_offset + 1}
        roots = [{"target_offset": root_offset}]

        nodes, _rejected, _incoming, opaque, skipped = _traverse_bounded(
            self.rom,
            roots,
            baseline_entries=baseline_entries,
            baseline_occupied=baseline_occupied,
        )

        self.assertEqual(nodes, {})
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["target_file_offset"], root_offset)
        self.assertEqual(skipped[0]["reason"], "frozen_baseline_entry")
        self.assertEqual(skipped[0]["edge_kind"], "root_entry")
        # The skipped record must not be mis-classified as an opaque edge.
        self.assertNotIn(skipped[0], opaque)

    # ---- test 2 ---------------------------------------------------------

    def test_target_into_baseline_instruction_middle_fails_closed(self) -> None:
        """A CFG edge whose target lands in the middle of a frozen baseline
        instruction is not a legal opaque-stop entry and must raise rather
        than being mislabeled as ``frozen_baseline_entry`` (§9.1 #4)."""

        # Frozen baseline is a 4-byte Thumb BL at [0x140, 0x144).
        baseline_entries = {("thumb", 0x140)}
        baseline_occupied = set(range(0x140, 0x144))
        root_offset = 0x130  # inside _TEST_RANGE, not in baseline
        target_middle = 0x142  # middle of the 4-byte BL

        synthetic_decoded = _make_decoded(
            offset=root_offset,
            size=2,
            successors=[
                {
                    "kind": "branch_target",
                    "mode": "thumb",
                    "file_offset": target_middle,
                },
            ],
        )

        with patch(
            "tools.export_rom_battle_controller_cfg._decode_one",
            return_value=synthetic_decoded,
        ):
            with self.assertRaisesRegex(ValueError, "baseline.*middle|legal.*entry"):
                _traverse_bounded(
                    self.rom,
                    [{"target_offset": root_offset}],
                    baseline_entries=baseline_entries,
                    baseline_occupied=baseline_occupied,
                )

    # ---- test 3 ---------------------------------------------------------

    def test_instruction_overlapping_baseline_bytes_raises(self) -> None:
        """A decoded instruction whose bytes span into frozen baseline must
        fail closed with a ValueError mentioning baseline (§9.1 #4)."""

        # Baseline at [0x142, 0x146).  A 4-byte instruction starting at
        # 0x140 spans bytes 0x140..0x143, overlapping baseline at 0x142, 0x143.
        baseline_entries = {("thumb", 0x142)}
        baseline_occupied = set(range(0x142, 0x146))
        root_offset = 0x140

        synthetic_decoded = _make_decoded(
            offset=root_offset,
            size=4,
            successors=[],
        )

        with patch(
            "tools.export_rom_battle_controller_cfg._decode_one",
            return_value=synthetic_decoded,
        ):
            with self.assertRaisesRegex(ValueError, "baseline"):
                _traverse_bounded(
                    self.rom,
                    [{"target_offset": root_offset}],
                    baseline_entries=baseline_entries,
                    baseline_occupied=baseline_occupied,
                )

    # ---- test 4 ---------------------------------------------------------

    def test_outside_range_bl_target_opaque_but_fallthrough_continues(
        self,
    ) -> None:
        """A BL whose call target escapes the controller range must be
        recorded as opaque_external_edge, while the BL's in-range fallthrough
        must continue into the worklist and be visited as a real node."""

        root_offset = 0x160  # inside _TEST_RANGE
        bl_target = 0x500  # outside _TEST_RANGE (range ends at 0x300)
        fallthrough = 0x164  # = root_offset + 4 (Thumb BL size); inside range

        def fake_decode(rom: bytes, offset: int, mode: str) -> dict:
            if offset == root_offset:
                return _make_decoded(
                    offset=root_offset,
                    size=4,
                    successors=[
                        {
                            "kind": "call_target",
                            "mode": "thumb",
                            "file_offset": bl_target,
                        },
                        {
                            "kind": "fallthrough",
                            "mode": "thumb",
                            "file_offset": fallthrough,
                        },
                    ],
                )
            if offset == fallthrough:
                return _make_decoded(
                    offset=fallthrough,
                    size=2,
                    successors=[],
                )
            return {
                "accepted": False,
                "mode": mode,
                "file_offset": offset,
                "frontier_reason": "synthetic_decode_failure",
            }

        with patch(
            "tools.export_rom_battle_controller_cfg._decode_one",
            side_effect=fake_decode,
        ):
            nodes, _rejected, _incoming, opaque, _skipped = _traverse_bounded(
                self.rom,
                [{"target_offset": root_offset}],
                baseline_entries=set(),
                baseline_occupied=set(),
            )

        # Fallthrough must be visited as a real node.
        self.assertIn(("thumb", fallthrough), nodes)
        self.assertEqual(nodes[("thumb", fallthrough)]["file_offset"], fallthrough)
        # BL target must NOT be visited as a node.
        self.assertNotIn(("thumb", bl_target), nodes)
        # BL target must be recorded as opaque_external_edge.
        external_opaque = [
            edge
            for edge in opaque
            if edge["reason"] == "outside_controller_range"
            and edge["target_file_offset"] == bl_target
        ]
        self.assertEqual(
            len(external_opaque),
            1,
            msg=(
                "outside-range BL target must be opaque_external_edge; "
                f"opaque={opaque!r}"
            ),
        )
        self.assertEqual(external_opaque[0]["edge_kind"], "call_target")
        # The fallthrough must NOT be mis-classified as opaque.
        fallthrough_opaque = [
            edge
            for edge in opaque
            if edge["target_file_offset"] == fallthrough
        ]
        self.assertEqual(fallthrough_opaque, [])


class RootReachabilityWorklistTests(unittest.TestCase):
    """§9.1 #5: per-root reachable instruction count must come from the CFG
    edge worklist (transitive block successors), not from counting only the
    entry block's nodes."""

    def test_reachable_instruction_count_includes_successor_blocks_via_edges(
        self,
    ) -> None:
        """A root whose entry block has 2 nodes but that reaches a successor
        block with 3 nodes via CFG edges must report reachable_instruction_count
        equal to 5, not 2."""

        roots = [
            {
                "target_offset": 0x150,
                "gba_address": "0x08000150",
                "entry_sha256": "a" * 64,
                "entry_size": 2,
                "source_states": [0x1234],
                "dispatch_transfer": {
                    "transfer_offset": 0x100,
                    "transfer_kind": "branch_target",
                    "transfer_raw_hex": "abcd",
                },
            }
        ]
        # Entry block A: nodes at 0x150, 0x152 (2 nodes).
        # Successor block B: nodes at 0x160, 0x162, 0x164 (3 nodes).
        # Total reachable from root via CFG edges = 5.
        node_to_block = {
            ("thumb", 0x150): "block-A",
            ("thumb", 0x152): "block-A",
            ("thumb", 0x160): "block-B",
            ("thumb", 0x162): "block-B",
            ("thumb", 0x164): "block-B",
        }
        # Provide the canonical block records the exporter ships so a GREEN
        # fix that walks ``block["successors"]`` has full input.  Block A
        # has a single branch successor to block B; block B is terminal.
        blocks = [
            {
                "id": "block-A",
                "mode": "thumb",
                "range": [0x150, 0x154],
                "instruction_count": 2,
                "bytes_sha256": _sha(b"\x00" * 4),
                "terminator": {
                    "file_offset": 0x152,
                    "size": 2,
                    "mnemonic": "b",
                    "op_str": "0x08000160",
                    "flow_kind": "unconditional_branch",
                    "conditional": False,
                },
                "successors": [
                    {
                        "kind": "branch_target",
                        "mode": "thumb",
                        "file_offset": 0x160,
                        "block_id": "block-B",
                    },
                ],
            },
            {
                "id": "block-B",
                "mode": "thumb",
                "range": [0x160, 0x166],
                "instruction_count": 3,
                "bytes_sha256": _sha(b"\x00" * 6),
                "terminator": {
                    "file_offset": 0x164,
                    "size": 2,
                    "mnemonic": "bx",
                    "op_str": "lr",
                    "flow_kind": "return",
                    "conditional": False,
                },
                "successors": [],
            },
        ]

        records = _bounded_root_records(
            roots, blocks=blocks, frontiers=[], node_to_block=node_to_block
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["entry_block_id"], "block-A")
        # The contract: reachable count must include the successor block
        # reached via CFG edges, not just the entry block.  A correct
        # implementation walks block successors and returns 5.  A buggy
        # implementation that only counts the entry block returns 2.
        self.assertEqual(
            records[0]["reachable_instruction_count"],
            5,
            msg=(
                "reachable_instruction_count must walk successor blocks via "
                "CFG edges; if this fails, the BFS in _bounded_root_records "
                "expands only by block membership rather than by successor "
                "edges (§9.1 #5)."
            ),
        )


# ---------------------------------------------------------------------------
# §9.1 #4 — baseline loader must independently rebuild the legal instruction
# entry set and the occupied byte set for every frozen block.  The parent
# agent has confirmed the current implementation is wrong: it only records
# ``(mode, block_start)`` as an entry and never validates ``instruction_count``,
# ``bytes_sha256`` or the per-instruction decode sizes against the block end.
# The three lightweight tests below use a synthetic ``TemporaryDirectory`` with
# four minimal JSON payloads (one per frozen baseline schema) and patch
# ``_decode_one`` to a deterministic synthetic decoder.  They are RED today.
# ---------------------------------------------------------------------------


_BASELINE_LOADER_FIXTURE_ARTIFACTS: tuple[tuple[str, str, str], ...] = (
    # (artifact_path, payload_name, schema) — ``artifact_path`` mirrors the
    # exporter's literal layout under ``root``, including the ``artifacts/``
    # prefix, because the loader resolves each payload through
    # ``_safe_file(root, "artifacts/<name>/<payload>")``.
    ("artifacts/rom-cfg-inventory-v2", "rom-cfg-inventory.json", "rom-cfg-inventory-v2"),
    ("artifacts/rom-cfg-inventory-v3", "rom-cfg-inventory-v3.json", "rom-cfg-inventory-v3"),
    ("artifacts/rom-cfg-proven-roots-v1", "rom-cfg-proven-roots.json", "rom-cfg-proven-roots-v1"),
    ("artifacts/rom-cfg-proven-roots-v2", "rom-cfg-proven-roots-v2.json", "rom-cfg-proven-roots-v2"),
)


def _write_four_baseline_artifacts(
    root: Path,
    block: dict,
) -> None:
    """Write one synthetic frozen-block payload per baseline schema.

    Blocks are placed at the location the corresponding real artifact uses
    so a future GREEN implementation that strictly reads ``extension.blocks``
    for v3 and the proven-roots family continues to see the synthetic block.
    The caller must pass a fully-resolved ``root`` so that ``_safe_file``'s
    ``relative_to(root)`` check sees a matching realpath on macOS, where
    ``tempfile.TemporaryDirectory().name`` is a symlinked path under
    ``/var/folders`` that resolves to ``/private/var/folders``.
    """

    for artifact_dir, payload_name, schema in _BASELINE_LOADER_FIXTURE_ARTIFACTS:
        _write_baseline_artifact(root, artifact_dir, payload_name, schema, block)


def _compute_frozen_baseline_payload_sha256_for(root: Path) -> dict[str, str]:
    """Compute the raw SHA256 of each synthetic frozen baseline payload
    already written under ``root`` and return a dict mapping the
    relative path ``"artifacts/<dir>/<payload>"`` to its raw SHA256.

    Use this with ``unittest.mock.patch(..., create=True)`` to inject
    the synthetic fixtures' identity into the module's
    ``FROZEN_BASELINE_PAYLOAD_SHA256`` so the GREEN identity check
    in ``_baseline_occupied_bytes`` accepts the synthetic fixtures
    rather than refusing them as raw-byte tampered.  Without this
    patch the GREEN refactor would break every existing loader test
    in this file.
    """

    shas: dict[str, str] = {}
    for artifact_dir, payload_name, _schema in _BASELINE_LOADER_FIXTURE_ARTIFACTS:
        payload_path = root / artifact_dir / payload_name
        rel = f"{artifact_dir}/{payload_name}"
        shas[rel] = hashlib.sha256(payload_path.read_bytes()).hexdigest()
    return shas


class _ResolvedTemporaryDirectory:
    """``tempfile.TemporaryDirectory`` whose ``name`` is the resolved path.

    macOS exposes ``/var/folders/...`` as a symlink to
    ``/private/var/folders/...``.  ``_safe_file`` rejects symlinked inputs,
    so the test must pass the resolved directory or the loader's path safety
    check will refuse the synthetic artifacts before any contract can be
    exercised.  Use as a context manager; ``.name`` is the resolved path.
    """

    def __enter__(self) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        self._resolved = Path(self._tmp.name).resolve()
        return self._resolved

    def __exit__(self, exc_type, exc, tb) -> None:
        self._tmp.cleanup()


def _synthetic_block_decoder(
    decode_table: dict[int, tuple[int, list[dict]]],
):
    """Return a fake ``_decode_one`` that consults ``decode_table``.

    The real ``_decode_one`` decodes via capstone; this stub is enough for a
    loader that must iterate ``offset`` and read ``size``/``successors`` to
    walk each instruction.  Offsets not present in ``decode_table`` are
    reported as decode failures so an over-iterating loader fails closed
    instead of silently dropping into the next block.
    """

    def _decode(rom: bytes, offset: int, mode: str) -> dict:
        if offset in decode_table:
            size, successors = decode_table[offset]
            return _make_decoded(offset, size, successors, mode=mode)
        return {
            "accepted": False,
            "mode": mode,
            "file_offset": offset,
            "frontier_reason": "synthetic_decode_out_of_block",
        }

    return _decode


class BaselineLoaderTests(unittest.TestCase):
    """§9.1 #4: frozen baseline loader must validate block metadata against
    the ROM bytes and report every per-instruction entry, not just the
    block start."""

    _BLOCK_START = 0x100
    _BLOCK_END = 0x108
    _BLOCK_BYTES = b"\x00" * (_BLOCK_END - _BLOCK_START)
    _BLOCK_SHA = hashlib.sha256(_BLOCK_BYTES).hexdigest()
    _INSTRUCTION_COUNT = 3

    def _build_block(self, **overrides) -> dict:
        block = {
            "range": [self._BLOCK_START, self._BLOCK_END],
            "mode": "thumb",
            "instruction_count": self._INSTRUCTION_COUNT,
            "bytes_sha256": self._BLOCK_SHA,
        }
        block.update(overrides)
        return block

    def _build_rom(self) -> bytes:
        # 1 KiB; comfortably covers [0x100, 0x108) with zero padding.
        return b"\x00" * 0x400

    # ---- test 1 -------------------------------------------------------

    def test_baseline_loader_reports_per_instruction_entries_inside_block(
        self,
    ) -> None:
        """A block containing three instructions must contribute three
        ``(mode, entry)`` tuples, not just ``(mode, block_start)``.

        The synthetic decoder returns sizes 2, 4 and 2 for offsets 0x100,
        0x102 and 0x106; those sizes sum to 8 bytes which equals the block
        length, and the block's ``instruction_count`` matches the decode
        count.  A GREEN implementation must therefore return entries
        ``{('thumb',0x100),('thumb',0x102),('thumb',0x106)}`` and occupied
        bytes ``[0x100,0x108)``.
        """

        decode_table = {
            0x100: (
                2,
                [
                    {
                        "kind": "fallthrough",
                        "mode": "thumb",
                        "file_offset": 0x102,
                    }
                ],
            ),
            0x102: (
                4,
                [
                    {
                        "kind": "fallthrough",
                        "mode": "thumb",
                        "file_offset": 0x106,
                    }
                ],
            ),
            0x106: (2, []),
        }

        with _ResolvedTemporaryDirectory() as root:
            _write_four_baseline_artifacts(root, self._build_block())
            rom = self._build_rom()

            # Patch the module's frozen identity table with the
            # raw SHAs of the synthetic fixtures so a future GREEN
            # identity check in ``_baseline_occupied_bytes`` does not
            # reject the synthetic fixtures as raw-byte tampered.
            frozen_shas = _compute_frozen_baseline_payload_sha256_for(root)
            with patch(
                "tools.export_rom_battle_controller_cfg.FROZEN_BASELINE_PAYLOAD_SHA256",
                frozen_shas,
                create=True,
            ), patch(
                "tools.export_rom_battle_controller_cfg._decode_one",
                side_effect=_synthetic_block_decoder(decode_table),
            ):
                occupied, entries = _baseline_occupied_bytes(root, rom)

        expected_entries = {
            ("thumb", 0x100),
            ("thumb", 0x102),
            ("thumb", 0x106),
        }
        expected_occupied = set(range(self._BLOCK_START, self._BLOCK_END))

        self.assertEqual(
            entries,
            expected_entries,
            msg=(
                "baseline loader must report one (mode, offset) entry per "
                "instruction; a buggy loader that only emits (mode, block_start) "
                "fails this contract (§9.1 #4)."
            ),
        )
        self.assertEqual(
            occupied,
            expected_occupied,
            msg=(
                "baseline loader must record every byte covered by the block "
                "range, irrespective of how many entries the loader emits; "
                "tampering with how entries are accumulated must not silently "
                "drop occupied bytes (§9.1 #4)."
            ),
        )

    # ---- test 2 -------------------------------------------------------

    def test_baseline_loader_rejects_instruction_count_mismatch(self) -> None:
        """Block metadata claiming fewer (or more) instructions than the
        decoder actually produces must fail closed."""

        decode_table = {
            0x100: (
                2,
                [
                    {
                        "kind": "fallthrough",
                        "mode": "thumb",
                        "file_offset": 0x102,
                    }
                ],
            ),
            0x102: (
                4,
                [
                    {
                        "kind": "fallthrough",
                        "mode": "thumb",
                        "file_offset": 0x106,
                    }
                ],
            ),
            0x106: (2, []),
        }

        with _ResolvedTemporaryDirectory() as root:
            # Single-point tamper: ``instruction_count=2`` while the decoder
            # returns three instructions.  A GREEN implementation must
            # detect this inconsistency and raise rather than returning the
            # three entries silently.
            _write_four_baseline_artifacts(
                root, self._build_block(instruction_count=2)
            )
            rom = self._build_rom()

            # Patch the module's frozen identity table with the
            # raw SHAs of the synthetic fixtures so a future GREEN
            # identity check in ``_baseline_occupied_bytes`` does not
            # reject the synthetic fixtures as raw-byte tampered.
            frozen_shas = _compute_frozen_baseline_payload_sha256_for(root)
            with patch(
                "tools.export_rom_battle_controller_cfg.FROZEN_BASELINE_PAYLOAD_SHA256",
                frozen_shas,
                create=True,
            ), patch(
                "tools.export_rom_battle_controller_cfg._decode_one",
                side_effect=_synthetic_block_decoder(decode_table),
            ):
                with self.assertRaises(ValueError):
                    _baseline_occupied_bytes(root, rom)

    # ---- test 3 -------------------------------------------------------

    def test_baseline_loader_rejects_decode_size_or_bytes_hash_mismatch(
        self,
    ) -> None:
        """Both bytes_sha256 mismatch and decode-size mismatch must fail
        closed.  Two single-point tampering sub-tests prove the contract."""

        decode_table_correct = {
            0x100: (
                2,
                [
                    {
                        "kind": "fallthrough",
                        "mode": "thumb",
                        "file_offset": 0x102,
                    }
                ],
            ),
            0x102: (
                4,
                [
                    {
                        "kind": "fallthrough",
                        "mode": "thumb",
                        "file_offset": 0x106,
                    }
                ],
            ),
            0x106: (2, []),
        }

        # Variant A: bytes_sha256 does not equal sha256(rom[start:end]).
        # Single-point tamper: replace the block's bytes_sha256 with a
        # value that does NOT equal _BLOCK_SHA.
        with self.subTest("bytes_sha256 mismatch"):
            wrong_sha = "11" * 32
            self.assertNotEqual(wrong_sha, self._BLOCK_SHA)

            with _ResolvedTemporaryDirectory() as root:
                _write_four_baseline_artifacts(
                    root, self._build_block(bytes_sha256=wrong_sha)
                )
                rom = self._build_rom()

                # Patch the module's frozen identity table with the
                # raw SHAs of the synthetic fixtures so a future GREEN
                # identity check in ``_baseline_occupied_bytes`` does
                # not reject the synthetic fixtures as raw-byte tampered.
                frozen_shas = _compute_frozen_baseline_payload_sha256_for(root)
                with patch(
                    "tools.export_rom_battle_controller_cfg.FROZEN_BASELINE_PAYLOAD_SHA256",
                    frozen_shas,
                    create=True,
                ), patch(
                    "tools.export_rom_battle_controller_cfg._decode_one",
                    side_effect=_synthetic_block_decoder(decode_table_correct),
                ):
                    with self.assertRaises(ValueError):
                        _baseline_occupied_bytes(root, rom)

        # Variant B: the per-instruction decode sizes overshoot the block
        # end.  Single-point tamper: change the last instruction's size
        # from 2 to 4 so the cumulative end lands at 0x10A, past 0x108.
        with self.subTest("decode size overshoots block end"):
            decode_table_overshoot = {
                0x100: (
                    2,
                    [
                        {
                            "kind": "fallthrough",
                            "mode": "thumb",
                            "file_offset": 0x102,
                        }
                    ],
                ),
                0x102: (
                    4,
                    [
                        {
                            "kind": "fallthrough",
                            "mode": "thumb",
                            "file_offset": 0x106,
                        }
                    ],
                ),
                0x106: (4, []),  # 0x106 + 4 = 0x10A > 0x108
            }

            with _ResolvedTemporaryDirectory() as root:
                _write_four_baseline_artifacts(root, self._build_block())
                rom = self._build_rom()

                # Patch the module's frozen identity table with the
                # raw SHAs of the synthetic fixtures so a future GREEN
                # identity check in ``_baseline_occupied_bytes`` does
                # not reject the synthetic fixtures as raw-byte tampered.
                frozen_shas = _compute_frozen_baseline_payload_sha256_for(root)
                with patch(
                    "tools.export_rom_battle_controller_cfg.FROZEN_BASELINE_PAYLOAD_SHA256",
                    frozen_shas,
                    create=True,
                ), patch(
                    "tools.export_rom_battle_controller_cfg._decode_one",
                    side_effect=_synthetic_block_decoder(
                        decode_table_overshoot
                    ),
                ):
                    with self.assertRaises(ValueError):
                        _baseline_occupied_bytes(root, rom)


# ---------------------------------------------------------------------------
# §9.1 #4 — frozen baseline identity contract.
#
# The bounded CFG loader parses JSON, validates per-block fields
# (``range``, ``mode``, ``instruction_count``, ``bytes_sha256``,
# per-instruction decode sizes), and trusts that the parsed shape
# reflects what was on disk.  That trust can be exploited by any silent
# tamper that preserves the parsed shape but alters what the artifact
# means:
#
#   * deleting a legitimate block — the loader would simply emit fewer
#     occupied bytes and a smaller entry set, with no error;
#   * adding a semantically harmless extra top-level field — the
#     loader parses it away, no error;
#   * replacing the file with a self-consistent subset — same.
#
# The contract in this section closes that gap by requiring the
# exporter to expose a module-level identity table
# ``FROZEN_BASELINE_PAYLOAD_SHA256`` that maps the four payload
# relative paths to the raw SHA256 of the canonical bytes.  The
# loader must read each payload's raw bytes and compare against the
# table before parsing; any mismatch fails closed.  The two RED
# tests below pin the new contract; they are the same kind of
# "expected-after-GREEN" probe as the loader tests above.
# ---------------------------------------------------------------------------


_FROZEN_BASELINE_PAYLOAD_RELATIVE_PATHS: tuple[str, ...] = (
    # Each entry must be the exact relative path the loader passes
    # through ``_safe_file(root, Path(artifact_path) / payload_name)``.
    "artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json",
    "artifacts/rom-cfg-inventory-v3/rom-cfg-inventory-v3.json",
    "artifacts/rom-cfg-proven-roots-v1/rom-cfg-proven-roots.json",
    "artifacts/rom-cfg-proven-roots-v2/rom-cfg-proven-roots-v2.json",
)

_FROZEN_BASELINE_PAYLOAD_SHA256: dict[str, str] = {
    "artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json": (
        "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd"
    ),
    "artifacts/rom-cfg-inventory-v3/rom-cfg-inventory-v3.json": (
        "596c4d8cffa57f3899858a0a59351894b1398006ee0405ce799ed9f32a81bf9d"
    ),
    "artifacts/rom-cfg-proven-roots-v1/rom-cfg-proven-roots.json": (
        "7fdee7d0d62d3a8c82bfe7b03804e9cb0e3d213ebdf63acce6b0533045aecf54"
    ),
    "artifacts/rom-cfg-proven-roots-v2/rom-cfg-proven-roots-v2.json": (
        "a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba"
    ),
}


class FrozenBaselineIdentityContractTests(unittest.TestCase):
    """§9.1 #4: the bounded CFG loader must refuse any silent tamper
    of the four frozen baseline JSON payloads.  Two contracts are
    pinned here:

    1. The exporter module exposes a module-level constant
       ``FROZEN_BASELINE_PAYLOAD_SHA256`` whose value is exactly the
       four-entry dict mapping each payload's relative path to the
       raw SHA256 of its canonical bytes.

    2. ``_baseline_occupied_bytes`` raises ``ValueError`` when ONE
       of the four payloads is silently tampered (a semantically
       harmless extra top-level field that does not affect the
       parsed shape) after the module constant has been patched to
       match the unaltered fixtures.

    The first contract is RED today because the constant does not
    exist.  The second is RED today because the loader ignores
    unknown JSON keys and therefore never compares the raw bytes
    against the identity table.
    """

    _BLOCK_START = 0x100
    _BLOCK_END = 0x108
    _BLOCK_BYTES = b"\x00" * (_BLOCK_END - _BLOCK_START)
    _BLOCK_SHA = hashlib.sha256(_BLOCK_BYTES).hexdigest()
    _INSTRUCTION_COUNT = 3

    def _build_block(self) -> dict:
        return {
            "range": [self._BLOCK_START, self._BLOCK_END],
            "mode": "thumb",
            "instruction_count": self._INSTRUCTION_COUNT,
            "bytes_sha256": self._BLOCK_SHA,
        }

    def _build_rom(self) -> bytes:
        return b"\x00" * 0x400

    # ---- contract 1 ---------------------------------------------------

    def test_exporter_module_exposes_frozen_baseline_payload_sha256_constant(
        self,
    ) -> None:
        """The exporter module must expose
        ``FROZEN_BASELINE_PAYLOAD_SHA256`` as a module-level dict
        that maps each frozen payload's relative path to the raw
        SHA256 of its canonical bytes.

        Without this identity table the loader has no way to detect
        a payload tamper that preserves the parsed shape (deleting
        a legitimate block, adding a harmless extra field, or
        replacing the file with a self-consistent subset).  The
        constant is the canonical reference the GREEN identity
        check in ``_baseline_occupied_bytes`` compares against.
        """

        import tools.export_rom_battle_controller_cfg as exporter

        self.assertTrue(
            hasattr(exporter, "FROZEN_BASELINE_PAYLOAD_SHA256"),
            msg=(
                "exporter module must expose FROZEN_BASELINE_PAYLOAD_SHA256 "
                "as a module-level constant; the bounded CFG identity "
                "contract is unanchored without it (§9.1 #4)."
            ),
        )
        const = exporter.FROZEN_BASELINE_PAYLOAD_SHA256
        self.assertIsInstance(
            const,
            dict,
            msg=(
                "FROZEN_BASELINE_PAYLOAD_SHA256 must be a dict "
                "mapping relative path to SHA256; got "
                f"{type(const).__name__}"
            ),
        )
        # Exactly the four canonical payloads, no more, no less.
        self.assertEqual(
            set(const.keys()),
            set(_FROZEN_BASELINE_PAYLOAD_RELATIVE_PATHS),
            msg=(
                "FROZEN_BASELINE_PAYLOAD_SHA256 must map exactly the "
                "four frozen baseline payloads; an extra key leaks a "
                "non-canonical payload, a missing key lets the loader "
                "skip the identity check for that payload (§9.1 #4)."
            ),
        )
        # Each value must be the canonical raw SHA256.
        for rel_path, expected_sha in _FROZEN_BASELINE_PAYLOAD_SHA256.items():
            self.assertEqual(
                const.get(rel_path),
                expected_sha,
                msg=(
                    f"FROZEN_BASELINE_PAYLOAD_SHA256[{rel_path!r}] must "
                    f"be the canonical raw SHA256; got "
                    f"{const.get(rel_path)!r}, expected {expected_sha!r}."
                ),
            )

    # ---- contract 2 ---------------------------------------------------

    def test_adding_harmless_extra_to_one_payload_triggers_value_error(
        self,
    ) -> None:
        """Adding a semantically harmless extra top-level field to ONE
        of the four frozen baseline JSON payloads (without updating
        the module's ``FROZEN_BASELINE_PAYLOAD_SHA256``) must cause
        ``_baseline_occupied_bytes`` to raise ``ValueError``.

        Sequence:

        1. Write four synthetic payloads (no extras).
        2. Compute each payload's raw SHA256 and patch the module's
           ``FROZEN_BASELINE_PAYLOAD_SHA256`` to match.  This is the
           GREEN reference the loader compares against.
        3. Add a semantically harmless extra top-level key to ONE
           payload; the file's raw SHA256 changes but the patched
           constant still has the OLD value.
        4. Call ``_baseline_occupied_bytes``; the loader must raise
           ``ValueError`` because the on-disk raw bytes no longer
           match the frozen identity.

        Today's implementation parses JSON and ignores unknown
        top-level keys, so the loader succeeds and the test is RED.
        The GREEN identity check closes the gap.
        """

        decode_table = {
            self._BLOCK_START: (
                2,
                [
                    {
                        "kind": "fallthrough",
                        "mode": "thumb",
                        "file_offset": self._BLOCK_START + 2,
                    }
                ],
            ),
            self._BLOCK_START + 2: (
                4,
                [
                    {
                        "kind": "fallthrough",
                        "mode": "thumb",
                        "file_offset": self._BLOCK_START + 6,
                    }
                ],
            ),
            self._BLOCK_START + 6: (2, []),
        }

        with _ResolvedTemporaryDirectory() as root:
            _write_four_baseline_artifacts(root, self._build_block())
            rom = self._build_rom()

            # Step 2: compute raw SHAs of the unaltered fixtures and
            # patch the module's frozen identity table to match.  This
            # is the GREEN reference the loader compares against.
            frozen_shas = _compute_frozen_baseline_payload_sha256_for(root)
            self.assertEqual(
                len(frozen_shas),
                4,
                msg="expected exactly four synthetic payloads under root",
            )
            tampered_rel = (
                "artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json"
            )

            with patch(
                "tools.export_rom_battle_controller_cfg.FROZEN_BASELINE_PAYLOAD_SHA256",
                frozen_shas,
                create=True,
            ):
                # Step 3: tamper ONE payload with a semantically
                # harmless extra top-level field.  The parsed shape
                # is unaffected, so today's loader silently accepts it;
                # the raw bytes change, so the GREEN identity check
                # must raise.
                tampered_path = root / tampered_rel
                payload = json.loads(tampered_path.read_bytes())
                payload["_harmless_extra_marker"] = (
                    "this key is silently dropped by the loader; "
                    "its presence must still be detectable from "
                    "the raw byte SHA"
                )
                tampered_path.write_bytes(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
                # Sanity: the patched constant still has the OLD SHA,
                # not the new one — that's the entire point of the
                # tamper scenario.
                self.assertNotEqual(
                    hashlib.sha256(tampered_path.read_bytes()).hexdigest(),
                    frozen_shas[tampered_rel],
                    msg=(
                        "tamper scenario lost its edge: the patched "
                        "constant must not have been refreshed to "
                        "the new raw SHA, otherwise the loader would "
                        "have no signal to fail closed."
                    ),
                )

                # Step 4: loader must raise ``ValueError``.  Today
                # it does not (the implementation ignores the extra
                # field), so the assertion fails and the test is RED.
                with patch(
                    "tools.export_rom_battle_controller_cfg._decode_one",
                    side_effect=_synthetic_block_decoder(decode_table),
                ):
                    with self.assertRaises(ValueError):
                        _baseline_occupied_bytes(root, rom)


if __name__ == "__main__":
    unittest.main()
