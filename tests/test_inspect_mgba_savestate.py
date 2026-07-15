import hashlib
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from tools.inspect_mgba_savestate import (
    inspect_savestate,
    load_gba_state,
    png_screen_fingerprint,
)
from tools.thumb_branch import encode_thumb_bl


def png_chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def _chunk_payload(png: bytes, wanted: bytes) -> bytes:
    cursor = 8
    while cursor + 12 <= len(png):
        size = struct.unpack_from(">I", png, cursor)[0]
        tag = png[cursor + 4 : cursor + 8]
        if tag == wanted:
            return bytes(png[cursor + 8 : cursor + 8 + size])
        cursor += size + 12
    raise AssertionError(f"missing test chunk {wanted!r}")


def _replace_chunk(png: bytes, wanted: bytes, payload: bytes) -> bytes:
    cursor = 8
    while cursor + 12 <= len(png):
        size = struct.unpack_from(">I", png, cursor)[0]
        tag = png[cursor + 4 : cursor + 8]
        chunk_end = cursor + size + 12
        if tag == wanted:
            return bytes(png[:cursor]) + png_chunk(tag, payload) + bytes(png[chunk_end:])
        cursor = chunk_end
    raise AssertionError(f"missing test chunk {wanted!r}")


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


def screen_png(scanlines: bytes = b"\x00\x01\x02\x03") -> bytes:
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", zlib.compress(scanlines))
        + png_chunk(b"IEND", b"")
    )


def _paeth(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    distances = (
        abs(estimate - left),
        abs(estimate - up),
        abs(estimate - upper_left),
    )
    return (left, up, upper_left)[distances.index(min(distances))]


def filtered_screen_png(
    pixels: bytes, *, width: int, height: int, filters: list[int]
) -> bytes:
    stride = width * 3
    if len(pixels) != stride * height or len(filters) != height:
        raise AssertionError("invalid filtered PNG test fixture")
    filtered = bytearray()
    previous = bytes(stride)
    for row_index, filter_type in enumerate(filters):
        row = pixels[row_index * stride : (row_index + 1) * stride]
        filtered.append(filter_type)
        for index, value in enumerate(row):
            left = row[index - 3] if index >= 3 else 0
            up = previous[index]
            upper_left = previous[index - 3] if index >= 3 else 0
            predictors = {
                0: 0,
                1: left,
                2: up,
                3: (left + up) // 2,
                4: _paeth(left, up, upper_left),
            }
            filtered.append((value - predictors[filter_type]) & 0xFF)
        previous = row
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", zlib.compress(filtered))
        + png_chunk(b"IEND", b"")
    )


class InspectMgbaSavestateTests(unittest.TestCase):
    def test_fingerprints_png_screen_from_normalized_rgb_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "screen.png"
            path.write_bytes(screen_png())

            fingerprint = png_screen_fingerprint(path)

        self.assertEqual(fingerprint["width"], 1)
        self.assertEqual(fingerprint["height"], 1)
        self.assertEqual(fingerprint["ihdr_sha256"], hashlib.sha256(
            struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        ).hexdigest())
        self.assertIn("rgb_pixels_sha256", fingerprint)
        self.assertEqual(
            fingerprint["rgb_pixels_sha256"],
            hashlib.sha256(b"\x01\x02\x03").hexdigest(),
        )
        self.assertEqual(fingerprint["rgb_pixels_length"], 3)

    def test_all_legal_png_filters_normalize_to_the_same_rgb_pixels(self):
        pixels = bytes(range(1, 31))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unfiltered = root / "unfiltered.png"
            mixed = root / "mixed.png"
            unfiltered.write_bytes(
                filtered_screen_png(pixels, width=2, height=5, filters=[0] * 5)
            )
            mixed.write_bytes(
                filtered_screen_png(pixels, width=2, height=5, filters=[0, 1, 2, 3, 4])
            )

            plain_fingerprint = png_screen_fingerprint(unfiltered)
            mixed_fingerprint = png_screen_fingerprint(mixed)

        self.assertEqual(plain_fingerprint, mixed_fingerprint)
        self.assertEqual(
            mixed_fingerprint["rgb_pixels_sha256"], hashlib.sha256(pixels).hexdigest()
        )

    def test_screen_fingerprint_fails_closed_on_crc_and_shape_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            corrupt_crc = root / "crc.png"
            payload = bytearray(screen_png())
            payload[-1] ^= 1
            corrupt_crc.write_bytes(payload)
            truncated = root / "truncated.png"
            truncated.write_bytes(screen_png()[:-3])
            wrong_shape = root / "wrong-shape.png"
            wrong_shape.write_bytes(screen_png(b"\x00\x01"))
            invalid_filter = root / "invalid-filter.png"
            invalid_filter.write_bytes(screen_png(b"\x05\x01\x02\x03"))
            trailing_zlib = root / "trailing-zlib.png"
            valid = screen_png()
            trailing_zlib.write_bytes(
                _replace_chunk(
                    valid,
                    b"IDAT",
                    _chunk_payload(valid, b"IDAT") + b"GARBAGE",
                )
            )

            with self.assertRaisesRegex(ValueError, "CRC"):
                png_screen_fingerprint(corrupt_crc)
            with self.assertRaisesRegex(ValueError, "truncated|IEND"):
                png_screen_fingerprint(truncated)
            with self.assertRaisesRegex(ValueError, "scanline"):
                png_screen_fingerprint(wrong_shape)
            with self.assertRaisesRegex(ValueError, "filter"):
                png_screen_fingerprint(invalid_filter)
            with self.assertRaisesRegex(ValueError, "trailing|unused"):
                png_screen_fingerprint(trailing_zlib)

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

    def test_reports_only_explicit_stack_returns_validated_as_thumb_bl(self):
        state_bytes = bytearray(fixture_savestate())
        state = bytearray(zlib.decompress(_chunk_payload(state_bytes, b"gbAs")))
        state[0x21000 + 0x2680C] = 0
        task_context = 0x19000 + 0x0A88 + 0x4C
        state[task_context] = 8
        struct.pack_into("<I", state, task_context + 4, 0x030011D8)
        struct.pack_into("<I", state, task_context + 8, 0x08067D03)
        returns = (
            (0x03001220, 0x080885C1, 0x08067158),
            (0x03001240, 0x08088F9F, 0x080884DC),
            (0x03001278, 0x0808F92D, 0x08088F10),
        )
        for stack_address, raw_return, _ in returns:
            struct.pack_into(
                "<I", state, 0x19000 + stack_address - 0x03000000, raw_return
            )
        savestate = _replace_chunk(state_bytes, b"gbAs", zlib.compress(state))
        rom = bytearray(0x90000)
        for _, raw_return, target in returns:
            callsite = raw_return - 5
            offset = callsite - 0x08000000
            rom[offset : offset + 4] = encode_thumb_bl(callsite, target)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "fixture.ss9"
            rom_path = root / "base.gba"
            path.write_bytes(savestate)
            rom_path.write_bytes(rom)

            report = inspect_savestate(
                path,
                rom_path=rom_path,
                task_slot=2,
                unwind_frames=[(address, target) for address, _, target in returns],
                memory_bytes=[0x0202680C],
            )

        self.assertEqual(report["tasks"][1]["resume_pc"], "0x08067D02")
        self.assertEqual(
            report["active_unwind"]["raw_return_words"],
            ["0x080885C1", "0x08088F9F", "0x0808F92D"],
        )
        self.assertEqual(
            [frame["stack_address"] for frame in report["active_unwind"]["frames"]],
            ["0x03001220", "0x03001240", "0x03001278"],
        )
        self.assertEqual(report["memory_bytes"]["0x0202680C"], 0)

    def test_rejects_explicit_unwind_when_stack_or_bl_target_does_not_match(self):
        state_bytes = bytearray(fixture_savestate())
        state = bytearray(zlib.decompress(_chunk_payload(state_bytes, b"gbAs")))
        struct.pack_into("<I", state, 0x19000 + 0x1200, 0x08001005)
        savestate = _replace_chunk(state_bytes, b"gbAs", zlib.compress(state))
        rom = bytearray(0x2000)
        rom[0x1000:0x1004] = encode_thumb_bl(0x08001000, 0x08001100)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "fixture.ss9"
            rom_path = root / "base.gba"
            path.write_bytes(savestate)
            rom_path.write_bytes(rom)

            with self.assertRaisesRegex(ValueError, "target"):
                inspect_savestate(
                    path,
                    rom_path=rom_path,
                    task_slot=1,
                    unwind_frames=[(0x03001200, 0x08001200)],
                )

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

    def test_savestate_container_rejects_crc_duplicate_truncation_and_trailing_data(self):
        valid = fixture_savestate()
        gbas_payload = _chunk_payload(valid, b"gbAs")
        gbas_chunk = png_chunk(b"gbAs", gbas_payload)
        iend_offset = valid.rfind(png_chunk(b"IEND", b""))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            corrupt_crc = root / "corrupt-crc.ss9"
            corrupt = bytearray(valid)
            gbas_offset = valid.find(gbas_chunk)
            corrupt[gbas_offset + len(gbas_chunk) - 1] ^= 1
            corrupt_crc.write_bytes(corrupt)
            duplicate = root / "duplicate.ss9"
            duplicate.write_bytes(valid[:iend_offset] + gbas_chunk + valid[iend_offset:])
            truncated = root / "truncated.ss9"
            truncated.write_bytes(valid[:-3])
            trailing_container = root / "trailing-container.ss9"
            trailing_container.write_bytes(valid + b"GARBAGE")
            trailing_zlib = root / "trailing-zlib.ss9"
            trailing_zlib.write_bytes(
                _replace_chunk(valid, b"gbAs", gbas_payload + b"GARBAGE")
            )

            with self.assertRaisesRegex(ValueError, "CRC"):
                load_gba_state(corrupt_crc)
            with self.assertRaisesRegex(ValueError, "exactly one|duplicate"):
                load_gba_state(duplicate)
            with self.assertRaisesRegex(ValueError, "truncated|IEND"):
                load_gba_state(truncated)
            with self.assertRaisesRegex(ValueError, "after IEND|trailing"):
                load_gba_state(trailing_container)
            with self.assertRaisesRegex(ValueError, "trailing|unused"):
                load_gba_state(trailing_zlib)

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
