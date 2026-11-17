"""Isolated regression tests: never contact a paid image endpoint."""
import base64
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from backend.app.illustrated_scene_engine import (
    enabled, illustrated_background, scene_prompt, ART_VERSION,
)
from backend.app.planet_art_direction import profile_for


class IllustratedSceneEngineTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "planet": "Vermelhão",
            "biome": "cânions vermelhos e desertos de areia dourada",
            "inhabitants": "Rochins, simpáticos construtores de pontes",
            "landmark": "Vale dos Ventos",
            "mission_object": "ponte de pedra",
        }
        self.scene = {
            "title": "Atravessando a ponte",
            "caption": "Luna e Tomi descobrem uma travessia",
            "visual_action": "A equipe atravessa a ponte sobre o rio.",
            "spoken_excerpt": "Olhem a ponte! Precisamos ajudar os moradores.",
        }

    def test_world_identity_and_narrative_are_in_prompt(self):
        prompt = scene_prompt(self.plan, self.scene, 2)
        for expected in ("Vermelhão", "Rochins", "cânions vermelhos",
                         "atravessa a ponte", "Vale dos Ventos"):
            self.assertIn(expected, prompt)
        self.assertIn("Do NOT draw Luna, Tomi, Pipo", prompt)

    def test_planets_create_different_briefs(self):
        other=dict(self.plan)
        other.update(planet="Oceânia Azul",biome="oceanos brilhantes e cidades sob redomas")
        self.assertNotEqual(
            scene_prompt(self.plan,self.scene,2),
            scene_prompt(other,self.scene,2),
        )
        self.assertNotEqual(profile_for("Vermelhão")[0],
                            profile_for("Oceânia Azul")[0])

    def test_no_api_key_preserves_legacy_mode(self):
        env={"ANIMA_SCENE_IMAGE_API_KEY":"","OPENAI_API_KEY":"",
             "ANIMA_REQUIRE_ILLUSTRATED_SCENES":"0"}
        with mock.patch.dict(os.environ,env):
            self.assertFalse(enabled())
            with tempfile.TemporaryDirectory() as temp:
                self.assertIsNone(illustrated_background(
                    self.plan,self.scene,0,Path(temp)))

    def test_premium_mode_fails_instead_of_claiming_quality(self):
        env={"ANIMA_SCENE_IMAGE_API_KEY":"","OPENAI_API_KEY":"",
             "ANIMA_REQUIRE_ILLUSTRATED_SCENES":"1"}
        with mock.patch.dict(os.environ,env):
            with tempfile.TemporaryDirectory() as temp:
                with self.assertRaisesRegex(RuntimeError,"API_KEY"):
                    illustrated_background(self.plan,self.scene,0,Path(temp))

    def test_generated_background_cached_once_without_network_on_retry(self):
        source=Image.new("RGB",(768,512),(114,210,143))
        blob=io.BytesIO()
        source.save(blob,format="PNG")
        encoded=base64.b64encode(blob.getvalue()).decode()
        response=mock.Mock()
        response.status_code=200
        response.raise_for_status.return_value=None
        response.json.return_value={"data":[{"b64_json":encoded}]}
        client=mock.MagicMock()
        client.post.return_value=response
        manager=mock.MagicMock()
        manager.__enter__.return_value=client
        env={"ANIMA_SCENE_IMAGE_API_KEY":"fake-test-only",
             "ANIMA_SCENE_IMAGE_MODEL":"gpt-image-2.5-flare",
             "ANIMA_SCENE_IMAGE_QUALITY":"medium"}
        with mock.patch.dict(os.environ,env):
            with tempfile.TemporaryDirectory() as temp:
                with mock.patch("backend.app.illustrated_scene_engine.httpx.Client",
                                return_value=manager):
                    first=illustrated_background(
                        self.plan,self.scene,0,Path(temp),output_size=(640,360))
                    second=illustrated_background(
                        self.plan,self.scene,0,Path(temp),output_size=(640,360))
                self.assertEqual(first.size,(640,360))
                self.assertEqual(first.tobytes(),second.tobytes())
                self.assertEqual(client.post.call_count,1)


if __name__=="__main__":
    unittest.main()
