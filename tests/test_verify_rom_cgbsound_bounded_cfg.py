from __future__ import annotations

import ast
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "build/experiments/active/cgbsound-bounded-cfg-20260829"
ROM = ROOT / "rom/base.gba"


def load(name):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        return None


class VerifyCgbsoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exporter = load("tools.export_rom_cgbsound_bounded_cfg")
        cls.verifier = load("tools.verify_rom_cgbsound_bounded_cfg")

    def implemented(self):
        self.assertIsNotNone(self.exporter, "CgbSound exporter is absent")
        self.assertIsNotNone(self.verifier, "CgbSound verifier is absent")
        return self.exporter, self.verifier

    def candidate(self, parent):
        e, _ = self.implemented(); p = parent / "candidate"; e.write_candidate(ROOT, p); return p

    def test_independent_rebuild_and_import_boundary(self):
        e, v = self.implemented(); proof = v.independent_rebuild(ROOT, ROM.read_bytes())
        self.assertTrue(proof["verified"])
        cfg = proof["payload"]["cfg"]
        self.assertEqual((cfg["instruction_count"], cfg["block_count"], cfg["internal_edge_count"], cfg["external_edge_count"]), (501, 100, 148, 3))
        tree = ast.parse((ROOT / "tools/verify_rom_cgbsound_bounded_cfg.py").read_text())
        source = (ROOT / "tools/verify_rom_cgbsound_bounded_cfg.py").read_text()
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)] + [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        self.assertFalse(any("export_rom_cgbsound_bounded_cfg" in str(x) for x in imports))
        self.assertNotIn("import_module", source)
        with mock.patch.object(e, "build_payload", side_effect=AssertionError("exporter consulted")), mock.patch.object(e, "analyze_cfg_from_rom", side_effect=AssertionError("exporter consulted")):
            self.assertTrue(v.independent_rebuild(ROOT, ROM.read_bytes())["verified"])

    def test_candidate_status_payload_binary_and_coherent_forgery(self):
        _, v = self.implemented(); RUN.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RUN) as temp:
            c = self.candidate(Path(temp))
            with self.assertRaises(ValueError): v.verify_artifact(ROOT, c)
            self.assertTrue(v.verify_artifact(ROOT, c, allow_candidate=True)["verified"])
            for name in ("rom-cgbsound-bounded-cfg.bin", "rom-cgbsound-bounded-cfg.json"):
                p = Path(temp) / (name + "-bad"); shutil.copytree(c, p)
                target = p / name
                if target.suffix == ".bin": target.write_bytes(bytes([target.read_bytes()[0] ^ 1]) + target.read_bytes()[1:])
                else:
                    obj = json.loads(target.read_text()); obj["schema"] = "forged"; target.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
                manifest = json.loads((p / "manifest.json").read_text()); raw = target.read_bytes(); manifest["files"][name] = {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}; (p / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                with self.assertRaises(ValueError): v.verify_artifact(ROOT, p, allow_candidate=True)

    def test_status_laundering_extra_manifest_and_fake_receipt_fail(self):
        _, v = self.implemented(); RUN.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RUN) as temp:
            source = self.candidate(Path(temp))
            for kind in ("status", "extra", "receipt"):
                p = Path(temp) / kind; shutil.copytree(source, p); mp = p / "manifest.json"; m = json.loads(mp.read_text())
                if kind == "status": m["artifact_status"] = "accepted"
                elif kind == "extra": m["overclaim"] = True
                else: m["artifact_status"] = "accepted"; m["acceptance"] = {"kind": "forged"}
                mp.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
                with self.subTest(kind=kind), self.assertRaises(ValueError): v.verify_artifact(ROOT, p, allow_candidate=True)

    def test_acceptance_receipt_source_identity_and_overlap(self):
        _, v = self.implemented(); RUN.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RUN) as temp:
            base = Path(temp); c = self.candidate(base); accepted = base / "accepted"
            report = v.accept_candidate(ROOT, c, accepted)
            self.assertEqual(report["artifact_status"], "accepted")
            manifest = json.loads((accepted / "manifest.json").read_text())
            self.assertEqual(set(manifest), {"schema", "artifact_schema", "artifact_status", "contract_sha256", "files", "acceptance", "verifier", "verification"})
            self.assertEqual(manifest["acceptance"]["source_candidate_artifact"], str(c.relative_to(ROOT)))
            self.assertEqual(set(manifest["acceptance"]), {"kind", "source_candidate_artifact", "source_candidate_identity", "output_artifact"})
            self.assertEqual(set(manifest["acceptance"]["source_candidate_identity"]), {"artifact_status", "manifest_sha256", "payload_sha256", "bundle_sha256"})
            self.assertEqual(manifest["verification"]["status"], "verified")
            for bad in (c, c / "accepted", base / "x" / ".." / "accepted-2"):
                with self.subTest(path=bad), self.assertRaises(ValueError): v.accept_candidate(ROOT, c, bad)
            for path in (("acceptance","source_candidate_artifact"),("acceptance","output_artifact"),("acceptance","source_candidate_identity","payload_sha256"),("verifier","sha256"),("verification","schema"),("verification","bundle_sha256")):
                forged=base/("forged-"+"-".join(path));shutil.copytree(accepted,forged);mp=forged/"manifest.json";obj=json.loads(mp.read_text());cursor=obj
                for key in path[:-1]:cursor=cursor[key]
                cursor[path[-1]]="forged";mp.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n")
                with self.subTest(path=path),self.assertRaises(ValueError):v.verify_artifact(ROOT,forged)

    def test_member_symlink_and_candidate_snapshot_swap_fail(self):
        _, v = self.implemented(); RUN.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RUN) as temp:
            base = Path(temp); c = self.candidate(base); forged = base / "symlink"; shutil.copytree(c, forged)
            member = forged / "rom-cgbsound-bounded-cfg.bin"; real = base / "real.bin"; member.rename(real); member.symlink_to(real)
            with self.assertRaises(ValueError): v.verify_artifact(ROOT, forged, allow_candidate=True)
            for name in ("manifest.json", "rom-cgbsound-bounded-cfg.json"):
                forged2 = base / (name + "-link"); shutil.copytree(c, forged2); member = forged2 / name; real2 = base / (name + "-real"); member.rename(real2); member.symlink_to(real2)
                with self.assertRaises(ValueError): v.verify_artifact(ROOT, forged2, allow_candidate=True)
            with mock.patch.object(v, "_artifact_files", wraps=v._artifact_files) as snap:
                v.accept_candidate(ROOT, c, base / "accepted")
                self.assertEqual(snap.call_count, 3)  # verify candidate, identity compare, verify accepted

    def test_rom_is_single_read_and_replay_never_reads_live(self):
        _, v = self.implemented(); RUN.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RUN) as temp:
            c = self.candidate(Path(temp))
            with mock.patch.object(v, "read_rom_snapshot", wraps=v.read_rom_snapshot) as read:
                v.verify_artifact(ROOT, c, allow_candidate=True)
                self.assertEqual(read.call_count, 1)
        with mock.patch.object(v, "load_live_coverage", side_effect=AssertionError("live consulted")):
            self.assertTrue(v.independent_rebuild(ROOT, ROM.read_bytes(), coverage_baseline_artifact=Path("artifacts/rom-cgb-audio-precoverage-v1"))["verified"])

    def test_output_parent_swap_and_failed_final_verify_leave_no_artifact(self):
        _, v = self.implemented(); RUN.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RUN) as temp:
            base = Path(temp); c = self.candidate(base); output = base / "failed"
            first=v.verify_artifact(ROOT,c,allow_candidate=True)
            with mock.patch.object(v, "verify_artifact", side_effect=[first, ValueError("final")]):
                with self.assertRaises(ValueError): v.accept_candidate(ROOT, c, output)
            self.assertFalse(output.exists())

    def test_parent_identity_swap_and_staging_failure_are_clean(self):
        _,v=self.implemented();RUN.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RUN) as temp:
            base=Path(temp);c=self.candidate(base);parent=base/"parent";parent.mkdir();real=v._validate_output
            def swapped(root,out):
                answer=real(root,out);parent.rename(base/"old-parent");parent.mkdir();return answer
            with mock.patch.object(v,"_validate_output",side_effect=swapped),self.assertRaises(ValueError):v.accept_candidate(ROOT,c,parent/"accepted")
            self.assertFalse((parent/"accepted").exists())
            parent.rmdir();(base/"old-parent").rename(parent);out=parent/"write-fail"
            with mock.patch.object(v,"_write_file_at",side_effect=OSError("write injected")),self.assertRaises(OSError):v.accept_candidate(ROOT,c,out)
            self.assertFalse(out.exists());self.assertFalse(any(p.name.startswith(".write-fail.") for p in parent.iterdir()))

    def test_cli_accept_is_mutually_exclusive_and_canonical(self):
        _, v = self.implemented()
        parser = v.build_parser()
        with self.assertRaises(SystemExit): parser.parse_args(["candidate", "--allow-candidate", "--accept-to", "accepted"])

    def test_staging_open_race_preserves_attacker_replacement(self):
        _,v=self.implemented();RUN.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RUN) as temp:
            base=Path(temp);c=self.candidate(base);out=base/"accepted";real_open=v.os.open;swapped=False
            def racing_open(path,flags,mode=0o777,*,dir_fd=None):
                nonlocal swapped
                if isinstance(path,str) and path.startswith(".accepted.") and dir_fd is not None and flags & os.O_DIRECTORY and not swapped:
                    swapped=True;os.rename(path,"owned-held",src_dir_fd=dir_fd,dst_dir_fd=dir_fd);os.mkdir(path,dir_fd=dir_fd);(base/path/"attacker").write_text("keep");raise OSError("staging replacement")
                return real_open(path,flags,mode,dir_fd=dir_fd)
            with mock.patch.object(v.os,"open",side_effect=racing_open),self.assertRaises(OSError):v.accept_candidate(ROOT,c,out)
            replacements=[p for p in base.iterdir() if p.name.startswith(".accepted.")]
            self.assertEqual(len(replacements),1);self.assertEqual((replacements[0]/"attacker").read_text(),"keep");self.assertTrue((base/"owned-held").is_dir())

    def test_published_stat_race_preserves_attacker_replacement(self):
        _,v=self.implemented();RUN.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RUN) as temp:
            base=Path(temp);c=self.candidate(base);out=base/"accepted";real_replace=v.os.replace;swapped=False
            def racing_replace(src,dst,*args,src_dir_fd=None,dst_dir_fd=None,**kwargs):
                nonlocal swapped
                result=real_replace(src,dst,*args,src_dir_fd=src_dir_fd,dst_dir_fd=dst_dir_fd,**kwargs)
                if dst==out.name and dst_dir_fd is not None and not swapped:
                    swapped=True;os.rename(dst,"published-owned",src_dir_fd=dst_dir_fd,dst_dir_fd=dst_dir_fd);os.mkdir(dst,dir_fd=dst_dir_fd);(out/"attacker").write_text("keep")
                return result
            with mock.patch.object(v.os,"replace",side_effect=racing_replace),self.assertRaises(ValueError):v.accept_candidate(ROOT,c,out)
            self.assertEqual((out/"attacker").read_text(),"keep");self.assertTrue((base/"published-owned").is_dir())

    def test_artifact_member_set_swap_during_snapshot_fails(self):
        _,v=self.implemented();RUN.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RUN) as temp:
            base=Path(temp);c=self.candidate(base);real=v._read_member;changed=False
            def mutate(fd,name):
                nonlocal changed
                raw=real(fd,name)
                if not changed:changed=True;extra=os.open("attacker",os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644,dir_fd=fd);os.close(extra)
                return raw
            with mock.patch.object(v,"_read_member",side_effect=mutate),self.assertRaises(ValueError):v.verify_artifact(ROOT,c,allow_candidate=True)

    def test_verifier_coverage_rejects_right_extending_overlap(self):
        _,v=self.implemented();summary=dict(json.loads((ROOT/"build/experiments/active/cgbsound-contract/codex-r1-20260829/CONTRACT.json").read_text())["coverage_baseline"]["summary"])
        coverage={"schema":"rom-byte-coverage-v1","summary":summary,"segments":[{"range":[634304,634384],"primary_class":"m4a_initializer_chain_consumed_literal_bytes","primary_claim_ids":["psg-initializer-literals-09adc0"]},{"range":[636220,636500],"primary_class":"unknown","primary_claim_ids":[]},{"range":[636400,638132],"primary_class":"unknown","primary_claim_ids":[]}]}
        with self.assertRaisesRegex(ValueError,"overlap|duplicate"):v._analyze_coverage(coverage)

    def test_payload_vectors_are_recomputed_and_partition_is_coherent(self):
        _, v = self.implemented(); payload = v.independent_rebuild(ROOT, ROM.read_bytes())["payload"]; cfg = payload["cfg"]
        canonical = lambda x: json.dumps(x, separators=(",", ":"), sort_keys=False).encode()
        semantic = [[i["offset"], i["size"], i["mnemonic"], i["op_str"]] for i in cfg["instructions"]]
        blocks = [b["range"] for b in cfg["blocks"]]
        rank = {"branch": 0, "opaque_call": 1, "fallthrough": 2}
        edges = [[e["source_instruction_offset"], e["target_offset"], e["kind"]] for e in sorted(cfg["block_edges"], key=lambda e:(e["source_instruction_offset"], rank[e["kind"]]))]
        self.assertEqual(hashlib.sha256(canonical(semantic)).hexdigest(), cfg["semantic_instruction_vector_sha256"])
        self.assertEqual(hashlib.sha256(canonical(blocks)).hexdigest(), cfg["block_range_vector_sha256"])
        self.assertEqual(hashlib.sha256(canonical(edges)).hexdigest(), cfg["edge_vector_sha256"])
        self.assertEqual(sum(b["instruction_count"] for b in cfg["blocks"]), 501)
        starts={i["offset"] for i in cfg["instructions"]};covered=[]
        for block in cfg["blocks"]:
            inside=[i for i in cfg["instructions"] if block["range"][0]<=i["offset"]<block["range"][1]];self.assertEqual(block["instruction_count"],len(inside));covered += [i["offset"] for i in inside]
            terminal=inside[-1]["offset"];self.assertEqual(block["successors"],[e for e in cfg["block_edges"] if e["source_instruction_offset"]==terminal])
        self.assertEqual(set(covered),starts);self.assertEqual(len(covered),len(starts))

    def test_scope_and_noncanonical_both_json_fail(self):
        _, v = self.implemented(); RUN.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RUN) as temp:
            c = self.candidate(Path(temp))
            for name in ("manifest.json", "rom-cgbsound-bounded-cfg.json"):
                p = Path(temp) / (name + "-compact"); shutil.copytree(c, p); f=p/name; f.write_text(json.dumps(json.loads(f.read_text()), separators=(",", ":")))
                if name != "manifest.json":
                    m=json.loads((p/"manifest.json").read_text()); raw=f.read_bytes(); m["files"][name]={"sha256":hashlib.sha256(raw).hexdigest(),"size":len(raw)}; (p/"manifest.json").write_text(json.dumps(m,indent=2,sort_keys=True)+"\n")
                with self.assertRaisesRegex(ValueError, "canonical"): v.verify_artifact(ROOT,p,allow_candidate=True)


if __name__ == "__main__":
    unittest.main()
