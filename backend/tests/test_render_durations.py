import shutil
import tempfile
import unittest
from pathlib import Path

from backend.app.worlds import build_episode_plan
from PIL import ImageChops

import backend.app.renderer as renderer
from backend.app.renderer import render_episode, draw_scene_frame, VOICE_PROFILE


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe") and shutil.which("espeak-ng") and shutil.which("blender"),
                     "FFmpeg/ffprobe/espeak-ng/Blender not installed")
class RenderDurationTests(unittest.TestCase):
    def test_scene_art_changes_without_text_overlays_and_voice_cast_is_stable(self):
        first = draw_scene_frame(
            (270, 480), ("A CHEGADA", "Legenda não deve aparecer", ""), 0, 5,
            True, "Aurora-7", biome="florestas de cristais", mission_object="farol",
            landmark="Grande Bosque"
        )
        reveal = draw_scene_frame(
            (270, 480), ("A SURPRESA", "Outra legenda que não deve aparecer", ""), 7, 5,
            True, "Aurora-7", biome="florestas de cristais", mission_object="farol",
            landmark="Grande Bosque"
        )
        self.assertEqual(first.size, (270, 480))
        self.assertIsNotNone(ImageChops.difference(first, reveal).getbbox())
        self.assertEqual(
            {name: profile["voice"] for name, profile in VOICE_PROFILE.items()},
            {
                "Narrador": "pt-BR-ThalitaMultilingualNeural",
                "Luna": "pt-BR-FranciscaNeural",
                "Tomi": "pt-BR-AntonioNeural",
                "Pipo": "pt-BR-AntonioNeural",
                "Moradora": "pt-BR-ThalitaMultilingualNeural",
            },
        )

    def test_horizontal_and_vertical_duration_contracts(self):
        plan = build_episode_plan(0)
        with tempfile.TemporaryDirectory(prefix="anima2d-test-") as tmp:
            root = Path(tmp)
            long_video = root / "episode-16x9.mp4"
            short_video = root / "episode-9x16.mp4"
            # Keep CI lightweight while still running Blender, rendering real 3D
            # geometry, synthesizing dialogue and validating final MP4 duration/resolution.
            original_fps = renderer.FPS
            renderer.FPS = 0.04
            try:
                long_result = render_episode(
                    plan["title"], plan["long_script"], "16:9", long_video, root,
                    planet_name=plan["planet"], story_plan=plan
                )
                short_result = render_episode(
                    plan["title"], plan["long_script"], "9:16", short_video, root,
                    planet_name=plan["planet"], story_plan=plan
                )
            finally:
                renderer.FPS = original_fps

            self.assertTrue(long_video.exists())
            self.assertTrue(short_video.exists())
            self.assertGreater(long_result["duration_seconds"], 300)
            self.assertLessEqual(long_result["duration_seconds"], 600)
            self.assertTrue({"Luna", "Tomi", "Pipo", "Narrador"}.issubset(set(long_result["speakers"])))
            self.assertGreaterEqual(short_result["duration_seconds"], 60)
            self.assertLessEqual(short_result["duration_seconds"], 90)
            self.assertTrue({"Luna", "Tomi", "Pipo", "Narrador"}.issubset(set(short_result["speakers"])))
            self.assertEqual(short_result["scene_count"], len(plan["short_scene_indices"]))
            self.assertEqual(long_result["resolution"], "1920x1080")
            self.assertEqual(short_result["resolution"], "1080x1920")
            self.assertEqual(long_result["render_engine"], "Blender 3D")
            self.assertEqual(short_result["render_engine"], "Blender 3D")


if __name__ == "__main__":
    unittest.main()
