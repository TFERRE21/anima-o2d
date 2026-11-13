"""Production gate for AI-generated backgrounds and transparent recurring cast."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

from backend.app.art_assets import (
    art_path, inspect_png, approve_art, approved_path, readiness,
    cutout_white_background,
)
from backend.app.art_director import create_art_plan


def png(width, height, *, transparent=False, white=False):
    bg = ((255, 255, 255, 255) if white else
          ((0, 0, 0, 0) if transparent else (100, 182, 215, 255)))
    im = Image.new("RGBA", (width, height), bg)
    if transparent or white:
        ImageDraw.Draw(im).ellipse((width//4, height//5, 3*width//4, 4*height//5),
                                   fill=(230, 70, 120, 255))
    f = io.BytesIO()
    im.save(f, "PNG")
    return f.getvalue()


class ApprovedArtTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = Path(self.tmp.name)
        self.job = "a1b2c3d4e5f6"
        self.story = {
            "planet": "Aurora-7", "scenes": [
                {"title": "Uma visita", "visual_action": "Luna entra no jardim."},
                {"title": "Um achado", "visual_action": "Pipo encontra a pista."},
            ],
            "short_scene_indices": [1],
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_cast_transparency_and_scene_ratio_required(self):
        with self.assertRaisesRegex(ValueError, "transparente|transparência"):
            inspect_png(png(320, 480), "luna", "9:16")
        with self.assertRaisesRegex(ValueError, "vertical"):
            inspect_png(png(768, 432), "scene-00-background", "9:16")
        info = inspect_png(png(320, 480, transparent=True), "luna", "9:16")
        self.assertEqual(info["width"], 320)

    def test_shared_cast_and_scene_approval_gate(self):
        for character in ("luna", "tomi", "pipo"):
            approve_art(self.storage, self.job, character, "9:16",
                        png(320, 480, transparent=True), self.story)
        approve_art(self.storage, self.job, "scene-01-background", "9:16",
                    png(432, 768), self.story)
        short = readiness(self.storage, self.job, self.story, "9:16", [1])
        self.assertTrue(short["ready"])
        self.assertFalse(readiness(self.storage, self.job, self.story, "16:9")["ready"])
        # Even if the PNG is present, edits without reapproval invalidate it.
        original = art_path(self.storage, self.job, "luna", "16:9")
        original.write_bytes(b"tampered!")
        self.assertIsNone(approved_path(self.storage, self.job, "luna",
                                        "9:16", short["identity_lock"]))

    def test_candidate_white_background_cutout(self):
        result = cutout_white_background(png(320, 480, white=True))
        info = inspect_png(result, "tomi", "9:16")
        self.assertGreater(info["bytes"], 100)
        with Image.open(io.BytesIO(result)) as image:
            self.assertEqual(image.convert("RGBA").getpixel((0, 0))[3], 0)
            self.assertEqual(image.convert("RGBA").getpixel((160, 200))[3], 255)

    def test_unrecognized_appearance_is_never_approved(self):
        with self.assertRaisesRegex(ValueError, "Material"):
            approve_art(self.storage, self.job, "random-villain", "9:16",
                        png(320, 480, transparent=True), self.story)
        self.assertEqual(create_art_plan(self.story)["identity_lock"],
                         create_art_plan(self.story, "16:9")["identity_lock"])


if __name__ == "__main__":
    unittest.main()
