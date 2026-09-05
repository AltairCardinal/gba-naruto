#!/usr/bin/env python3
"""RED tests for the independent battle-controller verifier's baseline loader
and bounded CFG traversal (handoff §9.1 #4 + §9.1 #5).

This file is intentionally read-only with respect to the verifier and
exporter source.  It only adds fresh assertions to lock the new contracts:

1. ``_baseline_occupied_bytes`` must accept ``(root, rom)`` and return
   ``(occupied, exact_entries)`` where ``exact_entries`` contains one
   ``(mode, file_offset)`` tuple per instruction inside every frozen
   baseline block.  The 2/4/2 byte three-instruction fixture must surface
   entries ``0x100 / 0x102 / 0x106`` plus occupied bytes ``[0x100, 0x108)``.

2. The loader must raise ``ValueError`` on any of:
     * instruction_count metadata disagreement,
     * bytes_sha256 metadata disagreement,
     * decode size that overshoots the block end.
   This is exercised via ``subTest`` against four minimal JSON payloads.

3. ``_rebuild_bounded`` must accept both ``baseline_entries`` and
   ``baseline_occupied`` so an exact legal entry can be opaque/skipped,
   while a target that lands in the middle of a frozen instruction must
   raise ``ValueError`` (no misclassification as ``frozen_baseline_entry``).

4. The verifier source must not import the exporter's controller module
   nor call any exporter helper; the boundary is enforced by source-text
   assertion so a future refactor that re-introduces the cross-module
   dependency fails closed.

All tests run against a 1 KiB synthetic ROM and a synthetic block decoder
patched onto ``tools.verify_rom_battle_controller_cfg._decode``; they never touch
the real ROM, the exporter, the artifact directory, or the proof/audit
pipeline.  The first three tests are RED today; test 4 is GREEN today and
must stay GREEN as a regression guard.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, cast
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.verify_rom_battle_controller_cfg import (  # noqa: E402
    CONTROLLER_RANGE,
    _baseline_occupied_bytes,
    _rebuild_bounded,
    verify_rom_battle_controller_cfg,
)


VERIFIER_SOURCE_PATH = (
    PROJECT_ROOT / "tools" / "verify_rom_battle_controller_cfg.py"
)

# Same schema layout the exporter-side test uses.  Mirrors the literal paths
# under ``root`` (with the ``artifacts/`` prefix) so ``_safe_file``'s
# ``relative_to(root)`` check sees a matching realpath on macOS where
# ``tempfile.TemporaryDirectory().name`` resolves through ``/private``.
_BASELINE_LOADER_SCHEMA_LAYOUT: dict[str, str] = {
    "rom-cfg-inventory-v2": "top",
    "rom-cfg-inventory-v3": "extension",
    "rom-cfg-proven-roots-v1": "extension",
    "rom-cfg-proven-roots-v2": "extension",
}

_BASELINE_LOADER_FIXTURE_ARTIFACTS: tuple[tuple[str, str, str], ...] = (
    (
        "artifacts/rom-cfg-inventory-v2",
        "rom-cfg-inventory.json",
        "rom-cfg-inventory-v2",
    ),
    (
        "artifacts/rom-cfg-inventory-v3",
        "rom-cfg-inventory-v3.json",
        "rom-cfg-inventory-v3",
    ),
    (
        "artifacts/rom-cfg-proven-roots-v1",
        "rom-cfg-proven-roots.json",
        "rom-cfg-proven-roots-v1",
    ),
    (
        "artifacts/rom-cfg-proven-roots-v2",
        "rom-cfg-proven-roots-v2.json",
        "rom-cfg-proven-roots-v2",
    ),
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


class _ResolvedTemporaryDirectory:
    """``tempfile.TemporaryDirectory`` whose ``name`` is the resolved path.

    macOS exposes ``/var/folders/...`` as a symlink to
    ``/private/var/folders/...``.  The verifier's ``_safe_file`` rejects
    inputs whose resolved path escapes ``root``, so the test must hand it
    the resolved directory or the path safety check will refuse the
    synthetic payloads before any loader contract can be exercised.
    """

    def __enter__(self) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        self._resolved = Path(self._tmp.name).resolve()
        return self._resolved

    def __exit__(self, exc_type, exc, tb) -> None:
        self._tmp.cleanup()


def _write_one_baseline_artifact(
    root: Path,
    artifact_dir: str,
    payload_name: str,
    schema: str,
    block: dict,
) -> Path:
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


def _write_four_baseline_artifacts(root: Path, block: dict) -> None:
    for artifact_dir, payload_name, schema in _BASELINE_LOADER_FIXTURE_ARTIFACTS:
        _write_one_baseline_artifact(root, artifact_dir, payload_name, schema, block)


def _build_block(start: int, end: int, **overrides) -> dict:
    body = b"\x00" * (end - start)
    block = {
        "range": [start, end],
        "mode": "thumb",
        "instruction_count": overrides.pop("instruction_count", 3),
        "bytes_sha256": overrides.pop("bytes_sha256", hashlib.sha256(body).hexdigest()),
    }
    block.update(overrides)
    return block


def _synthetic_block_decoder(
    decode_table: dict[int, tuple[int, list[dict]]],
):
    """Return a fake ``_decode`` that consults ``decode_table``.

    The real ``_decode`` uses capstone; this stub returns deterministic
    ``(size, successors)`` per offset so the loader can be exercised in
    isolation.  Offsets not present in ``decode_table`` are reported as
    decode failures so an over-iterating loader fails closed instead of
    silently dropping into the next block.
    """

    def _decode(rom: bytes, offset: int, mode: str) -> dict:
        size, successors = decode_table.get(
            offset, (0, [{"kind": "frontier", "reason": "synthetic_decode_out_of_block"}])
        )
        if not size:
            return {
                "accepted": False,
                "mode": mode,
                "file_offset": offset,
                "frontier_reason": "synthetic_decode_out_of_block",
            }
        return {
            "accepted": True,
            "mode": mode,
            "file_offset": offset,
            "size": size,
            "bytes_sha256": hashlib.sha256(b"\x00" * size).hexdigest(),
            "mnemonic": "synthetic",
            "op_str": "",
            "conditional": False,
            "flow_kind": "linear",
            "successors": successors,
            "frontiers": [],
        }

    return _decode


def _compute_frozen_baseline_payload_sha256_for(root: Path) -> dict[str, str]:
    """Compute the raw SHA256 of each synthetic frozen baseline payload
    already written under ``root`` and return a dict mapping the
    relative path ``"artifacts/<dir>/<payload>"`` to its raw SHA256.

    Use this with ``unittest.mock.patch(..., create=True)`` to inject
    the synthetic fixtures' identity into the verifier module's
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


# ---------------------------------------------------------------------------
# Test 1 — signature + per-instruction entries
# ---------------------------------------------------------------------------


class BaselineLoaderSignatureTests(unittest.TestCase):
    """§9.1 #4: frozen baseline loader must validate block metadata against
    the ROM bytes and report every per-instruction entry, not just the
    block start."""

    _BLOCK_START = 0x100
    _BLOCK_END = 0x108
    _BLOCK_BYTES = b"\x00" * (_BLOCK_END - _BLOCK_START)

    def _build_block(self, **overrides) -> dict:
        return _build_block(self._BLOCK_START, self._BLOCK_END, **overrides)

    def _build_rom(self) -> bytes:
        # 1 KiB; comfortably covers [0x100, 0x108) with zero padding.
        return b"\x00" * 0x400

    def test_baseline_loader_reports_per_instruction_entries_inside_block(
        self,
    ) -> None:
        """``_baseline_occupied_bytes`` must accept ``(root, rom)`` and
        return ``(occupied, exact_entries)`` so the verifier can validate
        frozen baseline bytes independently of the block-start shortcut.

        The synthetic decoder returns sizes 2/4/2 for offsets 0x100,
        0x102 and 0x106; those sizes sum to 8 bytes which equals the
        block length, and ``instruction_count=3`` matches the decode
        count.  A GREEN implementation must therefore return entries
        ``{('thumb', 0x100), ('thumb', 0x102), ('thumb', 0x106)}`` and
        occupied bytes ``[0x100, 0x108)``.
        """

        decode_table = {
            0x100: (
                2,
                [{"kind": "fallthrough", "mode": "thumb", "file_offset": 0x102}],
            ),
            0x102: (
                4,
                [{"kind": "fallthrough", "mode": "thumb", "file_offset": 0x106}],
            ),
            0x106: (2, []),
        }

        with _ResolvedTemporaryDirectory() as root:
            _write_four_baseline_artifacts(root, self._build_block())
            rom = self._build_rom()

            # Patch the verifier module's frozen identity table with
            # the raw SHAs of the synthetic fixtures so a future GREEN
            # identity check in ``_baseline_occupied_bytes`` does not
            # reject the synthetic fixtures as raw-byte tampered.
            frozen_shas = _compute_frozen_baseline_payload_sha256_for(root)
            with patch(
                "tools.verify_rom_battle_controller_cfg.FROZEN_BASELINE_PAYLOAD_SHA256",
                frozen_shas,
                create=True,
            ), patch(
                "tools.verify_rom_battle_controller_cfg._decode",
                side_effect=_synthetic_block_decoder(decode_table),
            ):
                result = _baseline_occupied_bytes(root, rom)

        self.assertIsInstance(
            result,
            tuple,
            msg=(
                "verifier baseline loader must return (occupied, exact_entries); "
                f"got {type(result).__name__} ({result!r})"
            ),
        )
        self.assertEqual(
            len(result),
            2,
            msg=(
                "verifier baseline loader must return exactly two values: "
                "(occupied, exact_entries)"
            ),
        )
        occupied, exact_entries = result
        self.assertEqual(
            occupied,
            set(range(self._BLOCK_START, self._BLOCK_END)),
            msg=(
                "verifier baseline loader must record every byte covered by "
                "the block range, irrespective of how many entries the loader "
                "emits; tampering with how entries are accumulated must not "
                "silently drop occupied bytes (§9.1 #4)."
            ),
        )
        self.assertEqual(
            exact_entries,
            {
                ("thumb", 0x100),
                ("thumb", 0x102),
                ("thumb", 0x106),
            },
            msg=(
                "verifier baseline loader must report one (mode, offset) "
                "entry per instruction; a buggy loader that only emits "
                "(mode, block_start) fails this contract (§9.1 #4)."
            ),
        )


# ---------------------------------------------------------------------------
# Test 2 — ValueError on metadata or block-end mismatch
# ---------------------------------------------------------------------------


class BaselineLoaderValidationTests(unittest.TestCase):
    """§9.1 #4: every inconsistency between the frozen block metadata and
    the ROM bytes (or the decoder's per-instruction walk) must raise
    ``ValueError``.  Three single-point tampers prove the contract."""

    _BLOCK_START = 0x100
    _BLOCK_END = 0x108

    def _build_block(self, **overrides) -> dict:
        return _build_block(self._BLOCK_START, self._BLOCK_END, **overrides)

    def _build_rom(self) -> bytes:
        return b"\x00" * 0x400

    def test_baseline_loader_rejects_inconsistencies(self) -> None:
        decode_table_correct = {
            0x100: (
                2,
                [{"kind": "fallthrough", "mode": "thumb", "file_offset": 0x102}],
            ),
            0x102: (
                4,
                [{"kind": "fallthrough", "mode": "thumb", "file_offset": 0x106}],
            ),
            0x106: (2, []),
        }

        # Variant A — instruction_count disagrees with the decoder.
        with self.subTest("instruction_count mismatch"):
            with _ResolvedTemporaryDirectory() as root:
                _write_four_baseline_artifacts(
                    root, self._build_block(instruction_count=2)
                )
                rom = self._build_rom()
                # Patch the verifier module's frozen identity table
                # with the raw SHAs of the synthetic fixtures so a
                # future GREEN identity check does not reject the
                # synthetic fixtures as raw-byte tampered.
                frozen_shas = _compute_frozen_baseline_payload_sha256_for(root)
                with patch(
                    "tools.verify_rom_battle_controller_cfg.FROZEN_BASELINE_PAYLOAD_SHA256",
                    frozen_shas,
                    create=True,
                ), patch(
                    "tools.verify_rom_battle_controller_cfg._decode",
                    side_effect=_synthetic_block_decoder(decode_table_correct),
                ):
                    with self.assertRaises(ValueError):
                        _baseline_occupied_bytes(root, rom)

        # Variant B — bytes_sha256 disagrees with sha256(rom[start:end]).
        wrong_sha = "11" * 32
        self.assertNotEqual(
            wrong_sha,
            hashlib.sha256(b"\x00" * (self._BLOCK_END - self._BLOCK_START)).hexdigest(),
        )
        with self.subTest("bytes_sha256 mismatch"):
            with _ResolvedTemporaryDirectory() as root:
                _write_four_baseline_artifacts(
                    root, self._build_block(bytes_sha256=wrong_sha)
                )
                rom = self._build_rom()
                # Patch the verifier module's frozen identity table
                # with the raw SHAs of the synthetic fixtures so a
                # future GREEN identity check does not reject the
                # synthetic fixtures as raw-byte tampered.
                frozen_shas = _compute_frozen_baseline_payload_sha256_for(root)
                with patch(
                    "tools.verify_rom_battle_controller_cfg.FROZEN_BASELINE_PAYLOAD_SHA256",
                    frozen_shas,
                    create=True,
                ), patch(
                    "tools.verify_rom_battle_controller_cfg._decode",
                    side_effect=_synthetic_block_decoder(decode_table_correct),
                ):
                    with self.assertRaises(ValueError):
                        _baseline_occupied_bytes(root, rom)

        # Variant C — the per-instruction decode sizes overshoot the
        # block end.  0x106 + 4 = 0x10A > 0x108.
        decode_table_overshoot = {
            0x100: (
                2,
                [{"kind": "fallthrough", "mode": "thumb", "file_offset": 0x102}],
            ),
            0x102: (
                4,
                [{"kind": "fallthrough", "mode": "thumb", "file_offset": 0x106}],
            ),
            0x106: (4, []),
        }
        with self.subTest("decode size overshoots block end"):
            with _ResolvedTemporaryDirectory() as root:
                _write_four_baseline_artifacts(root, self._build_block())
                rom = self._build_rom()
                # Patch the verifier module's frozen identity table
                # with the raw SHAs of the synthetic fixtures so a
                # future GREEN identity check does not reject the
                # synthetic fixtures as raw-byte tampered.
                frozen_shas = _compute_frozen_baseline_payload_sha256_for(root)
                with patch(
                    "tools.verify_rom_battle_controller_cfg.FROZEN_BASELINE_PAYLOAD_SHA256",
                    frozen_shas,
                    create=True,
                ), patch(
                    "tools.verify_rom_battle_controller_cfg._decode",
                    side_effect=_synthetic_block_decoder(decode_table_overshoot),
                ):
                    with self.assertRaises(ValueError):
                        _baseline_occupied_bytes(root, rom)


# ---------------------------------------------------------------------------
# Test 3 — bounded traversal: legal entries vs. middle-of-instruction
# ---------------------------------------------------------------------------


class BoundedTraversalBaselineEntriesTests(unittest.TestCase):
    """§9.1 #4: ``_rebuild_bounded`` must take both ``baseline_entries`` and
    ``baseline_occupied`` so the verifier can distinguish legal entry
    points (which may become opaque / skipped) from middle-of-instruction
    hits (which must raise).  Today the verifier's signature is
    ``(rom, roots, baseline_occupied)``; both keywords below are unknown
    and the call RED-fails on a TypeError until the GREEN refactor wires
    them through."""

    _TEST_RANGE = (0x100, 0x300)
    _SYNTHETIC_ROM = b"\x00" * 0x400  # 1 KiB; comfortably covers _TEST_RANGE.

    def setUp(self) -> None:
        # patch.dict semantics would clobber the module dict; restore the
        # constant in tearDown instead.
        self._saved_range = CONTROLLER_RANGE
        self._patcher = patch(
            "tools.verify_rom_battle_controller_cfg.CONTROLLER_RANGE",
            self._TEST_RANGE,
        )
        self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()
        # Belt-and-braces: never let a tainted module constant leak into
        # other tests in this process.
        import tools.verify_rom_battle_controller_cfg as verifier

        verifier.CONTROLLER_RANGE = self._saved_range

    def test_target_in_occupied_but_outside_entries_raises(self) -> None:
        """A CFG edge whose target lands inside ``baseline_occupied`` but
        is not a member of ``baseline_entries`` is a hit on the middle of
        a frozen baseline instruction.  The verifier must raise
        ``ValueError`` rather than mis-labelling it as
        ``frozen_baseline_entry`` (which would silently drop the entry
        from the worklist) — §9.1 #4."""

        baseline_entries = {("thumb", 0x140)}  # only the legal entry
        baseline_occupied = {0x140, 0x141, 0x142, 0x143}  # full 4-byte BL
        root_offset = 0x130  # inside _TEST_RANGE, not in baseline
        target_middle = 0x142  # middle of the 4-byte BL

        synthetic_decoded = {
            "accepted": True,
            "mode": "thumb",
            "file_offset": root_offset,
            "size": 2,
            "bytes_sha256": hashlib.sha256(b"\x00" * 2).hexdigest(),
            "mnemonic": "synthetic",
            "op_str": "",
            "conditional": False,
            "flow_kind": "linear",
            "successors": [
                {
                    "kind": "branch_target",
                    "mode": "thumb",
                    "file_offset": target_middle,
                },
            ],
            "frontiers": [],
        }

        with patch(
            "tools.verify_rom_battle_controller_cfg._decode",
            return_value=synthetic_decoded,
        ):
            # The new contract: ``_rebuild_bounded`` takes both
            # ``baseline_entries`` and ``baseline_occupied``.  Today the
            # signature is ``(rom, roots, baseline_occupied)`` so the
            # ``baseline_entries`` keyword raises ``TypeError`` and the
            # test is RED at the boundary.  A GREEN fix that wires the
            # new parameter through must raise ``ValueError`` with a
            # message that mentions the middle-of-instruction condition
            # — never silently record the hit as ``frozen_baseline_entry``.
            with self.assertRaises(ValueError) as context:
                _rebuild_bounded(
                    self._SYNTHETIC_ROM,
                    [{"target_offset": root_offset}],
                    baseline_entries=baseline_entries,
                    baseline_occupied=baseline_occupied,
                )
        # A silent regression that turned the middle hit into an opaque
        # edge would surface as an opaque list — assert the raise is
        # the contract failure, not a swallowed exception.
        self.assertNotIsInstance(
            context.exception, TypeError,
            msg=(
                "Once the GREEN refactor wires baseline_entries through, "
                "the call must raise ValueError on a middle-of-instruction "
                "hit, not TypeError on an unknown keyword."
            ),
        )


# ---------------------------------------------------------------------------
# Test 4 — source-text boundary: verifier must not import exporter helpers
# ---------------------------------------------------------------------------


class VerifierExporterBoundaryTests(unittest.TestCase):
    """§9.1 #4: the verifier must rebuild the bounded CFG independently of
    the exporter.  A future refactor that re-introduces the cross-module
    dependency would re-create exactly the bug the hand-off describes
    (silently trusting a single block-start entry, no per-instruction
    validation).  This source-text assertion fails closed if anyone
    tries to ``import tools.export_rom_battle_controller_cfg`` from the
    verifier or invokes any exporter helper."""

    def test_verifier_source_does_not_import_exporter_controller_module(self) -> None:
        source = VERIFIER_SOURCE_PATH.read_text(encoding="utf-8")

        forbidden_imports = (
            "from tools.export_rom_battle_controller_cfg",
            "import tools.export_rom_battle_controller_cfg",
        )
        for needle in forbidden_imports:
            self.assertNotIn(
                needle,
                source,
                msg=(
                    "verifier must independently rebuild the bounded CFG; "
                    f"forbidden import {needle!r} found in the verifier "
                    "source — this re-introduces the §9.1 #4 dependency "
                    "the hand-off explicitly forbids."
                ),
            )

        # Helper invocations must not call into the exporter module by
        # qualified name.  ``getattr(..., call)`` would still resolve to
        # the exporter helper, so we explicitly check for the qualified
        # ``tools.export_rom_battle_controller_cfg.<helper>`` form.
        forbidden_calls = (
            "tools.export_rom_battle_controller_cfg._baseline_occupied_bytes",
            "tools.export_rom_battle_controller_cfg._bounded_root_records",
            "tools.export_rom_battle_controller_cfg._dispatch_denominator",
            "tools.export_rom_battle_controller_cfg._traverse_bounded",
        )
        for needle in forbidden_calls:
            self.assertNotIn(
                needle,
                source,
                msg=(
                    "verifier must not call into the exporter's controller "
                    f"helpers; forbidden call {needle!r} found in the "
                    "verifier source."
                ),
            )


# ---------------------------------------------------------------------------
# Test 5 — verifier per-root closure (handoff §9.1 #5)
# ---------------------------------------------------------------------------
#
# The exporter's ``_bounded_root_records`` walks the CFG block-successor
# worklist (blocks[*].successors[*].block_id) and reports the per-root
# reachable instruction count.  The verifier today only checks
# ``entry_sha256``, ``entry_size``, ``target_offset``, and the
# ``source_states[0]`` mapping — it does NOT independently recompute
# ``reachable_instruction_count`` against ``extension.blocks`` and it does
# NOT compare per-root ``entry_block_id`` or full ``source_states`` against
# an independent rebuild.  A tampered artifact root that keeps the entry
# hash and dispatcher state intact but lies about its block identity or
# reachable count would slip through.
#
# The two tests below use a 2-block / 5-member synthetic fixture (block-A
# has 2 members, block-B has 3, block-A.successors[0].block_id points to
# block-B) and assert that the verifier exposes two private helpers
# that close this gap:
#
#   * ``_expected_root_records(root_records, blocks, member_to_block)``
#     walks the block-successor worklist and returns at least
#     ``{target_offset, entry_block_id, reachable_instruction_count,
#     source_states}`` per record.
#   * ``_verify_root_records_contract(artifact, expected)`` raises
#     ``ValueError`` on a tamper of any of those three fields, length
#     mismatch, or missing field.
#
# Both helpers do not exist today, so the tests RED at the
# ``getattr(..., None)`` boundary before any behaviour assertion runs.
# A GREEN refactor that wires both helpers into
# ``verify_rom_battle_controller_cfg`` (e.g. comparing
# ``payload["roots"]`` against ``_expected_root_records`` via
# ``_verify_root_records_contract``) will turn them GREEN.  The tests do
# not import the exporter, do not touch the artifact directory, and do
# not require the real ROM.


class _VerifierRootRecordFixture:
    """Synthetic 2-block / 5-member CFG used by the per-root closure tests.

    * ``block-A`` covers members at 0x150 / 0x152 (2 nodes).
    * ``block-B`` covers members at 0x160 / 0x162 / 0x164 (3 nodes).
    * ``block-A.successors[0].block_id = "block-B"`` so the worklist
      expands to block-B via the canonical ``block_id`` edge.
    * The single root is rooted at 0x150, i.e. inside block-A.
    """

    BLOCK_A_ID = "block-A"
    BLOCK_B_ID = "block-B"
    ROOT_OFFSET = 0x150

    BLOCK_A_RANGE = (0x150, 0x154)
    BLOCK_B_RANGE = (0x160, 0x166)

    @classmethod
    def member_to_block(cls) -> dict:
        return {
            ("thumb", 0x150): cls.BLOCK_A_ID,
            ("thumb", 0x152): cls.BLOCK_A_ID,
            ("thumb", 0x160): cls.BLOCK_B_ID,
            ("thumb", 0x162): cls.BLOCK_B_ID,
            ("thumb", 0x164): cls.BLOCK_B_ID,
        }

    @classmethod
    def blocks(cls) -> list:
        return [
            {
                "id": cls.BLOCK_A_ID,
                "mode": "thumb",
                "range": list(cls.BLOCK_A_RANGE),
                "instruction_count": 2,
                "bytes_sha256": "00" * 32,
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
                        "block_id": cls.BLOCK_B_ID,
                    },
                ],
            },
            {
                "id": cls.BLOCK_B_ID,
                "mode": "thumb",
                "range": list(cls.BLOCK_B_RANGE),
                "instruction_count": 3,
                "bytes_sha256": "00" * 32,
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

    @classmethod
    def root_records(cls) -> list:
        return [
            {
                "target_offset": cls.ROOT_OFFSET,
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


class VerifierRootRecordWorklistTests(unittest.TestCase):
    """§9.1 #5: the verifier must independently rebuild the per-root
    ``reachable_instruction_count`` via the block-successor worklist and
    must compare it (plus ``entry_block_id`` and ``source_states``)
    against the artifact root records in the payload.

    Both helpers below are missing from
    ``tools.verify_rom_battle_controller_cfg`` today; the tests RED at
    the ``getattr(..., None)`` boundary.  A GREEN refactor that adds
    the helpers and reuses them in
    ``verify_rom_battle_controller_cfg`` will turn them GREEN.
    """

    _EXPECTED_REBUILD_HELPER = "_expected_root_records"
    _CONTRACT_HELPER = "_verify_root_records_contract"
    _PROJECTION_HELPER = "_artifact_root_projection"

    def _verifier_module(self):
        import tools.verify_rom_battle_controller_cfg as verifier

        return verifier

    def test_artifact_root_projection_preserves_artifact_fields(self) -> None:
        """Projection must copy artifact root fields without expected-data backfill."""
        verifier = self._verifier_module()
        helper_obj = getattr(verifier, self._PROJECTION_HELPER, None)
        self.assertIsNotNone(
            helper_obj,
            msg=(
                "verifier must expose '_artifact_root_projection' to preserve "
                "artifact root fields before contract validation."
            ),
        )
        helper = cast(Callable[..., Any], helper_obj)
        fixture = _VerifierRootRecordFixture
        artifact = fixture.root_records()
        artifact[0] = dict(artifact[0])
        artifact[0]["entry_block_id"] = "tampered-block"
        artifact[0]["reachable_instruction_count"] = 999

        projection = helper(artifact)
        self.assertEqual(projection[0]["target_offset"], fixture.ROOT_OFFSET)
        self.assertEqual(projection[0]["entry_block_id"], "tampered-block")
        self.assertEqual(projection[0]["reachable_instruction_count"], 999)
        self.assertEqual(projection[0]["source_states"], [0x1234])

        rebuild = getattr(verifier, self._EXPECTED_REBUILD_HELPER)
        contract = getattr(verifier, self._CONTRACT_HELPER)
        expected = rebuild(
            fixture.root_records(), fixture.blocks(), fixture.member_to_block()
        )
        with self.assertRaises(ValueError):
            contract(projection, expected)

    def test_root_record_rebuild_walks_block_successor_edges(self) -> None:
        """Helper must walk ``blocks[*].successors[*].block_id`` and report
        ``reachable_instruction_count = 5`` for the 2-block / 5-member
        fixture (block-A 2 members + block-B 3 members reached via the
        successor edge).  A buggy implementation that only counts the
        entry block's nodes returns 2."""

        verifier = self._verifier_module()
        helper_obj = getattr(verifier, self._EXPECTED_REBUILD_HELPER, None)
        self.assertIsNotNone(
            helper_obj,
            msg=(
                "verifier must expose "
                f"{self._EXPECTED_REBUILD_HELPER!r} helper to "
                "independently rebuild per-root records via the "
                "block-successor worklist (§9.1 #5)."
            ),
        )
        helper = cast(Callable[..., Any], helper_obj)

        fixture = _VerifierRootRecordFixture
        root_records = fixture.root_records()
        result = helper(
            root_records,
            fixture.blocks(),
            fixture.member_to_block(),
        )

        self.assertIsInstance(
            result,
            list,
            msg=(
                f"{self._EXPECTED_REBUILD_HELPER} must return a list of "
                f"per-root records; got {type(result).__name__} ({result!r})"
            ),
        )
        self.assertEqual(
            len(result),
            len(root_records),
            msg=(
                f"{self._EXPECTED_REBUILD_HELPER} must return one record "
                "per input root; the verifier GREEN step will compare "
                "this list against the artifact's payload['roots']."
            ),
        )
        record = result[0]
        self.assertEqual(
            record.get("entry_block_id"),
            fixture.BLOCK_A_ID,
            msg=(
                "entry_block_id must be the block that contains the root's "
                "target_offset; a buggy implementation that ignores the "
                "member_to_block map would return None or a wrong id "
                "(§9.1 #5)."
            ),
        )
        self.assertEqual(
            record.get("reachable_instruction_count"),
            5,
            msg=(
                "reachable_instruction_count must come from a block-successor "
                "worklist: block-A's 2 members plus block-B's 3 members "
                "reached via the canonical block_id edge.  An implementation "
                "that only counts the entry block returns 2; one that walks "
                "the full member map without following successor edges would "
                "overcount.  A correct implementation returns 5 (§9.1 #5)."
            ),
        )
        # source_states must round-trip from the input root record so the
        # contract helper has a meaningful expected value to compare
        # against (test 2 below).  This is a structural assertion, not a
        # tamper check.
        self.assertEqual(
            record.get("source_states"),
            root_records[0]["source_states"],
            msg=(
                f"{self._EXPECTED_REBUILD_HELPER} must preserve source_states "
                "from the input record so the contract helper can compare it."
            ),
        )

    def test_root_record_contract_rejects_tampered_fields(self) -> None:
        """``_verify_root_records_contract`` must raise ``ValueError`` when
        any of ``entry_block_id``, ``reachable_instruction_count``, or
        ``source_states`` is tampered on the artifact side.  Three
        subTests lock each field; a regression that only checks
        ``target_offset`` membership (as today) would let all three
        variants pass silently and the test fails closed."""

        verifier = self._verifier_module()
        rebuild_obj = getattr(verifier, self._EXPECTED_REBUILD_HELPER, None)
        contract_obj = getattr(verifier, self._CONTRACT_HELPER, None)
        self.assertIsNotNone(
            rebuild_obj,
            msg=(
                "verifier must expose "
                f"{self._EXPECTED_REBUILD_HELPER!r} so the contract helper "
                "has a deterministic expected value to compare against."
            ),
        )
        self.assertIsNotNone(
            contract_obj,
            msg=(
                "verifier must expose "
                f"{self._CONTRACT_HELPER!r} to reject tampered per-root "
                "fields on the artifact side (§9.1 #5)."
            ),
        )
        rebuild = cast(Callable[..., Any], rebuild_obj)
        contract = cast(Callable[..., Any], contract_obj)

        fixture = _VerifierRootRecordFixture
        # Build the canonical expected record by running the rebuild
        # helper on a clean fixture.  This is the value the contract
        # helper will compare the artifact side against.
        expected = rebuild(
            fixture.root_records(),
            fixture.blocks(),
            fixture.member_to_block(),
        )
        canonical_artifact = {
            "target_offset": fixture.ROOT_OFFSET,
            "entry_block_id": fixture.BLOCK_A_ID,
            "reachable_instruction_count": 5,
            "source_states": [0x1234],
        }

        tamper_specs = (
            (
                "reachable_instruction_count bumped",
                {"reachable_instruction_count": 6},
            ),
            (
                "entry_block_id retargeted",
                {"entry_block_id": "block-X"},
            ),
            (
                "source_states replaced with disjoint state",
                {"source_states": [0x9999]},
            ),
        )

        for label, override in tamper_specs:
            with self.subTest(label):
                tampered = dict(canonical_artifact)
                tampered.update(override)
                with self.assertRaises(
                    ValueError,
                    msg=(
                        "_verify_root_records_contract must raise ValueError "
                        f"when {label!r}; a regression that only checks "
                        "entry_sha256/source_states[0] membership (as today) "
                        "would let this tamper through silently (§9.1 #5)."
                    ),
                ):
                    contract([tampered], expected)


# ---------------------------------------------------------------------------
# §9.1 #4 — frozen baseline identity contract for the verifier.
#
# Mirrors the exporter-side identity contract: the verifier must expose
# ``FROZEN_BASELINE_PAYLOAD_SHA256`` as a module-level dict with the
# same four payload mappings, and ``_baseline_occupied_bytes`` must
# raise ``ValueError`` when ONE of the four payloads is silently
# tampered (a semantically harmless extra top-level field that does
# not affect the parsed shape) after the module constant has been
# patched to match the unaltered fixtures.
#
# The verifier source must not import the exporter (already locked
# by ``VerifierExporterBoundaryTests``); the verifier's identity
# table is therefore an independent module-level constant, not a
# re-export.
# ---------------------------------------------------------------------------


_FROZEN_BASELINE_PAYLOAD_RELATIVE_PATHS: tuple[str, ...] = (
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


# ---------------------------------------------------------------------------
# §9.1 #5 — independently skipped root targets (dispatcher root 0x074918)
#
# The dispatcher root at ``0x074918`` is also a frozen producer
# instruction entry.  The exporter correctly treats it as a
# frozen-baseline opaque stop (entry_block_id=null,
# reachable_instruction_count=0), but today's verifier blindly enforces
# "every root must land in some block", which raises
# ``root target escapes blocks`` and fails the build.  Bypassing the
# check by re-adding the producer to the new CFG is forbidden by the
# frozen baseline contract.
#
# The fix is to teach the verifier that some roots are intentionally
# opaque: an explicit caller-provided set
# ``independently_skipped_root_targets: set[int]`` names the target
# offsets that are allowed to escape the block map.  The rebuild helper
# must emit a record with ``entry_block_id=None`` and
# ``reachable_instruction_count=0`` for each such target while
# preserving ``target_offset`` and ``source_states`` so the artifact
# projection can keep the skipped record verbatim.  A root that escapes
# blocks AND is not in the caller's set must still fail closed with
# ``root target escapes blocks``.
#
# The three tests below lock this contract.  They do not import the
# exporter, do not touch the artifact directory, do not require the
# real ROM, and do not implement product code.  The first and third
# tests RED at the signature boundary (``TypeError`` on the unknown
# keyword) until the GREEN refactor adds the keyword-only parameter;
# the second test REDs at the projection boundary because today's
# projection rejects ``None`` and ``0`` outright.
# ---------------------------------------------------------------------------


class SkippedRootTargetsContractTests(unittest.TestCase):
    """§9.1 #5: ``_expected_root_records`` must accept a keyword-only
    ``independently_skipped_root_targets: set[int]`` parameter and emit
    ``entry_block_id=None`` / ``reachable_instruction_count=0`` records
    for each listed target that escapes ``member_to_block``; the
    artifact projection must preserve those ``None`` / ``0`` records
    verbatim; an unlisted escape must still fail closed with
    ``root target escapes blocks``.

    Three sub-tests lock these contracts.
    """

    _SKIPPED_TARGET = 0x074918  # the real failing dispatcher root
    _NORMAL_TARGET = 0x074920
    _BLOCK_ID = "block-A"

    _EXPECTED_REBUILD_HELPER = "_expected_root_records"
    _PROJECTION_HELPER = "_artifact_root_projection"

    def _verifier_module(self):
        import tools.verify_rom_battle_controller_cfg as verifier

        return verifier

    def _build_blocks(self) -> list:
        return [
            {
                "id": self._BLOCK_ID,
                "mode": "thumb",
                "range": [self._NORMAL_TARGET, self._NORMAL_TARGET + 4],
                "instruction_count": 2,
                "bytes_sha256": "00" * 32,
                "terminator": {
                    "file_offset": self._NORMAL_TARGET + 2,
                    "size": 2,
                    "mnemonic": "bx",
                    "op_str": "lr",
                    "flow_kind": "return",
                    "conditional": False,
                },
                "successors": [],
            },
        ]

    def _build_member_to_block(self) -> dict:
        return {
            ("thumb", self._NORMAL_TARGET): self._BLOCK_ID,
            ("thumb", self._NORMAL_TARGET + 2): self._BLOCK_ID,
        }

    def _build_root_records(self) -> list:
        return [
            {
                "target_offset": self._SKIPPED_TARGET,
                "gba_address": f"0x{self._SKIPPED_TARGET + 0x08000000:08X}",
                "entry_sha256": "a" * 64,
                "entry_size": 2,
                "source_states": [0x1234],
                "dispatch_transfer": {
                    "transfer_offset": 0x100,
                    "transfer_kind": "branch_target",
                    "transfer_raw_hex": "abcd",
                },
            },
            {
                "target_offset": self._NORMAL_TARGET,
                "gba_address": f"0x{self._NORMAL_TARGET + 0x08000000:08X}",
                "entry_sha256": "b" * 64,
                "entry_size": 2,
                "source_states": [0x5678],
                "dispatch_transfer": {
                    "transfer_offset": 0x100,
                    "transfer_kind": "branch_target",
                    "transfer_raw_hex": "ef01",
                },
            },
        ]

    # ---- Test 1 -------------------------------------------------------

    def test_expected_root_records_emits_none_zero_for_skipped_root(
        self,
    ) -> None:
        """``_expected_root_records`` must accept a keyword-only
        ``independently_skipped_root_targets: set[int]`` argument and
        emit a record with ``entry_block_id=None`` and
        ``reachable_instruction_count=0`` for each listed target that
        is absent from ``member_to_block``.  ``target_offset`` and
        ``source_states`` must round-trip so the contract helper has
        a meaningful value to compare against.

        Today the verifier's signature is
        ``(root_records, blocks, member_to_block)`` with no
        ``independently_skipped_root_targets`` keyword, so the call
        raises ``TypeError`` on the unknown keyword and the test is
        RED at the signature boundary.  A GREEN refactor that wires
        the keyword through turns this test GREEN.
        """

        verifier = self._verifier_module()
        helper_obj = getattr(verifier, self._EXPECTED_REBUILD_HELPER, None)
        self.assertIsNotNone(
            helper_obj,
            msg=(
                "verifier must expose "
                f"{self._EXPECTED_REBUILD_HELPER!r} so the skipped-root "
                "contract has a deterministic value to assert against "
                "(§9.1 #5)."
            ),
        )
        helper = cast(Callable[..., Any], helper_obj)

        result = helper(
            self._build_root_records(),
            self._build_blocks(),
            self._build_member_to_block(),
            independently_skipped_root_targets={self._SKIPPED_TARGET},
        )

        # Two records: one skipped (0x074918) and one normal (0x074920).
        self.assertEqual(
            len(result),
            2,
            msg=(
                f"{self._EXPECTED_REBUILD_HELPER} must return one record "
                "per input root, including the independently skipped one."
            ),
        )

        skipped_record = result[0]
        self.assertEqual(
            skipped_record.get("target_offset"),
            self._SKIPPED_TARGET,
            msg=(
                "the independently-skipped record must round-trip "
                "target_offset so downstream comparison can match by key."
            ),
        )
        self.assertIsNone(
            skipped_record.get("entry_block_id"),
            msg=(
                "the independently-skipped record must carry "
                "entry_block_id=None; the frozen-baseline opaque stop is "
                "not part of any new CFG block, so the caller-provided set "
                "— not the artifact's entry_block_id or count — is the "
                "sole signal that the record is skipped."
            ),
        )
        self.assertEqual(
            skipped_record.get("reachable_instruction_count"),
            0,
            msg=(
                "the independently-skipped record must carry "
                "reachable_instruction_count=0; the skipped root has no "
                "new CFG block successors."
            ),
        )
        self.assertEqual(
            skipped_record.get("source_states"),
            [0x1234],
            msg=(
                "the independently-skipped record must round-trip "
                "source_states so the contract helper can compare it "
                "against the artifact side verbatim."
            ),
        )

        # Normal record: must still resolve to the block it lives in.
        normal_record = result[1]
        self.assertEqual(
            normal_record.get("target_offset"),
            self._NORMAL_TARGET,
            msg=(
                "the normal record must round-trip target_offset so the "
                "skipped and normal records are distinguishable by key."
            ),
        )
        self.assertEqual(
            normal_record.get("entry_block_id"),
            self._BLOCK_ID,
            msg=(
                "the normal record must resolve entry_block_id via "
                "member_to_block; only the independently-skipped target "
                "is allowed to escape the block map."
            ),
        )

    # ---- Test 2 -------------------------------------------------------

    def test_artifact_root_projection_preserves_none_zero_skipped_records(
        self,
    ) -> None:
        """``_artifact_root_projection`` must preserve a
        ``None`` / ``0`` skipped record verbatim — no early rejection
        on non-string ``entry_block_id`` or non-positive
        ``reachable_instruction_count``.  Normal block-root records
        with non-empty string and positive count must still pass
        through unchanged; an empty-string ``entry_block_id`` or a
        ``reachable_instruction_count <= 0`` on a non-skipped record
        must still be rejected.

        Today the projection rejects ``entry_block_id=None`` and
        ``reachable_instruction_count=0`` outright, so the
        skipped-record leg is RED.  The non-skipped legs
        (non-empty string, positive count, empty-string rejection,
        zero-count rejection) are GREEN today and stay GREEN as
        regression guards.

        The skipped decision lives in ``_expected_root_records`` via
        the caller-provided set; the projection must not infer skip
        from the artifact's ``entry_block_id`` or count — it only
        preserves the four contract fields verbatim.
        """

        verifier = self._verifier_module()
        helper_obj = getattr(verifier, self._PROJECTION_HELPER, None)
        self.assertIsNotNone(
            helper_obj,
            msg=(
                "verifier must expose "
                f"{self._PROJECTION_HELPER!r} so the skipped-root "
                "contract can preserve None/0 records."
            ),
        )
        helper = cast(Callable[..., Any], helper_obj)

        skipped_record = {
            "target_offset": self._SKIPPED_TARGET,
            "entry_block_id": None,
            "reachable_instruction_count": 0,
            "source_states": [0x1234],
        }
        normal_record = {
            "target_offset": self._NORMAL_TARGET,
            "entry_block_id": self._BLOCK_ID,
            "reachable_instruction_count": 2,
            "source_states": [0x5678],
        }

        # Skipped record: must be preserved verbatim.  Today's
        # projection rejects entry_block_id=None and
        # reachable_instruction_count=0, so this leg is RED.
        projection = helper([skipped_record])
        self.assertEqual(
            projection,
            [skipped_record],
            msg=(
                "artifact projection must preserve a None/0 skipped "
                "record verbatim — no early rejection on non-string "
                "entry_block_id or non-positive "
                "reachable_instruction_count.  Inferring skip from the "
                "artifact's entry_block_id or count is forbidden; the "
                "decision lives in _expected_root_records via the "
                "caller-provided set."
            ),
        )

        # Normal record: must pass through unchanged.  This is GREEN
        # today and stays GREEN as a regression guard.
        projection = helper([normal_record])
        self.assertEqual(
            projection,
            [normal_record],
            msg=(
                "artifact projection must pass a non-empty-string and "
                "positive-count record through unchanged."
            ),
        )

        # Empty-string entry_block_id on a non-skipped record must
        # still be rejected.  This is GREEN today and stays GREEN as
        # a regression guard.
        with self.assertRaises(ValueError):
            helper(
                [
                    {
                        "target_offset": self._NORMAL_TARGET,
                        "entry_block_id": "",
                        "reachable_instruction_count": 2,
                        "source_states": [0x5678],
                    }
                ]
            )

        # reachable_instruction_count == 0 on a non-skipped record
        # must still be rejected.  This is GREEN today and stays
        # GREEN as a regression guard.
        with self.assertRaises(ValueError):
            helper(
                [
                    {
                        "target_offset": self._NORMAL_TARGET,
                        "entry_block_id": self._BLOCK_ID,
                        "reachable_instruction_count": 0,
                        "source_states": [0x5678],
                    }
                ]
            )

    # ---- Test 3 -------------------------------------------------------

    def test_expected_root_records_fails_closed_for_unskipped_escape(
        self,
    ) -> None:
        """A root whose ``target_offset`` is absent from both
        ``member_to_block`` AND ``independently_skipped_root_targets``
        must still fail closed with ``ValueError`` whose message
        mentions ``root target escapes blocks``.  The skipped-root
        opt-out is a precise caller-provided allowlist, not a free
        pass: an unlisted target that escapes the block map is still
        a real inconsistency between the exporter's dispatcher and
        the new CFG blocks, and the verifier must surface it.

        Today the verifier accepts no keyword argument, so the call
        raises ``TypeError`` on the unknown keyword and the test is
        RED at the signature boundary.  A GREEN refactor must keep
        the fail-closed branch reachable through the new keyword —
        no silently-swallowed escape.
        """

        verifier = self._verifier_module()
        helper_obj = getattr(verifier, self._EXPECTED_REBUILD_HELPER, None)
        self.assertIsNotNone(
            helper_obj,
            msg=(
                "verifier must expose "
                f"{self._EXPECTED_REBUILD_HELPER!r} so the fail-closed "
                "branch has a deterministic call site to assert against."
            ),
        )
        helper = cast(Callable[..., Any], helper_obj)

        # Single root, target not in member_to_block, AND not in the
        # caller's skipped set.  A correct implementation must raise
        # ``ValueError`` mentioning ``root target escapes blocks``.
        with self.assertRaises(ValueError) as context:
            helper(
                [
                    {
                        "target_offset": self._SKIPPED_TARGET,
                        "source_states": [0x1234],
                    }
                ],
                self._build_blocks(),
                self._build_member_to_block(),
                independently_skipped_root_targets=set(),
            )
        self.assertIn(
            "root target escapes blocks",
            str(context.exception),
            msg=(
                "an unlisted root that escapes the block map must still "
                "fail closed with a message that names the offending "
                "condition; a GREEN refactor that swallows the failure "
                "behind the new keyword is a regression."
            ),
        )


class FrozenBaselineIdentityContractTests(unittest.TestCase):
    """§9.1 #4: the verifier's bounded CFG loader must refuse any silent
    tamper of the four frozen baseline JSON payloads.

    Two contracts are pinned here:

    1. The verifier module exposes its own module-level constant
       ``FROZEN_BASELINE_PAYLOAD_SHA256`` with the same four payload
       mappings as the exporter (independent definition; not a
       re-export from ``tools.export_rom_battle_controller_cfg``).

    2. ``_baseline_occupied_bytes`` raises ``ValueError`` when ONE
       of the four payloads is silently tampered (a semantically
       harmless extra top-level field) after the verifier's module
       constant has been patched to match the unaltered fixtures.
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

    def test_verifier_module_exposes_frozen_baseline_payload_sha256_constant(
        self,
    ) -> None:
        """The verifier module must expose its own
        ``FROZEN_BASELINE_PAYLOAD_SHA256`` constant with the same
        four payload mappings as the exporter.  The verifier source
        must not import the exporter (already locked by
        ``VerifierExporterBoundaryTests``), so this constant is an
        independent module-level definition.

        Without this identity table the verifier has no way to
        detect a payload tamper that preserves the parsed shape
        (deleting a legitimate block, adding a harmless extra
        field, or replacing the file with a self-consistent
        subset).  The constant is the canonical reference the
        GREEN identity check in ``_baseline_occupied_bytes``
        compares against.
        """

        import tools.verify_rom_battle_controller_cfg as verifier

        self.assertTrue(
            hasattr(verifier, "FROZEN_BASELINE_PAYLOAD_SHA256"),
            msg=(
                "verifier module must expose its own "
                "FROZEN_BASELINE_PAYLOAD_SHA256 as a module-level "
                "constant; the bounded CFG identity contract is "
                "unanchored without it (§9.1 #4)."
            ),
        )
        const = verifier.FROZEN_BASELINE_PAYLOAD_SHA256
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
                "FROZEN_BASELINE_PAYLOAD_SHA256 must map exactly "
                "the four frozen baseline payloads; an extra key "
                "leaks a non-canonical payload, a missing key "
                "lets the loader skip the identity check for that "
                "payload (§9.1 #4)."
            ),
        )
        # Each value must be the canonical raw SHA256.
        for rel_path, expected_sha in _FROZEN_BASELINE_PAYLOAD_SHA256.items():
            self.assertEqual(
                const.get(rel_path),
                expected_sha,
                msg=(
                    f"FROZEN_BASELINE_PAYLOAD_SHA256[{rel_path!r}] "
                    f"must be the canonical raw SHA256; got "
                    f"{const.get(rel_path)!r}, expected "
                    f"{expected_sha!r}."
                ),
            )

    # ---- contract 2 ---------------------------------------------------

    def test_adding_harmless_extra_to_one_payload_triggers_value_error(
        self,
    ) -> None:
        """Adding a semantically harmless extra top-level field to ONE
        of the four frozen baseline JSON payloads (without updating
        the verifier module's ``FROZEN_BASELINE_PAYLOAD_SHA256``)
        must cause ``_baseline_occupied_bytes`` to raise
        ``ValueError``.

        Sequence:

        1. Write four synthetic payloads (no extras).
        2. Compute each payload's raw SHA256 and patch the verifier
           module's ``FROZEN_BASELINE_PAYLOAD_SHA256`` to match.
           This is the GREEN reference the loader compares against.
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
                [{"kind": "fallthrough", "mode": "thumb", "file_offset": self._BLOCK_START + 2}],
            ),
            self._BLOCK_START + 2: (
                4,
                [{"kind": "fallthrough", "mode": "thumb", "file_offset": self._BLOCK_START + 6}],
            ),
            self._BLOCK_START + 6: (2, []),
        }

        with _ResolvedTemporaryDirectory() as root:
            _write_four_baseline_artifacts(root, self._build_block())
            rom = self._build_rom()

            # Step 2: compute raw SHAs of the unaltered fixtures and
            # patch the verifier module's frozen identity table to
            # match.  This is the GREEN reference the loader
            # compares against.
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
                "tools.verify_rom_battle_controller_cfg.FROZEN_BASELINE_PAYLOAD_SHA256",
                frozen_shas,
                create=True,
            ):
                # Step 3: tamper ONE payload with a semantically
                # harmless extra top-level field.  The parsed shape
                # is unaffected, so today's loader silently accepts
                # it; the raw bytes change, so the GREEN identity
                # check must raise.
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
                # Sanity: the patched constant still has the OLD
                # SHA, not the new one — that's the entire point of
                # the tamper scenario.
                self.assertNotEqual(
                    hashlib.sha256(tampered_path.read_bytes()).hexdigest(),
                    frozen_shas[tampered_rel],
                    msg=(
                        "tamper scenario lost its edge: the patched "
                        "constant must not have been refreshed to "
                        "the new raw SHA, otherwise the loader "
                        "would have no signal to fail closed."
                    ),
                )

                # Step 4: loader must raise ``ValueError``.  Today
                # it does not (the implementation ignores the
                # extra field), so the assertion fails and the
                # test is RED.
                with patch(
                    "tools.verify_rom_battle_controller_cfg._decode",
                    side_effect=_synthetic_block_decoder(decode_table),
                ):
                    with self.assertRaises(ValueError):
                        _baseline_occupied_bytes(root, rom)


# ---------------------------------------------------------------------------
# Committed-artifact independent verification (handoff §9.1 #5)
#
# The committed ``artifacts/rom-battle-controller-cfg-v1/`` directory holds
# the frozen exporter output that the build/CI pipeline consumes.  It must
# round-trip cleanly through ``verify_rom_battle_controller_cfg`` without
# any ``allow_implementation_drift`` escape hatch, and every field of the
# returned summary must match the canonical snapshot so the committed
# artifact becomes a stable identity contract for downstream consumers.
#
# The test below drives ``verify_rom_battle_controller_cfg`` directly on
# the committed artifact path (``ROOT / "artifacts/rom-battle-controller-cfg-v1"``).
# It is RED today because the committed payload's per-root
# ``reachable_instruction_count`` was produced by the OLD closure walk
# that only counted each root's own entry block; the new bounded-CFG
# rebuild (block-successor worklist) computes 2756 for every root that
# can reach the full block graph, so the artifact and the independent
# rebuild disagree on the contract field.  An implementation-identity
# hash mismatch (exporter / verifier / test SHAs diverged during the
# §9.1 refactor) also trips the GREEN identity check before any closure
# comparison.  Both failure modes prove the committed artifact is stale;
# the test must remain RED until the committed payload is regenerated
# by the current exporter and re-pinned into ``artifacts/``.
# ---------------------------------------------------------------------------


_COMMITTED_ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "rom-battle-controller-cfg-v1"

# Canonical frozen summary that ``verify_rom_battle_controller_cfg`` must
# return once the committed artifact is re-generated by the current
# exporter.  These numbers are derived from the committed manifest's
# ``extension_summary`` block; the verifier reconstructs the same
# values from ``_summary(blocks, frontiers, opaque_records)`` and the
# contract fails closed on any drift.
_COMMITTED_FROZEN_SUMMARY: dict[str, object] = {
    "decoded_basic_block_count": 739,
    "decoded_instruction_count": 2756,
    "frontier_count": 5,
    "frontier_reasons": {
        "decode_failure": 1,
        "indirect_pc_target": 2,
        "unsupported_armv4t_instruction": 2,
    },
    "opaque_external_edge_count": 227,
    "opaque_baseline_edge_count": 9,
    "reachable_instruction_bytes": 6172,
    "skipped_root_count": 1,
}

# Per-root dispatcher summary returned in the verifier report.  Mirrors
# the four fields the committed exporter writes into
# ``manifest.dispatch_summary``.
_COMMITTED_DISPATCH_SUMMARY: dict[str, object] = {
    "nondefault_state_count": 38,
    "default_state_count": 65_498,
}


class DispatcherPayloadTamperTests(unittest.TestCase):
    """The independent verifier must rebuild every dispatcher record.

    Artifact-level SHA pinning is a separate coverage/proof boundary.  These
    tests deliberately update the copied manifest after a single payload
    tamper so the verifier has to reject the semantic disagreement itself.
    """

    def _verify_tampered_dispatcher(self, mutate) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp).resolve() / "rom-battle-controller-cfg-v1"
            shutil.copytree(_COMMITTED_ARTIFACT_DIR, artifact)
            payload_path = artifact / "rom-battle-controller-cfg.json"
            manifest_path = artifact / "manifest.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            mutate(payload["dispatcher"])
            payload_raw = json.dumps(
                payload, ensure_ascii=False, indent=2, sort_keys=True
            ).encode("utf-8") + b"\n"
            payload_path.write_bytes(payload_raw)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][payload_path.name] = {
                "sha256": hashlib.sha256(payload_raw).hexdigest(),
                "size": len(payload_raw),
            }
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            return verify_rom_battle_controller_cfg(
                PROJECT_ROOT,
                artifact,
                allow_implementation_drift=True,
            )

    def test_rejects_tampered_complete_nondefault_mapping(self) -> None:
        def mutate(dispatcher: dict[str, object]) -> None:
            mappings = cast(list[dict[str, object]], dispatcher["mappings"])
            mappings[0]["decision_path_sha256"] = "0" * 64

        report = self._verify_tampered_dispatcher(mutate)
        self.assertFalse(report.get("verified"), report)
        self.assertTrue(
            any("dispatcher" in error for error in report.get("errors", [])),
            report,
        )

    def test_rejects_tampered_complete_default_transfers(self) -> None:
        def mutate(dispatcher: dict[str, object]) -> None:
            transfers = cast(
                list[dict[str, object]], dispatcher["default_transfers"]
            )
            transfers.pop()

        report = self._verify_tampered_dispatcher(mutate)
        self.assertFalse(report.get("verified"), report)
        self.assertTrue(
            any("dispatcher" in error for error in report.get("errors", [])),
            report,
        )


class CommittedArtifactIndependentVerificationTests(unittest.TestCase):
    """§9.1 #5: the committed ``artifacts/rom-battle-controller-cfg-v1/``
    payload must round-trip cleanly through the independent verifier
    and the returned report must carry the canonical summary frozen
    below.

    This test does NOT use ``allow_implementation_drift`` because the
    committed artifact is supposed to be a frozen identity anchor for
    the build pipeline: any drift in the exporter/verifier/test hashes
    is a real signal that the committed payload needs to be regenerated
    and re-pinned.  The test therefore fails closed on every identity
    mismatch and on every per-root closure drift, which is the
    intended RED until the committed payload is refreshed.
    """

    _COMMITTED_ROOT_COUNT = 38

    def test_committed_artifact_round_trips_with_frozen_summary(self) -> None:
        """Direct call to ``verify_rom_battle_controller_cfg`` on the
        committed artifact must return ``verified=True``, ``errors=[]``,
        ``root_count=38``, and a summary equal to the canonical frozen
        snapshot.  The committed artifact is RED today because (a) the
        implementation identity SHAs in the manifest diverge from the
        current exporter / verifier / test source hashes, and (b) the
        per-root ``reachable_instruction_count`` in the committed
        payload was computed by the OLD closure walk and disagrees
        with the bounded-CFG successor-walk the verifier independently
        rebuilds.  Both failure modes are real and structural; the
        test is RED until the committed payload is regenerated by the
        current exporter and re-pinned into ``artifacts/``.
        """

        self.assertTrue(
            _COMMITTED_ARTIFACT_DIR.is_dir(),
            msg=(
                "committed artifact directory must exist for the "
                "independent verification contract to be exercised: "
                f"{_COMMITTED_ARTIFACT_DIR}"
            ),
        )

        report = verify_rom_battle_controller_cfg(
            PROJECT_ROOT, _COMMITTED_ARTIFACT_DIR
        )

        self.assertEqual(
            report.get("verified"),
            True,
            msg=(
                "verify_rom_battle_controller_cfg must return "
                "verified=True for the committed artifact; the "
                "committed payload is stale and the verifier rejects "
                "it via errors[].  Real failure: "
                f"{report.get('errors')!r}"
            ),
        )
        self.assertEqual(
            report.get("errors"),
            [],
            msg=(
                "verify_rom_battle_controller_cfg must return "
                "errors=[] for the committed artifact; the verifier "
                f"rejected the stale payload with: {report.get('errors')!r}"
            ),
        )
        self.assertEqual(
            report.get("schema"),
            "rom-battle-controller-cfg-verification-v1",
            msg=(
                "verifier report schema changed; update the frozen "
                "contract below to match the new verifier return shape."
            ),
        )
        self.assertEqual(
            report.get("root_count"),
            self._COMMITTED_ROOT_COUNT,
            msg=(
                "committed artifact must carry exactly 38 dispatcher "
                "root records; the canonical dispatcher denominator "
                "is 38 non-default states."
            ),
        )
        self.assertEqual(
            report.get("dispatcher_nondefault_state_count"),
            _COMMITTED_DISPATCH_SUMMARY["nondefault_state_count"],
            msg=(
                "dispatcher nondefault_state_count drifted from the "
                "canonical 38; rebuild the dispatcher to recover the "
                "frozen value."
            ),
        )
        self.assertEqual(
            report.get("dispatcher_default_state_count"),
            _COMMITTED_DISPATCH_SUMMARY["default_state_count"],
            msg=(
                "dispatcher default_state_count drifted from the "
                "canonical 65,498; rebuild the dispatcher to recover "
                "the frozen value."
            ),
        )
        self.assertEqual(
            report.get("summary"),
            _COMMITTED_FROZEN_SUMMARY,
            msg=(
                "committed artifact summary drifted from the canonical "
                "frozen snapshot; regenerate the committed payload via "
                "tools/export_rom_battle_controller_cfg.py and re-pin "
                "the result.  Expected: "
                f"{_COMMITTED_FROZEN_SUMMARY!r}; got: "
                f"{report.get('summary')!r}."
            ),
        )


if __name__ == "__main__":
    unittest.main()
