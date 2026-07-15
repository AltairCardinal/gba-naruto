import hashlib
import unittest

from tools import build_battle_effect_runtime_probe as probe


class BattleEffectRuntimeProbeTests(unittest.TestCase):
    def test_probe_only_changes_calls_and_stub(self):
        base = bytearray(probe.STUB_OFFSET + probe.STUB_SIZE)
        hooks = []
        for site in probe.CALL_SITES:
            off = site - probe.ROM_BASE
            hooks.append(off)
            base[off:off + 4] = probe.encode_thumb_bl(site, probe.CONSUMER)
        old = probe.BASE_SHA1
        probe.BASE_SHA1 = hashlib.sha1(base).hexdigest()
        try:
            changed = probe.build_probe(bytes(base))
        finally:
            probe.BASE_SHA1 = old
        diffs = [i for i, (a, b) in enumerate(zip(base, changed)) if a != b]
        self.assertTrue(all(any(h <= i < h + 4 for h in hooks) or probe.STUB_OFFSET <= i < probe.STUB_OFFSET + probe.STUB_SIZE for i in diffs))
        self.assertEqual(probe.SCRATCH.to_bytes(4, "little"), changed[probe.STUB_OFFSET + 40:probe.STUB_OFFSET + 44])


if __name__ == "__main__":
    unittest.main()
