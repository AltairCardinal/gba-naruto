from __future__ import annotations

import hashlib
import unittest

from tools import build_save_state_runtime_probe as probe


class SaveStateRuntimeProbeTests(unittest.TestCase):
    def test_thumb_bl_round_trip_known_original_call(self):
        self.assertEqual(
            bytes.fromhex("02f010fe"),
            probe.encode_thumb_bl(probe.GROWTH_CALL_SITES[0], probe.ORIGINAL_GROWTH),
        )

    def test_probe_changes_only_hook_and_stub(self):
        size = probe.STUB_FILE_OFFSET + probe.STUB_SIZE
        base = bytearray(size)
        hooks = [site - probe.ROM_BASE for site in probe.GROWTH_CALL_SITES]
        for site, hook in zip(probe.GROWTH_CALL_SITES, hooks):
            base[hook:hook + 4] = probe.encode_thumb_bl(site, probe.ORIGINAL_GROWTH)
        old_sha = probe.BASE_SHA1
        probe.BASE_SHA1 = hashlib.sha1(base).hexdigest()
        try:
            changed = probe.build_probe(bytes(base))
        finally:
            probe.BASE_SHA1 = old_sha
        differences = [index for index, pair in enumerate(zip(base, changed)) if pair[0] != pair[1]]
        self.assertTrue(all(any(hook <= index < hook + 4 for hook in hooks) or probe.STUB_FILE_OFFSET <= index < probe.STUB_FILE_OFFSET + probe.STUB_SIZE for index in differences))
        self.assertEqual(bytes.fromhex("10b5"), changed[probe.STUB_FILE_OFFSET:probe.STUB_FILE_OFFSET + 2])
        self.assertEqual(bytes.fromhex("10bd"), changed[probe.STUB_FILE_OFFSET + 22:probe.STUB_FILE_OFFSET + 24])
        self.assertEqual(probe.SAVE_RESULT_WRAM.to_bytes(4, "little"), changed[probe.STUB_FILE_OFFSET + 28:probe.STUB_FILE_OFFSET + 32])


if __name__ == "__main__":
    unittest.main()
