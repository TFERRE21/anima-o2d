"""Regression for Brazilian narrator, synchronized spoken scenes and no bumper."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.app.narrated_draw_2d import scene_seconds, narrator_segments
from backend.app.worlds import build_episode_plan


class CalmPtBRStoryTests(unittest.TestCase):
    def test_spoken_scene_durations_are_not_artificially_reallocated(self):
        timeline=[
            {"scene":0,"start":0,"end":12},
            {"scene":1,"start":12,"end":32},
            {"scene":2,"start":32,"end":47},
        ]
        durations=scene_seconds([0,1,2],timeline,50)
        self.assertEqual([round(v,2) for v in durations],[12,20,18])

    def test_only_last_scene_receives_any_final_quiet_hold(self):
        timeline=[{"scene":7,"start":0,"end":3},
                  {"scene":8,"start":3,"end":5}]
        self.assertEqual(scene_seconds([7,8],timeline,9),[3,6])

    def test_dialogues_are_ptbr_and_preserve_exact_words(self):
        plan=build_episode_plan(0)
        for fmt in ("16:9","9:16"):
            segments=narrator_segments(plan,fmt,plan["story"])
            self.assertTrue(segments)
            self.assertTrue(all(entry["speaker"]=="Narrador" for entry in segments))
            self.assertTrue(all(entry["text"].strip() for entry in segments))

    def test_narrator_uses_only_brazilian_portuguese_voice(self):
        from backend.app.renderer import _edge_tts_save
        fake=mock.Mock()
        fake.save=mock.AsyncMock()
        mocked_module=mock.Mock()
        mocked_module.Communicate.return_value=fake
        with mock.patch.dict("sys.modules",{"edge_tts":mocked_module}):
            with mock.patch.dict("os.environ",{"ANIMA_NARRATOR_RATE":"-18%"},clear=False):
                asyncio.run(_edge_tts_save("Olá, crianças! Vamos conhecer o planeta.",
                                           Path("/virtual/voice.mp3"),"Narrador"))
        opts=mocked_module.Communicate.call_args.kwargs
        self.assertTrue(opts["voice"].startswith("pt-BR-"))
        self.assertNotIn("Multilingual",opts["voice"])
        self.assertLessEqual(int(opts["rate"].rstrip("%")),-8)

    def test_no_intro_or_outro_in_main_render_flow(self):
        from pathlib import Path
        source=Path("backend/app/main.py").read_text(encoding="utf-8")
        self.assertNotIn("metadata.update(finish_episode(",source)
        self.assertIn('"channel_intro":False',source)
        self.assertIn('"channel_outro":False',source)

    def test_illustration_uses_spoken_narration(self):
        from backend.app.character_reference_ai import stage_direction
        scene={"visual_action":"encontrar uma ponte",
               "narration_context":"Luna encontrou um mapa perto da ponte de cristal"}
        text=stage_direction(scene,3,"Aurora-7","florestas","town","Lumins")
        self.assertIn("Luna encontrou um mapa",text)
        self.assertIn("exact physical action",text)


if __name__=="__main__":
    unittest.main()
