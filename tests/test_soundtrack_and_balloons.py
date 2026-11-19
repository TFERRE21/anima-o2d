"""Regression for per-episode soundtrack, readable speech and audible TTS."""
from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

from PIL import Image

from backend.app.children_music import soundtrack_identity, create_music
from backend.app.comic_panels import comic_page
from backend.app.dialogue_timeline import draw_balloon, speaker_coordinates
from backend.app.narrated_draw_2d import narrator_segments


class SoundtrackAndBalloonTests(unittest.TestCase):
    def test_different_planets_generate_different_musical_identities(self):
        one=soundtrack_identity("Aurora-7 | A Missão de Aurora-7 | cristais")
        two=soundtrack_identity("Flora-Lume | A Missão de Flora-Lume | sementes")
        self.assertNotEqual(one["theme_id"],two["theme_id"])
        self.assertGreaterEqual(one["tempo_bpm"],88)
        self.assertLessEqual(two["tempo_bpm"],108)

    def test_original_audio_exists_and_changes_between_episodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=create_music(Path(tmp)/"one.wav",1.2,"Aurora-7 | episódio um")
            second=create_music(Path(tmp)/"two.wav",1.2,"Flora-Lume | episódio dois")
            with wave.open(str(first),"rb") as a, wave.open(str(second),"rb") as b:
                self.assertEqual(a.getnchannels(),1)
                self.assertGreater(a.getnframes(),1000)
                self.assertNotEqual(a.readframes(1000),b.readframes(1000))

    def test_balloon_over_final_portrait_scene_remains_legible(self):
        art=Image.new("RGB",(1280,720),(65,130,190))
        finished,_=comic_page([art],(720,1280),"Aurora-7",True,"color",0)
        anchor,center=speaker_coordinates(9,"luna",finished.size)
        talking=draw_balloon(finished,"Vamos ajudar nossos amigos!",
                             "luna",anchor,center)
        self.assertEqual(talking.size,(720,1280))
        self.assertNotEqual(talking.tobytes(),finished.tobytes())

    def test_shorts_real_dialogue_gets_bubbles_but_narration_does_not(self):
        from backend.app.worlds import build_episode_plan
        plan=build_episode_plan(0)
        result=narrator_segments(plan,"9:16",plan["story"])
        spoken=[s for s in result if s["dialogue_text"]]
        narrated=[s for s in result if not s["dialogue_text"]]
        self.assertGreaterEqual(len(spoken),4)
        self.assertGreaterEqual(len(narrated),2)
        self.assertTrue(any(x["original_speaker"]=="Luna" for x in spoken))

    def test_narration_guard_rejects_silent_tts(self):
        from backend.app.video_integrity import verify_narration_source
        with mock.patch("backend.app.renderer._probe_duration",return_value=75):
            with mock.patch("backend.app.video_integrity._ffmpeg_bin",
                            return_value="/opt/bundled/ffmpeg"):
                with mock.patch("backend.app.video_integrity.subprocess.run",
                    return_value=mock.Mock(returncode=0,stderr="max_volume: -inf dB")):
                    with self.assertRaisesRegex(RuntimeError,"inaudível"):
                        verify_narration_source(Path("/virtual/tts.wav"))


if __name__=="__main__":
    unittest.main()
