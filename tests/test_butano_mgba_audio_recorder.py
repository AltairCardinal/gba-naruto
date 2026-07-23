import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "butano" / "mgba_audio_recorder.c"


class MgbaAudioRecorderTest(unittest.TestCase):
    def test_recorder_uses_mgba_av_stream_and_writes_stereo_pcm(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn("struct mAVStream stream", text)
        self.assertIn("postAudioFrame", text)
        self.assertIn("audioRateChanged", text)
        self.assertIn("core->setAVStream(core, &recorder.stream)", text)
        self.assertIn("core->runFrame(core)", text)
        self.assertIn('fwrite("RIFF"', text)
        self.assertIn("sample_count", text)
        self.assertIn("MGBA_AUDIO_A_FRAME", text)
        self.assertIn("core->setKeys(core, 1)", text)
        self.assertIn("core->busRead32(core, 0x030076B0)", text)
        self.assertIn("player_slot=%d", text)


if __name__ == "__main__":
    unittest.main()
