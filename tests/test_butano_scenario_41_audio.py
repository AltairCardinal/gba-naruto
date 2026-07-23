import hashlib
import json
import struct
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from tools.butano.generate_scenario_41_sfx_assets import generate_sfx_assets
from tools.butano.verify_scenario_41_audio_states import verify_audio_state
from tools.inspect_mgba_savestate import GBA_STATE_SIZE, GbaState


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "butano" / "generate_scenario_41_audio_assets.py"


class Scenario41AudioAssetsTest(unittest.TestCase):
    def test_audio_state_verifier_requires_master_dma_and_timer(self):
        data = bytearray(GBA_STATE_SIZE)
        struct.pack_into("<H", data, 0x400 + 0x84, 0x80)
        struct.pack_into("<H", data, 0x400 + 0xC6, 0xB640)
        struct.pack_into("<H", data, 0x400 + 0xD2, 0xB640)
        struct.pack_into("<H", data, 0x400 + 0x102, 0x80)
        report = verify_audio_state(GbaState(bytes(data)))
        self.assertTrue(report["active"])

        struct.pack_into("<H", data, 0x400 + 0x84, 0)
        self.assertFalse(verify_audio_state(GbaState(bytes(data)))["active"])

    def test_generator_converts_music_to_maxmod_safe_mono_22050_pcm(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "sound_008.wav"
            output = temp / "sound_008.s3m"
            manifest = temp / "manifest.json"
            frames = bytes((0, 255, 32, 224, 64, 192, 96, 160))
            with wave.open(str(source), "wb") as stream:
                stream.setnchannels(2)
                stream.setsampwidth(1)
                stream.setframerate(15768)
                stream.writeframes(frames)

            subprocess.run(
                [
                    "python3",
                    str(GENERATOR),
                    "--input",
                    str(source),
                    "--output",
                    str(output),
                    "--manifest",
                    str(manifest),
                    "--segment-seconds",
                    "1",
                ],
                cwd=ROOT,
                check=True,
            )

            data = output.read_bytes()
            self.assertEqual(data[44:48], b"SCRM")
            self.assertEqual(struct.unpack_from("<H", data, 34)[0], 1)
            self.assertEqual(struct.unpack_from("<H", data, 36)[0], 1)
            instrument_pointers = struct.unpack_from("<H", data, 98)
            left_header = instrument_pointers[0] * 16
            self.assertEqual(struct.unpack_from("<I", data, left_header + 32)[0], 22050)

            def sample_bytes(header: int) -> bytes:
                pointer = data[header + 13] << 20
                pointer |= data[header + 15] << 12
                pointer |= data[header + 14] << 4
                length = struct.unpack_from("<I", data, header + 16)[0]
                return data[pointer : pointer + length]

            converted = sample_bytes(left_header)
            self.assertGreater(len(converted), 4)
            self.assertLessEqual(abs(sum(converted) / len(converted) - 128), 1)

            metadata = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(metadata["sound_id"], 8)
            self.assertEqual(metadata["source_sample_rate"], 15768)
            self.assertEqual(metadata["source_channels"], 2)
            self.assertEqual(metadata["sample_rate"], 22050)
            self.assertEqual(metadata["channels"], 1)
            self.assertLessEqual(abs(metadata["dc_offset_after"]), 1)
            self.assertTrue(metadata["loop"])
            self.assertEqual(metadata["pcm_sha256"], hashlib.sha256(frames).hexdigest())

    def test_generated_cue_8_loop_duration_matches_original_pcm(self):
        manifest = json.loads(
            (
                ROOT
                / "artifacts"
                / "scenario-41-audio-reference-v1"
                / "cue-8-manifest.json"
            ).read_text(encoding="utf-8")
        )
        self.assertLessEqual(abs(manifest["module_loop_error_seconds"]), 0.002)

    def test_runtime_verified_music_manifests_name_each_phase(self):
        expected = {
            2: "postbattle_map_bgm",
            5: "prebattle_bgm",
            8: "postbattle_dialogue_bgm",
            14: "battle_bgm",
            15: "combo_animation_bgm",
        }
        for sound_id, semantic in expected.items():
            manifest = json.loads(
                (
                    ROOT
                    / "artifacts"
                    / "scenario-41-audio-reference-v1"
                    / f"cue-{sound_id}-manifest.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["semantic"], semantic)
            self.assertLessEqual(abs(manifest["module_loop_error_seconds"]), 0.004)

    def test_butano_scene_starts_original_inherited_bgm(self):
        scene = (
            ROOT / "butano-sequel" / "game" / "src" / "scenario_41_scene.cpp"
        ).read_text(encoding="utf-8")
        for sound_id in (2, 5, 8, 14, 15):
            self.assertTrue(
                (ROOT / "butano-sequel" / "audio" / f"sound_{sound_id:03d}.s3m").is_file()
            )
        self.assertIn('#include "bn_music_items.h"', scene)
        self.assertIn("play_music_item(KONOHA_MUSIC_ITEM(sound_005))", scene)
        self.assertIn("battle_event::intro_dismissed", scene)
        self.assertIn("play_music_item(KONOHA_MUSIC_ITEM(sound_014))", scene)
        self.assertIn("state.animation_frame == 47", scene)
        self.assertIn("play_music_item(KONOHA_MUSIC_ITEM(sound_015))", scene)
        self.assertIn("state.animation_frame == 64", scene)
        self.assertIn("play_audio_item(bn::sound_items::sound_116)", scene)
        self.assertIn("state.animation_frame == 140", scene)
        self.assertIn("play_audio_item(bn::sound_items::sound_138)", scene)
        self.assertIn("play_audio_item(bn::sound_items::sound_149)", scene)
        self.assertIn("play_audio_item(bn::sound_items::sound_158)", scene)
        self.assertIn("play_audio_item(bn::sound_items::sound_051)", scene)
        self.assertIn("play_audio_item(bn::sound_items::sound_157)", scene)
        self.assertIn("play_audio_item(bn::sound_items::sound_112)", scene)
        self.assertIn("play_audio_item(bn::sound_items::sound_052)", scene)
        self.assertIn("play_music_item(KONOHA_MUSIC_ITEM(sound_008))", scene)
        self.assertIn("play_music_item(KONOHA_MUSIC_ITEM(sound_002))", scene)

    def test_diagnostic_build_can_gate_every_runtime_audio_trigger(self):
        scene = (
            ROOT / "butano-sequel" / "game" / "src" / "scenario_41_scene.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("KONOHA_DIAGNOSTIC_NO_AUDIO", scene)
        self.assertIn("void play_audio_item", scene)
        self.assertEqual(
            scene.count(".play()"),
            3,
            "all music and sound triggers must pass through the diagnostic gate",
        )

    def test_sfx_generator_downmixes_and_resamples_runtime_verified_cues(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "source"
            output = temp / "output"
            source.mkdir()
            with wave.open(str(source / "sound_116.wav"), "wb") as stream:
                stream.setnchannels(2)
                stream.setsampwidth(1)
                stream.setframerate(15768)
                stream.writeframes(bytes((0, 255, 32, 224, 64, 192)))

            manifest = generate_sfx_assets(source, output, (116,))

            with wave.open(str(output / "sound_116.wav"), "rb") as stream:
                self.assertEqual(stream.getnchannels(), 1)
                self.assertEqual(stream.getsampwidth(), 1)
                self.assertEqual(stream.getframerate(), 22050)
                self.assertEqual(stream.readframes(4), bytes((127, 128, 128, 128)))
            self.assertEqual(manifest["sound_ids"], [116])
            self.assertEqual(manifest["entries"][0]["semantic"], "combo_attack_motion")

    def test_sfx_generator_can_render_music_for_wav_bgm_diagnostic(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "source"
            output = temp / "output"
            source.mkdir()
            with wave.open(str(source / "sound_005.wav"), "wb") as stream:
                stream.setnchannels(2)
                stream.setsampwidth(1)
                stream.setframerate(15768)
                stream.writeframes(bytes((0, 255, 32, 224, 64, 192)))

            manifest = generate_sfx_assets(source, output, (5,))

            self.assertEqual(manifest["entries"][0]["semantic"], "prebattle_bgm")
            self.assertTrue((output / "sound_005.wav").is_file())

    def test_diagnostic_build_can_route_music_as_wav_sound_items(self):
        scene = (
            ROOT / "butano-sequel" / "game" / "src" / "scenario_41_scene.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("KONOHA_DIAGNOSTIC_WAV_BGM", scene)
        self.assertIn("play_music_item(KONOHA_MUSIC_ITEM(sound_005))", scene)
        self.assertIn("wav_bgm_handle->stop()", scene)
        self.assertNotIn("play_audio_item(bn::music_items::sound_005)", scene)


if __name__ == "__main__":
    unittest.main()
