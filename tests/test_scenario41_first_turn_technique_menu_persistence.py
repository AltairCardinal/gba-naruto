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

    def test_state_chain_is_contiguous_and_diagnostics_stay_off_chain(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertIn("state_chain", evidence, "reviewed state_chain is missing")
        chain = evidence["state_chain"]
        self.assertEqual(
            chain,
            [
                {
                    "run_id": "bcedf5f65522909b84edb3b160c59b90",
                    "input_state_sha256": "1bc95c63cb11d469e4b2e80e8bae5a937f04ad40e18d7a15706fc261cb9ffb94",
                    "output_state_sha256": "54cf5ecacd9cd89dd679b2b8926e6b6de2f27080da28331aae06c17abe414101",
                    "input_mode": "single-input",
                    "timing": {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8, "capture_frame": 128},
                    "artifacts": {
                        "input_audit_sha256": "42d21fdef06b9c5c154c880f05875d4b4a536e82bf3a6b6143887a34ae437d6a",
                        "guard_summary_sha256": "9d0074e72683e5d1435f299c1d67ddf515d06f613f4c259a7d3f0f04a154a7bb",
                        "done_sha256": "4d1fa5e15fa24a82970f31492e0495e4b64359821ebb4ba3b16db5967fd94bfc",
                    },
                },
                {
                    "run_id": "13ec9c4842007d4ace77efc17b7c043a",
                    "input_state_sha256": "54cf5ecacd9cd89dd679b2b8926e6b6de2f27080da28331aae06c17abe414101",
                    "output_state_sha256": "a6f0806c8d2409f6b84300bd58c7bd76e59bd5ee649dffc345b80ba3b3d7017a",
                    "input_mode": "single-input",
                    "timing": {"key": "Up", "down_frame": 5, "up_frame": 13, "hold_frames": 8, "capture_frame": 128},
                    "artifacts": {
                        "input_audit_sha256": "e507e1ec0bbfadcec95eafa38d19a2aac461fde74cc9ae5265ca185fec84724c",
                        "guard_summary_sha256": "9bbd86bfe01bc1dcb97a6de01e78486e1d437621877329b3cc9843b61728e906",
                        "done_sha256": "428279659f7f0fa1978a696bf41403b27240d47e9374ee91eff21dcc56896996",
                    },
                },
                {
                    "run_id": "10a2275055b9a604b006aed551c952be",
                    "input_state_sha256": "a6f0806c8d2409f6b84300bd58c7bd76e59bd5ee649dffc345b80ba3b3d7017a",
                    "output_state_sha256": "695d14e7828251b6c908f8dc57a5f0e8951fc9cc877c22525479e2a687323fa3",
                    "input_mode": "zero-input",
                    "timing": {"capture_frame": 1, "inputs": [], "pre_scripts": []},
                    "artifacts": {
                        "input_audit_sha256": "c70f431f147e7384f64f0c608a563cdffcce605e417ca310d4dd36b0b08b8f06",
                        "guard_summary_sha256": "6e58c2a1014dc90155b03023dce45a12d39e932ae03eb69348592801a134501c",
                        "done_sha256": "f1b7557cdb8cb2e3a89726d8e2a6390fde0d8178794fc65fda9c72787c472e67",
                    },
                },
                {
                    "run_id": "a619e9ec5d24a0cbee0748e83ae4439b",
                    "input_state_sha256": "695d14e7828251b6c908f8dc57a5f0e8951fc9cc877c22525479e2a687323fa3",
                    "output_state_sha256": "f26173ff9d03344cd2f1bb6715158e5764a1853eb8c808df811b852545a9a0f1",
                    "input_mode": "single-input",
                    "timing": {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8, "capture_frame": 128},
                    "artifacts": {
                        "input_audit_sha256": "d0d3d7d7ed838d32bd7d7cd1dbf674418b88d91eabc67b9afae746703f8ec053",
                        "guard_summary_sha256": "0b9b0aa19075941e57181573d533253bdd716cae18307d161b3e3bf74d12f5ef",
                        "done_sha256": "a354fd96258b6f06af4a26de0da54080214b6ef1de438bc1b2a42a3be4823372",
                    },
                },
                {
                    "run_id": "e1db6602c1f66570145d730c90064ab4",
                    "input_state_sha256": "f26173ff9d03344cd2f1bb6715158e5764a1853eb8c808df811b852545a9a0f1",
                    "output_state_sha256": EXPECTED_CHECKPOINT_SHA256,
                    "input_mode": "zero-input",
                    "timing": {"capture_frame": 24, "inputs": [], "pre_scripts": []},
                    "artifacts": {
                        "input_audit_sha256": "b5437c142667d33350c2a56b0a2a9d807debb86d76c48478ab14dfacae671182",
                        "guard_summary_sha256": "b1baa0bdfd61ec85c92e7abf82ccc5cff540a8aba25ec739ce59130185359acf",
                        "done_sha256": "2f5fcfec9272f7ae31974d5853bb785cfdbbfa82a564c760bfbe54088bff692f",
                    },
                },
            ],
        )
        self.assertEqual(chain[0]["input_state_sha256"], "1bc95c63cb11d469e4b2e80e8bae5a937f04ad40e18d7a15706fc261cb9ffb94")
        self.assertEqual(chain[-1]["output_state_sha256"], EXPECTED_CHECKPOINT_SHA256)
        for current, following in zip(chain, chain[1:]):
            self.assertEqual(current["output_state_sha256"], following["input_state_sha256"])

        self.assertEqual(
            evidence["corroboration_branches"],
            {
                "defense_cycle": {
                    "role": "diagnostic-cycle-not-canonical",
                    "run_id": "ca840f8e56bfd674a8695614fc490ca3",
                    "input_state_sha256": "a6f0806c8d2409f6b84300bd58c7bd76e59bd5ee649dffc345b80ba3b3d7017a",
                    "output_state_sha256": "5565acfb5116bbd8025d8db24b12c44868ed08d3c9a431aa98f5b28865c452c9",
                    "capture_frame": 600,
                    "period_frames": 1,
                    "match_frames": [0, 1, 2],
                    "artifacts": {
                        "input_audit_sha256": "f54806c0538a5fcdc403a6cc4a90538a334b61607d7579b1abe8632afae4e8f4",
                        "guard_summary_sha256": "77ac413caa653192974bf4f1e0498ed72108dfe95b46b460cff3388c002f7981",
                        "done_sha256": "a3945b66a56a063b6d274921dc68a5b07c9fec711f95f8b166f1fe88307b950a",
                        "cycle_analysis_sha256": "a03fe11bbf5cba40d8e367f6c465cd91d320a8812f5e306441a2181155aef0ad",
                    },
                },
                "defense_p2": {
                    "role": "serial-zero-input-corroboration-not-canonical",
                    "run_id": "95b2134e4abe6862a0227e7e68cbcc12",
                    "input_state_sha256": "695d14e7828251b6c908f8dc57a5f0e8951fc9cc877c22525479e2a687323fa3",
                    "output_state_sha256": "dae660b37a848ac3fbf051cb4fe15b42fc4a1d51ed7847a583d91b005c8f082c",
                    "capture_frame": 1,
                    "inputs": [],
                    "pre_scripts": [],
                    "artifacts": {
                        "input_audit_sha256": "da28a5a3103a68cae32a11e17213cd8f22ff7484602387de021e9f49ad9e43b5",
                        "guard_summary_sha256": "5e58a447be93012f3a7084c0a0a25bf2678dd05329f4eeb2118c83b950393bf1",
                        "done_sha256": "cbc813a345e9eced00756c5b91b865d70af6a0ea1c12e8f40c707cc1c4ac4d3f",
                    },
                },
                "technique_cycle": {
                    "role": "diagnostic-cycle-not-canonical",
                    "run_id": "42128f6224e172f1c17bd8b9d5ceca36",
                    "input_state_sha256": "f26173ff9d03344cd2f1bb6715158e5764a1853eb8c808df811b852545a9a0f1",
                    "output_state_sha256": "faf3b8a28d22bff56a97a8712c7e6450a6f82700380bde388a321fa95182c41f",
                    "capture_frame": 600,
                    "period_frames": 24,
                    "match_frames": [0, 24, 48],
                    "artifacts": {
                        "input_audit_sha256": "03497ba8dc957904e886a7b4dd8d4ef4a11b72b0bc92d5d477eb25945fe62c82",
                        "guard_summary_sha256": "3bfd07f5626529a62ad1f2a4903f660c55667af18bfc2edbb4a3261e81b77e3b",
                        "done_sha256": "9fc796952d171673f7a821792eb339be3a56abdb1bc86be6cbf3523a33858e0c",
                        "cycle_analysis_sha256": "9364a1e391b27b522f094c8d6a30b97b1e79000623901a37bd788b3322902c9b",
                    },
                },
                "technique_p2": {
                    "role": "serial-zero-input-corroboration-not-canonical",
                    "run_id": "9efd0047387a9520d06662c049b3bad6",
                    "input_state_sha256": EXPECTED_CHECKPOINT_SHA256,
                    "output_state_sha256": "ec10ab74ece254ae105f1056eb1bcda9e7302328535d613171253d5165c1889c",
                    "capture_frame": 24,
                    "inputs": [],
                    "pre_scripts": [],
                    "artifacts": {
                        "input_audit_sha256": "dcbdfeaa4f475eeabc87c669437dd66bda168f3eec348ee0fe4bc5eb2aa627a9",
                        "guard_summary_sha256": "40b85e6600e5109698e6d3b1f6174c2b45b15c5227d25b00173bb929e4e160ef",
                        "done_sha256": "881ef164f7e8129abd8ffc52484cfdc08577e902e042cbaffc9fcab135d330db",
                    },
                },
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
            "10a2275055b9a604b006aed551c952be",
            "a6f0806c8d2409f6b84300bd58c7bd76e59bd5ee649dffc345b80ba3b3d7017a",
            "695d14e7828251b6c908f8dc57a5f0e8951fc9cc877c22525479e2a687323fa3",
            "capture1 零输入桥",
            "稳定且尚未提交的术菜单边界",
            "不证明术已提交",
            "不证明 fresh MOVEDONE、回合完成、胜利或 postbattle",
        ):
            self.assertIn(phrase, note)


if __name__ == "__main__":
    unittest.main()
