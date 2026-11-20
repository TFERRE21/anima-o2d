"""The long-format policy must allow calm 5–15-minute stories."""
import unittest
from pathlib import Path
from backend.app.worlds import build_episode_plan


class LongDurationLimitTests(unittest.TestCase):
    def test_planned_limits(self):
        limits=build_episode_plan(0)["duration_targets"]
        self.assertEqual(limits["16:9"]["min_seconds"],300)
        self.assertEqual(limits["16:9"]["max_seconds"],900)
        self.assertEqual(limits["9:16"]["max_seconds"],90)

    def test_render_and_publish_admit_691_second_long_narration(self):
        narrator=Path("backend/app/narrated_draw_2d.py").read_text(encoding="utf-8")
        backend=Path("backend/app/main.py").read_text(encoding="utf-8")
        self.assertIn('else (300, 900)',narrator)
        self.assertIn('not 300 <= measured <= 900',narrator)
        self.assertIn('longest=900 if fmt=="16:9" else 100',backend)
        self.assertGreater(900-1.2,691.6)

    def test_89_second_short_has_room_without_speech_acceleration(self):
        source=Path("backend/app/narrated_draw_2d.py").read_text(encoding="utf-8")
        self.assertIn('if raw_seconds > maximum:',source)
        self.assertIn('if narration_seconds > maximum:',source)
        self.assertIn('duration = min(maximum, narration_seconds + 1.2)',source)
        raw_seconds=89.1
        result=min(90,raw_seconds+1.2)
        self.assertEqual(result,90)
        self.assertGreater(result-raw_seconds,0)

    def test_shorts_limits_not_changed(self):
        narrator=Path("backend/app/narrated_draw_2d.py").read_text(encoding="utf-8")
        self.assertIn('(60, 90) if fmt == "9:16"',narrator)
        self.assertIn('not 60 <= measured <= 90',narrator)

if __name__=="__main__":
    unittest.main()
