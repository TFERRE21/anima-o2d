"""Speech balloons must show actual scripted lines, synchronized by scene."""
import os
import unittest
from unittest import mock

from PIL import Image

from backend.app.dialogue_timeline import (
    balloon_parts, dialogue_beats, draw_balloon, speaker_coordinates,
)
from backend.app.narrated_draw_2d import narrator_segments
from backend.app.illustrated_scene_engine import (
    enabled, provider, selected_model,
)


class RealDialogueTests(unittest.TestCase):
    def test_every_scripted_word_is_retained(self):
        actual="Luna, vamos conhecer o planeta e ouvir o que os moradores querem contar!"
        chunks=balloon_parts(actual,5)
        self.assertEqual(" ".join(chunks),actual)
        self.assertGreater(len(chunks),1)

    def test_narrator_does_not_invent_character_balloons(self):
        plan={"audio_segments_long":[
            {"scene":0,"speaker":"Luna","text":"A nave chegou ao planeta."},
            {"scene":0,"speaker":"Luna","text":"Olá, Tomi! Vamos juntos."},
            {"scene":0,"speaker":"Narrador","text":"O céu ficou azul."},
        ],"dialogues":[{"scene":0,"speaker":"Luna",
                        "text":"Olá, Tomi! Vamos juntos."}]}
        segments=narrator_segments(plan,"16:9","")
        self.assertEqual(segments[0]["original_speaker"],"Narrador")
        self.assertEqual(segments[1]["original_speaker"],"Luna")
        self.assertEqual(segments[1]["dialogue_text"],"Olá, Tomi! Vamos juntos.")
        self.assertEqual(segments[2]["dialogue_text"],"")
        timeline=[
            {"scene":0,"start":0,"end":3},
            {"scene":0,"start":3,"end":6},
            {"scene":0,"start":6,"end":9},
        ]
        beats=dialogue_beats(segments,timeline,[0],"16:9")[0]
        self.assertEqual([(b["speaker"],b["text"]) for b in beats],
                         [(None,""),("luna","Olá, Tomi! Vamos juntos."),(None,"")])

    def test_multiple_speakers_follow_actual_audio(self):
        plan={"audio_segments_short":[
            {"scene":7,"speaker":"Luna","text":"Tomi, olha a pista!"},
            {"scene":7,"speaker":"Tomi","text":"Vamos ouvir os moradores."},
            {"scene":8,"speaker":"Pipo","text":"Au! Eu encontrei outra pista!"}
        ]}
        segments=narrator_segments(plan,"9:16","")
        timeline=[{"scene":7,"start":0,"end":2},{"scene":7,"start":2,"end":4},
                  {"scene":8,"start":4,"end":8}]
        beats=dialogue_beats(segments,timeline,[7,8],"9:16")
        self.assertEqual([item["speaker"] for item in beats[7]],["luna","tomi"])
        self.assertEqual([item["text"] for item in beats[7]],
                         ["Tomi, olha a pista!","Vamos ouvir os moradores."])
        self.assertEqual(beats[8][0]["speaker"],"pipo")

    def test_balloon_is_legible_and_does_not_replace_art(self):
        blank=Image.new("RGB",(1280,720),(110,195,218))
        anchor,center=speaker_coordinates(1,"luna",blank.size)
        modified=draw_balloon(blank,"Vamos conhecer os novos amigos!",
                              "luna",anchor,center)
        self.assertEqual(modified.size,blank.size)
        self.assertNotEqual(modified.tobytes(),blank.tobytes())
        self.assertEqual(blank.getpixel((1279,719)),(110,195,218))

    def test_cloudflare_is_detected_only_with_both_credentials(self):
        with mock.patch.dict(os.environ,{
            "CLOUDFLARE_API_TOKEN":"testing-not-real",
            "CLOUDFLARE_ACCOUNT_ID":"abc123",
            "ANIMA_SCENE_IMAGE_PROVIDER":"",
            "ANIMA_SCENE_IMAGE_API_KEY":"",
            "ANIMA_SCENE_IMAGE_ENABLED":"0",
        }):
            self.assertTrue(enabled())
            self.assertEqual(provider(),"cloudflare")
            self.assertEqual(selected_model(),"@cf/black-forest-labs/flux-1-schnell")


if __name__=="__main__":
    unittest.main()
