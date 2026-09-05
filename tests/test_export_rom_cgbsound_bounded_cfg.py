from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom/base.gba"
CONTRACT_PATH = ROOT / "build/experiments/active/cgbsound-contract/codex-r1-20260829/CONTRACT.json"
RUN = ROOT / "build/experiments/active/cgbsound-bounded-cfg-20260829"
CONTRACT_SHA = "12171aa29cd29d14f26dc491e4b0a5bb8ddd3fe6d6daac9f73e732786194561a"
PROMOTION_SHA = "edebdbe6e5cf5f9cf04fdb93839846f7e37e6516914b77a7517413c88ee9a151"
CFG_HASHES = {
    "semantic_instruction_vector_sha256": "07671aee1abdfc89e88571dc3589b56d61fa2763e5b403f2b415ac270f148204",
    "block_range_vector_sha256": "d7ec26b89231c6129cd49ecae68c80b9ffef223e8665c71aa39bfc6a2f843837",
    "edge_vector_sha256": "0380614c5c113eb322a59cff00d41aea0f03e696529d6be18f47d9c6d1bacab6",
}


def load_module():
    try:
        return importlib.import_module("tools.export_rom_cgbsound_bounded_cfg")
    except ModuleNotFoundError:
        return None


class ExportCgbsoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.contract = json.loads(CONTRACT_PATH.read_bytes())
        cls.rom = ROM.read_bytes()

    def implemented(self):
        self.assertIsNotNone(self.module, "CgbSound exporter is absent")
        return self.module

    def test_contract_promotion_and_binary(self):
        m = self.implemented()
        self.assertEqual(hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest(), CONTRACT_SHA)
        payload, binary = m.build_payload(ROOT)
        self.assertEqual(len(binary), 1084)
        self.assertEqual(hashlib.sha256(binary).hexdigest(), PROMOTION_SHA)
        self.assertEqual(payload["promotion"], self.contract["promotion"])
        self.assertEqual(len(payload["promotion_ranges"]), 19)
        canonical=lambda x:json.dumps(x,separators=(",",":"),sort_keys=False).encode()
        ranges=[r["range"] for r in payload["promotion_ranges"]]
        for row in payload["promotion_ranges"]:
            a,b=row["range"]; raw=self.rom[a:b]; self.assertEqual((len(raw),hashlib.sha256(raw).hexdigest()),(row["bytes"],row["sha256"]))
        self.assertEqual(hashlib.sha256(canonical(ranges)).hexdigest(),payload["promotion"]["range_vector_sha256"])
        code=self.contract["cfg"]["code_ranges"]; literals=self.contract["literal_projection"]["ranges"]
        self.assertEqual(hashlib.sha256(canonical(code)).hexdigest(),self.contract["cfg"]["code_range_vector_sha256"])
        self.assertEqual(hashlib.sha256(canonical(literals)).hexdigest(),self.contract["literal_projection"]["range_vector_sha256"])
        self.assertEqual(hashlib.sha256(b"".join(self.rom[a:b] for a,b in code)).hexdigest(),self.contract["cfg"]["packed_code_sha256"])
        a,b=self.contract["envelope"]["range"];self.assertEqual(hashlib.sha256(self.rom[a:b]).hexdigest(),self.contract["envelope"]["sha256"])

    def test_raw_cfg_capstone_vectors_calls_and_fallthroughs(self):
        cfg = self.implemented().analyze_cfg_from_rom(self.rom)
        self.assertEqual((cfg["instruction_count"], cfg["code_bytes"], cfg["block_count"]), (501, 1008, 100))
        self.assertEqual((cfg["internal_edge_count"], cfg["external_edge_count"], cfg["total_graph_edge_count"]), (148, 3, 151))
        self.assertEqual((cfg["structured_return_count"], cfg["frontier_count"]), (1, 0))
        for key, value in CFG_HASHES.items():
            self.assertEqual(cfg[key], value)
        calls = [(e["source_instruction_offset"], e["target_offset"], e["kind"]) for e in cfg["block_edges"] if e["kind"] == "opaque_call"]
        self.assertEqual(calls, [(636654, 636300, "opaque_call"), (636882, 636220, "opaque_call"), (636976, 636300, "opaque_call")])
        edges = {(e["source_instruction_offset"], e["target_offset"], e["kind"]) for e in cfg["block_edges"]}
        for edge in ((636654, 636658, "fallthrough"), (636882, 636886, "fallthrough"), (636976, 636980, "fallthrough")):
            self.assertIn(edge, edges)
        starts = {i["offset"] for i in cfg["instructions"]}
        self.assertTrue({636656, 636884, 636978}.isdisjoint(starts))
        self.assertTrue({636220, 636300}.isdisjoint(starts))

    def test_raw_decoder_mutations_reach_correct_checks(self):
        m = self.implemented()
        for offset in (636655, 636656, 636882, 637500):
            changed = bytearray(self.rom); changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                m.analyze_cfg_from_rom(bytes(changed), check_identity=False)
        with self.assertRaises(ValueError):
            m.analyze_cfg_from_rom(self.rom, roots=[636405], check_identity=False)

    def test_raw_direct_branches_reject_middle_gap_literal_and_escape(self):
        m=self.implemented();source=636404
        for kind,target in (("literal",636436),("gap",636534),("middle",636656),("outside",638000)):
            delta=target-(source+4);changed=bytearray(self.rom);changed[source:source+2]=struct.pack("<H",0xE000|((delta>>1)&0x7ff))
            with self.subTest(kind=kind),self.assertRaises(ValueError):m.analyze_cfg_from_rom(bytes(changed),check_identity=False)
        target=636534;delta=target-(source+4);changed=bytearray(self.rom);changed[source:source+2]=struct.pack("<H",0xD000|((delta>>1)&0xff))
        with self.assertRaises(ValueError):m.analyze_cfg_from_rom(bytes(changed),check_identity=False)

    def test_epilogue_pop_r0_and_bx_r0_are_full_sequence_bound(self):
        m = self.implemented()
        expected = self.contract["cfg"]["structured_return"]
        self.assertEqual(m.analyze_structured_return(self.rom), expected)
        for offset in range(637486, 637502):
            changed = bytearray(self.rom); changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                m.analyze_structured_return(bytes(changed))

    def test_all_literal_bindings_are_raw_unique_and_not_code(self):
        payload, _ = self.implemented().build_payload(ROOT)
        p = payload["literal_projection"]
        self.assertEqual((p["binding_count"], p["word_count"], p["bytes"]), (19, 19, 76))
        self.assertEqual(len({r[1] for r in p["bindings"]}), 19)
        self.assertEqual(len({r[2] for r in p["bindings"]}), 19)
        for consumer, literal, value, load_hex, literal_hex in p["bindings"]:
            h = struct.unpack("<H", bytes.fromhex(load_hex))[0]
            self.assertEqual(literal, ((consumer + 4) & ~3) + (h & 255) * 4)
            self.assertEqual(self.rom[literal:literal + 4].hex(), literal_hex)
            self.assertEqual(struct.unpack_from("<I", self.rom, literal)[0], value)
        canonical=lambda x:json.dumps(x,separators=(",",":"),sort_keys=False).encode()
        ranges=p["ranges"]; packed=b"".join(self.rom[a:b] for a,b in ranges)
        self.assertEqual(hashlib.sha256(canonical(p["bindings"])).hexdigest(), p["binding_vector_sha256"])
        self.assertEqual(hashlib.sha256(canonical(ranges)).hexdigest(), p["range_vector_sha256"])
        self.assertEqual(hashlib.sha256(packed).hexdigest(), p["packed_sha256"])
        code={o for a,b in self.contract["cfg"]["code_ranges"] for o in range(a,b)}; literal={o for a,b in ranges for o in range(a,b)}; gaps={o for a,b in self.contract["excluded_ranges"]["ranges"] for o in range(a,b)}
        self.assertFalse(code & literal or code & gaps or literal & gaps)

    def test_initializer_is_decoded_and_upstream_bound(self):
        m = self.implemented(); row = m.analyze_initializer(ROOT, self.rom)
        self.assertEqual(row, self.contract["initializer_binding"])
        self.assertEqual(row["destination_address"], row["structure_base"] + row["field_offset"])
        sem=m.decode_initializer_semantics(self.rom)
        self.assertEqual(sem["load"],{"offset":634220,"rt":"r0","pc_base":634224,"literal_offset":634364,"value":0x0809B5F5})
        self.assertEqual(sem["store"],{"offset":634222,"source":"r0","base":"r4","width":"word","field_offset":40})
        for offset in range(634220,634224):
            changed = bytearray(self.rom); changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError): m.analyze_initializer(ROOT, bytes(changed))

    def test_producer_is_scanned_and_vector_is_recomputed(self):
        m = self.implemented(); got = m.scan_producers(self.rom)
        self.assertEqual(got, self.contract["producer_denominator"])
        self.assertEqual(got["vector_sha256"], "8482c0fcd5cc2cfae53554ad4b1a06f5c6e92d69892179885e0b2a49a3a7fe55")
        changed = bytearray(self.rom); changed[600000:600004] = struct.pack("<I", 0x0809B5F5)
        with self.assertRaises(ValueError):
            m.scan_producers(bytes(changed))
        row=got["target"]; raw=json.dumps([row],separators=(",",":"),sort_keys=True).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), got["vector_sha256"])

    def test_every_other_producer_form_is_injected_and_rejected(self):
        m=self.implemented(); source=636000; conditional_source=636200; target=636404; delta=target-(source+4); cdelta=target-(conditional_source+4)
        variants={
            "thumb_b":struct.pack("<H",0xE000|((delta>>1)&0x7ff)),
            "thumb_b_conditional":struct.pack("<H",0xD000|((cdelta>>1)&0xff)),
            "thumb_bl":struct.pack("<HH",0xF000|((delta>>12)&0x7ff),0xF800|((delta>>1)&0x7ff)),
            "arm_b":struct.pack("<I",0xEA000000|(((target-(source+8))>>2)&0xffffff)),
            "arm_bl":struct.pack("<I",0xEB000000|(((target-(source+8))>>2)&0xffffff)),
            "bytewise_u32_entry":struct.pack("<I",0x08000000+target),
        }
        for name,raw in variants.items():
            at=conditional_source if name=="thumb_b_conditional" else source;changed=bytearray(self.rom);changed[at:at+len(raw)]=raw
            with self.subTest(name=name),self.assertRaises(ValueError):m.scan_producers(bytes(changed))

    def test_coverage_bad_shapes_owners_and_overlap_fail(self):
        m=self.implemented(); c=self.contract
        fixture={"schema":"rom-byte-coverage-v1","summary":dict(c["coverage_baseline"]["summary"]),"segments":[{"range":[636220,638132],"primary_class":"unknown","primary_claim_ids":[]},{"range":[634304,634384],"primary_class":"m4a_initializer_chain_consumed_literal_bytes","primary_claim_ids":["psg-initializer-literals-09adc0"]}]}
        m.analyze_coverage_baseline(fixture)
        for bad in (None,[],"x"):
            with self.assertRaises(ValueError): m.analyze_coverage_baseline(bad)
        drift=json.loads(json.dumps(fixture));drift["summary"]["unknown_bytes"]+=1
        with self.assertRaises(ValueError):m.analyze_coverage_baseline(drift)
        duplicate=json.loads(json.dumps(fixture));duplicate["segments"].append({"range":[636404,636436],"primary_class":"unknown","primary_claim_ids":[]})
        with self.assertRaises(ValueError):m.analyze_coverage_baseline(duplicate)
        owner=json.loads(json.dumps(fixture));owner["segments"][1]["primary_claim_ids"]=["foreign"]
        with self.assertRaises(ValueError):m.analyze_coverage_baseline(owner)
        right=json.loads(json.dumps(fixture));right["segments"][0:1]=[{"range":[636220,636500],"primary_class":"unknown","primary_claim_ids":[]},{"range":[636400,638132],"primary_class":"unknown","primary_claim_ids":[]}]
        with self.assertRaisesRegex(ValueError,"overlap|duplicate"):m.analyze_coverage_baseline(right)
        for interval in ([636404,636420],[636404,636440],[636500,636510]):
            bad=json.loads(json.dumps(fixture));bad["segments"][0]["range"]=interval;bad["segments"][0]["primary_class"]="foreign"
            with self.subTest(interval=interval),self.assertRaises(ValueError):m.analyze_coverage_baseline(bad)

    def test_replay_each_identity_layer_mutation_fails(self):
        m=self.implemented(); RUN.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RUN) as temp:
            for case in ("gzip","archive","raw","recovery","summary"):
                p=Path(temp)/case;shutil.copytree(ROOT/"artifacts/rom-cgb-audio-precoverage-v1",p);mp=p/"manifest.json";manifest=json.loads(mp.read_text())
                if case=="gzip":(p/"rom-byte-coverage.json.gz").write_bytes(b"bad")
                elif case=="archive":manifest["coverage"]["archive"]["size"]+=1;mp.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
                elif case=="raw":manifest["coverage"]["raw"]["sha256"]="0"*64;mp.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
                elif case=="recovery":manifest["recovery"]["kind"]="live";mp.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
                else:manifest["coverage"]["raw"]["summary"]["unknown_bytes"]+=1;mp.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
                with self.subTest(case=case),self.assertRaises(ValueError):m.build_payload(ROOT,coverage_baseline_artifact=p.relative_to(ROOT))

    def test_each_opaque_bl_raw_and_both_halfwords_are_bound(self):
        m=self.implemented(); cfg=m.analyze_cfg_from_rom(self.rom); by={i["offset"]:i for i in cfg["instructions"]}
        for off,target,raw in ((636654,636300,"fff74dff"),(636882,636220,"fff7b3fe"),(636976,636300,"fff7acfe")):
            self.assertEqual(by[off]["size"],4);self.assertEqual(by[off]["raw_hex"],raw)
            for delta in (0,2):
                changed=bytearray(self.rom);changed[off+delta]^=1
                with self.assertRaises(ValueError):m.analyze_cfg_from_rom(bytes(changed),check_identity=False)

    def test_coverage_projection_and_unknown_gaps_are_recomputed(self):
        m = self.implemented(); payload, _ = m.build_payload(ROOT)
        self.assertEqual(payload["coverage_projection"], self.contract["coverage_projection"])
        self.assertTrue(payload["coverage_projection_recomputed"])
        self.assertEqual(len(payload["excluded_ranges"]), 7)
        self.assertTrue(all(r["semantic_class"] == "unknown" and not r["promoted"] for r in payload["excluded_ranges"]))

    def test_replay_is_single_snapshot_and_does_not_read_live(self):
        m = self.implemented(); shared = Path("artifacts/rom-cgb-audio-precoverage-v1")
        with mock.patch.object(m, "load_live_coverage", side_effect=AssertionError("live consulted")):
            payload, _ = m.build_payload(ROOT, coverage_baseline_artifact=shared)
        self.assertEqual(payload["coverage_baseline_source"]["artifact"], shared.as_posix())
        self.assertEqual(payload["coverage_snapshot_read_count"], 1)

    def test_candidate_output_rejects_parent_escape_and_symlink(self):
        m = self.implemented(); RUN.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RUN) as temp:
            base = Path(temp)
            for bad in (base / ".." / "escape", ROOT, ROOT.parent, base / "candidate" / ".." / "candidate"):
                with self.subTest(path=bad), self.assertRaises(ValueError):
                    m.write_candidate(ROOT, bad)
            link = base / "link"; link.symlink_to(base, target_is_directory=True)
            with self.assertRaises(ValueError):
                m.write_candidate(ROOT, link / "candidate")

    def test_exporter_open_race_preserves_attacker_replacement(self):
        m=self.implemented();RUN.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RUN) as temp:
            base=Path(temp);out=base/"candidate";real_open=m.os.open;swapped=False
            def racing_open(path,flags,mode=0o777,*,dir_fd=None):
                nonlocal swapped
                if path==out.name and dir_fd is not None and flags & os.O_DIRECTORY and not swapped:
                    swapped=True;os.rename(out.name,"owned-held",src_dir_fd=dir_fd,dst_dir_fd=dir_fd);os.mkdir(out.name,dir_fd=dir_fd);(out/"attacker").write_text("keep");raise OSError("injected replacement")
                return real_open(path,flags,mode,dir_fd=dir_fd)
            with mock.patch.object(m,"build_payload",return_value=({"schema":"fixture"},b"x")),mock.patch.object(m.os,"open",side_effect=racing_open),self.assertRaises(OSError):m.write_candidate(ROOT,out)
            self.assertEqual((out/"attacker").read_text(),"keep");self.assertTrue((base/"owned-held").is_dir())


if __name__ == "__main__":
    unittest.main()
