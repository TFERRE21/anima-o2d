"""Integration tests for inline approval and automatic image queue (offline-safe)."""
from __future__ import annotations
import os
import queue
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Importing FastAPI main initializes its persistent store. Keep CI isolated
# from the VPS-only /data volume, which is not writable on GitHub Actions.
os.environ.setdefault("ANIMA_STORAGE", str(Path(tempfile.gettempdir()) / "anima-studio-ci-jobs"))
from backend.app import comfy_worker, main


class UnifiedStudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.storage = Path(self.temp.name)
        self.job_id = "c0ffeec0ffee"
        self.story = {
            "planet": "Aurora-7", "biome": "floresta estelar",
            "scenes": [
                {"title": "Chegada", "visual_action": "A equipe chega ao planeta."},
                {"title": "Trilha", "visual_action": "Pipo encontra pistas."},
            ],
            "short_scene_indices": [0],
        }
        self.job = {"id": self.job_id, "status": "story_ready",
                    "story_plan": self.story, "formats": ["16:9", "9:16"]}
        self.overrides = [
            mock.patch.object(main, "STORAGE", self.storage),
            mock.patch.object(main, "_get_job", return_value=self.job),
            mock.patch.object(main, "_update"),
            mock.patch.object(comfy_worker, "_tasks", {}),
            mock.patch.object(comfy_worker, "_queue", queue.Queue()),
            mock.patch.object(comfy_worker, "_store", self.storage / "comfyui" / "task-state.json"),
            mock.patch.object(comfy_worker, "_workers", {}),
        ]
        for patch in self.overrides:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.overrides):
            patch.stop()
        self.temp.cleanup()

    def test_approve_queues_every_new_planet_art_without_connected_gpu(self):
        output = main.approve_story_generate_images(self.job_id)
        self.assertFalse(output["worker_connected"])
        self.assertEqual(output["queued"], 6)  # three fixed protagonists + 2 wide + 1 short
        self.assertEqual(len(comfy_worker._tasks), 6)
        self.assertEqual(comfy_worker._queue.qsize(), 6)
        self.assertTrue(comfy_worker._store.exists())
        self.assertEqual(sum(1 for task in comfy_worker._tasks.values()
                             if task["asset_id"] == "luna"), 1)
        # A duplicate approval does not duplicate tasks or overwrite character images.
        second = main.approve_story_generate_images(self.job_id)
        self.assertEqual(second["queued"], 0)
        self.assertEqual(len(comfy_worker._tasks), 6)

    def test_jobs_get_inline_status_even_with_offline_worker(self):
        main.approve_story_generate_images(self.job_id)
        board = main.get_episode_art_board(self.job_id)
        self.assertEqual(board["formats"], ["16:9", "9:16"])
        self.assertEqual(len(board["tasks"]), 6)
        self.assertFalse(board["ready"])
        self.assertFalse(board["worker_connected"])

    def test_render_is_blocked_before_approval_and_art_is_ready(self):
        with self.assertRaises(main.HTTPException) as ctx:
            main.render_story(self.job_id, main.RenderRequest(formats=["9:16"]))
        self.assertIn(ctx.exception.status_code, (409, 503))
        self.assertEqual(comfy_worker._queue.qsize(), 0)


if __name__ == "__main__":
    unittest.main()
