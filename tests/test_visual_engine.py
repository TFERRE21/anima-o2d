"""Regression tests for approved-cast dynamic comics and soundtrack."""
import hashlib
import tempfile
import unittest
import wave
from pathlib import Path

from backend.app.approved_cast_embedded import character_sprite
from backend.app.official_comic_2d import draw_official_scene, has_official_model
from backend.app.children_music import create_music
from backend.app.story_comic_director import emotions


class StoryComicV5Tests(unittest.TestCase):
    def test_fixed_characters_available_without_manual_upload(self):
        self.assertTrue(has_official_model())
        for name in ("luna", "tomi", "pipo"):
            image = character_sprite(name)
            self.assertEqual(image.mode, "RGBA")
            self.assertGreater(image.getchannel("A").getbbox()[2], 20)

    def test_no_repeated_scenes_and_color(self):
        sample = [
            {"title":"A partida","caption":"A nave decola","visual_action":"A tripulação confere os cintos."},
            {"title":"Novos amigos","caption":"Habitantes da vila","visual_action":"Os habitantes recebem a equipe."},
            {"title":"Pistas","caption":"A surpresa","visual_action":"Luna encontra uma pista inesperada."}
        ]
        fingerprints = []
        for idx, scene in enumerate(sample):
            img = draw_official_scene(
                idx,"Oceânia Azul",scene["visual_action"],
                width=640,height=360,scene=scene,biome="oceanos brilhantes"
            )
            self.assertEqual(img.size,(640,360))
            self.assertGreater(len(img.getcolors(640*360) or []), 10)
            fingerprints.append(hashlib.sha256(img.tobytes()).hexdigest())
        self.assertEqual(len(set(fingerprints)),len(fingerprints))

    def test_emotions_follow_story(self):
        self.assertEqual(emotions("Uma surpresa inesperada!")[0],"surpresa")
        self.assertEqual(emotions("Descobriu uma pista")[0],"surpresa")
        self.assertEqual(emotions("Precisamos organizar um plano")[0],"concentracao")

    def test_original_music_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            path=create_music(Path(temp)/"music.wav",2.0,"Aurora-7")
            with wave.open(str(path),"rb") as song:
                self.assertEqual(song.getnchannels(),1)
                self.assertAlmostEqual(song.getnframes()/song.getframerate(),2.0,places=2)


if __name__=="__main__":
    unittest.main()
