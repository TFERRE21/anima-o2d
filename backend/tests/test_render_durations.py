"""Narrated 2D CPU animation tests, no GPU, Blender, API credits or image worker."""
import math
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from backend.app import narrated_draw_2d, renderer
from backend.app.worlds import build_episode_plan


class NarratedDrawingTests(unittest.TestCase):
    def test_only_narrator_voice_in_existing_dialogue(self):
        plan = build_episode_plan(0)
        segments = narrated_draw_2d.narrator_segments(plan, "9:16", "Uma história.")
        self.assertTrue(segments)
        self.assertEqual({s["speaker"] for s in segments}, {"Narrador"})
        self.assertTrue(any("Luna disse:" in s["text"] for s in segments))
        self.assertEqual(narrated_draw_2d.scene_index_order(plan, "9:16"), [7, 8, 9, 10, 11])
        self.assertEqual(narrated_draw_2d.scene_index_order(plan, "16:9"), list(range(15)))

    def test_scene_durations_follow_narration(self):
        times = [
            {"scene": 0, "start": 0, "end": 12},
            {"scene": 1, "start": 12, "end": 32},
            {"scene": 2, "start": 32, "end": 40},
        ]
        secs = narrated_draw_2d.scene_seconds([0, 1, 2], times, 60)
        self.assertAlmostEqual(sum(secs), 60, places=3)
        self.assertGreater(secs[1], secs[0])
        self.assertGreater(secs[0], secs[2])

    def test_illustrations_reuse_the_fixed_2d_cast_without_photo_api(self):
        plan = build_episode_plan(0)
        art, sketch = narrated_draw_2d.artwork_for_scene(
            plan, 0, "16:9", 320, 180, 1, 15
        )
        self.assertEqual(art.size, (320, 180))
        self.assertEqual(sketch.size, art.size)
        self.assertNotEqual(art.getpixel((100, 80)), sketch.getpixel((100, 80)))
        self.assertFalse(narrated_draw_2d.DRAW_ENGINE.lower().find("cpu") < 0)

    def test_renderer_dispatch_requires_no_gpu_art(self):
        plan = build_episode_plan(0)
        output = Path("/unused/episode.mp4")
        with mock.patch.object(narrated_draw_2d, "render_narrated_draw_episode",
                               return_value={"render_engine": narrated_draw_2d.DRAW_ENGINE}) as draw:
            result = renderer.render_episode(
                "Uma aventura", "Nossa história.",
                "9:16", output, Path("/unused"), story_plan=plan
            )
        self.assertEqual(result["render_engine"], narrated_draw_2d.DRAW_ENGINE)
        self.assertEqual(draw.call_count, 1)


@unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required for real CPU illustration test")
class DrawingMediaTests(unittest.TestCase):
    def test_real_ffmpeg_progressively_reveals_pencil_and_color(self):
        with tempfile.TemporaryDirectory(prefix="anima-draw2d-") as tmp:
            directory = Path(tmp)
            paper, sketch, colored = [directory / (name+".png")
                                      for name in ("paper", "sketch", "colored")]
            pencil = directory / "pencil.png"
            Image.new("RGB", (320, 180), "#faf5e9").save(paper)
            Image.new("RGB", (320, 180), "#555555").save(sketch)
            Image.new("RGB", (320, 180), "#75ad79").save(colored)
            narrated_draw_2d._pencil_image().save(pencil)
            output = directory / "progressive.mp4"
            narrated_draw_2d._render_scene_clip(
                shutil.which("ffmpeg"), paper, sketch, colored, pencil,
                output, 3.0, 8,
            )
            self.assertGreater(output.stat().st_size, 1000)
            duration = renderer._probe_duration(output)
            self.assertGreater(duration, 2.7)
            self.assertLess(duration, 3.3)


if __name__ == "__main__":
    unittest.main()
