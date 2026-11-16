"""Narrated 2D CPU animation tests, no GPU, Blender, API credits or image worker."""
import math
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from backend.app import narrated_draw_2d, renderer, comic_panels
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

    def test_comic_panel_layout_has_unique_reading_order(self):
        for portrait, size in ((True, (720,1280)), (False, (1280,720))):
            rects = comic_panels.layout(*size, portrait)
            self.assertEqual(len(rects), 3 if portrait else 4)
            for x0, y0, x1, y1 in rects:
                self.assertGreater(x1, x0)
                self.assertGreater(y1, y0)
                self.assertGreaterEqual(x0, 0)
                self.assertLessEqual(x1, size[0])
                self.assertLessEqual(y1, size[1])

    def test_comic_page_reveals_only_active_panel(self):
        src = Image.new("RGB", (320,180), "#26aa55")
        size = (720,1280)
        blank, panel = comic_panels.comic_page(
            [src], size, "Pequenos Guardiões", True, "paper", 0
        )
        finished, same = comic_panels.comic_page(
            [src], size, "Pequenos Guardiões", True, "color", 0
        )
        x0,y0,x1,y1=panel
        self.assertEqual(panel, same)
        self.assertNotEqual(blank.getpixel(((x0+x1)//2,(y0+y1)//2)),
                            finished.getpixel(((x0+x1)//2,(y0+y1)//2)))

    def test_real_hand_is_optional_but_must_be_transparent_photo(self):
        with mock.patch.dict("os.environ", {"ANIMA_REAL_HAND_PNG": ""}):
            self.assertIsNone(comic_panels.hand_asset())
        with tempfile.TemporaryDirectory() as tmp:
            opaque = Path(tmp)/"hand.png"
            Image.new("RGB", (200,200), "red").save(opaque)
            with mock.patch.dict("os.environ", {"ANIMA_REAL_HAND_PNG": str(opaque)}):
                with self.assertRaises(ValueError):
                    comic_panels.hand_asset()

    def test_curated_art_is_strict_when_quality_gate_is_enabled(self):
        plan=build_episode_plan(0)
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict("os.environ", {"ANIMA_COMIC_REQUIRE_CURATED_ART": "1"}):
                with self.assertRaisesRegex(ValueError,"arte de quadrinhos aprovada"):
                    narrated_draw_2d.artwork_for_scene(
                        plan,0,"16:9",320,180,1,15,workdir=Path(tmp)
                    )

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
    def test_green_screen_film_of_hand_is_composited_with_ffmpeg(self):
        with tempfile.TemporaryDirectory(prefix="anima-hand-comic-") as tmp:
            directory = Path(tmp)
            paper, sketch, colored = [directory / (x+".png")
                                      for x in ("paper","sketch","colored")]
            Image.new("RGB",(320,180),"#faf5e9").save(paper)
            Image.new("RGB",(320,180),"#292929").save(sketch)
            Image.new("RGB",(320,180),"#75ad79").save(colored)
            real_film=directory/"hand.mp4"
            cmd=[
                shutil.which("ffmpeg"),"-y","-loglevel","error",
                "-f","lavfi","-i","color=c=0x00ff00:s=160x120:r=12:d=4",
                "-vf","drawbox=x=70:y=20:w=40:h=80:color=0xc27f48:t=fill",
                "-pix_fmt","yuv420p",str(real_film),
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            output=directory/"with-hand.mp4"
            narrated_draw_2d._render_scene_clip(
                shutil.which("ffmpeg"),paper,sketch,colored,real_film,
                output,3.0,8,active_panel=(10,10,310,170),
            )
            self.assertGreater(output.stat().st_size,1000)
            self.assertGreater(renderer._probe_duration(output),2.7)

    def test_real_ffmpeg_progressively_reveals_pencil_and_color(self):
        with tempfile.TemporaryDirectory(prefix="anima-draw2d-") as tmp:
            directory = Path(tmp)
            paper, sketch, colored = [directory / (name+".png")
                                      for name in ("paper", "sketch", "colored")]
            pencil = directory / "pencil.png"
            Image.new("RGB", (320, 180), "#faf5e9").save(paper)
            Image.new("RGB", (320, 180), "#555555").save(sketch)
            Image.new("RGB", (320, 180), "#75ad79").save(colored)
            # The automatic renderer never creates a flying cartoon pencil.
            output = directory / "progressive.mp4"
            narrated_draw_2d._render_scene_clip(
                shutil.which("ffmpeg"), paper, sketch, colored, None,
                output, 3.0, 8,
            )
            self.assertGreater(output.stat().st_size, 1000)
            duration = renderer._probe_duration(output)
            self.assertGreater(duration, 2.7)
            self.assertLess(duration, 3.3)


if __name__ == "__main__":
    unittest.main()
