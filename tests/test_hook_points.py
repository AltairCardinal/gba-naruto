"""Hook point preimages must still match the base ROM.

The hook sites come from the vendored third-party package.  Their original
byte preimages are the same kind of precondition our patch pipeline enforces
with `before_hex`, so a mismatch means the ROM changed under us and every
patch aimed at that site would be wrong.
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools import text_codec  # noqa: E402
from tools.hook_points import HOOKS, verify_hook_preimages  # noqa: E402


def _rom_available():
    try:
        text_codec.resolve_rom()
        return True
    except FileNotFoundError:
        return False


@unittest.skipUnless(_rom_available(), "base ROM not available")
class HookPointTests(unittest.TestCase):
    def test_every_hook_preimage_matches_the_base_rom(self):
        rows = verify_hook_preimages()
        bad = [r for r in rows if not r["match"]]
        self.assertEqual(
            [], bad,
            "hook preimage mismatch:\n" + "\n".join(
                f"  {r['offset_hex']} {r['name']}: want {r['preimage']} "
                f"got {r['rom_actual']}" for r in bad
            ),
        )

    def test_hook_offsets_are_inside_the_rom(self):
        size = text_codec.resolve_rom().stat().st_size
        for offset, name, _purpose, preimage in HOOKS:
            self.assertLess(offset + len(preimage) // 2, size, name)


if __name__ == "__main__":
    unittest.main()
