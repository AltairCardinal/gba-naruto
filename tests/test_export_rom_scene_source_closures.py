from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "build/experiments/active/scene-source-closures-sol-20260905"


class SceneSourceClosuresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools import export_rom_scene_source_closures as E
        from tools import rom_scene_source_closures_contract as C
        from tools import verify_rom_scene_source_closures as V
        cls.E, cls.C, cls.V = E, C, V
        cls.payload = E.build_payload(ROOT)

    def test_frozen_denominators_and_promotion(self):
        p = self.payload
        self.assertEqual([138, 84, 132, 6], [p["pointer_denominator"][k] for k in ("hit_count", "unique_target_count", "external_count", "self_count")])
        self.assertEqual([131, 133, 77], [p["consumer_binding"][k] for k in ("literal_count", "consumer_count", "root_count")])
        self.assertEqual([125, 8], [p["consumer_binding"][k] for k in ("classified_consumer_count", "current_unknown_consumer_count")])
        self.assertEqual([[0x0FC054, 0x464441]], p["pointer_denominator"]["rejected_accidental_words"])
        self.assertEqual([73, 1015, 2, 360, 71, 655], [p["promotion"][k] for k in ("claim_count", "bytes", "obj_claim_count", "obj_bytes", "source_claim_count", "source_bytes")])
        self.assertEqual([46, 90], [p["excluded_alignment_gaps"][k] for k in ("range_count", "bytes")])
        self.assertEqual([23, 199], [p["preserved_unknown_holes"][k] for k in ("range_count", "bytes")])
        self.assertEqual(
            [[0x464298, "no_accepted_instruction_consumer"],
             [0x4642AC, "no_accepted_instruction_consumer"]],
            p["consumer_binding"]["rejected_unowned_source_roots"],
        )

    def test_contract_is_constants_only_and_verifier_independent(self):
        tree = ast.parse((ROOT / "tools/rom_scene_source_closures_contract.py").read_text())
        self.assertFalse(any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for n in ast.walk(tree)))
        source = (ROOT / "tools/verify_rom_scene_source_closures.py").read_text()
        self.assertNotIn("export_rom_scene_source_closures", source)

    def test_roundtrip_tamper_extra_and_no_replace(self):
        with tempfile.TemporaryDirectory(dir=RUN) as raw:
            out = Path(raw) / "candidate"
            self.E.export_artifact(ROOT, out)
            self.assertTrue(self.V.verify_artifact(ROOT, out)["verified"])
            with self.assertRaises(FileExistsError):
                self.E.export_artifact(ROOT, out)
            (out / "extra").write_text("x")
            self.assertFalse(self.V.verify_artifact(ROOT, out)["verified"])

    def test_semantic_mutations_fail_closed(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        for offset, label in ((0x070768, "genuine pointer word"),
                              (0x0FC054, "accidental word"),
                              (0x464034, "self pointer"),
                              (0x07071C, "LDR consumer opcode"),
                              (0x46403C, "OBJ closure internal pointer/size"),
                              (0x4643C8, "OBJ closure"),
                              (0x464048, "source endpoint/terminator")):
            changed = bytearray(rom); changed[offset] ^= 1
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, label):
                self.E.build_payload(ROOT, bytes(changed), verify_identity=False)

    def test_gaps_and_holes_are_not_promoted(self):
        promoted = [tuple(x["range"]) for x in self.payload["promotion"]["claims"]]
        for category in ("excluded_alignment_gaps", "preserved_unknown_holes"):
            for a, b in self.payload[category]["ranges"]:
                self.assertFalse(any(a < d and c < b for c, d in promoted))
        for rejected in ([0x464298, 0x46429D], [0x4642AC, 0x4642B3],
                         [0x46450E, 0x464510]):
            a, b = rejected
            self.assertFalse(any(a < d and c < b for c, d in promoted), rejected)

    def test_payload_and_manifest_tamper_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=RUN) as raw:
            base = Path(raw); original = base / "original"
            self.E.export_artifact(ROOT, original)
            for name, member in (("payload", self.C.PAYLOAD_NAME), ("manifest", "manifest.json")):
                target = base / name; shutil.copytree(original, target)
                path = target / member; path.write_bytes(path.read_bytes() + b" ")
                self.assertFalse(self.V.verify_artifact(ROOT, target)["verified"])

    def test_synchronized_payload_and_manifest_contract_tamper_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=RUN) as raw:
            base = Path(raw); original = base / "original"
            self.E.export_artifact(ROOT, original)
            mutations = {
                "pointer": lambda p: p["pointer_denominator"].__setitem__("hit_count", 999),
                "consumer": lambda p: p["consumer_binding"].__setitem__("root_count", 999),
                "claim-id": lambda p: p["promotion"]["claims"][0].__setitem__("id", "forged"),
                "claim-hash": lambda p: p["promotion"]["claims"][0].__setitem__("bytes_sha256", "0" * 64),
                "gaps": lambda p: p["excluded_alignment_gaps"]["ranges"].__setitem__(0, [0, 1]),
                "holes": lambda p: p["preserved_unknown_holes"]["ranges"].__setitem__(0, [0, 1]),
                "rom": lambda p: p["rom"].__setitem__("sha256", "0" * 64),
                "coverage": lambda p: p["coverage_baseline"].__setitem__("sha256", "0" * 64),
                "limitations": lambda p: p.__setitem__("limitations", []),
            }
            for name, mutate in mutations.items():
                with self.subTest(name=name):
                    target = base / name; shutil.copytree(original, target)
                    payload_path = target / self.C.PAYLOAD_NAME
                    payload = json.loads(payload_path.read_text()); mutate(payload)
                    raw_payload = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
                    payload_path.write_bytes(raw_payload)
                    manifest_path = target / "manifest.json"
                    manifest = json.loads(manifest_path.read_text())
                    manifest["files"][self.C.PAYLOAD_NAME] = {
                        "sha256": hashlib.sha256(raw_payload).hexdigest(),
                        "size": len(raw_payload),
                    }
                    manifest_path.write_text(
                        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                    self.assertFalse(self.V.verify_artifact(ROOT, target)["verified"])

    def test_manifest_recipe_and_schema_tamper_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=RUN) as raw:
            base = Path(raw); original = base / "original"
            self.E.export_artifact(ROOT, original)
            for name, mutate in (
                ("schema", lambda m: m.__setitem__("schema", "forged")),
                ("artifact", lambda m: m.__setitem__("artifact_schema", "forged")),
                ("producer", lambda m: m["producer"].__setitem__("command", ["false"])),
                ("verifier", lambda m: m["verifier"].__setitem__("command", ["false"])),
            ):
                with self.subTest(name=name):
                    target = base / name; shutil.copytree(original, target)
                    path = target / "manifest.json"; manifest = json.loads(path.read_text())
                    mutate(manifest)
                    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                    self.assertFalse(self.V.verify_artifact(ROOT, target)["verified"])

    def test_symlink_and_unauthorized_output_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=RUN) as raw:
            base = Path(raw)
            link = base / "link"
            link.symlink_to(base / "real", target_is_directory=True)
            with self.assertRaises(ValueError):
                self.E.export_artifact(ROOT, link)
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(ValueError):
                self.E.export_artifact(ROOT, Path(raw) / "candidate")

    def test_manifest_is_portable_and_implementation_bound(self):
        with tempfile.TemporaryDirectory(dir=RUN) as raw:
            out = Path(raw) / "candidate"
            self.E.export_artifact(ROOT, out)
            m = json.loads((out / "manifest.json").read_text())
            self.assertEqual("accepted", m["artifact_status"])
            self.assertEqual("content_verified_independent_of_copy_path", m["artifact_portability"])
            self.assertEqual(set(self.C.IMPLEMENTATION_PATHS), set(m["implementation"]))
            self.assertEqual(list(self.C.OFFICIAL_EXPORT_COMMAND), m["producer"]["command"])
            self.assertEqual(list(self.C.OFFICIAL_VERIFY_COMMAND), m["verifier"]["command"])

    def test_exact_official_authorization_and_traversal_alias(self):
        official = ROOT / self.C.OFFICIAL_ARTIFACT
        self.assertEqual(official, self.E._authorized(ROOT, official))
        with self.assertRaises(ValueError):
            self.E._authorized(ROOT, ROOT / "artifacts/../rom-scene-source-closures-v1")

    def test_atomic_no_replace_preserves_both_trees(self):
        with tempfile.TemporaryDirectory(dir=RUN) as raw:
            base = Path(raw); source = base / "source"; destination = base / "destination"
            source.mkdir(); destination.mkdir()
            (source / "new").write_text("new"); (destination / "keep").write_text("keep")
            with self.assertRaises(FileExistsError):
                self.E._publish_exclusive(source, destination)
            self.assertEqual("new", (source / "new").read_text())
            self.assertEqual("keep", (destination / "keep").read_text())


if __name__ == "__main__":
    unittest.main()
