import unittest

from backend.app.worlds import build_episode_plan


class StoryEngineTests(unittest.TestCase):
    def test_generates_distinct_planets_and_stories(self):
        used = set()
        titles = set()
        stories = set()
        for number in range(35):
            plan = build_episode_plan(number, used)
            self.assertNotIn(plan["planet"], used)
            self.assertNotIn(plan["title"], titles)
            self.assertNotIn(plan["long_script"], stories)
            self.assertEqual(len(plan["scenes"]), 12)
            self.assertEqual(plan["characters"], ["Luna", "Tomi", "Pipo"])
            used.add(plan["planet"])
            titles.add(plan["title"])
            stories.add(plan["long_script"])

    def test_duration_contracts_and_script_lengths(self):
        plan = build_episode_plan(0)
        self.assertGreaterEqual(plan["word_count_long"], 650)
        self.assertGreaterEqual(plan["word_count_short"], 80)
        self.assertLessEqual(plan["word_count_short"], 200)
        self.assertEqual(plan["duration_targets"]["16:9"]["min_seconds"], 301)
        self.assertEqual(plan["duration_targets"]["9:16"]["min_seconds"], 60)
        self.assertEqual(plan["duration_targets"]["9:16"]["max_seconds"], 90)

    def test_story_has_mission_and_learning(self):
        plan = build_episode_plan(4)
        self.assertTrue(plan["planet"])
        self.assertTrue(plan["challenge"])
        self.assertTrue(plan["value"])
        self.assertIn("Luna", plan["long_script"])
        self.assertIn("Tomi", plan["long_script"])
        self.assertIn("Pipo", plan["long_script"])


if __name__ == "__main__":
    unittest.main()
