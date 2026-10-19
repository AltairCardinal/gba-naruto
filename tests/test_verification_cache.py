"""Tests for the content-addressed verifier report cache.

The cache may only ever return exactly the evidence a fresh verifier run
would have produced, so every test here is about a case where the reuse
must NOT happen.
"""

import json
from pathlib import Path
import tempfile
import unittest

from tools import verification_cache as cache


class FingerprintTests(unittest.TestCase):
    def test_key_changes_with_every_input(self):
        base = cache.fingerprint(Path("tools/v.py"), "a" * 64, "b" * 64, (("x", "c" * 64),))
        self.assertNotEqual(
            base, cache.fingerprint(Path("tools/v.py"), "d" * 64, "b" * 64, (("x", "c" * 64),))
        )
        self.assertNotEqual(
            base, cache.fingerprint(Path("tools/v.py"), "a" * 64, "e" * 64, (("x", "c" * 64),))
        )
        self.assertNotEqual(
            base, cache.fingerprint(Path("tools/v.py"), "a" * 64, "b" * 64, (("x", "f" * 64),))
        )
        self.assertNotEqual(
            base, cache.fingerprint(Path("tools/v.py"), "a" * 64, "b" * 64, (("y", "c" * 64),))
        )
        self.assertNotEqual(
            base, cache.fingerprint(Path("tools/w.py"), "a" * 64, "b" * 64, (("x", "c" * 64),))
        )

    def test_key_is_stable_for_identical_inputs(self):
        first = cache.fingerprint(Path("tools/v.py"), "a" * 64, "b" * 64, (("x", "c" * 64),))
        second = cache.fingerprint(Path("tools/v.py"), "a" * 64, "b" * 64, (("x", "c" * 64),))
        self.assertEqual(first, second)

    def test_input_order_does_not_change_the_key(self):
        forward = cache.fingerprint(
            Path("tools/v.py"), "a" * 64, "b" * 64, (("x", "c" * 64), ("y", "d" * 64))
        )
        backward = cache.fingerprint(
            Path("tools/v.py"), "a" * 64, "b" * 64, (("y", "d" * 64), ("x", "c" * 64))
        )
        self.assertEqual(forward, backward)


class DescribeInputsTests(unittest.TestCase):
    def test_missing_input_is_a_hard_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "missing"):
                cache.describe_inputs(root, [Path("absent.json")])

    def test_input_outside_the_repository_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = Path(tmp).parent / "outside.bin"
            outside.write_bytes(b"x")
            try:
                with self.assertRaisesRegex(ValueError, "escapes the repository"):
                    cache.describe_inputs(root, [outside])
            finally:
                outside.unlink()

    def test_inputs_are_described_by_relative_path_and_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.bin").write_bytes(b"alpha")
            described = cache.describe_inputs(root, [Path("a.bin")])
            self.assertEqual(len(described), 1)
            relative, digest = described[0]
            self.assertEqual(relative, "a.bin")
            self.assertEqual(len(digest), 64)


class StoreAndLoadTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            key = "k" * 64
            report = {"verified": True, "errors": [], "promotion_bytes": 1542}
            cache.store_report(cache_dir, key, report)
            self.assertEqual(cache.load_report(cache_dir, key), report)

    def test_missing_entry_is_a_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(cache.load_report(Path(tmp), "k" * 64))

    def test_corrupt_entry_is_a_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            key = "k" * 64
            cache.store_report(cache_dir, key, {"verified": True})
            (cache_dir / f"{key}.json").write_text("{ not json", encoding="utf-8")
            self.assertIsNone(cache.load_report(cache_dir, key))

    def test_entry_with_a_foreign_key_is_a_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            key = "k" * 64
            cache.store_report(cache_dir, key, {"verified": True})
            document = json.loads((cache_dir / f"{key}.json").read_text(encoding="utf-8"))
            document["cache_key"] = "z" * 64
            (cache_dir / f"{key}.json").write_text(json.dumps(document), encoding="utf-8")
            self.assertIsNone(cache.load_report(cache_dir, key))

    def test_storing_twice_keeps_the_first_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            key = "k" * 64
            cache.store_report(cache_dir, key, {"verified": True, "value": 1})
            cache.store_report(cache_dir, key, {"verified": True, "value": 2})
            self.assertEqual(cache.load_report(cache_dir, key)["value"], 1)


class CachedVerifyTests(unittest.TestCase):
    def test_first_call_computes_and_second_call_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            calls = []

            def compute():
                calls.append(1)
                return {"verified": True, "errors": []}

            first, from_cache = cache.cached_verify(
                root=Path(tmp),
                cache_dir=cache_dir,
                verifier=Path("tools/v.py"),
                verifier_sha256="a" * 64,
                rom_sha256="b" * 64,
                inputs=(("x", "c" * 64),),
                compute=compute,
            )
            self.assertFalse(from_cache)
            self.assertTrue(first["verified"])

            second, from_cache = cache.cached_verify(
                root=Path(tmp),
                cache_dir=cache_dir,
                verifier=Path("tools/v.py"),
                verifier_sha256="a" * 64,
                rom_sha256="b" * 64,
                inputs=(("x", "c" * 64),),
                compute=compute,
            )
            self.assertTrue(from_cache)
            self.assertEqual(second, first)
            self.assertEqual(len(calls), 1)

    def test_a_changed_input_is_a_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            calls = []

            def compute():
                calls.append(1)
                return {"verified": True}

            cache.cached_verify(
                root=Path(tmp),
                cache_dir=cache_dir,
                verifier=Path("tools/v.py"),
                verifier_sha256="a" * 64,
                rom_sha256="b" * 64,
                inputs=(("x", "c" * 64),),
                compute=compute,
            )
            _, from_cache = cache.cached_verify(
                root=Path(tmp),
                cache_dir=cache_dir,
                verifier=Path("tools/v.py"),
                verifier_sha256="a" * 64,
                rom_sha256="b" * 64,
                inputs=(("x", "d" * 64),),
                compute=compute,
            )
            self.assertFalse(from_cache)
            self.assertEqual(len(calls), 2)

    def test_a_failing_verifier_is_never_memoised(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            calls = []

            def compute():
                calls.append(1)
                return {"verified": False, "errors": ["boom"]}

            for _ in range(2):
                report, from_cache = cache.cached_verify(
                    root=Path(tmp),
                    cache_dir=cache_dir,
                    verifier=Path("tools/v.py"),
                    verifier_sha256="a" * 64,
                    rom_sha256="b" * 64,
                    inputs=(("x", "c" * 64),),
                    compute=compute,
                )
                self.assertFalse(from_cache)
                self.assertFalse(report["verified"])
            self.assertEqual(len(calls), 2)

    def test_a_computing_exception_is_not_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"

            def compute():
                raise ValueError("verifier exploded")

            with self.assertRaisesRegex(ValueError, "exploded"):
                cache.cached_verify(
                    root=Path(tmp),
                    cache_dir=cache_dir,
                    verifier=Path("tools/v.py"),
                    verifier_sha256="a" * 64,
                    rom_sha256="b" * 64,
                    inputs=(("x", "c" * 64),),
                    compute=compute,
                )
            self.assertIsNone(cache.load_report(cache_dir, cache.fingerprint(
                Path("tools/v.py"), "a" * 64, "b" * 64, (("x", "c" * 64),)
            )))


if __name__ == "__main__":
    unittest.main()
