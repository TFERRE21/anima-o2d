import shutil
import tempfile
import unittest
from pathlib import Path

from backend.app.worlds import build_episode_plan
from backend.app.renderer import render_episode


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe") and shutil.which("espeak-ng"),
                     "FFmpeg/ffprobe/espeak-ng not installed")
class RenderDurationTests(unittest.TestCase):
    def test_horizontal_and_vertical_duration_contracts(self):
        plan = build_episode_plan(0)
        with tempfile.TemporaryDirectory(prefix="anima2d-test-") as tmp:
            root = Path(tmp)
            long_video = root / "episode-16x9.mp4"
            short_video = root / "episode-9x16.mp4"

            long_result = render_episode(
                plan["title"], plan["long_script"], "16:9", long_video, root,
                planet_name=plan["planet"], story_plan=plan
            )
            short_result = render_episode(
                plan["title"], plan["long_script"], "9:16", short_video, root,
                planet_name=plan["planet"], story_plan=plan
            )

            self.assertTrue(long_video.exists())
            self.assertTrue(short_video.exists())
            self.assertGreater(long_result["duration_seconds"], 300)
            self.assertGreaterEqual(short_result["duration_seconds"], 60)
            self.assertLessEqual(short_result["duration_seconds"], 90)
            self.assertEqual(long_result["resolution"], "1920x1080")
            self.assertEqual(short_result["resolution"], "1080x1920")


if __name__ == "__main__":
    unittest.main()
