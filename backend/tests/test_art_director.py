"""Illustration-first art-bible regression checks: no Blender required."""
from __future__ import annotations
import unittest

from backend.app.art_director import (
    ART_PIPELINE_VERSION, ART_STYLE, CAST, NEGATIVE, POSES, create_art_plan,
)


class ArtDirectorTests(unittest.TestCase):
    def test_character_identity_is_locked_across_scenes_and_formats(self):
        plan = {"planet": "Aurora-7", "biome": "jardim mágico",
                "scenes": [
                    {"title": "Uma surpresa", "visual_action": "Luna encontra uma pista."},
                    {"title": "A descoberta", "visual_action": "Pipo fareja a ponte."},
                ]}
        vertical = create_art_plan(plan, "9:16")
        horizontal = create_art_plan(plan, "16:9")
        self.assertEqual(vertical["version"], ART_PIPELINE_VERSION)
        self.assertEqual(vertical["identity_lock"], horizontal["identity_lock"])
        self.assertEqual(len(vertical["characters"]), 3)
        self.assertEqual(len(vertical["scenes"]), 2)
        self.assertEqual(vertical["scenes"][0]["background_asset"], "scenes/scene-00/background.png")
        self.assertIn("without characters", vertical["scenes"][0]["prompt"].lower())
        self.assertIn("vertical 9:16", vertical["scenes"][0]["prompt"])
        self.assertIn("wide 16:9", horizontal["scenes"][0]["prompt"])
        self.assertEqual(set(c["name"] for c in vertical["characters"]), {"Luna", "Tomi", "Pipo"})
        self.assertTrue(all(len(c["layers_required"]) >= 6 for c in vertical["characters"]))
        self.assertEqual(len(CAST), 3)

    def test_invalid_format_is_rejected(self):
        with self.assertRaises(ValueError):
            create_art_plan({}, "1:1")

    def test_scene_strings_are_cleaned_without_removing_letters(self):
        sample = {"scenes": [{"title": "Tomi caminha e aprende", "visual_action": "Pipo corre."}]}
        plan = create_art_plan(sample)
        self.assertIn("Tomi caminha e aprende", plan["scenes"][0]["prompt"])
        self.assertIn("Pipo corre.", plan["scenes"][0]["prompt"])
        self.assertIn("plastic toy", NEGATIVE)
        self.assertIn("story", ART_STYLE)
        self.assertIn("talking", POSES)


if __name__ == "__main__":
    unittest.main()
