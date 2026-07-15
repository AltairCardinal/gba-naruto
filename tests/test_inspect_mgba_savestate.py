import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from tools.inspect_mgba_savestate import inspect_savestate, load_gba_state


def png_chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def fixture_savestate() -> bytes:
    state = bytearray(0x61000)
    struct.pack_into("<I", state, 0, 0x01000007)
    struct.pack_into("<16I", state, 0x20, *range(15), 0x0806112A)
    struct.pack_into("<I", state, 0x60, 0x2000003F)
    state[0x21000 + 0x2680C] = 1

    context = 0x19000 + 0x0A88
    state[context] = 1
    state[context + 1] = 2
    struct.pack_into("<I", state, context + 4, 0x03001100)
    struct.pack_into("<I", state, context + 8, 0x08074197)
    state[context + 0x4C] = 8

    payload = zlib.compress(state)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", b"\0" * 13)
        + png_chunk(b"gbAs", payload)
        + png_chunk(b"IEND", b"")
    )


class InspectMgbaSavestateTests(unittest.TestCase):
    def test_loads_gbas_chunk_and_maps_gba_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.ss9"
            path.write_bytes(fixture_savestate())

            parsed = load_gba_state(path)

        self.assertEqual(parsed.version_magic, 0x01000007)
        self.assertEqual(parsed.registers[15], 0x0806112A)
        self.assertEqual(parsed.read_memory(0x0202680C, 1), b"\x01")

    def test_reports_cpu_and_cooperative_task_contexts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.ss9"
            path.write_bytes(fixture_savestate())

            report = inspect_savestate(path)

        self.assertEqual(report["cpu"]["saved_pc"], "0x0806112A")
        self.assertTrue(report["cpu"]["thumb"])
        self.assertEqual(
            report["tasks"][0],
            {
                "slot": 1,
                "type": 1,
                "delay": 2,
                "sp": "0x03001100",
                "lr": "0x08074197",
                "resume_pc": "0x08074196",
            },
        )
        self.assertEqual(report["tasks"][1]["type"], 8)

    def test_rejects_missing_or_wrong_sized_gbas_chunk(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.ss9"
            missing.write_bytes(b"\x89PNG\r\n\x1a\n" + png_chunk(b"IEND", b""))
            short = Path(tmp) / "short.ss9"
            short.write_bytes(
                b"\x89PNG\r\n\x1a\n"
                + png_chunk(b"gbAs", zlib.compress(b"short"))
                + png_chunk(b"IEND", b"")
            )

            with self.assertRaisesRegex(ValueError, "gbAs"):
                load_gba_state(missing)
            with self.assertRaisesRegex(ValueError, "397312"):
                load_gba_state(short)

    def test_reads_persisted_pre_controller_and_controller_checkpoints(self):
        root = Path(__file__).resolve().parents[1]

        pre_controller = load_gba_state(
            root
            / "artifacts"
            / "runtime-checkpoints"
            / "scenario-41-pre-controller-lineup.ss9"
        )
        pre_report = inspect_savestate(
            root
            / "artifacts"
            / "runtime-checkpoints"
            / "scenario-41-pre-controller-lineup.ss9"
        )
        self.assertEqual(pre_controller.registers[15], 0x0806112A)
        self.assertEqual(pre_controller.read_memory(0x0202680C, 1), b"\x00")
        self.assertEqual(pre_report["tasks"][1]["sp"], "0x030011FC")
        self.assertEqual(pre_report["tasks"][1]["lr"], "0x0806F997")
        self.assertEqual(pre_controller.read_u32(0x03001234), 0x0807513F)
        self.assertEqual(pre_controller.read_u32(0x03001240), 0x08089029)
        self.assertEqual(pre_controller.read_u32(0x03001278), 0x0808F92D)

        actionable = load_gba_state(
            root / "artifacts" / "runtime-checkpoints" / "actionable-move-grid.ss9"
        )
        actionable_report = inspect_savestate(
            root / "artifacts" / "runtime-checkpoints" / "actionable-move-grid.ss9"
        )
        self.assertEqual(actionable.registers[15], 0x0806112C)
        self.assertEqual(actionable.read_memory(0x0202680C, 1), b"\x01")
        self.assertEqual(actionable_report["tasks"][1]["sp"], "0x03001154")
        self.assertEqual(actionable_report["tasks"][1]["lr"], "0x0806F997")
        self.assertEqual(actionable.read_u32(0x0300118C), 0x080718F3)
        self.assertEqual(actionable.read_u32(0x03001220), 0x08074197)
        self.assertEqual(actionable.read_u32(0x03001278), 0x0808F957)
        self.assertEqual(actionable.read_u32(0x03001258), 0x080751A7)

        evidence = json.loads(
            (
                root
                / "artifacts"
                / "runtime-checkpoints"
                / "scenario-41-savestate-context-evidence.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            evidence["checkpoints"][0]["active_unwind_raw_return_words"],
            ["0x0807513F", "0x08089029", "0x0808F92D"],
        )
        self.assertEqual(
            evidence["checkpoints"][1]["active_unwind_raw_return_words"],
            ["0x080718F3", "0x08074197", "0x0808F957"],
        )
        self.assertEqual(
            evidence["checkpoints"][1][
                "stale_or_local_stack_words_excluded_from_active_unwind"
            ],
            ["0x080751A7"],
        )


if __name__ == "__main__":
    unittest.main()
