"""Regression tests for approved-cast dynamic comics and soundtrack."""
import hashlib
import shutil
import subprocess
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

    def test_story_balloon_and_spaceship_composition(self):
        from backend.app.story_comic_director import _balloon, render_story_background
        from PIL import Image, ImageDraw
        base, theme, _ = render_story_background(
            (640,360),0,"Aurora-7","cristais",{
                "title":"A partida","caption":"Nave decola",
                "visual_action":"A tripulação confere os cintos na nave Estrelinha."
            })
        self.assertEqual(theme, "nave")
        self.assertEqual(base.size,(640,360))
        bubble=Image.new("RGB",(640,360),"#c8e5f9")
        _balloon(ImageDraw.Draw(bubble),"UAU!",(180,85),(185,150),
                 canvas_size=bubble.size)
        self.assertNotEqual(bubble.getpixel((180,85)),(200,229,249))

    @unittest.skipUnless(shutil.which("ffmpeg"),"ffmpeg não instalado")
    def test_narration_music_duck_filter(self):
        # Make sure narration is split before both sidechain + final mix.
        filters=(
            "[0:a]apad=pad_dur=1,asplit=2[voice][key];"
            "[1:a]volume=0.30,lowpass=f=2400[music];"
            "[music][key]sidechaincompress=threshold=0.012:ratio=5:attack=80:release=500[duck];"
            "[voice][duck]amix=inputs=2:duration=first:weights='1 0.32':normalize=0[a]"
        )
        command=[
            "ffmpeg","-hide_banner","-loglevel","error","-y",
            "-f","lavfi","-i","sine=frequency=440:duration=0.5",
            "-f","lavfi","-i","sine=frequency=523:duration=0.5",
            "-filter_complex",filters,"-map","[a]","-t","0.5","-f","null","-"
        ]
        result=subprocess.run(command,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_every_planet_has_its_own_identity(self):
        from backend.app.planet_art_direction import (
            PROFILES,profile_for,draw_background,scene_theme,
        )
        from backend.app.worlds import WORLDS
        distinct=set()
        for world in WORLDS:
            key,profile=profile_for(
                world["planet"],world["biome"],world["inhabitants"])
            distinct.add(key)
            self.assertIn(profile["species"],
                          {entry["species"] for entry in PROFILES.values()})
        self.assertGreaterEqual(len(distinct),7)

    def test_narration_changes_scene_without_changing_planet(self):
        from backend.app.planet_art_direction import draw_background
        planet="Vermelhão"
        biome="cânions vermelhos e desertos de areia dourada"
        native="Rochins, simpáticos construtores de pontes"
        scenes=[
            {"title":"Na vila","visual_action":"Os moradores recebem a equipe."},
            {"title":"Na ponte","visual_action":"Os amigos atravessam a ponte sobre o rio."},
            {"title":"A pista","visual_action":"Luna investiga pegadas estranhas."},
        ]
        pictures=[]
        themes=[]
        identities=[]
        for idx,scene in enumerate(scenes):
            picture,theme,key,profile=draw_background(
                (640,360),planet,biome,native,scene,idx)
            pictures.append(hashlib.sha256(picture.tobytes()).hexdigest())
            themes.append(theme)
            identities.append(profile["species"])
        self.assertEqual(themes,["town","river","clue"])
        self.assertEqual(len(set(pictures)),3)
        self.assertEqual(len(set(identities)),1)

    def test_original_music_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            path=create_music(Path(temp)/"music.wav",2.0,"Aurora-7")
            with wave.open(str(path),"rb") as song:
                self.assertEqual(song.getnchannels(),1)
                self.assertAlmostEqual(song.getnframes()/song.getframerate(),2.0,places=2)


if __name__=="__main__":
    unittest.main()
