"""Frozen TDD suite for the boot register-init dependency CFG packet."""
from __future__ import annotations
import ast
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class BootRegisterInitDependencyCfgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_boot_register_init_dependency_cfg as exporter
        from tools import rom_boot_register_init_dependency_cfg_contract as contract
        from tools import verify_rom_boot_register_init_dependency_cfg as verifier
        cls.exporter, cls.contract, cls.verifier = exporter, contract, verifier
        cls.rom = (ROOT / contract.ROM_PATH).read_bytes()
        cls.payload = exporter.build_payload(ROOT)

    def test_frozen_identity_and_unique_raw_producer(self) -> None:
        self.assertEqual("rom-boot-register-init-dependency-cfg-v1", self.payload["schema"])
        self.assertEqual({"file_offset":0x06178C,"raw_hex":"30b581b0","entry_sha256":self.contract.ROOT_ENTRY_SHA256}, self.payload["root"])
        den = self.payload["producer_denominator"]
        self.assertEqual(([0,0x600000],2,1),(den["scan_range"],den["stride"],den["match_count"]))
        row = den["matches"][0]
        self.assertEqual((0x06109E,"thumb_bl","00f075fb",0x06178C),(row["file_offset"],row["kind"],row["raw_hex"],row["target_file_offset"]))
        self.assertTrue(row["accepted_as_root_proof"])

    def test_exact_upstream_owner(self) -> None:
        owner = self.payload["producer_owner"]
        self.assertEqual((True,"continuation-code-06108a-0610d4","armv4t_boot_interwork_continuation_code",[0x06108A,0x0610D4],"thumb"),(owner["verified"],owner["claim_id"],owner["primary_class"],owner["range"],owner["mode"]))
        self.assertEqual((self.contract.CONTINUATION_MANIFEST_SHA256,self.contract.CONTINUATION_PAYLOAD_SHA256,self.contract.CONTINUATION_VERIFIER_SHA256),(owner["manifest_sha256"],owner["payload_sha256"],owner["verifier_sha256"]))

    def test_producer_owner_binds_exact_hash_pinned_continuation_block(self) -> None:
        block=self.payload["producer_owner"]["producer_block"]
        self.assertEqual(
            {"id":"block-thumb-06109e","range":[0x06109E,0x0610A2],"mode":"thumb",
             "instruction_count":1,"bytes_sha256":self.contract.PRODUCER[5],
             "terminator":{"conditional":False,"file_offset":0x06109E,
                           "flow_kind":"call","mnemonic":"bl",
                           "op_str":"#0x806178c","raw_hex":"00f075fb","size":4},
             "call_target_successor":{"kind":"call_target","mode":"thumb",
                                      "resolution":"opaque_external_edge",
                                      "source_block_id":"block-thumb-06109e",
                                      "source_instruction_offset":0x06109E,
                                      "target_gba_address":"0x0806178C",
                                      "target_offset":0x06178C}}, block)
        for module in (self.exporter,self.verifier):
            bad=json.loads(json.dumps(block));bad["terminator"]["raw_hex"]="01f075fb"
            with self.subTest(module=module.__name__),self.assertRaises(ValueError):
                module._validate_producer_block(bad)

    def test_raw_cfg_denominators_ranges_and_hashes(self) -> None:
        cfg = self.payload["target_local_denominator"]
        self.assertEqual((154,318,12,32,3,3,0),tuple(cfg[k] for k in ("instruction_count","instruction_bytes","basic_block_count","literal_reference_count","opaque_call_count","frontier_count","structured_return_count")))
        self.assertEqual(self.contract.CODE_RANGES,tuple(map(tuple,cfg["code_ranges"])))
        self.assertEqual(self.contract.BLOCK_RANGES,tuple(map(tuple,cfg["block_ranges"])))
        self.assertEqual(self.contract.LITERAL_RANGES,tuple(map(tuple,cfg["literal_ranges"])))
        self.assertEqual(self.contract.CODE_RANGE_SHA256S,tuple(cfg["code_range_sha256s"]))
        self.assertEqual((self.contract.PACKED_CODE_SHA256,self.contract.BLOCK_VECTOR_SHA256,self.contract.LITERAL_BINDING_VECTOR_SHA256,self.contract.PACKED_LITERAL_SHA256),(cfg["packed_code_sha256"],cfg["block_vector_sha256"],cfg["literal_binding_vector_sha256"],cfg["packed_literal_sha256"]))

    def test_vector_hashes_are_recomputed_from_public_raw_derived_schema(self) -> None:
        cfg=self.payload["target_local_denominator"]
        digest=lambda value:hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        self.assertEqual({"start","end","instruction_count","bytes_sha256","terminator","successors","frontier"},set(cfg["block_vector"][0]))
        self.assertEqual({"source","source_raw_hex","target","word_hex","word_u32","word_sha256"},set(cfg["literal_bindings"][0]))
        self.assertEqual(digest(cfg["block_vector"]),cfg["block_vector_sha256"])
        self.assertEqual(digest(cfg["literal_bindings"]),cfg["literal_binding_vector_sha256"])

    def test_literals_exits_frontiers_and_exact_inventory_entry(self) -> None:
        cfg = self.payload["target_local_denominator"]
        self.assertEqual((32,32),(len(cfg["literal_bindings"]),len({x["target"] for x in cfg["literal_bindings"]})))
        self.assertEqual([(0x06202C,0x09C0E0,"3af058f8"),(0x062036,0x09C0E0,"3af053f8"),(0x062040,0x09C0E0,"3af04ef8")],[(x["source"],x["target"],x["raw_hex"]) for x in cfg["opaque_calls"]])
        self.assertEqual([(0x06181C,"0047","r0"),(0x06207A,"0047","r0"),(0x0620FE,"0047","r0")],[(x["file_offset"],x["raw_hex"],x["register"]) for x in cfg["frontiers"]])
        inv = self.payload["cfg_inventory"]
        self.assertEqual((True,"block-thumb-09c0e0",[0x09C0E0,0x09C0E2],"0bdf","cfg-thumb-0773-09c0d8",[0x09C0D8,0x09C0F4]),(inv["verified"],inv["entry_block"]["id"],inv["entry_block"]["range"],inv["entry_block"]["raw_hex"],inv["owner"]["claim_id"],inv["owner"]["range"]))

    def test_inventory_entry_and_owner_are_full_frozen_records(self) -> None:
        inv=self.payload["cfg_inventory"]
        self.assertEqual({"id":"block-thumb-09c0e0","range":[0x09C0E0,0x09C0E2],
                          "mode":"thumb","instruction_count":1,
                          "bytes_sha256":"38ac888b30c3f43dc0b29840880256705d34b3f73035d6daa036c7b61ab5db6e",
                          "raw_hex":"0bdf"},inv["entry_block"])
        self.assertEqual({"range":[0x09C0D8,0x09C0F4],
                          "primary_class":"armv4t_cfg_reachable_thumb_code",
                          "claim_id":"cfg-thumb-0773-09c0d8"},inv["owner"])
        for module in (self.exporter,self.verifier):
            for field,value in (("mode","arm"),("instruction_count",2),("raw_hex","0adf")):
                bad=json.loads(json.dumps(inv["entry_block"]));bad[field]=value
                with self.subTest(module=module.__name__,field=field),self.assertRaises(ValueError):
                    module._validate_inventory_records(bad,inv["owner"])
            bad_owner=json.loads(json.dumps(inv["owner"]));bad_owner["primary_class"]="unknown"
            with self.subTest(module=module.__name__,field="owner"),self.assertRaises(ValueError):
                module._validate_inventory_records(inv["entry_block"],bad_owner)

    def test_baseline_ordered_overlays_projection_promotion_and_holes(self) -> None:
        self.assertEqual((6198347,93109),tuple(self.payload["precoverage"][k] for k in ("classified_bytes","unknown_bytes")))
        overlays=self.payload["overlays"]
        self.assertEqual(["story_callback","v20","story_next"],[x["name"] for x in overlays])
        self.assertEqual([(32,1932,0),(18,1150,0),(19,854,0)],[(x["claim_count"],x["promotion_bytes"],x["overlap_bytes"]) for x in overlays])
        self.assertEqual((4382,6202729,88727),tuple(self.payload["coverage_projection"][k] for k in ("cumulative_promoted_bytes","classified_bytes","remaining_unknown_bytes")))
        p=self.payload["promotion"]
        self.assertEqual((8,318,128,446,4),(p["claim_count"],p["code_bytes"],p["literal_bytes"],p["promotion_bytes"],len(p["union_ranges"])))
        self.assertEqual(self.contract.UNION_RANGES,tuple(map(tuple,p["union_ranges"])))
        self.assertEqual(self.contract.PACKED_PROMOTION_SHA256,p["packed_promotion_sha256"])
        self.assertEqual(["0000"],[x["raw_hex"] for x in self.payload["preserved_unknown_holes"]])
        self.assertTrue(all(x["primary_class"]=="unknown" for x in self.payload["preserved_unknown_holes"]))
        exclusion = self.payload["outside_worklist_existing_owner_exclusions"][0]
        self.assertEqual(
            ([0x0620B4,0x0620CC],
             "00b504490878002801d00120887101bc00470000882f0003"),
            (exclusion["range"], exclusion["raw_hex"]),
        )
        self.assertEqual(
            [
                ([0x0620B4,0x0620C6],
                 "armv4t_boot_thumb_handoff_reachable_code",
                 "boot-thumb-handoff-code-11-0620b4"),
                ([0x0620C6,0x0620C8],
                 "boot_thumb_code_literal_alignment_bytes",
                 "boot-thumb-code-literal-gap-06-0620c6"),
                ([0x0620C8,0x0620CC],
                 "armv4t_boot_thumb_handoff_consumed_literal_pool",
                 "boot-thumb-handoff-literal-08-0620c8"),
            ],
            [(row["range"], row["primary_class"], row["claim_id"])
             for row in exclusion["owner_segments"]],
        )

    def test_raw_evidence_single_byte_mutations_fail_closed(self) -> None:
        bad=bytearray(self.rom);bad[-1]^=1
        with self.subTest(label="ROM identity"),self.assertRaises(ValueError):
            self.exporter.build_payload(ROOT,bytes(bad))
        bad=bytearray(self.rom);bad[0x06109E]^=1
        with self.subTest(label="producer denominator"),self.assertRaises(ValueError):
            self.exporter._producer_denominator(bytes(bad))
        for label,offset in {"root":0x06178C,"code":0x0617A0,"literal":0x0617DC,"exit":0x06202C,"frontier":0x06181C}.items():
            bad=bytearray(self.rom);bad[offset]^=1
            with self.subTest(label=label),self.assertRaises(ValueError):
                self.exporter._raw_cfg(ROOT,bytes(bad))

    def test_independent_verifier_raw_mutations_fail_before_payload_comparison(self) -> None:
        bad=bytearray(self.rom);bad[0x06109E]^=1
        with self.assertRaises(ValueError): self.verifier._producer_denominator(bytes(bad))
        for offset in (0x06178C,0x0617A0,0x0617DC,0x06202C,0x06181C):
            bad=bytearray(self.rom);bad[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError):
                self.verifier._raw_cfg(ROOT,bytes(bad))

    def test_independent_verifier_rebuilds_raw_evidence(self) -> None:
        source=(ROOT/"tools/verify_rom_boot_register_init_dependency_cfg.py").read_text()
        imports=[x for x in ast.walk(ast.parse(source)) if isinstance(x,(ast.Import,ast.ImportFrom))]
        self.assertFalse(any("export_rom_boot_register_init" in ast.unparse(x) for x in imports))
        for name in ("_producer_denominator","_raw_cfg","_literal_bindings"): self.assertIn(f"def {name}",source)

    def test_atomic_acceptance_stable_report_and_existing_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT/self.contract.EXPERIMENT_OUTPUT_ROOT) as raw:
            artifact=Path(raw)/"candidate";manifest=self.exporter.export(ROOT,artifact)
            self.assertEqual("accepted",manifest["artifact_status"])
            first=self.verifier.verify_root(ROOT,artifact);self.assertEqual(first,self.verifier.verify_root(ROOT,artifact));self.assertTrue(first["verified"])
            self.assertEqual((154,12,32,3,3,446),tuple(first[k] for k in ("instruction_count","basic_block_count","literal_word_count","opaque_call_count","frontier_count","promotion_bytes")))
            with self.assertRaises(ValueError): self.exporter.export(ROOT,artifact)

    def test_verifier_rejects_payload_mutation_noncanonical_and_extra_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT/self.contract.EXPERIMENT_OUTPUT_ROOT) as raw:
            artifact=Path(raw)/"candidate";self.exporter.export(ROOT,artifact);path=artifact/self.contract.PAYLOAD_NAME
            payload=json.loads(path.read_text());payload["promotion"]["promotion_bytes"]+=1;path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
            self.assertFalse(self.verifier.verify_root(ROOT,artifact)["verified"])
            path.write_text(json.dumps(payload,sort_keys=True));self.assertFalse(self.verifier.verify_root(ROOT,artifact)["verified"])
            (artifact/"extra").write_text("x");self.assertFalse(self.verifier.verify_root(ROOT,artifact)["verified"])

    def test_output_safety_rejects_symlink_ancestor_and_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as outside,tempfile.TemporaryDirectory(dir=ROOT/self.contract.EXPERIMENT_OUTPUT_ROOT) as raw:
            link=Path(raw)/"escape";os.symlink(outside,link)
            with self.assertRaises(ValueError): self.exporter.export(ROOT,link/"candidate")
            with self.assertRaises(ValueError): self.exporter.export(ROOT,Path(raw)/".."/".."/"escaped")

    def test_publish_uses_true_atomic_no_replace(self) -> None:
        source=(ROOT/"tools/export_rom_boot_register_init_dependency_cfg.py").read_text()
        self.assertIn("renameatx_np",source);self.assertIn("renameat2",source)
        with tempfile.TemporaryDirectory(dir=ROOT/self.contract.EXPERIMENT_OUTPUT_ROOT) as raw:
            parent=Path(raw);stage=parent/"stage";target=parent/"target"
            stage.mkdir();target.mkdir()
            with self.assertRaises(FileExistsError):
                self.exporter._publish_exclusive(stage,target)
            self.assertTrue(stage.is_dir());self.assertTrue(target.is_dir())

if __name__ == "__main__": unittest.main()
