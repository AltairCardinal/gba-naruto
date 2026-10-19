from pathlib import Path
import json
import shutil
import tempfile
import unittest
import zlib

from PIL import Image
from tests.test_inspect_mgba_savestate import _chunk_payload, _replace_chunk
from tools.verify_menu_portrait_pointer_ab import verify_source

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "notes/evidence/rom-menu-gfx-pointer-ab-20261001-v1/source"


class MenuPointerRuntimeTests(unittest.TestCase):
    def clone(self, destination):
        shutil.copytree(SOURCE, destination)

    def edit_json(self, path, change):
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")

    def test_replays_real_shared_lock_capture(self):
        result = verify_source(ROOT, SOURCE)
        self.assertTrue(result["verified"])
        self.assertEqual(result["changed_pixel_count"], 1)
        self.assertEqual(result["memory_differences"], {'IO': [], 'PRAM': [], 'VRAM': [0x11440], 'OAM': [], 'IWRAM': [], 'EWRAM': [0x3CC0]})
        self.assertEqual(result["record_ids_covered"], ["1"])
        self.assertEqual(result["field_ids_covered"], ["gfx_ptr_0"])
        self.assertEqual(result["cells_covered"], [{"record_id": "1", "field_id": "gfx_ptr_0"}])
        self.assertEqual(result["cells_total"], 630)
        self.assertEqual(result["zero_input_sample_count"], 3)
        self.assertTrue(result["natural_show_portrait_load"])
        self.assertFalse(result["exhaustive"])

    def test_rejects_wrong_shared_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory).resolve() / "source"
            self.clone(source)
            path = source / "runtime/zero-baseline-1/launch.json"
            def change(value):
                command = value["guard_command"]
                command[command.index("--lock-file") + 1] = str(ROOT / "build/resource-guard/heavy.lock")
            self.edit_json(path, change)
            with self.assertRaisesRegex(ValueError, "shared heavy lock"):
                verify_source(ROOT, source)

    def test_rejects_resigned_extra_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory).resolve() / "source"
            self.clone(source)
            path = source / "runtime/input-candidate/audit.json"
            self.edit_json(path, lambda v: v["inputs"].append({"key": "B"}))
            shutil.copy2(path, source / "runtime/input-candidate/sentinel.json")
            with self.assertRaisesRegex(ValueError, "input protocol"):
                verify_source(ROOT, source)

    def test_rejects_wrong_record_relabel(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory).resolve() / "source"
            self.clone(source)
            self.edit_json(source / "build-manifest.json", lambda v: v["edit"].update({"record_id": "5"}))
            with self.assertRaisesRegex(ValueError, "build manifest"):
                verify_source(ROOT, source)

    def test_rejects_forged_marker_or_library(self):
        for name, change in [
            ("runtime/input-candidate/guard.json.done.json", lambda v: v.update({"run_id": "forged"})),
            ("preflight-result.json", lambda v: v.update({"library_sha256": "0" * 64})),
        ]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                source = Path(directory).resolve() / "source"
                self.clone(source)
                self.edit_json(source / name, change)
                with self.assertRaises(ValueError):
                    verify_source(ROOT, source)

    def test_rejects_resigned_png_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory).resolve() / "source"
            self.clone(source)
            path = source / "runtime/input-candidate/frame80.png"
            with Image.open(path) as original:
                changed = original.convert("RGB")
            changed.putpixel((0, 0), (255, 0, 0))
            changed.save(path)
            with self.assertRaisesRegex(ValueError, "renderer|pixels"):
                verify_source(ROOT, source)

    def test_rejects_zero_input_memory_change(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory).resolve() / "source"
            self.clone(source)
            path = source / "runtime/zero-candidate/frame80.ss9"
            container = path.read_bytes()
            state = bytearray(zlib.decompress(_chunk_payload(container, b"gbAs")))
            state[0x21010] ^= 1
            path.write_bytes(_replace_chunk(container, b"gbAs", zlib.compress(state)))
            with self.assertRaisesRegex(ValueError, "zero input"):
                verify_source(ROOT, source)

    def test_rejects_other_memory_domain_change(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory).resolve() / "source"
            self.clone(source)
            path = source / "runtime/input-candidate/frame80.ss9"
            container = path.read_bytes()
            state = bytearray(zlib.decompress(_chunk_payload(container, b"gbAs")))
            state[0x21010] ^= 1
            path.write_bytes(_replace_chunk(container, b"gbAs", zlib.compress(state)))
            with self.assertRaisesRegex(ValueError, "memory domain"):
                verify_source(ROOT, source)

    def test_rejects_relabelled_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory).resolve() / "source"
            self.clone(source)
            self.edit_json(source / "plan.json", lambda v: v["cases"][0].update({"variant": "candidate"}))
            with self.assertRaisesRegex(ValueError, "plan"):
                verify_source(ROOT, source)

    def test_rejects_extra_guard_option(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory).resolve() / "source"
            self.clone(source)
            def change(value):
                cmd = value["guard_command"]
                cmd.insert(cmd.index("--"), "--allow-degraded")
            self.edit_json(source / "runtime/input-candidate/launch.json", change)
            with self.assertRaisesRegex(ValueError, "guard command"):
                verify_source(ROOT, source)

    def test_rejects_reused_run_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory).resolve() / "source"
            self.clone(source)
            for member in ["launch.json", "audit.json", "sentinel.json", "guard.json.done.json"]:
                self.edit_json(source / "runtime/zero-baseline-2" / member,
                               lambda v: v.update({"run_id": "menu-gfx-ptr-20261001-zero-baseline-1"}))
            with self.assertRaisesRegex(ValueError, "run identity"):
                verify_source(ROOT, source)

    def test_rejects_input_version_in_new_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory).resolve() / "source"
            self.clone(source)
            path = source / "runtime/input-candidate/frame80.ss9"
            container = path.read_bytes()
            state = bytearray(zlib.decompress(_chunk_payload(container, b"gbAs")))
            state[:4] = bytes.fromhex("07000001")
            path.write_bytes(_replace_chunk(container, b"gbAs", zlib.compress(state)))
            with self.assertRaisesRegex(ValueError, "snapshot version"):
                verify_source(ROOT, source)

    def test_rejects_symlink_or_extra_raw_file(self):
        for symbolic in [False, True]:
            with self.subTest(symbolic=symbolic), tempfile.TemporaryDirectory() as directory:
                source = Path(directory).resolve() / "source"
                self.clone(source)
                if symbolic:
                    path = source / "runtime/input-candidate/frame80.png"
                    path.unlink()
                    path.symlink_to(SOURCE / "runtime/input-candidate/frame80.png")
                else:
                    (source / "extra.bin").write_bytes(b"extra")
                with self.assertRaises(ValueError):
                    verify_source(ROOT, source)


if __name__ == "__main__":
    unittest.main()
