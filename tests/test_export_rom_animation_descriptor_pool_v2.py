import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import export_rom_animation_descriptor_pool_v2 as exporter
from tools import verify_rom_animation_descriptor_pool_v2 as verifier


EXPORTER_PATH = ROOT / "tools/export_rom_animation_descriptor_pool_v2.py"
VERIFIER_PATH = ROOT / "tools/verify_rom_animation_descriptor_pool_v2.py"
TEST_PATH = ROOT / "tests/test_export_rom_animation_descriptor_pool_v2.py"

CLAIM_START = 0x45832C
CLAIM_END = 0x4585AC
TAIL_START = 0x4585AC
TAIL_END = 0x458794


def _mutate(rom: bytes, offset: int, raw: bytes) -> bytes:
    mutated = bytearray(rom)
    mutated[offset:offset + len(raw)] = raw
    return bytes(mutated)


def _walk(rom: bytes, start: int, stride: int, limit: int):
    """Return the first 0xFFFF head reached by stepping `stride` from `start`."""
    cursor = start
    while cursor + 2 <= limit:
        if rom[cursor:cursor + 2] == b"\xff\xff":
            return cursor
        cursor += stride
    return None


class StructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.payload = exporter.build_payload(ROOT)

    def test_claim_is_exactly_640_bytes(self):
        claim = self.payload["claim"]
        self.assertEqual(claim["range"], [CLAIM_START, CLAIM_END])
        self.assertEqual(claim["range"][1] - claim["range"][0], 640)
        self.assertEqual(claim["bytes"], 640)
        self.assertEqual(
            claim["bytes_sha256"],
            "9be0375fab3cd7f25c99d6cdcfedfd3727d5d787b56532ac72894c74f5ec511c",
        )

    def test_promotion_claims_only_the_640_bytes(self):
        promotion = self.payload["promotion"]
        self.assertEqual(promotion["claim_count"], 1)
        self.assertEqual(promotion["promotion_bytes"], 640)
        self.assertEqual(promotion["promoted_from_primary_class"], "unknown")
        self.assertEqual(promotion["promotion_batch"], exporter.SCHEMA)
        claim = promotion["claims"][0]
        self.assertEqual(claim["range"], [CLAIM_START, CLAIM_END])
        self.assertEqual(claim["primary_class"],
                         "fixed_consumer_animation_descriptor_group_bytes")
        self.assertEqual(claim["claim_kind"],
                         "fixed_consumer_animation_descriptor_group_bytes")

    def test_eight_descriptors_carry_24_entries(self):
        descriptors = self.payload["descriptors"]
        self.assertEqual(descriptors["descriptor_count"], 8)
        self.assertEqual(descriptors["entry_count"], 24)
        self.assertEqual(len(descriptors["items"]), 8)
        self.assertEqual(sum(item["entry_count"] for item in descriptors["items"]), 24)
        self.assertEqual([item["entry_count"] for item in descriptors["items"]],
                         [12, 4, 1, 1, 2, 2, 1, 1])

    def test_descriptor_sizes_are_variable_and_end_with_a_two_byte_head(self):
        descriptors = self.payload["descriptors"]
        self.assertEqual(descriptors["entry_stride"], 0x14)
        self.assertEqual(descriptors["terminator_value"], 0xFFFF)
        self.assertEqual(descriptors["terminator_width"], 2)
        self.assertEqual(descriptors["terminator_position"], "head")
        sizes = set()
        for item in descriptors["items"]:
            size = item["range"][1] - item["range"][0]
            sizes.add(size)
            self.assertEqual(size, 0x14 * item["entry_count"] + 2)
            # The old table's four-byte 0x0000FFFF terminator must not apply.
            self.assertNotEqual(size, 0x14 * item["entry_count"] + 4)
            self.assertEqual(self.rom[item["terminator_offset"]:item["terminator_offset"] + 2],
                             b"\xff\xff")
        self.assertEqual(len(sizes), 4, "descriptor sizes must stay variable")
        self.assertIn(0x52, sizes)
        self.assertNotIn(0x54, sizes)

    def test_old_fixed_0x54_stride_is_falsified(self):
        descriptors = self.payload["descriptors"]
        for item in descriptors["items"]:
            start = item["range"][0]
            self.assertEqual(_walk(self.rom, start, 0x14, CLAIM_END),
                             item["terminator_offset"])
            legacy = _walk(self.rom, start, 0x54, CLAIM_END)
            self.assertNotEqual(legacy, item["terminator_offset"],
                                "the 0x54 stride must not reproduce a terminator")

    def test_eight_sequences_carry_a_u32_terminator(self):
        sequences = self.payload["sequences"]
        self.assertEqual(sequences["sequence_count"], 8)
        self.assertEqual(sequences["sequence_bytes"], 64)
        self.assertEqual(sequences["item_size"], 8)
        self.assertEqual(sequences["terminator_value"], 0x0000FFFF)
        self.assertEqual(sequences["terminator_width"], 4)
        self.assertEqual([item["record_index"] for item in sequences["items"]],
                         [0, 1, 0, 0, 0, 0, 0, 0])
        self.assertEqual([item["duration"] for item in sequences["items"]],
                         [1, 0, 1, 1, 1, 1, 1, 1])
        for item in sequences["items"]:
            self.assertEqual(self.rom[item["range"][1] - 4:item["range"][1]],
                             b"\xff\xff\x00\x00")

    def test_seven_base_pairs_bind_r0_and_r1(self):
        pairs = self.payload["base_pairs"]
        self.assertEqual(pairs["pair_count"], 7)
        self.assertEqual(len(pairs["items"]), 7)
        for index, pair in enumerate(pairs["items"]):
            self.assertEqual(pair["pair_index"], index)
            self.assertEqual(pair["r0_literal"],
                             0x08000000 + pair["descriptor_table_address"])
            self.assertEqual(pair["r1_literal"],
                             0x08000000 + pair["group_table_address"])
            self.assertEqual(len(pair["descriptor_targets"]),
                             pair["descriptor_table_slots"])
            self.assertEqual(len(pair["group_targets"]), pair["group_table_slots"])
        self.assertEqual(sum(pair["descriptor_table_slots"] for pair in pairs["items"]), 8)
        self.assertEqual(sum(pair["group_table_slots"] for pair in pairs["items"]), 8)

    def test_pointer_slot_denominator_is_sixteen(self):
        slots = self.payload["pointer_slots"]
        self.assertEqual(slots["slot_count"], 16)
        self.assertEqual(slots["pointer_slot_bytes"], 64)
        self.assertEqual(slots["table_count"], 14)
        self.assertEqual(sum(table["slot_count"] for table in slots["tables"]), 16)
        kinds = [table["kind"] for table in slots["tables"]]
        self.assertEqual(kinds.count("descriptor_table"), 7)
        self.assertEqual(kinds.count("group_table"), 7)

    def test_byte_attribution_leaves_nothing_unattributed(self):
        attribution = self.payload["byte_attribution"]
        self.assertEqual(attribution["total_bytes"], 640)
        self.assertEqual(attribution["descriptor_bytes"], 496)
        self.assertEqual(attribution["sequence_bytes"], 64)
        self.assertEqual(attribution["pointer_slot_bytes"], 64)
        self.assertEqual(attribution["padding_bytes"], 16)
        self.assertEqual(attribution["unattributed_bytes"], 0)
        self.assertEqual(
            attribution["descriptor_bytes"] + attribution["sequence_bytes"]
            + attribution["pointer_slot_bytes"] + attribution["padding_bytes"],
            640)

    def test_padding_is_eight_zero_pairs(self):
        padding = self.payload["padding"]
        self.assertEqual(padding["segment_count"], 8)
        self.assertEqual(padding["padding_bytes"], 16)
        expected = [0x45841E, 0x458472, 0x4584AA, 0x4584D2,
                    0x45850E, 0x45854A, 0x458572, 0x45859A]
        self.assertEqual([item["range"][0] for item in padding["items"]], expected)
        for item in padding["items"]:
            self.assertEqual(item["range"][1] - item["range"][0], 2)
            self.assertEqual(self.rom[item["range"][0]:item["range"][1]], b"\x00\x00")

    def test_excluded_tail_is_488_bytes_of_a_foreign_family(self):
        excluded = self.payload["excluded_regions"]
        self.assertEqual(len(excluded), 1)
        region = excluded[0]
        self.assertEqual(region["range"], [TAIL_START, TAIL_END])
        self.assertEqual(region["bytes"], 488)
        self.assertEqual(
            region["bytes_sha256"],
            "11d1938dc0a00025ed1e953ba3e7e69892467f757a1de07fbc162cdc5b6c0f69")
        self.assertFalse(region["inside_claim"])
        self.assertFalse(region["family_attributed"])
        self.assertIn("LV", region["reason"])
        claim = self.payload["claim"]
        self.assertEqual(claim["range"][1], TAIL_START)
        self.assertLess(claim["range"][1], TAIL_END)

    def test_literal_occurrence_denominator_is_six(self):
        consumer = self.payload["consumer_contract"]
        pinned = consumer["pinned_literal_occurrence_denominator"]
        self.assertEqual(
            pinned["0x0845854C"],
            [0x06F958, 0x078068, 0x0789EC, 0x093C40, 0x094DD0, 0x094E7C])
        self.assertEqual(
            pinned["0x08458558"],
            [0x06F95C, 0x07806C, 0x0789F0, 0x093C44, 0x094DD4, 0x094E80])
        self.assertEqual(
            pinned["0x08458510"],
            [0x0710D8, 0x08AEF8, 0x08BD64, 0x0909B0, 0x092654, 0x094DC0])
        self.assertEqual(
            pinned["0x0845851C"],
            [0x0710DC, 0x08AEFC, 0x08BD68, 0x0909B4, 0x092658, 0x094DC4])
        for value, offsets in pinned.items():
            self.assertEqual(len(offsets), 6, value)

    def test_every_literal_site_binds_r0_and_r1(self):
        binding = self.payload["consumer_contract"]["literal_loader_binding"]
        self.assertEqual(binding["r0_literal_occurrence_count"], 48)
        self.assertEqual(binding["r1_literal_occurrence_count"], 48)
        self.assertEqual(binding["literal_occurrence_count"], 96)
        self.assertEqual(binding["base_pair_pool_count"], 48)
        for entry in binding["descriptor_table_literals"].values():
            self.assertEqual(entry["register"], "r0")
            self.assertEqual(len(entry["sites"]), entry["occurrence_denominator"])
        for entry in binding["group_table_literals"].values():
            self.assertEqual(entry["register"], "r1")

    def test_caller_denominator_is_declared_open(self):
        denominator = self.payload["consumer_contract"]["caller_site_denominator"]
        self.assertEqual(denominator["base_pair_count"], 7)
        self.assertEqual(denominator["base_pair_pools"], 48)
        self.assertEqual(denominator["attributed_callers"], 2)
        self.assertEqual(denominator["attributed_pools"], 2)
        self.assertEqual(denominator["unattributed_pools"], 46)
        self.assertFalse(denominator["closed"])

    def test_located_callers_are_pinned_to_the_allocator(self):
        consumer = self.payload["consumer_contract"]
        self.assertEqual(consumer["located_caller_count"], 2)
        callers = consumer["located_callers"]
        self.assertEqual(callers[0]["code_range"], [0x06F908, 0x06F920])
        self.assertEqual(callers[0]["literal_load_halfwords"], [0x4812, 0x4913])
        self.assertEqual(callers[0]["literal_values"], [0x0845854C, 0x08458558])
        self.assertEqual(callers[0]["call_site"], 0x06F914)
        self.assertEqual(callers[0]["call_target"], 0x0626B4)
        self.assertEqual(callers[1]["code_range"], [0x071040, 0x071060])
        self.assertEqual(callers[1]["literal_load_halfwords"], [0x4824, 0x4925])
        self.assertEqual(callers[1]["literal_values"], [0x08458510, 0x0845851C])
        self.assertEqual(callers[1]["call_site"], 0x071060)
        self.assertEqual(callers[1]["call_target"], 0x0626B4)
        self.assertEqual(consumer["allocator_object_fields"],
                         {"group_index": 0x14, "record_slot": 0x16,
                          "descriptor_table": 0x1C, "group_table": 0x20})

    def test_upstream_consumer_segments_are_pinned(self):
        ranges = self.payload["consumer_contract"]["identity_ranges"]
        pinned = {row["label"]: (row["range"], row["bytes_sha256"]) for row in ranges}
        self.assertEqual(pinned["allocator"],
                         ([0x0626B4, 0x062766],
                          "09cd85fb8fcdc85751019c67ef6b91d6d3d64c1fbeb0b0496e270234f846d804"))
        self.assertEqual(pinned["renderer_select"],
                         ([0x062924, 0x062A0A],
                          "23ead2fcc1537d16a632bf68dbccdb96a142af170410f862baaf4c1d750e0a18"))
        self.assertEqual(pinned["renderer_step"],
                         ([0x0631F6, 0x063208],
                          "79cb19c28c7f5a75ed323f99c837e131c0e11dd06c91f422e60ac9ff859e8f44"))
        self.assertEqual(pinned["renderer_advance"],
                         ([0x063238, 0x0632BA],
                          "b6dc39ac66ecaac48e16f37406bab7e579362759e9e3570e9c6fa9e24ec0ab23"))

    def test_scope_is_entirely_false(self):
        scope = self.payload["scope"]
        self.assertTrue(scope)
        for key, value in scope.items():
            self.assertFalse(value, key)

    def test_scope_declares_every_open_obligation(self):
        scope = self.payload["scope"]
        for key in ("caller_denominator_closed", "flags_domain_closed",
                    "callback_domain_closed", "heterogeneous_tail_family_closed",
                    "natural_runtime_reachability"):
            self.assertIn(key, scope)
            self.assertFalse(scope[key])
        notes = self.payload["scope_notes"]
        self.assertIn("caller denominator is not closed", notes["caller_denominator_closed"])
        self.assertIn("flag domain is not closed", notes["flags_domain_closed"])
        self.assertIn("callback domain is not closed", notes["callback_domain_closed"])
        self.assertIn("488-byte tail", notes["heterogeneous_tail_family_closed"])
        self.assertIn("normal play", notes["natural_runtime_reachability"])


class VerifierIndependenceTests(unittest.TestCase):
    def test_verifier_does_not_import_exporter(self):
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        for name in imported:
            self.assertNotIn("export_rom_animation_descriptor_pool_v2", name)
        self.assertNotIn("importlib", imported)
        self.assertNotIn("__import__", source)

    def test_verifier_rebuild_matches_exporter_payload(self):
        rebuilt = verifier._rebuild((ROOT / "rom/base.gba").read_bytes())
        self.assertEqual(rebuilt, exporter.build_payload(ROOT))

    def test_both_sides_agree_byte_for_byte(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        self.assertEqual(verifier._canonical(verifier._rebuild(rom)),
                         exporter._canonical(exporter.build_payload(ROOT)))


class MutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def _expect_both_rejected(self, rom: bytes, message: str):
        with self.assertRaisesRegex(ValueError, message):
            exporter._build_from_rom(ROOT, rom, verify_identity=False)
        with self.assertRaisesRegex(ValueError, message):
            verifier._rebuild(rom, verify_identity=False)

    def test_rom_identity_is_still_checked_by_default(self):
        mutated = _mutate(self.rom, 0x45832C, b"\x02")
        with self.assertRaisesRegex(ValueError, "ROM identity changed"):
            exporter._build_from_rom(ROOT, mutated)
        with self.assertRaisesRegex(ValueError, "ROM identity changed"):
            verifier._rebuild(mutated)

    def test_descriptor_entry_count_is_rejected_by_both_sides(self):
        mutated = _mutate(self.rom, 0x4584A8, b"\x00\x00")
        self._expect_both_rejected(mutated, "descriptor entry denominator changed")

    def test_descriptor_entry_head_terminator_is_rejected_by_both_sides(self):
        mutated = _mutate(self.rom, 0x45832C, b"\xff\xff")
        self._expect_both_rejected(mutated, "descriptor has no entries")

    def test_descriptor_terminator_is_rejected_by_both_sides(self):
        mutated = _mutate(self.rom, 0x458598, b"\x00\x00")
        self._expect_both_rejected(mutated, "descriptor terminator missing")

    def test_sequence_terminator_is_rejected_by_both_sides(self):
        mutated = _mutate(self.rom, 0x4585A4, b"\x00\x00")
        self._expect_both_rejected(mutated, "pointer table kind denominator changed")

    def test_pointer_slot_is_rejected_by_both_sides(self):
        mutated = _mutate(self.rom, 0x458474, b"\x00")
        self._expect_both_rejected(mutated, "pointer slot denominator changed")

    def test_caller_load_halfword_is_rejected_by_both_sides(self):
        mutated = _mutate(self.rom, 0x06F90D, b"\x00")
        self._expect_both_rejected(mutated, "caller literal load halfword changed")

    def test_caller_call_halfword_is_rejected_by_both_sides(self):
        mutated = _mutate(self.rom, 0x06F915, b"\x00")
        self._expect_both_rejected(mutated, "caller call halfword changed")

    def test_caller_code_is_rejected_by_both_sides(self):
        mutated = _mutate(self.rom, 0x06F908, b"\x00")
        self._expect_both_rejected(mutated, "caller a identity changed")

    def test_caller_literal_pool_is_rejected_by_both_sides(self):
        mutated = _mutate(self.rom, 0x06F958, b"\x00")
        self._expect_both_rejected(mutated, "caller a literal pool identity changed")

    def test_literal_occurrence_denominator_is_rejected_by_both_sides(self):
        mutated = _mutate(self.rom, 0x078068, b"\x00")
        self._expect_both_rejected(mutated, "consumer literal denominator changed")

    def test_upstream_allocator_segment_is_rejected_by_both_sides(self):
        mutated = _mutate(self.rom, 0x0626B4, b"\x00")
        self._expect_both_rejected(mutated, "allocator identity changed")

    def test_upstream_renderer_select_segment_is_rejected_by_both_sides(self):
        mutated = _mutate(self.rom, 0x062924, b"\x00")
        self._expect_both_rejected(mutated, "renderer select identity changed")

    def test_upstream_renderer_step_segment_is_rejected_by_both_sides(self):
        mutated = _mutate(self.rom, 0x0631F6, b"\x00")
        self._expect_both_rejected(mutated, "renderer step identity changed")

    def test_upstream_renderer_advance_segment_is_rejected_by_both_sides(self):
        mutated = _mutate(self.rom, 0x063239, b"\x00")
        self._expect_both_rejected(mutated, "renderer advance identity changed")

    def test_claim_bytes_are_rejected_by_both_sides(self):
        mutated = _mutate(self.rom, 0x458330, b"\x00")
        self._expect_both_rejected(mutated, "claim identity changed")

    def test_excluded_tail_is_rejected_by_both_sides(self):
        mutated = _mutate(self.rom, TAIL_START, b"\x00")
        self._expect_both_rejected(mutated, "full segment identity changed")


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = ROOT / "build/experiments"
        cls.scratch.mkdir(parents=True, exist_ok=True)

    def _output(self, tmp: str) -> Path:
        return Path(tmp) / "artifacts" / "rom-animation-descriptor-pool-v2"

    def test_roundtrip_export_then_verify(self):
        with tempfile.TemporaryDirectory(dir=self.scratch) as tmp:
            output = self._output(tmp)
            exporter.export_artifact(ROOT, output)
            report = verifier.verify_artifact(ROOT, output)
            self.assertTrue(report["verified"], report["errors"])
            self.assertEqual(report["descriptor_count"], 8)
            self.assertEqual(report["descriptor_entry_count"], 24)
            self.assertEqual(report["base_pair_count"], 7)
            self.assertEqual(report["promotion_bytes"], 640)

    def test_manifest_carries_the_three_implementation_hashes(self):
        with tempfile.TemporaryDirectory(dir=self.scratch) as tmp:
            output = self._output(tmp)
            exporter.export_artifact(ROOT, output)
            manifest = json.loads((output / exporter.MANIFEST_NAME).read_text(
                encoding="utf-8"))
            implementation = manifest["implementation"]
            for key, path in (("exporter_sha256", EXPORTER_PATH),
                              ("verifier_sha256", VERIFIER_PATH),
                              ("test_sha256", TEST_PATH)):
                self.assertEqual(implementation[key],
                                 hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(manifest["summary"]["promotion_bytes"], 640)
            self.assertEqual(manifest["summary"]["descriptor_count"], 8)
            self.assertEqual(manifest["summary"]["descriptor_entry_count"], 24)
            self.assertEqual(manifest["summary"]["base_pair_count"], 7)

    def test_export_refuses_to_overwrite_an_existing_artifact(self):
        with tempfile.TemporaryDirectory(dir=self.scratch) as tmp:
            output = self._output(tmp)
            exporter.export_artifact(ROOT, output)
            with self.assertRaises(FileExistsError):
                exporter.export_artifact(ROOT, output)

    def test_verifier_rejects_a_tampered_payload(self):
        with tempfile.TemporaryDirectory(dir=self.scratch) as tmp:
            output = self._output(tmp)
            exporter.export_artifact(ROOT, output)
            payload_path = output / exporter.PAYLOAD_NAME
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["descriptors"]["entry_count"] = 23
            payload_path.write_bytes(exporter._canonical(payload))
            report = verifier.verify_artifact(ROOT, output)
            self.assertFalse(report["verified"])

    def test_verifier_rejects_a_tampered_scope(self):
        with tempfile.TemporaryDirectory(dir=self.scratch) as tmp:
            output = self._output(tmp)
            exporter.export_artifact(ROOT, output)
            payload_path = output / exporter.PAYLOAD_NAME
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["scope"]["natural_runtime_reachability"] = True
            payload_path.write_bytes(exporter._canonical(payload))
            report = verifier.verify_artifact(ROOT, output)
            self.assertFalse(report["verified"])

    def test_verifier_rejects_a_tampered_manifest(self):
        with tempfile.TemporaryDirectory(dir=self.scratch) as tmp:
            output = self._output(tmp)
            exporter.export_artifact(ROOT, output)
            manifest_path = output / exporter.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["summary"]["promotion_bytes"] = 1128
            manifest_path.write_bytes(exporter._canonical(manifest))
            report = verifier.verify_artifact(ROOT, output)
            self.assertFalse(report["verified"])

    def test_verifier_rejects_an_extra_artifact_member(self):
        with tempfile.TemporaryDirectory(dir=self.scratch) as tmp:
            output = self._output(tmp)
            exporter.export_artifact(ROOT, output)
            (output / "extra.json").write_text("{}", encoding="utf-8")
            report = verifier.verify_artifact(ROOT, output)
            self.assertFalse(report["verified"])

    def test_verifier_rejects_a_missing_artifact_directory(self):
        with tempfile.TemporaryDirectory(dir=self.scratch) as tmp:
            report = verifier.verify_artifact(ROOT, Path(tmp) / "absent")
            self.assertFalse(report["verified"])


class CommandLineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = ROOT / "build/experiments"
        cls.scratch.mkdir(parents=True, exist_ok=True)

    def test_exporter_and_verifier_cli_run_from_the_repository_root(self):
        with tempfile.TemporaryDirectory(dir=self.scratch) as tmp:
            relative = (Path(tmp) / "artifacts"
                        / "rom-animation-descriptor-pool-v2").relative_to(ROOT)
            exported = subprocess.run(
                [sys.executable, "tools/export_rom_animation_descriptor_pool_v2.py",
                 "--root", ".", "--output", relative.as_posix()],
                cwd=str(ROOT), capture_output=True, text=True)
            self.assertEqual(exported.returncode, 0, exported.stderr)
            verified = subprocess.run(
                [sys.executable, "tools/verify_rom_animation_descriptor_pool_v2.py",
                 "--root", ".", "--artifact", relative.as_posix()],
                cwd=str(ROOT), capture_output=True, text=True)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            report = json.loads(verified.stdout)
            self.assertTrue(report["verified"], report)
            self.assertEqual(report["promotion_bytes"], 640)

    def test_verifier_cli_reports_a_missing_artifact(self):
        with tempfile.TemporaryDirectory(dir=self.scratch) as tmp:
            completed = subprocess.run(
                [sys.executable, "tools/verify_rom_animation_descriptor_pool_v2.py",
                 "--root", ".", "--artifact", (Path(tmp) / "absent").as_posix()],
                cwd=str(ROOT), capture_output=True, text=True)
            self.assertEqual(completed.returncode, 1)
            self.assertFalse(json.loads(completed.stdout)["verified"])


class HygieneTests(unittest.TestCase):
    def test_new_files_hold_no_local_absolute_paths(self):
        needles = [str(Path.home()), "/" + "Users" + "/", "/" + "private" + "/var/"]
        for path in (EXPORTER_PATH, VERIFIER_PATH, TEST_PATH):
            text = path.read_text(encoding="utf-8")
            for needle in needles:
                self.assertNotIn(needle, text, f"{path.name} contains {needle}")

    def test_artifact_published_under_the_contracted_directory(self):
        official = ROOT / "artifacts/rom-animation-descriptor-pool-v2"
        self.assertTrue(official.is_dir(), "the official artifact must be published")
        report = verifier.verify_artifact(ROOT, official)
        self.assertTrue(report["verified"], report["errors"])


if __name__ == "__main__":
    unittest.main()
