"""Reference-aware character production contract, without live billable calls."""
from __future__ import annotations

import os
import io
import unittest
from unittest import mock
from PIL import Image

from backend.app.character_reference_ai import (
    reference_sheet, reference_digest, stage_direction)
from backend.app.illustrated_scene_engine import (
    character_mode, cache_tag, selected_model, _cloudflare_call)


class CharacterReferenceTests(unittest.TestCase):
    def test_built_in_character_sheet_small_enough_for_cloudflare(self):
        data=reference_sheet()
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.size,(480,480))
        self.assertEqual(len(reference_digest()),16)

    def test_city_scale_and_native_focus_from_narration(self):
        scene={"title":"Visita à vila",
               "visual_action":"Os moradores mostram suas casas coloridas."}
        text=stage_direction(scene,2,"Vermelhão","deserto vermelho",
                             "town","Rochins")
        self.assertIn("houses considerably taller than people",text)
        self.assertIn("1-3 endearing distinctive indigenous residents",text)
        self.assertIn("image 0",text)
        self.assertIn("pink spacesuit",text)

    def test_panorama_distant_people_and_no_residents(self):
        scene={"title":"Vista do planeta",
               "visual_action":"A equipe observa o horizonte."}
        text=stage_direction(scene,0,"Aurora-7","cristais",
                             "lookout","Lumin")
        self.assertIn("18-25 percent",text)
        self.assertIn("No extra indigenous residents",text)

    def test_model_switch_needs_explicit_opt_in(self):
        with mock.patch.dict(os.environ, {
            "CLOUDFLARE_API_TOKEN":"test", "CLOUDFLARE_ACCOUNT_ID":"account",
            "ANIMA_CHARACTER_MODE":"reference_ai",
            "ANIMA_SCENE_IMAGE_PROVIDER":"cloudflare",
        }):
            self.assertEqual(
                selected_model(),"@cf/black-forest-labs/flux-2-klein-4b")
            tag=cache_tag()
            self.assertEqual(len(tag),12)
            self.assertEqual(character_mode(),"reference_ai")
        with mock.patch.dict(os.environ,{
            "ANIMA_CHARACTER_MODE":"fixed",
            "ANIMA_SCENE_IMAGE_PROVIDER":"cloudflare"
        }):
            self.assertNotEqual(cache_tag(),tag)

    def test_cloudflare_uses_multipart_reference_and_avoids_seed(self):
        import base64
        response=mock.Mock()
        response.status_code=200
        response.json.return_value={"success":True,"result":{
            "image":base64.b64encode(b"image").decode()}}
        client=mock.MagicMock()
        client.post.return_value=response
        client_context=mock.MagicMock()
        client_context.__enter__.return_value=client
        with mock.patch.dict(os.environ,{
            "CLOUDFLARE_API_TOKEN":"secret-test",
            "CLOUDFLARE_ACCOUNT_ID":"test-account",
            "ANIMA_CHARACTER_MODE":"reference_ai",
            "ANIMA_SCENE_IMAGE_PROVIDER":"cloudflare",
        }):
            with mock.patch("backend.app.illustrated_scene_engine.httpx.Client",
                            return_value=client_context):
                self.assertEqual(_cloudflare_call(
                    "Luna Tomi Pipo in a colorful alien city",1,"Aurora-7"),
                    b"image")
        kwargs=client.post.call_args.kwargs
        self.assertIn("input_image_0",kwargs["files"])
        self.assertEqual(kwargs["data"]["width"],"1024")
        self.assertNotIn("seed",kwargs["data"])
        self.assertNotIn("Content-Type",kwargs["headers"])
        self.assertEqual(kwargs["files"]["input_image_0"][2],"image/png")


if __name__=="__main__":
    unittest.main()
