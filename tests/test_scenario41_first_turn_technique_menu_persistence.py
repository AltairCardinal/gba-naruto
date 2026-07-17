import hashlib
import json
import struct
import unittest
from pathlib import Path

from tools.inspect_mgba_savestate import load_gba_state, png_screen_fingerprint


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "artifacts/runtime-checkpoints/scenario-41-first-turn-technique-menu.ss9"
EVIDENCE = ROOT / "artifacts/runtime-checkpoints/scenario-41-first-turn-technique-menu-evidence.json"
LEDGER = ROOT / "artifacts/runtime-checkpoints/scenario-41-checkpoints.json"
NOTE = ROOT / "notes/scenario-41-movedone-runtime-20260717.md"
EXPECTED_CHECKPOINT_SHA256 = "039030d6b754f66a07582356402c9eaf99832badaf0821939af4dbdc8e83c6c1"
EXPECTED_RGB_SHA256 = "17644dae174acd0e26b9b004f3e8a03b9fd9a43b523cb3dff40f978b4f9b6eef"
EXPECTED_UNIT_SHA256 = "e48385264808378faf58c5ddace890789a2d4b99c06018170a33253649ebeb19"
EXPECTED_MOD1 = "4d4f44310100000001000000010000003c44070801000001944202029442020201010e0d00010000040a00040a00000000ff0000"
ZERO_MOD2 = "00" * 52


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Scenario41FirstTurnTechniqueMenuPersistenceTests(unittest.TestCase):
    def test_checkpoint_is_the_independently_approved_p1(self):
        self.assertTrue(CHECKPOINT.is_file(), "canonical technique-menu checkpoint is missing")
        self.assertEqual(sha256_file(CHECKPOINT), EXPECTED_CHECKPOINT_SHA256)

    def test_evidence_binds_provenance_lineage_cycle_and_serial_replays(self):
        self.assertTrue(EVIDENCE.is_file(), "compact technique-menu evidence is missing")
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(evidence["outcome"], "accepted-stable-unsubmitted-technique-menu")
        self.assertEqual(evidence["scope"], "scenario-41-first-turn-technique-menu")
        self.assertEqual(
            evidence["checkpoint"],
            {
                "path": "artifacts/runtime-checkpoints/scenario-41-first-turn-technique-menu.ss9",
                "sha256": EXPECTED_CHECKPOINT_SHA256,
            },
        )
        self.assertEqual(
            evidence["provenance"],
            {
                "base_rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "observer_rom_sha256": "2e0ef35475737789103403cfea454ace1de0ae6b6ed1789d49d7e55d5dc1737f",
                "observer_builder_sha256": "2998ad242e40fb5e7ad1b5a4b7192618aa77920148ae78b769a50c11dd543549",
                "binary_sha256": "20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408",
                "build_manifest_sha256": "9da6779d7c1ac3140e512b233f98abe754c4f11f3fbc8157af147e014661cc4d",
                "fixed_input_runner_sha256": "2f36d0bd8d3daddcbc4f6057b47fc75c9d62f5f2e71cda0992beae3439dc7ef9",
                "fixed_input_lua_sha256": "82fbae13b39d2e7dd4b53e4b79dcf89ccc56f29dcb9ea53466d007b1000b9412",
                "zero_input_runner_sha256": "44a117c53d272cbac8a62beb749d331927e4f3f043c20f3eb78681ceb7591bbc",
                "zero_input_lua_sha256": "1481f10cd8f72c7635326e8d3233c2466b76c7a4b812cefe1220fe43c29f9659",
                "sampler_sha256": "e10a05f7208e4330cbe0dc202a539c9f29506606f697e6658095fc95e75869ec",
                "analyzer_sha256": "db506421b23dcb7076063b81a2443f6e8a9727b2c39b5596a7b0ae49e4bc8184",
                "guard_sha256": "ea34554547c374cd7f9d868792d73c2d7932884f59938a4ffff039eacaa28666",
            },
        )
        self.assertEqual(
            evidence["lineage"],
            {
                "parent": "scenario-41-first-movedone-facing",
                "explicit_inputs": ["A", "Up", "A"],
                "screen": "first-turn-technique-menu",
                "runs": {
                    "facing_confirm": "bcedf5f65522909b84edb3b160c59b90",
                    "defense_up": "13ec9c4842007d4ace77efc17b7c043a",
                    "defense_affirmative": "a619e9ec5d24a0cbee0748e83ae4439b",
                },
            },
        )
        self.assertEqual(
            evidence["cycle"],
            {
                "run_id": "42128f6224e172f1c17bd8b9d5ceca36",
                "input_state_sha256": "f26173ff9d03344cd2f1bb6715158e5764a1853eb8c808df811b852545a9a0f1",
                "output_state_sha256": "faf3b8a28d22bff56a97a8712c7e6450a6f82700380bde388a321fa95182c41f",
                "period_frames": 24,
                "match_frames": [0, 24, 48],
            },
        )
        stability = evidence["zero_input_stability"]
        self.assertEqual(stability["period_frames"], 24)
        self.assertEqual(stability["normalized_rgb8_sha256"], EXPECTED_RGB_SHA256)
        self.assertEqual(
            [replay["run_id"] for replay in stability["replays"]],
            ["e1db6602c1f66570145d730c90064ab4", "9efd0047387a9520d06662c049b3bad6"],
        )
        self.assertEqual(
            [replay["input_state_sha256"] for replay in stability["replays"]],
            [
                "f26173ff9d03344cd2f1bb6715158e5764a1853eb8c808df811b852545a9a0f1",
                EXPECTED_CHECKPOINT_SHA256,
            ],
        )
        self.assertEqual(
            [replay["output_state_sha256"] for replay in stability["replays"]],
            [EXPECTED_CHECKPOINT_SHA256, "ec10ab74ece254ae105f1056eb1bcda9e7302328535d613171253d5165c1889c"],
        )
        for replay in stability["replays"]:
            self.assertEqual(replay["capture_frame"], 24)
            self.assertEqual(replay["inputs"], [])
            self.assertEqual(replay["pre_scripts"], [])
            self.assertTrue(replay["zero_input_verified"])
            self.assertEqual(replay["normalized_rgb8_sha256"], EXPECTED_RGB_SHA256)
            self.assertEqual(replay["guard"]["reason"], "completed")
            self.assertEqual(replay["guard"]["exit_code"], 0)
            self.assertFalse(replay["guard"]["degraded"])

    def test_checkpoint_has_the_reviewed_task_unit_and_movedone_state(self):
        state = load_gba_state(CHECKPOINT)
        task2 = state.read_memory(0x03000AD4, 0x4C)
        saved_lr = struct.unpack_from("<I", task2, 8)[0]
        self.assertEqual(saved_lr - 1, 0x08067D02)
        self.assertEqual(state.read_memory(0x0200A880, 8).hex(), "00" * 8)
        self.assertEqual(state.read_memory(0x02026804, 8).hex(), "0029000000000000")
        self.assertEqual(state.read_memory(0x0201BE28, 4).hex(), "242c0916")
        self.assertEqual(state.read_memory(0x0202680C, 8).hex(), "0100000194420202")
        unit = state.read_memory(0x02024294, 0x1D4)
        self.assertEqual(hashlib.sha256(unit).hexdigest(), EXPECTED_UNIT_SHA256)
        self.assertEqual(unit[:4].hex(), "01010e0d")
        self.assertEqual(unit[0xC0:0xD0].hex(), "10010000040a00040a00000000ff0000")
        self.assertEqual(unit[0xC9], 0)
        self.assertEqual(unit[0xCC:0xD0].hex(), "00ff0000")
        self.assertEqual(state.read_memory(0x0203F0E0, 4), b"\x01\x00\x00\x00")
        self.assertEqual(state.read_memory(0x0203F100, 52).hex(), EXPECTED_MOD1)
        self.assertEqual(state.read_memory(0x0203F140, 52).hex(), ZERO_MOD2)
        self.assertEqual(png_screen_fingerprint(CHECKPOINT)["rgb_pixels_sha256"], EXPECTED_RGB_SHA256)

        self.assertTrue(EVIDENCE.is_file(), "compact technique-menu evidence is missing")
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(
            evidence["business_state"],
            {
                "task_resume": "0x08067D02",
                "menu_round_raw_hex": "0000000000000000",
                "scenario": 41,
                "battle_raw_hex": "0029000000000000",
                "map": {"width": 36, "height": 44, "grid_x": 9, "grid_y": 22},
                "current_object_raw_hex": "0100000194420202",
                "slot": 1,
                "record_address": "0x02024294",
                "character_id": 1,
                "affiliation": 0,
                "coordinates": [4, 10],
                "initial_coordinates": [4, 10],
                "facing": 0,
                "action_raw_hex": "00ff0000",
                "complete_unit_sha256": EXPECTED_UNIT_SHA256,
                "movedone_counter": 1,
                "MOD1_raw_hex": EXPECTED_MOD1,
                "MOD2_raw_hex": ZERO_MOD2,
            },
        )

    def test_ledger_accepts_only_the_stable_unsubmitted_boundary(self):
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        records = [r for r in ledger["checkpoints"] if r["name"] == "scenario-41-first-turn-technique-menu"]
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["status"], "accepted")
        self.assertEqual(record["sha256"], EXPECTED_CHECKPOINT_SHA256)
        self.assertEqual(record["parent"], "scenario-41-first-movedone-facing")
        self.assertEqual(record["inputs"], ["A", "Up", "A"])
        self.assertEqual(record["screen"], "first-turn-technique-menu")
        self.assertTrue(record["stable_zero_input"])
        self.assertEqual(record["before_hooks"], ["0x0807443C", "0x08074918"])
        self.assertEqual(record["allowed_evidence"], [])
        self.assertEqual(
            record["zero_input_evidence"],
            ["artifacts/runtime-checkpoints/scenario-41-first-turn-technique-menu-evidence.json"],
        )
        for phrase in (
            "stable unsubmitted technique-menu boundary",
            "does not prove technique submission",
            "fresh MOVEDONE",
            "completed turn",
            "victory",
            "postbattle",
        ):
            self.assertIn(phrase, record["runtime_boundary"])

    def test_note_records_method_result_and_strict_boundary(self):
        note = NOTE.read_text(encoding="utf-8")
        for phrase in (
            EXPECTED_CHECKPOINT_SHA256,
            "scenario-41-first-turn-technique-menu",
            "bcedf5f65522909b84edb3b160c59b90",
            "13ec9c4842007d4ace77efc17b7c043a",
            "a619e9ec5d24a0cbee0748e83ae4439b",
            "42128f6224e172f1c17bd8b9d5ceca36",
            "[0, 24, 48]",
            "e1db6602c1f66570145d730c90064ab4",
            "9efd0047387a9520d06662c049b3bad6",
            "稳定且尚未提交的术菜单边界",
            "不证明术已提交",
            "不证明 fresh MOVEDONE、回合完成、胜利或 postbattle",
        ):
            self.assertIn(phrase, note)


if __name__ == "__main__":
    unittest.main()
