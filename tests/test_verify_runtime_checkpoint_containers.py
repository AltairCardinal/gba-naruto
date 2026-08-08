from __future__ import annotations

import struct
import tempfile
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


class RuntimeCheckpointContainerVerifierTests(unittest.TestCase):
    def test_accepts_all_tracked_runtime_checkpoints_as_mgba_states(self):
        from tools.verify_runtime_checkpoint_containers import verify_checkpoints

        result = verify_checkpoints(ROOT / "artifacts/runtime-checkpoints")

        self.assertTrue(result["verified"], result["errors"])
        self.assertEqual(result["checkpoint_count"], 106)
        self.assertEqual(result["valid_mgba_state_count"], 106)
        self.assertEqual(result["plain_png_count"], 0)
        self.assertEqual(result["invalid_count"], 0)

    def test_rejects_plain_png_without_gbas_state_chunk(self):
        from tools.verify_runtime_checkpoint_containers import verify_checkpoints

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "screenshot.ss9").write_bytes(
                b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IEND", b"")
            )

            result = verify_checkpoints(directory)

        self.assertFalse(result["verified"])
        self.assertEqual(result["plain_png_count"], 1)
        self.assertEqual(result["valid_mgba_state_count"], 0)
        self.assertIn("missing gbAs state chunk", result["errors"][0])


if __name__ == "__main__":
    unittest.main()
